import csv
import json
import os

import pytest

import assets as asset_data
from scripts import save_pill_colors

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED = os.path.join(REPO, 'pill_colors.json')
CSV = os.path.join(REPO, 'Asset Tracking V2.csv')


def strings_in(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from strings_in(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings_in(v)
    elif isinstance(node, str):
        yield node


def test_committed_file_matches_the_committed_export():
    with open(SAVED, encoding='utf-8') as f:
        assert json.load(f) == save_pill_colors.build(CSV)


def choice_values():
    with open(CSV, encoding='utf-8-sig', newline='') as f:
        return {c for field in asset_data.parse_schema(f.readline()).values()
                for c in field['choices']}


def test_saved_file_holds_only_column_keys_choices_and_colors():
    data = asset_data.read_saved_colors(SAVED)
    assert set(data) <= set(asset_data.COLUMNS.values())
    choices = choice_values()
    allowed = set(asset_data.COLUMNS.values()) | {'choices', 'colors', 'bg', 'fg'} | choices
    for entry in data.values():
        assert set(entry) == {'choices', 'colors'}
        assert set(entry['colors']) <= set(entry['choices'])
        for style in entry['colors'].values():
            assert set(style) == {'bg', 'fg'}
    for s in strings_in(data):
        assert s in allowed or asset_data._HEX.fullmatch(s), s


def test_saved_file_holds_no_item_data():
    text = open(SAVED, encoding='utf-8').read()
    assert '@' not in text
    with open(CSV, encoding='utf-8-sig', newline='') as f:
        f.readline()
        rows = list(csv.DictReader(f))
    saved = set(strings_in(json.loads(text)))
    choices = choice_values()
    checked = 0
    for row in rows:
        for header in ('Serial Number', 'Part Number', 'Check Out By/To', 'Asset Notes',
                       'Shelf Location', 'Date Out', 'Last Inventory'):
            value = (row.get(header) or '').strip()
            # Some rows have a choice typed into a text column (an asset type
            # as the serial number); that text is the list's choice, not item data.
            if value and value not in choices:
                checked += 1
                assert value not in saved, header
    assert checked > 100


def test_script_writes_utf8(tmp_path, monkeypatch):
    out = tmp_path / 'pill_colors.json'
    monkeypatch.setattr(save_pill_colors, 'OUT_PATH', str(out))
    assert save_pill_colors.main([CSV]) == 0
    assert json.loads(out.read_bytes().decode('utf-8')) == save_pill_colors.build(CSV)


def test_script_refuses_an_export_with_no_schema_line(tmp_path):
    plain = tmp_path / 'plain.csv'
    plain.write_text('Serial Number\nX\n', encoding='utf-8')
    with pytest.raises(SystemExit, match='no ListSchema= first line'):
        save_pill_colors.build(str(plain))
