"""Shared helpers of the portrait checks (docs/art_direction.md §7.4, §7.12, §7.14). numpy + Pillow only.

Not a script: the other files of tools/qa_portraits import it (they put their own folder on sys.path, so they work
under `python3 -I`). Everything here is about the shipped RGBA PNGs and the kit's sidecars:
- the 150 names of §7.12 and the size each prefix must have (commanders 512×588, leaders and the ruler 256×294);
  `present(DIR)` lists the names a folder holds and the ones it misses, so every check runs on a partial folder;
- the plates the game draws behind a portrait: both rarity palettes (ui_kit.gd Kit.RARITY and the GDD 04 §15.4 set
  that §7.4 quotes), the leaders' state colours exactly as the game passes them to CmdPortrait.plate
  (map_view.team_look(state)["body"] = SoftPalette.soft_team(state colour).body; the Barons are always the war
  red #DD3A30), the ruler's SKY; and the two plate gradients (`current` = cmd_portrait.gd today, `B` = §7.4);
- sRGB → CIE Lab, the premultiplied Lanczos downscale the asset pipeline uses, 48 px alpha masks;
- the framing numbers of §7.14 P-A6 as fractions of the file's own size;
- the sidecars the kit writes with --sidecars: meta/<name>.json (landmarks in PNG px) and ids/<name>.png (+ .json,
  the colour of every part-ID group).
"""
import json
import os

import numpy as np
from PIL import Image

COMMANDERS = ["bram", "lira", "olm", "vik", "vega", "kort", "seir", "frey", "irma", "hawk", "vance", "rai"]
LEADERS = ["barons", "hamlets", "league", "order", "alvaria", "saren", "pack", "conclave", "veilmark", "lakes"]
ERAS = ["", "_e2", "_e3", "_e4"]
LEADER_MOODS = ["", "_angry", "_cunning", "_smile", "_tired"]
RARITY = {"bram": "common", "lira": "common", "olm": "common", "vik": "common", "vega": "rare", "kort": "rare",
          "seir": "rare", "frey": "rare", "irma": "epic", "hawk": "epic", "vance": "epic", "rai": "legendary"}

# The two rarity palettes the art is checked on (§7.4): the game's Kit.RARITY (ui_kit.gd, ui_style §3.2) and the set
# §7.4 quotes from 04 §15.4 / 10 (stone, teal, purple, copper).
PLATES_UI = {"common": "#A7AFBC", "rare": "#3E9BF0", "epic": "#A65BF2", "legendary": "#FF9A1F"}
PLATES_GDD = {"common": "#9AA3AD", "rare": "#1FB5AD", "epic": "#8E5BD0", "legendary": "#F08A24"}
PALETTES = {"ui": PLATES_UI, "gdd": PLATES_GDD}
# A leader's plate = what game_ui passes to CmdPortrait.plate: map_view.team_look(state)["body"], i.e.
# SoftPalette.soft_team(sim state colour).body (hsv with s clamped to 0.62-0.8 and v to 0.82-1.0); the Barons (and a
# state at war) get SoftPalette.ENEMY.body. State colours: sim/map_gen.gd, ring_gen.gd, ring_next.gd.
LEADER_PLATE = {"barons": "#DD3A30", "hamlets": "#4FD162", "league": "#32D1C2", "order": "#704FD1",
                "alvaria": "#E8873A", "saren": "#D95290", "pack": "#D1934F", "conclave": "#D18D4F",
                "veilmark": "#58D14F", "lakes": "#42BED1"}
SKY = "#8FCDF2"  # the ruler (HUD, profile) and the advisor: ui_style SKY_TOP
# Plate gradients, top -> bottom of the picture: Godot's Color.lightened(a) = c + (1 - c) a, darkened(a) = c (1 - a)
# on the sRGB values. "current" = cmd_portrait.gd _draw today; "B" = §7.4 (the P4 change), the gated one.
PLATE_MODES = {"current": (0.08, 0.42), "B": (0.18, 0.0)}

ASPECT = 256 / 294  # 0.8707: _leader_bust hard-codes 128x147; every crop of the game assumes it
SIZE = {"cmd": (512, 588), "ldr": (256, 294), "ruler": (256, 294)}

# §7.14 P-A6 framing, as fractions of the file's own width / height
EYE_Y = (0.425, 0.01)          # eye line y = 0.425 h +- 0.01
HEAD_X = (0.50, 0.025)         # head centre x = 0.50 w +- 0.025
CHIN_MAX = 0.65                # chin y <= 0.65 h
TOP_MIN = 0.051                # highest opaque row >= 0.051 h (30 px of 588)
TOP_MIN_HEADGEAR = 0.085       # the ruler's crown and leaders' headgear (50 px of 588)
SIDE_ROWS = 0.70               # above 0.70 h ...
SIDE_FREE = 0.055              # ... nothing within 0.055 w of either side
SIG_X = (0.06, 0.94)           # the signature box inside x 0.06-0.94 w
CHIP = (0.50, 0.40, 0.39)      # the army chip circle: centre (0.50 w, 0.40 h), radius 0.39 w; the head stays inside

# Part-ID colours of ids/<name>.png (the kit writes the real table to ids/<name>.json; this is the default)
ID_COLORS = {"skin": (255, 0, 0), "hair": (0, 255, 0), "brow": (0, 0, 255), "sclera": (255, 255, 0),
             "iris": (255, 0, 255), "pupil": (0, 255, 255), "catch": (255, 255, 255), "lash": (128, 0, 0),
             "mouth": (0, 128, 0), "teeth": (0, 0, 128), "costume": (128, 128, 0), "metal": (128, 0, 128),
             "prop": (0, 128, 128), "signature": (255, 128, 0), "beard": (128, 255, 0), "lip": (255, 0, 128),
             "tongue": (255, 128, 128), "glass": (128, 128, 255), "nose": (255, 64, 0), "hat": (64, 255, 128),
             "eye": (255, 255, 160)}


def all_names():
    """The 150 file names of §7.12, in a fixed order."""
    out = []
    for c in COMMANDERS:
        for e in ERAS:
            out += ["cmd_%s%s" % (c, e), "cmd_%s%s_smile" % (c, e)]
    out += ["ldr_%s%s" % (x, m) for x in LEADERS for m in LEADER_MOODS]
    out += ["ruler" + e for e in ERAS]
    return out


def kind(name):
    return "cmd" if name.startswith("cmd_") else ("ldr" if name.startswith("ldr_") else "ruler")


def present(d):
    """(names found in DIR, names missing) over the 150 names."""
    have, miss = [], []
    for n in all_names():
        (have if os.path.exists(os.path.join(d, n + ".png")) else miss).append(n)
    return have, miss


def report_missing(d, tag=""):
    have, miss = present(d)
    print("%sfiles: %d of 150 present, %d missing%s" % (tag, len(have), len(miss),
          (" (e.g. " + ", ".join(miss[:6]) + (" ..." if len(miss) > 6 else "") + ")") if miss else ""))
    return have, miss


def path_of(d, name):
    p = os.path.join(d, name + ".png")
    return p if os.path.exists(p) else None


def parse(argv):
    """(positional args, {option: value}) from --opt=value / --flag."""
    pos = [a for a in argv if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in argv if a.startswith("--"))
    return pos, opts


def plate_of(name, palette="ui"):
    """The base plate colour the game draws behind `name` (rarity colour, the state's colour or SKY)."""
    if name.startswith("cmd_"):
        return PALETTES[palette][RARITY[name.split("_")[1]]]
    if name.startswith("ldr_"):
        return LEADER_PLATE[name.split("_")[1]]
    return SKY


def load(path):
    im = Image.open(path).convert("RGBA")
    return np.asarray(im).astype(np.float32) / 255.0


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def srgb_to_lab(rgb):
    """rgb: (..., 3) sRGB 0..1 -> CIE Lab (D65)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    c = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de76(l1, l2):
    return np.sqrt(((np.asarray(l1) - np.asarray(l2)) ** 2).sum(axis=-1))


def hsv_s(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    return (mx - mn) / np.maximum(mx, 1e-6)


def lightened(c, a):
    return c + (1 - c) * a


def darkened(c, a):
    return c * (1 - a)


def plate_rows(c, n, mode="B"):
    """The plate's sRGB colour per row (n rows, top -> bottom) for base colour c (hex or rgb)."""
    if isinstance(c, str):
        c = hex_rgb(c)
    lt, dk = PLATE_MODES[mode]
    t = np.linspace(0, 1, n)[:, None]
    return lightened(c, lt) * (1 - t) + darkened(c, dk) * t


def plate_image(c, w, h, mode="B"):
    """The whole plate the game draws behind a w x h picture (sRGB, (h, w, 3)): the vertical gradient of `mode` and its
    halo behind the head, as cmd_portrait.gd draws them — "B" (§7.4): soft concentric circles, about +12 L* in total,
    no outline (white α 0.05 at radii 0.40 / 0.33 / 0.26 u around (0.5 w, 0.42 h), u = min(w, h)); "current": one white
    α 0.1 disc of radius 0.36 u (its thin darker outline is left out)."""
    rows = plate_rows(c, h, mode)
    img = np.broadcast_to(rows[:, None, :], (h, w, 3)).astype(np.float32).copy()
    yy, xx = np.mgrid[0:h, 0:w]
    u = min(w, h)
    d = np.sqrt((xx - 0.5 * w) ** 2 + (yy - 0.42 * h) ** 2)
    discs = ((0.40, 0.05), (0.33, 0.05), (0.26, 0.05)) if mode == "B" else ((0.36, 0.10),)
    for r, a in discs:
        m = (d <= r * u)[..., None]
        img = np.where(m, img * (1 - a) + a, img)
    return img


def resize_rgba(rgba, size_w, size_h=None):
    """Premultiplied Lanczos downscale (what the asset pipeline does), back to straight alpha."""
    h, w = rgba.shape[:2]
    nh = size_h or max(1, round(h * size_w / w))
    pm = rgba.astype(np.float32).copy()
    pm[..., :3] *= pm[..., 3:4]
    chans = [np.asarray(Image.fromarray(pm[..., i].astype(np.float32), "F").resize((size_w, nh), Image.LANCZOS))
             for i in range(4)]
    out = np.stack(chans, axis=-1)
    a = np.clip(out[..., 3:4], 0, 1)
    out[..., :3] = np.where(a > 1e-4, np.clip(out[..., :3] / np.maximum(a, 1e-4), 0, 1), 0)
    out[..., 3:4] = a
    return out


def over_plate(rgba, plate_rgb):
    """Composite straight RGBA over a flat colour or a per-row colour array (h, 3)."""
    p = np.asarray(plate_rgb, dtype=np.float32)
    if p.ndim == 2:
        p = p[:, None, :]
    return rgba[..., :3] * rgba[..., 3:4] + p * (1 - rgba[..., 3:4])


def alpha_mask(rgba, size_w):
    """Area-downscale the alpha to size_w px wide (aspect kept) and threshold at 0.5."""
    h, w = rgba.shape[:2]
    a = Image.fromarray((rgba[..., 3] * 255).astype(np.uint8))
    nh = max(1, round(h * size_w / w))
    a = a.resize((size_w, nh), Image.BOX)
    return np.asarray(a) > 127


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum()) / u if u else 1.0


def save_rgba(arr, path):
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA" if arr.shape[-1] == 4 else "RGB").save(path)


# ------------------------------------------------------------------ sidecars
def meta(d, name):
    p = os.path.join(d, "meta", name + ".json")
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def ids(d, name):
    """(group -> bool mask dict, table) from ids/<name>.png and its colour table, or (None, None); the "signature"
    mask comes from ids/<name>_sig.png when the kit wrote it."""
    p = os.path.join(d, "ids", name + ".png")
    if not os.path.exists(p):
        return None, None
    table = dict(ID_COLORS)
    jp = os.path.join(d, "ids", name + ".json")
    if os.path.exists(jp):
        with open(jp) as f:
            table = {k: tuple(v) for k, v in json.load(f)["colors"].items()}
    im = np.asarray(Image.open(p).convert("RGBA")).astype(np.int32)
    rgb, a = im[..., :3], im[..., 3] > 127
    keys = list(table)
    cols = np.array([table[k] for k in keys], dtype=np.int32)
    # nearest table colour per pixel (the flat pass is exact up to 8-bit encoding; a tolerance of 24 absorbs it)
    dist = ((rgb[..., None, :] - cols[None, None]) ** 2).sum(-1)
    near = dist.argmin(-1)
    ok = a & (dist.min(-1) <= 24 * 24 * 3)
    masks = {k: ok & (near == i) for i, k in enumerate(keys)}
    sp = os.path.join(d, "ids", name + "_sig.png")
    if os.path.exists(sp):  # the signature mask (its own pass: a signature part also has its ID group)
        masks["signature"] = np.asarray(Image.open(sp).convert("RGBA"))[..., 3] > 127
    return masks, table
