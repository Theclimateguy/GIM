import SwiftUI

// Raw agent trace for the current Assistant session: the ACTUAL system prompt sent, forced
// routing decisions (Layer 3 — see gim2.assistant.run_assistant_turn), each raw model step,
// and tool results — as opposed to what the chat renders. Exists so "did the model even see
// the hint" is answerable by reading, not re-guessing from the rendered transcript.
struct TraceView: View {
    @EnvironmentObject var app: AppState
    @Environment(\.dismiss) private var dismiss

    private let kindLabels: [String: (String, Color)] = [
        "system_prompt": ("system", Theme.muted),
        "forced_route": ("forced-route", Theme.accent),
        "model_step": ("model", Theme.text),
        "tool_result": ("tool-result", Theme.deltaUp),
        "model_reply": ("reply", Theme.text),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Трейс агента").font(Theme.ui(16, .semibold)).foregroundStyle(Theme.text)
                Spacer()
                CopyButton(text: fullTraceText)
                Button { dismiss() } label: {
                    Image(systemName: "xmark.circle.fill").font(.system(size: 16)).foregroundStyle(Theme.muted)
                }.buttonStyle(.plain)
            }
            .padding(.horizontal, 20).padding(.top, 18).padding(.bottom, 10)

            Text("Что модель реально получила и решила на каждом шаге этой сессии — system-промпт, жёсткая маршрутизация (Слой 3), сырые вызовы инструментов, ответы модели. Не то, что отрисовано в чате.")
                .font(Theme.ui(11)).foregroundStyle(Theme.faint)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 20).padding(.bottom, 10)

            Divider().background(Theme.line)

            if app.trace.isEmpty {
                VStack {
                    Spacer()
                    Text("Пока пусто — отправьте сообщение с подключённой LLM, здесь появится трейс.")
                        .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    Spacer()
                }.frame(maxWidth: .infinity)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(app.trace) { entry in
                            traceRow(entry)
                        }
                    }
                    .padding(20)
                }
            }
        }
        .frame(width: 640, height: 560)
        .background(Theme.bg)
    }

    private func traceRow(_ entry: TraceEntry) -> some View {
        let (label, color) = kindLabels[entry.kind] ?? (entry.kind, Theme.muted)
        return VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 8) {
                Text(label.uppercased()).font(Theme.mono(9.5, .semibold)).foregroundStyle(color)
                    .padding(.horizontal, 6).padding(.vertical, 2)
                    .overlay(RoundedRectangle(cornerRadius: 4).stroke(color.opacity(0.5), lineWidth: 1))
                Text(entry.timestamp, style: .time).font(Theme.mono(9.5)).foregroundStyle(Theme.faint)
            }
            Text(entry.text).font(Theme.mono(11)).foregroundStyle(Theme.text)
                .textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .background(Theme.surface)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var fullTraceText: String {
        app.trace.map { "[\($0.kind)] \($0.text)" }.joined(separator: "\n\n")
    }
}
