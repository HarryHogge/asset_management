# Report 02: Windows date format fix

## Where the work started

- **Branch:** `agent/wednesday`, the branch Scott named earlier in the session
  and the one report 01 was committed to. Nothing was pushed to `main`.
- **Starting commit:** `2e88e7f` (the commit that added
  `prompts/02_windows_date_format_fix.md`).

## What changed

- **`app.py`**: added a `mdy_time` template filter next to `mdy`. It builds
  the export time by hand: `mdy()` for the date, then the hour on a 12-hour
  clock (0 becomes 12), minutes padded to two digits, and AM or PM. It uses no
  `strftime` at all.
- **`templates/base.html`**: the "exported …" line now uses
  `{{ loaded_at | mdy_time }}` instead of
  `loaded_at.strftime('%-m/%-d/%Y %-I:%M %p')`.
- **`README.md`**: "Running it" keeps the Linux/macOS commands and adds the
  Windows PowerShell versions (`.venv\Scripts\pip`, `.venv\Scripts\python`,
  `copy`).

## The output matches

Each time was formatted with both the old `strftime` call (on Linux, where it
works) and the new filter:

| Time | Old strftime (Linux) | New `mdy_time` | Same? |
|---|---|---|---|
| `2026-10-19 13:05` | `10/19/2026 1:05 PM` | `10/19/2026 1:05 PM` | yes |
| `2026-03-04 00:30` | `3/4/2026 12:30 AM` | `3/4/2026 12:30 AM` | yes |
| `2026-12-01 12:00` | `12/1/2026 12:00 PM` | `12/1/2026 12:00 PM` | yes |
| `2026-10-19 00:00` (midnight) | `10/19/2026 12:00 AM` | `10/19/2026 12:00 AM` | yes |
| `2026-10-19 23:59` (two-digit hour) | `10/19/2026 11:59 PM` | `10/19/2026 11:59 PM` | yes |
| `2026-01-09 09:07` (single-digit month, day, hour) | `1/9/2026 9:07 AM` | `1/9/2026 9:07 AM` | yes |

The live page renders `exported 10/19/2026 8:10 AM.`, the same as before.

## Other `strftime` and `%-` / `%#` use

I searched every Python file, template, script, `.env` and `.txt` file.

- **`strftime` calls:** none are left. The only match is the word in the new
  filter's comment in `app.py`.
- **`%-` and `%#`:** no date-format uses. The only matches are `{%-` in
  `templates/_macros.html`, which is Jinja's whitespace-trimming syntax and has
  nothing to do with dates.
- **Other date formatting:** `mdy()` in `app.py` (hand-built, safe),
  `isoformat()` in `assets.py` and the templates (safe), and the Excel cell
  format `m/d/yyyy` in the export (an Excel format string read by Excel, not
  by `strftime`; safe).

## Every page returns 200

Through Flask's test client:

| Page | Status |
|---|---|
| `/` | 200 |
| `/attention` | 200 |
| `/checkouts` | 200 |
| `/metrics` | 200 |
| `/api/summary` | 200 |
| `/api/export/assets.xlsx` | 200 |

This ran on Linux. The `strftime` call that would have failed on Windows is
gone, but I have not run the app on Windows itself.

## Other things that could trip up a Windows server (not fixed)

1. **`SITE_TIMEZONE` must be an IANA name.** `America/Los_Angeles` works
   (report 01's `tzdata` covers it). A Windows-style name such as
   `Pacific Standard Time` would raise `ZoneInfoNotFoundError` and every page
   would fail. Worth a note for whoever sets up `.env` on PROD.
2. **Replacing the CSV while it's open in Excel.** Excel locks files it has
   open on Windows. Saving a new export over `Asset Tracking V2.csv` while it
   is open in Excel will fail, so close it first.
3. **Firewall prompt on first start.** The app listens on `0.0.0.0:5070`.
   Windows Defender Firewall usually asks whether to allow Python on the
   network the first time; until someone allows it, other machines can't
   reach the dashboard.
