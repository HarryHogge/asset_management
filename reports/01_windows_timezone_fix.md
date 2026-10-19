# Report 01: Windows time zone fix

## Where the work started

- **Branch:** `agent/wednesday`. This is the branch Scott had pushed earlier
  in the session ("push that branch so I can have something to commit these
  files to"), and all dashboard work has been committed to it. The ship gate
  approves pushes to this branch only. Nothing was pushed to `main`.
- **Starting commit:** `18ca307` (the commit that added
  `prompts/01_windows_timezone_fix.md`).

## The fix

`requirements.txt` now pins **`tzdata==2026.5`**, the current release on PyPI
(uploaded 2026-10-03). On Windows, Python's `zoneinfo` has no system time zone
database to read and falls back to this package. Linux and macOS keep using
the system database, so nothing changes there.

## Proving it without Windows

Both checks ran in a fresh virtual environment (Python 3.11.2) created outside
the repo and deleted afterwards. `PYTHONTZPATH` was set to an empty string, so
`zoneinfo.TZPATH` was `()`, which is how Windows looks to Python.

**Check 1: without `tzdata`, the PROD failure reproduces.**
With nothing installed, `ZoneInfo('America/Los_Angeles')` failed with:

```
ZoneInfoNotFoundError: 'No time zone found with key America/Los_Angeles'
```

The app calls this when it loads the CSV and when it works out "today", so on
Windows every page would fail.

**Check 2: with `requirements.txt` installed, the app works.**
After `pip install -r requirements.txt`, `tzdata` 2026.5 was present and
`ZoneInfo('America/Los_Angeles')` loaded. Through Flask's test client:

| Page | Status |
|---|---|
| `/` | 200 |
| `/attention` | 200 |
| `/checkouts` | 200 |
| `/metrics` | 200 |
| `/api/summary` | 200 |
| `/api/export/assets.xlsx` | 200 |

## Other time zone and date code in the repo

Every time zone use is covered by this fix:

- `app.py`: `ZoneInfo(SITE_TIMEZONE)` for today's date (line 34), and passes
  `SITE_TIMEZONE` to the loader.
- `assets.py`: `ZoneInfo(tz_name)` in `load()` (line 180); `timezone.utc` and
  `astimezone()` in `_to_local_date()`. `timezone.utc` is built into Python and
  needs no database.
- `example.env`: sets `SITE_TIMEZONE=America/Los_Angeles`. Any other zone
  name set there is also covered by `tzdata`.

## Things that will still break on Windows (not fixed here)

This prompt allowed changes to `requirements.txt` only, so these are reported,
not fixed:

1. **Every page will still fail on Windows, for a different reason.**
   `templates/base.html` line 286 formats the export time as
   `loaded_at.strftime('%-m/%-d/%Y %-I:%M %p')`. The `%-` flags (no leading
   zero) come from the Linux/macOS C library. Windows' C library rejects them,
   so Python raises `ValueError: Invalid format string`. That line is in the
   base template every page uses, so the `/`, `/attention`, `/checkouts` and
   `/metrics` pages would all return 500. The JSON endpoints and the Excel
   export don't use it. I could not reproduce this on Linux; it follows from
   how Windows' C library handles `strftime`. The fix is to format the numbers
   in Python instead (the `mdy` filter in `app.py` already does this for
   dates).
2. **The README's run steps use Linux paths.** `.venv/bin/pip` and
   `.venv/bin/python` are `.venv\Scripts\pip` and `.venv\Scripts\python` on
   Windows, and `cp` is `copy`. This doesn't affect the app, only whoever
   follows the README on PROD.
