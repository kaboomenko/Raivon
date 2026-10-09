#!/usr/bin/env bash
# The standard «Raivon Soft» shot set (docs/art_direction.md §6.12): renders each set with tools/godot_shot.sh
# (Mobile renderer, 941x1672, --lang=ru; --shot-delay=3 except cer), then measures them with tools/look_metrics.py.
# Usage: tools/soft_shots.sh OUTDIR [set ...]
#   sets: strat z03 close dl8 cer sel battle   (default: strat z03 close dl8 cer)
# Writes OUTDIR/<set>.png, OUTDIR/<set>.log (the filtered godot output) and OUTDIR/metrics.txt.
# Each godot run takes the shared /tmp/raivon_godot.lock, so parallel callers queue instead of clashing (~1–3 min a set).
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "usage: $0 OUTDIR [strat|z03|close|dl8|cer|sel|battle ...]" >&2
  exit 2
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
OUTARG="$1"
shift
SETS=("$@")
if [ ${#SETS[@]} -eq 0 ]; then SETS=(strat z03 close dl8 cer); fi

# Each set carries its own timing. Most wait --shot-delay=3 (clouds, water and fires settle). cer must not: the
# ceremony clock keeps running while the shot waits (main.gd _process -> _step_ceremony), and at counters_at
# (>= 4 s) the result modal covers the map. cer runs at a fixed 6 fps instead (godot_shot.sh --fixed-fps), so the
# ~10 frames before the capture add the same ~1.7 s of game time on any machine load: the battle's floating texts
# (1.4 s) are gone, and ceremony:0.15 is caught mid-way — the first ring of captured hexes just flipped (pop rings,
# edges still drawing on), the next ring still hatched. The frame repeats exactly except for fire/smoke particles.
set_args() {
  case "$1" in
    strat)  echo "--shot-delay=3" ;;
    z03)    echo "--zoom=0.3 --dl=3 --shot-delay=3" ;;
    close)  echo "--focus=0,3,0.06 --shot-delay=3" ;;
    dl8)    echo "--zoom=0.45 --dl=8 --ai-dl=8 --shot-delay=3" ;;
    cer)    echo "--fixed-fps=6 --demo=ceremony:0.15" ;;
    sel)    echo "--focus=0,3,0.06 --select=0,3 --shot-delay=3" ;;
    battle) echo "--demo=battle:40 --shot-delay=3" ;;
    *) return 1 ;;
  esac
}

for s in "${SETS[@]}"; do  # fail fast on a typo before spending minutes on renders
  set_args "$s" >/dev/null || { echo "unknown set '$s' (strat z03 close dl8 cer sel battle)" >&2; exit 2; }
done
mkdir -p "$OUTARG"
OUTDIR="$(cd "$OUTARG" && pwd)"  # absolute: godot runs from game/, a relative --shot path would land there

PNGS=()
for s in "${SETS[@]}"; do
  read -r -a ARGS <<< "$(set_args "$s")"
  png="$OUTDIR/$s.png"
  rm -f "$png"
  "$HERE/godot_shot.sh" "$png" ${ARGS[@]+"${ARGS[@]}"} --lang=ru > "$OUTDIR/$s.log" 2>&1 || true
  perf="$(grep -m1 'perf ' "$OUTDIR/$s.log" || true)"
  echo "$s: ${perf:-NO PERF LINE}"
  # shader / script errors are shown right away: a broken shader renders invisible. godot_shot.sh also reports
  # a lock or godot timeout and a missing screenshot as "godot_shot: ERROR: ..."
  grep -E 'SCRIPT ERROR|SHADER ERROR|Parse Error|ERROR: |^E +[0-9]+->' "$OUTDIR/$s.log" | sed "s/^/  $s! /" || true
  if [ -f "$png" ]; then PNGS+=("$png"); fi
done

if [ ${#PNGS[@]} -gt 0 ]; then
  python3 -I "$HERE/look_metrics.py" "${PNGS[@]}" | tee "$OUTDIR/metrics.txt"
fi
