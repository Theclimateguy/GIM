import SwiftUI

enum RunKind: Hashable {
    case composed, whatif, play, game
}

struct ExpertView: View {
    @EnvironmentObject var app: AppState

    @State private var kind: RunKind = .composed

    // What-if
    @State private var question = "How will Hormuz tensions escalate?"
    // Composed
    @State private var scenarioBrief = ""
    @State private var shocks: [String: Double] = ["maritime": Magnitude.default]
    // Shared actor scope (what-if / composed)
    @State private var actors: Set<String> = []
    // Game
    @State private var gameBrief = "Энергетическое противостояние России и ЕС: газовое эмбарго против диверсификации поставок."
    @State private var equilibrium = true
    @State private var maxCombinations = 256
    // Play
    @State private var roundYears = 4
    @State private var ensembleSize = 3

    // Shared simulation parameters
    @State private var horizon = 5
    @State private var backgroundPolicy = "compiled-llm"
    @State private var llmRefresh = "trigger"
    @State private var seed = 2026

    private let policies = ["compiled-llm", "llm", "simple", "growth"]
    private let refreshes = ["trigger", "periodic", "never"]

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    PageHeader(
                        kicker: "Экспертный режим",
                        title: "Конфигурация прогона",
                        subtitle: "Полный пульт симулятора: выберите тип прогона, задайте возмущения и параметры — модель вернёт результат в Ситуационную комнату.")

                    SegTabs(items: [
                        (RunKind.composed, "Сценарий из шоков", "bolt.fill"),
                        (RunKind.whatif,   "Что-если",          "questionmark.bubble"),
                        (RunKind.play,     "Игра за страну",    "flag.checkered"),
                        (RunKind.game,     "Равновесие",        "circle.grid.cross"),
                    ], selection: $kind)

                    switch kind {
                    case .composed: composedConfig
                    case .whatif:   whatifConfig
                    case .play:     playConfig
                    case .game:     gameConfig
                    }

                    paramsPanel
                }
                .padding(28)
                .frame(maxWidth: 1000, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            runFooter
        }
    }

    // The primary action is pinned below the scroll so it is always reachable,
    // regardless of how long the configuration above it grows.
    private var runFooter: some View {
        VStack(spacing: 0) {
            Rectangle().fill(Theme.line).frame(height: 1)
            HStack(spacing: 14) {
                Button(action: run) {
                    Label(runTitle, systemImage: "play.fill")
                }
                .buttonStyle(PrimaryButtonStyle(enabled: canRun))
                .disabled(!canRun)

                if let e = app.runError {
                    Label(e, systemImage: "exclamationmark.triangle.fill")
                        .font(Theme.mono(11)).foregroundStyle(Theme.deltaDown)
                        .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                } else {
                    Text(reproNote).font(Theme.mono(11)).foregroundStyle(Theme.faint)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 28).padding(.vertical, 14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface)
        }
    }

    // MARK: - Per-type configuration

    private var composedConfig: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Возмущения (шоки)", icon: "bolt.fill",
                  caption: "выбрано \(shocks.count) · интенсивность 0.15–1.25") {
                ShockComposer(shocks: $shocks)
                Text("Каждый рычаг — калиброванное давление на один канал движка; интенсивность множит номинальный экспертный сдвиг.")
                    .font(Theme.ui(11)).foregroundStyle(Theme.faint).fixedSize(horizontal: false, vertical: true)
            }
            Panel(title: "Описание и охват", icon: "text.alignleft") {
                Field(label: "Краткое описание сценария", help: "Свободный текст для брифа; на расчёт влияют выбранные рычаги.") {
                    TextField("напр. энергошок плюс экспортный контроль по технологиям…", text: $scenarioBrief)
                        .textFieldStyle(.plain).inputField()
                }
                ActorPicker(actors: app.actors, selected: $actors)
            }
        }
    }

    private var whatifConfig: some View {
        Panel(title: "Вопрос и охват", icon: "questionmark.bubble") {
            Field(label: "Вопрос", help: "Свободный вопрос (англ.) — модель сама подберёт шаблон и шоки.") {
                TextField("Свободный вопрос…", text: $question)
                    .textFieldStyle(.plain).inputField()
            }
            ActorPicker(actors: app.actors, selected: $actors)
        }
    }

    private var playConfig: some View {
        VStack(alignment: .leading, spacing: 14) {
            Panel(title: "Страна и цель", icon: "flag.checkered") {
                HStack(spacing: 14) {
                    Field(label: "Страна") {
                        Picker("", selection: $app.playCountry) {
                            ForEach(app.actors) { Text($0.name).tag($0.name) }
                        }
                        .labelsHidden().pickerStyle(.menu).frame(width: 240)
                        .onChange(of: app.playCountry) { _ in Task { await app.loadDoctrine() } }
                    }
                    Field(label: "Фон") {
                        Text("прочие акторы — ИИ-автопилот").font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    }
                    Spacer()
                }
                Field(label: "Стратегическая цель", help: "Намерение игрока на горизонт раунда.") {
                    TextField("напр. занять европейский рынок газа за 5 лет", text: $app.playGoal)
                        .textFieldStyle(.plain).inputField()
                }
            }
            Panel(title: "Персона", icon: "person.crop.circle",
                  caption: "нейтральный архетип — смещает компиляцию доктрины") {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 158), spacing: 10)], spacing: 10) {
                    ForEach(app.personas) { p in
                        PersonaCard(persona: p, selected: app.playPersona == p.id) {
                            app.playPersona = p.id
                            Task { await app.loadDoctrine() }
                        }
                    }
                }
                if app.doctrineLoading {
                    HStack(spacing: 7) {
                        ProgressView().controlSize(.small).tint(Theme.accent)
                        Text("компилирую доктрину…").font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    }
                } else if !app.doctrineRows.isEmpty {
                    DoctrinePreviewView(rows: app.doctrineRows)
                }
            }
        }
    }

    private var gameConfig: some View {
        Panel(title: "Игровая постановка", icon: "circle.grid.cross") {
            Field(label: "Описание кейса", help: "Свободный текст — модель построит игру: акторы, ходы, выплаты.") {
                TextField("опишите противостояние и ставки сторон…", text: $gameBrief, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(2...4).inputField()
            }
            HStack(spacing: 24) {
                Field(label: "Поиск равновесия", help: "Итеративный поиск равновесия наилучших ответов.") {
                    Toggle("", isOn: $equilibrium).labelsHidden().toggleStyle(.switch).tint(Theme.accent)
                }
                Field(label: "Предел комбинаций", help: "Верхняя граница перебираемого пространства ходов.") {
                    Picker("", selection: $maxCombinations) {
                        ForEach([64, 128, 256, 512], id: \.self) { Text("\($0)").tag($0) }
                    }
                    .labelsHidden().pickerStyle(.menu).frame(width: 100)
                }
                Spacer()
            }
        }
    }

    // MARK: - Shared parameters

    private var paramsPanel: some View {
        Panel(title: "Параметры симуляции", icon: "slider.horizontal.3") {
            HStack(alignment: .top, spacing: 26) {
                if kind == .play {
                    param("Длина раунда, лет") {
                        Stepper("\(roundYears)", value: $roundYears, in: 1...10).fixedSize().font(Theme.ui(12))
                    }
                    param("Размер ансамбля") {
                        Stepper("\(ensembleSize)", value: $ensembleSize, in: 1...12).fixedSize().font(Theme.ui(12))
                            .help("Число стохастических прогонов в ансамбле раунда")
                    }
                } else {
                    param("Горизонт, лет") {
                        Stepper("\(horizon)", value: $horizon, in: 0...10).fixedSize().font(Theme.ui(12))
                            .help("0 — статическая оценка; >0 — динамическая симуляция по годам")
                    }
                }
                param("Фоновая политика") {
                    Picker("", selection: $backgroundPolicy) {
                        ForEach(policies, id: \.self) { Text($0).tag($0) }
                    }
                    .labelsHidden().pickerStyle(.menu).frame(width: 132)
                    .help("Как ходят не-игроки: compiled-llm — доктрина из состояния; llm — живой LLM; simple/growth — эвристики")
                }
                if kind != .game {
                    param("Обновление LLM") {
                        Picker("", selection: $llmRefresh) {
                            ForEach(refreshes, id: \.self) { Text($0).tag($0) }
                        }
                        .labelsHidden().pickerStyle(.menu).frame(width: 110)
                        .help("Когда пересчитывать доктрины: trigger — по событиям; periodic — раз в N лет; never — однократно")
                    }
                }
                param("Зерно ГСЧ") {
                    TextField("", value: $seed, format: .number.grouping(.never))
                        .textFieldStyle(.plain).frame(width: 72).inputField()
                        .help("Фиксирует воспроизводимость прогона")
                }
                Spacer(minLength: 0)
            }
        }
    }

    // MARK: - Run

    private var canRun: Bool {
        switch kind {
        case .composed: return !shocks.isEmpty
        case .whatif:   return !question.trimmingCharacters(in: .whitespaces).isEmpty
        case .play:     return !app.playPersona.isEmpty && !app.playCountry.isEmpty
        case .game:     return !gameBrief.trimmingCharacters(in: .whitespaces).isEmpty
        }
    }

    private var runTitle: String {
        switch kind {
        case .composed: return "Запустить сценарий"
        case .whatif:   return "Запустить прогон"
        case .play:     return "Запустить раунд"
        case .game:     return "Решить игру"
        }
    }

    private var reproNote: String {
        switch kind {
        case .composed: return "→ /run/composed · \(shocks.count) шок(ов), горизонт \(horizon)"
        case .whatif:   return "→ /run/whatif · горизонт \(horizon)"
        case .play:     return "→ /run/play · раунд \(roundYears) г., ансамбль \(ensembleSize)"
        case .game:     return "→ /run/game · комбинаций ≤ \(maxCombinations)\(equilibrium ? ", равновесие" : "")"
        }
    }

    private func run() {
        switch kind {
        case .composed:
            let levers = shocks.map { LeverChoice(lever: $0.key, magnitude: $0.value) }
            Task { await app.runComposed(question: scenarioBrief, levers: levers, actors: Array(actors),
                                         label: "Эксперт · Сценарий", horizon: horizon,
                                         backgroundPolicy: backgroundPolicy, llmRefresh: llmRefresh, seed: seed) }
        case .whatif:
            Task { await app.runWhatIf(question: question, actors: Array(actors),
                                       label: "Эксперт · Что-если", horizon: horizon,
                                       backgroundPolicy: backgroundPolicy, llmRefresh: llmRefresh, seed: seed) }
        case .play:
            Task { await app.runPlay(roundYears: roundYears, ensembleSize: ensembleSize, seed: seed,
                                     backgroundPolicy: backgroundPolicy) }
        case .game:
            Task { await app.runGame(description: gameBrief, label: "Эксперт · Равновесие", horizon: horizon,
                                     equilibrium: equilibrium, maxCombinations: maxCombinations,
                                     backgroundPolicy: backgroundPolicy, seed: seed) }
        }
    }

    @ViewBuilder private func param<C: View>(_ label: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(label).font(Theme.ui(11)).foregroundStyle(Theme.muted)
            content()
        }
    }
}
