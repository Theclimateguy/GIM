# GIM15 Validation Package (Release Track)

## Purpose

Provide a reproducible local validation package for release hardening with artifacts under `results/validation/...`.

## One-command run (non-LLM baseline)

```bash
./scripts/run_validation_package_v15.sh
```

Optional date tag:

```bash
./scripts/run_validation_package_v15.sh 2026-03-17
```

Default output:

- `results/validation/non_llm/<stamp>/unittest.log`
- `results/validation/non_llm/<stamp>/calibrate_simple.json`
- `results/validation/non_llm/<stamp>/calibrate_growth.json`
- `results/validation/non_llm/<stamp>/summary.md`

## Optional LLM package

LLM runs are opt-in and separated from the non-LLM baseline.

```bash
RUN_LLM=1 DEEPSEEK_API_KEY=... ./scripts/run_validation_package_v15.sh
```

Output:

- `results/validation/llm/<stamp>/calibrate_compiled_llm.json`

## Current local snapshot (2026-03-17)

Source:

- `results/validation/non_llm/wp3_wp5_2026-03-17/summary.md`

Summary:

- `operational_v2` pass rate: `5/5` in `simple`
- `operational_v2` pass rate: `5/5` in `growth`
- new economic outcomes appear where expected:
  - `sovereign_financial_crisis`
  - `social_unrest_without_military`
