#!/usr/bin/env python3
"""Checks the setup and says how to fix each problem (pixi run doctor).

    pixi run doctor            # setup, ROS 2 messages, real arm settings
    pixi run doctor --camera   # also opens the camera of SO101_CAMERA_DEVICE
"""
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import env_file

ROOT = Path(__file__).resolve().parent.parent
WSL = sys.platform.startswith("linux") and "microsoft" in platform.uname().release.lower()
results = []


def report(status: str, name: str, detail: str, fix: str = ""):
    results.append(status)
    print(f"[{status:>4}] {name}: {detail}")
    if fix:
        print(f"       fix: {fix}")


def check_repo_path():
    path = str(ROOT)
    if os.name == "nt" and " " in path:
        report("FAIL", "Repo path", path, "move the repo to a short path without spaces, e.g. C:\\tek5_robotics")
    elif WSL and path.startswith("/mnt/"):
        report("FAIL", "Repo path", f"{path} is on the Windows disk: builds are many times slower", "clone the repo in ~/ inside WSL")
    else:
        report("ok", "Repo path", path)


def check_workspace():
    if (ROOT / "ros2_ws" / "install").is_dir():
        report("ok", "Workspace", "built")
    else:
        report("FAIL", "Workspace", "not built", "pixi run build")


def check_ros_messages():
    """A second process must receive a small message and a camera-sized one (900 kB)."""
    listener = subprocess.Popen([sys.executable, __file__, "--listen"], stdout=subprocess.PIPE, text=True)
    import rclpy
    from sensor_msgs.msg import Image
    from std_msgs.msg import String

    rclpy.init()
    node = rclpy.create_node("so101_doctor_talker")
    small, big = node.create_publisher(String, "/so101_doctor/small", 10), node.create_publisher(Image, "/so101_doctor/big", 10)
    image = Image(height=480, width=640, encoding="rgb8", step=640 * 3, data=bytes(640 * 480 * 3))
    deadline = time.monotonic() + 8
    while listener.poll() is None and time.monotonic() < deadline:
        small.publish(String(data="ping"))
        big.publish(image)
        time.sleep(0.2)
    listener.kill()
    received = (listener.communicate()[0] or "").split()
    node.destroy_node()
    rclpy.shutdown()
    rmw = os.environ.get("RMW_IMPLEMENTATION", "default")
    if "small" not in received:
        report("FAIL", "ROS 2 messages", f"no message between two processes ({rmw})",
               "send this output to your teacher")
    elif "big" not in received:
        report("FAIL", "ROS 2 messages", f"small messages pass, camera-sized ones do not ({rmw})", "report it to your teacher with this output")
    else:
        report("ok", "ROS 2 messages", f"small and camera-sized messages pass ({rmw})")


def listen():
    import rclpy
    from sensor_msgs.msg import Image
    from std_msgs.msg import String

    rclpy.init()
    node = rclpy.create_node("so101_doctor_listener")
    got = set()
    node.create_subscription(String, "/so101_doctor/small", lambda _: got.add("small"), 10)
    node.create_subscription(Image, "/so101_doctor/big", lambda _: got.add("big"), 10)
    deadline = time.monotonic() + 8
    while got != {"small", "big"} and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    print(" ".join(sorted(got)), flush=True)


def check_real_arm():
    calibration = os.environ.get("SO101_CALIBRATION_FILE")
    if not calibration:
        report("warn", "SO101_CALIBRATION_FILE", "not set (needed for --backend real)", "lerobot-calibrate, then set it (README, Real arm)")
    elif not Path(calibration).expanduser().is_file():
        report("FAIL", "SO101_CALIBRATION_FILE", f"{calibration} does not exist", "check the path, or run lerobot-calibrate")
    else:
        try:
            motors = len(json.loads(Path(calibration).expanduser().read_text()))
            report("ok" if motors == 6 else "FAIL", "SO101_CALIBRATION_FILE", f"{calibration} ({motors} motors)",
                   "" if motors == 6 else "not an SO-101 calibration file, run lerobot-calibrate")
        except ValueError:
            report("FAIL", "SO101_CALIBRATION_FILE", f"{calibration} is not valid JSON", "run lerobot-calibrate again")

    from serial.tools import list_ports

    ports = [p.device for p in list_ports.comports() if p.vid is not None]  # USB only: no Bluetooth or /dev/ttyS*
    port = os.environ.get("SO101_PORT")
    if not port:
        report("warn", "SO101_PORT", "not set (or pass --port)", f"lerobot-find-port; ports now: {', '.join(ports) or 'none'}")
    elif sys.platform.startswith("linux") and Path(port).exists() and not port.startswith("/dev/serial/by-id/"):
        stable = [str(p) for p in Path("/dev/serial/by-id").glob("*") if p.resolve() == Path(port).resolve()]
        report("warn", "SO101_PORT", f"{port} can change when you plug the arms in another order",
               f"use SO101_PORT={stable[0]}" if stable else "use its /dev/serial/by-id/ name")
    elif port in ports or Path(port).exists():
        report("ok", "SO101_PORT", port)
    else:
        report("FAIL", "SO101_PORT", f"{port} not found", f"plug the arm, then lerobot-find-port; ports now: {', '.join(ports) or 'none'}")
    if sys.platform.startswith("linux") and not WSL:
        groups = subprocess.run(["id", "-Gn"], capture_output=True, text=True).stdout.split()
        if "dialout" not in groups:
            report("warn", "Serial access", "you are not in the dialout group", "sudo usermod -aG dialout $USER, then log out and back in")


def check_camera():
    import cv2

    device = os.environ.get("SO101_CAMERA_DEVICE", "0")
    capture = cv2.VideoCapture(int(device) if device.isdigit() else device)
    ok = capture.isOpened() and capture.read()[0]
    capture.release()
    if ok:
        report("ok", "Camera", f"SO101_CAMERA_DEVICE={device} gives images")
    else:
        report("FAIL", "Camera", f"SO101_CAMERA_DEVICE={device} gives no image",
               "lerobot-find-cameras, then set SO101_CAMERA_DEVICE; close the apps using the camera")


def main():
    if "--listen" in sys.argv:
        return listen()
    env_file.load()
    print(f"{platform.system()} {platform.release()}{' (WSL)' if WSL else ''}, Python {platform.python_version()}")
    check_repo_path()
    check_workspace()
    check_ros_messages()
    check_real_arm()
    if "--camera" in sys.argv:
        check_camera()
    failures = results.count("FAIL")
    print(f"\n{failures} problem(s) to fix" if failures else "\nAll good")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
