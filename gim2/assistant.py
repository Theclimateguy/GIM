"""GIM17 v2 assistant — natural-language control layer over the deterministic engine.

A *tool-calling router*, not a number generator: every quantitative claim comes from
an engine run (``run_answer`` → ``compute_answer``), which the LLM only narrates.
Ported from the v1 assistant but pointed at the **validated deterministic** modes.

Providers: ``deterministic`` (rule-based, no LLM, always works), ``ollama`` (local),
``openai`` (OpenAI-compatible incl. DeepSeek via ``base_url``). The caller supplies a
``tool_executor(name, args) -> {"summary": str, "result": dict|None}`` and an
``emit(event, data)`` SSE sink.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

try:
    import requests  # type: ignore

    REQUESTS_AVAILABLE = True
except Exception:  # pragma: no cover
    REQUESTS_AVAILABLE = False

from gim.core.policy import (
    DEEPSEEK_MODEL,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_DEFAULT_URL,
)

from . import archetypes as A
from . import levers as L

Emit = Callable[[str, dict[str, Any]], None]
ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

MODEL_MECHANICS = (
    "MODEL MECHANICS (ground every 'why'/'what drives this' answer in these actual causal channels — "
    "do not hand-wave):\n"
    "- Economy: CES production over capital/labor/energy per country-agent (ALPHA_CAPITAL, BETA_LABOR, "
    "GAMMA_ENERGY govern the mix; CAPITAL_DEPRECIATION and TFP_RD_SHARE_SENS drive capital/productivity "
    "growth). world_gdp is the sum of agent GDPs.\n"
    "- Climate: emissions (EMISSIONS_SCALE, DECARB_RATE_STRUCTURAL, land use, carbon feedbacks) accumulate "
    "into CO2, which drives temperature via a two-layer heat-capacity model (HEAT_CAP_SURFACE/DEEP, "
    "OCEAN_EXCHANGE, ECS_DEFAULT = equilibrium climate sensitivity). Temperature feeds back into GDP via a "
    "quadratic damage function (DAMAGE_QUAD_COEFF, with an optional benefit region at low warming).\n"
    "- Society/conflict: social_tension per agent responds to economic stress, migration pressure and "
    "resource scarcity; crosses thresholds into debt crises, regime crises, wars, and conflict_risk "
    "(CRISIS_SEVERITY_ALPHA, REGIME_COLLAPSE_*). Migration flows between agents respond to income and "
    "conflict push factors (MIGRATION_*).\n"
    "- Levers are grounded, structural interventions (carbon_price, decarbonization, growth, energy_shock, "
    "food_shock, trade_sanctions, stagflation) — each maps to specific parameter/pulse changes, not a "
    "generic multiplier; `list_levers` gives the exact mapping.\n"
    "- Sensitivity (Morris μ*): the mean absolute elementary effect of a calibrated parameter on a metric, "
    "screened over its full prior range — a bigger μ* means that assumption, not the scenario itself, is "
    "what's driving the uncertainty in the answer. Use it to answer 'what assumption matters most here'.\n"
    "- Weak signals: three independent, complementary diagnostics over a trajectory's state-space dynamics "
    "— Mahalanobis distance (is the joint state in an unusual region vs. its own recent history), "
    "structural breaks (did a metric's level shift, Bayesian change-point), and critical slowing down "
    "(rising autocorrelation/variance — a tipping-point precursor, but ONLY trustworthy on a stochastic "
    "ensemble; on a single deterministic trajectory treat a 'warning' as a hint to dig further with "
    "run_ensemble, not a confirmed diagnosis — say so explicitly if you cite it)."
)

#: Layer 2 — a decision table, not prose. LLMs (this one included — DeepSeek-chat in
#: production use kept defaulting to run_answer on an obvious run_sensitivity follow-up
#: question) follow a short "pattern → action" table far more reliably than a paragraph
#: of "use X for Y"-style guidance buried among other instructions.
TOOL_ROUTING_TABLE = (
    "TOOL ROUTING TABLE — match the user's question to a row, call that tool. Do not narrate without "
    "calling a tool first; you do not know the numbers.\n"
    "| question pattern                                          | tool               |\n"
    "| new strategic what-if, no scenario active yet             | run_answer         |\n"
    "| what drives / most sensitive to / which assumption matters| run_sensitivity    |\n"
    "| stable / tipping point / regime shift / warning signs      | run_weak_signals   |\n"
    "| how much lever is enough / is the effect linear            | run_dose_response  |\n"
    "| how uncertain is the baseline itself / what's normal        | run_ensemble       |\n"
    "| quick re-check of a lever combo, no cascade/actors needed  | run_scenario       |\n"
    "| what scenarios/levers exist                                | list_archetypes / list_levers |\n"
    "If nothing fits clearly, ASK one short clarifying question instead of guessing."
)

SYSTEM_PROMPT = (
    "You are the GIM17 v2 analyst — a natural-language control layer over a CALIBRATED, "
    "VALIDATED deterministic world model (economy + climate + resources, ~57 countries). "
    "You help a strategic planner stress-test a decision against cross-sector cascades and "
    "tail risks — and, within a session, dig into WHY the model produced a given answer.\n\n"
    "CRITICAL: you do NOT know the numbers. For ANY quantitative claim you MUST call a tool; you only "
    "narrate its result. Never invent deltas, thresholds, winners, losers, μ* rankings or anomaly counts.\n\n"
    f"{TOOL_ROUTING_TABLE}\n\n"
    "TOOL PARAMETERS — `run_answer`: EITHER a named `archetype` (list_archetypes) OR explicit `levers` "
    "(list_levers) with intensities; `actors` for trade/sanctions levers; prefer an archetype when one "
    "clearly fits. `run_scenario`/`run_sensitivity`/`run_weak_signals` all accept the SAME `levers` shape — "
    "when a scenario is already active in this session (see below), pass its EXACT SAME levers so you're "
    "analyzing that scenario, not a fresh baseline.\n\n"
    f"{MODEL_MECHANICS}\n\n"
    "CONVERSATION HISTORY & TOOL RESULTS: past tool calls in this session appear as compact `tool`-role "
    "summaries (verdict/key deltas/rankings — NOT the full time-series/ensemble arrays, to keep context "
    "small). Treat them as ground truth for follow-up reasoning ('why did that happen', 'what if we push "
    "harder') — you do not need to re-run a tool just to recall a past result. Re-run only when you need "
    "genuinely new numbers (a different lever, metric, magnitude, or fresh full-detail data). If the "
    "conversation is long, keep your own replies compact — the app may summarize older turns further "
    "before they reach you; do not assume you remember more than what's in the current message list.\n\n"
    "After a run_answer, the app ALREADY renders a Situation Room (verdict, metric cards, cascade, "
    "threshold, winners/losers, map) — do NOT re-list those numbers. Give a 1-2 sentence interpretation: "
    "what drives the result and what to watch, strictly grounded in the tool result and the mechanics "
    "above. For the other tools, narrate the key numbers yourself (they render only a compact summary, no "
    "card).\n\n"
    "LANGUAGE: reply in the SAME language as the user's latest message. If that message is in Russian, "
    "answer in standard literary Russian ONLY — never Ukrainian, Belarusian, Bulgarian, Surzhyk, or a "
    "mixed/transliterated form, and never switch language mid-answer. Keep discussing the computed scenario "
    "and its results freely; only the language of the reply is constrained."
)

#: Layer 1: the app tracks which scenario (if any) is already established in this session
#: (from the last successful run_answer/run_scenario's `selection`) and hands it back
#: structurally every turn — the model no longer has to re-infer "what scenario are we
#: even talking about" from its own past prose, which was unreliable.
def _active_scenario_block(active_levers: dict[str, float] | None, active_actors: list[str] | None) -> str:
    if not active_levers:
        return ""
    recipe = ", ".join(f"{k}={v:.2g}" for k, v in active_levers.items())
    actors_part = f"; actors={list(active_actors)}" if active_actors else ""
    return (
        "\n\nACTIVE SCENARIO IN THIS SESSION — levers: {" + recipe + "}" + actors_part + ". A scenario is "
        "ALREADY established. If the new question is about THIS scenario (why / sensitivity / stability / "
        "dose), call run_sensitivity / run_weak_signals / run_dose_response / run_ensemble WITH THESE EXACT "
        "SAME levers — do NOT call run_answer again just to re-narrate the same thing. Only call "
        "run_answer/list_archetypes again if the user clearly asks for a DIFFERENT or NEW scenario."
    )


#: Layer 3: a soft, keyword-based nudge for the common cases the LLM keeps missing (a
#: safety net alongside the routing table, not a replacement for it — never force-calls
#: a tool, just raises its priority for this turn when an active scenario already exists).
_FOLLOWUP_HINTS: list[tuple[tuple[str, ...], str, str]] = [
    (("чувствит", "фактор", "предположен", "завис"), "run_sensitivity",
     "спрашивает, что сильнее всего влияет / от каких допущений зависит результат"),
    (("устойч", "переломн", "тревожн", "срыв", "разладк", "аномал", "критическ", "режим"), "run_weak_signals",
     "спрашивает про устойчивость / риск срыва в другой режим / предвестники"),
    (("sensitiv", "assumption", "what drives", "most affect"), "run_sensitivity",
     "asks what drives the result / which assumption matters most"),
    (("tipping", "regime shift", "stabilit", "warning sign"), "run_weak_signals",
     "asks about stability / tipping risk / early warnings"),
    (("сколько нужно", "линейн", "порог", "насколько сильно"), "run_dose_response",
     "спрашивает, сколько рычага нужно и линеен ли эффект"),
    (("how much", "is it linear", "threshold"), "run_dose_response",
     "asks how much lever is enough / whether the effect is linear"),
]


def _suggest_followup_tool(text: str, has_active_scenario: bool) -> tuple[str, str] | None:
    if not has_active_scenario or not text:
        return None
    low = text.lower()
    for stems, tool, reason in _FOLLOWUP_HINTS:
        if any(stem in low for stem in stems):
            return tool, reason
    return None

_LEVER_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "lever": {"type": "string", "enum": list(L.GROUNDED_LEVERS.keys())},
        "magnitude": {"type": "number", "description": "Intensity 0.15-1.25 (default 0.6)."},
    },
    "required": ["lever"],
}

_METRIC_ENUM_ALL = ["world_gdp", "world_population", "temperature", "co2", "n_debt_crises",
                    "n_regime_crises", "n_wars", "mean_social_tension", "conflict_risk"]
_METRIC_ENUM_SENSITIVITY = ["world_gdp", "temperature", "co2", "mean_social_tension"]

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_answer",
            "description": (
                "Run a strategic-question answer on the deterministic engine. Provide EITHER an "
                "`archetype` id OR an explicit `levers` list; if you pass neither, levers are inferred "
                "from `question`. Returns a decision card: verdict, metric delta fans, cross-domain "
                "cascade, threshold, per-actor winners/losers and a map payload."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The user's scenario/strategic question."},
                    "archetype": {
                        "type": "string",
                        "description": "Named mixed-scenario id from list_archetypes (preferred when one fits).",
                    },
                    "levers": {
                        "type": "array",
                        "description": "Explicit grounded levers when no archetype fits.",
                        "items": _LEVER_ITEM_SCHEMA,
                    },
                    "actors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Country names for trade/sanctions levers (optional).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_scenario",
            "description": (
                "Focused scenario-vs-baseline delta run: explicit grounded `levers` only, no cascade/"
                "actors/threshold. Returns per-metric delta fans (median, IQR, 5-95) vs the validated "
                "baseline. Cheaper and narrower than run_answer — use for a quick re-check or to set up a "
                "sensitivity/weak-signals follow-up on the same scenario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "levers": {"type": "array", "items": _LEVER_ITEM_SCHEMA},
                    "actors": {"type": "array", "items": {"type": "string"}},
                    "years": {"type": "integer", "description": "Horizon in years (default 10)."},
                },
                "required": ["levers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_ensemble",
            "description": (
                "Pure baseline ensemble (no levers): per-metric uncertainty fans (median, IQR, 5-95) over "
                "the priors. Use for 'how uncertain is the baseline' or to contrast against a scenario."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "years": {"type": "integer", "description": "Horizon in years (default 10)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_dose_response",
            "description": (
                "Sweeps ONE grounded lever's magnitude over a grid (0, 0.25, 0.5, 0.75, 1.0, 1.25) and "
                "reports the terminal delta of one metric at each point. Use for 'how much of X is enough "
                "to matter' or 'is the effect linear/threshold-like' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lever": {"type": "string", "enum": list(L.GROUNDED_LEVERS.keys())},
                    "metric": {"type": "string", "enum": _METRIC_ENUM_ALL},
                    "actors": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["lever"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sensitivity",
            "description": (
                "Morris screening of the 33 calibrated parameters against one metric: returns mu* ranking "
                "(which assumptions drive the output most). Optionally pass `levers` to screen AROUND an "
                "already-established scenario instead of the plain baseline. Use for 'what assumption "
                "matters most' / 'what are we uncertain about' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": _METRIC_ENUM_SENSITIVITY},
                    "levers": {"type": "array", "items": _LEVER_ITEM_SCHEMA,
                              "description": "Optional: screen around this scenario instead of the baseline."},
                    "actors": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_weak_signals",
            "description": (
                "Scans a scenario's trajectory (or the baseline, if no levers) for early-warning signs: "
                "Mahalanobis joint-state anomalies, per-metric structural breaks, and critical-slowing-down "
                "trends. Use for 'is this scenario nearing a regime shift / tipping point' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "levers": {"type": "array", "items": _LEVER_ITEM_SCHEMA,
                              "description": "Optional: scan this scenario instead of the plain baseline."},
                    "actors": {"type": "array", "items": {"type": "string"}},
                    "years": {"type": "integer", "description": "Horizon in years, min 12 (default 20)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_archetypes",
            "description": "List the named mixed-scenario archetypes (id, name, what they combine).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_levers",
            "description": "List the grounded levers (id, label, what they map to in the core).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


@dataclass
class AssistantConfig:
    provider: str = "deterministic"  # deterministic | ollama | openai
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.3
    max_steps: int = 5


_METRIC_SNIFF: list[tuple[tuple[str, ...], str]] = [
    (("температур", "temperature", "потепл", "warming"), "temperature"),
    (("co2", "выброс", "эмисс", "emission"), "co2"),
    (("напряж", "tension", "конфликт", "conflict"), "mean_social_tension"),
]


def _sniff_metric(text: str) -> str:
    low = text.lower()
    for stems, metric in _METRIC_SNIFF:
        if any(stem in low for stem in stems):
            return metric
    return "world_gdp"


def run_assistant_turn(messages: list[dict[str, Any]], config: AssistantConfig,
                       tool_executor: ToolExecutor, emit: Emit, *,
                       active_levers: dict[str, float] | None = None,
                       active_actors: list[str] | None = None) -> None:
    """Drive one assistant turn: tool-call loop until the model produces a text reply.

    `active_levers`/`active_actors` — the recipe of the last scenario successfully computed
    in THIS session (the app tracks it; see AppState.activeSelection on the Swift side) — Layers
    1+4: hands the model a structural fact ("a scenario is already established, and here it
    is") instead of expecting it to infer that from its own past narration.

    Emits a `trace` SSE event at each key decision point (system prompt actually sent,
    forced-route decisions, each raw model step) — this is what the in-app "Трейс агента"
    view renders; it exists because a soft "ROUTING HINT" system-prompt addition, even
    layered on top of an explicit active-scenario block, was empirically NOT enough to make
    DeepSeek-chat reliably switch off run_answer for an obvious run_sensitivity follow-up
    (verified against real captured sessions) — hence Layer 3 below force-calls the matched
    tool directly rather than just suggesting it, and the trace exists so this class of
    "did the model even see the hint" question is answerable by looking, not re-guessing.
    """
    if config.provider == "deterministic" or not REQUESTS_AVAILABLE:
        _deterministic_turn(messages, tool_executor, emit)
        return

    system_content = SYSTEM_PROMPT + _active_scenario_block(active_levers, active_actors)
    emit("trace", {"kind": "system_prompt", "text": system_content})

    last_user_text = _last_user(messages)
    hint = _suggest_followup_tool(last_user_text, bool(active_levers))

    if hint:
        tool, reason = hint
        emit("trace", {"kind": "forced_route",
                       "text": f"forced {tool} — {reason} (active_levers={active_levers})"})
        args: dict[str, Any] = {"levers": [f"{k}={v}" for k, v in (active_levers or {}).items()]}
        if active_actors:
            args["actors"] = list(active_actors)
        if tool in ("run_sensitivity", "run_dose_response"):
            args["metric"] = _sniff_metric(last_user_text)
        if tool == "run_dose_response":
            args["lever"] = next(iter((active_levers or {}).keys()), "growth")
        emit("tool_call", {"name": tool, "args": args})
        out = tool_executor(tool, args)
        if out.get("result") is not None:
            emit("run_result", out["result"])
        # Ask the LLM to narrate the forced tool's result against the user's actual
        # question — this keeps the reply natural-language while guaranteeing the RIGHT
        # tool ran, rather than trusting the model to have chosen it itself.
        convo = [{"role": "system", "content": system_content}] + list(messages) + [{
            "role": "tool", "tool_call_id": tool, "name": tool, "content": str(out.get("summary", "")),
        }]
        try:
            message = _chat(config, convo)
            text = str(message.get("content") or "").strip() or str(out.get("summary", ""))
        except Exception as exc:  # noqa: BLE001 — still deliver the forced tool's own summary
            text = str(out.get("summary", "")) or f"(не удалось получить нарратив от модели: {exc})"
        emit("trace", {"kind": "model_reply", "text": text})
        emit("assistant_delta", {"text": text})
        emit("done", {})
        return

    convo: list[dict[str, Any]] = [{"role": "system", "content": system_content}] + list(messages)
    last_summary = ""
    for _ in range(max(1, config.max_steps)):
        message = _chat(config, convo)
        content = str(message.get("content") or "")
        tool_calls = message.get("tool_calls") or []
        emit("trace", {"kind": "model_step",
                       "text": f"content={content!r} tool_calls={[c.get('function',{}).get('name') for c in tool_calls]}"})
        if not tool_calls:
            tool_calls = _extract_text_tool_calls(content)
        if not tool_calls:
            emit("assistant_delta", {"text": content})
            emit("done", {})
            return
        convo.append(message)
        for call in tool_calls:
            fn = call.get("function", {}) or {}
            name = str(fn.get("name", ""))
            raw_args = fn.get("arguments")
            args = raw_args if isinstance(raw_args, dict) else _safe_json(raw_args)
            emit("tool_call", {"name": name, "args": args})
            out = tool_executor(name, args)
            if out.get("result") is not None:
                emit("run_result", out["result"])
            emit("trace", {"kind": "tool_result", "text": f"{name}: {str(out.get('summary',''))[:400]}"})
            last_summary = str(out.get("summary", "")) or last_summary
            convo.append({
                "role": "tool",
                "tool_call_id": call.get("id", name),
                "name": name,
                "content": str(out.get("summary", "")),
            })
    emit("assistant_delta", {"text": last_summary or "Достигнут лимит шагов инструментов."})
    emit("done", {})


# --------------------------------------------------------------------------- #
# tool-call recovery / JSON helpers (ported from v1)
# --------------------------------------------------------------------------- #


def _json_objects(text: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    value = json.loads(text[start:i + 1])
                    if isinstance(value, dict):
                        objects.append(value)
                except Exception:
                    pass
                start = -1
    return objects


def _extract_text_tool_calls(content: str) -> list[dict[str, Any]]:
    valid = {tool["function"]["name"] for tool in TOOLS}
    calls: list[dict[str, Any]] = []
    for blob in _json_objects(content):
        name = blob.get("name")
        if isinstance(name, str) and name in valid:
            args = blob.get("arguments", blob.get("parameters", {}))
            if isinstance(args, str):
                args = _safe_json(args)
            calls.append({"function": {"name": name, "arguments": args if isinstance(args, dict) else {}}})
    return calls


def _safe_json(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _chat(config: AssistantConfig, messages: list[dict[str, Any]]) -> dict[str, Any]:
    timeout = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
    if config.provider == "ollama":
        base = (config.base_url or os.getenv("OLLAMA_BASE_URL") or OLLAMA_DEFAULT_URL).rstrip("/")
        model = config.model or os.getenv("OLLAMA_MODEL") or OLLAMA_DEFAULT_MODEL
        payload = {"model": model, "messages": messages, "tools": TOOLS, "stream": False,
                   "options": {"temperature": config.temperature}}
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("message", {}) or {}

    base = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    key = (config.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
    model = config.model or (DEEPSEEK_MODEL if "deepseek" in base else "gpt-4o-mini")
    payload = {"model": model, "messages": messages, "tools": TOOLS, "temperature": config.temperature}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


# --------------------------------------------------------------------------- #
# Connection probe — powers the "Проверить" button in settings
# --------------------------------------------------------------------------- #


def _api_error_message(resp: Any) -> str:
    """Extract the provider's actual error text from a non-2xx body. This is what
    `requests.raise_for_status()` throws away — leaving the user with a bare
    '400 Bad Request' and no idea that e.g. the model name is wrong."""
    try:
        data = resp.json()
        err = data.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("type") or err.get("code")
            if msg:
                return f"{resp.status_code}: {msg}"
        if isinstance(err, str) and err:
            return f"{resp.status_code}: {err}"
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            return f"{resp.status_code}: {data['message']}"
    except Exception:
        pass
    body = (getattr(resp, "text", "") or "").strip()
    return f"{resp.status_code}: {body[:300]}" if body else f"HTTP {resp.status_code}"


def probe_llm(config: AssistantConfig) -> dict[str, Any]:
    """Minimal connectivity / auth / model probe for the configured provider. Mirrors a real
    `_chat` request — including the tool payload the assistant *requires* (so a model that
    can't do function-calling is reported as failing, which is the truth for this app) — but
    with a one-token message. Returns the provider's actual error message on failure."""
    if config.provider == "deterministic":
        return {"ok": True, "provider": "deterministic", "note": "правила, без LLM — соединение не нужно"}
    if not REQUESTS_AVAILABLE:
        return {"ok": False, "error": "модуль requests недоступен в движке"}

    probe = [{"role": "user", "content": "ping"}]
    timeout = float(os.getenv("LLM_PROBE_TIMEOUT_SEC", "20"))
    t0 = time.time()
    try:
        if config.provider == "ollama":
            base = (config.base_url or os.getenv("OLLAMA_BASE_URL") or OLLAMA_DEFAULT_URL).rstrip("/")
            model = config.model or os.getenv("OLLAMA_MODEL") or OLLAMA_DEFAULT_MODEL
            payload = {"model": model, "messages": probe, "stream": False,
                       "options": {"temperature": 0.0, "num_predict": 1}}
            resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        else:
            base = (config.base_url or "https://api.openai.com/v1").rstrip("/")
            key = (config.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "").strip()
            model = config.model or (DEEPSEEK_MODEL if "deepseek" in base else "gpt-4o-mini")
            if not key:
                return {"ok": False, "model": model, "error": "не указан API-ключ"}
            payload = {"model": model, "messages": probe, "tools": TOOLS,
                       "max_tokens": 1, "temperature": 0.0}
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)

        latency = int((time.time() - t0) * 1000)
        if resp.status_code // 100 == 2:
            return {"ok": True, "model": model, "status": resp.status_code, "latency_ms": latency}
        return {"ok": False, "model": model, "status": resp.status_code, "latency_ms": latency,
                "error": _api_error_message(resp)}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": f"таймаут {timeout:.0f} c — хост не отвечает"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "не удалось подключиться к хосту (проверьте Base URL и сеть)"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc) or exc.__class__.__name__}


# --------------------------------------------------------------------------- #
# Deterministic provider — rule-based router (no LLM required)
# --------------------------------------------------------------------------- #

# Question -> archetype. Each archetype lists stem-GROUPS; a group matches when ALL
# its stems appear (order-independent, inflection-robust). First archetype wins.
_ARCH_KEYWORDS: list[tuple[list[tuple[str, ...]], str]] = [
    ([("энергетическ", "войн"), ("energy", "war"), ("энергокризис",), ("энергетическ", "кризис")], "energy_war"),
    ([("стагфляц",), ("stagflation",)], "stagflation_decade"),
    ([("санкц",), ("sanctions",), ("эмбарго",)], "sanctions_spiral"),
    ([("зелён", "переход"), ("декарбон",), ("цена", "углерод"), ("green", "transition"), ("carbon", "price")], "green_transition_shock"),
    ([("продовольств",), ("урожай",), ("food",), ("голод",), ("famine",)], "food_social"),
    ([("цепочк", "поставок"), ("supply", "chain"), ("логистическ",)], "supply_chain_break"),
    ([("суверенн", "долг"), ("долгов", "кризис"), ("sovereign", "debt")], "sovereign_stress"),
    ([("мягк", "посадк"), ("soft", "landing")], "soft_landing"),
]


def _last_user(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _run_and_report(args: dict[str, Any], tool_executor: ToolExecutor, emit: Emit) -> None:
    emit("tool_call", {"name": "run_answer", "args": args})
    out = tool_executor("run_answer", args)
    if out.get("result") is not None:
        emit("run_result", out["result"])
    if out.get("summary"):
        emit("assistant_delta", {"text": str(out["summary"])})
    emit("done", {})


def _deterministic_turn(messages: list[dict[str, Any]], tool_executor: ToolExecutor, emit: Emit) -> None:
    text = _last_user(messages)
    low = text.lower()

    for groups, archetype in _ARCH_KEYWORDS:
        if any(all(stem in low for stem in grp) for grp in groups):
            _run_and_report({"archetype": archetype, "question": text}, tool_executor, emit)
            return

    # Free-form: if any grounded lever fires on the text, compose it on the fly.
    fired = L.match_levers(text)
    if fired:
        _run_and_report({"levers": [{"lever": l} for l in fired], "question": text}, tool_executor, emit)
        return

    names = ", ".join(a.name_ru for a in A.ARCHETYPES.values())
    emit("assistant_delta", {"text": (
        "Я прогоняю стратегические вопросы на детерминированном движке GIM17 и собираю карту ответа "
        "(вердикт, пороги, каскад, состояния стран). Спросите про шок или назовите сценарий — например: "
        "«что если энергошок и санкции против крупного экспортёра?», «десятилетие стагфляции», "
        "«шок зелёного перехода».\n\n"
        f"Готовые типовые сценарии: {names}.\n\n"
        "Подключите Ollama или ключ OpenAI в настройках — и я смогу свободнее разбирать формулировки "
        "и сам подбирать рычаги. Числа — всегда из прогона."
    )})
    emit("done", {})


__all__ = ["AssistantConfig", "run_assistant_turn", "probe_llm", "TOOLS", "SYSTEM_PROMPT"]
