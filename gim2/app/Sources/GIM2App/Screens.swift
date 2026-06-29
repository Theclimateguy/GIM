import SwiftUI

// Экспертный режим — one console over the validated deterministic modes:
// сценарий vs база / ансамбли / дозовая кривая / чувствительность / слабые сигналы.
// (Replaces the former Сценарий + Ансамбли·Доза + Эксперт sidebar sections.)

private let METRIC_OPTIONS = ["world_gdp", "temperature", "co2", "mean_social_tension"]

enum ExpertMode: Hashable { case scenario, ensemble, dose, sensitivity, weak }

// Shared atoms ------------------------------------------------------------- //

struct Chip: View {
    let text: String
    let on: Bool
    let tap: () -> Void
    var body: some View {
        Text(text)
            .font(Theme.ui(12, on ? .semibold : .regular))
            .padding(.horizontal, 10).padding(.vertical, 7)
            .frame(maxWidth: .infinity, minHeight: 42, alignment: .leading)
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
    var enabled: Bool = true
    var body: some View {
        Button(action: action) {
            HStack(spacing: 7) {
                if running { ProgressView().controlSize(.small).tint(Theme.accentInk) }
                Text(running ? "Выполняется…" : title)
            }
        }
        .buttonStyle(PrimaryButtonStyle(enabled: enabled && !running))
        .disabled(running || !enabled)
    }
}

struct ErrorLine: View {
    let text: String?
    var body: some View {
        if let text {
            Label(text, systemImage: "exclamationmark.triangle.fill")
                .font(Theme.mono(11)).foregroundStyle(Theme.deltaDown)
                .lineLimit(3).fixedSize(horizontal: false, vertical: true)
        }
    }
}

// A small fixed-width labeled stepper used across the params panels.
private struct ParamStepper: View {
    let label: String
    @Binding var value: Int
    let range: ClosedRange<Int>
    var step: Int = 1
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label).font(Theme.ui(11)).foregroundStyle(Theme.muted)
            Stepper("\(value)", value: $value, in: range, step: step).fixedSize().font(Theme.ui(12))
        }
    }
}

// Console ------------------------------------------------------------------ //

struct ExpertView: View {
    @State private var mode: ExpertMode = .scenario

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PageHeader(
                    kicker: "Экспертный режим",
                    title: "Конфигурация прогона",
                    subtitle: "Полный пульт движка. Все выходы относительны: сценарий измеряется как Δ к валидированной базовой линии.")

                SegTabs(items: [
                    (ExpertMode.scenario,    "Сценарий", "bolt.fill"),
                    (ExpertMode.ensemble,    "Ансамбли", "chart.line.uptrend.xyaxis"),
                    (ExpertMode.dose,        "Отклик",   "function"),
                    (ExpertMode.sensitivity, "Чувствит.", "tornado"),
                    (ExpertMode.weak,        "Сигналы",  "waveform.path.ecg"),
                ], selection: $mode)

                switch mode {
                case .scenario:    ScenarioPane()
                case .ensemble:    EnsemblePane()
                case .dose:        DosePane()
                case .sensitivity: SensitivityPane()
                case .weak:        WeakPane()
                }
            }
            .padding(28)
            .frame(maxWidth: 1040, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// Сценарий vs база --------------------------------------------------------- //

private struct ScenarioPane: View {
    @EnvironmentObject var app: AppState
    @State private var selected: Set<String> = ["decarbonization"]
    @State private var actors: Set<String> = []
    @State private var magnitude: Double = 0.6
    @State private var horizon: Int = 10
    @State private var members: Int = 120
    @State private var result: ScenarioResult?
    @State private var running = false
    @State private var error: String?

    private let leverCols = [GridItem(.adaptive(minimum: 178), spacing: 8)]
    private var needsActors: Bool {
        (app.ontology?.levers ?? []).contains { selected.contains($0.id) && $0.needsActors }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Рычаги сценария", icon: "bolt.fill",
                  caption: "выбрано \(selected.count) · заземлённые каналы движка") {
                if let levers = app.ontology?.levers {
                    LazyVGrid(columns: leverCols, alignment: .leading, spacing: 8) {
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
                if needsActors {
                    ActorPicker(actors: app.ontology?.actors ?? [], selected: $actors)
                }
            }

            Panel(title: "Параметры", icon: "slider.horizontal.3") {
                HStack(alignment: .top, spacing: 26) {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Интенсивность").font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        SliderControl(value: $magnitude, range: 0.15...1.25).frame(width: 220)
                    }
                    ParamStepper(label: "Горизонт, лет", value: $horizon, range: 3...30)
                    ParamStepper(label: "Членов ансамбля", value: $members, range: 40...500, step: 40)
                    Spacer(minLength: 0)
                }
            }

            HStack(spacing: 14) {
                RunButton(title: "Прогнать сценарий", running: running, action: run, enabled: !selected.isEmpty)
                ErrorLine(text: error)
                Spacer(minLength: 0)
            }

            if let result {
                Panel(title: "Аналитическая записка", icon: "text.alignleft") {
                    BriefView(text: result.brief)
                }
                ForEach(result.projection.metrics) { m in
                    ExpandableChartCard(
                        title: "Δ \(MetricLabel.of(m.metric))", icon: "chart.xyaxis.line",
                        caption: "сценарий − база, 5–95 / IQR / медиана · нажмите, чтобы развернуть",
                        note: "Отклонение «\(MetricLabel.of(m.metric))» от базовой траектории по годам: медиана с интервалами 25–75 и 5–95 по ансамблю. Пунктир — нулевая линия (нет эффекта).") { h in
                        DeltaChartView(delta: m.delta, height: h)
                    }
                }
                TraceLine(cli: result.equivCli)
            }
        }
    }

    private func run() {
        running = true; error = nil
        let req = ScenarioRequest(levers: Array(selected), magnitude: magnitude,
                                  actors: actors.isEmpty ? nil : Array(actors), members: members,
                                  years: horizon, maxAgents: 57)
        Task {
            defer { running = false }
            do {
                let r = try await app.runScenario(req)
                result = r
                let names = (app.ontology?.levers ?? []).filter { selected.contains($0.id) }.map { $0.labelRu }
                app.record(ScenarioRecord(scenario: r, label: "Сценарий: " + names.joined(separator: " + ")))
            } catch { self.error = "\(error)" }
        }
    }
}

// Ансамбли ----------------------------------------------------------------- //

private struct EnsemblePane: View {
    @EnvironmentObject var app: AppState
    @State private var members = 200
    @State private var years = 10
    @State private var result: EnsembleResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Параметры ансамбля", icon: "chart.line.uptrend.xyaxis",
                  caption: "медиана / IQR / 5–95 по приорам (Рис. 4)") {
                HStack(alignment: .top, spacing: 26) {
                    ParamStepper(label: "Членов", value: $members, range: 40...500, step: 40)
                    ParamStepper(label: "Годы", value: $years, range: 5...20)
                    Spacer(minLength: 0)
                }
            }
            HStack(spacing: 14) {
                RunButton(title: "Прогнать ансамбль", running: running, action: run)
                ErrorLine(text: error); Spacer(minLength: 0)
            }
            if let result {
                ForEach(result.projection.metrics) { fan in
                    ExpandableChartCard(
                        title: MetricLabel.of(fan.metric), icon: "chart.line.uptrend.xyaxis",
                        caption: "медиана · IQR · 5–95 · нажмите, чтобы развернуть",
                        note: "Ансамблевый веер «\(MetricLabel.of(fan.metric))»: медианная траектория с интервалами неопределённости (25–75 и 5–95 перцентили по приорам).") { h in
                        FanChartView(fan: fan, height: h)
                    }
                }
                TraceLine(cli: result.equivCli)
            }
        }
    }

    private func run() {
        running = true; error = nil
        let req = EnsembleRequest(members: members, years: years, maxAgents: 57, seed: 2026, priorSet: "key")
        Task { defer { running = false }
            do { result = try await app.runEnsemble(req) } catch { self.error = "\(error)" } }
    }
}

// Дозовая кривая ----------------------------------------------------------- //

private struct DosePane: View {
    @EnvironmentObject var app: AppState
    @State private var lever = "growth"
    @State private var metric = "world_gdp"
    @State private var result: DoseResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Кривая отклика", icon: "function",
                  caption: "как итог меняется с ростом силы рычага") {
                HStack(alignment: .top, spacing: 26) {
                    Field(label: "Рычаг") {
                        Picker("", selection: $lever) {
                            ForEach(app.ontology?.levers ?? []) { Text($0.labelRu).tag($0.id) }
                        }.labelsHidden().pickerStyle(.menu).frame(width: 240)
                    }
                    Field(label: "Метрика") {
                        Picker("", selection: $metric) {
                            ForEach(METRIC_OPTIONS, id: \.self) { Text(MetricLabel.of($0)).tag($0) }
                        }.labelsHidden().pickerStyle(.menu).frame(width: 200)
                    }
                    Spacer(minLength: 0)
                }
            }
            HStack(spacing: 14) {
                RunButton(title: "Построить кривую", running: running, action: run)
                ErrorLine(text: error); Spacer(minLength: 0)
            }
            if let result {
                ExpandableChartCard(
                    title: "\(result.lever) → Δ \(MetricLabel.of(result.projection.metric))", icon: "function",
                    caption: String(format: "база (терминал): %.4g · нажмите, чтобы развернуть", result.projection.baseline),
                    note: "Терминальная Δ метрики при росте величины рычага. Ненулевой наклон означает, что рычаг реально двигает выход модели.",
                    inlineHeight: 170, fullHeight: 440) { h in
                    DoseChartView(dose: result.projection, height: h)
                }
                TraceLine(cli: result.equivCli)
            }
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

// Чувствительность --------------------------------------------------------- //

private struct SensitivityPane: View {
    @EnvironmentObject var app: AppState
    @State private var metric = "world_gdp"
    @State private var result: SensitivityResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Скрининг параметров (Morris)", icon: "tornado",
                  caption: "какие параметры правят выходом (Рис. 3)") {
                Field(label: "Метрика") {
                    Picker("", selection: $metric) {
                        ForEach(METRIC_OPTIONS, id: \.self) { Text(MetricLabel.of($0)).tag($0) }
                    }.labelsHidden().pickerStyle(.menu).frame(width: 220)
                }
            }
            HStack(spacing: 14) {
                RunButton(title: "Запустить скрининг", running: running, action: run)
                ErrorLine(text: error); Spacer(minLength: 0)
            }
            if let result {
                ExpandableChartCard(
                    title: "μ* по \(MetricLabel.of(result.metric))", icon: "tornado",
                    caption: "Morris · топ-параметры · нажмите, чтобы развернуть",
                    note: "Скрининг Морриса: μ* — средний модуль элементарного эффекта параметра на метрику. Чем длиннее столбец, тем сильнее параметр правит выходом.",
                    inlineHeight: 220, fullHeight: 460) { h in
                    TornadoChartView(params: result.projection.params, height: h)
                }
                TraceLine(cli: result.equivCli)
            }
        }
    }

    private func run() {
        running = true; error = nil
        Task { defer { running = false }
            do { result = try await app.runSensitivity(.init(metric: metric, years: 10, r: 8, maxAgents: 30)) }
            catch { self.error = "\(error)" } }
    }
}

// Слабые сигналы ----------------------------------------------------------- //

private struct WeakPane: View {
    @EnvironmentObject var app: AppState
    @State private var lever = "energy_shock"
    @State private var result: WeakResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Слабые сигналы (сценарий vs база)", icon: "waveform.path.ecg",
                  caption: "Махаланобис-аномалии в динамике состояния") {
                Field(label: "Рычаг") {
                    Picker("", selection: $lever) {
                        ForEach(app.ontology?.levers ?? []) { Text($0.labelRu).tag($0.id) }
                    }.labelsHidden().pickerStyle(.menu).frame(width: 260)
                }
            }
            HStack(spacing: 14) {
                RunButton(title: "Сканировать динамику", running: running, action: run)
                ErrorLine(text: error); Spacer(minLength: 0)
            }
            if let m = result?.weakSignals.mahalanobis {
                Panel(title: "Аномалии: \(m.nAnomalies ?? 0) шагов", icon: "waveform.path.ecg") {
                    if let t = m.threshold {
                        Text(String(format: "порог χ²: %.2f", t)).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    }
                    if let d = result?.weakSignals.dimensions {
                        Text("измерения: " + d.joined(separator: ", "))
                            .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                    }
                    Text("Вероятность разладки и критическое замедление — в сыром payload weak_signals.")
                        .font(Theme.ui(10.5)).foregroundStyle(Theme.faint)
                }
            }
        }
    }

    private func run() {
        running = true; error = nil
        Task { defer { running = false }
            do { result = try await app.runWeak(WeakRequest(levers: [lever], years: 12, maxAgents: 30)) }
            catch { self.error = "\(error)" } }
    }
}
