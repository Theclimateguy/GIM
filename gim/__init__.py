"""GIM annual world core (57 actors) with scenario gaming layers.

Lineage: the validated GIM18 engine, extended in the GIM19 working tree and released as
GIM 20.1 for the paper. The optional intra-country block layer is flag-off by default,
which keeps this core bit-identical to the published numbers.
"""

__version__ = "20.1.1"

from .core import *  # noqa: F401,F403
from .crisis_metrics import CrisisMetricsEngine
from .game_runner import GameRunner
from .hybrid_simulator import HybridSimulator, compile_human_intent
from .runtime import load_world
from .scenario_compiler import compile_question, load_game_definition
from .sim_bridge import SimBridge

__all__ = [
    "__version__",
    "CrisisMetricsEngine",
    "GameRunner",
    "HybridSimulator",
    "SimBridge",
    "compile_human_intent",
    "compile_question",
    "load_game_definition",
    "load_world",
]
