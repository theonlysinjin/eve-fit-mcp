"""Phobos JSON data handler that supports multi-part dumps (types.0.json, …)."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from glob import glob

from eos.data_handler.base import BaseDataHandler
from eos.util.repr import make_repr_str

_PART_RE = re.compile(r"^(?P<stem>.+)\.(?P<idx>\d+)\.json$")


class PhobosJsonDataHandler(BaseDataHandler):
    """Load Phobos dumps as single files or merged ``name.N.json`` parts.

    ``basepath`` should be the Phobos output root containing ``fsd_built/``,
    ``fsd_lite/``, and ``phobos/`` (e.g. Pyfa ``staticdata/``).
    """

    def __init__(self, basepath: str):
        self.basepath = os.path.abspath(basepath)

    def get_evetypes(self):
        return self._values("fsd_built", "types")

    def get_evegroups(self):
        return self._values("fsd_built", "groups")

    def get_dgmattribs(self):
        return self._values("fsd_built", "dogmaattributes")

    def get_dgmtypeattribs(self):
        rows = []
        for type_id, type_data in self._mapping("fsd_built", "typedogma").items():
            type_id = int(type_id)
            for tdrow in type_data.get("dogmaAttributes", ()):
                rows.append(
                    {
                        "typeID": type_id,
                        "attributeID": tdrow["attributeID"],
                        "value": tdrow["value"],
                    }
                )
        return rows

    def get_dgmeffects(self):
        return self._values("fsd_built", "dogmaeffects")

    def get_dgmtypeeffects(self):
        rows = []
        for type_id, type_data in self._mapping("fsd_built", "typedogma").items():
            type_id = int(type_id)
            for tdrow in type_data.get("dogmaEffects", ()):
                rows.append(
                    {
                        "typeID": type_id,
                        "effectID": tdrow["effectID"],
                        "isDefault": bool(tdrow["isDefault"]),
                    }
                )
        return rows

    def get_dbuffcollections(self):
        rows = []
        dbuffs = self._mapping("fsd_lite", "dbuffcollections", required=False)
        for buff_id, row in dbuffs.items():
            row = dict(row)
            row["buffID"] = int(buff_id)
            rows.append(row)
        return rows

    def get_skillreqs(self):
        rows = []
        skillreq_datas = self._mapping("fsd_built", "requiredskillsfortypes")
        for type_id, skillreq_data in skillreq_datas.items():
            type_id = int(type_id)
            for skill_type_id, skill_level in skillreq_data.items():
                rows.append(
                    {
                        "typeID": type_id,
                        "skillTypeID": int(skill_type_id),
                        "level": skill_level,
                    }
                )
        return rows

    def get_typefighterabils(self):
        rows = []
        fighter_abils = self._mapping(
            "fsd_lite", "fighterabilitiesbytype", required=False
        )
        for type_id, type_abilities in fighter_abils.items():
            for _ability_slot, ability_data in type_abilities.items():
                ability_row = {"typeID": int(type_id)}
                self._collapse_dict(ability_data, ability_row)
                rows.append(ability_row)
        return rows

    def get_version(self):
        metadata = self._load("phobos", "metadata")
        if isinstance(metadata, Mapping):
            rows = list(metadata.values())
        else:
            rows = list(metadata)
        for row in rows:
            if row.get("field_name") == "client_build":
                return row["field_value"]
        return None

    def _values(self, miner: str, filename: str) -> list:
        data = self._load(miner, filename)
        if isinstance(data, Mapping):
            return [dict(v) if isinstance(v, Mapping) else v for v in data.values()]
        return [dict(v) if isinstance(v, Mapping) else v for v in data]

    def _mapping(self, miner: str, filename: str, *, required: bool = True) -> dict:
        try:
            data = self._load(miner, filename)
        except FileNotFoundError:
            if required:
                raise
            return {}
        if isinstance(data, Mapping):
            return {k: (dict(v) if isinstance(v, Mapping) else v) for k, v in data.items()}
        raise TypeError(f"Expected mapping for {miner}/{filename}, got {type(data)}")

    def _load(self, miner: str, filename: str):
        directory = os.path.join(self.basepath, miner)
        single = os.path.join(directory, f"{filename}.json")
        if os.path.isfile(single):
            with open(single, encoding="utf8") as fh:
                return json.load(fh)

        parts = []
        for path in glob(os.path.join(directory, f"{filename}.*.json")):
            base = os.path.basename(path)
            match = _PART_RE.match(base)
            if not match or match.group("stem") != filename:
                continue
            parts.append((int(match.group("idx")), path))
        if not parts:
            raise FileNotFoundError(
                f"No Phobos data for {miner}/{filename} under {self.basepath}"
            )
        parts.sort(key=lambda item: item[0])

        merged = None
        for _idx, path in parts:
            with open(path, encoding="utf8") as fh:
                chunk = json.load(fh)
            if merged is None:
                merged = chunk
            elif isinstance(merged, dict) and isinstance(chunk, dict):
                merged.update(chunk)
            elif isinstance(merged, list) and isinstance(chunk, list):
                merged.extend(chunk)
            else:
                raise TypeError(
                    f"Cannot merge Phobos parts of incompatible types for {filename}"
                )
        return merged

    @staticmethod
    def _collapse_dict(src, tgt):
        for key, value in src.items():
            if isinstance(value, Mapping):
                PhobosJsonDataHandler._collapse_dict(value, tgt)
            elif key not in tgt:
                tgt[key] = value

    def __repr__(self):
        return make_repr_str(self, ["basepath"])
