"""Commander portrait kit (04 §15.4): 3/4 busts built from the kit parameters — head shape, hair, facial hair,
headgear, uniform, accessory, palette from 04 §15.3 — rendered on a transparent background (the game draws the
rarity plate and frame). Run: python3 tools/blender/portrait_assets.py OUTDIR [ids...] [--size=256]
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402

# skin, head (w, h), hair colour, hair style, facial hair, headgear, uniform, accent
LOOK = {
    "cmd_bram": ("#e8b48e", (0.40, 0.41), "#b5562b", "short", "beard", "", "#d9c9a3", "#7a4e2d"),
    "cmd_lira": ("#f0c4a0", (0.33, 0.42), "#5a3420", "braid", "", "kerchief", "#3e9b5a", "#f2f2f2"),
    "cmd_olm": ("#e2b08c", (0.31, 0.45), "#c8c8c8", "sides", "", "goggles", "#7a4e2d", "#c9a24a"),
    "cmd_vik": ("#f2c8a4", (0.32, 0.43), "#e3c46a", "messy", "", "hood", "#4e6b3a", "#6b4a2a"),
    "cmd_vega": ("#e9bd99", (0.32, 0.42), "#2e2a2a", "bob", "", "glasses", "#44484f", "#c8ccd4"),
    "cmd_kort": ("#dca582", (0.41, 0.42), "#d8d8d8", "bald", "mustache_long", "", "#5d6236", "#b0803a"),
    "cmd_seir": ("#c98d68", (0.36, 0.41), "#cfcfcf", "short", "beard_short", "tricorn", "#1f6f8b", "#f2f2f2"),
    "cmd_frey": ("#e4b592", (0.38, 0.40), "#6b5a48", "buzz", "", "", "#3b5a44", "#9aa3ad"),
    "cmd_irma": ("#f1c9aa", (0.32, 0.42), "#efe9dc", "ponytail", "", "goggles", "#26272b", "#f08a24"),
    "cmd_hawk": ("#e6b996", (0.34, 0.42), "#4a3424", "short", "mustache", "flight", "#7a5133", "#6fa8dc"),
    "cmd_vance": ("#f0cdb2", (0.32, 0.42), "#d9d9de", "updo", "", "brooch", "#8e5bd0", "#e8e8f0"),
    "cmd_rai": ("#e7c0a0", (0.36, 0.43), "#f0f0f0", "long", "beard_long", "circlet", "#eef1f6", "#3a8dff"),
}
HEAD_Z = 1.3


def darker(hex_color, k=0.6):
    h = hex_color.lstrip("#")
    c = [int(int(h[i:i + 2], 16) * k) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(c)


def build(cid):
    skin_c, (hw, hh), hair_c, style, facial, gear, uni_c, acc_c = LOOK[cid]
    skin = kit.mat("skin_" + cid, skin_c, 0.55)
    hair = kit.mat("hair_" + cid, hair_c, 0.7)
    uni = kit.mat("uni_" + cid, uni_c, 0.65)
    acc = kit.mat("acc_" + cid, acc_c, 0.45, 0.3 if cid in ("cmd_vega", "cmd_frey", "cmd_rai") else 0.0)
    white = kit.mat("eye_white", "#f6f6f2", 0.3)
    dark = kit.mat("eye_dark", "#1d1714", 0.3)
    lips = kit.mat("lips", "#9b4a3c", 0.5)
    brow = kit.mat("brow_" + cid, darker(hair_c, 0.55), 0.8)
    # bust: shoulders, chest, neck
    kit.sphere("shoulders", 1.0, (0, 0.05, 0.62), uni, (0.72, 0.42, 0.3))
    kit.cyl("chest", 0.6, 0.8, (0, 0.05, 0.22), uni, 32, 0.05, r2=0.66)
    kit.cyl("neck", 0.13, 0.32, (0, 0.02, 0.95), skin, 16, 0.02)
    # the collar: a V of the shirt (or the accent) on the chest
    collar_m = acc if cid in ("cmd_lira", "cmd_seir", "cmd_vance") else kit.mat("shirt", "#e9e2d0", 0.6)
    me = bpy.data.meshes.new("collar")
    me.from_pydata([(-0.17, -0.47, 0.9), (0.17, -0.47, 0.9), (0.0, -0.53, 0.64)], [], [(0, 2, 1)])
    v = bpy.data.objects.new("collar", me)
    bpy.context.scene.collection.objects.link(v)
    me.materials.append(collar_m)
    # head
    kit.sphere("head", 1.0, (0, -0.02, HEAD_Z), skin, (hw, 0.37, hh))
    if cid in ("cmd_bram", "cmd_kort", "cmd_frey"):
        kit.sphere("jaw", 1.0, (0, -0.06, HEAD_Z - 0.2), skin, (hw * 0.92, 0.32, 0.22))
    for sx in (-1, 1):
        kit.sphere("ear", 1.0, (sx * hw * 0.98, 0.02, HEAD_Z - 0.02), skin, (0.06, 0.08, 0.1))
    # eyes, pupils, brows
    for sx in (-1, 1):
        kit.sphere("eye", 0.078, (sx * 0.135, -0.31, HEAD_Z + 0.03), white, (1.0, 0.6, 0.85), 2)
        pc = kit.mat("rai_eye", "#3a8dff", 0.2, emission="#5aa0ff", emit_strength=4.0) if cid == "cmd_rai" else dark
        kit.sphere("pupil", 0.045, (sx * 0.135 + 0.012, -0.355, HEAD_Z + 0.025), pc, (1, 0.6, 1.05), 2)
        b = kit.box("brow", (0.15, 0.04, 0.035), (sx * 0.14, -0.34, HEAD_Z + 0.13), brow, 0.01)
        b.rotation_euler.y = math.radians(-12 * sx if cid != "cmd_vega" or sx < 0 else 18)
    # nose and mouth
    if cid in ("cmd_bram", "cmd_kort"):
        kit.sphere("nose", 0.075, (0, -0.39, HEAD_Z - 0.06), skin, (1.0, 0.9, 0.9))
    else:
        n = kit.cone("nose", 0.05, 0.16, (0, -0.37, HEAD_Z - 0.04), skin, 8, 0.01)
        n.rotation_euler = (math.radians(-70), 0, 0)
    kit.box("mouth", (0.13, 0.03, 0.025), (0, -0.335, HEAD_Z - 0.18), lips, 0.01)
    # hair
    if style in ("short", "messy", "braid", "long", "ponytail", "updo", "bob", "buzz"):
        top = 0.3 if style != "buzz" else 0.24
        kit.sphere("hair_cap", 1.0, (0, 0.03, HEAD_Z + 0.16), hair, (hw + 0.03, 0.4, top + 0.06))
    if style == "messy":
        for k in range(6):
            a = -0.5 + k * 0.2
            c = kit.cone("tuft", 0.07, 0.18, (a * hw * 1.6, -0.2, HEAD_Z + 0.36), hair, 6, 0.0)
            c.rotation_euler = (math.radians(-40), math.radians(a * 50), 0)
    if style == "sides" or style == "bald":
        for sx in (-1, 1):
            kit.sphere("side_hair", 1.0, (sx * hw * 0.92, 0.05, HEAD_Z + 0.02), hair, (0.07, 0.2, 0.15))
    if style == "bob":
        for sx in (-1, 1):
            kit.sphere("bob", 1.0, (sx * hw * 0.92, 0.02, HEAD_Z - 0.02), hair, (0.1, 0.3, 0.28))
        kit.box("streak", (0.05, 0.05, 0.22), (-0.1, -0.33, HEAD_Z + 0.27), kit.mat("grey_streak", "#c4c4c4", 0.6), 0.02)
    if style == "braid":
        for k in range(5):
            kit.sphere("braid", 0.075 - k * 0.005, (hw * 0.75, -0.05 - k * 0.04, HEAD_Z - 0.2 - k * 0.12), hair)
    if style == "long":
        kit.sphere("long_hair", 1.0, (0, 0.12, HEAD_Z - 0.1), hair, (hw + 0.1, 0.32, 0.55))
    if style == "ponytail":
        c = kit.cone("ponytail", 0.11, 0.6, (hw * 0.4, 0.3, HEAD_Z + 0.05), hair, 10, 0.02)
        c.rotation_euler = (math.radians(150), math.radians(20), 0)
    if style == "updo":
        kit.sphere("bun", 0.17, (0, 0.06, HEAD_Z + 0.48), hair)
    # facial hair
    if facial.startswith("beard"):
        h = {"beard": 0.28, "beard_short": 0.18, "beard_long": 0.45}[facial]
        kit.sphere("beard", 1.0, (0, -0.16, HEAD_Z - 0.2 - h * 0.35), hair, (hw * 0.95, 0.27, h))
        kit.box("mouth_gap", (0.12, 0.03, 0.03), (0, -0.39 if facial != "beard_short" else -0.37, HEAD_Z - 0.18), lips, 0.01)
    if facial in ("mustache", "mustache_long", "beard", "beard_long"):
        ln = 0.26 if facial == "mustache_long" else 0.13
        for sx in (-1, 1):
            m = kit.sphere("mustache", 1.0, (sx * ln * 0.55, -0.36, HEAD_Z - 0.13 - (0.06 if facial == "mustache_long" else 0)), hair, (ln * 0.55, 0.05, 0.045))
            m.rotation_euler.y = math.radians(25 * sx if facial == "mustache_long" else 10 * sx)
    # headgear
    if gear == "kerchief":
        kit.sphere("kerchief", 1.0, (0, 0.02, HEAD_Z + 0.2), acc, (hw + 0.05, 0.41, 0.3))
    if gear in ("goggles", "flight"):
        if gear == "flight":
            kit.sphere("helmet", 1.0, (0, 0.03, HEAD_Z + 0.12), kit.mat("leather", "#6b4428", 0.55), (hw + 0.05, 0.42, 0.36))
        strap = kit.mat("strap", "#2a2a2a", 0.5)
        for sx in (-1, 1):
            g = kit.cyl("goggle", 0.075, 0.06, (sx * 0.13, -0.33, HEAD_Z + 0.27), strap, 16, 0.01)
            g.rotation_euler.x = math.radians(80)
            lens = kit.cyl("lens", 0.055, 0.02, (sx * 0.13, -0.365, HEAD_Z + 0.272), kit.mat("lens", "#8fc4d8" if gear == "goggles" else "#6fa8dc", 0.1, 0.3), 16, 0.0)
            lens.rotation_euler.x = math.radians(80)
    if gear == "hood":
        kit.sphere("hood", 1.0, (0, 0.08, HEAD_Z + 0.06), uni, (hw + 0.1, 0.42, 0.5))
        kit.sphere("hood_face", 1.0, (0, -0.02, HEAD_Z - 0.02), skin, (hw * 0.96, 0.36, hh * 0.9))
        kit.sphere("hood_hair", 1.0, (0, -0.06, HEAD_Z + 0.2), hair, (hw * 0.85, 0.33, 0.14))
    if gear == "glasses":
        frame = kit.mat("frame", "#c8ccd4", 0.3, 0.8)
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.085, minor_radius=0.012, location=(sx * 0.13, -0.36, HEAD_Z + 0.03), rotation=(math.radians(90), 0, 0))
            bpy.context.active_object.data.materials.append(frame)
    if gear == "tricorn":  # the admiral's peaked cap (04 §15.3: tricorn → cap by era)
        hat = kit.mat("hat", "#1d2533", 0.55)
        kit.cyl("cap_top", hw + 0.06, 0.1, (0, 0.04, HEAD_Z + 0.34), hat, 32, 0.03, r2=hw + 0.12)
        kit.cyl("cap_band", hw + 0.03, 0.07, (0, 0.03, HEAD_Z + 0.27), acc, 32, 0.01)
        visor = kit.sphere("visor", 1.0, (0, -0.3, HEAD_Z + 0.24), kit.mat("visor", "#0d0f14", 0.25), (hw * 0.75, 0.16, 0.03))
        visor.rotation_euler.x = math.radians(-12)
        kit.sphere("badge", 0.04, (0, -0.37, HEAD_Z + 0.3), kit.mat("gold_badge", "#e8b23a", 0.25, 0.8), (1, 0.5, 1))
    if gear == "circlet":
        silver = kit.mat("silver", "#d0d6de", 0.25, 0.9)
        bpy.ops.mesh.primitive_torus_add(major_radius=hw + 0.005, minor_radius=0.018, location=(0, -0.01, HEAD_Z + 0.22), rotation=(math.radians(-8), 0, 0))
        bpy.context.active_object.data.materials.append(silver)
        kit.sphere("raivite", 0.055, (0, -0.375, HEAD_Z + 0.2), kit.mat("raivite_gem", "#3a8dff", 0.1, emission="#5aa0ff", emit_strength=6.0), (1, 0.6, 1.25))
    if gear == "brooch":
        kit.sphere("brooch", 0.06, (0, -0.4, 0.66), kit.mat("pearl", "#f4f1ea", 0.15), (1, 0.6, 1))
    # uniform details
    if cid in ("cmd_vega", "cmd_frey", "cmd_kort", "cmd_vance", "cmd_rai"):
        for sx in (-1, 1):
            kit.sphere("epaulette", 1.0, (sx * 0.5, -0.02, 0.86), acc, (0.17, 0.2, 0.06))
    if cid == "cmd_kort":
        bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.09, location=(0, 0.02, 0.86))
        bpy.context.active_object.data.materials.append(kit.mat("fur", "#8a6a48", 0.9))
    if cid == "cmd_hawk":
        bpy.ops.mesh.primitive_torus_add(major_radius=0.2, minor_radius=0.075, location=(0, 0.0, 0.9))
        bpy.context.active_object.data.materials.append(kit.mat("scarf", "#f4f4f4", 0.7))
    if cid == "cmd_olm":
        kit.box("apron", (0.62, 0.05, 0.7), (0, -0.42, 0.3), kit.mat("apron", "#5a3820", 0.7), 0.03)
        kit.box("wrench", (0.05, 0.03, 0.3), (0.18, -0.46, 0.38), kit.mat("brass", "#c9a24a", 0.3, 0.8), 0.01)
    if cid == "cmd_lira":
        s = kit.box("bag_strap", (0.08, 0.04, 1.0), (0.05, -0.38, 0.45), kit.mat("strap_lira", "#7a5a3a", 0.7), 0.01)
        s.rotation_euler.y = math.radians(35)
    if cid == "cmd_rai":
        kit.sphere("cloak", 1.0, (0, 0.18, 0.55), kit.mat("cloak", "#3a8dff", 0.6), (0.72, 0.4, 0.5))


def setup(size):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 40
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = size
    sc.render.resolution_y = int(size * 1.15)
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.6, 0.7, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    key.data.energy = 260
    key.data.size = 2.5
    key.location = (-2.2, -2.6, 2.8)
    key.rotation_euler = (math.radians(50), 0, math.radians(-40))
    sc.collection.objects.link(key)
    rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", "AREA"))
    rim.data.energy = 160
    rim.data.size = 1.5
    rim.location = (2.2, 1.8, 2.4)
    rim.rotation_euler = (math.radians(-50), 0, math.radians(140))
    sc.collection.objects.link(rim)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 85
    cam.location = (-1.4, -3.85, 1.7)
    target = (0.0, 0.0, 1.17)
    d = [target[i] - cam.location[i] for i in range(3)]
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    sc.camera = cam


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    size = 256
    for a in sys.argv[1:]:
        if a.startswith("--size="):
            size = int(a[7:])
    out = args[0]
    ids = args[1:] or list(LOOK)
    os.makedirs(out, exist_ok=True)
    for cid in ids:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        kit._MATS.clear()
        build(cid)
        setup(size)
        bpy.context.scene.render.filepath = os.path.join(out, cid + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", cid)


main()
