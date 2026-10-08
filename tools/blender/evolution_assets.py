"""Visual evolution of a state by development level (canon §6.1): «халупа → небоскрёб», «плетень → ультразабор».

Builds and exports to OUT (default game/assets/models):
  city_dl{1..8}_{blue,red,green}.glb       one cluster per city hex (replaces the 4 loose houses)
  residence_dl{1..8}_{blue,red,green}.glb  the capital's Residence, designed for scale 1.0
  fort_l{1..8}.glb                         team-neutral fortification ring along the hex edge
  fort_l{1..8}_edge.glb / _post.glb        the same fortification split into one edge / one corner,
                                           for drawing only the edges that face foreign land (canon §7)

Run:   python3 tools/blender/evolution_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/evolution_assets.py game/assets/models --sheet OUT.png [--team blue]

Conventions (same as export_assets.py): Z up, base on Z=0, origin = hex centre, 1 hex = flat-top
hexagon of circumradius 1.0, the "front" of a model faces −Y (Godot +Z, towards the camera).
Everything is joined and its procedural colours are baked into one 512 px texture; emissive materials
(windows, neon, energy mesh, fire) stay separate so they keep glowing in Godot.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
from kit import mat, prism_roof  # noqa: E402

TEAMS = {"blue": "#2673ff", "red": "#e6261a", "green": "#40a64d"}  # Color(0.15,0.45,1) / (0.9,0.15,0.1) / (0.25,0.65,0.3)

WOOD = "#7d5130"
WOOD_L = "#a8743f"
WOOD_D = "#5a3a22"
LOG = "#a06c3c"
THATCH = "#d8b25c"
DAUB = "#c7a77a"
STONE = "#bdbab2"  # light grey stone (reference frames), was beige #cbc3b4
STONE_D = "#86837c"
COBBLE = "#a8a091"
DIRT = "#9c7a52"
PLASTER = "#e9dcc0"
BRICK = "#a9493a"
CONC = "#c2beb5"
CONC_D = "#8b877f"
ASPH = "#62646a"
GLASS = "#7cc3e8"
WIN_D = "#2f3a4a"
GOLD = "#ffc933"
WHITE = "#f3efe6"
LEAF = "#4f8f37"
LEAF2 = "#3f7d2e"
SLATE = "#5b6470"
CYAN = "#14d2ff"


def shade(c, k):
    """Darken (k<1) or lighten towards white (k>1) an sRGB hex colour."""
    h = c.lstrip("#")
    v = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    v = [x * k if k <= 1 else x + (255 - x) * (k - 1) for x in v]
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, round(x)))) for x in v)


def slate(team, k=1.0):
    """Roof tone of a team (the reference frames: deep slate-blue tiles, not the bright team colour)."""
    base = {TEAMS["blue"]: "#34548f", TEAMS["red"]: "#8f3a30", TEAMS["green"]: "#3d6b3c"}.get(team, shade(team, 0.7))
    return shade(base, k)


# ------------------------------------------------------------------ materials


def tex(kind, color, scale=1.0):
    return kit.textured(kind, color, scale)


def flat(name, color, rough=0.75):
    return mat(name, color, rough, 0.0)


def stone(color, scale=1.0):
    """Stone blocks laid in world space (rows stay horizontal on walls at any angle)."""
    return facade(color, color, wf=0.0, brick=True, brick_scale=11.0 * scale, mortar_k=0.72)


def glow(name, color, strength=3.0):
    return mat("glow_" + name, color, 0.4, 0.0, emission=color, emit_strength=strength)


def win_lit():
    return mat("win_lit", "#ffcf6b", 0.5, emission="#ffb84a", emit_strength=1.5)


def _sock(node, ident, out=False):
    return next(s for s in (node.outputs if out else node.inputs) if s.identifier == ident)


def facade(wall, win, col=0.07, floor=0.1, wf=0.5, hf=0.55, lit="#ffd27a", lit_p=0.22, brick=False, z0=0.0,
           brick_scale=30.0, mortar_k=1.35):
    """Wall with a grid of windows on every vertical face (world-space, so floors line up with Z=0).

    Baked into the texture like every procedural material: cheap windows without extra geometry.
    """
    key = ("facade", wall, win, col, floor, wf, hf, lit, lit_p, brick, z0, brick_scale, mortar_k)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("facade")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    L = nt.links

    def mth(op, a, b=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]

    def mix(fac, a, b):
        n = nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        L.new(fac, _sock(n, "Factor_Float"))
        for ident, v in (("A_Color", a), ("B_Color", b)):
            if isinstance(v, str):
                _sock(n, ident).default_value = (*kit.srgb(v), 1)
            else:
                L.new(v, _sock(n, ident))
        return _sock(n, "Result_Color", True)

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    sn = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], sn.inputs[0])
    u = mth("ADD", sp.outputs[0], sp.outputs[1])
    v = mth("SUBTRACT", sp.outputs[2], z0)
    du, dv = mth("DIVIDE", u, col), mth("DIVIDE", v, floor)
    fu, fv = mth("FRACT", du), mth("FRACT", dv)

    def band(f, frac):
        return mth("MULTIPLY", mth("GREATER_THAN", f, (1 - frac) / 2), mth("LESS_THAN", f, (1 + frac) / 2))

    vert = mth("LESS_THAN", mth("ABSOLUTE", sn.outputs[2]), 0.5)
    mask = mth("MULTIPLY", mth("MULTIPLY", band(fu, wf), band(fv, hf)), vert)
    cell = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(mth("FLOOR", du), cell.inputs[0])
    L.new(mth("FLOOR", dv), cell.inputs[1])
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    L.new(cell.outputs[0], wn.inputs["Vector"])
    litm = mth("GREATER_THAN", wn.outputs["Value"], 1 - lit_p)
    wincol = mix(litm, win, lit)
    if brick:
        co = nt.nodes.new("ShaderNodeCombineXYZ")
        hor = mth("SUBTRACT", 1.0, vert)
        L.new(mth("ADD", mth("MULTIPLY", u, vert), mth("MULTIPLY", sp.outputs[0], hor)), co.inputs[0])
        L.new(mth("ADD", mth("MULTIPLY", v, vert), mth("MULTIPLY", sp.outputs[1], hor)), co.inputs[1])
        br = nt.nodes.new("ShaderNodeTexBrick")
        L.new(co.outputs[0], br.inputs["Vector"])
        br.inputs["Color1"].default_value = (*kit.srgb(wall), 1)
        br.inputs["Color2"].default_value = (*kit.srgb(shade(wall, 0.82)), 1)
        br.inputs["Mortar"].default_value = (*kit.srgb(shade(wall, mortar_k)), 1)
        br.inputs["Scale"].default_value = brick_scale
        br.inputs["Mortar Size"].default_value = 0.03
        wallc = br.outputs["Color"]
    else:
        nz = nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 9.0
        L.new(geo.outputs["Position"], nz.inputs["Vector"])
        wallc = mix(nz.outputs["Fac"], shade(wall, 0.86), wall)
    L.new(mix(mask, wallc, wincol), bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    kit._MATS[key] = m
    return m


# ------------------------------------------------------------------ primitives


def bx(size, loc, mt, rz=0.0, bev=0.012, rot=None):
    o = kit.box("b", size, loc, mt, bev)
    if rot:
        o.rotation_euler = rot
    elif rz:
        o.rotation_euler.z = rz
    return o


def cy(r, h, loc, mt, n=8, bev=0.0, r2=None, rot=None):
    o = kit.cyl("c", r, h, loc, mt, n, bev, r2)
    if rot:
        o.rotation_euler = rot
    return o


def cn(r, h, loc, mt, n=8, rot=None):
    o = kit.cone("k", r, h, loc, mt, n, 0.0)
    if rot:
        o.rotation_euler = rot
    return o


def ico(r, loc, mt, scale=(1, 1, 1), sub=1):
    return kit.sphere("s", r, loc, mt, scale, sub)


def uvs(r, loc, mt, seg=10, rings=6, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=r, location=loc)
    o = bpy.context.active_object
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return kit._finish(o, mt, 0)


def torus(R, r, loc, mt, rot=(0, 0, 0), seg=8, mseg=3):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=r, major_segments=seg, minor_segments=mseg,
                                     location=loc, rotation=rot)
    o = bpy.context.active_object
    return kit._finish(o, mt, 0)


def mesh_obj(verts, faces, mt, loc=(0, 0, 0), rot=(0, 0, 0)):
    me = bpy.data.meshes.new("m")
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("m", me)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = rot
    o.data.materials.append(mt)
    return o


def extrude(pts, z0, z1, mt, loc=(0, 0, 0), rot=(0, 0, 0)):
    """Prism from a 2D polygon (any winding)."""
    n = len(pts)
    verts = [(x, y, z0) for x, y in pts] + [(x, y, z1) for x, y in pts]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    return mesh_obj(verts, faces, mt, loc, rot)


def ngon(r, n, rot=0.0, sx=1.0, sy=1.0, jitter=0.0, seed=0):
    rnd = random.Random(seed)
    return [(sx * r * (1 + rnd.uniform(-jitter, jitter)) * math.cos(rot + math.tau * k / n),
             sy * r * (1 + rnd.uniform(-jitter, jitter)) * math.sin(rot + math.tau * k / n)) for k in range(n)]


def pad(r, mt, h=0.02, n=14, jitter=0.0, seed=0, sx=1.0, sy=1.0):
    """Ground plate under a cluster (round-ish, so any rotation of the model on the hex looks right)."""
    return extrude(ngon(r, n, 0.1, sx, sy, jitter, seed), -0.01, h, mt)


ROOF_TRIM = "#3e2f25"  # ridge caps and eave boards: dark lines that keep a small roof readable at game size


def _rt(p, loc, rz):
    """Local roof point -> world (rotated by rz about Z, then moved to loc)."""
    c, s_ = math.cos(rz), math.sin(rz)
    return (loc[0] + p[0] * c - p[1] * s_, loc[1] + p[0] * s_ + p[1] * c, loc[2] + p[2])


def _trim_lines(lines, loc, rz, t):
    tm = flat("roof_trim", ROOF_TRIM, 0.8)
    for p0, p1 in lines:
        beam(_rt(p0, loc, rz), _rt(p1, loc, rz), t, tm)


def prism_roof(name, w, d, h, loc, material, overhang=0.08, rot_z=0.0):
    """Gable roof (kit.prism_roof) with a ridge cap and eave boards."""
    o = kit.prism_roof(name, w, d, h, loc, material, overhang, rot_z)
    L, D = w / 2 + overhang, d / 2 + overhang
    t = max(0.008, 0.05 * min(w, d))
    _trim_lines([((-L, 0, h + t * 0.2), (L, 0, h + t * 0.2)),
                 ((-L, -D, t * 0.3), (L, -D, t * 0.3)), ((-L, D, t * 0.3), (L, D, t * 0.3))], loc, rot_z, t)
    return o


def hip_roof(w, d, h, loc, mt, oh=0.03, rz=0.0):
    """Hip roof (or a pyramid / tent roof when w == d), base at loc.z; ridge, hip lines and eave boards."""
    o = _hip_roof(w, d, h, loc, mt, oh, rz)
    W, D = w / 2 + oh, d / 2 + oh
    rl = abs(w - d) / 2
    t = max(0.007, 0.045 * min(w, d))
    if rl < 1e-4:
        tops = [(0, 0, h)] * 4
        lines = []
    elif w > d:
        tops = [(-rl, 0, h), (rl, 0, h), (rl, 0, h), (-rl, 0, h)]
        lines = [((-rl, 0, h), (rl, 0, h))]
    else:
        tops = [(0, -rl, h), (0, -rl, h), (0, rl, h), (0, rl, h)]
        lines = [((0, -rl, h), (0, rl, h))]
    corners = [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0)]
    for i in range(4):
        lines.append((corners[i], tops[i]))  # hip ridges
        lines.append((corners[i], corners[(i + 1) % 4]))  # eaves
    _trim_lines(lines, loc, rz, t)
    return o


def _hip_roof(w, d, h, loc, mt, oh=0.03, rz=0.0):
    """Hip roof (or a pyramid / tent roof when w == d), base at loc.z."""
    W, D = w / 2 + oh, d / 2 + oh
    base = [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0)]
    rl = abs(w - d) / 2
    if rl < 1e-4:
        verts = base + [(0, 0, h)]
        faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)]
    elif w > d:
        verts = base + [(-rl, 0, h), (rl, 0, h)]
        faces = [(0, 1, 5, 4), (1, 2, 5), (2, 3, 4, 5), (3, 0, 4), (3, 2, 1, 0)]
    else:
        verts = base + [(0, -rl, h), (0, rl, h)]
        faces = [(0, 1, 4), (1, 2, 5, 4), (2, 3, 5), (3, 0, 4, 5), (3, 2, 1, 0)]
    return mesh_obj(verts, faces, mt, loc, (0, 0, rz))


def taper_box(size, loc, mt, top=(1.0, 1.0), rz=0.0, bev=0.0):
    o = bx(size, loc, mt, rz, bev)
    for v in o.data.vertices:
        if v.co.z > 0:
            v.co.x *= top[0]
            v.co.y *= top[1]
    return o


def rod(p0, p1, r, mt, r2=None, n=6):
    """Cylinder (or cone with r2) from 3D point p0 to p1."""
    from mathutils import Vector
    a, b = Vector(p0), Vector(p1)
    o = cy(r, (b - a).length, tuple((a + b) / 2), mt, n, 0.0, r2)
    o.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
    return o


def beam(p0, p1, t, mt, bev=0.0):
    """Box of thickness t from 3D point p0 to p1."""
    dx, dy, dz = (p1[i] - p0[i] for i in range(3))
    ln = math.sqrt(dx * dx + dy * dy + dz * dz)
    o = bx((ln, t, t), tuple((p0[i] + p1[i]) / 2 for i in range(3)), mt, 0, bev)
    o.rotation_euler = (0, -math.atan2(dz, math.hypot(dx, dy)), math.atan2(dy, dx))
    return o


def build_at(fn, x=0.0, y=0.0, rz=0.0, s=1.0, tilt=(0.0, 0.0), z=0.0):
    """Run a builder at the origin, then move everything it created (rotate rz, tilt, scale s)."""
    before = {o.name for o in bpy.context.scene.objects}
    res = fn()
    new = [o for o in bpy.context.scene.objects if o.name not in before]
    bpy.context.view_layer.update()
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rz, 4, "Z") @ Euler((tilt[0], tilt[1], 0)).to_matrix().to_4x4() @ Matrix.Scale(s, 4)
    for o in new:
        o.matrix_world = M @ o.matrix_world
    return res


# ------------------------------------------------------------------ small props


def tree(x, y, s=1.0, c=LEAF):
    cy(0.022 * s, 0.12 * s, (x, y, 0.06 * s), tex("wood", "#6a4327"), 6)
    ico(0.085 * s, (x, y, 0.17 * s), flat("leaf" + c, c, 0.8), (1, 1, 0.9))
    ico(0.06 * s, (x + 0.03 * s, y - 0.02 * s, 0.23 * s), flat("leaf" + shade(c, 1.15), shade(c, 1.15), 0.8), (1, 1, 0.9))


def pine(x, y, s=1.0):
    cy(0.018 * s, 0.08 * s, (x, y, 0.04 * s), tex("wood", "#6a4327"), 6)
    for i in range(3):
        cn((0.1 - i * 0.025) * s, 0.13 * s, (x, y, (0.12 + i * 0.07) * s), flat("pine", "#2a6233", 0.8), 7)


def flag_at(name, x, y, z, w, h, t=0.015):
    """Empty marking a flag cloth (centre, w × h facing ∓Y, t thick): the game paints the state's own flag on it."""
    o = bpy.data.objects.new(name, None)
    o.location = (x, y, z)
    o.scale = (w, t, h)
    bpy.context.scene.collection.objects.link(o)
    return o


def flagpole(x, y, h, team, w=0.15, pole="#d9d2c3"):
    cy(0.009, h, (x, y, h / 2), flat("pole", pole, 0.5), 6)
    bx((w, 0.008, w * 0.64), (x + w / 2 + 0.006, y, h - w * 0.34), flat("flag" + team, team, 0.7), bev=0)
    bx((w * 0.36, 0.011, w * 0.3), (x + w / 2 + 0.006, y, h - w * 0.3), flat("emblem", WHITE, 0.6), bev=0)
    flag_at("flagw", x + w / 2 + 0.006, y, h - w * 0.34, w + 0.004, w * 0.64 + 0.004)
    ico(0.016, (x, y, h + 0.01), flat("gold", GOLD, 0.35))


def banner(x, y, h, team, w=0.17):
    """Hanging war banner (crossbar, long cloth with white emblem) — the capital's marker."""
    pm = flat("pole", "#d9d2c3", 0.5)
    cy(0.011, h, (x, y, h / 2), pm, 6)
    cy(0.007, w + 0.04, (x + w / 2, y, h - 0.02), pm, 6, rot=(0, math.pi / 2, 0))
    bx((w, 0.01, w * 1.5), (x + w / 2, y, h - 0.03 - w * 0.75), flat("flag" + team, team, 0.7), bev=0)
    bx((w * 0.42, 0.013, w * 0.42), (x + w / 2, y, h - 0.03 - w * 0.6), flat("emblem", WHITE, 0.6), bev=0)
    flag_at("flagt", x + w / 2, y, h - 0.03 - w * 0.75, w + 0.004, w * 1.5 + 0.004, 0.017)
    ico(0.022, (x, y, h + 0.015), flat("gold", GOLD, 0.35))


def window(x, y, z, rz, w=0.045, h=0.05, frame=None):
    """Lit window (optionally framed) on a wall facing −Y rotated by rz about Z."""
    if frame:
        bx((w + 0.022, 0.01, h + 0.022), (x, y, z), flat("frame" + frame, frame, 0.7), rz, 0)
    bx((w, 0.014, h), (x, y, z), win_lit(), rz, 0)


def front_windows(w, d, zs, n=2, frame=None, sides=True, ww=0.045, wh=0.05):
    """Lit windows on the front (−Y) and back, plus the sides of a w×d box centred at the origin."""
    for z in zs:
        for i in range(n):
            x = (i + 0.5) / n * w - w / 2
            window(x, -d / 2 - 0.004, z, 0, ww, wh, frame)
            window(x, d / 2 + 0.004, z, 0, ww, wh, frame)
        if sides:
            window(-w / 2 - 0.004, 0, z, math.pi / 2, ww, wh, frame)
            window(w / 2 + 0.004, 0, z, math.pi / 2, ww, wh, frame)


def woodpile(n_rows=3):
    wm = tex("wood", "#9a6a3c", 3.0)
    cap = flat("logcut", "#d9b27a", 0.8)
    for row in range(n_rows):
        k = n_rows - row
        for i in range(k):
            y = (i - (k - 1) / 2) * 0.05
            z = 0.025 + row * 0.043
            cy(0.025, 0.2, (0, y, z), wm, 6, rot=(0, math.pi / 2, 0))
            for sx in (-1, 1):
                cy(0.021, 0.004, (sx * 0.1, y, z), cap, 6, rot=(0, math.pi / 2, 0))


def haystack(x, y, s=1.0):
    cy(0.085 * s, 0.07 * s, (x, y, 0.035 * s), tex("wood", THATCH, 3.0), 8)
    cn(0.095 * s, 0.13 * s, (x, y, 0.13 * s), tex("wood", THATCH, 3.0), 8)


def well():
    st = stone(STONE_D)
    cy(0.075, 0.08, (0, 0, 0.04), st, 10)
    cy(0.058, 0.004, (0, 0, 0.081), flat("water_d", "#24333d", 0.3), 10)
    wd = tex("wood", WOOD)
    for sx in (-1, 1):
        bx((0.022, 0.022, 0.22), (sx * 0.07, 0, 0.11), wd, bev=0)
    cy(0.012, 0.16, (0, 0, 0.17), wd, 6, rot=(0, math.pi / 2, 0))
    cy(0.022, 0.035, (0.02, 0, 0.12), tex("wood", WOOD_L), 8)
    return st


def bench(x, y, rz):
    def b():
        cy(0.022, 0.2, (0, 0, 0.03), tex("wood", "#8a5e36", 3.0), 6, rot=(0, math.pi / 2, 0))
    build_at(b, x, y, rz)


def smoke_at(x, y, z):
    """Empty node "smoke" at a chimney mouth: exported with the model, the game hangs a smoke plume on it."""
    o = bpy.data.objects.new("smoke", None)
    o.location = (x, y, z)
    bpy.context.scene.collection.objects.link(o)
    return o


def wattle(x0, y0, x1, y1, h=0.075):
    """Woven hazel fence (плетень): stakes and three wavy withy rows between them."""
    L = math.dist((x0, y0), (x1, y1))
    ang = math.atan2(y1 - y0, x1 - x0)
    n = max(2, round(L / 0.055))
    st = tex("wood", WOOD_D, 3.0)
    wy = flat("withy", "#8c6a42", 0.9)
    for i in range(n + 1):
        f = i / n
        cy(0.007, h + 0.02, (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, (h + 0.02) / 2), st, 5)
    for k in range(3):
        z = h * (0.3 + 0.32 * k)
        sh = 0.006 if k % 2 == 0 else -0.006
        bx((L, 0.009, 0.016), ((x0 + x1) / 2 - math.sin(ang) * sh, (y0 + y1) / 2 + math.cos(ang) * sh, z), wy, ang, 0)


def garden(w, d, rows=4, crop="#4f9a34", fence=True):
    """Vegetable patch: dark tilled soil, ridged beds with cabbage heads, a wattle fence with a gap for the gate."""
    soil = tex("plaster", "#5b3f27", 2.5)
    bx((w, d, 0.016), (0, 0, 0.008), soil, bev=0.004)
    bed = tex("plaster", "#6e4c2e", 3.0)
    leaf = flat("crop", crop, 0.8)
    leaf2 = flat("crop2", shade(crop, 1.25), 0.8)
    for r_ in range(rows):
        y = (r_ + 0.5) / rows * d - d / 2
        bx((w * 0.86, d / rows * 0.5, 0.018), (0, y, 0.02), bed, bev=0.006)
        n = max(2, int(w / 0.06))
        for i in range(n):
            x = (i + 0.5) / n * w * 0.82 - w * 0.41
            ico(0.019 if r_ % 2 == 0 else 0.015, (x, y, 0.04), leaf if (i + r_) % 3 else leaf2, (1, 1, 0.75), sub=1)
    if fence:
        hw, hd = w / 2 + 0.02, d / 2 + 0.02
        wattle(-hw, -hd, -hw, hd)
        wattle(-hw, hd, hw, hd)
        wattle(hw, hd, hw, -hd)
        wattle(hw, -hd, hw * 0.25, -hd)
        wattle(-hw * 0.25, -hd, -hw, -hd)


def cart(team, load="hay"):
    """Peasant cart (телега): plank bed on four spoked wheels, shafts, a load of hay or sacks."""
    wd = tex("wood", "#8a5e36", 2.5)
    dk = tex("wood", WOOD_D, 2.0)
    bx((0.2, 0.11, 0.02), (0, 0, 0.065), wd, bev=0.004)
    for sy in (-1, 1):
        bx((0.2, 0.01, 0.035), (0, sy * 0.055, 0.09), wd, bev=0.002)
    for sx in (-1, 1):
        bx((0.01, 0.11, 0.035), (sx * 0.1, 0, 0.09), wd, bev=0.002)
    for sx in (-0.065, 0.065):
        cy(0.006, 0.15, (sx, 0, 0.045), dk, 6, rot=(math.pi / 2, 0, 0))
        for sy in (-1, 1):
            rr = 0.045 if sx > 0 else 0.04
            cy(rr, 0.012, (sx, sy * 0.068, rr), dk, 10, rot=(math.pi / 2, 0, 0))
            cy(rr * 0.72, 0.014, (sx, sy * 0.068, rr), wd, 10, rot=(math.pi / 2, 0, 0))
            cy(rr * 0.25, 0.022, (sx, sy * 0.068, rr), dk, 6, rot=(math.pi / 2, 0, 0))
    for sy in (-1, 1):
        beam((-0.1, sy * 0.035, 0.07), (-0.27, sy * 0.045, 0.03), 0.01, dk)
    if load == "hay":
        uvs(0.075, (0.0, 0, 0.115), tex("wood", THATCH, 3.0), 8, 5, (1.35, 0.75, 0.55))
    else:
        sk = flat("sack", "#cdb88e", 0.95)
        for (x, y) in ((-0.05, -0.022), (0.0, 0.024), (0.05, -0.02)):
            uvs(0.03, (x, y, 0.105), sk, 7, 5, (1.3, 1, 0.85))
        bx((0.06, 0.02, 0.008), (0.0, 0.024, 0.134), flat("tie" + team, team, 0.7), bev=0)


def clock_face(x, y, z, rz, r=0.045):
    """Clock dial facing −Y rotated by rz around Z."""
    def b():
        cy(r * 1.15, 0.012, (0, -0.004, 0), flat("gold", GOLD, 0.35), 12, rot=(math.pi / 2, 0, 0))
        cy(r, 0.016, (0, -0.006, 0), flat("dial", "#fbf6e8", 0.5), 12, rot=(math.pi / 2, 0, 0))
        bx((0.006, 0.01, r * 0.75), (0, -0.016, r * 0.33), flat("hands", "#1d1b1a"), bev=0)
        bx((r * 0.6, 0.01, 0.006), (r * 0.27, -0.016, 0), flat("hands", "#1d1b1a"), bev=0)
    before = {o.name for o in bpy.context.scene.objects}
    b()
    new = [o for o in bpy.context.scene.objects if o.name not in before]
    bpy.context.view_layer.update()
    M = Matrix.Translation((x, y, z)) @ Matrix.Rotation(rz, 4, "Z")
    for o in new:
        o.matrix_world = M @ o.matrix_world


def onion(x, y, z, r, mt, drum_mt=None):
    """Onion dome on a drum: bulb, spike and a little golden ball (Russian terem/church top)."""
    if drum_mt:
        cy(r * 0.62, r * 0.9, (x, y, z + r * 0.45), drum_mt, 10)
        z += r * 0.9
    uvs(r, (x, y, z + r * 0.85), mt, 10, 6, (1, 1, 1.05))
    cn(r * 0.55, r * 1.25, (x, y, z + r * 1.55 + r * 0.62), mt, 10)
    ico(r * 0.17, (x, y, z + r * 2.45), flat("gold", GOLD, 0.35))


# ------------------------------------------------------------------ building types


def hut(w, d, h, team, smoke=False):
    """DL1 халупа: daub walls, shaggy thatch, team-coloured ridge cap and door."""
    bx((w, d, h + 0.04), (0, 0, (h - 0.04) / 2), tex("plaster", DAUB, 1.5), bev=0.015)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.014, h + 0.04, (sx * w / 2, sy * d / 2, (h - 0.04) / 2), tex("wood", WOOD_D), 6)
    rh = h * 1.2
    prism_roof("thatch", w, d, rh, (0, 0, h - 0.01), tex("wood", THATCH, 2.5), overhang=0.06)
    bx((w + 0.15, 0.05, 0.035), (0, 0, h + rh - 0.02), flat("ridge" + team, shade(team, 0.85)), bev=0.01)
    bx((0.07, 0.014, 0.11), (-w * 0.18, -d / 2 - 0.004, 0.055), flat("door" + team, shade(team, 0.7)), bev=0)
    window(w * 0.22, -d / 2 - 0.004, h * 0.6, 0, 0.04, 0.035, WOOD_D)
    if smoke:  # a clay flue through the thatch
        cy(0.022, 0.1, (w * 0.25, d * 0.08, h + rh * 0.55), tex("plaster", "#b08a62", 2.0), 7)
        smoke_at(w * 0.25, d * 0.08, h + rh * 0.55 + 0.06)


def laundry(x0, y0, x1, y1, team):
    wd = tex("wood", WOOD_D)
    for (x, y) in ((x0, y0), (x1, y1)):
        cy(0.011, 0.25, (x, y, 0.125), wd, 6)
    ang = math.atan2(y1 - y0, x1 - x0)
    L = math.dist((x0, y0), (x1, y1))
    bx((L, 0.006, 0.006), ((x0 + x1) / 2, (y0 + y1) / 2, 0.235), flat("rope", "#e8dcc0"), ang, 0)
    cols = [team, WHITE, shade(team, 0.7), "#e8cf8e", WHITE]
    for i, f in enumerate((0.14, 0.32, 0.5, 0.68, 0.86)):
        hgt = 0.09 if i % 2 == 0 else 0.065
        x, y = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        bx((0.07, 0.008, hgt), (x, y, 0.232 - hgt / 2), flat("cloth" + cols[i], cols[i], 0.85), ang, 0)


def log_house(w, d, h, team, gable_front=False, roof_k=0.85, logc=LOG, chimney=True, n_win=2, smoke=False):
    """DL2 изба: stacked logs with crossed corners, plank roof in the team colour, white-framed windows."""
    r = 0.023
    n = max(3, round(h / (2 * r * 0.92)))
    logm = tex("wood", logc, 3.0)
    cut = flat("logcut", "#d9b27a", 0.8)
    bx((w - 0.02, d - 0.02, h), (0, 0, h / 2), tex("wood", shade(logc, 0.75), 2.0), bev=0)
    top = 0
    for i in range(n):
        z = r + i * 2 * r * 0.92
        for sy in (-1, 1):
            cy(r, w + 0.07, (0, sy * d / 2, z), logm, 6, rot=(0, math.pi / 2, 0))
        z2 = z + r * 0.46
        for sx in (-1, 1):
            cy(r, d + 0.07, (sx * w / 2, 0, z2), logm, 6, rot=(math.pi / 2, 0, 0))
        top = z2 + r
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(r * 0.9, 0.006, (sx * (w / 2 + 0.035), sy * d / 2, r), cut, 6, rot=(0, math.pi / 2, 0))
    rh = (d if not gable_front else w) * roof_k
    roof = tex("wood", shade(team, 0.85), 2.0)
    if gable_front:
        prism_roof("roof", d, w, rh, (0, 0, top - 0.01), roof, overhang=0.06, rot_z=math.pi / 2)
        # carved white barge boards on the front gable
        tm = flat("trim", WHITE, 0.7)
        hw = w / 2 + 0.06
        for sx in (-1, 1):
            beam((sx * hw, -d / 2 - 0.068, top - 0.01), (0, -d / 2 - 0.068, top + rh - 0.01), 0.022, tm)
        window(0, -d / 2 - 0.066, top + rh * 0.32, 0, 0.04, 0.05, WHITE)
    else:
        prism_roof("roof", w, d, rh, (0, 0, top - 0.01), roof, overhang=0.06)
    for i in range(n_win):
        x = (i + 0.5) / n_win * w - w / 2
        window(x, -d / 2 - r - 0.002, h * 0.55, 0, 0.04, 0.05, WHITE)
        window(x, d / 2 + r + 0.002, h * 0.55, 0, 0.04, 0.05, WHITE)
    window(-w / 2 - r - 0.002, 0, h * 0.55, math.pi / 2, 0.04, 0.05, WHITE)
    if chimney:
        cy(0.026, 0.16, (w * 0.22, d * 0.12, top + rh * 0.55), stone(STONE_D), 8)
        cy(0.031, 0.02, (w * 0.22, d * 0.12, top + rh * 0.55 + 0.08), stone(STONE_D), 8)
        if smoke:
            smoke_at(w * 0.22, d * 0.12, top + rh * 0.55 + 0.1)
    return top, rh


def barn(team):
    w, d, h = 0.4, 0.28, 0.22
    bx((w, d, h), (0, 0, h / 2), tex("wood", "#7a5232", 1.6), bev=0.012)
    prism_roof("roof", w, d, 0.2, (0, 0, h - 0.005), tex("wood", shade(team, 0.75), 2.0), overhang=0.06)
    lw = tex("wood", WOOD_L)
    for sx in (-1, 1):
        bx((0.085, 0.014, 0.16), (sx * 0.045, -d / 2 - 0.004, 0.08), lw, bev=0)
        beam((sx * 0.045 - 0.035, -d / 2 - 0.013, 0.01), (sx * 0.045 + 0.035, -d / 2 - 0.013, 0.15), 0.014, flat("trim", WHITE, 0.7))
    bx((0.18, 0.016, 0.016), (0, -d / 2 - 0.012, 0.165), flat("trim", WHITE, 0.7), bev=0)


def stone_house(w, d, h, team, wall=STONE, roof_k=0.8, smoke=False):
    bx((w, d, h), (0, 0, h / 2), stone(wall, 1.6), bev=0.012)
    bx((w + 0.02, d + 0.02, 0.035), (0, 0, 0.0175), stone(STONE_D), bev=0)
    prism_roof("roof", w, d, d * roof_k, (0, 0, h - 0.005), tex("roof", slate(team, 1.00)), overhang=0.045)
    cy(0.028, 0.15, (w * 0.25, d * 0.15, h + d * roof_k * 0.55), stone(STONE_D), 8)
    if smoke:
        smoke_at(w * 0.25, d * 0.15, h + d * roof_k * 0.55 + 0.09)
    bx((0.065, 0.014, 0.11), (0, -d / 2 - 0.004, 0.055), tex("wood", WOOD_D), bev=0)
    for sx in (-1, 1):
        window(sx * w * 0.3, -d / 2 - 0.004, h * 0.62, 0, 0.04, 0.05, WOOD_D)
        window(sx * w * 0.3, d / 2 + 0.004, h * 0.62, 0, 0.04, 0.05, WOOD_D)
    window(w / 2 + 0.004, 0, h * 0.62, math.pi / 2, 0.04, 0.05, WOOD_D)
    window(-w / 2 - 0.004, 0, h * 0.62, math.pi / 2, 0.04, 0.05, WOOD_D)


def terem_block(w, d, h_stone, h_wood, team, roof_h, dome=True, dome_team=False):
    """Terem: white stone ground floor, timber upper storey, carved team band, tall tent roof, onion."""
    bx((w, d, h_stone), (0, 0, h_stone / 2), stone("#ece4d4", 1.4), bev=0.012)
    w2, d2 = w * 0.92, d * 0.92
    z1 = h_stone + h_wood
    bx((w2, d2, h_wood), (0, 0, h_stone + h_wood / 2), tex("wood", "#c98d4a", 2.5), bev=0.01)
    bx((w + 0.03, d + 0.03, 0.03), (0, 0, z1), flat("band" + team, shade(team, 0.9)), bev=0.006)
    hip_roof(w, d, roof_h, (0, 0, z1 + 0.015), tex("roof", slate(team, 1.00)), oh=0.035)
    nwin = 2 if w > 0.22 else 1
    for i in range(nwin):
        x = (i + 0.5) / nwin * w2 - w2 / 2
        window(x, -d2 / 2 - 0.004, h_stone + h_wood * 0.5, 0, 0.04, 0.06, WHITE)
        window(x, d2 / 2 + 0.004, h_stone + h_wood * 0.5, 0, 0.04, 0.06, WHITE)
    window(-w2 / 2 - 0.004, 0, h_stone + h_wood * 0.5, math.pi / 2, 0.04, 0.06, WHITE)
    window(w2 / 2 + 0.004, 0, h_stone + h_wood * 0.5, math.pi / 2, 0.04, 0.06, WHITE)
    window(0, -d / 2 - 0.004, h_stone * 0.55, 0, 0.035, 0.045, None)
    if dome:
        dm = flat("dome" + team, team, 0.45) if dome_team else flat("gold", GOLD, 0.35)
        onion(0, 0, z1 + roof_h * 0.85, min(w, d) * 0.2, dm, tex("wood", "#c98d4a"))
    return z1


def mansion(w, d, floors, wall, team, fh=0.11):
    H = floors * fh + 0.02
    bx((w + 0.02, d + 0.02, 0.04), (0, 0, 0.02), stone(STONE_D), bev=0)
    bx((w, d, H), (0, 0, H / 2), facade(wall, WIN_D, 0.07, fh, 0.42, 0.5, lit_p=0.3), bev=0.01)
    bx((w + 0.03, d + 0.03, 0.025), (0, 0, H), flat("cornice", WHITE, 0.6), bev=0.006)
    hip_roof(w, d, 0.14, (0, 0, H + 0.0125), tex("roof", slate(team, 1.00)), oh=0.02)
    for sx in (-1, 1):
        bx((0.035, 0.035, 0.1), (sx * w * 0.3, d * 0.15, H + 0.09), stone("#b0a594"), bev=0)
    bx((0.07, 0.016, 0.1), (0, -d / 2 - 0.004, 0.05), tex("wood", WOOD_D), bev=0)
    prism_roof("pedi", 0.03, 0.1, 0.035, (0, -d / 2 - 0.012, 0.105), flat("cornice", WHITE, 0.6), overhang=0.0, rot_z=math.pi / 2)
    return H


def tenement(w, d, floors, wall, team, fh=0.11):
    H = floors * fh + 0.03
    bx((w, d, H), (0, 0, H / 2), facade(wall, WIN_D, 0.065, fh, 0.45, 0.52, lit_p=0.28, z0=0.03), bev=0.008)
    bx((w + 0.025, d + 0.025, 0.022), (0, 0, H), flat("cornice", WHITE, 0.6), bev=0.005)
    bx((w - 0.03, d - 0.03, 0.012), (0, 0, H + 0.016), flat("tar", "#4a4b50", 0.9), bev=0)
    for sx in (-1, 1):
        bx((0.04, 0.05, 0.08), (sx * w * 0.32, 0.0, H + 0.05), stone(BRICK), bev=0)
    # ground-floor shops: lit shop window + team awning on the front and back
    for sy in (-1, 1):
        bx((w * 0.78, 0.012, 0.05), (0, sy * (d / 2 + 0.004), 0.06), win_lit(), bev=0)
        bx((w * 0.86, 0.07, 0.012), (0, sy * (d / 2 + 0.03), 0.11), flat("awn" + team, team, 0.7), bev=0,
           rot=(sy * 0.38, 0, 0))
    return H


def panel_block(w, d, floors, team, fh=0.088, wall=CONC):
    H = floors * fh + 0.03
    bx((w, d, H), (0, 0, H / 2), facade(wall, "#3a4656", 0.058, fh, 0.55, 0.5, lit="#ffe08a", lit_p=0.25, z0=0.03), bev=0.006)
    bx((w + 0.012, d + 0.012, 0.02), (0, 0, H), flat("parapet", CONC_D), bev=0)
    bx((0.09, 0.07, 0.06), (w * 0.25, 0, H + 0.04), flat("parapet", CONC_D), bev=0)
    # team stripes: stair-well column on both long faces + entrance canopies
    for sy in (-1, 1):
        bx((0.04, 0.014, H - 0.06), (-w * 0.2, sy * (d / 2 + 0.004), H / 2 + 0.02), flat("stripe" + team, team, 0.6), bev=0)
        bx((0.08, 0.05, 0.012), (-w * 0.2, sy * (d / 2 + 0.025), 0.085), flat("parapet", CONC_D), bev=0)
    return H


def glass_tower(w, d, h, team, style=0):
    """DL7 office tower: dark plinth, glass curtain wall, glowing floor bands, team crown."""
    base = flat("plinth", "#5d6470", 0.6)
    bx((w + 0.04, d + 0.04, 0.08), (0, 0, 0.04), base, bev=0.008)
    gl = facade("#33506b", GLASS, 0.05, 0.065, 0.8, 0.74, lit="#c8ecff", lit_p=0.3)
    bx((w, d, h - 0.08), (0, 0, 0.08 + (h - 0.08) / 2), gl, bev=0.006)
    band = glow("band", "#a8e6ff", 1.6)
    z = 0.08 + 0.2
    while z < h - 0.1:
        bx((w + 0.01, d + 0.01, 0.012), (0, 0, z), band, bev=0)
        z += 0.2
    tc = flat("crown" + team, team, 0.5)
    if style == 0:  # flat crown + antenna
        bx((w + 0.02, d + 0.02, 0.05), (0, 0, h + 0.02), tc, bev=0.006)
        bx((w * 0.5, d * 0.5, 0.06), (0, 0, h + 0.075), flat("plinth", "#5d6470", 0.6), bev=0)
        cy(0.008, 0.25, (w * 0.1, 0, h + 0.2), flat("mast", "#d0d4da", 0.5), 6)
        ico(0.014, (w * 0.1, 0, h + 0.33), glow("beacon", "#ff4a3a", 4.0))
    elif style == 1:  # slanted glass top
        bx((w + 0.02, d + 0.02, 0.03), (0, 0, h + 0.01), tc, bev=0)
        o = taper_box((w, d, 0.22), (0, 0, h + 0.135), gl, (1.0, 0.15))
        o.rotation_euler.z = 0.0
    else:  # stepped crown
        bx((w + 0.02, d + 0.02, 0.03), (0, 0, h + 0.01), tc, bev=0)
        bx((w * 0.7, d * 0.7, 0.22), (0, 0, h + 0.13), gl, bev=0.006)
        bx((w * 0.72, d * 0.72, 0.03), (0, 0, h + 0.25), tc, bev=0)
        cy(0.01, 0.3, (0, 0, h + 0.4), flat("mast", "#d0d4da", 0.5), 6)
        ico(0.014, (0, 0, h + 0.56), glow("beacon", "#ff4a3a", 4.0))


def neon_box(w, d, z0, h, team, gl, strips=True, ring=True):
    """Dark-glass block with team neon edges (DL8)."""
    neon = team_neon(team)
    bx((w, d, h), (0, 0, z0 + h / 2), gl, bev=0.006)
    if strips:
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((0.014, 0.014, h), (sx * w / 2, sy * d / 2, z0 + h / 2), neon, bev=0)
    if ring:
        frame(w, d, z0 + h - 0.01, neon)
    return neon


def frame(w, d, z, mt, t=0.016):
    """Glowing outline around the top of a w×d block (bars only, the roof stays dark)."""
    for sy in (-1, 1):
        bx((w + t, t, t), (0, sy * d / 2, z), mt, bev=0)
    for sx in (-1, 1):
        bx((t, d + t, t), (sx * w / 2, 0, z), mt, bev=0)


def team_neon(team):
    return glow("neon" + team, team, 3.0)


def dark_glass():
    return facade("#1b2533", "#2c4058", 0.045, 0.06, 0.62, 0.6, lit="#ffe2a0", lit_p=0.38)


# ------------------------------------------------------------------ CITY BLOCKS (one cluster per hex)


def city_dl1(team):
    pad(0.66, tex("plaster", DIRT, 1.2), 0.008, 12, 0.12, 1)
    build_at(lambda: hut(0.30, 0.24, 0.17, team, smoke=True), -0.36, 0.30, 0.25, 1, (0.05, -0.03))
    build_at(lambda: hut(0.27, 0.22, 0.15, team), 0.35, 0.33, -0.35, 1, (-0.04, 0.05))
    build_at(lambda: hut(0.28, 0.22, 0.16, team, smoke=True), -0.44, -0.22, 0.6, 1, (0.03, 0.05))
    build_at(lambda: hut(0.24, 0.20, 0.14, team), 0.42, -0.2, -0.5, 1, (-0.04, -0.03))
    laundry(-0.2, -0.03, 0.17, 0.06, team)
    build_at(woodpile, 0.0, 0.42, 0.1)
    cy(0.04, 0.06, (0.16, 0.36, 0.03), tex("wood", "#8a5e36"), 8)
    build_at(lambda: garden(0.24, 0.15, 3), -0.04, -0.3, 0.12)
    haystack(0.22, -0.46)
    bench(0.12, 0.22, 0.4)
    flagpole(-0.08, 0.2, 0.4, team, 0.12, "#8a6a44")
    tree(0.62, 0.08, 0.9)
    tree(-0.6, 0.16, 0.75, LEAF2)
    ico(0.05, (-0.3, -0.52, 0.01), tex("plaster", "#8d8a84"), (1.3, 1, 0.6))


def city_dl2(team):
    pad(0.66, tex("plaster", DIRT, 1.2), 0.008, 12, 0.1, 2)
    build_at(lambda: log_house(0.32, 0.26, 0.2, team, smoke=True), -0.36, 0.3, 0.12)
    build_at(lambda: log_house(0.28, 0.24, 0.18, team, gable_front=True, smoke=True), 0.36, 0.32, -0.15)
    build_at(lambda: log_house(0.28, 0.24, 0.17, team, n_win=1), -0.42, -0.26, 0.4)
    build_at(lambda: barn(team), 0.36, -0.26, -0.3)
    build_at(well, 0.0, -0.04, 0.3)
    prism_roof("well_roof", 0.18, 0.14, 0.07, (0, -0.04, 0.22), tex("wood", shade(team, 0.75)), overhang=0.02, rot_z=0.3)
    build_at(lambda: garden(0.26, 0.15, 3, "#5aa63a"), -0.1, -0.5, 0.25)
    build_at(lambda: cart(team, "sacks"), 0.17, -0.5, -0.5)
    haystack(0.58, -0.02, 0.85)
    build_at(lambda: woodpile(2), 0.02, 0.4, 0.0)
    bench(-0.16, 0.12, 0.2)
    pine(0.6, 0.22, 1.1)
    pine(-0.66, 0.06, 1.0)
    tree(-0.58, 0.3, 0.7, LEAF2)
    flagpole(0.14, 0.16, 0.45, team, 0.13, "#8a6a44")


def city_dl3(team):
    pad(0.7, stone(COBBLE, 1.8), 0.012, 14, 0.06, 3)
    build_at(lambda: (terem_block(0.3, 0.26, 0.16, 0.18, team, 0.3),
                      bx((0.14, 0.1, 0.02), (0, -0.18, 0.01), stone(STONE_D), bev=0)), 0.0, 0.32)
    build_at(lambda: stone_house(0.3, 0.22, 0.2, team, smoke=True), -0.46, 0.02, 0.2)
    build_at(lambda: stone_house(0.27, 0.22, 0.2, team, "#d8cdb6"), 0.46, -0.02, -0.25)
    build_at(lambda: stone_house(0.28, 0.2, 0.18, team, "#c2b8a6", smoke=True), -0.2, -0.43, 0.1)
    build_at(lambda: stone_house(0.24, 0.2, 0.17, team), 0.25, -0.44, -0.1)
    tree(-0.12, 0.62, 0.9)
    tree(0.36, 0.56, 0.8)
    flagpole(0.05, -0.12, 0.55, team, 0.14)


def city_dl4(team):
    pad(0.74, stone(COBBLE, 1.8), 0.012, 14, 0.04, 4)

    def town_hall():
        st = facade("#ddc9a0", WIN_D, 0.07, 0.12, 0.42, 0.5, lit_p=0.35)
        bx((0.58, 0.26, 0.28), (0, 0, 0.14), st, bev=0.01)
        bx((0.6, 0.28, 0.025), (0, 0, 0.28), flat("cornice", WHITE, 0.6), bev=0.006)
        hip_roof(0.58, 0.26, 0.13, (0, 0, 0.29), tex("roof", slate(team, 1.00)), oh=0.02)
        tw = stone("#e6dcc4", 1.5)
        bx((0.15, 0.15, 0.66), (0, 0.0, 0.33), tw, bev=0.01)
        bx((0.18, 0.18, 0.025), (0, 0, 0.66), flat("cornice", WHITE, 0.6), bev=0.005)
        bx((0.13, 0.13, 0.12), (0, 0, 0.73), tw, bev=0.008)
        for k in range(4):
            a = k * math.pi / 2
            clock_face(math.sin(a) * 0.076, -math.cos(a) * 0.076, 0.56, a)
            window(math.sin(a) * 0.066, -math.cos(a) * 0.066, 0.74, a, 0.04, 0.07)
        hip_roof(0.13, 0.13, 0.3, (0, 0, 0.79), tex("roof", slate(team, 1.00)), oh=0.025)
        ico(0.02, (0, 0, 1.11), flat("gold", GOLD, 0.35))
        for x in (-0.09, -0.03, 0.03, 0.09):
            cy(0.014, 0.18, (x, -0.165, 0.09), flat("cornice", WHITE, 0.6), 8)
        bx((0.24, 0.07, 0.02), (0, -0.165, 0.19), flat("cornice", WHITE, 0.6), bev=0)
        prism_roof("pedi", 0.07, 0.22, 0.06, (0, -0.165, 0.2), flat("cornice", WHITE, 0.6), overhang=0.01, rot_z=math.pi / 2)
    build_at(town_hall, 0.0, 0.36)
    build_at(lambda: mansion(0.26, 0.22, 3, "#f0d9b5", team), -0.47, -0.02, 0.15)
    build_at(lambda: mansion(0.28, 0.22, 2, "#e9c2b4", team), 0.47, 0.0, -0.15)
    build_at(lambda: mansion(0.24, 0.2, 2, "#d5dfc3", team), -0.2, -0.45, 0.08)
    build_at(lambda: mansion(0.22, 0.2, 3, "#f2e4c4", team), 0.24, -0.46, -0.08)

    def fountain():
        st = stone(STONE)
        cy(0.11, 0.05, (0, 0, 0.025), st, 12)
        cy(0.095, 0.004, (0, 0, 0.05), flat("water", "#5fb8e0", 0.15), 12)
        cy(0.02, 0.12, (0, 0, 0.09), st, 8)
        cy(0.045, 0.02, (0, 0, 0.15), st, 10)
    build_at(fountain, 0.02, -0.06)
    tree(-0.24, 0.0, 0.8)
    tree(0.26, -0.06, 0.8)
    flagpole(0.2, 0.18, 0.5, team, 0.14)


def city_dl5(team):
    pad(0.76, stone("#8f8a82", 2.2), 0.012, 14, 0.03, 5)

    def factory():
        f = facade(BRICK, "#3b4552", 0.085, 0.13, 0.5, 0.6, lit="#ffd27a", lit_p=0.35, brick=True)
        bx((0.62, 0.3, 0.24), (0, 0, 0.12), f, bev=0.01)
        bx((0.64, 0.32, 0.02), (0, 0, 0.24), flat("cornice", "#d8cfc0", 0.6), bev=0)
        for i in range(3):
            prism_roof("saw", 0.3, 0.2, 0.1, (-0.2 + i * 0.205, 0, 0.245), tex("roof", slate(team, 0.94)), overhang=0.01, rot_z=math.pi / 2)
        cm = stone("#9a3d30", 2.0)
        for (x, y, h) in ((-0.2, 0.2, 0.86), (0.06, 0.21, 0.72)):
            cy(0.055, h, (x, y, h / 2), cm, 10, r2=0.038)
            cy(0.045, 0.04, (x, y, h * 0.72), flat("band" + team, team, 0.6), 10)
            cy(0.044, 0.04, (x, y, h - 0.01), flat("soot", "#2b2726", 0.9), 10)
        bx((0.08, 0.016, 0.13), (-0.12, -0.155, 0.065), tex("wood", WOOD_D), bev=0)
        bx((0.08, 0.016, 0.13), (0.12, -0.155, 0.065), tex("wood", WOOD_D), bev=0)
    build_at(factory, -0.04, 0.33)

    def tank():
        bx((0.16, 0.16, 0.3), (0, 0, 0.15), facade(BRICK, "#3b4552", 0.08, 0.13, 0.4, 0.5, lit_p=0.3, brick=True), bev=0.008)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cy(0.01, 0.12, (sx * 0.05, sy * 0.05, 0.36), flat("iron", "#4a4d52", 0.6), 6)
        cy(0.08, 0.1, (0, 0, 0.47), flat("tankc", "#6d7278", 0.6), 12)
        cn(0.085, 0.05, (0, 0, 0.545), flat("roofi" + team, shade(team, 0.75), 0.6), 12)
    build_at(tank, 0.45, 0.16)
    build_at(lambda: tenement(0.26, 0.24, 4, "#dcb98a", team), -0.48, -0.08, 0.12)
    build_at(lambda: tenement(0.24, 0.22, 4, "#c9bba8", team), 0.44, -0.2, -0.12)
    build_at(lambda: tenement(0.3, 0.2, 3, "#e3c99c", team), -0.1, -0.46, 0.05)
    crate = tex("wood", WOOD_L)
    for (x, y) in ((0.2, -0.47), (0.25, -0.43), (0.22, -0.52)):
        bx((0.05, 0.05, 0.05), (x, y, 0.025), crate, bev=0.005)
    flagpole(0.2, 0.06, 0.55, team, 0.14)


def city_dl6(team):
    pad(0.78, flat("asph", ASPH, 0.9), 0.012, 14, 0.0, 6)
    build_at(lambda: panel_block(0.64, 0.16, 9, team), 0.0, 0.44)
    build_at(lambda: panel_block(0.44, 0.16, 5, team, wall="#d6cfc2"), -0.5, -0.02, math.pi / 2)
    build_at(lambda: panel_block(0.44, 0.16, 6, team, wall="#cfd3d6"), 0.5, 0.02, math.pi / 2)

    def station():
        f = facade("#e6dcc4", "#3a4656", 0.06, 0.1, 0.5, 0.65, lit_p=0.4)
        bx((0.5, 0.18, 0.16), (0, 0, 0.08), f, bev=0.008)
        hip_roof(0.5, 0.18, 0.08, (0, 0, 0.16), tex("roof", slate(team, 1.00)), oh=0.015)
        bx((0.17, 0.2, 0.27), (0, 0, 0.135), f, bev=0.008)
        prism_roof("hallroof", 0.17, 0.2, 0.09, (0, 0, 0.27), tex("roof", slate(team, 1.00)), overhang=0.015, rot_z=math.pi / 2)
        clock_face(0, -0.105, 0.21, 0, 0.035)
        bx((0.6, 0.12, 0.015), (0, -0.17, 0.15), flat("canopy" + team, team, 0.6), bev=0)
        for x in (-0.27, -0.09, 0.09, 0.27):
            cy(0.008, 0.15, (x, -0.215, 0.075), flat("iron", "#4a4d52", 0.6), 6)
        bx((0.66, 0.12, 0.03), (0, -0.17, 0.015), stone(STONE), bev=0)
    build_at(station, 0.0, -0.22)
    # rail line along the front edge
    bx((1.06, 0.13, 0.016), (0, -0.52, 0.016), tex("plaster", "#8a8178", 2.0), bev=0)
    for i in range(13):
        bx((0.025, 0.11, 0.01), (-0.48 + i * 0.08, -0.52, 0.028), tex("wood", WOOD_D), bev=0)
    for sy in (-0.035, 0.035):
        bx((1.04, 0.011, 0.014), (0, -0.52 + sy, 0.036), flat("rail", "#6f747b", 0.4), bev=0)
    tree(-0.2, 0.12, 0.9)
    tree(0.22, 0.14, 0.85)
    tree(0.0, 0.1, 0.75)
    flagpole(-0.32, -0.3, 0.45, team, 0.12)


def city_dl7(team):
    pad(0.8, stone("#c9c6bf", 3.0), 0.015, 14, 0.0, 7)
    build_at(lambda: glass_tower(0.3, 0.26, 1.42, team, 2), -0.16, 0.32)
    build_at(lambda: glass_tower(0.25, 0.23, 1.05, team, 1), 0.38, 0.14, -0.2)
    build_at(lambda: glass_tower(0.22, 0.22, 0.72, team, 0), -0.44, -0.24, 0.3)

    def pavilion():
        gl = facade("#33506b", GLASS, 0.05, 0.07, 0.8, 0.74, lit="#c8ecff", lit_p=0.3)
        bx((0.34, 0.2, 0.15), (0, 0, 0.075), gl, bev=0.008)
        bx((0.38, 0.24, 0.025), (0, 0, 0.16), flat("crown" + team, team, 0.5), bev=0.005)
        bx((0.26, 0.14, 0.02), (0, 0, 0.18), flat("lawn", "#5fa83a", 0.9), bev=0)
    build_at(pavilion, 0.22, -0.42, -0.1)
    for (x, y) in ((-0.1, -0.2), (0.06, -0.05), (-0.62, 0.1)):
        bx((0.08, 0.08, 0.04), (x, y, 0.02), flat("planter", "#7a7f88", 0.6), bev=0.006)
        tree(x, y, 0.75)
    for x in (-0.12, -0.04, 0.04):
        flagpole(x, -0.58, 0.42, team, 0.11, "#d0d4da")


def city_dl8(team):
    pad(0.8, flat("plaza8", "#3e424a", 0.7), 0.015, 14, 0.0, 8)
    gl = dark_glass()
    neon = team_neon(team)

    def tower_a():  # stepped needle, 2.2
        neon_box(0.36, 0.32, 0.0, 0.92, team, gl)
        neon_box(0.28, 0.25, 0.92, 0.6, team, gl)
        neon_box(0.18, 0.16, 1.52, 0.38, team, gl)
        cn(0.05, 0.3, (0, 0, 2.05), flat("spire", "#c9d0d8", 0.4), 6)
        ico(0.018, (0, 0, 2.2), neon)
    build_at(tower_a, -0.14, 0.3)

    def tower_b():  # tapered octagon, 1.7
        cy(0.22, 1.5, (0, 0, 0.75), gl, 8, r2=0.14)
        for z in (0.3, 0.6, 0.9, 1.2, 1.48):
            r = 0.22 + (0.14 - 0.22) * z / 1.5
            cy(r + 0.008, 0.016, (0, 0, z), neon, 8)
        cn(0.14, 0.24, (0, 0, 1.62), neon, 8)
    build_at(tower_b, 0.42, 0.12)

    def tower_c():  # slab with billboard, 1.25
        neon_box(0.3, 0.18, 0.0, 1.16, team, gl, strips=False)
        for x in (-0.09, 0.0, 0.09):
            bx((0.012, 0.012, 1.1), (x, -0.094, 0.58), neon, bev=0)
        taper_box((0.3, 0.18, 0.12), (0, 0, 1.22), gl, (1.0, 0.1))
        bx((0.018, 0.018, 0.16), (0.1, -0.04, 1.3), flat("mast", "#d0d4da", 0.5), bev=0)
        bx((0.22, 0.012, 0.13), (0.0, -0.11, 0.62), glow("holo" + team, shade(team, 1.35), 3.5), bev=0)
    build_at(tower_c, -0.44, -0.24, 0.35)

    def mall():
        bx((0.36, 0.22, 0.16), (0, 0, 0.08), gl, bev=0.008)
        frame(0.36, 0.22, 0.15, neon)
        bx((0.3, 0.012, 0.03), (0, -0.115, 0.12), glow("cyan", CYAN, 2.5), bev=0)
    build_at(mall, 0.24, -0.4, -0.1)
    for (x, y) in ((-0.02, -0.1), (0.12, 0.62), (-0.66, 0.12), (0.0, -0.6)):
        cy(0.007, 0.16, (x, y, 0.08), flat("mast", "#d0d4da", 0.5), 6)
        ico(0.016, (x, y, 0.17), glow("cyan", CYAN, 2.5))


# ------------------------------------------------------------------ RESIDENCES (capital, scale 1.0)


def residence_dl1(team):
    pad(0.78, tex("plaster", DIRT, 1.2), 0.008, 14, 0.1, 11)

    def shalash():
        br = tex("wood", "#8a6a3e", 2.5)
        cn(0.36, 0.64, (0, 0, 0.32), br, 9)
        cn(0.3, 0.3, (0, 0, 0.47), tex("wood", THATCH, 2.5), 9)
        wd = tex("wood", WOOD_D)
        for k in range(6):
            a = k * math.tau / 6 + 0.3
            beam((math.cos(a) * 0.34, math.sin(a) * 0.34, 0.0), (-math.cos(a) * 0.05, -math.sin(a) * 0.05, 0.8), 0.022, wd)
        mesh_obj([(-0.09, -0.335, 0.0), (0.09, -0.335, 0.0), (0.0, -0.215, 0.22), (-0.09, -0.345, 0.0), (0.09, -0.345, 0.0), (0.0, -0.225, 0.22)],
                 [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], flat("hole", "#1e140c", 0.95))
        bx((0.3, 0.012, 0.06), (0, -0.23, 0.32), flat("flag" + team, team, 0.7), bev=0, rot=(-0.5, 0, 0))
    build_at(shalash, 0.0, 0.2)

    def fire():
        rk = tex("plaster", "#8d8a84")
        for k in range(7):
            a = k * math.tau / 7
            ico(0.028, (math.cos(a) * 0.085, math.sin(a) * 0.085, 0.015), rk, (1.2, 1, 0.7))
        for k in range(3):
            a = k * math.tau / 3
            beam((math.cos(a) * 0.07, math.sin(a) * 0.07, 0.01), (-math.cos(a) * 0.02, -math.sin(a) * 0.02, 0.06), 0.02, tex("wood", WOOD_D))
        cn(0.05, 0.13, (0, 0, 0.08), glow("fire", "#ff7a1a", 4.0), 7)
        cn(0.028, 0.09, (0, 0, 0.07), glow("fire2", "#ffd34a", 5.0), 6)
        smoke_at(0, 0, 0.17)
    build_at(fire, 0.05, -0.36)
    bench(-0.17, -0.38, 1.4)
    bench(0.27, -0.36, 1.7)
    bench(0.07, -0.56, 0.0)

    def leanto():
        wd = tex("wood", WOOD_D)
        for sx in (-1, 1):
            cy(0.014, 0.24, (sx * 0.12, -0.08, 0.12), wd, 6)
        bx((0.3, 0.24, 0.02), (0, 0.0, 0.17), tex("wood", THATCH, 2.5), bev=0, rot=(-0.55, 0, 0))
        for i in range(3):
            ico(0.045, (-0.07 + i * 0.07, 0.03, 0.035), tex("plaster", "#d8c69c"), (1, 0.9, 1.1))
    build_at(leanto, -0.5, -0.04, 0.9)
    build_at(woodpile, 0.48, -0.16, -0.6)
    haystack(-0.36, 0.42, 0.9)
    banner(0.42, 0.28, 0.9, team, 0.16)
    pine(-0.6, 0.3, 1.1)


def residence_dl2(team):
    pad(0.8, tex("plaster", DIRT, 1.2), 0.008, 14, 0.08, 12)

    def main():
        top, rh = log_house(0.42, 0.5, 0.32, team, gable_front=True, roof_k=0.72, n_win=2, smoke=True)
        # porch (крыльцо) with its own little roof
        wd = tex("wood", WOOD_L)
        for i in range(3):
            bx((0.14, 0.05 - 0.0, 0.03), (0.0, -0.3 - i * 0.04, 0.09 - i * 0.03), wd, bev=0)
        for sx in (-1, 1):
            cy(0.012, 0.24, (sx * 0.07, -0.33, 0.12), wd, 6)
        prism_roof("porch", 0.1, 0.16, 0.08, (0, -0.31, 0.24), tex("wood", shade(team, 0.85)), overhang=0.02, rot_z=math.pi / 2)
    build_at(main, 0.0, 0.2)
    build_at(lambda: log_house(0.24, 0.2, 0.15, team, chimney=False, n_win=1), -0.48, -0.26, 0.5)
    build_at(lambda: barn(team), 0.46, -0.22, -0.5, 0.8)
    build_at(well, -0.12, -0.46, 0.2)
    prism_roof("well_roof", 0.18, 0.14, 0.07, (-0.12, -0.46, 0.22), tex("wood", shade(team, 0.75)), overhang=0.02, rot_z=0.2)
    fm = tex("wood", WOOD_L)
    for (x0, y0, x1, y1) in ((-0.62, 0.02, -0.3, 0.48), (0.62, 0.02, 0.3, 0.5)):
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            cy(0.012, 0.13, (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, 0.065), fm, 6)
        for z in (0.05, 0.1):
            beam((x0, y0, z), (x1, y1, z), 0.016, fm)
    banner(0.34, -0.42, 0.85, team, 0.15)
    banner(-0.36, 0.0, 0.85, team, 0.15)
    tree(0.14, 0.66, 0.9)


def residence_dl3(team):
    pad(0.82, stone(COBBLE, 1.8), 0.014, 14, 0.04, 13)
    bx((0.74, 0.5, 0.05), (0, 0.16, 0.025), stone("#d8cfbe", 1.5), bev=0.01)
    build_at(lambda: terem_block(0.36, 0.3, 0.2, 0.22, team, 0.42), 0.0, 0.2)
    build_at(lambda: terem_block(0.26, 0.24, 0.16, 0.16, team, 0.28, dome_team=True), -0.38, 0.06)
    build_at(lambda: terem_block(0.16, 0.16, 0.36, 0.2, team, 0.3, dome_team=True), 0.34, 0.26)
    # covered gallery joining the wing to the main terem
    gm = tex("wood", "#c98d4a", 2.5)
    bx((0.16, 0.1, 0.08), (-0.2, 0.06, 0.25), gm, bev=0.006)
    prism_roof("gal", 0.16, 0.1, 0.06, (-0.2, 0.06, 0.29), tex("roof", slate(team, 1.00)), overhang=0.02)
    for x in (-0.26, -0.14):
        cy(0.012, 0.25, (x, 0.06, 0.125), gm, 6)
    # front porch with a tent roof
    for i in range(3):
        bx((0.16, 0.05, 0.04), (0, -0.0 - i * 0.045, 0.13 - i * 0.04), stone("#ece4d4"), bev=0)
    for sx in (-1, 1):
        cy(0.014, 0.28, (sx * 0.07, -0.08, 0.14 + 0.05), gm, 6)
    hip_roof(0.16, 0.12, 0.12, (0, -0.05, 0.33), tex("roof", slate(team, 1.00)), oh=0.02)
    banner(-0.3, -0.45, 0.8, team, 0.15)
    banner(0.3, -0.45, 0.8, team, 0.15)
    tree(0.56, -0.2, 0.85)
    tree(-0.6, -0.3, 0.8)


def castle_tower(x, y, r, h, roof, team, flag=True):
    """A round castle tower as in the concept art: plinth, body, a string course, merlons, a tall cone roof
    with a gilt finial and a pennant in the team colour."""
    st = stone(STONE)
    dk = stone(STONE_D)
    cy(r + 0.012, 0.05, (x, y, 0.025), dk, 12)
    cy(r, h, (x, y, h / 2), st, 12)
    cy(r + 0.006, 0.016, (x, y, h * 0.55), dk, 12)
    cy(r + 0.014, 0.035, (x, y, h - 0.012), dk, 12)
    for k in range(8):
        a = math.tau * k / 8
        bx((r * 0.38, r * 0.3, 0.045), (x + math.cos(a) * r, y + math.sin(a) * r, h + 0.022), st, a, 0)
    for zf, k0 in ((0.36, 0), (0.74, 1)):  # narrow lit windows and dark slits around the body
        for k in range(3):
            a = math.tau * (k + 0.5 * k0) / 3 - math.pi / 2
            wx, wy = x + math.cos(a) * (r + 0.002), y + math.sin(a) * (r + 0.002)
            if k == 0:
                bx((0.022, 0.012, 0.04), (wx, wy, h * zf), win_lit(), a + math.pi / 2, 0)
            else:
                bx((0.014, 0.012, 0.034), (wx, wy, h * zf), flat("slit", "#1c1a19", 0.9), a + math.pi / 2, 0)
    cn(r + 0.03, r * 3.4, (x, y, h + r * 1.7 + 0.02), roof, 12)
    top = h + r * 3.4 + 0.02
    uvs(0.012, (x, y, top + 0.01), flat("finial", GOLD, 0.35), 6, 4)
    if flag:
        rod((x, y, top), (x, y, top + 0.13), 0.004, flat("pole", "#d9d2c3", 0.5), n=4)
        bx((0.07, 0.004, 0.04), (x + 0.036, y, top + 0.11), flat("pennant_" + team, team, 0.6), 0, 0)


def residence_dl4(team):
    pad(0.84, stone(COBBLE, 1.8), 0.014, 14, 0.03, 14)
    st = stone(STONE)
    roof = tex("roof", slate(team, 0.94))
    H = 0.48
    corners = [(-H, -H), (H, -H), (H, H), (-H, H)]

    def wall(x0, y0, x1, y1, gap=0.0):
        ln = math.dist((x0, y0), (x1, y1))
        ang = math.atan2(y1 - y0, x1 - x0)
        segs = [(0, ln)] if gap == 0 else [(0, ln / 2 - gap / 2), (ln / 2 + gap / 2, ln)]
        for (a, b) in segs:
            f = (a + b) / 2 / ln
            cx, cy_ = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            bx((b - a, 0.08, 0.28), (cx, cy_, 0.14), st, ang, bev=0.008)
            n = max(1, int((b - a) / 0.085))
            for i in range(0, n, 2):
                g = (a + (i + 0.5) * (b - a) / n) / ln
                bx(((b - a) / n, 0.085, 0.06), (x0 + (x1 - x0) * g, y0 + (y1 - y0) * g, 0.31), st, ang, bev=0)
    for i in range(4):
        x0, y0 = corners[i]
        x1, y1 = corners[(i + 1) % 4]
        wall(x0, y0, x1, y1, 0.22 if i == 0 else 0.0)
    for (x, y) in corners:
        castle_tower(x, y, 0.1, 0.52, roof, team)
        window(x, y - 0.1, 0.36, 0, 0.025, 0.045)
    # mid-wall towers on the three plain walls and turrets flanking the gate (the many towers of reference frame 4)
    for (x, y) in ((-H, 0.0), (H, 0.0), (0.0, H)):
        castle_tower(x, y, 0.075, 0.42, roof, team, flag=False)
    for sx in (-1, 1):
        castle_tower(sx * 0.17, -H - 0.02, 0.06, 0.5, roof, team, flag=False)
    # gatehouse
    bx((0.26, 0.16, 0.4), (0, -H, 0.2), st, bev=0.01)
    bx((0.12, 0.02, 0.18), (0, -H - 0.08, 0.09), tex("wood", "#4a2f19"), bev=0)
    prism_roof("gate_roof", 0.28, 0.18, 0.14, (0, -H, 0.4), roof)
    # keep with two turrets and a hall
    bx((0.4, 0.32, 0.66), (0.04, 0.12, 0.33), st, bev=0.012)
    prism_roof("keep_roof", 0.42, 0.34, 0.3, (0.04, 0.12, 0.66), roof)
    for i in range(4):
        window(-0.11 + i * 0.1, -0.044, 0.48, 0, 0.03, 0.06)
        window(-0.11 + i * 0.1, -0.044, 0.28, 0, 0.026, 0.05)
    for (x, y, h) in ((-0.16, -0.04, 0.86), (0.24, -0.04, 0.78)):
        castle_tower(x, y, 0.08, h, roof, team, flag=False)
    castle_tower(0.04, 0.24, 0.085, 1.08, roof, team)  # the tall central tower — the castle's silhouette
    build_at(lambda: stone_house(0.3, 0.22, 0.28, team, STONE), -0.26, 0.3)
    banner(0.04, 0.12, 1.4, team, 0.3)  # the great hanging banners of reference frame 4
    banner(-H, -H, 1.05, team, 0.2)
    banner(H, -H, 1.05, team, 0.2)
    for x in (-0.03, 0.11):  # long banners hanging down the keep front, between the turrets
        flag_at("flagt", x, -0.056, 0.5, 0.09, 0.22, 0.012)
        bx((0.09, 0.008, 0.22), (x, -0.056, 0.5), flat("flag" + team, team, 0.7), bev=0)
        bx((0.11, 0.012, 0.012), (x, -0.056, 0.615), flat("pole", "#d9d2c3", 0.5), bev=0)


def residence_dl5(team):
    pad(0.86, stone("#b9b3a8", 2.2), 0.014, 14, 0.0, 15)
    bx((0.88, 0.46, 0.05), (0, 0.12, 0.025), stone("#a59d8e", 1.6), bev=0.01)
    f = facade("#e3cfa6", WIN_D, 0.068, 0.12, 0.42, 0.55, lit_p=0.35, z0=0.05)
    roof = tex("roof", slate(team, 1.00))
    wh = flat("cornice", WHITE, 0.6)
    bx((0.62, 0.32, 0.36), (0, 0.14, 0.23), f, bev=0.01)
    bx((0.64, 0.34, 0.025), (0, 0.14, 0.41), wh, bev=0.006)
    hip_roof(0.62, 0.32, 0.14, (0, 0.14, 0.42), roof, oh=0.02)
    for sx in (-1, 1):  # corner pavilions with tent roofs
        bx((0.16, 0.38, 0.44), (sx * 0.36, 0.14, 0.27), f, bev=0.01)
        bx((0.18, 0.4, 0.025), (sx * 0.36, 0.14, 0.49), wh, bev=0.006)
        hip_roof(0.16, 0.38, 0.18, (sx * 0.36, 0.14, 0.5), roof, oh=0.02)
        flagpole(sx * 0.36, 0.14, 0.86, team, 0.12)
    # portico: columns + pediment
    bx((0.28, 0.08, 0.04), (0, -0.05, 0.07), stone("#d8cfbe"), bev=0)
    for i in range(5):
        cy(0.016, 0.3, (-0.12 + i * 0.06, -0.06, 0.24), wh, 8)
    bx((0.3, 0.1, 0.03), (0, -0.04, 0.405), wh, bev=0)
    prism_roof("pedi", 0.1, 0.28, 0.08, (0, -0.04, 0.42), wh, overhang=0.01, rot_z=math.pi / 2)
    # central clock tower with a team dome
    bx((0.17, 0.17, 0.36), (0, 0.14, 0.62), stone("#efe6d2", 1.5), bev=0.01)
    bx((0.2, 0.2, 0.025), (0, 0.14, 0.8), wh, bev=0.006)
    for k in range(4):
        a = k * math.pi / 2
        clock_face(math.sin(a) * 0.087, 0.14 - math.cos(a) * 0.087, 0.7, a, 0.045)
    cy(0.075, 0.08, (0, 0.14, 0.85), stone("#efe6d2"), 12)
    uvs(0.095, (0, 0.14, 0.89), flat("dome" + team, team, 0.45), 12, 6, (1, 1, 0.9))
    cy(0.02, 0.07, (0, 0.14, 1.0), wh, 8)
    flagpole(0, 0.14, 1.32, team, 0.16)
    # front square: fountain and two lamp posts
    cy(0.11, 0.05, (0, -0.42, 0.025), stone(STONE), 12)
    cy(0.095, 0.004, (0, -0.42, 0.05), flat("water", "#5fb8e0", 0.15), 12)
    cy(0.02, 0.12, (0, -0.42, 0.09), stone(STONE), 8)
    for sx in (-1, 1):
        cy(0.008, 0.2, (sx * 0.24, -0.4, 0.1), flat("iron", "#3b3d42", 0.6), 6)
        ico(0.022, (sx * 0.24, -0.4, 0.21), win_lit())
        tree(sx * 0.58, -0.3, 0.85)


def residence_dl6(team):
    pad(0.86, flat("asph", ASPH, 0.9), 0.014, 14, 0.0, 16)
    bx((0.94, 0.52, 0.05), (0, 0.12, 0.025), stone("#9a8f84", 1.6), bev=0.01)
    f = facade("#d8c4a0", "#34404e", 0.06, 0.1, 0.45, 0.55, lit="#ffe08a", lit_p=0.35, z0=0.05)
    trim = flat("cornice", "#efe6d2", 0.6)
    spire_m = flat("spire" + team, shade(team, 0.9), 0.4)
    gold = flat("gold", GOLD, 0.35)
    bx((0.88, 0.36, 0.32), (0, 0.16, 0.21), f, bev=0.01)
    bx((0.9, 0.38, 0.025), (0, 0.16, 0.37), trim, bev=0.006)
    tiers = [(0.36, 0.32, 0.05, 0.72), (0.27, 0.24, 0.72, 1.0), (0.18, 0.16, 1.0, 1.2)]
    for (w, d, z0, z1) in tiers:
        bx((w, d, z1 - z0), (0, 0.16, (z0 + z1) / 2), f, bev=0.008)
        bx((w + 0.03, d + 0.03, 0.025), (0, 0.16, z1), trim, bev=0.006)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cn(0.022, 0.09, (sx * w / 2, 0.16 + sy * d / 2, z1 + 0.055), spire_m, 4)
    cy(0.06, 0.08, (0, 0.16, 1.25), trim, 8)
    cn(0.06, 0.42, (0, 0.16, 1.5), spire_m, 8)
    # star on the spire (flat five-pointed, glowing faintly in the team colour)
    pts = []
    for k in range(10):
        r = 0.07 if k % 2 == 0 else 0.03
        a = math.pi / 2 + k * math.pi / 5
        pts.append((math.cos(a) * r, math.sin(a) * r))
    extrude(pts, -0.012, 0.012, glow("star" + team, shade(team, 1.2), 1.8), (0, 0.16, 1.77), (math.pi / 2, 0, 0))
    for sx in (-1, 1):  # side towers
        bx((0.13, 0.13, 0.62), (sx * 0.38, 0.16, 0.36), f, bev=0.008)
        bx((0.15, 0.15, 0.02), (sx * 0.38, 0.16, 0.67), trim, bev=0)
        cn(0.05, 0.28, (sx * 0.38, 0.16, 0.82), spire_m, 8)
        ico(0.018, (sx * 0.38, 0.16, 0.97), gold)
    # portico and banner
    for i in range(6):
        cy(0.016, 0.26, (-0.15 + i * 0.06, -0.06, 0.18), trim, 8)
    bx((0.36, 0.1, 0.04), (0, -0.04, 0.33), trim, bev=0)
    bx((0.1, 0.008, 0.3), (0, -0.0, 0.88), flat("flag" + team, team, 0.7), bev=0)
    bx((0.04, 0.01, 0.04), (0, -0.003, 0.95), flat("emblem", WHITE, 0.6), bev=0)
    for x in (-0.3, 0.0, 0.3):
        flagpole(x, -0.5, 0.55, team, 0.14, "#d0d4da")
    for sx in (-1, 1):
        bx((0.2, 0.18, 0.025), (sx * 0.28, -0.32, 0.0125), flat("lawn", "#5fa83a", 0.9), bev=0)
        tree(sx * 0.62, -0.18, 0.85)


def residence_dl7(team):
    pad(0.86, stone("#c9c6bf", 3.0), 0.015, 14, 0.0, 17)
    gl = facade("#33506b", GLASS, 0.05, 0.065, 0.8, 0.74, lit="#c8ecff", lit_p=0.3)
    tc = flat("crown" + team, team, 0.5)
    neon = team_neon(team)
    band = glow("band", "#a8e6ff", 1.6)
    # podium wings with roof gardens and a helipad
    for sx in (-1, 1):
        bx((0.32, 0.26, 0.17), (sx * 0.38, -0.02, 0.085), gl, bev=0.008)
        bx((0.34, 0.28, 0.025), (sx * 0.38, -0.02, 0.17), tc, bev=0.005)
    bx((0.26, 0.2, 0.02), (-0.38, -0.02, 0.19), flat("lawn", "#5fa83a", 0.9), bev=0)
    tree(-0.44, -0.06, 0.6)
    tree(-0.32, 0.02, 0.55)
    cy(0.1, 0.01, (0.38, -0.02, 0.19), flat("helipad", "#2e3138", 0.7), 16)
    bx((0.012, 0.08, 0.004), (0.355, -0.02, 0.196), flat("emblem", WHITE, 0.6), bev=0)
    bx((0.012, 0.08, 0.004), (0.405, -0.02, 0.196), flat("emblem", WHITE, 0.6), bev=0)
    bx((0.05, 0.012, 0.004), (0.38, -0.02, 0.196), flat("emblem", WHITE, 0.6), bev=0)
    # tower
    cy(0.26, 0.08, (0, 0.18, 0.04), flat("plinth", "#5d6470", 0.6), 12)
    cy(0.22, 1.36, (0, 0.18, 0.76), gl, 12)
    for z in (0.32, 0.56, 0.8, 1.04, 1.28):
        cy(0.226, 0.014, (0, 0.18, z), band, 12)
    for k in range(3):
        a = -math.pi / 2 + (k - 1) * 0.5
        bx((0.022, 0.022, 1.3), (math.cos(a) * 0.222, 0.18 + math.sin(a) * 0.222, 0.75), tc, a + math.pi / 2, bev=0)
    # council disc
    cy(0.2, 0.08, (0, 0.18, 1.48), gl, 12)
    cy(0.36, 0.1, (0, 0.18, 1.57), dark_glass(), 16, r2=0.32)
    cy(0.365, 0.022, (0, 0.18, 1.53), neon, 16)
    uvs(0.17, (0, 0.18, 1.62), flat("dome_glass", "#9fd4ef", 0.3), 12, 6, (1, 1, 0.55))
    cy(0.012, 0.36, (0, 0.18, 1.86), flat("mast", "#d0d4da", 0.5), 6)
    ico(0.02, (0, 0.18, 2.05), glow("beacon", "#ff4a3a", 4.0))
    for x in (-0.18, 0.0, 0.18):
        flagpole(x, -0.5, 0.5, team, 0.13, "#d0d4da")
    for (x, y) in ((-0.62, 0.3), (0.62, 0.3)):
        bx((0.08, 0.08, 0.04), (x, y, 0.02), flat("planter", "#7a7f88", 0.6), bev=0.006)
        tree(x, y, 0.75)


def residence_dl8(team):
    gl = dark_glass()
    neon = team_neon(team)
    cyan = glow("cyan", CYAN, 2.5)
    base = flat("plaza8", "#2e333c", 0.6)
    extrude(ngon(0.86, 12, math.pi / 12), -0.01, 0.06, base)
    for k in range(12):  # neon rim of the podium
        a0, a1 = math.pi / 12 + k * math.tau / 12, math.pi / 12 + (k + 1) * math.tau / 12
        beam((math.cos(a0) * 0.80, math.sin(a0) * 0.80, 0.062), (math.cos(a1) * 0.80, math.sin(a1) * 0.80, 0.062), 0.014, neon)
    extrude(ngon(0.52, 6, math.pi / 6), 0.06, 0.24, gl)
    hx = ngon(0.525, 6, math.pi / 6)
    for k in range(6):
        beam((*hx[k], 0.235), (*hx[(k + 1) % 6], 0.235), 0.016, neon)
    # main hexagonal tapered tower
    z0, h, r0, r1 = 0.24, 2.0, 0.3, 0.15
    cy(r0, h, (0, 0, z0 + h / 2), gl, 6, r2=r1, rot=(0, 0, math.pi / 6))
    for f in (0.2, 0.4, 0.6, 0.8, 0.98):
        r = r0 + (r1 - r0) * f
        cy(r + 0.01, 0.018, (0, 0, z0 + h * f), neon, 6, rot=(0, 0, math.pi / 6))
    # three buttress fins with neon edges
    for k in range(3):
        a = math.pi / 2 + k * math.tau / 3
        ca, sa = math.cos(a), math.sin(a)
        pts = [(0.24, 0.06), (0.62, 0.06), (0.62, 0.3), (0.24, 1.55)]
        fin = extrude([(p[0], p[1]) for p in pts], -0.03, 0.03, flat("fin", "#3d4654", 0.45))
        fin.rotation_euler = (math.pi / 2, 0, a)
        beam((ca * 0.625, sa * 0.625, 0.3), (ca * 0.245, sa * 0.245, 1.56), 0.018, neon)
    # crown: energy ring + spire
    torus(0.24, 0.022, (0, 0, z0 + h - 0.12), cyan, seg=16, mseg=4)
    cn(0.06, 0.5, (0, 0, z0 + h + 0.25), flat("spire", "#c9d0d8", 0.4), 6)
    ico(0.025, (0, 0, z0 + h + 0.52), neon)
    for sx in (-1, 1):  # satellite towers at the back
        def sat():
            cy(0.1, 0.72, (0, 0, 0.36 + 0.06), gl, 6, rot=(0, 0, math.pi / 6))
            cy(0.106, 0.016, (0, 0, 0.78), neon, 6, rot=(0, 0, math.pi / 6))
            cn(0.1, 0.12, (0, 0, 0.84), cyan, 6, rot=(0, 0, math.pi / 6))
        build_at(sat, sx * 0.5, 0.36)
    bx((0.3, 0.012, 0.12), (0, -0.48, 0.13), glow("holo" + team, shade(team, 1.35), 3.5), bev=0)
    for sx in (-1, 1):
        cy(0.008, 0.2, (sx * 0.16, -0.48, 0.1), flat("mast", "#d0d4da", 0.5), 6)


# ------------------------------------------------------------------ FORTIFICATIONS (team-neutral)

RC = 0.86  # corner radius of the fortification ring


def corner(k):
    a = math.pi / 3 * k
    return (RC * math.cos(a), RC * math.sin(a))


def edge_frame(p0, p1):
    L = math.dist(p0, p1)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    nl = math.hypot(mx, my)
    return L, ang, (mx, my), (mx / nl, my / nl)


def lerp2(p0, p1, f):
    return (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f)


def f1_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    wd = tex("wood", WOOD_D)
    wick = tex("wood", "#b08850", 4.0)
    for i in range(1, 5):
        x, y = lerp2(p0, p1, i / 5)
        cy(0.014, 0.22, (x, y, 0.11), wd, 6)
    bx((L - 0.05, 0.014, 0.15), (mid[0], mid[1], 0.095), tex("wood", "#8f6a3c", 5.0), ang, 0)
    for j, z in enumerate((0.04, 0.075, 0.11, 0.145)):
        off = 0.009 if j % 2 else -0.009
        bx((L - 0.06, 0.016, 0.03), (mid[0] + n[0] * off, mid[1] + n[1] * off, z), wick, ang, 0)
    # sharpened stakes leaning outwards
    for f in (0.3, 0.42, 0.58, 0.7):
        x, y = lerp2(p0, p1, f)
        rod((x + n[0] * 0.03, y + n[1] * 0.03, -0.01), (x + n[0] * 0.17, y + n[1] * 0.17, 0.19), 0.016, tex("wood", "#9a6a3c"), 0.002)


def f1_post(p):
    cy(0.022, 0.27, (p[0], p[1], 0.135), tex("wood", WOOD_D), 6)
    cn(0.022, 0.05, (p[0], p[1], 0.295), flat("stake_tip", "#d8b27a", 0.8), 6)


def f2_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    wd = tex("wood", "#9a6a3c", 3.0)
    tip = flat("stake_tip", "#d8b27a", 0.8)
    cnt = 11
    for i in range(1, cnt):
        x, y = lerp2(p0, p1, i / cnt)
        h = 0.3 + (0.03 if i % 2 else 0.0)
        cy(0.036, h, (x, y, h / 2), wd, 6)
        cn(0.036, 0.07, (x, y, h + 0.035), tip, 6)
    bx((L - 0.06, 0.035, 0.035), (mid[0] - n[0] * 0.04, mid[1] - n[1] * 0.04, 0.2), tex("wood", WOOD_D), ang, 0)


def f2_post(p):
    cy(0.055, 0.4, (p[0], p[1], 0.2), tex("wood", "#8a5e36", 3.0), 8)
    cn(0.055, 0.09, (p[0], p[1], 0.445), flat("stake_tip", "#d8b27a", 0.8), 8)
    bx((0.12, 0.12, 0.02), (p[0], p[1], 0.3), tex("wood", WOOD_D), math.atan2(p[1], p[0]), 0)


def f3_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    st = stone(STONE, 1.4)
    a, b = 0.07, L - 0.07
    segs = [(a, b)] if not gate else [(a, L / 2 - 0.11), (L / 2 + 0.11, b)]
    for (s0, s1) in segs:
        f = (s0 + s1) / 2 / L
        c = lerp2(p0, p1, f)
        bx((s1 - s0, 0.085, 0.26), (c[0], c[1], 0.13), st, ang, 0.008)
        bx((s1 - s0, 0.1, 0.05), (c[0], c[1], 0.025), stone(STONE_D), ang, 0.006)  # plinth
        bx((s1 - s0, 0.093, 0.016), (c[0], c[1], 0.2), stone(STONE_D), ang, 0)  # string course
        cnt = max(1, int((s1 - s0) / 0.085))
        for i in range(0, cnt, 2):
            g = (s0 + (i + 0.5) * (s1 - s0) / cnt) / L
            q = lerp2(p0, p1, g)
            bx(((s1 - s0) / cnt, 0.09, 0.06), (q[0], q[1], 0.29), st, ang, 0)
    if gate:
        for sx in (-1, 1):
            q = lerp2(p0, p1, 0.5 + sx * 0.13)
            bx((0.06, 0.13, 0.4), (q[0], q[1], 0.2), st, ang, 0.008)
        bx((0.32, 0.13, 0.08), (mid[0], mid[1], 0.38), st, ang, 0.008)
        for i in (-2, 0, 2):
            q = lerp2(p0, p1, 0.5 + i * 0.045)
            bx((0.04, 0.13, 0.05), (q[0], q[1], 0.445), st, ang, 0)
        for sx in (-1, 1):
            q = lerp2(p0, p1, 0.5 + sx * 0.045)
            bx((0.076, 0.02, 0.35), (q[0] + n[0] * 0.01, q[1] + n[1] * 0.01, 0.175), tex("wood", "#5a3a22"), ang, 0)
        for z in (0.07, 0.23):
            bx((0.16, 0.026, 0.018), (mid[0] + n[0] * 0.012, mid[1] + n[1] * 0.012, z), flat("iron", "#3b3d42", 0.6), ang, 0)


def f3_post(p):
    """Round stone tower: a dark plinth, two string courses, arrow slits, a merloned parapet, a slate cone with
    a gilt finial — enough shapes to read as masonry at map zoom."""
    st = stone(STONE, 1.4)
    dk = stone(STONE_D)
    cy(0.102, 0.06, (p[0], p[1], 0.03), dk, 10)  # plinth
    cy(0.09, 0.38, (p[0], p[1], 0.19), st, 10)
    for z in (0.14, 0.27):  # string courses
        cy(0.096, 0.016, (p[0], p[1], z), dk, 10)
    slit = flat("slit", "#1e1c1a", 0.9)
    for k in range(3):
        a = math.radians(-90 + (k - 1) * 60)
        bx((0.012, 0.012, 0.06), (p[0] + math.cos(a) * 0.088, p[1] + math.sin(a) * 0.088, 0.21), slit, a, 0)
    cy(0.105, 0.03, (p[0], p[1], 0.375), dk, 10)
    for k in range(8):  # merlons
        a = math.tau * k / 8
        bx((0.035, 0.03, 0.04), (p[0] + math.cos(a) * 0.092, p[1] + math.sin(a) * 0.092, 0.405), st, a, 0)
    cn(0.115, 0.2, (p[0], p[1], 0.5), flat("slate", SLATE, 0.6), 10)
    uvs(0.016, (p[0], p[1], 0.61), flat("finial", GOLD, 0.35), 6, 4)


def f4_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    st = stone("#a39b8d", 1.4)
    taper_box((L - 0.2, 0.17, 0.2), (mid[0], mid[1], 0.1), st, (1.0, 0.6), ang)
    bx((L - 0.2, 0.18, 0.03), (mid[0], mid[1], 0.015), stone(STONE_D), ang, 0.004)  # footing
    bx((L - 0.19, 0.145, 0.014), (mid[0], mid[1], 0.13), stone(STONE_D), ang, 0)  # cordon
    bx((L - 0.2, 0.03, 0.06), (mid[0] + n[0] * 0.035, mid[1] + n[1] * 0.035, 0.23), st, ang, 0)
    slit = flat("slit", "#1e1c1a", 0.9)
    cnt = max(2, int((L - 0.24) / 0.13))
    for i in range(cnt):  # embrasures in the parapet
        q = lerp2(p0, p1, 0.12 + (i + 0.5) * 0.76 / cnt)
        bx((0.03, 0.034, 0.03), (q[0] + n[0] * 0.035, q[1] + n[1] * 0.035, 0.245), slit, ang, 0)
    bx((L - 0.22, 0.07, 0.012), (mid[0] - n[0] * 0.015, mid[1] - n[1] * 0.015, 0.2), tex("wood", WOOD_L), ang, 0)
    bx((L - 0.24, 0.05, 0.01), (mid[0] - n[0] * 0.06, mid[1] - n[1] * 0.06, 0.2), flat("grassy", "#6f9a45", 0.9), ang, 0)  # turfed walk


def cannon(x, y, a, z=0.0):
    def b():
        wd = tex("wood", "#6a4327")
        bx((0.09, 0.06, 0.035), (0, 0, 0.04), wd, bev=0)
        for sy in (-1, 1):
            cy(0.03, 0.014, (-0.01, sy * 0.037, 0.03), wd, 8, rot=(math.pi / 2, 0, 0))
        o = cy(0.02, 0.15, (0.04, 0, 0.075), flat("iron", "#2e3034", 0.5), 8, r2=0.015)
        o.rotation_euler = (0, math.pi / 2 - 0.15, 0)
        for (cx, cy_) in ((-0.07, -0.03), (-0.07, 0.0), (-0.07, 0.03)):
            ico(0.014, (cx, cy_, 0.014), flat("iron", "#2e3034", 0.5))
    build_at(b, x, y, a, z=z)


def f4_post(p):
    a = math.atan2(p[1], p[0])
    pts = [(-0.14, -0.14), (0.02, -0.14), (0.12, 0.0), (0.02, 0.14), (-0.14, 0.14)]
    pr = [(p[0] + x * math.cos(a) - y * math.sin(a), p[1] + x * math.sin(a) + y * math.cos(a)) for x, y in pts]
    extrude(pr, 0.0, 0.24, stone("#a39b8d", 1.4))
    extrude([(p[0] + (x * 1.06) * math.cos(a) - (y * 1.06) * math.sin(a), p[1] + (x * 1.06) * math.sin(a) + (y * 1.06) * math.cos(a)) for x, y in pts],
            0.0, 0.035, stone(STONE_D))  # footing
    extrude([(p[0] + (x * 1.03) * math.cos(a) - (y * 1.03) * math.sin(a), p[1] + (x * 1.03) * math.sin(a) + (y * 1.03) * math.cos(a)) for x, y in pts],
            0.125, 0.14, stone(STONE_D))  # cordon
    extrude([(p[0] + (x * 0.85) * math.cos(a) - (y * 0.85) * math.sin(a), p[1] + (x * 0.85) * math.sin(a) + (y * 0.85) * math.cos(a)) for x, y in pts],
            0.24, 0.252, flat("grassy", "#6f9a45", 0.9))
    cannon(p[0] - math.cos(a) * 0.04, p[1] - math.sin(a) * 0.04, a, 0.252)


SANDBAG = "#b8a576"


def sandbags(qa, qb, off, n, courses=2, color=SANDBAG, f0=0.0, f1=1.0):
    """A staggered sandbag parapet from qa to qb, shifted by off along the normal n."""
    L = math.dist(qa, qb) * (f1 - f0)
    ang = math.atan2(qb[1] - qa[1], qb[0] - qa[0])
    bags = [flat("sand", color, 0.95), flat("sand2", shade(color, 0.86), 0.95)]
    k = max(2, int(L / 0.062))
    for c in range(courses):
        m = k - (c % 2)
        for i in range(m):
            f = f0 + (f1 - f0) * (i + 0.5 + 0.5 * (c % 2)) / k
            q = lerp2(qa, qb, f)
            bx((L / k * 0.94, 0.045, 0.026), (q[0] + n[0] * off, q[1] + n[1] * off, 0.014 + c * 0.025), bags[(i + c) % 2], ang, 0.009)


def sandbag_ring(x, y, r, courses=3, gap=0.9, color=SANDBAG):
    """A round sandbag nest open at the back (angle gap around +X of the local frame is left out)."""
    bags = [flat("sand", color, 0.95), flat("sand2", shade(color, 0.86), 0.95)]
    k = max(6, int(math.tau * r / 0.055))
    for c in range(courses):
        for i in range(k):
            a = (i + 0.5 * (c % 2)) / k * math.tau
            if abs(math.remainder(a - math.pi, math.tau)) < gap / 2:
                continue
            bx((math.tau * r / k * 0.95, 0.042, 0.026), (x + math.cos(a) * r, y + math.sin(a) * r, 0.014 + c * 0.025), bags[(i + c) % 2], a + math.pi / 2, 0.009)


def f5_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    cm = tex("plaster", "#b9b5ad", 2.0)
    rnd = random.Random(int((p0[0] + 3) * 100))
    for i in range(5):
        f = (i + 0.5) / 5
        q = lerp2(p0, p1, 0.06 + f * 0.88)
        taper_box((0.14, 0.09, 0.13), (q[0], q[1], 0.065), cm, (1.0, 0.45), ang + rnd.uniform(-0.12, 0.12), 0.006)
    steel = flat("wire", "#4c4f55", 0.5)
    for f in (0.1, 0.5, 0.9):
        q = lerp2(p0, p1, f)
        cy(0.007, 0.24, (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09, 0.12), steel, 5)
    for z in (0.1, 0.2):
        bx((L - 0.1, 0.006, 0.006), (mid[0] + n[0] * 0.09, mid[1] + n[1] * 0.09, z), steel, ang, 0)
    for i in range(6):
        q = lerp2(p0, p1, 0.1 + i * 0.8 / 5)
        torus(0.058, 0.006, (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09, 0.12), steel, (math.pi / 2, 0.25, ang + math.pi / 2), 7, 3)
    pk = tex("wood", WOOD_D, 3.0)
    for f in (0.3, 0.7):  # X-shaped wooden pickets that carry the wire
        q = lerp2(p0, p1, f)
        c_ = (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09)
        for s_ in (-1, 1):
            beam((c_[0] - n[0] * 0.05 * s_, c_[1] - n[1] * 0.05 * s_, 0.0), (c_[0] + n[0] * 0.05 * s_, c_[1] + n[1] * 0.05 * s_, 0.2), 0.012, pk)
    sandbags(p0, p1, -0.075, n, 2, f0=0.12, f1=0.88)


def f5_post(p):
    a = math.atan2(p[1], p[0])
    cm = tex("plaster", "#b9b5ad", 2.0)
    bx((0.15, 0.15, 0.13), (p[0], p[1], 0.065), cm, a, 0.008)
    bx((0.11, 0.11, 0.1), (p[0], p[1], 0.18), cm, a + 0.4, 0.008)
    bx((0.07, 0.008, 0.05), (p[0] + math.cos(a) * 0.08, p[1] + math.sin(a) * 0.08, 0.1), flat("warn", "#f2c230", 0.6), a + math.pi / 2, 0)

    def nest():  # machine-gun nest on the inner side: a sandbag ring and a water-cooled gun facing out
        sandbag_ring(0, 0, 0.075, 3)
        gm = flat("gun", "#33363b", 0.55)
        cy(0.016, 0.1, (-0.03, 0, 0.075), gm, 8, rot=(0, math.pi / 2, 0))
        cy(0.006, 0.07, (-0.11, 0, 0.075), gm, 6, rot=(0, math.pi / 2, 0))
        for k in range(3):
            q = k * math.tau / 3
            beam((0.0, 0.0, 0.07), (math.cos(q) * 0.04, math.sin(q) * 0.04, 0.0), 0.007, gm)
    build_at(nest, p[0] * 0.8, p[1] * 0.8, a + math.pi)


def hedgehog(x, y, rz):
    def b():
        m_ = flat("hedge", "#5b4a42", 0.6)
        for k in range(3):
            o = bx((0.15, 0.018, 0.018), (0, 0, 0.05), m_, bev=0)
            o.rotation_euler = (0, 0.62, k * math.tau / 3)
    build_at(b, x, y, rz)


def f6_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    taper_box((L - 0.24, 0.13, 0.06), (mid[0], mid[1], 0.03), tex("plaster", "#8a6e4b", 1.5), (1.0, 0.5), ang)
    taper_box((L - 0.28, 0.075, 0.012), (mid[0], mid[1], 0.064), tex("plaster", "#5f7a3a", 2.0), (1.0, 0.7), ang)
    # the trench on the inner side: a dark cut lined with a log revetment
    tr = (mid[0] - n[0] * 0.115, mid[1] - n[1] * 0.115)
    bx((L - 0.26, 0.06, 0.008), (tr[0], tr[1], 0.004), flat("trench", "#3a2c1e", 0.95), ang, 0)
    lg = tex("wood", "#7a5634", 3.0)
    for s_ in (-1, 1):
        cy(0.011, L - 0.26, (tr[0] + n[0] * 0.034 * s_, tr[1] + n[1] * 0.034 * s_, 0.014), lg, 6, rot=(0, math.pi / 2, ang))
    sandbags(p0, p1, -0.03, n, 1, "#9c936a", 0.2, 0.8)
    for f in (0.3, 0.5, 0.7):
        q = lerp2(p0, p1, f)
        hedgehog(q[0] + n[0] * 0.11, q[1] + n[1] * 0.11, ang + f * 2)


def f6_post(p):
    a = math.atan2(p[1], p[0])
    cm = tex("plaster", "#a9a59c", 2.0)
    cy(0.13, 0.13, (p[0], p[1], 0.065), cm, 6, r2=0.11, rot=(0, 0, a))
    cy(0.135, 0.03, (p[0], p[1], 0.145), cm, 6, rot=(0, 0, a))
    uvs(0.105, (p[0], p[1], 0.16), cm, 10, 5, (1, 1, 0.38))
    camo = [flat("camo1", "#5d6b3c", 0.85), flat("camo2", "#7a6a48", 0.85)]
    for k in range(5):
        q = a + k * 1.3 + 0.4
        ico(0.034, (p[0] + math.cos(q) * 0.1, p[1] + math.sin(q) * 0.1, 0.07 + (k % 2) * 0.04), camo[k % 2], (1.2, 1.2, 0.35))
    bx((0.022, 0.1, 0.025), (p[0] + math.cos(a) * 0.12, p[1] + math.sin(a) * 0.12, 0.09), flat("slit", "#15171a", 0.9), a, 0)
    # searchlight
    def sl():
        cy(0.012, 0.05, (0, 0, 0.025), flat("iron", "#3b3d42", 0.6), 6)
        cy(0.035, 0.06, (0.0, 0, 0.07), flat("lamp", "#5b636b", 0.5), 10, rot=(0, math.pi / 2 - 0.35, 0))
        cy(0.03, 0.01, (0.032, 0, 0.081), glow("lens", "#fff4c2", 5.0), 10, rot=(0, math.pi / 2 - 0.35, 0))
    build_at(sl, p[0], p[1], a, z=0.16)


def f7_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    sm = flat("steelwall", "#7f8995", 0.45)
    rib = flat("steelrib", "#5c6570", 0.45)
    bx((L - 0.16, 0.06, 0.34), (mid[0], mid[1], 0.17), sm, ang, 0.006)
    for i in range(5):
        q = lerp2(p0, p1, 0.18 + i * 0.64 / 4)
        bx((0.022, 0.075, 0.34), (q[0], q[1], 0.17), rib, ang, 0)
    bx((L - 0.16, 0.07, 0.03), (mid[0], mid[1], 0.355), flat("warn", "#f2c230", 0.6), ang, 0)
    bx((L - 0.16, 0.07, 0.02), (mid[0], mid[1], 0.03), rib, ang, 0)


def f7_post(p):
    a = math.atan2(p[1], p[0])
    dm = flat("steelrib", "#5c6570", 0.45)
    cy(0.1, 0.42, (p[0], p[1], 0.21), flat("steelwall", "#7f8995", 0.45), 8, rot=(0, 0, a))
    cy(0.105, 0.03, (p[0], p[1], 0.405), flat("warn", "#f2c230", 0.6), 8)

    def head():
        cy(0.065, 0.04, (0, 0, 0.02), dm, 10)
        bx((0.13, 0.1, 0.07), (0.01, 0, 0.075), flat("steelwall", "#7f8995", 0.45), bev=0.008)
        for sy in (-1, 1):
            cy(0.012, 0.11, (0.1, sy * 0.025, 0.08), dm, 6, rot=(0, math.pi / 2, 0))
        bx((0.012, 0.04, 0.02), (0.075, 0, 0.1), glow("sensor", "#ff4a3a", 4.0), bev=0)
    build_at(head, p[0], p[1], a + math.pi / 6, z=0.42)


def f8_edge(p0, p1, gate=False):
    L, ang, mid, n = edge_frame(p0, p1)
    comp = flat("composite", "#e3e8ee", 0.4)
    trim = flat("comptrim", "#4a515c", 0.5)
    cyan = glow("cyan", CYAN, 2.5)
    bx((L - 0.08, 0.07, 0.14), (mid[0], mid[1], 0.07), comp, ang, 0.008)
    bx((L - 0.08, 0.075, 0.025), (mid[0], mid[1], 0.03), trim, ang, 0)
    bx((L - 0.08, 0.075, 0.012), (mid[0], mid[1], 0.1), cyan, ang, 0)
    # mid pylon
    bx((0.06, 0.08, 0.46), (mid[0], mid[1], 0.23), comp, ang, 0.008)
    bx((0.062, 0.03, 0.4), (mid[0] + n[0] * 0.03, mid[1] + n[1] * 0.03, 0.24), trim, ang, 0)
    bx((0.014, 0.034, 0.36), (mid[0] + n[0] * 0.034, mid[1] + n[1] * 0.034, 0.24), cyan, ang, 0)
    # energy mesh: lattice of glowing bars between the pylons
    for (fa, fb) in ((0.06, 0.47), (0.53, 0.94)):
        qa, qb = lerp2(p0, p1, fa), lerp2(p0, p1, fb)
        for z in (0.24, 0.34, 0.44):
            beam((qa[0], qa[1], z), (qb[0], qb[1], z), 0.009, cyan)
        beam((qa[0], qa[1], 0.15), (qb[0], qb[1], 0.44), 0.008, cyan)
        qm = lerp2(p0, p1, (fa + fb) / 2)
        bx((math.dist(qa, qb), 0.006, 0.28), (qm[0], qm[1], 0.295), glow("curtain", "#1a8fd0", 0.7), ang, 0)
        beam((qa[0], qa[1], 0.44), (qb[0], qb[1], 0.15), 0.008, cyan)


def f8_post(p):
    a = math.atan2(p[1], p[0])
    comp = flat("composite", "#e3e8ee", 0.4)
    trim = flat("comptrim", "#4a515c", 0.5)
    cyan = glow("cyan", CYAN, 2.5)
    cy(0.075, 0.08, (p[0], p[1], 0.04), trim, 6, rot=(0, 0, a))
    bx((0.09, 0.09, 0.52), (p[0], p[1], 0.3), comp, a, 0.01)
    bx((0.016, 0.094, 0.44), (p[0], p[1], 0.3), cyan, a, 0)
    bx((0.094, 0.016, 0.44), (p[0], p[1], 0.3), cyan, a, 0)
    cy(0.06, 0.04, (p[0], p[1], 0.58), trim, 6, rot=(0, 0, a))
    ico(0.04, (p[0], p[1], 0.63), cyan)


FORTS = {
    1: (f1_edge, f1_post),
    2: (f2_edge, f2_post),
    3: (f3_edge, f3_post),
    4: (f4_edge, f4_post),
    5: (f5_edge, f5_post),
    6: (f6_edge, f6_post),
    7: (f7_edge, f7_post),
    8: (f8_edge, f8_post),
}


def fort_ring(level):
    edge, post = FORTS[level]
    for k in range(6):
        edge(corner(k), corner(k + 1), gate=(level == 3 and k == 4))
    for k in range(6):
        post(corner(k))


def fort_edge(level):
    """One wall section on the back (+Y, Godot −Z) edge between corners 60° and 120°. Rotate by k·60° about Y."""
    FORTS[level][0](corner(1), corner(2))


def fort_post(level):
    """Corner feature at the corner on +X (angle 0). Rotate by k·60° about Y."""
    FORTS[level][1](corner(0))


# ------------------------------------------------------------------ export

def homestead(team):
    """A farmstead on an owned open hex (the settled countryside of the reference frames): a stone cottage under a
    tiled roof in the owner's colour with a smoking chimney, a fenced vegetable patch, a haystack and a woodpile."""
    build_at(lambda: stone_house(0.22, 0.17, 0.15, team, "#c9c0ae", smoke=True), 0.0, 0.05, 0.15)
    build_at(lambda: garden(0.2, 0.13, 3), -0.02, -0.22, 0.15)
    haystack(0.2, -0.06, 0.7)
    build_at(lambda: woodpile(2), 0.27, 0.16, 1.4, 0.7)


def homestead_modern(team):
    """DL6–7 countryside: a two-storey panel house with a flat roof, a fenced lot with greenhouse rows, a car."""
    build_at(lambda: panel_block(0.24, 0.18, 2, team), 0.0, 0.06, 0.15)
    gh = flat("greenhouse", "#cfe6ee", 0.2)
    for i in range(2):
        build_at(lambda: (bx((0.2, 0.06, 0.05), (0, 0, 0.025), gh, bev=0.01)), -0.04, -0.17 - i * 0.09, 0.15)
    bx((0.09, 0.05, 0.04), (0.22, -0.02, 0.03), flat("car" + team, slate(team, 1.1), 0.4), 0.3, 0.012)


def homestead_scifi(team):
    """DL8 countryside: a dark-glass habitat pod with team neon edges, a landing pad with a glowing ring and a
    crate of raivite crystals."""
    gl = dark_glass()
    build_at(lambda: neon_box(0.2, 0.16, 0.0, 0.16, team, gl), 0.0, 0.08, 0.15)
    uvs(0.09, (0.0, 0.08, 0.17), flat("dome", "#a9d6f0", 0.15), 12, 6, (1, 1, 0.5))
    cy(0.11, 0.015, (0.02, -0.2, 0.008), flat("pad", "#4a515c", 0.5), 16)
    torus(0.095, 0.006, (0.02, -0.2, 0.018), team_neon(team))
    bx((0.07, 0.07, 0.05), (0.22, -0.04, 0.025), flat("crate", "#3e4550", 0.5), 0.4, 0.006)
    for k in range(3):
        cn(0.012, 0.05, (0.2 + k * 0.018, -0.04, 0.07), glow("raivite_c", CYAN, 2.0), 6)


def farm_modern(team):
    """DL6–7 farm: ploughed strips of crops, a tall grain silo with a team band, a barn and a red tractor."""
    pad(0.7, tex("plaster", "#6b5032", 2.0), 0.01, 12, 0.05, 31)
    crops = [flat("crop_a", "#d9b84a", 0.8), flat("crop_b", "#6f9a3a", 0.8)]
    for i in range(5):
        bx((0.62, 0.09, 0.03), (-0.1, -0.32 + i * 0.12, 0.02), crops[i % 2], 0.0, 0.01)
    cy(0.09, 0.5, (0.36, 0.3, 0.25), flat("silo", "#c9ced4", 0.4), 16)
    uvs(0.09, (0.36, 0.3, 0.5), flat("silo", "#c9ced4", 0.4), 12, 6, (1, 1, 0.6))
    cy(0.093, 0.04, (0.36, 0.3, 0.38), flat("band" + team, slate(team, 1.2), 0.5), 16)
    build_at(lambda: barn(team), 0.42, -0.02, 1.57, 0.8)
    trc = flat("tractor", "#c0392b", 0.5)
    bx((0.09, 0.05, 0.05), (-0.42, 0.3, 0.05), trc, 0.3, 0.01)
    for (dx, r) in ((-0.035, 0.03), (0.035, 0.02)):
        for sy in (-1, 1):
            cy(r, 0.015, (-0.42 + dx, 0.3 + sy * 0.032, r), flat("tyre", "#1f1f21", 0.9), 10, rot=(math.pi / 2, 0, 0.3))


def farm_scifi(team):
    """DL8 farm: hydroponic domes over glowing green beds, a water tank, a harvester drone pad."""
    pad(0.72, flat("plate", "#4a515c", 0.6), 0.012, 12, 0.0, 32)
    leaf = glow("hydro", "#5cff8a", 1.2)
    glass = flat("dome_glass", "#a9d6f0", 0.12)
    rib = flat("rib", "#d8dee6", 0.4)
    for (x, y) in ((-0.3, 0.2), (0.0, 0.25), (0.3, 0.2), (-0.15, -0.1), (0.15, -0.1)):
        def bed():
            bx((0.22, 0.14, 0.02), (0, 0, 0.02), leaf, 0, 0.004)
            for k in range(4):  # greenhouse ribs arching over the glowing bed
                torus(0.075, 0.005, (-0.08 + k * 0.053, 0, 0.02), rib, (0, 0, math.pi / 2), 12, 3)
            bx((0.2, 0.006, 0.006), (0, 0, 0.095), rib, 0, 0)
            frame(0.23, 0.15, 0.025, team_neon(team))
        build_at(bed, x, y)
    cy(0.07, 0.24, (0.36, -0.3, 0.12), flat("tank", "#c9ced4", 0.35), 16)
    cy(0.072, 0.02, (0.36, -0.3, 0.2), team_neon(team), 16)
    cy(0.08, 0.012, (-0.3, -0.32, 0.006), flat("pad", "#2c323b", 0.5), 16)
    torus(0.07, 0.005, (-0.3, -0.32, 0.014), team_neon(team))


def mine_scifi(team):
    """DL8 mine: an open pit of glowing raivite crystals under an extractor gantry, crates of crystals."""
    pad(0.7, flat("plate", "#4a515c", 0.6), 0.012, 12, 0.0, 33)
    cy(0.32, 0.03, (0, 0.05, 0.015), flat("pit", "#232830", 0.8), 20)
    cr = glow("crystal", "#3f9bff", 2.2)
    cr2 = glow("crystal2", "#7fc0ff", 2.8)
    rnd = random.Random(7)
    for k in range(16):
        a = rnd.uniform(0, math.tau)
        rr = rnd.uniform(0.0, 0.24)
        h = rnd.uniform(0.16, 0.34)
        o = cn(0.055, h, (math.cos(a) * rr, 0.05 + math.sin(a) * rr, 0.03 + h / 2), cr if k % 2 else cr2, 6)
        o.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)
    st = flat("gantry", "#5d6470", 0.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.022, 0.46, (sx * 0.3, 0.05 + sy * 0.3, 0.23), st, 8)
    for sy in (-1, 1):
        bx((0.64, 0.045, 0.05), (0, 0.05 + sy * 0.3, 0.46), st, 0, 0.004)
    bx((0.06, 0.64, 0.05), (0.05, 0.05, 0.47), st, 0, 0.004)
    bx((0.14, 0.14, 0.1), (0.05, 0.05, 0.4), flat("extractor", "#e3e8ee", 0.4), 0, 0.01)
    cy(0.02, 0.18, (0.05, 0.05, 0.22), team_neon(team), 8)
    for k in range(2):
        bx((0.08, 0.08, 0.06), (0.38, -0.3 + k * 0.1, 0.03), flat("crate", "#3e4550", 0.5), 0.2, 0.006)


CITY = [city_dl1, city_dl2, city_dl3, city_dl4, city_dl5, city_dl6, city_dl7, city_dl8]
RES = [residence_dl1, residence_dl2, residence_dl3, residence_dl4, residence_dl5, residence_dl6, residence_dl7, residence_dl8]

ASSETS = {}
for _t, _c in TEAMS.items():
    ASSETS[f"homestead_{_t}"] = (lambda c: (lambda: homestead(c)))(_c)
    ASSETS[f"homestead_modern_{_t}"] = (lambda c: (lambda: homestead_modern(c)))(_c)
    ASSETS[f"homestead_scifi_{_t}"] = (lambda c: (lambda: homestead_scifi(c)))(_c)
    ASSETS[f"farm_modern_{_t}"] = (lambda c: (lambda: farm_modern(c)))(_c)
    ASSETS[f"farm_scifi_{_t}"] = (lambda c: (lambda: farm_scifi(c)))(_c)
    ASSETS[f"mine_scifi_{_t}"] = (lambda c: (lambda: mine_scifi(c)))(_c)
for _n in range(1, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"city_dl{_n}_{_t}"] = (lambda f, c: (lambda: f(c)))(CITY[_n - 1], _c)
        ASSETS[f"residence_dl{_n}_{_t}"] = (lambda f, c: (lambda: f(c)))(RES[_n - 1], _c)
for _n in range(1, 9):
    ASSETS[f"fort_l{_n}"] = (lambda n: (lambda: fort_ring(n)))(_n)
    ASSETS[f"fort_l{_n}_edge"] = (lambda n: (lambda: fort_edge(n)))(_n)
    ASSETS[f"fort_l{_n}_post"] = (lambda n: (lambda: fort_post(n)))(_n)


def lowpoly(objs):
    """Mobile budget: one-segment chamfers, no bevel on tiny parts, smooth-by-angle shading."""
    plain = []
    for o in objs:
        dims = min(o.dimensions) if o.dimensions else 0
        bevels = [md for md in o.modifiers if md.type == "BEVEL"]
        for md in bevels:
            md.segments = 1
            if dims < 0.03 or md.width < 0.004:
                for x in list(o.modifiers):
                    o.modifiers.remove(x)
                break
            md.width = min(md.width, dims * 0.2)
        if not any(md.type == "BEVEL" for md in o.modifiers):
            plain.append(o)
    if plain:
        bpy.ops.object.select_all(action="DESELECT")
        for o in plain:
            o.select_set(True)
        bpy.context.view_layer.objects.active = plain[0]
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(50))


def export(name, out):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    lowpoly(objs)
    smokes = [o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.name.startswith(("smoke", "flag"))]
    ob = ea.bake_asset(objs, 512)
    ob.name = name
    ob.data.calc_loop_triangles()
    tris = len(ob.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    for o in smokes:  # chimney markers travel with the model as plain nodes
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
    rad = max(math.hypot(w.x, w.y) for w in ws)
    mats = [m_.name for m_ in ob.data.materials]
    print(f"EXPORTED {name}: tris={tris} radius={rad:.2f} zmin={min(w.z for w in ws):.2f} height={max(w.z for w in ws):.2f} mats={mats}", flush=True)
    return tris


# ------------------------------------------------------------------ contact sheet


def contact_sheet(model_dir, png, team="blue", only_rows=None, cols=None):
    """Rows: forts l1..l8 (front), city blocks dl1..dl8, residences dl1..dl8 (back), each on a grass hex."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    rows = [("fort_l{n}", 0.0), ("city_dl{n}_" + team, 3.0), ("residence_dl{n}_" + team, 6.4)]
    if only_rows:
        rows = [(p_, i * 3.2) for i, (p_, _) in enumerate(r for r in rows if r[0].split("_")[0] in only_rows)]
    cols = cols or list(range(1, 9))
    sp = 2.25
    for pattern, y in rows:
        for ci, n in enumerate(cols):
            x = (ci - (len(cols) - 1) / 2) * sp
            kit.hex_prism("tile", (x, y, 0), 1.0, 0.18, grass, dirt, 0.03)
            before = {o.name for o in bpy.context.scene.objects}
            bpy.ops.import_scene.gltf(filepath=os.path.join(model_dir, pattern.format(n=n) + ".glb"))
            for o in bpy.context.scene.objects:
                if o.name not in before and o.parent is None:
                    o.location.x += x
                    o.location.y += y
    world = bpy.data.worlds.new("w")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*kit.srgb("#8fa3b5"), 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.data.energy = 3.5
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(42), math.radians(-12), math.radians(-35))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = len(cols) * sp + 1.0
    el = math.radians(45)
    cy_ = max(y for _, y in rows) / 2 + 0.2
    cam.location = (0, cy_ - 30 * math.cos(el), 0.35 + 30 * math.sin(el))
    cam.rotation_euler = (math.pi / 2 - el, 0, 0)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x = 2400
    span = (max(y for _, y in rows) + 2.0) * math.sin(el) + 2.8 * math.cos(el)
    sc.render.resolution_y = int(min(1600, 2400 * (span + 0.4) / cam.data.ortho_scale))
    sc.view_settings.view_transform = "AgX"
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    print("SHEET", png)


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0] if args else "game/assets/models"
    rest = args[1:]
    if "--sheet" in rest:
        i = rest.index("--sheet")
        png = rest[i + 1]
        team = rest[rest.index("--team") + 1] if "--team" in rest else "blue"
        only_rows = rest[rest.index("--rows") + 1].split(",") if "--rows" in rest else None
        cols = [int(c) for c in rest[rest.index("--cols") + 1].split(",")] if "--cols" in rest else None
        contact_sheet(out, png, team, only_rows, cols)
        sys.exit(0)
    os.makedirs(out, exist_ok=True)
    only = set(rest)
    report = {}
    for name, build in ASSETS.items():
        if only and name not in only:
            continue
        ea.reset()
        build()
        report[name] = export(name, out)
    print("TRIS", report)
