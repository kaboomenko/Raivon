"""C-1 / C-2 / C-3 of docs/art_direction.md §7.14 on the shipped chest and crate icons (image-based, numpy + Pillow).

Usage: python3 -I tools/qa_icons/qa_chest.py ICON_DIR [names ...] [--strict]
       (default names: chest_wood chest_silver chest_royal chest_cards crate gift)

Per icon, on the alpha mask (alpha > 0.5; the ink rim is part of it — it is symmetric, so it biases nothing):
- mirror IoU: the mask against its own mirror image about the bbox centre. Gate C-2: >= 0.98.
- lean: the left and right outer edges of the silhouette over the body band (rows 40..90 % of the bbox height) are
  fitted with a line each; theta > 0 means the top of that edge leans to screen right. lean = (thetaL + thetaR) / 2
  is the ASYMMETRIC part (everything falling one way: what reads as «crooked»), conv = (thetaR - thetaL) / 2 the
  symmetric part (> 0 = wider at the top). Gate C-1: |lean| <= 0.5 deg. conv is printed for information only: on a
  chest the band runs from the lid's lip overhang in to the flared body and out to the boots, so it measures the
  shape, not the camera (the research prototype of §7.13 reads 13.8–16.3 deg here). The camera keystone — §7.14's
  «symmetric keystone <= 12 deg per side» — is measured geometrically by measure_lean.py (the tapered body edge).
- body width at 75 % of the bbox height (px at 128): the closed chests and the open card chest within +-2 px of each
  other (C-3; spread <= 4 px).
Prints one line per icon and RESULT PASS|FAIL <count>; exit 1 with --strict on any FAIL.
"""
import os
import sys

import numpy as np
from PIL import Image

LEAN_MAX, IOU_MIN, SPREAD_MAX = 0.5, 0.98, 4.0
DEFAULT = ["chest_wood", "chest_silver", "chest_royal", "chest_cards", "crate", "gift"]
FAMILY = ("chest_wood", "chest_silver", "chest_royal", "chest_cards")


def load(path):
    """RGBA as float32 0..1."""
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0


def path_of(d, name):
    for p in (os.path.join(d, name + ".png"), os.path.join(d, "icons", name + ".png")):
        if os.path.exists(p):
            return p
    return None


def measure(path):
    im = load(path)
    a = im[..., 3] > 0.5
    ys, xs = np.where(a)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    sub = a[y0:y1 + 1, x0:x1 + 1]
    m_iou = (sub & sub[:, ::-1]).sum() / (sub | sub[:, ::-1]).sum()
    hh = y1 - y0 + 1
    L, R, Y = [], [], []
    for y in range(y0 + int(hh * 0.40), y0 + int(hh * 0.90)):
        xr = np.where(a[y])[0]
        if len(xr):
            L.append(xr[0])
            R.append(xr[-1])
            Y.append(y)
    Y = np.array(Y, float)
    # x = k*y + c ; y grows downward, so a top leaning right has dx/dy < 0
    tl = -np.degrees(np.arctan(np.polyfit(Y, np.array(L, float), 1)[0]))
    tr = -np.degrees(np.arctan(np.polyfit(Y, np.array(R, float), 1)[0]))
    yb = y0 + int(hh * 0.75)
    xr = np.where(a[yb])[0]
    width = (xr[-1] - xr[0] + 1) * 128.0 / a.shape[1]
    return float(m_iou), float((tl + tr) / 2), float((tr - tl) / 2), float(width)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d, names = args[0], args[1:] or DEFAULT
    strict = "--strict" in sys.argv
    fails, widths = 0, {}
    for n in names:
        p = path_of(d, n)
        if not p:
            print("%-14s missing" % n)
            continue
        mi, lean, conv, wd = measure(p)
        bad = mi < IOU_MIN or abs(lean) > LEAN_MAX
        fails += bad
        if n in FAMILY:
            widths[n] = wd
        print("%-14s mirror IoU %.3f  lean %+5.2f deg  (conv %+5.2f deg, info)  body width %5.1f px@128 %s"
              % (n, mi, lean, conv, wd, "FAIL" if bad else "ok"))
    if len(widths) > 1:
        spread = max(widths.values()) - min(widths.values())
        print("chest family body width spread %.1f px@128 (gate <= %.0f) %s"
              % (spread, SPREAD_MAX, "FAIL" if spread > SPREAD_MAX else "ok"))
        fails += spread > SPREAD_MAX
    print("RESULT", "FAIL" if fails else "PASS", fails)
    sys.exit(1 if fails and strict else 0)


if __name__ == "__main__":
    main()
