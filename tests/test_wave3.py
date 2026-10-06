"""Wave 3 regressions; stdlib fixtures, no services or installed host required."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills/project-inventory/scripts"


def test_install_paths():
    """The documented commands install the same layout and update without nesting."""
    source = ROOT / "skills/project-inventory"
    with tempfile.TemporaryDirectory() as td:
        for host in (".codex", ".hermes"):
            for scenario in ("clean", "existing_home", "installed", "reinstall"):
                home = Path(td) / host / scenario
                dest = home / host / "skills/project-inventory"
                if scenario == "existing_home":
                    (home / host).mkdir(parents=True)
                if scenario in ("installed", "reinstall"):
                    dest.mkdir(parents=True)
                    (dest / "SKILL.md").write_text("old version")
                    sibling = dest.parent / "another-skill/SKILL.md"
                    sibling.parent.mkdir()
                    sibling.write_text("keep")
                env = dict(os.environ, HOME=str(home))
                commands = f'mkdir -p ~/{host}/skills/project-inventory\ncp -R "{source}/." ~/{host}/skills/project-inventory/\ntest -f ~/{host}/skills/project-inventory/SKILL.md'
                for _ in range(2 if scenario == "reinstall" else 1):
                    subprocess.run(["sh", "-ec", commands], env=env, check=True)
                assert (dest / "SKILL.md").read_bytes() == (source / "SKILL.md").read_bytes()
                assert (dest / "scripts/collect.py").is_file()
                assert not (dest / "project-inventory").exists()
                if scenario in ("installed", "reinstall"):
                    assert sibling.read_text() == "keep"
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    skill = "project-inventory"
    for doc in ("README.md", "說明書.md", "skills/project-inventory/SKILL.md"):
        assert f'/{plugin["name"]}:{skill}' in (ROOT / doc).read_text()


def test_artifact_fragment():
    """Reproducible output is a local fragment, with the same page data, not a publication."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "inventory.json").write_text(json.dumps({"projects": [{"key": "demo", "name": "Demo"}]}))
        for script in ("collect.py", "build.py"):
            result = subprocess.run([sys.executable, str(S / script), str(home)], capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
        page = (home / "out/index.html").read_text()
        fragment = (home / "out/artifact.html").read_text()
        for wrapper in ("<!doctype", "<html", "<head>", "<body>", "<meta"):
            assert wrapper not in fragment.lower(), wrapper
        assert "<style>" in fragment and "<script>" in fragment
        import re
        payload = r"const D = (.*?);\n"
        assert re.search(payload, page).group(1) == re.search(payload, fragment).group(1)
