import SwiftUI

struct ExpertView: View {
    @EnvironmentObject var app: AppState
    @State private var question = "How will Hormuz tensions escalate?"
    @State private var selected: Set<String> = ["Iran", "United States", "Israel"]
    @State private var horizon = 3
    @State private var backgroundPolicy = "compiled-llm"
    @State private var llmRefresh = "trigger"
    @State private var seed = 2026

    private let policies = ["compiled-llm", "llm", "simple", "growth"]
    private let refreshes = ["trigger", "periodic", "never"]
    private let actorCols = [GridItem(.adaptive(minimum: 132), spacing: 8)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 6) {
                    SectionLabel(text: "Экспертный режим")
                    Text("Полный пульт сценария «question»").font(Theme.ui(20, .medium))
                }

                VStack(alignment: .leading, spacing: 10) {
                    fieldLabel("Вопрос", help: "Свободный вопрос — модель сама подберёт шаблон и акторов")
                    TextField("Свободный вопрос (англ.)…", text: $question)
                        .textFieldStyle(.plain).padding(12)
                        .background(Theme.surface2)
                        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                }

                VStack(alignment: .leading, spacing: 12) {
                    HStack(spacing: 8) {
                        fieldLabel("Акторы", help: "Кого включить в сценарий")
                        Text("выбрано \(selected.count)").font(Theme.ui(11)).foregroundStyle(Theme.faint)
                        Spacer()
                        Button("сбросить") { selected.removeAll() }
                            .buttonStyle(.plain).font(Theme.ui(11)).foregroundStyle(Theme.accent)
                    }
                    ScrollView {
                        LazyVGrid(columns: actorCols, alignment: .leading, spacing: 8) {
                            ForEach(app.actors) { actorChip($0) }
                        }
                        .padding(2)
                    }
                    .frame(height: 156)
                    .padding(12)
                    .background(Theme.surface2)
                    .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 9))
                }

                VStack(alignment: .leading, spacing: 14) {
                    fieldLabel("Параметры прогона", help: nil)
                    HStack(alignment: .top, spacing: 28) {
                        param("Горизонт") {
                            Stepper("\(horizon) лет", value: $horizon, in: 1...8)
                                .fixedSize().font(Theme.ui(12))
                                .help("Сколько лет симулировать через step_world")
                        }
                        param("Фоновая политика") {
                            Picker("", selection: $backgroundPolicy) {
                                ForEach(policies, id: \.self) { Text($0).tag($0) }
                            }
                            .labelsHidden().pickerStyle(.menu).fixedSize()
                            .help("Как ходят не-игроки: compiled-llm — доктрина из состояния страны; llm — живой LLM; simple/growth — эвристики")
                        }
                        param("Обновление LLM") {
                            Picker("", selection: $llmRefresh) {
                                ForEach(refreshes, id: \.self) { Text($0).tag($0) }
                            }
                            .labelsHidden().pickerStyle(.menu).fixedSize()
                            .help("Когда пересчитывать доктрины: trigger — по событиям; periodic — раз в N лет; never — однократно")
                        }
                        param("Seed") {
                            TextField("seed", value: $seed, format: .number.grouping(.never))
                                .textFieldStyle(.plain).frame(width: 70).padding(8)
                                .background(Theme.surface2)
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .help("Зерно ГСЧ — фиксирует воспроизводимость прогона")
                        }
                    }
                }

                Button {
                    Task {
                        await app.runWhatIf(question: question, actors: Array(selected),
                                            label: "Эксперт", horizon: horizon,
                                            backgroundPolicy: backgroundPolicy, llmRefresh: llmRefresh, seed: seed)
                    }
                } label: {
                    Label("Запустить", systemImage: "play.fill")
                        .font(Theme.ui(13, .medium)).foregroundStyle(Theme.accentInk)
                        .padding(.horizontal, 20).padding(.vertical, 11)
                        .background(question.trimmingCharacters(in: .whitespaces).isEmpty ? Theme.accent.opacity(0.4) : Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                }
                .buttonStyle(.plain)
                .disabled(question.trimmingCharacters(in: .whitespaces).isEmpty)
                .padding(.top, 4)
            }
            .padding(28)
            .frame(maxWidth: 780, alignment: .leading)
        }
    }

    private func actorChip(_ actor: ActorOption) -> some View {
        let on = selected.contains(actor.name)
        return Button {
            if on { selected.remove(actor.name) } else { selected.insert(actor.name) }
        } label: {
            HStack(spacing: 5) {
                Image(systemName: on ? "checkmark.circle.fill" : "circle").font(.system(size: 10))
                Text(actor.name).font(Theme.ui(11)).lineLimit(1)
            }
            .foregroundStyle(on ? Theme.accentInk : Theme.muted)
            .padding(.horizontal, 9).padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(on ? Theme.accent : Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(on ? Theme.accent : Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
        }
        .buttonStyle(.plain)
    }

    private func fieldLabel(_ text: String, help: String?) -> some View {
        HStack(spacing: 5) {
            Text(text).font(Theme.ui(12)).foregroundStyle(Theme.muted)
            if let help {
                Image(systemName: "info.circle").font(.system(size: 10)).foregroundStyle(Theme.faint).help(help)
            }
        }
    }

    @ViewBuilder private func param<C: View>(_ label: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label).font(Theme.ui(11)).foregroundStyle(Theme.muted)
            content()
        }
    }
}
