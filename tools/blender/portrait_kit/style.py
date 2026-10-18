"""The numbers of docs/art_direction.md §7.3–§7.4 and §7.11 in one place (STYLE), the skin tones, the shared colours
and the part-ID colours of the QA pass. Every module of the kit reads its sizes from here; a character (chars.py)
overrides a value only inside the range §7.6 gives it.

Units: H is the head height from chin to crown without hair; the kit builds every head with H = HEAD_H kit units
(1.06, as the spike), so `STYLE["x"] * H` is a length in kit units. W (width at the cheekbones) = H * the
character's W/H ratio.
"""
HEAD_H = 1.06

STYLE = {
    # face layout (§7.3)
    "eye_line": 0.48,          # eye line above the chin, in H (0.46 Vik, Lira – 0.50 Kort)
    "eye_spacing": 0.34,       # centre to centre, in H (0.32–0.38)
    "sclera_h": 0.20,          # visible sclera height with the lids open, in H (0.18–0.22; never below 0.18)
    "sclera_w": 0.85,          # sclera width / height
    "sclera_protrude": 0.015,  # the eye stands out of the face plane, in H
    "eye_fit": 1.35,           # the lens is eye_fit x the visible sclera, so the curved face (brow ridge, cheek, the
                               # far eye's outer orbit) never clips inside the almond: only the almond (face.Almond) is
                               # built out of that lens — its geometry is clipped to the outline, which the lid shell and
                               # the lower rim cover — so the almond, not the face, is the outline; calibrated on the ID
                               # pass (meta eye_open_H = (open - low) x sclera_h)
    "rim": 0.010,              # the lower lid rim tube (radius, in H): every eye sits in a lid, calm included
    "rim_smile": 0.014,        # a smile's pushed-up lower lid, a little fuller
    "socket_depth": 0.022,     # a shallow seat: the socket brush flattens the face where the eye lens sits, in H
    "eye_pitch": -12.0,        # the eye lens faces a little up with the face under the eye (the cheek comes forward
                               # below it, its normal tilts up), in degrees about the lens x axis
    "socket_low": 0.016,       # the socket's lower half, deeper (in H), centred socket_low_z sclera heights under the
    "socket_low_z": 0.45,      # eye centre with a radius of socket_low_r sclera heights: the cheek apple stays clear of
    "socket_low_r": 0.55,      # the almond's lower curve
    "iris": 0.65,              # iris diameter / sclera height (0.60–0.70)
    "limbal": 0.12,            # dark limbal ring, share of the iris radius
    "pupil": 0.58,             # pupil / iris (0.48 angry – 0.62 smile)
    "pupil_smile": 0.62,
    "catch_big": 0.30,         # catchlight diameters / iris diameter; emission 6, no shadow
    "catch_small": 0.12,
    "catch_emit": 6.0,
    "lash_m": 0.026,           # lash line thickness, in H (men / women; 0.022–0.034)
    "lash_f": 0.032,
    "lash_flick": (0.06, 25.0),  # women: outer flick length (H) and angle (deg)
    "lid_open": 0.80,          # upper lid opening, calm (0.50 Kort – 0.85 Vik)
    "lid_shell": 1.10,         # lid shell = eye x 1.1
    "brow": 0.06,              # brow thickness at the inner third, in H (0.055–0.09)
    "brow_taper": 0.45,        # the outer end x 0.45
    "brow_len": 1.22,          # length / eye width (1.15–1.3)
    "brow_gap": 0.05,          # above the sclera, in H
    "nose_button": 0.095,      # button nose diameter, in H
    "nose_potato": 0.19,       # potato nose width, in W
    "nose_straight": 0.20,     # straight wedge length, in H
    "mouth_w": 0.29,           # closed mouth width, in H (0.26–0.32)
    "mouth_crease": 0.035,     # closed mouth crease >= 0.035 H
    "lower_lip_m": 0.030,
    "lower_lip_f": 0.036,
    "mouth_open": (0.34, 0.12),  # open D mouth width x height, in H
    "teeth_share": 0.30,       # upper teeth: share of the open mouth height
    "mouth_depth": 0.12,       # the open mouth's pocket: its back this far behind the face at the mouth line, in H
                               # (Lira's tuned pocket, now on every head: a fixed back plane made it 0.18 deep on
                               # Bram's broad face, where its walls went black — dark pixels past §7.4's 3 %)
    "ear_h": 0.23,             # C-shaped ears, height in H; stand out 0.05 H
    "ear_out": 0.05,
    "cheek_r": 0.12,           # cheek volumes r 0.12 H at +-0.19–0.24 H, 0.10–0.12 H below the eye line
    "cheek_x": 0.215,
    "cheek_below": 0.11,
    "cheek_smile": 0.055,      # a smile lifts them 0.04–0.07 H
    "blush_r": 0.09,
    "blush": {"m": 0.15, "f": 0.25, "young": 0.30},
    "female_jaw": 0.94,        # women: jaw 6 % narrower, nose smaller, brows <= 0.06 H, neck 0.36 W, shoulders -8 %
    "female_shoulders": 0.92,
    # marks (§7.3)
    "scar_w": 0.022, "freckle_d": 0.018, "freckle_n": (14, 18),
    # body (§7.3)
    "shoulders": 2.0,          # shoulder width, in W (1.75 Vik, Vance – 2.6 Frey)
    "neck_w": 0.55,            # neck width, in W (0.50–0.60; women 0.36 W per §7.3)
    "neck_show": 0.06,         # visible neck >= 0.06 H unless covered by design
    "layer_gap": 0.012,        # costume layers apart, in H
    "layer_min": 0.02,         # every layer >= 0.02 H thick, bevel 0.006 H
    "bevel": 0.006,
    "collar": 0.025,           # collars and lapels 0.025 H
    "attach_off": 0.012,       # buttons, badges, medals sit 0.012 H off the surface (ray along the normal)
    "strap_off": 0.006,        # straps shrinkwrapped 0.006 H off
    "strap_min": 0.02,         # straps >= 0.02 H thick
    # P-A7 contacts (§7.14)
    "contact_gap": 0.01,       # gap to the parent <= 0.01 H
    "contact_buried": 0.04,    # buried <= 0.04 H and <= 60 % of the points
    "contact_buried_share": 0.60,
}

SKIN = {"T1": "#F4B48E", "T2": "#F0A274", "T3": "#DE9A6C", "T4": "#C47A4E", "T5": "#9A5A38", "T6": "#7A4630"}
# The rig's warm key + sky fill + AgX Punchy take saturation out of skin (§7.0: 0.66 -> 0.30); the shader puts it
# back per tone so the lit skin keeps HSV S >= 0.35 (§7.4). Measured on the ID pass (lit cheek = brightest 30 % of
# the skin): T2 x1.15 -> S 0.40, T1 needs more, darker tones less.
SKIN_SAT = {"T1": 1.24, "T2": 1.15, "T3": 1.08, "T4": 1.05, "T5": 1.0, "T6": 1.0}
# Art director note (h) on the P2 fix sheet (2026-10-12): the skins read too saturated and orange under AgX Punchy
# (Olm and Kort sunburnt red-orange) — every skin's chroma down ~15-20 %, the cheeks rosy only on the blush. The
# saturation above (or a character's skin_sat) x k: the subsurface scattering amplifies albedo saturation, so k 0.94
# measured -17 to -27 % median C* on the rendered skin (k 0.90: -28 % and more); the warm hollow (AO) tint mixes
# `hollow` of #C0503A into the skin (0.35 before). The blush is painted after the chroma (face.skin_color), so it stays
# rosy. Two variants were tried and dropped: a shadow-side rolloff by the key's N.L (the darkest skin is the neck in
# the head's cast shadow, which N.L does not reach) and a lit-side hold (x1.22 where N.key >= 0.7, to keep §7.4's
# lit-cheek S >= 0.35): it turned the key-lit bald domes of Kort and Olm orange again. With k alone the lit cheeks of
# Lira, Olm, Vega, Seir, Hawk, Vance and Rai measure S 0.31-0.35 — §7.4's floor and note h conflict (main session).
SKIN_CHROMA = {"k": 0.94, "hollow": 0.30}

C = {
    "lash": "#2A1712", "pupil": "#1E1A24", "sclera": "#F7F3EE", "mouth_in": "#74282E", "teeth": "#FBF6EA",
    "tongue": "#E0606A", "blush": "#E5745E", "scar": "#D9787A", "freckle": "#C77B52", "shadow": "#5B5A8C",
    "floor": "#2A2A30", "seam": "#2A1D22",
    "gold": "#E8B23A", "brass": "#E0AD45", "silver": "#C8CCD4", "bronze": "#B0803A", "steel": "#B9C3CF",
}

# §7.11 light rig and render (kit units: skull centre at the origin, H = 1.06)
LIGHT = {
    # key 320 W, not §7.11's 220 W: at 220 W the lit skin of T1/T2 measured L* 68.5 (gate 70-82); the research
    # prototype's 320 W (research_chars) lands it at 70-71 with the rest of the rig unchanged
    "key": dict(size=2.5, color="#FFF1DA", energy=320.0, loc=(-2.4, -2.8, 1.6), target=(0.0, 0.0, -0.2)),
    # rim 5200 W and kicker 1300 W, not 700 / 240 (§7.11): the silhouette's inner 4 px rim must clear plate B's
    # L* 72-78, not land on it (P-A5 gate <= 35 % within dL* 8). P1 measured 37-47 % at 700 / 240 and set 2600 / 700;
    # P2's mid-value hoods, coats and domes (Vik's green hood, Kort's dome on the teal plate) still measured 36-48 %
    # at 2600 / 700, and 15-31 % at 5200 / 1300 — the edges go past the plate's band, the faces keep the key's L*
    "rim": dict(size=1.2, color="#CFE0FF", energy=5200.0, loc=(2.3, 2.2, 1.2), target=(0.0, 0.0, -0.3)),
    "kick": dict(size=1.2, color="#FFE2C0", energy=1300.0, loc=(-2.4, 2.0, 0.6), target=(0.0, 0.0, -0.3)),
    # world 1.45, not 1.05: §7.11 sets the sky fill for key : cheek shadow = 2.3 : 1 at a 220 W key; the 320 W key
    # needs 1.05 x 320 / 220 = 1.5 for the same ratio. At 1.05 the shadows went past the albedo floor (P-A5 "dark
    # <= 3 %": Bram 3.3 %, Lira 4.1 %); at 1.45 they measure 1.9 / 2.7 % and still read blue (#5B5A8C side, §7.4)
    "world": "#A9C1E8", "world_strength": 1.45, "reflect": "#F2ECE2", "reflect_share": 0.5,
}
RENDER = {
    "size": (512, 588), "samples": 64, "review_samples": 96, "adaptive": 0.01, "filter": 1.2, "bounces": 6,
    "transparent_bounces": 8, "clamp_indirect": 3.0, "look": "AgX - Punchy",
    "lens": 85.0, "sensor": 36.0,
    # framing solver on the 512x588 master (§7.11)
    "eye_y": 250.0, "eye_tol": 2.0, "head_x": 256.0, "head_tol": 12.0, "h_tol": 3.0, "skyline": 30.0,
    "skyline_headgear": 50.0, "side_band": 28.0, "side_rows": 412.0, "h_step": 4.0, "h_min": 256.0,
    # P-A6 "подбородок <= 0.65 h" (382 px of 588): a frame whose chin lands lower steps H_px down like the skyline does
    "chin_max": 381.0,
    # the face crop for the slots <= 72 px (--frame=face, §7.12): square, shares of its side. The head (chin-crown) at
    # 0.66 of the side, eye line at 0.50, centred; headgear keeps >= 0.02 of the side above it: the eye line moves down
    # (to 0.56) before the head steps smaller (0.02 a step, down to 0.56). Drawn cover-cropped in the game's slots, the
    # head (median of the 52 crops) grows +26 % in the 64 / 72 squares, +45 % in the 58x70 fan, +31 % in the army chip
    # over the bust's (T2, 2026-10-18); 8 of the 52 lowered the eye line (Vance's bun in every era, the E2 headgear of
    # Bram, Vega and Rai: at most 0.551), none needed the smaller head
    "face_h": 0.66, "face_eye_y": 0.50, "face_eye_max": 0.56, "face_sky": 0.02, "face_step": 0.02, "face_h_min": 0.56,
}

# Part-ID colours (flat emission pass for tools/qa_portraits): groups -> 8-bit sRGB. detail:<name> colours are
# assigned at build time from DETAIL_COLORS in order.
ID_COLORS = {"skin": (255, 0, 0), "hair": (0, 255, 0), "brow": (0, 0, 255), "sclera": (255, 255, 0),
             "iris": (255, 0, 255), "pupil": (0, 255, 255), "catch": (255, 255, 255), "lash": (128, 0, 0),
             "mouth": (0, 128, 0), "teeth": (0, 0, 128), "costume": (128, 128, 0), "metal": (128, 0, 128),
             "prop": (0, 128, 128), "signature": (255, 128, 0), "beard": (128, 255, 0), "lip": (255, 0, 128),
             "tongue": (255, 128, 128), "glass": (128, 128, 255), "nose": (255, 64, 0), "hat": (64, 255, 128),
             "eye": (255, 255, 160)}
COSTUME_COLORS = [(128, 128, 0), (160, 160, 0), (96, 96, 0), (128, 160, 32), (160, 128, 32), (96, 128, 0),
                  (128, 96, 0), (176, 144, 64), (112, 112, 48)]
DETAIL_COLORS = [(64, 0, 0), (0, 64, 0), (0, 0, 64), (64, 64, 0), (64, 0, 64), (0, 64, 64), (192, 64, 0),
                 (64, 192, 0), (0, 64, 192), (192, 0, 64), (64, 0, 192), (0, 192, 64), (192, 192, 64),
                 (64, 192, 192), (192, 64, 192), (96, 32, 160), (160, 96, 32), (32, 160, 96)]


# ------------------------------------------------------------------ colour maths (pure Python: chars.py uses it at
# import time, outside Blender's colour management)
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def lab_of(hx):
    """sRGB hex -> CIE Lab (D65), the formula of tools/qa_portraits/qa_common.srgb_to_lab."""
    h = hx.lstrip("#")
    r, g, b = (_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def hex_of_lab(L, a, b):
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def fi(t):
        return t ** 3 if t ** 3 > 216 / 24389 else (116 * t - 16) / (24389 / 27)
    x, y, z = fi(fx) * 0.95047, fi(fy), fi(fz) * 1.08883
    r = 3.2406 * x - 1.5372 * y - 0.4986 * z
    g = -0.9689 * x + 1.8758 * y + 0.0415 * z
    bb = 0.0557 * x - 0.2040 * y + 1.0570 * z
    return "#%02X%02X%02X" % tuple(int(round(_gam(c) * 255)) for c in (r, g, bb))


def de76(a, b):
    la, lb = lab_of(a), lab_of(b)
    return sum((p - q) ** 2 for p, q in zip(la, lb)) ** 0.5


def lab_adjust(hx, dL=0.0, chroma=1.0, mix=None, t=0.0):
    """A colour with its hue locked (§7.7): L* + dL, chroma x `chroma`, optionally first mixed (in Lab) with `mix`
    at `t` — the mix pulls the hue a little, the chroma step never turns it."""
    L, a, b = lab_of(hx)
    if mix:
        L2, a2, b2 = lab_of(mix)
        L, a, b = L + (L2 - L) * t, a + (a2 - a) * t, b + (b2 - b) * t
    return hex_of_lab(L + dL, a * chroma, b * chroma)


# §7.7 "Цвет по эпохам": the main colour of a costume by era (the hue locked; the old drift of every era into one khaki
# and one steel is gone): E2 rich wool (L* -5, saturation +5 %), E3 field (mix with #6E6A4E 0.20, saturation x0.85),
# E4 painted plates (L* +6, saturation x0.95; roughness 0.45, metallic 0.25 — ERA_PLATE) over an underlayer #3A4150.
ERA_FIELD = "#6E6A4E"
ERA_UNDER = "#3A4150"
ERA_PLATE = dict(rough=0.45, metal=0.25)


def era_color(hx, era):
    if era == 2:
        return lab_adjust(hx, dL=-5.0, chroma=1.05)
    if era == 3:
        return lab_adjust(hx, chroma=0.85, mix=ERA_FIELD, t=0.20)
    if era == 4:
        return lab_adjust(hx, dL=6.0, chroma=0.95)
    return hx.upper() if hx.startswith("#") else hx
