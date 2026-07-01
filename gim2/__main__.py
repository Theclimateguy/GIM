"""``python3 -m gim2`` — the reproducible deterministic CLI for the v2 line.

Every subcommand is a thin, deterministic wrapper over the *frozen* validated math
in :mod:`gim` and prints a stable JSON object. The same projections back the v2
HTTP engine (:mod:`gim2.engine_service`); the parity test asserts the two agree.

Subcommands
-----------
* ``ensemble``    — Monte-Carlo fan bands (median / IQR / 5–95).
* ``sensitivity`` — Morris elementary-effects screening (tornado).
* ``weak``        — weak-signal scan (Mahalanobis / break / critical-slowing).
* ``scc``         — social cost of carbon (central + multi-horizon + distribution).
* ``scenario``    — base-vs-scenario delta fans for a grounded lever set.
* ``dose``        — dose-response: terminal delta vs lever magnitude.
* ``meta``        — model-trust readouts: ``scc`` / ``backtest`` / ``conflict_auc``.
* ``engine``      — run the deterministic HTTP+SSE engine service.

The handlers ``lazy-import`` their implementation modules so ``--help`` and
``import gim2`` work even while later stages are still being built.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__


# --------------------------------------------------------------------------- #
# shared args / helpers
# --------------------------------------------------------------------------- #


def _add_world_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--state-csv", default=None, help="agent-states CSV (default: calibrated 2026)")
    p.add_argument("--state-year", type=int, default=None, help="base year of the state")
    p.add_argument("--max-agents", type=int, default=100, help="cap number of countries (default 100)")
    p.add_argument("--seed", type=int, default=2026, help="master RNG seed")


def _emit(obj: Any) -> int:
    json.dump(obj, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


# --------------------------------------------------------------------------- #
# handlers (lazy imports keep the module importable before later stages land)
# --------------------------------------------------------------------------- #


def _cmd_ensemble(args: argparse.Namespace) -> int:
    from .scenario import run_ensemble_cli

    return _emit(run_ensemble_cli(args))


def _cmd_sensitivity(args: argparse.Namespace) -> int:
    from .scenario import run_sensitivity_cli

    return _emit(run_sensitivity_cli(args))


def _cmd_weak(args: argparse.Namespace) -> int:
    from .scenario import run_weak_cli

    return _emit(run_weak_cli(args))


def _cmd_scc(args: argparse.Namespace) -> int:
    from .scenario import run_scc_cli

    return _emit(run_scc_cli(args))


def _cmd_scenario(args: argparse.Namespace) -> int:
    from .scenario import run_scenario_cli

    return _emit(run_scenario_cli(args))


def _cmd_dose(args: argparse.Namespace) -> int:
    from .dose_response import run_dose_cli

    return _emit(run_dose_cli(args))


def _cmd_answer(args: argparse.Namespace) -> int:
    from .answer import run_answer_cli

    return _emit(run_answer_cli(args))


def _cmd_meta(args: argparse.Namespace) -> int:
    from .scenario import run_meta_cli

    return _emit(run_meta_cli(args))


def _cmd_engine(args: argparse.Namespace) -> int:
    from .engine_service import run_engine_service

    run_engine_service(host=args.host, port=args.port)
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gim2",
        description="GIM17 v2.0 — deterministic analytical CLI (validated math only).",
    )
    parser.add_argument("--version", action="version", version=f"gim2 {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # ensemble ------------------------------------------------------------- #
    p = sub.add_parser("ensemble", help="Monte-Carlo fan bands for the headline indicators")
    _add_world_args(p)
    p.add_argument("--members", type=int, default=200, help="ensemble size (interactive default 200)")
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--prior-set", choices=["key", "all"], default="key")
    p.add_argument("--jobs", type=int, default=0, help="0=auto, 1=serial")
    p.set_defaults(func=_cmd_ensemble)

    # sensitivity ---------------------------------------------------------- #
    p = sub.add_parser("sensitivity", help="Morris elementary-effects screening (tornado)")
    _add_world_args(p)
    p.add_argument("--metric", default="world_gdp",
                   choices=["world_gdp", "temperature", "co2", "mean_social_tension"])
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--params", nargs="*", default=None, help="parameter names (default: key SCC/priors set)")
    p.add_argument("--r", type=int, default=10, help="Morris trajectories")
    p.add_argument("--levels", type=int, default=4)
    p.set_defaults(func=_cmd_sensitivity)

    # weak ----------------------------------------------------------------- #
    p = sub.add_parser("weak", help="weak-signal scan (scenario vs base trajectory)")
    _add_world_args(p)
    p.add_argument("--lever", action="append", default=[], help="grounded lever id (repeatable)")
    p.add_argument("--magnitude", type=float, default=None, help="lever magnitude (default per-lever)")
    p.add_argument("--actors", nargs="*", default=None)
    p.add_argument("--years", type=int, default=12)
    p.set_defaults(func=_cmd_weak)

    # scc ------------------------------------------------------------------ #
    p = sub.add_parser("scc", help="social cost of carbon ($/tCO2)")
    _add_world_args(p)
    p.add_argument("--horizons", type=int, nargs="*", default=[30, 100, 200])
    p.add_argument("--pulse-gtco2", type=float, default=10.0)
    p.add_argument("--distribution", action="store_true", help="propagate priors (percentiles)")
    p.add_argument("--samples", type=int, default=50)
    p.set_defaults(func=_cmd_scc)

    # scenario ------------------------------------------------------------- #
    p = sub.add_parser("scenario", help="base-vs-scenario delta fans for a grounded lever set")
    _add_world_args(p)
    p.add_argument("--lever", action="append", default=[], required=False,
                   help="grounded lever id (repeatable), optionally 'id=magnitude'")
    p.add_argument("--magnitude", type=float, default=None, help="default magnitude for bare levers")
    p.add_argument("--actors", nargs="*", default=None)
    p.add_argument("--members", type=int, default=200)
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--prior-set", choices=["key", "all"], default="key")
    p.add_argument("--jobs", type=int, default=0)
    p.set_defaults(func=_cmd_scenario)

    # dose ----------------------------------------------------------------- #
    p = sub.add_parser("dose", help="dose-response: terminal delta vs lever magnitude")
    _add_world_args(p)
    p.add_argument("--lever", required=True, help="grounded lever id to sweep")
    p.add_argument("--grid", type=float, nargs="*", default=[0.0, 0.25, 0.5, 0.75, 1.0, 1.25],
                   help="lever magnitudes to sweep")
    p.add_argument("--metric", default="world_gdp",
                   choices=["world_gdp", "temperature", "co2", "mean_social_tension"])
    p.add_argument("--actors", nargs="*", default=None)
    p.add_argument("--members", type=int, default=120)
    p.add_argument("--years", type=int, default=10)
    p.set_defaults(func=_cmd_dose)

    # answer --------------------------------------------------------------- #
    p = sub.add_parser("answer", help="карта ответа: вердикт + вееры + порог + каскад + записка")
    _add_world_args(p)
    p.add_argument("--archetype", default=None, help="id типового сценария (gim2.archetypes)")
    p.add_argument("--lever", action="append", default=[], help="рычаг (повторяемо), 'id=magnitude'")
    p.add_argument("--magnitude", type=float, default=None)
    p.add_argument("--actors", nargs="*", default=None)
    p.add_argument("--members", type=int, default=160)
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--threshold-lever", default=None)
    p.add_argument("--threshold-metric", default=None)
    p.set_defaults(func=_cmd_answer)

    # meta ----------------------------------------------------------------- #
    p = sub.add_parser("meta", help="model-trust readouts")
    p.add_argument("kind", choices=["scc", "backtest", "conflict_auc"])
    _add_world_args(p)
    p.set_defaults(func=_cmd_meta)

    # engine --------------------------------------------------------------- #
    p = sub.add_parser("engine", help="run the deterministic HTTP+SSE engine service")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=0)
    p.set_defaults(func=_cmd_engine)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
