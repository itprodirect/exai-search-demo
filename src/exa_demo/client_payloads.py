from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence


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

    resolved_include_domains = _clean_string_list(
        include_domains if include_domains is not None else config["include_domains"]
    )
    if resolved_include_domains:
        payload["includeDomains"] = resolved_include_domains

    resolved_exclude_domains = _clean_string_list(
        exclude_domains if exclude_domains is not None else config["exclude_domains"]
    )
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


def _clean_string_list(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            result.append(text)
    return result
