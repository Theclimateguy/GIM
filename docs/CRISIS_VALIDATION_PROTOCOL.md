# CRISIS_VALIDATION_PROTOCOL (GIM16)

## 1. Objective

Validate crisis mechanics beyond aggregate backtest by checking:

- directional validity (sign of effects)
- ordering validity (causal sequence)
- magnitude validity (reasonable range)
- near-miss discipline (low false-positive crisis activation)

## 2. Case structure

Each case file in `tests/crisis_cases/` contains:

- `case_id`, `case_type`, `horizon_years`
- `initial_overrides` (state shock at `t0`)
- `policy_overrides` (optional)
- `expected_signs`
- `expected_order`
- `magnitude_bounds`
- `ablation_targets`

## 3. Evaluation metrics

For each case compute:

\[
\Delta y = y_{t+h} - y_t
\]

and compare:

- sign check: `sign(Delta_model) == expected_sign`
- order check: first passage time of milestones follows `expected_order`
- magnitude check: `lower <= Delta_model <= upper`

Confidence labels:

- `pass`: all three checks pass
- `weak_pass`: sign+order pass, magnitude marginal
- `fail`: sign or order fail

## 4. Near-miss protocol

Near-miss cases are calibrated close to thresholds. A valid model should keep crisis flags inactive unless threshold crossing is material.

Primary near-miss indicators:

- no `debt_crisis_active_years > 0`
- no `fx_crisis_active_years > 0`
- no `regime_crisis_active_years > 0`
- no abrupt collapse in GDP/trust inconsistent with scenario design

## 5. Ablation protocol

For each crisis case run baseline and ablations:

- remove sanctions channel
- remove migration feedback
- remove debt spread feedback
- remove social instability feedback

Interpretation:

- if removal does not change outcome direction or timing, channel is likely non-informative or duplicated
- if removal flips direction unexpectedly, check for hidden coupling/double counting

Implemented in harness:

- for each `ablation_target`, run baseline and channel-off simulation
- report `delta_vs_baseline` for key metrics (`gdp`, `trade_intensity`, `trust_gov`, `social_tension`, `debt_ratio`, `debt_crisis_active_years`, `fx_crisis_active_years`, `credit_risk_score`)

## 6. Minimal run contract for harness

Per run, persist:

- `phase_trace` snapshots
- `detect_cards` and `propagate_cards`
- invariant report
- key trajectories (`gdp`, `public_debt`, `trust_gov`, `social_tension`, `debt_crisis_active_years`, `fx_crisis_active_years`, `credit_risk_score`)

Output table columns:

- `case_id`
- `directional_validity`
- `ordering_validity`
- `magnitude_validity`
- `label`
- `notes`
- `metric_deltas`
- `ablations`

## 7. Baseline run command

Run all crisis cases:

```bash
python3 -m gim.crisis_validation --max-agents 21
```

Default output file:

- `results/crisis_validation/crisis_validation_<timestamp>.json`
