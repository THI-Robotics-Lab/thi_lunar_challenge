#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

image="${THIROVER_GZ_IMAGE:-ghcr.io/turnwald/thirover-gz-jazzy-gui:latest}"

docker build -t "${image}" -f Dockerfile .
echo "Built image: ${image}"
