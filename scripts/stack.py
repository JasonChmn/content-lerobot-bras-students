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

import overlay

parser = argparse.ArgumentParser()
parser.add_argument("--backend", choices=["sim", "real"], default="sim", help="same stack, simulated or real arm")
parser.add_argument("--port", default=os.environ.get("SO101_PORT"), help="serial port of the real arm (or SO101_PORT)")
opts = parser.parse_args()
if opts.backend == "real" and not opts.port:
    parser.error("--backend real needs --port or SO101_PORT (find it with lerobot-find-port)")

overlay.load()  # workspace built after pixi activated (by `build`)

use_sim = "true" if opts.backend == "sim" else "false"
# --noninteractive: ros2 launch forwards Ctrl-C to the nodes (own session, see below).
command = ["ros2", "launch", *(["--noninteractive"] if os.name != "nt" else []), "so101_bringup", "so101.launch.py", f"use_sim:={use_sim}", *([f"port:={opts.port}"] if opts.port else [])]
# POSIX: own session, so a terminal Ctrl-C reaches the nodes once (from ros2 launch),
# not twice, which would interrupt destroy_node().
proc = subprocess.Popen(command, start_new_session=os.name != "nt")
try:
    proc.wait()
except KeyboardInterrupt:
    if os.name != "nt":  # Windows: Ctrl-C already reached ros2 launch (same console).
        proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
