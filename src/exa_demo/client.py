from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests

from .cache import SqliteCacheStore, parse_actual_cost, request_hash_for_payload, sha256_hex
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


def build_exa_payload(
    query: str,
    config: Mapping[str, Any],
    *,
    num_results: Optional[int] = None,
) -> Dict[str, Any]:
    resolved_num_results = int(num_results or config["num_results"])
    payload: Dict[str, Any] = {
        "query": query,
        "type": config["search_type"],
        "category": config["category"],
        "numResults": resolved_num_results,
        "userLocation": config["user_location"],
        "moderation": config["moderation"],
    }

    if config["include_domains"]:
        payload["includeDomains"] = config["include_domains"]
    if config["exclude_domains"]:
        payload["excludeDomains"] = config["exclude_domains"]
    additional_queries = [
        str(item).strip()
        for item in (config.get("additional_queries") or [])
        if str(item).strip()
    ]
    if additional_queries:
        payload["additionalQueries"] = additional_queries
    if config.get("start_published_date"):
        payload["startPublishedDate"] = str(config["start_published_date"])
    if config.get("end_published_date"):
        payload["endPublishedDate"] = str(config["end_published_date"])
    if config.get("livecrawl"):
        payload["livecrawl"] = True

    contents: Dict[str, Any] = {}
    if config["use_text"]:
        contents["text"] = True
    if config["use_highlights"]:
        contents["highlights"] = {
            "highlightsPerUrl": config["highlights_per_url"],
            "numSentences": config["highlight_num_sentences"],
        }
    if config["use_summary"]:
        contents["summary"] = {
            "query": "Summarize the person's professional background and insurance/CAT relevance."
        }

    if contents:
        payload["contents"] = contents

    return payload


def build_answer_payload(query: str) -> Dict[str, Any]:
    return {"query": query, "text": True}


def build_research_payload(query: str) -> Dict[str, Any]:
    return {"query": query}


def build_structured_search_payload(
    query: str,
    config: Mapping[str, Any],
    output_schema: Mapping[str, Any],
    *,
    num_results: Optional[int] = None,
) -> Dict[str, Any]:
    payload = build_exa_payload(query, config, num_results=num_results)
    payload["outputSchema"] = dict(output_schema)
    return payload


def build_find_similar_payload(
    url: str,
    config: Mapping[str, Any],
    *,
    num_results: Optional[int] = None,
    include_domains: Optional[Sequence[str]] = None,
    exclude_domains: Optional[Sequence[str]] = None,
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
) -> Dict[str, Any]:
    resolved_num_results = int(num_results or config["num_results"])
    payload: Dict[str, Any] = {
        "url": url,
        "numResults": resolved_num_results,
        "category": str(category or config["category"]),
        "moderation": bool(config["moderation"] if moderation is None else moderation),
    }

    resolved_include_domains = _clean_string_list(include_domains if include_domains is not None else config["include_domains"])
    if resolved_include_domains:
        payload["includeDomains"] = resolved_include_domains

    resolved_exclude_domains = _clean_string_list(exclude_domains if exclude_domains is not None else config["exclude_domains"])
    if resolved_exclude_domains:
        payload["excludeDomains"] = resolved_exclude_domains

    if start_crawl_date:
        payload["startCrawlDate"] = str(start_crawl_date)
    if end_crawl_date:
        payload["endCrawlDate"] = str(end_crawl_date)
    if start_published_date:
        payload["startPublishedDate"] = str(start_published_date)
    if end_published_date:
        payload["endPublishedDate"] = str(end_published_date)
    if exclude_source_domain is not None:
        payload["excludeSourceDomain"] = bool(exclude_source_domain)
    if context is not None:
        payload["context"] = context

    resolved_text = True if text is None else text
    if resolved_text is not None:
        payload["text"] = resolved_text
    if highlights is not None:
        payload["highlights"] = highlights

    return payload


def mock_exa_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    num_results = int(payload.get("numResults") or 5)
    contents = payload.get("contents") or {}
    wants_highlights = isinstance(contents.get("highlights"), dict)
    wants_text = contents.get("text") is True
    wants_summary = isinstance(contents.get("summary"), dict)

    slug = sha256_hex(query)[:8]
    results = []
    for index in range(num_results):
        item: Dict[str, Any] = {
            "id": f"mock-{slug}-{index + 1}",
            "title": f"Mock Professional Result {index + 1} - CAT loss / insurance expert",
            "url": f"https://www.linkedin.com/in/mock-{slug}-{index + 1}",
        }
        if wants_highlights:
            item["highlights"] = [
                f"Mock highlight for query: {query}. Public professional profile for insurance litigation and expert witness context."
            ]
            item["highlightScores"] = [0.99]
        if wants_text:
            item["text"] = f"Mock text body for query: {query}. Public/professional info only."
        if wants_summary:
            item["summary"] = "Mock summary: professional background relevant to insurance/CAT-loss workflows."
        results.append(item)

    return {
        "requestId": f"smoke-{slug}",
        "resolvedSearchType": str(payload.get("type") or "auto"),
        "results": results,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def mock_exa_find_similar_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    url = str(payload.get("url") or "")
    slug = sha256_hex(url)[:8]
    num_results = int(payload.get("numResults") or 5)
    wants_text = payload.get("text") is not False
    wants_highlights = payload.get("highlights") is not None and payload.get("highlights") is not False
    wants_context = payload.get("context") is not None and payload.get("context") is not False

    source_domain = _domain_from_url(url)
    result_domain = f"related-{slug}.example.com" if bool(payload.get("excludeSourceDomain")) else source_domain
    results = []
    for index in range(num_results):
        result_url = f"https://{result_domain}/similar/{slug}-{index + 1}"
        item: Dict[str, Any] = {
            "id": result_url,
            "title": f"Mock Similar Result {index + 1} - CAT loss / insurance expert",
            "url": result_url,
            "publishedDate": "2026-03-18",
            "author": "Mock Analyst",
        }
        if wants_text:
            item["text"] = f"Mock similar text for seed URL: {url}. Public/professional info only."
        if wants_highlights:
            item["highlights"] = [
                f"Mock highlight for seed URL: {url}. Public professional profile for insurance litigation and expert witness context."
            ]
            item["highlightScores"] = [0.99]
        results.append(item)

    response: Dict[str, Any] = {
        "requestId": f"smoke-{slug}",
        "results": results,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }
    if wants_context:
        response["context"] = (
            f"Mock context for seed URL {url}. "
            f"Similar results are generated from {result_domain}."
        )
    return response


def mock_exa_structured_search_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    slug = sha256_hex(query)[:8]
    num_results = int(payload.get("numResults") or 5)
    structured_output = _mock_structured_output(payload.get("outputSchema"), query)

    results = []
    for index in range(num_results):
        item: Dict[str, Any] = {
            "id": f"mock-{slug}-{index + 1}",
            "title": f"Mock Structured Result {index + 1} - CAT loss / insurance expert",
            "url": f"https://www.linkedin.com/in/mock-structured-{slug}-{index + 1}",
        }
        results.append(item)

    return {
        "requestId": f"smoke-{slug}",
        "resolvedSearchType": str(payload.get("type") or "auto"),
        "results": results,
        "structuredOutput": structured_output,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def mock_exa_answer_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    slug = sha256_hex(query)[:8]
    citations = [
        {
            "title": f"Mock Answer Citation {index + 1}",
            "url": f"https://example.com/mock-answer/{slug}/{index + 1}",
            "snippet": (
                f"Mock source snippet {index + 1} for query: {query}. "
                "Public/professional info only."
            ),
            "publishedDate": "2026-03-18",
            "author": "Mock Analyst",
        }
        for index in range(2)
    ]
    return {
        "requestId": f"smoke-{slug}",
        "answer": f"Mock answer for query: {query}. Public/professional info only.",
        "citations": citations,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def mock_exa_research_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    slug = sha256_hex(query)[:8]
    citations = [
        {
            "title": f"Mock Research Source {index + 1}",
            "url": f"https://example.com/mock-research/{slug}/{index + 1}",
            "snippet": (
                f"Mock research source snippet {index + 1} for query: {query}. "
                "Public/professional info only."
            ),
            "publishedDate": "2026-03-19",
            "author": "Mock Analyst",
        }
        for index in range(3)
    ]
    return {
        "requestId": f"smoke-{slug}",
        "report": (
            f"Mock research report for query: {query}.\n\n"
            "Key takeaways:\n"
            "- Market conditions remain dynamic.\n"
            "- Regulatory and litigation monitoring should continue.\n"
            "- Human review is required before operational use."
        ),
        "citations": citations,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


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

    meta = ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=response_json.get("resolvedSearchType") if isinstance(response_json, dict) else None,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    return response_json, meta


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
    payload = build_structured_search_payload(query, config, output_schema, num_results=num_results)
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

    meta = ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=response_json.get("resolvedSearchType") if isinstance(response_json, dict) else None,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    return response_json, meta


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
    include_domains: Optional[Sequence[str]] = None,
    exclude_domains: Optional[Sequence[str]] = None,
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

    meta = ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=response_json.get("resolvedSearchType") if isinstance(response_json, dict) else None,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    return response_json, meta


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

    meta = ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=None,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    return response_json, meta


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

    meta = ExaCallMeta(
        cache_hit=cache_hit,
        request_hash=request_hash_for_payload(payload),
        request_payload=payload,
        estimated_cost_usd=estimated_cost,
        actual_cost_usd=parse_actual_cost(response_json),
        request_id=response_json.get("requestId") if isinstance(response_json, dict) else None,
        resolved_search_type=None,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    return response_json, meta


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


def _mock_structured_output(schema: Any, query: str, *, path: str = "output") -> Any:
    if isinstance(schema, Mapping):
        schema_type = schema.get("type")
        if schema_type == "object":
            properties = schema.get("properties")
            if isinstance(properties, Mapping):
                return {
                    str(key): _mock_structured_output(value, query, path=f"{path}.{key}")
                    for key, value in properties.items()
                }
            return {"value": f"Mock {path} for query: {query}"}
        if schema_type == "array":
            items = schema.get("items")
            return [_mock_structured_output(items, query, path=f"{path}[0]")]
        if schema_type == "string":
            return f"Mock {path.rsplit('.', 1)[-1]} for query: {query}"
        if schema_type == "integer":
            return 1
        if schema_type == "number":
            return 1.0
        if schema_type == "boolean":
            return True
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and enum_values:
            return enum_values[0]
    return f"Mock {path} for query: {query}"


def _clean_string_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            result.append(text)
    return result


def _domain_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc:
        return parsed.netloc
    return "example.com"
