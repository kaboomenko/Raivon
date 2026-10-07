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
    for o in [o for o in bpy.context.scene.objects if o.hide_get()]:
        bpy.data.objects.remove(o)
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
    """Armoured footman ~0.44 tall (1:6 proportions), facing −Y: tabard with emblem, cape, nasal helm, kite shield."""
    skin = m("skin", "#e8b48e", 0.7)
    steel = m("armor", "#b8bec8", 0.3, 0.7)
    cloth = m("cloth" + color, color, 0.7)
    cape_c = m("cape" + color, "#" + "".join(f"{int(int(color[i:i + 2], 16) * 0.65):02x}" for i in (1, 3, 5)), 0.8)
    dark = m("trousers", "#3a3330", 0.85)
    leather = m("boots", "#4a3322", 0.8)
    white = m("emblem", "#f4f4f4", 0.6)
    z = lambda v: v * s  # noqa: E731
    for dx in (-0.022, 0.022):
        cyl("leg", 0.017 * s, z(0.15), (x + dx * s, y, z(0.085)), dark, 8, 0.004)
        box("boot", (0.03 * s, 0.045 * s, 0.035 * s), (x + dx * s, y - 0.006 * s, z(0.018)), leather, 0.006)
    cyl("hips", 0.042 * s, z(0.05), (x, y, z(0.17)), dark, 10, 0.01)
    cyl("chest", 0.046 * s, z(0.13), (x, y, z(0.25)), steel, 12, 0.015, r2=0.05 * s)
    box("tabard", (0.07 * s, 0.012 * s, 0.17 * s), (x, y - 0.046 * s, z(0.2)), cloth, 0.004)
    box("tabard_emblem", (0.03 * s, 0.014 * s, 0.03 * s), (x, y - 0.048 * s, z(0.25)), white, 0.003)
    box("belt", (0.1 * s, 0.1 * s, 0.014 * s), (x, y, z(0.185)), leather, 0.004)
    box("cape", (0.085 * s, 0.01 * s, 0.22 * s), (x, y + 0.048 * s, z(0.2)), cape_c, 0.004)
    for dx in (-0.055, 0.055):
        sphere("pauldron", 0.024 * s, (x + dx * s, y, z(0.305)), steel, (1, 1, 0.8), 2)
        arm = cyl("arm", 0.014 * s, z(0.13), (x + dx * 1.08 * s, y - 0.01 * s, z(0.24)), steel, 8, 0.003)
        arm.rotation_euler.x = 0.25
    cyl("neck", 0.016 * s, z(0.03), (x, y, z(0.33)), skin, 8, 0.0)
    sphere("head", 0.032 * s, (x, y, z(0.365)), skin, (1, 1, 1.05), 2)
    sphere("helm", 0.036 * s, (x, y + 0.002 * s, z(0.378)), steel, (1, 1, 0.95), 2)
    cyl("helm_rim", 0.038 * s, z(0.008), (x, y, z(0.362)), steel, 12, 0.0)
    box("nasal", (0.008 * s, 0.01 * s, 0.03 * s), (x, y - 0.035 * s, z(0.36)), steel, 0.002)
    if weapon == "spear":
        cyl("spear", 0.0065 * s, z(0.62), (x + 0.07 * s, y - 0.01 * s, z(0.31)), m("wood", WOOD), 6, 0.0)
        cone("tip", 0.014 * s, z(0.06), (x + 0.07 * s, y - 0.01 * s, z(0.65)), steel, 6, 0.0)
    elif weapon == "sword":
        box("sword", (0.008 * s, 0.006 * s, 0.16 * s), (x + 0.07 * s, y - 0.02 * s, z(0.27)), steel, 0.002)
    if shield:
        sx, sy, sz = x - 0.06 * s, y - 0.045 * s, z(0.22)
        box("shield", (0.07 * s, 0.012 * s, 0.075 * s), (sx, sy, sz + 0.015 * s), cloth, 0.006)
        c = cone("shield_tip", 0.05 * s, 0.06 * s, (sx, sy, sz - 0.04 * s), cloth, 3, 0.0)
        c.rotation_euler = (math.pi, 0, math.pi / 2)
        c.scale = (0.75, 0.25, 1)
        box("shield_cross_v", (0.012 * s, 0.014 * s, 0.07 * s), (sx, sy - 0.003 * s, sz + 0.005 * s), white, 0.002)
        box("shield_cross_h", (0.05 * s, 0.014 * s, 0.012 * s), (sx, sy - 0.003 * s, sz + 0.02 * s), white, 0.002)


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


def _beam(name, p0, p1, t, mt, bevel=0.004):
    """Square timber of thickness t from p0 to p1."""
    d = [p1[i] - p0[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in d))
    o = box(name, (ln, t, t), tuple((p0[i] + p1[i]) / 2 for i in range(3)), mt, bevel)
    o.rotation_euler = (0, -math.atan2(d[2], math.hypot(d[0], d[1])), math.atan2(d[1], d[0]))
    return o


def catapult():
    """Siege mangonel: a braced timber bed on four spoked wheels, an A-frame with a straw-padded stop beam,
    a torsion skein of rope, the throwing arm with a cup and a stone, a winch at the back and spare shot."""
    wd = m("wood", WOOD)
    wl = m("planks", WOOD_L)
    dk = m("wheel", "#5a3a22")
    iron = mat("iron", "#3b3d42", 0.55, 0.6)
    rope = mat("rope", "#c9b48a", 0.95)
    straw = mat("straw", "#d8b25c", 0.95)
    rock = m("stone", STONE_D)
    # bed: two long side beams, cross members, a plank deck at the front
    for dy in (-0.075, 0.075):
        box("rail", (0.44, 0.035, 0.035), (0, dy, 0.085), wd, 0.006)
        for x in (-0.16, 0.0, 0.16):
            box("band", (0.012, 0.038, 0.038), (x, dy, 0.085), iron, 0.002)
    for x in (-0.19, -0.06, 0.08, 0.19):
        box("cross", (0.03, 0.18, 0.025), (x, 0, 0.085), wd, 0.005)
    box("deck", (0.12, 0.13, 0.012), (0.13, 0, 0.105), wl, 0.003)
    # wheels: dark rim, lighter disc, six spokes, iron hub
    for dx in (-0.14, 0.14):
        cyl("axle", 0.01, 0.24, (dx, 0, 0.06), iron, 8, 0.0).rotation_euler.x = math.pi / 2
        for dy in (-0.105, 0.105):
            r = cyl("rim", 0.06, 0.02, (dx, dy, 0.06), dk, 16, 0.004)
            r.rotation_euler.x = math.pi / 2
            d = cyl("disc", 0.045, 0.012, (dx, dy * 1.03, 0.06), wl, 14, 0.0)
            d.rotation_euler.x = math.pi / 2
            for k in range(6):
                a = k * math.pi / 3
                sp = box("spoke", (0.009, 0.016, 0.09), (dx, dy * 1.07, 0.06), dk, 0.0)
                sp.rotation_euler = (0, a, 0)
            h = cyl("hub", 0.014, 0.03, (dx, dy * 1.1, 0.06), iron, 8, 0.0)
            h.rotation_euler.x = math.pi / 2
    # A-frame uprights with diagonal braces and the padded stop beam
    for dy in (-0.075, 0.075):
        _beam("post", (0.06, dy, 0.1), (0.04, dy, 0.33), 0.034, wd)
        _beam("brace", (0.18, dy, 0.1), (0.05, dy, 0.3), 0.024, wd)
        _beam("brace2", (-0.06, dy, 0.1), (0.035, dy, 0.24), 0.022, wd)
    box("stop", (0.04, 0.2, 0.04), (0.04, 0, 0.34), wd, 0.006)
    cyl("pad", 0.03, 0.15, (0.015, 0, 0.34), straw, 10, 0.004).rotation_euler.x = math.pi / 2
    for y in (-0.05, 0.0, 0.05):
        cyl("tie", 0.032, 0.008, (0.015, y, 0.34), rope, 10, 0.0).rotation_euler.x = math.pi / 2
    # torsion skein between the side beams, the arm rising from it towards the stop beam
    cyl("skein", 0.035, 0.12, (-0.1, 0, 0.1), rope, 12, 0.006).rotation_euler.x = math.pi / 2
    for dy in (-0.075, 0.075):
        cyl("lever", 0.016, 0.03, (-0.1, dy, 0.1), iron, 8, 0.0).rotation_euler.x = math.pi / 2
        _beam("lever_bar", (-0.13, dy * 1.2, 0.1), (-0.07, dy * 1.2, 0.1), 0.012, iron, 0.0)
    _beam("arm", (-0.1, 0, 0.1), (-0.02, 0, 0.42), 0.032, wl)
    for f in (0.3, 0.6):
        box("arm_band", (0.04, 0.04, 0.012), (-0.1 + 0.08 * f, 0, 0.1 + 0.32 * f), iron, 0.002).rotation_euler.y = -0.24
    cyl("cup", 0.05, 0.035, (-0.04, 0, 0.45), wd, 12, 0.004, r2=0.035).rotation_euler.y = 0.4
    sphere("shot", 0.038, (-0.045, 0, 0.475), rock, (1, 1, 0.9), 2)
    # winch at the back: drum with a rope to the arm and two crank handles
    cyl("drum", 0.022, 0.15, (-0.2, 0, 0.125), wl, 10, 0.003).rotation_euler.x = math.pi / 2
    for dy in (-0.075, 0.075):
        box("winch_post", (0.025, 0.02, 0.06), (-0.2, dy, 0.11), wd, 0.003)
        for k in range(2):
            hd = box("handle", (0.008, 0.008, 0.09), (-0.2, dy * 1.25, 0.125), wd, 0.0)
            hd.rotation_euler = (0, k * math.pi / 2, 0)
    _beam("winch_rope", (-0.2, 0, 0.14), (-0.075, 0, 0.18), 0.008, rope, 0.0)
    # spare shot beside the machine
    for (x, y, z, r) in ((0.05, 0.2, 0.03, 0.032), (0.11, 0.21, 0.03, 0.03), (0.08, 0.17, 0.028, 0.028), (0.08, 0.2, 0.075, 0.03)):
        sphere("pile", r, (x, y, z), rock, (1, 1, 0.9), 2)


def cannon():
    """Field gun of the bicorne era: a bronze barrel with reinforcing rings on a two-cheek trail carriage,
    tall spoked wheels, a rammer, a powder keg and a pyramid of shot."""
    wd = m("wood", "#6e4a2c")
    dk = m("wheel", "#4a3020")
    iron = mat("iron", "#3b3d42", 0.55, 0.6)
    bronze = mat("bronze", "#b0823a", 0.35, 0.85)
    # trail carriage: two cheeks running down to the ground behind, transoms, an iron trail plate
    for dy in (-0.04, 0.04):
        _beam("cheek", (0.08, dy, 0.13), (-0.26, dy * 0.6, 0.02), 0.03, wd)
    for f in (0.15, 0.5):
        x = 0.08 - 0.34 * f
        box("transom", (0.025, 0.07, 0.02), (x, 0, 0.13 - 0.11 * f), wd, 0.004)
    box("trail_plate", (0.05, 0.05, 0.012), (-0.255, 0, 0.012), iron, 0.002)
    cyl("handspike_ring", 0.012, 0.008, (-0.24, 0, 0.035), iron, 8, 0.0).rotation_euler.x = math.pi / 2
    # wheels: tall, twelve spokes, iron tyre and hub
    cyl("axle", 0.012, 0.2, (0.05, 0, 0.1), iron, 8, 0.0).rotation_euler.x = math.pi / 2
    for dy in (-0.085, 0.085):
        t = cyl("tyre", 0.1, 0.016, (0.05, dy, 0.1), iron, 20, 0.003)
        t.rotation_euler.x = math.pi / 2
        r = cyl("felloe", 0.092, 0.02, (0.05, dy * 1.01, 0.1), dk, 20, 0.0)
        r.rotation_euler.x = math.pi / 2
        cyl("inner", 0.078, 0.022, (0.05, dy * 1.02, 0.1), m("planks", "#9c7a52"), 18, 0.0).rotation_euler.x = math.pi / 2
        for k in range(6):
            sp = box("spoke", (0.008, 0.026, 0.16), (0.05, dy * 1.06, 0.1), dk, 0.0)
            sp.rotation_euler = (0, k * math.pi / 6, 0)
        h = cyl("hub", 0.022, 0.05, (0.05, dy * 1.1, 0.1), dk, 10, 0.003)
        h.rotation_euler.x = math.pi / 2
        cyl("cap", 0.014, 0.015, (0.05, dy * 1.4, 0.1), iron, 8, 0.0).rotation_euler.x = math.pi / 2
    # barrel along +X, slightly raised; breech, rings, muzzle swell and the cascabel knob
    el = -0.1

    def on_axis(x):
        return (x, 0, 0.165 + math.sin(-el) * x)
    b = cyl("barrel", 0.03, 0.32, on_axis(0.08), bronze, 14, 0.004, r2=0.022)
    b.rotation_euler = (0, math.pi / 2 + el, 0)
    for x, r in ((-0.06, 0.034), (0.0, 0.03), (0.1, 0.026), (0.2, 0.026)):
        o = cyl("ring", r, 0.014, on_axis(x), bronze, 14, 0.002)
        o.rotation_euler = (0, math.pi / 2 + el, 0)
    mz = cyl("muzzle", 0.028, 0.03, on_axis(0.235), bronze, 14, 0.003)
    mz.rotation_euler = (0, math.pi / 2 + el, 0)
    sphere("breech", 0.03, on_axis(-0.075), bronze, (0.7, 1, 1), 2)
    sphere("cascabel", 0.013, on_axis(-0.11), bronze, (1, 1, 1), 1)
    cyl("bore", 0.014, 0.004, on_axis(0.252), mat("bore", "#141414", 0.9), 10, 0.0).rotation_euler = (0, math.pi / 2 + el, 0)
    for dy in (-0.032, 0.032):
        cyl("trunnion", 0.01, 0.02, (0.02, dy, 0.165), bronze, 8, 0.0).rotation_euler.x = math.pi / 2
    # crew kit: rammer leaning on the wheel, a powder keg, a pyramid of shot
    _beam("rammer", (-0.05, 0.14, 0.0), (0.2, 0.12, 0.05), 0.008, m("planks", "#a8743f"), 0.0)
    cyl("sponge", 0.016, 0.04, (0.215, 0.12, 0.053), mat("sponge", "#3a2f28", 0.95), 8, 0.0).rotation_euler.y = math.pi / 2 - 0.2
    cyl("keg", 0.035, 0.07, (-0.14, -0.13, 0.035), wd, 12, 0.006)
    for z in (0.012, 0.058):
        cyl("hoop", 0.037, 0.008, (-0.14, -0.13, z), iron, 12, 0.0)
    shot = mat("shot", "#2b2c2f", 0.5, 0.7)
    for (x, y, z) in ((0.2, -0.12, 0.016), (0.232, -0.12, 0.016), (0.216, -0.092, 0.016), (0.216, -0.11, 0.042)):
        sphere("ball", 0.016, (x, y, z), shot, (1, 1, 1), 2)


def howitzer():
    """Field howitzer of the trench era: an olive barrel with a recoil cylinder over the cradle, a gun shield,
    split trails with spades, pressed-steel wheels with rubber tyres, shells and a crate."""
    od = mat("olive", "#5b6436", 0.7, 0.2)
    od_d = mat("olive_d", "#454c2a", 0.7, 0.2)
    steel = mat("steel", "#3d4044", 0.5, 0.6)
    tyre = mat("tyre", "#1f1f21", 0.9)
    # split trails spreading back to the spades
    for sy in (-1, 1):
        _beam("trail", (0.0, sy * 0.03, 0.1), (-0.3, sy * 0.13, 0.02), 0.03, od_d)
        box("spade", (0.02, 0.06, 0.05), (-0.31, sy * 0.135, 0.03), steel, 0.004)
    # axle, wheels with rubber tyres and pressed-steel discs
    cyl("axle", 0.014, 0.24, (0.0, 0, 0.09), steel, 8, 0.0).rotation_euler.x = math.pi / 2
    for sy in (-1, 1):
        t = cyl("tyre", 0.09, 0.04, (0.0, sy * 0.115, 0.09), tyre, 18, 0.008)
        t.rotation_euler.x = math.pi / 2
        d = cyl("disc", 0.065, 0.044, (0.0, sy * 0.115, 0.09), od, 16, 0.003)
        d.rotation_euler.x = math.pi / 2
        h = cyl("hub", 0.024, 0.05, (0.0, sy * 0.12, 0.09), steel, 8, 0.002)
        h.rotation_euler.x = math.pi / 2
        for k in range(5):
            a = k * math.tau / 5
            cyl("bolt", 0.006, 0.05, (math.cos(a) * 0.04, sy * 0.12, 0.09 + math.sin(a) * 0.04), steel, 6, 0.0).rotation_euler.x = math.pi / 2
    # cradle, barrel and recoil cylinder, raised to a firing angle
    el = 0.32

    def at(x, z=0.0):
        return (x * math.cos(el) - z * math.sin(el) + 0.02, 0, 0.16 + x * math.sin(el) + z * math.cos(el))
    box("cradle", (0.1, 0.07, 0.06), (0.02, 0, 0.15), od, 0.008)
    b = cyl("barrel", 0.024, 0.42, at(0.16), od, 14, 0.003, r2=0.02)
    b.rotation_euler = (0, math.pi / 2 - el, 0)
    r = cyl("recoil", 0.018, 0.22, at(0.06, 0.036), od_d, 12, 0.003)
    r.rotation_euler = (0, math.pi / 2 - el, 0)
    m_ = cyl("muzzle_brake", 0.03, 0.05, at(0.37), steel, 12, 0.003)
    m_.rotation_euler = (0, math.pi / 2 - el, 0)
    box("breech", (0.07, 0.06, 0.06), at(-0.06), steel, 0.006).rotation_euler.y = -el
    # gun shield with a sight window and a riveted rim
    sh = box("shield", (0.012, 0.24, 0.16), (0.1, 0, 0.2), od, 0.004)
    sh.rotation_euler.y = -0.15
    box("shield_top", (0.012, 0.2, 0.05), (0.095, 0, 0.3), od, 0.004).rotation_euler.y = -0.35
    box("sight", (0.014, 0.04, 0.025), (0.104, 0.06, 0.24), mat("glass", "#1a1d22", 0.3), 0.0)
    # shells, an ammo crate and a camo net roll on the trail
    brass = mat("brass", "#c9a043", 0.35, 0.8)
    for k in range(3):
        x = 0.17 + k * 0.035
        cyl("case", 0.013, 0.07, (x, -0.17, 0.035), brass, 10, 0.0)
        cone("tip", 0.013, 0.03, (x, -0.17, 0.085), steel, 10, 0.0)
    box("crate", (0.1, 0.07, 0.055), (0.2, 0.17, 0.028), mat("crate", "#6b5a3a", 0.85), 0.006)
    cyl("net", 0.028, 0.16, (-0.16, 0, 0.085), mat("net", "#4f5a32", 0.95), 10, 0.01).rotation_euler.x = math.pi / 2


def rocket_launcher():
    """Late-era launcher: a six-wheeled composite chassis with a cab, a raised pod of rocket tubes with glowing
    mouths, a radar mast and side lights, in the white-and-graphite look of the DL8 troops."""
    comp = mat("composite", "#e3e8ee", 0.4)
    trim = mat("comptrim", "#3e4550", 0.5)
    tyre = mat("tyre", "#1f1f21", 0.9)
    cyan = mat("cyan", "#14d2ff", 0.4, 0.0, "#14d2ff", 3.0)
    glass = mat("glass", "#1b2533", 0.2)
    # chassis and wheels
    box("hull", (0.42, 0.17, 0.07), (0, 0, 0.1), comp, 0.012)
    box("skirt", (0.43, 0.175, 0.025), (0, 0, 0.065), trim, 0.006)
    for x in (-0.14, 0.0, 0.14):
        for sy in (-1, 1):
            w = cyl("wheel", 0.045, 0.035, (x, sy * 0.09, 0.045), tyre, 14, 0.006)
            w.rotation_euler.x = math.pi / 2
            h = cyl("rim", 0.024, 0.038, (x, sy * 0.09, 0.045), trim, 10, 0.0)
            h.rotation_euler.x = math.pi / 2
    for sy in (-1, 1):
        box("light_strip", (0.36, 0.006, 0.01), (0, sy * 0.088, 0.11), cyan, 0.0)
    # cab at the front with a dark visor
    box("cab", (0.11, 0.16, 0.09), (0.15, 0, 0.18), comp, 0.016)
    box("visor", (0.02, 0.13, 0.04), (0.205, 0, 0.19), glass, 0.004)
    box("cab_roof", (0.08, 0.12, 0.012), (0.145, 0, 0.23), trim, 0.003)
    # launcher pod: a turntable, two arms and a 3×3 block of tubes tilted up toward the front
    cyl("turntable", 0.06, 0.03, (-0.07, 0, 0.15), trim, 16, 0.004)
    el = 0.5
    for sy in (-1, 1):
        a = box("arm", (0.03, 0.015, 0.1), (-0.07, sy * 0.06, 0.2), trim, 0.003)
        a.rotation_euler.y = -0.2
    pod = box("pod", (0.2, 0.12, 0.11), (-0.06, 0, 0.27), comp, 0.01)
    pod.rotation_euler.y = -el
    cx, cz = -0.06 + math.cos(el) * 0.1, 0.27 + math.sin(el) * 0.1
    for i in range(3):
        for j in range(3):
            off_y = (i - 1) * 0.034
            off_n = (j - 1) * 0.032
            px = cx - math.sin(el) * off_n
            pz = cz + math.cos(el) * off_n
            t = cyl("tube", 0.013, 0.012, (px, off_y, pz), trim, 10, 0.0)
            t.rotation_euler.y = math.pi / 2 - el
            g = cyl("tube_glow", 0.009, 0.014, (px + 0.002, off_y, pz + 0.001), cyan, 8, 0.0)
            g.rotation_euler.y = math.pi / 2 - el
    box("pod_stripe", (0.2, 0.124, 0.014), (-0.06, 0, 0.27), trim, 0.0).rotation_euler.y = -el
    # radar mast behind the cab
    cyl("mast", 0.006, 0.1, (0.07, 0.05, 0.2), trim, 6, 0.0)
    d = cyl("dish", 0.03, 0.008, (0.07, 0.05, 0.255), comp, 12, 0.002)
    d.rotation_euler = (0.9, 0, 0.5)
    sphere("beacon", 0.008, (0.07, 0.05, 0.262), cyan, (1, 1, 1), 1)


def mounted_knight(color):
    def build():
        horse = m("horse", "#6b4a2f", 0.75)
        mane = m("mane", "#2a1d14", 0.85)
        cloth = m("cloth" + color, color, 0.7)
        box("horse_body", (0.36, 0.11, 0.13), (0, 0, 0.27), horse, 0.05)
        neck = box("horse_neck", (0.09, 0.075, 0.18), (0.17, 0, 0.36), horse, 0.035)
        neck.rotation_euler.y = -0.55
        head = box("horse_head", (0.14, 0.065, 0.065), (0.25, 0, 0.43), horse, 0.028)
        head.rotation_euler.y = 0.55
        mn = box("mane", (0.1, 0.03, 0.05), (0.15, 0, 0.42), mane, 0.015)
        mn.rotation_euler.y = -0.55
        tail = cone("tail", 0.03, 0.16, (-0.2, 0, 0.24), mane, 6, 0.0)
        tail.rotation_euler.y = 2.6
        for dx in (-0.13, 0.13):
            for dy in (-0.035, 0.035):
                cyl("leg", 0.017, 0.21, (dx, dy, 0.105), horse, 8, 0.004)
                cyl("hoof", 0.02, 0.025, (dx, dy, 0.012), mane, 8, 0.0)
        box("caparison", (0.3, 0.125, 0.09), (0, 0, 0.24), cloth, 0.03)
        box("caparison_emblem", (0.06, 0.128, 0.05), (0, 0, 0.25), m("emblem", "#f4f4f4", 0.6), 0.01)
        soldier(0, 0, color, 0.85, weapon="spear", shield=True)
        for o in list(bpy.context.scene.objects):
            if o.name.startswith(("leg", "boot")) and o.location.z < 0.2 and abs(o.location.x) < 0.05:
                o.hide_set(True)
                o.select_set(False)
        for o in [o for o in bpy.context.scene.objects if o.location.z < 0.7 and not o.name.startswith(("horse", "mane", "tail", "leg", "hoof", "caparison"))]:
            o.location.z += 0.2
    return build


def infantry_squad(color):
    def build():
        for i in range(4):
            for j in range(3):
                soldier(-0.2 + i * 0.13 + (0.06 if j % 2 else 0), -0.12 + j * 0.13, color, 0.95)
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
    "castle_green": lambda: castle("#2f7d3a", "#2f8f3f"),
    "house_green": house("#3a7d34"),
    "banner_green": lambda: banner(0, 0, "#2f8f3f", 1.0, 0.26),
    "squad_green": infantry_squad("#2f8f3f"),
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
    "cannon": cannon,
    "howitzer": howitzer,
    "rocket_launcher": rocket_launcher,
    "knight_blue": mounted_knight(ROOF_BLUE),
    "knight_red": mounted_knight("#b3272b"),
    "squad_blue": infantry_squad(ROOF_BLUE),
    "squad_red": infantry_squad("#b3272b"),
    "banner_blue": lambda: banner(0, 0, ROOF_BLUE, 1.0, 0.26),
    "banner_red": lambda: banner(0, 0, "#b3272b", 1.0, 0.26),
    "tent_red": tent("#b3272b"),
}

if __name__ == "__main__":  # importable by evolution_assets.py (shared bake/export helpers)
    only = set(sys.argv[2:])
    for name, build in ASSETS.items():
        if only and name not in only:
            continue
        reset()
        build()
        export(name)
