import SwiftUI
import AppKit

// «Аналитический ассистент» — chat front door (ported from v1). A question →
// /assistant (SSE) → the engine composes a grounded scenario and returns a
// Situation Room. Numbers are always engine-produced.
struct ChatView: View {
    @EnvironmentObject var app: AppState
    @State private var draft = ""
    @State private var settingsOpen = false

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespaces).isEmpty && !app.chatStreaming
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                SectionTitle(title: "Аналитический ассистент", subtitle: nil)
                Spacer()
                Text(providerLabel).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line, lineWidth: 1))
                Button { settingsOpen = true } label: {
                    Image(systemName: "gearshape").font(.system(size: 13)).foregroundStyle(Theme.muted)
                }.buttonStyle(.plain).help("Модель ассистента")
            }
            .padding(.horizontal, 20).padding(.top, 14).padding(.bottom, 8)

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        if app.chat.isEmpty { emptyState }
                        ForEach(app.chat) { ChatRow(message: $0) }
                        if app.chatStreaming {
                            VStack(alignment: .leading, spacing: 7) {
                                Text("Считаю на движке… ~15–20 с")
                                    .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                                ProgressBarView().frame(maxWidth: 320)
                            }
                            .frame(maxWidth: 360, alignment: .leading)
                            .padding(12).card(padding: 12)
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }
                    .padding(20).frame(maxWidth: .infinity, alignment: .leading)
                }
                .onChange(of: app.chat.count) { _ in
                    withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom", anchor: .bottom) }
                }
            }

            HStack(spacing: 10) {
                TextField("Опишите сценарий или вопрос…", text: $draft, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(1...12).padding(11)
                    .background(Theme.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 9))
                    .onSubmit(send)
                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill").font(.system(size: 26))
                        .foregroundStyle(canSend ? Theme.accent : Theme.faint)
                }.buttonStyle(.plain).disabled(!canSend)
            }
            .padding(.horizontal, 20).padding(.vertical, 12)
        }
        .sheet(isPresented: $settingsOpen) { LLMSettingsView() }
    }

    private func send() {
        let text = draft; draft = ""
        Task { await app.sendChat(text) }
    }

    private var providerLabel: String {
        switch app.llmProvider {
        case "ollama": return "локально: " + (app.llmModel.isEmpty ? "ollama" : app.llmModel)
        case "openai": return "ключ: " + (app.llmModel.isEmpty ? "openai" : app.llmModel)
        default: return "без LLM"
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Спросите про сценарий").font(Theme.ui(16, .medium)).foregroundStyle(Theme.text)
            Text("Опишите стратегический вопрос — ассистент соберёт сценарий из заземлённых рычагов, прогонит движок и вернёт карту ответа (вердикт, точка перелома, цепочка последствий, состояния стран). Примеры: «что если энергетическая война и санкции против крупного экспортёра?», «десятилетие стагфляции», «шок зелёного перехода». Числа — всегда из прогона.")
                .font(Theme.ui(12)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
        }.padding(.bottom, 6)
    }
}

struct ChatRow: View {
    let message: ChatMessage
    var body: some View {
        switch message.role {
        case .user:
            HStack(spacing: 6) {
                Spacer(minLength: 48)
                CopyButton(text: message.text)
                Text(message.text).font(Theme.ui(13)).foregroundStyle(Theme.accentInk)
                    .textSelection(.enabled).padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 11))
            }
        case .tool:
            HStack(spacing: 6) {
                Image(systemName: "gearshape").font(.system(size: 10))
                Text(message.text).font(Theme.ui(11))
            }.foregroundStyle(Theme.muted)
        case .assistant:
            if let r = message.result {
                SituationRoom(result: r).card()
            } else {
                HStack(alignment: .bottom, spacing: 6) {
                    Text(message.text).font(Theme.ui(13)).foregroundStyle(Theme.text)
                        .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 12).padding(.vertical, 9)
                        .background(Theme.surface)
                        .overlay(RoundedRectangle(cornerRadius: 11).stroke(Theme.line, lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 11))
                    CopyButton(text: message.text)
                    Spacer(minLength: 48)
                }
            }
        }
    }
}

struct LLMSettingsView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Модель ассистента").font(Theme.ui(18, .medium)).foregroundStyle(Theme.text)

            field("Провайдер", help: "deterministic — без LLM; ollama — локальная модель; OpenAI-совместимый — по ключу (OpenAI/DeepSeek через Base URL)") {
                Picker("", selection: $app.llmProvider) {
                    Text("Без LLM").tag("deterministic")
                    Text("Локально (Ollama)").tag("ollama")
                    Text("OpenAI-совместимый (по ключу)").tag("openai")
                }.labelsHidden().pickerStyle(.menu).fixedSize()
            }

            if app.llmProvider == "deterministic" {
                Text("Распознаёт типовые сценарии и ключевые рычаги по тексту. Подключите Ollama или ключ — и ассистент сам подберёт рычаги и уточнит детали.")
                    .font(Theme.ui(12)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            } else {
                field("Модель", help: app.llmProvider == "ollama" ? "напр. qwen2.5:14b, llama3.1:8b (tools)" : "напр. gpt-4o-mini; для DeepSeek — deepseek-chat") {
                    textField(app.llmProvider == "ollama" ? "qwen2.5:14b" : "gpt-4o-mini", text: $app.llmModel)
                }
                if app.llmProvider == "ollama" {
                    Text("Нужен установленный Ollama и модель с поддержкой tools (qwen2.5 / llama3.1). Полностью офлайн.")
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                } else {
                    field("API-ключ", help: "хранится в Связке ключей macOS (Keychain)") {
                        SecureField("sk-…", text: $app.llmApiKey)
                            .textFieldStyle(.plain).padding(8).background(Theme.surface2)
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    field("Base URL (опц.)", help: "DeepSeek → https://api.deepseek.com; пусто → OpenAI") {
                        textField("https://api.openai.com/v1", text: $app.llmBaseURL)
                    }
                }
            }

            HStack {
                Spacer()
                Button { app.saveLLM(); dismiss() } label: {
                    Text("Готово").font(Theme.ui(13, .medium)).foregroundStyle(Theme.accentInk)
                        .padding(.horizontal, 18).padding(.vertical, 9)
                        .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 9))
                }.buttonStyle(.plain)
            }
        }
        .padding(24).frame(width: 460).background(Theme.bg).foregroundStyle(Theme.text)
    }

    @ViewBuilder private func textField(_ placeholder: String, text: Binding<String>) -> some View {
        TextField(placeholder, text: text)
            .textFieldStyle(.plain).padding(8).background(Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    @ViewBuilder private func field<C: View>(_ label: String, help: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 5) {
                Text(label).font(Theme.ui(12)).foregroundStyle(Theme.muted)
                Image(systemName: "info.circle").font(.system(size: 10)).foregroundStyle(Theme.faint).help(help)
            }
            content()
        }
    }
}
