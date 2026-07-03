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
    static let appIcon: Image? = load("AppIcon.png")
}

// The app mark as a clean rounded tile. The source PNG has transparent corners; a
// continuous (squircle) clip at the icon's own ~22.5% radius removes any corner
// fringe so no mismatched box shows against the dark canvas.
//
// Prefers `glyph` (256px, sized for in-app UI) over `appIcon` (1024px, meant for
// the Dock/.icns pipeline) — at the small point sizes this view actually renders
// at (26/62pt), scaling the 1024px source down was a ~20-40x downsample that
// aliased the thin rim into a dotted ring. The rim itself is drawn as a native
// SwiftUI stroke rather than baked into the raster, so it stays a crisp hairline
// at any render size instead of being resampled from a fixed-resolution source.
struct BrandMark: View {
    var size: CGFloat = 26

    var body: some View {
        Group {
            if let icon = Brand.glyph ?? Brand.appIcon {
                icon.resizable().interpolation(.high).scaledToFill()
                    .clipShape(RoundedRectangle(cornerRadius: size * 0.225, style: .continuous))
                    .overlay(
                        Circle()
                            .strokeBorder(Theme.ring, lineWidth: max(1, size * 0.012))
                            .padding(size * 0.0703)
                    )
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
