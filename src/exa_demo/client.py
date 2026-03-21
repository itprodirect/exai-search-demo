from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Tuple

import requests

from .cache import SqliteCacheStore, parse_actual_cost, request_hash_for_payload
from .client_payloads import (
    build_answer_payload,
    build_exa_payload,
    build_find_similar_payload,
    build_research_payload,
    build_structured_search_payload,
)
from .client_smoke import (
    mock_exa_answer_response,
    mock_exa_find_similar_response,
    mock_exa_research_response,
    mock_exa_response,
    mock_exa_structured_search_response,
)
from .cost_model import estimate_cost_from_pricing


@dataclass
class ExaCallMeta:
    cache_hit: bool
    request_hash: str
    request_payload: Dict[str, Any]
    estimated_cost_usd: float
    actual_cost_usd: Optional[float]
    request_id: Optional[str]
    resolved_search_type: Optional[str]
    created_at_utc: str


def exa_http_call(
    payload: Dict[str, Any],
    *,
    config: Mapping[str, Any],
    exa_api_key: str,
    smoke_no_network: bool,
    endpoint_name: str = "search",
    timeout: int = 60,
) -> Dict[str, Any]:
    if smoke_no_network:
        if endpoint_name == "findSimilar":
            return mock_exa_find_similar_response(payload)
        if isinstance(payload.get("outputSchema"), Mapping):
            return mock_exa_structured_search_response(payload)
        if endpoint_name == "answer":
            return mock_exa_answer_response(payload)
        if endpoint_name == "research":
            return mock_exa_research_response(payload)
        return mock_exa_response(payload)

    if not exa_api_key:
        raise RuntimeError("Missing EXA_API_KEY for live Exa request.")

    headers = {"x-api-key": exa_api_key, "Content-Type": "application/json"}
    response = requests.post(
        _resolve_exa_endpoint(str(config["exa_endpoint"]), endpoint_name=endpoint_name),
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def exa_search_people(
    query: str,
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
    exa_api_key: str,
    smoke_no_network: bool,
    run_id: str,
    cache_store: SqliteCacheStore,
    num_results: Optional[int] = None,
) -> Tuple[Dict[str, Any], ExaCallMeta]:
    payload = build_exa_payload(query, config, num_results=num_results)
    estimated_cost = estimate_cost_from_pricing(
        payload,
        int(payload["numResults"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        payload,
        estimated_cost,
        run_id=run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda request_payload: exa_http_call(
            request_payload,
            config=config,
            exa_api_key=exa_api_key,
            smoke_no_network=smoke_no_network,
            endpoint_name="search",
        ),
    )

    return response_json, _build_call_meta(
        payload=payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost=estimated_cost,
    )


def exa_structured_search(
    query: str,
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
    exa_api_key: str,
    smoke_no_network: bool,
    run_id: str,
    cache_store: SqliteCacheStore,
    output_schema: Mapping[str, Any],
    num_results: Optional[int] = None,
) -> Tuple[Dict[str, Any], ExaCallMeta]:
    payload = build_structured_search_payload(
        query, config, output_schema, num_results=num_results
    )
    estimated_cost = estimate_cost_from_pricing(
        payload,
        int(payload["numResults"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        payload,
        estimated_cost,
        run_id=run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda request_payload: exa_http_call(
            request_payload,
            config=config,
            exa_api_key=exa_api_key,
            smoke_no_network=smoke_no_network,
            endpoint_name="search",
        ),
    )

    return response_json, _build_call_meta(
        payload=payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost=estimated_cost,
    )


def exa_find_similar(
    url: str,
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
    exa_api_key: str,
    smoke_no_network: bool,
    run_id: str,
    cache_store: SqliteCacheStore,
    num_results: Optional[int] = None,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
    start_crawl_date: Optional[str] = None,
    end_crawl_date: Optional[str] = None,
    start_published_date: Optional[str] = None,
    end_published_date: Optional[str] = None,
    exclude_source_domain: Optional[bool] = None,
    category: Optional[str] = None,
    text: Any = None,
    highlights: Any = None,
    context: Any = None,
    moderation: Optional[bool] = None,
) -> Tuple[Dict[str, Any], ExaCallMeta]:
    payload = build_find_similar_payload(
        url,
        config,
        num_results=num_results,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        start_crawl_date=start_crawl_date,
        end_crawl_date=end_crawl_date,
        start_published_date=start_published_date,
        end_published_date=end_published_date,
        exclude_source_domain=exclude_source_domain,
        category=category,
        text=text,
        highlights=highlights,
        context=context,
        moderation=moderation,
    )
    estimated_cost = estimate_cost_from_pricing(
        _find_similar_cost_payload(payload),
        int(payload["numResults"]),
        pricing,
        int(config["max_supported_results_for_estimate"]),
    )

    response_json, cache_hit = cache_store.get_or_set(
        payload,
        estimated_cost,
        run_id=run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda request_payload: exa_http_call(
            request_payload,
            config=config,
            exa_api_key=exa_api_key,
            smoke_no_network=smoke_no_network,
            endpoint_name="findSimilar",
        ),
    )

    return response_json, _build_call_meta(
        payload=payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost=estimated_cost,
    )


def exa_answer(
    query: str,
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
    exa_api_key: str,
    smoke_no_network: bool,
    run_id: str,
    cache_store: SqliteCacheStore,
) -> Tuple[Dict[str, Any], ExaCallMeta]:
    payload = build_answer_payload(query)
    estimated_cost = _estimate_answer_cost_from_pricing(pricing)

    response_json, cache_hit = cache_store.get_or_set(
        payload,
        estimated_cost,
        run_id=run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda request_payload: exa_http_call(
            request_payload,
            config=config,
            exa_api_key=exa_api_key,
            smoke_no_network=smoke_no_network,
            endpoint_name="answer",
        ),
    )

    return response_json, _build_call_meta(
        payload=payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost=estimated_cost,
        resolved_search_type=None,
    )


def exa_research(
    query: str,
    *,
    config: Mapping[str, Any],
    pricing: Mapping[str, float],
    exa_api_key: str,
    smoke_no_network: bool,
    run_id: str,
    cache_store: SqliteCacheStore,
) -> Tuple[Dict[str, Any], ExaCallMeta]:
    payload = build_research_payload(query)
    estimated_cost = _estimate_research_cost_from_pricing(pricing)

    response_json, cache_hit = cache_store.get_or_set(
        payload,
        estimated_cost,
        run_id=run_id,
        budget_cap_usd=float(config["budget_cap_usd"]),
        fetcher=lambda request_payload: exa_http_call(
            request_payload,
            config=config,
            exa_api_key=exa_api_key,
            smoke_no_network=smoke_no_network,
            endpoint_name="research",
        ),
    )

    return response_json, _build_call_meta(
        payload=payload,
        response_json=response_json,
        cache_hit=cache_hit,
        estimated_cost=estimated_cost,
        resolved_search_type=None,
    )


def _build_call_meta(
    *,
    payload: Dict[str, Any],
    response_json: Any,
    cache_hit: bool,
    estimated_cost: float,
    resolved_search_type: Optional[str] = ...,
) -> ExaCallMeta:
    if resolved_search_type is ...:
        resolved_search_type = (
            response_json.get("resolvedSearchType")
            if isinstance(response_json, dict)
            else None
        )
    return ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=resolved_search_type,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def _estimate_answer_cost_from_pricing(pricing: Mapping[str, float]) -> float:
    for key in ("answer", "answer_1", "answer_1_25"):
        if key in pricing:
            return float(pricing[key])
    return float(pricing.get("search_1_25", 0.0))


def _estimate_research_cost_from_pricing(pricing: Mapping[str, float]) -> float:
    for key in ("research", "research_1", "research_1_25"):
        if key in pricing:
            return float(pricing[key])
    return float(pricing.get("search_1_25", 0.0))


def _resolve_exa_endpoint(base_url: str, *, endpoint_name: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/search"):
        return trimmed[: -len("/search")] + f"/{endpoint_name}"
    return f"{trimmed}/{endpoint_name}"


def _find_similar_cost_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    cost_payload: Dict[str, Any] = {"type": "auto"}
    contents: Dict[str, Any] = {}
    if payload.get("text") is not False:
        contents["text"] = True
    if payload.get("highlights") is not None and payload.get("highlights") is not False:
        contents["highlights"] = (
            payload.get("highlights")
            if isinstance(payload.get("highlights"), Mapping)
            else {"highlightsPerUrl": 1, "numSentences": 2}
        )
    if contents:
        cost_payload["contents"] = contents
    return cost_payload
