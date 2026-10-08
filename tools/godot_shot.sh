#!/usr/bin/env bash
# Renders the Godot client headlessly (software Vulkan) and saves a screenshot.
# Usage: tools/godot_shot.sh OUT.png [extra user args, e.g. --zoom=0.3]
set -euo pipefail
# Renders with the Mobile renderer — what phones run (the project's rendering_method.mobile default); pass
# --forward-plus as the first extra argument for the desktop renderer.
OUT="$1"; shift || true
METHOD=mobile
if [ "${1:-}" = "--forward-plus" ]; then METHOD=forward_plus; shift; fi
GODOT=/opt/godot/Godot_v4.5.1-stable_linux.x86_64
cd "$(dirname "$0")/../game"
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json timeout 900 xvfb-run -a -s "-screen 0 941x1672x24" \
  "$GODOT" --path . --rendering-method "$METHOD" --resolution 941x1672 -- --shot="$OUT" "$@" 2>&1 | grep -E 'shot saved|perf |SCRIPT ERROR|Parse Error' || true
