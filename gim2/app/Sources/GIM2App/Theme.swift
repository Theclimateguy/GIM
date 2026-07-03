import SwiftUI

// Visual language: direction C "Steel Technocratic", dark-only. Replaces the
// v1/v17 warm "Situation Amber" palette (gold on brown) with a near-monochrome
// steel/white system — cool graphite surfaces, white text, a restrained
// steel-blue accent used sparingly as a signal colour rather than a brand colour.
enum Theme {
    static let bg = Color(hex: 0x0A0B0D)
    static let surface = Color(hex: 0x15171B)
    static let surface2 = Color(hex: 0x0F1013)
    static let line = Color(hex: 0x2A2D33)
    static let text = Color(hex: 0xF2F3F5)
    static let muted = Color(hex: 0x9AA0AA)
    static let faint = Color(hex: 0x5A5F68)
    static let accent = Color(hex: 0x8FA8C9)
    static let accentInk = Color(hex: 0x0A1420)
    static let accentPress = Color(hex: 0x738DB0)
    static let ring = Color(hex: 0xC9D2DC)
    // Outcome bars — muted graphite ramp, steel-blue only on the lead.
    static let barRamp = [Color(hex: 0x70747C), Color(hex: 0x656971), Color(hex: 0x5A5E66), Color(hex: 0x50545B)]
    // +/- outcome colours: clearly distinct green/coral, matched to the map legend
    // ("лучше базы" / "хуже базы") so bars and choropleth read the same.
    static let deltaUp = Color(hex: 0x6FAE8C)
    static let deltaDown = Color(hex: 0xC97D6E)

    static func ui(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight)
    }
    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255.0,
            green: Double((hex >> 8) & 0xFF) / 255.0,
            blue: Double(hex & 0xFF) / 255.0,
            opacity: 1.0
        )
    }
}

struct Card: ViewModifier {
    var padding: CGFloat = 14
    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Theme.surface)
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.line, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

extension View {
    func card(padding: CGFloat = 14) -> some View { modifier(Card(padding: padding)) }
}
