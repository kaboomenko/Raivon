"""Key art for the splash/loading screen and store: the residence evolving DL1 → DL8 along a diagonal of
hex tiles (huts in front, neon citadel at the back), troops of matching eras beside them.

Run: python3 tools/blender/render_keyart.py OUT.png [width height samples]
Uses the exported models in game/assets/models (run evolution_assets.py / troops_assets.py first).
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import hex_prism, mat, noisy_mat  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/keyart.png"
W = int(sys.argv[2]) if len(sys.argv) > 2 else 941
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1672
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 64
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "models")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

grass = noisy_mat("grass", "#58b82a", "#8ad83f", 4.0)
grass_red = noisy_mat("grass_red", "#b5a43a", "#d4b24e", 4.0)
dirt = noisy_mat("dirt", "#8a5a34", "#a8743f", 6.0)
neon_blue = mat("neon_b", "#2f7dff", 0.4)
neon_red = mat("neon_r", "#ff3a2a", 0.4)
for m, col in ((neon_blue, (0.2, 0.5, 1.0, 1)), (neon_red, (1.0, 0.2, 0.12, 1))):
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Emission Color"].default_value = col
    bsdf.inputs["Emission Strength"].default_value = 2.2


def hex_xy(q, r):
    return 1.5 * q, -math.sqrt(3) * (r + q / 2)


def place(name, x, y, rz=0.0, s=1.0):
    path = os.path.join(MODELS, name + ".glb")
    if not os.path.exists(path):
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in set(bpy.data.objects) - before:
        if o.parent is None:
            o.location = (x + o.location.x, y + o.location.y, o.location.z)
            o.rotation_euler = (o.rotation_euler.x, o.rotation_euler.y, o.rotation_euler.z + rz)
            o.scale = (s, s, s)


# tiles: a diagonal path of 8 era hexes from the front (bottom of frame) to the back, wild hexes around
path = [(-2, 3), (-1, 2), (-1, 1), (0, 0), (0, -1), (1, -2), (1, -3), (2, -4)]
era = {c: len(path) - i for i, c in enumerate(path)}  # huts nearest the camera, citadel at the back
for q in range(-5, 6):
    for r in range(-7, 7):
        x, y = hex_xy(q, r)
        if abs(x) > 6.5 or y < -5.5 or y > 9:
            continue
        own = (q, r) in era
        enemy = q >= 2 and (q, r) not in era
        hex_prism(f"h{q}_{r}", (x, y, 0), 0.985, 0.95, grass_red if enemy else grass, dirt, bevel=0.035)
        if own:  # neon border ring on the era hexes
            kit.palisade  # (keep kit imported for its materials)
            bpy.ops.mesh.primitive_torus_add(major_radius=0.9, minor_radius=0.025, major_segments=6, minor_segments=4,
                                             location=(x, y, 0.37), rotation=(0, 0, math.pi / 6))
            bpy.context.active_object.data.materials.append(neon_blue)

for (q, r), dl in era.items():
    x, y = hex_xy(q, r)
    place(f"residence_dl{dl}_blue", x, y + 0.08, rz=0.25, s=1.45 if dl <= 3 else 1.15)
    side = -1 if dl % 2 else 1
    if dl >= 2:
        place(f"assault_dl{dl}_blue", x + 0.95 * side, y - 0.55, rz=0.4 * side, s=1.3)
    place(f"squad_dl{dl}_blue", x - 0.9 * side, y - 0.75, rz=-0.2 * side, s=1.2)

# a red rival city at the back right for contrast
place("city_dl5_red", 4.2, -3.2, rz=0.3, s=1.2)
place("residence_dl6_red", 4.6, -5.0, rz=0.2)

# sea far below, sky
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.6))
bpy.context.active_object.data.materials.append(mat("sea", "#1b7fb8", 0.2))
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.55, 0.75, 1.0, 1)
bg.inputs["Strength"].default_value = 0.9

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 4.0
sun.angle = math.radians(8)
so = bpy.data.objects.new("sun", sun)
so.rotation_euler = (math.radians(48), math.radians(-20), math.radians(35))
scene.collection.objects.link(so)

cam = bpy.data.cameras.new("cam")
cam.lens = 38
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
scene.camera = co
co.location = (4.5, 12.5, 8.0)
target = bpy.data.objects.new("t", None)
target.location = (0.5, 0.4, 0.9)
scene.collection.objects.link(target)
tc = co.constraints.new("TRACK_TO")
tc.target = target
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"

scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = W
scene.render.resolution_y = H
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
scene.view_settings.look = "AgX - Punchy" if scene.view_settings.view_transform == "AgX" else "None"
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("keyart ->", OUT)
