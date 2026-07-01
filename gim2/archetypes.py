"""Библиотека типовых сценариев (mixed scenario archetypes) для v2.

Стартовые точки вместо пустого экрана: именованные смешанные бандлы заземлённых
рычагов (`gim2.levers`), снабжённые отраслевыми профилями. Это данные, не модель —
архетип просто раскрывается в обычный ``LeverSelection`` для движка.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from . import levers as L

# Отраслевые профили (сегменты), под которые подсвечиваются архетипы.
SEGMENTS: Dict[str, str] = {
    "energy": "Энергетика / сырьё",
    "sovereign": "Суверен / ЦБ / SWF",
    "erm": "Перестрахование / ERM",
    "geo": "Госфорсайт / оборона",
}


@dataclass(frozen=True)
class Archetype:
    id: str
    name_ru: str
    description: str
    levers: Dict[str, float]                  # lever_id -> magnitude
    segments: Tuple[str, ...]                  # ключи из SEGMENTS
    headline_metric: str = "world_gdp"         # метрика для вердикта/карточек
    threshold_lever: str = ""                  # рычаг для свипа порога (по умолчанию — крупнейший)
    threshold_metric: str = ""                 # метрика порога (по умолчанию — headline)
    actors: Tuple[str, ...] = ()               # для actor-рычагов (санкции)

    def selection_items(self) -> List[Dict[str, float]]:
        return [{"lever": lid, "magnitude": mag} for lid, mag in self.levers.items()]

    def dominant_lever(self) -> str:
        return self.threshold_lever or max(self.levers, key=lambda k: self.levers[k])

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name_ru": self.name_ru,
            "description": self.description,
            "levers": dict(self.levers),
            "segments": list(self.segments),
            "headline_metric": self.headline_metric,
            "threshold_lever": self.dominant_lever(),
            "threshold_metric": self.threshold_metric or self.headline_metric,
            "actors": list(self.actors),
        }


ARCHETYPES: Dict[str, Archetype] = {
    "energy_war": Archetype(
        id="energy_war",
        name_ru="Энергетическая война",
        description="Резкий энергошок вместе с санкциями против крупного экспортёра.",
        levers={"energy_shock": 1.0, "trade_sanctions": 0.8},
        segments=("energy", "sovereign", "geo"),
        headline_metric="world_gdp",
        threshold_lever="energy_shock",
        threshold_metric="n_debt_crises",
        actors=("United States", "China"),
    ),
    "stagflation_decade": Archetype(
        id="stagflation_decade",
        name_ru="Десятилетие стагфляции",
        description="Устойчивый стагфляционный шок на фоне дорогой энергии.",
        levers={"stagflation": 1.0, "energy_shock": 0.6},
        segments=("sovereign", "erm"),
        headline_metric="mean_social_tension",
        threshold_lever="stagflation",
        threshold_metric="mean_social_tension",
    ),
    "sanctions_spiral": Archetype(
        id="sanctions_spiral",
        name_ru="Спираль санкций",
        description="Эскалация торговых барьеров между блоками плюс энергетический сбой.",
        levers={"trade_sanctions": 1.0, "energy_shock": 0.5},
        segments=("geo", "energy"),
        headline_metric="world_gdp",
        threshold_lever="trade_sanctions",
        threshold_metric="conflict_risk",
        actors=("United States", "China"),
    ),
    "green_transition_shock": Archetype(
        id="green_transition_shock",
        name_ru="Шок зелёного перехода",
        description="Высокая цена углерода и форсированная декарбонизация.",
        levers={"carbon_price": 1.0, "decarbonization": 0.8},
        segments=("sovereign", "energy"),
        headline_metric="co2",
        threshold_lever="carbon_price",
        threshold_metric="mean_social_tension",
    ),
    "food_social": Archetype(
        id="food_social",
        name_ru="Продовольственно-социальный шок",
        description="Продовольственный дефицит, усиленный стагфляцией.",
        levers={"food_shock": 1.0, "stagflation": 0.6},
        segments=("geo", "erm"),
        headline_metric="mean_social_tension",
        threshold_lever="food_shock",
        threshold_metric="mean_social_tension",
    ),
    "supply_chain_break": Archetype(
        id="supply_chain_break",
        name_ru="Разрыв цепочек поставок",
        description="Торговые барьеры между блоками вместе с продовольственным сбоем.",
        levers={"trade_sanctions": 0.9, "food_shock": 0.7},
        segments=("geo", "erm"),
        headline_metric="world_gdp",
        threshold_lever="trade_sanctions",
        threshold_metric="world_gdp",
        actors=("United States", "China"),
    ),
    "sovereign_stress": Archetype(
        id="sovereign_stress",
        name_ru="Суверенный долговой стресс",
        description="Стагфляция, дорогая энергия и санкции бьют по госфинансам.",
        levers={"stagflation": 0.9, "energy_shock": 0.7, "trade_sanctions": 0.5},
        segments=("sovereign", "erm"),
        headline_metric="n_debt_crises",
        threshold_lever="energy_shock",
        threshold_metric="n_debt_crises",
        actors=("United States", "China"),
    ),
    "soft_landing": Archetype(
        id="soft_landing",
        name_ru="Мягкая посадка",
        description="Благоприятный контраст: устойчивая декарбонизация плюс рост.",
        levers={"decarbonization": 0.8, "growth": 0.8},
        segments=("sovereign", "energy"),
        headline_metric="world_gdp",
        threshold_lever="growth",
        threshold_metric="world_gdp",
    ),
}


def get(archetype_id: str) -> Archetype:
    try:
        return ARCHETYPES[archetype_id]
    except KeyError:
        raise ValueError(
            f"unknown archetype {archetype_id!r}; allowed: {', '.join(sorted(ARCHETYPES))}"
        ) from None


def by_segment(segment: str) -> List[Archetype]:
    return [a for a in ARCHETYPES.values() if segment in a.segments]


def catalog(segment: str | None = None) -> Dict[str, object]:
    items = by_segment(segment) if segment else list(ARCHETYPES.values())
    return {
        "segments": [{"id": k, "label": v} for k, v in SEGMENTS.items()],
        "archetypes": [a.to_dict() for a in items],
    }


__all__ = ["Archetype", "ARCHETYPES", "SEGMENTS", "get", "by_segment", "catalog"]
