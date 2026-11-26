#!/usr/bin/env python3
"""Loads the freshly built workspace (ros2_ws/install) into this process.

pixi activates the environment once, when the command starts: a workspace built
afterwards (by `build`, or by `pixi run launch` in another terminal) is not in it yet.

    python scripts/overlay.py <command> ...   # runs <command> with the workspace loaded
"""
import os
import subprocess
import sys
from pathlib import Path

INSTALL = Path(__file__).resolve().parent.parent / "ros2_ws" / "install"


def load() -> None:
    if not INSTALL.is_dir():
        sys.exit("no workspace yet, run: pixi run build")
    if os.name == "nt":
        dump = ["cmd", "/c", str(INSTALL / "setup.bat"), "&&", "set"]
    else:
        # Printed by Python, not env: macOS SIP strips DYLD_LIBRARY_PATH from /usr/bin/env.
        dump = ["bash", "-c", f'source "{INSTALL}/setup.bash" && "$0" -c "import os; print(chr(0).join(k + \'=\' + v for k, v in os.environ.items()), end=\'\')"', sys.executable]
    out = subprocess.run(dump, capture_output=True, text=True, check=True).stdout
    os.environ.update(line.split("=", 1) for line in out.split("\0" if os.name != "nt" else "\n") if "=" in line)


if __name__ == "__main__":
    load()
    if sys.argv[1] == "rviz2" and sys.platform.startswith("linux") and "KDE" not in os.environ.get("XDG_CURRENT_DESKTOP", ""):
        # HiDPI screens (GNOME at 200 %): scale the whole window, not only the fonts.
        # KDE already scales X11 apps: Qt would round its 1.67 to 2, black squares on resize.
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    if sys.argv[1] == "rviz2" and os.path.exists("/dev/dxg"):
        # WSL: D3D12 draws empty views on many GPUs, opt in with GALLIUM_DRIVER=d3d12.
        if os.environ.get("GALLIUM_DRIVER") == "d3d12":
            print("[rviz] WSL: RViz renders on the GPU (GALLIUM_DRIVER=d3d12)", file=sys.stderr)
        else:
            os.environ["GALLIUM_DRIVER"] = "llvmpipe"
            print("[rviz] WSL: RViz renders on the CPU, GALLIUM_DRIVER=d3d12 for the GPU", file=sys.stderr)
    command = sys.argv[1:]
    if command[0] == "rviz2" and "--ros-args" not in command:
        # Hides its startup INFO lines ("Stereo is NOT SUPPORTED"), keeps warnings and errors.
        command += ["--ros-args", "--log-level", "rviz2:=warn"]
    try:
        sys.exit(subprocess.call(command))
    except KeyboardInterrupt:
        sys.exit(130)
