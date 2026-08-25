"""GIM19 annual world core (57 actors) with scenario gaming layers.

Lineage: the validated GIM18 engine; GIM19 = this core + the gim19 block layer
+ the coupling channels (flag-off contract keeps the core bit-identical).
"""

__version__ = "19.2.0"

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
