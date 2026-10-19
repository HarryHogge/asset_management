# asset_management
Custom dashboard driven by the Flight Ops "Asset Tracking V2" SharePoint list.
Built in the same style as `jira-dashboard`, kept in its own repo because its
credentials (Microsoft, not Jira) are separate.

For now it reads a CSV export of the list. A live Microsoft Graph feed is the
planned next step; `assets.load()` is the only thing that would change.

## Pages

| Page | What it shows |
|---|---|
| `/` Inventory | Every asset, with filters, sorting, and Excel export of what's shown |
| `/attention` | Data problems: OUT with no holder or date, checked out but not OUT, no status, never/overdue inventory, PMC/NMC with no notes |
| `/checkouts` | Who has what, and for how long |
| `/metrics` | Condition by asset type, status, ownership, inventory age |

JSON is available at `/api/assets`, `/api/fields`, `/api/summary` and `/api/attention`.

## Running it

```
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp example.env .env
.venv/bin/python app.py
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
