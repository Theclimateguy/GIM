import Foundation

// Spawns and supervises the Python engine sidecar, reading its one-line JSON
// handshake (contract §1) to learn the ephemeral port + session token.
//
// Dev mode: runs `python3 -m gim engine` from the repo root.
// Packaged mode: runs the frozen `gim-engine` binary bundled in Resources.
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
            "/opt/miniconda3/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        for c in candidates where FileManager.default.isExecutableFile(atPath: c) { return c }
        return "/usr/bin/python3"
    }

    static func repoRoot() -> URL {
        if let r = ProcessInfo.processInfo.environment["GIM_REPO_ROOT"], !r.isEmpty {
            return URL(fileURLWithPath: r)
        }
        return URL(fileURLWithPath: "/Users/theclimateguy/Documents/Projects/Global_Integrated_model/GIM17")
    }

    func start() async throws -> EngineReady {
        let p = Process()
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice

        if let bundled = Self.bundledEngineURL() {
            p.executableURL = bundled
            p.arguments = []
        } else {
            p.executableURL = URL(fileURLWithPath: Self.pythonPath())
            p.arguments = ["-m", "gim", "engine"]
            p.currentDirectoryURL = Self.repoRoot()
        }
        try p.run()
        self.process = p

        let line = try await Self.readFirstLine(out.fileHandleForReading)
        guard
            let data = line.data(using: .utf8),
            let ready = try? Self.decoder.decode(EngineReady.self, from: data),
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

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

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
