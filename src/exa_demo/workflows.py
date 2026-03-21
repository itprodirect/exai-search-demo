from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def build_find_similar_artifact(
    seed_url: str,
    *,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
) -> Dict[str, Any]:
    results = _normalize_find_similar_results(response_json.get("results"))
    payload = {
        "seed_url": seed_url,
        "result_count": len(results),
        "results": results,
        "top_result": results[0] if results else None,
    }
    return {
        **_artifact_base(
            request_payload=request_payload,
            response_json=response_json,
            cache_hit=cache_hit,
            estimated_cost_usd=estimated_cost_usd,
            actual_cost_usd=find_similar_actual_cost(response_json),
        ),
        **payload,
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
    payload = {
        "query": query,
        "report_text": report_text,
        "report_preview": report_text[:220],
        "citation_count": len(citations),
        "citations": citations,
    }
    return {
        **_artifact_base(
            request_payload=request_payload,
            response_json=response_json,
            cache_hit=cache_hit,
            estimated_cost_usd=estimated_cost_usd,
            actual_cost_usd=research_actual_cost(response_json),
        ),
        **payload,
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
    payload = {
        "query": query,
        "answer_text": answer_text,
        "citation_count": len(citations),
        "citations": citations,
    }
    return {
        **_artifact_base(
            request_payload=request_payload,
            response_json=response_json,
            cache_hit=cache_hit,
            estimated_cost_usd=estimated_cost_usd,
            actual_cost_usd=answer_actual_cost(response_json),
        ),
        **payload,
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
    payload = {
        "query": query,
        "schema_file": str(schema_path),
        "structured_output": structured_output,
        "structured_output_keys": sorted(structured_output.keys()) if isinstance(structured_output, Mapping) else [],
    }
    return {
        **_artifact_base(
            request_payload=request_payload,
            response_json=response_json,
            cache_hit=cache_hit,
            estimated_cost_usd=estimated_cost_usd,
            actual_cost_usd=structured_search_actual_cost(response_json),
        ),
        **payload,
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


def _artifact_base(
    *,
    request_payload: Mapping[str, Any],
    response_json: Mapping[str, Any],
    cache_hit: bool,
    estimated_cost_usd: float,
    actual_cost_usd: float,
) -> Dict[str, Any]:
    return {
        "request_payload": _jsonable_mapping(request_payload),
        "response": _jsonable_mapping(response_json),
        "request_id": _request_id(response_json),
        "cache_hit": cache_hit,
        "estimated_cost_usd": float(estimated_cost_usd),
        "actual_cost_usd": float(actual_cost_usd),
    }


def _jsonable_mapping(value: Mapping[str, Any]) -> Dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))


def _request_id(response_json: Mapping[str, Any]) -> str | None:
    if not isinstance(response_json, Mapping):
        return None
    value = response_json.get("requestId")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
