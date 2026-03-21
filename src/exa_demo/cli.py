from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence

from dotenv import load_dotenv

from .cache import SqliteCacheStore
from .config import RuntimeState, default_config, default_pricing, load_runtime_state
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
from .ranked_workflows import (
    LEGACY_DEFAULT_SUITE_ALIAS,
    benchmark_suite_choices,
    emit_eval_payload,
    emit_search_payload,
    normalized_query_suite,
    run_eval_workflow as run_ranked_eval_workflow,
    run_search_workflow,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI for the Exa search demo package.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Run a single search query.")
    _add_common_runtime_args(search_parser)
    _add_common_search_args(search_parser)
    search_parser.add_argument("query", help="Query string to send to Exa.")
    search_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON instead of a text summary.")
    search_parser.set_defaults(handler=run_search_command)

    eval_parser = subparsers.add_parser("eval", help="Run the benchmark evaluation suite.")
    _add_common_runtime_args(eval_parser)
    _add_common_search_args(eval_parser)
    eval_parser.add_argument(
        "--suite",
        default=LEGACY_DEFAULT_SUITE_ALIAS,
        choices=benchmark_suite_choices(),
        help="Named benchmark suite to run.",
    )
    eval_parser.add_argument("--queries-file", help="Optional JSON file containing an array of query strings.")
    eval_parser.add_argument("--limit", type=int, help="Optional cap on the number of benchmark queries to execute.")
    eval_parser.add_argument("--compare-to-run-id", help="Optional baseline run id for before/after comparison reporting.")
    eval_parser.add_argument(
        "--compare-base-dir",
        help="Optional base artifact directory for --compare-to-run-id. Defaults to --artifact-dir.",
    )
    eval_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit summary JSON instead of a text summary.")
    eval_parser.set_defaults(handler=run_eval_command)

    answer_parser = subparsers.add_parser("answer", help="Run a cited-answer query.")
    _add_common_runtime_args(answer_parser)
    answer_parser.add_argument("query", help="Question to send to Exa.")
    answer_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON instead of a text summary.")
    answer_parser.set_defaults(handler=run_answer_command)

    research_parser = subparsers.add_parser("research", help="Run a report-style research query.")
    _add_common_runtime_args(research_parser)
    research_parser.add_argument("query", help="Research prompt to send to Exa.")
    research_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON instead of a text summary.")
    research_parser.set_defaults(handler=run_research_command)

    find_similar_parser = subparsers.add_parser(
        "find-similar",
        help="Run a seed-URL similarity query.",
    )
    _add_common_runtime_args(find_similar_parser)
    _add_common_search_args(find_similar_parser)
    find_similar_parser.set_defaults(search_type="deep")
    find_similar_parser.add_argument("url", help="Seed URL to send to Exa.")
    find_similar_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON instead of a text summary.")
    find_similar_parser.set_defaults(handler=run_find_similar_command)

    structured_parser = subparsers.add_parser(
        "structured-search",
        help="Run a structured-output search query against a JSON schema.",
    )
    _add_common_runtime_args(structured_parser)
    _add_common_search_args(structured_parser)
    structured_parser.set_defaults(search_type="deep")
    structured_parser.add_argument("query", help="Query string to send to Exa.")
    structured_parser.add_argument("--schema-file", required=True, help="Path to a JSON schema file.")
    structured_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit structured JSON instead of a text summary.")
    structured_parser.set_defaults(handler=run_structured_search_command)

    compare_parser = subparsers.add_parser(
        "compare-search-types",
        help="Run the same evaluation suite for two search types and emit a before/after comparison.",
    )
    _add_common_runtime_args(compare_parser)
    _add_common_search_args(compare_parser, include_search_type=False)
    compare_parser.add_argument(
        "--suite",
        default=LEGACY_DEFAULT_SUITE_ALIAS,
        choices=benchmark_suite_choices(),
        help="Named benchmark suite to run for both search types.",
    )
    compare_parser.add_argument("--queries-file", help="Optional JSON file containing an array of query strings.")
    compare_parser.add_argument("--limit", type=int, help="Optional cap on the number of benchmark queries to execute.")
    compare_parser.add_argument(
        "--baseline-type",
        default="deep",
        help="Baseline search type to execute first. Defaults to deep.",
    )
    compare_parser.add_argument(
        "--candidate-type",
        default="deep-reasoning",
        help="Candidate search type to execute second. Defaults to deep-reasoning.",
    )
    compare_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit summary JSON instead of a text summary.")
    compare_parser.set_defaults(handler=run_compare_search_types_command)

    budget_parser = subparsers.add_parser("budget", help="Inspect cached spend metrics.")
    budget_parser.add_argument("--run-id", help="Optional run id to scope the budget summary.")
    budget_parser.add_argument("--sqlite-path", default="exa_cache.sqlite", help="Path to the sqlite cache/ledger database.")
    budget_parser.add_argument("--cache-ttl-hours", type=float, default=float(default_config()["cache_ttl_hours"]), help="TTL to use when opening the cache store.")
    budget_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON instead of text output.")
    budget_parser.set_defaults(handler=run_budget_command)

    return parser


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
    payload = _run_eval_workflow(args)
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
    baseline_type = str(args.baseline_type or "").strip()
    candidate_type = str(args.candidate_type or "").strip()
    if not baseline_type or not candidate_type:
        raise ValueError("Both --baseline-type and --candidate-type must be non-empty.")
    if baseline_type == candidate_type:
        raise ValueError("Baseline and candidate search types must differ.")

    load_dotenv()
    base_runtime = _resolve_runtime(args.mode, getattr(args, "run_id", None))
    base_run_id = base_runtime.run_id
    baseline_run_id = f"{base_run_id}-{_run_id_suffix_for_search_type(baseline_type)}"
    candidate_run_id = f"{base_run_id}-{_run_id_suffix_for_search_type(candidate_type)}"

    baseline_payload = _run_eval_workflow(
        args,
        run_id_override=baseline_run_id,
        search_type_override=baseline_type,
    )
    candidate_payload = _run_eval_workflow(
        args,
        run_id_override=candidate_run_id,
        search_type_override=candidate_type,
        compare_to_run_id=baseline_run_id,
        compare_base_dir=args.artifact_dir,
    )

    payload = {
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

    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    comparison = payload.get("comparison") if isinstance(payload.get("comparison"), dict) else {}
    deltas = comparison.get("deltas") if isinstance(comparison.get("deltas"), dict) else {}
    print(f"workflow: compare-search-types")
    print(f"query_suite: {payload['query_suite']}")
    print(f"baseline_run_id: {baseline_run_id}")
    print(f"candidate_run_id: {candidate_run_id}")
    print(f"baseline_search_type: {baseline_type}")
    print(f"candidate_search_type: {candidate_type}")
    print(f"baseline_artifact_dir: {baseline_payload['artifact_dir']}")
    print(f"candidate_artifact_dir: {candidate_payload['artifact_dir']}")
    print(f"delta_observed_confidence_score: {float(deltas.get('observed_confidence_score') or 0.0):+.3f}")
    print(f"delta_observed_failure_rate: {float(deltas.get('observed_failure_rate') or 0.0):+.3f}")
    print(f"comparison_markdown: {payload.get('comparison_markdown_path')}")
    return 0


def _run_eval_workflow(
    args: argparse.Namespace,
    *,
    run_id_override: str | None = None,
    search_type_override: str | None = None,
    compare_to_run_id: str | None = None,
    compare_base_dir: str | None = None,
) -> Dict[str, Any]:
    workflow_args = _namespace_with_overrides(
        args,
        run_id=run_id_override if run_id_override is not None else getattr(args, "run_id", None),
        search_type=search_type_override if search_type_override is not None else getattr(args, "search_type", default_config()["search_type"]),
    )
    config, pricing, runtime = _prepare_runtime(workflow_args)
    resolved_compare_to_run_id = compare_to_run_id if compare_to_run_id is not None else getattr(args, "compare_to_run_id", None)
    resolved_compare_base_dir = compare_base_dir if compare_base_dir is not None else getattr(args, "compare_base_dir", None)
    return run_ranked_eval_workflow(
        artifact_dir=args.artifact_dir,
        config=config,
        pricing=pricing,
        runtime=runtime,
        runtime_metadata=_runtime_metadata(runtime),
        suite=getattr(args, "suite", None),
        queries_file=getattr(args, "queries_file", None),
        limit=getattr(args, "limit", None),
        compare_to_run_id=resolved_compare_to_run_id,
        compare_base_dir=resolved_compare_base_dir,
    )


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
    env = dict(os.environ)
    exa_api_key = (env.get("EXA_API_KEY") or "").strip()
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "live" if exa_api_key else "smoke"

    env["EXA_SMOKE_NO_NETWORK"] = "1" if resolved_mode == "smoke" else "0"
    if run_id:
        env["EXA_RUN_ID"] = run_id
    return load_runtime_state(env=env)


def _runtime_metadata(runtime: RuntimeState) -> Dict[str, Any]:
    execution_mode = "smoke" if runtime.smoke_no_network else "live"
    return {
        "execution_mode": execution_mode,
        "smoke_no_network": bool(runtime.smoke_no_network),
        "network_access": not bool(runtime.smoke_no_network),
        "api_key_configured": bool(runtime.exa_api_key),
    }


def _apply_search_overrides(config: Dict[str, Any], pricing: Dict[str, float], args: argparse.Namespace) -> None:
    if getattr(args, "num_results", None):
        config["num_results"] = int(args.num_results)
    if getattr(args, "search_type", None):
        config["search_type"] = args.search_type
    if getattr(args, "category", None):
        config["category"] = args.category
    if getattr(args, "sqlite_path", None):
        config["sqlite_path"] = args.sqlite_path
    if getattr(args, "cache_ttl_hours", None) is not None:
        config["cache_ttl_hours"] = float(args.cache_ttl_hours)
    if getattr(args, "budget_cap_usd", None) is not None:
        config["budget_cap_usd"] = float(args.budget_cap_usd)
    if getattr(args, "include_domains", None):
        config["include_domains"] = list(args.include_domains)
    if getattr(args, "exclude_domains", None):
        config["exclude_domains"] = list(args.exclude_domains)
    if getattr(args, "additional_queries", None):
        config["additional_queries"] = _clean_string_list(args.additional_queries)
    if getattr(args, "start_published_date", None):
        config["start_published_date"] = str(args.start_published_date).strip()
    if getattr(args, "end_published_date", None):
        config["end_published_date"] = str(args.end_published_date).strip()
    if getattr(args, "livecrawl", None):
        config["livecrawl"] = True
    if hasattr(args, "use_text") and args.use_text:
        config["use_text"] = True
    if hasattr(args, "use_summary") and args.use_summary:
        config["use_summary"] = True
    if hasattr(args, "no_highlights") and args.no_highlights:
        config["use_highlights"] = False
    _apply_pricing_overrides(pricing, args)


def _add_common_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["smoke", "live", "auto"], default="auto", help="Runtime mode.")
    parser.add_argument("--run-id", help="Optional explicit run id.")
    parser.add_argument("--sqlite-path", default="exa_cache.sqlite", help="Path to the sqlite cache/ledger database.")
    parser.add_argument("--cache-ttl-hours", type=float, default=float(default_config()["cache_ttl_hours"]), help="Cache TTL in hours.")
    parser.add_argument("--artifact-dir", default="experiments", help="Base directory for run artifacts.")
    parser.add_argument("--budget-cap-usd", type=float, help="Optional override for the run budget cap.")


def _add_common_search_args(parser: argparse.ArgumentParser, *, include_search_type: bool = True) -> None:
    parser.add_argument("--num-results", type=int, default=int(default_config()["num_results"]), help="Number of results to request.")
    if include_search_type:
        parser.add_argument("--type", dest="search_type", default=default_config()["search_type"], help="Exa search type to request.")
    parser.add_argument("--category", default=default_config()["category"], help="Exa category to request.")
    parser.add_argument("--use-text", action="store_true", help="Include full text in contents.")
    parser.add_argument("--use-summary", action="store_true", help="Include summary in contents.")
    parser.add_argument("--no-highlights", action="store_true", help="Disable highlights in contents.")
    parser.add_argument("--include-domain", dest="include_domains", action="append", default=[], help="Domain to include. May be repeated.")
    parser.add_argument("--exclude-domain", dest="exclude_domains", action="append", default=[], help="Domain to exclude. May be repeated.")
    parser.add_argument("--additional-query", dest="additional_queries", action="append", default=[], help="Additional query hint for deep search. May be repeated.")
    parser.add_argument("--start-published-date", help="Optional lower bound for published date filtering (YYYY-MM-DD).")
    parser.add_argument("--end-published-date", help="Optional upper bound for published date filtering (YYYY-MM-DD).")
    parser.add_argument("--livecrawl", action="store_true", help="Force live crawl for the request.")
    parser.add_argument("--search-cost-1-25", type=float, dest="search_cost_1_25", help="Override the base search cost for 1-25 results.")
    parser.add_argument("--search-cost-26-100", type=float, dest="search_cost_26_100", help="Override the base search cost for 26-100 results.")
    parser.add_argument("--deep-search-cost-1-25", type=float, dest="deep_search_cost_1_25", help="Override deep search cost for 1-25 results.")
    parser.add_argument("--deep-search-cost-26-100", type=float, dest="deep_search_cost_26_100", help="Override deep search cost for 26-100 results.")
    parser.add_argument("--deep-reasoning-search-cost-1-25", type=float, dest="deep_reasoning_search_cost_1_25", help="Override deep-reasoning search cost for 1-25 results.")
    parser.add_argument("--deep-reasoning-search-cost-26-100", type=float, dest="deep_reasoning_search_cost_26_100", help="Override deep-reasoning search cost for 26-100 results.")


def _apply_pricing_overrides(pricing: Dict[str, float], args: argparse.Namespace) -> None:
    for arg_name, key in [
        ("search_cost_1_25", "search_1_25"),
        ("search_cost_26_100", "search_26_100"),
        ("deep_search_cost_1_25", "deep_search_1_25"),
        ("deep_search_cost_26_100", "deep_search_26_100"),
        ("deep_reasoning_search_cost_1_25", "deep_reasoning_search_1_25"),
        ("deep_reasoning_search_cost_26_100", "deep_reasoning_search_26_100"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None:
            pricing[key] = float(value)


def _clean_string_list(values: Sequence[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _namespace_with_overrides(args: argparse.Namespace, **overrides: Any) -> argparse.Namespace:
    payload = vars(args).copy()
    payload.update(overrides)
    return argparse.Namespace(**payload)


def _run_id_suffix_for_search_type(search_type: str) -> str:
    text = str(search_type or "").strip().lower()
    return text.replace("_", "-")
