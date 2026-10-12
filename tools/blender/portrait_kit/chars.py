"""Characters as data (§7.5 "Персонаж — только данные"): the face table, signature, moods, palette, costume and pose of
each portrait of docs/art_direction.md §7.6, plus the signature registry and its lint (no two ids share a
signature; no two commanders wear the same headgear in one era).

P1 (the kit proof): Bram, Lira and Vega in era 1, calm and smile. P2: all twelve commanders in era 1 (eras 2–4,
the leaders and the ruler keep the old builder in portrait_assets.py until P3 adds them here). A prop with a "hand"
pose (§7.5: Vega's pointer, Seir's spyglass, Vance's queen, Irma's gauntlet) builds the hand when the character's
"hands" is on (default) and its hand-free fallback otherwise (KIT_HANDS=0 / 1 forces either, for the review of §7.15
q3). Vega's is off (decided after P1: she carries no pointer), Vance's and Irma's too (the P2 reviewer's decision: the
queen pendant; one gauntlet tucked under the chest strap), and Seir's since the P2 fix review (the hand on the
shoulder read as a fist from the back at 512 and an orange lump at 128; the spyglass on its strap behind the back,
the eyepiece over the near shoulder, reads cleaner); their hands are built only under KIT_HANDS=1.

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
        # boost a little higher than T2's 1.15 so the lit cheek keeps HSV S >= 0.27 (§7.4, peach-pink)
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
        # a closer crop (a thin cap, flatter locks): the crown visibly narrower than the pear beard at 48 px (P-A2: the
        # thick dome was as wide as the beard, so his "pear" read as a plain bust)
        # (the thinner crop is less self-shadowed: a hair darker than #B5562B and the locks lifted a little more for AO
        # between them, so hair vs skin keeps >= 15 L* in the laugh)
        # (the thinner cap is lit more evenly: a step darker again, #9A4420, so hair vs skin keeps >= 15 L* in the
        # laugh — 13.4 at #A84C24)
        hair=dict(style="swept", color="#9A4420", dark="#521C0A", light="#A84C26", crevice="#3E1408",
                  sideburns=True, sheet=(0.016, 0.010), lock_th=0.034, lock_lift=0.36),
        # the beard #C8652F (§7.6) shaded hair-like but the other way up: lit lobe tips #E08A50 on the slate jerkin
        # (dL* >= 15), roots #8E3E1C and a #74301A band along the cheek (beard vs skin >= 15, also at the boundary:
        # art director note 1); a soft #8A3C1C crevice tone between the strand groups; the moustache in a darker
        # rust, so it reads as hair over the lip, not a fleshy upper lip
        beard=dict(style="pear", color="#C8652F", tip="#E08A50", root="#8E3E1C", edge="#74301A", crevice="#8A3C1C",
                   # 0.18 W past the jaw each side (§7.6 0.12 W), widest at the chin and full over its upper half:
                   # at 0.12 the pear only widened over the chest, where the shoulders hide it in the 48 px
                   # silhouette (P-A2; 0.20-0.22 pushed the laugh's dark pixels past §7.4's 3 %)
                   # (P2 review: still read as a plain bell at 48 px, named as Kort — wider again, 0.24 W, its widest
                   # row a little under the chin and full down to the middle, 0.50 H deep: round convex lobes that
                   # bulge past the face's outline; the hair cap thinner, so the crown is clearly the narrow end)
                   wider=0.24, below=0.50, widest=-0.05,
                   profile=[(-1.0, 0.70), (0.0, 1.0), (0.3, 1.0), (0.6, 0.86), (0.85, 0.62), (1.0, 0.46)],
                   moustache=True, moustache_color="#A04A22", moustache_dark="#76301A", moustache_light="#B5562B"),
        scar=dict(near=True, **{"from": (-0.34, 0.01), "to": (-0.23, -0.14)}),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#DCCAA0", rough=0.85, sheen=0.25),
            layers=[
                # a laced jerkin closed under the beard (the beard lies on slate: dL* >= 15, §7.4; #3F4D5E two steps
                # darker, #394552: the smile measured 14.7-14.8 at #3B4859 under the wider pear); no shirt collar —
                # the beard covers the neck
                # (shade 0.94 -> 0.92 down the jerkin, not 0.80 / 0.87: under the beard's shadow the bottom went past the
                # albedo floor — dark pixels, §7.4)
                # (#3D4A58 with the larger pear: its shadow on the jerkin pushed the laugh's dark pixels to 3.1 %)
                dict(kind="vest", id="jerkin", color="#3D4A58", z0=-1.32, z1=-0.645, thick=0.032, rough=0.9, sheen=0.4,
                     shade=(0.94, 0.92),
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
        hair=dict(style="bob", color="#463E40", dark="#3E3638", light="#605658", crevice="#3C3742", near_len=0.10,
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
        signature=dict(name="chisel bob + glasses bar", zone="head width; top"),   # no pointer since P1
    ),
    # ---------------------------------------------------------------- Kort (rare): §7.6
    "cmd_kort": dict(
        name="Kort", rarity="rare", female=False,
        # "массивный квадрат 1.0, 284 (самая крупная), брыли, большие уши"; eye line 0.50 (§7.3: Kort)
        head=dict(shape="square", wh=1.0, h_px=284, eye_line=0.50, jowls=1.0, cheeks=1.2, muzzle=1.1, brow_ridge=1.3,
                  jaw=0.02),
        ear_k=1.4,          # "большие уши" (§7.6): the near ear a clear side bump on the bald dome (48 px)
        # "T2 румяный" as a deeper rosy pink (#D88878): the white brows measured only 12.6 L* over the skin at #F2A07E
        # (§7.4: white brows >= 18 L* lighter than the skin); the pink hue (<= 16 deg) keeps it from going pumpkin
        # orange as it darkens (and takes §7.4's S floor 0.27 for peach-pink skin)
        # a weathered ruddy rose, a step less saturated and less orange (P2 review: at #D88878 x1.32 the head read as a
        # tomato beside Olm and Bram — skin S 0.58, hue 15 deg): #C87C72 x1.26, value 0.95 (skin S 0.50, hue 10 deg).
        # Darker rather than paler: the white brows and moustache need the skin >= 18 L* under them (§7.4; paler
        # tries measured 9-16). A matte skin (specular 0.08): the rim light's sheen on the bald dome is what §7.4's
        # lit-cheek sample (the brightest 30 % of the skin) caught, and it greyed it under the 0.27 floor (0.22 at the
        # default 0.35)
        # (P2 fix sheet: still tomato-red beside Bram and Olm at hue 11 deg, S 0.55 — a weathered rose-beige #C88878
        # under the set's lower chroma, art director note h: x1.36 x k 0.94, value 0.92 renders hue 15 deg, median C*
        # 34 (-17 %), the lit cheek S 0.28 (peach-pink floor 0.27) and the white brows 20 L* over the skin)
        skin="#C88878", skin_tone="T2", blush=0.28, skin_sat=1.36, skin_value=0.92, skin_spec=0.08,
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
        # the white tufts low and close behind the ears, small puffs pointing out and a little down, over a horseshoe
        # band round the back (raised up and out they read as hood points or horns at 48 px and fed the P-A2
        # confusion with Vik and Bram)
        hair=dict(style="tufts", bald=True, color="#FCFCFF", dark="#EEEEF4", light="#FFFFFF", crevice="#C4C8D6",
                  tufts=dict(band_az=96, band_lo=-26, band_hi=20, out=0.06, up=-0.06,
                             fans=[(104, -6, 1.0, 0.065, 4), (124, -10, 0.9, 0.06, 3)])),
        # the walrus moustache, white #EDEDF2, hanging 0.25 H below the mouth (§7.6), its ends pushed out past the jaw
        # (1.1 W, not 0.85: the ends must break the face's outline so his shape is wide and low at 48 px — P-A2)
        # (1.22 W, 0.32 H: the P2 review still read his outline as a plain dome — the ends now sweep out past the
        # cheeks like tusks over the collar)
        beard=dict(style="walrus", color="#EDEDF2", tip="#FFFFFF", root="#D4D6DE", crevice="#7E8496", w=1.22,
                   drop=0.32, smile_lift=0.04),
        age=dict(forehead=2, crows=3, nasolabial=False, k=0.45, smile_k=0.55),   # §7.3: 2 forehead folds
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
                # karakul in ribbons (§7.6): flat C-shaped curl ribbons half sunk into the sheet, AO in the grooves
                # between them (round clumps on a thick roll read as chocolate mousse, P2 review); wider over the
                # shoulders and puffed up round the neck to the moustache (his "shoulder width" zone: wide and low
                # at 48 px, P-A2)
                dict(kind="fur", id="fur", color="#7C5E4A", dark="#765A48", light="#9C7A62", crevice="#665040",
                     r=0.92, r_in=0.27, t=0.12, front_z=-1.05, side_z=-0.96, back_z=-0.86, open=0.10,
                     clumps=dict(n=95, len=0.13, w=0.034, th=0.024, curl=0.5, sink=0.88, rise=0.0, balls=7, tip=0.45),
                     detail="fur", min_px=8000, signature=True, smooth=2, res=0.011),
                dict(kind="clasp", color="#B0803A", z=-0.90, x=0.075),
            ]),
        # amber sand (§7.6 "янтарный песок"), a clearer glass: through the 0.35 glass the sand read white (P2 review)
        props=[dict(kind="hourglass", at=(-0.23, -0.93), h=0.22, button="button_0", sag=0.02, sand="#D8801C",
                    glass_alpha=0.08, glass_coat=0.0, glass_spec=0.2)],
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
        age=dict(forehead=2, crows=3, nasolabial=True, k=0.4, smile_k=0.5),      # §7.3: 2 forehead folds
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
        # (deeper in the pocket and leaning a little further out: the jaws sat at mouth height hugging the far face
        # contour, a tangent — §7.11; now beside the far side of the neck over the shoulder line, §7.6)
        # (dark iron, era 1 "ключ железный": the light steel melted into the grey plate where the jaws now stand clear
        # of the face on the silhouette's edge, P-A5 rim 38 %)
        props=[dict(kind="wrench", pocket="pocket", len=0.70, jaw=0.22, ang=13, color="#6C7482", signature=False,
                    depth=0.36, inset=0.010, dy=0.04, top_dy=0.10),
               dict(kind="pencil", color="#C9A24A")],
        pose=dict(body=24, head=10, roll=-4, nod=3),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="brass goggles on a bald dome + fluffy sides", zone="double bump on top"),
    ),
    # ---------------------------------------------------------------- Vik (common): §7.6
    "cmd_vik": dict(
        name="Vik", rarity="common", female=False,
        head=dict(shape="long", wh=0.80, h_px=264, eye_line=0.46, cheeks=1.0),
        # (value 0.81, a tanned ranger: with the set's lower skin chroma, art director note h, the straw no longer
        # separates from the face by colour — it does by value, hair vs skin |dL*| >= 15, §7.4)
        skin="#F2A276", skin_tone="T2", blush=0.30, skin_value=0.81,
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
        # straw (§7.6 #EBD27A) as a mid-tone with light tips and dark crevices between the clumps: eight tapered
        # wisps from under the hood onto the brows (a flat pale cream #FFF6CC, chosen for hair-skin dE, rendered them
        # as white pebbles, P2 review). Narrower wisps at alternating lifts, so they lie in two layers with dark gaps
        # between them (wide, even ones fused into one cream band), a deep crevice tone and darker roots under the
        # hood; the lit straw stays light (#FFEFA6): hair vs skin dE76 >= 30 (§7.4) — a mid-tone straw (#F2D672,
        # #F8E28E) measured 23-27 on his tanned T2
        # (P2 fix sheet: the pale cream wisps read as icing — the straw warmer and a step deeper, the lit tips
        # #F8E296, the roots and crevices darker so the clumps part; the set's less saturated skin keeps dE76 >= 30)
        hair=dict(style="fringe", color="#FFF3B2", dark="#C8984A", light="#FFF7C4", crevice="#4A3010", rim_el=50,
                  wisps=[(-44, 0.08, 18, 0.06, 0.014), (-31, 0.085, 24, 0.0, 0.036), (-17, 0.085, 28, 0.03, 0.016),
                         (-4, 0.09, 30, -0.01, 0.040), (9, 0.085, 30, 0.04, 0.018), (22, 0.08, 28, 0.05, 0.038),
                         (34, 0.07, 22, 0.11, 0.016), (44, 0.065, 16, 0.14, 0.030)]),
        # the soft peak stands >= 0.25 H clear of the hood (§7.6), up and back: it leaves the dome high on its near
        # back (az -138) and points up at 46 deg toward the picture's left (az -124 is side-on to the level 3/4
        # camera: aimed straight back, az -160, it was foreshortened behind the dome and stood only 15-40 px clear —
        # a small cat ear, P2 review); a fat base and a long taper, since a metaball chain's thin end shrinks inside
        # its nominal radius. #4E6B3A a hair lighter: dark budget
        # (the front edge a little higher than the kit's default, so the fringe has a forehead to fall over)
        # (the hood a step darker than the cloak, #3E6234: the larger peak is most of his signature mask, and at
        # #527040 its lit green sat dE76 22.9 from the grey common plate, §7.4 needs 25)
        # (shade_low 1.06: the drape's shadow under the chin put the laugh at 3.03 % dark pixels with the tanned skin)
        headgear=dict(kind="hood", color="#3E6234", thick=0.075, peak=0.42, peak_r=0.16, edge_r=0.05, shade_low=1.06,
                      peak_at=(-138, 54), peak_dir=(-124, 46), droop=0.11,
                      edge=[(0, 53), (40, 46), (62, 24), (76, -10), (88, -60), (180, -90)]),
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
        # the raven in profile, beak out to the left (a bird's eye looks at you from the side of its head: its near
        # eye and catchlight face the camera), out on the shoulder and leaning away from the hood — a notch of
        # background between bird and hood at 48 px (P-A2: pressed against the hood it merged into one slope)
        # (rolled 16 deg out: its head and back lean off the hood's slope, a notch of background between them; 20
        # pushed it into the frame's side band)
        props=[dict(kind="raven", x=-0.70, y=0.10, size=0.55, turn=-55, roll=16),
               dict(kind="bow", x0=0.66, y=0.26, z0=-0.86, len=0.6, lean=10)],
        pose=dict(body=18, head=14, roll=-6, nod=2),
        pose_smile=dict(roll=-4, nod=2),
        signature=dict(name="raven on the near shoulder + hood peak back", zone="near shoulder; top back"),
    ),
    # ---------------------------------------------------------------- Seir (rare): §7.6
    "cmd_seir": dict(
        name="Seir", rarity="rare", female=False,
        # hand-free (§7.15 q3, the P2 fix review): the spyglass on its strap behind the back, its eyepiece over the
        # near shoulder behind the ear (§7.6 "без кисти — на ремне за спиной, окуляр над плечом"); the held pose
        # (KIT_HANDS=1) read as a fist seen from the back at 512 and an orange lump at 128
        hands=False,
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
        # 0.06 H along the jaw as built (the sheet thinner than the norm and the clumps riding in it: the metaball
        # union had swollen it to ~0.2 H, P2 review)
        beard=dict(style="short", color="#B8B8C0", tip="#C6C6CC", root="#A0A0AA", crevice="#62626E", thick=0.036,
                   under=0.03, clump_lift=0.1, clump_th=0.55,
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
        # held (KIT_HANDS=1 only since the P2 fix review): the near hand on the near shoulder by the collar, the tube
        # rising up and back at 58 deg (world) so it passes behind the ear and the back hair and its eyepiece ends
        # under the tricorn's near corner — "за головой". Drawn out to 0.95 H (a telescope's sections extended): at
        # §7.6's 0.8 H the eyepiece stops at ear level whatever the angle, and aimed out to the left at 48 deg (the
        # interrupted fix) it stood clear of the head instead of behind it (P2 review: 72 deg beside the head)
        props=[dict(kind="spyglass", len=0.8, len_hand=0.95, d=0.11, ang=50, dir_world=(-0.8, 0.6, 0.0),
                    rest=(-0.48, None), dir_world_hand=(-0.8, 0.6, 0.0), ang_hand=58, rest_hand=(-0.42, None),
                    rest_y=0.06, below=0.30, strap_from=(-0.42, -0.70), strap_to=(0.55, -1.6), grip_t=0.12,
                    below_hand=0.18,
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
        # lit cheek S >= 0.35 (§7.4): a matter skin (roughness 0.62, specular 0.22) and x1.22 — the flat-top bares
        # the temples and forehead, and the key's sheen on them greyed the brightest skin pixels to S 0.33 (more
        # saturation alone did not lift them)
        skin=SKIN["T5"], skin_tone="T5", blush=0.2, skin_sat=1.10, skin_rough=0.62, skin_spec=0.22,
        eyes=dict(sclera=0.19, open=0.72, iris="#8A5A2E", tilt=0.0, arch=0.18, flick=0.028,
                  smile=dict(open=0.62, low=0.20, bow=0.3, arch=0.24)),
        brows=dict(shape="straight", thick=0.075, color="#342822", arch=0.01, len=1.25, inner=-0.01, gap=0.04,
                   smile=dict(lift=(0.015, 0.01))),
        brow_scar=dict(x=0.12, color="#C88A6A", w=0.025),
        nose=dict(type="straight", w=0.07, drop=0.21, k=1.05, tip="#A8603E", tip_k=0.3),
        mouth=dict(lip="#A0524A", line=0.20,
                   calm=dict(type="closed", w=0.28, near=0.01, far=0.0),
                   smile=dict(type="open", w=0.30, h=0.10, near=0.035, far=0.025, dz=-0.01)),
        # a flat-top (§7.6 "площадка"): a block with a level top and vertical walls on the parietal ridge, faded sides
        # with skin at the temples and over the ears, a bristle edge of short spikes along the hairline (P2 review: the
        # planed metaball shell read as a fleece cap, the noise bristle as stucco). A warm mid-brown, not §7.6's
        # #2A2420 (the art director's P2 note b: hair lighter than the uniform; a dark shell read as a beanie) nor the
        # grey-beige #A8907A (read grey-haired): darker crevices low, lighter tips on top; its value keeps hair vs the
        # T5 skin >= 15 L* (§7.4)
        hair=dict(style="flattop", color="#3A2A20", dark="#3C2C21", light="#4C382A", crevice="#3E2E22",
                  tip="#624A38", fleck="#4E3A2C", side=0.008, front=0.035, front_ramp=0.09, top=0.022,
                  corner=0.13, ridge=0.16, ramp=0.12, lean=(35.0, 22.0), stubble=0.35, grain=(150, 150, 34),
                  fade_band=0.05, fade_mix=0.5, bristles_front=(0.0, 0.0, 0, 0.0, 0.0),
                  rough=0.78, spec=0.3,
                  # the corners recede at the temples (a straight line across the forehead read as a cap's rim)
                  hairline=[(0, 0.31), (16, 0.315), (30, 0.29), (42, 0.265), (56, 0.25), (72, 0.21), (92, 0.14),
                            (130, -0.03), (180, -0.18)]),
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
        # hand-free (§7.15 q3, decided by the P2 reviewer: the gloved hand at the collar read as a claw at the
        # throat): one gauntlet tucked under the chest strap; KIT_HANDS=1 still builds the hand
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
                # the orange accent from piped edges (§7.6 "оранжевый кант"), not a bare slab: the riding jacket's
                # closure edge piped in orange from the collar down (the flat orange placket existed only to pass
                # P-A8's orange share, P2 review)
                dict(kind="piping", color="#F08A24", r=0.021,
                     path=[(0.07, -0.70), (0.09, -0.92), (0.10, -1.2), (0.10, -1.75)]),
                dict(kind="strap", id="strap", color="#2E2E34", **{"from": (-0.40, -0.72), "to": (0.45, -1.6)},
                     w=0.075),
            ]),
        # (a shorter cuff with a stronger flare, the glove pushed under the strap with only short finger tips
        # peeking out below it: the 0.30 H straight cuff with the glove hanging below it read as a forearm and a hand
        # on her chest, P2 review; folded palm up toward the camera it read as an open hand)
        props=[dict(kind="gauntlet", on="strap", color="#3A3C46", piping="#F08A24", free_color="#5E606C",
                    pipe_r=0.024, tuck_z=-0.93, lean=16, scale=1.0, cuff=0.22, flare=0.13, fold=12, curl=0.0,
                    palm=0.0, palm_k=0.5, fingers=0.42, thumb=False,
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
        # (the laugh's near brow 1.12x longer: over the winking eye it measured 5.2 px long at 64 px, P-A3 needs 6;
        # longer in the calm too, it covered the lit forehead under the quiff, leaving only a shaded sliver of skin
        # at the hair's edge)
        brows=dict(shape="arc", thick=0.078, color="#3A2414", arch=0.025, lift=(0.05, 0.0), len=1.2, len_far=1.7,
                   in_far=0.84, smile=dict(len_near=1.12)),
        nose=dict(type="button", k=1.1, drop=0.20, tip="#E0906A", tip_k=0.35),
        mouth=dict(lip="#B8645A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.04, far=0.005),
                   smile=dict(type="open", w=0.34, h=0.13, near=0.05, far=0.035, dz=-0.012)),
        # the darks a step over the albedo floor (#3A2818 / #24160C went under L* 17 in the quiff's shade: §7.4 budget)
        hair=dict(style="quiff", color="#4A3424", dark="#42301F", light="#6A4C34", crevice="#3A2818"),
        beard=dict(style="thin", color="#3A2414", tip="#3A2414", root="#2E1C10", crevice="#1E120A", thick=0.04,
                   curl=0.02),
        # the ear flaps hang down over the ears (a flying cap's; turned up and out they read as horns, P2 sheet)
        # (the flaps longer and splayed out a little at the bottom: hanging flat against the head they hardly showed,
        # P2 review)
        headgear=dict(kind="aviator", color="#7A5133", fur="#EDE3D0", fur_detail="fur",
                      flaps=dict(down=True, len=0.32, w=0.21, splay=0.38),
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
        # the scarf end wider (0.13 H at its tip, the fold kept): at 0.06 H it read as a thin ribbon (P2 review; §7.6
        # 0.9 x 0.18 H)
        # (P2 fix sheet, art director note i: at out 0.75 the end still stuck out sideways — now it crosses the fur
        # over the far shoulder and falls back behind it, its end dropping past the shoulder line)
        props=[dict(kind="scarf", style="back", len=0.9, w=(0.09, 0.17), thick=0.012, out=0.56, back=0.45, lift=0.20,
                    end_up=-0.42, droop=0.0, cross=0.75, drop_from=0.40, fold=140, detail="scarf"),
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
        signature=dict(name="tall vertical bun + queen pendant on the jabot", zone="top centre; chest"),
    ),
    # ---------------------------------------------------------------- Rai (legendary): §7.6
    "cmd_rai": dict(
        name="Rai", rarity="legendary", female=False,
        head=dict(shape="long", wh=0.82, h_px=274, eye_line=0.46, cheeks=1.0),
        # (value 0.97: the white brows >= 18 L* over the set's less saturated, lighter skin, §7.4; art director note h)
        skin="#BE8256", skin_tone="T4", blush=0.15, skin_value=0.97,
        # a light raivite iris (the #5AA8FF hue lightened, full lift): P-A8 wants it at L* 70-85 (#5AA8FF at lift
        # 0.45 measured 61, 0.85 64.5; #6CB4FF at 1.0 67.9), which cannot also keep §7.4's iris-sclera dL* >= 30 (the
        # sclera renders at L* ~71) — a spec conflict for the main session. A strong dark limbal ring (x0.30 of the
        # iris colour, 1.3x the norm's width, not glowing; P2 review: the pale iris read blank against the white at
        # 64 px) and a saturated #8CD0FF body: L* 70.7, iris-sclera dE76 12.3, pupil-iris dL* 53 (256 px check)
        eyes=dict(sclera=0.19, open=0.70, iris="#8CD0FF", iris_shade=1.0, glow=0.6, iris_lift=1.0, tilt=0.0, arch=0.18,
                  limbal_k=0.30, limbal_w=1.3,
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
                # (the front opening wider, so the beard lies on the stole: the cloak's rim-lit far edge touched it,
                # beard vs clothes dL* 3.7, P2 review)
                # the robe's neckline in the stole's blue (a stand band round the neck): above the stole's top edge a
                # sliver of the white robe showed beside the beard (beard vs costume dL* 4.8). The stole itself cannot
                # start higher: a bib projected above the torso's top stays a flat sheet in front of the chest
                # (P2 fix review: the funnel's top showed as a flat ellipse plate at the neck — a rolled piping in the
                # cape collar's deep blue along its top edge makes it read as a band; an upright band, `stand`, was
                # tried and dropped: narrower at the foot, it bared the cloak's rim-lit shoulder top beside the beard,
                # beard vs clothes dL* 7)
                dict(kind="collar", color="#2252EC", z=-0.68, h=0.11, out=0.0, flare=0.016, piping="#1E4FA8",
                     piping_r=0.016),
                # (the opening a little wider, most at the top: the cloak's edges are now exact arcs, not the outer
                # side of deleted faces, and the rim-lit far shoulder top touched the beard, beard vs clothes dL* 7)
                dict(kind="cloak", id="cloak", color="#173C86", rough=0.92, sheen=0.1, spec=0.15, shade=(0.84, 0.88),
                     z1=-0.64,
                     gap=0.012, flare=0.06, open=[(-1.9, 0.54), (-1.2, 0.52), (-0.85, 0.56), (-0.66, 0.64)]),
                dict(kind="cape_collar", color="#1E4FA8", z0=-0.72, top_z=0.02, r0=0.30, r1=0.58, open=58,
                     piping="#C8CCD4", detail="collar", min_px=4000),
                # the beard lies on the stole (§7.6 "борода лежит на синем палантине"); 0.42 W at its top: wider
                # (0.48), its top corners ran past the torso's shoulders, missed the projection and stood out as flat
                # blades in front of the chest
                # (#2252EC, a step more saturated than #2B5FD9: with more of the stole showing, Rai's clothes median
                # sat dE76 17 from Vance's violet and their P-A9 mean fell to 15.0)
                # (the top corners rounded, `round`, and 0.45 W: the square near corner folded into a pale flat
                # triangle on the shoulder slope, P2 review; at 0.50 and more the corners fold back in and the far one
                # sticks out as a blade)
                dict(kind="bib", id="stole", color="#2252EC", w=0.45, top=-0.665, bottom=-2.0, straps=False,
                     over_last=False, round=0.10),
            ]),
        props=[dict(kind="banner", x=0.50, y=0.32, top=0.80, w=0.40, h=0.60)],
        pose=dict(body=18, head=4, roll=0, nod=2),
        pose_smile=dict(roll=-3, nod=2),
        signature=dict(name="stand cape collar + banner over the far shoulder", zone="head frame; far side"),
    ),
}

# ================================================================== the AI leaders (§7.8) and the ruler (§7.10)
# Same kit, same bar; no commander-locked module (lint). Plates = the state colours the game passes to
# CmdPortrait.plate (tools/qa_portraits/qa_common.LEADER_PLATE); the costume's main colour is chosen by value against
# it (shoulder band >= 15 L* on plate B), the state colour is an accent (sash, lining, stone) >= 10 %. Headgear and
# props stay at y >= 50 of the master (tall_headgear: the framing solver's 50 px skyline). Moods: §7.9 defaults
# (chars._fill_mood) plus each leader's own patch ("moods").
CHARS.update({
    # ---------------------------------------------------------------- Baron Grodek the Fang (Barons, Wolf; war red)
    "ldr_barons": dict(
        name="Grodek", leader=True, female=False, tall_headgear=True, plate="#DD3A30",
        head=dict(shape="square", wh=0.98, h_px=260, eye_line=0.49, jaw=0.07, chin=0.03, cheeks=1.1, muzzle=1.2,
                  brow_ridge=1.5),
        skin=SKIN["T4"], skin_tone="T4", blush=0.18,
        eyes=dict(sclera=0.18, open=0.68, iris="#D0A030", iris_shade=0.9, tilt=-0.12, arch=0.10),
        brows=dict(shape="bushy", thick=0.085, color="#363236", arch=0.01, len=1.3, inner=-0.03, outer=0.02),
        nose=dict(type="aquiline", len=0.22, w=0.085, proj=0.07, hump=0.012, drop=0.21, tip="#B8604A", tip_k=0.4),
        mouth=dict(lip="#9A4A40", line=0.21,
                   calm=dict(type="closed", w=0.30, near=-0.012, far=0.012),
                   smile=dict(type="open", w=0.36, h=0.12, near=0.045, far=0.04, dz=-0.012, lower_teeth=True,
                              lower_share=0.22, teeth=0.32)),
        hair=dict(style="mane", res=0.015, color="#524E56", dark="#48444C", light="#6E6872", crevice="#423E46",
                  temples="#A8A8B0"),
        beard=dict(style="forked", color="#524E56", tip="#6E6872", root="#48444C", crevice="#423E46", below=0.48,
                   moustache=True, moustache_color="#403C40", moustache_dark="#363236", moustache_light="#5E585E",
                   signature=True),
        body=dict(shoulders=2.05),
        costume=dict(
            base=dict(color="#C8D0DA", rough=0.5, sheen=0.1),
            layers=[
                dict(kind="vest", id="cuirass", color="#C8D0DA", plate=True, metallic=0.30, rough=0.35, z0=-1.35,
                     z1=-0.70, thick=0.035),
                dict(kind="piping", color="#F08A24", r=0.02, path=[(-0.42, -0.74), (-0.2, -0.80), (0.0, -0.82),
                                                                   (0.2, -0.80), (0.42, -0.74)]),
                dict(kind="fur", id="pelt", res=0.016, color="#847A74", dark="#786E68", light="#A09690", crevice="#5E5652",
                     r=0.95, r_in=0.30, t=0.11, front_z=-1.0, side_z=-0.95, back_z=-0.85, open=0.16,
                     clumps=dict(n=70, len=0.14, w=0.05, th=0.03, curl=0.2), smooth=3),
            ]),
        props=[dict(kind="wolf_head", x=-0.48, y=0.12, size=0.70, lift=0.30, turn=25, color="#8E8882", dark="#6A6460",
                    light="#C8C2BC", min_px=2500),
               dict(kind="fang", side="near", len=0.07, r=0.022),
               dict(kind="pendant", at=(0.02, -1.02))],
        pose=dict(body=20, head=8, roll=-6, nod=-3),
        signature=dict(name="wolf head pelt + forked beard + fang", zone="near shoulder; lower face width"),
        moods=dict(
            smile=dict(eyes=dict(smile=dict(open=[0.64, 0.64], low=0.12))),
            # the calm frame is kept (§7.9): a -5/-6 deg nod put the heavy jaw past P-A6 (chin 387 / 394 > 381),
            # so his nod is smaller and the slump is carried by the roll
            angry=dict(pose_angry=dict(nod=-2.0), brows=dict(angry=dict(inner=-0.075, outer=0.025, in_dx=0.02, thick_k=1.15)),
                       mouth=dict(angry=dict(type="open", shape="trap", w=0.30, h=0.11, near=-0.02, far=-0.02,
                                             lower_teeth=True, fangs=True, dz=-0.008))),
            cunning=dict(eyes=dict(cunning=dict(open=[0.22, 0.66], tilt=-0.05, arch=0.08, low=0.06)),
                         mouth=dict(cunning=dict(type="closed", w=0.30, near=0.045, far=-0.005, sag=0.004))),
            tired=dict(pose_tired=dict(nod=-1.5, roll=-5.0)),
        ),
    ),
    # ---------------------------------------------------------------- Headwoman Mirosya Goldmouth (Hamlets, Fox)
    "ldr_hamlets": dict(
        name="Mirosya", leader=True, female=True, tall_headgear=True, plate="#4FD162",
        head=dict(shape="round", wh=0.96, h_px=262, eye_line=0.47, cheeks=1.45, muzzle=1.0, chin=0.0),
        skin=SKIN["T2"], skin_tone="T2", blush=0.34, skin_value=1.12,
        paint=[dict(at=(-0.24, -0.15), r=0.02, color="#C8705A", k=0.5), dict(at=(0.24, -0.15), r=0.02,
                                                                            color="#C8705A", k=0.5)],
        eyes=dict(sclera=0.21, open=0.78, iris="#9A6A2A", tilt=0.04, arch=0.26, flick=0.06),
        brows=dict(shape="arc", thick=0.058, color="#6A3418", arch=0.035, len=1.2, len_far=1.5, in_far=0.84),
        nose=dict(type="button", k=1.0, drop=0.19, tip="#E88A70", tip_k=0.5),
        mouth=dict(lip="#C8605A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.025, far=0.02),
                   smile=dict(type="open", w=0.35, h=0.13, near=0.05, far=0.045, dz=-0.012, gold_tooth=-0.45)),
        hair=dict(style="curls", color="#A85A24", dark="#7A3C14", light="#D8884A", crevice="#5A2A10", width=1.4,
                  n=75, curl=0.08, lobes=3, lobe_k=0.6),
        body=dict(shoulders=2.0),
        costume=dict(
            base=dict(color="#7E4028", rough=0.85, sheen=0.3),
            layers=[
                dict(kind="cloak", id="shawl", color="#8E3E1C", z1=-0.64, gap=0.03, flare=0.10,
                     open=[(-1.9, 0.30), (-1.2, 0.24), (-0.85, 0.20), (-0.66, 0.16)]),
                dict(kind="fur", id="fox", color="#F0E2CC", dark="#D8C8B0", light="#FFF8EC", crevice="#A89880",
                     r=0.62, r_in=0.24, t=0.09, front_z=-0.96, side_z=-0.86, back_z=-0.80, open=0.12,
                     clumps=dict(n=40, len=0.12, w=0.07, th=0.045), smooth=4),
                dict(kind="strap", id="ribbon", color="#3E9B5A", w=0.06, **{"from": (-0.30, -0.72), "to": (0.40, -1.5)}),
            ]),
        props=[dict(kind="chain", z=-1.04, d=0.22, color="#E8B23A", sheaf="#C8901A", link=0.06),
               dict(kind="monocle", eye="near", r=1.35, color="#E8B23A")],
        pose=dict(body=18, head=8, roll=4, nod=1),
        signature=dict(name="copper curl cloud + gold chain + monocle", zone="head width"),
        moods=dict(
            cunning=dict(eyes=dict(cunning=dict(open=[0.90, 0.42], tilt=0.0, arch=0.18, low=0.0)),
                         mouth=dict(cunning=dict(type="closed", w=0.27, near=0.045, far=0.0)),
                         **{"props~": {"monocle": dict(glint=3.0, r=1.45)}}),
            # angry: puffed cheeks, pursed lips (§7.8)
            angry=dict(mouth=dict(angry=dict(type="closed", w=0.17, near=-0.02, far=-0.02, sag=-0.004,
                                             crease=0.03)),
                       fx=dict(angry=dict(cheek_amt=0.035, cheek=(0.0, 0.0)))),
            tired=dict(hair=dict(flat=0.62)),
        ),
    ),
    # ---------------------------------------------------------------- Chancellor Iveta the Wise (League, Owl)
    "ldr_league": dict(
        name="Iveta", leader=True, female=True, tall_headgear=True, plate="#32D1C2",
        head=dict(shape="heart", wh=0.80, h_px=256, eye_line=0.47, cheekbones=0.03, chin=0.0),
        skin=SKIN["T5"], skin_tone="T5", blush=0.18,
        eyes=dict(sclera=0.22, open=0.80, iris="#C08A30", iris_shade=0.9, tilt=0.02, arch=0.24, flick=0.05),
        brows=dict(shape="arc", thick=0.058, color="#2A2226", arch=0.03, len=1.2, len_far=1.5, in_far=0.84),
        nose=dict(type="straight", w=0.048, drop=0.20, k=0.9, tip="#8A4E34", tip_k=0.3),
        mouth=dict(lip="#8A3E44", line=0.19,
                   calm=dict(type="closed", w=0.25, near=0.01, far=0.01),
                   smile=dict(type="closed", w=0.29, near=0.06, far=0.05, sag=0.012)),
        hair=dict(style="owl", color="#4C4652", dark="#403A44", light="#6A6272", crevice="#342E38",
                  tufts=dict(az=118, el=44, out=42, len=0.50, w=0.15)),
        body=dict(shoulders=1.9),
        costume=dict(
            base=dict(color="#7A2E4A", rough=0.85, sheen=0.4),
            layers=[
                dict(kind="cloak", id="mantle", color="#7A2E4A", z1=-0.64, gap=0.03, flare=0.12,
                     open=[(-1.9, 0.30), (-1.2, 0.22), (-0.85, 0.16), (-0.66, 0.12)]),
                dict(kind="bib", id="stole", color="#22A898", w=0.17, top=-0.72, bottom=-2.0, straps=False,
                     over_last=True, round=0.06, gap=0.006),
                dict(kind="ruff", id="ruff", color="#F4F2EE", z=-0.62, r=0.40, pleats=26, amp=0.045,
                     detail="ruff", min_px=3000, signature=True),
            ]),
        props=[dict(kind="glasses", shape="round", color="#6A4A30", tortoise="#B07A40", frame=0.03, w=1.65, h=1.5,
                    drop=0.02, off=0.03, tint="#FFFFFF", round_k=1.0)],
        pose=dict(body=22, head=6, roll=3, nod=3),
        signature=dict(name="owl tufts + white ruff + round glasses", zone="double bump on top; head frame"),
        moods=dict(
            smile=dict(eyes=dict(smile=dict(open=0.6, wink="both"))),
            cunning=dict(brows=dict(cunning=dict(lift=(-0.025, 0.10), arch_far=0.03, arch_near=-0.02)), **{"props~": {"glasses": dict(drop=0.075)}}, fx=dict(cunning=dict(gaze=(-0.30, 0.012)))),
            angry=dict(**{"props~": {"glasses": dict(glare=0.9)}},
                       mouth=dict(angry=dict(type="closed", w=0.22, near=-0.025, far=-0.02, crease=0.026))),
            tired=dict(**{"props~": {"glasses": dict(askew=11, drop=0.035)}}),
        ),
    ),
    # ---------------------------------------------------------------- Magister Torvald the Patient (Order, Turtle)
    "ldr_order": dict(
        name="Torvald", leader=True, female=False, tall_headgear=True, plate="#704FD1",
        head=dict(shape="long", wh=0.84, h_px=264, eye_line=0.47, brow_ridge=1.7, cheeks=0.95, muzzle=1.05),
        skin="#CC7A66", skin_tone="T3", blush=0.18, skin_sat=1.25, skin_value=0.90, skin_spec=0.08,
        eyes=dict(sclera=0.19, open=0.60, iris="#6A8AA0", iris_shade=0.9, tilt=-0.04, arch=0.06),
        brows=dict(shape="bushy", thick=0.085, color="#ECEEF2", arch=0.02, len=1.3, outer=-0.03),
        nose=dict(type="aquiline", len=0.24, w=0.07, proj=0.075, hump=0.01, drop=0.21, tip="#C8806A", tip_k=0.35),
        mouth=dict(lip="#A8605A", line=0.20,
                   calm=dict(type="closed", w=0.25, near=0.004, far=0.004),
                   smile=dict(type="closed", w=0.28, near=0.04, far=0.035, sag=0.01)),
        hair=dict(style="bald", bald=True, color="#B8B8C0"),
        beard=dict(style="braids", color="#E0E2E8", tip="#EEF0F4", root="#C4C6CE", crevice="#7A7C88", below=0.66,
                   mass_below=0.20, bead="#C8B48A", moustache=True, moustache_color="#E2E4EA",
                   moustache_dark="#C0C2CA", moustache_light="#F2F3F6", moustache_k=0.8),
        age=dict(forehead=2, crows=3, nasolabial=False, k=0.4),
        body=dict(shoulders=2.05),
        costume=dict(
            base=dict(color="#4E3522", rough=0.9, sheen=0.25),
            layers=[
                dict(kind="collar", color="#44301E", z=-0.66, h=0.10, out=0.02, flare=0.05, piping="#8E6AD8",
                     piping_r=0.018),
                dict(kind="piping", color="#8E6AD8", r=0.02, path=[(0.06, -0.72), (0.07, -1.0), (0.07, -1.4),
                                                                   (0.07, -1.8)]),
            ]),
        props=[dict(kind="shield", side="near", r=0.32, x=0.50, turn=35, up=0.5, color="#C8B48A", relief="hex",
                    edge="#A8946A", detail="shield", min_px=8000)],
        pose=dict(body=20, head=6, roll=-2, nod=-2),
        signature=dict(name="round turtle-shell shield on the near shoulder + braided beard",
                       zone="near shoulder; lower face width"),
        moods=dict(
            tired=dict(eyes=dict(tired=dict(open=0.10, tilt=0.15, arch=0.04))),
            cunning=dict(brows=dict(cunning=dict(lift=(-0.025, 0.10), arch_far=0.03, arch_near=-0.02)), eyes=dict(cunning=dict(open=[0.12, 0.74], tilt=0.0, arch=0.12))),
            angry=dict(brows=dict(angry=dict(inner=-0.075, outer=0.02, in_dx=0.02, thick_k=1.2)),
                       mouth=dict(angry=dict(type="closed", w=0.25, near=-0.03, far=-0.03, crease=0.024))),
        ),
    ),
    # ---------------------------------------------------------------- Sovereign Sairin the Iron (Alvaria, Wolf)
    "ldr_alvaria": dict(
        name="Sairin", leader=True, female=True, tall_headgear=True, plate="#E8873A",
        head=dict(shape="heart", wh=0.76, h_px=258, eye_line=0.47, cheekbones=0.035, chin=0.0),
        skin="#F2A898", skin_tone="T1", blush=0.16, skin_sat=1.40, skin_value=1.08,
        eyes=dict(sclera=0.19, open=0.70, iris="#5A8AC8", iris_shade=0.85, tilt=-0.05, arch=0.18, flick=0.07),
        brows=dict(shape="straight", thick=0.06, color="#2E2E3E", arch=0.015, outer=0.02, len=1.25, len_far=1.7,
                   in_far=0.84),
        nose=dict(type="straight", w=0.045, drop=0.21, k=0.95, tip="#E8A090", tip_k=0.25),
        mouth=dict(lip="#A85868", line=0.19,
                   calm=dict(type="closed", w=0.25, near=0.004, far=0.0),
                   smile=dict(type="closed", w=0.28, near=0.04, far=0.03, sag=0.008)),
        hair=dict(style="straight", res=0.015, color="#5A5A76", dark="#585874", light="#8890B6", crevice="#5A5A78", part=0.0,
                  drop=-0.68),
        headgear=dict(kind="diadem", color="#5A6270", w=0.07, el=(40, 22), spike=0.42, spike_az=34, back=22, out=16,
                      detail="diadem", min_px=1500),
        body=dict(shoulders=1.95),
        costume=dict(
            base=dict(color="#4A5A7C", rough=0.6, sheen=0.1),
            layers=[
                dict(kind="cloak", id="cloak", color="#36445F", z1=-0.64, gap=0.05, flare=0.10,
                     open=[(-1.9, 0.40), (-1.2, 0.36), (-0.85, 0.30), (-0.66, 0.26)]),
                # the state's orange as the cloak's lining showing along its front edges (§7.8 rule 3: >= 10 %)
                dict(kind="strip", id="lining", color="#F08A24", w=0.07, path=[(-0.30, -0.70), (-0.34, -1.0),
                                                                               (-0.38, -1.4), (-0.42, -1.8)]),
                dict(kind="strip", id="lining2", color="#F08A24", w=0.07, path=[(0.30, -0.70), (0.34, -1.0),
                                                                                (0.38, -1.4), (0.42, -1.8)]),
                dict(kind="vest", id="plate", color="#34507C", plate=True, metallic=0.4, rough=0.35, z0=-1.4, z1=-0.68,
                     thick=0.035),
                dict(kind="fur", id="stole", res=0.016, color="#F2F0EC", dark="#D8D4CC", light="#FFFFFF", crevice="#A8A49C",
                     r=0.78, r_in=0.28, t=0.11, front_z=-1.0, side_z=-0.9, back_z=-0.84, open=0.18,
                     clumps=dict(n=50, len=0.14, w=0.06, th=0.04), smooth=3, signature=True),
                dict(kind="tails", at=[(-0.24, -0.92), (0.24, -0.92)], len=0.55, r=0.075, color="#F2F0EC",
                     dark="#D8D4CC", light="#FFFFFF", crevice="#A8A49C", signature=True),
            ]),
        props=[],
        pose=dict(body=22, head=8, roll=-3, nod=4),
        signature=dict(name="iron diadem with two wolf-ear spikes + white wolf stole", zone="top centre; shoulders"),
        moods=dict(
            angry=dict(mouth=dict(angry=dict(type="open", shape="clench", w=0.27, h=0.07, near=-0.015, far=-0.015,
                                             dz=-0.004))),
            cunning=dict(mouth=dict(cunning=dict(type="closed", w=0.25, near=0.035, far=0.0, sag=0.002))),
            tired=dict(hair=dict(across=True)),
        ),
    ),
    # ---------------------------------------------------------------- Doge Velian the Sly (Saren, Fox)
    "ldr_saren": dict(
        name="Velian", leader=True, female=False, tall_headgear=True, plate="#D95290",
        head=dict(shape="heart", wh=0.74, h_px=260, eye_line=0.48, cheekbones=0.02, chin=-0.01),
        skin=SKIN["T4"], skin_tone="T4", blush=0.15, skin_sat=1.12,
        eyes=dict(sclera=0.19, open=0.64, iris="#5A6A26", iris_shade=0.9, tilt=0.10, arch=0.16),
        brows=dict(shape="angular", thick=0.058, color="#3A2418", arch=0.04, lift=(0.0, 0.03), len=1.25, len_far=1.8,
                   in_far=0.9),
        nose=dict(type="aquiline", len=0.28, w=0.05, proj=0.085, hump=0.008, drop=0.23, tip="#B86A4A", tip_k=0.3),
        mouth=dict(lip="#985048", line=0.20,
                   calm=dict(type="closed", w=0.26, near=0.03, far=0.0),
                   smile=dict(type="open", w=0.36, h=0.145, near=0.06, far=0.05, dz=-0.012)),
        hair=dict(style="slick", color="#64422A", dark="#543620", light="#825C3E", crevice="#3A2416", rough=0.4),
        beard=dict(style="goatee", color="#64422A", tip="#744E36", root="#543620", crevice="#3A2416", below=0.30,
                   width=0.16, moustache="upturned", curl=0.09, reach=0.32, signature=True),
        headgear=dict(kind="hat", id="toque", color="#14505A", mat="velvet", h=0.15, rim_dz=0.13, tilt=-8,
                      profile=[(0.0, 1.0), (0.3, 1.32), (0.62, 1.56), (0.86, 1.52), (1.0, 1.30)], top_dome=0.03,
                      top_tilt=3,
                      badge=dict(kind="coin", size=0.13, color="#E8B23A", g=0.55), signature=True, detail="toque",
                      min_px=3000),
        body=dict(shoulders=1.85),
        costume=dict(
            base=dict(color="#165446", rough=0.7, sheen=0.5),
            layers=[
                dict(kind="collar", color="#F2EEE4", z=-0.66, h=0.12, out=0.016, flare=0.02),
                # a cream cravat under the goatee: the dark chestnut goatee on the dark kaftan measured |dL*| 3.8
                dict(kind="neckerchief", color="#F2EEE4", z=-0.64),
                dict(kind="frogging", color="#E8B23A", z=(-0.88, -1.00, -1.12), w=0.20, t=0.022),
                dict(kind="strap", id="sash", color="#B83C78", w=0.08, **{"from": (-0.36, -0.72), "to": (0.45, -1.55)}),
            ]),
        props=[dict(kind="monocle", eye="near", r=1.25, color="#E8B23A"),
               dict(kind="chain", z=-1.06, d=0.14, color="#E8B23A", link=0.05, top_x=0.28,
                    emblem=dict(kind="coin", color="#E8B23A"))],
        pose=dict(body=24, head=10, roll=4, nod=3),
        signature=dict(name="flat wide toque + pointed goatee", zone="top centre; lower face"),
        moods=dict(
            cunning=dict(eyes=dict(cunning=dict(open=[0.40, 0.58], tilt=0.12, arch=0.10)),
                         mouth=dict(cunning=dict(type="closed", w=0.27, near=0.05, far=0.0)),
                         **{"props~": {"monocle": dict(glint=3.0)}}),
            angry=dict(beard=dict(curl=-0.05),
                       mouth=dict(angry=dict(type="open", shape="clench", w=0.28, h=0.07, near=-0.02, far=-0.02))),
            tired=dict(pose_tired=dict(nod=-4.5, roll=-2.0),
                       **{"props~": {"monocle": dict(hang=True, hang_at=(-0.14, -1.0), chain_to=(-0.34, -0.80))}}),
        ),
    ),
    # ---------------------------------------------------------------- Chieftain Bjorulf Black Feather (Pack, Raven)
    "ldr_pack": dict(
        name="Bjorulf", leader=True, female=False, tall_headgear=True, plate="#D1934F",
        head=dict(shape="long", wh=0.74, h_px=274, eye_line=0.47, cheeks=0.72, brow_ridge=1.4, jaw=-0.02,
                  muzzle=0.95),
        skin="#E8907C", skin_tone="T2", blush=0.12, skin_sat=1.25,
        mask=dict(**{"from": (-0.46, 0.02), "to": (0.46, 0.02)}, w=0.15, color="#4A5470", k=0.92, min_px=300),
        eyes=dict(sclera=0.18, open=0.66, iris="#A89A2C", iris_shade=0.9, tilt=-0.06, arch=0.12),
        brows=dict(shape="angular", thick=0.065, color="#2E2C30", arch=0.03, len=1.25, len_far=1.7, in_far=0.9),
        nose=dict(type="aquiline", len=0.27, w=0.058, proj=0.09, hump=0.03, drop=0.23, tip="#C8705A", tip_k=0.3),
        mouth=dict(lip="#A05048", line=0.20,
                   calm=dict(type="closed", w=0.26, near=0.02, far=-0.01),
                   smile=dict(type="open", w=0.34, h=0.12, near=0.05, far=0.04, dz=-0.012, lower_teeth=True,
                              fangs=True)),
        hair=dict(style="wild", color="#56545E", dark="#4A4852", light="#74727C", crevice="#36343C",
                  streak="#9A9AA4", drop=-0.60),
        beard=dict(style="scruffy", color="#4C4A52", tip="#666470", root="#44424A", crevice="#2C2A30", thick=0.045,
                   under=0.04, clump_lift=0.15, clump_th=0.6),
        body=dict(shoulders=1.95),
        costume=dict(
            base=dict(color="#5A4A3A", rough=0.7, sheen=0.1),
            layers=[
                dict(kind="cloak", id="cloak", color="#FAFBFC", z1=-0.64, gap=0.04, flare=0.12,
                     open=[(-1.9, 0.34), (-1.2, 0.28), (-0.85, 0.22), (-0.66, 0.18)]),
                dict(kind="fur", id="scales", color="#F4F6F8", dark="#DCE0E6", light="#FFFFFF", crevice="#AAB2BE",
                     r=0.92, r_in=0.30, t=0.07, front_z=-0.98, side_z=-0.92, back_z=-0.84, open=0.18,
                     clumps=dict(n=60, len=0.16, w=0.05, th=0.022, tip=0.25), smooth=2),
                dict(kind="strap", id="strap", color="#6A4A30", w=0.07, **{"from": (0.42, -0.72), "to": (-0.45, -1.6)}),
            ]),
        props=[dict(kind="feathers", len=0.5, w=0.11, back_k=0.3, out_k=1.6, color="#2E2E36", sheen="#4A5470", bead="#C8902A"),
               dict(kind="pendant", at=(-0.08, -1.0), color="#C8902A")],
        pose=dict(body=22, head=10, roll=-4, nod=-1),
        signature=dict(name="three black feathers up-back", zone="top back"),
        moods=dict(
            tired=dict(**{"props~": {"feathers": dict(droop=20)}}),
            cunning=dict(mouth=dict(cunning=dict(type="closed", w=0.27, near=0.05, far=-0.01))),
        ),
    ),
    # ---------------------------------------------------------------- Archmaster Ormdek the Stone (Conclave, Turtle)
    "ldr_conclave": dict(
        name="Ormdek", leader=True, female=False, tall_headgear=True, plate="#D18D4F",
        head=dict(shape="square", wh=1.18, n_top=3.4, h_px=258, eye_line=0.49, jaw=0.08, brow_ridge=1.6, cheeks=1.0, muzzle=1.1,
                  chin=0.02),
        skin="#9A5E4C", skin_tone="T5", blush=0.12, skin_sat=1.12, skin_spec=0.10,
        eyes=dict(sclera=0.18, open=0.66, iris="#7A8A9A", iris_shade=0.9, tilt=-0.06, arch=0.05),
        brows=dict(shape="straight", thick=0.09, color="#B4B4BC", arch=0.0, len=1.3, inner=-0.01, rough=0.6),
        nose=dict(type="straight", w=0.085, drop=0.21, k=1.05, tip="#8A4E34", tip_k=0.3),
        mouth=dict(lip="#7A4038", line=0.21,
                   calm=dict(type="closed", w=0.26, near=-0.005, far=-0.005),
                   smile=dict(type="open", w=0.30, h=0.10, near=0.03, far=0.03, dz=-0.008, teeth=0.45)),
        hair=dict(style="bald", bald=True, color="#9A9AA2"),
        beard=dict(style="box", color="#A0A0A8", tip="#B8B8C0", root="#8A8A94", crevice="#5A5A66", below=0.42,
                   wider=0.10, moustache=True, moustache_color="#A8A8B0", moustache_dark="#8A8A94",
                   moustache_light="#C4C4CA", signature=True),
        headgear=dict(kind="shell", id="steel_plate", color="#C0C8D0", mat="metal", rough=0.3, metallic=0.5,
                      edge=[(0, 52), (40, 48), (80, 40), (120, 34), (180, 30)], thick=0.04, roll=0.02, res=0.012,
                      smooth=3),
        body=dict(shoulders=2.02, neck=0.62),
        costume=dict(
            base=dict(color="#7A6A5A", rough=0.7, sheen=0.1),
            layers=[
                dict(kind="vest", id="steel", color="#5A6270", plate=True, metallic=0.35, rough=0.35, z0=-1.4, z1=-0.68,
                     thick=0.04),
                dict(kind="piping", color="#A87A50", r=0.022, path=[(-0.42, -0.74), (-0.2, -0.80), (0.0, -0.82),
                                                                   (0.2, -0.80), (0.42, -0.74)]),
                dict(kind="buttons", id="rivet", at=[(-0.30, -0.95), (0.30, -0.95), (-0.30, -1.15), (0.30, -1.15)],
                     r=0.026, color="#A87A50"),
            ]),
        props=[dict(kind="shield", side="far", r=0.40, x=0.48, turn=42, up=0.15, dz=0.15, color="#B8C0C8", metal=True,
                    edge="#A87A50", rivets=12, detail="shield", min_px=2000)],
        pose=dict(body=16, head=4, roll=0, nod=-3),
        signature=dict(name="box beard + one massive shield pauldron on the far shoulder",
                       zone="lower face width; far side"),
        moods=dict(
            smile=dict(eyes=dict(smile=dict(open=[0.62, 0.62], low=0.12))),     # P-A3: >= 6 px open at 128
            angry=dict(pose_angry=dict(nod=-3.0), beard=dict(jut=0.06),
                       brows=dict(angry=dict(inner=-0.075, outer=0.025, in_dx=0.02, thick_k=1.25)),
                       fx=dict(angry=dict(blush=0.05, nose_red=0.12)),    # deep skin: the full flush read orange
                       mouth=dict(angry=dict(type="open", shape="clench", w=0.27, h=0.07, near=-0.015, far=-0.015))),
            cunning=dict(brows=dict(cunning=dict(lift=(0.0, 0.10), arch_far=0.02))),
            tired=dict(pose_tired=dict(nod=-3.0, roll=-3.0), eyes=dict(tired=dict(open=0.26))),
        ),
    ),
    # ---------------------------------------------------------------- Margravine Vedana Dark Wing (Veilmark, Raven)
    "ldr_veilmark": dict(
        name="Vedana", leader=True, female=True, tall_headgear=True, plate="#58D14F",
        head=dict(shape="oval", wh=0.78, h_px=266, eye_line=0.47, cheekbones=0.04, chin=0.0),
        skin="#F2A898", skin_tone="T1", blush=0.18, skin_sat=1.40, skin_value=1.08,
        eyes=dict(sclera=0.20, open=0.64, iris="#7A6A9A", iris_shade=0.9, tilt=0.08, arch=0.18, flick=0.08,
                  shadow="#6A4A70", shadow_k=0.5),
        brows=dict(shape="arc", thick=0.056, color="#2E2638", arch=0.04, lift=(0.0, 0.02), len=1.25, len_far=1.7,
                   in_far=0.84),
        nose=dict(type="straight", w=0.042, drop=0.20, k=0.9, tip="#F0A090", tip_k=0.25),
        mouth=dict(lip="#6A2A48", line=0.19,
                   calm=dict(type="closed", w=0.25, near=0.03, far=0.0),
                   smile=dict(type="closed", w=0.28, near=0.065, far=0.04, sag=0.01)),
        hair=dict(style="straight", color="#726290", dark="#685A84", light="#9482B0", crevice="#6A5C88", part=36,
                  drop=-0.70),
        body=dict(shoulders=1.85),
        costume=dict(
            base=dict(color="#7A6290", rough=0.8, sheen=0.4),
            layers=[
                dict(kind="collar", color="#76608C", z=-0.64, h=0.16, out=-0.004, flare=0.06, gap=0.10,
                     piping="#C8CCD4", piping_r=0.014),
                dict(kind="lapels", color="#76608C",
                     shape=[(0.08, -0.66), (0.24, -0.70), (0.33, -0.78), (0.28, -0.84), (0.20, -0.98), (0.04, -1.14)]),
            ]),
        props=[dict(kind="wing", x=0.52, y=0.06, n=10, len=1.30, a0=70, spread=48, w=0.13, color="#706C84", sheen="#9A7ACA",
                    min_px=4000),
               dict(kind="brooch", at=(0.0, -0.74), d=0.10),
               dict(kind="feather_pin", az=-82, el=24, len=0.20, w=0.04, color="#2E2A36", pin="#C8CCD4",
                    dir=(-0.4, 0.5, 0.8))],
        pose=dict(body=26, head=8, roll=3, nod=3),
        signature=dict(name="dark wing rising over the far shoulder", zone="far side"),
        moods=dict(
            smile=dict(eyes=dict(smile=dict(open=[0.60, 0.60], low=0.12))),
            tired=dict(hair=dict(across=True), eyes=dict(tired=dict(open=0.26, tilt=0.22, arch=0.10, low=0.0))),
            angry=dict(mouth=dict(angry=dict(type="open", shape="clench", w=0.26, h=0.07, near=-0.01, far=-0.02))),
        ),
    ),
    # ---------------------------------------------------------------- Consul Arman the Nocturne (Lakes, Owl)
    "ldr_lakes": dict(
        name="Arman", leader=True, female=False, tall_headgear=True, plate="#42BED1",
        head=dict(shape="long", wh=0.76, h_px=262, eye_line=0.47, cheeks=0.95),
        skin=SKIN["T6"], skin_tone="T6", blush=0.10,
        eyes=dict(sclera=0.19, open=0.72, iris="#8A5A2A", iris_shade=1.0, tilt=0.02, arch=0.20),
        brows=dict(shape="arc", thick=0.06, color="#E4E6EC", arch=0.025, len=1.25, len_far=1.7, in_far=0.84),
        nose=dict(type="straight", w=0.05, drop=0.21, k=1.05, tip="#6A3828", tip_k=0.2),
        mouth=dict(lip="#5A3028", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.016, far=0.01),
                   smile=dict(type="closed", w=0.30, near=0.055, far=0.05, sag=0.01)),
        hair=dict(style="short", color="#E4E6EC", dark="#B8BCC8", light="#FFFFFF", crevice="#7A8094",
                  escape=[(-72, 26, 4, 0.065), (-88, 20, -6, 0.06), (78, 24, 4, 0.06)]),
        headgear=dict(kind="hat", id="top_hat", color="#222C48", mat="velvet", h=0.36, rim_dz=0.01, tilt=-4,
                      profile=[(0.0, 1.0), (0.06, 0.99), (0.5, 1.0), (1.0, 1.08)], top_tilt=-3,
                      band=dict(h=0.07, color="#C8CCD4", mat="metal"),
                      brim=dict(w=0.07, ang=0, up_sides=22, t=0.024, color="#222C48"), signature=True,
                      detail="top_hat", min_px=5000),
        body=dict(shoulders=1.9),
        costume=dict(
            base=dict(color="#2A3A62", rough=0.8, sheen=0.4),
            layers=[
                dict(kind="neckerchief", color="#F2F2F2", z=-0.62),
                dict(kind="lapels", color="#2A8AA0",
                     shape=[(0.10, -0.66), (0.28, -0.70), (0.38, -0.80), (0.32, -0.86), (0.24, -1.00), (0.05, -1.18)]),
                dict(kind="buttons", id="btn", at=[(-0.16, -1.02), (0.16, -1.02), (-0.15, -1.20), (0.15, -1.20)], r=0.03,
                     color="#C8CCD4"),
            ]),
        props=[dict(kind="glasses", shape="half", color="#C8CCD4", metal=0.5, frame=0.022, w=1.8, h=1.0, drop=0.075,
                    off=0.04, tint="#FFFFFF"),
               dict(kind="brooch", at=(0.0, -0.74), d=0.08)],
        pose=dict(body=20, head=6, roll=2, nod=1),
        signature=dict(name="tall top hat + half glasses", zone="top centre"),
        moods=dict(
            smile=dict(**{"headgear~": dict(side_tilt=8.0)}),
            cunning=dict(fx=dict(cunning=dict(gaze=(-0.30, 0.014)))),
            angry=dict(**{"props~": {"glasses": dict(glare=0.9, drop=0.05)}},
                       mouth=dict(angry=dict(type="closed", w=0.22, near=-0.02, far=-0.02, crease=0.026))),
            tired=dict(**{"headgear~": dict(top_tilt=-12.0, rim_dz=-0.06, tilt=-14)}),
        ),
    ),
    # ---------------------------------------------------------------- the ruler (§7.10)
    "ruler": dict(
        name="Ruler", ruler=True, female=False, tall_headgear=True, plate="#8FCDF2",
        head=dict(shape="square", wh=0.90, h_px=264, eye_line=0.48, jaw=0.0, cheeks=1.1),
        skin="#E0907A", skin_tone="T3", blush=0.20, skin_sat=1.22,
        eyes=dict(sclera=0.20, open=0.80, iris="#6A4426", iris_shade=1.0, tilt=0.04, arch=0.22),
        brows=dict(shape="arc", thick=0.068, color="#4A3020", arch=0.025, len=1.22, len_far=1.6, in_far=0.84),
        nose=dict(type="potato", k=0.82, drop=0.20, tip="#D8806A", tip_k=0.35),
        mouth=dict(lip="#A85A4A", line=0.20,
                   calm=dict(type="closed", w=0.27, near=0.015, far=0.015)),
        hair=dict(style="long", res=0.015, color="#5E3E26", dark="#50361E", light="#7E5838", crevice="#3C2816", drop=-0.42),
        beard=dict(style="round", color="#5E3E26", tip="#7E5838", root="#50361E", crevice="#3C2816", below=0.22,
                   moustache=True, moustache_color="#563620", moustache_dark="#4A3018", moustache_light="#7A5434",
                   signature=True),
        headgear=dict(kind="crown", color="#E8B23A", band=0.07, merlon=0.15, merlon_w=0.15, cap=0.22, rim_dz=0.10,
                      velvet="#2E5BD8", emit=1.0),
        body=dict(shoulders=2.1),
        costume=dict(
            base=dict(color="#2E5BD8", rough=0.85, sheen=0.4),
            layers=[
                dict(kind="cloak", id="mantle", color="#2E5BD8", z1=-0.64, gap=0.03, flare=0.12,
                     open=[(-1.9, 0.30), (-1.2, 0.24), (-0.85, 0.18), (-0.66, 0.14)]),
                dict(kind="fur", id="fur", res=0.016, color="#F4F1EA", dark="#DCD6CC", light="#FFFFFF", crevice="#A8A296",
                     r=0.82, r_in=0.28, t=0.10, front_z=-0.98, side_z=-0.9, back_z=-0.82, open=0.14,
                     clumps=dict(n=40, len=0.14, w=0.07, th=0.04), smooth=4),
            ]),
        props=[dict(kind="chain", z=-1.06, d=0.18, color="#E8B23A", link=0.055, top_x=0.30,
                    emblem=dict(kind="hex", color="#E8B23A", inner="#3A8DFF", inner_emit=0.8))],
        pose=dict(body=18, head=6, roll=0, nod=1),
        signature=dict(name="crown merlons + round beard", zone="top centre; lower face width"),
    ),
})


# ================================================================== eras, moods, the resolver
import copy  # noqa: E402

# Era looks (§7.6 "Палитра и эпохи", §7.7): per commander {era: patch}. A patch replaces whole entries named in
# REPLACE (the costume, the headgear, the props list), deep-merges dicts (hair, body, pose ...), and edits props by
# kind: "props~": {kind: {...} | None} patches (or drops) the era-1 prop of that kind, "props+": [...] adds props.
# Filled below (ERA_LOOKS.update); the face, the hair's shape and colour, the facial hair, the signature and the
# accent never change between eras (§7.7) — the lint checks the face keys are not patched.
ERA_LOOKS = {}
REPLACE = ("costume", "headgear", "props", "paint")
FACE_KEYS = ("head", "skin", "skin_tone", "eyes", "brows", "nose", "mouth", "beard", "signature", "female")


def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict) and k not in REPLACE:
            _merge(a[k], v)
        else:
            a[k] = copy.deepcopy(v)
    return a


def apply_patch(c, patch):
    patch = dict(patch)
    pt = patch.pop("props~", None)
    add = patch.pop("props+", None)
    # "<key>~": merge into an entry REPLACE would otherwise replace (a mood tilting a leader's hat: "headgear~")
    for k in [k for k in patch if k.endswith("~")]:
        v = patch.pop(k)
        base = c.get(k[:-1])
        if isinstance(base, dict):
            _merge(base, v)
    _merge(c, patch)
    if pt:
        out = []
        for pr in c.get("props", []):
            if pr["kind"] in pt:
                if pt[pr["kind"]] is None:
                    continue
                pr = _merge(copy.deepcopy(pr), pt[pr["kind"]])
            out.append(pr)
        c["props"] = out
    if add:
        c["props"] = c.get("props", []) + copy.deepcopy(add)
    return c


# §7.9 the five moods, as deltas over the character's own calm face (numbers in H). The face keys (eyes, brows,
# mouth) are filled for a mood the character does not describe itself (the leaders; the commanders carry their own
# smile, §7.6); "fx" are the mood's shader and brush effects (cheek lift near / far, blush, pupil, gaze, eye bags,
# the angry snarl), read by head.py, face.py and rig.py through ctx.fx.
MOOD_POSE = {"smile": dict(roll=-5.0, nod=3.0), "angry": dict(nod=-5.0), "cunning": dict(roll=5.0, head=-4.0),
             "tired": dict(nod=-6.0, roll=-2.0)}
MOOD_FX = {
    "calm": dict(),
    # the commanders' smile as P1/P2 built it (cheeks up STYLE cheek_smile, blush +10 %, pupil 0.62, a fuller rim)
    "smile": dict(cheek=(0.055, 0.055), cheek_amt=0.018, blush=0.10, pupil=0.62, rim="smile"),
    # a snarl: cheeks up 0.02, a red flush on the nose and cheeks (+8-15 %), flared nostrils, two folds between the
    # brows; the pupil 0.48
    "angry": dict(cheek=(0.02, 0.02), cheek_amt=0.008, blush=0.12, nose_red=0.30, pupil=0.48, nostrils=1.18,
                  frown=2),
    # the near cheek up 0.03, the glance 30 % of the eye's width toward the near side, the pupil 0.55
    "cunning": dict(cheek=(0.03, 0.0), cheek_amt=0.006, pupil=0.55, gaze=(-0.30, 0.0)),
    # cheeks down 0.03, bags under the eyes (skin x0.85, a crescent 0.03 H), the glance 0.015 H down
    "tired": dict(cheek=(-0.03, -0.03), cheek_amt=-0.012, pupil=0.58, gaze=(0.0, -0.015), bags=0.85),
}


def _open_of(ey, side):
    o = ey.get("open", 0.80)
    return o[side] if isinstance(o, (list, tuple)) else o


def _fill_mood(c, mood):
    """The §7.9 numbers for a mood the character does not describe: eyes, brows, mouth and the head's pose delta."""
    if mood == "calm":
        return
    if mood == "smile" and c.get("_cid", "").startswith("cmd_"):
        return      # a commander's smile is its own approved P2 preset (§7.6); what it leaves out stays calm, as in P2
    ey, br, mo = c["eyes"], c["brows"], c["mouth"]
    tilt, arch = ey.get("tilt", 0.08), ey.get("arch", 0.24)
    if mood not in ey:
        if mood == "smile":
            ey[mood] = dict(open=[max(0.45, _open_of(ey, i) - 0.08) for i in (0, 1)], low=0.20, bow=0.30,
                            arch=arch + 0.04, tilt=tilt)
        elif mood == "angry":   # 0.55, the inner corner lower
            ey[mood] = dict(open=min(0.55, _open_of(ey, 0)), tilt=-0.22, arch=0.10, low=0.04)
        elif mood == "cunning":  # the near eye narrowed 0.40-0.45, the far 0.60-0.65
            ey[mood] = dict(open=[0.43, 0.62], tilt=tilt * 0.5, arch=arch * 0.6, low=0.06)
        elif mood == "tired":    # 0.30, the outer corner down
            ey[mood] = dict(open=0.30, tilt=0.22, arch=0.10, low=0.0)
    if mood not in br:
        br[mood] = {"smile": dict(inner=0.025, outer=0.01, arch=0.01),
                    "angry": dict(inner=-0.065, outer=0.025, in_dx=0.02, thick_k=1.15, arch=-0.01),
                    "cunning": dict(lift=(-0.02, 0.09), arch_far=0.03, arch_near=-0.02),
                    "tired": dict(inner=0.035, outer=-0.03, arch=-0.005)}[mood]
    if mood not in mo:
        cw = mo.get("calm", {}).get("w", 0.27)
        mo[mood] = {"smile": dict(type="open", w=0.33, h=0.12, near=0.04, far=0.035, dz=-0.012),
                    "angry": dict(type="open", shape="trap", w=0.28, h=0.10, near=-0.02, far=-0.02, dz=-0.006,
                                  lower_teeth=True),
                    "cunning": dict(type="closed", w=cw, near=0.04, far=0.0, sag=0.004),
                    "tired": dict(type="closed", w=0.24, near=-0.015, far=-0.015, sag=0.0, crease=0.026)}[mood]
    if "pose_" + mood not in c:
        c["pose_" + mood] = dict(MOOD_POSE.get(mood, {}))


def resolve(cid, era=1, mood="calm"):
    """The character's data for one era and mood: its era-1 entry, the era patch (ERA_LOOKS), the §7.9 mood
    defaults for whatever the character does not describe, its own mood patch (c["moods"][mood]) and the mood's
    effects (c["_fx"] = MOOD_FX[mood] updated by c["fx"][mood])."""
    c = copy.deepcopy(CHARS[cid])
    c["_cid"] = cid
    look = ERA_LOOKS.get(cid, {}).get(era)
    if look:
        apply_patch(c, look)
    _fill_mood(c, mood)
    mp = c.get("moods", {}).get(mood)
    if mp:
        apply_patch(c, mp)
    fx = dict(MOOD_FX.get(mood, {}))
    fx.update(c.get("fx", {}).get(mood, {}))
    c["_fx"] = fx
    c["_era"] = era
    return c


COMMANDER_IDS = [k for k in CHARS if k.startswith("cmd_")]
LEADER_IDS = [k for k in CHARS if k.startswith("ldr_")]
KIT_IDS = set(CHARS)
# since P3 every id and era goes through the kit (the leaders have no era files, §7.8 rule 4)
KIT_ERAS = {cid: ({1} if cid.startswith("ldr_") else {1, 2, 3, 4}) for cid in CHARS}


def headgear_of(cid, era):
    """A commander's headgear id in an era (the builder kind unless it says otherwise: Olm's brass goggles and Irma's
    motor goggles share the goggles builder) — for the uniqueness lint (§7.6)."""
    hg = resolve(cid, era).get("headgear") or {}
    return hg.get("id", hg.get("kind"))


# Modules locked to a commander (§7.8 rule 1): no leader (nor the ruler) may use them.
LOCKED = dict(hair={"kerchief": "Lira", "ponytail": "Irma", "bun": "Vance", "bob": "Vega", "flattop": "Frey",
                    "fringe": "Vik"},
              beard={"pear": "Bram", "long": "Rai", "walrus": "Kort", "thin": "Hawk", "chops": "Olm"},
              headgear={"hood": "Vik", "circlet": "Rai", "aviator": "Hawk", "kerchief": "Lira",
                        "brass_goggles": "Olm"},
              props={"raven": "Vik", "scarf": "Hawk", "queen": "Vance", "spoon": "Bram", "spyglass": "Seir"})


def lint():
    """Fail the build when an id has no signature or no signature zone, two ids share a signature, two commanders
    share a headgear in one era, an era patch touches the face, or a leader / the ruler uses a module locked to a
    commander (runs at every build, portrait_kit.build)."""
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
        for cid in COMMANDER_IDS:
            if era not in KIT_ERAS.get(cid, ()):
                continue
            k = headgear_of(cid, era)
            if k:
                if k in worn:
                    errs.append("era %d: %s and %s both wear %s" % (era, worn[k], cid, k))
                worn[k] = cid
    for cid, looks in ERA_LOOKS.items():
        for era, patch in looks.items():
            bad = [k for k in patch if k in FACE_KEYS]
            if bad:
                errs.append("%s era %d patches the face (%s): §7.7 keeps it" % (cid, era, ", ".join(bad)))
    for cid, c in CHARS.items():
        if cid.startswith("cmd_"):
            continue
        hs = (c.get("hair") or {}).get("style")
        if hs in LOCKED["hair"]:
            errs.append("%s uses %s's hair module %r" % (cid, LOCKED["hair"][hs], hs))
        bs = (c.get("beard") or {}).get("style")
        if bs in LOCKED["beard"]:
            errs.append("%s uses %s's beard module %r" % (cid, LOCKED["beard"][bs], bs))
        for era in (1, 2, 3, 4):
            hg = resolve(cid, era).get("headgear") or {}
            for k in (hg.get("kind"), hg.get("id")):
                if k in LOCKED["headgear"]:
                    errs.append("%s uses %s's headgear %r" % (cid, LOCKED["headgear"][k], k))
            for pr in resolve(cid, era).get("props", []):
                if pr["kind"] in LOCKED["props"]:
                    errs.append("%s uses %s's prop %r" % (cid, LOCKED["props"][pr["kind"]], pr["kind"]))
                if pr["kind"] == "glasses" and pr.get("shape", "rect") == "rect":
                    errs.append("%s wears Vega's rectangular glasses" % cid)
    if errs:
        raise ValueError("chars.py lint: " + "; ".join(sorted(set(errs))))
    return True


# ================================================================== the era looks (§7.6 "Палитра и эпохи", §7.7)
# E2 coats and braid (the main colour L* -5, +5 % saturation), E3 field uniform (mixed 0.20 with #6E6A4E, x0.85),
# E4 rounded painted plates (L* +6, x0.95, roughness 0.45, metallic 0.25) over the #3A4150 underlayer with an accent
# strip (1.0-1.2, >= 0.04 H wide). style.era_color does the colour maths; the face, the hair, the facial hair, the
# signature and the accent never change (the lint refuses an era patch of a face key).
from .style import ERA_UNDER as _UNDER  # noqa: E402
from .style import era_color as _E  # noqa: E402

_LAPEL = [(0.08, -0.66), (0.24, -0.70), (0.33, -0.78), (0.28, -0.84), (0.20, -0.98), (0.04, -1.14)]
_ROUND_HELMET = [(0.0, 1.0), (0.3, 1.0), (0.62, 0.88), (0.86, 0.58), (1.0, 0.0)]
_FRONT = [(-0.42, -0.74), (-0.2, -0.80), (0.0, -0.82), (0.2, -0.80), (0.42, -0.74)]   # a plate's top edge


def _plate(col, z0=-1.42, z1=-0.66, **kw):
    """§7.7 E4: a rounded painted breastplate (vest shell)."""
    return dict(kind="vest", id="plate", color=col, plate=True, z0=z0, z1=z1, thick=kw.pop("thick", 0.04), **kw)


# E3 field colours where the formula alone would make two commanders twins (§7.7 asks dE76 >= 12 between any two
# commanders in E3; Bram's slate #3D4A58 and Vega's graphite #44484F are dE76 ~3 apart already in E1, the olive mix of
# E3 leaves them at 2.9, and Lira's green came within 7.8 of Vik's camo): Bram keeps his hue a step bluer, Vega's
# graphite a step lighter, Lira's green deeper and less mixed — each within dE76 22 of its own E1
_BRAM_E3 = "#34507A"      # dE76 17.9 to E1
_VEGA_E3 = "#626670"      # dE76 14.5 to E1
_LIRA_E3 = "#226A40"      # dE76 8.8 to E1
_KORT_E3 = "#566A3C"      # dE76 7.1 to E1 (the olive mix brought his greatcoat within 11.5 of Hawk's flight jacket)
_FREY_E3 = "#1A5A44"      # dE76 20.6 to E1 as rendered (the olive mix left him 8.4 from Vik's camo; now 13.7)
# E4 plates of the slate / graphite / black-leather commanders converged (bram-vega 3.4, bram-irma 3.9, vega-irma
# 5.6): Bram's plates a step bluer, Vega's a step lighter (Irma's keep the formula); Hawk's E4 suit sky-tinted, apart
# from Rai's white plates (2.2)
_BRAM_E4 = "#4A6488"      # dE76 17.1 to E1
_VEGA_E4 = "#6C7280"      # dE76 ~19 to E1


ERA_LOOKS.update({
    # ---------------------------------------------------------------- Bram
    "cmd_bram": {
        2: dict(costume=dict(base=dict(color="#34486A", rough=0.85, sheen=0.35), layers=[
                    dict(kind="collar", color="#34486A", z=-0.64, h=0.07, out=0.004, flare=0.012),
                    dict(kind="lapels", color="#DCCAA0", shape=_LAPEL),
                    dict(kind="strap", id="sash", color="#F2F0EA", w=0.09, **{"from": (-0.44, -0.70), "to": (0.50, -1.6)}),
                    dict(kind="buttons", id="btn", at=[(-0.30, -0.88), (-0.31, -1.00), (-0.31, -1.12)], r=0.032,
                         color="#E0AD45"),
                    dict(kind="belt", z=-1.09, w=0.13, color="#6B4226", buckle="#E0AD45", over=0.006)]),
                headgear=dict(kind="hat", id="shako", color="#34486A", h=0.40, profile=[(0.0, 1.0), (1.0, 1.14)],
                              band=dict(h=0.05, color="#423C3E", mat="leather"), top_tilt=-4,
                              brim=dict(w=0.10, ang=-14, front=58, color="#423C3E", mat="leather"),
                              badge=dict(kind="millstone", size=0.17, color="#E0AD45", g=0.48, dark="#8A6A2A"))),
        3: dict(costume=dict(base=dict(color=_BRAM_E3, rough=0.9, sheen=0.25), layers=[
                    dict(kind="collar", color=_BRAM_E3, z=-0.64, h=0.07, out=0.004, flare=0.012),
                    dict(kind="strap", id="ystrap1", color="#6B4226", w=0.075,
                         **{"from": (-0.36, -0.70), "to": (-0.16, -1.1)}),
                    dict(kind="strap", id="ystrap2", color="#6B4226", w=0.075,
                         **{"from": (0.36, -0.70), "to": (0.16, -1.1)}),
                    dict(kind="belt", z=-1.09, w=0.13, color="#6B4226", buckle="#B0A090", over=0.006)]),
                headgear=dict(kind="hat", id="brodie", color=_BRAM_E3, mat="painted", h=0.34, rim_dz=0.07,
                              profile=[(0.0, 1.0), (0.25, 0.98), (0.6, 0.86), (0.85, 0.58), (1.0, 0.0)],
                              brim=dict(w=0.13, ang=-8, t=0.026), chinstrap=dict(color="#6B4226", to_z=-0.38)),
                **{"props~": {"chevrons": dict(n=3, at=(0.13, 0.21, 0.29))}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_BRAM_E4),
                    dict(kind="collar", color="#B9C7D6", metal=True, z=-0.66, h=0.07, out=0.03, flare=0.02),
                    dict(kind="pauldrons", color=_BRAM_E4, painted=True, stripe="#F0A830", n=2, spread=84,
                         bands=[(92, 36), (44, 0)], detail="pauldrons", min_px=4000),
                    dict(kind="strip", id="amber", color="#F0A830", emit=1.1, w=0.05, detail="glow", min_px=100,
                         path=[(-0.62, -1.22), (-0.3, -1.25), (0.0, -1.26), (0.3, -1.25), (0.62, -1.22)]),
                    dict(kind="belt", z=-1.09, w=0.13, color="#6B4226", buckle="#E0AD45", over=0.058)]),
                headgear=dict(kind="hat", id="open_helmet", color=_BRAM_E4, mat="painted", h=0.30,
                              rim_dz=0.06, profile=_ROUND_HELMET, brim=dict(w=0.035, ang=0, t=0.024),
                              extra=[dict(kind="visor", el=58, span=62, h=0.10, dh=8, tint="#DDEBF4", frame="#B9C7D6",
                                          off=0.03)]),
                **{"props~": {"chevrons": None},
                   "props+": [dict(kind="emblem", shape="millstone", at=(-0.30, -1.00), size=0.20, color="#B9C7D6",
                                   dark="#6A7484", detail="millstone", min_px=200)]}),
    },
})

ERA_LOOKS.update({
    # ---------------------------------------------------------------- Lira
    "cmd_lira": {
        2: dict(costume=dict(base=dict(color=_E("#2E7A44", 2), rough=0.85, sheen=0.35), layers=[
                    dict(kind="collar", color=_E("#2E7A44", 2), z=-0.64, h=0.08, out=0.004, flare=0.016),
                    dict(kind="lapels", color="#F2F0EA", shape=_LAPEL),
                    dict(kind="buttons", id="btn", at=[(-0.14, -0.96), (0.14, -0.96), (-0.13, -1.12), (0.13, -1.12)],
                         r=0.03, color="#E0AD45"),
                    dict(kind="epaulettes", color="#E0AD45", len=0.16, w=0.08, x=0.46, fringe=0, board=True,
                         stripe="#3E9B5A"),
                    dict(kind="strap", id="strap", color="#8A5A34", detail="satchel_strap", min_px=3000,
                         **{"from": (0.46, -0.70), "to": (-0.62, -1.75)}, w=0.10)]),
                headgear=dict(kind="shell", id="bonnet", color="#EAF0F8", mat="fabric", thick=0.06, lift=0.07,
                              roll=0.028, clear=0.03,
                              edge=[(0, 44), (40, 36), (75, 18), (100, 6), (140, -6), (180, -14)],
                              ribbon=dict(color="#3E9B5A", w=0.055, above=7, knot_az=-150, knot_el=12, tail=0.30),
                              badge=dict(kind="leaf", size=0.15, color="#3E9B5A", el=40, metal=0.0, rough=0.5))),
        3: dict(costume=dict(base=dict(color=_LIRA_E3, rough=0.9, sheen=0.25), layers=[
                    dict(kind="collar", color=_LIRA_E3, z=-0.64, h=0.07, out=0.004, flare=0.014),
                    dict(kind="neckerchief", color="#22603A", z=-0.63),
                    dict(kind="pocket", id="pocket1", on="torso", at=(-0.22, -1.02), w=0.11, h=0.14,
                         color=_LIRA_E3),
                    dict(kind="strap", id="strap", color="#8A5A34", detail="satchel_strap", min_px=3000,
                         **{"from": (0.46, -0.70), "to": (-0.62, -1.75)}, w=0.10)]),
                headgear=dict(kind="hat", id="side_cap", color=_LIRA_E3, h=0.12, rim_dz=0.15, tilt=-4,
                              side_tilt=-8, squash=(0.62, 1.12), profile=[(0.0, 1.0), (0.55, 0.96), (0.85, 0.7),
                                                                          (1.0, 0.18)],
                              badge=dict(kind="leaf", size=0.10, color="#3E9B5A", g=0.4, az=-20, metal=0.0)),
                **{"props+": [dict(kind="chevrons", style="ring", n=1, at=(0.30,), r=0.05, color="#F2F0EA",
                                   detail="armband", min_px=200)]}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#2E7A44", 4)),
                    dict(kind="piping", color="#2E7A44", r=0.02, path=_FRONT),
                    dict(kind="pauldrons", color="#ECEFEA", painted=True, stripe="#3E9B5A", n=1, spread=84,
                         bands=[(92, 30)], detail="pauldrons", min_px=2000),
                    dict(kind="strap", id="strap", color="#3E9B5A", detail="satchel_strap", min_px=3000,
                         **{"from": (0.46, -0.70), "to": (-0.62, -1.75)}, w=0.10)]),
                headgear=dict(kind="hat", id="rescue_helmet", color="#D8E6F6", mat="painted", h=0.30, rim_dz=0.05,
                              profile=_ROUND_HELMET, brim=dict(w=0.03, ang=0, t=0.022),
                              band=dict(h=0.05, color="#3E9B5A", mat="painted"),
                              extra=[dict(kind="visor", el=60, span=60, h=0.10, dh=8, tint="#E8F6FF", frame="#3E9B5A",
                                          off=0.03)]),
                **{"props~": {"badge": dict(glow=0.8)}}),
    },
    # ---------------------------------------------------------------- Olm
    "cmd_olm": {
        2: dict(costume=dict(base=dict(color="#563620", rough=0.85, sheen=0.3), layers=[
                    dict(kind="collar", color="#FAF4E6", z=-0.64, h=0.06, out=0.004, flare=0.012, gap=0.06),
                    dict(kind="buttons", id="btn", at=[(-0.40, -0.92), (-0.40, -1.08), (0.40, -0.92), (0.40, -1.08)],
                         r=0.03, color="#C9A24A"),
                    dict(kind="bib", id="apron", color="#7A4E2D", leather=True, w=0.30, top=-0.80, bottom=-2.0,
                         straps=True, detail="apron", min_px=6000),
                    dict(kind="pocket", id="pocket", on="apron", at=(0.15, -1.00), w=0.13, h=0.22, color="#6B4426")]),
                headgear=dict(CHARS["cmd_olm"]["headgear"], id="green_goggles", lens_color="#5AC88A"),
                **{"props~": {"wrench": dict(color="#C9A24A")}}),
        3: dict(costume=dict(base=dict(color="#8A6A44", rough=0.85, sheen=0.25), layers=[
                    dict(kind="collar", color="#8A6A44", z=-0.64, h=0.07, out=0.004, flare=0.014),
                    dict(kind="bib", id="apron", color="#7A4E2D", leather=True, w=0.28, top=-0.92, bottom=-2.0,
                         straps=True, detail="apron", min_px=5000),
                    dict(kind="pocket", id="pocket", on="apron", at=(0.15, -1.06), w=0.13, h=0.22, color="#6B4426"),
                    dict(kind="belt", z=-1.30, w=0.11, color="#4E3620", buckle="#C9A24A", over=0.045)]),
                headgear=dict(CHARS["cmd_olm"]["headgear"], id="rubber_goggles", rim_color="#3A3A40",
                              lens_color="#A8D8E8", metallic=0.1, strap="#3A3A40"),
                **{"props~": {"wrench": dict(color="#6C7482", handle="#B83A2A", top_dy=0.10)}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate("#6A4630"),
                    dict(kind="piping", color="#C9A24A", r=0.02, path=_FRONT),
                    dict(kind="bib", id="apron", color="#5A3A22", leather=True, w=0.26, top=-0.92, bottom=-2.0,
                         straps=True, over_last=True, detail="apron", min_px=4000),
                    dict(kind="pocket", id="pocket", on="apron", at=(0.15, -1.06), w=0.13, h=0.22, color="#4A3020")]),
                headgear=dict(CHARS["cmd_olm"]["headgear"], id="hud_goggles", lens_color="#FF9A40", lens_glow=0.6,
                              rim_color="#C9A24A"),
                **{"props~": {"wrench": None},
                   "props+": [dict(kind="cutter", pocket="pocket", len=0.62, ang=13, depth=0.32, top_dy=0.10,
                                   glow=1.5, signature=False)]}),
    },
    # ---------------------------------------------------------------- Vik
    "cmd_vik": {
        2: dict(costume=dict(base=dict(color="#6E4A28", rough=0.6, sheen=0.15), layers=[
                    dict(kind="cloak", id="cloak", color=_E("#4E6B3A", 2), z1=-0.64, gap=0.03, flare=0.10,
                         open=[(-1.9, 0.34), (-1.2, 0.26), (-0.85, 0.18), (-0.66, 0.14)]),
                    dict(kind="frogging", color="#E0AD45", z=(-0.88, -1.00, -1.12), w=0.16, t=0.024),
                    dict(kind="strap", id="strap", color="#4E3620", **{"from": (0.40, -0.72), "to": (-0.45, -1.6)},
                         w=0.07)]),
                headgear=dict(CHARS["cmd_vik"]["headgear"], id="hood_feather", color="#3C6A30"),
                **{"props~": {"raven": dict(variant="tube")},
                   "props+": [dict(kind="feather_pin", az=-58, el=40, len=0.30, w=0.06, color="#B8502A",
                                   dir=(-0.35, 0.55, 0.75))]}),
        3: dict(costume=dict(base=dict(color="#5E7A44", rough=0.85, sheen=0.2), layers=[
                    dict(kind="cloak", id="cloak", color="#5E7A44", camo=["#3E5A2E", "#8A9A5A", "#4E4A30"],
                         camo_scale=6.0, z1=-0.64, gap=0.03, flare=0.10,
                         open=[(-1.9, 0.34), (-1.2, 0.26), (-0.85, 0.18), (-0.66, 0.14)]),
                    dict(kind="strap", id="strap", color="#4E3620", **{"from": (0.40, -0.72), "to": (-0.45, -1.6)},
                         w=0.07)]),
                headgear=dict(CHARS["cmd_vik"]["headgear"], id="camo_hood", color="#5E7A44",
                              camo=["#3E5A2E", "#8A9A5A", "#4E4A30"], camo_scale=6.0),
                **{"props~": {"raven": dict(variant="clockwork", color="#2E3038", sheen="#5A5E6A"), "bow": None},
                   "props+": [dict(kind="binoculars", at=(0.10, -1.04), size=0.20)]}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#4E6B3A", 4), z0=-1.40, z1=-0.68),
                    dict(kind="pauldrons", color=_E("#4E6B3A", 4), painted=True, stripe="#5AE07A", stripe_emit=0.0,
                         n=1, spread=80, bands=[(92, 30)], detail="pauldrons", min_px=2000),
                    dict(kind="strip", id="glow", color="#5AE07A", emit=1.1, w=0.045, detail="glow", min_px=80,
                         path=[(-0.30, -0.80), (-0.32, -1.0), (-0.34, -1.2)])]),
                headgear=dict(CHARS["cmd_vik"]["headgear"], id="tech_hood", color=_E("#3E6234", 4),
                              extra=[dict(kind="visor", el=52, span=58, h=0.075, dh=6, glow=1.1, tint="#5AE07A",
                                          frame="#3A4150", off=0.035, detail="visor", min_px=150)]),
                **{"props~": {"raven": None, "bow": None},
                   "props+": [dict(kind="drone", x=-0.62, y=0.10, size=0.55, turn=-55, roll=10)]}),
    },
    # ---------------------------------------------------------------- Vega
    "cmd_vega": {
        2: dict(costume=dict(base=dict(color=_E("#3F4658", 2), rough=0.8, sheen=0.35), layers=[
                    dict(kind="collar", color="#F2F2F2", z=-0.66, h=0.13, out=0.018, flare=0.035, gap=0.05, thick=0.03),
                    dict(kind="lapels", color=_E("#3F4658", 2), shape=_LAPEL),
                    dict(kind="buttons", id="btn", at=[(-0.16, -0.96), (0.16, -0.96), (-0.15, -1.12), (0.15, -1.12)],
                         r=0.03, color="#C8CCD4"),
                    dict(kind="epaulettes", color="#C8CCD4", len=0.22, w=0.15, x=0.44, fringe=9, fringe_len=0.10)]),
                headgear=dict(kind="bicorne", id="bicorne", color="#2E3240", trim="#C8CCD4", rim_dz=0.06, tilt=-6,
                              crown=0.18, wall=0.30, wall_corner=0.35, corner=0.30, mid=0.0, crown_sub=1,
                              badge=dict(kind="disc", size=0.10, color="#C8CCD4", g=0.55))),
        3: dict(costume=dict(base=dict(color=_VEGA_E3, rough=0.85, sheen=0.25), layers=[
                    dict(kind="collar", color=_VEGA_E3, z=-0.66, h=0.10, out=0.018, flare=0.03, gap=0.05),
                    dict(kind="medal_bar", at=(-0.10, -0.72), colors=["#C8CCD4"], w=0.05, h=0.03, detail="tabs",
                         min_px=20),
                    dict(kind="medal_bar", at=(0.10, -0.72), colors=["#C8CCD4"], w=0.05, h=0.03, detail="tabs2",
                         min_px=20),
                    dict(kind="strap", id="sam_browne", color="#3A2A1E", w=0.07,
                         **{"from": (-0.42, -0.70), "to": (0.45, -1.6)}),
                    dict(kind="belt", z=-1.22, w=0.11, color="#3A2A1E", buckle="#C8CCD4", over=0.006)]),
                headgear=dict(kind="hat", id="beret", color="#3A4050", h=0.10, rim_dz=0.10, tilt=-4, side_tilt=-12,
                              profile=[(0.0, 1.0), (0.25, 1.22), (0.6, 1.30), (0.85, 1.12), (1.0, 0.0)],
                              badge=dict(kind="arrow", size=0.12, color="#C8CCD4", g=0.3, az=-25)),
                **{"props~": {"glasses": dict(tint="#E6EAF2")}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_VEGA_E4),
                    dict(kind="piping", color="#C8CCD4", r=0.02, path=_FRONT),
                    dict(kind="collar", color="#F2F2F2", z=-0.66, h=0.11, out=0.03, flare=0.03, gap=0.05)]),
                headgear=dict(kind="visor", id="hud_strip", on="head", el=-4, span=48, h=0.13, dh=6, off=0.11,
                              tint="#EEF6FF", frame="#C8CCD4", frame_r=0.008, line="#FFFFFF", line_emit=0.6,
                              detail="hud", min_px=300,
                              extra=[dict(kind="headset", sides=(1,), color="#3A4150", accent="#C8CCD4", mic=True)]),
                **{"props~": {"glasses": None}}),
    },
    # ---------------------------------------------------------------- Kort
    "cmd_kort": {
        2: dict(costume=dict(base=dict(color=_E("#5D6236", 2), rough=0.85, sheen=0.3), layers=[
                    dict(kind="placket", color="#4E5330", w=0.045, top=-0.80, x=0.0),
                    dict(kind="buttons", id="button", at=[(0.0, -0.98), (0.0, -1.16)], r=0.032, color="#B0803A"),
                    CHARS["cmd_kort"]["costume"]["layers"][2],
                    dict(kind="clasp", color="#B0803A", z=-0.90, x=0.075),
                    dict(kind="epaulettes", color="#B0803A", len=0.16, w=0.13, x=0.54, fringe=9, fringe_len=0.11,
                         fringe_r=0.013)]),
                headgear=dict(kind="hat", id="colpack", color="#5E4636", mat="fur", fur_dark="#4E3A2C",
                              fur_light="#7A5E4A", fur_crevice="#3A2A20", h=0.40, rim_dz=-0.01,
                              profile=[(0.0, 1.04), (0.5, 1.07), (1.0, 1.02)], top_dome=0.03, wall=0.05,
                              tassel=dict(color="#B0803A", az=60))),
        3: dict(costume=dict(base=dict(color=_KORT_E3, rough=0.9, sheen=0.25), layers=[
                    dict(kind="placket", color="#4E5330", w=0.045, top=-0.80, x=0.0),
                    dict(kind="buttons", id="button", at=[(0.0, -0.98), (0.0, -1.16)], r=0.032, color="#B0803A"),
                    dict(CHARS["cmd_kort"]["costume"]["layers"][2], r=1.0, t=0.14),
                    dict(kind="epaulettes", color="#B0803A", len=0.16, w=0.10, x=0.54, board=True, stripe="#E0B040"),
                    dict(kind="medal_bar", at=(-0.30, -1.06), colors=["#B0803A", "#C0452A", "#3E9BF0"], detail="medals",
                         min_px=60)]),
                headgear=dict(kind="shell", id="ushanka", color="#6B5040", mat="fur", fur_dark="#5A4232",
                              fur_light="#8A6E58", fur_crevice="#3A2A20", thick=0.07, lift=0.06, roll=0.035,
                              edge=[(0, 46), (40, 40), (80, 22), (110, 8), (180, -4)],
                              flaps=dict(up=True, len=0.22, w=0.20, mat="fur", color="#6B5040"),
                              badge=dict(kind="star", size=0.11, color="#B0803A", el=44))),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#5D6236", 4)),
                    dict(kind="piping", color="#B0803A", r=0.02, path=[(0.0, -0.95), (0.0, -1.2), (0.0, -1.6)]),
                    dict(kind="buttons", id="button", at=[(0.0, -0.98), (0.0, -1.16)], r=0.032, color="#B0803A"),
                    CHARS["cmd_kort"]["costume"]["layers"][2]]),
                headgear=dict(kind="headset", id="headset", sides=(-1,), color="#3A4150", accent="#B0803A", mic=True,
                              w=0.04, detail="headset", min_px=200),
                **{"props~": {"hourglass": dict(sand_glow=1.2, sand="#F0A040")}}),
    },
    # ---------------------------------------------------------------- Seir
    "cmd_seir": {
        2: dict(costume=dict(base=dict(color=_E("#175A72", 2), rough=0.85, sheen=0.3), layers=[
                    dict(kind="neckerchief", color="#F2F2F2", z=-0.64),
                    dict(kind="lapels", color="#F2F2F2",
                         shape=[(0.10, -0.66), (0.30, -0.70), (0.42, -0.80), (0.36, -0.86), (0.30, -1.02), (0.05, -1.20)]),
                    dict(kind="buttons", id="btn", r=0.036, color="#E8B23A",
                         at=[(-0.22, -0.98), (0.22, -0.98), (-0.20, -1.14), (0.20, -1.14)]),
                    dict(kind="epaulettes", color="#E8B23A", len=0.22, w=0.15, x=0.44, fringe=9, fringe_len=0.10)]),
                headgear=dict(CHARS["cmd_seir"]["headgear"], id="tricorn_gold", trim="#E8B23A", tape2=True,
                              badge=dict(kind="disc", size=0.10, color="#F2F2F2", g=0.5, metal=0.0, rough=0.5)),
                **{"props~": {"spyglass": dict(bands="#E8B23A")}}),
        3: dict(costume=dict(base=dict(color=_E("#175A72", 3), rough=0.85, sheen=0.25), layers=[
                    dict(kind="collar", color=_E("#175A72", 3), z=-0.64, h=0.08, out=0.004, flare=0.02, gap=0.06),
                    dict(kind="neckerchief", color="#F2F2F2", z=-0.64),
                    dict(kind="buttons", id="btn", r=0.034, color="#E8B23A",
                         at=[(-0.20, -0.98), (0.20, -0.98), (-0.19, -1.14), (0.19, -1.14)])]),
                headgear=dict(kind="hat", id="peaked_cap", color="#F2F2F2", h=0.30, rim_dz=0.01, tilt=-4,
                              profile=[(0.0, 1.0), (0.45, 1.02), (0.78, 1.24), (1.0, 1.26)], top_tilt=4,
                              band=dict(h=0.07, color="#134B5F"),
                              brim=dict(w=0.12, ang=-14, front=56, color="#2E2A2C", mat="leather"),
                              badge=dict(kind="wave_hex", size=0.12, color="#E8B23A", g=0.12, wave="#2F8FB0")),
                **{"props~": {"spyglass": dict(color="#C8CCD4", rough=0.22)},
                   "props+": [dict(kind="chevrons", style="ring", n=2, at=(0.82, 0.88), r=0.016, color="#E8B23A",
                                   detail="cuff_stripes", min_px=60)]}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#175A72", 4)),
                    dict(kind="piping", color="#F2F2F2", r=0.02, path=_FRONT),
                    dict(kind="pauldrons", color="#F2F2F2", painted=True, stripe=_E("#175A72", 4), n=1, spread=80,
                         bands=[(92, 30)], detail="pauldrons", min_px=2000)]),
                headgear=dict(kind="hat", id="hud_cap", color="#F2F2F2", mat="painted", h=0.30, rim_dz=0.01, tilt=-4,
                              profile=[(0.0, 1.0), (0.45, 1.02), (0.78, 1.24), (1.0, 1.26)], top_tilt=4,
                              band=dict(h=0.07, color=_E("#175A72", 4), mat="painted"),
                              brim=dict(w=0.12, ang=-14, front=56, color=_E("#175A72", 4), mat="painted"),
                              badge=dict(kind="wave_hex", size=0.12, color="#E8B23A", g=0.12, wave="#2F8FB0"),
                              extra=[dict(kind="visor", el=34, span=50, h=0.08, dh=6, tint="#E0F4FF", frame="#C8CCD4",
                                          off=0.12)]),
                **{"props~": {"spyglass": None},
                   "props+": [dict(CHARS["cmd_seir"]["props"][0], kind="rangefinder", len=0.62, glow_ring="#5AD8FF",
                                   glow=1.4)]}),
    },
})

ERA_LOOKS.update({
    # ---------------------------------------------------------------- Frey (no hat in any era: the flat top is her sign)
    "cmd_frey": {
        2: dict(costume=dict(base=dict(color=_E("#1F7040", 2), rough=0.85, sheen=0.3), layers=[
                    dict(kind="collar", color="#C8D0DA", metal=True, z=-0.66, h=0.07, out=0.03, flare=0.025),
                    _plate("#66707E", z0=-1.36, z1=-0.70, metallic=0.55, rough=0.3, thick=0.035),
                    dict(kind="pauldrons", color="#6C7684", stripe="#2E8A50", stripe_r=0.02, n=3, spread=88,
                         detail="pauldrons", min_px=10000)]),
                **{"props~": {"badge_relief": dict(at=(-0.26, -1.0))}}),
        3: dict(costume=dict(base=dict(color=_FREY_E3, rough=0.9, sheen=0.25), layers=[
                    dict(kind="collar", color=_FREY_E3, z=-0.64, h=0.08, out=0.004, flare=0.02),
                    _plate("#626C78", z0=-1.36, z1=-0.72, metallic=0.45, rough=0.45, thick=0.03),
                    dict(kind="strap", id="ystrap1", color="#4E3620", w=0.075,
                         **{"from": (-0.36, -0.70), "to": (-0.20, -1.5)}),
                    dict(kind="strap", id="ystrap2", color="#4E3620", w=0.075,
                         **{"from": (0.36, -0.70), "to": (0.20, -1.5)}),
                    dict(kind="pauldrons", color="#6C7684", stripe="#2E8A50", stripe_r=0.02, n=3, spread=88,
                         detail="pauldrons", min_px=10000)]),
                **{"props~": {"badge_relief": dict(at=(-0.27, -1.02))}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#1F7040", 4)),
                    dict(kind="collar", color="#C8D0DA", metal=True, z=-0.66, h=0.08, out=0.03, flare=0.025,
                         piping="#3AD07A", piping_r=0.02),
                    dict(kind="pauldrons", color="#C8D0DA", stripe="#3AD07A", stripe_emit=1.0, stripe_r=0.022, n=3,
                         spread=90, detail="pauldrons", min_px=10000)]),
                **{"props~": {"badge_relief": dict(at=(-0.26, -1.0), glow_rim="#5AE07A", glow=1.3)}}),
    },
    # ---------------------------------------------------------------- Irma
    "cmd_irma": {
        2: dict(costume=dict(base=dict(color="#40434F", rough=0.45, sheen=0.1), layers=[
                    dict(kind="collar", color=_E("#3A3C46", 2), z=-0.66, h=0.20, out=0.004, flare=0.07, gap=0.10,
                         thick=0.03, piping="#F08A24", piping_r=0.022),
                    dict(kind="frogging", color="#F08A24", z=(-0.86, -0.98, -1.10), w=0.22, t=0.026),
                    dict(kind="strap", id="strap", color="#2E2E34", **{"from": (-0.40, -0.72), "to": (0.45, -1.6)},
                         w=0.075)]),
                headgear=dict(CHARS["cmd_irma"]["headgear"], id="goggles_e2", rim_color="#E0AD45", style="rubber",
                              lens_color="#F0B060", metallic=0.5)),
        3: dict(costume=dict(base=dict(color="#3E3E42", rough=0.5, sheen=0.1), layers=[
                    dict(kind="collar", color="#5A4A3A", z=-0.66, h=0.20, out=-0.004, flare=0.12, gap=0.10, thick=0.04),
                    dict(kind="piping", color="#F08A24", r=0.021,
                         path=[(0.07, -0.70), (0.09, -0.92), (0.10, -1.2), (0.10, -1.75)]),
                    dict(kind="strap", id="strap", color="#2E2E34", **{"from": (-0.40, -0.72), "to": (0.45, -1.6)},
                         w=0.075)]),
                headgear=dict(kind="shell", id="tank_headset", color="#4A3E30", mat="leather", thick=0.05, roll=0.03,
                              edge=[(0, 50), (40, 44), (80, 26), (100, 6), (140, -2), (180, 2)], clear=0.02,
                              ribs=[-40, 0, 40],
                              cups=dict(r=0.11, d=0.06, color="#3A3226", mat="leather"),
                              extra=[dict(CHARS["cmd_irma"]["headgear"], el=46)])),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#3A3C46", 4)),
                    dict(kind="collar", color=_E("#3A3C46", 4), z=-0.66, h=0.20, out=0.02, flare=0.07, gap=0.10),
                    dict(kind="strip", id="glow1", color="#F08A24", emit=1.2, w=0.045, detail="glow", min_px=100,
                         path=[(0.08, -0.74), (0.10, -1.0), (0.11, -1.3), (0.12, -1.7)]),
                    dict(kind="strip", id="glow2", color="#F08A24", emit=1.2, w=0.045, detail="glow2", min_px=60,
                         path=[(-0.56, -0.78), (-0.50, -0.90), (-0.40, -0.98)]),
                    dict(kind="strap", id="strap", color="#2E2E34", **{"from": (-0.40, -0.72), "to": (0.45, -1.6)},
                         w=0.075)]),
                headgear=dict(kind="frame", id="helmet_frame", color=_E("#3A3C46", 4), mat="painted", el=32, w=0.07,
                              ring=True,
                              extra=[dict(kind="visor", el=56, span=55, h=0.07, dh=5, glow=1.2, tint="#F08A24",
                                          frame="#2E2E34", off=0.06, detail="visor", min_px=120)])),
    },
    # ---------------------------------------------------------------- Hawk
    "cmd_hawk": {
        # §7.6 E2 "небесно-голубой мундир": the sky is Hawk's accent; §7.7's hue lock on the main colour (the leather)
        # cannot hold for this era by §7.6's own design (reported)
        2: dict(costume=dict(base=dict(color="#8EC2EE", rough=0.8, sheen=0.35), layers=[
                    dict(kind="collar", color="#78AEDE", z=-0.64, h=0.08, out=0.004, flare=0.02, gap=0.06),
                    dict(kind="buttons", id="btn", at=[(-0.16, -0.98), (0.16, -0.98), (-0.15, -1.14), (0.15, -1.14)],
                         r=0.03, color="#E8B23A"),
                    dict(kind="epaulettes", color="#E8B23A", len=0.22, w=0.15, x=0.44, fringe=9, fringe_len=0.10)]),
                headgear=dict(CHARS["cmd_hawk"]["headgear"], id="flight_helmet_leather", color="#4A3020",
                              fur_roll=False)),
        3: dict(costume=dict(base=dict(color="#54402C", rough=0.5, sheen=0.1), layers=[
                    CHARS["cmd_hawk"]["costume"]["layers"][0],
                    dict(kind="strap", id="harness", color="#2E2218", w=0.07,
                         **{"from": (-0.36, -0.72), "to": (-0.20, -1.6)}),
                    dict(kind="medal_bar", at=(0.26, -1.06), colors=["#6FA8DC", "#E8B23A"], detail="medals",
                         min_px=40)]),
                headgear=dict(CHARS["cmd_hawk"]["headgear"], id="flight_helmet", color="#6A4428")),
        4: dict(costume=dict(base=dict(color="#A8C8E8", rough=0.6, sheen=0.2), layers=[
                    dict(kind="collar", color="#C8D6E4", z=-0.64, h=0.09, out=0.004, flare=0.02, gap=0.06),
                    dict(kind="strap", id="harness1", color="#3A4150", w=0.08,
                         **{"from": (-0.36, -0.72), "to": (-0.18, -1.6)}),
                    dict(kind="strap", id="harness2", color="#3A4150", w=0.08,
                         **{"from": (0.36, -0.72), "to": (0.18, -1.6)}),
                    dict(kind="belt", z=-1.30, w=0.10, color="#3A4150", buckle="#B9C7D6", over=0.006)]),
                headgear=dict(kind="shell", id="hard_helmet", color="#E8EEF4", mat="painted",
                              edge=[(0, 47), (35, 42), (60, 28), (78, 6), (92, -16), (120, -24), (180, -26)],
                              thick=0.06, roll=0.03, clear=0.03, cut_hair=True,
                              cups=dict(r=0.12, d=0.07, color="#6FA8DC", mat="painted"),
                              extra=[dict(kind="visor", el=56, span=60, h=0.09, dh=8, tint="#BFE0FF", frame="#6FA8DC",
                                          off=0.03)]),
                **{"props~": {"badge_relief": dict(glow_rim="#9FD0FF", glow=1.2)}}),
    },
    # ---------------------------------------------------------------- Vance (no hat in any era: the bun is her hat)
    "cmd_vance": {
        2: dict(costume=dict(base=dict(color=_E("#3A2262", 2), rough=0.8, sheen=0.4), layers=[
                    dict(kind="collar", color="#40266A", z=-0.64, h=0.07, out=0.004, flare=0.012, gap=0.08),
                    dict(kind="lapels", color="#5E3A9E", shape=[(0.08, -0.66), (0.24, -0.70), (0.33, -0.78),
                                                                (0.28, -0.84), (0.20, -0.98), (0.04, -1.14)]),
                    dict(kind="jabot", color="#F4F2F6", top=-0.66, tiers=3, r=0.12),
                    dict(kind="epaulettes", color="#C8CCD4", len=0.20, w=0.14, x=0.42, fringe=8, fringe_len=0.09),
                    dict(kind="aiguillette", color="#C8CCD4", n=3, r=0.022, **{"from": (0.42, -0.72), "to": (0.12, -0.96)},
                         detail="aiguillette", min_px=800)]),
                **{"props~": {"queen": dict(mat="metal", color="#C8CCD4")}}),
        3: dict(costume=dict(base=dict(color=_E("#3A2262", 3), rough=0.85, sheen=0.3), layers=[
                    dict(kind="collar", color=_E("#3A2262", 3), z=-0.64, h=0.09, out=0.004, flare=0.02, gap=0.06),
                    dict(kind="medal_bar", at=(-0.10, -0.70), colors=["#8E5BD0"], w=0.05, h=0.03, detail="tabs",
                         min_px=20),
                    dict(kind="medal_bar", at=(0.10, -0.70), colors=["#8E5BD0"], w=0.05, h=0.03, detail="tabs2",
                         min_px=20),
                    dict(kind="jabot", color="#F4F2F6", top=-0.68, tiers=2, r=0.10),
                    dict(kind="aiguillette", color="#C8CCD4", n=3, r=0.022, **{"from": (0.42, -0.72), "to": (0.12, -0.96)},
                         detail="aiguillette", min_px=800)]),
                # the brooch a little lower on the smaller jabot (at -0.70 it sat on the jabot top, facing up, and the queen
                # chain left its frame)
                **{"props~": {"queen": dict(mat="porcelain"), "brooch": dict(at=(0.0, -0.72))}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate(_E("#3A2262", 4)),
                    dict(kind="piping", color="#C8CCD4", r=0.018, path=_FRONT),
                    dict(kind="collar", color=_E("#3A2262", 4), z=-0.66, h=0.20, out=0.03, flare=0.05, gap=0.06,
                         piping="#C8CCD4", piping_r=0.014),
                    dict(kind="aiguillette", color="#C8CCD4", n=3, r=0.022, **{"from": (0.42, -0.72), "to": (0.12, -0.96)},
                         detail="aiguillette", min_px=800)]),
                headgear=dict(kind="earpiece", id="earpiece", color="#C8CCD4"),
                **{"props~": {"queen": dict(mat="holo", color="#B48CFF", emit=1.0), "brooch": dict(at=(0.0, -0.72))}}),
    },
    # ---------------------------------------------------------------- Rai
    "cmd_rai": {
        2: dict(costume=dict(base=dict(color="#EEF1F6", rough=0.85, sheen=0.3), layers=[
                    CHARS["cmd_rai"]["costume"]["layers"][0],
                    dict(kind="epaulettes", color="#2E4A80", len=0.20, w=0.14, x=0.46, fringe=8, fringe_len=0.09),
                    CHARS["cmd_rai"]["costume"]["layers"][2],
                    CHARS["cmd_rai"]["costume"]["layers"][3]]),
                **{"props~": {"banner": dict(finial="#E8C870")}}),
        3: dict(costume=dict(base=dict(color="#E6EAF0", rough=0.9, sheen=0.25), layers=[
                    CHARS["cmd_rai"]["costume"]["layers"][0],
                    dict(kind="epaulettes", color="#2E4A80", len=0.18, w=0.09, x=0.46, board=True, stripe="#1E4FA8"),
                    CHARS["cmd_rai"]["costume"]["layers"][2],
                    CHARS["cmd_rai"]["costume"]["layers"][3]]),
                **{"props~": {"banner": dict(color="#9AA4B0", staff_metal=0.5, staff_rough=0.3)}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate("#46566E", metallic=0.35),
                    dict(kind="strip", id="seam1", color="#3A8DFF", emit=1.4, w=0.042, detail="glow", min_px=80,
                         path=[(-0.40, -0.80), (-0.36, -1.0), (-0.34, -1.3)]),
                    CHARS["cmd_rai"]["costume"]["layers"][0],
                    dict(kind="pauldrons", color="#C8CCD4", stripe="#3A8DFF", stripe_emit=1.2, n=1, spread=82,
                         bands=[(92, 30)], detail="pauldrons", min_px=2000),
                    CHARS["cmd_rai"]["costume"]["layers"][2],
                    CHARS["cmd_rai"]["costume"]["layers"][3]]),
                headgear=dict(CHARS["cmd_rai"]["headgear"], emit=2.0),
                **{"props~": {"banner": dict(light=0.9, color="#C8CCD4", staff_metal=0.5, cloth="#3A70E0",
                                             alpha=0.7)}}),
    },
    # ---------------------------------------------------------------- the ruler (§7.10)
    "ruler": {
        # the coat a step LIGHTER than E1 (§7.7 says L* -5): the chestnut beard lies on it and needs |dL*| >= 15
        # (P-A5 beard-clothes; at -5 it measured 9.1); the hue stays locked (dE76 to E1 15.7)
        2: dict(costume=dict(base=dict(color="#5878E6", rough=0.85, sheen=0.35), layers=[
                    dict(kind="collar", color="#5878E6", z=-0.64, h=0.08, out=0.004, flare=0.016,
                         piping="#E8B23A", piping_r=0.016),
                    dict(kind="strap", id="sash", color="#F4F1EA", w=0.10, **{"from": (-0.44, -0.70), "to": (0.50, -1.6)}),
                    dict(kind="buttons", id="btn", at=[(-0.30, -0.90), (-0.31, -1.04), (-0.31, -1.18)], r=0.032,
                         color="#E8B23A"),
                    dict(kind="epaulettes", color="#E8B23A", len=0.22, w=0.15, x=0.46, fringe=9, fringe_len=0.10)]),
                **{"props~": {"chain": None}}),
        # E3 likewise lighter (the 0.20 olive mix of a saturated blue alone gives dE76 26.6 > 22 and a beard contrast
        # of 12.0): a blue-grey that keeps the hue
        3: dict(costume=dict(base=dict(color="#5676D6", rough=0.9, sheen=0.25), layers=[
                    dict(kind="collar", color="#E8B23A", z=-0.64, h=0.08, out=0.004, flare=0.02, metal=True),
                    dict(kind="buttons", id="btn", at=[(-0.30, -0.92), (-0.31, -1.08), (-0.31, -1.24)], r=0.032,
                         color="#E8B23A"),
                    dict(kind="epaulettes", color="#E8B23A", len=0.18, w=0.09, x=0.46, board=True, stripe="#2E5BD8"),
                    dict(kind="medal_bar", at=(0.30, -1.00), colors=["#E8B23A"], detail="medals", min_px=60,
                         medals=[dict(kind="star", size=0.11, color="#E8B23A", ribbon="#2E5BD8")])]),
                **{"props~": {"chain": None}}),
        4: dict(costume=dict(base=dict(color=_UNDER, rough=0.7, sheen=0.2), layers=[
                    _plate("#5A7CE8"),        # L* +12 not +6: the beard on the plate (P-A5 beard-clothes 12.7)
                    dict(kind="piping", color="#E8B23A", r=0.02, path=_FRONT),
                    dict(kind="pauldrons", color="#F2F4F8", painted=True, stripe="#E8B23A", n=1, spread=84,
                         bands=[(92, 30)], detail="pauldrons", min_px=2000),
                    dict(kind="strip", id="raivite", color="#3A8DFF", emit=1.0, w=0.045, detail="glow", min_px=80,
                         path=[(-0.62, -1.24), (-0.3, -1.27), (0.0, -1.28), (0.3, -1.27), (0.62, -1.24)])]),
                headgear=dict(CHARS["ruler"]["headgear"], emit=1.6),
                **{"props~": {"chain": None}}),
    },
})
