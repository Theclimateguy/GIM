import Foundation

struct ChatMessage: Identifiable {
    enum Role { case user, tool, assistant }
    let id = UUID()
    let role: Role
    var text: String
    var result: AnswerResult? = nil
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
}
