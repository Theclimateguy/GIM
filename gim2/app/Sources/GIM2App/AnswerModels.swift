import Foundation

// Codable models for POST /run/answer (the «Аналитический ассистент» card).
// Keys arrive snake_case; EngineClient decodes with .convertFromSnakeCase.

struct AnswerCard: Decodable, Identifiable {
    let metric: String
    let label: String
    let deltaP50: Double
    let p5: Double
    let p95: Double
    let lead: Bool
    var id: String { metric }
}

struct AnswerThreshold: Decodable {
    let lever: String
    let metric: String
    let note: String
    let crossingMagnitude: Double?
}

struct CascadeNode: Decodable, Identifiable {
    let id: String
    let label: String
    let shown: String
    let direction: String
    let focusScope: String
}

struct CascadeBlock: Decodable {
    let nodes: [CascadeNode]
    let affected: [String]
    let selectionActors: [String]
}

struct ActorEntry: Decodable, Identifiable {
    let id: String
    let name: String
    let region: String
    let verdict: String
    let score: Double
}

// Encodable too: re-encoded (snake_case) to inject into the Leaflet map.
struct GeoCountry: Codable {
    let id: String
    let name: String
    let geoName: String
    let score: Double
    let gdpPct: Double
    let tension: Double
    let debtPct: Double
    let crisisYears: Double
    let inflationPp: Double?
    let unemploymentPp: Double?
    let crisisAdded: Double?
}

struct Geo: Codable {
    let domains: [String]
    let countries: [GeoCountry]
}

struct ActorsBlock: Decodable {
    let leaders: [ActorEntry]
    let laggards: [ActorEntry]
    let geo: Geo
}

struct AnswerArchetype: Decodable {
    let id: String
    let nameRu: String
    let description: String
    let segments: [String]
}

struct AnswerResult: Decodable {
    let mode: String
    let verdict: String
    let headlineMetric: String
    let brief: String
    let cards: [AnswerCard]
    let threshold: AnswerThreshold?
    let cascade: CascadeBlock
    let actors: ActorsBlock
    let archetype: AnswerArchetype?
    let projection: DeltaProjection?   // delta fans over time (kind=scenario_delta)
    let equivCli: String?
    let selection: SelectionInfo?
}

// /archetypes catalog
struct ArchetypeInfo: Decodable, Identifiable {
    let id: String
    let nameRu: String
    let description: String
    let segments: [String]
    let headlineMetric: String
}

struct ArchetypeCatalog: Decodable {
    let archetypes: [ArchetypeInfo]
}

struct AnswerRequest: Encodable {
    var archetype: String?
    var members: Int
    var years: Int
    var maxAgents: Int
    var thresholdMembers: Int
    var cascadeMembers: Int
}
