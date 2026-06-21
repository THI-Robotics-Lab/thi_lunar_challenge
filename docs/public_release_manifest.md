# Public Release Manifest

This manifest is allowlist-first. If a file or directory is not listed here, it
should be treated as private by default.

## PUBLIC RELEASE KEEP

- `README.md`
- docs needed for public users
- `Dockerfile` and setup docs
- `ros2_ws/src/rover_description/`
- `ros2_ws/src/rover_gazebo/`
- `ros2_ws/src/rover_autonomy/`
- `ros2_ws/src/remote_control/` if used
- scripts needed for participant and demo launch
- `scripts/generate_luna_scene_01_assets.py`
- `scripts/generate_luna_scene_02_assets.py`
- `scripts/world_generation/luna_2d_map_editor.svg`
- `scripts/world_generation/world02.csv`
- `ros2_ws/src/rover_gazebo/assets/luna/rock/*`
- final published `competition_luna_scene_XX.sdf` files

## PRIVATE ONLY / DO NOT RELEASE BY DEFAULT

- `outputs/`
- `.venv/`
- `build/`
- `install/`
- `log/`
- `ros2_ws/build/`
- `ros2_ws/install/`
- `ros2_ws/log/`
- `__pycache__/`
- `*.pyc`
- `*.Zone.Identifier`
- unreleased world CSVs
- unreleased tasks and scoring docs
- internal notes
- debug screenshots
- probe worlds and probe scripts unless explicitly promoted

## Release Boundary Rule

Anything not explicitly listed in the public keep set is private-only until it
is intentionally promoted and validated for release.
