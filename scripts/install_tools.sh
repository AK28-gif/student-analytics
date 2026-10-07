#!/usr/bin/env bash
# One-time installation of the system tools this project needs (macOS, Apple Silicon).
# Idempotent: anything already installed is skipped.
#
#   PostgreSQL 16 ...... Homebrew
#   Python 3.11 ........ uv (prebuilt CPython, no compiling)
#   Docker engine ...... Colima + Lima (lightweight VM, no Docker Desktop licence needed)
#   Docker CLI/compose . official prebuilt binaries in ~/.local/bin and ~/.docker/cli-plugins
set -euo pipefail
BIN="$HOME/.local/bin"; PLUG="$HOME/.docker/cli-plugins"
mkdir -p "$BIN" "$PLUG"
export PATH="$BIN:$PATH"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

DOCKER_VERSION=29.8.2; COLIMA_VERSION=0.10.3; LIMA_VERSION=2.2.1; COMPOSE_VERSION=5.6.0; BUILDX_VERSION=0.37.2

echo "==> PostgreSQL 16 + libomp (Homebrew)"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list postgresql@16 >/dev/null 2>&1 || HOMEBREW_NO_AUTO_UPDATE=1 brew install postgresql@16
brew list libomp >/dev/null 2>&1 || HOMEBREW_NO_AUTO_UPDATE=1 brew install libomp

echo "==> uv + Python 3.11"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.11

echo "==> Docker CLI"
if ! command -v docker >/dev/null; then
  curl -sSfL -o "$TMP/docker.tgz" "https://download.docker.com/mac/static/stable/aarch64/docker-${DOCKER_VERSION}.tgz"
  tar -xzf "$TMP/docker.tgz" -C "$TMP" && cp "$TMP/docker/docker" "$BIN/"
fi

echo "==> Colima + Lima"
if ! command -v colima >/dev/null; then
  curl -sSfL -o "$BIN/colima" "https://github.com/abiosoft/colima/releases/download/v${COLIMA_VERSION}/colima-Darwin-arm64"
fi
if ! command -v limactl >/dev/null; then
  curl -sSfL -o "$TMP/lima.tgz" "https://github.com/lima-vm/lima/releases/download/v${LIMA_VERSION}/lima-${LIMA_VERSION}-Darwin-arm64.tar.gz"
  tar -xzf "$TMP/lima.tgz" -C "$HOME/.local"
fi

echo "==> docker compose + buildx plugins"
[ -x "$PLUG/docker-compose" ] || curl -sSfL -o "$PLUG/docker-compose" \
  "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-darwin-aarch64"
[ -x "$PLUG/docker-buildx" ] || curl -sSfL -o "$PLUG/docker-buildx" \
  "https://github.com/docker/buildx/releases/download/v${BUILDX_VERSION}/buildx-v${BUILDX_VERSION}.darwin-arm64"

chmod +x "$BIN"/docker "$BIN"/colima "$PLUG"/* 2>/dev/null || true
xattr -dr com.apple.quarantine "$BIN" "$PLUG" 2>/dev/null || true

grep -q '.local/bin' "$HOME/.zshrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
echo "Done. Open a new terminal (or run: export PATH=\"\$HOME/.local/bin:\$PATH\")."
