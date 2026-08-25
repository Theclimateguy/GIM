#!/usr/bin/env python3
"""El Niño 2026–27: base-vs-scenario ensemble on the GIM19 core.

Follows the gim2 substantive-quantity rule: everything reported is a paired
DELTA (scenario − baseline) over the SAME member seeds, as an ensemble fan.
No absolute point forecasts.

Scenario construction (an El Niño-specific pulse, not the generic food/energy
lever). Magnitude m = 1.0 is anchored to a *very strong* event (ONI >= +2.0 degC):

  supply, regional (physical channel)
    tier 1  monsoon/drought core  -6% * m food output
            AUS IND IDN THA PHL MYS VNM ZAF + S.Asia/E.Asia/Oceania/Global-S aggregates
            (28.4% of world food production in the compiled state)
    tier 2  mixed / partial       -3% * m food output
            BRA COL PAK BGD NGA EGY + S.America/Middle-East aggregates (11.2%)
    tier 3  wet-side beneficiaries +1% * m food output
            ARG CHL USA (8.7%)
    => world food supply -2.0% * m; MARKET_CLEARING (eps=0.4) turns that into
       roughly +5% * m on the food price endogenously.
    hydro  -2% * m energy output in the hydro-exposed set (17.4% of world
           energy production) => -0.35% * m world energy supply.

  policy / expectation impulse (what the physical channel does NOT contain)
    food price  +3% * m   export bans, precautionary stockpiling (India rice 2023-24)
    energy price +4% * m  LNG/coal scramble as hydro fails and cooling demand peaks

  Combined the two channels land near the empirical El Niño elasticities:
  Cashin/Mohaddes/Raissi (IMF WP/15/89) +5.3% non-fuel commodities and +13.9%
  oil after 4 quarters for a 1 s.d. shock; World Bank Oct-2026 food-index risk.

  Timing profile (annual core, event peaks Q4-2026 - Q1-2027):
    2026 x0.40,  2027 x1.00,  2028 x0.35 (carryover / restocking)

Runs:
  base          no pulse
  elnino_strong m = 0.5   (strong event, ONI ~ +1.5)
  elnino_vstrong m = 1.0  (very strong, ONI >= +2.0)
  elnino_hormuz m = 1.0 + a concurrent energy-supply shock (Hormuz)

Usage:  python3 scripts/run_elnino_2026.py --members 200 --years 10
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gim.core.params import default_params  # noqa: E402
from gim.core.policy import make_policy_map  # noqa: E402
from gim.core.priors import all_priors, key_priors, sample_parameter_set  # noqa: E402
from gim.core.resources import normalize_resource_scales_forward  # noqa: E402
from gim.core.rng import seed_world  # noqa: E402
from gim.core.simulation import step_world  # noqa: E402
from gim.core.world_factory import make_world_from_csv  # noqa: E402
from gim.ensemble import EnsembleConfig, _member_seed  # noqa: E402

BASE_YEAR = 2023
STATE_CSV = str(ROOT / "data" / "agent_states_operational.csv")

# --------------------------------------------------------------------------- #
# El Nino exposure map
# --------------------------------------------------------------------------- #

FOOD_TIER1 = ("AUS", "IND", "IDN", "THA", "PHL", "MYS", "VNM", "ZAF",
              "AG_SOUTH_AS", "AG_EAST_ASI", "AG_OCEANIA", "AG_GLOBAL_S")
FOOD_TIER2 = ("BRA", "COL", "PAK", "BGD", "NGA", "EGY",
              "AG_SOUTH_AM", "AG_MIDDLE_E")
FOOD_TIER3 = ("ARG", "CHL", "USA")
HYDRO_SET = ("BRA", "COL", "CHL", "IND", "VNM", "ZAF",
             "AG_SOUTH_AM", "AG_SOUTH_AS", "AG_EAST_ASI", "AG_GLOBAL_S")

C_FOOD_T1, C_FOOD_T2, C_FOOD_T3 = -0.060, -0.030, +0.010
C_HYDRO = -0.020
C_FOOD_PRICE, C_ENERGY_PRICE = 0.030, 0.040

# calendar year -> share of the full impulse
PROFILE = {2026: 0.40, 2027: 1.00, 2028: 0.35}

# Hormuz overlay: sustained energy supply/price shock on top (2026-2027).
HORMUZ_PRICE, HORMUZ_PROD = 0.12, -0.03
HORMUZ_PROFILE = {2026: 1.0, 2027: 1.0, 2028: 0.4}

# Food-importer stress set (net importers where a food-price shock bites hardest).
IMPORTER_SET = ("EGY", "NGA", "PAK", "BGD", "PHL", "IDN", "TUR", "IRQ",
                "AG_MIDDLE_E", "AG_GLOBAL_S", "AG_SOUTH_AS")

# --------------------------------------------------------------------------- #
# EXTENSION (not part of the validated core): world food price -> domestic CPI.
#
# gim.core.labor_market.update_inflation_unemployment builds cost-push from the
# ENERGY price change only — there is no food term in the Phillips curve. So the
# core cannot answer "food prices -> imported inflation -> policy rate", which is
# the main channel the analytical note claims for Russia. This overlay adds it
# EXOGENOUSLY, after the step, and is reported separately from the headline runs.
#
#   dpi_i = PASSTHROUGH * food_share_i * dlog(p_food)
#
# food_share_i: food share of the consumption basket (ILO/WB CPI weights;
#   ~0.13 advanced, ~0.30 middle-income, ~0.45 low-income).
# PASSTHROUGH: world -> domestic food CPI pass-through over a year, ~0.25
#   for EMs (IMF, Furceri et al. 2016 on global food-price pass-through).
FOOD_CPI_PASSTHROUGH = 0.25
FOOD_SHARE_HIGH = ("NGA", "PAK", "BGD", "EGY", "IND", "PHL", "VNM", "IRQ",
                   "AG_GLOBAL_S", "AG_SOUTH_AS", "AG_MIDDLE_E")   # 0.45
FOOD_SHARE_MID = ("IDN", "THA", "BRA", "MEX", "COL", "ZAF", "TUR", "RUS", "CHN",
                  "MYS", "IRN", "ARG", "ROU", "AG_SOUTH_AM", "AG_EAST_ASI")  # 0.30
FOOD_SHARE_DEFAULT = 0.13


def _food_share(aid: str) -> float:
    if aid in FOOD_SHARE_HIGH:
        return 0.45
    if aid in FOOD_SHARE_MID:
        return 0.30
    return FOOD_SHARE_DEFAULT


def apply_food_cpi(world, enabled: bool) -> None:
    """Add the food leg of cost-push to each agent's inflation (see note above)."""
    if not enabled:
        return
    prices = world.global_state.prices
    now = max(1e-9, float(prices.get("food", 1.0)))
    prev = getattr(world.global_state, "_elnino_food_price_prev", None)
    world.global_state._elnino_food_price_prev = now
    if prev is None or prev <= 0.0:
        return
    change = (now - prev) / prev
    if change == 0.0:
        return
    params = world.params if getattr(world, "params", None) else None
    lo = float(params.get("INFLATION_MIN", -0.02)) if params else -0.02
    hi = float(params.get("INFLATION_MAX", 0.30)) if params else 0.30
    for aid, agent in world.agents.items():
        d = FOOD_CPI_PASSTHROUGH * _food_share(aid) * change
        agent.economy.inflation = max(lo, min(hi, agent.economy.inflation + d))


# Per-actor readout (the aggregate washes out exactly the distribution that matters).
FOCUS = ("IND", "IDN", "BRA", "AUS", "ZAF", "EGY", "NGA", "PAK",
         "THA", "ARG", "USA", "CHN", "RUS", "DEU", "FRA", "ITA", "ESP", "GBR")

# --------------------------------------------------------------------------- #
# Transient global-temperature bump.
#
# GIM's global temperature is CO2-driven: an ENSO event redistributes ocean heat
# but does not change forcing, so the El Nino runs above leave `temperature_global`
# untouched. The observed +0.1..+0.2 degC that a strong event adds to the peak
# year therefore has to be injected by hand if we want to ask what the model's
# damage channel does with it. Reported as a separate, clearly-labelled run.
TEMP_BUMP_PROFILE = {2027: 1.0, 2028: 0.33}
TEMP_BUMP_C = 0.15


def apply_temp_bump(world, calendar_year: int, m: float) -> None:
    if m <= 0.0:
        return
    if calendar_year not in TEMP_BUMP_PROFILE and (calendar_year - 1) not in TEMP_BUMP_PROFILE:
        return
    now = TEMP_BUMP_C * m * TEMP_BUMP_PROFILE.get(calendar_year, 0.0)
    prev = TEMP_BUMP_C * m * TEMP_BUMP_PROFILE.get(calendar_year - 1, 0.0)
    world.global_state.temperature_global += (now - prev)


def _scale_resource(world, aid: str, name: str, factor: float) -> None:
    """Scale an agent's resource output by ``factor``.

    Both ``production`` (this year's market supply) AND the carried
    ``_primary_production`` must move: update_resource_stocks takes the carried
    primary output as NEXT year's desired base, so touching ``production`` alone
    is silently reverted on the following step.
    """
    agent = world.agents.get(aid)
    res = agent.resources.get(name) if agent else None
    if res is None:
        return
    res.production = max(0.0, res.production * factor)
    prev = getattr(res, "_primary_production", None)
    if prev is not None:
        res._primary_production = max(0.0, prev * factor)


def _level(profile: dict, coeff: float, year: int, m: float) -> float:
    """Shock LEVEL vs baseline for ``year`` (1.0 == no shock)."""
    return 1.0 + coeff * m * profile.get(year, 0.0)


def _increment(profile: dict, coeff: float, year: int, m: float) -> float:
    """Per-year multiplicative STEP that walks the level path, so the state
    follows the profile and returns to the baseline path once it ends."""
    now = _level(profile, coeff, year, m)
    prev = _level(profile, coeff, year - 1, m)
    return now / prev if prev > 0 else 1.0


def apply_elnino(world, calendar_year: int, m: float) -> None:
    if m <= 0.0:
        return
    if calendar_year not in PROFILE and (calendar_year - 1) not in PROFILE:
        return
    for ids, coeff in ((FOOD_TIER1, C_FOOD_T1), (FOOD_TIER2, C_FOOD_T2),
                       (FOOD_TIER3, C_FOOD_T3)):
        f = _increment(PROFILE, coeff, calendar_year, m)
        if f != 1.0:
            for aid in ids:
                _scale_resource(world, aid, "food", f)
    f = _increment(PROFILE, C_HYDRO, calendar_year, m)
    if f != 1.0:
        for aid in HYDRO_SET:
            _scale_resource(world, aid, "energy", f)
    prices = world.global_state.prices
    prices["food"] = prices.get("food", 1.0) * _increment(PROFILE, C_FOOD_PRICE, calendar_year, m)
    prices["energy"] = prices.get("energy", 1.0) * _increment(PROFILE, C_ENERGY_PRICE, calendar_year, m)


def apply_hormuz(world, calendar_year: int, m: float) -> None:
    if m <= 0.0:
        return
    if calendar_year not in HORMUZ_PROFILE and (calendar_year - 1) not in HORMUZ_PROFILE:
        return
    prices = world.global_state.prices
    prices["energy"] = prices.get("energy", 1.0) * _increment(
        HORMUZ_PROFILE, HORMUZ_PRICE, calendar_year, m)
    f = _increment(HORMUZ_PROFILE, HORMUZ_PROD, calendar_year, m)
    if f != 1.0:
        for aid in list(world.agents):
            _scale_resource(world, aid, "energy", f)


# --------------------------------------------------------------------------- #
# collector
# --------------------------------------------------------------------------- #

def collect(world) -> dict:
    agents = world.agents
    gs = world.global_state
    gdp_tot = sum(a.economy.gdp for a in agents.values())
    infl = sum(a.economy.inflation * a.economy.gdp for a in agents.values()) / max(gdp_tot, 1e-9)
    unemp = sum(a.economy.unemployment * a.economy.gdp for a in agents.values()) / max(gdp_tot, 1e-9)
    tens = [a.society.social_tension for a in agents.values()]
    imp = [agents[i].society.social_tension for i in IMPORTER_SET if i in agents]
    imp_gdp = sum(agents[i].economy.gdp for i in IMPORTER_SET if i in agents)
    out = {}
    for aid in FOCUS:
        a = agents.get(aid)
        if a is None:
            continue
        out[f"gdp_{aid}"] = a.economy.gdp
        out[f"tension_{aid}"] = a.society.social_tension
        out[f"infl_{aid}"] = a.economy.inflation
        out[f"pop_{aid}"] = a.economy.population
    rus = agents.get("RUS")
    out.update({
        "food_supply": sum(a.resources["food"].production for a in agents.values()
                           if "food" in a.resources),
        "food_demand": sum(a.resources["food"].consumption for a in agents.values()
                           if "food" in a.resources),
        "energy_supply": sum(a.resources["energy"].production for a in agents.values()
                             if "energy" in a.resources),
        "world_gdp": gdp_tot,
        "food_price": gs.prices.get("food", 1.0),
        "energy_price": gs.prices.get("energy", 1.0),
        "world_inflation": infl,
        "world_unemployment": unemp,
        "mean_social_tension": sum(tens) / max(len(tens), 1),
        "importer_social_tension": sum(imp) / max(len(imp), 1),
        "importer_gdp": imp_gdp,
        "n_debt_crises": float(sum(1 for a in agents.values()
                                   if getattr(a.risk, "debt_crisis_active_years", 0) > 0)),
        "n_regime_crises": float(sum(1 for a in agents.values()
                                     if getattr(a.risk, "regime_crisis_active_years", 0) > 0)),
        "temperature": gs.temperature_global,
        "rus_gdp": rus.economy.gdp if rus else float("nan"),
        "rus_inflation": rus.economy.inflation if rus else float("nan"),
        "rus_tension": rus.society.social_tension if rus else float("nan"),
    })
    return out


def run_member(config: EnsembleConfig, index: int, m_elnino: float, m_hormuz: float,
               food_cpi: bool = False, m_temp: float = 0.0) -> list:
    seed = _member_seed(config.master_seed, index)
    priors = key_priors() if config.prior_set == "key" else all_priors()
    sampled = sample_parameter_set(default_params(), priors, random.Random(seed))
    world = make_world_from_csv(config.state_csv, max_agents=config.max_agents,
                                base_year=config.base_year)
    world.params = sampled
    seed_world(world, seed)
    normalize_resource_scales_forward(world)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    traj = [collect(world)]
    for t in range(1, config.years + 1):
        step_world(world, policies)
        year = config.base_year + t
        apply_elnino(world, year, m_elnino)
        apply_hormuz(world, year, m_hormuz)
        apply_temp_bump(world, year, m_temp)
        apply_food_cpi(world, food_cpi)
        traj.append(collect(world))
    return traj


# --------------------------------------------------------------------------- #

RUNS = (
    # name,                 m_elnino, m_hormuz, food->CPI overlay
    ("base",                     0.0, 0.0, False),
    ("elnino_strong",            0.5, 0.0, False),   # strong, ONI ~ +1.5
    ("elnino_vstrong",           1.0, 0.0, False),   # very strong, ONI >= +2.0
    ("elnino_historic",         1.25, 0.0, False),   # tail: RONI +2.5..+3.0 (NOAA 13.08.2026)
    ("hormuz_only",              0.0, 1.0, False),   # the geopolitical leg on its own
    ("elnino_hormuz",            1.0, 1.0, False),   # compound: is it super-additive?
    ("temp_bump_only",           0.0, 0.0, False, 1.0),   # +0.15 degC transient, no El Nino
    ("elnino_temp",              1.0, 0.0, False, 1.0),   # El Nino + its thermal increment
    ("full_stack",               1.0, 1.0, False, 1.0),  # El Nino + Hormuz + thermal increment
    ("base_foodcpi",             0.0, 0.0, True),
    ("elnino_vstrong_foodcpi",   1.0, 0.0, True),
    ("elnino_hormuz_foodcpi",    1.0, 1.0, True),
    ("full_stack_foodcpi",       1.0, 1.0, True, 1.0),
)
# every scenario is differenced against a baseline run under the SAME overlay setting
BASELINE_OF = {"elnino_strong": "base", "elnino_vstrong": "base",
               "elnino_historic": "base", "hormuz_only": "base", "elnino_hormuz": "base",
               "temp_bump_only": "base", "elnino_temp": "base",
               "full_stack": "base",
               "elnino_vstrong_foodcpi": "base_foodcpi",
               "elnino_hormuz_foodcpi": "base_foodcpi",
               "full_stack_foodcpi": "base_foodcpi"}

FIELDS = (
    "food_supply", "food_demand", "energy_supply",
    "world_gdp", "food_price", "energy_price", "world_inflation", "world_unemployment",
    "mean_social_tension", "importer_social_tension", "importer_gdp",
    "n_debt_crises", "n_regime_crises", "temperature",
    "rus_gdp", "rus_inflation", "rus_tension",
) + tuple(f"{pre}_{aid}" for aid in FOCUS
        for pre in ("gdp", "tension", "infl", "pop"))


def pct(values, p):
    vs = sorted(values)
    if not vs:
        return float("nan")
    k = (len(vs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vs) - 1)
    return vs[lo] + (vs[hi] - vs[lo]) * (k - lo)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", type=int, default=200)
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "results" / "elnino2026"))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    config = EnsembleConfig(state_csv=STATE_CSV, n_members=args.members, years=args.years,
                            base_year=BASE_YEAR, max_agents=57, master_seed=args.seed,
                            prior_set="key", n_jobs=args.jobs)

    import multiprocessing as mp
    n_jobs = args.jobs or (mp.cpu_count() or 1)

    all_traj = {}
    for spec in RUNS:
        name, m_en, m_hz, fcpi = spec[:4]
        m_t = spec[4] if len(spec) > 4 else 0.0
        tasks = [(config, i, m_en, m_hz, fcpi, m_t) for i in range(args.members)]
        if n_jobs <= 1:
            res = [run_member(*t) for t in tasks]
        else:
            with mp.Pool(n_jobs) as pool:
                res = pool.starmap(run_member, tasks)
        all_traj[name] = res
        print(f"[ok] {name}: {len(res)} members")

    years = [BASE_YEAR + t for t in range(args.years + 1)]
    rows = []
    for name in (r[0] for r in RUNS):
        for yi, year in enumerate(years):
            for f in FIELDS:
                vals = [tr[yi][f] for tr in all_traj[name]]
                row = {"run": name, "year": year, "metric": f,
                       "p5": pct(vals, 5), "p25": pct(vals, 25), "p50": median(vals),
                       "p75": pct(vals, 75), "p95": pct(vals, 95)}
                ref = BASELINE_OF.get(name)
                if ref:
                    if (f.startswith("n_") or "tension" in f or f.startswith("infl_")
                            or f in ("world_inflation",
                                       "world_unemployment", "rus_inflation", "temperature")):
                        d = [tr[yi][f] - b[yi][f] for tr, b in zip(all_traj[name], all_traj[ref])]
                        row["delta_kind"] = "abs"
                    else:
                        d = [tr[yi][f] / b[yi][f] - 1.0 for tr, b in
                             zip(all_traj[name], all_traj[ref]) if b[yi][f] != 0]
                        row["delta_kind"] = "rel"
                    row.update({"d_p5": pct(d, 5), "d_p25": pct(d, 25), "d_p50": median(d),
                                "d_p75": pct(d, 75), "d_p95": pct(d, 95),
                                "share_negative": sum(1 for x in d if x < 0) / max(len(d), 1)})
                rows.append(row)

    keys = ["run", "year", "metric", "p5", "p25", "p50", "p75", "p95",
            "delta_kind", "d_p5", "d_p25", "d_p50", "d_p75", "d_p95", "share_negative"]
    with open(out / "fans.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})

    meta = {
        "members": args.members, "years": args.years, "seed": args.seed,
        "base_year": BASE_YEAR, "state_csv": STATE_CSV,
        "runs": {r[0]: {"m_elnino": r[1], "m_hormuz": r[2], "food_cpi_overlay": r[3],
                        "m_temp_bump": r[4] if len(r) > 4 else 0.0} for r in RUNS},
        "temp_bump_c": TEMP_BUMP_C,
        "baseline_of": BASELINE_OF,
        "food_cpi_passthrough": FOOD_CPI_PASSTHROUGH,
        "profile": PROFILE,
        "coefficients": {"food_tier1": C_FOOD_T1, "food_tier2": C_FOOD_T2,
                         "food_tier3": C_FOOD_T3, "hydro": C_HYDRO,
                         "food_price_impulse": C_FOOD_PRICE,
                         "energy_price_impulse": C_ENERGY_PRICE,
                         "hormuz_price": HORMUZ_PRICE, "hormuz_prod": HORMUZ_PROD},
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"saved {out/'fans.csv'} ({len(rows)} rows) + meta.json")


if __name__ == "__main__":
    main()
