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

// Adaptive numeric format for hover read-outs: more decimals for small magnitudes.
private func fanFmt(_ v: Double) -> String {
    let a = abs(v)
    if a >= 100 { return String(format: "%.0f", v) }
    if a >= 10  { return String(format: "%.1f", v) }
    if a >= 1   { return String(format: "%.2f", v) }
    return String(format: "%.3f", v)
}

// Bulletproof uncertainty band: a single closed polygon (upper edge left→right, then
// lower edge right→left). Drawn in .chartBackground via the chart proxy, so — unlike a
// range AreaMark, which self-intersects into the herringbone "ёлочка" on this Charts
// version — it is geometrically guaranteed continuous.
private func bandShape(_ pts: [FanPoint], _ low: KeyPath<FanPoint, Double>,
                       _ high: KeyPath<FanPoint, Double>, _ proxy: ChartProxy, _ frame: CGRect) -> Path {
    var path = Path()
    func pt(_ t: Int, _ v: Double) -> CGPoint? {
        guard let x = proxy.position(forX: t), let y = proxy.position(forY: v) else { return nil }
        return CGPoint(x: frame.minX + x, y: frame.minY + y)
    }
    let upper = pts.compactMap { pt($0.t, $0[keyPath: high]) }
    let lower = pts.reversed().compactMap { pt($0.t, $0[keyPath: low]) }
    guard let start = upper.first else { return path }
    path.move(to: start)
    upper.dropFirst().forEach { path.addLine(to: $0) }
    lower.forEach { path.addLine(to: $0) }
    path.closeSubpath()
    return path
}

// Hover read-out for the banded charts: a vertical guide, a median marker, and a
// tooltip with the year and the value on both axes (median + 5–95 range). Pure
// chartOverlay so it composes onto any fan/delta Chart without touching its marks.
private struct FanHover: ViewModifier {
    let pts: [FanPoint]
    var unit: String = ""
    var color: Color = Theme.accent
    var deltaPrefix: Bool = false
    @State private var hit: FanPoint? = nil

    func body(content: Content) -> some View {
        content.chartOverlay { proxy in
            GeometryReader { geo in
                let frame = geo[proxy.plotAreaFrame]
                if frame.width > 0 {
                    ZStack(alignment: .topLeading) {
                        Rectangle().fill(Color.clear).contentShape(Rectangle())
                            .onContinuousHover { phase in
                                switch phase {
                                case .active(let p):
                                    let dx = p.x - frame.minX
                                    if dx >= 0, dx <= frame.width, let xv: Double = proxy.value(atX: dx) {
                                        hit = pts.min(by: { abs(Double($0.t) - xv) < abs(Double($1.t) - xv) })
                                    } else { hit = nil }
                                case .ended:
                                    hit = nil
                                }
                            }
                        if let h = hit, let px = proxy.position(forX: h.t), let py = proxy.position(forY: h.p50) {
                            let gx = frame.minX + px
                            Rectangle().fill(Theme.muted.opacity(0.45))
                                .frame(width: 1, height: frame.height)
                                .position(x: gx, y: frame.midY)
                            Circle().fill(color).frame(width: 7, height: 7)
                                .overlay(Circle().stroke(Theme.bg, lineWidth: 1.5))
                                .position(x: gx, y: frame.minY + py)
                            tip(h)
                                .position(x: min(max(gx, frame.minX + 54), frame.maxX - 54),
                                          y: frame.minY + 22)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder private func tip(_ h: FanPoint) -> some View {
        let pfx = deltaPrefix ? "Δ " : ""
        let suffix = unit.isEmpty ? "" : " " + unit
        VStack(alignment: .leading, spacing: 1) {
            Text("год \(h.t)").font(Theme.ui(9.5)).foregroundStyle(Theme.muted)
            Text(pfx + fanFmt(h.p50) + suffix).font(Theme.mono(12, .semibold)).foregroundStyle(Theme.text)
            Text(fanFmt(h.p5) + " – " + fanFmt(h.p95)).font(Theme.mono(9.5)).foregroundStyle(Theme.faint)
        }
        .padding(.vertical, 4).padding(.horizontal, 7)
        .background(RoundedRectangle(cornerRadius: 6).fill(Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line, lineWidth: 1)))
        .fixedSize()
    }
}

private extension View {
    func fanHover(_ pts: [FanPoint], unit: String = "", color: Color = Theme.accent,
                  deltaPrefix: Bool = false) -> some View {
        modifier(FanHover(pts: pts, unit: unit, color: color, deltaPrefix: deltaPrefix))
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
    var unit: String = ""
    var body: some View {
        let pts = fanPoints(fan)
        let yLo = pts.map(\.p5).min() ?? 0
        let yHi = pts.map(\.p95).max() ?? 1
        let pad = max((yHi - yLo) * 0.08, 1e-9)
        // Only the median LineMark lives in the Chart; the 5–95 / 25–75 bands are drawn as
        // explicit closed polygons in .chartBackground (bandShape) because range AreaMarks
        // render as a self-crossing "ёлочка" here. The y-scale is widened to the 5–95 span.
        darkAxes(
            Chart(pts) { p in
                LineMark(x: .value("Год", p.t), y: .value("медиана", p.p50))
                    .foregroundStyle(color).lineStyle(.init(lineWidth: 2))
                    .interpolationMethod(.monotone)
            }
            .chartYScale(domain: (yLo - pad)...(yHi + pad))
            .chartBackground { proxy in
                GeometryReader { geo in
                    let f = geo[proxy.plotAreaFrame]
                    ZStack {
                        bandShape(pts, \.p5, \.p95, proxy, f).fill(color.opacity(0.12))
                        bandShape(pts, \.p25, \.p75, proxy, f).fill(color.opacity(0.22))
                    }
                }
            }
        )
        .fanHover(pts, unit: unit, color: color)
        .frame(height: height)
    }
}

/// Delta: scenario − baseline with a zero reference line (Fig. 6–9 / E6).
struct DeltaChartView: View {
    let delta: FanSeries
    var height: CGFloat = 150
    var unit: String = ""
    var body: some View {
        let pts = fanPoints(delta)
        let yLo = min(0, pts.map(\.p5).min() ?? 0)
        let yHi = max(0, pts.map(\.p95).max() ?? 0)
        let pad = max((yHi - yLo) * 0.08, 1e-9)
        darkAxes(
            Chart(pts) { p in
                LineMark(x: .value("Год", p.t), y: .value("Δ медиана", p.p50))
                    .foregroundStyle(Theme.accent).lineStyle(.init(lineWidth: 2))
                    .interpolationMethod(.monotone)
                RuleMark(y: .value("0", 0.0))
                    .foregroundStyle(Theme.faint).lineStyle(.init(lineWidth: 1, dash: [4, 3]))
            }
            .chartYScale(domain: (yLo - pad)...(yHi + pad))
            .chartBackground { proxy in
                GeometryReader { geo in
                    let f = geo[proxy.plotAreaFrame]
                    ZStack {
                        bandShape(pts, \.p5, \.p95, proxy, f).fill(Theme.accent.opacity(0.12))
                        bandShape(pts, \.p25, \.p75, proxy, f).fill(Theme.accent.opacity(0.22))
                    }
                }
            }
        )
        .fanHover(pts, unit: unit, color: Theme.accent, deltaPrefix: true)
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
        // Expand affordance lives in the Panel title row (trailing) — it used to overlay
        // the chart's top-right corner and collide with the y-axis labels there.
        Panel(title: title, icon: icon, caption: caption, trailing: AnyView(expandButton)) {
            Button { open = true } label: {
                chart(inlineHeight).contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .sheet(isPresented: $open) {
            ChartSheet(title: title, note: note) { chart(fullHeight) }
        }
    }

    private var expandButton: some View {
        Button { open = true } label: {
            Image(systemName: "arrow.up.left.and.arrow.down.right")
                .font(.system(size: 11)).foregroundStyle(Theme.faint)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain).help("Открыть на весь экран")
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
