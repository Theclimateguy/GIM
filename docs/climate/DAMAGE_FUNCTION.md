# GIM18 Climate Damage Function — Empirical Cross-Validation (T1.4)

The damage coefficient is the single most consequential and most disputed parameter in any
IAM and the main driver of the wide spread in published Social-Cost-of-Carbon estimates.
T1.4 pins GIM's choice to the world empirical literature so its position is explicit,
auditable, and guarded by a test (`gim/damage_validation.py`, `tests/test_damage_validation.py`).

## GIM's form

A **level-effect** quadratic damage on annual output, **normalised to the 2023 baseline** (#17, 2026-07):

```
output multiplier = 1 - DAMAGE_QUAD_COEFF · (T² − T_2023²)   (T = warming above pre-industrial)
DAMAGE_QUAD_COEFF = 0.0078        T_2023 = 1.333 °C
```

> **#17 update (2026-07).** Two corrections: (1) the coefficient was re-anchored `0.006 → 0.0078` to
> the Howard & Sterner (2017) preferred central (~7% GDP at +3 °C above pre-industrial); the issue's
> claim that 0.006 implied "0.6% at 3C" was a miscalculation (`0.006·9 = 5.4%`). (2) The multiplier is
> now **normalised to the 2023 baseline** so the 2023-anchored GDP is not double-counted — damages
> accrue on *incremental* warming, the multiplier is exactly 1.0 at +1.333 °C, and removing the spurious
> base damage **improved** the 2015-2023 backtest GDP RMSE (0.621 → 0.598). The unsupported warming
> **benefit** term is disabled (`DAMAGE_BENEFIT_MAX = 0`). Absolute-T loss (vs pre-industrial, for
> literature comparison): **3.1% / 7.0% / 12.5% at +2 / +3 / +4 °C**.

## The empirical spectrum (level-effect, loss = a·T²)

| Study | loss @ +3 °C | coeff a | note |
|---|---|---|---|
| Prior meta-analyses, low end (Howard-Sterner survey) | 1.9% | 0.00211 | envelope floor |
| **DICE-2016R2** (Nordhaus & Moffat 2017) | 2.1% | 0.00236 | widely seen as a lower bound |
| DICE-2013R | 2.4% | 0.00267 | revised down in 2016 |
| **GIM18** (#17 re-anchor) | **7.0%** | **0.0078** | ~3.3× DICE-2016R2; = Howard-Sterner preferred central (was 5.4% / 0.006 pre-#17) |
| Howard-Sterner 2017 preferred (non-catastrophic) | 7–8% | 0.0078–0.0089 | meta-analysis central |
| Howard-Sterner 2017 + catastrophic | 9–10% | 0.010–0.011 | |
| Prior meta-analyses, high end | 17.3% | 0.01922 | envelope ceiling |

GIM sits **inside the empirical envelope at every policy-relevant warming**, well above DICE
(addressing the common critique that IAMs lowball damages), **at the Howard-Sterner preferred
central** (lower edge of the 7–8% band) and below the incl-catastrophic estimates. This is the
defensible academic position, and the tests (`gim_within_envelope()`,
`test_gim_at_howard_sterner_preferred_above_dice`) guard it against future drift.

## Growth-effect studies (context, not a level coefficient)

Two influential empirical studies estimate temperature effects on the growth *rate*
(persistent, compounding), which a level multiplier cannot represent:

- **Burke, Hsiang & Miguel 2015** (Nature 527:235): ~23% lower global income by 2100 under
  RCP8.5; roughly linear, slightly concave; 2.5–100× prior IAM costs at 2 °C.
- **Kotz, Levermann & Wenz 2024** (Nature 628:551): ~19% committed income reduction by ~2049.
  **This article was retracted** — reported here for context only, never used as a calibration anchor.

Implication: because GIM uses a level-effect multiplier, its damages are likely a
**lower bound** on the growth-effect estimates. This is represented as uncertainty rather
than hidden: the `DAMAGE_QUAD_COEFF` prior is a right-skewed lognormal (median 0.006, range
0.0015–0.025) whose upper tail reaches the high-empirical / catastrophic region. (Note: the
sampling prior in `data/parameter_priors.csv` still centres on the pre-#17 median 0.006, below
the re-anchored central 0.0078 — a known follow-up, left untouched to keep the published SCC
bands stable.)

## Calibration stance

The central coefficient was **re-anchored 0.006 → 0.0078** in the #17 review cycle (2026-07),
to the Howard & Sterner (2017) preferred central — see the update note above. (T1.4's original
stance kept 0.006; its lasting deliverable is the explicit cross-validation and the honest
representation of the deep uncertainty — the "catastrophic spread".) Closing the residual
level-vs-growth spread would require modelling *growth-effect* persistence; the Burke growth
channel is calibrated and switchable (`GROWTH_DAMAGE_TFP_COEFF`, off by default).

## SCC context

With this damage function, the SCC under Nordhaus-style discounting is ~$22 / $43 / $46 per tCO₂
at the 30/100/200-year horizons; under a modern Ramsey scheme (near-zero ρ) the 200-year headline
is ~$90 (range ~$90–280 across economic-core calibrations; see `docs/climate/WELFARE_SCC.md`).
The headline sits below the modern EPA-2023 / RFF-SP central (~$190) chiefly because of (a) the
truncated horizon and (b) the absence of growth-effect persistence — both documented, not a
sign of low damages (GIM damage is ~3.3× DICE).

## Validation

`tests/test_damage_validation.py` (7 tests): each level study's coefficient reproduces its
reported %GDP loss at 3 °C; the retracted study is flagged and excluded from the numeric
envelope; GIM is above DICE, below Howard-Sterner preferred, and inside the empirical
envelope at +2/+3/+4 °C.
