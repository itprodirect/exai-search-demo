from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

import pandas as pd

from .cost_model import estimate_unit_cost_for_config
from .evaluation import FAILURE_LOW_CONFIDENCE, FAILURE_NO_RESULTS, FAILURE_OFF_DOMAIN, LOW_CONFIDENCE_THRESHOLD


def build_qualitative_notes(
    batch_df: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    smoke_no_network: bool,
) -> List[str]:
    notes: List[str] = []
    if not batch_df.empty:
        taxonomy = summarize_failure_taxonomy(batch_df)
        linkedin_rate = float(batch_df["linkedin_present"].mean()) if "linkedin_present" in batch_df.columns else 0.0
        avg_results = float(batch_df["result_count"].mean()) if "result_count" in batch_df.columns else 0.0
        notes.append(
            "Scorecard means - "
            f"relevance: {taxonomy['relevance_score_mean']:.0%}, "
            f"credibility: {taxonomy['credibility_score_mean']:.0%}, "
            f"actionability: {taxonomy['actionability_score_mean']:.0%}, "
            f"confidence: {taxonomy['confidence_score_mean']:.0%}."
        )
        notes.append(f"LinkedIn profile signal present in: {linkedin_rate:.0%} of queries.")
        notes.append(f"Average results returned per query: {avg_results:.1f} (num_results={config['num_results']}).")

        if taxonomy["queries_with_failures"] > 0:
            notes.append(
                "Queries with taxonomy failures: "
                f"{taxonomy['queries_with_failures']}/{taxonomy['total_queries']} "
                f"({taxonomy['failure_rate']:.0%})."
            )
            top_primary = sorted(
                taxonomy["primary_failure_counts"].items(),
                key=lambda item: (-int(item[1]), item[0]),
            )
            if top_primary:
                summary = ", ".join(f"{name}={count}" for name, count in top_primary[:3])
                notes.append(f"Top primary failure reasons: {summary}.")
    else:
        notes.append("No batch results yet. Run Cell 6.")

    if config["use_text"]:
        notes.append("Text is enabled: better evidence depth but higher spend.")
    else:
        notes.append("Text is disabled: cheaper baseline; highlights are usually enough for triage.")

    if config["use_summary"]:
        notes.append("Summary is enabled: validate value before scaling due to extra cost.")
    else:
        notes.append("Summary is disabled (recommended baseline for low-cost evaluation).")

    if smoke_no_network:
        notes.append("Smoke mode active: results are mocked and costs are zero.")

    return notes


def build_cost_projections(
    summary_metrics: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
) -> Dict[str, Any]:
    projection_basis = "observed_avg_uncached"
    projection_unit_cost = float(summary_metrics.get("avg_cost_per_uncached_query", 0.0))
    if projection_unit_cost <= 0:
        projection_unit_cost = estimate_unit_cost_for_config(config, pricing)
        projection_basis = "estimated_from_current_config"

    return {
        "projection_basis": projection_basis,
        "unit_cost_usd": round(projection_unit_cost, 6),
        "projected_100_queries_usd": round(projection_unit_cost * 100, 4),
        "projected_1000_queries_usd": round(projection_unit_cost * 1000, 4),
        "projected_10000_queries_usd": round(projection_unit_cost * 10000, 4),
    }


def recommendation(
    summary_metrics: Mapping[str, Any],
    batch_df: pd.DataFrame,
    *,
    run_id: str,
    budget_cap_usd: float,
    smoke_no_network: bool,
) -> Dict[str, Any]:
    taxonomy = summarize_failure_taxonomy(batch_df)
    relevance_rate = float(taxonomy["relevance_score_mean"])
    credibility_rate = float(taxonomy["credibility_score_mean"])
    actionability_rate = float(taxonomy["actionability_score_mean"])
    confidence_score = float(taxonomy["confidence_score_mean"])
    failure_rate = float(taxonomy["failure_rate"])

    if batch_df.empty:
        linkedin_rate = 0.0
    else:
        linkedin_rate = float(batch_df["linkedin_present"].mean()) if "linkedin_present" in batch_df.columns else 0.0

    avg_cost = float(summary_metrics.get("avg_cost_per_uncached_query", 0.0))

    headline = "Integrate only for scoped workflows"
    if relevance_rate >= 0.70 and confidence_score >= 0.65 and (avg_cost <= 0.02 or smoke_no_network):
        headline = "Integrate (with human review and budget guards)"
    if relevance_rate < 0.50 or confidence_score < 0.45 or avg_cost > 0.05:
        headline = "Do not integrate at current settings"

    return {
        "run_id": run_id,
        "headline_recommendation": headline,
        "observed_relevance_rate": round(relevance_rate, 3),
        "observed_linkedin_rate": round(linkedin_rate, 3),
        "observed_credibility_rate": round(credibility_rate, 3),
        "observed_actionability_rate": round(actionability_rate, 3),
        "observed_confidence_score": round(confidence_score, 3),
        "observed_failure_rate": round(failure_rate, 3),
        "avg_cost_per_uncached_query_usd": round(avg_cost, 4),
        "budget_cap_usd": float(budget_cap_usd),
        "safety_guardrails": [
            "Public/professional info only",
            "No address hunting or contact harvesting",
            "Keep redaction enabled for displayed snippets",
            "Human review required before operational use",
        ],
        "integration_points": [
            {
                "workflow": "Expert/professional discovery",
                "value": "Find candidate experts and collect source URLs + short relevance snippets for analyst review.",
                "safe_pattern": "Query by role + peril + jurisdiction; keep outputs to title/url/highlights by default.",
            },
            {
                "workflow": "Consultant/witness context enrichment",
                "value": "When reports name professionals, quickly pull public bios/publications for context.",
                "safe_pattern": "Search by name + role + insurance/litigation terms; do not harvest personal contact data.",
            },
            {
                "workflow": "Claim dispute research triage",
                "value": "Identify relevant disciplines (forensic engineer, meteorologist, accountant, etc.) fast.",
                "safe_pattern": "Use highlights-on/text-off baseline; selectively deepen only shortlisted results.",
            },
        ],
        "next_tuning_moves": [
            "Keep highlights on, text off, summary off, num_results=5 for baseline cost testing.",
            "Use include_domains only when you need tighter source control.",
            "Enable text/summary only in second-pass review workflows.",
        ],
    }


def summarize_failure_taxonomy(batch_df: pd.DataFrame) -> Dict[str, Any]:
    base_reason_counts: Dict[str, int] = {
        FAILURE_NO_RESULTS: 0,
        FAILURE_OFF_DOMAIN: 0,
        FAILURE_LOW_CONFIDENCE: 0,
    }

    if batch_df.empty:
        return {
            "total_queries": 0,
            "queries_with_failures": 0,
            "queries_without_failures": 0,
            "failure_rate": 0.0,
            "relevance_score_mean": 0.0,
            "credibility_score_mean": 0.0,
            "actionability_score_mean": 0.0,
            "confidence_score_mean": 0.0,
            "failure_reason_counts": dict(base_reason_counts),
            "failure_reason_rates": {reason: 0.0 for reason in base_reason_counts},
            "primary_failure_counts": {},
        }

    reason_counts: Counter[str] = Counter()
    primary_counts: Counter[str] = Counter()
    queries_with_failures = 0

    for row in batch_df.to_dict(orient="records"):
        reasons = _row_failure_reasons(row)
        if reasons:
            queries_with_failures += 1
            reason_counts.update(reasons)
            primary = str(row.get("primary_failure_reason") or "").strip()
            if not primary:
                primary = reasons[0]
            primary_counts.update([primary])

    total_queries = int(len(batch_df.index))
    queries_without_failures = total_queries - queries_with_failures

    relevance_mean = _mean_score(batch_df, "relevance_score", fallback_column="relevance_keywords_present")
    credibility_mean = _mean_score(batch_df, "credibility_score", fallback_column="linkedin_present")
    actionability_mean = _mean_score(batch_df, "actionability_score")
    if actionability_mean <= 0 and "result_count" in batch_df.columns:
        actionability_mean = float((pd.to_numeric(batch_df["result_count"], errors="coerce").fillna(0) > 0).mean())

    confidence_mean = _mean_score(batch_df, "confidence_score")
    if confidence_mean <= 0:
        confidence_mean = (0.5 * relevance_mean) + (0.3 * credibility_mean) + (0.2 * actionability_mean)

    failure_reason_counts = dict(base_reason_counts)
    for reason, count in reason_counts.items():
        failure_reason_counts[str(reason)] = int(count)

    failure_reason_rates = {
        reason: (float(count) / float(total_queries) if total_queries else 0.0)
        for reason, count in failure_reason_counts.items()
    }

    return {
        "total_queries": total_queries,
        "queries_with_failures": int(queries_with_failures),
        "queries_without_failures": int(queries_without_failures),
        "failure_rate": round(float(queries_with_failures / total_queries), 6) if total_queries else 0.0,
        "relevance_score_mean": round(float(relevance_mean), 6),
        "credibility_score_mean": round(float(credibility_mean), 6),
        "actionability_score_mean": round(float(actionability_mean), 6),
        "confidence_score_mean": round(float(confidence_mean), 6),
        "failure_reason_counts": failure_reason_counts,
        "failure_reason_rates": {key: round(float(value), 6) for key, value in failure_reason_rates.items()},
        "primary_failure_counts": {key: int(value) for key, value in primary_counts.items()},
    }


def build_before_after_report(
    before_run_dir: str | Path,
    *,
    after_run_id: str,
    after_summary_metrics: Mapping[str, Any],
    after_batch_df: pd.DataFrame,
    after_recommendation: Mapping[str, Any] | None = None,
    after_context: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
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
    grouped_query_outcomes = _compare_grouped_query_outcomes(before_df, after_df, group_columns=group_columns)

    after_recommendation = after_recommendation or {}

    before_run_id = str(before_summary.get("run_id") or before_dir.name)
    before_spent = _safe_float(before_summary.get("spent_usd"), 0.0)
    before_avg_cost = _safe_float(before_summary.get("avg_cost_per_uncached_query"), 0.0)
    before_relevance = _safe_float(before_summary.get("observed_relevance_rate"), before_taxonomy["relevance_score_mean"])
    before_confidence = _safe_float(before_summary.get("observed_confidence_score"), before_taxonomy["confidence_score_mean"])
    before_failure_rate = _safe_float(before_summary.get("observed_failure_rate"), before_taxonomy["failure_rate"])

    after_spent = _safe_float(after_summary_metrics.get("spent_usd"), 0.0)
    after_avg_cost = _safe_float(after_summary_metrics.get("avg_cost_per_uncached_query"), 0.0)
    after_relevance = _safe_float(after_recommendation.get("observed_relevance_rate"), after_taxonomy["relevance_score_mean"])
    after_confidence = _safe_float(after_recommendation.get("observed_confidence_score"), after_taxonomy["confidence_score_mean"])
    after_failure_rate = _safe_float(after_recommendation.get("observed_failure_rate"), after_taxonomy["failure_rate"])

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
    deltas = comparison_report.get("deltas") if isinstance(comparison_report.get("deltas"), Mapping) else {}
    query_outcomes = comparison_report.get("query_outcomes") if isinstance(comparison_report.get("query_outcomes"), Mapping) else {}
    comparison_context = comparison_report.get("comparison_context") if isinstance(comparison_report.get("comparison_context"), Mapping) else {}
    grouped_query_outcomes = comparison_report.get("grouped_query_outcomes") if isinstance(comparison_report.get("grouped_query_outcomes"), list) else []

    lines: List[str] = []
    lines.append("# Before/After Comparison Report")
    lines.append("")
    lines.append(f"- Baseline run: `{baseline_run_id}`")
    lines.append(f"- Candidate run: `{candidate_run_id}`")
    lines.append(f"- Shared queries: {int(comparison_report.get('shared_query_count') or 0)}")
    group_columns = list(comparison_context.get("group_columns") or [])
    if group_columns:
        lines.append(f"- Grouped by: `{', '.join(str(item) for item in group_columns)}`")
    baseline_context = comparison_context.get("baseline") if isinstance(comparison_context.get("baseline"), Mapping) else {}
    candidate_context = comparison_context.get("candidate") if isinstance(comparison_context.get("candidate"), Mapping) else {}
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
    lines.append(f"| Spent USD | {_format_delta(deltas.get('spent_usd'), kind='currency')} |")
    lines.append(f"| Avg Cost Per Uncached Query | {_format_delta(deltas.get('avg_cost_per_uncached_query'), kind='currency')} |")
    lines.append(f"| Observed Relevance Rate | {_format_delta(deltas.get('observed_relevance_rate'), kind='percent')} |")
    lines.append(f"| Observed Confidence Score | {_format_delta(deltas.get('observed_confidence_score'), kind='percent')} |")
    lines.append(f"| Observed Failure Rate | {_format_delta(deltas.get('observed_failure_rate'), kind='percent')} |")
    lines.append("")
    lines.append("## Query Outcomes")
    lines.append("")
    lines.append(f"- Resolved queries: {int(query_outcomes.get('resolved_query_count') or 0)}")
    lines.append(f"- Regressed queries: {int(query_outcomes.get('regressed_query_count') or 0)}")
    lines.append(f"- Confidence improved queries: {int(query_outcomes.get('confidence_improved_query_count') or 0)}")
    lines.append(f"- Confidence declined queries: {int(query_outcomes.get('confidence_declined_query_count') or 0)}")
    lines.append(f"- Average confidence delta: {_format_delta(query_outcomes.get('avg_confidence_delta'), kind='percent')}")
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
        lines.append("| Group | Baseline Search Type | Candidate Search Type | Shared Queries | Resolved | Regressed | Avg Confidence Delta | Resolved Failures | Introduced Failures |")
        lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |")
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


def render_research_markdown(
    *,
    query: str,
    report_text: str,
    citations: List[Mapping[str, Any]] | None = None,
) -> str:
    lines: List[str] = []
    lines.append("# Research Report")
    lines.append("")
    lines.append(f"- Query: `{query}`")
    lines.append("")
    lines.append("## Report")
    lines.append("")
    lines.append(report_text.strip() or "No report text returned.")
    citations = citations or []
    if citations:
        lines.append("")
        lines.append("## Citations")
        lines.append("")
        for citation in citations:
            title = str(citation.get("title") or "Untitled source").strip()
            url = str(citation.get("url") or "").strip()
            snippet = str(citation.get("snippet") or "").strip()
            if url:
                lines.append(f"- [{title}]({url})")
            else:
                lines.append(f"- {title}")
            if snippet:
                lines.append(f"  - {snippet}")
    return "\n".join(lines).strip() + "\n"


def _load_run_summary_payload(run_dir: Path) -> Dict[str, Any]:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Baseline summary is missing: {summary_path}")
    with summary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Baseline summary payload is not a JSON object: {summary_path}")
    return payload


def _load_run_results_df(run_dir: Path) -> pd.DataFrame:
    results_path = run_dir / "results.jsonl"
    if not results_path.exists():
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []
    with results_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {results_path} at line {line_number}: {exc}") from exc
            if isinstance(payload, dict):
                rows.append(payload)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _extract_run_context(summary_payload: Mapping[str, Any]) -> Dict[str, Any]:
    extra = summary_payload.get("extra")
    if not isinstance(extra, Mapping):
        return {}

    context = extra.get("run_context")
    if not isinstance(context, Mapping):
        return _clean_context(extra.get("query_suite") and {"query_suite": extra.get("query_suite")} or {})

    return _clean_context(context)


def _clean_context(context: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(context, Mapping):
        return {}
    cleaned: Dict[str, Any] = {}
    for key, value in context.items():
        text = str(key).strip()
        if not text:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            cleaned[text] = stripped
        else:
            cleaned[text] = value
    return cleaned


def _apply_context_columns(df: pd.DataFrame, context: Mapping[str, Any]) -> pd.DataFrame:
    if df.empty or not context:
        return df
    result = df.copy()
    for key, value in context.items():
        if key not in result.columns:
            result[key] = value
    return result


def _comparison_group_columns(before_df: pd.DataFrame, after_df: pd.DataFrame) -> List[str]:
    if _context_column_available(before_df, after_df, "query_suite"):
        return ["query_suite"]
    return []


def _context_column_available(before_df: pd.DataFrame, after_df: pd.DataFrame, column: str) -> bool:
    return _column_has_values(before_df, column) and _column_has_values(after_df, column)


def _column_has_values(df: pd.DataFrame, column: str) -> bool:
    if column not in df.columns:
        return False
    series = df[column].dropna()
    if series.empty:
        return False
    return any(str(value).strip() for value in series.tolist())


def _compare_grouped_query_outcomes(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    *,
    group_columns: List[str],
) -> List[Dict[str, Any]]:
    if not group_columns:
        return [
            {
                "group": {"group": "all"},
                "baseline_resolved_search_type": _dominant_string_value(before_df, "resolved_search_type"),
                "candidate_resolved_search_type": _dominant_string_value(after_df, "resolved_search_type"),
                **_compare_query_outcomes(before_df, after_df),
            }
        ]

    before_groups = _group_rows(before_df, group_columns)
    after_groups = _group_rows(after_df, group_columns)
    grouped_rows: List[Dict[str, Any]] = []

    for group_key in sorted(set(before_groups.keys()) | set(after_groups.keys()), key=_group_sort_key):
        group_before = before_groups.get(group_key, pd.DataFrame())
        group_after = after_groups.get(group_key, pd.DataFrame())
        if group_before.empty and group_after.empty:
            continue
        group_outcome = _compare_query_outcomes(group_before, group_after)
        grouped_rows.append(
            {
                "group": _group_key_to_mapping(group_columns, group_key),
                "baseline_resolved_search_type": _dominant_string_value(group_before, "resolved_search_type"),
                "candidate_resolved_search_type": _dominant_string_value(group_after, "resolved_search_type"),
                **group_outcome,
            }
        )

    return grouped_rows


def _group_rows(df: pd.DataFrame, group_columns: List[str]) -> Dict[tuple[Any, ...], pd.DataFrame]:
    if df.empty:
        return {}

    usable_columns = [column for column in group_columns if column in df.columns]
    if not usable_columns:
        return {("all",): df}

    grouped: Dict[tuple[Any, ...], pd.DataFrame] = {}
    for group_values, group_df in df.groupby(usable_columns, dropna=False):
        normalized = group_values if isinstance(group_values, tuple) else (group_values,)
        grouped[tuple(_normalize_group_value(value) for value in normalized)] = group_df
    return grouped


def _normalize_group_value(value: Any) -> str:
    if value is None:
        return "none"
    text = str(value).strip()
    return text or "none"


def _group_key_to_mapping(group_columns: List[str], group_key: tuple[Any, ...]) -> Dict[str, Any]:
    if not group_columns:
        return {}
    return {column: group_key[index] if index < len(group_key) else "none" for index, column in enumerate(group_columns)}


def _group_sort_key(group_key: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(str(value) for value in group_key)


def _format_group_label(group: Any) -> str:
    if not isinstance(group, Mapping):
        return "all"
    parts = [f"{key}={value}" for key, value in group.items()]
    return " | ".join(parts) if parts else "all"


def _dominant_string_value(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns or df.empty:
        return "none"
    values = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
    if not values:
        return "none"
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _compare_query_outcomes(before_df: pd.DataFrame, after_df: pd.DataFrame) -> Dict[str, Any]:
    before_by_query = _index_rows_by_query(before_df)
    after_by_query = _index_rows_by_query(after_df)

    shared_queries = sorted(set(before_by_query.keys()) & set(after_by_query.keys()))
    resolved_failures: Counter[str] = Counter()
    introduced_failures: Counter[str] = Counter()

    resolved_query_count = 0
    regressed_query_count = 0
    confidence_improved_count = 0
    confidence_declined_count = 0
    confidence_delta_total = 0.0

    for query in shared_queries:
        before_row = before_by_query[query]
        after_row = after_by_query[query]

        before_reasons = set(_row_failure_reasons(before_row))
        after_reasons = set(_row_failure_reasons(after_row))

        if before_reasons and not after_reasons:
            resolved_query_count += 1
        if not before_reasons and after_reasons:
            regressed_query_count += 1

        resolved_failures.update(before_reasons - after_reasons)
        introduced_failures.update(after_reasons - before_reasons)

        confidence_delta = _row_confidence_score(after_row) - _row_confidence_score(before_row)
        confidence_delta_total += confidence_delta
        if confidence_delta >= 0.05:
            confidence_improved_count += 1
        elif confidence_delta <= -0.05:
            confidence_declined_count += 1

    shared_count = len(shared_queries)
    avg_confidence_delta = (confidence_delta_total / shared_count) if shared_count else 0.0

    return {
        "shared_query_count": int(shared_count),
        "resolved_query_count": int(resolved_query_count),
        "regressed_query_count": int(regressed_query_count),
        "confidence_improved_query_count": int(confidence_improved_count),
        "confidence_declined_query_count": int(confidence_declined_count),
        "avg_confidence_delta": round(float(avg_confidence_delta), 6),
        "resolved_failure_counts": {key: int(value) for key, value in resolved_failures.items()},
        "introduced_failure_counts": {key: int(value) for key, value in introduced_failures.items()},
    }


def _index_rows_by_query(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    if df.empty or "query" not in df.columns:
        return {}

    indexed: Dict[str, Dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        query = str(row.get("query") or "").strip()
        if not query or query in indexed:
            continue
        indexed[query] = row
    return indexed


def _row_failure_reasons(row: Mapping[str, Any]) -> List[str]:
    value = row.get("failure_reasons")

    if isinstance(value, list):
        parsed = [str(item).strip() for item in value if str(item).strip()]
        if parsed:
            return parsed

    if isinstance(value, str):
        text = value.strip()
        if text:
            if text.startswith("[") and text.endswith("]"):
                try:
                    loaded = json.loads(text)
                    if isinstance(loaded, list):
                        parsed = [str(item).strip() for item in loaded if str(item).strip()]
                        if parsed:
                            return parsed
                except json.JSONDecodeError:
                    pass
            separator = "|" if "|" in text else ","
            parsed = [part.strip() for part in text.split(separator) if part.strip()]
            if parsed:
                return parsed

    reasons: List[str] = []
    result_count = int(_safe_float(row.get("result_count"), 0))
    if result_count <= 0:
        reasons.append(FAILURE_NO_RESULTS)
        return reasons

    relevance_present = _truthy(row.get("relevance_keywords_present"))
    if not relevance_present:
        reasons.append(FAILURE_OFF_DOMAIN)

    confidence_score = _safe_float(row.get("confidence_score"), None)
    if confidence_score is not None:
        if confidence_score < LOW_CONFIDENCE_THRESHOLD:
            reasons.append(FAILURE_LOW_CONFIDENCE)
    else:
        linkedin_present = _truthy(row.get("linkedin_present"))
        if relevance_present and not linkedin_present:
            reasons.append(FAILURE_LOW_CONFIDENCE)

    return reasons


def _row_confidence_score(row: Mapping[str, Any]) -> float:
    observed = _safe_float(row.get("confidence_score"), None)
    if observed is not None:
        return float(observed)

    relevance = 1.0 if _truthy(row.get("relevance_keywords_present")) else 0.0
    credibility = 1.0 if _truthy(row.get("linkedin_present")) else 0.0
    actionability = 1.0 if int(_safe_float(row.get("result_count"), 0)) > 0 else 0.0
    return (0.5 * relevance) + (0.3 * credibility) + (0.2 * actionability)


def _mean_score(df: pd.DataFrame, column: str, fallback_column: str | None = None) -> float:
    if column in df.columns:
        observed = pd.to_numeric(df[column], errors="coerce").dropna()
        if not observed.empty:
            return float(observed.mean())

    if fallback_column and fallback_column in df.columns:
        fallback = pd.to_numeric(df[fallback_column], errors="coerce").fillna(0.0)
        if not fallback.empty:
            return float(fallback.mean())

    return 0.0


def _format_counter(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "none"
    pairs = [(str(key), int(val)) for key, val in value.items() if int(val) > 0]
    if not pairs:
        return "none"
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{key}={count}" for key, count in pairs)


def _format_delta(value: Any, *, kind: str) -> str:
    parsed = _safe_float(value, 0.0)
    if parsed is None:
        parsed = 0.0
    if kind == "currency":
        return f"{parsed:+.4f}"
    if kind == "percent":
        return f"{parsed:+.1%}"
    return f"{parsed:+.4f}"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _safe_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
