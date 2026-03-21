from __future__ import annotations

from typing import Any, Dict, List, Mapping

import pandas as pd

from . import comparison_reporting as _comparison_reporting
from .cost_model import estimate_unit_cost_for_config

build_before_after_report = _comparison_reporting.build_before_after_report
render_comparison_markdown = _comparison_reporting.render_comparison_markdown
write_comparison_markdown = _comparison_reporting.write_comparison_markdown


def build_qualitative_notes(
    batch_df: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    smoke_no_network: bool,
) -> List[str]:
    notes: List[str] = []
    if not batch_df.empty:
        taxonomy = summarize_failure_taxonomy(batch_df)
        linkedin_rate = (
            float(batch_df["linkedin_present"].mean())
            if "linkedin_present" in batch_df.columns
            else 0.0
        )
        avg_results = (
            float(batch_df["result_count"].mean())
            if "result_count" in batch_df.columns
            else 0.0
        )
        notes.append(
            "Scorecard means - "
            f"relevance: {taxonomy['relevance_score_mean']:.0%}, "
            f"credibility: {taxonomy['credibility_score_mean']:.0%}, "
            f"actionability: {taxonomy['actionability_score_mean']:.0%}, "
            f"confidence: {taxonomy['confidence_score_mean']:.0%}."
        )
        notes.append(f"LinkedIn profile signal present in: {linkedin_rate:.0%} of queries.")
        notes.append(
            f"Average results returned per query: {avg_results:.1f} (num_results={config['num_results']})."
        )

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
    pricing: Mapping[str, Any],
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
        linkedin_rate = (
            float(batch_df["linkedin_present"].mean())
            if "linkedin_present" in batch_df.columns
            else 0.0
        )

    avg_cost = float(summary_metrics.get("avg_cost_per_uncached_query", 0.0))

    headline = "Integrate only for scoped workflows"
    if relevance_rate >= 0.70 and confidence_score >= 0.65 and (
        avg_cost <= 0.02 or smoke_no_network
    ):
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
    from .comparison_analysis import row_failure_reasons

    base_reason_counts: Dict[str, int] = {
        "no_results": 0,
        "off_domain": 0,
        "low_confidence": 0,
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

    reason_counts: Dict[str, int] = {}
    primary_counts: Dict[str, int] = {}
    queries_with_failures = 0

    for row in batch_df.to_dict(orient="records"):
        reasons = row_failure_reasons(row)
        if reasons:
            queries_with_failures += 1
            for reason in reasons:
                reason_counts[reason] = int(reason_counts.get(reason, 0)) + 1
            primary = str(row.get("primary_failure_reason") or "").strip()
            if not primary:
                primary = reasons[0]
            primary_counts[primary] = int(primary_counts.get(primary, 0)) + 1

    total_queries = int(len(batch_df.index))
    queries_without_failures = total_queries - queries_with_failures

    relevance_mean = _mean_score(
        batch_df, "relevance_score", fallback_column="relevance_keywords_present"
    )
    credibility_mean = _mean_score(
        batch_df, "credibility_score", fallback_column="linkedin_present"
    )
    actionability_mean = _mean_score(batch_df, "actionability_score")
    if actionability_mean <= 0 and "result_count" in batch_df.columns:
        actionability_mean = float(
            (pd.to_numeric(batch_df["result_count"], errors="coerce").fillna(0) > 0).mean()
        )

    confidence_mean = _mean_score(batch_df, "confidence_score")
    if confidence_mean <= 0:
        confidence_mean = (
            (0.5 * relevance_mean)
            + (0.3 * credibility_mean)
            + (0.2 * actionability_mean)
        )

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
        "failure_rate": round(float(queries_with_failures / total_queries), 6)
        if total_queries
        else 0.0,
        "relevance_score_mean": round(float(relevance_mean), 6),
        "credibility_score_mean": round(float(credibility_mean), 6),
        "actionability_score_mean": round(float(actionability_mean), 6),
        "confidence_score_mean": round(float(confidence_mean), 6),
        "failure_reason_counts": failure_reason_counts,
        "failure_reason_rates": {
            key: round(float(value), 6) for key, value in failure_reason_rates.items()
        },
        "primary_failure_counts": {key: int(value) for key, value in primary_counts.items()},
    }


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
