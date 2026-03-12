# GIM_13 Crisis Metrics Flow

Ниже отдельная схема того, как работает `crisis metric layer`: что он берет на вход, какие прокси считает, как строит агентские и глобальные метрики и как они затем попадают в `ScenarioEvaluation`.

## 1. Общий поток crisis layer

```mermaid
flowchart TD
    A["WorldState"] --> B["Выбор scenario actors"]
    A --> C["Глобальные агрегаты мира"]
    B --> D["AgentState features"]
    B --> E["Relations / conflicts / sanctions / trust"]

    C --> F["Global metric proxies"]
    D --> G["Agent raw stress proxies"]
    E --> G

    G --> H["Archetype detection"]
    H --> I["Relevance weights"]
    G --> J["Base crisis metrics"]
    I --> K["Weighted crisis metrics"]
    J --> K

    F --> L["GlobalCrisisContext"]
    K --> M["AgentCrisisReport"]

    L --> N["CrisisDashboard"]
    M --> N

    N --> O{"Есть policy actions?"}
    O -->|нет| P["Baseline dashboard"]
    O -->|да| Q["ACTION_CRISIS_SHIFTS"]
    Q --> R["Policy-adjusted crisis overlay"]
    R --> S["crisis_delta_by_agent"]
    S --> T["crisis_signal_summary"]

    P --> U["ScenarioEvaluation"]
    T --> U
```

## 2. Глобальные метрики

```mermaid
flowchart LR
    A["World energy demand"] --> E["global_energy_volume_gap"]
    B["World energy supply"] --> E

    B --> F["global_oil_market_stress"]
    C["Import dependence"] --> F
    D["Route / chokepoint pressure"] --> F

    G["Active sanctions count"] --> H["global_sanctions_footprint"]
    I["Average trade barriers"] --> J["global_trade_fragmentation"]
    K["Falling trade intensity"] --> J

    E --> L["GlobalCrisisContext"]
    F --> L
    H --> L
    J --> L
```

## 3. Агентские метрики и связи между ними

```mermaid
flowchart TD
    A["AgentState"] --> B["Macro inputs"]
    A --> C["External balance inputs"]
    A --> D["Social / political inputs"]
    A --> E["Security / geopolitics inputs"]

    B --> F["inflation"]
    C --> G["oil_vulnerability"]
    C --> H["fx_stress"]
    H --> I["sovereign_stress"]

    B --> J["food_affordability_stress"]
    D --> K["protest_pressure"]
    K --> L["regime_fragility"]

    C --> M["sanctions_strangulation"]
    E --> N["conflict_escalation_pressure"]
    C --> O["strategic_dependency"]
    E --> P["chokepoint_exposure"]

    F --> K
    J --> K
    M --> K

    H --> M
    M --> L
    N --> L

    G --> O
    P --> O
    F --> O

    G --> Q["AgentCrisisReport"]
    H --> Q
    I --> Q
    J --> Q
    K --> Q
    L --> Q
    M --> Q
    N --> Q
    O --> Q
    P --> Q
    F --> Q
```

## 4. Приближенные формулы

Это не буквальный код, а логика сборки прокси.

```mermaid
flowchart TD
    A["inflation"] --> A1["base inflation"]
    A --> A2["+ energy pass-through"]
    A --> A3["+ food pass-through"]
    A --> A4["+ metals pass-through"]
    A --> A5["+ sanctions / barriers"]

    B["oil_vulnerability"] --> B1["energy import dependence"]
    B --> B2["+ inventory cover pressure"]
    B --> B3["+ route / chokepoint pressure"]
    B --> B4["+ export-side route exposure for exporters"]

    C["fx_stress"] --> C1["monthly import bill proxy"]
    C --> C2["+ reserve adequacy gap"]
    C --> C3["+ import compression pressure"]

    D["sovereign_stress"] --> D1["debt / GDP"]
    D --> D2["+ interest burden"]
    D --> D3["+ fiscal strain"]
    D --> D4["+ fx_stress spillover"]

    E["food_affordability_stress"] --> E1["food gap"]
    E --> E2["+ basket price pressure"]
    E --> E3["+ weak household income buffer"]
    E --> E4["+ low food cover"]

    F["protest_pressure"] --> F1["core protest risk"]
    F --> F2["+ inflation"]
    F --> F3["+ unemployment / social tension"]
    F --> F4["+ food stress"]
    F --> F5["+ trust erosion"]

    G["regime_fragility"] --> G1["baseline regime stability inverse"]
    G --> G2["+ protest_pressure"]
    G --> G3["+ trust erosion"]
    G --> G4["+ sanctions strain"]

    H["sanctions_strangulation"] --> H1["active sanctions"]
    H --> H2["+ trade barriers"]
    H --> H3["+ low trade intensity"]
    H --> H4["+ fx_stress"]

    I["conflict_escalation_pressure"] --> I1["conflict links"]
    I --> I2["+ hawkishness"]
    I --> I3["+ military posture"]
    I --> I4["+ sanctions pressure"]
    I --> I5["+ low trust"]

    J["strategic_dependency"] --> J1["energy gap"]
    J --> J2["+ food gap"]
    J --> J3["+ metals gap"]
    J --> J4["+ reserve stress"]
    J --> J5["+ thin buffers"]

    K["chokepoint_exposure"] --> K1["import dependence"]
    K --> K2["+ trade openness"]
    K --> K3["+ route risk proxy"]
    K --> K4["+ global oil stress"]
```

## 5. Archetype router

```mermaid
flowchart LR
    A["Raw agent metrics"] --> B{"Archetype detection"}

    B -->|advanced_service_democracy| C["Lower weight on food stress<br/>higher weight on FX / sanctions / macro"]
    B -->|developing_importer| D["Higher weight on inflation / food / FX"]
    B -->|hydrocarbon_exporter| E["Higher weight on oil vulnerability / sanctions / chokepoints"]
    B -->|industrial_power| F["Higher weight on strategic dependency / sanctions / escalation"]
    B -->|fragile_conflict_state| G["Higher weight on protest / regime fragility / conflict"]
    B -->|mixed_emerging| H["Balanced weights"]

    C --> I["Relevance-adjusted severity"]
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

## 6. Как crisis layer входит в policy gaming

```mermaid
flowchart TD
    A["Baseline CrisisDashboard"] --> B["ACTION_CRISIS_SHIFTS by chosen actions"]
    B --> C["Adjusted CrisisDashboard"]
    A --> D["Baseline copy"]
    C --> E["metric-by-metric delta"]
    D --> E

    E --> F["crisis_delta_by_agent"]
    F --> G["macro_stress_shift"]
    F --> H["stability_stress_shift"]
    F --> I["geopolitical_stress_shift"]
    F --> J["global_context_shift"]
    F --> K["worst_actor_shift"]

    G --> L["crisis_signal_summary"]
    H --> L
    I --> L
    J --> L
    K --> L

    L --> M["score_player()"]
    M --> N["payoff with crisis-aware penalties and utilities"]
```

## 7. Как читать этот слой

- crisis layer не подменяет `step_world`, а диагностирует и ранжирует кризисные каналы поверх baseline мира;
- одна и та же стратегия может улучшать outcome probability, но ухудшать crisis metrics и поэтому терять payoff;
- глобальные метрики задают фон, агентские метрики показывают конкретные каналы уязвимости;
- archetype router нужен для того, чтобы не сравнивать страны по одному и тому же весовому шаблону;
- текущая версия это explainable proxy-layer, который сохраняет совместимость с калибровкой `GIM_12`.
