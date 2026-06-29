import SwiftUI

// Сравнение сценариев — validated baseline pinned on top, run history with
// multi-select, and a Δ matrix of terminal deltas (all values are scenario − base,
// so the base column is zero by construction).
struct CompareView: View {
    @EnvironmentObject var app: AppState
    @State private var comparing = false

    private var selectedRecords: [ScenarioRecord] {
        app.history.filter { app.compareSelection.contains($0.id) }.prefix(3).map { $0 }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack(alignment: .top, spacing: 12) {
                    PageHeader(
                        kicker: "Сравнение сценариев",
                        title: "Сравнение сценариев",
                        subtitle: "Сверху — базовый сценарий: инерционный мир без новых шоков. Все прогоны ниже измеряются как Δ к нему.")
                    Button {
                        exportReportPDF(ReportDoc(
                            date: Date(),
                            baseline: app.baselineEnsemble,
                            backtest: app.backtest,
                            auc: app.auc,
                            scc: app.scc,
                            records: selectedRecords.isEmpty ? Array(app.history.prefix(3)) : selectedRecords))
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "arrow.down.doc").font(.system(size: 12))
                            Text("Экспорт в PDF").font(Theme.ui(12.5, .medium))
                        }
                    }
                    .buttonStyle(GhostButtonStyle())
                    .help("Сохранить отчёт: базовый сценарий, валидация, сравнение прогонов")
                    .fixedSize()
                }

                baselineScenarioPanel
                baselineCharts
                trustPanel

                Panel(title: "История прогонов", icon: "clock.arrow.circlepath",
                      caption: app.history.isEmpty ? "пусто" : "\(app.history.count) · отметьте до 3") {
                    if app.history.isEmpty {
                        Text("Запустите сценарий в Экспертном режиме или задайте вопрос Ассистенту — прогоны появятся здесь.")
                            .font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        VStack(spacing: 8) { ForEach(app.history) { historyRow($0) } }
                    }
                }

                if !app.history.isEmpty {
                    HStack(spacing: 10) {
                        Button { comparing = true } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "arrow.left.arrow.right").font(.system(size: 11))
                                Text(selectedRecords.count <= 1 ? "Сравнить с базовым" : "Сравнить выбранные (\(selectedRecords.count))")
                            }
                        }
                        .buttonStyle(PrimaryButtonStyle(enabled: !selectedRecords.isEmpty))
                        .disabled(selectedRecords.isEmpty)
                        Text(selectedRecords.isEmpty
                             ? "Отметьте хотя бы один прогон — сравним его с базовым сценарием."
                             : "Один прогон сравнивается с базой; до трёх — между собой и с базой.")
                            .font(Theme.ui(11)).foregroundStyle(Theme.faint)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                if comparing, !selectedRecords.isEmpty {
                    Panel(title: "Δ к базовой линии", icon: "arrow.left.arrow.right",
                          caption: "терминальная Δ (сценарий − база) по метрикам") {
                        CompareMatrix(records: selectedRecords)
                    }
                }
            }
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .task { await app.loadValidation(); await app.loadBaselineEnsemble() }
    }

    // MARK: baseline scenario — the no-lever inertial ensemble (what we compare to)

    private let baseMetricOrder = ["world_gdp", "temperature", "co2", "mean_social_tension"]
    private func baseMetrics(_ ens: EnsembleResult) -> [FanSeries] {
        baseMetricOrder.compactMap { key in ens.projection.metrics.first { $0.metric == key } }
    }
    private func terminalText(_ fan: FanSeries) -> String {
        let v = fan.p50.last ?? 0
        return String(format: abs(v) >= 100 ? "%.0f" : "%.2f", v)
    }

    private var baselineScenarioPanel: some View {
        Panel(title: "Базовый сценарий", icon: "scope",
              caption: "инерционный мир без новых шоков · ансамбль 120 × 10 лет") {
            if let ens = app.baselineEnsemble {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Опорная траектория, относительно которой измеряется каждый сценарий (Δ = сценарий − база). Медиана и интервалы — по ансамблю приоров.")
                        .font(Theme.ui(12)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                    HStack(alignment: .top, spacing: 30) {
                        ForEach(baseMetrics(ens)) { fan in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(MetricLabel.of(fan.metric)).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                                Text(terminalText(fan)).font(Theme.mono(16, .medium)).foregroundStyle(Theme.text)
                                Text("к году \(fan.years.last ?? 0)").font(Theme.ui(10)).foregroundStyle(Theme.faint)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                }
            } else if app.baselineEnsembleLoading {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small).tint(Theme.accent)
                    Text("считаю базовый сценарий…").font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                Button("Построить базовый сценарий") { Task { await app.loadBaselineEnsemble() } }
                    .buttonStyle(GhostButtonStyle())
            }
        }
    }

    @ViewBuilder private var baselineCharts: some View {
        if let ens = app.baselineEnsemble {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 340), spacing: 14)], spacing: 14) {
                ForEach(baseMetrics(ens)) { fan in
                    ExpandableChartCard(
                        title: MetricLabel.of(fan.metric), icon: "chart.line.uptrend.xyaxis",
                        caption: "база · медиана · IQR · 5–95 · нажмите, чтобы развернуть",
                        note: "Абсолютная траектория «\(MetricLabel.of(fan.metric))» в инерционном мире без новых шоков: медиана и интервалы неопределённости по ансамблю.") { h in
                        FanChartView(fan: fan, height: h)
                    }
                }
            }
        }
    }

    // MARK: model-trust metrics (separate panel)

    private var trustPanel: some View {
        Panel(title: "Доверие к модели", icon: "checkmark.seal",
              caption: "валидированные показатели из ретро-прогонов") {
            VStack(alignment: .leading, spacing: 12) {
                if let auc = app.auc {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Относительный риск конфликта").font(Theme.ui(12, .semibold)).foregroundStyle(Theme.text)
                        AUCView(proj: auc.projection)
                    }
                }
                if app.backtest != nil || app.scc != nil {
                    HStack(alignment: .top, spacing: 32) {
                        if let b = app.backtest {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("Ретро-валидация (RMSE), \(b.startYear)–\(b.endYear)")
                                    .font(Theme.ui(11, .semibold)).foregroundStyle(Theme.muted)
                                Text(String(format: "ВВП %.2f трлн · CO₂ %.2f Гт", b.gdpRmseTrillions, b.globalCo2RmseGtco2))
                                    .font(Theme.mono(11.5)).foregroundStyle(Theme.text)
                                Text(String(format: "T %.3f°C (смещение %.3f)", b.temperatureRmseC, b.temperatureBiasC))
                                    .font(Theme.mono(11.5)).foregroundStyle(Theme.text)
                            }
                        }
                        if let scc = app.scc {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("SCC, $/тCO₂").font(Theme.ui(11, .semibold)).foregroundStyle(Theme.muted)
                                ForEach(scc.centralUsdPerTco2.sorted { (Int($0.key) ?? 0) < (Int($1.key) ?? 0) }, id: \.key) { kv in
                                    Text("\(kv.key) лет — \(String(format: "%.0f", kv.value)) $/т")
                                        .font(Theme.mono(11.5)).foregroundStyle(Theme.text)
                                }
                            }
                        }
                        Spacer(minLength: 0)
                    }
                } else {
                    Button(app.backtestLoading ? "загрузка ретро-валидации и SCC…" : "Загрузить ретро-валидацию и SCC") {
                        Task { await app.loadBacktest() }
                    }
                    .buttonStyle(GhostButtonStyle())
                    .disabled(app.backtestLoading)
                }
            }
        }
    }

    // MARK: history row

    private func historyRow(_ record: ScenarioRecord) -> some View {
        let on = app.compareSelection.contains(record.id)
        let atCap = app.compareSelection.count >= 3
        return HStack(spacing: 10) {
            Button {
                if on { app.compareSelection.removeAll { $0 == record.id } }
                else if !atCap { app.compareSelection.append(record.id) }
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: on ? "checkmark.square.fill" : "square")
                        .font(.system(size: 15)).foregroundStyle(on ? Theme.accent : Theme.faint)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(record.label).font(Theme.ui(13, .medium)).foregroundStyle(Theme.text).lineLimit(1)
                        Text(summary(record)).font(Theme.mono(11)).foregroundStyle(Theme.muted).lineLimit(1)
                    }
                    Spacer(minLength: 8)
                    Text(record.kind == "answer" ? "ассистент" : "эксперт")
                        .font(Theme.ui(10)).foregroundStyle(Theme.faint)
                        .padding(.horizontal, 7).padding(.vertical, 2)
                        .overlay(RoundedRectangle(cornerRadius: 5).stroke(Theme.line, lineWidth: 1))
                }
                .opacity(!on && atCap ? 0.5 : 1)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(!on && atCap)

            Button { exportScenarioPDF(record) } label: {
                Image(systemName: "arrow.down.doc").font(.system(size: 13)).foregroundStyle(Theme.muted)
                    .padding(.leading, 2).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .help("Экспорт сценария в PDF — полный war room (графики, каскад, страны)")
        }
        .padding(.horizontal, 12).padding(.vertical, 10)
        .background(on ? Theme.surface2 : Color.clear)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(on ? Theme.accent.opacity(0.45) : Theme.line, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }

    private func summary(_ r: ScenarioRecord) -> String {
        r.metrics.prefix(3).map { "\(MetricLabel.of($0.key)) \(fmt($0.delta))" }.joined(separator: " · ")
    }
}

private func fmt(_ d: Double) -> String { String(format: "%+.3g", d) }

// Side-by-side matrix: rows = union of metrics; columns = база (0) + each scenario.
struct CompareMatrix: View {
    let records: [ScenarioRecord]
    private let labelWidth: CGFloat = 180

    private var metricKeys: [String] {
        var seen: [String] = []
        for r in records { for m in r.metrics where !seen.contains(m.key) { seen.append(m.key) } }
        return seen
    }

    var body: some View {
        VStack(spacing: 0) {
            headerRow
            divider
            ForEach(metricKeys, id: \.self) { key in
                row(key)
                if key != metricKeys.last { divider }
            }
        }
    }

    private var headerRow: some View {
        HStack(spacing: 0) {
            Text("Метрика").font(Theme.ui(11)).foregroundStyle(Theme.faint)
                .frame(width: labelWidth, alignment: .leading)
            Text("База").font(Theme.ui(11.5, .medium)).foregroundStyle(Theme.muted)
                .frame(width: 70, alignment: .leading)
            ForEach(Array(records.enumerated()), id: \.offset) { _, r in
                Text(r.label).font(Theme.ui(11.5, .medium)).foregroundStyle(Theme.text).lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.bottom, 9)
    }

    private func row(_ key: String) -> some View {
        HStack(spacing: 0) {
            Text(MetricLabel.of(key)).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                .frame(width: labelWidth, alignment: .leading).lineLimit(1)
            Text("0").font(Theme.mono(12)).foregroundStyle(Theme.faint)
                .frame(width: 70, alignment: .leading)
            ForEach(Array(records.enumerated()), id: \.offset) { _, r in
                let v = r.delta(of: key)
                Text(v.map { fmt($0) } ?? "—")
                    .font(Theme.mono(12.5))
                    .foregroundStyle(color(v))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.vertical, 8)
    }

    private var divider: some View { Rectangle().fill(Theme.line).frame(height: 1) }

    private func color(_ v: Double?) -> Color {
        guard let v, abs(v) > 1e-9 else { return Theme.faint }
        return v > 0 ? Theme.deltaUp : Theme.deltaDown
    }
}
