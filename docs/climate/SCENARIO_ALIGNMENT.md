# GIM18 SSP/RCP Alignment & FAIR/MAGICC Benchmark (T2.1 + Phase-4 benchmark)

Establishes that GIM's physical climate core is consistent with the IPCC AR6
reduced-complexity climate models (FAIR, MAGICC) and locates GIM's emergent baseline within
the AR6 SSP warming envelopes. `gim/scenario_alignment.py`, `tests/test_scenario_alignment.py`.

## Emulator benchmark (FAIR/MAGICC bar: ECS + TCR)

An AR6-consistent climate emulator must reproduce two assessed numbers:

| metric | GIM | AR6 best (likely range) | source |
|---|---|---|---|
| Equilibrium climate sensitivity (ECS) | 3.00 | 3.0 (2.5–4.0) | AR6 WG1 SPM A.4.4 |
| Transient climate response (TCR) | **1.79** | 1.8 (1.4–2.2) | AR6 WG1 Ch.7 |

TCR is measured by driving GIM's two-box EBM under the idealised 1%/yr CO₂ ramp to doubling
(~year 70) with internal variability switched off (forced response only). Post-T1.3b
recalibration GIM lands at 1.79 °C — essentially the AR6 best estimate. Matching **both** ECS
and TCR is exactly how FAIR and MAGICC are themselves constrained, so GIM's emulator is
AR6-consistent on the equilibrium and the transient response simultaneously.

## SSP warming envelopes

`AR6_SSP_WARMING_2100` holds the AR6 WG1 SPM.1 assessed 2081–2100 warming (vs 1850–1900):

| scenario | best | very-likely range |
|---|---|---|
| SSP1-1.9 | 1.4 | 1.0–1.8 |
| SSP1-2.6 | 1.8 | 1.3–2.4 |
| SSP2-4.5 | 2.7 | 2.1–3.5 |
| SSP3-7.0 | 3.6 | 2.8–4.6 |
| SSP5-8.5 | 4.4 | 3.3–5.7 |

`classify_warming(T)` / `closest_ssp(T)` label any run in IPCC-comparable terms.

## Where GIM's baseline sits

GIM's "simple policy" baseline run to 2100 (30-agent panel) yields ~2.0 °C warming with CO₂
emissions falling ~28 → ~2 GtCO₂/yr, driven by the model's structural decarbonisation rate.
That places the **default baseline closest to SSP1-2.6** (strong-mitigation), not a
no-additional-policy SSP2-4.5/SSP3-7.0 reference.

This is a finding, not a defect: GIM's baseline embeds optimistic structural decarbonisation.
To produce an IPCC-style *reference* (higher-emission) scenario, the structural decarbonisation
and policy levers must be relaxed — a scenario-driver layer is the natural follow-up
(scenario emissions/decarb presets per SSP). The climate emulator itself is already AR6-consistent
(ECS + TCR), so under any SSP emissions path GIM will track AR6 warming.

## Validation

`tests/test_scenario_alignment.py` (6 tests): ECS == AR6 best; TCR within the AR6 likely range and
within 0.15 °C of 1.8; both flagged consistent in the report; SSP envelopes ordered; warming
classification buckets; GIM baseline (~2.0 °C) closest to SSP1-2.6.

## Follow-up

A per-SSP scenario-driver preset (emissions/decarbonisation paths for SSP1-2.6 / SSP2-4.5 /
SSP3-7.0) so GIM can *run* each named scenario and reproduce its 2100 warming end-to-end
(emission-driven), not only match the emulator constants. Phase-5 item.
