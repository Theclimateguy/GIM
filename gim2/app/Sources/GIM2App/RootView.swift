import SwiftUI

// v2 navigation: deterministic, validated modes ONLY. No softmax game /
// criticality / LLM-persona surface (THE-71 satisfied by construction — the
// exploratory layer is simply not built into this shell).
struct RootView: View {
    @EnvironmentObject var app: AppState
    @State private var section = 0
    @State private var assistantExpanded = false

    private let sections: [(title: String, icon: String)] = [
        ("Ассистент", "message"),
        ("Экспертный режим", "slider.horizontal.3"),
        ("Сравнение", "arrow.left.arrow.right"),
        ("Документация", "book"),
    ]

    var body: some View {
        HStack(spacing: 0) {
            sidebar.frame(width: 230)
            Divider().background(Theme.line)
            Group {
                switch section {
                case 0: ChatView()
                case 1: ExpertView()
                case 2: CompareView()
                default: DocsView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.bg)
        }
        .background(Theme.bg)
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                BrandMark(size: 26)
                VStack(alignment: .leading, spacing: 1) {
                    Text("GIM18").font(Theme.ui(15, .semibold)).foregroundStyle(Theme.text)
                    Text("интегрированная модель мира").font(Theme.ui(9.5)).foregroundStyle(Theme.faint)
                }
            }
            .padding(.horizontal, 16).padding(.vertical, 18)

            assistantRow
            if assistantExpanded { sessionsList }

            ForEach(Array(sections.enumerated().dropFirst()), id: \.offset) { idx, item in
                navRow(idx, item)
            }

            Spacer()

            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    Circle().fill(app.ready ? Theme.accent : Theme.faint).frame(width: 7, height: 7)
                    Text(app.ready ? "движок готов · офлайн" : "запуск движка…")
                        .font(Theme.ui(10)).foregroundStyle(Theme.muted)
                }
                let core = app.info?.engineLine ?? "18.1.1"
                let appVer = (Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String) ?? "2.1.0"
                if let url = URL(string: "https://github.com/Theclimateguy/GIM/releases/tag/v\(core)") {
                    Link(destination: url) {
                        HStack(spacing: 4) {
                            Text("Ядро: GIM \(core)").font(Theme.ui(10)).foregroundStyle(Theme.accent)
                            Image(systemName: "arrow.up.right.square")
                                .font(.system(size: 8.5)).foregroundStyle(Theme.accent.opacity(0.85))
                        }
                    }
                    .buttonStyle(.plain).help("Открыть релиз валидированного ядра на GitHub")
                }
                Text("Приложение (ПО): \(appVer)").font(Theme.ui(10)).foregroundStyle(Theme.faint)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
        }
        .frame(maxHeight: .infinity)
        .background(Theme.surface2)
    }

    // MARK: - Nav rows

    private func navRow(_ idx: Int, _ item: (title: String, icon: String)) -> some View {
        Button { section = idx } label: {
            HStack(spacing: 9) {
                Image(systemName: item.icon).font(.system(size: 12)).frame(width: 16)
                Text(item.title).font(Theme.ui(13, section == idx ? .semibold : .regular))
            }
            .foregroundStyle(section == idx ? Theme.text : Theme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16).padding(.vertical, 10)
            .background(section == idx ? Theme.surface : Color.clear)
            .overlay(alignment: .leading) {
                Rectangle().fill(section == idx ? Theme.accent : .clear).frame(width: 3)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    // "Ассистент" doubles as a disclosure control for the session list — click navigates
    // there AND toggles the history open/closed, same gesture as Claude Code's own
    // session picker (click → history drops down right below; click again → collapses).
    private var assistantRow: some View {
        Button {
            section = 0
            assistantExpanded.toggle()
        } label: {
            HStack(spacing: 9) {
                Image(systemName: "message").font(.system(size: 12)).frame(width: 16)
                Text("Ассистент").font(Theme.ui(13, section == 0 ? .semibold : .regular))
                Spacer(minLength: 0)
                Image(systemName: assistantExpanded ? "chevron.down" : "chevron.right")
                    .font(.system(size: 9)).foregroundStyle(Theme.faint)
            }
            .foregroundStyle(section == 0 ? Theme.text : Theme.muted)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 16).padding(.vertical, 10)
            .background(section == 0 ? Theme.surface : Color.clear)
            .overlay(alignment: .leading) {
                Rectangle().fill(section == 0 ? Theme.accent : .clear).frame(width: 3)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var sessionsList: some View {
        VStack(alignment: .leading, spacing: 1) {
            Button {
                app.newSession()
                section = 0
            } label: {
                HStack(spacing: 7) {
                    Image(systemName: "plus.circle.fill").font(.system(size: 11)).foregroundStyle(Theme.accent)
                    Text("Новая сессия").font(Theme.ui(12)).foregroundStyle(Theme.accent)
                }
                .padding(.leading, 30).padding(.trailing, 16).padding(.vertical, 7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)

            ForEach(app.sessions) { s in
                let active = s.id == app.currentSessionID
                Button {
                    app.selectSession(s.id)
                    section = 0
                } label: {
                    Text(s.title).font(Theme.mono(11.5, active ? .semibold : .regular)).lineLimit(1)
                        .foregroundStyle(active ? Theme.text : Theme.muted)
                        .padding(.leading, 30).padding(.trailing, 16).padding(.vertical, 6)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(active ? Theme.surface : Color.clear)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .contextMenu {
                    if app.sessions.count > 1 {
                        Button("Удалить сессию", role: .destructive) { app.deleteSession(s.id) }
                    }
                }
            }
        }
        .padding(.vertical, 4)
        .background(Theme.bg.opacity(0.35))
    }
}
