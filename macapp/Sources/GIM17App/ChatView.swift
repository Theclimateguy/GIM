import SwiftUI
import AppKit

struct ChatView: View {
    @EnvironmentObject var app: AppState
    @State private var draft = ""

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespaces).isEmpty && !app.chatStreaming
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 10) {
                SectionLabel(text: "Ассистент")
                Text(providerLabel).font(Theme.ui(11)).foregroundStyle(Theme.muted)
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.line, lineWidth: 1))
                Spacer()
                optionChip(title: "Что если", icon: "bolt.fill") { app.route = .whatif }
                optionChip(title: "Играть", icon: "play.fill") { app.route = .play }
            }
            .padding(.horizontal, 20).padding(.top, 14).padding(.bottom, 8)

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        if app.chat.isEmpty { emptyState }
                        ForEach(app.chat) { ChatRow(message: $0) }
                        if app.chatStreaming {
                            HStack(spacing: 6) {
                                ProgressView().controlSize(.small).tint(Theme.accent)
                                Text("думаю…").font(Theme.ui(12)).foregroundStyle(Theme.muted)
                            }
                        }
                        Color.clear.frame(height: 1).id("bottom")
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .onChange(of: app.chat.count) { _ in
                    withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo("bottom", anchor: .bottom) }
                }
            }

            HStack(spacing: 10) {
                TextField("Спросите ассистента…", text: $draft, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(1...4).padding(11)
                    .background(Theme.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 9))
                    .onSubmit(send)
                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill").font(.system(size: 26))
                        .foregroundStyle(canSend ? Theme.accent : Theme.faint)
                }
                .buttonStyle(.plain).disabled(!canSend)
            }
            .padding(.horizontal, 20).padding(.vertical, 12)
        }
    }

    private func send() {
        let text = draft
        draft = ""
        Task { await app.sendChat(text) }
    }

    @ViewBuilder private func optionChip(title: String, icon: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon).font(.system(size: 10))
                Text(title).font(Theme.ui(11))
            }
            .padding(.horizontal, 9).padding(.vertical, 4)
            .foregroundStyle(Theme.muted)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.line, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .help("Запустить структурированный режим — результат вернётся сюда")
    }

    private var providerLabel: String {
        switch app.llmProvider {
        case "ollama": return "локально: " + (app.llmModel.isEmpty ? "ollama" : app.llmModel)
        case "openai": return "ключ: " + (app.llmModel.isEmpty ? "openai" : app.llmModel)
        default: return "без LLM (детерминированный)"
        }
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Поговорите с моделью").font(Theme.ui(16, .medium))
            Text("Опишите сценарий — ассистент соберёт его из рычагов и прогонит. Примеры: «энергошок плюс экспортный контроль по Китаю», «что если закроют Ормуз?», «играть за Германию как технократ». Числа всегда из прогона движка. Структурированные режимы — кнопками «Что если» и «Играть» выше.")
                .font(Theme.ui(12)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
        }
        .padding(.bottom, 6)
    }
}

struct ChatRow: View {
    let message: ChatMessage

    var body: some View {
        switch message.role {
        case .user:
            // Copy button is always present (faint) — hover-gating caused it to
            // flicker out exactly as the cursor reached it, so it was unclickable.
            HStack(alignment: .center, spacing: 6) {
                Spacer(minLength: 48)
                CopyButton(text: message.text)
                Text(message.text).font(Theme.ui(13)).foregroundStyle(Theme.accentInk)
                    .textSelection(.enabled)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 11))
            }
        case .tool:
            HStack(spacing: 6) {
                Image(systemName: "gearshape").font(.system(size: 10))
                Text(message.text).font(Theme.ui(11))
            }
            .foregroundStyle(Theme.muted)
        case .assistant:
            if let r = message.result {
                AssistantResultCard(result: r)
            } else {
                HStack(alignment: .center, spacing: 6) {
                    Text(message.text).font(Theme.ui(13)).foregroundStyle(Theme.text)
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
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

/// One-click copy of any chat output or message. Shows a brief checkmark.
struct CopyButton: View {
    let text: String
    @State private var copied = false

    var body: some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(text, forType: .string)
            copied = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { copied = false }
        } label: {
            Image(systemName: copied ? "checkmark" : "doc.on.doc")
                .font(.system(size: 11))
                .foregroundStyle(copied ? Theme.accent : Theme.faint)
        }
        .buttonStyle(.plain)
        .help("Копировать")
    }
}

struct AssistantResultCard: View {
    @EnvironmentObject var app: AppState
    let result: RunResult

    private var summaryText: String {
        var lines: [String] = []
        if let v = result.verdict { lines.append(v) }
        if let c = result.criticality { lines.append(String(format: "Критичность: %.2f", c)) }
        if let o = result.outcomes, !o.isEmpty {
            lines.append("Исходы:")
            for it in o.prefix(5) {
                let pct = it.value <= 1.0 ? it.value * 100 : it.value
                lines.append(String(format: "  • %@ — %.0f%%", it.name, pct))
            }
        }
        return lines.joined(separator: "\n")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                if let c = result.criticality { CriticalityRing(value: c, size: 54) }
                Text(result.verdict ?? "—").font(Theme.ui(14, .medium))
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                CopyButton(text: summaryText)
            }
            if let o = result.outcomes, !o.isEmpty { OutcomeBars(outcomes: Array(o.prefix(4))) }
            Button { app.lastResult = result; app.route = .situation } label: {
                Label("Открыть в Ситуационной комнате", systemImage: "chart.bar.fill")
                    .font(Theme.ui(12)).foregroundStyle(Theme.accent)
            }
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

struct LLMSettingsView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    private var modelPlaceholder: String {
        app.llmProvider == "ollama" ? "qwen2.5:14b" : "gpt-4o-mini"
    }
    private var modelHelp: String {
        app.llmProvider == "ollama"
            ? "напр. qwen2.5:14b, llama3.1:8b (с поддержкой tools)"
            : "напр. gpt-4o-mini, gpt-4o; для DeepSeek — deepseek-chat"
    }
    private var baseURLPlaceholder: String { "https://api.openai.com/v1" }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Модель ассистента").font(Theme.ui(18, .medium))

            field("Провайдер", help: "deterministic — без LLM; ollama — локальная модель; OpenAI-совместимый — по ключу (OpenAI, DeepSeek и др. через Base URL)") {
                Picker("", selection: $app.llmProvider) {
                    Text("Без LLM (детерминированный)").tag("deterministic")
                    Text("Локально (Ollama)").tag("ollama")
                    Text("OpenAI-совместимый (по ключу)").tag("openai")
                }
                .labelsHidden().pickerStyle(.menu).fixedSize()
            }

            if app.llmProvider == "deterministic" {
                Text("Ассистент распознаёт базовые запросы (пресет-шоки, «играть за страну», сборку сценария по ключевым словам). Подключите Ollama или ключ — и он сможет свободно рассуждать, уточнять детали и предлагать варианты.")
                    .font(Theme.ui(12)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            } else {
                field("Модель", help: modelHelp) {
                    TextField(modelPlaceholder, text: $app.llmModel)
                        .textFieldStyle(.plain).padding(8).background(Theme.surface2)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
                if app.llmProvider == "ollama" {
                    Text("Нужен установленный Ollama и модель: ollama pull qwen2.5:14b. Полностью офлайн, бесплатно. Подсказка: берите модель с поддержкой инструментов (tools), напр. qwen2.5 / llama3.1.")
                        .font(Theme.ui(11)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                } else {
                    field("API-ключ", help: "хранится в Связке ключей macOS (Keychain), а не в открытых настройках") {
                        SecureField(app.llmProvider == "deepseek" ? "sk-… (DeepSeek)" : "sk-…", text: $app.llmApiKey)
                            .textFieldStyle(.plain).padding(8).background(Theme.surface2)
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                    field("Base URL (опц.)", help: "для совместимых хостов: DeepSeek → https://api.deepseek.com; пусто → OpenAI") {
                        TextField(baseURLPlaceholder, text: $app.llmBaseURL)
                            .textFieldStyle(.plain).padding(8).background(Theme.surface2)
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
            }

            HStack {
                Spacer()
                Button { app.saveLLM(); dismiss() } label: {
                    Text("Готово").font(Theme.ui(13, .medium)).foregroundStyle(Theme.accentInk)
                        .padding(.horizontal, 18).padding(.vertical, 9)
                        .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 9))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(24)
        .frame(width: 460)
        .background(Theme.bg)
        .foregroundStyle(Theme.text)
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
