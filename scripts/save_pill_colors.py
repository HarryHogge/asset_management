"""Save the list's pill colors from a CSV export into pill_colors.json.

The SharePoint source uses this file for colors when SharePoint will not hand
over the column formatting (see README.md, "Saved pill colors"). It holds only
column keys, choice values and colors: no item data, names or emails.

Usage, from the repo folder:

    python scripts/save_pill_colors.py                      (uses Asset Tracking V2.csv)
    python scripts/save_pill_colors.py "exports/new export.csv"
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import assets as asset_data  # noqa: E402

DEFAULT_CSV = os.path.join(REPO, 'Asset Tracking V2.csv')
OUT_PATH = os.path.join(REPO, 'pill_colors.json')


def build(csv_path):
    """The pill_colors.json content for one export, as a dict."""
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        first = f.readline()
    if not first.startswith('ListSchema='):
        raise SystemExit('%s has no ListSchema= first line. Export the list again with '
                         'Export > Export to CSV and use that file.' % os.path.basename(csv_path))
    return asset_data.saved_colors(asset_data.parse_schema(first))


def write(data, out_path):
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    csv_path = argv[0] if argv else DEFAULT_CSV
    if not os.path.isfile(csv_path):
        raise SystemExit('No file at %s' % csv_path)
    data = build(csv_path)
    write(data, OUT_PATH)
    for key, entry in data.items():
        print('%-15s %2d choices, %2d with a color' % (key, len(entry['choices']), len(entry['colors'])))
    print('Wrote %s' % OUT_PATH)
    return 0


if __name__ == '__main__':
    sys.exit(main())
