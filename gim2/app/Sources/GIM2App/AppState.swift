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

    // Assistant chat + LLM config (key in Keychain; rest in UserDefaults).
    @Published var chat: [ChatMessage] = []
    @Published var chatStreaming = false
    @Published var llmProvider = "deterministic"
    @Published var llmModel = ""
    @Published var llmBaseURL = ""
    @Published var llmApiKey = ""

    private let proc = EngineProcess()
    private(set) var client: EngineClient?

    init() {
        let d = UserDefaults.standard
        llmProvider = d.string(forKey: "llmProvider") ?? "deterministic"
        llmModel = d.string(forKey: "llmModel") ?? ""
        llmBaseURL = d.string(forKey: "llmBaseURL") ?? ""
        llmApiKey = Keychain.get(account: "llm_key")
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

    func saveLLM() {
        let d = UserDefaults.standard
        d.set(llmProvider, forKey: "llmProvider")
        d.set(llmModel, forKey: "llmModel")
        d.set(llmBaseURL, forKey: "llmBaseURL")
        Keychain.set(llmApiKey.trimmingCharacters(in: .whitespacesAndNewlines), account: "llm_key")
    }

    func sendChat(_ text: String) async {
        let t = text.trimmingCharacters(in: .whitespaces)
        guard !t.isEmpty, let client else { return }
        chat.append(ChatMessage(role: .user, text: t))
        chatStreaming = true
        let history: [AssistantMsg] = chat.compactMap { m in
            if m.role == .user { return AssistantMsg(role: "user", content: m.text) }
            if m.role == .assistant, m.result == nil, !m.text.isEmpty {
                return AssistantMsg(role: "assistant", content: m.text)
            }
            return nil
        }
        let req = AssistantRequest(provider: llmProvider, model: llmModel,
                                   apiKey: llmApiKey, baseURL: llmBaseURL, messages: history)
        do {
            for try await (event, data) in client.stream("/assistant", req) {
                let obj = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
                switch event {
                case "tool_call":
                    chat.append(ChatMessage(role: .tool, text: "запуск: \(obj?["name"] as? String ?? "движок")…"))
                case "run_result":
                    if let r = try? EngineClient.decoder.decode(AnswerResult.self, from: data) {
                        chat.append(ChatMessage(role: .assistant, text: "", result: r))
                        record(ScenarioRecord(answer: r, label: r.archetype?.nameRu ?? "Ассистент"))
                    }
                case "assistant_delta":
                    if let txt = obj?["text"] as? String, !txt.isEmpty {
                        chat.append(ChatMessage(role: .assistant, text: txt))
                    }
                case "error":
                    chat.append(ChatMessage(role: .assistant, text: "Ошибка: \(obj?["message"] as? String ?? "сбой")"))
                default:
                    break
                }
            }
        } catch {
            chat.append(ChatMessage(role: .assistant, text: "Сбой связи с движком: \(error.localizedDescription)"))
        }
        chatStreaming = false
    }
    func meta<T: Decodable>(_ kind: String, as type: T.Type) async throws -> T {
        try await require().get("/meta/\(kind)", as: T.self)
    }
}
