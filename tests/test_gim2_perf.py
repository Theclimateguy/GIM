"""THE-66 — perf/async: baseline cache correctness, cooperative cancel, policy."""

from __future__ import annotations

import threading

import pytest

from gim2 import scenario as S
from gim2.levers import LeverSelection
from gim2.perf import recommended_members


def _cfg(members=3, years=2, max_agents=8):
    return S.build_config(state_csv=None, members=members, years=years,
                          max_agents=max_agents, seed=2026, prior_set="key", jobs=1)


def test_baseline_cache_hit_returns_same_object_and_correct_values():
    S.clear_baseline_cache()
    cfg = _cfg()
    first = S.baseline_trajectories(cfg)
    second = S.baseline_trajectories(cfg)
    assert second is first, "second call should be a cache hit (same object)"
    fresh = S.run_trajectories(cfg, LeverSelection())
    assert fresh == first, "cached baseline must equal a freshly computed one"


def test_cache_keeps_scenario_baseline_stable_across_levers():
    S.clear_baseline_cache()
    a = S.compute_scenario(levers=["decarbonization"], magnitude=1.0, members=3, years=2, max_agents=8, jobs=1)
    b = S.compute_scenario(levers=["carbon_price"], magnitude=1.0, members=3, years=2, max_agents=8, jobs=1)
    assert a["baseline"] == b["baseline"], "shared baseline must be identical across lever changes"


def test_cooperative_cancel_raises():
    S.clear_baseline_cache()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(S.RunCancelled):
        S.compute_scenario(levers=["energy_shock"], magnitude=1.0, members=3, years=2,
                           max_agents=8, jobs=1, cancel=cancel)


def test_member_size_policy():
    assert recommended_members(interactive=True) == S.INTERACTIVE_MEMBERS
    assert recommended_members(interactive=False) == S.BACKGROUND_MEMBERS
    assert S.INTERACTIVE_MEMBERS < S.BACKGROUND_MEMBERS
