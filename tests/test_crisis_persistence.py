from __future__ import annotations

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
from gim.core.social import check_debt_crisis, check_regime_stability


class CrisisPersistenceTests(unittest.TestCase):
    def _make_agent(
        self,
        *,
        agent_id: str = "A",
        name: str = "Agent A",
        gdp: float = 1.0,
        public_debt: float = 3.0,
        unemployment: float = 0.08,
        trust_gov: float = 0.15,
        social_tension: float = 0.92,
        climate_shock_years: int = 0,
        regime_stability: float = 0.20,
        debt_crisis_prone: float = 1.0,
    ) -> AgentState:
        economy = EconomyState(
            gdp=gdp,
            capital=2.0,
            population=50_000_000,
            public_debt=public_debt,
            fx_reserves=0.1,
            unemployment=unemployment,
            climate_shock_years=climate_shock_years,
        )
        economy.gdp_per_capita = economy.gdp * 1e12 / economy.population
        return AgentState(
            id=agent_id,
            type="country",
            name=name,
            region="test",
            economy=economy,
            resources={
                "energy": ResourceSubState(own_reserve=10.0, production=1.0, consumption=1.2),
                "food": ResourceSubState(own_reserve=8.0, production=1.0, consumption=1.0),
                "metals": ResourceSubState(own_reserve=6.0, production=1.0, consumption=1.0),
            },
            society=SocietyState(
                trust_gov=trust_gov,
                social_tension=social_tension,
                inequality_gini=42.0,
            ),
            climate=ClimateSubState(climate_risk=0.5, co2_annual_emissions=0.2),
            culture=CulturalState(),
            technology=TechnologyState(tech_level=1.0, military_power=1.0, security_index=0.5),
            risk=RiskState(
                water_stress=0.4,
                regime_stability=regime_stability,
                debt_crisis_prone=debt_crisis_prone,
                conflict_proneness=0.3,
            ),
        )

    def _make_world(self, *agents: AgentState) -> WorldState:
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
                temperature_global=1.2,
                biodiversity_index=0.72,
                temperature_ocean=0.8,
            ),
            relations=relations,
        )

    def test_debt_crisis_persists_multiple_years(self) -> None:
        agent = self._make_agent(trust_gov=0.35, social_tension=0.70)
        world = self._make_world(agent)

        check_debt_crisis(agent, world)
        first_gdp = agent.economy.gdp
        first_trust = agent.society.trust_gov
        first_tension = agent.society.social_tension

        self.assertEqual(agent.risk.debt_crisis_active_years, 1)

        check_debt_crisis(agent, world)
        self.assertEqual(agent.risk.debt_crisis_active_years, 2)
        self.assertLess(agent.economy.gdp, first_gdp)
        self.assertLess(agent.society.trust_gov, first_trust)
        self.assertGreater(agent.society.social_tension, first_tension)

    def test_regime_crisis_persists_multiple_years(self) -> None:
        agent = self._make_agent()

        check_regime_stability(agent)
        first_gdp = agent.economy.gdp
        first_capital = agent.economy.capital

        self.assertEqual(agent.risk.regime_crisis_active_years, 1)

        agent.society.trust_gov = 0.10
        agent.society.social_tension = 0.92
        check_regime_stability(agent)
        self.assertEqual(agent.risk.regime_crisis_active_years, 2)
        self.assertLess(agent.economy.gdp, first_gdp)
        self.assertLess(agent.economy.capital, first_capital)

    def test_debt_onset_is_harsher_than_persistence(self) -> None:
        self.assertLess(cal.DEBT_CRISIS_GDP_MULT, cal.DEBT_CRISIS_PERSIST_GDP_MULT)

    def test_debt_crisis_counter_is_capped(self) -> None:
        agent = self._make_agent(trust_gov=0.35, social_tension=0.70)
        world = self._make_world(agent)
        agent.risk.debt_crisis_active_years = cal.DEBT_CRISIS_MAX_YEARS

        check_debt_crisis(agent, world)

        self.assertEqual(agent.risk.debt_crisis_active_years, cal.DEBT_CRISIS_MAX_YEARS)

    def test_no_hidden_crisis_state_attributes_are_created(self) -> None:
        agent = self._make_agent(trust_gov=0.35, social_tension=0.70)
        world = self._make_world(agent)

        check_debt_crisis(agent, world)
        check_regime_stability(agent)

        self.assertFalse(hasattr(agent, "_debt_crisis_this_step"))
        self.assertFalse(hasattr(agent, "_collapsed_this_step"))

    def test_stable_agent_has_no_crisis_flags(self) -> None:
        agent = self._make_agent(
            public_debt=0.3,
            trust_gov=0.62,
            social_tension=0.22,
            regime_stability=0.82,
            debt_crisis_prone=0.2,
        )
        world = self._make_world(agent)

        obs = build_observation(world, agent.id)

        self.assertEqual(obs.self_state["competitive"]["crisis_flags"], [])
        self.assertNotIn("CRISIS:", obs.summary)

    def test_observation_contains_crisis_flags(self) -> None:
        focal = self._make_agent(climate_shock_years=2)
        peer = self._make_agent(agent_id="B", name="Agent B", trust_gov=0.5, social_tension=0.3)
        peer.active_sanctions[focal.id] = "strong"
        peer.sanction_years[focal.id] = 2
        third = self._make_agent(agent_id="C", name="Agent C", trust_gov=0.55, social_tension=0.25)
        third.active_sanctions[focal.id] = "mild"
        third.sanction_years[focal.id] = 1
        world = self._make_world(focal, peer, third)
        world.relations[focal.id][peer.id].at_war = True
        world.relations[focal.id][peer.id].war_years = 2

        check_debt_crisis(focal, world)
        check_regime_stability(focal)
        obs = build_observation(world, focal.id)
        crisis_types = {flag["type"] for flag in obs.self_state["competitive"]["crisis_flags"]}

        self.assertIn("debt_crisis", crisis_types)
        self.assertIn("regime_crisis", crisis_types)
        self.assertIn("climate_shock", crisis_types)
        self.assertIn("active_war", crisis_types)
        self.assertIn("sanctions_pressure", crisis_types)
        self.assertIn("CRISIS:", obs.summary)

    def test_crisis_flags_clear_on_recovery(self) -> None:
        agent = self._make_agent()
        world = self._make_world(agent)

        check_debt_crisis(agent, world)
        check_regime_stability(agent)
        self.assertGreater(agent.risk.debt_crisis_active_years, 0)
        self.assertGreater(agent.risk.regime_crisis_active_years, 0)

        agent.economy.public_debt = 0.4 * agent.economy.gdp
        agent.risk.debt_crisis_prone = 0.1
        agent.society.trust_gov = 0.55
        agent.society.social_tension = 0.25
        agent.risk.regime_stability = 0.85
        agent.economy.climate_shock_years = 0

        check_debt_crisis(agent, world)
        check_regime_stability(agent)
        self.assertEqual(agent.risk.debt_crisis_active_years, 2)
        self.assertEqual(agent.risk.regime_crisis_active_years, 0)

        check_debt_crisis(agent, world)
        check_regime_stability(agent)
        obs = build_observation(world, agent.id)

        self.assertEqual(agent.risk.debt_crisis_active_years, 0)
        self.assertEqual(agent.risk.regime_crisis_active_years, 0)
        self.assertEqual(obs.self_state["competitive"]["crisis_flags"], [])
        self.assertNotIn("CRISIS:", obs.summary)

    def test_near_threshold_debt_crisis_has_two_step_hysteresis(self) -> None:
        focal = self._make_agent(
            public_debt=1.25,
            trust_gov=0.35,
            social_tension=0.70,
            regime_stability=0.20,
        )
        peer = self._make_agent(
            agent_id="B",
            name="Agent B",
            public_debt=2.4,
            trust_gov=0.40,
            social_tension=0.50,
            regime_stability=0.20,
        )
        world = self._make_world(focal, peer)
        world.relations[focal.id][peer.id].trade_intensity = 1.0
        world.relations[focal.id][peer.id].trust = 0.2

        def _noop(agent_id: str):
            def _policy(obs, memory_summary=None):  # noqa: ARG001
                return Action(
                    agent_id=agent_id,
                    time=obs.time,
                    domestic_policy=DomesticPolicy(0.0, 0.0, 0.0, 0.0, "none"),
                    foreign_policy=ForeignPolicy(),
                    finance=FinancePolicy(0.0, 0.0),
                )

            return _policy

        policies = {focal.id: _noop(focal.id), peer.id: _noop(peer.id)}

        step_world(
            world,
            policies,
            enable_extreme_events=False,
            apply_political_filters=False,
            apply_institutions=False,
        )
        self.assertEqual(world.agents[focal.id].risk.debt_crisis_active_years, 1)

        step_world(
            world,
            policies,
            enable_extreme_events=False,
            apply_political_filters=False,
            apply_institutions=False,
        )
        self.assertEqual(world.agents[focal.id].risk.debt_crisis_active_years, 2)

        step_world(
            world,
            policies,
            enable_extreme_events=False,
            apply_political_filters=False,
            apply_institutions=False,
        )
        self.assertEqual(world.agents[focal.id].risk.debt_crisis_active_years, 0)

    def test_debt_spiral_integration_reaches_multi_year_persistence(self) -> None:
        focal = self._make_agent(
            public_debt=3.0,
            trust_gov=0.35,
            social_tension=0.70,
            regime_stability=0.20,
        )
        peer = self._make_agent(
            agent_id="B",
            name="Agent B",
            public_debt=2.4,
            trust_gov=0.40,
            social_tension=0.50,
            regime_stability=0.20,
        )
        world = self._make_world(focal, peer)
        world.relations[focal.id][peer.id].trade_intensity = 1.0
        world.relations[focal.id][peer.id].trust = 0.2
        initial_gdp = focal.economy.gdp
        peak_years = 0

        def _noop(agent_id: str):
            def _policy(obs, memory_summary=None):  # noqa: ARG001
                return Action(
                    agent_id=agent_id,
                    time=obs.time,
                    domestic_policy=DomesticPolicy(0.0, 0.0, 0.0, 0.0, "none"),
                    foreign_policy=ForeignPolicy(),
                    finance=FinancePolicy(0.0, 0.0),
                )

            return _policy

        policies = {focal.id: _noop(focal.id), peer.id: _noop(peer.id)}

        for _ in range(10):
            step_world(
                world,
                policies,
                enable_extreme_events=False,
                apply_political_filters=False,
                apply_institutions=False,
            )
            peak_years = max(peak_years, world.agents[focal.id].risk.debt_crisis_active_years)

        self.assertGreaterEqual(peak_years, 3)
        self.assertLess(world.agents[focal.id].economy.gdp, initial_gdp)


if __name__ == "__main__":
    unittest.main()
