"""Real Chromium regressions for the release checker; no external services."""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from test_support import case, summary
from demo_fixture import add_history, offline_fonts

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / 'skills/project-inventory/scripts'
spec = importlib.util.spec_from_file_location('check_page', S / 'check_page.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def run(script, *args):
    result = subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)
    return result


def check(home):
    return run(S / 'check_page.py', home)


@case
def test_browser_rejects_missing_browser(home):
    import os
    env = dict(os.environ, CHROMIUM_BIN=str(home / 'absent-browser'))
    result = subprocess.run([sys.executable, str(S / 'check_page.py'), str(home)], env=env, capture_output=True, text=True)
    assert result.returncode != 0 and 'FAILED' in result.stdout, result.stdout


@case
def test_browser_rejects_console_errors(home, original):
    page = home / 'out/index.html'
    page.write_text(original.replace('boot();', 'console.error("release-console-sentinel"); boot();'))
    result = check(home)
    assert result.returncode != 0 and 'console.error' in result.stdout, result.stdout
    page.write_text(original)


@case
def test_browser_rejects_js_errors(home, original):
    page = home / 'out/index.html'
    page.write_text(original.replace('boot();', 'boot(); setTimeout(() => {throw Error("release-js-sentinel")}, 0);'))
    result = check(home)
    assert result.returncode != 0 and 'release-js-sentinel' in result.stdout, result.stdout
    page.write_text(original)


@case
def test_browser_rejects_home_overflow(home, original):
    page = home / 'out/index.html'
    page.write_text(original.replace('</style>', '#home {min-width:2000px}</style>'))
    result = check(home)
    assert result.returncode != 0 and 'home: horizontal overflow' in result.stdout, result.stdout
    page.write_text(original)


@case
def test_browser_rejects_missing_projects(home, original):
    inventory = home / 'inventory.json'
    saved = inventory.read_text()
    data = json.loads(saved)
    data['projects'].append({'key':'missing', 'name':'Missing'})
    inventory.write_text(json.dumps(data))
    result = check(home)
    assert result.returncode != 0 and 'missing projects' in result.stdout, result.stdout
    inventory.write_text(saved)


@case
def test_browser_rejects_hidden_panels(home, original):
    page = home / 'out/index.html'
    page.write_text(original.replace('</style>', '.panel {visibility:hidden}</style>'))
    result = check(home)
    assert result.returncode != 0 and 'invisible panel' in result.stdout, result.stdout
    page.write_text(original)


@case
def test_browser_rejects_unloaded_assets(home, original):
    page = home / 'out/index.html'
    page.write_text(original.replace('</body>', '<img src="data:image/png;base64,YmFk" alt="broken"></body>'))
    result = check(home)
    assert result.returncode != 0 and 'image failed to load' in result.stdout, result.stdout
    page.write_text(original)


@case
def test_browser_states_long_paths_and_images(home):
    """Empty, failed and reused reads stay distinct in visible panels in every mode."""
    import datetime as dt
    import uuid
    data = json.loads((home / 'inventory.json').read_text())
    projects = data['projects']
    for key in ('empty', 'failed', 'stale'):
        projects.append({'key':key, 'name':key, 'sources':{'notion':{'url':'https://notion.so/fixture'}, 'local':projects[0]['sources']['local']},
                         'nodes':[{'id':1, 'title':'Read', 'paths':['long/' + 'x'*220 + '.py'],
                                   'media':[{'src':'data:image/png;base64,' + base64.b64encode(PNG).decode(), 'caption':'Sample image'}]}]})
    (home / 'inventory.json').write_text(json.dumps(data))
    gathered = home / 'gathered'; gathered.mkdir()
    stamp = dt.datetime.now().astimezone().isoformat()
    rid = uuid.uuid4().hex
    payload = {'_run':{'run_id':rid}}
    for key in ('empty', 'failed', 'stale'):
        payload[key] = {'sources':{'notion':{'run_id':rid, 'status':'failed' if key == 'failed' else 'ok',
                                           'complete':key != 'failed', 'fetched_at':stamp, 'error':'fixture failure' if key == 'failed' else None}},
                        'tickets':[]}
    (gathered / f'{dt.date.today()}.json').write_text(json.dumps(payload))
    for _ in range(2):
        result = run(S / 'collect.py', home)
        assert result.returncode == 1, result.stdout + result.stderr
    assert run(S / 'build.py', home).returncode == 0
    offline_fonts(home)
    result = check(home)
    assert result.returncode == 0, result.stdout + result.stderr
    # Inspect the same renderer payload, so browser coverage cannot silently lose a state.
    import re
    built = (home / 'out/index.html').read_text()
    d = json.loads(re.search(r'const D = (.*?);\n', built).group(1))
    states = {p['key']:p['ticket_state']['status'] for p in d['projects']}
    assert states['failed'] == 'failed' and states['stale'] == 'stale', states
    # A fresh complete empty read must remain empty (not stale).
    rid = uuid.uuid4().hex
    payload['_run']['run_id'] = rid
    for key in ('empty','stale'):
        payload[key]['sources']['notion']['run_id'] = rid
    (gathered / f'{dt.date.today()}.json').write_text(json.dumps(payload))
    assert run(S / 'collect.py', home).returncode == 1
    assert run(S / 'build.py', home).returncode == 0
    offline_fonts(home)
    built = (home / 'out/index.html').read_text()
    d = json.loads(re.search(r'const D = (.*?);\n', built).group(1))
    assert next(p for p in d['projects'] if p['key'] == 'empty')['ticket_state']['status'] == 'empty'
    result = check(home)
    assert result.returncode == 0, result.stdout + result.stderr


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII=')


def main():
    # Browser availability is mandatory for the release gate.
    checker.chromium()
    with tempfile.TemporaryDirectory(prefix='browser-cases-') as td:
        home = Path(td) / 'demo'
        result = run(S.parent / 'reference/demo.py', home)
        assert result.returncode == 0, result.stderr
        add_history(home)
        for script in (S / 'collect.py', S / 'build.py'):
            result = run(script, home)
            assert result.returncode == 0, result.stdout + result.stderr
        offline_fonts(home)
        page = home / 'out/index.html'
        # Intentional mutations are browser fixtures, so remove only their CSP meta.
        import re
        original = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', '', page.read_text())
        page.write_text(original)
        test_browser_rejects_missing_browser(home)
        for fn in (test_browser_rejects_console_errors, test_browser_rejects_js_errors,
                   test_browser_rejects_home_overflow, test_browser_rejects_missing_projects,
                   test_browser_rejects_hidden_panels, test_browser_rejects_unloaded_assets):
            fn(home, original)
        test_browser_states_long_paths_and_images(home)
    print('OK: ' + summary())


if __name__ == '__main__':
    main()
