# Prompt 10: Compare the Riga Excel export to the US list

Runs in: Local machine. The workbook is only on Scott's Mac and is git-ignored, so the sandbox cannot see it.
Type: Diagnostic. No code changes.
Output: `reports/10_riga_columns.md`, committed with the message "Prompt 10: Riga columns report" and pushed to `agent/wednesday`. The workbook itself is not committed.

## Task

A file from the Riga site has been added at `data/samples/riga_assets.xlsx`. Read it and write `reports/10_riga_columns.md` covering:

1. **Sheets, row count, and every column** with its type and fill count, in the same format as the field table in report 03.
2. **A column-by-column match against the 12 US columns:** exact, renamed, missing or extra.
   - For the choice columns (Asset Type, Status, Location, Material Condition, Ownership), list Riga's distinct values and which US choices they map to.
   - Flag values that do not map.
3. **Asset Type values not in `asset_families.json`.**
4. **Row-level problems that would break the current loader:** merged cells, blank header rows, dates stored as text and formulas.
5. **A recommendation** for how the Riga data should be read: reuse the CSV loader with a column map, or a separate Excel loader, and why. Do not build it.
