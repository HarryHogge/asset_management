# Report 11: Riga tab fed from the Excel workbook

## Start

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `2e38b07` ("Add prompt 11"), after `git pull`.
- **Where it ran:** the sandbox. DEV only: nothing was applied to PROD, and `deploy/` was not changed. `docs/decisions.md` was not changed.
- **No real Riga data.** The real workbook was not available here and is not in the repo. Everything was built from report 10's description, and tested against a made-up workbook that the tests build themselves.

## What was built

### `riga_loader.py` (new)

- **`read_mapping()`** reads and checks `riga_mapping.json`. A missing file, bad JSON or a wrong shape gives a clear reason, for example "sheet MK2 needs a header_row of 1 or more" or "the Status BROKEN maps to 'Fine', which is not one of FMC, PMC, NMC, Destroyed/Lost".
- **`read_workbook()`** reads the workbook with `openpyxl` in read-only mode, using cached values and never formulas. For each mapped sheet:
  - it finds the header row given in the mapping, and the six mapped headers in it, ignoring case and surrounding spaces but not spelling;
  - it reads from the row below, and only rows whose serial cell is filled. Only the mapped columns are read, so titles, legends, side tables to the right and side tables below with no serial are skipped because of where they are;
  - serials are read as text. A whole number has no decimal point, so VXE's numeric serial `4417` reads as `4417`;
  - **dates:**
    - an Excel date becomes a calendar date with no time zone shift;
    - text is read day first, as `dd.mm.yyyy` or `dd.mm.yy` (a one-digit day or month such as `6.3.2026` is accepted too);
    - anything else is blank and counted for that sheet;
    - a date inside the notes stays in the notes;
  - a formula error such as `#REF!` in a mapped column is blank and counted. An error in the serial column means the row is skipped and counted;
  - the Status value is matched case-sensitively after trimming spaces. A value not in the map gives no condition, and is counted.
- **`findings()`** turns what was found into plain sentences for the log and the Riga view. Examples are "Sheet Notes 2026 is not in riga_mapping.json and was skipped." and "Status "NFC ISSUES" on 1 row(s) is not in riga_mapping.json, so those rows have no condition." They name sheets, headers and Status values, never row contents.
- **`cross_check()`** compares each sheet's family in the mapping with `asset_families.json`, which decides.
  - If the two disagree, or the type is missing from the family file, that type is left out of the families used for Riga, so its rows are Unmapped.
  - The log (once per change), the Riga view and the check command say so.
- **`attention()`** gives the four Riga alerts (see "The Riga view").
- **`RigaSource`** is the source the app uses.
  - It reads the workbook again when its modified time or size, or the mapping file, changes, in the same way the CSV source watches its modified time.
  - Its `load()` never raises. It answers with one of these states: off (folder could not be made), mapping problem, none uploaded, unreadable, or OK.
  - A problem is logged once, and again only when it changes.
- **`save_upload()`** does the upload steps described under "Upload".
- **The check command,** `python -m riga_loader --check PATH`, is described under "Before trusting Riga numbers".

### `riga_mapping.json` (new), in words

- **`date_formats`:** `dd.mm.yyyy` and `dd.mm.yy`. Only these two names are allowed, so the file cannot hold a US month-first format by mistake.
- **`conditions`:**

  | Riga Status | Condition |
  |---|---|
  | RTF | FMC |
  | RTF WITH REMARKS | PMC |
  | FCF REQUIRED | PMC (Scott's answer) |
  | GROUNDED | NMC |
  | WRITTEN OFF | Destroyed/Lost |

- **`ignored_sheets`:** VEHICLES, ZALENIEKI STOCK and OVERALL.
- **`sheets`:** the 10 equipment sheets, in this order. The order matters for row IDs, so new sheets go at the end.

  | # | Sheet | Asset Type | Family | Header row | Status header | Owner header | Notes header | Date header |
  |---|---|---|---|---|---|---|---|---|
  | 1 | Mk2.x | Penguin C Mk2.x | Aircraft | 3 | Status | Asset owner | Actions/Defects | INFO UPDATE |
  | 2 | MK2 | Penguin C Mk2 | Aircraft | 3 | Status | Asset owner | Actions/Defects | INFO UPDATE |
  | 3 | 2.5 VTOL | Penguin C Mk2.5 VTOL | Aircraft | 3 | Status | Asset owner | Actions/Defects | INFO UPDATE |
  | 4 | MK3 | Penguin C Mk3 VTOL | Aircraft | 3 | Status | Asset owner | Actions/Defects | INFO UPDATE |
  | 5 | VXE | VXE (Riga) | Aircraft | 3 | Status | Asset owner | NOTES | INFO UPDATE |
  | 6 | EPS | Epsilon Gimbal | Payload | 3 | STATUS | Asset Owner | Actions/Defects | Date |
  | 7 | TRC | Tracking Antenna | Support | 3 | Status | Asset Owner | Actions/Defects | DATE |
  | 8 | PPC | Catapult | Support | 2 | Status | Asset Owner | INFO | Date |
  | 9 | GCS | Ground Control Station (Riga) | Ground Control Station | 3 | STATUS | Asset Owner | INFO: | (none) |
  | 10 | ENG | Engine | Engine | 3 | Status | Asset Owner | Actions/Defects | INFO UPDATE |

  Every sheet reads its serial from `S/N` and its location from `Location`. GCS has no date column, so its date is `null`.
- **`about`:** one line saying where the file is explained.

### Row ID scheme

A Riga row's ID is **minus (sheet number × 10,000,000 + Excel row number)**. The sheet number is the sheet's place in `riga_mapping.json`, counting from 1. For example, the first data row of Mk2.x (sheet 1, Excel row 4) is `-10000004`.

- **No collisions.** US IDs are SharePoint item IDs or CSV row positions, and both are always positive. An Excel sheet has at most 1,048,576 rows, which is less than 10,000,000, so two Riga IDs can never be equal either.
- **Stable.** The ID is the same for the same sheet and row in the same file. It changes if rows are inserted above, which is fine because nothing stores Riga IDs.
- **No effect on export.** The Excel export's `?ids=` only accepts positive numbers. Riga rows are not on Inventory anyway.

### `app.py`

- **New setting `RIGA_WORKBOOK_PATH`.** It defaults to `data/riga/current.xlsx`, and a relative path resolves against the repo.
  - `make_riga()` makes the folder at startup, as `make_history()` does for the history file.
  - If the folder cannot be made, the log says so once and the Riga view and upload page say so until a restart. The US view is not affected.
  - The startup banner prints `Riga workbook: <path>`, or `Riga workbook: OFF until restart, because ...`.
- **`/` reads `?site=`.**
  - `riga` gives the Riga view. Anything else, including nothing, gives the US view, exactly as before.
  - The Riga workbook is loaded on every overview view, for either site, so Riga's history line is written even on days nobody opens the Riga view.
  - A failure loading Riga, even an unexpected one, is caught and logged, and never breaks the US view.
- **`/overview`** still redirects with the query string, so `site` and `location` are kept.
- **New page `/riga/upload`** (GET shows the form, POST uploads).
- **Request size limits.**
  - Every request now has an outer size limit of 11 MB. Only uploads come near it.
  - A larger upload is answered on the upload page with "The file is larger than the 10 MB limit."
- **Riga time zone.** Riga's time zone is fixed in the code as `Europe/Riga`, not a setting. It is used for the upload time, for Riga's "today" in the alerts, and for Riga's history day.

### `fleet.py`

- **Engine family.** Engine is a fifth family. `read_families()` accepts it, and Unmapped is still only the fallback.
- **Headline readiness.** The headline (`overall`) now leaves out the Engine family. The family cards and the trend lines were already only Aircraft, Ground Control Station and Payload. US numbers do not change, because the US list has no engines.
- **History per site.**
  - Each history line has `"site": "US"` or `"site": "Riga"`, and the one-line-a-day rule is applied per site, also after a restart.
  - A line with no `site` is a US line.
  - `entries(site)` gives one site's lines for its trend.
  - The line's family counts still include Engine.

### `assets.py` and `sharepoint.py`

- **US rows get `site: "US"`.** This applies to both the CSV and the SharePoint source.
- **The JSON endpoints leave `site` out.** They only ever hold US rows, and leaving it out keeps their answers byte for byte as before. This is also why the CSV fingerprint test still passes unchanged.

### `asset_families.json`

The 29 US entries are unchanged and still come first. The 10 Riga entries from the prompt's table are added after them. Tracking Antenna is in Support, pending Scott's answer (question 1).

### Templates

- **`base.html`:** the "Data from ..." line is now in a block, so the Riga view can word it for Riga.
- **`overview.html`:**
  - the site switch;
  - the Riga notes;
  - the Riga version of each panel, described below;
  - the Engine table.
- **`riga_upload.html` (new):** the upload page.

### Tests, README and `example.env`

- **New `tests/riga_fixture.py`:** builds the made-up workbook.
- **New `tests/test_riga.py`:** 61 tests.
- **README:** a new "Riga" section, and notes in Pages, Asset families and the history section.
- **`example.env`:** documents `RIGA_WORKBOOK_PATH`.
- **`tests/conftest.py`:** points `RIGA_WORKBOOK_PATH` at a temporary folder, so tests never write to `data/`.

## The fixture

`tests/riga_fixture.py` writes a 14-sheet workbook with made-up serials (`TST-...`), notes and initials. Mapped to report 10's findings:

| Report 10 finding | In the fixture |
|---|---|
| 13 sheets: 10 equipment, VEHICLES, ZALENIEKI STOCK, OVERALL | All 13, plus one sheet the mapping does not know ("Notes 2026") |
| Merged title in row 1, merged legend in row 2, headers in row 3 | On every equipment sheet except PPC |
| PPC headers on row 2 | Yes |
| Headers differ in case and wording | `STATUS` on EPS and GCS; VXE writes `STATUS` where the mapping says `Status`; `Asset owner` and `Asset Owner`; `Insurance due` on VXE |
| Status column in different places | Column E on aircraft sheets, D on TRC, B on GCS |
| Notes headers NOTES, INFO, INFO: | VXE, PPC, GCS |
| GCS has no date column | Yes, and the inventory alerts skip it |
| Side tables to the right | 2.5 VTOL columns W to Y, TRC's count table in M and N (including the `GRTF WITH REMARKS` typo), ENG's marker columns L and M |
| Side table below with no S/N | 2.5 VTOL rows 21 to 25 |
| Excel dates, `dd.mm.yyyy` text dates, mixed in one column | ENG holds both; Mk2.x, MK3, PPC have Excel dates; MK2, VXE, EPS, TRC have text dates |
| Text dates `dd.mm.yy` | One on TRC |
| A date that cannot be read | 2.5 VTOL: `last spring` |
| Dates inside the notes | Mk2.x notes start with `dd.mm.yyyy:` |
| VXE serial stored as a number | `4417`, stored as a number |
| `NFC ISSUES` (not in the list) | On EPS |
| `#REF!` results | In MK3's Location (a mapped column), and in Mk2.x's Equip. Rediness (not mapped, so not counted) |
| A mapped header missing | MK2 calls its owner column "Owner" |
| FCF REQUIRED, RTF WITH REMARKS, WRITTEN OFF | On MK3, 2.5 VTOL and ENG |
| Engines with a mix of conditions | 5 engines: 2 RTF, 2 GROUNDED, 1 WRITTEN OFF |
| Frequency as a number | On MK3 and TRC (not read) |
| SIGN initials, a number plate, a part number | In SIGN, VEHICLES and STOCK, to prove the check command never prints them |

**Not covered:**

- **Formula cells with cached results.** `openpyxl` cannot write a formula together with a cached result, so the fixture's `#REF!` cells are stored error values rather than formulas whose last result was `#REF!`.
  - Excel saves cached results, so the real file should behave the same.
  - But a formula in a mapped column that Excel never calculated would read as blank. The check command would show that as blank fields.
- **Not reproduced because they are never read:** choice lists on row 4 only, conditional formatting and cell colors, and the insurance columns.
- **The Latvian note.** Non-English text in notes is not tested specifically. Notes are read as plain text, so any language passes through.
- **Size.** Row counts are small, not the 36 engines and 82 stock lines of the sample.

## The Riga view, for the fixture

Opening `/?site=riga` after uploading the fixture shows, from top to bottom:

1. **Page heading** "Fleet Overview", with an **Upload Riga workbook** button at the top right.
2. **The "Data from" line:** "Data from **Riga workbook riga_assets.xlsx**, uploaded <date and time>. Times and dates are in Riga's time zone."
3. **The US / Riga switch,** with Riga highlighted. US links to `/?site=us`, which is the same as `/`.
4. **A note listing the workbook's problems,** with the rows still shown:
   - Notes 2026 skipped;
   - MK2 has no "Asset owner" column;
   - 2.5 VTOL has 1 unreadable date;
   - MK3 has 1 formula error;
   - "NFC ISSUES" on 1 row.
5. **The Location filter:** Riga's own values (DEMO, Field, MRO, Nakotne, and No location for the `#REF!` row). The choice is kept with the site, for example `/?site=riga&location=Field`, which shows "Showing 4 assets and 1 engine at Field".
6. **Riga Fleet Readiness:** 58% (7 Ready, 2 Limited, 2 Not Ready, 1 No condition), with "12 assets in all, engines not included".
7. **Family cards:**
   - Aircraft: 6, readiness 50% (3 Ready, 2 Limited, 1 Not Ready);
   - Ground Control Stations: 1, 100%;
   - Payloads: 1, 0% (1 No condition).
8. **Support and Unmapped:** Support 4 assets, readiness 75% (the tracking antennas and the catapult); Unmapped 0.
9. **Last Updated:** the upload time, then "Uploaded by Test Person on <date and time>, from riga_assets.xlsx. In Riga's time zone.", with a link to upload a new one.
10. **Tables for Aircraft (6), Ground Control Stations (1) and Payloads (1).**
    - The columns are Serial Number, Asset Type, Location, Condition and Notes; Status and Checked out to are left out.
    - Support has no table, the same as on the US view (question 8).
11. **Engines (5),** with "2 Ready, 0 Limited, 2 Not Ready" in the heading, in the same columns.
12. **Alerts.** Four rows, as counts with no links, and a line saying the Needs Attention page covers US assets only. On October 29, 2026:
    - Never inventoried 3;
    - Inventory overdue 3;
    - PMC/NMC with no notes 2;
    - No condition 1.
13. **Readiness Trend:** one point at 58% today. The note says the trend fills in one point per day, and "All of Riga: the Location filter does not change this chart."

**When the Riga view cannot show anything,** it shows the switch and one short note, not an error page.

| Situation | Note shown |
|---|---|
| No workbook uploaded yet | "No Riga workbook has been uploaded yet." with a link to the upload page |
| Workbook folder could not be made | That the Riga view is off until a restart |
| Mapping file broken | That `riga_mapping.json` could not be read |
| Workbook file damaged | That the workbook could not be read, with a link to upload it again |

Each note says the US view is not affected, and the log gives the reason once.

**The US view** (`/`, or `/?site=us`) is as before, with the switch added above it. It still reads 83% for the committed export.

**No screenshots were committed.** The ui-tester checked the pages at 1440 and 390 pixels wide, in both themes; see "Visual check".

## Upload

- **The form** at `/riga/upload` has:
  - a file chooser limited to `.xlsx`;
  - "Your name" (required, at most 80 characters, trimmed);
  - Submit.
  - It also shows who uploaded the current workbook and when.
- **The steps,** under one lock:
  1. Write the upload to a temporary file in the same folder (`.upload-*.part.xlsx`; `openpyxl` only opens names ending in `.xlsx`).
  2. Check it: it must open as a workbook and give at least one Riga row.
  3. Copy the current file to a dated backup beside it, for example `current-20261029-143012.xlsx`. If that name is taken, `-2` is added.
  4. Move the new file into place with one `os.replace`.
  5. Write `current.upload.json` beside it, holding the name, the time with its offset, the original file name, the size and the rows per sheet.
- **Rejections.** In each case the page says "Not uploaded: <reason> The previous workbook is still in use.", and the previous file is untouched:
  - the name does not end in `.xlsx`;
  - the file cannot be opened as a workbook;
  - none of the mapped sheets has a row with a serial number;
  - the file is larger than **10 MB**. The sample workbook is far smaller; this limit only stops a wrong file;
  - the name is blank or longer than 80 characters.
  - Two more cases are also refused:
    - the mapping file is broken, so the file cannot be checked;
    - the new file cannot be moved into place, for example because the workbook is open on the server.
- **Leftovers.** The temporary file is always removed.
- **Security.** The dashboard has no sign-in, so anyone who can open it can upload, and the name is whatever they type. Sign-in was not added. See question 3.

## Test results

- **Plain run:** `python -m pytest`: **224 passed** (163 existing, 61 new).
- **Run with `PYTHONTZPATH=""`:** **224 passed**.

**Existing tests changed** (two, both in `tests/test_fleet.py`):

1. **`test_committed_family_file_matches_report_05`** now checks that the first 29 entries are exactly report 05's, in order, and that the rest are exactly the 10 Riga entries. This is because `asset_families.json` grew.
2. **`test_family_readiness_covers_all_five_families`** now expects `Engine` in the list of families.
   - This one changed because of the new Engine family, not because `asset_families.json` grew. It is the only change outside what the prompt foresaw.
   - It could not be avoided, since the prompt asks for Engine as a family.

**One change was avoided by a choice in the template.** An existing test allows only "Fleet Overview" and "Show all" links to `/`. So the US side of the switch links to `/?site=us`, which shows the same US view.

The CSV fingerprint test and every other existing test pass unchanged.

## Visual check

The ui-tester opened the Riga view, the upload page and the US view at 1440 and 390 pixels wide. The scratch app was on port 5071, with the made-up workbook. The results are below; nothing was saved to the repo.

- **No sideways scroll and no console errors** on any of the three pages, at either width. The light theme was checked on the Riga view at 1440: it is readable, with nothing overlapping, and no text below 3 to 1 contrast.
- **Every Riga panel listed above is present and in order.** The Engines heading reads "2 Ready, 0 Limited, 2 Not Ready" against a badge of 5; the fifth engine is Destroyed/Lost.
- **Fixed: at 390 wide the Alerts and Readiness Trend cards did not stack.** They were squashed side by side, on the US view too.
  - **Cause:** this came from prompt 06's layout. The phone-width rule for `.grid-bottom` came before `.grid-bottom`'s own rule in the stylesheet, so it lost.
  - **Fix:** a phone-width rule placed after it.
  - **Rechecked:** both cards are 358 px wide and stacked on both views.
- **Fixed: trend points at 0% and 100% were half cut off** at the chart's top and bottom edges. They are now drawn whole.
- **Fixed: the upload page heading almost touched the first card.** The gap is now 18 px.
- **Tables at 390 wide** scroll inside their own box, as on the US view, and the page itself does not.

## Before trusting Riga numbers

**The real workbook has not been loaded yet.** Everything above was built and tested against report 10's description and a made-up workbook. Report 10's question 1 (whether the sample is the full workbook) is still open.

Before anyone relies on the Riga view:

1. Scott runs the check on the real file, outside the sandbox. On the Mac (from the repo folder, with the venv):

   ```
   .venv/bin/python -m riga_loader --check data/samples/riga_assets.xlsx
   ```

   On Windows:

   ```
   .venv\Scripts\python -m riga_loader --check "C:\path\to\riga workbook.xlsx"
   ```

   It needs no running dashboard and no SharePoint settings. It prints:
   - the sheets found, mapped, ignored and unknown;
   - rows per sheet;
   - mapped headers not found;
   - unknown Status values with counts;
   - unreadable dates and formula errors per sheet;
   - the first 3 rows of each sheet. Serials are masked, for example `TST***`, and notes are shown only as their length. SIGN, initials, number plates and part numbers are never read;
   - the totals per family, and the headline readiness without engines.
2. Scott pastes the output into a session.
3. Any header name, sheet name or Status value that differs is fixed in `riga_mapping.json` only, with no code change.

## PROD apply notes

Nothing here was applied, and `deploy/` was not changed. A later runbook prompt can turn these notes into a Part F.

- **New setting.** Add this to `.env`, without quotes:

  ```
  RIGA_WORKBOOK_PATH=C:\Users\slovett\apps\asset_data\riga\current.xlsx
  ```

  It sits outside the repo folder, like the history file. That way uploads survive a re-clone, and real Riga data can never be committed.
- **The folder.** `C:\Users\slovett\apps\asset_data\riga`. The dashboard creates it at startup, but making it first proves the `slovett` account can write there:

  ```
  New-Item -ItemType Directory -Force C:\Users\slovett\apps\asset_data\riga
  ```

- **Backups.** Every upload after the first keeps the previous workbook as `current-YYYYMMDD-HHMMSS.xlsx` in that folder. Nothing deletes them, so the folder grows by one workbook per upload, about the size of the sample each time. See question 4.
- **No new packages.** `openpyxl` is already installed. The usual pull and `pip` line from Part B is enough.
- **What to check after `pm2 restart asset-management`:**
  1. The log (`pm2 logs asset-management --nostream`) shows `Riga workbook: C:\Users\slovett\apps\asset_data\riga\current.xlsx`. It must not show `OFF until restart`.
  2. `http://localhost:5070/` looks as before (the US view), with the US / Riga switch at the top.
  3. `http://localhost:5070/?site=riga` says "No Riga workbook has been uploaded yet." with a link. This is not an error.
  4. After running the check command (above) on the real file and fixing the mapping if needed, upload it at `/riga/upload`. The Riga view should then show "Uploaded by <name> on <date and time>", and `Test-Path C:\Users\slovett\apps\asset_data\riga\current.upload.json` returns `True`.
  5. Inventory, Needs Attention, Checkouts, Metrics and Export to Excel still show US assets only.

## Questions for Scott

1. **Decided** (see "Decisions (prompt 12)"). **Tracking antenna family.** It is in **Support** for now; report 10 offered Ground Control Station or Support. Which one?
2. **Decided** (see "Decisions (prompt 12)"). **Riga on other pages.** Should Riga rows ever appear on Inventory, Needs Attention, Checkouts and Metrics, for example with a site filter? Today they are only on the overview's Riga view.
3. **Decided** (see "Decisions (prompt 12)"). **Who can upload.** The upload page is open to anyone who can reach the dashboard, and the name is whatever they type. Is that acceptable on the PROD network, or should uploads be limited (for example by sign-in, or only from the server itself)?
4. **Decided** (see "Decisions (prompt 12)"). **Backups.** How many should be kept? Today every one is kept. A limit, for example the last 20, is easy to add.
5. **Decided** (see "Decisions (prompt 12)"). **"No condition" for the US.** Should the US also get the "No condition" alert? Today a blank Material Condition lowers US readiness, but no US alert lists it.
6. **Open with Riga** (see "Decisions (prompt 12)"). **The full workbook (report 10 question 1).** Still open: is the sample the full workbook? The check command on the real file answers most of it.
7. **Decided** (see "Decisions (prompt 12)"). **New.** **Support on the Riga view.** Tracking antennas and the catapult (4 in the fixture) are counted in the Support card but have no table, the same as US Support kits. Should Riga's Support get a table, as engines do?

## Decisions (prompt 12)

Scott's answers to the questions above. They are final.

| Question | Decision |
|---|---|
| 1. Tracking antenna family | Stays **Support** |
| 2. Riga on other pages | Riga rows appear **only on the overview** for now |
| 3. Who can upload | **No sign-in** is needed for uploads on PROD |
| 4. Backups | Keep the **20 most recent** (done in prompt 12) |
| 5. "No condition" for the US | **Yes** (done in prompt 12) |
| 6. Is the sample the full workbook? | **Still open, with the Riga team** |
| 7. Support table on the Riga view | **Yes** (done in prompt 12) |
