import SwiftUI

// First-launch note (once per install, see AppState.showWelcome/dismissWelcome):
// the engine gives real forecasts with zero setup (deterministic core); an LLM
// only unlocks the Assistant dialog and actor role-play — worth saying up front
// since neither is obvious from the empty Ассистент screen alone.
struct WelcomeView: View {
    // A plain closure instead of @EnvironmentObject: this sheet is presented from
    // Scene-level content (WindowGroup), where a prior version of this file relied
    // on ancestor `.environmentObject` propagation and crashed at runtime
    // (EnvironmentObject.error()) despite the object being injected correctly one
    // level up — sidestep that entirely rather than debug SwiftUI's environment
    // propagation across Scene/sheet boundaries further.
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 12) {
                Image(systemName: "globe.americas.fill")
                    .font(.system(size: 22)).foregroundStyle(Theme.accent)
                Text("Добро пожаловать в GIM18").font(Theme.ui(17, .semibold)).foregroundStyle(Theme.text)
            }

            Text("Движок работает полностью офлайн и без каких-либо ключей — сценарии, ансамбли и "
                 + "прогнозы в Экспертном режиме считаются детерминированно, локально на этой машине.")
                .font(Theme.ui(12.5)).foregroundStyle(Theme.text).fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 8) {
                bullet("Диалог с Ассистентом на естественном языке")
                bullet("«Ролевая игра акторов» в Экспертном режиме")
            }
            Text("Для этих двух возможностей нужна LLM — локальная модель через Ollama или ключ "
                 + "OpenAI-совместимого провайдера (включая DeepSeek). Подключить можно в любой момент: "
                 + "значок шестерёнки на вкладке «Ассистент».")
                .font(Theme.ui(12.5)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)

            HStack(spacing: 6) {
                Image(systemName: "book").font(.system(size: 11)).foregroundStyle(Theme.accent)
                Text("Подробнее — в разделе «Документация» (вкладка «Инструкции»).")
                    .font(Theme.ui(11.5)).foregroundStyle(Theme.faint)
                    .fixedSize(horizontal: false, vertical: true)
            }

            HStack {
                Spacer()
                Button("Понятно") { onDismiss() }
                    .buttonStyle(PrimaryButtonStyle(enabled: true))
            }
        }
        .padding(26)
        .frame(width: 440)
        .background(Theme.surface)
        .environment(\.colorScheme, .dark)
    }

    private func bullet(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text("·").font(Theme.ui(13, .semibold)).foregroundStyle(Theme.accent)
            Text(text).font(Theme.ui(12.5, .medium)).foregroundStyle(Theme.text)
        }
    }
}
