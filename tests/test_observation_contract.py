from __future__ import annotations

import json
from statistics import mean
import unittest

from gim.core import calibration_params as cal
from gim.core.core import (
    Action,
    AgentState,
    ClimateSubState,
    CulturalState,
    DomesticPolicy,
    EconomyState,
    FinancePolicy,
    ForeignPolicy,
    GlobalState,
    RelationState,
    ResourceSubState,
    RiskState,
    SocietyState,
    TechnologyState,
    WorldState,
)
from gim.core.observation import build_observation
from gim.core.simulation import step_world
from gim.core.world_factory import make_world_from_csv


class ObservationContractTests(unittest.TestCase):
    def _status_quo_policy(self, agent_id: str):
        def policy(obs):
            return Action(
                agent_id=agent_id,
                time=obs.time,
                domestic_policy=DomesticPolicy(
                    tax_fuel_change=0.0,
                    social_spending_change=0.0,
                    military_spending_change=0.0,
                    rd_investment_change=0.0,
                    climate_policy="none",
                ),
                foreign_policy=ForeignPolicy(),
                finance=FinancePolicy(
                    borrow_from_global_markets=0.0,
                    use_fx_reserves_change=0.0,
                ),
            )

        return policy

    def _austerity_policy(self, agent_id: str):
        def policy(obs):
            return Action(
                agent_id=agent_id,
                time=obs.time,
                domestic_policy=DomesticPolicy(
                    tax_fuel_change=0.0,
                    social_spending_change=-0.012,
                    military_spending_change=0.0,
                    rd_investment_change=0.0,
                    climate_policy="none",
                ),
                foreign_policy=ForeignPolicy(),
                finance=FinancePolicy(
                    borrow_from_global_markets=0.0,
                    use_fx_reserves_change=0.0,
                ),
            )

        return policy

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
            sizes.append(len(json.dumps(obs.main_payload(), ensure_ascii=False)))

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

    def test_situation_summary_present(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.12, social_tension=0.90)
        focal.risk.debt_crisis_active_years = 2
        focal.economy._gdp_prev = 1.05
        focal.economy._debt_gdp_prev = 0.73
        focal.society._trust_prev = 0.18
        focal.society._tension_prev = 0.82
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)
        world.global_state.temp_trend_3yr = 0.06

        obs = build_observation(world, focal.id)

        self.assertIn("situation_summary", obs.self_state)
        self.assertIsInstance(obs.self_state["situation_summary"], str)
        self.assertTrue(obs.self_state["situation_summary"])

    def test_situation_summary_stable_agent(self) -> None:
        focal = self._make_agent(agent_id="A")
        focal.economy.public_debt = 0.35
        focal.economy.climate_shock_years = 0
        peer = self._make_agent(agent_id="B")
        peer.economy.public_debt = 0.45
        peer.economy.climate_shock_years = 0
        world = self._make_world(focal, peer, temp=1.5)

        obs = build_observation(world, focal.id)

        self.assertEqual(obs.self_state["situation_summary"], "stable baseline conditions")

    def test_situation_summary_crisis_agent(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.12, social_tension=0.90)
        focal.risk.debt_crisis_active_years = 2
        focal.risk.regime_crisis_active_years = 1
        focal.economy._gdp_prev = 1.04
        focal.economy._debt_gdp_prev = 0.74
        focal.society._trust_prev = 0.18
        focal.society._tension_prev = 0.82
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)

        obs = build_observation(world, focal.id)
        summary = obs.self_state["situation_summary"]

        self.assertIn("active crises", summary)
        self.assertIn("debt_crisis", summary)
        self.assertIn("regime_crisis", summary)

    def test_peer_standing_present(self) -> None:
        focal = self._make_agent(agent_id="A")
        focal.economy.public_debt = 1.0
        focal.economy.climate_damage_factor = 0.22
        peer = self._make_agent(agent_id="B")
        peer.economy.gdp = 0.8
        peer.economy.public_debt = 0.3
        peer.economy.climate_damage_factor = 0.12
        third = self._make_agent(agent_id="C")
        third.economy.gdp = 1.4
        third.economy.public_debt = 0.5
        third.economy.climate_damage_factor = 0.35
        world = self._make_world(focal, peer, third)

        obs = build_observation(world, focal.id)
        peer_standing = obs.self_state["competitive"]["peer_standing"]

        self.assertIn("peer_standing", obs.self_state["competitive"])
        self.assertGreaterEqual(peer_standing["gdp_percentile"], 0.0)
        self.assertLessEqual(peer_standing["gdp_percentile"], 1.0)
        self.assertIsInstance(peer_standing["debt_gdp_vs_median"], float)
        self.assertIsInstance(peer_standing["trust_vs_median"], float)
        self.assertIsInstance(peer_standing["climate_damage_rank"], int)

    def test_policy_history_empty_on_step0(self) -> None:
        focal = self._make_agent(agent_id="A")
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)

        obs = build_observation(world, focal.id)

        self.assertEqual(obs.memory["policy_history"], [])

    def test_policy_history_populated_after_steps(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.18, social_tension=0.82)
        focal.economy.public_debt = 2.4
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)
        policies = {
            focal.id: self._austerity_policy(focal.id),
            peer.id: self._status_quo_policy(peer.id),
        }

        for _ in range(3):
            step_world(world, policies, memory={})

        obs = build_observation(world, focal.id)
        history = obs.memory["policy_history"]

        self.assertEqual(len(history), 3)
        record = history[0]
        self.assertIn("action", record)
        self.assertIn("gdp_delta", record)
        self.assertIn("crises_after", record)

    def test_policy_history_rolling_window(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.18, social_tension=0.82)
        focal.economy.public_debt = 2.4
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)
        policies = {
            focal.id: self._austerity_policy(focal.id),
            peer.id: self._status_quo_policy(peer.id),
        }

        for _ in range(5):
            step_world(world, policies, memory={})

        obs = build_observation(world, focal.id)
        history = obs.memory["policy_history"]

        self.assertEqual(len(history), cal.POLICY_LOG_DEPTH)
        self.assertEqual(history[-1]["step"], 5)

    def test_policy_history_no_private_field_leak(self) -> None:
        focal = self._make_agent(agent_id="A", trust_gov=0.18, social_tension=0.82)
        focal.economy.public_debt = 2.4
        peer = self._make_agent(agent_id="B")
        world = self._make_world(focal, peer)
        policies = {
            focal.id: self._austerity_policy(focal.id),
            peer.id: self._status_quo_policy(peer.id),
        }

        for _ in range(2):
            step_world(world, policies, memory={})

        obs = build_observation(world, focal.id)
        for record in obs.memory["policy_history"]:
            self.assertFalse(any(key.startswith("_") for key in record))
