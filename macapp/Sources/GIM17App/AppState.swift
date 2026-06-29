import SwiftUI

enum Route: Hashable {
    case home, whatif, play, running, situation, compare, expert, chat
}

enum EngineStatus: Equatable {
    case launching
    case ready
    case failed(String)
}

@MainActor
final class AppState: ObservableObject {
    @Published var engineStatus: EngineStatus = .launching
    @Published var route: Route = .chat
    @Published var actors: [ActorOption] = []
    @Published var personas: [Persona] = []
    @Published var worldKey: String = ""
    @Published var stateYear: Int = 2026
    @Published var lastResult: RunResult?
    @Published var progress: ProgressEvent?
    @Published var currentRunId: String?
    @Published var runError: String?
    @Published var runMode: String = ""
    @Published var playCountry: String = "United States"
    @Published var playPersona: String = ""
    @Published var playGoal: String = ""
    @Published var doctrineRows: [DoctrineRow] = []
    @Published var doctrineLoading = false
    @Published var streamedIntents: [IntentFeedItem] = []
    @Published var history: [RunRecord] = []
    @Published var baseline: RunRecord?
    @Published var baselineLoading = false
    @Published var compareSelection: [UUID] = []
    @Published var chat: [ChatMessage] = []
    @Published var chatStreaming = false
    @Published var llmProvider = "deterministic"
    @Published var llmModel = ""
    @Published var llmApiKey = ""
    @Published var llmBaseURL = ""

    let engine = EngineProcess()
    private(set) var client: EngineClient?

    private let keychainAccount = "openai"

    init() {
        let d = UserDefaults.standard
        llmProvider = d.string(forKey: "gim.llmProvider") ?? "deterministic"
        llmModel = d.string(forKey: "gim.llmModel") ?? ""
        llmBaseURL = d.string(forKey: "gim.llmBaseURL") ?? ""
        // The dedicated "deepseek" provider was folded into OpenAI-compatible;
        // migrate any saved selection so it keeps working via base_url.
        if llmProvider == "deepseek" {
            llmProvider = "openai"
            if llmBaseURL.isEmpty { llmBaseURL = "https://api.deepseek.com" }
        }
        // API key lives in the Keychain. One-time migration: if an older build
        // left it in UserDefaults (plaintext), move it to the Keychain and wipe
        // the plaintext copy.
        llmApiKey = Keychain.get(account: keychainAccount)
        if llmApiKey.isEmpty, let legacy = d.string(forKey: "gim.llmApiKey"), !legacy.isEmpty {
            llmApiKey = legacy
            Keychain.set(legacy, account: keychainAccount)
        }
        d.removeObject(forKey: "gim.llmApiKey")
    }

    func boot() async {
        engineStatus = .launching
        do {
            let ready = try await engine.start()
            guard let token = ready.token, let port = ready.port else {
                engineStatus = .failed("missing port/token in handshake")
                return
            }
            let client = EngineClient(
                baseURL: URL(string: "http://127.0.0.1:\(port)")!,
                token: token
            )
            self.client = client
            let world = try await client.post(
                "/world/load",
                WorldLoadRequest(stateCsv: nil, stateYear: stateYear, maxCountries: nil),
                as: WorldLoadResponse.self
            )
            self.worldKey = world.worldKey
            self.actors = world.actors ?? []
            self.personas = world.personas ?? []
            self.engineStatus = .ready
        } catch {
            self.engineStatus = .failed(String(describing: error))
        }
    }

    func runWhatIf(question: String, actors: [String], label: String,
                   horizon: Int = 3, backgroundPolicy: String = "compiled-llm",
                   llmRefresh: String = "trigger", seed: Int = 2026) async {
        guard let client else { return }
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return }
        runError = nil
        progress = nil
        currentRunId = nil
        runMode = label
        route = .running
        let req = WhatIfRequest(
            worldKey: worldKey, question: q,
            actors: actors.isEmpty ? nil : actors, template: nil, horizon: horizon,
            backgroundPolicy: backgroundPolicy, llmRefresh: llmRefresh, seed: seed
        )
        do {
            for try await (event, data) in client.stream("/run/whatif", req) {
                switch event {
                case "progress":
                    if let p = try? EngineClient.decoder.decode(ProgressEvent.self, from: data) {
                        progress = p
                        if currentRunId == nil { currentRunId = p.runId }
                    }
                case "result":
                    if let r = try? EngineClient.decoder.decode(RunResult.self, from: data) {
                        lastResult = r
                        record(r, label: label)
                    }
                    route = .situation
                case "error":
                    runError = (try? EngineClient.decoder.decode(SSEError.self, from: data))?.message ?? "run failed"
                    route = .expert
                default:
                    break
                }
            }
        } catch {
            runError = String(describing: error)
            route = .expert
        }
    }

    // Shared streaming driver for the structured Expert run-types. Navigates to
    // the Running screen, then to the Situation room on a result; routes errors
    // back to Expert. `collectsIntents` is only used by Play.
    private func streamStructured<B: Encodable>(
        path: String, body: B, label: String, collectsIntents: Bool = false
    ) async {
        guard let client else { return }
        runError = nil
        progress = nil
        currentRunId = nil
        runMode = label
        if collectsIntents { streamedIntents = [] }
        route = .running
        do {
            for try await (event, data) in client.stream(path, body) {
                switch event {
                case "progress":
                    if let p = try? EngineClient.decoder.decode(ProgressEvent.self, from: data) {
                        progress = p
                        if currentRunId == nil { currentRunId = p.runId }
                    }
                case "intent" where collectsIntents:
                    if let it = try? EngineClient.decoder.decode(IntentFeedItem.self, from: data) {
                        streamedIntents.append(it)
                    }
                case "result":
                    if let r = try? EngineClient.decoder.decode(RunResult.self, from: data) {
                        lastResult = r
                        record(r, label: label)
                    }
                    route = .situation
                case "error":
                    runError = (try? EngineClient.decoder.decode(SSEError.self, from: data))?.message ?? "прогон не выполнен"
                    route = .expert
                default:
                    break
                }
            }
        } catch {
            runError = String(describing: error)
            route = .expert
        }
    }

    func runComposed(question: String, levers: [LeverChoice], actors: [String], label: String,
                     horizon: Int = 5, backgroundPolicy: String = "compiled-llm",
                     llmRefresh: String = "trigger", seed: Int = 2026) async {
        guard !levers.isEmpty else { return }
        let q = question.trimmingCharacters(in: .whitespacesAndNewlines)
        let req = ComposedRequest(
            worldKey: worldKey,
            question: q.isEmpty ? "Композитный сценарий из выбранных возмущений" : q,
            levers: levers, actors: actors.isEmpty ? nil : actors, horizon: horizon,
            backgroundPolicy: backgroundPolicy, llmRefresh: llmRefresh, seed: seed)
        await streamStructured(path: "/run/composed", body: req, label: label)
    }

    func runGame(description: String, label: String, horizon: Int = 4,
                 equilibrium: Bool = true, episodes: Int = 50, maxCombinations: Int = 256,
                 backgroundPolicy: String = "compiled-llm", seed: Int = 2026) async {
        let d = description.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !d.isEmpty else { return }
        let req = GameRequest(
            worldKey: worldKey, casePath: nil, description: d, horizon: horizon,
            equilibrium: equilibrium, episodes: episodes, maxCombinations: maxCombinations,
            backgroundPolicy: backgroundPolicy, seed: seed)
        await streamStructured(path: "/run/game", body: req, label: label)
    }

    // The pinned reference for Compare: the model's inertial trajectory with no
    // new shocks. A real engine run (not a stored constant), computed once.
    func loadBaseline() async {
        guard let client, baseline == nil, !baselineLoading else { return }
        baselineLoading = true
        defer { baselineLoading = false }
        let req = WhatIfRequest(
            worldKey: worldKey,
            question: "Baseline: inertial world trajectory, no new shocks.",
            actors: nil, template: nil, horizon: 5,
            backgroundPolicy: "compiled-llm", llmRefresh: "never", seed: 2026)
        do {
            for try await (event, data) in client.stream("/run/whatif", req) {
                if event == "result", let r = try? EngineClient.decoder.decode(RunResult.self, from: data) {
                    baseline = RunRecord(label: "Базовая линия", result: r)
                }
            }
        } catch {
            // Baseline is best-effort; Compare degrades to scenario-vs-scenario.
        }
    }

    func cancelRun() async {
        if let id = currentRunId { await client?.cancel(runId: id) }
    }

    func loadDoctrine() async {
        guard let client, !playPersona.isEmpty, !playCountry.isEmpty else {
            doctrineRows = []
            return
        }
        doctrineLoading = true
        defer { doctrineLoading = false }
        do {
            let data = try await client.getData(
                "/personas/\(playPersona)/doctrine",
                query: [
                    URLQueryItem(name: "world_key", value: worldKey),
                    URLQueryItem(name: "country", value: playCountry),
                ]
            )
            guard let obj = try JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
            let base = obj["base"] as? [String: Any] ?? [:]
            let shifted = obj["shifted"] as? [String: Any] ?? [:]
            let deltas = obj["deltas"] as? [String: Any] ?? [:]
            doctrineRows = doctrineDims.compactMap { dim in
                guard let b = (base[dim.key] as? NSNumber)?.doubleValue else { return nil }
                let s = (shifted[dim.key] as? NSNumber)?.doubleValue ?? b
                let d = (deltas[dim.key] as? NSNumber)?.doubleValue ?? (s - b)
                return DoctrineRow(key: dim.key, label: dim.label, base: b, shift: s, delta: d)
            }
        } catch {
            doctrineRows = []
        }
    }

    func runPlay(roundYears: Int = 4, ensembleSize: Int = 3, seed: Int = 2026,
                 backgroundPolicy: String = "compiled-llm") async {
        guard let client, !playCountry.isEmpty, !playPersona.isEmpty else { return }
        runError = nil
        progress = nil
        currentRunId = nil
        streamedIntents = []
        runMode = "Игра за страну · \(playCountry)"
        route = .running
        let goal = playGoal.trimmingCharacters(in: .whitespacesAndNewlines)
        let req = PlayRequest(
            worldKey: worldKey, country: playCountry, persona: playPersona,
            goal: goal.isEmpty ? "Hold current course." : goal,
            roundYears: roundYears, ensembleSize: ensembleSize, seed: seed
        )
        do {
            for try await (event, data) in client.stream("/run/play", req) {
                switch event {
                case "progress":
                    if let p = try? EngineClient.decoder.decode(ProgressEvent.self, from: data) {
                        progress = p
                        if currentRunId == nil { currentRunId = p.runId }
                    }
                case "intent":
                    if let it = try? EngineClient.decoder.decode(IntentFeedItem.self, from: data) {
                        streamedIntents.append(it)
                    }
                case "result":
                    if let r = try? EngineClient.decoder.decode(RunResult.self, from: data) {
                        lastResult = r
                        record(r, label: runMode)
                    }
                    route = .situation
                case "error":
                    runError = (try? EngineClient.decoder.decode(SSEError.self, from: data))?.message ?? "run failed"
                    route = .expert
                default:
                    break
                }
            }
        } catch {
            runError = String(describing: error)
            route = .expert
        }
    }

    func record(_ r: RunResult, label: String) {
        history.insert(RunRecord(label: label, result: r), at: 0)
        if history.count > 6 { history.removeLast() }
    }

    func saveLLM() {
        // Trim — a trailing newline from a pasted key is a common 401 cause.
        llmApiKey = llmApiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        llmBaseURL = llmBaseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let d = UserDefaults.standard
        d.set(llmProvider, forKey: "gim.llmProvider")
        d.set(llmModel, forKey: "gim.llmModel")
        d.set(llmBaseURL, forKey: "gim.llmBaseURL")
        // Secret only in the Keychain (empty key removes it); never in UserDefaults.
        Keychain.set(llmApiKey, account: keychainAccount)
        d.removeObject(forKey: "gim.llmApiKey")
    }

    func sendChat(_ text: String) async {
        guard let client else { return }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !chatStreaming else { return }
        chat.append(ChatMessage(role: .user, text: trimmed))
        chatStreaming = true
        let history: [ChatTurn] = chat.compactMap { m in
            switch m.role {
            case .user: return ChatTurn(role: "user", content: m.text)
            case .assistant where !m.text.isEmpty: return ChatTurn(role: "assistant", content: m.text)
            default: return nil
            }
        }
        let body = AssistantRequest(worldKey: worldKey, provider: llmProvider, model: llmModel,
                                    apiKey: llmApiKey, baseUrl: llmBaseURL, messages: history)
        do {
            for try await (event, data) in client.stream("/assistant", body) {
                switch event {
                case "tool_call":
                    if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let name = obj["name"] as? String {
                        chat.append(ChatMessage(role: .tool, text: toolLabel(name), toolName: name))
                    }
                case "run_result":
                    if let r = try? EngineClient.decoder.decode(RunResult.self, from: data) {
                        lastResult = r
                        record(r, label: "Ассистент")
                        chat.append(ChatMessage(role: .assistant, result: r))
                    }
                case "assistant_delta":
                    if let payload = try? EngineClient.decoder.decode([String: String].self, from: data),
                       let txt = payload["text"], !txt.isEmpty {
                        chat.append(ChatMessage(role: .assistant, text: txt))
                    }
                case "error":
                    let msg = (try? EngineClient.decoder.decode(SSEError.self, from: data))?.message ?? "ошибка"
                    chat.append(ChatMessage(role: .assistant, text: "⚠️ " + msg))
                default:
                    break
                }
            }
        } catch {
            chat.append(ChatMessage(role: .assistant, text: "⚠️ " + String(describing: error)))
        }
        chatStreaming = false
    }

    private func toolLabel(_ name: String) -> String {
        switch name {
        case "run_whatif": return "Прогоняю «Что если»…"
        case "run_composed": return "Собираю сценарий…"
        case "run_play": return "Играю раунд…"
        case "doctrine_preview": return "Считаю доктрину…"
        case "list_actors": return "Смотрю список стран…"
        case "list_personas": return "Смотрю персоны…"
        default: return name
        }
    }

    func shutdown() {
        engine.stop()
    }
}
