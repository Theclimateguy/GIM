import Foundation

// Engine transport for the v2 deterministic sidecar (gim-engine/2). The client is
// reused verbatim from the v1 app (generic HTTP+SSE); the process spawns
// `python3 -m gim2 engine` instead of v1's `-m gim engine`.

enum EngineError: Error, CustomStringConvertible {
    case badHandshake(String)
    case http(Int, String)

    var description: String {
        switch self {
        case .badHandshake(let s): return "bad engine handshake: \(s)"
        case .http(let code, let body): return "engine HTTP \(code): \(body)"
        }
    }
}

struct EngineReady: Decodable {
    let ready: Bool?
    let schema: String?
    let port: Int?
    let token: String?
    let gim2Version: String?
    let engineLine: String?
    let modes: [String]?
    let exploratory: Bool?
}

struct EngineClient {
    let baseURL: URL
    let token: String

    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()
    static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    private func makeRequest(path: String, query: [URLQueryItem] = [], method: String = "GET",
                             body: Data? = nil, sse: Bool = false) -> URLRequest {
        var comps = URLComponents(url: baseURL.appendingPathComponent(path), resolvingAgainstBaseURL: false)!
        if !query.isEmpty { comps.queryItems = query }
        var req = URLRequest(url: comps.url!)
        req.httpMethod = method
        req.timeoutInterval = 120
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if sse { req.setValue("text/event-stream", forHTTPHeaderField: "Accept") }
        if let body {
            req.httpBody = body
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        return req
    }

    private static func check(_ resp: URLResponse, _ data: Data) throws {
        guard let http = resp as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            throw EngineError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }

    func get<T: Decodable>(_ path: String, query: [URLQueryItem] = [], as type: T.Type) async throws -> T {
        let (data, resp) = try await URLSession.shared.data(for: makeRequest(path: path, query: query))
        try Self.check(resp, data)
        return try Self.decoder.decode(T.self, from: data)
    }

    func post<Body: Encodable, T: Decodable>(_ path: String, _ payload: Body, as type: T.Type) async throws -> T {
        let body = try Self.encoder.encode(payload)
        let (data, resp) = try await URLSession.shared.data(for: makeRequest(path: path, method: "POST", body: body))
        try Self.check(resp, data)
        return try Self.decoder.decode(T.self, from: data)
    }

    func cancel(runId: String) async {
        let req = makeRequest(path: "/run/\(runId)/cancel", method: "POST", body: Data("{}".utf8))
        _ = try? await URLSession.shared.data(for: req)
    }

    /// Streams SSE frames as (eventName, rawDataJSON) tuples until the stream ends.
    func stream<Body: Encodable>(_ path: String, _ payload: Body) -> AsyncThrowingStream<(String, Data), Error> {
        AsyncThrowingStream { continuation in
            let task = Task.detached {
                do {
                    let body = try Self.encoder.encode(payload)
                    let req = makeRequest(path: path, method: "POST", body: body, sse: true)
                    let (bytes, resp) = try await URLSession.shared.bytes(for: req)
                    if let http = resp as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
                        throw EngineError.http(http.statusCode, "stream rejected")
                    }
                    var event = "message"
                    for try await line in bytes.lines {
                        if line.hasPrefix("event: ") {
                            event = String(line.dropFirst("event: ".count))
                        } else if line.hasPrefix("data: ") {
                            continuation.yield((event, Data(String(line.dropFirst("data: ".count)).utf8)))
                            event = "message"
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}

final class EngineProcess {
    private var process: Process?
    private(set) var port: Int = 0
    private(set) var token: String = ""

    static func bundledEngineURL() -> URL? {
        guard let res = Bundle.main.resourceURL else { return nil }
        let candidate = res.appendingPathComponent("gim-engine")
        return FileManager.default.isExecutableFile(atPath: candidate.path) ? candidate : nil
    }

    static func pythonPath() -> String {
        if let p = ProcessInfo.processInfo.environment["GIM_PYTHON"], !p.isEmpty { return p }
        let candidates = [
            "/opt/miniconda3/bin/python3", "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3", "/usr/bin/python3",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) { return c }
        return "/usr/bin/python3"
    }

    static func repoRoot() -> URL {
        if let r = ProcessInfo.processInfo.environment["GIM_REPO_ROOT"], !r.isEmpty {
            return URL(fileURLWithPath: r)
        }
        return URL(fileURLWithPath: "/Users/theclimateguy/Documents/Projects/Global_Integrated_model/GIM18")
    }

    func start() async throws -> EngineReady {
        let p = Process()
        let out = Pipe()
        p.standardOutput = out
        // Engine stderr (logs + any crash trace) → a temp log, so a dead engine is
        // diagnosable instead of silent (was /dev/null).
        let logURL = FileManager.default.temporaryDirectory.appendingPathComponent("gim2-engine.log")
        FileManager.default.createFile(atPath: logURL.path, contents: nil)
        p.standardError = (try? FileHandle(forWritingTo: logURL)) ?? FileHandle.nullDevice

        if let bundled = Self.bundledEngineURL() {
            p.executableURL = bundled
            p.arguments = []
        } else {
            p.executableURL = URL(fileURLWithPath: Self.pythonPath())
            p.arguments = ["-m", "gim2", "engine"]
            p.currentDirectoryURL = Self.repoRoot()
        }
        try p.run()
        self.process = p

        let line = try await Self.readFirstLine(out.fileHandleForReading)
        guard
            let data = line.data(using: .utf8),
            let ready = try? EngineClient.decoder.decode(EngineReady.self, from: data),
            let port = ready.port, let token = ready.token
        else {
            throw EngineError.badHandshake(line)
        }
        self.port = port
        self.token = token
        return ready
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    private static func readFirstLine(_ handle: FileHandle) async throws -> String {
        try await withCheckedThrowingContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                var buffer = Data()
                while true {
                    let chunk = handle.availableData
                    if chunk.isEmpty {
                        cont.resume(throwing: EngineError.badHandshake("engine exited before handshake"))
                        return
                    }
                    buffer.append(chunk)
                    if let nl = buffer.firstIndex(of: 0x0A) {
                        let lineData = buffer.subdata(in: buffer.startIndex..<nl)
                        cont.resume(returning: String(data: lineData, encoding: .utf8) ?? "")
                        return
                    }
                }
            }
        }
    }
}
