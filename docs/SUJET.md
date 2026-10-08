# Tek5 — SO-ARM101: simulation, IK, perception, pick & place

**Goal:** a camera spots a red cube with holes, the arm picks it up and drops it in a box.
In simulation first, then, even better, on the real robot.
In a second phase, find your own application with this robot arm. It could be anything !

> [!NOTE]
> The sim cube is the same 5 cm printed cube you will use on the real robot.

## What you get

| Item | Where | Role |
|---|---|---|
| `so101-core` | `core/lerobot_min/` | Driver for the **real** arm (`SO101Follower`), extracted from LeRobot (HuggingFace) |
| `so101-sim` | `sim/` | MuJoCo digital twin (`SO101Sim`), **same API** as `SO101Follower` |
| Scene | `sim/so101_sim/assets/so101/scene_tek5.xml` | Arm + object + drop box + fixed external camera |
| URDF | `sim/so101_sim/assets/so101/so101_new_calib.urdf` | For your IK |
| Docker | `docker/` | Two containers, `control` and `perception`, on a shared ROS2 network |
| ROS2 example | `ros2_ws/src/example_py_pkg` | Minimal package. Check inter-container comms with `talker` first |

Common API for both backends:

```python
robot.connect()
obs = robot.get_observation()   # {"shoulder_pan.pos": rad, ..., "gripper.pos": 0-100,
                                #  "external_cam": RGB image (sim only)}
robot.send_action({"shoulder_pan.pos": 0.35, "gripper.pos": 50.0})
robot.disconnect()
```

## What you write

Everything else. At least three ROS2 nodes:

### 1. `driver_node` (control container)
- Instantiates `SO101Sim` **or** `SO101Follower` from a `use_sim` parameter
  (default `true`). The rest of your stack must **never** know which one runs.
- Publishes `/joint_states` (≥20 Hz) and `/external_cam/image_raw` (~10 Hz).
- Subscribes to `/joint_command` (radians, gripper 0-100).

### 2. `perception_node` (perception container)
- Detects the object and the drop box (HSV, YOLO, ArUco… your call, justify it).
- Publishes their 3D positions **in the robot frame** (`/object_position`,
  `/drop_box_position`, 5-10 Hz). Topic names are suggestions.
- The hard part is not detection, it is **pixel → 3D**: you need the intrinsics
  K (`get_camera_intrinsics()`), the camera pose, and an assumption of your own
  (known object size? object on the table?).
- `get_camera_extrinsics()` gives the ground-truth camera pose: fine to unblock
  the other parts, but in the end you need **your own calibration** (as shown
  at the kickoff). On the real robot, nobody hands you that matrix.

### 3. `brain_node` (control container)
- Reads the positions, computes the IK and runs approach → grasp → transport → drop.
- IK method is up to you: `ikpy` and `pinocchio` are good starting points,
  anything else is welcome.
- Explicit state machine. Control **never** blocks waiting for perception
  (use the last known value).

```
        /external_cam/image_raw
   ┌──────────────────────────────────────────┐
   │                                          ▼
┌──────────┐                          ┌──────────────┐
│  driver  │                          │  perception  │
└──────────┘                          └──────┬───────┘
   ▲    │                                    │ /object_position
   │    │                                    │ /drop_box_position
   │    │        /joint_states               ▼
   │    └─────────────────────────────▶┌──────────────┐
   │                                   │    brain     │
   │                                   │ (IK + state) │
   │                                   └──────┬───────┘
   └──────────────────────────────────────────┘
        /joint_command (5 DoF + gripper 0-100)
```

## Rules

- Motor commands go through `/joint_command` only. No direct backend access from
  `brain_node` or `perception_node`.
- `get_object_position()` is **forbidden** in your pipeline (fine in tests, to
  validate your perception).
- Code on Git, with each member's history visible.

## Milestones

- **S4 (mid-term review):** IK works, the arm reaches an arbitrary XYZ (< 1 cm error,
  measured), gripper controllable. Ideally the pick & place should be functional.
- **S7 (final defense):** Robust pick & place in sim (and real robot preferred) + phase 2, the go further project.

## Phase 1 : Pick & Place project

Remote sessions (visio) on perception and on control / kinematics are planned along the way.

The real arm is a bonus on paper, but it is **the whole point of this project**.
Thanks to `use_sim`, it is not much extra work, and a video of a real robot
picking a real cube is far more fun, and worth a lot more on your CV, than any
simulation. Also make a video of your demo with you on it for the final defense.

Split the work in your team, but **every member must understand the whole
pipeline**: camera, calibration, perception, IK, control, ROS2. Even at a basic
level. That end-to-end view is what robotics is about, and what you will need
if you keep going in this field.

## Phase 2 : Go further

Go beyond the pick & place and find your own application.
The only constraint is that you need to use the work made in Phase 1.

Be ambitious ! It does not have to be perfect.
It could be anything: AI for control or perception, LLM, VLM, voice control, imitation learning, RL ...
