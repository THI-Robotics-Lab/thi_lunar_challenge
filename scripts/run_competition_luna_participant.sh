#!/usr/bin/env bash
set -Eeuo pipefail

world="01"
gui="true"
rviz="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --world)
      world="${2:?missing value for --world}"
      shift 2
      ;;
    --gui)
      gui="${2:?missing value for --gui}"
      shift 2
      ;;
    --rviz)
      rviz="${2:?missing value for --rviz}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/run_competition_luna_participant.sh [--world 01] [--gui true|false] [--rviz true|false]

Defaults: --world 01 --gui true --rviz true
Launches Gazebo with the specified competition world using existing release assets.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if ! [[ "$world" =~ ^[0-9]+$ ]]; then
  echo "World must be a numeric identifier such as 01." >&2
  exit 2
fi

if [[ "$gui" != "true" && "$gui" != "false" ]]; then
  echo "GUI must be true or false." >&2
  exit 2
fi

if [[ "$rviz" != "true" && "$rviz" != "false" ]]; then
  echo "RViz must be true or false." >&2
  exit 2
fi

world_padded="$(printf '%02d' "$((10#$world))")"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

scene_world="${repo_root}/ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_${world_padded}.sdf"
rock_src_root="${repo_root}/ros2_ws/src/rover_gazebo/assets/luna/rock"
sky_src_root="${repo_root}/ros2_ws/src/rover_gazebo/meshes/world"
required_assets=(
  "${rock_src_root}/apollo_sample20.glb"
  "${rock_src_root}/apollo_sample20.bbox.json"
  "${rock_src_root}/lunalab_boulder1.glb"
  "${rock_src_root}/lunalab_boulder1.bbox.json"
)

for asset in "${required_assets[@]}"; do
  if [[ ! -f "${asset}" ]]; then
    echo "Required tracked rock asset not found: ${asset}" >&2
    exit 1
  fi
done

if [[ ! -f "${scene_world}" ]]; then
  echo "World file not found: ${scene_world}" >&2
  exit 1
fi

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"

world_path="/workspace/thirover/ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_${world_padded}.sdf"

launch_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  if [ -f install/setup.bash ]; then
    source install/setup.bash
  fi
  set -u
  exec ros2 launch rover_gazebo gazebo_rover.launch.py gui:='"${gui}"' world:='"${world_path}"' camera_bridge:=true rviz:='"${rviz}"'
'

scripts/start_gazebo_container.sh
if docker exec "${container_name}" pgrep -f 'gz sim' >/dev/null; then
  echo "Gazebo is already running in ${container_name}; stop it before starting another world." >&2
  exit 1
fi

exec scripts/exec_in_gazebo_container.sh --user bash -lc "${launch_command}"
