#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

scripts/start_gazebo_container.sh
exec scripts/exec_in_gazebo_container.sh --user bash -lc '
  set -Eeo pipefail
  source /opt/ros/jazzy/setup.bash
  if [ -f /workspace/thirover/ros2_ws/install/setup.bash ]; then
    source /workspace/thirover/ros2_ws/install/setup.bash
  fi
  exec ros2 run rover_gazebo rover_remote_control --ros-args -p use_sim_time:=true
'
