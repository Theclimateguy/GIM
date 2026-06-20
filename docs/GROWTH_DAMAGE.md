# GIM17 Growth-Effect Climate Damage Channel (F4)

The single biggest remaining driver of the "catastrophic spread" in SCC estimates, and the
upside F1 identified vs EPA/RFF, is **growth-effect** damage persistence: temperature affecting
the *growth rate* (Burke et al. 2015; Kotz et al. 2024), not just the output *level*. GIM's
damage was purely level-effect (`1 − 0.006·T²`); F4 adds a switchable growth-effect channel.

## Mechanism

Warming above the 2023 baseline persistently reduces TFP growth (`gim/core/metrics.py`,
`update_tfp_endogenous`):

```
tfp_growth -= GROWTH_DAMAGE_TFP_COEFF · max(0, T − T_2023)
```

Because TFP compounds into the production function each year, this is a true *growth* effect
(permanent path reduction), distinct from the level multiplier. It is **switchable and
default-off**: `GROWTH_DAMAGE_TFP_COEFF = 0.0` reproduces the validated model exactly (golden
backtest unchanged: 1.026 / 1.606 / 0.134).

## What it does (illustrative, coeff = 0.001 / °C)

| metric | level-only (off) | growth-effect on |
|---|---|---|
| 2100 world GDP | 238 tn | 229 tn (−4%) |
| SCC 200 yr @ modern 2% | ~$191 | ~$647 |

The growth-effect channel lets GIM **span the Burke/Kotz upper tail** that a level multiplier
structurally cannot reach — exactly the region driving the divergence across IAMs.

## Calibration status (honest)

`coeff = 0.001/°C` is **illustrative-upper**, not a calibrated central value: combined with 2%
discounting over 200 yr it yields ~$647, above the EPA/RFF central (~$190) and into the
high-tail. The channel's purpose is to **represent the deep growth-effect uncertainty as an
explicit, switchable, uncertainty-bearing term**, not to pick a point. Proper calibration —
fitting `GROWTH_DAMAGE_TFP_COEFF` to the Burke 2015 / Kotz 2024 estimates with a wide prior, and
deciding the default on/off stance for headline runs — is the next F4 step.

## Validation

`tests/test_growth_damage.py` (4 tests): default off; warming lowers TFP growth when enabled;
no drag at/below the 2023 baseline; the enabled channel lowers long-run GDP. Golden backtest
unchanged at the default.

## Remaining F4

Land-use-change CO₂ source (closes the ~10 ppm carbon-cycle gap + the negative CO₂ skill from
F1); full AR6 net non-CO₂ (P4-B2); growth-effect coefficient calibration + prior. These ride
with a climate/economy recalibration.
