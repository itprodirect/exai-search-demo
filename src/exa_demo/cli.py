from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import pandas as pd
from dotenv import load_dotenv

from .artifacts import ExperimentArtifactWriter
from .cache import SqliteCacheStore
from .client import exa_research, exa_search_people
from .config import RuntimeState, default_config, default_pricing, load_runtime_state
from .cost_model import estimate_cost_from_pricing
from .evaluation import DEFAULT_RELEVANCE_KEYWORDS, evaluate_batch_queries, evaluate_result_set, load_benchmark_queries, load_benchmark_suites
from .models import QueryEvaluationRecord, ResearchRecord
from .reporting import (
    build_before_after_report,
    build_cost_projections,
    build_qualitative_notes,
    render_research_markdown,
    recommendation,
    summarize_failure_taxonomy,
    write_comparison_markdown,
)
from .safety import extract_preview, redact_text
from .workflows import (
    build_answer_artifact,
    build_answer_request_payload,
    build_find_similar_artifact,
    build_find_similar_request_payload,
    build_research_artifact,
    build_structured_search_artifact,
    build_structured_search_request_payload,
    find_similar_http_call,
    load_json_schema,
    structured_search_http_call,
    answer_http_call,
)


LEGACY_DEFAULT_SUITE_ALIAS = "insurance"
DEFAULT_BENCHMARK_SUITE = "all"


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
        choices=_benchmark_suite_choices(),
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
        choices=_benchmark_suite_choices(),
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
        run_context={},
        runtime_metadata=_runtime_metadata(runtime),
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
    payload = _run_eval_workflow(args)
    _emit_eval_payload(payload, as_json=bool(args.as_json))
    return 0


def run_answer_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    cache_store = _cache_store(config)
    request_payload = build_answer_request_payload(args.query)
    estimated_cost = estimate_cost_from_pricing(
        {"type": "auto"},
        1,
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: answer_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
        ),
    )

    answer_payload = build_answer_artifact(
        args.query,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )

    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "answer"},
        runtime_metadata=_runtime_metadata(runtime),
        base_dir=args.artifact_dir,
    )
    writer.write_json_artifact("answer.json", answer_payload)
    writer.write_summary(
        summary,
        projections={
            "projection_basis": "observed_avg_uncached",
            "unit_cost_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0),
            "projected_100_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 100,
            "projected_1000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 1000,
            "projected_10000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 10000,
        },
        recommendation_data={"headline_recommendation": "Use for cited-answer workflows with human review"},
        qualitative_notes=[
            "Answer workflow active: answer text and citations are stored in answer.json.",
            "Smoke mode active: answers are mocked and costs are zero.",
        ] if runtime.smoke_no_network else [
            "Answer workflow active: answer text and citations are stored in answer.json.",
        ],
        extra={
            "workflow": "answer",
            "answer": {
                "query": args.query,
                "cache_hit": cache_hit,
                "citation_count": answer_payload["citation_count"],
                "answer_length": len(answer_payload["answer_text"]),
            },
        },
    )

    payload = {
        "workflow": "answer",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "answer": answer_payload["answer_text"],
        "citations": answer_payload["citations"],
        "citation_count": answer_payload["citation_count"],
        "cache_hit": cache_hit,
        "request_id": answer_payload.get("request_id"),
        "summary": summary,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"cache_hit: {cache_hit}")
    print(f"citation_count: {answer_payload['citation_count']}")
    print("")
    print(answer_payload["answer_text"])
    if answer_payload["citations"]:
        print("")
        print(pd.DataFrame(answer_payload["citations"]).to_markdown(index=False))
    return 0


def run_research_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    cache_store = _cache_store(config)
    response_json, meta = exa_research(
        args.query,
        config=config,
        pricing=pricing,
        exa_api_key=runtime.exa_api_key,
        smoke_no_network=runtime.smoke_no_network,
        run_id=runtime.run_id,
        cache_store=cache_store,
    )
    record = ResearchRecord.from_runtime(args.query, response_json, meta)
    research_payload = build_research_artifact(
        args.query,
        request_payload=meta.request_payload,
        response_json=response_json,
        cache_hit=meta.cache_hit,
        estimated_cost_usd=meta.estimated_cost_usd,
    )

    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "research"},
        runtime_metadata=_runtime_metadata(runtime),
        base_dir=args.artifact_dir,
    )
    writer.write_json_artifact("research.json", research_payload)
    writer.write_text_artifact(
        "research.md",
        render_research_markdown(
            query=args.query,
            report_text=record.report_text or "",
            citations=[citation.to_dict() for citation in record.citations],
        ),
        kind="markdown",
    )
    writer.write_summary(
        summary,
        projections={
            "projection_basis": "observed_avg_uncached",
            "unit_cost_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0),
            "projected_100_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 100,
            "projected_1000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 1000,
            "projected_10000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 10000,
        },
        recommendation_data={"headline_recommendation": "Use for research-style report generation with human review"},
        qualitative_notes=[
            "Research workflow active: the response payload is stored in research.json.",
            "Smoke mode active: research reports are mocked and costs are zero.",
        ] if runtime.smoke_no_network else [
            "Research workflow active: the response payload is stored in research.json.",
        ],
        extra={
            "workflow": "research",
            "research": {
                "query": args.query,
                "cache_hit": record.cache_hit,
                "citation_count": record.citation_count,
                "report_length": len(record.report_text or ""),
            },
        },
    )

    payload = {
        "workflow": "research",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "query": args.query,
        "report": record.report_text,
        "report_preview": record.report_preview,
        "citations": [citation.to_dict() for citation in record.citations],
        "citation_count": record.citation_count,
        "cache_hit": record.cache_hit,
        "request_id": record.request_id,
        "summary": summary,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"cache_hit: {record.cache_hit}")
    print(f"citation_count: {record.citation_count}")
    print("")
    print(record.report_text or "")
    if record.citations:
        print("")
        print(pd.DataFrame([citation.to_dict() for citation in record.citations]).to_markdown(index=False))
    return 0


def run_find_similar_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    cache_store = _cache_store(config)
    request_payload = build_find_similar_request_payload(args.url, config)
    estimated_cost = estimate_cost_from_pricing(
        request_payload,
        int(request_payload.get("numResults") or config["num_results"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: find_similar_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
            config=config,
        ),
    )

    find_similar_payload = build_find_similar_artifact(
        args.url,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )

    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "find-similar"},
        runtime_metadata=_runtime_metadata(runtime),
        base_dir=args.artifact_dir,
    )
    writer.write_json_artifact("find_similar.json", find_similar_payload)
    writer.write_summary(
        summary,
        projections={
            "projection_basis": "observed_avg_uncached",
            "unit_cost_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0),
            "projected_100_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 100,
            "projected_1000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 1000,
            "projected_10000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 10000,
        },
        recommendation_data={"headline_recommendation": "Use for seed-url discovery workflows"},
        qualitative_notes=[
            "Find-similar workflow active: the response payload is stored in find_similar.json.",
            "Smoke mode active: similar-page results are mocked and costs are zero.",
        ] if runtime.smoke_no_network else [
            "Find-similar workflow active: the response payload is stored in find_similar.json.",
        ],
        extra={
            "workflow": "find-similar",
            "find_similar": {
                "seed_url": args.url,
                "cache_hit": cache_hit,
                "result_count": find_similar_payload["result_count"],
                "top_result_title": find_similar_payload["top_result"]["title"] if find_similar_payload["top_result"] else None,
            },
        },
    )

    payload = {
        "workflow": "find-similar",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "seed_url": args.url,
        "cache_hit": cache_hit,
        "request_id": find_similar_payload.get("request_id"),
        "result_count": find_similar_payload["result_count"],
        "top_result": find_similar_payload.get("top_result"),
        "results": find_similar_payload.get("results"),
        "summary": summary,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"seed_url: {args.url}")
    print(f"cache_hit: {cache_hit}")
    print(f"result_count: {find_similar_payload['result_count']}")
    print(f"request_id: {find_similar_payload.get('request_id')}")
    if find_similar_payload.get("top_result"):
        print("top_result:")
        print(json.dumps(find_similar_payload["top_result"], indent=2, sort_keys=True))
    return 0


def run_structured_search_command(args: argparse.Namespace) -> int:
    config, pricing, runtime = _prepare_runtime(args)
    cache_store = _cache_store(config)
    schema_path = Path(args.schema_file)
    output_schema = load_json_schema(schema_path)
    request_payload = build_structured_search_request_payload(args.query, config, output_schema)
    estimated_cost = estimate_cost_from_pricing(
        request_payload,
        int(request_payload.get("numResults") or config["num_results"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        request_payload,
        estimated_cost,
        run_id=runtime.run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda payload: structured_search_http_call(
            payload,
            exa_api_key=runtime.exa_api_key,
            smoke_no_network=runtime.smoke_no_network,
            config=config,
        ),
    )

    structured_payload = build_structured_search_artifact(
        args.query,
        schema_path=schema_path,
        request_payload=request_payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost_usd=estimated_cost,
    )

    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"workflow": "structured-search"},
        runtime_metadata=_runtime_metadata(runtime),
        base_dir=args.artifact_dir,
    )
    writer.write_json_artifact("structured_output.json", structured_payload)
    writer.write_summary(
        summary,
        projections={
            "projection_basis": "observed_avg_uncached",
            "unit_cost_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0),
            "projected_100_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 100,
            "projected_1000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 1000,
            "projected_10000_queries_usd": float(summary.get("avg_cost_per_uncached_query", 0.0) or 0.0) * 10000,
        },
        recommendation_data={"headline_recommendation": "Use for schema-driven extraction workflows"},
        qualitative_notes=[
            "Structured output active: the response payload is stored in structured_output.json.",
            "Smoke mode active: structured output is mocked and costs are zero.",
        ] if runtime.smoke_no_network else [
            "Structured output active: the response payload is stored in structured_output.json.",
        ],
        extra={
            "workflow": "structured-search",
            "structured_search": {
                "query": args.query,
                "schema_file": str(schema_path),
                "cache_hit": cache_hit,
                "structured_keys": structured_payload["structured_output_keys"],
            },
        },
    )

    payload = {
        "workflow": "structured-search",
        "run_id": runtime.run_id,
        "artifact_dir": str(writer.artifact_dir),
        "schema_file": str(schema_path),
        "cache_hit": cache_hit,
        "request_id": structured_payload.get("request_id"),
        "structured_output": structured_payload.get("structured_output"),
        "summary": summary,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"run_id: {runtime.run_id}")
    print(f"artifact_dir: {writer.artifact_dir}")
    print(f"schema_file: {schema_path}")
    print(f"cache_hit: {cache_hit}")
    print(f"request_id: {structured_payload.get('request_id')}")
    print("structured_output:")
    print(json.dumps(structured_payload.get("structured_output"), indent=2, sort_keys=True))
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
        "query_suite": _normalized_query_suite(getattr(args, "suite", None)),
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
    cache_store = _cache_store(config)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"query_suite": _normalized_query_suite(args.suite)},
        runtime_metadata=_runtime_metadata(runtime),
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
    writer.write_dataframe_csv("results.csv", batch_df, kind="results-csv")
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
    resolved_compare_to_run_id = compare_to_run_id if compare_to_run_id is not None else getattr(args, "compare_to_run_id", None)
    resolved_compare_base_dir = compare_base_dir if compare_base_dir is not None else getattr(args, "compare_base_dir", None)
    if resolved_compare_to_run_id:
        compare_base_dir_path = Path(resolved_compare_base_dir) if resolved_compare_base_dir else Path(args.artifact_dir)
        compare_run_dir = compare_base_dir_path / str(resolved_compare_to_run_id)
        comparison_report = build_before_after_report(
            compare_run_dir,
            after_run_id=runtime.run_id,
            after_summary_metrics=summary,
            after_batch_df=batch_df,
            after_recommendation=rec,
            after_context={"query_suite": _normalized_query_suite(args.suite)},
        )
        comparison_markdown_path = write_comparison_markdown(writer.artifact_dir, comparison_report)
        writer.write_json_artifact("comparison.json", comparison_report)
        grouped_query_outcomes = comparison_report.get("grouped_query_outcomes")
        if isinstance(grouped_query_outcomes, list):
            writer.write_dataframe_csv(
                "grouped_query_outcomes.csv",
                pd.DataFrame(grouped_query_outcomes),
                kind="comparison-csv",
            )

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
        "queries_executed": int(len(batch_df.index)),
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

    return payload


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
    normalized_suite = _normalized_query_suite(getattr(args, "suite", None))
    if args.queries_file:
        requested_suite = None if getattr(args, "suite", None) == LEGACY_DEFAULT_SUITE_ALIAS else normalized_suite
        queries = load_benchmark_queries(Path(args.queries_file), suite=requested_suite)
        return queries[: args.limit] if args.limit else queries

    queries = load_benchmark_queries(suite=normalized_suite)
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


def _benchmark_suite_choices() -> list[str]:
    suites = sorted(load_benchmark_suites().keys())
    if LEGACY_DEFAULT_SUITE_ALIAS not in suites:
        suites.insert(0, LEGACY_DEFAULT_SUITE_ALIAS)
    return suites


def _normalized_query_suite(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or text == LEGACY_DEFAULT_SUITE_ALIAS:
        return DEFAULT_BENCHMARK_SUITE
    return text


def _emit_eval_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"queries_executed: {int(payload.get('queries_executed') or 0)}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    recommendation_payload = payload.get("recommendation") if isinstance(payload.get("recommendation"), Mapping) else {}
    taxonomy = payload.get("taxonomy") if isinstance(payload.get("taxonomy"), Mapping) else {}
    print(f"spent_usd: {float(summary.get('spent_usd') or 0.0):.4f}")
    print(f"avg_cost_per_uncached_query: {float(summary.get('avg_cost_per_uncached_query') or 0.0):.4f}")
    print(f"headline_recommendation: {recommendation_payload.get('headline_recommendation')}")
    print(f"failure_rate: {float(taxonomy.get('failure_rate') or 0.0):.0%}")

    comparison_report = payload.get("comparison") if isinstance(payload.get("comparison"), Mapping) else None
    if comparison_report is not None:
        print(f"baseline_run_id: {comparison_report['baseline_run_id']}")
        print(f"shared_query_count: {comparison_report['shared_query_count']}")
        print(f"delta_observed_confidence_score: {comparison_report['deltas']['observed_confidence_score']:+.3f}")
        print(f"delta_observed_failure_rate: {comparison_report['deltas']['observed_failure_rate']:+.3f}")
        print(f"comparison_markdown: {payload.get('comparison_markdown_path')}")


def _namespace_with_overrides(args: argparse.Namespace, **overrides: Any) -> argparse.Namespace:
    payload = vars(args).copy()
    payload.update(overrides)
    return argparse.Namespace(**payload)


def _run_id_suffix_for_search_type(search_type: str) -> str:
    text = str(search_type or "").strip().lower()
    return text.replace("_", "-")
