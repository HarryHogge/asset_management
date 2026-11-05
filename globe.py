"""The Global View page's numbers: where each Location is, and the asset
counts and readiness at each place.

Places come from location_sites.json, which lists sites, each with a name,
a latitude and longitude, and the Location values found there. A Location is
matched by its text, ignoring case and spaces at the ends. Riga's place is in
the file too, but Riga's assets come from the uploaded workbook, so they are
all at Riga whatever their own Location says.

Every US asset is shown somewhere: at a site, or under Unplaced when its
Location is not in the file, is listed in not_places, or is blank.
"""
import json
import logging
import math
import os
import threading
from urllib.parse import quote

import fleet

log = logging.getLogger('asset_management.globe')

LOCATION_SITES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'location_sites.json')

# A place's readiness % -> its colour on the globe: at or above GOOD_PCT is
# good, at or above WARN_PCT is warn, below that bad; None is neutral.
GOOD_PCT = 80
WARN_PCT = 50

# A site this close (in degrees of arc) to a site with more assets shows only
# its header line, and its list opens on hover, so the lists never sit on top
# of each other. 40 degrees, because a whole list is about as tall on screen
# as 30 degrees of the globe: Huntsville and San Luis Obispo, 28 degrees
# apart, overlapped in the browser check at 8.
CLOSE_DEGREES = 40

# Why a line is under Unplaced.
NOT_IN_FILE = 'not in location_sites.json yet'
NOT_A_PLACE = 'not a place'
BLANK = 'no Location'


def norm(text):
    """How Locations are matched: ignoring case and spaces at the ends."""
    return (text or '').strip().casefold()


def band(pct):
    if pct is None:
        return 'none'
    if pct >= GOOD_PCT:
        return 'good'
    if pct >= WARN_PCT:
        return 'warn'
    return 'bad'


def overview_link(location=None, riga=False):
    """The Fleet Overview address for a Location, URL-encoded, or for Riga."""
    parts = ['site=riga'] if riga else []
    if location is not None:
        parts.append('location=' + quote(location, safe=''))
    return '/?' + '&'.join(parts) if parts else '/'


def arc_degrees(a, b):
    """The angle between two places seen from the Earth's centre, in degrees."""
    la1, lo1, la2, lo2 = map(math.radians, (a['lat'], a['lon'], b['lat'], b['lon']))
    c = (math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2))
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


# ---------------------------------------------------------------------------
# location_sites.json
# ---------------------------------------------------------------------------

def _place(entry, what):
    if not isinstance(entry, dict):
        raise ValueError('%s is not a set of name, lat and lon' % what)
    name = entry.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('%s has no name' % what)
    for key, limit in (('lat', 90), ('lon', 180)):
        value = entry.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value) or abs(value) > limit:
            raise ValueError('the site %s has no usable %s (a number from -%d to %d)'
                             % (name, key, limit, limit))
    return {'name': name.strip(), 'lat': float(entry['lat']), 'lon': float(entry['lon'])}


def read_sites(path):
    """Read location_sites.json. Returns {'sites': [{name, lat, lon,
    locations}], 'not_places': [...], 'riga': {name, lat, lon} or None}.
    Raises OSError if it cannot be read and ValueError if it is not in the
    expected shape, naming the problem."""
    with open(path, encoding='utf-8') as f:
        try:
            data = json.load(f)
        except ValueError:
            raise ValueError('it is not valid JSON') from None
    if not isinstance(data, dict) or not isinstance(data.get('sites'), list):
        raise ValueError('it has no list of "sites"')
    seen = {}

    def claim(location, owner):
        if not isinstance(location, str) or not location.strip():
            raise ValueError('%s has a blank or non-text Location' % owner)
        key = norm(location)
        if key in seen:
            raise ValueError('the Location %s is in two places: %s and %s'
                             % (location.strip(), seen[key], owner))
        seen[key] = owner

    sites = []
    for i, entry in enumerate(data['sites'], start=1):
        site = _place(entry, 'site %d' % i)
        locations = entry.get('locations')
        if not isinstance(locations, list) or not locations:
            raise ValueError('the site %s has no list of "locations"' % site['name'])
        for location in locations:
            claim(location, 'the site %s' % site['name'])
        site['locations'] = [x.strip() for x in locations]
        sites.append(site)
    not_places = data.get('not_places', [])
    if not isinstance(not_places, list):
        raise ValueError('"not_places" is not a list')
    for location in not_places:
        claim(location, 'not_places')
    riga = data.get('riga')
    if riga is not None:
        riga = _place(riga, '"riga"')
    return {'sites': sites, 'not_places': [x.strip() for x in not_places], 'riga': riga}


EMPTY = {'sites': [], 'not_places': [], 'riga': None}


class SiteMap:
    """Reads location_sites.json at each use, so an edit shows without a
    restart. A problem is logged once, and again only when it changes."""

    def __init__(self, path=LOCATION_SITES_PATH):
        self.path = path
        self._state = None
        self._lock = threading.Lock()

    def load(self):
        """(sites, problem). With a problem no place is known, so every asset
        is Unplaced, and `problem` says why in a sentence for the page."""
        name = os.path.basename(self.path)
        problem = None
        try:
            sites = read_sites(self.path)
        except FileNotFoundError:
            sites, problem = EMPTY, 'there is no %s next to the app' % name
        except OSError as e:
            sites, problem = EMPTY, '%s could not be opened (%s)' % (name, type(e).__name__)
        except ValueError as e:
            sites, problem = EMPTY, '%s could not be used: %s' % (name, e)
        with self._lock:
            if problem != self._state:
                self._state = problem
                if problem:
                    log.error('Location sites: every asset shows as Unplaced on the Global View, '
                              'because %s.', problem)
                else:
                    log.info('Location sites: %d site(s) read from %s.', len(sites['sites']), name)
        return sites, problem


# ---------------------------------------------------------------------------
# The numbers
# ---------------------------------------------------------------------------

def _numbers(assets, mapping):
    """Asset count (engines included) and the headline readiness %, engines
    left out, as on Fleet Overview."""
    pct = fleet.fleet_readiness(assets, mapping)['overall']['pct']
    # The text is made here, as Fleet Overview writes it, so the globe and the
    # table round the same way (80.5 shows as 80% on both).
    text = '\u2013' if pct is None else '%.0f%%' % pct
    return {'count': len(assets), 'pct': pct, 'pct_text': text, 'band': band(pct)}


def _location_lines(assets, mapping, riga=False):
    """One line per Location value, by its exact text, most assets first. An
    asset with several Locations is on each of their lines."""
    by_value = {}
    for a in assets:
        for value in a['location']:
            by_value.setdefault(value, []).append(a)
    lines = []
    for value, rows in by_value.items():
        line = {'location': value, 'href': overview_link(value, riga=riga)}
        line.update(_numbers(rows, mapping))
        lines.append(line)
    lines.sort(key=lambda r: (-r['count'], r['location'].casefold()))
    return lines


def riga_note(state):
    """Why Riga has no point, in one sentence, or None."""
    kind = state.get('state')
    if kind == 'ok':
        return None
    if kind == 'none':
        return 'No Riga workbook has been uploaded yet, so Riga has no point on the globe.'
    if kind == 'off':
        return ('The folder for the Riga workbook could not be created when the dashboard started, '
                'so Riga has no point on the globe. The reason is in the dashboard log.')
    if kind == 'mapping':
        return ('The Riga mapping file (riga_mapping.json) could not be read, so Riga has no point '
                'on the globe. The reason is in the dashboard log.')
    return 'The Riga workbook could not be read, so Riga has no point on the globe. ' \
           'The reason is in the dashboard log.'


def globe_data(us_assets, us_mapping, riga_state, sites):
    """The page's numbers: {'sites': [...], 'unplaced': [...], 'riga_note'}.

    Each site: name, lat, lon, count (each asset once), pct and band (engines
    left out of the %), href, and one line per Location there. Unplaced: one
    line per Location value not placed, and one for assets with no Location,
    each with its count, why it is there, and a link to Fleet Overview."""
    where = {}
    for site in sites['sites']:
        for location in site['locations']:
            where[norm(location)] = site['name']
    not_places = {norm(x) for x in sites['not_places']}

    at_site = {s['name']: [] for s in sites['sites']}
    unplaced = {}
    blank = []
    for a in us_assets:
        if not a['location']:
            blank.append(a)
            continue
        here = set()
        for value in a['location']:
            name = where.get(norm(value))
            if name is not None:
                here.add(name)
            else:
                reason = NOT_A_PLACE if norm(value) in not_places else NOT_IN_FILE
                unplaced.setdefault((value, reason), []).append(a)
        for name in here:
            at_site[name].append(a)

    out_sites = []
    for site in sites['sites']:
        rows = at_site[site['name']]
        if not rows:
            continue
        keys = {norm(x) for x in site['locations']}
        lines = [line for line in _location_lines(rows, us_mapping) if norm(line['location']) in keys]
        entry = {'name': site['name'], 'lat': site['lat'], 'lon': site['lon'], 'kind': 'us',
                 'href': None, 'lines': lines}
        entry.update(_numbers(rows, us_mapping))
        out_sites.append(entry)

    note = riga_note(riga_state)
    riga_unplaced = None
    if note is None:
        rows = riga_state['data']['assets']
        mapping = riga_state.get('families') or {}
        if sites['riga'] is None:
            riga_unplaced = {'location': 'Riga workbook', 'reason': 'Riga has no place in '
                             'location_sites.json', 'href': overview_link(riga=True)}
            riga_unplaced.update(_numbers(rows, mapping))
        else:
            entry = dict(sites['riga'], kind='riga', href=overview_link(riga=True),
                         lines=_location_lines(rows, mapping, riga=True))
            entry.update(_numbers(rows, mapping))
            out_sites.append(entry)
    out_sites.sort(key=lambda s: (-s['count'], s['name'].casefold()))
    for i, site in enumerate(out_sites):
        site['collapsed'] = any(arc_degrees(site, bigger) < CLOSE_DEGREES for bigger in out_sites[:i])

    out_unplaced = []
    for (value, reason), rows in unplaced.items():
        line = {'location': value, 'reason': reason, 'href': overview_link(value)}
        line.update(_numbers(rows, us_mapping))
        out_unplaced.append(line)
    out_unplaced.sort(key=lambda r: (-r['count'], r['location'].casefold()))
    if blank:
        line = {'location': '(blank)', 'reason': BLANK, 'href': overview_link(fleet.NO_LOCATION)}
        line.update(_numbers(blank, us_mapping))
        out_unplaced.append(line)
    if riga_unplaced:
        out_unplaced.append(riga_unplaced)
    return {'sites': out_sites, 'unplaced': out_unplaced, 'riga_note': note}
