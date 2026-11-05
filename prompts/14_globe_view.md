# Prompt 14: Globe view of assets by location

Runs in: Sandbox
Type: Build and docs
Output: code, a new page, a new settings file, vendored library files, tests, README changes, a new Part H in `deploy/prod_runbook.md`, and `reports/14_globe_view.md`, committed with the message "Prompt 14: globe view" and pushed to `agent/wednesday`. DEV only: nothing is applied to PROD.

Read `CLAUDE.md`, `templates/base.html`, `templates/overview.html`, `fleet.py` (`readiness`, `fleet_readiness`, `filter_location`, `location_options`, `FamilyMap`), `app.py` (the `/` route, `PAGES`, `load`, `load_riga`) and `deploy/prod_runbook.md` first.

## Background

Scott wants a modern, dark, 3D globe that shows where the assets are, in the style of a night-side Earth seen from space: dark oceans, city lights, a thin blue glow around the edge, and glowing points. His decisions:

1. **A globe, dark style.** Not a flat map.
2. **Every place with assets gets a point on the globe,** customer sites included. Above each point floats a small list of what is there.
3. **Its own page** in the side menu, for now. Fleet Overview does not change.

**Facts checked on the local machine at commit `1625b9f`, before this prompt was written:**

- **Tests:** 246, all passing.
- **Location values in the committed CSV**, with asset counts. An asset can have more than one Location; it counts at each.

  | Location | Assets | Place |
  |---|---|---|
  | HSV Flight Ops | 74 | Huntsville, Alabama |
  | HSV LRR Internal | 19 | Huntsville |
  | HSV ENG | 10 | Huntsville |
  | Gimbal Gauntlet HSV | 10 | Huntsville |
  | SLO ENG | 14 | San Luis Obispo, California |
  | SLO Flight Ops | 6 | San Luis Obispo |
  | RDT UK | 1 | United Kingdom, city not known yet |
  | Secret Service | 1 | Customer site, not known yet |
  | Anduril | 1 | Customer site, not known yet |
  | CACI | 1 | Customer site, not known yet |
  | LRLE | 1 | Not known yet |
  | Global Support | 3 | Not a place |
  | No Verified Location | 2 | Not a place |
  | (blank) | 4 | Not a place |

  On PROD with `ASSET_SOURCE=sharepoint` the values can differ, and new ones will appear over time.
- **Riga** assets come from the uploaded workbook (`RIGA.load()` / `load_riga()` in `app.py`). All of them are at Riga, Latvia, whatever their own Location text says.
- **Readiness** uses `fleet.readiness()` and the Fleet Overview rule: engines are left out of the headline (`fleet_readiness()['overall']`).
- **Fleet Overview already filters by location:** `/?location=<value>` and `/?site=riga`. Inventory has no filter in its address, so links from the globe go to Fleet Overview.
- **The dashboard is dark by default** with a light theme toggle (`data-theme="light"` in `base.html`). Chart.js is saved locally in `static/vendor/chart-4.4.1.umd.js` so pages need no internet. Do the same for everything this page uses.

## Task

### 1. Where each Location is: `location_sites.json`

Add a settings file next to `asset_families.json`, read the same way (UTF-8, a clear error naming the file and the problem if it cannot be read, no crash). It lists **sites**, each with a display name, latitude, longitude, and the Location values found there. For example:

```json
{
  "sites": [
    {"name": "Huntsville", "lat": 34.73, "lon": -86.59,
     "locations": ["HSV Flight Ops", "HSV LRR Internal", "HSV ENG", "Gimbal Gauntlet HSV"]},
    {"name": "San Luis Obispo", "lat": 35.28, "lon": -120.66,
     "locations": ["SLO ENG", "SLO Flight Ops"]}
  ],
  "not_places": ["Global Support", "No Verified Location"]
}
```

- **Fill in** Huntsville, San Luis Obispo and Riga (Riga is placed by the workbook, not by Location values).
- **Do not guess** coordinates for RDT UK, Secret Service, Anduril, CACI or LRLE. Leave them out of the file. Scott will add them. Put the list in the report's questions.
- **Matching** is exact text, ignoring case and spaces at the ends.
- **A Location in two sites** in the file is an error, shown on the page and logged once, naming the value.

### 2. The page: `/globe`

Add "Global View" to `PAGES` and the side menu, after Fleet Overview.

**The globe:**
- Use **globe.gl** (it is built on three.js). Save its single-file build in `static/vendor/` with the version in the file name, plus its licence file. No CDN links.
- For the Earth, use NASA's **Black Marble** night-lights image, which is public domain. Save one JPEG of about 4096 by 2048 pixels, 2 MB at most, in `static/vendor/`, and state its source in the README.
- Style:
  - a black, starry background;
  - a thin blue atmosphere glow;
  - a faint triangle mesh like Scott's reference image, if it can be done simply (globe.gl hex polygons or a wire sphere); skip it if not, and say so in the report;
  - slow automatic rotation that stops while the user drags and starts again after a few seconds.
- The globe area stays dark even in the light theme. The rest of the page follows the theme.

**Points:**
- One glowing point per site.
- Its size grows with the asset count (square root, so Huntsville at about 112 does not swamp a site with 1).
- Its colour follows site readiness with the dashboard's own colours (`--good`, `--warn`, `--bad`). Use a neutral colour when readiness is None.
- A soft pulse ring is welcome if it stays subtle.

**Floating lists above each point:**
- Use globe.gl's HTML elements layer, anchored a little above the point.
- Each list shows:
  - the site name;
  - its asset count and readiness %;
  - one line per Location at the site, with count and readiness %.
- Style: small, dark, semi-transparent panels with a thin border, readable on the globe, about 260 px wide at most. Truncate long names with the full text on hover.
- Hide a list when its point is on the far side of the globe.
- Clicking a Location line opens `/?location=<value>`. Clicking Riga opens `/?site=riga`.
- With several sites close together, lists must not sit on top of each other. Offset them, or collapse to the site line and expand on hover. Say in the report which you chose.

**Beside the globe, an "Unplaced" panel** lists assets whose Location is not in the file, is in `not_places`, or is blank. Each line gives a count and links to Fleet Overview filtered to it. Nothing may disappear silently (rule 5).

**Riga:**
- One point at Riga, from the workbook.
- When the workbook is missing or unreadable, show no Riga point and one plain note saying why. The US globe still works.

**No 3D support:** when WebGL is not available, which happens on some locked-down PCs and remote desktops, show the same numbers as a plain table, with a one-line note saying why.

**Freshness:** show when the data was loaded, the same way other pages do. Show stale data as stale.

### 3. The numbers, in Python

Add one function that takes the US assets, the Riga state and the site mapping, and returns the sites with their counts and readiness, the per-Location lines, and the Unplaced lines. Pass it to the page as JSON, as `overview.html` does with `trend`. Do the counting in Python so it can be tested, not in JavaScript.

### 4. Tests

Use made-up data only (rule 3). At least:

1. Sites get the right counts and readiness. An asset with two Locations at the same site counts once for the site and once on each Location line.
2. Engines are left out of readiness, as on Fleet Overview.
3. Unknown Locations, `not_places` values and blank Locations go to Unplaced with correct counts.
4. Matching ignores case and spaces at the ends.
5. A Location in two sites, and an unreadable or missing `location_sites.json`, give a clear message on the page and one log line. The page still loads.
6. Riga is present with a good workbook and absent, with its note, without one.
7. `/globe` returns 200, is in the side menu, and loads its scripts from `static/vendor/` only. There are no `http` script or image addresses in the page.
8. The links in the data point at `/?location=...` with the value URL-encoded.

Run the full suite twice, once normally and once with `PYTHONTZPATH=""`.

Then open the page in a real browser on the sandbox if one is available. Check that the globe draws, rotates, the lists float and hide correctly, and the fallback table shows with WebGL turned off. Say in the report what was checked by eye and what was not.

### 5. README

Add:
- the new page;
- `location_sites.json`: what it is, and how Scott adds a site or a Location in plain steps, including how to find latitude and longitude, for example by right-clicking a spot in Google Maps;
- the sources and licences of globe.gl and the Earth image.

### 6. Runbook Part H

Add Part H to `deploy/prod_runbook.md`, in the style of Part G:

- note the commit;
- pull and `pm2 restart asset-management`;
- checks:
  - the Global View page loads from a normal user PC;
  - the globe draws;
  - points show for Huntsville, San Luis Obispo and Riga;
  - the Unplaced panel lists the rest;
  - the browser's developer tools show no requests leaving the server;
- one check from a remote-desktop session, if Scott uses one, to see whether the globe or the fallback table shows;
- roll back;
- what to paste back.

Check every PowerShell command for Windows.

## Report

Write `reports/14_globe_view.md` in plain language:

- **Start:** the branch and the commit the work started from.
- **What changed,** file by file, with the size of each vendored file.
- **What the page shows,** for the made-up test data and for the committed CSV.
- **The choices made** for overlapping lists and the triangle mesh, and any styling left out.
- **Test results** for both runs, and what was checked by eye in a browser.
- **Part H:** its outline.
- **PROD:** confirm that nothing was applied to PROD.
- **Questions for Scott:**
  - Where to put RDT UK, Secret Service, Anduril, CACI and LRLE: city, or latitude and longitude. Until then they appear under Unplaced.
  - Any others that come up.
