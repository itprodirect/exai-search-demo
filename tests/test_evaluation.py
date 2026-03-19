from __future__ import annotations

from dataclasses import dataclass

import json

from exa_demo.evaluation import (
    DEFAULT_RELEVANCE_KEYWORDS,
    evaluate_batch_queries,
    load_benchmark_queries,
    load_benchmark_suite_definitions,
    load_benchmark_suites,
)
from exa_demo.models import QueryEvaluationRecord


@dataclass
class FakeMeta:
    cache_hit: bool
    estimated_cost_usd: float
    actual_cost_usd: float | None
    request_hash: str = 'hash-123'
    request_payload: dict | None = None
    request_id: str | None = 'req-123'
    resolved_search_type: str | None = 'auto'
    created_at_utc: str = '2026-03-10T00:00:00+00:00'


def test_load_benchmark_queries_matches_current_fixture() -> None:
    queries = load_benchmark_queries()

    assert len(queries) == 49
    assert queries[0].startswith("public adjuster licensing requirements Florida")
    assert queries[-1].startswith("property insurance vendor performance scorecard")


def test_load_benchmark_queries_can_target_named_suite() -> None:
    all_queries = load_benchmark_queries(suite="all")
    public_adjuster_queries = load_benchmark_queries(suite="public_adjusters")
    forensic_queries = load_benchmark_queries(suite="forensic_and_damage_engineering")
    coverage_queries = load_benchmark_queries(suite="cat_law_and_coverage")
    legacy_coverage_queries = load_benchmark_queries(suite="coverage_and_litigation")
    appraiser_queries = load_benchmark_queries(suite="appraisers_umpires_and_restoration")
    legacy_adjuster_queries = load_benchmark_queries(suite="adjusters_appraisers_and_restoration")
    adjuster_queries = load_benchmark_queries(suite="independent_adjusters")
    adjacent_queries = load_benchmark_queries(suite="adjacent_industries")
    restoration_queries = load_benchmark_queries(suite="restoration_and_mitigation")
    vendor_queries = load_benchmark_queries(suite="carrier_tpa_and_vendor_ecosystem")
    market_queries = load_benchmark_queries(suite="regulatory_legislative_and_market_news")
    suite_definitions = load_benchmark_suite_definitions()
    suites = load_benchmark_suites()

    assert len(all_queries) == 49
    assert len(public_adjuster_queries) == 5
    assert len(forensic_queries) == 5
    assert len(coverage_queries) == 8
    assert len(legacy_coverage_queries) == 4
    assert len(appraiser_queries) == 7
    assert len(legacy_adjuster_queries) == 6
    assert len(adjuster_queries) == 4
    assert len(adjacent_queries) == 9
    assert len(restoration_queries) == 5
    assert len(vendor_queries) == 5
    assert len(market_queries) == 6
    assert suites["public_adjusters"][0].startswith("public adjuster licensing requirements")
    assert suites["forensic_and_damage_engineering"][0].startswith("forensic engineer wind damage")
    assert suites["cat_law_and_coverage"][0].startswith("policyholder attorney")
    assert suites["coverage_and_litigation"][0].startswith("policyholder attorney")
    assert suites["appraisers_umpires_and_restoration"][0].startswith("insurance appraisal umpire")
    assert suites["adjusters_appraisers_and_restoration"][0].startswith("insurance appraisal umpire")
    assert suites["independent_adjusters"][0].startswith("licensed independent adjuster")
    assert suites["adjacent_industries"][-1].startswith("civil engineer structural")
    assert suites["restoration_and_mitigation"][0].startswith("hurricane board-up contractor")
    assert suites["carrier_tpa_and_vendor_ecosystem"][1].startswith("AI property damage assessment")
    assert suites["regulatory_legislative_and_market_news"][0].startswith("Florida insurance legislative session")
    assert suite_definitions["restoration_and_mitigation"]["description"] == "Field-service vendors and mitigation specialists involved in post-loss response."
    assert suite_definitions["carrier_tpa_and_vendor_ecosystem"]["metadata"]["focus"] == "firm discovery"
    assert suite_definitions["regulatory_legislative_and_market_news"]["queries"][0]["category"] == "news"


def test_load_benchmark_queries_supports_legacy_list_fixtures(tmp_path) -> None:
    legacy_path = tmp_path / "legacy_queries.json"
    legacy_queries = ["one query", "two query"]
    legacy_path.write_text(json.dumps(legacy_queries), encoding="utf-8")

    assert load_benchmark_suites(legacy_path) == {"default": legacy_queries}
    assert load_benchmark_queries(legacy_path) == legacy_queries
    assert load_benchmark_suite_definitions(legacy_path)["default"]["queries"] == [
        {"text": "one query"},
        {"text": "two query"},
    ]


def test_load_benchmark_queries_supports_rich_suite_definitions(tmp_path) -> None:
    rich_path = tmp_path / "rich_queries.json"
    rich_path.write_text(
        json.dumps(
            {
                "default_suite": "all",
                "suites": {
                    "all": {
                        "description": "Rich mixed-format suite",
                        "audience": "research",
                        "queries": [
                            {
                                "text": "alpha query",
                                "topic": "people",
                                "intent": "discover",
                                "category": "people",
                            },
                            "beta query",
                        ],
                    },
                    "market_watch": {
                        "description": "Market watch suite",
                        "focus": "news",
                        "queries": [
                            {
                                "query": "gamma query",
                                "topic": "news",
                                "intent": "monitor",
                                "category": "news",
                            }
                        ],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    suite_definitions = load_benchmark_suite_definitions(rich_path)

    assert suite_definitions["all"]["description"] == "Rich mixed-format suite"
    assert suite_definitions["all"]["metadata"]["audience"] == "research"
    assert suite_definitions["all"]["queries"][0]["text"] == "alpha query"
    assert suite_definitions["all"]["queries"][0]["topic"] == "people"
    assert suite_definitions["all"]["queries"][1]["text"] == "beta query"
    assert suite_definitions["market_watch"]["metadata"]["focus"] == "news"
    assert suite_definitions["market_watch"]["queries"][0]["text"] == "gamma query"
    assert suite_definitions["market_watch"]["queries"][0]["category"] == "news"
    assert load_benchmark_suites(rich_path) == {
        "all": ["alpha query", "beta query"],
        "market_watch": ["gamma query"],
    }
    assert load_benchmark_queries(rich_path) == ["alpha query", "beta query"]
    assert load_benchmark_queries(rich_path, suite="market_watch") == ["gamma query"]


def test_evaluate_batch_queries_builds_expected_flags() -> None:
    def fake_search_people(query: str, *, num_results: int):
        return (
            {
                "results": [
                    {
                        "title": f"{query} insurance expert witness",
                        "url": "https://www.linkedin.com/in/test-person",
                        "highlights": ["forensic insurance litigation profile"],
                    }
                ]
            },
            FakeMeta(cache_hit=False, estimated_cost_usd=0.01, actual_cost_usd=0.02, request_payload={"query": query}),
        )

    df = evaluate_batch_queries(
        ["query one"],
        search_people=fake_search_people,
        num_results=5,
        relevance_keywords=DEFAULT_RELEVANCE_KEYWORDS,
        redact_text=lambda value: value,
        extract_preview=lambda row, max_chars: " | ".join(row.get("highlights", []))[:max_chars],
    )

    row = df.iloc[0].to_dict()
    assert row["linkedin_present"] is True
    assert row["relevance_keywords_present"] is True
    assert row["top_url"] == "https://www.linkedin.com/in/test-person"
    assert row["top_preview"] == "forensic insurance litigation profile"
    assert row["request_hash"] == 'hash-123'
    assert row["relevance_score"] == 1.0
    assert row["credibility_score"] == 1.0
    assert row["actionability_score"] >= 0.0
    assert row["confidence_score"] >= 0.5
    assert row["failure_reasons"] == []


def test_evaluate_batch_queries_marks_no_results_failure() -> None:
    def fake_search_people(query: str, *, num_results: int):
        return (
            {"results": []},
            FakeMeta(cache_hit=False, estimated_cost_usd=0.01, actual_cost_usd=0.0, request_payload={"query": query}),
        )

    df = evaluate_batch_queries(
        ["query one"],
        search_people=fake_search_people,
        num_results=5,
        relevance_keywords=DEFAULT_RELEVANCE_KEYWORDS,
        redact_text=lambda value: value,
        extract_preview=lambda row, max_chars: "",
    )

    row = df.iloc[0].to_dict()
    assert row["result_count"] == 0
    assert row["failure_reasons"] == ["no_results"]
    assert row["primary_failure_reason"] == "no_results"


def test_evaluate_batch_queries_can_emit_structured_records() -> None:
    emitted: list[QueryEvaluationRecord] = []

    def fake_search_people(query: str, *, num_results: int):
        return (
            {
                "results": [
                    {
                        "title": f"{query} insurance expert witness",
                        "url": "https://www.linkedin.com/in/test-person",
                        "highlights": ["forensic insurance litigation profile"],
                    }
                ],
                "costDollars": {"search": 0.005, "contents": 0.001, "total": 0.006},
            },
            FakeMeta(cache_hit=True, estimated_cost_usd=0.01, actual_cost_usd=0.0, request_payload={"query": query}),
        )

    evaluate_batch_queries(
        ["query one"],
        search_people=fake_search_people,
        num_results=5,
        relevance_keywords=DEFAULT_RELEVANCE_KEYWORDS,
        redact_text=lambda value: value,
        extract_preview=lambda row, max_chars: " | ".join(row.get("highlights", []))[:max_chars],
        record_query=emitted.append,
    )

    assert len(emitted) == 1
    assert emitted[0].query == 'query one'
    assert emitted[0].cache_hit is True
    assert emitted[0].results[0].url == 'https://www.linkedin.com/in/test-person'
    assert emitted[0].cost_breakdown.total == 0.006
    assert emitted[0].failure_reasons == []
    assert emitted[0].primary_failure_reason is None
