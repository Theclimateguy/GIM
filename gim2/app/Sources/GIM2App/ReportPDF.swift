import SwiftUI
import AppKit
import UniformTypeIdentifiers

// One-page PDF report of the current Compare state: baseline terminal metrics and the
// selected scenario deltas. Rendered on white (print look) via ImageRenderer and saved
// through an NSSavePanel.

struct ReportDoc: View {
    let date: Date
    let baseline: EnsembleResult?
    let records: [ScenarioRecord]

    private let ink = Color(hex: 0x1A1A1A)
    private let sub = Color(hex: 0x6B6B6B)
    private let ruleC = Color(hex: 0xDADADA)
    private let up = Color(hex: 0x2E9E63)
    private let down = Color(hex: 0xC0503F)
    private let gold = Color(hex: 0xA9781F)
    private let baseOrder = ["world_gdp", "temperature", "co2", "mean_social_tension"]

    var body: some View {
        VStack(alignment: .leading, spacing: 15) {
            VStack(alignment: .leading, spacing: 2) {
                Text("GIM18 — отчёт о симуляции").font(.system(size: 20, weight: .semibold)).foregroundStyle(ink)
                Text("Детерминированная модель мира · \(stamp)").font(.system(size: 10.5)).foregroundStyle(sub)
            }
            rule
            if let b = baseline {
                section("Базовый сценарий — инерционный мир, к году \(b.projection.years.last ?? 0)") {
                    baselineRows(b)
                }
            }
            if !records.isEmpty {
                section("Сравнение прогонов · Δ = сценарий − база, терминал") { compareRows }
            }
            rule
            Text("Все числа получены прогоном валидированного движка gim-engine/2. Базовый сценарий — инерционный мир без новых шоков; каждый сценарий измеряется как отклонение (Δ) от него.")
                .font(.system(size: 8.5)).foregroundStyle(sub).fixedSize(horizontal: false, vertical: true)
        }
        .padding(30)
        .frame(width: 560, alignment: .leading)
        .background(Color.white)
    }

    private var stamp: String {
        let f = DateFormatter()
        f.dateFormat = "d MMMM yyyy, HH:mm"
        f.locale = Locale(identifier: "ru_RU")
        return f.string(from: date)
    }
    private var rule: some View { Rectangle().fill(ruleC).frame(height: 1) }

    @ViewBuilder private func section<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(.system(size: 12.5, weight: .semibold)).foregroundStyle(gold)
            content()
        }
    }

    @ViewBuilder private func baselineRows(_ ens: EnsembleResult) -> some View {
        let fans = baseOrder.compactMap { k in ens.projection.metrics.first { $0.metric == k } }
        VStack(spacing: 4) {
            ForEach(fans) { f in
                HStack {
                    Text(MetricLabel.of(f.metric)).font(.system(size: 11)).foregroundStyle(ink)
                    Spacer()
                    Text(fmtAbs(f.p50.last ?? 0)).font(.system(size: 11.5, design: .monospaced)).foregroundStyle(ink)
                }
            }
        }
    }


    @ViewBuilder private var compareRows: some View {
        let keys = orderedKeys
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                Text("Метрика").font(.system(size: 10, weight: .medium)).foregroundStyle(sub)
                    .frame(width: 150, alignment: .leading)
                ForEach(Array(records.enumerated()), id: \.offset) { _, r in
                    Text(r.label).font(.system(size: 10, weight: .medium)).foregroundStyle(ink).lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(.bottom, 5)
            ForEach(keys, id: \.self) { key in
                HStack(spacing: 0) {
                    Text(MetricLabel.of(key)).font(.system(size: 10.5)).foregroundStyle(ink)
                        .frame(width: 150, alignment: .leading).lineLimit(1)
                    ForEach(Array(records.enumerated()), id: \.offset) { _, r in
                        let v = r.metrics.first { $0.key == key }?.delta
                        Text(v.map { fmtDelta($0) } ?? "—")
                            .font(.system(size: 10.5, design: .monospaced))
                            .foregroundStyle(v == nil ? sub : (v! > 0 ? up : (v! < 0 ? down : sub)))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.vertical, 3)
                Rectangle().fill(ruleC).frame(height: 0.5)
            }
        }
    }

    private var orderedKeys: [String] {
        var seen: [String] = []
        for r in records { for m in r.metrics where !seen.contains(m.key) { seen.append(m.key) } }
        return seen
    }

    private func line(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(label).font(.system(size: 10)).foregroundStyle(sub)
            Text(value).font(.system(size: 11, design: .monospaced)).foregroundStyle(ink)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
    private func fmtAbs(_ v: Double) -> String { String(format: abs(v) >= 100 ? "%.0f" : "%.2f", v) }
    private func fmtDelta(_ v: Double) -> String { String(format: abs(v) >= 100 ? "%+.0f" : "%+.3g", v) }
}

// Generic: render any SwiftUI view to a one-page PDF at a fixed width, save via NSSavePanel.
@MainActor
func exportViewPDF<V: View>(_ view: V, name: String, width: CGFloat) {
    let renderer = ImageRenderer(content: view)
    renderer.proposedSize = ProposedViewSize(width: width, height: nil)
    let panel = NSSavePanel()
    panel.allowedContentTypes = [UTType.pdf]
    panel.nameFieldStringValue = name
    panel.canCreateDirectories = true
    panel.begin { resp in
        guard resp == .OK, let url = panel.url else { return }
        renderer.render { size, draw in
            var box = CGRect(origin: .zero, size: size)
            guard let pdf = CGContext(url as CFURL, mediaBox: &box, nil) else { return }
            pdf.beginPDFPage(nil)
            draw(pdf)
            pdf.endPDFPage()
            pdf.closePDF()
        }
    }
}

@MainActor func exportReportPDF(_ doc: ReportDoc) {
    exportViewPDF(doc, name: "GIM18_report.pdf", width: 560)
}

@MainActor func exportScenarioPDF(_ record: ScenarioRecord) {
    let safe = String(record.label.prefix(48)).replacingOccurrences(of: "/", with: "-")
    exportViewPDF(ScenarioReport(record: record), name: "GIM18_\(safe).pdf", width: 760)
}

// Full per-scenario "war room": the assistant Situation Room (sans the live map, which
// can't rasterize) or, for an Expert run, its delta fans. Dark, matching the app.
struct ScenarioReport: View {
    let record: ScenarioRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text(record.label).font(Theme.ui(17, .semibold)).foregroundStyle(Theme.text)
                Spacer(minLength: 12)
                Text("GIM18 · \(stamp)").font(Theme.ui(10)).foregroundStyle(Theme.muted)
            }
            Rectangle().fill(Theme.line).frame(height: 1)
            if let a = record.answer {
                SituationRoom(result: a, printMode: true)
            } else if let s = record.scenario {
                scenarioFans(s)
            } else {
                Text("Нет сохранённых данных прогона для отчёта.")
                    .font(Theme.ui(12)).foregroundStyle(Theme.muted)
            }
        }
        .padding(22)
        .frame(width: 760, alignment: .leading)
        .background(Theme.bg)
        .environment(\.colorScheme, .dark)
    }

    @ViewBuilder private func scenarioFans(_ s: ScenarioResult) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if !s.brief.isEmpty { BriefView(text: s.brief) }
            ForEach(s.projection.metrics) { m in
                VStack(alignment: .leading, spacing: 5) {
                    Text("Δ \(MetricLabel.of(m.metric))").font(Theme.ui(12, .semibold)).foregroundStyle(Theme.text)
                    DeltaChartView(delta: m.delta, height: 150)
                }
            }
        }
    }

    private var stamp: String {
        let f = DateFormatter()
        f.dateFormat = "d MMMM yyyy, HH:mm"
        f.locale = Locale(identifier: "ru_RU")
        return f.string(from: Date())
    }
}
