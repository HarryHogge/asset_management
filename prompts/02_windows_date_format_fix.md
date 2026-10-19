# Prompt 02: Windows date format fix (report 01)

Runs in: Sandbox
Type: Build
Output: code and README changes, plus `reports/02_windows_date_format_fix.md`, committed with the message "Prompt 02: Windows date format fix" and pushed.

Work on the branch Scott named at the start of the session. If none was named, ask before committing. Never push to `main`.

Read `reports/01_windows_timezone_fix.md` first.

## Background

Report 01 found that `templates/base.html` line 286 formats the export time with `loaded_at.strftime('%-m/%-d/%Y %-I:%M %p')`. The `%-` flags only exist in the Linux and macOS C library. On Windows, Python raises `ValueError: Invalid format string`, and because the line is in the base template, every HTML page returns 500 on PROD.

## Task

1. **Format the export time in Python, not with `strftime` flags.**
   - Add a template filter in `app.py` next to the existing `mdy` filter, in the same style, that produces the same text the template produces today on Linux: month, day and hour without leading zeros, minutes with one, then AM or PM. For example `10/19/2026 1:05 PM`, `3/4/2026 12:30 AM`, `12/1/2026 12:00 PM`.
   - Use it in `templates/base.html` in place of the `strftime` call.
   - It must not use `%-`, `%#`, or any other platform-specific `strftime` flag.
2. **Check the output matches.** For at least the three example times above plus midnight (`12:00 AM`) and a two-digit hour (`11:59 PM`), show that the new filter gives the same string the old `strftime` call gives on Linux.
3. **Check nothing else does this.** Search the whole repo (Python files and templates) for `strftime` and `%-` and `%#`. List every `strftime` call you found and say whether it is safe on Windows.
4. **Request every page.** With Flask's test client, request `/`, `/attention`, `/checkouts`, `/metrics`, `/api/summary` and `/api/export/assets.xlsx`. All must return 200.
5. **README.** Under "Running it", keep the existing commands and add the Windows PowerShell equivalents next to them (`.venv\Scripts\pip`, `.venv\Scripts\python`, `copy`).

## Report

`reports/02_windows_date_format_fix.md`, in plain language:

- The branch and the commit the work started from.
- What changed, file by file.
- The comparison table from step 2, the `strftime` list from step 3, and the status code of each page from step 4.
- Anything else you saw that would fail on a Windows server. Report it; do not fix it.

## Chat reply

When the report is committed and pushed, reply with exactly: "Prompt run successfully, report authored and committed." If the prompt cannot be completed, reply in one line with the reason and the report path.
