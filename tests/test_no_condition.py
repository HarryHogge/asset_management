"""The US "No condition" rule (prompt 12): Material Condition is blank."""
import re

import pytest

import app as dashboard
import assets as asset_data
import fleet
import sharepoint
from fake_sharepoint import FakeClock, FakeSharePoint, FakeTokens, fake_env, make_item
from test_fleet import alert_card, asset


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, 'HISTORY',
                        fleet.ReadinessHistory(str(tmp_path / 'readiness_history.jsonl')))


def rule(key):
    return next(r for r in asset_data.attention_rules(90) if r[0] == key)


def test_fires_on_blank_and_not_on_an_unknown_value():
    _, title, why, test = rule('no_condition')
    assert title == 'No condition' and why == 'Material Condition is blank.'
    assert test(asset(condition=''), None)
    assert not test(asset(condition='Awaiting Parts'), None)
    for value in ('FMC', 'PMC', 'NMC', 'Destroyed/Lost'):
        assert not test(asset(condition=value), None)


def test_sits_after_no_status():
    keys = [r[0] for r in asset_data.attention_rules(90)]
    assert keys == ['out_no_holder', 'out_no_date', 'holder_not_out', 'no_status',
                    'no_condition', 'never_inventoried', 'inventory_overdue', 'degraded_no_notes']


def test_committed_export_has_none(history):
    client = dashboard.app.test_client()
    card = alert_card(client.get('/').get_data(as_text=True))
    row = [c for c in card if c[0] == 'no_condition']
    assert row == [('no_condition', '/attention#no_condition', 0, True)]
    # Zero rows come last, so it is below every rule with a count.
    first_zero = min(i for i, c in enumerate(card) if c[2] == 0)
    assert card.index(row[0]) >= first_zero
    html = client.get('/attention').get_data(as_text=True)
    assert 'id="no_condition"' in html and 'Material Condition is blank.' in html


def test_with_a_csv_export(tmp_path, monkeypatch, history):
    path = tmp_path / 'made_up.csv'
    path.write_text(
        'Asset Type,Serial Number,Status,Location,Material Condition,Last Inventory\n'
        'VXE-30,SN-BLANK-1,"[""IN""]","[""Test Bay A""]",,2026-10-01T07:00:00Z\n'
        'VXE-30,SN-ODD-1,"[""IN""]","[""Test Bay A""]",Awaiting Parts,2026-10-01T07:00:00Z\n'
        'VXE-30,SN-FINE-1,"[""IN""]","[""Test Bay A""]",FMC,2026-10-01T07:00:00Z\n',
        encoding='utf-8')
    monkeypatch.setattr(dashboard, 'SOURCE', dashboard.CsvSource(str(path), 'America/Los_Angeles'))
    client = dashboard.app.test_client()
    groups = {g['key']: [a['serial_number'] for a in g['assets']]
              for g in client.get('/api/attention').get_json()}
    assert groups['no_condition'] == ['SN-BLANK-1']
    card = {k: n for k, _, n, _ in alert_card(client.get('/').get_data(as_text=True))}
    assert card['no_condition'] == 1
    html = client.get('/attention').get_data(as_text=True)
    section = html.split('id="no_condition"')[1].split('id="never_inventoried"')[0]
    assert 'SN-BLANK-1' in section and 'SN-ODD-1' not in section


def test_with_the_sharepoint_source(pfx, monkeypatch, history):
    fake = FakeSharePoint([
        make_item(1, 'SN-FAKE-001'),
        make_item(2, 'SN-FAKE-BLANK', condition=''),
        make_item(3, 'SN-FAKE-ODD', condition='Awaiting Parts'),
    ])
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=lambda s: None)
    source = sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                         clock=FakeClock(), background=False)
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    web = dashboard.app.test_client()
    groups = {g['key']: [a['serial_number'] for a in g['assets']]
              for g in web.get('/api/attention').get_json()}
    assert groups['no_condition'] == ['SN-FAKE-BLANK']
    card = {k: n for k, _, n, _ in alert_card(web.get('/').get_data(as_text=True))}
    assert card['no_condition'] == 1
    assert re.search(r'id="no_condition"[\s\S]*SN-FAKE-BLANK', web.get('/attention').get_data(as_text=True))
