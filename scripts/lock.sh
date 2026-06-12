#!/usr/bin/env bash
#
# Regenerates the locked */requirements.txt files from */requirements.in
# using uv. Resolution runs inside a Linux container so the lock matches the
# platform the Docker images actually run on (x86_64 Linux), regardless of the
# host OS (works the same on Windows/macOS/Linux).
#
# Usage:
#   bash scripts/lock.sh
#
# After it finishes, review the diff and rebuild:
#   docker compose build
#
set -euo pipefail

cd "$(dirname "$0")/.."

UV_IMAGE="ghcr.io/astral-sh/uv:python3.11-bookworm-slim"

# Host path Docker understands. On Git Bash (Windows), `pwd -W` yields C:/...;
# elsewhere plain `pwd` is correct. MSYS_NO_PATHCONV stops Git Bash from
# rewriting the container-side `/w` path.
HOST_PWD="$(pwd -W 2>/dev/null || pwd)"

for part in backend frontend; do
  echo ">> Locking ${part}/requirements.txt from ${part}/requirements.in"
  MSYS_NO_PATHCONV=1 docker run --rm -v "${HOST_PWD}:/w" -w /w "$UV_IMAGE" \
    uv pip compile "${part}/requirements.in" \
      --output-file "${part}/requirements.txt" \
      --python-version 3.11 \
      --python-platform x86_64-unknown-linux-gnu \
      --generate-hashes \
      --no-header
done

echo
echo "Locks regenerated. Review the diff, then rebuild:"
echo "  docker compose build"
