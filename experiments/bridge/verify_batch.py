"""Exercise rate limiting, an interruption, a resumed batch, and an already complete batch offline."""
import os
import tempfile
from pathlib import Path
from urllib.error import HTTPError

from batch import collect, schedule

for host in ("hosted", "independent"):
    os.environ[host.upper() + "_MODEL"] = "offline"
waits = []
calls = 0


def fixture(settings, question):
    global calls
    calls += 1
    if calls == 1:
        raise HTTPError("fixture", 429, "rate limited", {"Retry-After": "75"}, None)
    if calls == 8:
        raise RuntimeError("fixture interruption")
    return "take_road", None, "stop", "offline", {}


with tempfile.TemporaryDirectory() as tmp:
    args = dict(directory=Path(tmp), request=fixture, persist=lambda directory: None,
                sleep=waits.append, clock=lambda: 0)
    try:
        collect(**args)
    except RuntimeError as error:
        assert str(error) == "fixture interruption"
    rows = collect(**args)
    assert len(rows) == 120 and calls == 122 and 75 in waits and 35 in waits and 10 in waits
    assert [(r["episode"], r["deployment"], r["condition"]) for r in rows] == schedule()
    assert collect(**args) == rows and calls == 122
print("Offline rate-limit, resume and duplicate-run checks passed.")
