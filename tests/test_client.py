from __future__ import annotations

from exa_demo.client import (
    build_answer_payload,
    build_exa_payload,
    build_find_similar_payload,
    build_research_payload,
    build_structured_search_payload,
    exa_answer,
    exa_find_similar,
    exa_research,
    exa_structured_search,
    mock_exa_answer_response,
    mock_exa_find_similar_response,
    mock_exa_response,
    mock_exa_research_response,
    mock_exa_structured_search_response,
)
from exa_demo.config import default_config
from exa_demo.config import default_pricing


class FakeCacheStore:
    def __init__(self) -> None:
        self.calls = []

    def get_or_set(self, payload, estimated_cost, *, run_id, budget_cap_usd, fetcher):
        self.calls.append(
            {
                "payload": payload,
                "estimated_cost": estimated_cost,
                "run_id": run_id,
                "budget_cap_usd": budget_cap_usd,
            }
        )
        return fetcher(payload), False


def test_build_exa_payload_includes_additive_deep_search_fields() -> None:
    config = default_config()
    config.update(
        {
            "additional_queries": [
                "licensed public adjuster Florida",
                "  catastrophe claims expert witness  ",
                "",
            ],
            "start_published_date": "2026-01-01",
            "end_published_date": "2026-03-01",
            "livecrawl": True,
        }
    )

    payload = build_exa_payload("insurance expert witness", config, num_results=3)

    assert payload["query"] == "insurance expert witness"
    assert payload["numResults"] == 3
    assert payload["additionalQueries"] == [
        "licensed public adjuster Florida",
        "catastrophe claims expert witness",
    ]
    assert payload["startPublishedDate"] == "2026-01-01"
    assert payload["endPublishedDate"] == "2026-03-01"
    assert payload["livecrawl"] is True
    assert "results" not in payload


def test_build_exa_payload_leaves_additive_fields_out_by_default() -> None:
    config = default_config()

    payload = build_exa_payload("insurance expert witness", config)

    assert "additionalQueries" not in payload
    assert "startPublishedDate" not in payload
    assert "endPublishedDate" not in payload
    assert "livecrawl" not in payload


def test_mock_exa_response_preserves_search_result_shape_with_additive_controls() -> None:
    payload = build_exa_payload(
        "insurance expert witness",
        {
            **default_config(),
            "additional_queries": ["licensed public adjuster Florida"],
            "start_published_date": "2026-01-01",
            "end_published_date": "2026-03-01",
            "livecrawl": True,
        },
    )

    response = mock_exa_response(payload)

    assert response["resolvedSearchType"] == "auto"
    assert isinstance(response["results"], list)
    assert len(response["results"]) == payload["numResults"]
    assert response["results"][0]["title"].startswith("Mock Professional Result")


def test_build_find_similar_payload_includes_similarity_controls() -> None:
    config = default_config()
    config.update(
        {
            "include_domains": ["example.com"],
            "exclude_domains": ["badexample.com"],
            "moderation": False,
        }
    )

    payload = build_find_similar_payload(
        "https://example.com/article",
        config,
        num_results=3,
        start_crawl_date="2026-01-01",
        end_crawl_date="2026-03-01",
        start_published_date="2026-01-15",
        end_published_date="2026-03-15",
        exclude_source_domain=True,
        text=True,
        highlights={"highlightsPerUrl": 2, "numSentences": 1},
        context=True,
    )

    assert payload["url"] == "https://example.com/article"
    assert payload["numResults"] == 3
    assert payload["includeDomains"] == ["example.com"]
    assert payload["excludeDomains"] == ["badexample.com"]
    assert payload["startCrawlDate"] == "2026-01-01"
    assert payload["endCrawlDate"] == "2026-03-01"
    assert payload["startPublishedDate"] == "2026-01-15"
    assert payload["endPublishedDate"] == "2026-03-15"
    assert payload["excludeSourceDomain"] is True
    assert payload["moderation"] is False
    assert payload["text"] is True
    assert payload["highlights"] == {"highlightsPerUrl": 2, "numSentences": 1}
    assert payload["context"] is True


def test_mock_exa_find_similar_response_returns_context_and_text() -> None:
    payload = build_find_similar_payload(
        "https://example.com/article",
        default_config(),
        exclude_source_domain=True,
        text=True,
        highlights=True,
        context=True,
    )

    response = mock_exa_find_similar_response(payload)

    assert isinstance(response["results"], list)
    assert len(response["results"]) == payload["numResults"]
    assert response["context"].startswith("Mock context for seed URL https://example.com/article")
    assert response["results"][0]["text"].startswith("Mock similar text for seed URL:")
    assert response["results"][0]["highlights"][0].startswith("Mock highlight for seed URL:")
    assert response["results"][0]["url"].split("/")[2].startswith("related-")


def test_build_structured_search_payload_adds_output_schema() -> None:
    config = default_config()
    config.update(
        {
            "additional_queries": ["licensed public adjuster Florida"],
            "livecrawl": True,
        }
    )
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "professionals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                    },
                },
            },
        },
    }

    payload = build_structured_search_payload(
        "insurance expert witness",
        config,
        output_schema,
        num_results=2,
    )

    assert payload["query"] == "insurance expert witness"
    assert payload["numResults"] == 2
    assert payload["additionalQueries"] == ["licensed public adjuster Florida"]
    assert payload["livecrawl"] is True
    assert payload["outputSchema"] == output_schema


def test_mock_exa_structured_search_response_returns_structured_output() -> None:
    payload = build_structured_search_payload(
        "insurance expert witness",
        default_config(),
        {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "professionals": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                        },
                    },
                },
            },
        },
    )

    response = mock_exa_structured_search_response(payload)

    assert response["resolvedSearchType"] == "auto"
    assert response["structuredOutput"]["summary"].startswith("Mock summary for query:")
    assert response["structuredOutput"]["professionals"][0]["name"].startswith("Mock name for query:")
    assert len(response["results"]) == payload["numResults"]


def test_build_answer_payload_is_query_only() -> None:
    payload = build_answer_payload("What is the Florida appraisal clause dispute process?")

    assert payload == {"query": "What is the Florida appraisal clause dispute process?", "text": True}


def test_mock_exa_answer_response_returns_citations() -> None:
    payload = build_answer_payload("What is the Florida appraisal clause dispute process?")

    response = mock_exa_answer_response(payload)

    assert response["answer"].startswith("Mock answer for query:")
    assert isinstance(response["citations"], list)
    assert len(response["citations"]) == 2
    assert response["citations"][0]["url"].startswith("https://example.com/mock-answer/")


def test_build_research_payload_is_query_only() -> None:
    payload = build_research_payload("Summarize the Florida CAT market outlook.")

    assert payload == {"query": "Summarize the Florida CAT market outlook."}


def test_mock_exa_research_response_returns_report_and_citations() -> None:
    payload = build_research_payload("Summarize the Florida CAT market outlook.")

    response = mock_exa_research_response(payload)

    assert response["report"].startswith("Mock research report for query:")
    assert isinstance(response["citations"], list)
    assert len(response["citations"]) == 3
    assert response["citations"][0]["url"].startswith("https://example.com/mock-research/")


def test_exa_answer_uses_smoke_cited_answer_shape() -> None:
    cache_store = FakeCacheStore()
    config = default_config()
    pricing = default_pricing()

    response_json, meta = exa_answer(
        "What is the Florida appraisal clause dispute process?",
        config=config,
        pricing=pricing,
        exa_api_key="",
        smoke_no_network=True,
        run_id="answer-run",
        cache_store=cache_store,
    )

    assert response_json["answer"].startswith("Mock answer for query:")
    assert len(response_json["citations"]) == 2
    assert meta.cache_hit is False
    assert meta.request_payload == {"query": "What is the Florida appraisal clause dispute process?", "text": True}
    assert meta.estimated_cost_usd == pricing["search_1_25"]
    assert cache_store.calls[0]["run_id"] == "answer-run"


def test_exa_research_uses_smoke_report_shape() -> None:
    cache_store = FakeCacheStore()
    config = default_config()
    pricing = default_pricing()

    response_json, meta = exa_research(
        "Summarize the Florida CAT market outlook.",
        config=config,
        pricing=pricing,
        exa_api_key="",
        smoke_no_network=True,
        run_id="research-run",
        cache_store=cache_store,
    )

    assert response_json["report"].startswith("Mock research report for query:")
    assert len(response_json["citations"]) == 3
    assert meta.cache_hit is False
    assert meta.request_payload == {"query": "Summarize the Florida CAT market outlook."}
    assert meta.estimated_cost_usd == pricing["search_1_25"]
    assert cache_store.calls[0]["run_id"] == "research-run"


def test_exa_structured_search_uses_smoke_structured_output_shape() -> None:
    cache_store = FakeCacheStore()
    config = default_config()
    pricing = default_pricing()
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "professionals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                    },
                },
            },
        },
    }

    response_json, meta = exa_structured_search(
        "What is the Florida appraisal clause dispute process?",
        config=config,
        pricing=pricing,
        exa_api_key="",
        smoke_no_network=True,
        run_id="structured-run",
        cache_store=cache_store,
        output_schema=output_schema,
        num_results=2,
    )

    assert response_json["structuredOutput"]["summary"].startswith("Mock summary for query:")
    assert response_json["structuredOutput"]["professionals"][0]["name"].startswith("Mock name for query:")
    assert meta.cache_hit is False
    assert meta.request_payload["outputSchema"] == output_schema
    assert meta.estimated_cost_usd == cache_store.calls[0]["estimated_cost"]
    assert cache_store.calls[0]["run_id"] == "structured-run"


def test_exa_find_similar_uses_smoke_similar_shape() -> None:
    cache_store = FakeCacheStore()
    config = default_config()
    pricing = default_pricing()

    response_json, meta = exa_find_similar(
        "https://example.com/article",
        config=config,
        pricing=pricing,
        exa_api_key="",
        smoke_no_network=True,
        run_id="similar-run",
        cache_store=cache_store,
        exclude_source_domain=True,
        text=True,
        highlights=True,
        context=True,
        num_results=2,
    )

    assert response_json["context"].startswith("Mock context for seed URL https://example.com/article")
    assert response_json["results"][0]["text"].startswith("Mock similar text for seed URL:")
    assert meta.cache_hit is False
    assert meta.request_payload["url"] == "https://example.com/article"
    assert meta.request_payload["excludeSourceDomain"] is True
    assert meta.request_payload["text"] is True
    assert meta.estimated_cost_usd == cache_store.calls[0]["estimated_cost"]
    assert cache_store.calls[0]["run_id"] == "similar-run"
