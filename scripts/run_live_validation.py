from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded set of Exa workflow validations through the CLI."
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "live", "auto"],
        default="auto",
        help="Execution mode: smoke=no network/billing, live=real API calls, auto=live if EXA_API_KEY is present else smoke.",
    )
    parser.add_argument(
        "--artifact-dir",
        default="live-validation-artifacts",
        help="Base directory for validation artifacts.",
    )
    parser.add_argument(
        "--run-id-prefix",
        help="Optional prefix for generated run ids. Defaults to a UTC timestamped live-validation label.",
    )
    parser.add_argument(
        "--include-comparison",
        action="store_true",
        help="Also run the compare-search-types workflow. This is more expensive than the default validation set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = repo_root / args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    mode = _resolve_mode(args.mode)
    if mode == "live" and not (os.getenv("EXA_API_KEY") or "").strip():
        print("Mode=live requested but EXA_API_KEY is missing.", file=sys.stderr)
        return 1

    os.environ["EXA_SMOKE_NO_NETWORK"] = "1" if mode == "smoke" else "0"
    print(
        "Mode=smoke: EXA_SMOKE_NO_NETWORK=1 (no network/API billing)."
        if mode == "smoke"
        else "Mode=live: using Exa API for bounded manual validation."
    )

    run_id_prefix = args.run_id_prefix or _default_run_id_prefix()
    commands = build_validation_commands(
        repo_root=repo_root,
        artifact_dir=artifact_dir,
        run_id_prefix=run_id_prefix,
        mode=mode,
        include_comparison=bool(args.include_comparison),
    )

    summary_rows: List[Dict[str, Any]] = []
    for command in commands:
        summary_rows.append(
            _run_validation_command(
                command,
                artifact_dir=artifact_dir,
                mode=mode,
            )
        )

    summary_path = artifact_dir / "validation_summary.json"
    summary_payload = {
        "mode": mode,
        "run_id_prefix": run_id_prefix,
        "artifact_dir": str(artifact_dir),
        "commands": summary_rows,
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Validation summary written to: {summary_path}")
    return 0


def build_validation_commands(
    *,
    repo_root: Path,
    artifact_dir: Path,
    run_id_prefix: str,
    mode: str,
    include_comparison: bool,
) -> List[Dict[str, Any]]:
    schema_path = repo_root / "assets" / "live_validation_schema.json"
    base_command = [sys.executable, "-m", "exa_demo"]

    commands: List[Dict[str, Any]] = [
        {
            "name": "search",
            "run_id": f"{run_id_prefix}-search",
            "argv": base_command
            + [
                "search",
                "forensic engineer insurance expert witness",
                "--mode",
                mode,
                "--run-id",
                f"{run_id_prefix}-search",
                "--artifact-dir",
                str(artifact_dir),
                "--json",
            ],
        },
        {
            "name": "answer",
            "run_id": f"{run_id_prefix}-answer",
            "argv": base_command
            + [
                "answer",
                "What is the Florida appraisal clause dispute process?",
                "--mode",
                mode,
                "--run-id",
                f"{run_id_prefix}-answer",
                "--artifact-dir",
                str(artifact_dir),
                "--json",
            ],
        },
        {
            "name": "research",
            "run_id": f"{run_id_prefix}-research",
            "argv": base_command
            + [
                "research",
                "Summarize the Florida CAT market outlook.",
                "--mode",
                mode,
                "--run-id",
                f"{run_id_prefix}-research",
                "--artifact-dir",
                str(artifact_dir),
                "--json",
            ],
        },
        {
            "name": "structured-search",
            "run_id": f"{run_id_prefix}-structured",
            "argv": base_command
            + [
                "structured-search",
                "independent adjuster florida catastrophe claims",
                "--schema-file",
                str(schema_path),
                "--mode",
                mode,
                "--run-id",
                f"{run_id_prefix}-structured",
                "--artifact-dir",
                str(artifact_dir),
                "--json",
            ],
        },
        {
            "name": "find-similar",
            "run_id": f"{run_id_prefix}-find-similar",
            "argv": base_command
            + [
                "find-similar",
                "https://www.merlinlawgroup.com/",
                "--mode",
                mode,
                "--run-id",
                f"{run_id_prefix}-find-similar",
                "--artifact-dir",
                str(artifact_dir),
                "--json",
            ],
        },
    ]

    if include_comparison:
        commands.append(
            {
                "name": "compare-search-types",
                "run_id": f"{run_id_prefix}-compare",
                "argv": base_command
                + [
                    "compare-search-types",
                    "--mode",
                    mode,
                    "--run-id",
                    f"{run_id_prefix}-compare",
                    "--artifact-dir",
                    str(artifact_dir),
                    "--suite",
                    "forensic_and_damage_engineering",
                    "--limit",
                    "2",
                    "--baseline-type",
                    "deep",
                    "--candidate-type",
                    "deep-reasoning",
                    "--json",
                ],
            }
        )

    return commands


def _run_validation_command(
    command: Dict[str, Any],
    *,
    artifact_dir: Path,
    mode: str,
) -> Dict[str, Any]:
    argv = [str(part) for part in command["argv"]]
    print(f"Running validation command: {command['name']}")
    completed = subprocess.run(
        argv,
        cwd=artifact_dir.parents[0],
        capture_output=True,
        text=True,
        check=False,
        env=dict(os.environ),
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        raise RuntimeError(f"Validation command failed: {command['name']}")

    stdout_payload = _parse_json_output(completed.stdout, command["name"])
    return {
        "name": command["name"],
        "mode": mode,
        "run_id": command["run_id"],
        "artifact_dir": stdout_payload.get("artifact_dir"),
        "request_id": stdout_payload.get("request_id"),
    }


def _parse_json_output(raw_output: str, command_name: str) -> Dict[str, Any]:
    try:
        payload = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Validation command did not emit JSON: {command_name}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Validation command emitted unexpected payload type: {command_name}")
    return payload


def _default_run_id_prefix() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"live-validation-{timestamp}"


def _resolve_mode(mode: str) -> str:
    if mode != "auto":
        return mode
    return "live" if (os.getenv("EXA_API_KEY") or "").strip() else "smoke"


if __name__ == "__main__":
    raise SystemExit(main())
