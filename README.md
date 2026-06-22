# ThiRover

ROS 2 Jazzy + Gazebo rover simulation stack for the THI rover project.

The public image is:

```text
ghcr.io/turnwald/thirover-gz-jazzy-gui:latest
```

## What this repository provides

This repository provides a complete simulation environment for the THI Lunar Rover Challenge. Students can:
- Clone and run the simulation
- Start Gazebo and RViz
- Start remote control
- Implement their own autonomy algorithms

## Requirements

- Docker
- WSL2 (Windows) or Linux
- ROS 2 Jazzy + Gazebo Sim

## Quick Start

1. Clone repo
```bash
git clone https://github.com/THI-Robotics-Lab/thi_lunar_challenge.git thi_lunar_challenge
cd thi_lunar_challenge
```

2. Start competition participant (with world selection)
```bash
./scripts/run_competition_luna_participant.sh
```

3. Start remote control
```bash
./scripts/run_gazebo_rover_remote_control.sh
```

## Write your own algorithm

Edit the odometry-only baseline here:
```text
ros2_ws/src/rover_autonomy/rover_autonomy/autonomy_controller.py
```

Edit the LiDAR-based example here (if present):
```text
ros2_ws/src/rover_autonomy/rover_autonomy/lidar_control.py
```

Look for:
```text
WRITE YOUR ALGORITHM HERE
```

## Useful ROS topics

- `/odom` - Rover odometry data
- `/scan` - Laser scan data
- `/front_camera` - Front camera feed
- `/cmd_vel` - Velocity commands to rover

## Troubleshooting / further docs

See remaining student-facing documentation in the `docs/` directory.