# Integration benchmark

Makes the paper's "integrated beats sectoral" claim **computational**: for three shocks, take a
published conclusion from a named *sectoral* model, run GIM on the same shock, and show GIM
surfaces a cross-sector consequence the sectoral model cannot represent.

Full write-up, citations, and the three honesty notes: [`docs/INTEGRATION_BENCHMARK.md`](../../docs/INTEGRATION_BENCHMARK.md).

```bash
# 1. run the controlled experiments (deterministic; ~10s)
python3 -m scripts.integration_benchmark.gim_benchmark
#    -> results/integration_benchmark/<timestamp>/benchmark.json (+ latest.json pointer)

# 2. render the figures (matches paper house style)
python3 -m scripts.integration_benchmark.make_benchmark_figures
#    -> paper/figures/fig6_integration_carbon, fig7_integration_oil,
#       fig8_integration_crop, fig9_integration_summary  (.pdf + .png)
```

| file | what |
|---|---|
| `gim_benchmark.py` | scenario definitions, shock injection at validated transmission points, dose-response sweeps, results JSON |
| `make_benchmark_figures.py` | reproducible figures (trajectory contrast + dose-response per scenario, plus the thesis summary panel) |

Scenarios: **A** carbon tax \$50/t (DICE → emissions; GIM adds social tension), **B** oil −20%
(MESSAGEix → price; GIM adds the sovereign-debt cascade), **C** +2°C crop (AgMIP → hunger; GIM adds
protest pressure). Each reports a baseline-vs-shock trajectory and a dose-response whose sectoral
slope is structurally zero.
