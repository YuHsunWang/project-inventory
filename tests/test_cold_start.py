"""Cold-start issue regressions; stdlib Python and the existing Node renderer."""
from contextlib import redirect_stdout
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

from test_support import case, summary

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / 'skills/project-inventory/scripts'
sys.path.insert(0, str(S))
import build, collect
from validation import validate_inventory


def inventory(local):
    return {'lang': 'zh-TW', 'projects': [{'key': 'p', 'name': 'P', 'color': '#c00',
                                        'sources': {'local': local}}]}


def snapshot(home, inv, error=None):
    (home / 'inventory.json').write_text(json.dumps(inv))
    calls = []
    def git(cmd, **kwargs):
        calls.append(cmd)
        args = cmd[1:]
        if error and str(kwargs.get("cwd")) != "/healthy":
            raise RuntimeError(error)
        if args == ['remote']: return 'origin\n'
        if args[:2] == ['remote', 'get-url']: return 'https://example.com/repo.git\n'
        if args[0] == 'fetch': return ''
        if args[0] == 'branch': return 'main\n'
        if args[0] == 'rev-parse': return 'origin/main\n' if '@{upstream}' in args else 'a' * 40 + '\n'
        if args[:2] == ['rev-list', '--left-right']: return '0 0\n'
        if args[0] == 'rev-list': return 'a' * 40 + '\n'
        if args[0] == 'status': return '?? local.txt\n'
        if args[:2] == ['log', '-1']: return f'{dt.date.today()} local work\n'
        if args[0] == 'log':
            rows = [f'{"a" * 40}\t{dt.date.today()}\tlocal work']
            if '--all' in args: rows.append(f'{"b" * 40}\t{dt.date.today()}\tother branch')
            return '\n'.join(rows)
        raise AssertionError(cmd)
    with patch.object(collect, 'run', side_effect=git), redirect_stdout(io.StringIO()):
        code, path, _ = collect.collect_snapshot(home)
    return code, json.loads(path.read_text())['projects']['p'], calls


def rendered(home):
    with redirect_stdout(io.StringIO()): build.build_page(home)
    result = subprocess.run(['node', str(ROOT / 'tests/html_collection.js')],
                            input=(home / 'out/index.html').read_text(), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)[0]


@case
def test_issue34_fetch_opt_out():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        spec = {'label': 'checkout', 'path': '/fixture'}
        code, f, calls = snapshot(home, inventory([spec]))
        assert code == 0 and any(c[1] == 'fetch' for c in calls), 'default must still fetch'
        last_fetch = f['repos'][0]['last_fetched_at']
        code, f, calls = snapshot(home, inventory([{**spec, 'fetch': False}]))
        assert not any(c[1] == 'fetch' for c in calls), 'fetch:false must never run git fetch'
        r = f['repos'][0]
        assert code == 0 and not f['errors'] and f['sources']['git:/fixture']['status'] == 'ok'
        assert r['ahead'] is None and r['behind'] is None
        assert r['head'] == 'a' * 40 and r['branch'] == 'main' and r['dirty'] == 1 and f['commits']
        assert r['fetch_performed'] is False and r['last_fetched_at'] == last_fetch
        html = rendered(home)['facts']
        assert '遠端比較未知' in html and '這條分支還沒推上去' not in html
        for value in (0, 'false', None):
            try: validate_inventory(inventory([{**spec, 'fetch': value}]))
            except ValueError as e: assert '.fetch' in str(e)
            else: raise AssertionError(f'invalid fetch accepted: {value!r}')
        # Reading a new, empty checkout must still succeed without a HEAD commit.
        empty = home / 'empty'
        subprocess.run(['git', 'init', '-q', str(empty)], check=True, capture_output=True)
        for scope in ('all', 'head'):
            state = collect.git_state(empty, dt.date.today(), fetch=False, history=scope)
            assert state['head'] is None and state['last_commit'] is None and not state['_commits']
            assert state['fetch_performed'] is False
        # The scheduler's change check must not contact the remote either (PR #38 review).
        import auto_refresh
        for opt, expect in ((None, True), (False, False)):
            remote_calls = []
            def run(cmd, **kwargs):
                remote_calls.append(cmd)
                return 'origin\n' if cmd[1] == 'remote' else ''
            local = {**spec} if opt is None else {**spec, 'fetch': opt}
            with patch.object(auto_refresh, 'local_git', lambda path: {}), patch.object(collect, 'run', run):
                _, failed = auto_refresh.fingerprints(home, inventory([local]))
            assert not failed and any(c[1] == 'ls-remote' for c in remote_calls) == expect, (opt, remote_calls)


@case
def test_issue35_history_scope():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        spec = {'label': 'checkout', 'path': '/fixture', 'fetch': False}
        for scope, expected in [(None, 2), ('all', 2), ('head', 1)]:
            source = {**spec, **({'history': scope} if scope else {})}
            _, f, _ = snapshot(home, inventory([source]))
            assert len(f['commits']) == expected, 'head history must exclude other refs'
            assert f['commit_count_14'] == expected and sum(w['n'] for w in f['weekly']) == expected
            html = rendered(home)
            label = '目前分支' if scope == 'head' else '所有分支'
            assert label in html['project'] and label in html['trends'], 'history scope must be visible'
        _, f, _ = snapshot(home, inventory([
            {**spec, 'label': 'all refs', 'history': 'all'},
            {**spec, 'label': 'HEAD only', 'history': 'head'}]))
        assert len(f['commits']) == 2, 'mixed scopes still deduplicate full commit hashes'
        html = rendered(home)['history']
        assert 'all refs · 所有分支' in html and 'HEAD only · 目前分支' in html
        try: validate_inventory(inventory([{**spec, 'history': 'invalid'}]))
        except ValueError as e: assert '.history' in str(e)
        else: raise AssertionError('invalid history accepted')


@case
def test_issue36_git_not_collected():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        for sources, error in [([{'label': 'blocked', 'path': '/fixture'}], 'Permission denied <fixture>'), ([], None)]:
            _, f, _ = snapshot(home, inventory(sources), error)
            html = rendered(home)
            for where in ('now', 'project', 'home', 'trends', 'history'):
                assert '改動紀錄沒讀到' in html[where], (where, html[where])
                assert '沒有改動紀錄' not in html[where], where
                if error: assert 'Permission denied &lt;fixture&gt;' in html[where], where
            if error: assert f['sources']['git:/fixture']['status'] == 'failed'
        _, _, _ = snapshot(home, inventory([{'label': 'ok', 'path': '/fixture', 'fetch': False}]))
        assert '改動紀錄沒讀到' not in rendered(home)['now']
        # One failed checkout must not hide the successfully read checkout's work.
        _, f, _ = snapshot(home, inventory([
            {'label': 'blocked', 'path': '/fixture', 'fetch': False},
            {'label': 'healthy', 'path': '/healthy', 'fetch': False}]), 'Permission denied')
        html = rendered(home)
        assert f['commits'] and len(f['repos']) == 1
        assert '部分 Git 來源' in html['now'] and 'local work' in html['history']
        assert 'Permission denied' in html['home']
        # Legacy snapshots still carry enough information to report a failed read.
        path = next((home / 'facts').glob('*.json'))
        old = json.loads(path.read_text())
        old['projects']['p']['sources'] = {}
        path.write_text(json.dumps(old))
        assert 'Permission denied' in rendered(home)['now']


@case
def test_issue37_setup_explains_diagram_limits():
    text = (S.parent / 'SKILL.md').read_text()
    setup = text.split('**Optional plain words.**', 1)[1].split('**Optional schedule', 1)[0]
    assert 'title' in setup and 'sub' in setup and 'zone' in setup
    assert 'never adds' in setup and all(word in setup for word in ('steps', 'paths', 'detail', 'media'))
    assert 'report.py' in setup and '"paths": ["report.py"]' in setup
    # The manual example must be usable configuration, not only a promise to explain later.
    example = setup.split('```json', 1)[1].split('```', 1)[0]
    node = json.loads(example)
    assert node['id'] and node['title'] and node['paths'] == ['report.py']


if __name__ == '__main__':
    failures = 0
    for test in (test_issue34_fetch_opt_out, test_issue35_history_scope,
                 test_issue36_git_not_collected, test_issue37_setup_explains_diagram_limits):
        try: test()
        except Exception as e:
            failures += 1
            print(f'FAILED {test.__name__}: {type(e).__name__}: {e}', flush=True)
    print(('FAILED: ' if failures else 'OK: ') + summary())
    raise SystemExit(bool(failures))
