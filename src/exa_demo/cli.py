from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

import pandas as pd
from dotenv import load_dotenv

from .artifacts import ExperimentArtifactWriter
from .cache import SqliteCacheStore
from .client import exa_search_people
from .config import RuntimeState, default_config, default_pricing, load_runtime_state
from .evaluation import DEFAULT_RELEVANCE_KEYWORDS, evaluate_batch_queries, evaluate_result_set, load_benchmark_queries
from .models import QueryEvaluationRecord
from .reporting import (
    build_before_after_report,
    build_cost_projections,
    build_qualitative_notes,
    recommendation,
    summarize_failure_taxonomy,
    write_comparison_markdown,
)
from .safety import extract_preview, redact_text


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
    eval_parser.add_argument("--suite", default="insurance", choices=["insurance"], help="Named benchmark suite to run.")
    eval_parser.add_argument("--queries-file", help="Optional JSON file containing an array of query strings.")
    eval_parser.add_argument("--limit", type=int, help="Optional cap on the number of benchmark queries to execute.")
    eval_parser.add_argument("--compare-to-run-id", help="Optional baseline run id for before/after comparison reporting.")
    eval_parser.add_argument(
        "--compare-base-dir",
        help="Optional base artifact directory for --compare-to-run-id. Defaults to --artifact-dir.",
    )
    eval_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit summary JSON instead of a text summary.")
    eval_parser.set_defaults(handler=run_eval_command)

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
    cache_store = _cache_store(config)
    search_people = _make_search_people(config, pricing, runtime, cache_store)
    response_json, meta = search_people(args.query, num_results=int(config["num_results"]))
    results = response_json.get("results", []) if isinstance(response_json, dict) else []
    evaluated = evaluate_result_set(
        results,
        num_results=int(config["num_results"]),
        relevance_keywords=list(DEFAULT_RELEVANCE_KEYWORDS),
        redact_text=lambda value: redact_text(value, enabled=bool(config.get("redact_emails_phones", True))),
        extract_preview=lambda row, max_chars: extract_preview(
            row,
            max_chars=max_chars,
            redact_enabled=bool(config.get("redact_emails_phones", True)),
        ),
    )
    record = QueryEvaluationRecord.from_runtime(args.query, response_json, meta, evaluated)
    batch_df = pd.DataFrame([record.to_flat_dict()])
    taxonomy = summarize_failure_taxonomy(batch_df)
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    qualitative_notes = build_qualitative_notes(batch_df, config, smoke_no_network=runtime.smoke_no_network)
    projections = build_cost_projections(summary, config=config, pricing=pricing)
    rec = recommendation(
        summary,
        batch_df,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        smoke_no_network=runtime.smoke_no_network,
    )
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        base_dir=args.artifact_dir,
    )
    writer.record_query(record)
    writer.write_summary(
        summary,
        projections=projections,
        recommendation_data=rec,
        batch_df=batch_df,
        qualitative_notes=qualitative_notes,
        extra={"taxonomy": taxonomy},
    )

    payload = {
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "record": record.to_dict(),
        "summary": summary,
        "taxonomy": taxonomy,
        "recommendation": rec,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"cache_hit: {record.cache_hit}")
    print(f"result_count: {record.result_count}")
    print(f"estimated_cost_usd: {record.estimated_cost_usd:.4f}")
    actual_cost = record.actual_cost_usd if record.actual_cost_usd is not None else 0.0
    print(f"actual_cost_usd: {actual_cost:.4f}")
    print(f"taxonomy_failure_reasons: {', '.join(record.failure_reasons) if record.failure_reasons else 'none'}")
    _print_results_table(record)
    return 0


def run_eval_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    cache_store = _cache_store(config)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        base_dir=args.artifact_dir,
    )
    queries = _load_queries(args)
    search_people = _make_search_people(config, pricing, runtime, cache_store)
    batch_df = evaluate_batch_queries(
        queries,
        search_people=search_people,
        num_results=int(config["num_results"]),
        relevance_keywords=list(DEFAULT_RELEVANCE_KEYWORDS),
        redact_text=lambda value: redact_text(value, enabled=bool(config.get("redact_emails_phones", True))),
        extract_preview=lambda row, max_chars: extract_preview(
            row,
            max_chars=max_chars,
            redact_enabled=bool(config.get("redact_emails_phones", True)),
        ),
        record_query=writer.record_query,
    )
    taxonomy = summarize_failure_taxonomy(batch_df)
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    qualitative_notes = build_qualitative_notes(batch_df, config, smoke_no_network=runtime.smoke_no_network)
    projections = build_cost_projections(summary, config=config, pricing=pricing)
    rec = recommendation(
        summary,
        batch_df,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        smoke_no_network=runtime.smoke_no_network,
    )

    comparison_report: Dict[str, Any] | None = None
    comparison_markdown_path: Path | None = None
    if args.compare_to_run_id:
        compare_base_dir = Path(args.compare_base_dir) if args.compare_base_dir else Path(args.artifact_dir)
        compare_run_dir = compare_base_dir / str(args.compare_to_run_id)
        comparison_report = build_before_after_report(
            compare_run_dir,
            after_run_id=runtime.run_id,
            after_summary_metrics=summary,
            after_batch_df=batch_df,
            after_recommendation=rec,
        )
        comparison_markdown_path = write_comparison_markdown(writer.artifact_dir, comparison_report)

    summary_extra: Dict[str, Any] = {"taxonomy": taxonomy}
    if comparison_report is not None:
        summary_extra["comparison"] = comparison_report

    summary_path = writer.write_summary(
        summary,
        projections=projections,
        recommendation_data=rec,
        batch_df=batch_df,
        qualitative_notes=qualitative_notes,
        extra=summary_extra,
    )

    payload = {
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "summary_path": str(summary_path),
        "summary": summary,
        "taxonomy": taxonomy,
        "projections": projections,
        "recommendation": rec,
    }
    if comparison_report is not None:
        payload["comparison"] = comparison_report
        payload["comparison_markdown_path"] = str(comparison_markdown_path)

    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"queries_executed: {len(batch_df)}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"spent_usd: {summary['spent_usd']:.4f}")
    print(f"avg_cost_per_uncached_query: {summary['avg_cost_per_uncached_query']:.4f}")
    print(f"headline_recommendation: {rec['headline_recommendation']}")
    print(f"failure_rate: {taxonomy['failure_rate']:.0%}")

    if comparison_report is not None:
        print(f"baseline_run_id: {comparison_report['baseline_run_id']}")
        print(f"shared_query_count: {comparison_report['shared_query_count']}")
        print(f"delta_observed_confidence_score: {comparison_report['deltas']['observed_confidence_score']:+.3f}")
        print(f"delta_observed_failure_rate: {comparison_report['deltas']['observed_failure_rate']:+.3f}")
        print(f"comparison_markdown: {comparison_markdown_path}")

    if not batch_df.empty:
        print(batch_df[["query", "result_count", "cache_hit", "actual_cost_usd", "primary_failure_reason"]].to_markdown(index=False))
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
    env = dict(os.environ)
    exa_api_key = (env.get("EXA_API_KEY") or "").strip()
    resolved_mode = mode
    if resolved_mode == "auto":
        resolved_mode = "live" if exa_api_key else "smoke"

    env["EXA_SMOKE_NO_NETWORK"] = "1" if resolved_mode == "smoke" else "0"
    if run_id:
        env["EXA_RUN_ID"] = run_id
    return load_runtime_state(env=env)


def _make_search_people(
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: RuntimeState,
    cache_store: SqliteCacheStore,
) -> Callable[..., Any]:
    def _search(query: str, *, num_results: Optional[int] = None):
        return exa_search_people(
            query,
            config=config,
            pricing=pricing,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
            run_id=runtime.run_id,
            cache_store=cache_store,
            num_results=num_results,
        )

    return _search


def _cache_store(config: Dict[str, Any]) -> SqliteCacheStore:
    return SqliteCacheStore(config["sqlite_path"], float(config["cache_ttl_hours"]))


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


def _load_queries(args: argparse.Namespace) -> list[str]:
    if args.queries_file:
        return load_benchmark_queries(Path(args.queries_file))[: args.limit] if args.limit else load_benchmark_queries(Path(args.queries_file))

    queries = load_benchmark_queries()
    if args.limit:
        queries = queries[: args.limit]
    return queries


def _print_results_table(record: QueryEvaluationRecord) -> None:
    rows = []
    for result in record.results:
        preview = " | ".join(result.highlights) if result.highlights else (result.summary or result.text or "")
        rows.append(
            {
                "title": result.title,
                "url": result.url,
                "preview": preview[:120],
            }
        )

    if not rows:
        print("No results returned.")
        return

    print(pd.DataFrame(rows).to_markdown(index=False))


def _add_common_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mode", choices=["smoke", "live", "auto"], default="auto", help="Runtime mode.")
    parser.add_argument("--run-id", help="Optional explicit run id.")
    parser.add_argument("--sqlite-path", default="exa_cache.sqlite", help="Path to the sqlite cache/ledger database.")
    parser.add_argument("--cache-ttl-hours", type=float, default=float(default_config()["cache_ttl_hours"]), help="Cache TTL in hours.")
    parser.add_argument("--artifact-dir", default="experiments", help="Base directory for run artifacts.")
    parser.add_argument("--budget-cap-usd", type=float, help="Optional override for the run budget cap.")


def _add_common_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--num-results", type=int, default=int(default_config()["num_results"]), help="Number of results to request.")
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
