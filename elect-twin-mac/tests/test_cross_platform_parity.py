"""Explicit Mac→Windows mirror parity and protected Rooms/native files."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

MAC = Path(__file__).resolve().parents[1]
WORKSPACE = MAC.parent
WINDOWS = WORKSPACE / "elect-twin-windows"
TOOL = WORKSPACE / "tools" / "sync_opentwin.py"
SPEC = importlib.util.spec_from_file_location("sync_opentwin", TOOL)
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CrossPlatformParityTests(unittest.TestCase):
    def test_every_allowlisted_file_is_identical(self):
        mismatches = [name for name in SYNC.MIRRORED_FILES if not (WINDOWS / name).is_file() or digest(MAC / name) != digest(WINDOWS / name)]
        self.assertEqual(mismatches, [])

    def test_sync_allowlist_excludes_rooms_native_and_installers(self):
        source = TOOL.read_text(encoding="utf-8")
        for protected in ("rooms_server.py", "ElectTwinWin/Program.cs", "installer.iss", "test_rooms_server.py"):
            self.assertNotIn(protected, source)
            self.assertNotIn(protected, SYNC.MIRRORED_FILES)

    def test_sync_preserves_protected_windows_hashes(self):
        protected = [WINDOWS / "rooms_server.py", WINDOWS / "test_rooms_server.py", WINDOWS / "ElectTwinWin" / "Program.cs", WINDOWS / "installer.iss"]
        before = {path: digest(path) for path in protected}
        copied = SYNC.sync_files(MAC, WINDOWS)
        self.assertEqual(copied, list(SYNC.MIRRORED_FILES))
        self.assertEqual({path: digest(path) for path in protected}, before)


if __name__ == "__main__":
    unittest.main()
