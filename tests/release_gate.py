"""Run the offline release gate: python3 tests/release_gate.py."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / 'skills/project-inventory/scripts'


def main():
    scratch = ROOT / '.tmp'
    scratch.mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(scratch)
    tempfile.tempdir = str(scratch)
    passed = skipped = failed = 0
    with tempfile.TemporaryDirectory(prefix='release-') as td:
        commands = [
            ('unit, contracts and JS render', [sys.executable, str(ROOT / 'tests/test_scripts.py')]),
            ('browser regressions', [sys.executable, str(ROOT / 'tests/test_check_page.py')]),
            ('create zero-service demo', [sys.executable, str(S.parent / 'reference/demo.py'), td + '/demo']),
            ('add local demo history', [sys.executable, str(ROOT / 'tests/demo_fixture.py'), td + '/demo']),
            ('collect zero-service demo', [sys.executable, str(S / 'collect.py'), td + '/demo']),
            ('build zero-service demo', [sys.executable, str(S / 'build.py'), td + '/demo']),
            ('prepare offline demo fonts', [sys.executable, str(ROOT / 'tests/demo_fixture.py'), td + '/demo', '--offline-fonts']),
            ('demo browser matrix', [sys.executable, str(S / 'check_page.py'), td + '/demo']),
        ]
        for name, command in commands:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            output = result.stdout + result.stderr
            print(output, end='' if output.endswith('\n') else '\n', flush=True)
            match = re.search(r'OK: (\d+) passed / (\d+) skipped', output)
            if match:
                passed += int(match[1]); skipped += int(match[2])
            elif result.returncode == 0:
                passed += 1
            if result.returncode:
                failed += 1
                print(f'FAILED {name}: exit {result.returncode}', flush=True)
            else:
                print(f'PASSED {name}', flush=True)
    print(f'{"FAILED" if failed else "OK"}: {passed} passed / {skipped} skipped ({failed} failed stages)')
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
