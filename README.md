# asset_management
Custom dashboard driven by the Flight Ops "Asset Tracking V2" SharePoint list.
Built in the same style as `jira-dashboard`, kept in its own repo because its
credentials (Microsoft, not Jira) are separate.

It reads the list from one of two sources, set by `ASSET_SOURCE` in `.env`:

- `csv` (the default): a CSV export of the list. See "Updating the data".
- `sharepoint`: the live list, read through Microsoft Graph. See "The live
  SharePoint source".

Needs Python 3.10 or later.

## Pages

| Page | What it shows |
|---|---|
| `/` Inventory | Every asset, with filters, sorting, and Excel export of what's shown |
| `/attention` | Data problems: OUT with no holder or date, checked out but not OUT, no status, never/overdue inventory, PMC/NMC with no notes |
| `/checkouts` | Who has what, and for how long |
| `/metrics` | Condition by asset type, status, ownership, inventory age |

JSON is available at `/api/assets`, `/api/fields`, `/api/summary` and `/api/attention`.

## Running it

Linux / macOS:

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp example.env .env
.venv/bin/python app.py
```

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy example.env .env
.venv\Scripts\python app.py
```

Then open http://localhost:5070.

## Updating the data

In SharePoint, open the list and use **Export → Export to CSV**, then save the
file over `Asset Tracking V2.csv` (or point `ASSET_CSV` in `.env` at it). The
app reloads it automatically when the file changes.

The export's first line (`ListSchema=...`) holds the list's column definitions;
the app reads the choice values and pill colors from it, so new choices added
in SharePoint show up here without code changes.

Exports include colleagues' names and email addresses. Keep new ones in
`exports/` (git-ignored) rather than committing them.

## The live SharePoint source

With `ASSET_SOURCE=sharepoint`, the dashboard signs in to Microsoft as an app
(no user) with a certificate and reads the list through Microsoft Graph. It
only reads: it never changes anything in SharePoint.

### Settings

All in `.env`; `example.env` explains each one. Every one except
`SP_REFRESH_SECONDS` is required, with no defaults. If one is missing, the
certificate file is not there, or its password is wrong, the dashboard does
not start and says which setting is the problem.

| Setting | What it is |
|---|---|
| `SP_TENANT_ID` | Directory (tenant) ID, from IT |
| `SP_CLIENT_ID` | Application (client) ID of the app registration, from IT |
| `SP_SITE_ID` | Site ID of the Flight Ops (FLOPS) SharePoint site, from IT |
| `SP_LIST_NAME` | The list's name as SharePoint shows it: `Asset Tracking V2` |
| `SP_CERT_PATH` | Full path to the `.pfx` certificate file |
| `SP_CERT_PASSWORD` | The `.pfx` file's password |
| `SP_REFRESH_SECONDS` | How long a fetched copy is reused, default 300 (5 minutes) |

Write paths and passwords without double quotes. Inside double quotes a
backslash is read as a special character, so `"C:\certs\a.pfx"` breaks.

### Where the certificate goes

Outside this folder, so it can never be committed. On Windows, for example
`C:\certs\asset-dashboard.pfx`; on macOS or Linux, for example
`~/certs/asset-dashboard.pfx`. Point `SP_CERT_PATH` at it. `.gitignore`
also refuses `.pfx`, `.p12`, `.pem`, `.key` and `.cer` files as a backstop.

### Checking the connection

Run this before switching the dashboard over. It works whatever
`ASSET_SOURCE` says, does not start the web server, and leaves a running
dashboard alone. It goes through every step once (settings, certificate,
sign-in, site, list, columns, items, colors, people, dates) and says which
step failed and why. Its output holds no passwords, tokens or list contents,
so it is safe to paste into a chat.

Windows (PowerShell):

```
.venv\Scripts\python -m sharepoint --check
```

macOS / Linux:

```
.venv/bin/python -m sharepoint --check
```

### Switching over, and back

Set `ASSET_SOURCE=sharepoint` in `.env` and restart the dashboard
(`pm2 restart asset-management`). The line above each page then reads
"Data from SharePoint: Asset Tracking V2, fetched <time>". If a refresh
fails, the pages keep showing the last good copy with a warning saying how
old it is and why the refresh failed.

To go back to the CSV export, set `ASSET_SOURCE=csv` and restart. Nothing else
needs changing; the `SP_` settings are ignored.

## Tests

The tests use made-up Microsoft replies and never touch the network.

Windows (PowerShell):

```
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```

macOS / Linux:

```
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```
