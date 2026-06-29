"""Инкремент 1 — карта ответа: типовые сценарии + /run/answer.

Проверяет сборку решение-ориентированного ответа (вердикт, карточки, порог,
каскад, записка), каталог архетипов и логику порога; плюс маршрут движка.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import threading

import pytest

from gim2 import archetypes as A
from gim2 import answer as ANS
from gim2.answer import compute_answer
from gim2.cascade import compute_cascade
from gim2.engine_service import build_engine_server
from gim2.levers import make_selection


def _small(**kw):
    base = dict(members=10, years=5, max_agents=10, threshold_members=10, cascade_members=6,
                jobs=1, seed=2026)
    base.update(kw)
    return compute_answer(**base)


# --------------------------------------------------------------------------- #
# архетипы
# --------------------------------------------------------------------------- #


def test_catalog_lists_archetypes_and_segments():
    cat = A.catalog()
    ids = {a["id"] for a in cat["archetypes"]}
    assert {"energy_war", "stagflation_decade", "sanctions_spiral", "green_transition_shock",
            "soft_landing", "sovereign_stress"} <= ids
    assert len(ids) >= 8
    assert {s["id"] for s in cat["segments"]} == {"energy", "sovereign", "erm", "geo"}


def test_by_segment_filters():
    energy = {a.id for a in A.by_segment("energy")}
    assert "energy_war" in energy
    assert "food_social" not in energy  # food_social is geo/erm


def test_unknown_archetype_raises():
    with pytest.raises(ValueError):
        A.get("not_a_real_archetype")


# --------------------------------------------------------------------------- #
# карта ответа
# --------------------------------------------------------------------------- #


def test_answer_from_archetype_assembles_full_card():
    r = _small(archetype="energy_war")
    assert r["mode"] == "answer"
    assert isinstance(r["verdict"], str) and r["verdict"]
    assert 1 <= len(r["cards"]) <= 4
    assert any(c["lead"] for c in r["cards"])             # есть ведущая метрика
    assert r["projection"]["kind"] == "scenario_delta"    # дельта-вееры на месте
    assert r["threshold"]["lever"] == "energy_shock"
    assert "curve" in r["threshold"]                       # дозовая кривая приложена
    casc = r["cascade"]["nodes"]
    assert casc and all({"id", "label", "shown", "direction", "scope", "focus_scope"} <= set(n) for n in casc)
    assert r["cascade"]["affected"]                         # сильнее всего затронутые названы
    assert r["archetype"]["name_ru"] == "Энергетическая война"


def test_answer_from_explicit_levers():
    r = _small(levers=["energy_shock=1.0", "stagflation=0.6"])
    assert r["mode"] == "answer"
    assert r["archetype"] is None
    assert set(r["selection"]["levers"]) == {"energy_shock", "stagflation"}
    # каскад объединяет цепочки обоих рычагов (energy_shock→debt, stagflation→tension)
    ids = {n["id"] for n in r["cascade"]["nodes"]}
    assert "debt" in ids and "tension" in ids


def test_answer_requires_a_lever():
    with pytest.raises(ValueError):
        _small(levers=[])


# --------------------------------------------------------------------------- #
# состояния акторов (winners/losers + geo)
# --------------------------------------------------------------------------- #


def test_answer_includes_actor_states():
    r = _small(archetype="energy_war")
    a = r["actors"]
    assert a["leaders"] and a["laggards"]
    assert a["leaders"][0]["score"] >= a["laggards"][0]["score"]      # отсортировано по score
    assert a["geo"]["countries"] and all("geo_name" in c for c in a["geo"]["countries"])
    assert {"gdp_pct", "tension", "debt_pct", "crisis_years"} == set(a["geo"]["domains"])


def test_actor_states_alias_and_aggregates_excluded_from_map():
    from gim2.actors import build_actor_states
    from gim2.cascade import run_actor_pair

    run = run_actor_pair(selection=make_selection(["energy_shock=1.0"]), years=4,
                         max_agents=57, members=6, seed=2026)
    st = build_actor_states(run)
    by_id = {a["id"]: a for a in st["actors"]}
    assert by_id["USA"]["geo_name"] == "United States of America"   # alias resolves
    aggregates = [a for a in st["actors"] if a["aggregate"]]
    assert aggregates and all(not a["mappable"] for a in aggregates)
    geo_ids = {c["id"] for c in st["geo"]["countries"]}
    assert all(a["id"] not in geo_ids for a in aggregates)          # aggregates off the map


# --------------------------------------------------------------------------- #
# логика порога
# --------------------------------------------------------------------------- #


def test_threshold_crossing_interpolates():
    # синтетическая дозовая кривая: Δ долговых кризисов пересекает 1.0 между 0.5 и 0.75
    dose = {"x": [0.0, 0.25, 0.5, 0.75, 1.0], "delta": [0.0, 0.2, 0.6, 1.4, 2.0], "baseline": 5.0}
    out = ANS._threshold_crossing(dose, "energy_shock", "n_debt_crises")
    assert out["crossing_magnitude"] == pytest.approx(0.5 + 0.25 * (1.0 - 0.6) / (1.4 - 0.6), abs=1e-3)
    assert "доп. событий" in out["note"]


def test_threshold_no_crossing_reported():
    dose = {"x": [0.0, 0.5, 1.0], "delta": [0.0, 0.1, 0.2], "baseline": 5.0}
    out = ANS._threshold_crossing(dose, "energy_shock", "n_debt_crises")
    assert out["crossing_magnitude"] is None
    assert "не достигается" in out["note"]


# --------------------------------------------------------------------------- #
# количественный каскад
# --------------------------------------------------------------------------- #


def test_cascade_measured_nodes_in_causal_order():
    sel = make_selection(["energy_shock=1.0"])
    res = compute_cascade(selection=sel, years=5, max_agents=12, members=6, seed=2026)
    assert [n["id"] for n in res["nodes"]] == ["energy_price", "inflation", "debt"]
    ep = next(n for n in res["nodes"] if n["id"] == "energy_price")
    assert ep["delta"] > 0 and ep["pct"] is not None and ep["direction"] == "up"
    # без явных акторов агентные узлы скоупятся на top-K сильнее всего затронутых
    assert res["affected"] and res["selection_actors"] == []
    debt = next(n for n in res["nodes"] if n["id"] == "debt")
    assert debt["focus_scope"] == "most_affected"


def test_cascade_actor_scoped_for_sanctions():
    sel = make_selection(["trade_sanctions=1.0"], actors=["United States", "China"])
    res = compute_cascade(selection=sel, years=5, max_agents=14, members=6, seed=2026)
    assert "United States" in res["selection_actors"] or "China" in res["selection_actors"]
    tb = next(n for n in res["nodes"] if n["id"] == "trade_barrier")
    assert tb["delta"] > 0 and tb["direction"] == "up" and tb["focus_scope"] == "selection"
    gdp = next(n for n in res["nodes"] if n["id"] == "gdp")
    assert gdp["focus_scope"] == "selection"  # ВВП от actor-рычага → именованные акторы


def test_cascade_empty_without_levers():
    out = compute_cascade(selection=make_selection([]), members=4)
    assert out["nodes"] == [] and out["selection_actors"] == []


# --------------------------------------------------------------------------- #
# маршрут движка
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def _engine():
    server = build_engine_server("127.0.0.1", 0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield server.ready_payload["port"], server.ready_payload["token"]  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()


def _get(port, token, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
    conn.request("GET", path, headers={"Authorization": f"Bearer {token}"})
    raw = conn.getresponse().read().decode()
    conn.close()
    return json.loads(raw)


def test_engine_answer_route_and_archetypes_endpoint():
    with _engine() as (port, token):
        cat = _get(port, token, "/archetypes?segment=energy")
        assert any(a["id"] == "energy_war" for a in cat["archetypes"])

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=120)
        body = json.dumps({"archetype": "energy_war", "members": 8, "years": 4,
                           "max_agents": 8, "threshold_members": 8, "cascade_members": 6, "jobs": 1})
        conn.request("POST", "/run/answer", body=body,
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        resp = conn.getresponse()
        payload = json.loads(resp.read().decode())
        conn.close()
    assert resp.status == 200
    assert payload["mode"] == "answer"
    assert payload["cascade"]
    assert "trace" in payload
