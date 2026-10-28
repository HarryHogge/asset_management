# Prompt 08: Runbook update for prompts 06 and 07

Runs in: Sandbox
Type: Docs only. No code, test, template, setting or `example.env` changes.
Output: changes to `reports/07_overview_followups.md` and `deploy/prod_runbook.md`, plus `reports/08_runbook_06_07.md`, committed with the message "Prompt 08: runbook for prompts 06 and 07" and pushed to `agent/wednesday`. Nothing is applied to PROD.

Read `CLAUDE.md`, `deploy/prod_runbook.md` (all of it), `reports/06_fleet_overview.md` and `reports/07_overview_followups.md` first.

## Background

Prompts 06 and 07 built the Fleet Overview and made it the home page. PROD has neither yet. Scott applies them by hand from the runbook, so the runbook must be right before he does.

Facts checked on the local machine at commit `bef937e`, before this prompt was written:

- **The runbook so far.** `deploy/prod_runbook.md` has Parts A to D. Part B has the standard "Code update" and "Roll back" blocks. Parts C and D each pull new code with their own steps.
- **Text that says the front page is Inventory.** These places treat `http://localhost:5070` as the Inventory page or "the table":
  - A6: "the Inventory page shows the assets", and "the line above the table".
  - C4: "same rows, and the line above the table".
  - D4: "the line above the table", and "Inventory shows 146 rows".
- **Which source PROD runs.** It is not known from the repo whether Scott has carried out Part D. PROD may be on `ASSET_SOURCE=csv` or `ASSET_SOURCE=sharepoint`, so Part E must work for both.
- **Branch.** The PROD clone follows `agent/wednesday` (A2).
- **`docs/decisions.md`** says Claude Code must not change it. Do not edit it in this prompt.

## Task

### 1. Close out the two carried-over questions in report 07

- At the end of `reports/07_overview_followups.md`, after "Questions for Scott", add a short section headed "Decisions (prompt 08)". Record both answers as final:
  1. Assets with no Material Condition count as not ready. They stay in the total and lower readiness, which is what the code already does.
  2. All Block 40 rows count as aircraft until SharePoint has a separate Asset Type for stands.
- Mark questions 1 and 2 in that report as decided, pointing to the new section. Leave question 3 (the runbook wording) and the rest of the report as written; this prompt answers it.
- These two are settled. Do not raise them again in this or any later report.

### 2. Update the front-page wording in `deploy/prod_runbook.md`

- **What to change.** Wherever the runbook treats `http://localhost:5070` as the Inventory page or "the table" (A6, C4, D4 and any other place you find), make it right for the code after prompt 07:
  - the front page is the Fleet Overview;
  - Inventory is at `http://localhost:5070/inventory`;
  - the "Data from ..." line is above every page's content.
- **Past parts.** Parts C and D describe steps Scott may already have run. Keep their meaning and order, and only fix what someone re-running them today would find wrong. Do not renumber anything.

### 3. Add Part E: applying prompts 06 and 07 to PROD

Add it after Part D, in the same style: PowerShell blocks, one block at a time, what to expect after each, and what to send back if something is wrong. It must work whether PROD is on the CSV or the SharePoint source.

1. **Note the current commit** before pulling, with `git rev-parse --short HEAD` in `C:\Users\slovett\apps\asset_management`, and write it down. This is the commit the rollback goes back to.
2. **Pull:** the usual pull block from Part B, including the `pip` line. No new packages, but it is safe to run.
3. **Settings:** add this line to `.env`, written without quotes, as `example.env` says for paths:

   ```
   READINESS_HISTORY_PATH=C:\Users\slovett\apps\asset_data\readiness_history.jsonl
   ```

   Nothing needs removing. `READINESS_HISTORY` was never on PROD.
4. **History folder:** create `C:\Users\slovett\apps\asset_data` if it is missing. Use a PowerShell command that does nothing if it already exists. The dashboard also creates it at startup; this step makes sure it is in place and writable under the `slovett` account.
5. **Restart:** `pm2 restart asset-management`.
6. **The four checks from report 07** ("What to check after `pm2 restart asset-management`"), with their expected results:
   1. the banner shows the history path, not "OFF", and there is no "READINESS_HISTORY is ignored" warning;
   2. `Test-Path` on the folder returns `True`;
   3. after opening `http://localhost:5070/` once, the history file holds one line starting with today's date;
   4. `/inventory` opens and Export to Excel downloads a file.
   - **Explain when the first history line appears.** It is written on the first successful data load after the restart: the first page view.
     - With the SharePoint source, that first page view may take a few seconds while the list is fetched.
     - Viewing pages again the same day adds no line.
     - A new line appears with the first page view each later day.
   - **If the file stays empty,** say what to look at: the "Readiness history" lines in `pm2 logs asset-management`, and the note on the overview.
7. **What Scott should see.**
   - **Front page:** `http://localhost:5070/` opens the Fleet Overview, with the left nav, the readiness cards and a one-point trend.
   - **Inventory:** at `/inventory`, with Export to Excel at the top right.
   - **Bookmarks:** bookmarks to `/` now land on the overview, and old `/overview` links redirect.
   - **For other users:** say that anyone used to Inventory at `/` should be told the new address.
8. **Roll back:**
   - `git checkout <the commit from step 1>`, then `pm2 restart asset-management`.
   - What is left behind:
     - the `READINESS_HISTORY_PATH` line in `.env` (the old code ignores it, so it can stay);
     - the history file and folder (harmless; keep them so the trend is not lost).
   - How to return to the branch afterwards: `git checkout agent/wednesday`, then `git pull`. The rollback leaves the clone on a single commit rather than the branch, so a plain `git pull` would not work until then.
   - What to paste back into the session if a rollback was needed.

Also update the runbook's opening lines so they mention Part E.

## Checks before committing

- Check every command in Part E for PowerShell on Windows:
  - paths with backslashes;
  - no quotes around the `.env` value;
  - `New-Item ... -Force`, or `Test-Path` before creating;
  - no Unix-only commands.
- Check the four checks match report 07 exactly, including the expected banner text.
- No em dashes anywhere you write.
- Run the test suite once to confirm nothing outside the docs changed. Expect 163 passed.

## Report

Write a short `reports/08_runbook_06_07.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **Report 07:** what was added to it.
- **Front-page wording:** each runbook step whose wording changed, with the old and new wording in brief.
- **Part E:** its outline, step by step.
- **Test result:** the suite count.
- **PROD:** confirm that nothing was applied to PROD.
