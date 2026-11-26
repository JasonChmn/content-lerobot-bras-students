#!/usr/bin/env python3
"""driver_node.py - ROS2 driver of the SO-ARM101.

The only node that talks to the backend: SO101Sim (MuJoCo) or SO101Follower
(real arm), chosen by the `use_sim` parameter. The rest of the stack never
knows which one runs.

TODO:
  - Publish /joint_states in RADIANS (>= 20 Hz)
  - Subscribe to /joint_command (radians, gripper 0-100 %)
  - Real arm: publish the USB camera on /external_cam/image_raw
    (the simulated camera is provided: _start_sim_camera)
"""
import os
import threading
import time
from pathlib import Path

import rclpy
import rclpy.node
from cv_bridge import CvBridge
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import CameraInfo, Image, JointState
from so101_sim import SO101Sim

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# Gripper joint limits in the URDF (rad).
# LeRobot convention: 0 % = closed (lower), 100 % = open (upper).
GRIPPER_RANGE_RAD = (-0.174533, 1.74533)


CONTROL_HZ = 50.0
JOINT_STATE_HZ = 30.0
CAMERA_HZ = 10.0
CAMERA_FRAME = "external_cam_optical_frame"


def _calibration_file() -> Path:
    """Calibration file of the real arm, from SO101_CALIBRATION_FILE (provided)."""
    path = os.environ.get("SO101_CALIBRATION_FILE")
    if not path:
        raise RuntimeError("SO101_CALIBRATION_FILE is not set: point it to the calibration file of your arm (see README, Real arm)")
    return Path(path).expanduser()


def _gripper_pct_to_rad(pct: float) -> float:
    raise NotImplementedError("TO DO")


class DriverNode(rclpy.node.Node):
    """Driver SO-ARM101: /joint_command -> backend -> /joint_states."""

    def __init__(self):
        super().__init__("so101_driver")
        self._use_sim: bool = self.declare_parameter("use_sim", True).value
        port: str = self.declare_parameter("port", "").value
        self.get_logger().info("Mode: simulation" if self._use_sim else f"Mode: hardware (port={port})")

        self._robot = self._connect_arm(port)
        self.get_logger().info(f"Robot connected: {type(self._robot).__name__}")

        # TODO: create the publishers, subscribers and timers.

        if self._use_sim:
            self._start_sim_camera()

        self.get_logger().info("Driver node ready.")

    def _connect_arm(self, port: str) -> SO101Sim | SO101Follower:
        """Creates and connects the backend chosen by use_sim (provided)."""
        if self._use_sim:
            robot = SO101Sim()
            robot.connect()
            return robot

        if not port:
            raise RuntimeError("No serial port: pass port:=<port> (pixi run launch --backend real --port <port>)")
        calibration_file = _calibration_file()
        if not calibration_file.is_file():
            raise RuntimeError(f"No calibration file at {calibration_file}: calibrate it with `lerobot-calibrate` first")
        config = SO101FollowerConfig(
            port=port,
            id=calibration_file.stem,
            calibration_dir=calibration_file.parent,
            use_radians=True,
        )
        robot = SO101Follower(config)
        robot.connect(calibrate=False)
        if not robot.is_calibrated:
            robot.disconnect()
            raise RuntimeError(
                f"{calibration_file} does not match the motors: wrong file for this arm? "
                "Re-run `lerobot-calibrate`."
            )
        robot.bus.disable_torque()  # Comment out this line to control the robot.
        self.get_logger().info(
            "Torque disabled: arm can be moved freely by hand. Remove this part to control the arm."
        )
        return robot

    def _start_sim_camera(self):
        """Publishes the MuJoCo camera at CAMERA_HZ (provided): /external_cam/image_raw + camera_info."""
        self._image_pub = self.create_publisher(Image, "/external_cam/image_raw", 1)
        self._camera_info_pub = self.create_publisher(CameraInfo, "/external_cam/camera_info", 1)
        K = self._robot.get_camera_intrinsics()
        self._camera_info = CameraInfo(
            width=self._robot.camera_width,
            height=self._robot.camera_height,
            distortion_model="plumb_bob",
            d=[0.0] * 5,
            k=[float(v) for v in K.flatten()],
            r=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            p=[float(v) for v in K[0]] + [0.0] + [float(v) for v in K[1]] + [0.0] + [float(v) for v in K[2]] + [0.0],
        )
        self._camera_info.header.frame_id = CAMERA_FRAME
        self._camera_stop = threading.Event()
        # Own thread: a render takes 30-150 ms, it must not delay /joint_states.
        self._camera_thread = threading.Thread(target=self._sim_camera_loop, daemon=True)
        self._camera_thread.start()

    def _sim_camera_loop(self):
        bridge = CvBridge()
        next_frame = time.monotonic()
        while not self._camera_stop.wait(max(0.0, next_frame - time.monotonic())):
            next_frame += 1.0 / CAMERA_HZ
            # shortcut: renders while your timers step the physics; fine for a camera image.
            image = bridge.cv2_to_imgmsg(self._robot.render_camera(), encoding="rgb8")
            image.header.stamp = self.get_clock().now().to_msg()
            image.header.frame_id = CAMERA_FRAME
            self._camera_info.header.stamp = image.header.stamp
            try:
                self._image_pub.publish(image)
                self._camera_info_pub.publish(self._camera_info)
            except Exception:  # ROS context already shut down (Ctrl-C)
                return

    def destroy_node(self):
        """Disconnects the backend (provided). On the real arm this disables the torque."""
        if getattr(self, "_camera_thread", None) is not None:
            self._camera_stop.set()
            self._camera_thread.join(timeout=2.0)
        if self._robot.is_connected:
            self._robot.disconnect()
            self.get_logger().info("Robot disconnected.")
        super().destroy_node()

    def _cb_joint_command(self, msg: JointState):
        raise NotImplementedError("TO DO")

    def _control_step(self):
        raise NotImplementedError("TO DO")

    def _publish_joint_states(self):
        raise NotImplementedError("TO DO")


def main(args=None):
    rclpy.init(args=args)
    node = DriverNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
