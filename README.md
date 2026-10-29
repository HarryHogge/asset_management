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
| `/` Fleet Overview (home page) | Readiness of the whole fleet and of Aircraft, Ground Control Stations and Payloads, a table per family, the number of assets each data-problem rule affects, and a 7-day readiness trend. A US / Riga switch at the top: `/?site=riga` shows the Riga site (see "Riga"). Filter by Location with `?location=...`. The old address `/overview` redirects here, keeping the site and the filter |
| `/riga/upload` | Upload a new Riga fleet workbook. Linked from the Riga view, not from the nav |
| `/inventory` Inventory | Every asset, with filters, sorting, and Excel export of what's shown |
| `/attention` | Data problems: OUT with no holder or date, checked out but not OUT, no status, no condition (Material Condition blank), never/overdue inventory, PMC/NMC with no notes |
| `/checkouts` | Who has what, and for how long |
| `/metrics` | Condition by asset type, status, ownership, inventory age |

Every page has the same left nav. Inventory's "Export to Excel" button is at
the top right of the page, beside its heading.

JSON is available at `/api/assets`, `/api/fields`, `/api/summary` and `/api/attention`.

Inventory, Needs Attention, Checkouts, Metrics, the JSON and the Excel
export show US assets only. Riga assets appear only on the overview's Riga
view.

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
certificate file is not there, or its password is wrong, the dashboard still
starts (so PM2 does not restart it over and over), but every page says which
setting is the problem, without showing its value. The JSON endpoints answer
with the same message and HTTP 503. The problem is written to the log once,
at startup. Fix `.env` and restart the dashboard.

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

Run it from the dashboard's folder; elsewhere Python answers "No module
named sharepoint".

### Renamed columns

Anyone can rename a column in the list. The dashboard finds each column by
its display name, and if that fails, by its internal name, which SharePoint
never changes (for example "Asset Type" was renamed "Assets"; its internal
name is still `AssetType`). The dashboard keeps its own label, and the log
says once: "Column Asset Type was found by its internal name AssetType;
SharePoint now calls it "Assets"." The check command prints the same as a
NOTE under step 6. A column that cannot be found either way still shows
blank, with a WARNING in the check and in the log.

### Switching over, and back

Set `ASSET_SOURCE=sharepoint` in `.env` and restart the dashboard
(`pm2 restart asset-management`). The line above each page then reads
"Data from SharePoint: Asset Tracking V2, fetched <time>". Check Out By/To
shows each person's name, as SharePoint's own screen does (the CSV export
shows email addresses instead).

If a refresh fails, the pages keep showing the last good copy with a short
note, for example "Data is from 9:40 AM. SharePoint could not be reached;
showing the last copy." The reason is in the log
(`pm2 logs asset-management`), and `python -m sharepoint --check` shows it
too. If there has never been a good copy since the dashboard started, pages
say SharePoint could not be reached. Either way the dashboard tries again
every minute.

To go back to the CSV export, set `ASSET_SOURCE=csv` and restart. Nothing else
needs changing; the `SP_` settings are ignored.

### Pill colors

The colored pills (Status, Asset Type and so on) come from the first of these
that works, tried again at every refresh:

1. **Live**, from the list's own column formatting, through SharePoint's REST
   API. This needs the app to have SharePoint's own `Sites.Selected`
   permission, not only Microsoft Graph's.
2. **Saved**, from `pill_colors.json` in this folder: the colors as they were
   in an export. A choice added to the list since then shows in the plain
   outlined style until the file is refreshed.
3. **Default**: every pill in the plain outlined style, if `pill_colors.json`
   is missing or damaged.

The log says which one is in use when the dashboard starts and whenever it
changes. Step 8 of the check command says the same, and lists any choices the
saved file does not have.

`pill_colors.json` holds only column names, choice values and colors, never
item data, names or emails.

### Refreshing the saved pill colors

After choices or colors change in SharePoint:

1. Export the list (**Export → Export to CSV**) and save the file in
   `exports/` (git-ignored), for example `exports/Asset Tracking V2.csv`.
2. Run the script on it.

   Windows (PowerShell):

   ```
   .venv\Scripts\python scripts\save_pill_colors.py "exports\Asset Tracking V2.csv"
   ```

   macOS / Linux:

   ```
   .venv/bin/python scripts/save_pill_colors.py "exports/Asset Tracking V2.csv"
   ```

   It prints the number of choices and colors for each column and rewrites
   `pill_colors.json`. With no file named, it reads the committed
   `Asset Tracking V2.csv`.
3. Commit `pill_colors.json` (not the export) and restart the dashboard, or
   wait for the next refresh: the file is read again at each one.

## Fleet Overview

### Readiness

Material Condition decides readiness: FMC is Ready (green), PMC is Limited
(yellow), NMC is Not Ready (red). Destroyed/Lost is shown in gray and left
out. Readiness % = FMC / (all assets minus Destroyed/Lost). An asset with a
blank condition stays in the total as "No condition", so it lowers the
percentage. With nothing to divide by, the page shows a dash.

### Asset families

`asset_families.json` in this folder places each Asset Type in Aircraft,
Ground Control Station, Payload, Support or Engine. The match is on the
exact text. Engines are Riga's; they have their own table on the Riga view
and are left out of the headline readiness and the family cards, but the
history still counts them.
A type the file does not name, or a blank one, shows as **Unmapped**, and the
Support and Unmapped card lists those types. To place a new type, add a line
to the file, for example `"New Kit": "Support",`, and commit it. The file is
read at each page view, so no restart is needed. If the file is missing or
damaged, every asset shows as Unmapped, the page says so, and the log gives
the reason.

### The readiness history

The first good data load of each day, on any page, adds one US line to the file
named by `READINESS_HISTORY_PATH` (default `data/readiness_history.jsonl`,
which git ignores; a relative path resolves against this folder). The
Readiness Trend chart reads it, so it fills in one point per day. A
SharePoint copy is only recorded when it is fresh: not stale, and fetched
that day. A CSV export is recorded as it is.

- **At startup** the dashboard makes the file's folder if it is missing, and
  the startup banner prints the file's path. If the folder cannot be made,
  the history is off until the next restart: the log says why once, the
  banner says it is off, and the overview shows a short note.
- **If a line cannot be written** although the folder exists, the pages
  still load, the overview shows a short note, the log gives the reason
  once, and the next page load tries again.
- The setting used to be called `READINESS_HISTORY`. That name is ignored
  now, with a warning in the log at startup if it is still set.
- Each line says its site, `"site": "US"` or `"site": "Riga"`, and each
  site gets at most one line a day. Lines from before Riga was added have no
  site and are read as US. Riga's line is written by the first good load of
  the Riga workbook each day (Riga's calendar day), whenever the overview is
  opened for either site. With no workbook uploaded there is no Riga line.
  The trend shows the chosen site's lines.

## Riga

The Riga site keeps its fleet in an Excel workbook with one sheet per kind of
equipment, not in SharePoint (report 10 describes it). The dashboard reads it
with `riga_loader.py`, and the Riga view of the overview shows it.

### Uploading the workbook

Open the Riga view (`/?site=riga`) and use **Upload Riga workbook**, or go to
`/riga/upload`. Choose the `.xlsx` file, type your name, and submit. The file
is checked before it replaces the current one. It is refused, and the current
one stays in use, if it does not end in `.xlsx`, cannot be opened as a
workbook, holds no Riga rows, is larger than 10 MB, or no name was given.
A good upload is saved to `RIGA_WORKBOOK_PATH` (default
`data/riga/current.xlsx`); the previous file is kept beside it as
`current-YYYYMMDD-HHMMSS.xlsx` (or `...-2.xlsx` and so on if that name is
taken). The 20 most recent backups are kept: after each successful upload,
older ones are deleted, newest decided by the date and time in the name.
Only files named exactly like that are ever deleted. If one cannot be
deleted, the upload still counts, the page says so in one line, the log
names the file, and the next upload tries again. `current.upload.json` records who
uploaded it, when, the original file name and the rows per sheet. The Riga
view then says "Uploaded by <name> on <date and time>", in Riga's time zone.

Anyone who can open the dashboard can upload, and the name is whatever they
type: the dashboard has no sign-in.

### How the workbook is read

`riga_mapping.json` holds every Riga rule, so a difference in the real file
is fixed there, with no code change:

- the 10 equipment sheets, each with its Asset Type, its family (a check on
  `asset_families.json`, which decides), its header row, and the header text
  of the six columns read (serial, Status, Location, owner, notes, date);
- the sheets to ignore (VEHICLES, ZALENIEKI STOCK, OVERALL);
- what each Riga Status means: RTF is FMC, RTF WITH REMARKS and FCF REQUIRED
  are PMC, GROUNDED is NMC, WRITTEN OFF is Destroyed/Lost;
- the text date formats, day first: `dd.mm.yyyy` and `dd.mm.yy`.

Only the mapped columns are read, from the row below the header row, and
only where the serial number is filled in, so titles, legends and side
tables are skipped. Headers match ignoring case and surrounding spaces, not
spelling. A sheet in neither list, a Status value not in the map, a header
not found, a date that cannot be read and a formula error such as `#REF!`
are each listed in the log and in a note on the Riga view; the rows are
still shown. The Riga view has a table for each family, Engines and
Support included (the US view has no Support table). Riga rows have no
Status, Date Out or Check Out By/To, so the Riga tables leave those columns out and the Riga alerts use only: No
condition, Never inventoried, Inventory overdue (both only on sheets with a
date column; that date is when the row was last updated and signed, not a
physical count) and PMC/NMC with no notes.

### Checking a workbook

Run this on any workbook before trusting the numbers. It needs no running
dashboard and no SharePoint settings, and its output masks serial numbers
and shows notes only as their length, so it is safe to paste into a chat.

Windows (PowerShell):

```
.venv\Scripts\python -m riga_loader --check "C:\path\to\riga workbook.xlsx"
```

macOS / Linux:

```
.venv/bin/python -m riga_loader --check "path/to/riga workbook.xlsx"
```

It lists the sheets found, mapped, ignored and unknown; the rows per sheet;
mapped headers not found; unknown Status values; unreadable dates and
formula errors; the first 3 rows of each sheet; and the totals per family.

### Pill colors in the light theme

Some of the list's pill colors are pale (mint, light gray, gold, cyan and
others) and fade into the white page. In the light theme only, each pill is
adjusted so its text has a contrast of at least 4.5 to 1 and the pill stands
out from the page at 3 to 1 or more: dark text is darkened as needed, a pale
pill gets a border in its text color, and a dark pill with white text is
darkened as needed. The dark theme shows the list's colors exactly.
`pill_colors.json` keeps the list's own colors.

## Tests

The tests use made-up Microsoft replies and a made-up Riga workbook built in
`tests/riga_fixture.py`, and never touch the network. They write the
readiness history and Riga uploads to a temporary folder, never to `data/`.
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
