# Eos Fitting MCP Server

MCP server that wraps the [Eos](https://github.com/pyfa-org/eos) EVE Online fitting engine. Agents propose fit changes; this server applies them, recalculates, and returns a **FitReport** (stats + validation). Eos never suggests fits — it only evaluates.

## Requirements

- Python 3.10+
- Sibling [eos](https://github.com/pyfa-org/eos) checkout (or `EOS_PACKAGE_PATH`)
- A Phobos data dump (or Pyfa `staticdata/` layout with `fsd_built/`, `fsd_lite/`, `phobos/`)

Phobos itself lives at `../Phobos` and is used to generate dumps from the EVE client; you do not need to run it at MCP runtime if you already have a dump.

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `EOS_PHOBOS_PATH` | yes | Phobos dump root (folder containing `fsd_built/`, `fsd_lite/`, `phobos/`) |
| `EOS_CACHE_PATH` | yes | Eos cache file path, e.g. `.cache/eos_tq.json.bz2` |
| `EOS_SOURCE_ALIAS` | no | Default `tq` |
| `EOS_PACKAGE_PATH` | no | Path to eos repo root if not importable |
| `EOS_MAX_FITS` | no | Max in-memory fits (default 100) |
| `EOS_FIT_TTL` | no | Optional fit TTL in seconds |

Example using Pyfa’s staticdata (multi-part `*.0.json` files are supported):

```bash
export EOS_PHOBOS_PATH=/home/sinjin/workspace/Pyfa/staticdata
export EOS_CACHE_PATH=/home/sinjin/workspace/eve-fit-mcp/.cache/eos_tq.json.bz2
export EOS_PACKAGE_PATH=/home/sinjin/workspace/eos
```

First start builds the Eos cache from Phobos (can take a few minutes). Later starts reuse the cache when the fingerprint matches.

## Install & run

```bash
cd eve-fit-mcp
uv venv .venv && source .venv/bin/activate
uv pip install -e ".[dev]"
# eos is loaded via EOS_PACKAGE_PATH / PYTHONPATH (its setup.py needs pip)
export PYTHONPATH=/home/sinjin/workspace/eos:$PYTHONPATH

eve-fit-mcp
# or: python -m eve_fit_mcp
```

### Cursor MCP config

```json
{
  "mcpServers": {
    "eos-fitting": {
      "command": "/home/sinjin/workspace/eve-fit-mcp/.venv/bin/python",
      "args": ["-m", "eve_fit_mcp"],
      "env": {
        "EOS_PHOBOS_PATH": "/home/sinjin/workspace/Pyfa/staticdata",
        "EOS_CACHE_PATH": "/home/sinjin/workspace/eve-fit-mcp/.cache/eos_tq.json.bz2",
        "EOS_PACKAGE_PATH": "/home/sinjin/workspace/eos",
        "PYTHONPATH": "/home/sinjin/workspace/eos"
      }
    }
  }
}
```

## Creating `AGENTS.md` (fitting projects)

Put an `AGENTS.md` in the project where you design fits (not in this MCP repo). Cursor loads it as the agent playbook for that workspace. Example:

```markdown
# Fit with Eos MCP

You design EVE Online fits by proposing changes; the **eos-fitting** MCP evaluates them. It never suggests modules — you do.

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

Optionally keep skill caches under `users/<Name>/skills.json` next to that file. Contributor notes for **this** MCP codebase are in [AGENT.md](AGENT.md).

## Agent loop

1. Decide a goal (e.g. more DPS under skills, EHP ≥ X).
2. `create_fit` with skills (or `apply_all_skills_5`).
3. Equip an approximate fit (`equip_module`, `add_drone`, …).
4. Read the FitReport; propose **one** swap or state change.
5. Call the mutation tool; compare reports.
6. Repeat until constraints are met or returns diminish.

## Tools (v1)

**Session:** `create_fit`, `clone_fit`, `delete_fit`, `list_fits`, `get_fit`, `reset_fit`  
**Skills:** `set_skills`, `set_skill`, `clear_skills`, `apply_all_skills_5`  
**Hull:** `set_ship`, `set_stance`, `equip_module`, `replace_module`, `remove_module`, `set_module_state`, `set_charge`, `add_rig` / `remove_rig`, `add_subsystem` / `remove_subsystem`, `add_drone` / `remove_drone` / `set_drone_state`, `add_fighter` / `remove_fighter` / `set_fighter_state`, `add_implant` / `remove_implant`, `add_booster` / `remove_booster`, `set_effect_beacon`  
**Eval:** `get_stats`, `validate_fit`

Every mutation returns `{fit_id, report}` with the same FitReport shape as `get_stats`. Soft validation failures are included in the report; the mutation still applies. Hard errors (unknown type ID, invalid rack) leave the fit unchanged.

## Tests

```bash
export EOS_PHOBOS_PATH=... EOS_CACHE_PATH=... EOS_PACKAGE_PATH=...
pytest
```

Unit tests for report serialization run without data. Integration roundtrips skip if `EOS_PHOBOS_PATH` is missing.

## Non-goals

- Autofitting / “make this better”
- ESI login, skill sync, market prices
- wx/GUI / Pyfa desktop integration
- Full EFT/DNA import in v1
