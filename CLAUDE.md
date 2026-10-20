# asset_management: Working Rules for Claude Code

Read this file at the start of every session.

## What this project is

A dashboard for the Flight Ops "Asset Tracking V2" SharePoint list: inventory, data problems, checkouts and metrics. Flask, served by waitress on port 5070. It runs on the PROD Windows server under PM2, next to the other ground station apps.

## How work runs

1. Scott names a branch and one prompt file, for example: "Work on branch agent/wednesday. Pull it, then read and carry out prompts/03_sharepoint_feed.md." Carry out that prompt only.
2. Work on the branch Scott named. If none was named, ask before committing. Never push to `main` unless Scott says so.
3. Write the output where the prompt says, normally `reports/NN_<name>.md`, numbered to match the prompt. Start every report with the branch and the commit the work started from.
4. Commit and push, naming the prompt number in the commit message.

Each prompt says where it runs: `Sandbox`, `Local machine` or `PROD`. Claude Code never has access to PROD; PROD steps are runbooks in `deploy/` that Scott carries out.

## Chat replies

- When a prompt completes and its report is committed, reply with exactly: "Prompt run successfully, report authored and committed."
- If a prompt cannot be completed, reply in one line: "Prompt stopped: <reason in under 20 words>. Details in <report path>."
- Ask a question in chat only when the work cannot continue without Scott's answer.

## Rules

1. **Read only.** The app reads SharePoint. Never create, change or delete anything in SharePoint or Microsoft 365.
2. **No secrets in the repo.** No certificates, passwords, client secrets or tokens in any committed file, report, log line or error message. Credentials live in `.env` and in a certificate file outside the repository. Settings needed for SharePoint have no defaults: a missing one stops with a clear error naming the setting.
3. **No new list data in the repo.** `Asset Tracking V2.csv` is already committed and may stay. Do not commit other exports, SharePoint responses or query results. Test data is made up.
4. **Everything runs on Windows.** PROD is Windows: Windows-safe paths, explicit UTF-8 encoding, no `strftime` flags like `%-d`, IANA time zone names via `tzdata`, PowerShell for anything operational.
5. **Never fail silently.** An error reaches the page or the log with its cause. Stale data is shown as stale, never as current.
6. **Product decisions belong to Scott.** What users see, what data is kept, scope and sequencing: ask in the report. Technical choices are yours; explain them in plain terms with their practical consequences.
7. **Diagnostics are read only.** When a prompt says it is a diagnostic, report findings and fix nothing.

## Writing style

Plain language for a mechanical engineer, not a software engineer. No em dashes in any document, code comment or commit message. Be specific: numbers, names, file paths.

## Where things are

| Path | Contents |
| --- | --- |
| `app.py` | Pages and settings |
| `assets.py` | Loading and cleaning the list data, and the derived views |
| `prompts/` | Numbered task prompts |
| `reports/` | Numbered outputs, one per prompt |
| `deploy/` | PROD runbooks |
| `example.env` | Every setting, with no secrets |
