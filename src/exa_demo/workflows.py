from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

import requests

from .client import build_exa_payload

EXA_ANSWER_ENDPOINT = "https://api.exa.ai/answer"


def build_answer_request_payload(query: str) -> Dict[str, Any]:
    return {
        "query": query,
    }


def build_structured_search_request_payload(
    query: str,
    config: Mapping[str, Any],
    output_schema: Mapping[str, Any],
) -> Dict[str, Any]:
    payload = build_exa_payload(query, config, num_results=int(config["num_results"]))
    payload["outputSchema"] = json.loads(json.dumps(dict(output_schema), ensure_ascii=False, default=str))
    return payload


def build_find_similar_request_payload(url: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "url": url,
        "numResults": int(config["num_results"]),
        "type": str(config.get("search_type") or "deep"),
    }
    contents: Dict[str, Any] = {}
    if config.get("use_text"):
        contents["text"] = True
    if config.get("use_summary"):
        contents["summary"] = {
            "query": f"Summarize pages similar to {url}."
        }
    if config.get("use_highlights", True):
        contents["highlights"] = {
            "highlightsPerUrl": int(config["highlights_per_url"]),
            "numSentences": int(config["highlight_num_sentences"]),
        }
    if contents:
        payload["contents"] = contents
    if config.get("include_domains"):
        payload["includeDomains"] = list(config["include_domains"])
    if config.get("exclude_domains"):
        payload["excludeDomains"] = list(config["exclude_domains"])
    return payload


def answer_http_call(
    payload: Dict[str, Any],
    *,
    exa_api_key: str,
    smoke_no_network: bool,
    timeout: int = 60,
) -> Dict[str, Any]:
    if smoke_no_network:
        return mock_answer_response(payload)

    if not exa_api_key:
        raise RuntimeError("Missing EXA_API_KEY for live Exa answer request.")

    headers = {"x-api-key": exa_api_key, "Content-Type": "application/json"}
    response = requests.post(
        EXA_ANSWER_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def find_similar_http_call(
    payload: Dict[str, Any],
    *,
    exa_api_key: str,
    smoke_no_network: bool,
    config: Mapping[str, Any],
    timeout: int = 60,
) -> Dict[str, Any]:
    if smoke_no_network:
        return mock_find_similar_response(payload)

    if not exa_api_key:
        raise RuntimeError("Missing EXA_API_KEY for live Exa find-similar request.")

    headers = {"x-api-key": exa_api_key, "Content-Type": "application/json"}
    response = requests.post(
        resolve_exa_endpoint(str(config["exa_endpoint"]), endpoint_name="findSimilar"),
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def structured_search_http_call(
    payload: Dict[str, Any],
    *,
    exa_api_key: str,
    smoke_no_network: bool,
    config: Mapping[str, Any],
    timeout: int = 60,
) -> Dict[str, Any]:
    if smoke_no_network:
        return mock_structured_search_response(payload)

    if not exa_api_key:
        raise RuntimeError("Missing EXA_API_KEY for live Exa structured-search request.")

    headers = {"x-api-key": exa_api_key, "Content-Type": "application/json"}
    response = requests.post(
        resolve_exa_endpoint(str(config["exa_endpoint"]), endpoint_name="search"),
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def mock_answer_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    slug = query[:24].strip().lower().replace(" ", "-") or "answer"
    citations = [
        {
            "title": "Florida appraisal clause overview",
            "url": "https://example.com/florida-appraisal-clause",
            "snippet": "Mock citation about appraisal clause dispute flow.",
        },
        {
            "title": "Insurance claim dispute process",
            "url": "https://example.com/insurance-dispute-process",
            "snippet": "Mock citation about dispute resolution steps.",
        },
    ]
    return {
        "requestId": f"smoke-{slug}",
        "answer": (
            "Mock answer: the Florida appraisal clause dispute process typically starts with a demand, "
            "followed by insurer response and, if needed, appraisal selection."
        ),
        "citations": citations,
        "_smokeMode": True,
    }


def mock_find_similar_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    seed_url = str(payload.get("url") or "")
    slug = seed_url[:24].strip().lower().replace(" ", "-") or "find-similar"
    similar_results = [
        {
            "title": "Florida Insurance Litigation Firm",
            "url": "https://example.com/florida-insurance-litigation-firm",
            "snippet": "Mock result for seed-url discovery and competitor analysis.",
            "score": 0.98,
        },
        {
            "title": "Public Adjuster and Catastrophe Claims Team",
            "url": "https://example.com/public-adjuster-catastrophe-claims",
            "snippet": "Mock result for expert discovery and similar professional pages.",
            "score": 0.94,
        },
        {
            "title": "Property Insurance Appraisal Resources",
            "url": "https://example.com/property-insurance-appraisal-resources",
            "snippet": "Mock result for content discovery around appraisal and coverage disputes.",
            "score": 0.91,
        },
    ]
    return {
        "requestId": f"smoke-{slug}",
        "resolvedSearchType": str(payload.get("type") or "deep"),
        "results": similar_results,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def mock_structured_search_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    schema = payload.get("outputSchema") if isinstance(payload.get("outputSchema"), Mapping) else {}
    slug = query[:24].strip().lower().replace(" ", "-") or "structured-search"
    properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    property_names = sorted(str(key) for key in properties.keys())
    structured_output = {
        "query": query,
        "schema_title": str(schema.get("title") or "structured-output"),
        "field_names": property_names,
        "record_count": 1,
        "records": [
            {
                "name": "Mock Structured Record",
                "role": "Insurance expert witness",
                "firm": "Mock Advisory Group",
                "state_licenses": ["FL"],
                "specializations": ["catastrophe claims", "appraisal"],
                "notable_cases_or_experience": "Mock structured output for smoke testing.",
            }
        ],
    }
    return {
        "requestId": f"smoke-{slug}",
        "resolvedSearchType": str(payload.get("type") or "deep"),
        "structuredData": structured_output,
        "results": [],
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def build_find_similar_artifact(
    seed_url: str,
    *,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
) -> Dict[str, Any]:
    results = _normalize_find_similar_results(response_json.get("results"))
    return {
        "seed_url": seed_url,
        "request_payload": json.loads(json.dumps(dict(request_payload), ensure_ascii=False, default=str)),
        "response": json.loads(json.dumps(dict(response_json), ensure_ascii=False, default=str)),
        "request_id": response_json.get("requestId") if isinstance(response_json, Mapping) else None,
        "cache_hit": cache_hit,
        "estimated_cost_usd": float(estimated_cost_usd),
        "actual_cost_usd": find_similar_actual_cost(response_json),
        "result_count": len(results),
        "results": results,
        "top_result": results[0] if results else None,
    }


def build_research_artifact(
    query: str,
    *,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
) -> Dict[str, Any]:
    report_text = _extract_research_report_text(response_json)
    citations = _normalize_citations(
        response_json.get("citations")
        if isinstance(response_json.get("citations"), list)
        else response_json.get("sources")
    )
    return {
        "query": query,
        "request_payload": json.loads(json.dumps(dict(request_payload), ensure_ascii=False, default=str)),
        "response": json.loads(json.dumps(dict(response_json), ensure_ascii=False, default=str)),
        "request_id": response_json.get("requestId") if isinstance(response_json, Mapping) else None,
        "cache_hit": cache_hit,
        "estimated_cost_usd": float(estimated_cost_usd),
        "actual_cost_usd": research_actual_cost(response_json),
        "report_text": report_text,
        "report_preview": report_text[:220],
        "citation_count": len(citations),
        "citations": citations,
    }


def build_answer_artifact(
    query: str,
    *,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
) -> Dict[str, Any]:
    answer_text = str(response_json.get("answer") or response_json.get("text") or "").strip()
    citations = _normalize_citations(response_json.get("citations"))
    return {
        "query": query,
        "request_payload": dict(request_payload),
        "response": json.loads(json.dumps(dict(response_json), ensure_ascii=False, default=str)),
        "request_id": response_json.get("requestId") if isinstance(response_json, Mapping) else None,
        "cache_hit": cache_hit,
        "estimated_cost_usd": float(estimated_cost_usd),
        "actual_cost_usd": answer_actual_cost(response_json),
        "answer_text": answer_text,
        "citation_count": len(citations),
        "citations": citations,
    }


def build_structured_search_artifact(
    query: str,
    *,
    schema_path: Path,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
) -> Dict[str, Any]:
    structured_output = _extract_structured_output(response_json)
    return {
        "query": query,
        "schema_file": str(schema_path),
        "request_payload": json.loads(json.dumps(dict(request_payload), ensure_ascii=False, default=str)),
        "response": json.loads(json.dumps(dict(response_json), ensure_ascii=False, default=str)),
        "request_id": response_json.get("requestId") if isinstance(response_json, Mapping) else None,
        "cache_hit": cache_hit,
        "estimated_cost_usd": float(estimated_cost_usd),
        "actual_cost_usd": structured_search_actual_cost(response_json),
        "structured_output": structured_output,
        "structured_output_keys": sorted(structured_output.keys()) if isinstance(structured_output, Mapping) else [],
    }


def _normalize_citations(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    citations: list[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        citations.append(
            {
                "title": str(item.get("title") or item.get("name") or "").strip(),
                "url": str(item.get("url") or item.get("sourceUrl") or "").strip(),
                "snippet": str(item.get("snippet") or item.get("text") or item.get("passage") or "").strip(),
            }
        )
    return citations


def _normalize_find_similar_results(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    results: list[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        results.append(
            {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "snippet": str(item.get("snippet") or item.get("text") or "").strip(),
                "score": _coerce_optional_float(item.get("score")),
            }
        )
    return results


def answer_actual_cost(response_json: Mapping[str, Any]) -> float:
    return _answer_actual_cost(response_json)


def research_actual_cost(response_json: Mapping[str, Any]) -> float:
    return _answer_actual_cost(response_json)


def structured_search_actual_cost(response_json: Mapping[str, Any]) -> float:
    return _answer_actual_cost(response_json)


def find_similar_actual_cost(response_json: Mapping[str, Any]) -> float:
    return _answer_actual_cost(response_json)


def _answer_actual_cost(response_json: Mapping[str, Any]) -> float:
    cost = response_json.get("costDollars")
    if isinstance(cost, Mapping):
        total = cost.get("total")
        try:
            return float(total)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _extract_structured_output(response_json: Mapping[str, Any]) -> Any:
    if not isinstance(response_json, Mapping):
        return None

    for key in ("structuredData", "structuredOutput", "output", "data"):
        value = response_json.get(key)
        if value is not None:
            return value

    results = response_json.get("results")
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, Mapping):
                continue
            for key in ("structuredData", "structuredOutput", "output", "data"):
                value = item.get(key)
                if value is not None:
                    return value
    return None


def _extract_research_report_text(response_json: Mapping[str, Any]) -> str:
    if not isinstance(response_json, Mapping):
        return ""

    for key in ("report", "reportText", "markdown", "summary", "text", "response", "content"):
        value = response_json.get(key)
        if value is not None:
            return str(value).strip()
    return ""


def load_json_schema(schema_path: Path) -> Dict[str, Any]:
    schema_text = schema_path.read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    if not isinstance(schema, Mapping):
        raise ValueError(f"Schema file must contain a JSON object: {schema_path}")
    return dict(schema)


def resolve_exa_endpoint(base_url: str, *, endpoint_name: str = "search") -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/search"):
        return trimmed[: -len("/search")] + f"/{endpoint_name}"
    return f"{trimmed}/{endpoint_name}"


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
