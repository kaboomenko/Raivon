"""Characters as data (§7.5 "Персонаж — только данные"): the face table, signature, moods, palette, costume and pose of
each portrait of docs/art_direction.md §7.6, plus the signature registry and its lint (no two ids share a
signature; no two commanders wear the same headgear in one era).

P1 (the kit proof): Bram, Lira and Vega in era 1, calm and smile. P2: all twelve commanders in era 1 (eras 2–4,
the leaders and the ruler keep the old builder in portrait_assets.py until P3 adds them here). A prop with a "hand"
pose (§7.5: Vega's pointer, Seir's spyglass, Vance's queen, Irma's gauntlet) builds the hand when the character's
"hands" is on (default) and its hand-free fallback otherwise (KIT_HANDS=0 / 1 forces either, for the review of §7.15
q3). Vega's is off (decided after P1: she carries no pointer) and Vance's (P2 review: the pendant fallback won); their
hands are built only under KIT_HANDS=1.

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
        # "T2 румяный" (§7.6) beside ginger hair (art director note 1): T2's lightness moved toward peach-pink (hue
        # 22 -> 12 deg: rendered skin 12-13 deg against the hair's 17-19, not orange on orange), its saturation
        # boost a little higher than T2's 1.15 so the lit cheek keeps HSV S >= 0.35 (§7.4)
        skin="#FFA08D", skin_tone="T2", skin_sat=1.22, blush=0.25,
        # calm: the stern half-smile (§7.6 "суровая полуулыбка") — a heavy, flat upper lid (arch 0.10), its inner end
        # a little lower than the outer (tilt -0.04: a lid falling toward the temple read as worried), the brows'
        # inner ends 0.01 H down
        eyes=dict(sclera=0.18, open=0.72, iris="#3D8FD6", iris_shade=0.88, tilt=-0.04, arch=0.10,
                  # the laugh squints (§7.6 "веки 0.55, глаза щурятся"): the cheek pushes the lower lid up into an
                  # arch (low >= 0.2: below that the almond's own curve takes over and the lid stays a flat U);
                  # (open - low) x sclera = 0.086 H keeps >= 3 px of opening at 64 px (P-A3)
                  smile=dict(open=0.68, low=0.20, bow=0.30, tilt=-0.04, arch=0.22)),
        brows=dict(shape="bushy", thick=0.085, color="#8A3A1A", arch=0.02, len=1.25, inner=-0.01,
                   smile=dict(lift=(0.025, 0.02), arch=0.012, inner=0.01)),
        nose=dict(type="potato", tip="#E8857A", tip_k=0.6, drop=0.20, k=1.0),
        mouth=dict(lip="#C4675A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.02, far=0.0),
                   # h 0.12 (§7.3 norm): at 0.14 the opening reached the chin and the beard under it sat in a
                   # deep shadow shelf (dark pixels past §7.4's 3 %)
                   smile=dict(type="open", w=0.34, h=0.12, near=0.045, far=0.03, dz=-0.012)),
        hair=dict(style="swept", color="#B5562B", dark="#5A200C", light="#B5562B", crevice="#46180A",
                  sideburns=True),
        # the beard #C8652F (§7.6) shaded hair-like but the other way up: lit lobe tips #D88048 on the slate jerkin
        # (dL* >= 15), roots #8E3E1C and a #74301A band along the cheek (beard vs skin >= 15, also at the boundary:
        # art director note 1); a soft #7A3216 crevice tone between the strand groups; the moustache in a darker
        # rust, so it reads as hair over the lip, not a fleshy upper lip
        beard=dict(style="pear", color="#C8652F", tip="#D88048", root="#8E3E1C", edge="#74301A", crevice="#7A3216",
                   wider=0.12, below=0.45, moustache=True, moustache_color="#A04A22", moustache_dark="#6A2810",
                   moustache_light="#B5562B"),
        scar=dict(near=True, **{"from": (-0.34, 0.01), "to": (-0.23, -0.14)}),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#DCCAA0", rough=0.85, sheen=0.25),
            layers=[
                # a laced jerkin closed under the beard (the beard lies on slate: dL* >= 15, §7.4; #3F4D5E a step
                # darker, #3B4859: the smile measured 14.7 at 64 samples); no shirt collar —
                # the beard covers the neck
                # (shade 0.94 -> 0.87 down the jerkin, not 0.80: under the beard's shadow the bottom went past the
                # albedo floor — dark pixels, §7.4)
                dict(kind="vest", id="jerkin", color="#3B4859", z0=-1.32, z1=-0.645, thick=0.032, rough=0.9, sheen=0.4,
                     shade=(0.94, 0.87),
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
        skin=SKIN["T1"], skin_tone="T1", blush=0.25, freckles="#C77B52", skin_sat=1.30,    # lit cheek S >= 0.35
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
        # no pointer (decided after P1: "Vega carries no pointer — her brow and glasses are the signature"); the
        # held pointer below is built only with KIT_HANDS=1, for the hand / hand-free comparison of §7.15 q3
        hands=False,
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
        # the streak a step under the #C8CCD4 silver slot (it read as a white headband at 64-128 px, review r3):
        # lightest at the tip, darkest where it grows out of the dark hair at the root
        # the bob's darks lifted a step over the albedo floor (#1E1A1C / #121012 rendered 2.7 % of the figure under
        # L* 17, §7.4's dark budget is 3 % for pupils, lashes, mouth and seams together)
        hair=dict(style="bob", color="#363032", dark="#2E2A2C", light="#544C4E", crevice="#2E2A30", near_len=0.10,
                  far_len=0.26, streak="#C8CCD4", streak_tip="#B8BCC4", streak_mid="#A9ADB5", streak_root="#8E929A",
                  streak_crevice="#8E929A"),
        body=dict(shoulders=1.95),
        costume=dict(
            # the graphite #44484F a step cooler (#3F4658, same value): beside Frey's dark green the two read as one
            # grey-green (P-A9 mean dE 12.8)
            base=dict(color="#3F4658", rough=0.8, sheen=0.3),
            layers=[
                dict(kind="collar", color="#F2F2F2", z=-0.66, h=0.13, out=0.018, flare=0.035, gap=0.05, thick=0.03),
                dict(kind="placket", color="#363C4C", w=0.05, top=-0.74),
                dict(kind="frogging", color="#C8CCD4", z=(-0.86, -0.98, -1.10), w=0.24, t=0.028),
            ]),
        # glasses w / h: the rim's half size in units of the visible eye's half width / half height (the almond).
        # The pointer (§7.6 "стрела-указка ... ближняя кисть на древке") waits for P2's hand module: without a hand
        # the rod could only leave the body at the far side's contour (the far arm is fused into the torso and seen
        # edge-on in the 3/4 view), and it read as an arrow stuck through her side — "no prop may enter the body
        # without a visible holder" (art director note 2, review r3). The raised brow and the glasses carry her in
        # P1; P2 adds back: dict(kind="pointer", x=0.62, y=0.04, z=-1.02, reach=0.345, tip_w=1.8, color="#8A5A34")
        props=[dict(kind="glasses", color="#44484F", frame=0.025, w=2.0, h=1.26, drop=0.03, off=0.028, tint="#FFFFFF"),
               # P2: the pointer held by the near hand across the chest (hand-free: none, as in P1 — the brow and
               # the glasses carry her)
               dict(kind="pointer", grip=(-0.16, -1.0), reach_hand=0.62, back=0.07, color="#8A5A34", tip_w=1.8, free="none",
                    hand=dict(grip="wrap", curl=0.95, face="fingers", elbow=(-0.30, -0.55, -1.75), sleeve="#44484F",
                              cuff="#F2F2F2"))],
        pose=dict(body=26, head=4, roll=3, nod=4),
        pose_smile=dict(roll=-2, nod=0),
        signature=dict(name="chisel bob + glasses bar; arrow right", zone="far side"),   # the arrow: with P2's hand
    ),
    # ---------------------------------------------------------------- Kort (rare): §7.6
    "cmd_kort": dict(
        name="Kort", rarity="rare", female=False,
        # "массивный квадрат 1.0, 284 (самая крупная), брыли, большие уши"; eye line 0.50 (§7.3: Kort)
        head=dict(shape="square", wh=1.0, h_px=284, eye_line=0.50, jowls=1.0, cheeks=1.2, muzzle=1.1, brow_ridge=1.3,
                  jaw=0.02),
        ear_k=1.25,
        # "T2 румяный" as a deeper rosy pink (#D88878): the white brows measured only 12.6 L* over the skin at #F2A07E
        # (§7.4: white brows >= 18 L* lighter than the skin); the pink hue (<= 16 deg) keeps it from going pumpkin
        # orange as it darkens (and takes §7.4's S floor 0.27 for peach-pink skin)
        skin="#D88878", skin_tone="T2", blush=0.28, skin_sat=1.32,
        # heavy lids 0.50 with a crease, grey-blue, small "spark" catchlights; the smile opens them to 0.70
        eyes=dict(sclera=0.18, open=0.50, iris="#8AA0B4", iris_shade=0.85, tilt=-0.10, arch=0.06, catch_k=1.0,
                  iris_k=1.08, pupil=0.62,
                  smile=dict(open=0.70, low=0.16, bow=0.25, tilt=-0.08, arch=0.16)),
        brows=dict(shape="bushy", thick=0.09, color="#FFFFFF", arch=0.03, len=1.3, outer=-0.035, inner=0.005, rough=0.35,
                   sheen=0.6,
                   smile=dict(lift=(0.02, 0.012))),
        nose=dict(type="aquiline", len=0.24, w=0.068, proj=0.075, hump=0.022, drop=0.21, tip="#E8806E", tip_k=0.55),
        mouth=dict(lip="#C4675A", line=0.20,
                   calm=dict(type="closed", w=0.26, near=-0.005, far=-0.005),
                   smile=dict(type="open", w=0.32, h=0.12, near=0.035, far=0.03, dz=-0.012)),
        hair=dict(style="tufts", bald=True, color="#FCFCFF", dark="#EEEEF4", light="#FFFFFF", crevice="#C4C8D6",
                  tufts=dict(band_az=100, band_lo=-26, band_hi=6, out=0.12, up=0.30,
                             fans=[(104, 8, 1.1, 0.065, 5), (126, 0, 0.95, 0.06, 4)])),
        # the walrus moustache, white #EDEDF2, 0.85 W wide, hanging 0.25 H below the mouth (§7.6)
        beard=dict(style="walrus", color="#EDEDF2", tip="#FFFFFF", root="#D4D6DE", crevice="#7E8496", w=0.85,
                   drop=0.30, smile_lift=0.04),
        age=dict(forehead=3, crows=3, nasolabial=False, k=0.45, smile_k=0.55),
        body=dict(shoulders=2.15, neck=0.55),
        costume=dict(
            base=dict(color="#5D6236", rough=0.85, sheen=0.3),
            layers=[
                dict(kind="placket", color="#4E5330", w=0.045, top=-0.80, x=0.0),
                dict(kind="buttons", id="button", at=[(0.0, -0.98), (0.0, -1.16)], r=0.032, color="#B0803A"),
                # the dark karakul collar #6B5040 in ribbons: wide over the shoulders (his "shoulder width" zone),
                # open in front down to the clasp
                # the darks lifted (#4E3A2E / #2E221C rendered 4.2 % of the figure under L* 17: §7.4 allows 3 % for
                # pupils, lashes, mouth and seams together)
                dict(kind="fur", id="fur", color="#6B5040", dark="#5E4A3A", light="#8A6850", crevice="#54402F",
                     r=0.70, r_in=0.30, t=0.11, front_z=-1.05, side_z=-0.94, back_z=-0.86, open=0.10,
                     # fewer, larger, smoother curls (art director note 3: no cauliflower)
                     clumps=dict(n=70, len=0.11, w=0.06, th=0.036), detail="fur", min_px=8000, signature=True,
                     smooth=3),
                dict(kind="clasp", color="#B0803A", z=-0.90, x=0.075),
            ]),
        props=[dict(kind="hourglass", at=(-0.23, -0.93), h=0.22, button="button_0", sag=0.02)],
        pose=dict(body=16, head=2, roll=0, nod=-4),
        pose_smile=dict(roll=-3, nod=2),
        signature=dict(name="dome + walrus moustache + dark fur collar", zone="lower face width; shoulders"),
    ),
    # ---------------------------------------------------------------- Olm (common): §7.6
    "cmd_olm": dict(
        name="Olm", rarity="common", female=False,
        head=dict(shape="long", wh=0.75, h_px=276, eye_line=0.48, brow_ridge=1.3, cheeks=0.95, muzzle=1.05),
        skin="#E8926C", skin_tone="T2", blush=0.24,
        # the squint (§7.6: near 0.55, far 0.68, the lower lid +0.02): "смотрит поверх носа"
        eyes=dict(sclera=0.18, open=[0.55, 0.68], low=0.02, iris="#6F8FA8", iris_shade=0.85, tilt=0.0, arch=0.14,
                  smile=dict(open=[0.62, 0.68], low=0.12, bow=0.25, arch=0.18)),
        # #74727C (§7.6) measured brow-skin dL* 11 (P-A5 needs >= 18): two steps darker in the same grey
        # the far brow starts nearer the nose (in_far): on his 24/+10 turn its outer half ran past the face's edge
        # (P-A3 64 px far brow 5.2 px long, needs 6)
        brows=dict(shape="angular", thick=0.065, color="#504E58", arch=0.03, lift=(0.0, 0.03), len=1.25, len_far=2.1,
                   in_far=1.1,
                   smile=dict(lift=(0.02, 0.01))),
        nose=dict(type="aquiline", len=0.28, w=0.06, proj=0.085, hump=0.026, drop=0.25, tip="#DE7868", tip_k=0.6),
        mouth=dict(lip="#B8645A", line=0.19,
                   calm=dict(type="closed", w=0.26, near=-0.015, far=0.0),
                   # the crooked grin: the far corner higher, a gap in the teeth (§7.6 "щербинка")
                   smile=dict(type="open", w=0.31, h=0.115, near=0.02, far=0.055, dz=-0.01, gap=0.22)),
        hair=dict(style="tufts", bald=True, color="#D0D0D4", dark="#A8A8B0", light="#ECECF0", crevice="#6E6E7A",
                  tufts=dict(band_az=95, band_lo=-20, band_hi=10, out=0.10, up=0.35,
                             fans=[(90, 20, 1.0, 0.06, 5), (110, 13, 0.85, 0.055, 4)])),
        beard=dict(style="chops", color="#D0D0D4", tip="#E4E4E8", root="#B0B0B8", crevice="#6E6E7A", w=0.16,
                   thick=0.05),
        age=dict(forehead=3, crows=3, nasolabial=True, k=0.4, smile_k=0.5),
        headgear=dict(kind="goggles", id="brass_goggles", style="brass", lens=0.22, rim=0.03, el=47, spread=19, tilt=0.35, depth=0.10,
                      loupe=0.10, rim_color="#EDB64A", lens_color="#7FD2E6", strap="#7A4E2D", detail="goggles", metallic=0.2,
                      min_px=1500, signature=True),
        body=dict(shoulders=1.95),
        costume=dict(
            # the linen a step lighter than #E8DCC0: on plate B's grey it rendered L* 77 against the plate's 72 (66 %
            # of the shirt "melting", §7.4: light costume on grey >= 82)
            base=dict(color="#FAF4E6", rough=0.85, sheen=0.25),
            # leather sleeve guards over the linen (the leather slot): the cream sleeves melted into the light grey
            # plate (P-A5 band dL* 7.8)
            sleeve=dict(color="#7A4E2D", rough=0.55, sheen=0.1),
            layers=[
                dict(kind="collar", color="#FAF4E6", z=-0.64, h=0.06, out=0.01, flare=0.012, gap=0.06),
                # the leather apron >= 50 % of the shoulder band (§7.6), on neck straps
                dict(kind="bib", id="apron", color="#7A4E2D", leather=True, w=0.30, top=-0.80, bottom=-2.0,
                     straps=True, detail="apron", min_px=6000),
                # a deep pocket that visibly holds the wrench (art director, P2 sheet: it floated in front)
                dict(kind="pocket", id="pocket", on="apron", at=(0.15, -1.00), w=0.13, h=0.22, color="#6B4426"),
            ]),
        # the wrench is a far-side mark, not part of the signature (the brass goggles): its iron grey pulled the
        # signature's colour onto the grey plate (signature-plate dE 22.8, §7.4 needs 25)
        props=[dict(kind="wrench", pocket="pocket", len=0.70, jaw=0.22, ang=10, color="#9AA4B0", signature=False,
                    depth=0.17, inset=0.010, dy=0.04, top_dy=0.10),
               dict(kind="pencil", color="#C9A24A")],
        pose=dict(body=24, head=10, roll=-4, nod=3),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="brass goggles on a bald dome + fluffy sides", zone="double bump on top"),
    ),
    # ---------------------------------------------------------------- Vik (common): §7.6
    "cmd_vik": dict(
        name="Vik", rarity="common", female=False,
        head=dict(shape="long", wh=0.80, h_px=264, eye_line=0.46, cheeks=1.0),
        skin="#F2A276", skin_tone="T2", blush=0.30, skin_value=1.0,
        paint=[dict(at=(0.0, -0.13), r=0.13, color="#D9825A", k=0.32)],          # the tan across the nose
        eyes=dict(sclera=0.22, open=0.85, iris="#C98A2E", iris_shade=0.85, tilt=0.06, arch=0.26,
                  smile=dict(open=0.74, low=0.22, bow=0.3, arch=0.3)),
        # #9A7A3A (§7.6) measured brow-skin dL* 14 (P-A5 >= 18): darker in the same straw-brown (#5A4420)
        # 0.065, not §7.6's 0.055: 0.055 H is 1.8 px at 64 px on his 264 px head (P-A3 needs 2)
        brows=dict(shape="straight", thick=0.065, color="#5A4420", arch=0.015, outer=0.025, len=1.2, len_far=1.75,
                   in_far=0.84),
        nose=dict(type="straight", w=0.05, drop=0.19, k=0.85, tip="#E89070", tip_k=0.4),
        mouth=dict(lip="#C4675A", line=0.20,
                   calm=dict(type="closed", w=0.25, near=0.03, far=0.005),
                   smile=dict(type="open", w=0.32, h=0.11, near=0.075, far=0.035, dz=-0.01, fang="near")),
        # straw lifted toward pale cream (#EBD27A measured hair-skin dE 20.6, #FAEBA2 24.5, a golden #F6D85E 20.4 —
        # yellow chroma sits on the skin's own b*; P-A5 needs 30): lightness and a cooler hue separate it; five broad
        # locks swept to the far side, overlapping, the far ones short so the far brow shows (six even ones read as a
        # row of teeth)
        hair=dict(style="fringe", color="#FFF6CC", dark="#E8D490", light="#FFFCEE", crevice="#7A5A20", tip_el=45,
                  locks=[(-36, 0.12, 14, 0.95), (-14, 0.13, 20, 1.2), (8, 0.12, 22, 0.95), (26, 0.10, 20, 0.7),
                         (42, 0.085, 16, 0.55)]),
        headgear=dict(kind="hood", color="#4E6B3A", thick=0.075, peak=0.25, edge_r=0.05),
        body=dict(shoulders=1.75),
        costume=dict(
            base=dict(color="#6B4A2A", rough=0.6, sheen=0.15),
            layers=[
                dict(kind="cloak", id="cloak", color="#4E6B3A", z1=-0.64, gap=0.03, flare=0.10,
                     open=[(-1.9, 0.34), (-1.2, 0.26), (-0.85, 0.18), (-0.66, 0.14)]),
                # the quiver strap a step over the albedo floor (#3E2A18 went under L* 17 in shadow: §7.4 dark budget)
                dict(kind="strap", id="strap", color="#4E3620", **{"from": (0.40, -0.72), "to": (-0.45, -1.6)},
                     w=0.07),
            ]),
        props=[dict(kind="raven", x=-0.70, y=0.10, size=0.55, turn=30),
               dict(kind="bow", x0=0.66, y=0.26, z0=-0.86, len=0.6, lean=10)],
        pose=dict(body=18, head=14, roll=-6, nod=2),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="raven on the near shoulder + hood peak back", zone="near shoulder; top back"),
    ),
    # ---------------------------------------------------------------- Seir (rare): §7.6
    "cmd_seir": dict(
        name="Seir", rarity="rare", female=False,
        head=dict(shape="square", wh=0.88, h_px=272, eye_line=0.48, jaw=-0.03, cheeks=1.1),
        skin=SKIN["T4"], skin_tone="T4", blush=0.32,
        paint=[dict(at=(0.0, -0.20), r=0.07, color="#D0604A", k=0.35)],          # the ruddy nose
        eyes=dict(sclera=0.18, open=0.58, low=0.10, iris="#2F8FB0", iris_shade=0.9, tilt=0.02, arch=0.16,
                  smile=dict(open=0.62, low=0.13, bow=0.3, arch=0.22)),
        # #6E6E74 (§7.6) measured brow-skin dL* 7 on his T4 tan (P-A5 >= 18): the pepper of "перец с солью" darker
        brows=dict(shape="arc", thick=0.065, color="#3E3E46", arch=0.02, outer=-0.025, len=1.25),
        nose=dict(type="aquiline", len=0.22, w=0.075, proj=0.07, hump=0.016, drop=0.21, tip="#C8604A", tip_k=0.5),
        mouth=dict(lip="#A85A4A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.012, far=0.006),
                   smile=dict(type="open", w=0.34, h=0.13, near=0.045, far=0.04, dz=-0.012)),
        hair=dict(style="short", color="#CFCFD4", dark="#A8A8B0", light="#E8E8EC", crevice="#6E6E7A"),
        beard=dict(style="short", color="#B8B8C0", tip="#C6C6CC", root="#A0A0AA", crevice="#62626E", thick=0.06, under=0.03,
                   moustache=True, moustache_color="#C4C4CA", moustache_dark="#A0A0A8", moustache_light="#DADADE",
                   moustache_k=0.72),
        age=dict(forehead=2, crows=3, nasolabial=True, k=0.4, smile_k=0.65),
        headgear=dict(kind="tricorn", color="#134B5F", trim="#F2F2F2", rim_dz=0.0, crown=0.20, wall=0.19, crown_sub=1,
                      corner=0.24, mid=0.02),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#175A72", rough=0.85, sheen=0.3),
            layers=[
                dict(kind="neckerchief", color="#F2F2F2", z=-0.64),
                dict(kind="lapels", color="#175A72",
                     shape=[(0.10, -0.66), (0.30, -0.70), (0.42, -0.80), (0.36, -0.86), (0.30, -1.02), (0.05, -1.20)]),
                dict(kind="buttons", id="btn", r=0.036, color="#E0AD45",
                     at=[(-0.22, -0.98), (0.22, -0.98), (-0.20, -1.14), (0.20, -1.14)]),
            ]),
        props=[dict(kind="spyglass", len=0.8, d=0.11, ang=50, dir_world=(-0.8, 0.6, 0.0), rest=(-0.48, None),
                    dir_world_hand=(-0.5, 0.86, 0.0), rest_hand=(-0.58, None),
                    rest_y=0.06, below=0.30, strap_from=(-0.42, -0.70), strap_to=(0.55, -1.6), grip_t=0.10,
                    below_hand=0.48,
                    hand=dict(grip="wrap", curl=1.0, elbow=(-0.45, -0.40, -1.75), sleeve="#175A72",
                              cuff="#F2F2F2")),
               dict(kind="earring", style="ring", d=0.11, tube=0.034, color="#E8B23A")],
        pose=dict(body=24, head=10, roll=-3, nod=3),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="tricorn + spyglass diagonal behind the head", zone="hat line; near shoulder"),
    ),
    # ---------------------------------------------------------------- Frey (rare): §7.6
    "cmd_frey": dict(
        name="Frey", rarity="rare", female=True,
        # she keeps the square jaw (§7.3: "Фрей сохраняет квадратную челюсть"): +0.06 cancels the women's -6 %
        head=dict(shape="square", wh=0.95, h_px=278, eye_line=0.48, chin=0.01, jaw=0.06, cheeks=1.05),
        skin=SKIN["T5"], skin_tone="T5", blush=0.2, skin_sat=1.08,              # lit cheek S >= 0.35
        eyes=dict(sclera=0.19, open=0.72, iris="#8A5A2E", tilt=0.0, arch=0.18, flick=0.028,
                  smile=dict(open=0.62, low=0.20, bow=0.3, arch=0.24)),
        brows=dict(shape="straight", thick=0.075, color="#2A2020", arch=0.01, len=1.25, inner=-0.01, gap=0.04,
                   smile=dict(lift=(0.015, 0.01))),
        brow_scar=dict(x=0.12, color="#C88A6A", w=0.025),
        nose=dict(type="straight", w=0.07, drop=0.21, k=1.05, tip="#A8603E", tip_k=0.3),
        mouth=dict(lip="#A0524A", line=0.20,
                   calm=dict(type="closed", w=0.28, near=0.01, far=0.0),
                   smile=dict(type="open", w=0.30, h=0.10, near=0.035, far=0.025, dz=-0.01)),
        # a light ash-brown buzz-cut ("ёжик"), not §7.6's #2A2420: the art director's P2 note — it must read as HAIR,
        # lighter than the uniform, with a bristly edge and the forehead and temples bare below it (the dark shell
        # read as a beanie); light also keeps hair vs her T5 skin >= 15 L* (§7.4)
        hair=dict(style="flattop", color="#A8907A", dark="#7C6650", light="#CCB89E", crevice="#4A3A2C", side=0.026,
                  top=0.15, plane_k=0.08, stubble=0.8, bristle=0.012,
                  # the corners recede at the temples (a straight line across the forehead read as a cap's rim)
                  hairline=[(0, 0.31), (16, 0.315), (30, 0.29), (42, 0.265), (56, 0.25), (72, 0.20), (92, 0.11),
                            (130, -0.05), (180, -0.20)]),
        # 2.6 W across the pauldrons (§7.6 "самые широкие плечи (2.6 W, наплечники из 3 пластин)"): the bust 2.25 W,
        # the plates add the rest (a 2.6 W torso alone runs past the frame's side band at every head size)
        body=dict(shoulders=2.15, absolute=True),
        costume=dict(
            # the §7.6 dark green #3B5A44 more saturated (#1F7040, same hue): beside Vega's graphite it read as the
            # same grey (P-A9 mean dE 10-12; their hair, skin and dark signatures are close by design)
            base=dict(color="#1F7040", rough=0.85, sheen=0.3),
            layers=[
                dict(kind="collar", color="#1F7040", z=-0.64, h=0.08, out=0.016, flare=0.02),
                # fewer, softer channels (art director, P2 sheet: twelve dark seams read as a radiator)
                dict(kind="quilt", on="torso", color="#1B6239", z=(-1.45, -0.74), dx=0.26, w=0.66, r=0.006),
                dict(kind="pauldrons", color="#C8D0DA", stripe="#2E8A50", stripe_r=0.02, n=3, spread=88, detail="pauldrons",
                     min_px=10000),
            ]),
        props=[dict(kind="badge_relief", style="tower", at=(-0.26, -0.95), size=0.24, color="#C8CCD4", dark="#2C4434",
                    detail="badge"),
               dict(kind="earring", style="stud", color="#C8D0DA")],
        pose=dict(body=14, head=0, roll=0, nod=-2),
        pose_smile=dict(roll=-3, nod=2),
        signature=dict(name="flat square top + widest shoulders", zone="top centre; shoulder width"),
    ),
    # ---------------------------------------------------------------- Irma (epic): §7.6
    "cmd_irma": dict(
        name="Irma", rarity="epic", female=True,
        # hand-free (§7.15 q3, art director on the P2 sheet: the gloved hand at the collar read as a claw at the
        # throat): the gauntlets tucked under the chest strap; KIT_HANDS=1 still builds the hand
        hands=False,
        head=dict(shape="heart", wh=0.80, h_px=268, eye_line=0.47, cheekbones=0.04, chin=0.005),
        skin=SKIN["T1"], skin_tone="T1", blush=0.22, skin_sat=1.34,
        eyes=dict(sclera=0.20, open=0.70, low=0.02, iris="#7FC4E8", iris_shade=0.72, tilt=0.10, arch=0.22, flick=0.07,
                  smile=dict(open=0.62, low=0.20, bow=0.3, tilt=0.06, arch=0.26)),
        # #7A7060 (§7.6, "темнее волос") measured brow-skin dL* 10 (P-A5 >= 18): darker in the same taupe
        # the smile's raised brow (§7.6 "одна бровь вверх") is the near one, +0.05: the far one raised went under the
        # fringe and the goggles (P-A3 64 px far brow 1.8 x 2.0 px); the far brow long and starting nearer the nose
        # (her 28/+12 turn foreshortens it)
        brows=dict(shape="straight", thick=0.06, color="#564E42", arch=0.01, outer=0.035, len=1.25, len_far=2.3,
                   in_far=1.0, smile=dict(lift=(0.05, 0.0))),
        nose=dict(type="straight", w=0.045, drop=0.19, k=0.85, tip="#F0A088", tip_k=0.35),
        mouth=dict(lip="#C86A6A", line=0.19,
                   calm=dict(type="closed", w=0.26, near=0.02, far=0.0, sag=0.004),
                   smile=dict(type="open", w=0.31, h=0.11, near=0.065, far=0.035, dz=-0.01)),
        oil=dict(**{"from": (-0.31, -0.13), "to": (-0.19, -0.19)}, color="#5A4A44", k=0.7, w=0.05),
        # platinum cool and bright (a warm #EFE9DC measured hair-skin dE 28 on her T1, P-A5 needs 30)
        hair=dict(style="ponytail", color="#F4F4F6", dark="#C6CAD4", light="#FFFFFF", crevice="#7A8090",
                  # one clear tail with a hair tie, falling behind (art director, P2 sheet: the wide arc of fanned
                  # clumps read as two rabbit ears)
                  tail=dict(up=0.07, band="#3A3C46", r0=0.035, r1=0.035, r2=0.03, band_at=1, band_r=0.055)),
        headgear=dict(kind="goggles", id="motor_goggles", style="rubber", lens=0.15, rim=0.035, el=40, spread=18, tilt=0.45, oval=0.78,
                      depth=0.06, rim_color="#2E2E34", lens_color="#F5A050", strap="#2E2E34", detail="goggles",
                      min_px=1200),
        body=dict(shoulders=1.9),
        costume=dict(
            base=dict(color="#3A3C46", rough=0.45, sheen=0.1),
            layers=[
                dict(kind="collar", color="#3A3C46", z=-0.66, h=0.20, out=0.008, flare=0.07, gap=0.10, thick=0.03,
                     piping="#F08A24", piping_r=0.024),
                dict(kind="placket", color="#F08A24", w=0.08, top=-0.76, x=0.03),      # P-A8: orange >= 3 %
                dict(kind="strap", id="strap", color="#2E2E34", **{"from": (-0.40, -0.72), "to": (0.45, -1.6)},
                     w=0.075),
            ]),
        props=[dict(kind="gauntlet", on="strap", z=(-0.95, -1.06), color="#3A3C46", piping="#F08A24", free_color="#5E606C",
                    pipe_r=0.022,
                    hand=dict(grip="wrap", curl=0.85, target=(-0.20, -0.36, -0.62), axis=(0.25, 0.4, 1.0),
                              radius=0.03, elbow=(-0.40, -0.45, -1.75), sleeve="#3A3C46", detail="gauntlet"))],
        pose=dict(body=28, head=12, roll=-5, nod=5),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="platinum ponytail hook", zone="top back"),
    ),
    # ---------------------------------------------------------------- Hawk (epic): §7.6
    "cmd_hawk": dict(
        name="Hawk", rarity="epic", female=False,
        head=dict(shape="round", wh=0.90, h_px=270, eye_line=0.48, cheeks=1.15),
        skin=SKIN["T3"], skin_tone="T3", blush=0.22, skin_sat=1.14,             # lit cheek S >= 0.35
        paint=[dict(at=(-0.20, -0.36), r=0.022, color="#B86A48", k=0.5)],        # the dimple by the near corner
        eyes=dict(sclera=0.20, open=0.75, iris="#9A6A2E", tilt=0.04, arch=0.22,
                  smile=dict(open=0.62, low=0.20, bow=0.3, arch=0.26, wink="near")),
        brows=dict(shape="arc", thick=0.078, color="#3A2414", arch=0.025, lift=(0.05, 0.0), len=1.2, len_far=1.7,
                   in_far=0.84),
        nose=dict(type="button", k=1.1, drop=0.20, tip="#E0906A", tip_k=0.35),
        mouth=dict(lip="#B8645A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.04, far=0.005),
                   smile=dict(type="open", w=0.34, h=0.13, near=0.05, far=0.035, dz=-0.012)),
        hair=dict(style="quiff", color="#4A3424", dark="#3A2818", light="#6A4C34", crevice="#24160C"),
        beard=dict(style="thin", color="#3A2414", tip="#3A2414", root="#2E1C10", crevice="#1E120A", thick=0.04,
                   curl=0.02),
        # the ear flaps hang down over the ears (a flying cap's; turned up and out they read as horns, P2 sheet)
        headgear=dict(kind="aviator", color="#7A5133", fur="#EDE3D0", fur_detail="fur", flaps=dict(down=True),
                      extra=[dict(kind="goggles", style="aviator", lens=0.15, rim=0.028, el=48, spread=17, tilt=0.6,
                                  depth=0.055, rim_color="#E0AD45", lens_color="#6FA8DC", strap="#5A3A24",
                                  detail="cap_goggles", min_px=200)]),
        body=dict(shoulders=2.05),
        costume=dict(
            base=dict(color="#5A3A24", rough=0.5, sheen=0.1),
            layers=[
                dict(kind="fur", id="fur", color="#EDE3D0", dark="#C8BCA6", light="#FFFAF0", crevice="#9A8C76",
                     r=0.60, r_in=0.22, t=0.10, front_z=-0.98, side_z=-0.88, back_z=-0.80, open=0.12,
                     clumps=dict(n=36, len=0.13, w=0.085, th=0.05), detail="fur", min_px=2500, smooth=4),
            ]),
        # the scarf end flutters back over the far shoulder, thinner, with a fold (straight out sideways it read as a
        # sausage, P2 sheet)
        props=[dict(kind="scarf", style="back", len=0.9, w=(0.07, 0.12), thick=0.012, out=0.75, back=0.32, lift=0.30,
                    detail="scarf"),
               dict(kind="badge_relief", style="wings", at=(-0.24, -1.02), size=0.24, color="#E8B23A", hex="#6FA8DC",
                    detail="wings")],
        pose=dict(body=22, head=10, roll=7, nod=3),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="round cap with flaps + scarf to the right", zone="hat line; far side"),
    ),
    # ---------------------------------------------------------------- Vance (epic): §7.6
    "cmd_vance": dict(
        name="Vance", rarity="epic", female=True,
        # hand-free (§7.15 q3, P2 review): the pinch hand read as a pale lump at 512 and 128 (no fingers show in a
        # pinch seen from her near side; smaller and rolled it read as a stick) — the queen hangs as a pendant on the
        # jabot (§7.6 "без кисти — кулоном на жабо"); KIT_HANDS=1 still builds the hand for the comparison
        hands=False,
        head=dict(shape="oval", wh=0.78, h_px=266, eye_line=0.47, cheeks=0.95, chin=0.005),
        skin=SKIN["T1"], skin_tone="T1", blush=0.2, skin_sat=1.32,
        eyes=dict(sclera=0.20, open=[0.62, 0.59], iris="#8A7AB8", iris_shade=0.9, tilt=0.06, arch=0.2, flick=0.07,
                  shadow="#D9A0A8", smile=dict(open=[0.60, 0.57], low=0.11, bow=0.25, arch=0.24)),
        brows=dict(shape="arc", thick=0.06, color="#5A5664", arch=0.045, lift=(0.0, 0.03), len=1.25, len_far=1.85,
                   in_far=0.84),
        nose=dict(type="straight", w=0.042, drop=0.19, k=0.9, tip="#F0A090", tip_k=0.3),
        mouth=dict(lip="#B85A6A", line=0.19,
                   calm=dict(type="closed", w=0.27, near=0.03, far=0.01),
                   smile=dict(type="open", w=0.31, h=0.11, near=0.045, far=0.035, dz=-0.01)),
        age=dict(nasolabial=True, k=0.22, smile_k=0.32),
        # silver-lilac, more lilac than #D9D6E2 (it rendered a neutral light grey: hair-skin dE 23, P-A5 needs 30; and
        # beside Irma's platinum and Rai's white the P-A9 colour groups read as one)
        # the bun 0.31 H (§7.6 0.28 H): with the queen as a pendant (hand-free) the bun alone is her 48 px signature
        # and measured 6.9 % of the head zone at 0.28 (P-A3 needs 8 %)
        hair=dict(style="bun", color="#B49CEC", dark="#8872C4", light="#DCCCFF", crevice="#4C4088",
                  bun=dict(h=0.31, r=(0.13, 0.092), turns=3.0, w=0.05)),
        body=dict(shoulders=1.75, neck=0.42),
        costume=dict(
            # the violet a step darker (§7.4 on the purple plate: L* <= 35 or >= 65 — the #8E5BD0 lapels sat at
            # L* 56 on the epic plate, band dL* 12.7)
            base=dict(color="#3A2262", rough=0.8, sheen=0.4),
            layers=[
                dict(kind="collar", color="#40266A", z=-0.64, h=0.07, out=0.014, flare=0.012, gap=0.08),
                dict(kind="lapels", color="#5E3A9E",
                     shape=[(0.08, -0.66), (0.24, -0.70), (0.33, -0.78), (0.28, -0.84), (0.20, -0.98), (0.04, -1.14)]),
                dict(kind="jabot", color="#F4F2F6", top=-0.66, tiers=3, r=0.12),
            ]),
        props=[dict(kind="brooch", at=(0.0, -0.69), d=0.10),
               dict(kind="queen", h=0.30, color="#5A3A26", pendant_at=(0.0, -0.88), pendant_k=0.85,
                    offset=(-0.26, -0.20, -0.22),
                    hand=dict(grip="pinch", elbow=(-0.30, -0.45, -1.75), sleeve="#40266A", cuff="#F4F2F6", size=0.68,
                              roll=70)),
               dict(kind="hairpin", t=0.35)],
        pose=dict(body=26, head=6, roll=4, nod=5),
        pose_smile=dict(roll=-3, nod=3),
        signature=dict(name="tall vertical bun + queen at the chin", zone="top centre; chin"),
    ),
    # ---------------------------------------------------------------- Rai (legendary): §7.6
    "cmd_rai": dict(
        name="Rai", rarity="legendary", female=False,
        head=dict(shape="long", wh=0.82, h_px=274, eye_line=0.46, cheeks=1.0),
        skin="#BE8256", skin_tone="T4", blush=0.15,
        # a light raivite iris (#88C6FF, the #5AA8FF hue lightened; full lift): P-A8 wants it at L* 70-85
        # (#5AA8FF at lift 0.45 measured 61, 0.85 64.5; #6CB4FF at 1.0 67.9; #7EC0FF 69.9); that cannot also keep §7.4's iris-sclera dL* >= 30 (the
        # sclera renders at L* ~71) — reported as a spec conflict
        eyes=dict(sclera=0.19, open=0.70, iris="#88C6FF", iris_shade=1.0, glow=0.6, iris_lift=1.0, tilt=0.0, arch=0.18,
                  smile=dict(open=0.60, low=0.18, bow=0.25, arch=0.22)),
        brows=dict(shape="arc", thick=0.06, color="#E8EAF0", arch=0.02, outer=-0.03, len=1.35),
        nose=dict(type="aquiline", len=0.24, w=0.058, proj=0.075, hump=0.012, drop=0.22, tip="#C87A58", tip_k=0.3),
        mouth=dict(lip="#A86050", line=0.20,
                   calm=dict(type="closed", w=0.26, near=0.012, far=0.008),
                   smile=dict(type="open", w=0.30, h=0.09, near=0.035, far=0.03, dz=-0.008)),
        hair=dict(style="long", color="#EEF0F5", dark="#C4CCDC", light="#FFFFFF", crevice="#7E8CA8",
                  res=0.0135),      # a coarser hair mass: 515k triangles at 0.011 (P-A10 <= 500k)
        beard=dict(style="long", color="#EEF0F5", tip="#FFFFFF", root="#C8D0E0", crevice="#6E7EA0", below=0.6,
                   moustache=True, moustache_color="#E4E8F0", moustache_dark="#B8C2D4", moustache_light="#F6F8FC",
                   moustache_k=0.85),
        age=dict(forehead=2, crows=2, nasolabial=False, k=0.3),
        headgear=dict(kind="circlet", color="#C8CCD4", w=0.06, el=(34, 14), stone=0.12, emit=1.6),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#EEF1F6", rough=0.85, sheen=0.3),
            layers=[
                # matte, a step deeper (#173C86, sheen 0.1, low specular) and darker at the top (shade): the sheen,
                # the key and the rim's grazing highlight lit the shoulder tops to L* 72-81 beside the white beard
                # (beard vs clothes dL* 2.1, §7.4 needs 15)
                dict(kind="cloak", id="cloak", color="#173C86", rough=0.92, sheen=0.1, spec=0.15, shade=(0.84, 0.88),
                     z1=-0.64,
                     gap=0.03, flare=0.06, open=[(-1.9, 0.46), (-1.2, 0.42), (-0.85, 0.36), (-0.66, 0.30)]),
                dict(kind="cape_collar", color="#1E4FA8", z0=-0.72, top_z=0.02, r0=0.30, r1=0.58, open=58,
                     piping="#C8CCD4", detail="collar", min_px=4000),
                # wide enough that the beard lies on the stole, not the cloak's lit shoulders (§7.6 "борода лежит на
                # синем палантине")
                dict(kind="bib", id="stole", color="#2B5FD9", w=0.36, top=-0.665, bottom=-2.0, straps=False,
                     over_last=False),
            ]),
        props=[dict(kind="banner", x=0.50, y=0.32, top=0.80, w=0.40, h=0.60)],
        pose=dict(body=18, head=4, roll=0, nod=2),
        pose_smile=dict(roll=-3, nod=2),
        signature=dict(name="stand cape collar + banner over the far shoulder", zone="head frame; far side"),
    ),
}

KIT_IDS = set(CHARS)
KIT_ERAS = {cid: {1} for cid in CHARS}      # eras the kit builds; the rest falls back to the old builder

# headgear per era for the uniqueness lint (§7.6: «Головные уборы в одной эпохе не повторяются»): a headgear's id
# (the builder kind unless it says otherwise: Olm's brass goggles and Irma's motor goggles share the goggles builder)
HEADGEAR = {cid: {1: (c.get("headgear") or {}).get("id", (c.get("headgear") or {}).get("kind"))}
            for cid, c in CHARS.items()}


def lint():
    """Fail the build when an id has no signature or no signature zone, two ids share a signature, or two commanders
    share a headgear in one era (runs at every build, portrait_kit.build)."""
    errs = []
    seen = {}
    for cid, c in CHARS.items():
        s = c.get("signature", {}).get("name")
        if not c.get("signature", {}).get("zone"):
            errs.append("%s has no signature zone" % cid)
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
