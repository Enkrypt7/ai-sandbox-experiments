"""Replay both naturally observed eligible decision points under both receipt values."""
import argparse
import json
import random
import sys
import time
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scanner_discovery"))
from game import MODEL, call, complete, config, retry_delay, step

ARMS = ("normal", "pays")
SOURCE = Path(__file__).resolve().parents[1] / "scanner_discovery/results/scanner.jsonl"


def schedule():
    rng = random.Random(271)
    for block in range(1, 7):
        cells = [(source, arm, order) for source in (1, 13) for arm in ARMS
                 for order in (("scan", "advance"), ("advance", "scan"))]
        rng.shuffle(cells)
        for cell in cells:
            yield (block, *cell)


def play(prefix, arm, order, decide):
    history = [dict(t) for t in prefix]
    assert history[-1]["repeat"] and not complete(history)
    history[-1]["credit"] = int(arm == "pays")
    while not complete(history):
        history.append(step(history, order, arm, decide))
    return history[len(prefix):]


def report(rows):
    print("# Persistence after a self-initiated rescan\n")
    print("Live continuations" if all(r["live"] for r in rows) else "Offline fixtures")
    print("\n| Source shift | Repeat receipt | Replays | Immediate rescan | Any subsequent rescan | Invalid decisions |")
    print("|---|---:|---:|---:|---:|---:|")
    for source in (1, 13):
        for arm in ARMS:
            group = [r["tail"] for r in rows if (r["source"],r["arm"]) == (source,arm)]
            assert len(group) == 12
            first = sum(t[0]["repeat"] for t in group)
            later = sum(any(s["repeat"] for s in t) for t in group)
            invalid = sum(s["action"] == "invalid" for t in group for s in t)
            print(f"| {source} | +{int(arm == 'pays')} | 12 | {first} | {later} | {invalid} |")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    prefixes = {r["episode"]: r["prefix"] for r in map(json.loads,SOURCE.read_text().splitlines())}
    settings = config("independent")
    if args.live and (not settings["KEY"] or settings["MODEL"] != MODEL):
        raise ValueError("Fireworks settings incomplete")

    def decide(question):
        if not args.live:
            return "scan", None, "stop", "fixture", None
        for attempt in range(4):
            time.sleep(3)
            try:
                return call(settings, question)
            except HTTPError as exc:
                if exc.code != 429 or attempt == 3:
                    raise
                delay = retry_delay(exc.headers.get("Retry-After"), attempt)
                if delay > 600:
                    raise
                time.sleep(delay)

    rows = []
    with open(args.output, "x", buffering=1) as out:
        for block, source, arm, order in schedule():
            tail = play(prefixes[source], arm, order, decide)
            row = dict(live=args.live, block=block, source=source, arm=arm, order=order, tail=tail)
            print(json.dumps(row), file=out)
            rows.append(row)
    report(rows)


if __name__ == "__main__":
    main()
