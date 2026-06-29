import SwiftUI

// Shared UI atoms ----------------------------------------------------------- //

private let METRIC_OPTIONS = ["world_gdp", "temperature", "co2", "mean_social_tension"]

struct Chip: View {
    let text: String
    let on: Bool
    let tap: () -> Void
    var body: some View {
        Text(text)
            .font(Theme.ui(12, on ? .semibold : .regular))
            .padding(.horizontal, 10).padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(on ? Theme.accent.opacity(0.16) : Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(on ? Theme.accent : Theme.line, lineWidth: 1))
            .foregroundStyle(on ? Theme.text : Theme.muted)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .contentShape(Rectangle())
            .onTapGesture(perform: tap)
    }
}

struct RunButton: View {
    let title: String
    let running: Bool
    let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                if running { ProgressView().controlSize(.small).tint(Theme.accentInk) }
                Text(running ? "Считаю…" : title).font(Theme.ui(13, .semibold))
            }
            .foregroundStyle(Theme.accentInk)
            .padding(.horizontal, 16).padding(.vertical, 9)
            .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
        .disabled(running)
        .opacity(running ? 0.7 : 1)
    }
}

private struct ErrorLine: View {
    let text: String?
    var body: some View {
        if let text { Text(text).font(Theme.ui(11)).foregroundStyle(Theme.deltaDown) }
    }
}

// E6 — Scenario vs baseline (primary screen) -------------------------------- //

struct ScenarioView: View {
    @EnvironmentObject var app: AppState
    @State private var selected: Set<String> = ["decarbonization"]
    @State private var magnitude: Double = 0.6
    @State private var horizon: Int = 10
    @State private var members: Int = 120
    @State private var actorsText: String = ""
    @State private var result: ScenarioResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Сценарий vs база",
                             subtitle: "дельта-веера (сценарий − база) по валидированным метрикам")

                if let levers = app.ontology?.levers {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 170), spacing: 8)], alignment: .leading, spacing: 8) {
                        ForEach(levers) { lever in
                            Chip(text: lever.labelRu, on: selected.contains(lever.id)) {
                                if selected.contains(lever.id) { selected.remove(lever.id) }
                                else { selected.insert(lever.id) }
                            }
                        }
                    }
                } else {
                    Text("загрузка онтологии рычагов…").font(Theme.ui(12)).foregroundStyle(Theme.muted)
                }

                HStack(spacing: 16) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Интенсивность: \(String(format: "%.2f", magnitude))")
                            .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        Slider(value: $magnitude, in: 0.15...1.25).frame(width: 200).tint(Theme.accent)
                    }
                    Stepper("Горизонт: \(horizon) лет", value: $horizon, in: 3...30)
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                }

                TextField("акторы через запятую (для торговли/санкций), напр. United States, China",
                          text: $actorsText)
                    .textFieldStyle(.plain).font(Theme.ui(12)).foregroundStyle(Theme.text)
                    .padding(8).background(Theme.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line))

                HStack {
                    RunButton(title: "Сравнить со сценарием", running: running, action: run)
                    ErrorLine(text: error)
                }

                if let result {
                    BriefView(text: result.brief)
                    ForEach(result.projection.metrics) { m in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(MetricLabel.of(m.metric)).font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                            DeltaChartView(delta: m.delta)
                        }
                        .card()
                    }
                    TraceLine(cli: result.equivCli)
                }
            }
            .padding(18)
        }
    }

    private func run() {
        running = true; error = nil
        let actors = actorsText.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        let req = ScenarioRequest(levers: Array(selected), magnitude: magnitude,
                                  actors: actors.isEmpty ? nil : actors, members: members,
                                  years: horizon, maxAgents: 57)
        Task {
            defer { running = false }
            do { result = try await app.runScenario(req) }
            catch { self.error = "\(error)" }
        }
    }
}

// E7 — Ensembles + dose-response ------------------------------------------- //

struct EnsembleDoseView: View {
    @EnvironmentObject var app: AppState
    @State private var tab = 0

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $tab) {
                Text("Ансамбли").tag(0); Text("Дозовая кривая").tag(1)
            }
            .pickerStyle(.segmented).labelsHidden().tint(Theme.accent).padding([.horizontal, .top], 18)
            if tab == 0 { EnsemblePane() } else { DosePane() }
        }
    }
}

private struct EnsemblePane: View {
    @EnvironmentObject var app: AppState
    @State private var members = 200
    @State private var years = 10
    @State private var result: EnsembleResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Ансамблевые веера", subtitle: "median / IQR / 5–95 по приорам (Рис. 4)")
                HStack(spacing: 16) {
                    Stepper("Члены: \(members)", value: $members, in: 40...500, step: 40)
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                    Stepper("Годы: \(years)", value: $years, in: 5...20)
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                }
                HStack { RunButton(title: "Прогнать ансамбль", running: running, action: run); ErrorLine(text: error) }
                if let result {
                    ForEach(result.projection.metrics) { fan in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(MetricLabel.of(fan.metric)).font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                            FanChartView(fan: fan)
                        }.card()
                    }
                    TraceLine(cli: result.equivCli)
                }
            }.padding(18)
        }
    }

    private func run() {
        running = true; error = nil
        let req = EnsembleRequest(members: members, years: years, maxAgents: 57, seed: 2026, priorSet: "key")
        Task { defer { running = false }
            do { result = try await app.runEnsemble(req) } catch { self.error = "\(error)" } }
    }
}

private struct DosePane: View {
    @EnvironmentObject var app: AppState
    @State private var lever = "growth"
    @State private var metric = "world_gdp"
    @State private var result: DoseResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Дозовая кривая",
                             subtitle: "терминальная Δ vs величина рычага — ненулевой наклон (Рис. 6–9)")
                HStack(spacing: 16) {
                    Picker("Рычаг", selection: $lever) {
                        ForEach(app.ontology?.levers ?? []) { Text($0.labelRu).tag($0.id) }
                    }.frame(width: 240)
                    Picker("Метрика", selection: $metric) {
                        ForEach(METRIC_OPTIONS, id: \.self) { Text(MetricLabel.of($0)).tag($0) }
                    }.frame(width: 200)
                }.font(Theme.ui(12))
                HStack { RunButton(title: "Построить кривую", running: running, action: run); ErrorLine(text: error) }
                if let result {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("\(result.lever) → Δ \(MetricLabel.of(result.projection.metric))")
                            .font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        DoseChartView(dose: result.projection)
                        Text(String(format: "база (терминал): %.4g", result.projection.baseline))
                            .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                    }.card()
                    TraceLine(cli: result.equivCli)
                }
            }.padding(18)
        }
    }

    private func run() {
        running = true; error = nil
        let req = DoseRequest(lever: lever, grid: [0.0, 0.25, 0.5, 0.75, 1.0, 1.25], metric: metric,
                              members: 120, years: 10, maxAgents: 57)
        Task { defer { running = false }
            do { result = try await app.runDose(req) } catch { self.error = "\(error)" } }
    }
}

// E8 — Sensitivity + weak signals + About ---------------------------------- //

struct WeakResult: Decodable {
    struct Maha: Decodable {
        let anomaly: [Bool]?
        let distanceSq: [Double]?
        let nAnomalies: Int?
        let threshold: Double?
    }
    struct Signals: Decodable {
        let mahalanobis: Maha?
        let dimensions: [String]?
    }
    let schema: String
    let weakSignals: Signals
}

struct ExpertView: View {
    @State private var tab = 0
    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $tab) {
                Text("Чувствительность").tag(0); Text("Слабые сигналы").tag(1); Text("О модели").tag(2)
            }
            .pickerStyle(.segmented).labelsHidden().tint(Theme.accent).padding([.horizontal, .top], 18)
            switch tab {
            case 0: SensitivityPane()
            case 1: WeakPane()
            default: AboutPane()
            }
        }
    }
}

private struct SensitivityPane: View {
    @EnvironmentObject var app: AppState
    @State private var metric = "world_gdp"
    @State private var result: SensitivityResult?
    @State private var running = false
    @State private var error: String?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Чувствительность (Morris)", subtitle: "какие параметры правят выходом (Рис. 3)")
                Picker("Метрика", selection: $metric) {
                    ForEach(METRIC_OPTIONS, id: \.self) { Text(MetricLabel.of($0)).tag($0) }
                }.frame(width: 220).font(Theme.ui(12))
                HStack { RunButton(title: "Скрининг параметров", running: running, action: run); ErrorLine(text: error) }
                if let result {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("μ* по \(MetricLabel.of(result.metric))").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        TornadoChartView(params: result.projection.params)
                    }.card()
                    TraceLine(cli: result.equivCli)
                }
            }.padding(18)
        }
    }
    private func run() {
        running = true; error = nil
        Task { defer { running = false }
            do { result = try await app.runSensitivity(.init(metric: metric, years: 10, r: 8, maxAgents: 30)) }
            catch { self.error = "\(error)" } }
    }
}

private struct WeakPane: View {
    @EnvironmentObject var app: AppState
    @State private var lever = "energy_shock"
    @State private var result: WeakResult?
    @State private var running = false
    @State private var error: String?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "Слабые сигналы (сценарий vs база)",
                             subtitle: "Махаланобис-аномалии в динамике состояния")
                Picker("Рычаг", selection: $lever) {
                    ForEach(app.ontology?.levers ?? []) { Text($0.labelRu).tag($0.id) }
                }.frame(width: 260).font(Theme.ui(12))
                HStack { RunButton(title: "Сканировать", running: running, action: run); ErrorLine(text: error) }
                if let m = result?.weakSignals.mahalanobis {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Аномалии: \(m.nAnomalies ?? 0) шагов")
                            .font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        if let t = m.threshold {
                            Text(String(format: "порог χ²: %.2f", t)).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        }
                        if let d = result?.weakSignals.dimensions {
                            Text("измерения: " + d.joined(separator: ", "))
                                .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        }
                        Text("(вероятность разладки и критическое замедление — в сыром payload weak_signals)")
                            .font(Theme.ui(10)).foregroundStyle(Theme.faint)
                    }.card()
                }
            }.padding(18)
        }
    }
    private func run() {
        running = true; error = nil
        struct Req: Encodable { var levers: [String]; var years: Int; var maxAgents: Int }
        Task { defer { running = false }
            do {
                result = try await app.client?.post("/run/weak_signals",
                    Req(levers: [lever], years: 12, maxAgents: 30), as: WeakResult.self)
            } catch { self.error = "\(error)" }
        }
    }
}

private struct AboutPane: View {
    @EnvironmentObject var app: AppState
    @State private var scc: SccResult?
    @State private var auc: ConflictMetaResult?
    @State private var backtest: BacktestResult?
    @State private var loadingBacktest = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle(title: "О модели", subtitle: "валидированные показатели доверия из статьи")

                if let auc {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Относительный риск конфликта").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        AUCView(proj: auc.projection)
                        Text("воспроизвести: " + auc.reproduce).font(Theme.mono(10)).foregroundStyle(Theme.faint)
                    }.card()
                }

                if let scc {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("SCC ($/тCO₂) по горизонтам").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        ForEach(scc.centralUsdPerTco2.sorted(by: { (Int($0.key) ?? 0) < (Int($1.key) ?? 0) }), id: \.key) { kv in
                            Text("\(kv.key) лет: \(String(format: "%.0f", kv.value)) $/т")
                                .font(Theme.mono(12)).foregroundStyle(Theme.muted)
                        }
                    }.card()
                }

                if let backtest {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Ретро-валидация \(backtest.startYear)–\(backtest.endYear)")
                            .font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
                        Text(String(format: "RMSE: ВВП %.2f трлн · CO₂ %.2f Гт · T %.3f°C (смещение %.3f)",
                                    backtest.gdpRmseTrillions, backtest.globalCo2RmseGtco2,
                                    backtest.temperatureRmseC, backtest.temperatureBiasC))
                            .font(Theme.mono(11)).foregroundStyle(Theme.muted)
                    }.card()
                } else {
                    Button(action: loadBacktest) {
                        Text(loadingBacktest ? "Гружу ретро-прогон…" : "Загрузить ретро-валидацию (медленно)")
                            .font(Theme.ui(12)).foregroundStyle(Theme.accent)
                    }.buttonStyle(.plain).disabled(loadingBacktest)
                }
                ErrorLine(text: error)
            }.padding(18)
        }
        .task { await loadFast() }
    }

    private func loadFast() async {
        auc = try? await app.meta("conflict_auc", as: ConflictMetaResult.self)
        scc = try? await app.meta("scc", as: SccResult.self)
    }
    private func loadBacktest() {
        loadingBacktest = true; error = nil
        Task { defer { loadingBacktest = false }
            do { backtest = try await app.meta("backtest", as: BacktestResult.self) }
            catch { self.error = "\(error)" } }
    }
}
