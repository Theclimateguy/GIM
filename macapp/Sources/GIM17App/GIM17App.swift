import SwiftUI

struct GIM17App: App {
    @StateObject private var app = AppState()

    var body: some Scene {
        WindowGroup("GIM17") {
            RootView()
                .environmentObject(app)
                .task { await app.boot() }
                .onDisappear { app.shutdown() }
        }
        .windowResizability(.contentMinSize)
    }
}
