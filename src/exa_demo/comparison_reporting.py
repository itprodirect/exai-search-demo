from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping

import pandas as pd

from .comparison_analysis import (
    apply_context_columns as _apply_context_columns,
    clean_context as _clean_context,
    compare_grouped_query_outcomes as _compare_grouped_query_outcomes,
    compare_query_outcomes as _compare_query_outcomes,
    comparison_group_columns as _comparison_group_columns,
    dominant_string_value as _dominant_string_value,
    extract_run_context as _extract_run_context,
    format_counter as _format_counter,
    format_delta as _format_delta,
    format_group_label as _format_group_label,
    load_run_results_df as _load_run_results_df,
    load_run_summary_payload as _load_run_summary_payload,
    safe_float as _safe_float,
)


def build_before_after_report(
    before_run_dir: str | Path,
    *,
    after_run_id: str,
    after_summary_metrics: Mapping[str, Any],
    after_batch_df: pd.DataFrame,
    after_recommendation: Mapping[str, Any] | None = None,
    after_context: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    from .reporting import summarize_failure_taxonomy

    before_dir = Path(before_run_dir)
    before_summary = _load_run_summary_payload(before_dir)
    before_df = _load_run_results_df(before_dir)

    before_context = _extract_run_context(before_summary)
    after_context = _clean_context(after_context)

    before_df = _apply_context_columns(before_df, before_context)
    after_df = _apply_context_columns(after_batch_df, after_context)
    group_columns = _comparison_group_columns(before_df, after_df)
    before_search_type = _dominant_string_value(before_df, "resolved_search_type")
    after_search_type = _dominant_string_value(after_df, "resolved_search_type")

    before_taxonomy = summarize_failure_taxonomy(before_df)
    after_taxonomy = summarize_failure_taxonomy(after_df)
    query_outcomes = _compare_query_outcomes(before_df, after_df)
    grouped_query_outcomes = _compare_grouped_query_outcomes(
        before_df, after_df, group_columns=group_columns
    )

    after_recommendation = after_recommendation or {}

    before_run_id = str(before_summary.get("run_id") or before_dir.name)
    before_spent = _safe_float(before_summary.get("spent_usd"), 0.0)
    before_avg_cost = _safe_float(before_summary.get("avg_cost_per_uncached_query"), 0.0)
    before_relevance = _safe_float(
        before_summary.get("observed_relevance_rate"),
        before_taxonomy["relevance_score_mean"],
    )
    before_confidence = _safe_float(
        before_summary.get("observed_confidence_score"),
        before_taxonomy["confidence_score_mean"],
    )
    before_failure_rate = _safe_float(
        before_summary.get("observed_failure_rate"), before_taxonomy["failure_rate"]
    )

    after_spent = _safe_float(after_summary_metrics.get("spent_usd"), 0.0)
    after_avg_cost = _safe_float(
        after_summary_metrics.get("avg_cost_per_uncached_query"), 0.0
    )
    after_relevance = _safe_float(
        after_recommendation.get("observed_relevance_rate"),
        after_taxonomy["relevance_score_mean"],
    )
    after_confidence = _safe_float(
        after_recommendation.get("observed_confidence_score"),
        after_taxonomy["confidence_score_mean"],
    )
    after_failure_rate = _safe_float(
        after_recommendation.get("observed_failure_rate"),
        after_taxonomy["failure_rate"],
    )

    return {
        "baseline_run_id": before_run_id,
        "candidate_run_id": str(after_run_id),
        "baseline_artifact_dir": str(before_dir),
        "candidate_query_count": int(len(after_batch_df.index)),
        "baseline_query_count": int(len(before_df.index)),
        "shared_query_count": int(query_outcomes["shared_query_count"]),
        "comparison_context": {
            "baseline": before_context,
            "candidate": after_context,
            "baseline_resolved_search_type": before_search_type,
            "candidate_resolved_search_type": after_search_type,
            "group_columns": group_columns,
        },
        "deltas": {
            "spent_usd": round(after_spent - before_spent, 6),
            "avg_cost_per_uncached_query": round(after_avg_cost - before_avg_cost, 6),
            "observed_relevance_rate": round(after_relevance - before_relevance, 6),
            "observed_confidence_score": round(after_confidence - before_confidence, 6),
            "observed_failure_rate": round(after_failure_rate - before_failure_rate, 6),
        },
        "baseline_taxonomy": before_taxonomy,
        "candidate_taxonomy": after_taxonomy,
        "query_outcomes": query_outcomes,
        "grouped_query_outcomes": grouped_query_outcomes,
    }


def render_comparison_markdown(comparison_report: Mapping[str, Any]) -> str:
    baseline_run_id = str(comparison_report.get("baseline_run_id") or "baseline")
    candidate_run_id = str(comparison_report.get("candidate_run_id") or "candidate")
    deltas = (
        comparison_report.get("deltas")
        if isinstance(comparison_report.get("deltas"), Mapping)
        else {}
    )
    query_outcomes = (
        comparison_report.get("query_outcomes")
        if isinstance(comparison_report.get("query_outcomes"), Mapping)
        else {}
    )
    comparison_context = (
        comparison_report.get("comparison_context")
        if isinstance(comparison_report.get("comparison_context"), Mapping)
        else {}
    )
    grouped_query_outcomes = (
        comparison_report.get("grouped_query_outcomes")
        if isinstance(comparison_report.get("grouped_query_outcomes"), list)
        else []
    )

    lines: List[str] = []
    lines.append("# Before/After Comparison Report")
    lines.append("")
    lines.append(f"- Baseline run: `{baseline_run_id}`")
    lines.append(f"- Candidate run: `{candidate_run_id}`")
    lines.append(f"- Shared queries: {int(comparison_report.get('shared_query_count') or 0)}")
    group_columns = list(comparison_context.get("group_columns") or [])
    if group_columns:
        lines.append(f"- Grouped by: `{', '.join(str(item) for item in group_columns)}`")
    baseline_context = (
        comparison_context.get("baseline")
        if isinstance(comparison_context.get("baseline"), Mapping)
        else {}
    )
    candidate_context = (
        comparison_context.get("candidate")
        if isinstance(comparison_context.get("candidate"), Mapping)
        else {}
    )
    baseline_suite = baseline_context.get("query_suite")
    candidate_suite = candidate_context.get("query_suite")
    if baseline_suite or candidate_suite:
        lines.append(f"- Baseline query suite: `{baseline_suite or 'none'}`")
        lines.append(f"- Candidate query suite: `{candidate_suite or 'none'}`")
    baseline_search_type = comparison_context.get("baseline_resolved_search_type")
    candidate_search_type = comparison_context.get("candidate_resolved_search_type")
    if baseline_search_type or candidate_search_type:
        lines.append(f"- Baseline search type: `{baseline_search_type or 'none'}`")
        lines.append(f"- Candidate search type: `{candidate_search_type or 'none'}`")
    lines.append("")
    lines.append("## Delta Summary")
    lines.append("")
    lines.append("| Metric | Delta |")
    lines.append("| --- | ---: |")
    lines.append(
        f"| Spent USD | {_format_delta(deltas.get('spent_usd'), kind='currency')} |"
    )
    lines.append(
        f"| Avg Cost Per Uncached Query | {_format_delta(deltas.get('avg_cost_per_uncached_query'), kind='currency')} |"
    )
    lines.append(
        f"| Observed Relevance Rate | {_format_delta(deltas.get('observed_relevance_rate'), kind='percent')} |"
    )
    lines.append(
        f"| Observed Confidence Score | {_format_delta(deltas.get('observed_confidence_score'), kind='percent')} |"
    )
    lines.append(
        f"| Observed Failure Rate | {_format_delta(deltas.get('observed_failure_rate'), kind='percent')} |"
    )
    lines.append("")
    lines.append("## Query Outcomes")
    lines.append("")
    lines.append(
        f"- Resolved queries: {int(query_outcomes.get('resolved_query_count') or 0)}"
    )
    lines.append(
        f"- Regressed queries: {int(query_outcomes.get('regressed_query_count') or 0)}"
    )
    lines.append(
        f"- Confidence improved queries: {int(query_outcomes.get('confidence_improved_query_count') or 0)}"
    )
    lines.append(
        f"- Confidence declined queries: {int(query_outcomes.get('confidence_declined_query_count') or 0)}"
    )
    lines.append(
        f"- Average confidence delta: {_format_delta(query_outcomes.get('avg_confidence_delta'), kind='percent')}"
    )
    lines.append("")

    resolved_failures = query_outcomes.get("resolved_failure_counts")
    introduced_failures = query_outcomes.get("introduced_failure_counts")

    lines.append("## Failure Taxonomy Changes")
    lines.append("")
    lines.append(f"- Resolved failure counts: {_format_counter(resolved_failures)}")
    lines.append(f"- Introduced failure counts: {_format_counter(introduced_failures)}")

    if grouped_query_outcomes:
        lines.append("")
        lines.append("## Grouped Query Outcomes")
        lines.append("")
        lines.append(
            "| Group | Baseline Search Type | Candidate Search Type | Shared Queries | Resolved | Regressed | Avg Confidence Delta | Resolved Failures | Introduced Failures |"
        )
        lines.append(
            "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |"
        )
        for entry in grouped_query_outcomes:
            group_label = _format_group_label(entry.get("group"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        group_label,
                        str(entry.get("baseline_resolved_search_type") or "none"),
                        str(entry.get("candidate_resolved_search_type") or "none"),
                        str(int(entry.get("shared_query_count") or 0)),
                        str(int(entry.get("resolved_query_count") or 0)),
                        str(int(entry.get("regressed_query_count") or 0)),
                        _format_delta(entry.get("avg_confidence_delta"), kind="percent"),
                        _format_counter(entry.get("resolved_failure_counts")),
                        _format_counter(entry.get("introduced_failure_counts")),
                    ]
                )
                + " |"
            )

    return "\n".join(lines).strip() + "\n"


def write_comparison_markdown(
    artifact_dir: str | Path,
    comparison_report: Mapping[str, Any],
    *,
    filename: str = "comparison.md",
) -> Path:
    target_dir = Path(artifact_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    path.write_text(render_comparison_markdown(comparison_report), encoding="utf-8")
    return path
