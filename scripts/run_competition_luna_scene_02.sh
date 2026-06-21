#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"
rock_src_root="${repo_root}/ros2_ws/src/rover_gazebo/assets/luna/rock"
sky_src_root="${repo_root}/ros2_ws/src/rover_gazebo/meshes/world"
terrain_src_root="${repo_root}/outputs/competition_luna_scene_02/terrain"

asset_dst_root="/tmp/thirover_scene_02_assets"
rock_dst_root="${asset_dst_root}/object/rock"
sky_dst_root="${asset_dst_root}/sky"
terrain_dst_root="${asset_dst_root}/terrain"
sky_dome_name="sky_dome_plain_starfield_no_haze_1.glb"
sky_signature_file="${sky_dst_root}/.${sky_dome_name}.sha256"

launch_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  if [ -f install/setup.bash ]; then
    source install/setup.bash
  fi
  set -u
  exec ros2 launch rover_gazebo gazebo_rover.launch.py gui:=true world:=/workspace/thirover/ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_02.sdf
'

build_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install --packages-select rover_gazebo rover_autonomy
'

scripts/start_gazebo_container.sh
docker exec "${container_name}" bash -lc "mkdir -p '${rock_dst_root}' '${terrain_dst_root}' '${sky_dst_root}'"
docker cp "${rock_src_root}/apollo_sample20.glb" "${container_name}:${rock_dst_root}/apollo_sample20.glb"
docker cp "${rock_src_root}/lunalab_boulder1.glb" "${container_name}:${rock_dst_root}/lunalab_boulder1.glb"
docker cp "${terrain_src_root}/lunar_scene_02_terrain.obj" "${container_name}:${terrain_dst_root}/lunar_scene_02_terrain.obj"
docker cp "${terrain_src_root}/lunar_scene_02_terrain.mtl" "${container_name}:${terrain_dst_root}/lunar_scene_02_terrain.mtl"
sky_signature="$(
  sha256sum "${sky_src_root}/${sky_dome_name}" | awk '{print $1}'
)"
if [[ ! -f "${sky_signature_file}" || "$(docker exec "${container_name}" cat "${sky_signature_file}" 2>/dev/null || true)" != "${sky_signature}" ]]; then
  docker cp "${sky_src_root}/${sky_dome_name}" "${container_name}:${sky_dst_root}/${sky_dome_name}"
  docker exec "${container_name}" bash -lc "printf '%s\\n' '${sky_signature}' > '${sky_signature_file}'"
fi
scripts/exec_in_gazebo_container.sh --user bash -lc "${build_command}"

if [[ -n "${THIROVER_GZ_TIMEOUT:-}" ]]; then
  exec scripts/exec_in_gazebo_container.sh --user \
    timeout --signal=INT --kill-after=10s "${THIROVER_GZ_TIMEOUT}" \
    bash -lc "${launch_command}"
fi

exec scripts/exec_in_gazebo_container.sh --user bash -lc "${launch_command}"
