"""Every 3D UI icon (docs/ui_style.md §3.5): resources for the top bar, HUD buttons, tabs, window titles, rewards.
One camera, one key light (plus the cool rim light), the same chunky low-poly kit as the map models.

Run: python3 tools/blender/icon_assets.py [game/assets/ui] [name ...] [--raw=DIR]
- With no names, renders every icon in ICONS.
- coin, food, metal, raivite, oil, builder go to <out>/<name>.png (the HUD loads res://assets/ui/<name>.png);
  every other icon goes to <out>/icons/<name>.png.

Pipeline, per icon (reproducible, the rim is applied exactly once):
1. render 256 × 256, transparent, into a temp dir (--raw=DIR, default a fresh dir under the system temp — never the
   repo); the camera's ortho scale and shift are fitted to the model's silhouette, so every icon fills the same
   share of its square (FILL) and leaves room for the rim;
2. downscale to 128 × 128 (Lanczos);
3. tools/ui/ink_rim.py bakes the 3 px INK rim into the final file.
Portraits and card art (tools/blender/card_art.py) get no rim.
"""
import math
import os
import subprocess
import sys
import tempfile

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cone, cyl, mat, sphere  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
INK_RIM = os.path.join(HERE, "..", "ui", "ink_rim.py")
ROOT_ICONS = ("coin", "food", "metal", "raivite", "oil", "builder")  # these sit in assets/ui/, the rest in assets/ui/icons/
RAW, OUT_PX = 256, 128


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()


def gold():
    return mat("gold", "#e09a1a", 0.3, 1.0)


def coin():
    g = gold()
    dark = mat("gold_d", "#b8801c", 0.35, 1.0)
    c = cyl("coin", 0.5, 0.12, (0, 0, 0), g, 48, 0.03)
    c.rotation_euler.x = math.radians(72)
    rim = cyl("rim", 0.42, 0.135, (0, 0, 0), dark, 48, 0.01)
    rim.rotation_euler.x = math.radians(72)
    face = cyl("face", 0.38, 0.14, (0, 0, 0), g, 48, 0.01)
    face.rotation_euler.x = math.radians(72)
    # an embossed «R»: a stem, a bowl and a leg, raised on the face
    for (x, z, w, h, rot) in ((-0.1, 0.0, 0.07, 0.42, 0), (0.03, 0.12, 0.22, 0.07, 0), (0.03, 0.0, 0.2, 0.07, 0),
                              (0.12, 0.06, 0.07, 0.16, 0), (0.07, -0.13, 0.085, 0.28, -0.6)):
        b = box("R", (w, 0.05, h), (x, -0.085 + 0.33 * z, z), g, 0.01)  # follow the tilted face
        b.rotation_euler = (math.radians(-18), rot, 0)


def raivite():
    c = mat("raivite", "#0f48d0", 0.2, 0.0, "#1a5cff", 0.5)  # a strong glow washes the blue out under AgX
    c2 = mat("raivite2", "#2470f0", 0.15, 0.0, "#3a86ff", 0.7)
    for (x, z, h, r, tilt, m) in ((0, 0, 0.8, 0.16, 0, c2), (-0.2, -0.1, 0.5, 0.11, -0.4, c), (0.2, -0.1, 0.55, 0.12, 0.35, c),
                                 (0.08, -0.15, 0.35, 0.08, 0.6, c2)):
        o = cyl("crystal", r, h, (x, 0, z), m, 6, 0.0)
        o.rotation_euler.y = tilt
        tip = cone("tip", r, r * 1.6, (x + math.sin(tilt) * (h / 2 + r * 0.8), 0, z + math.cos(tilt) * (h / 2 + r * 0.8)), m, 6, 0.0)
        tip.rotation_euler.y = tilt
    sphere("base", 0.24, (0, 0, -0.38), mat("rock", "#5a5f6a", 0.8), (1.4, 1, 0.5), 2)


def builder():
    head = mat("head", "#9aa3ad", 0.25, 1.0)
    handle = mat("handle", "#8a5e36", 0.6)
    h = cyl("handle", 0.05, 0.9, (0, 0, -0.1), handle, 12, 0.01)
    h.rotation_euler.y = 0.6
    b = box("head", (0.5, 0.17, 0.17), (0.2, 0, 0.27), head, 0.03)
    b.rotation_euler.y = 0.6 - math.pi / 2 + math.pi / 2


def steel():
    return mat("steel_i", "#b8c2cf", 0.25, 1.0)


def castle_icon():
    st = mat("stone_i", "#c9c4ba", 0.7)
    roof = mat("roof_i", "#2f62c8", 0.45)
    box("wall", (0.7, 0.3, 0.32), (0, 0, -0.18), st, 0.02)
    for x in (-0.36, 0.36):
        cyl("tower", 0.13, 0.62, (x, 0, -0.04), st, 16, 0.01)
        cone("cone", 0.16, 0.34, (x, 0, 0.44), roof, 16, 0.0)
    cyl("keep", 0.16, 0.8, (0, 0.05, 0.05), st, 16, 0.01)
    cone("keep_cone", 0.2, 0.42, (0, 0.05, 0.66), roof, 16, 0.0)
    box("gate", (0.16, 0.05, 0.2), (0, -0.16, -0.24), mat("door_i", "#4a2f19", 0.7), 0.01)
    for k in range(4):
        box("merlon", (0.08, 0.32, 0.07), (-0.27 + k * 0.18, 0, 0.0), st, 0.005)


def helmet():
    s_ = steel()
    sphere("dome", 0.36, (0, 0, 0.05), mat("steel_h", "#9aa6b4", 0.35, 0.9), (1, 1, 1.05), 3)
    cyl("brim", 0.38, 0.06, (0, 0, -0.16), s_, 32, 0.02)
    box("nasal", (0.07, 0.06, 0.32), (0, -0.37, -0.05), s_, 0.01)
    box("crest", (0.62, 0.07, 0.14), (0, 0.0, 0.42), mat("crest", "#2f62c8", 0.6), 0.02)
    box("visor", (0.5, 0.05, 0.05), (0, -0.35, 0.0), mat("slot", "#1d1b1a", 0.8), 0.01)


def hammer():
    head = steel()
    handle = mat("handle_i", "#8a5e36", 0.6)
    h = cyl("handle", 0.06, 0.9, (0.0, 0, -0.08), handle, 12, 0.01)
    h.rotation_euler.y = 0.55
    b = box("head", (0.5, 0.2, 0.2), (0.235, 0, 0.31), head, 0.03)  # on the top end of the handle
    b.rotation_euler.y = 0.55 + math.pi / 2
    sc = box("scroll", (0.5, 0.06, 0.34), (0.18, 0.15, -0.2), mat("paper", "#e8dcb8", 0.8), 0.02)
    sc.rotation_euler.y = -0.3


def hands():
    """Diplomacy: a treaty scroll tied with a ribbon and a red wax seal."""
    paper = mat("paper_d", "#efe4c6", 0.8)
    r = cyl("roll", 0.16, 0.8, (0, 0, 0), paper, 24, 0.02)
    r.rotation_euler.y = math.pi / 2
    for sx in (-1, 1):
        e = cyl("knob", 0.07, 0.08, (sx * 0.43, 0, 0), mat("wood_d", "#6e4a2c", 0.6), 16, 0.01)
        e.rotation_euler.y = math.pi / 2
    cyl("ribbon", 0.165, 0.08, (0, 0, 0), mat("ribbon", "#2f62c8", 0.6), 24, 0.0).rotation_euler.y = math.pi / 2
    s2 = cyl("seal", 0.12, 0.05, (0.0, -0.17, -0.05), mat("wax", "#b5302a", 0.5), 20, 0.01)
    s2.rotation_euler.x = math.pi / 2
    for sx in (-1, 1):
        t = box("tail", (0.07, 0.02, 0.24), (sx * 0.05, -0.17, -0.22), mat("ribbon", "#2f62c8", 0.6), 0.005)
        t.rotation_euler.y = sx * 0.25


def trophy():
    g = gold()
    cyl("cup", 0.17, 0.42, (0, 0, 0.18), g, 32, 0.02, r2=0.32)
    cyl("stem", 0.06, 0.25, (0, 0, -0.15), g, 12, 0.0)
    cyl("base", 0.24, 0.08, (0, 0, -0.32), g, 24, 0.02)
    for sx in (-1, 1):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.025, location=(sx * 0.3, 0, 0.22),
                                         rotation=(math.pi / 2, 0, 0))
        bpy.context.active_object.data.materials.append(g)
    sphere("gem", 0.06, (0, -0.24, 0.18), mat("gem", "#2f62c8", 0.1), (1, 0.5, 1), 2)


def book():
    """Chronicle / Academy: an open leather-bound tome seen from the front — two cream page spreads with ink lines,
    a red cover showing round the pages, a gold-cornered spine and a blue ribbon bookmark."""
    cover = mat("cover", "#8a3b2a", 0.6)
    pages = mat("pages", "#efe4c6", 0.8)
    edge = mat("pages_e", "#d9caa0", 0.85)
    ink = mat("ink", "#6b5a44", 0.9)
    for sx in (-1, 1):
        c = box("cover", (0.5, 0.54, 0.04), (sx * 0.245, 0, -0.02), cover, 0.015)
        c.rotation_euler.y = sx * -0.16
        p = box("leaf", (0.44, 0.46, 0.07), (sx * 0.22, 0, 0.03), edge, 0.01)
        p.rotation_euler.y = sx * -0.16
        top = box("page", (0.43, 0.45, 0.012), (sx * 0.22, 0, 0.068), pages, 0.004)
        top.rotation_euler.y = sx * -0.16
        for k in range(5):  # ink lines on the page, following its tilt
            ln = box("line", (0.3 - (0.08 if k == 4 else 0.0), 0.02, 0.004), (sx * 0.22, -0.14 + k * 0.065, 0.077), ink, 0.0)
            ln.rotation_euler.y = sx * -0.16
        for (y, z0) in ((-0.25, 0), (0.25, 0)):
            g = box("corner", (0.07, 0.04, 0.045), (sx * 0.45, y * 0.98, -0.02 + 0.215 * math.sin(0.16)), gold(), 0.008)
            g.rotation_euler.y = sx * -0.16
    box("spine", (0.06, 0.52, 0.05), (0, 0, -0.035), mat("cover_d", "#6e2c1f", 0.6), 0.015)
    box("ribbon", (0.035, 0.5, 0.006), (0.02, -0.02, 0.066), mat("ribbon_b", "#2f62c8", 0.6), 0.0)
    rt = box("ribbon_tail", (0.035, 0.012, 0.15), (0.03, -0.27, 0.0), mat("ribbon_b", "#2f62c8", 0.6), 0.0)
    rt.rotation_euler.y = 0.2
    tilt = bpy.data.objects.new("tilt", None)  # tip the whole open book towards the camera about one pivot
    bpy.context.scene.collection.objects.link(tilt)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        o.parent = tilt
    tilt.rotation_euler.x = math.radians(52)


def mail():
    paper = mat("env", "#f0e6cc", 0.8)
    box("env", (0.8, 0.06, 0.52), (0, 0, 0), paper, 0.02)
    for sx in (-1, 1):
        f = box("flap", (0.47, 0.065, 0.02), (sx * 0.19, -0.035, 0.1), mat("env_d", "#d8caa4", 0.8), 0.005)
        f.rotation_euler.y = sx * 0.55
    cyl("seal", 0.1, 0.04, (0, -0.05, -0.02), mat("wax", "#b5302a", 0.5), 20, 0.01).rotation_euler.x = math.pi / 2


def gear():
    s_ = steel()
    g = cyl("gear", 0.36, 0.14, (0, 0, 0), s_, 32, 0.02)
    g.rotation_euler.x = math.pi / 2
    for k in range(8):
        a = k * math.tau / 8
        t = box("tooth", (0.13, 0.14, 0.13), (math.cos(a) * 0.42, 0, math.sin(a) * 0.42), s_, 0.01)
        t.rotation_euler.y = -a
    h = cyl("hole", 0.12, 0.16, (0, 0, 0), mat("hole", "#2b2d31", 0.6), 24, 0.0)
    h.rotation_euler.x = math.pi / 2


def target():
    """Focus on the front: crossed swords over a red target disc."""
    disc = cyl("disc", 0.4, 0.06, (0, 0.1, 0), mat("disc", "#c0392b", 0.5), 32, 0.02)
    disc.rotation_euler.x = math.pi / 2
    ring = cyl("ring", 0.26, 0.07, (0, 0.09, 0), mat("disc_w", "#f3efe6", 0.5), 32, 0.0)
    ring.rotation_euler.x = math.pi / 2
    core = cyl("core", 0.13, 0.08, (0, 0.08, 0), mat("disc", "#c0392b", 0.5), 24, 0.0)
    core.rotation_euler.x = math.pi / 2
    for sx in (-1, 1):
        b = box("blade", (0.07, 0.03, 0.8), (0, -0.05, 0.05), steel(), 0.01)
        b.rotation_euler.y = sx * 0.7
        g = box("guard", (0.26, 0.05, 0.05), (sx * -0.24, -0.06, -0.25), gold(), 0.01)
        g.rotation_euler.y = sx * 0.7


def pin():
    """Focus on the capital: a map pin with the royal crown."""
    red = mat("pin", "#2f62c8", 0.4)
    sphere("head", 0.3, (0, 0, 0.18), red, (1, 1, 1), 3)
    cone("point", 0.2, 0.42, (0, 0, -0.24), red, 24, 0.0).rotation_euler.x = math.pi
    g = gold()
    cyl("crown", 0.14, 0.1, (0, -0.26, 0.2), g, 16, 0.01).rotation_euler.x = math.pi / 2
    for k in range(3):
        cone("tine", 0.04, 0.1, (-0.08 + k * 0.08, -0.29, 0.3), g, 6, 0.0)


def fort():
    """Fortify: a stone wall span with merlons and a shield."""
    st = mat("stone_i", "#c9c4ba", 0.7)
    box("wall", (0.8, 0.26, 0.4), (0, 0, -0.1), st, 0.02)
    for k in range(4):
        box("merlon", (0.13, 0.28, 0.14), (-0.3 + k * 0.2, 0, 0.17), st, 0.01)
    sh = cyl("shield", 0.2, 0.06, (0, -0.16, -0.08), mat("shield", "#2f62c8", 0.5), 6, 0.01)
    sh.rotation_euler = (math.pi / 2, 0, 0)
    box("emblem", (0.06, 0.07, 0.2), (0, -0.2, -0.08), mat("disc_w", "#f3efe6", 0.5), 0.005)


def tower():
    """Build a watchtower: a round stone tower with a blue cone roof and a pennant."""
    st = mat("stone_i", "#c9c4ba", 0.7)
    cyl("body", 0.2, 0.7, (0, 0, -0.12), st, 20, 0.01)
    cyl("lip", 0.25, 0.08, (0, 0, 0.25), st, 20, 0.01)
    cone("roof", 0.28, 0.38, (0, 0, 0.48), mat("roof_i", "#2f62c8", 0.45), 20, 0.0)
    box("door", (0.1, 0.05, 0.16), (0, -0.2, -0.38), mat("door_i", "#4a2f19", 0.7), 0.01)
    box("window", (0.06, 0.05, 0.1), (0, -0.2, 0.05), mat("lit", "#ffd27a", 0.4, 0.0, "#ffb84a", 2.0), 0.0)
    cyl("pole", 0.012, 0.22, (0, 0, 0.75), mat("pole_i", "#d9d2c3", 0.5), 6, 0.0)
    box("pennant", (0.16, 0.01, 0.08), (0.08, 0, 0.8), mat("pennant_i", "#2f62c8", 0.5), 0.0)


def crate():
    """Warehouse: two stacked plank crates with iron corners and a sack."""
    wd = mat("crate_w", "#b07d47", 0.7)
    dk = mat("crate_d", "#6e4526", 0.7)
    iron = mat("iron_i", "#4a4d52", 0.5, 0.6)
    for (x, z, s_, r) in ((-0.18, -0.2, 0.46, 0.15), (0.2, -0.24, 0.38, -0.1), (0.0, 0.2, 0.36, 0.3)):
        b = box("crate", (s_, s_, s_), (x, 0, z), wd, 0.02)
        b.rotation_euler.z = r
        for dz in (-s_ * 0.3, s_ * 0.3):
            bb = box("plank", (s_ + 0.01, s_ + 0.01, 0.04), (x, 0, z + dz), dk, 0.005)
            bb.rotation_euler.z = r
        for dx in (-1, 1):
            c = box("corner", (0.05, s_ + 0.02, s_ + 0.02), (x + dx * s_ * 0.5 * math.cos(r), dx * s_ * 0.5 * math.sin(r), z), iron, 0.005)
            c.rotation_euler.z = r


def flask():
    """Infirmary: a round glass flask of green remedy with a cork and a herb sprig."""
    glass = mat("flask_g", "#9fe0b0", 0.05, 0.0, "#3fbf6a", 0.4)
    sphere("flask", 0.34, (0, 0, -0.14), glass, (1, 1, 1), 4)
    cyl("neck", 0.1, 0.32, (0, 0, 0.3), mat("flask_n", "#c8f0d4", 0.05), 20, 0.01)
    cyl("cork", 0.11, 0.12, (0, 0, 0.5), mat("cork", "#a8794a", 0.8), 20, 0.01)
    cyl("lip", 0.13, 0.04, (0, 0, 0.44), mat("flask_n", "#c8f0d4", 0.05), 20, 0.01)
    leaf = mat("leaf_i", "#4f9a3a", 0.6)
    for k in range(3):
        o = sphere("leaf", 0.08, (0.26 + k * 0.05, -0.25, 0.1 + k * 0.08), leaf, (0.4, 0.2, 1.0), 2)
        o.rotation_euler.y = -0.6


def cart():
    """Convoy yard: a two-wheeled cart in three-quarter view, a big spoked wheel, a load of tied sacks."""
    wd = mat("cart_w", "#a0713f", 0.7)
    dk = mat("cart_d", "#5e3d22", 0.7)
    iron = mat("iron_i", "#4a4d52", 0.5, 0.6)
    box("bed", (0.66, 0.4, 0.07), (0.04, 0, -0.06), wd, 0.015)
    for sy in (-1, 1):
        box("side", (0.66, 0.035, 0.15), (0.04, sy * 0.2, 0.03), wd, 0.01)
        box("rail", (0.68, 0.04, 0.03), (0.04, sy * 0.2, 0.115), dk, 0.005)
    for sx in (-1, 1):
        box("end", (0.035, 0.4, 0.15), (0.04 + sx * 0.33, 0, 0.03), wd, 0.01)
    for sy in (-1, 1):
        y = sy * 0.26
        rim = bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.03, location=(0.04, y, -0.2),
                                               major_segments=28, minor_segments=8)
        w = bpy.context.active_object
        w.rotation_euler.x = math.pi / 2
        w.data.materials.append(dk)
        for k in range(6):
            sp = box("spoke", (0.024, 0.024, 0.42), (0.04, y, -0.2), wd, 0.0)
            sp.rotation_euler.y = k * math.pi / 6
        h = cyl("hub", 0.055, 0.08, (0.04, y - sy * 0.01, -0.2), iron, 12, 0.0)
        h.rotation_euler.x = math.pi / 2
    for sy in (-1, 1):
        s_ = cyl("shaft", 0.022, 0.42, (-0.47, sy * 0.13, -0.13), dk, 8, 0.0)
        s_.rotation_euler.y = math.pi / 2 + 0.25
    sack = mat("sack_i", "#d8c08c", 0.9)
    tie = mat("tie_i", "#8a5e36", 0.8)
    for (x, y, z, r) in ((-0.15, 0.05, 0.13, 0.15), (0.13, -0.04, 0.13, 0.16), (0.0, 0.0, 0.3, 0.14)):
        sphere("sack", r, (x, y, z), sack, (1.0, 0.85, 0.8), 3)
        cyl("neck", r * 0.28, r * 0.5, (x, y, z + r * 0.85), sack, 8, 0.0)
        cyl("tie", r * 0.32, r * 0.14, (x, y, z + r * 0.72), tie, 8, 0.0)
    _tilt(rz=-28)


def stall():
    """Market: a stall under a striped blue-and-white awning with goods on the counter."""
    wd = mat("stall_w", "#a0713f", 0.7)
    for sx in (-1, 1):
        cyl("post", 0.03, 0.8, (sx * 0.38, 0, -0.05), wd, 8, 0.0)
    box("counter", (0.82, 0.3, 0.24), (0, 0, -0.32), wd, 0.02)
    for k, c in enumerate(("#2f62c8", "#f3efe6", "#2f62c8", "#f3efe6", "#2f62c8")):
        a = box("awn", (0.18, 0.42, 0.03), (-0.36 + k * 0.18, -0.04, 0.38), mat("awn" + c, c, 0.6), 0.005)
        a.rotation_euler.x = -0.35
    for k, c in enumerate(("#d8452f", "#e8b84a", "#6faa3c")):
        sphere("goods", 0.09, (-0.22 + k * 0.22, -0.02, -0.12), mat("goods" + c, c, 0.6), (1, 1, 0.85), 3)


def anchor():
    """Port: an iron anchor with a ring and a coil of rope."""
    iron = mat("anchor_i", "#5d6672", 0.35, 0.8)
    cyl("shank", 0.05, 0.9, (0, 0, 0.0), iron, 12, 0.01)
    t = cyl("stock", 0.04, 0.5, (0, 0, 0.36), iron, 12, 0.01)
    t.rotation_euler.y = math.pi / 2
    r = bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.03, location=(0, 0, 0.52))
    bpy.context.active_object.rotation_euler.x = math.pi / 2
    bpy.context.active_object.data.materials.append(iron)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.36, minor_radius=0.045, location=(0, 0, -0.08))
    arc = bpy.context.active_object
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(arc.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.02], context="VERTS")  # keep the lower arc only
    bm.to_mesh(arc.data)
    bm.free()
    arc.rotation_euler.x = math.pi / 2  # local y < 0 → below the centre
    arc.data.materials.append(iron)
    for sx in (-1, 1):
        c = cone("fluke", 0.09, 0.18, (sx * 0.36, 0, -0.02), iron, 12, 0.0)
        c.rotation_euler.y = sx * 0.6


def houses():
    """Quarters: three town houses of different heights with blue roofs and lit windows."""
    st = mat("plaster_i", "#e3d4b4", 0.7)
    roof = mat("roof_i", "#2f62c8", 0.45)
    lit = mat("lit", "#ffd27a", 0.4, 0.0, "#ffb84a", 2.0)
    for (x, h, w) in ((-0.32, 0.5, 0.3), (0.0, 0.72, 0.32), (0.32, 0.42, 0.28)):
        box("house", (w, 0.3, h), (x, 0, -0.45 + h / 2), st, 0.01)
        r = cone("roof", w * 0.78, 0.22, (x, 0, -0.45 + h + 0.1), roof, 4, 0.0)
        r.rotation_euler.z = math.pi / 4
        for k in range(int(h / 0.22)):
            box("win", (0.07, 0.03, 0.09), (x, -0.155, -0.33 + k * 0.2), lit, 0.0)


def orders():
    """Daily orders: a blue war flag with a white star on a gilt-tipped pole."""
    pole = mat("pole_i", "#8a5e36", 0.6)
    cyl("pole", 0.025, 1.0, (-0.28, 0, 0.0), pole, 10, 0.0)
    sphere("finial", 0.05, (-0.28, 0, 0.52), gold(), (1, 1, 1), 2)
    cloth = mat("flag_b", "#2f62c8", 0.6)
    # a waving cloth: three panels, each tilted a little, from the pole outwards
    for k, (x, ry, rz) in enumerate(((-0.14, 0.0, 0.12), (0.06, 0.0, -0.18), (0.24, 0.0, 0.14))):
        f = box("cloth", (0.21, 0.025, 0.46), (x, 0.0 + (0.02 if k == 1 else 0.0), 0.22), cloth, 0.01)
        f.rotation_euler.z = rz
    _star_mesh("star", 0.1, 0.042, 0.04, 0.22, -0.035, -0.05, mat("star_w", "#f6f3ea", 0.4))
    box("hem", (0.62, 0.03, 0.04), (0.05, 0, -0.02), gold(), 0.005)
    box("hem_t", (0.62, 0.03, 0.04), (0.05, 0, 0.46), gold(), 0.005)
    for z in (0.0, 0.44):  # gilt rings holding the cloth to the pole
        cyl("ring", 0.038, 0.03, (-0.28, 0, z), gold(), 12, 0.0)


def _tilt(rx=0.0, ry=0.0, rz=0.0):
    """Turn the whole icon about the origin (one pivot for every part, so the parts stay put relative to each other)."""
    e = bpy.data.objects.new("tilt", None)
    bpy.context.scene.collection.objects.link(e)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH" and o.parent is None]:
        o.parent = e
    e.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))


def hourglass():
    """Free timers: a brass-capped hourglass with golden sand running down."""
    wood = mat("hg_wood", "#7a4e2c", 0.6)
    glass = mat("hg_glass", "#cfe8f2", 0.05, 0.0, "#9fd0e8", 0.15)
    sand = mat("sand", "#f0b84a", 0.6)
    for z in (-0.42, 0.42):
        cyl("cap", 0.3, 0.07, (0, 0, z), wood, 24, 0.02)
        cyl("cap_rim", 0.27, 0.03, (0, 0, z - 0.05 if z > 0 else z + 0.05), gold(), 24, 0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("post", 0.025, 0.78, (sx * 0.22, sy * 0.06, 0), wood, 8, 0.0)
    cyl("bulb_top", 0.2, 0.36, (0, 0, 0.2), glass, 24, 0.0, r2=0.03)
    cyl("bulb_bot", 0.03, 0.36, (0, 0, -0.2), glass, 24, 0.0, r2=0.2)
    cyl("sand_top", 0.12, 0.12, (0, 0, 0.14), sand, 20, 0.0, r2=0.03)
    cone("sand_pile", 0.18, 0.14, (0, 0, -0.31), sand, 20, 0.0)
    cyl("stream", 0.008, 0.24, (0, 0, -0.08), sand, 6, 0.0)
    _tilt(ry=-12)


def key():
    """Royal case key: an ornate gold key with a ring bow and a toothed bit."""
    g = gold()
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.05, location=(-0.3, 0, 0.0),
                                     major_segments=32, minor_segments=10)
    bow = bpy.context.active_object
    bow.rotation_euler.x = math.pi / 2
    bow.data.materials.append(g)
    sphere("gem", 0.06, (-0.3, -0.02, 0.0), mat("gem", "#c0392b", 0.1), (1, 0.6, 1), 2)
    shaft = cyl("shaft", 0.04, 0.62, (0.15, 0, 0), g, 12, 0.0)
    shaft.rotation_euler.y = math.pi / 2
    cyl("collar", 0.06, 0.05, (-0.1, 0, 0), g, 12, 0.0).rotation_euler.y = math.pi / 2
    for (x, h) in ((0.33, 0.16), (0.4, 0.11), (0.25, 0.08)):
        box("bit", (0.05, 0.05, h), (x, 0, -h / 2 - 0.02), g, 0.005)
    _tilt(ry=30)


def frame():
    """Profile frame cosmetic: an ornate gold frame round a blue field with a white star."""
    g = gold()
    dark = mat("gold_d", "#b8801c", 0.35, 1.0)
    box("field", (0.6, 0.04, 0.72), (0, 0.02, 0), mat("card_b", "#2a4fa0", 0.5), 0.0)
    for (w, h, x, z) in ((0.8, 0.11, 0, 0.41), (0.8, 0.11, 0, -0.41), (0.11, 0.92, 0.355, 0), (0.11, 0.92, -0.355, 0)):
        box("rail", (w, 0.1, h), (x, 0, z), g, 0.03)
        box("bead", (w * 0.94 if w > h else 0.03, 0.11, h * 0.94 if h > w else 0.03), (x, -0.005, z), dark, 0.0)
    for sx in (-1, 1):
        for sz in (-1, 1):
            sphere("boss", 0.075, (sx * 0.355, -0.04, sz * 0.41), g, (1, 0.7, 1), 2)
    _star_mesh("star", 0.17, 0.07, 0.0, 0.0, -0.005, -0.03, mat("star_w", "#f6f3ea", 0.4))
    _tilt(rz=-12)


def crown():
    """Royal case: a gold crown with five pearl-tipped points, gems on the band, a blue velvet cap."""
    g = gold()
    dark = mat("gold_d", "#b8801c", 0.35, 1.0)
    sphere("cap", 0.3, (0, 0.02, -0.02), mat("velvet", "#2b4fa8", 0.85), (1.0, 1.0, 0.85), 3)
    cyl("band", 0.36, 0.2, (0, 0, -0.2), g, 40, 0.02)
    cyl("rim_lo", 0.375, 0.04, (0, 0, -0.29), dark, 40, 0.01)
    cyl("rim_hi", 0.37, 0.035, (0, 0, -0.11), dark, 40, 0.01)
    for k in range(10):
        a = math.radians(-90 + k * 36)
        x, y = math.cos(a) * 0.35, math.sin(a) * 0.35
        if k % 2 == 0:  # five tall points topped by pearls
            p = cone("point", 0.1, 0.34, (x, y, 0.06), g, 4, 0.0)
            p.rotation_euler.z = a + math.pi / 4
            sphere("pearl", 0.045, (x, y, 0.25), mat("pearl", "#f6f1e4", 0.25), (1, 1, 1), 2)
        else:  # small fleurons between them
            cone("fleuron", 0.055, 0.14, (x, y, -0.04), g, 4, 0.0).rotation_euler.z = a + math.pi / 4
    for k, c in enumerate(("#c0392b", "#2f62c8", "#2e9e5a", "#2f62c8", "#c0392b")):
        a = math.radians(-90 + (k - 2) * 30)
        sphere("gem", 0.05, (math.cos(a) * 0.37, math.sin(a) * 0.37, -0.2), mat("gem" + c, c, 0.1), (1, 0.6, 1.2), 2)
    sphere("orb", 0.06, (0, 0.02, 0.29), g, (1, 1, 1), 2)
    box("cross_v", (0.025, 0.025, 0.13), (0, 0.02, 0.38), g, 0.004)
    box("cross_h", (0.08, 0.025, 0.025), (0, 0.02, 0.39), g, 0.004)


def _star_mesh(name, r_out, r_in, cx, cz, y0, y1, material, rot_y=0.0):
    """A five-point star prism facing −Y (front face at y0, back at y1), centred at (cx, cz)."""
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = r_out if k % 2 == 0 else r_in
        pts.append((math.cos(a) * rr, math.sin(a) * rr))
    me = bpy.data.meshes.new(name)
    verts = [(x, y0, z) for (x, z) in pts] + [(x, y1, z) for (x, z) in pts]
    faces = [tuple(range(9, -1, -1)), tuple(range(10, 20))] + [(i, (i + 1) % 10, 10 + (i + 1) % 10, 10 + i) for i in range(10)]
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.location = (cx, 0, cz)
    o.rotation_euler.y = rot_y
    o.data.materials.append(material)
    return o


def cards():
    """Collection case: three fanned cards — blue backs with a gold border, the front one showing a gold star."""
    back = mat("card_b", "#2a4fa0", 0.5)
    face = mat("card_f", "#efe6cf", 0.7)
    trim = gold()
    for k, (a, x, y) in enumerate(((0.42, -0.2, 0.08), (0.0, 0.0, 0.04), (-0.42, 0.2, 0.0))):
        c = box("card", (0.42, 0.02, 0.6), (x, y, -0.02), back if k < 2 else face, 0.02)
        c.rotation_euler.y = a
        fr = box("frame", (0.44, 0.016, 0.62), (x, y + 0.006, -0.02), trim, 0.02)
        fr.rotation_euler.y = a
        if k < 2:
            d = box("diamond", (0.14, 0.03, 0.14), (x, y - 0.012, -0.02), trim, 0.01)
            d.rotation_euler = (0, a + math.pi / 4, 0)
    pic = box("pic", (0.32, 0.03, 0.4), (0.2, -0.016, 0.0), back, 0.01)
    pic.rotation_euler.y = -0.42
    _star_mesh("star", 0.13, 0.055, 0.2, 0.0, -0.034, -0.05, mat("star_w", "#f6f3ea", 0.4), -0.42)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        o.rotation_euler.x += math.radians(8)


def lock():
    """Locked reward: a brass padlock with a steel shackle and a dark keyhole."""
    brass = mat("brass", "#d4a03a", 0.3, 1.0)
    dark = mat("brass_d", "#9c7228", 0.35, 1.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.065, location=(0, 0, 0.12),
                                     major_segments=32, minor_segments=10)
    sh = bpy.context.active_object
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(sh.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -0.01], context="VERTS")  # the upper half only
    bm.to_mesh(sh.data)
    bm.free()
    sh.rotation_euler.x = math.pi / 2  # local +y → up
    sh.data.materials.append(steel())
    for sx in (-1, 1):
        cyl("leg", 0.065, 0.14, (sx * 0.22, 0, 0.06), steel(), 12, 0.0)
    box("body", (0.66, 0.26, 0.5), (0, 0, -0.22), brass, 0.06)
    box("band", (0.68, 0.27, 0.06), (0, 0, -0.04), dark, 0.02)
    box("band2", (0.68, 0.27, 0.06), (0, 0, -0.42), dark, 0.02)
    k = cyl("hole", 0.06, 0.04, (0, -0.13, -0.18), mat("hole", "#1d1b1a", 0.8), 16, 0.0)
    k.rotation_euler.x = math.pi / 2
    box("slot", (0.04, 0.04, 0.13), (0, -0.13, -0.27), mat("hole", "#1d1b1a", 0.8), 0.0)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        o.rotation_euler.z += math.radians(-14)


def _parallelogram(name, x0, x1, z0, z1, skew, y, material):
    """A flat stripe on a −Y-facing face: bottom edge x0..x1 at z0, top edge shifted by skew at z1."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(x0, y, z0), (x1, y, z0), (x1 + skew, y, z1), (x0 + skew, y, z1)], [], [(0, 1, 2, 3)])
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(material)
    return o


def ad():
    """Rewarded ad: a film clapperboard — a slate with a striped clapper flipped open and a gold play mark."""
    slate_m = mat("slate_i", "#2a2d33", 0.55)
    white = mat("disc_w", "#f3efe6", 0.5)
    box("slate", (0.8, 0.08, 0.52), (0, 0, -0.18), slate_m, 0.03)
    for zz in (0.0, -0.36):
        box("line", (0.66, 0.09, 0.018), (0, 0, zz), mat("chalk", "#9aa3ad", 0.6), 0.0)
    play = mat("play", "#f2b632", 0.3, 0.6)
    tri = cone("play", 0.15, 0.03, (0.02, -0.055, -0.18), play, 3, 0.0)
    tri.rotation_euler = (math.pi / 2, 0, 0)
    tri.rotation_euler.y = math.pi / 2

    def bar(z):
        objs = [box("bar", (0.8, 0.09, 0.1), (0, 0, z), white, 0.005)]
        for k in range(4):
            x0 = -0.38 + k * 0.2
            objs.append(_parallelogram("stripe", x0, x0 + 0.09, z - 0.05, z + 0.05, 0.06, -0.0462, slate_m))
        return objs

    bar(0.13)
    hinge = bpy.data.objects.new("hinge", None)
    bpy.context.scene.collection.objects.link(hinge)
    hinge.location = (-0.4, 0, 0.18)
    for o in bar(0.25):
        o.parent = hinge
        o.location.x += 0.4
        o.location.z -= 0.18
    hinge.rotation_euler.y = -0.36
    cyl("pin", 0.035, 0.12, (-0.4, 0, 0.18), steel(), 12, 0.0).rotation_euler.x = math.pi / 2


def medal():
    """War pass: a gold star medal on a blue-and-white ribbon (the season's military pass)."""
    _medal(gold(), mat("gold_d", "#b8801c", 0.35, 1.0))


def medal_bronze():
    """Chronicle tier 1: the medal in bronze."""
    _medal(mat("bronze", "#c98348", 0.32, 1.0), mat("bronze_d", "#8a4f24", 0.38, 1.0))


def medal_silver():
    """Chronicle tier 2: the medal in silver."""
    _medal(mat("silver", "#e3e9f1", 0.22, 1.0), mat("silver_d", "#9aa6b6", 0.3, 1.0))


def medal_gold():
    """Chronicle tier 3: the medal in bright gold with a gold ribbon edge."""
    _medal(mat("gold_b", "#f2b531", 0.25, 1.0), mat("gold_d", "#b8801c", 0.35, 1.0))


def _medal(g, disc_m):
    blue = mat("ribbon_b", "#2f62c8", 0.6)
    white = mat("disc_w", "#f3efe6", 0.5)
    for sx in (-1, 1):
        r = box("ribbon", (0.2, 0.03, 0.46), (sx * 0.1, 0.04, 0.24), blue, 0.005)
        r.rotation_euler.y = sx * -0.32
        s_ = box("stripe", (0.05, 0.035, 0.46), (sx * 0.1, 0.035, 0.24), white, 0.0)
        s_.rotation_euler.y = sx * -0.32
    box("clasp", (0.42, 0.06, 0.08), (0, 0.0, 0.03), g, 0.015)
    d = cyl("disc", 0.27, 0.06, (0, 0, -0.26), disc_m, 40, 0.02)
    d.rotation_euler.x = math.pi / 2
    star = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = 0.24 if k % 2 == 0 else 0.1
        star.append((math.cos(a) * rr, math.sin(a) * rr))
    me = bpy.data.meshes.new("star")
    verts = [(x, -0.04, z - 0.26) for (x, z) in star] + [(x, -0.08, z - 0.26) for (x, z) in star]
    faces = [tuple(range(9, -1, -1)), tuple(range(10, 20))] + [(i, (i + 1) % 10, 10 + (i + 1) % 10, 10 + i) for i in range(10)]
    me.from_pydata(verts, [], faces)
    me.update()
    so = bpy.data.objects.new("star", me)
    bpy.context.scene.collection.objects.link(so)
    so.data.materials.append(g)
    cyl("gem", 0.05, 0.03, (0, -0.095, -0.26), mat("gem", "#c0392b", 0.1), 16, 0.0).rotation_euler.x = math.pi / 2


# ------------------------------------------------------------------ helpers for the v2 icon set (docs/ui_style.md §3.5)


def brass():
    return mat("brass", "#d4a03a", 0.3, 1.0)


def _extrude(name, pts, depth, material, y=0.0, bevel=0.0):
    """A flat shape facing the camera (−Y): the outline pts [(x, z), …] at y, extruded back to y + depth."""
    import bmesh
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for (x, z) in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, depth, 0), verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    return kit._finish(o, material, bevel, 3, smooth=bevel > 0)


def _group(before, loc=(0, 0, 0), rot=(0, 0, 0), s=1.0):
    """Parent every top-level object made since `before` to one empty and place it (rot in degrees)."""
    e = bpy.data.objects.new("grp", None)
    bpy.context.scene.collection.objects.link(e)
    for o in list(bpy.context.scene.objects):
        if o not in before and o is not e and o.parent is None:
            o.parent = e
    e.location = loc
    e.rotation_euler = tuple(math.radians(a) for a in rot)
    e.scale = (s, s, s)
    return e


def _cut(o, keep):
    """Delete the vertices of o (in its local frame) for which keep(co) is False."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keep(v.co)], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    return o


def _torus(name, R, r, loc, material, rot=(0, 0, 0), keep=None, seg=32):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, location=loc, major_segments=seg, minor_segments=10)
    o = bpy.context.active_object
    o.name = name
    if keep:
        _cut(o, keep)
    o.rotation_euler = rot
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def _dome(name, r, loc, material, scale=(1, 1, 1)):
    """The upper half of a sphere (open below)."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    _cut(o, lambda co: co.z > -1e-4)
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def _face_cyl(name, r, h, loc, material, verts=32, bevel=0.01):
    """A disc facing the camera (axis along Y)."""
    c = cyl(name, r, h, loc, material, verts, bevel)
    c.rotation_euler.x = math.pi / 2
    return c


def _along(name, p0, p1, r0, r1, material, verts=16):
    """A frustum from p0 (radius r0) to p1 (radius r1), both points in the XZ plane at y = p[1]."""
    dx, dz = p1[0] - p0[0], p1[2] - p0[2]
    L = math.hypot(dx, dz)
    c = cyl(name, r0, L, ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, (p0[2] + p1[2]) / 2), material, verts, 0.0, r2=r1)
    c.rotation_euler.y = math.atan2(dx, dz)
    return c


# ------------------------------------------------------------------ the v2 set


def swords():
    """War / offensive: two crossed chunky swords — steel blades, brass guards, leather grips."""
    blade = mat("blade", "#d6dee8", 0.28, 0.75)
    edge = mat("blade_hi", "#f4f7fb", 0.2, 0.6)
    grip = mat("grip", "#7a3f26", 0.7)
    for k, (ang, y) in enumerate(((40, -0.05), (-40, 0.05))):
        before = set(bpy.context.scene.objects)
        w = 0.085
        _extrude("blade", [(-w, -0.3), (w, -0.3), (w, 0.44), (0, 0.62), (-w, 0.44)], 0.07, blade, y=-0.035, bevel=0.016)
        _extrude("fuller", [(-0.024, -0.24), (0.024, -0.24), (0.024, 0.4), (0, 0.48), (-0.024, 0.4)], 0.01, edge, y=-0.046)
        box("guard", (0.4, 0.11, 0.09), (0, 0, -0.33), brass(), 0.025)
        for sx in (-1, 1):
            sphere("guard_end", 0.065, (sx * 0.21, 0, -0.33), brass(), (1, 1, 1), 2)
        cyl("grip", 0.05, 0.22, (0, 0, -0.48), grip, 12, 0.012)
        sphere("pommel", 0.08, (0, 0, -0.63), brass(), (1, 1, 1), 2)
        _group(before, (0, y, 0.0), (0, ang, 0))


def shield():
    """Defence: a round brass-rimmed blue shield with a plain white star."""
    blue = mat("shield_b", "#3f86f0", 0.45)
    _face_cyl("rim", 0.47, 0.1, (0, 0.02, 0), brass(), 48, 0.025)
    _face_cyl("face", 0.4, 0.12, (0, 0, 0), blue, 48, 0.02)
    for k in range(10):
        a = k * math.tau / 10 + 0.3
        sphere("rivet", 0.03, (math.cos(a) * 0.435, -0.03, math.sin(a) * 0.435), brass(), (1, 0.7, 1), 2)
    _star_mesh("star", 0.26, 0.11, 0.0, 0.0, -0.085, -0.055, mat("star_w", "#f6f3ea", 0.4))
    _tilt(rx=-8, rz=-20)


def dove():
    """Peace: a white dove in flight with an olive sprig in its beak."""
    white = mat("dove", "#f7f6f0", 0.55)
    shade = mat("dove_far", "#d9dce6", 0.6)
    sphere("body", 0.21, (0, 0, -0.02), white, (1.55, 0.9, 0.95), 3)
    sphere("head", 0.135, (0.32, 0, 0.12), white, (1, 1, 1), 3)
    beak = cone("beak", 0.045, 0.12, (0.48, 0, 0.1), mat("beak", "#f0a030", 0.5), 12, 0.0)
    beak.rotation_euler.y = math.pi / 2 + 0.25
    sphere("eye", 0.026, (0.37, -0.115, 0.16), mat("eye", "#1b2140", 0.3), (1, 1, 1), 2)
    _extrude("tail", [(-0.24, 0.02), (-0.6, 0.14), (-0.66, 0.0), (-0.62, -0.14), (-0.26, -0.1)], 0.12, white, y=-0.06, bevel=0.025)
    wing = [(-0.2, 0.06), (0.16, 0.08), (0.08, 0.36), (-0.06, 0.6), (-0.2, 0.52), (-0.26, 0.62), (-0.4, 0.48), (-0.34, 0.3)]
    _extrude("wing_far", [(x + 0.08, z + 0.04) for (x, z) in wing], 0.07, shade, y=0.08, bevel=0.02)
    w = _extrude("wing", wing, 0.08, white, y=-0.2, bevel=0.022)
    w.rotation_euler.x = math.radians(-12)
    leaf = mat("olive_leaf", "#5f9e3c", 0.6)
    st = cyl("sprig", 0.013, 0.3, (0.52, -0.06, -0.02), mat("sprig", "#6b7a2a", 0.7), 6, 0.0)
    st.rotation_euler.y = 2.5
    for k, (x, z, a) in enumerate(((0.5, 0.02, 0.8), (0.56, -0.06, -0.6), (0.6, -0.12, 0.9), (0.66, -0.17, -0.4))):
        lf = sphere("leaf", 0.075, (x, -0.08, z), leaf, (0.45, 0.25, 1.0), 2)
        lf.rotation_euler.y = a
    sphere("olive", 0.04, (0.56, -0.1, -0.16), mat("olive", "#4f6b22", 0.4), (1, 1, 1.2), 2)


def treaty():
    """Peace treaty: an unrolled document between two rolls, lines of text, a red wax seal with ribbon tails."""
    paper = mat("paper_t", "#f6ead0", 0.8)
    roll = mat("paper_r", "#e6d4a8", 0.8)
    wood = mat("wood_d", "#6e4a2c", 0.6)
    box("sheet", (0.6, 0.03, 0.66), (0, 0, -0.02), paper, 0.01)
    for z, r in ((0.32, 0.08), (-0.36, 0.065)):
        c = cyl("roll", r, 0.72, (0, 0, z), roll, 24, 0.01)
        c.rotation_euler.y = math.pi / 2
        for sx in (-1, 1):
            k = cyl("knob", r * 0.7, 0.07, (sx * 0.39, 0, z), wood, 16, 0.01)
            k.rotation_euler.y = math.pi / 2
    ink = mat("ink_t", "#8a7a5e", 0.9)
    for k in range(5):
        box("line", (0.42 - (0.16 if k == 4 else 0.0) - (0.04 if k % 2 else 0), 0.01, 0.03), (-0.0 - (0.08 if k == 4 else 0), -0.02, 0.2 - k * 0.075), ink, 0.0)
    wax = mat("wax", "#c0362c", 0.45)
    ribbon = mat("ribbon", "#2f62c8", 0.6)
    for sx in (-1, 1):
        t = box("tail", (0.08, 0.02, 0.28), (0.14 + sx * 0.06, -0.035, -0.36), ribbon, 0.005)
        t.rotation_euler.y = sx * 0.3
    _face_cyl("seal", 0.13, 0.05, (0.14, -0.06, -0.2), wax, 24, 0.012)
    for k in range(9):
        a = k * math.tau / 9
        sphere("blob", 0.04, (0.14 + math.cos(a) * 0.12, -0.06, -0.2 + math.sin(a) * 0.12), wax, (1, 0.6, 1), 2)
    h = _face_cyl("hex", 0.07, 0.03, (0.14, -0.088, -0.2), mat("wax_l", "#e05a46", 0.4), 6, 0.006)
    _tilt(rx=6, rz=-10)


def seal():
    """Signed and sealed: a red wax disc with a raised hex emblem and two blue ribbon tails."""
    wax = mat("wax", "#c0362c", 0.45)
    ribbon = mat("ribbon", "#2f62c8", 0.6)
    for sx in (-1, 1):
        t = box("tail", (0.16, 0.03, 0.46), (sx * 0.13, 0.06, -0.36), ribbon, 0.01)
        t.rotation_euler.y = sx * 0.32
    _face_cyl("disc", 0.36, 0.1, (0, 0, 0), wax, 40, 0.02)
    for k in range(11):
        a = k * math.tau / 11 + 0.2
        sphere("blob", 0.09 + 0.02 * (k % 3 == 0), (math.cos(a) * 0.34, 0, math.sin(a) * 0.34), wax, (1, 0.6, 1), 2)
    _face_cyl("ring", 0.26, 0.12, (0, 0, 0), mat("wax_d", "#a32a22", 0.5), 40, 0.012)
    _face_cyl("ring_in", 0.22, 0.13, (0, 0, 0), wax, 40, 0.01)
    _face_cyl("hex", 0.15, 0.16, (0, 0, 0), mat("wax_l", "#e05a46", 0.4), 6, 0.02)
    _tilt(rx=8, rz=-14)


def handshake():
    """Pact / alliance: two chunky mitten hands clasped — a blue sleeve from the left, a red one from the right."""
    skin = mat("skin", "#f4c79a", 0.6)
    skin2 = mat("skin2", "#e9b583", 0.6)
    cuff = mat("cuff", "#f6f3ea", 0.6)
    for sx, sleeve_c in ((-1, "#3f86f0"), (1, "#dd3a30")):
        s = cyl("sleeve", 0.14, 0.42, (sx * 0.52, 0, -0.16), mat("sleeve" + sleeve_c, sleeve_c, 0.6), 20, 0.03)
        s.rotation_euler.y = math.pi / 2 + sx * 0.32
        c = cyl("cuff", 0.155, 0.08, (sx * 0.3, 0, -0.085), cuff, 20, 0.02)
        c.rotation_euler.y = math.pi / 2 + sx * 0.32
    sphere("palm_r", 0.17, (0.08, 0.06, 0.0), skin2, (1.35, 0.85, 0.8), 3)  # the far hand, behind
    sphere("palm_l", 0.17, (-0.08, -0.04, -0.01), skin, (1.35, 0.85, 0.8), 3)
    for k in range(3):  # the far hand's fingers wrapping round the near one
        sphere("finger", 0.055, (-0.16 + k * 0.1, -0.15, -0.1), skin2, (1.0, 0.8, 1.15), 2)
    th = sphere("thumb_l", 0.06, (0.08, -0.12, 0.12), skin, (1.7, 0.85, 0.85), 2)
    th.rotation_euler.y = -0.35
    th2 = sphere("thumb_r", 0.055, (-0.02, 0.0, 0.15), skin2, (1.6, 0.85, 0.85), 2)
    th2.rotation_euler.y = 0.35


def globe():
    """The world (World tab, «scales» and «globe»): a blue and green globe on a brass meridian and stand."""
    sea = mat("sea_i", "#2f7fe0", 0.3)
    land = mat("land_i", "#58b03a", 0.6)
    sphere("globe", 0.4, (0, 0, 0.06), sea, (1, 1, 1), 4)
    for (x, y, z, r) in ((-0.15, -0.28, 0.22, 0.15), (0.17, -0.31, -0.03, 0.13), (-0.06, -0.35, -0.16, 0.1),
                         (0.24, -0.2, 0.26, 0.11), (-0.3, -0.18, -0.02, 0.09)):
        sphere("land", r, (x, y, z), land, (1.2, 0.5, 1), 2)
    _torus("meridian", 0.47, 0.032, (0, 0, 0.06), brass(), (math.pi / 2, math.radians(-23), 0),
           keep=lambda co: co.x < 0.06)
    cyl("stem", 0.045, 0.14, (0, 0, -0.44), brass(), 12, 0.0)
    cyl("base", 0.24, 0.07, (0, 0, -0.53), brass(), 32, 0.02)
    cyl("base_top", 0.16, 0.04, (0, 0, -0.48), mat("gold_d", "#b8801c", 0.35, 1.0), 32, 0.01)


def horn():
    """Alarm (diplomacy threat): a curved brass war horn with dark bands and a red cord."""
    band = mat("horn_band", "#8a5a1c", 0.4, 0.9)
    cx, cz, R = 0.0, 0.08, 0.38
    a0, a1, n = math.radians(195), math.radians(338), 10
    pts = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        pts.append((cx + math.cos(a) * R, 0, cz + math.sin(a) * R))
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        _along("seg", pts[i], pts[i + 1], 0.035 + 0.075 * t0 ** 1.4, 0.035 + 0.075 * t1 ** 1.4, brass(), 18)
        if i in (3, 7):
            _along("band", pts[i], (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * 0.3, 0, pts[i][2] + (pts[i + 1][2] - pts[i][2]) * 0.3),
                   0.045 + 0.08 * t0 ** 1.4, 0.045 + 0.08 * t0 ** 1.4, band, 18)
    end, dirx, dirz = pts[-1], math.cos(a1 + math.pi / 2), math.sin(a1 + math.pi / 2)
    tip = (end[0] + dirx * 0.16, 0, end[2] + dirz * 0.16)
    _along("bell", end, tip, 0.11, 0.21, brass(), 28)
    inner = _along("bell_in", (tip[0] - dirx * 0.01, 0, tip[2] - dirz * 0.01), (tip[0] + dirx * 0.005, 0, tip[2] + dirz * 0.005),
                   0.17, 0.17, mat("horn_in", "#5a3a12", 0.6), 24)
    st = pts[0]
    bx, bz = math.sin(a0), -math.cos(a0)  # backwards from the first segment
    _along("mouth", st, (st[0] + bx * 0.1, 0, st[2] + bz * 0.1), 0.05, 0.035, band, 12)
    cord = mat("cord", "#c0362c", 0.7)
    _torus("cord", 0.3, 0.018, (0.0, -0.02, 0.02), cord, (math.pi / 2, 0, 0), keep=lambda co: co.y < 0.02)
    sphere("tassel", 0.05, (0.0, -0.03, -0.3), cord, (0.8, 0.8, 1.4), 2)
    _tilt(rz=-12)


def gift():
    """A present: a red box with a blue ribbon and a bow."""
    red = mat("gift", "#e04a3e", 0.5)
    red_l = mat("gift_l", "#ee5c4f", 0.5)
    rib = mat("gift_rib", "#3e8ff0", 0.45)
    box("box", (0.6, 0.6, 0.46), (0, 0, -0.16), red, 0.02)
    box("lid", (0.68, 0.68, 0.14), (0, 0, 0.12), red_l, 0.025)
    box("band_x", (0.14, 0.7, 0.62), (0, 0, -0.06), rib, 0.01)
    box("band_y", (0.7, 0.14, 0.62), (0, 0, -0.06), rib, 0.01)
    for sx in (-1, 1):
        lp = _torus("loop", 0.12, 0.045, (sx * 0.11, 0, 0.3), rib, (math.pi / 2, sx * 0.55, 0), seg=24)
        lp.scale = (1.0, 0.6, 1.0)
    sphere("knot", 0.07, (0, 0, 0.24), rib, (1, 1, 0.9), 2)
    _tilt(rx=22, rz=-32)


def coins():
    """A stack of three gold coins, the top one showing the embossed R."""
    g = gold()
    dark = mat("gold_d", "#b8801c", 0.35, 1.0)
    for k, (x, y) in enumerate(((0.02, 0.0), (-0.05, 0.02), (0.04, -0.02))):
        z = -0.2 + k * 0.13
        cyl("coin", 0.4, 0.12, (x, y, z), g, 48, 0.03)
        cyl("rim", 0.33, 0.13, (x, y, z), dark, 48, 0.0)
        cyl("face", 0.3, 0.135, (x, y, z), g, 48, 0.0)
    x, y, z = 0.04, -0.02, 0.06 + 0.075
    for (bx, by, w, h, rot) in ((-0.1, 0.0, 0.07, 0.42, 0), (0.03, 0.12, 0.22, 0.07, 0), (0.03, 0.0, 0.2, 0.07, 0),
                                (0.12, 0.06, 0.07, 0.16, 0), (0.07, -0.13, 0.085, 0.28, -0.6)):
        b = box("R", (w, h, 0.04), (x + bx, y + by, z), g, 0.01)
        b.rotation_euler.z = -rot
    _tilt(rx=48)


def lightning():
    """Speed-up: a chunky yellow lightning bolt."""
    y_ = mat("bolt", "#ffc531", 0.35, 0.0, "#ffb000", 0.25)
    pts = [(-0.02, 0.62), (0.3, 0.62), (0.08, 0.14), (0.3, 0.14), (-0.22, -0.66), (-0.04, -0.04), (-0.27, -0.04)]
    _extrude("bolt", pts, 0.16, y_, y=-0.08, bevel=0.035)
    _tilt(rz=-22)


def barrel():
    """Oil (HUD resource and «barrel»): a green oil drum with brass hoops and black oil dripping over the rim."""
    green = mat("drum", "#2f8a4c", 0.45, 0.25)
    lid = mat("drum_lid", "#287540", 0.5, 0.25)
    oil_m = mat("oil_k", "#14161c", 0.08, 0.0)

    def r_at(z):
        return 0.34 - 0.05 * abs(z) / 0.42

    cyl("drum_lo", 0.29, 0.42, (0, 0, -0.21), green, 32, 0.0, r2=0.34)
    cyl("drum_hi", 0.34, 0.42, (0, 0, 0.21), green, 32, 0.0, r2=0.29)
    for z in (-0.38, -0.13, 0.13, 0.38):
        cyl("hoop", r_at(z) + 0.014, 0.05, (0, 0, z), brass(), 32, 0.01)
    cyl("lid", 0.285, 0.03, (0, 0, 0.42), lid, 32, 0.01)
    cyl("bung", 0.05, 0.04, (0.13, 0.06, 0.445), brass(), 12, 0.01)
    sphere("pool", 0.13, (-0.07, -0.06, 0.435), oil_m, (1.5, 1.1, 0.12), 3)
    sphere("drip_lip", 0.06, (-0.1, -0.27, 0.41), oil_m, (1.2, 0.8, 0.6), 2)
    sphere("drip", 0.05, (-0.1, -0.305, 0.28), oil_m, (0.8, 0.55, 2.4), 2)
    sphere("drop", 0.055, (-0.1, -0.31, 0.12), oil_m, (1, 0.8, 1.15), 2)
    _tilt(rx=16, rz=-14)


def calendar():
    """Daily calendar: a block of pages with a red top band, two rings and a grid of days, one ringed."""
    page = mat("cal_page", "#fbf6ea", 0.7)
    edge = mat("cal_edge", "#e3d6b6", 0.8)
    red = mat("cal_red", "#e04a3e", 0.5)
    box("pages", (0.72, 0.14, 0.72), (0, 0.03, -0.04), edge, 0.02)
    box("page", (0.7, 0.04, 0.7), (0, -0.04, -0.03), page, 0.015)
    box("band", (0.74, 0.16, 0.22), (0, 0.0, 0.32), red, 0.025)
    for sx in (-1, 1):
        _torus("ring", 0.075, 0.022, (sx * 0.18, 0.0, 0.44), steel(), (0, math.pi / 2, 0), seg=20)
    cell = mat("cal_cell", "#c9d3e6", 0.7)
    for r in range(3):
        for c in range(4):
            box("day", (0.11, 0.012, 0.1), (-0.225 + c * 0.15, -0.065, 0.1 - r * 0.15), cell, 0.0)
    _torus("mark", 0.08, 0.018, (0.075, -0.075, -0.05), red, (math.pi / 2, 0, 0), seg=20)
    _tilt(rx=8, rz=-14)


def charter():
    """Royal charter (the subscription): a rolled scroll tied with red cord, a gold seal with a crown on it."""
    paper = mat("paper_c", "#f1e3be", 0.8)
    paper_d = mat("paper_cd", "#d9c69a", 0.85)
    red = mat("cord", "#c0362c", 0.6)
    ang = math.pi / 2 - 0.42
    r = cyl("roll", 0.17, 0.86, (0, 0.04, 0.12), paper, 32, 0.015)
    r.rotation_euler.y = ang
    for s in (-1, 1):
        e = cyl("end", 0.12, 0.88, (0, 0.04, 0.12), paper_d, 24, 0.0)
        e.rotation_euler.y = ang
    b = cyl("tie", 0.178, 0.08, (0, 0.04, 0.12), red, 32, 0.0)
    b.rotation_euler.y = ang
    for sx in (-1, 1):
        t = box("cord", (0.05, 0.02, 0.32), (sx * 0.05, -0.12, -0.08), red, 0.005)
        t.rotation_euler.y = sx * 0.25
    _face_cyl("medal", 0.17, 0.05, (0, -0.16, -0.24), gold(), 32, 0.012)
    _face_cyl("medal_in", 0.13, 0.06, (0, -0.165, -0.24), mat("gold_d", "#b8801c", 0.35, 1.0), 32, 0.006)
    g = gold()
    box("crown_band", (0.15, 0.03, 0.04), (0, -0.2, -0.29), g, 0.005)
    for k in range(3):
        c = cone("crown_pt", 0.035, 0.09, (-0.05 + k * 0.05, -0.2, -0.235 + (0.015 if k == 1 else 0)), g, 4, 0.0)
        c.rotation_euler.z = math.pi / 4
    _tilt(rx=5, rz=-8)


def _chest(body, band, trim, lock_m, planks=None, gem=None):
    """A chest: a box body under a round lid, straps over both, a lock plate."""
    box("body", (0.8, 0.5, 0.42), (0, 0, -0.2), body, 0.03)
    if planks:
        for z in (-0.13, -0.27):
            box("plank", (0.79, 0.505, 0.012), (0, 0, z), planks, 0.0)
    lid = cyl("lid", 0.25, 0.8, (0, 0, 0.01), body, 32, 0.02)
    lid.rotation_euler.y = math.pi / 2
    box("rim_lo", (0.83, 0.53, 0.06), (0, 0, -0.39), trim, 0.012)
    box("rim_hi", (0.83, 0.53, 0.05), (0, 0, 0.0), trim, 0.012)
    for sx in (-1, 1):
        box("strap", (0.08, 0.52, 0.42), (sx * 0.26, 0, -0.2), band, 0.01)
        s = cyl("strap_lid", 0.262, 0.08, (sx * 0.26, 0, 0.01), band, 32, 0.0)
        s.rotation_euler.y = math.pi / 2
        e = cyl("lid_end", 0.258, 0.03, (sx * 0.4, 0, 0.01), trim, 32, 0.0)
        e.rotation_euler.y = math.pi / 2
    box("lock", (0.15, 0.05, 0.18), (0, -0.26, -0.02), lock_m, 0.015)
    if gem:
        _face_cyl("gem", 0.04, 0.03, (0, -0.29, 0.0), gem, 6, 0.006)
    else:
        _face_cyl("hole", 0.025, 0.03, (0, -0.285, -0.0), mat("hole", "#1d1b1a", 0.8), 12, 0.0)
        box("slot", (0.02, 0.03, 0.05), (0, -0.285, -0.04), mat("hole", "#1d1b1a", 0.8), 0.0)
    _tilt(rx=14, rz=-26)


def chest_wood():
    """Free case: a plank chest with iron straps."""
    _chest(mat("chest_w", "#b07a42", 0.7), mat("iron_c", "#5d6470", 0.45, 0.6), mat("chest_wd", "#7a4e2a", 0.7),
           brass(), planks=mat("chest_wd", "#7a4e2a", 0.7))


def chest_silver():
    """Silver case: a steel-blue chest with bright silver straps."""
    s = mat("silver", "#e3e9f1", 0.22, 1.0)
    _chest(mat("chest_s", "#7d90ad", 0.5, 0.2), s, s, s)


def chest_royal():
    """Royal case: a blue chest with gold straps and a red gem on the lock."""
    _chest(mat("chest_r", "#2f5fc8", 0.5), gold(), gold(), gold(), gem=mat("gem", "#c0392b", 0.1))


def chest_cards():
    """Collection case: an open red chest with gold trim and a fan of cards rising from it."""
    body = mat("chest_c", "#c0483a", 0.5)
    g = gold()
    box("body", (0.8, 0.5, 0.4), (0, 0, -0.26), body, 0.03)
    box("rim", (0.83, 0.53, 0.06), (0, 0, -0.06), g, 0.012)
    box("rim_lo", (0.83, 0.53, 0.06), (0, 0, -0.44), g, 0.012)
    for sx in (-1, 1):
        box("strap", (0.08, 0.52, 0.4), (sx * 0.26, 0, -0.26), g, 0.01)
    before = set(bpy.context.scene.objects)
    box("lid", (0.8, 0.5, 0.08), (0, -0.25, 0.1), body, 0.02)  # built round the hinge (the body's back top edge)
    box("lid_rim", (0.83, 0.53, 0.04), (0, -0.25, 0.04), g, 0.01)
    _group(before, (0, 0.25, -0.06), (-105, 0, 0))
    back = mat("card_b", "#2a4fa0", 0.5)
    face = mat("card_f", "#efe6cf", 0.7)
    for k, (a, x) in enumerate(((0.45, -0.2), (0.0, 0.0), (-0.45, 0.2))):
        c = box("card", (0.3, 0.02, 0.44), (x, 0.02 - k * 0.03, 0.12), back if k != 1 else face, 0.015)
        c.rotation_euler.y = a
        f = box("frame", (0.32, 0.016, 0.46), (x, 0.03 - k * 0.03, 0.12), g, 0.015)
        f.rotation_euler.y = a
    _star_mesh("star", 0.09, 0.04, 0.0, 0.13, -0.025, -0.01, mat("star_b", "#2f62c8", 0.4))
    box("lock", (0.15, 0.05, 0.16), (0, -0.26, -0.12), g, 0.015)
    _tilt(rx=14, rz=-22)


def shard():
    """A commander shard: a broken corner of a framed portrait — a blue crystal fragment set in a gold frame corner."""
    face = mat("shard", "#5aa8f0", 0.15, 0.0, "#3a86ff", 0.15)
    face_l = mat("shard_l", "#9fd0ff", 0.15, 0.0, "#6ab0ff", 0.15)
    frag = [(-0.34, 0.38), (0.34, 0.38), (0.16, 0.12), (0.3, -0.04), (0.04, -0.16), (0.1, -0.44), (-0.34, -0.44)]
    _extrude("frag", frag, 0.1, face, y=-0.05, bevel=0.012)
    _extrude("facet", [(-0.26, 0.3), (0.08, 0.3), (-0.26, -0.1)], 0.01, face_l, y=-0.058)
    _extrude("facet2", [(0.06, 0.02), (0.2, 0.06), (-0.02, -0.12)], 0.01, face_l, y=-0.058)
    g = gold()
    dark = mat("gold_d", "#b8801c", 0.35, 1.0)
    _extrude("frame_top", [(-0.46, 0.5), (0.4, 0.5), (0.34, 0.38), (-0.34, 0.38)], 0.16, g, y=-0.08, bevel=0.02)
    _extrude("frame_left", [(-0.46, 0.5), (-0.34, 0.38), (-0.34, -0.44), (-0.46, -0.52)], 0.16, g, y=-0.08, bevel=0.02)
    box("bead_t", (0.68, 0.02, 0.025), (-0.04, -0.095, 0.44), dark, 0.0)
    box("bead_l", (0.025, 0.02, 0.84), (-0.4, -0.095, -0.03), dark, 0.0)
    sphere("boss", 0.07, (-0.4, -0.1, 0.44), g, (1, 0.7, 1), 2)
    _tilt(rx=-6, ry=8, rz=-14)


def blueprint():
    """Research (blueprint): a sheet of blue drafting paper unrolled from a tube, white grid and a drawn house."""
    blue = mat("bp", "#3e7fc1", 0.6)
    blue_d = mat("bp_d", "#2f68a6", 0.6)
    line = mat("bp_line", "#e8f2ff", 0.5)
    grid = mat("bp_grid", "#7fb0e0", 0.6)
    box("sheet", (0.66, 0.02, 0.56), (0, 0, -0.06), blue, 0.008)
    for k in range(5):
        box("gv", (0.008, 0.012, 0.54), (-0.26 + k * 0.13, -0.012, -0.06), grid, 0.0)
    for k in range(4):
        box("gh", (0.64, 0.012, 0.008), (0, -0.012, -0.28 + k * 0.13), grid, 0.0)
    for (x, z, w, h, r) in ((0.0, -0.24, 0.32, 0.03, 0), (-0.15, -0.12, 0.03, 0.27, 0), (0.15, -0.12, 0.03, 0.27, 0),
                            (-0.08, 0.08, 0.03, 0.24, -0.95), (0.08, 0.08, 0.03, 0.24, 0.95), (0.0, -0.17, 0.08, 0.03, 0),
                            (-0.04, -0.2, 0.03, 0.08, 0), (0.04, -0.2, 0.03, 0.08, 0)):
        b = box("draw", (w, 0.014, h), (x, -0.018, z), line, 0.0)
        b.rotation_euler.y = r
    for z, rr in ((0.27, 0.085), (-0.37, 0.06)):
        c = cyl("tube", rr, 0.72, (0, 0.0, z), blue_d, 24, 0.012)
        c.rotation_euler.y = math.pi / 2
        for sx in (-1, 1):
            e = cyl("tube_end", rr * 0.6, 0.73, (0, 0.0, z), mat("bp_end", "#a9cdef", 0.6), 16, 0.0)
            e.rotation_euler.y = math.pi / 2
    _tilt(rx=10, rz=-12)


def xp():
    """Experience: a fat gold star with a raised inner star."""
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = 0.52 if k % 2 == 0 else 0.25
        pts.append((math.cos(a) * rr, math.sin(a) * rr - 0.02))
    _extrude("star", pts, 0.2, gold(), y=-0.1, bevel=0.05)
    inner = [(x * 0.55, z * 0.55 - 0.01) for (x, z) in pts]
    _extrude("star_in", inner, 0.04, mat("gold_l", "#ffd34a", 0.25, 1.0), y=-0.135, bevel=0.012)
    _tilt(rx=-6, rz=-12)


def mason():
    """The free builder (mason): a cheerful worker bust in a yellow hard hat, holding up a trowel."""
    skin = mat("skin", "#f4c79a", 0.6)
    shirt = mat("shirt", "#3f86f0", 0.65)
    hat = mat("hardhat", "#ffc531", 0.35)
    sphere("torso", 0.3, (0, 0.04, -0.42), shirt, (1.35, 0.8, 0.75), 3)
    box("strap", (0.07, 0.3, 0.3), (-0.18, -0.04, -0.36), mat("overall", "#e07a2c", 0.6), 0.02)
    box("strap2", (0.07, 0.3, 0.3), (0.18, -0.04, -0.36), mat("overall", "#e07a2c", 0.6), 0.02)
    cyl("neck", 0.09, 0.14, (0, 0, -0.19), skin, 16, 0.0)
    sphere("head", 0.23, (0, 0, 0.0), skin, (1, 0.95, 1.05), 3)
    for sx in (-1, 1):
        sphere("eye", 0.032, (sx * 0.08, -0.205, 0.04), mat("eye", "#1b2140", 0.3), (1, 0.6, 1.2), 2)
        sphere("ear", 0.05, (sx * 0.23, 0, -0.01), skin, (0.6, 1, 1), 2)
    sphere("nose", 0.05, (0, -0.24, -0.03), mat("nose", "#eaa97a", 0.6), (1, 1, 1), 2)
    sphere("tache", 0.06, (0, -0.215, -0.09), mat("tache", "#7a4a2a", 0.8), (1.8, 0.7, 0.6), 2)
    _dome("hat", 0.255, (0, 0, 0.08), hat, (1, 1, 0.85))
    cyl("brim", 0.3, 0.035, (0, -0.03, 0.08), hat, 32, 0.012)
    box("ridge", (0.06, 0.3, 0.08), (0, 0, 0.29), hat, 0.02)
    # the trowel, raised in the right hand
    sphere("hand", 0.075, (0.36, -0.12, -0.24), skin, (1, 1, 1), 2)
    h = cyl("handle", 0.035, 0.18, (0.38, -0.12, -0.12), mat("handle_i", "#8a5e36", 0.6), 10, 0.01)
    h.rotation_euler.y = 0.2
    box("shank", (0.02, 0.03, 0.08), (0.4, -0.12, -0.0), steel(), 0.005)
    _extrude("trowel", [(0.4, 0.02), (0.52, 0.12), (0.42, 0.38), (0.3, 0.12)], 0.025, mat("trowel", "#cfd8e3", 0.3, 0.7),
             y=-0.14, bevel=0.006)
    _tilt(rz=-8)


def white_flag():
    """Retreat: a white flag on a wooden pole."""
    pole = mat("pole_i", "#8a5e36", 0.6)
    cyl("pole", 0.028, 1.0, (-0.28, 0, 0.0), pole, 10, 0.0)
    sphere("finial", 0.055, (-0.28, 0, 0.52), brass(), (1, 1, 1), 2)
    cloth = mat("flag_w", "#f7f5ef", 0.6)
    for k, (x, rz) in enumerate(((-0.14, 0.12), (0.06, -0.18), (0.24, 0.14))):
        f = box("cloth", (0.21, 0.03, 0.44), (x, 0.0 + (0.02 if k == 1 else 0.0), 0.24), cloth, 0.012)
        f.rotation_euler.z = rz
    for z in (0.04, 0.44):
        cyl("ring", 0.04, 0.03, (-0.28, 0, z), brass(), 12, 0.0)


def pencil():
    """Rename / edit: a yellow pencil with a pink eraser."""
    before = set(bpy.context.scene.objects)
    body = cyl("body", 0.1, 0.72, (0, 0, 0.0), mat("pencil", "#ffc531", 0.45), 6, 0.01)
    body.rotation_euler.z = math.pi / 6
    cyl("ferrule", 0.105, 0.1, (0, 0, 0.41), steel(), 16, 0.01)
    for z in (0.385, 0.435):
        cyl("ferrule_r", 0.11, 0.015, (0, 0, z), mat("steel_d", "#8a96a4", 0.3, 1.0), 16, 0.0)
    cyl("eraser", 0.098, 0.13, (0, 0, 0.52), mat("eraser", "#f08aa0", 0.7), 16, 0.03)
    t = cone("tip", 0.1, 0.22, (0, 0, -0.47), mat("wood_p", "#ebc48a", 0.7), 6, 0.0)
    t.rotation_euler = (math.pi, 0, math.pi / 6)
    g = cone("lead", 0.038, 0.085, (0, 0, -0.54), mat("lead", "#3a3d4a", 0.4), 12, 0.0)
    g.rotation_euler.x = math.pi
    _group(before, rot=(0, 45, 0))


def _speaker():
    body = mat("spk", "#41507a", 0.5)
    c = mat("spk_cone", "#cfd7e3", 0.4, 0.3)
    box("spk_box", (0.2, 0.26, 0.3), (-0.33, 0, 0.0), body, 0.03)
    k = cyl("spk_horn", 0.13, 0.3, (-0.1, 0, 0.0), c, 24, 0.015, r2=0.33)
    k.rotation_euler.y = math.pi / 2
    k2 = cyl("spk_rim", 0.335, 0.04, (0.06, 0, 0.0), body, 24, 0.01)
    k2.rotation_euler.y = math.pi / 2


def sound_on():
    """Sound on: a speaker with two sound waves."""
    _speaker()
    wave = mat("wave", "#ffc531", 0.35)
    for R in (0.2, 0.34):
        _torus("wave", R, 0.04, (0.12, 0, 0.0), wave, (math.pi / 2, 0, 0), seg=40,
               keep=lambda co, R=R: co.x > R * 0.6)
    _tilt(rz=-14)


def sound_off():
    """Sound off: the speaker with a red cross."""
    _speaker()
    red = mat("x_red", "#ef4b3f", 0.45)
    for a in (45, -45):
        b = box("x", (0.08, 0.08, 0.42), (0.34, -0.04, 0.0), red, 0.025)
        b.rotation_euler.y = math.radians(a)
    _tilt(rz=-14)


def _die(loc, rot, body, pip):
    before = set(bpy.context.scene.objects)
    s = 0.21
    box("die", (2 * s, 2 * s, 2 * s), (0, 0, 0), body, 0.06)
    faces = {(0, -1, 0): 1, (0, 1, 0): 6, (1, 0, 0): 3, (-1, 0, 0): 4, (0, 0, 1): 2, (0, 0, -1): 5}
    layouts = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)], 4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
               5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)], 6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
    for n, val in faces.items():
        axis = [i for i in range(3) if n[i] != 0][0]
        others = [i for i in range(3) if i != axis]
        for (u, v) in layouts[val]:
            p = [0.0, 0.0, 0.0]
            p[axis] = n[axis] * (s - 0.005)
            p[others[0]] = u * 0.105
            p[others[1]] = v * 0.105
            sc = [1.0, 1.0, 1.0]
            sc[axis] = 0.4
            sphere("pip", 0.045, tuple(p), pip, tuple(sc), 2)
    _group(before, loc, rot)


def dice():
    """Random pick: a white die and a red die."""
    navy = mat("pip_n", "#1b2140", 0.4)
    white = mat("die_w", "#f8f6f0", 0.4)
    _die((-0.25, 0.1, -0.16), (24, 10, 32), white, navy)
    _die((0.26, -0.1, 0.16), (-18, -16, -24), mat("die_r", "#e04a3e", 0.4), mat("pip_w", "#fbf8f0", 0.4))


def eye_off():
    """Hidden (an army in the fog): an eye struck through."""
    white = mat("eye_w", "#f8f6f0", 0.45)
    sphere("eye", 0.42, (0, 0, 0), white, (1, 0.34, 0.55), 4)
    _face_cyl("iris", 0.17, 0.05, (0, -0.125, 0), mat("iris", "#3e7fc1", 0.35), 32, 0.01)
    _face_cyl("pupil", 0.085, 0.05, (0, -0.145, 0), mat("pupil", "#1b2140", 0.3), 24, 0.005)
    sphere("glint", 0.03, (-0.05, -0.17, 0.05), mat("glint", "#ffffff", 0.2), (1, 0.5, 1), 2)
    lid = _torus("lid", 0.43, 0.035, (0, -0.02, 0.0), mat("lid", "#41507a", 0.5), (math.pi / 2, 0, 0), seg=40)
    lid.scale = (1, 0.55, 1)
    b = box("slash", (0.1, 0.1, 1.05), (0, -0.2, 0), mat("x_red", "#ef4b3f", 0.45), 0.03)
    b.rotation_euler.y = math.radians(42)


def hex_tile():
    """A hex of land (captured hexes, rewards): a grass hex with soil sides, tufts and a few flowers."""
    grass = kit.noisy_mat("grass_t", "#74a645", "#86c45e", 4.0)
    dirt = kit.noisy_mat("dirt_t", "#b58a5e", "#7e5a45", 6.0)
    kit.hex_prism("tile", (0, 0, 0), 0.62, 0.22, grass, dirt, 0.04)
    tuft = mat("tuft", "#8fc255", 0.7)
    for (x, y) in ((-0.25, 0.1), (0.2, -0.2), (0.3, 0.22), (-0.05, -0.32), (-0.35, -0.15)):
        for k in range(3):
            c = cone("tuft", 0.03, 0.09, (x + (k - 1) * 0.03, y, 0.04), tuft, 6, 0.0)
            c.rotation_euler.y = (k - 1) * 0.35
    for (x, y, c) in ((0.05, 0.05, "#ffffff"), (-0.15, -0.12, "#ffd34a"), (0.32, -0.02, "#ffffff")):
        sphere("flower", 0.035, (x, y, 0.03), mat("fl" + c, c, 0.5), (1, 1, 0.7), 2)
    kit.tree((0.12, 0.3, 0.0), 0.55, 1)
    _tilt(rx=52, rz=0)


# ------------------------------------------------------------------ re-drawn resources


def food():
    """Food: a tied burlap sack full of grain, wheat ears standing out of its mouth."""
    sack = mat("sack", "#d9b779", 0.9)
    sack_d = mat("sack_d", "#bf9a5c", 0.9)
    rope = mat("rope", "#8a5e36", 0.8)
    grain = mat("grain", "#f2c650", 0.55)
    stalk = mat("stalk", "#c99a3a", 0.7)
    sphere("sack", 0.31, (0, 0, -0.2), sack, (1.08, 0.95, 1.0), 3)
    cyl("neck", 0.17, 0.14, (0, 0, 0.12), sack, 20, 0.02, r2=0.11)
    _torus("tie", 0.12, 0.03, (0, 0, 0.15), rope, seg=20)
    cyl("mouth", 0.12, 0.1, (0, 0, 0.23), sack, 20, 0.02, r2=0.2)
    sphere("grain_top", 0.17, (0, 0, 0.27), grain, (1.05, 1.05, 0.4), 3)
    box("patch", (0.2, 0.02, 0.16), (0.06, -0.29, -0.22), sack_d, 0.01).rotation_euler.y = 0.12
    for k, a in enumerate((-0.42, -0.05, 0.36)):
        x0, z0 = math.sin(a) * 0.05, 0.28
        L = 0.42 if k != 1 else 0.5
        x1, z1 = x0 + math.sin(a) * L, z0 + math.cos(a) * L
        s = cyl("stalk", 0.018, L, ((x0 + x1) / 2, -0.01, (z0 + z1) / 2), stalk, 6, 0.0)
        s.rotation_euler.y = a
        for j in range(5):
            t = 0.5 + j * 0.11
            px, pz = x0 + (x1 - x0) * t, z0 + (z1 - z0) * t
            for side in (-1, 1):
                g = sphere("ear", 0.045, (px + side * 0.035 * math.cos(a), -0.02, pz - side * 0.035 * math.sin(a)), grain,
                           (0.75, 0.7, 1.35), 2)
                g.rotation_euler.y = a + side * 0.35
        sphere("ear_tip", 0.04, (x1 + math.sin(a) * 0.04, -0.02, z1 + math.cos(a) * 0.04), grain, (0.7, 0.7, 1.3), 2)
    for (x, y) in ((-0.3, -0.24), (-0.22, -0.3), (0.32, -0.26)):
        sphere("spill", 0.035, (x, y, -0.48), grain, (1, 1, 0.8), 2)


def _ingot(loc, rz, m, top):
    x, y, z = loc
    bw, bd, tw, td, h = 0.25, 0.14, 0.19, 0.085, 0.17
    verts = [(-bw, -bd, 0), (bw, -bd, 0), (bw, bd, 0), (-bw, bd, 0), (-tw, -td, h), (tw, -td, h), (tw, td, h), (-tw, td, h)]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    me = bpy.data.meshes.new("ingot")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new("ingot", me)
    bpy.context.scene.collection.objects.link(o)
    o.location = (x, y, z)
    o.rotation_euler.z = rz
    kit._finish(o, m, 0.02, 3)
    t = box("ingot_mark", (0.16, 0.07, 0.012), (x, y, z + h + 0.004), top, 0.004)
    t.rotation_euler.z = rz


def metal():
    """Metal: a pyramid of three light steel ingots (the blue rim light picks out their edges)."""
    m = mat("steel_ig", "#d3dbe6", 0.3, 0.55)
    top = mat("steel_igl", "#eef3f9", 0.25, 0.5)
    for (x, y, z) in ((-0.26, 0.0, -0.17), (0.26, 0.0, -0.17), (0.0, 0.0, 0.0)):
        _ingot((x, y, z), 0.0, m, top)
    _tilt(rx=26, rz=-12)


def oil():
    barrel()


ICONS = {"coin": coin, "food": food, "metal": metal, "raivite": raivite, "oil": oil, "builder": builder,
         "castle_icon": castle_icon, "helmet": helmet, "hammer": hammer, "hands": hands, "scales": globe,
         "trophy": trophy, "book": book, "mail": mail, "gear": gear,
         "target": target, "pin": pin, "fort": fort, "tower": tower,
         "crate": crate, "flask": flask, "cart": cart, "stall": stall, "anchor": anchor, "houses": houses,
         "crown": crown, "cards": cards, "lock": lock, "ad": ad, "medal": medal, "orders": orders,
         "hourglass": hourglass, "key": key, "frame": frame,
         # the v2 set (docs/ui_style.md §3.5)
         "swords": swords, "shield": shield, "dove": dove, "treaty": treaty, "seal": seal, "handshake": handshake,
         "globe": globe, "horn": horn, "gift": gift, "coins": coins, "lightning": lightning, "barrel": barrel,
         "calendar": calendar, "charter": charter, "chest_wood": chest_wood, "chest_silver": chest_silver,
         "chest_royal": chest_royal, "chest_cards": chest_cards, "medal_bronze": medal_bronze,
         "medal_silver": medal_silver, "medal_gold": medal_gold, "shard": shard, "blueprint": blueprint, "xp": xp,
         "mason": mason, "white_flag": white_flag, "pencil": pencil, "sound_on": sound_on, "sound_off": sound_off,
         "dice": dice, "eye_off": eye_off, "hex_tile": hex_tile}

# The share of the square the model's larger side fills (default FILL). 0.9 leaves 6 px of 128 round the model:
# room for the 3 px rim and a little air. Thin or very round icons get a touch less, so they weigh the same.
FILL = 0.9
FILL_BY = {"coin": 0.88, "coins": 0.88, "shield": 0.86, "seal": 0.86, "gear": 0.86, "scales": 0.88, "globe": 0.88,
           "frame": 0.84, "xp": 0.9, "lightning": 0.88}
# Per-icon strength of the cool rim light (W); metal gets a strong blue edge so the light steel reads on slate.
RIM_BY = {"metal": 420}


def _fit_camera(cam, fill):
    """Ortho scale and shift so the model's silhouette (every evaluated vertex, projected) fills `fill` of the frame,
    centred."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    inv = cam.matrix_world.inverted()
    lo, hi = [1e9, 1e9], [-1e9, -1e9]
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        mw = eo.matrix_world
        for v in me.vertices:
            p = inv @ (mw @ v.co)
            lo[0], lo[1] = min(lo[0], p.x), min(lo[1], p.y)
            hi[0], hi[1] = max(hi[0], p.x), max(hi[1], p.y)
        eo.to_mesh_clear()
    size = max(hi[0] - lo[0], hi[1] - lo[1]) / fill
    cam.data.ortho_scale = size
    cam.data.shift_x = (lo[0] + hi[0]) / 2 / size
    cam.data.shift_y = (lo[1] + hi[1]) / 2 / size


def render(path, fill=FILL, rim_energy=120, raw_dir=None, samples=64):
    sc = bpy.context.scene
    bpy.ops.object.light_add(type="AREA", location=(-1.5, -2.5, 2.5))
    k = bpy.context.active_object
    k.data.energy = 260
    k.data.size = 2.5
    k.rotation_euler = (math.radians(50), 0, math.radians(-30))
    bpy.ops.object.light_add(type="AREA", location=(2, 1.5, 1.2))
    r = bpy.context.active_object
    r.data.energy = rim_energy
    r.data.color = (0.6, 0.75, 1.0)
    r.rotation_euler = (math.radians(70), 0, math.radians(125))
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.4, 0.5, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.location = (0, -6, 0.6)
    cam.rotation_euler = (math.radians(84), 0, 0)
    sc.camera = cam
    _fit_camera(cam, fill)
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = RAW
    sc.render.resolution_y = RAW
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    raw = os.path.join(raw_dir or tempfile.mkdtemp(prefix="raivon_icons_"), os.path.basename(path))
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    _finish(raw, path)


def _finish(raw, path):
    """256 → 128 (Lanczos on premultiplied colour, so the edge keeps no dark fringe), then the INK rim."""
    from PIL import Image
    im = Image.open(raw).convert("RGBA").convert("RGBa").resize((OUT_PX, OUT_PX), Image.LANCZOS).convert("RGBA")
    small = raw[:-4] + "_%d.png" % OUT_PX
    im.save(small)
    res = subprocess.run([sys.executable, "-I", INK_RIM, small, path], capture_output=True, text=True)
    if res.stdout.strip():
        print(res.stdout.strip(), flush=True)
    if res.returncode not in (0, 2):
        raise RuntimeError("ink_rim failed for %s: %s" % (path, res.stderr))


def out_path(base, name):
    return os.path.join(base if name in ROOT_ICONS else os.path.join(base, "icons"), name + ".png")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    base = os.path.abspath(args[0] if args else "game/assets/ui")
    raw_dir = opts.get("raw") or tempfile.mkdtemp(prefix="raivon_icons_")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(os.path.join(base, "icons"), exist_ok=True)
    for name in (args[1:] or list(ICONS)):
        reset()
        ICONS[name]()
        render(out_path(base, name), FILL_BY.get(name, FILL), RIM_BY.get(name, 120), raw_dir,
               int(opts.get("samples", 64)))
        print("ICON", name, flush=True)
