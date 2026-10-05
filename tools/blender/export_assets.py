"""Builds every medieval-stage model and exports it as glTF binary for Godot.

Run: python3 tools/blender/export_assets.py game/assets/models
Each asset is modelled around the origin (base on Z=0, 1 hex = radius 1).
"""
import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cone, cyl, mat, noisy_mat, prism_roof, sphere  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "game/assets/models"
os.makedirs(OUT, exist_ok=True)

STONE = "#b9b2a6"
STONE_D = "#8f877b"
ROOF_BLUE = "#2d55b8"
ROOF_RED = "#9b2a26"
WOOD = "#7d5130"
WOOD_L = "#a8743f"
GOLD = "#ffc933"
PLASTER = "#e9dcc0"


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()


def bake_asset(objs, size=1024):
    """Join, unwrap and bake base colour of procedural materials into one texture (glTF-friendly)."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.convert(target="MESH")  # apply modifiers
    bpy.ops.object.join()
    ob = bpy.context.active_object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    img = bpy.data.images.new("bake", size, size)
    for slot in ob.material_slots:
        nt = slot.material.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.use_pass_direct = False
    sc.render.bake.use_pass_indirect = False
    sc.render.bake.margin = 4
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
    # one material: baked colour + per-slot roughness/metal/emission averaged into the main one
    emissive = [s.material for s in ob.material_slots if s.material.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value > 0]
    metal = [s.material for s in ob.material_slots if s.material.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value > 0.3]
    baked = bpy.data.materials.new("baked")
    baked.use_nodes = True
    bnt = baked.node_tree
    tex = bnt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    bnt.links.new(tex.outputs["Color"], bnt.nodes["Principled BSDF"].inputs["Base Color"])
    bnt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    keep = {}
    for i, slot in enumerate(ob.material_slots):
        keep[i] = slot.material if (slot.material in emissive or slot.material in metal) else baked
    mats = list(dict.fromkeys(keep.values()))
    old_idx = [p.material_index for p in ob.data.polygons]
    ob.data.materials.clear()
    for mm in mats:
        ob.data.materials.append(mm)
    for p, oi in zip(ob.data.polygons, old_idx):
        p.material_index = mats.index(keep[oi])
    img.pack()
    return ob


def export(name):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    objs = [bake_asset(objs, 512 if len(objs) < 12 else 1024)]
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    path = os.path.join(OUT, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    print("exported", path, len(objs), "objects")


def m(name, color, rough=0.75, metal=0.0, emission=None, strength=0.0):
    tex = {"stone": "stone", "stone_d": "stone", "cobble": "stone", "roof": "roof", "wood": "wood",
           "planks": "wood", "timber": "wood", "plaster": "plaster", "door": "wood", "mrock": "plaster",
           "mrock_d": "plaster", "rock": "plaster", "roof_wood": "wood"}
    if name in tex and not emission and metal == 0.0:
        return kit.textured(tex[name], color)
    return mat(name, color, rough, metal, emission, strength)


# ------------------------------------------------------------------ building blocks


def crenellated_wall(x0, y0, x1, y1, h=0.32, t=0.12, color=STONE):
    st = m("stone", color, 0.85)
    ln = math.dist((x0, y0), (x1, y1))
    ang = math.atan2(y1 - y0, x1 - x0)
    w = box("wall", (ln, t, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), st, 0.015)
    w.rotation_euler.z = ang
    n = max(2, int(ln / 0.09))
    for i in range(n):
        if i % 2:
            continue
        f = (i + 0.5) / n
        px, py = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        b = box("merlon", (ln / n, t * 1.05, 0.07), (px, py, h + 0.035), st, 0.008)
        b.rotation_euler.z = ang


def round_tower(x, y, r=0.11, h=0.55, roof=ROOF_BLUE, banner=None):
    st = m("stone", STONE, 0.85)
    cyl("tower", r, h, (x, y, h / 2), st, 14, 0.015)
    cyl("tower_ring", r * 1.12, 0.05, (x, y, h - 0.02), m("stone_d", STONE_D), 14, 0.01)
    cone("tower_roof", r * 1.35, r * 3.2, (x, y, h + r * 1.6), m("roof", roof, 0.5), 14, 0.01)
    sphere("tip", r * 0.18, (x, y, h + r * 3.25), m("gold", GOLD, 0.3, 0.7), (1, 1, 1), 1)
    # windows
    for k in range(3):
        a = k * 2.1
        box("win", (0.025, 0.02, 0.05), (x + math.cos(a) * r * 0.98, y + math.sin(a) * r * 0.98, h * 0.6), m("win", "#2a1d12", 0.9), 0.002).rotation_euler.z = a + math.pi / 2


def square_house(x, y, w, d, h, roof=ROOF_BLUE, wall=PLASTER, rot=0.0, timber=True):
    o = box("house", (w, d, h), (x, y, h / 2), m("plaster", wall, 0.85), 0.015)
    o.rotation_euler.z = rot
    r = prism_roof("roof", w, d, h * 0.9, (x, y, h), m("roof", roof, 0.55), overhang=0.04, rot_z=rot)
    if timber:
        beam = m("timber", "#5a3a22", 0.8)
        for f in (-0.5, 0.5):
            b = box("beam", (0.025, d * 1.01, h), (x + f * w * 0.98 * math.cos(rot), y + f * w * 0.98 * math.sin(rot), h / 2), beam, 0.004)
            b.rotation_euler.z = rot
    return o, r


def soldier(x, y, color, s=1.0, weapon="spear", shield=True):
    skin = m("skin", "#e8b48e", 0.7)
    armor = m("armor", "#aeb5c0", 0.35, 0.65)
    cloth = m("cloth" + color, color, 0.7)
    cyl("legs", 0.035 * s, 0.11 * s, (x, y, 0.055 * s), m("boots", "#3b2c22"), 8, 0.008)
    cyl("torso", 0.055 * s, 0.13 * s, (x, y, 0.17 * s), cloth, 10, 0.02)
    cyl("chest", 0.058 * s, 0.07 * s, (x, y, 0.2 * s), armor, 10, 0.015)
    sphere("head", 0.045 * s, (x, y, 0.28 * s), skin, (1, 1, 1), 2)
    sphere("helm", 0.05 * s, (x, y, 0.3 * s), armor, (1, 1, 0.85), 2)
    if weapon == "spear":
        cyl("spear", 0.007 * s, 0.42 * s, (x + 0.06 * s, y, 0.22 * s), m("wood", WOOD), 6, 0.0)
        cone("tip", 0.016 * s, 0.05 * s, (x + 0.06 * s, y, 0.45 * s), armor, 6, 0.0)
    if shield:
        sh = cyl("shield", 0.05 * s, 0.015 * s, (x, y - 0.06 * s, 0.17 * s), cloth, 12, 0.005)
        sh.rotation_euler.x = math.pi / 2
        cyl("boss", 0.015 * s, 0.02 * s, (x, y - 0.07 * s, 0.17 * s), m("gold", GOLD, 0.3, 0.7), 8, 0.0).rotation_euler.x = math.pi / 2


def banner(x, y, color, h=0.9, w=0.22):
    cyl("pole", 0.012, h, (x, y, h / 2), m("pole", "#d9d2c3", 0.5), 8, 0.003)
    cyl("bar", 0.008, w + 0.04, (x + w / 2, y, h - 0.02), m("pole", "#d9d2c3", 0.5), 6, 0.0).rotation_euler.y = math.pi / 2
    b = box("cloth", (w, 0.012, w * 1.6), (x + w / 2, y, h - 0.02 - w * 0.8), m("banner" + color, color, 0.7), 0.003)
    # white emblem
    box("emblem", (w * 0.45, 0.016, w * 0.45), (x + w / 2, y, h - 0.02 - w * 0.65), m("emblem", "#f4f4f4", 0.6), 0.003)
    cone("cut", w * 0.36, 0.02, (x + w / 2, y, h - 0.02 - w * 1.62), m("banner" + color, color, 0.7), 3, 0.0)
    sphere("orb", 0.025, (x, y, h + 0.02), m("gold", GOLD, 0.3, 0.7), (1, 1, 1), 1)


# ------------------------------------------------------------------ assets


def castle(roof=ROOF_BLUE, flagc=ROOF_BLUE):
    st = m("stone", STONE, 0.85)
    box("base", (1.3, 1.3, 0.06), (0, 0, 0.03), m("cobble", "#a59d8e", 0.9), 0.02)
    corners = [(-0.55, -0.55), (0.55, -0.55), (0.55, 0.55), (-0.55, 0.55)]
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        crenellated_wall(x0, y0, x1, y1, 0.3)
        round_tower(x0, y0, 0.11, 0.5, roof)
    # gatehouse
    box("gate", (0.28, 0.16, 0.42), (0, -0.56, 0.21), st, 0.02)
    box("gate_door", (0.13, 0.03, 0.2), (0, -0.645, 0.1), m("door", "#4a2f19", 0.8), 0.01)
    prism_roof("gate_roof", 0.3, 0.18, 0.14, (0, -0.56, 0.42), m("roof", roof, 0.5))
    # keep
    box("keep", (0.5, 0.42, 0.75), (0.05, 0.12, 0.375), st, 0.02)
    prism_roof("keep_roof", 0.54, 0.46, 0.34, (0.05, 0.12, 0.75), m("roof", roof, 0.5))
    for x, y, h in [(-0.22, -0.08, 0.95), (0.3, -0.08, 0.85), (0.3, 0.32, 1.05), (-0.2, 0.33, 0.8)]:
        round_tower(x, y, 0.09, h, roof)
    # hall
    square_house(-0.28, 0.32, 0.34, 0.26, 0.38, roof, STONE, 0.0, False)
    for i in range(6):
        w = box("win", (0.03, 0.02, 0.06), (-0.14 + i * 0.07, -0.095, 0.5), m("win_lit", "#ffcf6b", 0.5, emission="#ffb84a", strength=2.0), 0.003)
    banner(0.05, 0.12, flagc, 1.45, 0.24)
    banner(-0.55, -0.55, flagc, 0.95, 0.16)
    banner(0.55, -0.55, flagc, 0.95, 0.16)


def house(roof):
    def build():
        square_house(0, 0, 0.42, 0.32, 0.28, roof)
        cyl("chimney", 0.035, 0.18, (0.1, 0.07, 0.42), m("stone", STONE, 0.85), 8, 0.008)
        box("door", (0.08, 0.02, 0.13), (0, -0.165, 0.065), m("door", "#4a2f19", 0.8), 0.006)
        for dx in (-0.12, 0.12):
            box("win", (0.05, 0.02, 0.05), (dx, -0.165, 0.17), m("win_lit", "#ffcf6b", 0.5, emission="#ffb84a", strength=1.5), 0.003)
    return build


def mine():
    rock = m("rock", "#8a8174", 0.9)
    rnd = random.Random(3)
    for i in range(9):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0.1, 0.5)
        sphere("rock", rnd.uniform(0.14, 0.26), (math.cos(a) * r, math.sin(a) * r + 0.15, 0.05), rock, (1.2, 1.0, rnd.uniform(0.6, 1.1)), 1)
    wd = m("wood", WOOD)
    for dx in (-0.16, 0.16):
        box("post", (0.05, 0.05, 0.4), (dx, -0.25, 0.2), wd, 0.006)
    box("lintel", (0.42, 0.06, 0.06), (0, -0.25, 0.42), wd, 0.006)
    box("hole", (0.24, 0.06, 0.3), (0, -0.21, 0.15), m("dark", "#15100b", 1.0), 0.0)
    # scaffold tower
    for dx, dy in [(0.25, -0.05), (0.45, -0.05), (0.25, 0.15), (0.45, 0.15)]:
        box("scaf", (0.035, 0.035, 0.55), (dx, dy, 0.275), wd, 0.004)
    box("scaf_deck", (0.26, 0.26, 0.03), (0.35, 0.05, 0.55), m("planks", WOOD_L), 0.006)
    prism_roof("scaf_roof", 0.28, 0.28, 0.14, (0.35, 0.05, 0.56), m("roof_wood", "#6e4a2c"))
    box("cart", (0.18, 0.12, 0.08), (-0.38, -0.4, 0.09), wd, 0.01)
    for i in range(5):
        sphere("stone_block", 0.04, (-0.38 + rnd.uniform(-0.06, 0.06), -0.4 + rnd.uniform(-0.03, 0.03), 0.15), m("blocks", "#d8d4cc", 0.8), (1.2, 1, 0.8), 1)
    soldier(-0.15, -0.45, "#6b5a45", 0.9, weapon=None, shield=False)


def windmill():
    st = m("stone", STONE, 0.85)
    cyl("base", 0.2, 0.55, (0, 0, 0.275), st, 12, 0.02, r2=0.15)
    cone("roof", 0.2, 0.25, (0, 0, 0.67), m("roof", ROOF_BLUE, 0.5), 12)
    hub_y = -0.2
    sail = m("sail", "#efe6d2", 0.85)
    wd = m("wood", WOOD)
    for i in range(4):
        a = i * math.pi / 2 + 0.4
        cx, cz = math.sin(a) * 0.24, 0.55 + math.cos(a) * 0.24
        s = box("sail", (0.08, 0.015, 0.42), (cx, hub_y, cz), sail, 0.004)
        s.rotation_euler.y = a
        sp = box("spar", (0.015, 0.02, 0.48), (cx * 0.95, hub_y - 0.01, 0.55 + (cz - 0.55) * 0.95), wd, 0.002)
        sp.rotation_euler.y = a
    box("door", (0.08, 0.02, 0.13), (0, -0.17, 0.065), m("door", "#4a2f19"), 0.006)


def wheat_field():
    soil = m("soil", "#7b5432", 0.95)
    wheat = m("wheat", "#e6b93c", 0.7)
    box("soil", (0.95, 0.75, 0.04), (0, 0, 0.02), soil, 0.01)
    rnd = random.Random(5)
    for i in range(7):
        for j in range(5):
            x = -0.42 + i * 0.14
            y = -0.3 + j * 0.15
            cyl("sheaf", 0.05, 0.12 + rnd.uniform(-0.02, 0.02), (x, y, 0.1), wheat, 6, 0.0, r2=0.035)
    # low wooden fence
    wd = m("wood", WOOD_L)
    for (x0, y0, x1, y1) in [(-0.5, -0.4, 0.5, -0.4), (0.5, -0.4, 0.5, 0.4), (0.5, 0.4, -0.5, 0.4), (-0.5, 0.4, -0.5, -0.4)]:
        ln = math.dist((x0, y0), (x1, y1))
        b = box("rail", (ln, 0.02, 0.02), ((x0 + x1) / 2, (y0 + y1) / 2, 0.08), wd, 0.003)
        b.rotation_euler.z = math.atan2(y1 - y0, x1 - x0)


def watchtower():
    wd = m("wood", WOOD)
    for dx, dy in [(-0.12, -0.12), (0.12, -0.12), (-0.12, 0.12), (0.12, 0.12)]:
        b = box("leg", (0.045, 0.045, 0.8), (dx, dy, 0.4), wd, 0.006)
    for z in (0.25, 0.55):
        for (x0, y0, x1, y1) in [(-0.12, -0.12, 0.12, -0.12), (0.12, -0.12, 0.12, 0.12)]:
            b = box("brace", (0.27, 0.025, 0.025), ((x0 + x1) / 2, (y0 + y1) / 2, z), wd, 0.003)
            b.rotation_euler.z = math.atan2(y1 - y0, x1 - x0)
    box("deck", (0.36, 0.36, 0.04), (0, 0, 0.8), m("planks", WOOD_L), 0.008)
    for (x0, y0, x1, y1) in [(-0.18, -0.18, 0.18, -0.18), (0.18, -0.18, 0.18, 0.18), (0.18, 0.18, -0.18, 0.18), (-0.18, 0.18, -0.18, -0.18)]:
        b = box("rail", (0.36, 0.025, 0.1), ((x0 + x1) / 2, (y0 + y1) / 2, 0.87), wd, 0.004)
        b.rotation_euler.z = math.atan2(y1 - y0, x1 - x0)
    cone("cap", 0.3, 0.26, (0, 0, 1.08), m("roof", ROOF_BLUE, 0.5), 4, 0.01).rotation_euler.z = math.pi / 4
    soldier(0, 0, ROOF_BLUE, 0.7, weapon="spear", shield=False)
    bpy.context.active_object.location.z += 0.0
    for o in list(bpy.context.scene.objects)[-8:]:
        o.location.z += 0.82


def barracks():
    square_house(0, 0.1, 0.62, 0.4, 0.3, ROOF_BLUE, STONE, 0.0, False)
    box("yard", (0.8, 0.4, 0.03), (0, -0.32, 0.015), m("dirt", "#9a7650", 0.95), 0.01)
    for x in (-0.36, 0.36):
        cyl("post", 0.02, 0.35, (x, -0.5, 0.175), m("wood", WOOD), 8, 0.004)
    banner(0.3, 0.3, ROOF_BLUE, 0.85, 0.16)
    for i in range(4):
        for j in range(2):
            soldier(-0.22 + i * 0.15, -0.26 - j * 0.15, ROOF_BLUE, 0.85)


def tree_pine():
    trunk = m("trunk", "#6a4327")
    green = m("pine", "#1f4d2a", 0.75)
    green2 = m("pine2", "#2a6233", 0.75)
    cyl("trunk", 0.035, 0.15, (0, 0, 0.075), trunk, 8, 0.005)
    for i in range(4):
        cone("tier", 0.2 - i * 0.04, 0.22, (0, 0, 0.2 + i * 0.12), green if i % 2 else green2, 9, 0.01)


def tree_round():
    trunk = m("trunk", "#6a4327")
    leaf = m("leaf", "#3b7a2e", 0.8)
    leaf2 = m("leaf2", "#4f8f37", 0.8)
    cyl("trunk", 0.035, 0.2, (0, 0, 0.1), trunk, 8, 0.005)
    sphere("crown", 0.17, (0, 0, 0.32), leaf, (1, 1, 0.9), 2)
    sphere("crown2", 0.12, (0.07, -0.05, 0.42), leaf2, (1, 1, 0.9), 2)


def rock():
    sphere("rock", 0.14, (0, 0, 0.04), m("rock", "#8d8a84", 0.9), (1.3, 1.0, 0.7), 1)
    sphere("rock2", 0.08, (0.12, 0.05, 0.03), m("rock", "#8d8a84", 0.9), (1.2, 1, 0.8), 1)


def mountain():
    rnd = random.Random(11)
    rockm = m("mrock", "#7d776e", 0.9)
    rockd = m("mrock_d", "#5f5a53", 0.9)
    snow = m("snow", "#f2f4f7", 0.6)
    for i in range(5):
        a = rnd.uniform(0, math.tau)
        r = rnd.uniform(0, 0.35)
        h = rnd.uniform(0.7, 1.3)
        rad = rnd.uniform(0.3, 0.45)
        x, y = math.cos(a) * r, math.sin(a) * r
        c = cone("peak", rad, h, (x, y, h / 2), rockm if i % 2 else rockd, 7, 0.02)
        c.rotation_euler.z = rnd.uniform(0, 1)
        cone("snowcap", rad * 0.32, h * 0.32, (x, y, h * 0.84), snow, 7, 0.01).rotation_euler.z = c.rotation_euler.z


def catapult():
    wd = m("wood", WOOD)
    box("frame", (0.36, 0.2, 0.05), (0, 0, 0.09), wd, 0.008)
    for dx in (-0.12, 0.12):
        for dy in (-0.11, 0.11):
            w = cyl("wheel", 0.06, 0.03, (dx, dy, 0.06), m("wheel", "#5a3a22"), 12, 0.004)
            w.rotation_euler.x = math.pi / 2
    for dy in (-0.07, 0.07):
        b = box("upright", (0.04, 0.04, 0.22), (0.02, dy, 0.2), wd, 0.005)
    arm = box("arm", (0.45, 0.035, 0.035), (-0.05, 0, 0.3), wd, 0.004)
    arm.rotation_euler.y = 0.6
    sphere("bucket", 0.04, (-0.22, 0, 0.42), m("stone", STONE_D), (1, 1, 0.7), 1)


def mounted_knight(color):
    def build():
        horse = m("horse", "#6b4a2f", 0.75)
        body = box("horse_body", (0.3, 0.1, 0.11), (0, 0, 0.18), horse, 0.04)
        box("horse_neck", (0.08, 0.07, 0.14), (0.15, 0, 0.26), horse, 0.03).rotation_euler.y = -0.6
        box("horse_head", (0.1, 0.06, 0.06), (0.21, 0, 0.32), horse, 0.025).rotation_euler.y = 0.3
        for dx in (-0.1, 0.1):
            for dy in (-0.035, 0.035):
                cyl("leg", 0.018, 0.14, (dx, dy, 0.07), horse, 6, 0.004)
        box("caparison", (0.24, 0.115, 0.06), (0, 0, 0.16), m("cloth" + color, color, 0.7), 0.02)
        soldier(0, 0, color, 0.8, weapon="spear", shield=True)
        for o in list(bpy.context.scene.objects)[-9:]:
            o.location.z += 0.17
    return build


def infantry_squad(color):
    def build():
        for i in range(3):
            for j in range(2):
                soldier(-0.15 + i * 0.15, -0.07 + j * 0.15 + (0.04 if i % 2 else 0), color, 1.0)
    return build


def tent(color):
    def build():
        cone("tent", 0.22, 0.32, (0, 0, 0.16), m("canvas", "#e6dcc6", 0.85), 6, 0.01)
        cone("tent_top", 0.07, 0.1, (0, 0, 0.35), m("cloth" + color, color, 0.7), 6, 0.005)
        banner(0.18, 0.1, color, 0.6, 0.12)
    return build


ASSETS = {
    "castle": castle,
    "castle_red": lambda: castle(ROOF_RED, "#b3272b"),
    "house_blue": house(ROOF_BLUE),
    "house_red": house(ROOF_RED),
    "mine": mine,
    "windmill": windmill,
    "wheat_field": wheat_field,
    "watchtower": watchtower,
    "barracks": barracks,
    "tree_pine": tree_pine,
    "tree_round": tree_round,
    "rock": rock,
    "mountain": mountain,
    "catapult": catapult,
    "knight_blue": mounted_knight(ROOF_BLUE),
    "knight_red": mounted_knight("#b3272b"),
    "squad_blue": infantry_squad(ROOF_BLUE),
    "squad_red": infantry_squad("#b3272b"),
    "banner_blue": lambda: banner(0, 0, ROOF_BLUE, 1.0, 0.26),
    "banner_red": lambda: banner(0, 0, "#b3272b", 1.0, 0.26),
    "tent_red": tent("#b3272b"),
}

only = set(sys.argv[2:])
for name, build in ASSETS.items():
    if only and name not in only:
        continue
    reset()
    build()
    export(name)
