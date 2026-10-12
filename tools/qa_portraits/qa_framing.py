"""P-A6 files and framing (docs/art_direction.md §7.12, §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_framing.py PORTRAIT_DIR [--strict]

Per file (every number is a fraction of the file's own size, so 512 and 256 masters are judged alike):
- size: cmd_* 512×588, ldr_* and ruler* 256×294 (§7.12); aspect 0.8707 +- 0.003; RGBA with transparent top corners;
- top: the highest opaque row >= 0.051 h (30 px of 588); the ruler and the leaders (crown, headgear) >= 0.085 h; a
  designed overflow (the kit's meta "top_exempt" ID group: Rai's banner) is printed and the rest of the figure gated;
- sides: above 0.70 h nothing within 0.055 w of either side (the album crop, the fan, the chip);
- fringe: semi-transparent edge pixels darker than L* 6 <= 1 % (un-premultiplied black halos);
- with the kit's meta/<name>.json: eye line 0.425 h +- 0.01, head centre x 0.50 w +- 0.025, chin <= 0.65 h,
  signature box inside x 0.06-0.94 w, head box inside the army chip circle (centre 0.50 w, 0.40 h, r 0.39 w).
Size and framing problems are counted separately (the current 256 px set fails "size" for all 96 commanders by
design: §7.12 moves them to 512). A folder that holds only some of the 150 names is fine: the missing ones are listed.
Exit 1 with --strict when any present file has a problem.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402


def check(d, n):
    im = Q.load(os.path.join(d, n + ".png"))
    h, w = im.shape[:2]
    a = im[..., 3]
    size, prob = [], []
    want = Q.SIZE[Q.kind(n)]
    if (w, h) != want:
        size.append("size %dx%d (want %dx%d)" % (w, h, want[0], want[1]))
    if abs(w / h - Q.ASPECT) > 0.003:
        prob.append("aspect %.4f" % (w / h))
    if max(a[0, 0], a[0, -1]) > 0.02:
        prob.append("top corner alpha")
    rows = np.where((a > 0.5).sum(axis=1) >= 2)[0]
    overflow = ""
    m0 = Q.meta(d, n) or {}
    if m0.get("top_exempt") and len(rows):
        # a designed overflow of the top (Rai's banner, §7.2 "знамя за верх кадра"; meta top_exempt names its ID
        # group): the gate reads the rest of the figure, the overflow is printed (as portrait_qa's P-A6 does)
        masks, _ = Q.ids(d, n)
        if masks is not None and m0["top_exempt"] in masks:
            rest = (a > 0.5) & ~masks[m0["top_exempt"]]
            rows_r = np.where(rest.sum(axis=1) >= 2)[0]
            if len(rows_r):
                overflow = "  %s by design from %.3f h" % (m0["top_exempt"], rows[0] / h)
                rows = rows_r
    top = rows[0] / h if len(rows) else 1.0
    tmin = Q.TOP_MIN if n.startswith("cmd_") else Q.TOP_MIN_HEADGEAR
    if top < tmin:
        prob.append("top %.3f h (%d px; min %.3f)" % (top, rows[0], tmin))
    upper = a[: int(h * Q.SIDE_ROWS)] > 0.5
    cols = np.where(upper.any(axis=0))[0]
    if len(cols) and (cols[0] < Q.SIDE_FREE * w or cols[-1] > w - 1 - Q.SIDE_FREE * w):
        prob.append("side x %d..%d (free band %.0f px)" % (cols[0], cols[-1], Q.SIDE_FREE * w))
    edge = (a > 0.02) & (a < 0.6)
    if edge.sum():
        L = Q.srgb_to_lab(im[..., :3])[..., 0]
        dark = (edge & (L < 6)).sum() / edge.sum()
        if dark > 0.01:
            prob.append("dark fringe %.1f%%" % (dark * 100))
    m = Q.meta(d, n)
    info = ""
    if m:
        ey = m["eye_y"] / h
        hb = m["head_box"]
        hx = (hb[0] + hb[2]) / 2 / w
        info = "eye %.3f h  head x %.3f w  chin %.3f h  top %.3f h" % (ey, hx, m["chin_y"] / h, top)
        if abs(ey - Q.EYE_Y[0]) > Q.EYE_Y[1]:
            prob.append("eye y %.3f h" % ey)
        if abs(hx - Q.HEAD_X[0]) > Q.HEAD_X[1]:
            prob.append("head x %.3f w" % hx)
        if m["chin_y"] / h > Q.CHIN_MAX:
            prob.append("chin %.3f h" % (m["chin_y"] / h))
        sb = m.get("sig_box")
        if sb and (sb[0] < Q.SIG_X[0] * w or sb[2] > Q.SIG_X[1] * w):
            prob.append("signature x %d..%d" % (sb[0], sb[2]))
        cx, cy, r = Q.CHIP[0] * w, Q.CHIP[1] * h, Q.CHIP[2] * w
        far = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x in (hb[0], hb[2]) for y in (hb[1], hb[3]))
        # the corners of the box are farther than the round head; judge the box's edge midpoints
        mids = [((hb[0] + hb[2]) / 2, hb[1]), ((hb[0] + hb[2]) / 2, hb[3]), (hb[0], (hb[1] + hb[3]) / 2),
                (hb[2], (hb[1] + hb[3]) / 2)]
        out = max(((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 for x, y in mids)
        if out > r:
            prob.append("head outside the chip circle (%.0f > %.0f px)" % (out, r))
        info += "  chip %.0f/%.0f px (corner %.0f)" % (out, r, far)
    info += overflow
    return size, prob, top, info


def main():
    pos, opts = Q.parse(sys.argv[1:])
    d = pos[0]
    have, miss = Q.report_missing(d)
    n_size = n_frame = 0
    worst_top = (1.0, "")
    for n in have:
        size, prob, top, info = check(d, n)
        worst_top = min(worst_top, (top, n))
        n_size += bool(size)
        n_frame += bool(prob)
        if size or prob or info:
            print("%-22s %s%s" % (n, "; ".join(size + prob) or "ok", ("   [" + info + "]") if info else ""))
    print("highest point: %.3f h (%s)" % worst_top)
    print("size problems: %d files; framing problems: %d files (of %d present)" % (n_size, n_frame, len(have)))
    fails = n_size + n_frame
    print("RESULT", "FAIL" if fails else "PASS", n_frame, "framing +", n_size, "size")
    sys.exit(1 if fails and "strict" in opts else 0)


if __name__ == "__main__":
    main()
