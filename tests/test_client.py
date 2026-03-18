from __future__ import annotations

from exa_demo.client import build_exa_payload, mock_exa_response
from exa_demo.config import default_config
from exa_demo.client import build_answer_payload, exa_answer, mock_exa_answer_response
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
