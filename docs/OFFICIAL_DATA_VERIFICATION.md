# Official water-data verification

Checked: 3 November 2026 (Asia/Kolkata). These are access and file-content checks, not hydrological validation or statewide coverage certification. No data was imported into the application database.

## Confirmed downloads and record APIs

The four resources below returned HTTP 200 for both full CSV downloads and unauthenticated CKAN `datastore_search` requests. API totals matched downloaded row counts. Dates below are observation dates parsed from the CSV, not website update dates. All acquisition timestamps parsed successfully. Raw downloads, hashes, API snapshots and scripts are under the ignored `work/official-source-verification/` directory; a portable summary is in `OFFICIAL_DATA_VERIFICATION.json`.

| Resource | Rows | Distinct station names | Coverage in downloaded resource | Latest observation |
|---|---:|---:|---|---|
| Maharashtra SW river discharge, 2026-2030 resource | 1,366 | 12 | Gadchiroli, Wardha, Yavatmal | 30 September 2026, 17:30 |
| Maharashtra SW canal discharge, 2026-2030 resource | 17,729 | 7 | Jalgaon, Solapur | 2 November 2026, 23:00 |
| Bhima-Sina Link Canal discharge, 2026-2030 resource | 2,565 | 1 | Solapur | 2 November 2026, 22:00 |
| Totladoh reservoir water level, 2023-2026 resource | 25,928 | 1 | Nagpur | 14 October 2026, 13:00 |

Sources:

- [River discharge](https://nwdp.nwic.gov.in/dataset/river-discharge-manual-dailly-maharashtra-surface-water-department)
- [Canal discharge](https://nwdp.nwic.gov.in/dataset/canal-discharge-dataset-telemetry-hourly-maharashtra-surface-water-department)
- [Bhima-Sina discharge](https://nwdp.nwic.gov.in/dataset/reservoir_discharge_bhima-sina_link_canal_maharashtra_telemetry_hourly)
- [Totladoh level](https://nwdp.nwic.gov.in/dataset/reservoir-water-level-totladoh-reservoir-maharashtra-telemetry-hourly-2023-2026)

Important limitations:

- None of these four checked resources contains Satara station records. This does not establish that Satara records are absent from other agencies, resources or portals.
- River, canal and Bhima-Sina files have a `Village` field, but every downloaded value is `-`. Totladoh has no village field. They do not establish a source-to-beneficiary-village connection.
- The canal file includes Bhima-Sina Link Canal, Hatnur assets and Ujjani assets. Its broad title must not be interpreted as an inventory of all Maharashtra canals.
- Bhima-Sina appears in both the general canal file and its specific discharge file. These are overlapping asset records, not independent water supplies to add together.
- Actual river values are labelled `m3/sec`. Actual canal/Bhima-Sina gate values are labelled `cusec`, despite broader catalogue descriptions referring to cubic metres per second. Preserve original units and review conversion before use.
- Totladoh values are `Water Level (M)`, not usable storage or deliverable supply. No volume conversion was performed.
- A catalogue/resource update dated 3 November does not imply observations through 3 November. Resources labelled `2026-2030` contain observations, not future forecasts.
- Counts are distinct station names in these files; stable identities and instrument changes have not been independently reviewed. Continuity, sensor accuracy and all quality flags remain unvalidated.

## Supporting sources

### Tankers

[Maharashtra WSSD listing](https://water.maharashtra.gov.in/en/document-category/tanker-report/) and its [latest downloaded PDF](https://cdnbbsr.s3waas.gov.in/s3347665597cbfaef834886adbb848011f/uploads/2026/11/20261103938485333.pdf) returned HTTP 200. The PDF was rendered and visually inspected. Its report date is 2 November 2026 and its latest reporting period is 26 October through 1 November 2026. It is a scanned one-page district summary of villages, wadis and tanker counts. It provides neither named village delivery records nor delivered litres/trips. It is a district scarcity indicator, not village daily supply evidence. The previous statement naming 26 October as the latest available report is superseded by this direct check.

### Population and households

The [Satara Census catalogue](https://censusindia.gov.in/nada/index.php/catalog/6718) and its [XLSX download](https://censusindia.gov.in/nada/index.php/catalog/6718/download/9795/DDW_PCA2731_2011_MDDS%20with%20UI.xlsx) returned HTTP 200. The workbook is a valid XLSX ZIP containing a workbook and one worksheet. The catalogue identifies village/town/ward population and household data for 2011. This check did not validate all workbook cells, update population estimates, or reconcile Census codes with current LGD village codes.

### JJM water sources and schemes

[JJM Citizen Corner](https://ejalshakti.gov.in/JJM/citizen_corner/villageinformation.aspx) returned HTTP 200. The page contains village selectors and source/scheme tables. Its client code includes read operations named `BindSourceInfo`, `BindSchemeInfo` and scheme-wise source details, with source-location/type and scheme-functionality fields. A populated Maharashtra village response and stable bulk-export/API contract were NOT verified. Page availability and table definitions are not proof of complete downloadable village data. The page's Maharashtra state selector value is 18, unlike LGD state code 27; IDs must not be joined without a verified crosswalk.

### Livestock

The [official Maharashtra 20th Livestock Census listing](https://dahd.maharashtra.gov.in/en/publication/20-th-livestock-census/) returned HTTP 200 on retry, and its [2019 report PDF](https://cdnbbsr.s3waas.gov.in/s369dafe8b58066478aea48f3d0f384820/uploads/2024/02/202402131737819886.pdf) downloaded successfully. Public access to the report is confirmed. This does not establish current village-level livestock counts or daily water demand.

## Unverified sources and missing operational data

- The [government pipeline GIS case study](https://nceg.gov.in/assets/pdf/WSS.pdf) could not be downloaded from either the bare or www host in this environment. No downloadable GIS layer, pipeline geometry or operating network was verified. A case study alone would not be a dataset.
- The CWC NWIC catalogue entry titled `Reservoir Water Storage Level (Manual - Daily)` was checked directly. Its listed resources were Odisha storage and Madhya Pradesh levels; no Maharashtra resource appeared in that particular package. This does not invalidate other Maharashtra WRD or CWC storage products.
- Official catalogue text searches for Dhom, Veer and Nira returned no results. This is a search result, not proof those assets lack data elsewhere or inside broadly named files.
- Live village/DMA flow, pressure, leakage, tank inventories, pump operations, outages, supply allocations, measured well yield, village tanker litres and current crop-wise irrigated area were not verified in this audit.

## Implication for JalSathi

Official machine-readable surface-water data is genuinely accessible. These checked resources are not sufficient for a Phaltan/Satara village water balance. The next requirement is a reviewed village-to-scheme-to-source mapping and actual dated supply/storage/demand evidence for those villages. Do not fill missing links or operational readings with inferred measurements. No model was trained or approved during this audit.
