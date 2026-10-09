"""Resource icons for the top bar, rendered in 3D like the reference HUD (docs/reference): a gold coin with an embossed
R, a wheat sheaf, a stack of metal ingots, a raivite crystal cluster, an oil drop, a builder's hammer.

Run: python3 tools/blender/icon_assets.py game/assets/ui [name ...]
Writes <name>.png (128 × 128, transparent) for coin, food, metal, raivite, oil, builder.
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cone, cyl, mat, sphere  # noqa: E402


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


def food():
    stalk = mat("stalk", "#c99a3a", 0.7)
    grain = mat("grain", "#f0c548", 0.55)
    tie = mat("tie", "#b5452e", 0.7)
    for k in range(7):
        a = (k - 3) * 0.13
        top = (math.sin(a) * 0.55, 0, 0.35 + math.cos(a) * 0.12)
        s = cyl("stalk", 0.026, 0.75, (math.sin(a) * 0.2, 0, 0.0), stalk, 6, 0.0)
        s.rotation_euler.y = a
        for j in range(6):
            t = 0.55 + j * 0.07
            sphere("grain", 0.068, (math.sin(a) * (0.2 + t * 0.5), -0.01, -0.0 + t * 0.62 * math.cos(a) - 0.05), grain, (0.7, 0.7, 1.2), 2)
    cyl("tie", 0.09, 0.07, (0, 0, -0.12), tie, 16, 0.01)


def metal():
    steel = mat("steel", "#aab4c0", 0.25, 1.0)
    for (x, y, z) in ((-0.26, 0, -0.1), (0.26, 0, -0.1), (0.0, 0, 0.17)):
        box("ingot", (0.48, 0.28, 0.24), (x, y, z), steel, 0.05)
        box("ingot_top", (0.4, 0.2, 0.02), (x, y, z + 0.125), mat("steel_l", "#d2dae3", 0.2, 1.0), 0.005)


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


def oil():
    o = mat("oil", "#2a2238", 0.12, 0.3)
    sphere("drop", 0.34, (0, 0, -0.1), o, (1, 1, 1), 4)
    cone("drop_tip", 0.3, 0.5, (0, 0, 0.3), o, 32, 0.0)
    sphere("shine", 0.07, (-0.12, -0.3, 0.02), mat("shine", "#b8a8e0", 0.1), (0.6, 0.4, 1.2), 2)


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


def globe():
    sea = mat("sea_i", "#2a6fd0", 0.3)
    land = mat("land_i", "#4f9a34", 0.6)
    sphere("globe", 0.42, (0, 0, 0.04), sea, (1, 1, 1), 4)
    for (x, y, z, r) in ((-0.15, -0.3, 0.2, 0.14), (0.18, -0.32, -0.05, 0.12), (-0.05, -0.36, -0.18, 0.09), (0.25, -0.2, 0.25, 0.1)):
        sphere("land", r, (x, y, z), land, (1.2, 0.5, 1), 2)
    t = cyl("ring", 0.5, 0.03, (0, 0, 0.04), gold(), 48, 0.0)
    t.rotation_euler = (math.radians(70), math.radians(20), 0)
    cyl("stand", 0.2, 0.06, (0, 0, -0.45), mat("wood_i", "#6e4a2c", 0.6), 24, 0.02)


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
    g = gold()
    blue = mat("ribbon_b", "#2f62c8", 0.6)
    white = mat("disc_w", "#f3efe6", 0.5)
    for sx in (-1, 1):
        r = box("ribbon", (0.2, 0.03, 0.46), (sx * 0.1, 0.04, 0.24), blue, 0.005)
        r.rotation_euler.y = sx * -0.32
        s_ = box("stripe", (0.05, 0.035, 0.46), (sx * 0.1, 0.035, 0.24), white, 0.0)
        s_.rotation_euler.y = sx * -0.32
    box("clasp", (0.42, 0.06, 0.08), (0, 0.0, 0.03), g, 0.015)
    d = cyl("disc", 0.27, 0.06, (0, 0, -0.26), mat("gold_d", "#b8801c", 0.35, 1.0), 40, 0.02)
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


ICONS = {"coin": coin, "food": food, "metal": metal, "raivite": raivite, "oil": oil, "builder": builder,
         "castle_icon": castle_icon, "helmet": helmet, "hammer": hammer, "hands": hands, "scales": globe,
         "trophy": trophy, "book": book, "mail": mail, "gear": gear,
         "target": target, "pin": pin, "fort": fort, "tower": tower,
         "crate": crate, "flask": flask, "cart": cart, "stall": stall, "anchor": anchor, "houses": houses,
         "crown": crown, "cards": cards, "lock": lock, "ad": ad, "medal": medal, "orders": orders,
         "hourglass": hourglass, "key": key, "frame": frame}


ORTHO = {"hourglass": 1.2, "key": 1.15, "frame": 1.25, "book": 1.0, "orders": 1.2, "crown": 1.15, "cards": 1.2, "lock": 1.2, "ad": 1.2, "medal": 1.25, "crate": 1.4, "cart": 1.08, "stall": 1.5, "anchor": 1.5, "houses": 1.45, "target": 1.5, "pin": 1.45, "fort": 1.5, "tower": 1.7, "castle_icon": 1.75, "hammer": 1.6, "scales": 1.5, "trophy": 1.45, "gear": 1.4, "hands": 1.45}


def render(path, ortho=1.35):
    sc = bpy.context.scene
    bpy.ops.object.light_add(type="AREA", location=(-1.5, -2.5, 2.5))
    k = bpy.context.active_object
    k.data.energy = 260
    k.data.size = 2.5
    k.rotation_euler = (math.radians(50), 0, math.radians(-30))
    bpy.ops.object.light_add(type="AREA", location=(2, 1.5, 1.2))
    r = bpy.context.active_object
    r.data.energy = 120
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
    cam.data.ortho_scale = ortho
    cam.location = (0, -6, 0.6)
    cam.rotation_euler = (math.radians(84), 0, 0)
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = 128
    sc.render.resolution_y = 128
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "game/assets/ui"
    os.makedirs(out, exist_ok=True)
    for name in (args[1:] or list(ICONS)):
        reset()
        ICONS[name]()
        render(os.path.join(os.path.abspath(out), name + ".png"), ORTHO.get(name, 1.35))
        print("ICON", name, flush=True)
