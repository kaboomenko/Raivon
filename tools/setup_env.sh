#!/usr/bin/env bash
# Restores the dev toolchain in a fresh cloud container (idempotent).
# Blender (bpy wheel), Godot 4.5.1, Xvfb + Mesa (lavapipe) for headless rendering, npm deps.
set -euo pipefail
cd "$(dirname "$0")/.."
GODOT=/opt/godot/Godot_v4.5.1-stable_linux.x86_64
if [ ! -x "$GODOT" ]; then
  mkdir -p /opt/godot
  curl -sSL -o /opt/godot/godot.zip https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_linux.x86_64.zip
  unzip -o -q /opt/godot/godot.zip -d /opt/godot && rm /opt/godot/godot.zip
fi
python3 -c "import bpy" 2>/dev/null || pip install -q bpy==5.0.1
if ! command -v xvfb-run >/dev/null; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq xvfb libgl1-mesa-dri mesa-vulkan-drivers libvulkan1 \
    libxcursor1 libxinerama1 libxrandr2 libxi6 libasound2t64 libpulse0 >/dev/null
fi
[ -d node_modules ] || npm ci --silent
# Godot import (creates game/.godot cache)
"$GODOT" --headless --path game --import >/dev/null 2>&1 || true
echo "toolchain ready"
