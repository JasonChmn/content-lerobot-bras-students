# SO-ARM101 Pick and Place

This project implements a fully automated pick-and-place pipeline for the SO-ARM101 robotic arm. It uses ROS 2 (Jazzy) and operates across two Docker containers. The system is designed to work in both a MuJoCo-based simulation (`so101_sim`) and on the real physical hardware.

## Project Structure

The architecture is divided into three main ROS 2 nodes, ensuring separation of concerns between hardware control, computer vision, and robot logic:

1. **`driver_node` (Control Container)**

   * **Role:** The hardware abstraction layer. It connects to either the MuJoCo simulation or the physical arm depending on the `USE_SIM` environment variable.

   * **I/O:** Publishes robot joint states (`/joint_states`) and the camera feed (`/external_cam/image_raw`). Listens for movement commands on `/joint_command`.

2. **`perception_node` (Perception Container)**

   * **Role:** The vision system. It subscribes to the camera feed, segments the red hollow cube using HSV color masking, and calculates the center of the object.

   * **I/O:** Uses the camera's intrinsic (`K`) and extrinsic matrices to project the 2D pixel coordinates into 3D world space (intersecting the $Z=0.025$ plane), publishing the result to `/object_position`.

3. **`brain_node` (Control Container)**

   * **Role:** The intelligence and logic. It calculates Forward and Inverse Kinematics (IK) using the **Pinocchio** library to determine how to move the arm's joints to reach a specific 3D coordinate.

   * **I/O:** Runs a time-based state machine (Hover $\rightarrow$ Descend $\rightarrow$ Grasp $\rightarrow$ Lift $\rightarrow$ Move $\rightarrow$ Release $\rightarrow$ Home). It waits in `IDLE` until triggered by a ROS 2 service call.

## Docker Setup & Usage

### 1. Prerequisites

* Docker and Docker Compose installed.

* Ensure you have run `xhost +local:docker` on your host machine if you intend to use RViz2 for visualization (requires X11 forwarding).

### 2. Configuration

Before starting, ensure your `.env` file in the `docker/` directory is configured properly for your target backend:

```
# Set to true for MuJoCo simulation, false for real hardware
USE_SIM=true

```

### 3. Build and Launch

Build the Docker images if it wasn’t done already (this installs ROS 2, Pinocchio, and necessary dependencies):

```
docker compose build

```

Start the network and containers. This will launch the driver, perception, and brain nodes, along with RViz for visualization:

```
docker compose up -d

```

### 4. Triggering the Pick and Place Sequence

By default, the `brain_node` boots into an `IDLE` state. It will process camera data but will not move the arm until it receives a manual start command.

Open a **new terminal** and attach to the running control container:

```
docker compose exec control bash

```

Source the workspace (if not automatically sourced in your `.bashrc`) and call the start service:

```
source /opt/ros/jazzy/setup.bash && source /ros2_ws/install/setup.bash
ros2 service call /brain/start std_srvs/srv/Trigger

```

The robot will now execute the pick and place sequence. You can stop it at any time (forcing it to return to IDLE after its current sequence) by calling:

```
ros2 service call /brain/stop std_srvs/srv/Trigger

```

## Developing and Rebuilding

If you make changes to the Python nodes, you will need to rebuild the specific package inside the container and restart it. For example, if you modify the brain node:

```
docker compose exec control bash -lc "cd /ros2_ws && colcon build --packages-select so101_brain"
docker compose restart control

```
