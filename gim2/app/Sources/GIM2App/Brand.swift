import SwiftUI
import AppKit

// Brand assets loaded from the .app bundle Resources (reused from v1). Absent in
// dev builds; callers fall back gracefully.
enum Brand {
    private static func load(_ name: String) -> Image? {
        guard let url = Bundle.main.resourceURL?.appendingPathComponent(name),
              FileManager.default.fileExists(atPath: url.path),
              let image = NSImage(contentsOf: url) else { return nil }
        return Image(nsImage: image)
    }

    static let glyph: Image? = load("glyph.png")
    static let logo: Image? = load("logo.png")
}
