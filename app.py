from flask import Flask, render_template, jsonify, request, send_file, abort
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import io
import logging
import os

import assets as asset_data
import fleet
import sharepoint

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'), encoding='utf-8')

if __name__ == '__main__':
    # Set up before the data source is made, so a settings problem found at
    # startup reaches the log in the same format as everything else. MSAL is
    # held to warnings so the log never fills with sign-in chatter.
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logging.getLogger('msal').setLevel(logging.WARNING)
log = logging.getLogger('asset_management.app')

app = Flask(__name__)

# Where the SharePoint export lives. Relative paths resolve against this repo.
ASSET_CSV = os.getenv('ASSET_CSV', 'Asset Tracking V2.csv')
if not os.path.isabs(ASSET_CSV):
    ASSET_CSV = os.path.join(BASE_DIR, ASSET_CSV)
# The SharePoint site's time zone; list dates are stored as local midnight in UTC.
SITE_TIMEZONE = os.getenv('SITE_TIMEZONE', 'America/Los_Angeles')
INVENTORY_STALE_DAYS = int(os.getenv('INVENTORY_STALE_DAYS', '90'))
# Not 5060/5061: those are SIP ports and Chrome refuses to open them.
PORT = int(os.getenv('PORT', '5070'))
# One line per day of readiness numbers, for the Fleet Overview trend.
READINESS_HISTORY = os.getenv('READINESS_HISTORY', os.path.join('data', 'readiness_history.jsonl'))
if not os.path.isabs(READINESS_HISTORY):
    READINESS_HISTORY = os.path.join(BASE_DIR, READINESS_HISTORY)


class CsvSource:
    """The SharePoint list's CSV export (the default source)."""

    def __init__(self, path, tz_name):
        self.path = path
        self.tz_name = tz_name

    def load(self):
        return asset_data.load(self.path, self.tz_name)


class UnavailableSource:
    """Stands in for the data source when a setting is wrong. The dashboard
    stays up (under PM2, exiting would only restart it over and over) and
    every page says which setting to fix."""

    def __init__(self, problem):
        self.problem = problem

    def load(self):
        raise sharepoint.ConfigError(self.problem)


def make_source(name, env=None):
    """The data source named by ASSET_SOURCE. A settings problem is logged
    here, once, and every page then shows it until .env is fixed."""
    name = (name or 'csv').strip().lower()
    try:
        if name == 'csv':
            return CsvSource(ASSET_CSV, SITE_TIMEZONE)
        if name == 'sharepoint':
            return sharepoint.SharePointSource.from_env(SITE_TIMEZONE, env)
        raise sharepoint.ConfigError('ASSET_SOURCE must be csv or sharepoint.')
    except sharepoint.ConfigError as e:
        log.error('Settings problem: %s The dashboard is running, but every page shows '
                  'this until .env is fixed and the dashboard is restarted.', e)
        return UnavailableSource(str(e))


SOURCE = make_source(os.getenv('ASSET_SOURCE'))
FAMILIES = fleet.FamilyMap()
HISTORY = fleet.ReadinessHistory(READINESS_HISTORY)

PAGES = [
    ('overview', '/overview', 'Fleet Overview'),
    ('inventory', '/', 'Inventory'),
    ('attention', '/attention', 'Needs Attention'),
    ('checkouts', '/checkouts', 'Checkouts'),
    ('metrics', '/metrics', 'Metrics'),
]


def today():
    return datetime.now(ZoneInfo(SITE_TIMEZONE)).date()


def load():
    try:
        data = SOURCE.load()
    except FileNotFoundError:
        abort(503, description='Asset export not found: %s (set ASSET_CSV in .env)'
              % os.path.basename(ASSET_CSV))
    except sharepoint.ConfigError as e:
        abort(503, description='The dashboard cannot read the asset list because of a '
              'settings problem. %s Fix it in .env on the server, then restart the '
              'dashboard.' % e)
    except sharepoint.SourceError:
        # The reason is already in the log, written when the fetch failed.
        abort(503, description='SharePoint could not be reached, and there is no earlier '
              'copy of the asset list to show. The dashboard tries again every minute, '
              'so reload this page shortly. The reason is in the dashboard log.')
    # The first good load of each day adds that day's line to the readiness
    # history. It never raises: a failed write is logged and noted on /overview.
    HISTORY.record(data, FAMILIES, datetime.now(ZoneInfo(SITE_TIMEZONE)))
    return data


@app.errorhandler(503)
def unavailable(e):
    # The JSON endpoints answer in JSON; pages and the Excel download get a page.
    if request.path.startswith('/api/') and not request.path.startswith('/api/export/'):
        return jsonify({'error': e.description}), 503
    return render_template('error.html', active=None, message=e.description), 503


@app.context_processor
def page_context():
    return {'pages': PAGES, 'stale_days': INVENTORY_STALE_DAYS}


@app.template_filter('mdy')
def mdy(value):
    return '%d/%d/%d' % (value.month, value.day, value.year) if value else ''


def _clock(value):
    # Built by hand rather than with strftime's %-m/%-I: those no-leading-zero
    # flags don't exist on Windows and raise ValueError there.
    hour = value.hour % 12 or 12
    return '%d:%02d %s' % (hour, value.minute, 'AM' if value.hour < 12 else 'PM')


@app.template_filter('mdy_time')
def mdy_time(value):
    return '%s %s' % (mdy(value), _clock(value)) if value else ''


@app.template_filter('short_time')
def short_time(value):
    """Just the time if it is today in the site's time zone, otherwise the
    date and time, so "9:40 AM" never means yesterday."""
    if not value:
        return ''
    if value.astimezone(ZoneInfo(SITE_TIMEZONE)).date() == today():
        return _clock(value)
    return mdy_time(value)


def render(template, active, data, **kwargs):
    # `data` is the copy the route already used, so a background refresh that
    # finishes mid-request cannot mix two versions on one page.
    return render_template(
        template,
        active=active,
        fields=data['fields'],
        source=data['source'],
        loaded_at=data['loaded_at'],
        live=data.get('live', False),
        stale=data.get('stale'),
        **kwargs,
    )


@app.route('/overview')
def overview():
    data = load()
    mapping, mapping_problem = FAMILIES.load()
    location = request.args.get('location', '')
    assets = fleet.filter_location(data['assets'], location)
    locations, any_without = fleet.location_options(data['assets'], data['fields'])
    groups = asset_data.attention(assets, today(), INVENTORY_STALE_DAYS)
    alert_rows, problem_count = fleet.alerts(groups)
    # The trend is fleet-wide: it comes from the history, not the filter.
    trend = fleet.trend(HISTORY.entries(), today())
    return render('overview.html', 'overview', data,
                  left_nav=True,
                  location=location,
                  no_location=fleet.NO_LOCATION,
                  locations=locations,
                  any_without_location=any_without,
                  ready=fleet.fleet_readiness(assets, mapping),
                  tables=[(f, fleet.table_rows(assets, mapping, f)) for f in fleet.MAIN_FAMILIES],
                  unmapped=fleet.unmapped_types(assets, mapping),
                  mapping_problem=mapping_problem,
                  history_problem=HISTORY.problem,
                  alert_rows=alert_rows,
                  problem_count=problem_count,
                  trend=trend)


@app.route('/')
def inventory():
    data = load()
    groups = asset_data.attention(data['assets'], today(), INVENTORY_STALE_DAYS)
    return render('inventory.html', 'inventory', data,
                  assets=data['assets'],
                  options=asset_data.filter_options(data['assets'], data['fields']),
                  flagged=asset_data.flagged_ids(groups))


@app.route('/attention')
def attention():
    data = load()
    groups = asset_data.attention(data['assets'], today(), INVENTORY_STALE_DAYS)
    return render('attention.html', 'attention', data, groups=groups)


@app.route('/checkouts')
def checkouts():
    data = load()
    rows = asset_data.checkouts(data['assets'], today())
    holders = {}
    for r in rows:
        holders.setdefault(r['checked_out_to'] or '(nobody listed)', []).append(r)
    holders = sorted(holders.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return render('checkouts.html', 'checkouts', data, rows=rows, holders=holders)


@app.route('/metrics')
def metrics():
    data = load()
    return render('metrics.html', 'metrics', data,
                  summary=asset_data.summary(data['assets'], today(), INVENTORY_STALE_DAYS))


@app.route('/api/assets')
def api_assets():
    data = load()
    return jsonify({
        'source': data['source'],
        'loaded_at': data['loaded_at'].isoformat(),
        'count': len(data['assets']),
        'assets': [asset_data.serialize(a) for a in data['assets']],
    })


@app.route('/api/fields')
def api_fields():
    return jsonify(load()['fields'])


@app.route('/api/summary')
def api_summary():
    return jsonify(asset_data.summary(load()['assets'], today(), INVENTORY_STALE_DAYS))


@app.route('/api/attention')
def api_attention():
    groups = asset_data.attention(load()['assets'], today(), INVENTORY_STALE_DAYS)
    return jsonify([
        dict(g, assets=[asset_data.serialize(a) for a in g['assets']]) for g in groups
    ])


@app.route('/api/export/assets.xlsx')
def export_assets():
    """Excel export of the inventory, optionally limited to ?ids=1,2,3
    (the inventory page passes whatever its filters currently show)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    data = load()
    rows = data['assets']
    ids = request.args.get('ids')
    if ids:
        wanted = {int(i) for i in ids.split(',') if i.strip().isdigit()}
        rows = [a for a in rows if a['id'] in wanted]

    columns = [
        ('Asset Type', 'asset_type', 20), ('Serial Number', 'serial_number', 16),
        ('Part Number', 'part_number', 18), ('Ownership', 'ownership', 20),
        ('Status', 'status', 10), ('Location', 'location', 22),
        ('Material Condition', 'condition', 12), ('Date Out', 'date_out', 12),
        ('Check Out By/To', 'checked_out_to', 28), ('Shelf Location', 'shelf_location', 24),
        ('Last Inventory', 'last_inventory', 14), ('Asset Notes', 'notes', 50),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = 'Assets'
    header_fill = PatternFill('solid', fgColor='B00000')
    for col, (label, _, width) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        ws.column_dimensions[get_column_letter(col)].width = width
    for r, asset in enumerate(rows, start=2):
        for col, (_, key, _) in enumerate(columns, start=1):
            value = asset[key]
            if isinstance(value, list):
                value = ', '.join(value)
            cell = ws.cell(row=r, column=col, value=value)
            if key in asset_data.DATES and value:
                cell.number_format = 'm/d/yyyy'
            if key == 'notes':
                cell.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='assets-%s.xlsx' % today().isoformat(),
    )


if __name__ == '__main__':
    from waitress import serve
    print("=" * 60)
    print("Asset Tracking Dashboard starting...")
    if isinstance(SOURCE, CsvSource):
        print(f"Data source: CSV export {ASSET_CSV}")
    elif isinstance(SOURCE, UnavailableSource):
        print("Data source: NOT AVAILABLE because of a settings problem (see the log line")
        print("above). Every page shows the problem until .env is fixed and the dashboard")
        print("is restarted.")
    else:
        print(f"Data source: SharePoint list {SOURCE.settings['list_name']}, "
              f"refreshed every {SOURCE.settings['refresh_seconds']} seconds")
    print(f"Site time zone: {SITE_TIMEZONE}")
    print(f"Readiness history: {READINESS_HISTORY}")
    print("=" * 60)
    print(f"\nOpen http://localhost:{PORT} in your browser\n")
    serve(app, host='0.0.0.0', port=PORT)
