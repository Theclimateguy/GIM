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

SYSTEM_PROMPT = (
    "You are the GIM17 v2 analyst — a natural-language control layer over a CALIBRATED, "
    "VALIDATED deterministic world model (economy + climate + resources, ~57 countries). "
    "You help a strategic planner stress-test a decision against cross-sector cascades and "
    "tail risks.\n\n"
    "CRITICAL: you do NOT know the numbers. For ANY quantitative claim you MUST call `run_answer`, "
    "which runs the engine; you only narrate its result. Never invent deltas, thresholds, winners or "
    "losers.\n\n"
    "`run_answer` is your tool. Map the user's strategic question to EITHER a named mixed-scenario "
    "`archetype` (call `list_archetypes` to see them — energy_war, stagflation_decade, sanctions_spiral, "
    "green_transition_shock, food_social, supply_chain_break, sovereign_stress, soft_landing) OR an "
    "explicit set of grounded `levers` (call `list_levers` — carbon_price, decarbonization, growth, "
    "energy_shock, food_shock, trade_sanctions, stagflation) with intensities. Pass `actors` (country "
    "names) for trade/sanctions levers. Prefer an archetype when one clearly fits; otherwise compose "
    "levers. If the request is too vague to map, ASK one short clarifying question instead of guessing.\n\n"
    "After a run, the app ALREADY renders a Situation Room (verdict, metric cards, cascade, threshold, "
    "winners/losers, map) — do NOT re-list those numbers. Give a 1-2 sentence interpretation: what drives "
    "the result and what to watch, strictly grounded in the tool result. Reply in the user's language."
)

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
                        "items": {
                            "type": "object",
                            "properties": {
                                "lever": {
                                    "type": "string",
                                    "enum": list(L.GROUNDED_LEVERS.keys()),
                                },
                                "magnitude": {"type": "number", "description": "Intensity 0.15-1.25 (default 0.6)."},
                            },
                            "required": ["lever"],
                        },
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
