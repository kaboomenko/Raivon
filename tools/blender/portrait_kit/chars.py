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
        brows=dict(shape="straight", thick=0.075, color="#2A2020", arch=0.01, len=1.25, inner=-0.01, gap=0.04,
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
        hair=dict(style="flattop", color="#BE8E60", dark="#B08254", light="#BE8E60", crevice="#6A4428",
                  tip="#C89C6E", fleck="#C49466", side=0.008, front=0.04, front_ramp=0.09, top=0.03,
                  corner=0.07, ridge=0.16, ramp=0.10, lean=(35.0, 10.0), stubble=0.35, grain=(150, 150, 34),
                  fade_band=0.035, bristles_front=(0.0, 0.0, 0, 0.0, 0.0),
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
