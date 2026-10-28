# Prompt 06: Fleet Overview page

Runs in: Sandbox
Type: Build
Output: code, tests, `asset_families.json`, README and `example.env` changes, plus `reports/06_fleet_overview.md`, committed with the message "Prompt 06: Fleet Overview page" and pushed to `agent/wednesday`. Nothing on PROD and no change to `deploy/`.

Read `CLAUDE.md`, `docs/decisions.md` and the report 05 mapping first.

## Background

Report 05 proposed a family for each Asset Type in the list, and Scott has approved its "Proposed family" column as written. This prompt builds a Fleet Overview page from that mapping.

Facts checked on the local machine at commit `ee61c30`, before this prompt was written:

- **Report 05's location.** It was written to `docs/reports/05-asset-family-mapping.md`, not to `reports/` like reports 01 to 04.
- **Tests.** The suite has 73 tests, all passing.
- **Chart library.** Chart.js 4.4.1 is already vendored at `static/vendor/chart-4.4.1.umd.js` and used by `/metrics`.
- **Navigation.** It is a row of buttons in the header (`PAGES` in `app.py`, drawn in `templates/base.html`). There is no left nav today.
- **Condition data.** In the committed export, Material Condition is filled on all 146 rows. A blank condition is still possible in the live list.
- **Location.** It is a multi-choice column, so one asset can have several locations.

## Task

### 0. Move report 05

Move `docs/reports/05-asset-family-mapping.md` to `reports/05_asset_family_mapping.md` with `git mv`, to match the other reports. Change nothing inside it. Remove `docs/reports/` if it is then empty.

### Part A: the mapping file

1. **Create `asset_families.json`.**
   - It holds one entry per Asset Type in report 05's Step 3 table, all 29 of them.
   - Each entry maps to Aircraft, Ground Control Station, Payload or Support, using the "Proposed family" column exactly as written.
   - Load it the same way as `pill_colors.json`: a path next to the app, and a reader function that rejects a file in the wrong shape. A wrong shape includes a family that is not one of the four.
2. **Unmapped types.**
   - Any Asset Type not in the file, including a blank one, belongs to a fifth family, Unmapped. Never silently default to Support.
   - Match the text exactly, with no loose matching. Report 05 showed why: near-identical names are different items.
   - If the file is missing or unreadable, every type shows as Unmapped. The page then shows a short note saying so, and the log gets the reason, written once and again only when it changes.

### Part B: the daily snapshot

3. **When to write.**
   - Once per calendar day in `SITE_TIMEZONE`, on the first successful data load after midnight, append one line to the history file.
   - Never write more than one line per day, including after a restart. Work out the last recorded date from the file itself, not only from memory.
   - Waitress serves several requests at once, so guard the write with a lock.
4. **What a line holds.**
   - The date and the time it was recorded.
   - The source name, as shown in the line above each page.
   - The total number of assets.
   - The FMC, PMC, NMC and Destroyed/Lost counts, and a count of assets with no condition.
   - The readiness percentage.
   - The same counts and percentage for each of the five families.
5. **What counts as a successful load.**
   - It works for both `ASSET_SOURCE` values.
   - With the SharePoint source, do not record a stale copy (one where the last refresh failed). Also do not record a copy fetched on an earlier day; wait for the fresh fetch.
   - With the CSV source, record what the export holds, whatever its date.
   - A data load that fails records nothing.
6. **The history file.**
   - Its location is a new setting, `READINESS_HISTORY`, with the default `data/readiness_history.jsonl`. A relative path resolves against the repo, like `ASSET_CSV`.
   - Create the file and its folder if they are missing.
   - Add `data/` to `.gitignore`.
   - Write UTF-8 with `\n` line endings.
   - If the write fails, the page still loads. The cause goes to the log and a short note appears on the overview page.
7. **Keep tests out of the repo folder.** Every existing test loads pages, so without a change the suite would write to `data/` in the repo. Point `READINESS_HISTORY` at a temporary folder in `tests/conftest.py`.

### Part C: the page

The page lives at `/overview`. Add it to the nav, first in the list. `/` stays Inventory.

8. **Readiness rules.**
   - FMC = Ready (green).
   - PMC = Limited (yellow).
   - NMC = Not Ready (red).
   - Destroyed/Lost is shown in gray and left out of readiness.
   - Readiness % = FMC ÷ (total minus Destroyed/Lost). If that total is zero, show a dash, not 0%.
   - An asset with no condition counts in the total and is shown as "No condition". Say in the report how it affects the percentage.
   - No per-asset percentages and no progress bars. Condition is a category, so use pills only.
   - Use the existing `--good`, `--warn`, `--bad` and `--lost` colors so the light theme still works.
9. **Top row.**
   - **Overall Fleet Readiness:** a Chart.js doughnut with the percentage in the middle and the Ready, Limited and Not Ready counts. Give the Destroyed/Lost count beside it in gray.
   - **One card each for Aircraft, Ground Control Stations and Payloads:** the total, the three counts and the family's readiness %.
   - **A smaller combined card for Support and Unmapped.** If Unmapped is above zero, list those Asset Types on the card so Scott can add them to the mapping file.
   - **Last Updated:** the time from the data load, with the same "fetched" or "exported" wording as the line above each page.
   - **Location filter:**
     - Fill it from the Location column, using the list's own choices in the list's order and then any typed-in values. `asset_data.filter_options` already does this. Add a "No location" option if any asset has none.
     - An asset with several locations appears under each of them.
     - Use a plain GET parameter (`/overview?location=...`) so the filtered view can be linked.
     - The filter applies to the cards, the doughnut, the tables and the alerts. It does not apply to the trend, which is fleet-wide; say so under the chart.
10. **Middle row: one table per family (Aircraft, GCS, Payload).**
    - Columns: Serial Number, Asset Type, Location, Condition pill, Status (IN/OUT/RMA/BAILMENT pills as on the other pages), Checked out to, Notes.
    - Notes are cut to one line, with the full text on hover.
    - Sort Not Ready first, then Limited, then Ready, then No condition, then Destroyed/Lost. Within each group, sort by Asset Type, then Serial Number.
    - Stack the tables full width; seven columns do not fit three across.
11. **Bottom row.**
    - **Alerts card:** the first 5 rows from the existing `/attention` logic, in the same order as that page, each with its problem title, with a "View all" link to `/attention` and the total number of problems.
    - **Readiness Trend:** a line chart from the history file.
      - Show the last 7 days, with all 7 dates on the axis and a gap for any day with no line.
      - Show the overall readiness %, plus a line each for Aircraft, Ground Control Station and Payload.
      - With one point or none, say in plain words that the trend fills in one point per day.
12. **Visual style.**
    - Dark theme, card grid and a left nav, in the spirit of a fleet readiness tracker.
    - Give `/overview` a left nav built from the same `PAGES` list, through a switch in `base.html` that the route turns on. The other pages keep the header nav for now. Moving every page to a left nav is a question for Scott in the report.
    - Keep the theme toggle working.
    - Use the vendored Chart.js. No outside web access and no equipment images.

## Tests

Add tests for:

- the mapping lookup: a mapped type, an unknown type and a blank type giving Unmapped, and a missing or badly shaped file making everything Unmapped with the note on the page;
- the committed `asset_families.json`: it holds exactly the 29 types and families from report 05;
- the readiness math, with Destroyed/Lost left out, a zero total, and a blank condition;
- the once-per-day snapshot:
  - two loads on the same day write one line;
  - the next day writes a second line;
  - a fresh history object on the same day (a restart) writes nothing;
  - a missing file is created;
  - a stale SharePoint copy and one fetched on an earlier day write nothing;
  - it works through `/overview` with both the CSV source and the fake SharePoint source;
- the Location filter: an asset with two locations appears under both, and "No location" works;
- the table order;
- `/overview` returning 200 with both sources, and the 503 page when the source is unavailable.

All 73 existing tests must still pass. Run the whole suite, then again with `PYTHONTZPATH=""`.

## Report

Write `reports/06_fleet_overview.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What was built,** file by file.
- **The page:** a description, panel by panel, with the numbers it shows for the committed export.
  - Do not commit screenshots: they would show serial numbers, names and notes from the list.
- **Thin data:** any place where the data was too thin to fill a panel. At least cover:
  - the trend, which starts with one point;
  - Block 40 rows that report 05 says may be stands;
  - blank Status;
  - how few assets have Check Out By/To filled.
- **Test results** for both runs.
- **What a PROD apply would involve:**
  - the files to pull;
  - new settings;
  - whether the history file should live outside the repo folder on PROD, with a recommended path and the reason (for example, that it must survive a re-clone, and that it is not list data to commit).
  - Do not perform the apply and do not change `deploy/`.
- **Questions for Scott:** at least:
  - the left nav on every page;
  - whether `/overview` should replace Inventory at `/`;
  - how a blank condition should count.
