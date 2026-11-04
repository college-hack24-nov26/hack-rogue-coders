# JalSathi operational-data request packet

Prepared 4 November 2026. **Draft only; not submitted.** This packet covers data still missing after public collection. It is not an assertion that every authority holds or can release every requested field.

## Authority routes

- JJM API registration/permission: [official API portal](https://ejalshakti.gov.in/webapi/) and [Help Guide v1.02](https://ejalshakti.gov.in/webapi/Content/JJM_Web_API.pdf). Request Maharashtra village, habitation, scheme/source and service-area identifiers, dictionary and permitted APIs. Ask separately whether operational time series are available.
- Maharashtra state water-supply data: [Water Supply and Sanitation Department](https://water.maharashtra.gov.in/), its [attached offices](https://water.maharashtra.gov.in/en/organization-type/attached-offices/) and the relevant Zilla Parishad rural water-supply divisions, scheme operators and Gram Panchayats/Paani Samitis. Confirm the current data custodian through the department rather than guessing an email recipient.
- [Maharashtra Jeevan Pradhikaran](https://mjp.maharashtra.gov.in/) for applicable multi-village scheme engineering, network topology and operational records. Scheme ownership and available records need confirmation.
- MJP's official “IoT for JJM Schemes” link points to [MahaJal IoT](https://dashboard1.mahajaliot.in/). Its published client protects LPCD, consumption, scheme and report routes. Request an approved read-only account or export/API for relevant village/ESR operational history, its dictionary, coverage and publication timestamps. No login bypass or account registration was attempted. Access to this portal may be separate from national JJM API approval.

## Reusable request text

Subject: Maharashtra village water-supply operational data and permitted API/export access for JalSathi

We are developing JalSathi to evaluate whether village water supply is sufficient for the next seven and fifteen days. We are requesting access to existing records and their data dictionary for Maharashtra, starting with schemes/villages for which reliable operational history is available and expanding according to availability and permissions.

Please confirm which of the following records your office holds, the responsible custodian, permitted research/application uses, geographic coverage, measurement methods, quality controls, update schedule, historical revisions and access procedure. A machine-readable CSV/JSON export or documented API is preferred. Household names, phone numbers, personal addresses and beneficiary details are not required.

Requested history: 1 January 2021 through the latest completed day, with priority to the latest 6–12 months of continuous daily records. Please identify missing periods and scheme changes explicitly; provide available data rather than substituting older population or infrastructure assumptions. Current daily updates would support later forecasting, subject to their completeness and publication timing.

Required data groups:

1. Stable village/habitation/service-area identifiers and dated crosswalks to LGD/JJM identifiers, including splits, mergers and renamings; scheme/source IDs and villages actually served.
2. Daily or interval inlet/outlet meter readings and volumes at the village delivery boundary, units, meter IDs/locations, calibration, reading times, resets, outages and publication/revision timestamps. Please distinguish measured, estimated, scheduled and sanctioned values.
3. Tank working capacity, dimensions/calibration, dead/reserve storage, opening/closing levels or usable volumes and measurement timestamps.
4. Pump/source flow tests, actual operating hours, breakdowns, power interruptions, daily allocations and transfers between service areas; conveyance losses only where measured or documented.
5. Tanker requests, assessed need and reasons, request/assessment dates, dispatches, destination service areas, actual received litres or calibrated capacity × completed trips, receipt confirmation and cancelled/missed deliveries. Routine dispatch and emergency shortage relief must be distinguishable.
6. Dated current population/household registers in aggregate and domestic, livestock, agricultural, institutional and industrial demand where applicable. Please specify whether demand is independently estimated/measured or constrained by supply.
7. Shortage incidents, start/end dates, affected service areas, restrictions, verified unmet demand and follow-up showing whether records cover days without shortages as well as incidents.
8. GIS/topology of sources, intakes, treatment, pipes, valves, pumps, tanks and DMAs, with surveyed coordinates/CRS, asset IDs, upstream/downstream relationships, operational dates/status and service-area links. Sensitive locations may be generalized or omitted as required, with the limitation documented.

Please also provide release conditions, permitted retention/sharing, contact for corrections, expected latency and any restrictions on using these records for model development or application forecasts. We will keep source lineage and uncertainty and will not present estimates as measurements. Please advise if a formal application or agreement is required.

## Preferred export structure

One daily operations row per verified `village_id`/`service_area_id`, `scope`, `date`; no duplicate unversioned rows. An interval export can be aggregated only when interval coverage and cumulative-meter resets are documented.

| Fields | Units/meaning |
|---|---|
| Source namespace + village/service-area/scheme/source/asset IDs | Explicit namespaces and valid-from/to mapping; no name-only joins |
| `date`, interval start/end, `available_at`, revision time | Local service date; timezone-aware times; actual publication time when known |
| Inlet/outlet/received tanker volume | Litres or explicit original unit; daily total vs cumulative reading identified |
| Opening/closing usable storage and working capacity | Litres; reserves/dead storage separate; actual measurement method |
| Flow-test rate and actual running hours | L/s and hours with test/operation dates; estimates flagged |
| Demand by sector, independently observed unmet demand | Litres/day and estimation/measurement method; service scope and coverage |
| Pump/power outages, restrictions, shortage/need assessments | Start/end, cause, affected service area and reviewed evidence |
| Provenance, completeness, quality and missingness | File/record reference, measured/reported/estimated basis, calibration, missing-data code, revision history |

Blank/missing values must be distinguishable from measured zeros. Unknown publication times should be marked unknown, not copied from observation dates. Please provide counts of villages, dates and records, any known coverage gaps and a small representative sample before a large transfer.

## Project processing after access

Reconcile identities and units; retain originals; check totals, meter resets and dates; separate measured values from formula estimates; establish complete service-day coverage; then build chronological seven/fifteen-day outcomes. Independently review the project's urgency rubric, including whether a tanker was actually needed within the first seven days. Reserve later dates and held-out villages for validation before accepting any model for wider Maharashtra use.
