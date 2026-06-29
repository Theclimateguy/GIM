import SwiftUI
import WebKit
import AppKit

// Static model documentation: a bundled HTML page with SVG architecture / LLM-journey
// diagrams, module descriptions, and the embedded validation figures (backtest, ensemble,
// Morris). No JS bridge — it only renders.
struct DocsWebView: NSViewRepresentable {
    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = context.coordinator
        web.wantsLayer = true
        web.layer?.backgroundColor = NSColor(red: 0.055, green: 0.059, blue: 0.071, alpha: 1).cgColor
        let dir = MapWebView.webDir()   // reuse the bundled web/ resolver (bundle or dev repo)
        web.loadFileURL(dir.appendingPathComponent("docs.html"), allowingReadAccessTo: dir)
        return web
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {}
    func makeCoordinator() -> Coordinator { Coordinator() }

    // Open external (http/https) links — e.g. the repo link — in the default browser instead
    // of navigating away from the docs page inside the WebView.
    final class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            if navigationAction.navigationType == .linkActivated,
               let url = navigationAction.request.url, url.scheme == "http" || url.scheme == "https" {
                NSWorkspace.shared.open(url)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

struct DocsView: View {
    var body: some View {
        DocsWebView().background(Theme.bg)
    }
}
