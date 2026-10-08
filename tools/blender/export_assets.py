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


# ------------------------------------------------------------------ low-poly helpers for the siege engines, the bridge
# and the war banners: one bevel segment (or crisp flat/edge-split shading), open spoked wheels, coursed masonry.


def _bx(name, size, loc, mt, bev=0.0, rot=None):
    """Box with a single-segment bevel (44 tris) or none (12 tris, flat shaded)."""
    o = box(name, size, loc, mt, bev)
    if bev > 0:
        o.modifiers["bevel"].segments = 1
    else:
        for p in o.data.polygons:
            p.use_smooth = False
    if rot:
        o.rotation_euler = rot
    return o


def _cy(name, r, h, loc, mt, verts=8, r2=None, rot=None):
    """Cylinder with smooth sides and crisp caps (edge split), no bevel."""
    o = cyl(name, r, h, loc, mt, verts, 0.0, r2)
    es = o.modifiers.new("split", "EDGE_SPLIT")
    es.split_angle = math.radians(70)
    if rot:
        o.rotation_euler = rot
    return o


YROT = (math.pi / 2, 0, 0)  # a cylinder lying along Y (axles, wheels)
XROT = (0, math.pi / 2, 0)  # a cylinder lying along X


def _ico(name, r, loc, mt, scale=(1, 1, 1), sub=1, jitter=0.0, seed=0, smooth=True):
    """Ico sphere (20 / 80 tris); jitter roughens it into a hewn stone (flat shaded)."""
    o = sphere(name, r, loc, mt, scale, sub)
    if jitter > 0:
        rnd = random.Random(seed)
        for v in o.data.vertices:
            v.co *= 1.0 + rnd.uniform(-jitter, jitter)
    for p in o.data.polygons:
        p.use_smooth = smooth
    return o


def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return n


def _mesh(name, verts, faces, mt, outward, smooth=None):
    """Mesh from raw faces; each face is turned so its normal agrees with outward(face_index, centre)."""
    fixed = []
    for i, f in enumerate(faces):
        pts = [verts[k] for k in f]
        c = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
        want = outward(i, c)
        n = _newell(pts)
        fixed.append(tuple(reversed(f)) if sum(n[j] * want[j] for j in range(3)) < 0 else tuple(f))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], fixed)
    me.validate()
    o = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(o)
    me.materials.append(mt)
    for i, p in enumerate(me.polygons):
        p.use_smooth = bool(smooth and smooth[i])
    return o


def _ring(name, r_out, r_in, w, loc, mt, n=14, rz=0.0, surfaces=(0, 1, 2, 3)):
    """Annulus around local Y (a wheel rim or an iron tyre). Surfaces: 0 outer, 1 +Y side, 2 inner, 3 −Y side;
    each has its own vertices so the round faces shade smooth and the flat sides stay crisp."""
    prof = {0: ((r_out, -w / 2), (r_out, w / 2)), 1: ((r_out, w / 2), (r_in, w / 2)),
            2: ((r_in, w / 2), (r_in, -w / 2)), 3: ((r_in, -w / 2), (r_out, -w / 2))}
    verts, faces, smooth, want = [], [], [], []
    for si in surfaces:
        pa, pb = prof[si]
        base = len(verts)
        for k in range(n):
            a = math.tau * k / n
            for (r, y) in (pa, pb):
                verts.append((r * math.cos(a), y, r * math.sin(a)))
        for k in range(n):
            k2 = (k + 1) % n
            faces.append((base + 2 * k, base + 2 * k2, base + 2 * k2 + 1, base + 2 * k + 1))
            smooth.append(si in (0, 2))
            am = math.tau * (k + 0.5) / n
            radial = (math.cos(am), 0.0, math.sin(am))
            want.append({0: radial, 1: (0, 1, 0), 2: tuple(-v for v in radial), 3: (0, -1, 0)}[si])
    o = _mesh(name, verts, faces, mt, lambda i, c: want[i], smooth)
    o.location = loc
    o.rotation_euler.z = rz
    return o


def _extrude_xz(name, outline, y0, y1, mt):
    """An outline in XZ (any winding) extruded along Y from y0 to y1: one closed solid."""
    area = sum(outline[i][0] * outline[(i + 1) % len(outline)][1] - outline[(i + 1) % len(outline)][0] * outline[i][1]
               for i in range(len(outline)))
    if area < 0:
        outline = list(reversed(outline))
    nv = len(outline)
    verts = [(x, y0, z) for (x, z) in outline] + [(x, y1, z) for (x, z) in outline]
    faces = [tuple(range(nv)), tuple(range(nv, 2 * nv))]
    faces += [(i, (i + 1) % nv, nv + (i + 1) % nv, nv + i) for i in range(nv)]

    def outward(i, c):
        if i == 0:
            return (0, -1, 0)
        if i == 1:
            return (0, 1, 0)
        a, b = outline[i - 2], outline[(i - 1) % nv]
        return (b[1] - a[1], 0, -(b[0] - a[0]))  # CCW outline: the edge's right-hand side is outside
    return _mesh(name, verts, faces, mt, outward)


def _rbeam(name, p0, p1, t, mt, bev=0.0, h=None):
    """Timber of section t × h (h along the beam's local up) from p0 to p1."""
    d = [p1[i] - p0[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in d))
    o = _bx(name, (ln, t, h or t), tuple((p0[i] + p1[i]) / 2 for i in range(3)), mt, bev)
    o.rotation_euler = (0, -math.atan2(d[2], math.hypot(d[0], d[1])), math.atan2(d[1], d[0]))
    return o


def _spoked_wheel(name, c, r, w, spokes, wood, dark, iron, rim_t=0.016, hub_r=None, cap=True, n=14):
    """An open wooden wheel on an axle along Y: felloe ring, iron tyre, spokes through the hub, iron hub cap."""
    x, y, z = c
    _ring(name + "_felloe", r - 0.003, r - rim_t, w, c, dark, n, surfaces=(1, 2, 3))
    _ring(name + "_tyre", r + 0.002, r - 0.005, w * 0.82, c, iron, n, surfaces=(0, 1, 3))
    for k in range(spokes // 2):
        sp = _bx(name + "_spoke", (w * 0.32, w * 0.42, 2 * (r - rim_t * 0.6)), c, wood)
        sp.rotation_euler = (0, k * math.tau / spokes + math.pi / spokes, 0)
    hr = hub_r or r * 0.24
    _cy(name + "_hub", hr, w * 1.7, c, dark, 8, rot=YROT)
    if cap:
        sy = 1 if y >= 0 else -1
        _cy(name + "_cap", hr * 0.62, w * 0.5, (x, y + sy * w * 0.95, z), iron, 6, rot=YROT)


def _timber(color, scale=2.6, dark=0.74):
    """Wood with a soft grain fine enough to read on beams a few centimetres thick (kit's wood bands are sized for
    whole buildings, and scaled up they turn into zebra stripes)."""
    key = ("timber", color, scale, dark)
    if key in kit._MATS:
        return kit._MATS[key]
    mt = bpy.data.materials.new(f"timber_{color}")
    mt.use_nodes = True
    nt = mt.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 3.0
    wave.inputs["Detail"].default_value = 2.0
    wave.inputs["Detail Roughness"].default_value = 0.4
    nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    base = kit.srgb(color)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[0].color = (*tuple(c * dark for c in base), 1)
    ramp.color_ramp.elements[1].position = 0.85
    ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 0.18
    nt.links.new(ramp.outputs["Color"], mul.inputs["A"])
    nt.links.new(noise.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    kit._MATS[key] = mt
    return mt


def _masonry(color, scale=1.0, mortar=0.03):
    """Dressed stone courses on every face: the brick pattern runs in plan on tops and along X+Y / Z on walls
    (kit's stone texture is planar in XY, so on walls it smears into stripes)."""
    key = ("masonry", color, scale, mortar)
    if key in kit._MATS:
        return kit._MATS[key]
    mt = bpy.data.materials.new(f"masonry_{color}")
    mt.use_nodes = True
    nt = mt.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sp.inputs["Vector"])
    sn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Normal"], sn.inputs["Vector"])
    ab = nt.nodes.new("ShaderNodeMath")
    ab.operation = "ABSOLUTE"
    nt.links.new(sn.outputs["Z"], ab.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    gt.inputs[1].default_value = 0.7
    nt.links.new(ab.outputs[0], gt.inputs[0])
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    nt.links.new(sp.outputs["X"], add.inputs[0])
    nt.links.new(sp.outputs["Y"], add.inputs[1])
    side = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(add.outputs[0], side.inputs["X"])
    nt.links.new(sp.outputs["Z"], side.inputs["Y"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "VECTOR"
    nt.links.new(gt.outputs[0], mix.inputs["Factor"])
    nt.links.new(side.outputs["Vector"], mix.inputs[4])
    nt.links.new(tc.outputs["Object"], mix.inputs[5])
    base = kit.srgb(color)
    br = nt.nodes.new("ShaderNodeTexBrick")
    nt.links.new(mix.outputs[1], br.inputs["Vector"])
    br.inputs["Color1"].default_value = (*base, 1)
    br.inputs["Color2"].default_value = (*tuple(c * 0.74 for c in base), 1)
    br.inputs["Mortar"].default_value = (*tuple(c * 0.42 for c in base), 1)
    br.inputs["Scale"].default_value = 7.0 * scale
    br.inputs["Mortar Size"].default_value = mortar
    br.inputs["Brick Width"].default_value = 0.62
    br.inputs["Row Height"].default_value = 0.3
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 30.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 0.3
    nt.links.new(br.outputs["Color"], mul.inputs["A"])
    nt.links.new(noise.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    kit._MATS[key] = mt
    return mt


def _camo(colors, scale=16.0):
    """Disruptive paint of the trench era: hard-edged blotches of three or four tones."""
    key = ("camo", tuple(colors), scale)
    if key in kit._MATS:
        return kit._MATS[key]
    mt = bpy.data.materials.new("camo")
    mt.use_nodes = True
    nt = mt.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 1.5
    noise.inputs["Roughness"].default_value = 0.4
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    stops = [0.0, 0.43, 0.5, 0.57][:len(colors)]
    els[0].position, els[0].color = stops[0], (*kit.srgb(colors[0]), 1)
    els[1].position, els[1].color = stops[1], (*kit.srgb(colors[1]), 1)
    for s, ccol in zip(stops[2:], colors[2:]):
        e = els.new(s)
        e.color = (*kit.srgb(ccol), 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
    kit._MATS[key] = mt
    return mt


def _bolts(pts, mt, s=0.008, axis="y"):
    """Square bolt heads (12 tris each) standing proud of a face; axis is the face normal."""
    t = s * 0.6
    size = {"x": (t, s, s), "y": (s, t, s), "z": (s, s, t)}[axis]
    for p in pts:
        _bx("bolt", size, p, mt)


def catapult():
    """Siege mangonel after the engines on the front in reference frame 1: a heavy timber bed on four open spoked
    wheels with iron tyres, two tall cross-braced trusses carrying a massive stop beam with a straw pad, iron plates
    with bright bolt heads at the joints, a rope torsion skein with iron ratchets and levers, the throwing arm with a
    bucket and a stone, a capstan winch with its rope at the back and a pile of hewn shot beside it."""
    wd = _timber(WOOD)
    wl = _timber(WOOD_L)
    dk = _timber("#5a3a22")
    iron = mat("iron", "#3b3d42", 0.55, 0.6)
    bolt = mat("bolt", "#e2dccb", 0.5)
    rope = mat("rope", "#c9b48a", 0.95)
    rope_d = mat("rope_d", "#9c8560", 0.95)
    straw = mat("straw", "#d8b25c", 0.95)
    rock = m("rock", "#a7a197")
    B = 0.006  # bevel of the big timbers
    RY = 0.085  # side rails and trusses
    # bed: two long side rails, four cross beams, iron straps over the axles
    for sy in (-1, 1):
        _bx("rail", (0.47, 0.04, 0.042), (0, sy * RY, 0.1), wd, B)
        for x in (-0.16, 0.16):
            _bx("strap", (0.016, 0.046, 0.05), (x, sy * RY, 0.098), iron)
    for x in (-0.215, -0.06, 0.06, 0.215):
        _bx("cross", (0.034, 0.22, 0.03), (x, 0, 0.1), wd, B)
    _bx("floor", (0.1, 0.13, 0.01), (-0.17, 0, 0.12), wl)
    # four open wheels on iron axles
    for x in (-0.16, 0.16):
        _cy("axle", 0.011, 0.32, (x, 0, 0.072), iron, 8, rot=YROT)
        for sy in (-1, 1):
            _spoked_wheel("wheel", (x, sy * 0.148, 0.072), 0.072, 0.024, 8, wl, dk, iron, rim_t=0.017, n=14)
    # the two trusses: front and back posts leaning in under the stop beam, a mid rail, an X of braces below
    front = ((0.2, 0.11), (0.07, 0.42))
    back = ((-0.1, 0.11), (0.025, 0.42))

    def on(post, z):
        (x0, z0), (x1, z1) = post
        return x0 + (x1 - x0) * (z - z0) / (z1 - z0)
    for sy in (-1, 1):
        y = sy * RY
        for (x0, z0), (x1, z1) in (front, back):
            _rbeam("post", (x0, y, z0), (x1, y, z1), 0.036, wd, B)
        _bx("mid_rail", (0.21, 0.03, 0.03), (0.05, y, 0.27), wd, B)
        _rbeam("brace", (0.18, y, 0.125), (-0.03, y, 0.26), 0.022, wl)
        _rbeam("brace", (-0.08, y, 0.125), (0.125, y, 0.26), 0.018, wl)
        _rbeam("tie", (on(front, 0.36) - 0.01, y, 0.36), (on(back, 0.36) + 0.01, y, 0.36), 0.024, wd)
        # iron plates over the joints, each with bright bolt heads
        for x in (0.2, -0.1):
            _bx("plate", (0.05, 0.006, 0.046), (x, y + sy * 0.023, 0.1), iron)
            _bolts([(x + dx, y + sy * 0.027, 0.1 + dz) for dx in (-0.015, 0.015) for dz in (-0.013, 0.013)], bolt)
        for x in (on(front, 0.27), on(back, 0.27)):
            _bx("plate", (0.042, 0.006, 0.042), (x, y + sy * 0.021, 0.27), iron)
            _bolts([(x - 0.011, y + sy * 0.025, 0.281), (x + 0.011, y + sy * 0.025, 0.259)], bolt)
    # the stop beam on top with iron end caps and a straw pad lashed to its back
    _bx("stop", (0.052, 0.25, 0.05), (0.048, 0, 0.44), wd, B)
    for sy in (-1, 1):
        _bx("stop_cap", (0.058, 0.008, 0.056), (0.048, sy * 0.127, 0.44), iron)
        _bolts([(0.048 + dx, sy * 0.132, 0.44) for dx in (-0.015, 0.015)], bolt)
    _cy("pad", 0.026, 0.15, (0.0, 0, 0.435), straw, 10, rot=YROT)
    for y in (-0.045, 0.0, 0.045):
        _cy("tie", 0.0275, 0.009, (0.0, y, 0.435), rope_d, 10, rot=YROT)
    # torsion skein between the rails, iron ratchets with crossed levers outside them
    _cy("skein", 0.034, 0.13, (-0.1, 0, 0.1), rope, 10, rot=YROT)
    for y in (-0.03, 0.03):
        _cy("skein_band", 0.036, 0.012, (-0.1, y, 0.1), rope_d, 10, rot=YROT)
    for sy in (-1, 1):
        _cy("ratchet", 0.03, 0.01, (-0.1, sy * 0.111, 0.1), iron, 8, rot=YROT)
        for a in (0.4, 0.4 + math.pi / 2):
            _bx("lever", (0.007, 0.007, 0.08), (-0.1, sy * 0.119, 0.1), iron, rot=(0, a, 0))
    # the throwing arm resting on the pad, two iron bands, the bucket with a stone in it
    p0, p1 = (-0.1, 0, 0.1), (-0.035, 0, 0.455)

    def arm_at(t):
        return tuple(p0[i] + (p1[i] - p0[i]) * t for i in range(3))
    _rbeam("arm", p0, p1, 0.03, wl, B, h=0.034)
    for t in (0.36, 0.68):
        _rbeam("arm_band", arm_at(t - 0.03), arm_at(t + 0.03), 0.036, iron, h=0.04)
        a = arm_at(t)
        _bolts([(a[0], sy * 0.02, a[2]) for sy in (-1, 1)], bolt)
    tilt = math.atan2(p1[0] - p0[0], p1[2] - p0[2])
    ax = (math.sin(tilt), 0, math.cos(tilt))
    cc = (-0.031, 0, 0.472)
    _cy("bucket", 0.032, 0.034, cc, dk, 10, r2=0.047, rot=(0, tilt, 0))
    _cy("bucket_in", 0.041, 0.004, tuple(cc[i] + ax[i] * 0.014 for i in range(3)), mat("dark", "#2c1d12", 0.9), 10, rot=(0, tilt, 0))
    _cy("bucket_hoop", 0.043, 0.008, tuple(cc[i] + ax[i] * 0.008 for i in range(3)), iron, 10, rot=(0, tilt, 0))
    _ico("shot", 0.031, tuple(cc[i] + ax[i] * 0.036 for i in range(3)), rock, (1, 1, 0.92), 2, 0.1, 7, smooth=False)
    # capstan winch at the back: posts, a drum with rope coils, star handles, the rope up to the arm
    for sy in (-1, 1):
        _bx("winch_post", (0.026, 0.026, 0.075), (-0.205, sy * RY, 0.155), wd, 0.004)
        _cy("capstan", 0.017, 0.022, (-0.205, sy * 0.11, 0.165), dk, 8, rot=YROT)
        for a in (0.3, 0.3 + math.pi / 2):
            _bx("handle", (0.008, 0.008, 0.09), (-0.205, sy * 0.118, 0.165), wl, rot=(0, a, 0))
    _cy("drum", 0.02, 0.21, (-0.205, 0, 0.165), wl, 8, rot=YROT)
    for y in (-0.03, 0.025):
        _cy("coil", 0.025, 0.035, (-0.205, y, 0.165), rope, 10, rot=YROT)
    _rbeam("winch_rope", (-0.2, 0, 0.188), arm_at(0.3), 0.007, rope)
    # spare shot: hewn stones piled beside the engine
    for i, (x, y, z, r) in enumerate(((0.0, 0.205, 0.026, 0.032), (0.066, 0.212, 0.026, 0.033), (0.032, 0.25, 0.024, 0.03),
                                      (0.03, 0.185, 0.024, 0.028), (0.034, 0.215, 0.072, 0.031))):
        _ico("pile", r, (x, y, z), rock, (1, 1, 0.88), 2, 0.12, 11 + i, smooth=False)


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
    mouths, a radar mast and side lights, in the gunmetal-and-graphite look of the DL8 troops."""
    comp = mat("gunmetal", "#68707b", 0.4)  # gunmetal like frame 5's machines
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


def bridge():
    """Stone arch bridge along X (length 0.5, deck width 0.15): an arched span over the river, parapets with
    coping, cutwaters and a cobbled deck (the bridges over the rivers in the reference frames)."""
    st = m("stone", STONE)
    std = m("stone_d", STONE_D)
    cob = m("cobble", "#a59b8a")
    def profile(name, outline, y0, y1, mt):
        """An outline in XZ extruded along Y from y0 to y1 (one solid: front, back and side faces)."""
        nv = len(outline)
        verts = [(x, y0, z) for (x, z) in outline] + [(x, y1, z) for (x, z) in outline]
        faces = [tuple(range(nv - 1, -1, -1)), tuple(range(nv, 2 * nv))]
        faces += [(i, (i + 1) % nv, nv + (i + 1) % nv, nv + i) for i in range(nv)]
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.validate()
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        me.materials.append(mt)
        return o
    arch = [(-math.cos(math.pi * k / 12) * 0.15, math.sin(math.pi * k / 12) * 0.1) for k in range(13)]
    # the span: masonry from the banks up to the deck with an arched opening through it
    body = [(-0.25, 0.0)] + [(x, z) for (x, z) in arch] + [(0.25, 0.0), (0.25, 0.145), (-0.25, 0.145)]
    profile("span", body, -0.075, 0.075, st)
    # a darker ring of voussoirs proud of both faces
    ring = [(x * 1.25, z * 1.3) for (x, z) in arch] + [(x, z) for (x, z) in reversed(arch)]
    for y0, y1 in ((-0.082, -0.074), (0.074, 0.082)):
        profile("voussoirs", ring, y0, y1, std)
    box("deck", (0.5, 0.15, 0.025), (0, 0, 0.155), cob, 0.004)
    # parapets with a coping stone and little end posts
    for sy in (-1, 1):
        box("parapet", (0.5, 0.022, 0.045), (0, sy * 0.068, 0.19), st, 0.004)
        box("coping", (0.52, 0.03, 0.012), (0, sy * 0.068, 0.218), std, 0.003)
        for x in (-0.25, 0.25):
            box("post", (0.035, 0.035, 0.08), (x, sy * 0.068, 0.2), std, 0.004)
    # cutwaters at the springing points and the ramps down to the banks
    for x in (-0.19, 0.19):
        c = cyl("cutwater", 0.035, 0.09, (x, 0, 0.035), std, 6, 0.004)
    for sx in (-1, 1):
        r = box("ramp", (0.12, 0.15, 0.02), (sx * 0.3, 0, 0.11), cob, 0.003)
        r.rotation_euler.y = sx * 0.55


def gunship():
    """DL8 hover gunship flying over the army (reference frame 2: aircraft over the front): a wedge composite body,
    swept wings with glowing ducted fans, a dark canopy and a nose gun."""
    comp = mat("gunmetal", "#68707b", 0.4)  # gunmetal like frame 5's machines
    trim = mat("comptrim", "#3e4550", 0.5)
    cyan = mat("cyan", "#14d2ff", 0.4, 0.0, "#14d2ff", 3.0)
    glass = mat("glass", "#1b2533", 0.2)
    b = box("body", (0.34, 0.1, 0.06), (0, 0, 0), comp, 0.02)
    cone("nose", 0.05, 0.12, (0.22, 0, 0), comp, 8, 0.0).rotation_euler.y = math.pi / 2
    sphere("canopy", 0.045, (0.08, 0, 0.035), glass, (1.6, 0.8, 0.6), 2)
    box("tail", (0.08, 0.012, 0.07), (-0.16, 0, 0.04), trim, 0.006)
    for sy in (-1, 1):
        w = box("wing", (0.14, 0.2, 0.014), (-0.04, sy * 0.13, -0.005), comp, 0.006)
        w.rotation_euler.z = sy * 0.35
        cyl("fan", 0.045, 0.03, (-0.06, sy * 0.21, 0.0), trim, 16, 0.004)
        cyl("fan_glow", 0.036, 0.034, (-0.06, sy * 0.21, 0.0), cyan, 16, 0.0)
    box("stripe", (0.3, 0.104, 0.008), (0, 0, 0.005), cyan, 0.0)
    cyl("gun", 0.008, 0.1, (0.2, 0, -0.03), trim, 6, 0.0).rotation_euler.y = math.pi / 2


def fighter():
    """DL6–7 propeller fighter flying over the army: olive fuselage, straight wings with roundels, a spinning-disc
    propeller and a bubble canopy."""
    od = mat("olive", "#5b6436", 0.6)
    white = mat("white", "#f3efe6", 0.5)
    f = cyl("fuselage", 0.035, 0.34, (0, 0, 0), od, 12, 0.01, r2=0.02)
    f.rotation_euler.y = math.pi / 2
    sphere("nose", 0.036, (0.17, 0, 0), od, (0.7, 1, 1), 2)
    cyl("prop", 0.06, 0.003, (0.2, 0, 0), mat("prop", "#4a4f55", 0.5), 16, 0.0).rotation_euler.y = math.pi / 2
    box("wing", (0.08, 0.42, 0.01), (0.03, 0, -0.01), od, 0.004)
    box("tailplane", (0.04, 0.14, 0.008), (-0.15, 0, 0.0), od, 0.003)
    box("fin", (0.05, 0.008, 0.06), (-0.15, 0, 0.03), od, 0.003)
    sphere("canopy", 0.025, (0.04, 0, 0.03), mat("canopy", "#9fd4ff", 0.15), (1.6, 0.8, 0.8), 2)
    for sy in (-1, 1):
        cyl("roundel", 0.03, 0.012, (0.03, sy * 0.15, -0.004), white, 12, 0.0)


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
    "bridge": bridge,
    "gunship": gunship,
    "fighter": fighter,
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
        ob = bpy.context.view_layer.objects.active
        ob.data.calc_loop_triangles()
        vs = [ob.matrix_world @ v.co for v in ob.data.vertices]
        print(f"EXPORTED {name}: tris={len(ob.data.loop_triangles)} radius={max(math.hypot(v.x, v.y) for v in vs):.3f} "
              f"x={min(v.x for v in vs):.3f}..{max(v.x for v in vs):.3f} y={min(v.y for v in vs):.3f}..{max(v.y for v in vs):.3f} "
              f"zmin={min(v.z for v in vs):.3f} height={max(v.z for v in vs):.3f} "
              f"mats={[s.material.name for s in ob.material_slots]}", flush=True)
