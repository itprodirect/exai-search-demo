from __future__ import annotations

import json

import pandas as pd

from exa_demo.reporting import (
    build_before_after_report,
    render_research_markdown,
    render_comparison_markdown,
    summarize_failure_taxonomy,
    write_comparison_markdown,
)


def test_summarize_failure_taxonomy_supports_legacy_rows() -> None:
    df = pd.DataFrame(
        [
            {
                'query': 'q1',
                'result_count': 0,
                'relevance_keywords_present': False,
                'linkedin_present': False,
            },
            {
                'query': 'q2',
                'result_count': 1,
                'relevance_keywords_present': False,
                'linkedin_present': False,
            },
            {
                'query': 'q3',
                'result_count': 1,
                'relevance_keywords_present': True,
                'linkedin_present': True,
            },
        ]
    )

    taxonomy = summarize_failure_taxonomy(df)

    assert taxonomy['total_queries'] == 3
    assert taxonomy['queries_with_failures'] == 2
    assert taxonomy['failure_reason_counts']['no_results'] == 1
    assert taxonomy['failure_reason_counts']['off_domain'] == 1


def test_build_before_after_report_compares_baseline_with_current_batch(tmp_path) -> None:
    baseline_dir = tmp_path / 'baseline'
    baseline_dir.mkdir()

    (baseline_dir / 'summary.json').write_text(
        json.dumps(
            {
                'run_id': 'baseline',
                'spent_usd': 0.10,
                'avg_cost_per_uncached_query': 0.05,
                'observed_relevance_rate': 0.25,
                'observed_confidence_score': 0.25,
                'observed_failure_rate': 1.0,
                'extra': {'run_context': {'query_suite': 'insurance'}},
            },
            indent=2,
            sort_keys=True,
        )
        + '\n',
        encoding='utf-8',
    )

    baseline_rows = [
        {
            'query': 'q1',
            'result_count': 0,
            'relevance_keywords_present': False,
            'linkedin_present': False,
            'failure_reasons': ['no_results'],
            'confidence_score': 0.0,
            'query_suite': 'insurance',
            'resolved_search_type': 'auto',
        },
        {
            'query': 'q2',
            'result_count': 1,
            'relevance_keywords_present': False,
            'linkedin_present': False,
            'failure_reasons': ['off_domain', 'low_confidence'],
            'confidence_score': 0.2,
            'query_suite': 'insurance',
            'resolved_search_type': 'auto',
        },
    ]
    (baseline_dir / 'results.jsonl').write_text(
        '\n'.join(json.dumps(row, sort_keys=True) for row in baseline_rows) + '\n',
        encoding='utf-8',
    )

    after_df = pd.DataFrame(
        [
            {
                'query': 'q1',
                'result_count': 1,
                'relevance_keywords_present': True,
                'linkedin_present': True,
                'failure_reasons': [],
                'confidence_score': 0.95,
                'resolved_search_type': 'deep',
            },
            {
                'query': 'q2',
                'result_count': 1,
                'relevance_keywords_present': True,
                'linkedin_present': True,
                'failure_reasons': [],
                'confidence_score': 0.90,
                'resolved_search_type': 'deep',
            },
        ]
    )

    report = build_before_after_report(
        baseline_dir,
        after_run_id='candidate',
        after_summary_metrics={'spent_usd': 0.02, 'avg_cost_per_uncached_query': 0.01},
        after_batch_df=after_df,
        after_context={'query_suite': 'insurance'},
        after_recommendation={
            'observed_relevance_rate': 1.0,
            'observed_confidence_score': 0.925,
            'observed_failure_rate': 0.0,
        },
    )

    assert report['baseline_run_id'] == 'baseline'
    assert report['candidate_run_id'] == 'candidate'
    assert report['shared_query_count'] == 2
    assert report['query_outcomes']['resolved_query_count'] == 2
    assert report['deltas']['observed_failure_rate'] < 0
    assert report['comparison_context']['group_columns'] == ['query_suite']
    assert report['grouped_query_outcomes'][0]['group']['query_suite'] == 'insurance'
    assert report['grouped_query_outcomes'][0]['baseline_resolved_search_type'] == 'auto'
    assert report['grouped_query_outcomes'][0]['candidate_resolved_search_type'] == 'deep'


def test_render_and_write_comparison_markdown(tmp_path) -> None:
    report = {
        'baseline_run_id': 'baseline',
        'candidate_run_id': 'candidate',
        'shared_query_count': 2,
        'comparison_context': {
            'group_columns': ['query_suite'],
            'baseline_resolved_search_type': 'auto',
            'candidate_resolved_search_type': 'deep',
            'baseline': {'query_suite': 'insurance'},
            'candidate': {'query_suite': 'insurance'},
        },
        'deltas': {
            'spent_usd': -0.02,
            'avg_cost_per_uncached_query': -0.01,
            'observed_relevance_rate': 0.10,
            'observed_confidence_score': 0.20,
            'observed_failure_rate': -0.30,
        },
        'query_outcomes': {
            'resolved_query_count': 2,
            'regressed_query_count': 0,
            'confidence_improved_query_count': 2,
            'confidence_declined_query_count': 0,
            'avg_confidence_delta': 0.20,
            'resolved_failure_counts': {'no_results': 1},
            'introduced_failure_counts': {},
        },
        'grouped_query_outcomes': [
            {
                'group': {'query_suite': 'insurance'},
                'baseline_resolved_search_type': 'auto',
                'candidate_resolved_search_type': 'deep',
                'shared_query_count': 2,
                'resolved_query_count': 2,
                'regressed_query_count': 0,
                'avg_confidence_delta': 0.20,
                'resolved_failure_counts': {'no_results': 1},
                'introduced_failure_counts': {},
            }
        ],
    }

    markdown = render_comparison_markdown(report)
    assert '# Before/After Comparison Report' in markdown
    assert 'Baseline run: `baseline`' in markdown
    assert '| Observed Failure Rate | -30.0% |' in markdown
    assert '## Grouped Query Outcomes' in markdown
    assert '| Group | Baseline Search Type | Candidate Search Type |' in markdown

    written = write_comparison_markdown(tmp_path, report)
    assert written.name == 'comparison.md'
    assert written.exists()
    assert '## Query Outcomes' in written.read_text(encoding='utf-8')


def test_render_research_markdown_includes_report_and_citations() -> None:
    markdown = render_research_markdown(
        query='Summarize the Florida CAT market outlook.',
        report_text='Mock research report body.',
        citations=[
            {
                'title': 'Florida market bulletin',
                'url': 'https://example.com/bulletin',
                'snippet': 'Bulletin summary',
            }
        ],
    )

    assert '# Research Report' in markdown
    assert 'Summarize the Florida CAT market outlook.' in markdown
    assert 'Mock research report body.' in markdown
    assert '[Florida market bulletin](https://example.com/bulletin)' in markdown

