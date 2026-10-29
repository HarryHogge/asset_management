"""The Riga tab: the Excel loader, the check command, the upload page, the
site switch on the overview, engines, per-site history and Riga's alerts.
Every workbook here is made up by riga_fixture.py."""
import io
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import fleet
import riga_fixture
import riga_loader

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIGA_TZ = ZoneInfo(riga_loader.RIGA_TIMEZONE)
US_TZ = ZoneInfo('America/Los_Angeles')


@pytest.fixture(scope='session')
def workbook(tmp_path_factory):
    return riga_fixture.build(str(tmp_path_factory.mktemp('riga') / 'riga_assets.xlsx'))


@pytest.fixture(scope='session')
def workbook_bytes(workbook):
    with open(workbook, 'rb') as f:
        return f.read()


@pytest.fixture(scope='session')
def result(workbook):
    return riga_loader.read_workbook(workbook, riga_loader.read_mapping())


def rows_by_serial(result):
    return {r['serial_number']: r for r in result['rows']}


@pytest.fixture
def riga(tmp_path, monkeypatch):
    """An empty Riga folder for the app, in a temporary folder."""
    folder = tmp_path / 'riga'
    folder.mkdir()
    source = riga_loader.RigaSource(str(folder / 'current.xlsx'))
    monkeypatch.setattr(dashboard, 'RIGA', source)
    monkeypatch.setattr(dashboard, '_riga_logged', {'mismatches': ()})
    return source


@pytest.fixture
def history(tmp_path, monkeypatch):
    h = fleet.ReadinessHistory(str(tmp_path / 'history' / 'readiness_history.jsonl'))
    monkeypatch.setattr(dashboard, 'HISTORY', h)
    return h


def lines(h):
    if not os.path.exists(h.path):
        return []
    with open(h.path, encoding='utf-8') as f:
        return [json.loads(x) for x in f.read().splitlines()]


def upload(client, content, filename='riga_assets.xlsx', name='Test Person'):
    return client.post('/riga/upload', data={'workbook': (io.BytesIO(content), filename),
                                             'name': name},
                       content_type='multipart/form-data')


@pytest.fixture
def uploaded(riga, workbook_bytes):
    """The Riga folder with the fixture uploaded through the page."""
    resp = upload(dashboard.app.test_client(), workbook_bytes)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return riga


# --- The mapping file ---------------------------------------------------------

def test_committed_mapping_is_valid_and_matches_report_10():
    m = riga_loader.read_mapping()
    assert [s['sheet'] for s in m['sheets']] == ['Mk2.x', 'MK2', '2.5 VTOL', 'MK3', 'VXE', 'EPS',
                                                 'TRC', 'PPC', 'GCS', 'ENG']
    assert m['ignored_sheets'] == ['VEHICLES', 'ZALENIEKI STOCK', 'OVERALL']
    assert m['conditions'] == {'RTF': 'FMC', 'RTF WITH REMARKS': 'PMC', 'FCF REQUIRED': 'PMC',
                               'GROUNDED': 'NMC', 'WRITTEN OFF': 'Destroyed/Lost'}
    sheets = {s['sheet']: s for s in m['sheets']}
    assert sheets['PPC']['header_row'] == 2
    assert all(s['header_row'] == 3 for n, s in sheets.items() if n != 'PPC')
    assert sheets['GCS']['columns']['date'] is None
    assert (sheets['EPS']['columns']['condition'], sheets['GCS']['columns']['condition']) == \
        ('STATUS', 'STATUS')
    assert sheets['VXE']['columns']['notes'] == 'NOTES'
    assert sheets['PPC']['columns']['notes'] == 'INFO'
    assert sheets['GCS']['columns']['notes'] == 'INFO:'
    assert sheets['Mk2.x']['columns']['owner'] == 'Asset owner'
    assert sheets['TRC']['columns']['owner'] == 'Asset Owner'
    # Each sheet's family agrees with asset_families.json.
    _, mismatches = riga_loader.cross_check(fleet.read_families(fleet.ASSET_FAMILIES_PATH), m)
    assert mismatches == []


@pytest.mark.parametrize('change, reason', [
    (lambda m: m.pop('sheets'), 'no "sheets"'),
    (lambda m: m['sheets'][0].update(family='Drone'), 'not one of'),
    (lambda m: m['sheets'][0].update(header_row=0), 'header_row'),
    (lambda m: m['sheets'][0]['columns'].pop('date'), 'exactly'),
    (lambda m: m['sheets'][0]['columns'].update(serial=None), 'no header text for serial'),
    (lambda m: m['sheets'].append(dict(m['sheets'][0])), 'twice'),
    (lambda m: m['conditions'].update(BROKEN='Fine'), 'not one of'),
    (lambda m: m.update(date_formats=['mm/dd/yyyy']), 'date format'),
    (lambda m: m['ignored_sheets'].append('MK2'), 'both mapped and ignored'),
])
def test_badly_shaped_mapping_is_refused(tmp_path, change, reason):
    m = riga_loader.read_mapping()
    change(m)
    path = tmp_path / 'riga_mapping.json'
    path.write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(ValueError, match=reason):
        riga_loader.read_mapping(str(path))
    state = riga_loader.RigaSource(str(tmp_path / 'current.xlsx'), str(path)).load()
    assert state['state'] == 'mapping' and reason.split()[0] in state['problem']


def test_mapping_that_is_not_json_or_missing(tmp_path):
    path = tmp_path / 'riga_mapping.json'
    path.write_text('{"sheets": [', encoding='utf-8')
    assert 'not valid JSON' in riga_loader.RigaSource('x.xlsx', str(path)).load()['problem']
    missing = riga_loader.RigaSource('x.xlsx', str(tmp_path / 'nope.json')).load()
    assert missing['state'] == 'mapping' and 'there is no nope.json' in missing['problem']


# --- The loader ---------------------------------------------------------------

def test_rows_per_sheet(result):
    assert {n: s['rows'] for n, s in result['sheets'].items()} == riga_fixture.ROWS_PER_SHEET
    assert [r['serial_number'] for r in result['rows']] == riga_fixture.SERIALS


def test_titles_legends_and_side_tables_are_ignored(result):
    serials = {r['serial_number'] for r in result['rows']}
    # Nothing from row 1 or 2, the upgrade matrix, the part list, TRC's
    # count table or ENG's marker columns.
    for text in ('PNC Mk2', 'FLIGHT READY', 'Upgrade', 'Wing', 'Spare part 21', 'RTF', 'X'):
        assert text not in serials
    assert result['sheets']['2.5 VTOL']['rows'] == 1
    assert result['sheets']['TRC']['rows'] == 3


def test_sheets_mapped_ignored_and_unknown(result):
    assert result['ignored'] == ['VEHICLES', 'ZALENIEKI STOCK', 'OVERALL']
    assert result['unknown'] == ['Notes 2026']
    assert result['missing'] == []
    assert len(result['mapped']) == 10
    found = riga_loader.findings(result)
    assert 'Sheet Notes 2026 is not in riga_mapping.json and was skipped.' in found


def test_a_mapped_sheet_missing_from_the_workbook_is_listed(tmp_path):
    path = riga_fixture.build(str(tmp_path / 'w.xlsx'))
    from openpyxl import load_workbook
    wb = load_workbook(path)
    del wb['PPC']
    wb.save(path)
    result = riga_loader.read_workbook(path, riga_loader.read_mapping())
    assert result['missing'] == ['PPC']
    assert 'Sheet PPC is in riga_mapping.json but not in the workbook.' in riga_loader.findings(result)


def test_dates(result):
    rows = rows_by_serial(result)
    assert rows['TST-MK2X-0001']['last_inventory'] == date(2026, 10, 1)   # Excel date
    assert rows['TST-MK2-0001']['last_inventory'] == date(2026, 3, 15)    # dd.mm.yyyy text
    assert rows['TST-TRC-0002']['last_inventory'] == date(2026, 10, 5)    # dd.mm.yy text
    assert rows['TST-VTOL-0001']['last_inventory'] is None                # cannot be read
    assert rows['TST-TRC-0003']['last_inventory'] is None                 # blank
    assert rows['TST-GCS-0001']['last_inventory'] is None                 # no date column
    assert {n: s['bad_dates'] for n, s in result['sheets'].items() if s['bad_dates']} == \
        {'2.5 VTOL': 1}
    # A date written inside the notes stays in the notes.
    assert rows['TST-MK2X-0001']['notes'].startswith('01.10.2026: ')
    assert result['dated_types'] == {s['asset_type'] for n, s in result['sheets'].items()
                                     if n != 'GCS'}


def test_day_first_is_never_read_month_first():
    assert riga_loader._parse_date('06.03.2026', ['dd.mm.yyyy']) == (date(2026, 3, 6), False)
    assert riga_loader._parse_date('6.3.2026', ['dd.mm.yyyy']) == (date(2026, 3, 6), False)
    assert riga_loader._parse_date('2026-03-06', ['dd.mm.yyyy', 'dd.mm.yy']) == (None, True)
    assert riga_loader._parse_date(45000, ['dd.mm.yyyy']) == (None, True)
    assert riga_loader._parse_date('  ', ['dd.mm.yyyy']) == (None, False)


def test_numeric_serial_and_header_case(result):
    rows = rows_by_serial(result)
    # VXE's serial is stored as a number; it reads without a decimal point.
    assert rows['4417']['asset_type'] == 'VXE (Riga)'
    # VXE's header is STATUS; the mapping says Status.
    assert rows['4417']['condition'] == 'FMC'
    assert result['sheets']['VXE']['missing_headers'] == []


def test_conditions_and_the_unknown_value(result):
    rows = rows_by_serial(result)
    assert rows['TST-MK3-0002']['condition'] == 'PMC'        # FCF REQUIRED
    assert rows['TST-VTOL-0001']['condition'] == 'PMC'       # RTF WITH REMARKS
    assert rows['TST-ENG-0005']['condition'] == 'Destroyed/Lost'
    assert rows['TST-EPS-0001']['condition'] == ''           # NFC ISSUES
    assert result['unknown_conditions'] == {'NFC ISSUES': 1}


def test_formula_error_in_a_mapped_column(result):
    rows = rows_by_serial(result)
    assert rows['TST-MK3-0002']['location'] == []
    assert result['sheets']['MK3']['formula_errors'] == 1
    # The Equip. Rediness #REF! on Mk2.x is not in a mapped column.
    assert result['sheets']['Mk2.x']['formula_errors'] == 0


def test_missing_header_leaves_the_field_blank_and_is_listed(result):
    assert result['sheets']['MK2']['missing_headers'] == [('owner', 'Asset owner')]
    assert rows_by_serial(result)['TST-MK2-0001']['ownership'] == ''
    assert 'Sheet MK2 has no column headed "Asset owner", so its owner is blank.' in \
        riga_loader.findings(result)


def test_row_shape_matches_us_rows_plus_site(result):
    us = dashboard.CsvSource(dashboard.ASSET_CSV, 'America/Los_Angeles').load()['assets'][0]
    for row in result['rows']:
        assert set(row) == set(us)
        for key in us:
            if us[key] is not None and row[key] is not None:
                assert type(row[key]) is type(us[key]), key
        assert row['site'] == 'Riga'
        assert row['status'] == [] and row['checked_out_to'] == '' and row['date_out'] is None
        assert row['part_number'] == '' and row['shelf_location'] == ''
    assert us['site'] == 'US'
    row = rows_by_serial(result)['TST-MK2X-0001']
    assert (row['location'], row['ownership']) == (['MRO'], 'FOPS')


def test_ids_never_collide_and_stay_the_same(result, workbook):
    ids = [r['id'] for r in result['rows']]
    assert len(set(ids)) == len(ids)
    assert all(isinstance(i, int) and i < 0 for i in ids)
    us_ids = {a['id'] for a in dashboard.CsvSource(dashboard.ASSET_CSV,
                                                   'America/Los_Angeles').load()['assets']}
    assert not us_ids & set(ids)
    again = riga_loader.read_workbook(workbook, riga_loader.read_mapping())
    assert [r['id'] for r in again['rows']] == ids
    # Sheet 1 (Mk2.x), Excel row 4.
    assert rows_by_serial(result)['TST-MK2X-0001']['id'] == -(1 * 10000000 + 4)


def test_a_file_that_is_not_a_workbook(tmp_path):
    path = tmp_path / 'fake.xlsx'
    path.write_bytes(b'not a workbook')
    with pytest.raises(riga_loader.WorkbookError, match='could not be opened'):
        riga_loader.read_workbook(str(path), riga_loader.read_mapping())


def test_family_mismatch_makes_those_rows_unmapped(result):
    families = fleet.read_families(fleet.ASSET_FAMILIES_PATH)
    families['Catapult'] = 'Payload'
    del families['Epsilon Gimbal']
    use, mismatches = riga_loader.cross_check(families, riga_loader.read_mapping())
    assert [(m[0], m[3]) for m in mismatches] == [('EPS', None), ('PPC', 'Payload')]
    assert 'Catapult' not in use and 'Epsilon Gimbal' not in use
    ready = fleet.fleet_readiness(result['rows'], use)
    assert ready['families']['Unmapped']['total'] == 2
    assert ready['families']['Payload']['total'] == 0
    assert 'riga_mapping.json says Support but asset_families.json says Payload' in \
        riga_loader.mismatch_text(mismatches[1])


def test_family_mismatch_on_the_page_and_in_the_log(tmp_path, monkeypatch, uploaded, history,
                                                    caplog):
    families = fleet.read_families(fleet.ASSET_FAMILIES_PATH)
    families['Catapult'] = 'Payload'
    path = tmp_path / 'asset_families.json'
    path.write_text(json.dumps(families), encoding='utf-8')
    monkeypatch.setattr(dashboard, 'FAMILIES', fleet.FamilyMap(str(path)))
    with caplog.at_level(logging.WARNING):
        html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
        dashboard.app.test_client().get('/?site=riga')
    assert 'Sheet PPC (Catapult): riga_mapping.json says Support' in html
    assert 'Catapult: 1' in html  # listed under Unmapped
    logged = [r for r in caplog.records if 'Sheet PPC (Catapult)' in r.getMessage()]
    assert len(logged) == 1


# --- The check command --------------------------------------------------------

def run_check(path):
    out = io.StringIO()
    code = riga_loader.check(path, out=out)
    return code, out.getvalue()


def test_check_command_sections(workbook):
    code, text = run_check(workbook)
    assert code == 0
    for heading in ('1. Sheets', '2. Rows read per sheet', '3. Mapped headers not found',
                    '4. Unknown Status values', '5. Dates that could not be read',
                    '6. First 3 rows of each sheet', '7. Totals per family'):
        assert heading in text
    assert 'Unknown, skipped (1): Notes 2026' in text
    assert 'Ignored (3): VEHICLES, ZALENIEKI STOCK, OVERALL' in text
    assert 'ENG (Engine, Engine): 5' in text
    assert 'MK2: "Asset owner" (owner)' in text
    assert '"NFC ISSUES": 1 row(s)' in text
    assert '2.5 VTOL: 1 date(s) not read, 0 formula error(s)' in text
    assert 'MK3: 0 date(s) not read, 1 formula error(s)' in text
    assert 'Engine: 5 (Ready 2, Limited 0, Not Ready 2, No condition 0, Destroyed/Lost 1)' in text
    assert 'Headline readiness, engines left out: 58%' in text


def test_check_command_output_is_safe_to_paste(workbook):
    _, text = run_check(workbook)
    assert 'serial TST***' in text and 'serial 44***' in text
    for serial in riga_fixture.SERIALS:
        assert serial not in text
    assert riga_fixture.SECRET_NOTE not in text and 'Minor wear' not in text
    assert riga_fixture.SIGN not in text
    assert 'XX-0000' not in text and 'PN-TEST' not in text
    assert 'notes 33 characters' in text


def test_mask_never_shows_a_short_serial_whole():
    assert riga_loader.mask('TST-ENG-0001') == 'TST***'
    assert riga_loader.mask('4417') == '44***'
    assert riga_loader.mask('AB') == 'A***'
    assert riga_loader.mask('A') == '***'


def test_check_command_on_a_bad_file(tmp_path):
    path = tmp_path / 'fake.xlsx'
    path.write_bytes(b'not a workbook')
    code, text = run_check(str(path))
    assert code == 1 and 'FAILED' in text


def test_check_command_runs_alone_without_settings(workbook):
    """As Scott runs it: python -m riga_loader --check PATH, with no
    dashboard and no SharePoint settings."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('SP_') and k not in ('ASSET_SOURCE', 'RIGA_WORKBOOK_PATH')}
    proc = subprocess.run([sys.executable, '-m', 'riga_loader', '--check', workbook], cwd=REPO,
                          env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert '7. Totals per family' in proc.stdout
    usage = subprocess.run([sys.executable, '-m', 'riga_loader'], cwd=REPO, env=env,
                           capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert usage.returncode == 2 and 'Usage' in usage.stderr


# --- Upload -------------------------------------------------------------------

def test_good_upload_with_backup_and_record(riga, workbook_bytes):
    client = dashboard.app.test_client()
    first = upload(client, workbook_bytes, name='  First Person  ')
    html = first.get_data(as_text=True)
    assert first.status_code == 200 and 'Uploaded riga_assets.xlsx: 17 Riga rows read' in html
    assert os.path.exists(riga.path)
    record = json.load(open(riga_loader.upload_info_path(riga.path), encoding='utf-8'))
    assert record['uploaded_by'] == 'First Person'
    assert record['original_filename'] == 'riga_assets.xlsx'
    assert record['rows_per_sheet'] == riga_fixture.ROWS_PER_SHEET
    assert datetime.fromisoformat(record['uploaded_at']).tzinfo is not None
    folder = os.path.dirname(riga.path)
    assert sorted(os.listdir(folder)) == ['current.upload.json', 'current.xlsx']

    second = upload(client, workbook_bytes, filename='second.xlsx', name='Second Person')
    assert second.status_code == 200
    names = sorted(os.listdir(folder))
    backups = [n for n in names if n.startswith('current-') and n.endswith('.xlsx')]
    assert len(backups) == 1 and len(backups[0]) == len('current-20261029-143012.xlsx')
    assert json.load(open(riga_loader.upload_info_path(riga.path),
                          encoding='utf-8'))['uploaded_by'] == 'Second Person'
    # No temporary files are left behind.
    assert not [n for n in names if n.startswith('.upload-')]


def test_backup_names_never_overwrite(tmp_path):
    path = str(tmp_path / 'current.xlsx')
    now = datetime(2026, 10, 29, 14, 30, 12, tzinfo=RIGA_TZ)
    first = riga_loader.backup_path(path, now)
    assert first.endswith('current-20261029-143012.xlsx')
    open(first, 'w').close()
    assert riga_loader.backup_path(path, now).endswith('current-20261029-143012-2.xlsx')


def previous_kept(riga, before):
    with open(riga.path, 'rb') as f:
        assert f.read() == before
    assert not [n for n in os.listdir(os.path.dirname(riga.path)) if n.startswith('.upload-')]


@pytest.mark.parametrize('kind, expected', [
    ('csv name', 'Only Excel workbooks ending in .xlsx'),
    ('not a workbook', 'could not be opened as an Excel workbook'),
    ('zero rows', 'holds no Riga assets'),
    ('blank name', 'Enter your name'),
    ('long name', 'at most 80 characters'),
    ('too large', 'larger than the'),
])
def test_rejected_uploads_keep_the_previous_file(uploaded, workbook_bytes, monkeypatch,
                                                 tmp_path, kind, expected):
    with open(uploaded.path, 'rb') as f:
        before = f.read()
    content, filename, name = workbook_bytes, 'riga.xlsx', 'Test Person'
    if kind == 'csv name':
        filename = 'riga.csv'
    elif kind == 'not a workbook':
        content = b'PK not really a zip'
    elif kind == 'zero rows':
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = 'Something else'
        buf = io.BytesIO()
        wb.save(buf)
        content = buf.getvalue()
    elif kind == 'blank name':
        name = '   '
    elif kind == 'long name':
        name = 'x' * 81
    elif kind == 'too large':
        monkeypatch.setattr(riga_loader, 'MAX_UPLOAD_BYTES', 1000)
    resp = upload(dashboard.app.test_client(), content, filename, name)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 400
    assert 'Not uploaded:' in html and expected in html
    assert 'The previous workbook is still in use.' in html
    previous_kept(uploaded, before)
    assert len([n for n in os.listdir(os.path.dirname(uploaded.path))
                if n.startswith('current-')]) == 0


def test_request_over_the_outer_limit_is_refused_on_the_page(riga, monkeypatch):
    monkeypatch.setitem(dashboard.app.config, 'MAX_CONTENT_LENGTH', 2000)
    resp = upload(dashboard.app.test_client(), b'x' * 5000)
    assert resp.status_code == 413
    assert 'larger than the 10 MB limit' in resp.get_data(as_text=True)
    assert not os.path.exists(riga.path)


def test_upload_page_and_folder_off(tmp_path, monkeypatch):
    blocker = tmp_path / 'a-file'
    blocker.write_text('x', encoding='utf-8')
    source = dashboard.make_riga({'RIGA_WORKBOOK_PATH': str(blocker / 'riga' / 'current.xlsx')})
    assert source.off_reason and str(blocker) in source.off_reason
    monkeypatch.setattr(dashboard, 'RIGA', source)
    client = dashboard.app.test_client()
    page = client.get('/riga/upload').get_data(as_text=True)
    assert 'uploads cannot be saved until the dashboard is restarted' in page
    assert 'No Riga workbook has been uploaded yet.' in page
    view = client.get('/?site=riga')
    assert view.status_code == 200
    assert 'the Riga view is off until the dashboard is restarted' in view.get_data(as_text=True)
    resp = upload(client, b'x')
    assert resp.status_code == 400 and 'could not be created' in resp.get_data(as_text=True)
    # The US view is not affected.
    assert client.get('/').status_code == 200


def test_workbook_path_setting(tmp_path):
    assert dashboard.riga_workbook_path({}) == os.path.join(dashboard.BASE_DIR, 'data', 'riga',
                                                            'current.xlsx')
    assert dashboard.riga_workbook_path({'RIGA_WORKBOOK_PATH': os.path.join('x', 'w.xlsx')}) == \
        os.path.join(dashboard.BASE_DIR, 'x', 'w.xlsx')
    absolute = str(tmp_path / 'w.xlsx')
    assert dashboard.riga_workbook_path({'RIGA_WORKBOOK_PATH': absolute}) == absolute
    made = dashboard.make_riga({'RIGA_WORKBOOK_PATH': str(tmp_path / 'new' / 'current.xlsx')})
    assert (tmp_path / 'new').is_dir() and made.off_reason is None


# --- Sites --------------------------------------------------------------------

def test_home_page_defaults_to_us(uploaded, history):
    html = dashboard.app.test_client().get('/').get_data(as_text=True)
    assert 'aria-current="page">US</a>' in html
    assert 'Overall Fleet Readiness' in html and 'id="readiness-pct">83%' in html
    assert 'TST-' not in html
    assert '<th>Checked out to</th>' in html


def test_riga_view_shows_riga_only(uploaded, history):
    html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
    assert 'aria-current="page">Riga</a>' in html
    assert 'Riga Fleet Readiness' in html
    assert 'id="readiness-pct">58%' in html          # 7 of 12, engines left out
    # Every Riga row, Support included: since prompt 12 Support has a table.
    for serial in riga_fixture.SERIALS:
        assert serial in html
    assert 'Support</span>\n            <span>4 assets' in html
    assert 'Asset Tracking V2.csv' not in html
    assert '<th>Checked out to</th>' not in html and '<th>Status</th>' not in html
    assert 'Uploaded by Test Person on ' in html
    assert 'Data from <strong>Riga workbook riga_assets.xlsx</strong>, uploaded' in html
    assert 'href="/riga/upload"' in html
    # The workbook's problems are listed, not hidden.
    assert 'Status &#34;NFC ISSUES&#34; on 1 row(s)' in html or 'Status "NFC ISSUES"' in html


def test_riga_view_with_no_workbook_is_not_an_error(riga, history):
    resp = dashboard.app.test_client().get('/?site=riga')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'No Riga workbook has been uploaded yet.' in html
    assert 'href="/riga/upload"' in html
    assert 'role="alert"' not in html.split('No Riga workbook')[0].split('site-switch')[-1]


def test_location_filter_within_a_site(uploaded, history):
    client = dashboard.app.test_client()
    html = client.get('/?site=riga&location=Field').get_data(as_text=True)
    # At Field: MK2 and ENG-0002 (plus Support rows, which have no table).
    assert 'TST-MK2-0001' in html and 'TST-ENG-0002' in html
    assert 'TST-MK2X-0001' not in html and 'TST-ENG-0001' not in html
    assert 'Showing 4 assets and 1 engine at <strong>Field</strong>' in html
    assert '<input type="hidden" name="site" value="riga">' in html
    assert '<option value="Nakotne"' in html and 'Test Bay' not in html
    assert '<a href="/?site=riga">Show all</a>' in html
    us = client.get('/').get_data(as_text=True)
    assert '<option value="Nakotne"' not in us


def test_overview_redirect_keeps_the_site(uploaded):
    resp = dashboard.app.test_client().get('/overview?site=riga&location=MRO')
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/?site=riga&location=MRO')


def test_us_pages_and_json_show_no_riga_rows(uploaded, history):
    client = dashboard.app.test_client()
    for path in ('/inventory', '/attention', '/checkouts', '/metrics', '/api/assets',
                 '/api/summary', '/api/attention', '/api/export/assets.xlsx'):
        resp = client.get(path)
        assert resp.status_code == 200, path
        body = resp.get_data()
        assert b'TST-' not in body and b'Penguin' not in body, path
    assets = client.get('/api/assets').get_json()['assets']
    assert len(assets) == 146 and 'site' not in assets[0]


def test_a_broken_riga_file_leaves_the_us_view_working(riga, history, caplog):
    with open(riga.path, 'wb') as f:
        f.write(b'this is not a workbook')
    client = dashboard.app.test_client()
    with caplog.at_level(logging.ERROR):
        us = client.get('/')
        view = client.get('/?site=riga')
        client.get('/?site=riga')
    assert us.status_code == 200 and 'id="readiness-pct">83%' in us.get_data(as_text=True)
    assert view.status_code == 200
    assert 'The Riga workbook could not be read' in view.get_data(as_text=True)
    assert len([r for r in caplog.records if 'Riga workbook' in r.getMessage()]) == 1
    assert [x['site'] for x in lines(history)] == ['US']


def test_a_broken_mapping_leaves_the_us_view_working(tmp_path, monkeypatch, uploaded, history):
    bad = tmp_path / 'riga_mapping.json'
    bad.write_text('[]', encoding='utf-8')
    monkeypatch.setattr(uploaded, 'mapping_path', str(bad))
    client = dashboard.app.test_client()
    assert client.get('/').status_code == 200
    html = client.get('/?site=riga').get_data(as_text=True)
    assert 'The Riga mapping file (riga_mapping.json) could not be read' in html


def test_a_broken_us_source_leaves_the_riga_view_working(uploaded, history, monkeypatch):
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.UnavailableSource('Broken for the test.'))
    client = dashboard.app.test_client()
    assert client.get('/').status_code == 503
    resp = client.get('/?site=riga')
    assert resp.status_code == 200 and 'TST-MK2X-0001' in resp.get_data(as_text=True)


# --- Engines ------------------------------------------------------------------

def test_engines_left_out_of_the_headline_and_cards(result):
    mapping = fleet.read_families(fleet.ASSET_FAMILIES_PATH)
    ready = fleet.fleet_readiness(result['rows'], mapping)
    assert ready['overall']['total'] == 12 and ready['overall']['pct'] == round(700 / 12, 1)
    engine = ready['families']['Engine']
    assert (engine['total'], engine['fmc'], engine['nmc'], engine['lost']) == (5, 2, 2, 1)
    assert 'Engine' not in fleet.MAIN_FAMILIES


def test_engine_table_on_the_riga_view(uploaded, history):
    html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
    engines = html.split('Engines <span')[1].split('</table>')[0]
    assert '2 Ready, 0 Limited, 2 Not Ready' in engines
    assert engines.count('TST-ENG-') == 5
    # The engine table comes after the three family tables.
    assert html.index('Engines <span') > html.index('Payloads <span')
    cards = html.split('class="grid-top"')[1].split('class="grid-top-2"')[0]
    assert 'Engine' not in cards
    assert '12 assets in all, engines not included' in html


def test_engines_stay_in_the_history_counts(uploaded, history):
    dashboard.app.test_client().get('/?site=riga')
    riga_line = [x for x in lines(history) if x['site'] == 'Riga'][0]
    assert riga_line['families']['Engine']['total'] == 5
    assert riga_line['total'] == 12 and riga_line['readiness_pct'] == round(700 / 12, 1)
    assert riga_line['source'] == 'Riga workbook riga_assets.xlsx'


# --- History ------------------------------------------------------------------

def test_one_line_per_site_per_day(uploaded, history):
    client = dashboard.app.test_client()
    client.get('/')
    client.get('/?site=riga')
    client.get('/')
    client.get('/inventory')
    got = lines(history)
    assert sorted(x['site'] for x in got) == ['Riga', 'US']
    riga_line = [x for x in got if x['site'] == 'Riga'][0]
    assert riga_line['date'] == datetime.now(RIGA_TZ).date().isoformat()


def test_riga_line_is_written_from_the_us_view_too(uploaded, history):
    dashboard.app.test_client().get('/')
    assert sorted(x['site'] for x in lines(history)) == ['Riga', 'US']


def test_no_riga_line_without_a_workbook(riga, history):
    client = dashboard.app.test_client()
    client.get('/')
    client.get('/?site=riga')
    assert [x['site'] for x in lines(history)] == ['US']


def test_old_lines_with_no_site_read_as_us(tmp_path):
    path = tmp_path / 'h.jsonl'
    path.write_text('{"date": "2026-10-28", "readiness_pct": 80.0}\n', encoding='utf-8')
    h = fleet.ReadinessHistory(str(path))
    assert [e['date'] for e in h.entries(fleet.US)] == ['2026-10-28']
    assert h.entries(fleet.RIGA) == []
    data = {'fields': {}, 'assets': [], 'source': 'x', 'live': False,
            'loaded_at': datetime(2026, 10, 28, 9, 0, tzinfo=US_TZ)}
    now = datetime(2026, 10, 28, 9, 0, tzinfo=US_TZ)
    # US already has its line for the day; Riga does not.
    assert h.record(data, fleet.FamilyMap(), now) is False
    assert h.record(data, None, now, site=fleet.RIGA, mapping={}) is True
    assert h.record(data, None, now, site=fleet.RIGA, mapping={}) is False
    restarted = fleet.ReadinessHistory(str(path))
    assert restarted.record(data, None, now, site=fleet.RIGA, mapping={}) is False
    assert len(h.entries()) == 2


def test_trend_per_site(uploaded, history):
    os.makedirs(os.path.dirname(history.path))
    with open(history.path, 'w', encoding='utf-8') as f:
        today = datetime.now(RIGA_TZ).date()
        f.write(json.dumps({'date': '2020-01-01', 'site': 'Riga', 'readiness_pct': 1.0}) + '\n')
        f.write(json.dumps({'date': today.isoformat(), 'site': 'US', 'readiness_pct': 11.0,
                            'families': {}}) + '\n')
    us_today = datetime.now(US_TZ).date()
    riga_trend = fleet.trend(history.entries(fleet.RIGA), today)
    us_trend = fleet.trend(history.entries(fleet.US), us_today)
    assert 11.0 not in riga_trend['series']['Overall']
    assert riga_trend['points'] == 0
    html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
    trend = json.loads(html.split('var trend = ')[1].split(';\n')[0])
    assert trend['series']['Overall'][-1] == round(700 / 12, 1)
    assert 11.0 not in trend['series']['Overall']
    assert 'All of Riga: the Location filter does not change this chart' in html
    assert us_trend['points'] >= 0


# --- Riga alerts --------------------------------------------------------------

def test_riga_alerts_are_only_the_four_rules(result):
    today = date(2026, 10, 29)
    groups = riga_loader.attention(result['rows'], today, 90, result['dated_types'])
    hits = {g['key']: sorted(a['serial_number'] for a in g['assets']) for g in groups}
    assert list(hits) == ['no_condition', 'never_inventoried', 'inventory_overdue',
                          'degraded_no_notes']
    assert hits['no_condition'] == ['TST-EPS-0001']
    # GCS has no date column, so it is never "never inventoried".
    assert hits['never_inventoried'] == ['TST-ENG-0004', 'TST-TRC-0003', 'TST-VTOL-0001']
    assert hits['inventory_overdue'] == ['TST-ENG-0005', 'TST-MK2-0001', 'TST-MK3-0001']
    assert hits['degraded_no_notes'] == ['TST-ENG-0004', 'TST-MK2-0001']


def test_riga_alert_card_has_counts_without_links(uploaded, history):
    html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
    card = html.split('Alerts <span')[1].split('Readiness Trend')[0]
    assert card.count('<div class="alert-row') == 4
    assert 'href="/attention' not in card
    assert 'The Needs Attention page covers US assets only' in card
    for key in ('no_condition', 'never_inventoried', 'inventory_overdue', 'degraded_no_notes'):
        assert 'data-rule="%s"' % key in card
    for key in ('out_no_holder', 'no_status', 'holder_not_out'):
        assert key not in card
    # Since prompt 12 the US has its own "No condition" rule, linked to
    # /attention like the other US rules.
    us = dashboard.app.test_client().get('/').get_data(as_text=True)
    assert 'href="/attention#no_condition" data-rule="no_condition"' in us


# --- Prompt 12: the Riga Support table ------------------------------------------

def table_after(html, heading):
    """The HTML of the table whose heading starts with `heading`."""
    return html.split(heading + ' <span')[1].split('</table>')[0]


def test_riga_support_table_below_engines(uploaded, history):
    html = dashboard.app.test_client().get('/?site=riga').get_data(as_text=True)
    assert html.index('Support <span') > html.index('Engines <span')
    support = table_after(html, 'Support')
    assert '3 Ready, 0 Limited, 1 Not Ready' in support
    assert html.split('Support <span class="count-badge ')[1].startswith('">4</span>')
    headers = [h for h in support.split('<th>')[1:]]
    assert [h.split('</th>')[0] for h in headers] == ['Serial Number', 'Asset Type', 'Location',
                                                      'Condition', 'Notes']
    # Not Ready first, then by Asset Type and serial: Catapult before Tracking Antenna.
    order = ['TST-TRC-0003', 'TST-PPC-0001', 'TST-TRC-0001', 'TST-TRC-0002']
    positions = [support.index(s) for s in order]
    assert positions == sorted(positions)
    assert 'TST-ENG-' not in support and 'TST-MK' not in support


def test_riga_support_table_follows_the_location_filter(uploaded, history):
    html = dashboard.app.test_client().get('/?site=riga&location=Field').get_data(as_text=True)
    support = table_after(html, 'Support')
    assert 'TST-PPC-0001' in support and 'TST-TRC-0001' in support and 'TST-TRC-0002' in support
    assert 'TST-TRC-0003' not in support
    assert '3 Ready, 0 Limited, 0 Not Ready' in support


def test_us_view_has_no_support_table(uploaded, history):
    html = dashboard.app.test_client().get('/').get_data(as_text=True)
    assert 'Support <span' not in html and 'Engines <span' not in html


# --- Prompt 12: keeping the 20 most recent backups ------------------------------

def make_backups(folder, n, stem='current'):
    """n backups named for days in 2025, with modified times in the opposite
    order, so a sort by modified time would pick the wrong ones."""
    names = []
    for i in range(n):
        name = '%s-202501%02d-120000.xlsx' % (stem, i + 1)
        path = os.path.join(folder, name)
        with open(path, 'wb') as f:
            f.write(b'old')
        os.utime(path, (2000000000 - i * 1000, 2000000000 - i * 1000))
        names.append(name)
    return names


def test_backup_order_and_pattern(tmp_path):
    for name in ('current-20260101-120000.xlsx', 'current-20260101-120000-2.xlsx',
                 'current-20260101-120000-10.xlsx', 'current-20251231-235959.xlsx',
                 'current.xlsx', 'current.upload.json', '.upload-abc.part.xlsx',
                 'current-2026-01-01.xlsx', 'current-20260101-120000.xlsx.bak',
                 'other-20270101-120000.xlsx', 'notes.txt'):
        (tmp_path / name).write_bytes(b'x')
    got = [os.path.basename(p) for p in riga_loader.backups(str(tmp_path / 'current.xlsx'))]
    assert got == ['current-20260101-120000-10.xlsx', 'current-20260101-120000-2.xlsx',
                   'current-20260101-120000.xlsx', 'current-20251231-235959.xlsx']
    # The workbook's own name decides the pattern, not a fixed "current".
    assert riga_loader.backups(str(tmp_path / 'riga.xlsx')) == []
    other = [os.path.basename(p) for p in riga_loader.backups(str(tmp_path / 'other.xlsx'))]
    assert other == ['other-20270101-120000.xlsx']


def test_upload_keeps_the_20_newest_backups_and_nothing_else(uploaded, workbook_bytes):
    folder = os.path.dirname(uploaded.path)
    names = make_backups(folder, 25)
    for extra in ('.upload-left.part.xlsx', 'notes.txt', 'current-20250101-120000.xlsx.bak'):
        with open(os.path.join(folder, extra), 'wb') as f:
            f.write(b'keep me')
    resp = upload(dashboard.app.test_client(), workbook_bytes, name='Pruner')
    assert resp.status_code == 200
    assert 'could not be removed' not in resp.get_data(as_text=True)
    left = riga_loader.backups(uploaded.path)
    assert len(left) == 20
    kept = {os.path.basename(p) for p in left}
    # The new backup (made today) and the 19 newest 2025 names.
    assert set(names[-19:]) <= kept and not set(names[:6]) & kept
    present = set(os.listdir(folder))
    assert {'current.xlsx', 'current.upload.json', '.upload-left.part.xlsx', 'notes.txt',
            'current-20250101-120000.xlsx.bak'} <= present
    assert json.load(open(riga_loader.upload_info_path(uploaded.path),
                          encoding='utf-8'))['uploaded_by'] == 'Pruner'


def test_a_rejected_upload_deletes_nothing(uploaded):
    folder = os.path.dirname(uploaded.path)
    make_backups(folder, 25)
    before = sorted(os.listdir(folder))
    resp = upload(dashboard.app.test_client(), b'not a workbook')
    assert resp.status_code == 400
    assert sorted(os.listdir(folder)) == before


def test_a_failed_delete_still_counts_as_uploaded(uploaded, workbook_bytes, monkeypatch, caplog):
    folder = os.path.dirname(uploaded.path)
    make_backups(folder, 22)
    stuck = 'current-20250101-120000.xlsx'
    real_remove = os.remove

    def remove(path):
        if os.path.basename(path) == stuck:
            raise PermissionError('in use')
        real_remove(path)
    monkeypatch.setattr(riga_loader.os, 'remove', remove)
    with caplog.at_level(logging.ERROR):
        resp = upload(dashboard.app.test_client(), workbook_bytes, name='Stuck')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200 and 'Uploaded riga_assets.xlsx' in html
    assert 'An old backup could not be removed; the next upload tries again.' in html
    logged = [r.getMessage() for r in caplog.records if 'could not be removed' in r.getMessage()]
    assert len(logged) == 1 and stuck in logged[0] and 'PermissionError' in logged[0]
    assert os.path.exists(os.path.join(folder, stuck))
    # 23 backups: 20 kept, 2 deleted, 1 stuck. The next upload tries again.
    assert len(riga_loader.backups(uploaded.path)) == 21
    monkeypatch.setattr(riga_loader.os, 'remove', real_remove)
    assert upload(dashboard.app.test_client(), workbook_bytes).status_code == 200
    assert len(riga_loader.backups(uploaded.path)) == 20
    assert not os.path.exists(os.path.join(folder, stuck))
