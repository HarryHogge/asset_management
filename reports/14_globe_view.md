# Report 14: Globe view of assets by location

**Start:** branch `agent/wednesday`, commit `786f0bc` (prompt 14 added on top of `1625b9f`).

## Summary

- **A new page, Global View,** at `/globe`, in the side menu after Fleet Overview:
  - a dark 3D globe of the Earth at night, with a glowing point at each site that has assets;
  - a small list floating above each point;
  - an Unplaced panel beside the globe.
- **`location_sites.json`,** a new settings file, says where each Location is.
- **Everything the page uses is saved in `static/vendor/`,** so it needs no internet. The browser check saw no request leave the server.
- **When a PC cannot draw 3D,** the page shows the same numbers as a table, with a note saying why.
- **Tests:** 246 before, 267 after, all passing in both runs. One existing test changed (below).
- **Nothing was applied to PROD.**

## What changed, file by file

| File | What | Size |
| --- | --- | --- |
| `globe.py` (new) | Reads `location_sites.json` (`read_sites`, and `SiteMap`, which logs a problem once). Works out the page's numbers (`globe_data`) | |
| `location_sites.json` (new) | Huntsville, San Luis Obispo, Riga's place, and the two `not_places` | |
| `templates/globe.html` (new) | The page: globe, floating lists, Unplaced panel, the fallback table, notes | |
| `static/vendor/globe.gl-2.46.2.min.js` (new) | globe.gl single-file build, with three.js inside | 1,885,160 bytes |
| `static/vendor/globe.gl-2.46.2.LICENSE.txt` (new) | globe.gl's MIT licence | 1,072 bytes |
| `static/vendor/black_marble_2016_3600x1800.jpg` (new) | NASA Black Marble 2016, 3600 by 1800 pixels | 779,638 bytes |
| `app.py` | "Global View" in `PAGES` after Fleet Overview; `LOCATION_SITES = globe.SiteMap()`; the `/globe` route | |
| `tests/test_globe.py` (new) | 21 tests (below) | |
| `tests/test_fleet.py` | One assert updated for the new menu order | |
| `README.md` | The new page in the page table; a "Global View" section: the page, `location_sites.json` and how to add to it, sources and licences | |
| `deploy/prod_runbook.md` | New Part H; the opening paragraph now also names Parts G and H | |

**Where the vendored files came from:**
- **globe.gl 2.46.2** (released August 22, 2026) was taken from the npm package. The download was checked against the SHA-512 npm publishes for it.
  - The single-file build has three.js and globe.gl's other libraries inside it, with their licence notices.
  - I searched it for web addresses. It loads nothing from the internet by itself.
- **The Earth image** is NASA's own 0.1 degree "Black Marble 2016", 3600 by 1800 pixels.
  - It is the nearest ready-made size to the 4096 by 2048 asked for, and well under 2 MB.
  - Resizing it would have needed an image package the project does not have, so it is used as published.
  - NASA images are public domain.

## How the numbers are worked out

All the counting is in Python (`globe.globe_data`), and the page gets the result as JSON, as `overview.html` does with the trend.

- **Matching.** A Location matches a site when its text is the same, ignoring capitals and spaces at the ends.
- **A site's numbers:**
  - its asset count counts each asset once, even with two Locations there;
  - its readiness is Fleet Overview's headline rule: engines are left out of the %, but counted in the asset count;
  - each Location line counts every asset with that Location.
- **Colour:**
  - green at 80% and above, amber at 50% and above, red below 50%;
  - grey when there is nothing to work out a % from (for example, only engines).
  - The % text is written in Python, rounded the way Fleet Overview rounds, so the globe and the table always agree (80.5% shows as 80% on both).
- **Point size** grows with the square root of the asset count.
- **Unplaced** gets one line for each Location value that is:
  - not in the file ("not in location_sites.json yet");
  - in `not_places` ("not a place");
  - blank ("no Location", linked to `/?location=%28none%29`, Fleet Overview's own value for "no location").

  An asset with one placed and one unplaced Location shows in both places, so nothing is lost.
- **Links** go to `/?location=<value>`, URL-encoded, using the exact text from the list, which is what Fleet Overview's filter matches. Riga goes to `/?site=riga`, and Riga's Location lines to `/?site=riga&location=<value>`.
- **Riga:**
  - Riga is one point, at the place `location_sites.json` gives it, with all the workbook's assets.
  - Without a good workbook there is no Riga point, and a one-line note says why. The note has one wording each for: no upload yet, folder off, mapping unreadable, and workbook unreadable.
  - If the file had no place for Riga, its assets would be listed under Unplaced instead.
- **A problem with `location_sites.json`:** it may be missing, not JSON, badly shaped, or have one Location in two places. Then:
  - the page shows a note naming the problem;
  - the log says it once (again only if it changes);
  - every asset is listed under Unplaced;
  - the page still loads.

## What the page shows

**For the committed CSV** (worked out by `globe_data` on it, and seen in the browser):

| Site | Assets | Readiness | Locations |
| --- | --- | --- | --- |
| Huntsville | 113 | 80% | HSV Flight Ops 74 (78%), HSV LRR Internal 19 (84%), Gimbal Gauntlet HSV 10 (90%), HSV ENG 10 (80%) |
| San Luis Obispo | 20 | 100% | SLO ENG 14 (100%), SLO Flight Ops 6 (100%) |

- Huntsville is 113, not the "about 112" in the prompt: the four Locations add up to 113 assets, with no asset in two of them.
- **Unplaced, 14 in all:**
  - Global Support 3 and No Verified Location 2 ("not a place");
  - Anduril, CACI, LRLE, RDT UK and Secret Service, 1 each ("not in location_sites.json yet");
  - (blank) 4.
- **Riga:** no point, and the note "No Riga workbook has been uploaded yet, so Riga has no point on the globe."

**For the made-up test data:** the tests check the numbers for made-up sites ("Alpha Town", "Bravo City", "Far Port") and made-up assets:
- counts, readiness, engines, Unplaced and links;
- Riga with a made-up workbook from `tests/riga_fixture.py`.

## Choices made

1. **Lists close together: collapse, and expand on hover.**
   - **The rule.** A site within 40 degrees of arc (about 4,400 km) of a site with more assets shows only its top line (name, count, %), with a small arrow. Its Location lines open when the mouse is over it, drawn on top.
   - **Where.** This is decided in Python, so it is tested.
   - **Why 40 degrees.** I first used 8 degrees. The browser check showed the San Luis Obispo list covering part of Huntsville's: the two are 28 degrees apart, and a list is about as tall on screen as 30 degrees of the globe. So San Luis Obispo now shows its top line only.
   - **Lifted clear as well.** Even the top line alone still covered part of Huntsville's list at some angles, the second check showed. So the page also measures the lists on screen ten times a second. A list that would cover a bigger site's list is lifted just clear of it, and drops back once the globe has turned them apart.
   - **A thin line** joins a lifted list to its point. It was added after the last browser check, from its note that nothing linked the lifted list to its point, and was not seen by eye.
2. **The triangle mesh: done simply.**
   - **How.** A very faint blue wireframe sphere just above the Earth, made from the globe's own three.js parts. The lines of a sphere's wireframe form triangles.
   - **Why not the alternatives.** globe.gl's hex polygons need country outlines, which would be another download. A separate copy of three.js would mean loading it twice.
   - **If it fails,** the mesh is skipped and the rest of the globe is not affected.
3. **Stars** are drawn by the page's own style sheet: tiny dots in the dark background. There is no star image to download.
4. **Lists on the far side.** A list hides, and cannot be clicked, once its point has turned past the edge of the globe as seen from the camera.
   - **Why not globe.gl's own check.** In the browser it hid lists 8 seconds or more after their point passed the edge, and left one showing over Asia. The page now works out the edge itself, from the camera's height, a few degrees in from the true edge.
   - **The result.** In the third browser check each list hid 2 to 5 seconds after its point reached the edge, at the slow turning speed. That is a few degrees of turn, while the list's own width still overhangs the edge.
   - **Also,** the lists now float at 2% of the Earth's radius above the surface instead of 5%.
5. **The globe stays dark in the light theme.** Its area keeps the dark theme's colours, including the dark theme's green, amber and red, so the points look the same in both themes. The fallback table and the Unplaced panel follow the theme.
6. **The table is shown until the globe has drawn.** If the browser has no WebGL, the library does not load, or the globe fails to start, the table stays and a note says which. With JavaScript off entirely, the table is shown anyway.
7. **Styling left out:**
   - no glowing "bloom" effect on the points (it needs extra three.js add-ons);
   - the pulse ring is a soft ring in the point's colour, fading as it spreads.

## Test results

| Run | Result |
| --- | --- |
| Before, as stated in the prompt | 246 passed |
| `pytest`, after | **267 passed** |
| `PYTHONTZPATH="" pytest`, after | **267 passed** |

**Existing test changed:** `tests/test_fleet.py::test_overview_is_first_in_the_nav_at_the_home_page`. It checked that Inventory comes right after Fleet Overview in the menu. It now checks Fleet Overview, then Global View, then Inventory, because the menu order changed as the prompt asks.

**The 21 new tests** (`tests/test_globe.py`), against the prompt's list:
1. **Counts and readiness:** an asset with two Locations at one site counts once for the site and once on each line.
2. **Engines** are left out of the %, but counted. A site with only engines has no %.
3. **Unplaced:** unknown, `not_places` and blank Locations, with correct counts, and every asset accounted for.
4. **Matching** ignores capitals and spaces at the ends.
5. **Bad files.** Three cases go through the page: a missing file, a file that is not JSON, and one Location in two sites. Each shows its note on the page, logs one line over three page loads, and the page still answers 200. Five more bad files are refused by the reader, each with its reason.
6. **Riga:** a point with a good workbook (from the made-up data, and through the page with the made-up uploaded workbook), and absent with its note in each of the four states.
7. **The page:**
   - `/globe` answers 200 and is highlighted in the side menu, after Fleet Overview;
   - its only script is `/static/vendor/globe.gl-2.46.2.min.js`, and the Earth image is from `static/vendor/`;
   - the page has no `http://` or `https://` address at all.
8. **Links** are URL-encoded, for example `R&D / Bay #2` gives `/?location=R%26D%20%2F%20Bay%20%232`.

Also tested:
- the rounding of the % text matches Fleet Overview;
- the collapse rule for close sites;
- the committed `location_sites.json` is valid;
- the fallback table holds the same numbers;
- the committed CSV places Huntsville and San Luis Obispo.

**Checked by eye in a browser** (Chromium with Playwright, in the sandbox, against the dashboard on the committed CSV):
- **The globe draws** with the Black Marble image, the blue glow and the starry background, with a green point and a floating list at Huntsville and San Luis Obispo.
- **It rotates:** two screenshots 6 seconds apart show North America moving, the lists moving with it, and the Huntsville list hidden once it had turned to the far side.
- **Network:** only 3 requests, all to the local dashboard: the page, the globe.gl file and the Earth image. No console errors; only 4 warnings from the graphics driver about speed.
- **The light theme:** the globe area stayed dark while the side menu, header and Unplaced panel went light.
- **No WebGL** (switched off in the browser): the globe is hidden, and the note and the table show, with Huntsville 113 / 80% and San Luis Obispo 20 / 100% and their Locations.
- **The first check found** the overlapping lists, a list hiding late at the edge, and Huntsville showing 81% on the globe but 80% in the table. Two later checks confirmed the fixes:
  - **The second check:** the % now matches and San Luis Obispo is collapsed, but its top line still overlapped and hiding was still late.
  - **The third check, after the lift and the page's own edge check:**
    - no two visible lists overlapped in about 50 seconds of sampling;
    - hovering San Luis Obispo shows its lines on top;
    - lists hide 2 to 5 seconds after their point reaches the edge;
    - still only local requests and no console errors.

**Not checked by eye:**
- dragging with a real mouse, and the 4-second restart of the rotation;
- clicking through from a list;
- a Riga point in the browser (no workbook was uploaded on the test server; the tests cover it);
- a real remote desktop. Part H step 6 covers this on PROD.

## Part H of the runbook, in outline

- **H1.** Note the current commit.
- **H2.** `git pull`, `git log --oneline -1` (expect `Prompt 14: globe view`), `pm2 restart asset-management`. No new packages and no new setting.
- **H3. Checks:**
  1. The three new files in `static\vendor` with their sizes, and `location_sites.json`, with `Get-ChildItem` and `Test-Path`.
  2. The page from a normal user PC: the menu entry, the `Data from ...` line, the night globe with its glow, turning slowly.
  3. The points: Huntsville 113 / 80% and San Luis Obispo 20 / 100% with the committed export (San Luis Obispo shows its top line, and opens on hover). Riga if a workbook is uploaded, or its note. Lists hide on the far side, and the links work.
  4. The Unplaced panel and what each line should say.
  5. In the browser's developer tools (F12, Network), no request to any other domain.
  6. From a remote desktop, if one is used: the globe, or the note and table. Both are correct.
  7. The log line `Location sites: 2 site(s) read from location_sites.json.`
- **H4.** Roll back: `git checkout <commit from H1>`, `pm2 restart asset-management`. Nothing else needs putting back.
- **What to paste back.**

Every log text and page note in Part H was checked against the code. The PowerShell commands use only Windows PowerShell 5.1 built-ins: `Get-ChildItem`, `Select-Object`, `Test-Path` and `Select-String`.

## PROD

Nothing was applied to PROD. Part H is for Scott to carry out.

## Questions for Scott

1. **Where are RDT UK, Secret Service, Anduril, CACI and LRLE?** A city, or a latitude and longitude, for each. Until then they appear under Unplaced as "not in location_sites.json yet". The README says how to add them; I can add them if you send the places.
2. **The colour bands.** Fleet Overview has no green, amber and red bands for a readiness %, so I chose: green at 80% and above, amber at 50% and above, red below 50%. They are two constants in `globe.py` (`GOOD_PCT`, `WARN_PCT`). Do you want other bands?
3. **"Global Support" and "No Verified Location"** are listed as not places, as in the prompt's example. Should any other Location be treated that way?
