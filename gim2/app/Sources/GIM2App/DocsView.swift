import SwiftUI
import WebKit
import AppKit

// Static model documentation: a bundled HTML page with SVG architecture / LLM-journey
// diagrams, module descriptions, and the embedded validation figures (backtest, ensemble,
// Morris). No JS bridge — it only renders.
struct DocsWebView: NSViewRepresentable {
    var page: String = "docs.html"   // also used for instructions.html (Инструкции tab)

    func makeNSView(context: Context) -> WKWebView {
        let web = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        web.navigationDelegate = context.coordinator
        web.wantsLayer = true
        web.layer?.backgroundColor = NSColor(red: 0.055, green: 0.059, blue: 0.071, alpha: 1).cgColor
        let dir = MapWebView.webDir()   // reuse the bundled web/ resolver (bundle or dev repo)
        web.loadFileURL(dir.appendingPathComponent(page), allowingReadAccessTo: dir)
        return web
    }
    func updateNSView(_ nsView: WKWebView, context: Context) {
        let dir = MapWebView.webDir()
        let target = dir.appendingPathComponent(page)
        if nsView.url != target {
            nsView.loadFileURL(target, allowingReadAccessTo: dir)
        }
    }
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
    @State private var tab = 0  // 0 = docs, 1 = validation, 2 = instructions (WebView)

    var body: some View {
        VStack(spacing: 0) {
            SegTabs(items: [
                (0, "Документация", "book"),
                (1, "Валидация", "checkmark.seal"),
                (2, "Инструкции", "questionmark.circle"),
            ], selection: $tab)
            .frame(maxWidth: 480)
            .padding(.horizontal, 22).padding(.top, 14).padding(.bottom, 8)
            .frame(maxWidth: .infinity, alignment: .leading)

            switch tab {
            case 0: DocsWebView(page: "docs.html")
            case 1: ScrollView { ValidationView() }
            default: DocsWebView(page: "instructions.html")
            }
        }
        .background(Theme.bg)
        .environment(\.colorScheme, .dark)
    }
}
