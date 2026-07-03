import SwiftUI
import AppKit

// Renders a tool result (Expert-mode compute — scenario/ensemble/dose/sensitivity/weak
// signals) to a static PNG for the Assistant chat: a real chart, but a flat image rather
// than a live interactive Chart, so a long conversation doesn't carry dozens of live chart
// views. run_answer is excluded — it already gets the rich, live SituationRoom card.
@MainActor
enum ChartSnapshot {
    static func render(toolName: String, resultJSON: String) -> String? {
        guard let data = resultJSON.data(using: .utf8), let view = preview(toolName, data) else { return nil }
        let framed = view
            .padding(12)
            .frame(width: 360)
            .background(Theme.surface)
            .environment(\.colorScheme, .dark)

        let renderer = ImageRenderer(content: framed)
        renderer.scale = 2.0
        guard let nsImage = renderer.nsImage,
              let tiff = nsImage.tiffRepresentation,
              let rep = NSBitmapImageRep(data: tiff),
              let png = rep.representation(using: .png, properties: [:]) else { return nil }
        return png.base64EncodedString()
    }

    private static func preview(_ toolName: String, _ data: Data) -> AnyView? {
        switch toolName {
        case "run_scenario":
            guard let r = try? EngineClient.decoder.decode(ScenarioResult.self, from: data),
                  let m = r.projection.metrics.first else { return nil }
            return AnyView(labeled("Δ " + MetricLabel.of(m.metric) + " · сценарий vs база") {
                DeltaChartView(delta: m.delta, height: 130)
            })
        case "run_ensemble":
            guard let r = try? EngineClient.decoder.decode(EnsembleResult.self, from: data),
                  let m = r.projection.metrics.first else { return nil }
            return AnyView(labeled(MetricLabel.of(m.metric) + " · база (медиана, 5–95)") {
                FanChartView(fan: m, height: 130)
            })
        case "run_dose_response":
            guard let r = try? EngineClient.decoder.decode(DoseResult.self, from: data) else { return nil }
            return AnyView(labeled("\(r.lever) → Δ " + MetricLabel.of(r.projection.metric)) {
                DoseChartView(dose: r.projection, height: 130)
            })
        case "run_sensitivity":
            guard let r = try? EngineClient.decoder.decode(SensitivityResult.self, from: data) else { return nil }
            return AnyView(labeled("μ* по " + MetricLabel.of(r.metric) + " (Morris)") {
                TornadoChartView(params: r.projection.params, height: 160)
            })
        case "run_weak_signals":
            guard let r = try? EngineClient.decoder.decode(WeakResult.self, from: data),
                  let m = r.weakSignals.mahalanobis, let d2 = m.distanceSq,
                  let anomaly = m.anomaly, let threshold = m.threshold else { return nil }
            return AnyView(labeled("Махаланобис-аномалии совместного состояния") {
                MahalanobisChartView(distanceSq: d2, anomaly: anomaly, threshold: threshold, height: 130)
            })
        default:
            return nil
        }
    }

    @ViewBuilder
    private static func labeled<C: View>(_ title: String, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(Theme.ui(11, .semibold)).foregroundStyle(Theme.text)
            content()
        }
    }
}
