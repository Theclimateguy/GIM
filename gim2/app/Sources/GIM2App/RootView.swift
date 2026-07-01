import SwiftUI

// v2 navigation: deterministic, validated modes ONLY. No softmax game /
// criticality / LLM-persona surface (THE-71 satisfied by construction — the
// exploratory layer is simply not built into this shell).
struct RootView: View {
    @EnvironmentObject var app: AppState
    @State private var section = 0

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

            ForEach(Array(sections.enumerated()), id: \.offset) { idx, item in
                Button {
                    section = idx
                } label: {
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

            Spacer()

            VStack(alignment: .leading, spacing: 5) {
                HStack(spacing: 6) {
                    Circle().fill(app.ready ? Theme.accent : Theme.faint).frame(width: 7, height: 7)
                    Text(app.ready ? "движок готов · офлайн" : "запуск движка…")
                        .font(Theme.ui(10)).foregroundStyle(Theme.muted)
                }
                let core = app.info?.engineLine ?? "18.0.0"
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
}
