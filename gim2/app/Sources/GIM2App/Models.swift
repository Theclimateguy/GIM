import Foundation

// Codable models for the v2 engine projections (gim-engine/2). Keys arrive
// snake_case; EngineClient decodes with .convertFromSnakeCase, so properties are
// camelCase. See gim2/docs/ENGINE_BRIDGE_CONTRACT_v2.md.

// MARK: fans

struct FanSeries: Decodable, Identifiable {
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

struct EnsembleProjection: Decodable {
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

struct DeltaMetric: Decodable, Identifiable {
    let metric: String
    let delta: FanSeries
    let baselineP50: [Double]
    let scenarioP50: [Double]
    var id: String { metric }
}

struct DeltaProjection: Decodable {
    let kind: String
    let nMembers: Int
    let years: [Int]
    let metrics: [DeltaMetric]
}

struct ScenarioResult: Decodable {
    let schema: String
    let mode: String
    let projection: DeltaProjection
    let baseline: EnsembleProjection
    let scenario: EnsembleProjection
    let brief: String
    let equivCli: String?
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
    var years: Int
    var maxAgents: Int
}

struct WeakResult: Decodable {
    struct Maha: Decodable {
        let anomaly: [Bool]?
        let distanceSq: [Double]?
        let nAnomalies: Int?
        let threshold: Double?
    }
    struct Signals: Decodable {
        let mahalanobis: Maha?
        let dimensions: [String]?
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
}

// MARK: UI helpers

enum MetricLabel {
    static let ru: [String: String] = [
        "world_gdp": "ВВП (трлн$)",
        "temperature": "Температура (°C)",
        "co2": "CO₂ (Гт)",
        "mean_social_tension": "Соц. напряжённость",
        "n_debt_crises": "Долговые кризисы",
        "n_wars": "Войны",
        "conflict_risk": "Риск конфликта",
    ]
    static func of(_ key: String) -> String { ru[key] ?? key }
}

// A comparable run summary for the Compare screen: terminal Δ (scenario − base)
// per metric. Both /run/scenario and the assistant's /run/answer reduce to this.
struct ScenarioRecord: Identifiable {
    let id = UUID()
    let label: String
    let kind: String                 // "scenario" | "answer"
    let metrics: [(key: String, delta: Double)]
    let cli: String?

    init(label: String, kind: String, metrics: [(key: String, delta: Double)], cli: String?) {
        self.label = label; self.kind = kind; self.metrics = metrics; self.cli = cli
    }

    init(scenario r: ScenarioResult, label: String) {
        self.init(label: label, kind: "scenario",
                  metrics: r.projection.metrics.map { ($0.metric, $0.delta.p50.last ?? 0) },
                  cli: r.equivCli)
    }

    init(answer r: AnswerResult, label: String) {
        self.init(label: label, kind: "answer",
                  metrics: r.cards.map { ($0.metric, $0.deltaP50) },
                  cli: r.equivCli)
    }

    func delta(of key: String) -> Double? { metrics.first { $0.key == key }?.delta }
}
