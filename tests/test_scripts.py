from __future__ import annotations

import importlib.util
import builtins
import sqlite3
import sys
from argparse import Namespace
from pathlib import Path

import nbformat


ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_run_notebook_smoke_live_requires_api_key(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script_module('scripts_run_notebook_smoke_test_live', 'scripts/run_notebook_smoke.py')
    fake_repo_root = tmp_path
    fake_script = fake_repo_root / 'scripts' / 'run_notebook_smoke.py'
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text('# test script placeholder\n', encoding='utf-8')
    (fake_repo_root / 'exa_people_search_eval.ipynb').write_text('{}\n', encoding='utf-8')

    monkeypatch.setattr(module, '__file__', str(fake_script))
    monkeypatch.setattr(module, 'parse_args', lambda: Namespace(mode='live', timeout=5))
    monkeypatch.delenv('EXA_API_KEY', raising=False)

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'Mode=live requested but EXA_API_KEY is missing.' in captured.err
    assert module.os.environ['EXA_SMOKE_NO_NETWORK'] == '0'


def test_run_notebook_smoke_auto_falls_back_to_smoke(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script_module('scripts_run_notebook_smoke_test_auto', 'scripts/run_notebook_smoke.py')
    fake_repo_root = tmp_path
    fake_script = fake_repo_root / 'scripts' / 'run_notebook_smoke.py'
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text('# test script placeholder\n', encoding='utf-8')
    (fake_repo_root / 'exa_people_search_eval.ipynb').write_text('{}\n', encoding='utf-8')

    runtime_dir = fake_repo_root / 'runtime'
    ipython_dir = fake_repo_root / 'ipython'
    runtime_dir.mkdir()
    ipython_dir.mkdir()

    executed = {}

    class FakeNotebookClient:
        def __init__(self, nb, timeout, kernel_name, resources, allow_errors) -> None:
            executed['nb'] = nb
            executed['timeout'] = timeout
            executed['kernel_name'] = kernel_name
            executed['resources'] = resources
            executed['allow_errors'] = allow_errors

        def execute(self) -> None:
            executed['called'] = True

    monkeypatch.setattr(module, '__file__', str(fake_script))
    monkeypatch.setattr(module, 'parse_args', lambda: Namespace(mode='auto', timeout=17))
    monkeypatch.delenv('EXA_API_KEY', raising=False)
    monkeypatch.setattr(module.tempfile, 'mkdtemp', lambda prefix: str(runtime_dir if 'jupyter' in prefix else ipython_dir))
    monkeypatch.setattr(module.nbformat, 'read', lambda _handle, as_version: nbformat.v4.new_notebook())
    monkeypatch.setattr(module, 'NotebookClient', FakeNotebookClient)

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert 'Mode=smoke: EXA_SMOKE_NO_NETWORK=1 (no network/API billing).' in captured.out
    assert 'Notebook execution completed successfully.' in captured.out
    assert module.os.environ['EXA_SMOKE_NO_NETWORK'] == '1'
    assert module.os.environ['JUPYTER_PLATFORM_DIRS'] == '1'
    assert executed['called'] is True
    assert executed['timeout'] == 17
    assert executed['kernel_name'] == 'python3'
    assert executed['allow_errors'] is False
    assert executed['resources']['metadata']['path'] == str(fake_repo_root)


def test_reset_cache_missing_file_exits_cleanly(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script_module('scripts_reset_cache_test_missing', 'scripts/reset_cache.py')
    fake_repo_root = tmp_path
    fake_script = fake_repo_root / 'scripts' / 'reset_cache.py'
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text('# test script placeholder\n', encoding='utf-8')

    monkeypatch.setattr(module, '__file__', str(fake_script))
    monkeypatch.setattr(module.argparse.ArgumentParser, 'parse_args', lambda self: Namespace(yes=True))

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert 'No cache file found' in captured.out


def test_reset_cache_cancel_keeps_valid_sqlite_file(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script_module('scripts_reset_cache_test_cancel', 'scripts/reset_cache.py')
    fake_repo_root = tmp_path
    fake_script = fake_repo_root / 'scripts' / 'reset_cache.py'
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text('# test script placeholder\n', encoding='utf-8')
    cache_path = fake_repo_root / 'exa_cache.sqlite'
    with sqlite3.connect(cache_path):
        pass

    monkeypatch.setattr(module, '__file__', str(fake_script))
    monkeypatch.setattr(module.argparse.ArgumentParser, 'parse_args', lambda self: Namespace(yes=False))
    monkeypatch.setattr(builtins, 'input', lambda _prompt: 'no')

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert 'Cancelled.' in captured.out
    assert cache_path.exists()


def test_reset_cache_rejects_non_sqlite_file(tmp_path, monkeypatch, capsys) -> None:
    module = _load_script_module('scripts_reset_cache_test_bad_sqlite', 'scripts/reset_cache.py')
    fake_repo_root = tmp_path
    fake_script = fake_repo_root / 'scripts' / 'reset_cache.py'
    fake_script.parent.mkdir(parents=True)
    fake_script.write_text('# test script placeholder\n', encoding='utf-8')
    cache_path = fake_repo_root / 'exa_cache.sqlite'
    cache_path.write_text('not a sqlite database', encoding='utf-8')

    class FakeConnection:
        def __enter__(self):
            raise sqlite3.DatabaseError('file is not a database')

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    monkeypatch.setattr(module, '__file__', str(fake_script))
    monkeypatch.setattr(module.argparse.ArgumentParser, 'parse_args', lambda self: Namespace(yes=True))
    monkeypatch.setattr(module.sqlite3, 'connect', lambda _path: FakeConnection())

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert 'did not open cleanly as sqlite' in captured.out
    assert 'Refusing to delete automatically.' in captured.out
    assert cache_path.exists()
