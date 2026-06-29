import SwiftUI

// Сравнение сценариев — validated baseline pinned on top, run history with
// multi-select, and a Δ matrix of terminal deltas (all values are scenario − base,
// so the base column is zero by construction).
struct CompareView: View {
    @EnvironmentObject var app: AppState

    private var selectedRecords: [ScenarioRecord] {
        app.history.filter { app.compareSelection.contains($0.id) }.prefix(3).map { $0 }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PageHeader(
                    kicker: "Сравнение сценариев",
                    title: "Сравнение сценариев",
                    subtitle: "Сверху — валидированная базовая линия модели. Отметьте прогоны из истории, чтобы сопоставить их Δ к базе между собой.")

                baselinePanel

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

                if selectedRecords.count >= 2 {
                    Panel(title: "Δ к базовой линии", icon: "arrow.left.arrow.right",
                          caption: "терминальная Δ (сценарий − база) по метрикам") {
                        CompareMatrix(records: selectedRecords)
                    }
                } else if !app.history.isEmpty {
                    Text("Отметьте минимум два прогона для сопоставления.")
                        .font(Theme.ui(12)).foregroundStyle(Theme.faint)
                }
            }
            .padding(28)
            .frame(maxWidth: 1040, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .task { await app.loadValidation() }
    }

    // MARK: pinned validated baseline (model-trust metrics)

    private var baselinePanel: some View {
        Panel(title: "Базовая линия (валидированная)", icon: "checkmark.seal",
              caption: "опорная траектория модели — из ретро-прогонов") {
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
                Text("Сценарии ниже измеряются как отклонение от этой базы.")
                    .font(Theme.ui(11)).foregroundStyle(Theme.faint)
            }
        }
    }

    // MARK: history row

    private func historyRow(_ record: ScenarioRecord) -> some View {
        let on = app.compareSelection.contains(record.id)
        let atCap = app.compareSelection.count >= 3
        return Button {
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
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(on ? Theme.surface2 : Color.clear)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(on ? Theme.accent.opacity(0.45) : Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
            .opacity(!on && atCap ? 0.5 : 1)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!on && atCap)
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
