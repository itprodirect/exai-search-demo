from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping

import pandas as pd

from .evaluation import (
    FAILURE_LOW_CONFIDENCE,
    FAILURE_NO_RESULTS,
    FAILURE_OFF_DOMAIN,
    LOW_CONFIDENCE_THRESHOLD,
)


def load_run_summary_payload(run_dir: Path) -> Dict[str, Any]:
    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"Baseline summary is missing: {summary_path}")
    with summary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Baseline summary payload is not a JSON object: {summary_path}")
    return payload


def load_run_results_df(run_dir: Path) -> pd.DataFrame:
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
                raise ValueError(
                    f"Invalid JSON in {results_path} at line {line_number}: {exc}"
                ) from exc
            if isinstance(payload, dict):
                rows.append(payload)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def extract_run_context(summary_payload: Mapping[str, Any]) -> Dict[str, Any]:
    extra = summary_payload.get("extra")
    if not isinstance(extra, Mapping):
        return {}

    context = extra.get("run_context")
    if not isinstance(context, Mapping):
        return clean_context(
            extra.get("query_suite") and {"query_suite": extra.get("query_suite")} or {}
        )

    return clean_context(context)


def clean_context(context: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(context, Mapping):
        return {}
    cleaned: Dict[str, Any] = {}
    for key, value in context.items():
        text = str(key).strip()
        if not text or value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            cleaned[text] = stripped
        else:
            cleaned[text] = value
    return cleaned


def apply_context_columns(df: pd.DataFrame, context: Mapping[str, Any]) -> pd.DataFrame:
    if df.empty or not context:
        return df
    result = df.copy()
    for key, value in context.items():
        if key not in result.columns:
            result[key] = value
    return result


def comparison_group_columns(before_df: pd.DataFrame, after_df: pd.DataFrame) -> List[str]:
    if _context_column_available(before_df, after_df, "query_suite"):
        return ["query_suite"]
    return []


def compare_grouped_query_outcomes(
    before_df: pd.DataFrame,
    after_df: pd.DataFrame,
    *,
    group_columns: List[str],
) -> List[Dict[str, Any]]:
    if not group_columns:
        return [
            {
                "group": {"group": "all"},
                "baseline_resolved_search_type": dominant_string_value(
                    before_df, "resolved_search_type"
                ),
                "candidate_resolved_search_type": dominant_string_value(
                    after_df, "resolved_search_type"
                ),
                **compare_query_outcomes(before_df, after_df),
            }
        ]

    before_groups = _group_rows(before_df, group_columns)
    after_groups = _group_rows(after_df, group_columns)
    grouped_rows: List[Dict[str, Any]] = []

    for group_key in sorted(
        set(before_groups.keys()) | set(after_groups.keys()), key=_group_sort_key
    ):
        group_before = before_groups.get(group_key, pd.DataFrame())
        group_after = after_groups.get(group_key, pd.DataFrame())
        if group_before.empty and group_after.empty:
            continue
        grouped_rows.append(
            {
                "group": _group_key_to_mapping(group_columns, group_key),
                "baseline_resolved_search_type": dominant_string_value(
                    group_before, "resolved_search_type"
                ),
                "candidate_resolved_search_type": dominant_string_value(
                    group_after, "resolved_search_type"
                ),
                **compare_query_outcomes(group_before, group_after),
            }
        )

    return grouped_rows


def format_group_label(group: Any) -> str:
    if not isinstance(group, Mapping):
        return "all"
    parts = [f"{key}={value}" for key, value in group.items()]
    return " | ".join(parts) if parts else "all"


def dominant_string_value(df: pd.DataFrame, column: str) -> str:
    if column not in df.columns or df.empty:
        return "none"
    values = [str(value).strip() for value in df[column].tolist() if str(value).strip()]
    if not values:
        return "none"
    counts = Counter(values)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def compare_query_outcomes(before_df: pd.DataFrame, after_df: pd.DataFrame) -> Dict[str, Any]:
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

        before_reasons = set(row_failure_reasons(before_row))
        after_reasons = set(row_failure_reasons(after_row))

        if before_reasons and not after_reasons:
            resolved_query_count += 1
        if not before_reasons and after_reasons:
            regressed_query_count += 1

        resolved_failures.update(before_reasons - after_reasons)
        introduced_failures.update(after_reasons - before_reasons)

        confidence_delta = row_confidence_score(after_row) - row_confidence_score(
            before_row
        )
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
        "resolved_failure_counts": {
            key: int(value) for key, value in resolved_failures.items()
        },
        "introduced_failure_counts": {
            key: int(value) for key, value in introduced_failures.items()
        },
    }


def row_failure_reasons(row: Mapping[str, Any]) -> List[str]:
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
                        parsed = [
                            str(item).strip() for item in loaded if str(item).strip()
                        ]
                        if parsed:
                            return parsed
                except json.JSONDecodeError:
                    pass
            separator = "|" if "|" in text else ","
            parsed = [part.strip() for part in text.split(separator) if part.strip()]
            if parsed:
                return parsed

    reasons: List[str] = []
    result_count = int(safe_float(row.get("result_count"), 0))
    if result_count <= 0:
        reasons.append(FAILURE_NO_RESULTS)
        return reasons

    relevance_present = truthy(row.get("relevance_keywords_present"))
    if not relevance_present:
        reasons.append(FAILURE_OFF_DOMAIN)

    confidence_score = safe_float(row.get("confidence_score"), None)
    if confidence_score is not None:
        if confidence_score < LOW_CONFIDENCE_THRESHOLD:
            reasons.append(FAILURE_LOW_CONFIDENCE)
    else:
        linkedin_present = truthy(row.get("linkedin_present"))
        if relevance_present and not linkedin_present:
            reasons.append(FAILURE_LOW_CONFIDENCE)

    return reasons


def row_confidence_score(row: Mapping[str, Any]) -> float:
    observed = safe_float(row.get("confidence_score"), None)
    if observed is not None:
        return float(observed)

    relevance = 1.0 if truthy(row.get("relevance_keywords_present")) else 0.0
    credibility = 1.0 if truthy(row.get("linkedin_present")) else 0.0
    actionability = 1.0 if int(safe_float(row.get("result_count"), 0)) > 0 else 0.0
    return (0.5 * relevance) + (0.3 * credibility) + (0.2 * actionability)


def format_counter(value: Any) -> str:
    if not isinstance(value, Mapping) or not value:
        return "none"
    parts = [f"{key}={int(amount)}" for key, amount in sorted(value.items())]
    return ", ".join(parts)


def format_delta(value: Any, *, kind: str) -> str:
    number = safe_float(value, 0.0)
    if kind == "currency":
        return f"{number:+.4f}"
    if kind == "percent":
        return f"{number:+.1%}"
    return f"{number:+.3f}"


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def safe_float(value: Any, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _context_column_available(before_df: pd.DataFrame, after_df: pd.DataFrame, column: str) -> bool:
    return _column_has_values(before_df, column) and _column_has_values(after_df, column)


def _column_has_values(df: pd.DataFrame, column: str) -> bool:
    if column not in df.columns:
        return False
    series = df[column].dropna()
    if series.empty:
        return False
    return any(str(value).strip() for value in series.tolist())


def _group_rows(
    df: pd.DataFrame, group_columns: List[str]
) -> Dict[tuple[Any, ...], pd.DataFrame]:
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


def _group_key_to_mapping(
    group_columns: List[str], group_key: tuple[Any, ...]
) -> Dict[str, Any]:
    if not group_columns:
        return {}
    return {
        column: group_key[index] if index < len(group_key) else "none"
        for index, column in enumerate(group_columns)
    }


def _group_sort_key(group_key: tuple[Any, ...]) -> tuple[str, ...]:
    return tuple(str(value) for value in group_key)


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
