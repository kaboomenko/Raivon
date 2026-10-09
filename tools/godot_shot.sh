#!/usr/bin/env bash
# Renders the Godot client headlessly (software Vulkan) and saves a screenshot.
# Usage: tools/godot_shot.sh OUT.png [extra user args, e.g. --zoom=0.3]
# --res=WxH sets the window (and the virtual X screen) size, default 941x1672 — e.g. --res=941x2040 for a tall phone
# (the project stretches with aspect "expand", so the canvas grows taller and VB moves down).
set -euo pipefail
# Renders with the Mobile renderer — what phones run (the project's rendering_method.mobile default); pass
# --forward-plus as an extra argument for the desktop renderer.
# --fixed-fps=N is passed to the engine (`--fixed-fps N`): every frame then advances game time by exactly 1/N s, so
# an animation captured part-way (e.g. --demo=ceremony:T) lands on the same moment however slow the software
# renderer is; a --shot-delay then costs N frames a second, so use it without a delay.
OUT="$1"; shift || true
METHOD=mobile
RES=941x1672
ENGINE=()
ARGS=()
for a in "$@"; do
  case "$a" in
    --forward-plus) METHOD=forward_plus ;;
    --fixed-fps=*) ENGINE+=(--fixed-fps "${a#--fixed-fps=}") ;;
    --res=*) RES="${a#--res=}" ;;
    *) ARGS+=("$a") ;;
  esac
done
GODOT=/opt/godot/Godot_v4.5.1-stable_linux.x86_64
LOCK=/tmp/raivon_godot.lock
LOCK_WAIT=1800  # s to wait for another godot run
RUN_LIMIT=900   # s for this godot run
cd "$(dirname "$0")/../game"
START=$(date +%s)
# Several agents shoot in parallel: the lock serialises godot runs (and `godot --import`, which should take the same
# lock: `flock -w 1800 /tmp/raivon_godot.lock godot --headless --path game --import`). -o: only flock holds the lock.
# Shader compile errors are printed too (with the offending source line, "E  12-> ..."): a shader that fails to
# compile renders invisible and is easy to miss.
rc=0
flock -E 75 -o -w "$LOCK_WAIT" "$LOCK" \
  env VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json timeout "$RUN_LIMIT" xvfb-run -a -s "-screen 0 ${RES}x24" \
  "$GODOT" --path . --rendering-method "$METHOD" ${ENGINE[@]+"${ENGINE[@]}"} --resolution "$RES" \
  -- --shot="$OUT" ${ARGS[@]+"${ARGS[@]}"} 2>&1 \
  | grep -E 'shot saved|perf |SCRIPT ERROR|SHADER ERROR|Parse Error|ERROR: .*([Ss]hader|uniform)|^E +[0-9]+->' \
  || rc=${PIPESTATUS[0]}
# The exit status stays 0 (callers loop over shots); a failed run says why instead of printing nothing.
if [ "$rc" -eq 75 ]; then
  echo "godot_shot: ERROR: gave up after $LOCK_WAIT s waiting for $LOCK (another godot run holds it)" >&2
elif [ "$rc" -eq 124 ]; then
  echo "godot_shot: ERROR: godot was stopped after $RUN_LIMIT s (timeout); no screenshot" >&2
else
  case "$OUT" in
    *://*) ;;  # res:// or user:// — not a path this shell can check
    *) if [ ! -f "$OUT" ] || [ "$(stat -c %Y "$OUT")" -lt "$START" ]; then
         echo "godot_shot: ERROR: no screenshot was saved to $OUT (godot exit status $rc)" >&2
       fi ;;
  esac
fi
exit 0
