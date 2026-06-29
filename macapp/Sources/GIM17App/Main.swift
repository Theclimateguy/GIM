import Foundation

// Single entry point. `--selftest` runs a headless Swift→engine round-trip
// (boot sidecar, load world, light What-if) and exits — verifiable from the
// terminal without a GUI display. Otherwise the SwiftUI app runs normally.
@main
enum EntryPoint {
    static func main() async {
        if CommandLine.arguments.contains("--selftest") {
            exit(await SelfTest.run())
        }
        GIM17App.main()
    }
}

enum SelfTest {
    static func run() async -> Int32 {
        do {
            let engine = EngineProcess()
            let ready = try await engine.start()
            log("engine ready: schema=\(ready.schema ?? "?") gim=\(ready.gimVersion ?? "?") port=\(engine.port) offline=\(ready.offline ?? false)")

            let client = EngineClient(baseURL: URL(string: "http://127.0.0.1:\(engine.port)")!, token: engine.token)

            let world = try await client.post(
                "/world/load",
                WorldLoadRequest(stateCsv: nil, stateYear: 2026, maxCountries: nil),
                as: WorldLoadResponse.self
            )
            log("world_key=\(world.worldKey) actors=\(world.actors?.count ?? 0) personas=\(world.personas?.count ?? 0)")
            if let p = world.personas?.first {
                log("persona[0]: id=\(p.id) name=\(p.name.current) nudges=\(p.nudges?.count ?? 0)")
            }

            let result = try await client.post(
                "/run/whatif",
                WhatIfRequest(
                    worldKey: world.worldKey,
                    question: "How will Hormuz tensions escalate?",
                    actors: ["Iran", "United States", "Israel"],
                    template: nil,
                    horizon: 2
                ),
                as: RunResult.self
            )
            let crit = result.criticality.map { String(format: "%.3f", $0) } ?? "nil"
            log("whatif: criticality=\(crit) outcomes=\(result.outcomes?.count ?? 0) drivers=\(result.drivers?.count ?? 0)")
            log("whatif verdict: \(result.verdict ?? "nil")")
            log("trace: \(result.trace?.equivCli ?? "nil")")
            if let top = result.outcomes?.prefix(3) {
                for o in top { log("  outcome: \(o.name) = \(String(format: "%.3f", o.value)) [\(o.valence ?? "-")]") }
            }

            var progressCount = 0
            var streamedResult: RunResult?
            for try await (event, data) in client.stream(
                "/run/whatif",
                WhatIfRequest(worldKey: world.worldKey, question: "How will Hormuz tensions escalate?",
                              actors: ["Iran", "United States", "Israel"], template: nil, horizon: 2)
            ) {
                if event == "progress" { progressCount += 1 }
                if event == "result" { streamedResult = try? EngineClient.decoder.decode(RunResult.self, from: data) }
            }
            log("SSE whatif: progress=\(progressCount) result=\(streamedResult != nil)")
            if let s = streamedResult?.series {
                log("series: gdp=\(s.gdp?.count ?? 0) tension=\(s.socialTension?.count ?? 0) energyPts=\(s.prices?.energy?.count ?? 0)")
            }

            let doc = try await client.getData(
                "/personas/hawk_protectionist/doctrine",
                query: [URLQueryItem(name: "world_key", value: world.worldKey),
                        URLQueryItem(name: "country", value: "United States")]
            )
            if let obj = try JSONSerialization.jsonObject(with: doc) as? [String: Any],
               let deltas = obj["deltas"] as? [String: Any] {
                log("doctrine: dims=\(deltas.count) escalation_delta=\(deltas["escalation_bias"] ?? "?")")
            }

            var intents = 0
            var playRes: RunResult?
            for try await (event, data) in client.stream(
                "/run/play",
                PlayRequest(worldKey: world.worldKey, country: "United States",
                            persona: "hawk_protectionist", goal: "Pressure China on trade",
                            roundYears: 2, ensembleSize: 2)
            ) {
                if event == "intent" { intents += 1 }
                if event == "result" { playRes = try? EngineClient.decoder.decode(RunResult.self, from: data) }
            }
            log("play: intents=\(intents) result=\(playRes != nil) feed=\(playRes?.intentsFeed?.count ?? 0)")

            var asstResult = false
            for try await (event, _) in client.stream(
                "/assistant",
                AssistantRequest(worldKey: world.worldKey, provider: "deterministic", model: "",
                                 apiKey: "", baseUrl: "",
                                 messages: [ChatTurn(role: "user", content: "что если закроют Ормуз?")])
            ) {
                if event == "run_result" { asstResult = true }
            }
            log("assistant(deterministic): run_result=\(asstResult)")

            engine.stop()
            log("SELFTEST OK")
            return 0
        } catch {
            log("SELFTEST FAIL: \(error)")
            return 1
        }
    }

    private static func log(_ s: String) {
        FileHandle.standardError.write(Data("[selftest] \(s)\n".utf8))
    }
}
