"""Raivon procedural art kit for Blender (bpy). Chunky, bevelled, saturated — Clash-of-Clans-like.

All models are built from code so every asset is reproducible from the repository
(owner decision 10). Units: 1 hex = radius 1.0 (flat-top), Z up.
"""
import math
import random

import bpy
from mathutils import Vector

SQ3 = math.sqrt(3)

# ---------------------------------------------------------------- materials

_MATS = {}


def mat(name, color, rough=0.6, metal=0.0, emission=None, emit_strength=0.0):
    key = (name, color, rough, metal)
    if key in _MATS:
        return _MATS[key]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*srgb(color), 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*srgb(emission), 1)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    _MATS[key] = m
    return m


def noisy_mat(name, c1, c2, scale=6.0, rough=0.7):
    """Two-colour noise material (grass, stone) for a hand-painted feel."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[0].color = (*srgb(c1), 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (*srgb(c2), 1)
    nt.links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    return m


def srgb(hex_color):
    if isinstance(hex_color, tuple):
        return hex_color
    h = hex_color.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ---------------------------------------------------------------- primitives


def _finish(obj, material, bevel=0.0, segments=3, smooth=True):
    if material:
        obj.data.materials.append(material)
    if bevel > 0:
        b = obj.modifiers.new("bevel", "BEVEL")
        b.width = bevel
        b.segments = segments
        b.limit_method = "ANGLE"
    if smooth:
        for p in obj.data.polygons:
            p.use_smooth = True
        if bevel > 0:
            obj.modifiers.new("wn", "WEIGHTED_NORMAL")
    return obj


def box(name, size, loc, material, bevel=0.04, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material, bevel)


def cyl(name, r, h, loc, material, verts=16, bevel=0.03, r2=None):
    if r2 is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=h, location=loc)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=r2, depth=h, location=loc)
    o = bpy.context.active_object
    o.name = name
    return _finish(o, material, bevel)


def cone(name, r, h, loc, material, verts=16, bevel=0.02):
    bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=0, depth=h, location=loc)
    o = bpy.context.active_object
    o.name = name
    return _finish(o, material, bevel)


def sphere(name, r, loc, material, scale=(1, 1, 1), subdiv=3):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=r, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish(o, material, 0)


def prism_roof(name, w, d, h, loc, material, overhang=0.08, rot_z=0.0):
    """Gable roof: triangular prism with its ridge along local X, base at loc.z."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=1.0, depth=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.name = name
    # triangle in local XY with apex at +X → rotate so the axis is X and the apex points up
    o.rotation_euler = (0, math.pi / 2, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    o.rotation_euler = (math.pi / 2, 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    # now: ridge along X, triangle in YZ. Normalise to width d, height h, length w.
    bb = [v.co.copy() for v in o.data.vertices]
    miny = min(v.y for v in bb); maxy = max(v.y for v in bb)
    minz = min(v.z for v in bb); maxz = max(v.z for v in bb)
    for v in o.data.vertices:
        v.co.x = v.co.x * (w + 2 * overhang)
        v.co.y = (v.co.y - (miny + maxy) / 2) / (maxy - miny) * (d + 2 * overhang)
        v.co.z = (v.co.z - minz) / (maxz - minz) * h
    o.location = loc
    o.rotation_euler = (0, 0, rot_z)
    return _finish(o, material, 0.025, 2, smooth=False)


def hex_prism(name, center, radius, height, top_mat, side_mat, bevel=0.06):
    """Flat-top hex tile: grassy top, earthy sides."""
    verts = []
    for z in (0.0, height):
        for k in range(6):
            a = math.pi / 3 * k
            verts.append((center[0] + radius * math.cos(a), center[1] + radius * math.sin(a), center[2] - height + z))
    faces = [tuple(range(6, 12)), tuple(reversed(range(6)))]
    for k in range(6):
        n = (k + 1) % 6
        faces.append((k, n, n + 6, k + 6))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(top_mat)
    o.data.materials.append(side_mat)
    o.data.polygons[0].material_index = 0
    for p in o.data.polygons[1:]:
        p.material_index = 1
    b = o.modifiers.new("bevel", "BEVEL")
    b.width = bevel
    b.segments = 3
    return o


def axial_to_xy(q, r, R=1.0):
    """Flat-top axial → world XY (Y up the screen = −r)."""
    return 1.5 * R * q, -SQ3 * R * (r + q / 2)


# ---------------------------------------------------------------- props


def tree(loc, s=1.0, seed=0):
    rnd = random.Random(seed)
    x, y, z = loc
    trunk = mat("trunk", "#7a4a2a", 0.8)
    leaf = noisy_mat(f"leaf{seed % 3}", "#2f8f2f", "#58c43e", 8.0)
    cyl("trunk", 0.06 * s, 0.3 * s, (x, y, z + 0.15 * s), trunk, 8, 0.01)
    for i, (r, h) in enumerate([(0.32, 0.38), (0.25, 0.62), (0.16, 0.82)]):
        sphere("leaf", r * s, (x + rnd.uniform(-0.03, 0.03), y, z + h * s), leaf, (1, 1, 0.85), 2)


def pine(loc, s=1.0):
    x, y, z = loc
    trunk = mat("trunk", "#6b4226", 0.8)
    green = mat("pine", "#2e7d32", 0.7)
    cyl("trunk", 0.05 * s, 0.2 * s, (x, y, z + 0.1 * s), trunk, 8, 0.01)
    for i in range(3):
        cone("pine", (0.32 - i * 0.08) * s, 0.36 * s, (x, y, z + (0.32 + i * 0.2) * s), green, 10, 0.03)


def rock(loc, s=1.0):
    stone = noisy_mat("rock", "#8d8d8d", "#b9b9b9", 5)
    o = sphere("rock", 0.18 * s, loc, stone, (1.2, 1.0, 0.7), 1)
    return o


def house(loc, rot=0.0, wall="#f2e2c4", roof="#d64a3a", s=1.0):
    x, y, z = loc
    w, d, h = 0.55 * s, 0.42 * s, 0.34 * s
    o1 = box("house_wall", (w, d, h), (x, y, z + h / 2), mat("wall", wall, 0.8), 0.03)
    o1.rotation_euler.z = rot
    bpy.context.view_layer.update()
    o2 = prism_roof("house_roof", w, d, 0.32 * s, (x, y, z + h), mat("roof", roof, 0.5), rot_z=rot)
    door = box("door", (0.12 * s, 0.02, 0.18 * s), (x, y - d / 2 - 0.005, z + 0.09 * s), mat("door", "#6b3e1f", 0.7), 0.01)
    door.rotation_euler.z = rot
    if rot:
        # rotate door around house centre
        dv = Vector((0, -d / 2 - 0.005, 0))
        dv.rotate(o1.rotation_euler)
        door.location = (x + dv.x, y + dv.y, z + 0.09 * s)
    cyl("chimney", 0.04 * s, 0.2 * s, (x + w * 0.25, y + 0.05, z + h + 0.25 * s), mat("stone", "#9e9e9e", 0.8), 8, 0.01)
    return o1


def flag(loc, color, h=0.7):
    x, y, z = loc
    cyl("pole", 0.015, h, (x, y, z + h / 2), mat("pole", "#e8e0d0", 0.5), 8, 0.005)
    me = bpy.data.meshes.new("banner")
    verts = [(0, 0, 0), (0.28, 0.02, -0.05), (0.26, 0.0, -0.18), (0, 0, -0.2)]
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    o = bpy.data.objects.new("banner", me)
    bpy.context.collection.objects.link(o)
    o.location = (x, y, z + h)
    o.data.materials.append(mat("banner" + color, color, 0.6))
    s = o.modifiers.new("solid", "SOLIDIFY")
    s.thickness = 0.015
    sphere("finial", 0.03, (x, y, z + h + 0.02), mat("gold", "#ffcc33", 0.3, 0.6), (1, 1, 1), 2)
    return o


def palisade(p0, p1, z, color="#a0703e"):
    """Wooden stake fence (DL1–2 fortification) between two points."""
    wood = mat("stake", color, 0.85)
    tip = mat("stake_tip", "#c89a63", 0.8)
    v0, v1 = Vector((p0[0], p0[1], z)), Vector((p1[0], p1[1], z))
    n = max(2, int((v1 - v0).length / 0.11))
    for i in range(n + 1):
        p = v0.lerp(v1, i / n)
        h = 0.26 + (0.03 if i % 2 else 0)
        cyl("stake", 0.045, h, (p.x, p.y, z + h / 2), wood, 8, 0.01)
        cone("stake_tip", 0.045, 0.08, (p.x, p.y, z + h + 0.04), tip, 8, 0.0)
    # cross beam
    mid = (v0 + v1) / 2
    beam = box("beam", ((v1 - v0).length, 0.04, 0.04), (mid.x, mid.y, z + 0.15), wood, 0.01)
    beam.rotation_euler.z = math.atan2(v1.y - v0.y, v1.x - v0.x)
