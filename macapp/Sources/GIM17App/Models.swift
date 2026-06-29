import Foundation

// Wire models for the engine bridge (docs/mac_app/ENGINE_BRIDGE_CONTRACT.md).
// Decoding uses convertFromSnakeCase; encoding uses convertToSnakeCase, so Swift
// properties stay camelCase. Most fields are optional to tolerate contract drift.

enum EngineError: Error, CustomStringConvertible {
    case badHandshake(String)
    case http(Int, String)
    case noClient
    case decode(String)

    var description: String {
        switch self {
        case .badHandshake(let s): return "engine handshake failed: \(s)"
        case .http(let code, let body): return "HTTP \(code): \(body)"
        case .noClient: return "engine client not ready"
        case .decode(let s): return "decode error: \(s)"
        }
    }
}

struct EngineReady: Decodable {
    let ready: Bool?
    let schema: String?
    let port: Int?
    let token: String?
    let pid: Int?
    let gimVersion: String?
    let offline: Bool?
}

// --- requests ---------------------------------------------------------------

struct WorldLoadRequest: Encodable {
    var stateCsv: String?
    var stateYear: Int?
    var maxCountries: Int?
}

struct WhatIfRequest: Encodable {
    var worldKey: String
    var question: String
    var actors: [String]?
    var template: String?
    var horizon: Int
    var backgroundPolicy: String = "compiled-llm"
    var llmRefresh: String = "trigger"
    var seed: Int? = 2026
}

struct PlayRequest: Encodable {
    var worldKey: String
    var country: String
    var persona: String
    var goal: String
    var mode: String = "WHAT_IF"
    var roundYears: Int = 4
    var ensembleSize: Int = 3
    var seed: Int? = 2026
}

struct GameRequest: Encodable {
    var worldKey: String
    var casePath: String?
    var description: String?
    var horizon: Int = 3
    var equilibrium: Bool = true
    var maxCombinations: Int = 256
    var seed: Int? = 2026

    enum CodingKeys: String, CodingKey {
        case worldKey, description, horizon, equilibrium, maxCombinations, seed
        case casePath = "case"
    }
}

// --- responses --------------------------------------------------------------

struct ActorOption: Decodable, Identifiable, Hashable {
    let id: String
    let name: String
    let label: String?
}

struct Bilingual: Decodable, Hashable {
    let ru: String?
    let en: String?
    var current: String { ru ?? en ?? "" }   // RU primary per design
}

struct Persona: Decodable, Identifiable, Hashable {
    let id: String
    let name: Bilingual
    let tagline: Bilingual?
    let declaration: Bilingual?
    let nudges: [String: Double]?
}

struct WorldLoadResponse: Decodable {
    let worldKey: String
    let stateYear: Int?
    let actors: [ActorOption]?
    let personas: [Persona]?
    let schema: String?
}

struct Outcome: Decodable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let value: Double
    let valence: String?
}

struct Driver: Decodable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let value: Double
}

struct GDPSeries: Decodable, Identifiable, Hashable {
    var id: String { idField }
    let idField: String
    let name: String
    let baseline: [Double]
    let policy: [Double]

    enum CodingKeys: String, CodingKey {
        case idField = "id"
        case name, baseline, policy
    }
}

struct Prices: Decodable, Hashable {
    let energy: [Double]?
    let food: [Double]?
    let metals: [Double]?
}

struct SeriesBundle: Decodable, Hashable {
    let gdp: [GDPSeries]?
    let socialTension: [GDPSeries]?
    let prices: Prices?
}

struct IntentFeedItem: Decodable, Identifiable, Hashable {
    var id: String { (agentId ?? "") + (posture ?? "") }
    let agentId: String?
    let agentName: String?
    let posture: String?
    let tags: [String]?
    let intensity: String?
    let actions: [String]?
}

struct Trace: Decodable, Hashable {
    let runId: String?
    let equivCli: String?
    let seed: Int?
    let artifactsDir: String?
    let elapsedMs: Int?
}

struct DimensionMetric: Decodable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let value: Double
}

struct DimensionGroup: Decodable, Identifiable, Hashable {
    var id: String { group }
    let group: String
    let metrics: [DimensionMetric]
}

struct RunResult: Decodable {
    let mode: String?
    let schema: String?
    let verdict: String?
    let criticality: Double?
    let outcomes: [Outcome]?
    let dimensions: [DimensionGroup]?
    let drivers: [Driver]?
    let years: [Int]?
    let series: SeriesBundle?
    let intentsFeed: [IntentFeedItem]?
    let trace: Trace?
}

struct ProgressEvent: Decodable {
    let runId: String?
    let percent: Int?
    let stepIndex: Int?
    let stepTotal: Int?
    let message: String?
}

struct DoctrineDim: Decodable, Identifiable, Hashable {
    var id: String { name }
    let name: String
    let base: Double
    let shift: Double
}

struct SSEError: Decodable {
    let code: String?
    let message: String?
}

struct DoctrineRow: Identifiable {
    let id = UUID()
    let key: String
    let label: String
    let base: Double
    let shift: Double
    let delta: Double
}

struct RunRecord: Identifiable {
    let id = UUID()
    let label: String
    let result: RunResult
}

struct ChatMessage: Identifiable {
    enum Role { case user, assistant, tool }
    let id = UUID()
    let role: Role
    var text: String = ""
    var toolName: String? = nil
    var result: RunResult? = nil
}

struct ChatTurn: Encodable {
    let role: String
    let content: String
}

struct AssistantRequest: Encodable {
    let worldKey: String
    let provider: String
    let model: String
    let apiKey: String
    let baseUrl: String
    let messages: [ChatTurn]
}

let doctrineDims: [(key: String, label: String)] = [
    ("escalation_bias", "Эскалация"),
    ("trade_openness", "Открытость торговли"),
    ("sanctions_tolerance", "Толерантность к санкциям"),
    ("mediation_openness", "Посредничество"),
    ("military_readiness", "Военная готовность"),
    ("domestic_priority", "Внутренний приоритет"),
    ("reserve_protection", "Защита резервов"),
    ("finance_defensiveness", "Фин. оборонительность"),
    ("climate_pragmatism", "Климат-прагматизм"),
]
