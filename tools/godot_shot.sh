#!/usr/bin/env bash
# Renders the Godot client headlessly (software Vulkan) and saves a screenshot.
# Usage: tools/godot_shot.sh OUT.png [extra user args, e.g. --zoom=0.3]
# --res=WxH sets the window (and the virtual X screen) size, default 941x1672 — e.g. --res=941x2040 for a tall phone
# (the project stretches with aspect "expand", so the canvas grows taller and VB moves down).
set -euo pipefail
# Renders with the Mobile renderer — what phones run (the project's rendering_method.mobile default); pass
# --forward-plus as an extra argument for the desktop renderer.
# --perf-tree: after the shot, the canvas draw calls of every HUD subtree (game/tools/perf_probe.gd): printed as
# «perf-tree» lines and written to OUT.png.tree.txt. --hud-only: the shot without the 3D world (the canvas alone, on
# the clear colour) — two builds' HUDs compare pixel for pixel (tools/hud_diff.py). --perf-tree --perf-smoke: instead of
# the breakdown, the HUD while it moves — the card row scrolled (culling checked; OUT_s37.png / OUT_s111.png once it
# holds still) and the camera panned and zoomed (canvas draws per frame, bake rounds, atlas resets); «FAIL» lines.
# --perf-tree --perf-late (with --demo=calendar|chronicle|pass): the screen again in a late-game state (calendar day 27,
# every Chronicle goal taken, War Pass level 30 claimed), shot over OUT.png («perf late» line) and measured so.
# --perf-tree --perf-trans --perf-trans-open=<main opener> (use --fixed-fps=60): canvas draws frame by frame while the
# window closes and opens, the bottom tabs switch and toasts come. --perf-tree --perf-fling --fixed-fps=60
# --virtual-clock: the open window's list scrolled 18 then 45 px every frame (a finger), each held 150 frames, every
# frame's canvas draws recorded; FAIL lines for frames over 300 (--virtual-clock: the kit bake's timers count frames at
# 60 a second, as on a phone, however slowly the software renderer draws). --perf-nobreak: the counts (and --perf-vec's
# bake/vector pair) without the per-subtree breakdown (much faster).
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
# s for this godot run. A plain shot takes ~20-70 s and the game ends its own process once the PNG is saved
# (main.gd _shot: a normal quit could hang in the renderer teardown under xvfb/lavapipe and hold the lock); the
# --perf-tree probes (the breakdown, the shop tabs, the fling) walk many frames and get the old 15 min.
RUN_LIMIT=300
case " $* " in *" --perf-tree "*) RUN_LIMIT=900 ;; esac
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
  | grep -E 'shot saved|perf |perf-tree |SCRIPT ERROR|SHADER ERROR|Parse Error|ERROR: .*([Ss]hader|uniform)|^E +[0-9]+->' \
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
