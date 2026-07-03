import SwiftUI

// Shared polish components: boot splash + a themed indeterminate progress bar.

/// Slim animated progress bar (gold sliver over a graphite track) — used on the
/// splash and while the assistant computes. Theme-consistent, no system blue.
struct ProgressBarView: View {
    @State private var phase: CGFloat = 0
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.surface2)
                Capsule().fill(Theme.accent)
                    .frame(width: w * 0.35)
                    .offset(x: -w * 0.35 + phase * (w * 1.35))
            }
            .clipShape(Capsule())
            .onAppear {
                withAnimation(.easeInOut(duration: 1.15).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
        }
        .frame(height: 4)
    }
}

/// Boot splash: the app mark + a text wordmark on the app background + a progress
/// bar + status. Rendered as a clean tile + type (not the baked-background
/// `logo.png`, whose warm panel clashed with the cold app background).
struct SplashView: View {
    let status: String

    private var isError: Bool { status.lowercased().contains("ошибк") }

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            VStack(spacing: 22) {
                HStack(spacing: 16) {
                    BrandMark(size: 62)
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 0) {
                            Text("GIM").font(.system(size: 34, weight: .bold)).foregroundStyle(Theme.text)
                            Text("18").font(.system(size: 34, weight: .bold)).foregroundStyle(Theme.accent)
                        }
                        Text("DETERMINISTIC WORLD SIMULATOR")
                            .font(.system(size: 9, weight: .semibold)).tracking(2.5).foregroundStyle(Theme.accent)
                    }
                }
                if isError {
                    Text(status).font(Theme.ui(12)).foregroundStyle(Theme.deltaDown)
                        .frame(maxWidth: 420).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    ProgressBarView().frame(width: 240)
                    Text(status.isEmpty ? "запуск движка…" : status)
                        .font(Theme.mono(11)).foregroundStyle(Theme.muted)
                }
            }
            .padding(40)
        }
    }
}
