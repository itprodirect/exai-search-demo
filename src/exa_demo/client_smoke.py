from __future__ import annotations

from typing import Any, Dict, Mapping
from urllib.parse import urlparse

from .cache import sha256_hex


def smoke_response_for_request(
    payload: Mapping[str, Any], *, endpoint_name: str
) -> Dict[str, Any]:
    if endpoint_name == "findSimilar":
        return mock_exa_find_similar_response(payload)
    if isinstance(payload.get("outputSchema"), Mapping):
        return mock_exa_structured_search_response(payload)
    if endpoint_name == "answer":
        return mock_exa_answer_response(payload)
    if endpoint_name == "research":
        return mock_exa_research_response(payload)
    return mock_exa_response(payload)


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
    wants_highlights = (
        payload.get("highlights") is not None and payload.get("highlights") is not False
    )
    wants_context = (
        payload.get("context") is not None and payload.get("context") is not False
    )

    source_domain = _domain_from_url(url)
    result_domain = (
        f"related-{slug}.example.com"
        if bool(payload.get("excludeSourceDomain"))
        else source_domain
    )
    mock_titles = [
        "Florida Insurance Litigation Firm",
        "Public Adjuster and Catastrophe Claims Team",
        "Property Insurance Appraisal Resources",
    ]
    mock_snippets = [
        "Mock result for seed-url discovery and competitor analysis.",
        "Mock result for expert discovery and similar professional pages.",
        "Mock result for content discovery around appraisal and coverage disputes.",
    ]
    results = []
    for index in range(num_results):
        result_url = f"https://{result_domain}/similar/{slug}-{index + 1}"
        title = (
            mock_titles[index]
            if index < len(mock_titles)
            else f"Mock Similar Result {index + 1} - CAT loss / insurance expert"
        )
        snippet = (
            mock_snippets[index]
            if index < len(mock_snippets)
            else "Mock result for seed-url discovery and similar-page analysis."
        )
        item: Dict[str, Any] = {
            "id": result_url,
            "title": title,
            "url": result_url,
            "publishedDate": "2026-03-18",
            "author": "Mock Analyst",
            "snippet": snippet,
            "score": round(0.98 - (index * 0.04), 2),
        }
        if wants_text:
            item["text"] = (
                f"Mock similar text for seed URL: {url}. Public/professional info only."
            )
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
    schema = (
        payload.get("outputSchema")
        if isinstance(payload.get("outputSchema"), Mapping)
        else {}
    )
    structured_output = _mock_structured_output(schema, query)
    properties = (
        schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
    )
    structured_data = {
        "query": query,
        "schema_title": str(schema.get("title") or "structured-output"),
        "field_names": sorted(str(key) for key in properties.keys()),
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
        "structuredData": structured_data,
        "structuredOutput": structured_output,
        "costDollars": {"search": 0.0, "contents": 0.0, "total": 0.0},
        "_smokeMode": True,
    }


def mock_exa_answer_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    query = str(payload.get("query") or "")
    slug = sha256_hex(query)[:8]
    citations = [
        {
            "title": "Florida appraisal clause overview",
            "url": f"https://example.com/mock-answer/{slug}/1",
            "snippet": "Mock citation about appraisal clause dispute flow.",
            "publishedDate": "2026-03-18",
            "author": "Mock Analyst",
        },
        {
            "title": "Insurance claim dispute process",
            "url": f"https://example.com/mock-answer/{slug}/2",
            "snippet": "Mock citation about dispute resolution steps.",
            "publishedDate": "2026-03-18",
            "author": "Mock Analyst",
        },
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


def _domain_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.netloc:
        return parsed.netloc
    return "example.com"
