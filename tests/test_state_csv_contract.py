from pathlib import Path
import tempfile
import unittest

from GIM_13.runtime import load_world


CSV_HEADER = (
    "id,name,region,regime_type,gdp,population,fx_reserves,trust_gov,social_tension,"
    "inequality_gini,climate_risk,pdi,idv,mas,uai,lto,ind,traditional_secular,"
    "survival_self_expression,alliance_block,capital,public_debt_pct_gdp,energy_reserve,"
    "energy_production,energy_consumption,food_reserve,food_production,food_consumption,"
    "metals_reserve,metals_production,metals_consumption,co2_annual_emissions,"
    "biodiversity_local,water_stress,regime_stability,debt_crisis_prone,"
    "conflict_proneness,tech_level,security_index,military_power\n"
)


def _write_csv(directory: str, rows: list[list[object]]) -> Path:
    path = Path(directory) / "agent_states.csv"
    body = "\n".join(",".join("" if value is None else str(value) for value in row) for row in rows)
    path.write_text(CSV_HEADER + body + "\n", encoding="utf-8")
    return path


class StateCsvContractTests(unittest.TestCase):
    def test_loader_uses_capital_and_derives_public_debt_from_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _write_csv(
                tmpdir,
                [[
                    "T01",
                    "Testland",
                    "Europe",
                    "Democracy",
                    2.0,
                    1_000_000,
                    0.2,
                    0.55,
                    0.25,
                    35,
                    0.45,
                    40,
                    60,
                    55,
                    50,
                    45,
                    65,
                    6.0,
                    7.0,
                    "Western",
                    6.5,
                    60,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    0.1,
                    0.7,
                    None,
                    None,
                    None,
                    None,
                    1.1,
                    0.6,
                    0.8,
                ]],
            )

            world = load_world(state_csv=str(csv_path))
            agent = world.agents["T01"]

            self.assertAlmostEqual(agent.economy.capital, 6.5)
            self.assertAlmostEqual(agent.economy.public_debt, 1.2)
            self.assertAlmostEqual(agent.resources["energy"].own_reserve, 20.0)
            self.assertAlmostEqual(agent.resources["food"].production, 50.0)
            self.assertAlmostEqual(agent.resources["metals"].consumption, 20.0)
            self.assertAlmostEqual(agent.climate.biodiversity_local, 0.7)

    def test_loader_rejects_negative_resource_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = _write_csv(
                tmpdir,
                [[
                    "T01",
                    "Testland",
                    "Europe",
                    "Democracy",
                    2.0,
                    1_000_000,
                    0.2,
                    0.55,
                    0.25,
                    35,
                    0.45,
                    40,
                    60,
                    55,
                    50,
                    45,
                    65,
                    6.0,
                    7.0,
                    "Western",
                    None,
                    None,
                    1,
                    1,
                    1,
                    1,
                    1,
                    1,
                    -1,
                    1,
                    1,
                    0.1,
                    0.7,
                    0.2,
                    0.8,
                    0.3,
                    0.4,
                    1.1,
                    0.6,
                    0.8,
                ]],
            )

            with self.assertRaisesRegex(ValueError, "must be >= 0"):
                load_world(state_csv=str(csv_path))


if __name__ == "__main__":
    unittest.main()
