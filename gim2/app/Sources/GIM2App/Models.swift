import Foundation

// Codable models for the v2 engine projections (gim-engine/2). Keys arrive
// snake_case; EngineClient decodes with .convertFromSnakeCase, so properties are
// camelCase. See gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md.

// MARK: fans

struct FanSeries: Codable, Identifiable {
    let metric: String
    let years: [Int]
    let p5: [Double]
    let p25: [Double]
    let p50: [Double]
    let p75: [Double]
    let p95: [Double]
    let mean: [Double]
    var id: String { metric }
}

struct EnsembleProjection: Codable {
    let kind: String
    let nMembers: Int
    let years: [Int]
    let metrics: [FanSeries]
}

struct EnsembleResult: Decodable {
    let schema: String
    let mode: String
    let projection: EnsembleProjection
    let equivCli: String?
}

// MARK: scenario delta

struct DeltaMetric: Codable, Identifiable {
    let metric: String
    let delta: FanSeries
    let baselineP50: [Double]
    let scenarioP50: [Double]
    var id: String { metric }
}

struct DeltaProjection: Codable {
    let kind: String
    let nMembers: Int
    let years: [Int]
    let metrics: [DeltaMetric]
}

// The exact lever recipe behind a run (compute_scenario/compute_answer/compute_sensitivity/
// compute_weak all echo it back as `selection.to_dict()`): per-lever magnitude + affected actors.
// Lets the Expert-mode Sensitivity/Weak panes replay a saved run instead of only screening the
// plain baseline or a single ad-hoc lever.
struct SelectionInfo: Codable {
    let levers: [String: Double]
    let actors: [String]

    /// "id=magnitude" strings — the exact wire format compute_sensitivity/compute_weak parse
    /// (gim2.levers.make_selection), so replaying preserves each lever's own magnitude.
    var asLeverItems: [String] { levers.map { "\($0.key)=\($0.value)" } }
}

struct ScenarioResult: Codable {
    let schema: String
    let mode: String
    let projection: DeltaProjection
    let baseline: EnsembleProjection
    let scenario: EnsembleProjection
    let brief: String
    let equivCli: String?
    let selection: SelectionInfo?
}

// MARK: dose response

struct DoseProjection: Decodable {
    let kind: String
    let metric: String
    let x: [Double]
    let delta: [Double]
    let scenario: [Double]
    let baseline: Double
    let xLabel: String
    let yLabel: String
}

struct DoseResult: Decodable {
    let schema: String
    let mode: String
    let lever: String
    let projection: DoseProjection
    let equivCli: String?
}

// MARK: sensitivity (tornado)

struct TornadoParam: Decodable, Identifiable {
    let name: String
    let muStar: Double
    let mu: Double
    let sigma: Double
    var id: String { name }
}

struct TornadoProjection: Decodable {
    let kind: String
    let metric: String
    let params: [TornadoParam]
}

struct SensitivityResult: Decodable {
    let schema: String
    let mode: String
    let metric: String
    let projection: TornadoProjection
    let equivCli: String?
    let selection: SelectionInfo?
}

// MARK: meta (model trust)

struct SccResult: Decodable {
    let schema: String
    let mode: String
    let centralUsdPerTco2: [String: Double]
}

struct BacktestResult: Decodable {
    let schema: String
    let mode: String
    let startYear: Int
    let endYear: Int
    let gdpRmseTrillions: Double
    let globalCo2RmseGtco2: Double
    let temperatureRmseC: Double
    let temperatureBiasC: Double
}

struct ConflictAUCProjection: Decodable {
    let kind: String
    let auc: Double
    let ci95: [Double]
    let pValue: Double
}

struct ConflictMetaResult: Decodable {
    let schema: String
    let mode: String
    let validated: Bool
    let reproduce: String
    let projection: ConflictAUCProjection
}

// MARK: ollama discovery (queried directly from the app, not via the engine)

struct OllamaModel: Decodable { let name: String }
struct OllamaTags: Decodable { let models: [OllamaModel] }

// MARK: weak signals

struct WeakRequest: Encodable {
    var levers: [String]
    var magnitude: Double? = nil
    var actors: [String]? = nil
    var years: Int
    var maxAgents: Int
}

struct WeakResult: Decodable {
    struct Maha: Decodable {
        let anomaly: [Bool]?
        let distanceSq: [Double]?
        let nAnomalies: Int?
        let threshold: Double?
        let dims: Int?
    }
    // Bayesian-flavoured mean-shift change-point per state dimension (gim.weak_signal.structural_break):
    // breakProb is a BIC-penalised posterior-style probability that the series' dynamics shifted level;
    // location is the most likely break step (nil if the series was too short to localise one).
    struct StructuralBreak: Decodable {
        let breakProb: Double
        let location: Int?
        let score: Double
    }
    // Critical-slowing-down trend per dimension (gim.criticality.early_warning_score): rising
    // autocorrelation + variance ahead of a regime shift. EXPERIMENTAL on the single deterministic
    // trajectory this endpoint scans — the engine's own code notes (gim/criticality.py) that without
    // the stochastic ensemble a smooth/trending scenario can itself produce a rising trend here, so
    // `warning` should be read as a hint to investigate further, not a confirmed signal.
    struct EarlyWarning: Decodable {
        let autocorrTrend: Double
        let varianceTrend: Double
        let combined: Double
        let warning: Bool
    }
    struct Signals: Decodable {
        let mahalanobis: Maha?
        let structuralBreaks: [String: StructuralBreak]?
        let earlyWarning: [String: EarlyWarning]?
        let dimensions: [String]?
        let detrended: Bool?
    }
    let schema: String
    let weakSignals: Signals
}

// MARK: ontology (lever menu)

struct LeverInfo: Decodable, Identifiable {
    let id: String
    let kind: String
    let channel: String
    let label: String
    let labelRu: String
    let rationale: String
    let defaultMagnitude: Double
    let needsActors: Bool
}

struct Ontology: Decodable {
    let levers: [LeverInfo]
    let actors: [String]?
}

struct OntologyResult: Decodable {
    let schema: String
    let ontology: Ontology
}

// MARK: request bodies (encoded with .convertToSnakeCase)

struct EnsembleRequest: Encodable {
    var members: Int
    var years: Int
    var maxAgents: Int
    var seed: Int
    var priorSet: String
}

struct ScenarioRequest: Encodable {
    var levers: [String]
    var magnitude: Double?
    var actors: [String]?
    var members: Int
    var years: Int
    var maxAgents: Int
}

struct DoseRequest: Encodable {
    var lever: String
    var grid: [Double]
    var metric: String
    var members: Int
    var years: Int
    var maxAgents: Int
}

struct SensitivityRequest: Encodable {
    var metric: String
    var years: Int
    var r: Int
    var maxAgents: Int
    var levers: [String]? = nil
    var magnitude: Double? = nil
    var actors: [String]? = nil
}

// MARK: policy game (Экспертный режим → «Ролевая игра акторов», exploratory: LLM-compiled
// per-actor doctrine instead of the scripted policy — see gim2/policy_game.py)

struct PolicyGameRequest: Encodable {
    var llmActors: [String]
    var personaByActor: [String: String]? = nil
    var levers: [String]? = nil
    var magnitude: Double? = nil
    var actors: [String]? = nil
    var years: Int
    var maxAgents: Int
    var refreshMode: String = "trigger"
    var llmProvider: String
    var llmModel: String
    var llmApiKey: String
    var llmBaseURL: String
}

struct PolicyDecision: Decodable, Identifiable {
    let time: Int
    let agentId: String
    let agentName: String
    let explanation: String
    let domesticSummary: String
    let foreignSummary: String
    var id: String { "\(agentId)-\(time)" }
}

struct PolicyGameResult: Decodable {
    let schema: String
    let mode: String
    let llmActors: [String]
    let personaByActor: [String: String]
    let selection: SelectionInfo?
    let projection: EnsembleProjection
    let decisions: [PolicyDecision]
    let brief: String
}

// MARK: UI helpers

enum MetricLabel {
    static let ru: [String: String] = [
        "world_gdp": "ВВП (трлн$)",
        "world_population": "Население",
        "temperature": "Температура (°C)",
        "co2": "CO₂ (Гт)",
        "mean_social_tension": "Соц. напряжённость",
        "n_debt_crises": "Долговые кризисы",
        "n_regime_crises": "Кризисы режима",
        "n_wars": "Войны",
        "conflict_risk": "Риск конфликта",
    ]
    static func of(_ key: String) -> String { ru[key] ?? key }
}

// Human labels for the 33 calibrated key parameters (Morris sensitivity ranking) — mirrors
// gim2/param_labels.py. Without this a chart would show "ECS_DEFAULT" instead of
// "климатическая чувствительность".
enum ParamLabel {
    static let ru: [String: String] = [
        "ECS_DEFAULT": "Климатическая чувствительность",
        "DAMAGE_QUAD_COEFF": "Квадратичный ущерб от потепления",
        "DAMAGE_BENEFIT_MAX": "Выгода от лёгкого потепления",
        "DAMAGE_BENEFIT_PEAK": "Пик выгоды от потепления",
        "DAMAGE_RISK_ADJ": "Надбавка ущерба уязвимым странам",
        "ALPHA_CAPITAL": "Доля капитала в производстве",
        "BETA_LABOR": "Доля труда в производстве",
        "GAMMA_ENERGY": "Доля энергии в производстве",
        "CAPITAL_DEPRECIATION": "Износ капитала",
        "HEAT_CAP_SURFACE": "Теплоёмкость поверхности",
        "HEAT_CAP_DEEP": "Теплоёмкость глубокого океана",
        "OCEAN_EXCHANGE": "Теплообмен с океаном",
        "DECARB_RATE_STRUCTURAL": "Темп декарбонизации",
        "EMISSIONS_SCALE": "Масштаб выбросов",
        "BASE_BIRTH_RATE": "Базовая рождаемость",
        "BASE_DEATH_RATE": "Базовая смертность",
        "BASE_INTEREST_RATE": "Базовая процентная ставка",
        "TFP_RD_SHARE_SENS": "Чувствительность роста к НИОКР",
        "ELASTICITY_MARGINAL_UTILITY": "Эластичность предельной полезности",
        "PURE_TIME_PREFERENCE": "Временное предпочтение",
        "GROWTH_DAMAGE_TFP_COEFF": "Ущерб роста от потепления",
        "LAND_USE_CO2_GTCO2_YR": "Выбросы от землепользования",
        "CARBON_FEEDBACK_CO2_GTCO2_PER_C": "Углеродная обратная связь",
        "CARBON_FEEDBACK_CH4_WM2_PER_C": "Метановая обратная связь",
        "CES_SIGMA_KE": "Замена капитала энергией",
        "MARKET_DEMAND_ELASTICITY": "Эластичность спроса на ресурсы",
        "CRISIS_SEVERITY_ALPHA": "Тяжесть хвоста кризисов",
        "MIGRATION_BASE_RATE": "Базовый темп миграции",
        "MIGRATION_MAX_SHARE": "Предел миграционного оттока",
        "MIGRATION_INCOME_PUSH_W": "Вес дохода в миграции",
        "MIGRATION_CONFLICT_PUSH_W": "Вес конфликта в миграции",
        "REGIME_COLLAPSE_GDP_MULT": "Удар по ВВП при распаде режима",
        "REGIME_COLLAPSE_CAPITAL_MULT": "Удар по капиталу при распаде режима",
    ]
    static func of(_ key: String) -> String { ru[key] ?? key }
}

// A comparable run summary for the Compare screen: terminal Δ (scenario − base)
// per metric. Both /run/scenario and the assistant's /run/answer reduce to this.
struct ScenarioRecord: Identifiable {
    let id = UUID()
    let createdAt: Date
    let label: String
    let kind: String                 // "scenario" | "answer"
    let metrics: [(key: String, delta: Double)]
    let cli: String?
    // Full result kept for per-scenario PDF export (the complete war room / delta fans).
    let answer: AnswerResult?
    let scenario: ScenarioResult?

    init(label: String, kind: String, metrics: [(key: String, delta: Double)], cli: String?,
         answer: AnswerResult? = nil, scenario: ScenarioResult? = nil, createdAt: Date = Date()) {
        self.label = label; self.kind = kind; self.metrics = metrics; self.cli = cli
        self.answer = answer; self.scenario = scenario; self.createdAt = createdAt
    }

    init(scenario r: ScenarioResult, label: String, createdAt: Date = Date()) {
        self.init(label: label, kind: "scenario",
                  metrics: r.projection.metrics.map { ($0.metric, $0.delta.p50.last ?? 0) },
                  cli: r.equivCli, scenario: r, createdAt: createdAt)
    }

    init(answer r: AnswerResult, label: String, createdAt: Date = Date()) {
        self.init(label: label, kind: "answer",
                  metrics: r.cards.map { ($0.metric, $0.deltaP50) },
                  cli: r.equivCli, answer: r, createdAt: createdAt)
    }

    func delta(of key: String) -> Double? { metrics.first { $0.key == key }?.delta }

    /// The lever recipe behind this run, regardless of whether it came from the Scenario pane
    /// or the Assistant — lets Sensitivity/Weak-signals replay a saved run as their baseline.
    var selection: SelectionInfo? { scenario?.selection ?? answer?.selection }
}
