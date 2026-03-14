from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_CORE = REPO_ROOT / "legacy" / "GIM_11_1"
if str(LEGACY_CORE) not in sys.path:
    sys.path.insert(0, str(LEGACY_CORE))

from gim_11_1 import calibration_params as cal  # noqa: E402
from gim_11_1.climate import update_global_climate  # noqa: E402
from gim_11_1.core import CO2_PREINDUSTRIAL_GT, GlobalState, WorldState  # noqa: E402


class ClimateForcingTests(unittest.TestCase):
    def _make_world(self) -> WorldState:
        return WorldState(
            time=0,
            agents={},
            global_state=GlobalState(
                co2=CO2_PREINDUSTRIAL_GT,
                temperature_global=1.0,
                biodiversity_index=0.72,
                temperature_ocean=0.6,
            ),
            relations={},
        )

    def test_nonco2_forcing_uses_calendar_base_year(self) -> None:
        world = self._make_world()
        world.global_state._calendar_year_base = 2015

        update_global_climate(world, dt=0.0)
        self.assertAlmostEqual(world.global_state.forcing_total, cal.F_NONCO2_DEFAULT, places=6)

        world.time = 8
        update_global_climate(world, dt=0.0)
        expected = cal.F_NONCO2_DEFAULT + 8 * cal.F_NONCO2_TREND
        self.assertAlmostEqual(world.global_state.forcing_total, expected, places=6)

    def test_explicit_nonco2_override_beats_calendar_schedule(self) -> None:
        world = self._make_world()
        world.global_state._calendar_year_base = 2015
        world.time = 8

        update_global_climate(world, dt=0.0, f_nonco2=0.25)
        self.assertAlmostEqual(world.global_state.forcing_total, 0.25, places=6)


if __name__ == "__main__":
    unittest.main()
