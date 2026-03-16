from __future__ import annotations

from .schemas import EventDetections


def build_event_detections(cards: list[dict]) -> EventDetections:
    return EventDetections(cards=list(cards))


__all__ = ["build_event_detections"]
