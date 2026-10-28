# Report 08: Runbook for prompts 06 and 07

## Start

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `857a13d` ("Add prompt 08"), after `git pull`.
- **Docs only.** No code, test, template, setting or `example.env` changed. `docs/decisions.md` was not touched.

## Report 07

- **New section.** "Decisions (prompt 08)" is added at the end, recording both answers as final:
  1. assets with no Material Condition count as not ready, which the code already does;
  2. all Block 40 rows count as aircraft until SharePoint has a separate Asset Type for stands.
- **Questions 1 and 2** are marked "Decided", with a pointer to that section.
- **Question 3** (the runbook wording) and the rest of the report are unchanged. This prompt answers question 3.

## Front-page wording in `deploy/prod_runbook.md`

| Place | Before | After |
| --- | --- | --- |
| Opening lines | Mentioned Parts A and C only; "read from a SharePoint CSV export" | Mentions Parts C, D and E, and that the app reads a CSV export or live SharePoint. A new paragraph says `/` is the Fleet Overview since prompt 07, Inventory is at `/inventory`, and the `Data from ...` line is above every page's content |
| A6 | "the Inventory page shows the assets"; "the line above the table reads ..."; "Attention, Checkouts and Metrics all open" | The front page opens (the Fleet Overview since prompt 07, Inventory on older code); Inventory shows the assets, at `/inventory` since prompt 07; "the `Data from ...` line above the page's content reads ..."; "Needs Attention, Checkouts and Metrics all open" |
| C4 | "Open `http://localhost:5070` ... same rows, and the line above the table still says `exported`" | Open `http://localhost:5070/inventory` (on code from before prompt 07, `http://localhost:5070`); same rows, and the `Data from ...` line above the page's content still says `exported` |
| D4 | "the line above the table reads ..."; "Inventory shows 146 rows" | The first page is the Fleet Overview since prompt 07, and Inventory is at `/inventory`; "the `Data from ...` line above the page's content reads ..."; "Inventory (`/inventory`) shows 146 rows" |

- **No other place** treated `http://localhost:5070` as Inventory. A8 and D5 do not mention the front page.
- **Parts C and D** keep their steps, order and numbering. Only the addresses and wording above changed.
- **The old address is kept in brackets in A6 and C4,** because someone on older code would still find Inventory there.

## Part E: outline

Part E works on both `ASSET_SOURCE=csv` and `ASSET_SOURCE=sharepoint`, and tells Scott to leave that line as it is.

1. **E1. Note the current commit.** `git rev-parse --short HEAD` in `C:\Users\slovett\apps\asset_management`; write it down for the rollback.
2. **E2. Pull.** `git pull`, `git log --oneline -1` (expect `Prompt 08: runbook for prompts 06 and 07` or newer), and the `pip` line. No restart yet.
3. **E3. Settings.** Add `READINESS_HISTORY_PATH=C:\Users\slovett\apps\asset_data\readiness_history.jsonl` to `.env`, without quotes. Nothing to remove.
4. **E4. History folder.**
   - `New-Item -ItemType Directory -Force` makes the folder, or does nothing if it exists.
   - A test file is then written and removed with `Set-Content` and `Remove-Item`, to prove the `slovett` account can write there.
   - Any red text means stop and paste.
5. **E5. Restart.** `pm2 restart asset-management`.
6. **E6. The four checks from report 07**, with expected results:
   1. **The log** (`pm2 logs ... --nostream`) shows `Readiness history: C:\Users\slovett\apps\asset_data\readiness_history.jsonl`. It must not say `OFF until restart`, and there must be no `READINESS_HISTORY is ignored` warning.
   2. **`Test-Path` on the folder** returns `True`.
   3. **After one view of `http://localhost:5070/`,** `Get-Content` shows one line starting `{"date": "<today>"`, with `Get-Date -Format yyyy-MM-dd` to compare.
      - It explains when lines appear: the first page view after the restart, a few seconds' wait with SharePoint, no second line the same day, and one new line per later day.
      - If the file stays empty: look at the `Readiness history` log lines (with `Select-String`) and at the note on the overview, and paste both.
   4. **`/inventory` opens,** and Export to Excel downloads `assets-<today>.xlsx`.
7. **E7. What Scott should see.**
   - The front page is the overview, with the left nav, the cards, the tables, the Alerts card and a one-point trend.
   - Inventory is at `/inventory`, with Export at the top right.
   - Bookmarks to `/` open the overview, and `/overview` links redirect.
   - Users who go to Inventory should be told its new address.
8. **E8. Roll back.**
   - `git checkout <commit from E1>`, then `pm2 restart asset-management`.
   - The `.env` line and the history folder and file can stay: the old code ignores them, and keeping them keeps the trend's days.
   - To get back onto the branch: `git checkout agent/wednesday`, then `git pull`.
   - What to paste back: `git log --oneline -1` before and after, 50 log lines, and what the page showed.

**Windows checks.**
- Every path uses backslashes, and the `.env` value has no quotes.
- The folder is made with `New-Item -Force`.
- No Unix-only commands are used: filtering is done with `Select-String`, reading with `Get-Content`, and the date with `Get-Date`.

**Matches report 07.** The expected banner text, the history line and the export file name were checked against the code:
- the banner is `Readiness history: <path>`, or `Readiness history: OFF until restart, because ...`;
- each line starts `{"date": "`;
- the export is `assets-<date>.xlsx`;
- the two overview notes begin "The readiness history is off" and "Today's readiness could not be saved".

One addition to report 07's check 1: if the banner lines are missing from the PM2 log, checks 2 and 3 prove the same thing. The sandbox cannot show what PM2 captures on PROD, and A8 already relies on the banner appearing there.

## Test result

163 passed. Nothing outside the docs changed.

## PROD

Nothing was applied to PROD. Part E is for Scott to run by hand.
