# Prompt 13: Record readiness every day without a visit

Runs in: Sandbox
Type: Build and docs
Output: code, tests, README changes, a new Part G in `deploy/prod_runbook.md`, and `reports/13_daily_readiness.md`, committed with the message "Prompt 13: daily readiness timer" and pushed to `agent/wednesday`. DEV only: nothing is applied to PROD.

Read `CLAUDE.md`, `fleet.py` (`worth_recording`, `ReadinessHistory`, `trend`), `app.py` (`load`, `load_riga`, the `__main__` block) and `deploy/prod_runbook.md` first.

## Background

The Readiness Trend chart on Fleet Overview often shows only the first and last day of the week as two dots, with no line between them. The cause is in the history, not the chart:

- A day's line is written only by `HISTORY.record()`, which runs inside `load()` and `load_riga()` in `app.py`. Those run only when someone opens a page. A day with no visits gets no line.
- The chart sets `spanGaps: false` (`templates/overview.html`), so a missing day breaks the line. Two dots with gaps between them draw no line at all. This is deliberate and stays as it is: Scott chose to fix the missing data, not to hide the gaps.

Scott's decision: **a timer inside the dashboard** records each day whether or not anyone visits. No Windows Task Scheduler job.

**Facts checked on the local machine at commit `77afb30`, before this prompt was written:**

- **Tests:** 236, all passing.
- **The SharePoint source only fetches when asked.** `SharePointSource.load()` (`sharepoint.py`) returns the copy it holds and, when `SP_REFRESH_SECONDS` (default 300) has passed, starts a background refresh. So the first call of a new day usually returns the copy from the day before. `worth_recording()` turns that copy down because its `loaded_at` is not today. A second call after the refresh has finished gets today's copy and records it. The timer must allow for this: one call a day is not enough.
- **`app.load()` cannot be called from the timer as it is.** It calls Flask's `abort()` on errors, which is meant for a page request. The timer needs a path that calls `SOURCE.load()` and `HISTORY.record()` directly and logs failures instead.
- **`load_riga()` never raises** and records Riga's line itself when the workbook is good, so the timer can call it as it is.
- **The waitress server starts only in the `if __name__ == '__main__':` block** at the end of `app.py`. Tests import `app` without running that block.
- **`HISTORY.record()` is already safe to call often.** It holds a lock, checks the last date it wrote for that site, and returns `False` at once if today is already there. It never raises.
- **`HISTORY.off_reason`, `RIGA.off_reason` and `UnavailableSource`** each mean "nothing to record". The timer must not log an error every hour for these, because startup already logs them once.

## Task

### 1. The timer

Add a daemon thread, started only from the `__main__` block, just before `serve()`. Never start it at import, so tests and anything else that imports `app` get no thread.

- **Every 15 minutes:** call the US source and record, then call `load_riga()`. 15 minutes means a fresh SharePoint copy lands within the same hour even when the first call of the day gets yesterday's copy. Make the interval a module constant, not a setting.
- **One pass first, a minute after startup,** so a restart late in the day still records that day.
- **Never let the thread die.** Catch every exception in a pass, log it with its cause, and carry on with the next pass.
- **Log once, not every pass.** Use the same once-per-cause pattern as `ReadinessHistory._set_problem`:
  - log a failure once, with its cause;
  - log it again only if the cause changes;
  - log one INFO line when it works again.
- **Log one INFO line per day per site when the timer itself writes the line** (`record()` returns `True`), naming the site and the date, so the log shows the timer is working.
- **Skip quietly** when history is off, or the source is an `UnavailableSource`. Startup has already logged why.
- **Add one startup line** to the banner in `__main__`, for example "Readiness history: recorded by a timer every 15 minutes, as well as on page loads."

Keep page loads recording as they do now. The timer is an addition, not a replacement.

Put the timer code in `app.py` or a small new module, whichever reads more simply. Write it so a test can call one pass directly, with a fake clock and fake sources, and no thread or sleeping.

### 2. Tests

Use made-up data only (rule 3). At least:

1. **A pass with no page visits writes today's US line,** using the CSV source.
2. **SharePoint returns yesterday's copy first.** The first pass writes nothing; after the refresh has finished, the next pass writes today's line. Use `tests/fake_sharepoint.py`.
3. **A second pass the same day writes nothing** and logs nothing new.
4. **A failing source is logged once** across several passes, logged again when the cause changes, and gets one "works again" line when it recovers. The pass never raises.
5. **History off, or an `UnavailableSource`:** a pass does nothing and logs nothing.
6. **Riga:** with a good uploaded workbook (`tests/riga_fixture.py`), a pass writes Riga's line. With no workbook, a pass does nothing and the US line is still written.
7. **Importing `app` starts no timer thread.** Check `threading.enumerate()`.
8. **The trend has no gaps after daily passes.** Seven passes on seven made-up days give `trend()` seven points in a row.

Run the full suite twice, once normally and once with `PYTHONTZPATH=""` as before. Both must pass.

### 3. README

In the section on the readiness trend, say in plain words that the dashboard now records each day on its own every 15 minutes, so the chart fills in even when nobody opens it, and that a day can still be missed if the dashboard was not running that day.

### 4. Runbook Part G

Add Part G to `deploy/prod_runbook.md`, in the same style as Part F:

- **G1.** Note the current commit.
- **G2.** `git pull` on `agent/wednesday`, then `pm2 restart asset-management`.
- **G3.** Checks:
  - the new startup line is in the PM2 log;
  - within about 2 minutes, today's line is in the history file, or it was already there. Give the PowerShell command to list the dates in the history file, for example `Get-Content <path> | ForEach-Object { ($_ | ConvertFrom-Json).date }`, using the real history path on PROD from earlier parts;
  - the next morning, check that the log shows the timer's "recorded" line for the new day, with no page visited first.
- **G4.** Roll back: `git checkout <the commit from G1>`, then `pm2 restart asset-management`. Lines the timer already wrote stay and are the same format, so the history file needs nothing.
- What to paste back.

Check every PowerShell command for Windows, and check the expected log text against the code exactly.

## Report

Write `reports/13_daily_readiness.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What changed,** file by file.
- **How the timer works,** in a few sentences a mechanical engineer can follow, including why it runs every 15 minutes rather than once a day.
- **What it adds to SharePoint traffic:** with nobody using the dashboard, about one list read every 15 minutes (each pass can start one refresh). With people using it, little or nothing extra, because pages already refresh every `SP_REFRESH_SECONDS`. Still read only.
- **Test results** for both runs, listing any existing test that changed and why.
- **Part G:** its outline.
- **PROD:** confirm that nothing was applied to PROD.
- **Questions for Scott,** only if any come up.
