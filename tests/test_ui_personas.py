"""Tests for the persona-aware UI server endpoints (THE-49)."""

from __future__ import annotations

import json

import pytest

from gim.ui_server import (
    RESULTS_DIR,
    _apply_personas_to_payload,
    _compare_payload,
    _doctrine_preview_payload,
    _intents_feed_payload,
    _personas_payload,
    _summarize_actions,
)


def test_personas_payload_lists_archetypes():
    payload = _personas_payload()
    ids = {p["id"] for p in payload["personas"]}
    assert {"hawk_protectionist", "dove", "technocrat"} <= ids
    for persona in payload["personas"]:
        assert persona["name"]["ru"] and persona["name"]["en"]
        assert "nudges" in persona


def test_apply_personas_augments_list_intents():
    payload = {
        "command": "hybrid",
        "tables": ["United States"],
        "intents": ["United States=Pressure China on trade"],
        "persona": {"United States": "hawk_protectionist"},
    }
    _apply_personas_to_payload(payload)
    intent = payload["intents"][0]
    assert intent.startswith("United States=Pressure China on trade")
    assert "tariffs" in intent  # hawk keywords appended


def test_apply_personas_handles_dict_intents_and_unknown_persona():
    payload = {"intents": {"Iran": "Hold the line"}, "persona": {"Iran": "not_real"}}
    _apply_personas_to_payload(payload)
    # unknown persona leaves the intent unchanged but normalizes to list form
    assert payload["intents"] == ["Iran=Hold the line"]


def test_doctrine_preview_for_real_country():
    preview, status = _doctrine_preview_payload(
        "hawk_protectionist", "United States", None, 2026
    )
    assert status == 200
    assert preview["country"] == "United States"
    for side in ("base", "shifted", "deltas"):
        assert "escalation_bias" in preview[side]
    # hawk raises escalation and sanctions tolerance, lowers trade openness
    assert preview["deltas"]["escalation_bias"] > 0
    assert preview["deltas"]["trade_openness"] < 0


def test_doctrine_preview_unknown_country_is_400():
    _preview, status = _doctrine_preview_payload(
        "dove", "Atlantis", None, 2026
    )
    assert status == 400


def test_summarize_actions_extracts_chips():
    chips = _summarize_actions(
        [
            {
                "foreign_policy": {
                    "sanctions_actions": [{"type": "strong", "target": "CHN"}],
                    "security_actions": {"type": "none"},
                },
                "domestic_policy": {"military_spending_change": 0.01},
            }
        ]
    )
    assert "sanctions→CHN" in chips
    assert "military_spend↑" in chips
    assert _summarize_actions([]) == []


def test_intents_feed_from_hybrid_result(tmp_path):
    data = {
        "hybrid_result": {
            "intents": [
                {
                    "agent_id": "USA",
                    "agent_name": "United States",
                    "raw_text": "Pressure China",
                    "matched_topics": ["trade_restrict", "sanctions"],
                    "intensity": "medium",
                }
            ],
            "effective_actions_by_agent": {
                "USA": [{"domestic_policy": {"military_spending_change": 0.01}}]
            },
        }
    }
    path = tmp_path / "hybrid_result.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    feed = _intents_feed_payload(path)["feed"]
    assert len(feed) == 1
    assert feed[0]["agent_name"] == "United States"
    assert feed[0]["tags"] == ["trade_restrict", "sanctions"]
    assert "military_spend↑" in feed[0]["actions"]


def test_compare_payload_diffs_two_runs():
    dirs = [
        p.parent.name
        for p in sorted(
            RESULTS_DIR.glob("*/evaluation.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True,
        )
    ][:2]
    if len(dirs) < 2:
        pytest.skip("need two runs with evaluation.json")
    result = _compare_payload(dirs)
    assert len(result["runs"]) == 2
    assert "criticality" in result["runs"][0]
    assert "criticality_delta" in result["diff"]
    assert len(result["diff"]["outcome_deltas"]) >= 1


def test_compare_payload_requires_resolvable_runs():
    result = _compare_payload(["does-not-exist-1", "does-not-exist-2"])
    assert result["runs"] == []
    assert result["diff"] == {}
