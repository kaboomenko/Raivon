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


ICONS = {"coin": coin, "food": food, "metal": metal, "raivite": raivite, "oil": oil, "builder": builder}


def render(path):
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
    cam.data.ortho_scale = 1.35
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
        render(os.path.join(os.path.abspath(out), name + ".png"))
        print("ICON", name, flush=True)
