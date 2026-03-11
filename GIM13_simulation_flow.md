# GIM_13 Simulation Flow

Ниже вынесена отдельная блок-схема того, что происходит при запуске `GIM_13` и как внутри собирается итоговая оценка сценария.

## 1. Общий контур запуска

```mermaid
flowchart TD
    A["CLI запуск<br/>python3 -m GIM_13 ..."] --> B["__main__.py<br/>parse args / dispatch mode"]
    B --> C{"Режим"}

    C -->|question| D["runtime.load_world()<br/>загрузка калиброванного WorldState"]
    D --> E["scenario_compiler.compile_question()<br/>question -> ScenarioDefinition"]
    E --> F["game_runner.evaluate_scenario()"]

    C -->|game| G["runtime.load_world()<br/>загрузка калиброванного WorldState"]
    G --> H["scenario_compiler.load_game_definition()<br/>case json -> GameDefinition"]
    H --> I["game_runner.run_game()"]

    C -->|metrics| J["runtime.load_world()<br/>загрузка калиброванного WorldState"]
    J --> K["CrisisMetricsEngine.evaluate_agents()"]
    K --> L["explanations.format_crisis_dashboard()"]
    L --> M["stdout / CLI output"]

    F --> N["ScenarioEvaluation"]
    N --> O["explanations.format_question_evaluation()"]
    O --> P["stdout / CLI output"]

    I --> Q["baseline evaluation"]
    Q --> R["enumerate action combinations"]
    R --> S["evaluate each strategy profile"]
    S --> T["rank by total payoff"]
    T --> U["GameResult"]
    U --> V["explanations.format_game_result()"]
    V --> W["stdout / CLI output"]
```

## 2. Внутренняя логика оценки сценария

```mermaid
flowchart TD
    A["ScenarioDefinition<br/>+ optional actions"] --> B["resolve scenario actors"]
    B --> C["build aggregated actor profile"]

    C --> D["raw outcome scores"]
    D --> D1["status_quo"]
    D --> D2["internal_destabilization"]
    D --> D3["proxy / maritime / direct escalation"]
    D --> D4["negotiated_deescalation"]

    C --> E["template-specific shifts"]
    E --> F["action risk shifts"]
    F --> G["tail-risk expansion"]
    G --> H["softmax"]
    H --> I["risk_probabilities"]

    B --> J["CrisisMetricsEngine"]
    J --> K["baseline crisis dashboard"]

    K --> L{"Есть policy actions?"}
    L -->|нет| M["baseline dashboard = final dashboard"]
    L -->|да| N["ACTION_CRISIS_SHIFTS"]
    N --> O["policy-adjusted crisis overlay"]
    O --> P["crisis delta vs baseline"]
    P --> Q["crisis signal summary"]

    I --> R["ScenarioEvaluation"]
    M --> R
    Q --> R

    R --> S{"Контекст"}
    S -->|question| T["top outcomes + drivers + crisis layer"]
    S -->|game| U["player payoffs + profile ranking"]
```

## 3. Детализация `game` режима

```mermaid
flowchart TD
    A["GameDefinition"] --> B["evaluate_scenario() без действий"]
    B --> C["baseline risk probabilities"]
    B --> D["baseline crisis dashboard"]

    A --> E["сгенерировать все допустимые комбинации действий игроков"]
    E --> F["strategy profile 1"]
    E --> G["strategy profile 2"]
    E --> H["strategy profile N"]

    F --> I["evaluate_scenario(actions)"]
    G --> J["evaluate_scenario(actions)"]
    H --> K["evaluate_scenario(actions)"]

    I --> L["outcome distribution"]
    J --> M["outcome distribution"]
    K --> N["outcome distribution"]

    I --> O["crisis delta vs baseline"]
    J --> P["crisis delta vs baseline"]
    K --> Q["crisis delta vs baseline"]

    O --> R["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]
    P --> S["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]
    Q --> T["score_player()<br/>objective utility + action bonus + crisis utility - penalties"]

    R --> U["profile payoff"]
    S --> V["profile payoff"]
    T --> W["profile payoff"]

    U --> X["sort all profiles"]
    V --> X
    W --> X
    X --> Y["best strategy profile"]
```

## 4. Как читать схему

- `runtime.py` только поднимает калиброванный мир и не меняет физику legacy-core.
- `scenario_compiler.py` превращает вопрос или JSON-case в формальную постановку.
- `game_runner.py` считает одновременно два слоя: outcome layer и crisis layer.
- `crisis_metrics.py` дает диагностический слой по глобальным и агентским метрикам.
- `ACTION_CRISIS_SHIFTS` меняет не мир напрямую, а crisis overlay поверх baseline dashboard.
- В `game` режиме стратегия выигрывает только если дает приемлемый outcome и не слишком ухудшает crisis metrics.
