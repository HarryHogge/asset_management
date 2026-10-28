"""The Fleet Overview page's numbers: asset families, readiness, and the
once-a-day readiness history behind the trend chart.

Families come from asset_families.json, which maps each Asset Type, by its
exact text, to Aircraft, Ground Control Station, Payload or Support. Any type
the file does not name, a blank one included, is Unmapped. Nothing is ever
guessed into Support.
"""
import json
import logging
import os
import threading
from datetime import date, timedelta

import assets as asset_data

log = logging.getLogger('asset_management.fleet')

FAMILIES = ['Aircraft', 'Ground Control Station', 'Payload', 'Support']
UNMAPPED = 'Unmapped'
ALL_FAMILIES = FAMILIES + [UNMAPPED]
# The families with their own card and table on the page.
MAIN_FAMILIES = ['Aircraft', 'Ground Control Station', 'Payload']

ASSET_FAMILIES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'asset_families.json')

# The value of ?location= that means "assets with no location".
NO_LOCATION = '(none)'


# ---------------------------------------------------------------------------
# Families
# ---------------------------------------------------------------------------

def _no_repeats(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError('it names the Asset Type %s twice' % key)
        seen[key] = value
    return seen


def read_families(path):
    """Read asset_families.json: {Asset Type: family}. Raises OSError if it
    cannot be read and ValueError if it is not in the expected shape."""
    with open(path, encoding='utf-8') as f:
        try:
            data = json.load(f, object_pairs_hook=_no_repeats)
        except ValueError as e:
            if 'twice' in str(e):
                raise
            raise ValueError('it is not valid JSON') from None
    if not isinstance(data, dict) or not data:
        raise ValueError('it does not hold a set of Asset Types')
    for asset_type, family in data.items():
        if not asset_type.strip():
            raise ValueError('it has a blank Asset Type')
        if family not in FAMILIES:
            raise ValueError('Asset Type %s has the family %r, which is not one of %s'
                             % (asset_type, family, ', '.join(FAMILIES)))
    return data


class FamilyMap:
    """Reads asset_families.json at each use, so an edit shows without a
    restart. A problem is logged once, and again only when it changes."""

    def __init__(self, path=ASSET_FAMILIES_PATH):
        self.path = path
        self._state = None
        self._lock = threading.Lock()

    def load(self):
        """(mapping, problem). With a problem the mapping is empty, so every
        type is Unmapped, and `problem` says why in a sentence for the log."""
        name = os.path.basename(self.path)
        problem = None
        try:
            mapping = read_families(self.path)
        except FileNotFoundError:
            mapping, problem = {}, 'there is no %s next to the app' % name
        except OSError as e:
            mapping, problem = {}, '%s could not be opened (%s)' % (name, type(e).__name__)
        except ValueError as e:
            mapping, problem = {}, '%s could not be used: %s' % (name, e)
        with self._lock:
            if problem != self._state:
                self._state = problem
                if problem:
                    log.error('Asset families: every asset shows as Unmapped, because %s.',
                              problem)
                else:
                    log.info('Asset families: %d Asset Types read from %s.', len(mapping), name)
        return mapping, problem


def family_of(asset_type, mapping):
    """Exact text only: near-identical names in the list are different items."""
    return mapping.get(asset_type, UNMAPPED) if asset_type else UNMAPPED


def unmapped_types(assets, mapping):
    """[(Asset Type, rows)] for the types the mapping does not name, most rows
    first. A blank type is listed as ''."""
    counts = {}
    for a in assets:
        if family_of(a['asset_type'], mapping) == UNMAPPED:
            counts[a['asset_type']] = counts.get(a['asset_type'], 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------

# Material Condition -> (key, readiness label). Anything else that is filled
# in counts as 'other', so a new choice added to the list is shown, not lost.
CONDITIONS = {
    'FMC': ('fmc', 'Ready'),
    'PMC': ('pmc', 'Limited'),
    'NMC': ('nmc', 'Not Ready'),
    'Destroyed/Lost': ('lost', 'Destroyed/Lost'),
}


def condition_key(condition):
    if not condition:
        return 'none'
    return CONDITIONS.get(condition, ('other', None))[0]


def readiness(assets):
    """Counts per condition and the readiness %: FMC / (total - Destroyed/Lost).
    An asset with no condition stays in the total, so it lowers the %. The %
    is None when nothing is left to divide by."""
    out = {'total': len(assets), 'fmc': 0, 'pmc': 0, 'nmc': 0, 'lost': 0, 'none': 0, 'other': 0}
    for a in assets:
        out[condition_key(a['condition'])] += 1
    counted = out['total'] - out['lost']
    out['pct'] = round(100.0 * out['fmc'] / counted, 1) if counted else None
    return out


def fleet_readiness(assets, mapping):
    """{'overall': readiness, 'families': {family: readiness}} for all five families."""
    by_family = {f: [] for f in ALL_FAMILIES}
    for a in assets:
        by_family[family_of(a['asset_type'], mapping)].append(a)
    return {
        'overall': readiness(assets),
        'families': {f: readiness(rows) for f, rows in by_family.items()},
    }


# Not Ready, Limited, Ready, no condition, Destroyed/Lost.
_ORDER = {'nmc': 0, 'pmc': 1, 'fmc': 2, 'none': 3, 'other': 3, 'lost': 4}


def table_rows(assets, mapping, family):
    rows = [a for a in assets if family_of(a['asset_type'], mapping) == family]
    rows.sort(key=lambda a: (_ORDER[condition_key(a['condition'])],
                             a['asset_type'].casefold(), a['serial_number'].casefold()))
    return rows


# ---------------------------------------------------------------------------
# Location filter and alerts
# ---------------------------------------------------------------------------

def filter_location(assets, location):
    """Assets at `location`. An asset with several locations is at each of
    them. NO_LOCATION picks the assets with none; a blank value picks all."""
    if not location:
        return list(assets)
    if location == NO_LOCATION:
        return [a for a in assets if not a['location']]
    return [a for a in assets if location in a['location']]


def alert_rows(groups):
    """One row per attention rule, {'key', 'title', 'count'}, largest count
    first, ties in the /attention page's order (so rules at 0 come last).
    Also the total number of problems."""
    rows = [{'key': g['key'], 'title': g['title'], 'count': len(g['assets']), 'order': i}
            for i, g in enumerate(groups)]
    rows.sort(key=lambda r: (-r['count'], r['order']))
    return rows, sum(r['count'] for r in rows)


# ---------------------------------------------------------------------------
# The daily history
# ---------------------------------------------------------------------------

def _counts(r):
    return {
        'total': r['total'], 'fmc': r['fmc'], 'pmc': r['pmc'], 'nmc': r['nmc'],
        'destroyed_lost': r['lost'], 'no_condition': r['none'],
        'other_condition': r['other'], 'readiness_pct': r['pct'],
    }


def snapshot(data, mapping, now):
    """One history line, as a dict."""
    ready = fleet_readiness(data['assets'], mapping)
    line = {'date': now.date().isoformat(), 'recorded_at': now.isoformat(timespec='seconds'),
            'source': data['source']}
    line.update(_counts(ready['overall']))
    line['families'] = {f: _counts(r) for f, r in ready['families'].items()}
    return line


def worth_recording(data, now):
    """Whether this copy of the list may go in the history today. A live
    SharePoint copy must be fresh: not stale, and fetched today. A CSV export
    is recorded as it is, whatever its date."""
    if not data.get('live'):
        return True
    if data.get('stale'):
        return False
    return data['loaded_at'].astimezone(now.tzinfo).date() == now.date()


class ReadinessHistory:
    """The history file: one JSON line per calendar day. Written at most once
    a day, also across restarts, because the last date comes from the file."""

    def __init__(self, path, off_reason=None):
        self.path = path
        # Set when the folder could not be made at startup: history is then
        # off until a restart, with no attempt at each page load.
        self.off_reason = off_reason
        self._lock = threading.Lock()
        self._last_date = None
        self._bad_lines = 0
        # Kept apart so a good read never hides a failed write, or the reverse.
        self._problems = {'write': None, 'read': None}

    @property
    def problem(self):
        """A write or read problem for the page, or None."""
        return self._problems['write'] or self._problems['read']

    def _read_lines(self):
        """[(date, entry)] for the good lines, and the number of bad ones."""
        good, bad = [], 0
        try:
            f = open(self.path, encoding='utf-8')
        except FileNotFoundError:
            return good, bad
        with f:
            for raw in f:
                if not raw.strip():
                    continue
                try:
                    entry = json.loads(raw)
                    good.append((date.fromisoformat(entry['date']), entry))
                except (ValueError, TypeError, KeyError):
                    bad += 1
        return good, bad

    def _set_problem(self, kind, problem):
        """Log a problem once, and again only when it changes or clears."""
        before = self._problems[kind]
        if problem != before:
            if problem:
                log.error('Readiness history: %s', problem)
            else:
                log.info('Readiness history: %s works again: %s.',
                         'writing' if kind == 'write' else 'reading', self.path)
        self._problems[kind] = problem

    def record(self, data, families, now):
        """Append today's line if it is not there yet. Never raises: a problem
        goes to the log (once per cause) and to `problem` for the page.
        `families` is a FamilyMap, read only when a line is written."""
        if self.off_reason or not worth_recording(data, now):
            return False
        today = now.date()
        with self._lock:
            if self._last_date is not None and self._last_date >= today:
                return False
            try:
                good, _ = self._read_lines()
                last = max((d for d, _ in good), default=None)
                if last is not None and last >= today:
                    self._last_date = last
                    self._set_problem('write', None)
                    return False
                mapping, _ = families.load()
                text = json.dumps(snapshot(data, mapping, now), ensure_ascii=False)
                folder = os.path.dirname(self.path)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                with open(self.path, 'a', encoding='utf-8', newline='\n') as f:
                    f.write(text + '\n')
            except Exception as e:
                self._set_problem('write', 'today\'s line could not be written to %s (%s: %s). '
                                  'The pages still load; the trend misses this day until it '
                                  'works.' % (self.path, type(e).__name__, e))
                return False
            self._last_date = today
            self._set_problem('write', None)
            return True

    def entries(self):
        """The good lines, oldest first. A file that cannot be read gives none,
        with the reason in `problem` and the log."""
        if self.off_reason:
            return []
        with self._lock:
            try:
                good, bad = self._read_lines()
            except Exception as e:
                self._set_problem('read', '%s could not be read for the trend (%s: %s).'
                                  % (self.path, type(e).__name__, e))
                return []
            self._set_problem('read', None)
            if bad and bad != self._bad_lines:
                log.warning('Readiness history: %d line(s) in %s could not be read and are '
                            'left out of the trend.', bad, self.path)
            self._bad_lines = bad
        return [entry for _, entry in sorted(good, key=lambda de: de[0])]


def trend(entries, today, days=7):
    """The last `days` days ending today: labels, the number of days with a
    line, and one series per line on the chart, None for a missing day."""
    dates = [today - timedelta(days=days - 1 - i) for i in range(days)]
    by_date = {e['date']: e for e in entries}
    series = {'Overall': []}
    series.update({f: [] for f in MAIN_FAMILIES})
    points = 0
    for d in dates:
        e = by_date.get(d.isoformat())
        points += e is not None
        series['Overall'].append(e.get('readiness_pct') if e else None)
        for f in MAIN_FAMILIES:
            fam = (e or {}).get('families', {}).get(f) or {}
            series[f].append(fam.get('readiness_pct'))
    return {
        'labels': ['%d/%d' % (d.month, d.day) for d in dates],
        'points': points,
        'series': series,
    }


def location_options(assets, fields):
    """The Location filter's choices: the list's own, in its order, then
    typed-in values, then "No location" if any asset has none."""
    options = asset_data.filter_options(assets, fields)['location']
    return options['values'], options['blank']
