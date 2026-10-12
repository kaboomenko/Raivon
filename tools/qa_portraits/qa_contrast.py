"""P-A5 contrast and colour (docs/art_direction.md §7.4, §7.14). numpy + Pillow.

Usage: python3 -I tools/qa_portraits/qa_contrast.py PORTRAIT_DIR [--strict] [--quiet] [--moods]

The game draws the plate, so the render must separate from it. Plates: a commander on its rarity colour in BOTH
palettes (ui = Kit.RARITY, gdd = the 04 §15.4 set of §7.4), a leader on its state's colour exactly as the game
passes it to CmdPortrait.plate, the ruler on SKY. Plate gradient "B" (§7.4: rc.lightened(0.18) -> rc) is GATED;
today's gradient (lightened(0.08) -> darkened(0.42)) is printed as INFO.
Image rules (calm files: every era of a commander, each leader's calm, the ruler; --moods adds the smiles and the
leaders' moods, which share the costume):
- shoulder band (opaque pixels in rows 0.80-0.95 h) vs the plate pixel behind each (gradient + halo, qa_common.
  plate_image): median |dL*| >= 15 and pixels with |dL*| < 8 ("melting") <= 25 %;
- silhouette rim (opaque pixels within 4 px of transparency at 512, scaled; rows < 0.92 h, the bottom edge cuts the
  body): <= 35 % within dL* 8 of the plate;
- dark pixels (L* < 17, the albedo floor #2A2A30) <= 3 % of the opaque pixels (with the ID pass, also split INFO:
  the exempt groups of §7.4 — pupils, lash lines, mouth, glasses — vs the rest).
ID rules (only with the kit's sidecars ids/<name>.png + meta/<name>.json):
- hair, headgear or beard next to the face vs skin: |dL*| >= 15 or dE76 >= 30;   - brows vs skin: |dL*| >= 18 (the
  skin's global median; INFO: the same against the skin within 8 px of the brows);
- hair / beard vs skin AT THE EDGE (art director note 1): a 3 px band each side of the boundary, the mouth region
  (within 0.2 H of the mouth) and the rest apart: skin L* - hair L* >= 12 in each, where the hair is darker than the
  skin (platinum or white hair: INFO); INFO line: the hue of the skin (all / lit) against the hair and the beard;
- iris vs sclera: dL* >= 30;   - beard vs each garment it lies on (costume:<id> groups): |dL*| >= 15;
- signature vs plate (B, both palettes): dE76 >= 25;
- the lit cheek (the brightest 30 % of the skin pixels: the key-lit side of the face): median L* from
  min(70, L* of the skin albedo - 8) to 82 (the albedo from the kit's meta "skin_albedo"; 70 without it) and median
  HSV S >= 0.35, >= 0.27 for peach-pink skin (the lit cheek's hue <= 16 deg) — §7.4 as decided after P1.
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
    """(median |dL*|, melting share) of the shoulder band against the plate (gradient + halo) of `mode`."""
    h, w = im.shape[:2]
    r0, r1 = int(h * BAND[0]), int(h * BAND[1])
    band = im[r0:r1]
    op = band[..., 3] > 0.9
    if op.sum() < 20:
        return None
    L = Q.srgb_to_lab(band[..., :3])[..., 0]
    pl = Q.srgb_to_lab(Q.plate_image(plate_hex, w, h, mode)[r0:r1])[..., 0]
    dl = np.abs(L - pl)[op]
    return float(np.median(dl)), float((dl < 8).mean())


def rim_share(im, plate_hex, mode, exclude=None):
    """Share of the silhouette's inner rim (4 px at 512) within dL* 8 of the plate behind it (gradient + halo);
    `exclude` (a mask) leaves some pixels out (INFO only: the ruler's crown, whose gold §7.10 sets at dL* ~4 to the
    sky)."""
    h, w = im.shape[:2]
    a = im[..., 3]
    px = max(2, int(round(4 * w / 512)))
    m = Image.fromarray(((a > 0.05) * 255).astype(np.uint8))
    inner = np.asarray(m.filter(ImageFilter.MinFilter(2 * px + 1))) > 127
    ring = (a > 0.95) & ~inner
    ring[int(h * 0.92):] = False
    if exclude is not None:
        ring &= ~exclude
    if ring.sum() < 10:
        return None
    L = Q.srgb_to_lab(im[..., :3])[..., 0]
    pl = Q.srgb_to_lab(Q.plate_image(plate_hex, w, h, mode))[..., 0]
    dl = np.abs(L - pl)[ring]
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
    # hair, headgear and beard (moustache included) next to the face, each against the skin: §7.4 "волосы или шапка
    # у лица — кожа" (a beard on the face is hair at the face; a melting beard passed every tool before)
    for hk in ("hair", "hat", "beard"):
        hair_mask = grp(hk)
        if skin is None or hair_mask is None or hair_mask.sum() < 12:
            continue
        # only the part next to the face: within 0.15 H of a skin pixel
        hp = max(3, int(0.15 * m.get("h_px", 272)))
        near_skin = np.asarray(Image.fromarray((masks["skin"] * 255).astype(np.uint8))
                               .filter(ImageFilter.MaxFilter(2 * (hp // 2) + 1))) > 127
        hair = med(hair_mask & near_skin)
        if hair is not None:
            dl, de = abs(hair[0] - skin[0]), float(Q.de76(hair, skin))
            out.append((hk + "-skin", dl, dl >= 15 or de >= 30, "|dL*| %.1f dE %.1f" % (dl, de)))
    # the boundary itself (art director note 1, 2026-10-11: "beard vs skin dL* >= 12 measured at the boundary", the
    # same for ginger / brown hair): a 3 px band (at 512) on each side of the hair / beard edge with the skin (nose
    # included), split into the mouth region (within 0.2 H of the mouth: moustache, lips, chin) and the rest (the
    # cheek line, the hairline); median skin L* minus median hair L* per region. Gated where the hair is darker than
    # the skin; platinum or white hair (lighter than the skin) is reported as INFO
    skin_any = grp("skin", "nose")
    if skin is not None and skin_any is not None:
        hpx = m.get("h_px", 272)
        k = max(1, int(round(3 * w / 512)))
        mc = m.get("mouth")
        near_mouth = np.zeros((h, w), bool)
        if mc and len(mc) == 2:
            yy, xx = np.mgrid[0:h, 0:w]
            cx_, cy_ = (mc[0][0] + mc[1][0]) / 2, (mc[0][1] + mc[1][1]) / 2
            near_mouth = (xx - cx_) ** 2 + (yy - cy_) ** 2 <= (0.2 * hpx) ** 2
        sk_d = np.asarray(Image.fromarray((skin_any * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * k + 1))) > 127
        for hk in ("hair", "beard"):
            hm = grp(hk)
            if hm is None or hm.sum() < 50:
                continue
            hm_d = np.asarray(Image.fromarray((hm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * k + 1))) > 127
            a_side, b_side = skin_any & hm_d, hm & sk_d
            parts = []
            for reg, rm in (("mouth", near_mouth), ("face", ~near_mouth)):
                if (a_side & rm).sum() >= 30 and (b_side & rm).sum() >= 30:
                    dl = float(np.median(lab[..., 0][a_side & rm]) - np.median(lab[..., 0][b_side & rm]))
                    parts.append((reg, dl))
            if not parts:
                continue
            worst = min(parts, key=lambda q: q[1])
            gated = med(hm)[0] < skin[0]
            txt = ", ".join("%s %.1f" % q for q in parts) + ("" if gated else " (INFO: lighter than the skin)")
            out.append((hk + "-skin edge", worst[1], (worst[1] >= 12) if gated else True, "dL* " + txt))
        # INFO: the hues (the skin must read peach-pink beside ginger hair, not orange on orange)
        def hue_of(mask):
            rgb = np.median(im[..., :3][mask], axis=0)
            mx, mn = rgb.max(), rgb.min()
            if mx - mn < 1e-6:
                return 0.0, 0.0
            r, g, b = rgb
            if mx == r:
                hh = ((g - b) / (mx - mn)) % 6
            elif mx == g:
                hh = (b - r) / (mx - mn) + 2
            else:
                hh = (r - g) / (mx - mn) + 4
            return 60.0 * hh, (mx - mn) / mx
        Ls_ = lab[..., 0][masks["skin"]] if "skin" in masks else None
        if Ls_ is not None and Ls_.size > 100:
            lit_ = masks["skin"] & (lab[..., 0] >= np.percentile(Ls_, 70))
            sh, ss = hue_of(masks["skin"])
            lh, _ = hue_of(lit_)
            hs = ["skin %.0f° S %.2f (lit %.0f°)" % (sh, ss, lh)]
            for hk in ("hair", "beard"):
                hm = grp(hk)
                if hm is not None and hm.sum() >= 50:
                    hh_, hs_ = hue_of(hm)
                    hs.append("%s %.0f° S %.2f" % (hk, hh_, hs_))
            out.append(("hue (INFO)", 0.0, True, ", ".join(hs)))
    brow = med(grp("brow"))
    if skin is not None and brow is not None:
        dl = abs(brow[0] - skin[0])
        # INFO beside the gated global median: the skin right round the brows (8 px at 512) — on a bald, lit dome
        # (Kort, Olm) the global skin median sits far above the forehead the brows are read against
        bm_ = grp("brow")
        kr = max(2, int(round(8 * w / 512)))
        ring = (np.asarray(Image.fromarray((bm_ * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * kr + 1)))
                > 127) & ~bm_ & grp("skin")
        extra = ""
        if ring.sum() >= 30:
            extra = "; ring (INFO) |dL*| %.1f" % abs(brow[0] - float(np.median(lab[..., 0][ring])))
        out.append(("brow-skin", dl, dl >= 18, "|dL*| %.1f (target 20)%s" % (dl, extra)))
    iris, sclera = med(grp("iris")), med(grp("sclera"))
    if iris is not None and sclera is not None:
        dl = sclera[0] - iris[0]
        out.append(("iris-sclera", dl, dl >= 30, "dL* %.1f" % dl))
        pupil = med(grp("pupil"))
        if iris[0] > sclera[0] - 15 and pupil is not None:
            # a light (glowing) iris — Rai's, which P-A8 wants at L* 70-85 while the white renders ~71: the numbers of
            # the replacement rule proposed for the main session's decision (iris-sclera dE76 >= 12, pupil-iris
            # dL* >= 40), INFO only — the gate above stays as §7.4 has it
            out.append(("glowing iris (INFO)", 0.0, True, "iris-sclera dE76 %.1f, pupil-iris dL* %.1f" % (
                float(Q.de76(iris, sclera)), iris[0] - pupil[0])))
    bm = grp("beard")
    if bm is not None and bm.sum() > 50:
        k = max(3, int(round(6 * w / 512)))
        dil = np.asarray(Image.fromarray((bm * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * k + 1))) > 127
        b = med(bm)
        worst = None
        for key, mk in masks.items():          # each garment the beard lies on, separately (costume:<id>)
            if not (key == "costume" or key.startswith("costume:")):
                continue
            under = mk & dil & ~bm
            if under.sum() < 50:
                continue
            c = med(under)
            dl = abs(b[0] - c[0])
            if worst is None or dl < worst[0]:
                worst = (dl, key)
        if worst is not None:
            out.append(("beard-clothes", worst[0], worst[0] >= 15, "|dL*| %.1f (vs %s)" % worst))
    sg = grp("signature")
    if sg is not None and sg.sum() > 20:
        s = med(sg)
        ys = np.where(sg.any(1))[0]
        row = int(ys.mean())
        ys_, xs_ = np.nonzero(sg)
        col = int(xs_.mean())
        for tag, pc in plates_for(name):
            pl = Q.srgb_to_lab(Q.plate_image(pc, w, h, "B")[row, col])
            de = float(Q.de76(s, pl))
            out.append(("signature-plate " + tag, de, de >= 25, "dE %.1f" % de))
    sk = grp("skin")
    if sk is not None and sk.sum() > 100:
        # the lit cheek = the brightest 30 % of the skin pixels (the key-lit side of the face; the definition the
        # §7.4 numbers come from, design A §3.7): their median L* 70-82 and median HSV S >= 0.35
        Ls = lab[..., 0][sk]
        cut = np.percentile(Ls, 70)
        lit = sk & (lab[..., 0] >= cut)
        L = float(np.median(lab[..., 0][lit]))
        S = float(np.median(Q.hsv_s(im[..., :3][lit])))
        # the floor follows the skin (§7.4, decided after P1): min(70, the albedo's L* - 8) — a T4-T6 face cannot
        # reach 70 without bleaching; files without the kit's skin_albedo keep 70
        lo = 70.0
        if m.get("skin_albedo"):
            alb = Q.srgb_to_lab(np.array(Q.hex_rgb(m["skin_albedo"]), dtype=np.float32))
            lo = min(70.0, float(alb[0]) - 8.0)
        # the S floor: 0.27 for peach-pink skin (the lit cheek's hue <= 16 deg: AgX turns more saturation salmon),
        # 0.35 otherwise
        rgb = np.median(im[..., :3][lit], axis=0)
        mx, mn = float(rgb.max()), float(rgb.min())
        hue = 0.0
        if mx - mn > 1e-6 and mx == rgb[0]:
            hue = 60.0 * (((rgb[1] - rgb[2]) / (mx - mn)) % 6)
        elif mx - mn > 1e-6:
            hue = 60.0 * ((rgb[2] - rgb[0]) / (mx - mn) + 2) if mx == rgb[1] else 60.0 * ((rgb[0] - rgb[1]) / (mx - mn) + 4)
        s_lo = 0.27 if hue <= 16.0 else 0.35
        out.append(("lit cheek L*", L, lo <= L <= 82, "L* %.1f (%.0f-82)" % (L, lo)))
        out.append(("lit cheek S", S, S >= s_lo, "S %.2f (>= %.2f, hue %.0f°)" % (S, s_lo, hue)))
        # INFO: the same sample on the face only (skin below the brows' lowest point): on a bald head the brightest
        # 30 % of all the skin is the rim-lit dome, not the key-lit cheek (Kort, Olm) — numbers for the main session
        brows = m.get("brows") or []
        if brows:
            yb = max(p[1] for b in brows for p in b)
            face = sk.copy()
            face[: int(yb) + 1] = False
            if face.sum() > 100:
                cut_f = np.percentile(lab[..., 0][face], 70)
                lit_f = face & (lab[..., 0] >= cut_f)
                out.append(("lit cheek, face only (INFO)", 0.0, True, "L* %.1f S %.2f" % (
                    float(np.median(lab[..., 0][lit_f])), float(np.median(Q.hsv_s(im[..., :3][lit_f]))))))
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
            # INFO for the owner's call on the dark gate (§7.4 lets pupils, lash lines, mouth interiors, seams and
            # glasses sit below the floor): the dark pixels split by part — exempt groups vs the rest (shadow sides)
            op = im[..., 3] > 0.9
            dark = op & (Q.srgb_to_lab(im[..., :3])[..., 0] < 17)
            ex = np.zeros_like(dark)
            for kk, v in masks.items():
                if kk in ("lash", "pupil", "mouth", "glass", "catch") or kk.startswith("detail:glasses"):
                    ex |= v
            tot = max(1, int(op.sum()))
            idl.append("dark by part (INFO): exempt %.1f%%, other %.1f%%" % (100.0 * (dark & ex).sum() / tot,
                                                                         100.0 * (dark & ~ex).sum() / tot))
            for rule, v, ok, txt in id_rules(im, masks, Q.meta(d, n) or {}, n):
                idl.append("%s %s%s" % (rule, txt, "" if ok else " FAIL"))
                if rule.endswith("(INFO)"):
                    continue
                key = rule.split(" ")[0] if rule.startswith("signature") else rule
                tally.setdefault(key, [0, 0])
                tally[key][0] += ok
                tally[key][1] += 1
                bad |= not ok
            if n.startswith("ruler") and image_rules:
                crown = np.zeros(im.shape[:2], bool)
                for kk, v in masks.items():
                    if kk.startswith("detail:crown"):
                        crown |= v
                rc = rim_share(im, "#8FCDF2", "B", exclude=crown)
                if rc is not None:
                    idl.append("rim without the crown (INFO, §7.10 sets the gold at dL* ~4 to the sky) %.0f%%"
                               % (rc * 100))
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
