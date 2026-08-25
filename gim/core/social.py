import math
from typing import Dict

from . import calibration_params as cal
from .params import resolve_params
from .critical_pending import get_transition_pending, record_debt_flow
from .core import Action, AgentState, WorldState, clamp01, effective_trade_intensity
from .economy import compute_effective_interest_rate
from .geo_coupling import adjacency as _geo_adjacency
from .rng import get_rng
from ..criticality import powerlaw_severity


def _crisis_severity(world: WorldState, cal_ns) -> float:
    """Fat-tailed (power-law) crisis-severity multiplier (F5); 1.0 when disabled (default)."""
    if not getattr(cal_ns, "CRISIS_SEVERITY_POWERLAW", False):
        return 1.0
    return powerlaw_severity(
        get_rng(world),
        alpha=getattr(cal_ns, "CRISIS_SEVERITY_ALPHA", 1.5),
        a=1.0,
        b=getattr(cal_ns, "CRISIS_SEVERITY_MAX", 20.0),
    )

_SOCIAL_CRITICAL_PENDING_ATTR = "_social_critical_pending"


def _get_social_pending(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, None)
    if pending is None:
        pending = {}
        setattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, pending)
    return pending


def _effective_critical(agent: AgentState, world: WorldState, field: str) -> float:
    pending = _get_social_pending(world).get(agent.id, {})
    transition_pending = get_transition_pending(world).get(agent.id, {})
    base = {
        "gdp": float(agent.economy.gdp),
        "capital": float(agent.economy.capital),
        "public_debt": float(agent.economy.public_debt),
        "trust_gov": float(agent.society.trust_gov),
        "social_tension": float(agent.society.social_tension),
    }[field]
    return base + float(transition_pending.get(field, 0.0)) + float(pending.get(field, 0.0))


def _add_critical_delta(
    world: WorldState,
    agent: AgentState,
    *,
    gdp: float = 0.0,
    capital: float = 0.0,
    public_debt: float = 0.0,
    trust_gov: float = 0.0,
    social_tension: float = 0.0,
) -> None:
    pending = _get_social_pending(world)
    values = pending.setdefault(
        agent.id,
        {
            "gdp": 0.0,
            "capital": 0.0,
            "public_debt": 0.0,
            "trust_gov": 0.0,
            "social_tension": 0.0,
        },
    )
    values["gdp"] += float(gdp)
    values["capital"] += float(capital)
    values["public_debt"] += float(public_debt)
    record_debt_flow(world, agent.id, "restructuring", public_debt)
    values["trust_gov"] += float(trust_gov)
    values["social_tension"] += float(social_tension)


def _set_critical_effective(world: WorldState, agent: AgentState, field: str, target: float) -> None:
    current = _effective_critical(agent, world, field)
    delta = float(target) - current
    if delta == 0.0:
        return
    _add_critical_delta(world, agent, **{field: delta})


def pop_social_critical_deltas(world: WorldState) -> Dict[str, Dict[str, float]]:
    pending = getattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, None)
    if not pending:
        return {}
    setattr(world.global_state, _SOCIAL_CRITICAL_PENDING_ATTR, {})
    return {
        agent_id: {
            "gdp": float(values.get("gdp", 0.0)),
            "capital": float(values.get("capital", 0.0)),
            "public_debt": float(values.get("public_debt", 0.0)),
            "trust_gov": float(values.get("trust_gov", 0.0)),
            "social_tension": float(values.get("social_tension", 0.0)),
        }
        for agent_id, values in pending.items()
    }


def _flush_social_pending_for_agent(world: WorldState, agent: AgentState) -> None:
    pending = _get_social_pending(world)
    values = pending.pop(agent.id, None)
    if not values:
        return
    economy = agent.economy
    society = agent.society
    setattr(economy, "gdp", max(0.0, float(economy.gdp) + float(values.get("gdp", 0.0))))
    setattr(economy, "capital", max(0.0, float(economy.capital) + float(values.get("capital", 0.0))))
    setattr(
        economy,
        "public_debt",
        max(0.0, float(economy.public_debt) + float(values.get("public_debt", 0.0))),
    )
    setattr(society, "trust_gov", clamp01(float(society.trust_gov) + float(values.get("trust_gov", 0.0))))
    setattr(
        society,
        "social_tension",
        clamp01(float(society.social_tension) + float(values.get("social_tension", 0.0))),
    )


def logistic_birth_rate(gdp_per_capita: float, cal) -> float:
    """[#15] Logistic demographic-transition crude birth rate as a function of income (Lutz et al.
    2001, Nature 412:543). High at low income, falling steeply through middle income, plateauing at
    high income: CBR(y) = MIN + (MAX-MIN)/(1+exp(K*(ln y - ln y_mid))). Replaces the linear
    `BASE_BIRTH_RATE - BIRTH_GDP_PC_DECAY*y` (negligible slope; could go negative at high income).
    """
    y = max(gdp_per_capita, 1.0)
    lo, hi = cal.CBR_LOGISTIC_MIN, cal.CBR_LOGISTIC_MAX
    z = cal.CBR_LOGISTIC_K * (math.log(y) - math.log(cal.CBR_LOGISTIC_MID_GDP_PC))
    return lo + (hi - lo) / (1.0 + math.exp(z))


def preston_death_rate(gdp_per_capita: float, cal) -> float:
    """[#15] Income-driven underlying crude death rate (Preston 1975, Pop. Studies 29:231): mortality
    risk falls with income (via life expectancy), plateauing at high income. Logistic in log-income.
    NB GIM has no age structure, so this models the income->mortality channel holding age-composition
    fixed (it does NOT reproduce the aging-driven CDR rebound in rich countries — documented limitation).
    """
    y = max(gdp_per_capita, 1.0)
    lo, hi = cal.CDR_LOGISTIC_MIN, cal.CDR_LOGISTIC_MAX
    z = cal.CDR_LOGISTIC_K * (math.log(y) - math.log(cal.CDR_LOGISTIC_MID_GDP_PC))
    return lo + (hi - lo) / (1.0 + math.exp(z))


def update_population(agent: AgentState, world: WorldState) -> None:
    cal = resolve_params(world)
    gdp_per_capita = agent.economy.gdp_per_capita
    gini = agent.society.inequality_gini / 100.0

    food = agent.resources.get("food")
    if food is not None:
        availability_ratio = (food.production + cal.FOOD_RESERVE_WEIGHT * food.own_reserve) / max(
            food.consumption, 1e-6
        )
    else:
        availability_ratio = 1.0
    availability_ratio = min(cal.FOOD_AVAILABILITY_MAX, max(0.0, availability_ratio))
    scarcity = max(0.0, 1.0 - availability_ratio)

    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    ratio = max(gdp_per_capita / baseline, 1e-6)
    prosperity = 1.0 / (1.0 + math.exp(-cal.PROSPERITY_LOGIT_SENS * math.log(ratio)))

    # [#15] Income channel: logistic demographic transition (switchable) vs the legacy linear term.
    # When on, the absolute-income logistic SUBSUMES both the linear income term and the relative-
    # prosperity damp (avoiding a double income->fertility channel); scarcity/gini multipliers remain.
    if getattr(cal, "DEMOGRAPHIC_LOGISTIC", False):
        birth_rate = logistic_birth_rate(gdp_per_capita, cal)
    else:
        birth_rate = cal.BASE_BIRTH_RATE - cal.BIRTH_GDP_PC_DECAY * gdp_per_capita
        birth_rate *= 1.0 - cal.BIRTH_PROSPERITY_DAMP * prosperity
    birth_rate *= 1.0 - cal.BIRTH_SCARCITY_DAMP * scarcity
    birth_rate *= 1.0 - cal.BIRTH_GINI_DAMP * gini
    agent.economy.birth_rate = max(cal.BIRTH_RATE_MIN, min(cal.BIRTH_RATE_MAX, birth_rate))

    if getattr(cal, "DEMOGRAPHIC_LOGISTIC", False):
        death_rate = preston_death_rate(gdp_per_capita, cal)
    else:
        death_rate = cal.BASE_DEATH_RATE - cal.DEATH_GDP_PC_DECAY * gdp_per_capita
        death_rate *= 1.0 - cal.DEATH_PROSPERITY_DAMP * prosperity
    death_rate *= 1.0 + cal.DEATH_SCARCITY_SENS * scarcity + cal.DEATH_GINI_SENS * gini
    agent.economy.death_rate = max(cal.DEATH_RATE_MIN, min(cal.DEATH_RATE_MAX, death_rate))

    growth_rate = agent.economy.birth_rate - agent.economy.death_rate
    agent.economy.population *= 1 + growth_rate


def update_migration_flows(world: WorldState) -> None:
    cal = resolve_params(world)
    baseline = getattr(world.global_state, "baseline_gdp_pc", 0.0) or 1.0
    base_rate = cal.MIGRATION_BASE_RATE
    max_share = cal.MIGRATION_MAX_SHARE

    gdp_pc: dict[str, float] = {}
    for agent in world.agents.values():
        if agent.economy.gdp_per_capita > 0:
            gdp_pc_val = agent.economy.gdp_per_capita
        else:
            gdp_pc_val = agent.economy.gdp * 1e12 / max(agent.economy.population, 1.0)
        gdp_pc[agent.id] = gdp_pc_val

    net_flows: dict[str, float] = {agent_id: 0.0 for agent_id in world.agents}

    for origin_id, origin in world.agents.items():
        income_gap = max(0.0, (baseline - gdp_pc[origin_id]) / baseline)
        conflict_push = clamp01(origin.risk.conflict_proneness)
        push = cal.MIGRATION_INCOME_PUSH_W * income_gap + cal.MIGRATION_CONFLICT_PUSH_W * conflict_push
        if push <= 0.0:
            continue

        population = origin.economy.population
        outflow = base_rate * population * push
        outflow = min(outflow, max_share * population)
        if outflow <= 0.0:
            continue

        weights: dict[str, float] = {}
        total_weight = 0.0
        for dest_id, rel in world.relations.get(origin_id, {}).items():
            dest = world.agents.get(dest_id)
            if dest is None:
                continue
            gap = max(0.0, (gdp_pc[dest_id] - gdp_pc[origin_id]) / baseline)
            if gap <= 0.0:
                continue
            dest_conflict = clamp01(dest.risk.conflict_proneness)
            trade_weight = max(0.0, effective_trade_intensity(rel))
            weight = trade_weight * gap * (1.0 - cal.MIGRATION_DEST_CONFLICT_DAMP * dest_conflict)
            if weight <= 0.0:
                continue
            weights[dest_id] = weight
            total_weight += weight

        if total_weight <= 0.0:
            continue

        for dest_id, weight in weights.items():
            flow = outflow * (weight / total_weight)
            net_flows[origin_id] -= flow
            net_flows[dest_id] += flow

    for agent_id, delta in net_flows.items():
        if abs(delta) <= 0.0:
            continue
        agent = world.agents[agent_id]
        agent.economy.population = max(0.0, agent.economy.population + delta)


_TRUST_ANCHORS_ATTR = "_trust_anchors"
_GINI_ANCHORS_ATTR = "_gini_anchors"
_GDPPC_ANCHORS_ATTR = "_gdppc_anchors"


def _trust_anchors(world: WorldState) -> Dict[str, float]:
    """Per-agent anchor trust_gov for the equilibrium pull: each agent's own base-year value
    (captured once, the first time this is called) -- mirrors resources._resource_price_anchors."""
    anchors = getattr(world.global_state, _TRUST_ANCHORS_ATTR, None)
    if anchors is None:
        anchors = {aid: clamp01(a.society.trust_gov) for aid, a in world.agents.items()}
        setattr(world.global_state, _TRUST_ANCHORS_ATTR, anchors)
    return anchors


def _gini_anchors(world: WorldState) -> Dict[str, float]:
    """Per-agent base-year inequality_gini, captured once. Reference level for the
    deviation form of the trust-inequality term (TRUST_GINI_DEVIATION_FORM)."""
    anchors = getattr(world.global_state, _GINI_ANCHORS_ATTR, None)
    if anchors is None:
        anchors = {aid: float(a.society.inequality_gini) for aid, a in world.agents.items()}
        setattr(world.global_state, _GINI_ANCHORS_ATTR, anchors)
    return anchors


def _gdppc_anchors(world: WorldState) -> Dict[str, float]:
    """Per-agent base-year gdp_per_capita, captured once. Reference level for the
    deviation form of the trust-income term (TRUST_GDPPC_DEVIATION_FORM)."""
    anchors = getattr(world.global_state, _GDPPC_ANCHORS_ATTR, None)
    if anchors is None:
        anchors = {aid: max(1e-9, float(a.economy.gdp_per_capita))
                   for aid, a in world.agents.items()}
        setattr(world.global_state, _GDPPC_ANCHORS_ATTR, anchors)
    return anchors


def update_social_state(agent: AgentState, action: Action, world: WorldState) -> None:
    cal = resolve_params(world)
    # [F-social-form] Trust is a bounded state, but three of its five drivers enter as LEVELS,
    # so a country at a constant, entirely normal gini/unemployment/inflation loses trust every
    # year forever. At calibrated values TRUST_GINI_SENS * gini alone is ~-0.0165/yr against a
    # TRUST_GDP_PC_SENS term of ~+0.0005/yr, and nothing cancels it: trust is a countdown, not a
    # state. (The tension term below already uses the correct deviation form, from
    # TRUST_TENSION_THRESHOLD.) The deviation switches restore that form driver by driver:
    # unemployment against NAIRU, inflation against INFLATION_TARGET, gini and income against
    # each agent's own base-year value. All default False => level form, bit-identical.
    if getattr(cal, "TRUST_GDPPC_DEVIATION_FORM", False):
        gdp_pc_ref = _gdppc_anchors(world).get(agent.id, cal.TRUST_GDP_PC_REF)
        gdp_pc_effect = cal.TRUST_GDP_PC_SENS * (
            (agent.economy.gdp_per_capita - gdp_pc_ref) / cal.TRUST_GDP_PC_REF
        )
    else:
        gdp_pc_effect = cal.TRUST_GDP_PC_SENS * (agent.economy.gdp_per_capita / cal.TRUST_GDP_PC_REF)

    if getattr(cal, "TRUST_UNEMP_DEVIATION_FORM", False):
        unemployment_effect = cal.TRUST_UNEMPLOYMENT_SENS * (
            agent.economy.unemployment - cal.NAIRU
        )
    else:
        unemployment_effect = cal.TRUST_UNEMPLOYMENT_SENS * agent.economy.unemployment

    if getattr(cal, "TRUST_INFLATION_DEVIATION_FORM", False):
        inflation_effect = cal.TRUST_INFLATION_SENS * (
            agent.economy.inflation - cal.INFLATION_TARGET
        )
    else:
        inflation_effect = cal.TRUST_INFLATION_SENS * agent.economy.inflation

    if getattr(cal, "TRUST_GINI_DEVIATION_FORM", False):
        gini_ref = _gini_anchors(world).get(agent.id, agent.society.inequality_gini)
        inequality_trust_penalty = cal.TRUST_GINI_SENS * (
            agent.society.inequality_gini - gini_ref
        )
    else:
        inequality_trust_penalty = cal.TRUST_GINI_SENS * agent.society.inequality_gini

    current_tension = _effective_critical(agent, world, "social_tension")
    tension_trust_penalty = cal.TRUST_TENSION_SENS * max(
        0.0,
        current_tension - cal.TRUST_TENSION_THRESHOLD,
    )

    trust_change = (
        gdp_pc_effect
        + unemployment_effect
        + inflation_effect
        + inequality_trust_penalty
        + tension_trust_penalty
    )
    # [#16] Inequality x unemployment interaction (Gould & Hijzen 2016): inequality erodes trust more
    # in downturns. Default coef 0.0 => off (golden-safe).
    interact = getattr(cal, "TRUST_GINI_UNEMP_INTERACT", 0.0)
    if interact:
        trust_change -= interact * (agent.society.inequality_gini / 100.0) * agent.economy.unemployment
    # [F3] Culture link: power distance -> weaker accountability institutions -> lower trust.
    if getattr(cal, "CULTURE_SOCIAL_LINKS", False):
        _ref = cal.CULTURE_DIM_REF
        trust_change -= cal.CULTURE_PDI_TRUST_SENS * (agent.culture.pdi - _ref) / 100.0
    current_trust = _effective_critical(agent, world, "trust_gov")
    trust_next = clamp01(current_trust + trust_change)
    # [2026-07-12] Weak equilibrium pull toward this agent's own base-year trust, applied AFTER the
    # walk step -- same role PRICE_ANCHOR_PULL plays for prices (resources.py), linear here since
    # trust_gov is additive/[0,1], not multiplicative. Default 0.0 => off, golden-safe/bit-identical.
    anchor_pull = float(getattr(cal, "TRUST_ANCHOR_PULL", 0.0))
    if anchor_pull > 0.0:
        anchor = _trust_anchors(world).get(agent.id, trust_next)
        trust_next = clamp01(trust_next + anchor_pull * (anchor - trust_next))
    _set_critical_effective(world, agent, "trust_gov", trust_next)

    inequality_sensitivity = 1.0 - agent.culture.idv / 100.0
    # [F-social-form 2026-08-24] Tension carries the same level-vs-deviation defect as trust, and
    # a larger one: INEQUALITY_EFFECT_SENS * gini is about +0.02/yr at a realistic gini of 40 and
    # never returns to zero, so tension ratchets up for a country whose inequality never changed.
    # Tension then drains trust through the tension_trust_penalty above, which is the
    # self-reinforcing loop the 2026-07-12 note describes. Same switch semantics as the trust
    # terms: gini against each agent's own base-year value, unemployment against NAIRU, inflation
    # against INFLATION_TARGET. Default False => level form, golden bit-identical.
    if getattr(cal, "TENSION_GINI_DEVIATION_FORM", False):
        gini_ref_t = _gini_anchors(world).get(agent.id, agent.society.inequality_gini)
        inequality_effect = (cal.INEQUALITY_EFFECT_SENS
                             * (agent.society.inequality_gini - gini_ref_t)
                             * inequality_sensitivity)
    else:
        inequality_effect = cal.INEQUALITY_EFFECT_SENS * agent.society.inequality_gini * inequality_sensitivity

    if getattr(cal, "TENSION_STRESS_DEVIATION_FORM", False):
        stress_effect = (
            cal.SOCIAL_STRESS_UNEMPLOYMENT_SENS * (agent.economy.unemployment - cal.NAIRU)
            + cal.SOCIAL_STRESS_INFLATION_SENS * (agent.economy.inflation - cal.INFLATION_TARGET)
        )
    else:
        stress_effect = (
            cal.SOCIAL_STRESS_UNEMPLOYMENT_SENS * agent.economy.unemployment
            + cal.SOCIAL_STRESS_INFLATION_SENS * agent.economy.inflation
        )
    # [F3] Culture link: uncertainty avoidance amplifies the reaction to economic stress.
    if getattr(cal, "CULTURE_SOCIAL_LINKS", False):
        _ref = cal.CULTURE_DIM_REF
        stress_effect *= 1.0 + cal.CULTURE_UAI_STRESS_SENS * (agent.culture.uai - _ref) / 100.0
    # [2026-07-12] SOCIAL_TRUST_ANCHOR_REF is a single global constant (0.50) regardless of an
    # agent's own natural trust baseline -- for an agent whose base-year trust sits above 0.50 (most
    # of the tracked set), an ordinary crisis dip below the constant flips this term from damping
    # tension to actively amplifying it, at a threshold with no relation to that agent's own social
    # reality. Gated on the same TRUST_ANCHOR_PULL flag (same underlying fix: give trust dynamics a
    # per-agent baseline instead of one global reference point); default off leaves REF untouched.
    # [F-social-form 2026-08-24] The per-agent reference is the right one whether or not the
    # anchor pull is active -- the two were only ever tied together because they were written in
    # the same pass. TENSION_REF_PER_AGENT selects it independently; the original gating on
    # anchor_pull is kept so existing configurations stay bit-identical.
    if getattr(cal, "TENSION_REF_PER_AGENT", False) or anchor_pull > 0.0:
        tension_ref = _trust_anchors(world).get(agent.id, cal.SOCIAL_TRUST_ANCHOR_REF)
    else:
        tension_ref = cal.SOCIAL_TRUST_ANCHOR_REF
    trust_anchor = cal.SOCIAL_TRUST_ANCHOR_SENS * (tension_ref - trust_next)

    # [F-climate-social 2026-08-24] CONTESTED PRIOR, DEFAULT OFF. A continuous climate ->
    # social-stress channel. GIM reaches society from climate only through discrete extreme
    # events (climate.py:400, apply_climate_extreme_events), which the deterministic headline
    # runs switch off entirely -- so at the headline configuration climate does not touch
    # tension at all, and the climate-risk spatial diffusion is exactly inert as a result
    # (Paper/revision/results/e18_climate_spatial_with_events.json).
    # The canonical prior is Hsiang, Burke & Miguel 2013 (Science 341, 1235367): per one
    # standard deviation of warming, interpersonal violence rises 4% and intergroup conflict
    # 14%, from a meta-analysis of 60 studies. It is genuinely disputed -- Buhaug et al. 2014
    # (Climatic Change 127:391-397) argue the meta-analysis has sample-selection and
    # analytical-coherence problems and that the literature is mixed and inconclusive; Hsiang
    # et al. reply identifying five errors in that reanalysis. The dispute is not settled.
    # The DIRECTION is defensible; the MAGNITUDE is not identified. So this ships off, tagged
    # as a prior, for tail and sensitivity scenarios only -- the same treatment the carbon
    # feedbacks get. Do not enable it in a headline configuration without saying so.
    climate_tension_sens = float(getattr(cal, "TENSION_CLIMATE_SENS", 0.0))
    climate_effect = (climate_tension_sens * clamp01(agent.climate.climate_risk)
                      if climate_tension_sens != 0.0 else 0.0)

    tension_change = inequality_effect + stress_effect + trust_anchor + climate_effect
    # [F3] Culture link: long-term orientation (patience) damps short-run unrest swings.
    if getattr(cal, "CULTURE_SOCIAL_LINKS", False):
        _ref = cal.CULTURE_DIM_REF
        tension_change *= 1.0 - cal.CULTURE_LTO_PATIENCE_SENS * (agent.culture.lto - _ref) / 100.0
    # [GEO] Spatial contagion: unrest diffuses across geographic neighbours (Arab-Spring-style; Braha
    # 2012; Hale 2013). Spatial lag toward the neighbourhood-mean tension; 0.0 when off => golden-safe.
    # Neighbours are read at their start-of-step values (society writes are deferred), so order-stable.
    if getattr(cal, "GEOGRAPHY_TENSION_LINKS", False):
        neigh = _geo_adjacency(world).get(agent.id, ())
        vals = [world.agents[nb].society.social_tension for nb in neigh if nb in world.agents]
        if vals:
            tension_change += cal.GEO_TENSION_SPILLOVER_W * (sum(vals) / len(vals) - current_tension)
    tension_next = clamp01(current_tension + tension_change)
    _set_critical_effective(world, agent, "social_tension", tension_next)

    # Inequality dynamics: GDP growth distribution, fiscal policy, and social tension.
    prev_gdp = getattr(
        agent.economy,
        "_gdp_step_start",
        getattr(agent.economy, "_gdp_prev", agent.economy.gdp),
    )
    gdp = agent.economy.gdp
    gdp_growth = (gdp - prev_gdp) / max(prev_gdp, 1e-6)

    social_spend_delta = action.domestic_policy.social_spending_change
    growth_effect = cal.GINI_GROWTH_SENS * gdp_growth
    recession_penalty = cal.GINI_RECESSION_SENS * abs(min(0.0, gdp_growth)) * (
        cal.GINI_RECESSION_TENSION_OFFSET + tension_next
    )
    fiscal_effect = cal.GINI_FISCAL_SENS * social_spend_delta
    tension_effect = cal.GINI_TENSION_SENS * (tension_next - cal.GINI_TENSION_REF)

    gini_next = (
        agent.society.inequality_gini
        + growth_effect
        + recession_penalty
        + fiscal_effect
        + tension_effect
    )
    agent.society.inequality_gini = max(cal.GINI_MIN, min(cal.GINI_MAX, gini_next))


def check_regime_stability(agent: AgentState, world: WorldState | None = None) -> None:
    # WRITES: risk.regime_crisis_active_years, economy.capital, economy.gdp,
    # economy.public_debt, society.trust_gov, society.social_tension
    cal = resolve_params(world)
    if world is None:
        trust_threshold = cal.REGIME_COLLAPSE_TRUST_THRESHOLD
        tension_threshold = cal.REGIME_COLLAPSE_TENSION_THRESHOLD
        in_crisis = (
            agent.society.trust_gov < trust_threshold
            and agent.society.social_tension > tension_threshold
        )
        if in_crisis:
            agent.risk.regime_crisis_active_years = min(
                agent.risk.regime_crisis_active_years + 1,
                cal.REGIME_CRISIS_MAX_YEARS,
            )
            crisis_year = agent.risk.regime_crisis_active_years
            if crisis_year == 1:
                economy = agent.economy
                society = agent.society
                setattr(economy, "capital", economy.capital * cal.REGIME_COLLAPSE_CAPITAL_MULT)
                setattr(economy, "gdp", economy.gdp * cal.REGIME_COLLAPSE_GDP_MULT)
                setattr(economy, "public_debt", economy.public_debt * cal.REGIME_COLLAPSE_DEBT_MULT)
                setattr(society, "trust_gov", max(society.trust_gov, cal.REGIME_COLLAPSE_TRUST_FLOOR))
                setattr(society, "social_tension", min(society.social_tension, cal.REGIME_COLLAPSE_TENSION_CAP))
                agent.risk.regime_stability = max(
                    0.0,
                    agent.risk.regime_stability - cal.REGIME_COLLAPSE_STABILITY_HIT,
                )
            else:
                economy = agent.economy
                setattr(economy, "capital", economy.capital * cal.REGIME_CRISIS_PERSIST_CAPITAL_MULT)
                setattr(economy, "gdp", economy.gdp * cal.REGIME_CRISIS_PERSIST_GDP_MULT)
        else:
            agent.risk.regime_crisis_active_years = 0
        return

    trust_threshold = cal.REGIME_COLLAPSE_TRUST_THRESHOLD
    tension_threshold = cal.REGIME_COLLAPSE_TENSION_THRESHOLD
    trust_effective = _effective_critical(agent, world, "trust_gov")
    tension_effective = _effective_critical(agent, world, "social_tension")
    in_crisis = (
        trust_effective < trust_threshold
        and tension_effective > tension_threshold
    )
    if in_crisis:
        agent.risk.regime_crisis_active_years = min(
            agent.risk.regime_crisis_active_years + 1,
            cal.REGIME_CRISIS_MAX_YEARS,
        )
        crisis_year = agent.risk.regime_crisis_active_years
        if crisis_year == 1:
            sev = _crisis_severity(world, cal)  # F5: fat-tailed collapse depth (1.0 when disabled)
            _set_critical_effective(
                world,
                agent,
                "capital",
                _effective_critical(agent, world, "capital") * (1.0 + sev * (cal.REGIME_COLLAPSE_CAPITAL_MULT - 1.0)),
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * (1.0 + sev * (cal.REGIME_COLLAPSE_GDP_MULT - 1.0)),
            )
            _set_critical_effective(
                world,
                agent,
                "public_debt",
                _effective_critical(agent, world, "public_debt") * (1.0 + sev * (cal.REGIME_COLLAPSE_DEBT_MULT - 1.0)),
            )

            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(_effective_critical(agent, world, "trust_gov"), cal.REGIME_COLLAPSE_TRUST_FLOOR),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(_effective_critical(agent, world, "social_tension"), cal.REGIME_COLLAPSE_TENSION_CAP),
            )
            agent.risk.regime_stability = max(
                0.0,
                agent.risk.regime_stability - cal.REGIME_COLLAPSE_STABILITY_HIT,
            )
        else:
            _set_critical_effective(
                world,
                agent,
                "capital",
                _effective_critical(agent, world, "capital") * cal.REGIME_CRISIS_PERSIST_CAPITAL_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.REGIME_CRISIS_PERSIST_GDP_MULT,
            )
    else:
        agent.risk.regime_crisis_active_years = 0


_TRADE_SCALE_ATTR = "_resource_trade_gdp_scale"


def _raw_resource_balance(agent: AgentState, world: WorldState) -> float:
    """Resource production minus consumption, valued at world prices, in RAW units."""
    prices = getattr(world.global_state, "prices", {}) or {}
    total = 0.0
    for resource_name in ("energy", "food", "metals"):
        resource = agent.resources.get(resource_name)
        if resource is None:
            continue
        unit_price = max(float(prices.get(resource_name, 1.0)), 1e-6)
        total += (float(resource.production) - float(resource.consumption)) * unit_price
    return total


def _resource_trade_scale(world: WorldState) -> float:
    """Conversion from raw resource-value units into GDP units, captured once.

    [F-fx 2026-08-24] Resource quantities are physical and prices are indices, so their
    product is not commensurate with GDP in trillions -- yet `_estimate_annual_import_bill`
    was divided by GDP and read as a ratio. Measured, the world sum of net import bills is
    **3190% of world GDP**, roughly 300x too large, which is why fx_cover_months came out at a
    median of 0.053 months (1.6 days of import cover) and why the fx block's ratios were
    meaningless. fx_reserves, by contrast, are already in GDP units (median 13.9% of GDP,
    realistic), so only the trade side needs converting.

    The scale is set so the world sum of net import bills equals
    RESOURCE_TRADE_GDP_SHARE of world GDP. Anchor: WTO 2022 world exports of fuels and mining
    products were US$5.16tn (21% of world merchandise exports) and agricultural products
    roughly US$2.2tn, together about 7.4% of world GDP GROSS; the model computes each agent's
    NET position, whose sum is a fraction of gross trade, so the default targets 4%.
    """
    scale = getattr(world.global_state, _TRADE_SCALE_ATTR, None)
    if scale is None:
        cal = resolve_params(world)
        share = float(getattr(cal, "RESOURCE_TRADE_GDP_SHARE", 0.0))
        if share <= 0.0:
            scale = 1.0          # disabled => raw units, golden bit-identical
        else:
            world_gdp = sum(max(0.0, float(a.economy.gdp)) for a in world.agents.values())
            raw_bill = sum(max(0.0, -_raw_resource_balance(a, world))
                           for a in world.agents.values())
            scale = (share * world_gdp / raw_bill) if raw_bill > 0.0 else 1.0
        setattr(world.global_state, _TRADE_SCALE_ATTR, float(scale))
    return float(scale)


def _estimate_annual_import_bill(agent: AgentState, world: WorldState) -> float:
    return max(0.0, -_raw_resource_balance(agent, world)) * _resource_trade_scale(world)


def apply_structural_trade_balance(world: WorldState) -> None:
    """Write each agent's resource trade balance into `economy.net_exports`.

    [F-fx 2026-08-24] `net_exports` was written ONLY by executed bilateral trade deals
    (actions.py:404-449), and those come from `proposed_trade_deals`, which is populated only
    from LLM or player action data. Both scripted policies propose none, so in every
    deterministic run net_exports was identically zero for all 57 agents, the current-account
    ratio was pinned at zero, and the fx-crisis trigger could not fire at any calibration --
    while its other two conditions coincided in 63.68% of agent-years
    (Paper/revision/results/e12_fx_trigger_diagnosis.json).

    The structural balance is production minus consumption valued at world prices, converted
    into GDP units by `_resource_trade_scale`, then demeaned pro rata to GDP so the world sum is
    exactly zero -- the closed-economy invariant `TRADE_BALANCE_TOL` checks. It is ADDED to
    whatever the deal layer wrote, so a bilateral deal still moves the balance on top of the
    structural position.

    No-op unless STRUCTURAL_TRADE_BALANCE is on, so existing configurations are bit-identical.
    """
    cal = resolve_params(world)
    if not getattr(cal, "STRUCTURAL_TRADE_BALANCE", False):
        return
    scale = _resource_trade_scale(world)
    balances = {aid: _raw_resource_balance(a, world) * scale
                for aid, a in world.agents.items()}

    # [F-fx 2026-08-24] Crisis-driven current-account reversal. In a real currency crisis the
    # exchange rate depreciates, imports compress and the deficit narrows sharply -- reversals of
    # several percent of GDP within a year are the empirical regularity. GIM has no nominal
    # exchange rate (stated in the paper's Limitations), so without a stand-in for that
    # adjustment a deficit country can never rebuild reserves and the fx crisis becomes a
    # permanent trap: measured mean duration 8.35 years with no reserve accumulation and 27 years
    # with it, against a real-world 1-3. Compressing the deficit of an agent already in crisis is
    # the minimal stand-in. Applied BEFORE the demeaning below, so the world still closes exactly.
    compression = float(getattr(cal, "FX_CRISIS_DEFICIT_COMPRESSION", 0.0))
    if compression > 0.0:
        for aid, agent in world.agents.items():
            if agent.risk.fx_crisis_active_years > 0 and balances[aid] < 0.0:
                balances[aid] *= max(0.0, 1.0 - compression)

    total = sum(balances.values())
    world_gdp = sum(max(0.0, float(a.economy.gdp)) for a in world.agents.values())
    if world_gdp <= 0.0:
        return
    accum = float(getattr(cal, "FX_RESERVE_ACCUMULATION_SHARE", 0.0))
    for aid, agent in world.agents.items():
        share = max(0.0, float(agent.economy.gdp)) / world_gdp
        balance = balances[aid] - total * share
        agent.economy.net_exports = float(agent.economy.net_exports) + balance
        # [F-fx 2026-08-24] Balance-of-payments identity: a trade surplus accumulates reserves,
        # a deficit drains them. Nothing in the model did this -- fx_reserves was written only by
        # bilateral trade deals (dead), IMF-style grants (institutions.py:368) and explicit
        # policy. So once an agent's reserve cover fell below the crisis threshold nothing could
        # rebuild it and the fx crisis became a permanent trap: measured mean duration 8.35 years
        # against a real-world 1-3 (Paper/revision/results/e17_fx_channel_validation.json).
        # Only a share of the current account reaches official reserves -- the rest is private
        # capital flows the model does not carry -- hence the share parameter. 0.0 => off.
        if accum > 0.0:
            agent.economy.fx_reserves = max(0.0, float(agent.economy.fx_reserves)
                                            + accum * balance)


def _fx_crisis_inputs(agent: AgentState, world: WorldState) -> Dict[str, float]:
    cal = resolve_params(world)
    gdp = max(_effective_critical(agent, world, "gdp"), 1e-6)
    debt_gdp = _effective_critical(agent, world, "public_debt") / gdp
    annual_import_bill = _estimate_annual_import_bill(agent, world)
    # [F-fx 2026-08-24] "Months of import cover" is defined against TOTAL imports, but the model
    # only carries the resource bill. WTO 2022: fuels and mining products were 21% of world
    # merchandise exports and agricultural products roughly 9%, so resource goods are about 30%
    # of merchandise trade -> total imports are roughly 3.3x the resource bill. 1.0 => unchanged.
    cover_multiplier = max(1.0, float(getattr(cal, "IMPORT_COVER_TOTAL_MULTIPLIER", 1.0)))
    monthly_import_bill = max(annual_import_bill * cover_multiplier / 12.0, 1e-6)
    fx_cover_months = float(agent.economy.fx_reserves) / monthly_import_bill
    reserve_ratio = float(agent.economy.fx_reserves) / gdp
    import_ratio = annual_import_bill / gdp
    trade_balance_ratio = float(agent.economy.net_exports) / gdp
    current_account_ratio = min(0.0, trade_balance_ratio)
    if current_account_ratio < 0.0:
        current_account_ratio -= cal.FX_CRISIS_IMPORT_LEAKAGE_WEIGHT * import_ratio
    external_debt_ratio = max(0.0, debt_gdp - cal.FX_CRISIS_RESERVE_OFFSET_WEIGHT * reserve_ratio)
    return {
        "annual_import_bill": annual_import_bill,
        "fx_cover_months": fx_cover_months,
        "current_account_ratio": current_account_ratio,
        "external_debt_ratio": external_debt_ratio,
    }


def check_debt_crisis(agent: AgentState, world: WorldState, *, defer_critical_writes: bool = False) -> None:
    cal = resolve_params(world)
    economy = agent.economy
    risk = agent.risk

    # WRITES: risk.debt_crisis_active_years, economy.public_debt, economy.gdp,
    # economy.unemployment, society.trust_gov, society.social_tension
    gdp = max(_effective_critical(agent, world, "gdp"), 1e-6)
    debt_gdp = _effective_critical(agent, world, "public_debt") / gdp
    interest_rate = compute_effective_interest_rate(agent, world)

    debt_trigger = (
        debt_gdp > cal.DEBT_CRISIS_DEBT_THRESHOLD
        and interest_rate > cal.DEBT_CRISIS_RATE_THRESHOLD
    )

    if risk.debt_crisis_active_years == 0:
        in_crisis = debt_trigger
        recovered = False
        if in_crisis:
            risk.debt_crisis_trigger = "debt"
    else:
        recovery_window_open = risk.debt_crisis_active_years >= 2
        recovered = (
            debt_gdp < cal.DEBT_CRISIS_EXIT_THRESHOLD
            and interest_rate < cal.DEBT_CRISIS_EXIT_RATE
        )
        in_crisis = not (recovery_window_open and recovered)

    if in_crisis:
        risk.debt_crisis_active_years = min(
            risk.debt_crisis_active_years + 1,
            cal.DEBT_CRISIS_MAX_YEARS,
        )
        crisis_year = risk.debt_crisis_active_years
        if crisis_year == 1:
            # F5: fat-tailed crisis severity scales the shock DEPTH (sev=1.0 when disabled).
            sev = _crisis_severity(world, cal)
            _set_critical_effective(
                world,
                agent,
                "public_debt",
                _effective_critical(agent, world, "public_debt") * (1.0 + sev * (cal.DEBT_CRISIS_DEBT_MULT - 1.0)),
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * (1.0 + sev * (cal.DEBT_CRISIS_GDP_MULT - 1.0)),
            )
            economy.unemployment = min(
                cal.DEBT_CRISIS_UNEMPLOYMENT_MAX,
                economy.unemployment + sev * cal.DEBT_CRISIS_UNEMPLOYMENT_HIT,
            )
            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - sev * cal.DEBT_CRISIS_TRUST_HIT),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(1.0, _effective_critical(agent, world, "social_tension") + sev * cal.DEBT_CRISIS_TENSION_HIT),
            )
            risk.regime_stability = max(0.0, risk.regime_stability - sev * cal.DEBT_CRISIS_STABILITY_HIT)
        elif not recovered:
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.DEBT_CRISIS_PERSIST_GDP_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - cal.DEBT_CRISIS_PERSIST_TRUST_HIT),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(
                    1.0,
                    _effective_critical(agent, world, "social_tension") + cal.DEBT_CRISIS_PERSIST_TENSION_HIT,
                ),
            )
    else:
        risk.debt_crisis_active_years = 0
        risk.debt_crisis_trigger = "debt"
    if not defer_critical_writes:
        _flush_social_pending_for_agent(world, agent)


def check_fx_crisis(agent: AgentState, world: WorldState, *, defer_critical_writes: bool = False) -> None:
    cal = resolve_params(world)
    economy = agent.economy
    risk = agent.risk

    # WRITES: risk.fx_crisis_active_years, risk.external_debt_ratio,
    # risk.current_account_ratio, risk.fx_reserve_cover_months, economy.public_debt,
    # economy.gdp, economy.unemployment, society.trust_gov, society.social_tension
    fx_inputs = _fx_crisis_inputs(agent, world)
    external_debt_ratio = float(fx_inputs["external_debt_ratio"])
    current_account_ratio = float(fx_inputs["current_account_ratio"])
    fx_cover_months = float(fx_inputs["fx_cover_months"])

    risk.external_debt_ratio = external_debt_ratio
    risk.current_account_ratio = current_account_ratio
    risk.fx_reserve_cover_months = fx_cover_months

    # [F-fx 2026-08-24] An agent that does not issue the currency it uses, or that issues a
    # reserve currency, cannot have a conventional currency crisis -- and holds thin reserves for
    # exactly that reason, which is what the cover test would otherwise misread.
    _exempt_set = set(getattr(cal, "FX_CRISIS_MONETARY_EXEMPT_AGENTS", ()) or ())
    exempt = (agent.id in _exempt_set) or (getattr(agent, "name", None) in _exempt_set)
    fx_trigger = (
        not exempt
        and external_debt_ratio > cal.FX_CRISIS_EXTERNAL_DEBT_THRESHOLD
        and current_account_ratio < cal.FX_CRISIS_CURRENT_ACCOUNT_DEFICIT_THRESHOLD
        and fx_cover_months < cal.FX_CRISIS_RESERVE_MONTHS_THRESHOLD
    )

    if risk.fx_crisis_active_years == 0:
        in_crisis = fx_trigger
        recovered = False
    else:
        recovery_window_open = risk.fx_crisis_active_years >= 1
        recovered = fx_cover_months > cal.FX_CRISIS_RECOVERY_RESERVE_MONTHS
        in_crisis = not (recovery_window_open and recovered)
        # [F-fx 2026-08-24] FX_CRISIS_MAX_YEARS capped the COUNTER but did not end the episode,
        # so an agent whose reserve cover never recovered stayed in crisis indefinitely with the
        # counter parked at its maximum. Since nothing in the model rebuilds reserves -- there is
        # no nominal exchange rate, so no depreciation-driven import compression -- that made the
        # fx crisis a permanent absorbing state: measured mean duration 8.35 years against a
        # real-world 1-3 (Paper/revision/results/e17_fx_channel_validation.json). With the bound
        # enforced the parameter does what its name says. Default False keeps the old behaviour
        # bit-identical.
        if (getattr(cal, "FX_CRISIS_MAX_YEARS_TERMINATES", False)
                and risk.fx_crisis_active_years >= cal.FX_CRISIS_MAX_YEARS):
            in_crisis = False
            recovered = True

    if in_crisis:
        risk.fx_crisis_active_years = min(
            risk.fx_crisis_active_years + 1,
            cal.FX_CRISIS_MAX_YEARS,
        )
        crisis_year = risk.fx_crisis_active_years
        if crisis_year == 1:
            sev = _crisis_severity(world, cal)  # F5: fat-tailed severity (1.0 when disabled)
            _set_critical_effective(
                world,
                agent,
                "public_debt",
                _effective_critical(agent, world, "public_debt") * (1.0 + sev * (cal.FX_CRISIS_DEBT_MULT - 1.0)),
            )
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * (1.0 + sev * (cal.FX_CRISIS_GDP_MULT - 1.0)),
            )
            economy.unemployment = min(
                cal.DEBT_CRISIS_UNEMPLOYMENT_MAX,
                economy.unemployment + sev * cal.FX_CRISIS_UNEMPLOYMENT_HIT,
            )
            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - sev * cal.FX_CRISIS_TRUST_HIT),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(1.0, _effective_critical(agent, world, "social_tension") + sev * cal.FX_CRISIS_TENSION_HIT),
            )
            risk.regime_stability = max(0.0, risk.regime_stability - cal.FX_CRISIS_STABILITY_HIT)
        elif not recovered:
            _set_critical_effective(
                world,
                agent,
                "gdp",
                _effective_critical(agent, world, "gdp") * cal.FX_CRISIS_PERSIST_GDP_MULT,
            )
            _set_critical_effective(
                world,
                agent,
                "trust_gov",
                max(0.0, _effective_critical(agent, world, "trust_gov") - cal.FX_CRISIS_PERSIST_TRUST_HIT),
            )
            _set_critical_effective(
                world,
                agent,
                "social_tension",
                min(
                    1.0,
                    _effective_critical(agent, world, "social_tension") + cal.FX_CRISIS_PERSIST_TENSION_HIT,
                ),
            )
    else:
        risk.fx_crisis_active_years = 0
    if not defer_critical_writes:
        _flush_social_pending_for_agent(world, agent)


def check_financial_crises(agent: AgentState, world: WorldState, *, defer_critical_writes: bool = False) -> None:
    check_debt_crisis(agent, world, defer_critical_writes=True)
    check_fx_crisis(agent, world, defer_critical_writes=True)
    if not defer_critical_writes:
        _flush_social_pending_for_agent(world, agent)
