# Report 12: Riga follow-ups and runbook Part F

## Start

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `51ddc68` ("Add prompt 12"), after `git pull`.
- **Where it ran:** the sandbox. `docs/decisions.md` was not changed.

## What changed

### `reports/11_riga_tab.md`

- **New section.** "Decisions (prompt 12)" is added at the end, with Scott's seven answers.
- **The questions.**
  - Questions 1 to 5 and 7 are marked **Decided**.
  - Question 6 is marked **Open with Riga**.
  - Each has a pointer to the new section.
- **Nothing else** in the report changed.

### Riga Support table (`app.py`, `fleet.py`, `templates/overview.html`)

- **Where and what.** The Riga view has a **Support** table below the Engines table.
  - It uses the same table as the other Riga families: the same columns, the same sort, and the same Location filter.
  - Its heading has a count badge and the Ready, Limited and Not Ready counts, like Engines.
- **New name.** `fleet.SUPPORT` names the family.
- **US view.** The US view has **no** Support table; that was not asked for. US Support kits are still counted only in the Support and Unmapped card.

### Keeping the 20 most recent backups (`riga_loader.py`, `templates/riga_upload.html`)

- **`KEEP_BACKUPS = 20`.**
- **`backups(path)`** lists the backups beside the workbook, newest first.
  - **What counts:** only names that match exactly `<name>-YYYYMMDD-HHMMSS.xlsx` or `<name>-YYYYMMDD-HHMMSS-N.xlsx`. `<name>` and `.xlsx` come from `RIGA_WORKBOOK_PATH`'s own file name (`current` by default), not a fixed word.
  - **Order:** by the date, time and number in the name. A name with no number counts as 1, so `-2` and `-10` come after it, in that order.
  - **Not modified time:** a backup copy keeps the original's modified time, so that is not used.
- **`prune_backups(path)`** deletes the backups beyond the 20 newest.
  - **When it runs:** only inside a successful upload, after the new workbook is in place and `current.upload.json` is written. A rejected upload never reaches it.
  - **What it never touches:** the current workbook, `current.upload.json`, the temporary `.upload-*.part.xlsx` files, or anything else in the folder, because none of them match the pattern.
- **If a delete fails** (for example, a file open on the server):
  - the upload still succeeds;
  - the log names the file and the cause, for example "the old backup ... could not be removed (PermissionError: ...). The next upload tries again.";
  - the upload page shows one extra line: "An old backup could not be removed; the next upload tries again. The reason is in the dashboard log.";
  - the next upload tries again, because pruning always works from the folder as it is.
- **The upload page** now says "20 most recent kept".

### US "No condition" rule (`assets.py`)

- **The rule.** A new US attention rule, `no_condition`:
  - title "No condition", the same as Riga's;
  - explanation "Material Condition is blank.";
  - it fires only when Material Condition is blank. A filled value outside FMC, PMC, NMC and Destroyed/Lost does not fire it; the overview already counts that as "Other condition".
- **Its place in the US rule order** (the order of `/attention`, and of ties on the Alerts card):
  1. out with no holder;
  2. out with no date;
  3. checked out but not OUT;
  4. No status;
  5. **No condition**;
  6. Never inventoried;
  7. Inventory overdue;
  8. PMC/NMC with no notes.

  It sits right after "No status" because both are about a blank column.
- **For the committed export** the count is 0. It shows in the Alerts card in the grey zero style, among the zero rows at the bottom.
- **Also affected:** the rule shows in the Metrics page's attention counts and in `/api/attention`, since both come from the same rule list.
- **Riga's rules** did not change.

### README

- **The `/attention` row** in the Pages table lists "no condition".
- **The Riga section:**
  - says the 20 most recent backups are kept, and how they are chosen;
  - says what happens if one cannot be deleted;
  - says the Riga view has a Support table and the US view does not.

### `deploy/prod_runbook.md`

- **Opening lines.** They now mention Part F.
- **New Part F** after Part E; outlined below.

### Tests

- **Added to `tests/test_riga.py`:** 7 tests.
  - Support table: 3 tests.
  - Backup pruning: 4 tests. `test_backup_order_and_pattern` covers both the `-N` sort and the base-name rule.
- **New `tests/test_no_condition.py`:** 5 tests.

## The Riga view's Support table, for the fixture

Below the Engines table:

| Item | For the fixture |
|---|---|
| Heading | "Support", badge **4**, then "3 Ready, 0 Limited, 1 Not Ready" |
| Columns | Serial Number, Asset Type, Location, Condition, Notes. No Status or Checked out to |
| Rows | The 3 made-up tracking antennas and the catapult |
| Order | Not Ready first (`TST-TRC-0003`), then the Ready rows by Asset Type and serial: Catapult (`TST-PPC-0001`) before Tracking Antenna (`TST-TRC-0001`, `TST-TRC-0002`) |
| With `?location=Field` | The catapult and two antennas, "3 Ready, 0 Limited, 0 Not Ready" |

For Scott's real sample, the check command found 8 Support rows.

The table uses the same template block as the Engines table, which prompt 11's visual check covered at 1440 and 390 wide in both themes. No new browser check was run for this prompt.

## Test results

- **Plain run:** `python -m pytest`: **236 passed**. That is the 224 from before, plus 7 new tests in `tests/test_riga.py` and 5 in `tests/test_no_condition.py`.
- **Run with `PYTHONTZPATH=""`:** **236 passed**.

**Existing tests changed** (two, both in `tests/test_riga.py`, both because of Scott's decisions):

1. **`test_riga_view_shows_riga_only`** used to check that the Support serials (antennas, catapult) were *not* on the Riga view, because Support had no table. It now checks that every Riga serial is shown.
2. **`test_riga_alert_card_has_counts_without_links`** used to check that the US Alerts card had *no* `no_condition` row. It now checks that the US card has one, linked to `/attention#no_condition` like the other US rules.

No other existing test changed. The US rule-count tests (`test_alert_card_matches_the_attention_page`, and the location-filter alert test) work from the rule list and passed unchanged.

**What the new tests cover:**

- **Support table:** placed below Engines; the heading counts; exactly the five columns; the sort order; only Support rows; the Location filter; no Support or Engines table on the US view.
- **Backups:**
  - with 25 old backups, an upload leaves exactly 20: the new one and the 19 newest by name. The old backups are given modified times in the opposite order, so a sort by modified time would fail the test;
  - the current workbook, `current.upload.json`, a temporary `.upload-*.part.xlsx`, `notes.txt` and `current-20250101-120000.xlsx.bak` are untouched;
  - `-2` and `-10` sort after the plain name, and a different workbook name sees none of `current`'s backups;
  - a rejected upload leaves the folder exactly as it was;
  - a delete that fails with `PermissionError` leaves the upload successful, puts the one-line note on the page, logs the file name and cause once, and the next upload removes the file.
- **US "No condition":**
  - fires on blank, not on "Awaiting Parts" or the four known values;
  - its place in the rule order;
  - 0 and grey for the committed export, with its section on `/attention`;
  - a made-up CSV and the fake SharePoint source, each with one blank and one unknown condition. Only the blank one is listed on `/api/attention`, the Alerts card and `/attention`.

## Part F

Part F, "Riga site on the overview (prompts 11 and 12)", follows Part E's shape: PowerShell blocks one at a time, what to expect after each, and what to paste back. It assumes Part E is done and works on either `ASSET_SOURCE`.

1. **F1. Note the current commit and the US figure.** `git rev-parse --short HEAD`, written down for the rollback. Also write down the US readiness percentage from `http://localhost:5070/`, so F7 can check it did not change: 83% with the committed CSV, or today's figure with SharePoint.
2. **F2. Back up the history file.** `Copy-Item` copies `readiness_history.jsonl` to `readiness_history.before-F.jsonl` in the same folder, and `Test-Path` confirms it.
3. **F3. Pull.** The usual block with the `pip` line; `git log` should show this prompt's commit or newer. No restart yet.
4. **F4. Settings.** Add `RIGA_WORKBOOK_PATH=C:\Users\slovett\apps\asset_data\riga\current.xlsx` to `.env`, without quotes.
5. **F5. The folder.** `New-Item -ItemType Directory -Force`, then a write-and-remove test with `Set-Content` and `Remove-Item`, as in E4.
6. **F6. Restart.** `pm2 restart asset-management`.
7. **F7. Checks:**
   1. **The log banner** reads `Riga workbook: C:\Users\slovett\apps\asset_data\riga\current.xlsx`, not `OFF until restart`.
   2. **The US view** shows the F1 percentage, with the US side of the switch highlighted. The new No condition row in Alerts reads 0, in grey.
   3. **`/?site=riga`** says "No Riga workbook has been uploaded yet." with a link. This is expected.
   4. **The check command** is run on the copy to be uploaded.
      - For the sample it gives: 52 rows; Aircraft 6, Ground Control Station 1, Payload 1, Support 8, Engine 36; 80%.
      - Two section 5 lines are named as known and fine: the one ENG date, and GCS's missing date column.
      - Anything else in sections 3, 4 or 5 means paste the output.
   5. **The first upload, by hand,** at `/riga/upload`, with the expected success text and what a refusal looks like.
   6. **The Riga view after the upload.** For the sample: "Uploaded by <name> on <date and time>", 80%, "16 assets in all, engines not included", Engines 36 and Support 8 (52 in all), and the note about the ENG date. For a newer file, the counts follow the check instead.
   7. **The upload record:** `Test-Path` on `current.upload.json` returns `True`.
   8. **The other pages** show US assets only, and Needs Attention has the new No condition section.

   It also says that 20 backups are kept, and when Riga's trend gets its daily point.
8. **F8. Roll back:**
   - `git checkout <commit from F1>`;
   - `Copy-Item ... -Force` to put `readiness_history.before-F.jsonl` back;
   - `pm2 restart asset-management`.

   Then it covers what is left behind and can stay (the `.env` line, the `riga` folder), how to get back onto the branch (`git checkout agent/wednesday`, `git pull`), and what to paste back.

**The rollback risk and how F2 and F8 handle it.** Since prompt 11, the history file also holds Riga's daily lines, each marked `"site": "Riga"`. Code from before prompt 11 ignores that mark and reads every line as US. Then:

- its trend takes one line per date, so a Riga line could stand in for that day's US point;
- its once-a-day check could see today already written and skip the US line.

The file is not damaged, but the US trend would be wrong. F2 copies the file before anything else changes, and F8 copies it back as part of the rollback, so the old code only ever sees US lines. The cost is that the days between F2 and the rollback drop out of the trend. F8 says this in one plain sentence.

**Checked for Windows:**

- every path uses backslashes, and the `.env` line has no quotes;
- the folder is made with `New-Item -Force`;
- the history backup and restore use `Copy-Item` (with `-Force` on the restore);
- the checks use `Test-Path`, and there are no Unix-only commands.

**Checked against the code:**

- the banner text `Riga workbook: <path>` and `Riga workbook: OFF until restart, because ...` (`app.py`);
- "No Riga workbook has been uploaded yet. Upload the Riga workbook to see Riga's fleet here." (`overview.html`);
- `Uploaded <file name>: 52 Riga rows read.` and `Not uploaded:` (`riga_upload.html`). The refusal box border is amber, and the runbook says so;
- "Uploaded by <name> on <date and time>" and "16 assets in all, engines not included" (`overview.html`);
- the check command's section titles, its two known section 5 lines, and `Headline readiness, engines left out: 80%` (`riga_loader.py`);
- the backup name `current-YYYYMMDD-HHMMSS.xlsx` and the 20 kept (`riga_loader.py`).

## PROD

Nothing was applied to PROD. Part F is for Scott to run by hand.

## New questions

None. The decisions recorded in report 11 cover everything this prompt touched.
