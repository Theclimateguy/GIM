"""THE-64 — grounded lever ontology: each lever measurably moves the deterministic
core, and the base path never drifts from the frozen ensemble member."""

from __future__ import annotations

import pytest

from gim.ensemble import EnsembleConfig, METRICS, _run_member
from gim.runtime import default_state_csv
from gim2 import levers as L


def _config(years: int = 8, max_agents: int = 16) -> EnsembleConfig:
    return EnsembleConfig(
        state_csv=default_state_csv(),
        n_members=1,
        years=years,
        base_year=2026,
        max_agents=max_agents,
        master_seed=2026,
        prior_set="key",
    )


CFG = _config()


def _terminal_l1(a, b) -> float:
    return sum(abs(float(a[-1][k]) - float(b[-1][k])) for k in METRICS)


@pytest.fixture(scope="module")
def base_traj():
    return L.run_member(CFG, L.LeverSelection(), index=0)


# --------------------------------------------------------------------------- #
# honesty guard: empty selection == frozen ensemble member, byte-for-byte
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("index", [0, 1, 2])
def test_base_member_matches_frozen_ensemble(index: int):
    mine = L.run_member(CFG, L.LeverSelection(), index=index)
    frozen = _run_member({"config": CFG, "index": index})
    assert mine == frozen, "v2 baseline member drifted from gim.ensemble._run_member"


# --------------------------------------------------------------------------- #
# every grounded lever produces a non-zero core response
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("lever_id", sorted(L.GROUNDED_LEVERS))
def test_lever_moves_trajectory(lever_id: str, base_traj):
    sel = L.make_selection([lever_id], default_magnitude=1.0, actors=["United States", "China"])
    traj = L.run_member(CFG, sel, index=0)
    delta = _terminal_l1(traj, base_traj)
    assert delta > 0.0, f"lever {lever_id!r} produced no measurable core response"


def test_sign_decarbonization_lowers_co2(base_traj):
    sel = L.make_selection(["decarbonization"], default_magnitude=1.0)
    traj = L.run_member(CFG, sel, index=0)
    assert traj[-1]["co2"] < base_traj[-1]["co2"], "decarbonization should lower terminal CO2"


def test_sign_growth_raises_gdp(base_traj):
    sel = L.make_selection(["growth"], default_magnitude=1.0)
    traj = L.run_member(CFG, sel, index=0)
    assert traj[-1]["world_gdp"] > base_traj[-1]["world_gdp"], "growth lever should raise world GDP"


# --------------------------------------------------------------------------- #
# selection parsing / validation
# --------------------------------------------------------------------------- #


def test_make_selection_parses_and_clamps():
    sel = L.make_selection(["energy_shock", "growth=0.4", {"lever": "stagflation", "magnitude": 5.0}])
    assert sel.magnitudes["energy_shock"] == pytest.approx(L.GROUNDED_LEVERS["energy_shock"].default_magnitude)
    assert sel.magnitudes["growth"] == pytest.approx(0.4)
    assert sel.magnitudes["stagflation"] == pytest.approx(L.MAGNITUDE_MAX)  # clamped


def test_validate_rejects_unknown_and_out_of_band():
    sel = L.LeverSelection(magnitudes={"not_a_lever": 0.5, "growth": 9.0})
    problems = L.validate_selection(sel)
    assert any("not a grounded lever" in p for p in problems)
    assert any("outside band" in p for p in problems)


def test_param_levers_anchored_to_appendix_a():
    # THE-64 calibration: magnitude 1.0 moves a param to its Appendix-A prior edge.
    from gim.core.params import default_params
    from gim.core.priors import all_priors

    base = default_params()
    pri = all_priors()
    decarb = L.apply_param_levers(base, L.make_selection(["decarbonization"], default_magnitude=1.0))
    assert decarb.get("DECARB_RATE_STRUCTURAL") == pytest.approx(pri["DECARB_RATE_STRUCTURAL"].high, rel=2e-3)
    assert decarb.get("EMISSIONS_SCALE") == pytest.approx(pri["EMISSIONS_SCALE"].low, rel=2e-3)
    growth = L.apply_param_levers(base, L.make_selection(["growth"], default_magnitude=1.0))
    assert growth.get("SSP_FORWARD_TFP_DRIFT") == pytest.approx(pri["SSP_FORWARD_TFP_DRIFT"].high, rel=2e-3)
    assert growth.get("TFP_RD_SHARE_SENS") == pytest.approx(pri["TFP_RD_SHARE_SENS"].high, rel=2e-3)


def test_carbon_price_is_hybrid_param_and_pulse():
    # carbon_price applies BOTH a param (decarb) and a pulse (energy price level shift).
    from gim.core.params import default_params

    sel = L.make_selection(["carbon_price"], default_magnitude=1.0)
    out = L.apply_param_levers(default_params(), sel)
    assert out.get("DECARB_RATE_STRUCTURAL") > default_params().get("DECARB_RATE_STRUCTURAL")

    class _W:
        agents = {}
        relations = {}
        class _G: prices = {"energy": 1.0}
        global_state = _G()
    w = _W()
    L.apply_pulses(w, 1, sel, [])
    assert w.global_state.prices["energy"] == pytest.approx(1.0 + L._C_CARBON_ENERGY)


def test_param_levers_compose_onto_params():
    from gim.core.params import default_params

    base = default_params()
    sel = L.make_selection(["decarbonization"], default_magnitude=1.0)
    out = L.apply_param_levers(base, sel)
    assert out.get("DECARB_RATE_STRUCTURAL") > base.get("DECARB_RATE_STRUCTURAL")
    assert out.get("EMISSIONS_SCALE") < base.get("EMISSIONS_SCALE")
