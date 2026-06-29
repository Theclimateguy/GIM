// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "GIM17App",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "GIM17App",
            path: "Sources/GIM17App"
        )
    ]
)
