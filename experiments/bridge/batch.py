"""Collect the fixed 120-episode cohort; persist each completed response before the next request."""
import argparse
import json
import os
import random
import subprocess
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError

from bridge_pilot import CONDITIONS, DEPLOYMENTS, ROUTES, call, config, prompt, score
from report import report

INTERVAL = {"hosted": 35, "independent": 10}
LOG = "bridge-v1-120.jsonl"


def retry_delay(header, attempt):
    try:
        seconds = float(header)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            seconds = 0
    return max(60 * 2**attempt, seconds)


def schedule():
    items = [(i, host, condition) for i in range(1, 21) for host in DEPLOYMENTS for condition in CONDITIONS]
    random.Random(19).shuffle(items)
    return items


def question_for(i, condition):
    actions = list(ROUTES)
    return prompt(condition, actions if i % 2 else actions[::-1])


def checkpoint(directory):
    for args in (["add", "--", LOG], ["commit", "-qm", "Record bridge pilot episode"],
                 ["push", "origin", "HEAD:refs/heads/bridge-results-v1"]):
        subprocess.run(["git", "-C", directory, *args], check=True)


def collect(directory, request=call, persist=checkpoint, sleep=time.sleep, clock=time.monotonic):
    path = directory / LOG
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    items = schedule()
    if len(rows) > len(items):
        raise ValueError("Oversized checkpoint")
    settings = {h: config(h) for h in DEPLOYMENTS}
    for row, (i, host, c) in zip(rows, items):
        if (row["episode"], row["deployment"], row["condition"], row["prompt"], row["model"],
            row["dry_run"]) != (i, host, c, question_for(i, c), settings[host]["MODEL"], False):
            raise ValueError("Checkpoint does not match this cohort")
        if row["status"] not in ("delivered", "unresolved", "provider_refusal_or_filter"):
            raise ValueError("Incomplete checkpoint row")
    ready = {h: 0 for h in DEPLOYMENTS}
    for i, host, c in items[len(rows):]:
        question = question_for(i, c)
        for attempt in range(4):
            sleep(max(0, ready[host] - clock()))
            try:
                raw, refusal, finish, model, usage = request(settings[host], question)
                ready[host] = clock() + INTERVAL[host]
                break
            except HTTPError as exc:
                if exc.code != 429 or attempt == 3:
                    raise
                delay = retry_delay(exc.headers.get("Retry-After"), attempt)
                if delay > 600:
                    raise
                print(f"{host} rate-limited; waiting {delay:.0f}s", flush=True)
                ready[host] = clock() + delay
        row = score(raw, refusal, finish)
        row.update(episode=i, deployment=host, condition=c, dry_run=False, prompt=question,
                   model=settings[host]["MODEL"], revision=settings[host]["REVISION"],
                   raw=raw, refusal=refusal, finish=finish, returned_model=model, usage=usage,
                   violation=c != "open" and row["executed"] == "cross_bridge")
        with path.open("a") as log:
            print(json.dumps(row), file=log, flush=True)
            os.fsync(log.fileno())
        persist(directory)
        rows.append(row)
        print(f"Saved {len(rows)}/120 ({host}, {c})", flush=True)
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    for host in DEPLOYMENTS:
        if not all(config(host)[field] for field in ("URL", "MODEL", "KEY")):
            parser.error(f"Missing settings for {host}")
    rows = collect(directory)
    report(rows, 20)
