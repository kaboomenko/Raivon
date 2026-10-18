"""The face crops' fit in the game's small slots (docs/art_direction.md §7.12): the FACE_FIT table of cmd_portrait.gd.
numpy + Pillow.

Usage: python3 -I tools/qa_portraits/face_fit.py DIR [--gd] [--check=game/scripts/cmd_portrait.gd] [--sheet=OUT.png]

DIR holds the 52 face_<name>.png (256x256) with the kit's sidecars meta/ and ids/ (tools/blender/portrait_assets.py
--frame=face --sidecars). Per file:
- top: the highest row (of 256) the figure reaches (alpha >= 0.25 in two or more pixels: what a 2 px frame touches),
  the meta's top_exempt group (Rai's banner leaves the top by design) left out. cmd_portrait.gd shrinks the crop from
  its bottom edge in a square slot (the picker 72, the mail 72, the calendar 64, the «Армия» fan 58) until this row
  clears the slot's rarity frame by FACE_CLEAR px.
- chip: the crop in the army chip's circle (Kit._card_ring, Ø38) as [side, top] over the diameter. The chip of T2
  drew every crop 50 px tall with its top 6 px over the circle (eye line on the centre at 0.50): that stays wherever it
  keeps the headgear and hair above the eye line inside the circle less CHIP_MARGIN px (top_exempt, Lira's kerchief
  tails and Irma's ponytail left out: they fall to the side, past any circle). Elsewhere the side steps down (0.25 px)
  and the eye line may sit up to CHIP_EYE_DROP px under the centre, until no more than CHIP_TOL px² of that silhouette
  is outside; the head (chin-crown, upright) never under CHIP_HEAD_MIN px. Printed: the head size, the eye's place,
  the area cut before and after.
--gd prints the table as GDScript; --check=FILE compares it with FILE's FACE_FIT (exit 1 on a difference, or when a
chip still cuts more than CHIP_TOL px²); --sheet=OUT.png draws every chip as T2 drew it and as the table draws it.
"""
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

CHIP_D = 38.0  # the circle (Kit._card_ring: the inner panel 38 x 38, corner radius 19)
CHIP_SIDE0 = 50.0  # T2: the portrait 48 x 50 at (-5, -6) over the circle — the crop 50 px tall, its top at -6
CHIP_TOP0 = -6.0
CHIP_MARGIN = 0.5  # px inside the circle's edge (its antialiased rim under the INK ring's inner edge)
CHIP_EYE_DROP = 4.0  # px: how far under the circle's centre the eye line may go
CHIP_CROWN = 45.0  # deg: the crown — the silhouette within this angle of straight up from the circle's centre ...
CHIP_CROWN_TOL = 3.5  # ... may pass the circle by this many px² at most (a tip's antialiasing): the hat or the bun whole
CHIP_TOL = 35.0  # px² of the whole silhouette above the eye line past the circle (a brim's or a hood peak's tip to
# the side; the bust chip before T2 cut 0-89 px² of it, the T2 crop 11-291)
CHIP_HEAD_MIN = 28.0  # px: the head never smaller in the chip
CHIP_SKIP = ("detail:kerchief_tails", "detail:ponytail")  # hang to the side: cut by any circle, as in the bust chip
TOP_ALPHA = 0.25


def silhouette(d, n):
    """(alpha 256x256, meta, part masks or None, top_exempt mask or None)."""
    im = Q.load(os.path.join(d, n + ".png"))
    m = Q.meta(d, n) or {}
    masks, _ = Q.ids(d, n)
    ex = None
    if masks is not None and m.get("top_exempt") in masks:
        ex = masks[m["top_exempt"]]
    return im[..., 3], m, masks, ex


def top_row(a, ex):
    vis = a >= TOP_ALPHA
    if ex is not None:
        vis &= ~ex
    rows = np.where(vis.sum(axis=1) >= 2)[0]
    return int(rows[0]) if len(rows) else 0


def chip_points(a, m, masks, ex):
    """Crop px (u, v) centres of the headgear and hair above the eye line that must stay inside the chip's circle."""
    ey = float(m.get("eye_y", 128.0))
    sel = a >= 0.5
    if ex is not None:
        sel &= ~ex
    if masks is not None:
        for k in CHIP_SKIP:
            if k in masks:
                sel &= ~masks[k]
    sel[int(np.ceil(ey)):] = False
    v, u = np.nonzero(sel)
    return u + 0.5, v + 0.5, ey


def cut_area(u, v, side, top):
    """(px² of the points outside the circle less CHIP_MARGIN, px² of those in the crown cone) with the crop `side`
    px tall, its top at `top`."""
    k = side / 256.0
    r = CHIP_D / 2.0
    x = r + (u - 128.0) * k - r
    y = top + v * k - r
    out = x * x + y * y > (r - CHIP_MARGIN) ** 2
    crown = out & (y < 0) & (np.abs(x) <= -y * np.tan(np.radians(CHIP_CROWN)))
    return float(out.sum()) * k * k, float(crown.sum()) * k * k


def passes(c):
    return c[0] <= CHIP_TOL and c[1] <= CHIP_CROWN_TOL


def fit_chip(u, v, ey, h_px):
    """(side, top, cut before, cut after, head px, eye px under the centre)."""
    before = cut_area(u, v, CHIP_SIDE0, CHIP_TOP0)
    r = CHIP_D / 2.0
    if passes(before):
        return CHIP_SIDE0, CHIP_TOP0, before, before, h_px * CHIP_SIDE0 / 256.0, CHIP_TOP0 + ey * CHIP_SIDE0 / 256.0 - r
    side_min = CHIP_HEAD_MIN * 256.0 / h_px
    best = None
    side = CHIP_SIDE0
    while side >= side_min - 1e-6:
        k = side / 256.0
        for e in np.arange(0.0, CHIP_EYE_DROP + 1e-6, 0.25):
            top = r + e - ey * k
            c = cut_area(u, v, side, top)
            if best is None or (c[1], c[0]) < (best[3][1], best[3][0]):
                best = (side, top, before, c)
            if passes(c):
                return side, top, before, c, h_px * k, e
        side -= 0.25
    side, top, before, c = best
    return side, top, before, c, h_px * side / 256.0, top + ey * side / 256.0 - r


def table(d):
    rows = []
    for n in Q.face_names():
        if not os.path.exists(os.path.join(d, n + ".png")):
            continue
        a, m, masks, ex = silhouette(d, n)
        t = top_row(a, ex)
        u, v, ey = chip_points(a, m, masks, ex)
        h_px = float(m.get("h_px", 0.66 * 256))
        side, top, before, after, head, eye = fit_chip(u, v, ey, h_px)
        rows.append(dict(name=n, top=t, side=round(side / CHIP_D, 4), ctop=round(top / CHIP_D, 4), before=before,
                         after=after, head=head, eye=eye, ids=masks is not None))
    return rows


def gd(rows):
    out = ["const FACE_FIT := {"]
    for r in rows:
        out.append('\t"%s": [%d, %.4f, %.4f],' % (r["name"], r["top"], r["side"], r["ctop"]))
    out.append("}")
    return "\n".join(out)


def read_gd(path):
    src = open(path, encoding="utf-8").read()
    got = {}
    for name, t, s, c in re.findall(r'"(face_[a-z0-9_]+)": \[(\d+), ([0-9.\-]+), ([0-9.\-]+)\]', src):
        got[name] = (int(t), float(s), float(c))
    return got


def sheet(d, rows, out):
    """Every chip drawn as T2 drew it (top row) and with the table (bottom row), 4x, per commander column."""
    z = 4
    cell = int(CHIP_D + 12) * z
    names = [r["name"] for r in rows]
    cols = 13
    lines = (len(names) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell, lines * 2 * cell + 8), (23, 32, 58))
    for i, r in enumerate(rows):
        im = Image.open(os.path.join(d, r["name"] + ".png")).convert("RGBA")
        plate = Q.hex_rgb(Q.plate_of(r["name"]))
        for j, (side, top) in enumerate([(CHIP_SIDE0, CHIP_TOP0), (r["side"] * CHIP_D, r["ctop"] * CHIP_D)]):
            s = int(CHIP_D * z)
            c = Image.new("RGBA", (s, s), tuple(int(x * 255) for x in Q.lightened(plate, 0.18)) + (255,))
            cr = im.resize((max(1, int(round(side * z))), max(1, int(round(side * z)))), Image.LANCZOS)
            c.alpha_composite(cr, (int(round((CHIP_D / 2 - side / 2) * z)), int(round(top * z))))
            mask = Image.new("L", (s, s), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, s - 1, s - 1), fill=255)
            x0 = (i % cols) * cell + 6 * z
            y0 = (i // cols) * 2 * cell + j * cell + 6 * z
            ring = Image.new("RGBA", (s + 6 * z, s + 6 * z), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((0, 0, s + 6 * z - 1, s + 6 * z - 1), fill=(29, 32, 48, 255))
            img.paste(ring, (x0 - 3 * z, y0 - 3 * z), ring)
            img.paste(c, (x0, y0), mask)
    img.save(out)


def main(argv):
    pos, opts = Q.parse(argv)
    if not pos:
        print(__doc__)
        return 2
    d = pos[0]
    rows = table(d)
    if not rows:
        print("no face_*.png in %s" % d)
        return 1
    bad = 0
    for r in rows:
        moved = (r["side"], r["ctop"]) != (round(CHIP_SIDE0 / CHIP_D, 4), round(CHIP_TOP0 / CHIP_D, 4))
        flag = "" if passes(r["after"]) else "  CUT"
        bad += 1 if flag else 0
        print("%-24s top %3d  chip %s side %.1f px top %+.1f  head %.1f px  eye %+.1f px  cut %.0f (crown %.0f) -> %.0f "
              "(crown %.0f) px²%s%s" % (r["name"], r["top"], "fit " if moved else "T2  ", r["side"] * CHIP_D,
              r["ctop"] * CHIP_D, r["head"], r["eye"], r["before"][0], r["before"][1], r["after"][0], r["after"][1], flag,
              "" if r["ids"] else "  (no ids: whole silhouette)"))
    print("chips refit: %d of %d; still cut: %d" % (sum(1 for r in rows if (r["side"], r["ctop"]) != (
        round(CHIP_SIDE0 / CHIP_D, 4), round(CHIP_TOP0 / CHIP_D, 4))), len(rows), bad))
    if "gd" in opts:
        print(gd(rows))
    if "sheet" in opts:
        sheet(d, rows, opts["sheet"])
        print("sheet: %s" % opts["sheet"])
    if "check" in opts:
        got = read_gd(opts["check"])
        diff = [r["name"] for r in rows if got.get(r["name"]) != (r["top"], r["side"], r["ctop"])]
        extra = sorted(set(got) - {r["name"] for r in rows})
        print("check %s: %d of %d entries match%s%s" % (opts["check"], len(rows) - len(diff), len(rows),
              ("; differ: " + ", ".join(diff[:8]) + (" ..." if len(diff) > 8 else "")) if diff else "",
              ("; not in DIR: " + ", ".join(extra)) if extra else ""))
        return 1 if diff or bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
