from __future__ import annotations

from pathlib import Path

from exa_demo.client_payloads import build_exa_payload, build_find_similar_payload
from exa_demo.config import default_config
from exa_demo.workflows import (
    build_answer_artifact,
    build_find_similar_artifact,
    build_research_artifact,
    build_structured_search_artifact,
)


def test_build_exa_payload_trims_additional_queries_and_dates() -> None:
    config = default_config()
    config.update(
        {
            'additional_queries': [' licensed public adjuster Florida ', '', '  '],
            'start_published_date': ' 2026-01-01 ',
            'end_published_date': ' ',
        }
    )

    payload = build_exa_payload('insurance expert witness', config)

    assert payload['additionalQueries'] == ['licensed public adjuster Florida']
    assert payload['startPublishedDate'] == '2026-01-01'
    assert 'endPublishedDate' not in payload


def test_build_find_similar_payload_trims_optional_date_filters() -> None:
    payload = build_find_similar_payload(
        'https://example.com/article',
        default_config(),
        start_crawl_date=' 2026-01-01 ',
        end_crawl_date='',
        start_published_date=' 2026-01-15 ',
        end_published_date='   ',
    )

    assert payload['startCrawlDate'] == '2026-01-01'
    assert payload['startPublishedDate'] == '2026-01-15'
    assert 'endCrawlDate' not in payload
    assert 'endPublishedDate' not in payload


def test_build_answer_artifact_normalizes_base_fields() -> None:
    payload = build_answer_artifact(
        'What is the Florida appraisal clause dispute process?',
        request_payload={'query': 'What is the Florida appraisal clause dispute process?'},
        response_json={'requestId': ' req-answer ', 'answer': 'Mock answer', 'costDollars': {'total': '0.01'}},
        cache_hit=True,
        estimated_cost_usd=0.02,
    )

    assert payload['request_id'] == 'req-answer'
    assert payload['cache_hit'] is True
    assert payload['estimated_cost_usd'] == 0.02
    assert payload['actual_cost_usd'] == 0.01
    assert payload['answer_text'] == 'Mock answer'


def test_build_research_artifact_prefers_sources_when_citations_missing() -> None:
    payload = build_research_artifact(
        'Summarize the Florida CAT market outlook.',
        request_payload={'query': 'Summarize the Florida CAT market outlook.'},
        response_json={
            'requestId': 'req-research',
            'report': 'Mock report',
            'sources': [
                {
                    'name': 'Florida Market Bulletin',
                    'sourceUrl': 'https://example.com/bulletin',
                    'text': 'Market bulletin summary',
                }
            ],
            'costDollars': {'total': 0.0},
        },
        cache_hit=False,
        estimated_cost_usd=0.01,
    )

    assert payload['request_id'] == 'req-research'
    assert payload['citation_count'] == 1
    assert payload['citations'][0]['title'] == 'Florida Market Bulletin'
    assert payload['report_preview'] == 'Mock report'


def test_build_find_similar_artifact_sets_top_result_and_score() -> None:
    payload = build_find_similar_artifact(
        'https://example.com/article',
        request_payload={'url': 'https://example.com/article'},
        response_json={
            'requestId': 'req-find-similar',
            'results': [
                {
                    'title': 'Florida Insurance Litigation Firm',
                    'url': 'https://example.com/firm',
                    'snippet': 'Mock result',
                    'score': '0.98',
                }
            ],
            'costDollars': {'total': 0.0},
        },
        cache_hit=False,
        estimated_cost_usd=0.01,
    )

    assert payload['request_id'] == 'req-find-similar'
    assert payload['result_count'] == 1
    assert payload['top_result']['title'] == 'Florida Insurance Litigation Firm'
    assert payload['results'][0]['score'] == 0.98


def test_build_structured_search_artifact_sorts_structured_keys(tmp_path: Path) -> None:
    schema_file = tmp_path / 'schema.json'
    schema_file.write_text('{"type":"object"}\n', encoding='utf-8')

    payload = build_structured_search_artifact(
        'insurance expert witness',
        schema_path=schema_file,
        request_payload={'query': 'insurance expert witness'},
        response_json={
            'requestId': 'req-structured',
            'structuredOutput': {
                'records': [{'name': 'Jane Doe'}],
                'schema_title': 'Structured Professionals',
                'field_names': ['name'],
            },
            'costDollars': {'total': 0.0},
        },
        cache_hit=False,
        estimated_cost_usd=0.01,
    )

    assert payload['request_id'] == 'req-structured'
    assert payload['schema_file'] == str(schema_file)
    assert payload['structured_output_keys'] == ['field_names', 'records', 'schema_title']
