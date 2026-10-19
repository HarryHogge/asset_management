# Prompt 01: Windows time zone fix

Runs in: Sandbox
Type: Build
Output: `requirements.txt` change, plus `reports/01_windows_timezone_fix.md`, committed with the message "Prompt 01: Windows time zone fix" and pushed.

Work on the branch Scott named at the start of the session. If none was named, ask before committing. Never push to `main`.

## Background

This app is about to be deployed to the PROD server, which runs Windows. `app.py` and `assets.py` use Python's `zoneinfo` to turn SharePoint dates into the site's local calendar day (`SITE_TIMEZONE`, default `America/Los_Angeles`).

On Linux and macOS, `zoneinfo` reads the operating system's time zone database. Windows has no such database, so `zoneinfo` needs the `tzdata` package from PyPI. `requirements.txt` does not list it, so on PROD `ZoneInfo('America/Los_Angeles')` would raise `ZoneInfoNotFoundError` and the app would fail on every start.

## Task

1. Add `tzdata` to `requirements.txt`, pinned to an exact version like the other lines. Use the current release on PyPI.
2. Check the whole repo for any other `zoneinfo` or time zone use that this does not cover, and list what you found.
3. Prove the fix without Windows. Python only reads the system database through `zoneinfo.TZPATH`, and setting the environment variable `PYTHONTZPATH` to an empty string empties it, the same as on Windows. In a fresh virtual environment outside the repo:
   - With `tzdata` **not** installed and `PYTHONTZPATH=""`, show that `ZoneInfo('America/Los_Angeles')` fails. This proves the test reproduces the PROD failure.
   - With `requirements.txt` installed and `PYTHONTZPATH=""`, start the app with Flask's test client and request `/`, `/attention`, `/checkouts`, `/metrics`, `/api/summary` and `/api/export/assets.xlsx`. All must return 200.
4. Delete the throwaway virtual environment afterwards. Commit nothing except `requirements.txt` and the report.

## Report

`reports/01_windows_timezone_fix.md`, in plain language:

- The branch and the commit the work started from.
- The `tzdata` version pinned.
- The result of each step of 3, with the exact error from the first check and the status code of each page.
- Anything else found in step 2 that could break on Windows.

## Chat reply

When the report is committed and pushed, reply with exactly: "Prompt run successfully, report authored and committed." If the prompt cannot be completed, reply in one line with the reason and the report path.
