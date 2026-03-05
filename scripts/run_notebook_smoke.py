from __future__ import annotations

import asyncio
import argparse
import os
import sys
import tempfile
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute exa_people_search_eval.ipynb end-to-end."
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "live", "auto"],
        default="smoke",
        help=(
            "Execution mode: smoke=no network/billing, live=real API calls, "
            "auto=live if EXA_API_KEY is present else smoke."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-cell execution timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    nb_path = repo_root / "exa_people_search_eval.ipynb"

    if not nb_path.exists():
        print(f"Notebook not found: {nb_path}", file=sys.stderr)
        return 1

    exa_key = (os.getenv("EXA_API_KEY") or "").strip()
    mode = args.mode
    if mode == "auto":
        mode = "live" if exa_key else "smoke"

    if mode == "smoke":
        os.environ["EXA_SMOKE_NO_NETWORK"] = "1"
        print("Mode=smoke: EXA_SMOKE_NO_NETWORK=1 (no network/API billing).")
    else:
        os.environ["EXA_SMOKE_NO_NETWORK"] = "0"
        if not exa_key:
            print("Mode=live requested but EXA_API_KEY is missing.", file=sys.stderr)
            return 1
        print("Mode=live: using Exa API (cache may reduce rebilling).")

    # Some Windows/sandbox environments restrict Jupyter's default runtime dir ACL writes.
    runtime_dir = Path(tempfile.mkdtemp(prefix="jupyter-runtime-"))
    ipython_dir = Path(tempfile.mkdtemp(prefix="ipython-"))
    os.environ["JUPYTER_RUNTIME_DIR"] = str(runtime_dir)
    os.environ["IPYTHONDIR"] = str(ipython_dir)
    os.environ.setdefault("JUPYTER_ALLOW_INSECURE_WRITES", "true")

    # Sandbox/CI workaround: Windows ACL restriction calls can fail even on writable temp paths.
    try:
        import jupyter_core.paths as jupyter_paths

        if hasattr(jupyter_paths, "win32_restrict_file_to_user"):
            jupyter_paths.win32_restrict_file_to_user = lambda *_args, **_kwargs: None
    except Exception:
        pass

    if os.name == "nt" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    with nb_path.open("r", encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    client = NotebookClient(
        nb,
        timeout=args.timeout,
        kernel_name="python3",
        resources={"metadata": {"path": str(repo_root)}},
        allow_errors=False,
    )
    client.execute()

    print("Notebook execution completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())