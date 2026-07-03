import Foundation

// On-disk persistence for scenario/answer runs (Compare screen "История прогонов"),
// mirroring SessionStore: one JSON file per run, so every run made in Expert mode or
// via the Assistant survives an app restart and shows up in Compare individually —
// not just the runs made in the current process (previously `history` lived only in
// memory, capped at the last 8).
enum RunHistoryStore {
    private struct MetricDTO: Codable { let key: String; let delta: Double }

    private struct RecordDTO: Codable {
        let createdAt: Date
        let label: String
        let kind: String
        let metrics: [MetricDTO]
        let cli: String?
        let answer: AnswerResult?
        let scenario: ScenarioResult?
    }

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
        let dir = base.appendingPathComponent("GIM18/runs", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private static func fileURL(for record: ScenarioRecord) -> URL {
        directory.appendingPathComponent("\(record.id.uuidString).json")
    }

    static func loadAll() -> [ScenarioRecord] {
        guard let files = try? FileManager.default.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: nil) else { return [] }
        let records = files.filter { $0.pathExtension == "json" }.compactMap { url -> ScenarioRecord? in
            guard let data = try? Data(contentsOf: url),
                  let dto = try? decoder.decode(RecordDTO.self, from: data) else { return nil }
            return ScenarioRecord(label: dto.label, kind: dto.kind,
                                   metrics: dto.metrics.map { ($0.key, $0.delta) }, cli: dto.cli,
                                   answer: dto.answer, scenario: dto.scenario, createdAt: dto.createdAt)
        }
        return records.sorted { $0.createdAt > $1.createdAt }
    }

    static func save(_ record: ScenarioRecord) {
        let dto = RecordDTO(createdAt: record.createdAt, label: record.label, kind: record.kind,
                             metrics: record.metrics.map { MetricDTO(key: $0.key, delta: $0.delta) },
                             cli: record.cli, answer: record.answer, scenario: record.scenario)
        guard let data = try? encoder.encode(dto) else { return }
        try? data.write(to: fileURL(for: record), options: .atomic)
    }
}
