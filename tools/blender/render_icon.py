"""App icon in the «Raivon Soft» look (docs/art_direction.md §6): the player's capital — the DL4 castle of reference
frame 4 (residence_dl4_blue.glb: blue slate roofs, stone towers, the realm's eagle flags on its banners) — on one meadow hex
ringed by the player's border ribbon, against a warm sky. Readable at 48 px: the castle fills most of the icon, blue
roofs on a warm gold-to-sky ground, no thin parts.

Run: python3 tools/blender/render_icon.py OUT_DIR [--samples=N] [--res=PX] [--model=NAME] [--keep-raw]
     (defaults: 64 samples at 1600 px; the result goes through the import lock like any game asset)
Writes to OUT_DIR (the game's is game/assets/icon):
  icon_1024.png   1024×1024, opaque — iOS (export_presets icons/icon_1024x1024) and the store listings
  icon_512.png    512×512, opaque — the project icon (application/config/icon), Android's legacy launcher icon and
                  the Google Play store icon
  icon_fg_432.png Android adaptive foreground, transparent: the castle inside the 66 dp safe circle of the 108 dp
                  layer (FG_SAFE), so no launcher mask (circle, squircle, teardrop) cuts the banner or a tower
  icon_bg_432.png Android adaptive background: the warm sky alone
  icon_mono_432.png Android 13+ themed icon: the foreground in white, two-tone by alpha (roofs and banners solid,
                  walls and tile at MONO_BODY)
The model is rendered once on a transparent film (RES px, Cycles) and the PNGs are composed from it with Pillow.
"""
import math
import os
import sys
import tempfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import render_keyart as rk  # noqa: E402  (place() with the realm's flag on the banners, the border ribbon)

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
OPTS = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
OUT_DIR = os.path.abspath(ARGS[0]) if ARGS else os.path.abspath("icon_out")
SAMPLES = int(OPTS.get("samples", 64))
RES = int(OPTS.get("res", 1600))
MODEL = OPTS.get("model", "residence_dl4_blue")

# the soft light (§6.4, card_art.py's rig): a warm key sun with a 25° disc, a cool sky-blue world at AMBIENT of the
# key, AgX at its base contrast, then the map's grade
KEY_COLOR, SKY_FILL = "#fff1da", "#a9c1e8"
KEY_W, AMBIENT, SUN_ANGLE = 4.2, 0.8, 25.0
GRADE = (1.03, 1.04, 1.12)  # brightness, contrast, saturation (main.gd's Environment adjustments)
# the ground: the lawn and the tile's soil side of §6.3, flat (noise reads as dirt at 48 px)
LAWN, SOIL, SOIL_DEEP = "#7FB347", "#B58A5E", "#7E5A45"
# the warm sky (§6 «тёплый ключ, холодная заливка»): gold low behind the castle, the HUD crest's sky blue at the top
SKY_TOP, SKY_MID, SKY_LOW, SUN_GLOW = (0x8F, 0xCD, 0xF2), (0xFF, 0xE2, 0xA8), (0xFF, 0xC8, 0x7A), (0xFF, 0xF4, 0xD6)
FILL_1024 = 0.86     # the castle and hex span this share of the full-bleed icon's width (iOS masks ~ 10 % corners)
FG_SAFE = 31.0       # dp: the foreground's farthest opaque pixel from the centre (the safe circle is 33 of 108)
MONO_BODY = 0.5     # the themed icon's walls and tile, as a share of the roofs' opacity
CAM_ELEV, CAM_AZ = 30.0, 18.0  # degrees: a little lower than the map camera, turned so two faces of the keep show


def build():
    rk.reset_scene()
    # the tile: the lawn on top, the soil side darkening with depth (a deeper slab whose top hides inside the tile —
    # no coplanar faces, which Cycles renders black where they overlap)
    kit.hex_prism("tile", (0, 0, 0), 1.0, 0.22, kit.mat("lawn", LAWN, 0.95), kit.mat("soil", SOIL, 0.95), bevel=0.05)
    kit.hex_prism("tile_deep", (0, 0, -0.215), 0.985, 0.17, kit.mat("deep", SOIL_DEEP, 0.95),
                  kit.mat("deep_side", SOIL_DEEP, 0.95), bevel=0.04)
    rk.border_ribbon([(0, 0)])  # the player's border round the hex (§6.6)
    rk.place(MODEL, 0.0, 0.02, rz=0.0, s=1.0, z=0.004)
    # light
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.data.energy = KEY_W
    sun.data.color = kit.srgb(KEY_COLOR)
    sun.data.angle = math.radians(SUN_ANGLE)
    sun.rotation_euler = (math.radians(48), math.radians(-18), math.radians(-38))
    w = bpy.data.worlds.new("w")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*kit.srgb(SKY_FILL), 1)
    bg.inputs["Strength"].default_value = AMBIENT * KEY_W / math.pi
    # camera: orthographic, from the front (−Y, where the castle's gate and the keep's banner face)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.9  # the whole tile and the tower's tip with a margin (compose crops to the art)
    el, az = math.radians(CAM_ELEV), math.radians(CAM_AZ)
    d = 12.0
    cam.location = (d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el) + 0.45)
    cam.rotation_euler = (math.radians(90) - el, 0, az)
    bpy.context.scene.camera = cam
    return cam


def render(path):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = SAMPLES
    sc.cycles.seed = 0
    sc.cycles.use_denoising = True
    sc.render.resolution_x = RES
    sc.render.resolution_y = RES
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def grade(im):
    import numpy as np
    from PIL import Image
    a = im.getchannel("A")
    c = np.asarray(im.convert("RGB")).astype(np.float64) / 255.0
    b, k, sat = GRADE
    c = c * b
    c = 0.5 + (c - 0.5) * k
    m = c.mean(axis=2, keepdims=True)
    c = m + (c - m) * sat
    out = Image.fromarray(np.round(np.clip(c, 0.0, 1.0) * 255.0).astype(np.uint8), "RGB")
    out.putalpha(a)
    return out


def sky(n):
    """The warm sky, n×n: a vertical blend sky blue → warm cream → gold, and a soft sun glow behind the castle."""
    import numpy as np
    from PIL import Image
    y = (np.arange(n) + 0.5)[:, None] / n
    x = (np.arange(n) + 0.5)[None, :] / n

    def lerp(a, b, t):
        return np.array(a)[None, None, :] * (1 - t[..., None]) + np.array(b)[None, None, :] * t[..., None]
    t1 = np.clip(y / 0.62, 0, 1) ** 1.2 * np.ones_like(x)
    c = lerp(SKY_TOP, SKY_MID, t1)
    t2 = np.clip((y - 0.62) / 0.38, 0, 1) * np.ones_like(x)
    c = c * (1 - (y > 0.62)[..., None] * 1.0) + lerp(SKY_MID, SKY_LOW, t2) * ((y > 0.62)[..., None] * 1.0)
    r = np.hypot(x - 0.5, (y - 0.46) * 1.15)
    g = np.clip(1 - r / 0.42, 0, 1) ** 2 * 0.75
    c = c * (1 - g[..., None]) + np.array(SUN_GLOW)[None, None, :] * g[..., None]
    return Image.fromarray(np.clip(np.round(c), 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def compose(raw):
    """All five PNGs from the raw transparent render."""
    import numpy as np
    from PIL import Image
    layer = grade(Image.open(raw).convert("RGBA"))
    a = np.asarray(layer.getchannel("A"))
    ys, xs = np.nonzero(a > 8)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    art = layer.crop(box)
    aw, ah = art.size
    os.makedirs(OUT_DIR, exist_ok=True)

    # full-bleed square icons: the art FILL_1024 of the width (or 0.86 of the height), centred a touch low
    def square(n):
        k = min(n * FILL_1024 / aw, n * 0.88 / ah)
        im = art.resize((max(1, round(aw * k)), max(1, round(ah * k))), Image.LANCZOS)
        base = sky(n)
        base.alpha_composite(im, ((n - im.size[0]) // 2, int(n * 0.53 - im.size[1] / 2)))
        return base.convert("RGB")
    big = square(1024)
    big.save(os.path.join(OUT_DIR, "icon_1024.png"))
    big.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT_DIR, "icon_512.png"))

    # adaptive foreground: shrink the art until its farthest opaque pixel lies FG_SAFE dp from the centre
    n = 432
    centre = np.array([aw / 2, ah / 2])
    pts = np.stack([xs - box[0], ys - box[1]], axis=1)[::7].astype(np.float64)
    reach = np.hypot(*(pts - centre).T).max()  # in art px
    k = (FG_SAFE / 108.0 * n) / reach
    im = art.resize((max(1, round(aw * k)), max(1, round(ah * k))), Image.LANCZOS)
    fg = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    fg.alpha_composite(im, ((n - im.size[0]) // 2, (n - im.size[1]) // 2))
    fg.save(os.path.join(OUT_DIR, "icon_fg_432.png"))
    sky(n).convert("RGB").save(os.path.join(OUT_DIR, "icon_bg_432.png"))

    # themed (monochrome, Android 13+): the launcher tints the layer by its alpha alone, so the alpha carries a
    # two-tone drawing — the blue roofs and banners solid, the walls and the tile at MONO_BODY — and the castle still
    # reads as roofs over walls on a tile, not one blob
    fa = np.asarray(fg).astype(np.float64)
    alpha = fa[..., 3] / 255.0
    rgb = fa[..., :3] / np.maximum(alpha[..., None], 1e-3)  # un-premultiply the edge pixels before classifying
    blue = np.clip((rgb[..., 2] - rgb[..., 0] - 30.0) / 30.0, 0, 1)
    m = alpha * (MONO_BODY + (1 - MONO_BODY) * blue)
    mono = Image.new("RGBA", (n, n), (255, 255, 255, 0))
    mono.putalpha(Image.fromarray(np.round(np.clip(m, 0, 1) * 255).astype(np.uint8)))
    mono.save(os.path.join(OUT_DIR, "icon_mono_432.png"))
    print("icon ->", OUT_DIR, "art box", box, "fg scale %.3f" % k)


if __name__ == "__main__":
    build()
    raw = os.path.join(tempfile.mkdtemp(prefix="raivon_icon_"), "raw.png")
    render(raw)
    compose(raw)
    if "--keep-raw" in sys.argv:  # the transparent render, for QA
        import shutil
        shutil.copy(raw, os.path.join(OUT_DIR, "icon_raw.png"))
