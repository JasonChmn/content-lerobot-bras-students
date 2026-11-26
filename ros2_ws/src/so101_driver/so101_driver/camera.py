"""camera.py - /external_cam publishers of the driver (provided).

SimCamera renders the MuJoCo camera, UsbCamera reads the USB camera of the real arm
(SO101_CAMERA_DEVICE, found with `lerobot-find-cameras`). Each one runs in its own
thread: a frame takes 30-150 ms, it must not delay /joint_states.
"""
import os
import threading
import time

import cv2
import numpy as np
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from so101_sim import SO101Sim

CAMERA_FRAME = "external_cam_optical_frame"


class _Camera:
    """Publishes the frames of _read() on /external_cam/image_raw at `hz`, in a thread."""

    def __init__(self, node: Node, hz: float, encoding: str):
        self._node = node
        self._hz = hz
        self._encoding = encoding
        self._image_pub = node.create_publisher(Image, "/external_cam/image_raw", 1)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _read(self) -> np.ndarray | None:
        raise NotImplementedError

    def _publish(self, image: Image):
        self._image_pub.publish(image)

    def _loop(self):
        bridge = CvBridge()
        next_frame = time.monotonic()
        while not self._stop.wait(max(0.0, next_frame - time.monotonic())):
            next_frame += 1.0 / self._hz
            try:
                frame = self._read()
            except Exception as error:  # e.g. no OpenGL for MuJoCo: say it, instead of an empty topic
                self._node.get_logger().error(f"Camera stopped, /external_cam/image_raw stays empty: {error!r}")
                return
            if frame is None:
                continue
            image = bridge.cv2_to_imgmsg(frame, encoding=self._encoding)
            image.header.stamp = self._node.get_clock().now().to_msg()
            image.header.frame_id = CAMERA_FRAME
            try:
                self._publish(image)
            except Exception:  # ROS context already shut down (Ctrl-C)
                return


class SimCamera(_Camera):
    """MuJoCo camera at 10 Hz, with its /external_cam/camera_info."""

    def __init__(self, node: Node, robot: SO101Sim):
        super().__init__(node, hz=10.0, encoding="rgb8")
        self._robot = robot
        self._camera_info_pub = node.create_publisher(CameraInfo, "/external_cam/camera_info", 1)
        K = robot.get_camera_intrinsics()
        self._camera_info = CameraInfo(
            width=robot.camera_width,
            height=robot.camera_height,
            distortion_model="plumb_bob",
            d=[0.0] * 5,
            k=[float(v) for v in K.flatten()],
            r=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
            p=[float(v) for v in K[0]] + [0.0] + [float(v) for v in K[1]] + [0.0] + [float(v) for v in K[2]] + [0.0],
        )
        self._camera_info.header.frame_id = CAMERA_FRAME
        self._thread.start()

    def _read(self) -> np.ndarray:
        # shortcut: renders while the driver steps the physics; fine for a camera image.
        return self._robot.render_camera()

    def _publish(self, image: Image):
        super()._publish(image)
        self._camera_info.header.stamp = image.header.stamp
        self._camera_info_pub.publish(self._camera_info)


class UsbCamera(_Camera):
    """USB camera at 30 Hz. No camera_info: its intrinsics come from your own calibration."""

    def __init__(self, node: Node):
        super().__init__(node, hz=30.0, encoding="bgr8")
        device = os.environ.get("SO101_CAMERA_DEVICE", "0")  # index, or /dev/videoN on Linux
        self._capture = cv2.VideoCapture(int(device) if device.isdigit() else device)
        if not self._capture.isOpened():
            node.get_logger().error(f"Camera {device} not available: set SO101_CAMERA_DEVICE (see README, Real arm)")
            return
        node.get_logger().info(f"Camera {device} opened")
        self._thread.start()

    def stop(self):
        super().stop()
        self._capture.release()

    def _read(self) -> np.ndarray | None:
        ok, frame = self._capture.read()
        return frame if ok else None
