# PROD runbook: asset_management

Runs on: PROD (Windows), in PowerShell, as `slovett`.
App: the asset tracking dashboard, read from a SharePoint CSV export or live from SharePoint. Port 5070. PM2 name `asset-management`.

Part A installs the CSV version, which has no secrets. Part C adds the SharePoint certificate and settings and tests the live connection. Part D switches the live dashboard to SharePoint. Part E applies the Fleet Overview (prompts 06 and 07), which becomes the front page. Part F adds the Riga site to the overview (prompts 11 and 12), with an upload page for the Riga workbook.

Since prompt 07, `http://localhost:5070/` opens the **Fleet Overview** and Inventory is at `http://localhost:5070/inventory`. Every page has the `Data from ...` line above its content.

Run the commands one block at a time and check each result before going on.

## Part A: First install

### A1. Check Python

```powershell
python --version
```

Needs 3.10 or later. The SharePoint packages (report 03) do not install on 3.9.

### A2. Clone the repo next to the other apps

```powershell
cd C:\Users\slovett\apps
git clone https://github.com/HarryHogge/asset_management.git
cd asset_management
git checkout agent/wednesday
git log --oneline -1
```

The last line should show `Prompt 02: Windows date format fix` or something newer.

### A3. Create the Python environment

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

`tzdata` should be in the list of packages it installs. Windows needs it for the SharePoint site's time zone (report 01).

### A4. Settings

```powershell
copy example.env .env
mkdir exports
```

Open `.env` in Notepad and change one line, so the app reads its data from `exports\`:

```
ASSET_CSV=exports\Asset Tracking V2.csv
```

Leave the rest as it is. `SITE_TIMEZONE` must stay a name like `America/Los_Angeles`. A Windows name such as `Pacific Standard Time` makes every page fail.

Why `exports\`: the repo already contains a copy of the CSV. If new exports were saved over that copy, the next `git pull` would refuse to run. `exports\` is excluded from Git, so updates there never get in the way.

### A5. Put the data in place

In SharePoint, open the Asset Tracking V2 list and choose **Export, Export to CSV**. Save the file as:

```
C:\Users\slovett\apps\asset_management\exports\Asset Tracking V2.csv
```

To start with the copy already in the repo instead:

```powershell
copy "Asset Tracking V2.csv" "exports\Asset Tracking V2.csv"
```

### A6. Test run by hand, before PM2

```powershell
.venv\Scripts\python app.py
```

It prints `Open http://localhost:5070 in your browser`. On PROD, open that address and check:

- the front page opens (since prompt 07 this is the Fleet Overview; on older code it is Inventory);
- the Inventory page shows the assets (at `http://localhost:5070/inventory` since prompt 07);
- the `Data from ...` line above the page's content reads `Data from Asset Tracking V2.csv, exported <date and time>`, where the time is when you saved the file;
- Needs Attention, Checkouts and Metrics all open.

If Windows asks whether to allow Python on the network, choose **Allow** for Domain networks. Then stop the app with Ctrl+C.

If the page shows an error, stop here and send me the last lines the window printed.

### A7. Add it to PM2

The PM2 entry is already committed to `redwire_gs`. Pull it in the folder you normally run `pm2 start ecosystem.config.js` from:

```powershell
cd <your redwire_gs folder>
git pull
pm2 start ecosystem.config.js --only asset-management
pm2 save
```

`--only` starts this one app and leaves the running services alone. `pm2 save` makes PM2 bring it back after a reboot.

### A8. Check it

```powershell
pm2 status
pm2 logs asset-management --lines 20 --nostream
```

`asset-management` should be `online`, with a restart count of 0 that stays at 0. The log should show the `Open http://localhost:5070` banner.

Then, from your own computer, not PROD, open port 5070 on the same server name you use for jira-dash on 5050.

### A9. Only if A8 works on PROD but not from your computer

The Windows firewall is blocking the port. In an **administrator** PowerShell on PROD:

```powershell
New-NetFirewallRule -DisplayName "asset-management 5070" -Direction Inbound -Protocol TCP -LocalPort 5070 -Action Allow -Profile Domain
```

Try again from your computer.

## Part B: Later

### Code update

```powershell
cd C:\Users\slovett\apps\asset_management
git pull
.venv\Scripts\python -m pip install -r requirements.txt
pm2 restart asset-management
```

The `pip` line only matters when `requirements.txt` changed, but it is safe to run every time.

If the sandbox has moved to a new branch name, `git pull` keeps pulling the old one. Run `git fetch` then `git checkout <new branch>` first.

### Data update

Export the list to CSV again and save it over `exports\Asset Tracking V2.csv`. The app notices the change by itself, so no restart is needed. Close the file in Excel first, or Windows will not let you save over it.

### Roll back

```powershell
cd C:\Users\slovett\apps\asset_management
git log --oneline -5
git checkout <previous commit>
pm2 restart asset-management
```

To take it off PROD altogether: `pm2 delete asset-management`, then `pm2 save`.

## Part C: SharePoint connection test

Goal: put the certificate and settings on PROD and run the connection check, while the dashboard people use **stays on the CSV**. Nothing here switches the live app to SharePoint.

You need from IT: the tenant ID, client ID, FLOPS site ID, the `.pfx` file and its password. Never paste any of them into a chat or a commit.

### C1. Put the certificate in its own folder

Outside the repo, readable only by you, SYSTEM and administrators:

```powershell
mkdir C:\Users\slovett\certs
icacls C:\Users\slovett\certs /inheritance:r /grant:r "slovett:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "Administrators:(OI)(CI)F"
```

Copy the `.pfx` into that folder, then check it is there:

```powershell
Get-ChildItem C:\Users\slovett\certs
```

### C2. Pull the new code

```powershell
cd C:\Users\slovett\apps\asset_management
git pull
git log --oneline -1
.venv\Scripts\python -m pip install -r requirements.txt
```

`git log` should show `Add PROD runbook Part C and decisions` or something newer. `pip` should end with `Successfully installed ...` (msal, cryptography and others) and no red errors.

### C3. Add the SharePoint settings to `.env`

Your `.env` was copied before these settings existed. Open it:

```powershell
notepad .env
```

Add these lines at the end and fill in the values. Write them **without double quotes**: inside double quotes a backslash is read as a special character, and `\n` in a path would become a line break.

```
ASSET_SOURCE=csv
SP_TENANT_ID=<tenant ID>
SP_CLIENT_ID=<client ID>
SP_SITE_ID=<FLOPS site ID>
SP_LIST_NAME=Asset Tracking V2
SP_CERT_PATH=C:\Users\slovett\certs\<file name>.pfx
SP_CERT_PASSWORD=<pfx password>
SP_REFRESH_SECONDS=300
```

If the password contains a space, `#` or a quote, put it in single quotes: `SP_CERT_PASSWORD='...'`.

Leave `ASSET_SOURCE=csv`. That keeps the live dashboard on the CSV.

### C4. Restart on the new code, still on CSV

```powershell
pm2 restart asset-management
pm2 logs asset-management --lines 20 --nostream
```

Open `http://localhost:5070/inventory` (on code from before prompt 07, Inventory is at `http://localhost:5070`). It should look exactly as before: same rows, and the `Data from ...` line above the page's content still says `exported`.

### C5. Run the connection check

```powershell
.venv\Scripts\python -m sharepoint --check
```

It runs once and exits. It does not touch the running dashboard. It makes only read requests to Microsoft, and prints no passwords, IDs or list contents.

**Paste the whole output back into the session.** Each step says `[OK]`, `[FAILED]` or `[--]` (not run, because an earlier step failed), and a failure says which step failed and why. Whatever it says, leave `ASSET_SOURCE=csv` for now; the switch-over comes after we have read the output together.

If the check itself crashes with a Python error instead of printing its steps, paste that too.

## Part D: Switch the live dashboard to SharePoint

Do this after the Part C check has passed. Switching back takes one line and a restart (D5).

### D1. Pull the new code

```powershell
cd C:\Users\slovett\apps\asset_management
git pull
git log --oneline -1
.venv\Scripts\python -m pip install -r requirements.txt
```

`git log` should show `Add PROD runbook Part D` or something newer. There are no new packages, so `pip` should only say `Requirement already satisfied`.

### D2. Run the check again on the new code

```powershell
.venv\Scripts\python -m sharepoint --check
```

It should end with `RESULT: every step passed.` Step 8 should now say `SAVED` (colors from `pill_colors.json`) instead of plain pills. Once IT adds the SharePoint permission, it will say `LIVE`. If any step fails, stop here and paste the output.

### D3. Switch

```powershell
notepad .env
```

Change `ASSET_SOURCE=csv` to `ASSET_SOURCE=sharepoint`, save, then:

```powershell
pm2 restart asset-management
```

### D4. Check it

Open `http://localhost:5070`. The first page takes a few seconds while it fetches the list. Since prompt 07 that first page is the Fleet Overview and Inventory is at `http://localhost:5070/inventory`. Then:

- the `Data from ...` line above the page's content reads `Data from SharePoint: Asset Tracking V2, fetched <date and time>`;
- there is no yellow note box;
- Inventory (`/inventory`) shows 146 rows (or the current count in SharePoint), with pills in the same colors as before;
- Check Out By/To shows **names**, not email addresses, on Inventory and on Checkouts;
- Checkouts has no `(unknown person, ID n)` entries;
- Needs Attention and Metrics show the same groups and totals as before, apart from any edits made in SharePoint since the last CSV export.

Then look at the log:

```powershell
pm2 logs asset-management --lines 30 --nostream
```

Expect:

- `Data source: SharePoint list Asset Tracking V2, refreshed every 300 seconds`;
- `SharePoint refresh OK: 146 items`;
- one `Pill colors: using the saved colors in pill_colors.json ...` line mentioning HTTP 401. That line is expected until IT adds the permission, and should not repeat every 5 minutes.

Last, edit something harmless in the SharePoint list, such as an Asset Notes field. Within 5 minutes, reloading the dashboard should show the change.

### D5. Switch back, if anything is wrong

Set `ASSET_SOURCE=csv` in `.env`, then run `pm2 restart asset-management`. The dashboard goes back to the CSV, with email addresses and the word `exported`. Paste what you saw, and the log lines, into the session.

### D6. When IT adds the SharePoint permission

Nothing to change. Run the check again: step 8 should say `LIVE`. The dashboard picks it up at its next refresh, and logs `Pill colors: read live from SharePoint` once.

## Part E: Fleet Overview (prompts 06 and 07)

What changes for users:
- the Fleet Overview becomes the front page, `http://localhost:5070/`;
- Inventory moves to `http://localhost:5070/inventory`;
- every page gets a left nav.

The dashboard also starts keeping one line of readiness numbers per day, for the trend chart, in a file outside the repo.

This works the same whether `.env` says `ASSET_SOURCE=csv` or `ASSET_SOURCE=sharepoint`. Leave that line as it is.

### E1. Note the current commit

```powershell
cd C:\Users\slovett\apps\asset_management
git rev-parse --short HEAD
```

It prints a short code such as `bef937e`. **Write it down.** It is the commit E8 goes back to if something is wrong.

### E2. Pull the new code

```powershell
git pull
git log --oneline -1
.venv\Scripts\python -m pip install -r requirements.txt
```

`git log` should show `Prompt 08: runbook for prompts 06 and 07` or something newer. There are no new packages, so `pip` should only say `Requirement already satisfied`. Do not restart yet.

### E3. Add the history setting to `.env`

```powershell
notepad .env
```

Add this line at the end, **without quotes**, as for every path in `.env`, then save:

```
READINESS_HISTORY_PATH=C:\Users\slovett\apps\asset_data\readiness_history.jsonl
```

Nothing needs removing. The older name `READINESS_HISTORY` was never on PROD.

### E4. Make the history folder

```powershell
New-Item -ItemType Directory -Force -Path C:\Users\slovett\apps\asset_data
Set-Content -Path C:\Users\slovett\apps\asset_data\write_test.txt -Value ok
Remove-Item C:\Users\slovett\apps\asset_data\write_test.txt
```

- **The first line** makes the folder, or does nothing if it is already there. It prints the folder either way.
- **The other two** write a small file and delete it again. That proves `slovett`, the account PM2 runs the dashboard under, can write there. They should print nothing.
- **If any line prints red text, stop** and paste it into the session.

The dashboard also makes the folder by itself at startup; this step makes sure it is there and writable first.

### E5. Restart

```powershell
pm2 restart asset-management
```

### E6. Check it

**1. The banner and warnings in the log.**

```powershell
pm2 logs asset-management --lines 40 --nostream
```

Expect the line:

```
Readiness history: C:\Users\slovett\apps\asset_data\readiness_history.jsonl
```

- It must not say `Readiness history: OFF until restart, because ...`.
- There must be no warning containing `READINESS_HISTORY is ignored`.
- If the banner lines are missing altogether, go on to checks 2 and 3: they show the same thing.

**2. The folder.**

```powershell
Test-Path C:\Users\slovett\apps\asset_data
```

Expect `True`.

**3. The first history line.** Open `http://localhost:5070/` once in the browser, then:

```powershell
Get-Date -Format yyyy-MM-dd
Get-Content C:\Users\slovett\apps\asset_data\readiness_history.jsonl
```

Expect exactly one line, starting `{"date": "<today>"`, where `<today>` is the date the first command printed.

When the line is written:
- **The first page view** writes it: that is the first successful load of the list after the restart.
- **With the SharePoint source,** that first view can take a few seconds while the list is fetched.
- **More page views the same day** add no line.
- **A new line** appears with the first page view of each later day, so the trend fills in one point per day.

If the file is missing or empty after a page view:

```powershell
pm2 logs asset-management --lines 100 --nostream | Select-String "Readiness history"
```

Also look for a short note at the top of the overview, either:
- "The readiness history is off ..." (the folder could not be made at startup); or
- "Today's readiness could not be saved ..." (the file could not be written).

Paste the `Select-String` output and the note into the session.

**4. Inventory and the Excel export.** Open `http://localhost:5070/inventory`. The table of assets shows, with **Export to Excel** at the top right, beside the "Inventory" heading. Click it: a file named `assets-<today>.xlsx` downloads.

### E7. What you should see

- **The front page.** `http://localhost:5070/` opens the Fleet Overview, with:
  - the left nav;
  - the readiness doughnut and cards;
  - a table for each family;
  - the Alerts card;
  - a Readiness Trend with one point, saying it fills in one point per day.
- **Inventory** is at `http://localhost:5070/inventory`, with Export to Excel at the top right.
- **Bookmarks** to `http://localhost:5070/` now open the overview. Old `/overview` links still work: they redirect to `/`, keeping any Location filter.
- **Tell other users.** Anyone who opens the dashboard for Inventory should be told its new address, `http://localhost:5070/inventory` (or the same path on the server name used from their own computer).

### E8. Roll back, if anything is wrong

Use the commit you wrote down in E1:

```powershell
cd C:\Users\slovett\apps\asset_management
git checkout <commit from E1>
pm2 restart asset-management
```

The dashboard is then back to how it was before Part E, with Inventory at `http://localhost:5070`.

What is left behind, and can stay:
- **The `READINESS_HISTORY_PATH` line in `.env`.** The old code ignores it.
- **`C:\Users\slovett\apps\asset_data` and the history file.** They are harmless. Keep them, so the trend keeps its days when Part E is applied again.

**Getting back onto the branch.** After a rollback the clone sits on that single commit, not on the branch, so a plain `git pull` will not work. Before the next update, run:

```powershell
git checkout agent/wednesday
git pull
```

**What to paste into the session** if you rolled back:
- the output of `git log --oneline -1` from before and after the rollback;
- `pm2 logs asset-management --lines 50 --nostream`;
- what the page showed, including any note or error text.

## Part F: Riga site on the overview (prompts 11 and 12)

Do Part E first; Part F assumes it is done.

What changes for users:
- the Fleet Overview gets a **US / Riga** switch at the top. US is the default and looks as before;
- `http://localhost:5070/?site=riga` shows Riga's fleet, read from an Excel workbook uploaded at `http://localhost:5070/riga/upload`;
- Needs Attention and the US Alerts card get a new rule, **No condition** (Material Condition is blank).

Inventory, Needs Attention, Checkouts, Metrics and Export to Excel stay US only. This works the same whether `.env` says `ASSET_SOURCE=csv` or `ASSET_SOURCE=sharepoint`. Leave that line as it is.

### F1. Note the current commit and the US figure

```powershell
cd C:\Users\slovett\apps\asset_management
git rev-parse --short HEAD
```

It prints a short code such as `0d0d513`. **Write it down.** It is the commit F8 goes back to.

Then open `http://localhost:5070/` and **write down the percentage** in the middle of the readiness doughnut. F7 checks that it has not changed. With the committed CSV export it is 83%; with SharePoint it is whatever the list says today.

### F2. Back up the history file

```powershell
Copy-Item C:\Users\slovett\apps\asset_data\readiness_history.jsonl C:\Users\slovett\apps\asset_data\readiness_history.before-F.jsonl
Test-Path C:\Users\slovett\apps\asset_data\readiness_history.before-F.jsonl
```

Expect `True`. F8 needs this copy if you roll back. From Part F on, the history file also holds Riga's daily lines, and code from before Part F would read them as US lines.

### F3. Pull the new code

```powershell
git pull
git log --oneline -1
.venv\Scripts\python -m pip install -r requirements.txt
```

`git log` should show `Prompt 12: Riga follow-ups and runbook Part F` or something newer. There are no new packages, so `pip` should only say `Requirement already satisfied`. Do not restart yet.

### F4. Add the Riga setting to `.env`

```powershell
notepad .env
```

Add this line at the end, **without quotes**, then save:

```
RIGA_WORKBOOK_PATH=C:\Users\slovett\apps\asset_data\riga\current.xlsx
```

It sits outside the repo folder, so uploads survive a re-clone and the real workbook can never be committed.

### F5. Make the Riga folder

```powershell
New-Item -ItemType Directory -Force -Path C:\Users\slovett\apps\asset_data\riga
Set-Content -Path C:\Users\slovett\apps\asset_data\riga\write_test.txt -Value ok
Remove-Item C:\Users\slovett\apps\asset_data\riga\write_test.txt
```

- **The first line** makes the folder, or does nothing if it is already there. It prints the folder either way.
- **The other two** write a small file and delete it again, to prove `slovett` can write there. They should print nothing.
- **If any line prints red text, stop** and paste it into the session.

### F6. Restart

```powershell
pm2 restart asset-management
```

### F7. Check it

**1. The banner in the log.**

```powershell
pm2 logs asset-management --lines 40 --nostream
```

Expect the line:

```
Riga workbook: C:\Users\slovett\apps\asset_data\riga\current.xlsx
```

It must not say `Riga workbook: OFF until restart, because ...`. The `Readiness history: ...` line from Part E should still be there too.

**2. The US view.** Open `http://localhost:5070/`.
- The **US** side of the new switch is highlighted, and the readiness percentage is the one you wrote down in F1 (83% with the committed CSV).
- The Alerts card has a new row, **No condition**, with 0, in grey near the bottom. It shows a number only if a US asset has a blank Material Condition.

**3. The Riga view, before any upload.** Open `http://localhost:5070/?site=riga`. Expect:

```
No Riga workbook has been uploaded yet. Upload the Riga workbook to see Riga's fleet here.
```

That is expected, not an error.

**4. Check the real workbook before uploading it.** Run the check on the exact copy you will upload:

```powershell
.venv\Scripts\python -m riga_loader --check "C:\path\to\riga workbook.xlsx"
```

It needs no running dashboard and no SharePoint settings, and its output masks serial numbers, so it is safe to paste.

- **For the sample workbook** it reads:
  - 52 rows in all;
  - Aircraft 6, Ground Control Station 1, Payload 1, Support 8, Engine 36;
  - `Headline readiness, engines left out: 80%`.
- **Two lines in section 5 are known and fine:**
  - `ENG: 1 date(s) not read, 0 formula error(s)`;
  - `GCS: no date column, so the inventory alerts skip it`.
- **Paste the whole output into a session** if anything else is listed under:
  - section 3 (`Mapped headers not found`);
  - section 4 (`Unknown Status values`);
  - section 5 (`Dates that could not be read, and formula errors`).

  Such a difference is fixed in `riga_mapping.json`, not by changing the file.

**5. The first upload, by hand.**
1. Open `http://localhost:5070/riga/upload`.
2. Choose the workbook and type your name.
3. Click **Submit**.

Expect a green-bordered box: `Uploaded <file name>: 52 Riga rows read.` (for the sample), with the rows per sheet. An amber-bordered box starting `Not uploaded:` says why, and nothing was changed; paste it into the session.

**6. The Riga view after the upload.** Open `http://localhost:5070/?site=riga`. For the sample:
- `Uploaded by <your name> on <date and time>`, in the Last Updated card;
- **80%** in the doughnut, with `16 assets in all, engines not included`;
- an **Engines** table of 36 and a **Support** table of 8, below the Aircraft, Ground Control Stations and Payloads tables. That is 52 in all;
- a yellow-bordered note listing what the check found, for the sample the one ENG date that could not be read.

If the uploaded file is newer than the sample, the counts follow the check from step 4, not these numbers.

**7. The upload record.**

```powershell
Test-Path C:\Users\slovett\apps\asset_data\riga\current.upload.json
```

Expect `True`.

**8. The other pages are US only.** Inventory, Needs Attention, Checkouts, Metrics and Export to Excel show the same US assets as before; no Riga serial numbers. Needs Attention has a new **No condition** section.

**Later uploads.** Each upload keeps the previous workbook beside it as `current-YYYYMMDD-HHMMSS.xlsx`. The 20 most recent are kept and older ones are deleted by the dashboard. Riga's trend gets one point per day: the first time the overview is opened each day, for either site, after a workbook has been uploaded.

### F8. Roll back, if anything is wrong

Use the commit you wrote down in F1:

```powershell
cd C:\Users\slovett\apps\asset_management
git checkout <commit from F1>
Copy-Item C:\Users\slovett\apps\asset_data\readiness_history.before-F.jsonl C:\Users\slovett\apps\asset_data\readiness_history.jsonl -Force
pm2 restart asset-management
```

**Why the history file is put back:** the older code does not know about sites, so it would read Riga's daily lines as US lines and mix them into the US trend. Putting back the F2 copy removes them. The days between F2 and the rollback drop out of the trend; nothing else is lost.

The dashboard is then back to how it was before Part F, with no site switch.

What is left behind, and can stay:
- **The `RIGA_WORKBOOK_PATH` line in `.env`.** The older code ignores it.
- **`C:\Users\slovett\apps\asset_data\riga` and its files.** The older code does not read them. Keep them, so the workbook is already in place when Part F is applied again.

**Getting back onto the branch.** After a rollback the clone sits on that single commit, not on the branch, so a plain `git pull` will not work. Before the next update, run:

```powershell
git checkout agent/wednesday
git pull
```

**What to paste into the session** if you rolled back:
- the output of `git log --oneline -1` from before and after the rollback;
- `pm2 logs asset-management --lines 50 --nostream`;
- the output of the check command from F7 step 4, if you got that far;
- what the page showed, including any note or error text.
