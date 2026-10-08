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
    cover = mat("cover", "#8a3b2a", 0.6)
    pages = mat("pages", "#efe4c6", 0.8)
    box("pages", (0.62, 0.42, 0.14), (0, 0, 0), pages, 0.02)
    box("cover_t", (0.66, 0.46, 0.04), (0, 0, 0.09), cover, 0.02)
    box("cover_b", (0.66, 0.46, 0.04), (0, 0, -0.09), cover, 0.02)
    box("spine", (0.06, 0.46, 0.22), (-0.33, 0, 0), cover, 0.02)
    box("clasp", (0.16, 0.1, 0.05), (0.0, -0.24, 0.1), gold(), 0.01)
    for o in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        o.rotation_euler.x += math.radians(60)


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


ICONS = {"coin": coin, "food": food, "metal": metal, "raivite": raivite, "oil": oil, "builder": builder,
         "castle_icon": castle_icon, "helmet": helmet, "hammer": hammer, "hands": hands, "scales": globe,
         "trophy": trophy, "book": book, "mail": mail, "gear": gear,
         "target": target, "pin": pin, "fort": fort, "tower": tower}


ORTHO = {"target": 1.5, "pin": 1.45, "fort": 1.5, "tower": 1.7, "castle_icon": 1.75, "hammer": 1.6, "scales": 1.5, "trophy": 1.45, "gear": 1.4, "hands": 1.45}


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
