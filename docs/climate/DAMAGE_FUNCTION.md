# GIM17 Climate Damage Function — Empirical Cross-Validation (T1.4)

The damage coefficient is the single most consequential and most disputed parameter in any
IAM and the main driver of the wide spread in published Social-Cost-of-Carbon estimates.
T1.4 pins GIM's choice to the world empirical literature so its position is explicit,
auditable, and guarded by a test (`gim/damage_validation.py`, `tests/test_damage_validation.py`).

## GIM's form

A **level-effect** quadratic damage on annual output:

```
output multiplier = 1 - DAMAGE_QUAD_COEFF · T²        (T = warming above pre-industrial)
loss fraction      = DAMAGE_QUAD_COEFF · T²            DAMAGE_QUAD_COEFF = 0.006
```

GIM losses: **2.4% / 5.4% / 9.6% of GDP at +2 / +3 / +4 °C**.

## The empirical spectrum (level-effect, loss = a·T²)

| Study | loss @ +3 °C | coeff a | note |
|---|---|---|---|
| Prior meta-analyses, low end (Howard-Sterner survey) | 1.9% | 0.00211 | envelope floor |
| **DICE-2016R2** (Nordhaus & Moffat 2017) | 2.1% | 0.00236 | widely seen as a lower bound |
| DICE-2013R | 2.4% | 0.00267 | revised down in 2016 |
| **GIM17** | **5.4%** | **0.006** | ~2.5× DICE-2016R2 |
| Howard-Sterner 2017 preferred (non-catastrophic) | 7–8% | 0.0078–0.0089 | meta-analysis central |
| Howard-Sterner 2017 + catastrophic | 9–10% | 0.010–0.011 | |
| Prior meta-analyses, high end | 17.3% | 0.01922 | envelope ceiling |

GIM sits **inside the empirical envelope at every policy-relevant warming**, above DICE
(addressing the common critique that IAMs lowball damages) and below the Howard-Sterner
preferred central estimate. This is the defensible academic position, and the test
`gim_within_envelope()` guards it against future drift.

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
0.0015–0.025) whose upper tail reaches the high-empirical / catastrophic region.

## Calibration stance

The central coefficient is **kept at 0.006** — it is empirically defensible and already more
conservative (higher damage) than DICE. The deliverable of T1.4 is the explicit
cross-validation and the honest representation of the deep uncertainty (the "catastrophic
spread"), not a point change. Closing the residual spread further would require modelling
*growth-effect* persistence — a Phase-5 structural item.

## SCC context

With this damage function, post-recalibration SCC is ~$15 / $45 / $48 per tCO₂ at the
30/100/200-year horizons (see `docs/WELFARE_SCC.md`). The headline value is below the modern
EPA-2023 / RFF-SP central (~$185) chiefly because of (a) the truncated horizon and (b) the
absence of growth-effect persistence — both documented, both Phase-5 extensions, not a
sign of low damages (GIM damage is ~2.5× DICE).

## Validation

`tests/test_damage_validation.py` (7 tests): each level study's coefficient reproduces its
reported %GDP loss at 3 °C; the retracted study is flagged and excluded from the numeric
envelope; GIM is above DICE, below Howard-Sterner preferred, and inside the empirical
envelope at +2/+3/+4 °C.
