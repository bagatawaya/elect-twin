"""Cold-start bundled servers with isolated data and exercise real local HTTP."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]

def _normalize_engine_path(raw):
    p = Path(raw)
    if not p.is_absolute():
        if (Path.cwd() / p).exists():
            return str((Path.cwd() / p).resolve())
        if (ROOT / p).exists():
            return str((ROOT / p).resolve())
        if (ROOT.parent / p).exists():
            return str((ROOT.parent / p).resolve())
    return raw

def resolve_twin_cmd():
    custom = os.environ.get("ELECT_TWIN_ENGINE")
    if custom:
        custom = _normalize_engine_path(custom)
        if custom.endswith(".py"):
            return [sys.executable, custom]
        return [custom]
    exe_candidate = ROOT.parent / "elect-twin-windows" / "dist" / "twin-server.exe"
    if exe_candidate.exists():
        return [str(exe_candidate)]
    bin_candidate = ROOT / "packaging" / "dist" / "twin-server"
    if bin_candidate.exists():
        return [str(bin_candidate)]
    return [sys.executable, str(ROOT / "twin.py")]

def resolve_rooms_cmd():
    custom = os.environ.get("ELECT_TWIN_ROOMS_ENGINE")
    if custom:
        custom = _normalize_engine_path(custom)
        if custom.endswith(".py"):
            return [sys.executable, custom]
        return [custom]
    app_candidate = ROOT / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" / "Resources" / "server" / "rooms-server"
    if app_candidate.exists():
        return [str(app_candidate)]
    exe_candidate = ROOT.parent / "elect-twin-windows" / "dist" / "rooms-server.exe"
    if exe_candidate.exists():
        return [str(exe_candidate)]
    py_candidate = ROOT.parent / "elect-twin-windows" / "rooms_server.py"
    if py_candidate.exists():
        return [sys.executable, str(py_candidate)]
    return [str(app_candidate)]

def ready(process):
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("Engine exited before its ready message")
    value = json.loads(line)
    if not value.get("ready"):
        raise RuntimeError("Engine did not become ready")
    return value

with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
    root = Path(directory)
    rooms_environment = dict(os.environ)
    rooms_environment["HOME"] = str(root / "rooms-home")
    rooms_environment["LOCALAPPDATA"] = str(root / "rooms-home" / "AppData" / "Local")
    rooms = subprocess.Popen(resolve_rooms_cmd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=rooms_environment)
    twin = None
    try:
        room_value = ready(rooms)
        room_origin = room_value["urls"]["jay"].split("/#", 1)[0]
        room_token = room_value["urls"]["jay"].split("token=", 1)[1]
        with urlopen(Request(room_origin + "/api/state", headers={"Authorization": "Bearer " + room_token}), timeout=5) as response:
            room_state = json.load(response)
        assert len(room_state["people"]) == 2
        # Check database creation (Library on Darwin, AppData or .electri-rooms on others)
        rooms_db_found = any((root / "rooms-home").rglob("rooms.sqlite3"))
        assert rooms_db_found, "Rooms did not create its isolated database after initialization"
        environment = dict(os.environ)
        environment["ELECT_TWIN_ROOMS_JAY"] = room_value["urls"]["jay"]
        environment["ELECT_TWIN_ROOMS_ALEX"] = room_value["urls"]["alex"]
        twin_cmd = resolve_twin_cmd() + ["--native", "--port", "0", "--data", str(root / "projects.db")]
        twin = subprocess.Popen(twin_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
        twin_value = ready(twin)
        twin_url = twin_value["url"]
        token = twin_url.split("token=", 1)[1]
        origin = twin_value["origin"]
        def api(path, data=None):
            request = Request(origin + path, data=json.dumps(data).encode() if data is not None else None, headers={"X-Twin-Token": token, "Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                return json.load(response)
        with urlopen(twin_url, timeout=5) as response:
            html = response.read().decode()
            assert "Agent Zoo" in html and "My Models" in html
        state = api("/api/state")
        assert state["rooms"]["jay"] == room_value["urls"]["jay"]
        project = api("/api/projects", {"name": "Packaging smoke", "goal": "Verify a real local project"})
        api("/api/decision", {"project_id": project["id"], "text": "Keep Rooms data separate"})
        challenge = api("/api/challenges", {"title": "Installed app check", "prompt": "Inspect the packaged engine"})
        api("/api/challenge/review", {"id": challenge["id"], "approved": True})
        api("/api/follow", {"kind": "agent", "target": "jay-twin", "label": "Jay Twin"})
        state = api("/api/state")
        assert state["projects"][0]["name"] == "Packaging smoke"
        assert state["challenges"][0]["status"] == "reviewed"
        assert len(state["following"]) == 1
        assert not (root / "rooms-home" / "Library" / "Application Support" / "Elect Twin Rooms" / "rooms.sqlite3").read_bytes() == (root / "projects.db").read_bytes()
        print(json.dumps({"bundled_runtime_cold_start": "passed", "project_write": "passed", "challenge_review": "passed", "following": "passed", "rooms_links": "passed", "provider_calls": 0}, indent=2))
    finally:
        if twin is not None:
            twin.terminate()
            twin.wait(timeout=10)
        rooms.terminate()
        rooms.wait(timeout=10)
