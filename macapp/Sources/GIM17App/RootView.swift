import SwiftUI

struct NavItem: Identifiable {
    let id = UUID()
    let route: Route
    let title: String
    let icon: String
}

// Three top-level destinations. "Играть" and "Что если" are no longer tabs —
// they are options launched from inside the assistant.
let navItems: [NavItem] = [
    NavItem(route: .chat, title: "Ассистент", icon: "message"),
    NavItem(route: .compare, title: "Сравнить", icon: "arrow.left.arrow.right"),
    NavItem(route: .expert, title: "Эксперт", icon: "slider.horizontal.3"),
]

struct RootView: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            VStack(spacing: 0) {
                TopBar()
                Rectangle().fill(Theme.line).frame(height: 1)
                content
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .frame(minWidth: 920, minHeight: 660)
        .foregroundStyle(Theme.text)
        .environment(\.colorScheme, .dark)
        .tint(Theme.accent)
    }

    @ViewBuilder private var content: some View {
        switch app.engineStatus {
        case .launching:
            BootView(text: "Запуск движка…", spinning: true)
        case .failed(let err):
            BootView(text: "Движок не запустился:\n\(err)", spinning: false)
        case .ready:
            switch app.route {
            case .home: HomeView()
            case .chat: ChatView()
            case .whatif: WhatIfView()
            case .play: PlaySetupView()
            case .running: RunningView()
            case .situation: SituationRoomView()
            case .compare: CompareView()
            case .expert: ExpertView()
            }
        }
    }
}

struct TopBar: View {
    @EnvironmentObject var app: AppState
    @State private var showSettings = false

    var body: some View {
        HStack(spacing: 12) {
            Button(action: { app.route = .home }) {
                HStack(spacing: 8) {
                    if let icon = Brand.appIcon {
                        icon.resizable().interpolation(.high).frame(width: 22, height: 22)
                            .clipShape(RoundedRectangle(cornerRadius: 5))
                    }
                    Text("GIM17").font(Theme.ui(13, .medium)).foregroundStyle(Theme.text)
                }
            }
            .buttonStyle(.plain)

            Spacer()

            HStack(spacing: 2) {
                ForEach(navItems) { item in
                    let active = app.route == item.route
                    Button(action: { app.route = item.route }) {
                        HStack(spacing: 6) {
                            Image(systemName: item.icon).font(.system(size: 11))
                            Text(item.title).font(Theme.ui(12))
                        }
                        .padding(.horizontal, 9).padding(.vertical, 5)
                        .background(active ? Theme.accent : Color.clear)
                        .foregroundStyle(active ? Theme.accentInk : Theme.muted)
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(3)
            .background(Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))

            Spacer()

            StatusChip()
            Button { showSettings = true } label: {
                Image(systemName: "gearshape").font(.system(size: 14)).foregroundStyle(Theme.muted)
            }
            .buttonStyle(.plain).help("Настройки модели ассистента")
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(Theme.surface)
        .sheet(isPresented: $showSettings) { LLMSettingsView().environmentObject(app) }
    }
}

struct StatusChip: View {
    @EnvironmentObject var app: AppState

    var body: some View {
        HStack(spacing: 7) {
            Circle().fill(dotColor).frame(width: 8, height: 8)
            Text(label).font(Theme.ui(12)).foregroundStyle(Theme.muted)
        }
        .padding(.horizontal, 9).padding(.vertical, 5)
        .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.line, lineWidth: 1))
    }

    private var dotColor: Color {
        switch app.engineStatus {
        case .launching: return Theme.accent
        case .ready: return Color(hex: 0x28C840)
        case .failed: return Color(hex: 0xFF5F57)
        }
    }
    private var label: String {
        switch app.engineStatus {
        case .launching: return "запуск"
        case .ready: return "движок готов"
        case .failed: return "ошибка"
        }
    }
}

struct RunningBar: View {
    @State private var animate = false
    private let trackWidth: CGFloat = 240
    private let segWidth: CGFloat = 84

    var body: some View {
        ZStack(alignment: .leading) {
            Capsule().fill(Theme.line).frame(width: trackWidth, height: 3)
            Capsule()
                .fill(LinearGradient(
                    colors: [Theme.accent.opacity(0.15), Theme.accent, Theme.accent.opacity(0.15)],
                    startPoint: .leading, endPoint: .trailing))
                .frame(width: segWidth, height: 3)
                .offset(x: animate ? trackWidth - segWidth : 0)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true)) { animate = true }
        }
    }
}

struct BootView: View {
    let text: String
    let spinning: Bool

    var body: some View {
        VStack(spacing: 22) {
            HStack(spacing: 14) {
                if let icon = Brand.appIcon {
                    icon.resizable().interpolation(.high).frame(width: 60, height: 60)
                        .clipShape(RoundedRectangle(cornerRadius: 13))
                }
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 0) {
                        Text("GIM").font(.system(size: 32, weight: .bold)).foregroundStyle(Theme.text)
                        Text("17").font(.system(size: 32, weight: .bold)).foregroundStyle(Theme.accent)
                    }
                    Text("INTEGRATED WORLD SIMULATOR")
                        .font(.system(size: 9, weight: .semibold)).tracking(2.5).foregroundStyle(Theme.accent)
                }
            }
            if spinning {
                RunningBar()
            } else {
                Image(systemName: "exclamationmark.triangle").font(.system(size: 28)).foregroundStyle(Theme.deltaDown)
            }
            Text(text)
                .font(Theme.mono(12))
                .foregroundStyle(Theme.muted)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 560)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

struct HomeView: View {
    @EnvironmentObject var app: AppState

    private let columns = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Глобальная интегрированная модель · v17.2.0")
                    .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                Text("Как будем работать?").font(Theme.ui(20, .medium))

                LazyVGrid(columns: columns, spacing: 12) {
                    PathCard(route: .chat, icon: "message", title: "Ассистент",
                             desc: "Опишите задачу словами — ассистент соберёт сценарий, прогонит его и предложит варианты. Здесь же «что если» и игра за страну.",
                             featured: true)
                    PathCard(route: .expert, icon: "slider.horizontal.3", title: "Экспертный режим",
                             desc: "Полный пульт: все рычаги, state-CSV, рантайм-флаги, прямой контроль над прогоном.")
                }
                .frame(maxWidth: 640)

                Text("\(app.actors.count) акторов · \(app.personas.count) персон · мир загружен")
                    .font(Theme.mono(11)).foregroundStyle(Theme.faint)
                    .padding(.top, 4)
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct PathCard: View {
    @EnvironmentObject var app: AppState
    let route: Route
    let icon: String
    let title: String
    let desc: String
    var featured: Bool = false

    var body: some View {
        Button(action: { app.route = route }) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Image(systemName: icon).font(.system(size: 26)).foregroundStyle(Theme.accent)
                    Spacer()
                    if featured {
                        Text("флагман").font(Theme.ui(10))
                            .foregroundStyle(Theme.accentInk)
                            .padding(.horizontal, 7).padding(.vertical, 2)
                            .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 5))
                    }
                }
                Spacer(minLength: 6)
                Text(title).font(Theme.ui(16, .medium))
                Text(desc).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, minHeight: 150, alignment: .topLeading)
            .padding(18)
            .background(Theme.surface)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(featured ? Theme.accent : Theme.line, lineWidth: featured ? 2 : 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
    }
}

struct PlaceholderView: View {
    @EnvironmentObject var app: AppState
    let title: String
    let icon: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 30)).foregroundStyle(Theme.accent)
            Text(title).font(Theme.ui(18, .medium))
            Text("экран в работе").font(Theme.ui(12)).foregroundStyle(Theme.muted)
            Button(action: { app.route = .home }) {
                Text("← на главную").font(Theme.ui(12)).foregroundStyle(Theme.accent)
            }
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
