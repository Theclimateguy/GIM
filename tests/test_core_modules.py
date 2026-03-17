from __future__ import annotations

import unittest

from gim.core.actions import apply_action
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
    InstitutionState,
    RelationState,
    ResourceSubState,
    RiskState,
    SanctionsAction,
    SecurityActions,
    SocietyState,
    TechnologyState,
    TradeRestriction,
    WorldState,
)
from gim.core.credit_rating import update_credit_ratings
from gim.core.economy import compute_effective_interest_rate
from gim.core.geopolitics import apply_security_actions, update_active_conflicts
from gim.core.institutions import update_institutions
from gim.core.metrics import compute_crisis_flags
from gim.core.political_dynamics import apply_political_constraints
from gim.core.resources import update_global_resource_prices
from gim.core.simulation import step_world


class CoreModuleTests(unittest.TestCase):
    def _make_agent(
        self,
        *,
        agent_id: str,
        gdp: float = 1.0,
        public_debt: float = 0.6,
        trust_gov: float = 0.6,
        social_tension: float = 0.2,
        regime_stability: float = 0.8,
    ) -> AgentState:
        economy = EconomyState(
            gdp=gdp,
            capital=3.0 * gdp,
            population=50_000_000,
            public_debt=public_debt,
            fx_reserves=0.2,
            unemployment=0.06,
            inflation=0.03,
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
            climate=ClimateSubState(climate_risk=0.6, co2_annual_emissions=0.4, biodiversity_local=0.75),
            culture=CulturalState(),
            technology=TechnologyState(tech_level=1.0, military_power=1.0, security_index=0.5),
            risk=RiskState(
                water_stress=0.4,
                regime_stability=regime_stability,
                debt_crisis_prone=0.8,
                conflict_proneness=0.4,
            ),
        )

    def _make_world(self, *agents: AgentState) -> WorldState:
        relations = {agent.id: {} for agent in agents}
        for left in agents:
            for right in agents:
                if left.id == right.id:
                    continue
                relations[left.id][right.id] = RelationState(
                    trade_intensity=0.6,
                    trust=0.3,
                    conflict_level=0.3,
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

    def test_actions_climate_policy_reduces_emissions_and_raises_debt(self) -> None:
        agent = self._make_agent(agent_id="A")
        world = self._make_world(agent)
        before_emissions = agent.climate.co2_annual_emissions
        before_debt = agent.economy.public_debt
        action = Action(
            agent_id="A",
            time=0,
            domestic_policy=DomesticPolicy(
                tax_fuel_change=0.3,
                social_spending_change=0.01,
                military_spending_change=0.0,
                rd_investment_change=0.0,
                climate_policy="moderate",
            ),
            foreign_policy=ForeignPolicy(),
            finance=FinancePolicy(0.0, 0.0),
        )

        apply_action(world, action)

        self.assertLess(agent.climate.co2_annual_emissions, before_emissions)
        self.assertGreater(agent.economy.public_debt, before_debt)

    def test_credit_rating_marks_distressed_agent_and_interest_reflects_zone(self) -> None:
        distressed = self._make_agent(
            agent_id="A",
            gdp=1.0,
            public_debt=10.0,
            trust_gov=0.01,
            social_tension=0.99,
            regime_stability=0.01,
        )
        distressed.economy.unemployment = 0.30
        distressed.economy.inflation = 0.18
        distressed.economy.fx_reserves = 0.0
        distressed.risk.water_stress = 1.0
        distressed.resources["energy"] = ResourceSubState(
            own_reserve=0.1,
            production=0.1,
            consumption=2.0,
        )
        distressed.resources["food"] = ResourceSubState(
            own_reserve=0.1,
            production=0.1,
            consumption=2.0,
        )
        distressed.resources["metals"] = ResourceSubState(
            own_reserve=0.1,
            production=0.1,
            consumption=2.0,
        )
        partner = self._make_agent(agent_id="B", public_debt=5.0, trust_gov=0.05, social_tension=0.95)
        world = self._make_world(distressed, partner)
        world.relations["A"]["B"].at_war = True
        world.relations["A"]["B"].conflict_level = 1.0
        world.relations["A"]["B"].trust = 0.0
        partner.active_sanctions["A"] = "strong"
        partner.sanction_years["A"] = 3
        memory = {
            "A": [
                {"time": 0, "gdp": 2.0, "social_tension": 0.5, "trust_gov": 0.5},
                {"time": 1, "gdp": 1.0, "social_tension": 0.99, "trust_gov": 0.01},
            ]
        }

        update_credit_ratings(world, memory=memory)

        self.assertIn(distressed.credit_zone, {"distressed", "default"})

        distressed.credit_zone = "default"
        default_rate = compute_effective_interest_rate(distressed, world)
        distressed.credit_zone = "investment"
        investment_rate = compute_effective_interest_rate(distressed, world)
        self.assertGreater(default_rate, investment_rate)

    def test_geopolitics_conflict_sets_war_and_reduces_trade(self) -> None:
        actor = self._make_agent(agent_id="A")
        target = self._make_agent(agent_id="B")
        world = self._make_world(actor, target)
        world.relations["A"]["B"].trust = 0.10
        world.relations["B"]["A"].trust = 0.10
        world.relations["A"]["B"].conflict_level = 0.85
        world.relations["B"]["A"].conflict_level = 0.85
        before_trade = world.relations["A"]["B"].trade_intensity
        action = Action(
            agent_id="A",
            time=0,
            domestic_policy=DomesticPolicy(0.0, 0.0, 0.0, 0.0, "none"),
            foreign_policy=ForeignPolicy(
                security_actions=SecurityActions(type="conflict", target="B")
            ),
            finance=FinancePolicy(0.0, 0.0),
        )

        apply_security_actions(world, {"A": action})
        update_active_conflicts(world)

        self.assertTrue(world.relations["A"]["B"].at_war)
        self.assertLess(world.relations["A"]["B"].trade_intensity, before_trade)

    def test_institutions_reduce_trade_barriers_for_members(self) -> None:
        left = self._make_agent(agent_id="A")
        right = self._make_agent(agent_id="B")
        world = self._make_world(left, right)
        world.institutions = {
            "TradeClub": InstitutionState(
                id="TradeClub",
                name="TradeClub",
                org_type="TradeOrg",
                mandate=["trade_rules"],
                members=["A", "B"],
                legitimacy=0.8,
            )
        }
        world.relations["A"]["B"].trade_barrier = 0.40

        update_institutions(world)

        self.assertLess(world.relations["A"]["B"].trade_barrier, 0.40)
        self.assertTrue(world.institution_reports)

    def test_metrics_emit_expected_crisis_flags(self) -> None:
        stable = self._make_agent(agent_id="A")
        stressed = self._make_agent(agent_id="B", public_debt=2.0)
        stressed.risk.debt_crisis_active_years = 2
        world = self._make_world(stable, stressed)

        self.assertEqual(compute_crisis_flags(stable, world), [])
        self.assertIn(
            "debt_crisis",
            {flag["type"] for flag in compute_crisis_flags(stressed, world)},
        )

    def test_political_constraints_downgrade_overreach(self) -> None:
        agent = self._make_agent(agent_id="A")
        agent.political.policy_space = 1.0
        agent.political.sanction_propensity = 0.2
        action = Action(
            agent_id="A",
            time=0,
            domestic_policy=DomesticPolicy(0.0, 0.0, 0.0, 0.0, "none"),
            foreign_policy=ForeignPolicy(
                sanctions_actions=[SanctionsAction(target="B", type="strong")],
                trade_restrictions=[TradeRestriction(target="B", level="hard")],
            ),
            finance=FinancePolicy(0.0, 0.0),
        )

        constrained = apply_political_constraints(action, agent)

        self.assertEqual(constrained.foreign_policy.sanctions_actions[0].type, "mild")
        self.assertEqual(constrained.foreign_policy.trade_restrictions[0].level, "soft")

    def test_resource_prices_rise_under_shortage(self) -> None:
        agent = self._make_agent(agent_id="A")
        agent.resources["energy"].production = 0.5
        agent.resources["energy"].consumption = 2.0
        world = self._make_world(agent)
        before = world.global_state.prices["energy"]

        update_global_resource_prices(world)

        self.assertGreater(world.global_state.prices["energy"], before)

    def test_simulation_logs_policy_failures_before_fallback(self) -> None:
        agent = self._make_agent(agent_id="A")
        world = self._make_world(agent)

        def bad_policy(obs):  # noqa: ARG001
            raise RuntimeError("boom")

        with self.assertLogs("gim.core.simulation", level="WARNING") as captured:
            next_world = step_world(
                world,
                {"A": bad_policy},
                enable_extreme_events=False,
                apply_institutions=False,
            )

        self.assertEqual(next_world.time, 1)
        self.assertTrue(any("falling back to simple policy" in entry for entry in captured.output))
