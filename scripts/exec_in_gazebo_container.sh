#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"
mode="user"
software_gl="${THIROVER_GZ_SOFTWARE_GL:-0}"

if [[ "${1:-}" == "--root" ]]; then
  mode="root"
  shift
elif [[ "${1:-}" == "--user" ]]; then
  mode="user"
  shift
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage:
  scripts/exec_in_gazebo_container.sh [--user] [command...]
  scripts/exec_in_gazebo_container.sh --root [command...]

Runs a command inside the long-lived thirover Gazebo/RViz GUI container.
Default mode uses the host UID/GID; --root uses root for system GUI smoke.
EOF
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -Fxq "${container_name}"; then
  echo "Container ${container_name} is not running."
  echo "Start it first with: scripts/start_gazebo_container.sh"
  exit 1
fi

if (( $# == 0 )); then
  set -- bash
fi

docker_tty=()
if [[ -t 0 && -t 1 ]]; then
  docker_tty=(-it)
fi

gl_env=()
if [[ "${software_gl}" == "1" || "${software_gl}" == "true" || "${software_gl}" == "yes" ]]; then
  gl_env=(
    -e LIBGL_ALWAYS_SOFTWARE=1
    -e MESA_LOADER_DRIVER_OVERRIDE=swrast
    -e QT_OPENGL=software
  )
fi

if [[ "${mode}" == "root" ]]; then
  home_dir="/tmp/thirover-root"
  runtime_dir="${home_dir}/runtime"
  docker exec "${container_name}" bash -lc "mkdir -p '${home_dir}' '${runtime_dir}' && chmod 700 '${runtime_dir}'"
  exec docker exec "${docker_tty[@]}" \
    "${gl_env[@]}" \
    -e HOME="${home_dir}" \
    -e XDG_RUNTIME_DIR="${runtime_dir}" \
    "${container_name}" \
    bash -lc 'set -Eeo pipefail; source /opt/ros/jazzy/setup.bash; set -u; mkdir -p "$HOME"; cd /workspace/thirover; exec "$@"' \
    bash "$@"
fi

host_uid="$(id -u)"
host_gid="$(id -g)"
home_dir="/tmp/thirover-user-${host_uid}"
runtime_dir="${home_dir}/runtime"

docker exec "${container_name}" bash -lc "mkdir -p '${home_dir}' '${runtime_dir}' && chown '${host_uid}:${host_gid}' '${home_dir}' '${runtime_dir}' && chmod 700 '${runtime_dir}'"
exec docker exec "${docker_tty[@]}" \
  "${gl_env[@]}" \
  -u "${host_uid}:${host_gid}" \
  -e HOME="${home_dir}" \
  -e XDG_RUNTIME_DIR="${runtime_dir}" \
  "${container_name}" \
  bash -lc 'set -Eeo pipefail; source /opt/ros/jazzy/setup.bash; set -u; mkdir -p "$HOME"; cd /workspace/thirover; exec "$@"' \
  bash "$@"
