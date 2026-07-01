"""GIM17 assistant — a natural-language control layer over the engine API.

The assistant is a *tool-calling router*, not a number generator: every quantitative
claim must come from an engine run (the tools), which the LLM then narrates. Three
providers:

- ``deterministic`` — no LLM; a small rule-based intent router. Always available and
  fully testable (the default), so the chat works out-of-the-box.
- ``ollama`` — local models via ``/api/chat`` with tool-calling (fully offline).
- ``openai`` — OpenAI-compatible ``/chat/completions`` with tools (OpenAI or, via
  ``base_url``, DeepSeek / other compatible hosts).

The caller supplies a ``tool_executor(name, args) -> {"summary": str, "result": dict|None}``
that actually runs the engine, and an ``emit(event, data)`` sink for SSE.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

try:
    import requests  # type: ignore
    REQUESTS_AVAILABLE = True
except Exception:  # pragma: no cover
    REQUESTS_AVAILABLE = False

from .core.policy import (
    DEEPSEEK_API_URL,
    DEEPSEEK_MODEL,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_DEFAULT_URL,
)

Emit = Callable[[str, dict[str, Any]], None]
ToolExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]

SYSTEM_PROMPT = (
    "You are the GIM17 assistant — a natural-language control layer over a calibrated world "
    "simulator (economy, climate, geopolitics, ~57 countries). You help a decision-maker explore "
    "scenarios.\n\n"
    "CRITICAL: you do NOT know the numbers yourself. For ANY quantitative claim you MUST call a tool "
    "that runs the engine, and you cite the run. Never invent outcomes, probabilities or criticality.\n\n"
    "Modes are all reachable as tools. **run_composed is your default** for ANY free-form scenario: you "
    "author it by selecting calibrated levers (sanctions, alliance, proxy, maritime, resource, domestic, "
    "technology, cyber) and intensities, then the engine evaluates it. Map the user's situation to a "
    "combination of levers — e.g. a sieged economy → resource+sanctions; a tech war → technology+sanctions; "
    "internal collapse → domestic+resource. Use run_whatif ONLY for the named presets, and run_play to play "
    "as a country with a persona. "
    "When the user's request is missing required info (which country? which actors? which persona?), "
    "ASK one short clarifying question instead of guessing. If unsure which country/persona names are "
    "valid, call list_actors / list_personas first. Keep replies concise and in the user's language. "
    "After a run, the app ALREADY renders a card with the outcome distribution and criticality — do NOT "
    "re-list those numbers. Give a 1-2 sentence interpretation (what is driving the result, what to watch), "
    "strictly grounded in the tool result."
)

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_whatif",
            "description": "Run a 'what if' scenario; returns outcome distribution, criticality, drivers, trace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Scenario question (English works best)."},
                    "actors": {"type": "array", "items": {"type": "string"}, "description": "Country names to include (optional)."},
                    "horizon": {"type": "integer", "description": "Years to simulate, 1-8 (default 3)."},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_composed",
            "description": (
                "Compose a scenario on the fly from the calibrated lever ontology and evaluate it. This is "
                "your DEFAULT for any free-form scenario — prefer it over run_whatif (which is only for the "
                "named presets). You author the scenario by choosing levers: sanctions, alliance, proxy, "
                "maritime, resource, domestic, technology, cyber. Combine several to express a rich situation "
                "(e.g. resource+technology for an 'energy shock plus export controls'; cyber+domestic for "
                "'cyber attack and unrest'). If you don't pass explicit levers they are inferred from the text. "
                "Returns the outcome distribution, criticality, per-dimension readout (economy/society/climate/"
                "security) and a reproduce trace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Free-form scenario description (English works best)."},
                    "levers": {
                        "type": "array",
                        "description": "Explicit lever selection (optional but preferred when you can map the situation).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "lever": {"type": "string", "enum": ["sanctions", "alliance", "proxy", "maritime", "resource", "domestic", "technology", "cyber"]},
                                "magnitude": {"type": "number", "description": "Intensity 0.15-1.25 (default 0.6)."},
                            },
                            "required": ["lever"],
                        },
                    },
                    "actors": {"type": "array", "items": {"type": "string"}, "description": "Country names to involve (optional)."},
                    "horizon": {"type": "integer", "description": "Years to simulate: 0 = fast static score (default), 1-8 = full trajectory sim."},
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_play",
            "description": "Play as a country with a neutral persona archetype; runs a hybrid round.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {"type": "string"},
                    "persona": {"type": "string", "description": "Persona id from list_personas."},
                    "goal": {"type": "string", "description": "One-line strategic goal (optional)."},
                    "round_years": {"type": "integer"},
                },
                "required": ["country", "persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "doctrine_preview",
            "description": "Show how a persona shifts a country's doctrine (base vs shifted across 9 dimensions).",
            "parameters": {
                "type": "object",
                "properties": {"country": {"type": "string"}, "persona": {"type": "string"}},
                "required": ["country", "persona"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_actors",
            "description": "List the country names available in the model.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_personas",
            "description": "List persona archetype ids and names.",
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


def run_assistant_turn(messages: list[dict[str, Any]], config: AssistantConfig,
                       tool_executor: ToolExecutor, emit: Emit) -> None:
    """Drive one assistant turn: tool-call loop until the model produces a text reply."""
    if config.provider == "deterministic" or not REQUESTS_AVAILABLE:
        _deterministic_turn(messages, tool_executor, emit)
        return

    convo: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}] + list(messages)
    last_summary = ""
    for _ in range(max(1, config.max_steps)):
        message = _chat(config, convo)
        content = str(message.get("content") or "")
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            # Some models (notably via Ollama) emit a tool call as JSON in the
            # text content instead of the structured ``tool_calls`` field. Recover
            # it so the tool still runs rather than dumping raw JSON to the user.
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
            last_summary = str(out.get("summary", "")) or last_summary
            convo.append({
                "role": "tool",
                "tool_call_id": call.get("id", name),
                "name": name,
                "content": str(out.get("summary", "")),
            })
    # Hit the step cap: fall back to the last tool summary so the user still gets
    # the engine's answer instead of a bare "limit reached" notice.
    emit("assistant_delta", {"text": last_summary or "Достигнут лимит шагов инструментов."})
    emit("done", {})


def _json_objects(text: str) -> list[dict[str, Any]]:
    """Extract top-level balanced JSON objects from free text (ignoring braces
    inside strings). Tolerates markdown fences and surrounding prose."""
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
    """Recover ``{"name": ..., "arguments": {...}}`` tool calls a model emitted as
    plain text, mapping only to tools we actually expose."""
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

    # openai-compatible hosts. ``deepseek`` is a first-class provider so the user
    # never has to know DeepSeek's base URL — picking "openai" with a DeepSeek key
    # and no base_url would otherwise hit api.openai.com and 401.
    if config.provider == "deepseek":
        base = (config.base_url or "https://api.deepseek.com").rstrip("/")
        key = (config.api_key or os.getenv("DEEPSEEK_API_KEY") or "").strip()
        model = config.model or DEEPSEEK_MODEL
    else:  # openai (or any custom OpenAI-compatible host via base_url)
        base = (config.base_url or "https://api.openai.com/v1").rstrip("/")
        key = (config.api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        model = config.model or ("deepseek-chat" if "deepseek" in base else "gpt-4o-mini")
    payload = {"model": model, "messages": messages, "tools": TOOLS, "temperature": config.temperature}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    resp = requests.post(f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


# --------------------------------------------------------------------------- #
# Deterministic provider — rule-based intent router (no LLM required)
# --------------------------------------------------------------------------- #

_PRESETS = [
    (("hormuz", "ормуз", "пролив", "strait"), "How will Hormuz tensions escalate?",
     ["Iran", "United States", "Israel"]),
    (("taiwan", "тайвань"), "Will a Taiwan blockade escalate?", ["China", "United States"]),
    (("sanction", "санкц"), "Will the sanctions spiral deepen?", ["Russia", "United States", "Germany"]),
]

_PERSONA_SYNONYMS = {
    "hawk": ("ястреб", "hawk", "протекц", "war"),
    "dove": ("голуб", "dove", "миролюб", "peace"),
    "tech": ("технократ", "technocrat", "tech"),
}


def _last_user(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _run_and_report(tool: str, args: dict[str, Any], tool_executor: ToolExecutor, emit: Emit) -> None:
    emit("tool_call", {"name": tool, "args": args})
    out = tool_executor(tool, args)
    if out.get("result") is not None:
        # The result card already shows verdict + distribution + criticality, so
        # don't also emit the text summary (it duplicated the card in the chat).
        emit("run_result", out["result"])
    else:
        emit("assistant_delta", {"text": str(out.get("summary", ""))})
    emit("done", {})


def _match_persona(low: str, personas: list[dict[str, Any]]) -> str | None:
    for persona in personas:
        pid = str(persona.get("id", ""))
        name_ru = str(persona.get("name_ru", "")).lower()
        for family, syns in _PERSONA_SYNONYMS.items():
            if family in pid.lower() and any(s in low for s in syns):
                return pid
        if name_ru and name_ru.split(" ")[0] in low:
            return pid
    return None


def _deterministic_turn(messages: list[dict[str, Any]], tool_executor: ToolExecutor, emit: Emit) -> None:
    low = _last_user(messages).lower()

    for keys, question, actors in _PRESETS:
        if any(k in low for k in keys):
            _run_and_report("run_whatif", {"question": question, "actors": actors}, tool_executor, emit)
            return

    if "играть" in low or "play as" in low or "сыграть" in low or "играю" in low:
        actors = (tool_executor("list_actors", {}).get("result") or {}).get("actors", [])
        found = next((a for a in actors if a.lower() in low), None)
        if not found:
            emit("assistant_delta", {"text": "За какую страну сыграем? И какой архетип — ястреб, голубь или технократ?"})
            emit("done", {})
            return
        personas = (tool_executor("list_personas", {}).get("result") or {}).get("personas", [])
        persona = _match_persona(low, personas)
        if not persona:
            emit("assistant_delta", {"text": f"Хорошо — играем за {found}. Какой архетип: ястреб, голубь или технократ?"})
            emit("done", {})
            return
        _run_and_report("run_play", {"country": found, "persona": persona}, tool_executor, emit)
        return

    # Free-form scenario: if any calibrated lever fires on the text, compose it
    # on the fly. This is what makes the no-LLM provider build arbitrary scenarios
    # instead of only matching the three presets above.
    from .scenario_ontology import match_levers

    if match_levers(_last_user(messages)):
        _run_and_report("run_composed", {"question": _last_user(messages)}, tool_executor, emit)
        return

    emit("assistant_delta", {"text": (
        "Я прогоняю сценарии на движке GIM17. Примеры: «что если закроют Ормуз?», "
        "«играть за Германию как технократ», «Тайвань — блокада». Числа — всегда из прогона, со ссылкой "
        "на команду воспроизведения.\n\nПодключите локальную модель (Ollama) или ключ OpenAI в настройках "
        "— и я смогу свободнее рассуждать, уточнять детали и предлагать варианты."
    )})
    emit("done", {})
