#!/usr/bin/env python3
"""Builds ros2_ws with colcon (pixi run build). Extra arguments go to colcon."""
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from crash_report import location

WS = Path(__file__).resolve().parent.parent / "ros2_ws"
STAMPS = WS / "build" / "so101_stamps.json"



def package_roots() -> dict:
    """Package name -> its folder, for the packages colcon builds."""
    roots = {}
    for xml in (WS / "src").rglob("package.xml"):
        root = xml.parent
        if not any((d / "COLCON_IGNORE").exists() for d in [root, *root.parents] if WS / "src" in [d, *d.parents]):
            roots[re.search(r"<name>\s*(\S+?)\s*</name>", xml.read_text(encoding="utf-8"))[1]] = root
    return roots


def package_stamps() -> dict:
    """Package name -> latest modification time of its files."""
    return {
        name: max(
            os.stat(os.path.join(d, f)).st_mtime
            for d, dirs, files in os.walk(root)
            if "__pycache__" not in d and ".egg-info" not in d
            for f in [*files, "."]
        )
        for name, root in package_roots().items()
    }


def syntax_errors(packages: list) -> list:
    """Compiles the Python files of these packages: a typo shows now, not after the stack started."""
    roots = package_roots()
    errors = []
    for name in packages:
        for path in sorted(roots[name].rglob("*.py")):
            try:
                compile(path.read_bytes(), str(path), "exec")
            except SyntaxError as error:
                errors.append(f"{location(str(path), error.lineno or 1, error.offset)}: {type(error).__name__}: {error.msg}")
                line = (error.text or "").rstrip()
                code = line.lstrip()
                errors.append(f"    {code}")
                if error.offset:
                    errors.append("    " + " " * max(0, error.offset - 1 - (len(line) - len(code))) + "^")
    return errors


if sys.platform.startswith("linux") and "microsoft" in platform.uname().release.lower() and str(WS).startswith("/mnt/"):
    print(f"WSL: {WS.parent} is on the Windows disk, builds are many times slower. Clone the repo in ~/ instead.", file=sys.stderr)

select = []
if not sys.argv[1:]:
    old = json.loads(STAMPS.read_text()) if STAMPS.is_file() and (WS / "install").is_dir() else {}
    changed = [name for name, stamp in package_stamps().items() if old.get(name) != stamp]
    if not changed:
        print("ros2_ws is up to date (pixi run clean to rebuild everything)")
        sys.exit(0)
    if errors := syntax_errors(changed):
        print("\n".join(errors), file=sys.stderr)
        sys.exit("\nFix this Python error first: nothing was built or launched.")
    select = ["--packages-select", *changed]

# Symlinks need admin rights on Windows: Python edits need a rebuild (launch does it).
args = ["--merge-install"] if os.name == "nt" else ["--symlink-install"]
# python -m colcon: the colcon.exe shim breaks when the Python path holds a space.
code = subprocess.call([sys.executable, "-m", "colcon", "build", *args, *select, *sys.argv[1:]], cwd=WS)
if code == 0 and select:
    # A failed build marks nothing: the changed packages are retried next time.
    STAMPS.write_text(json.dumps({**old, **{name: stamp for name, stamp in package_stamps().items() if name in changed}}))
sys.exit(code)
