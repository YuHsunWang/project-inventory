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


def test_text_token_contrast():
    """Measure actual CSS tokens, including automatic/manual dark and mixed backgrounds."""
    import re
    css = (S / "template.html").read_text().split("<style>", 1)[1].split("</style>", 1)[0]
    modes = [dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", block))
             for block in re.findall(r":root[^{}]*\{([^}]+)\}", css) if "--ground:" in block]
    assert len(modes) == 3, "light, automatic dark and explicit dark must all be checked"
    assert modes[1] == modes[2], "automatic and explicit dark tokens must stay in step"
    def rgb(value):
        return tuple(int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
    def luminance(value):
        return sum(weight * (v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4)
                   for weight, v in zip((.2126, .7152, .0722), value))
    def ratio(a, b):
        low, high = sorted((luminance(a), luminance(b)))
        return (high + .05) / (low + .05)
    def mix(a, b, amount):
        return tuple(x * amount + y * (1 - amount) for x, y in zip(a, b))
    # All fixed text tokens on the page/ground, semantic badges and inverse labels.
    text = set(re.findall(r"(?<![\w-])color:var\(--([\w-]+)\)", css)) - {"c"}
    pairs = {(fg, bg) for fg in text - {"paper"} for bg in ("paper", "ground")}
    pairs.add(("paper", "ink"))
    for rule in re.findall(r"\{([^{}]*)\}", css):
        fg = re.search(r"(?<![\w-])color:var\(--([\w-]+)\)", rule)
        bg = re.search(r"background:var\(--([\w-]+)\)", rule)
        if fg and bg:
            pairs.add((fg[1], bg[1]))
    minimum = 100
    for mode, tokens in enumerate(modes):
        for fg, bg in pairs:
            score = ratio(rgb(tokens[fg]), rgb(tokens[bg]))
            assert score >= 4.5, (mode, fg, bg, score)
            minimum = min(minimum, score)
        # Card numbers/labels, inset detail and subnav text inherit these backgrounds.
        for fg in ("open", "wait", "accent", "bad"):
            bg = mix(rgb(tokens[fg]), rgb(tokens["paper"]), .11)
            for label in (fg, "muted"):
                score = ratio(rgb(tokens[label]), bg)
                assert score >= 4.5, (mode, "summary", label, score)
                minimum = min(minimum, score)
        for fg in ("ink", "muted", "faint"):
            for base in ("ground", "paper"):
                bg = mix(rgb(tokens["ink"]), rgb(tokens[base]), .07)
                score = ratio(rgb(tokens[fg]), bg)
                assert score >= 4.5, (mode, "subnav", fg, score)
                minimum = min(minimum, score)
        bg = mix(rgb(tokens["accent"]), rgb(tokens["paper"]), .07)
        for fg in ("ink", "muted"):
            assert ratio(rgb(tokens[fg]), bg) >= 4.5, (mode, "detail", fg)
        # Arbitrary project colors tint nodes; check both RGB extremes and midpoint.
        for project in ("#000000", "#FFFFFF", "#808080"):
            pc = rgb(project) if mode == 0 else mix(rgb(project), rgb("#FFFFFF"), .62)
            for amount in (.16, .28):
                bg = mix(pc, rgb(tokens["paper"]), amount)
                assert ratio(rgb(tokens["ink"]), bg) >= 4.5, (mode, "node", project)
    assert ".node .s{font-size:13px;color:var(--ink)" in css
    return minimum
