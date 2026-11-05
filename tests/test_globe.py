"""The Global View page (prompt 14): sites, readiness and Unplaced, worked
out in Python, and the page itself. All assets here are made up."""
import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import fleet
import globe
from test_riga import history, riga, uploaded, workbook, workbook_bytes  # noqa: F401

MAPPING = {'Test Aircraft': 'Aircraft', 'Test GCS': 'Ground Control Station',
           'Test Engine': 'Engine', 'Test Kit': 'Support'}
SITES = {
    'sites': [
        {'name': 'Alpha Town', 'lat': 34.7, 'lon': -86.6, 'locations': ['Alpha Hangar', 'Alpha Lab']},
        {'name': 'Bravo City', 'lat': 35.3, 'lon': -120.7, 'locations': ['Bravo Field']},
    ],
    'not_places': ['Roving Support'],
    'riga': {'name': 'Riga', 'lat': 56.95, 'lon': 24.11},
}
NO_RIGA = {'state': 'none'}


def asset(serial, locations, condition='FMC', asset_type='Test Aircraft'):
    return {'serial_number': serial, 'asset_type': asset_type, 'condition': condition,
            'location': list(locations)}


def site(result, name):
    (s,) = [s for s in result['sites'] if s['name'] == name]
    return s


def line(rows, location):
    (r,) = [r for r in rows if r['location'] == location]
    return r


# --- The numbers -----------------------------------------------------------------

def test_sites_get_counts_and_readiness_and_two_locations_count_once_at_the_site():
    assets = [asset('T-1', ['Alpha Hangar', 'Alpha Lab']),          # both at Alpha Town
              asset('T-2', ['Alpha Hangar'], 'NMC'),
              asset('T-3', ['Alpha Lab'], 'PMC'),
              asset('T-4', ['Bravo Field'])]
    result = globe.globe_data(assets, MAPPING, NO_RIGA, SITES)
    alpha = site(result, 'Alpha Town')
    assert (alpha['count'], alpha['pct'], alpha['band']) == (3, 33.3, 'bad')
    assert (line(alpha['lines'], 'Alpha Hangar')['count'], line(alpha['lines'], 'Alpha Lab')['count']) == (2, 2)
    assert line(alpha['lines'], 'Alpha Hangar')['pct'] == 50.0
    bravo = site(result, 'Bravo City')
    assert (bravo['count'], bravo['pct'], bravo['band']) == (1, 100.0, 'good')
    assert [s['name'] for s in result['sites']] == ['Alpha Town', 'Bravo City']   # most assets first
    assert result['unplaced'] == []


def test_the_percent_text_rounds_as_fleet_overview_does():
    # 161 ready of 200 is 80.5%: Fleet Overview writes it as 80%, so the globe does too.
    assets = [asset('T-%d' % i, ['Bravo Field'], 'FMC' if i < 161 else 'NMC') for i in range(200)]
    bravo = site(globe.globe_data(assets, MAPPING, NO_RIGA, SITES), 'Bravo City')
    assert (bravo['pct'], bravo['pct_text'], bravo['band']) == (80.5, '80%', 'good')
    empty = site(globe.globe_data([asset('E-1', ['Bravo Field'], 'FMC', 'Test Engine')],
                                  MAPPING, NO_RIGA, SITES), 'Bravo City')
    assert empty['pct_text'] == '\u2013'


def test_engines_are_left_out_of_readiness_but_counted():
    assets = [asset('T-1', ['Bravo Field']),
              asset('E-1', ['Bravo Field'], 'NMC', 'Test Engine'),
              asset('E-2', ['Bravo Field'], 'NMC', 'Test Engine')]
    bravo = site(globe.globe_data(assets, MAPPING, NO_RIGA, SITES), 'Bravo City')
    assert (bravo['count'], bravo['pct']) == (3, 100.0)
    only_engines = [asset('E-3', ['Alpha Lab'], 'FMC', 'Test Engine')]
    alpha = site(globe.globe_data(only_engines, MAPPING, NO_RIGA, SITES), 'Alpha Town')
    assert (alpha['count'], alpha['pct'], alpha['band']) == (1, None, 'none')


def test_unknown_not_a_place_and_blank_locations_go_to_unplaced():
    assets = [asset('T-1', ['Customer Site X']), asset('T-2', ['Customer Site X']),
              asset('T-3', ['Roving Support']), asset('T-4', []), asset('T-5', []),
              asset('T-6', ['Alpha Hangar', 'Customer Site X'])]       # placed, and unplaced too
    result = globe.globe_data(assets, MAPPING, NO_RIGA, SITES)
    rows = result['unplaced']
    assert (line(rows, 'Customer Site X')['count'], line(rows, 'Customer Site X')['reason']) == \
        (3, globe.NOT_IN_FILE)
    assert (line(rows, 'Roving Support')['count'], line(rows, 'Roving Support')['reason']) == \
        (1, globe.NOT_A_PLACE)
    blank = line(rows, '(blank)')
    assert (blank['count'], blank['reason'], blank['href']) == (2, globe.BLANK, '/?location=%28none%29')
    assert site(result, 'Alpha Town')['count'] == 1
    # Nothing disappears: every asset is at a site or under Unplaced.
    shown = {a['serial_number'] for a in assets
             if any(globe.norm(x) in {'alpha hangar', 'alpha lab', 'bravo field'} for x in a['location'])}
    assert shown | {'T-1', 'T-2', 'T-3', 'T-4', 'T-5'} == {a['serial_number'] for a in assets}


def test_matching_ignores_case_and_spaces_at_the_ends():
    assets = [asset('T-1', ['  alpha HANGAR ']), asset('T-2', ['roving support'])]
    result = globe.globe_data(assets, MAPPING, NO_RIGA, SITES)
    alpha = site(result, 'Alpha Town')
    assert alpha['count'] == 1 and alpha['lines'][0]['location'] == '  alpha HANGAR '
    assert line(result['unplaced'], 'roving support')['reason'] == globe.NOT_A_PLACE


def test_links_are_url_encoded():
    assets = [asset('T-1', ['Alpha Lab']), asset('T-2', ['R&D / Bay #2'])]
    result = globe.globe_data(assets, MAPPING, NO_RIGA, SITES)
    assert site(result, 'Alpha Town')['lines'][0]['href'] == '/?location=Alpha%20Lab'
    assert line(result['unplaced'], 'R&D / Bay #2')['href'] == '/?location=R%26D%20%2F%20Bay%20%232'
    assert globe.overview_link(riga=True) == '/?site=riga'
    assert globe.overview_link('Hall 1', riga=True) == '/?site=riga&location=Hall%201'


def test_a_close_smaller_site_collapses_and_a_far_one_does_not():
    near = dict(SITES, sites=SITES['sites'] + [
        {'name': 'Alpha Annex', 'lat': 34.9, 'lon': -86.0, 'locations': ['Annex']},
        {'name': 'Far Port', 'lat': 51.5, 'lon': -0.1, 'locations': ['Far Dock']}])
    assets = [asset('T-1', ['Alpha Hangar']), asset('T-2', ['Alpha Hangar']),
              asset('T-3', ['Annex']), asset('T-4', ['Bravo Field']), asset('T-5', ['Far Dock'])]
    result = globe.globe_data(assets, MAPPING, NO_RIGA, near)
    # Bravo City is 28 degrees from Alpha Town: close enough for the lists to overlap on screen.
    assert [(s['name'], s['collapsed']) for s in result['sites']] == [
        ('Alpha Town', False), ('Alpha Annex', True), ('Bravo City', True), ('Far Port', False)]


def test_riga_is_a_point_with_a_good_workbook_and_a_note_without():
    state = {'state': 'ok', 'families': MAPPING,
             'data': {'assets': [asset('R-1', ['Hall 1']), asset('R-2', ['Hall 2'], 'NMC'),
                                 asset('R-3', ['Hall 2'], 'NMC', 'Test Engine')]}}
    result = globe.globe_data([], MAPPING, state, SITES)
    riga_site = site(result, 'Riga')
    assert (riga_site['count'], riga_site['pct'], riga_site['href']) == (3, 50.0, '/?site=riga')
    assert line(riga_site['lines'], 'Hall 2')['href'] == '/?site=riga&location=Hall%202'
    assert result['riga_note'] is None
    for kind in ('none', 'off', 'mapping', 'unreadable'):
        result = globe.globe_data([], MAPPING, {'state': kind}, SITES)
        assert [s['name'] for s in result['sites']] == [] and 'Riga has no point' in result['riga_note']
    # With no place for Riga in the file, its assets are listed under Unplaced instead.
    result = globe.globe_data([], MAPPING, state, dict(SITES, riga=None))
    assert line(result['unplaced'], 'Riga workbook')['count'] == 3


# --- location_sites.json -----------------------------------------------------------

def test_the_committed_file_is_valid():
    sites = globe.read_sites(globe.LOCATION_SITES_PATH)
    assert {s['name'] for s in sites['sites']} == {'Huntsville', 'San Luis Obispo'}
    assert sites['riga']['name'] == 'Riga'


@pytest.mark.parametrize('content, reason', [
    ('not json', 'it is not valid JSON'),
    ('{"places": []}', 'it has no list of "sites"'),
    ('{"sites": [{"name": "A", "lat": 1, "lon": 2, "locations": ["X"]},'
     ' {"name": "B", "lat": 3, "lon": 4, "locations": [" x "]}]}',
     'the Location x is in two places: the site A and the site B'),
    ('{"sites": [{"name": "A", "lat": 91, "lon": 2, "locations": ["X"]}]}', 'the site A has no usable lat'),
    ('{"sites": [{"name": "A", "lat": 1, "lon": 2, "locations": ["X"]}], "not_places": ["X"]}',
     'the Location X is in two places: the site A and not_places'),
])
def test_a_bad_file_is_refused_with_its_reason(tmp_path, content, reason):
    path = tmp_path / 'location_sites.json'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match=re.escape(reason)):
        globe.read_sites(str(path))


# --- The page ----------------------------------------------------------------------

@pytest.fixture
def sites_file(tmp_path, monkeypatch):
    path = tmp_path / 'location_sites.json'
    path.write_text(json.dumps(SITES), encoding='utf-8')
    site_map = globe.SiteMap(str(path))
    monkeypatch.setattr(dashboard, 'LOCATION_SITES', site_map)
    return path


class FakeSource:
    def __init__(self, assets):
        self.assets = assets

    def load(self):
        return {'assets': self.assets, 'fields': {}, 'source': 'made-up export',
                'loaded_at': datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo('America/Los_Angeles')),
                'live': False}


@pytest.fixture
def made_up(monkeypatch, sites_file, riga, history):
    monkeypatch.setattr(dashboard, 'SOURCE', FakeSource([
        asset('T-1', ['Alpha Hangar']), asset('T-2', ['Customer Site X']), asset('T-3', [])]))
    return dashboard.app.test_client()


def test_the_page_loads_is_in_the_menu_and_uses_local_files_only(made_up):
    resp = made_up.get('/globe')
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert '<a href="/globe" class="active" aria-current="page">Global View</a>' in html
    nav = html.split('<nav class="side-links">')[1].split('</nav>')[0]
    assert nav.index('Fleet Overview') < nav.index('Global View')
    scripts = re.findall(r'<script[^>]*\ssrc="([^"]+)"', html)
    assert scripts == ['/static/vendor/globe.gl-2.46.2.min.js']
    assert '/static/vendor/black_marble_2016_3600x1800.jpg' in html
    assert 'http://' not in html and 'https://' not in html
    assert 'Data from <strong>made-up export</strong>' in html


def test_the_page_carries_the_numbers_and_the_unplaced_panel(made_up):
    html = made_up.get('/globe').get_data(as_text=True)
    numbers = json.loads(re.search(r'var numbers = (\{.*?\});\n', html).group(1))
    assert [(s['name'], s['count']) for s in numbers['sites']] == [('Alpha Town', 1)]
    unplaced = html.split('id="unplaced"')[1].split('</aside>')[0]
    assert '/?location=Customer%20Site%20X' in unplaced and '/?location=%28none%29' in unplaced
    assert 'No Riga workbook has been uploaded yet' in html
    # The table the page falls back to without WebGL holds the same numbers.
    table = html.split('id="sites-table"')[1].split('</table>')[0]
    assert 'Alpha Town' in table and '/?location=Alpha%20Hangar' in table


def test_riga_on_the_page_with_a_good_workbook(uploaded, sites_file, history):
    html = dashboard.app.test_client().get('/globe').get_data(as_text=True)
    numbers = json.loads(re.search(r'var numbers = (\{.*?\});\n', html).group(1))
    (riga_site,) = [s for s in numbers['sites'] if s['name'] == 'Riga']
    assert riga_site['href'] == '/?site=riga' and riga_site['count'] > 0
    assert numbers['riga_note'] is None and 'id="riga-note"' not in html


@pytest.mark.parametrize('content, words', [
    (None, 'there is no location_sites.json next to the app'),
    ('{oops', 'location_sites.json could not be used: it is not valid JSON'),
    ('{"sites": [{"name": "A", "lat": 1, "lon": 2, "locations": ["X"]},'
     ' {"name": "B", "lat": 3, "lon": 4, "locations": ["X"]}]}',
     'the Location X is in two places: the site A and the site B'),
])
def test_a_bad_or_missing_file_is_on_the_page_and_logged_once(tmp_path, monkeypatch, made_up,
                                                              caplog, content, words):
    path = tmp_path / 'other' / 'location_sites.json'
    path.parent.mkdir()
    if content is not None:
        path.write_text(content, encoding='utf-8')
    monkeypatch.setattr(dashboard, 'LOCATION_SITES', globe.SiteMap(str(path)))
    caplog.set_level(logging.INFO)
    for _ in range(3):
        resp = made_up.get('/globe')
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'The location file (location_sites.json) could not be used' in html and words in html
    errors = [r for r in caplog.records if r.name == 'asset_management.globe' and r.levelno == logging.ERROR]
    assert len(errors) == 1 and words in errors[0].getMessage()
    unplaced = html.split('id="unplaced"')[1].split('</aside>')[0]
    assert 'Alpha Hangar' in unplaced                     # nothing disappears


def test_the_committed_csv_places_huntsville_and_san_luis_obispo(riga, history):
    html = dashboard.app.test_client().get('/globe').get_data(as_text=True)
    numbers = json.loads(re.search(r'var numbers = (\{.*?\});\n', html).group(1))
    names = [s['name'] for s in numbers['sites']]
    assert names[:2] == ['Huntsville', 'San Luis Obispo']
    assert fleet.NO_LOCATION not in names
