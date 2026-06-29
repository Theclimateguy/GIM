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
        // Force the whole window dark — including the titlebar/background chrome,
        // which `environment(colorScheme:)` alone does not affect. Without this the
        // native titlebar renders light (the "white around the top-left" + the
        // loading-screen colour mismatch).
        .preferredColorScheme(.dark)
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
            case .home: ChatView()
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
            Button(action: { app.route = .chat }) {
                HStack(spacing: 8) {
                    BrandMark(size: 22)
                    Text("GIM17").font(Theme.ui(13, .medium)).foregroundStyle(Theme.text)
                }
            }
            .buttonStyle(.plain)
            .help("На главный экран — Ассистент")

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
                BrandMark(size: 60)
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

// Home, the standalone What-if/Play screens and the placeholder were retired when
// the app collapsed to three destinations: Assistant, Expert, Compare. Structured
// runs now live in Expert; results render in the Situation room.
