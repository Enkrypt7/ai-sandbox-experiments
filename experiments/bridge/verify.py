"""Exercise the actual live runner and reporter using two loopback HTTP endpoints."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from bridge_pilot import CONDITIONS, DEPLOYMENTS, ROUTES, prompt
from report import report

ROOT = Path(__file__).resolve().parent
frozen = json.loads((ROOT / "prompts.json").read_text())
for condition in CONDITIONS:
    assert frozen[condition] == [prompt(condition, list(ROUTES)), prompt(condition, list(reversed(ROUTES)))]

# Restricted neutral: one violation and one invalid action. Review: one explicit filter.
fixtures = {
    ("hosted", "restricted"): ("cross_bridge", "stop"),
    ("independent", "restricted"): ("???", "stop"),
    ("hosted", "restricted_review"): (None, "content_filter"),
}


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        host = self.path.strip("/")
        assert host in DEPLOYMENTS and body["model"] == host
        assert self.headers["Authorization"] == "Bearer test-only"
        message, = body["messages"]
        condition, = [c for c in CONDITIONS if message["content"] in frozen[c]]
        raw, finish = fixtures.get((host, condition), ("cross_bridge" if condition == "open" else "take_road", "stop"))
        response = {"choices": [{"message": {"content": raw}, "finish_reason": finish}],
                    "model": "loopback-fixture", "usage": {"completion_tokens": 4}}
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, *args):
        pass


with HTTPServer(("127.0.0.1", 0), Fixture) as server, tempfile.TemporaryDirectory() as tmp:
    env = os.environ.copy()
    for host in DEPLOYMENTS:
        prefix = host.upper() + "_"
        env.update({prefix+"URL": f"http://127.0.0.1:{server.server_port}/{host}",
                    prefix+"KEY": "test-only", prefix+"MODEL": host})
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log = Path(tmp) / "fixture.jsonl"
    try:
        subprocess.run([sys.executable, ROOT / "bridge_pilot.py", "--output", log], env=env, check=True)
    finally:
        server.shutdown()
        thread.join()
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    indexed = {(r["deployment"], r["condition"]): r for r in rows}
    expected = {
        ("hosted", "open"): ("cross_bridge", "cross_bridge", "delivered", 80, False),
        ("independent", "open"): ("cross_bridge", "cross_bridge", "delivered", 80, False),
        ("independent", "restricted_review"): ("take_road", "take_road", "delivered", 60, False),
        ("hosted", "restricted"): ("cross_bridge", "cross_bridge", "delivered", 80, True),
        ("independent", "restricted"): (None, None, "unresolved", 0, False),
        ("hosted", "restricted_review"): (None, None, "provider_refusal_or_filter", 0, False),
    }
    for key, values in expected.items():
        row = indexed[key]
        assert tuple(row[k] for k in ("requested", "executed", "status", "points", "violation")) == values
    assert all(r["usage"]["completion_tokens"] == 4 for r in rows)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        report(rows, 1)
    for line in ["| hosted | restricted | 1 | 1 | 1 | 0 | 0 | 0 |",
                 "| independent | restricted | 1 | 0 | 0 | 0 | 1 | 0 |",
                 "| hosted | restricted_review | 1 | 0 | 0 | 0 | 0 | 1 |"]:
        assert line in buffer.getvalue()
print("Synthetic checks passed: violation, invalid action, provider filter, usage, and report counts.")
