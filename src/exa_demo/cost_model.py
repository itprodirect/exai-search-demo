from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping


def estimate_cost_from_pricing(
    payload: Mapping[str, Any],
    num_results: int,
    pricing: Mapping[str, float],
    max_supported_results: int,
) -> float:
    if num_results <= 0:
        raise ValueError("num_results must be >= 1")
    if num_results > int(max_supported_results):
        raise ValueError(
            f"num_results={num_results} exceeds supported estimator range (<= {max_supported_results}). "
            "Lower num_results or update PRICING tiers before running."
        )

    search_type = str(payload.get("type") or "auto").strip().lower()
    search_cost = _resolve_search_cost(search_type, num_results, pricing)

    contents_cost = 0.0
    contents = payload.get("contents") or {}
    if contents.get("text") is True:
        contents_cost += num_results * float(pricing["content_text_per_page"])
    if isinstance(contents.get("highlights"), dict):
        contents_cost += num_results * float(pricing["content_highlights_per_page"])
    if isinstance(contents.get("summary"), dict):
        contents_cost += num_results * float(pricing["content_summary_per_page"])

    return round(search_cost + contents_cost, 6)


def estimate_unit_cost_for_config(
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
) -> float:
    contents: Dict[str, Any] = {}
    if config.get("use_text"):
        contents["text"] = True
    if config.get("use_highlights"):
        contents["highlights"] = {
            "highlightsPerUrl": int(config["highlights_per_url"]),
            "numSentences": int(config["highlight_num_sentences"]),
        }
    if config.get("use_summary"):
        contents["summary"] = {
            "query": "Summarize the person's professional background and insurance/CAT relevance."
        }

    payload: Dict[str, Any] = {}
    if contents:
        payload["contents"] = contents

    return estimate_cost_from_pricing(
        payload,
        int(config["num_results"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )


def summarize_ledger_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, float]:
    request_count = 0
    cache_hits = 0
    uncached_calls = 0
    spent_usd = 0.0
    uncached_total = 0.0

    for row in rows:
        request_count += 1
        cache_hit = int(row.get("cache_hit") or 0) == 1
        if cache_hit:
            cache_hits += 1
            billable_cost = 0.0
        else:
            uncached_calls += 1
            actual_cost = row.get("actual_cost_usd")
            if _has_real_value(actual_cost):
                billable_cost = float(actual_cost)
            else:
                billable_cost = float(row.get("estimated_cost_usd") or 0.0)
            uncached_total += billable_cost
        spent_usd += billable_cost

    avg_uncached = uncached_total / uncached_calls if uncached_calls else 0.0
    return {
        "request_count": int(request_count),
        "cache_hits": int(cache_hits),
        "uncached_calls": int(uncached_calls),
        "spent_usd": round(float(spent_usd), 6),
        "avg_cost_per_uncached_query": round(float(avg_uncached), 6),
    }


def enforce_budget(
    next_estimated_cost: float,
    *,
    spent_usd: float,
    budget_cap_usd: float,
    run_id: str,
) -> None:
    projected_spend = float(spent_usd) + float(next_estimated_cost)
    if projected_spend > float(budget_cap_usd):
        raise RuntimeError(
            "Budget cap exceeded before uncached Exa call.\n"
            f"RUN_ID: {run_id}\n"
            f"Run spend so far: ${float(spent_usd):.4f}\n"
            f"Next call estimate: ${float(next_estimated_cost):.4f}\n"
            f"Cap: ${float(budget_cap_usd):.2f}\n"
            "Lower num_results and/or disable text/summary, or reuse cached queries."
        )


def _has_real_value(value: Any) -> bool:
    if value is None:
        return False
    try:
        return not math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _resolve_search_cost(search_type: str, num_results: int, pricing: Mapping[str, float]) -> float:
    if num_results <= 25:
        tier_suffix = "1_25"
    else:
        tier_suffix = "26_100"

    candidate_keys = []
    normalized_type = search_type.replace("-", "_")
    if normalized_type == "deep_reasoning":
        candidate_keys.extend(
            [
                f"deep_reasoning_search_{tier_suffix}",
                f"deep_reasoning_{tier_suffix}",
            ]
        )
    if normalized_type in {"deep", "deep_reasoning"}:
        candidate_keys.extend(
            [
                f"deep_search_{tier_suffix}",
            ]
        )
    candidate_keys.append(f"search_{tier_suffix}")

    for key in candidate_keys:
        if key in pricing:
            return float(pricing[key])

    raise KeyError(
        f"Missing pricing for search type '{search_type}' at tier '{tier_suffix}'. "
        f"Tried: {', '.join(candidate_keys)}"
    )
