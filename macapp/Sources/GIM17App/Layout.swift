import SwiftUI

// Shared layout grammar for the redesigned screens. The goal is a consistent,
// geometrically aligned console: left-aligned content, titled panels ("плашки"),
// fixed-width controls (no stretched/centered inputs), one button vocabulary.

// MARK: - Page scaffolding

/// Standard page header: kicker (small caps) + title + optional subtitle.
struct PageHeader: View {
    let kicker: String
    let title: String
    var subtitle: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(kicker.uppercased())
                .font(Theme.ui(11, .semibold)).tracking(1.6).foregroundStyle(Theme.accent)
            Text(title).font(Theme.ui(22, .semibold)).foregroundStyle(Theme.text)
            if let subtitle {
                Text(subtitle).font(Theme.ui(12.5)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// A titled panel on a surface card: caption row + content. The workhorse "плашка".
struct Panel<Content: View>: View {
    let title: String
    var icon: String? = nil
    var caption: String? = nil
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(spacing: 7) {
                if let icon {
                    Image(systemName: icon).font(.system(size: 12)).foregroundStyle(Theme.accent)
                }
                Text(title).font(Theme.ui(12.5, .semibold)).foregroundStyle(Theme.text)
                if let caption {
                    Text(caption).font(Theme.ui(11)).foregroundStyle(Theme.faint)
                }
                Spacer(minLength: 0)
            }
            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(Theme.surface)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.line, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Form controls

/// Small muted label with an optional info affordance.
struct InfoLabel: View {
    let text: String
    var help: String? = nil

    var body: some View {
        HStack(spacing: 5) {
            Text(text).font(Theme.ui(11.5)).foregroundStyle(Theme.muted)
            if let help {
                Image(systemName: "info.circle").font(.system(size: 10))
                    .foregroundStyle(Theme.faint).help(help)
            }
        }
    }
}

/// A labeled vertical control group (label above its control).
struct Field<C: View>: View {
    let label: String
    var help: String? = nil
    @ViewBuilder var content: () -> C

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            InfoLabel(text: label, help: help)
            content()
        }
    }
}

extension View {
    /// Shared text-input chrome so every field reads identically.
    func inputField() -> some View {
        self
            .padding(.horizontal, 11).padding(.vertical, 9)
            .background(Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    var enabled: Bool = true
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.ui(13, .semibold))
            .foregroundStyle(Theme.accentInk)
            .padding(.horizontal, 20).padding(.vertical, 11)
            .background(enabled ? (configuration.isPressed ? Theme.accentPress : Theme.accent)
                                : Theme.accent.opacity(0.35))
            .clipShape(RoundedRectangle(cornerRadius: 9))
            .contentShape(Rectangle())
    }
}

struct GhostButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.ui(12.5, .medium))
            .foregroundStyle(configuration.isPressed ? Theme.text : Theme.muted)
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background(configuration.isPressed ? Theme.surface2 : Color.clear)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .contentShape(Rectangle())
    }
}

/// Segmented selector. Equal-width segments, gold fill on the active one.
struct SegTabs<T: Hashable>: View {
    let items: [(value: T, label: String, icon: String)]
    @Binding var selection: T

    var body: some View {
        HStack(spacing: 3) {
            ForEach(items, id: \.value) { item in
                let active = selection == item.value
                Button { selection = item.value } label: {
                    HStack(spacing: 6) {
                        Image(systemName: item.icon).font(.system(size: 11))
                        Text(item.label).font(Theme.ui(12.5, active ? .semibold : .regular))
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .foregroundStyle(active ? Theme.accentInk : Theme.muted)
                    .background(active ? Theme.accent : Color.clear)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
        .padding(3)
        .background(Theme.surface2)
        .overlay(RoundedRectangle(cornerRadius: 11).stroke(Theme.line, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 11))
    }
}

/// A labeled slider with a fixed-width numeric readout — used for shock intensity.
struct SliderControl: View {
    let value: Binding<Double>
    let range: ClosedRange<Double>
    var format: String = "%.2f"

    var body: some View {
        HStack(spacing: 10) {
            Slider(value: value, in: range).tint(Theme.accent)
            Text(String(format: format, value.wrappedValue))
                .font(Theme.mono(12)).foregroundStyle(Theme.text)
                .frame(width: 42, alignment: .trailing)
        }
    }
}

// MARK: - Actor picker

/// Multi-select country chips. Rendered inline (no nested scroll) so the page
/// scrolls as one surface — a nested scroller here would trap the outer scroll
/// and hide controls placed below it.
struct ActorPicker: View {
    let actors: [ActorOption]
    @Binding var selected: Set<String>
    private let cols = [GridItem(.adaptive(minimum: 132), spacing: 8)]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                InfoLabel(text: "Акторы", help: "Кого включить в сценарий. Пусто — модель подберёт сама.")
                Text("выбрано \(selected.count)").font(Theme.ui(11)).foregroundStyle(Theme.faint)
                Spacer()
                if !selected.isEmpty {
                    Button("очистить") { selected.removeAll() }
                        .buttonStyle(.plain).font(Theme.ui(11)).foregroundStyle(Theme.accent)
                }
            }
            LazyVGrid(columns: cols, alignment: .leading, spacing: 8) {
                ForEach(actors) { chip($0) }
            }
            .padding(10)
            .background(Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
        }
    }

    private func chip(_ actor: ActorOption) -> some View {
        let on = selected.contains(actor.name)
        return Button {
            if on { selected.remove(actor.name) } else { selected.insert(actor.name) }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: on ? "checkmark.circle.fill" : "circle").font(.system(size: 10))
                Text(actor.name).font(Theme.ui(11.5)).lineLimit(1)
            }
            .foregroundStyle(on ? Theme.accentInk : Theme.muted)
            .padding(.horizontal, 9).padding(.vertical, 6)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(on ? Theme.accent : Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(on ? Theme.accent : Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Shock composer

/// The shock library: each calibrated lever toggles on with an intensity slider.
/// `shocks` maps lever id → magnitude; absence means the lever is off.
struct ShockComposer: View {
    @Binding var shocks: [String: Double]

    var body: some View {
        VStack(spacing: 8) {
            ForEach(shockLevers) { lever in row(lever) }
        }
    }

    private func row(_ lever: ShockLever) -> some View {
        let on = shocks[lever.id] != nil
        return VStack(spacing: 0) {
            HStack(spacing: 11) {
                Button {
                    if on { shocks.removeValue(forKey: lever.id) }
                    else { shocks[lever.id] = Magnitude.default }
                } label: {
                    Image(systemName: on ? "checkmark.square.fill" : "square")
                        .font(.system(size: 15)).foregroundStyle(on ? Theme.accent : Theme.faint)
                }
                .buttonStyle(.plain)

                Image(systemName: lever.icon).font(.system(size: 13))
                    .foregroundStyle(on ? Theme.accent : Theme.muted).frame(width: 18)

                VStack(alignment: .leading, spacing: 2) {
                    Text(lever.label).font(Theme.ui(12.5, on ? .medium : .regular))
                        .foregroundStyle(on ? Theme.text : Theme.muted)
                    if on {
                        Text(lever.note).font(Theme.ui(10.5)).foregroundStyle(Theme.faint).lineLimit(1)
                    }
                }
                Spacer(minLength: 8)

                if on {
                    SliderControl(
                        value: Binding(
                            get: { shocks[lever.id] ?? Magnitude.default },
                            set: { shocks[lever.id] = $0 }),
                        range: Magnitude.min...Magnitude.max)
                    .frame(width: 168)
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 9)
            .background(on ? Theme.surface2 : Color.clear)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(on ? Theme.accent.opacity(0.45) : Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
        }
    }
}
