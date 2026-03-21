from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .config import RuntimeState, load_runtime_state


def resolve_runtime(mode: str, run_id: Optional[str]) -> RuntimeState:
    env = dict(os.environ)
    exa_api_key = (env.get("EXA_API_KEY") or "").strip()
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "live" if exa_api_key else "smoke"

    env["EXA_SMOKE_NO_NETWORK"] = "1" if resolved_mode == "smoke" else "0"
    if run_id:
        env["EXA_RUN_ID"] = run_id
    return load_runtime_state(env=env)


def runtime_metadata(runtime: RuntimeState) -> Dict[str, Any]:
    execution_mode = "smoke" if runtime.smoke_no_network else "live"
    return {
        "execution_mode": execution_mode,
        "smoke_no_network": bool(runtime.smoke_no_network),
        "network_access": not bool(runtime.smoke_no_network),
        "api_key_configured": bool(runtime.exa_api_key),
    }
