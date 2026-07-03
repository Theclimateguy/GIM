import Foundation
import AppKit

// A message in an Assistant session. Only plain, always-Codable fields are stored
// (role/text/toolName/toolSummary + the raw JSON of any tool result) — this is what
// actually gets persisted to disk and replayed into subsequent-turn history, so none of
// the ~15 engine result models need to become Encodable just to support sessions.
// `result` re-decodes AnswerResult lazily from the stored JSON for the rich Situation
// Room card (the only tool with a dedicated chat renderer today).
struct ChatMessage: Identifiable, Codable {
    enum Role: String, Codable { case user, tool, assistant }
    var id: UUID = UUID()
    let role: Role
    var text: String
    var toolName: String? = nil
    var toolSummary: String? = nil
    var resultJSON: String? = nil
    /// Base64 PNG snapshot of the tool's chart (ChartSnapshot) — a flat image, not a live
    /// chart, so a long session doesn't carry dozens of interactive Chart views.
    var chartImageBase64: String? = nil

    init(role: Role, text: String, toolName: String? = nil, toolSummary: String? = nil,
         resultJSON: String? = nil, chartImageBase64: String? = nil) {
        self.role = role; self.text = text
        self.toolName = toolName; self.toolSummary = toolSummary
        self.resultJSON = resultJSON; self.chartImageBase64 = chartImageBase64
    }

    var result: AnswerResult? {
        guard let resultJSON, let data = resultJSON.data(using: .utf8) else { return nil }
        return try? EngineClient.decoder.decode(AnswerResult.self, from: data)
    }

    var chartImage: NSImage? {
        guard let chartImageBase64, let data = Data(base64Encoded: chartImageBase64) else { return nil }
        return NSImage(data: data)
    }
}

// One entry in the agent trace: what the backend actually sent/decided at a given point
// (full system prompt, forced-route decisions, raw per-step model output, tool results) —
// not what the app rendered. Answers "did the model even see the hint" by inspection
// instead of re-guessing from the chat transcript alone.
struct TraceEntry: Identifiable, Codable {
    var id: UUID = UUID()
    let kind: String        // system_prompt | forced_route | model_step | tool_result | model_reply
    let text: String
    var timestamp: Date = Date()
}

// One Assistant conversation. Explicit, on-disk, navigable — see SessionStore.
struct ChatSession: Identifiable, Codable {
    static let titleFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "dd.MM HH:mm"
        return f
    }()

    let id: UUID
    var title: String
    let createdAt: Date
    var messages: [ChatMessage]
    var trace: [TraceEntry] = []

    init(id: UUID = UUID(), title: String? = nil, createdAt: Date = Date(), messages: [ChatMessage] = [],
         trace: [TraceEntry] = []) {
        self.id = id; self.createdAt = createdAt; self.messages = messages; self.trace = trace
        self.title = title ?? Self.titleFormatter.string(from: createdAt)
    }
}

struct AssistantMsg: Encodable {
    let role: String
    let content: String
}

struct AssistantRequest: Encodable {
    let provider: String
    let model: String
    let apiKey: String
    let baseURL: String
    let messages: [AssistantMsg]
    // The session's already-established scenario (if any) — handed to the backend
    // structurally each turn so the model doesn't have to re-infer it from its own past
    // prose (see gim2.assistant._active_scenario_block).
    var activeLevers: [String: Double]? = nil
    var activeActors: [String]? = nil
}

// Connection-test (the settings "Проверить" button): the same LLM config, no messages.
struct LLMTestRequest: Encodable {
    let provider: String
    let model: String
    let apiKey: String
    let baseURL: String
}

struct LLMTestResult: Decodable {
    let ok: Bool
    let error: String?
    let model: String?
    let status: Int?
    let latencyMs: Int?
    let note: String?
}
