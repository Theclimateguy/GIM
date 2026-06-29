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

/// Boot splash: the wordmark logo on the app background + a progress bar + status.
struct SplashView: View {
    let status: String

    private var isError: Bool { status.lowercased().contains("ошибк") }

    var body: some View {
        ZStack {
            Theme.bg.ignoresSafeArea()
            VStack(spacing: 24) {
                if let logo = Brand.logo {
                    logo.resizable().scaledToFit().frame(maxWidth: 380)
                } else {
                    Text("GIM17 v2").font(Theme.ui(34, .bold)).foregroundStyle(Theme.text)
                }
                if isError {
                    Text(status).font(Theme.ui(12)).foregroundStyle(Theme.deltaDown)
                        .frame(maxWidth: 420).multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    ProgressBarView().frame(width: 240)
                    Text(status.isEmpty ? "запуск движка…" : status)
                        .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                }
            }
            .padding(40)
        }
    }
}
