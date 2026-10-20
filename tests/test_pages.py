import io

import pytest
from openpyxl import load_workbook

import app as dashboard
import sharepoint
from fake_sharepoint import FakeClock, FakeSharePoint, FakeTokens, fake_env, make_item

PAGES = ['/', '/attention', '/checkouts', '/metrics', '/api/summary', '/api/assets',
         '/api/attention', '/api/fields', '/api/export/assets.xlsx']
PEOPLE = {'7': {'Title': 'Pat Example', 'EMail': 'pat.example@example.com'}}


def items():
    return [
        make_item(17, 'SN-FAKE-017', status=['OUT'], person=7, date_out='2026-09-03T07:00:00Z'),
        make_item(23, 'SN-FAKE-023', condition='NMC', last_inventory='2026-01-27T08:00:00Z'),
        make_item(42, 'SN-FAKE-042', status=['RMA'], location=['Test Bay B']),
    ]


@pytest.fixture
def sharepoint_app(pfx, monkeypatch):
    fake = FakeSharePoint(items(), people=PEOPLE)
    clock = FakeClock()
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=lambda s: None)
    source = sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                         clock=clock, background=False)
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    return dashboard.app.test_client(), fake, clock


@pytest.mark.parametrize('path', PAGES)
def test_every_page_with_the_csv_source(path):
    assert dashboard.app.test_client().get(path).status_code == 200


@pytest.mark.parametrize('path', PAGES)
def test_every_page_with_the_sharepoint_source(sharepoint_app, path):
    client, _, _ = sharepoint_app
    assert client.get(path).status_code == 200


def test_pages_show_sharepoint_data_and_item_ids(sharepoint_app):
    client, _, _ = sharepoint_app
    html = client.get('/').get_data(as_text=True)
    assert 'SharePoint: Asset Tracking V2' in html and ', fetched ' in html
    for item_id in ('17', '23', '42'):
        assert 'data-id="%s"' % item_id in html
    assert 'pat.example@example.com' in client.get('/checkouts').get_data(as_text=True)
    ids = [a['id'] for a in client.get('/api/assets').get_json()['assets']]
    assert ids == [17, 23, 42]


def test_excel_export_ids_filter_uses_sharepoint_item_ids(sharepoint_app):
    client, _, _ = sharepoint_app
    resp = client.get('/api/export/assets.xlsx?ids=17,42')
    assert resp.status_code == 200
    ws = load_workbook(io.BytesIO(resp.data)).active
    serials = [ws.cell(row=r, column=2).value for r in range(2, ws.max_row + 1)]
    assert serials == ['SN-FAKE-017', 'SN-FAKE-042']


def test_stale_copy_is_marked_on_every_page(sharepoint_app):
    client, fake, clock = sharepoint_app
    assert client.get('/').status_code == 200
    fake.fail_status = 503
    clock.advance(301)
    for path in ['/', '/attention', '/checkouts', '/metrics']:
        resp = client.get(path)
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'This data is out of date.' in html
        assert 'server problem' in html
        assert 'SN-FAKE-017' in client.get('/').get_data(as_text=True)


def test_no_good_fetch_shows_the_error_page(pfx, monkeypatch):
    fake = FakeSharePoint(items())
    fake.fail_status = 403
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=lambda s: None)
    source = sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                         clock=FakeClock(), background=False)
    monkeypatch.setattr(dashboard, 'SOURCE', source)
    resp = dashboard.app.test_client().get('/')
    assert resp.status_code == 503
    assert 'Permission missing' in resp.get_data(as_text=True)
