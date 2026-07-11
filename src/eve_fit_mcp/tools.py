"""Register all MCP tools on a FastMCP instance."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from eve_fit_mcp import mutations
from eve_fit_mcp.eos_bootstrap import skill_type_ids
from eve_fit_mcp.errors import FitMcpError
from eve_fit_mcp.fit_store import FitStore
from eve_fit_mcp.report import collect_validation_errors
from eve_fit_mcp.typecheck import require_type
AGENT_CONTRACT = (
    "This server evaluates fits only — it does not recommend modules or autofit. "
    "Propose one change at a time, call a mutation tool, compare FitReport snapshots, "
    "and iterate. Set character skills before judging skill-gated modules."
)


def _raise(exc: Exception) -> None:
    if isinstance(exc, FitMcpError):
        raise ToolError(exc.message) from exc
    raise ToolError(str(exc)) from exc


def register_tools(mcp: FastMCP, store: FitStore) -> None:
    # --- Session ---

    @mcp.tool(description=f"Create a new fit for ship_type_id. {AGENT_CONTRACT}")
    def create_fit(
        ship_type_id: int,
        skills: dict[str, int] | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        try:
            return store.create(ship_type_id, skills=skills, label=label)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Clone an existing fit into a new fit_id.")
    def clone_fit(fit_id: str) -> dict[str, Any]:
        try:
            return store.clone(fit_id)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Delete a fit from the in-memory store.")
    def delete_fit(fit_id: str) -> dict[str, Any]:
        try:
            return store.delete(fit_id)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="List fits: fit_id, ship_type_id, label.")
    def list_fits() -> list[dict[str, Any]]:
        return store.list_fits()

    @mcp.tool(description="Full structured fit + FitReport for fit_id.")
    def get_fit(fit_id: str) -> dict[str, Any]:
        try:
            return store.report(fit_id)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(
        description=(
            "Clear modules/drones/etc. Keep or replace ship; keep skills unless "
            "you clear them separately."
        )
    )
    def reset_fit(fit_id: str, ship_type_id: int | None = None) -> dict[str, Any]:
        try:
            return store.reset(fit_id, ship_type_id=ship_type_id)
        except Exception as exc:
            _raise(exc)
            raise

    # --- Skills ---

    @mcp.tool(description="Replace the entire skill map for a fit. Keys are type_id strings/ints.")
    def set_skills(fit_id: str, skills: dict[str, int]) -> dict[str, Any]:
        try:
            return store.set_skills(fit_id, skills)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Upsert a single skill level (0-5).")
    def set_skill(fit_id: str, type_id: int, level: int) -> dict[str, Any]:
        try:
            return store.set_skill(fit_id, type_id, level)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove all skills from a fit.")
    def clear_skills(fit_id: str) -> dict[str, Any]:
        try:
            return store.clear_skills(fit_id)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(
        description=(
            "Set all Phobos skill types (category 16) to level 5 for theorycraft. "
            "Does not recommend fits."
        )
    )
    def apply_all_skills_5(fit_id: str) -> dict[str, Any]:
        try:
            skills = {str(tid): 5 for tid in skill_type_ids()}
            return store.set_skills(fit_id, skills)
        except Exception as exc:
            _raise(exc)
            raise

    # --- Hull / fittings ---

    @mcp.tool(description="Set or replace the ship hull. Does not clear other items.")
    def set_ship(fit_id: str, ship_type_id: int) -> dict[str, Any]:
        try:
            from eos import Ship, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            require_type(int(ship_type_id), kind="ship")
            try:
                fit.ship = Ship(int(ship_type_id))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(ship_type_id), "ship type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set tactical mode/stance type_id, or null to clear.")
    def set_stance(fit_id: str, type_id: int | None = None) -> dict[str, Any]:
        try:
            from eos import Stance, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            if type_id is None:
                fit.stance = None
            else:
                require_type(int(type_id), kind="stance")
                try:
                    fit.stance = Stance(int(type_id))
                except TypeFetchError as exc:
                    raise InvalidTypeError(int(type_id), "stance type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(
        description=(
            "Equip a module on rack high|mid|low. Optional state, charge_type_id, index. "
            "One change at a time — this server does not recommend modules."
        )
    )
    def equip_module(
        fit_id: str,
        rack: str,
        type_id: int,
        state: str | None = None,
        charge_type_id: int | None = None,
        index: int | None = None,
    ) -> dict[str, Any]:
        try:
            mutations.equip_module(
                store.get_fit(fit_id),
                rack,
                type_id,
                state=state,
                charge_type_id=charge_type_id,
                index=index,
            )
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Replace module at rack/index. Fit unchanged on hard errors.")
    def replace_module(
        fit_id: str,
        rack: str,
        index: int,
        type_id: int,
        state: str | None = None,
        charge_type_id: int | None = None,
    ) -> dict[str, Any]:
        try:
            mutations.replace_module(
                store.get_fit(fit_id),
                rack,
                index,
                type_id,
                state=state,
                charge_type_id=charge_type_id,
            )
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove module at rack/index.")
    def remove_module(fit_id: str, rack: str, index: int) -> dict[str, Any]:
        try:
            mutations.remove_module(store.get_fit(fit_id), rack, index)
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set module state: offline|online|active|overload.")
    def set_module_state(fit_id: str, rack: str, index: int, state: str) -> dict[str, Any]:
        try:
            mutations.set_module_state(store.get_fit(fit_id), rack, index, state)
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set or clear charge on module at rack/index.")
    def set_charge(
        fit_id: str, rack: str, index: int, charge_type_id: int | None = None
    ) -> dict[str, Any]:
        try:
            mutations.set_charge(store.get_fit(fit_id), rack, index, charge_type_id)
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add a rig by type_id.")
    def add_rig(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eos import Rig, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="rig")
            try:
                fit.rigs.add(Rig(int(type_id)))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(type_id), "rig type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove one rig matching type_id.")
    def remove_rig(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            for rig in list(fit.rigs):
                if rig._type_id == int(type_id):
                    fit.rigs.remove(rig)
                    return {"fit_id": fit_id, "report": store.report(fit_id)}
            raise MutationError(f"No rig with type_id {type_id}")
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add a subsystem by type_id.")
    def add_subsystem(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eos import Subsystem, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="subsystem")
            try:
                fit.subsystems.add(Subsystem(int(type_id)))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(type_id), "subsystem type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove one subsystem matching type_id.")
    def remove_subsystem(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            for item in list(fit.subsystems):
                if item._type_id == int(type_id):
                    fit.subsystems.remove(item)
                    return {"fit_id": fit_id, "report": store.report(fit_id)}
            raise MutationError(f"No subsystem with type_id {type_id}")
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add quantity drones (default 1). state: offline|online|active.")
    def add_drone(
        fit_id: str,
        type_id: int,
        state: str | None = "active",
        quantity: int = 1,
    ) -> dict[str, Any]:
        try:
            from eos import Drone, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError
            from eve_fit_mcp.state_map import parse_state

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="drone")
            st = parse_state(state, default=parse_state("active"))
            for _ in range(max(1, int(quantity))):
                try:
                    fit.drones.add(Drone(int(type_id), state=st))
                except TypeFetchError as exc:
                    raise InvalidTypeError(int(type_id), "drone type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove up to quantity drones of type_id.")
    def remove_drone(fit_id: str, type_id: int, quantity: int = 1) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            remaining = max(1, int(quantity))
            removed = 0
            for drone in list(fit.drones):
                if drone._type_id == int(type_id) and remaining > 0:
                    fit.drones.remove(drone)
                    remaining -= 1
                    removed += 1
            if removed == 0:
                raise MutationError(f"No drones with type_id {type_id}")
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set state for all drones of type_id.")
    def set_drone_state(fit_id: str, type_id: int, state: str) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError
            from eve_fit_mcp.state_map import parse_state

            fit = store.get_fit(fit_id)
            st = parse_state(state)
            matched = False
            for drone in fit.drones:
                if drone._type_id == int(type_id):
                    drone.state = st
                    matched = True
            if not matched:
                raise MutationError(f"No drones with type_id {type_id}")
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add a fighter squad.")
    def add_fighter(
        fit_id: str, type_id: int, state: str | None = "active"
    ) -> dict[str, Any]:
        try:
            from eos import FighterSquad, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError
            from eve_fit_mcp.state_map import parse_state

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="fighter")
            try:
                fit.fighters.add(
                    FighterSquad(int(type_id), state=parse_state(state, default=parse_state("active")))
                )
            except TypeFetchError as exc:
                raise InvalidTypeError(int(type_id), "fighter type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove one fighter squad of type_id.")
    def remove_fighter(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            for item in list(fit.fighters):
                if item._type_id == int(type_id):
                    fit.fighters.remove(item)
                    return {"fit_id": fit_id, "report": store.report(fit_id)}
            raise MutationError(f"No fighter with type_id {type_id}")
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set state for fighter squads of type_id.")
    def set_fighter_state(fit_id: str, type_id: int, state: str) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError
            from eve_fit_mcp.state_map import parse_state

            fit = store.get_fit(fit_id)
            st = parse_state(state)
            matched = False
            for item in fit.fighters:
                if item._type_id == int(type_id):
                    item.state = st
                    matched = True
            if not matched:
                raise MutationError(f"No fighter with type_id {type_id}")
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add an implant.")
    def add_implant(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eos import Implant, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="implant")
            try:
                fit.implants.add(Implant(int(type_id)))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(type_id), "implant type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove implant of type_id.")
    def remove_implant(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            for item in list(fit.implants):
                if item._type_id == int(type_id):
                    fit.implants.remove(item)
                    return {"fit_id": fit_id, "report": store.report(fit_id)}
            raise MutationError(f"No implant with type_id {type_id}")
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Add a booster.")
    def add_booster(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eos import Booster, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            require_type(int(type_id), kind="booster")
            try:
                fit.boosters.add(Booster(int(type_id)))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(type_id), "booster type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Remove booster of type_id.")
    def remove_booster(fit_id: str, type_id: int) -> dict[str, Any]:
        try:
            from eve_fit_mcp.errors import MutationError

            fit = store.get_fit(fit_id)
            for item in list(fit.boosters):
                if item._type_id == int(type_id):
                    fit.boosters.remove(item)
                    return {"fit_id": fit_id, "report": store.report(fit_id)}
            raise MutationError(f"No booster with type_id {type_id}")
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(description="Set system effect beacon type_id, or null to clear.")
    def set_effect_beacon(fit_id: str, type_id: int | None = None) -> dict[str, Any]:
        try:
            from eos import EffectBeacon, TypeFetchError
            from eve_fit_mcp.errors import InvalidTypeError

            fit = store.get_fit(fit_id)
            if type_id is None:
                fit.effect_beacon = None
            else:
                require_type(int(type_id), kind="effect_beacon")
                try:
                    fit.effect_beacon = EffectBeacon(int(type_id))
                except TypeFetchError as exc:
                    raise InvalidTypeError(int(type_id), "beacon type not in data") from exc
            return {"fit_id": fit_id, "report": store.report(fit_id)}
        except Exception as exc:
            _raise(exc)
            raise

    # --- Evaluation ---

    @mcp.tool(
        description=(
            "Return FitReport (DPS/EHP/CPU/PG/slots/validation). options may include "
            "dps_reload, dmg_profile, tgt_resists, dps_filters. Does not mutate the fit."
        )
    )
    def get_stats(fit_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            entry = store.get_entry(fit_id)
            if options is not None:
                entry.stats_options = options
            return store.report(fit_id, options=options)
        except Exception as exc:
            _raise(exc)
            raise

    @mcp.tool(
        description=(
            "Validate fit. Returns ok + structured errors mapped from Eos Restriction names. "
            "Optional skip_checks: list of restriction names."
        )
    )
    def validate_fit(
        fit_id: str, skip_checks: list[str] | None = None
    ) -> dict[str, Any]:
        try:
            fit = store.get_fit(fit_id)
            errors = collect_validation_errors(fit, skip_checks=skip_checks)
            return {
                "fit_id": fit_id,
                "ok": len(errors) == 0,
                "validation_errors": errors,
            }
        except Exception as exc:
            _raise(exc)
            raise

    # --- Static data ---

    @mcp.tool(
        description=(
            "Download / refresh TQ Phobos staticdata from the eve-fit-mcp GitHub release "
            "asset (or EOS_STATICDATA_URL), replace the local cache dump, clear the Eos "
            "cache, and re-bootstrap. Use after patches or when dumps look stale. "
            "force=true re-downloads even if a dump is already present."
        )
    )
    def refresh_static_data(force: bool = True) -> dict[str, Any]:
        try:
            from eve_fit_mcp.eos_bootstrap import bootstrap_eos
            from eve_fit_mcp.staticdata import refresh_staticdata

            result = refresh_staticdata(force=force)
            # Prefer the downloaded dump for subsequent fits
            os.environ["EOS_PHOBOS_PATH"] = result["staticdata_path"]
            os.environ["EOS_CACHE_PATH"] = result["cache_path"]
            bootstrap_eos(
                phobos_path=result["staticdata_path"],
                cache_path=result["cache_path"],
                force=True,
                allow_download=False,
            )
            result["bootstrapped"] = True
            return result
        except Exception as exc:
            _raise(exc)
            raise
