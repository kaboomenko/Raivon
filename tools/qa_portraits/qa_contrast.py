"""P-A5 contrast and colour (docs/art_direction.md §7.4, §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_contrast.py PORTRAIT_DIR [--strict] [--quiet] [--moods]

The game draws the plate, so the render must separate from it. Plates: a commander on its rarity colour in BOTH
palettes (ui = Kit.RARITY, gdd = the 04 §15.4 set of §7.4), a leader on its state's colour exactly as the game
passes it to CmdPortrait.plate, the ruler on SKY. Plate gradient "B" (§7.4: rc.lightened(0.18) -> rc) is GATED;
today's gradient (lightened(0.08) -> darkened(0.42)) is printed as INFO.
Image rules (calm files: every era of a commander, each leader's calm, the ruler; --moods adds the smiles and the
leaders' moods, which share the costume):
- shoulder band (opaque pixels in rows 0.80-0.95 h) vs the plate row behind it: median |dL*| >= 15 and pixels with
  |dL*| < 8 ("melting") <= 25 %;
- silhouette rim (opaque pixels within 4 px of transparency at 512, scaled; rows < 0.92 h, the bottom edge cuts the
  body): <= 35 % within dL* 8 of the plate;
- dark pixels (L* < 17, the albedo floor #2A2A30) <= 3 % of the opaque pixels.
ID rules (only with the kit's sidecars ids/<name>.png + meta/<name>.json):
- hair or headgear next to the face vs skin: |dL*| >= 15 or dE76 >= 30;   - brows vs skin: |dL*| >= 18;
- iris vs sclera: dL* >= 30;   - beard vs the clothing it lies on: |dL*| >= 15;
- signature vs plate (B, both palettes): dE76 >= 25;
- the lit cheek (near side, between the eye line and the mouth): L* 70-82 and HSV S >= 0.35.
A folder that holds only some of the 150 names is fine. Exit 1 with --strict when a gated rule fails.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

BAND = (0.80, 0.95)


def band_stats(im, plate_hex, mode):
    """(median |dL*|, melting share) of the shoulder band against the plate gradient `mode`."""
    h = im.shape[0]
    r0, r1 = int(h * BAND[0]), int(h * BAND[1])
    band = im[r0:r1]
    op = band[..., 3] > 0.9
    if op.sum() < 20:
        return None
    L = Q.srgb_to_lab(band[..., :3])[..., 0]
    pl = Q.srgb_to_lab(Q.plate_rows(plate_hex, h, mode)[r0:r1])[:, 0][:, None]
    dl = np.abs(L - pl)[op]
    return float(np.median(dl)), float((dl < 8).mean())


def rim_share(im, plate_hex, mode):
    h, w = im.shape[:2]
    a = im[..., 3]
    px = max(2, int(round(4 * w / 512)))
    m = Image.fromarray(((a > 0.05) * 255).astype(np.uint8))
    inner = np.asarray(m.filter(ImageFilter.MinFilter(2 * px + 1))) > 127
    ring = (a > 0.95) & ~inner
    ring[int(h * 0.92):] = False
    if ring.sum() < 10:
        return None
    L = Q.srgb_to_lab(im[..., :3])[..., 0]
    pl = Q.srgb_to_lab(Q.plate_rows(plate_hex, h, mode))[:, 0][:, None]
    dl = np.abs(L - np.broadcast_to(pl, L.shape))[ring]
    return float((dl < 8).mean())


def dark_share(im):
    op = im[..., 3] > 0.9
    if not op.any():
        return 0.0
    L = Q.srgb_to_lab(im[..., :3][op])[..., 0]
    return float((L < 17).mean())


def plates_for(name):
    if name.startswith("cmd_"):
        r = Q.RARITY[name.split("_")[1]]
        return [("ui/" + r, Q.PLATES_UI[r]), ("gdd/" + r, Q.PLATES_GDD[r])]
    if name.startswith("ldr_"):
        return [("state", Q.LEADER_PLATE[name.split("_")[1]])]
    return [("sky", Q.SKY)]


def id_rules(im, masks, m, name):
    """The ID-pass colour rules of §7.4 -> list of (rule, value, ok, text)."""
    lab = Q.srgb_to_lab(im[..., :3])
    h, w = im.shape[:2]
    out = []

    def med(mask):
        return np.median(lab[mask], axis=0) if mask is not None and mask.sum() >= 12 else None

    def grp(*names):
        mk = None
        for k in list(masks):
            if k in names or any(k.startswith(n + ":") for n in names):
                mk = masks[k] if mk is None else (mk | masks[k])
        return mk

    skin = med(grp("skin"))
    hair_mask = grp("hair", "hat")
    if skin is not None and hair_mask is not None:
        # only the hair next to the face: within 0.15 H of a skin pixel
        hp = max(3, int(0.15 * m.get("h_px", 272)))
        near_skin = np.asarray(Image.fromarray((masks["skin"] * 255).astype(np.uint8))
                               .filter(ImageFilter.MaxFilter(2 * (hp // 2) + 1))) > 127
        hair = med(hair_mask & near_skin)
        if hair is not None:
            dl, de = abs(hair[0] - skin[0]), float(Q.de76(hair, skin))
            out.append(("hair-skin", dl, dl >= 15 or de >= 30, "|dL*| %.1f dE %.1f" % (dl, de)))
    brow = med(grp("brow"))
    if skin is not None and brow is not None:
        dl = abs(brow[0] - skin[0])
        out.append(("brow-skin", dl, dl >= 18, "|dL*| %.1f (target 20)" % dl))
    iris, sclera = med(grp("iris")), med(grp("sclera"))
    if iris is not None and sclera is not None:
        dl = sclera[0] - iris[0]
        out.append(("iris-sclera", dl, dl >= 30, "dL* %.1f" % dl))
    bm = grp("beard")
    cm = grp("costume")
    if bm is not None and cm is not None and bm.sum() > 50:
        k = max(3, int(round(6 * w / 512)))
        dil = np.asarray(Image.fromarray((bm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * k + 1))) > 127
        under = cm & dil & ~bm
        b, c = med(bm), med(under)
        if b is not None and c is not None:
            dl = abs(b[0] - c[0])
            out.append(("beard-clothes", dl, dl >= 15, "|dL*| %.1f" % dl))
    sg = grp("signature")
    if sg is not None and sg.sum() > 20:
        s = med(sg)
        ys = np.where(sg.any(1))[0]
        row = int(ys.mean())
        for tag, pc in plates_for(name):
            pl = Q.srgb_to_lab(Q.plate_rows(pc, h, "B")[row])
            de = float(Q.de76(s, pl))
            out.append(("signature-plate " + tag, de, de >= 25, "dE %.1f" % de))
    sk = grp("skin")
    if sk is not None and m and m.get("iris") and m.get("mouth"):
        near_eye = min(m["iris"], key=lambda p: p[0])
        mouth_y = (m["mouth"][0][1] + m["mouth"][1][1]) / 2
        hb = m["head_box"]
        y0, y1 = int(m["eye_y"] + 0.06 * m["h_px"]), int(mouth_y)
        x0, x1 = int(hb[0]), int(near_eye[0] + 0.02 * m["h_px"])
        cheek = np.zeros_like(sk)
        cheek[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
        cheek &= sk
        if cheek.sum() > 30:
            L = float(np.median(lab[..., 0][cheek]))
            S = float(np.median(Q.hsv_s(im[..., :3][cheek])))
            out.append(("lit cheek L*", L, 70 <= L <= 82, "L* %.1f (70-82)" % L))
            out.append(("lit cheek S", S, S >= 0.35, "S %.2f (>= 0.35)" % S))
    return out


def main():
    pos, opts = Q.parse(sys.argv[1:])
    d = pos[0]
    quiet = "quiet" in opts
    have, _ = Q.report_missing(d)
    fails = 0
    tally = {}
    moods = ("_smile", "_angry", "_cunning", "_tired")
    for n in have:
        im = Q.load(os.path.join(d, n + ".png"))
        lines = []
        bad = False
        image_rules = "moods" in opts or not n.endswith(moods)
        for tag, pc in (plates_for(n) if image_rules else []):
            b = band_stats(im, pc, "B")
            c = band_stats(im, pc, "current")
            r = rim_share(im, pc, "B")
            okb = b is None or (b[0] >= 15 and b[1] <= 0.25)
            okr = r is None or r <= 0.35
            tally.setdefault("band B", [0, 0])
            tally["band B"][0] += okb
            tally["band B"][1] += 1
            tally.setdefault("rim B", [0, 0])
            tally["rim B"][0] += okr
            tally["rim B"][1] += 1
            if c is not None:
                tally.setdefault("band current (INFO)", [0, 0])
                tally["band current (INFO)"][0] += c[0] >= 15 and c[1] <= 0.25
                tally["band current (INFO)"][1] += 1
            bad |= not (okb and okr)
            lines.append("%-9s %s  band B dL %s melt %s%s | rim %s%s | current dL %s melt %s" % (
                tag, pc, "%5.1f" % b[0] if b else "  -  ", "%3.0f%%" % (b[1] * 100) if b else " - ",
                "" if okb else " FAIL", "%3.0f%%" % (r * 100) if r is not None else " - ", "" if okr else " FAIL",
                "%5.1f" % c[0] if c else "  -  ", "%3.0f%%" % (c[1] * 100) if c else " - "))
        ds = dark_share(im)
        okd = ds <= 0.03
        bad |= not okd
        tally.setdefault("dark <= 3%", [0, 0])
        tally["dark <= 3%"][0] += okd
        tally["dark <= 3%"][1] += 1  # every file: an open mouth adds dark pixels
        masks, _ = Q.ids(d, n)
        idl = []
        if masks is not None:
            for rule, v, ok, txt in id_rules(im, masks, Q.meta(d, n) or {}, n):
                idl.append("%s %s%s" % (rule, txt, "" if ok else " FAIL"))
                key = rule.split(" ")[0] if rule.startswith("signature") else rule
                tally.setdefault(key, [0, 0])
                tally[key][0] += ok
                tally[key][1] += 1
                bad |= not ok
        fails += bad
        if not quiet or bad:
            print("%-22s dark %.1f%%%s%s" % (n, ds * 100, "" if okd else " FAIL", "   FAIL" if bad else ""))
            for ln in lines:
                print("    " + ln)
            if idl:
                print("    ids: " + "; ".join(idl))
    print("\n== summary (passing / checked) ==")
    for k, (ok, tot) in tally.items():
        print("  %-24s %3d / %3d" % (k, ok, tot))
    print("RESULT", "FAIL" if fails else "PASS", fails)
    sys.exit(1 if fails and "strict" in opts else 0)


if __name__ == "__main__":
    main()
