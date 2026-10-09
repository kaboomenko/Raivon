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
    _bx("floor", (0.1, 0.126, 0.01), (-0.17, 0, 0.121), wl)
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
    _cy("bucket_in", 0.04, 0.004, tuple(cc[i] + ax[i] * 0.0185 for i in range(3)), mat("dark", "#2c1d12", 0.9), 10, rot=(0, tilt, 0))
    _cy("bucket_hoop", 0.0458, 0.008, tuple(cc[i] + ax[i] * 0.008 for i in range(3)), iron, 10, rot=(0, tilt, 0))
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
    for i, (x, y, z, r) in enumerate(((0.0, -0.205, 0.026, 0.032), (0.066, -0.212, 0.026, 0.033), (0.032, -0.25, 0.024, 0.03),
                                      (0.03, -0.185, 0.024, 0.028), (0.034, -0.215, 0.072, 0.031))):
        _ico("pile", r, (x, y, z), rock, (1, 1, 0.88), 2, 0.12, 11 + i, smooth=False)


def cannon():
    """Field gun of the bicorne era: a bronze barrel with reinforcing rings, a muzzle swell, dolphins and a cascabel on
    a bracket-trail carriage strapped and bolted in iron, cap squares over the trunnions, an elevating screw, tall open
    spoked wheels with iron tyres, a rammer and a water bucket, a powder keg, an ammunition chest and a pyramid of shot."""
    wd = _timber("#6e4a2c")
    wl = _timber("#9c7a52")
    dk = _timber("#4a3020")
    iron = mat("iron", "#3b3d42", 0.55, 0.6)
    bolt = mat("bolt", "#e2dccb", 0.5)
    bronze = mat("bronze", "#b0823a", 0.35, 0.85)
    # bracket-trail carriage: two cheeks down to the ground behind, raised brackets under the trunnions, transoms
    c0, c1 = (0.1, 0.135), (-0.26, 0.022)

    def cheek_at(f, sy):
        return (c0[0] + (c1[0] - c0[0]) * f, sy * (0.042 - 0.016 * f), c0[1] + (c1[1] - c0[1]) * f)
    for sy in (-1, 1):
        _rbeam("cheek", cheek_at(0, sy), cheek_at(1, sy), 0.024, wd, 0.004, h=0.05)
        _bx("bracket", (0.11, 0.028, 0.05), (0.035, sy * 0.042, 0.135), wd, 0.004)
        for f in (0.32, 0.62, 0.9):
            _rbeam("strap", cheek_at(f - 0.02, sy), cheek_at(f + 0.02, sy), 0.029, iron, h=0.055)
        _bolts([(x, sy * 0.056, z) for (x, z) in ((0.075, 0.145), (0.0, 0.145), (0.075, 0.122), (0.0, 0.122))], bolt)
        _bolts([(p[0], sy * (abs(p[1]) + 0.014), p[2]) for p in (cheek_at(0.47, sy), cheek_at(0.77, sy))], bolt)
        _bx("cap_square", (0.03, 0.028, 0.008), (0.02, sy * 0.042, 0.179), iron)
    for f in (0.12, 0.45, 0.8):
        p = cheek_at(f, 1)
        _bx("transom", (0.025, 2 * p[1] - 0.01, 0.024), (p[0], 0, p[2]), wd, 0.003)
    _bx("trail_plate", (0.05, 0.05, 0.012), (-0.255, 0, 0.012), iron)
    _cy("handspike_ring", 0.012, 0.008, (-0.24, 0, 0.035), iron, 8, rot=YROT)
    # tall open wheels on an iron axle
    _cy("axle", 0.012, 0.2, (0.05, 0, 0.1), iron, 8, rot=YROT)
    for sy in (-1, 1):
        _spoked_wheel("wheel", (0.05, sy * 0.085, 0.1), 0.1, 0.02, 12, wl, dk, iron, rim_t=0.018, hub_r=0.022, n=18)
    # barrel along +X, slightly raised: rings, muzzle swell and lip, breech and cascabel, dolphins, trunnions
    el = -0.1
    brot = (0, math.pi / 2 + el, 0)

    def on_axis(x, up=0.0):
        return (x - math.sin(-el) * up, 0, 0.165 + math.sin(-el) * x + up)
    _cy("barrel", 0.03, 0.32, on_axis(0.08), bronze, 14, r2=0.022, rot=brot)
    for x, r in ((-0.06, 0.034), (0.0, 0.031), (0.1, 0.027), (0.2, 0.026)):
        _cy("ring", r, 0.014, on_axis(x), bronze, 14, rot=brot)
    _cy("muzzle", 0.026, 0.03, on_axis(0.232), bronze, 14, r2=0.029, rot=brot)
    _cy("muzzle_lip", 0.031, 0.008, on_axis(0.249), bronze, 14, rot=brot)
    _cy("bore", 0.014, 0.004, on_axis(0.254), mat("bore", "#141414", 0.9), 10, rot=brot)
    _ico("breech", 0.03, on_axis(-0.075), bronze, (0.7, 1, 1), 2)
    _ico("cascabel", 0.013, on_axis(-0.11), bronze, (1, 1, 1), 1)
    for sy in (-1, 1):
        _cy("trunnion", 0.01, 0.02, (0.02, sy * 0.032, 0.165), bronze, 8, rot=YROT)
        for x in (0.015, 0.055):
            lg = on_axis(x, 0.031)
            _bx("dolphin_leg", (0.006, 0.006, 0.016), (lg[0], sy * 0.012, lg[2]), bronze, rot=(0, el, 0))
        d = on_axis(0.035, 0.04)
        _bx("dolphin", (0.048, 0.007, 0.006), (d[0], sy * 0.012, d[2]), bronze, rot=(0, el, 0))
    _bx("vent_field", (0.02, 0.014, 0.004), on_axis(-0.04, 0.033), mat("bore", "#141414", 0.9), rot=(0, el, 0))
    # elevating screw under the breech with its cross handle
    _cy("screw", 0.006, 0.036, (-0.07, 0, 0.112), iron, 6)
    _bx("screw_handle", (0.045, 0.005, 0.005), (-0.07, 0, 0.106), iron)
    # crew kit: rammer and sponge on the ground, a water bucket, a powder keg, an ammunition chest, a pyramid of shot
    ra = math.atan2(0.03, 0.22)
    _rbeam("rammer", (-0.2, 0.172, 0.008), (0.02, 0.202, 0.008), 0.008, wl)
    _cy("sponge", 0.015, 0.04, (0.04, 0.205, 0.015), mat("sponge", "#3a2f28", 0.95), 8, rot=(0, math.pi / 2, ra))
    _cy("bucket", 0.022, 0.034, (0.13, 0.175, 0.017), wd, 10, r2=0.025)
    _cy("bucket_hoop", 0.0268, 0.006, (0.13, 0.175, 0.026), iron, 10)
    _cy("keg", 0.035, 0.07, (-0.14, -0.13, 0.035), wd, 12)
    for z in (0.012, 0.058):
        _cy("hoop", 0.037, 0.008, (-0.14, -0.13, z), iron, 12)
    _cy("keg_bulge", 0.038, 0.022, (-0.14, -0.13, 0.035), wd, 12)
    _bx("chest", (0.09, 0.06, 0.048), (-0.165, 0.125, 0.024), wd, 0.004)
    _bx("chest_lid", (0.096, 0.066, 0.012), (-0.165, 0.125, 0.054), wl, 0.003)
    for x in (-0.19, -0.14):
        _bx("chest_strap", (0.008, 0.068, 0.062), (x, 0.125, 0.032), iron)
    for sx in (-1, 1):
        _bx("chest_handle", (0.005, 0.022, 0.008), (-0.165 + sx * 0.047, 0.125, 0.036), iron)
    shot = mat("shot", "#2b2c2f", 0.5, 0.7)
    d, r = 0.031, 0.015
    for layer, n in enumerate((3, 2, 1)):
        for i in range(n):
            for j in range(n - i):
                x = 0.165 + (j + i * 0.5 + layer * 0.5) * d
                y = -0.145 + (i + layer / 3) * d * 0.866
                _ico("ball", r, (x, y, r + layer * d * 0.8165), shot, (1, 1, 1), 1)


def howitzer():
    """Field howitzer of the trench era in disruptive camouflage: a barrel with a recoil cylinder above and a
    recuperator below on the cradle, a muzzle brake, a riveted gun shield with a folded top, a sight port, a telescope
    and an apron, elevation and traverse hand wheels, split trails with spades, pressed-steel wheels with rubber tyres
    and steel rims, an open crate of brass shells, stacked ammunition boxes, spent cases and a camo net roll."""
    camo = _camo(("#5b6436", "#73603b", "#a39a68"), 13.0)
    od_d = mat("olive_d", "#454c2a", 0.7, 0.2)
    steel = mat("steel", "#3d4044", 0.5, 0.6)
    tyre = mat("tyre", "#1f1f21", 0.9)
    rivet = mat("rivet", "#b9b59c", 0.5)
    brass = mat("brass", "#c9a043", 0.35, 0.8)
    crate = _timber("#7a6442", 3.0, 0.8)
    # split trails spreading back to the spades, a cross tie and the spade handles
    for sy in (-1, 1):
        t0, t1 = (0.0, sy * 0.03, 0.1), (-0.3, sy * 0.13, 0.025)

        def trail_at(f, up=0.0):
            return (t0[0] + (t1[0] - t0[0]) * f, t0[1] + (t1[1] - t0[1]) * f, t0[2] + (t1[2] - t0[2]) * f + up)
        _rbeam("trail", t0, t1, 0.03, camo, 0.004, h=0.036)
        _bx("spade", (0.02, 0.07, 0.055), (-0.312, sy * 0.135, 0.03), steel, 0.003)
        _rbeam("spade_grip", trail_at(0.72, 0.034), trail_at(0.88, 0.034), 0.007, steel)
        for f in (0.72, 0.88):
            _rbeam("spade_grip_leg", trail_at(f, 0.012), trail_at(f, 0.037), 0.007, steel)
    _bx("trail_tie", (0.025, 0.17, 0.02), (-0.16, 0, 0.065), od_d, 0.003)
    # axle, wheels: rubber tyre, steel rim, pressed disc in the paint, hub and bolt ring
    _cy("axle", 0.014, 0.24, (0.0, 0, 0.09), steel, 8, rot=YROT)
    for sy in (-1, 1):
        c = (0.0, sy * 0.115, 0.09)
        _ring("tyre", 0.09, 0.064, 0.04, c, tyre, 18, surfaces=(0, 1, 3))
        _ring("rim", 0.066, 0.056, 0.043, c, steel, 18, surfaces=(1, 3))
        _cy("disc", 0.058, 0.03, c, camo, 16, rot=YROT)
        _cy("hub", 0.022, 0.05, (0.0, sy * 0.12, 0.09), steel, 8, rot=YROT)
        for k in range(6):
            a = k * math.tau / 6
            _bx("hub_bolt", (0.007, 0.01, 0.007), (math.cos(a) * 0.036, sy * 0.132, 0.09 + math.sin(a) * 0.036), rivet)
    # cradle, barrel, recoil cylinder above and recuperator below, raised to a firing angle
    el = 0.32
    brot = (0, math.pi / 2 - el, 0)

    def at(x, z=0.0):
        return (x * math.cos(el) - z * math.sin(el) + 0.02, 0, 0.16 + x * math.sin(el) + z * math.cos(el))
    _bx("cradle", (0.12, 0.07, 0.06), (0.02, 0, 0.15), camo, 0.008)
    _cy("barrel", 0.024, 0.42, at(0.16), camo, 12, r2=0.02, rot=brot)
    _cy("recoil", 0.019, 0.22, at(0.06, 0.037), od_d, 10, rot=brot)
    _cy("recuperator", 0.015, 0.2, at(0.05, -0.032), od_d, 10, rot=brot)
    for x in (-0.03, 0.15):
        _cy("band", 0.027, 0.012, at(x, 0.0), steel, 10, rot=brot)
    _cy("muzzle_brake", 0.03, 0.05, at(0.37), steel, 12, rot=brot)
    for sy in (-1, 1):
        _bx("brake_port", (0.03, 0.006, 0.014), (at(0.37)[0], sy * 0.029, at(0.37)[2]), mat("bore", "#141414", 0.9), rot=(0, -el, 0))
    _cy("bore", 0.013, 0.004, at(0.396), mat("bore", "#141414", 0.9), 10, rot=brot)
    _bx("breech", (0.07, 0.06, 0.06), at(-0.06), steel, 0.006, rot=(0, -el, 0))
    _bx("breech_lever", (0.008, 0.008, 0.05), (at(-0.09)[0], -0.035, at(-0.09)[2] - 0.01), steel, rot=(0, 0.6, 0))
    # gun shield: main plate, folded top, apron below the axle, rivets along the edges, sight port and telescope
    _bx("shield", (0.012, 0.26, 0.17), (0.1, 0, 0.2), camo, rot=(0, -0.15, 0))
    _bx("shield_top", (0.012, 0.22, 0.05), (0.095, 0, 0.3), camo, rot=(0, -0.35, 0))
    _bx("apron", (0.01, 0.17, 0.05), (0.098, 0, 0.075), camo, rot=(0, -0.1, 0))
    tilt = -0.15
    nx, nz = math.cos(tilt), -math.sin(tilt)  # the plate's front normal and its up direction
    ux, uz = math.sin(tilt), math.cos(tilt)

    def on_shield(y, lz):
        return (0.1 + 0.0085 * nx + lz * ux, y, 0.2 + 0.0085 * nz + lz * uz)
    edge = [(-0.115 + k * 0.02875, lz) for k in range(9) for lz in (-0.074, 0.074)]
    edge += [(sy * 0.12, lz) for sy in (-1, 1) for lz in (-0.037, 0.0, 0.037)]
    for (y, lz) in edge:
        _bx("rivet", (0.006, 0.008, 0.008), on_shield(y, lz), rivet, rot=(0, tilt, 0))
    _bx("sight_port", (0.014, 0.04, 0.025), (0.106, 0.06, 0.24), mat("glass", "#1a1d22", 0.3))
    _cy("telescope", 0.008, 0.07, (0.07, -0.07, 0.3), steel, 8, rot=(0, math.pi / 2 - 0.2, 0))
    # hand wheels: elevation on the left of the cradle, traverse on the right
    for (x, y, z) in ((-0.03, -0.062, 0.15), (-0.05, 0.062, 0.125)):
        _ring("handwheel", 0.026, 0.02, 0.006, (x, y, z), steel, 12, surfaces=(0, 1, 3))
        for a in (0.0, math.pi / 2):
            _bx("handwheel_spoke", (0.004, 0.004, 0.048), (x, y, z), steel, rot=(0, a, 0))
        _cy("handwheel_shaft", 0.004, abs(y) - 0.03, (x, y * 0.75, z), steel, 6, rot=YROT)
        _cy("handwheel_grip", 0.004, 0.016, (x + 0.02, y * 1.12, z + 0.012), od_d, 6, rot=YROT)
    # ammunition: an open crate of brass shells in front, stacked boxes on the other side, spent cases, the net roll
    cx, cy0 = 0.2, -0.17
    _bx("crate_floor", (0.1, 0.07, 0.008), (cx, cy0, 0.004), crate)
    for sx in (-1, 1):
        _bx("crate_end", (0.008, 0.07, 0.04), (cx + sx * 0.046, cy0, 0.02), crate)
        _bx("crate_side", (0.1, 0.008, 0.032), (cx, cy0 + sx * 0.031, 0.016), crate)
    for k in range(4):
        y = cy0 - 0.021 + k * 0.014
        _cy("case", 0.0065, 0.055, (cx - 0.012, y, 0.0145), brass, 8, rot=XROT)
        _cy("tip", 0.0065, 0.025, (cx + 0.028, y, 0.0145), steel, 8, r2=0.0, rot=XROT)
    _bx("ammo_box", (0.1, 0.07, 0.05), (0.2, 0.17, 0.025), crate, 0.004)
    _bx("ammo_box", (0.09, 0.065, 0.045), (0.205, 0.168, 0.0725), crate, 0.004)
    for z in (0.025, 0.0725):
        _bx("stencil", (0.04, 0.072, 0.012), (0.2, 0.17, z), mat("stencil", "#e8e2c8", 0.6))
    for (x, y, a) in ((0.12, -0.2, 0.4), (0.27, -0.12, 1.3)):
        _cy("spent", 0.0065, 0.05, (x, y, 0.0065), brass, 8, rot=(math.pi / 2, 0, a))
    _cy("net", 0.028, 0.16, (-0.16, 0, 0.1), mat("net", "#4f5a32", 0.95), 10, rot=YROT)
    for y in (-0.05, 0.05):
        _cy("net_strap", 0.03, 0.01, (-0.16, y, 0.1), mat("strap", "#3b2f22", 0.9), 10, rot=YROT)


# ------------------------------------------------------------------ helpers for the aircraft and the late-era launcher:
# lofted bodies (fuselages, hulls, drop tanks), flat discs (roundels, glowing fan faces), slabs (wings), armour plate
# with panel seams and aircraft paint (camouflage over a pale belly with panel lines).


def _ell(ry, rz, cz=0.0, n=10, cy=0.0):
    """Elliptic cross-section ring of n points (y, z) for _loft."""
    return [(cy + ry * math.cos(math.tau * k / n + math.pi / n), cz + rz * math.sin(math.tau * k / n + math.pi / n))
            for k in range(n)]


def _chamf(ry, zt, zb, c):
    """Chamfered-rectangle cross-section (8 points) for _loft: the faceted armour of the late-era machines."""
    return [(ry, zt - c), (ry - c, zt), (-ry + c, zt), (-ry, zt - c), (-ry, zb + c), (-ry + c, zb), (ry - c, zb),
            (ry, zb + c)]


def _loft(name, secs, mt, smooth=True):
    """A body along X through cross-sections secs = [(x, ring)], every ring the same number of (y, z) points, or a
    single point that closes the body to a tip. Open ends get flat caps; the sides shade smooth (a fuselage) or
    flat (faceted armour)."""
    verts, faces, want, sm = [], [], [], []
    rings = []
    for x, pts in secs:
        rings.append((len(verts), len(pts), (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))))
        verts += [(x, y, z) for (y, z) in pts]
    n = max(r[1] for r in rings)
    for (b0, n0, c0), (b1, n1, c1) in zip(rings, rings[1:]):
        cy, cz = (c0[0] + c1[0]) / 2, (c0[1] + c1[1]) / 2
        for k in range(n):
            if n0 == 1:
                f = (b0, b1 + k, b1 + (k + 1) % n)
            elif n1 == 1:
                f = (b0 + k, b0 + (k + 1) % n, b1)
            else:
                f = (b0 + k, b0 + (k + 1) % n, b1 + (k + 1) % n, b1 + k)
            fy = sum(verts[i][1] for i in f) / len(f)
            fz = sum(verts[i][2] for i in f) / len(f)
            faces.append(f)
            want.append((0.0, fy - cy, fz - cz))
            sm.append(smooth)
    for (b, nn, _), sx in ((rings[0], -1.0), (rings[-1], 1.0)):
        if nn > 1:
            faces.append(tuple(range(b, b + nn)))
            want.append((sx, 0.0, 0.0))
            sm.append(False)
    return _mesh(name, verts, faces, mt, lambda i, c: want[i], sm)


def _disc(name, r, loc, mt, n=12, rot=None):
    """A flat n-gon facing +Z (before rot): roundels, glowing fan faces, hatch openings."""
    o = _mesh(name, [(r * math.cos(math.tau * k / n), r * math.sin(math.tau * k / n), 0.0) for k in range(n)],
              [tuple(range(n))], mt, lambda i, c: (0, 0, 1))
    o.location = loc
    if rot:
        o.rotation_euler = rot
    return o


def _slab(name, top, bot, mt):
    """A plate between two matching outlines of 3D points (a wing, a tailplane): flat top, bottom and edges."""
    n = len(top)
    cx = sum(p[0] for p in top) / n
    cy = sum(p[1] for p in top) / n
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]

    def outward(i, c):
        if i < 2:
            return (0, 0, 1 if i == 0 else -1)
        return (c[0] - cx, c[1] - cy, 0)
    return _mesh(name, list(top) + list(bot), faces, mt, outward)


def _panelled(key, base_rgb_fn, seams, scale, width, row, mortar, grime, offset=0.5):
    """Shared node set-up of _plated and _warpaint: a brick pattern laid in plan on tops and wrapped along X+Y / Z on
    walls (as _masonry does) multiplied over a base colour as thin dark seams, and a little grime."""
    mt = bpy.data.materials.new(key)
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
    br = nt.nodes.new("ShaderNodeTexBrick")
    nt.links.new(mix.outputs[1], br.inputs["Vector"])
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (*(seams[0],) * 3, 1)
    br.inputs["Mortar"].default_value = (*(seams[1],) * 3, 1)
    br.inputs["Scale"].default_value = scale
    br.inputs["Mortar Size"].default_value = mortar
    br.inputs["Brick Width"].default_value = width
    br.inputs["Row Height"].default_value = row
    br.offset = offset
    base = base_rgb_fn(nt, tc, sn)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(base, mul.inputs["A"])
    nt.links.new(br.outputs["Color"], mul.inputs["B"])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 40.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    dirt = nt.nodes.new("ShaderNodeMix")
    dirt.data_type = "RGBA"
    dirt.blend_type = "MULTIPLY"
    dirt.inputs["Factor"].default_value = grime
    nt.links.new(mul.outputs["Result"], dirt.inputs["A"])
    nt.links.new(noise.outputs["Color"], dirt.inputs["B"])
    nt.links.new(dirt.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return mt


def _plated(color, scale=9.0, width=0.9, row=0.5, mortar=0.03, offset=0.5):
    """Armour plate of the late-era machines (reference frame 5): panels a shade apart with dark seams."""
    key = ("plated", color, scale, width, row, mortar, offset)
    if key not in kit._MATS:
        def base(nt, tc, sn):
            rgb = nt.nodes.new("ShaderNodeRGB")
            rgb.outputs[0].default_value = (*kit.srgb(color), 1)
            return rgb.outputs[0]
        kit._MATS[key] = _panelled(f"plated_{color}", base, (0.92, 0.52), scale, width, row, mortar, 0.14, offset)
    return kit._MATS[key]


def _warpaint(colors, belly, scale=14.0, panels=8.0):
    """Aircraft paint of the trench era: hard-edged camouflage blotches on every surface facing up or sideways, a
    pale belly underneath, fine panel lines over both."""
    key = ("warpaint", tuple(colors), belly, scale, panels)
    if key not in kit._MATS:
        def base(nt, tc, sn):
            noise = nt.nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = scale
            noise.inputs["Detail"].default_value = 1.5
            noise.inputs["Roughness"].default_value = 0.4
            nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
            ramp = nt.nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.interpolation = "CONSTANT"
            els = ramp.color_ramp.elements
            stops = [0.0, 0.45, 0.56][:len(colors)]
            els[0].position, els[0].color = stops[0], (*kit.srgb(colors[0]), 1)
            els[1].position, els[1].color = stops[1], (*kit.srgb(colors[1]), 1)
            for s, ccol in zip(stops[2:], colors[2:]):
                els.new(s).color = (*kit.srgb(ccol), 1)
            nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
            under = nt.nodes.new("ShaderNodeMath")
            under.operation = "LESS_THAN"
            under.inputs[1].default_value = -0.35
            nt.links.new(sn.outputs["Z"], under.inputs[0])
            pick = nt.nodes.new("ShaderNodeMix")
            pick.data_type = "RGBA"
            nt.links.new(under.outputs[0], pick.inputs["Factor"])
            nt.links.new(ramp.outputs["Color"], pick.inputs["A"])
            pick.inputs["B"].default_value = (*kit.srgb(belly), 1)
            return pick.outputs["Result"]
        kit._MATS[key] = _panelled("warpaint", base, (1.0, 0.66), panels, 0.9, 0.5, 0.025, 0.1, offset=0.0)
    return kit._MATS[key]


def rocket_launcher():
    """Late-era launcher (DL8 armies and sieges) facing +X: a six-wheeled armoured carrier in plated gunmetal with
    dark seams like frame 5's machines — armoured skirts over chunky wheels with cyan light strips, a faceted cab with
    a dark visor over a cyan light line, cyan headlights, a roof hatch with a pintle gun and a radar dish — carrying a
    ribbed launch box raised on a turntable, its front a dark grid of nine pale rocket noses; stowage on the deck: a
    rolled tarp, strapped tan cases, a whip aerial with a cyan tip."""
    comp = _plated("#68707b")
    dk = mat("comptrim", "#2c3139", 0.55)
    tyre = mat("tyre", "#1f1f21", 0.9)
    cyan = mat("cyan", "#14d2ff", 0.4, 0.0, "#14d2ff", 3.0)
    glass = mat("glass", "#1b2533", 0.2)
    ivory = mat("warhead", "#ece6d6", 0.45)
    tan = mat("case_tan", "#a08a5c", 0.7)
    tarp = mat("tarp", "#6f6a4f", 0.85)
    bronze = mat("bronze_trim", "#a8743e", 0.4)
    # running gear: six chunky wheels under armoured skirts, a dark belly between them (the hull comes first: the
    # joined mesh takes the first object's frame, and the plate seams are laid out in it)
    _bx("hull", (0.36, 0.19, 0.07), (-0.03, 0, 0.1), comp, 0.006)
    _bx("belly", (0.38, 0.14, 0.04), (0.0, 0, 0.07), dk)
    for x in (-0.14, 0.0, 0.14):
        for sy in (-1, 1):
            _cy("tyre", 0.046, 0.034, (x, sy * 0.089, 0.046), tyre, 10, rot=YROT)
            _cy("hub", 0.022, 0.04, (x, sy * 0.089, 0.046), dk, 6, rot=YROT)
    for sy in (-1, 1):
        _bx("skirt", (0.39, 0.012, 0.052), (-0.01, sy * 0.103, 0.099), comp)
        _bx("skirt_strip", (0.32, 0.004, 0.007), (-0.02, sy * 0.1095, 0.113), cyan)
        _bx("skirt_trim", (0.39, 0.016, 0.006), (-0.01, sy * 0.103, 0.128), dk)
    # cab: hood, sloped windscreen, roof; a dark visor over a cyan light line, side windows, headlights, bumper
    cab = [(0.1, 0.065), (0.208, 0.065), (0.218, 0.095), (0.212, 0.125), (0.185, 0.14), (0.16, 0.2), (0.1, 0.205)]
    _extrude_xz("cab", cab, -0.088, 0.088, comp)
    th = math.atan2(0.025, 0.06)
    nx, nz = math.cos(th), math.sin(th)
    _bx("visor", (0.004, 0.15, 0.056), (0.1725 + nx * 0.002, 0, 0.17 + nz * 0.002), glass, rot=(0, -th, 0))
    _bx("visor_light", (0.004, 0.13, 0.005), (0.183 + nx * 0.0025, 0, 0.142 + nz * 0.0025), cyan, rot=(0, -th, 0))
    for sy in (-1, 1):
        _bx("side_window", (0.042, 0.004, 0.03), (0.135, sy * 0.0885, 0.178), glass)
        _bx("headlight", (0.006, 0.026, 0.01), (0.2155, sy * 0.06, 0.11), cyan)
    _bx("bumper", (0.014, 0.196, 0.022), (0.213, 0, 0.074), dk)
    _bx("grille", (0.004, 0.07, 0.022), (0.2165, 0, 0.098), dk)
    # roof hatch (open, lid thrown back) with a pintle gun; radar dish with a beacon on the other roof corner
    _cy("hatch_ring", 0.02, 0.012, (0.135, 0.032, 0.209), dk, 8)
    _disc("hatch_hole", 0.014, (0.135, 0.032, 0.216), mat("hole", "#121519", 0.9), 8)
    _bx("hatch_lid", (0.036, 0.036, 0.006), (0.108, 0.032, 0.226), comp, rot=(0, 1.15, 0))
    _bx("pintle", (0.006, 0.006, 0.024), (0.148, 0.032, 0.225), dk)
    _bx("mg", (0.06, 0.006, 0.008), (0.165, 0.032, 0.238), dk)
    _bx("mg_box", (0.016, 0.014, 0.012), (0.145, 0.032, 0.238), dk)
    _bx("radar_mast", (0.006, 0.006, 0.05), (0.118, -0.062, 0.228), dk)
    _cy("radar_dish", 0.026, 0.006, (0.118, -0.062, 0.256), comp, 10, rot=(0.9, 0, 0.5))
    _bx("beacon", (0.008, 0.008, 0.008), (0.118, -0.062, 0.262), cyan)
    # deck stowage: a rolled tarp behind the cab, strapped tan cases at the tail, an exhaust stack, a whip aerial
    _cy("tarp", 0.017, 0.15, (0.072, 0, 0.152), tarp, 8, rot=YROT)
    for y in (-0.045, 0.045):
        _bx("tarp_strap", (0.036, 0.006, 0.036), (0.072, y, 0.152), dk)
    for y in (-0.055, 0.055):
        _bx("case", (0.042, 0.05, 0.034), (-0.185, y, 0.152), tan)
        _bx("case_strap", (0.008, 0.054, 0.037), (-0.185, y, 0.152), dk)
    _cy("exhaust", 0.008, 0.07, (0.09, 0.08, 0.17), dk, 6)
    _bx("aerial", (0.003, 0.003, 0.1), (-0.2, -0.082, 0.185), dk)
    _bx("aerial_tip", (0.006, 0.006, 0.008), (-0.2, -0.082, 0.236), cyan)
    # launcher: turntable, lift arms, a ribbed launch box raised toward the front with a dark face of rocket noses
    _cy("turntable", 0.066, 0.026, (-0.07, 0, 0.148), dk, 10)
    for sy in (-1, 1):
        _bx("lift_arm", (0.03, 0.012, 0.1), (-0.07, sy * 0.06, 0.2), dk, rot=(0, -0.2, 0))
    el = 0.45
    ax = (math.cos(el), math.sin(el))   # the box's axis in XZ
    up = (-math.sin(el), math.cos(el))  # its up
    pc = (-0.06, 0.255)
    L, W, H = 0.22, 0.15, 0.1

    def at(a, u=0.0):
        return (pc[0] + ax[0] * a + up[0] * u, pc[1] + ax[1] * a + up[1] * u)
    rot = (0, -el, 0)
    x, z = at(0)
    _bx("pod", (L, W, H), (x, 0, z), comp, 0.006, rot=rot)
    for a in (-L / 2 + 0.01, -0.02, 0.05, L / 2 - 0.008):
        x, z = at(a)
        _bx("pod_rib", (0.014, W + 0.008, H + 0.008), (x, 0, z), dk, rot=rot)
    x, z = at(L / 2 + 0.001)
    _bx("pod_face", (0.004, W - 0.006, H - 0.006), (x, 0, z), mat("hole", "#121519", 0.9), rot=rot)
    for sy in (-1, 1):
        x, z = at(-0.055, 0.015)
        _bx("pod_strip", (0.06, 0.004, 0.008), (x, sy * (W / 2 + 0.002), z), cyan, rot=rot)
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            x, z = at(L / 2 + 0.003 + 0.012, j * 0.03)
            cone("warhead", 0.012, 0.024, (x, i * 0.045, z), ivory, 6, 0.0).rotation_euler = (0, math.pi / 2 - el, 0)


def bridge():
    """Stone humpback bridge along X (length 0.71, deck width 0.12) after the river crossings of reference frames 1
    and 3: coursed masonry on every face, an arch ringed with voussoirs and a pale keystone, a flagstone deck that runs
    down to the banks, parapets under a light coping, crenellated turret piers over the springings of the arch and
    lanterns with a warm glow on the end posts."""
    L = 0.355

    def deck_z(x):
        t = min(max((abs(x) - 0.08) / (L - 0.08), 0.0), 1.0)
        return 0.03 + 0.14 * (1 - t * t * (3 - 2 * t))
    st = _masonry(STONE)
    std = _masonry(STONE_D)
    flags = _masonry("#b09c80", 0.6, 0.05)
    cope = kit.textured("plaster", "#ddd4c2")
    xs = [-L + 2 * L * k / 28 for k in range(29)]
    # the span: masonry from the banks up under the deck with the arched opening through it
    arch = [(-math.cos(math.pi * k / 12) * 0.15, math.sin(math.pi * k / 12) * 0.1) for k in range(13)]
    body = [(-L, 0.0)] + arch + [(L, 0.0)] + [(x, deck_z(x) - 0.004) for x in reversed(xs)]
    _extrude_xz("span", body, -0.072, 0.072, st)
    # flagstone deck following the hump down to the road on both banks
    _extrude_xz("deck", [(x, deck_z(x) + 0.006) for x in xs] + [(x, deck_z(x) - 0.012) for x in reversed(xs)], -0.062, 0.062, flags)
    # parapets and their coping stones between the end posts
    px = [x for x in xs if abs(x) <= 0.3 + 1e-6]
    px = [-0.3] + [x for x in px if abs(x) < 0.3 - 1e-6] + [0.3]
    for sy in (-1, 1):
        y0, y1 = sorted((sy * 0.058, sy * 0.08))
        _extrude_xz("parapet", [(x, deck_z(x) + 0.046) for x in px] + [(x, deck_z(x) - 0.006) for x in reversed(px)], y0, y1, st)
        y0, y1 = sorted((sy * 0.054, sy * 0.085))
        _extrude_xz("coping", [(x, deck_z(x) + 0.058) for x in px] + [(x, deck_z(x) + 0.045) for x in reversed(px)], y0, y1, cope)
    # voussoirs round the arch on both faces, alternating tones, with a proud pale keystone at the crown
    n = 11
    tones = (kit.textured("plaster", "#9d968a"), kit.textured("plaster", "#bdb5a6"))
    key = kit.textured("plaster", "#e2d9c6")
    for k in range(n):
        a0 = math.pi * k / n + 0.012
        a1 = math.pi * (k + 1) / n - 0.012
        ko = 1.38 if k == n // 2 else 1.27
        ring = [(-math.cos(a0) * 0.15, math.sin(a0) * 0.1), (-math.cos(a1) * 0.15, math.sin(a1) * 0.1),
                (-math.cos(a1) * 0.15 * ko, math.sin(a1) * 0.1 * ko), (-math.cos(a0) * 0.15 * ko, math.sin(a0) * 0.1 * ko)]
        mt = key if k == n // 2 else tones[k % 2]
        proud = 0.011 if k == n // 2 else 0.008
        for sy in (-1, 1):
            y0, y1 = sorted((sy * 0.07, sy * (0.072 + proud)))
            _extrude_xz("voussoir", ring, y0, y1, mt)
    # crenellated turret piers standing out of both faces over the springings (reference frame 3)
    dark = mat("dark", "#2a2622", 0.9)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 0.168, sy * 0.096
            _bx("turret", (0.062, 0.05, 0.216), (x, y, 0.108), st, 0.004)
            _bx("cornice", (0.072, 0.06, 0.012), (x, y, 0.218), std, 0.003)
            _bx("turret_floor", (0.048, 0.036, 0.004), (x, y, 0.225), dark)
            for dx in (-1, 1):
                for dy in (-1, 1):
                    _bx("merlon", (0.02, 0.018, 0.026), (x + dx * 0.026, y + dy * 0.021, 0.236), st)
            _bx("slit", (0.012, 0.004, 0.03), (x, y + sy * 0.0255, 0.15), dark)
    # end posts with iron lanterns glowing warm, like the lit windows of the reference frames
    glow = m("win_lit", "#ffcf6b", 0.5, emission="#ffb84a", strength=2.0)
    iron = mat("iron", "#3b3d42", 0.55, 0.6)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 0.318, sy * 0.07
            _bx("end_post", (0.036, 0.036, 0.15), (x, y, 0.075), std, 0.004)
            _bx("lamp_base", (0.03, 0.03, 0.006), (x, y, 0.153), iron)
            _bx("lamp", (0.02, 0.02, 0.026), (x, y, 0.169), glow)
            for dx in (-1, 1):
                for dy in (-1, 1):
                    _bx("lamp_bar", (0.004, 0.004, 0.026), (x + dx * 0.011, y + dy * 0.011, 0.169), iron)
            _cy("lamp_cap", 0.022, 0.018, (x, y, 0.191), iron, 4, r2=0.0, rot=(0, 0, math.pi / 4))


def war_banner(color):
    """A war banner on its pole. The cloth hangs exactly where banner() hangs it, because the game paints the state's
    flag over it there (map_view._paint_flag: x 0.13, z 0.775, 0.25 × 0.4); around it: a dark wooden staff with iron
    bands set in a dressed-stone plinth, the crossbar lashed on with rope and capped in gold, a gold spear finial and a
    shield in the side's colour leaning on the plinth (reference frame 3: banners on dark poles with gold fittings)."""
    def build():
        h, w = 1.0, 0.26
        box("cloth", (w, 0.012, w * 1.6), (w / 2, 0, h - 0.02 - w * 0.8), m("banner" + color, color, 0.7), 0.003)
        box("emblem", (w * 0.45, 0.016, w * 0.45), (w / 2, 0, h - 0.02 - w * 0.65), m("emblem", "#f4f4f4", 0.6), 0.003)
        wood = _timber("#5e3d24", 9.0, 0.72)
        gold = mat("gold", GOLD, 0.3, 0.7)
        iron = mat("iron", "#3b3d42", 0.55, 0.6)
        rope = mat("rope", "#c9b48a", 0.95)
        # plinth of two dressed blocks, an iron socket, a few loose stones at its foot
        _bx("plinth", (0.13, 0.13, 0.046), (0, 0, 0.023), _masonry(STONE, 1.6), 0.005)
        _bx("plinth_top", (0.086, 0.086, 0.04), (0, 0, 0.066), _masonry("#c9c1b2", 1.6), 0.004)
        _cy("socket", 0.02, 0.03, (0, 0, 0.1), iron, 8)
        for i, (x, y, r) in enumerate(((0.075, 0.045, 0.02), (-0.07, 0.06, 0.017), (-0.072, -0.068, 0.015))):
            _ico("stone", r, (x, y, r * 0.5), m("rock", "#9a948a"), (1.2, 1, 0.75), 1, 0.15, 30 + i, smooth=False)
        # the staff with two iron bands, the crossbar with gold caps and a rope lashing, the gold spear finial
        _cy("pole", 0.012, h - 0.08, (0, 0, 0.08 + (h - 0.08) / 2), wood, 8)
        for z in (0.26, 0.46):
            _cy("band", 0.0145, 0.014, (0, 0, z), iron, 8)
        _cy("bar", 0.008, w + 0.03, (w / 2, 0, h - 0.02), wood, 6, rot=XROT)
        for x in (-0.017, w + 0.017):
            _ico("bar_cap", 0.013, (x, 0, h - 0.02), gold, (1, 1, 1), 1)
        _cy("lashing", 0.016, 0.026, (0, 0, h - 0.02), rope, 8)
        _cy("collar", 0.017, 0.012, (0, 0, h + 0.006), gold, 8)
        _ico("knop", 0.016, (0, 0, h + 0.024), gold, (1, 1, 1), 1)
        _cy("spear", 0.014, 0.05, (0, 0, h + 0.06), gold, 6, r2=0.0)
        # a round shield in the side's colour with an iron rim and a gold boss, leaning on the plinth
        tilt = math.pi / 2 - 0.3
        _cy("shield", 0.042, 0.008, (0.018, -0.079, 0.043), m("shield" + color, color, 0.6), 12, rot=(tilt, 0, 0))
        rim = _ring("shield_rim", 0.044, 0.037, 0.011, (0.018, -0.079, 0.043), iron, 12, surfaces=(0, 1, 3))
        rim.rotation_euler = (-0.3, 0, 0)
        nrm = (0, -math.sin(tilt), math.cos(tilt))
        _ico("boss", 0.012, (0.018, -0.079 + nrm[1] * 0.006, 0.043 + nrm[2] * 0.006), gold, (1, 1, 0.8), 1)
        # one mesh, so export() bakes it at 512 like the plain banner was (the game paints over most of the cloth)
        parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        bpy.ops.object.select_all(action="DESELECT")
        for o in parts:
            o.select_set(True)
        bpy.context.view_layer.objects.active = parts[0]
        bpy.ops.object.convert(target="MESH")
        bpy.ops.object.join()
    return build


def gunship():
    """DL8 hover gunship circling over the army (nose +X), after reference frame 2's aircraft and frame 5's
    machines: a faceted hull in plated gunmetal with dark seams, a dark faceted canopy edged by cyan light strips
    along the spine, a bronze trim line, stub wings carrying twin rotary cannon (the two forward rods of frame 2) and
    missile pods with glowing tubes, wingtip ducted fans glowing cyan through dark vanes inside banded nacelles, canted
    twin fins tipped with light, rear thrusters glowing cyan."""
    comp = _plated("#68707b", 8.0, row=0.45, offset=0.0)
    dk = mat("comptrim", "#2c3139", 0.55)
    cyan = mat("cyan", "#14d2ff", 0.4, 0.0, "#14d2ff", 3.0)
    glass = mat("glass", "#1b2533", 0.2)
    steel = mat("barrel", "#aab2bc", 0.35)
    bronze = mat("bronze_trim", "#a8743e", 0.4)
    pale = mat("pale_band", "#d9dde2", 0.45)
    hull = [(0.282, _chamf(0.012, 0.004, -0.014, 0.004)), (0.22, _chamf(0.032, 0.02, -0.028, 0.01)),
            (0.13, _chamf(0.048, 0.032, -0.04, 0.016)), (0.0, _chamf(0.06, 0.038, -0.044, 0.02)),
            (-0.12, _chamf(0.054, 0.034, -0.036, 0.018)), (-0.2, _chamf(0.036, 0.026, -0.022, 0.012))]
    _loft("hull", hull, comp, smooth=False)
    _loft("canopy", [(0.205, _chamf(0.006, 0.022, 0.012, 0.002)), (0.165, _chamf(0.026, 0.048, 0.015, 0.008)),
                     (0.1, _chamf(0.032, 0.06, 0.02, 0.012)), (0.04, _chamf(0.026, 0.056, 0.025, 0.01)),
                     (0.0, _chamf(0.012, 0.045, 0.03, 0.005))], glass, smooth=False)
    _loft("canopy_frame", [(0.128, _chamf(0.033, 0.0605, 0.02, 0.012)), (0.12, _chamf(0.033, 0.0605, 0.02, 0.012))],
          dk, smooth=False)
    # cyan light strips along the spine's edges (the light lines of frame 2's aircraft), a bronze trim line between
    tops = [(0.22, 0.022, 0.02), (0.13, 0.032, 0.032), (0.0, 0.04, 0.038), (-0.12, 0.036, 0.034), (-0.18, 0.029, 0.028)]
    for sy in (-1, 1):
        for (x0, y0, z0), (x1, y1, z1) in zip(tops, tops[1:]):
            _rbeam("spine_light", (x0, sy * (y0 - 0.002), z0 + 0.0015), (x1, sy * (y1 - 0.002), z1 + 0.0015), 0.005,
                   cyan, h=0.003)
    _rbeam("spine", (-0.005, 0, 0.0385), (-0.17, 0, 0.031), 0.014, dk, h=0.006)
    for sy in (-1, 1):
        _bx("intake", (0.07, 0.012, 0.022), (-0.03, sy * 0.058, 0.008), dk)
        _bx("intake_glow", (0.05, 0.004, 0.006), (-0.03, sy * 0.0645, 0.008), cyan)
    for sy in (-1, 1):  # intake grilles with glowing slits on the back (the rear deck of the DL8 hover tank)
        _bx("grille", (0.05, 0.018, 0.004), (-0.09, sy * 0.02, 0.0355), dk, rot=(0, -0.033, 0))
        for x in (-0.075, -0.105):
            _bx("grille_glow", (0.006, 0.013, 0.003), (x, sy * 0.02, 0.0373 + (x + 0.09) * 0.033), cyan,
                rot=(0, -0.033, 0))
    _bx("keel", (0.18, 0.04, 0.012), (-0.01, 0, -0.046), dk)
    _bx("keel_glow", (0.14, 0.02, 0.004), (-0.01, 0, -0.053), cyan)
    _bx("nose_eye", (0.006, 0.016, 0.006), (0.281, 0, -0.004), cyan)
    for sy in (-1, 1):
        # stub wing into the nacelle
        out = [(0.07, 0.04), (-0.01, 0.175), (-0.09, 0.175), (-0.12, 0.04)]
        _slab("wing", [(x, sy * s, 0.002) for x, s in out], [(x, sy * s, -0.014) for x, s in out], comp)

        def edge(s):  # leading and trailing edge x at span s
            f = (s - 0.04) / 0.135
            return 0.07 - 0.08 * f + 0.0015, -0.12 + 0.03 * f - 0.0015
        band = [(edge(0.082)[0], 0.082), (edge(0.097)[0], 0.097), (edge(0.097)[1], 0.097), (edge(0.082)[1], 0.082)]
        _slab("wing_band", [(x, sy * s, 0.0032) for x, s in band], [(x, sy * s, 0.001) for x, s in band], pale)
        # wingtip ducted fan: banded nacelle, a glowing cyan face crossed by dark vanes, the same underneath
        c = (-0.05, sy * 0.205)
        _cy("nacelle", 0.05, 0.036, (c[0], c[1], -0.004), comp, 12)
        o = _ring("nacelle_band", 0.0508, 0.049, 0.006, (c[0], c[1], -0.004), cyan, 12, surfaces=(0,))
        o.rotation_euler = (math.pi / 2, 0, 0)
        o = _ring("nacelle_lip", 0.052, 0.04, 0.006, (c[0], c[1], 0.014), dk, 12, surfaces=(0, 1, 2))
        o.rotation_euler = (math.pi / 2, 0, 0)
        _disc("fan_glow", 0.04, (c[0], c[1], 0.015), cyan, 12)
        _disc("fan_glow_under", 0.04, (c[0], c[1], -0.023), cyan, 12, rot=(math.pi, 0, 0))
        for a in (0.4, 0.4 + math.pi / 2):
            _bx("fan_vane", (0.078, 0.007, 0.004), (c[0], c[1], 0.0155), dk, rot=(0, 0, a))
        _cy("fan_hub", 0.012, 0.006, (c[0], c[1], 0.016), dk, 8)
        # rotary cannon under the wing root: housing, three steel barrels, muzzle ring, pylon
        y = sy * 0.095
        _bx("gun_pylon", (0.04, 0.01, 0.014), (0.02, y, -0.02), dk)
        _cy("gun_housing", 0.015, 0.07, (0.03, y, -0.032), dk, 6, rot=XROT)
        for k in range(3):
            a = math.tau * k / 3 + math.pi / 2
            _bx("gun_barrel", (0.085, 0.005, 0.005), (0.105, y + 0.007 * math.cos(a), -0.032 + 0.007 * math.sin(a)),
                steel)
        _cy("gun_muzzle", 0.0125, 0.008, (0.14, y, -0.032), bronze, 6, rot=XROT)
        # missile pod on the wing with glowing tube ends
        _bx("pod", (0.07, 0.032, 0.023), (-0.03, sy * 0.13, 0.0125), dk)
        for dy in (-0.008, 0.008):
            _bx("pod_tube", (0.003, 0.009, 0.009), (0.0055, sy * 0.13 + dy, 0.013), cyan)
        # canted fin with a light tip, a rear thruster with a glowing face
        fin = [(-0.125, 0.0), (-0.172, 0.052), (-0.2, 0.052), (-0.203, 0.0)]
        o = _extrude_xz("fin", fin, -0.0035, 0.0035, comp)
        o.location = (0, sy * 0.03, 0.018)
        o.rotation_euler = (-sy * 0.38, 0, 0)
        o = _extrude_xz("fin_light", [(-0.1684, 0.048), (-0.1716, 0.0525), (-0.2005, 0.0525), (-0.2005, 0.048)],
                        -0.0042, 0.0042, cyan)
        o.location = (0, sy * 0.03, 0.018)
        o.rotation_euler = (-sy * 0.38, 0, 0)
        _bx("thruster", (0.02, 0.026, 0.022), (-0.2, sy * 0.02, 0.0), dk)
        _bx("thruster_glow", (0.004, 0.02, 0.016), (-0.211, sy * 0.02, 0.0), cyan)


def fighter():
    """DL6–7 piston fighter circling over the army (nose +X): a lofted fuselage in olive-and-earth camouflage over a
    pale belly with panel lines (the trench-era paint of the howitzer), a cream identification band and spinner, a
    dark cowling with exhaust stubs, a three-blade propeller with yellow tips, tapered wings with pale roundels, wing
    guns and drop tanks, a framed bubble canopy, a tail fin with a cream tip."""
    paint = _warpaint(("#66703d", "#86704a", "#46522f"), "#b4bcb6", 14.0)
    cream = mat("cream", "#efe6cf", 0.55)
    dark = mat("cowl", "#2b2f25", 0.6)
    slate = mat("roundel", "#3b4250", 0.6)
    glass = mat("canopy", "#8fc0dc", 0.15)
    prop = mat("prop", "#26282a", 0.5)
    yellow = mat("prop_tip", "#e8cf6a", 0.5)
    fus = [(0.186, 0.026, 0.026, 0.002), (0.17, 0.032, 0.032, 0.003), (0.13, 0.036, 0.037, 0.004),
           (0.07, 0.035, 0.040, 0.006), (0.0, 0.031, 0.038, 0.006), (-0.06, 0.024, 0.031, 0.008),
           (-0.12, 0.014, 0.022, 0.012), (-0.168, 0.006, 0.012, 0.016)]

    def sec(x):  # the fuselage section (ry, rz, cz) at x
        for a, b in zip(fus, fus[1:]):
            if b[0] <= x <= a[0]:
                t = (a[0] - x) / (a[0] - b[0])
                return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
        return fus[-1][1:]
    _loft("fuselage", [(0.153, _ell(*sec(0.153)))] + [(x, _ell(ry, rz, cz)) for x, ry, rz, cz in fus if x < 0.153],
          paint)
    # dark cowling ring, cream spinner, three-blade propeller with yellow tips, exhaust stubs
    _loft("cowl", [(x, _ell(sec(x)[0] * 1.04, sec(x)[1] * 1.04, sec(x)[2])) for x in (0.152, 0.17, 0.186)], dark)
    cone("spinner", 0.021, 0.03, (0.201, 0, 0.002), cream, 10, 0.0).rotation_euler = (0, math.pi / 2, 0)
    for k in range(3):
        a = math.radians(90 + 120 * k)
        ca, sa = math.cos(a), math.sin(a)
        _bx("blade", (0.005, 0.012, 0.048), (0.193, 0.032 * ca, 0.002 + 0.032 * sa), prop, rot=(a - math.pi / 2, 0, 0))
        _bx("blade_tip", (0.0055, 0.0125, 0.008), (0.193, 0.054 * ca, 0.002 + 0.054 * sa), yellow,
            rot=(a - math.pi / 2, 0, 0))
    for sy in (-1, 1):
        ry, rz, cz = sec(0.115)
        _bx("exhaust", (0.045, 0.007, 0.008), (0.115, sy * (ry * 0.95), cz + 0.012), dark)
    # cream identification band round the rear fuselage
    _loft("band", [(x, _ell(sec(x)[0] * 1.07, sec(x)[1] * 1.07, sec(x)[2])) for x in (-0.074, -0.096)], cream)
    # bubble canopy with two dark frames
    can = [(0.085, 0.004, 0.003, 0.040), (0.07, 0.014, 0.012, 0.040), (0.05, 0.019, 0.02, 0.040),
           (0.025, 0.019, 0.021, 0.039), (0.0, 0.015, 0.016, 0.038), (-0.025, 0.006, 0.006, 0.036)]
    _loft("canopy", [(x, _ell(ry, rz, cz)) for x, ry, rz, cz in can], glass)
    for x0, x1, s in ((0.064, 0.058, 1.12), (0.03, 0.025, 1.08)):
        def cs(x):
            for a, b in zip(can, can[1:]):
                if b[0] <= x <= a[0]:
                    t = (a[0] - x) / (a[0] - b[0])
                    return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
        _loft("canopy_frame", [(x, _ell(cs(x)[0] * s, cs(x)[1] * s, cs(x)[2])) for x in (x0, x1)], dark)
    # tapered wings with dihedral: pale roundels on top, two guns in each leading edge, a drop tank underneath
    d, zw, t = 0.09, -0.016, 0.01
    plan = [(0.08, 0.025), (0.066, 0.12), (0.052, 0.185), (0.036, 0.208), (0.018, 0.213), (0.004, 0.205),
            (-0.004, 0.185), (-0.03, 0.025)]
    for sy in (-1, 1):
        def wp(x, s, h):
            return (x, sy * (s * math.cos(d) - h * math.sin(d)), zw + s * math.sin(d) + h * math.cos(d))
        _slab("wing", [wp(x, s, t / 2) for x, s in plan], [wp(x, s, -t / 2) for x, s in plan], paint)
        for r, mt, k in ((0.029, cream, 1), (0.019, slate, 2), (0.008, cream, 3)):
            _disc("roundel", r, wp(0.026, 0.15, t / 2 + 0.001 * k), mt, 12, rot=(sy * d, 0, 0))
        for s in (0.1, 0.116):
            le = 0.08 + (0.066 - 0.08) * (s - 0.025) / 0.095
            _bx("gun", (0.03, 0.0035, 0.0035), wp(le + 0.008, s, 0.0), dark, rot=(sy * d, 0, 0))
        tz = wp(0.02, 0.085, -t / 2)[2] - 0.016
        ty = wp(0.02, 0.085, 0.0)[1]
        _bx("pylon", (0.03, 0.004, 0.016), (0.02, ty, tz + 0.0095), dark)
        _loft("drop_tank", [(0.075, [(ty, tz)]), (0.062, _ell(0.007, 0.007, tz, 8, ty)),
                            (0.04, _ell(0.0105, 0.0105, tz, 8, ty)), (0.0, _ell(0.0105, 0.0105, tz, 8, ty)),
                            (-0.03, _ell(0.006, 0.006, tz, 8, ty)), (-0.04, [(ty, tz)])], paint)
    # tailplane and fin with a cream tip
    tp = [(-0.12, 0.012), (-0.133, 0.068), (-0.145, 0.078), (-0.16, 0.076), (-0.168, 0.06), (-0.17, 0.012)]
    tp = tp + [(x, -y) for x, y in reversed(tp)]
    _slab("tailplane", [(x, y, 0.0155) for x, y in tp], [(x, y, 0.0085) for x, y in tp], paint)
    fin = [(-0.115, 0.02), (-0.14, 0.05), (-0.155, 0.066), (-0.168, 0.07), (-0.178, 0.06), (-0.178, 0.015)]
    _extrude_xz("fin", fin, -0.004, 0.004, paint)
    _extrude_xz("fin_tip", [(-0.1462, 0.0565), (-0.1546, 0.0668), (-0.168, 0.0708), (-0.1787, 0.0604),
                            (-0.1787, 0.0565)], -0.0046, 0.0046, cream)


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
    "banner_green": war_banner("#2f8f3f"),
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
    "banner_blue": war_banner(ROOF_BLUE),
    "banner_red": war_banner("#b3272b"),
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
