"""Inspect only the bundled prototype entry point to diagnose storage arguments."""
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader

path = Path(__file__).resolve().parents[1] / "rooms-reference" / "Elect Twin Rooms.app" / "Contents" / "Resources" / "server" / "rooms-server"
archive = CArchiveReader(str(path))
entry = archive.extract("mac_entry")
import marshal
import types
code = marshal.loads(entry)
def walk(value):
    if isinstance(value, types.CodeType):
        print("CODE", value.co_name, "NAMES", value.co_names, "VARS", value.co_varnames)
        for item in value.co_consts:
            walk(item)
    elif isinstance(value, (str, int, float, tuple)) and value:
        print(repr(value))
walk(code)
