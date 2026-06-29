import SwiftUI

struct SituationRoomView: View {
    @EnvironmentObject var app: AppState
    private var r: RunResult? { app.lastResult }

    var body: some View {
        ScrollView {
            if let r {
                VStack(alignment: .leading, spacing: 16) {
                    HStack(spacing: 10) {
                        Button { app.route = .expert } label: {
                            Label("К конфигурации", systemImage: "chevron.left")
                        }
                        .buttonStyle(GhostButtonStyle())
                        Button { app.route = .compare } label: {
                            Label("В сравнение", systemImage: "arrow.left.arrow.right")
                        }
                        .buttonStyle(GhostButtonStyle())
                        Spacer()
                    }
                    header(r)
                    if let o = r.outcomes, !o.isEmpty {
                        VStack(alignment: .leading, spacing: 9) {
                            SectionLabel(text: "Распределение исходов")
                            OutcomeBars(outcomes: o)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .card()
                    }
                    if let dims = r.dimensions, !dims.isEmpty {
                        VStack(alignment: .leading, spacing: 10) {
                            SectionLabel(text: "Измерения — экономика · социум · климат · безопасность")
                            DimensionsView(groups: dims)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .card()
                    }
                    if let s = r.series { TrajectoryRow(series: s, years: r.years) }
                    if let d = r.drivers, !d.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            SectionLabel(text: "Главные драйверы")
                            DriversList(drivers: d)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    if let feed = r.intentsFeed, !feed.isEmpty { IntentsFeed(items: feed) }
                    if let t = r.trace { TraceLine(trace: t) }
                }
                .padding(20)
                .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                Text("Нет результата — запустите сценарий.")
                    .font(Theme.ui(13)).foregroundStyle(Theme.muted)
                    .frame(maxWidth: .infinity, maxHeight: .infinity).padding(40)
            }
        }
    }

    private func header(_ r: RunResult) -> some View {
        HStack(alignment: .center, spacing: 18) {
            VStack(alignment: .leading, spacing: 8) {
                SectionLabel(text: app.runMode.isEmpty ? "Результат" : app.runMode)
                Text(r.verdict ?? "—")
                    .font(Theme.ui(20, .medium))
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            if let c = r.criticality { CriticalityRing(value: c) }
        }
    }
}

struct TrajectoryRow: View {
    let series: SeriesBundle
    var years: [Int]? = nil
    private let cols = [GridItem(.adaptive(minimum: 175), spacing: 10)]
    @State private var detail: ChartDetail?

    var body: some View {
        LazyVGrid(columns: cols, spacing: 10) {
            if let gdp = series.gdp?.first {
                expandable(makeGDP(gdp)) {
                    trajCard("ВВП — политика vs база") {
                        VStack(spacing: 6) {
                            GDPSparkline(series: gdp)
                            HStack(spacing: 12) {
                                legend(Theme.accent, "политика")
                                legend(Theme.muted, "база")
                            }
                            .font(Theme.ui(11)).foregroundStyle(Theme.muted)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                }
            }
            if let st = series.socialTension?.first, !st.policy.isEmpty {
                expandable(makeSocial(st)) {
                    trajCard("Соц. напряжённость") { MiniSparkline(values: st.policy, color: Theme.ring) }
                }
            }
            if let e = series.prices?.energy, !e.isEmpty {
                expandable(makeEnergy(e)) {
                    trajCard("Цены: энергия") { MiniSparkline(values: e, color: Theme.accent) }
                }
            }
        }
        .sheet(item: $detail) { ChartDetailSheet(detail: $0) }
    }

    // Tap any chart card to open the full-screen detail popup.
    @ViewBuilder private func expandable<Content: View>(_ d: ChartDetail, @ViewBuilder _ content: () -> Content) -> some View {
        Button { detail = d } label: { content() }.buttonStyle(.plain)
    }

    private func makeGDP(_ g: GDPSeries) -> ChartDetail {
        ChartDetail(
            title: "ВВП — политика vs база", yLabel: "ВВП (индекс)",
            comment: "«Политика» — траектория ВВП при заданном сценарии; «база» — без вмешательства. Расхождение линий = чистый эффект сценария на выпуск.",
            lines: [
                ChartLine(name: "политика", color: Theme.accent, values: g.policy),
                ChartLine(name: "база", color: Theme.muted, values: g.baseline, dashed: true),
            ], years: years)
    }
    private func makeSocial(_ s: GDPSeries) -> ChartDetail {
        ChartDetail(
            title: "Социальная напряжённость", yLabel: "индекс",
            comment: "Индекс социальной напряжённости по годам сценария. Устойчивый рост повышает риск внутренней дестабилизации и протестной активности.",
            lines: [ChartLine(name: "напряжённость", color: Theme.ring, values: s.policy)], years: years)
    }
    private func makeEnergy(_ e: [Double]) -> ChartDetail {
        ChartDetail(
            title: "Цены на энергию", yLabel: "индекс цен",
            comment: "Динамика цен на энергию в сценарии. Скачки отражают ресурсные и морские шоки — перекрытие проливов, эмбарго, срыв поставок.",
            lines: [ChartLine(name: "энергия", color: Theme.accent, values: e)], years: years)
    }

    private func trajCard<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                SectionLabel(text: title)
                Spacer()
                Image(systemName: "arrow.up.left.and.arrow.down.right")
                    .font(.system(size: 10)).foregroundStyle(Theme.faint)
            }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(padding: 12)
    }

    private func legend(_ color: Color, _ label: String) -> some View {
        HStack(spacing: 4) {
            Rectangle().fill(color).frame(width: 14, height: 2)
            Text(label)
        }
    }
}

struct IntentsFeed: View {
    let items: [IntentFeedItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            SectionLabel(text: "Объявленные позиции → действия")
            ForEach(items) { item in
                HStack(alignment: .top, spacing: 11) {
                    Text(code(item.agentName ?? item.agentId ?? "?"))
                        .font(Theme.mono(11)).foregroundStyle(Theme.accentInk)
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 5))
                    VStack(alignment: .leading, spacing: 5) {
                        Text("\(item.agentName ?? item.agentId ?? "?") — «\(item.posture ?? "")»")
                            .font(Theme.ui(13))
                        if let acts = item.actions, !acts.isEmpty {
                            HStack(spacing: 6) {
                                ForEach(acts, id: \.self) { a in
                                    Text(a).font(Theme.mono(11)).foregroundStyle(Theme.text.opacity(0.8))
                                        .padding(.horizontal, 7).padding(.vertical, 3)
                                        .background(Theme.surface2)
                                        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line, lineWidth: 1))
                                        .clipShape(RoundedRectangle(cornerRadius: 6))
                                }
                            }
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func code(_ name: String) -> String {
        String(name.prefix(2)).uppercased()
    }
}
