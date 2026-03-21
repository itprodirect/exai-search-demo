from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Dict, Mapping

from .config import default_config


def run_eval_workflow(
    args: argparse.Namespace,
    *,
    prepare_runtime: Callable[[argparse.Namespace], tuple[Dict[str, Any], Dict[str, float], Any]],
    runtime_metadata: Callable[[Any], Dict[str, Any]],
    namespace_with_overrides: Callable[..., argparse.Namespace],
    run_eval_workflow_impl: Callable[..., Dict[str, Any]],
    run_id_override: str | None = None,
    search_type_override: str | None = None,
    compare_to_run_id: str | None = None,
    compare_base_dir: str | None = None,
) -> Dict[str, Any]:
    workflow_args = namespace_with_overrides(
        args,
        run_id=run_id_override
        if run_id_override is not None
        else getattr(args, "run_id", None),
        search_type=search_type_override
        if search_type_override is not None
        else getattr(args, "search_type", default_config()["search_type"]),
    )
    config, pricing, runtime = prepare_runtime(workflow_args)
    resolved_compare_to_run_id = (
        compare_to_run_id
        if compare_to_run_id is not None
        else getattr(args, "compare_to_run_id", None)
    )
    resolved_compare_base_dir = (
        compare_base_dir
        if compare_base_dir is not None
        else getattr(args, "compare_base_dir", None)
    )
    return run_eval_workflow_impl(
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=runtime_metadata(runtime),
        suite=getattr(args, "suite", None),
        queries_file=getattr(args, "queries_file", None),
        limit=getattr(args, "limit", None),
        compare_to_run_id=resolved_compare_to_run_id,
        compare_base_dir=resolved_compare_base_dir,
    )


def run_compare_search_types_workflow(
    args: argparse.Namespace,
    *,
    load_env: Callable[[], None],
    resolve_runtime: Callable[[str, str | None], Any],
    run_id_suffix_for_search_type: Callable[[str], str],
    normalized_query_suite: Callable[[str | None], str],
    eval_workflow_runner: Callable[..., Dict[str, Any]],
) -> Dict[str, Any]:
    baseline_type = str(args.baseline_type or "").strip()
    candidate_type = str(args.candidate_type or "").strip()
    if not baseline_type or not candidate_type:
        raise ValueError("Both --baseline-type and --candidate-type must be non-empty.")
    if baseline_type == candidate_type:
        raise ValueError("Baseline and candidate search types must differ.")

    load_env()
    base_runtime = resolve_runtime(args.mode, getattr(args, "run_id", None))
    base_run_id = base_runtime.run_id
    baseline_run_id = f"{base_run_id}-{run_id_suffix_for_search_type(baseline_type)}"
    candidate_run_id = f"{base_run_id}-{run_id_suffix_for_search_type(candidate_type)}"

    baseline_payload = eval_workflow_runner(
        args,
        run_id_override=baseline_run_id,
        search_type_override=baseline_type,
    )
    candidate_payload = eval_workflow_runner(
        args,
        run_id_override=candidate_run_id,
        search_type_override=candidate_type,
        compare_to_run_id=baseline_run_id,
        compare_base_dir=args.artifact_dir,
    )

    return {
        "workflow": "compare-search-types",
        "base_run_id": base_run_id,
        "query_suite": normalized_query_suite(getattr(args, "suite", None)),
        "baseline_search_type": baseline_type,
        "candidate_search_type": candidate_type,
        "baseline_run": baseline_payload,
        "candidate_run": candidate_payload,
        "comparison": candidate_payload.get("comparison"),
        "comparison_markdown_path": candidate_payload.get("comparison_markdown_path"),
    }


def emit_compare_search_types_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    comparison = (
        payload.get("comparison")
        if isinstance(payload.get("comparison"), Mapping)
        else {}
    )
    deltas = (
        comparison.get("deltas")
        if isinstance(comparison.get("deltas"), Mapping)
        else {}
    )
    baseline_run = (
        payload.get("baseline_run")
        if isinstance(payload.get("baseline_run"), Mapping)
        else {}
    )
    candidate_run = (
        payload.get("candidate_run")
        if isinstance(payload.get("candidate_run"), Mapping)
        else {}
    )
    print("workflow: compare-search-types")
    print(f"query_suite: {payload['query_suite']}")
    print(f"baseline_run_id: {baseline_run.get('run_id')}")
    print(f"candidate_run_id: {candidate_run.get('run_id')}")
    print(f"baseline_search_type: {payload['baseline_search_type']}")
    print(f"candidate_search_type: {payload['candidate_search_type']}")
    print(f"baseline_artifact_dir: {baseline_run.get('artifact_dir')}")
    print(f"candidate_artifact_dir: {candidate_run.get('artifact_dir')}")
    print(
        "delta_observed_confidence_score: "
        f"{float(deltas.get('observed_confidence_score') or 0.0):+.3f}"
    )
    print(
        "delta_observed_failure_rate: "
        f"{float(deltas.get('observed_failure_rate') or 0.0):+.3f}"
    )
    print(f"comparison_markdown: {payload.get('comparison_markdown_path')}")
