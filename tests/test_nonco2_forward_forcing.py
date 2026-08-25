"""#11 SSP2-4.5 forward non-CO2 forcing table replaces the unbounded linear extrapolation.

Guards: (a) the calibrated window (<= 2024) is byte-identical to the linear path (golden-safe);
(b) the forward path bends DOWN toward the SSP2-4.5 plateau, not the unphysical linear 1.42 W/m2;
(c) the table is continuous at the handoff year.
"""

import unittest

from gim.core import calibration_params as cp
from gim.core.forcing import _linear_lumped, lumped_nonco2_forcing
from gim.core.params import default_params


class NonCO2ForwardForcingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.p = default_params()

    def test_in_window_identical_to_linear(self) -> None:
        for year in (1990, 2000, 2015, 2020, 2024):
            self.assertAlmostEqual(
                lumped_nonco2_forcing(self.p, year), _linear_lumped(self.p, year), places=9
            )

    def test_continuous_at_handoff(self) -> None:
        from_year = cp.F_NONCO2_FORWARD_FROM_YEAR
        self.assertAlmostEqual(
            lumped_nonco2_forcing(self.p, from_year),
            lumped_nonco2_forcing(self.p, from_year + 1),
            delta=0.02,
        )

    def test_forward_plateaus_below_linear(self) -> None:
        # By 2100 the SSP2-4.5 table must be far below the unbounded linear extrapolation.
        table_2100 = lumped_nonco2_forcing(self.p, 2100)
        linear_2100 = _linear_lumped(self.p, 2100)
        self.assertLess(table_2100, 0.85)  # plateau, not 1.42
        self.assertGreater(linear_2100, 1.3)
        self.assertLess(table_2100, linear_2100 - 0.5)
        # Monotone non-decreasing toward the plateau across the century.
        self.assertGreaterEqual(lumped_nonco2_forcing(self.p, 2050), lumped_nonco2_forcing(self.p, 2030))
        self.assertGreaterEqual(lumped_nonco2_forcing(self.p, 2100), lumped_nonco2_forcing(self.p, 2050))

    def test_fallback_to_linear_when_disabled(self) -> None:
        p = self.p.with_overrides({"F_NONCO2_FORWARD_TABLE": False})
        for year in (2030, 2050, 2100):
            self.assertAlmostEqual(lumped_nonco2_forcing(p, year), _linear_lumped(p, year), places=9)


if __name__ == "__main__":
    unittest.main()
