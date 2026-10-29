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

# Light theme backgrounds a pill can sit on (base.html: --surface, --surface-2,
# --bg, --row-hover). A pill must stand out from every one of them.
LIGHT_BACKGROUNDS = ('#ffffff', '#fafafa', '#f5f5f5', '#f2f2f2')
TEXT_CONTRAST = 4.5   # text on its pill
EDGE_CONTRAST = 3.0   # the pill's fill or border against the page


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(int(round(c)) for c in rgb)


def luminance(hex_color):
    """Relative luminance, as WCAG defines it."""
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG contrast ratio of two colors, from 1 to 21."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _darken(hex_color, step=0.02):
    return _hex(c * (1 - step) for c in _rgb(hex_color))


def _darken_until(hex_color, ok):
    color = hex_color
    for _ in range(200):
        if ok(color):
            return color
        color = _darken(color)
    return '#000000'


def _stands_out(color):
    return all(contrast(color, page) >= EDGE_CONTRAST for page in LIGHT_BACKGROUNDS)


_light_cache = {}


def light_pill(bg, fg):
    """The light theme version of a pill: {'bg', 'fg', 'border'}.

    - Text must reach TEXT_CONTRAST on the fill. Light text on a dark fill:
      the fill is darkened. Dark text on a pale fill: the text is darkened, so
      the pale fill keeps the list's color.
    - The fill, or else a border, must reach EDGE_CONTRAST against every light
      page background. A pale fill gets a border in its own text color,
      darkened if needed.
    - A pill that already meets both is returned unchanged, with no border.
    """
    key = (bg.lower(), fg.lower())
    if key in _light_cache:
        return _light_cache[key]
    bg, fg = key
    if luminance(fg) > luminance(bg):
        darker = _darken_until(bg, lambda c: contrast(fg, c) >= TEXT_CONTRAST)
        if contrast(fg, darker) >= TEXT_CONTRAST:
            bg = darker
    else:
        darker = _darken_until(fg, lambda c: contrast(c, bg) >= TEXT_CONTRAST)
        if contrast(darker, bg) >= TEXT_CONTRAST:
            fg = darker
    if contrast(fg, bg) < TEXT_CONTRAST:
        # Two dark colors cannot get there by darkening: keep the fill and use
        # black or white text, whichever is further from it. One of the two
        # is always at least 4.58 to 1 on any fill.
        fg = max(('#000000', '#ffffff'), key=lambda c: contrast(c, bg))
    if _stands_out(bg):
        border = 'transparent'
    else:
        border = _darken_until(fg if luminance(fg) < luminance(bg) else bg, _stands_out)
    result = {'bg': bg, 'fg': fg, 'border': border}
    _light_cache[key] = result
    return result


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
# Each column's internal name in SharePoint, from the list's schema. Anyone
# can rename a column's display name in the list ("Asset Type" became
# "Assets"), but the internal name never changes. Columns are found by display
# name first and by this name if that fails, so a rename does not blank them.
INTERNAL_NAMES = {
    'Part Number': 'PartNumber',
    'Asset Type': 'AssetType',
    'Serial Number': 'SerialNumber',
    'Ownership': 'Ownership',
    'Status': 'Status',
    'Location': 'OwnershipandLocation',
    'Material Condition': 'MaterialCondition',
    'Date Out': 'DateOut',
    'Check Out By/To': 'CheckOutBy_x002f_To',
    'Asset Notes': 'AssetNotes',
    'Shelf Location': 'ShelfLocation',
    'Last Inventory': 'LastInventory',
}
MULTI_CHOICE = {'status', 'location'}
DATES = {'date_out', 'last_inventory'}
# Text the export pads with tabs, newlines or trailing spaces.
SINGLE_LINE = {'part_number', 'serial_number', 'shelf_location', 'checked_out_to'}

# Every row says which site it belongs to. Rows from the SharePoint list or
# its CSV export are US rows; riga_loader.py makes the Riga ones.
US_SITE = 'US'

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


def _schema_payload(line):
    return json.loads(line.split('=', 1)[1]).get('schemaXmlList', [])


def parse_schema(line):
    """Parse the `ListSchema=` line into {key: {label, type, choices, colors}}."""
    return parse_schema_xml(_schema_payload(line))


def _schema_headers(elements):
    """Which column definition is which dashboard column, as {id(element):
    header}. By display name first, as before; then, for a column with no
    display name match, by its internal name."""
    chosen = {}
    for el in elements:
        if el.get('DisplayName') in COLUMNS:
            chosen[el.get('DisplayName')] = el
    by_internal = {name: header for header, name in INTERNAL_NAMES.items()}
    for el in elements:
        header = by_internal.get(el.get('Name'))
        if header and header not in chosen:
            chosen[header] = el
    return {id(el): header for header, el in chosen.items()}


def renamed_columns(xml_list):
    """{display name now in the list: dashboard header} for each column found
    only by its internal name, for example {'Assets': 'Asset Type'}."""
    elements = [ElementTree.fromstring(xml) for xml in xml_list]
    headers = _schema_headers(elements)
    renamed = {}
    for el in elements:
        header = headers.get(id(el))
        if header and el.get('DisplayName') != header:
            renamed[el.get('DisplayName')] = header
    return renamed


def parse_schema_xml(xml_list):
    """Turn SharePoint column XML (one <Field .../> string per column) into
    {key: {label, type, choices, colors}}. The CSV export's schema line and
    SharePoint's REST `SchemaXml` hold the same XML, so both sources use this.
    A column renamed in the list is found by its internal name and keeps the
    dashboard's label."""
    elements = [ElementTree.fromstring(xml) for xml in xml_list]
    headers = _schema_headers(elements)
    fields = {}
    for el in elements:
        label = headers.get(id(el))
        if not label:
            continue
        key = COLUMNS[label]
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


def saved_colors(fields):
    """The part of parse_schema's result that pill_colors.json keeps: for each
    choice column, its choices in the list's order and their colors. Column
    definitions only, never item data."""
    return {
        key: {'choices': list(field['choices']), 'colors': dict(field['colors'])}
        for key, field in fields.items() if field.get('choices')
    }


_HEX = re.compile(r'#[0-9a-fA-F]{6}')


def read_saved_colors(path):
    """Read pill_colors.json (see scripts/save_pill_colors.py). Raises OSError
    if it cannot be read and ValueError if it is not in the expected shape."""
    with open(path, encoding='utf-8') as f:
        try:
            data = json.load(f)
        except ValueError:
            raise ValueError('it is not valid JSON') from None
    if not isinstance(data, dict):
        raise ValueError('it does not hold a set of columns')
    for key, entry in data.items():
        if key not in COLUMNS.values():
            raise ValueError('it names a column the dashboard does not know: %s' % key)
        if (not isinstance(entry, dict) or not isinstance(entry.get('choices'), list)
                or not isinstance(entry.get('colors'), dict)):
            raise ValueError('column %s needs "choices" and "colors"' % key)
        if not all(isinstance(c, str) for c in entry['choices']):
            raise ValueError('column %s has a choice that is not text' % key)
        for style in entry['colors'].values():
            if not (isinstance(style, dict)
                    and all(isinstance(style.get(p), str) and _HEX.fullmatch(style[p])
                            for p in ('bg', 'fg'))):
                raise ValueError('column %s has a color that is not like #a1b2c3' % key)
    return data


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
    """One list item as the pages expect it. `raw` is keyed by the column's
    display name. Values are text as in the CSV export; multi-choice columns
    may also arrive as a list, which is how Microsoft Graph sends them."""
    row = {'id': row_id}
    for header, key in COLUMNS.items():
        value = raw.get(header) or ''
        if not isinstance(value, (str, list)):
            value = str(value)
        if isinstance(value, list) and key not in MULTI_CHOICE:
            value = ', '.join(str(v) for v in value)
        if key in MULTI_CHOICE:
            if isinstance(value, list):
                parsed = value
            else:
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


def with_site(row, site):
    """The row with its `site` field added after the _clean_row fields."""
    row['site'] = site
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
                xml_list = _schema_payload(first)
                fields = parse_schema_xml(xml_list)
                # A column renamed in the list has its new name as the CSV
                # header; read it under the dashboard's header.
                renamed = renamed_columns(xml_list)
            else:
                # A plain export with no schema line: rewind and read it as CSV.
                fields = {}
                renamed = {}
                f.seek(0)
            # The export has no SharePoint item ID and serial numbers repeat,
            # so the row position is the only stable key within one file.
            assets = [with_site(_clean_row({renamed.get(h, h): v for h, v in r.items()}, tz, i + 1),
                                US_SITE)
                      for i, r in enumerate(csv.DictReader(f))]
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
        # The same rule as Riga's. A filled value outside FMC, PMC, NMC and
        # Destroyed/Lost is not caught here: the overview shows it as
        # "Other condition".
        ('no_condition', 'No condition',
         'Material Condition is blank.',
         lambda a, today: not a['condition']),
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
    """An asset for the JSON endpoints. They only ever hold US rows, so the
    `site` field is left out and their answers stay exactly as before."""
    out = dict(asset)
    out.pop('site', None)
    for key in DATES:
        out[key] = asset[key].isoformat() if asset[key] else None
    return out
