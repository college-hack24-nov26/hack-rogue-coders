# Village water evidence, data access and approximations

4 November 2026 update: see [Supply data, features and assumptions](SUPPLY_DATA_FEATURES_AND_ASSUMPTIONS.md). Public Janori source/scheme metadata is now verified as downloadable; dated delivery/device requests were empty. A further six-resource flow audit includes CWC Satara context. These findings do not supply village delivery/shortage targets. Offline formula estimates and explicit scenario bounds preserve provenance; operational gaps remain.

Checked 3 November 2026. Publicly accessible data is not a complete source-to-tap operational network. Missing measurements remain unavailable; no village supplies have been fabricated or automatically approved.

## What Maps now supports

Select a village in Admin → Maps. The village view reports location coverage, documented connections, recent delivery readings, pipeline/DMA gaps and demand/storage gaps. Sources outside the village or district remain visible when a reviewed connection explicitly identifies them.

An authorised administrator or official within the village's jurisdiction can record a source connection using **Record or update source evidence**. Each review records a scheme/service-area reference, source reference, evidence URL, evidence date, explanation, review method and expiry. Findings can be documented, not connected, or unresolved. Corrections create a new version with an audit record. Concurrent edits are rejected.

Delivery is a separate finding. A measured delivery needs litres/day, a timezone-aware reading timestamp, evidence link and method. Zero is preserved when measured; missing delivery is not changed to zero. Readings older than 48 hours and expired reviews do not count as current delivery. A stopped-supply report is retained as a report, not converted to a measured volume. Sources without surveyed coordinates are listed without map pins. The form does not generate pipeline routes.

Reviewed connections are evidence entered by an accountable application user; the app cannot independently authenticate the contents of every linked document. These records do not automatically become model inputs or approved supply allocations.

## Sources and access still needed

**4 November update:** further public collection is complete for the enumerated JJM/PMC/WSSD/PoCRA sources: 40,297 village household/tap profiles, 648 tanker spreadsheets, 84 tanker PDFs and 504 dated district weather rows. These add context, not eligible daily village supply/outcome rows. Full coverage, file checks, assumptions and the unsent access request are in [Public supply-data status](PUBLIC_SUPPLY_DATA_STATUS.md).

| Required data | Authoritative route | What is available / missing |
|---|---|---|
| Scheme, source and village/service-area relationships | [JJM Citizen Corner](https://ejalshakti.gov.in/JJM/citizen_corner/villageinformation.aspx), [JJM API guide v1.02](https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf) | Public portal exposes scheme/source sections. The documented bulk API requires registration, authority approval and API permissions. No credentials or application were submitted. JJM IDs are not assumed equal to LGD IDs. |
| Source-to-tap assets, Sujal Gaon/service-area IDs | State JJM/WSSD; [20 August 2026 Sujalam Bharat policy announcement](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2301566&lang=1&reg=3) | Official policy establishes governed access. No unrestricted statewide asset export was verified. Need an authorised scheme/service-area crosswalk. |
| Pipes, pumps, valves, treatment plants, tanks and DMA topology | Maharashtra WSSD/MJP, Zilla Parishad rural water-supply divisions and scheme operators | Need surveyed GIS, stable IDs, upstream/downstream assets, service villages, commissioning/retirement dates and operational status. No public complete operational feed verified. |
| Actual water reaching villages | Scheme operators / Gram Panchayat / Paani Samiti | Need meter location, time interval, cumulative/daily inlet and outlet readings, units, calibration and meter outages; also tanker delivery logs. Dam storage, sanctioned capacity and tap counts cannot substitute. |
| Storage, source yields and allocations | Scheme operators, GSDA and allocation authorities | Need dated tank opening/closing storage, working capacity, pump tests, permitted/allocated abstraction and shared-source allocations. |
| Current demand | Dated village household/population register and operator bills/meters; agriculture, livestock and industrial records | No 2011 population or default household-size conversion. Household tap counts are not population or litres consumed. Animal counts from 2019 are not today's livestock demand. |
| Official future weather forecasts | [IMD API reference](https://api.imd.gov.in/public/api_reference.html) | Previously checked forecast endpoint returned HTTP 401; API access required. Existing Open-Meteo support is a separately labelled non-government grid forecast. |
| Modern village coordinates/boundaries | Maharashtra land records/LGD/SOI or authority GIS export | LGD directory establishes identities, not coordinates. The checked [MRSAC/GSDA configuration](https://jsin.mrsac.org.in/mahagsda/config.xml) references `admin2011` boundaries; these have been excluded. |

The operator confirmed on 3 November 2026 that JJM/Sujalam approval has not been requested. Those integrations remain awaiting authority access. No emails, access applications or messages have been sent to authorities.

## Public pipeline and utility data added

The [MIDC Department Utility Map Service](https://gis.midcindia.org/server/rest/services/Application/Department_Utility_Map_Service/MapServer) exposes nine water-network layers. Its public query returned **881 features**: 660 [water pipelines](https://gis.midcindia.org/server/rest/services/Application/Department_Utility_Map_Service/MapServer/6), 175 valves, 32 reservoirs/tanks, 7 pump houses, 6 treatment plants and 1 jackwell/intake. Flow meters, water meters and water-specials layers returned zero records. This is partial **industrial** infrastructure coverage, not statewide rural drinking-water coverage. Survey/update dates and present operation are unknown.

Maps has separate industrial-pipe, pump, valve, intake, tank and treatment filters plus **Pipes & network assets**. MIDC geometries use the server's EPSG:4326 output with 0.0002° display generalisation. Stable object IDs, per-layer record counts, a hash receipt and source URLs are preserved. Person/contact fields are not requested. Asset attributes retain original values; unspecified capacity/discharge units are not guessed. These records are reference context, excluded from prediction inputs and not automatically connected to villages.

The [MRSAC WSSD map configuration](https://jsin.mrsac.org.in/mahawssd/config.xml) identifies PWS, regional and spot scheme-point layers and PWS/regional pipe-line layers. All five referenced HTTPS service metadata requests failed TLS retrieval in this environment; the web retrieval tool also could not access the checked services. Their records and village connections have not been invented. Authority access or a working export is still needed.

The [PoCRA water-budget portal](https://gis.mahapocra.gov.in/html/water-budget-service/water-budget.html) was also inspected. Public client code includes crop-deficit/soil-moisture models, but one budget request hard-codes `2025-06-08`, and its displayed last-update footer is calculated from yesterday's system date. The footer therefore does not establish actual data freshness. These estimates have not been imported as current measured domestic demand or delivery.

To refresh the public industrial utility reference layers independently:

```powershell
.venv/Scripts/python.exe -m scripts.sync_public_utilities
```

## Additional reservoir observations

The explicitly public [Pravah-AI dam feed](https://pravahaimwrd.in/api/v1/public/dams/latest) returned 3,079 records. Of these, 2,200 have supported coordinates and measurements, 840 have no valid Maharashtra coordinate and 39 were rejected for unsupported dates/identity/measurements. Original response and SHA-256 receipt are retained in the ignored raw cache. The mapped subset is in `data/water/reservoirs.geojson`.

This dashboard is WRD branded, but its publisher authority has not been independently confirmed. It is visibly labelled **publisher authority unconfirmed / context only**, excluded from prediction inputs, and not merged by dam name into NWIC records. The [official WRD website](https://wrd.maharashtra.gov.in/) links a different portal, `mwrdpravah.in/damstorage`; that portal and the linked storage PDF failed TLS retrieval here. No figures from the failed official export were invented. The two domains are not asserted to be equivalent.

## Historical collection and exports

All **98 historical resources** have now been downloaded and calendar-date-profiled: **6,729,094,635 raw bytes**, **42,720,846 source rows**, and **39,240,902 candidate export rows from 2021–2025**. There are no remaining download/profile failures. This is the indexed NWIC historical collection, not a claim that all village operational data is public. The resumable collector downloads these via verified HTTP ranges, checking response lengths, byte offsets and stable ETags, then hashes each complete archive. Existing cache files are accepted only when their revision, size and hash match the receipt.

```powershell
.venv/Scripts/python.exe -m scripts.collect_water_history
.venv/Scripts/python.exe -m scripts.publish_historical_quality
```

Progress and failures are recorded in `data/water/history-collection.json` and exposed on Maps → Live & training data. Each CSV candidate export is stored under ignored `data/raw/training/` with its own metadata. The export retains calendar dates from 2021 through the year before the current year (2021–2025 at this check), preserving original columns and units. Older years and the current-year holdout are excluded. Missing cells remain blank.

**Downloaded/profiled is not quality-approved.** Duplicates, gaps, physical plausibility, sensor datum, sampling interval, station identity and chronological train/validation/test splits still require modelling review. Profiling validates calendar dates, not every intra-day timestamp or timezone. Resources without a State column rely on their published Maharashtra resource geography. No model was retrained or approved by these scripts.

The manual groundwater archive also contributes 3,871 historical well-coordinate identities with supported readings from 2021 onward, the latest dated 16 October 2025. Of its 636,605 raw rows, 75,685 pass the 2021–2025 date/state export filter; older rows are excluded. Its only non-ASCII byte is AE (278 registered-sign characters), so this one source is explicitly decoded as Windows-1252 and exported as UTF-8. Other resources retain strict UTF-8 decoding. No unknown encoding is guessed. The map does not infer LGD village identity or supply from the publisher’s village-name field.

All eight indexed historical water-quality resources have been retrieved. Their latest supported samples from 2021 onward produce 1,544 historical sample locations, published as an explicitly dated context layer. They are not current drinking-water safety certificates or village supply connections.

Refresh current public observations and the additional reservoir/context manifest with:

```powershell
.venv/Scripts/python.exe -m scripts.sync_water_data
```

Do not run multiple collectors against the same raw files simultaneously. Raw archives and training exports are ignored by Git; publish receipts/catalogues rather than committing GB of downloaded records.

## Approximations and assumptions

| Area | Actual rule | Implication |
|---|---|---|
| Village map area | Supplied boundary; otherwise ±0.12° around reviewed coordinates; otherwise district station extent with 0.05° padding | Display context, not a hydrological catchment or service area. No guessed village pin. |
| District context | Published district name/code and feature bounding-box intersection | Border-crossing features may appear. This is not source-to-village verification. |
| Reference geometry | CRS transformed to EPSG:4326; simplified by 0.0002° (roughly 20 m); survey date unknown | Geometry is a reference, not a survey-accurate current pipe network. |
| Monitoring identity | Agency + station name + coordinates rounded to 5 decimals | Minor coordinate/name changes may split identities. Different agencies are not merged solely by proximity. |
| Dates and freshness | Unzoned NWIC timestamps treated as India time; date-only dam readings represented at 00:00 India time; recent = ≤48 h | Exact time of date-only readings is unknown. Freshness is an app rule, not a government reliability threshold. |
| Source connection | Explicit reviewed crosswalk or dated evidence review | Nearby wells/rivers, shared names and downhill terrain are insufficient. Prior crosswalks do not prove current operation. |
| Water delivered | Separate dated meter/delivery evidence | Storage, river discharge, groundwater depth, tap coverage and sanctioned scheme capacity are never converted directly to village delivery. |
| Missing operational inputs | No assumed household size, leakage rate, pump capacity, source yield or straight-line pipe | Missing values block a complete supply balance instead of being silently filled. |
| Industrial utility geometry | MIDC water assets; source survey/update date unknown; empty meter layers | No rural service area, flow direction, valve operation, pressure or current delivery is inferred. |
| Display limits | State map defaults to 4,000 features (maximum 12,000); sidebar lists 150 matches | Zoom/filter to inspect additional records. Counts are map records, not confirmed supplying sources. |
| Review validity | Operator-selected expiry, at most 366 days after evidence date | App review rule, not a government verification standard. |
| Additional dams | Publisher coordinates and numbers retained; authority unconfirmed | Context only; no cross-dataset name joins or model inputs. |
| Existing groundwater models | Station-history features, 1–15-day groundwater forecasts | Do not forecast whole-village water availability or route water through pipes. New map layers have not been added to model features. |
| Existing weather requests | Village coordinates rounded to 0.1° request cells; provider response preserves actual grid location | Roughly 10–11 km request grouping; grid forecasts are not village rain gauges. |
| Existing crop irrigation planning | ETc = reviewed Kc × ET0; effective rain = forecast rain × reviewed factor; requirement divided by reviewed irrigation efficiency | Soil-water contribution defaults to 0 mm when unmeasured. Crop coefficients and efficiencies require review. This estimates demand, not water availability or permission. |
| Existing supply scenarios | Reviewed sector demand, inflow, opening storage, capacity and delivery limit | Scenario calculations are not measured service delivery. Missing supply produces an unavailable shortage result. |

Maps exposes the applicable map assumptions under **Approximations and missing information** for each selected village. The 2011 Census is not a population, demand or infrastructure baseline.


## Final validation

- All 98 archive receipts and exported row counts reconcile with their 2021–2025 calendar-year counts. Original source files contain 42,720,846 rows; filtered candidate exports contain 39,240,902 rows. No download/profile failures remain.
- The running map reads 10,140 point records and 18,252 reference network features. These include multiple time periods and data families; they are not a count of unique confirmed supplying sources.
- 19 focused map/data/review tests and four browser checks passed. TypeScript and both web builds passed. Screenshots were visually inspected.
- Local API health returned 200. Anonymous catalogue and review requests returned 401; the review route is active. No database migration was run.
- Earlier auth/security checks passed. The earlier full backend suite still had failures caused by absent older research model artifacts; this work does not restore those models, train or approve a new model.
- Recent code and derived data changes are local and uncommitted. Raw archives and training exports are ignored by Git.
