"""Owner-facing contact sheets for a portrait step (docs/dev/portraits_plan.json "Owner-facing sheets"). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/owner_sheet.py NEW_DIR OUT_DIR [--before=DIR] [--alt=DIR] [--alt-label=TEXT]
                                                [--ids=bram,lira,...] [--tag=NAME] [--p3]

NEW_DIR holds the step's renders (cmd_<id>.png and cmd_<id>_smile.png, 512x588); --before the set they replace (the
game's portraits folder or a copy of it); --alt a second variant of some ids (the hand-free fallbacks of §7.15 q3) shown
next to the new render. Writes into OUT_DIR (TAG_ prefixed when --tag is given):
  masters_512.png     every commander present, calm | smile at 512, on a neutral grey, captioned;
  plates_128_64.png   calm and smile at 128 and 64 px on the commander's rarity plate — plate B (§7.4) in the UI palette
                      (Kit.RARITY) and in the GDD §15.4 palette — the sizes the album, the card and the small slots show;
  silhouettes_48.png  every era-1 calm render as a black 48 px alpha mask, captioned (the shuffled, uncaptioned sheet
                      for the blind naming test P-A2 is qa_sheets.py's silhouettes_48.png);
  before_after.png    with --before: the current file | the new one, calm and smile, at 256 px wide;
  alt.png             with --alt: the new render | the alternative, at 384 px wide.
With --p3 (the eras, the leaders and the ruler, plan step P3) it writes instead:
  eras_128_48.png             12 commanders x 4 eras (calm) at 128 px on plate B + their 48 px silhouettes (with
                              --before: current | new per era);
  leaders_moods_138_80.png    10 leaders x 5 moods at 138 px (the seal) and 80 px (the dialog row) on the state plate B;
  ruler_eras_104_74.png       the ruler's 4 eras at 104 px (the profile) and 74 px (the HUD) on the sky;
  eras_masters_256.png, leaders_masters_256.png, ruler_masters_256.png   the files at 256 px, captioned.
A folder with only some of the ids is fine (missing ones are skipped and listed).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "fonts", "Rubik-VF.ttf")
BG = (232, 234, 238)
GREY = (167, 175, 188)


def font(px):
    try:
        return ImageFont.truetype(FONT, px)
    except OSError:
        return ImageFont.load_default()


def on(rgba, colour):
    """Composite straight RGBA over a flat colour -> RGB uint8 image."""
    c = np.array(colour, dtype=np.float32) / 255.0 if isinstance(colour, tuple) else colour
    return Image.fromarray((np.clip(Q.over_plate(rgba, c), 0, 1) * 255 + 0.5).astype(np.uint8))


def on_plate(rgba, rarity_hex):
    """Composite over plate B of a rarity colour (the gradient and the soft halo the game draws, §7.4)."""
    h, w = rgba.shape[:2]
    plate = Q.plate_image(rarity_hex, w, h, "B")
    rgb = rgba[..., :3] * rgba[..., 3:4] + plate * (1 - rgba[..., 3:4])
    return Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8))


def caption(dr, xy, text, px=18, fill=(40, 44, 52)):
    dr.text(xy, text, font=font(px), fill=fill)


def masters(src, ids, out):
    cell_w, cell_h, pad, top = 512, 588, 10, 30
    cols = 6
    items = [(c, m) for c in ids for m in ("", "_smile")]
    rows = (len(items) + cols - 1) // cols
    sh = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (cell_h + top + pad) + pad), BG)
    dr = ImageDraw.Draw(sh)
    for k, (c, m) in enumerate(items):
        p = Q.path_of(src, "cmd_" + c + m)
        if not p:
            continue
        x, y = pad + (k % cols) * (cell_w + pad), pad + (k // cols) * (cell_h + top + pad)
        sh.paste(on(Q.load(p), GREY), (x, y + top))
        caption(dr, (x + 4, y + 4), "%s %s - %s" % (c.capitalize(), "smile" if m else "calm", Q.RARITY[c]), 20)
    sh.save(out)


def plates(src, ids, out):
    pad = 8
    col_w = 128 + 64 + 3 * pad
    head = 26
    sh = Image.new("RGB", (len(ids) * 2 * col_w + pad, 2 * (147 + head + pad) + 40), BG)
    dr = ImageDraw.Draw(sh)
    caption(dr, (pad, 4), "128 and 64 px on plate B: top row UI palette (Kit.RARITY), bottom row GDD 15.4 palette;"
            " calm | smile", 18)
    for i, c in enumerate(ids):
        for j, m in enumerate(("", "_smile")):
            p = Q.path_of(src, "cmd_" + c + m)
            if not p:
                continue
            a = Q.load(p)
            for r, pal in enumerate(("ui", "gdd")):
                x = pad + (i * 2 + j) * col_w
                y = 40 + r * (147 + head + pad)
                rh = Q.PALETTES[pal][Q.RARITY[c]]
                big = on_plate(Q.resize_rgba(a, 128), Q.hex_rgb(rh))
                small = on_plate(Q.resize_rgba(a, 64), Q.hex_rgb(rh))
                sh.paste(big, (x, y + head))
                sh.paste(small, (x + 128 + pad, y + head))
                if r == 0:
                    caption(dr, (x, y + 4), "%s %s" % (c, "smile" if m else "calm"), 15)
    sh.save(out)


def silhouettes(src, ids, out):
    cell, pad = 64, 10
    sh = Image.new("RGB", (len(ids) * (cell + pad) + pad, cell + 50), "white")
    dr = ImageDraw.Draw(sh)
    for i, c in enumerate(ids):
        p = Q.path_of(src, "cmd_" + c)
        if not p:
            continue
        m = Q.alpha_mask(Q.load(p), 48)
        tile = Image.fromarray(np.where(m, 20, 255).astype(np.uint8)).convert("RGB")
        x = pad + i * (cell + pad)
        sh.paste(tile, (x + (cell - tile.width) // 2, 8))
        caption(dr, (x, cell + 18), c, 13, (90, 90, 90))
    sh.save(out)


def side_by_side(a_dir, b_dir, ids, out, labels, width=256, moods=("", "_smile")):
    pad, top = 8, 24
    h = round(width * 588 / 512)
    cols = len(moods) * 2
    sh = Image.new("RGB", (cols * (width + pad) + pad + 70, len(ids) * (h + pad) + top + pad), BG)
    dr = ImageDraw.Draw(sh)
    for j, m in enumerate(moods):
        for k, lab in enumerate(labels):
            caption(dr, (70 + pad + (j * 2 + k) * (width + pad), 4), "%s %s" % (lab, "smile" if m else "calm"), 16)
    for i, c in enumerate(ids):
        y = top + i * (h + pad)
        caption(dr, (6, y + h // 2 - 8), c, 15)
        for j, m in enumerate(moods):
            for k, d in enumerate((a_dir, b_dir)):
                p = Q.path_of(d, "cmd_" + c + m) if d else None
                if not p:
                    continue
                img = Q.load(p)
                x = 70 + pad + (j * 2 + k) * (width + pad)
                sh.paste(on(Q.resize_rgba(img, width, h) if img.shape[1] != width else img, GREY), (x, y))
    sh.save(out)


# ------------------------------------------------------------------ P3 sheets: eras, leaders x moods, the ruler
def eras_sheet(src, out, ids, before=None):
    """12 commanders x 4 eras (calm) at 128 px on their rarity plate B (UI palette) with each one's 48 px black
    silhouette under it; with `before`, the current file's 128 px tile in a thin column at the left of each era."""
    pad, head, cw = 10, 30, 128
    rows_h = 147 + 8 + 56 + pad
    sh = Image.new("RGB", (110 + 4 * (cw + pad) * (2 if before else 1) + pad, head + len(ids) * rows_h + pad), BG)
    dr = ImageDraw.Draw(sh)
    for j, e in enumerate(Q.ERAS):
        x = 110 + j * (cw + pad) * (2 if before else 1)
        caption(dr, (x, 6), ("E%s" % (e[2:] or "1")) + ("  current | new" if before else ""), 16)
    for i, c in enumerate(ids):
        y = head + i * rows_h
        caption(dr, (6, y + 60), c, 16)
        for j, e in enumerate(Q.ERAS):
            x = 110 + j * (cw + pad) * (2 if before else 1)
            for k, d in enumerate(([before] if before else []) + [src]):
                p = Q.path_of(d, "cmd_" + c + e)
                if not p:
                    continue
                a = Q.load(p)
                xx = x + k * (cw + pad)
                sh.paste(on_plate(Q.resize_rgba(a, cw), Q.hex_rgb(Q.PLATES_UI[Q.RARITY[c]])), (xx, y))
                m = Q.alpha_mask(a, 48)
                tile = Image.fromarray(np.where(m, 20, 255).astype(np.uint8)).convert("RGB")
                sh.paste(tile, (xx + (cw - tile.width) // 2, y + 147 + 6))
    sh.save(out)


def leaders_sheet(src, out, before=None):
    """10 leaders x 5 moods at 138 px (the seal) and 80 px (the dialog row) on the state's plate B; with `before`, the
    current calm at 138 px first."""
    pad, head = 8, 30
    cw = 138 + 80 + 3 * pad
    rows_h = 159 + pad + 18
    extra = (138 + pad) if before else 0
    sh = Image.new("RGB", (110 + extra + 5 * cw + pad, head + len(Q.LEADERS) * rows_h + pad), BG)
    dr = ImageDraw.Draw(sh)
    if before:
        caption(dr, (110, 6), "current", 16)
    for j, m in enumerate(Q.LEADER_MOODS):
        caption(dr, (110 + extra + j * cw, 6), (m or "_calm")[1:] + "  138 | 80 px", 16)
    for i, x in enumerate(Q.LEADERS):
        y = head + i * rows_h
        caption(dr, (6, y + 60), x, 16)
        plate = Q.hex_rgb(Q.LEADER_PLATE[x])
        if before:
            p = Q.path_of(before, "ldr_" + x)
            if p:
                sh.paste(on_plate(Q.resize_rgba(Q.load(p), 138), plate), (110, y))
        for j, m in enumerate(Q.LEADER_MOODS):
            p = Q.path_of(src, "ldr_" + x + m)
            if not p:
                continue
            a = Q.load(p)
            xx = 110 + extra + j * cw
            sh.paste(on_plate(Q.resize_rgba(a, 138), plate), (xx, y))
            sh.paste(on_plate(Q.resize_rgba(a, 80), plate), (xx + 138 + pad, y))
    sh.save(out)


def ruler_sheet(src, out, before=None):
    """The ruler in 4 eras at 74 px on the sky plate (the HUD) and at 104 px (the profile); with `before`, the current
    files in the row above."""
    pad, head = 12, 30
    rows = [("new", src)] + ([("current", before)] if before else [])
    sh = Image.new("RGB", (100 + 4 * (104 + 74 + 3 * pad) + pad, head + len(rows) * (120 + 2 * pad) + pad), BG)
    dr = ImageDraw.Draw(sh)
    sky = Q.hex_rgb(Q.SKY)
    for j, e in enumerate(Q.ERAS):
        caption(dr, (100 + j * (104 + 74 + 3 * pad), 6), "E%s  104 | 74 px" % (e[2:] or "1"), 16)
    for i, (lab, d) in enumerate(rows):
        y = head + i * (120 + 2 * pad)
        caption(dr, (6, y + 40), lab, 16)
        for j, e in enumerate(Q.ERAS):
            p = Q.path_of(d, "ruler" + e)
            if not p:
                continue
            a = Q.load(p)
            x = 100 + j * (104 + 74 + 3 * pad)
            sh.paste(on_plate(Q.resize_rgba(a, 104), sky), (x, y))
            sh.paste(on_plate(Q.resize_rgba(a, 74), sky), (x + 104 + pad, y))
    sh.save(out)


def masters_any(src, names, out, cols=6, width=256):
    """Any set of files at `width` on grey, captioned (the P3 era and leader masters at their review size)."""
    pad, top = 8, 24
    h = round(width * 588 / 512)
    rows = (len(names) + cols - 1) // cols
    sh = Image.new("RGB", (cols * (width + pad) + pad, rows * (h + top + pad) + pad), BG)
    dr = ImageDraw.Draw(sh)
    for k, n in enumerate(names):
        p = Q.path_of(src, n)
        if not p:
            continue
        a = Q.load(p)
        x, y = pad + (k % cols) * (width + pad), pad + (k // cols) * (h + top + pad)
        sh.paste(on(Q.resize_rgba(a, width, h) if a.shape[1] != width else a, GREY), (x, y + top))
        caption(dr, (x + 2, y + 2), n, 15)
    sh.save(out)


def main():
    pos, opts = Q.parse(sys.argv[1:])
    src, outd = pos[0], pos[1]
    os.makedirs(outd, exist_ok=True)
    if "p3" in opts:
        tag = (opts["tag"] + "_") if opts.get("tag") else ""
        bef = opts.get("before")
        eras_sheet(src, os.path.join(outd, tag + "eras_128_48.png"), Q.COMMANDERS, bef)
        leaders_sheet(src, os.path.join(outd, tag + "leaders_moods_138_80.png"), bef)
        ruler_sheet(src, os.path.join(outd, tag + "ruler_eras_104_74.png"), bef)
        masters_any(src, ["cmd_%s%s%s" % (c, e, m) for c in Q.COMMANDERS for e in Q.ERAS[1:] for m in ("", "_smile")],
                    os.path.join(outd, tag + "eras_masters_256.png"), cols=6)
        masters_any(src, ["ldr_%s%s" % (x, m) for x in Q.LEADERS for m in Q.LEADER_MOODS],
                    os.path.join(outd, tag + "leaders_masters_256.png"), cols=5)
        masters_any(src, ["ruler" + e for e in Q.ERAS], os.path.join(outd, tag + "ruler_masters_256.png"), cols=4)
        print("wrote", outd)
        return
    ids = opts.get("ids", ",".join(Q.COMMANDERS)).split(",")
    have = [c for c in ids if Q.path_of(src, "cmd_" + c)]
    miss = [c for c in ids if c not in have]
    if miss:
        print("missing (skipped):", " ".join(miss))
    tag = (opts["tag"] + "_") if opts.get("tag") else ""
    masters(src, have, os.path.join(outd, tag + "masters_512.png"))
    plates(src, have, os.path.join(outd, tag + "plates_128_64.png"))
    silhouettes(src, have, os.path.join(outd, tag + "silhouettes_48.png"))
    if opts.get("before"):
        side_by_side(opts["before"], src, have, os.path.join(outd, tag + "before_after.png"), ("current", "new"))
    if opts.get("alt"):
        alt_ids = [c for c in have if Q.path_of(opts["alt"], "cmd_" + c)]
        side_by_side(src, opts["alt"], alt_ids, os.path.join(outd, tag + "alt.png"),
                     ("new", opts.get("alt-label", "alternative")), width=384)
    print("wrote", outd)


if __name__ == "__main__":
    main()
