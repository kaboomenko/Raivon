#!/usr/bin/env python3
"""HUD pixel-parity check (docs/dev/hud_perf_plan.json H1/H2): compares two screenshots of the same screen in the
regions the HUD covers and writes a diff image.

    python3 -I tools/hud_diff.py BEFORE.png AFTER.png OUT_DIFF.png [--regions x0,y0,x1,y1 ...] [--thr 24]
           [--mask-map BEFORE2.png]

The 3D map under the HUD animates (smoke, water, troops), so two runs never match there: by default only the HUD's
rectangles are compared (top bar, left column, map tools, minimap, tabs/tray/hex panel/big button), and pixels that
also differ between two runs of the *same* build (--mask-map: a second before-shot) are ignored. The diff image
shows AFTER greyed out with every pixel that differs by more than --thr (out of 255, any channel) in red, and the
HUD regions outlined. Prints per region: pixels over the threshold, the largest difference, the mean difference.
Exit status 0 always (it is a report)."""
import argparse
import sys

from PIL import Image, ImageChops, ImageDraw

# the HUD's rectangles in the 941×1672 design space (hud.gd, game_ui.gd)
HUD = {
    "pills": (110, 0, 941, 92),
    "crest+ruler": (0, 0, 112, 250),
    "left column": (0, 240, 112, 860),
    "minimap": (726, 90, 941, 300),
    "map tools": (800, 300, 941, 760),
    "tabs": (0, 1360, 640, 1470),
    "tray": (0, 1460, 645, 1672),
    "hex panel": (645, 1340, 941, 1530),
    "big button": (645, 1520, 941, 1672),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("out")
    ap.add_argument("--regions", nargs="*", default=None, help="x0,y0,x1,y1 rectangles instead of the HUD set")
    ap.add_argument("--thr", type=int, default=24)
    ap.add_argument("--mask-map", default=None, help="a second BEFORE shot: pixels that differ between the two runs are ignored")
    a = ap.parse_args()
    b = Image.open(a.before).convert("RGB")
    f = Image.open(a.after).convert("RGB")
    if b.size != f.size:
        print("size differs: %s vs %s" % (b.size, f.size))
        return 0
    regions = HUD
    if a.regions:
        regions = {r: tuple(int(v) for v in r.split(",")) for r in a.regions}
    d = ImageChops.difference(b, f)
    dm = d.split()
    dmax = ImageChops.lighter(ImageChops.lighter(dm[0], dm[1]), dm[2])  # per-pixel max over the channels
    noise = None
    if a.mask_map:
        b2 = Image.open(a.mask_map).convert("RGB")
        n = ImageChops.difference(b, b2).split()
        noise = ImageChops.lighter(ImageChops.lighter(n[0], n[1]), n[2]).point(lambda v: 255 if v > a.thr // 2 else 0)
    px = dmax.load()
    npx = noise.load() if noise else None
    out = Image.blend(f.convert("L").convert("RGB"), Image.new("RGB", f.size, (40, 40, 40)), 0.5)
    op = out.load()
    total = 0
    for name, (x0, y0, x1, y1) in regions.items():
        x1 = min(x1, f.size[0])
        y1 = min(y1, f.size[1])
        over = 0
        mx = 0
        s = 0
        cnt = 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                v = px[x, y]
                if npx is not None and npx[x, y]:
                    continue
                cnt += 1
                s += v
                if v > mx:
                    mx = v
                if v > a.thr:
                    over += 1
                    op[x, y] = (255, 40, 40)
        total += over
        print("%-12s over %3d: %6d px   max %3d   mean %.2f" % (name, a.thr, over, mx, s / max(1, cnt)))
    dr = ImageDraw.Draw(out)
    for name, (x0, y0, x1, y1) in regions.items():
        dr.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(80, 200, 255))
    out.save(a.out)
    print("total over threshold: %d px -> %s" % (total, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
