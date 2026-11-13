"""Extract inline scripts and validate syntax with the installed Node runtime."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
rooms_ref_web = ROOT / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" / "Resources" / "server" / "_internal" / "web" / "index.html"
win_rooms_web = ROOT.parent / "elect-twin-windows" / "web" / "index.html"

candidate_rooms = rooms_ref_web if rooms_ref_web.exists() else win_rooms_web

DOCUMENTS = [
    ROOT / "web" / "index.html",
    ROOT / "web" / "shell.html",
    ROOT / "web" / "zoo.js",
    ROOT / "web" / "app.js",
    ROOT / "web" / "hub.js",
    ROOT / "web" / "onboarding.js",
    candidate_rooms,
]

with tempfile.TemporaryDirectory(dir=ROOT / "tests") as directory:
    for index, document in enumerate(DOCUMENTS):
        source = document.read_text(encoding="utf-8")
        scripts = [source] if document.suffix == ".js" else re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", source, re.S)
        if not scripts:
            raise SystemExit(f"No JavaScript found in {document}")
        for script_index, script in enumerate(scripts):
            target = Path(directory) / f"script-{index}-{script_index}.js"
            target.write_text(script, encoding="utf-8")
            subprocess.run(["node", "--check", str(target)], check=True)
        try:
            display_name = document.relative_to(ROOT.parent)
        except ValueError:
            display_name = document.name
        print(f"JavaScript syntax passed: {display_name}")
