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
    ]
    static func of(_ key: String) -> String { ru[key] ?? key }
}
