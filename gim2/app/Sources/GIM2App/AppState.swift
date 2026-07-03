import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @Published var status: String = "запуск движка…"
    @Published var ready: Bool = false
    @Published var info: EngineReady?
    @Published var ontology: Ontology?
    @Published var archetypes: [ArchetypeInfo] = []

    // Run history + comparison selection (Compare screen).
    @Published var history: [ScenarioRecord] = []
    @Published var compareSelection: [UUID] = []

    // Validated model-trust metrics, pinned as the Compare baseline.
    @Published var scc: SccResult?
    @Published var auc: ConflictMetaResult?
    @Published var backtest: BacktestResult?
    @Published var backtestLoading = false

    // The baseline scenario itself — the no-lever inertial ensemble shown in Compare.
    @Published var baselineEnsemble: EnsembleResult?
    @Published var baselineEnsembleLoading = false

    // Ollama discovery (queried directly from the app at the base URL).
    @Published var ollamaChecked = false
    @Published var ollamaReachable = false
    @Published var ollamaModels: [String] = []
    @Published var ollamaWarming = false
    @Published var ollamaWarmMessage: String?

    // Assistant sessions (explicit, on-disk — see SessionStore) + LLM config (key in
    // Keychain; rest in UserDefaults). `chat` is a thin view onto the active session's
    // messages so the rest of the app (ChatView) is unchanged by the session refactor.
    @Published var sessions: [ChatSession] = []
    @Published var currentSessionID: UUID = UUID()
    @Published var chatStreaming = false
    @Published var llmProvider = "deterministic"
    @Published var llmModel = ""
    @Published var llmBaseURL = ""
    @Published var llmApiKey = ""

    // LLM connection test ("Проверить" in settings).
    enum LLMTestState: Equatable { case idle, testing, ok, fail }
    @Published var llmTestState: LLMTestState = .idle
    @Published var llmTestMessage = ""

    private let proc = EngineProcess()
    private(set) var client: EngineClient?

    init() {
        let d = UserDefaults.standard
        llmProvider = d.string(forKey: "llmProvider") ?? "deterministic"
        llmModel = d.string(forKey: "llmModel") ?? ""
        llmBaseURL = d.string(forKey: "llmBaseURL") ?? ""
        llmApiKey = Keychain.get(account: "llm_key")

        sessions = SessionStore.loadAll()
        if let first = sessions.first {
            currentSessionID = first.id
        } else {
            let fresh = ChatSession()
            sessions = [fresh]
            currentSessionID = fresh.id
            SessionStore.save(fresh)
        }
    }

    // MARK: - Assistant sessions

    private var currentSessionIndex: Int? { sessions.firstIndex(where: { $0.id == currentSessionID }) }

    /// A thin view onto the active session's messages — everything else (ChatView, sendChat)
    /// reads/writes `chat` exactly as before the session refactor.
    var chat: [ChatMessage] {
        get { currentSessionIndex.map { sessions[$0].messages } ?? [] }
        set {
            guard let i = currentSessionIndex else { return }
            sessions[i].messages = newValue
        }
    }

    func newSession() {
        let fresh = ChatSession()
        sessions.insert(fresh, at: 0)
        currentSessionID = fresh.id
        SessionStore.save(fresh)
    }

    /// A thin view onto the active session's trace log (see TraceEntry / "trace" SSE events).
    var trace: [TraceEntry] {
        get { currentSessionIndex.map { sessions[$0].trace } ?? [] }
        set {
            guard let i = currentSessionIndex else { return }
            sessions[i].trace = newValue
        }
    }

    /// The scenario (if any) already established in the current session — the most recent
    /// run_answer/run_scenario tool call's lever recipe. Sent to the backend every turn so
    /// the LLM can route follow-ups (sensitivity/weak-signals/dose) onto the SAME scenario
    /// instead of re-inferring it from its own past narration (or defaulting to run_answer).
    var activeSelection: SelectionInfo? {
        for m in chat.reversed() {
            guard let toolName = m.toolName, let json = m.resultJSON,
                  let data = json.data(using: .utf8) else { continue }
            switch toolName {
            case "run_answer":
                if let r = try? EngineClient.decoder.decode(AnswerResult.self, from: data),
                   let sel = r.selection, !sel.levers.isEmpty { return sel }
            case "run_scenario":
                if let r = try? EngineClient.decoder.decode(ScenarioResult.self, from: data),
                   let sel = r.selection, !sel.levers.isEmpty { return sel }
            default: continue
            }
        }
        return nil
    }

    func selectSession(_ id: UUID) {
        guard sessions.contains(where: { $0.id == id }) else { return }
        currentSessionID = id
    }

    func deleteSession(_ id: UUID) {
        SessionStore.delete(id)
        sessions.removeAll { $0.id == id }
        if sessions.isEmpty { newSession() }
        else if currentSessionID == id { currentSessionID = sessions[0].id }
    }

    private func persistCurrentSession() {
        guard let i = currentSessionIndex else { return }
        SessionStore.save(sessions[i])
    }

    func boot() async {
        do {
            let info = try await proc.start()
            let client = EngineClient(baseURL: URL(string: "http://127.0.0.1:\(proc.port)")!, token: proc.token)
            self.client = client
            self.info = info
            self.ready = true
            self.status = "движок готов · gim2 \(info.gim2Version ?? "?") · ядро \(info.engineLine ?? "?")"
            if let ont = try? await client.get(
                "/ontology", query: [URLQueryItem(name: "max_agents", value: "57")], as: OntologyResult.self) {
                self.ontology = ont.ontology
            }
            if let cat = try? await client.get("/archetypes", as: ArchetypeCatalog.self) {
                self.archetypes = cat.archetypes
            }
        } catch {
            self.status = "ошибка движка: \(error)"
        }
    }

    func shutdown() { proc.stop() }

    private func require() throws -> EngineClient {
        guard let client else { throw EngineError.badHandshake("engine not ready") }
        return client
    }

    func runScenario(_ req: ScenarioRequest) async throws -> ScenarioResult {
        try await require().post("/run/scenario", req, as: ScenarioResult.self)
    }
    func runEnsemble(_ req: EnsembleRequest) async throws -> EnsembleResult {
        try await require().post("/run/ensemble", req, as: EnsembleResult.self)
    }
    func runDose(_ req: DoseRequest) async throws -> DoseResult {
        try await require().post("/run/dose_response", req, as: DoseResult.self)
    }
    func runSensitivity(_ req: SensitivityRequest) async throws -> SensitivityResult {
        try await require().post("/run/sensitivity", req, as: SensitivityResult.self)
    }
    func runAnswer(_ req: AnswerRequest) async throws -> AnswerResult {
        try await require().post("/run/answer", req, as: AnswerResult.self)
    }
    func runWeak(_ req: WeakRequest) async throws -> WeakResult {
        try await require().post("/run/weak_signals", req, as: WeakResult.self)
    }

    func record(_ rec: ScenarioRecord) {
        history.insert(rec, at: 0)
        if history.count > 8 { history.removeLast() }
    }

    // Pinned-baseline trust metrics. AUC is fast; SCC + backtest are slow (they
    // run ensembles), so they load lazily together behind a button.
    func loadValidation() async {
        if auc == nil { auc = try? await meta("conflict_auc", as: ConflictMetaResult.self) }
    }
    func loadBacktest() async {
        guard backtest == nil, !backtestLoading else { return }
        backtestLoading = true
        defer { backtestLoading = false }
        async let btTask = meta("backtest", as: BacktestResult.self)
        async let sccTask = meta("scc", as: SccResult.self)
        backtest = try? await btTask
        scc = try? await sccTask
    }

    // The baseline scenario = the no-lever inertial ensemble (absolute trajectory).
    // It is the reference every scenario Δ is measured against.
    func loadBaselineEnsemble() async {
        guard baselineEnsemble == nil, !baselineEnsembleLoading, let client else { return }
        baselineEnsembleLoading = true
        defer { baselineEnsembleLoading = false }
        let req = EnsembleRequest(members: 120, years: 10, maxAgents: 57, seed: 2026, priorSet: "key")
        baselineEnsemble = try? await client.post("/run/ensemble", req, as: EnsembleResult.self)
    }

    // MARK: - Ollama (queried directly; the engine relays the actual chat)

    var ollamaBase: String {
        let b = llmBaseURL.trimmingCharacters(in: .whitespaces)
        return b.isEmpty ? "http://127.0.0.1:11434" : b
    }

    func refreshOllama() async {
        ollamaChecked = false
        guard let url = URL(string: ollamaBase + "/api/tags") else { return }
        var req = URLRequest(url: url)
        req.timeoutInterval = 4
        do {
            let (data, _) = try await URLSession.shared.data(for: req)
            let tags = try JSONDecoder().decode(OllamaTags.self, from: data)
            ollamaModels = tags.models.map { $0.name }
            ollamaReachable = true
            if (llmModel.isEmpty || !ollamaModels.contains(llmModel)), let first = ollamaModels.first {
                llmModel = first
            }
        } catch {
            ollamaReachable = false
            ollamaModels = []
        }
        ollamaChecked = true
    }

    // Warm the selected model so it is loaded and ready for the assistant.
    func warmOllama() async {
        let model = llmModel.trimmingCharacters(in: .whitespaces)
        guard !model.isEmpty, let url = URL(string: ollamaBase + "/api/generate") else { return }
        ollamaWarming = true
        ollamaWarmMessage = nil
        defer { ollamaWarming = false }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 120
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["model": model, "prompt": "ok", "stream": false])
        do {
            let (_, resp) = try await URLSession.shared.data(for: req)
            let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
            ollamaWarmMessage = (200..<300).contains(code)
                ? "Модель «\(model)» загружена и готова."
                : "Не удалось загрузить модель (код \(code))."
        } catch {
            ollamaWarmMessage = "Ошибка: \(error.localizedDescription)"
        }
    }

    func saveLLM() {
        let d = UserDefaults.standard
        d.set(llmProvider, forKey: "llmProvider")
        d.set(llmModel, forKey: "llmModel")
        d.set(llmBaseURL, forKey: "llmBaseURL")
        Keychain.set(llmApiKey.trimmingCharacters(in: .whitespacesAndNewlines), account: "llm_key")
    }

    // Probe the configured model through the engine: green on success, red + the provider's
    // actual error message (tooltip) on failure. Tests the values currently in the form.
    func testLLM() async {
        guard let client else {
            llmTestState = .fail; llmTestMessage = "движок ещё не запущен"; return
        }
        llmTestState = .testing
        llmTestMessage = ""
        let req = LLMTestRequest(provider: llmProvider,
                                 model: llmModel.trimmingCharacters(in: .whitespaces),
                                 apiKey: llmApiKey.trimmingCharacters(in: .whitespacesAndNewlines),
                                 baseURL: llmBaseURL.trimmingCharacters(in: .whitespaces))
        do {
            let r = try await client.post("/assistant/test", req, as: LLMTestResult.self)
            if r.ok {
                llmTestState = .ok
                var parts: [String] = []
                if let m = r.model, !m.isEmpty { parts.append(m) }
                if let l = r.latencyMs { parts.append("\(l) мс") }
                if let n = r.note, !n.isEmpty { parts.append(n) }
                llmTestMessage = parts.isEmpty ? "соединение успешно" : parts.joined(separator: " · ")
            } else {
                llmTestState = .fail
                llmTestMessage = r.error ?? "не удалось подключиться"
            }
        } catch {
            llmTestState = .fail
            llmTestMessage = "ошибка запроса к движку: \(error.localizedDescription)"
        }
    }

    func sendChat(_ text: String) async {
        let t = text.trimmingCharacters(in: .whitespaces)
        guard !t.isEmpty, let client else { return }
        chat.append(ChatMessage(role: .user, text: t))
        persistCurrentSession()
        chatStreaming = true

        // Compact history sent to the LLM: user turns as-is; past tool outcomes are folded
        // into the assistant's own text (not resent as separate tool-role messages — strict
        // OpenAI-style APIs reject a "tool" message without a matching live tool_call in the
        // SAME turn) so the model has continuity across turns without the full raw payload.
        let history: [AssistantMsg] = chat.compactMap { m -> AssistantMsg? in
            switch m.role {
            case .user:
                return AssistantMsg(role: "user", content: m.text)
            case .tool:
                return nil
            case .assistant:
                var content = m.text
                if let s = m.toolSummary, !s.isEmpty {
                    let prefix = m.toolName.map { "[\($0)] " } ?? ""
                    content = content.isEmpty ? prefix + s : prefix + s + "\n" + content
                }
                return content.isEmpty ? nil : AssistantMsg(role: "assistant", content: content)
            }
        }
        let active = activeSelection
        let req = AssistantRequest(provider: llmProvider, model: llmModel,
                                   apiKey: llmApiKey, baseURL: llmBaseURL, messages: history,
                                   activeLevers: active?.levers,
                                   activeActors: active?.actors.isEmpty == false ? active?.actors : nil)

        // Tracks the most recent tool_call/run_result pair until the model's narration
        // (assistant_delta) arrives, so the final chat bubble carries what was computed.
        var pendingToolName: String? = nil
        var pendingResultJSON: String? = nil
        do {
            for try await (event, data) in client.stream("/assistant", req) {
                let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
                switch event {
                case "tool_call":
                    let name = obj?["name"] as? String ?? "движок"
                    pendingToolName = name
                    chat.append(ChatMessage(role: .tool, text: "запуск: \(name)…"))
                case "run_result":
                    pendingResultJSON = String(data: data, encoding: .utf8)
                    if pendingToolName == "run_answer",
                       let r = try? EngineClient.decoder.decode(AnswerResult.self, from: data) {
                        chat.append(ChatMessage(role: .assistant, text: "", toolName: "run_answer",
                                                toolSummary: r.verdict, resultJSON: pendingResultJSON))
                        record(ScenarioRecord(answer: r, label: r.archetype?.nameRu ?? "Ассистент"))
                        pendingToolName = nil; pendingResultJSON = nil
                    }
                case "assistant_delta":
                    if let txt = obj?["text"] as? String, !txt.isEmpty {
                        let chartImage = (pendingToolName != nil && pendingResultJSON != nil)
                            ? ChartSnapshot.render(toolName: pendingToolName!, resultJSON: pendingResultJSON!)
                            : nil
                        chat.append(ChatMessage(role: .assistant, text: txt, toolName: pendingToolName,
                                                toolSummary: pendingToolName == nil ? nil : txt,
                                                resultJSON: pendingResultJSON, chartImageBase64: chartImage))
                        pendingToolName = nil; pendingResultJSON = nil
                    }
                case "error":
                    chat.append(ChatMessage(role: .assistant, text: "Ошибка: \(obj?["message"] as? String ?? "сбой")"))
                case "trace":
                    let kind = obj?["kind"] as? String ?? "?"
                    let text = obj?["text"] as? String ?? ""
                    trace.append(TraceEntry(kind: kind, text: text))
                default:
                    break
                }
                persistCurrentSession()
            }
        } catch {
            chat.append(ChatMessage(role: .assistant, text: "Сбой связи с движком: \(error.localizedDescription)"))
            persistCurrentSession()
        }
        chatStreaming = false
    }
    func meta<T: Decodable>(_ kind: String, as type: T.Type) async throws -> T {
        try await require().get("/meta/\(kind)", as: T.self)
    }
}
