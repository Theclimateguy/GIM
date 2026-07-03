import Foundation

// Explicit on-disk persistence for Assistant chat sessions: each session (chat history +
// the tool calls/results made within it) is one JSON file, so sessions survive an app
// restart and can be browsed/deleted independently. Kept deliberately simple (one file per
// session, no database) — session counts are small (human conversations, not telemetry).
enum SessionStore {
    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()
    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        e.outputFormatting = [.sortedKeys]
        return e
    }()

    private static var directory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        let dir = base.appendingPathComponent("GIM18/sessions", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private static func fileURL(for id: UUID) -> URL {
        directory.appendingPathComponent("\(id.uuidString).json")
    }

    static func loadAll() -> [ChatSession] {
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: nil) else { return [] }
        let sessions = files.filter { $0.pathExtension == "json" }.compactMap { url -> ChatSession? in
            guard let data = try? Data(contentsOf: url) else { return nil }
            return try? decoder.decode(ChatSession.self, from: data)
        }
        return sessions.sorted { $0.createdAt > $1.createdAt }
    }

    static func save(_ session: ChatSession) {
        guard let data = try? encoder.encode(session) else { return }
        try? data.write(to: fileURL(for: session.id), options: .atomic)
    }

    static func delete(_ id: UUID) {
        try? FileManager.default.removeItem(at: fileURL(for: id))
    }
}
