import hashlib
import json

import app as dashboard
import assets as asset_data

# Fingerprints of the committed "Asset Tracking V2.csv" as read by assets.py
# before the SharePoint source was added (commit 20b1c12). If the CSV path
# changes how it reads or cleans anything, these stop matching.
ROWS_SHA256 = '00a9ff2fe2c8d708e8a99961a6b5008c2cd74dca412ad3c7e4e089447fc270e8'
FIELDS_SHA256 = '000b0c543837450e7a87187b85a13383ed215f5554b2d737f38475bdcca96a91'


def test_csv_source_gives_the_same_rows_as_before():
    data = dashboard.CsvSource(dashboard.ASSET_CSV, 'America/Los_Angeles').load()
    rows = json.dumps([asset_data.serialize(r) for r in data['assets']], sort_keys=True)
    fields = json.dumps(data['fields'], sort_keys=True)
    assert len(data['assets']) == 146
    assert hashlib.sha256(rows.encode('utf-8')).hexdigest() == ROWS_SHA256
    assert hashlib.sha256(fields.encode('utf-8')).hexdigest() == FIELDS_SHA256
    assert data.get('stale') is None


def test_an_export_with_a_renamed_column_reads_the_same(tmp_path):
    """An export taken after "Asset Type" was renamed to "Assets" in the list:
    the schema line and the CSV header both say "Assets". Built from the
    committed export, so no new list data is added to the repository."""
    with open(dashboard.ASSET_CSV, encoding='utf-8-sig', newline='') as f:
        schema, header, rest = f.readline(), f.readline(), f.read()
    assert 'DisplayName=\\"Asset Type\\"' in schema and ',"Asset Type",' in header
    renamed = tmp_path / 'renamed.csv'
    renamed.write_text(schema.replace('DisplayName=\\"Asset Type\\"', 'DisplayName=\\"Assets\\"')
                       + header.replace(',"Asset Type",', ',"Assets",') + rest,
                       encoding='utf-8', newline='')
    original = dashboard.CsvSource(dashboard.ASSET_CSV, 'America/Los_Angeles').load()
    data = asset_data.load(str(renamed), 'America/Los_Angeles')
    assert [a['asset_type'] for a in data['assets']] == [a['asset_type'] for a in original['assets']]
    assert sum(1 for a in data['assets'] if a['asset_type']) > 100
    assert data['fields']['asset_type'] == original['fields']['asset_type']
