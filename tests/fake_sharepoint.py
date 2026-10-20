"""Made-up Microsoft Graph and SharePoint replies for the tests.

Nothing here comes from the real list: the site, people, serial numbers and
notes are invented. No test makes a network request.
"""
import base64
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from xml.etree import ElementTree

import sharepoint

SITE_ID = 'contoso.sharepoint.com,11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222'
WEB_URL = 'https://contoso.sharepoint.com/sites/TestOps'
LIST_ID = '33333333-3333-3333-3333-333333333333'
LIST_NAME = 'Asset Tracking V2'
FAKE_TOKEN_SECRET_PART = 'not-a-real-signature'


def make_jwt(claims):
    def part(obj):
        raw = json.dumps(obj).encode('utf-8')
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    return '%s.%s.%s' % (part({'alg': 'none'}), part(claims), FAKE_TOKEN_SECRET_PART)


class FakeTokens:
    def __init__(self, roles=('Sites.Selected',), fail=None):
        self.token_value = make_jwt({'roles': list(roles)})
        self.fail = fail
        self.scopes = []

    def token(self, scope):
        self.scopes.append(scope)
        if self.fail:
            raise sharepoint.SourceError(self.fail)
        return self.token_value


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError('no body')
        return self._body


GRAPH_COLUMNS = [
    {'name': 'Title', 'displayName': 'Title', 'text': {}},
    {'name': 'AssetType', 'displayName': 'Asset Type',
     'choice': {'choices': ['VXE-30', 'SGCS 1', 'Field Support Kit']}},
    {'name': 'SerialNumber', 'displayName': 'Serial Number', 'text': {}},
    {'name': 'OwnershipandLocation', 'displayName': 'Location',
     'choice': {'choices': ['Test Bay A', 'Test Bay B']}},
    {'name': 'MaterialCondition', 'displayName': 'Material Condition',
     'choice': {'choices': ['FMC', 'PMC', 'NMC', 'Destroyed/Lost']}},
    {'name': 'PartNumber', 'displayName': 'Part Number', 'text': {}},
    {'name': 'DateOut', 'displayName': 'Date Out', 'dateTime': {'format': 'dateTime'}},
    {'name': 'CheckOutBy_x002f_To', 'displayName': 'Check Out By/To', 'personOrGroup': {}},
    {'name': 'AssetNotes', 'displayName': 'Asset Notes', 'text': {'allowMultipleLines': True}},
    {'name': 'LastInventory', 'displayName': 'Last Inventory', 'dateTime': {'format': 'dateOnly'}},
    {'name': 'ShelfLocation', 'displayName': 'Shelf Location', 'text': {}},
    {'name': 'Ownership', 'displayName': 'Ownership',
     'choice': {'choices': ['Team Alpha', 'Team Bravo']}},
    {'name': 'Status', 'displayName': 'Status',
     'choice': {'choices': ['IN', 'OUT', 'RMA', 'BAILMENT']}},
]


def make_item(item_id, serial, asset_type='VXE-30', status=('IN',), location=('Test Bay A',),
              condition='FMC', owner='Team Alpha', date_out=None, person=None,
              last_inventory=None, notes='', part='', shelf=''):
    fields = {
        'Title': '', 'AssetType': asset_type, 'SerialNumber': serial,
        'OwnershipandLocation': list(location), 'MaterialCondition': condition,
        'Ownership': owner, 'Status': list(status),
        'Status@odata.type': 'Collection(Edm.String)',
        'OwnershipandLocation@odata.type': 'Collection(Edm.String)',
    }
    for key, value in [('PartNumber', part), ('AssetNotes', notes), ('ShelfLocation', shelf),
                       ('DateOut', date_out), ('LastInventory', last_inventory)]:
        if value:
            fields[key] = value
    if person is not None:
        fields['CheckOutBy_x002f_ToLookupId'] = str(person)
    return {'id': str(item_id), 'fields': fields}


def schema_xml():
    """SchemaXml for two columns, shaped like the real list's: Status with a
    pill formatter (IN green, OUT dark red), and Asset Type with none."""
    formatter = {
        'elmType': 'div',
        'children': [{
            'forEach': '__INTERNAL__ in @currentField',
            'elmType': 'div',
            'attributes': {'class': {'operator': ':', 'operands': [
                {'operator': '==', 'operands': ['[$__INTERNAL__]', 'IN']},
                'sp-css-backgroundColor-BgGreen sp-css-color-WhiteFont',
                {'operator': ':', 'operands': [
                    {'operator': '==', 'operands': ['[$__INTERNAL__]', 'OUT']},
                    'sp-css-backgroundColor-BgDarkRed sp-css-color-WhiteFont',
                    'sp-field-borderAllRegular']}]}},
        }],
    }
    status = ElementTree.Element('Field', {
        'DisplayName': 'Status', 'Name': 'Status', 'Type': 'MultiChoice',
        'CustomFormatter': json.dumps(formatter)})
    choices = ElementTree.SubElement(status, 'CHOICES')
    for c in ['IN', 'OUT', 'RMA', 'BAILMENT']:
        ElementTree.SubElement(choices, 'CHOICE').text = c
    asset_type = ElementTree.Element('Field', {
        'DisplayName': 'Asset Type', 'Name': 'AssetType', 'Type': 'Choice'})
    choices = ElementTree.SubElement(asset_type, 'CHOICES')
    for c in ['VXE-30', 'SGCS 1', 'Field Support Kit']:
        ElementTree.SubElement(choices, 'CHOICE').text = c
    return [ElementTree.tostring(status, encoding='unicode'),
            ElementTree.tostring(asset_type, encoding='unicode')]


class FakeSharePoint:
    """Answers the GET requests sharepoint.py makes, from in-memory data.
    It has no way to answer anything but GET."""

    def __init__(self, items, page_size=200, people=None, schema=True,
                 user_list_in_graph=True, list_name=LIST_NAME):
        self.items = items
        self.page_size = page_size
        self.people = people or {}
        self.schema = schema_xml() if schema is True else schema
        self.user_list_in_graph = user_list_in_graph
        self.list_name = list_name
        self.fail_status = None
        self.fail_path = None
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        assert headers['Authorization'].startswith('Bearer ')
        assert timeout
        self.calls.append(url)
        parsed = urlparse(url)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        if self.fail_status and (self.fail_path is None or self.fail_path in path):
            return FakeResponse(self.fail_status, {'error': {'code': 'fakeFailure', 'message': 'x'}})
        if parsed.netloc == 'contoso.sharepoint.com':
            return self._rest(path)
        return self._graph(url, path, query)

    def _rest(self, path):
        if path.endswith('/fields'):
            # schema=None refuses with 403; schema=401 (any number) with that status.
            if self.schema is None or isinstance(self.schema, int):
                return FakeResponse(self.schema or 403,
                                    {'odata.error': {'code': '-2147024891, Access denied'}})
            return FakeResponse(200, {'value': [{'SchemaXml': x, 'Hidden': False} for x in self.schema]})
        m = re.search(r'getuserbyid\((\d+)\)', path)
        if m:
            person = self.people.get(m.group(1))
            if not person:
                return FakeResponse(404, {'odata.error': {'code': 'not found'}})
            return FakeResponse(200, {'Title': person['Title'], 'Email': person['EMail']})
        return FakeResponse(404, {})

    def _graph(self, url, path, query):
        site = '/v1.0/sites/%s' % SITE_ID
        if path == site:
            return FakeResponse(200, {'id': SITE_ID, 'displayName': 'Test Ops', 'name': 'TestOps',
                                      'webUrl': WEB_URL})
        if not path.startswith(site):
            return FakeResponse(404, {'error': {'code': 'itemNotFound'}})
        rest = path[len(site):]
        if rest == '/lists':
            return FakeResponse(200, {'value': [
                {'id': 'docs', 'displayName': 'Documents', 'name': 'Shared Documents'},
                {'id': LIST_ID, 'displayName': self.list_name, 'name': 'AssetTrackingV2'},
            ]})
        if rest == '/lists/%s/columns' % LIST_ID:
            return FakeResponse(200, {'value': GRAPH_COLUMNS})
        if rest == '/lists/%s/items' % LIST_ID:
            start = int(query.get('$skiptoken', ['0'])[0])
            page = self.items[start:start + self.page_size]
            body = {'value': page}
            if start + self.page_size < len(self.items):
                next_query = dict((k, v[0]) for k, v in query.items())
                next_query['$skiptoken'] = str(start + self.page_size)
                body['@odata.nextLink'] = url.split('?')[0] + '?' + urlencode(next_query)
            return FakeResponse(200, body)
        if rest == '/lists/User Information List':
            if not self.user_list_in_graph:
                return FakeResponse(404, {'error': {'code': 'itemNotFound'}})
            return FakeResponse(200, {'id': 'user-info'})
        m = re.fullmatch(r'/lists/User Information List/items/(\d+)', rest)
        if m and self.user_list_in_graph:
            person = self.people.get(m.group(1))
            if not person:
                return FakeResponse(404, {'error': {'code': 'itemNotFound'}})
            return FakeResponse(200, {'id': m.group(1), 'fields': dict(person)})
        return FakeResponse(404, {'error': {'code': 'itemNotFound'}})


def fake_env(pfx, **overrides):
    env = {
        'SP_TENANT_ID': 'tenant-made-up-0001',
        'SP_CLIENT_ID': 'client-made-up-0002',
        'SP_SITE_ID': SITE_ID,
        'SP_LIST_NAME': LIST_NAME,
        'SP_CERT_PATH': pfx['path'],
        'SP_CERT_PASSWORD': pfx['password'],
        'SITE_TIMEZONE': 'America/Los_Angeles',
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


def make_pfx(password):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'asset-dashboard-test')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=365))
            .sign(key, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(
        b'test', key, cert, None, BestAvailableEncryption(password.encode('utf-8')))


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
