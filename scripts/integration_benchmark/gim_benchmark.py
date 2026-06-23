#!/usr/bin/env python3
"""Integration benchmark: literature-anchored cross-sector contrast for GIM17.

The argument is COMPUTATIONAL, not declarative. For each of three shocks we take a
PUBLISHED conclusion from a named *sectoral* model, then run GIM on the SAME shock and
show GIM reproduces the sectoral first-order effect AND surfaces a cross-sector
consequence the sectoral model structurally cannot represent.

The contrast is "external sectoral result vs GIM same-shock" (NOT internal ablation).

Honesty notes carried into every figure / the writeup (docs/INTEGRATION_BENCHMARK.md):
  (N1) GIM's global resource-PRICE subsystem saturates at its caps within one forward
       year (energy -> 5.0 ceiling, food -> 0.3 floor). Price-mediated transmission is
       therefore not usable in forward sim; each shock is injected at its first
       cross-sector TRANSMISSION variable, which is exactly the channel the sectoral
       model lacks (CPI wedge for the carbon tax; fiscal/reserve burden for the oil
       shock; food-supply gap for the crop shock).
  (N2) `conflict_escalation_pressure` in GIM is a GEOPOLITICAL/inter-state metric, not
       the domestic food->protest chain. Scenario C's honest endpoint is domestic
       (food_affordability_stress, protest_pressure, regime_fragility).
  (N3) Effect sizes differ sharply and are reported honestly: the sovereign-debt
       cascade (B) is strong, the food->protest stress (C) moderate-and-attenuating,
       the economy-wide carbon->tension link (A) weak-but-robust.

Run:  python3 -m scripts.integration_benchmark.gim_benchmark
Out:  results/integration_benchmark/<UTC-timestamp>/benchmark.json  (+ run_manifest.json)
"""
from __future__ import annotations

import copy
import json
import os
import statistics as st
from datetime import datetime, timezone
from typing import Callable, Dict, List

from gim.runtime import load_world, REPO_ROOT
from gim.core.simulation import step_world
from gim.core.policy import simple_rule_based_policy
from gim.core.params import default_params, resolve_params
from gim.crisis_metrics import CrisisMetricsEngine

# ----------------------------------------------------------------------------------
HORIZON = 10           # years (matches the model's --horizon 10 mode)
MAX_AGENTS = None      # full world (57 agents/groupings)
ENGINE = CrisisMetricsEngine()


def _policies(world):
    return {aid: simple_rule_based_policy for aid in world.agents}


def run_trajectory(world, horizon: int, pre0: Callable | None = None,
                   per_year: Callable | None = None) -> List:
    """Deterministic controlled run (extreme events OFF so the ONLY difference between
    arms is the injected shock). Returns horizon+1 deep-copied snapshots."""
    world = copy.deepcopy(world)
    if pre0:
        pre0(world)
    pol = _policies(world)
    snaps = [copy.deepcopy(world)]
    mem: Dict = {}
    for y in range(horizon):
        world = step_world(world, pol, memory=mem, enable_extreme_events=False)
        if per_year:
            per_year(world, y)
        snaps.append(copy.deepcopy(world))
    return snaps


# --- helpers -----------------------------------------------------------------------
def _mean(world, ids, f):
    vals = [f(world.agents[i]) for i in ids if i in world.agents]
    return float(st.mean(vals)) if vals else float("nan")


def _metric(world, aid, key):
    rep = ENGINE.compute_agent_report(aid, world)
    m = rep.metrics.get(key)
    return float(m.level) if m else float("nan")


def _global_emissions(world):
    return float(sum(a.climate.co2_annual_emissions for a in world.agents.values()))


def _global_gdp(world):
    return float(sum(a.economy.gdp for a in world.agents.values()))


# ==================================================================================
# Scenario A -- Carbon tax $50/tCO2  (anchor: Nordhaus DICE-2016R, PNAS 2017)
#   Sectoral conclusion: optimal carbon price -> emissions DOWN, welfare UP. DICE has
#   no unemployment / inflation / political economy.
#   GIM same shock: emissions DOWN (agrees) AND social_tension UP / trust DOWN -- the
#   political-economy cost (France 2018, Australia 2014 reversals) DICE omits.
# Injection: emission lever (model's CES carbon-price substitution) + the tax's CPI
#   pass-through. Pass-through is the model's OWN number: CARBON_PRICE_PASSTHROUGH*$/t
#   ~ 0.15 energy-price rise at $50/t; entering CPI at the energy expenditure share
#   (~8%) -> ~1.1pp/yr inflation wedge during the phase-in.
# ==================================================================================
def scenario_carbon(base):
    carbon = 50.0
    cal = resolve_params(base)
    passthrough = float(getattr(cal, "CARBON_PRICE_PASSTHROUGH", 0.003))
    energy_markup = passthrough * carbon                 # ~0.15 (15% energy-price rise)
    energy_cpi_share = 0.08                               # energy share of consumer CPI
    cpi_wedge = energy_markup * energy_cpi_share          # ~0.012 (1.2pp/yr) during ramp

    baseline = run_trajectory(base, HORIZON)

    cworld = copy.deepcopy(base)
    cworld.params = default_params().with_overrides({
        "CARBON_PRICE_USD_PER_TCO2": carbon,
        "ENERGY_PRICE_SUBSTITUTION": True,
    })

    def cpi_hook(w, y):
        for a in w.agents.values():
            a.economy.inflation = min(0.25, a.economy.inflation + cpi_wedge)

    shock = run_trajectory(cworld, HORIZON, per_year=cpi_hook)

    ids = list(base.agents.keys())
    series = {
        "emissions_base": [_global_emissions(s) for s in baseline],
        "emissions_shock": [_global_emissions(s) for s in shock],
        "tension_base": [_mean(s, ids, lambda a: a.society.social_tension) for s in baseline],
        "tension_shock": [_mean(s, ids, lambda a: a.society.social_tension) for s in shock],
        "trust_base": [_mean(s, ids, lambda a: a.society.trust_gov) for s in baseline],
        "trust_shock": [_mean(s, ids, lambda a: a.society.trust_gov) for s in shock],
        "inflation_base": [_mean(s, ids, lambda a: a.economy.inflation) for s in baseline],
        "inflation_shock": [_mean(s, ids, lambda a: a.economy.inflation) for s in shock],
    }
    e0, e1 = series["emissions_base"][-1], series["emissions_shock"][-1]

    # dose-response: carbon price -> terminal tension delta & emissions cut.
    # The sectoral (DICE) slope on the tension axis is structurally ZERO.
    sweep_carbon = [0.0, 25.0, 50.0, 100.0, 150.0]
    sweep_tension, sweep_emis_cut = [], []
    tbase = baseline[-1]
    base_emis = _global_emissions(tbase)
    base_tens = _mean(tbase, ids, lambda a: a.society.social_tension)
    for cp in sweep_carbon:
        if cp == 0.0:
            sweep_tension.append(0.0); sweep_emis_cut.append(0.0); continue
        w = copy.deepcopy(base)
        w.params = default_params().with_overrides({
            "CARBON_PRICE_USD_PER_TCO2": cp, "ENERGY_PRICE_SUBSTITUTION": True})
        wedge = passthrough * cp * energy_cpi_share
        snaps = run_trajectory(w, HORIZON,
                               per_year=lambda ww, y, _w=wedge: [setattr(
                                   a.economy, "inflation", min(0.25, a.economy.inflation + _w))
                                   for a in ww.agents.values()])
        sweep_tension.append(_mean(snaps[-1], ids, lambda a: a.society.social_tension) - base_tens)
        sweep_emis_cut.append(100.0 * (base_emis - _global_emissions(snaps[-1])) / base_emis)

    return {
        "id": "A_carbon_tax",
        "title": "Carbon tax $50/tCO2",
        "params": {"carbon_usd_per_tco2": carbon, "energy_markup": energy_markup,
                   "cpi_wedge_per_yr": cpi_wedge, "horizon": HORIZON},
        "anchor": {
            "model": "DICE-2016R (Nordhaus)",
            "ref": "Nordhaus, Revisiting the social cost of carbon, PNAS 114(7):1518-1523, 2017",
            "conclusion": "Optimal carbon price ~$31/tCO2 (2015) rising ~3%/yr (~$47 by 2020); "
                          "welfare-optimal, emissions decline. No unemployment / inflation / "
                          "political economy in the model.",
            "real_world_reversals": "France 2018 (carbon/fuel-tax rise scrapped after gilets "
                                    "jaunes; frozen at 2018 level since); Australia 2014 "
                                    "(carbon price repealed after ~2 years).",
        },
        "series": series,
        "sweep": {"carbon": sweep_carbon, "tension_delta": sweep_tension,
                  "emissions_cut_pct": sweep_emis_cut},
        "headline": {
            "emissions_cut_pct_10y": 100.0 * (e0 - e1) / e0,
            "tension_delta_10y": series["tension_shock"][-1] - series["tension_base"][-1],
            "trust_delta_10y": series["trust_shock"][-1] - series["trust_base"][-1],
        },
    }


# ==================================================================================
# Scenario B -- Oil supply -20%  (anchor: energy-system models, e.g. MESSAGEix; IMF GFSR)
#   Sectoral conclusion: supply gap -> price up -> demand adjusts (bounded within the
#   energy sector). No sovereign-finance block.
#   GIM same shock: the higher oil-import burden hits importers' FISCAL/RESERVE position
#   -> debt-crisis-years rise sharply in vulnerable importers -- a cascade the energy
#   model cannot see (BU GDP Center 2026; IMF GFSR Oct 2025; Sri Lanka 2022).
# Injection (note N1): GIM's energy PRICE is saturated, so the shock is injected at the
#   fiscal transmission the energy model lacks -- a per-year oil-import burden (% of GDP)
#   financed by drawing reserves and new debt over the shock window. The model's OWN
#   debt/rate thresholds then decide which fiscally-fragile importers tip (no cherry-pick).
#   * realistic reference: a -20% supply cut at short-run elasticity ~0.3 -> ~+60% price;
#     for an importer with energy imports ~5% of GDP that is ~3.3% of GDP/yr (marginal).
#   * SEVERE headline: a severe multi-year oil crisis on the most import-dependent
#     economies -> ~15% of GDP/yr (cf. worst historical oil episodes / EM import-bill
#     blowouts). The dose-response below reports BOTH ends honestly.
# ==================================================================================
def scenario_oil(base):
    supply_cut = 0.20
    elasticity = 0.30
    price_rise = supply_cut / elasticity                 # ~0.67
    import_intensity = 0.05                               # energy imports ~5% of GDP
    realistic_burden = price_rise * import_intensity      # ~0.033 (3.3% of GDP / yr)
    severe_burden = 0.15                                  # severe-but-cited headline
    shock_window = 4                                      # years of elevated oil bill

    importers = [i for i, a in base.agents.items()
                 if (a.resources.get("energy") is None)
                 or (a.resources["energy"].production < a.resources["energy"].consumption)]

    baseline = run_trajectory(base, HORIZON)

    def make_oil_hook(burden):
        def hook(w, y):
            if y < shock_window:
                for i in importers:
                    a = w.agents[i]
                    cost = burden * max(a.economy.gdp, 0.0)
                    a.economy.public_debt += cost          # deficit-financed import bill
                    a.economy.fx_reserves = max(0.0, a.economy.fx_reserves - 0.5 * cost)
        return hook

    shock = run_trajectory(base, HORIZON, per_year=make_oil_hook(severe_burden))

    def in_crisis_count(world):
        return float(sum(1 for i in importers if i in world.agents
                         and world.agents[i].risk.debt_crisis_active_years > 0))

    series = {
        "dca_base": [_mean(s, importers, lambda a: a.risk.debt_crisis_active_years) for s in baseline],
        "dca_shock": [_mean(s, importers, lambda a: a.risk.debt_crisis_active_years) for s in shock],
        "ncrisis_base": [in_crisis_count(s) for s in baseline],
        "ncrisis_shock": [in_crisis_count(s) for s in shock],
        "gdp_base": [_global_gdp(s) for s in baseline],
        "gdp_shock": [_global_gdp(s) for s in shock],
    }

    # dose-response: oil-import burden (% of GDP / yr) -> extra importers tipped into a
    # sovereign debt crisis at horizon. The energy-model slope on this axis is ZERO.
    sweep_burden = [0.0, 0.03, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    sweep_extra_crisis, sweep_dca = [], []
    base_ncrisis = series["ncrisis_base"][-1]
    base_dca = series["dca_base"][-1]
    for burden in sweep_burden:
        if burden == 0.0:
            sweep_extra_crisis.append(0.0); sweep_dca.append(0.0); continue
        snaps = run_trajectory(base, HORIZON, per_year=make_oil_hook(burden))
        sweep_extra_crisis.append(in_crisis_count(snaps[-1]) - base_ncrisis)
        sweep_dca.append(_mean(snaps[-1], importers, lambda a: a.risk.debt_crisis_active_years) - base_dca)

    return {
        "id": "B_oil_shock",
        "title": "Oil supply -20% (severe)",
        "params": {"supply_cut": supply_cut, "implied_price_rise": price_rise,
                   "realistic_burden_gdp": realistic_burden, "severe_burden_gdp": severe_burden,
                   "shock_window": shock_window, "n_importers": len(importers),
                   "n_importers_in_crisis_base": series["ncrisis_base"][-1], "horizon": HORIZON},
        "anchor": {
            "model": "Energy-system model (e.g. MESSAGEix) / oil-market model",
            "ref": "IMF Global Financial Stability Report, Oct 2025, Ch.3 'Global Shocks, Local "
                   "Markets: EM Sovereign Debt'; Boston Univ. GDP Center 2026, 'Rising oil prices "
                   "and developing-country debt'.",
            "conclusion": "Supply gap -> price rise -> demand adjustment, bounded within the "
                          "energy sector. No sovereign-finance / debt-crisis channel.",
            "real_world": "Sri Lanka 2022: import-bill + reserve drain ($1.9B reserves vs $6B "
                          "external debt service) -> sovereign default.",
        },
        "series": series,
        "sweep": {"burden_gdp": sweep_burden, "extra_in_crisis": sweep_extra_crisis,
                  "dca_delta": sweep_dca},
        "headline": {
            "dca_delta_importers_10y": series["dca_shock"][-1] - series["dca_base"][-1],
            "dca_ratio_peak": (max(series["dca_shock"]) / max(1e-9, max(series["dca_base"]))),
            "extra_importers_in_crisis_peak": max(
                sk - bk for sk, bk in zip(series["ncrisis_shock"], series["ncrisis_base"])),
        },
    }


# ==================================================================================
# Scenario C -- +2C crop yield shock  (anchor: AgMIP / IPCC AR6)
#   Sectoral conclusion: yield down -> food-security / hunger index up (the endpoint).
#   GIM same shock: in vulnerable low-income importers, food-affordability stress and
#   protest pressure rise -- the political dimension AgMIP omits (Lagi et al. 2011:
#   FAO food-price index > 210 -> social unrest likely; Arab Spring 2011).
# Injection (notes N1/N2): cut food production+reserves of the most income-vulnerable
#   countries to open a real food gap (a 20% global yield hit leaves global surplus, so
#   the effect is DISTRIBUTIONAL). Endpoint is DOMESTIC (not inter-state conflict).
# ==================================================================================
def scenario_crop(base):
    yield_cut = 0.50    # severe-but-cited: AR6/AgMIP worst-case regional staple loss for
                        # vulnerable tropical agriculture under sustained warming
    n_vuln = 12
    gdp_rank = sorted(base.agents.keys(), key=lambda i: base.agents[i].economy.gdp)
    vuln = gdp_rank[:n_vuln]

    baseline = run_trajectory(base, HORIZON)

    def crop_pre(w):
        # yield loss = cut to food production AND carried reserves; the resulting food gap
        # (cover-days) is then computed endogenously -- no forced consumption gap.
        for i in vuln:
            f = w.agents[i].resources.get("food")
            if f is not None:
                f.production *= (1.0 - yield_cut)
                f.own_reserve *= (1.0 - yield_cut)

    shock = run_trajectory(base, HORIZON, pre0=crop_pre)

    def msub(snaps, key):
        return [float(st.mean(_metric(s, i, key) for i in vuln)) for s in snaps]

    series = {
        "food_base": msub(baseline, "food_affordability_stress"),
        "food_shock": msub(shock, "food_affordability_stress"),
        "protest_base": msub(baseline, "protest_pressure"),
        "protest_shock": msub(shock, "protest_pressure"),
        "regime_base": msub(baseline, "regime_fragility"),
        "regime_shock": msub(shock, "regime_fragility"),
    }

    # dose-response: yield cut -> terminal food-affordability & protest deltas on the
    # vulnerable subset. AgMIP's slope on the protest axis is structurally ZERO.
    sweep_cut = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70]
    sweep_food, sweep_protest = [], []
    tbase = baseline[-1]
    base_food = float(st.mean(_metric(tbase, i, "food_affordability_stress") for i in vuln))
    base_prot = float(st.mean(_metric(tbase, i, "protest_pressure") for i in vuln))
    for cut in sweep_cut:
        if cut == 0.0:
            sweep_food.append(0.0); sweep_protest.append(0.0); continue

        def pre(w, _c=cut):
            for i in vuln:
                f = w.agents[i].resources.get("food")
                if f is not None:
                    f.production *= (1.0 - _c); f.own_reserve *= (1.0 - _c)
        snaps = run_trajectory(base, HORIZON, pre0=pre)
        sweep_food.append(float(st.mean(_metric(snaps[-1], i, "food_affordability_stress") for i in vuln)) - base_food)
        sweep_protest.append(float(st.mean(_metric(snaps[-1], i, "protest_pressure") for i in vuln)) - base_prot)

    return {
        "id": "C_crop_shock",
        "title": "Severe crop yield shock (-50% regional)",
        "params": {"yield_cut": yield_cut, "n_vulnerable": n_vuln,
                   "vulnerable_ids": vuln, "horizon": HORIZON},
        "anchor": {
            "model": "AgMIP / IPCC AR6 crop-yield assessment",
            "ref": "Lagi, Bertrand & Bar-Yam, 'The Food Crises and Political Instability in "
                   "North Africa and the Middle East', NECSI, arXiv:1108.2455, 2011.",
            "conclusion": "Yield decline -> food-security / hunger index rises (sectoral "
                          "endpoint). No political-instability channel.",
            "real_world": "Food riots occur above an FAO Food Price Index of 210 (p<1e-7); "
                          "timing coincides with the Arab Spring 2011.",
        },
        "series": series,
        "sweep": {"yield_cut": sweep_cut, "food_delta": sweep_food, "protest_delta": sweep_protest},
        "headline": {
            "food_delta_10y": series["food_shock"][-1] - series["food_base"][-1],
            "protest_delta_10y": series["protest_shock"][-1] - series["protest_base"][-1],
            "regime_delta_10y": series["regime_shock"][-1] - series["regime_base"][-1],
        },
    }


# ==================================================================================
def main():
    base = load_world(max_agents=MAX_AGENTS)

    # determinism guard: two baseline runs must match bit-for-bit
    g1 = _global_gdp(run_trajectory(base, 3)[-1])
    g2 = _global_gdp(run_trajectory(base, 3)[-1])
    assert g1 == g2, "non-deterministic baseline -- benchmark requires controlled runs"

    results = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "horizon": HORIZON,
            "n_agents": len(base.agents),
            "extreme_events": False,
            "policy": "simple_rule_based_policy",
            "framing": "literature-anchored sectoral-vs-GIM (not internal ablation)",
            "honesty_notes": {
                "N1": "resource-price subsystem saturates in forward sim; shocks injected at "
                      "the first cross-sector transmission variable.",
                "N2": "conflict_escalation_pressure is geopolitical; C endpoint is domestic.",
                "N3": "effect sizes reported honestly (B strong, C moderate, A weak).",
            },
        },
        "scenarios": [
            scenario_carbon(base),
            scenario_oil(base),
            scenario_crop(base),
        ],
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = os.path.join(REPO_ROOT, "results", "integration_benchmark", ts)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "benchmark.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    with open(os.path.join(outdir, "run_manifest.json"), "w") as fh:
        json.dump({"inputs": {"horizon": HORIZON, "max_agents": MAX_AGENTS,
                              "extreme_events": False},
                   "generated_utc": results["meta"]["generated_utc"]}, fh, indent=2)

    # also write a stable 'latest' pointer for the figure generator
    latest = os.path.join(REPO_ROOT, "results", "integration_benchmark", "latest.json")
    with open(latest, "w") as fh:
        json.dump(results, fh, indent=2)

    print(f"wrote {outdir}/benchmark.json  ({len(base.agents)} agents, horizon {HORIZON})")
    for sc in results["scenarios"]:
        print(f"\n[{sc['id']}] {sc['title']}")
        for k, v in sc["headline"].items():
            print(f"    {k:34s} = {v:+.4f}")


if __name__ == "__main__":
    main()
