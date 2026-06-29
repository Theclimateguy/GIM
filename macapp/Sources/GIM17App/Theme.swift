import SwiftUI

// Locked visual language: direction B "Situation Amber", dark-only.
// (See docs/ui_redesign + memory gim17-macos-app.)
enum Theme {
    static let bg = Color(hex: 0x0E0F12)
    static let surface = Color(hex: 0x17181D)
    static let surface2 = Color(hex: 0x121317)
    static let line = Color(hex: 0x2E2C28)
    static let text = Color(hex: 0xECE6DD)
    static let muted = Color(hex: 0x9A948A)
    static let faint = Color(hex: 0x5A554D)
    static let accent = Color(hex: 0xE0A458)
    static let accentInk = Color(hex: 0x1A1407)
    static let accentPress = Color(hex: 0xC98B3D)
    static let ring = Color(hex: 0xE8B45A)
    static let barLead = Color(hex: 0xE0A458)
    // Outcome bars — Variant 3: muted graphite ramp, gold only on the lead.
    static let barRamp = [Color(hex: 0x736E64), Color(hex: 0x67625A), Color(hex: 0x5C5851), Color(hex: 0x524E48)]
    static let deltaUp = Color(hex: 0xE0A458)
    static let deltaDown = Color(hex: 0xC08457)

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

// Surface card styling shared across screens.
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
