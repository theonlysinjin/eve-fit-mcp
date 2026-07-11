"""In-memory fit store: fit_id → Fit (+ metadata)."""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from eos import (
    Booster,
    Charge,
    Drone,
    EffectBeacon,
    FighterSquad,
    Fit,
    Implant,
    ModuleHigh,
    ModuleLow,
    ModuleMid,
    Rig,
    Ship,
    Skill,
    Stance,
    Subsystem,
    TypeFetchError,
)

from eve_fit_mcp.errors import FitNotFoundError, InvalidTypeError
from eve_fit_mcp.report import build_report
from eve_fit_mcp.typecheck import require_type


@dataclass
class FitEntry:
    fit: Fit
    label: str | None = None
    created_at: float = field(default_factory=time.time)
    stats_options: dict[str, Any] = field(default_factory=dict)


class FitStore:
    def __init__(self, *, max_fits: int = 100, ttl_seconds: float | None = None):
        self._fits: dict[str, FitEntry] = {}
        self.max_fits = max_fits
        self.ttl_seconds = ttl_seconds

    def _purge(self) -> None:
        if self.ttl_seconds is None:
            return
        now = time.time()
        expired = [
            fid
            for fid, entry in self._fits.items()
            if now - entry.created_at > self.ttl_seconds
        ]
        for fid in expired:
            del self._fits[fid]

    def get_entry(self, fit_id: str) -> FitEntry:
        self._purge()
        try:
            return self._fits[fit_id]
        except KeyError as exc:
            raise FitNotFoundError(fit_id) from exc

    def get_fit(self, fit_id: str) -> Fit:
        return self.get_entry(fit_id).fit

    def report(self, fit_id: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        entry = self.get_entry(fit_id)
        opts = options if options is not None else entry.stats_options
        return build_report(fit_id, entry.fit, label=entry.label, options=opts)

    def create(
        self,
        ship_type_id: int,
        skills: dict[int | str, int] | None = None,
        label: str | None = None,
    ) -> dict[str, Any]:
        self._purge()
        if len(self._fits) >= self.max_fits:
            # Drop oldest
            oldest = min(self._fits.items(), key=lambda kv: kv[1].created_at)
            del self._fits[oldest[0]]

        fit = Fit()
        require_type(int(ship_type_id), kind="ship")
        try:
            fit.ship = Ship(int(ship_type_id))
        except TypeFetchError as exc:
            raise InvalidTypeError(int(ship_type_id), "ship type not in data") from exc

        if skills:
            self._apply_skills(fit, skills, replace=True)

        fit_id = str(uuid.uuid4())
        self._fits[fit_id] = FitEntry(fit=fit, label=label)
        return {"fit_id": fit_id, "report": self.report(fit_id)}

    def clone(self, fit_id: str) -> dict[str, Any]:
        entry = self.get_entry(fit_id)
        new_fit = self._clone_fit(entry.fit)
        new_id = str(uuid.uuid4())
        label = f"{entry.label} (copy)" if entry.label else None
        self._fits[new_id] = FitEntry(
            fit=new_fit,
            label=label,
            stats_options=copy.deepcopy(entry.stats_options),
        )
        return {"fit_id": new_id, "report": self.report(new_id)}

    def delete(self, fit_id: str) -> dict[str, Any]:
        self.get_entry(fit_id)  # ensure exists
        del self._fits[fit_id]
        return {"deleted": True, "fit_id": fit_id}

    def list_fits(self) -> list[dict[str, Any]]:
        self._purge()
        result = []
        for fit_id, entry in self._fits.items():
            ship = entry.fit.ship
            result.append(
                {
                    "fit_id": fit_id,
                    "ship_type_id": int(ship._type_id) if ship else None,
                    "label": entry.label,
                }
            )
        return result

    def reset(self, fit_id: str, ship_type_id: int | None = None) -> dict[str, Any]:
        entry = self.get_entry(fit_id)
        fit = entry.fit
        skills = {s._type_id: s.level for s in fit.skills}

        new_fit = Fit()
        target_ship = ship_type_id
        if target_ship is None and fit.ship is not None:
            target_ship = fit.ship._type_id
        if target_ship is not None:
            require_type(int(target_ship), kind="ship")
            try:
                new_fit.ship = Ship(int(target_ship))
            except TypeFetchError as exc:
                raise InvalidTypeError(int(target_ship), "ship type not in data") from exc
        self._apply_skills(new_fit, skills, replace=True)
        entry.fit = new_fit
        return {"fit_id": fit_id, "report": self.report(fit_id)}

    @staticmethod
    def _apply_skills(
        fit: Fit,
        skills: dict[int | str, int],
        *,
        replace: bool,
    ) -> None:
        if replace:
            fit.skills.clear()
        for type_id, level in skills.items():
            tid = int(type_id)
            lvl = int(level)
            if lvl < 0 or lvl > 5:
                raise InvalidTypeError(tid, f"skill level must be 0-5, got {lvl}")
            require_type(tid, kind="skill")
            try:
                if tid in fit.skills:
                    fit.skills[tid].level = lvl
                else:
                    fit.skills.add(Skill(tid, level=lvl))
            except TypeFetchError as exc:
                raise InvalidTypeError(tid, "skill type not in data") from exc
            except ValueError:
                # race: already present
                fit.skills[tid].level = lvl

    def set_skills(self, fit_id: str, skills: dict[int | str, int]) -> dict[str, Any]:
        fit = self.get_fit(fit_id)
        self._apply_skills(fit, skills, replace=True)
        return {"fit_id": fit_id, "report": self.report(fit_id)}

    def set_skill(self, fit_id: str, type_id: int, level: int) -> dict[str, Any]:
        return self.set_skills_upsert(fit_id, {type_id: level})

    def set_skills_upsert(
        self, fit_id: str, skills: dict[int | str, int]
    ) -> dict[str, Any]:
        fit = self.get_fit(fit_id)
        self._apply_skills(fit, skills, replace=False)
        return {"fit_id": fit_id, "report": self.report(fit_id)}

    def clear_skills(self, fit_id: str) -> dict[str, Any]:
        fit = self.get_fit(fit_id)
        fit.skills.clear()
        return {"fit_id": fit_id, "report": self.report(fit_id)}

    @staticmethod
    def _clone_fit(src: Fit) -> Fit:
        dst = Fit()
        if src.ship is not None:
            dst.ship = Ship(src.ship._type_id)
        if src.stance is not None:
            dst.stance = Stance(src.stance._type_id)
        if src.effect_beacon is not None:
            dst.effect_beacon = EffectBeacon(src.effect_beacon._type_id)

        for skill in src.skills:
            dst.skills.add(Skill(skill._type_id, level=skill.level))

        for rack_name, cls in (
            ("high", ModuleHigh),
            ("mid", ModuleMid),
            ("low", ModuleLow),
        ):
            src_rack = getattr(src.modules, rack_name)
            dst_rack = getattr(dst.modules, rack_name)
            for index, module in enumerate(src_rack):
                if module is None:
                    continue
                charge = None
                if module.charge is not None:
                    charge = Charge(module.charge._type_id)
                new_mod = cls(module._type_id, state=module.state, charge=charge)
                dst_rack.place(index, new_mod)

        for rig in src.rigs:
            dst.rigs.add(Rig(rig._type_id))
        for sub in src.subsystems:
            dst.subsystems.add(Subsystem(sub._type_id))
        for drone in src.drones:
            dst.drones.add(Drone(drone._type_id, state=drone.state))
        for fighter in src.fighters:
            dst.fighters.add(FighterSquad(fighter._type_id, state=fighter.state))
        for implant in src.implants:
            dst.implants.add(Implant(implant._type_id))
        for booster in src.boosters:
            dst.boosters.add(Booster(booster._type_id))
        return dst
