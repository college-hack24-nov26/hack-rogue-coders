# Drought intensity and village supply shortage

Update: the user-defined [0-5 supply-urgency scale](SUPPLY_URGENCY_SCALE.md) is now supported in offline training, with level 5 requiring reviewed tanker need within seven days. It is distinct from the climate-drought indices discussed below. No urgency candidate has been trained on real village records yet. The prior binary target is retained with `--target sufficiency`.

Requirement recorded 4 November 2026. **Climate drought intensity is not currently implemented or a target of the offline trainer.** Training reports state this explicitly. No climate-drought category is inferred from groundwater depth, pipe proximity, a supply-urgency class or shortage probability.

The later prediction interface should distinguish these outputs:

| Output | Meaning | Evidence required |
| --- | --- | --- |
| Supply sufficiency, next 7/15 days | Whether daily usable supply meets the named village demand scope | Deliveries, usable storage, demand and verified supplying connections; current trainer targets these events |
| Supply-shortage intensity | Deficit litres, deficit as a fraction of demand, days affected and worst daily deficit | Dated water-balance inputs or separately trained and validated volume/deficit forecasts; the current binary classifiers do not estimate magnitude |
| Drought intensity | Meteorological/agricultural/hydrological drought conditions with an explicit index, period and location | Dated SPI/SPEI or other supported indices, rainfall/dry spells, and appropriate vegetation/soil-moisture/hydrological evidence |

A village may experience a supply shortage during normal rainfall because of an outage or distribution problem. A village in a dry region may maintain supply through storage, allocations or transfers. Neither condition alone establishes the other.

IMD describes SPI as precipitation anomalies standardized against historical rainfall for a specified accumulation period. Its published guidance distinguishes moderately, severely and extremely dry conditions. These are **SPI dryness classes**, not a complete official drought declaration or arbitrary 7/15-day shortage bands. Source: [IMD Climate Application FAQ](https://www.imdpune.gov.in/caui/faq_caui.html) and [IMD SPI bulletin methodology PDF](https://www.imdpune.gov.in/caui/dru-spi/spi_info.pdf).

India's drought-monitoring framework uses rainfall-related indicators along with impact indicators such as crop/vegetation and soil-moisture conditions. A rainfall index alone must not be presented as a verified composite agricultural/hydrological assessment. See [ISRO/SAC Krishi-DSS drought portal](https://vedas.sac.gov.in/vapps/krishi_dss/dss/) and the [Drought Management Manual hosted by SAC](https://vedas.sac.gov.in/static/pdf/Drought%20Manual-2020.pdf). These references establish methodology and candidate sources; an automated, current Maharashtra village-index feed has not been obtained or joined here.

Before implementation:

1. Retrieve the latest available publisher-issued index values and historical index observations. Preserve the index name, accumulation window, valid period, issue/publication time, source, reference climatology, units and native grid/administrative geography.
2. Verify Maharashtra coverage, missingness, update cadence, download/API access and a reproducible village-to-grid/administrative mapping. District or grid data must retain its actual spatial resolution; it is not an independent measurement at each of 44,929 villages.
3. Prefer a current published standardized index over fitting SPI to the short 2021+ local archive. Standardization requires an appropriate historical reference distribution; current operational population/assets must not be replaced by old Census baselines.
4. Display drought **conditions for the publisher's valid period** separately from future supply predictions. A current monthly drought index is not automatically a daily drought forecast for the next 7/15 days.
5. If learned drought forecasts are requested later, use independently dated index targets and chronological/region holdouts. Only index releases available at forecast issue time may enter supply-model features. Avoid future observed rainfall or retrospectively revised indices leaking into historical predictions.
6. Distinguish a publisher's index class, an app estimate and an official government drought declaration. No unreviewed mild/moderate/severe thresholds or weighted composite score will be inserted.
7. Keep missing/stale/unmapped evidence as **not assessed/insufficient data**, not no drought. Show data dates and assumptions alongside every intensity result.

No model, display layer, satellite feed, climate normal, drought declaration or forecast was added by recording this requirement. Prediction implementation remains separate from the user's requested offline training setup.
