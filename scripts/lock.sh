#!/usr/bin/env bash
#
# Regenerates the locked */requirements.txt files from */requirements.in
# using uv. Resolution always targets x86_64 Linux (the platform the Docker
# images run on) via uv's `--python-platform` flag, so the lock is identical
# regardless of the host OS (Windows/macOS/Linux).
#
# Prefers a locally installed `uv` (no Docker needed); falls back to running
# uv inside a Linux container when only Docker is available.
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

# Resolution flags. `--python-platform` is what keeps the lock Linux-correct
# even when uv runs on a Windows/macOS host, making Docker optional.
UV_ARGS=(
  --python-version 3.11
  --python-platform x86_64-unknown-linux-gnu
  --generate-hashes
  --no-header
  # Trust the OS certificate store too (needed behind corporate proxies that
  # MITM TLS with a custom root CA); harmless on networks without one.
  --system-certs
)

run_compile() {  # $1 = part (backend|frontend)
  local in="$1/requirements.in" out="$1/requirements.txt"
  if command -v uv >/dev/null 2>&1; then
    uv pip compile "$in" --output-file "$out" "${UV_ARGS[@]}"
  elif command -v docker >/dev/null 2>&1; then
    MSYS_NO_PATHCONV=1 docker run --rm -v "${HOST_PWD}:/w" -w /w "$UV_IMAGE" \
      uv pip compile "$in" --output-file "$out" "${UV_ARGS[@]}"
  else
    echo "Erro: instale 'uv' (pip install uv) ou Docker para gerar o lock." >&2
    exit 1
  fi
}

for part in backend frontend; do
  echo ">> Locking ${part}/requirements.txt from ${part}/requirements.in"
  run_compile "$part"
done

echo
echo "Locks regenerated. Review the diff, then rebuild:"
echo "  docker compose build"
