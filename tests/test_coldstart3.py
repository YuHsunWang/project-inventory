"""Regressions for cold-start issues 48–49; fake data and repo-local homes only."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from test_support import case, summary

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills/project-inventory/scripts"
sys.path.insert(0, str(S))
import build, collect, validation


@case
def test_issue48_blank_obsidian_checkboxes_collect_and_validate():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        vault = home / "vault"
        vault.mkdir()
        (vault / "tasks.md").write_text("- [ ]\n- [x]\n- [ ]   \n- [x] \t\n- [X]   \n- [ ] Buy milk\n")
        inv = {"lang": "en", "projects": [{"key": "app", "name": "My App",
               "sources": {"obsidian": [{"path": str(vault)}]}, "nodes": []}]}
        (home / "inventory.json").write_text(json.dumps(inv))
        with redirect_stdout(io.StringIO()):
            code, snapshot, _ = collect.collect_snapshot(home)
            build.build_page(home)
        facts = validation.validate_snapshot(json.loads(snapshot.read_text()), inv)
        note = facts["projects"]["app"]["obsidian"][0]
        assert code == 0 and note["open"] == 1 and note["done"] == 0, note
        assert note["total"] == note["shown"] == 1
        assert note["items"] == [{"text": "Buy milk", "file": "tasks.md", "line": 6}]
        note["items"][0]["text"] = ""
        try:
            validation.validate_snapshot(facts, inv)
        except ValueError as exc:
            assert ".text" in str(exc), str(exc)
        else:
            raise AssertionError("snapshot validation must still reject empty task text")


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn) and (len(sys.argv) == 1 or name in sys.argv[1:]):
            try:
                fn()
            except Exception as exc:
                failed += 1
                print(f"FAILED {name}: {type(exc).__name__}: {exc}", flush=True)
    print(("FAILED: " if failed else "OK: ") + summary() + f" ({failed} failed)")
    raise SystemExit(bool(failed))
