# WSL Docker Setup

This repository targets ROS 2 Jazzy and Gazebo Sim in Docker. The active container is persistent and named `thirover_gz_jazzy_gui`.

## Container Model

The default image tag is `ghcr.io/turnwald/thirover-gz-jazzy-gui:latest`. The start script reuses the existing container, starts it when stopped, and creates it only when missing.

```bash
./scripts/start_gazebo_container.sh
./scripts/gazebo_dev_shell.sh
```

The repository is mounted at `/workspace/thirover`. Build from:

```bash
cd /workspace/thirover/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select rover_description rover_gazebo
source install/setup.bash
```

## GUI Forwarding

The working GUI path uses WSLg/X11 mounts and host networking:

- `DISPLAY=${DISPLAY:-:0}`
- `WAYLAND_DISPLAY=wayland-0`
- `XDG_RUNTIME_DIR=/mnt/wslg/runtime-dir`
- `QT_QPA_PLATFORM=xcb`
- `QT_X11_NO_MITSHM=1`
- `MESA_D3D12_DEFAULT_ADAPTER_NAME=${MESA_D3D12_DEFAULT_ADAPTER_NAME:-NVIDIA}`
- mounts for `/mnt/wslg`, `/tmp/.X11-unix`, `/dev`, `/usr/lib/wsl`, and this repo at `/workspace/thirover`

Run:

```bash
./scripts/run_gazebo_rover_gui.sh
./scripts/run_gazebo_rover_rviz.sh
```

If WSLg shows only a taskbar thumbnail or `WARN:COPY MODE`, try:

```bash
THIROVER_GZ_SOFTWARE_GL=1 ./scripts/run_gazebo_rover_gui.sh
```

If the same command still fails visually, restart WSL from Windows with `wsl --shutdown` and try again.

## Headless Smoke

Use a bounded timeout for CI-style checks:

```bash
THIROVER_GZ_TIMEOUT=45s ./scripts/run_gazebo_rover_headless.sh
```

The helper sends `SIGINT` before killing the launch, which avoids leaving Gazebo servers running inside the persistent container.

Stop or recreate the container:

```bash
docker stop thirover_gz_jazzy_gui
docker rm -f thirover_gz_jazzy_gui
```
