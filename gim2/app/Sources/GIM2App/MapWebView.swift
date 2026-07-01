import SwiftUI
import WebKit

// Forwards the scroll wheel to the enclosing SwiftUI ScrollView so the chat keeps
// scrolling when the cursor is over the map (the map is a static overview; pan by
// drag). Without this, WKWebView swallows the wheel and the page can't scroll past
// the map.
final class PassThroughWebView: WKWebView {
    override func scrollWheel(with event: NSEvent) {
        nextResponder?.scrollWheel(with: event)
    }
}

// Leaflet choropleth in a WKWebView. Loads the bundled web/ assets (vendored
// leaflet + world_countries.geojson as a local script) and injects the engine's
// actors.geo payload via window.renderGeo(...). True country borders — not dots.
struct MapWebView: NSViewRepresentable {
    let geo: Geo?

    static func webDir() -> URL {
        if let res = Bundle.main.resourceURL {
            let w = res.appendingPathComponent("web")
            if FileManager.default.fileExists(atPath: w.appendingPathComponent("map.html").path) {
                return w
            }
        }
        // dev fallback (swift run, no .app bundle)
        return EngineProcess.repoRoot().appendingPathComponent("gim2/app/Resources/web")
    }

    func makeNSView(context: Context) -> WKWebView {
        let web = PassThroughWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = context.coordinator
        // Dark backing layer so there is no white flash before the page paints
        // (public API — avoids the private `drawsBackground` KVC).
        web.wantsLayer = true
        web.layer?.backgroundColor = NSColor(red: 0.055, green: 0.059, blue: 0.071, alpha: 1).cgColor
        let dir = Self.webDir()
        web.loadFileURL(dir.appendingPathComponent("map.html"), allowingReadAccessTo: dir)
        context.coordinator.web = web
        return web
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        context.coordinator.pending = geo
        context.coordinator.render()
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, WKNavigationDelegate {
        weak var web: WKWebView?
        var pending: Geo?
        private var loaded = false

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            loaded = true
            render()
        }

        func render() {
            guard loaded, let web, let geo = pending,
                  let data = try? EngineClient.encoder.encode(geo),
                  let json = String(data: data, encoding: .utf8) else { return }
            web.evaluateJavaScript("window.renderGeo(\(json));", completionHandler: nil)
        }
    }
}
