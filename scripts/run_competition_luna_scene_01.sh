#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"
rock_src_root="${repo_root}/ros2_ws/src/rover_gazebo/assets/luna/rock"
terrain_src_root="${repo_root}/outputs/competition_luna_scene_01/terrain"

asset_dst_root="/tmp/thirover_scene_01_assets"
rock_dst_root="${asset_dst_root}/object/rock"
terrain_dst_root="${asset_dst_root}/terrain"

launch_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  if [ -f install/setup.bash ]; then
    source install/setup.bash
  fi
  set -u
  exec ros2 launch rover_gazebo gazebo_rover.launch.py gui:=true world:=/workspace/thirover/ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_01.sdf
'

build_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install --packages-select rover_gazebo rover_autonomy
'

scripts/start_gazebo_container.sh
docker exec "${container_name}" bash -lc "mkdir -p '${rock_dst_root}' '${terrain_dst_root}'"
docker cp "${rock_src_root}/apollo_sample20.glb" "${container_name}:${rock_dst_root}/apollo_sample20.glb"
docker cp "${rock_src_root}/lunalab_boulder1.glb" "${container_name}:${rock_dst_root}/lunalab_boulder1.glb"
docker cp "${terrain_src_root}/lunar_scene_01_terrain.obj" "${container_name}:${terrain_dst_root}/lunar_scene_01_terrain.obj"
docker cp "${terrain_src_root}/lunar_scene_01_terrain.mtl" "${container_name}:${terrain_dst_root}/lunar_scene_01_terrain.mtl"
scripts/exec_in_gazebo_container.sh --user bash -lc "${build_command}"

if [[ -n "${THIROVER_GZ_TIMEOUT:-}" ]]; then
  exec scripts/exec_in_gazebo_container.sh --user \
    timeout --signal=INT --kill-after=10s "${THIROVER_GZ_TIMEOUT}" \
    bash -lc "${launch_command}"
fi

exec scripts/exec_in_gazebo_container.sh --user bash -lc "${launch_command}"
