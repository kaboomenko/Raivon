"""Review sheets for the human / agent checks P-A2 and P-A4 (docs/art_direction.md §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_sheets.py PORTRAIT_DIR OUT_DIR [--seed=7]

Writes into OUT_DIR:
- silhouettes_48.png + silhouettes_key.txt: every era-1 calm portrait present (12 commanders, 10 leaders, the ruler)
  as a black 48 px alpha mask, unlabeled, in a shuffled order. P-A2: a reviewer names each commander from the shape
  alone (>= 11 of 12) BEFORE opening the key.
- moods_blind.png + moods_key.txt: every leader mood present at the 138 px seal and the 80 px dialog-row size on its
  state plate, shuffled, numbered. P-A4: the reviewer labels calm / angry / cunning / smile / tired (>= 45 of 50, no
  mood below 8 of 10).
A folder that holds only some of the 150 names is fine (a sheet with nothing to show is skipped).
"""
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402


def main():
    pos, opts = Q.parse(sys.argv[1:])
    d, out = pos[0], pos[1]
    os.makedirs(out, exist_ok=True)
    rng = random.Random(int(opts.get("seed", 7)))
    Q.report_missing(d)

    ids = ["cmd_" + c for c in Q.COMMANDERS] + ["ldr_" + x for x in Q.LEADERS] + ["ruler"]
    ids = [i for i in ids if Q.path_of(d, i)]
    rng.shuffle(ids)
    if ids:
        cell, cols = 64, 8
        sheet = Image.new("RGB", (cols * cell, ((len(ids) + cols - 1) // cols) * (cell + 14)), "white")
        dr = ImageDraw.Draw(sheet)
        for k, i in enumerate(ids):
            m = Q.alpha_mask(Q.load(Q.path_of(d, i)), 48)
            tile = Image.fromarray(np.where(m, 0, 255).astype(np.uint8)).convert("RGB")
            x, y = (k % cols) * cell, (k // cols) * (cell + 14)
            sheet.paste(tile, (x + (cell - tile.width) // 2, y))
            dr.text((x + 2, y + cell - 4), str(k + 1), fill=(200, 0, 0))
        sheet.save(os.path.join(out, "silhouettes_48.png"))
        with open(os.path.join(out, "silhouettes_key.txt"), "w") as f:
            f.write("\n".join("%d %s" % (k + 1, i) for k, i in enumerate(ids)) + "\n")

    items = [(x, m) for x in Q.LEADERS for m in Q.LEADER_MOODS if Q.path_of(d, "ldr_" + x + m)]
    rng.shuffle(items)
    if items:
        cw, ch, cols = 138 + 80 + 18, 176, 5
        sheet = Image.new("RGB", (cols * cw, ((len(items) + cols - 1) // cols) * ch), (247, 238, 220))
        dr = ImageDraw.Draw(sheet)
        for k, (x, m) in enumerate(items):
            im = Q.load(Q.path_of(d, "ldr_" + x + m))
            plate = Q.hex_rgb(Q.LEADER_PLATE[x])
            px, py = (k % cols) * cw, (k // cols) * ch
            ox = px + 4
            for wd in (138, 80):
                r = Q.resize_rgba(im, wd)
                rgb = Q.over_plate(r, plate)
                sheet.paste(Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)), (ox, py + 4))
                ox += wd + 6
            dr.text((px + 4, py + ch - 14), str(k + 1), fill=(160, 0, 0))
        sheet.save(os.path.join(out, "moods_blind.png"))
        with open(os.path.join(out, "moods_key.txt"), "w") as f:
            f.write("\n".join("%d %s %s" % (k + 1, x, (m or "_calm")[1:]) for k, (x, m) in enumerate(items)) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
