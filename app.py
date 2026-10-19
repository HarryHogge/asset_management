from flask import Flask, render_template, jsonify, request, send_file, abort
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import io
import os

import assets as asset_data

load_dotenv()

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Where the SharePoint export lives. Relative paths resolve against this repo.
ASSET_CSV = os.getenv('ASSET_CSV', 'Asset Tracking V2.csv')
if not os.path.isabs(ASSET_CSV):
    ASSET_CSV = os.path.join(BASE_DIR, ASSET_CSV)
# The SharePoint site's time zone; list dates are stored as local midnight in UTC.
SITE_TIMEZONE = os.getenv('SITE_TIMEZONE', 'America/Los_Angeles')
INVENTORY_STALE_DAYS = int(os.getenv('INVENTORY_STALE_DAYS', '90'))
# Not 5060/5061: those are SIP ports and Chrome refuses to open them.
PORT = int(os.getenv('PORT', '5070'))

PAGES = [
    ('inventory', '/', 'Inventory'),
    ('attention', '/attention', 'Needs Attention'),
    ('checkouts', '/checkouts', 'Checkouts'),
    ('metrics', '/metrics', 'Metrics'),
]


def today():
    return datetime.now(ZoneInfo(SITE_TIMEZONE)).date()


def load():
    try:
        return asset_data.load(ASSET_CSV, SITE_TIMEZONE)
    except FileNotFoundError:
        abort(503, description='Asset export not found: %s (set ASSET_CSV in .env)'
              % os.path.basename(ASSET_CSV))


@app.context_processor
def page_context():
    return {'pages': PAGES, 'stale_days': INVENTORY_STALE_DAYS}


@app.template_filter('mdy')
def mdy(value):
    return '%d/%d/%d' % (value.month, value.day, value.year) if value else ''


@app.template_filter('mdy_time')
def mdy_time(value):
    # Built by hand rather than with strftime's %-m/%-I: those no-leading-zero
    # flags don't exist on Windows and raise ValueError there.
    if not value:
        return ''
    hour = value.hour % 12 or 12
    return '%s %d:%02d %s' % (mdy(value), hour, value.minute,
                              'AM' if value.hour < 12 else 'PM')


def render(template, active, **kwargs):
    data = load()
    return render_template(
        template,
        active=active,
        fields=data['fields'],
        source=data['source'],
        loaded_at=data['loaded_at'],
        **kwargs,
    )


@app.route('/')
def inventory():
    data = load()
    groups = asset_data.attention(data['assets'], today(), INVENTORY_STALE_DAYS)
    return render('inventory.html', 'inventory',
                  assets=data['assets'],
                  options=asset_data.filter_options(data['assets'], data['fields']),
                  flagged=asset_data.flagged_ids(groups))


@app.route('/attention')
def attention():
    data = load()
    groups = asset_data.attention(data['assets'], today(), INVENTORY_STALE_DAYS)
    return render('attention.html', 'attention', groups=groups)


@app.route('/checkouts')
def checkouts():
    data = load()
    rows = asset_data.checkouts(data['assets'], today())
    holders = {}
    for r in rows:
        holders.setdefault(r['checked_out_to'] or '(nobody listed)', []).append(r)
    holders = sorted(holders.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return render('checkouts.html', 'checkouts', rows=rows, holders=holders)


@app.route('/metrics')
def metrics():
    data = load()
    return render('metrics.html', 'metrics',
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
    print(f"Asset export: {ASSET_CSV}")
    print(f"Site time zone: {SITE_TIMEZONE}")
    print("=" * 60)
    print(f"\nOpen http://localhost:{PORT} in your browser\n")
    serve(app, host='0.0.0.0', port=PORT)
