#!/usr/bin/env bash
# The store screenshot sets (docs/store/listing.md «Графика»): a curated set of game screens in ru and en at the
# sizes the stores take, rendered by tools/godot_shot.sh (Mobile renderer, the window at the store size).
# Usage: tools/store_shots.sh [OUTDIR] [--dry-run] [--langs=ru,en] [--sizes=play,iphone,ipad] [--scenes=map,battle,...]
#   OUTDIR      default docs/store/screens; shots land in OUTDIR/<size>/<lang>/NN_<scene>.png
#   --dry-run   print every godot_shot.sh call (and check the names) without running Godot
# Sizes (portrait):
#   play    1080x1920  Google Play phone (Play takes 16:9 / 9:16 and rejects a side over twice the other, so not
#                      the 1080x2400 of a modern phone)
#   iphone  1290x2796  App Store 6.9"/6.7" iPhone (the one size App Store Connect requires; it scales it down)
#   ipad    2064x2752  App Store 13" iPad (export_presets targeted_device_family includes iPad)
# Scenes: map (a chapter III realm), battle (a DL5 battle with the war cards), peace (the peace treaty), ceremony
# (the border flowing over the new land), city (a DL8 neon city), album (the commanders album).
# Every PNG is flattened to RGB (App Store Connect refuses an alpha channel) and checked for its size; a shot that
# fails says so and the run goes on. One godot run per shot, each under the shared /tmp/raivon_godot.lock (godot_shot.sh):
# the full set (6 scenes x 2 languages x 3 sizes) takes about an hour on the 4-core box. Re-run it whenever the game's
# screens change (after a code lane lands), then read every shot at real size.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUTARG="$ROOT/docs/store/screens"
DRY=0
LANGS=(ru en)
SIZES=(play iphone ipad)
SCENES=(map battle peace ceremony city album)
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --langs=*) IFS=, read -r -a LANGS <<< "${a#--langs=}" ;;
    --sizes=*) IFS=, read -r -a SIZES <<< "${a#--sizes=}" ;;
    --scenes=*) IFS=, read -r -a SCENES <<< "${a#--scenes=}" ;;
    -h|--help) sed -n '2,19p' "$0"; exit 0 ;;
    --*) echo "unknown option $a" >&2; exit 2 ;;
    *) OUTARG="$a" ;;
  esac
done

size_res() {
  case "$1" in
    play) echo 1080x1920 ;;
    iphone) echo 1290x2796 ;;
    ipad) echo 2064x2752 ;;
    *) return 1 ;;
  esac
}
# the scene's godot_shot.sh arguments (the demos of game/scripts/main.gd _demo; see tools/soft_shots.sh for timing)
scene_args() {
  case "$1" in
    map) echo "--demo=ch3:view --shot-delay=3" ;;
    battle) echo "--dl=5 --ai-dl=5 --demo=battle:40 --shot-delay=3" ;;
    peace) echo "--demo=peace --shot-delay=3" ;;
    ceremony) echo "--fixed-fps=6 --demo=ceremony:0.15" ;;
    city) echo "--zoom=0.45 --dl=8 --ai-dl=8 --shot-delay=3" ;;
    album) echo "--demo=commanders --shot-delay=3" ;;
    *) return 1 ;;
  esac
}
for s in "${SIZES[@]}"; do size_res "$s" >/dev/null || { echo "unknown size '$s' (play iphone ipad)" >&2; exit 2; }; done
for s in "${SCENES[@]}"; do scene_args "$s" >/dev/null || { echo "unknown scene '$s' (map battle peace ceremony city album)" >&2; exit 2; }; done
for l in "${LANGS[@]}"; do case "$l" in ru|en) ;; *) echo "unknown language '$l' (ru en)" >&2; exit 2 ;; esac; done

OUT="$(realpath -m "$OUTARG")"  # absolute: godot runs from game/, a relative --shot path would land there
n_ok=0; n_bad=0
for size in "${SIZES[@]}"; do
  res="$(size_res "$size")"
  for lang in "${LANGS[@]}"; do
    dir="$OUT/${size}_${res}/$lang"
    i=0
    for scene in "${SCENES[@]}"; do
      i=$((i + 1))
      png="$dir/$(printf '%02d' "$i")_$scene.png"
      read -r -a ARGS <<< "$(scene_args "$scene")"
      if [ "$DRY" -eq 1 ]; then
        echo "tools/godot_shot.sh $png ${ARGS[*]} --res=$res --lang=$lang"
        continue
      fi
      mkdir -p "$dir"
      rm -f "$png"
      "$HERE/godot_shot.sh" "$png" "${ARGS[@]}" "--res=$res" "--lang=$lang" > "${png%.png}.log" 2>&1 || true
      perf="$(grep -m1 'perf ' "${png%.png}.log" || true)"
      errs="$(grep -E 'SCRIPT ERROR|SHADER ERROR|Parse Error|godot_shot: ERROR' "${png%.png}.log" | head -3 || true)"
      if [ -f "$png" ] && python3 -I - "$png" "$res" <<'PY'
import sys
from PIL import Image
path, res = sys.argv[1], sys.argv[2]
w, h = (int(v) for v in res.split("x"))
im = Image.open(path)
if im.size != (w, h):
    print("  size %dx%d, wanted %dx%d" % (im.size[0], im.size[1], w, h))
    sys.exit(1)
im.convert("RGB").save(path, optimize=True)  # flattened: no alpha channel
PY
      then
        n_ok=$((n_ok + 1))
        echo "$size/$lang/$(basename "$png"): ok  ${perf:-no perf line}"
      else
        n_bad=$((n_bad + 1))
        echo "$size/$lang/$(basename "$png"): FAILED"
      fi
      [ -n "$errs" ] && echo "$errs" | sed 's/^/  ! /'
      rm -f "${png%.png}.log"
    done
  done
done
if [ "$DRY" -eq 0 ]; then
  echo "store_shots: $n_ok shots, $n_bad failed, in $OUT"
  [ "$n_bad" -eq 0 ]
fi
