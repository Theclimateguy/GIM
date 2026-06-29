import SwiftUI
import Charts

// Criticality ring gauge (0..1), arc colored Theme.ring.
struct CriticalityRing: View {
    let value: Double
    var size: CGFloat = 118

    var body: some View {
        let lw = max(5, size * 0.09)   // stroke scales with size (was a fixed 10pt → too thick at 54)
        ZStack {
            Circle().stroke(Theme.line, lineWidth: lw)
            Circle()
                .trim(from: 0, to: max(0, min(1, value)))
                .stroke(Theme.ring, style: StrokeStyle(lineWidth: lw, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 1) {
                Text(String(format: "%.2f", value)).font(Theme.mono(size * 0.26, .medium)).foregroundStyle(Theme.text)
                // The word doesn't fit inside a small ring (it wrapped/overflowed on
                // the result card) — show it only on the large detail ring.
                if size >= 90 {
                    Text("критичность").font(Theme.ui(10)).foregroundStyle(Theme.muted)
                }
            }
        }
        .frame(width: size, height: size)
        .help(String(format: "критичность %.2f", value))
    }
}

// Outcome distribution — Variant 3: muted graphite ramp, gold on the lead bar.
struct OutcomeBars: View {
    let outcomes: [Outcome]

    private var sorted: [Outcome] { outcomes.sorted { $0.value > $1.value } }
    private var maxValue: Double { max(0.0001, sorted.first?.value ?? 1) }

    var body: some View {
        VStack(spacing: 9) {
            ForEach(Array(sorted.enumerated()), id: \.element.id) { idx, o in
                HStack(spacing: 10) {
                    Text(o.name).font(Theme.ui(13)).foregroundStyle(Theme.text)
                        .frame(width: 168, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.surface2)
                            Capsule().fill(color(idx))
                                .frame(width: max(3, geo.size.width * (o.value / maxValue)))
                        }
                    }
                    .frame(height: 9)
                    Text("\(Int((o.value * 100).rounded()))%")
                        .font(Theme.mono(12)).foregroundStyle(Theme.muted)
                        .frame(width: 38, alignment: .trailing)
                }
            }
        }
    }

    private func color(_ idx: Int) -> Color {
        idx == 0 ? Theme.barLead : Theme.barRamp[min(idx - 1, Theme.barRamp.count - 1)]
    }
}

// GDP sparkline: policy (solid gold) vs baseline (dashed muted).
struct GDPSparkline: View {
    let series: GDPSeries

    var body: some View {
        Chart {
            ForEach(Array(series.baseline.enumerated()), id: \.offset) { i, v in
                LineMark(x: .value("t", i), y: .value("v", v), series: .value("s", "база"))
                    .foregroundStyle(Theme.muted)
                    .lineStyle(StrokeStyle(lineWidth: 1.4, dash: [4, 3]))
            }
            ForEach(Array(series.policy.enumerated()), id: \.offset) { i, v in
                LineMark(x: .value("t", i), y: .value("v", v), series: .value("s", "политика"))
                    .foregroundStyle(Theme.accent)
                    .lineStyle(StrokeStyle(lineWidth: 2))
            }
        }
        .chartXAxis(.hidden).chartYAxis(.hidden).chartLegend(.hidden)
        .frame(height: 44)
    }
}

// Single-series sparkline.
struct MiniSparkline: View {
    let values: [Double]
    var color: Color = Theme.accent

    var body: some View {
        Chart(Array(values.enumerated()), id: \.offset) { i, v in
            LineMark(x: .value("t", i), y: .value("v", v))
                .foregroundStyle(color)
                .lineStyle(StrokeStyle(lineWidth: 2))
        }
        .chartXAxis(.hidden).chartYAxis(.hidden)
        .frame(height: 44)
    }
}

// Non-military readout: economy / society / climate / security dimensions the
// engine computes, so a scenario isn't read only through conflict risk-classes.
struct DimensionsView: View {
    let groups: [DimensionGroup]
    private let cols = [GridItem(.adaptive(minimum: 230), spacing: 14)]

    private var maxVal: Double {
        max(0.001, groups.flatMap { $0.metrics }.map { abs($0.value) }.max() ?? 1)
    }

    var body: some View {
        LazyVGrid(columns: cols, alignment: .leading, spacing: 12) {
            ForEach(groups) { group in
                VStack(alignment: .leading, spacing: 6) {
                    Text(group.group).font(Theme.ui(11, .medium)).foregroundStyle(Theme.accent)
                    ForEach(group.metrics) { m in
                        HStack(spacing: 8) {
                            Text(m.name).font(Theme.ui(12)).foregroundStyle(Theme.text)
                                .frame(width: 118, alignment: .leading).lineLimit(1)
                            GeometryReader { geo in
                                ZStack(alignment: .leading) {
                                    Capsule().fill(Theme.surface2)
                                    Capsule().fill(Theme.barRamp.first ?? Theme.muted)
                                        .frame(width: max(2, geo.size.width * min(1, abs(m.value) / maxVal)))
                                }
                            }
                            .frame(height: 6)
                            Text(String(format: "%.2f", m.value))
                                .font(Theme.mono(11)).foregroundStyle(Theme.muted)
                                .frame(width: 36, alignment: .trailing)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// One line of a detailed (expanded) chart.
struct ChartLine: Identifiable {
    let id = UUID()
    let name: String
    let color: Color
    let values: [Double]
    var dashed: Bool = false
}

// A chart shown full-size in a popup, with axes, legend and an explanatory note.
struct ChartDetail: Identifiable {
    let id = UUID()
    let title: String
    let yLabel: String
    let comment: String
    let lines: [ChartLine]
    var years: [Int]? = nil
}

// Full-screen popup chart: visible axes, legend, and a per-metric comment — the
// detail screen's sparklines are too small to read on their own.
struct ChartDetailSheet: View {
    let detail: ChartDetail
    @Environment(\.dismiss) private var dismiss

    private func xLabel(_ i: Int) -> String {
        if let ys = detail.years, i < ys.count { return String(ys[i]) }
        return "\(i)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(detail.title).font(Theme.ui(18, .medium))
                Spacer()
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 18)).foregroundStyle(Theme.muted)
                }
                .buttonStyle(.plain).help("Закрыть")
            }

            Chart {
                ForEach(detail.lines) { line in
                    ForEach(Array(line.values.enumerated()), id: \.offset) { i, v in
                        LineMark(
                            x: .value("Год", xLabel(i)),
                            y: .value(detail.yLabel, v),
                            series: .value("Серия", line.name)
                        )
                        .foregroundStyle(line.color)
                        .lineStyle(StrokeStyle(lineWidth: 2, dash: line.dashed ? [5, 3] : []))
                    }
                }
            }
            .chartYAxis { AxisMarks(position: .leading) }
            .chartXAxis { AxisMarks() }
            .chartLegend(.hidden)
            .frame(minHeight: 360)

            HStack(spacing: 16) {
                ForEach(detail.lines) { line in
                    HStack(spacing: 5) {
                        Rectangle().fill(line.color).frame(width: 16, height: 2)
                        Text(line.name).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    }
                }
                Spacer()
            }

            Text(detail.comment)
                .font(Theme.ui(13)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(24)
        .frame(minWidth: 700, minHeight: 560)
        .background(Theme.bg)
        .foregroundStyle(Theme.text)
        .environment(\.colorScheme, .dark)
    }
}

struct DriversList: View {
    let drivers: [Driver]
    private var maxValue: Double { max(0.0001, drivers.map(\.value).max() ?? 1) }

    var body: some View {
        VStack(spacing: 7) {
            ForEach(drivers) { d in
                HStack(spacing: 10) {
                    Text(d.name).font(Theme.ui(12.5)).foregroundStyle(Theme.text)
                        .frame(width: 180, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.surface2)
                            Capsule().fill(Theme.faint)
                                .frame(width: max(3, geo.size.width * (d.value / maxValue)))
                        }
                    }
                    .frame(height: 7)
                    Text(String(format: "%.2f", d.value).replacingOccurrences(of: "0.", with: "."))
                        .font(Theme.mono(11.5)).foregroundStyle(Theme.muted)
                        .frame(width: 32, alignment: .trailing)
                }
            }
        }
    }
}

struct TraceLine: View {
    let trace: Trace
    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "terminal").font(.system(size: 11))
            Text(trace.equivCli ?? "—").lineLimit(2)
        }
        .font(Theme.mono(11)).foregroundStyle(Theme.faint)
        .padding(.top, 10)
        .overlay(Rectangle().fill(Theme.line).frame(height: 1), alignment: .top)
    }
}

struct SectionLabel: View {
    let text: String
    var body: some View {
        Text(text).font(Theme.ui(12)).foregroundStyle(Theme.muted)
    }
}
