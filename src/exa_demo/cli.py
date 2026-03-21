from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional, Sequence

from dotenv import load_dotenv

from .cache import SqliteCacheStore
from .cli_eval import (
    emit_compare_search_types_payload,
    run_compare_search_types_workflow,
    run_eval_workflow,
)
from .cli_parser import (
    apply_search_overrides as _apply_search_overrides,
    build_parser as build_cli_parser,
    namespace_with_overrides as _namespace_with_overrides,
    run_id_suffix_for_search_type as _run_id_suffix_for_search_type,
)
from .config import RuntimeState, default_config, default_pricing
from .cli_runtime import resolve_runtime as _resolve_runtime_impl, runtime_metadata as _runtime_metadata_impl
from .endpoint_workflows import (
    emit_answer_payload,
    emit_find_similar_payload,
    emit_research_payload,
    emit_structured_search_payload,
    run_answer_workflow,
    run_find_similar_workflow,
    run_research_workflow,
    run_structured_search_workflow,
)
from .ranked_workflows import emit_eval_payload, emit_search_payload, normalized_query_suite, run_eval_workflow as run_ranked_eval_workflow, run_search_workflow


def build_parser() -> argparse.ArgumentParser:
    return build_cli_parser(
        handlers={
            "search": run_search_command,
            "eval": run_eval_command,
            "answer": run_answer_command,
            "research": run_research_command,
            "find-similar": run_find_similar_command,
            "structured-search": run_structured_search_command,
            "compare-search-types": run_compare_search_types_command,
            "budget": run_budget_command,
        }
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


def run_search_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    payload, record = run_search_workflow(
        query=args.query,
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
    )
    emit_search_payload(payload, record=record, as_json=bool(args.as_json))
    return 0


def run_eval_command(args: argparse.Namespace) -> int:
    payload = run_eval_workflow(
        args,
        prepare_runtime=_prepare_runtime,
        runtime_metadata=_runtime_metadata,
        namespace_with_overrides=_namespace_with_overrides,
        run_eval_workflow_impl=run_ranked_eval_workflow,
    )
    emit_eval_payload(payload, as_json=bool(args.as_json))
    return 0


def run_answer_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    payload = run_answer_workflow(
        query=args.query,
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
    )
    emit_answer_payload(payload, as_json=bool(args.as_json))
    return 0


def run_research_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    payload = run_research_workflow(
        query=args.query,
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
    )
    emit_research_payload(payload, as_json=bool(args.as_json))
    return 0


def run_find_similar_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    payload = run_find_similar_workflow(
        seed_url=args.url,
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
    )
    emit_find_similar_payload(payload, as_json=bool(args.as_json))
    return 0


def run_structured_search_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    payload = run_structured_search_workflow(
        query=args.query,
        schema_file=args.schema_file,
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
    )
    emit_structured_search_payload(payload, as_json=bool(args.as_json))
    return 0


def run_compare_search_types_command(args: argparse.Namespace) -> int:
    payload = run_compare_search_types_workflow(
        args,
        load_env=load_dotenv,
        resolve_runtime=_resolve_runtime,
        run_id_suffix_for_search_type=_run_id_suffix_for_search_type,
        normalized_query_suite=normalized_query_suite,
        eval_workflow_runner=lambda command_args, **overrides: run_eval_workflow(
            command_args,
            prepare_runtime=_prepare_runtime,
            runtime_metadata=_runtime_metadata,
            namespace_with_overrides=_namespace_with_overrides,
            run_eval_workflow_impl=run_ranked_eval_workflow,
            **overrides,
        ),
    )
    emit_compare_search_types_payload(payload, as_json=bool(args.as_json))
    return 0


def run_budget_command(args: argparse.Namespace) -> int:
    cache_store = SqliteCacheStore(args.sqlite_path, float(args.cache_ttl_hours))
    summary = cache_store.spend_so_far(run_id=args.run_id)
    ledger_df = cache_store.ledger_summary(run_id=args.run_id)
    payload = {
        "run_id": args.run_id,
        "summary": summary,
        "ledger_rows": int(len(ledger_df.index)),
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    scope = args.run_id or "all runs"
    print(f"budget scope: {scope}")
    print(json.dumps(summary, indent=2))
    print(f"ledger_rows: {len(ledger_df.index)}")
    return 0


def _prepare_runtime(args: argparse.Namespace) -> tuple[Dict[str, Any], Dict[str, float], RuntimeState]:
    load_dotenv()
    config = default_config()
    pricing = default_pricing()
    _apply_search_overrides(config, pricing, args)
    runtime = _resolve_runtime(args.mode, getattr(args, "run_id", None))
    return config, pricing, runtime


def _resolve_runtime(mode: str, run_id: Optional[str]) -> RuntimeState:
    return _resolve_runtime_impl(mode, run_id)


def _runtime_metadata(runtime: RuntimeState) -> Dict[str, Any]:
    return _runtime_metadata_impl(runtime)
