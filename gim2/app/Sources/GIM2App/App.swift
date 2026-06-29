import SwiftUI

// Custom entry point: `--selftest` runs a headless Swift→engine round-trip and
// exits (CI / verification without a GUI); otherwise the SwiftUI app launches.
@main
struct GIM2Entry {
    static func main() {
        if CommandLine.arguments.contains("--selftest") {
            Selftest.run()
            return
        }
        GIM2GUI.main()
    }
}

struct GIM2GUI: App {
    @StateObject private var app = AppState()

    var body: some Scene {
        WindowGroup("GIM17 v2") {
            ZStack {
                RootView().environmentObject(app)
                if !app.ready {
                    SplashView(status: app.status).transition(.opacity)
                }
            }
            .frame(minWidth: 940, minHeight: 640)
            .preferredColorScheme(.dark)
            .animation(.easeOut(duration: 0.4), value: app.ready)
            .task { await app.boot() }
            .onDisappear { app.shutdown() }
        }
        .windowStyle(.hiddenTitleBar)
    }
}

enum Selftest {
    static func run() {
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        var msg = ""
        Task {
            let proc = EngineProcess()
            do {
                _ = try await proc.start()
                let client = EngineClient(baseURL: URL(string: "http://127.0.0.1:\(proc.port)")!, token: proc.token)
                let req = ScenarioRequest(levers: ["decarbonization"], magnitude: 1.0, actors: nil,
                                          members: 6, years: 4, maxAgents: 8)
                let res = try await client.post("/run/scenario", req, as: ScenarioResult.self)
                let okScenario = res.mode == "scenario" && !res.projection.metrics.isEmpty

                // Exercise the heavy /run/answer over the SAME spawn path the app uses.
                let areq = AnswerRequest(archetype: "energy_war", members: 16, years: 6,
                                         maxAgents: 40, thresholdMembers: 12, cascadeMembers: 12)
                let ares = try await client.post("/run/answer", areq, as: AnswerResult.self)
                let okAnswer = ares.mode == "answer" && !ares.actors.geo.countries.isEmpty

                ok = okScenario && okAnswer
                msg = "scenario=\(res.projection.metrics.count) · answer map=\(ares.actors.geo.countries.count) "
                    + "verdict=\"\(ares.verdict.prefix(36))…\""
                proc.stop()
            } catch {
                msg = "\(error)"
            }
            sem.signal()
        }
        sem.wait()
        FileHandle.standardError.write(Data("selftest: \(ok ? "OK" : "FAIL") · \(msg)\n".utf8))
        exit(ok ? 0 : 1)
    }
}
