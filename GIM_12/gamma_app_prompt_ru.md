# Gamma App Prompt: GIM_12 Mechanics

Сделай презентацию на русском языке о механике модели `GIM_12`.
Каждый блок между `---` должен быть отдельным слайдом.
Не сливай соседние блоки в один слайд.
Сохраняй технический стиль: короткие списки, формулы в моноширинном виде, названия переменных как в коде.
В каждом слайде явно показывай: какие переменные используются, откуда они берутся, как считаются и как влияют на решения агента.

---

# Слайд 1. Что моделирует GIM_12 и как устроен шаг симуляции

`GIM_12` — это мультиагентная модель мировой экономики, ресурсов, климата, общества и геополитики. Активная папка запуска: `GIM_12/`. Реальное ядро модели находится в legacy compatibility path `legacy/GIM_11_1/gim_11_1/`.

Источники механики:
`core.py`, `world_factory.py`, `simulation.py`, `policy.py`, `actions.py`, `political_dynamics.py`, `geopolitics.py`, `resources.py`, `climate.py`, `economy.py`, `social.py`, `metrics.py`, `institutions.py`, `memory.py`, `credit_rating.py`.

Основной годовой цикл:
`compute_relative_metrics -> update_political_states -> update_institutions -> build_observation -> generate Action -> apply_political_constraints -> resolve_foreign_policy -> apply_sanctions_effects -> apply_security_actions -> update_active_conflicts -> apply_trade_barrier_effects -> apply_action -> apply_trade_deals -> update_relations_endogenous -> update_resource_stocks -> update_global_resource_prices -> update_global_climate -> update_climate_risks -> apply_climate_extreme_events -> update_economy_output -> update_public_finances -> check_debt_crisis -> update_migration_flows -> update_population -> update_social_state -> check_regime_stability -> update_agent_memory -> update_credit_ratings`.

Главная идея:
агенты меняют политику, политика меняет экономику и внешние отношения, это меняет ресурсы, климат, доверие, конфликты и кредитный риск, а эти метрики в следующем году влияют на новые решения.

---

# Слайд 2. State of the Agent: прямое состояние агента, признаки и источники

Состояние агента хранится в `AgentState`.

Источники признаков агента:
`agent_states.csv` — начальные наблюдаемые параметры страны.
`world_factory.py` — инициализация derived-полей.
`metrics.py`, `political_dynamics.py`, `credit_rating.py` — производные метрики.
`relations`, `institutions`, `memory` — внешние и исторические сигналы.

Прямые блоки состояния:
`economy`: `gdp`, `capital`, `population`, `public_debt`, `fx_reserves`, `taxes`, `gov_spending`, `social_spending`, `military_spending`, `rd_spending`, `climate_adaptation_spending`, `interest_payments`, `net_exports`, `gdp_per_capita`, `unemployment`, `inflation`, `birth_rate`, `death_rate`, `climate_shock_years`, `climate_shock_penalty`.

`resources`: по `energy`, `food`, `metals` хранятся `own_reserve`, `production`, `consumption`, `efficiency`.

`society`: `trust_gov`, `social_tension`, `inequality_gini`.

`climate`: `climate_risk`, `co2_annual_emissions`, `biodiversity_local`.

`culture`: `pdi`, `idv`, `mas`, `uai`, `lto`, `ind`, `survival_self_expression`, `traditional_secular`, `regime_type`.

`technology`: `tech_level`, `military_power`, `security_index`.

`risk`: `water_stress`, `regime_stability`, `debt_crisis_prone`, `conflict_proneness`.

`political`: `legitimacy`, `protest_pressure`, `hawkishness`, `protectionism`, `coalition_openness`, `sanction_propensity`, `policy_space`, `last_block_change`.

Дополнительные поля:
`alliance_block`, `active_sanctions`, `sanction_years`, `credit_rating`, `credit_zone`, `credit_risk_score`, `credit_rating_details`.

---

# Слайд 3. State of the Agent: производные признаки и математика расчета

Базовые derived-показатели агента:

`gdp_per_capita = gdp * 1e12 / population`

`reserve_years[resource] = own_reserve / production`

`debt_stress = min(max(public_debt / gdp - 1.0, 0) * debt_crisis_prone, 3.0)`

`protest_risk = clamp01((0.6 * social_tension + 0.3 * (1 - trust_gov) + 0.1 * (inequality_gini / 100)) * (0.5 + 0.5 * (1 - regime_stability)))`

Политические метрики агента:

`legitimacy = 0.6 * trust_gov + 0.4 * (1 - social_tension)`

`protest_pressure = 0.5 * protest_risk + 0.5 * social_tension`

`resource_stress = 0.5 * stress(energy_years, 5) + 0.3 * stress(food_years, 3) + 0.2 * stress(metals_years, 5)`

`hawkishness = 0.3 * conflict_proneness + 0.25 * (1 - trust_gov) + 0.25 * (1 - regime_stability) + 0.2 * resource_stress`

`protectionism = 0.4 * unemployment + 0.3 * (inequality_gini / 100) + 0.3 * (1 - trust_gov)`

`coalition_openness = 0.6 * trust_gov + 0.4 * (1 - social_tension)`

`sanction_propensity = 0.6 * hawkishness + 0.4 * (1 - coalition_openness)`

`policy_space = 0.5 * legitimacy + 0.3 * (1 - protest_pressure) + 0.2 * (1 - debt_stress / 3)`

Сравнительные метрики агента:

`gdp_share = gdp_i / sum_j gdp_j`

`gdp_rank` — место страны по GDP среди всех агентов.

`influence_score = ln(1 + gdp) + ln(1 + population / 1e6) + 0.5 * ln(1 + trade_degree)`

`security_margin = own_military_power / avg_neighbor_military_power`

Эти признаки попадают в `Observation.self_state["competitive"]` и используются policy-модулем при выборе действия.

---

# Слайд 4. State of the World: глобальное состояние, отношения, институты и источники

Состояние мира хранится в `WorldState`.

Источники состояния мира:
`agent_states.csv` — начальные данные стран.
`world_factory.py` — генерация стартового `relations` и `global_state`.
`institutions.py` — построение международных институтов.
`simulation.py` — ежегодное обновление общего состояния.

Блок `global_state`:
`co2`, `temperature_global`, `temperature_ocean`, `forcing_total`, `biodiversity_index`, `carbon_pools`, `baseline_gdp_pc`, `prices`, `global_reserves`.

Начальные глобальные константы:
`CO2_STOCK_2023_GT = 3270.0`
`CO2_PREINDUSTRIAL_GT = 2184.0`
`TGLOBAL_2023_C = 1.2`
`WORLD_PROVEN_RESERVES_ZJ = 32.5`
`WORLD_ANNUAL_SUPPLY_CAP_ZJ = 0.65`

Межстрановые отношения `RelationState` для каждой направленной пары:
`trade_intensity`, `trust`, `conflict_level`, `trade_barrier`, `at_war`, `war_years`, `war_start_gdp`, `war_start_pop`, `war_start_resource`.

Стартовые отношения:
`trade_intensity = 0.5`
`trust = 0.6`
`conflict_level = 0.1`
`trade_barrier = 0.0`

Институты:
`UN`, `UNSC`, `IMF`, `WorldBank`, `FSB`, `WTO`, `EU`, `USMCA`, `ASEAN`, `UNFCCC`, `GCF`, `IPCC`, `NATO`, `WHO`, `ILO`, `UNEP_UNESCO`.

Они добавляют в мир `institution_reports`, которые затем видят все агенты в наблюдении.

---

# Слайд 5. State of the World: математика глобальных переменных и отношений

Базовые мировые агрегаты:

`baseline_gdp_pc = sum_i gdp_i * 1e12 / sum_i population_i`

`biodiversity_index = weighted_mean(biodiversity_local_i, weight = population_i^0.3)`

Эффективная торговая связность пары:

`effective_trade_intensity = trade_intensity * (1 - clamp01(trade_barrier))`

Глобальные цены ресурсов:

`imbalance = (demand - supply) / (supply + eps)`

`price_next = clamp(price * (1 + alpha * imbalance), min_price, max_price)`

Энергетические квоты:
глобальные запасы энергии и yearly cap распределяются пропорционально `energy.own_reserve` стран.

Эндогенная динамика конфликтов:

`conflict_drift = 0.02 * (0.1 - conflict_level)`

`conflict_push = 0.04 * trade_short + 0.05 * avg_tension + 0.06 * military_gap + 0.04 * trade_barrier + 0.03 * sanction_flag + propagation + block_rivalry - mediation`

`conflict_level_next = clamp01(conflict_level + conflict_drift + conflict_push)`

Эндогенная динамика доверия:

`trust_drift = 0.02 * (0.6 - trust)`

`trust_push = 0.04 * trade_gap - 0.05 * conflict_level - 0.04 * avg_tension - 0.05 * trade_barrier - 0.03 * sanction_flag + 0.5 * mediation`

`trust_next = clamp01(trust + trust_drift + trust_push)`

Институты меняют мир слабо, но системно:
`TradeOrg` снижает барьеры,
`FinanceOrg` добавляет ликвидность,
`SecurityOrg` снижает конфликт,
`ClimateOrg` снижает `climate_risk`,
`SocialOrg` снижает `social_tension` и повышает `trust_gov`.

---

# Слайд 6. State of the World: экономика, ресурсы и климат как глобальная физика модели

Экономика страны:

`GDP_potential = tfp * tech_factor * K^0.30 * L^0.60 * E^0.10`

`tech_factor = 1 + 0.6 * max(0, tech_level - 1)`

`L = population / 1e9`

`E = (energy_consumption / 1000) * energy_efficiency`

`GDP_target = GDP_potential * scale_factor * effective_damage_multiplier`

`GDP_next = (1 - adjust_speed) * GDP_now + adjust_speed * GDP_target`

Капитал:

`savings_rate = clamp(0.24 * (0.7 + 0.6 * regime_stability - 0.4 * social_tension), 0.05, 0.40)`

`capital_next = (1 - 0.05) * capital + savings_rate * gdp`

TFP:

`tfp_growth = clamp(0.01 + 2.0 * rd_share * (1 + 0.3 * avg_trade) + 0.02 * avg_tech_gap, -0.05, 0.05)`

`tfp_next = tfp * (1 + tfp_growth)`

Выбросы:

`emissions = gdp * base_intensity * exp(-0.12 * max(0, tech_level - 1)) * (1 / efficiency) * exp(-0.049 * time) * tax_effect * (1 - policy_reduction) * 1.8`

Глобальный климат:

`pool_i(t+1) = pool_i(t) * exp(-dt / tau_i) + frac_i * total_emissions`

`CO2 = CO2_preindustrial + sum(pool_i)`

`F_CO2 = 5.35 * ln(Cppm / C0ppm)`

`T_surface(t+1) = T_surface + dt / Cs * (F_total - lambda * T_surface - k * (T_surface - T_ocean))`

Климатический риск страны:

`base = clamp01(0.3 + 0.45 * water_stress + 0.15 * gini_norm)`

`target = clamp01(base + (1 - base) * (1 - exp(-0.45 * deltaT)))`

`climate_risk_next = climate_risk + 0.06 * (target - climate_risk)`

Экстремальные события:
вероятность растет с `climate_risk` и температурой, а ущерб зависит от `resilience`, которая строится из `regime_stability`, `tech_level`, `trust_gov` и `climate_adaptation_spending / gdp`.

---

# Слайд 7. Как агент принимает решения: реальные policy-переменные и допустимые границы

Агент выбирает объект `Action`.

Источники решения:
`Observation` текущего года,
`memory_summary` последних лет,
режим policy: `simple`, `growth`, `llm`.

Внутренние управляемые переменные:
`tax_fuel_change` в диапазоне `[-1.5, 1.5]`
`social_spending_change` в диапазоне `[-0.015, 0.020]`
`military_spending_change` в диапазоне `[-0.010, 0.015]`
`rd_investment_change` в диапазоне `[-0.002, 0.008]`
`climate_policy` в одном из состояний: `none`, `weak`, `moderate`, `strong`

Внешние управляемые переменные:
до 4 `TradeDeal`
до 2 `SanctionsAction`
до 2 `TradeRestriction`
один `SecurityActions`

Структура `TradeDeal`:
`partner`, `resource`, `direction`, `volume_change`, `price_preference`

Структура `SanctionsAction`:
`target`, `type`, `reason`

Структура `TradeRestriction`:
`target`, `level`, `reason`

Структура `SecurityActions`:
`type`, `target`

`FinancePolicy` существует в интерфейсе, но в текущем ядре не меняет физику шага напрямую.

---

# Слайд 8. Как policy-переменные меняют систему: механика внутренних и внешних действий

Механика внутренних действий:

`tax_fuel_change` уменьшает `gdp` и меняет `trust_gov` и `social_tension` через культурную чувствительность: `uai`, `pdi`, `idv`, `regime_type`, `unemployment`, `inequality_gini`.

`social_spending_change` меняет `social_spending`, `gov_spending`, `public_debt`, затем повышает `trust_gov` и снижает `social_tension`.

`military_spending_change` меняет `military_spending`, `gov_spending`, `public_debt`, повышает `military_power`, а также может повысить или снизить `trust_gov` в зависимости от `security_index`, `mas`, `survival_self_expression`, `regime_type`.

`rd_investment_change` меняет `rd_spending`, `gov_spending`, `public_debt`, повышает `tech_level`, увеличивает `resource.efficiency`, а затем через `tfp` и emissions влияет на рост и декарбонизацию.

`climate_policy` снижает GDP в краткосрочном периоде, но уменьшает выбросы через `policy_reduction` и может улучшать восприятие власти в обществах с высокой climate risk и высокой self-expression.

Механика внешних действий:

`TradeDeal` меняет `fx_reserves`, `net_exports`, `consumption` ресурса у импортера и повышает `trade_intensity` между странами.

`SanctionsAction` сначала является намерением, потом через политическую поддержку превращается в `active_sanctions`, которые уменьшают `trade_intensity`, `trust`, увеличивают `trade_barrier` и бьют по GDP цели.

`TradeRestriction` сначала является намерением, потом повышает `trade_barrier`, который затем снижает `trade_intensity`.

`SecurityActions` меняет `conflict_level`, `trust`, `military_power`, а при эскалации переводит пару стран в режим войны `at_war`.

---

# Слайд 9. Как оптимизируется поведение агента: objective function, thresholds и фильтры

Агент не оптимизирует абстрактное мировое благо. Он оптимизирует собственную устойчивость и относительную мощь.

Главные цели агента:
рост `gdp` и `gdp_per_capita`
сохранение `trust_gov` и сдерживание `social_tension`
удержание `security_margin >= 1.0`
избежание низких `reserve_years` по `energy`, `food`, `metals`
рост или защита `gdp_share`, `gdp_rank`, `influence_score`
избежание перехода в плохую кредитную зону

Ключевые трешхолды и hard constraints:

`policy_space` масштабирует почти все внутренние решения:
`scale = 0.4 + 0.6 * policy_space`

если `sanction_propensity < 0.2`, санкции обнуляются

если `0.2 <= sanction_propensity < 0.4`, `strong` санкции понижаются до `mild`

если `protectionism < 0.2`, торговые ограничения обнуляются

если `0.2 <= protectionism < 0.4`, `hard` ограничения понижаются до `soft`

если `protest_pressure > 0.7` и `legitimacy < 0.4`, security action запрещается

если `public_debt / gdp > 1.2`, положительное фискальное расширение ограничивается `2% GDP` вместо `3% GDP`

режимный коллапс:
если `trust_gov < 0.2` и `social_tension > 0.8`, происходят потери капитала, GDP и устойчивости режима

долговой кризис:
если `public_debt / gdp > 1.2` и `interest_rate > 0.12`, происходит haircut долга, падение GDP и рост безработицы

санкционная активация:
поддержка ниже `0.35` не запускает санкции, `0.35..0.65` дает `mild`, выше `0.65` дает `strong`

---

# Слайд 10. Как агент оптимизирует решения по шагам и как выглядит рациональная стратегия

Рациональная логика выбора действия:

сначала агент оценивает внутреннюю устойчивость:
`trust_gov`, `social_tension`, `policy_space`, `debt_stress`, `credit_risk_score`

затем агент оценивает производственную и ресурсную базу:
`gdp`, `capital`, `tech_level`, `reserve_years`, `fx_reserves`, `net_exports`

после этого агент оценивает внешнюю среду:
двусторонние `trade_intensity`, `trust`, `conflict_level`, `trade_barrier`, санкционное давление, `security_margin`, блоковую принадлежность, отчеты институтов

типовые правила оптимизации:

если низкие `reserve_years`, агент должен искать импорт или наращивать устойчивость через R&D и снижение конфликтов

если высокий `debt_stress`, агент должен избегать больших новых расходов и жестких shocks

если низкий `security_margin` при враждебных соседях, агент должен повышать `military_spending`, применять `arms_buildup` или укреплять связи внутри блока, но избегать ранней войны

если падают `gdp_share` и `influence_score`, агент должен усиливать рост через `rd_investment_change`, ограниченное социальное смягчение и торговую экспансию

если высок `climate_risk`, но страна богата и социально стабильна, агенту рационально использовать `climate_policy` как инструмент защиты долгосрочного роста

если конфликт велик, но `trust` еще не разрушен, агент рационально начинает с `sanctions`, `trade_restrictions` или `military_exercise`, а не с немедленной войны

итог:
оптимальный агент в `GIM_12` — это не максимизатор одной метрики, а адаптивный контроллер, который балансирует рост, устойчивость, безопасность, ресурсную обеспеченность и относительное положение страны в мировой системе.
