# Architecture

ThiRover currently provides a compact ROS 2 Jazzy + Gazebo Sim rover stack under `ros2_ws/src`.

## Packages

- `rover_description`: xacro/URDF for the student rover.
- `rover_gazebo`: Gazebo world, launch file, controller config, and small relay nodes.

## Geometry Convention

- `x`: forward
- `y`: left
- `z`: up

## Container

- Image: `thirover-gz-jazzy-gui:latest`
- Container: `thirover_gz_jazzy_gui`
- Repository mount: `/workspace/thirover`
- ROS workspace: `/workspace/thirover/ros2_ws`
- ROS distribution: Jazzy
- Gazebo Sim: `gz sim`

## Simulation Stack

The launch file starts Gazebo, publishes `robot_description`, spawns the rover from xacro, and activates:

- `joint_state_broadcaster`
- `diff_drive_controller`
- `leg_position_controller`

`cmd_vel_relay` maps public `/cmd_vel` to the diff-drive controller input. `odom_relay` maps `/diff_drive_controller/odom` to the conventional `/odom` topic.

## Current Boundary

This setup intentionally stays focused on a first usable rover simulation. It does not add Nav2, SLAM, mapping, perception, terrain assets, CAD meshes, hardware code, or rover variants.
