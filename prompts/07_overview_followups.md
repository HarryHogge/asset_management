# Prompt 07: Overview follow-ups

Runs in: Sandbox
Type: Build
Output: code, tests, README and `example.env` changes, plus `reports/07_overview_followups.md`, committed with the message "Prompt 07: overview follow-ups" and pushed to `agent/wednesday`. Nothing on PROD and no change to `deploy/`.

Read `CLAUDE.md`, `docs/decisions.md` and `reports/06_fleet_overview.md` first.

## Background

These are Scott's answers to report 06's questions 1, 2 and 5, the Alerts card, and the history setting.

Facts checked on the local machine at commit `aff7db5`, before this prompt was written:

- **Navigation.** `templates/base.html` has a `left_nav` switch that only `/overview` turns on. Inventory puts its "Export to Excel" button in the header through `{% block actions %}`.
- **Links to `/`.**
  - `PAGES` in `app.py` lists Inventory at `/`.
  - `templates/metrics.html` line 72 links its Assets card to `/`.
  - The tests call `/` as Inventory in `tests/test_pages.py`, and `tests/test_fleet.py` line 400 checks `PAGES[1][1] == '/'`.
- **Location filter.** `/overview` takes `?location=...`, and report 06 says filtered views can be linked.
- **The Attention page.** It has no filtering. Each rule's card has an anchor (`id="{{ g.key }}"`), so `/attention#out_no_holder` jumps to that rule.
- **The Alerts card.** `fleet.alerts(groups, limit=5)` takes the first 5 rows. With the committed export, all 5 come from one rule.
- **The history file.**
  - Its setting is `READINESS_HISTORY` (`app.py` line 36), not yet on PROD.
  - `fleet.ReadinessHistory.record()` creates the folder at write time.
  - On failure it logs once, shows a note on `/overview`, and tries again at the next load.
- **Pills.** Colors come from `BG_COLORS` and `FONT_COLORS` in `assets.py` and are written inline on each pill (`templates/_macros.html` and the overview template). Report 06 names SLO ENG, Global Support, RMA and Mod A Kit as too pale on the light background.

## Task

### 1. Left nav on every page

- **One layout.** Inventory, Needs Attention, Checkouts and Metrics use the same left nav as the overview, so the app has one navigation style. Remove the header nav and the `left_nav` switch rather than keeping two layouts.
- **Current page.** It stays highlighted.
- **Inventory.** Keep the "Export to Excel" button working and easy to find. Where it goes is your call; say where in the report.
- **Check widths.** Check each page at 1440 and 390 pixels wide in both themes. Check especially that the wide Inventory table still fits beside the nav, with no sideways scrolling of the page itself. A table may still scroll inside its own box, as now.

### 2. Overview becomes the home page

- **New routes.**
  - `/` serves the overview.
  - Inventory moves to `/inventory`.
  - `/overview` redirects to `/`, keeping the query string, so `/overview?location=SLO+ENG` lands on `/?location=SLO+ENG`.
  - Use a temporary redirect (302), so browsers do not remember it if the home page changes again.
- **Update every link to the old Inventory address**, including the Metrics Assets card.
- **Update the nav.** Overview first at `/`, then Inventory at `/inventory`.
- **No dead links.** Search the templates and scripts for any remaining link to `/` that meant Inventory. A link to the home page should still read as the home page.

### 3. Alerts card: one row per rule

- **Rows.** One row per attention rule, with the number of assets it affects. Use the same rules and counts as `/attention`, with the Location filter applied as it is now.
- **Order.** Sort by count, largest first; break ties in the `/attention` order. Show rules with a count of 0 too, at the bottom, in the muted zero style `/attention` already uses.
- **Links.** Each row links to `/attention#<rule key>`. The Attention page has no filtering, so this jumps to the rule's section.
  - Do not add filtering to `/attention` in this prompt.
  - With a Location filter on, also say in plain words that `/attention` shows the whole fleet.
- **Total.** Keep the total number of problems and the "View all" link.
- **Remove** the first-5-rows behavior and any code only it used.

### 4. Light theme: readable pills

- **Change.** In the light theme only, darken the pale pill colors so that:
  - the text is readable on the pill: a contrast of at least 4.5 to 1;
  - the pill stands out from the white page: at least 3 to 1 against the page background for the pill's fill or its border.
- **Dark theme.** Pixel for pixel unchanged.
- **Scope.** Cover every color in `BG_COLORS`, not only the four named, so a color added to the list later is handled too.
- **How.** Your choice, for example a light-theme color for each entry, or a border. Explain it in the report.
- **In the report,** list each color whose light-theme look changed, with before and after values and their contrast ratios.
- **`pill_colors.json`** keeps the list's own colors and does not change.
- **Condition pills** (Ready, Limited, Not Ready, Destroyed/Lost) already use `--good`, `--warn`, `--bad` and `--lost`. Check that they meet the same contrast rules in the light theme.

### 5. History file location setting

- **Rename the setting** `READINESS_HISTORY` to `READINESS_HISTORY_PATH`.
  - The default stays `data/readiness_history.jsonl` inside the repo.
  - A relative path resolves against the repo, as now.
  - The old name is not on PROD, so rename it everywhere (code, `example.env`, README, tests) with no fallback.
  - If the old name is still set in the environment, log one warning at startup saying it is ignored and naming the new one.
- **At startup:**
  - if the folder does not exist, create it;
  - if it cannot be created, log the error with its cause once and keep the app running with snapshots turned off;
  - snapshots stay off until the app restarts; no attempt at each page load.
  - `/overview` keeps showing a short note that the readiness history is off. The log has the reason.
- **Keep how write failures behave now** when the folder exists but writing still fails (for example, a file that cannot be written): log once, show the note, try again at the next load.
- **The startup banner** prints the history path, or that history is off and why.

### 6. Tests

Update and add tests for:

- **routing:**
  - `/` serves the overview;
  - `/inventory` serves Inventory;
  - `/overview` and `/overview?location=X` redirect with 302 to `/` with the query string kept;
  - every page and the page walk in `tests/test_pages.py` uses the new addresses, with both sources and every bad-setting case;
  - no page links to `/` as Inventory;
- **the left nav on every page,** with the current page highlighted;
- **the Alerts rows:** one per rule, the counts match `/attention`, the order is by count with ties in rule order, zero rows are at the bottom, the links point to each rule's anchor, and the Location filter is applied;
- **pills:** each light-theme pill color meets the two contrast rules above, and dark-theme colors are unchanged;
- **the history path setting:**
  - the default path;
  - a relative path;
  - an absolute path;
  - a missing folder that is created;
  - a folder that cannot be created (a path under a file, for example), where the app stays up, writes no snapshot, logs once and shows the note on `/overview`;
  - the old `READINESS_HISTORY` name logging its warning.

All 112 existing tests must still pass, changed only where the address moved. Run the whole suite, then again with `PYTHONTZPATH=""`.

## Report

Write `reports/07_overview_followups.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What changed,** file by file.
- **Each page's new layout,** described in words. Do not commit screenshots.
- **The pill color table** from step 4.
- **Test results** for both runs.
- **PROD apply notes.** Do not perform the apply and do not change `deploy/`. Cover:
  - **The new setting:** `READINESS_HISTORY_PATH=C:\Users\slovett\apps\asset_data\readiness_history.jsonl`, written without quotes, as `example.env` says for paths.
  - **Bookmarks:** bookmarks to `/` now land on the overview, and Inventory is at `/inventory`. Old `/overview` links still work through the redirect.
  - **What to check** after `pm2 restart asset-management`:
    - the banner shows the history path;
    - the folder exists;
    - the file gets one line after the first page view.
- **Questions for Scott,** if any. Report 06's questions 3 (blank condition) and 4 (Block 40 stands) are still open; carry them over unchanged.
