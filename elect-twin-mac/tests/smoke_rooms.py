"""Exercise the copied Rooms engine with an isolated persistent HOME."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_APP = ROOT / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" / "Resources" / "server" / "rooms-server"
CANDIDATE_PY = ROOT.parent / "elect-twin-windows" / "rooms_server.py"

def get_engine_cmd():
    custom = os.environ.get("ELECT_TWIN_ROOMS_ENGINE")
    if custom:
        if custom.endswith(".py"):
            return [sys.executable, custom]
        return [custom]
    if CANDIDATE_APP.exists():
        return [str(CANDIDATE_APP)]
    if CANDIDATE_PY.exists():
        return [sys.executable, str(CANDIDATE_PY)]
    return [str(CANDIDATE_APP)]

def start(home):
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    cmd = get_engine_cmd()
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
    value = json.loads(process.stdout.readline())
    assert value["ready"]
    return process, value["urls"]

def client(url):
    origin = url.split("/#", 1)[0]
    token = url.split("token=", 1)[1]
    def call(path, data=None):
        request = Request(origin + "/api/" + path, data=json.dumps(data).encode() if data is not None else None, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    return call

with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
    home = Path(directory) / "rooms-home"
    process, urls = start(home)
    try:
        jay = client(urls["jay"])
        alex = client(urls["alex"])
        state = jay("state")
        room = state["rooms"][0]["id"]
        jay("policy", {"room": room, "agent": "jay-twin", "enabled": True, "topics": [], "mentions": True, "max_runs": 5, "tool_limit": 5, "tools": ["read_shared_context"]})
        jay("message", {"room": room, "text": "@jay-twin summarize this packaging check", "nonce": "native-smoke-1"})
        detail = None
        for _ in range(50):
            detail = jay("room?id=" + room)
            if any(event.get("kind") == "agent" for event in detail.get("events", [])):
                break
            time.sleep(0.1)
        assert any(event.get("kind") == "agent" and "deterministic" in event.get("text", "").lower() for event in detail["events"])
        assert any(job.get("status") == "complete" for job in detail["jobs"])
        jay("private", {"text": "Jay-only native smoke secret"})
        assert alex("private")["text"] != "Jay-only native smoke secret"
        alex_state = alex("state")
        assert "Jay-only native smoke secret" not in json.dumps(alex_state)
        print(json.dumps({"rooms_permission_and_job": "passed", "private_note_isolation": "passed", "llm_calls": 0}, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)

    process, urls = start(home)
    try:
        jay = client(urls["jay"])
        state = jay("state")
        room = state["rooms"][0]["id"]
        detail = jay("room?id=" + room)
        assert any("packaging check" in event.get("text", "") for event in detail["events"])
        assert jay("private")["text"] == "Jay-only native smoke secret"
        database = home / "Library" / "Application Support" / "Elect Twin Rooms" / "rooms.sqlite3"
        assert database.exists()
        print(json.dumps({"rooms_restart_persistence": "passed", "isolated_database": str(database.relative_to(home))}, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)
