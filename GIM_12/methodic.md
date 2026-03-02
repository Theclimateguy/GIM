# Methodic Map (GIM_12)

Этот документ описывает актуальную модель в `GIM_12`, включая все ключевые взаимодействия, уравнения и метрики, фактически реализованные в коде.

## 1. Область и источник истины

- Активная папка запуска: `GIM_12/`.
- Ядро модели: `legacy/GIM_11_1/gim_11_1/`.
- `GIM_12/GIM_12.py` только подключает legacy-ядро и вызывает `gim_11_1.cli.main`.

Следовательно, все механики ниже основаны на коде:
- `core.py`, `world_factory.py`, `simulation.py`,
- `policy.py`, `actions.py`, `political_dynamics.py`, `geopolitics.py`,
- `resources.py`, `climate.py`, `economy.py`, `social.py`,
- `metrics.py`, `institutions.py`, `memory.py`, `credit_rating.py`,
- `logging_utils.py`.

## 2. Границы модели

Экзогенные входы:
- начальное состояние стран из CSV (`STATE_CSV`),
- лимит числа стран (`MAX_COUNTRIES`),
- режим политики (`POLICY_MODE=llm|simple|growth|auto`),
- параметры LLM (таймаут, ретраи, батчинг, параллелизм),
- случайность (`SIM_SEED`) для экстремальных климатических событий и авто-эскалации безопасности,
- флаги исполнения (`DISABLE_EXTREME_EVENTS`, `SAVE_CSV_LOGS`, `GENERATE_CREDIT_MAP`).

Эндогенно внутри модели формируются:
- GDP, капитал, долг, FX-резервы,
- ресурсные запасы/потоки/цены,
- доверие, напряженность, неравенство, миграция, демография,
- санкции, торговые барьеры, интенсивность торговли, конфликтность, войны,
- выбросы CO2, глобальный CO2, температура, биоразнообразие, климатические риски,
- политические метрики, сравнительные метрики, кредитный рейтинг (1..26).

## 3. Состояние системы (State Vector)

## 3.1 `WorldState`
- `time`
- `agents: Dict[str, AgentState]`
- `global_state: GlobalState`
- `relations: Dict[str, Dict[str, RelationState]]`
- `institutions: Dict[str, InstitutionState]`
- `institution_reports: List[Dict[str, Any]]`

## 3.2 `AgentState`
- Идентификация: `id`, `name`, `region`, `type`, `alliance_block`.
- Экономика (`EconomyState`): `gdp`, `capital`, `population`, `public_debt`, `fx_reserves`, `taxes`, `gov_spending`, `social_spending`, `military_spending`, `rd_spending`, `climate_adaptation_spending`, `interest_payments`, `net_exports`, `gdp_per_capita`, `unemployment`, `inflation`, `birth_rate`, `death_rate`, климатический шок (`climate_shock_years`, `climate_shock_penalty`).
- Ресурсы (`ResourceSubState`) по `energy|food|metals`: `own_reserve`, `production`, `consumption`, `efficiency`.
- Общество (`SocietyState`): `trust_gov`, `social_tension`, `inequality_gini`.
- Климат (`ClimateSubState`): `climate_risk`, `co2_annual_emissions`, `biodiversity_local`.
- Культура (`CulturalState`): Hofstede/World Values + `regime_type`.
- Технологии (`TechnologyState`): `tech_level`, `military_power`, `security_index`.
- Риски (`RiskState`): `water_stress`, `regime_stability`, `debt_crisis_prone`, `conflict_proneness`.
- Политика (`PoliticalState`): `legitimacy`, `protest_pressure`, `hawkishness`, `protectionism`, `coalition_openness`, `sanction_propensity`, `policy_space`, `last_block_change`.
- Санкции: `active_sanctions`, `sanction_years`.
- Кредитный блок: `credit_rating`, `credit_zone`, `credit_risk_score`, `credit_rating_details`.

## 3.3 `RelationState` (направленный граф)
- `trade_intensity`
- `trust`
- `conflict_level`
- `trade_barrier`
- `at_war`, `war_years`, `war_start_gdp`, `war_start_pop`, `war_start_resource`

Эффективная торговая интенсивность:

```text
effective_trade_intensity = trade_intensity * (1 - clamp01(trade_barrier))
```

## 3.4 `GlobalState`
- `co2`, `temperature_global`, `temperature_ocean`, `forcing_total`
- `biodiversity_index`
- `carbon_pools` (4-пуловая углеродная модель)
- `baseline_gdp_pc`
- `prices` по ресурсам
- `global_reserves` по ресурсам

## 4. Инициализация мира (`world_factory.py`)

1. CSV-валидация:
- обязательные колонки и обязательные числовые поля,
- опциональные числовые поля валидируются при наличии значения.

2. Начальные значения стран:
- `capital = 3.0 * gdp`,
- `gdp_per_capita = gdp * 1e12 / population`,
- дефолты по опциональным колонкам (если пусто в CSV):
  - `public_debt=0`,
  - `energy_reserve=20, energy_production=100, energy_consumption=100`,
  - `food_reserve=10, food_production=50, food_consumption=50`,
  - `metals_reserve=30, metals_production=20, metals_consumption=20`,
  - `co2_annual_emissions=0`, `biodiversity_local=0.8`,
  - `water_stress=0.5`, `regime_stability=0.6`, `debt_crisis_prone=0.5`, `conflict_proneness=0.4`,
  - `tech_level=1.0`, `military_power=1.0`, `security_index=0.5`,
  - `alliance_block="NonAligned"`.

3. Начальные отношения (для каждой пары стран):

```text
trade_intensity = 0.5
trust = 0.6
conflict_level = 0.1
trade_barrier = 0.0
```

4. Глобальные базисы:

```text
baseline_gdp_pc = (sum_i GDP_i) * 1e12 / (sum_i Population_i)
biodiversity_index(0) = weighted_mean(biodiversity_local_i, weight = population_i^0.3)
```

5. После сборки мира сразу выполняются:
- `update_political_states(world)`,
- `build_default_institutions(world)`,
- `update_credit_ratings(world, memory={})`.

## 5. Годовой цикл симуляции (`step_world`)

Порядок строго такой:
1. `compute_relative_metrics` (до генерации политик).
2. Обновление политических состояний стран.
3. Обновление институтов и формирование `institution_reports`.
4. Генерация действий стран:
- non-LLM: сразу,
- LLM: батчами и параллельно (`LLM_BATCH_SIZE`, `LLM_MAX_CONCURRENCY`) с `memory_summary`.
5. Применение политических ограничений (`apply_political_constraints`).
6. `resolve_foreign_policy`:
- санкции по intent + инерция,
- обновление торговых барьеров,
- обновление коалиций.
7. Эффекты санкций (`apply_sanctions_effects`).
8. Действия безопасности (`apply_security_actions`).
9. Поддержка активных войн (`update_active_conflicts`).
10. Эффекты торговых барьеров на `trade_intensity`.
11. Внутренние действия (`apply_action`).
12. Реализация торговых сделок (`apply_trade_deals`).
13. Эндогенное обновление отношений (`update_relations_endogenous`).
14. Логирование действий (если включено).
15. Ресурсы: квоты энергии -> обновление запасов -> обновление мировых цен.
16. Климат: глобальный климат -> климатические риски -> экстремальные события (если не отключены).
17. Экономика: обновление выпуска и капитала.
18. Госфинансы + проверка долгового кризиса.
19. Миграция.
20. Население, соцсостояние, проверка коллапса режима.
21. `compute_relative_metrics` (повторно после всех обновлений).
22. Обновление памяти агентов.
23. Обновление кредитных рейтингов.
24. `time += 1`.

## 6. Политики и нормализация действий

## 6.1 Режимы политик (`policy.py`)
- `simple`: детерминированный baseline.
- `growth`: детерминированная ростовая политика.
- `llm`: LLM-policy через DeepSeek API.
- `auto`: LLM только если выполнены предусловия.

LLM отключается принудительно при `USE_SIMPLE_POLICIES=1` или `NO_LLM=1`.

`FinancePolicy` (`borrow_from_global_markets`, `use_fx_reserves_change`) хранится в `Action`,
логируется и доступен для расширения, но в текущем ядре напрямую не применяется
в уравнениях шага.

## 6.2 Жесткие ограничители действия (`_normalize_action_for_stability`)
- `tax_fuel_change` in `[-1.5, 1.5]`
- `social_spending_change` in `[-0.015, 0.02]`
- `military_spending_change` in `[-0.01, 0.015]`
- `rd_investment_change` in `[-0.002, 0.008]`
- максимум 4 торговых сделки, 2 санкции, 2 торговых ограничения.
- `volume_change` сделки в `[0, 50]`.

## 6.3 Политические фильтры (`apply_political_constraints`)

Масштаб внутренней политики:

```text
scale = 0.4 + 0.6 * policy_space
```

Для налога на топливо при повышении дополнительно:

```text
tax_fuel_change *= max(0.2, 1 - 0.7 * protest_pressure)
```

После этого внутренние рычаги умножаются на `scale`.

Ограничения внешней политики:
- `sanction_propensity < 0.2` -> санкции обнуляются.
- `0.2 <= sanction_propensity < 0.4` -> `strong` понижается до `mild`.
- `protectionism < 0.2` -> торговые ограничения обнуляются.
- `0.2 <= protectionism < 0.4` -> `hard` понижается до `soft`.
- если `protest_pressure > 0.7` и `legitimacy < 0.4`, то security-action отключается.

## 7. Полный каталог взаимодействий между блоками

## 7.1 Политические метрики страны (`update_political_state`)

```text
legitimacy = 0.6*trust + 0.4*(1 - tension)
protest_pressure = 0.5*protest_risk + 0.5*tension

resource_stress =
  0.5*stress(energy_years,5) + 0.3*stress(food_years,3) + 0.2*stress(metals_years,5)

hawkishness =
  0.3*conflict_proneness + 0.25*(1-trust) + 0.25*(1-regime_stability) + 0.2*resource_stress

protectionism = 0.4*unemployment + 0.3*gini_norm + 0.3*(1-trust)
coalition_openness = 0.6*trust + 0.4*(1-tension)
sanction_propensity = 0.6*hawkishness + 0.4*(1-coalition_openness)

policy_space = 0.5*legitimacy + 0.3*(1-protest_pressure) + 0.2*(1-debt_stress_norm)
```

## 7.2 Санкции: intent -> активные санкции (`resolve_sanctions`)

Поддержка санкций:

```text
support =
  0.4*sanction_propensity(actor)
  + 0.3*conflict_level(actor,target)
  + 0.3*(1 - trust(actor,target))
  + intent_bonus
```

где `intent_bonus = 0.10` для `strong`, `0.05` для `mild`.

Поправка на блоки:
- общий блок (не `NonAligned`) -> `support *= 0.6`
- разные блоки -> `support += 0.05`

Тип санкции по поддержке:
- `<0.35`: `none`
- `0.35..0.65`: `mild`
- `>=0.65`: `strong`

Инерция:
- минимальная длительность санкций `min_duration = 2` года,
- даже при исчезновении intent санкции продолжают спадать по `sanction_years`.

## 7.3 Торговые ограничения и барьеры (`update_trade_barriers`)

Желаемый барьер:

```text
base = 0.15*protectionism + 0.25*conflict + 0.25*(1-trust)
if same_block: base *= 0.7
intent_boost = {none:0, soft:0.15, hard:0.35}
```

Если есть trade restriction intent или санкции:
- `desired = base + intent_boost`
- floor: `0.25` при mild-санкциях, `0.5` при strong-санкциях.

Если intent/санкций нет:
- при `trust<0.25` или `conflict>0.6`: `desired = base*0.7`
- иначе `desired = 0`.

Сглаживание:

```text
trade_barrier(t+1) = 0.7*trade_barrier(t) + 0.3*desired
```

## 7.4 Эффект барьеров на торговлю (`apply_trade_barrier_effects`)

```text
friction = 0.04*conflict + 0.02*avg_tension
decay = 0.05*trade_barrier + friction
trade_intensity *= (1 - decay)
```

## 7.5 Санкции как реализованный шок (`apply_sanctions_effects`)

На направленную пару actor->target:
- `mild`: `trade_intensity*=0.85`, `trust*=0.92`, `trade_barrier += 0.05`.
- `strong`: `trade_intensity*=0.65`, `trust*=0.85`, `trade_barrier += 0.15`, `actor.gdp*=0.995`.

На цель санкций (агрегировано по всем входящим санкциям, через sqrt-count):

```text
gdp_penalty = min(0.12, 0.01*sqrt(mild_count) + 0.03*sqrt(strong_count))
target.gdp *= (1 - gdp_penalty)
```

Социальная реакция цели зависит от культуры (`pdi`, self-expression, regime_type):
- автократии могут получить частичный rally-around-flag,
- демократии обычно теряют доверие и получают рост напряженности.

## 7.6 Безопасность и войны (`apply_security_actions`, `update_active_conflicts`)

Типы действий:
- `military_exercise`
- `arms_buildup`
- `border_incident`
- `conflict`

Автоэскалация (`_auto_security_action`) запускается, если игрок не задал security action и есть высокий `trigger`, зависящий от:
- двусторонней конфликтности/недоверия,
- ресурсного стресса,
- социальной напряженности,
- институциональной хрупкости (`1-regime_stability`).

Escalation gate:
- `conflict` может быть автоматически понижен до `border_incident`,
- `border_incident` может быть понижен до `military_exercise`,
чтобы избегать мгновенных катастрофических скачков.

Эффекты:
- `military_exercise`: +конфликт, -доверие.
- `arms_buildup`: рост `military_power`, +конфликт.
- `border_incident`: +резкий конфликт, -GDP обеих сторон, +tension, -trust.
- `conflict`: крупные потери капитала/GDP обеих сторон, сильные социальные шоки, запуск `at_war`.

Активная война каждый год:
- дополнительные потери капитала/GDP,
- падение торговой интенсивности пары,
- проверка истощения по порогам относительно `war_start_*`:
  - GDP < 70% старта или
  - Population < 90% старта или
  - ResourceIndex < 50% старта.

Завершение войны:
- взаимное истощение (обе стороны) или победа/поражение одной стороны.

## 7.7 Эндогенная эволюция отношений (`update_relations_endogenous`)

Базовые якоря: `trade=0.5`, `trust=0.6`, `conflict=0.1`.

Конфликт:

```text
conflict_drift = 0.02*(0.1 - conflict)
conflict_push =
  0.04*trade_short
  + 0.05*avg_tension
  + 0.06*mil_gap
  + 0.04*trade_barrier
  + 0.03*sanction_flag
  + propagation_from_trade_network
  + block_rivalry
  - mediation_by_security_orgs
```

Доверие:

```text
trust_drift = 0.02*(0.6 - trust)
trust_push =
  0.04*trade_gap
  - 0.05*conflict
  - 0.04*avg_tension
  - 0.05*trade_barrier
  - 0.03*sanction_flag
  + 0.5*mediation
```

## 7.8 Коалиции (`update_coalitions`)

Страна может сменить `alliance_block`, если:
- прошел cooldown (`3` года по умолчанию),
- лучший блок дает прирост `score` более `0.08`.

`score` учитывает:
- доверие/конфликт с членами блока,
- эффективную торговлю,
- `coalition_openness`.

## 7.9 Внутренняя политика (`apply_action`)

Перед применением рычагов действует второй уровень фискального guardrail:
- положительное суммарное расширение (`social + military + rd`) ограничивается:
  - `3% GDP` обычно,
  - `2% GDP`, если `debt/GDP > 1.2`.

Каналы влияния:

1. `tax_fuel_change`:
- прямой удар по GDP,
- изменение trust/tension через культурную чувствительность (`UAI`, `PDI`, `IDV`, тип режима, безработица, неравенство).

2. `social_spending_change`:
- меняет `social_spending`, `gov_spending`, `public_debt`,
- повышает trust и снижает tension.

3. `military_spending_change`:
- меняет `military_spending`, `gov_spending`, `public_debt`,
- увеличивает `military_power` (с учетом tech),
- может повышать или снижать trust в зависимости от perceived threat (`security_index`) и культуры (`MAS`, self-expression, regime_type).

4. `rd_investment_change`:
- увеличивает `rd_spending`, `gov_spending`, `public_debt`,
- повышает `tech_level`,
- повышает ресурсную эффективность (`resource.efficiency *= exp(0.02*rd_delta)`).

5. `climate_policy` (`none|weak|moderate|strong`):
- снижает GDP на издержки перехода,
- задает `policy_reduction` выбросов (`0.05|0.15|0.30`),
- меняет trust/tension в зависимости от `climate_risk`, self-expression и типа режима.

После этого пересчитываются выбросы через `update_emissions_from_economy`.

## 7.10 Торговля (`apply_trade_deals`)

Для каждой сделки:
- проверка партнера/ресурса/положительного объема,
- цена = глобальная цена * модификатор `cheap|fair|premium = 0.9|1.0|1.1`,
- ограничение объема по:
  - экспортной мощности (`production - consumption + 0.2*reserve`),
  - FX-лимиту импортера (`fx_reserves + 0.05*GDP trade credit`),
  - торговым барьерам (берется максимум барьера в обе стороны).

Финансовый и торговый учет:
- обновляются `fx_reserves` и `net_exports` обеих сторон,
- накапливается `trade_realized`.

Побочные эффекты импорта:
- `metals` -> рост капитала импортера (`+0.001*value`),
- `food` -> снижение tension и рост trust.

Связность:
- двусторонняя `trade_intensity` растет на `min(0.05, 0.002*volume_real)`.

Глобальный баланс:

```text
sum_i net_exports_i = 0
```

Остаток (численная погрешность) перераспределяется пропорционально абсолютным `net_exports` (или GDP, если нулевые веса).

## 7.11 Ресурсы и цены (`resources.py`)

Энергия:
- глобальные запасы и annual cap распределяются пропорционально энергетическим резервам стран.

Запасы ресурсов:
- для `energy` производство ограничено глобальной квотой и локальным резервом,
- для `metals` работает:
  - замещение спроса по цене: `consumption *= (price/ref)^(-elasticity)`,
  - переработка: `production += recycling_rate * consumption`,
- для `food` запас не вычитается на производство (плюс регенерация и tech-expansion),
- для `energy/metals` запас уменьшается на первичную добычу.

Мировые запасы `global_reserves` обновляются через суммарную первичную добычу и регенерацию.

Глобальные цены:

```text
imbalance = (demand - supply) / (supply + eps)
price_next = clamp(price * (1 + alpha*imbalance), min_price, max_price)
```

## 7.12 Климат (`climate.py`)

### Выбросы по стране

```text
intensity =
  base_intensity
  * exp(-0.12 * max(0, tech_level-1))
  * (1 / efficiency)
  * exp(-0.049 * time)
  * tax_effect

tax_effect = clamp(1 - 0.12*fuel_tax_change, 0.6, 1.4)
emissions = GDP * intensity * (1 - policy_reduction) * 1.8
```

### Глобальный углеродный цикл (4 пула)

```text
pool_i(t+1) = pool_i(t) * exp(-dt/tau_i) + frac_i * total_emissions
CO2 = CO2_preindustrial + sum(pool_i)
```

### Форсинг и температура (2-box EBM)

```text
F_CO2 = 5.35 * ln(Cppm/C0ppm)
F_total = F_CO2 + F_nonCO2
lambda = F2x / ECS

T_surface(t+1) = T_surface + dt/Cs * (F_total - lambda*T_surface - k*(T_surface - T_ocean))
T_ocean(t+1)   = T_ocean   + dt/Cd * (k*(T_surface - T_ocean))
```

### Биоразнообразие
- глобальное: взвешенное среднее локального (`weight = population^0.3`),
- локальное: деградация от потепления и климатического риска, ослабляемая resilience.

### Климатический риск

```text
base = clamp01(0.3 + 0.45*water_stress + 0.15*gini_norm)
temp_component = 1 - exp(-0.45 * max(0, deltaT))
target = clamp01(base + (1-base)*temp_component)
risk_next = risk + 0.06*(target - risk)
```

### Экстремальные события
- вероятность растет с риском и температурой, снижается resilience,
- при событии:
  - потери капитала и населения,
  - рост social_tension,
  - изменение trust по режимной устойчивости,
  - запускается 2-летний persistent GDP shock (`climate_shock_penalty`).

## 7.13 Экономика и госфинансы (`economy.py`, `metrics.py`)

### TFP (эндогенно)

Инициализация `tfp` из наблюдаемого состояния (один раз), далее:

```text
rd_share = rd_spending / GDP
avg_trade = average(effective_trade_intensity with partners)
spillover = 1 + 0.3*avg_trade

diffusion = 0.02 * weighted_avg_positive_tech_gap
tfp_growth = clamp(0.01 + 2.0*rd_share*spillover + diffusion, -0.05, 0.05)
tfp *= (1 + tfp_growth)
```

### Выпуск (Cobb-Douglas + частичная адаптация)

```text
GDP_potential = tfp * tech_factor * K^0.30 * L^0.60 * E^0.10
tech_factor = 1 + 0.6*max(0, tech_level-1)
L = population / 1e9
E = (energy_consumption/1000) * energy_efficiency
```

`_scale_factor` фиксирует начальное соответствие модели к наблюдаемому GDP.

```text
GDP_target = GDP_potential * scale_factor * effective_damage_multiplier
if climate_shock_years > 0: GDP_target *= (1 - climate_shock_penalty)

gap = (GDP_target - GDP_now)/GDP_now
adjust_speed = 0.30 + 0.35*clamp01(max(0,gap))
GDP_next = (1-adjust_speed)*GDP_now + adjust_speed*GDP_target
```

### Капитал

```text
savings_rate = clamp(0.24*(0.7 + 0.6*regime_stability - 0.4*social_tension), 0.05, 0.40)
K_next = (1-0.05)*K + savings_rate*GDP
```

### Ставка долга

```text
debt_gdp = debt / GDP
excess = max(0, debt_gdp - 0.6)
spread_raw = 0.03*excess + 0.10*excess^2
fragility = 1 - regime_stability
spread = spread_raw * (0.5+0.5*debt_crisis_prone) * (0.7+0.6*fragility)
```

Плюс contagion из торгово-взвешенного стресса партнеров (кап `0.05`).
Итоговая ставка ограничена диапазоном `[0, 0.35]`.

### Госфинансы

```text
climate_adaptation_share = 0.005 + 0.015*climate_risk
baseline_spending = GDP * (0.15 + 0.035 + climate_adaptation_share)
policy_spending = social_spending + military_spending + rd_spending
gov_spending = baseline_spending + policy_spending
taxes = 0.22 * GDP
interest_payments = rate * public_debt
total_deficit = (gov_spending - taxes) + interest_payments
```

- если `total_deficit > 0`: новый долг ограничен `5% GDP`,
- если `total_deficit <= 0`: долг гасится.
- `rd_spending` затухает ежегодно: `* 0.85`.

## 7.14 Социальный блок и демография (`social.py`)

### Население

Параметры рождаемости/смертности зависят от:
- `gdp_per_capita`,
- food availability/scarcity,
- `inequality_gini`,
- относительного процветания к `baseline_gdp_pc`.

### Миграция
- исходящий поток формируется из `income_gap` и `conflict_proneness`,
- распределение по направлениям через торговую связность и разницу доходов,
- глобально сохраняется баланс населения между странами.

### Доверие/напряженность/неравенство

```text
trust_change = gdp_pc_effect - unemployment_effect - inflation_effect
             - 0.0004*gini - 0.08*max(0,tension-0.3)

tension_change = inequality_effect + stress_effect + 0.06*(0.5 - trust)
```

Неравенство:

```text
gini_next = gini
  + 6.0*gdp_growth
  + 4.0*abs(min(0,gdp_growth))*(0.5+tension)
  - 60.0*social_spending_change
  + 1.2*(tension-0.4)
```

Пороговые события:
- коллапс режима при `trust<0.2` и `tension>0.8`,
- долговой кризис при `debt/GDP>1.2` и `interest_rate>0.12`.

## 7.15 Институты (`institutions.py`)

Набор организаций: `UN, UNSC, IMF, WorldBank, FSB, WTO, EU, USMCA, ASEAN, UNFCCC, GCF, IPCC, NATO, WHO, ILO, UNEP_UNESCO`.

Типы: `SecurityOrg|FinanceOrg|TradeOrg|ClimateOrg|KnowledgeOrg|SocialOrg`.

Каждый шаг:
1. Считаются глобальные метрики (GDP, trust, tension, trade/conflict, CO2, temp).
2. Обновляется легитимность организации (частичная адаптация к `target_legitimacy`).
3. Обновляется бюджет:

```text
budget = base_budget_share * total_gdp * legitimacy
```

4. Применяются меры:
- `TradeOrg`: снижение внутренних барьеров.
- `FinanceOrg`: liquidity support странам со стрессом долга/FX.
- `SecurityOrg`: медиация и снижение конфликтности.
- `ClimateOrg`: небольшое снижение `climate_risk`.
- `SocialOrg`: снижение tension и рост trust.
- `KnowledgeOrg`: сигнал (без прямого численного воздействия).

Результаты пишутся в `world.institution_reports` и попадают в наблюдение/логи.

## 7.16 Память (`memory.py`)

На каждом шаге сохраняется snapshot по стране:
- GDP, GDP per capita, trust, tension, security_margin, climate risk, emissions,
- summary последнего внутреннего действия.

`summarize_agent_memory` возвращает тренды и последние действия; используется LLM-политикой и кредитным модулем.

## 8. Метрики (полный реестр)

## 8.1 Сравнительные метрики (`compute_relative_metrics`)

Для каждой страны:
- `economy.gdp_share = gdp / sum_gdp`,
- `economy.gdp_rank` (ранг по GDP),
- `influence_score = ln(1+gdp) + ln(1+pop/1e6) + 0.5*ln(1+trade_degree)`,
- `security_margin = own_military_power / avg_neighbor_military`.

## 8.2 Риск-метрики

- `reserve_years[resource] = own_reserve / production`,
- `debt_stress = min(max(debt_gdp-1,0) * debt_crisis_prone, 3)`,
- `protest_risk = f(tension, trust, gini, regime_fragility)` в `[0,1]`.

Эти метрики используются в:
- политической динамике,
- наблюдении policy-движка,
- кредитном скоринге.

## 8.3 Политические метрики

`legitimacy`, `protest_pressure`, `hawkishness`, `protectionism`,
`coalition_openness`, `sanction_propensity`, `policy_space`.

## 8.4 Кредитный рейтинг (next-year) (`credit_rating.py`)

Шкала:
- `rating in [1..26]`, где `26` хуже,
- `zone = green (<=12) | yellow (13..20) | red (>=21)`.

Интегральный риск:

```text
total_risk_score =
  0.25*financial_risk
  + 0.20*war_risk
  + 0.22*social_risk
  + 0.13*sanctions_risk
  + 0.20*macro_risk
```

Маппинг:

```text
rating = round(1 + total_risk_score * 25), затем clamp в [1,26]
```

Подкомпоненты, сохраняемые в `credit_rating_details`:
- `financial_risk`
- `war_risk`
- `social_risk`
- `sanctions_risk`
- `macro_risk`
- `total_risk_score`
- `debt_gdp`
- `interest_rate`
- `debt_crisis_now`
- `at_war_now`
- `war_links`
- `high_conflict_links`
- `protest_risk`
- `next_year_revolution_risk`
- `structural_social_risk`
- `management_strength`
- `sanction_now`
- `sanction_next`
- `inbound_sanctions_mild`
- `inbound_sanctions_strong`
- `macro_reserve_risk`
- `gdp_trend_ratio`

## 8.5 Метрики в наблюдении (`build_observation`)

`self_state["competitive"]` включает:
- `gdp_share`, `gdp_rank`, `influence_score`, `security_margin`,
- `reserve_years`,
- `debt_stress`,
- `protest_risk`.

`external_actors` включает:
- соседей с `trade_intensity`, `trade_barrier`, `trust`, `conflict_level`, `gdp`, `military_power`, `alliance_block`,
- глобальный срез состояния,
- сводку институтов и их отчеты.

## 9. Метрики в логах (CSV)

## 9.1 Мир (`*_t0-tN.csv`)

Колонки:
- `time`, `agent_id`,
- экономика: `gdp`, `capital`, `population`, `public_debt`, `fx_reserves`, `net_exports`,
- ресурсы: `energy_*`, `food_*`, `metals_*`,
- общество/климат: `trust_gov`, `social_tension`, `inequality_gini`, `climate_risk`, `co2_annual_emissions`, `biodiversity_local`,
- глобальные: `global_co2`, `global_temperature`, `global_biodiversity`,
- демография: `birth_rate`, `death_rate`,
- кредит: `credit_rating`, `credit_zone`, `credit_risk_score`,
- компоненты кредита: `credit_financial_risk`, `credit_war_risk`, `credit_social_risk`, `credit_sanctions_risk`, `credit_macro_risk`, `credit_next_year_revolution_risk`, `credit_sanction_risk_next`, `credit_inbound_sanctions_mild`, `credit_inbound_sanctions_strong`.

## 9.2 Действия (`*_actions.csv`)

Ключевые колонки:
- идентификация и базовое состояние: `time`, `agent_id`, `agent_name`, `alliance_block`, `gdp`, `trust_gov`, `social_tension`, `inequality_gini`,
- политические метрики: `political_*`,
- внутренние рычаги: `dom_*`,
- внешние intents/realized: `trade_deals`, `trade_realized`, `sanctions_intent`, `trade_restrictions_intent`, `security_intent_*`, `security_applied_*`,
- `active_sanctions`,
- средние отношения: `avg_trade_barrier`, `avg_trade_intensity`, `avg_relation_trust`, `avg_relation_conflict`,
- `explanation`.

В текущей реализации в дополнительные поля также попадают
`credit_rating_pre_step`, `credit_zone_pre_step`, `credit_risk_score_pre_step`.
Любые другие дополнительные ключи автоматически добавляются в конец схемы.

## 9.3 Институты (`*_institutions.csv`)

Колонки:
- `time`, `org_id`, `org_type`, `legitimacy`, `budget`, `members`, `measures`,
- глобальные метрики шага: `global_gdp`, `global_trust`, `global_tension`, `global_rel_trust`, `global_rel_conflict`, `global_trade_intensity`, `global_co2`, `global_temp`.

## 10. Управляющие параметры v12 (основные)

Через CLI и `run_10y_llm.sh`:
- `STATE_CSV`
- `MAX_COUNTRIES`
- `SIM_YEARS`
- `SIM_SEED`
- `POLICY_MODE`
- `USE_SIMPLE_POLICIES`, `NO_LLM`
- `DEEPSEEK_API_KEY`
- `LLM_MAX_CONCURRENCY`, `LLM_BATCH_SIZE`
- `LLM_TIMEOUT_SEC`, `LLM_MAX_RETRIES`, `LLM_RETRY_BACKOFF_SEC`
- `DISABLE_EXTREME_EVENTS`
- `SAVE_CSV_LOGS`
- `GENERATE_CREDIT_MAP`

## 11. Ключевые свойства модели

- Модель мультиагентная, направленная по отношениям и эндогенная почти во всех каналах.
- Взаимодействия многократно замыкаются в циклы:
  - политика -> геополитика -> торговля -> экономика -> социальная динамика -> политика,
  - экономика/ресурсы -> выбросы/климат -> ущерб/риски -> экономика,
  - институты смягчают/усиливают часть контуров.
- Кредитный рейтинг вычисляется как интегральный индикатор next-year риска и зависит от всех крупных подсистем.

---

Этот файл отражает текущую реализацию `GIM_12` на базе `legacy/GIM_11_1`. При изменении формул/констант в коде документ должен обновляться синхронно.
