#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

launch_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  if [ -f install/setup.bash ]; then
    source install/setup.bash
  fi
  set -u
  exec ros2 launch rover_gazebo gazebo_rover_gui_rviz_rays.launch.py
'

build_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install --packages-select rover_gazebo rover_autonomy
'

scripts/start_gazebo_container.sh
scripts/exec_in_gazebo_container.sh --user bash -lc "${build_command}"

if [[ -n "${THIROVER_GZ_TIMEOUT:-}" ]]; then
  exec scripts/exec_in_gazebo_container.sh --user \
    timeout --signal=INT --kill-after=10s "${THIROVER_GZ_TIMEOUT}" \
    bash -lc "${launch_command}"
fi

exec scripts/exec_in_gazebo_container.sh --user bash -lc "${launch_command}"
