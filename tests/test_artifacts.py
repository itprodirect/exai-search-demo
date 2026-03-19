from __future__ import annotations

import json

import pandas as pd

from exa_demo.artifacts import ExperimentArtifactWriter
from exa_demo.models import CostBreakdown, ExaResult, QueryEvaluationRecord


def test_experiment_artifact_writer_persists_run_files(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='demo-run',
        config={'num_results': 5, 'search_type': 'auto'},
        pricing={'search_1_25': 0.005},
        run_context={'query_suite': 'insurance'},
        base_dir=tmp_path,
    )

    record = QueryEvaluationRecord(
        query='forensic engineer',
        cache_hit=False,
        request_hash='hash-1',
        request_payload={'query': 'forensic engineer'},
        request_id='req-1',
        resolved_search_type='auto',
        created_at_utc='2026-03-10T00:00:00+00:00',
        estimated_cost_usd=0.01,
        actual_cost_usd=0.01,
        top_title='Forensic Engineer',
        top_url='https://linkedin.com/in/example',
        top_preview='insurance litigation',
        linkedin_present=True,
        relevance_keywords_present=True,
        result_count=1,
        relevance_score=1.0,
        credibility_score=1.0,
        actionability_score=1.0,
        confidence_score=1.0,
        failure_reasons=[],
        primary_failure_reason=None,
        results=[ExaResult(title='Forensic Engineer', url='https://linkedin.com/in/example', highlights=['insurance litigation'])],
        cost_breakdown=CostBreakdown(total=0.01, search=0.01),
    )

    writer.record_query(record)
    summary_path = writer.write_summary(
        {'request_count': 1, 'cache_hits': 0, 'uncached_calls': 1, 'spent_usd': 0.01, 'avg_cost_per_uncached_query': 0.01},
        projections={'projection_basis': 'observed_avg_uncached', 'unit_cost_usd': 0.01},
        recommendation_data={
            'headline_recommendation': 'Integrate',
            'observed_relevance_rate': 1.0,
            'observed_linkedin_rate': 1.0,
            'observed_credibility_rate': 1.0,
            'observed_actionability_rate': 1.0,
            'observed_confidence_score': 1.0,
            'observed_failure_rate': 0.0,
            'budget_cap_usd': 7.5,
        },
        qualitative_notes=['note one'],
        extra={'taxonomy': {'failure_rate': 0.0}},
    )

    config_payload = json.loads((tmp_path / 'demo-run' / 'config.json').read_text(encoding='utf-8'))
    query_lines = (tmp_path / 'demo-run' / 'queries.jsonl').read_text(encoding='utf-8').strip().splitlines()
    result_lines = (tmp_path / 'demo-run' / 'results.jsonl').read_text(encoding='utf-8').strip().splitlines()
    summary_payload = json.loads(summary_path.read_text(encoding='utf-8'))

    assert config_payload['run_id'] == 'demo-run'
    assert len(query_lines) == 1
    assert len(result_lines) == 1
    assert json.loads(query_lines[0])['query_suite'] == 'insurance'
    assert json.loads(result_lines[0])['query_suite'] == 'insurance'
    assert summary_payload['query_records_written'] == 1
    assert summary_payload['headline_recommendation'] == 'Integrate'
    assert summary_payload['observed_confidence_score'] == 1.0
    assert summary_payload['extra']['run_context']['query_suite'] == 'insurance'
    assert summary_payload['extra']['taxonomy']['failure_rate'] == 0.0
    manifest_payload = json.loads((tmp_path / 'demo-run' / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest_payload['run_id'] == 'demo-run'
    assert {item['filename'] for item in manifest_payload['artifacts']} >= {
        'config.json',
        'queries.jsonl',
        'results.jsonl',
        'summary.json',
    }


def test_experiment_artifact_writer_writes_json_artifact(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='answer-run',
        config={'mode': 'smoke'},
        pricing={'search_1_25': 0.005},
        run_context={'workflow': 'answer'},
        base_dir=tmp_path,
    )

    path = writer.write_json_artifact(
        'answer.json',
        {
            'query': 'What is the Florida appraisal clause dispute process?',
            'answer_text': 'Mock answer text.',
            'citations': [
                {
                    'title': 'Florida appraisal clause overview',
                    'url': 'https://example.com/florida-appraisal-clause',
                    'snippet': 'Mock citation.',
                }
            ],
        },
    )

    payload = json.loads(path.read_text(encoding='utf-8'))
    assert path.name == 'answer.json'
    assert payload['query'] == 'What is the Florida appraisal clause dispute process?'
    assert payload['citations'][0]['title'] == 'Florida appraisal clause overview'


def test_experiment_artifact_writer_writes_research_artifact(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='research-run',
        config={'mode': 'smoke'},
        pricing={'search_1_25': 0.005},
        run_context={'workflow': 'research'},
        base_dir=tmp_path,
    )

    path = writer.write_json_artifact(
        'research.json',
        {
            'query': 'Summarize the Florida CAT market outlook.',
            'report_text': 'Mock research report.',
            'citations': [
                {
                    'title': 'Florida market bulletin',
                    'url': 'https://example.com/bulletin',
                    'snippet': 'Mock research citation.',
                }
            ],
        },
    )

    payload = json.loads(path.read_text(encoding='utf-8'))
    assert path.name == 'research.json'
    assert payload['query'] == 'Summarize the Florida CAT market outlook.'
    assert payload['citations'][0]['title'] == 'Florida market bulletin'


def test_experiment_artifact_writer_writes_text_and_csv_artifacts(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='exports-run',
        config={'mode': 'smoke'},
        pricing={'search_1_25': 0.005},
        base_dir=tmp_path,
    )

    markdown_path = writer.write_text_artifact('research.md', '# Research Report\n', kind='markdown')
    csv_path = writer.write_dataframe_csv(
        'results.csv',
        pd.DataFrame([{'query': 'one', 'confidence_score': 0.9}]),
        kind='results-csv',
    )

    manifest_payload = json.loads((tmp_path / 'exports-run' / 'manifest.json').read_text(encoding='utf-8'))
    assert markdown_path.name == 'research.md'
    assert csv_path.name == 'results.csv'
    assert {item['filename'] for item in manifest_payload['artifacts']} >= {'config.json', 'research.md', 'results.csv'}


def test_experiment_artifact_writer_writes_structured_output_artifact(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='structured-run',
        config={'mode': 'smoke'},
        pricing={'search_1_25': 0.005},
        run_context={'workflow': 'structured-search'},
        base_dir=tmp_path,
    )

    path = writer.write_json_artifact(
        'structured_output.json',
        {
            'query': 'independent adjuster florida catastrophe claims',
            'structured_output': {
                'schema_title': 'Structured Professionals',
                'field_names': ['name', 'role'],
            },
        },
    )

    payload = json.loads(path.read_text(encoding='utf-8'))
    assert path.name == 'structured_output.json'
    assert payload['query'] == 'independent adjuster florida catastrophe claims'
    assert payload['structured_output']['schema_title'] == 'Structured Professionals'


def test_experiment_artifact_writer_writes_find_similar_artifact(tmp_path) -> None:
    writer = ExperimentArtifactWriter(
        run_id='find-similar-run',
        config={'mode': 'smoke'},
        pricing={'search_1_25': 0.005},
        run_context={'workflow': 'find-similar'},
        base_dir=tmp_path,
    )

    path = writer.write_json_artifact(
        'find_similar.json',
        {
            'seed_url': 'https://www.merlinlawgroup.com/',
            'results': [
                {
                    'title': 'Florida Insurance Litigation Firm',
                    'url': 'https://example.com/florida-insurance-litigation-firm',
                    'snippet': 'Mock result.',
                }
            ],
        },
    )

    payload = json.loads(path.read_text(encoding='utf-8'))
    assert path.name == 'find_similar.json'
    assert payload['seed_url'] == 'https://www.merlinlawgroup.com/'
    assert payload['results'][0]['title'] == 'Florida Insurance Litigation Firm'
