# Prompt 03: Live SharePoint feed

Runs in: Sandbox
Type: Build
Output: code, tests, `example.env`, `README.md` and `.gitignore` changes, plus `reports/03_sharepoint_feed.md`, committed with the message "Prompt 03: SharePoint feed" and pushed.

Read `CLAUDE.md` first, then `assets.py` and `app.py`.

## Background

The dashboard reads a CSV export of the SharePoint list. This prompt adds a second source: the list itself, read live through Microsoft Graph. The CSV source stays and remains the default.

The sandbox cannot reach SharePoint, and has no credentials and must not get any. Build and test everything against made-up responses. The first real connection will happen on the PROD Windows server, through a runbook Scott carries out. So the code must be right on Windows the first time, and the check command (step 5) must tell us everything we need from one run.

What Scott has from IT, for an Entra app registration:

- Tenant ID
- Client ID
- Site ID of the Flight Ops (FLOPS) SharePoint site
- A certificate as a `.pfx` file, plus its password

There is no client secret. Authenticate with the certificate. It is not yet known which Graph permission the app was granted (probably `Sites.Selected` or `Sites.Read.All`).

## What the list looks like

From the `ListSchema=` line of the committed CSV, the columns the app uses are:

| Display name | SharePoint type |
| --- | --- |
| Asset Type, Material Condition, Ownership | Choice |
| Status, Location | MultiChoice |
| Serial Number, Part Number, Shelf Location | Text |
| Asset Notes | Note |
| Date Out, Last Inventory | DateTime |
| Check Out By/To | User (a Person column) |

Graph returns fields under their internal names, which can differ from the display names (spaces become `_x0020_` and so on). Map them through the list's column definitions, never by guessing.

## Task

### 1. Settings

Add to `example.env`, with comments and no values for anything secret:

- `ASSET_SOURCE`: `csv` (default) or `sharepoint`.
- `SP_TENANT_ID`, `SP_CLIENT_ID`, `SP_SITE_ID`, `SP_LIST_NAME` (example value `Asset Tracking V2`).
- `SP_CERT_PATH`: full path to the `.pfx`, outside the repository.
- `SP_CERT_PASSWORD`.
- `SP_REFRESH_SECONDS`: how long a fetched copy is reused before fetching again. Pick a sensible default and explain it.

When `ASSET_SOURCE=sharepoint`, every `SP_` setting except `SP_REFRESH_SECONDS` is required, with no fallback values. A missing one, a missing certificate file or a wrong password stops at startup with an error that names the setting and never prints its value.

Add `*.pfx`, `*.p12`, `*.pem`, `*.key` and `*.cer` to `.gitignore`.

### 2. Sign-in

Use MSAL (`msal` on PyPI) with certificate credentials, app-only, scope `https://graph.microsoft.com/.default`. Pin every new package to an exact version in `requirements.txt`, and check each one installs on Windows without a compiler. Reuse the token until it is close to expiry.

### 3. Reading the list

New module, for example `sharepoint.py`. Make only GET requests.

- Find the list by `SP_LIST_NAME` on the site `SP_SITE_ID`.
- Read the column definitions and every item, following `@odata.nextLink` until the end. Never stop at the first page.
- Turn each item into exactly the row shape `assets._clean_row` produces today, with the same keys, types and cleaning. Share code with the CSV path where it is the same, rather than copying it.
- Dates: check whether Graph returns DateTime fields the same way the CSV does (a UTC instant of local midnight). Make sure each one lands on the same calendar day the CSV path gives.
- **Check Out By/To is a Person column.** Graph returns only a lookup ID for it (a field ending in `LookupId`), not the name. Resolve each ID to the person's display name, matching what the CSV shows, through the site's hidden "User Information List" or another read-only Graph route. Cache the lookups. If a name cannot be resolved, show that clearly instead of a blank, and record it.
- **Choices and pill colors.** The CSV path reads each choice column's allowed values and colors from the `CustomFormatter` in the column XML. Find out whether Graph exposes the formatter.
  - If Graph does not, the SharePoint REST endpoint for the list's fields returns `SchemaXml`, the same XML the CSV schema line contains. It needs a token for the SharePoint resource, not Graph. If you use it, reuse `parse_schema`'s logic for the XML.
  - If neither works, fall back to Graph's choice values with default pill colors.
  - Explain the choice in the report.
- Row `id`: use the SharePoint item ID. Check that every page and the Excel export's `?ids=` filter still work with it.

### 4. Caching and failure

- `load()` keeps returning `{'fields', 'assets', 'loaded_at', 'source'}`, so the pages do not change.
- For SharePoint, `loaded_at` is when the data was fetched, and `source` reads like `SharePoint: Asset Tracking V2`.
- Reuse a fetched copy for `SP_REFRESH_SECONDS`. Only one request should refresh at a time; others use the current copy meanwhile.
- If a refresh fails after a good fetch, keep serving the last good copy. Show on every page that it is stale, since when, and why, in plain words. If there has never been a good fetch, the page shows the error, not an empty table.
- Log every failure with its cause. Logs must never contain tokens, the certificate password, or list contents.

### 5. A connection check for the first PROD run

A command, for example `python -m sharepoint --check`, that runs the whole path once and prints a short report. Scott will run it on PROD while the live app keeps serving the CSV, then paste its output back here, so:

- it must run on its own, reading `.env` but ignoring `ASSET_SOURCE`, without starting the web server or touching the running app;
- when a step fails, it says which step failed and the cause in plain words (for example: sign-in refused, certificate password wrong, permission missing, site not found, list not found), and still reports the steps before it;
- its output must be safe to paste into a chat.

It prints:

- whether sign-in worked;
- the Graph permissions in the token, by name only, read from the token's `roles` claim;
- the site's name and URL, and whether the list was found;
- the number of items, and every column's display name, internal name and type;
- whether choices and colors came from `SchemaXml` or from the fallback;
- how many Check Out By/To IDs were resolved and how many were not.

It prints no secrets and no item contents, and makes only GET requests. It must run in Windows PowerShell as `.venv\Scripts\python -m sharepoint --check`.

### 6. Tests

Add `pytest` with made-up Graph responses (fake names, fake serial numbers), with no network access. At least:

- paging across three pages;
- internal-name mapping, including one display name with a space and one with `/`;
- the date round trip for a winter and a summer date in `America/Los_Angeles`;
- Person lookup, including one ID that cannot be resolved;
- choices and colors from a sample `SchemaXml`, and the fallback;
- a missing setting, a missing certificate file, and a failed refresh that keeps serving the stale copy;
- the CSV source still giving the same rows as before this prompt;
- every page returning 200 with the SharePoint source, using the fake responses.

Run the tests a second time with `PYTHONTZPATH=""`, as in report 01.

### 7. README

Add a section on the SharePoint source: the settings, where the certificate goes, the check command, and how to switch back to CSV. Give Windows PowerShell commands as well as macOS and Linux ones.

## Report

`reports/03_sharepoint_feed.md`, in plain language:

- The branch and the commit the work started from.
- What changed, file by file.
- Each technical choice (formatter source, Person lookup route, refresh time, row IDs) and its practical consequence.
- What the first PROD run must confirm against the real list, as a checklist. Scott will run the check command there; list what to look for in its output.
- Test results, including the `PYTHONTZPATH=""` run.
- Any question that needs Scott's decision.
