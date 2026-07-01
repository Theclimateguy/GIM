import SwiftUI

// Native, app-themed validation block for the Docs tab (replaces the white matplotlib PNGs):
// backtest RMSE bars, ensemble fans, conflict AUC, and Morris sensitivity — all in the gold/black
// house style, rendered by the app itself from the engine's own data.
struct ValidationView: View {
    @EnvironmentObject var app: AppState
    @State private var sens: SensitivityResult?
    @State private var sensLoading = false

    // Golden-backtest RMSE (18.0.0 reviewer-response deepening: damage function re-anchored to
    // Howard-Sterner + normalised to the 2023 baseline, internal-variability spread re-derived from
    // observed residuals): the closed CES core vs the Cobb–Douglas baseline. (label, core, baseline) —
    // lower is better. Both production functions still fit the product equally (~0.60 trn); the
    // nested-CES advantage remains concentrated in emissions (0.94 vs 1.74 Gt).
    private let rmse: [(String, Double, Double)] = [
        ("Мировой продукт, трлн $", 0.60, 0.60),
        ("CO₂, Гт", 0.94, 1.74),
        ("Температура, °C", 0.145, 0.144),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionTitle(title: "Валидация модели",
                         subtitle: "графики рассчитаны движком и отрисованы приложением в его стилистике")

            Panel(title: "Ретро-валидация 2015–2023, RMSE", icon: "checkmark.seal",
                  caption: "замкнутое ядро (CES) против базового (Кобб–Дуглас) · ниже — лучше") {
                RmseBarsView(rows: rmse)
            }

            Panel(title: "Ансамбль Монте-Карло", icon: "chart.line.uptrend.xyaxis",
                  caption: "веера неопределённости по приорам · медиана, IQR, 5–95") {
                if let ens = app.baselineEnsemble {
                    fans(ens)
                } else {
                    loadingRow("строится базовый ансамбль…")
                }
            }

            Panel(title: "Риск конфликта (UCDP, 1990–2023)", icon: "scope",
                  caption: "ранжирование 57 стран и страновых агрегатов, образующих весь мир") {
                if let a = app.auc {
                    AUCView(proj: a.projection)
                } else {
                    loadingRow("загрузка AUC…")
                }
            }

            Panel(title: "Чувствительность (метод Морриса)", icon: "slider.horizontal.3",
                  caption: "ведущие параметры мирового продукта · μ* (r = 8)") {
                if let s = sens {
                    TornadoChartView(params: s.projection.params)
                } else if sensLoading {
                    loadingRow("скрининг Морриса…")
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        Button("Запустить скрининг") { Task { await loadSens() } }
                            .buttonStyle(GhostButtonStyle())
                        Text("Полный скрининг по четырём метрикам — в Экспертном режиме.")
                            .font(Theme.ui(11)).foregroundStyle(Theme.faint)
                    }
                }
            }
        }
        .padding(.horizontal, 22).padding(.vertical, 18)
        .task {
            await app.loadValidation()        // conflict AUC (fast)
            await app.loadBaselineEnsemble()  // ensemble fans
        }
    }

    @ViewBuilder private func fans(_ ens: EnsembleResult) -> some View {
        let units = ["world_gdp": "трлн $", "temperature": "°C"]
        let series = ["world_gdp", "temperature"].compactMap { k in
            ens.projection.metrics.first { $0.metric == k }
        }
        VStack(spacing: 14) {
            ForEach(series) { f in
                VStack(alignment: .leading, spacing: 4) {
                    Text(MetricLabel.of(f.metric)).font(Theme.ui(12, .semibold)).foregroundStyle(Theme.text)
                    FanChartView(fan: f, color: Theme.accent, height: 150, unit: units[f.metric] ?? "")
                }
            }
        }
    }

    @ViewBuilder private func loadingRow(_ text: String) -> some View {
        HStack(spacing: 8) {
            ProgressView().controlSize(.small)
            Text(text).font(Theme.ui(11.5)).foregroundStyle(Theme.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, 6)
    }

    private func loadSens() async {
        sensLoading = true
        defer { sensLoading = false }
        sens = try? await app.runSensitivity(.init(metric: "world_gdp", years: 10, r: 8, maxAgents: 30))
    }
}

// Grouped horizontal RMSE bars: gold = closed CES core, faint = Cobb–Douglas baseline.
// Each metric is normalized to its own row max (the three metrics live on different scales),
// with the absolute value pinned to the right.
struct RmseBarsView: View {
    let rows: [(String, Double, Double)]  // (label, core, baseline)

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            ForEach(rows, id: \.0) { row in
                let maxv = max(row.1, row.2, 1e-9)
                VStack(alignment: .leading, spacing: 5) {
                    Text(row.0).font(Theme.ui(11.5, .semibold)).foregroundStyle(Theme.text)
                    bar(value: row.1, frac: row.1 / maxv, color: Theme.accent)
                    bar(value: row.2, frac: row.2 / maxv, color: Theme.faint)
                }
            }
            HStack(spacing: 16) {
                legend(Theme.accent, "замкнутое ядро (CES)")
                legend(Theme.faint, "базовое (Кобб–Дуглас)")
            }
            .padding(.top, 2)
        }
    }

    private func bar(value: Double, frac: Double, color: Color) -> some View {
        HStack(spacing: 8) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.surface2).frame(height: 15)
                    Capsule().fill(color).frame(width: max(3, frac * geo.size.width), height: 15)
                }
            }
            .frame(height: 15)
            Text(String(format: "%g", value)).font(Theme.mono(11)).foregroundStyle(Theme.muted)
                .frame(width: 46, alignment: .trailing)
        }
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 6) {
            Capsule().fill(color).frame(width: 16, height: 9)
            Text(text).font(Theme.ui(10.5)).foregroundStyle(Theme.muted)
        }
    }
}
