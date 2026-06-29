import SwiftUI
import Charts

// THE-67 — reusable, informative chart components for the validated projections.
// Direct answer to "flat sparklines, off-point brief": fans with IQR/5–95 bands,
// delta charts with a zero line, dose curves, Morris tornado, conflict AUC.

private struct FanPoint: Identifiable {
    let id = UUID()
    let t: Int
    let p5, p25, p50, p75, p95: Double
}

private func fanPoints(_ fan: FanSeries) -> [FanPoint] {
    let n = min(fan.years.count, fan.p50.count)
    return (0..<n).map { i in
        FanPoint(t: fan.years[i], p5: fan.p5[i], p25: fan.p25[i], p50: fan.p50[i],
                 p75: fan.p75[i], p95: fan.p95[i])
    }
}

private func darkAxes<V: View>(_ chart: V) -> some View {
    chart
        .chartXAxis { AxisMarks { AxisGridLine().foregroundStyle(Theme.line)
            AxisValueLabel().foregroundStyle(Theme.muted) } }
        .chartYAxis { AxisMarks { AxisGridLine().foregroundStyle(Theme.line)
            AxisValueLabel().foregroundStyle(Theme.muted) } }
}

/// Fan: median + IQR + 5–95 bands (Fig. 4).
struct FanChartView: View {
    let fan: FanSeries
    var color: Color = Theme.accent
    var height: CGFloat = 150
    var body: some View {
        let pts = fanPoints(fan)
        darkAxes(Chart(pts) { p in
            AreaMark(x: .value("Год", p.t), yStart: .value("p5", p.p5), yEnd: .value("p95", p.p95))
                .foregroundStyle(color.opacity(0.10))
            AreaMark(x: .value("Год", p.t), yStart: .value("p25", p.p25), yEnd: .value("p75", p.p75))
                .foregroundStyle(color.opacity(0.22))
            LineMark(x: .value("Год", p.t), y: .value("медиана", p.p50))
                .foregroundStyle(color).lineStyle(.init(lineWidth: 2))
        })
        .frame(height: height)
    }
}

/// Delta: scenario − baseline with a zero reference line (Fig. 6–9 / E6).
struct DeltaChartView: View {
    let delta: FanSeries
    var height: CGFloat = 150
    var body: some View {
        let pts = fanPoints(delta)
        darkAxes(Chart(pts) { p in
            AreaMark(x: .value("Год", p.t), yStart: .value("p5", p.p5), yEnd: .value("p95", p.p95))
                .foregroundStyle(Theme.accent.opacity(0.10))
            AreaMark(x: .value("Год", p.t), yStart: .value("p25", p.p25), yEnd: .value("p75", p.p75))
                .foregroundStyle(Theme.accent.opacity(0.20))
            LineMark(x: .value("Год", p.t), y: .value("Δ медиана", p.p50))
                .foregroundStyle(Theme.accent).lineStyle(.init(lineWidth: 2))
            RuleMark(y: .value("0", 0.0))
                .foregroundStyle(Theme.faint).lineStyle(.init(lineWidth: 1, dash: [4, 3]))
        })
        .frame(height: height)
    }
}

private struct DosePoint: Identifiable { let id = UUID(); let x: Double; let y: Double }

/// Dose-response: terminal delta vs lever magnitude (Fig. 6–9).
struct DoseChartView: View {
    let dose: DoseProjection
    var height: CGFloat = 170
    var body: some View {
        let pts = (0..<min(dose.x.count, dose.delta.count)).map { DosePoint(x: dose.x[$0], y: dose.delta[$0]) }
        darkAxes(Chart(pts) { p in
            LineMark(x: .value(dose.xLabel, p.x), y: .value(dose.yLabel, p.y))
                .foregroundStyle(Theme.accent).lineStyle(.init(lineWidth: 2))
            PointMark(x: .value(dose.xLabel, p.x), y: .value(dose.yLabel, p.y))
                .foregroundStyle(Theme.accent)
            RuleMark(y: .value("0", 0.0))
                .foregroundStyle(Theme.faint).lineStyle(.init(lineWidth: 1, dash: [4, 3]))
        })
        .frame(height: height)
    }
}

/// Morris tornado: parameter ranking (Fig. 3).
struct TornadoChartView: View {
    let params: [TornadoParam]
    var height: CGFloat? = nil
    var body: some View {
        let top = Array(params.prefix(8))
        darkAxes(Chart(top) { p in
            BarMark(x: .value("μ*", p.muStar), y: .value("параметр", p.name))
                .foregroundStyle(Theme.accent.opacity(0.85))
        })
        .frame(height: height ?? CGFloat(max(120, top.count * 26)))
    }
}

// A chart inside a Panel that expands to a full-screen sheet on click. The same
// chart view is re-rendered larger in the sheet (the `chart` closure takes a
// height), with an explanatory note. Self-contained — owns its sheet state.
struct ExpandableChartCard<C: View>: View {
    let title: String
    var icon: String? = nil
    var caption: String? = nil
    var note: String? = nil
    var inlineHeight: CGFloat = 150
    var fullHeight: CGFloat = 420
    @ViewBuilder let chart: (CGFloat) -> C
    @State private var open = false

    var body: some View {
        Panel(title: title, icon: icon, caption: caption) {
            Button { open = true } label: {
                ZStack(alignment: .topTrailing) {
                    chart(inlineHeight)
                    Image(systemName: "arrow.up.left.and.arrow.down.right")
                        .font(.system(size: 10)).foregroundStyle(Theme.faint)
                        .padding(5).background(Theme.surface.opacity(0.7))
                        .clipShape(RoundedRectangle(cornerRadius: 5))
                        .help("Открыть на весь экран")
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .sheet(isPresented: $open) {
            ChartSheet(title: title, note: note) { chart(fullHeight) }
        }
    }
}

/// Full-screen chart detail: larger chart + explanatory note, on the app bg.
struct ChartSheet<C: View>: View {
    let title: String
    var note: String? = nil
    @ViewBuilder let content: () -> C
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text(title).font(Theme.ui(18, .semibold)).foregroundStyle(Theme.text)
                Spacer()
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 18)).foregroundStyle(Theme.muted)
                }.buttonStyle(.plain).help("Закрыть")
            }
            content()
            if let note {
                Text(note).font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(24)
        .frame(minWidth: 760, minHeight: 540)
        .background(Theme.bg)
        .environment(\.colorScheme, .dark)
    }
}

/// Conflict relative-risk AUC vs the 0.5 chance line, with the 95% CI (Fig. 2b).
struct AUCView: View {
    let proj: ConflictAUCProjection
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(String(format: "AUC %.3f", proj.auc))
                    .font(Theme.mono(22, .semibold)).foregroundStyle(Theme.text)
                Text(String(format: "95%% ДИ [%.2f, %.2f] · p≈%.3f", proj.ci95.first ?? 0, proj.ci95.last ?? 0, proj.pValue))
                    .font(Theme.ui(11)).foregroundStyle(Theme.muted)
            }
            GeometryReader { geo in
                let w = geo.size.width
                let frac = max(0, min(1, (proj.auc - 0.5) / 0.5))
                let loFrac = max(0, min(1, ((proj.ci95.first ?? proj.auc) - 0.5) / 0.5))
                let hiFrac = max(0, min(1, ((proj.ci95.last ?? proj.auc) - 0.5) / 0.5))
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.surface2).frame(height: 10)
                    Capsule().fill(Theme.accent.opacity(0.25))
                        .frame(width: max(2, (hiFrac - loFrac) * w), height: 10)
                        .offset(x: loFrac * w)
                    Circle().fill(Theme.accent).frame(width: 12, height: 12)
                        .offset(x: frac * w - 6)
                }
            }
            .frame(height: 14)
            HStack {
                Text("0.5 (случайность)").font(Theme.ui(10)).foregroundStyle(Theme.faint)
                Spacer()
                Text("1.0").font(Theme.ui(10)).foregroundStyle(Theme.faint)
            }
        }
    }
}

/// Relative brief — the honest, relative readout under a scenario result.
struct BriefView: View {
    let text: String
    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Rectangle().fill(Theme.accent).frame(width: 3)
            Text(text).font(Theme.ui(12)).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 2)
    }
}

// Shared section header + monospace trace line.
struct SectionTitle: View {
    let title: String
    var subtitle: String? = nil
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(Theme.ui(15, .semibold)).foregroundStyle(Theme.text)
            if let subtitle { Text(subtitle).font(Theme.ui(11)).foregroundStyle(Theme.muted) }
        }
    }
}

struct TraceLine: View {
    let cli: String?
    var body: some View {
        if let cli {
            Text("⎘ " + cli).font(Theme.mono(10)).foregroundStyle(Theme.faint)
                .textSelection(.enabled).lineLimit(2)
        }
    }
}
