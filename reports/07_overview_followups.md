# Report 07: Overview follow-ups

## Start

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `f25bc11` ("Add prompt 07"), after `git pull`.
- **Where it ran:** the sandbox. Nothing on PROD, and `deploy/` is unchanged.

## What changed

| File | What changed |
| --- | --- |
| `templates/base.html` | One layout for every page. The header bar, its nav and the `left_nav` switch are gone. Every page has the left nav, built from `PAGES`. The current page's link is highlighted and marked `aria-current="page"`. A new heading row at the top of each page shows the page's name, with its buttons (`{% block actions %}`) on the right. There is also a light-theme rule for list pills (step 4). |
| `app.py` | `/` serves the overview and Inventory moved to `/inventory`. `/overview` answers with a 302 redirect to `/`, keeping the query string. In `PAGES`, Fleet Overview is at `/` and Inventory at `/inventory`. New `history_path()` and `make_history()` for `READINESS_HISTORY_PATH` (step 5). The startup banner prints the history path, or says history is off and why. `light_pill` is made available to the templates. |
| `fleet.py` | `alerts()` (the first 5 rows) is replaced by `alert_rows()`: one row per rule, with its count. `ReadinessHistory` can be created switched off, with the reason; it then records nothing and reads nothing. |
| `assets.py` | New `light_pill()`: the light-theme version of any pill color. Also the contrast math (`luminance`, `contrast`) it uses. |
| `templates/_macros.html` | Each colored pill carries its light-theme colors as CSS variables. Its inline colors for the dark theme are exactly as before. |
| `templates/overview.html` | The Alerts card shows one row per rule. The filter form and "Show all" point to `/`. There is a note when the history is off. Light-theme text on the Limited pill is black (see step 4). |
| `templates/metrics.html` | The Assets card links to `/inventory`. |
| `README.md`, `example.env` | The new addresses, `READINESS_HISTORY_PATH` (with the old name ignored), what happens at startup, and the light-theme pills. |
| `tests/conftest.py` | Uses `READINESS_HISTORY_PATH`, and clears the old name. |
| `tests/test_pages.py` | The page walk uses the new addresses. New tests cover routing, links, the left nav, the Export button and the error page. |
| `tests/test_fleet.py` | The new addresses, plus new tests for the Alerts rows and the history setting. |
| `tests/test_light_pills.py` (new) | The contrast rules for every list color and for the condition pills, and the check that the dark theme is unchanged. |

**Links checked.** I searched the templates and scripts for links to `/` and `/overview`. Every link to `/` now means the home page: the nav's "Fleet Overview" and the overview's own "Show all". The Metrics Assets card was the only link to the old Inventory address, and it now goes to `/inventory`. A test checks every page for this.

`deploy/prod_runbook.md` still describes `http://localhost:5070` as showing the inventory table, for example "same rows, and the line above the table". That address now opens the overview. I did not change `deploy/`; the wording needs updating when the runbook is next touched.

## Each page's new layout

All five pages, and the error page, have the same frame.

- **The left nav.** A 220-pixel column with the "AT" logo, "Asset Tracking / Flight Operations", then Fleet Overview, Inventory, Needs Attention, Checkouts and Metrics, with the Theme button at the bottom. The current page has a red bar on its left and bold text. The nav stays in place while the page scrolls.
- **The heading row.** At the top of the content: the page's name on the left (for example "Inventory") and that page's buttons on the right.
- **Below the heading:** the "Data from ..." line, then the page itself as before.
- **Below 900 pixels wide:** the nav becomes a short bar across the top, with the logo and Theme on one line and the links on the line below. The current link is underlined in red.

The pages:

- **Fleet Overview (`/`).** As in report 06, except for the Alerts card. The card has one row for each of the 7 rules, each with its count badge, largest first. A rule at 0 is grey and goes to the bottom. Each row links to that rule's section of Needs Attention, for example `/attention#never_inventoried`. The total and "View all" stay. With a Location filter on, the card adds: "These counts are for the location chosen above. The Needs Attention page shows the whole fleet." For the committed export, with no filter, the rows are:
  1. Never inventoried, 80
  2. No status, 21
  3. Inventory overdue, 17
  4. Out, with no Date Out, 8
  5. Out, but not checked out to anyone, 7
  6. Checked out to someone, but not marked OUT, 4
  7. PMC/NMC with no notes, 1

  That is 138 problems in all.
- **Inventory (`/inventory`).** The **Export to Excel** button is at the top right of the page, on the same line as the "Inventory" heading, in the accent red. It still exports exactly what the filters show. The filter card and the table follow. The table fits beside the nav and scrolls inside its own box, as before; the page itself does not scroll sideways. A few rows are taller than the rest because their Asset Notes wrap onto several lines, as they did before.
- **Needs Attention, Checkouts, Metrics.** Unchanged in content. They are now in the left-nav frame, with the page name as the heading.

**Browser check.** Every page was checked at 1440 and 390 pixels wide, in both themes, in a browser in the sandbox:
- the page width always equalled the window width, so there was no sideways scrolling;
- exactly one nav link was highlighted, the right one;
- there were no console errors;
- `/overview?location=SLO+ENG` landed on `/?location=SLO+ENG`.

No screenshots are committed.

## Step 4: pill colors in the light theme

**How it works.**
- Each colored pill keeps the list's colors inline, as before, so the dark theme is untouched. It also carries a light-theme fill, text color and border as CSS variables, and only a light-theme rule reads those variables.
- The light-theme colors are worked out by `assets.light_pill(fill, text)` from whatever colors a pill has. So a color added to the list later, or read live from SharePoint, is handled with no code change.
- The rules, checked against all four light backgrounds a pill can sit on (`#ffffff`, `#fafafa`, `#f5f5f5`, `#f2f2f2`):
  - **Text on the pill: 4.5 to 1 or more.**
    - With light text on a dark fill, the fill is darkened step by step until the text passes.
    - With dark text on a pale fill, the text is darkened instead, so the pale fill keeps the list's color.
    - If two dark colors cannot pass either way, the text becomes black or white, whichever is further from the fill. One of the two always reaches at least 4.58 to 1.
  - **Pill against the page: 3 to 1 or more,** for the fill or else a border. A pale fill gets a 1-pixel border in its own text color, darkened if needed.
  - A pill that already passes both rules is left exactly as it is.
- `pill_colors.json` is unchanged.

**Every color in `BG_COLORS`,** with the text color the list uses with it. "Edge vs page" is the lowest of the four backgrounds.

| List color | Before: fill / text | Text contrast | Fill vs page | Light theme after: fill / text / border | Text contrast | Edge vs page | Used today by |
|---|---|---|---|---|---|---|---|
| BgMintGreen | #dff6dd / #0b6a0b | 5.96 | 1.02 | #dff6dd / #0b6a0b / **#0b6a0b** | 5.96 | 6.09 | B40 HLB Charging Kit, B40 Main Charging Kit, Field Support Kit, Fuel Cell Support Kit, HLB Charging Kit, Main Battery Charging Kit, SIL Laptop, SLO Flight Ops |
| BgLightGray | #e1dfdd / #3b3a39 | 8.54 | 1.19 | #e1dfdd / #3b3a39 / **#3b3a39** | 8.54 | 10.14 | HIL Simulator, Other, Student Laptop Kit |
| BgMauve | #efe4f7 / #5c2e91 | 7.59 | 1.10 | #efe4f7 / #5c2e91 / **#5c2e91** | 7.59 | 8.32 | Gimbal Support Kit |
| BgGold | #fff1c2 / #7a5400 | 6.01 | 1.01 | #fff1c2 / #7a5400 / **#7a5400** | 6.01 | 6.06 | PMC, Starlink |
| BgCyan | #dcf5f9 / #005b70 | 6.77 | 1.02 | #dcf5f9 / #005b70 / **#005b70** | 6.77 | 6.87 | Fuel Cell, Mod A Kit, Ping 200x Transponder Kit, SLO ENG, Wing Utility Pylon |
| BgDustRose | #f6e4e2 / #8b3a33 | 6.22 | 1.10 | #f6e4e2 / #8b3a33 / **#8b3a33** | 6.22 | 6.82 | Global Support |
| BgPeach | #fde5d6 / #8f3500 | 6.48 | 1.08 | #fde5d6 / #8f3500 / **#8f3500** | 6.48 | 7.01 | LRLE |
| BgCoral | #fde7e9 / #a4262c | 6.15 | 1.05 | #fde7e9 / #a4262c / **#a4262c** | 6.15 | 6.49 | RMA |
| BgTeal | #038387 / #ffffff | 4.56 | 4.08 | unchanged | 4.56 | 4.08 | Block 40, VXE 35 x, VXE-30, VXE-30B |
| BgBrown | #8e562e / #ffffff | 5.96 | 5.33 | unchanged | 5.96 | 5.33 | SGCS 1, SGCS 2, SGCS 3 |
| BgPurple | #6b47b8 / #ffffff | 6.52 | 5.83 | unchanged | 6.52 | 5.83 | E 140 MWIR, E 140Z G2, E 140Z G2 Dual GPS, E 180, E 95 |
| BgGray | #605e5c / #ffffff | 6.46 | 5.77 | unchanged | 6.46 | 5.77 | B40 Battery |
| BgGreen | #498205 / #ffffff | 4.69 | 4.19 | unchanged | 4.69 | 4.19 | FMC, HSV Flight Ops, IN |
| BgDarkGreen | #0b5a0b / #ffffff | 8.46 | 7.56 | unchanged | 8.46 | 7.56 | Engineering, HSV ENG |
| BgRed | #c50f1f / #ffffff | 6.07 | 5.42 | unchanged | 6.07 | 5.42 | NMC, No Verified Location |
| BgOrange | #ca5010 / #ffffff | 4.50 | 4.02 | unchanged (4.5004, just over) | 4.50 | 4.02 | HSV LRR Internal, LRR |
| BgDarkBlue | #004e8c / #ffffff | 8.51 | 7.60 | unchanged | 8.51 | 7.60 | BD HSV |
| BgLavender | #8764b8 / #ffffff | 4.62 | 4.13 | unchanged | 4.62 | 4.13 | Business Development |
| BgDarkRed | #a4262c / #ffffff | 7.26 | 6.49 | unchanged | 7.26 | 6.49 | OUT |
| BgBlue | #0f6cbd / #ffffff | 5.38 | 4.81 | unchanged | 5.38 | 4.81 | BAILMENT |

What changed in practice:
- **The 8 pale colors** were already readable, but faded into the white page at about 1 to 1. Each now has a border in its own text color; their fills and text are unchanged.
- **The 12 dark colors** already passed both rules and look the same.

The tests also check every list color with every text color the list offers (and white), not only the pairs above.

**Condition pills on the overview** (light-theme values from `base.html`):

| Pill | Fill / text | Text contrast | Fill vs page | Change |
|---|---|---|---|---|
| Ready (FMC) | `--good` #107c10 / #ffffff | 5.37 | 4.79 | none |
| Limited (PMC) | `--warn` #a86b00 / #1a1a1a | **3.95** | 3.93 | text set to **#000000** in the light theme: 4.76 |
| Not Ready (NMC) | `--bad` #c50f1f / #ffffff | 6.07 | 5.42 | none |
| Destroyed/Lost | `--lost` #6b6b6b / #ffffff | 5.33 | 4.76 | none |
| No condition | clear fill, `--muted` #666666 border, `--text-2` #333333 text | 11.3 or more on the page | border 5.13 | none |

The Limited pill was the one that failed: its text was 3.95 to 1. It now uses black text in the light theme only. The dark theme's Limited pill is unchanged.

## Step 5: the history path setting

- **The setting is now `READINESS_HISTORY_PATH`.**
  - It is empty or not set: the default `data/readiness_history.jsonl` in the repo.
  - A relative path resolves against the repo.
  - The old name `READINESS_HISTORY` is ignored, with no fallback. If it is still set, the log gets one warning at startup: "The setting READINESS_HISTORY is ignored: it was renamed READINESS_HISTORY_PATH. Rename it in .env."
- **At startup the dashboard makes the folder.** If that fails:
  - the log gets one ERROR with the cause, for example: "Readiness history is OFF until the dashboard is restarted, because the folder ...\README.md\x could not be created (NotADirectoryError: ...). Fix READINESS_HISTORY_PATH in .env, then restart.";
  - the dashboard keeps running;
  - no snapshot is attempted on any page load;
  - `/` shows: "The readiness history is off, so no daily numbers are saved for the trend until the dashboard is restarted. The reason is in the dashboard log."
- **When the folder exists but writing fails,** nothing changed: one log line per cause, the note on the overview, and another try at the next load.
- **The startup banner** prints `Readiness history: <path>`, or `Readiness history: OFF until restart, because <reason>`. I saw both in the sandbox: the first with a working path, and the second with a path under a file.

## Test results

- Whole suite: **163 passed.**
- Again with `PYTHONTZPATH=""`: **163 passed.**

Of the 112 earlier tests:
- **110 still run,** with only the address changed where it moved.
- **One was removed:** the test of the first-5 Alerts rows, because that code is gone.
- **One was rewritten:** the test that `/` was Inventory and that only the overview had the left nav. It now checks the new nav order.

52 tests are new:
- **16 for addresses and the nav:**
  - `/` serves the overview and `/inventory` serves Inventory;
  - 3 redirect cases, the query string kept;
  - no page links to `/` as Inventory (5 pages);
  - the left nav and its highlight (5 pages);
  - the Export button;
  - the error page.
- **3 for the Alerts card:**
  - the order;
  - the counts and links match `/attention`;
  - the Location filter.
- **4 for the history setting:**
  - the default, relative and absolute paths;
  - a missing folder is created;
  - a folder that cannot be created;
  - the old name's warning.
- **29 for the pills:**
  - all 20 list colors;
  - the condition pills;
  - the dark theme unchanged;
  - the light backgrounds match `base.html`.

## PROD apply notes

This was not done, and `deploy/` is unchanged.

- **The new setting.** Add this line to `.env` on PROD, written without quotes, as `example.env` says for paths:

  ```
  READINESS_HISTORY_PATH=C:\Users\slovett\apps\asset_data\readiness_history.jsonl
  ```

  The folder `asset_data` is created at startup if it is missing. `READINESS_HISTORY` was never on PROD, so nothing needs removing.
- **Bookmarks.**
  - A bookmark to `http://localhost:5070/` now opens the Fleet Overview.
  - Inventory is at `http://localhost:5070/inventory`.
  - Old `/overview` links still work through the redirect, with any Location filter kept.
- **Packages:** none new.
- **What to check after `pm2 restart asset-management`:**
  1. `pm2 logs asset-management --lines 30 --nostream`: the banner line reads `Readiness history: C:\Users\slovett\apps\asset_data\readiness_history.jsonl`, not "OFF". There should be no "READINESS_HISTORY is ignored" warning.
  2. `Test-Path C:\Users\slovett\apps\asset_data` returns `True`.
  3. Open `http://localhost:5070/` once, then `Get-Content C:\Users\slovett\apps\asset_data\readiness_history.jsonl`. It shows one line, starting with today's date.
  4. Open `http://localhost:5070/inventory` and check that the Export to Excel button downloads a file.

## Questions for Scott

1. **(Carried over from report 06, question 3.) A blank condition.** Today it stays in the total and lowers readiness. Should it instead:
   - stay in the total, as now (it counts as not ready until someone fills it in);
   - be left out, like Destroyed/Lost; or
   - be left out, with a warning count on the card?
2. **(Carried over from report 06, question 4.) Block 40 stands.** Report 05's question still stands. Until the list gives stands their own Asset Type, they count as aircraft here.
3. **The PROD runbook's wording.** `deploy/prod_runbook.md` still says the front page shows the inventory table. Should it be updated, perhaps as part of the next runbook prompt?
