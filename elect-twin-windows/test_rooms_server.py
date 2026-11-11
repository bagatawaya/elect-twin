"""Verify the pure-Python rooms_server.py implementation against all smoke_rooms contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

SERVER_SCRIPT = Path(__file__).resolve().parent / "rooms_server.py"

def start(home):
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    process = subprocess.Popen(
        [sys.executable, str(SERVER_SCRIPT), "--port", "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    line = process.stdout.readline()
    value = json.loads(line)
    assert value["ready"], f"Expected ready, got {value}"
    return process, value["urls"]

def client(url):
    origin = url.split("/#", 1)[0]
    token = url.split("token=", 1)[1]
    def call(path, data=None):
        request = Request(
            origin + "/api/" + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        )
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    return call

def main():
    print("Testing pure-Python rooms_server.py...")
    with tempfile.TemporaryDirectory() as temp_dir:
        home = Path(temp_dir) / "rooms-home"
        process, urls = start(home)
        try:
            jay = client(urls["jay"])
            alex = client(urls["alex"])

            state = jay("state")
            assert len(state["rooms"]) > 0, "No rooms found in state"
            room = state["rooms"][0]["id"]

            jay("policy", {
                "room": room,
                "agent": "jay-twin",
                "enabled": True,
                "topics": [],
                "mentions": True,
                "max_runs": 5,
                "tool_limit": 5,
                "tools": ["read_shared_context"]
            })

            jay("message", {
                "room": room,
                "text": "@jay-twin summarize this packaging check",
                "nonce": "windows-smoke-1"
            })

            detail = None
            for _ in range(50):
                detail = jay("room?id=" + room)
                if any(event.get("kind") == "agent" for event in detail.get("events", [])):
                    break
                time.sleep(0.1)

            assert detail is not None, "Failed to fetch room detail"
            assert any(
                event.get("kind") == "agent" and "deterministic" in event.get("text", "").lower()
                for event in detail["events"]
            ), "Missing deterministic agent event"
            assert any(job.get("status") == "complete" for job in detail["jobs"]), "Missing complete job"

            jay("private", {"text": "Jay-only native smoke secret"})
            assert alex("private")["text"] != "Jay-only native smoke secret", "Private note leaked to Alex"
            alex_state = alex("state")
            assert "Jay-only native smoke secret" not in json.dumps(alex_state), "Private secret in Alex state"

            print(json.dumps({
                "rooms_permission_and_job": "passed",
                "private_note_isolation": "passed",
                "llm_calls": 0
            }, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)

        # Persistence check across restart
        process, urls = start(home)
        try:
            jay = client(urls["jay"])
            state = jay("state")
            room = state["rooms"][0]["id"]
            detail = jay("room?id=" + room)

            assert any("packaging check" in event.get("text", "") for event in detail["events"]), "Event not persisted"
            assert jay("private")["text"] == "Jay-only native smoke secret", "Private note not persisted"

            database = home / "Library" / "Application Support" / "Elect Twin Rooms" / "rooms.sqlite3"
            assert database.exists(), f"Database not found at {database}"

            print(json.dumps({
                "rooms_restart_persistence": "passed",
                "isolated_database": str(database.relative_to(home))
            }, indent=2))
        finally:
            process.terminate()
            process.wait(timeout=10)

    print("ALL ROOMS SERVER CONTRACTS PASSED CLEANLY!")

if __name__ == "__main__":
    main()
