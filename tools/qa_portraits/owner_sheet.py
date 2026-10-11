"""Owner-facing contact sheets for a portrait step (docs/dev/portraits_plan.json "Owner-facing sheets"). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/owner_sheet.py NEW_DIR OUT_DIR [--before=DIR] [--alt=DIR] [--alt-label=TEXT]
                                                [--ids=bram,lira,...] [--tag=NAME]

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


def main():
    pos, opts = Q.parse(sys.argv[1:])
    src, outd = pos[0], pos[1]
    os.makedirs(outd, exist_ok=True)
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
