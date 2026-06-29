import SwiftUI

struct WhatIfPreset: Identifiable {
    let id = UUID()
    let title: String
    let question: String
    let actors: [String]
}

let whatIfPresets: [WhatIfPreset] = [
    .init(title: "Ормуз — закрытие пролива",
          question: "How will Hormuz tensions escalate?",
          actors: ["Iran", "United States", "Israel"]),
    .init(title: "Тайвань — блокада",
          question: "Will a Taiwan blockade escalate?",
          actors: ["China", "United States"]),
    .init(title: "Санкционная спираль",
          question: "Will the sanctions spiral deepen?",
          actors: ["Russia", "United States", "Germany"]),
]

struct WhatIfView: View {
    @EnvironmentObject var app: AppState
    @State private var question: String = ""
    private let cols = [GridItem(.adaptive(minimum: 220), spacing: 10)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SectionLabel(text: "Что если…")
                Text("Заданный шок или свободный вопрос").font(Theme.ui(20, .medium))

                LazyVGrid(columns: cols, spacing: 10) {
                    ForEach(whatIfPresets) { p in
                        Button {
                            Task { await app.runWhatIf(question: p.question, actors: p.actors, label: "Что если · \(p.title)") }
                        } label: {
                            HStack(spacing: 10) {
                                Image(systemName: "bolt.fill").foregroundStyle(Theme.accent)
                                Text(p.title).font(Theme.ui(13, .medium)).foregroundStyle(Theme.text)
                                    .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                                Spacer(minLength: 0)
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, minHeight: 60, alignment: .leading)
                            .background(Theme.surface)
                            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }

                VStack(alignment: .leading, spacing: 8) {
                    SectionLabel(text: "…или свой вопрос")
                    HStack(spacing: 10) {
                        TextField("Свободный вопрос (англ.)…", text: $question)
                            .textFieldStyle(.plain)
                            .padding(10)
                            .background(Theme.surface2)
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        Button {
                            Task { await app.runWhatIf(question: question, actors: [], label: "Что если") }
                        } label: {
                            Text("Запустить").font(Theme.ui(13, .medium)).foregroundStyle(Theme.accentInk)
                                .padding(.horizontal, 16).padding(.vertical, 10)
                                .background(Theme.accent).clipShape(RoundedRectangle(cornerRadius: 9))
                        }
                        .buttonStyle(.plain)
                        .disabled(question.trimmingCharacters(in: .whitespaces).isEmpty)
                        .opacity(question.trimmingCharacters(in: .whitespaces).isEmpty ? 0.5 : 1)
                    }
                }
                .card()

                if let e = app.runError {
                    Text(e).font(Theme.mono(11)).foregroundStyle(Theme.deltaDown)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct RunningView: View {
    @EnvironmentObject var app: AppState
    private let phases = ["база", "внеш.политика", "санкции", "ресурсы", "экономика", "миграция", "сверка", "кредит"]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionLabel(text: app.runMode.isEmpty ? "Идёт расчёт" : app.runMode)
            let pct = app.progress?.percent ?? 0
            let step = app.progress?.stepIndex ?? 0
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text("\(pct)%").font(Theme.mono(24, .medium)).foregroundStyle(Theme.accent)
                    Text(app.progress?.message ?? "запуск…").font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    Spacer()
                    Button { Task { await app.cancelRun() } } label: {
                        Label("Отменить", systemImage: "xmark")
                            .font(Theme.ui(12)).foregroundStyle(Theme.text)
                            .padding(.horizontal, 11).padding(.vertical, 5)
                            .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.line, lineWidth: 1))
                    }
                    .buttonStyle(.plain)
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Theme.surface2)
                        Capsule().fill(Theme.accent).frame(width: geo.size.width * Double(pct) / 100.0)
                    }
                }
                .frame(height: 8)
                HStack(spacing: 2) {
                    ForEach(Array(phases.enumerated()), id: \.offset) { i, name in
                        Text(name).font(.system(size: 10))
                            .foregroundStyle(i + 1 == step ? Theme.accent : (i + 1 < step ? Theme.muted : Theme.faint))
                            .frame(maxWidth: .infinity)
                    }
                }
            }
            .card()
            if !app.streamedIntents.isEmpty {
                ScrollView { IntentsFeed(items: app.streamedIntents).padding(.top, 4) }
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }
}
