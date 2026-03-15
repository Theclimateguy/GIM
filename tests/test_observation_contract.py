from __future__ import annotations

import json
from statistics import mean
import unittest

from gim.core import calibration_params as cal
from gim.core.core import (
    AgentState,
    ClimateSubState,
    CulturalState,
    EconomyState,
    GlobalState,
    RelationState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)
from gim.core.observation import build_observation
from gim.core.world_factory import make_world_from_csv


class ObservationContractTests(unittest.TestCase):
    def _make_agent(
        self,
        *,
        agent_id: str,
        trust_gov: float = 0.55,
        social_tension: float = 0.25,
    ) -> AgentState:
        economy = EconomyState(
            gdp=1.0,
            capital=2.5,
            population=50_000_000,
            public_debt=0.8,
            fx_reserves=0.1,
            climate_shock_years=2,
            climate_shock_penalty=0.08,
        )
        economy.gdp_per_capita = economy.gdp * 1e12 / economy.population
        return AgentState(
            id=agent_id,
            type="country",
            name=agent_id,
            region="test",
            economy=economy,
            resources={
                "energy": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.1),
                "food": ResourceSubState(own_reserve=8.0, production=1.0, consumption=1.0),
                "metals": ResourceSubState(own_reserve=6.0, production=1.0, consumption=1.0),
            },
            society=SocietyState(
                trust_gov=trust_gov,
                social_tension=social_tension,
                inequality_gini=40.0,
            ),
            climate=ClimateSubState(climate_risk=0.7, co2_annual_emissions=0.3, biodiversity_local=0.72),
            culture=CulturalState(),
            technology=TechnologyState(tech_level=1.0, military_power=1.0, security_index=0.5),
            risk=RiskState(
                water_stress=0.4,
                regime_stability=0.3,
                debt_crisis_prone=0.9,
                conflict_proneness=0.4,
            ),
        )

    def _make_world(self, *agents: AgentState, temp: float = 3.0) -> WorldState:
        relations = {agent.id: {} for agent in agents}
        for left in agents:
            for right in agents:
                if left.id == right.id:
                    continue
                relations[left.id][right.id] = RelationState(
                    trade_intensity=0.4,
                    trust=0.3,
                    conflict_level=0.4,
                )
        return WorldState(
            time=0,
            agents={agent.id: agent for agent in agents},
            global_state=GlobalState(
                co2=3270.0,
                temperature_global=temp,
                biodiversity_index=0.72,
                temperature_ocean=0.8,
            ),
            relations=relations,
        )

    def test_observation_size_stays_under_budget(self) -> None:
        world = make_world_from_csv("data/agent_states_operational.csv", max_agents=20)
        sizes = []

        for agent_id in list(world.agents)[:20]:
            obs = build_observation(world, agent_id)
            sizes.append(len(json.dumps(obs.__dict__, ensure_ascii=False)))

        self.assertLess(mean(sizes), 8192)
        self.assertLess(max(sizes), 8192)

    def test_observation_includes_damage_and_inbound_sanctions_without_private_fields(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.12, social_tension=0.90)
        focal.economy._gdp_prev = 0.95
        focal.economy._debt_gdp_prev = 0.70
        focal.society._trust_prev = 0.18
        focal.society._tension_prev = 0.82
        focal.climate._emissions_prev = 0.36
        peer = self._make_agent(agent_id="B")
        peer.active_sanctions[focal.id] = "strong"
        peer.sanction_years[focal.id] = 2
        third = self._make_agent(agent_id="C")
        third.active_sanctions[focal.id] = "mild"
        third.sanction_years[focal.id] = 1
        world = self._make_world(focal, peer, third, temp=3.0)
        world.global_state.temp_history = [2.7, 2.8, 3.0]
        world.global_state.temp_trend_3yr = 0.15

        obs = build_observation(world, focal.id)
        competitive = obs.self_state["competitive"]
        trends = obs.self_state["trends"]

        self.assertIn("climate_damage_factor", competitive)
        self.assertGreaterEqual(competitive["climate_damage_factor"], 0.0)
        self.assertLessEqual(competitive["climate_damage_factor"], 1.0)
        self.assertIn("inbound_sanctions", competitive)
        self.assertEqual(competitive["inbound_sanctions"]["B"]["type"], "strong")
        self.assertEqual(competitive["inbound_sanctions"]["C"]["type"], "mild")
        self.assertNotIn("_gdp_prev", obs.self_state["economy"])
        self.assertNotIn("_debt_gdp_prev", obs.self_state["economy"])
        self.assertNotIn("_trust_prev", obs.self_state["society"])
        self.assertNotIn("_emissions_prev", obs.self_state["climate"])
        self.assertNotIn("temp_history", obs.external_actors["global"])
        self.assertEqual(set(trends), {
            "gdp_growth_last_step",
            "debt_gdp_change",
            "trust_change",
            "social_tension_change",
            "temp_trend_3yr",
            "emissions_change",
        })
        for value in trends.values():
            self.assertIsInstance(value, float)
        self.assertAlmostEqual(trends["gdp_growth_last_step"], (1.0 - 0.95) / 0.95)
        self.assertAlmostEqual(trends["debt_gdp_change"], 0.1)
        self.assertAlmostEqual(trends["trust_change"], -0.06)
        self.assertAlmostEqual(trends["social_tension_change"], 0.08)
        self.assertAlmostEqual(trends["temp_trend_3yr"], 0.15)
        self.assertAlmostEqual(trends["emissions_change"], -0.06)
        self.assertLessEqual(len(obs.external_actors["neighbors"]), cal.OBS_MAX_NEIGHBORS)
