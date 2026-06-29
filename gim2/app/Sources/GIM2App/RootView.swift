import SwiftUI

// v2 navigation: deterministic, validated modes ONLY. No softmax game /
// criticality / LLM-persona surface (THE-71 satisfied by construction — the
// exploratory layer is simply not built into this shell).
struct RootView: View {
    @EnvironmentObject var app: AppState
    @State private var section = 0

    private let sections = ["Ассистент", "Сценарий vs база", "Ансамбли · Доза", "Эксперт"]

    var body: some View {
        HStack(spacing: 0) {
            sidebar.frame(width: 220)
            Divider().background(Theme.line)
            Group {
                switch section {
                case 0: ChatView()
                case 1: ScenarioView()
                case 2: EnsembleDoseView()
                default: ExpertView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.bg)
        }
        .background(Theme.bg)
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 9) {
                if let glyph = Brand.glyph {
                    glyph.resizable().interpolation(.high).frame(width: 26, height: 26)
                        .clipShape(RoundedRectangle(cornerRadius: 7))  // crop the icon rim (no white edge)
                }
                Text("GIM17 v2").font(Theme.ui(15, .semibold)).foregroundStyle(Theme.text)
            }
            .padding(.horizontal, 16).padding(.vertical, 18)

            ForEach(Array(sections.enumerated()), id: \.offset) { idx, title in
                Button {
                    section = idx
                } label: {
                    Text(title)
                        .font(Theme.ui(13, section == idx ? .semibold : .regular))
                        .foregroundStyle(section == idx ? Theme.text : Theme.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 16).padding(.vertical, 10)
                        .background(section == idx ? Theme.surface : Color.clear)
                        .overlay(alignment: .leading) {
                            Rectangle().fill(section == idx ? Theme.accent : .clear).frame(width: 3)
                        }
                }
                .buttonStyle(.plain)
            }

            Spacer()

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Circle().fill(app.ready ? Theme.accent : Theme.faint).frame(width: 7, height: 7)
                    Text(app.ready ? "детерминированный режим" : "…")
                        .font(Theme.ui(10)).foregroundStyle(Theme.muted)
                }
                Text(app.status).font(Theme.ui(10)).foregroundStyle(Theme.faint)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(16)
        }
        .frame(maxHeight: .infinity)
        .background(Theme.surface2)
    }
}
