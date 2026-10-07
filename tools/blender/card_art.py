"""Illustrations for the battle cards (art direction: the «War Cards» panel of the concept art — tall cards with a
painted scene and a cost coin), rendered from the game's own models with a dramatic sky, fire and smoke.

Run: python3 tools/blender/card_art.py game/assets/ui/cards [card ...]
Writes <card>.png (270 × 300) for attack, breakthrough, airstrike, encircle, defense, landing, missile, corps.
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import box, cone, cyl, mat, sphere  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "..", "..", "game", "assets", "models")
W, H = 270, 300


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()


def glow(name, color, strength):
    return mat(name, color, 0.5, 0.0, color, strength)


def load(name, loc=(0, 0, 0), rz=0.0, s=1.0):
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(MODELS, name + ".glb"))
    for o in bpy.context.scene.objects:
        if o not in before and o.parent is None:
            o.location = loc
            o.rotation_euler.z = rz
            o.scale = (s, s, s)


def sky(top, bottom, ground="#2c3a22"):
    """A big backdrop with a vertical gradient (emissive, so it reads as a painted sky) and a ground plane."""
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 9, 6), rotation=(math.pi / 2, 0, 0))
    bd = bpy.context.active_object
    m = bpy.data.materials.new("sky")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (*kit.srgb(bottom), 1)
    ramp.color_ramp.elements[1].position = 0.62
    ramp.color_ramp.elements[1].color = (*kit.srgb(top), 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs[0])
    bd.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    g = bpy.context.active_object
    g.data.materials.append(kit.noisy_mat("ground", ground, "#4a5a30", 3.0))


def smoke_mat():
    m = bpy.data.materials.get("smoke_soft")
    if m:
        return m
    m = mat("smoke_soft", "#6e6660", 0.95)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Alpha"].default_value = 0.55
    return m


def fireball(x, y, z, r=0.25):
    sphere("fire", r, (x, y, z), glow("fire", "#e8420a", 1.3), (1.2, 1, 0.9), 2)
    sphere("fire_mid", r * 0.75, (x, y - r * 0.2, z - r * 0.05), glow("fire_mid", "#ff8a1a", 1.8), (1.1, 1, 0.9), 2)
    sphere("fire_core", r * 0.45, (x, y - r * 0.45, z - r * 0.1), glow("fire_core", "#ffd060", 2.6), (1, 1, 0.9), 2)
    for k, (dx, dz, rr) in enumerate(((-0.25, 0.4, 0.6), (0.3, 0.45, 0.55), (0.0, 0.7, 0.75), (-0.15, 1.05, 0.7), (0.15, 1.35, 0.6))):
        sphere("smoke", r * rr, (x + dx * r * 3, y + 0.3, z + dz * r * 3), smoke_mat(), (1.3, 1, 1), 3)
    bpy.ops.object.light_add(type="POINT", location=(x, y - 0.4, z))
    bpy.context.active_object.data.energy = 120 * r * 4
    bpy.context.active_object.data.color = (1.0, 0.55, 0.2)


def lights(key=6.0, rim="#7fb2ff"):
    bpy.ops.object.light_add(type="AREA", location=(0.8, -3.0, 2.2))  # a soft fill from the camera side
    f = bpy.context.active_object
    f.data.energy = 220
    f.data.size = 3.0
    f.rotation_euler = (math.radians(55), 0, math.radians(15))
    bpy.ops.object.light_add(type="SUN")
    s = bpy.context.active_object
    s.data.energy = key
    s.data.color = (1.0, 0.92, 0.8)
    s.rotation_euler = (math.radians(50), math.radians(-25), math.radians(-30))
    bpy.ops.object.light_add(type="SUN")
    r = bpy.context.active_object
    r.data.energy = 2.0
    r.data.color = kit.srgb(rim)
    r.rotation_euler = (math.radians(70), 0, math.radians(160))


def camera(loc, target, lens=50):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.lens = lens
    cam.location = loc
    d = [target[i] - loc[i] for i in range(3)]
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    bpy.context.scene.camera = cam


def render(path):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x = W
    sc.render.resolution_y = H
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.07, 0.12, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ scenes


def attack():
    sky("#1d2a4a", "#e0703a")
    load("squad_dl6_blue", (0, 0, 0), math.radians(200), 1.6)
    fireball(0.9, 1.6, 0.35, 0.35)
    fireball(-1.0, 2.2, 0.3, 0.25)
    lights()
    camera((0.7, -1.7, 0.75), (0, 0.15, 0.42), 40)


def breakthrough():
    sky("#22304f", "#d9894a", "#4a3a26")
    load("assault_dl6_blue", (0, 0, 0), math.radians(235), 2.4)
    for k, (x, y, r) in enumerate(((0.6, 0.7, 0.35), (-0.5, 0.9, 0.3), (0.1, 1.1, 0.45))):
        sphere("dust", r, (x, y, r * 0.5), mat("dust", "#a08060", 0.95), (1.4, 1, 0.8), 2)
    fireball(-1.1, 2.0, 0.4, 0.3)
    lights()
    camera((1.0, -1.8, 0.7), (0, 0.1, 0.32), 40)


def plane(color="#2e6bff"):
    body = mat("plane_body", color, 0.45, 0.2)
    dark = mat("plane_dark", "#20242c", 0.5)
    white = mat("plane_white", "#f3efe6", 0.5)
    f = cyl("fuselage", 0.11, 1.0, (0, 0, 0), body, 16, 0.02, r2=0.06)
    f.rotation_euler.y = math.pi / 2
    sphere("nose", 0.11, (0.5, 0, 0), body, (0.6, 1, 1), 2)
    cyl("spinner", 0.05, 0.08, (0.58, 0, 0), dark, 12, 0.01).rotation_euler.y = math.pi / 2
    d = cyl("prop", 0.32, 0.01, (0.62, 0, 0), mat("prop", "#c8ccd4", 0.4), 24, 0.0)
    d.rotation_euler.y = math.pi / 2
    box("wing", (0.3, 1.4, 0.03), (0.12, 0, -0.03), body, 0.02)
    box("tailplane", (0.15, 0.5, 0.02), (-0.46, 0, 0.0), body, 0.01)
    box("fin", (0.18, 0.02, 0.2), (-0.46, 0, 0.1), body, 0.01)
    sphere("canopy", 0.08, (0.15, 0, 0.09), mat("canopy", "#9fd4ff", 0.15), (1.6, 0.8, 0.8), 2)
    for sy in (-1, 1):
        cyl("roundel", 0.1, 0.01, (0.1, sy * 0.48, 0.0), white, 16, 0.0)
        cyl("roundel_c", 0.05, 0.012, (0.1, sy * 0.48, 0.0), body, 12, 0.0)
        cyl("bomb", 0.03, 0.16, (0.1, sy * 0.25, -0.1), dark, 10, 0.01).rotation_euler.y = math.pi / 2


def airstrike():
    sky("#1a2850", "#e07a40")
    before = set(bpy.context.scene.objects)
    plane()
    grp = [o for o in bpy.context.scene.objects if o not in before]
    bpy.ops.object.empty_add(location=(0, 0, 0))
    piv = bpy.context.active_object
    for o in grp:
        o.parent = piv
    piv.location = (0, 0, 1.15)
    piv.rotation_euler = (math.radians(-14), math.radians(10), math.radians(205))
    fireball(0.2, 1.2, 0.25, 0.32)
    fireball(-0.8, 1.8, 0.2, 0.22)
    lights()
    camera((0.6, -2.6, 1.3), (0, 0.3, 0.95), 42)


def encircle():
    sky("#202a48", "#b8443a", "#3a2a22")
    load("squad_dl6_red", (0, 0.2, 0), math.radians(180), 1.6)
    ring = glow("ring", "#3aa0ff", 6.0)
    bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.035, major_segments=48, minor_segments=8, location=(0, 0.2, 0.08))
    bpy.context.active_object.data.materials.append(ring)
    for k in range(4):
        a = k * math.tau / 4 + 0.4
        c = cone("arrow", 0.1, 0.24, (math.cos(a) * 1.0, 0.2 + math.sin(a) * 1.0, 0.08), ring, 10, 0.0)
        c.rotation_euler = (0, math.pi / 2, a + math.pi / 2)
    bpy.ops.object.light_add(type="POINT", location=(0, 0.2, 0.4))
    bpy.context.active_object.data.energy = 60
    bpy.context.active_object.data.color = (0.3, 0.6, 1.0)
    lights(5.0, "#ff6a5a")
    camera((0, -2.2, 2.0), (0, 0.25, 0.2), 38)


def defense():
    sky("#1d2c4c", "#6a86b8", "#3a4030")
    load("fort_l3_edge", (0, 1.0, 0), math.radians(90), 2.2)
    steel = mat("steel", "#9aa3ad", 0.35, 0.8)
    field = mat("field", "#2e6bff", 0.5)
    # a heater shield: a pointed outline extruded, a steel rim and a white emblem
    outline = [(-0.5, 0.45), (0.5, 0.45), (0.5, 0.05), (0.32, -0.38), (0.0, -0.62), (-0.32, -0.38), (-0.5, 0.05)]

    def shield(scale, mt, y, name):
        me = bpy.data.meshes.new(name)
        verts = [(x * scale, y, z * scale + 0.75) for (x, z) in outline] + [(x * scale, y + 0.06, z * scale + 0.75) for (x, z) in outline]
        n = len(outline)
        faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] + [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        me.from_pydata(verts, [], faces)
        o = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(o)
        me.materials.append(mt)
        return o
    shield(1.08, steel, 0.02, "rim")
    shield(1.0, field, -0.01, "face")
    star = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = 0.27 if k % 2 == 0 else 0.11
        star.append((math.cos(a) * rr, math.sin(a) * rr + 0.82))
    me = bpy.data.meshes.new("star")
    me.from_pydata([(x, -0.025, z) for (x, z) in star] + [(0, -0.025, 0.82)], [], [(10, k, (k + 1) % 10) for k in range(10)])
    so = bpy.data.objects.new("star", me)
    bpy.context.scene.collection.objects.link(so)
    me.materials.append(mat("emblem", "#f3efe6", 0.5))
    for (x, z) in ((-0.42, 1.15), (0.42, 1.15), (0.0, 0.18), (-0.45, 0.82), (0.45, 0.82)):
        sphere("rivet", 0.03, (x, -0.02, z), steel, (1, 0.6, 1), 1)
    lights(4.5)
    camera((0.35, -2.6, 1.05), (0, 0.3, 0.75), 42)


def landing():
    sky("#1d2c50", "#d88a4a", "#1d4a6a")
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0.02))
    sea = bpy.context.active_object
    sea.data.materials.append(mat("sea", "#1f5a86", 0.12, 0.2))
    hull = mat("hull", "#5b6436", 0.6)
    dark = mat("hull_d", "#3d4428", 0.6)
    # a landing craft with its bow ramp down and a squad aboard, wake behind it
    box("hull", (1.1, 0.55, 0.22), (0, 0.2, 0.1), hull, 0.03)
    for sy in (-1, 1):
        box("side", (1.1, 0.04, 0.16), (0, 0.2 + sy * 0.27, 0.28), dark, 0.01)
    r = box("ramp", (0.05, 0.55, 0.42), (-0.62, 0.2, 0.18), dark, 0.01)
    r.rotation_euler.y = -1.0
    box("wheelhouse", (0.22, 0.3, 0.2), (0.45, 0.2, 0.36), hull, 0.02)
    load("squad_dl6_blue", (0.0, 0.2, 0.2), math.radians(90), 0.95)
    for k in range(5):
        sphere("wake", 0.1 + k * 0.03, (0.65 + k * 0.18, 0.2 + (k % 2 - 0.5) * 0.15, 0.03), mat("foam", "#e8f0f4", 0.6), (1.5, 1, 0.3), 2)
    fireball(-1.4, 2.4, 0.3, 0.3)
    lights()
    camera((-0.4, -2.2, 1.1), (0, 0.25, 0.3), 38)


def missile():
    sky("#0f1a36", "#5a3a6a", "#2a2e2a")
    load("rocket_launcher", (0.2, 0.3, 0), math.radians(200), 2.2)
    white = mat("rocket", "#e3e8ee", 0.4)
    # the rocket climbing away on a column of flame and smoke
    rx, ry, rz = -0.35, 0.9, 1.35
    piv_before = set(bpy.context.scene.objects)
    cyl("rocket_body", 0.05, 0.42, (0, 0, 0), white, 12, 0.01)
    cone("rocket_nose", 0.05, 0.14, (0, 0, 0.28), mat("rocket_tip", "#c0392b", 0.4), 12, 0.0)
    for k in range(4):
        f = box("fin", (0.012, 0.09, 0.1), (0, 0, -0.17), white, 0.003)
        f.rotation_euler.z = k * math.pi / 2
        f.location = (math.cos(k * math.pi / 2) * 0.05, math.sin(k * math.pi / 2) * 0.05, -0.17)
    cone("flame", 0.06, 0.4, (0, 0, -0.42), glow("flame", "#ffb040", 3.0), 12, 0.0).rotation_euler.x = math.pi
    grp = [o for o in bpy.context.scene.objects if o not in piv_before]
    bpy.ops.object.empty_add(location=(0, 0, 0))
    piv = bpy.context.active_object
    for o in grp:
        o.parent = piv
    piv.location = (rx, ry, rz)
    piv.rotation_euler = (math.radians(-20), math.radians(-25), 0)
    for k in range(7):
        t = k / 6
        sphere("trail", 0.08 + t * 0.12, (rx + 0.2 + t * 0.6, ry - 0.1 - t * 0.5, rz - 0.45 - t * 1.0), smoke_mat(), (1, 1, 1), 3)
    bpy.ops.object.light_add(type="POINT", location=(rx + 0.1, ry - 0.3, rz - 0.4))
    bpy.context.active_object.data.energy = 150
    bpy.context.active_object.data.color = (1.0, 0.65, 0.3)
    lights(4.0, "#b07aff")
    camera((0.9, -2.3, 0.9), (-0.05, 0.4, 0.75), 40)


def corps():
    sky("#1d2c4c", "#e0a050", "#34482a")
    load("squad_dl6_green", (0.25, 0.25, 0), math.radians(200), 1.4)
    load("banner_blue", (-0.45, 0.35, 0), math.radians(10), 1.4)
    load("banner_green", (0.75, 0.6, 0), math.radians(-10), 1.4)
    lights()
    camera((0.3, -2.1, 0.95), (0.1, 0.3, 0.6), 40)


SCENES = {"attack": attack, "breakthrough": breakthrough, "airstrike": airstrike, "encircle": encircle, "defense": defense,
          "landing": landing, "missile": missile, "corps": corps}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "game/assets/ui/cards"
    os.makedirs(out, exist_ok=True)
    for name in (args[1:] or list(SCENES)):
        reset()
        SCENES[name]()
        render(os.path.join(os.path.abspath(out), name + ".png"))
        print("CARD", name, flush=True)
