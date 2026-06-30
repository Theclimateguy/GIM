#!/usr/bin/env python3
"""Fast strict-mode invariant gate (Stage E).

Runs a short world simulation with the enforceable invariants in strict mode and exits
non-zero if any are breached. Designed for CI as a quick integrity gate, separate from the
full test suite. Knobs via env: STATE_CSV, CHECK_YEARS, CHECK_MAX_AGENTS.
"""

from __future__ import annotations

import os
import sys

# Allow running from a checkout without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gim.core.invariants import InvariantViolation, aggregate_run
from gim.core.policy import make_policy_map
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv

STATE_CSV = os.getenv("STATE_CSV", "data/agent_states_operational.csv")
YEARS = int(os.getenv("CHECK_YEARS", "10"))
MAX_AGENTS = int(os.getenv("CHECK_MAX_AGENTS", "100"))


def main() -> int:
    world = make_world_from_csv(STATE_CSV, max_agents=MAX_AGENTS, base_year=2023)
    policies = make_policy_map(world.agents.keys(), mode="simple")
    log: list[dict] = []
    try:
        for _ in range(YEARS):
            step_world(world, policies, invariant_log=log, invariant_mode="strict")
    except InvariantViolation as exc:
        print(f"INVARIANT VIOLATION: {exc}", file=sys.stderr)
        return 1

    agg = aggregate_run(log)
    enforceable = agg["enforceable"]
    print(f"Strict invariant gate: {YEARS}y x {len(world.agents)} actors")
    print(f"  enforceable: {enforceable}")
    print(f"  diagnostics: debt_residual={agg['diagnostic_debt_fiscal_residual']['worst_abs_share']:.3f}, "
          f"resource_pools_exhausted={agg['diagnostic_resource_consistency']['pools_exhausted_with_active_production']}")
    if not enforceable["clean"]:
        print("FAIL: enforceable invariants are not clean.", file=sys.stderr)
        return 1
    print("OK: enforceable invariants clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
