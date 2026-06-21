# GIM17 External Data Sources (F3 unique-layer grounding & validation)

Maps each GIM unique-layer variable to its established external index, with the exact source
and how to obtain it. See `docs/SOCIAL_GEO_METRICS.md` for the variable→metric rationale.
Ingestion: `scripts/ingest_external_data.py` (World Bank live) + hand-downloaded bulk archives.

Verified reachable June 2026.

## A. World Bank API — fetched live by the ingestion script (no auth)

| GIM target | External metric | WB code | Source DB | Notes |
|---|---|---|---|---|
| economy anchor | GDP (current US$) | `NY.GDP.MKTP.CD` | WDI (source 2) | clean, 1990–2024 |
| population / CINC | Population, total | `SP.POP.TOTL` | WDI | CINC component |
| CINC | Energy use (kg oe p.c.) | `EG.USE.PCAP.KG.OE` | WDI | CINC component |
| `economy.military_spending` / CINC | Military expenditure (US$) | `MS.MIL.XPND.CD` | WDI, **SIPRI-sourced** | direct $ anchor |
| mil burden | Military expenditure (% GDP) | `MS.MIL.XPND.GD.ZS` | WDI, SIPRI-sourced | |
| `society.inequality_gini` | Gini index | `SI.POV.GINI` | WDI | SWIID proxy (sparse coverage) |
| `risk.regime_stability` | Political Stability & Absence of Violence | `PV.EST` | WGI (**archive source 57**) | path-endpoint; versioned |
| `society.trust_gov` | Voice & Accountability | `VA.EST` | WGI (57) | |
| `political.legitimacy` | Government Effectiveness | `GE.EST` | WGI (57) | |
| `political.legitimacy` | Rule of Law | `RL.EST` | WGI (57) | |

WGI note: the WB API serves WGI only under the archived source id 57 via the path-style
`/v2/sources/57/country/{c}/series/{code}/time/all/data` endpoint (the `?source=` query param
is stripped by some HTTP redirects). The script keeps the latest version per (country, year).
Cleaner alternative: the official WGI bulk CSV (see below) — preferred for a frozen release.

## B. Bulk archives — download by hand, place in `data/external/raw/`

The World Bank API does NOT serve these; they are zip/xlsx/rda. Download and drop into
`data/external/raw/` (filenames the parser expects in parentheses).

| Dataset | What it anchors | Download | File expected |
|---|---|---|---|
| **UCDP/PRIO Armed Conflict Dataset v24.1** | conflict onset/escalation backtest target (`at_war`, `conflict_level`) | https://ucdp.uu.se/downloads/ (UCDP/PRIO ACD, CSV) | `ucdp-prio-acd-241.csv` |
| **ACLED** (optional, event-level unrest) | `social_tension`, protests/riots | https://acleddata.com/data-export-tool/ (free account) | `acled_events.csv` |
| **SWIID v9.x** | `society.inequality_gini` (preferred, standardized) | https://fsolt.org/swiid/ (GitHub `fsolt/swiid`) | `swiid9_x_summary.csv` |
| **Correlates of War — National Material Capabilities v6.0** | CINC validation for `military_power` | https://correlatesofwar.org/data-sets/national-material-capabilities/ | `NMC-60-abridged.csv` |
| **SIPRI Military Expenditure Database** (full) | `economy.military_spending` full series | https://www.sipri.org/databases/milex | `SIPRI-Milex-data.xlsx` |
| **Global Sanctions Database (GSDB) v3** | `political.sanction_propensity` | https://www.globalsanctionsdatabase.com/ | `GSDB_V3.xlsx` |
| **V-Dem v14** (optional) | `culture.regime_type` ground (Democracy/Autocracy) | https://v-dem.net/data/the-v-dem-dataset/ | `V-Dem-CY-Core-v14.csv` |
| **WRI Aqueduct 4.0** (optional) | `risk.water_stress` | https://www.wri.org/data/aqueduct-global-maps-40-data | `Aqueduct40_baseline.csv` |

## C. Already in-repo (no external fetch needed)

| Variable | Source | File |
|---|---|---|
| global fossil CO₂ | Global Carbon Project / OWID | `data/global_co2_emissions_owid.csv` |
| temperature 1990–2023 | NOAA / HadCRUT5 | `tests/fixtures/climate_observations_1990_2023.json` |
| `technology.military_power` (CINC-style) | reproduced from GIM components (pop, energy, GDP, milex), CoW methodology | `gim/capability.py` (validated vs published CINC: CN 0.205, US 0.147, IN 0.096) |

## Provenance discipline

When a frozen release is cut, record each file's download date and dataset version in
`data/external/raw/MANIFEST.json` and treat them as immutable inputs (mirror the climate
artifact-binding rule in `docs/CALIBRATION_REFERENCE.md`).
