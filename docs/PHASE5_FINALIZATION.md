# GIM17 Phase 5 — Finalization Status (honest)

Phase 5 ("finalize the model across all dimensions to modern standards; the paper is a separate
deferred artifact"). This is an accurate accounting of what is delivered vs what genuinely
remains — no item is marked done unless it is validated and committed.

## Delivered & validated (building blocks)

| Track | Deliverable | Validation | Default |
|---|---|---|---|
| **F1** objectivity | SCC vs modern benchmarks at comparable discounting; skill-vs-naive | GIM SCC at 2% Ramsey = ~$191 ≈ EPA-2023 $190 / RFF-SP $185; skill: temp +0.15, GDP +0.09, CO₂ −0.17 | n/a (diagnostic) |
| **F3** unique-layer audit | influence audit; external metric map; CINC for `military_power` | 7/8 Hofstede dims empirically inert; CINC reproduces CoW ranking (China 0.205, US 0.147, India 0.096) | tools; CINC not auto-wired |
| **F4** damages | growth-effect TFP-drag channel + literature prior | coeff→SCC map ($184→$314→$490 at 2% / 200y); prior spans Burke/Kotz | **off** (golden-preserving) |
| **F5** criticality | early-warning primitives (Scheffer); fat-tailed crisis severity (Richardson) | EWS discriminates synthetic bifurcation; severity mean 0.997, p99 4.2× | **off** (golden-preserving) |

All blocks ship with tests and docs; the 2015–2023 golden backtest stays at 1.026/1.606/0.134
throughout (every behaviour-changing channel is default-off / switchable).

## What "production finalization" still requires

The validated channels above are **switchable and default-off** so they never silently broke the
validated calibration. Turning them on for headline runs is a **single joint decision**: activating
{growth-effect damages, fat-tailed crisis severity, CINC-grounded military_power, any wired culture
links} together and **re-anchoring the golden/calibration** to the new dynamics. That joint
recalibration (analogous to T1.3b for climate) is the remaining production step — deliberately left
as one explicit decision rather than a drift of silent default changes.

## Genuinely remaining (each a dedicated effort)

- **F2 — economics depth (largest):** nested-CES (KLE) production with energy-capital substitution;
  stock-flow-consistent private finance/money on the T1.1 base; forward-looking expectations;
  optional partial market clearing. A real refactor that re-anchors the golden backtest.
- **F4 — land-use CO₂** source (closes the ~10 ppm carbon-cycle gap + the negative CO₂ skill) and
  the **full AR6 net non-CO₂** (P4-B2): both require a climate recalibration.
- **F3 — external-data validation:** WGI/SWIID initial-state anchoring and a **UCDP conflict
  backtest** with skill-vs-base-rate (needs the external datasets ingested); wire-or-remove
  decision on the 7 inert Hofstede dims.
- **F5 — war severity + cascades:** war cost in GIM is diffuse (no single war-size variable), so a
  Richardson-power-law on war severity needs an explicit war-size term first; plus the SOC
  cascade/contagion generalisation and an ensemble-based live early-warning monitor.
- **Cross-cutting:** a DICE reproduction as a regression sanity-check; skill-vs-naive reported in CI.

## Honest summary

The **methodological foundation** of every dimension is now in place, validated against modern
references (AR6/FAIR, EPA/RFF-SP, PWT/Gollin, CoW-CINC, Richardson/Scheffer) rather than the dated
DICE/RICE. The remaining work is **integration and calibration** (activate + recalibrate) and
**external-data validation** of the unique social-geopolitical layers — which, as documented, can be
grounded on inputs now but will never reach AR6-grade predictive identifiability, so the honest bar
there is skill-vs-base-rate, not point precision.
