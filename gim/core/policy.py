import json
import os
import time
from typing import Any, Callable, Dict, Iterable, Optional

from .core import (
    Action,
    DomesticPolicy,
    FinancePolicy,
    ForeignPolicy,
    Observation,
    SanctionsAction,
    SecurityActions,
    TradeDeal,
    TradeRestriction,
)

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_policy_mode(mode: str = "auto") -> str:
    normalized = (mode or "auto").strip().lower()
    if normalized not in {"auto", "simple", "llm", "growth"}:
        raise ValueError(
            f"Unsupported policy mode: {mode!r}. Use auto|simple|llm|growth."
        )
    return normalized


def should_use_llm(mode: str = "auto") -> bool:
    enabled, _ = llm_enablement_status(mode)
    return enabled


def llm_enablement_status(mode: str = "auto") -> tuple[bool, str]:
    normalized = resolve_policy_mode(mode)

    if _is_truthy(os.getenv("USE_SIMPLE_POLICIES")):
        return False, "disabled by USE_SIMPLE_POLICIES"
    if _is_truthy(os.getenv("NO_LLM")):
        return False, "disabled by NO_LLM"

    if normalized == "simple":
        return False, "POLICY_MODE=simple"
    if normalized == "growth":
        return False, "POLICY_MODE=growth"
    if normalized == "llm":
        if not REQUESTS_AVAILABLE:
            return False, "requests library not available"
        if not bool(os.getenv("DEEPSEEK_API_KEY")):
            return False, "DEEPSEEK_API_KEY missing"
        return True, "POLICY_MODE=llm and prerequisites satisfied"

    if not REQUESTS_AVAILABLE:
        return False, "requests library not available"
    if not bool(os.getenv("DEEPSEEK_API_KEY")):
        return False, "DEEPSEEK_API_KEY missing"
    return True, "auto mode detected LLM prerequisites"


def make_policy_map(
    agent_ids: Iterable[str],
    mode: str = "auto",
) -> Dict[str, Callable[..., Action]]:
    normalized = resolve_policy_mode(mode)
    if normalized == "growth":
        policy_fn = growth_seeking_policy
    else:
        policy_fn = llm_policy if should_use_llm(mode) else simple_rule_based_policy
    return {agent_id: policy_fn for agent_id in agent_ids}


def _sanitize_target(value: Any) -> Optional[str]:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _clamp_float(value: Any, lo: float, hi: float, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        x = default
    return max(lo, min(hi, x))


def _normalize_action_for_stability(action: Action) -> Action:
    dom = action.domestic_policy
    dom.tax_fuel_change = _clamp_float(dom.tax_fuel_change, -1.5, 1.5)
    dom.social_spending_change = _clamp_float(dom.social_spending_change, -0.015, 0.02)
    dom.military_spending_change = _clamp_float(dom.military_spending_change, -0.01, 0.015)
    dom.rd_investment_change = _clamp_float(dom.rd_investment_change, -0.002, 0.008)
    if dom.climate_policy not in {"none", "weak", "moderate", "strong"}:
        dom.climate_policy = "none"

    fp = action.foreign_policy
    fp.proposed_trade_deals = fp.proposed_trade_deals[:4]
    for deal in fp.proposed_trade_deals:
        deal.volume_change = _clamp_float(deal.volume_change, 0.0, 50.0)
        if deal.resource not in {"energy", "food", "metals"}:
            deal.resource = "energy"
        if deal.direction not in {"import", "export"}:
            deal.direction = "import"
        if deal.price_preference not in {"cheap", "fair", "premium"}:
            deal.price_preference = "fair"

    fp.sanctions_actions = fp.sanctions_actions[:2]
    for sanction in fp.sanctions_actions:
        if sanction.type not in {"none", "mild", "strong"}:
            sanction.type = "none"
        sanction.target = _sanitize_target(sanction.target) or ""

    fp.trade_restrictions = fp.trade_restrictions[:2]
    for restriction in fp.trade_restrictions:
        if restriction.level not in {"none", "soft", "hard"}:
            restriction.level = "none"
        restriction.target = _sanitize_target(restriction.target) or ""

    if fp.security_actions.type not in {
        "none",
        "military_exercise",
        "arms_buildup",
        "border_incident",
        "conflict",
    }:
        fp.security_actions.type = "none"
    fp.security_actions.target = _sanitize_target(fp.security_actions.target)

    return action


def call_llm(prompt: str) -> str:
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests library is required for llm_policy")
    deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY environment variable is not set")

    timeout_sec = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "2"))
    retry_backoff_sec = float(os.getenv("LLM_RETRY_BACKOFF_SEC", "2.0"))

    headers = {
        "Authorization": f"Bearer {deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a policy decision engine that outputs ONLY JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout_sec,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            sleep_s = retry_backoff_sec * (2**attempt)
            time.sleep(sleep_s)

    raise RuntimeError(
        f"LLM request failed after {max_retries + 1} attempts "
        f"(timeout={timeout_sec}s): {last_error}"
    )


def simple_rule_based_policy(obs: Observation) -> Action:
    gdp_pc = obs.self_state.get("economy", {}).get("gdp_per_capita", 10000.0) or 10000.0
    if gdp_pc > 30000:
        rd_delta = 0.002
    elif gdp_pc > 10000:
        rd_delta = 0.003
    else:
        rd_delta = 0.001

    return Action(
        agent_id=obs.agent_id,
        time=obs.time,
        domestic_policy=DomesticPolicy(
            tax_fuel_change=0.0,
            social_spending_change=0.0,
            military_spending_change=0.0,
            rd_investment_change=rd_delta,
            climate_policy="none",
        ),
        foreign_policy=ForeignPolicy(),
        finance=FinancePolicy(
            borrow_from_global_markets=0.0,
            use_fx_reserves_change=0.0,
        ),
        explanation="baseline do-nothing policy",
    )


def growth_seeking_policy(obs: Observation) -> Action:
    gdp_pc = obs.self_state.get("economy", {}).get("gdp_per_capita", 10000.0) or 10000.0
    if gdp_pc >= 40000:
        rd_delta = 0.004
        social_delta = 0.000
    elif gdp_pc >= 20000:
        rd_delta = 0.005
        social_delta = 0.001
    else:
        rd_delta = 0.006
        social_delta = 0.002

    return Action(
        agent_id=obs.agent_id,
        time=obs.time,
        domestic_policy=DomesticPolicy(
            tax_fuel_change=0.0,
            social_spending_change=social_delta,
            military_spending_change=0.0,
            rd_investment_change=rd_delta,
            climate_policy="none",
        ),
        foreign_policy=ForeignPolicy(),
        finance=FinancePolicy(
            borrow_from_global_markets=0.0,
            use_fx_reserves_change=0.0,
        ),
        explanation="deterministic growth-seeking policy",
    )


LLM_SCHEMA_HINT = """
You MUST output a single JSON object with this structure:
{
  "agent_id": "C01",
  "time": 0,
  "domestic_policy": {
    "tax_fuel_change": 0.0,
    "social_spending_change": 0.0,
    "military_spending_change": 0.0,
    "rd_investment_change": 0.0,
    "climate_policy": "none"
  },
  "foreign_policy": {
    "proposed_trade_deals": [
      {"partner": "C02", "resource": "energy", "direction": "import",
       "volume_change": 10.0, "price_preference": "fair"}
    ],
    "sanctions_actions": [],
    "trade_restrictions": [
      {"target": "C03", "level": "soft", "reason": "domestic protectionism"}
    ],
    "security_actions": {"type": "none", "target": null}
  },
  "finance": {
    "borrow_from_global_markets": 0.0,
    "use_fx_reserves_change": 0.0
  },
  "explanation": ""
}
NUMERIC GUARDRAILS (hard constraints):
- tax_fuel_change: [-1.5, +1.5]
- social_spending_change: [-0.015, +0.020]
- military_spending_change: [-0.010, +0.015]
- rd_investment_change: [-0.002, +0.008]
- each trade deal volume_change: [0, 50]
- trade_restrictions level: none|soft|hard (max 2 entries)
Use small, incremental changes. Avoid extreme one-step shocks.
IMPORTANT: The observation contains a nested field:
  self_state["competitive"] = {
    "gdp_share": float,
    "gdp_rank": int,
    "influence_score": float,
    "security_margin": float,
    "reserve_years": {"energy": float, "food": float, "metals": float}
  }
Use these to reason about your relative position in the world.

If present, you may also use:
  "memory_summary": {
    "horizon": int,
    "gdp_trend": float,
    "gdp_per_capita_trend": float,
    "trust_trend": float,
    "tension_trend": float,
    "security_trend": float,
    "climate_risk_trend": float,
    "last_actions": [ { "time": int, "last_action": {...} } ]
  }
This summarizes your recent trajectory and should inform medium-term planning.
"""


LLM_POLICY_PROMPT_TEMPLATE = (
    "You are the government of ONE country, not a global planner.\n"
    "You see only your own state and summaries about others.\n\n"
    "WIN CONDITIONS (for this country):\n"
    "- Grow your GDP and GDP per capita over time.\n"
    "- Maintain or improve social stability (avoid unrest and collapse).\n"
    "- Keep security_margin >= 1.0 so you are not militarily vulnerable.\n"
    "- Avoid critical shortages in energy, food, and metals (reserve_years not near zero).\n"
    "- Improve your RELATIVE position vs neighbors and rivals:\n"
    "  * Raise or defend your gdp_share and improve your gdp_rank.\n"
    "  * Increase your influence_score compared to competitors.\n\n"
    "LOSS CONDITIONS (must avoid):\n"
    "- Economic collapse: large GDP contraction or very low GDP per capita vs peers.\n"
    "- Social breakdown: trust_gov < 0.2 OR social_tension > 0.8.\n"
    "- Strategic weakness: security_margin < 1.0 while neighbors are hostile or rearming.\n"
    "- Resource trap: very low reserve_years for key resources for several years in a row.\n"
    "- Relative decline: your gdp_share AND influence_score fall compared to main rivals.\n"
    "Do NOT choose policies that satisfy short-term goals but clearly push you toward these loss conditions.\n\n"
    "STATE SUMMARY (key fields in self_state):\n"
    "- economy   : GDP, capital, population, public_debt, rd_spending.\n"
    "- resources : own_reserve, production, consumption per resource.\n"
    "- society   : trust_gov, social_tension, inequality_gini.\n"
    "- climate   : climate_risk, co2_annual_emissions, biodiversity_local.\n"
    "- culture   : Hofstede (PDI, IDV, MAS, UAI, LTO, IND), Inglehart, regime_type.\n"
    "- risk      : water_stress, regime_stability, debt_crisis_prone, conflict_proneness.\n"
    "- political : legitimacy, protest_pressure, hawkishness, protectionism,\n"
    "              coalition_openness, sanction_propensity, policy_space.\n"
    "- competitive: gdp_share, gdp_rank, influence_score, security_margin,\n"
    "              reserve_years, debt_stress, protest_risk.\n"
    "- alliance_block: geopolitical bloc label.\n"
    "- neighbors (external_actors['neighbors']): trade_intensity, trade_barrier,\n"
    "  trust, conflict_level, gdp, military_power, alliance_block.\n\n"
    "- institutions (external_actors['institutions']): id, type, legitimacy,\n"
    "  mandate, members, active_rules.\n"
    "- institution_reports (external_actors['institution_reports']): per-org\n"
    "  global state summary and measures applied this step.\n\n"
    "BEHAVIORAL HETEROGENEITY (must obey):\n"
    "- Use your own regime_type, culture and alliance_block to shape policy.\n"
    "  * High PDI & low IDV & Autocracy: more state-directed investment,\n"
    "    more focus on security_margin, more tolerance for social_tension.\n"
    "  * Low PDI & high IDV & Democracy: avoid large tax/military shocks,\n"
    "    prioritize broad welfare and stability.\n"
    "  * High MAS: more comfortable with military_spending and competitive moves.\n"
    "  * High self-expression: more willing to adopt strong climate_policy.\n"
    "- Your decisions should NOT be generic. Countries with different income,\n"
    "  culture, climate_risk and emissions must not all choose the same mix.\n\n"
    "CLIMATE POLICY AS RISK MANAGEMENT (not a moral goal):\n"
    "- Use climate_policy only as one tool to protect your long-run economic power.\n"
    "- Consider stronger climate_policy when ALL are true:\n"
    "  * co2_annual_emissions are high for your size,\n"
    "  * climate_risk is high,\n"
    "  * you are relatively rich and stable (high GDP per capita, moderate tension),\n"
    "  * your culture/regime supports such moves (e.g. high self-expression).\n"
    "- Consider weak or no climate_policy when:\n"
    "  * you are poor or highly fragile (very low GDP per capita, high inequality/tension),\n"
    "  * you face acute security or resource threats that require priority.\n"
    "- It is WRONG for all countries to choose the same climate_policy. Your choice\n"
    "  must be justified by YOUR state, not by what would be globally ideal.\n\n"
    "FOREIGN POLICY GUIDANCE (by alliance_block):\n"
    "- Western : deepen trade and cooperation within Western/IndoPacific;\n"
    "           be cautious with Eurasian rivals.\n"
    "- Eurasian: build ties within block and with NonAligned/GlobalSouth;\n"
    "           treat Western military alliances carefully.\n"
    "- NonAligned/Latin/MENA: diversify partners to reduce dependence on any bloc.\n\n"
    "COERCION & SECURITY ACTIONS (use sparingly but decisively):\n"
    "- If neighbor conflict_level >= 0.45 AND trust <= 0.35, consider at least\n"
    "  one coercive tool (sanction, trade_restriction, or security_action) rather\n"
    "  than doing nothing.\n"
    "- Escalation ladder:\n"
    "  * military_exercise: signal resolve when conflict_level 0.35-0.55.\n"
    "  * arms_buildup: when security_margin < 1.1 OR neighbor rearming.\n"
    "  * border_incident: only when conflict_level > 0.60 AND trust < 0.30.\n"
    "  * conflict: only when conflict_level > 0.80 AND trust < 0.15 AND your\n"
    "    security_margin > 1.2 or you face severe resource survival threats.\n"
    "- Sanctions/trade restrictions should target specific rivals. Use mild by\n"
    "  default; strong only if sanction_propensity is high or conflict is severe.\n"
    "- Persistent passivity under high conflict is strategic weakness.\n\n"
    "TOOLS:\n"
    "- Domestic: tax_fuel_change, social/military/R&D spending, climate_policy.\n"
    "- Foreign : trade deals, sanctions (intent), trade_restrictions (intent), security_actions.\n"
    "- Finance : borrowing, FX reserves use.\n\n"
    "NOTE: Sanctions and trade_restrictions are INTENT signals. The model will\n"
    "apply endogenous political dynamics and social constraints before they\n"
    "become real actions.\n\n"
    "HEURISTICS (guidance only):\n"
    "- Low reserve_years  -> secure imports or invest in production capacity.\n"
    "- High debt_stress   -> limit borrowing and avoid big new spending.\n"
    "- Low security_margin & high neighbor conflict_level -> consider higher\n"
    "  military_spending or alliances, but avoid reckless wars.\n"
    "- Low gdp_share/influence_score -> expand trade and invest in growth,\n"
    "  without causing social collapse.\n"
    "- Large, fast policy swings that would clearly cause big GDP loss or\n"
    "  push trust_gov below 0.2 / tension above 0.8 should be avoided.\n\n"
    "You must output ONLY the JSON object following the schema below.\n\n"
    "CURRENT STATE:\n{obs_json}\n\n"
    "{schema_hint}\n"
)


def llm_policy(obs: Observation, memory_summary: Optional[Dict[str, Any]] = None) -> Action:
    payload: Dict[str, Any] = {
        "agent_id": obs.agent_id,
        "time": obs.time,
        "self_state": obs.self_state,
        "resource_balance": obs.resource_balance,
        "external_actors": obs.external_actors,
    }
    if memory_summary is not None:
        payload["memory_summary"] = memory_summary

    prompt = LLM_POLICY_PROMPT_TEMPLATE.format(
        obs_json=json.dumps(payload, ensure_ascii=False),
        schema_hint=LLM_SCHEMA_HINT,
    )

    try:
        raw = call_llm(prompt)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError(f"No JSON object found in LLM output: {raw!r}")

        data = json.loads(raw[start : end + 1])
        domestic = DomesticPolicy(**data["domestic_policy"])
        security_raw = data["foreign_policy"]["security_actions"]
        security_actions = SecurityActions(
            type=security_raw.get("type", "none"),
            target=_sanitize_target(security_raw.get("target")),
        )
        foreign = ForeignPolicy(
            proposed_trade_deals=[
                TradeDeal(**{k: v for k, v in deal.items() if k != "target"})
                for deal in data["foreign_policy"]["proposed_trade_deals"]
            ],
            sanctions_actions=[
                SanctionsAction(
                    target=_sanitize_target(sanction.get("target")) or "",
                    type=sanction.get("type", "none"),
                    reason=sanction.get("reason", ""),
                )
                for sanction in data["foreign_policy"]["sanctions_actions"]
                if _sanitize_target(sanction.get("target")) is not None
            ],
            trade_restrictions=[
                TradeRestriction(
                    target=_sanitize_target(restriction.get("target")) or "",
                    level=restriction.get("level", "none"),
                    reason=restriction.get("reason", ""),
                )
                for restriction in data["foreign_policy"].get("trade_restrictions", [])
                if _sanitize_target(restriction.get("target")) is not None
            ],
            security_actions=security_actions,
        )
        finance = FinancePolicy(**data["finance"])

        action = Action(
            agent_id=data["agent_id"],
            time=data["time"],
            domestic_policy=domestic,
            foreign_policy=foreign,
            finance=finance,
            explanation=data.get("explanation", ""),
        )
        return _normalize_action_for_stability(action)
    except Exception as exc:
        print(f"LLM policy error for {obs.agent_id}, falling back to simple policy: {exc}")
        return simple_rule_based_policy(obs)
