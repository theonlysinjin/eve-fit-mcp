# Pyfa MCP

MCP server that wraps the [Eos](https://github.com/pyfa-org/eos) EVE Online fitting engine (same stack as [Pyfa](https://github.com/pyfa-org/Pyfa)). Agents propose fit changes; this server applies them, recalculates, and returns a **FitReport**. It never suggests modules — it only evaluates.

## Install (uvx)

Once published to PyPI:

```bash
uvx pyfa-mcp
```

Until then, from a checkout (submodules required so Eos is bundled into the install):

```bash
git clone --recurse-submodules git@github.com:theonlysinjin/eve-fit-mcp.git
cd eve-fit-mcp
uvx --from . pyfa-mcp
```

Or from git directly (after submodules are fetchable in the build):

```bash
uvx --from git+https://github.com/theonlysinjin/eve-fit-mcp.git pyfa-mcp
```

### Cursor MCP config (uvx)

```json
{
  "mcpServers": {
    "pyfa-mcp": {
      "command": "uvx",
      "args": ["--from", "/path/to/eve-fit-mcp", "pyfa-mcp"]
    }
  }
}
```

After PyPI:

```json
{
  "mcpServers": {
    "pyfa-mcp": {
      "command": "uvx",
      "args": ["pyfa-mcp"]
    }
  }
}
```

Staticdata downloads on first run into `~/.cache/pyfa-mcp/` (or call `refresh_static_data`). First Eos cache build can take a few minutes.

## Requirements

- Python 3.10+ (pulled in by uvx)
- Network on first run for staticdata (or set `EOS_PHOBOS_PATH`)
- Dev checkouts: git submodules `eos`, `phobos`, `pyfa` (`pyfa/staticdata` used when present)

### Staticdata (auto / refresh)

1. `EOS_PHOBOS_PATH` if set  
2. In-tree `pyfa/staticdata` (submodule)  
3. `~/.cache/pyfa-mcp/staticdata` (or `EOS_DATA_DIR`)  
4. Download from GitHub release [`staticdata`](https://github.com/theonlysinjin/eve-fit-mcp/releases/tag/staticdata)

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `EOS_PHOBOS_PATH` | no | Dump root; auto-resolved if omitted |
| `EOS_CACHE_PATH` | no | Eos cache file (default under data dir) |
| `EOS_DATA_DIR` | no | Download/cache root (default `~/.cache/pyfa-mcp`) |
| `EOS_STATICDATA_URL` | no | Override release asset URL |
| `EOS_SOURCE_ALIAS` | no | Default `tq` |
| `EOS_PACKAGE_PATH` | no | Only needed for editable/dev without wheel-bundled eos |
| `EOS_MAX_FITS` | no | Max in-memory fits (default 100) |
| `EOS_FIT_TTL` | no | Optional fit TTL in seconds |

## Dev install

```bash
git clone --recurse-submodules git@github.com:theonlysinjin/eve-fit-mcp.git
cd eve-fit-mcp
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
pyfa-mcp   # or: python -m pyfa_mcp
```

### Prebuilt binary

See [`binary-latest`](https://github.com/theonlysinjin/eve-fit-mcp/releases/tag/binary-latest) (`pyfa-mcp-linux-x64`, macOS, Windows). Point Cursor at the binary; staticdata still auto-downloads.

## Creating `AGENTS.md` (fitting projects)

Put an `AGENTS.md` in the project where you design fits (not in this MCP repo):

```markdown
# Fit with Pyfa MCP

You design EVE Online fits by proposing changes; the **pyfa-mcp** MCP evaluates them. It never suggests modules — you do.

Use the **eve-online-esi** MCP when the fit should reflect a real character’s skills. Prefer a cached map under `users/<Name>/skills.json`; refresh from ESI when asked or when the file is missing/stale.

## Skills (player maps)

**Apply (fitting):** load `users/<Name>/skills.json` → `set_skills(fit_id, data["skills"])`. Keys are skill type IDs; values are `active_skill_level` (0–5). Theorycraft: skip and use `apply_all_skills_5`.

**Refresh (update cache):**
1. `add_character` if needed (SSO; tokens stay local). Re-auth on 401 / missing character.
2. `GetCharactersCharacterIdSkills` with `character_id` (+ `X-Compatibility-Date`).
3. Write `users/<Name>/skills.json` as `{ character_id, name, updated_at, total_sp?, unallocated_sp?, skills: { str(skill_id): active_skill_level } }`.

## Startup

1. Confirm the goal in one line: role, constraints (EHP, DPS, tank type, cap stable?), and skills (player map via `users/…/skills.json`, or theorycraft).
2. If using a player map: load (or refresh) skills as above.
3. `create_fit(ship_type_id)` then either `set_skills` (from file) or `apply_all_skills_5`.
4. Rough in a full fit with type IDs: highs → mids → lows → rigs → drones/fighters → implants if needed.
5. Read the FitReport. Fix hard blockers first (`validation_errors`, CPU/PG/slots), then optimize toward the goal.
6. Iterate: **one** change per turn (`equip_module` / `replace_module` / `set_module_state` / `set_charge` / …). Compare reports. Use `clone_fit` for A/B forks.

## Rules

- Type IDs only — never invent them.
- Soft failures (CPU, skills, slots) still apply; hard errors (bad ID, wrong rack) do not mutate.
- Racks: `high` / `mid` / `low`. States: `offline` | `online` | `active` | `overload`.
- Stop when constraints are met or gains flatten. Summarize the final fit + key stats.

## FitReport priorities

`validation_errors` → `resources` / `slots` → `combat` (dps, ehp, RPS) → `mobility` → `fit` snapshot.
```

## Tools (v1)

**Session:** `create_fit`, `clone_fit`, `delete_fit`, `list_fits`, `get_fit`, `reset_fit`  
**Skills:** `set_skills`, `set_skill`, `clear_skills`, `apply_all_skills_5`  
**Hull:** `set_ship`, `set_stance`, `equip_module`, `replace_module`, `remove_module`, `set_module_state`, `set_charge`, `add_rig` / `remove_rig`, `add_subsystem` / `remove_subsystem`, `add_drone` / `remove_drone` / `set_drone_state`, `add_fighter` / `remove_fighter` / `set_fighter_state`, `add_implant` / `remove_implant`, `add_booster` / `remove_booster`, `set_effect_beacon`  
**Eval:** `get_stats`, `validate_fit`  
**Data:** `refresh_static_data`

## Non-goals

- Autofitting / “make this better”
- ESI login, skill sync, market prices
- wx/GUI / Pyfa desktop integration
- Full EFT/DNA import in v1
