import json
import logging
from datetime import date
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import assets as asset_data
import sharepoint
from fake_sharepoint import (FakeClock, FakeSharePoint, FakeTokens, LIST_NAME, fake_env,
                             make_item)

TZ = ZoneInfo('America/Los_Angeles')
PEOPLE = {
    '7': {'Title': 'Pat Example', 'EMail': 'pat.example@example.com'},
    '8': {'Title': 'Sam Sample', 'EMail': 'sam.sample@example.com'},
}


def sample_items(n=5):
    items = [make_item(100 + i, 'SN-TEST-%03d' % i) for i in range(n)]
    items[0] = make_item(100, 'SN-TEST-000', status=['OUT'], person=7,
                         date_out='2026-01-27T08:00:00Z', last_inventory='2026-07-15T07:00:00Z',
                         notes='made-up note', part=' PN-0001\t', shelf='Shelf 1 ')
    return items


def reader_for(fake, pfx, tokens=None, **env):
    settings = sharepoint.load_settings(fake_env(pfx, **env))
    client = sharepoint.GraphClient(tokens or FakeTokens(), session=fake, sleep=lambda s: None)
    return sharepoint.ListReader(client, settings, TZ)


def source_for(fake, pfx, clock=None, tokens=None):
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(tokens or FakeTokens(), session=fake, sleep=lambda s: None)
    return sharepoint.SharePointSource(settings, 'America/Los_Angeles', client=client,
                                       clock=clock or FakeClock(), background=False)


# --- Reading the list ------------------------------------------------------

def test_paging_follows_next_link_across_three_pages(pfx):
    fake = FakeSharePoint(sample_items(5), page_size=2, people=PEOPLE)
    reader = reader_for(fake, pfx)
    rows = reader.fetch()
    assert [r['serial_number'] for r in rows] == ['SN-TEST-%03d' % i for i in range(5)]
    assert reader.item_pages == 3
    assert len([c for c in fake.calls if '/items?' in c and 'User' not in c]) == 3


def test_internal_names_come_from_the_column_definitions(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE)
    reader = reader_for(fake, pfx)
    row = reader.fetch()[0]
    # A display name with a space, one with "/", and one whose internal name
    # is different altogether.
    assert reader.mapping['Serial Number'] == 'SerialNumber'
    assert reader.mapping['Check Out By/To'] == 'CheckOutBy_x002f_To'
    assert reader.mapping['Location'] == 'OwnershipandLocation'
    assert row['serial_number'] == 'SN-TEST-000'
    assert row['checked_out_to'] == 'pat.example@example.com'
    assert row['location'] == ['Test Bay A']
    assert row['status'] == ['OUT']
    # Same cleaning as the CSV path: tabs and trailing spaces removed.
    assert row['part_number'] == 'PN-0001'
    assert row['shelf_location'] == 'Shelf 1'
    assert reader.missing_columns == []


def test_rows_have_the_same_keys_and_types_as_csv_rows(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE)
    sp_row = reader_for(fake, pfx).fetch()[0]
    csv_row = dashboard.CsvSource(dashboard.ASSET_CSV, 'America/Los_Angeles').load()['assets'][0]
    assert set(sp_row) == set(csv_row)
    for key in csv_row:
        if csv_row[key] is not None and sp_row[key] is not None:
            assert type(sp_row[key]) is type(csv_row[key]), key


def test_winter_and_summer_dates_land_on_the_same_day_as_the_csv(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE)
    reader = reader_for(fake, pfx)
    row = reader.fetch()[0]
    # Winter: Pacific Standard Time, midnight is 08:00 UTC.
    assert row['date_out'] == date(2026, 1, 27)
    # Summer: Pacific Daylight Time, midnight is 07:00 UTC.
    assert row['last_inventory'] == date(2026, 7, 15)
    csv_style = asset_data._clean_row(
        {'Date Out': '2026-01-27T08:00:00Z', 'Last Inventory': '2026-07-15T07:00:00Z'}, TZ, 1)
    assert (csv_style['date_out'], csv_style['last_inventory']) == (row['date_out'], row['last_inventory'])
    assert reader.date_check() == (2, 2)


def test_person_ids_resolve_and_unknown_ids_are_shown_and_recorded(pfx, caplog):
    items = sample_items(3)
    items[1] = make_item(101, 'SN-TEST-001', person=99)
    fake = FakeSharePoint(items, people=PEOPLE)
    reader = reader_for(fake, pfx)
    with caplog.at_level(logging.WARNING, logger='asset_management.sharepoint'):
        rows = reader.fetch()
    assert rows[0]['checked_out_to'] == 'pat.example@example.com'
    assert rows[1]['checked_out_to'] == '(unknown person, ID 99)'
    assert rows[2]['checked_out_to'] == ''
    assert reader.people_resolved == 1
    assert reader.people_unresolved == ['99']
    assert reader.people_route == 'graph'
    assert 'person ID(s): 99' in caplog.text


def test_resolved_people_are_cached_between_refreshes(pfx):
    fake = FakeSharePoint(sample_items(2), people=PEOPLE)
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake)
    cache = {}
    sharepoint.ListReader(client, settings, TZ, cache).fetch()
    sharepoint.ListReader(client, settings, TZ, cache).fetch()
    assert len([c for c in fake.calls if 'User%20Information%20List/items/7' in c]) == 1


def test_person_lookup_falls_back_to_sharepoint_rest(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE, user_list_in_graph=False)
    reader = reader_for(fake, pfx)
    row = reader.fetch()[0]
    assert reader.people_route == 'rest'
    assert row['checked_out_to'] == 'pat.example@example.com'


def test_choices_and_colors_come_from_schemaxml(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE)
    tokens = FakeTokens()
    reader = reader_for(fake, pfx, tokens=tokens)
    reader.fetch()
    assert reader.schema_source == 'SchemaXml'
    status = reader.fields['status']
    assert status['choices'] == ['IN', 'OUT', 'RMA', 'BAILMENT']
    assert status['colors']['IN'] == {'bg': asset_data.BG_COLORS['BgGreen'], 'fg': '#ffffff'}
    assert status['colors']['OUT']['bg'] == asset_data.BG_COLORS['BgDarkRed']
    assert reader.fields['asset_type']['colors'] == {}
    # SchemaXml needs a token for SharePoint itself, not for Graph.
    assert 'https://contoso.sharepoint.com/.default' in tokens.scopes


def test_choices_fall_back_to_graph_when_schemaxml_is_refused(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE, schema=None)
    reader = reader_for(fake, pfx)
    rows = reader.fetch()
    assert reader.schema_source == 'fallback'
    assert 'Permission missing' in reader.schema_fallback_reason
    assert reader.fields['status']['choices'] == ['IN', 'OUT', 'RMA', 'BAILMENT']
    assert reader.fields['status']['type'] == 'MultiChoice'
    assert reader.fields['asset_type']['type'] == 'Choice'
    assert all(f['colors'] == {} for f in reader.fields.values())
    assert len(rows) == 1


def test_list_not_found_names_the_list(pfx):
    fake = FakeSharePoint(sample_items(1), list_name='Something Else')
    with pytest.raises(sharepoint.SourceError, match='List not found.*Asset Tracking V2'):
        reader_for(fake, pfx).fetch()


def test_throttling_reply_is_waited_out(pfx):
    fake = FakeSharePoint(sample_items(1), people=PEOPLE)
    original = fake.get
    replies = []

    def throttle_once(url, headers=None, timeout=None):
        if not replies:
            replies.append(1)
            from fake_sharepoint import FakeResponse
            return FakeResponse(429, {'error': {'code': 'tooManyRequests'}}, {'Retry-After': '2'})
        return original(url, headers=headers, timeout=timeout)

    fake.get = throttle_once
    waits = []
    settings = sharepoint.load_settings(fake_env(pfx))
    client = sharepoint.GraphClient(FakeTokens(), session=fake, sleep=waits.append)
    assert len(sharepoint.ListReader(client, settings, TZ).fetch()) == 1
    assert waits == [2]


# --- Settings and certificate ----------------------------------------------

def test_missing_setting_is_named_and_values_are_not_printed(pfx):
    env = fake_env(pfx, SP_CERT_PASSWORD=None, SP_LIST_NAME=None)
    with pytest.raises(sharepoint.ConfigError) as e:
        sharepoint.load_settings(env)
    message = str(e.value)
    assert 'SP_CERT_PASSWORD' in message and 'SP_LIST_NAME' in message
    for value in env.values():
        assert value not in message


def test_missing_certificate_file(pfx, tmp_path):
    missing = str(tmp_path / 'nowhere' / 'cert.pfx')
    with pytest.raises(sharepoint.ConfigError) as e:
        sharepoint.load_certificate(missing, pfx['password'])
    assert 'SP_CERT_PATH' in str(e.value)
    assert missing not in str(e.value)


def test_wrong_certificate_password(pfx):
    with pytest.raises(sharepoint.ConfigError) as e:
        sharepoint.load_certificate(pfx['path'], 'wrong password 123')
    assert 'SP_CERT_PASSWORD' in str(e.value)
    assert 'wrong password 123' not in str(e.value)
    cert = sharepoint.load_certificate(pfx['path'], pfx['password'])
    assert len(cert['thumbprint_sha1']) == 40


def test_app_does_not_start_with_a_missing_setting(pfx):
    with pytest.raises(SystemExit) as e:
        dashboard.make_source('sharepoint', fake_env(pfx, SP_SITE_ID=None))
    assert 'SP_SITE_ID' in str(e.value)
    with pytest.raises(SystemExit) as e:
        dashboard.make_source('sharepoint', fake_env(pfx, SP_CERT_PASSWORD='nope'))
    assert 'SP_CERT_PASSWORD' in str(e.value) and 'nope' not in str(e.value)


def test_refresh_seconds_default_and_validation(pfx):
    assert sharepoint.load_settings(fake_env(pfx))['refresh_seconds'] == 300
    assert sharepoint.load_settings(fake_env(pfx, SP_REFRESH_SECONDS='600'))['refresh_seconds'] == 600
    with pytest.raises(sharepoint.ConfigError, match='SP_REFRESH_SECONDS'):
        sharepoint.load_settings(fake_env(pfx, SP_REFRESH_SECONDS='5'))


# --- Caching and failure ---------------------------------------------------

def test_copy_is_reused_until_refresh_is_due(pfx):
    fake = FakeSharePoint(sample_items(2), people=PEOPLE)
    clock = FakeClock()
    source = source_for(fake, pfx, clock)
    first = source.load()
    calls = len(fake.calls)
    clock.advance(299)
    assert source.load()['assets'] == first['assets']
    assert len(fake.calls) == calls
    clock.advance(2)
    source.load()
    assert len(fake.calls) > calls
    assert first['source'] == 'SharePoint: %s' % LIST_NAME


def test_failed_refresh_keeps_serving_the_last_good_copy(pfx, caplog):
    fake = FakeSharePoint(sample_items(2), people=PEOPLE)
    clock = FakeClock()
    tokens = FakeTokens()
    source = source_for(fake, pfx, clock, tokens)
    good = source.load()
    assert good['stale'] is None

    fake.fail_status = 500
    clock.advance(301)
    with caplog.at_level(logging.INFO):
        stale = source.load()
    assert stale['assets'] == good['assets']
    assert stale['stale']['since'] == good['loaded_at']
    assert 'server problem' in stale['stale']['reason']
    assert 'SharePoint refresh failed' in caplog.text
    # Logs never hold the token, the certificate password or list contents.
    assert tokens.token_value not in caplog.text
    assert pfx['password'] not in caplog.text
    assert 'SN-TEST' not in caplog.text

    fake.fail_status = None
    clock.advance(61)
    assert source.load()['stale'] is None


def test_first_fetch_failing_shows_the_error_not_an_empty_list(pfx):
    fake = FakeSharePoint(sample_items(2))
    fake.fail_status = 403
    clock = FakeClock()
    source = source_for(fake, pfx, clock)
    with pytest.raises(sharepoint.SourceError, match='Permission missing'):
        source.load()
    calls = len(fake.calls)
    # Within the retry wait the same error comes back without new requests.
    with pytest.raises(sharepoint.SourceError, match='Permission missing'):
        source.load()
    assert len(fake.calls) == calls


class FakeLogin:
    """Answers MSAL's two requests to Microsoft's sign-in service."""

    def __init__(self, token_reply):
        self.token_reply = token_reply
        self.posts = []

    def _reply(self, body):
        class Reply:
            # Microsoft answers a refused sign-in with HTTP 400.
            status_code = 400 if 'error' in body else 200
            headers = {}
            text = json.dumps(body)

            def raise_for_status(self):
                pass
        return Reply()

    def get(self, url, **kwargs):
        if 'discovery/instance' in url:
            return self._reply({'metadata': [{'preferred_network': 'login.microsoftonline.com',
                                              'aliases': ['login.microsoftonline.com']}]})
        tenant = url.split('/')[3]
        base = 'https://login.microsoftonline.com/' + tenant
        return self._reply({
            'authorization_endpoint': base + '/oauth2/v2.0/authorize',
            'token_endpoint': base + '/oauth2/v2.0/token',
            'device_authorization_endpoint': base + '/oauth2/v2.0/devicecode',
            'issuer': base + '/v2.0',
        })

    def post(self, url, data=None, headers=None, **kwargs):
        self.posts.append(data)
        return self._reply(self.token_reply)

    def close(self):
        pass


def test_msal_signs_in_with_the_pfx_and_reuses_the_token(pfx):
    from fake_sharepoint import make_jwt
    token = make_jwt({'roles': ['Sites.Selected']})
    login = FakeLogin({'access_token': token, 'token_type': 'Bearer', 'expires_in': 3599})
    provider = sharepoint.TokenProvider(sharepoint.load_settings(fake_env(pfx)), http_client=login)
    assert provider.token(sharepoint.GRAPH_SCOPE) == token
    assert provider.token(sharepoint.GRAPH_SCOPE) == token
    # One sign-in request; the second call reused MSAL's cached token.
    assert len(login.posts) == 1
    body = login.posts[0]
    assert body['grant_type'] == 'client_credentials'
    assert body['client_assertion_type'] == 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer'
    assertion = body['client_assertion']
    assertion = assertion.decode('ascii') if isinstance(assertion, bytes) else assertion
    # A signed JWT: header, claims and signature.
    assert assertion.count('.') == 2
    assert pfx['password'] not in assertion
    assert sharepoint.token_roles(token) == ['Sites.Selected']


def test_msal_sign_in_refusal_is_in_plain_words(pfx):
    login = FakeLogin({'error': 'invalid_client',
                       'error_description': 'AADSTS700016: Application not found.'})
    provider = sharepoint.TokenProvider(sharepoint.load_settings(fake_env(pfx)), http_client=login)
    with pytest.raises(sharepoint.SourceError, match='client ID .SP_CLIENT_ID. is not known'):
        provider.token(sharepoint.GRAPH_SCOPE)


def test_sign_in_errors_are_in_plain_words():
    text = sharepoint._sign_in_error({'error': 'invalid_client',
                                      'error_description': 'AADSTS700027: Client assertion failed.'})
    assert 'not the one uploaded to the app registration' in text
    assert 'AADSTS700027' in text


# --- The check command -----------------------------------------------------

def run_check(fake, pfx, **env):
    lines = []
    tokens = FakeTokens(roles=['Sites.Selected'])
    code = sharepoint.run_check(
        fake_env(pfx, **env), out=lines.append,
        client_factory=lambda s: sharepoint.GraphClient(tokens, session=fake, sleep=lambda x: None))
    return code, '\n'.join(lines), tokens


def test_check_reports_every_step_without_secrets_or_contents(pfx):
    items = sample_items(5)
    items[1] = make_item(101, 'SN-TEST-001', person=99)
    fake = FakeSharePoint(items, page_size=2, people=PEOPLE)
    code, text, tokens = run_check(fake, pfx, ASSET_SOURCE='csv')
    assert code == 0, text
    assert 'Permissions in the token: Sites.Selected' in text
    assert 'Name: Test Ops' in text and 'URL: https://contoso.sharepoint.com/sites/TestOps' in text
    assert 'Found "Asset Tracking V2"' in text
    assert 'Check Out By/To | CheckOutBy_x002f_To | personOrGroup' in text
    assert '5 items, read in 3 page(s).' in text
    assert 'From SharePoint SchemaXml' in text
    assert 'Resolved 1, not resolved 1' in text
    assert 'All 2 date values are midnight' in text
    assert 'RESULT: every step passed.' in text
    for secret in [tokens.token_value, pfx['password'], 'SN-TEST', 'pat.example',
                   'made-up note', 'client-made-up-0002', 'tenant-made-up-0001']:
        assert secret not in text
    assert all(c.startswith('https://') for c in fake.calls)


def test_check_says_which_step_failed_and_keeps_earlier_steps(pfx):
    fake = FakeSharePoint(sample_items(1))
    fake.fail_status = 404
    fake.fail_path = '/v1.0/sites/'
    code, text, _ = run_check(fake, pfx)
    assert code == 1
    assert '[OK]     1. Settings' in text
    assert '[OK]     2. Certificate' in text
    assert '[OK]     3. Sign-in' in text
    assert '[FAILED] 4. Site' in text and 'Not found: the site in SP_SITE_ID' in text
    assert '5. List: not run, because step 4 failed' in text
    assert 'RESULT: stopped at 4. Site.' in text


def test_check_reports_a_wrong_password_as_the_certificate_step(pfx):
    code, text, _ = run_check(FakeSharePoint([]), pfx, SP_CERT_PASSWORD='not it')
    assert code == 1
    assert '[FAILED] 2. Certificate' in text and 'SP_CERT_PASSWORD' in text
    assert 'not it' not in text
