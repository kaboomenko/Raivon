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
    "eye_fit": 1.18,           # the lens is sized up so its cap left visible by the curved face (brow ridge above,
                               # cheek below) measures sclera_h: calibrated on the ID pass (meta sclera_vis_H)
    "socket_depth": 0.022,     # a shallow seat: the socket brush flattens the face where the eye lens sits, in H
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
    # rim 2600 W and kicker 700 W, not 700 / 240: at those the silhouette's inner 4 px rim measured 37-47 % within
    # dL* 8 of plate B on the grey plates (P-A5 gate <= 35 %): the rim must clear the plate's L* 72-77, not land on it
    "rim": dict(size=1.2, color="#CFE0FF", energy=2600.0, loc=(2.3, 2.2, 1.2), target=(0.0, 0.0, -0.3)),
    "kick": dict(size=1.2, color="#FFE2C0", energy=700.0, loc=(-2.4, 2.0, 0.6), target=(0.0, 0.0, -0.3)),
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
