# Public supply-data collection: 4 November 2026

**The public downloads are local; the requested village supply model is not ready to train.** This collection has added zero verified daily village supply records and zero reviewed 0–5 urgency outcomes. The empty operations template has not been filled with environmental data, tanker counts or generated outcomes.

**Subsequent user-authorised prototype option:** a separate [simulation dataset](SIMULATED_SUPPLY_TRAINING.md) is now prepared and passes its training checks. It supplies hypothetical balances/labels, without changing the measured-data findings in this audit.

## Newly collected files

| Official source | Local collection | What it establishes | Limits |
|---|---|---|---|
| [JJM village profiles](https://ejalshakti.gov.in/jjmreport/JJMVillage_Profile.aspx) | 40,297 unique JJM village household/tap profiles; 34 rural dashboard districts | Published household and tap-connection counts | Observation vintage is not supplied. A connection does not establish water delivered. This is not all 44,929 directory villages. |
| [PMC tanker-register API](https://webadmin.pmc.gov.in/en/jsonapi/node/water_tanker?include=field_file_upload&page%5Blimit%5D=50) | 650 index entries, 648 downloadable spreadsheets; all downloaded | Public urban tanker registers | Pune city coverage. Six files duplicate another file’s content. No rural village or litre conversion is inferred. |
| [Maharashtra WSSD tanker reports](https://water.maharashtra.gov.in/en/document-category/tanker-report/) | 84 PDFs across seven listing pages, all downloaded; listing report dates 24 February 2025–2 November 2026 | State district summaries of tanker coverage | Weekly report counts do not establish village identity, delivered litres, daily storage or assessed need dates. |
| [PoCRA GIS](https://gis.mahapocra.gov.in/) | 504 district weather rows, 36 districts, 20 October–2 November 2026 | Dated rainfall, temperature, humidity and wind fields as published | The 3 November request returned 14 dates through 2 November. District aggregates are not village readings. Wind units, aggregation method and historical publication times remain unverified. |
| PoCRA public attributes | 44,839 village attribute records, plus 95 dry-spell class/count rows | Publisher identifiers and district dry-spell context | Village/geometry vintage is unverified; geometry was excluded. Dry-spell responses lack an observation-period field, so their request date is not treated as their valid date. |

Raw files, receipts and normalized records are under `data/raw/supply/public-completion/`. Hashes, retrieval times, original URLs and request parameters are retained. Raw files are ignored by Git. No contact details were exported into derived data or Maps.

The previously downloaded 98 NWIC historical archives and 147,069 station/parameter daily flow-context rows remain available. These are environmental inputs requiring quality checks, not water-supply outcome labels. See [remaining data and approximations](REMAINING_DATA_AND_APPROXIMATIONS.md).

## File-level checks

The spreadsheet extraction reads explicit scheduled-trip and required-trip columns, preserves blanks and zeros, excludes subtotal rows, detects repeated serial numbers and does not assume a tanker capacity. These columns have not been certified as completed dispatches.

- 642 distinct spreadsheet contents yielded 662 supported worksheets, with no file-read errors.
- Only 251 worksheets have a single valid dated heading without a conflicting four-digit title date. Those headings range from 17 April to 25 October 2026. Two-digit sheet-name years and upload dates do not establish the service date.
- One worksheet has a conflicting title date; 11 worksheets have repeated serial numbers. All remain flagged.
- All 84 PDFs were profiled; only eight have more than 100 extractable text characters. Most require visual reading/OCR and table reconciliation before numeric use.
- The latest [Tanker Report 02.11.2026](https://cdnbbsr.s3waas.gov.in/s3347665597cbfaef834886adbb848011f/uploads/2026/11/20261103938485333.pdf), page 1, was rendered and visually checked. It compares district counts for 19–25 October and 26 October–1 November, alongside a prior-year comparison. It does not list village names or delivered volumes. Its source hash is `a571aab2a80e7a0a8af5fed8f09f273e63f25a2fb9f3698e0b46949d1cbb8cdb`.

Machine-readable summaries: `data/water/public-supply-completion.json` and `data/water/public-supply-file-audit.json`. Maps → Live & training data displays the collection counts and the remaining supply-training gap.

## What still prevents real training

| Required input/outcome | Result of checks | Can a formula replace it? |
|---|---|---|
| Actual daily water entering each village/service area | No verified statewide public feed/export obtained. The checked Maharashtra JJM IoT pilot returned no daily volume series. | Calibrated flow × actual running time can estimate it, but both dated operands must exist. Dam storage and river discharge cannot provide those operands. |
| Opening/closing usable tank storage | No daily statewide export obtained | Tank geometry × calibrated level can estimate storage; dimensions and actual dated levels are still needed. |
| Pump hours, outages, allocation and tanker litres | No verified statewide rural daily series obtained; PMC trip columns are urban and have unverified completion/volume | No default pump hours, tanker size, loss rate or shared-source allocation is applied. |
| Current whole-village demand | Public tap counts lack household size, dated population and sector demand | Population × explicit LPCD and agricultural/livestock formulas are supported only with their required inputs and declared assumptions. Supply restrictions must not define independent demand. |
| Verified 7/15-day shortage outcomes and assessed first-week tanker need | No eligible village targets collected | Dispatch alone does not prove necessity or severity. The project’s new 0–5 rubric is not an existing government target column. It needs consistent review/annotation from actual outcomes. |
| Source → scheme → pipe/DMA → service-village relationships | Partial public references, no complete verified statewide operational crosswalk | Nearby sources, matching names and straight-line pipes do not establish a connection. |

The public Janori profiles also conflict: an older IoT inventory reports population 5,700, whereas a newly retrieved village profile reports 880 and 148 households. Neither supplies a dated population measurement. The values were retained for review and not silently combined into current demand.

The documented [JJM API guide v1.02](https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf) requires registration and approval. Approval does not by itself guarantee daily operational telemetry exists or is included. The user has not applied; no account application or messages have been sent. The exact export fields and authority routes are prepared in [the access-request packet](SUPPLY_DATA_ACCESS_REQUEST.md).

An additional relevant route was verified through the [official MJP website](https://mjp.maharashtra.gov.in/): its “IoT for JJM Schemes” link opens [MahaJal IoT](https://dashboard1.mahajaliot.in/). The published client marks dashboard, scheme LPCD, water-consumption and report pages as protected routes and offers login screens. No authorised session was available, and no protected operational records were downloaded. This is a concrete access route to ask MJP about; its exact coverage, time history, completeness and export permissions remain unverified. The separate MJP citizen water-works portal exposes a region selector, not a verified daily village telemetry export.

## Assumptions applied in this collection

No new numerical supply, loss, storage, population or urgency assumptions were added. Administrative counts remain administrative snapshots; weather remains district context. IDs called Census codes by publishers are retained as identifiers only, without importing 2011 population or treating them as verified LGD crosswalks. PoCRA’s `wtp_layer` sample contained codes such as CNB/WB and was not classified as water-treatment-plant locations. Advertised budget-layer sample requests did not produce verified usable observations; soil-moisture/irrigation estimates are not domestic supply measurements.

## Refresh and offline use

Collect or resume public files while online, one collector at a time:

```powershell
.venv/Scripts/python.exe -m scripts.collect_remaining_public_supply
```

Successful downloads are reused only when request identity and SHA-256 match. Add `--refresh` to fetch a new snapshot; this replaces the current cache, so copy the raw folder first if older snapshots must be preserved. The downloader does not install a scheduled task. Partial/failing sources remain explicit in the report.

The read-only file audit uses `scripts.extract_public_supply` with Python providing `openpyxl` and `pypdf` (the bundled Codex Python was used for this check). It performs no network or database calls. It exports aggregate diagnostics, not recipient names, addresses, phones or vehicle numbers.

`train_offline.cmd` remains an offline trainer. It will still stop with a missing-data report on the current actual records. Public context files are kept outside its operations folder, so downloading more context cannot silently train a model on invented supply labels. No model was fitted, app forecasts published or application database updated by this collection.

## Validation of this update

44 focused Python checks passed across collection/cache integrity, privacy, map summaries, feature engineering, urgency labels and the offline trainer. TypeScript checking, both web builds and the targeted browser check for map selection/data coverage passed. The local API was refreshed to load the collection summary. These checks validate the implementation; they do not validate a trained model or make the missing operational records available.
