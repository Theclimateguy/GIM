import SwiftUI
import AppKit

/// One-click copy of any text to the macOS pasteboard, with a brief checkmark.
struct CopyButton: View {
    let text: String
    var size: CGFloat = 11
    @State private var copied = false

    var body: some View {
        Button {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(text, forType: .string)
            copied = true
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) { copied = false }
        } label: {
            Image(systemName: copied ? "checkmark" : "doc.on.doc")
                .font(.system(size: size)).foregroundStyle(copied ? Theme.accent : Theme.faint)
        }
        .buttonStyle(.plain).help("Копировать")
    }
}

// Shared layout grammar for the redesigned v2 screens: left-aligned content,
// titled panels ("плашки"), fixed-width controls, one button vocabulary. Mirrors
// the macapp design system so both lines read identically.

// MARK: - Page scaffolding

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
    var trailing: AnyView? = nil          // optional accessory pinned to the title row
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
                if let trailing { trailing }
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
                        Text(item.label).font(Theme.ui(12, active ? .semibold : .regular)).lineLimit(1)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8).padding(.horizontal, 4)
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

/// A labeled slider with a fixed-width numeric readout.
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

// MARK: - Actor picker (string-keyed, from the ontology)

/// Multi-select country chips, inline (no nested scroll) so the page scrolls as
/// one surface. Used to scope a scenario to specific actors (trade/sanctions).
struct ActorPicker: View {
    let actors: [String]
    @Binding var selected: Set<String>
    private let cols = [GridItem(.adaptive(minimum: 132), spacing: 8)]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                InfoLabel(text: "Акторы", help: "Для рычагов торговли/санкций. Пусто — модель подберёт сама.")
                Text("выбрано \(selected.count)").font(Theme.ui(11)).foregroundStyle(Theme.faint)
                Spacer()
                if !selected.isEmpty {
                    Button("очистить") { selected.removeAll() }
                        .buttonStyle(.plain).font(Theme.ui(11)).foregroundStyle(Theme.accent)
                }
            }
            LazyVGrid(columns: cols, alignment: .leading, spacing: 8) {
                ForEach(actors, id: \.self) { chip($0) }
            }
            .padding(10)
            .background(Theme.surface2)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
        }
    }

    private func chip(_ name: String) -> some View {
        let on = selected.contains(name)
        return Button {
            if on { selected.remove(name) } else { selected.insert(name) }
        } label: {
            HStack(spacing: 6) {
                Image(systemName: on ? "checkmark.circle.fill" : "circle").font(.system(size: 10))
                Text(name).font(Theme.ui(11.5)).lineLimit(1)
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
