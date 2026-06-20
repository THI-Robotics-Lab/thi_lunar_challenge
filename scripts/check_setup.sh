#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${THIROVER_GZ_IMAGE:-ghcr.io/turnwald/thirover-gz-jazzy-gui:latest}"
legacy_image="${THIROVER_GZ_LEGACY_IMAGE:-thirover-gz-jazzy-gui:latest}"

echo "repo root: ${repo_root}"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not available on PATH" >&2
  exit 1
fi
echo "docker: $(docker --version)"

if docker compose version >/dev/null 2>&1; then
  echo "compose: $(docker compose version)"
else
  echo "compose: not required for the Gazebo/Jazzy workflow"
fi

if docker image inspect "${image}" >/dev/null 2>&1; then
  echo "gazebo image: ${image} present"
elif docker image inspect "${legacy_image}" >/dev/null 2>&1; then
  echo "gazebo image: legacy local tag ${legacy_image} present"
else
  echo "gazebo image: ${image} not found locally"
  echo "The start script will try to pull it from GHCR, then fall back to THIROVER_GZ_BASE_IMAGE if that base image is present."
fi

echo "DISPLAY: ${DISPLAY:-<not set>}"
echo "WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-<not set>}"
echo "XDG_RUNTIME_DIR: ${XDG_RUNTIME_DIR:-<not set>}"
echo "PULSE_SERVER: ${PULSE_SERVER:-<not set>}"

if [[ -d /mnt/wslg ]]; then
  echo "WSLg: /mnt/wslg present"
else
  echo "WSLg: /mnt/wslg not present; GUI may need local X/Wayland setup"
fi

if [[ -S /tmp/.X11-unix/X0 || -n "${DISPLAY:-}" ]]; then
  echo "X11: display socket or DISPLAY appears available"
else
  echo "X11: not detected; headless Gazebo validation does not require it"
fi
