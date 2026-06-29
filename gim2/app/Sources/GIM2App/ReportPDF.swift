import SwiftUI
import AppKit
import UniformTypeIdentifiers

// One-page PDF report of the current Compare state: baseline terminal metrics, model-trust
// validation, and the selected scenario deltas. Rendered on white (print look) via
// ImageRenderer and saved through an NSSavePanel.

struct ReportDoc: View {
    let date: Date
    let baseline: EnsembleResult?
    let backtest: BacktestResult?
    let auc: ConflictMetaResult?
    let scc: SccResult?
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
                Text("GIM17 — отчёт о симуляции").font(.system(size: 20, weight: .semibold)).foregroundStyle(ink)
                Text("Детерминированная модель мира · \(stamp)").font(.system(size: 10.5)).foregroundStyle(sub)
            }
            rule
            if let b = baseline {
                section("Базовый сценарий — инерционный мир, к году \(b.projection.years.last ?? 0)") {
                    baselineRows(b)
                }
            }
            section("Доверие к модели") { trustRows }
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

    @ViewBuilder private var trustRows: some View {
        VStack(alignment: .leading, spacing: 5) {
            if let b = backtest {
                line("Ретро-валидация \(b.startYear)–\(b.endYear), RMSE",
                     String(format: "ВВП %.2f трлн · CO₂ %.2f Гт · T %.3f °C",
                            b.gdpRmseTrillions, b.globalCo2RmseGtco2, b.temperatureRmseC))
            }
            if let a = auc?.projection {
                line("Относительный риск конфликта (AUC)",
                     String(format: "%.3f · 95%% ДИ [%.2f, %.2f] · p≈%.3f",
                            a.auc, a.ci95.first ?? 0, a.ci95.last ?? 0, a.pValue))
            }
            if let s = scc, !s.centralUsdPerTco2.isEmpty {
                let parts = s.centralUsdPerTco2.sorted { (Int($0.key) ?? 0) < (Int($1.key) ?? 0) }
                    .map { "\($0.key) лет — $\(Int($0.value.rounded()))" }.joined(separator: " · ")
                line("Социальная цена углерода (SCC, $/тCO₂)", parts)
            }
            if backtest == nil && auc == nil && scc == nil {
                Text("Показатели валидации не загружены — откройте «Доверие к модели» во вкладке «Сравнение».")
                    .font(.system(size: 10)).foregroundStyle(sub)
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

// Render the report to a PDF and save via NSSavePanel.
@MainActor
func exportReportPDF(_ doc: ReportDoc) {
    let renderer = ImageRenderer(content: doc)
    renderer.proposedSize = ProposedViewSize(width: 560, height: nil)
    let panel = NSSavePanel()
    panel.allowedContentTypes = [UTType.pdf]
    panel.nameFieldStringValue = "GIM17_report.pdf"
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
