# GIM_13 Simulation Flow

Ниже вынесена блок-схема того, что происходит при запуске `GIM_13`, как он опирается на годовой core `GIM_12`, и как внутри собирается итоговая оценка сценария. Явные технические названия в узлах сразу сопровождаются короткой расшифровкой.

## 0. Как работает годовой шаг `GIM_12`

`GIM_13` не заменяет legacy-core, поэтому сначала важно видеть реальную последовательность одного шага базовой симуляции `GIM_12`.

```mermaid
flowchart TD
    A["Старт шага GIM_12<br/>вход: калиброванный WorldState за год t"] --> B["compute_relative_metrics()<br/>пересчет сравнительных метрик стран и двусторонних отношений"]
    B --> C["update_political_states()<br/>обновление политического состояния, доверия, напряжения, санкционного контекста"]
    C --> D["update_institutions()<br/>международные институты и их корректирующие меры"]
    D --> E["Генерация действий агентов<br/>policy(obs) -> Action для каждой страны"]
    E --> F["apply_political_constraints()<br/>фильтр: что политически допустимо исполнить"]
    F --> G["resolve_foreign_policy()<br/>сведение внешнеполитических намерений в совместимый набор действий"]
    G --> H["apply_sanctions_effects() + apply_security_actions()<br/>санкции, силовые действия и их прямые эффекты"]
    H --> I["update_active_conflicts() + apply_trade_barrier_effects()<br/>эскалация конфликтов и торговые барьеры"]
    I --> J["apply_action() + apply_trade_deals()<br/>внедрение внутренних и внешних политик в состояние мира"]
    J --> K["update_relations_endogenous()<br/>эндогенное обновление отношений после действий"]
    K --> L["allocate_energy_reserves_and_caps()<br/>распределение энергии, резервов и production caps"]
    L --> M["update_resource_stocks() + update_global_resource_prices()<br/>ресурсы, дефициты и мировые цены"]
    M --> N["update_global_climate() + update_climate_risks()<br/>климатический фон и риски"]
    N --> O["apply_climate_extreme_events()<br/>экстремальные климатические события, если включены"]
    O --> P["update_economy_output()<br/>выпуск, капитал, TFP, климатические потери"]
    P --> Q["update_public_finances() + check_debt_crisis()<br/>бюджет, долг и проверка долгового кризиса"]
    Q --> R["update_migration_flows()<br/>межстрановая миграция"]
    R --> S["update_population() + update_social_state()<br/>демография, протесты, социальное напряжение"]
    S --> T["check_regime_stability()<br/>проверка устойчивости режима"]
    T --> U["compute_relative_metrics()<br/>повторный пересчет сравнительных метрик на новом состоянии"]
    U --> V["update_agent_memory() + update_credit_ratings()<br/>память агентов и кредитный риск на следующий год"]
    V --> W["world.time += 1<br/>завершение шага: t -> t + 1"]
```

### Подсказки к названиям в шаге `GIM_12`

- `WorldState`: полный снимок мира на начало шага, включая страны, отношения, ресурсы и климат.
- `Observation`: то, что агент видит перед выбором своей политики.
- `Action`: формализованный пакет решений агента на один шаг.
- `policy(obs)`: функция политики, которая получает наблюдение и возвращает действие агента.
- `Political constraints`: ограничения, которые не дают агенту исполнить политически нереалистичное действие.
- `Production caps`: годовые ограничения на добычу и поставку ресурсов.
- `TFP`: total factor productivity, то есть технологическая/организационная эффективность экономики.
- `Agent memory`: краткая память о прошлых шагах, которую используют политики и кредитный слой.
- `Credit ratings`: оценка долговой и политической уязвимости на следующий год.

## 1. Общий контур запуска `GIM_13`

```mermaid
flowchart TD
    A["CLI запуск<br/>python3 -m GIM_13 ..."] --> B["__main__.py<br/>разбор аргументов и выбор режима"]
    B --> C{"Режим"}

    C -->|question| D["runtime.load_world()<br/>загрузка калиброванного WorldState из базового мира"]
    D --> E["scenario_compiler.compile_question()<br/>вопрос -> ScenarioDefinition, то есть формальный сценарий"]
    E --> F["game_runner.evaluate_scenario()<br/>оценка исходов и crisis layer для одного сценария"]

    C -->|game| G["runtime.load_world()<br/>загрузка того же калиброванного мира"]
    G --> H["scenario_compiler.load_game_definition()<br/>case json -> GameDefinition, то есть формальная постановка игры"]
    H --> I["game_runner.run_game()<br/>baseline, стратегии, payoffs и ранжирование профилей"]

    C -->|metrics| J["runtime.load_world()<br/>загрузка мира без policy game"]
    J --> K["CrisisMetricsEngine.evaluate_agents()<br/>чистый расчет crisis dashboard по выбранным агентам"]
    K --> L["explanations.format_crisis_dashboard()<br/>человеко-читаемый вывод метрик"]
    L --> M["stdout / CLI output<br/>печать результата в консоль"]

    F --> N["ScenarioEvaluation<br/>единый объект результата: вероятности исходов, драйверы, crisis metrics"]
    N --> O["explanations.format_question_evaluation()<br/>ответ по question-режиму"]
    O --> P["stdout / CLI output<br/>печать результата в консоль"]

    I --> Q["baseline evaluation<br/>базовая оценка кейса без действий игроков"]
    Q --> R["enumerate action combinations<br/>перебор допустимых комбинаций действий"]
    R --> S["evaluate each strategy profile<br/>оценка каждого профиля стратегий"]
    S --> T["rank by total payoff<br/>сортировка профилей по суммарной полезности"]
    T --> U["GameResult<br/>итог игры: лучший профиль и top rankings"]
    U --> V["explanations.format_game_result()<br/>человеко-читаемый вывод game-режима"]
    V --> W["stdout / CLI output<br/>печать результата в консоль"]
```

## 2. Внутренняя логика оценки сценария

```mermaid
flowchart TD
    A["ScenarioDefinition + optional actions<br/>сценарий и, при наличии, действия игроков"] --> B["resolve scenario actors<br/>разрешение имен стран и выделение акторов сценария"]
    B --> C["build aggregated actor profile<br/>сбор сводного профиля напряжений, буферов и зависимостей"]

    C --> D["raw outcome scores<br/>сырые score по классам исходов"]
    D --> D1["status_quo<br/>сохранение общего статус-кво"]
    D --> D2["internal_destabilization<br/>внутренняя дестабилизация"]
    D --> D3["proxy / maritime / direct escalation<br/>эскалация через прокси, морской кризис или прямой удар"]
    D --> D4["negotiated_deescalation<br/>договорная деэскалация"]

    C --> E["template-specific shifts<br/>смещения от выбранного сценарного шаблона"]
    E --> F["action risk shifts<br/>смещения рисков от конкретных действий игроков"]
    F --> G["tail-risk expansion<br/>усиление хвостовых редких и критических исходов"]
    G --> H["softmax<br/>нормализация raw scores в вероятности"]
    H --> I["risk_probabilities<br/>вероятности outcome classes"]

    B --> J["CrisisMetricsEngine<br/>диагностический слой кризисных метрик"]
    J --> K["baseline crisis dashboard<br/>базовый снимок кризисных метрик без policy overlay"]

    K --> L{"Есть policy actions?"}
    L -->|нет| M["baseline dashboard = final dashboard<br/>метрики остаются как в базовом сценарии"]
    L -->|да| N["ACTION_CRISIS_SHIFTS<br/>таблица того, как действия двигают crisis metrics"]
    N --> O["policy-adjusted crisis overlay<br/>поверх baseline накладывается policy-driven сдвиг"]
    O --> P["crisis delta vs baseline<br/>разница метрик относительно базового состояния"]
    P --> Q["crisis signal summary<br/>сводка сдвигов по macro, stability, geopolitics и global context"]

    I --> R["ScenarioEvaluation<br/>единый результат сценарной оценки"]
    M --> R
    Q --> R

    R --> S{"Контекст использования"}
    S -->|question| T["top outcomes + drivers + crisis layer<br/>ответ на сценарный вопрос"]
    S -->|game| U["player payoffs + profile ranking<br/>оценка стратегий игроков"]
```

## 3. Детализация `game` режима

```mermaid
flowchart TD
    A["GameDefinition<br/>формальная постановка policy game"] --> B["evaluate_scenario() без действий<br/>получаем базовый baseline"]
    B --> C["baseline risk probabilities<br/>базовые вероятности исходов без стратегических ходов"]
    B --> D["baseline crisis dashboard<br/>базовый снимок crisis metrics без overlay"]

    A --> E["сгенерировать все допустимые комбинации действий игроков<br/>strategy profiles"]
    E --> F["strategy profile 1<br/>первая комбинация действий"]
    E --> G["strategy profile 2<br/>вторая комбинация действий"]
    E --> H["strategy profile N<br/>последняя допустимая комбинация"]

    F --> I["evaluate_scenario(actions)<br/>пересчет outcomes и crisis layer для профиля 1"]
    G --> J["evaluate_scenario(actions)<br/>пересчет outcomes и crisis layer для профиля 2"]
    H --> K["evaluate_scenario(actions)<br/>пересчет outcomes и crisis layer для профиля N"]

    I --> L["outcome distribution<br/>распределение вероятностей исходов"]
    J --> M["outcome distribution<br/>распределение вероятностей исходов"]
    K --> N["outcome distribution<br/>распределение вероятностей исходов"]

    I --> O["crisis delta vs baseline<br/>как профиль 1 сдвинул кризисные метрики"]
    J --> P["crisis delta vs baseline<br/>как профиль 2 сдвинул кризисные метрики"]
    K --> Q["crisis delta vs baseline<br/>как профиль N сдвинул кризисные метрики"]

    O --> R["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]
    P --> S["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]
    Q --> T["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]

    R --> U["profile payoff<br/>суммарная полезность профиля 1"]
    S --> V["profile payoff<br/>суммарная полезность профиля 2"]
    T --> W["profile payoff<br/>суммарная полезность профиля N"]

    U --> X["sort all profiles<br/>ранжирование всех профилей по payoff"]
    V --> X
    W --> X
    X --> Y["best strategy profile<br/>лучшая комбинация действий"]
```

## 4. Словарь терминов на схемах

- `ScenarioDefinition`: формализованный сценарий, собранный из вопроса, года, акторов и выбранного шаблона.
- `GameDefinition`: формализованная игровая постановка, где уже заданы игроки, их действия и цели.
- `ScenarioEvaluation`: итог оценки одного сценария, включающий вероятности исходов, драйверы и crisis layer.
- `GameResult`: итог policy game после сравнения всех допустимых профилей стратегий.
- `Baseline evaluation`: оценка кейса без действий игроков; нужна как точка сравнения.
- `Baseline crisis dashboard`: базовый crisis snapshot без наложения policy-driven shifts.
- `ACTION_CRISIS_SHIFTS`: словарь правил, который задает, какие именно crisis metrics меняет каждое действие.
- `Policy-adjusted crisis overlay`: слой сдвигов поверх baseline dashboard, не изменяющий сам legacy-world напрямую.
- `Crisis delta vs baseline`: разница между baseline dashboard и dashboard после выбранной стратегии.
- `Crisis signal summary`: агрегированная сводка по крупным осям риска, например `macro_stress_shift` и `geopolitical_stress_shift`.
- `Payoff`: суммарная полезность стратегии с учетом outcome probabilities, целей игрока и кризисных штрафов.
- `Outcome distribution`: вероятностное распределение по классам исходов, а не один жестко выбранный результат.
- `Objective utility`: полезность исхода с точки зрения явной цели игрока, например `regime_retention` или `reduce_war_risk`.
- `Action bonus`: небольшой дополнительный бонус за действие, которое содержательно соответствует цели игрока.
- `Crisis utility`: вклад crisis metrics в payoff, то есть штрафы или бонусы за изменение кризисных сигналов.
- `Penalties`: штрафы за неконсистентность, чрезмерный tail-risk или нарушение калибровочных ожиданий.

## 5. Как читать схему

- `runtime.py` только поднимает калиброванный мир и не меняет физику legacy-core.
- `GIM_12` по-прежнему делает годовой state transition, а `GIM_13` строит orchestration, diagnostics и policy gaming поверх него.
- `scenario_compiler.py` превращает вопрос или JSON-case в формальную постановку.
- `game_runner.py` считает одновременно два слоя: outcome layer и crisis layer.
- `crisis_metrics.py` дает explainable слой глобальных и агентских метрик.
- `ACTION_CRISIS_SHIFTS` меняет не сам `WorldState`, а диагностический overlay поверх baseline dashboard.
- В `game` режиме стратегия выигрывает только если дает приемлемый outcome и не слишком ухудшает crisis metrics.
