import SwiftUI

struct CompareView: View {
    @EnvironmentObject var app: AppState
    private var records: [RunRecord] { Array(app.history.prefix(3)) }
    private let cols = [GridItem(.adaptive(minimum: 200), spacing: 10)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SectionLabel(text: "Сравнить")
                Text("Последние прогоны рядом").font(Theme.ui(20, .medium))

                if records.count < 2 {
                    Text("Запустите минимум два сценария («Что если» или «Играть»), чтобы сравнить.")
                        .font(Theme.ui(13)).foregroundStyle(Theme.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, 8)
                } else {
                    LazyVGrid(columns: cols, spacing: 10) {
                        ForEach(records) { CompareCard(record: $0) }
                    }
                    DiffLine(b: records[0], a: records[1])
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct CompareCard: View {
    let record: RunRecord
    private var top: [Outcome] { Array((record.result.outcomes ?? []).sorted { $0.value > $1.value }.prefix(3)) }
    private var maxValue: Double { max(0.0001, top.first?.value ?? 1) }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                CriticalityRing(value: record.result.criticality ?? 0, size: 46)
                VStack(alignment: .leading, spacing: 2) {
                    Text(record.label).font(Theme.ui(13, .medium)).lineLimit(2)
                    Text("крит \(String(format: "%.2f", record.result.criticality ?? 0))")
                        .font(Theme.mono(11)).foregroundStyle(Theme.muted)
                }
            }
            ForEach(Array(top.enumerated()), id: \.element.id) { idx, o in
                HStack(spacing: 8) {
                    Text(o.name).font(Theme.ui(11)).frame(width: 90, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.surface2)
                            Capsule().fill(idx == 0 ? Theme.barLead : Theme.barRamp[min(idx - 1, Theme.barRamp.count - 1)])
                                .frame(width: max(2, geo.size.width * (o.value / maxValue)))
                        }
                    }
                    .frame(height: 7)
                    Text("\(Int((o.value * 100).rounded()))").font(Theme.mono(11)).foregroundStyle(Theme.muted)
                        .frame(width: 22, alignment: .trailing)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(padding: 13)
    }
}

struct DiffLine: View {
    let b: RunRecord
    let a: RunRecord

    private var critDelta: Double { (b.result.criticality ?? 0) - (a.result.criticality ?? 0) }
    private var outcomeShifts: [(name: String, delta: Double)] {
        let av = Dictionary((a.result.outcomes ?? []).map { ($0.name, $0.value) }, uniquingKeysWith: { x, _ in x })
        let bv = Dictionary((b.result.outcomes ?? []).map { ($0.name, $0.value) }, uniquingKeysWith: { x, _ in x })
        let names = Set(av.keys).union(bv.keys)
        var shifts: [(name: String, delta: Double)] = []
        for n in names {
            let delta: Double = (bv[n] ?? 0) - (av[n] ?? 0)
            shifts.append((name: n, delta: delta))
        }
        shifts.sort { abs($0.delta) > abs($1.delta) }
        return Array(shifts.prefix(2))
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionLabel(text: "Ключевой trade-off · \(b.label) vs \(a.label)")
            HStack(spacing: 14) {
                metric("критичность", critDelta)
                ForEach(outcomeShifts, id: \.name) { s in
                    metric(s.name, s.delta, asPP: true)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }

    private func metric(_ label: String, _ delta: Double, asPP: Bool = false) -> some View {
        let value = asPP ? "\(delta >= 0 ? "+" : "−")\(Int((abs(delta) * 100).rounded())) пп" : "\(delta >= 0 ? "+" : "−")\(String(format: "%.2f", abs(delta)))"
        return HStack(spacing: 6) {
            Text(label).font(Theme.ui(12)).foregroundStyle(Theme.muted).lineLimit(1)
            Text(value).font(Theme.mono(12))
                .foregroundStyle(delta >= 0 ? Theme.deltaDown : Theme.accent)
        }
    }
}
