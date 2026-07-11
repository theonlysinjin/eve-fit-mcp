# pyfa-mcp

MCP server wrapping [Eos](https://github.com/pyfa-org/eos) for EVE Online fitting (Pyfa stack). Agents propose mutations; this package returns **FitReport**s. No autofit.

Consumer playbooks live in the user’s fitting project as `AGENTS.md` — see README. This file is for work **on this repo**.

## Layout

| Path | Role |
|------|------|
| `src/pyfa_mcp/server.py` | FastMCP entry (`pyfa-mcp`) |
| `src/pyfa_mcp/tools.py` | MCP tools |
| `src/pyfa_mcp/staticdata.py` | Download / refresh dump |
| `eos/` | Submodule — bundled into the wheel for `uvx` / PyPI |
| `pyfa/` | Submodule — `staticdata/` source for CI packs |
| `phobos/` | Submodule — dump tool |
| `.github/workflows/release-staticdata.yml` | Pack dump → release `staticdata` |
| `.github/workflows/release-binary.yml` | PyInstaller → `binary-latest` |

## uvx / packaging

```bash
git submodule update --init --recursive   # needed to build (eos in wheel)
uvx --from . pyfa-mcp
```

Wheel force-includes `eos/eos` → top-level `eos` package. No `EOS_PACKAGE_PATH` required for uvx/PyPI installs.

## Dev

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
```

## Contracts

- Evaluate only — no module recommendations.
- Soft failures still apply; hard errors do not mutate.
- Type IDs only; racks `high`/`mid`/`low`; states `offline`/`online`/`active`/`overload`.
