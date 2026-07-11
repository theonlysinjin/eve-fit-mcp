"""MCP entrypoint for the Eos fitting server."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from eve_fit_mcp.eos_bootstrap import bootstrap_eos
from eve_fit_mcp.fit_store import FitStore
from eve_fit_mcp.tools import AGENT_CONTRACT, register_tools

INSTRUCTIONS = f"""
Eos Fitting MCP — evaluate EVE Online ship fits using the Eos engine.

{AGENT_CONTRACT}

Typical loop:
1. create_fit(ship_type_id, skills) or create_fit + apply_all_skills_5
2. equip_module / add_drone / add_rig for an approximate fit
3. get_stats / read mutation FitReport
4. Change one module or state; compare reports
5. Repeat until constraints are met

Type IDs are canonical. Mutations that fail hard (bad type ID, wrong rack)
leave the fit unchanged and return a tool error. Soft validation failures
(CPU, skills, slots) still apply the change and appear in FitReport.validation_errors.
""".strip()


def create_server() -> FastMCP:
    bootstrap_eos()
    store = FitStore(
        max_fits=int(os.environ.get("EOS_MAX_FITS", "100")),
        ttl_seconds=(
            float(os.environ["EOS_FIT_TTL"])
            if os.environ.get("EOS_FIT_TTL")
            else None
        ),
    )
    mcp = FastMCP("eos-fitting", instructions=INSTRUCTIONS)
    register_tools(mcp, store)
    return mcp


def main() -> None:
    mcp = create_server()
    mcp.run()


if __name__ == "__main__":
    main()
