# Report 06: Fleet Overview page

## Start

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `5247bb9` ("Add prompt 06"), after `git pull`.
- **Where it ran:** the sandbox. Nothing on PROD, and `deploy/` is unchanged.

## What was built

| File | What changed |
| --- | --- |
| `reports/05_asset_family_mapping.md` | Moved with `git mv` from `docs/reports/05-asset-family-mapping.md`, unchanged. `docs/reports/` is gone. |
| `asset_families.json` (new) | The 29 Asset Types from report 05's Step 3 table, each with its "Proposed family" exactly as written: 4 Aircraft, 3 Ground Control Station, 7 Payload, 15 Support. |
| `fleet.py` (new) | Everything the page computes: reading the family file, family lookup, readiness math, table order, the Location filter, the alerts list, the daily history and the trend. |
| `app.py` | New `/overview` route, first in the nav. New setting `READINESS_HISTORY`. Every successful data load, on any page, offers the day's line to the history. The startup banner prints the history path. `/` is still Inventory. |
| `templates/overview.html` (new) | The page. |
| `templates/base.html` | A switch, `left_nav`, that the route turns on: the page then gets a left nav built from the same `PAGES` list, with the Theme button in it. Other pages keep the header nav. |
| `.gitignore` | `data/` added. |
| `example.env`, `README.md` | `READINESS_HISTORY` explained. The README has a new Fleet Overview section: the readiness rule, how to add a type to the family file, and how the history fills in. |
| `tests/conftest.py` | Points `READINESS_HISTORY` at a temporary folder (deleted when the tests end), so the suite never writes to `data/` in the repo. |
| `tests/test_fleet.py` (new) | 37 tests. |
| `tests/test_pages.py` | `/overview` added to the pages every existing test walks: both sources, and every bad-setting case. |

### How the main pieces behave

- **Family file.**
  - It is read at each page view, so an edit shows without a restart.
  - The reader refuses: a file that is not a set of Asset Types; an empty set; a blank type; a type named twice; and a family that is not one of the four.
  - If the file is missing or refused, every asset is Unmapped. The page shows a short note, and the log gets the reason once, then again only when it changes.
  - The match is on the exact text. "VXE30" or "VXE-30 " (with a trailing space) are Unmapped, not Aircraft.
- **Unknown Material Condition.** The list has four conditions. If someone adds a fifth choice in SharePoint, assets with it are counted as "Other condition": in the total, not Ready, and shown on the cards. They are not dropped or treated as blank.
- **History.**
  - **What it holds:** one JSON line per day, in UTF-8 with `\n` endings. The line is written under a lock, because waitress serves several requests at once.
  - **Once a day:** before writing, the code reads the last date from the file itself, so a restart on the same day writes nothing.
  - **SharePoint source:**
    - a stale copy is not recorded;
    - nor is a copy fetched on an earlier day;
    - the first fresh fetch of the day is recorded.
  - **CSV source:** the export is recorded as it is, whatever its date.
  - **Problems:**
    - A failed data load records nothing.
    - A failed write leaves every page working. `/overview` shows a short note, the log gets the cause once, and the write is tried again on the next load.
    - Lines that cannot be read are left out of the trend, with one log line.
- **One line, as written for the committed export:** `date`, `recorded_at`, `source`, `total`, `fmc`, `pmc`, `nmc`, `destroyed_lost`, `no_condition`, `other_condition` and `readiness_pct`, plus the same nine numbers (`total` to `readiness_pct`) for each of the five families. It holds counts only: no serial numbers, names or notes.

## The page

Numbers below are for the committed export (`Asset Tracking V2.csv`, 146 rows) with no filter. No screenshots are committed. I viewed the page in a browser at 1440 and 390 pixels wide, in both themes, with no console errors. The first look found the page running off the right edge. That was fixed, and checked again with no sideways scrolling at either width.

**Left nav.** Fleet Overview (active), Inventory, Needs Attention, Checkouts, Metrics, and the Theme button. Below 900 pixels wide it folds into a short bar across the top.

**Location filter.** A dropdown above the cards, using the list's own 13 choices in the list's order:
- HSV Flight Ops (74 assets)
- SLO Flight Ops (6)
- HSV ENG (10)
- No Verified Location (2)
- HSV LRR Internal (19)
- Global Support (3)
- SLO ENG (14)
- Anduril (1)
- CACI (1)
- Gimbal Gauntlet HSV (10)
- LRLE (1)
- RDT UK (1)
- Secret Service (1)

"No location" is added because 4 assets have none. One asset has two locations and is counted under both. Picking a choice reloads the page as `/overview?location=SLO+ENG` (and so on), so a filtered view can be linked. "No location" is `?location=(none)`.

**Top row.**

| Panel | Shows |
| --- | --- |
| Overall Fleet Readiness | Doughnut, **83%** in the middle (120 / (146 - 2)). 120 Ready, 8 Limited, 16 Not Ready; 2 Destroyed/Lost in gray beside it; 146 assets in all |
| Aircraft | 16 assets, readiness 88% (87.5%): 14 Ready, 1 Limited, 1 Not Ready |
| Ground Control Stations | 25 assets, readiness 88%: 22 Ready, 3 Limited, 0 Not Ready |
| Payloads | 43 assets, readiness 68% (28 / 41): 28 Ready, 3 Limited, 10 Not Ready, 2 Destroyed/Lost |
| Support and Unmapped | Support 62 assets, readiness 90%. Unmapped 0 assets, readiness shown as a dash. No types to list, since all 26 types in use are in the file |
| Last Updated | The export's time and "Exported from SharePoint". For the CSV source this is the file's modified time on the machine (10/19/2026 8:10 AM in the sandbox); with SharePoint it is the fetch time and says "Fetched" |

**Middle row.** Three full-width tables: Aircraft (16 rows), Ground Control Stations (25), Payloads (43).
- **Columns:** Serial Number, Asset Type, Location, Condition, Status, Checked out to, Notes.
- **Order:** Not Ready, Limited, Ready, No condition, Destroyed/Lost; then by Asset Type, then Serial Number. For example, the Payloads table opens with its 10 NMC rows and ends with its 2 Destroyed/Lost rows.
- **Pills:**
  - Condition pills use the readiness colors (`--good`, `--warn`, `--bad`, `--lost`) and show the list's own value (FMC, PMC, NMC, Destroyed/Lost, or "No condition"). Hovering a pill gives Ready, Limited or Not Ready.
  - Status, Location and Asset Type pills use the list's colors, as on the other pages.
- **Notes:** cut to one line; hovering shows the full text.

**Bottom row.**
- **Alerts:** 138 data problems in all, counted as on `/attention`. One asset can have several problems. The first 5 are shown, in the page's order, and all come from the first rule, "Out, but not checked out to anyone" (7 rows). Each shows its problem title, Asset Type and serial number, and there is a "View all" link to `/attention`.
- **Readiness Trend:** a line chart of the last 7 days, with all 7 dates on the axis and a gap for any day with no line. It has four lines: Overall, Aircraft, Ground Control Station, Payload. With one point or none it says: "The trend fills in one point per day: the first good data load of each day adds that day's numbers." It also says the chart is fleet-wide and the Location filter does not change it.

The Location filter applies to the cards, the doughnut, the tables, the Support and Unmapped card and the alerts. It does not apply to the trend, and the history always records the whole fleet.

**How a blank condition affects the percentage.** An asset with no condition stays in the total and is not Ready, so it lowers readiness. The committed export has none. One blank-condition asset added to today's fleet would take readiness from 83.3% (120 / 144) to 82.8% (120 / 145). Leaving such assets out of the total instead would hide them from the number. That choice is a question below.

## Thin data

- **The trend starts with one point.** A line needs two days, so the chart shows a single dot per series at today's date until tomorrow's first load adds a second. It takes 7 days to fill. The history is made going forward; past days cannot be rebuilt from the export.
- **Block 40 rows that may be stands.** All 4 Block 40 rows are FMC and count as Aircraft, as report 05 proposed. If 2 of them are stands, the Aircraft card shows 16 where 14 may be true, and Aircraft readiness would be 12 / 14 = 85.7% instead of 87.5%. The page cannot tell a stand from an aircraft; only a different Asset Type in SharePoint can.
- **Blank Status.** 21 of 146 assets have no Status, so their Status cell in the tables is empty. They are also the 21 rows of the "No status" alert.
- **Check Out By/To.** It is filled on only 23 of 146 assets, while 26 are marked OUT. 7 OUT assets have nobody listed, and 4 assets list a holder but are not OUT. So the "Checked out to" column is mostly empty, and it is not a full record of who has what.
- **No condition.** Material Condition is filled on all 146 rows, so the "No condition" count and its group in the tables are empty today.
- **Unmapped.** Empty today. The card fills in only when a new Asset Type appears in SharePoint.

## Test results

- Whole suite: **112 passed** (73 existing, 37 new in `tests/test_fleet.py`, and 2 new `/overview` cases in the existing page walk).
- Again with `PYTHONTZPATH=""`: **112 passed**.
- After the runs, `git status` shows no `data/` folder in the repo.

## What a PROD apply would involve

This was not done, and `deploy/` is unchanged.

- **Files to pull:**
  - new: `fleet.py`, `asset_families.json`, `templates/overview.html`;
  - changed: `app.py`, `templates/base.html`, `.gitignore`, `example.env`, `README.md`;
  - moved: report 05;
  - tests.
- **Packages:** none new. The page uses the Chart.js copy already in `static/vendor/`.
- **New setting:** `READINESS_HISTORY`. It is optional, with the default `data/readiness_history.jsonl` inside the app folder.
- **Where the history should live on PROD.** I recommend outside the repo folder, for example `READINESS_HISTORY=C:\Users\slovett\apps\asset_data\readiness_history.jsonl`, written without quotes, as `example.env` says for paths. The reasons:
  - **It must survive a re-clone.** The runbook clones into `C:\Users\slovett\apps\asset_management`. Deleting and cloning that folder again would lose every day of history, and those days cannot be rebuilt.
  - **It is made from list data.** `data/` is git-ignored, but outside the folder it cannot be swept into a commit by mistake.
  - **The folder is created on the first write.** The account PM2 runs the dashboard under needs write access there. Under the user's own `apps` folder it should have it. If not, `/overview` shows the note and the log names the cause.
- **Then:** `pm2 restart asset-management`, open `/overview`, and check that the history file has one line. A runbook part for this would go in `deploy/` when Scott asks for it.

## Questions for Scott

1. **Left nav on every page.** Only `/overview` has the left nav for now. Should Inventory, Needs Attention, Checkouts and Metrics move to it too? It is a one-line switch per page, plus checking that the wide Inventory table still fits beside the nav.
2. **The front page.** Should `/overview` replace Inventory at `/`? Then Inventory would move to `/inventory`, and old bookmarks to `/` would open the overview.
3. **A blank condition.** Today it stays in the total and lowers readiness. Should it instead:
   - stay in the total, as now (it counts as not ready until someone fills it in);
   - be left out, like Destroyed/Lost; or
   - be left out, with a warning count on the card?
4. **Block 40 stands.** Report 05's question still stands. Until the list gives stands their own Asset Type, they count as aircraft here.
5. **Light-theme pills.** A few of the list's own pill colors (for example SLO ENG, Global Support, RMA and Mod A Kit) are pale on a white background. They match SharePoint's colors, so I left them as they are. Say if the dashboard should darken them in the light theme.
