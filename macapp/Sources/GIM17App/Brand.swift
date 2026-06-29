import SwiftUI
import AppKit

// Brand assets, loaded from the .app bundle Resources at runtime. In dev builds
// (no .app) these are absent and callers fall back gracefully.
enum Brand {
    private static func load(_ name: String) -> Image? {
        guard let url = Bundle.main.resourceURL?.appendingPathComponent(name),
              FileManager.default.fileExists(atPath: url.path),
              let image = NSImage(contentsOf: url) else { return nil }
        return Image(nsImage: image)
    }

    static let glyph: Image? = load("glyph.png")
    static let logo: Image? = load("logo.png")
    static let appIcon: Image? = load("AppIcon.png")
}

// The app mark, rendered as a clean rounded tile. The source PNG is a macOS-style
// icon whose corners are transparent; a continuous (squircle) clip at the icon's
// own ~22.5% radius removes any corner fringe so no mismatched box shows around it
// against the dark canvas.
struct BrandMark: View {
    var size: CGFloat = 22

    var body: some View {
        Group {
            if let icon = Brand.appIcon {
                icon.resizable().interpolation(.high).scaledToFill()
            } else {
                RoundedRectangle(cornerRadius: size * 0.225, style: .continuous)
                    .fill(Theme.surface2)
                    .overlay(Image(systemName: "globe").font(.system(size: size * 0.5)).foregroundStyle(Theme.accent))
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: size * 0.225, style: .continuous))
    }
}
