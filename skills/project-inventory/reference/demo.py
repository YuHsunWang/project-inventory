"""Create a zero-service home from the repository example (sample orders only).

    python3 skills/project-inventory/reference/demo.py .tmp/demo
    python3 skills/project-inventory/scripts/collect.py .tmp/demo
    python3 skills/project-inventory/scripts/build.py .tmp/demo
"""
import datetime as dt
import json
from pathlib import Path
import sys


def main():
    home = Path(sys.argv[1]).expanduser().resolve()
    if (home / "inventory.json").exists():
        sys.exit("Refusing to overwrite an existing inventory home; use a new directory.")
    home.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(Path(__file__).with_name("example-inventory.json").read_text())
    project = inventory["projects"][0]
    project["sources"] = {}
    project["tag"] = "Sample orders: fetch input, then build a report. No external services."
    orders = home / "orders.csv"
    orders.write_text("order_id,created_at\n1," + dt.date.today().isoformat() + "\n")
    project["data"][0]["path"] = str(orders)
    (home / "inventory.json").write_text(json.dumps(inventory, indent=2))
    print("Created sample-only home: " + str(home))


if __name__ == "__main__":
    main()
