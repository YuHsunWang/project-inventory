"""Add deterministic local sample history to the zero-service browser demo."""
import json
from pathlib import Path
import subprocess


def add_history(home):
    home = Path(home)
    repo = home / 'sample-repo'
    repo.mkdir()
    for args in (['init','-q'], ['-c','user.name=Sample','-c','user.email=sample@example.invalid',
                              'commit','-q','--allow-empty','-m','Sample report input']):
        subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
    path = home / 'inventory.json'
    inventory = json.loads(path.read_text())
    inventory['projects'][0]['sources']['local'] = [{'label':'Sample history', 'path':str(repo.resolve())}]
    path.write_text(json.dumps(inventory))


def offline_fonts(home):
    # Offline browser fixtures exercise the CSS fallback fonts; CDN availability
    # is a separate live acceptance concern, not part of the zero-service gate.
    import re
    page = Path(home) / 'out/index.html'
    page.write_text(re.sub(r'<link[^>]+href="https://fonts\.(?:googleapis|gstatic)\.com[^>]*>', '', page.read_text()))


if __name__ == '__main__':
    import sys
    offline_fonts(sys.argv[1]) if len(sys.argv) > 2 else add_history(sys.argv[1])
