from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import pandas as pd

from .artifacts import ExperimentArtifactWriter
from .cache import SqliteCacheStore
from .client import exa_search_people
from .evaluation import (
    DEFAULT_RELEVANCE_KEYWORDS,
    evaluate_batch_queries,
    evaluate_result_set,
    load_benchmark_queries,
    load_benchmark_suites,
)
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


LEGACY_DEFAULT_SUITE_ALIAS = "insurance"
DEFAULT_BENCHMARK_SUITE = "all"


def benchmark_suite_choices() -> list[str]:
    suites = sorted(load_benchmark_suites().keys())
    if LEGACY_DEFAULT_SUITE_ALIAS not in suites:
        suites.insert(0, LEGACY_DEFAULT_SUITE_ALIAS)
    return suites


def normalized_query_suite(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or text == LEGACY_DEFAULT_SUITE_ALIAS:
        return DEFAULT_BENCHMARK_SUITE
    return text


def load_queries(
    *,
    queries_file: str | None,
    suite: str | None,
    limit: int | None,
) -> list[str]:
    normalized_suite = normalized_query_suite(suite)
    if queries_file:
        requested_suite = None if suite == LEGACY_DEFAULT_SUITE_ALIAS else normalized_suite
        queries = load_benchmark_queries(Path(queries_file), suite=requested_suite)
        return queries[:limit] if limit else queries

    queries = load_benchmark_queries(suite=normalized_suite)
    if limit:
        queries = queries[:limit]
    return queries


def run_search_workflow(
    *,
    query: str,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
) -> tuple[Dict[str, Any], QueryEvaluationRecord]:
    cache_store = _cache_store(config)
    search_people = _make_search_people(config, pricing, runtime, cache_store)
    response_json, meta = search_people(query, num_results=int(config["num_results"]))
    results = response_json.get("results", []) if isinstance(response_json, dict) else []
    evaluated = evaluate_result_set(
        results,
        num_results=int(config["num_results"]),
        relevance_keywords=list(DEFAULT_RELEVANCE_KEYWORDS),
        redact_text=lambda value: redact_text(
            value,
            enabled=bool(config.get("redact_emails_phones", True)),
        ),
        extract_preview=lambda row, max_chars: extract_preview(
            row,
            max_chars=max_chars,
            redact_enabled=bool(config.get("redact_emails_phones", True)),
        ),
    )
    record = QueryEvaluationRecord.from_runtime(query, response_json, meta, evaluated)
    batch_df = pd.DataFrame([record.to_flat_dict()])
    taxonomy = summarize_failure_taxonomy(batch_df)
    summary = cache_store.spend_so_far(run_id=runtime.run_id)
    qualitative_notes = build_qualitative_notes(
        batch_df,
        config,
        smoke_no_network=runtime.smoke_no_network,
    )
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
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
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
    return payload, record


def emit_search_payload(
    payload: Mapping[str, Any],
    *,
    record: QueryEvaluationRecord,
    as_json: bool,
) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    print(f"cache_hit: {record.cache_hit}")
    print(f"result_count: {record.result_count}")
    print(f"estimated_cost_usd: {record.estimated_cost_usd:.4f}")
    actual_cost = record.actual_cost_usd if record.actual_cost_usd is not None else 0.0
    print(f"actual_cost_usd: {actual_cost:.4f}")
    print(
        "taxonomy_failure_reasons: "
        f"{', '.join(record.failure_reasons) if record.failure_reasons else 'none'}"
    )
    _print_results_table(record)


def run_eval_workflow(
    *,
    artifact_dir: str,
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    runtime_metadata: Mapping[str, Any],
    suite: str | None,
    queries_file: str | None,
    limit: int | None,
    compare_to_run_id: str | None = None,
    compare_base_dir: str | None = None,
) -> Dict[str, Any]:
    cache_store = _cache_store(config)
    writer = ExperimentArtifactWriter(
        run_id=runtime.run_id,
        config=config,
        pricing=pricing,
        run_context={"query_suite": normalized_query_suite(suite)},
        runtime_metadata=dict(runtime_metadata),
        base_dir=artifact_dir,
    )
    queries = load_queries(
        queries_file=queries_file,
        suite=suite,
        limit=limit,
    )
    search_people = _make_search_people(config, pricing, runtime, cache_store)
    batch_df = evaluate_batch_queries(
        queries,
        search_people=search_people,
        num_results=int(config["num_results"]),
        relevance_keywords=list(DEFAULT_RELEVANCE_KEYWORDS),
        redact_text=lambda value: redact_text(
            value,
            enabled=bool(config.get("redact_emails_phones", True)),
        ),
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
    qualitative_notes = build_qualitative_notes(
        batch_df,
        config,
        smoke_no_network=runtime.smoke_no_network,
    )
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
    if compare_to_run_id:
        compare_base_dir_path = Path(compare_base_dir) if compare_base_dir else Path(artifact_dir)
        compare_run_dir = compare_base_dir_path / str(compare_to_run_id)
        comparison_report = build_before_after_report(
            compare_run_dir,
            after_run_id=runtime.run_id,
            after_summary_metrics=summary,
            after_batch_df=batch_df,
            after_recommendation=rec,
            after_context={"query_suite": normalized_query_suite(suite)},
        )
        comparison_markdown_path = write_comparison_markdown(
            writer.artifact_dir,
            comparison_report,
        )
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

    payload: Dict[str, Any] = {
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


def emit_eval_payload(payload: Mapping[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    print(f"run_id: {payload['run_id']}")
    print(f"queries_executed: {int(payload.get('queries_executed') or 0)}")
    print(f"artifact_dir: {payload['artifact_dir']}")
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    recommendation_payload = (
        payload.get("recommendation")
        if isinstance(payload.get("recommendation"), Mapping)
        else {}
    )
    taxonomy = payload.get("taxonomy") if isinstance(payload.get("taxonomy"), Mapping) else {}
    print(f"spent_usd: {float(summary.get('spent_usd') or 0.0):.4f}")
    print(
        "avg_cost_per_uncached_query: "
        f"{float(summary.get('avg_cost_per_uncached_query') or 0.0):.4f}"
    )
    print(
        "headline_recommendation: "
        f"{recommendation_payload.get('headline_recommendation')}"
    )
    print(f"failure_rate: {float(taxonomy.get('failure_rate') or 0.0):.0%}")

    comparison_report = (
        payload.get("comparison") if isinstance(payload.get("comparison"), Mapping) else None
    )
    if comparison_report is not None:
        print(f"baseline_run_id: {comparison_report['baseline_run_id']}")
        print(f"shared_query_count: {comparison_report['shared_query_count']}")
        print(
            "delta_observed_confidence_score: "
            f"{comparison_report['deltas']['observed_confidence_score']:+.3f}"
        )
        print(
            "delta_observed_failure_rate: "
            f"{comparison_report['deltas']['observed_failure_rate']:+.3f}"
        )
        print(f"comparison_markdown: {payload.get('comparison_markdown_path')}")


def _make_search_people(
    config: Dict[str, Any],
    pricing: Dict[str, float],
    runtime: Any,
    cache_store: SqliteCacheStore,
):
    def _search(query: str, *, num_results: int | None = None):
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


def _print_results_table(record: QueryEvaluationRecord) -> None:
    rows = []
    for result in record.results:
        preview = " | ".join(result.highlights) if result.highlights else (
            result.summary or result.text or ""
        )
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
