# PROD runbook: asset_management

Runs on: PROD (Windows), in PowerShell, as `slovett`.
App: the asset tracking dashboard, read from a SharePoint CSV export. Port 5070. PM2 name `asset-management`.

Part A installs the CSV version, which has no secrets. Part C adds the SharePoint certificate and settings and tests the live connection.

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

Open `http://localhost:5070`. It should look exactly as before: same rows, and the line above the table still says `exported`.

### C5. Run the connection check

```powershell
.venv\Scripts\python -m sharepoint --check
```

It runs once and exits. It does not touch the running dashboard. It makes only read requests to Microsoft, and prints no passwords, IDs or list contents.

**Paste the whole output back into the session.** Each step says `[OK]`, `[WARN]` or `[FAIL]`, and a failure says which step failed and why. Whatever it says, leave `ASSET_SOURCE=csv` for now; the switch-over comes after we have read the output together.

If the check itself crashes with a Python error instead of printing its steps, paste that too.
