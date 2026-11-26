# Tek5: SO-ARM101 pick & place

Simulation, IK, perception and pick & place on the SO-ARM101 arm, with ROS 2 Jazzy and MuJoCo.
Project spec: [`docs/SUJET.md`](docs/SUJET.md).

## Prerequisites

Install [Pixi](https://pixi.sh) 0.84 or newer (already installed: `pixi self-update`), then open a new terminal.

### macOS, Linux

```bash
curl -fsSL https://pixi.sh/install.sh | sh
```

### Windows

Choose native or WSL2:

| | Native (PowerShell or Command Prompt) | WSL2 (Ubuntu) |
|---|---|---|
| RViz | GPU | CPU, slower |
| Setup | Pixi | `wsl --install -d Ubuntu` (admin), then as Linux |
| Python edits | Need `pixi run build` | Taken into account directly |
| Real arm | `COM` port | USB attached with [usbipd-win](https://learn.microsoft.com/windows/wsl/connect-usb) |

Native, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm -useb https://pixi.sh/install.ps1 | iex"
```

WSL2: in Ubuntu, follow [macOS, Linux](#macos-linux).

## Quickstart

```bash
git clone https://github.com/JasonChmn/content-lerobot-bras-students.git tek5_robotics
cd tek5_robotics
pixi install
pixi run build
pixi run launch --backend sim
```

Windows: clone in a path without spaces (e.g. `C:\tek5_robotics`). WSL2: clone in `~/`, not in `/mnt/c/`.

In a second terminal: `pixi run rviz2`.

## Commands

| Command | |
|---|---|
| `pixi run build` | Build `ros2_ws` |
| `pixi run launch --backend sim` | Build and launch the stack in simulation (default backend) |
| `pixi run launch --backend real --port <port>` | Same stack on the real arm |
| `pixi run rviz2` | RViz with `ros2_ws/so101.rviz` |
| `pixi shell` | Shell with ROS 2 and the workspace sourced |
| `pixi run ros2 <args>` | Any ROS 2 command |
| `pixi run doctor` | Check the setup, with the fix for each problem |
| `pixi run clean` | Delete `ros2_ws/build install log` |
| `pixi add <pkg>`, `pixi add --pypi <pkg>` | Add a dependency, commit `pixi.toml` and `pixi.lock` |

`launch` runs `ros2_ws/src/so101_bringup/launch/so101.launch.py`: add your nodes' launch files there.

## RViz

`pixi run rviz2` shows a grid and the simulation camera (`/external_cam/image_raw`). To display the arm:

1. **Add** → **RobotModel**.
2. **Description Topic**: `/robot_description`.
3. **File** → **Save Config**.

The arm stays "in pieces" until `driver_node` publishes `/joint_states`.

## Real arm

In a `pixi shell`, use `lerobot-find-port`, `lerobot-calibrate` and `lerobot-find-cameras` as in the [LeRobot SO-101 guide](https://huggingface.co/docs/lerobot/main/en/so101) (`--robot.type=so101_follower`). Then copy `.env.example` to `.env`, fill in the port, the calibration file and the camera, and:

```bash
pixi run doctor                    # checks them
pixi run launch --backend real
```

- **Linux**: `sudo usermod -aG dialout $USER`, then log out and back in. Use the port's stable name from `ls -l /dev/serial/by-id/`: `/dev/ttyACM0` can change when you plug the arms in another order. Another way to find the port, watch it appear when you plug the USB cable:
  `sudo udevadm monitor --subsystem-match=tty --property | grep --line-buffered -E "(DEVNAME=|ACTION=)"`
- **WSL2**: attach the USB device with [usbipd-win](https://learn.microsoft.com/windows/wsl/connect-usb).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ros2 topic list` does not see your nodes | Start each terminal with `pixi run` or `pixi shell` |
| Windows: odd `colcon` or `ros2` errors | Move the repo to a short path without spaces, e.g. `C:\tek5_robotics` |
| Windows: Python edit not taken into account | `pixi run build` (no symlinks on Windows) |
| Windows: firewall popup for `python.exe` | Cancel: ROS 2 only talks on your machine |
| WSL2: RViz is slow | CPU by default. GPU: `GALLIUM_DRIVER=d3d12 pixi run rviz2` (drop it if the view is empty) |
