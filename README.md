# GIM — library + MCP server

Self-contained distribution of the **Global Integrated Model (GIM17)** engine, packaged as
a library and exposed to LLMs through an **MCP server**. Designed for risk analysts who want
GIM's validated climate–economy–conflict math available as tools (scenario distributions,
SCC, sensitivity, weak-signals, bespoke what-ifs) while a frontier model handles the natural
language. Runs fully offline — no network/LLM calls inside the engine — so it is safe to use
inside a company perimeter.

## What's in this branch

```
gim/                  the validated GIM17 engine (the library)
gim/mcp_server.py     the MCP server (gim-mcp) — 6 tools + 3 resources
gim/data/             calibrated state snapshots, priors, world geometry — bundled
                      INSIDE the package, so a plain `pip install` works out of the box
docs/mcp_server.md    MCP tool/resource reference + client setup
paper/                the GIM17 paper (RU primary, EN) — the authoritative math guide
```

## The math guide

The model's mathematics, calibration, and validation are documented in the paper:

- **[paper/gim_paper_ru.pdf](paper/gim_paper_ru.pdf)** — primary (Russian)
- [paper/gim_paper.pdf](paper/gim_paper.pdf) — English

Read it to understand what the tools compute and under what assumptions. The MCP layer never
invents quantities; it only surfaces what the engine in this paper produces.

## Install

```bash
pip install ".[mcp]"        # from a checkout
# or build a wheel and install it on a clean machine:
#   pip install build && python -m build
#   pip install "dist/gim17-*.whl[mcp]"
```

The calibrated state snapshots, priors, and world geometry ship **inside the package**
(`gim/data/`), so the engine finds them after a plain install — no source tree required.
This registers the `gim-mcp` console script.

## Connect (Claude Desktop)

Add to `claude_desktop_config.json`, then restart the client:

```jsonc
{
  "mcpServers": {
    "gim": { "command": "gim-mcp" }
  }
}
```

See **[docs/mcp_server.md](docs/mcp_server.md)** for the full tool/resource reference, the
provenance-envelope contract (determinism, anti-drift, fidelity), and snapshot selection.

## License

Apache-2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
