# Decisions

Scott's decisions for asset_management, with reasons where given. Newest sections at the bottom. Claude Code must treat these as settled and must not change this file.

## October 20, 2026: SharePoint source (report 03)

| Topic | Decision |
| --- | --- |
| Where the real connection is tested | On PROD. The sandbox cannot reach SharePoint, so the sandbox builds against made-up responses, and Scott runs `python -m sharepoint --check` on PROD while the live app stays on `ASSET_SOURCE=csv`. |
| Check Out By/To | With the SharePoint source, show the person's **name**, as SharePoint's own screen does. The CSV source keeps showing what the export holds (email addresses); the CSV is temporary. |
| A missing or wrong SharePoint setting | The dashboard **stays up** and every page says which setting is wrong and why, never printing the value. It does not refuse to start (under PM2 that is an endless restart loop). |
| Stale data | Users see a **short note**: when the data is from, and that SharePoint could not be reached. The technical reason goes to the log and to the check command, not the page. |
| PROD Python | PROD runs Python 3.10 or later, which the SharePoint packages need. |

## October 20, 2026: first PROD check (Part C)

The connection check passed on PROD: `Sites.Selected` permission, 146 items, all 12 columns, 8 of 8 people resolved, all 90 dates at local midnight. Only the column formatting failed: SharePoint REST refused the token (HTTP 401).

| Topic | Decision |
| --- | --- |
| Pill colors | Use the colors in today's list, saved from the committed CSV's schema line into a small committed file with no personal data. Scott asks IT to grant the app SharePoint's own `Sites.Selected` permission; once that works, colors come live from the list and the saved file is only a fallback. |
