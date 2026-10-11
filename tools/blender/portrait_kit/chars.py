"""Characters as data (§7.5 "Персонаж — только данные"): the face table, signature, moods, palette, costume and pose of
each portrait of docs/art_direction.md §7.6, plus the signature registry and its lint (no two ids share a
signature; no two commanders wear the same headgear in one era).

P1 (the kit proof): Bram, Lira and Vega in era 1, calm and smile. Every other id keeps the old builder in
portrait_assets.py until P2/P3 add its entry here.

Units: lengths in H (head height without hair) unless noted; x / z offsets of marks are in head units relative to
the eye line; colours are albedo sRGB. Moods are deltas over the calm face (§7.9).
"""
from .style import SKIN

CHARS = {
    # ---------------------------------------------------------------- Bram (common): §7.6
    "cmd_bram": dict(
        name="Bram", rarity="common", female=False,
        # eye line 0.47 (§7.3 range 0.46-0.50, "lower = friendlier"): at 0.48 with H_px 280 the chin lands at
        # 0.654 h, past P-A6's 0.65 h
        head=dict(shape="square", wh=0.92, h_px=280, eye_line=0.47, cheeks=1.15, muzzle=1.15, brow_ridge=1.2),
        skin=SKIN["T2"], skin_tone="T2", blush=0.20,
        eyes=dict(sclera=0.18, open=0.72, iris="#3D8FD6", iris_shade=0.88, tilt=0.10, arch=0.22,
                  # the laugh squints (§7.6 "веки 0.55, глаза щурятся"): the cheek pushes the lower lid up into an
                  # arch; (open - low) x sclera stays >= 0.09 H so the eye keeps 3 px at 64 px (P-A3)
                  smile=dict(open=0.64, low=0.10, bow=0.30, tilt=-0.02, arch=0.26)),
        brows=dict(shape="bushy", thick=0.085, color="#8A3A1A", arch=0.02, len=1.25,
                   smile=dict(lift=(0.025, 0.02), arch=0.012)),
        nose=dict(type="potato", tip="#E8857A", tip_k=0.6, drop=0.20, k=1.0),
        mouth=dict(lip="#C4675A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.02, far=0.0),
                   smile=dict(type="open", w=0.34, h=0.14, near=0.045, far=0.03, dz=-0.012)),
        hair=dict(style="swept", color="#B5562B", dark="#5A200C", light="#B5562B", crevice="#46180A",
                  sideburns=True),
        # the beard #C8652F (§7.6) shaded hair-like but the other way up: lit lobe tips #D88048 on the slate jerkin
        # (dL* >= 15), roots #A04A22 and a #7A3216 band along the cheek (it no longer melts into the T2 skin); the
        # moustache in a darker rust, so it reads as hair over the lip, not a fleshy upper lip
        beard=dict(style="pear", color="#C8652F", tip="#D88048", root="#A04A22", edge="#7A3216", crevice="#5A220C",
                   wider=0.12, below=0.45, moustache=True, moustache_color="#A04A22", moustache_dark="#6A2810",
                   moustache_light="#B5562B"),
        scar=dict(near=True, **{"from": (-0.34, 0.01), "to": (-0.23, -0.14)}),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#DCCAA0", rough=0.85, sheen=0.25),
            layers=[
                # a laced jerkin closed under the beard (the beard lies on slate: dL* >= 15, §7.4); no shirt collar —
                # the beard covers the neck
                dict(kind="vest", id="jerkin", color="#3F4D5E", z0=-1.32, z1=-0.645, thick=0.032, rough=0.9, sheen=0.4,
                     shade=(0.94, 0.80),
                     open=[(-1.40, 0.10), (-1.15, 0.05), (-0.85, 0.05), (-0.70, 0.10), (-0.66, 0.16)]),
                dict(kind="belt", z=-1.09, w=0.13, color="#6B4226", buckle="#E0AD45", over=0.05),
            ]),
        props=[dict(kind="spoon", x=-0.15, lean=20, bowl=0.16),
               dict(kind="amulet", x=-0.36, z=-0.95, d=0.16),
               dict(kind="chevrons", n=2, color="#C0452A")],
        pose=dict(body=22, head=6, roll=0, nod=-2),
        pose_smile=dict(roll=-3, nod=0),
        signature=dict(name="pear beard", zone="lower face width"),
    ),
    # ---------------------------------------------------------------- Lira (common): §7.6
    "cmd_lira": dict(
        name="Lira", rarity="common", female=True,
        head=dict(shape="oval", wh=0.80, h_px=268, eye_line=0.46, cheeks=1.0, chin=0.005),
        skin=SKIN["T1"], skin_tone="T1", blush=0.25, freckles="#C77B52",
        eyes=dict(sclera=0.21, open=0.82, iris="#5E9E4A", tilt=0.06, arch=0.26, flick=0.06,
                  smile=dict(open=0.78, low=0.26, bow=0.35, tilt=-0.02, arch=0.30)),
        brows=dict(shape="arc", thick=0.06, color="#4A2818", arch=0.03, len=1.2, len_far=1.42,
                   smile=dict(lift=(0.004, 0.0), arch=0.004)),
        nose=dict(type="button", tip="#F09A86", tip_k=0.45, drop=0.19, k=0.95),
        mouth=dict(lip="#D9786A", line=0.185,
                   calm=dict(type="closed", w=0.26, near=0.012, far=0.004),
                   smile=dict(type="open", w=0.32, h=0.12, near=0.03, far=0.025)),
        hair=dict(style="kerchief", color="#5A3420", dark="#4A2A1A", light="#7A4A30", crevice="#2A160C", fringe=0.08,
                  braid=dict(w=0.17, ribbon="#3E9B5A")),
        # the kerchief in her green (§7.6 gives no colour for it; palette slots only): white cloth on the light grey
        # plate melted at the rim (P-A5) and repeated the apron; the lighter leaf green still melted where the rim
        # light catches its top edge; a shade darker than the jacket (#22603A) so the two greens read as two layers
        headgear=dict(kind="kerchief", color="#22603A", thick=0.075, tail=0.34, knot_az=-138, knot_el=24),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#2E7A44", rough=0.85, sheen=0.35),
            layers=[
                dict(kind="collar", color="#2E7A44", z=-0.64, h=0.07, out=0.012, flare=0.014),
                dict(kind="bib", color="#F2F0EA", w=0.16, top=-0.82, bottom=-2.0, straps=True),
                dict(kind="strap", id="strap", color="#8A5A34", detail="satchel_strap", min_px=3000,
                     **{"from": (0.46, -0.70), "to": (-0.62, -1.75)}, w=0.10),
            ]),
        props=[dict(kind="badge", on="strap", z=-0.98, d=0.20, leaf="#3E9B5A", detail="leaf"),
               dict(kind="bandage", on="strap", z=-1.20, d=0.12)],
        pose=dict(body=20, head=8, roll=5, nod=0),
        pose_smile=dict(roll=-2, nod=2),
        signature=dict(name="braid over the near shoulder + kerchief knot tails", zone="near shoulder; top back"),
    ),
    # ---------------------------------------------------------------- Vega (rare): §7.6
    "cmd_vega": dict(
        name="Vega", rarity="rare", female=True,
        # eye line 0.46 (§7.3 range 0.46-0.50): her chin-up pose (+4) lifts the eyes more than the chin in the
        # level camera, and at 0.48 the chin lands at 0.659 h, past P-A6's 0.65 h
        head=dict(shape="heart", wh=0.78, h_px=270, eye_line=0.46, cheekbones=0.03, chin=0.0),
        skin=SKIN["T3"], skin_tone="T3", blush=0.2,
        eyes=dict(sclera=0.19, open=0.70, iris="#7C7EA8", tilt=-0.06, arch=0.30, flick=0.065,
                  smile=dict(open=0.72, low=0.20, bow=0.30, tilt=-0.08, arch=0.30)),
        brows=dict(shape="angular", thick=0.055, color="#2A2224", arch=0.035, arch_far=0.03, lift=(0.0, 0.09), len=1.3,
                   len_far=1.95, in_far=0.84,   # the raised far brow ends at the face edge: it starts nearer the nose
                   smile=dict(lift=(0.01, 0.0))),
        nose=dict(type="straight", tip="#E59A7E", tip_k=0.35, drop=0.21, k=1.0, w=0.05),
        mouth=dict(lip="#B8605A", line=0.19,
                   calm=dict(type="closed", w=0.25, near=0.025, far=0.0),
                   # the closed smile's corners rise >= 6 px over the calm ones on the master (P-A4), the
                   # expression alone (pose held), not only the head's tilt
                   smile=dict(type="closed", w=0.30, near=0.068, far=0.045, sag=0.012)),
        hair=dict(style="bob", color="#2E2A2A", dark="#1E1A1C", light="#4A4446", crevice="#121012", near_len=0.10,
                  far_len=0.26, streak="#C8CCD4"),
        body=dict(shoulders=1.95),
        costume=dict(
            base=dict(color="#44484F", rough=0.8, sheen=0.3),
            layers=[
                dict(kind="collar", color="#F2F2F2", z=-0.66, h=0.13, out=0.018, flare=0.035, gap=0.05, thick=0.03),
                dict(kind="placket", color="#3A3D44", w=0.05, top=-0.74),
                dict(kind="frogging", color="#C8CCD4", z=(-0.86, -0.98, -1.10), w=0.24, t=0.028),
            ]),
        # glasses w / h: the rim's half size in units of the visible eye's half width / half height (the almond)
        props=[dict(kind="glasses", color="#44484F", frame=0.025, w=2.0, h=1.26, drop=0.03, off=0.028, tint="#FFFFFF"),
               dict(kind="pointer", x=0.62, y=0.04, z=-1.02, reach=0.345, tip_w=1.4, color="#8A5A34")],
        pose=dict(body=26, head=4, roll=3, nod=4),
        pose_smile=dict(roll=-2, nod=0),
        signature=dict(name="chisel bob + glasses bar; arrow right", zone="far side"),
    ),
}

KIT_IDS = set(CHARS)
KIT_ERAS = {cid: {1} for cid in CHARS}      # eras the kit builds; the rest falls back to the old builder

# headgear per era for the uniqueness lint (§7.6: «Головные уборы в одной эпохе не повторяются»)
HEADGEAR = {cid: {1: (c.get("headgear") or {}).get("kind")} for cid, c in CHARS.items()}


def lint():
    """Fail the build when two ids share a signature or two commanders share a headgear in one era."""
    errs = []
    seen = {}
    for cid, c in CHARS.items():
        s = c.get("signature", {}).get("name")
        if not s:
            errs.append("%s has no signature" % cid)
        elif s in seen:
            errs.append("%s and %s share the signature %r" % (seen[s], cid, s))
        else:
            seen[s] = cid
    for era in (1, 2, 3, 4):
        worn = {}
        for cid, by_era in HEADGEAR.items():
            k = by_era.get(era)
            if k:
                if k in worn:
                    errs.append("era %d: %s and %s both wear %s" % (era, worn[k], cid, k))
                worn[k] = cid
    if errs:
        raise ValueError("chars.py lint: " + "; ".join(errs))
    return True
