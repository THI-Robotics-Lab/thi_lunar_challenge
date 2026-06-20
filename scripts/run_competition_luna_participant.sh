#!/usr/bin/env bash
set -Eeuo pipefail

world="01"
gui="true"
rviz="true"
csv_override=""
regen_mode="auto"
build_mode="auto"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --world)
      world="${2:?missing value for --world}"
      shift 2
      ;;
    --csv)
      csv_override="${2:?missing value for --csv}"
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
    --regen)
      regen_mode="${2:?missing value for --regen}"
      shift 2
      ;;
    --build)
      build_mode="${2:?missing value for --build}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/run_competition_luna_participant.sh [--world 01] [--csv PATH] [--gui true|false] [--rviz true|false] [--regen auto|always|never] [--build auto|always|never]

Defaults: --world 01 --gui true --rviz true --regen auto --build auto
Auto-generates scene 01 directly or scene N from a matching CSV before launching Gazebo.
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

if [[ "$regen_mode" != "auto" && "$regen_mode" != "always" && "$regen_mode" != "never" ]]; then
  echo "Regen mode must be auto, always, or never." >&2
  exit 2
fi

if [[ "$build_mode" != "auto" && "$build_mode" != "always" && "$build_mode" != "never" ]]; then
  echo "Build mode must be auto, always, or never." >&2
  exit 2
fi

world_padded="$(printf '%02d' "$((10#$world))")"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

scene_world="${repo_root}/ros2_ws/src/rover_gazebo/worlds/competition_luna_scene_${world_padded}.sdf"
scene_output_dir="${repo_root}/outputs/competition_luna_scene_${world_padded}/terrain"
scene_csv="${csv_override:-${repo_root}/scripts/world_generation/world${world_padded}.csv}"
terrain_name="lunar_scene_${world_padded}_terrain"
terrain_obj="${scene_output_dir}/${terrain_name}.obj"
terrain_mtl="${scene_output_dir}/${terrain_name}.mtl"
install_setup="${repo_root}/ros2_ws/install/setup.bash"
rock_src_root="${repo_root}/ros2_ws/src/rover_gazebo/assets/luna/rock"
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

need_regen="false"
if [[ "$regen_mode" == "always" ]]; then
  need_regen="true"
elif [[ ! -f "${scene_world}" || ! -f "${terrain_obj}" || ! -f "${terrain_mtl}" ]]; then
  if [[ "$regen_mode" == "never" ]]; then
    echo "Regen mode is never, but required files are missing:" >&2
    [[ -f "${scene_world}" ]] || echo "  missing world: ${scene_world}" >&2
    [[ -f "${terrain_obj}" ]] || echo "  missing terrain OBJ: ${terrain_obj}" >&2
    [[ -f "${terrain_mtl}" ]] || echo "  missing terrain MTL: ${terrain_mtl}" >&2
    exit 1
  fi
  need_regen="true"
fi

echo "Selected world: ${world_padded}"
echo "Selected CSV: ${scene_csv}"
echo "Regen mode: ${regen_mode} (${need_regen})"
echo "Build mode: ${build_mode}"
echo "GUI mode: ${gui}"
echo "RViz mode: ${rviz}"

if [[ "$need_regen" == "true" ]]; then
  echo "Running generator for world ${world_padded}."
  if [[ "$world_padded" == "01" ]]; then
    python3 scripts/generate_luna_scene_01_assets.py \
      --output-dir "${scene_output_dir}" \
      --world "${scene_world}"
  else
    python3 scripts/generate_luna_scene_02_assets.py \
      --scene-id "${world_padded}" \
      --map-csv "${scene_csv}" \
      --output-dir "${scene_output_dir}" \
      --world "${scene_world}" \
      --world-name "competition_luna_scene_${world_padded}"
  fi
else
  echo "Skipping generation; required world and terrain files already exist."
fi

world_file="${scene_world}"
if [[ ! -f "${world_file}" ]]; then
  echo "World file not found: ${world_file}" >&2
  exit 1
fi

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"

asset_dst_root="/tmp/thirover_scene_${world_padded}_assets"
rock_dst_root="${asset_dst_root}/object/rock"
terrain_dst_root="${asset_dst_root}/terrain"
terrain_name="lunar_scene_${world_padded}_terrain"

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

build_command='
  set -Eeo pipefail
  cd /workspace/thirover/ros2_ws
  source /opt/ros/jazzy/setup.bash
  colcon build --symlink-install --packages-select rover_description rover_gazebo rover_autonomy
'

for asset in \
  "${terrain_obj}" \
  "${terrain_mtl}"; do
  if [[ ! -f "${asset}" ]]; then
    echo "Required world asset not found: ${asset}" >&2
    exit 1
  fi
done

need_build="false"
if [[ "$build_mode" == "always" ]]; then
  need_build="true"
elif [[ "$build_mode" == "auto" && ! -f "${install_setup}" ]]; then
  need_build="true"
elif [[ "$build_mode" == "never" && ! -f "${install_setup}" ]]; then
  echo "Build mode is never, but install/setup.bash is missing: ${install_setup}" >&2
  exit 1
fi

scripts/start_gazebo_container.sh
if docker exec "${container_name}" pgrep -f 'gz sim' >/dev/null; then
  echo "Gazebo is already running in ${container_name}; stop it before starting another world." >&2
  exit 1
fi
docker exec "${container_name}" bash -lc "mkdir -p '${rock_dst_root}' '${terrain_dst_root}'"
docker cp "${rock_src_root}/apollo_sample20.glb" "${container_name}:${rock_dst_root}/apollo_sample20.glb"
docker cp "${rock_src_root}/lunalab_boulder1.glb" "${container_name}:${rock_dst_root}/lunalab_boulder1.glb"
docker cp "${terrain_obj}" "${container_name}:${terrain_dst_root}/${terrain_name}.obj"
docker cp "${terrain_mtl}" "${container_name}:${terrain_dst_root}/${terrain_name}.mtl"

if [[ "$need_build" == "true" ]]; then
  echo "Build will run."
else
  echo "Build will skip."
fi
if [[ "$need_build" == "true" ]]; then
  echo "Running colcon build."
  scripts/exec_in_gazebo_container.sh --user bash -lc "${build_command}"
else
  echo "Skipping colcon build."
fi

if [[ -n "${THIROVER_GZ_TIMEOUT:-}" ]]; then
  exec scripts/exec_in_gazebo_container.sh --user \
    timeout --signal=INT --kill-after=10s "${THIROVER_GZ_TIMEOUT}" \
    bash -lc "${launch_command}"
fi

exec scripts/exec_in_gazebo_container.sh --user bash -lc "${launch_command}"
