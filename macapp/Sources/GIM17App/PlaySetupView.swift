import SwiftUI

struct PlaySetupView: View {
    @EnvironmentObject var app: AppState
    private let personaCols = [GridItem(.adaptive(minimum: 150), spacing: 10)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                SectionLabel(text: "Играть за страну")

                HStack(spacing: 10) {
                    Picker("", selection: $app.playCountry) {
                        ForEach(app.actors) { actor in
                            Text(actor.name).tag(actor.name)
                        }
                    }
                    .labelsHidden()
                    .frame(maxWidth: 260)
                    .help("Страна, за которую вы играете")
                    Text("противники — ИИ-автопилот (compiled-llm)")
                        .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                    Spacer()
                }
                .onChange(of: app.playCountry) { _ in
                    Task { await app.loadDoctrine() }
                }

                SectionLabel(text: "Персона — нейтральный архетип (смещает компиляцию доктрины)")
                LazyVGrid(columns: personaCols, spacing: 10) {
                    ForEach(app.personas) { p in
                        PersonaCard(persona: p, selected: app.playPersona == p.id) {
                            app.playPersona = p.id
                            Task { await app.loadDoctrine() }
                        }
                    }
                }

                HStack(spacing: 10) {
                    Text("Цель").font(Theme.ui(12)).foregroundStyle(Theme.muted).frame(width: 40, alignment: .leading)
                    TextField("Например: занять европейский рынок газа за 5 лет", text: $app.playGoal)
                        .textFieldStyle(.plain)
                        .padding(9)
                        .background(Theme.surface2)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }

                if app.doctrineLoading {
                    HStack { ProgressView().controlSize(.small).tint(Theme.accent); Text("компилирую доктрину…").font(Theme.ui(12)).foregroundStyle(Theme.muted) }
                } else if !app.doctrineRows.isEmpty {
                    DoctrinePreviewView(rows: app.doctrineRows)
                } else if !app.playPersona.isEmpty {
                    Text("Доктрина для этой страны недоступна.")
                        .font(Theme.ui(12)).foregroundStyle(Theme.deltaDown)
                }

                Button {
                    Task { await app.runPlay() }
                } label: {
                    Label("Запустить раунд · 4 года", systemImage: "play.fill")
                        .font(Theme.ui(13, .medium)).foregroundStyle(Theme.accentInk)
                        .padding(.horizontal, 16).padding(.vertical, 10)
                        .background(app.playPersona.isEmpty ? Theme.accent.opacity(0.4) : Theme.accent)
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                }
                .buttonStyle(.plain)
                .disabled(app.playPersona.isEmpty)
            }
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

struct PersonaCard: View {
    let persona: Persona
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 6) {
                Image(systemName: icon).font(.system(size: 18))
                    .foregroundStyle(selected ? Theme.accent : Theme.muted)
                Text(persona.name.current).font(Theme.ui(13, .medium)).foregroundStyle(Theme.text)
                if let t = persona.tagline?.current, !t.isEmpty {
                    Text(t).font(Theme.ui(11)).foregroundStyle(Theme.muted).lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .frame(maxWidth: .infinity, minHeight: 76, alignment: .topLeading)
            .padding(12)
            .background(Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(selected ? Theme.accent : Theme.line, lineWidth: selected ? 2 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }

    private var icon: String {
        let id = persona.id.lowercased()
        if id.contains("hawk") { return "flame.fill" }
        if id.contains("dove") { return "leaf.fill" }
        if id.contains("tech") { return "cpu" }
        return "person.fill"
    }
}

struct DoctrinePreviewView: View {
    let rows: [DoctrineRow]

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack {
                Label("Доктрина · база → сдвиг · только просмотр", systemImage: "lock")
                    .font(Theme.ui(12)).foregroundStyle(Theme.muted)
                Spacer()
            }
            ForEach(rows) { r in
                HStack(spacing: 10) {
                    Text(r.label).font(Theme.ui(12)).foregroundStyle(Theme.text)
                        .frame(width: 178, alignment: .leading).lineLimit(1)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.surface2)
                            Capsule().fill(Color(hex: 0x3A3833))
                                .frame(width: max(0, geo.size.width * clamp(r.base)))
                            Rectangle().fill(Theme.accent)
                                .frame(width: 2, height: 14)
                                .offset(x: geo.size.width * clamp(r.shift) - 1, y: -3)
                        }
                    }
                    .frame(height: 8)
                    Text(deltaStr(r.delta))
                        .font(Theme.mono(11))
                        .foregroundStyle(r.delta > 0.005 ? Theme.deltaUp : (r.delta < -0.005 ? Theme.deltaDown : Theme.muted))
                        .frame(width: 44, alignment: .trailing)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }

    private func clamp(_ v: Double) -> Double { max(0, min(1, v)) }

    private func deltaStr(_ d: Double) -> String {
        let v = (d * 100).rounded() / 100
        let s = String(format: "%.2f", abs(v)).replacingOccurrences(of: "0.", with: ".")
        if v > 0.005 { return "+" + s }
        if v < -0.005 { return "−" + s }
        return "·"
    }
}
