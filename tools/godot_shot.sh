#!/usr/bin/env bash
# Renders the Godot client headlessly (software Vulkan) and saves a screenshot.
# Usage: tools/godot_shot.sh OUT.png [extra user args, e.g. --zoom=0.3]
set -euo pipefail
OUT="$1"; shift || true
GODOT=/opt/godot/Godot_v4.5.1-stable_linux.x86_64
cd "$(dirname "$0")/../game"
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json timeout 900 xvfb-run -a -s "-screen 0 941x1672x24" \
  "$GODOT" --path . --resolution 941x1672 -- --shot="$OUT" "$@" 2>&1 | grep -E 'shot saved|SCRIPT ERROR|Parse Error' || true
