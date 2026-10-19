"""Load and clean the SharePoint "Asset Tracking V2" list export.

A SharePoint list CSV export starts with one `ListSchema=<json>` line holding
every column's XML definition (type, allowed choices, and the CustomFormatter
that colors each choice as a pill), followed by an ordinary CSV. This module
reads both halves so the dashboard shows the same choices and colors the list
does, without hard-coding them.

Everything here is a pure function of the file, cached on its mtime, so the
same loader can later be swapped for a Microsoft Graph fetch without the
pages noticing.
"""
import csv
import json
import os
import re
import threading
from datetime import date, datetime, timezone
from xml.etree import ElementTree
from zoneinfo import ZoneInfo


# Microsoft Lists pill colors, keyed by the suffix of the SharePoint class
# (sp-css-backgroundColor-BgTeal -> "BgTeal"). Approximations of the Lists
# palette; anything unknown falls back to the outlined default pill.
BG_COLORS = {
    'BgTeal': '#038387', 'BgBrown': '#8e562e', 'BgMintGreen': '#dff6dd',
    'BgPurple': '#6b47b8', 'BgLightGray': '#e1dfdd', 'BgMauve': '#efe4f7',
    'BgGold': '#fff1c2', 'BgCyan': '#dcf5f9', 'BgGray': '#605e5c',
    'BgGreen': '#498205', 'BgDarkGreen': '#0b5a0b', 'BgRed': '#c50f1f',
    'BgOrange': '#ca5010', 'BgDustRose': '#f6e4e2', 'BgDarkBlue': '#004e8c',
    'BgLavender': '#8764b8', 'BgPeach': '#fde5d6', 'BgDarkRed': '#a4262c',
    'BgCoral': '#fde7e9', 'BgBlue': '#0f6cbd',
}
FONT_COLORS = {
    'WhiteFont': '#ffffff', 'MintGreenFont': '#0b6a0b', 'LightGrayFont': '#3b3a39',
    'MauveFont': '#5c2e91', 'GoldFont': '#7a5400', 'CyanFont': '#005b70',
    'DustRoseFont': '#8b3a33', 'PeachFont': '#8f3500', 'CoralFont': '#a4262c',
}

# CSV header -> key used everywhere else.
COLUMNS = {
    'Part Number': 'part_number',
    'Asset Type': 'asset_type',
    'Serial Number': 'serial_number',
    'Ownership': 'ownership',
    'Status': 'status',
    'Location': 'location',
    'Material Condition': 'condition',
    'Date Out': 'date_out',
    'Check Out By/To': 'checked_out_to',
    'Asset Notes': 'notes',
    'Shelf Location': 'shelf_location',
    'Last Inventory': 'last_inventory',
}
MULTI_CHOICE = {'status', 'location'}
DATES = {'date_out', 'last_inventory'}
# Text the export pads with tabs, newlines or trailing spaces.
SINGLE_LINE = {'part_number', 'serial_number', 'shelf_location', 'checked_out_to'}

_cache = {'key': None, 'data': None}
_lock = threading.Lock()


def _pill_tree(node):
    """Find the first `attributes.class` conditional in a CustomFormatter."""
    if isinstance(node, dict):
        cls = node.get('attributes', {}).get('class')
        if isinstance(cls, dict) and cls.get('operator') == ':':
            return cls
        for child in node.values():
            found = _pill_tree(child)
            if found:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _pill_tree(child)
            if found:
                return found
    return None


def _style_for(classes):
    bg = re.search(r'sp-css-backgroundColor-(\w+)', classes or '')
    fg = re.search(r'sp-css-color-(\w+)', classes or '')
    if not bg or bg.group(1) not in BG_COLORS:
        return None
    return {
        'bg': BG_COLORS[bg.group(1)],
        'fg': FONT_COLORS.get(fg.group(1) if fg else '', '#ffffff'),
    }


def _pill_colors(formatter):
    """Walk the nested `cond ? classes : else` tree into {choice: style}."""
    colors = {}
    node = _pill_tree(formatter)
    while isinstance(node, dict) and node.get('operator') == ':':
        cond, then, rest = (node.get('operands') or [None, None, None])[:3]
        if isinstance(cond, dict) and cond.get('operator') == '==':
            value = (cond.get('operands') or ['', ''])[1]
            style = _style_for(then)
            # The list repeats some choices (VXE-30 appears twice); first wins,
            # matching how SharePoint evaluates the chain.
            if value and style and value not in colors:
                colors[value] = style
        node = rest
    return colors


def parse_schema(line):
    """Parse the `ListSchema=` line into {key: {label, type, choices, colors}}."""
    payload = json.loads(line.split('=', 1)[1])
    fields = {}
    for xml in payload.get('schemaXmlList', []):
        el = ElementTree.fromstring(xml)
        label = el.get('DisplayName')
        key = COLUMNS.get(label)
        if not key:
            continue
        choices = []
        for c in el.iter('CHOICE'):
            if c.text and c.text not in choices:
                choices.append(c.text)
        formatter = el.get('CustomFormatter')
        fields[key] = {
            'label': label,
            'type': el.get('Type'),
            'description': el.get('Description') or '',
            'choices': choices,
            'colors': _pill_colors(json.loads(formatter)) if formatter else {},
        }
    return fields


def _to_local_date(value, tz):
    """SharePoint exports dates as UTC instants of local midnight
    (2026-10-02T07:00:00Z is 10/2 in Pacific time). Convert back to the
    site's calendar date, or the dashboard shows the day before."""
    value = (value or '').strip()
    if not value:
        return None
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(tz).date()


def _clean_row(raw, tz, row_id):
    row = {'id': row_id}
    for header, key in COLUMNS.items():
        value = raw.get(header) or ''
        if key in MULTI_CHOICE:
            try:
                parsed = json.loads(value) if value.strip() else []
            except ValueError:
                parsed = [value]
            if not isinstance(parsed, list):
                parsed = [parsed]
            row[key] = [str(v).strip() for v in parsed if str(v).strip()]
        elif key in DATES:
            row[key] = _to_local_date(value, tz)
        elif key in SINGLE_LINE:
            row[key] = ' '.join(value.split())
        else:
            row[key] = value.strip()
    return row


def load(path, tz_name):
    """Return {'fields', 'assets', 'loaded_at', 'source'}, cached on file mtime."""
    mtime = os.path.getmtime(path)
    key = (path, mtime, tz_name)
    with _lock:
        if _cache['key'] == key:
            return _cache['data']
        tz = ZoneInfo(tz_name)
        with open(path, encoding='utf-8-sig', newline='') as f:
            first = f.readline()
            if first.startswith('ListSchema='):
                fields = parse_schema(first)
            else:
                # A plain export with no schema line: rewind and read it as CSV.
                fields = {}
                f.seek(0)
            # The export has no SharePoint item ID and serial numbers repeat,
            # so the row position is the only stable key within one file.
            assets = [_clean_row(r, tz, i + 1) for i, r in enumerate(csv.DictReader(f))]
        data = {
            'fields': fields,
            'assets': assets,
            'loaded_at': datetime.fromtimestamp(mtime, tz),
            'source': os.path.basename(path),
        }
        _cache['key'] = key
        _cache['data'] = data
        return data


# ---------------------------------------------------------------------------
# Derived views
# ---------------------------------------------------------------------------

def is_out(asset):
    return 'OUT' in asset['status']


def attention_rules(stale_days):
    """(key, title, explanation, predicate) for each data problem we flag."""
    return [
        ('out_no_holder', 'Out, but not checked out to anyone',
         'Status is OUT and Check Out By/To is blank.',
         lambda a, today: is_out(a) and not a['checked_out_to']),
        ('out_no_date', 'Out, with no Date Out',
         'Status is OUT and Date Out is blank.',
         lambda a, today: is_out(a) and not a['date_out']),
        ('holder_not_out', 'Checked out to someone, but not marked OUT',
         'Check Out By/To is filled in but Status is not OUT.',
         lambda a, today: bool(a['checked_out_to']) and not is_out(a)),
        ('no_status', 'No status',
         'Status is blank.',
         lambda a, today: not a['status']),
        ('never_inventoried', 'Never inventoried',
         'Last Inventory is blank.',
         lambda a, today: a['last_inventory'] is None),
        ('inventory_overdue', 'Inventory overdue',
         'Last Inventory is more than %d days ago.' % stale_days,
         lambda a, today: a['last_inventory'] is not None
         and (today - a['last_inventory']).days > stale_days),
        ('degraded_no_notes', 'PMC/NMC with no notes',
         'Material Condition is PMC or NMC but Asset Notes says nothing about why.',
         lambda a, today: a['condition'] in ('PMC', 'NMC') and not a['notes']),
    ]


def attention(assets, today, stale_days):
    groups = []
    for key, title, why, test in attention_rules(stale_days):
        hits = [a for a in assets if test(a, today)]
        groups.append({'key': key, 'title': title, 'why': why, 'assets': hits})
    return groups


def flagged_ids(groups):
    return {a['id'] for g in groups for a in g['assets']}


def filter_options(assets, fields):
    """Dropdown values per filterable column: the list's own choices in the
    list's order, then any typed-in values (Location allows fill-ins)."""
    options = {}
    for key in ('asset_type', 'ownership', 'status', 'location', 'condition'):
        used = set()
        blank = False
        for a in assets:
            values = a[key] if isinstance(a[key], list) else [a[key]]
            values = [v for v in values if v]
            used.update(values)
            blank = blank or not values
        choices = [c for c in fields.get(key, {}).get('choices', []) if c in used]
        extras = sorted(used - set(choices))
        options[key] = {'values': choices + extras, 'blank': blank}
    return options


def checkouts(assets, today):
    rows = []
    for a in assets:
        if not (is_out(a) or a['checked_out_to']):
            continue
        days = (today - a['date_out']).days if a['date_out'] else None
        rows.append(dict(a, days_out=days))
    rows.sort(key=lambda r: (r['days_out'] is None, -(r['days_out'] or 0)))
    return rows


def inventory_age_bucket(asset, today, stale_days):
    if asset['last_inventory'] is None:
        return 'Never'
    days = (today - asset['last_inventory']).days
    if days <= 30:
        return '0-30 days'
    if days <= stale_days:
        return '31-%d days' % stale_days
    return 'Over %d days' % stale_days


def summary(assets, today, stale_days):
    def count(values):
        out = {}
        for v in values:
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    conditions = ['FMC', 'PMC', 'NMC', 'Destroyed/Lost']
    types = count(a['asset_type'] or '(blank)' for a in assets)
    by_type = {
        t: {c: sum(1 for a in assets if (a['asset_type'] or '(blank)') == t and a['condition'] == c)
            for c in conditions}
        for t in types
    }
    buckets = ['Never', '0-30 days', '31-%d days' % stale_days, 'Over %d days' % stale_days]
    ages = count(inventory_age_bucket(a, today, stale_days) for a in assets)
    groups = attention(assets, today, stale_days)
    total = len(assets)
    fmc = sum(1 for a in assets if a['condition'] == 'FMC')
    current = ages.get('0-30 days', 0) + ages.get('31-%d days' % stale_days, 0)
    return {
        'total': total,
        'fmc': fmc,
        'fmc_pct': round(100 * fmc / total) if total else 0,
        'out': sum(1 for a in assets if is_out(a)),
        'flagged': len(flagged_ids(groups)),
        'inventory_current_pct': round(100 * current / total) if total else 0,
        'conditions': conditions,
        'by_type': by_type,
        'status': count(s for a in assets for s in (a['status'] or ['(blank)'])),
        'ownership': count(a['ownership'] or '(blank)' for a in assets),
        'inventory_age': {b: ages.get(b, 0) for b in buckets},
        'attention': {g['title']: len(g['assets']) for g in groups},
    }


def serialize(asset):
    out = dict(asset)
    for key in DATES:
        out[key] = asset[key].isoformat() if asset[key] else None
    return out
