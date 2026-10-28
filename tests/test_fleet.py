"""The Fleet Overview page: families, readiness, the daily history and /overview."""
import json
import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import fleet
import sharepoint
from fake_sharepoint import FakeClock, FakeSharePoint, FakeTokens, fake_env, make_item

TZ = ZoneInfo('America/Los_Angeles')
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset(asset_type='VXE-30', condition='FMC', location=('Test Bay A',), serial='SN-1',
          status=('IN',), notes=''):
    return {'id': 1, 'asset_type': asset_type, 'condition': condition, 'location': list(location),
            'serial_number': serial, 'status': list(status), 'notes': notes,
            'checked_out_to': '', 'date_out': None, 'last_inventory': None,
            'part_number': '', 'ownership': '', 'shelf_location': ''}


def csv_data(assets):
    return {'fields': {}, 'assets': assets, 'source': 'test.csv', 'live': False,
            'loaded_at': datetime(2026, 1, 2, 9, 0, tzinfo=TZ)}


@pytest.fixture
def history(tmp_path, monkeypatch):
    """A fresh history file for the app, in a temporary folder."""
    h = fleet.ReadinessHistory(str(tmp_path / 'data' / 'readiness_history.jsonl'))
    monkeypatch.setattr(dashboard, 'HISTORY', h)
    return h


def lines(h):
    with open(h.path, encoding='utf-8') as f:
        return [json.loads(x) for x in f.read().splitlines()]


# --- Families ---------------------------------------------------------------

def test_mapped_unknown_and_blank_types():
    mapping = {'VXE-30': 'Aircraft', 'SGCS 1': 'Ground Control Station'}
    assert fleet.family_of('VXE-30', mapping) == 'Aircraft'
    assert fleet.family_of('SGCS 1', mapping) == 'Ground Control Station'
    assert fleet.family_of('Brand New Kit', mapping) == 'Unmapped'
    assert fleet.family_of('', mapping) == 'Unmapped'
    # Exact text only: a near-identical name is a different item.
    assert fleet.family_of('VXE30', mapping) == 'Unmapped'
    assert fleet.family_of('VXE-30 ', mapping) == 'Unmapped'


def test_unmapped_types_are_listed_with_their_rows():
    mapping = {'VXE-30': 'Aircraft'}
    rows = [asset('VXE-30'), asset('Brand New Kit'), asset('Brand New Kit'), asset('')]
    assert fleet.unmapped_types(rows, mapping) == [('Brand New Kit', 2), ('', 1)]


@pytest.mark.parametrize('content, reason', [
    ('{"VXE-30": "Aircraft", "SGCS 1": "Ground"}', 'not one of'),
    ('["VXE-30"]', 'does not hold'),
    ('{}', 'does not hold'),
    ('{"VXE-30": "Aircraft", "VXE-30": "Payload"}', 'twice'),
    ('{" ": "Support"}', 'blank'),
    ('{"VXE-30": "Aircraft",', 'not valid JSON'),
])
def test_badly_shaped_family_file_is_refused(tmp_path, content, reason):
    path = tmp_path / 'asset_families.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match=reason):
        fleet.read_families(str(path))
    mapping, problem = fleet.FamilyMap(str(path)).load()
    assert mapping == {} and reason in problem


def test_missing_family_file_makes_everything_unmapped_and_logs_once(tmp_path, monkeypatch,
                                                                     history, caplog):
    families = fleet.FamilyMap(str(tmp_path / 'asset_families.json'))
    monkeypatch.setattr(dashboard, 'FAMILIES', families)
    client = dashboard.app.test_client()
    with caplog.at_level(logging.INFO):
        html = client.get('/overview').get_data(as_text=True)
        client.get('/overview')
    assert 'could not be read, so every asset shows as Unmapped' in html
    assert 'Readiness &ndash;' in html  # Aircraft: nothing to divide by.
    logged = [r for r in caplog.records if 'shows as Unmapped' in r.getMessage()]
    assert len(logged) == 1 and 'there is no asset_families.json' in logged[0].getMessage()
    # Recorded today as all Unmapped, not as Support.
    day = lines(history)[0]
    assert day['families']['Unmapped']['total'] == day['total'] == 146
    assert day['families']['Support']['total'] == 0


def test_badly_shaped_family_file_shows_the_note(tmp_path, monkeypatch, history):
    path = tmp_path / 'asset_families.json'
    path.write_text('{"VXE-30": "Drone"}', encoding='utf-8')
    monkeypatch.setattr(dashboard, 'FAMILIES', fleet.FamilyMap(str(path)))
    html = dashboard.app.test_client().get('/overview').get_data(as_text=True)
    assert 'could not be read, so every asset shows as Unmapped' in html
    assert 'Unmapped</span>' in html


def report_05_mapping():
    """{Asset Type: Proposed family} from report 05's Step 3 table."""
    with open(os.path.join(REPO, 'reports', '05_asset_family_mapping.md'), encoding='utf-8') as f:
        text = f.read()
    step3 = text.split('## Step 3')[1].split('**Rows per family:**')[0]
    rows = {}
    for line in step3.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) == 5 and re.fullmatch(r'\d+', cells[1]):
            rows[cells[0]] = cells[2]
    return rows


def test_committed_family_file_matches_report_05():
    committed = fleet.read_families(fleet.ASSET_FAMILIES_PATH)
    expected = report_05_mapping()
    assert len(expected) == 29
    assert committed == expected


# --- Readiness ----------------------------------------------------------------

def test_readiness_leaves_destroyed_lost_out():
    rows = [asset(condition=c) for c in ['FMC', 'FMC', 'FMC', 'PMC', 'NMC', 'Destroyed/Lost']]
    r = fleet.readiness(rows)
    assert (r['total'], r['fmc'], r['pmc'], r['nmc'], r['lost']) == (6, 3, 1, 1, 1)
    assert r['pct'] == 60.0  # 3 / (6 - 1)


def test_readiness_with_nothing_to_divide_by_is_none():
    assert fleet.readiness([])['pct'] is None
    assert fleet.readiness([asset(condition='Destroyed/Lost')])['pct'] is None


def test_blank_condition_counts_in_the_total_and_lowers_the_percentage():
    r = fleet.readiness([asset(condition='FMC'), asset(condition='')])
    assert (r['total'], r['none'], r['pct']) == (2, 1, 50.0)


def test_unknown_condition_is_counted_not_lost():
    r = fleet.readiness([asset(condition='FMC'), asset(condition='Awaiting Parts')])
    assert (r['total'], r['other'], r['none'], r['pct']) == (2, 1, 0, 50.0)


def test_family_readiness_covers_all_five_families():
    mapping = {'VXE-30': 'Aircraft', 'E 95': 'Payload'}
    ready = fleet.fleet_readiness([asset('VXE-30'), asset('E 95', 'NMC'), asset('?')], mapping)
    assert list(ready['families']) == ['Aircraft', 'Ground Control Station', 'Payload',
                                       'Support', 'Unmapped']
    assert ready['families']['Payload']['pct'] == 0.0
    assert ready['families']['Unmapped']['total'] == 1
    assert ready['families']['Support']['pct'] is None


# --- Tables, filter and alerts ------------------------------------------------

def test_table_order():
    mapping = {'VXE-30': 'Aircraft', 'Block 40': 'Aircraft', 'SGCS 1': 'Ground Control Station'}
    rows = [
        asset('VXE-30', 'Destroyed/Lost', serial='A'),
        asset('VXE-30', 'FMC', serial='B'),
        asset('VXE-30', '', serial='C'),
        asset('VXE-30', 'PMC', serial='D'),
        asset('VXE-30', 'NMC', serial='E2'),
        asset('Block 40', 'NMC', serial='Z'),
        asset('VXE-30', 'NMC', serial='E1'),
        asset('SGCS 1', 'NMC', serial='G'),
    ]
    got = [(a['condition'], a['asset_type'], a['serial_number'])
           for a in fleet.table_rows(rows, mapping, 'Aircraft')]
    assert got == [
        ('NMC', 'Block 40', 'Z'), ('NMC', 'VXE-30', 'E1'), ('NMC', 'VXE-30', 'E2'),
        ('PMC', 'VXE-30', 'D'), ('FMC', 'VXE-30', 'B'), ('', 'VXE-30', 'C'),
        ('Destroyed/Lost', 'VXE-30', 'A'),
    ]


def test_location_filter():
    two = asset(location=('Bay A', 'Bay B'), serial='TWO')
    rows = [two, asset(location=('Bay A',), serial='A'), asset(location=(), serial='NONE')]
    assert [a['serial_number'] for a in fleet.filter_location(rows, 'Bay A')] == ['TWO', 'A']
    assert [a['serial_number'] for a in fleet.filter_location(rows, 'Bay B')] == ['TWO']
    assert [a['serial_number'] for a in fleet.filter_location(rows, fleet.NO_LOCATION)] == ['NONE']
    assert len(fleet.filter_location(rows, '')) == 3


def test_alerts_follow_the_attention_page_order():
    groups = [{'title': 'First', 'assets': [asset(serial='1'), asset(serial='2')]},
              {'title': 'Empty', 'assets': []},
              {'title': 'Second', 'assets': [asset(serial=str(n)) for n in range(3, 9)]}]
    rows, total = fleet.alerts(groups)
    assert total == 8
    assert [(t, a['serial_number']) for t, a in rows] == [
        ('First', '1'), ('First', '2'), ('Second', '3'), ('Second', '4'), ('Second', '5')]


# --- The daily snapshot -------------------------------------------------------

def test_two_loads_on_the_same_day_write_one_line(tmp_path):
    h = fleet.ReadinessHistory(str(tmp_path / 'h.jsonl'))
    families = fleet.FamilyMap()
    morning = datetime(2026, 10, 28, 0, 5, tzinfo=TZ)
    assert h.record(csv_data([asset()]), families, morning) is True
    assert h.record(csv_data([asset(), asset()]), families, morning + timedelta(hours=15)) is False
    assert len(lines(h)) == 1
    line = lines(h)[0]
    assert line['date'] == '2026-10-28' and line['recorded_at'] == '2026-10-28T00:05:00-07:00'
    assert line['source'] == 'test.csv' and line['total'] == 1
    assert line['readiness_pct'] == 100.0
    assert set(line['families']) == set(fleet.ALL_FAMILIES)
    assert set(line) >= {'fmc', 'pmc', 'nmc', 'destroyed_lost', 'no_condition'}


def test_next_day_writes_a_second_line(tmp_path):
    h = fleet.ReadinessHistory(str(tmp_path / 'h.jsonl'))
    day1 = datetime(2026, 10, 28, 23, 59, tzinfo=TZ)
    h.record(csv_data([asset()]), fleet.FamilyMap(), day1)
    h.record(csv_data([asset(condition='NMC')]), fleet.FamilyMap(), day1 + timedelta(minutes=2))
    got = lines(h)
    assert [x['date'] for x in got] == ['2026-10-28', '2026-10-29']
    assert [x['readiness_pct'] for x in got] == [100.0, 0.0]


def test_a_restart_on_the_same_day_writes_nothing(tmp_path):
    path = str(tmp_path / 'h.jsonl')
    now = datetime(2026, 10, 28, 8, 0, tzinfo=TZ)
    fleet.ReadinessHistory(path).record(csv_data([asset()]), fleet.FamilyMap(), now)
    restarted = fleet.ReadinessHistory(path)
    assert restarted.record(csv_data([asset()]), fleet.FamilyMap(), now + timedelta(hours=1)) is False
    assert len(lines(restarted)) == 1


def test_missing_file_and_folder_are_created(tmp_path):
    path = tmp_path / 'new' / 'folder' / 'h.jsonl'
    h = fleet.ReadinessHistory(str(path))
    h.record(csv_data([asset()]), fleet.FamilyMap(), datetime(2026, 10, 28, 8, 0, tzinfo=TZ))
    raw = path.read_bytes()
    assert raw.endswith(b'\n') and b'\r\n' not in raw
    assert len(lines(h)) == 1


def test_csv_export_from_an_earlier_day_is_recorded(tmp_path):
    h = fleet.ReadinessHistory(str(tmp_path / 'h.jsonl'))
    data = csv_data([asset()])  # exported January 2
    assert h.record(data, fleet.FamilyMap(), datetime(2026, 10, 28, 8, 0, tzinfo=TZ)) is True


def sharepoint_data(loaded_at, stale=None):
    return {'fields': {}, 'assets': [asset()], 'source': 'SharePoint: Asset Tracking V2',
            'live': True, 'loaded_at': loaded_at, 'stale': stale}


def test_stale_or_earlier_day_sharepoint_copy_writes_nothing(tmp_path):
    h = fleet.ReadinessHistory(str(tmp_path / 'h.jsonl'))
    now = datetime(2026, 10, 28, 0, 10, tzinfo=TZ)
    yesterday = datetime(2026, 10, 27, 23, 58, tzinfo=TZ)
    stale = {'since': now - timedelta(minutes=5), 'failed_at': now, 'reason': 'x'}
    assert h.record(sharepoint_data(now - timedelta(minutes=5), stale), fleet.FamilyMap(), now) is False
    assert h.record(sharepoint_data(yesterday), fleet.FamilyMap(), now) is False
    assert not os.path.exists(h.path)
    # The fresh fetch of the day is recorded.
    assert h.record(sharepoint_data(now), fleet.FamilyMap(), now) is True


def test_a_failed_load_records_nothing(history, monkeypatch):
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.UnavailableSource('Broken for the test.'))
    assert dashboard.app.test_client().get('/overview').status_code == 503
    assert not os.path.exists(history.path)


def test_failed_write_keeps_the_page_up_with_a_note(tmp_path, monkeypatch, caplog):
    # A folder where the file should be: opening it to append fails.
    blocked = tmp_path / 'readiness_history.jsonl'
    blocked.mkdir()
    monkeypatch.setattr(dashboard, 'HISTORY', fleet.ReadinessHistory(str(blocked)))
    client = dashboard.app.test_client()
    with caplog.at_level(logging.INFO):
        resp = client.get('/overview')
        client.get('/')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Today's readiness could not be saved to the trend history" in html
    logged = [r for r in caplog.records if 'could not be written' in r.getMessage()]
    assert len(logged) == 1 and str(blocked) in logged[0].getMessage()


def test_overview_records_with_the_csv_source(history):
    client = dashboard.app.test_client()
    client.get('/overview')
    client.get('/')
    got = lines(history)
    assert len(got) == 1
    assert got[0]['source'] == 'Asset Tracking V2.csv' and got[0]['total'] == 146
    assert got[0]['date'] == datetime.now(TZ).date().isoformat()


@pytest.fixture
def sharepoint_app(pfx, monkeypatch):
    fake = FakeSharePoint([
        make_item(1, 'SN-FAKE-001'),
        make_item(2, 'SN-FAKE-002', condition='NMC', location=['Test Bay A', 'Test Bay B']),
        make_item(3, 'SN-FAKE-003', asset_type='SGCS 1', condition='PMC', location=[]),
        make_item(4, 'SN-FAKE-004', asset_type='Field Support Kit', condition='Destroyed/Lost'),
    ])
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=lambda s: None)
    source = sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                         clock=FakeClock(), background=False)
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    return dashboard.app.test_client(), fake


def test_overview_with_the_sharepoint_source(sharepoint_app, history):
    client, _ = sharepoint_app
    resp = client.get('/overview')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'SN-FAKE-001' in html and ', fetched ' in html
    got = lines(history)
    assert len(got) == 1 and got[0]['source'] == 'SharePoint: Asset Tracking V2'
    assert (got[0]['total'], got[0]['fmc'], got[0]['nmc'], got[0]['pmc']) == (4, 1, 1, 1)
    assert got[0]['readiness_pct'] == round(100 / 3, 1)
    assert got[0]['families']['Aircraft']['readiness_pct'] == 50.0
    assert got[0]['families']['Support']['destroyed_lost'] == 1


def test_overview_stale_sharepoint_copy_is_not_recorded(sharepoint_app, history):
    client, fake = sharepoint_app
    dashboard.SOURCE.load()  # first good copy, recorded through no page
    fake.fail_status = 503
    dashboard.SOURCE.clock.advance(301)
    dashboard.SOURCE.load()  # the refresh fails: the copy is now stale
    resp = client.get('/overview')
    assert resp.status_code == 200
    assert 'SharePoint could not be reached; showing the last copy' in resp.get_data(as_text=True)
    assert not os.path.exists(history.path)


def test_overview_location_filter_through_the_page(sharepoint_app, history):
    client, _ = sharepoint_app
    html = client.get('/overview?location=Test+Bay+B').get_data(as_text=True)
    assert 'SN-FAKE-002' in html and 'SN-FAKE-001' not in html
    html = client.get('/overview?location=Test+Bay+A').get_data(as_text=True)
    assert 'SN-FAKE-001' in html and 'SN-FAKE-002' in html and 'SN-FAKE-003' not in html
    html = client.get('/overview?location=' + fleet.NO_LOCATION).get_data(as_text=True)
    assert 'SN-FAKE-003' in html and 'SN-FAKE-001' not in html
    assert '<option value="(none)" selected>No location</option>' in html
    # The history is fleet-wide whatever the filter.
    assert lines(history)[0]['total'] == 4


# --- The trend ----------------------------------------------------------------

def test_trend_has_seven_dates_with_gaps():
    today = datetime(2026, 10, 28).date()
    entries = [
        {'date': '2026-10-22', 'readiness_pct': 80.0,
         'families': {'Aircraft': {'readiness_pct': 90.0}}},
        {'date': '2026-10-28', 'readiness_pct': 83.3,
         'families': {'Aircraft': {'readiness_pct': None}}},
        {'date': '2026-10-01', 'readiness_pct': 10.0, 'families': {}},
    ]
    t = fleet.trend(entries, today)
    assert t['labels'] == ['10/22', '10/23', '10/24', '10/25', '10/26', '10/27', '10/28']
    assert t['points'] == 2
    assert t['series']['Overall'] == [80.0, None, None, None, None, None, 83.3]
    assert t['series']['Aircraft'] == [90.0, None, None, None, None, None, None]
    assert list(t['series']) == ['Overall', 'Aircraft', 'Ground Control Station', 'Payload']


def test_trend_with_one_point_says_how_it_fills_in(history):
    html = dashboard.app.test_client().get('/overview').get_data(as_text=True)
    assert 'The trend fills in one point per day' in html
    assert 'the Location filter does not change this chart' in html


def test_bad_history_lines_are_skipped(tmp_path, caplog):
    path = tmp_path / 'h.jsonl'
    path.write_text('{"date": "2026-10-27", "readiness_pct": 50}\nnot json\n\n',
                    encoding='utf-8')
    h = fleet.ReadinessHistory(str(path))
    with caplog.at_level(logging.INFO):
        assert [e['date'] for e in h.entries()] == ['2026-10-27']
        h.entries()
    assert len([r for r in caplog.records if 'could not be read' in r.getMessage()]) == 1


# --- The page -----------------------------------------------------------------

def test_overview_is_first_in_the_nav_and_has_the_left_nav(history):
    assert dashboard.PAGES[0] == ('overview', '/overview', 'Fleet Overview')
    assert dashboard.PAGES[1][1] == '/'
    html = dashboard.app.test_client().get('/overview').get_data(as_text=True)
    assert 'class="side-nav"' in html and 'class="header-bar"' not in html
    assert 'id="theme-toggle"' in html
    other = dashboard.app.test_client().get('/').get_data(as_text=True)
    assert 'class="header-bar"' in other and 'class="side-nav"' not in other


def test_overview_numbers_for_the_committed_export(history):
    html = dashboard.app.test_client().get('/overview').get_data(as_text=True)
    assert 'id="readiness-pct">83%' in html
    assert 'Ground Control Stations' in html and 'Payloads' in html


def test_overview_unavailable_source_gives_503(monkeypatch):
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.UnavailableSource('Broken for the test.'))
    resp = dashboard.app.test_client().get('/overview')
    assert resp.status_code == 503
    assert 'Broken for the test.' in resp.get_data(as_text=True)
