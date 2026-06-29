import Foundation

// Talks to the loopback engine over HTTP (light calls) and SSE (runs).
// Every request carries the session bearer token (contract §1).
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

    func getData(_ path: String, query: [URLQueryItem] = []) async throws -> Data {
        let (data, resp) = try await URLSession.shared.data(for: makeRequest(path: path, query: query))
        try Self.check(resp, data)
        return data
    }

    func cancel(runId: String) async {
        let req = makeRequest(path: "/run/\(runId)/cancel", method: "POST", body: Data("{}".utf8))
        _ = try? await URLSession.shared.data(for: req)
    }

    // Streams SSE frames as (eventName, rawDataJSON) tuples until the stream ends.
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
                            let json = String(line.dropFirst("data: ".count))
                            continuation.yield((event, Data(json.utf8)))
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
