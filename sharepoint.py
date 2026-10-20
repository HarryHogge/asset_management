"""Read the Asset Tracking list live from SharePoint, through Microsoft Graph.

This is the second data source next to the CSV export (see assets.py). It only
ever makes GET requests: it never creates, changes or deletes anything in
SharePoint or Microsoft 365.

How a fetch works, in order:

1. Sign in as the app (no user) with the certificate, using MSAL.
2. Look up the site (SP_SITE_ID) and find the list by name (SP_LIST_NAME).
3. Read the list's column definitions, to map each column's display name
   ("Serial Number") to the internal name Graph uses ("SerialNumber").
4. Read every item, page by page, until Graph says there are no more.
5. Read the choice values and pill colors. Graph does not return SharePoint's
   column formatting, so these come from SharePoint's own REST API
   (`SchemaXml`, the same XML the CSV export carries). If that is refused,
   the choices come from Graph and the pills use the default style.
6. Turn the "Check Out By/To" person IDs into the person's email address,
   which is what the CSV export shows, through the site's hidden
   "User Information List".
7. Clean each item into the same row the CSV path produces.

Run `python -m sharepoint --check` to try all of this once and print a report
that is safe to paste into a chat. See README.md.
"""
import base64
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import assets as asset_data

log = logging.getLogger('asset_management.sharepoint')

GRAPH = 'https://graph.microsoft.com/v1.0'
GRAPH_SCOPE = 'https://graph.microsoft.com/.default'
LOGIN = 'https://login.microsoftonline.com/'

# Every one of these must be set when ASSET_SOURCE=sharepoint. No defaults.
REQUIRED_SETTINGS = [
    'SP_TENANT_ID', 'SP_CLIENT_ID', 'SP_SITE_ID', 'SP_LIST_NAME',
    'SP_CERT_PATH', 'SP_CERT_PASSWORD',
]
DEFAULT_REFRESH_SECONDS = 300
MIN_REFRESH_SECONDS = 30
# After a failed refresh, wait this long before trying again, so a broken
# connection does not turn every page view into a slow failed request.
RETRY_AFTER_FAILURE_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 30
PAGE_SIZE = 200
USER_INFO_LIST = 'User Information List'
PERSON_HEADER = 'Check Out By/To'
DATE_HEADERS = [h for h, k in asset_data.COLUMNS.items() if k in asset_data.DATES]
MULTI_HEADERS = [h for h, k in asset_data.COLUMNS.items() if k in asset_data.MULTI_CHOICE]


class ConfigError(Exception):
    """A setting or the certificate is wrong. The message names the setting
    and never contains its value."""


class SourceError(Exception):
    """Reading from Microsoft failed. The message is in plain words and is
    safe to show on a page or in a log."""


# ---------------------------------------------------------------------------
# Settings and certificate
# ---------------------------------------------------------------------------

def load_settings(env=None):
    env = os.environ if env is None else env
    missing = [name for name in REQUIRED_SETTINGS if not (env.get(name) or '').strip()]
    if missing:
        raise ConfigError(
            'Missing setting in .env: %s. To read from SharePoint, every SP_ setting '
            'except SP_REFRESH_SECONDS must be set.' % ', '.join(missing))
    raw_refresh = (env.get('SP_REFRESH_SECONDS') or '').strip()
    if raw_refresh:
        try:
            refresh = int(raw_refresh)
        except ValueError:
            refresh = 0
        if refresh < MIN_REFRESH_SECONDS:
            raise ConfigError('SP_REFRESH_SECONDS must be a whole number of seconds, '
                              '%d or more.' % MIN_REFRESH_SECONDS)
    else:
        refresh = DEFAULT_REFRESH_SECONDS
    return {
        'tenant_id': env['SP_TENANT_ID'].strip(),
        'client_id': env['SP_CLIENT_ID'].strip(),
        'site_id': env['SP_SITE_ID'].strip(),
        'list_name': env['SP_LIST_NAME'].strip(),
        'cert_path': env['SP_CERT_PATH'].strip().strip('"'),
        # Not stripped: a password may legitimately start or end with a space.
        'cert_password': env['SP_CERT_PASSWORD'],
        'refresh_seconds': refresh,
    }


def load_certificate(path, password):
    """Open the .pfx to prove the path and password are right, and return the
    public facts about it (never the key itself)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import pkcs12

    if not os.path.isfile(path):
        raise ConfigError('SP_CERT_PATH: there is no file at that path. Use the full '
                          'path to the .pfx file, for example C:\\certs\\asset-dashboard.pfx.')
    with open(path, 'rb') as f:
        data = f.read()
    try:
        key, cert, _ = pkcs12.load_key_and_certificates(data, password.encode('utf-8'))
    except ValueError:
        raise ConfigError('SP_CERT_PASSWORD: the certificate file could not be opened. '
                          'Either the password is wrong, or SP_CERT_PATH does not point '
                          'to a .pfx file.') from None
    if key is None or cert is None:
        raise ConfigError('SP_CERT_PATH: the .pfx file does not contain both a certificate '
                          'and its private key. Ask IT for the .pfx that includes the private key.')
    return {
        # Thumbprints are public: Entra shows them next to the app's certificates.
        'thumbprint_sha1': cert.fingerprint(hashes.SHA1()).hex().upper(),
        'expires': cert.not_valid_after_utc,
    }


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------

# Entra sign-in error codes, in plain words.
SIGN_IN_ERRORS = {
    'AADSTS700016': 'the client ID (SP_CLIENT_ID) is not known in this tenant',
    'AADSTS90002': 'the tenant ID (SP_TENANT_ID) was not found',
    'AADSTS900023': 'the tenant ID (SP_TENANT_ID) is not valid',
    'AADSTS700027': 'Microsoft did not accept the certificate. This certificate is '
                    'probably not the one uploaded to the app registration',
    'AADSTS7000112': 'the app registration is disabled',
    'AADSTS700024': 'the sign-in was outside its valid time. Check the PROD server clock',
    'AADSTS500011': 'the resource (Graph or SharePoint) is not available to this tenant',
    'AADSTS1002012': 'the requested permission scope is not valid',
}


def _sign_in_error(result):
    text = '%s %s' % (result.get('error', ''), result.get('error_description', ''))
    codes = [w.rstrip(':') for w in text.split() if w.startswith('AADSTS')]
    code = codes[0] if codes else ''
    meaning = SIGN_IN_ERRORS.get(code)
    if meaning:
        return 'Sign-in refused: %s (%s).' % (meaning, code)
    if code:
        return 'Sign-in refused by Microsoft (%s).' % code
    return 'Sign-in refused by Microsoft (%s).' % (result.get('error') or 'no reason given')


class TokenProvider:
    """App-only tokens from MSAL, signed with the certificate.

    MSAL keeps each token in memory and hands back the same one until it is
    about five minutes from expiring (tokens last about an hour), so asking
    for a token on every request costs nothing."""

    def __init__(self, settings, http_client=None):
        self._settings = settings
        # Only the tests pass an HTTP client, to answer MSAL without a network.
        self._http_client = http_client
        self._app = None
        self._lock = threading.Lock()

    def _client(self):
        import msal
        with self._lock:
            if self._app is None:
                s = self._settings
                extra = {'http_client': self._http_client} if self._http_client else {}
                try:
                    self._app = msal.ConfidentialClientApplication(
                        s['client_id'],
                        authority=LOGIN + s['tenant_id'],
                        client_credential={
                            'private_key_pfx_path': s['cert_path'],
                            'passphrase': s['cert_password'],
                        },
                        **extra,
                    )
                except ValueError as e:
                    # MSAL looks the tenant up here; its message may repeat the
                    # tenant ID, so only the kind of problem is passed on.
                    raise SourceError('Sign-in could not start: Microsoft did not recognise '
                                      'the tenant ID (SP_TENANT_ID), or %s could not be '
                                      'reached (%s).' % (LOGIN, type(e).__name__)) from None
                except Exception as e:
                    import requests
                    if isinstance(e, requests.exceptions.RequestException):
                        raise SourceError('Sign-in could not start: could not reach %s '
                                          '(network or proxy problem, %s).'
                                          % (LOGIN, type(e).__name__)) from None
                    log.exception('Unexpected problem starting sign-in')
                    raise SourceError('Sign-in could not start because of an unexpected '
                                      'problem (%s). Details are in the log.'
                                      % type(e).__name__) from None
            return self._app

    def token(self, scope):
        import requests
        app = self._client()
        try:
            result = app.acquire_token_for_client(scopes=[scope])
        except requests.exceptions.RequestException as e:
            raise SourceError('Sign-in failed: could not reach %s (network or proxy '
                              'problem, %s).' % (LOGIN, type(e).__name__)) from None
        except Exception as e:
            log.exception('Unexpected sign-in problem')
            raise SourceError('Sign-in failed with an unexpected problem (%s). Details are '
                              'in the log.' % type(e).__name__) from None
        if 'access_token' not in result:
            raise SourceError(_sign_in_error(result))
        return result['access_token']


def token_roles(token):
    """The application permissions in a token (its `roles` claim). The token
    is only read, not checked; Microsoft checks it on every request."""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload.encode('ascii')))
    except Exception:
        return None
    return sorted(claims.get('roles') or [])


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class GraphClient:
    """GET-only HTTP with plain-words errors. Follows paging links and waits
    out short throttling ("try again in N seconds") replies."""

    def __init__(self, tokens, session=None, sleep=time.sleep):
        if session is None:
            import requests
            session = requests.Session()
        self.tokens = tokens
        self.session = session
        self.sleep = sleep

    def get_json(self, url, what, scope=GRAPH_SCOPE, accept='application/json'):
        host = urlparse(url).netloc
        for attempt in range(3):
            token = self.tokens.token(scope)
            try:
                resp = self.session.get(url, headers={'Authorization': 'Bearer ' + token,
                                                      'Accept': accept},
                                        timeout=REQUEST_TIMEOUT_SECONDS)
            except Exception as e:
                raise SourceError('Could not reach %s while reading %s (network or proxy '
                                  'problem, %s).' % (host, what, type(e).__name__)) from None
            if resp.status_code in (429, 503) and attempt < 2:
                try:
                    wait = int(resp.headers.get('Retry-After', '5'))
                except ValueError:
                    wait = 5
                self.sleep(min(max(wait, 1), 30))
                continue
            if resp.status_code != 200:
                raise SourceError(http_error(resp, what))
            try:
                return resp.json()
            except ValueError:
                raise SourceError('Microsoft sent a reply that is not JSON while reading %s.'
                                  % what) from None
        raise SourceError(http_error(resp, what))

    def get_all(self, url, what, scope=GRAPH_SCOPE, accept='application/json'):
        """Every result across all pages. Returns (values, pages)."""
        values, pages = [], 0
        while url:
            body = self.get_json(url, what, scope=scope, accept=accept)
            pages += 1
            values.extend(body.get('value', []))
            url = body.get('@odata.nextLink') or body.get('odata.nextLink')
        return values, pages


def _error_code(resp):
    try:
        err = resp.json().get('error', {})
    except Exception:
        return ''
    if isinstance(err, dict):
        code = err.get('code') or ''
        return code if isinstance(code, str) else ''
    return ''


def http_error(resp, what):
    code = _error_code(resp)
    detail = ' (HTTP %d%s)' % (resp.status_code, ', ' + code if code else '')
    status = resp.status_code
    if status == 401:
        return 'The sign-in token was not accepted while reading %s%s.' % (what, detail)
    if status == 403:
        return ('Permission missing: the app signed in but is not allowed to read %s%s. '
                'With Sites.Selected, IT must also grant the app read access to this '
                'site.' % (what, detail))
    if status == 404:
        return 'Not found: %s%s.' % (what, detail)
    if status == 400:
        return 'Microsoft rejected the request for %s%s.' % (what, detail)
    if status == 429:
        return 'Microsoft is limiting requests (throttling) while reading %s%s.' % (what, detail)
    if status >= 500:
        return 'Microsoft had a server problem while reading %s%s.' % (what, detail)
    return 'Unexpected reply while reading %s%s.' % (what, detail)


# ---------------------------------------------------------------------------
# Reading the list
# ---------------------------------------------------------------------------

def column_type(col):
    """A short type name for a Graph column definition."""
    for facet in ('text', 'choice', 'dateTime', 'personOrGroup', 'number', 'boolean',
                  'calculated', 'lookup', 'currency', 'hyperlinkOrPicture', 'term',
                  'geolocation', 'thumbnail', 'contentApprovalStatus'):
        if facet in col:
            detail = col.get(facet) or {}
            if facet == 'text' and detail.get('allowMultipleLines'):
                return 'text (multiple lines)'
            if facet == 'dateTime' and detail.get('format'):
                return 'dateTime (%s)' % detail['format']
            return facet
    return 'other'


class ListReader:
    """One pass over the list. The steps are separate so the check command
    can run them one at a time and report each."""

    def __init__(self, client, settings, tz, people_cache=None):
        self.client = client
        self.settings = settings
        self.tz = tz
        self.people_cache = {} if people_cache is None else people_cache
        self.site = None
        self.list = None
        self.columns = []
        self.mapping = {}
        self.items = []
        self.item_pages = 0
        self.fields = {}
        self.schema_source = None
        self.schema_fallback_reason = None
        self.people_route = None
        self.people_resolved = 0
        self.people_unresolved = []

    @property
    def site_path(self):
        return '%s/sites/%s' % (GRAPH, self.settings['site_id'])

    def read_site(self):
        self.site = self.client.get_json(
            self.site_path + '?$select=id,displayName,name,webUrl',
            'the site in SP_SITE_ID')
        return self.site

    def find_list(self):
        lists, _ = self.client.get_all(self.site_path + '/lists?$select=id,displayName,name',
                                       'the lists on the site')
        wanted = self.settings['list_name'].casefold()
        for lst in lists:
            if (lst.get('displayName') or '').strip().casefold() == wanted:
                self.list = lst
                return lst
        names = sorted(l.get('displayName') or '' for l in lists)
        raise SourceError('List not found: the site has no list named "%s". Lists on the '
                          'site: %s.' % (self.settings['list_name'], ', '.join(names) or 'none'))

    @property
    def list_path(self):
        return '%s/lists/%s' % (self.site_path, self.list['id'])

    def read_columns(self):
        self.columns, _ = self.client.get_all(self.list_path + '/columns', 'the list columns')
        by_display = {}
        for col in self.columns:
            by_display.setdefault((col.get('displayName') or '').strip(), col)
        # Display name -> internal name, from the list's own definitions.
        self.mapping = {h: by_display[h]['name'] for h in asset_data.COLUMNS if h in by_display}
        missing = [h for h in asset_data.COLUMNS if h not in self.mapping]
        if missing:
            log.warning('SharePoint list has no column named: %s', ', '.join(missing))
        return self.columns

    @property
    def missing_columns(self):
        return [h for h in asset_data.COLUMNS if h not in self.mapping]

    def _graph_field_names(self):
        names = []
        for header, internal in self.mapping.items():
            names.append(internal + 'LookupId' if header == PERSON_HEADER else internal)
        return names

    def read_items(self):
        select = ','.join(self._graph_field_names())
        url = '%s/items?$expand=fields($select=%s)&$top=%d' % (self.list_path, select, PAGE_SIZE)
        self.items, self.item_pages = self.client.get_all(url, 'the list items')
        return self.items

    def read_schema(self):
        """Choices and pill colors. SharePoint's REST API returns each column's
        `SchemaXml`, which includes the formatting; Graph does not."""
        web_url = (self.site or {}).get('webUrl', '')
        host = urlparse(web_url).netloc
        try:
            if not host:
                raise SourceError('the site has no web address')
            url = ("%s/_api/web/lists(guid'%s')/fields?$select=SchemaXml,Hidden&$top=500"
                   % (web_url.rstrip('/'), self.list['id']))
            body = self.client.get_json(url, "the list's column formatting (SharePoint REST)",
                                        scope='https://%s/.default' % host,
                                        accept='application/json;odata=nometadata')
            xml_list = [f['SchemaXml'] for f in body.get('value', []) if f.get('SchemaXml')]
            if not xml_list:
                raise SourceError('SharePoint returned no column definitions')
            self.fields = asset_data.parse_schema_xml(xml_list)
            self.schema_source = 'SchemaXml'
            self.schema_fallback_reason = None
        except Exception as e:
            reason = str(e) if isinstance(e, SourceError) else (
                'the column formatting could not be read (%s)' % type(e).__name__)
            log.warning('Pill colors not available, using defaults: %s', reason)
            self.fields = self._fields_from_graph()
            self.schema_source = 'fallback'
            self.schema_fallback_reason = reason
        return self.fields

    def _fields_from_graph(self):
        multi = self._multi_value_headers()
        fields = {}
        for header, key in asset_data.COLUMNS.items():
            col = next((c for c in self.columns if c.get('name') == self.mapping.get(header)), None)
            if col is None:
                continue
            choices = []
            for c in (col.get('choice') or {}).get('choices', []):
                if c not in choices:
                    choices.append(c)
            kind = column_type(col)
            if kind == 'choice':
                kind = 'MultiChoice' if header in multi else 'Choice'
            fields[key] = {
                'label': header,
                'type': kind,
                'description': col.get('description') or '',
                'choices': choices,
                'colors': {},
            }
        return fields

    def _multi_value_headers(self):
        multi = set(MULTI_HEADERS)
        for item in self.items:
            f = item.get('fields', {})
            for header, internal in self.mapping.items():
                if isinstance(f.get(internal), list):
                    multi.add(header)
        return multi

    def _person_ids(self):
        internal = self.mapping.get(PERSON_HEADER)
        ids = []
        if not internal:
            return ids
        for item in self.items:
            value = item.get('fields', {}).get(internal + 'LookupId')
            values = value if isinstance(value, list) else [value]
            for v in values:
                if isinstance(v, dict):
                    v = v.get('LookupId')
                if v not in (None, '') and str(v) not in ids:
                    ids.append(str(v))
        return ids

    def resolve_people(self):
        """Look up each person ID once. Resolved names are kept between
        refreshes; IDs that could not be resolved are tried again next time."""
        ids = self._person_ids()
        todo = [i for i in ids if i not in self.people_cache]
        self.people_unresolved = []
        if not ids:
            self.people_route = self.people_route or 'none needed'
        elif todo:
            route = self._people_route()
            for person_id in todo:
                label = self._lookup_person(route, person_id) if route else None
                if label:
                    self.people_cache[person_id] = label
                else:
                    self.people_unresolved.append(person_id)
            if self.people_unresolved:
                log.warning('Could not resolve %d Check Out By/To person ID(s): %s',
                            len(self.people_unresolved), ', '.join(self.people_unresolved))
        else:
            self.people_route = self.people_route or 'cached'
        self.people_resolved = len([i for i in ids if i in self.people_cache])
        return self.people_resolved, self.people_unresolved

    def _people_route(self):
        """Graph's view of the hidden User Information List first; SharePoint's
        REST user lookup if Graph cannot see that list."""
        try:
            self.client.get_json('%s/lists/%s?$select=id' % (self.site_path, quote(USER_INFO_LIST)),
                                 'the User Information List')
            self.people_route = 'graph'
        except SourceError as e:
            log.warning('User Information List not readable through Graph: %s', e)
            self.people_route = 'rest' if (self.site or {}).get('webUrl') else None
        return self.people_route

    def _lookup_person(self, route, person_id):
        try:
            if route == 'graph':
                body = self.client.get_json(
                    '%s/lists/%s/items/%s?$expand=fields($select=Title,EMail)'
                    % (self.site_path, quote(USER_INFO_LIST), quote(person_id)),
                    'person ID %s' % person_id)
                f = body.get('fields', {})
                return (f.get('EMail') or f.get('Title') or '').strip() or None
            web_url = self.site['webUrl'].rstrip('/')
            body = self.client.get_json(
                '%s/_api/web/getuserbyid(%d)' % (web_url, int(person_id)),
                'person ID %s (SharePoint REST)' % person_id,
                scope='https://%s/.default' % urlparse(web_url).netloc,
                accept='application/json;odata=nometadata')
            return (body.get('Email') or body.get('Title') or '').strip() or None
        except (SourceError, ValueError) as e:
            log.warning('Person ID %s not resolved: %s', person_id, e)
            return None

    def person_label(self, person_id):
        if person_id in self.people_cache:
            return self.people_cache[person_id]
        return '(unknown person, ID %s)' % person_id

    def rows(self):
        """Every item as the same row assets._clean_row gives the CSV path."""
        person_internal = self.mapping.get(PERSON_HEADER)
        rows = []
        for item in self.items:
            f = item.get('fields', {})
            raw = {}
            for header, internal in self.mapping.items():
                if header == PERSON_HEADER:
                    continue
                raw[header] = f.get(internal)
            if person_internal:
                value = f.get(person_internal + 'LookupId')
                if isinstance(value, dict):
                    value = value.get('LookupId')
                raw[PERSON_HEADER] = self.person_label(str(value)) if value not in (None, '') else ''
            rows.append(asset_data._clean_row(raw, self.tz, int(item['id'])))
        return rows

    def date_check(self):
        """How many date values are local midnight in the site's time zone,
        which is what the CSV export holds. Counts only, no values."""
        total = midnight = 0
        for item in self.items:
            f = item.get('fields', {})
            for header in DATE_HEADERS:
                value = f.get(self.mapping.get(header, ''))
                if not value:
                    continue
                total += 1
                try:
                    local = datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(self.tz)
                except ValueError:
                    continue
                if (local.hour, local.minute) == (0, 0):
                    midnight += 1
        return total, midnight

    def fetch(self):
        self.read_site()
        self.find_list()
        self.read_columns()
        self.read_items()
        self.read_schema()
        self.resolve_people()
        return self.rows()


# ---------------------------------------------------------------------------
# The data source the app uses
# ---------------------------------------------------------------------------

class SharePointSource:
    """Keeps the last good copy of the list and refreshes it every
    `refresh_seconds`. Pages never wait for a refresh once a first copy
    exists: one request starts it in the background and everyone keeps the
    current copy until it finishes. A failed refresh keeps the last good copy
    and marks it stale."""

    def __init__(self, settings, tz_name, client=None, clock=time.monotonic, background=True):
        self.settings = settings
        self.tz = ZoneInfo(tz_name)
        self.client = client or GraphClient(TokenProvider(settings))
        self.clock = clock
        self.background = background
        self.people_cache = {}
        self._data = None
        self._stale = None
        self._last_error = None
        self._next_due = 0.0
        self._refresh_lock = threading.Lock()
        self._state_lock = threading.Lock()

    @classmethod
    def from_env(cls, tz_name, env=None):
        settings = load_settings(env)
        load_certificate(settings['cert_path'], settings['cert_password'])
        return cls(settings, tz_name)

    def load(self):
        now = self.clock()
        with self._state_lock:
            data, due = self._data, now >= self._next_due
        if data is None:
            # Nothing to show yet: this request waits for the first fetch.
            # After a failure, the same error is shown until the retry is due,
            # rather than every page view trying (and failing) again.
            with self._refresh_lock:
                with self._state_lock:
                    have_data = self._data is not None
                    wait = self._last_error is not None and self.clock() < self._next_due
                if not have_data:
                    if wait:
                        raise SourceError(self._last_error)
                    self._refresh()
                    if self._data is None:
                        raise SourceError(self._last_error)
            return self._view()
        if due and self._refresh_lock.acquire(blocking=False):
            if self.background:
                threading.Thread(target=self._refresh_and_release, daemon=True).start()
            else:
                self._refresh_and_release()
        return self._view()

    def _refresh_and_release(self):
        try:
            self._refresh()
        finally:
            self._refresh_lock.release()

    def _refresh(self):
        started = self.clock()
        try:
            reader = ListReader(self.client, self.settings, self.tz, self.people_cache)
            rows = reader.fetch()
            data = {
                'fields': reader.fields,
                'assets': rows,
                'loaded_at': datetime.now(self.tz),
                'source': 'SharePoint: %s' % self.settings['list_name'],
                'live': True,
            }
            with self._state_lock:
                self._data = data
                self._stale = None
                self._last_error = None
                self._next_due = started + self.settings['refresh_seconds']
            log.info('SharePoint refresh OK: %d items', len(rows))
        except Exception as e:
            reason = str(e) if isinstance(e, SourceError) else (
                'unexpected problem while reading the list (%s). Details are in the log.'
                % type(e).__name__)
            if isinstance(e, SourceError):
                log.error('SharePoint refresh failed: %s', reason)
            else:
                log.exception('SharePoint refresh failed: %s', reason)
            with self._state_lock:
                self._last_error = reason
                self._next_due = started + min(RETRY_AFTER_FAILURE_SECONDS,
                                               self.settings['refresh_seconds'])
                if self._data is not None:
                    self._stale = {
                        'since': self._data['loaded_at'],
                        'failed_at': datetime.now(self.tz),
                        'reason': reason,
                    }

    def _view(self):
        with self._state_lock:
            return dict(self._data, stale=self._stale)


# ---------------------------------------------------------------------------
# python -m sharepoint --check
# ---------------------------------------------------------------------------

def run_check(env=None, out=print, client_factory=None):
    """Run every step once and print a report that is safe to paste into a
    chat: no secrets, no item contents, GET requests only. Returns 0 when
    every step passed, 1 otherwise."""
    env = os.environ if env is None else env
    steps = [
        '1. Settings', '2. Certificate', '3. Sign-in', '4. Site', '5. List',
        '6. Columns', '7. Items', '8. Choices and colors', '9. Check Out By/To people',
        '10. Dates',
    ]
    done = []

    def ok(step, *lines):
        done.append(step)
        out('[OK]     %s' % step)
        for line in lines:
            out('         %s' % line)

    def fail(step, reason):
        out('[FAILED] %s' % step)
        out('         %s' % reason)
        for later in steps[steps.index(step) + 1:]:
            out('[--]     %s: not run, because step %s failed' % (later, step.split('.')[0]))
        out('')
        out('RESULT: stopped at %s.' % step)
        return 1

    out('Asset dashboard: SharePoint connection check')
    out('Reads .env, ignores ASSET_SOURCE, makes GET requests only, prints no secrets '
        'and no item contents.')
    out('')

    tz_name = (env.get('SITE_TIMEZONE') or 'America/Los_Angeles').strip()
    try:
        settings = load_settings(env)
        tz = ZoneInfo(tz_name)
    except ConfigError as e:
        return fail(steps[0], str(e))
    except Exception:
        return fail(steps[0], 'SITE_TIMEZONE is not a time zone name Python knows. Use a '
                              'name like America/Los_Angeles.')
    ok(steps[0], 'All of %s are set.' % ', '.join(REQUIRED_SETTINGS),
       'SP_REFRESH_SECONDS: %d. SITE_TIMEZONE: %s.' % (settings['refresh_seconds'], tz_name))

    try:
        cert = load_certificate(settings['cert_path'], settings['cert_password'])
    except ConfigError as e:
        return fail(steps[1], str(e))
    expires = cert['expires']
    days_left = (expires - datetime.now(timezone.utc)).days
    lines = ['Opened with the password. SHA-1 thumbprint (compare with the app '
             'registration): %s' % cert['thumbprint_sha1'],
             'Expires %d/%d/%d (%d days from now).' % (expires.month, expires.day,
                                                       expires.year, days_left)]
    if days_left < 0:
        return fail(steps[1], 'The certificate expired %d days ago. Ask IT for a new one.'
                    % -days_left)
    if days_left < 30:
        lines.append('WARNING: expires in under 30 days. Ask IT for a replacement.')
    ok(steps[1], *lines)

    if client_factory:
        client = client_factory(settings)
    else:
        client = GraphClient(TokenProvider(settings))
    try:
        token = client.tokens.token(GRAPH_SCOPE)
    except SourceError as e:
        return fail(steps[2], str(e))
    roles = token_roles(token)
    if roles is None:
        role_line = 'Permissions in the token: could not be read.'
    elif roles:
        role_line = 'Permissions in the token: %s' % ', '.join(roles)
    else:
        role_line = ('Permissions in the token: none. IT needs to add an application '
                     'permission (for example Sites.Selected) and grant admin consent.')
    ok(steps[2], 'Signed in to Microsoft Graph as the app.', role_line)

    reader = ListReader(client, settings, tz)
    try:
        site = reader.read_site()
    except SourceError as e:
        return fail(steps[3], str(e))
    ok(steps[3], 'Name: %s' % site.get('displayName'), 'URL: %s' % site.get('webUrl'))

    try:
        reader.find_list()
    except SourceError as e:
        return fail(steps[4], str(e))
    ok(steps[4], 'Found "%s".' % reader.list.get('displayName'))

    try:
        reader.read_columns()
    except SourceError as e:
        return fail(steps[5], str(e))
    lines = ['%d columns (display name | internal name | type):' % len(reader.columns)]
    for col in reader.columns:
        lines.append('  %s | %s | %s' % (col.get('displayName'), col.get('name'), column_type(col)))
    if reader.missing_columns:
        lines.append('WARNING: the dashboard uses these columns but the list has none by '
                     'that name: %s. They will show blank.' % ', '.join(reader.missing_columns))
    else:
        lines.append('All %d columns the dashboard uses were found.' % len(asset_data.COLUMNS))
    ok(steps[5], *lines)

    try:
        reader.read_items()
    except SourceError as e:
        return fail(steps[6], str(e))
    ok(steps[6], '%d items, read in %d page(s).' % (len(reader.items), reader.item_pages))

    reader.read_schema()
    colored = sorted(f['label'] for f in reader.fields.values() if f.get('colors'))
    if reader.schema_source == 'SchemaXml':
        ok(steps[7], 'From SharePoint SchemaXml. Columns with pill colors: %s.'
           % (', '.join(colored) or 'none'))
    else:
        ok(steps[7], 'FALLBACK: choices from Graph, pills in the default style.',
           'Reason: %s' % reader.schema_fallback_reason)

    resolved, unresolved = reader.resolve_people()
    route = {'graph': 'Graph, User Information List', 'rest': 'SharePoint REST',
             'cached': 'cache', 'none needed': 'none needed (no person IDs in the list)',
             None: 'none available'}[reader.people_route]
    lines = ['Resolved %d, not resolved %d. Route: %s.' % (resolved, len(unresolved), route)]
    if unresolved:
        lines.append('Not resolved, by person ID: %s. These show as "(unknown person, ID n)".'
                     % ', '.join(unresolved))
    ok(steps[8], *lines)

    total, midnight = reader.date_check()
    if total and midnight == total:
        line = 'All %d date values are midnight in %s, the same as the CSV export.' % (total, tz_name)
    else:
        line = ('%d of %d date values are midnight in %s. The CSV export has them all at '
                'midnight, so tell the developer.' % (midnight, total, tz_name))
    ok(steps[9], line)

    try:
        reader.rows()
    except Exception as e:
        out('')
        out('RESULT: every step passed, but turning the items into rows failed (%s).'
            % type(e).__name__)
        return 1
    out('')
    out('RESULT: every step passed.')
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ['--check']:
        print('Usage: python -m sharepoint --check')
        return 2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
                encoding='utf-8')
    # The check prints its own report; library chatter would only add noise.
    logging.basicConfig(level=logging.CRITICAL)
    return run_check()


if __name__ == '__main__':
    sys.exit(main())
