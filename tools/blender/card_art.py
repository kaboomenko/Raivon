"""Illustrations for the battle cards (art direction: the «War Cards» panel of the concept art — tall cards with a
painted scene and a cost coin), rendered from the game's own models with a dramatic sky, fire and smoke; the Army
tab's unit cards, the hex panel's tiles, and the Buildings tab's building cards.

Run: python3 tools/blender/card_art.py game/assets/ui/cards [card ...]
Writes <card>.png: 270 × 300 for attack, breakthrough, airstrike, encircle, defense, landing, missile, corps and
unit_dl1..8; 160 × 140 for tile_*; 270 × 180 for bld_<type> (every building the Buildings tab lists — see BUILDINGS).
Card art gets no ink rim (that is for icons only).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

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


def sky(top, bottom, ground="#2c3a22", ground2="#4a5a30", band=(0.42, 0.62)):
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
    ramp.color_ramp.elements[0].position = band[0]  # the backdrop's height share where the horizon colour ends
    ramp.color_ramp.elements[0].color = (*kit.srgb(bottom), 1)
    ramp.color_ramp.elements[1].position = band[1]
    ramp.color_ramp.elements[1].color = (*kit.srgb(top), 1)
    nt.links.new(ramp.outputs["Color"], em.inputs["Color"])
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], out.inputs[0])
    bd.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    g = bpy.context.active_object
    g.data.materials.append(kit.noisy_mat("ground", ground, ground2, 3.0))


def smoke_mat():
    m = bpy.data.materials.get("smoke_soft")
    if m:
        return m
    m = mat("smoke_soft", "#a8a19a", 0.95)  # grey-white battle smoke (dark smoke read as rocks on the bright sky)
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


def render(path, w=None, h=None, transparent=False, world=None):
    sc = bpy.context.scene
    sc.render.film_transparent = transparent
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x = w or W
    sc.render.resolution_y = h or H
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (*kit.srgb(world[0]), 1) if world else (0.05, 0.07, 0.12, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = world[1] if world else 0.6
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ scenes

# One stage for every battle card (docs/ui_style.md s02): the same warm afternoon sky, meadow and key light, so the
# eight cards in a hand read as one set on the brighter, sunnier map (docs/art_direction.md §6).
STAGE_SKY = ("#3f8fe2", "#fde6be")  # zenith, horizon
STAGE_GROUND = ("#6f9f42", "#8abb52")
STAGE_WORLD = ("#bcd8f0", 0.75)
BATTLE = ("attack", "breakthrough", "airstrike", "encircle", "defense", "landing", "missile", "corps")


def stage():
    # the backdrop spans z −14…26 at y 9: the band 0.335…0.43 puts the horizon colour at the ground line and the
    # zenith blue at the top of a card's frame
    sky(STAGE_SKY[0], STAGE_SKY[1], *STAGE_GROUND, band=(0.335, 0.43))
    lights(5.0, "#9cc4ff")



def attack():
    stage()
    load("squad_dl6_blue", (0, 0, 0), math.radians(200), 1.6)
    fireball(0.9, 1.6, 0.35, 0.35)
    fireball(-1.0, 2.2, 0.3, 0.25)
    camera((0.7, -1.7, 0.75), (0, 0.15, 0.42), 40)


def breakthrough():
    stage()
    load("assault_dl6_blue", (0, 0, 0), math.radians(235), 2.4)
    for k, (x, y, r) in enumerate(((0.6, 0.7, 0.35), (-0.5, 0.9, 0.3), (0.1, 1.1, 0.45))):
        sphere("dust", r, (x, y, r * 0.5), mat("dust", "#a08060", 0.95), (1.4, 1, 0.8), 2)
    fireball(-1.1, 2.0, 0.4, 0.3)
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
    stage()
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
    camera((0.6, -2.6, 1.3), (0, 0.3, 0.95), 42)


def encircle():
    stage()
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
    camera((0, -2.2, 2.0), (0, 0.25, 0.2), 38)


def defense():
    stage()
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
    camera((0.35, -2.6, 1.05), (0, 0.3, 0.75), 42)


def landing():
    stage()
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
    camera((-0.4, -2.2, 1.1), (0, 0.25, 0.3), 38)


def missile():
    stage()
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
    camera((0.9, -2.3, 0.9), (-0.05, 0.4, 0.75), 40)


def corps():
    stage()
    load("squad_dl6_green", (0.25, 0.25, 0), math.radians(200), 1.4)
    load("banner_blue", (-0.45, 0.35, 0), math.radians(10), 1.4)
    load("banner_green", (0.75, 0.6, 0), math.radians(-10), 1.4)
    camera((0.3, -2.1, 0.95), (0.1, 0.3, 0.6), 40)


def unit(n):
    """The Army tab's card picture (the unit cards of the reference HUD): the era's infantry up close with its
    assault unit behind, under the card sky."""
    def scene():
        sky("#1d2c4c", "#d8a060", "#34482a")
        load("squad_dl%d_blue" % n, (0.05, 0.1, 0), math.radians(205), 1.7)
        if n >= 2:
            load("assault_dl%d_blue" % n, (0.75, 0.75, 0), math.radians(215), 1.5)
        lights()
        camera((0.35, -1.55, 0.72), (0.15, 0.25, 0.32), 40)
    return scene


TILE_MODELS = {
    "plain": [("tree_round", (0.45, 0.3), 0.8), ("bush", (-0.4, -0.2), 1.2), ("flowers", (0.1, -0.4), 1.2)],
    "forest": [("tree_pine", (x, y), 1.0) for (x, y) in ((-0.4, 0.1), (0.0, 0.35), (0.35, 0.05), (-0.1, -0.25), (0.4, -0.35), (-0.5, -0.4), (0.15, -0.05))],
    "hills": [("rock", (-0.3, 0.1), 1.8), ("rock", (0.35, -0.1), 1.5), ("rock", (0.0, -0.4), 1.2), ("tree_pine", (0.3, 0.4), 0.9)],
    "mountain": [("mountain", (0, 0), 1.3)],
    "water": [],
    "farm": [("wheat_field", (0.1, 0.1), 0.95), ("windmill", (-0.45, -0.3), 0.95)],
    "mine": [("mine", (0, 0), 1.1)],
    "city": [("city_dl3_blue", (0, 0), 1.15)],
    "capital": [("residence_dl4_blue", (0, 0), 1.0)],
    "port": [("port", (0, 0), 1.0)],
    "military_base": [("military_base", (0, 0), 1.0)],
}
# the capital and the city of each development level in each state colour (the hex panel follows the owner's era)
for _n in range(1, 9):
    for _side in ("blue", "red", "green"):
        TILE_MODELS["capital_dl%d_%s" % (_n, _side)] = [("residence_dl%d_%s" % (_n, _side), (0, 0), 0.9 if _n >= 7 else 1.0)]
        TILE_MODELS["city_dl%d_%s" % (_n, _side)] = [("city_dl%d_%s" % (_n, _side), (0, 0), 1.0 if _n >= 7 else 1.15)]


def tile(kind):
    """The hex panel's picture (the «Равнина» tile of the reference HUD): one hex of that land or building."""
    def scene():
        grass = kit.noisy_mat("grass", "#4c7a2c", "#5f8f36", 4.0)
        dirt = kit.noisy_mat("dirt", "#5b4029", "#6d4a2c", 6.0)
        if kind == "water":
            grass = mat("water", "#1b5a78", 0.15, 0.2)
        kit.hex_prism("tile", (0, 0, -0.18), 1.0, 0.18, grass, dirt, 0.03)
        for name, (x, y), sc in TILE_MODELS[kind]:
            load(name, (x, y, 0), 0.4, sc)
        lights(4.0)
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        bpy.context.scene.collection.objects.link(cam)
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = 2.5
        el = math.radians(42)
        cam.location = (0, -12 * math.cos(el), 12 * math.sin(el) + 0.2)
        cam.rotation_euler = (math.pi / 2 - el, 0, 0)
        bpy.context.scene.camera = cam
    return scene


# ------------------------------------------------------------------ building cards (docs/ui_style.md §4.4, «Здания»)
#
# The Buildings tab's card art: the building on a round grass plot under the card sky, 270 × 180. The model is
# rendered on a transparent film with a shadow catcher under it; the backdrop (SKY_TOP → SKY_LOW gradient, a GRASS
# disc that is the projected ground circle, with a darker lip) is painted in Pillow, so the UI tokens stay exact.

SKY_TOP, SKY_LOW, GRASS, GRASS_LIP = "#8FCDF2", "#E3F4FD", "#86C45E", "#5E9A40"
BW, BH = 270, 180
BLUE = "#3f86f0"  # the player's team colour on models (docs/art_direction.md §6.3)
ROOF = "#2d55b8"  # the roof blue of the map's stone houses (export_assets.ROOF_BLUE)
STONE_C, BEAM, PLASTER, THATCH_C = "#d3c8b4", "#6b4a30", "#efe3c8", "#d8b25c"

# Buildings that have a map model: (model, (x, y), rz, scale). The DL1 models, blue team.
BUILDING_MODELS = {
    "residence": [("residence_dl1_blue", (0, 0), 0.3, 1.0)],
    "barracks": [("barracks", (0, 0), 0.0, 1.0)],
    "quarters": [("city_dl1_blue", (0, 0), 0.2, 1.0)],
    "farm": [("wheat_field", (0.22, 0.12), 0.0, 0.72), ("wheat_field", (-0.2, 0.42), math.pi, 0.45),
             ("windmill", (-0.36, -0.12), 0.4, 0.95)],
    "mine": [("mine", (0, 0), 0.2, 1.0)],
    "port": [("port", (0, 0), 0.0, 1.0)],
    "military_base": [("military_base", (0, 0), 0.3, 1.0)],
}


def _wall_house(x, y, w, d, h, wall, roof, rz=0.0, roof_h=None):
    """A chunky house: a soft box, a gable roof with a darker trim, corner beams."""
    o = box("wall", (w, d, h), (x, y, h / 2), mat("wall" + wall, wall, 0.85), 0.02)
    o.rotation_euler.z = rz
    kit.prism_roof("roof", w, d, roof_h or h * 0.85, (x, y, h), mat("roof" + roof, roof, 0.6), overhang=0.05, rot_z=rz)
    return o


def _door(x, y, z, w, h, rz=0.0):
    d = box("door", (w, 0.03, h), (x, y, z + h / 2), mat("door_b", "#5a3a22", 0.8), 0.008)
    d.rotation_euler.z = rz


def _window(x, y, z, s=0.07):
    box("win", (s, 0.02, s * 1.2), (x, y, z), mat("win_lit", "#ffd27a", 0.4, 0.0, "#ffb84a", 1.2), 0.004)


def _flag(x, y, h, color, w=0.2):
    cyl("pole", 0.014, h, (x, y, h / 2), mat("pole_b", "#e8e0d0", 0.5), 8, 0.0)
    sphere("finial", 0.026, (x, y, h + 0.02), mat("gold_b", "#e6b13e", 0.3, 0.6), (1, 1, 1), 2)
    f = box("flag", (w, 0.012, w * 0.62), (x + w / 2 + 0.012, y, h - w * 0.33), mat("flag" + color, color, 0.65), 0.004)
    return f


def _crate(x, y, z, s, rz=0.0):
    b = box("crate", (s, s, s), (x, y, z + s / 2), mat("crate_w", "#b07d47", 0.75), 0.012)
    b.rotation_euler.z = rz
    for dz in (0.2, 0.8):
        p = box("plank", (s + 0.006, s + 0.006, s * 0.12), (x, y, z + s * dz), mat("crate_d", "#7a4e2a", 0.75), 0.003)
        p.rotation_euler.z = rz


def _sack(x, y, s=1.0):
    sphere("sack", 0.07 * s, (x, y, 0.06 * s), mat("sack_b", "#dcbb7c", 0.9), (1.0, 0.9, 1.0), 2)
    cyl("sack_n", 0.025 * s, 0.05 * s, (x, y, 0.13 * s), mat("sack_b", "#dcbb7c", 0.9), 8, 0.0)


def _barrel_prop(x, y, s=1.0):
    cyl("barrel", 0.06 * s, 0.15 * s, (x, y, 0.075 * s), mat("barrel_w", "#9a6a3c", 0.75), 12, 0.01)
    for z in (0.03, 0.12):
        cyl("hoop", 0.063 * s, 0.015 * s, (x, y, z * s), mat("iron_b", "#5d6470", 0.5, 0.5), 12, 0.0)


def _bush(x, y, s=1.0):
    sphere("bush", 0.08 * s, (x, y, 0.06 * s), mat("bush_c", "#4f9a3a", 0.85), (1.2, 1.1, 0.9), 2)
    sphere("bush2", 0.06 * s, (x + 0.05 * s, y - 0.03 * s, 0.09 * s), mat("bush_l", "#6bb84a", 0.85), (1, 1, 0.9), 2)


def _academy():
    """A stone hall of learning with a blue roof and an observatory tower: a dome and a brass telescope."""
    _wall_house(0.1, 0.05, 0.62, 0.38, 0.32, STONE_C, ROOF)
    for k in range(3):
        _window(-0.08 + k * 0.18, -0.145, 0.19)
    _door(0.1, -0.15, 0.0, 0.1, 0.17)
    cyl("tower", 0.17, 0.62, (-0.3, -0.02, 0.31), mat("wall" + STONE_C, STONE_C, 0.85), 20, 0.015)
    cyl("tower_lip", 0.19, 0.05, (-0.3, -0.02, 0.62), mat("roof_trim", "#8c86a0", 0.7), 20, 0.01)
    sphere("dome", 0.18, (-0.3, -0.02, 0.64), mat("roof" + ROOF, ROOF, 0.6), (1, 1, 0.9), 3)
    _window(-0.3, -0.19, 0.42, 0.075)
    t = cyl("scope", 0.035, 0.32, (-0.22, -0.06, 0.8), mat("brass_b", "#e6b13e", 0.3, 0.8), 12, 0.006, r2=0.026)
    t.rotation_euler.y = 0.85
    box("sign", (0.2, 0.02, 0.12), (0.1, -0.16, 0.25), mat("sign_b", "#f3efe6", 0.6), 0.006)
    box("sign_book", (0.12, 0.022, 0.07), (0.1, -0.165, 0.25), mat("book_c", "#8a3b2a", 0.6), 0.004)
    _bush(0.48, -0.2)
    _bush(-0.5, -0.2, 0.8)


def _warehouse():
    """A big timber barn with wide doors, crates, sacks and barrels stacked outside."""
    _wall_house(0.0, 0.08, 0.7, 0.44, 0.34, "#b68a58", ROOF, roof_h=0.32)
    for k in range(5):
        box("board", (0.012, 0.012, 0.32), (-0.28 + k * 0.14, -0.145, 0.17), mat("wall_d", "#8a6238", 0.85), 0.0)
    box("doors", (0.26, 0.03, 0.26), (0.0, -0.15, 0.13), mat("door_b", "#5a3a22", 0.8), 0.008)
    for s_ in (-1, 1):
        b = box("brace", (0.012, 0.035, 0.34), (0.0, -0.17, 0.13), mat("wall_d", "#8a6238", 0.85), 0.0)
        b.rotation_euler.y = s_ * 0.78
    _crate(-0.42, -0.24, 0.0, 0.16, 0.3)
    _crate(-0.38, -0.25, 0.16, 0.12, -0.2)
    _crate(0.38, -0.3, 0.0, 0.13, -0.3)
    for (x, y) in ((0.24, -0.34), (0.18, -0.42), (0.3, -0.45)):
        _sack(x, y)
    _barrel_prop(-0.2, -0.38)
    _barrel_prop(-0.08, -0.42, 0.9)


def _infirmary():
    """A white cottage with a blue roof, a green herb sign and herb beds in front."""
    _wall_house(0.0, 0.1, 0.56, 0.38, 0.3, PLASTER, ROOF)
    for x in (-0.16, 0.16):
        _window(x, -0.1, 0.18)
    _door(0.0, -0.1, 0.0, 0.1, 0.17)
    sphere("sign", 0.075, (0.0, -0.11, 0.38), mat("sign_g", "#f3efe6", 0.6), (1, 0.3, 1), 2)
    leaf = mat("herb", "#3fae5a", 0.6)
    for a in (-0.6, 0.0, 0.6):
        lf = sphere("leaf", 0.03, (math.sin(a) * 0.025, -0.135, 0.38 + math.cos(a) * 0.025), leaf, (0.6, 0.3, 1.2), 2)
        lf.rotation_euler.y = a
    for (x, y) in ((-0.3, -0.34), (0.3, -0.34)):
        box("bed", (0.32, 0.16, 0.05), (x, y, 0.025), mat("soil", "#8a6448", 0.9), 0.01)
        for k in range(4):
            sphere("herb", 0.04, (x - 0.11 + k * 0.073, y, 0.08), mat("herb_" + str(k % 2), "#4f9a3a" if k % 2 else "#6bb84a", 0.85), (1, 1, 1.1), 2)
    cyl("pot", 0.05, 0.08, (0.4, 0.0, 0.04), mat("pot", "#c0703e", 0.7), 12, 0.008)
    sphere("pot_herb", 0.06, (0.4, 0.0, 0.11), leaf, (1, 1, 1), 2)


def _cart(x, y, rz, load=True):
    before = set(bpy.context.scene.objects)
    wd = mat("cart_w", "#a0713f", 0.7)
    dk = mat("cart_d", "#5e3d22", 0.7)
    box("bed", (0.36, 0.22, 0.04), (0, 0, 0.13), wd, 0.008)
    for sy in (-1, 1):
        box("side", (0.36, 0.02, 0.07), (0, sy * 0.11, 0.17), wd, 0.005)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.1, minor_radius=0.016, location=(0, sy * 0.14, 0.1),
                                         major_segments=20, minor_segments=6)
        w = bpy.context.active_object
        w.rotation_euler.x = math.pi / 2
        w.data.materials.append(dk)
        for k in range(3):
            sp = box("spoke", (0.012, 0.012, 0.19), (0, sy * 0.14, 0.1), wd, 0.0)
            sp.rotation_euler.y = k * math.pi / 3
    for sy in (-1, 1):
        s = cyl("shaft", 0.012, 0.3, (-0.3, sy * 0.07, 0.11), dk, 6, 0.0)
        s.rotation_euler.y = math.pi / 2 + 0.25
    if load:
        for (lx, ly, lz) in ((-0.08, 0.0, 0.0), (0.08, 0.0, 0.0), (0.0, 0.0, 0.1)):
            sphere("load", 0.075, (lx, ly, 0.22 + lz * 0.7), mat("sack_b", "#dcbb7c", 0.9), (1.1, 1.0, 0.8), 2)
    e = bpy.data.objects.new("cart", None)
    bpy.context.scene.collection.objects.link(e)
    for o in list(bpy.context.scene.objects):
        if o not in before and o is not e and o.parent is None:
            o.parent = e
    e.location = (x, y, 0)
    e.rotation_euler.z = rz


def _convoy_yard():
    """A wagon yard: an open shed on posts, two loaded carts and a fence."""
    roof = mat("roof" + ROOF, ROOF, 0.6)
    wd = mat("post_w", BEAM, 0.8)
    for (x, y) in ((-0.32, 0.05), (0.32, 0.05), (-0.32, 0.38), (0.32, 0.38)):
        cyl("post", 0.025, 0.36, (x, y, 0.18), wd, 8, 0.004)
    kit.prism_roof("shed_roof", 0.72, 0.42, 0.18, (0, 0.215, 0.36), roof, overhang=0.05)
    _cart(-0.12, 0.2, 0.15)
    _cart(0.2, -0.3, -0.5)
    for k in range(5):
        cyl("fence", 0.018, 0.16, (-0.55 + k * 0.1, -0.35 + k * 0.02, 0.08), wd, 6, 0.0)
    rail = box("rail", (0.44, 0.02, 0.02), (-0.35, -0.31, 0.12), wd, 0.0)
    rail.rotation_euler.z = 0.2
    _sack(0.45, 0.0)
    _crate(0.42, 0.18, 0.0, 0.13, 0.4)


def _stall(x, y, rz, goods):
    before = set(bpy.context.scene.objects)
    wd = mat("stall_w", "#a0713f", 0.7)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cyl("post", 0.014, 0.3, (sx * 0.15, sy * 0.1, 0.15), wd, 6, 0.0)
    box("counter", (0.34, 0.22, 0.11), (0, -0.0, 0.055), wd, 0.008)
    for k, c in enumerate(("#3f86f0", "#f3efe6", "#3f86f0", "#f3efe6", "#3f86f0")):
        a = box("awn", (0.074, 0.3, 0.015), (-0.148 + k * 0.074, -0.02, 0.33), mat("awn" + c, c, 0.6), 0.003)
        a.rotation_euler.x = -0.3
    for k, c in enumerate(goods):
        sphere("goods", 0.04, (-0.1 + k * 0.1, -0.04, 0.14), mat("goods" + c, c, 0.6), (1, 1, 0.85), 2)
    e = bpy.data.objects.new("stall", None)
    bpy.context.scene.collection.objects.link(e)
    for o in list(bpy.context.scene.objects):
        if o not in before and o is not e and o.parent is None:
            o.parent = e
    e.location = (x, y, 0)
    e.rotation_euler.z = rz


def _market():
    """A market square: three striped stalls with fruit, bread and cloth, crates and a barrel between them."""
    _stall(-0.3, 0.15, 0.25, ("#d8452f", "#e8b84a", "#6faa3c"))
    _stall(0.24, 0.24, -0.2, ("#e8b84a", "#c97a3a", "#e8b84a"))
    _stall(0.02, -0.26, 0.05, ("#6faa3c", "#d8452f", "#3f86f0"))
    _crate(-0.46, -0.24, 0.0, 0.12, 0.3)
    _barrel_prop(0.42, -0.2)
    _sack(-0.34, -0.36, 0.9)


def _embassy():
    """An embassy: a stately white hall with columns under a pediment, two flags of friendly realms in front."""
    w, d, h = 0.6, 0.36, 0.3
    box("hall", (w, d, h), (0, 0.08, h / 2 + 0.05), mat("wall" + PLASTER, PLASTER, 0.85), 0.015)
    box("step", (w + 0.12, d + 0.16, 0.05), (0, 0.02, 0.025), mat("wall" + STONE_C, STONE_C, 0.85), 0.01)
    box("cornice", (w + 0.06, d + 0.06, 0.04), (0, 0.06, h + 0.07), mat("wall" + STONE_C, STONE_C, 0.85), 0.008)
    kit.prism_roof("roof", w + 0.04, d + 0.04, 0.16, (0, 0.06, h + 0.09), mat("roof" + ROOF, ROOF, 0.6), overhang=0.02)
    for k in range(4):
        cyl("column", 0.03, h, (-0.22 + k * 0.147, -0.13, h / 2 + 0.05), mat("column", "#f6f1e6", 0.6), 12, 0.006)
    _door(0.0, -0.105, 0.05, 0.1, 0.16)
    box("crest", (0.1, 0.02, 0.07), (0, -0.115, h + 0.15), mat("gold_b", "#e6b13e", 0.3, 0.6), 0.005)
    _flag(-0.42, -0.25, 0.48, BLUE)
    _flag(0.36, -0.25, 0.48, "#4cb050")
    _bush(-0.5, 0.15, 0.8)
    _bush(0.5, 0.18, 0.8)


# Closer framing where a tall thin flag or a wide yard would leave the building itself small (the flag tip may crop).
BUILDING_ZOOM = {"barracks": 1.35, "mine": 1.25, "residence": 1.2, "military_base": 1.15, "farm": 1.15, "port": 1.08}
BUILDING_SCENES = {"academy": _academy, "warehouse": _warehouse, "infirmary": _infirmary,
                   "convoy_yard": _convoy_yard, "market": _market, "embassy": _embassy}
BUILDINGS = ["residence", "barracks", "academy", "warehouse", "infirmary", "convoy_yard", "market", "embassy",
             "quarters", "farm", "mine", "port", "military_base"]


def building(kind):
    """The card picture of a building: its DL1 map model (or, for the capital's own buildings that have no map
    model, a small scene in the same kit) on a grass plot, from three-quarters above."""
    def scene():
        if kind in BUILDING_MODELS:
            for name, (x, y), rz, s in BUILDING_MODELS[kind]:
                load(name, (x, y, 0), rz, s)
        else:
            BUILDING_SCENES[kind]()
        bpy.ops.mesh.primitive_plane_add(size=8, location=(0, 0, 0))
        catcher = bpy.context.active_object
        catcher.name = "shadow_catcher"
        catcher.is_shadow_catcher = True
        bpy.ops.object.light_add(type="SUN")
        s = bpy.context.active_object
        s.data.energy = 3.6
        s.data.color = kit.srgb("#fff1da")
        s.data.angle = math.radians(12)  # soft shadows
        s.rotation_euler = (math.radians(50), math.radians(-12), math.radians(-38))
        bpy.ops.object.light_add(type="AREA", location=(0.6, -3.0, 2.4))
        f = bpy.context.active_object
        f.data.energy = 160
        f.data.size = 4.0
        f.rotation_euler = (math.radians(52), 0, math.radians(10))
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        bpy.context.scene.collection.objects.link(cam)
        cam.data.type = "ORTHO"
        el, az = math.radians(34), math.radians(-18)
        dist = 12
        cam.location = (dist * math.cos(el) * math.sin(az), -dist * math.cos(el) * math.cos(az), dist * math.sin(el))
        cam.rotation_euler = (math.pi / 2 - el, 0, az)
        bpy.context.scene.camera = cam
    return scene


def _fit_building(cam, w, h, zoom=1.0):
    """Ortho scale and shift: the model fills ≤ 88 % of the width and ≤ 76 % of the height, centred across, its
    base 15 % above the card's bottom edge (the tray card shows the art cropped to 180 × 104, about 8 % off the top
    and the bottom, with the name on a shade over the bottom). Returns the ground radius for the grass disc."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    inv = cam.matrix_world.inverted()
    lo, hi = [1e9, 1e9], [-1e9, -1e9]
    foot = 0.0
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or o.name.startswith("shadow_catcher"):
            continue
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        mw = eo.matrix_world
        for v in me.vertices:
            wv = mw @ v.co
            if wv.z < 0.05:
                foot = max(foot, math.hypot(wv.x, wv.y))
            p = inv @ wv
            lo[0], lo[1] = min(lo[0], p.x), min(lo[1], p.y)
            hi[0], hi[1] = max(hi[0], p.x), max(hi[1], p.y)
        eo.to_mesh_clear()
    aspect = w / h
    s = max((hi[0] - lo[0]) / 0.88, aspect * (hi[1] - lo[1]) / 0.76) / zoom
    frame_h = s / aspect
    cam.data.ortho_scale = s
    cam.data.shift_x = (lo[0] + hi[0]) / 2 / s
    cam.data.shift_y = (lo[1] + (0.5 - 0.15) * frame_h) / s
    return foot


def render_building(path, kind):
    """Render the model on a transparent film (with its caught shadow) at 2×, then paint the backdrop in Pillow."""
    from PIL import Image, ImageDraw
    from bpy_extras.object_utils import world_to_camera_view
    sc = bpy.context.scene
    cam = sc.camera
    ss = 2
    foot = _fit_building(cam, BW, BH, BUILDING_ZOOM.get(kind, 1.0))
    sc.render.film_transparent = True
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    sc.render.resolution_x = BW * ss
    sc.render.resolution_y = BH * ss
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    wd = bpy.data.worlds.new("w")
    sc.world = wd
    wd.use_nodes = True
    wd.node_tree.nodes["Background"].inputs["Color"].default_value = (*kit.srgb("#b9dcf5"), 1)
    wd.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7
    raw = path[:-4] + "_raw.png"
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    # the grass plot: the ground circle under the model, projected; a darker copy below it is the plot's lip
    r = max(0.55, foot * 1.12)
    pts = []
    for k in range(72):
        a = k * math.tau / 72
        p = world_to_camera_view(sc, cam, Vector((math.cos(a) * r, math.sin(a) * r, 0.0)))
        pts.append((p.x * BW * ss, (1 - p.y) * BH * ss))
    bg = Image.new("RGBA", (BW * ss, BH * ss))
    top, low = kit_rgb(SKY_TOP), kit_rgb(SKY_LOW)
    d = ImageDraw.Draw(bg)
    for yy in range(BH * ss):
        t = yy / (BH * ss - 1)
        d.line([(0, yy), (BW * ss, yy)], fill=tuple(round(top[i] + (low[i] - top[i]) * t) for i in range(3)) + (255,))
    lip = 7 * ss
    d.polygon([(x, y + lip) for (x, y) in pts], fill=kit_rgb(GRASS_LIP) + (255,))
    d.polygon(pts, fill=kit_rgb(GRASS) + (255,))
    model = Image.open(raw).convert("RGBA")
    bg.alpha_composite(model)
    bg.convert("RGBa").resize((BW, BH), Image.LANCZOS).convert("RGB").save(path)
    os.remove(raw)


def kit_rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


SCENES = {"attack": attack, "breakthrough": breakthrough, "airstrike": airstrike, "encircle": encircle, "defense": defense,
          "landing": landing, "missile": missile, "corps": corps}
for _n in range(1, 9):
    SCENES["unit_dl%d" % _n] = unit(_n)
for _k in TILE_MODELS:
    SCENES["tile_" + _k] = tile(_k)
for _b in BUILDINGS:
    SCENES["bld_" + _b] = building(_b)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "game/assets/ui/cards"
    os.makedirs(out, exist_ok=True)
    for name in (args[1:] or list(SCENES)):
        reset()
        SCENES[name]()
        if name.startswith("tile_"):
            render(os.path.join(os.path.abspath(out), name + ".png"), 160, 140, True)
        elif name.startswith("bld_"):
            render_building(os.path.join(os.path.abspath(out), name + ".png"), name[4:])
        else:
            render(os.path.join(os.path.abspath(out), name + ".png"), world=STAGE_WORLD if name in BATTLE else None)
        print("CARD", name, flush=True)
