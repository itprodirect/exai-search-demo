from __future__ import annotations

from exa_demo.models import (
    AnswerCitation,
    AnswerRecord,
    CostBreakdown,
    ExaResult,
    FindSimilarRecord,
    QueryEvaluationRecord,
    ResearchRecord,
    StructuredOutputField,
    StructuredOutputRecord,
)


class Meta:
    cache_hit = False
    request_hash = 'hash-abc'
    request_payload = {'query': 'forensic engineer'}
    request_id = 'req-abc'
    resolved_search_type = 'deep'
    created_at_utc = '2026-03-10T00:00:00+00:00'
    estimated_cost_usd = 0.012
    actual_cost_usd = 0.01


def test_exa_result_normalizes_api_fields() -> None:
    result = ExaResult.from_api_result(
        {
            'title': 'Example Title',
            'url': 'https://example.com/profile',
            'publishedDate': '2026-03-01',
            'author': 'Analyst',
            'highlights': ['one', 'two'],
            'highlightScores': ['0.5', 0.75],
            'summary': 'Summary',
            'text': 'Body',
        }
    )

    assert result.title == 'Example Title'
    assert result.highlight_scores == [0.5, 0.75]
    assert result.to_dict()['published_date'] == '2026-03-01'


def test_cost_breakdown_handles_known_and_unknown_keys() -> None:
    breakdown = CostBreakdown.from_response(
        {
            'costDollars': {
                'search': 0.005,
                'contents': 0.002,
                'deepSearch': 0.01,
                'rerank': 0.003,
                'total': 0.02,
            }
        }
    )

    assert breakdown.search == 0.005
    assert breakdown.content_highlights == 0.002
    assert breakdown.deep_search == 0.01
    assert breakdown.other_costs == {'rerank': 0.003}
    assert breakdown.total == 0.02


def test_query_evaluation_record_builds_flat_row() -> None:
    record = QueryEvaluationRecord.from_runtime(
        'forensic engineer',
        {
            'results': [
                {
                    'title': 'Forensic Engineer',
                    'url': 'https://linkedin.com/in/example',
                    'highlights': ['insurance litigation'],
                }
            ],
            'costDollars': {'search': 0.005, 'total': 0.005},
        },
        Meta(),
        {
            'top_title': 'Forensic Engineer',
            'top_url': 'https://linkedin.com/in/example',
            'top_preview': 'insurance litigation',
            'linkedin_present': True,
            'relevance_keywords_present': True,
            'relevance_score': 1.0,
            'credibility_score': 1.0,
            'actionability_score': 1.0,
            'confidence_score': 1.0,
            'failure_reasons': [],
            'primary_failure_reason': None,
            'result_count': 1,
        },
    )

    flat = record.to_flat_dict()
    assert flat['query'] == 'forensic engineer'
    assert flat['request_id'] == 'req-abc'
    assert flat['result_count'] == 1
    assert flat['confidence_score'] == 1.0
    assert flat['failure_reasons'] == []
    assert record.results[0].title == 'Forensic Engineer'


def test_answer_citation_normalizes_source_fields() -> None:
    citation = AnswerCitation.from_api_citation(
        {
            'name': 'Florida Appraisal Statute',
            'sourceUrl': 'https://example.com/statute',
            'text': 'Appraisal clause dispute process',
            'published_date': '2026-03-01',
            'author': 'Analyst',
        }
    )

    assert citation.title == 'Florida Appraisal Statute'
    assert citation.url == 'https://example.com/statute'
    assert citation.snippet == 'Appraisal clause dispute process'
    assert citation.published_date == '2026-03-01'


def test_answer_record_builds_flat_row() -> None:
    class AnswerMeta:
        cache_hit = True
        request_hash = 'hash-answer'
        request_payload = {'query': 'What is the Florida appraisal clause dispute process?'}
        request_id = 'answer-abc'
        created_at_utc = '2026-03-18T00:00:00+00:00'
        estimated_cost_usd = 0.005
        actual_cost_usd = 0.0

    record = AnswerRecord.from_runtime(
        'What is the Florida appraisal clause dispute process?',
        {
            'answer': 'Mock answer for query: What is the Florida appraisal clause dispute process?',
            'citations': [
                {
                    'title': 'Florida Appraisal Statute',
                    'url': 'https://example.com/statute',
                    'snippet': 'Appraisal clause dispute process',
                }
            ],
        },
        AnswerMeta(),
    )

    flat = record.to_flat_dict()
    assert flat['question'] == 'What is the Florida appraisal clause dispute process?'
    assert flat['request_id'] == 'answer-abc'
    assert flat['citation_count'] == 1
    assert flat['top_citation_url'] == 'https://example.com/statute'
    assert record.answer.startswith('Mock answer for query:')
    assert record.citations[0].title == 'Florida Appraisal Statute'


def test_research_record_builds_flat_row() -> None:
    class ResearchMeta:
        cache_hit = False
        request_hash = 'hash-research'
        request_payload = {'query': 'Summarize the Florida CAT market outlook.'}
        request_id = 'research-abc'
        created_at_utc = '2026-03-19T00:00:00+00:00'
        estimated_cost_usd = 0.005
        actual_cost_usd = 0.0

    record = ResearchRecord.from_runtime(
        'Summarize the Florida CAT market outlook.',
        {
            'report': 'Mock research report for query: Summarize the Florida CAT market outlook.',
            'sources': [
                {
                    'name': 'Florida Market Bulletin',
                    'sourceUrl': 'https://example.com/bulletin',
                    'text': 'Market bulletin summary',
                }
            ],
        },
        ResearchMeta(),
    )

    flat = record.to_flat_dict()
    assert flat['query'] == 'Summarize the Florida CAT market outlook.'
    assert flat['request_id'] == 'research-abc'
    assert flat['citation_count'] == 1
    assert flat['top_citation_url'] == 'https://example.com/bulletin'
    assert record.report_text.startswith('Mock research report for query:')
    assert record.citations[0].title == 'Florida Market Bulletin'


def test_find_similar_record_builds_flat_row() -> None:
    class SimilarMeta:
        cache_hit = True
        request_hash = 'hash-similar'
        request_payload = {'url': 'https://example.com/article', 'text': True}
        request_id = 'similar-abc'
        resolved_search_type = None
        created_at_utc = '2026-03-18T00:00:00+00:00'
        estimated_cost_usd = 0.012
        actual_cost_usd = 0.0

    record = FindSimilarRecord.from_runtime(
        'https://example.com/article',
        {
            'context': 'Mock context for seed URL https://example.com/article. Similar results are generated from example.com.',
            'results': [
                {
                    'title': 'Jane Doe',
                    'url': 'https://example.com/profile',
                    'text': 'Relevant background',
                }
            ],
            'costDollars': {'search': 0.005, 'total': 0.005},
        },
        SimilarMeta(),
    )

    flat = record.to_flat_dict()
    assert flat['source_url'] == 'https://example.com/article'
    assert flat['request_id'] == 'similar-abc'
    assert flat['result_count'] == 1
    assert flat['context_preview'].startswith('Mock context for seed URL')
    assert record.top_title == 'Jane Doe'
    assert record.results[0].text == 'Relevant background'


def test_structured_output_field_normalizes_leaf_values() -> None:
    field = StructuredOutputField.from_value('structuredOutput.professionals[0].name', 'Jane Doe')

    assert field.path == 'structuredOutput.professionals[0].name'
    assert field.value == 'Jane Doe'
    assert field.value_type == 'str'


def test_structured_output_record_builds_flat_row() -> None:
    class StructuredMeta:
        cache_hit = False
        request_hash = 'hash-structured'
        request_payload = {'query': 'insurance expert witness', 'outputSchema': {'type': 'object'}}
        request_id = 'structured-abc'
        resolved_search_type = 'deep'
        created_at_utc = '2026-03-18T00:00:00+00:00'
        estimated_cost_usd = 0.012
        actual_cost_usd = 0.0

    record = StructuredOutputRecord.from_runtime(
        'insurance expert witness',
        {
            'structuredOutput': {
                'summary': 'Mock summary',
                'professionals': [
                    {
                        'name': 'Jane Doe',
                        'role': 'Public Adjuster',
                    }
                ],
            },
            'results': [
                {
                    'title': 'Jane Doe',
                    'url': 'https://example.com/profile',
                }
            ],
            'costDollars': {'search': 0.005, 'total': 0.005},
        },
        StructuredMeta(),
    )

    flat = record.to_flat_dict()
    assert flat['query'] == 'insurance expert witness'
    assert flat['request_id'] == 'structured-abc'
    assert flat['result_count'] == 1
    assert flat['field_count'] == 3
    assert flat['top_field_path'] == 'structuredOutput.summary'
    assert flat['top_field_value'] == 'Mock summary'
    assert record.fields[1].path == 'structuredOutput.professionals[0].name'
    assert record.top_title == 'Jane Doe'
    assert record.results[0].url == 'https://example.com/profile'
