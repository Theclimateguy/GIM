from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from typing import Any

from .decision_language import labelize, risk_label, top_driver_entries
from .explanations import DRIVER_LABELS
from .model_terms import TERM_EXPLANATIONS

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False


DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

WAR_KEYWORDS = (
    "war",
    "invasion",
    "attack",
    "strike",
    "conflict",
    "войн",
    "удар",
    "конфликт",
    "вторжен",
)


@dataclass(frozen=True)
class InterpretiveSummary:
    paragraphs: list[str]
    source: str
    note: str | None = None

    @property
    def source_label(self) -> str:
        if self.source == "llm":
            return "DeepSeek synthesis"
        return "Deterministic fallback"


def build_interpretive_summary(
    payload: dict[str, Any],
    *,
    prefer_llm: bool = True,
) -> InterpretiveSummary:
    facts = _build_facts(payload)
    if prefer_llm:
        llm_summary = _try_llm_summary(facts)
        if llm_summary is not None:
            return llm_summary
    return _deterministic_summary(facts)


def _build_facts(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = payload["scenario"]
    evaluation = payload["evaluation"]
    trajectory = payload.get("trajectory") or []
    actor_names = list(scenario.get("actor_names") or [])
    top_outcomes = [
        {
            "name": risk_name,
            "label": risk_label(risk_name),
            "probability": float(probability),
        }
        for risk_name, probability in sorted(
            (evaluation.get("risk_probabilities") or {}).items(),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
    ]
    top_drivers = [
        {
            "name": name,
            "label": DRIVER_LABELS.get(name, labelize(name)),
            "value": float(value),
            "explanation": TERM_EXPLANATIONS.get(name, "Model-defined driver term."),
        }
        for name, value in top_driver_entries(evaluation, 3)
    ]

    dashboard_agents = (evaluation.get("crisis_dashboard") or {}).get("agents", {})
    primary_actor_id = next(iter(scenario.get("actor_ids") or []), None)
    primary_report = dashboard_agents.get(primary_actor_id) if primary_actor_id else None
    if primary_report is None and dashboard_agents:
        primary_report = next(iter(dashboard_agents.values()))

    top_metrics = []
    if primary_report is not None:
        for metric_name in primary_report.get("top_metric_names", [])[:3]:
            top_metrics.append(
                {
                    "name": metric_name,
                    "label": labelize(metric_name),
                    "explanation": TERM_EXPLANATIONS.get(metric_name, "Model-defined risk term."),
                }
            )

    global_metrics = (evaluation.get("crisis_dashboard") or {}).get("global_context", {}).get("metrics", {})
    oil_stress = float(global_metrics.get("global_oil_market_stress", {}).get("level", 0.0))
    energy_gap = float(global_metrics.get("global_energy_volume_gap", {}).get("level", 0.0))
    direct_war_probability = float(evaluation.get("risk_probabilities", {}).get("direct_strike_exchange", 0.0)) + float(
        evaluation.get("risk_probabilities", {}).get("broad_regional_escalation", 0.0)
    )
    indirect_escalation_probability = float(
        evaluation.get("risk_probabilities", {}).get("limited_proxy_escalation", 0.0)
    )
    chokepoint_probability = float(
        evaluation.get("risk_probabilities", {}).get("maritime_chokepoint_crisis", 0.0)
    )

    start_energy_price = 1.0
    end_energy_price = 1.0
    if trajectory:
        start_energy_price = float((trajectory[0].get("global_state") or {}).get("prices", {}).get("energy", 1.0))
        end_energy_price = float((trajectory[-1].get("global_state") or {}).get("prices", {}).get("energy", 1.0))

    return {
        "question": str(scenario.get("source_prompt") or scenario.get("title") or ""),
        "language": _detect_language(str(scenario.get("source_prompt") or "")),
        "actors": actor_names,
        "base_year": int(scenario.get("base_year", 2023) or 2023),
        "horizon_months": int(scenario.get("horizon_months", 0) or 0),
        "horizon_years": max(len(trajectory) - 1, 0),
        "top_outcomes": top_outcomes,
        "top_drivers": top_drivers,
        "top_metrics": top_metrics,
        "criticality_score": float(evaluation.get("criticality_score", 0.0)),
        "calibration_score": float(evaluation.get("calibration_score", 0.0)),
        "physical_consistency_score": float(evaluation.get("physical_consistency_score", 0.0)),
        "crisis_signal_summary": evaluation.get("crisis_signal_summary") or {},
        "direct_war_probability": direct_war_probability,
        "indirect_escalation_probability": indirect_escalation_probability,
        "chokepoint_probability": chokepoint_probability,
        "global_oil_market_stress": oil_stress,
        "global_energy_volume_gap": energy_gap,
        "energy_price_change": end_energy_price - start_energy_price,
    }


def _detect_language(text: str) -> str:
    if re.search(r"[А-Яа-яЁё]", text):
        return "ru"
    return "en"


def _try_llm_summary(facts: dict[str, Any]) -> InterpretiveSummary | None:
    if not REQUESTS_AVAILABLE:
        return None
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    prompt = _llm_prompt(facts)
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise executive interpretations for decision-makers. "
                    "You must answer directly, stay faithful to the supplied model outputs, "
                    "and output only JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout_sec = float(os.getenv("LLM_TIMEOUT_SEC", "120"))
    max_retries = int(os.getenv("LLM_MAX_RETRIES", "1"))
    retry_backoff_sec = float(os.getenv("LLM_RETRY_BACKOFF_SEC", "2.0"))

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
            raw = response.json()["choices"][0]["message"]["content"].strip()
            data = json.loads(raw)
            paragraphs = [str(item).strip() for item in data.get("paragraphs", []) if str(item).strip()]
            if len(paragraphs) != 3:
                raise ValueError("Expected exactly 3 paragraphs in LLM interpretive summary")
            return InterpretiveSummary(paragraphs=paragraphs, source="llm")
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            time.sleep(retry_backoff_sec * (2**attempt))

    return InterpretiveSummary(
        paragraphs=_deterministic_paragraphs(facts),
        source="deterministic",
        note=f"LLM interpretation failed: {last_error}",
    )


def _llm_prompt(facts: dict[str, Any]) -> str:
    return (
        "Write a short decision-maker interpretation of the model output.\n"
        "Return JSON only in this format:\n"
        '{"paragraphs": ["p1", "p2", "p3"]}\n'
        "Rules:\n"
        "- exactly 3 paragraphs\n"
        "- each paragraph should be 2 to 4 sentences\n"
        "- first paragraph must answer the question directly in plain language\n"
        "- if the question is about war, distinguish direct war from indirect escalation\n"
        "- second paragraph must interpret the main drivers and stress channels\n"
        "- third paragraph must explain what to monitor next and what this means for a decision-maker\n"
        "- do not invent facts beyond the supplied data\n"
        f"- write in {'Russian' if facts['language'] == 'ru' else 'English'}\n\n"
        f"Data:\n{json.dumps(facts, ensure_ascii=False, indent=2)}"
    )


def _deterministic_summary(facts: dict[str, Any]) -> InterpretiveSummary:
    return InterpretiveSummary(
        paragraphs=_deterministic_paragraphs(facts),
        source="deterministic",
        note="DeepSeek key unavailable, so the interpretation was generated from deterministic rules.",
    )


def _deterministic_paragraphs(facts: dict[str, Any]) -> list[str]:
    question = str(facts["question"])
    if facts["language"] == "ru":
        return _deterministic_paragraphs_ru(question, facts)
    return _deterministic_paragraphs_en(question, facts)


def _deterministic_paragraphs_en(question: str, facts: dict[str, Any]) -> list[str]:
    top = facts["top_outcomes"][0]
    direct_war = 100.0 * facts["direct_war_probability"]
    indirect = 100.0 * facts["indirect_escalation_probability"]
    chokepoint = 100.0 * facts["chokepoint_probability"]
    if _is_war_question(question):
        if direct_war >= 40.0:
            opening = (
                f"The model treats direct war around {', '.join(facts['actors']) or 'the focal actor'} as a material risk, "
                f"but not as the single base case over the {facts['base_year']}-{facts['base_year'] + max(facts['horizon_years'], 1)} horizon. "
                f"Direct-war outcomes sum to {direct_war:.1f}%, while the leading single trajectory is {top['label'].lower()} at {100.0 * top['probability']:.1f}%."
            )
        else:
            opening = (
                f"The model does not make direct war in {', '.join(facts['actors']) or 'the focal actor'} the base case over the "
                f"{facts['base_year']}-{facts['base_year'] + max(facts['horizon_years'], 1)} horizon. "
                f"It assigns {direct_war:.1f}% to direct-war outcomes, while indirect escalation and route disruption dominate: "
                f"{top['label']} leads at {100.0 * top['probability']:.1f}%, indirect escalation is {indirect:.1f}%, and chokepoint stress is {chokepoint:.1f}%."
            )
    else:
        opening = (
            f"The model does not reduce this question to a binary yes-or-no answer. "
            f"Its leading reading is {top['label'].lower()} at {100.0 * top['probability']:.1f}%, "
            f"with criticality at {facts['criticality_score']:.2f}."
        )

    driver_labels = [entry["label"] for entry in facts["top_drivers"][:2]]
    metric_labels = [entry["label"] for entry in facts["top_metrics"][:2]]
    second = (
        f"The quantitative picture is being driven mainly by {driver_labels[0].lower()}"
        + (f" and {driver_labels[1].lower()}" if len(driver_labels) > 1 else "")
        + ". "
        + (
            f"At the actor level, the main stress signals are {metric_labels[0].lower()}"
            + (f" and {metric_labels[1].lower()}" if len(metric_labels) > 1 else "")
            + ". "
            if metric_labels
            else ""
        )
        + f"This is consistent with a high-volatility environment rather than a clean immediate-war forecast, especially because calibration remains {facts['calibration_score']:.2f} and physical consistency remains {facts['physical_consistency_score']:.2f}."
    )

    watch_oil = facts["global_oil_market_stress"] >= 0.5 or facts["energy_price_change"] > 0.1
    third = (
        "For a decision-maker, the practical implication is to watch whether the scenario stays in indirect escalation or crosses into direct-strike territory. "
        + (
            f"The immediate watchlist is protest and regime fragility inside the focal actor, plus oil and energy stress in the wider system; global oil-market stress is already {facts['global_oil_market_stress']:.2f}. "
            if watch_oil
            else "The immediate watchlist is domestic instability, coercive signaling, and whether the crisis spreads from proxy pressure into overt military exchange. "
        )
        + "If those channels intensify together, the model would read that as movement from pressure and disruption into an actual war scenario."
    )
    return [opening, second, third]


def _deterministic_paragraphs_ru(question: str, facts: dict[str, Any]) -> list[str]:
    top = facts["top_outcomes"][0]
    direct_war = 100.0 * facts["direct_war_probability"]
    indirect = 100.0 * facts["indirect_escalation_probability"]
    chokepoint = 100.0 * facts["chokepoint_probability"]
    if _is_war_question(question):
        if direct_war >= 40.0:
            opening = (
                f"Модель считает прямую войну вокруг {', '.join(facts['actors']) or 'ключевого актора'} существенным риском, "
                f"но не базовым сценарием на горизонте {facts['base_year']}-{facts['base_year'] + max(facts['horizon_years'], 1)}. "
                f"Суммарная вероятность прямых военных исходов составляет {direct_war:.1f}%, тогда как лидирующая траектория — {top['label'].lower()} с вероятностью {100.0 * top['probability']:.1f}%."
            )
        else:
            opening = (
                f"Модель не делает прямую войну в {', '.join(facts['actors']) or 'ключевом акторе'} базовым сценарием на горизонте "
                f"{facts['base_year']}-{facts['base_year'] + max(facts['horizon_years'], 1)}. "
                f"На прямую войну приходится {direct_war:.1f}%, а доминируют косвенная эскалация и системные сбои: "
                f"{top['label']} дает {100.0 * top['probability']:.1f}%, косвенная эскалация — {indirect:.1f}%, стресс по chokepoint-каналу — {chokepoint:.1f}%."
            )
    else:
        opening = (
            f"Модель не сводит этот вопрос к бинарному ответу. "
            f"Ее основная интерпретация — {top['label'].lower()} с вероятностью {100.0 * top['probability']:.1f}%, "
            f"при критичности {facts['criticality_score']:.2f}."
        )

    driver_labels = [entry["label"] for entry in facts["top_drivers"][:2]]
    metric_labels = [entry["label"] for entry in facts["top_metrics"][:2]]
    second = (
        f"Количественная картина сейчас в первую очередь определяется факторами {driver_labels[0].lower()}"
        + (f" и {driver_labels[1].lower()}" if len(driver_labels) > 1 else "")
        + ". "
        + (
            f"На уровне актора наиболее важные сигналы — {metric_labels[0].lower()}"
            + (f" и {metric_labels[1].lower()}" if len(metric_labels) > 1 else "")
            + ". "
            if metric_labels
            else ""
        )
        + f"Это больше похоже на высоковолатильную кризисную среду, чем на однозначный прогноз немедленной войны, тем более что calibration score равен {facts['calibration_score']:.2f}, а physical consistency — {facts['physical_consistency_score']:.2f}."
    )

    watch_oil = facts["global_oil_market_stress"] >= 0.5 or facts["energy_price_change"] > 0.1
    third = (
        "Для ЛПР практический смысл в том, чтобы отслеживать, остается ли сценарий в зоне косвенной эскалации или начинает переходить к прямому военному обмену. "
        + (
            f"Ключевой watchlist сейчас — протестное и режимное давление внутри актора, а также нефтяной и энергетический стресс во внешнем контуре; глобальный oil-market stress уже находится на уровне {facts['global_oil_market_stress']:.2f}. "
            if watch_oil
            else "Ключевой watchlist сейчас — внутренняя дестабилизация, сигналы силового давления и признаки перехода от прокси-эскалации к открытому военному столкновению. "
        )
        + "Если эти каналы начнут усиливаться одновременно, модель будет читать это как движение от кризисного давления к уже собственно военному сценарию."
    )
    return [opening, second, third]


def _is_war_question(question: str) -> bool:
    lowered = question.lower()
    return any(token in lowered for token in WAR_KEYWORDS)
