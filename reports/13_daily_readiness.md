# Report 13: Record readiness every day without a visit

**Start:** branch `agent/wednesday`, commit `92841c6` (prompt 13 added on top of `77afb30`).

## Summary

- **A timer inside the dashboard** now records the day's readiness every 15 minutes, whether or not anyone opens a page. The Readiness Trend fills in on days with no visits.
- **Page loads still record as before.** The timer is an addition, not a replacement.
- **Tests:** 236 before, 246 after, all passing. The suite was run twice, normally and with `PYTHONTZPATH=""`. No existing test changed.
- **Runbook Part G** describes the update on PROD. **Nothing was applied to PROD.**

## What changed, file by file

- **`app.py`**
  - `readiness_pass(now=None)`: one pass of the timer.
    1. It loads the US source and records today's US line, then calls `load_riga()`, which records Riga's line itself.
    2. It returns the sites it wrote a line for.
    3. It never raises.
  - `_timer_problem(site, problem)`: logs a failure once per cause, and one line when it works again, as `ReadinessHistory._set_problem` does.
  - `_timer_loop()` and `start_readiness_timer()`: the daemon thread, named `readiness-timer`. It waits 1 minute, then runs a pass every 15 minutes.
  - **Constants:** `TIMER_SECONDS = 15 * 60` and `TIMER_FIRST_SECONDS = 60`. They are constants, not settings, as the prompt asks.
  - **`load_riga()`** now keeps what `HISTORY.record()` returns, as `state['recorded']`, so the timer can log when it wrote Riga's line. Nothing else in it changed, and the pages ignore the new key.
  - **The `__main__` block** prints one more banner line and starts the timer just before `serve()`. Importing `app` starts no thread.
- **`tests/test_readiness_timer.py`** (new): 10 tests, listed below.
- **`README.md`**: a new point in "The readiness history". It says that the dashboard records each day on its own every 15 minutes, why not once a day, and that a day is still missed if the dashboard was not running that day.
- **`deploy/prod_runbook.md`**: new Part G.

## How the timer works

The dashboard runs a small background task that wakes up every 15 minutes. Each time it does what a page view does for the history:

1. It reads the US asset list and writes today's US line, if today's is not there yet.
2. It reads the uploaded Riga workbook and writes today's Riga line, if it is not there yet.

The history file still gets at most one line per site per day, because the writing code checks the last date in the file before it writes.

**Why every 15 minutes, not once a day:**
- the SharePoint source hands out the copy of the list it already holds, and only fetches a new one in the background when it is more than 5 minutes old;
- so the first read after midnight usually gets the previous day's copy, and the history refuses to record a copy that was not fetched that day;
- that first read also starts the fetch, so the next pass, 15 minutes later, has today's copy and records it;
- a single daily call would usually miss the day.

**When a pass runs:**
- the first pass is 1 minute after startup, so a restart late in the day still records that day;
- a pass that fails is logged with its cause, once, and the timer carries on;
- a second failure with the same cause is not logged again; a new cause is; one line says when it works again;
- when the history is off, or the US source has a settings problem, the pass quietly does nothing, because startup has already logged why.

**What the log shows:**
- `Readiness timer: recorded the US line for <date>.` (and the same for Riga), on a day the timer wrote the line itself;
- nothing, on days a page view wrote the line first.

## What it adds to SharePoint traffic

- **With nobody using the dashboard:** about one list read every 15 minutes. Each pass can start one background refresh, because the copy is then older than `SP_REFRESH_SECONDS` (300 s).
- **With people using it:** little or nothing extra. Pages already start a refresh every `SP_REFRESH_SECONDS`, and a pass between them just reuses the copy held.
- **It is still read only.** It makes the same GET requests as a page view.
- **The Riga workbook** is a file on the server, so it adds no network traffic.

## Test results

| Run | Result |
| --- | --- |
| Before the change, as stated in the prompt | 236 passed |
| `pytest`, after | **246 passed** |
| `PYTHONTZPATH="" pytest`, after | **246 passed** |

**No existing test changed.**

The 10 new tests, in `tests/test_readiness_timer.py`, all on made-up data:

1. **A pass with no page visits** writes today's US line from the CSV source, and logs the "recorded" line.
2. **SharePoint gives yesterday's copy first.** The fake SharePoint is held so the background refresh cannot finish early. The first pass writes nothing; once the refresh has finished, the next pass writes today's line.
3. **A second pass the same day** writes nothing and logs nothing.
4. **A failing source:**
   - over four passes, one error line;
   - when the cause changes, one more;
   - when it recovers, one "works again" line and today's line written;
   - no pass raises.
5. **History off, or an `UnavailableSource`:** nothing written, nothing logged.
6. **Riga with a good uploaded workbook** (`tests/riga_fixture.py`): a pass writes both lines.
7. **Riga with no workbook:** a pass writes the US line, with no warning.
8. **Importing `app` starts no timer thread** (`threading.enumerate()`).
9. **The loop survives an error in a pass.** With a made-up sleep and no waiting, it waits 60 s, then 900 s after every pass, and logs each error.
10. **Seven daily passes** on seven made-up days give `trend()` seven points in a row, with no gap.

**One technical point for test 2.**
- **The cause:** a SharePoint refresh started in the background can finish before the same call returns its copy. With the fast made-up SharePoint it did, and the first run of the test failed that way.
- **The fix in the test:** it holds the made-up SharePoint until the first pass has returned, which is what the real one's network delay does.
- **On PROD,** this means an occasional first pass of a day can already get today's copy. That only makes the line arrive 15 minutes sooner.

## Part G of the runbook, in outline

- **G1.** Note the current commit (`git rev-parse --short HEAD`).
- **G2.** `git pull`, `git log --oneline -1` (expect `Prompt 13: daily readiness timer`), `pm2 restart asset-management`. No new packages.
- **G3. Checks:**
  1. The new banner line in `pm2 logs asset-management --lines 40 --nostream`: `Readiness history: recorded by a timer every 15 minutes, as well as on page loads.`
  2. Two minutes after the restart, with no page opened, today's line is in `C:\Users\slovett\apps\asset_data\readiness_history.jsonl`, written by the timer or already there. The PowerShell command lists the date and site of each line.
  3. The next morning, before anyone opens the dashboard: `Select-String "Readiness timer"` on the log shows `Readiness timer: recorded the US line for <today>.` With SharePoint, expect it up to about 30 minutes after midnight Pacific time.
- **G4. Roll back:** `git checkout <commit from G1>`, `pm2 restart asset-management`. The history file needs nothing.
- **What to paste back.**

Every log text in Part G was checked against the strings in `app.py`. The PowerShell commands use only Windows PowerShell 5.1 built-ins: `Get-Content`, `Where-Object`, `ForEach-Object`, `ConvertFrom-Json`, `Select-String` and `Get-Date`.

## PROD

Nothing was applied to PROD. Part G is for Scott to carry out.

## Questions for Scott

None.
