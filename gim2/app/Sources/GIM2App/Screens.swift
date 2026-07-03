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
                    (ExpertMode.sensitivity, "Чувствительность", "tornado"),
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

// Shared: run Sensitivity/Weak signals against the plain baseline, or replay the exact lever
// recipe behind a saved Compare-tab / Assistant run instead. --------------------------------- //

private enum RunSource: Hashable {
    case baseline
    case saved(UUID)

    /// Resolves to the "id=magnitude" lever items + affected actors compute_sensitivity/
    /// compute_weak expect, or nil for the plain baseline (no lever overlay).
    func resolve(in history: [ScenarioRecord]) -> (levers: [String], actors: [String]?)? {
        guard case .saved(let id) = self, let rec = history.first(where: { $0.id == id }),
              let sel = rec.selection, !sel.levers.isEmpty else { return nil }
        return (sel.asLeverItems, sel.actors.isEmpty ? nil : sel.actors)
    }
}

private struct SourceField: View {
    @EnvironmentObject var app: AppState
    @Binding var source: RunSource
    var body: some View {
        Field(label: "Источник", help: "Прогнать поверх базы или поверх уже сыгранного сценария (Сравнение / Ассистент)") {
            Picker("", selection: $source) {
                Text("База (без сценария)").tag(RunSource.baseline)
                ForEach(app.history) { rec in Text(rec.label).tag(RunSource.saved(rec.id)) }
            }.labelsHidden().pickerStyle(.menu).frame(width: 280)
        }
    }
}

// Чувствительность --------------------------------------------------------- //

private struct SensitivityPane: View {
    @EnvironmentObject var app: AppState
    @State private var metric = "world_gdp"
    @State private var source: RunSource = .baseline
    @State private var result: SensitivityResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Скрининг параметров (Morris)", icon: "tornado",
                  caption: "какие из 33 калиброванных параметров правят выходом (Рис. 3) · до ~1 мин") {
                HStack(alignment: .top, spacing: 26) {
                    Field(label: "Метрика") {
                        Picker("", selection: $metric) {
                            ForEach(METRIC_OPTIONS, id: \.self) { Text(MetricLabel.of($0)).tag($0) }
                        }.labelsHidden().pickerStyle(.menu).frame(width: 220)
                    }
                    SourceField(source: $source)
                    Spacer(minLength: 0)
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
                    note: "Скрининг Морриса: μ* — средний модуль элементарного эффекта параметра на метрику. Чем длиннее столбец, тем сильнее параметр правит выходом."
                        + (result.selection.map { " Наложен сценарий: " + $0.levers.map { "\($0.key)=\($0.value)" }.joined(separator: ", ") } ?? ""),
                    inlineHeight: 220, fullHeight: 460) { h in
                    TornadoChartView(params: result.projection.params, height: h)
                }
                TraceLine(cli: result.equivCli)
            }
        }
    }

    private func run() {
        running = true; error = nil
        let resolved = source.resolve(in: app.history)
        Task { defer { running = false }
            do {
                result = try await app.runSensitivity(.init(
                    metric: metric, years: 10, r: 8, maxAgents: 30,
                    levers: resolved?.levers, actors: resolved?.actors))
            } catch { self.error = "\(error)" } }
    }
}

// Слабые сигналы ----------------------------------------------------------- //

private struct WeakPane: View {
    @EnvironmentObject var app: AppState
    @State private var lever = "energy_shock"
    @State private var source: RunSource = .baseline
    @State private var years = 20
    @State private var result: WeakResult?
    @State private var running = false
    @State private var error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Слабые сигналы (сценарий vs база)", icon: "waveform.path.ecg",
                  caption: "три метода раннего предупреждения на многомерной динамике состояния") {
                HStack(alignment: .top, spacing: 26) {
                    SourceField(source: $source)
                    if case .baseline = source {
                        Field(label: "Рычаг") {
                            Picker("", selection: $lever) {
                                ForEach(app.ontology?.levers ?? []) { Text($0.labelRu).tag($0.id) }
                            }.labelsHidden().pickerStyle(.menu).frame(width: 260)
                        }
                    }
                    ParamStepper(label: "Горизонт, лет", value: $years, range: 12...40)
                    Spacer(minLength: 0)
                }
                if let resolved = source.resolve(in: app.history) {
                    Text("Наложен сценарий: " + resolved.levers.joined(separator: ", "))
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                }
            }
            HStack(spacing: 14) {
                RunButton(title: "Сканировать динамику", running: running, action: run)
                ErrorLine(text: error); Spacer(minLength: 0)
            }

            if let signals = result?.weakSignals {
                if let m = signals.mahalanobis, let d2 = m.distanceSq, let anomaly = m.anomaly, let t = m.threshold {
                    ExpandableChartCard(
                        title: "Махаланобис-аномалии — \(m.nAnomalies ?? 0) из \(d2.count) шагов", icon: "waveform.path.ecg",
                        caption: "совместное отклонение состояния от базового периода · нажмите, чтобы развернуть",
                        note: "Квадрат расстояния Махаланобиса между совместным состоянием \(m.dims ?? signals.dimensions?.count ?? 0) измерений на каждом шаге и распределением первой половины траектории (с учётом ковариации между измерениями). Пунктир — порог χ² на уровне 99%; точки над ним (красные) — шаги, где система вышла в необычную область многомерного пространства состояний относительно своей же истории.",
                        inlineHeight: 170, fullHeight: 380) { h in
                        MahalanobisChartView(distanceSq: d2, anomaly: anomaly, threshold: t, height: h)
                    }
                }

                if let breaks = signals.structuralBreaks, !breaks.isEmpty {
                    Panel(title: "Структурные сдвиги по измерениям", icon: "arrow.triangle.branch",
                          caption: "вероятность смены уровня динамики (Байес, BIC-штраф) · где именно") {
                        VStack(alignment: .leading, spacing: 8) {
                            ForEach(breaks.sorted(by: { $0.value.breakProb > $1.value.breakProb }), id: \.key) { name, b in
                                BreakRow(name: name, b: b)
                            }
                        }
                    }
                }

                if let ew = signals.earlyWarning, !ew.isEmpty {
                    Panel(title: "Критическое замедление (экспериментально)", icon: "gauge.with.dots.needle.bottom.50percent",
                          caption: "рост автокорреляции + дисперсии — предвестник смены режима") {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("На одиночной детерминированной траектории тренд может отражать динамику самого сценария, а не истинное критическое замедление — метод валиден в полную силу только на стохастическом ансамбле. Читайте «есть сигнал» как повод присмотреться, не как подтверждённый диагноз.")
                                .font(Theme.ui(10.5)).foregroundStyle(Theme.faint)
                                .fixedSize(horizontal: false, vertical: true)
                            ForEach(ew.sorted(by: { abs($0.value.combined) > abs($1.value.combined) }), id: \.key) { name, w in
                                EarlyWarningRow(name: name, w: w)
                            }
                        }
                    }
                }

                if let dims = signals.dimensions, !dims.isEmpty {
                    Text("Измерения состояния: " + dims.map { MetricLabel.of($0) }.joined(separator: ", "))
                        .font(Theme.ui(10.5)).foregroundStyle(Theme.faint)
                }
            }
        }
    }

    private func run() {
        running = true; error = nil
        let resolved = source.resolve(in: app.history)
        let req = WeakRequest(levers: resolved?.levers ?? [lever], actors: resolved?.actors,
                              years: years, maxAgents: 30)
        Task { defer { running = false }
            do { result = try await app.runWeak(req) }
            catch { self.error = "\(error)" } }
    }
}

private struct BreakRow: View {
    let name: String
    let b: WeakResult.StructuralBreak
    var body: some View {
        HStack(spacing: 10) {
            Text(MetricLabel.of(name)).font(Theme.ui(12)).foregroundStyle(Theme.text)
                .frame(width: 150, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 3).fill(Theme.surface2).frame(height: 6)
                    RoundedRectangle(cornerRadius: 3)
                        .fill(b.breakProb > 0.5 ? Theme.deltaDown : Theme.accent)
                        .frame(width: max(2, geo.size.width * CGFloat(min(max(b.breakProb, 0), 1))), height: 6)
                }
            }.frame(height: 6)
            Text(String(format: "%.0f%%", b.breakProb * 100))
                .font(Theme.mono(11.5)).foregroundStyle(Theme.text).frame(width: 42, alignment: .trailing)
            Text(b.location.map { "год \($0)" } ?? "—")
                .font(Theme.mono(10.5)).foregroundStyle(Theme.faint).frame(width: 50, alignment: .trailing)
        }
    }
}

private struct EarlyWarningRow: View {
    let name: String
    let w: WeakResult.EarlyWarning
    private var arrow: String { w.combined > 0.15 ? "arrow.up.right" : (w.combined < -0.15 ? "arrow.down.right" : "arrow.right") }
    private var color: Color { w.warning ? Theme.deltaDown : Theme.muted }
    var body: some View {
        HStack(spacing: 10) {
            Text(MetricLabel.of(name)).font(Theme.ui(12)).foregroundStyle(Theme.text)
                .frame(width: 150, alignment: .leading)
            Image(systemName: arrow).font(.system(size: 11, weight: .semibold)).foregroundStyle(color)
            Text(String(format: "%.2f", w.combined)).font(Theme.mono(11.5)).foregroundStyle(Theme.text)
            if w.warning {
                Text("сигнал").font(Theme.ui(10, .semibold)).foregroundStyle(Theme.accentInk)
                    .padding(.horizontal, 7).padding(.vertical, 2)
                    .background(Theme.deltaDown).clipShape(Capsule())
            }
            Spacer(minLength: 0)
        }
    }
}
