"""Named case reporting shared by the release suites (stdlib only)."""
from functools import wraps
from unittest import SkipTest

passed = skipped = 0


def case(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        global passed, skipped
        try:
            result = fn(*args, **kwargs)
        except SkipTest as e:
            skipped += 1
            print(f"SKIPPED {fn.__name__}: {e}", flush=True)
            return
        passed += 1
        print(f"PASSED {fn.__name__}", flush=True)
        return result
    return run


def summary():
    return f"{passed} passed / {skipped} skipped"
