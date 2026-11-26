#!/usr/bin/env python3
"""Launches the ROS 2 stack: so101_bringup/launch/so101.launch.py.

Ctrl-C stops it cleanly so destroy_node() runs (the real arm gets a proper disconnect).

    pixi run launch                                        # backend sim (default)
    pixi run launch --backend real --port /dev/ttyACM0     # real arm (port from lerobot-find-port)
    pixi run launch --backend real                         # port from SO101_PORT
"""
import argparse
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

import overlay
from crash_report import CrashReport

parser = argparse.ArgumentParser()
parser.add_argument("--backend", choices=["sim", "real"], default="sim", help="same stack, simulated or real arm")
parser.add_argument("--port", default=os.environ.get("SO101_PORT"), help="serial port of the real arm (or SO101_PORT)")
opts = parser.parse_args()
if opts.backend == "real" and not opts.port:
    parser.error("--backend real needs --port or SO101_PORT (find it with lerobot-find-port)")

overlay.load()  # workspace built after pixi activated (by `build`)

os.environ.setdefault("PYTHONUNBUFFERED", "1")  # print() of the nodes shows at once
if os.name == "nt":  # ros2 launch only shows lines ending with \r\n on Windows, rcutils ends them with \n
    os.environ.setdefault("RCUTILS_CONSOLE_OUTPUT_FORMAT", "[{severity}] [{time}] [{name}]: {message}\r")

use_sim = "true" if opts.backend == "sim" else "false"
# --noninteractive: ros2 launch forwards Ctrl-C to the nodes (own session, see below).
command = ["ros2", "launch", *(["--noninteractive"] if os.name != "nt" else []), "so101_bringup", "so101.launch.py", f"use_sim:={use_sim}", *([f"port:={opts.port}"] if opts.port else [])]
# POSIX: own session, so a terminal Ctrl-C reaches the nodes once (from ros2 launch),
# not twice, which would interrupt destroy_node().
proc = subprocess.Popen(command, start_new_session=os.name != "nt", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
report = CrashReport(Path(__file__).resolve().parent.parent / "ros2_ws" / "src")
reader = threading.Thread(target=report.follow, args=(proc.stdout,), daemon=True)
reader.start()


def _interrupt(*_):
    raise KeyboardInterrupt


# Closed terminal (SIGHUP) or kill: stop the stack too, it no longer gets the terminal's signals.
for name in ("SIGHUP", "SIGTERM"):
    if hasattr(signal, name):
        signal.signal(getattr(signal, name), _interrupt)
try:
    proc.wait()
except KeyboardInterrupt:
    report.stopping = True
    for name in ("SIGINT", "SIGHUP", "SIGTERM"):  # extra Ctrl-C: the nodes are already stopping
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), signal.SIG_IGN)
    if os.name != "nt":  # Windows: Ctrl-C already reached ros2 launch (same console).
        proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            os.killpg(proc.pid, signal.SIGKILL)  # ros2 launch and its nodes
        else:
            proc.kill()
reader.join(timeout=5)
if os.name == "nt":
    # ros2 launch stops a Python node by killing its .exe wrapper: kill the python.exe orphaned by it.
    install = str(Path(__file__).resolve().parent.parent / "ros2_ws" / "install").replace("'", "''")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "$alive = (Get-Process).Id; Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*"
                    + install + "*' -and $alive -notcontains $_.ParentProcessId } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True)
try:
    sys.exit(report.print_summary())
except OSError:  # terminal closed
    sys.exit(1)
