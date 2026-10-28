# Report 05: Draft asset family mapping

## Where the work started

- **Branch:** `agent/wednesday`. Nothing was pushed to `main`.
- **Starting commit:** `f1999d4` ("Find renamed columns by their internal name"), after `git pull`.
- **No application code changed.** This report is the only new file.
- **Report location:** the prompt asked for `docs/reports/05-asset-family-mapping.md`, so it is here. The earlier reports are in `reports/` with names like `reports/04_sharepoint_decisions.md`. Say if you want it moved there to match.

## Sources used

- **SharePoint list:** the committed `Asset Tracking V2.csv`: 146 rows, plus the column definitions in its first line (`ListSchema=`). Live SharePoint was not read. Edits made since that export are not counted here.
- **Training Tracker:** found on this machine at `/Users/scottlovett/Dev/RedWire/training`, a separate repository at commit `03692fa` (September 8, 2026). Two parts of it were used:
  - `scripts/seed.ts`, the committed list of 21 equipment items. Each item is marked `airframe` or `payload`.
  - `data/training.db`, a local database that git ignores. Its table `airframe_uas_mapping` links 19 AlarisPro aircraft serial numbers to the Training Tracker airframes. It is used below only for match counts. No serial numbers are copied into this report.

## Step 1: Asset Type values and row counts

The list has 30 Asset Type choices. They are 29 different values, because "VXE-30" appears twice (see Step 3). 26 of them are in use. All 146 rows hold one of the defined choices, and no row has a value outside the list.

| Asset Type | Rows |
|---|---|
| E 140Z G2 | 20 |
| SGCS 1 | 13 |
| Main Battery Charging Kit | 9 |
| SGCS 2 | 9 |
| HLB Charging Kit | 8 |
| Field Support Kit | 8 |
| VXE-30 | 7 |
| E 95 | 7 |
| B40 Battery | 7 |
| Fuel Cell | 6 |
| Starlink | 5 |
| VXE-30B | 5 |
| E 140 MWIR | 5 |
| Gimbal Support Kit | 4 |
| Other | 4 |
| Block 40 | 4 |
| E 180 | 3 |
| SGCS 3 | 3 |
| Fuel Cell Support Kit | 3 |
| Mod A Kit | 3 |
| Wing Utility Pylon | 3 |
| Student Laptop Kit | 3 |
| E 140Z G2 Dual GPS | 2 |
| B40 Main Charging Kit | 2 |
| B40 HLB Charging Kit | 2 |
| SIL Laptop | 1 |
| **Total** | **146** |

**Choices defined in the list with no rows:**

| Asset Type | Rows |
|---|---|
| VXE 35 x | 0 |
| Ping 200x Transponder Kit | 0 |
| HIL Simulator | 0 |

## Step 2: Comparison with the Training Tracker

### What the Training Tracker lists

- **Airframes (4):** VXE30 - Standard, VXE30 - Adv Nav, Block 35X, Block 40.
- **Payloads (17):** OGCS, Spectrum Dominance, ATAK, NEOS, E140Z G2, E140 MWIR, E95, E180, Trillium HD40, Trillium HD55, Mod A-Kit, Wing Utility Pylon, Heavy Payload Main Battery, Orbital Droppers, JAI, Epsilon 135, IMSAR.
- **AlarisPro name variants** in its `payload_alaris_mapping` table: "Epsilon 140G2" means E140Z G2, "HD40-XV" means Trillium HD40, and "Wing Utility Dropper" means Wing Utility Pylon.

**One caution.** The Training Tracker's "payload" group means "anything a pilot qualifies on that is not an airframe". It includes OGCS (ground control software), ATAK (a tablet app) and Heavy Payload Main Battery. So its group cannot be copied straight into the four families. I used its group only where it agrees with what the item physically is.

### Matches

| SharePoint Asset Type | Training Tracker item | Match | Difference |
|---|---|---|---|
| Block 40 | Block 40 | Exact | |
| Wing Utility Pylon | Wing Utility Pylon | Exact | |
| VXE-30 | VXE30 - Standard, VXE30 - Adv Nav | Loose | Hyphen, and the tracker splits the airframe into two variants |
| VXE-30B | VXE30 - Standard / Adv Nav | Loose | Suffix "B". See the serial check below. |
| VXE 35 x | Block 35X | Loose | "VXE" instead of "Block", spacing, case |
| E 140Z G2 | E140Z G2 | Loose | Space |
| E 140Z G2 Dual GPS | E140Z G2 | Loose | Suffix "Dual GPS" |
| E 140 MWIR | E140 MWIR | Loose | Space |
| E 95 | E95 | Loose | Space |
| E 180 | E180 | Loose | Space |
| Mod A Kit | Mod A-Kit | Loose | Hyphen |

**No match (18):** SGCS 1, SGCS 2, SGCS 3, SIL Laptop, HIL Simulator, Student Laptop Kit, Main Battery Charging Kit, HLB Charging Kit, B40 Main Charging Kit, B40 HLB Charging Kit, B40 Battery, Field Support Kit, Fuel Cell Support Kit, Gimbal Support Kit, Fuel Cell, Starlink, Ping 200x Transponder Kit, Other.

B40 Battery is close in meaning to "Heavy Payload Main Battery" but not in name, so it is counted as no match.

### Serial number check on the aircraft types

I compared the SharePoint serial numbers with the 19 aircraft serial numbers in the Training Tracker's AlarisPro mapping:

| SharePoint Asset Type | Rows | Serial found in Training Tracker | Training Tracker airframe for those serials |
|---|---|---|---|
| VXE-30 | 7 | 7 | All 7: VXE30 - Standard |
| VXE-30B | 5 | 4 | 2 VXE30 - Adv Nav, 1 Block 35X, 1 Block 40 |
| Block 40 | 4 | 1 | Block 40 |

What this means:

- **VXE-30:** all 7 rows are aircraft the Training Tracker knows.
- **VXE-30B:** these are aircraft, but the label does not mean one model. The Training Tracker files the same airframes under three different variants.
- **Block 40:** only 1 of the 4 rows matches a known aircraft. The notes on 2 of the other rows describe a stand, not an aircraft. Some Block 40 rows may be ground equipment logged under the aircraft's type.

## Step 3: Draft mapping

| Asset Type | Rows | Proposed family | Confidence | Reason |
|---|---|---|---|---|
| VXE-30 | 7 | Aircraft | High | Training Tracker airframe; all 7 serials are known VXE30 - Standard aircraft. |
| VXE-30B | 5 | Aircraft | High | 4 of 5 serials are Training Tracker airframes, though under mixed variants. |
| Block 40 | 4 | Aircraft | Medium | Exact Training Tracker airframe, but only 1 serial matches and 2 rows look like stands. |
| VXE 35 x | 0 | Aircraft | Medium | Loose match to the Block 35X airframe; no rows to confirm it. |
| SGCS 1 | 13 | Ground Control Station | High | Ground control station hardware; notes record OGCS software versions. |
| SGCS 2 | 9 | Ground Control Station | High | Same family as SGCS 1. |
| SGCS 3 | 3 | Ground Control Station | High | Same family as SGCS 1. |
| E 140Z G2 | 20 | Payload | High | Training Tracker payload E140Z G2 (camera gimbal). |
| E 140Z G2 Dual GPS | 2 | Payload | High | A version of E140Z G2. |
| E 140 MWIR | 5 | Payload | High | Training Tracker payload E140 MWIR. |
| E 95 | 7 | Payload | High | Training Tracker payload E95. |
| E 180 | 3 | Payload | High | Training Tracker payload E180. |
| Mod A Kit | 3 | Payload | Medium | Training Tracker lists it as a payload, but it may be a fitting kit rather than a sensor. |
| Wing Utility Pylon | 3 | Payload | Medium | Training Tracker payload; it carries droppers and is a mount, not a sensor. |
| Main Battery Charging Kit | 9 | Support | High | Charging equipment. |
| HLB Charging Kit | 8 | Support | High | Charging equipment. |
| B40 Main Charging Kit | 2 | Support | High | Charging equipment. |
| B40 HLB Charging Kit | 2 | Support | High | Charging equipment. |
| Field Support Kit | 8 | Support | High | A support kit by name. |
| Fuel Cell Support Kit | 3 | Support | High | A support kit by name. |
| Gimbal Support Kit | 4 | Support | High | Spares and tools for the gimbals, not a gimbal. |
| B40 Battery | 7 | Support | Medium | Flight batteries are consumable support items; the Training Tracker's nearest item is in its "payload" group. |
| Student Laptop Kit | 3 | Support | Medium | Training laptops; could count as Ground Control Station if students fly with them. |
| SIL Laptop | 1 | Support | Medium | A standalone software simulation laptop running OGCS, not a station that flies aircraft. |
| HIL Simulator | 0 | Support | Medium | Simulator test equipment. |
| Starlink | 5 | Support | Medium | Satellite link for the field site; could count as Ground Control Station. |
| Fuel Cell | 6 | Support | Low | The aircraft's power unit (part D450XR). It is neither an airframe nor a payload. |
| Ping 200x Transponder Kit | 0 | Support | Low | Transponder kit fitted to aircraft; no rows to check. |
| Other | 4 | Support | Low | No type information; part numbers and notes do not identify the items. |

**Rows per family:**

| Family | Asset Types | Rows |
|---|---|---|
| Aircraft | 4 | 16 |
| Ground Control Station | 3 | 25 |
| Payload | 7 | 43 |
| Support | 15 | 62 |
| **Total** | **29** | **146** |

### The duplicate "VXE-30" choice

The Asset Type column defines "VXE-30" twice, as the 1st and 29th choice. The two entries are identical, character for character, with no extra spaces. In practice:

- **Rows:** a row cannot tell the two entries apart. All 7 VXE-30 rows simply hold the text "VXE-30".
- **Mapping:** the mapping is keyed by the text, so "VXE-30" maps once, to Aircraft, and both entries are covered.
- **Today's dashboard:** it already removes the repeat. `pill_colors.json` holds 29 Asset Type choices, not 30, so there is no duplicate filter option.
- **What I recommend:** ask whoever owns the list to delete the second entry in SharePoint's column settings. The dashboard only reads SharePoint, so it cannot fix this itself, and it does not need to.

## Step 4: Types that could not be placed with confidence

These stay in Support, marked Low:

- **Other (4 rows).** Nothing in the row says what the item is. The best fix is to give these 4 items a real Asset Type in SharePoint.
- **Fuel Cell (6 rows).** It is the aircraft's power unit, part of the aircraft but not an airframe. If the overview should show everything that flies, it could go under Aircraft instead.
- **Ping 200x Transponder Kit (0 rows).** It is fitted to aircraft, so it could be Support or Payload. Nothing depends on this choice until a row uses it.

## Questions for Scott

1. **Block 40:** 3 of the 4 Block 40 rows do not match a known aircraft serial, and 2 have notes describing a stand. Should the overview count all 4 as aircraft? If not, the list needs a different Asset Type for stands, or a page rule could leave out rows whose notes say "stand". The first is cleaner.
2. **VXE-30B:** the Training Tracker files these airframes as Adv Nav, Block 35X and Block 40. Is "VXE-30B" the right label for all 5 in SharePoint, or do some need retyping?
3. **Middle cases:** do you agree with these placements?
   - Starlink and Student Laptop Kit: Support or Ground Control Station?
   - Mod A Kit and Wing Utility Pylon: Payload or Support?
   - Fuel Cell: Support or Aircraft?
4. **Where the mapping lives:** when the page is built, should the mapping be a small committed file you can edit, like `pill_colors.json`? Then a new Asset Type added in SharePoint would show as "Unmapped" until you place it, instead of silently going to Support.
5. **Report location:** keep this in `docs/reports/`, or move it to `reports/05_asset_family_mapping.md` with the others?
