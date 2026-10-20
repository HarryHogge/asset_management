# Report 03: Live SharePoint feed

## Where the work started

- **Branch:** `agent/wednesday`, the branch Scott named and the one reports 01
  and 02 were committed to. Nothing was pushed to `main`.
- **Starting commit:** `20b1c12` ("Prompt 03: first real SharePoint test
  happens on PROD").

## What changed, file by file

- **`sharepoint.py`** (new): everything for the live source. Reading the
  settings and opening the certificate, signing in with MSAL, GET-only
  requests to Microsoft Graph and SharePoint, reading the list, the cached
  data source the app uses, and the `python -m sharepoint --check` command.
- **`assets.py`**: two small changes so both sources share the same code.
  `parse_schema_xml()` now holds the column-XML parsing that `parse_schema()`
  did, so the CSV schema line and SharePoint's `SchemaXml` go through the same
  function. `_clean_row()` also accepts a multi-choice value that is already a
  list, which is how Graph sends Status and Location. Nothing else changed,
  and a test proves the CSV rows are byte-for-byte what they were before.
- **`app.py`**: reads `ASSET_SOURCE` and builds the data source at startup.
  With `sharepoint`, a missing setting, missing certificate file or wrong
  password stops the app with a message naming the setting. Pages get the
  stale warning when there is one, and a 503 page with the reason when there
  has never been a good fetch. Logging is switched on when it runs as
  `python app.py`, with MSAL's own messages held to warnings. `.env` is now
  read from the app's folder explicitly, as UTF-8.
- **`templates/base.html`**: the line above each page says "fetched" for
  SharePoint and "exported" for the CSV, and a warning box appears when the
  data is stale.
- **`example.env`**: `ASSET_SOURCE` and every `SP_` setting, with comments
  and no secret values.
- **`.gitignore`**: adds `*.pfx`, `*.p12`, `*.pem`, `*.key`, `*.cer`.
- **`requirements.txt`**: adds MSAL and every package it pulls in, each
  pinned exactly.
- **`requirements-dev.txt`** (new): `pytest` and its packages, pinned. Only
  needed to run the tests, not on PROD.
- **`pytest.ini`** and **`tests/`** (new): 48 tests, all against made-up
  replies, none touching the network.
- **`README.md`**: a section on the SharePoint source (settings, certificate
  location, check command, switching over and back) and one on running the
  tests, with PowerShell and macOS/Linux commands.

## New packages

| Package | Version | Why |
|---|---|---|
| msal | 1.39.0 | Microsoft's sign-in library |
| cryptography | 50.0.2 | Opens the `.pfx`; MSAL needs it to sign |
| requests | 2.34.2 | HTTP |
| PyJWT | 2.15.1 | Pulled in by MSAL |
| cffi, pycparser | 2.1.1, 3.11 | Pulled in by cryptography |
| certifi, charset-normalizer, idna, urllib3 | 2026.10.19, 3.5.2, 3.20, 2.8.0 | Pulled in by requests |
| typing-extensions | 4.16.0 | Only on Python 3.10 |

Every one has a ready-made Windows wheel on PyPI, so nothing needs a
compiler. `cryptography` and `cffi` have Windows builds for Python 3.10
through 3.15; the rest are pure Python. A fresh install of
`requirements-dev.txt` installed exactly these versions and `pip check` found
no conflicts.

**These need Python 3.10 or later** (`requests`, `urllib3`, `cffi` and
`pycparser` dropped 3.9). The PROD runbook, step A1, still says 3.9 is
enough. See question 2.

## Technical choices and what they mean in practice

**Pill colors come from SharePoint's REST API, with a fallback.** Graph's
column definitions list each choice column's values but have nothing for the
column formatting. SharePoint's own REST API returns each column's
`SchemaXml`, the same XML the CSV export carries, so the existing parser reads
it unchanged. In practice:

- It needs a second sign-in token, for SharePoint rather than Graph. Same
  certificate, same app, no extra setting.
- The app's permission must also cover SharePoint's REST API. With
  `Sites.Read.All` from Graph alone, that may not be the case; with
  `Sites.Selected`, IT may have granted it for Graph only. If SharePoint
  refuses, the dashboard still works: the choices come from Graph and every
  pill is drawn in the plain outlined style. The check command says which
  happened (step 8).

**Check Out By/To shows the email address, as the CSV does.** Graph gives
only a number for a Person column. Each number is looked up in the site's
hidden "User Information List" through Graph. If Graph cannot see that list,
the lookup uses SharePoint's REST user lookup instead. In practice:

- The CSV export shows email addresses (`firstname.lastname@rdw.com`), so I
  show the same, and the Checkouts page groups people exactly as it does now.
  The prompt said "display name", but also "matching what the CSV shows";
  those disagree, see question 1.
- Each person is looked up once and remembered until the app restarts. A
  number that cannot be resolved shows as `(unknown person, ID 17)` rather
  than a blank, is written to the log, and is tried again at the next
  refresh.

**A fetched copy is reused for 5 minutes (`SP_REFRESH_SECONDS=300`).** People
edit the list by hand a few times a day, so being up to 5 minutes behind
costs nothing. In return the dashboard makes a handful of requests every 5
minutes however many people use it, far below Microsoft's throttling limits.
Pages never wait for a refresh after the first one. When the 5 minutes are up,
the next page view starts a refresh in the background and is served the
current copy meanwhile; only one refresh runs at a time. The very first view
after a start waits for the first fetch, a few seconds.

**When a refresh fails, the last good copy stays up.** Every page then shows
"This data is out of date", with when it was fetched, when the refresh
failed, and why, in plain words. It retries after 60 seconds. If there has
never been a good fetch, pages show the error (HTTP 503), not an empty table.
Every failure is logged with its cause. Logs never hold tokens, the
certificate password or list contents. A test checks this.

**Row IDs are SharePoint's item IDs.** They stay the same from one refresh to
the next and when items are edited, unlike the CSV's row positions. Every
page and the Excel export's `?ids=` filter work with them (tested). Switching
between CSV and SharePoint changes the IDs, but nothing stores them: the
inventory page keeps its filters, not IDs.

**Sign-in.** MSAL signs in as the app with the `.pfx` and its password, and
keeps each token in memory until about 5 minutes before it expires (tokens
last about an hour). At startup the dashboard opens the `.pfx` itself first,
only to prove the path and password are right and to stop with a clear
message if not.

**Dates.** Graph is expected to send DateTime columns the same way the CSV
does: the UTC moment of local midnight (`2026-10-02T07:00:00Z` is 10/2 in
Pacific time). The same conversion is used for both, and tests cover a winter
date (08:00 UTC) and a summer date (07:00 UTC). This could not be confirmed
against the real list from here, so the check command counts how many date
values fall on local midnight (step 10).

**Only GET requests.** The HTTP code has no way to send anything else, and the
fake SharePoint in the tests only answers GET.

**Columns are matched by display name through the list's own column
definitions**, never guessed. Only the 12 columns the dashboard uses are
requested. A column that cannot be found shows blank and is named in the log
and in the check output.

## What the first PROD run must confirm

Scott runs `.venv\Scripts\python -m sharepoint --check` on PROD. Look for:

- [ ] **1. Settings:** `[OK]`.
- [ ] **2. Certificate:** `[OK]`. The SHA-1 thumbprint matches the one in the
      app registration's "Certificates & secrets" page. Note the expiry date;
      a warning appears if it is under 30 days away.
- [ ] **3. Sign-in:** `[OK]`. "Permissions in the token" shows
      `Sites.Selected` or `Sites.Read.All`. If it says "none", IT has not
      granted admin consent.
- [ ] **4. Site:** the name and URL are the Flight Ops site (the URL ends in
      `/sites/FLOPS`).
- [ ] **5. List:** `Found "Asset Tracking V2"`.
- [ ] **6. Columns:** "All 12 columns the dashboard uses were found." The
      internal names should be the ones in the CSV schema: `AssetType`,
      `SerialNumber`, `PartNumber`, `Ownership`, `Status`,
      `OwnershipandLocation` (Location), `MaterialCondition`, `DateOut`,
      `CheckOutBy_x002f_To`, `AssetNotes`, `ShelfLocation`, `LastInventory`.
- [ ] **7. Items:** the count matches the number of items SharePoint shows
      for the list (146 at the last export).
- [ ] **8. Choices and colors:** "From SharePoint SchemaXml" with Asset Type,
      Location, Material Condition, Ownership and Status listed as having
      colors. "FALLBACK" means the dashboard works with plain pills; the
      reason line says why.
- [ ] **9. People:** "not resolved 0", or close to it. The last export had 8
      different people.
- [ ] **10. Dates:** "All N date values are midnight". Anything else means
      Graph sends dates differently from the CSV, and I need to see it.
- [ ] **RESULT: every step passed.**

Paste the whole output back here. It contains no secrets or item contents.

If it passes, switch over by setting `ASSET_SOURCE=sharepoint` in `.env` and
running `pm2 restart asset-management`. To go back, set `ASSET_SOURCE=csv`
and restart.

## Tests

48 tests, all with made-up data (fake site, fake people, fake serial numbers,
a certificate generated on the fly in a temporary folder). They cover
everything the prompt listed:

- paging across three pages;
- internal-name mapping, including `Serial Number` (a space),
  `Check Out By/To` (a `/`) and `Location` (internal name
  `OwnershipandLocation`);
- a winter and a summer date in `America/Los_Angeles`, matching the CSV path;
- Person lookup, including an ID that cannot be resolved, caching between
  refreshes, and the REST fallback;
- choices and colors from a sample `SchemaXml`, and the fallback when
  SharePoint refuses;
- a missing setting, a missing certificate file and a wrong password, with
  checks that no value is printed, and the app refusing to start;
- a failed refresh that keeps serving the stale copy, with checks that the log
  holds no token, password or item contents;
- the CSV source giving exactly the same rows and fields as before this
  prompt (fingerprints taken with the old code);
- every page returning 200 with the SharePoint source and with the CSV
  source, the Excel `?ids=` filter with SharePoint IDs, the stale warning on
  every page, and the error page when there has never been a good fetch;
- MSAL signing in with the `.pfx` and reusing the token, against a fake
  sign-in service;
- the check command: a full passing run whose output contains no token,
  password, tenant or client ID, serial numbers, emails or notes, and a run
  that fails at step 4 and still reports steps 1 to 3.

Results, in a fresh virtual environment with only the pinned packages:

| Run | Result |
|---|---|
| Normal | 48 passed |
| `PYTHONTZPATH=""` (`zoneinfo.TZPATH` empty, as on Windows) | 48 passed |

All of this ran on Linux. Nothing has run against the real Microsoft
services, by design; the check command is how PROD confirms it.

## Questions for Scott

1. **Check Out By/To: email address or name?** The CSV export shows email
   addresses, and the dashboard shows the same now. SharePoint's screen shows
   names ("Jack Hofmister"). The SharePoint source could show names instead,
   but the CSV has no names, so the two sources would then show different
   things. Which do you want people to see?
2. **PROD needs Python 3.10 or later.** Several of the new packages no
   longer support 3.9. Please check `python --version` on PROD. If it is 3.9,
   step A3 of the runbook will fail on the `pip install`. The runbook's A1
   line should say 3.10; I did not change it because this prompt did not
   cover `deploy/`.
3. **What should happen when a setting is missing under PM2?** As the prompt
   asks, the app stops at startup with a clear message. Under PM2 that shows
   as the process restarting over and over, with the message in
   `pm2 logs asset-management`. The alternative is to stay up and show the
   settings problem on every page. Which do you prefer?
4. **Who should see the stale-data warning?** It currently appears to every
   user on every page, with the technical reason in plain words (for example
   "Permission missing: the app signed in but is not allowed to read the
   list items"). Is that wording fine for the people who use the dashboard,
   or should they see a shorter message, with the detail only in the log?
