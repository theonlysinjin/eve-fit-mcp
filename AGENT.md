# eve-fit-mcp

MCP server that wraps the [Eos](https://github.com/pyfa-org/eos) EVE Online fitting engine. Agents propose fit mutations; this package applies them, recalculates, and returns a **FitReport**. It never suggests modules or autofits.

Consumer-facing agent playbooks (how to *use* the MCP while fitting) live in the user’s project as `AGENTS.md` — see the README for a template. This file is for work **on this repo**.

## Layout

| Path | Role |
|------|------|
| `src/eve_fit_mcp/server.py` | FastMCP entry (`eos-fitting`), bootstrap + tool registration |
| `src/eve_fit_mcp/tools.py` | MCP tool surface; `AGENT_CONTRACT` text |
| `src/eve_fit_mcp/fit_store.py` | In-memory fits, TTL/max, mutation orchestration |
| `src/eve_fit_mcp/mutations.py` | Equip / replace / state / charge / drones / … |
| `src/eve_fit_mcp/report.py` | FitReport serialization + validation errors |
| `src/eve_fit_mcp/eos_bootstrap.py` | Load Eos + Phobos/cache fingerprint |
| `src/eve_fit_mcp/phobos_data.py` | Type/group lookups from dump |
| `tests/` | Smoke (no data) + roundtrips (need Phobos) |

## Environment

Required at runtime: `EOS_PHOBOS_PATH`, `EOS_CACHE_PATH`. Optional: `EOS_PACKAGE_PATH`, `EOS_SOURCE_ALIAS`, `EOS_MAX_FITS`, `EOS_FIT_TTL`. See `.env.example` and README.

Eos is a sibling checkout (or `EOS_PACKAGE_PATH`); it is not a PyPI dependency.

## Dev commands

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
export EOS_PHOBOS_PATH=… EOS_CACHE_PATH=… EOS_PACKAGE_PATH=…
pytest
eve-fit-mcp   # or: python -m eve_fit_mcp
```

Integration tests skip when Phobos data is missing.

## Contracts to preserve

- **Evaluate only** — no recommendations, market, or ESI in this package.
- Mutations return `{fit_id, report}` with a stable FitReport shape.
- Soft failures (CPU, skills, slots) still apply; hard errors (bad type ID, wrong rack) leave the fit unchanged and raise a tool error.
- Type IDs are canonical; racks are `high` / `mid` / `low`; module states are `offline` | `online` | `active` | `overload`.
