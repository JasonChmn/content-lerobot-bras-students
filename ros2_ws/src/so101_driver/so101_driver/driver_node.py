#!/usr/bin/env python3
"""driver_node.py - ROS2 driver of the SO-ARM101.

The only node that talks to the backend: SO101Sim (MuJoCo) or SO101Follower
(real arm), chosen by the `use_sim` parameter. The rest of the stack never
knows which one runs.

  /joint_command  (sensor_msgs/JointState, in)  arm joints in rad, gripper in 0-100 %
  /joint_states   (sensor_msgs/JointState, out) all joints in rad (URDF convention)
  /external_cam/image_raw (sensor_msgs/Image, out, sim only) rgb8
"""
import math
from pathlib import Path

import rclpy
import rclpy.node
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import Image, JointState

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]
ARM_JOINT_NAMES = JOINT_NAMES[:5]

# Gripper joint limits in the URDF (rad).
# LeRobot convention: 0 % = closed (lower), 100 % = open (upper).
GRIPPER_RANGE_RAD = (-0.174533, 1.74533)

# Calibration file of the real arm, mounted by docker compose (CALIBRATION_FILE in docker/.env).
CALIBRATION_FILE = Path("/calibration/arm.json")
DEFAULT_PORT = "/dev/ttyACM0"

CONTROL_HZ = 50.0
JOINT_STATE_HZ = 30.0
CAMERA_HZ = 10.0


def _gripper_pct_to_rad(pct: float) -> float:
    lo, hi = GRIPPER_RANGE_RAD
    pct = min(max(pct, 0.0), 100.0)
    return lo + pct / 100.0 * (hi - lo)


class DriverNode(rclpy.node.Node):
    """Driver SO-ARM101: /joint_command -> backend -> /joint_states."""

    def __init__(self):
        super().__init__("so101_driver")
        self._use_sim: bool = self.declare_parameter("use_sim", True).value
        port: str = self.declare_parameter("port", DEFAULT_PORT).value
        mode = "simulation" if self._use_sim else "hardware"
        self.get_logger().info(f"Mode: {mode} (port={port})")

        self._robot = self._connect_arm(port)
        self._has_camera = hasattr(self._robot, "render_camera")

        # Latest observation (joint -> value, gripper in %) and pending command.
        self._obs = self._robot.get_observation()
        self._pending_action: dict | None = None

        self._pub_joint_states = self.create_publisher(JointState, "/joint_states", 10)
        self._pub_image = (
            self.create_publisher(Image, "/external_cam/image_raw", 1)
            if self._has_camera
            else None
        )
        self.create_subscription(JointState, "/joint_command", self._cb_joint_command, 10)

        # Single-threaded executor: the timers never run concurrently, so the
        # backend (MuJoCo data / serial bus) is never accessed from two places at once.
        self.create_timer(1.0 / CONTROL_HZ, self._control_step)
        self.create_timer(1.0 / JOINT_STATE_HZ, self._publish_joint_states)
        if self._has_camera:
            self.create_timer(1.0 / CAMERA_HZ, self._publish_image)

        self.get_logger().info("Driver node ready.")

    def _connect_arm(self, port: str = DEFAULT_PORT):
        if self._use_sim:
            from so101_sim import SO101Sim

            robot = SO101Sim()
            robot.connect()
            return robot

        from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

        config = SO101FollowerConfig(
            port=port,
            id=CALIBRATION_FILE.stem,
            calibration_dir=CALIBRATION_FILE.parent,
            use_radians=True,
        )
        robot = SO101Follower(config)
        # calibrate=False: the interactive calibration prompt cannot run under ros2 launch.
        robot.connect(calibrate=False)
        if not robot.is_calibrated:
            if not robot.calibration:
                raise RuntimeError(
                    f"No calibration found at {CALIBRATION_FILE}: set CALIBRATION_FILE in docker/.env"
                )
            self.get_logger().info(f"Writing calibration {CALIBRATION_FILE} to the motors")
            robot.bus.write_calibration(robot.calibration)
        return robot

    def destroy_node(self):
        robot = getattr(self, "_robot", None)
        if robot is not None and robot.is_connected:
            self.get_logger().info("Disconnecting backend.")
            robot.disconnect()
        super().destroy_node()

    def _cb_joint_command(self, msg: JointState):
        if len(msg.name) != len(msg.position):
            self.get_logger().warn("/joint_command: name and position lengths differ, ignored")
            return
        action = {}
        for name, value in zip(msg.name, msg.position):
            if name not in JOINT_NAMES:
                self.get_logger().warn(f"/joint_command: unknown joint '{name}', ignored")
                continue
            if not math.isfinite(value):
                self.get_logger().warn(f"/joint_command: non-finite value for '{name}', ignored")
                continue
            action[f"{name}.pos"] = float(value)
        if action:
            # Merge so that two partial commands received between two control steps both apply.
            self._pending_action = {**(self._pending_action or {}), **action}

    def _control_step(self):
        if self._pending_action is not None:
            self._robot.send_action(self._pending_action)
            self._pending_action = None
        # On the sim, get_observation() also advances the physics.
        self._obs = self._robot.get_observation()

    def _publish_joint_states(self):
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = list(JOINT_NAMES)
        positions = [float(self._obs[f"{n}.pos"]) for n in ARM_JOINT_NAMES]
        positions.append(_gripper_pct_to_rad(float(self._obs["gripper.pos"])))
        msg.position = positions
        self._pub_joint_states.publish(msg)

    def _publish_image(self):
        img = self._robot.render_camera()  # (H, W, 3) uint8 RGB
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "external_cam"
        msg.height, msg.width = int(img.shape[0]), int(img.shape[1])
        msg.encoding = "rgb8"
        msg.is_bigendian = 0
        msg.step = msg.width * 3
        msg.data = img.tobytes()
        self._pub_image.publish(msg)


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
