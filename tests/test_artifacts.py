from __future__ import annotations

import json

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
