"""C-2 / C-3 / C-4 / C-5 of docs/art_direction.md §7.14 on finished chest and crate icons (numpy + Pillow).

Usage:
  python3 -I tools/qa_icons/chest_qa.py OUT_DIR NAME=PATH [NAME=PATH ...] [--masks=DIR] [--strict]
  e.g. chest_qa.py out wood=…/chest_wood.png silver=… royal=… cards=… crate=… gift=… --masks=out/masks

Per icon (alpha > 0.5 mask, ink rim included, which is what the player sees):
- mirror IoU about the mask's own bbox centre                                   (C-2: >= 0.98)
- lean: lines fitted to the left and right silhouette edges over the body band (50–88 % of the bbox height);
  asym = the mean of the two edge angles, conv = half their difference          (C-1: |asym| <= 0.5°)
- bbox width at 128 px (family size)
- mean L* of the opaque pixels at 48 px                                         (C-4: silver > wood > royal,
                                                                                 pairwise >= 8)
With --masks=DIR (tools/qa_icons/masks.py, renders <icon>_ids.png / <icon>_units.png at the raw size):
- lock: the lock's own blob at 48 px (coverage > 0.5): bbox ≥ 5 px on its short side, and its contrast (ΔE76 of
  the lock pixels against the ring of chest pixels round it) on cream #F7EEDC and on the tier tile   (C-5)
- iron: the share of the model's pixels that belong to dark-iron parts (materials iron*)   (C-5: <= 15 %);
  also, for information, the share of those pixels that render darker than L* 40 («visibly dark iron»)
- crates: each box's own pixels at 48 px (>= 150, C-5: three crates distinct) and, for information, the seam
  between touching boxes (L* of the boundary pixels below the boxes' median) — judge the read on the sheet
Names: wood silver royal cards crate gift (the tier tile follows the name: Kit.RARITY common, rare, epic, legendary).
Writes OUT_DIR/chest_report.txt and OUT_DIR/chest_sheet.png (128/64/48 on cream and on the tier tile, the 48 px
black silhouette). Exit 1 with --strict on any FAIL.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

CREAM = np.array([0xF7, 0xEE, 0xDC]) / 255
TILE = {"wood": "a7afbc", "silver": "3e9bf0", "royal": "a65bf2", "cards": "ff9a1f"}  # ui_kit.gd Kit.RARITY
ICON = {"wood": "chest_wood", "silver": "chest_silver", "royal": "chest_royal", "cards": "chest_cards"}
IOU_MIN, LEAN_MAX, LADDER_GAP, LOCK_PX, IRON_MAX = 0.98, 0.5, 8.0, 5, 0.15


def hexc(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]) / 255


def srgb_to_lab(rgb):
    """rgb in 0..1, shape (...,3) -> L*a*b* (D65)."""
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def resize(a, w, h):
    """Lanczos on premultiplied RGBA (the pipeline's downscale), returns straight RGBA."""
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    chans = [np.asarray(Image.fromarray((pm[..., i] * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS),
                        dtype=np.float64) / 255 for i in range(4)]
    out = np.stack(chans, -1)
    al = np.clip(out[..., 3:4], 1e-6, 1)
    out[..., :3] = np.clip(out[..., :3] / al, 0, 1)
    return out


def box_down(m, w):
    """Area-average a coverage map (0..1) down to w × w."""
    return np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((w, w), Image.BOX),
                      dtype=np.float64) / 255


def load(p):
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float64) / 255
    if a.shape[0] != 128:
        a = resize(a, 128, 128)
    return a


def comp(a, bg):
    return a[..., :3] * a[..., 3:4] + bg * (1 - a[..., 3:4])


def mirror_iou(m):
    ys, xs = np.where(m)
    sub = m[:, xs.min():xs.max() + 1]
    fl = sub[:, ::-1]
    return float(np.logical_and(sub, fl).sum()) / max(1, np.logical_or(sub, fl).sum())


def edge_angles(m):
    ys, xs = np.where(m)
    y0, y1 = ys.min(), ys.max()
    L, R, Y = [], [], []
    for y in range(int(y0 + 0.50 * (y1 - y0)), int(y0 + 0.88 * (y1 - y0)) + 1):  # the body band, under the lid
        xr = np.where(m[y])[0]
        if len(xr) < 4:
            continue
        L.append(xr.min()), R.append(xr.max()), Y.append(y)
    Y = np.array(Y, float)
    al = np.degrees(np.arctan(np.polyfit(Y, np.array(L, float), 1)[0]))  # + = the edge runs right going down
    ar = np.degrees(np.arctan(np.polyfit(Y, np.array(R, float), 1)[0]))
    return -(al + ar) / 2, (ar - al) / 2  # asym (+ = the top leans right), conv (> 0: wider at the bottom)


def components(m):
    """4-connected components of a boolean map: a list of (ys, xs) arrays, largest first."""
    seen = np.zeros_like(m, bool)
    out = []
    for y, x in zip(*np.where(m)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        p = np.array(pts)
        out.append((p[:, 0], p[:, 1]))
    return sorted(out, key=lambda c: -len(c[0]))


def dilate(m, r=1):
    o = m.copy()
    for _ in range(r):
        o = o | np.roll(o, 1, 0) | np.roll(o, -1, 0) | np.roll(o, 1, 1) | np.roll(o, -1, 1)
    return o


def mask_checks(name, a, masks, lines):
    """C-5 from the ID passes; returns the number of FAILs."""
    icon = ICON.get(name, name)
    fails = 0
    p = os.path.join(masks, icon + "_ids.png")
    if not os.path.exists(p):
        return 0
    ids = np.asarray(Image.open(p).convert("RGBA")).astype(np.float64) / 255
    cov = ids[..., 3]
    lock, iron = ids[..., 0] * cov, ids[..., 1] * cov
    share = float(iron.sum() / max(cov.sum(), 1e-6))
    dark = None
    raw = os.path.join(masks, "..", "raw", icon + ".png")
    if os.path.exists(raw):  # the 256 master the masks were drawn over (<masks>/../raw/<icon>.png)
        rr = np.asarray(Image.open(raw).convert("RGBA")).astype(np.float64) / 255
        if rr.shape[:2] == iron.shape:
            dark = float((iron * (srgb_to_lab(rr[..., :3])[..., 0] < 40)).sum() / max(cov.sum(), 1e-6))
    bad = share > IRON_MAX
    fails += bad
    lines.append("%s %-8s iron %.1f %% of the model (gate <= %.0f %%); rendering darker than L* 40: %s (info)" % (
        "FAIL" if bad else "PASS", name, 100 * share, 100 * IRON_MAX, "n/a" if dark is None else "%.1f %%" % (100 * dark)))
    if lock.max() > 0.5:  # icons without a lock (crate, gift) skip the lock check
        lk = box_down(lock, 48) > 0.5
        model = box_down(cov, 48) > 0.5
        comps = components(lk)
        if not comps:
            lines.append("FAIL %-8s lock: no blob at 48 px" % name)
            return fails + 1
        ys, xs = comps[0]
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        blob = np.zeros_like(lk)
        blob[ys, xs] = True
        ring = dilate(blob, 2) & ~dilate(blob, 0) & model & ~lk
        s48 = resize(a, 48, 48)
        cons = []
        for label, bg in (("cream", CREAM), ("tile", hexc(TILE.get(name, "a7afbc")))):
            lab = srgb_to_lab(comp(s48, bg))
            cons.append((label, float(np.linalg.norm(lab[blob].mean(0) - lab[ring].mean(0)))))
        bad = min(w, h) < LOCK_PX or min(c for _, c in cons) < 15
        fails += bad
        lines.append("%s %-8s lock blob at 48 px %d x %d px (gate >= %d), %d px; contrast dE76 %s (gate >= 15)" % (
            "FAIL" if bad else "PASS", name, w, h, LOCK_PX, len(ys), ", ".join("%s %.0f" % c for c in cons)))
    pu = os.path.join(masks, icon + "_units.png")
    if os.path.exists(pu):
        u = np.asarray(Image.open(pu).convert("RGBA")).astype(np.float64) / 255
        units = [box_down(u[..., k] * u[..., 3], 48) > 0.5 for k in range(3)]
        L = srgb_to_lab(comp(resize(a, 48, 48), CREAM))[..., 0]
        sizes = [int(m.sum()) for m in units]
        seams = []
        for i, j in ((0, 1), (0, 2), (1, 2)):
            bi = units[i] & dilate(units[j], 1)
            bj = units[j] & dilate(units[i], 1)
            border = bi | bj
            if border.sum() == 0:
                continue
            body = (units[i] | units[j]) & ~dilate(border, 1)
            seams.append(("%d/%d" % (i, j), float(np.median(L[body]) - L[border].mean())))
        bad = min(sizes) < 150
        fails += bad
        lines.append("%s %-8s crates at 48 px: %s px each (gate >= 150); seam L* below the boxes %s (info)" % (
            "FAIL" if bad else "PASS", name, "/".join(map(str, sizes)), ", ".join("%s %.0f" % s for s in seams)))
    return fails


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    items = [a.split("=", 1) for a in sys.argv[2:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[2:] if a.startswith("--") and "=" in a)
    lines, rows, lstar, fails = [], [], {}, 0
    for name, path in items:
        a = load(path)
        m = a[..., 3] > 0.5
        mi = mirror_iou(m)
        asym, conv = edge_angles(m)
        xs = np.where(m.any(0))[0]
        width = xs.max() - xs.min() + 1
        s48 = resize(a, 48, 48)
        L = float(srgb_to_lab(s48[..., :3])[..., 0][s48[..., 3] > 0.9].mean())
        lstar[name] = L
        bad = mi < IOU_MIN or abs(asym) > LEAN_MAX
        fails += bad
        lines.append("%s %-8s mirrorIoU %.3f  lean(asym) %+.2f deg  converge %+.1f deg  width128 %3d px  L*48 %.1f" % (
            "FAIL" if bad else "PASS", name, mi, asym, conv, width, L))
        rows.append((name, a))
    for name, path in items:
        if "masks" in opts:
            fails += mask_checks(name, load(path), opts["masks"], lines)
    ladder = [n for n in ("silver", "wood", "royal") if n in lstar]
    if len(ladder) == 3:
        order = lstar["silver"] > lstar["wood"] > lstar["royal"]
        gaps = sorted((abs(lstar[x] - lstar[y]), x, y) for x, y in itertools.combinations(ladder, 2))
        bad = not order or gaps[0][0] < LADDER_GAP
        fails += bad
        lines.append("%s tier ladder L*48: %s; order silver > wood > royal %s; smallest gap %.1f (%s/%s), gate >= %.0f%s" % (
            "FAIL" if bad else "PASS", ", ".join("%s %.1f" % (n, lstar[n]) for n in ladder), "yes" if order else "NO",
            gaps[0][0], gaps[0][1], gaps[0][2], LADDER_GAP, "; cards %.1f" % lstar["cards"] if "cards" in lstar else ""))
    lines.append("RESULT %s %d" % ("FAIL" if fails else "PASS", fails))
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(out, "chest_report.txt"), "w").write(txt + "\n")
    # the sheet: per icon a column — 128 / 64 / 48 on cream, the same on its tier tile, and the 48 px black shape
    col, H = 150, 4 + (128 + 64 + 48 + 12) * 2 + 48 + 30
    sh = Image.new("RGB", (8 + len(rows) * col, H), (214, 218, 226))
    d = ImageDraw.Draw(sh)
    for i, (name, a) in enumerate(rows):
        x, y = 8 + i * col, 4
        for bg in (CREAM, hexc(TILE.get(name, "a7afbc"))):
            for s in (128, 64, 48):
                t = resize(a, s, s)
                tile = Image.new("RGB", (s + 8, s + 4), tuple(int(c * 255) for c in bg))
                tile.paste(Image.fromarray((comp(t, bg) * 255).astype(np.uint8)), (4, 2))
                sh.paste(tile, (x, y))
                y += s + 4
        sil = np.where(resize(a, 48, 48)[..., 3] > 0.5, 25, 255).astype(np.uint8)
        sh.paste(Image.fromarray(sil).convert("RGB"), (x + 4, y))
        d.text((x + 60, y + 18), name, fill=(30, 30, 30))
    sh.save(os.path.join(out, "chest_sheet.png"))
    sys.exit(1 if fails and "--strict" in sys.argv else 0)


if __name__ == "__main__":
    main()
