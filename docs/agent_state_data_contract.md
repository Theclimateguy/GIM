# Agent State Data Contract

This document separates the real-world source layer from the model-ready `agent_states.csv` layer.
It is the working contract for the future `top-50 + regional aggregates + Taiwan` rebuild.

## 1. Design Rules

- The model CSV must contain only fields that are actually used by the loader or simulation logic.
- Physical quantities must never be negative.
- `capital` is optional input. If missing, the loader derives it as `3 * gdp`.
- `public_debt_pct_gdp` is the preferred debt input for build pipelines. The loader derives absolute `public_debt`.
- `military_gdp_ratio` is deprecated for model CSV. It is useful in the source layer, but the simulation does not read it directly.
- Resource columns are model-normalized state variables, not raw FAO or energy workbook units.
- Residual regional aggregates must be built from the full raw country layer first, then normalized. Do not create aggregates by subtracting already-normalized partial totals if that can produce negative remainders.

## 2. Canonical Model CSV

### Required columns

- `id`
- `name`
- `region`
- `regime_type`
- `gdp`
- `population`
- `fx_reserves`
- `trust_gov`
- `social_tension`
- `inequality_gini`
- `climate_risk`
- `pdi`
- `idv`
- `mas`
- `uai`
- `lto`
- `ind`
- `traditional_secular`
- `survival_self_expression`

### Recommended columns

- `alliance_block`
- `public_debt_pct_gdp` or `public_debt`
- `co2_annual_emissions`
- `biodiversity_local`
- `water_stress`
- `regime_stability`
- `debt_crisis_prone`
- `conflict_proneness`
- `tech_level`
- `security_index`
- `military_power`
- `energy_reserve`
- `energy_production`
- `energy_consumption`
- `food_reserve`
- `food_production`
- `food_consumption`
- `metals_reserve`
- `metals_production`
- `metals_consumption`

### Optional columns accepted by loader

- `capital`
- `public_debt`
- `public_debt_pct_gdp`

### Deprecated columns

- `military_gdp_ratio`

## 3. Units for Model CSV

| Field group | Unit in model CSV | Note |
| --- | --- | --- |
| `gdp`, `public_debt`, `fx_reserves`, `capital` | current USD trillions | Divide raw USD by `1e12`. |
| `population` | persons | Raw headcount. |
| `co2_annual_emissions` | GtCO2e | Convert Mt to Gt by dividing by `1000`. |
| `inequality_gini`, Hofstede | original index scale | `0..100`. |
| `traditional_secular`, `survival_self_expression` | WVS-style scale | `0..10`. |
| `trust_gov`, `social_tension`, `climate_risk`, `biodiversity_local`, `water_stress`, `regime_stability`, `debt_crisis_prone`, `conflict_proneness`, `security_index` | bounded model score | `0..1`. |
| `tech_level`, `military_power` | positive model multiplier | Usually around `0.5..2.0`. |
| Resource columns | model-normalized stock/flow units | Do not mix raw tonnes, calories or EJ directly into the CSV. |

## 4. Source Dictionary

### 4.1 Economy and Macro

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `gdp` | World Bank `NY.GDP.MKTP.CD` | Use 2023 current USD. | Sum. | No imputation for top-50. Taiwan uses official national accounts or IMF-compatible series. |
| `population` | World Bank `SP.POP.TOTL` | Use 2023. | Sum. | No imputation for top-50. Taiwan from official statistics. |
| `fx_reserves` | World Bank `FI.RES.XGLD.CD` | Use 2023 if available, else latest year. | Sum. | If missing, use IMF/central bank latest or regional GDP-weighted reserve ratio. |
| `public_debt_pct_gdp` | IMF WEO gross debt or general government debt | Use 2023 estimate. | GDP-weighted average, then derive absolute debt. | If missing, use latest IMF value; if unavailable, regional GDP-weighted median. |
| `capital` | World Bank wealth accounts, Penn World Table, or internal calibrated proxy | Optional. | Sum if measured on same basis. | If absent, loader derives `3 * gdp`. |

### 4.2 Climate and Environment

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `co2_annual_emissions` | World Bank `EN.GHG.CO2.MT.CE.AR5` or equivalent total CO2 series | Use 2023 Mt and convert to Gt. | Sum. | No imputation for top-50. Taiwan from official inventory or global datasets. |
| `climate_risk` | ND-GAIN vulnerability or equivalent hazard-vulnerability index | Use 2023 or latest available. | Population-weighted average on raw vulnerability score, then normalize to `0..1`. | If missing, use regional population-weighted mean. |
| `water_stress` | World Bank `ER.H2O.FWST.ZS` or FAO AQUASTAT | Latest available is acceptable; usually 2022. | Population-weighted average or water-withdrawal weighted average if raw inputs exist. | If missing, use regional population-weighted mean. |
| `biodiversity_local` | Protected area, habitat or biodiversity proxy index | Use latest available. | Population-weighted average or land-area weighted average if raw biodiversity basis is land based. | If missing, use regional mean by biome or income group. |

### 4.3 Society and Institutions

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `inequality_gini` | World Bank `SI.POV.GINI` | Use 2023 if available, else latest. | Population-weighted average. | Use latest value first, then regional mean. |
| `trust_gov` | OECD trust in government, Gallup confidence in national government, or calibrated latent score | Use latest cross-country survey if available. | Population-weighted average, then clip to `0..1`. | If survey missing, derive from `government_effectiveness`, `regime_stability`, GDP per capita and inequality. |
| `social_tension` | Calibrated latent score from inflation, food stress, inequality, conflict and trust | Build for 2023. | Recompute after aggregation from aggregate inputs. | Do not fill by residual subtraction. |
| `regime_stability` | WGI Political Stability (`PV.EST`) mapped to `0..1` | Use 2023. | Population-weighted average on mapped score. | If missing, use regional mean from WGI mapping. |
| `debt_crisis_prone` | Derived latent score from debt ratio, FX buffer and regime fragility | Build for 2023. | Recompute after aggregation from aggregate debt ratio, reserves and regime score. | No direct residual subtraction. |
| `conflict_proneness` | Derived latent score from conflict datasets, sanctions exposure and regime fragility | Build for 2023. | Recompute after aggregation from aggregate conflict inputs where possible. | Fallback to regional mean only if raw conflict inputs absent. |

### 4.4 Culture and Values

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `pdi`, `idv`, `mas`, `uai`, `lto`, `ind` | Hofstede dimensions | Treated as slow-moving structural values, not annual. | Population-weighted average. | If country missing, nearest-neighbor by region, language family or income group. |
| `traditional_secular`, `survival_self_expression` | World Values Survey or equivalent values mapping | Use Wave 7 or latest available. | Population-weighted average. | If missing, regional WVS average; if unavailable, infer from regime type, GDP per capita and Hofstede cluster. |
| `regime_type` | Internal categorical mapping | Use 2023 political regime. | Aggregate is a manual label. | No automatic majority vote if the aggregate is geopolitically mixed. |
| `alliance_block` | Internal geopolitical classification | Use 2023 stance. | Aggregate is a manual label. | Keep manual, not numeric. |

### 4.5 Technology and Security

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `tech_level` | Derived latent score from GDP per capita, R&D intensity, manufacturing complexity and governance | Build for 2023. | Recompute after aggregation from aggregate GDP per capita and structural proxies. | If some inputs missing, use regional GDP-weighted mean. |
| `security_index` | Derived score from WGI government effectiveness, rule of law and strategic buffer | Build for 2023. | Recompute after aggregation from aggregate governance proxies. | If missing, map from WGI governance score. |
| `military_power` | Derived score from military spending, force posture and economic scale | Build for 2023. | Recompute after aggregation from spending and GDP scale. | Do not use `military_gdp_ratio` alone as the final state variable. |

### 4.6 Resources

| Model field | Preferred source | 2023 rule | Aggregate rule | Imputation rule |
| --- | --- | --- | --- | --- |
| `energy_reserve` | World Mining Data fuels + World Bank fossil rents / net energy imports | Build reserve basis from observed 2023 production with source-backed reserve-years proxy. | Sum raw reserve basis first, normalize after aggregation. | Missing direct producer data can use World Bank energy balance fallback; reserve-years remain proxy-based. |
| `energy_production`, `energy_consumption` | World Mining Data fuels + World Bank energy use / net imports | Build 2023 raw production in Mtoe-equivalent and raw consumption from WB energy use per capita. | Sum raw layer first, normalize after aggregation. | Missing producer rows fall back to WB net-import balance; no world-residual subtraction. |
| `food_production`, `food_consumption` | FAOSTAT Food Balance Sheets | Build from 2023 top-level food groups in `1000 t`, then normalize after aggregation. | Sum raw layer first, normalize after aggregation. | If direct country rows are absent, use regional per-capita imputation before aggregation. |
| `food_reserve` | Internal strategic buffer proxy | Build from import dependence, production surplus and food cover days. | Recompute after aggregation. | Do not compute as world residual. |
| `metals_production`, `metals_consumption`, `metals_reserve` | World Mining Data + World Bank manufacturing structure | Build production from 2023 weighted mineral basket shares; build consumption from manufacturing-demand proxy; build reserve basis from production and mineral-rents proxy. | Sum raw layer first, normalize after aggregation. | Countries with no direct mining row can be zero-production actors; do not force world residuals negative. |

## 5. Build Rules for Top-50 + Residual Regions + Taiwan

- Step 1: Build a full raw country layer for all available countries plus Taiwan in real units.
- Step 2: Select top-50 by 2023 nominal GDP.
- Step 3: Keep Taiwan as an explicit actor even if it falls outside the top-50 ranking.
- Step 4: Assign all remaining countries to residual regional buckets.
- Step 5: Aggregate raw quantities inside each residual region.
- Step 6: Only after that, transform the raw layer into model units and latent scores.

### Additive fields

- `gdp`
- `population`
- `fx_reserves`
- `public_debt`
- `co2_annual_emissions`
- raw resource totals before normalization

### Weighted-average fields

- `inequality_gini`
- Hofstede dimensions
- WVS values
- `climate_risk`
- `water_stress`
- `biodiversity_local`
- `trust_gov`
- `regime_stability`

Preferred weights:

- Population weight for social and cultural indicators.
- GDP weight for debt and macro-financial indicators when averaging ratios.
- Raw physical weight for physical intensity variables when the raw basis is available.

### Recompute after aggregation

- `social_tension`
- `debt_crisis_prone`
- `conflict_proneness`
- `tech_level`
- `security_index`
- `military_power`
- `food_reserve`

## 6. Validation Rules

- No negative physical quantities.
- No duplicate `id`.
- No duplicate `name`.
- All `0..1` model scores must stay inside bounds.
- Hofstede fields must be inside `0..100`.
- WVS axes must be inside `0..10`.
- Aggregate rows must be created from raw country totals, not by subtracting partially normalized columns.
- If a residual region would produce a negative resource component, rebuild the raw aggregation instead of clipping silently.

## 7. Known Coverage Constraints

- World Bank coverage is strong for GDP, population, CO2 and reserves, but weak for debt and uneven for Gini.
- Water stress is typically latest available rather than exact 2023.
- WVS and Hofstede are structural snapshots, not annual time series.
- Taiwan must be added manually because it is not consistently covered in the same way as World Bank sovereign entries.

## 8. Practical Recommendation

- Treat the source layer as a country panel in real units.
- Treat the model CSV as a compiled artifact.
- Keep the compiled CSV compact and model-facing.
- Keep deprecated fields such as `military_gdp_ratio` out of the compiled CSV.
