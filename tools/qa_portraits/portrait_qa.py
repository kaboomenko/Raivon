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
                  closed mouth >= 2 px, open mouth >= 40 px²; at 64 px: brows >= 2 px thick and >= 6 px long, eye
                  opening >= 3 px, pupil >= 2 px, open mouth >= 6 px², signature >= 20 px; at 48 px the signature
                  alone >= 8 % of the head-zone mask; irises behind glasses keep >= 70 % of their contrast
  P-A7            meta "floating" empty; one alpha island; every detail:* at least its P-A8 pixel count
Exit 1 with --strict if any FAIL.
"""
import itertools
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

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
    tops, side, metas = [], [], []
    for n, a in imgs.items():
        al = a[..., 3] > 0.5
        h, w = al.shape
        rows = np.where(al.sum(1) >= 2)[0]
        if not len(rows):
            continue
        tmin = Q.TOP_MIN if n.startswith("cmd_") else Q.TOP_MIN_HEADGEAR
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
    brows = _split(grp("brow"), xs)
    mouth_open = bool(m.get("mouth_open")) or grp("teeth").sum() > 30
    # the closed mouth is the fold: crease + lips (§7.3 "складка", lower lip 0.03 H); the open one its whole opening
    mouth = grp("mouth", "teeth", "tongue") if mouth_open else grp("mouth", "lip")
    sig = grp("signature")
    for px in (128, 64):
        k = px / w
        for i, side in enumerate(("near", "far")):
            if i < len(brows):
                out.append(("%d brow %s thick" % (px, side), _thick(brows[i]) * k, 3 if px == 128 else 2))
                if px == 64:
                    out.append(("64 brow %s long" % side, _long(brows[i]) * k, 6))
            if i < len(eyes):
                out.append(("%d eye %s opening" % (px, side), _thick(eyes[i]) * k, 6 if px == 128 else 3))
            if px == 128 and i < len(irises):
                out.append(("128 iris %s" % side, _thick(irises[i]) * k, 4))
            if px == 64 and i < len(pupils):
                out.append(("64 pupil %s" % side, _thick(pupils[i]) * k, 2))
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
        if not len(ys):
            continue
        y0, y1 = int(ys.min() * ks), int(np.ceil(ys.max() * ks)) + 1
        x0, x1 = int(xs_.min() * ks), int(np.ceil(xs_.max() * ks)) + 1
        out.append(("128 catchlight %s max" % ("near" if i == 0 else "far"), float(lum[y0:y1, x0:x1].max()), 0.85))
    # 48 px: the signature alone >= 8 % of the head-zone alpha mask
    if sig.any():
        am = Q.alpha_mask(a, 48)
        hz = int(am.shape[0] * 0.70)
        sm = np.asarray(Image.fromarray((sig * 255).astype(np.uint8)).resize(am.shape[::-1], Image.BOX)) > 127
        out.append(("48 signature share", sm[:hz].sum() / max(1, am[:hz].sum()), 0.08))
    if "lens_iris_contrast" in m:
        out.append(("iris contrast behind glass", m["lens_iris_contrast"], 0.70))
    return [(lab, v, g, v >= g) for lab, v, g in out]


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
        dl = []
        for name, need in det.items():
            got = int(masks.get("detail:" + name, np.zeros(1, bool)).sum())
            dl.append((name, got, need))
        if dl:
            badd = [x for x in dl if x[1] < x[2]]
            rep.add("FAIL" if badd else "PASS", "P-A8 details " + n, "; ".join(
                "%s %d/%d%s" % (x[0], x[1], x[2], "" if x[1] >= x[2] else " FAIL") for x in dl))


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


def main():
    pos, opts = Q.parse(sys.argv[1:])
    src, out = pos[0], pos[1]
    os.makedirs(out, exist_ok=True)
    rep = Report()
    have, miss = Q.present(src)
    imgs = check_files(src, have, miss, rep)
    if imgs:
        check_framing(src, imgs, rep)
        check_silhouettes(imgs, rep, out)
        check_contrast(imgs, rep)
        check_moods(imgs, rep, out)
        check_ids(src, imgs, rep)
        check_meta(src, imgs, rep)
    txt = "\n".join(rep.lines)
    with open(os.path.join(out, "report.txt"), "w") as f:
        f.write(txt + "\n")
    print(txt)
    print("RESULT", "FAIL" if rep.fails else "PASS", rep.fails)
    if "strict" in opts and rep.fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
