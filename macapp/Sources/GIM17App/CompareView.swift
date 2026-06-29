import SwiftUI

struct CompareView: View {
    @EnvironmentObject var app: AppState

    // Scenarios chosen for the matrix, in history order, capped for layout.
    private var selectedRecords: [RunRecord] {
        app.history.filter { app.compareSelection.contains($0.id) }.prefix(3).map { $0 }
    }
    // The comparison columns: validated baseline first (if computed), then picks.
    private var columns: [RunRecord] {
        (app.baseline.map { [$0] } ?? []) + selectedRecords
    }
    private var canCompare: Bool {
        (app.baseline != nil && !selectedRecords.isEmpty) || selectedRecords.count >= 2
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PageHeader(
                    kicker: "Сравнение сценариев",
                    title: "Сравнение сценариев",
                    subtitle: "Сверху закреплена валидированная базовая линия. Отметьте прогоны из истории, чтобы сопоставить их между собой и с базой.")

                baselinePanel

                Panel(title: "История прогонов", icon: "clock.arrow.circlepath",
                      caption: app.history.isEmpty ? "пусто" : "\(app.history.count) · отметьте до 3") {
                    if app.history.isEmpty {
                        Text("Запустите сценарий в Ассистенте или Экспертном режиме — прогоны появятся здесь.")
                            .font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(app.history) { historyRow($0) }
                        }
                    }
                }

                if canCompare {
                    Panel(title: "Δ к базовой линии", icon: "arrow.left.arrow.right",
                          caption: "проценты — доля исхода; Δ — пункты к первой колонке") {
                        ComparisonMatrix(columns: columns)
                    }
                } else if !app.history.isEmpty {
                    Text("Отметьте \(app.baseline == nil ? "минимум два прогона" : "хотя бы один прогон") для сопоставления.")
                        .font(Theme.ui(12)).foregroundStyle(Theme.faint)
                }
            }
            .padding(28)
            .frame(maxWidth: 1000, alignment: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .onAppear { Task { await app.loadBaseline() } }
    }

    // MARK: - Pinned baseline

    private var baselinePanel: some View {
        Panel(title: "Базовая линия", icon: "scope",
              caption: "референсная траектория без новых шоков") {
            if let b = app.baseline {
                ScenarioSummary(record: b, badge: "база")
            } else if app.baselineLoading {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small).tint(Theme.accent)
                    Text("строю базовую линию…").font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                Button("Построить базовую линию") { Task { await app.loadBaseline() } }
                    .buttonStyle(GhostButtonStyle())
            }
        }
    }

    // MARK: - History row

    private func historyRow(_ record: RunRecord) -> some View {
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
                    Text(topOutcomeLine(record)).font(Theme.ui(11)).foregroundStyle(Theme.muted).lineLimit(1)
                }
                Spacer(minLength: 8)
                Text(String(format: "крит %.2f", record.result.criticality ?? 0))
                    .font(Theme.mono(11.5)).foregroundStyle(Theme.muted)
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

    private func topOutcomeLine(_ record: RunRecord) -> String {
        let top = (record.result.outcomes ?? []).sorted { $0.value > $1.value }.prefix(2)
        return top.map { "\($0.name) \(Int(($0.value * 100).rounded()))%" }.joined(separator: " · ")
    }
}

// A compact one-row summary of a single run: ring + verdict + top outcomes.
struct ScenarioSummary: View {
    let record: RunRecord
    var badge: String? = nil
    private var top: [Outcome] { Array((record.result.outcomes ?? []).sorted { $0.value > $1.value }.prefix(3)) }

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            CriticalityRing(value: record.result.criticality ?? 0, size: 52)
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    if let badge {
                        Text(badge).font(Theme.ui(10, .semibold)).foregroundStyle(Theme.accentInk)
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 5))
                    }
                    Text(record.label).font(Theme.ui(13, .medium)).foregroundStyle(Theme.text).lineLimit(1)
                }
                if let v = record.result.verdict {
                    Text(v).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 14) {
                    ForEach(top) { o in
                        HStack(spacing: 5) {
                            Text(o.name).font(Theme.ui(11)).foregroundStyle(Theme.muted).lineLimit(1)
                            Text("\(Int((o.value * 100).rounded()))%").font(Theme.mono(11)).foregroundStyle(Theme.text)
                        }
                    }
                }
            }
            Spacer(minLength: 0)
        }
    }
}

// Side-by-side matrix: rows = criticality + union of top outcomes; columns =
// each scenario. Δ is computed against the first column (the baseline if present).
struct ComparisonMatrix: View {
    let columns: [RunRecord]
    private let labelWidth: CGFloat = 156

    private var outcomeNames: [String] {
        var seen: [String: Double] = [:]
        for col in columns {
            for o in col.result.outcomes ?? [] {
                seen[o.name] = max(seen[o.name] ?? 0, o.value)
            }
        }
        return seen.sorted { $0.value > $1.value }.prefix(6).map { $0.key }
    }

    var body: some View {
        VStack(spacing: 0) {
            headerRow
            divider
            metricRow(name: "Критичность", values: columns.map { $0.result.criticality ?? 0 },
                      format: { String(format: "%.2f", $0) }, deltaScale: 1)
            ForEach(outcomeNames, id: \.self) { name in
                divider
                metricRow(name: name, values: columns.map { value(of: name, in: $0) },
                          format: { "\(Int(($0 * 100).rounded()))%" }, deltaScale: 100)
            }
        }
    }

    private var headerRow: some View {
        HStack(spacing: 0) {
            Text("").frame(width: labelWidth, alignment: .leading)
            ForEach(Array(columns.enumerated()), id: \.offset) { idx, col in
                VStack(alignment: .leading, spacing: 3) {
                    Text(col.label).font(Theme.ui(11.5, .medium)).foregroundStyle(Theme.text).lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                    if idx == 0 { Text("опорная").font(Theme.ui(9.5)).foregroundStyle(Theme.faint) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.bottom, 9)
    }

    private func metricRow(name: String, values: [Double],
                           format: @escaping (Double) -> String, deltaScale: Double) -> some View {
        let base = values.first ?? 0
        return HStack(spacing: 0) {
            Text(name).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                .frame(width: labelWidth, alignment: .leading).lineLimit(1)
            ForEach(Array(values.enumerated()), id: \.offset) { idx, v in
                HStack(spacing: 7) {
                    Text(format(v)).font(Theme.mono(12.5)).foregroundStyle(Theme.text)
                    if idx > 0 {
                        let d = (v - base) * deltaScale
                        Text(deltaLabel(d, pp: deltaScale > 1))
                            .font(Theme.mono(10.5))
                            .foregroundStyle(abs(d) < 0.5 ? Theme.faint : (d > 0 ? Theme.deltaDown : Theme.accent))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.vertical, 8)
    }

    private var divider: some View { Rectangle().fill(Theme.line).frame(height: 1) }

    private func value(of name: String, in record: RunRecord) -> Double {
        record.result.outcomes?.first { $0.name == name }?.value ?? 0
    }

    private func deltaLabel(_ d: Double, pp: Bool) -> String {
        if abs(d) < (pp ? 0.5 : 0.005) { return "—" }
        let sign = d > 0 ? "+" : "−"
        return pp ? "\(sign)\(Int(abs(d).rounded()))пп" : "\(sign)\(String(format: "%.2f", abs(d)))"
    }
}
