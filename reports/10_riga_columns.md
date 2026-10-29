# Report 10: Riga Excel export compared with the US list

## Where the work started

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `0d0d513` ("Prompt 08: runbook for prompts 06 and 07"), after `git pull`.
- **Where it ran:** the local machine, not the sandbox. `data/samples/riga_assets.xlsx` is only on this Mac. Git ignores it twice: `data/` since prompt 06, and `*.xlsx`. Committing it would break rule 3, because it holds real Riga data: serial numbers, initials, a vehicle number plate and defect notes. Scott chose to run this read-only diagnostic locally and commit only the report.
- **No code changed.** The workbook stays out of git.
- **No row contents copied.** This report has no serial numbers, initials, notes, part numbers or number plates. It does include column names, counts and choice values.

## Summary

- **Not one list.** The Riga file is a 13-sheet tracker, not one list like the US one:
  - 10 sheets each hold one kind of equipment;
  - 1 holds vehicles;
  - 1 holds spare-part stock;
  - 1 (OVERALL) is built from formulas over the others.
- **Assets.** The 10 equipment sheets hold **52 assets**. None of their serial numbers is in the US list.
- **Different column meanings.** Riga's **Status** is a readiness value (RTF, GROUNDED and so on), which corresponds to the US **Material Condition**. Nothing in Riga matches the US Status (IN, OUT, RMA, BAILMENT), Check Out By/To or Date Out.
- **No Asset Type column.** The type comes from the sheet name.
- **Missing families.** None of the Riga types is in `asset_families.json`. Two are loose matches.
- **The current loader cannot read the file.** Beyond being Excel and not CSV, the column headers start on row 3, there are side tables beside the data, broken formulas, and dates written as `dd.mm.yyyy` text.
- **Recommendation:** a separate Excel loader that produces the same cleaned rows the pages already use, driven by a small per-sheet map. Reusing the CSV loader with a column map is not workable (Step 5).
- **The file looks trimmed.** The OVERALL sheet links to 40 assets, but 33 of those links are broken (`#REF!`), and the aircraft sheets hold only 7 aircraft. See question 1.

## Step 1: Sheets, rows and columns

### The sheets

| Sheet | Title in row 1 | Header row | Rows | What a row is |
|---|---|---|---|---|
| Mk2.x | PNC Mk2 | 3 | 1 | Aircraft |
| MK2 | PNC Mk2/2.X | 3 | 1 | Aircraft |
| 2.5 VTOL | PNC Mk2.5 VTOL | 3 | 1, plus 13 rows of side tables | Aircraft |
| MK3 | PNC Mk3 VTOL | 3 | 2 | Aircraft |
| VXE | PNC VXE | 3 | 1 | Aircraft |
| EPS | EPSILON GIMBALS | 3 | 1 | Gimbal payload |
| TRC | TRACKING ANTENNA | 3 | 7 | Tracking antenna |
| PPC | Catapult | 2 | 1 | Launcher |
| GCS | GROUND CONTROL STATIONS | 3 | 1 | Ground control station |
| ENG | ENGINES | 3 | 36 | Engine |
| **Assets on the 10 sheets above** | | | **52** | |
| VEHICLES | FLOPS CAR UNIT | 2 | 1 | Car |
| ZALENIEKI STOCK | Critical Spare Part List | 2 | 82 | Spare part line with quantities |
| OVERALL | STATUS TABLE (READ ONLY) ... | 2 | 41 | Formula links to the other sheets |

**Row 2 is a color legend** on 9 of the 10 equipment sheets, for example "FLIGHT READY", "NOT FLIGHT READY", "Insurance expired" and "Insurance will expire soon". The colors come from conditional formatting driven by the Status column.

**There are no hidden rows or columns.**

### Columns on the five aircraft sheets

These sheets share one layout with small differences. Each cell gives the cells filled out of the sheet's rows.

| Column | Type | Mk2.x (1) | MK2 (1) | 2.5 VTOL (1) | MK3 (2) | VXE (1) | Notes |
|---|---|---|---|---|---|---|---|
| S/N | Text; a number on VXE | 1 | 1 | 1 | 2 | 1 | |
| Configuration | Text | 1 | 1 | 1 | 2 | 1 | Values in Step 2 |
| Frequency | Text, or a number on MK3 | 1 | 1 | 1 | 2 | 1 | For example `4.4 (SS5)` or `4.4` |
| Insurance status | Date written as text | 1 | 1 | 1 | 1 | 1 | Called "Insurance due" on VXE. All 5 filled values are `dd.mm.yyyy` text |
| Status | Choice (list on row 4 only) | 1 | 1 | 1 | 2 | 1 | Values in Step 2 |
| Location | Choice (list on row 4 only) | 1 | 1 | 1 | 2 | 1 | |
| Asset owner | Choice (list on row 4 only) | 1 | 1 | 1 | 2 | 1 | |
| INFO UPDATE | Date, sometimes text | 1 | 1 | 1 | 2 | 1 | 2 of the 6 are `dd.mm.yyyy` text |
| Sign / SIGN | Text (initials) | 1 | 1 | 1 | 2 | 1 | Header case differs between sheets |
| Actions/Defects | Free text | 1 | 1 | 0 | 2 | 0 | |
| NC # | Text | 0 | 0 | 0 | 0 | 0 | |
| MB FW | Text | 0 | 1 | 0 | 0 | 0 | |
| PX4 FW | Text | 0 | 1 | 0 | 0 | | Not on VXE |
| PX4 param / PX4 Config | Text | 0 | 1 | 0 | 0 | | Not on VXE |
| Penguin Base Ver. | Text | 0 | 1 | | | | Mk2.x and MK2 only |
| Estimate for RTF / Planned RTF | Date or text | 0 | 1 | 0 | 1 | 1 | Name differs between sheets |
| PRJ202 | Text | | | 0 | | | 2.5 VTOL only |
| NOTES | Free text | | | | | 1 | VXE only |
| Equip. Rediness All / R&D / FLOPS | Formula | 1 | 1 | 1 | 2 | 1 | Results are `#REF!`; see Step 4 |

### Columns on the other equipment sheets

| Sheet | Column | Type | Filled | Notes |
|---|---|---|---|---|
| EPS (1) | S/N, Configuration, Positioned in, Location, Asset Owner, STATUS, SIGN | Text or choice | 1 each | "Positioned in" names the aircraft the gimbal is fitted to |
| | Date | Date written as text | 1 | |
| | Actions/Defects | Free text | 1 | |
| | NC #, Planned RTF | Text | 0 | |
| | Equip. Rediness (3 columns) | Formula | 1 | All `#REF!` |
| TRC (7) | S/N, Configuration, Frequency, Status, Location, Asset Owner, SIGN | Text, choice; Frequency is a number | 7 each | |
| | Licences | Text | 1 | |
| | NC # | Text | 1 | |
| | DATE | Date, mostly text | 6 | 5 of the 6 are `dd.mm.yyyy` text |
| | Actions/Defects | Free text | 4 | |
| | Columns M and N (no header) | Text and formulas | 6 | A readiness count table beside the data |
| PPC (1) | S/N, Configuration, Location, Asset Owner, Status, SIGN | Text or choice | 1 each | |
| | NEXT MNT (launches) | Number | 1 | Launches until maintenance |
| | Date | Date | 1 | A real date |
| | INFO | Free text | 1 | |
| | Defects, NC #, Planned RTF | | 0 | |
| | Equip. Rediness (3 columns) | Formula | 1 | All `#REF!` |
| GCS (1) | S/N, STATUS, Configuration, PC INSTALLED, Location, Asset Owner | Text or choice | 1 each | STATUS is column B here, not E |
| | INFO:, SIGN, Actions/Defects, NC # | | 0 | |
| ENG (36) | S/N, Configuration, Asset Owner, Status | Text or choice | 36 each | |
| | Positioned in | Text | 34 | An aircraft serial, "On shelf", "UNKNOWN" and similar |
| | Location | Choice | 35 | |
| | SIGN | Text | 34 | |
| | INFO UPDATE | Date, sometimes text | 28 | 22 dates, 5 `dd.mm.yyyy` text, 1 other text |
| | Actions/Defects | Free text | 22 | |
| | Planned RTF | Text | 12 | |
| | NC # | Text | 3 | |
| | Columns L and M (no header) | Text | 18 and 5 | An "X" marker and a copy of the status choices |
| | Equip. Rediness (3 columns) | Formula | 6 | 2 `#REF!` |

### The non-equipment sheets

- **VEHICLES:** 1 row and 11 columns:
  - Car, Number plate;
  - service and inspection dates (mixed real and text dates);
  - insurance and KASKO dates;
  - Vignette, Defects and service fields.
- **ZALENIEKI STOCK:** 82 spare-part lines:
  - name, Required Quantity, P/N, Available QTY;
  - Missing (to order): a formula on 76 rows;
  - Received (date): 3 rows;
  - a separate compatibility table beside it, with the header "Compatibility" used twice.
- **OVERALL:** 41 rows:
  - Model typed in on 26 rows; the other 15 are formulas;
  - S/N, Status, Owner, Location, Notes, INFO UPDATED and SIGN are formulas linking to the equipment sheets, and 33 of 40 return `#REF!`;
  - "In Alaris" is marked `x` on 20 rows;
  - a status count table sits beside the data.

## Step 2: Match against the 12 US columns

| US column | Riga column | Match | Notes |
|---|---|---|---|
| Serial Number | S/N | Renamed | On all 10 equipment sheets. Stored as a number on VXE |
| Asset Type | (none) | Missing | Implied by the sheet name, with Configuration as detail. See Step 3 |
| Ownership | Asset owner / Asset Owner / Owner | Renamed | Values do not match; see below |
| Status | (none) | Missing | Nothing in Riga records IN, OUT, RMA or BAILMENT |
| Location | Location | Exact name | Values do not match; see below |
| Material Condition | Status / STATUS | Renamed | Riga's Status is a readiness value; mapping below |
| Part Number | (none) | Missing | Only the stock sheet has P/N, for spare parts |
| Date Out | (none) | Missing | |
| Check Out By/To | (none) | Missing | SIGN is who last updated the row, not who has the item |
| Asset Notes | Actions/Defects | Renamed (loose) | Also NOTES on VXE and INFO on PPC |
| Shelf Location | Positioned in | Renamed (loose) | EPS and ENG only. Mostly the aircraft an engine or gimbal is fitted to, sometimes "On shelf" |
| Last Inventory | INFO UPDATE / Date / DATE | Renamed (loose) | The date the row was last updated and signed. Not the same as a physical inventory count |

**Riga columns with no US equivalent:**
- **Common to several sheets:** Configuration, Frequency, Insurance status or due, SIGN, NC #, Planned RTF or Estimate for RTF, and the Equip. Rediness formulas.
- **Firmware fields:** MB FW, PX4 FW, PX4 param or Config, Penguin Base Ver.
- **One sheet each:** PRJ202, PC INSTALLED, Licences, NEXT MNT (launches), and OVERALL's "In Alaris".

### Choice columns

**Asset Type: none in Riga.** One type per sheet. Configuration values:

| Sheet | Configuration values | Closest US Asset Type | Match |
|---|---|---|---|
| Mk2.x | Mk2.x Piccolo | none | Unmatched |
| MK2 | Ice Pilot, 24v | none | Unmatched |
| 2.5 VTOL | Piccolo + SPAN | none | Unmatched |
| MK3 | Piccolo | none | Unmatched |
| VXE | VXE 30 - Battery cell | VXE-30 (or VXE-30B) | Loose |
| EPS | E180 | E 180 | Loose (spacing) |
| TRC | 4x4, 2x2, MOXA 4x4, and one 4x4 with a network address | none | Unmatched |
| PPC | 4m | none | Unmatched |
| GCS | std | none (SGCS 1/2/3 are US station models) | Unmatched |
| ENG | MK2.5/Mk2X BXR (15), MK2 (11), EFI 1 cylinder (7), MK3 BXR (3) | none | Unmatched |

**Status in Riga, which maps to US Material Condition.**

- **The choice list:** RTF, GROUNDED, FCF REQUIRED, RTF WITH REMARKS, WRITTEN OFF. It is the same on every sheet.
- **One more value:** the EPS sheet's coloring also tests for "NFC ISSUES", which is not in the list.

| Riga value | Assets | Proposed US Material Condition | Confidence |
|---|---|---|---|
| RTF | 30 | FMC | High |
| RTF WITH REMARKS | 3 | PMC | High |
| GROUNDED | 17 | NMC | High |
| FCF REQUIRED | 1 | NMC (cannot fly until a functional check flight) | **Flagged:** could be PMC; see question 2 |
| WRITTEN OFF | 1 | Destroyed/Lost | High |
| NFC ISSUES | 0 | none | **Flagged:** not in the list |

US Status (IN, OUT, RMA, BAILMENT) has no Riga source. Every Riga asset would have a blank US Status.

**Location.**

- **The choice list:** MRO, Field, QC, RnD, Nakotne, In Transit, DEMO.
- **One stray list:** TRC has a second list that adds "Engineering". It is attached to its Licences column, which looks like a stray copy.

| Riga value | Assets | US match |
|---|---|---|
| MRO | 28 | None, unmatched |
| Field | 11 | None, unmatched |
| Nakotne | 8 | None, unmatched |
| RnD | 3 | None, unmatched. "HSV ENG" and "SLO ENG" are other sites |
| DEMO | 1 | None, unmatched |
| (blank) | 1 | |
| QC, In Transit | 0 | In the list but unused |

**Asset owner, which maps to US Ownership.** The choice list: FOPS, R&D, OTHER.

| Riga value | Assets | US match |
|---|---|---|
| FOPS | 43 | Loose only: "HSV Flight Ops" and "SLO Flight Ops" are other sites. Unmatched |
| R&D | 9 | Loose: "Engineering". Flagged |
| OTHER | 0 | In the list but unused |

## Step 3: Asset Types not in `asset_families.json`

Riga has no Asset Type column, so a type has to come from the sheet. None of the 10 sheet types is in `asset_families.json`. The proposed families below are for Scott to decide.

| Riga type (sheet) | Assets | Nearest entry in the file | Proposed family |
|---|---|---|---|
| Penguin C Mk2.x | 1 | none | Aircraft |
| Penguin C Mk2 | 1 | none | Aircraft |
| Penguin C Mk2.5 VTOL | 1 | none | Aircraft |
| Penguin C Mk3 VTOL | 2 | none | Aircraft |
| VXE | 1 | VXE-30, loose | Aircraft |
| Epsilon gimbal (E180) | 1 | E 180, loose | Payload |
| Ground control station | 1 | none | Ground Control Station |
| Tracking antenna | 7 | none | Ground Control Station or Support |
| Catapult launcher | 1 | none | Support |
| Engine | 36 | none | Support |

**Engines dominate the count.** They are 36 of the 52 assets, and 16 of them are grounded. Counting engines in the fleet would change any readiness figure a lot. See question 5.

## Step 4: Row-level problems for the current loader

`assets.load()` reads one CSV file. It expects the column headers on line 1 (after an optional `ListSchema=` line), the US header names, ISO dates and one row per asset. Against this workbook:

1. **It is an Excel file with 13 sheets.** The loader cannot open it. Saving it as CSV from Excel writes only the open sheet, so the US-style path would need 10 separate exports, by hand, every time.
2. **Title and legend rows above the headers.**
   - Row 1 is a merged title and row 2 a merged color legend; the headers are on row 3 (row 2 on PPC).
   - Every equipment sheet has 2 to 4 merged ranges in rows 1 and 2.
   - A loader reading line 1 as headers would take the title as the only column.
3. **Headers differ between sheets.**
   - Case differs: Status and STATUS, Sign and SIGN, Asset owner and Asset Owner.
   - Wording differs: Insurance status and Insurance due, Estimate for RTF and Planned RTF.
   - Order differs: Status is column E on most sheets, column D on TRC and column B on GCS.
   - A per-sheet map is needed in any case.
4. **Side tables beside and below the data.** These would be read as extra columns or as assets with no serial number:
   - 2.5 VTOL has an upgrade matrix in columns W to AF, and a part list in rows 21 to 25. That gives 13 non-blank rows with no S/N.
   - TRC has a status count table in M and N.
   - ENG has unlabeled marker columns L and M.
   - STOCK has a compatibility table to the right.
   - OVERALL has a count table in L to N.
5. **Formulas with errors.**
   - 8 equipment sheets have "Equip. Rediness" formula columns. All 8 have at least one `#REF!` result.
   - In OVERALL, 33 of 40 linked rows return `#REF!`. This is consistent with rows having been deleted from the equipment sheets after the links were made.
   - In TRC, the count for "RTF WITH REMARKS" searches for `"GRTF WITH REMARKS"` (a typo), so Riga's own readiness figure on that sheet undercounts.
6. **Dates stored as text, day first.**
   - Many dates are `dd.mm.yyyy` text rather than Excel dates: all 6 insurance dates, 8 of 36 "last update" dates (INFO UPDATE, plus Date on EPS and PPC), 5 of 6 TRC dates, and the vehicle KASKO date.
   - Real dates and text dates are mixed in one column, for example ENG INFO UPDATE with 22 dates and 5 text values.
   - Today's `_to_local_date()` returns blank for anything that is not ISO, so these would disappear without a message, which breaks rule 5.
   - Read as US month/day, `06.03.2026` would also mean June 3, not March 6.
7. **Dates inside free text.** Actions/Defects and INFO often start with a date, for example "dd.mm.yyyy: ...". That is fine as notes, but it cannot be used as a date.
8. **Numbers where text is expected.**
   - The VXE serial number is stored as a number. A serial with a leading zero would lose it.
   - Frequency is a number on MK3 and TRC but text elsewhere.
9. **Choice lists cover only row 4.** On most equipment sheets the Status, Location and owner lists apply to row 4 alone; only ENG and TRC cover all rows. Values typed in other rows are not checked by Excel, so spelling can drift.
10. **Cell colors are not reliable data.**
    - Column A fills do not agree with Status. For example, RTF rows are filled red on Mk2.x and VXE and yellow on TRC.
    - The legend reuses colors for insurance expiry too.
    - Only the Status text should be read, never colors.
11. **A non-English note.** One cell on ENG is in Latvian. That is harmless for loading, but notes should be expected in either language.

The OVERALL sheet should not be read at all. It only links to the other sheets and is mostly broken.

## Step 5: Recommendation: a separate Excel loader

**Recommendation:** write a separate Excel loader, `riga.py` for example, that reads the equipment sheets directly with `openpyxl` (already installed for the Excel export). It should return rows in exactly the shape `_clean_row()` produces, so every page, the families and the readiness math work unchanged. Do not try to reuse the CSV loader with a column map.

**Why not the CSV loader with a column map:**
- **Too many exports.** It would need 10 separate CSV exports from Excel, each saved by hand, every time.
- **Different structure on each sheet.** Each sheet has its own header row, header names, column order and side tables. A single column map cannot describe that; it would be a per-sheet map anyway.
- **Errors and dates.** Formula errors and day-first text dates would reach the loader as plain text, and the CSV path would blank them silently.

**What the Excel loader would hold** (described, not built):

- **A small committed map,** like `asset_families.json`. For each sheet it gives:
  - the Asset Type it stands for;
  - how to find the header row: the row whose first cell is "S/N";
  - which Riga column fills which US field.

  It also holds the value maps: Riga Status to Material Condition, and Riga Location and owner to whatever values Scott chooses.
- **Rows:** only rows with a serial number. Only columns named in the map, so side tables are skipped.
- **Dates:**
  - real Excel dates are read as dates;
  - text dates are read strictly as day first (`dd.mm.yyyy`);
  - anything else is reported, never silently blanked.
- **Never fail silently:** any value not in a map, any `#REF!` in a mapped column, and any sheet missing from the workbook goes to the log and to the Needs Attention page.
- **A Site field** (US or Riga) on every row, so the overview can filter or split by site. This is a product decision; see question 4.
- **Where the workbook comes from.** If it lives in SharePoint or OneDrive, the app's existing Microsoft sign-in could download it read-only with the same certificate. If it arrives by email, a file path setting like `ASSET_CSV` would do. See question 6.

## Questions for Scott

1. **Is this the full workbook?**
   - OVERALL links to 40 assets, but 33 of the links are broken.
   - The aircraft sheets hold 7 aircraft, against 41 rows on OVERALL.
   - It looks like rows were removed before the file was shared. If so, the counts here are for the sample only, and a full copy should be checked before any loader is built.
2. **FCF REQUIRED:** NMC (as proposed) or PMC?
3. **No checkout data in Riga.** Nothing records IN or OUT, who has an item, or when it went out. Should Riga assets show a blank Status and holder? Or does Riga track this somewhere else?
4. **Riga Location and Ownership values.**
   - Should they be kept as Riga's own values, for example "Riga: MRO"?
   - Or should there be a separate Site field, with the US pages filtering by site?
   - Or should Riga be mapped onto the US choices?
5. **Which Riga sheets count as fleet assets?**
   - Engines (36, of which 16 are grounded) would outweigh everything else.
   - Should engines, tracking antennas and the catapult be included?
   - VEHICLES and ZALENIEKI STOCK are proposed as left out.
6. **Where does the Riga workbook live, and how often is it updated?** That decides between a SharePoint read and a file path.
7. **For Riga, not for us.**
   - TRC's readiness count has a typo (`GRTF WITH REMARKS`).
   - Most "Equip. Rediness" formulas return `#REF!`.
   - Worth passing on to the Riga team?
