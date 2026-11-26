#!/usr/bin/env python3
"""driver_node.py - ROS2 driver of the SO-ARM101.

The only node that talks to the backend: SO101Sim (MuJoCo) or SO101Follower
(real arm), chosen by the `use_sim` parameter. The rest of the stack never
knows which one runs.

TODO:
  - Publish /joint_states in RADIANS (>= 20 Hz)
  - Subscribe to /joint_command (radians, gripper 0-100 %)
"""
import os
from pathlib import Path

import rclpy
import rclpy.node
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import JointState
from so101_sim import SO101Sim

from .camera import SimCamera, UsbCamera

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

        self._camera = SimCamera(self, self._robot) if self._use_sim else UsbCamera(self)

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

    def destroy_node(self):
        """Disconnects the backend (provided). On the real arm this disables the torque."""
        if hasattr(self, "_camera"):
            self._camera.stop()
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
