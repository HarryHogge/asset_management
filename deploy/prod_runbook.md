# PROD runbook: asset_management

Runs on: PROD (Windows), in PowerShell, as `slovett`.
App: the asset tracking dashboard, read from a SharePoint CSV export. Port 5070. PM2 name `asset-management`.

This version has no secrets. The SharePoint API key and certificate are not used yet.

Run the commands one block at a time and check each result before going on.

## Part A: First install

### A1. Check Python

```powershell
python --version
```

Needs 3.9 or later. Any version the other Python services already run on is fine.

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

- the Inventory page shows the assets;
- the line above the table reads `Data from Asset Tracking V2.csv, exported <date and time>`, where the time is when you saved the file;
- Attention, Checkouts and Metrics all open.

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
