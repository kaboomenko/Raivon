"""App icon: the blue castle on a glowing hex. Run: python3 tools/blender/render_icon.py OUT.png [size]"""
import math
import sys
import os

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402

OUT = sys.argv[1]
SIZE = int(sys.argv[2]) if len(sys.argv) > 2 else 512
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(os.path.dirname(__file__), "../../game/assets/models/castle.glb"))
grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
kit.hex_prism("tile", (0, 0, 0), 1.0, 0.35, grass, dirt, 0.05)
glow = kit.mat("glow", "#3b8bff", 0.3, emission="#5aa0ff", emit_strength=6.0)
for k in range(6):
    a0, a1 = math.pi / 3 * k, math.pi / 3 * (k + 1)
    p0 = (math.cos(a0) * 0.97, math.sin(a0) * 0.97)
    p1 = (math.cos(a1) * 0.97, math.sin(a1) * 0.97)
    o = kit.box("edge", (math.dist(p0, p1) + 0.05, 0.06, 0.05), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, 0.02), glow, 0.01)
    o.rotation_euler.z = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
world = bpy.data.worlds.new("w")
bpy.context.scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (*kit.srgb("#123a8c"), 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
bpy.ops.object.light_add(type="SUN")
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(45), math.radians(-15), math.radians(-40))
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
bpy.context.scene.collection.objects.link(cam)
cam.data.type = "ORTHO"
cam.data.ortho_scale = 2.6
cam.location = (0, -6, 5.2)
cam.rotation_euler = (math.radians(49), 0, 0)
bpy.context.scene.camera = cam
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.render.resolution_x = SIZE
sc.render.resolution_y = SIZE
sc.view_settings.view_transform = "AgX"
sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
