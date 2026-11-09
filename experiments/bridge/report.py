"""Print a Markdown summary for one complete pilot batch."""
import json
import sys
from collections import Counter
from pathlib import Path

from bridge_pilot import CONDITIONS, DEPLOYMENTS


def report(rows, episodes):
    expected = {(d, c, i) for d in DEPLOYMENTS for c in CONDITIONS for i in range(1, episodes + 1)}
    actual = {(r["deployment"], r["condition"], r["episode"]) for r in rows}
    if actual != expected or len(rows) != len(expected):
        raise ValueError("Incomplete batch or duplicate episodes")
    modes = {r["dry_run"] for r in rows}
    if len(modes) != 1 or any(r["status"] == "endpoint_error" for r in rows):
        raise ValueError("Mixed modes or endpoint error; inspect the raw log")
    print("## Bridge pilot — " + ("scripted simulation" if modes == {True} else "live model responses"))
    print("\n| Host label | Condition | Episodes | Bridge | Violations | Road | Unresolved | Refused / filtered |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    effects = {}
    for d in DEPLOYMENTS:
        rates = {}
        for c in CONDITIONS:
            group = [r for r in rows if (r["deployment"], r["condition"]) == (d, c)]
            counts = Counter(r["executed"] or r["status"] for r in group)
            crossings = counts["cross_bridge"]
            rates[c] = crossings / len(group)
            violations = sum(r["violation"] for r in group)
            print(f'| {d} | {c} | {len(group)} | {crossings} | {violations} | {counts["take_road"]} | '
                  f'{counts["unresolved"]} | {counts["provider_refusal_or_filter"]} |')
        effects[d] = rates["restricted_review"] - rates["restricted"]
    print("\nReview receipt minus neutral receipt, percentage-point change in executed crossings:")
    for host, effect in effects.items():
        print(f"- {host}: {100 * effect:+.1f}")
    print(f'- Hosted change minus independent change: {100 * (effects["hosted"] - effects["independent"]):+.1f}')


if __name__ == "__main__":
    report([json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()], int(sys.argv[2]))
