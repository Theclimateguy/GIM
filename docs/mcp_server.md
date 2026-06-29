# GIM17 MCP server

Exposes the validated GIM17 deterministic core as tools for any MCP-capable host
(LLM desktop apps, IDE plugins, agent frameworks, custom clients). The LLM drives scenario
work in natural language; the engine supplies the validated math. Fully self-contained — no
network/LLM calls inside the engine, so it runs inside a company perimeter.

## Install

```bash
pip install "gim17[mcp]"     # from the built wheel/sdist; pulls mcp + numpy + shapely
# or, from a checkout:
pip install ".[mcp]"
```

This registers the `gim-mcp` console script (stdio MCP server). State snapshots, priors, and
world geometry are bundled inside the package (`gim/data/`), so the server works out of the box
on a clean machine — no source checkout or data download required.

## Connect (any MCP client)

`gim-mcp` is a standard stdio MCP server. Any MCP-capable host — LLM desktop apps, IDE
plugins, agent frameworks, or a custom client — connects with the same contract:

- **command:** `gim-mcp` (or its absolute path if the host runs without your shell `PATH`)
- **transport:** stdio
- **args:** none

Most hosts accept this as a small JSON entry; the common shape is:

```jsonc
{
  "mcpServers": {
    "gim": { "command": "gim-mcp" }
  }
}
```

Consult your host's documentation for where this config lives. Once connected, the `gim`
server exposes 3 resources + 6 tools.

## Resources (read-only grounding)

| URI | Contents |
|---|---|
| `gim://model/card` | version, tracked metrics + units, validated-engine disclaimer |
| `gim://state/catalog` | available state snapshots (`snapshot` ids) |
| `gim://params/priors` | literature-anchored parameter priors |

## Tools

| Tool | Purpose |
|---|---|
| `gim_baseline` | current observable state of selected countries (the "where are we now" anchor) |
| `gim_ensemble` | Monte-Carlo fan bands (p5..p95) over 9 headline metrics — scenario distribution |
| `gim_scenario_delta` | evaluate a natural-language what-if; validated risk profile + crisis deltas |
| `gim_scc` | social cost of carbon ($/tCO₂): point / multi-horizon / distribution |
| `gim_sensitivity` | Morris screening — which parameters drive a target metric (factor attribution) |
| `gim_weak_signals` | early-warning scan: anomalies, structural breaks, critical slowing down |

### Output envelope (every tool)

```jsonc
{
  "result": { ... },
  "provenance": { "model_version", "state_snapshot", "seed", "params_set", ... },
  "overrides_applied": [],   // non-empty => caller/LLM changed an input; shown explicitly
  "units": { ... },
  "caveats": [ ... ],
  "disclaimer": "engine validated; LLM narrative is not"
}
```

Guarantees: **deterministic** (same inputs → identical result, fully provenanced),
**anti-drift** (any override is echoed), **fidelity-switchable**
(`quick`/`standard`/`publication` trade speed for tightness).

The default `snapshot` is the **calibrated 2026** state — the one the paper's validated
headline numbers are computed on. Override per call with `snapshot=<id from the catalog>`.

## Notes

- `gim_scenario_delta` parses the question deterministically (`compile_question`) as the
  primary path; pin `actors` / `template_id` as an escape hatch. It runs the offline
  `simple` policy (no LLM).
- `gim_sensitivity` needs numpy (included in the `[mcp]` extra).
