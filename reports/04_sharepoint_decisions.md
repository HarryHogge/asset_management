# Report 04: SharePoint source, Scott's decisions and saved colors

## Where the work started

- **Branch:** `agent/wednesday`, as for reports 01 to 03. Nothing was pushed
  to `main`.
- **Starting commit:** `0eecf4b` ("Add PROD runbook Part C and decisions"),
  after `git pull`.

## What changed, file by file

- **`sharepoint.py`**
  - **Names.** Check Out By/To now shows the person's display name (the
    `Title` of the User Information List entry, or SharePoint REST's `Title`
    on the fallback route). This is the same lookup that resolved 8 of 8 on
    PROD. Only if a person has no name does it fall back to their email. An
    unresolved ID still shows as `(unknown person, ID 17)` and is logged.
  - **Colors.** `read_schema()` now uses three sources, in this order:
    1. live `SchemaXml`;
    2. choices from Graph, colored from `pill_colors.json`;
    3. default pills.

    It records which source it used, why `SchemaXml` was not used (with the
    HTTP status), why the saved file could not be used, and any choice that
    Graph has but the saved file does not.
  - **Logging the colors.** The data source writes the color result to the
    log only when it changes. A 401 that repeats at every 5 minute refresh
    is logged once, and "read live" is logged once when the permission
    starts working. `SchemaXml` is still asked for at every refresh.
  - **Check command, step 8.** It now says `LIVE`, `SAVED` or `DEFAULT`. On
    a 401, the reason line adds: "The app probably needs SharePoint's own
    Sites.Selected permission, in addition to the one for Microsoft Graph it
    already has." It also lists choices the saved file is missing.
  - **Time zone.** `SITE_TIMEZONE` is now checked when the SharePoint source
    is set up, so a bad value is a settings problem like the others instead
    of a crash.
- **`app.py`**
  - **Bad setting.** A bad setting no longer stops the app.
    `make_source()` logs the problem once and returns a stand-in source.
    From then on, every page returns HTTP 503 with an error page naming the
    setting, and every JSON endpoint returns `{"error": "..."}` with HTTP
    503. This covers a missing setting, a missing certificate file, a wrong
    password, a bad `SP_REFRESH_SECONDS`, a bad `SITE_TIMEZONE` and an
    unknown `ASSET_SOURCE`.
  - **No good fetch.** If there has never been a good fetch, the page says
    "SharePoint could not be reached" with no technical reason. The reason
    is already in the log from the failed fetch.
  - **Logging at startup.** Logging is now set up before the data source is
    made, so the startup problem appears in the log in the normal format.
  - **Time filter.** A new `short_time` filter shows just the time for
    today and the date and time for an earlier day, so "9:40 AM" never
    means yesterday. It uses the same hand-built clock as `mdy_time`, with
    no `strftime`.
- **`templates/base.html`**
  - The stale box is now one line: "Data is from 9:40 AM. SharePoint could
    not be reached; showing the last copy." The reason is no longer on the
    page.
  - The "Data from ..." line is hidden on the error page, which has no data
    to describe.
- **`templates/error.html`** (new): the error page, with the usual header and
  menu.
- **`assets.py`**
  - `saved_colors(fields)` picks the choices and colors out of
    `parse_schema`'s result.
  - `read_saved_colors(path)` reads `pill_colors.json` and rejects a file
    that is not in the expected shape, for example a color that is not
    `#a1b2c3`.
  - Nothing that the CSV source uses changed.
- **`scripts/save_pill_colors.py`** (new): reads the `ListSchema=` line of an
  export with the existing `parse_schema` code and writes `pill_colors.json`
  as UTF-8.
- **`pill_colors.json`** (new): generated from the committed
  `Asset Tracking V2.csv`. It covers five columns:

  | Column | Choices | With a color |
  |---|---|---|
  | Asset Type | 29 | 29 |
  | Location | 8 | 8 |
  | Material Condition | 4 | 3 |
  | Ownership | 7 | 7 |
  | Status | 4 | 4 |

  The one Material Condition choice without a color is also uncolored in
  the list itself. The file holds column keys, choice values and colors,
  nothing else.
- **`README.md`**
  - The settings section now says the dashboard stays up when a setting is
    wrong.
  - The switch-over section describes names and the short stale note.
  - New sections: "Pill colors" and "Refreshing the saved pill colors", with
    PowerShell and macOS/Linux commands.
- **`example.env`**: the SharePoint comment now says a bad setting keeps the
  dashboard up and names the setting.
- **Tests:** `tests/test_pages.py`, `tests/test_sharepoint.py` and
  `tests/fake_sharepoint.py` were changed, and `tests/test_pill_colors.py`
  is new. See below.

No new packages.

## Tests

67 tests, up from 48. All replies are made up and nothing touches the
network. New or changed tests, by step of the prompt:

1. **Names**
   - With the SharePoint source, names appear on Inventory, Checkouts, the
     JSON and the Excel export, and the email does not.
   - The two Attention rules that test Check Out By/To ("checked out to
     someone, but not marked OUT" and "OUT, but not checked out to anyone")
     pick the right items.
   - A person with no name falls back to their email.
   - The REST route also gives the name.
   - The CSV source still shows email addresses.
   - The check command prints no names.
2. **Bad settings**
   - Four cases: missing setting, missing certificate file, wrong password,
     bad refresh time.
   - In each case, all 9 pages and endpoints return 503 naming the setting
     and print no value of any setting.
   - The log holds exactly one "Settings problem" line across all those
     requests, and no password.
   - An unknown `ASSET_SOURCE` also keeps the app up.
3. **Stale note**
   - The exact wording, on all 4 pages.
   - The reason (`server problem`, `HTTP 503`) is in the log and not on any
     page.
   - The date is added when the copy is from an earlier day.
   - With no good fetch, the page and the JSON say "SharePoint could not be
     reached" and do not give the reason, which is in the log.
4. **Colors**
   - Live `SchemaXml` wins over the saved file.
   - On a 401, the colors come from the saved file. A choice missing from
     the saved file (`BAILMENT`) and a column missing from it (Asset Type)
     get the default pill and are listed.
   - A missing, non-JSON or wrongly shaped saved file gives default pills.
   - Over four refreshes with a 401, `SchemaXml` is asked for 4 times but
     logged once. When the permission arrives, colors go live and that is
     logged once.
   - Check step 8 wording is right for all three sources, including the
     `Sites.Selected` hint on a 401.
5. **`pill_colors.json`**
   - Only column keys, choice values, colors and the four structural words
     are in it.
   - None of the serial numbers, part numbers, people, notes, shelf
     locations or dates in the CSV appear in it. One serial number cell in
     the export holds an asset type ("Ping 200x Transponder Kit"); that is
     a choice value, so the test skips it.
   - It matches what the script produces from the committed export.
   - The script writes UTF-8 and refuses an export with no schema line.

| Run | Result |
|---|---|
| Normal | 67 passed |
| `PYTHONTZPATH=""` (`zoneinfo.TZPATH` empty, as on Windows) | 67 passed |

I also started the real app (`python app.py` under waitress) with
`ASSET_SOURCE=sharepoint` and no `SP_` settings. It stayed up and wrote the
problem to the log once. `/`, `/checkouts`, `/api/assets` and the Excel
export each returned 503 naming the missing settings, with no further log
lines.

All of this ran on Linux in a fresh virtual environment with only the pinned
packages.

## What Scott should see on PROD after switching

Pull, install and restart as in runbook Part C, step C2. Then set
`ASSET_SOURCE=sharepoint` in `.env` and run `pm2 restart asset-management`.

**The log** (`pm2 logs asset-management --lines 30 --nostream`):

- the banner "Data source: SharePoint list Asset Tracking V2, refreshed
  every 300 seconds";
- within a few seconds of the first page view, `SharePoint refresh OK: 146
  items`;
- one line `Pill colors: using the saved colors in pill_colors.json, because
  SharePoint did not give the column formatting: ... (HTTP 401 ...) The app
  probably needs SharePoint's own Sites.Selected permission ...`. If the
  next line lists choices "not in pill_colors.json", those were added to the
  list after the committed export; see "Refreshing the saved pill colors" in
  the README.
- The pill colors line should not repeat at each 5 minute refresh. It will
  be followed one day by `Pill colors: read live from SharePoint` once IT
  grants the permission.

**Every page:**

- the first page view after the restart takes a few seconds (the first
  fetch); later ones are immediate;
- the line above the content reads "Data from SharePoint: Asset Tracking V2,
  fetched 10/20/2026 h:mm AM/PM", in Pacific time;
- no yellow note box.

**Inventory (`/`):**

- 146 rows, the same assets as the CSV view;
- pills in the same colors as now;
- the Check Out By/To column shows names such as "Jack Hofmister" instead of
  `firstname.lastname@rdw.com`;
- the filters list the same values as before;
- searching for a person's name finds their items;
- "Export to Excel" gives a file with names in the Check Out By/To column.

**Needs Attention (`/attention`):** the same groups and counts as on the CSV
view, if nobody has edited the list since the CSV export. Edits since then
will show up here, which is the point.

**Checkouts (`/checkouts`):**

- the same people, now as names;
- the same number of items each;
- no "(unknown person, ID n)" entries. The PROD check resolved 8 of 8.

**Metrics (`/metrics`):** the same charts and totals as the CSV view, again
allowing for edits since the export.

**Going back:** set `ASSET_SOURCE=csv` and restart; everything returns to the
email addresses and "exported".

**If something is wrong:** a page titled "The asset list cannot be shown
right now" means one of two things:

- it names a setting: fix that setting in `.env` and restart;
- it says SharePoint could not be reached: the reason is in
  `pm2 logs asset-management`, and `python -m sharepoint --check` shows it
  step by step.

## Questions for Scott

1. **Two people with the same name** would be grouped together on the
   Checkouts page, because it groups by what it shows. Today's 8 people all
   have different names, so this does not matter now. If it ever does, the
   page could group by the person's ID and show the name. Leave it as is
   for now?
2. **Runbook wording, for information.** Part C, step C5 says each check
   step prints `[OK]`, `[WARN]` or `[FAIL]`. The check actually prints
   `[OK]`, `[FAILED]` or `[--]` (not run). Step 8 stays `[OK]` when it uses
   saved or default colors and says which in words. I did not change
   `deploy/`, since this prompt did not cover it.
