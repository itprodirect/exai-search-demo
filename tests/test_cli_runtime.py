from __future__ import annotations

from argparse import Namespace

from exa_demo import cli as cli_module
from exa_demo import cli_eval as cli_eval_module
from exa_demo import cli_runtime as cli_runtime_module
from exa_demo.config import RuntimeState


def test_resolve_runtime_auto_without_api_key_uses_smoke(monkeypatch) -> None:
    monkeypatch.delenv('EXA_API_KEY', raising=False)
    monkeypatch.delenv('EXA_SMOKE_NO_NETWORK', raising=False)
    monkeypatch.delenv('EXA_RUN_ID', raising=False)

    runtime = cli_runtime_module.resolve_runtime('auto', 'runtime-smoke')

    assert runtime.smoke_no_network is True
    assert runtime.run_id == 'runtime-smoke'
    assert runtime.exa_api_key == ''


def test_resolve_runtime_auto_with_api_key_uses_live(monkeypatch) -> None:
    monkeypatch.setenv('EXA_API_KEY', 'test-key')
    monkeypatch.delenv('EXA_SMOKE_NO_NETWORK', raising=False)
    monkeypatch.delenv('EXA_RUN_ID', raising=False)

    runtime = cli_runtime_module.resolve_runtime('auto', 'runtime-live')

    assert runtime.smoke_no_network is False
    assert runtime.run_id == 'runtime-live'
    assert runtime.exa_api_key == 'test-key'


def test_runtime_metadata_reports_execution_state() -> None:
    runtime = RuntimeState(exa_api_key='test-key', smoke_no_network=False, run_id='demo-run')

    payload = cli_runtime_module.runtime_metadata(runtime)

    assert payload == {
        'execution_mode': 'live',
        'smoke_no_network': False,
        'network_access': True,
        'api_key_configured': True,
    }


def test_run_eval_workflow_forwards_runtime_and_compare_overrides() -> None:
    captured: dict[str, object] = {}
    args = Namespace(
        artifact_dir='artifacts',
        run_id='base-run',
        search_type='auto',
        suite='all',
        queries_file=None,
        limit=2,
        compare_to_run_id='baseline-run',
        compare_base_dir='artifacts',
    )
    runtime = RuntimeState(exa_api_key='', smoke_no_network=True, run_id='override-run')

    def fake_namespace_with_overrides(namespace, **overrides):
        captured['namespace_overrides'] = overrides
        values = dict(vars(namespace))
        values.update(overrides)
        return Namespace(**values)

    def fake_prepare_runtime(namespace):
        captured['prepared_run_id'] = namespace.run_id
        captured['prepared_search_type'] = namespace.search_type
        return ({'config': True}, {'pricing': True}, runtime)

    def fake_runtime_metadata(resolved_runtime):
        captured['runtime_metadata_runtime'] = resolved_runtime
        return {'execution_mode': 'smoke'}

    def fake_workflow_impl(**kwargs):
        captured['workflow_kwargs'] = kwargs
        return {'run_id': resolved_runtime_id(kwargs['runtime'])}

    payload = cli_eval_module.run_eval_workflow(
        args,
        prepare_runtime=fake_prepare_runtime,
        runtime_metadata=fake_runtime_metadata,
        namespace_with_overrides=fake_namespace_with_overrides,
        run_eval_workflow_impl=fake_workflow_impl,
        run_id_override='override-run',
        search_type_override='deep',
        compare_to_run_id='override-baseline',
        compare_base_dir='override-artifacts',
    )

    assert captured['namespace_overrides'] == {'run_id': 'override-run', 'search_type': 'deep'}
    assert captured['prepared_run_id'] == 'override-run'
    assert captured['prepared_search_type'] == 'deep'
    assert captured['runtime_metadata_runtime'] is runtime
    assert captured['workflow_kwargs']['artifact_dir'] == 'artifacts'
    assert captured['workflow_kwargs']['runtime_metadata'] == {'execution_mode': 'smoke'}
    assert captured['workflow_kwargs']['compare_to_run_id'] == 'override-baseline'
    assert captured['workflow_kwargs']['compare_base_dir'] == 'override-artifacts'
    assert payload == {'run_id': 'override-run'}


def test_run_compare_search_types_workflow_builds_related_run_ids() -> None:
    captured: dict[str, object] = {}
    args = Namespace(
        mode='smoke',
        run_id='compare-base',
        suite='insurance',
        artifact_dir='artifacts',
        baseline_type='deep',
        candidate_type='deep-reasoning',
    )
    runtime = RuntimeState(exa_api_key='', smoke_no_network=True, run_id='compare-base')

    def fake_load_env():
        captured['loaded_env'] = True

    def fake_resolve_runtime(mode, run_id):
        captured['resolve_runtime'] = (mode, run_id)
        return runtime

    def fake_suffix(search_type):
        return search_type.replace('-', '_')

    def fake_normalized_query_suite(suite):
        return f'normalized:{suite}'

    def fake_eval_runner(namespace, **overrides):
        captured.setdefault('eval_calls', []).append(overrides)
        run_id = overrides['run_id_override']
        payload = {'run_id': run_id, 'artifact_dir': f'artifacts/{run_id}'}
        if run_id.endswith('deep_reasoning'):
            payload['comparison'] = {'candidate_run_id': run_id}
            payload['comparison_markdown_path'] = f'artifacts/{run_id}/comparison.md'
        return payload

    payload = cli_eval_module.run_compare_search_types_workflow(
        args,
        load_env=fake_load_env,
        resolve_runtime=fake_resolve_runtime,
        run_id_suffix_for_search_type=fake_suffix,
        normalized_query_suite=fake_normalized_query_suite,
        eval_workflow_runner=fake_eval_runner,
    )

    assert captured['loaded_env'] is True
    assert captured['resolve_runtime'] == ('smoke', 'compare-base')
    assert captured['eval_calls'] == [
        {'run_id_override': 'compare-base-deep', 'search_type_override': 'deep'},
        {
            'run_id_override': 'compare-base-deep_reasoning',
            'search_type_override': 'deep-reasoning',
            'compare_to_run_id': 'compare-base-deep',
            'compare_base_dir': 'artifacts',
        },
    ]
    assert payload['query_suite'] == 'normalized:insurance'
    assert payload['baseline_run']['run_id'] == 'compare-base-deep'
    assert payload['candidate_run']['run_id'] == 'compare-base-deep_reasoning'
    assert payload['comparison_markdown_path'] == 'artifacts/compare-base-deep_reasoning/comparison.md'


def test_run_runtime_payload_command_uses_prepared_runtime_context(monkeypatch, capsys) -> None:
    args = Namespace(as_json=True, artifact_dir='artifacts')
    runtime = RuntimeState(exa_api_key='', smoke_no_network=True, run_id='runtime-command')
    captured: dict[str, object] = {}

    def fake_prepare_runtime(_args):
        captured['prepared'] = True
        return ({'config': True}, {'pricing': True}, runtime)

    def fake_runtime_metadata(resolved_runtime):
        captured['runtime_metadata_runtime'] = resolved_runtime
        return {'execution_mode': 'smoke'}

    def fake_workflow_runner(**kwargs):
        captured['workflow_kwargs'] = kwargs
        return {'workflow': 'demo'}

    def fake_emitter(payload, *, as_json):
        captured['emitter'] = (payload, as_json)

    monkeypatch.setattr(cli_module, '_prepare_runtime', fake_prepare_runtime)
    monkeypatch.setattr(cli_module, '_runtime_metadata', fake_runtime_metadata)

    exit_code = cli_module._run_runtime_payload_command(
        args,
        workflow_runner=fake_workflow_runner,
        payload_emitter=fake_emitter,
        query='demo query',
    )

    assert exit_code == 0
    assert captured['prepared'] is True
    assert captured['runtime_metadata_runtime'] is runtime
    assert captured['workflow_kwargs'] == {
        'artifact_dir': 'artifacts',
        'config': {'config': True},
        'pricing': {'pricing': True},
        'runtime': runtime,
        'runtime_metadata': {'execution_mode': 'smoke'},
        'query': 'demo query',
    }
    assert captured['emitter'] == ({'workflow': 'demo'}, True)


def resolved_runtime_id(runtime: RuntimeState) -> str:
    return runtime.run_id
