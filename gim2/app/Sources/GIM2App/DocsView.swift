import SwiftUI
import WebKit

// Static model documentation: a bundled HTML page with SVG architecture / LLM-journey
// diagrams, module descriptions, and the embedded validation figures (backtest, ensemble,
// Morris). No JS bridge — it only renders.
struct DocsWebView: NSViewRepresentable {
    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.wantsLayer = true
        web.layer?.backgroundColor = NSColor(red: 0.055, green: 0.059, blue: 0.071, alpha: 1).cgColor
        let dir = MapWebView.webDir()   // reuse the bundled web/ resolver (bundle or dev repo)
        web.loadFileURL(dir.appendingPathComponent("docs.html"), allowingReadAccessTo: dir)
        return web
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
}

struct DocsView: View {
    var body: some View {
        DocsWebView().background(Theme.bg)
    }
}
