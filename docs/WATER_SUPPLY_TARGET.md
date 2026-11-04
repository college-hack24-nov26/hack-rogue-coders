# Prediction target: village water-supply sufficiency

The primary question is whether usable water covers village demand every day over the next 7 and 15 days. Groundwater station forecasts do not answer this question and are no longer foregrounded on Water estimates.

The 4 November 2026 [supply-data and feature-engineering audit](SUPPLY_DATA_FEATURES_AND_ASSUMPTIONS.md) adds checked public evidence, 147,069 daily surface-flow context rows, explicit input formulas and a provenance-aware 7/15-day training-data builder. The public requests supplied no verified daily Maharashtra village shortage targets; training readiness remains false. These offline estimates do not automatically replace the app's reviewed inputs.

GET /api/v1/villages/{id}/supply-outlook returns both horizons, a nullable enough flag, shortfall in litres, first shortage date and daily storage/delivery balances. Missing sectors, expired source allocations, or unreviewed net supply/storage partitioning produce insufficient_data. All four sectors must be recorded; an inapplicable sector requires an explicit reviewed zero.

Current implementation is a conditional scenario using reviewed daily demand and inflow rates, opening usable storage, capacity and delivery limits. Rates stay constant through the horizon. Daily inflow can serve daily demand before remaining water is capped by tank capacity; excess becomes overflow. It does not resolve hourly outages or automatically move sector allocations.

SupplyAllocation now accepts storage_partition_verified and net_supply_after_losses, both false by default. An accountable reviewer must explicitly confirm non-overlapping sector storage and supply net of treatment/conveyance losses. Source and allocation evidence must cover the full horizon. These confirmations do not make an allocation a live measurement.

No supply ML model has been trained or approved. The old groundwater artifacts remain research assets and are excluded from this endpoint. To build a trained supply forecast, collect dated village inlet deliveries, usable tank storage, source yield/allocations, pump/valve outages, losses and demand; evaluate shortage events and supply volumes chronologically for 7- and 15-day horizons. The public station archive cannot substitute for those village delivery targets.

Admin Water estimates, farmer Water Outlook and assistant evidence now use the supply-sufficiency endpoint. The farmer cache uses a new namespace so old groundwater forecasts cannot appear as supply results. Legacy groundwater research endpoints/artifacts are retained for compatibility, outside the primary supply view.

Validation: the calculation/API tests cover 7-day sufficiency with a day-11 shortage inside the 15-day window, expiring source plans, missing sectors, unreviewed loss/storage assumptions and direct pipe delivery without tank storage. Both web builds, the farmer web export and TypeScript checks pass.
