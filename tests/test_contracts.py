"""Config/data contract regressions, imported by test_scripts.py; stdlib only."""
import copy
import datetime as dt
import json
from pathlib import Path
from unittest.mock import patch

import collect
import validation as v


def expect_error(fn, text):
    try:
        fn()
    except ValueError as e:
        assert text in str(e), str(e)
    else:
        raise AssertionError('invalid input was accepted: ' + text)


def test_inventory_contract_paths():
    inv = {'projects': [{'key': 'cvs', 'name': 'CVS', 'nodes': [{'id': 1}, {'id': 2, 'on': 1}]}]}
    cases = [({'key': 'home'}, 'projects[0].key: reserved'),
             ({'key': 'team/app'}, 'projects[0].key: use only'),
             ({'key': 'x y'}, 'projects[0].key: use only'),
             ({'nodes': [{'id': 1}, {'id': 1}]}, 'projects[0].nodes[1].id: duplicate'),
             ({'nodes': [{'id': 1}, {'id': 2, 'on': 99}]}, 'projects[0].nodes[1].on:'),
             ({'nodes': [{'id': 1}, {'id': 2, 'on': 1}, {'id': 3, 'on': 2}]}, 'projects[0].nodes[2].on:'),
             ({'nodes': [{'id': 1, 'on': 1}]}, 'projects[0].nodes[0].on:'),
             ({'links': [['bad', 'javascript:alert(1)']]}, 'projects[0].links[0][1]:'),
             ({'sources': {'notion': {'url': 'relative'}}}, 'projects[0].sources.notion.url:'),
             ({'data': [{'kind': 'json', 'path': 'x', 'column': 'date', 'max_age_days': -1}]}, 'projects[0].data[0].max_age_days:')]
    for changes, message in cases:
        bad = copy.deepcopy(inv); bad['projects'][0].update(changes)
        expect_error(lambda: v.validate_inventory(bad), message)
    duplicate = {'projects': [*inv['projects']] * 4}
    expect_error(lambda: v.validate_inventory(duplicate), 'projects[1].key: duplicate "cvs"')
    expect_error(lambda: v.validate_inventory({'projects': 'bad'}), 'projects: expected list')
    assert v.validate_inventory(inv) == inv
    # The user fixture must remain valid without migration or writes to its source.
    real = Path.home() / '.project-inventory/inventory.json'
    if real.exists():
        v.validate_inventory(json.loads(real.read_text()))


def ticket(**fields):
    return {'id': 'N-1', 'source_id': 'full-page-1', 'source': 'notion', 'title': 'one',
            'state': 'open', 'created': '2026-10-01', 'url': 'https://notion.so/full-page-1', **fields}


def test_gathered_contract_and_dedupe():
    inv = {'projects': [{'key': 'p', 'name': 'P', 'nodes': [{'id': 1}]}]}
    for field, value, message in [('state', 'broken', '.state:'), ('created', '2026-02-30', '.created:'),
                                  ('completed', 'garbage', '.completed:'), ('url', 'ftp://host', '.url:'),
                                  ('node', 99, '.node:')]:
        data = {'p': {'tickets': [ticket(**{field: value})]}}
        expect_error(lambda: v.validate_gathered(data, inv), 'gathered.p.tickets[0]' + message)
    expect_error(lambda: v.validate_gathered({'missing': {}}, inv), 'gathered.missing: unknown')
    short = ticket(); short.pop('source_id'); short.pop('url')
    expect_error(lambda: v.validate_gathered({'p': {'tickets': [short]}}, inv), '.source_id:')
    # Colliding short display IDs belong to distinct full Notion page IDs.
    pr = {'repo': 'o/r', 'number': 1, 'title': 'PR', 'url': 'https://github.com/o/r/pull/1'}
    data = {'p': {'tickets': [ticket(), ticket(title='duplicate'), ticket(source_id='full-page-2'),
                              ticket(source='linear')], 'prs': [pr, dict(pr), {**pr, 'repo': 'o/other'}]}}
    v.validate_gathered(data, inv)
    assert len(data['p']['tickets']) == 3 and len(data['p']['prs']) == 2
    legacy = [ticket(), ticket()]
    for row in legacy: row.pop('source_id')
    assert len(v.validate_rows(legacy, 'tickets')) == 1, 'full page URL is a stable legacy identity'


def test_contract_cli_failures(root, run):
    root.mkdir()
    inv = {'projects': [{'key': 'p', 'name': 'P'}]}
    (root / 'inventory.json').write_text(json.dumps(inv))
    inv['projects'].append(inv['projects'][0])
    (root / 'inventory.json').write_text(json.dumps(inv))
    for script in ('build.py', 'collect.py'):
        result = run(script, str(root))
        assert result.returncode == 2 and 'projects[1].key: duplicate "p"' in result.stderr, result.stderr
        assert 'Traceback' not in result.stderr
    inv['projects'].pop(); (root / 'inventory.json').write_text(json.dumps(inv))
    (root / 'gathered').mkdir()
    path = root / 'gathered' / f'{dt.date.today()}.json'
    path.write_text(json.dumps({'p': {'tickets': [ticket(state='bad')]}}))
    with patch.object(collect, 'git_state', side_effect=AssertionError('must fail before collection')):
        expect_error(lambda: collect.collect_snapshot(root), str(path) + '.p.tickets[0].state:')
    result = run('collect.py', str(root))
    assert result.returncode == 2 and '.p.tickets[0].state:' in result.stderr
    # Build validates loaded fact rows too, before rendering or creating a page.
    (root / 'refresh.json').unlink()
    for file in (root / 'out').glob('*.html'): file.unlink()
    (root / 'facts').mkdir()
    snap = {'date': '2026-10-06', 'generated_at': '2026-10-06T00:00:00',
            'projects': {'p': {'tickets': [ticket(state='bad')]}}}
    (root / 'facts/2026-10-06.json').write_text(json.dumps(snap))
    result = run('build.py', str(root))
    assert result.returncode == 2 and 'snapshot.projects.p.tickets[0].state:' in result.stderr
    assert 'const D =' not in (root / 'out/index.html').read_text(), 'failure banner may exist, but no broken dashboard'


def run_validation_tests(tmp, run):
    test_inventory_contract_paths()
    test_gathered_contract_and_dedupe()
    test_contract_cli_failures(tmp / 'contracts', run)
    test_timezone_normalization_and_boundary(tmp)


def test_timezone_normalization_and_boundary(tmp):
    assert v.calendar_date('2026-10-04T23:30:00Z', 'Asia/Taipei') == dt.date(2026, 10, 5)
    assert v.calendar_date('2026-10-05T07:30:00+08:00', 'UTC') == dt.date(2026, 10, 4)
    assert v.calendar_date('2026-10-04', 'Asia/Taipei') == dt.date(2026, 10, 4)
    assert v.calendar_date('2026-10-05T00:30:00', 'Asia/Taipei') == dt.date(2026, 10, 5)
    expect_error(lambda: v.validate_inventory({'timezone': 'Bad/Zone', 'projects': []}), 'timezone: unknown')
    for value in ('', 'bad', '2026-02-30', '20261004', '2026-10-04junk'):
        expect_error(lambda: v.normalize_date(value), 'date:')
    file = tmp / 'dates.jsonl'
    spec = {'kind': 'jsonl', 'path': str(file), 'column': 'date', 'max_age_days': 1}
    file.write_text('\n'.join(json.dumps({'date': x}) for x in [None, '', '2026-10-05',
        '2026-10-05T00:15:00+08:00', '2026-10-04T23:30:00Z']))
    assert collect.newest_date(spec, 'Asia/Taipei') == '2026-10-05T07:30:00+08:00'
    assert not collect.data_check(spec, dt.date(2026, 10, 6), 'Asia/Taipei')['stale'], 'equality is fresh'
    assert collect.data_check(spec, dt.date(2026, 10, 7), 'Asia/Taipei')['stale'], 'limit + 1 is stale'
    for value, message in [('2099-01-01', 'future date'), ('bad', 'invalid ISO'), ('', 'no values')]:
        file.write_text(json.dumps({'date': value}))
        try:
            collect.data_check(spec, dt.date(2026, 10, 6), 'Asia/Taipei')
        except RuntimeError as e:
            assert message in str(e), str(e)
        else:
            raise AssertionError('invalid/future/empty dates must not look fresh')
    import sqlite3
    db = tmp / 'mixed.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE dates (day TEXT)')
        con.executemany('INSERT INTO dates VALUES (?)', [('2026-10-05T00:15:00+08:00',), ('2026-10-04T23:30:00Z',)])
    assert collect.newest_date({'kind': 'sqlite', 'path': str(db), 'column': 'day', 'table': 'dates'}, 'Asia/Taipei') == '2026-10-05T07:30:00+08:00'
