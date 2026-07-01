// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "GIM2App",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "GIM2App",
            path: "Sources/GIM2App",
            swiftSettings: [.unsafeFlags(["-parse-as-library"])]
        )
    ]
)
