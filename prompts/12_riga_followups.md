# Prompt 12: Riga follow-ups and runbook Part F

Runs in: Sandbox
Type: Build and docs
Output: code, tests, README changes, additions to `reports/11_riga_tab.md`, a new Part F in `deploy/prod_runbook.md`, and `reports/12_riga_followups.md`, committed with the message "Prompt 12: Riga follow-ups and runbook Part F" and pushed to `agent/wednesday`. DEV only: nothing is applied to PROD.

Read `CLAUDE.md`, `deploy/prod_runbook.md` (Part E most of all), `reports/10_riga_columns.md` and `reports/11_riga_tab.md` first.

## Background

Scott has answered report 11's questions. This prompt records the answers, makes the three small changes they call for, and writes the runbook part that takes prompts 11 and 12 to PROD.

**Facts checked on the local machine at commit `20fe0fa`, before this prompt was written:**

- **Tests:** 224, all passing, also with `PYTHONTZPATH=""`.
- **The real workbook checks clean.** `python -m riga_loader --check data/samples/riga_assets.xlsx`, run on the real sample on Scott's Mac, found:
  - all 13 sheets, with the 10 equipment sheets mapped and 3 ignored;
  - **52 rows:** Aircraft 6, Ground Control Station 1, Payload 1, Support 8, Engine 36;
  - no missing headers, no unknown sheets and no unknown Status values;
  - 1 ENG date not read;
  - headline readiness, engines left out: **80%**.

  So for this sample the Riga view shows "16 assets in all, engines not included" plus an Engines table of 36. **52 is never shown as a single number.**
- **The US 83%** is for the committed CSV export. On PROD the US view reads the CSV or SharePoint, depending on `ASSET_SOURCE`, so its percentage may differ from 83%.
- **The Riga "No condition" rule** (`riga_loader.attention()`) fires when the row's condition is blank. An unknown Riga Status is turned into blank by the loader.
- **Backups.** `riga_loader.backup_path()` names them `current-YYYYMMDD-HHMMSS.xlsx`, with `-2`, `-3` and so on if the name is taken, in the same folder as `current.xlsx`. `current.upload.json` and the temporary `.upload-*.part.xlsx` files live there too.
- **Rollback risk.** History lines have carried `site` since prompt 11. Code from before prompt 11 (`bef937e`, for example) reads every line as US:
  - its trend keeps one line per date, so a Riga line can stand in for that day's US point;
  - its once-a-day check sees today's date already written, so it can skip that day's US line.

  So rolling back after Riga lines exist can mix up the US trend. The file itself is not damaged.

## Task

### 1. Record Scott's decisions in report 11

Add a section headed "Decisions (prompt 12)" at the end of `reports/11_riga_tab.md`. Mark each of its questions "Decided", with a pointer to the section, or, for question 6, "Open with Riga". Leave the rest of the report as it is.

| Report 11 question | Decision |
|---|---|
| 1. Tracking antenna family | Stays **Support** |
| 2. Riga on other pages | Riga rows appear **only on the overview** for now |
| 3. Who can upload | **No sign-in** is needed for uploads on PROD |
| 4. Backups | Keep the **20 most recent** (step 3) |
| 5. "No condition" for the US | **Yes** (step 4) |
| 6. Is the sample the full workbook? | **Still open, with the Riga team** |
| 7. Support table on the Riga view | **Yes** (step 2) |

These are settled. Do not raise them again in this or any later report.

### 2. Riga view: Support table

- **Where:** add a Support table below the Engine table on the Riga view.
- **Columns:** the same as the other Riga family tables: Serial Number, Asset Type, Location, Condition, Notes.
- **Order:** the same sort as the others.
- **Heading:** a count badge and Ready, Limited and Not Ready counts, like the Engine table.
- **Location filter:** it applies.
- **US view:** it does not get a Support table; that was not asked for. Say so in the report.

### 3. Keep the 20 most recent upload backups

- **When to prune:** only after a successful upload, once the new file is in place and the JSON beside it is written. Then delete backups beyond the 20 most recent.
- **What counts as a backup:** only files whose name matches the backup pattern exactly: `current-YYYYMMDD-HHMMSS.xlsx` or `current-YYYYMMDD-HHMMSS-N.xlsx`. Use the base name of `RIGA_WORKBOOK_PATH`, not a hard-coded "current".
- **Which are newest:** sort by the date, time and number in the name, not by file modified time. A copy keeps the original's modified time (`shutil.copy2`), so modified time cannot be trusted.
- **Never delete:** the current workbook, `current.upload.json`, a temporary upload file, or any other file in the folder.
- **If deleting fails,** for example because a file is open on the server:
  - the upload still counts as successful;
  - the log names the file and the cause;
  - the page says in one line that an old backup could not be removed;
  - the next upload tries again.
- **Rejected uploads** prune nothing.
- **README:** say that 20 are kept.

### 4. "No condition" for US rows

- **The rule:** add "No condition" to the US attention rules, using the same rule Riga uses: Material Condition is blank.
  - Do not fire on a US value that is filled but not one of FMC, PMC, NMC and Destroyed/Lost; the overview already counts that as "Other condition".
  - Match Riga's title. Write the explanation for the US column name.
- **Where it shows:** on `/attention` and in the US Alerts card, in the existing order rules. Choose its place among the US rules and say where.
- **What it counts:** the committed export has no blank conditions, so the count is 0. It appears at the bottom of the Alerts card in the muted zero style.
- **Riga rules do not change.**

### 5. Tests

Add tests for:
- **The Riga Support table:**
  - it renders below the Engine table, with the right rows, columns and order;
  - the Location filter applies;
  - the US view has no Support table.
- **Backup pruning:**
  - with 25 backups present, a successful upload leaves exactly 20, the newest by name;
  - the current file, its JSON beside it, a temporary file and an unrelated file are never touched;
  - `-N` names sort correctly;
  - a rejected upload deletes nothing;
  - a failed delete leaves the upload successful and is logged.
- **The US "No condition" rule:**
  - it fires on a fixture row with a blank Material Condition;
  - it does not fire on a filled value outside the four;
  - it shows on `/attention` and in the US Alerts card;
  - it works with both the CSV and the fake SharePoint source.

All 224 existing tests must still pass. Change them only where adding a US rule changes a rule count or order, and list each change in the report. Run the whole suite, then again with `PYTHONTZPATH=""`.

### 6. Runbook Part F: applying prompts 11 and 12 to PROD

Add Part F after Part E in `deploy/prod_runbook.md`, in the same shape and style as Part E: PowerShell blocks, one block at a time, what to expect after each, and what to paste back if something is wrong. Update the runbook's opening lines to mention Part F. Part F assumes Part E has been done.

- **F1. Note the current commit.** Run `git rev-parse --short HEAD` and write it down for the rollback.
- **F2. Back up the history file.** Copy it to `readiness_history.before-F.jsonl` in the same folder. The rollback needs it (see F8).
- **F3. Pull** with the usual block, including the `pip` line. There are no new packages.
- **F4. Settings.** Add this line to `.env`, without quotes:

  ```
  RIGA_WORKBOOK_PATH=C:\Users\slovett\apps\asset_data\riga\current.xlsx
  ```

- **F5. The folder.** Create `C:\Users\slovett\apps\asset_data\riga` with a command that does nothing if it already exists. Then prove the `slovett` account can write there by writing and removing a test file, as in E4.
- **F6. Restart:** `pm2 restart asset-management`.
- **F7. Checks after the restart,** each with its expected result:
  1. **The log** shows `Riga workbook: C:\Users\slovett\apps\asset_data\riga\current.xlsx`, not `OFF until restart`.
  2. **The US view** at `http://localhost:5070/` reads as before Part F. With the committed CSV that is **83%**. With the SharePoint source it is the same figure as just before F6, so the runbook should say to note that figure at F1.
     - The new "No condition" row shows in the Alerts card with 0, unless a US asset has a blank condition.
  3. **`http://localhost:5070/?site=riga`** says "No Riga workbook has been uploaded yet." with a link. That is expected, not an error.
  4. **Check the real file before uploading it.** Run `.venv\Scripts\python -m riga_loader --check "<path to the workbook>"` on the copy to be uploaded, and paste the output into a session if anything is listed under sections 3, 4 or 5. Section 3 is mapped headers not found, 4 is unknown Status values, and 5 is dates and formula errors. For the sample it reads 52 rows, the five family totals above and 80%.
  5. **The first upload, by hand.** The first Riga upload has to be done by hand: open `http://localhost:5070/riga/upload`, choose the workbook, type your name and submit.
  6. **After the upload, the Riga view shows:**
     - "Uploaded by <name> on <date and time>";
     - for the sample: "16 assets in all, engines not included", 80% readiness, an Engines table of 36, and a Support table of 8. That is 52 in all.
     - If the uploaded file is newer than the sample, the counts follow the check from step 4, not these numbers.
  7. **The upload record exists.** `Test-Path C:\Users\slovett\apps\asset_data\riga\current.upload.json` returns `True`.
  8. **The other pages are US only.** Inventory, Needs Attention, Checkouts, Metrics and Export to Excel still show US assets only. Needs Attention has the new "No condition" section.
- **F8. Roll back:**
  1. `git checkout <the commit from F1>`.
  2. Restore the history file from `readiness_history.before-F.jsonl`. Explain why in one plain sentence: older code reads Riga's history lines as US lines and would mix up the US trend.
  3. `pm2 restart asset-management`.

  What is left behind and can stay:
  - the `RIGA_WORKBOOK_PATH` line, which older code ignores;
  - the `riga` folder and its files.

  Then:
  - how to return to the branch afterwards: `git checkout agent/wednesday` and `git pull`;
  - what to paste back.

**Checks before committing the runbook:**
- Check every PowerShell command for Windows: backslashes, no quotes in `.env`, `New-Item -Force`, `Copy-Item` for the backup, and no Unix-only commands.
- Check the expected log and page text in Part F against the code exactly, as prompt 08 did for Part E.

## Report

Write `reports/12_riga_followups.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What changed,** file by file, including where the US "No condition" rule sits in the rule order.
- **The Riga view's new Support table,** described for the fixture.
- **Test results** for both runs, listing any existing test that changed and why.
- **Part F:** its outline, step by step, and the rollback risk with the history file and how F2 and F8 handle it.
- **PROD:** confirm that nothing was applied to PROD.
- **New questions:** only questions the decisions in step 1 do not already answer.
