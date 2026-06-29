import SwiftUI

// Polished result view for an /run/answer payload — the v1 «Ситуационная комната»
// visual language (ring gauge + graphite/colored bars) on the validated
// deterministic outputs.
struct SituationRoom: View {
    let result: AnswerResult

    // Severity proxy: share of mapped countries in net loss (score < −0.25).
    private var severity: Double {
        let c = result.actors.geo.countries
        guard !c.isEmpty else { return 0 }
        return Double(c.filter { $0.score < -0.25 }.count) / Double(c.count)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 14) {
                SeverityRing(value: severity, size: 64)
                VStack(alignment: .leading, spacing: 4) {
                    if let a = result.archetype {
                        Text(a.nameRu).font(Theme.ui(13, .semibold)).foregroundStyle(Theme.accent)
                    }
                    Text(result.verdict).font(Theme.ui(14, .medium)).foregroundStyle(Theme.text)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }

            LazyVGrid(columns: [GridItem(.adaptive(minimum: 140), spacing: 8)], spacing: 8) {
                ForEach(result.cards) { c in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(c.label).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        Text(String(format: "%+.3g", c.deltaP50))
                            .font(Theme.mono(16, .semibold))
                            .foregroundStyle(c.lead ? Theme.accent : Theme.text)
                        Text(String(format: "[%+.2g … %+.2g]", c.p5, c.p95))
                            .font(Theme.ui(10)).foregroundStyle(Theme.faint)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .card(padding: 10)
                }
            }

            cascade

            if let t = result.threshold {
                HStack(spacing: 8) {
                    Text("Порог").font(Theme.ui(11, .semibold)).foregroundStyle(Theme.accent)
                    Text(t.note).font(Theme.ui(11)).foregroundStyle(Theme.text)
                }
                .padding(10).frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.surface2).clipShape(RoundedRectangle(cornerRadius: 8))
            }

            Text("Состояния акторов").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
            HStack(alignment: .top, spacing: 16) {
                ActorBars(title: "▲ В выигрыше", actors: result.actors.leaders, positive: true)
                ActorBars(title: "▼ В проигрыше", actors: result.actors.laggards, positive: false)
            }

            MapWebView(geo: result.actors.geo)
                .frame(height: 360)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line))

            BriefView(text: result.brief)
            TraceLine(cli: result.equivCli)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var cascade: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Каскад между доменами").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.text)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 150), spacing: 6)], alignment: .leading, spacing: 6) {
                ForEach(result.cascade.nodes) { n in
                    HStack(spacing: 5) {
                        Text(n.direction == "up" ? "▲" : n.direction == "down" ? "▼" : "■")
                            .font(Theme.ui(9)).foregroundStyle(n.direction == "flat" ? Theme.faint : Theme.accent)
                        Text(n.label).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                        Text(n.shown).font(Theme.mono(11)).foregroundStyle(Theme.text)
                    }
                    .padding(.horizontal, 8).padding(.vertical, 5)
                    .background(Theme.surface2).clipShape(RoundedRectangle(cornerRadius: 8))
                }
            }
            if !result.cascade.selectionActors.isEmpty || !result.cascade.affected.isEmpty {
                Text((result.cascade.selectionActors.isEmpty ? "" : "акторы: \(result.cascade.selectionActors.joined(separator: ", "))  ")
                     + "· сильнее всего затронуты: \(result.cascade.affected.joined(separator: ", "))")
                    .font(Theme.ui(10)).foregroundStyle(Theme.faint)
            }
        }
    }
}

// Severity gauge (0..1) — ported from v1's criticality ring.
struct SeverityRing: View {
    let value: Double
    var size: CGFloat = 64
    var body: some View {
        let lw = max(5, size * 0.09)
        ZStack {
            Circle().stroke(Theme.line, lineWidth: lw)
            Circle().trim(from: 0, to: max(0, min(1, value)))
                .stroke(Theme.ring, style: StrokeStyle(lineWidth: lw, lineCap: .round))
                .rotationEffect(.degrees(-90))
            VStack(spacing: 0) {
                Text("\(Int((value * 100).rounded()))%").font(Theme.mono(size * 0.24, .medium)).foregroundStyle(Theme.text)
                if size >= 90 { Text("в минусе").font(Theme.ui(10)).foregroundStyle(Theme.muted) }
            }
        }
        .frame(width: size, height: size)
        .help(String(format: "доля стран в минусе: %.0f%%", value * 100))
    }
}

// Winners / losers bars — ported from v1's OutcomeBars (graphite track + accent fill).
struct ActorBars: View {
    let title: String
    let actors: [ActorEntry]
    let positive: Bool

    private var maxAbs: Double { max(0.01, actors.map { abs($0.score) }.max() ?? 1) }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(title).font(Theme.ui(11, .semibold)).foregroundStyle(Theme.muted)
            ForEach(actors) { a in
                HStack(spacing: 8) {
                    Text(a.name).font(Theme.ui(12)).foregroundStyle(Theme.text)
                        .frame(width: 130, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.surface2)
                            Capsule().fill(positive ? Theme.deltaUp : Theme.deltaDown)
                                .frame(width: max(3, geo.size.width * min(1, abs(a.score) / maxAbs)))
                        }
                    }
                    .frame(height: 8)
                    Text(String(format: "%+.2f", a.score)).font(Theme.mono(11))
                        .foregroundStyle(Theme.muted).frame(width: 40, alignment: .trailing)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
