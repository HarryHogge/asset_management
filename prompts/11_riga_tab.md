# Prompt 11: Riga tab fed from the Excel workbook

Runs in: Sandbox
Type: Build
Output: code, tests, `riga_mapping.json`, changes to `asset_families.json`, README and `example.env`, plus `reports/11_riga_tab.md`, committed with the message "Prompt 11: Riga tab" and pushed to `agent/wednesday`. DEV only: nothing on PROD and no change to `deploy/`.

Read `CLAUDE.md`, `docs/decisions.md`, `reports/06_fleet_overview.md`, `reports/07_overview_followups.md` and, most carefully, `reports/10_riga_columns.md` first.

## Background

Riga keeps its fleet in a 13-sheet Excel workbook, not in SharePoint. Report 10 describes it in detail. **The real workbook is not in the repo and must never be committed**: it holds real data, and rule 3 applies.
- Use report 10 as the specification of the layout, the sheet names, the column names, the condition values and the date formats.
- Build a synthetic fixture workbook inside the tests, with made-up data, that reproduces that layout.
- Every Riga-specific rule lives in a mapping file, not in code, so the real file can be matched later by editing only the mapping.

**Scott's answers to report 10's questions:**

| Question | Answer |
|---|---|
| 2. FCF REQUIRED | **PMC** (report 10 proposed NMC; Scott chose PMC) |
| 3. No checkout data in Riga | Status, Date Out and Check Out By/To stay blank on Riga rows |
| 4. Location and Ownership | Riga keeps its own values. A new Site field tells the two sites apart |
| 5. Engines | Included, in a new Engine family with its own table, but left out of the headline readiness and the family cards |
| 6. How the workbook arrives | Uploaded through a page in the dashboard |
| 1. Is the sample the full workbook? | **Still open.** Build to report 10's layout; the real file is checked later with the check command (step 7) |

**Facts checked on the local machine at commit `0f85ee2`, before this prompt was written:**

- **Tests:** 163, all passing.
- **Families in `fleet.py`:**
  - `FAMILIES` holds the four families;
  - `UNMAPPED` is the fallback;
  - `MAIN_FAMILIES` (Aircraft, GCS, Payload) drives the cards and the trend;
  - `read_families()` rejects any family not in `FAMILIES`.
- **Row IDs:**
  - they are integers: SharePoint item IDs, or row positions for the CSV;
  - the Excel export parses `?ids=` as integers;
  - Inventory writes `data-id`.
- **History lines** have `date` and `recorded_at`, but no site. `ReadinessHistory` allows one line per day.
- **US dates** go through `_to_local_date()`, which converts a UTC instant to the site's day. Riga dates are plain calendar dates and must not be shifted.
- **Git ignores** `data/` and `*.xlsx`, so `data/riga/` is ignored already.

## Part A: Data model

1. **Site field.**
   - Every asset row gets a `site` field: `"US"` for rows from the SharePoint list or the CSV, `"Riga"` for rows from the workbook.
   - Inventory, Needs Attention, Checkouts, Metrics, the JSON endpoints and the Excel export keep showing **US rows only**, exactly as now. Riga rows appear only on the overview's Riga view (Part D).
   - Mixing Riga into the other pages is a question for the report, not part of this prompt.
2. **Engine family.**
   - Add Engine as a fifth family, allowed by `read_families()` alongside the four. Unmapped stays the fallback and is never written in the file.
   - Engines show on the Riga view in their own table.
   - Engines are left out of the headline readiness percentage and the family cards, but they stay in the history line's family counts.
3. **One place decides families.**
   - `asset_families.json` stays the only place that sets a family. Add the Riga Asset Types to it, as below.
   - The `family` field per sheet in `riga_mapping.json` (step 4) is a cross-check. If the two disagree, those rows are Unmapped, and the log and the check command say so.
   - Keep the 29 US entries exactly as they are. Update the test that checks the file holds exactly report 05's 29 types: the 29 US entries are unchanged, and the Riga entries are the ones below.

   | Riga Asset Type (one per sheet) | Family | Source |
   |---|---|---|
   | Penguin C Mk2.x | Aircraft | Report 10 |
   | Penguin C Mk2 | Aircraft | Report 10 |
   | Penguin C Mk2.5 VTOL | Aircraft | Report 10 |
   | Penguin C Mk3 VTOL | Aircraft | Report 10 |
   | VXE (Riga) | Aircraft | Report 10. Kept apart from the US "VXE-30", so US counts do not change |
   | Epsilon Gimbal | Payload | Report 10 |
   | Ground Control Station (Riga) | Ground Control Station | Report 10 |
   | Tracking Antenna | Support | Report 10 offered GCS or Support; Support pending Scott's answer. Put it in the report's questions |
   | Catapult | Support | Report 10 |
   | Engine | Engine | Scott |

## Part B: The Excel loader

4. **`riga_loader.py` and `riga_mapping.json`.**
   - Create `riga_loader.py`, driven by a committed `riga_mapping.json` pre-filled from report 10. The mapping holds:
     - **For each of the 10 equipment sheets:**
       - the sheet name;
       - the Asset Type it represents;
       - the header row number: 3, or 2 for PPC;
       - the header text for each field the loader reads: serial, condition, location, owner, notes and date;
       - the family, as the cross-check.
     - **Header names exactly as report 10 lists them for that sheet,** for example `STATUS` on EPS and GCS, `Asset owner` on the aircraft sheets and `Asset Owner` elsewhere.
       - Notes: `Actions/Defects`, or `NOTES` on VXE, `INFO` on PPC and `INFO:` on GCS.
       - Date: `INFO UPDATE`, `Date` or `DATE`. GCS has no date column, so its date field is empty.
     - **Ignored sheets:** VEHICLES, ZALENIEKI STOCK and OVERALL. They are skipped and listed as "ignored", which keeps them apart from unknown sheets.
     - **The condition map, case-sensitive after trimming spaces:**

       | Riga value | Condition |
       |---|---|
       | RTF | FMC |
       | RTF WITH REMARKS | PMC |
       | FCF REQUIRED | PMC |
       | GROUNDED | NMC |
       | WRITTEN OFF | Destroyed/Lost |

     - **The accepted day-first date formats:** at least `dd.mm.yyyy`, and also `d.m.yyyy` and `dd.mm.yy` if report 10's examples need them.
   - Validate the mapping file the same way as `asset_families.json`: a missing or badly shaped file stops the Riga view with a clear note and a log line, and never affects the US view.
5. **Unknown values.**
   - **A sheet** that is in neither list is skipped and listed as unknown.
   - **A condition value** not in the map becomes "no condition" and is listed. Report 10's `NFC ISSUES` is one example. Under the prompt 08 decision, a row with no condition counts as not ready.
   - **A mapped header** that is not found in the sheet's header row leaves that field blank for the sheet, and is listed. Header matching ignores case and surrounding spaces, but not spelling.
6. **What a Riga row holds.**
   - Status, Date Out and Check Out By/To are blank. Part Number and Shelf Location are blank too.
   - Location and Ownership keep Riga's own values. Location goes in the same list shape US rows use.
7. **What is read.**
   - Read the workbook with `openpyxl`, using cached values, never formulas.
   - Only the mapped columns of the mapped header row are read. Rows are read from the row below the header, and only where the serial cell is filled. So titles, legends, side tables to the right, and side tables below with an empty serial column are ignored by position, not by recognising their content.
   - **Serial numbers:** read as text. A whole number stays without a decimal point; the VXE serial is stored as a number.
   - **Dates:**
     - Excel dates become calendar dates with no time zone shift;
     - text dates are read day-first, using the mapping's formats;
     - anything that cannot be read stays blank and is counted per sheet;
     - a date written inside free text is left in the notes.
   - **A formula error** such as `#REF!` in a mapped column is blank, and counted.
8. **Row shape.**
   - The loader produces exactly the row shape `assets._clean_row()` produces, plus `site`, so the families, the readiness math and the tables work unchanged.
   - Row IDs:
     - must be integers that cannot collide with US IDs;
     - must stay the same for the same sheet and row in the same file;
     - explain the scheme in the report.
9. **Loading and reloading.** Load the workbook from `RIGA_WORKBOOK_PATH` and reload it when the file changes, as the CSV source does with its modified time.
10. **The check command: `python -m riga_loader --check PATH`.** For any workbook, it prints:
    - the sheets found, mapped, ignored and unknown;
    - the rows read per sheet;
    - the mapped headers not found;
    - the unknown condition values, with counts;
    - the dates that could not be read, and formula errors, per sheet;
    - the first 3 rows of each sheet, with serial numbers masked (for example the first 3 characters, then `***`) and notes shown only as their length;
    - the totals per family.

    It works without a running dashboard and without SharePoint settings. Its output must be safe to paste into a chat: no full serials, notes, initials or SIGN values. This is how Scott checks the real file outside the sandbox.

## Part C: Upload

11. **The page `/riga/upload`.**
    - It has a file chooser for `.xlsx`, a required "Your name" field (trimmed, at most 80 characters) and a Submit button. Link to it from the Riga view, not from the nav.
12. **Saving.**
    - The file is saved to `RIGA_WORKBOOK_PATH`. It is a new setting, with the default `data/riga/current.xlsx`; a relative path resolves against the repo.
    - Create the folder at startup in the same way as the history folder. If that fails, the Riga view and the upload page say so and the US view is unaffected.
    - **Order of steps:**
      1. Write the upload to a temporary file in the same folder.
      2. Check it.
      3. Keep the previous file as a dated backup next to it, for example `current-20261029-143012.xlsx`.
      4. Move the new file into place.
      5. Write the uploader's name, the time, the original file name and the rows per sheet to a small JSON file beside it.
13. **Rejection.** The previous file stays in place, and the page says why in plain words, if:
    - the file name does not end in `.xlsx`;
    - `openpyxl` cannot open it as a workbook;
    - it gives zero Riga rows;
    - it is larger than a limit you choose (say what it is in the report);
    - the name is empty.
14. **On the Riga view.** It shows "Uploaded by <name> on <date and time>", in the site's time zone, using the existing time formatting with no `strftime`. With no file uploaded yet, it says so, with a link to the upload page. That is not an error.
15. **Security.** The dashboard has no sign-in, so anyone who can open it can upload, and the name is whatever they type. Do not add sign-in in this prompt. Say this plainly in the report as a question for Scott.

## Part D: The overview

16. **Site switch.**
    - A US / Riga switch sits at the top of the overview. It is kept in the URL: `/?site=riga`, combined with `location`, for example `/?site=riga&location=MRO`. US is the default.
    - Each site has its own readiness, cards, Location filter values, tables and alerts.
    - The `/overview` redirect keeps passing the query string, so `site` is kept.
17. **The Riga view.**
    - The tables leave out the Status and Checked out to columns.
    - It adds an Engine table below the others, with its own Ready, Limited and Not Ready counts in the table heading.
    - The headline readiness and the family cards leave out engines.
    - A problem with the Riga workbook or mapping never breaks the US view, and the reverse.
18. **History per site.**
    - Each history line gains `"site": "US"` or `"site": "Riga"`, and the once-a-day rule applies per site.
    - Existing lines with no `site` are read as US.
    - **When Riga's line is written:**
      - on the first successful load of the workbook each day;
      - load it whenever the overview is viewed for either site, so the Riga trend fills in even on days nobody opens the Riga view;
      - with no workbook uploaded, no Riga line.
    - The trend chart shows the chosen site's lines.
19. **Riga alerts.** Use only rules that make sense without checkout data:
    - **No condition:** a new rule, for Riga only. Its title and wording are in the same style as the others. It covers Status blank or not recognised.
    - **Never inventoried** and **Inventory overdue:** only for rows from sheets that have a mapped date column. Say in the report that this date is "last updated and signed", not a physical count, as report 10 noted.
    - **PMC/NMC with no notes.**
    - The US alerts do not change.
    - The Needs Attention page is US only, so on the Riga view the alert rows show counts with no links. Note this in the report.

## Tests

Build the fixture in the tests with `openpyxl`, from made-up data, written to a temporary folder. It reproduces report 10's layout, including:
- a merged title in row 1, a merged legend in row 2 and the header in row 3;
- PPC with its header in row 2;
- a side table to the right, and one below with no serial;
- an Excel date, a `dd.mm.yyyy` text date and a date that cannot be read;
- a numeric serial;
- a header in different case (`STATUS`);
- an unknown condition value;
- a formula error in a mapped column;
- an ignored sheet, and an unknown sheet;
- an engine sheet with a mix of conditions.

Tests for:
- **The loader:**
  - rows per sheet;
  - the side tables ignored;
  - the date results and counts;
  - the unknown sheet and condition listed;
  - the missing header listed;
  - the row shape matching US rows plus `site`;
  - IDs not colliding with US IDs;
  - a mapping file that is missing or badly shaped;
  - the family cross-check mismatch giving Unmapped.
- **The check command:**
  - its sections;
  - masked serials;
  - no notes text, no SIGN values and no full serials in its output.
- **Upload:**
  - a good upload, its backup and its JSON beside it;
  - rejection for a non-`.xlsx` name, a file that is not a workbook, zero rows, a file too large and a blank name, each leaving the previous file in place.
- **Sites:**
  - `/` defaults to US;
  - `/?site=riga` shows Riga only;
  - the Location filter within a site;
  - US pages and the JSON show no Riga rows;
  - a broken Riga file leaves the US view working.
- **Engines:** they are left out of the headline readiness and the cards, but present in their table and in the history counts.
- **History:**
  - one line per site per day;
  - old lines with no site read as US;
  - no Riga line without a workbook;
  - the trend per site.
- **Riga alerts:** only the four rules; the inventory rules skip sheets without a date column.

All 163 existing tests must still pass, changed only where `asset_families.json` grew. Run the whole suite, then again with `PYTHONTZPATH=""`.

## Report

Write `reports/11_riga_tab.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What was built,** file by file, including the full `riga_mapping.json` explained in words, and the row ID scheme.
- **The fixture:** what it covers, mapped to report 10's findings one by one, and anything in report 10 it does not cover.
- **The Riga view,** described panel by panel for the fixture. Do not commit screenshots.
- **Test results** for both runs.
- **Before trusting Riga numbers:** say plainly that the real workbook has not been loaded yet. Scott runs `python -m riga_loader --check <path>` on the real file and pastes the output into a session. Any header or value differences are then fixed in `riga_mapping.json`, with no code change.
- **PROD apply notes.** Do not perform the apply and do not change `deploy/`. Cover:
  - **the new setting** `RIGA_WORKBOOK_PATH`, with the recommended PROD value `C:\Users\slovett\apps\asset_data\riga\current.xlsx`. It sits outside the repo, like the history file, so uploads survive a re-clone and real data cannot be committed;
  - **the folder** to create;
  - **backups,** which grow with every upload;
  - **what to check** after the restart.
- **Questions for Scott,** at least:
  - the tracking antenna's family;
  - whether Riga rows should ever appear on Inventory, Needs Attention, Checkouts and Metrics;
  - the upload page being open to anyone who can reach the dashboard;
  - how many backups to keep;
  - whether US should also get the "No condition" alert;
  - report 10 question 1 (is the sample the full workbook), still open.
