# Prompt 04: SharePoint source, Scott's decisions and saved colors

Runs in: Sandbox
Type: Build
Output: code, tests, README and `example.env` changes, plus `reports/04_sharepoint_decisions.md`, committed with the message "Prompt 04: SharePoint decisions" and pushed.

Read `CLAUDE.md`, `docs/decisions.md` (both October 20 sections) and `reports/03_sharepoint_feed.md` first.

## Background

Scott ran `python -m sharepoint --check` on PROD. Every step passed:

- Permission in the Graph token: `Sites.Selected`.
- Site "Redwire Flight Operations Hub", list "Asset Tracking V2" found, 146 items in one page.
- All 12 columns found, under the internal names report 03 expected. `Last Inventory` is `dateTime (dateOnly)`; `Date Out` is `dateTime (dateTime)`.
- Check Out By/To: 8 resolved, 0 not resolved, through the Graph "User Information List" route.
- All 90 date values at midnight in `America/Los_Angeles`.

One gap: step 8 fell back to plain pills. SharePoint REST refused the token with HTTP 401 while reading the column formatting. The most likely cause is that the app has Graph's `Sites.Selected` but not SharePoint's own `Sites.Selected`. Scott is asking IT to add it.

The live dashboard on PROD still runs with `ASSET_SOURCE=csv`. After this prompt, Scott switches it to `sharepoint`.

## Task

### 1. Check Out By/To shows names with the SharePoint source

- With `ASSET_SOURCE=sharepoint`, show each person's display name, the way SharePoint's own screen does, from the same lookup that resolved 8 of 8 on PROD.
- The CSV source is unchanged and keeps showing what the export holds.
- An unresolved person still shows clearly as unresolved, never blank.
- Check the Checkouts page, the Attention rules that test Check Out By/To, the inventory filters and the Excel export all still behave correctly with names.

### 2. A bad SharePoint setting keeps the dashboard up

Replace the refuse-to-start behavior from prompt 03.

- With `ASSET_SOURCE=sharepoint` and a missing setting, a missing certificate file or a wrong password, the app starts and stays up under PM2.
- Every page returns an error page that names the setting and says what is wrong in plain words, without printing any value. The JSON endpoints return the same as an error with a non-200 status.
- The cause is written to the log once at startup, not on every request.
- `python -m sharepoint --check` keeps reporting these exactly as it does now.

### 3. Stale data: short note for users, detail in the log

- When a refresh fails after a good fetch, pages show only a short note, for example: "Data is from 9:40 AM. SharePoint could not be reached; showing the last copy." Use the site's time zone and the `mdy_time` style already in `app.py`.
- The technical reason (sign-in refused, permission missing and so on) goes to the log, and stays available to the check command. It is not shown on the page.
- If there has never been a good fetch, the error page from step 2's style says SharePoint could not be reached, in plain words, and the reason goes to the log.

### 4. Saved pill colors

- Add a script, for example `scripts/save_pill_colors.py`, that reads the `ListSchema=` line of a CSV export with the existing `parse_schema` code and writes, for each choice column, its choice values in order and their colors. Write it to a committed file, for example `pill_colors.json`, as UTF-8.
- The file must contain only column keys, choice values and colors. No item data, names or emails. Check this in a test.
- Run the script on the committed `Asset Tracking V2.csv` and commit the result.
- With the SharePoint source, take choices and colors in this order:
  1. SharePoint REST `SchemaXml`, when it works;
  2. otherwise the choices from Graph, colored from the saved file. A choice that is in Graph but not in the saved file gets the default pill;
  3. otherwise, if the saved file is missing or unreadable, default pills, as now.
- Keep retrying `SchemaXml` so colors go live once IT adds the permission. Log the 401 once, and again only when the result changes, not on every refresh.
- The check command's step 8 says which of the three was used. For the 401 case, the reason line adds, in plain words, that the app probably needs SharePoint's own `Sites.Selected` permission in addition to Graph's.
- README: how to refresh the saved file from a new export.

### 5. Tests

Add or change tests for each of steps 1 to 4, including:

- names shown with the SharePoint source and the CSV source unchanged;
- each bad-setting case starting up and returning the error page on every page, with no value printed;
- the stale note's exact wording, and that the reason is in the log but not in the page;
- the three color sources, a choice missing from the saved file, and the 401 logged only once across several refreshes;
- `pill_colors.json` holding no item data.

Run the whole suite, then again with `PYTHONTZPATH=""`.

## Report

`reports/04_sharepoint_decisions.md`, in plain language:

- The branch and the commit the work started from.
- What changed, file by file.
- Test results for both runs.
- What Scott should see on PROD after switching to `ASSET_SOURCE=sharepoint`, page by page, so he can check it.
- Any question that needs Scott's decision.
