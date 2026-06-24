#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"
image="${THIROVER_GZ_IMAGE:-ghcr.io/turnwald/thirover-gz-jazzy-gui:latest}"
legacy_image="${THIROVER_GZ_LEGACY_IMAGE:-thirover-gz-jazzy-gui:latest}"
base_image="${THIROVER_GZ_BASE_IMAGE:-unfrobotics/docker-ros2-jazzy-gz-rviz2:latest}"
display_value="${DISPLAY:-:0}"
wayland_display="wayland-0"
# Detect platform and set appropriate WSL variables
if [[ -d "/mnt/wslg" ]]; then
  xdg_runtime_dir="/mnt/wslg/runtime-dir"
  mesa_adapter="${MESA_D3D12_DEFAULT_ADAPTER_NAME:-NVIDIA}"
else
  xdg_runtime_dir="${XDG_RUNTIME_DIR:-/tmp/runtime}"
  mesa_adapter="${MESA_D3D12_DEFAULT_ADAPTER_NAME:-}"
fi

required_mounts=(
  "/workspace/thirover"
  "/tmp/.X11-unix"
  "/dev"
)
if [[ -d "/mnt/wslg" ]]; then
  required_mounts+=("/mnt/wslg")
  required_mounts+=("/usr/lib/wsl")
fi

container_id="$(docker ps -aq --filter "name=^/${container_name}$")"

if ! docker image inspect "${image}" >/dev/null 2>&1; then
  if docker pull "${image}" >/dev/null 2>&1; then
    :
  elif docker image inspect "${legacy_image}" >/dev/null 2>&1; then
    docker tag "${legacy_image}" "${image}"
  elif docker image inspect "${base_image}" >/dev/null 2>&1; then
    docker tag "${base_image}" "${image}"
  fi
fi

if [[ -n "${container_id}" ]]; then
  existing_image="$(docker inspect --format '{{.Config.Image}}' "${container_name}")"
  if [[ "${existing_image}" != "${image}" && "${existing_image}" != "${legacy_image}" ]]; then
    echo "Existing container ${container_name} uses image ${existing_image}, but this run expects ${image}."
    echo "Docker cannot change an existing container image in place."
    echo
    echo "Recreate it with:"
    echo "  docker rm -f ${container_name}"
    echo "  ${BASH_SOURCE[0]}"
    exit 1
  fi

  missing_mounts=()
  for mount_point in "${required_mounts[@]}"; do
    if ! docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "${container_name}" | grep -Fxq "${mount_point}"; then
      missing_mounts+=("${mount_point}")
    fi
  done

  if (( ${#missing_mounts[@]} > 0 )); then
    echo "Existing container ${container_name} is missing required mounts:"
    printf '  %s\n' "${missing_mounts[@]}"
    echo
    echo "Recreate it with:"
    echo "  docker rm -f ${container_name}"
    echo "  ${BASH_SOURCE[0]}"
    exit 1
  fi

  x11_source="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/tmp/.X11-unix"}}{{.Source}}{{end}}{{end}}' "${container_name}")"
  if [[ "${x11_source}" != "/tmp/.X11-unix" ]]; then
    echo "Existing container ${container_name} mounts ${x11_source} at /tmp/.X11-unix."
    echo "The rndmpc ROS/Gazebo pattern mounts host /tmp/.X11-unix directly."
    echo
    echo "Recreate it with:"
    echo "  docker rm -f ${container_name}"
    echo "  ${BASH_SOURCE[0]}"
    exit 1
  fi

  if ! docker ps --format '{{.Names}}' | grep -Fxq "${container_name}"; then
    docker start "${container_name}" >/dev/null
  fi

  echo "Gazebo/RViz GUI container is running: ${container_name}"
  exit 0
fi

echo "Starting Gazebo/RViz GUI container: ${container_name}"
echo "Image: ${image}"
if [[ "${image}" != "${base_image}" ]]; then
  echo "Base image: ${base_image}"
fi
echo "DISPLAY=${display_value}"
echo "WAYLAND_DISPLAY=${wayland_display}"
echo "XDG_RUNTIME_DIR=${xdg_runtime_dir}"
echo "QT_QPA_PLATFORM=xcb"
echo "MESA_D3D12_DEFAULT_ADAPTER_NAME=${mesa_adapter}"

docker run -d \
  --name "${container_name}" \
  --privileged \
  --network host \
  -e DISPLAY="${display_value}" \
  -e WAYLAND_DISPLAY="${wayland_display}" \
  -e XDG_RUNTIME_DIR="${xdg_runtime_dir}" \
  -e QT_QPA_PLATFORM=xcb \
  -e QT_X11_NO_MITSHM=1 \
  -e MESA_D3D12_DEFAULT_ADAPTER_NAME="${mesa_adapter}" \
  -e LD_LIBRARY_PATH="/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v /dev:/dev \
  -v "${repo_root}:/workspace/thirover" \
  -w /workspace/thirover \
  "${image}" \
  bash -lc 'trap : TERM INT; sleep infinity & wait' >/dev/null

echo "Gazebo/RViz GUI container is running: ${container_name}"
