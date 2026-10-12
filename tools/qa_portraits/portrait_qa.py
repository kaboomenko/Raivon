"""Portrait acceptance checks, all in one report (docs/art_direction.md §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/portrait_qa.py PORTRAIT_DIR OUT_DIR [--strict]

Reads <name>.png for the 150 names of §7.12 (a folder with only some of them is fine: the missing ones are listed and
every check runs on what exists). When the kit wrote its sidecars into PORTRAIT_DIR (portrait_assets.py
--sidecars=PORTRAIT_DIR), they are used too:
  meta/<name>.json  projected landmarks in PNG px (eye_y, chin_y, crown_y, skyline_y, head_box, sig_box, h_px, iris
                    centres, eye openings, brow end points, mouth corners), the contact report ("floating",
                    "contacts"), the P-A8 detail thresholds ("details") and, for glasses, "lens_iris_contrast";
  ids/<name>.png    the flat part-ID pass (same camera, 1 sample, box filter), its colour table in ids/<name>.json:
                    skin, hair, beard, brow, sclera, iris, pupil, catch, lash, mouth, lip, teeth, tongue, nose, costume,
                    metal, prop, signature, glass and detail:<name>.
Checks (PASS / FAIL / INFO with numbers, one line each, into OUT_DIR/report.txt):
  P-A6 files      names, sizes (cmd 512×588, ldr/ruler 256×294), aspect, transparent top corners
  P-A6 framing    top >= 0.051 h (ruler / leaders 0.085 h), side band, and with meta: eye 0.425 h +- 0.01,
                  head x 0.50 w +- 0.025, chin <= 0.65 h
  P-A1            head-zone IoU at 48 px: commander pairs <= 0.85 (median <= 0.78), leader-commander and leader pairs
                  <= 0.85, eras >= 0.70; sheet sil48.png
  P-A5            shoulder band vs plate B (gated) and today's plate (INFO), both rarity palettes; rim <= 35 %;
                  with ids: hair/brow/iris/beard/signature/lit-cheek rules (qa_contrast.id_rules)
  P-A4            leader moods at 64 px (INFO here; qa_moods.py gates); sheet faces64.png
  P-A3 (ids)      at 128 px: brows >= 3 px thick, eye opening >= 6 px, iris >= 4 px, a catchlight pixel > 0.85,
                  closed mouth >= 2 px, open mouth >= 40 px²; at 64 px: brows >= 2 px thick and >= 6 px long (each
                  brow = the connected parts nearest its iris, not a cut midway between the irises), eye
                  opening >= 3 px, pupil >= 2 px, open mouth >= 6 px², signature >= 20 px; at 48 px the signature
                  alone >= 8 % of the head-zone mask; irises behind glasses keep >= 70 % of their contrast; seated
                  eyes: <= 2 % of each eye's sclera / iris / pupil pixels outside the lids' outline (meta eye_almond).
                  What "seated" covers: eye_almond comes from the same face.Almond that clips the lens, so this is a
                  regression guard — it catches a lid shell that no longer covers the lens top, an eye drawn over
                  the face's outline or a shifted almond; it cannot prove the eye sits in its lids (a white sliver
                  under the rim inside the outline passes): judge that on the face crops at 512. A winking eye
                  (meta "wink", or lids shut by design < 0.12) skips its opening, iris, pupil and catchlight; its
                  brow keeps both brow gates; a P3 mood (angry, cunning, tired) reports its eye sizes as INFO (the
                  P-A4 mood bands gate them against the calm face)
  P-A4 smile      calm / smile pairs with meta: both mouth corners >= 6 px higher, in the picture and with the pose
                  held (head-local corners); open smiles: cavity >= 900 px² on the master, teeth visible
  P-A4 bands      each leader mood vs its calm (meta brows, pupils, eye openings, gaze, pose): angry brows' inner
                  ends down >= 20 deg, pupil <= 0.85; tired opening 0.30-0.50, brows' inner ends up >= 12 deg;
                  cunning brow difference +0.06 H, glance >= 25 % of the eye width, roll >= 4 deg
  P-A7            meta "floating" empty; one alpha island; every detail:* at least its P-A8 pixel count (a detail the
                  kit measures on another group says so in meta "detail_groups": Hawk's helmet = the "hat", which
                  holds only the cap and its flaps; a part of one surface gets its own group instead — Vik's hood
                  peak is detail:hood_peak, the hood's faces outside the hood built without it)
  P-A8 extra      Vega's raised brow >= 15 px, Kort's lids <= 0.6, Rai's iris L* 70-85, Irma's orange >= 3 %
  P-A9            the mean dE76 of the four largest colour groups (hair + beard, clothes, hat or skin, signature)
                  between any two era-1 commanders >= 15 (matrix in OUT_DIR/de76_matrix.txt); signatures unique
Exit 1 with --strict if any FAIL.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402
from qa_contrast import band_stats, id_rules, plates_for, rim_share  # noqa: E402


class Report:
    def __init__(self):
        self.lines, self.fails = [], 0

    def add(self, status, check, msg):
        if status == "FAIL":
            self.fails += 1
        self.lines.append("%-4s %-24s %s" % (status, check, msg))


def islands(alpha):
    """Number of 4-connected opaque islands larger than 4 px (PIL flood fill)."""
    arr = ((alpha > 0.5) * 255).astype(np.uint8)
    n = 0
    for _ in range(500):
        ys, xs = np.nonzero(arr == 255)
        if not len(ys):
            break
        im = Image.fromarray(arr).copy()  # a writable copy: fromarray may wrap a read-only buffer
        ImageDraw.floodfill(im, (int(xs[0]), int(ys[0])), 100)
        new = np.asarray(im)
        filled = new == 100
        if not filled.any():  # never loop on a fill that did nothing
            arr[ys[0], xs[0]] = 0
            continue
        arr = np.where(filled, 0, arr).astype(np.uint8)
        if int(filled.sum()) > 4:
            n += 1
            if n >= 50:
                break
    return n


def check_files(d, have, miss, rep):
    imgs = {}
    bad_size, bad_aspect, opaque = [], [], []
    for n in have:
        a = Q.load(os.path.join(d, n + ".png"))
        imgs[n] = a
        h, w = a.shape[:2]
        if (w, h) != Q.SIZE[Q.kind(n)]:
            bad_size.append(n)
        if abs(w / h - Q.ASPECT) > 0.003:
            bad_aspect.append(n)
        if max(a[0, 0, 3], a[0, -1, 3]) > 0.02:
            opaque.append(n)
    rep.add("INFO" if miss else "PASS", "P-A6 files", "%d/150 present%s" % (len(have), (", missing %d (e.g. %s)" % (
        len(miss), " ".join(miss[:5]))) if miss else ""))
    rep.add("FAIL" if bad_size else "PASS", "P-A6 sizes", "%d of %d files off-size%s" % (
        len(bad_size), len(have), (": " + " ".join(bad_size[:6]) + (" ..." if len(bad_size) > 6 else "")) if bad_size else ""))
    rep.add("FAIL" if bad_aspect else "PASS", "P-A6 aspect 0.8707", "%d off-aspect" % len(bad_aspect))
    rep.add("FAIL" if opaque else "PASS", "P-A6 transparent", "opaque top corners in %d files" % len(opaque))
    return imgs


def check_framing(d, imgs, rep):
    tops, side, metas, ex_rows = [], [], [], []
    for n, a in imgs.items():
        al = a[..., 3] > 0.5
        h, w = al.shape
        rows = np.where(al.sum(1) >= 2)[0]
        if not len(rows):
            continue
        tmin = Q.TOP_MIN if n.startswith("cmd_") else Q.TOP_MIN_HEADGEAR
        m0 = Q.meta(d, n) or {}
        ex = m0.get("top_exempt")
        if ex:
            # a designed overflow of the top (Rai's banner, §7.2 "знамя за верх кадра"): the gate reads the rest of
            # the figure (the ID pass's other groups), the overflow is reported
            masks, _ = Q.ids(d, n)
            if masks is not None and ex in masks:
                rest = al & ~masks[ex]
                rows_r = np.where(rest.sum(1) >= 2)[0]
                if len(rows_r):
                    ex_rows.append("%s %s from %.3f h, the rest from %.3f h" % (n, ex, rows[0] / h, rows_r[0] / h))
                    rows = rows_r
        tops.append((rows[0] / h, n, tmin))
        cols = np.where(al[: int(h * Q.SIDE_ROWS)].any(0))[0]
        if len(cols) and (cols[0] < Q.SIDE_FREE * w or cols[-1] > w - 1 - Q.SIDE_FREE * w):
            side.append(n)
        m = Q.meta(d, n)
        if m:
            hb = m["head_box"]
            metas.append((n, m["eye_y"] / h, (hb[0] + hb[2]) / 2 / w, m["chin_y"] / h, m.get("skyline_y", rows[0]) / h))
    tops.sort()
    lo = [t for t in tops if t[0] < t[2]]
    rep.add("FAIL" if lo else "PASS", "P-A6 top", "highest point %.3f h (%s); %d files above their minimum%s" % (
        tops[0][0], tops[0][1], len(lo), (": " + " ".join(t[1] for t in lo[:6])) if lo else ""))
    if ex_rows:
        rep.add("INFO", "P-A6 top overflow", "designed (meta top_exempt): " + "; ".join(ex_rows))
    rep.add("FAIL" if side else "PASS", "P-A6 side band", "%d files within %.3f w of a side above %.2f h%s" % (
        len(side), Q.SIDE_FREE, Q.SIDE_ROWS, (": " + " ".join(side[:6])) if side else ""))
    if not metas:
        rep.add("INFO", "P-A6 landmarks", "no meta/*.json: eye line, head x and chin not checked")
        return
    eb = [x for x in metas if abs(x[1] - Q.EYE_Y[0]) > Q.EYE_Y[1]]
    hb = [x for x in metas if abs(x[2] - Q.HEAD_X[0]) > Q.HEAD_X[1]]
    cb = [x for x in metas if x[3] > Q.CHIN_MAX]
    rep.add("FAIL" if eb else "PASS", "P-A6 eye line", "%s; %d outside 0.425 +- 0.01 h" % (
        ", ".join("%s %.3f" % (x[0], x[1]) for x in metas[:6]), len(eb)))
    rep.add("FAIL" if hb else "PASS", "P-A6 head x", "%s; %d outside 0.50 +- 0.025 w" % (
        ", ".join("%s %.3f" % (x[0], x[2]) for x in metas[:6]), len(hb)))
    rep.add("FAIL" if cb else "PASS", "P-A6 chin", "max %.3f h; %d below 0.65 h" % (max(x[3] for x in metas), len(cb)))


def check_silhouettes(imgs, rep, out):
    m = {n: Q.alpha_mask(a, 48) for n, a in imgs.items()}
    hz = {n: v[: int(v.shape[0] * 0.70)] for n, v in m.items()}
    base = [n for n in m if (n.startswith("cmd_") and n.count("_") == 1) or (n.startswith("ldr_") and n.count("_") == 1)]
    cm = [n for n in base if n.startswith("cmd_")]
    lm = [n for n in base if n.startswith("ldr_")]
    cc = sorted(((Q.iou(hz[a], hz[b]), a, b) for a, b in itertools.combinations(cm, 2)), reverse=True)
    if cc:
        med = sorted(x[0] for x in cc)[len(cc) // 2]
        bad = [x for x in cc if x[0] > 0.85]
        rep.add("FAIL" if bad or med > 0.78 else "PASS", "P-A1 commanders",
                "head IoU max %.3f (%s/%s), median %.3f, %d of %d pairs > 0.85" % (cc[0][0], cc[0][1], cc[0][2], med,
                                                                                 len(bad), len(cc)))
    else:
        rep.add("INFO", "P-A1 commanders", "fewer than 2 era-1 commanders present")
    lc = sorted(((Q.iou(hz[a], hz[b]), a, b) for a in lm for b in cm), reverse=True)
    if lc:
        bad = [x for x in lc if x[0] > 0.85]
        rep.add("FAIL" if bad else "PASS", "P-A1 leader-commander", "max %.3f (%s/%s), %d pairs > 0.85" % (
            lc[0][0], lc[0][1], lc[0][2], len(bad)))
    ll = sorted(((Q.iou(hz[a], hz[b]), a, b) for a, b in itertools.combinations(lm, 2)), reverse=True)
    if ll:
        rep.add("FAIL" if ll[0][0] > 0.85 else "PASS", "P-A1 leader pairs", "max %.3f (%s/%s)" % ll[0])
    era = []
    for c in Q.COMMANDERS + ["ruler"]:
        b = ("cmd_" + c) if c != "ruler" else "ruler"
        for e in Q.ERAS[1:]:
            if b in hz and b + e in hz:
                era.append((Q.iou(hz[b], hz[b + e]), b + e))
    if era:
        era.sort()
        bad = [x for x in era if x[0] < 0.70]
        rep.add("FAIL" if bad else "PASS", "P-A1 era identity", "min %.3f (%s), %d below 0.70" % (era[0][0], era[0][1],
                                                                                              len(bad)))
    keys = [k for k in Q.all_names() if k in m and (k.count("_") == 1 or k == "ruler")]
    cols = 12
    sh = Image.new("RGB", (cols * 64 + 8, max(1, (len(keys) + cols - 1) // cols) * 80 + 8), "white")
    dr = ImageDraw.Draw(sh)
    for i, k in enumerate(keys):
        x, y = 8 + (i % cols) * 64, 8 + (i // cols) * 80
        sh.paste(Image.fromarray(np.where(m[k], 20, 255).astype(np.uint8)), (x, y))
        dr.text((x, y + 57), k.replace("cmd_", "").replace("ldr_", "L:")[:10], fill=(90, 90, 90))
    sh.save(os.path.join(out, "sil48.png"))


def check_contrast(imgs, rep):
    for mode, gated in (("B", True), ("current", False)):
        res = []
        for n, a in imgs.items():
            if n.endswith(("_smile", "_angry", "_cunning", "_tired")):
                continue
            for tag, pc in plates_for(n):
                b = band_stats(a, pc, mode)
                if b:
                    res.append((b[0], b[1], n, tag))
        if not res:
            continue
        bad = [r for r in res if r[0] < 15 or r[1] > 0.25]
        res.sort()
        rep.add(("FAIL" if bad else "PASS") if gated else "INFO", "P-A5 band vs plate " + mode,
                "%d of %d portrait/plate pairs fail (median dL* < 15 or melt > 25%%); worst: %s" % (
                    len(bad), len(res), "; ".join("%s/%s dL %.1f melt %.0f%%" % (r[2], r[3], r[0], r[1] * 100)
                                                   for r in res[:4])))
    res = []
    for n, a in imgs.items():
        if n.endswith(("_smile", "_angry", "_cunning", "_tired")):
            continue
        for tag, pc in plates_for(n):
            r = rim_share(a, pc, "B")
            if r is not None:
                res.append((r, n, tag))
    if res:
        res.sort(reverse=True)
        bad = [r for r in res if r[0] > 0.35]
        rep.add("FAIL" if bad else "PASS", "P-A5 rim vs plate B", "%d of %d pairs > 35%%; worst %s" % (
            len(bad), len(res), ", ".join("%s/%s %.0f%%" % (r[1], r[2], r[0] * 100) for r in res[:4])))


def check_moods(imgs, rep, out):
    rows, worst = [], []
    for x in Q.LEADERS:
        ms = ["ldr_%s%s" % (x, m) for m in Q.LEADER_MOODS]
        if not all(k in imgs for k in ms):
            continue
        small = {k: Q.resize_rgba(imgs[k], 64) for k in ms}
        hh = small[ms[0]].shape[0]
        y0, y1, x0, x1 = int(hh * 0.30), int(hh * 0.70), 14, 50
        labs = {k: Q.srgb_to_lab(small[k][y0:y1, x0:x1, :3])[..., 0] for k in ms}
        for a, b in itertools.combinations(ms, 2):
            worst.append((float((np.abs(labs[a] - labs[b]) > 6).mean()), a, b))
        rows.append([small[k] for k in ms] + [Q.hex_rgb(Q.LEADER_PLATE[x])])
    if worst:
        worst.sort()
        rep.add("INFO", "P-A4 leader moods 64px", "min changed share %.3f (%s vs %s); qa_moods.py gates" % worst[0])
        sh = Image.new("RGB", (5 * 70 + 8, len(rows) * 80 + 8), (247, 238, 220))
        for j, r in enumerate(rows):
            for i, s in enumerate(r[:-1]):
                comp = Q.over_plate(s, r[-1])
                sh.paste(Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8)), (8 + i * 70, 8 + j * 80))
        sh.save(os.path.join(out, "faces64.png"))


def _split(mask, xs):
    """Split a mask into the parts nearest each x in xs (the two eyes / brows)."""
    if len(xs) < 2:
        return [mask]
    cut = (xs[0] + xs[1]) / 2
    cols = np.arange(mask.shape[1])[None, :]
    lo, hi = sorted(xs)
    return [mask & (cols < cut), mask & (cols >= cut)] if xs[0] == lo else [mask & (cols >= cut), mask & (cols < cut)]


def _components(mask):
    """Connected parts of a small mask (4-neighbour flood fill; numpy + Pillow only) -> list of bool masks."""
    ys, xs = np.nonzero(mask)
    left = set(zip(ys.tolist(), xs.tolist()))
    out = []
    while left:
        seed = left.pop()
        comp, stack = [seed], [seed]
        while stack:
            y, x = stack.pop()
            for q in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if q in left:
                    left.remove(q)
                    comp.append(q)
                    stack.append(q)
        mk = np.zeros(mask.shape, bool)
        cy, cx = zip(*comp)
        mk[list(cy), list(cx)] = True
        out.append(mk)
    return out


def _split_parts(mask, xs):
    """Split a mask of separate parts (the two brows) by its connected parts, each to the eye whose x is nearest the
    part's centre: in the 3/4 view the far brow's inner end crosses the midpoint between the irises, and the
    midpoint cut gave that end to the near brow (a far brow that starts nearer the nose measured shorter). Parts under
    6 px are ignored; falls back to the midpoint cut when the parts do not separate."""
    if len(xs) < 2:
        return [mask]
    parts = [c for c in _components(mask) if c.sum() >= 6]
    if len(parts) < 2:
        return _split(mask, xs)
    out = [np.zeros(mask.shape, bool), np.zeros(mask.shape, bool)]
    for c in parts:
        cx = np.nonzero(c)[1].mean()
        out[0 if abs(cx - xs[0]) <= abs(cx - xs[1]) else 1] |= c
    return out


def _thick(mask):
    s = mask.sum(0)
    return int(s.max()) if s.any() else 0


def _long(mask):
    return int(mask.any(0).sum())


def readability(d, n, a, masks, m):
    """P-A3 numbers -> list of (label, value, gate, ok)."""
    h, w = a.shape[:2]
    out = []

    def grp(*names):
        mk = np.zeros((h, w), bool)
        for k, v in masks.items():
            if k in names or any(k.startswith(x + ":") for x in names):
                mk |= v
        return mk

    xs = [p[0] for p in m.get("iris", [])]
    eyes = _split(grp("sclera", "iris", "pupil", "catch"), xs)
    irises = _split(grp("iris", "pupil", "catch"), xs)
    pupils = _split(grp("pupil", "catch"), xs)
    brows = _split_parts(grp("brow"), xs)
    mouth_open = bool(m.get("mouth_open")) or grp("teeth").sum() > 30
    # the closed mouth is the fold: crease + lips (§7.3 "складка", lower lip 0.03 H); the open one its whole opening
    mouth = grp("mouth", "teeth", "tongue") if mouth_open else grp("mouth", "lip")
    sig = grp("signature")
    # a winking eye (meta "wink": "near" / "far", Hawk's laugh) is closed by design: its opening, iris, pupil and
    # catchlight are not gated (the other eye is)
    wink_i = {"near": 0, "far": 1}.get(m.get("wink"), -1)
    # an eye shut by design beside the wink (Iveta's smile: "глаза-дуги", both lids 0) is treated like one; the P3
    # moods narrow the eyes by design (§7.9: tired 0.30, cunning near 0.40-0.45, angry 0.55, and the glasses' opaque
    # glare of Iveta's and Arman's anger): their opening, iris, pupil and catchlight sizes are reported as INFO here
    # and gated by the P-A4 mood bands against the calm face (portrait_qa check_mood_bands)
    lids = m.get("lids") or []
    shut = {i for i, v in enumerate(lids[:2]) if v is not None and v < 0.12}
    narrowed = m.get("mood") in ("angry", "cunning", "tired")
    for px in (128, 64):
        k = px / w
        for i, side in enumerate(("near", "far")):
            if i == wink_i or i in shut:
                if px == 128:
                    out.append(("eye %s closed (wink)" % side, 1, 0))
                if i < len(brows):
                    # the brow over a winking eye is still gated, thickness and (64 px) length both
                    out.append(("%d brow %s thick" % (px, side), _thick(brows[i]) * k, 3 if px == 128 else 2))
                    if px == 64:
                        out.append(("64 brow %s long" % side, _long(brows[i]) * k, 6))
                continue
            if i < len(brows):
                out.append(("%d brow %s thick" % (px, side), _thick(brows[i]) * k, 3 if px == 128 else 2))
                if px == 64:
                    out.append(("64 brow %s long" % side, _long(brows[i]) * k, 6))
            info = " (INFO, mood)" if narrowed else ""
            if i < len(eyes):
                out.append(("%d eye %s opening%s" % (px, side, info), _thick(eyes[i]) * k,
                            0 if narrowed else (6 if px == 128 else 3)))
            if px == 128 and i < len(irises):
                out.append(("128 iris %s%s" % (side, info), _thick(irises[i]) * k, 0 if narrowed else 4))
            if px == 64 and i < len(pupils):
                out.append(("64 pupil %s%s" % (side, info), _thick(pupils[i]) * k, 0 if narrowed else 2))
        if mouth_open:
            out.append(("%d open mouth px2" % px, mouth.sum() * k * k, 40 if px == 128 else 6))
        elif px == 128:
            out.append(("128 closed mouth", _thick(mouth) * k, 2))
        if px == 64 and sig.any():
            out.append(("64 signature px2", sig.sum() * k * k, 20))
    # catchlight: a pixel brighter than 0.85 inside each eye at 128 px
    small = Q.resize_rgba(a, 128)
    ks = 128 / w
    lum = small[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    for i, e in enumerate(eyes):
        ys, xs_ = np.nonzero(e)
        if not len(ys) or i == wink_i or i in shut:
            continue
        y0, y1 = int(ys.min() * ks), int(np.ceil(ys.max() * ks)) + 1
        x0, x1 = int(xs_.min() * ks), int(np.ceil(xs_.max() * ks)) + 1
        out.append(("128 catchlight %s max%s" % ("near" if i == 0 else "far", " (INFO, mood)" if narrowed else ""),
                    float(lum[y0:y1, x0:x1].max()), 0 if narrowed else 0.85))
    # 48 px: the signature alone >= 8 % of the head-zone alpha mask
    if sig.any():
        am = Q.alpha_mask(a, 48)
        hz = int(am.shape[0] * 0.70)
        sm = np.asarray(Image.fromarray((sig * 255).astype(np.uint8)).resize(am.shape[::-1], Image.BOX)) > 127
        out.append(("48 signature share", sm[:hz].sum() / max(1, am[:hz].sum()), 0.08))
    if "lens_iris_contrast" in m:
        out.append(("iris contrast behind glass", m["lens_iris_contrast"], 0.70))
    res = [(lab, v, g, v >= g) for lab, v, g in out]
    # seated eyes: the white, iris and pupil stay inside the outline the lids draw (meta eye_almond: under the lash
    # line, over the lower rim); at most 2 % of each eye's pixels outside it (1.5 px tolerance at 512). A regression
    # guard, not proof: the outline and the lens come from the same Almond (see the module docstring)
    for i, poly in enumerate(m.get("eye_almond", [])[:2]):
        if i >= len(eyes) or not eyes[i].any():
            continue
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).polygon([tuple(q) for q in poly], fill=255)
        tol = max(1, int(round(1.5 * w / 512)))
        inside = np.asarray(im.filter(ImageFilter.MaxFilter(2 * tol + 1))) > 127
        share = float((eyes[i] & ~inside).sum()) / float(eyes[i].sum())
        res.append(("eye %s outside lids" % ("near" if i == 0 else "far"), share, 0.02, share <= 0.02))
    return res


def check_ids(d, imgs, rep):
    have = [n for n in imgs if Q.ids(d, n)[0] is not None]
    if not have:
        rep.add("INFO", "P-A3/P-A5 ids", "no ids/*.png sidecars: feature-size and colour-pair checks skipped")
        return
    for n in have:
        masks, _ = Q.ids(d, n)
        m = Q.meta(d, n) or {}
        rd = readability(d, n, imgs[n], masks, m)
        bad = [r for r in rd if not r[3]]
        rep.add("FAIL" if bad else "PASS", "P-A3 " + n, "; ".join(
            "%s %.1f%s" % (lab, v, "" if ok else "<%g FAIL" % g) for lab, v, g, ok in rd))
        cr = id_rules(imgs[n], masks, m, n)
        badc = [r for r in cr if not r[2]]
        rep.add("FAIL" if badc else "PASS", "P-A5 ids " + n, "; ".join(
            "%s %s%s" % (r[0], r[3], "" if r[2] else " FAIL") for r in cr))
        det = m.get("details", {})
        alias = m.get("detail_groups", {})     # a detail measured on another group (Hawk's helmet = the "hat")
        dl = []
        for name, need in det.items():
            got = int(masks.get(alias.get(name, "detail:" + name), np.zeros(1, bool)).sum())
            dl.append((name, got, need))
        if dl:
            badd = [x for x in dl if x[1] < x[2]]
            rep.add("FAIL" if badd else "PASS", "P-A8 details " + n, "; ".join(
                "%s %d/%d%s" % (x[0], x[1], x[2], "" if x[1] >= x[2] else " FAIL") for x in dl))


def check_smiles(d, imgs, rep):
    """P-A4 smile, from the ID pass and the landmarks of a calm / smile pair: both mouth corners >= 6 px higher on the
    master — in the picture and with the pose held (the expression alone, from the head-local corners in meta
    mouth_local), so a head tilt cannot carry the mood; an open smile's cavity (mouth + teeth + tongue) >= 900 px² on
    the master (scaled by the file's own size) with its teeth visible. A closed smile (§7.6 gives some characters
    one: Vega) is reported for the cavity and teeth as INFO. Eye opening and brow lift changes are INFO."""
    for n in sorted(imgs):
        if not n.endswith("_smile"):
            continue
        base = n[:-len("_smile")]
        ms, mc = Q.meta(d, n), Q.meta(d, base)
        if not ms or not mc or len(ms.get("mouth", [])) < 2 or len(mc.get("mouth", [])) < 2:
            continue
        k = imgs[n].shape[1] / 512.0
        img_d = [mc["mouth"][i][1] - ms["mouth"][i][1] for i in (0, 1)]
        held = []
        if ms.get("mouth_local") and mc.get("mouth_local"):
            held = [(ms["mouth_local"][i][1] - mc["mouth_local"][i][1]) * ms["h_px"] for i in (0, 1)]
        bad = [v for v in img_d + held if v < 6 * k]
        txt = "corners up (near, far): picture %.1f / %.1f px" % tuple(img_d)
        if held:
            txt += ", pose held %.1f / %.1f px" % tuple(held)
        masks, _ = Q.ids(d, n)
        info = []
        if masks is not None:
            def grp(*names):
                mk = None
                for kk, v in masks.items():
                    if kk in names:
                        mk = v if mk is None else (mk | v)
                return mk
            cav = grp("mouth", "teeth", "tongue")
            teeth = grp("teeth")
            area = (float(cav.sum()) if cav is not None else 0.0) / (k * k)
            tpx = (float(teeth.sum()) if teeth is not None else 0.0) / (k * k)
            if ms.get("mouth_open"):
                if area < 900 or tpx < 60:
                    bad.append(0)
                txt += "; cavity %.0f px² (>= 900), teeth %.0f px²" % (area, tpx)
            else:
                info.append("closed smile (§7.6): cavity %.0f px², teeth %.0f px² — the >= 900 px² rule is for open "
                            "smiles" % (area, tpx))
        eo = [ms["eye_open_px"][i] - mc["eye_open_px"][i] for i in range(min(len(ms.get("eye_open_px", [])),
                                                                              len(mc.get("eye_open_px", []))))]
        if eo:
            info.append("eye opening change %s px" % "/".join("%+d" % v for v in eo))
        if ms.get("brows") and mc.get("brows"):
            bl = [mc["brows"][i][0][1] - ms["brows"][i][0][1] for i in range(min(len(ms["brows"]), len(mc["brows"])))]
            info.append("brow inner ends up %s px" % "/".join("%.1f" % v for v in bl))
        rep.add("FAIL" if bad else "PASS", "P-A4 smile " + base, txt + ("; " + "; ".join(info) if info else ""))


def check_meta(d, imgs, rep):
    have = [n for n in imgs if Q.meta(d, n)]
    if not have:
        rep.add("INFO", "P-A7 contacts", "no meta/*.json sidecars: floating-part checks skipped")
    else:
        fl = []
        for n in have:
            f = Q.meta(d, n).get("floating", [])
            if f:
                fl.append("%s: %s" % (n, ",".join(f[:4])))
        rep.add("FAIL" if fl else "PASS", "P-A7 floating parts", "%d of %d files%s" % (
            len(fl), len(have), (" — " + "; ".join(fl[:4])) if fl else ""))
    isl = [(islands(a[..., 3]), n) for n, a in imgs.items() if n.startswith("cmd_") or n in have]
    bad = [x for x in isl if x[0] > 1]
    rep.add("FAIL" if bad else "PASS", "P-A7 alpha islands", "%d files with more than one island%s" % (
        len(bad), (": " + ", ".join("%s %d" % (b[1], b[0]) for b in bad[:6])) if bad else ""))


def _group_lab(rgba, masks, names, prefixes=()):
    """Mean Lab of the render under the union of ID groups (alpha > 0.5), or None when it covers < 200 px."""
    mk = np.zeros(rgba.shape[:2], bool)
    for k, v in masks.items():
        if k in names or any(k.startswith(p) for p in prefixes):
            mk |= v
    mk &= rgba[..., 3] > 0.5
    if mk.sum() < 200:
        return None, 0
    return Q.srgb_to_lab(rgba[..., :3][mk]).mean(0), int(mk.sum())


def colour_groups(rgba, masks):
    """§7.14 P-A9's four largest colour groups of a portrait: hair with beard (and sideburns), clothes (every costume
    group), headgear or skin (the hat when it covers >= 2 % of the figure, else the skin), the signature."""
    fig = max(1, int((rgba[..., 3] > 0.5).sum()))
    out = {}
    out["hair"] = _group_lab(rgba, masks, ("hair", "beard", "detail:sideburns"))[0]
    out["clothes"] = _group_lab(rgba, masks, ("costume",), ("costume:",))[0]
    hat, n_hat = _group_lab(rgba, masks, ("hat",))
    out["hat_or_skin"] = hat if (hat is not None and n_hat >= 0.02 * fig) else _group_lab(rgba, masks, ("skin",))[0]
    out["signature"] = _group_lab(rgba, masks, ("signature",))[0]
    return out


def check_distinct(d, imgs, rep):
    """P-A9: the mean dE76 of the four largest colour groups between any two era-1 calm commanders >= 15; the
    signatures unique (the kit's registry, meta "signature")."""
    names = [n for n in imgs if n.startswith("cmd_") and n.count("_") == 1]
    groups, sigs = {}, {}
    for n in names:
        masks, _ = Q.ids(d, n)
        if masks is None:
            continue
        groups[n] = colour_groups(imgs[n], masks)
        sigs[n] = (Q.meta(d, n) or {}).get("signature")
    if len(groups) < 2:
        rep.add("INFO", "P-A9 colour groups", "fewer than 2 era-1 commanders with ids/ sidecars")
        return
    rows = []
    for a, b in itertools.combinations(sorted(groups), 2):
        des = [float(Q.de76(groups[a][k], groups[b][k])) for k in ("hair", "clothes", "hat_or_skin", "signature")
               if groups[a][k] is not None and groups[b][k] is not None]
        if des:
            rows.append((sum(des) / len(des), a, b))
    rows.sort()
    bad = [r for r in rows if r[0] < 15]
    rep.add("FAIL" if bad else "PASS", "P-A9 colour groups", "mean dE76 min %.1f (%s/%s), median %.1f; %d of %d pairs "
            "< 15%s" % (rows[0][0], rows[0][1], rows[0][2], rows[len(rows) // 2][0], len(bad), len(rows),
                        "".join("; %s/%s %.1f" % (r[1], r[2], r[0]) for r in bad[:6])))
    seen, dup = {}, []
    for n, sg in sigs.items():
        if not sg:
            dup.append("%s has none" % n)
        elif sg in seen:
            dup.append("%s = %s" % (n, seen[sg]))
        else:
            seen[sg] = n
    rep.add("FAIL" if dup else "PASS", "P-A9 signatures", "%d unique of %d%s" % (len(seen), len(sigs),
                                                                              ("; " + ", ".join(dup)) if dup else ""))
    with open(os.path.join(rep.out, "de76_matrix.txt"), "w") as f:
        ks = sorted(groups)
        f.write("mean dE76 of hair / clothes / hat-or-skin / signature\n%-10s" % "" +
                "".join("%7s" % k[4:9] for k in ks) + "\n")
        lut = {(a, b): v for v, a, b in rows}
        for a in ks:
            f.write("%-10s" % a[4:] + "".join("%7s" % ("" if a == b else "%.1f" % lut.get((a, b), lut.get((b, a), 0)))
                                               for b in ks) + "\n")


def check_extra_details(d, imgs, rep):
    """P-A8 rows that are not a pixel count of a detail group (§7.14): Vega's raised brow >= 15 px higher than the
    near one (from the lash line, meta brow_gap_H), Kort's lids <= 0.6 (meta lids), Rai's iris L* 70-85 (render under
    the iris mask), Irma's orange >= 3 % of the costume (render pixels of hue 15-45 deg, S >= 0.5, under the costume,
    metal and detail groups below the chin)."""
    for n in sorted(imgs):
        if n.count("_") != 1:
            continue
        m = Q.meta(d, n) or {}
        masks, _ = Q.ids(d, n)
        rgba = imgs[n]
        if n == "cmd_vega" and len(m.get("brow_gap_H", [])) == 2:
            dpx = (m["brow_gap_H"][1] - m["brow_gap_H"][0]) * m.get("h_px", 272)
            rep.add("PASS" if dpx >= 15 else "FAIL", "P-A8 extra " + n, "far brow %.1f px higher than the near (>= 15)"
                    % dpx)
        if n == "cmd_kort" and m.get("lids"):
            lid = max(m["lids"])
            rep.add("PASS" if lid <= 0.6 else "FAIL", "P-A8 extra " + n, "lids %.2f (<= 0.6)" % lid)
        if n == "cmd_rai" and masks is not None:
            mk = masks.get("iris", np.zeros(1, bool)) & (rgba[..., 3] > 0.5)
            if mk.sum() > 20:
                L = float(np.median(Q.srgb_to_lab(rgba[..., :3][mk])[..., 0]))
                rep.add("PASS" if 70 <= L <= 85 else "FAIL", "P-A8 extra " + n, "iris L* %.1f (70-85)" % L)
        if n == "cmd_irma" and masks is not None and m.get("chin_y"):
            mk = np.zeros(rgba.shape[:2], bool)
            for k, v in masks.items():
                if k in ("costume", "metal") or k.startswith("costume:") or (k.startswith("detail:") and k not in (
                        "detail:oil", "detail:goggles")):
                    mk |= v
            mk[: int(m["chin_y"])] = False
            mk &= rgba[..., 3] > 0.5
            px = rgba[..., :3][mk]
            mx, mn = px.max(-1), px.min(-1)
            sat = (mx - mn) / np.maximum(mx, 1e-6)
            r, g, b = px[:, 0], px[:, 1], px[:, 2]
            hue = (np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) + 360) % 360
            share = float(((hue >= 15) & (hue <= 45) & (sat >= 0.5) & (mx > 0.35)).mean()) if len(px) else 0.0
            rep.add("PASS" if share >= 0.03 else "FAIL", "P-A8 extra " + n, "orange %.1f %% of the costume (>= 3 %%)"
                    % (share * 100))


def _brow_angle(b):
    """The brow's inner end down, in degrees (picture y grows down): b = [inner, outer] picture points."""
    (xi, yi), (xo, yo) = b
    return float(np.degrees(np.arctan2(yi - yo, max(1e-6, abs(xi - xo)))))


def check_mood_bands(d, imgs, rep):
    """P-A4 by the landmarks of each leader mood against its own calm (§7.14): angry — the brows' inner ends down >= 20
    deg and the pupil <= 0.85 of the calm one; tired — the eye opening 0.30-0.50 of the calm one and the brows' inner
    ends up >= 12 deg; cunning — the two brows' height difference (near minus far, signed) changed by >= 0.06 H, the
    glance >= 25 % of the eye's width sideways, the head rolled >= 4 deg. (Smile: check_smiles.) An eye closed by
    design (a wink, the smile's happy closed eyes) skips its opening."""
    for x in Q.LEADERS:
        mc = Q.meta(d, "ldr_" + x)
        if not mc or not mc.get("brows"):
            continue
        for mood in ("angry", "tired", "cunning"):
            n = "ldr_%s_%s" % (x, mood)
            mm = Q.meta(d, n)
            if not mm or not mm.get("brows") or n not in imgs:
                continue
            out, bad = [], False
            h = mm.get("h_px", 270.0)
            da = [_brow_angle(bm) - _brow_angle(bc) for bm, bc in zip(mm["brows"], mc["brows"])]
            if mood == "angry":
                ok = min(da) >= 20
                out.append("brows inner down %s deg (>= 20)%s" % ("/".join("%.1f" % v for v in da), "" if ok else " FAIL"))
                bad |= not ok
                pr = [a / b for a, b in zip(mm.get("pupils") or [], mc.get("pupils") or []) if a and b]
                if pr:
                    ok = max(pr) <= 0.851
                    out.append("pupil %.2f of calm (<= 0.85)%s" % (max(pr), "" if ok else " FAIL"))
                    bad |= not ok
            elif mood == "tired":
                op = [a / b for a, b in zip(mm.get("eye_open_px") or [], mc.get("eye_open_px") or []) if b]
                if op:
                    ok = all(0.25 <= v <= 0.52 for v in op)
                    out.append("opening %s of calm (0.30-0.50)%s" % ("/".join("%.2f" % v for v in op), "" if ok else " FAIL"))
                    bad |= not ok
                ok = max(da) <= -12
                out.append("brows inner up %s deg (>= 12)%s" % ("/".join("%.1f" % -v for v in da), "" if ok else " FAIL"))
                bad |= not ok
            else:
                def mid_y(b):
                    return (b[0][1] + b[1][1]) / 2
                # signed (near minus far): a calm face whose far brow already sits a little lower would read a raised
                # far brow as a SMALLER |difference| (Mirosya: calm -4 px, cunning +1 px). Head-local and pose-free
                # when the kit wrote brows_local (in H, z up): §7.9's brow deltas are against the character's own calm
                # face, and the cunning roll (checked on its own below) tilts the picture's brow line by ~0.04 H
                if mm.get("brows_local") and mc.get("brows_local"):
                    diff_m = mid_y(mm["brows_local"][1]) - mid_y(mm["brows_local"][0])
                    diff_c = mid_y(mc["brows_local"][1]) - mid_y(mc["brows_local"][0])
                    where = "head-local"
                else:
                    diff_m = (mid_y(mm["brows"][0]) - mid_y(mm["brows"][1])) / h
                    diff_c = (mid_y(mc["brows"][0]) - mid_y(mc["brows"][1])) / h
                    where = "picture"
                ok = abs(diff_m - diff_c) >= 0.06 - 1e-6
                out.append("brow difference %+.3f H %s (>= 0.06)%s" % (diff_m - diff_c, where, "" if ok else " FAIL"))
                bad |= not ok
                gz = []
                for gm, gc in zip(mm.get("gaze") or [], mc.get("gaze") or []):
                    gz.append(abs((gm[0] - gm[2]) - (gc[0] - gc[2])) / max(1e-6, 2 * gm[3]))
                if gz:
                    ok = min(gz) >= 0.25 - 1e-6
                    out.append("glance %s of the eye width (>= 0.25)%s" % ("/".join("%.2f" % v for v in gz),
                                                                         "" if ok else " FAIL"))
                    bad |= not ok
                roll = abs((mm.get("pose") or {}).get("mood_roll", 0.0))
                ok = roll >= 4
                out.append("roll %.1f deg (>= 4)%s" % (roll, "" if ok else " FAIL"))
                bad |= not ok
            rep.add("FAIL" if bad else "PASS", "P-A4 band " + n, "; ".join(out))


def main():
    pos, opts = Q.parse(sys.argv[1:])
    src, out = pos[0], pos[1]
    os.makedirs(out, exist_ok=True)
    rep = Report()
    rep.out = out
    have, miss = Q.present(src)
    imgs = check_files(src, have, miss, rep)
    if imgs:
        check_framing(src, imgs, rep)
        check_silhouettes(imgs, rep, out)
        check_contrast(imgs, rep)
        check_moods(imgs, rep, out)
        check_ids(src, imgs, rep)
        check_smiles(src, imgs, rep)
        check_mood_bands(src, imgs, rep)
        check_meta(src, imgs, rep)
        check_distinct(src, imgs, rep)
        check_extra_details(src, imgs, rep)
    txt = "\n".join(rep.lines)
    with open(os.path.join(out, "report.txt"), "w") as f:
        f.write(txt + "\n")
    print(txt)
    print("RESULT", "FAIL" if rep.fails else "PASS", rep.fails)
    if "strict" in opts and rep.fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
