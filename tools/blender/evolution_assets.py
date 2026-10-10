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

# «Raivon Soft» team colours on the models (art direction §6.3): a sky blue, a warm red and a fresh green, lighter and
# less neon than the old #2673ff / #e6261a / #40a64d; troops and props import TEAMS, so their re-exports follow
TEAMS = {"blue": "#3F86F0", "red": "#DD3A30", "green": "#4CB050"}

WOOD = "#7d5130"
WOOD_L = "#a8743f"
WOOD_D = "#5a3a22"
LOG = "#a06c3c"
THATCH = "#d8b25c"
DAUB = "#c7a77a"
STONE = "#D3C8B4"  # warm light building stone (§6.3), was the cooler grey #bdbab2
STONE_D = "#A39A8C"  # its shade (was #86837c): a darker stone, never a near-black one
WSTONE, WSTONE_D = "#c6b6a0", "#8e8070"  # the warm sandstone of reference frame 4's castle
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
    """Stone blocks laid in world space (rows stay horizontal on walls at any angle).

    «Raivon Soft» (§6.5): blocks twice as big (scale 11 -> 5.5) and a faint seam: mortar 0.9 of the stone in sRGB
    (≈ 0.8 in linear light, as kit.textured's 0.82), was 0.72 — a soft painted course, no dark grid at map distance."""
    return facade(color, color, wf=0.0, brick=True, brick_scale=5.5 * scale, mortar_k=0.9)


def glow(name, color, strength=3.0):
    return mat("glow_" + name, color, 0.4, 0.0, emission=color, emit_strength=strength)


def win_lit():
    return mat("win_lit", "#ffcf6b", 0.5, emission="#ffb84a", emit_strength=1.5)


def _sock(node, ident, out=False):
    return next(s for s in (node.outputs if out else node.inputs) if s.identifier == ident)


def facade(wall, win, col=0.07, floor=0.1, wf=0.5, hf=0.55, lit="#ffd27a", lit_p=0.22, brick=False, z0=0.0,
           brick_scale=15.0, mortar_k=1.35, pil=0, pil_c=None):
    """Wall with a grid of windows on every vertical face (world-space, so floors line up with Z=0).

    Baked into the texture like every procedural material: cheap windows without extra geometry.
    pil > 0: a pale pilaster (pil_c) between the windows at every pil-th column.
    """
    key = ("facade", wall, win, col, floor, wf, hf, lit, lit_p, brick, z0, brick_scale, mortar_k, pil, pil_c)
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
    out = mix(mask, wallc, wincol)
    if pil:
        g = mth("FRACT", mth("DIVIDE", u, col * pil))
        hw = (1 - wf) / 2 * 0.75 / pil
        pm = mth("MULTIPLY", mth("ADD", mth("LESS_THAN", g, hw), mth("GREATER_THAN", g, 1 - hw)), vert)
        out = mix(pm, out, pil_c or shade(wall, 1.5))
    L.new(out, bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    kit._MATS[key] = m
    return m


# ------------------------------------------------------------------ primitives


# «Raivon Soft» (art direction §6.2): only the few largest masses of a model get a round 3-segment bevel ("soft
# boxes"); everything else keeps lowpoly()'s one-segment chamfer. The bevel is min(SOFT_W, 0.08 × the smallest side).
SOFT_W = 0.015
SOFT_MIN = 0.08  # a soft mass keeps its 3 segments only when its smallest side is at least this (lowpoly)
SOFT_MAX = 6  # at most this many soft masses per model keep 3 segments (the largest by volume; lowpoly)


def _soften(o, mode):
    """Make o a soft mass (art direction §6.2): its BEVEL becomes round (3 segments, profile 0.5) and only bevels the
    edges that show, picked by edge bevel weights; the other edges are marked sharp so the WEIGHTED_NORMAL after the
    bevel (keep sharp) keeps the big faces flat and only the bevel strips shade round. Tags o["soft"] for lowpoly().
    mode "v": the vertical edges only (walls whose top is under a roof, cornice or parapet, and whose foot stands on
    the ground or a plinth); True: the vertical and the top edges of a box, the top rim of a cylinder (the bottom
    edges never show: the camera and the sun are always above, and the feet stand on something)."""
    me = o.data
    if len(me.vertices) == 8:  # a box: its underside stands on the ground, a plinth or a lower storey — left out
        bm = bmesh.new()
        bm.from_mesh(me)
        zb = min(v.co.z for v in bm.verts)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(abs(v.co.z - zb) < 1e-6 for v in f.verts)],
                         context="FACES_ONLY")
        bm.to_mesh(me)
        bm.free()
    bw = me.attributes.get("bevel_weight_edge") or me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
    sh = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    for e in me.edges:
        a, b = (me.vertices[i].co for i in e.vertices)
        vert = abs(a.x - b.x) < 1e-6 and abs(a.y - b.y) < 1e-6
        top = abs(a.z - z1) < 1e-6 and abs(b.z - z1) < 1e-6
        side = vert and len(me.vertices) > 8  # a cylinder's side edge: smooth, neither bevelled nor sharp
        on = top if len(me.vertices) > 8 else (vert or (top and mode != "v"))
        bw.data[e.index].value = 1.0 if on else 0.0
        sh.data[e.index].value = not on and not side
    for md in o.modifiers:
        if md.type == "BEVEL":
            md.limit_method = "WEIGHT"
            md.segments = 3
            md.profile = 0.5
        elif md.type == "WEIGHTED_NORMAL":
            md.keep_sharp = True
    o["soft"] = True
    return o


def bx(size, loc, mt, rz=0.0, bev=0.012, rot=None, soft=False):
    """Box; soft=True / "v": a soft mass (see _soften) with a round bevel of min(SOFT_W, 0.08 × its smallest side)."""
    if soft:
        bev = min(SOFT_W, 0.08 * min(size))
    o = kit.box("b", size, loc, mt, bev)
    if soft:
        _soften(o, soft)
    if rot:
        o.rotation_euler = rot
    elif rz:
        o.rotation_euler.z = rz
    return o


def cy(r, h, loc, mt, n=8, bev=0.0, r2=None, rot=None, soft=False):
    """Cylinder (or frustum with r2); soft=True: a soft mass with a round bevel on its top rim (see _soften)."""
    if soft:
        bev = min(SOFT_W, 0.08 * min(2 * r, h))
    o = kit.cyl("c", r, h, loc, mt, n, bev, r2)
    if soft:
        _soften(o, soft)
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


# ridge caps, hip lines and eave boards keep a small roof readable at game size. «Raivon Soft» (§6.3): a deep shade of
# the roof itself where the roof colour is known, else warm timber — never the old near-black #3e2f25
ROOF_TRIM = "#6B4A30"
TRIM_K = 0.62
TRIM_AUTO = "auto"  # gable_roof's default ridge / barge boards: derived from the roof colour
# «Raivon Soft» roof trim (§6.8, plan step B1): a round ridge roll (a smooth 12-sided cylinder, r ≤ RIDGE_R) and round
# hip rolls in roof × RIDGE_K instead of the dark ridge-cap boxes; eave and barge boards in roof × EAVE_K, and eave
# boards thinner than EAVE_MIN are left out (a hair line at map distance)
RIDGE_R = 0.018
RIDGE_K = 0.75
EAVE_K = 0.7
EAVE_MIN = 0.02
ROLL_RISE = 0.009  # how far a gable roof's barge roll stands over its course butts (gable_roof)


def roof_trim(roof_c=None, k=TRIM_K):
    """The trim colour of a roof of colour roof_c (an sRGB hex): roof × k, or ROOF_TRIM when the roof colour is
    unknown."""
    return shade(roof_c, k) if isinstance(roof_c, str) and roof_c.startswith("#") else ROOF_TRIM


def _mat_color(mt):
    """The sRGB hex a kit material was made from (kit.mat, kit.textured or facade), or None."""
    for key, m_ in kit._MATS.items():
        if m_ is not mt or not isinstance(key, tuple) or len(key) < 2:
            continue
        c = key[2] if key[0] == "tex" else key[1]
        return c if isinstance(c, str) and c.startswith("#") else None
    return None


def _rt(p, loc, rz):
    """Local roof point -> world (rotated by rz about Z, then moved to loc)."""
    c, s_ = math.cos(rz), math.sin(rz)
    return (loc[0] + p[0] * c - p[1] * s_, loc[1] + p[0] * s_ + p[1] * c, loc[2] + p[2])


def ridge_r(span):
    """Radius of the ridge roll of a roof spanning `span` (its smaller side): RIDGE_R, thinner on a small roof."""
    return min(RIDGE_R, 0.1 * span)


def _round_trim(loc, rz, roof_c, span, ridges=(), hips=(), eaves=(), eave_t=0.0):
    """The soft roof trim (local roof points, see _rt): round ridge rolls of ridge_r(span) with 12 sides and hip
    rolls of 0.75 of that with 6 sides in roof × RIDGE_K (rolls thinner than 0.006 are left out); eave boards eave_t
    thick in roof × EAVE_K, left out when thinner than EAVE_MIN."""
    r = ridge_r(span)
    if r >= 0.006 and (ridges or hips):
        rm = flat("ridge", roof_trim(roof_c, RIDGE_K), 0.8)
        for p0, p1 in ridges:
            rod(_rt(p0, loc, rz), _rt(p1, loc, rz), r, rm, n=12)
        for p0, p1 in hips:
            rod(_rt(p0, loc, rz), _rt(p1, loc, rz), r * 0.75, rm, n=6)["round"] = True  # (shaded round: lowpoly)
    if eave_t >= EAVE_MIN and eaves:
        em = flat("eave", roof_trim(roof_c, EAVE_K), 0.8)
        for p0, p1 in eaves:
            beam(_rt(p0, loc, rz), _rt(p1, loc, rz), eave_t, em)


def prism_roof(name, w, d, h, loc, material, overhang=0.08, rot_z=0.0):
    """Gable roof (kit.prism_roof) with a round ridge roll and (when thick enough) eave boards."""
    o = kit.prism_roof(name, w, d, h, loc, material, overhang, rot_z)
    L, D = w / 2 + overhang, d / 2 + overhang
    t = max(0.008, 0.05 * min(w, d))
    _round_trim(loc, rot_z, _mat_color(material), min(w, d), ridges=[((-L, 0, h + t * 0.2), (L, 0, h + t * 0.2))],
                eaves=[((-L, -D, t * 0.3), (L, -D, t * 0.3)), ((-L, D, t * 0.3), (L, D, t * 0.3))], eave_t=t)
    return o


def _hip_lines(w, d, h, oh):
    """The ridge, hip and eave lines of a hip roof (local points): ([ridge], [4 hips], [4 eaves])."""
    W, D = w / 2 + oh, d / 2 + oh
    rl = abs(w - d) / 2
    if rl < 1e-4:
        tops = [(0, 0, h)] * 4
        ridges = []
    elif w > d:
        tops = [(-rl, 0, h), (rl, 0, h), (rl, 0, h), (-rl, 0, h)]
        ridges = [((-rl, 0, h), (rl, 0, h))]
    else:
        tops = [(0, -rl, h), (0, -rl, h), (0, rl, h), (0, rl, h)]
        ridges = [((0, -rl, h), (0, rl, h))]
    corners = [(-W, -D, 0), (W, -D, 0), (W, D, 0), (-W, D, 0)]
    return ridges, [(corners[i], tops[i]) for i in range(4)], [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


def hip_roof(w, d, h, loc, mt, oh=0.03, rz=0.0):
    """Hip roof (or a pyramid / tent roof when w == d), base at loc.z; round ridge and hip rolls, eave boards when
    thick enough."""
    o = _hip_roof(w, d, h, loc, mt, oh, rz)
    ridges, hips, eaves = _hip_lines(w, d, h, oh)
    _round_trim(loc, rz, _mat_color(mt), min(w, d), ridges, hips, eaves, max(0.007, 0.045 * min(w, d)))
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


def facade_banner(x, y, z_top, w, h, team, rz=0.0, rod_c="#d9d2c3"):
    """A long banner hanging down a facade that faces −Y (rotated by rz): a rod on top, the cloth in the team colour
    with a white emblem, and a cloth marker so the game paints the state's flag on it (reference frames 4 and 5)."""
    def b():
        bx((w + 0.02, 0.012, 0.012), (0, 0, z_top), flat("pole", rod_c, 0.5), bev=0)
        bx((w, 0.008, h), (0, -0.004, z_top - 0.006 - h / 2), flat("flag" + team, team, 0.7), bev=0)
        bx((w * 0.45, 0.011, w * 0.45), (0, -0.006, z_top - h * 0.35), flat("emblem", WHITE, 0.6), bev=0)
        flag_at("flagt", 0, -0.004, z_top - 0.006 - h / 2, w + 0.004, h + 0.004, 0.014)
    build_at(b, x, y, rz)


def flagpole(x, y, h, team, w=0.15, pole="#d9d2c3"):
    cy(0.009, h, (x, y, h / 2), flat("pole", pole, 0.5), 6)
    bx((w, 0.008, w * 0.64), (x + w / 2 + 0.006, y, h - w * 0.34), flat("flag" + team, team, 0.7), bev=0)
    bx((w * 0.36, 0.011, w * 0.3), (x + w / 2 + 0.006, y, h - w * 0.3), flat("emblem", WHITE, 0.6), bev=0)
    flag_at("flagw", x + w / 2 + 0.006, y, h - w * 0.34, w + 0.004, w * 0.64 + 0.004)
    ico(0.016, (x, y, h + 0.01), flat("gold", GOLD, 0.35))


BANNER_K = 1.3  # «Raivon Soft» (plan step B2): the capitals' eagle banners are 1.3× wider (and so longer)


def banner(x, y, h, team, w=0.17, side=1, z0=0.0):
    """Hanging war banner (crossbar, long cloth with white emblem) — the capital's marker. «Raivon Soft»: the cloth
    is BANNER_K wider than w, 0.012 thick, on a stout pole (no part thinner than 0.018). side −1 hangs the cloth to
    the left of the pole (−X); z0: where the pole starts (on a roof)."""
    w *= BANNER_K
    cx = x + side * w / 2
    pm = flat("pole", "#d9d2c3", 0.5)
    cy(0.012, h - z0, (x, y, (h + z0) / 2), pm, 6)
    cy(0.009, w + 0.04, (cx, y, h - 0.02), pm, 6, rot=(0, math.pi / 2, 0))
    bx((w, 0.012, w * 1.5), (cx, y, h - 0.03 - w * 0.75), flat("flag" + team, team, 0.7), bev=0)
    bx((w * 0.42, 0.015, w * 0.42), (cx, y, h - 0.03 - w * 0.6), flat("emblem", WHITE, 0.6), bev=0)
    flag_at("flagt", cx, y, h - 0.03 - w * 0.75, w + 0.004, w * 1.5 + 0.004, 0.019)
    ico(0.026, (x, y, h + 0.018), flat("gold", GOLD, 0.35))


# «Raivon Soft» (§6.2, plan step B1): windows and doors are bigger than life (×1.3) and their frames lighter — a soft
# shade of the wall (wall × FRAME_K) instead of dark timber, so a facade reads as a few big warm openings, not a
# grid of dark outlines
WIN_K = 1.3
FRAME_K = 0.8
WIN_MAX = 3  # windows per row on one face (front_windows)


def frame_c(frame, wall=None):
    """The frame colour of a window or door: a light frame (white carving, pale stone) stays; otherwise the wall
    colour × FRAME_K when the wall is known, else the given frame lightened by 30 % (no near-black outlines)."""
    if not frame:
        return frame
    h_ = frame.lstrip("#")
    if sum(int(h_[i:i + 2], 16) for i in (0, 2, 4)) / 3 > 200:
        return frame
    return shade(wall, FRAME_K) if wall else shade(frame, 1.3)


def window(x, y, z, rz, w=0.045, h=0.05, frame=None, wall=None):
    """Lit window (optionally framed) on a wall facing −Y rotated by rz about Z; w and h are scaled by WIN_K, the
    frame is lightened (frame_c)."""
    w, h = w * WIN_K, h * WIN_K
    if frame:
        fc = frame_c(frame, wall)
        bx((w + 0.022, 0.01, h + 0.022), (x, y, z), flat("frame" + fc, fc, 0.7), rz, 0)
    bx((w, 0.014, h), (x, y, z), win_lit(), rz, 0)


def front_windows(w, d, zs, n=2, frame=None, sides=True, ww=0.045, wh=0.05, wall=None):
    """Lit windows on the front (−Y) and back, plus the sides of a w×d box centred at the origin (at most WIN_MAX
    per row on a face)."""
    n = min(n, WIN_MAX)
    for z in zs:
        for i in range(n):
            x = (i + 0.5) / n * w - w / 2
            window(x, -d / 2 - 0.004, z, 0, ww, wh, frame, wall)
            window(x, d / 2 + 0.004, z, 0, ww, wh, frame, wall)
        if sides:
            window(-w / 2 - 0.004, 0, z, math.pi / 2, ww, wh, frame, wall)
            window(w / 2 + 0.004, 0, z, math.pi / 2, ww, wh, frame, wall)


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


def well_roof(x, y, rz, team):
    """The well's little gable roof in the team's plank courses (DL2 village and terem)."""
    gable_roof(0.16, 0.1, 0.07, (x, y, 0.22), shade(team, 0.75), tex("wood", WOOD, 3.0), rz=rz, oh=0.02, ohx=0.02,
               n=3, tk=0.014, ct=0.014, kind="wood", gable_timber=None, eave_z=0.0, **SOFT_ROOF)  # (no slab under 0.014)


def plank_fence(pts, h, gap=0.044, w=0.03, c=WOOD_L):
    """A fence of boards on two rails along the polyline pts (two-sided flat boards: cheap). «Raivon Soft» (plan
    step B2): fat boards (w 0.03, was 0.022) with round tops (a half-round in 4 segments, was a point), 0.02 rails
    and stout end posts — no stick or rail thinner than 0.02."""
    from mathutils import Vector
    mb = _MB()
    rail = tex("wood", WOOD, 3.0)
    top = [(math.cos(math.pi * i / 4), math.sin(math.pi * i / 4)) for i in range(5)]  # the half-round head
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.dist((x0, y0), (x1, y1))
        e = Vector(((x1 - x0) / L, (y1 - y0) / L, 0))
        nrm = Vector((-e.y, e.x, 0))
        for z in (h * 0.3, h * 0.68):
            beam((x0, y0, z), (x1, y1, z), 0.02, rail)
        for sx in (0.0, 1.0):
            cy(0.016, h + 0.02, (x0 + (x1 - x0) * sx, y0 + (y1 - y0) * sx, (h + 0.02) / 2), rail, 8)
        k = max(2, int(L / gap))
        for i in range(k):
            c0 = Vector((x0, y0, 0)) + e * (L * (i + 0.5) / k)
            for side in (1, -1):
                o = nrm * (0.011 * side)
                zc = h - w / 2
                prof = [c0 - e * w / 2 + o, c0 + e * w / 2 + o]
                prof += [c0 + e * (w / 2 * cx_) + o + Vector((0, 0, zc + w / 2 * sz)) for cx_, sz in top]
                mb.face(prof, nrm * side)
    mb.obj(tex("wood", c, 3.0), "fence")


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
    # «Raivon Soft» (§6.8: towers end in balls): a short round neck and a gilt ball of 0.3 r (at least 0.012), not a
    # needle spike with a speck on it
    cn(r * 0.5, r * 0.75, (x, y, z + r * 1.55 + r * 0.37), mt, 10)
    rb = max(0.012, r * 0.3)
    ico(rb, (x, y, z + r * 2.05 + rb * 0.6), flat("gold", GOLD, 0.35), sub=2 if rb >= 0.016 else 1)


# ------------------------------------------------------------------ half-timber kit (reference frames 3 and 4)
# The cottages and town houses of the reference: dark timber frames over cream plaster on a stone plinth, roofs
# laid in visible courses with dark barge boards and ridge caps, chunky brick chimneys with caps, doors under a
# little hood with a step, shutters and flower boxes. Built from cheap flat strips and wedge rows so a whole town
# stays inside the mobile budget.

TIMBER = "#6B4A30"  # oak beams (§6.3), was the near-black #47301f
SHUTTER_K = 0.62  # shutters: a deep shade of the team colour
# the settlement roofs: course shadow bands a little lighter and narrower than gable_roof's defaults, and a lighter
# slab edge, so the courses read as bright tile rows (reference frames 3 and 4) rather than dark seams or louvres.
# «Raivon Soft» (§6.8, plan step B1): the roofs are 3 fat courses (COURSES) of 0.018 slabs and steps with a 0.05
# overhang, and the course butts only a soft step darker (BUTT_K 0.82, was 0.68 / 0.75): a toy roof of three rounded
# rows, not a louvre of thin dark seams
COURSES = 3
BUTT_K = 0.82
ROOF_T = 0.018  # slab and course thickness of the gable and hip roofs (was 0.012 / 0.011)
SOFT_ROOF = dict(butt_k=BUTT_K, slab_k=0.8, band=0.8)


class _MB:
    """Mesh builder that keeps each face's winding pointing along a given outward normal (open shells cull right)."""

    def __init__(self):
        self.v, self.f = [], []

    def face(self, pts, n):
        from mathutils import Vector
        pts = [Vector(p) for p in pts]
        c = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        if len(pts) == 4 and c.length < 1e-10:
            c = (pts[2] - pts[0]).cross(pts[3] - pts[0])
        if c.dot(Vector(n)) < 0:
            pts = pts[::-1]
        i = len(self.v)
        self.v += [tuple(p) for p in pts]
        self.f.append(tuple(range(i, i + len(pts))))

    def strip(self, p0, p1, n, t, off=0.003):
        """A flat beam of width t from p0 to p1 lying on a wall with outward normal n, lifted off it by off."""
        from mathutils import Vector
        p0, p1, n = Vector(p0), Vector(p1), Vector(n).normalized()
        u = p1 - p0
        if u.length < 1e-6:
            return
        u.normalize()
        v = n.cross(u) * (t / 2)
        lift = n * off
        self.face([p0 - v + lift, p1 - v + lift, p1 + v + lift, p0 + v + lift], n)

    def obj(self, mt, name="m"):
        if not self.f:
            return None
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        # weld the shared corners: every face was laid with its own vertices, and loose faces each become a UV
        # island of their own (thousands of sub-texel islands that bake to the black gutter)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bm.to_mesh(me)
        bm.free()
        me.update()
        o = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(o)
        o.data.materials.append(mt)
        return o


NOSE = 0.5  # «Raivon Soft» course nose: the butt's top edge is chamfered by this fraction of the course thickness


def course_rows(mbs, A, B, C, D, n, t, eps=0.0015, up=(0, 0, 1), butt=None, band=0.72, nose=0.0, sides=True):
    """Roof courses on one roof face: eave edge A→B, top edge D→C (D above A, C above B; C == D on a hip end).
    n rows of wedges whose lower edge (the butt) stands t proud of the face: the stepped shadow lines of the tiles
    and shingles of the reference roofs. Rows alternate between the builders in mbs (two tones).
    nose > 0 («Raivon Soft», plan step B1): the butt's top edge is chamfered at 45° by nose × t, in the course's own
    material, so (smoothed with the course top by lowpoly's 50° rule) each course ends in a fat rounded lip over its
    dark butt instead of a knife step. sides=False: leave out the course ends at A→D and B→C (a gable verge whose
    barge roll swallows them)."""
    from mathutils import Vector
    A, B, C, D = (Vector(p) for p in (A, B, C, D))
    N = (B - A).cross(D - A)
    if N.length < 1e-10:
        N = (B - A).cross(C - A)
    N.normalize()
    if N.dot(Vector(up)) < 0:
        N = -N
    for k in range(n):
        fa, fb = k / n, min(1.0, (k + 1.2) / n)
        P0, P1 = A.lerp(D, fa), B.lerp(C, fa)
        Q0, Q1 = A.lerp(D, fb), B.lerp(C, fb)
        e = (P1 - P0).normalized()
        s = ((Q0 + Q1) / 2 - (P0 + P1) / 2).normalized()
        mb = mbs[k % len(mbs)]
        p0e, p1e, p0t, p1t, q0e, q1e = P0 + N * eps, P1 + N * eps, P0 + N * t, P1 + N * t, Q0 + N * eps, Q1 + N * eps
        c0a, c1a, c0b, c1b = p0t, p1t, p0t, p1t  # the nose: c?a on the butt, c?b on the course top
        nz = nose * (t - eps)
        if nz > 1e-5 and (q0e - p0t).length > 4 * nz and (q1e - p1t).length > 4 * nz:
            # cut 1.6× further along the top than down the butt: the chamfer meets the (down-tilted) course top at
            # ≈ 35°, under lowpoly's 50° smoothing limit, so the two shade as one rounded lip
            c0a, c1a = p0t - N * nz, p1t - N * nz
            c0b, c1b = p0t + (q0e - p0t).normalized() * nz * 1.6, p1t + (q1e - p1t).normalized() * nz * 1.6
            mb.face([c0a, c1a, c1b, c0b], N - s)
        if butt is not None and k < n - 1:
            # the shadow band under the next course: the top of this row darkens just below the next row's edge,
            # so the courses read from the high game camera (which never sees the down-facing butts)
            lam = ((k + band) / n - fa) / (fb - fa)
            m0, m1 = p0t.lerp(q0e, lam), p1t.lerp(q1e, lam)
            mb.face([c0b, c1b, m1, m0], N)
            butt.face([m0, m1, q1e, q0e], N)
        else:
            mb.face([c0b, c1b, q1e, q0e], N)
        (butt or mb).face([p0e, p1e, c1a, c0a], -s)
        if sides:
            mb.face([p0e, c0a, c0b, q0e] if c0a != c0b else [p0e, p0t, q0e], -e)
            mb.face([p1e, q1e, c1b, c1a] if c1a != c1b else [p1e, q1e, p1t], e)


def _roof_mats(roof_c, tone=0.9, kind="roof", scale=1.6):
    return [tex(kind, roof_c, scale), tex(kind, shade(roof_c, tone), scale)]


def gable_roof(w, d, h, loc, roof_c, gable_mt, rz=0.0, oh=0.05, ohx=0.045, n=COURSES, tk=ROOF_T, ct=ROOF_T, tone=0.84,
               kind="roof", barge=TRIM_AUTO, ridge=TRIM_AUTO, ridge_t=None, gable_timber=TIMBER, gable_win=False,
               eave_z=None, butt_k=BUTT_K, slab_k=0.72, band=0.72):
    """Gable roof of the reference cottages, ridge along local X, loc = centre of the wall top (w × d):
    two slabs with eaves and verges, courses laid on them, gable walls in the house material under the verges
    (not roof-coloured ends), barge boards, a ridge roll and a timbered gable with an optional lit window.
    «Raivon Soft» (§6.8): 3 fat courses on 0.018 slabs with a 0.05 overhang; the barge boards are round rolls along
    the verges (barge=TRIM_AUTO: roof × EAVE_K) and the ridge a smooth 12-sided roll of ridge_r(d) (ridge=TRIM_AUTO:
    roof × RIDGE_K; ridge_t: its diameter) instead of the dark ridge-cap box.
    eave_z=None: the slopes run through the wall-top edges and the eaves drop below them; a number: the eaves sit
    at that height (relative to the wall top) and short knee walls close the gap under the slabs, so the walls and
    their windows stay in view. butt_k / slab_k: shades of the course shadow bands and the slab edge, band: where
    each band starts up its course (the settlement roofs pass SOFT_ROOF: lighter, narrower bands that read as tile
    rows rather than seams)."""
    from mathutils import Vector
    if barge == TRIM_AUTO:
        barge = roof_trim(roof_c, EAVE_K)
    hd = d / 2
    L = w / 2 + ohx
    ye = hd + oh
    if eave_z is None:
        ze = -oh * h / hd
        knee = 0.0
    else:
        ze = eave_z
        knee = ze + (h - ze) * oh / ye  # slab height above the wall line
    ln = math.hypot(h - ze, ye)
    k = (h - ze) / ye
    P = lambda x, y, z: Vector(_rt((x, y, z), loc, rz))  # noqa: E731
    # gable walls: a closed prism over the walls (a triangle, or a pentagon with knee walls)
    if knee > 1e-4:
        poly = [(-hd, 0.0), (hd, 0.0), (hd, knee - 0.002), (0.0, h - 0.003), (-hd, knee - 0.002)]
    else:
        poly = [(-hd, 0.0), (hd, 0.0), (0.0, h - 0.003)]
    m = len(poly)
    verts = [(x, py, pz) for x in (-w / 2, w / 2) for (py, pz) in poly]
    faces = [tuple(range(m)), tuple(range(2 * m - 1, m - 1, -1))] + [(i, (i + 1) % m, (i + 1) % m + m, i + m) for i in range(m)]
    mesh_obj(verts, faces, gable_mt, loc, (0, 0, rz))
    MBs = [_MB(), _MB()]
    BUTT = _MB()
    slab = _MB()
    for sy in (-1, 1):
        ny, nz = sy * (h - ze) / ln, ye / ln  # outward normal of this slope (y, z)
        eb, rb = (sy * ye, ze), (0.0, h)
        et, rt = (eb[0] + ny * tk, eb[1] + nz * tk), (rb[0] + ny * tk, rb[1] + nz * tk)
        nrm = P(0, ny, nz) - P(0, 0, 0)
        # slab: bottom, eave edge, verge ends (its top lies under the courses and the ridge edge under the ridge
        # cap: both hidden, left out so their texels go to the visible parts)
        slab.face([P(-L, *eb), P(L, *eb), P(L, *rb), P(-L, *rb)], -nrm)
        slab.face([P(-L, *eb), P(L, *eb), P(L, *et), P(-L, *et)], P(0, sy, -k * 0.2) - P(0, 0, 0))
        for sx in (-1, 1):
            slab.face([P(sx * L, *eb), P(sx * L, *et), P(sx * L, *rt), P(sx * L, *rb)], P(sx, 0, 0) - P(0, 0, 0))
        # the barge roll (see below): its axis runs mid-way up the course layer, and its radius lets its crest stand
        # ROLL_RISE over the course butts even on a flat of the 6-sided roll (cos 30°), so it reads as a clean rolled
        # rim over the verge rather than a rail the course lips scallop
        ra = tk + ct * 0.5
        br = (ct * 0.5 + ROLL_RISE) / math.cos(math.pi / 6)
        roll = bool(barge) and br * 2 >= EAVE_MIN
        # with barge rolls the courses end at the rolls' axes, so the rolls swallow their stepped ends (no dark
        # notches along the verge) and the course ends are left out
        Lc = L - br * 0.6 if roll else L
        course_rows(MBs, P(-Lc, *et), P(Lc, *et), P(Lc, *rt), P(-Lc, *rt), n, ct, butt=BUTT, band=band, nose=NOSE,
                    sides=not roll)
        if roll:  # a round roll along each verge (covers the slab and course ends)
            for sx in (-1, 1):
                mid_e = (eb[0] + ny * ra, eb[1] + nz * ra)
                mid_r = (rb[0] + ny * ra, rb[1] + nz * ra)
                o = rod(tuple(P(sx * Lc, *mid_e)), tuple(P(sx * Lc, *mid_r)), br, flat("barge" + barge, barge, 0.8),
                        n=6)
                o["round"] = True  # (shaded round: lowpoly)
    slab.obj(tex(kind, shade(roof_c, slab_k), 1.6), "roof_slab")
    for mb, mt in zip(MBs, _roof_mats(roof_c, tone, kind)):
        mb.obj(mt, "roof_courses")
    BUTT.obj(tex(kind, shade(roof_c, butt_k), 1.6), "roof_butts")
    if ridge == TRIM_AUTO:
        ridge = roof_trim(roof_c, RIDGE_K)
    rr = ridge_t / 2 if ridge_t else ridge_r(d)
    if ridge and rr >= 0.006:  # a smooth round ridge roll over the meeting slabs
        rod(tuple(P(-L - 0.006, 0, h + tk * 0.9)), tuple(P(L + 0.006, 0, h + tk * 0.9)), rr,
            flat("ridge" + ridge, ridge, 0.8), n=12)
    if gable_timber:
        g = _MB()
        tt = max(0.009, 0.05 * d)
        for sx in (-1, 1):
            nx = P(sx, 0, 0) - P(0, 0, 0)
            x = sx * w / 2
            g.strip(P(x, -hd, tt / 2), P(x, hd, tt / 2), nx, tt)  # tie beam
            g.strip(P(x, 0, 0), P(x, 0, h * 0.86), nx, tt)  # king post
            for sy in (-1, 1):
                g.strip(P(x, sy * hd * 0.62, 0), P(x, 0, h * 0.5), nx, tt * 0.85)  # struts
        g.obj(flat("timber", gable_timber, 0.85), "gable_timber")
    if gable_win:
        for sx in (-1, 1):
            p = P(sx * (w / 2 + 0.004), 0, h * 0.3)
            window(p.x, p.y, p.z, rz + math.pi / 2, 0.026, 0.03)
    return h


def roof_surface(u, half, h, oh=0.05, eave_z=None, tk=ROOF_T, ct=ROOF_T):
    """Height above the wall top of the course tops of a gable_roof (half-span half, rise h, eave overhang oh) at
    horizontal distance u from the ridge: where a chimney or a flue comes out of the roof."""
    ze = -oh * h / half if eave_z is None else eave_z
    k = (h - ze) / (half + oh)
    return h - k * u + (tk + ct) * math.sqrt(1 + k * k)


def coursed_hip(w, d, h, loc, roof_c, oh=0.045, rz=0.0, n=COURSES, ct=ROOF_T, tone=0.84, kind="roof", trim=True,
                butt_k=BUTT_K, band=0.8):
    """hip_roof with the courses of the reference roofs laid on its four faces; the ridge and hip rolls (round, roof ×
    RIDGE_K) sit on top of the courses so they stay visible; eave boards only where at least EAVE_MIN thick."""
    _hip_roof(w, d, h, loc, tex(kind, shade(roof_c, 0.8), 1.6), oh, rz)
    ridges, hips, eaves = _hip_lines(w, d, h, oh)
    MBs = [_MB(), _MB()]
    BUTT = _MB()
    for (a, ta), (_, tb), (_, b) in zip(hips, hips[1:] + hips[:1], eaves):
        course_rows(MBs, _rt(a, loc, rz), _rt(b, loc, rz), _rt(tb, loc, rz), _rt(ta, loc, rz), n, ct, butt=BUTT,
                    band=band, nose=NOSE)
    for mb, mt in zip(MBs, _roof_mats(roof_c, tone, kind)):
        mb.obj(mt, "roof_courses")
    BUTT.obj(tex(kind, shade(roof_c, butt_k), 1.6), "roof_butts")
    if trim:
        lift = lambda ls: [((p0[0], p0[1], p0[2] + ct * 1.1), (p1[0], p1[1], p1[2] + ct * 1.1)) for p0, p1 in ls]  # noqa: E731
        _round_trim(loc, rz, roof_c, min(w, d), lift(ridges), lift(hips), lift(eaves), max(0.0095, 0.05 * min(w, d)))


def round_cap(r, h, loc, mt, n=10, bev=0.004, segs=1):
    """A short cylinder (r, h, centred at loc) whose top rim is rounded in the mesh itself (a bevel built with bmesh:
    lowpoly() strips the bevel modifiers of parts this small; smooth shading rounds the chamfer). Its underside is
    left out (it sits on a stack: never seen from the camera above)."""
    o = kit.cyl("c", r, h, loc, mt, n, 0.0)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    z0, z1 = min(v.co.z for v in bm.verts), max(v.co.z for v in bm.verts)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if all(abs(v.co.z - z0) < 1e-6 for v in f.verts)],
                     context="FACES_ONLY")
    rim = [e for e in bm.edges if all(abs(v.co.z - z1) < 1e-6 for v in e.verts)]
    bmesh.ops.bevel(bm, geom=rim, offset=min(bev, r * 0.4, h * 0.6), segments=segs, profile=0.5, affect="EDGES")
    bm.to_mesh(o.data)
    bm.free()
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


def disc(r, loc, mt, n=10):
    """A flat round disc facing up (one n-gon: a flue mouth, a water surface)."""
    return mesh_obj([(r * math.cos(math.tau * i / n), r * math.sin(math.tau * i / n), 0.0) for i in range(n)],
                    [tuple(range(n))], mt, loc)


def chimney(x, y, z0, z1, w=0.044, mt=None, cap=STONE_D):
    """A square chimney stack with a projecting cap and a flue mouth (the brick chimneys of reference frame 3).
    «Raivon Soft» (plan step B1): the cap is round (10 sides, rounded rim) and the flue a dark warm disc, not a
    near-black square. Returns the mouth height (for the smoke marker)."""
    mt = mt or stone(BRICK, 1.4)
    bx((w, w, z1 - z0), (x, y, (z0 + z1) / 2), mt, bev=0)
    rc = (w + 0.016) / 2 * 1.06  # the round cap still overhangs the square stack's corners a little
    round_cap(rc, 0.016, (x, y, z1 + 0.008), flat("cap" + cap, cap, 0.8))
    disc((w - 0.014) / 2, (x, y, z1 + 0.0162), flat("flue", "#3a302b", 0.9))
    return z1 + 0.016


chimney_stack = chimney  # for builders whose `chimney` flag shadows the helper


DOOR_K = 1.15  # doors ×1.15 wider, under a round arch (plan step B1)


def arch_slab(w, h, y0, y1, mt, n=8, x=0.0, sides=True):
    """A slab w wide and h tall standing on z = 0 on a wall facing −Y, its face at y0 and its back at y1 (on the wall,
    left open), centred at x, whose top is a half-round of radius w / 2 in n segments (an arched door). sides=False:
    only the front face (a frame plate flat on the wall)."""
    a = w / 2
    hr = max(1e-3, h - a)
    prof = [(a, 0.0)] + [(a * math.cos(math.pi * i / n), hr + a * math.sin(math.pi * i / n)) for i in range(n + 1)]
    prof.append((-a, 0.0))  # counter-clockwise in x, z: up the right side, over the arch, down the left side
    mb = _MB()
    mb.face([(x + px, y0, pz) for px, pz in prof], (0, -1, 0))
    if sides:
        for (px0, pz0), (px1, pz1) in zip(prof, prof[1:]):
            mb.face([(x + px0, y0, pz0), (x + px1, y0, pz1), (x + px1, y1, pz1), (x + px0, y1, pz0)],
                    (pz1 - pz0, 0.0, px0 - px1))
    return mb.obj(mt, "arch")


def doorway(x, y, rz, w=0.05, h=0.085, door_c=WOOD_D, hood_c=None, step=STONE_D, frame=TIMBER, wall=None):
    """A plank door in a frame on a wall facing −Y (rotated rz), a stone step and, with hood_c, a little gabled hood
    over it (the cottage porches of reference frame 3). «Raivon Soft»: the door is DOOR_K wider with a round arched
    top (a half-round of 8 segments), its frame lighter (frame_c: wall × FRAME_K when the wall is known)."""
    w = w * DOOR_K
    fc = frame_c(frame, wall)

    def b():
        # flat arched plates (§6.1: parts thinner than 0.08 are paint, not geometry): the frame, the door 3 mm proud
        arch_slab(w + 0.018, h + 0.009, -0.006, 0.002, flat("frame" + fc, fc, 0.85), sides=False)
        arch_slab(w, h, -0.009, 0.002, tex("wood", door_c, 3.0), sides=False)
        if step:
            bx((w + 0.04, 0.04, 0.016), (0, -0.026, 0.008), stone(step, 1.4), bev=0)
        if hood_c:
            hm = tex("roof", hood_c, 2.0)
            hw, hh, hd_ = w / 2 + 0.018, 0.026, 0.05
            mesh_obj([(-hw, 0.0, h + 0.02), (hw, 0.0, h + 0.02), (0, 0.0, h + 0.02 + hh),
                      (-hw, -hd_, h + 0.02), (hw, -hd_, h + 0.02), (0, -hd_, h + 0.02 + hh)],
                     [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], flat("hood_wall", PLASTER, 0.8))
            for sx in (-1, 1):
                mesh_obj([(0, 0.004, h + 0.02 + hh + 0.006), (sx * (hw + 0.008), 0.004, h + 0.014),
                          (sx * (hw + 0.008), -hd_ - 0.008, h + 0.014), (0, -hd_ - 0.008, h + 0.02 + hh + 0.006),
                          (0, 0.004, h + 0.02 + hh + 0.014), (sx * (hw + 0.008), 0.004, h + 0.022),
                          (sx * (hw + 0.008), -hd_ - 0.008, h + 0.022), (0, -hd_ - 0.008, h + 0.02 + hh + 0.014)],
                         [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)], hm)
    build_at(b, x, y, rz)


def shutter_window(x, y, z, rz, team, w=0.036, h=0.044, shutters=True, flowers=False, frame=TIMBER, crown=False,
                   wall=None):
    """A lit window on a wall facing −Y (rotated rz) in a frame, with shutters in a deep shade of the team colour and
    an optional flower box (reference frames 1 and 3). «Raivon Soft»: w and h × WIN_K, the frame lighter (frame_c:
    wall × FRAME_K when the wall is known, white carving stays white)."""
    w, h = w * WIN_K, h * WIN_K
    frame = frame_c(frame, wall)

    def b():
        bx((w + 0.012, 0.008, h + 0.012), (0, -0.002, 0), flat("frame" + frame, frame, 0.85), bev=0)
        bx((w, 0.012, h), (0, -0.004, 0), win_lit(), bev=0)
        if shutters:
            # the transom: a 0.012 bar, never a hair line (§6.1: nothing thinner than 0.012)
            bx((w + 0.004, 0.016, 0.012), (0, -0.006, 0.0), flat("frame" + frame, frame, 0.85), bev=0)
            sc = flat("shutter" + team, shade(team, SHUTTER_K), 0.75)
            for sx in (-1, 1):
                bx((w * 0.48, 0.008, h + 0.006), (sx * (w * 0.74 + 0.006), -0.006, 0), sc, bev=0)
        if crown:  # the carved head of a наличник (bands 0.016 tall, not 0.012 hair lines)
            bx((w + 0.03, 0.012, 0.016), (0, -0.004, h / 2 + 0.014), flat("frame" + frame, frame, 0.85), bev=0)
            bx((w * 0.5, 0.012, 0.016), (0, -0.004, h / 2 + 0.03), flat("frame" + frame, frame, 0.85), bev=0)
        if flowers:
            bx((w + 0.016, 0.018, 0.014), (0, -0.012, -h / 2 - 0.012), tex("wood", WOOD, 3.0), bev=0)
            bx((w + 0.008, 0.014, 0.01), (0, -0.012, -h / 2 - 0.0), flat("flowers", "#d9465a", 0.8), bev=0)
            bx((w * 0.4, 0.016, 0.008), (w * 0.22, -0.014, -h / 2 + 0.002), flat("flowers2", "#f2c84b", 0.8), bev=0)
    build_at(b, x, y, rz, z=z)


def timber_walls(w, d, z0, z1, wins=None, door=None, t=0.011, bay=0.042, rail=0.42, mt=None, posts=True):
    """Half-timber frame over a w × d wall box between z0 and z1 (reference frames 3 and 4): corner posts, sill,
    top plate, a mid rail, studs and the braces of the end bays, studs round the openings.
    wins: {face: [u, ...]} window centres along each face (faces 0 front −Y, 1 right +X, 2 back +Y, 3 left −X);
    door: (u, width, height) on the front face. Returns the window-centre height."""
    wins = wins or {}
    mb = _MB()
    zm = z0 + (z1 - z0) * rail
    zw = (zm + z1) / 2
    for f in range(4):
        a = f * math.pi / 2
        Lf = w if f % 2 == 0 else d
        dist = (d if f % 2 == 0 else w) / 2
        n = (math.sin(a), -math.cos(a), 0)
        e = (math.cos(a), math.sin(a), 0)

        def p(u, z):
            return (n[0] * dist + e[0] * u, n[1] * dist + e[1] * u, z)
        hl = Lf / 2
        if posts == "strip":
            for sx in (-1, 1):
                mb.strip(p(sx * (hl - t * 0.5), z0), p(sx * (hl - t * 0.5), z1), n, t * 1.2)
        mb.strip(p(-hl, z0 + t / 2), p(hl, z0 + t / 2), n, t)
        mb.strip(p(-hl, z1 - t / 2), p(hl, z1 - t / 2), n, t)
        dr = door if (f == 0 and door) else None
        if dr:
            du, dw_, dh = dr
            dw_ *= DOOR_K  # (doorway() widens the door)
            g0, g1 = du - dw_ / 2 - t, du + dw_ / 2 + t
            mb.strip(p(-hl, zm), p(g0, zm), n, t)
            mb.strip(p(g1, zm), p(hl, zm), n, t)
            for u in (g0 + t / 2, g1 - t / 2):
                mb.strip(p(u, z0), p(u, z1), n, t)
            mb.strip(p(g0, z0 + dh + t / 2), p(g1, z0 + dh + t / 2), n, t)
        else:
            mb.strip(p(-hl, zm), p(hl, zm), n, t)
        bw = min(bay, Lf * 0.28)
        for sx in (-1, 1):
            ui = sx * (hl - bw)
            mb.strip(p(ui, z0), p(ui, z1), n, t)
            mb.strip(p(ui, zm), p(sx * hl, z0 + t * 0.5), n, t * 0.9)  # the "Mann" braces of the end bays
            mb.strip(p(ui, zm), p(sx * hl, z1 - t * 0.5), n, t * 0.9)
        for u in wins.get(f, []):  # studs either side of a window (spaced for the WIN_K-bigger windows)
            for sx in (-1, 1):
                mb.strip(p(u + sx * 0.03 * WIN_K, zm), p(u + sx * 0.03 * WIN_K, z1), n, t * 0.85)
    mb.obj(mt or flat("timber", TIMBER, 0.85), "timber")
    if posts is True:
        pm = mt or flat("timber", TIMBER, 0.85)
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((t * 1.3, t * 1.3, z1 - z0), (sx * w / 2, sy * d / 2, (z0 + z1) / 2), pm, bev=0)
    return zw


def cottage(w, d, h, team, wall=PLASTER, pitch=1.15, smoke=False, chim=1, plinth=0.035, n_courses=COURSES,
            flowers=True, side_win=True, back_win=True, door_u=-0.24, gable_win=True, gable_front=True, eave_z=None,
            plain=False):
    """The half-timbered cottage of reference frame 3 (the homesteads and the small houses of the towns): a stone
    plinth, cream plaster under a dark timber frame, a roof of team-slate courses with dark barge boards, a brick
    chimney with a cap, a hooded door with a step under the front gable, lit windows with team shutters and a
    flower box. w along X (the front), d along Y; with gable_front the ridge runs front to back.
    plain: a back-row house that only shows its roof over the houses in front: no frame, windows or hood."""
    roof_c = slate(team, 1.0)
    pm = tex("plaster", wall, 1.5)
    bx((w + 0.018, d + 0.018, plinth), (0, 0, plinth / 2), stone(STONE_D, 1.4), bev=0)
    bx((w, d, h), (0, 0, h / 2), pm, soft="v")  # a soft mass: round corners (its top is under the roof)
    du = door_u * w
    wins = {0: [-du * 0.95]}
    if back_win:
        wins[2] = [-w * 0.2, w * 0.2] if w > 0.2 else [0.0]
    if side_win:
        wins[1] = [0.0]
        wins[3] = [0.0]
    if plain:
        wins = {}
    else:
        zw = timber_walls(w, d, plinth, h, wins, (du, 0.05, 0.085))
    doorway(du, -d / 2 - 0.004, 0.0, 0.05, 0.085, hood_c=None if plain else roof_c, wall=wall)
    for f, us in wins.items():
        a = f * math.pi / 2
        dist = (d if f % 2 == 0 else w) / 2 + 0.006
        for u in us:
            x = math.sin(a) * dist + math.cos(a) * u
            y = -math.cos(a) * dist + math.sin(a) * u
            shutter_window(x, y, zw, a, team, flowers=(flowers and f == 0), shutters=(f == 0 or not gable_front or f == 2),
                           wall=wall)
    span = w if gable_front else d
    rh = span / 2 * pitch
    gt = None if plain else TIMBER
    if gable_front:
        gable_roof(d, w, rh, (0, 0, h), roof_c, pm, rz=math.pi / 2, n=n_courses, gable_win=gable_win and not plain,
                   eave_z=eave_z, gable_timber=gt, **SOFT_ROOF)
    else:
        gable_roof(w, d, rh, (0, 0, h), roof_c, pm, n=n_courses, gable_win=gable_win and not plain, eave_z=eave_z,
                   gable_timber=gt, **SOFT_ROOF)
    if chim:  # a tall brick stack (reference frame 3): 6 cm of brick above the tiles, down the slope from the ridge
        if gable_front:
            cx_, cy_ = w * 0.32, chim * d * 0.22
            zr = h + roof_surface(abs(cx_), w / 2, rh, eave_z=eave_z)
        else:
            cx_, cy_ = chim * w * 0.28, d * 0.24
            zr = h + roof_surface(abs(cy_), d / 2, rh, eave_z=eave_z)
        top = chimney(cx_, cy_, h, zr + 0.06)
        if smoke:
            smoke_at(cx_, cy_, top + 0.01)
    return h + rh


def town_house(w, d, h0, h1, team, wall0=STONE, plaster=PLASTER, gable_front=True, smoke=False, jetty=0.014,
               shop=None, pitch=1.15, n_courses=COURSES, chim=1, side_win=True, gable_win=True, h2=0.0):
    """A town house of the reference towns: a stone ground floor with a door and a lit shop window (with an awning
    in the shop colour), a jettied half-timbered upper storey with team shutters, a coursed team-slate roof with
    its gable to the street and a brick chimney."""
    roof_c = slate(team, 1.0)
    bx((w, d, h0), (0, 0, h0 / 2), stone(wall0, 1.4), soft="v")  # soft mass (the jetty beam covers its top)
    doorway(-w * 0.24, -d / 2 - 0.004, 0.0, 0.046, min(0.08, h0 - 0.02), hood_c=None, wall=wall0)
    if shop:
        bx((w * 0.36, 0.012, h0 * 0.42), (w * 0.17, -d / 2 - 0.004, h0 * 0.42), win_lit(), bev=0)
        fc = frame_c(TIMBER, wall0)
        bx((w * 0.4, 0.008, h0 * 0.5), (w * 0.17, -d / 2 - 0.001, h0 * 0.42), flat("frame" + fc, fc, 0.85), bev=0)
        bx((w * 0.44, 0.05, 0.008), (w * 0.17, -d / 2 - 0.026, h0 * 0.78), flat("awn" + shop, shop, 0.7), bev=0,
           rot=(0.35, 0, 0))
    else:
        shutter_window(w * 0.2, -d / 2 - 0.006, h0 * 0.55, 0, team, shutters=False, wall=wall0)
    W1, D1, z1 = w, d, h0
    for k, hk in enumerate((h1, h2)):  # one or two jettied timber storeys
        if hk <= 0:
            continue
        W1, D1 = W1 + 2 * jetty, D1 + 2 * jetty
        bx((W1 + 0.01, D1 + 0.01, 0.018), (0, 0, z1 + 0.009), flat("timber", TIMBER, 0.85), bev=0)  # jetty beam
        pm = tex("plaster", plaster, 1.5)
        z0, z1 = z1 + 0.018, z1 + 0.018 + hk
        bx((W1, D1, hk), (0, 0, (z0 + z1) / 2), pm, soft="v")
        fw = [-W1 * 0.22, W1 * 0.22] if W1 > 0.2 else [0.0]
        sides = side_win and k == 0
        wins = {0: fw, 2: fw, 1: [0.0], 3: [0.0]} if sides else {0: fw, 2: fw}
        zw = timber_walls(W1, D1, z0, z1, wins, None, rail=0.32, posts="strip")
        for f, us in wins.items():
            a = f * math.pi / 2
            dist = (D1 if f % 2 == 0 else W1) / 2 + 0.006
            for u in us:
                x = math.sin(a) * dist + math.cos(a) * u
                y = -math.cos(a) * dist + math.sin(a) * u
                shutter_window(x, y, zw, a, team, shutters=(f == 0), flowers=(f == 0 and k == 1), wall=plaster)
    span = W1 if gable_front else D1
    rh = span / 2 * pitch
    if gable_front:
        gable_roof(D1, W1, rh, (0, 0, z1), roof_c, pm, rz=math.pi / 2, n=n_courses, gable_win=gable_win, eave_z=0.0,
                   **SOFT_ROOF)
    else:
        gable_roof(W1, D1, rh, (0, 0, z1), roof_c, pm, n=n_courses, gable_win=gable_win, eave_z=0.0, **SOFT_ROOF)
    if chim:
        if gable_front:
            cx_, cy_ = W1 * 0.24, chim * D1 * 0.2
            zr = z1 + roof_surface(abs(cx_), W1 / 2, rh, eave_z=0.0)
        else:
            cx_, cy_ = chim * W1 * 0.28, D1 * 0.22
            zr = z1 + roof_surface(abs(cy_), D1 / 2, rh, eave_z=0.0)
        top = chimney(cx_, cy_, z1, zr + 0.06)
        if smoke:
            smoke_at(cx_, cy_, top + 0.01)
    return z1 + rh


# ------------------------------------------------------------------ building types


def hut(w, d, h, team, smoke=False):
    """DL1 халупа: wattle and daub between rough dark posts and braces, a shaggy thatch laid in thick stepped
    courses with a team-coloured ridge, a team door in a plank frame, a clay flue."""
    dm = tex("plaster", DAUB, 1.5)
    bx((w, d, h + 0.04), (0, 0, (h - 0.04) / 2), dm, soft="v")  # soft mass (its top is under the thatch)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.014, h + 0.04, (sx * w / 2, sy * d / 2, (h - 0.04) / 2), tex("wood", WOOD_D), 6)
    timber_walls(w, d, 0.0, h, {}, (-w * 0.18, 0.07, 0.11), t=0.012, bay=w * 0.3, rail=0.5, posts=False,
                 mt=flat("rough_timber", "#5a3d26", 0.9))
    rh = w / 2 * 1.2  # the gable faces the front: the door and window stay out from under the low thatch eaves
    gable_roof(d, w, rh, (0, 0, h - 0.01), THATCH, dm, rz=math.pi / 2, oh=0.04, ohx=0.04, n=3, tk=0.02, ct=0.022,
               tone=0.86, kind="wood", barge=None, ridge=None, gable_timber="#5a3d26", **SOFT_ROOF)
    # a round team-painted ridge bundle (a smooth roll, not a box) held by two withy ties
    zr = h - 0.01 + rh + 0.022
    rod((0, -(d + 0.11) / 2, zr), (0, (d + 0.11) / 2, zr), 0.024, flat("ridge" + team, shade(team, 0.85)), n=12)
    for sy in (-1, 1):
        rod((0, sy * d * 0.3 - 0.008, zr), (0, sy * d * 0.3 + 0.008, zr), 0.027, flat("withy", "#8c6a42", 0.9), n=8)
    arch_slab(0.07 * DOOR_K, 0.11, -d / 2 - 0.005, -d / 2, flat("door" + team, shade(team, 0.7)), x=-w * 0.18,
              sides=False)  # an arched door plate
    window(w * 0.22, -d / 2 - 0.004, h * 0.62, 0, 0.04, 0.035, WOOD_D, wall=DAUB)
    if smoke:  # a clay flue standing 7 cm out of the thatch, a quarter of the width from the ridge
        zt = h - 0.01 + roof_surface(w * 0.25, w / 2, rh, 0.04, None, 0.02, 0.022)
        cy(0.022, 0.11, (w * 0.25, d * 0.08, zt + 0.015), tex("plaster", "#b08a62", 2.0), 7)
        cy(0.027, 0.014, (w * 0.25, d * 0.08, zt + 0.07), tex("plaster", "#8f6c4a", 2.0), 7)
        smoke_at(w * 0.25, d * 0.08, zt + 0.087)


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
        # «Raivon Soft»: the logs are the izba's soft mass — tagged "round", lowpoly shades the 6-sided logs as
        # smooth round logs (no extra triangles; the walls carry no bevel)
        for sy in (-1, 1):
            cy(r, w + 0.07, (0, sy * d / 2, z), logm, 6, rot=(0, math.pi / 2, 0))["round"] = True
        z2 = z + r * 0.46
        for sx in (-1, 1):
            cy(r, d + 0.07, (sx * w / 2, 0, z2), logm, 6, rot=(math.pi / 2, 0, 0))["round"] = True
        top = z2 + r
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(r * 0.9, 0.006, (sx * (w / 2 + 0.035), sy * d / 2, r), cut, 6, rot=(0, math.pi / 2, 0))
    rh = (d if not gable_front else w) * roof_k
    # plank roof in the team colour laid in shingle courses, planked gables, carved white barge boards on the front
    # gable, white carved window frames (наличники) with team shutters, a brick chimney with a cap
    roof_c = shade(team, 0.85)
    plank = tex("wood", shade(logc, 0.9), 3.0)
    # plank courses: 3 fat rows on a cottage roof, 4 on the long roof of the residence's big izba («Raivon Soft»: was
    # shingle rows of 0.034, 6 and more)
    nc = max(COURSES, round(math.hypot(rh, (w if gable_front else d) / 2 + 0.07) / 0.09))
    if gable_front:
        gable_roof(d + 2 * r, w + 2 * r, rh, (0, 0, top - 0.01), roof_c, plank, rz=math.pi / 2, oh=0.045, ohx=0.045,
                   n=nc, tone=0.84, kind="wood", barge=WHITE, gable_timber=None, gable_win=True, eave_z=0.0,
                   **SOFT_ROOF)
        # carved horse-head ridge finial (конёк) over the front gable
        tm = flat("trim" + WHITE, WHITE, 0.7)
        zt = top - 0.01 + rh + 0.02
        bx((0.024, 0.07, 0.024), (0, -d / 2 - r - 0.06, zt), tm, bev=0)  # (0.024: no 0.018 sticks, §6.1)
        bx((0.024, 0.034, 0.044), (0, -d / 2 - r - 0.09, zt + 0.018), tm, bev=0, rot=(0.5, 0, 0))
    else:
        gable_roof(w + 2 * r, d + 2 * r, rh, (0, 0, top - 0.01), roof_c, plank, oh=0.045, ohx=0.045, n=nc, tone=0.84,
                   kind="wood", gable_timber=None, gable_win=True, eave_z=0.0, **SOFT_ROOF)
    for i in range(n_win):
        x = (i + 0.5) / n_win * w - w / 2
        shutter_window(x, -d / 2 - r - 0.002, h * 0.55, 0, team, 0.04, 0.05, frame=WHITE, crown=True)
        shutter_window(x, d / 2 + r + 0.002, h * 0.55, math.pi, team, 0.04, 0.05, shutters=False, frame=WHITE)
    shutter_window(-w / 2 - r - 0.002, 0, h * 0.55, -math.pi / 2, team, 0.04, 0.05, shutters=False, frame=WHITE)
    if chimney:
        cx_, cy_ = w * 0.22, d * 0.12
        if gable_front:
            zr = top - 0.01 + roof_surface(abs(cx_), w / 2 + r, rh, 0.045, 0.0)
        else:
            zr = top - 0.01 + roof_surface(abs(cy_), d / 2 + r, rh, 0.045, 0.0)
        mouth = chimney_stack(cx_, cy_, top - 0.02, zr + 0.06)
        if smoke:
            smoke_at(cx_, cy_, mouth + 0.01)
    return top, rh


def barn(team, coursed=False):
    w, d, h = 0.4, 0.28, 0.22
    bx((w, d, h), (0, 0, h / 2), tex("wood", "#7a5232", 1.6), soft="v")  # soft mass (its top is under the roof)
    if coursed:  # the DL2 village and terem: plank courses like the izbas, planked gables
        gable_roof(w, d, 0.2, (0, 0, h - 0.005), shade(team, 0.75), tex("wood", "#7a5232", 1.6), oh=0.05, ohx=0.045,
                   kind="wood", gable_timber=None, eave_z=0.0, **SOFT_ROOF)
        for sx in (-1, 1):  # hay loft door in each gable
            bx((0.014, 0.08, 0.07), (sx * (w / 2 + 0.004), 0, h + 0.05), tex("wood", WOOD_D, 3.0), bev=0)
    else:
        prism_roof("roof", w, d, 0.2, (0, 0, h - 0.005), tex("wood", shade(team, 0.75), 2.0), overhang=0.06)
    lw = tex("wood", WOOD_L)
    for sx in (-1, 1):
        bx((0.085, 0.014, 0.16), (sx * 0.045, -d / 2 - 0.004, 0.08), lw, bev=0)
    # the white Z braces and lintel are paint on the door leaves (flat 0.02 strips), not 0.014 sticks (§6.1)
    zb = _MB()
    yb = -d / 2 - 0.0135
    for sx in (-1, 1):
        zb.strip((sx * 0.045 - 0.03, yb, 0.02), (sx * 0.045 + 0.03, yb, 0.14), (0, -1, 0), 0.02, off=0.0)
    zb.strip((-0.09, yb, 0.153), (0.09, yb, 0.153), (0, -1, 0), 0.024, off=0.0)
    zb.obj(flat("trim", WHITE, 0.7), "door_braces")


def stone_house(w, d, h, team, wall=STONE, roof_k=0.8, smoke=False):
    bx((w, d, h), (0, 0, h / 2), stone(wall, 1.6), soft="v")
    bx((w + 0.02, d + 0.02, 0.035), (0, 0, 0.0175), stone(STONE_D), bev=0)
    prism_roof("roof", w, d, d * roof_k, (0, 0, h - 0.005), tex("roof", slate(team, 1.00)), overhang=0.045)
    cy(0.028, 0.15, (w * 0.25, d * 0.15, h + d * roof_k * 0.55), stone(STONE_D), 8)
    if smoke:
        smoke_at(w * 0.25, d * 0.15, h + d * roof_k * 0.55 + 0.09)
    bx((0.065, 0.014, 0.11), (0, -d / 2 - 0.004, 0.055), tex("wood", WOOD_D), bev=0)
    for sx in (-1, 1):
        window(sx * w * 0.3, -d / 2 - 0.004, h * 0.62, 0, 0.04, 0.05, WOOD_D, wall)
        window(sx * w * 0.3, d / 2 + 0.004, h * 0.62, 0, 0.04, 0.05, WOOD_D, wall)
    window(w / 2 + 0.004, 0, h * 0.62, math.pi / 2, 0.04, 0.05, WOOD_D, wall)
    window(-w / 2 - 0.004, 0, h * 0.62, math.pi / 2, 0.04, 0.05, WOOD_D, wall)


def terem_block(w, d, h_stone, h_wood, team, roof_h, dome=True, dome_team=False, rich=False):
    """Terem: white stone ground floor, timber upper storey, carved team band, tall tent roof, onion.
    rich (the residence): carved white window frames with team shutters, an arched lit window in the stone storey,
    white carved corner boards on the timber storey."""
    # soft masses: the stone storey rounds its corners and the ledge round the timber storey; the timber storey only
    # its corners (the carved band covers its top)
    bx((w, d, h_stone), (0, 0, h_stone / 2), stone("#ece4d4", 1.4), soft=True)
    w2, d2 = w * 0.92, d * 0.92
    z1 = h_stone + h_wood
    bx((w2, d2, h_wood), (0, 0, h_stone + h_wood / 2), tex("wood", "#c98d4a", 2.5), soft="v")
    bx((w + 0.03, d + 0.03, 0.03), (0, 0, z1), flat("band" + team, shade(team, 0.9)), bev=0.006)
    coursed_hip(w, d, roof_h, (0, 0, z1 + 0.015), slate(team, 1.00))
    nwin = 2 if w > 0.22 else 1
    for i in range(nwin):
        x = (i + 0.5) / nwin * w2 - w2 / 2
        if rich:
            shutter_window(x, -d2 / 2 - 0.006, h_stone + h_wood * 0.47, 0, team, 0.04, 0.06, frame=WHITE, crown=True)
        else:
            window(x, -d2 / 2 - 0.004, h_stone + h_wood * 0.5, 0, 0.04, 0.06, WHITE)
        window(x, d2 / 2 + 0.004, h_stone + h_wood * 0.5, 0, 0.04, 0.06, WHITE)
    window(-w2 / 2 - 0.004, 0, h_stone + h_wood * 0.5, math.pi / 2, 0.04, 0.06, WHITE)
    window(w2 / 2 + 0.004, 0, h_stone + h_wood * 0.5, math.pi / 2, 0.04, 0.06, WHITE)
    window(0, -d / 2 - 0.004, h_stone * 0.55, 0, 0.035, 0.045, None, "#ece4d4")
    if rich:
        cb = _MB()
        for f in range(4):  # carved white corner boards on the timber storey
            a = f * math.pi / 2
            n_ = (math.sin(a), -math.cos(a), 0)
            e_ = (math.cos(a), math.sin(a), 0)
            hl, dist = (w2 if f % 2 == 0 else d2) / 2, (d2 if f % 2 == 0 else w2) / 2
            for sx in (-1, 1):
                u = sx * (hl - 0.008)
                p0 = (n_[0] * dist + e_[0] * u, n_[1] * dist + e_[1] * u, h_stone)
                cb.strip(p0, (p0[0], p0[1], z1 - 0.015), n_, 0.016)
        cb.obj(flat("trim" + WHITE, WHITE, 0.7), "corner_boards")
    if dome:
        dm = flat("dome" + team, team, 0.45) if dome_team else flat("gold", GOLD, 0.35)
        onion(0, 0, z1 + roof_h * 0.85, min(w, d) * 0.2, dm, tex("wood", "#c98d4a"))
    return z1


def mansion(w, d, floors, wall, team, fh=0.11):
    H = floors * fh + 0.02
    bx((w + 0.02, d + 0.02, 0.04), (0, 0, 0.02), stone(STONE_D), bev=0)
    bx((w, d, H), (0, 0, H / 2), facade(wall, WIN_D, 0.07, fh, 0.42, 0.5, lit_p=0.3), soft="v")  # (cornice on top)
    bx((w + 0.03, d + 0.03, 0.025), (0, 0, H), flat("cornice", WHITE, 0.6), bev=0.006)
    coursed_hip(w, d, 0.14, (0, 0, H + 0.0125), slate(team, 1.00), oh=0.03)
    for sx in (-1, 1):
        chimney(sx * w * 0.3, d * 0.15, H + 0.04, H + 0.15, 0.036, stone("#b0a594", 1.4))
    arch_slab(0.07 * DOOR_K, 0.1, -d / 2 - 0.005, -d / 2, tex("wood", WOOD_D), sides=False)  # an arched door plate
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
    build_at(lambda: barn(team, coursed=True), 0.36, -0.26, -0.3)
    build_at(well, 0.0, -0.04, 0.3)
    well_roof(0.0, -0.04, 0.3, team)
    build_at(lambda: garden(0.26, 0.15, 3, "#5aa63a"), -0.1, -0.5, 0.25)
    build_at(lambda: cart(team, "sacks"), 0.17, -0.5, -0.5)
    haystack(0.58, -0.02, 0.85)
    build_at(lambda: woodpile(2), 0.02, 0.4, 0.0)
    bench(-0.16, 0.12, 0.2)
    pine(0.6, 0.22, 1.1)
    pine(-0.66, 0.06, 1.0)
    tree(-0.58, 0.3, 0.7, LEAF2)
    flagpole(0.14, 0.16, 0.45, team, 0.13, "#8a6a44")


def market_stall(team, awn):
    """A market stall: four posts, a striped awning, a counter with goods (reference frame 3: the town square)."""
    wd = tex("wood", WOOD, 3.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.006, 0.11, (sx * 0.05, sy * 0.035, 0.055), wd, 5)
    bx((0.11, 0.08, 0.02), (0, 0, 0.05), tex("wood", WOOD_L), bev=0.003)
    for k, c in enumerate((awn, WHITE, awn)):
        o = bx((0.13, 0.034, 0.008), (0, -0.03 + k * 0.03, 0.118 - k * 0.004), flat("awn" + c, c, 0.7), bev=0)
        o.rotation_euler.x = -0.25
    for k, c in enumerate(("#d8452f", "#e8b84a", "#6faa3c")):
        ico(0.014, (-0.03 + k * 0.03, 0.0, 0.07), flat("goods" + c, c, 0.7), (1, 1, 0.8))


def town_props(team, spots):
    """Barrels and crates in little heaps at the given spots."""
    for i, (x, y) in enumerate(spots):
        cy(0.022, 0.05, (x, y, 0.025), tex("wood", WOOD), 8)
        cy(0.023, 0.006, (x, y, 0.04), flat("band", "#3d3f45", 0.5), 8)
        bx((0.04, 0.04, 0.035), (x + 0.04, y + 0.01, 0.018), tex("wood", WOOD_L), 0.3 * i, 0)


def city_dl3(team):
    pad(0.7, stone(COBBLE, 1.8), 0.012, 14, 0.06, 3)
    build_at(lambda: (terem_block(0.3, 0.26, 0.16, 0.18, team, 0.3),
                      bx((0.14, 0.1, 0.02), (0, -0.18, 0.01), stone(STONE_D), bev=0)), 0.0, 0.32)
    # the town of reference frame 3: half-timbered houses (two storeys at the sides and back, low cottages in
    # front so the market square stays in view), coursed team roofs, brick chimneys, shop windows under awnings
    build_at(lambda: town_house(0.28, 0.2, 0.12, 0.11, team, STONE, PLASTER, smoke=True, shop="#c0392b"), -0.46, 0.02, 0.2)
    build_at(lambda: town_house(0.26, 0.2, 0.12, 0.11, team, "#d8cdb6", "#efe1c4", chim=-1), 0.46, -0.02, -0.25)
    build_at(lambda: cottage(0.27, 0.19, 0.15, team, "#f2e8d4", smoke=True, pitch=1.0), -0.2, -0.43, 0.1)
    build_at(lambda: cottage(0.24, 0.19, 0.14, team, "#ead9b8", gable_front=False, pitch=1.0, eave_z=0.0, flowers=False,
                             side_win=False), 0.25, -0.44, -0.1)
    tree(-0.12, 0.62, 0.9)
    tree(0.36, 0.56, 0.8)
    flagpole(0.05, -0.12, 0.55, team, 0.14)
    # denser like the town of reference frame 3: two more houses at the back, a market on the square, goods in heaps
    build_at(lambda: town_house(0.2, 0.16, 0.1, 0.09, team, "#cfc6b4", "#efe3c8", shop="#e8b84a",
                                side_win=False, gable_win=False), -0.46, 0.42, 0.5)
    build_at(lambda: town_house(0.2, 0.15, 0.1, 0.09, team, "#d8cdb6", "#f1e6d2", smoke=True, gable_front=False,
                                side_win=False, gable_win=False), 0.52, 0.38, -0.5)
    for (x, y, rz, c) in ((-0.17, -0.14, 0.2, "#c0392b"), (0.2, -0.16, -0.2, "#2f62c8"), (-0.02, -0.26, 0.0, "#e8b84a")):
        build_at(lambda c=c: market_stall(team, c), x, y, rz)
    town_props(team, [(-0.62, -0.18), (0.62, -0.2)])


def city_dl4(team):
    pad(0.74, stone(COBBLE, 1.8), 0.012, 14, 0.04, 4)

    def town_hall():
        st = facade("#ddc9a0", WIN_D, 0.07, 0.12, 0.42, 0.5, lit_p=0.35)
        bx((0.58, 0.26, 0.28), (0, 0, 0.14), st, soft="v")  # soft masses (cornices on their tops)
        bx((0.6, 0.28, 0.025), (0, 0, 0.28), flat("cornice", WHITE, 0.6), bev=0.006)
        coursed_hip(0.58, 0.26, 0.13, (0, 0, 0.29), slate(team, 1.00), oh=0.03)
        tw = stone("#e6dcc4", 1.5)
        bx((0.15, 0.15, 0.66), (0, 0.0, 0.33), tw, soft="v")
        bx((0.18, 0.18, 0.025), (0, 0, 0.66), flat("cornice", WHITE, 0.6), bev=0.005)
        bx((0.13, 0.13, 0.12), (0, 0, 0.73), tw, soft="v")
        for k in range(4):
            a = k * math.pi / 2
            clock_face(math.sin(a) * 0.076, -math.cos(a) * 0.076, 0.56, a)
            window(math.sin(a) * 0.066, -math.cos(a) * 0.066, 0.74, a, 0.04, 0.062)
        coursed_hip(0.13, 0.13, 0.3, (0, 0, 0.79), slate(team, 1.00), oh=0.03, ct=0.014)
        ico(0.02, (0, 0, 1.11), flat("gold", GOLD, 0.35), sub=2)  # a round gilt ball on the spire
        for x in (-0.09, -0.03, 0.03, 0.09):
            cy(0.014, 0.18, (x, -0.165, 0.09), flat("cornice", WHITE, 0.6), 8)
        bx((0.24, 0.07, 0.02), (0, -0.165, 0.19), flat("cornice", WHITE, 0.6), bev=0)
        prism_roof("pedi", 0.07, 0.22, 0.06, (0, -0.165, 0.2), flat("cornice", WHITE, 0.6), overhang=0.01, rot_z=math.pi / 2)
    build_at(town_hall, 0.0, 0.36)
    build_at(lambda: mansion(0.26, 0.22, 3, "#f0d9b5", team), -0.47, -0.02, 0.15)
    build_at(lambda: mansion(0.28, 0.22, 2, "#e9c2b4", team), 0.47, 0.0, -0.15)
    # tall jettied half-timber houses on the front of the square (the town of reference frame 3, grown rich), set
    # wide and turned in, so the market stalls and the fountain show through the street between them
    build_at(lambda: town_house(0.23, 0.18, 0.12, 0.11, team, "#d5d0c3", "#f2e8d4", shop="#2f62c8", smoke=True),
             -0.29, -0.42, 0.25)
    build_at(lambda: town_house(0.21, 0.18, 0.12, 0.11, team, "#cfc6b4", "#efe1c4", shop="#c0392b", chim=-1),
             0.31, -0.42, -0.25)

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
    for (x, y, rz, c) in ((-0.05, -0.39, 0.1, "#c0392b"), (0.08, -0.29, -0.12, "#2f62c8")):
        build_at(lambda c=c: market_stall(team, c), x, y, rz)
    # back-row houses: only their roofs and chimneys show over the mansions and the town hall
    build_at(lambda: cottage(0.2, 0.16, 0.15, team, "#efe3c8", smoke=True, plain=True), -0.5, 0.42, 0.45)
    build_at(lambda: cottage(0.18, 0.15, 0.14, team, "#f1e6d2", gable_front=False, eave_z=0.0, plain=True),
             0.52, 0.4, -0.45)
    town_props(team, [(-0.64, -0.24), (0.64, -0.26)])


def street_lamp(x, y, h=0.2, modern=False):
    """A street lamp: a gas lantern on a cast-iron post (DL5), a slim steel pole with a cold head (DL6+)."""
    post = flat("lamp_post", "#2f3237" if not modern else "#7c838c", 0.5)
    cy(0.006, h, (x, y, h / 2), post, 6)
    if modern:
        bx((0.05, 0.014, 0.008), (x + 0.02, y, h), post, bev=0)
        bx((0.026, 0.016, 0.006), (x + 0.04, y, h - 0.006), glow("lamp_cold", "#d8f0ff", 3.0), bev=0)
    else:
        bx((0.022, 0.022, 0.03), (x, y, h + 0.014), glow("lamp_gas", "#ffcf7a", 3.0), bev=0)
        cn(0.02, 0.016, (x, y, h + 0.036), post, 4)


def car(x, y, rz, color):
    """A small parked car: a coloured body, a dark glass cabin, four wheels."""
    def b():
        bx((0.1, 0.048, 0.026), (0, 0, 0.024), flat("car" + color, color, 0.4), bev=0.006)
        bx((0.054, 0.044, 0.024), (-0.006, 0, 0.048), flat("car_glass", "#1d2a38", 0.2), bev=0.005)
        for sx in (-0.032, 0.032):
            for sy in (-0.024, 0.024):
                cy(0.012, 0.008, (sx, sy, 0.012), flat("tyre", "#1f1f21", 0.9), 8, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz)


def mansard(w, d, h, loc, roof_c, inset=0.045, n=COURSES, oh=0.012, ct=0.014):
    """A mansard roof over a w × d block (loc = centre of the wall top): four steep slopes laid in slate courses
    like the gable roofs (course_rows), round hip rolls (roof × RIDGE_K), and a flat lead top behind a pale zinc rim
    (the Paris and Petersburg tenements of the industrial age). Returns the height of the flat top."""
    x0, y0, z0 = loc
    W, D = w / 2 + oh, d / 2 + oh
    Wi, Di = w / 2 - inset, d / 2 - inset
    b = [(x0 - W, y0 - D, z0), (x0 + W, y0 - D, z0), (x0 + W, y0 + D, z0), (x0 - W, y0 + D, z0)]
    t = [(x0 - Wi, y0 - Di, z0 + h), (x0 + Wi, y0 - Di, z0 + h), (x0 + Wi, y0 + Di, z0 + h), (x0 - Wi, y0 + Di, z0 + h)]
    mesh_obj(b + t, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], tex("roof", shade(roof_c, 0.8), 1.6))
    MBs, BUTT = [_MB(), _MB()], _MB()
    for i in range(4):
        course_rows(MBs, b[i], b[(i + 1) % 4], t[(i + 1) % 4], t[i], n, ct, butt=BUTT, band=0.8, nose=NOSE)
    for mb, mt in zip(MBs, _roof_mats(roof_c, 0.84)):
        mb.obj(mt, "mansard_courses")
    BUTT.obj(tex("roof", shade(roof_c, BUTT_K), 1.6), "mansard_butts")
    lift = lambda p: (p[0], p[1], p[2] + ct * 1.1)  # noqa: E731
    tm = flat("ridge", roof_trim(roof_c, RIDGE_K), 0.8)
    for i in range(4):
        rod(lift(b[i]), lift(t[i]), 0.01, tm, n=6)["round"] = True  # (shaded round: lowpoly)
    bx((2 * Wi + 0.012, 2 * Di + 0.012, 0.012), (x0, y0, z0 + h + 0.004), flat("zinc", "#aeb3b8", 0.5), bev=0)
    bx((2 * Wi - 0.01, 2 * Di - 0.01, 0.006), (x0, y0, z0 + h + 0.0115), flat("tar", "#4a4b50", 0.9), bev=0)
    return z0 + h + 0.0145


def tenement5(w, d, floors, wall, team, fh=0.11, brick=False, dormers=2, smoke=True, shop=True):
    """An industrial-age tenement (DL5): a stucco or brick block over a ground floor of shops under team awnings,
    a pale string course and cornice, a slate mansard with lit dormers on the front and two brick stacks (one
    smoking: the lived-in chimneys of reference frame 3)."""
    H = floors * fh + 0.03
    f = facade(wall, WIN_D, 0.065, fh, 0.45, 0.52, lit_p=0.3, z0=0.03, brick=brick, brick_scale=34.0)
    bx((w, d, H), (0, 0, H / 2), f, bev=0)
    wh = flat("cornice", WHITE, 0.6)
    bx((w + 0.012, d + 0.012, 0.014), (0, 0, fh + 0.03), wh, bev=0)  # string course over the shops
    bx((w + 0.026, d + 0.026, 0.022), (0, 0, H), wh, bev=0)  # cornice
    roof_c = slate(team, 1.0)
    rh = 0.1
    mansard(w, d, rh, (0, 0, H + 0.011), roof_c, inset=0.045, n=3)
    # dormers on the front slope: a stucco cheek box with a lit window under a little slate gable
    zd = H + 0.011 + rh * 0.42
    yf = -(d / 2 + 0.014)  # the dormer cheeks stand on the eave line, proud of the steep slope
    for i in range(dormers):
        x = (i + 0.5) / dormers * w * 0.8 - w * 0.4
        bx((0.044, 0.06, 0.05), (x, yf + 0.03, zd), flat("dormer", shade(wall, 1.1), 0.8), bev=0)
        bx((0.026, 0.012, 0.03), (x, yf - 0.002, zd - 0.002), win_lit(), bev=0)
        wedge(0.068, 0.058, 0.026, (x, yf + 0.03, zd + 0.025), tex("roof", roof_c, 1.6), math.pi / 2)
    tops = []
    for sx in (-1, 1):
        tops.append((sx * w * 0.3, d * 0.16, chimney(sx * w * 0.3, d * 0.16, H + 0.04, H + 0.17, 0.034, stone(BRICK, 1.4))))
    if smoke:
        smoke_at(*tops[0])
    if shop:  # ground-floor shop window and a team awning on the street front
        bx((w * 0.78, 0.012, 0.05), (0, -(d / 2 + 0.004), 0.06), win_lit(), bev=0)
        bx((w * 0.86, 0.07, 0.012), (0, -(d / 2 + 0.03), 0.11), flat("awn" + team, team, 0.7), bev=0, rot=(-0.38, 0, 0))
        bx((w * 0.86, 0.012, 0.016), (0, -(d / 2 + 0.064), 0.098), flat("awn_hem", WHITE, 0.7), bev=0)
    return H


def sawtooth_roof(w, d, teeth, h, loc, roof_c, gable_mt, glass_mt):
    """A factory's sawtooth roof over a w × d hall: `teeth` ridges running front to back (the jagged profile
    shows on the gable ends towards the camera), each a slate slope rising to a dark ridge with a tall glazed
    north light dropping from it to the next tooth."""
    x0, y0, z0 = loc
    step = w / teeth
    yf, yk = y0 - d / 2, y0 + d / 2
    gl, rf, en = _MB(), [_MB(), _MB()], _MB()
    BUTT = _MB()
    for k in range(teeth):
        xa, xb = x0 - w / 2 + k * step, x0 - w / 2 + (k + 1) * step
        C, D = (xb, yk, z0 + h), (xb, yf, z0 + h)
        gl.face([(xb, yf, z0), (xb, yk, z0), C, D], (1, 0, 0))
        en.face([(xa, yf, z0), (xb, yf, z0), D], (0, -1, 0))
        en.face([(xa, yk, z0), (xb, yk, z0), C], (0, 1, 0))
        # the slope, laid in three courses from its low edge up to the ridge over the glazing
        course_rows(rf, (xa, yf, z0), (xa, yk, z0), C, D, 3, 0.008, butt=BUTT, band=0.8)
        beam((xb, yf - 0.008, z0 + h + 0.004), (xb, yk + 0.008, z0 + h + 0.004), 0.012,
             flat("roof_trim", roof_trim(roof_c), 0.8))
    gl.obj(glass_mt, "north_lights")
    en.obj(gable_mt, "saw_ends")
    for mb, mt in zip(rf, _roof_mats(roof_c, 0.86)):
        mb.obj(mt, "saw_courses")
    BUTT.obj(tex("roof", shade(roof_c, 0.68), 1.6), "saw_butts")


def tram(team):
    """A horse-era city tram (DL5): team-coloured lower body, a cream upper band with a lit window strip, a dark
    roof with a clerestory, open end platforms."""
    tc = flat("tram" + team, shade(team, 0.85), 0.5)
    bx((0.2, 0.058, 0.044), (0, 0, 0.04), tc, bev=0)
    bx((0.2, 0.06, 0.034), (0, 0, 0.079), flat("tram_cream", "#efe3c6", 0.6), bev=0)
    bx((0.17, 0.064, 0.02), (0, 0, 0.08), win_lit(), bev=0)
    bx((0.25, 0.07, 0.012), (0, 0, 0.102), flat("tram_roof", "#3a3c40", 0.7), bev=0)
    bx((0.14, 0.032, 0.014), (0, 0, 0.114), flat("tram_roof", "#3a3c40", 0.7), bev=0)
    bx((0.25, 0.05, 0.012), (0, 0, 0.018), flat("tyre", "#1f1f21", 0.9), bev=0)  # underframe and wheels


def poster_column(x, y):
    """A Litfaß advertising column: a dark green drum with a band of bright posters and a little dome cap."""
    cy(0.028, 0.012, (x, y, 0.006), flat("lamp_post", "#2f3237", 0.5), 8)
    cy(0.024, 0.13, (x, y, 0.075), flat("column_g", "#2f5a3e", 0.6), 8)
    cy(0.0255, 0.06, (x, y, 0.085), tex("plaster", "#e8d9a8", 3.0), 8)
    cn(0.03, 0.035, (x, y, 0.157), flat("column_g", "#2f5a3e", 0.6), 8)


def city_dl5(team):
    """The industrial town (DL5): a brick works with a sawtooth north-light hall, two smoking stacks and a water
    tower behind a cobbled street with tram rails and a team tram; slate-mansard tenements with lit dormers and
    shops under team awnings; gas lamps, an advertising column, a carter and crates."""
    pad(0.76, stone("#8f8a82", 2.2), 0.012, 14, 0.03, 5)
    roof_c = slate(team, 1.0)

    def factory():
        f = facade(BRICK, "#3b4552", 0.085, 0.13, 0.5, 0.6, lit="#ffd27a", lit_p=0.35, brick=True, pil=2,
                   pil_c=shade(BRICK, 0.72))
        bx((0.62, 0.3, 0.24), (0, 0, 0.12), f, bev=0)
        bx((0.64, 0.32, 0.02), (0, 0, 0.24), flat("cornice", "#d8cfc0", 0.6), bev=0)
        glass = facade("#3b4552", "#7fa7c4", 0.035, 0.026, 0.72, 0.7, lit="#ffd27a", lit_p=0.3)
        sawtooth_roof(0.6, 0.3, 3, 0.12, (0, 0, 0.25), roof_c, stone(BRICK, 1.4), glass)
        cm = stone("#9a3d30", 2.0)
        for (x, y, h) in ((-0.2, 0.2, 0.86), (0.06, 0.21, 0.72)):
            bx((0.13, 0.13, 0.08), (x, y, 0.04), stone("#7d3329", 2.0), bev=0)  # square base
            cy(0.055, h, (x, y, h / 2), cm, 10, r2=0.038)
            cy(0.045, 0.04, (x, y, h * 0.72), flat("band" + team, team, 0.6), 10)
            cy(0.05, 0.05, (x, y, h - 0.02), flat("soot", "#2b2726", 0.9), 10, r2=0.044)  # corbelled sooty crown
            smoke_at(x, y, h + 0.01)
        for sx in (-1, 1):  # the gates, with a team signboard over them
            bx((0.08, 0.016, 0.13), (sx * 0.12, -0.155, 0.065), tex("wood", WOOD_D), bev=0)
            bx((0.1, 0.012, 0.012), (sx * 0.12, -0.158, 0.136), flat("cornice", "#d8cfc0", 0.6), bev=0)
        bx((0.2, 0.012, 0.04), (0, -0.158, 0.19), flat("sign" + team, shade(team, 0.8), 0.6), bev=0)
        bx((0.14, 0.014, 0.01), (0, -0.16, 0.19), flat("emblem", WHITE, 0.6), bev=0)
    build_at(factory, -0.04, 0.36)

    def tank():
        bx((0.16, 0.16, 0.3), (0, 0, 0.15), facade(BRICK, "#3b4552", 0.08, 0.13, 0.4, 0.5, lit_p=0.3, brick=True), bev=0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cy(0.01, 0.12, (sx * 0.05, sy * 0.05, 0.36), flat("iron", "#4a4d52", 0.6), 6)
        cy(0.08, 0.1, (0, 0, 0.47), tex("wood", "#7a5a3c", 3.0), 12)  # a staved timber tank with iron hoops
        for z in (0.44, 0.5):
            cy(0.082, 0.008, (0, 0, z), flat("iron", "#4a4d52", 0.6), 12)
        cn(0.088, 0.05, (0, 0, 0.545), tex("roof", roof_c, 1.6), 12)
    build_at(tank, 0.47, 0.2)
    # the cobbled street with kerbs and tram rails, and a team tram on it
    bx((1.4, 0.15, 0.008), (0, 0.04, 0.014), stone("#6d6a66", 3.0), bev=0)
    for sy in (-1, 1):
        bx((1.4, 0.012, 0.012), (0, 0.04 + sy * 0.078, 0.016), flat("kerb", "#c9c3b6", 0.7), bev=0)
        bx((1.38, 0.007, 0.006), (0, 0.04 + sy * 0.026, 0.02), flat("rail", "#8a8f96", 0.4), bev=0)
    build_at(lambda: tram(team), -0.1, 0.04)
    build_at(lambda: tenement5(0.26, 0.24, 4, "#dcb98a", team), -0.47, -0.2, 0.12)
    build_at(lambda: tenement5(0.24, 0.22, 4, "#b8634e", team, brick=True, smoke=False), 0.45, -0.24, -0.12)
    build_at(lambda: tenement5(0.3, 0.2, 3, "#e3c99c", team, dormers=3), -0.04, -0.5, 0.05)
    crate = tex("wood", WOOD_L)
    for (x, y) in ((0.24, -0.52), (0.29, -0.48), (0.26, -0.57)):
        bx((0.05, 0.05, 0.05), (x, y, 0.025), crate, bev=0)
    barrel(0.2, -0.46)
    flagpole(0.2, -0.1, 0.55, team, 0.14)
    for (x, y) in ((-0.42, 0.13), (0.1, -0.04), (0.2, 0.13), (0.55, -0.05), (-0.2, -0.3)):  # gas lamps
        street_lamp(x, y, 0.2)
    poster_column(-0.24, -0.08)
    tree(0.06, -0.24, 0.8)
    build_at(lambda: cart(team, "sacks"), 0.26, -0.3, 0.4)  # a carter on the way to the works


def panel_block6(w, d, floors, team, fh=0.088, wall=CONC, stacks=(-0.3, 0.1, 0.36), tank=True, mural=0):
    """A mid-century panel block (DL6): the window grid on a concrete box over a dark plinth, stacks of balconies
    down the front (pale parapets over shadowed loggias, some lit), a team stair-well stripe over the entrance
    canopy, and the roof kit of the era: parapet, lift machine room, a water tank and TV aerials."""
    H = floors * fh + 0.03
    bx((w, d, H), (0, 0, H / 2), facade(wall, "#3a4656", 0.058, fh, 0.55, 0.5, lit="#ffe08a", lit_p=0.25, z0=0.03),
       bev=0)
    dk = flat("parapet", CONC_D)
    bx((w + 0.008, d + 0.008, 0.03), (0, 0, 0.015), flat("plinth6", "#6f6c67", 0.8), bev=0)
    bx((w + 0.012, d + 0.012, 0.02), (0, 0, H), dk, bev=0)
    bx((w - 0.012, d - 0.012, 0.004), (0, 0, H + 0.0105), flat("tar", "#4a4b50", 0.9), bev=0)
    # balcony stacks: one box each, the parapet / loggia bands come from the facade texture
    loggia = facade("#ece7dc", "#4d5866", 1.0, fh, 1.0, 0.42, lit="#ffd98a", lit_p=0.18, z0=0.03 + fh * 0.62)
    for u in stacks:
        bx((0.07, 0.026, H - fh - 0.04), (u * w, -(d / 2 + 0.013), (H + fh + 0.03) / 2), loggia, bev=0)
    tc = flat("stripe" + team, team, 0.6)
    xs = -w * 0.08
    bx((0.04, 0.014, H - 0.06), (xs, -(d / 2 + 0.004), H / 2 + 0.02), tc, bev=0)
    bx((0.08, 0.05, 0.012), (xs, -(d / 2 + 0.025), 0.085), dk, bev=0)
    bx((0.03, 0.012, 0.05), (xs, -(d / 2 + 0.006), 0.045), tex("wood", WOOD_D, 3.0), bev=0)  # the entrance door
    bx((0.09, 0.07, 0.06), (w * 0.25, 0, H + 0.04), dk, bev=0)  # lift machine room
    if mural:  # a mosaic on the blank end wall at local x = mural · w/2: a team panel with a pale emblem
        xm = mural * (w / 2 + 0.004)
        bx((0.012, d * 0.62, H * 0.55), (xm, 0, H * 0.58), flat("mural" + team, shade(team, 0.85), 0.6), bev=0)
        bx((0.016, d * 0.26, d * 0.26), (xm + mural * 0.002, 0, H * 0.62), flat("emblem", WHITE, 0.6), bev=0,
           rot=(math.pi / 4, 0, 0))
        bx((0.016, d * 0.5, 0.012), (xm + mural * 0.002, 0, H * 0.36), flat("emblem", WHITE, 0.6), bev=0)
    if tank:  # a water tank on a steel stand
        bx((0.05, 0.05, 0.03), (-w * 0.3, 0.0, H + 0.025), flat("iron", "#4a4d52", 0.6), bev=0)
        cy(0.034, 0.05, (-w * 0.3, 0.0, H + 0.065), flat("tank6", "#8d949b", 0.5), 8)
        cn(0.036, 0.018, (-w * 0.3, 0.0, H + 0.099), flat("tank6", "#8d949b", 0.5), 8)
    mast = flat("mast", "#d0d4da", 0.5)
    for k, u in enumerate((0.05, 0.4)):  # TV aerials: a pole and two crossbars
        x = u * w * (1 if k else -1)
        h = 0.09 + 0.02 * k
        rod((x, d * 0.2, H + 0.01), (x, d * 0.2, H + 0.01 + h), 0.003, mast, n=4)
        for zb, lb in ((h * 0.75, 0.05), (h * 0.95, 0.035)):
            bx((lb, 0.004, 0.004), (x, d * 0.2, H + 0.01 + zb), mast, bev=0)
    return H


def playground(team):
    """A courtyard playground (DL6): a sandbox, a swing frame, a slide in the team colour, a little roundabout."""
    wd = tex("wood", "#b07a44", 3.0)
    bx((0.1, 0.1, 0.02), (-0.12, 0.0, 0.016), wd, bev=0)
    bx((0.084, 0.084, 0.022), (-0.12, 0.0, 0.017), flat("sand", "#e6cf8f", 0.95), bev=0)
    red = flat("play_red", "#d8443a", 0.6)
    yel = flat("play_yel", "#f2c230", 0.6)
    for sx in (-1, 1):  # swing frame: two A-legs and a top bar, two seats on chains
        for sy in (-1, 1):
            beam((sx * 0.06, sy * 0.03, 0.006), (sx * 0.06, 0.0, 0.11), 0.007, red)
    beam((-0.064, 0.0, 0.11), (0.064, 0.0, 0.11), 0.008, red)
    for x in (-0.025, 0.025):
        bx((0.003, 0.003, 0.06), (x, 0.0, 0.08), flat("iron", "#4a4d52", 0.6), bev=0)
        bx((0.022, 0.014, 0.005), (x, 0.0, 0.05), yel, bev=0)
    tc = flat("slide" + team, shade(team, 1.1), 0.5)
    bx((0.03, 0.03, 0.09), (0.13, 0.03, 0.045), yel, bev=0)  # slide tower
    beam((0.13, 0.016, 0.09), (0.13, -0.08, 0.012), 0.024, tc)  # the slide
    cy(0.032, 0.008, (0.04, -0.07, 0.018), tc, 10)  # roundabout
    cy(0.004, 0.04, (0.04, -0.07, 0.04), yel, 4)


def park_bench(x, y, rz):
    """A park bench (DL6+): a slatted seat and a backrest (towards local +Y) on two dark iron ends."""
    def b():
        wd = tex("wood", "#b07a44", 3.0)
        iron = flat("iron", "#3b3d42", 0.6)
        for sx in (-0.03, 0.03):
            bx((0.007, 0.03, 0.028), (sx, 0.003, 0.014), iron, bev=0)
        bx((0.076, 0.028, 0.007), (0, 0, 0.0315), wd, bev=0)
        bx((0.076, 0.007, 0.026), (0, 0.0175, 0.048), wd, bev=0)
    build_at(b, x, y, rz)


def bus(team):
    """A mid-century bus in the team colour: lit windows, a team roof with a cream roof light strip (the game camera
    looks down on it, so the roof carries the colour)."""
    bx((0.17, 0.05, 0.04), (0, 0, 0.032), flat("bus" + team, shade(team, 0.9), 0.5), bev=0)
    bx((0.15, 0.052, 0.024), (0.006, 0, 0.064), win_lit(), bev=0)
    bx((0.17, 0.05, 0.012), (0, 0, 0.082), flat("busroof" + team, shade(team, 1.1), 0.6), bev=0)
    bx((0.12, 0.018, 0.004), (0.004, 0, 0.09), flat("bus_roof", "#e9e4d8", 0.6), bev=0)
    bx((0.17, 0.04, 0.012), (0, 0, 0.011), flat("tyre", "#1f1f21", 0.9), bev=0)


def city_dl6(team):
    """The mid-century district (DL6): panel blocks with balcony stacks and roof kit round a green courtyard with a
    playground, trees and benches, a road with lane markings, parked cars and a team bus, the station and rail line."""
    pad(0.78, flat("asph", ASPH, 0.9), 0.012, 14, 0.0, 6)
    build_at(lambda: panel_block6(0.64, 0.16, 9, team), 0.0, 0.44)
    build_at(lambda: panel_block6(0.44, 0.16, 5, team, wall="#d6cfc2", stacks=(-0.25, 0.25), mural=-1), -0.5, -0.02,
             math.pi / 2)
    build_at(lambda: panel_block6(0.44, 0.16, 6, team, wall="#cfd3d6", stacks=(-0.25, 0.25), mural=1), 0.5, 0.02,
             -math.pi / 2)
    for sx in (-1, 1):  # lawns with a tree and a hedge in the front corners
        bx((0.22, 0.13, 0.006), (sx * 0.5, -0.36, 0.015), tex("plaster", "#5f9e3c", 2.0), bev=0)
        bx((0.2, 0.022, 0.03), (sx * 0.5, -0.305, 0.03), flat("hedge", "#2f6a2c", 0.85), bev=0)
        tree(sx * 0.54, -0.38, 0.8)
    # the courtyard: a lawn with a path cross, a playground, trees and benches
    bx((0.68, 0.26, 0.006), (0, 0.205, 0.015), tex("plaster", "#5f9e3c", 2.0), bev=0)
    paving = flat("paving6", "#bdb7aa", 0.8)
    bx((0.68, 0.035, 0.004), (0, 0.205, 0.019), paving, bev=0)
    bx((0.035, 0.26, 0.004), (-0.06, 0.205, 0.0195), paving, bev=0)
    build_at(lambda: playground(team), 0.14, 0.23)
    for (x, y, s_) in ((-0.28, 0.27, 0.85), (-0.27, 0.115, 0.75), (0.31, 0.12, 0.8)):
        tree(x, y, s_)
    for (y, rz) in ((0.245, 0.0), (0.165, math.pi)):  # two benches facing each other across the path, on the lawn
        park_bench(-0.15, y, rz)
    # the road in front of the blocks: kerbs and white lane dashes (only where the station leaves them in sight)
    bx((0.86, 0.006, 0.01), (0, 0.072, 0.017), flat("kerb", "#c9c3b6", 0.7), bev=0)
    paint = flat("paint", "#e8e6df", 0.7)
    for x in (-0.38, -0.3, 0.3, 0.38):
        bx((0.06, 0.008, 0.003), (x, -0.02, 0.0135), paint, bev=0)

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
    flagpole(-0.32, -0.3, 0.45, team, 0.12)
    for (x, y, rz, c) in ((-0.31, 0.04, 0.0, "#b8332a"), (-0.19, 0.04, 0.0, "#e8e4da"), (0.32, 0.04, math.pi, "#2f5f9a"),
                          (-0.32, -0.065, 0.0, "#3f6b3a")):  # parked at the kerb, one driving
        car(x, y, rz, c)
    # the team bus waiting at the station, in the open lane beside it (behind the station it was out of sight)
    build_at(lambda: bus(team), 0.33, -0.21, math.pi / 2)
    for (x, y) in ((-0.36, 0.09), (0.36, 0.09), (-0.16, -0.115), (0.12, -0.115)):
        street_lamp(x, y, 0.2, True)


def glass_tower7(w, d, h, team, crown="mast", setback=None, tone=0):
    """A contemporary glass tower (DL7): a granite step and a warm-lit lobby, a curtain wall framed by pale steel
    corner fins and a centre mullion, cold light bands, an optional setback with a team band on its terrace, and a
    crown: "mast" (plant room, mast, red beacon), "slant" (a sloped glass top), "helipad" (a pad with a white H on
    a yellow rim) or "ac" (rooftop plant)."""
    steel = flat("mullion", "#d9dde2", 0.4)
    base = flat("plinth", "#5d6470", 0.6)
    tc = flat("crown" + team, team, 0.5)
    if tone == 0:
        gl = facade("#33506b", GLASS, 0.05, 0.065, 0.8, 0.74, lit="#c8ecff", lit_p=0.3)
    else:
        gl = facade("#2a4256", "#5aa6cf", 0.045, 0.065, 0.78, 0.72, lit="#ffe6b0", lit_p=0.22)
    band = glow("band", "#a8e6ff", 1.6)
    bx((w + 0.04, d + 0.04, 0.03), (0, 0, 0.015), base, bev=0)
    lobby = facade("#3a4048", "#ffe2a8", 0.05, 0.07, 0.86, 0.8, lit="#ffe2a8", lit_p=1.0, z0=0.03)
    bx((w - 0.012, d - 0.012, 0.07), (0, 0, 0.065), lobby, bev=0)
    bx((w * 0.5, 0.05, 0.008), (0, -(d / 2 + 0.02), 0.095), steel, bev=0)  # entrance canopy
    z1 = h * setback if setback else h
    parts = [(w, d, 0.1, z1)] + ([(w * 0.78, d * 0.78, z1, h)] if setback else [])
    for (pw, pd, za, zb) in parts:
        zm = (za + zb) / 2
        bx((pw, pd, zb - za), (0, 0, zm), gl, bev=0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((0.016, 0.016, zb - za), (sx * pw / 2, sy * pd / 2, zm), steel, bev=0)
        bx((0.01, 0.012, zb - za - 0.02), (0, -(pd / 2 + 0.004), zm), steel, bev=0)
        bx((pw + 0.016, pd + 0.016, 0.026), (0, 0, zb + 0.004), tc, bev=0)
        z = za + 0.2
        while z < zb - 0.08:
            bx((pw + 0.01, pd + 0.01, 0.012), (0, 0, z), band, bev=0)
            z += 0.2
    pw, pd = parts[-1][0], parts[-1][1]
    zt = h + 0.017
    if crown == "mast":
        bx((pw * 0.5, pd * 0.5, 0.06), (0, 0, zt + 0.03), base, bev=0)
        rod((pw * 0.1, 0, zt + 0.06), (pw * 0.1, 0, zt + 0.5), 0.008, flat("mast", "#d0d4da", 0.5), r2=0.004, n=6)
        ico(0.014, (pw * 0.1, 0, zt + 0.52), glow("beacon", "#ff4a3a", 4.0))
    elif crown == "slant":
        taper_box((pw, pd, 0.22), (0, 0, zt + 0.11), gl, (1.0, 0.15))
    elif crown == "helipad":
        r = min(pw, pd) * 0.44
        cy(r + 0.01, 0.008, (0, 0, zt + 0.004), flat("pad_rim", "#f2c230", 0.6), 12)
        cy(r, 0.012, (0, 0, zt + 0.006), flat("helipad", "#2e3138", 0.7), 12)
        wm = flat("emblem", WHITE, 0.6)
        for sx in (-1, 1):
            bx((0.012, r * 0.9, 0.004), (sx * r * 0.3, 0, zt + 0.013), wm, bev=0)
        bx((r * 0.6, 0.012, 0.004), (0, 0, zt + 0.013), wm, bev=0)
        ico(0.01, (pw / 2 - 0.01, pd / 2 - 0.01, zt + 0.01), glow("beacon", "#ff4a3a", 4.0))
    else:  # rooftop plant: AC boxes with dark fans and a duct
        for (x, y) in ((-pw * 0.22, -pd * 0.18), (pw * 0.2, -pd * 0.18), (-pw * 0.22, pd * 0.2)):
            bx((0.05, 0.05, 0.03), (x, y, zt + 0.015), flat("ac_unit", "#8a9099", 0.5), bev=0)
            cy(0.016, 0.004, (x, y, zt + 0.032), flat("fan", "#2e3138", 0.7), 6)
        bx((0.03, pd * 0.45, 0.02), (pw * 0.2, pd * 0.12, zt + 0.01), flat("ac_unit", "#8a9099", 0.5), bev=0)


def billboard(team, w=0.2, h=0.1, z=0.12):
    """A lit roadside billboard: two steel posts, a dark frame, a glowing team-tinted panel with a white logo."""
    post = flat("lamp_post", "#7c838c", 0.5)
    for sx in (-1, 1):
        cy(0.007, z, (sx * w * 0.3, 0, z / 2), post, 6)
    bx((w + 0.016, 0.014, h + 0.016), (0, 0.004, z + h / 2), flat("bb_frame", "#2b2f36", 0.6), bev=0)
    bx((w, 0.01, h), (0, -0.004, z + h / 2), glow("bb" + team, shade(team, 1.35), 1.4), bev=0)
    bx((w * 0.5, 0.012, h * 0.22), (-w * 0.12, -0.006, z + h * 0.62), glow("bb_logo", "#f4fbff", 1.6), bev=0)


def city_dl7(team):
    """The contemporary city (DL7): glass towers framed by steel fins with lit lobbies, setbacks and crowns (a mast
    with a beacon, a sloped glass top, a helipad, rooftop plant), a glass skybridge, a roof-garden pavilion, street
    trees in planters, a lit billboard, flags, cars and lamps on a paved plaza."""
    pad(0.8, stone("#c9c6bf", 1.6), 0.015, 14, 0.0, 7)  # large granite plaza slabs (they read at map size)
    build_at(lambda: glass_tower7(0.3, 0.26, 1.42, team, "mast", 0.66), -0.16, 0.32)
    build_at(lambda: glass_tower7(0.25, 0.23, 1.05, team, "slant", tone=1), 0.38, 0.14, -0.2)
    build_at(lambda: glass_tower7(0.22, 0.22, 0.72, team, "helipad"), -0.44, -0.24, 0.3)
    build_at(lambda: glass_tower7(0.18, 0.18, 0.55, team, "ac", tone=1), 0.54, -0.24, 0.15)
    # a glass skybridge from the tall tower to its neighbour, aimed so each end sinks 0.02 into a tower: from
    # (-0.03, 0.26) inside the tall tower's east face to the slant tower's local (-0.105, 0.07)
    ta, tb = (-0.03, 0.26), (0.38 - 0.105 * math.cos(0.2) + 0.07 * math.sin(0.2),
                             0.14 + 0.105 * math.sin(0.2) + 0.07 * math.cos(0.2))
    bl, brz = math.dist(ta, tb), math.atan2(tb[1] - ta[1], tb[0] - ta[0])
    bc = ((ta[0] + tb[0]) / 2, (ta[1] + tb[1]) / 2)
    bx((bl, 0.06, 0.05), (bc[0], bc[1], 0.62), facade("#33506b", GLASS, 0.03, 0.05, 0.8, 0.7, lit="#c8ecff", lit_p=0.3),
       brz, bev=0)
    bx((bl, 0.064, 0.01), (bc[0], bc[1], 0.598), glow("band", "#a8e6ff", 1.6), brz, bev=0)

    def pavilion():
        gl = facade("#33506b", GLASS, 0.05, 0.07, 0.8, 0.74, lit="#c8ecff", lit_p=0.3)
        bx((0.34, 0.2, 0.15), (0, 0, 0.075), gl, bev=0)
        bx((0.38, 0.24, 0.025), (0, 0, 0.16), flat("crown" + team, team, 0.5), bev=0)
        bx((0.3, 0.18, 0.02), (0, 0, 0.18), flat("lawn", "#5fa83a", 0.9), bev=0)
        for (x, y) in ((-0.1, 0.03), (0.1, -0.03)):
            build_at(lambda: tree(0, 0, 0.5), x, y, z=0.19)
    build_at(pavilion, 0.22, -0.42, -0.1)
    for (x, y) in ((-0.1, -0.2), (0.06, -0.05), (-0.62, 0.1), (0.64, 0.3), (-0.22, -0.02)):
        bx((0.08, 0.08, 0.04), (x, y, 0.02), flat("planter", "#7a7f88", 0.6), bev=0)
        bx((0.066, 0.066, 0.004), (x, y, 0.041), tex("plaster", "#5b3f27", 2.5), bev=0)
        tree(x, y, 0.75)
    for x in (-0.12, -0.04, 0.04):
        flagpole(x, -0.58, 0.42, team, 0.11, "#d0d4da")
    build_at(lambda: billboard(team), -0.36, -0.52, 0.12)
    paint = flat("paint", "#e8e6df", 0.7)
    for i in range(4):  # a zebra crossing on the plaza drive
        bx((0.016, 0.07, 0.003), (-0.14 + i * 0.03, -0.36, 0.0165), paint, bev=0)
    for (x, y, rz, c) in ((-0.24, -0.36, 0.0, "#e8e4da"), (0.0, -0.36, 0.0, "#c23a2b"), (0.1, 0.06, 1.7, "#2b2f36")):
        car(x, y, rz, c)
    for (x, y) in ((-0.3, -0.42), (0.02, -0.26), (0.16, 0.2), (-0.3, 0.02)):
        street_lamp(x, y, 0.24, True)


def spire8(x, y, w, d, h, mats, rings=(0.62, 0.8), crown=0.12, needle=0.12, buttress=True, banner=None):
    """A steel tower of the neon city (reference frames 2 and 5, the residence_dl8 kit at city scale): a shaft in
    the steel facade with plate seams, corner buttresses, thin neon rings round it, inset team panels with a cold
    light strip on the faces towards the camera, a setback crown and a dark four-sided needle with a lit tip."""
    st, plate, seam, panel, cap, neon, tip = mats
    bx((w, d, h), (x, y, h / 2), st, bev=0)
    bx((w + 0.012, d + 0.012, 0.022), (x, y, h * 0.34), seam, bev=0)
    if buttress:
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((0.018, 0.018, h * 0.96), (x + sx * w / 2, y + sy * d / 2, h * 0.48), plate, bev=0)
    for zf in rings:
        bx((w + 0.016, d + 0.016, 0.014), (x, y, h * zf), neon, bev=0)
    mb = _MB()
    if banner:  # a great banner down the front instead of the panel (reference frame 2's banners on the spires)
        facade_banner(x, y - d / 2 - 0.016, h * 0.9, w * 0.52, h * 0.4, banner, 0.0, "#c9a24a")
    for (nx, ny) in (((1, 0),) if banner else ((0, -1), (1, 0))):
        L = w if ny else d
        off = (d if ny else w) / 2 + 0.002
        px, py = x + nx * off, y + ny * off
        tx, ty = -ny * L * 0.2, nx * L * 0.2
        mb.face([(px - tx, py - ty, h * 0.38), (px + tx, py + ty, h * 0.38), (px + tx, py + ty, h * 0.93),
                 (px - tx, py - ty, h * 0.93)], (nx, ny, 0))
        bx((0.012, 0.008, h * 0.5), (px + nx * 0.003, py + ny * 0.003, h * 0.655), neon, 0.0 if ny else math.pi / 2,
           bev=0)
    mb.obj(panel, "panels")
    ch = h * crown
    bx((w * 0.78, d * 0.78, ch), (x, y, h + ch / 2), st, bev=0)
    bx((w * 0.8, d * 0.8, 0.012), (x, y, h + ch), plate, bev=0)
    hc = min(w, d) * 1.6
    cn(min(w, d) * 0.42, hc, (x, y, h + ch + hc / 2), cap, 4, rot=(0, 0, math.pi / 4))
    top = h + ch + hc
    if needle:
        rod((x, y, top - 0.01), (x, y, top + needle), 0.006, cap, r2=0.0015, n=4)
        bx((0.014, 0.014, 0.014), (x, y, top + needle * 0.6), tip, bev=0)
    return top


def round8(x, y, r, h, mats, rings=(0.45, 0.75)):
    """A round steel tower of the neon city (the drum towers of reference frame 2): neon rings, cold light strips
    down the front, a plate crown and a glass dome with a lit ring and a needle."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r, h, (x, y, h / 2), st, 10)
    for zf in rings:
        cy(r + 0.007, 0.014, (x, y, h * zf), neon, 10)
    for a in (-math.pi / 2 - 0.6, -math.pi / 2 + 0.6, 0.35):
        bx((0.012, 0.008, h * 0.7), (x + math.cos(a) * (r + 0.002), y + math.sin(a) * (r + 0.002), h * 0.5), neon,
           a + math.pi / 2, bev=0)
    cy(r * 1.12, 0.03, (x, y, h + 0.015), plate, 10)
    cy(r * 1.0, 0.01, (x, y, h + 0.034), neon, 10)
    hemi(r * 0.9, (x, y, h + 0.03), flat("dome_glass", "#6fa9cf", 0.3), 10, 3, (1, 1, 0.8))
    rod((x, y, h + 0.03 + r * 0.7), (x, y, h + 0.03 + r * 0.7 + 0.12), 0.006, cap, r2=0.0015, n=4)
    bx((0.014, 0.014, 0.014), (x, y, h + 0.03 + r * 0.7 + 0.08), tip, bev=0)


def city_dl8(team):
    """The neon city (DL8) after reference frames 2 and 5, in the steel of the late residence: grey steel towers
    with plate seams and buttresses, inset team panels with cold light strips, neon rings and dark needles round a
    tall central spire; low steel blocks with lit bands; a dark steel plaza laced with glowing street strips; a
    holo banner projecting the state's crest, light masts and cargo crates."""
    st = steel_facade()
    plate = flat("plate8", "#505760", 0.45)
    seam = flat("seam8", "#8c939c", 0.45)
    panel = flat("panel8" + team, shade(team, 0.42), 0.4)
    cap = flat("spire8", "#4c535d", 0.35)
    neon = glow("strip" + team, shade(team, 1.25), 2.0)
    cyan = glow("cyan", CYAN, 2.5)
    mats = (st, plate, seam, panel, cap, neon, cyan)
    pad(0.8, stone("#454a52", 0.8), 0.015, 14, 0.0, 8)
    # glowing street strips: a cross of avenues edged by light lines, and a light rim round the plaza
    for (x0, y0, x1, y1) in ((-0.74, -0.15, 0.74, -0.15), (-0.74, -0.27, 0.74, -0.27),
                             (0.07, -0.74, 0.07, 0.74), (0.19, -0.74, 0.19, 0.74)):
        beam((x0, y0, 0.017), (x1, y1, 0.017), 0.012, neon)
    paving = flat("road8", "#2c3036", 0.6)
    bx((1.48, 0.11, 0.004), (0, -0.21, 0.0155), paving, bev=0)
    for (y0, y1) in ((-0.74, -0.27), (-0.15, 0.74)):  # (not across the other avenue: overlapping plates bake black)
        bx((0.11, y1 - y0, 0.004), (0.13, (y0 + y1) / 2, 0.0155), paving, bev=0)
    # the central spire, the city's needle, and the ring of towers stepping down from it
    spire8(-0.18, 0.36, 0.26, 0.22, 1.42, mats, rings=(0.3, 0.46, 0.94), crown=0.14, needle=0.2, banner=team)
    spire8(0.42, 0.3, 0.18, 0.16, 1.1, mats, rings=(0.28, 0.94), banner=team)
    spire8(-0.5, 0.1, 0.17, 0.15, 0.9, mats, rings=(0.66,))
    spire8(0.6, -0.04, 0.14, 0.14, 0.7, mats, rings=(0.7,), buttress=False)  # (clear of the banner on its right)
    round8(-0.42, -0.46, 0.09, 0.66, mats)
    # a steel skybridge between the spire and its neighbour, a light line along it (the lit bridges of frame 2)
    beam((-0.3, 0.3, 0.52), (-0.43, 0.12, 0.52), 0.045, plate)
    beam((-0.3, 0.3, 0.495), (-0.43, 0.12, 0.495), 0.05, neon)
    # low steel blocks with lit window bands and roof plant (the podiums of frame 5)
    for (x, y, w, d, h) in ((-0.2, 0.0, 0.3, 0.2, 0.16), (0.42, -0.46, 0.3, 0.18, 0.14)):
        bx((w, d, h), (x, y, h / 2), st, bev=0)
        bx((w + 0.012, d + 0.012, 0.016), (x, y, h), plate, bev=0)
        bx((w + 0.004, d + 0.004, 0.012), (x, y, h * 0.55), neon, bev=0)
        bx((0.05, 0.05, 0.03), (x + w * 0.36, y + d * 0.26, h + 0.023), seam, bev=0)  # (clear of the dome)
    # a glass dome on the front block (the domes of frame 2)
    hemi(0.09, (0.42, -0.46, 0.148), flat("dome_glass", "#6fa9cf", 0.3), 10, 3, (1, 1, 0.7))
    cy(0.094, 0.01, (0.42, -0.46, 0.15), neon, 10)
    # a holo banner: a mast projecting the state's colour as a glowing panel with the crest
    hx, hy = -0.08, -0.4
    cy(0.04, 0.03, (hx, hy, 0.03), plate, 6)
    cy(0.007, 0.36, (hx, hy, 0.2), flat("mast", "#d0d4da", 0.5), 6)
    bx((0.12, 0.004, 0.17), (hx + 0.066, hy, 0.29), glow("holo" + team, team, 1.0), bev=0)
    bx((0.13, 0.008, 0.008), (hx + 0.066, hy, 0.38), cyan, bev=0)
    crest = [(0.0, -0.036), (0.026, -0.016), (0.026, 0.026), (0.0, 0.016), (-0.026, 0.026), (-0.026, -0.016)]
    extrude(crest, -0.004, 0.004, glow("holo_crest", "#eef8ff", 1.6), (hx + 0.066, hy, 0.305), (math.pi / 2, 0, 0))
    for (x, y) in ((0.3, -0.08), (-0.06, -0.62), (0.62, -0.28), (-0.66, -0.12)):  # light masts by the avenues
        cy(0.007, 0.16, (x, y, 0.08), flat("mast", "#d0d4da", 0.5), 6)
        bx((0.022, 0.022, 0.022), (x, y, 0.17), glow("lamp8", "#bfe8ff", 3.0), bev=0)
    for (x, y, s_) in ((0.41, -0.02, 0.045), (0.36, 0.03, 0.035), (-0.02, 0.18, 0.04)):  # (in sight of the camera)
        bx((s_, s_ * 1.4, s_), (x, y, s_ / 2 + 0.015), flat("crate8", "#b8862e", 0.6), bev=0)


# ------------------------------------------------------------------ RESIDENCES (capital, scale 1.0)


def residence_dl1(team):
    """The chieftain's camp, «Raivon Soft» (plan step B2): the big reed shalash and the small hut end in round
    thatch tufts (not needle points), their door holes a warm dark brown (no near-black), the poles, spit and rack
    sticks at least 0.02 thick (the roasting spit is gone), a fat pot, a round fir, the banner ×1.3."""
    pad(0.78, tex("plaster", DIRT, 1.2), 0.008, 14, 0.1, 11)
    hole = flat("hole", "#3b2a1f", 0.95)  # a warm dark door hole (§6.1: no albedo near black; was #1e140c)

    def tiers(r, top, n, z_top=None):
        """A cone of thatch laid in n tiers, each lower rim kicked out over the tier below (bundles of reed), tied
        off at the top in a round tuft of 0.14 r."""
        k = r / top
        zs = [top * i / n * 0.92 for i in range(n)] + [top]
        for i in range(n):
            z0, z1 = zs[i], min(top, zs[i + 1] + 0.03)
            r0, r1 = r - k * z0 + (0.025 if i else 0.0), max(0.012, r - k * z1)
            cy(r0, z1 - z0, (0, 0, (z0 + z1) / 2), tex("wood", shade(THATCH, 1.0 if i % 2 == 0 else 0.88), 2.5), 10, r2=r1)
        ico(0.14 * r, (0, 0, top - 0.11 * r), tex("wood", shade(THATCH, 0.94), 2.5), (1, 1, 0.85))
        return k

    def shalash():
        k = tiers(0.36, 0.72, 4)
        cy(0.36 - k * 0.11 + 0.007, 0.05, (0, 0, 0.135), flat("band" + team, shade(team, 0.85), 0.7), 10,
           r2=0.36 - k * 0.16 + 0.007)  # a team-painted band hugging the lowest tier
        wd = tex("wood", WOOD_D)
        for kk in range(6):
            a = kk * math.tau / 6 + 0.3
            beam((math.cos(a) * 0.36, math.sin(a) * 0.36, 0.0), (-math.cos(a) * 0.05, -math.sin(a) * 0.05, 0.8), 0.022, wd)
        mesh_obj([(-0.085, -0.352, 0.0), (0.085, -0.352, 0.0), (0.0, -0.262, 0.2), (-0.085, -0.362, 0.0), (0.085, -0.362, 0.0), (0.0, -0.272, 0.2)],
                 [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)], hole)
        # a team cloth hung over the door, with a white stripe: two panels laid on the two thatch facets that meet
        # above the door (the tier is a ten-sided frustum with an edge at −Y), so the cloth hugs the thatch
        from mathutils import Vector

        def rr(z):  # radius of the second tier's corners at height z
            return 0.3022 + (0.1794 - 0.3022) * (z - 0.1656) / (0.3612 - 0.1656)

        def cloth(za, zb, f, lift, mt):
            mb = _MB()
            for a0, a1, fa, fb in ((234, 270, 1 - f, 1.0), (270, 306, 0.0, f)):
                ca, cb = (Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0)) for a in (a0, a1))

                def P(z, t):
                    p = (ca * rr(z)).lerp(cb * rr(z), t)
                    p.z = z
                    return p
                q = [P(za, fa), P(za, fb), P(zb, fb), P(zb, fa)]
                nrm = (q[1] - q[0]).cross(q[3] - q[0]).normalized()
                if nrm.dot(ca + cb) < 0:
                    nrm = -nrm
                mb.face([p + nrm * lift for p in q], nrm)
            mb.obj(mt, "cloth")
        cloth(0.25, 0.322, 0.45, 0.004, flat("flag" + team, team, 0.7))
        cloth(0.262, 0.274, 0.45, 0.0065, flat("emblem", WHITE, 0.6))  # a white stripe woven across the hem
    build_at(shalash, 0.0, 0.2)

    def small_hut():
        tiers(0.15, 0.32, 2)
        wd = tex("wood", WOOD_D)
        for kk in range(3):
            a = kk * math.tau / 3 + 0.5
            beam((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.0), (-math.cos(a) * 0.03, -math.sin(a) * 0.03, 0.4), 0.02, wd)
        bx((0.066, 0.012, 0.1), (0, -0.142, 0.048), hole, bev=0, rot=(0.42, 0, 0))
    build_at(small_hut, 0.52, 0.47, 0.3)

    def hide_rack():  # a hide stretched to dry on a pole frame (stout 0.024 poles, a 0.012 hide)
        wd = tex("wood", WOOD_D)
        for sx in (-1, 1):
            cy(0.012, 0.27, (sx * 0.1, 0, 0.135), wd, 6)
        cy(0.01, 0.25, (0, 0, 0.255), wd, 6, rot=(0, math.pi / 2, 0))
        bx((0.16, 0.012, 0.17), (0, 0, 0.15), flat("hide", "#cdb08a", 0.9), bev=0)
        bx((0.07, 0.015, 0.06), (0.02, 0.0, 0.17), flat("hide_d", "#9c7b56", 0.9), bev=0)
    build_at(hide_rack, -0.42, 0.18, 0.6)
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
        # (the roasting spit on its 0.012 sticks is gone: §6.1, nothing that thin) — a fat clay pot by the fire
        ico(0.042, (0.14, 0.07, 0.034), flat("pot", "#9a5a36", 0.8), (1, 1, 0.85))
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
    toy_pine(-0.6, 0.3, 1.0, 3)


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
        gable_roof(0.16, 0.12, 0.08, (0, -0.31, 0.24), shade(team, 0.85), tex("wood", WOOD_L, 3.0), rz=math.pi / 2,
                   oh=0.025, ohx=0.02, n=3, tk=0.014, ct=0.014, kind="wood", barge=WHITE, gable_timber=None, eave_z=0.0,
                   **SOFT_ROOF)
        bench(0.13, -0.3, math.pi / 2)
        # the izba's door at the top of the porch steps: half the log wall high, in the team colour, white frame
        build_at(lambda: doorway(0, 0, 0, 0.064, 0.16, door_c=shade(team, 0.62), step=None, frame=WHITE, wall=LOG),
                 0, -0.275, 0, z=0.105)
    build_at(main, 0.0, 0.2)
    build_at(lambda: log_house(0.24, 0.2, 0.15, team, chimney=False, n_win=1), -0.48, -0.26, 0.5)
    build_at(lambda: barn(team, coursed=True), 0.46, -0.22, -0.5, 0.8)
    build_at(well, -0.12, -0.46, 0.2)
    well_roof(-0.12, -0.46, 0.2, team)
    plank_fence([(-0.62, 0.02), (-0.3, 0.48)], 0.13)  # a board fence with pointed pickets round the back yard
    plank_fence([(0.62, 0.02), (0.3, 0.5)], 0.13)
    build_at(lambda: woodpile(2), -0.6, -0.04, 1.2, 0.8)
    for (x, y) in ((-0.152, -0.128), (-0.196, -0.152)):  # barrels and a crate by the porch, clear of the log corner
        cy(0.022, 0.05, (x, y, 0.025), tex("wood", WOOD), 8)
        cy(0.023, 0.006, (x, y, 0.038), flat("band", "#3d3f45", 0.5), 8)
    bx((0.04, 0.04, 0.036), (-0.142, -0.178, 0.018), tex("wood", WOOD_L), 0.35, 0)
    banner(0.34, -0.42, 0.85, team, 0.15)
    banner(-0.36, 0.0, 0.85, team, 0.15)
    tree(0.14, 0.66, 0.9)


def residence_dl3(team):
    """The terem court with its white-stone kremlin wall, «Raivon Soft» (plan step B2): roofs 45–60 % of each block's
    height (the tower block lower and wider), onions ending in balls, a big door at the top of the porch, a thick soft
    wall (×1.1) with three fat round-headed merlons a side (×1.6), corner turrets ×1.25 under coursed cones with
    gilt balls, banners ×1.3, no post or slab thinner than 0.014."""
    pad(0.82, stone(COBBLE, 1.8), 0.014, 14, 0.04, 13)
    bx((0.74, 0.5, 0.05), (0, 0.16, 0.025), stone("#d8cfbe", 1.5), bev=0.01)
    build_at(lambda: terem_block(0.36, 0.3, 0.2, 0.22, team, 0.42, rich=True), 0.0, 0.2)
    build_at(lambda: terem_block(0.26, 0.24, 0.16, 0.16, team, 0.28, dome_team=True, rich=True), -0.38, 0.06)
    build_at(lambda: terem_block(0.2, 0.2, 0.24, 0.16, team, 0.36, dome_team=True, rich=True), 0.35, 0.26)
    # covered gallery joining the wing to the main terem
    gm = tex("wood", "#c98d4a", 2.5)
    bx((0.16, 0.1, 0.08), (-0.2, 0.06, 0.25), gm, bev=0.006)
    gable_roof(0.16, 0.1, 0.06, (-0.2, 0.06, 0.29), slate(team, 1.00), gm, oh=0.02, ohx=0.01, n=3, tk=0.014, ct=0.014,
               gable_timber=None, eave_z=0.0, **SOFT_ROOF)
    for x in (-0.26, -0.14):
        cy(0.014, 0.25, (x, 0.06, 0.125), gm, 6)
    # front porch with a tent roof, and the door at the top of its steps (half the stone storey and more)
    for i in range(3):
        bx((0.16, 0.05, 0.04), (0, -0.0 - i * 0.045, 0.13 - i * 0.04), stone("#ece4d4"), bev=0)
    for sx in (-1, 1):
        cy(0.014, 0.28, (sx * 0.07, -0.08, 0.14 + 0.05), gm, 6)
    coursed_hip(0.16, 0.12, 0.12, (0, -0.05, 0.33), slate(team, 1.00), oh=0.02)
    fc = frame_c(WHITE)
    build_at(lambda: (arch_slab(0.1, 0.165, -0.004, 0.0, flat("frame" + fc, fc, 0.85), sides=False),
                      arch_slab(0.08, 0.15, -0.007, 0.0, flat("door" + team, shade(team, 0.62), 0.8), sides=False)),
             0, 0.05, 0, z=0.15)
    # the white-stone enclosure of an early stone keep (кремль): a crenellated wall round the back of the court
    # with tent-roofed corner turrets
    ws, wd_ = stone("#e6dece", 1.2), stone("#c9bfae", 1.2)
    WT, WH, MW, MH = 0.055, 0.13, 0.058, 0.064  # wall ×1.1 thick; merlons ×1.6
    pts = [(math.cos(math.radians(a)) * 0.72, math.sin(math.radians(a)) * 0.72 + 0.04) for a in (14, 52, 90, 128, 166)]
    for j, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
        L = math.dist((x0, y0), (x1, y1))
        ang = math.atan2(y1 - y0, x1 - x0)
        dz = 0.004 * (j % 2)  # neighbouring segments overlap at the joints: no two wall tops in one plane
        bx((L + WT, WT, WH + dz), ((x0 + x1) / 2, (y0 + y1) / 2, (WH + dz) / 2), ws, ang, soft=True)
        blocked = [(0.0, 0.105 if j == 0 else 0.03), (L - (0.105 if j == len(pts) - 2 else 0.03), L)]
        round_merlons((x0, y0), (x1, y1), merlon_us(free_spans(L, blocked), MW, 0.07), MW, MH, WT, WH + dz, ws, seg=2)
    for (x, y) in (pts[0], pts[-1]):
        castle_tower(x, y, 0.085, 0.24, team, slate(team, 1.0), rc=0.112, hc=0.25, st=ws, dk=wd_, sides=10)
    banner(-0.3, -0.45, 0.8, team, 0.15)
    banner(0.3, -0.45, 0.8, team, 0.15)
    tree(0.56, -0.2, 0.85)
    tree(-0.6, -0.3, 0.8)


def coursed_cone(x, y, z0, r, h, roof_c, rings=COURSES, sides=16, lip=0.006, band=0.78, butt_k=BUTT_K, eave=0.007,
                 finial=GOLD):
    """A tower's cone roof laid in courses of slates (the steep tower roofs of reference frame 4): the lower edge of
    each course stands a lip proud of the one below, the courses alternate two tones and the top of each darkens a
    little just under the next course's edge (the shadow line the high game camera reads, as course_rows does on the
    flat roofs). The eave course flares out by `eave` (it also covers the merlon tops). Open at the bottom: the tower
    top closes it. «Raivon Soft» (§6.8, plan step B1): 3 fat courses on a smooth 16-sided cone and, with finial (a
    colour), a round ball of 0.12 r (an ico sphere, subdivision 2) on the tip instead of the needle point.
    Returns the height of the cone's tip."""
    mbs, butt = [_MB(), _MB()], _MB()

    def P(rr, z, a):
        return (x + rr * math.cos(a), y + rr * math.sin(a), z)
    for k in range(rings):
        last = k == rings - 1
        fa, fb = k / rings, (1.0 if last else (k + 1.18) / rings)
        za, zb = z0 + h * fa, z0 + h * fb
        ra, rb = r * (1 - fa) + (eave if k == 0 else lip), r * (1 - fb)
        fm = (k + band) / rings
        lam = (fm - fa) / (fb - fa)
        zm, rm = za + (zb - za) * lam, ra + (rb - ra) * lam
        for i in range(sides):
            a0, a1 = math.tau * i / sides, math.tau * (i + 1) / sides
            am = (a0 + a1) / 2
            n = (math.cos(am), math.sin(am), r / h)
            if last:
                mbs[k % 2].face([P(ra, za, a0), P(ra, za, a1), P(0.0, zb, 0.0)], n)
            else:
                mbs[k % 2].face([P(ra, za, a0), P(ra, za, a1), P(rm, zm, a1), P(rm, zm, a0)], n)
                butt.face([P(rm, zm, a0), P(rm, zm, a1), P(rb, zb, a1), P(rb, zb, a0)], n)
    for mb, mt in zip(mbs, _roof_mats(roof_c, 0.86)):
        mb.obj(mt, "cone_courses")
    butt.obj(tex("roof", shade(roof_c, butt_k), 1.6), "cone_butts")
    if finial:
        ball(x, y, z0 + h, 0.12 * r, finial)
    return z0 + h


def ball(x, y, z_tip, rf, color=GOLD):
    """A round gilt ball finial (ico sphere, subdivision 2) of radius rf sitting on a tip at z_tip (it swallows the
    point: «Raivon Soft» towers end in balls, not needles)."""
    return ico(rf, (x, y, z_tip + rf * 0.55), flat("gold", color, 0.35), sub=2)


def castle_tower(x, y, r, h, team, roof_c, rc=None, hc=None, z0=0.0, wins=(-math.pi / 2,), corbel=False, st=None,
                 dk=None, sides=14, win_z=None):
    """«Raivon Soft» (plan step B2) round tower of the capitals: a body of radius r from z0 up to h, a fat corbelled
    crown band under a wide coursed cone (base rc ≈ 1.32 r, height hc ≈ 2.4 rc: a friendly witch's hat, not the old
    3.4 r needle) that ends in a gilt ball (coursed_cone), and big arched lit windows facing the angles in wins.
    corbel: the body starts mid-air on a corbel frustum (a bartizan on a wall corner); otherwise it stands on a round
    plinth (none when the body starts above the ground inside another mass). st / dk: the body and trim stone
    (default the warm sandstone of reference frame 4); win_z: the windows' height (default 0.55 up the body).
    Returns the tip height (under the ball)."""
    st = st or stone(WSTONE, 0.6)
    dk = dk or stone(WSTONE_D, 0.6)
    rc = rc or r * 1.32
    hc = hc or rc * 2.4
    if corbel:
        cy(r * 0.4, 0.1, (x, y, z0 - 0.05), dk, sides, r2=r + 0.004)
    elif z0 <= 0.0:
        cy(r + 0.016, 0.05, (x, y, 0.025), dk, sides)
    cy(r, h - z0, (x, y, (z0 + h) / 2), st, sides)
    cy(r + 0.02, 0.05, (x, y, h - 0.025), dk, sides)  # the corbelled crown under the eave
    ww = min(0.045, r * 0.5)
    for a in wins:
        arch_window(x + math.cos(a) * (r + 0.002), y + math.sin(a) * (r + 0.002),
                    win_z if win_z is not None else z0 + (h - z0) * 0.55, a + math.pi / 2, ww, ww * 1.55)
    return coursed_cone(x, y, h - 0.004, rc, hc, roof_c, sides=16 if sides >= 14 else 12)


def square_tower(x, y, w, h, team, roof_c, hr=None, finial=True, wins=((0, 0.62),)):
    """«Raivon Soft» (plan step B2) square keep tower of reference frame 4: a plinth, a soft-cornered body, a fat
    corbelled parapet band and a steep coursed slate pyramid (hr ≈ 1.6 w) whose eave covers the parapet, a gilt ball
    on top (finial; off where a banner pole rises out of the roof) and big arched lit windows: wins = (face, height
    fraction), faces 0 front (−Y), 1 right (+X), 2 back, 3 left. Returns the roof apex height."""
    st = stone(WSTONE, 0.6)
    dk = stone(WSTONE_D, 0.6)
    hr = hr or w * 1.6
    bx((w + 0.024, w + 0.024, 0.05), (x, y, 0.025), dk, bev=0.004)
    bx((w, w, h), (x, y, h / 2), st, soft="v")  # a soft mass: round corners (plinth and parapet cover its ends)
    bx((w + 0.036, w + 0.036, 0.05), (x, y, h - 0.01), dk, bev=0.006)  # corbelled parapet band
    for sd, zf in wins:
        a = sd * math.pi / 2
        arch_window(x + math.sin(a) * (w / 2 + 0.002), y - math.cos(a) * (w / 2 + 0.002), h * zf, a, 0.046, 0.072)
    coursed_hip(w + 0.02, w + 0.02, hr, (x, y, h + 0.015), roof_c, oh=0.02)
    top = h + 0.015 + hr + ROOF_T * 1.1
    if finial:
        ball(x, y, top, max(0.014, 0.085 * w))
    return top


def arch_window(x, y, z, rz, w=0.04, h=0.065, frame=None):
    """«Raivon Soft» arched lit window (plan step B2) centred at height z on a wall facing −Y rotated by rz: two flat
    arched plates (§6.1: openings are paint, not geometry), a lit pane of w × h with a round head in a frame 0.01
    wider all round in a soft shade of the warm stone (frame_c), 20 triangles."""
    fc = frame or shade(WSTONE, FRAME_K)
    build_at(lambda: arch_slab(w + 0.02, h + 0.02, -0.004, 0.0, flat("frame" + fc, fc, 0.85), sides=False), x, y, rz,
             z=z - h / 2 - 0.01)
    build_at(lambda: arch_slab(w, h, -0.007, 0.0, win_lit(), sides=False), x, y, rz, z=z - h / 2)


def round_merlons(p0, p1, us, mw, mh, depth, z0, mt, k=0.4, seg=3):
    """«Raivon Soft» crenellation (plan step B2): fat merlons whose two top corners are rounded with a radius of
    k × their width (seg segments each), so seen from the front they read as soft toy blocks with round heads, not
    sharp teeth. They stand on z0 along the wall p0 → p1, centred at distances us from p0, mw wide, mh tall and
    depth deep (centred on the wall line); all in one mesh, 34 triangles each (open underneath)."""
    L = math.dist(p0, p1)
    if L < 1e-6 or not us:
        return None
    ex, ey = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    nx, ny = -ey, ex
    rc = k * mw
    prof = [(mw / 2, 0.0)]
    prof += [(mw / 2 - rc + rc * math.cos(math.pi / 2 * i / seg), mh - rc + rc * math.sin(math.pi / 2 * i / seg))
             for i in range(seg + 1)]
    prof += [(-mw / 2 + rc + rc * math.cos(math.pi / 2 * (1 + i / seg)), mh - rc + rc * math.sin(math.pi / 2 * (1 + i / seg)))
             for i in range(seg + 1)]
    prof.append((-mw / 2, 0.0))  # counter-clockwise in (u, z): up the right side, over the round head, down the left
    mb = _MB()
    for u in us:
        cx, cy_ = p0[0] + ex * u, p0[1] + ey * u

        def P(pu, pz, sd):
            return (cx + ex * pu + nx * sd * depth / 2, cy_ + ey * pu + ny * sd * depth / 2, z0 + pz)
        for sd in (-1, 1):
            mb.face([P(pu, pz, sd) for pu, pz in prof], (nx * sd, ny * sd, 0.0))
        for (u0, w0), (u1, w1) in zip(prof, prof[1:]):
            mb.face([P(u0, w0, -1), P(u1, w1, -1), P(u1, w1, 1), P(u0, w0, 1)],
                    (ex * (w1 - w0), ey * (w1 - w0), u0 - u1))
    return mb.obj(mt, "merlons")


def free_spans(L, blocked, margin=0.012):
    """The free stretches of a wall of length L once the intervals in `blocked` (towers standing on it, in distance
    along the wall) are taken out, each shrunk by margin: [(u0, u1), ...]."""
    spans, a = [], 0.0
    for b0, b1 in sorted(blocked):
        if b0 - margin > a:
            spans.append((a, b0 - margin))
        a = max(a, b1 + margin)
    if a < L:
        spans.append((a, L))
    return spans


def merlon_us(spans, mw, gap):
    """Merlon centres for the free wall stretches: as many mw-wide merlons with gaps of at least `gap` as fit in each
    stretch, spread evenly with a half gap at both ends."""
    us = []
    for u0, u1 in spans:
        n = int((u1 - u0 + gap) / (mw + gap) + 1e-6)
        if n <= 0:
            continue
        pitch = (u1 - u0) / n
        us += [u0 + pitch * (i + 0.5) for i in range(n)]
    return us


def toy_pine(x, y, s=1.0, seed=0):
    """«Raivon Soft» fir for the capitals (§6.8, after env_assets.tall_pine but cheap): a visible trunk and three fat
    tiers, each a round skirt scalloped r·(1 + 0.1·cos 6θ) with a rolled lip under the rim and a small apex ring
    inside the tier above, a ball on top, in the conifer greens of §6.3 (deep tiers below, lit ones above). ≈ 150
    triangles."""
    rnd = random.Random(seed)
    rot = rnd.uniform(0, math.tau)
    cy(0.026 * s, 0.11 * s, (x, y, 0.055 * s), tex("wood", "#7b5536", 2.0), 6)
    tiers = [(0.15, 0.08, 0.25, "#2E6B3E"), (0.118, 0.17, 0.33, "#3F8A47"), (0.083, 0.255, 0.4, "#4E9A4C")]
    n, na = 12, 6
    for r, z0, z1, c in tiers:
        r, z0, z1 = r * s, z0 * s, z1 * s
        lip = 0.1 * r
        verts = [(x + 0.2 * r * math.cos(rot + math.tau * k / na), y + 0.2 * r * math.sin(rot + math.tau * k / na), z1)
                 for k in range(na)]
        for k in range(n):
            a = rot + math.tau * k / n
            rr = r * (1 + 0.1 * math.cos(6 * (a - rot)))
            verts.append((x + rr * math.cos(a), y + rr * math.sin(a), z0))
        for k in range(n):
            a = rot + math.tau * k / n
            rr = r * (1 + 0.1 * math.cos(6 * (a - rot))) - lip
            verts.append((x + rr * math.cos(a), y + rr * math.sin(a), z0 - lip))
        S, Lp = na, na + n
        faces = []
        for i in range(na):
            for j in range(2):
                faces.append((i, S + (2 * i + j) % n, S + (2 * i + j + 1) % n))
            faces.append((i, S + (2 * i + 2) % n, (i + 1) % na))
        for k in range(n):
            faces.append((S + k, Lp + k, Lp + (k + 1) % n, S + (k + 1) % n))
        o = mesh_obj(verts, faces, flat("pine_" + c, c, 0.85))
        for p_ in o.data.polygons:
            p_.use_smooth = True
        o["round"] = True
    ico(0.032 * s, (x, y, (tiers[-1][2] + 0.012) * s), flat("pine_tip", "#8CC152", 0.85), sub=2)


def slits(items, mt=None, one_side=False):
    """Arrow slits as two flat quads each (both faces of the wall), all in one mesh: a box per slit spent 12
    triangles on faces buried in the masonry. items: (x, y, z, ang, through, w, h), the slit centred on the wall
    line at (x, y), the wall running along ang and `through` thick."""
    mb = _MB()
    for (x, y, z, ang, th, w, h) in items:
        e = (math.cos(ang), math.sin(ang), 0.0)
        n = (-e[1], e[0], 0.0)
        for s in ((-1,) if one_side else (1, -1)):
            c = (x + n[0] * th / 2 * s, y + n[1] * th / 2 * s)
            pts = [(c[0] + e[0] * w / 2 * a, c[1] + e[1] * w / 2 * a, z + h / 2 * b) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            mb.face(pts, (n[0] * s, n[1] * s, 0.0))
    mb.obj(mt or flat("slit", "#1c1a19", 0.9), "slits")


def lean_to(A, B, C, D, roof_c, n=COURSES, kind="roof", tk=0.015, ct=0.015):
    """A mono-pitch roof laid in courses like the gable roofs: eave edge A→B (low), top edge D→C (high), a slab
    under the courses with its eave and verge edges showing."""
    from mathutils import Vector
    A, B, C, D = (Vector(p) for p in (A, B, C, D))
    N = (B - A).cross(D - A).normalized()
    if N.z < 0:
        N = -N
    slab = _MB()
    At, Bt, Ct, Dt = A + N * tk, B + N * tk, C + N * tk, D + N * tk
    e = (B - A).normalized()
    s_ = (D - A).normalized()
    slab.face([A, B, C, D], -N)
    slab.face([A, B, Bt, At], -s_)
    slab.face([A, D, Dt, At], -e)
    slab.face([B, C, Ct, Bt], e)
    slab.obj(tex(kind, shade(roof_c, 0.72), 1.6), "lean_slab")
    MBs, BUTT = [_MB(), _MB()], _MB()
    course_rows(MBs, At, Bt, Ct, Dt, n, ct, butt=BUTT, band=0.8, nose=NOSE)
    for mb, mt in zip(MBs, _roof_mats(roof_c, 0.84, kind)):
        mb.obj(mt, "lean_courses")
    BUTT.obj(tex(kind, shade(roof_c, BUTT_K), 1.6), "lean_butts")


def barrel(x, y, s=1.0):
    """A cask (staves in the wood grain)."""
    cy(0.021 * s, 0.05 * s, (x, y, 0.025 * s), tex("wood", "#8d5f35", 4.0), 8)


def crate(x, y, s, rz=0.0):
    bx((s, s, s), (x, y, s / 2), tex("wood", "#a77b48", 5.0), rz, 0)
    bx((s + 0.002, s * 0.18, s + 0.002), (x, y, s / 2), tex("wood", WOOD_D, 3.0), rz, 0)


def hand_cart(team):
    """A two-wheeled cart heaped with hay, its shafts on the ground (local: shafts towards −X). «Raivon Soft» (plan
    step B2): chunky — 0.014 wheels on 0.02 hubs, 0.02 side boards and shafts (was 0.008 / 0.01 sticks)."""
    wd = tex("wood", "#8a5e36", 2.5)
    dk = tex("wood", WOOD_D, 2.0)
    bx((0.13, 0.085, 0.016), (0.0, 0, 0.055), wd, bev=0)
    for sy in (-1, 1):
        bx((0.13, 0.014, 0.032), (0.0, sy * 0.043, 0.075), wd, bev=0)
        cy(0.036, 0.014, (0.0, sy * 0.056, 0.036), dk, 10, rot=(math.pi / 2, 0, 0))
        cy(0.014, 0.022, (0.0, sy * 0.058, 0.036), wd, 6, rot=(math.pi / 2, 0, 0))
        beam((-0.06, sy * 0.03, 0.05), (-0.17, sy * 0.034, 0.012), 0.02, dk)
    uvs(0.065, (0.005, 0, 0.095), tex("wood", THATCH, 3.0), 10, 5, (1.2, 0.8, 0.65))


def smithy(team):
    """A lean-to forge against a wall (local: the wall behind at +Y, open to −Y): timber posts, a slate lean-to
    roof, a stone hearth with glowing coals under a stone chimney (a smoke marker), an anvil on a stump and a quench
    tub — the busy castle yard of reference frame 4."""
    wd = tex("wood", WOOD, 2.5)
    st = stone(WSTONE_D, 0.9)
    for sx in (-1, 1):
        bx((0.02, 0.02, 0.16), (sx * 0.1, -0.06, 0.08), wd, bev=0)
    bx((0.22, 0.02, 0.02), (0, -0.06, 0.155), wd, bev=0)
    lean_to((-0.125, -0.085, 0.152), (0.125, -0.085, 0.152), (0.125, 0.075, 0.22), (-0.125, 0.075, 0.22),
            slate(team, 0.94), n=3)
    bx((0.09, 0.07, 0.065), (-0.05, 0.035, 0.0325), st, bev=0)
    bx((0.07, 0.05, 0.012), (-0.05, 0.03, 0.068), glow("forge", "#ff8a2a", 3.0), bev=0)
    top = chimney(-0.05, 0.05, 0.065, 0.36, 0.05, st)
    smoke_at(-0.05, 0.05, top + 0.01)
    # «Raivon Soft» (plan step B2): one chunky anvil on its stump and a fat quench tub (the 0.014 anvil bar and the
    # water disc were specks at game size)
    cy(0.024, 0.036, (0.05, -0.02, 0.018), tex("wood", "#6a4327", 3.0), 8)
    bx((0.05, 0.026, 0.024), (0.05, -0.02, 0.048), flat("anvil", "#5d6470", 0.6), bev=0.006)
    cy(0.03, 0.034, (0.1, 0.03, 0.017), tex("wood", "#8d5f35", 4.0), 10)


def residence_dl4(team):
    """The castle of reference frame 4 — square front towers, an arched gate, warm sandstone, eagle banners — as a
    chunky «Raivon Soft» toy (plan step B2): fewer, bigger towers (radius ×1.25) under fat coursed roofs that make
    45–60 % of each building's height and end in gilt balls, thick soft curtain walls (×1.1) with 3–5 fat
    round-headed merlons a side (×1.6), big arched windows (≤ 3 a face), a gate half the gatehouse wall high, banners
    ×1.3, and no stick, slit or bar thinner than 0.02 (the hoardings, portcullis, arrow slits and pennants are gone)."""
    pad(0.84, stone("#a48c6c", 1.2), 0.014, 14, 0.03, 14)  # warm paved court
    # the big pale flagstones of reference frame 4's castle yard (it shows round the keep from the game camera), and
    # a flagged road out of the gate that widens towards the edge and lies almost flush, in a tone between the two
    flags = stone("#c9b38e", 0.9)
    bx((0.86, 0.86, 0.006), (0, 0, 0.017), flags, bev=0)
    extrude([(-0.1, -0.6), (0.1, -0.6), (0.152, -0.795), (-0.152, -0.795)], 0.012, 0.0155, stone("#b9a17d", 0.9))
    st = stone(WSTONE, 0.6)  # larger blocks that survive the bake (reference frame 4 shows every stone)
    dk = stone(WSTONE_D, 0.6)
    roof_c = slate(team, 0.94)
    H = 0.44  # the curtain's corners (was 0.48: the ×1.25 towers stay inside the 0.86 pad)
    WT, WH = 0.088, 0.26  # curtain thickness (×1.1) and height
    MW, MH, MG = 0.115, 0.096, 0.07  # merlon width and height (×1.6), the least gap between merlons
    SQ, RT = 0.24, 0.125  # front square towers and back round towers (×1.25)
    GW, GD, GH = 0.24, 0.18, 0.3  # the gatehouse
    sq, rt = SQ / 2 + 0.018, RT + 0.02  # how far the towers' parapet / crown reach along a wall from its corner
    walls = [((-H, -H), (-GW / 2, -H), [(0.0, sq)]),  # the front curtain either side of the gate
             ((GW / 2, -H), (H, -H), [(H - GW / 2 - sq, H - GW / 2)]),
             ((H, -H), (H, H), [(0.0, sq), (2 * H - rt, 2 * H)]),
             ((H, H), (-H, H), [(0.0, rt), (2 * H - rt, 2 * H)]),
             ((-H, H), (-H, -H), [(0.0, rt), (2 * H - sq, 2 * H)])]
    for p0, p1, blocked in walls:
        L = math.dist(p0, p1)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        bx((L + WT, WT, WH), ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, WH / 2), st, ang, soft=True)
        round_merlons(p0, p1, merlon_us(free_spans(L, blocked), MW, MG), MW, MH, WT, WH, st)
    # front corners: square towers with steep slate pyramids (reference frame 4) carrying the banners; back corners
    # round towers under fat cones
    for (x, y) in ((-H, -H), (H, -H)):
        square_tower(x, y, SQ, 0.46, team, roof_c, hr=0.4, wins=((0, 0.6), (3 if x < 0 else 1, 0.6)))
    for (x, y) in ((H, H), (-H, H)):
        castle_tower(x, y, RT, 0.44, team, roof_c, rc=0.165, hc=0.4, wins=(-math.pi / 2, 0.0 if x > 0 else math.pi))
    # the gatehouse: its gable to the front over a big arched gate (≈ 57 % of its wall), lit by two lanterns
    gy = -H - GD / 2  # its front face
    bx((GW, GD, GH), (0, -H, GH / 2), st, soft="v")  # soft masses: the gatehouse, the keep, the hall
    gable_roof(GD, GW, 0.25, (0, -H, GH), roof_c, st, rz=math.pi / 2, oh=0.03, ohx=0.04, gable_timber=None,
               eave_z=0.0, **SOFT_ROOF)
    sur = flat("gate_sur", shade(WSTONE_D, 0.92), 0.85)
    gl = mat("gate_glow", "#8a5426", 0.7, emission="#e0863a", emit_strength=0.45)  # torch-lit passage, not a lamp
    build_at(lambda: arch_slab(0.155, 0.195, -0.004, 0.0, sur, sides=False), 0, gy, 0)
    build_at(lambda: arch_slab(0.125, 0.17, -0.007, 0.0, gl, sides=False), 0, gy, 0)
    arch_window(0, gy - 0.002, GH + 0.085, 0, 0.042, 0.06)  # a lit window in the gable
    for k in range(2):  # steps down to the square
        bx((0.21 - k * 0.04, 0.04, 0.016 * (k + 1)), (0, gy - 0.06 + k * 0.035, 0.008 * (k + 1)), dk, bev=0.004)
    for sx in (-1, 1):  # chunky lanterns either side of the gate
        bx((0.022, 0.03, 0.024), (sx * 0.1, gy - 0.012, 0.19), dk, bev=0)
        uvs(0.02, (sx * 0.1, gy - 0.03, 0.2), glow("torch", "#ffb347", 4.0), 8, 5)
    # the keep: a big coursed slate roof (46 % of its height) with two lit dormers, round bartizans on its front
    # corners and a central tower rising through the ridge; one long eagle banner between two arched windows
    KX, KY, KW, KD, KH, KR = 0.04, 0.12, 0.46, 0.32, 0.5, 0.42
    kf = KY - KD / 2
    bx((KW, KD, KH), (KX, KY, KH / 2), st, soft="v")
    gable_roof(KW, KD, KR, (KX, KY, KH), roof_c, st, oh=0.065, ohx=0.045, tk=0.02, ct=0.02, gable_timber=None,
               eave_z=0.0, **SOFT_ROOF)
    for sx in (-1, 1):
        arch_window(KX + sx * 0.094, kf - 0.002, 0.34, 0, 0.05, 0.08)
        arch_window(KX + sx * 0.15, KY + KD / 2 + 0.002, 0.34, math.pi, 0.05, 0.08)  # the back (AI capitals face away)
        arch_window(KX + sx * (KW / 2 + 0.002), KY, 0.34, sx * math.pi / 2, 0.05, 0.08)
    flag_at("flagt", KX, kf - 0.007, 0.47 - 0.143, 0.117, 0.286, 0.014)
    bx((0.117, 0.012, 0.286), (KX, kf - 0.007, 0.47 - 0.143), flat("flag" + team, team, 0.7), bev=0)
    bx((0.14, 0.02, 0.02), (KX, kf - 0.01, 0.475), flat("pole", "#d9d2c3", 0.5), bev=0)
    for sx in (-1, 1):  # dormers on the front slope, each with a lit window
        dx = KX + sx * 0.1
        bx((0.08, 0.12, 0.2), (dx, kf + 0.04, KH + 0.2), st, bev=0)
        arch_window(dx, kf - 0.022, KH + 0.235, 0, 0.036, 0.05)
        gable_roof(0.12, 0.08, 0.055, (dx, kf + 0.04, KH + 0.3), roof_c, st, rz=math.pi / 2, oh=0.016, ohx=0.012, n=2,
                   tk=0.014, ct=0.014, gable_timber=None, eave_z=0.0, barge=None, **SOFT_ROOF)
    cxk, cyk = KX - 0.15, KY + 0.09
    chimney(cxk, cyk, KH + 0.2, KH + roof_surface(0.09, KD / 2, KR, 0.065, 0.0, 0.02, 0.02) + 0.06, 0.05,
            stone(WSTONE_D, 0.8))
    for sx in (-1, 1):
        castle_tower(KX + sx * KW / 2, kf, 0.1, 0.56, team, roof_c, rc=0.13, hc=0.31, z0=0.28, corbel=True,
                     wins=(-math.pi / 2,), sides=12)
    castle_tower(KX, 0.19, 0.106, 1.06, team, roof_c, rc=0.14, hc=0.34, z0=KH + 0.1, wins=(-math.pi / 2, math.pi / 2),
                 win_z=0.97)  # the tall central tower, rising through the ridge
    # the great hall behind the keep: warm stone under a coursed slate roof, a door half its wall high, lit windows

    def hall():
        w, d, h = 0.3, 0.22, 0.28
        bx((w, d, h), (0, 0, h / 2), stone(WSTONE, 1.0), soft="v")
        bx((w + 0.02, d + 0.02, 0.035), (0, 0, 0.0175), stone(STONE_D), bev=0)
        gable_roof(w, d, 0.24, (0, 0, h), roof_c, stone(WSTONE, 1.0), oh=0.04, ohx=0.03, gable_timber=None,
                   **SOFT_ROOF)
        arch_slab(0.075 * DOOR_K, 0.14, -d / 2 - 0.005, -d / 2, tex("wood", WOOD_D), sides=False)
        for sx in (-1, 1):
            arch_window(sx * w * 0.32, -d / 2 - 0.002, h * 0.55, 0, 0.046, 0.07)
        arch_window(-w / 2 - 0.002, 0, h * 0.55, -math.pi / 2, 0.046, 0.07)
    build_at(hall, -0.25, 0.29)
    # the busy outer bailey: a forge against the west curtain, a hay cart, a haystack, fat casks and crates by the
    # gate, round firs (reference frames 3 and 4)
    build_at(lambda: smithy(team), -0.56, 0.2, -math.pi / 2)
    build_at(lambda: hand_cart(team), -0.62, -0.24, math.pi / 2 + 0.25)
    haystack(-0.64, -0.03, 0.62)
    barrel(-0.6, 0.4, 1.4)
    crate(-0.58, 0.04, 0.056, 0.3)
    for x in (0.24, -0.25):  # casks and a crate stacked outside the gate
        barrel(x, -0.6, 1.4)
    crate(0.29, -0.56, 0.056, 0.2)
    toy_pine(0.64, 0.2, 1.0, 1)
    toy_pine(-0.08, 0.66, 0.95, 2)
    # the great hanging banners of reference frame 4 (×1.3 in banner()), clear of the towers' silhouettes: the great
    # one on a pole beside the central tower flying over the keep's right wing, a second one over the back-left
    # round tower hanging outwards
    banner(KX + 0.165, 0.19, 1.58, team, 0.3, z0=0.6)
    banner(-H, H, 1.3, team, 0.2, side=-1, z0=0.8)


def wedge(w, d, h, loc, mt, rz=0.0):
    """A plain triangular prism, ridge along local X (a dormer roof or a pediment): 8 triangles."""
    hw, hd = w / 2, d / 2
    return mesh_obj([(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0), (-hw, 0, h), (hw, 0, h)],
                    [(0, 1, 5, 4), (3, 4, 5, 2), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)], mt, loc, (0, 0, rz))


def iron_fence(x0, x1, y, h, gaps=(), step=0.034):
    """A wrought-iron railing along X at y: two rails and flat bars with spear tips (both faces), skipping the
    x-ranges in gaps (gates, piers)."""
    iron = flat("iron", "#2b2d31", 0.6)
    mb = _MB()
    spans, a = [], x0
    for g0, g1 in sorted(gaps):
        spans.append((a, g0))
        a = g1
    spans.append((a, x1))
    for s0, s1 in spans:
        if s1 - s0 < 0.02:
            continue
        for z in (0.035, h - 0.012):
            bx((s1 - s0, 0.007, 0.007), ((s0 + s1) / 2, y, z), iron, bev=0)
        k = max(1, round((s1 - s0) / step))
        for i in range(k):
            x = s0 + (i + 0.5) * (s1 - s0) / k
            for sd in (-1, 1):
                yy = y + sd * 0.002
                mb.face([(x - 0.003, yy, 0.014), (x + 0.003, yy, 0.014), (x + 0.003, yy, h), (x, yy, h + 0.012),
                         (x - 0.003, yy, h)], (0, sd, 0))
    mb.obj(iron, "railing")


def parterre(x, y, w, d, flower):
    """A clipped box-hedge bed with a lawn inside (the dark border reads as a ring from above) and a flower
    knot in the middle."""
    bx((w, d, 0.034), (x, y, 0.017), flat("hedge", "#2f6a2c", 0.85), bev=0)
    bx((w - 0.026, d - 0.026, 0.038), (x, y, 0.019), tex("plaster", "#6aa543", 2.0), bev=0)
    q = min(w, d) * 0.42
    bx((q, q, 0.044), (x, y, 0.022), flat("flowers_" + flower, flower, 0.8), math.pi / 4, bev=0)


def topiary(x, y, s=1.0):
    cy(0.02 * s, 0.03 * s, (x, y, 0.015 * s), stone("#c9bca6", 1.4), 6)
    cn(0.03 * s, 0.11 * s, (x, y, 0.085 * s), flat("topiary", "#2c6630", 0.85), 6)


def statue(x, y, z, mt):
    """A small gilded statue on a plinth (the roofline figures of a baroque palace)."""
    bx((0.022, 0.022, 0.016), (x, y, z + 0.008), flat("cornice", WHITE, 0.6), bev=0)
    cy(0.008, 0.036, (x, y, z + 0.034), mt, 6, r2=0.006)
    ico(0.008, (x, y, z + 0.058), mt)


def residence_dl5(team):
    pad(0.86, stone("#b9b3a8", 2.2), 0.014, 14, 0.0, 15)
    bx((0.88, 0.46, 0.05), (0, 0.12, 0.025), stone("#a59d8e", 1.6), bev=0.01)
    f = facade("#e3cfa6", WIN_D, 0.068, 0.12, 0.42, 0.55, lit_p=0.35, z0=0.05)
    roof_c = slate(team, 1.00)
    wh = flat("cornice", WHITE, 0.6)
    gold = flat("gold", GOLD, 0.35)
    bx((0.62, 0.32, 0.36), (0, 0.14, 0.23), f, bev=0.01)
    bx((0.64, 0.34, 0.025), (0, 0.14, 0.41), wh, bev=0.006)
    bx((0.635, 0.335, 0.014), (0, 0.14, 0.17), wh, bev=0)  # string course between the floors
    # the roof laid in slate courses, set back behind a balustrade on the cornice, with lit dormers and chimneys
    coursed_hip(0.58, 0.28, 0.16, (0, 0.14, 0.4225), roof_c, oh=0.0, n=4)
    bal = facade(WHITE, "#77716a", 0.017, 0.04, 0.5, 0.56, lit="#77716a", lit_p=0.0, z0=0.4225)
    bx((0.6, 0.012, 0.036), (0, -0.018, 0.4405), bal, bev=0)
    for sx in (-1, 1):
        statue(sx * 0.255, -0.018, 0.4585, gold)
    for x in (-0.2, 0.2):
        bx((0.05, 0.07, 0.085), (x, 0.03, 0.47), f, bev=0)
        window(x, -0.0065, 0.478, 0, 0.026, 0.034, WHITE)
        wedge(0.08, 0.07, 0.034, (x, 0.025, 0.5125), tex("roof", roof_c, 1.6), math.pi / 2)
    for sx in (-1, 1):
        chimney(sx * 0.2, 0.24, 0.45, 0.63, 0.036, stone("#b0a594", 1.4))
    for sx in (-1, 1):  # corner pavilions with tall coursed tent roofs
        bx((0.16, 0.38, 0.44), (sx * 0.36, 0.14, 0.27), f, bev=0.01)
        bx((0.18, 0.4, 0.025), (sx * 0.36, 0.14, 0.49), wh, bev=0.006)
        bx((0.175, 0.395, 0.014), (sx * 0.36, 0.14, 0.17), wh, bev=0)
        coursed_hip(0.16, 0.38, 0.2, (sx * 0.36, 0.14, 0.5025), roof_c, oh=0.02, n=4)
        flagpole(sx * 0.36, 0.14, 0.88, team, 0.12)
    # portico: columns + pediment with gilt acroteria
    bx((0.28, 0.08, 0.04), (0, -0.05, 0.07), stone("#d8cfbe"), bev=0)
    for i in range(5):
        cy(0.016, 0.3, (-0.12 + i * 0.06, -0.06, 0.24), wh, 8)
    bx((0.3, 0.1, 0.03), (0, -0.04, 0.405), wh, bev=0)
    prism_roof("pedi", 0.1, 0.28, 0.08, (0, -0.04, 0.42), wh, overhang=0.01, rot_z=math.pi / 2)
    for (x, z) in ((0.0, 0.508), (-0.14, 0.43), (0.14, 0.43)):
        ico(0.013, (x, -0.09, z + 0.012), gold)
    for sx in (-1, 1):
        facade_banner(sx * 0.21, -0.025, 0.39, 0.07, 0.24, team)
    for k, top in enumerate((0.075, 0.055, 0.035)):  # a broad stair down from the portico to the garden walk
        bx((0.3, 0.03, top), (0, -0.103 - k * 0.028, top / 2), stone("#d8cfbe"), bev=0)
    # central clock tower with a team dome and a gilt lantern
    bx((0.17, 0.17, 0.36), (0, 0.14, 0.62), stone("#efe6d2", 1.5), bev=0.01)
    bx((0.2, 0.2, 0.025), (0, 0.14, 0.8), wh, bev=0.006)
    # dials towards the square, the park behind and the west (the player's capital stands turned +0.3 rad, which
    # brings the west face round towards the camera)
    for a in (0.0, math.pi, -math.pi / 2):
        clock_face(math.sin(a) * 0.087, 0.14 - math.cos(a) * 0.087, 0.7, a, 0.045)
    cy(0.075, 0.08, (0, 0.14, 0.85), stone("#efe6d2"), 12)
    uvs(0.095, (0, 0.14, 0.89), flat("dome" + team, team, 0.45), 12, 6, (1, 1, 0.9))
    cy(0.098, 0.012, (0, 0.14, 0.895), gold, 12)
    cy(0.028, 0.05, (0, 0.14, 1.0), wh, 8)
    cn(0.034, 0.05, (0, 0.14, 1.05), gold, 8)
    flagpole(0, 0.14, 1.32, team, 0.16)
    # the formal garden of a baroque palace: a gravel forecourt, box-hedge parterres, topiary cones, a tiered
    # fountain on the central walk, and a wrought-iron railing with gate piers and lanterns along the front
    bx((0.9, 0.5, 0.006), (0, -0.37, 0.017), tex("plaster", "#d9ccaa", 2.0), bev=0)
    bx((0.14, 0.52, 0.006), (0, -0.39, 0.0215), stone("#e4dccb", 1.6), bev=0)
    for sx in (-1, 1):
        for (y, fl) in ((-0.25, "#d9465a"), (-0.5, "#f2c84b")):
            parterre(sx * 0.25, y, 0.26, 0.17, fl)
        for (x, y) in ((0.42, -0.15), (0.42, -0.6), (0.09, -0.21), (0.09, -0.6)):
            topiary(sx * x, y, 1.0)
    fs = stone(STONE)
    cy(0.1, 0.045, (0, -0.375, 0.0225), fs, 12)
    cy(0.088, 0.004, (0, -0.375, 0.046), flat("water", "#5fb8e0", 0.15), 12)
    cy(0.016, 0.1, (0, -0.375, 0.09), fs, 6)
    cy(0.045, 0.016, (0, -0.375, 0.14), fs, 10, r2=0.03)
    cn(0.012, 0.05, (0, -0.375, 0.17), flat("jet", "#cfeefc", 0.2), 6)
    iron_fence(-0.46, 0.46, -0.66, 0.1, gaps=((-0.48, -0.44), (-0.135, 0.135), (0.44, 0.48)))
    pier = stone("#d8cfbe", 1.4)
    for sx in (-1, 1):
        bx((0.044, 0.044, 0.13), (sx * 0.11, -0.66, 0.065), pier, bev=0)
        bx((0.054, 0.054, 0.012), (sx * 0.11, -0.66, 0.136), wh, bev=0)
        bx((0.022, 0.022, 0.03), (sx * 0.11, -0.66, 0.157), glow("lamp_gas", "#ffcf7a", 3.0), bev=0)
        cn(0.02, 0.016, (sx * 0.11, -0.66, 0.18), flat("lamp_post", "#2f3237", 0.5), 4)
        bx((0.04, 0.04, 0.11), (sx * 0.46, -0.66, 0.055), pier, bev=0)
        ico(0.018, (sx * 0.46, -0.66, 0.128), gold)
        tree(sx * 0.56, 0.48, 0.85)


def sedan(x, y, rz, color):
    """A cheap parked car for the plazas: body, glass cabin, two wheel axles (a cylinder through each pair)."""
    def b():
        bx((0.1, 0.048, 0.024), (0, 0, 0.024), flat("car" + color, color, 0.4), bev=0)
        bx((0.052, 0.044, 0.022), (-0.006, 0, 0.046), flat("car_glass", "#1d2a38", 0.2), bev=0)
        for sx in (-0.032, 0.032):
            cy(0.012, 0.052, (sx, 0, 0.012), flat("tyre", "#1f1f21", 0.9), 6, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz, z=0.014)


def residence_dl6(team):
    pad(0.86, flat("asph", ASPH, 0.9), 0.014, 14, 0.0, 16)
    bx((0.94, 0.52, 0.05), (0, 0.12, 0.025), stone("#9a8f84", 1.6), bev=0.01)
    # tall window bands between stone pilasters (the vertical rhythm of a 1950s ministry tower)
    f = facade("#d8c4a0", "#34404e", 0.055, 0.1, 0.4, 0.78, lit="#ffe08a", lit_p=0.3, z0=0.05, pil=2,
               pil_c="#f1eadb")
    trim = flat("cornice", "#efe6d2", 0.6)
    spire_m = flat("spire" + team, shade(team, 0.9), 0.4)
    gold = flat("gold", GOLD, 0.35)
    bx((0.88, 0.36, 0.32), (0, 0.16, 0.21), f, bev=0.01)
    bx((0.9, 0.38, 0.025), (0, 0.16, 0.37), trim, bev=0.006)
    bx((0.895, 0.375, 0.022), (0, 0.16, 0.075), trim, bev=0)  # a pale granite base course
    tiers = [(0.36, 0.32, 0.05, 0.72), (0.27, 0.24, 0.72, 1.0), (0.18, 0.16, 1.0, 1.2)]
    for (w, d, z0, z1) in tiers:
        bx((w, d, z1 - z0), (0, 0.16, (z0 + z1) / 2), f, bev=0.008)
        bx((w + 0.03, d + 0.03, 0.025), (0, 0.16, z1), trim, bev=0.006)
        for sx in (-1, 1):
            for sy in (-1, 1):
                cn(0.022, 0.09, (sx * w / 2, 0.16 + sy * d / 2, z1 + 0.055), spire_m, 4)
    cy(0.06, 0.08, (0, 0.16, 1.25), trim, 8)
    cy(0.066, 0.016, (0, 0.16, 1.29), gold, 8)
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
    facade_banner(0, 0.035, 0.98, 0.11, 0.4, team)
    for sx in (-1, 1):
        facade_banner(sx * 0.38, 0.09, 0.6, 0.08, 0.3, team)
    # the monumental stair down to a granite parade square with flagpoles, box-hedged lawns and lamps; cars parked
    # on the asphalt either side (the reference cities' lived-in streets)
    gran = stone("#a39d93", 1.3)
    for k, top in enumerate((0.05, 0.038, 0.026)):
        bx((0.44 + k * 0.04, 0.03, top), (0, -0.155 - k * 0.03, top / 2), stone("#cfc8bb", 1.4), bev=0)
    bx((0.84, 0.42, 0.006), (0, -0.39, 0.017), gran, bev=0)
    for x in (-0.3, 0.0, 0.3):
        flagpole(x, -0.5, 0.55, team, 0.14, "#d0d4da")
    for sx in (-1, 1):
        parterre(sx * 0.29, -0.33, 0.2, 0.16, "#d9465a")
        street_lamp(sx * 0.13, -0.3, 0.22, True)
        street_lamp(sx * 0.45, -0.52, 0.22, True)
        tree(sx * 0.6, 0.45, 0.85)
    paint = flat("paint", "#e8e6df", 0.7)
    for sx, cars in ((-1, ("#c0392b", "#2f62c8")), (1, ("#e8e2d0", "#2b2d31"))):
        for i, c in enumerate(cars):
            sedan(sx * 0.6, -0.3 + i * 0.13, 0.0, c)
        for i in range(3):
            bx((0.12, 0.006, 0.004), (sx * 0.6, -0.365 + i * 0.13, 0.016), paint, bev=0)


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
    for (x, y, s_) in ((-0.45, -0.07, 0.6), (-0.31, 0.03, 0.55), (-0.46, 0.05, 0.5)):  # on the roof, not in the wing
        build_at(lambda s_=s_: tree(0, 0, s_), x, y, z=0.2)
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
    for sx in (-1, 1):  # tall banners down the tower front (reference frame 5)
        facade_banner(sx * 0.1, 0.18 - 0.205, 1.2, 0.09, 0.6, team, 0.0, "#d0d4da")
    for (x, y) in ((-0.62, 0.3), (0.62, 0.3)):
        bx((0.08, 0.08, 0.04), (x, y, 0.02), flat("planter", "#7a7f88", 0.6), bev=0.006)
        tree(x, y, 0.75)
    for y in (0.07, -0.11):  # plant on the east wing's roof beside the helipad
        bx((0.04, 0.05, 0.03), (0.505, y, 0.197), flat("ac_unit", "#8a9099", 0.5), bev=0)
        cy(0.014, 0.004, (0.505, y, 0.213), flat("fan", "#2e3138", 0.7), 6)
    # a ribbed glass atrium at the tower's foot (the sculptural entrance of a contemporary parliament), on a
    # team-lit ring
    o = cy(0.152, 0.014, (0, -0.15, 0.022), neon, 12)
    o.scale = (1.3, 1.0, 1.0)
    hemi(0.14, (0, -0.15, 0.028), flat("atrium_glass", "#7fbfe3", 0.15), 12, 3, (1.3, 1.0, 0.85))
    fr = flat("mullion", "#d9dde2", 0.4)
    for a0 in (0.0, math.pi / 2):  # two ribs crossing over the crown
        pts = []
        for k in range(7):
            t = math.pi * k / 6
            r_ = 0.142
            ex, ey = math.cos(t) * math.cos(a0) * r_ * 1.3, math.cos(t) * math.sin(a0) * r_
            pts.append((ex, -0.15 + ey, 0.028 + math.sin(t) * r_ * 0.85))
        for p0, p1 in zip(pts, pts[1:]):
            beam(p0, p1, 0.008, fr)
    # the plaza: a granite walk past the flags to a reflecting pool with fountain jets, benches and lamp posts
    bx((0.24, 0.34, 0.006), (0, -0.46, 0.018), stone("#8f949c", 1.6), bev=0)
    bx((0.46, 0.14, 0.03), (0, -0.67, 0.015), stone("#9a9ea6", 1.6), bev=0)
    bx((0.4, 0.09, 0.004), (0, -0.67, 0.032), flat("water", "#3c9ccc", 0.1), bev=0)
    for x in (-0.13, 0.0, 0.13):
        cn(0.012, 0.07, (x, -0.67, 0.069), flat("jet", "#e4f6ff", 0.2), 6)
    for sx in (-1, 1):
        bx((0.1, 0.03, 0.022), (sx * 0.3, -0.6, 0.026), stone("#b5b8bd", 1.4), bev=0)
        street_lamp(sx * 0.27, -0.42, 0.24, True)
        street_lamp(sx * 0.62, -0.3, 0.24, True)
        bx((0.08, 0.08, 0.04), (sx * 0.5, -0.47, 0.02), flat("planter", "#7a7f88", 0.6), bev=0.006)
        tree(sx * 0.5, -0.47, 0.7)


def hemi(r, loc, mt, seg=12, rings=3, scale=(1, 1, 1)):
    """A dome (the upper half of a sphere) without the buried lower half: seg × rings quads closed by a fan."""
    verts, faces = [], []
    for i in range(rings):
        phi = math.pi / 2 * i / rings
        for j in range(seg):
            a = math.tau * j / seg
            verts.append((math.cos(a) * math.cos(phi) * r * scale[0], math.sin(a) * math.cos(phi) * r * scale[1],
                          math.sin(phi) * r * scale[2]))
    verts.append((0, 0, r * scale[2]))
    for i in range(rings - 1):
        for j in range(seg):
            a, b = i * seg + j, i * seg + (j + 1) % seg
            faces.append((a, b, b + seg, a + seg))
    top = len(verts) - 1
    for j in range(seg):
        faces.append(((rings - 1) * seg + j, (rings - 1) * seg + (j + 1) % seg, top))
    return mesh_obj(verts, faces, mt, loc)


def steel_facade():
    """Grey steel of the late-era citadel (reference frame 5): tall narrow window slits in rows, many lit cold blue."""
    return facade("#5f6670", "#161c24", 0.04, 0.085, 0.26, 0.64, lit="#8fd4ff", lit_p=0.34)  # darker steel: frame 5 is a dim, cool scene


def citadel_tower(x, y, w, d, h, st, plate, neon, cap, seam=None, panel=None, tip=None, needle=True):
    """A tall rectangular tower of the citadel (reference frame 5): a body with a setback crown and a four-sided
    spire with a needle and a lit tip, pale plate seams banding it, and on every face an inset panel in a deep team
    tone with a cold light strip down its middle (the citadel's signature)."""
    bx((w, d, h), (x, y, h / 2), st, bev=0.006)
    for zf in (0.35, 0.6, 0.83):  # plate seams round the body (the string course of the old tower, and two more)
        bx((w + 0.012, d + 0.012, 0.02 if zf != 0.35 else 0.03), (x, y, h * zf), seam or plate, bev=0)
    bx((w * 0.78, d * 0.78, h * 0.16), (x, y, h + h * 0.08), st, bev=0.005)  # setback crown
    bx((w * 0.8 + 0.006, 0.008, 0.01), (x, y - d * 0.4 - 0.003, h + 0.006), neon, bev=0)  # a light line under the crown
    cn(min(w, d) * 0.42, h * 0.32, (x, y, h * 1.16 + h * 0.16), cap, 4, rot=(0, 0, math.pi / 4))
    top = h * 1.16 + h * 0.32
    if needle:
        rod((x, y, top - 0.01), (x, y, top + 0.08), 0.006, cap, r2=0.0015, n=4)
        bx((0.012, 0.012, 0.012), (x, y, top + 0.05), tip or neon, bev=0)
    # the panels lie flush on all four faces (the enemy capitals stand turned half round, showing the back), below
    # the plate seams, which run proud across them so they read as insets; the light strip stands proud of both
    mb = _MB()
    for (nx, ny) in ((0, -1), (1, 0), (-1, 0), (0, 1)):
        L = (w if ny else d)
        off = (d if ny else w) / 2
        px, py = x + nx * (off + 0.002), y + ny * (off + 0.002)
        tx, ty = -ny * L * 0.2, nx * L * 0.2
        mb.face([(px - tx, py - ty, h * 0.15), (px + tx, py + ty, h * 0.15), (px + tx, py + ty, h * 0.85),
                 (px - tx, py - ty, h * 0.85)], (nx, ny, 0))
        rz = 0.0 if ny else math.pi / 2
        bx((0.014, 0.008, h * 0.62), (px + nx * 0.0035, py + ny * 0.0035, h * 0.5), neon, rz, bev=0)
    mb.obj(panel or plate, "panels")


def residence_dl8(team):
    """The late-era capital after reference frame 5: a grey steel citadel of tall towers round a central keep with
    a spire, cold-blue light strips, a portal hall at the head of a grand stair, side wings and great banners, on a
    dark steel plaza laced with light strips."""
    st = steel_facade()
    plate = flat("plate8", "#505760", 0.45)
    seam = flat("seam8", "#8c939c", 0.45)  # pale plate seams: the panel lines of the frame 5 towers
    panel = flat("panel8" + team, shade(team, 0.42), 0.4)  # recessed panels in a deep team tone behind the strips
    cap = flat("spire8", "#4c535d", 0.35)  # dark gothic needles (frame 5), not pale cones
    neon = glow("strip" + team, shade(team, 1.25), 2.0)  # cold light strips: thin lines, not lamps (frame 5)
    cyan = glow("cyan", CYAN, 2.5)
    gold = "#c9a24a"  # the banners' gilded poles (frame 5)
    base = stone("#454a52", 0.8)  # dark steel plaza slabs (frame 5's plaza is dark steel, not pale paving)
    extrude(ngon(0.86, 12, math.pi / 12), -0.01, 0.06, base)
    for k in range(12):  # neon rim of the podium
        a0, a1 = math.pi / 12 + k * math.tau / 12, math.pi / 12 + (k + 1) * math.tau / 12
        beam((math.cos(a0) * 0.80, math.sin(a0) * 0.80, 0.062), (math.cos(a1) * 0.80, math.sin(a1) * 0.80, 0.062), 0.014, neon)
    for k in range(6):  # light strips across the plaza from the terrace to the rim
        a = k * math.tau / 6
        beam((math.cos(a) * 0.58, math.sin(a) * 0.58, 0.062), (math.cos(a) * 0.78, math.sin(a) * 0.78, 0.062), 0.012, neon)
    extrude(ngon(0.56, 8, math.pi / 8), 0.06, 0.14, flat("terrace8", "#4b4f56", 0.5))  # the citadel's terrace
    tp = ngon(0.555, 8, math.pi / 8)
    for k in range(8):  # a light line along the terrace edge
        if k == 5:  # (not across the grand stair)
            continue
        (x0, y0), (x1, y1) = tp[k], tp[(k + 1) % 8]
        beam((x0, y0, 0.142), (x1, y1, 0.142), 0.01, neon)
    # the central keep: a tall stepped tower with the spire
    citadel_tower(0, 0.1, 0.26, 0.22, 1.45, st, plate, neon, cap, seam, panel, cyan, needle=False)
    rod((0, 0.1, 1.9), (0, 0.1, 2.15), 0.008, cap, n=5)
    ico(0.022, (0, 0.1, 2.16), cyan)
    # the ring of towers, tallest at the back so the silhouette climbs to the keep
    for (x, y, w, h) in ((-0.21, -0.02, 0.13, 1.0), (0.21, -0.02, 0.13, 1.0), (-0.37, 0.16, 0.12, 0.82),
                         (0.37, 0.16, 0.12, 0.82), (-0.17, 0.33, 0.12, 1.2), (0.17, 0.33, 0.12, 1.2)):
        citadel_tower(x, y, w, w, h, st, plate, neon, cap, seam, panel, cyan)
    # the portal hall in front of the keep, with a glowing gate
    bx((0.46, 0.16, 0.3), (0, -0.2, 0.15 + 0.06), st, bev=0.008)
    bx((0.48, 0.18, 0.025), (0, -0.2, 0.37), plate, bev=0.004)
    bx((0.47, 0.17, 0.02), (0, -0.2, 0.3), seam, bev=0)
    bx((0.12, 0.012, 0.16), (0, -0.282, 0.14), cyan, bev=0)
    cy(0.06, 0.012, (0, -0.282, 0.22), cyan, 12, rot=(math.pi / 2, 0, 0))
    for sx in (-1, 1):
        bx((0.03, 0.03, 0.34), (sx * 0.1, -0.29, 0.06 + 0.17), plate, bev=0.004)  # portal pylons
        bx((0.008, 0.008, 0.28), (sx * 0.1, -0.306, 0.06 + 0.15), neon, bev=0)
        bx((0.18, 0.28, 0.18), (sx * 0.5, -0.06, 0.06 + 0.09), st, bev=0.006)  # low side wings
        bx((0.19, 0.29, 0.02), (sx * 0.5, -0.06, 0.25), plate, bev=0.003)
        bx((0.19, 0.008, 0.008), (sx * 0.5, -0.205, 0.235), neon, bev=0)  # a light line along the wing's front
        bx((0.06, 0.05, 0.03), (sx * 0.52, -0.02, 0.275), seam, bev=0)  # roof plant on the wings
    for sx in (-1, 1):  # holo masts at the hall corners
        cy(0.008, 0.2, (sx * 0.2, -0.3, 0.46), flat("mast", "#d0d4da", 0.5), 6)
        bx((0.012, 0.012, 0.012), (sx * 0.2, -0.3, 0.565), cyan, bev=0)
    # the base of reference frame 5: a grand stair up the podium, an energy orb on a pedestal, banners, plaza lamps
    stair = flat("stair", "#5e656f", 0.5)
    for k in range(5):
        bx((0.34 - k * 0.02, 0.06, 0.036), (0, -0.62 + k * 0.035, 0.018 + k * 0.036), stair, bev=0.004)
    for sx in (-1, 1):
        bx((0.04, 0.2, 0.012), (sx * 0.19, -0.56, 0.11), neon, bev=0)  # light rails along the stair
        # shield emitters flanking the foot of the stair: dark pylons with a cold glowing head
        bx((0.04, 0.04, 0.15), (sx * 0.2, -0.69, 0.075 + 0.0), flat("pedestal", "#3a4049", 0.5), bev=0)
        bx((0.05, 0.05, 0.012), (sx * 0.2, -0.69, 0.156), seam, bev=0)
        uvs(0.017, (sx * 0.2, -0.69, 0.18), cyan, 6, 4)
    ox, oy = 0.5, -0.42
    cy(0.07, 0.08, (ox, oy, 0.1), flat("pedestal", "#3a4049", 0.5), 12)
    cy(0.075, 0.012, (ox, oy, 0.14), neon, 12)
    uvs(0.08, (ox, oy, 0.24), glow("orb" + team, shade(team, 1.05), 1.6), 14, 8)
    torus(0.11, 0.006, (ox, oy, 0.24), flat("ring_frame", "#c9d0d8", 0.4), (math.pi / 2.6, 0, 0.4), 20, 3)
    # a holo banner on the other side: a mast projecting the state's colour as a glowing panel
    hx, hy = -0.5, -0.42
    cy(0.05, 0.03, (hx, hy, 0.075), flat("pedestal", "#3a4049", 0.5), 8)
    cy(0.007, 0.36, (hx, hy, 0.24), flat("mast", "#d0d4da", 0.5), 6)
    bx((0.12, 0.004, 0.17), (hx + 0.066, hy, 0.31), glow("holo" + team, team, 1.0), bev=0)
    bx((0.13, 0.008, 0.008), (hx + 0.066, hy, 0.4), cyan, bev=0)
    # the state's crest projected on it, white and lit (both faces), so the panel reads as a banner, not a sign
    crest = [(0.0, -0.036), (0.026, -0.016), (0.026, 0.026), (0.0, 0.016), (-0.026, 0.026), (-0.026, -0.016)]
    extrude(crest, -0.004, 0.004, glow("holo_crest", "#eef8ff", 1.6), (hx + 0.066, hy, 0.325), (math.pi / 2, 0, 0))
    for sx in (-1, 1):  # the two great banners of reference frame 5, down the flanking towers
        facade_banner(sx * 0.21, -0.091, 0.92, 0.1, 0.42, team, 0.0, gold)
    facade_banner(0, -0.016, 1.3, 0.12, 0.5, team, 0.0, gold)
    for (x, y) in ((-0.55, -0.24), (-0.3, -0.62), (0.28, -0.64), (0.62, -0.2)):
        cy(0.008, 0.16, (x, y, 0.14), flat("mast", "#d0d4da", 0.5), 6)
        ico(0.016, (x, y, 0.23), glow("lamp8", "#bfe8ff", 3.0))
    # service blocks with lit window bands at the back corners of the plaza, a few cargo crates
    for sx in (-1, 1):
        bx((0.2, 0.13, 0.08), (sx * 0.56, 0.42, 0.1), st, bev=0.004)
        bx((0.21, 0.14, 0.012), (sx * 0.56, 0.42, 0.146), plate, bev=0)
        bx((0.16, 0.006, 0.012), (sx * 0.56, 0.352, 0.11), neon, bev=0)
    for (x, y, s_) in ((-0.62, 0.22, 0.045), (-0.58, 0.18, 0.035), (0.6, 0.24, 0.04)):
        bx((s_, s_ * 1.4, s_), (x, y, 0.06 + s_ / 2), flat("crate8", "#b8862e", 0.6), bev=0)


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


def ebox(p0, p1, u0, u1, v, t, z0, z1, mt):
    """A plain box laid along the edge p0→p1: from u0 to u1 (distances from p0), centred v outward of the edge
    line (negative = inside the hex), t thick, from z0 to z1."""
    L, ang, mid, n = edge_frame(p0, p1)
    c = lerp2(p0, p1, (u0 + u1) / 2 / L)
    return bx((u1 - u0, t, z1 - z0), (c[0] + n[0] * v, c[1] + n[1] * v, (z0 + z1) / 2), mt, ang, 0)


def merlon_row(p0, p1, u0, u1, v, t, z0, h, mw, pitch, mt, mb=None):
    """Merlons along the edge p0→p1 between u0 and u1 (evenly spaced, mw wide, one every `pitch`), v outward and
    t thick, standing on z0: five faces each (their bottoms sit on the wall top), all in one mesh."""
    L, ang, mid, n = edge_frame(p0, p1)
    e = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
    k = max(1, int((u1 - u0 - mw) / pitch) + 1)
    start = u0 + (u1 - u0 - (k - 1) * pitch - mw) / 2
    own = mb is None
    mb = mb or _MB()

    def P(u, w, z):
        return (p0[0] + e[0] * u + n[0] * w, p0[1] + e[1] * u + n[1] * w, z)
    for i in range(k):
        a, b = start + i * pitch, start + i * pitch + mw
        lo, hi = v - t / 2, v + t / 2
        z1 = z0 + h
        mb.face([P(a, lo, z1), P(b, lo, z1), P(b, hi, z1), P(a, hi, z1)], (0, 0, 1))
        mb.face([P(a, hi, z0), P(b, hi, z0), P(b, hi, z1), P(a, hi, z1)], (n[0], n[1], 0))
        mb.face([P(a, lo, z0), P(b, lo, z0), P(b, lo, z1), P(a, lo, z1)], (-n[0], -n[1], 0))
        mb.face([P(a, lo, z0), P(a, hi, z0), P(a, hi, z1), P(a, lo, z1)], (-e[0], -e[1], 0))
        mb.face([P(b, lo, z0), P(b, hi, z0), P(b, hi, z1), P(b, lo, z1)], (e[0], e[1], 0))
    if own:
        mb.obj(mt, "merlons")
    return k


def hazard(period=0.035, c1="#f2c230", c2="#26272b"):
    """Yellow-and-black hazard stripes running diagonally in world space (baked like every procedural colour)."""
    key = ("hazard", period, c1, c2)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("hazard")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    acc = None
    for ax in range(3):
        if acc is None:
            acc = sp.outputs[ax]
            continue
        ad = nt.nodes.new("ShaderNodeMath")
        ad.operation = "ADD"
        L.new(acc, ad.inputs[0])
        L.new(sp.outputs[ax], ad.inputs[1])
        acc = ad.outputs[0]
    dv = nt.nodes.new("ShaderNodeMath")
    dv.operation = "DIVIDE"
    L.new(acc, dv.inputs[0])
    dv.inputs[1].default_value = period
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    L.new(dv.outputs[0], fr.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    L.new(fr.outputs[0], gt.inputs[0])
    gt.inputs[1].default_value = 0.5
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(gt.outputs[0], _sock(mx, "Factor_Float"))
    _sock(mx, "A_Color").default_value = (*kit.srgb(c1), 1)
    _sock(mx, "B_Color").default_value = (*kit.srgb(c2), 1)
    bs = nt.nodes["Principled BSDF"]
    L.new(_sock(mx, "Result_Color", True), bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.6
    kit._MATS[key] = m
    return m


def _stripe_mat(key, s_of, c1, c2):
    """Two-colour stripes baked like every procedural colour: s_of(nt, links, pos) returns the stripe coordinate
    (one stripe pair per unit); the fractional part picks c1 or c2."""
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("hazard")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    s = s_of(nt, L, geo.outputs["Position"])
    fr = nt.nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    L.new(s, fr.inputs[0])
    gt = nt.nodes.new("ShaderNodeMath")
    gt.operation = "GREATER_THAN"
    L.new(fr.outputs[0], gt.inputs[0])
    gt.inputs[1].default_value = 0.5
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(gt.outputs[0], _sock(mx, "Factor_Float"))
    _sock(mx, "A_Color").default_value = (*kit.srgb(c1), 1)
    _sock(mx, "B_Color").default_value = (*kit.srgb(c2), 1)
    bs = nt.nodes["Principled BSDF"]
    L.new(_sock(mx, "Result_Color", True), bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.6
    kit._MATS[key] = m
    return m


def hazard_dir(period, ang, c1="#f2c230", c2="#26272b"):
    """Hazard stripes for a band running along the direction ang: they lean at 45° on both long faces of the band
    whatever way the edge runs (the world-space hazard() turns to long smears on some edge directions)."""
    def s_of(nt, L, pos):
        dp = nt.nodes.new("ShaderNodeVectorMath")
        dp.operation = "DOT_PRODUCT"
        L.new(pos, dp.inputs[0])
        dp.inputs[1].default_value = (math.cos(ang) / period, math.sin(ang) / period, 1.0 / period)
        return _sock(dp, "Value", True)
    return _stripe_mat(("hazard_dir", period, round(ang, 4), c1, c2), s_of, c1, c2)


def hazard_ring(cx, cy_, r, n=8, c1="#f2c230", c2="#26272b"):
    """Hazard stripes round a vertical drum centred on (cx, cy_) with radius r: n stripe pairs per turn, leaning at
    45° (seamless, since a whole number of pairs fits the circumference)."""
    pz = math.tau * r / n

    def s_of(nt, L, pos):
        sub = nt.nodes.new("ShaderNodeVectorMath")
        sub.operation = "SUBTRACT"
        L.new(pos, sub.inputs[0])
        sub.inputs[1].default_value = (cx, cy_, 0.0)
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(sub.outputs[0], sp.inputs[0])
        at = nt.nodes.new("ShaderNodeMath")
        at.operation = "ARCTAN2"
        L.new(sp.outputs[1], at.inputs[0])
        L.new(sp.outputs[0], at.inputs[1])
        ma = nt.nodes.new("ShaderNodeMath")
        ma.operation = "MULTIPLY_ADD"  # angle · n/τ + z/pz
        L.new(at.outputs[0], ma.inputs[0])
        ma.inputs[1].default_value = n / math.tau
        zz = nt.nodes.new("ShaderNodeMath")
        zz.operation = "DIVIDE"
        L.new(sp.outputs[2], zz.inputs[0])
        zz.inputs[1].default_value = pz
        L.new(zz.outputs[0], ma.inputs[2])
        return ma.outputs[0]
    return _stripe_mat(("hazard_ring", round(cx, 4), round(cy_, 4), r, n, c1, c2), s_of, c1, c2)


def zigzag_wire(p0, p1, u0, u1, v, z, amp, n_z, mt, w=0.006):
    """Razor / barbed wire seen from afar: a zigzag ribbon along the edge (both faces), n_z teeth."""
    L, ang, mid, nrm = edge_frame(p0, p1)
    e = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
    mb = _MB()
    pts = []
    for i in range(2 * n_z + 1):
        u = u0 + (u1 - u0) * i / (2 * n_z)
        zz = z + (amp if i % 2 else -amp)
        pts.append((p0[0] + e[0] * u + nrm[0] * v, p0[1] + e[1] * u + nrm[1] * v, zz))
    for a, b in zip(pts, pts[1:]):
        for sd in (1, -1):
            o = (nrm[0] * w * 0.5 * sd, nrm[1] * w * 0.5 * sd)
            mb.face([(a[0] + o[0], a[1] + o[1], a[2] - w), (b[0] + o[0], b[1] + o[1], b[2] - w),
                     (b[0] + o[0], b[1] + o[1], b[2] + w), (a[0] + o[0], a[1] + o[1], a[2] + w)], (nrm[0] * sd, nrm[1] * sd, 0))
    mb.obj(mt, "wire")


ROPE = "#c2a466"  # rope lashings: pale tan bindings that read on the dark logs
FORT_SLATE = "#56657a"  # the neutral blue-grey slate of the fort towers (the forts carry no team colour)


def f1_edge(p0, p1, gate=False):
    """Wattle palisade: stakes with pale sharpened tips bound to the woven panel by rope lashings, and a row of
    sharpened stakes leaning out (the camp fences of the early reference hexes)."""
    L, ang, mid, n = edge_frame(p0, p1)
    wd = tex("wood", WOOD_D)
    wick = tex("wood", "#b08850", 4.0)
    tip = flat("stake_tip", "#d8b27a", 0.8)
    rope = flat("rope", ROPE, 0.9)
    for i in range(1, 5):
        x, y = lerp2(p0, p1, i / 5)
        cy(0.014, 0.2, (x, y, 0.1), wd, 6)
        cn(0.016, 0.04, (x, y, 0.22), tip, 6)
        bx((0.032, 0.032, 0.018), (x, y, 0.14), rope, ang, 0)
    bx((L - 0.05, 0.014, 0.15), (mid[0], mid[1], 0.095), tex("wood", "#8f6a3c", 5.0), ang, 0)
    for j, z in enumerate((0.04, 0.075, 0.11, 0.145)):
        off = 0.009 if j % 2 else -0.009
        bx((L - 0.06, 0.016, 0.03), (mid[0] + n[0] * off, mid[1] + n[1] * off, z), wick, ang, 0)
    # sharpened stakes leaning outwards: dark shafts with pale cut points
    shaft = tex("wood", "#7a5232")
    for f in (0.3, 0.43, 0.57, 0.7):
        x, y = lerp2(p0, p1, f)
        a = (x + n[0] * 0.03, y + n[1] * 0.03, -0.01)
        b = (x + n[0] * 0.17, y + n[1] * 0.17, 0.19)
        m = tuple(a[i] + (b[i] - a[i]) * 0.78 for i in range(3))
        rod(a, m, 0.016, shaft, 0.012)
        rod(m, b, 0.012, tip, 0.001, n=4)


def f1_post(p):
    cy(0.022, 0.27, (p[0], p[1], 0.135), tex("wood", WOOD_D), 6)
    cn(0.022, 0.05, (p[0], p[1], 0.295), flat("stake_tip", "#d8b27a", 0.8), 6)
    bx((0.05, 0.05, 0.02), (p[0], p[1], 0.19), flat("rope", ROPE, 0.9), math.atan2(p[1], p[0]), 0)


def f2_edge(p0, p1, gate=False):
    """Timber stockade: logs in two tones with pale pointed tops, bound by two rope lashings on the outside, and a
    plank fighting walk on trestles along the inside (the wall walks of reference frame 4)."""
    L, ang, mid, n = edge_frame(p0, p1)
    woods = [tex("wood", "#9a6a3c", 3.0), tex("wood", "#86592f", 3.0)]
    tip = flat("stake_tip", "#d8b27a", 0.8)
    cnt = 11
    for i in range(1, cnt):
        x, y = lerp2(p0, p1, i / cnt)
        h = 0.3 + (0.03 if i % 2 else 0.0)
        cy(0.036, h, (x, y, h / 2), woods[i % 2], 6)
        cn(0.036, 0.07, (x, y, h + 0.035), tip, 6)
    rope = flat("rope", ROPE, 0.9)
    for z in (0.11, 0.25):
        ebox(p0, p1, 0.055, L - 0.055, 0.031, 0.012, z, z + 0.018, rope)
    plank = tex("wood", "#a8743f", 4.0)
    ebox(p0, p1, 0.06, L - 0.06, -0.07, 0.07, 0.19, 0.204, plank)
    dk = tex("wood", WOOD_D)
    for f in (0.22, 0.5, 0.78):
        ebox(p0, p1, L * f - 0.009, L * f + 0.009, -0.095, 0.018, 0.0, 0.19, dk)


def f2_post(p):
    a = math.atan2(p[1], p[0])
    cy(0.055, 0.4, (p[0], p[1], 0.2), tex("wood", "#8a5e36", 3.0), 8)
    cn(0.055, 0.09, (p[0], p[1], 0.445), flat("stake_tip", "#d8b27a", 0.8), 8)
    bx((0.12, 0.12, 0.02), (p[0], p[1], 0.3), tex("wood", WOOD_D), a, 0)
    for z in (0.12, 0.25):  # rope lashings square to the wall lines (corners inside the old 0.922 footprint)
        bx((0.116, 0.116, 0.018), (p[0], p[1], z), flat("rope", ROPE, 0.9), a, 0)


def f3_edge(p0, p1, gate=False):
    """Stone curtain wall of reference frames 3 and 4: a battered plinth, coursed light-grey masonry with a string
    course and arrow slits, a corbelled parapet of chunky merlons on the outer edge, a flagstone wall walk and a low
    inner parapet."""
    L, ang, mid, n = edge_frame(p0, p1)
    st = stone(STONE, 1.4)
    dk = stone(STONE_D)
    walk = stone("#d4cec2", 2.4)
    T, H = 0.09, 0.24
    a, b = 0.07, L - 0.07
    segs = [(a, b)] if not gate else [(a, L / 2 - 0.11), (L / 2 + 0.11, b)]
    mb = _MB()
    slit_items = []
    e = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
    for (s0, s1) in segs:
        ebox(p0, p1, s0, s1, 0.0, T, 0.0, H, st)
        ebox(p0, p1, s0, s1, 0.006, T + 0.03, 0.0, 0.05, dk)  # plinth
        ebox(p0, p1, s0, s1, 0.0, T + 0.012, 0.15, 0.166, dk)  # string course
        ebox(p0, p1, s0, s1, T / 2 + 0.004, 0.014, H - 0.032, H - 0.004, dk)  # corbel band under the parapet
        # the flagstone walk: one quad over the wall top, between the parapets
        q = [(p0[0] + e[0] * u + n[0] * w, p0[1] + e[1] * u + n[1] * w, H + 0.003) for (u, w) in
             ((s0, -T / 2), (s1, -T / 2), (s1, T / 2), (s0, T / 2))]
        wm = _MB()
        wm.face(q, (0, 0, 1))
        wm.obj(walk, "walk")
        merlon_row(p0, p1, s0, s1, T / 2 - 0.012, 0.036, H, 0.058, 0.056, 0.093, st, mb)
        ebox(p0, p1, s0, s1, -T / 2 + 0.008, 0.016, H, H + 0.026, st)  # inner parapet
        k = max(1, int((s1 - s0) / 0.19))
        for i in range(k):
            c = lerp2(p0, p1, (s0 + (i + 0.5) * (s1 - s0) / k) / L)
            slit_items.append((c[0], c[1], 0.1, ang, T + 0.004, 0.014, 0.05))
    mb.obj(st, "merlons")
    slits(slit_items, one_side=True)
    if gate:
        for sx in (-1, 1):
            q = lerp2(p0, p1, 0.5 + sx * 0.13)
            bx((0.06, 0.13, 0.4), (q[0], q[1], 0.2), st, ang, 0)
        bx((0.32, 0.142, 0.08), (mid[0], mid[1], 0.38), st, ang, 0)  # (proud of the pillars: coplanar faces bake black)
        for i in (-2, 0, 2):
            q = lerp2(p0, p1, 0.5 + i * 0.045)
            bx((0.04, 0.142, 0.05), (q[0], q[1], 0.445), st, ang, 0)
        for sx in (-1, 1):
            q = lerp2(p0, p1, 0.5 + sx * 0.058)
            bx((0.098, 0.02, 0.35), (q[0] + n[0] * 0.01, q[1] + n[1] * 0.01, 0.175), tex("wood", "#5a3a22"), ang, 0)
        for z in (0.07, 0.23):
            bx((0.16, 0.026, 0.018), (mid[0] + n[0] * 0.012, mid[1] + n[1] * 0.012, z), flat("iron", "#3b3d42", 0.6), ang, 0)


def f3_post(p):
    """Round stone tower of reference frames 3 and 4: a dark plinth, coursed body with a string course, a lit
    window towards the town and the field, arrow slits, a corbelled crenellated parapet, a cone roof laid in
    blue-grey slate courses, a gilt finial and a pennant (its cloth marker lets the game paint the owner's flag)."""
    x, y = p
    r = 0.09
    st = stone(STONE, 1.4)
    dk = stone(STONE_D)
    a0 = math.atan2(y, x)
    cy(r + 0.014, 0.05, (x, y, 0.025), dk, 10)  # plinth
    cy(r, 0.36, (x, y, 0.18), st, 10)
    cy(r + 0.006, 0.016, (x, y, 0.16), dk, 10)  # string course
    cy(r + 0.003, 0.034, (x, y, 0.343), dk, 10, r2=r + 0.024)  # corbels flaring out under the parapet
    cy(r + 0.024, 0.032, (x, y, 0.376), st, 10)  # parapet
    mb = _MB()
    for k in range(8):
        a = math.tau * (k + 0.5) / 8
        ca, sa = math.cos(a), math.sin(a)
        ta, tb = (-sa, ca), (ca, sa)
        rr = r + 0.012
        cxk, cyk = x + ca * rr, y + sa * rr
        hw, ht, z0, z1 = 0.019, 0.012, 0.392, 0.428
        corners = [(cxk + ta[0] * u + tb[0] * w, cyk + ta[1] * u + tb[1] * w) for (u, w) in
                   ((-hw, -ht), (hw, -ht), (hw, ht), (-hw, ht))]
        c3 = lambda i, z: (corners[i][0], corners[i][1], z)  # noqa: E731
        mb.face([c3(0, z1), c3(1, z1), c3(2, z1), c3(3, z1)], (0, 0, 1))
        mb.face([c3(3, z0), c3(2, z0), c3(2, z1), c3(3, z1)], (tb[0], tb[1], 0))
        mb.face([c3(0, z0), c3(1, z0), c3(1, z1), c3(0, z1)], (-tb[0], -tb[1], 0))
        mb.face([c3(0, z0), c3(3, z0), c3(3, z1), c3(0, z1)], (-ta[0], -ta[1], 0))
        mb.face([c3(1, z0), c3(2, z0), c3(2, z1), c3(1, z1)], (ta[0], ta[1], 0))
    mb.obj(st, "merlons")
    # the cone stands inside the crenellated parapet (reference frame 4's tower roofs), its eave behind the merlons
    top = coursed_cone(x, y, 0.392, r + 0.002, 0.23, FORT_SLATE, rings=4, sides=10, lip=0.003, butt_k=0.75, eave=0.0,
                       finial=None)  # (the forts keep their look: not part of the soft pass yet)
    ico(0.013, (x, y, top + 0.004), flat("finial", GOLD, 0.35))
    for aa in (a0, a0 + math.pi):  # lit windows: one towards the field, one towards the town
        bx((0.022, 0.012, 0.036), (x + math.cos(aa) * (r - 0.002), y + math.sin(aa) * (r - 0.002), 0.27), win_lit(),
           aa + math.pi / 2, 0)
    slits([(x + math.cos(a0 + s_) * (r + 0.002), y + math.sin(a0 + s_) * (r + 0.002), 0.22, a0 + s_ + math.pi / 2,
            0.0, 0.014, 0.04) for s_ in (-1.1, 1.1)], one_side=True)
    rod((x, y, top), (x, y, top + 0.058), 0.004, flat("pole", "#d9d2c3", 0.5), n=4)
    bx((0.05, 0.004, 0.026), (x + 0.026, y, top + 0.044), flat("pennant", "#d9b84a", 0.6), 0, 0)
    flag_at("flagw", x + 0.026, y, top + 0.044, 0.054, 0.03)


def f4_edge(p0, p1, gate=False):
    """Bastioned rampart (16th-17th c.): a battered masonry face on a footing, a pale stone cordon, a parapet of
    stone blocks with open embrasures, a timber gun walk and a turfed slope down the inside."""
    L, ang, mid, n = edge_frame(p0, p1)
    st = stone("#a39b8d", 1.4)
    taper_box((L - 0.2, 0.17, 0.2), (mid[0], mid[1], 0.1), st, (1.0, 0.6), ang)
    ebox(p0, p1, 0.1, L - 0.1, 0.0, 0.18, 0.0, 0.03, stone(STONE_D))  # footing
    ebox(p0, p1, 0.095, L - 0.095, 0.0, 0.15, 0.124, 0.14, flat("cordon", "#e6dfd0", 0.7))  # the pale cordon
    merlon_row(p0, p1, 0.11, L - 0.11, 0.035, 0.036, 0.2, 0.05, 0.1, 0.14, st)
    ebox(p0, p1, 0.11, L - 0.11, -0.015, 0.07, 0.194, 0.206, tex("wood", WOOD_L))
    # two guns run out through the embrasures: a dark carriage on the walk, the iron barrel poking out
    iron = flat("iron", "#2e3034", 0.5)
    for f in (0.29 / 0.86, 0.57 / 0.86):
        c = lerp2(p0, p1, f)
        ebox(p0, p1, L * f - 0.022, L * f + 0.022, -0.022, 0.05, 0.206, 0.232, tex("wood", "#6a4327"))
        rod((c[0] - n[0] * 0.02, c[1] - n[1] * 0.02, 0.228), (c[0] + n[0] * 0.085, c[1] + n[1] * 0.085, 0.232), 0.013,
            iron, 0.011, n=6)


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
    """Arrow-head bastion with a gun on its terreplein and a stone sentry turret (échauguette) corbelled out at its
    point under a blue-grey slate cap."""
    a = math.atan2(p[1], p[0])
    pts = [(-0.14, -0.14), (0.02, -0.14), (0.12, 0.0), (0.02, 0.14), (-0.14, 0.14)]

    def ring(k):
        return [(p[0] + (x * k) * math.cos(a) - (y * k) * math.sin(a), p[1] + (x * k) * math.sin(a) + (y * k) * math.cos(a))
                for x, y in pts]
    extrude(ring(1.0), 0.0, 0.24, stone("#a39b8d", 1.4))
    extrude(ring(1.06), 0.0, 0.035, stone(STONE_D))  # footing
    extrude(ring(1.03), 0.125, 0.14, flat("cordon", "#e6dfd0", 0.7))  # cordon
    extrude(ring(0.85), 0.24, 0.252, flat("grassy", "#6f9a45", 0.9))
    cannon(p[0] - math.cos(a) * 0.04, p[1] - math.sin(a) * 0.04, a, 0.252)
    # the échauguette at the salient (kept inside the old footprint: 0.86 + 0.09 + 0.036 stays under the bastion's
    # 0.987, so the turrets of two posts sharing a corner never meet)
    tx, ty = p[0] + math.cos(a) * 0.09, p[1] + math.sin(a) * 0.09
    st = stone("#bdb6a8", 1.4)
    cn(0.03, 0.05, (tx, ty, 0.2), st, 8, rot=(math.pi, 0, 0))  # corbel cone under it
    cy(0.03, 0.075, (tx, ty, 0.2625), st, 8)
    bx((0.012, 0.01, 0.028), (tx + math.cos(a) * 0.028, ty + math.sin(a) * 0.028, 0.268), flat("slit", "#1c1a19", 0.9),
       a + math.pi / 2, 0)
    cn(0.036, 0.05, (tx, ty, 0.325), tex("roof", FORT_SLATE, 1.6), 8)
    ico(0.007, (tx, ty, 0.351), flat("finial", GOLD, 0.35))


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
    """Trench-war line: concrete dragon's teeth with hazard-striped bands, concertina wire on wooden X-pickets
    in front, a sandbag parapet behind, ammunition boxes."""
    L, ang, mid, n = edge_frame(p0, p1)
    cm = tex("plaster", "#b9b5ad", 2.0)
    hz = hazard(0.03)
    rnd = random.Random(int((p0[0] + 3) * 100))
    for i in range(5):
        f = (i + 0.5) / 5
        q = lerp2(p0, p1, 0.06 + f * 0.88)
        r_ = ang + rnd.uniform(-0.12, 0.12)
        taper_box((0.14, 0.09, 0.13), (q[0], q[1], 0.065), cm, (1.0, 0.45), r_, 0.0)
        # a painted hazard band round the tooth (the taper box's walls lean in: the band follows them, proud)
        taper_box((0.146, 0.08, 0.04), (q[0], q[1], 0.078), hz, (1.0, 0.8), r_, 0.0)
    steel = flat("wire", "#4c4f55", 0.5)
    for f in (0.1, 0.5, 0.9):
        q = lerp2(p0, p1, f)
        cy(0.007, 0.24, (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09, 0.12), steel, 5)
    for z in (0.1, 0.2):
        bx((L - 0.1, 0.006, 0.006), (mid[0] + n[0] * 0.09, mid[1] + n[1] * 0.09, z), steel, ang, 0)
    for i in range(5):
        q = lerp2(p0, p1, 0.12 + i * 0.76 / 4)
        torus(0.06, 0.006, (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09, 0.12), steel, (math.pi / 2, 0.25, ang + math.pi / 2), 7, 3)
    pk = tex("wood", WOOD_D, 3.0)
    for f in (0.3, 0.7):  # X-shaped wooden pickets that carry the wire
        q = lerp2(p0, p1, f)
        c_ = (q[0] + n[0] * 0.09, q[1] + n[1] * 0.09)
        for s_ in (-1, 1):
            beam((c_[0] - n[0] * 0.05 * s_, c_[1] - n[1] * 0.05 * s_, 0.0), (c_[0] + n[0] * 0.05 * s_, c_[1] + n[1] * 0.05 * s_, 0.2), 0.012, pk)
    sandbags(p0, p1, -0.075, n, 2, f0=0.12, f1=0.88)
    ammo = flat("ammo", "#5d6a3a", 0.7)
    for (u, w) in ((0.3, -0.13), (0.34, -0.135), (0.62, -0.13)):
        ebox(p0, p1, L * u - 0.02, L * u + 0.02, w, 0.028, 0.0, 0.026, ammo)


def f5_post(p):
    """Concrete pillbox with a dark firing slit, a yellow warning plate and a hazard-striped barrier boom, and a
    sandbagged machine-gun nest on the inner side."""
    a = math.atan2(p[1], p[0])
    cm = tex("plaster", "#b9b5ad", 2.0)
    bx((0.15, 0.15, 0.13), (p[0], p[1], 0.065), cm, a, 0)
    bx((0.11, 0.11, 0.1), (p[0], p[1], 0.18), cm, a + 0.4, 0)
    bx((0.13, 0.13, 0.012), (p[0], p[1], 0.236), flat("conc_cap", "#8b877f", 0.8), a + 0.4, 0)
    slits([(p[0] + math.cos(a) * 0.077, p[1] + math.sin(a) * 0.077, 0.1, a + math.pi / 2, 0.0, 0.08, 0.016)],
          one_side=True)
    bx((0.07, 0.008, 0.05), (p[0] + math.cos(a + 0.6) * 0.078, p[1] + math.sin(a + 0.6) * 0.078, 0.06),
       flat("warn", "#f2c230", 0.6), a + 0.6 + math.pi / 2, 0)
    # the barrier boom across the line, striped
    bx((0.024, 0.024, 0.07), (p[0] - math.sin(a) * 0.1, p[1] + math.cos(a) * 0.1, 0.035), flat("conc_cap", "#8b877f", 0.8), a, 0)
    beam((p[0] - math.sin(a) * 0.1, p[1] + math.cos(a) * 0.1, 0.075),
         (p[0] - math.sin(a) * 0.1 - math.cos(a) * 0.16, p[1] + math.cos(a) * 0.1 - math.sin(a) * 0.16, 0.075),
         0.014, hazard(0.03, "#e8e2d6", "#c0302a"))

    def nest():  # machine-gun nest on the inner side: a sandbag ring and a water-cooled gun facing out
        sandbag_ring(0, 0, 0.075, 3)
        gm = flat("gun", "#33363b", 0.55)
        cy(0.016, 0.1, (-0.03, 0, 0.075), gm, 8, rot=(0, math.pi / 2, 0))
        cy(0.006, 0.07, (-0.11, 0, 0.075), gm, 6, rot=(0, math.pi / 2, 0))
        for k in range(3):
            q = k * math.tau / 3
            beam((0.0, 0.0, 0.07), (math.cos(q) * 0.04, math.sin(q) * 0.04, 0.0), 0.007, gm)
    build_at(nest, p[0] * 0.8, p[1] * 0.8, a + math.pi)


def hedgehog(x, y, rz, s=1.0):
    def b():
        m_ = flat("hedge", "#5b4a42", 0.6)
        for k in range(3):
            o = bx((0.15 * s, 0.018, 0.018), (0, 0, 0.012 + 0.038 * s), m_, bev=0)
            o.rotation_euler = (0, 0.62, k * math.tau / 3)
    build_at(b, x, y, rz)


def f6_edge(p0, p1, gate=False):
    """Bunker line: an earth berm with a turfed crest and camouflage net, a log-lined trench behind with a sandbag
    lip, steel hedgehogs and a low barbed-wire fence on stakes in front."""
    L, ang, mid, n = edge_frame(p0, p1)
    taper_box((L - 0.24, 0.13, 0.06), (mid[0], mid[1], 0.03), tex("plaster", "#8a6e4b", 1.5), (1.0, 0.5), ang)
    taper_box((L - 0.28, 0.075, 0.012), (mid[0], mid[1], 0.064), tex("plaster", "#5f7a3a", 2.0), (1.0, 0.7), ang)
    # camouflage nets draped over the crest
    camo = [flat("camo1", "#5d6b3c", 0.85), flat("camo2", "#7a6a48", 0.85)]
    for k, (u0, u1) in enumerate(((0.2, 0.36), (0.5, 0.64))):
        ebox(p0, p1, L * u0, L * u1, 0.0, 0.085, 0.064, 0.074, camo[k % 2])
    tr = (mid[0] - n[0] * 0.115, mid[1] - n[1] * 0.115)
    bx((L - 0.26, 0.06, 0.008), (tr[0], tr[1], 0.004), flat("trench", "#3a2c1e", 0.95), ang, 0)
    lg = tex("wood", "#7a5634", 3.0)
    for s_ in (-1, 1):
        cy(0.011, L - 0.26, (tr[0] + n[0] * 0.034 * s_, tr[1] + n[1] * 0.034 * s_, 0.014), lg, 6, rot=(0, math.pi / 2, ang))
    sandbags(p0, p1, -0.03, n, 1, "#9c936a", 0.2, 0.8)
    # the wire belt in front of the berm, all inside the tile (apothem 0.866 = edge line + 0.121): steel hedgehogs
    # (one beam along the line, so they reach 0.045 out) between wooden stakes, a barbed wire strung through them
    for k, f in enumerate((0.3, 0.5, 0.7)):
        q = lerp2(p0, p1, f)
        hedgehog(q[0] + n[0] * 0.067, q[1] + n[1] * 0.067, ang + k * math.pi / 3, 0.85)
    pk = tex("wood", WOOD_D, 3.0)
    for f in (0.16, 0.39, 0.61, 0.84):
        ebox(p0, p1, L * f - 0.006, L * f + 0.006, 0.08, 0.012, 0.0, 0.1, pk)
    zigzag_wire(p0, p1, L * 0.16, L * 0.84, 0.08, 0.06, 0.018, 10, flat("wire", "#4c4f55", 0.5))


def f6_post(p):
    """Hexagonal concrete pillbox: dark firing slits round the front, a camouflage of turf and net, a steel door
    in a hazard-striped frame at the back, a radio mast and a searchlight on the roof."""
    a = math.atan2(p[1], p[0])
    cm = tex("plaster", "#a9a59c", 2.0)
    cy(0.13, 0.13, (p[0], p[1], 0.065), cm, 6, r2=0.11, rot=(0, 0, a))
    cy(0.135, 0.03, (p[0], p[1], 0.145), cm, 6, rot=(0, 0, a))
    uvs(0.105, (p[0], p[1], 0.16), cm, 10, 5, (1, 1, 0.38))
    camo = [flat("camo1", "#5d6b3c", 0.85), flat("camo2", "#7a6a48", 0.85)]
    for k in range(5):
        q = a + k * 1.3 + 0.4
        ico(0.034, (p[0] + math.cos(q) * 0.1, p[1] + math.sin(q) * 0.1, 0.07 + (k % 2) * 0.04), camo[k % 2], (1.2, 1.2, 0.35))
    sl = []
    for d_ in (-math.pi / 3, 0.0, math.pi / 3):  # firing slits on the three outer faces
        q = a + d_
        rr = 0.102  # the slanted face's distance at the slit height
        sl.append((p[0] + math.cos(q) * rr, p[1] + math.sin(q) * rr, 0.095, q + math.pi / 2, 0.0, 0.07, 0.018))
    slits(sl, one_side=True)
    # the door at the back in a hazard-striped frame
    qb = a + math.pi
    for (rr, w_, h_, mt) in ((0.106, 0.06, 0.09, hazard(0.02)), (0.11, 0.04, 0.075, flat("door6", "#4a5048", 0.6))):
        bx((w_, 0.012, h_), (p[0] + math.cos(qb) * rr, p[1] + math.sin(qb) * rr, h_ / 2), mt, qb + math.pi / 2, 0)
    # radio mast
    mx, my = p[0] + math.cos(a + 2.2) * 0.05, p[1] + math.sin(a + 2.2) * 0.05
    rod((mx, my, 0.18), (mx, my, 0.29), 0.004, flat("mast", "#3b3d42", 0.6), r2=0.0015, n=4)
    bx((0.03, 0.004, 0.004), (mx, my, 0.27), flat("mast", "#3b3d42", 0.6), a, 0)

    def searchl():
        cy(0.012, 0.05, (0, 0, 0.025), flat("iron", "#3b3d42", 0.6), 6)
        cy(0.035, 0.06, (0.0, 0, 0.07), flat("lamp", "#5b636b", 0.5), 10, rot=(0, math.pi / 2 - 0.35, 0))
        cy(0.03, 0.01, (0.032, 0, 0.081), glow("lens", "#fff4c2", 5.0), 10, rot=(0, math.pi / 2 - 0.35, 0))
    build_at(searchl, p[0], p[1], a, z=0.16)


F7_PLATES = ("#4f5761", "#8e98a4")  # dark seams round pale steel plates (the plates read light, as the old wall did)


def f7_edge(p0, p1, gate=False):
    """Steel wall: pale riveted plates with dark seams between buttress ribs, a bold solid yellow coping (the gold
    outline that makes L7 read on the map) with amber warning lamps, a wide hazard-striped band lower down wrapping
    the ribs, razor wire along the top and a plinth."""
    L, ang, mid, n = edge_frame(p0, p1)
    plates = facade(F7_PLATES[0], F7_PLATES[1], 0.11, 0.11, 0.94, 0.9, lit=F7_PLATES[1], lit_p=0.0)
    rib = flat("steelrib", "#5c6570", 0.45)
    ebox(p0, p1, 0.08, L - 0.08, 0.0, 0.06, 0.0, 0.33, plates)
    for i in range(5):
        u = L * (0.18 + i * 0.64 / 4)
        ebox(p0, p1, u - 0.011, u + 0.011, 0.0, 0.075, 0.0, 0.33, rib)
    ebox(p0, p1, 0.08, L - 0.08, 0.0, 0.08, 0.235, 0.28, hazard_dir(0.1, ang))  # wide stripes: they survive the map
    ebox(p0, p1, 0.08, L - 0.08, 0.0, 0.074, 0.33, 0.36, flat("warn", "#f2c230", 0.6))
    ebox(p0, p1, 0.08, L - 0.08, 0.0, 0.082, 0.0, 0.03, rib)
    zigzag_wire(p0, p1, 0.1, L - 0.1, 0.0, 0.385, 0.02, 8, flat("wire", "#c3c9d1", 0.4), w=0.009)
    for f in (0.34, 0.66):  # warning lamps on the coping
        c = lerp2(p0, p1, f)
        bx((0.024, 0.024, 0.02), (c[0] + n[0] * 0.025, c[1] + n[1] * 0.025, 0.37), glow("warnlamp", "#ffb02e", 3.0), ang, 0)


def f7_post(p):
    """Steel watchtower: a plated drum with a solid yellow top band (it ties into the coping) and a hazard-striped
    band level with the wall's, a twin-gun turret with a red sensor, a cold floodlight on the inner side and a red
    beacon."""
    a = math.atan2(p[1], p[0])
    dm = flat("steelrib", "#5c6570", 0.45)
    plates = facade(F7_PLATES[0], F7_PLATES[1], 0.08, 0.1, 0.92, 0.9, lit=F7_PLATES[1], lit_p=0.0)
    cy(0.1, 0.42, (p[0], p[1], 0.21), plates, 8, rot=(0, 0, a))
    # (the bands turn with the drum: an octagon turned against another pokes its corners through)
    cy(0.105, 0.03, (p[0], p[1], 0.405), flat("warn", "#f2c230", 0.6), 8, rot=(0, 0, a))
    cy(0.105, 0.045, (p[0], p[1], 0.2575), hazard_ring(p[0], p[1], 0.105, 8), 8, rot=(0, 0, a))
    cy(0.106, 0.03, (p[0], p[1], 0.03), dm, 8, rot=(0, 0, a))
    bx((0.03, 0.016, 0.02), (p[0] - math.cos(a) * 0.1, p[1] - math.sin(a) * 0.1, 0.36), glow("flood", "#d8f0ff", 3.0),
       a + math.pi / 2, 0)

    def head():
        cy(0.065, 0.04, (0, 0, 0.02), dm, 10)
        bx((0.13, 0.1, 0.07), (0.01, 0, 0.075), flat("steelwall", "#7f8995", 0.45), bev=0)
        for sy in (-1, 1):
            cy(0.012, 0.11, (0.1, sy * 0.025, 0.08), dm, 6, rot=(0, math.pi / 2, 0))
        bx((0.012, 0.04, 0.02), (0.075, 0, 0.1), glow("sensor", "#ff4a3a", 4.0), bev=0)
        bx((0.012, 0.012, 0.016), (-0.04, 0.03, 0.118), glow("beacon", "#ff4a3a", 4.0), bev=0)
    build_at(head, p[0], p[1], a + math.pi / 6, z=0.42)


def f8_edge(p0, p1, gate=False):
    """Energy wall of the late era (reference frame 2's steel walls with cold light): composite plates with dark
    seams on a steel base, glowing joints and a light line along the coping, a central emitter pylon, and an energy
    curtain on a light lattice between the pylons."""
    L, ang, mid, n = edge_frame(p0, p1)
    comp = facade("#9aa2ac", "#555d68", 0.12, 0.08, 0.94, 0.86, lit="#555d68", lit_p=0.0)
    trim = flat("comptrim", "#3e444d", 0.5)
    cyan = glow("cyan", CYAN, 2.5)
    ebox(p0, p1, 0.04, L - 0.04, 0.0, 0.07, 0.0, 0.14, comp)
    ebox(p0, p1, 0.04, L - 0.04, 0.0, 0.076, 0.0, 0.04, trim)
    ebox(p0, p1, 0.04, L - 0.04, 0.0, 0.076, 0.14, 0.152, trim)
    ebox(p0, p1, 0.04, L - 0.04, 0.0, 0.078, 0.094, 0.104, cyan)
    for f in (0.17, 0.33, 0.67, 0.83):  # glowing joints between the plates
        u = L * f
        ebox(p0, p1, u - 0.005, u + 0.005, 0.0, 0.078, 0.04, 0.14, cyan)
    # mid pylon with an emitter head
    ebox(p0, p1, L / 2 - 0.03, L / 2 + 0.03, 0.0, 0.08, 0.0, 0.46, comp)
    ebox(p0, p1, L / 2 - 0.031, L / 2 + 0.031, 0.029, 0.032, 0.04, 0.44, trim)
    ebox(p0, p1, L / 2 - 0.007, L / 2 + 0.007, 0.047, 0.006, 0.06, 0.42, cyan)
    ebox(p0, p1, L / 2 - 0.04, L / 2 + 0.04, 0.0, 0.09, 0.46, 0.475, trim)
    ebox(p0, p1, L / 2 - 0.016, L / 2 + 0.016, 0.0, 0.03, 0.475, 0.5, cyan)
    for (fa, fb) in ((0.06, 0.465), (0.535, 0.94)):
        qa, qb = lerp2(p0, p1, fa), lerp2(p0, p1, fb)
        beam((qa[0], qa[1], 0.44), (qb[0], qb[1], 0.44), 0.01, cyan)  # the bright upper edge of the field
        qm = lerp2(p0, p1, (fa + fb) / 2)
        # the field: a deep blue sheet in three bands (a scanning look) between the coping and the top edge
        for (z0, z1) in ((0.16, 0.25), (0.265, 0.345), (0.36, 0.43)):
            bx((math.dist(qa, qb), 0.006, z1 - z0), (qm[0], qm[1], (z0 + z1) / 2), glow("curtain", "#1a8fd0", 0.7), ang, 0)
        for q in (qa, qb):  # emitter nodes at the field's top corners
            bx((0.022, 0.03, 0.022), (q[0], q[1], 0.44), trim, ang, 0)


def f8_post(p):
    """Emitter pylon: a steel base, a composite shaft with cold light strips and three light rings, dark emitter
    fins and a glowing orb on the cap."""
    a = math.atan2(p[1], p[0])
    comp = facade("#9aa2ac", "#555d68", 0.05, 0.1, 0.9, 0.9, lit="#555d68", lit_p=0.0)
    trim = flat("comptrim", "#3e444d", 0.5)
    cyan = glow("cyan", CYAN, 2.5)
    cy(0.075, 0.08, (p[0], p[1], 0.04), trim, 6, rot=(0, 0, a))
    bx((0.09, 0.09, 0.52), (p[0], p[1], 0.3), comp, a, 0)
    bx((0.016, 0.094, 0.44), (p[0], p[1], 0.3), cyan, a, 0)
    bx((0.094, 0.016, 0.44), (p[0], p[1], 0.3), cyan, a, 0)
    for z in (0.2, 0.36, 0.5):
        bx((0.104, 0.104, 0.012), (p[0], p[1], z), cyan, a, 0)
    for s_ in (-1, 1):  # emitter fins along the wall lines
        q = a + s_ * math.pi / 2
        bx((0.012, 0.05, 0.2), (p[0] + math.cos(q) * 0.055, p[1] + math.sin(q) * 0.055, 0.42), trim, q, 0)
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
    """A farmstead on an owned open hex (the settled countryside of the reference frames): a half-timbered cottage
    under a coursed roof in the owner's colour with a smoking brick chimney, a fenced vegetable patch, a haystack,
    a woodpile and barrels by the door."""
    build_at(lambda: cottage(0.24, 0.19, 0.17, team, smoke=True, pitch=1.06), 0.0, 0.05, 0.15)
    build_at(lambda: garden(0.2, 0.13, 3), -0.02, -0.25, 0.15)
    haystack(0.22, -0.1, 0.7)
    build_at(lambda: woodpile(2), 0.27, 0.16, 1.4, 0.7)
    for (x, y) in ((-0.19, -0.06), (-0.22, -0.01)):
        cy(0.02, 0.045, (x, y, 0.0225), tex("wood", WOOD, 3.0), 8)
        cy(0.021, 0.006, (x, y, 0.034), flat("band", "#3d3f45", 0.5), 8)


# ------------------------------------------------------------------ LATE-ERA COUNTRYSIDE (DL6+ homesteads, farms, mine)
# Reference frame 3 shows how lived-in the countryside is (houses with gardens, fences, carts, fields round a mill);
# frame 2 shows the late-era version (fields with machinery, greenhouse domes, silos, small compounds, glowing
# crystal extraction). These builders bring the DL6+ homesteads, farms and the DL8 mine up to that density.


def lr_bands(key, axis, period, c1, c2):
    """Two-colour bands across one world axis (0 x, 1 y, 2 z), one pair per period: lap siding, corrugated steel,
    ploughed furrows, mown lawn stripes, garage door panels (baked like every procedural colour)."""
    def s_of(nt, L, pos):
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(pos, sp.inputs[0])
        dv = nt.nodes.new("ShaderNodeMath")
        dv.operation = "DIVIDE"
        L.new(sp.outputs[axis], dv.inputs[0])
        dv.inputs[1].default_value = period
        return dv.outputs[0]
    return _stripe_mat(("lr_bands", key, axis, period, c1, c2), s_of, c1, c2)


def lr_window(x, y, z, rz, w=0.032, h=0.036, lit=True, frame="#33373d", wall=None):
    """A window on a wall facing −Y (rotated rz), all flat plates (a mobile homestead has a dozen of them): a frame,
    warm lit (or dark) glass, a mullion and a pale sill. «Raivon Soft»: w and h × WIN_K, the frame lighter
    (frame_c)."""
    w, h = w * WIN_K, h * WIN_K
    frame = frame_c(frame, wall)

    def b():
        fm, gl, sl = _MB(), _MB(), _MB()
        fm.face([(-w / 2 - 0.005, -0.003, -h / 2 - 0.005), (w / 2 + 0.005, -0.003, -h / 2 - 0.005),
                 (w / 2 + 0.005, -0.003, h / 2 + 0.005), (-w / 2 - 0.005, -0.003, h / 2 + 0.005)], (0, -1, 0))
        gl.face([(-w / 2, -0.005, -h / 2), (w / 2, -0.005, -h / 2), (w / 2, -0.005, h / 2), (-w / 2, -0.005, h / 2)],
                (0, -1, 0))
        fm.face([(-0.002, -0.0065, -h / 2), (0.002, -0.0065, -h / 2), (0.002, -0.0065, h / 2), (-0.002, -0.0065, h / 2)],
                (0, -1, 0))
        z0 = -h / 2 - 0.004
        sl.face([(-w / 2 - 0.008, 0.0, z0), (w / 2 + 0.008, 0.0, z0), (w / 2 + 0.008, -0.014, z0),
                 (-w / 2 - 0.008, -0.014, z0)], (0, 0, 1))
        sl.face([(-w / 2 - 0.008, -0.014, z0), (w / 2 + 0.008, -0.014, z0), (w / 2 + 0.008, -0.014, z0 - 0.006),
                 (-w / 2 - 0.008, -0.014, z0 - 0.006)], (0, -1, 0))
        fm.obj(flat("frame" + frame, frame, 0.6), "win_frame")
        gl.obj(win_lit() if lit else flat("glass_d", "#2b3a4c", 0.25), "win_glass")
        sl.obj(flat("sill", "#f4f2ec", 0.6), "win_sill")
    build_at(b, x, y, rz, z=z)


def lr_picket_fence(segs, h=0.034, gap=0.024, c="#f4f2ec"):
    """A white picket fence (the bright outline of a suburban lot that reads at map distance): a post at every
    segment end, two rails and square pickets along each (x0, y0, x1, y1) segment, all two-sided plates."""
    from mathutils import Vector
    fm = flat("picket", c, 0.6)
    mb = _MB()
    posts = {}
    for (x0, y0, x1, y1) in segs:
        L = math.dist((x0, y0), (x1, y1))
        e = Vector(((x1 - x0) / L, (y1 - y0) / L, 0))
        nrm = Vector((-e.y, e.x, 0))
        p0, p1 = Vector((x0, y0, 0)), Vector((x1, y1, 0))
        for side in (1, -1):
            o = nrm * (0.0055 * side)
            for z in (h * 0.32, h * 0.74):
                mb.face([p0 + o + Vector((0, 0, z - 0.003)), p1 + o + Vector((0, 0, z - 0.003)),
                         p1 + o + Vector((0, 0, z + 0.003)), p0 + o + Vector((0, 0, z + 0.003))], nrm * side)
        for p in ((x0, y0), (x1, y1)):
            posts[(round(p[0], 4), round(p[1], 4))] = p
        k = max(2, int(L / gap))
        for i in range(k):
            c0 = p0 + e * (L * (i + 0.5) / k)
            for side in (1, -1):
                o = nrm * (0.004 * side)
                mb.face([c0 - e * 0.0045 + o, c0 + e * 0.0045 + o, c0 + e * 0.0045 + o + Vector((0, 0, h)),
                         c0 - e * 0.0045 + o + Vector((0, 0, h))], nrm * side)
    mb.obj(fm, "pickets")
    for (px, py) in posts.values():
        bx((0.012, 0.012, h + 0.008), (px, py, (h + 0.008) / 2), fm, bev=0)


def lr_polytunnel(x, y, L, r, rz=0.0):
    """A polytunnel greenhouse: a pale film barrel vault on white hoops, dark doors at both ends."""
    def b():
        film = flat("film", "#dcecef", 0.25)
        hoop = flat("hoop", "#fbfbf8", 0.5)
        seg = 6
        arc = [(r * math.cos(math.pi * i / seg), r * math.sin(math.pi * i / seg) * 1.05) for i in range(seg + 1)]
        vault, ends, ribs = _MB(), _MB(), _MB()
        for i in range(seg):
            (y0, z0), (y1, z1) = arc[i], arc[i + 1]
            n = (0, (y0 + y1) / 2, (z0 + z1) / 2)
            vault.face([(-L / 2, y0, z0), (L / 2, y0, z0), (L / 2, y1, z1), (-L / 2, y1, z1)], n)
            for k in range(5):
                xr = -L / 2 + 0.006 + k * (L - 0.012) / 4
                ribs.strip((xr, y0, z0), (xr, y1, z1), n, 0.007, 0.002)
        for sx in (-1, 1):
            ends.face([(sx * L / 2, yy, zz) for yy, zz in arc], (sx, 0, 0))
        vault.obj(film, "tunnel")
        ends.obj(film, "tunnel_ends")
        ribs.obj(hoop, "hoops")
        for sx in (-1, 1):
            bx((0.004, r * 0.7, r * 0.8), (sx * (L / 2 + 0.002), 0, r * 0.4), flat("tunnel_door", "#5d6b6e", 0.6), bev=0)
        bx((L * 0.8, 0.004, 0.006), (0, -r * 0.62, r * 0.82), flat("crop_in", "#5f9a3a", 0.8), bev=0)
    build_at(b, x, y, rz)


def lr_raised_bed(x, y, w, d, rz=0.0, crop="#4f9a34", n=4):
    """A plank raised bed with dark soil and a row of leafy heads in two greens."""
    def b():
        bx((w, d, 0.026), (0, 0, 0.013), tex("wood", "#8a5e36", 3.0), bev=0)
        bx((w - 0.01, d - 0.01, 0.004), (0, 0, 0.027), flat("soil_d", "#4a3322", 0.95), bev=0)
        for i in range(n):
            u = (i + 0.5) / n * (w - 0.014) - (w - 0.014) / 2
            c = crop if i % 2 == 0 else shade(crop, 1.3)
            ico(min(d * 0.36, 0.016), (u, 0, 0.034), flat("crop" + c, c, 0.8), (1, 1, 0.75), sub=1)
    build_at(b, x, y, rz)


def lr_porch(x, y, team, w=0.07):
    """A front porch on a wall facing −Y: a door in the team colour, a step, a pale canopy on two posts, a lamp."""
    trim = flat("trim_w", "#f7f5ef", 0.6)
    bx((0.034, 0.008, 0.062), (x, y - 0.002, 0.051), flat("frame#33373d", "#33373d", 0.6), bev=0)
    bx((0.028, 0.012, 0.056), (x, y - 0.004, 0.048), flat("door" + team, shade(team, 0.8), 0.5), bev=0)
    bx((w, 0.04, 0.012), (x, y - 0.02, 0.014), flat("plinth_c", "#8d8a84", 0.8), bev=0)
    bx((w + 0.01, 0.05, 0.008), (x, y - 0.022, 0.086), trim, bev=0)
    for sx in (-1, 1):
        bx((0.007, 0.007, 0.07), (x + sx * w * 0.42, y - 0.04, 0.054), trim, bev=0)
    bx((0.01, 0.006, 0.012), (x + 0.026, y - 0.006, 0.07), glow("lamp_warm", "#ffcf7a", 3.0), bev=0)


def lr_thuja(x, y, h, r=0.019):
    """A columnar conifer (the thuja row of a suburban lot; slim enough for the strip between a wall and a fence):
    a short trunk under two narrow stacked cones in two greens."""
    cy(0.006, 0.02, (x, y, 0.01), tex("wood", "#6a4327"), 5)
    cn(r, h * 0.62, (x, y, 0.012 + h * 0.31), flat("pine", "#2a6233", 0.8), 7)
    cn(r * 0.8, h * 0.55, (x, y, h * 0.695), flat("pine_l", "#347a3c", 0.8), 7)


def lr_farmhouse(team, smoke=True):
    """The DL6–7 farmhouse (reference frame 3's cottages brought up to date): a concrete plinth, cream lap siding
    with white corner boards, warm lit windows in dark frames on two floors, a gable roof laid in team-slate courses
    with an attic window, a brick chimney with smoke, a porch with a team door, and an attached garage under a flat
    roof with solar panels and a panelled door."""
    w, d, h = 0.2, 0.14, 0.125
    siding = lr_bands("siding", 2, 0.017, "#f2ede2", "#d9d2c3")
    trim = flat("trim_w", "#f7f5ef", 0.6)
    bx((w + 0.012, d + 0.012, 0.018), (0, 0, 0.009), flat("plinth_c", "#8d8a84", 0.8), bev=0)
    bx((w, d, h), (0, 0, h / 2), siding, bev=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.01, 0.01, h - 0.018), (sx * w / 2, sy * d / 2, 0.018 + (h - 0.018) / 2), trim, bev=0)
    bx((w + 0.008, d + 0.008, 0.008), (0, 0, 0.066), trim, bev=0)  # the floor band between the storeys
    z1, z2 = 0.042, 0.097
    for (u, z, lit) in ((-0.065, z1, True), (-0.065, z2, False), (0.0, z2, True), (0.065, z2, True)):
        lr_window(u, -d / 2 - 0.004, z, 0.0, lit=lit)
    for (u, z, lit) in ((-0.06, z1, False), (0.03, z1, True), (-0.06, z2, True), (0.03, z2, False)):
        lr_window(u, d / 2 + 0.004, z, math.pi, lit=lit)
    for (u, z, lit) in ((0.0, z1, False), (0.0, z2, True)):  # the left gable wall (the garage covers the right one)
        lr_window(-(w / 2 + 0.004), u, z, -math.pi / 2, lit=lit)  # (rz -pi/2 turns the window's -Y face to -X)
    lr_porch(0.06, -d / 2 - 0.004, team)
    bx((0.11, 0.016, 0.014), (-0.04, -d / 2 - 0.012, 0.007), flat("bed_soil", "#5a3d26", 0.9), bev=0)  # flower bed
    for i, c in enumerate(("#e0485c", "#f4c84a", "#e0485c", "#f2f0ea", "#c95ad6")):
        ico(0.011, (-0.088 + i * 0.024, -d / 2 - 0.013, 0.018), flat("flower" + c, c, 0.8), (1, 1, 0.8), sub=1)
    rh = 0.078
    gable_roof(w, d, rh, (0, 0, h), slate(team), siding, n=5, barge="#ebe8e1", ridge="#2c3036", ridge_t=0.02,
               gable_timber=None, gable_win=True, eave_z=0.0, **SOFT_ROOF)
    cx_, cy_ = -0.055, 0.035
    top = chimney(cx_, cy_, h, h + roof_surface(cy_, d / 2, rh, eave_z=0.0) + 0.05, w=0.036)
    if smoke:
        smoke_at(cx_, cy_, top)
    # the garage: siding, a flat roof with a pale parapet, a panelled door with a lamp over it, solar panels
    gx, gw, gd, gh = w / 2 + 0.06, 0.12, 0.13, 0.08
    bx((gw, gd, gh), (gx, 0.0, gh / 2), siding, bev=0)
    bx((gw + 0.01, gd + 0.01, 0.012), (gx, 0.0, gh + 0.006), trim, bev=0)
    bx((gw - 0.012, gd - 0.012, 0.004), (gx, 0.0, gh + 0.012), flat("roof_d", "#4a4e55", 0.8), bev=0)
    bx((0.084, 0.008, 0.062), (gx, -gd / 2 - 0.002, 0.032), flat("frame#33373d", "#33373d", 0.6), bev=0)
    bx((0.076, 0.012, 0.056), (gx, -gd / 2 - 0.004, 0.029), lr_bands("gdoor", 2, 0.011, "#f5f3ee", "#c9c6bf"), bev=0)
    bx((0.012, 0.006, 0.01), (gx, -gd / 2 - 0.006, 0.07), glow("lamp_warm", "#ffcf7a", 3.0), bev=0)
    sm = solar8()
    for i in range(2):
        for j in range(2):
            px, py = gx - 0.026 + i * 0.052, -0.03 + j * 0.06
            bx((0.046, 0.05, 0.005), (px, py, gh + 0.03), sm, bev=0, rot=(0.42, 0, 0))
            bx((0.04, 0.006, 0.02), (px, py + 0.018, gh + 0.02), flat("rail_s", "#9aa1a9", 0.5), bev=0)
    return gx


def homestead_modern(team):
    """DL6–7 countryside (reference frame 3's lived-in homesteads, brought up to date): a farmhouse with a team-slate
    gable roof, a smoking chimney and a porch, an attached garage with solar panels, a car in the team colour on the
    concrete drive, a white picket fence round a mown lawn, a polytunnel and raised vegetable beds, a doghouse, a
    mailbox, a shade tree and a pine."""
    X0, X1, Y0, Y1 = -0.26, 0.245, -0.195, 0.195
    bx((X1 - X0, Y1 - Y0, 0.006), ((X0 + X1) / 2, (Y0 + Y1) / 2, 0.003),
       lr_bands("lawn", 0, 0.052, "#6ba849", "#5c963f"), bev=0)
    hx, hy = -0.09, 0.095
    gx = build_at(lambda: lr_farmhouse(team), hx, hy)
    dx = hx + gx
    bx((0.09, hy - 0.065 - Y0, 0.006), (dx, (hy - 0.065 + Y0) / 2, 0.006), flat("drive", "#aaa69e", 0.85), bev=0)
    bx((0.05, 0.035, 0.006), (hx + 0.06, hy - 0.11, 0.006), flat("drive", "#aaa69e", 0.85), bev=0)  # porch path
    build_at(lambda: car(dx, -0.1, math.pi / 2 + 0.04, team), z=0.009)  # (on the drive, not sunk into it)
    lr_picket_fence([(X0, Y0, dx - 0.05, Y0), (dx + 0.05, Y0, X1, Y0), (X1, Y0, X1, Y1), (X1, Y1, X0, Y1),
                     (X0, Y1, X0, Y0)])
    # the kitchen garden in the front corner: a polytunnel and two raised beds
    lr_polytunnel(-0.15, -0.15, 0.17, 0.036)
    lr_raised_bed(-0.21, -0.06, 0.1, 0.04)
    lr_raised_bed(-0.095, -0.06, 0.1, 0.04, crop="#7aa83a")
    # the side lawn: a trampoline in the team colour, a mailbox by the drive, a shade tree; a pine and a rain barrel
    # behind the house
    tx, ty = 0.185, -0.075
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        cy(0.003, 0.024, (tx + math.cos(a) * 0.04, ty + math.sin(a) * 0.04, 0.012), flat("post_d", "#3a3e44", 0.6), 4)
    cy(0.047, 0.008, (tx, ty, 0.026), flat("tramp" + team, team, 0.5), 12)
    cy(0.035, 0.002, (tx, ty, 0.031), flat("tramp_mat", "#22252a", 0.9), 12)
    cy(0.004, 0.044, (dx + 0.064, Y0 - 0.014, 0.022), flat("post_d", "#3a3e44", 0.6), 6)
    bx((0.016, 0.026, 0.014), (dx + 0.064, Y0 - 0.014, 0.05), flat("mail" + team, team, 0.5), bev=0)
    tree(0.2, 0.13, 1.0)
    for (x, y) in ((-0.23, 0.128), (-0.23, 0.168)):  # columnar conifers in the narrow strip by the left gable
        lr_thuja(x, y, 0.13)
    cy(0.018, 0.04, (X0 + 0.05, hy - 0.04, 0.02), flat("barrel_g", "#4f6b4a", 0.7), 8)


def lr_dome_ribs(x, y, z0, R, C, mt, n=8, phis=(0.0, 0.4, 0.8, 1.15, 1.4), ring=0.62, t=0.01):
    """Pale ribs over a dome of radius R and rise C standing at z0 (the ribbed glass domes of frame 2): n meridian
    ribs and one ring rib round the shoulder."""
    def pt(phi, a):
        return (x + R * math.cos(phi) * math.cos(a), y + R * math.cos(phi) * math.sin(a), z0 + C * math.sin(phi))

    def nrm(phi, a):
        v = (math.cos(phi) * math.cos(a) / R, math.cos(phi) * math.sin(a) / R, math.sin(phi) / C)
        ln = math.sqrt(sum(c * c for c in v))
        return tuple(c / ln for c in v)
    ribs = _MB()
    for k in range(n):
        a = math.tau * k / n + math.pi / n
        for i in range(len(phis) - 1):
            ribs.strip(pt(phis[i], a), pt(phis[i + 1], a), nrm((phis[i] + phis[i + 1]) / 2, a), t, 0.003)
    m = 2 * n
    if ring:
        for k in range(m):
            a0, a1 = math.tau * k / m, math.tau * (k + 1) / m
            ribs.strip(pt(ring, a0), pt(ring, a1), nrm(ring, (a0 + a1) / 2), t * 0.9, 0.003)
    ribs.obj(mt, "ribs")


def lr_ring_panes(x, y, r, z0, z1, n, mt, fill=0.62, off=0.003):
    """n flat panes round a drum of radius r between z0 and z1 (a ribbon of windows broken by the drum's mullions)."""
    mb = _MB()
    for k in range(n):
        a0 = math.tau * k / n
        a1 = a0 + math.tau / n * fill
        am = (a0 + a1) / 2
        p = [(x + (r + off) * math.cos(a), y + (r + off) * math.sin(a)) for a in (a0, a1)]
        mb.face([(p[0][0], p[0][1], z0), (p[1][0], p[1][1], z0), (p[1][0], p[1][1], z1), (p[0][0], p[0][1], z1)],
                (math.cos(am), math.sin(am), 0))
    return mb.obj(mt, "panes")


def lr_drone(x, y, z, team, mats, rz=0.0, s=1.0):
    """A quadcopter drone (the small craft over the fields of frame 2): a steel body with a team top and a cold eye,
    four arms, dark rotor discs with lit hubs."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((0.036, 0.036, 0.014), (0, 0, 0.007), seam, bev=0)
        bx((0.028, 0.028, 0.005), (0, 0, 0.016), flat("hullteam" + team, team, 0.5), bev=0)
        bx((0.01, 0.004, 0.006), (0, -0.019, 0.007), tip, bev=0)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            ex, ey = math.cos(a) * 0.04, math.sin(a) * 0.04
            beam((0, 0, 0.01), (ex, ey, 0.012), 0.006, plate)
            cy(0.019, 0.003, (ex, ey, 0.016), flat("rotor", "#1d2026", 0.4), 7)
            cy(0.004, 0.006, (ex, ey, 0.016), tip, 4)
        for sx in (-1, 1):  # landing skids
            bx((0.004, 0.04, 0.004), (sx * 0.014, 0, -0.004), plate, bev=0)
    build_at(b, x, y, rz, s=s, z=z)


def lr_offset_line(pts, d):
    """The polyline pts shifted sideways by d (to the left of travel), mitred at every bend, so ribbons laid between
    two offsets join without overlapping."""
    def nrm(a, b):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        return -(b[1] - a[1]) / L, (b[0] - a[0]) / L
    out = []
    for i, p in enumerate(pts):
        if i == 0:
            nx, ny = nrm(pts[0], pts[1])
        elif i == len(pts) - 1:
            nx, ny = nrm(pts[-2], pts[-1])
        else:
            (ax, ay), (bx_, by_) = nrm(pts[i - 1], p), nrm(p, pts[i + 1])
            mx, my = ax + bx_, ay + by_
            ml = math.hypot(mx, my)
            k = 1.0 / max((mx * ax + my * ay) / ml, 0.3)  # 1 / cos(half the bend)
            nx, ny = mx / ml * k, my / ml * k
        out.append((p[0] + nx * d, p[1] + ny * d))
    return out


def lr_ribbon(mb, pts, d0, d1, z):
    """Quads between the offsets d0 and d1 of the polyline pts, flat at height z (one joined, mitred strip)."""
    A, B = lr_offset_line(pts, d0), lr_offset_line(pts, d1)
    for i in range(len(pts) - 1):
        mb.face([(A[i][0], A[i][1], z), (A[i + 1][0], A[i + 1][1], z), (B[i + 1][0], B[i + 1][1], z),
                 (B[i][0], B[i][1], z)], (0, 0, 1))


def lr_lit_path(pts, w, mats, z=0.009, ext=(0.004, 0.004)):
    """A dark footpath with a thin cold light line along each edge, along the polyline pts, on a pale kerb slab — each
    layer one mitred strip, so the bends have no overlapping faces (no black seams, no z-fighting)."""
    st, plate, seam, panel, cap, neon, tip = mats
    road, edge, kerb = _MB(), _MB(), _MB()
    lr_ribbon(road, pts, -w / 2, w / 2, z)
    for sd in (-1, 1):
        lr_ribbon(edge, pts, sd * w / 2 - 0.003, sd * w / 2 + 0.003, z + 0.002)
    # the kerb runs ext past each end (a negative ext stops it short, where the path joins another one's kerb) and
    # stands out 6 mm on both sides: a top ribbon, walls and end caps
    (x0, y0), (x1, y1) = pts[0], pts[1]
    L = math.hypot(x1 - x0, y1 - y0)
    a = (x0 - (x1 - x0) / L * ext[0], y0 - (y1 - y0) / L * ext[0])
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0)
    b = (x1 + (x1 - x0) / L * ext[1], y1 + (y1 - y0) / L * ext[1])
    kp = [a] + list(pts[1:-1]) + [b]
    hw, zk = w / 2 + 0.006, z - 0.003
    lr_ribbon(kerb, kp, -hw, hw, zk)
    for sd in (-1, 1):
        o = lr_offset_line(kp, sd * hw)
        for i in range(len(kp) - 1):
            (ex, ey), (fx, fy) = o[i], o[i + 1]
            kerb.face([(ex, ey, -0.002), (fx, fy, -0.002), (fx, fy, zk), (ex, ey, zk)], (sd * -(fy - ey), sd * (fx - ex), 0))
    for (i, j) in ((0, 1), (-1, -2)):
        l_, r_ = lr_offset_line(kp, hw)[i], lr_offset_line(kp, -hw)[i]
        ox, oy = kp[i][0] - kp[j][0], kp[i][1] - kp[j][1]
        kerb.face([(l_[0], l_[1], -0.002), (r_[0], r_[1], -0.002), (r_[0], r_[1], zk), (l_[0], l_[1], zk)], (ox, oy, 0))
    road.obj(flat("path8", "#2f343b", 0.7), "path")
    edge.obj(neon, "path_lights")
    kerb.obj(seam, "path_kerb")


def lr_mast(x, y, h, mats, z0=0.0):
    """d8_mast (a slim pale pole with a cold lamp, the lamp at the same height) for ground that is not the districts'
    0.02 plate: the pole starts at z0 (bare ground, a deck) on a small dark foot, so it never floats."""
    st, plate, seam, panel, cap, neon, tip = mats
    top = 0.02 + h
    cy(0.012, 0.012, (x, y, z0 + 0.004), plate, 6)
    cy(0.006, top - z0, (x, y, (z0 + top) / 2), seam, 6)
    bx((0.02, 0.02, 0.02), (x, y, top + 0.01), tip, bev=0)


def lr_planter(x, y, L, mats, rz=0.0):
    """A hydroponic trough: a steel box with a glowing nutrient channel and a row of leafy heads on it."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((L, 0.034, 0.03), (0, 0, 0.015), plate, bev=0)
        bx((L - 0.012, 0.022, 0.004), (0, 0, 0.031), glow("hydro", "#5cff8a", 1.2), bev=0)
        n = max(3, int(L / 0.026))
        for i in range(n):
            u = (i + 0.5) / n * (L - 0.016) - (L - 0.016) / 2
            c = "#3f8f3a" if i % 2 else "#62b347"
            ico(0.012, (u, 0, 0.039), flat("crop" + c, c, 0.8), (1, 1, 0.8), sub=1)
        bx((0.006, 0.04, 0.034), (-L / 2 - 0.003, 0, 0.017), seam, bev=0)
        bx((0.006, 0.04, 0.034), (L / 2 + 0.003, 0, 0.017), seam, bev=0)
    build_at(b, x, y, rz)


def homestead_scifi(team):
    """DL8 countryside (frames 2 and 5: small steel compounds with domes and cold light): a habitat pod in the
    citadel's steel kit — a plinth, a drum with a ribbon of warm lit windows over a team band with a light strip, a
    ribbed glass dome with a lit lantern and a needle — joined by a tube to a glowing hydroponic greenhouse dome and
    to a steel wing with an inset team panel, solar panels and a dish; an airlock porch; a landing pad with a
    parked drone; hydroponic planters; lit paths, light masts and pines."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    # the deck under the buildings: steel slabs with a pale kerb
    deck = [(-0.25, 0.0), (-0.21, -0.04), (0.21, -0.04), (0.25, 0.0), (0.25, 0.17), (0.2, 0.21), (-0.2, 0.21),
            (-0.25, 0.17)]
    extrude(deck, -0.01, 0.014, seam)
    extrude([(px * 0.96, py * 0.96 + 0.004) for px, py in deck], 0.0, 0.02, flat("ground8#4d545e", "#4d545e", 0.6))
    # the habitat pod
    px_, py_, r, h = 0.0, 0.085, 0.1, 0.07
    cy(r + 0.016, 0.02, (px_, py_, 0.03), plate, 16)
    cy(r, h, (px_, py_, 0.02 + h / 2), flat("hab_steel", "#626a74", 0.5), 16)
    cy(r + 0.004, 0.022, (px_, py_, 0.042), flat("hab_team" + team, shade(team, 0.78), 0.5), 16)
    cy(r + 0.006, 0.006, (px_, py_, 0.056), neon, 16)
    lr_ring_panes(px_, py_, r, 0.064, 0.084, 10, win_lit())
    zc = 0.02 + h
    cy(r * 1.1, 0.012, (px_, py_, zc + 0.006), plate, 16)
    R, C = r * 0.94, r * 0.94 * 0.74
    hemi(R, (px_, py_, zc + 0.012), flat("dome_glass", "#6fa9cf", 0.3), 16, 3, (1, 1, 0.74))
    lr_dome_ribs(px_, py_, zc + 0.012, R, C, seam)
    zt = zc + 0.012 + C
    cy(R * 0.26, 0.016, (px_, py_, zt + 0.004), plate, 8)
    cy(R * 0.18, 0.012, (px_, py_, zt + 0.016), tip, 8)
    rod((px_, py_, zt + 0.02), (px_, py_, 0.236), 0.005, cap, r2=0.0015, n=4)
    # the airlock porch on the front
    build_at(lambda: d8_portal(0, 0, 0, mats), px_, py_ - r - 0.012, 0.0, s=0.62, z=0.02)
    # the greenhouse dome on the left (glowing beds under the glass) and the tube to it
    gx, gy, gr = -0.175, 0.1, 0.062
    cy(gr + 0.01, 0.022, (gx, gy, 0.031), plate, 12)
    cy(gr + 0.012, 0.006, (gx, gy, 0.044), neon, 12)
    hemi(gr, (gx, gy, 0.042), glow("hydro", "#5cff8a", 1.2), 12, 3, (1, 1, 0.9))
    lr_dome_ribs(gx, gy, 0.042, gr, gr * 0.9, seam, n=6, phis=(0.0, 0.5, 0.95, 1.3), ring=0.55, t=0.009)
    rod((gx + gr * 0.6, gy - 0.004, 0.05), (px_ - r * 0.8, py_, 0.05), 0.02, plate, n=8)
    for f in (0.35, 0.65):
        x_ = gx + gr * 0.6 + (px_ - r * 0.8 - gx - gr * 0.6) * f
        cy(0.023, 0.008, (x_, gy - 0.004 + (py_ - gy + 0.004) * f, 0.05), seam, 8, rot=(0, math.pi / 2, 0))
    # the steel wing on the right: warm shopfront band, inset team panel with a light strip, solar panels and a dish
    wx, wy, ww, wd, wh = 0.168, 0.095, 0.105, 0.13, 0.07
    d8_podium(wx, wy, ww, wd, wh, mats, 0.0, plant=False, lights=False)
    pm, sm_ = _MB(), _MB()
    for (nx, ny, L, off) in ((0, -1, ww, wd / 2), (1, 0, wd, ww / 2)):
        qx, qy = wx + nx * (off + 0.003), wy + ny * (off + 0.003)
        tx, ty = -ny * L * 0.24, nx * L * 0.24
        pm.face([(qx - tx, qy - ty, 0.042), (qx + tx, qy + ty, 0.042), (qx + tx, qy + ty, 0.074),
                 (qx - tx, qy - ty, 0.074)], (nx, ny, 0))
        qx, qy = wx + nx * (off + 0.005), wy + ny * (off + 0.005)
        ux, uy = -ny * L * 0.2, nx * L * 0.2
        sm_.face([(qx - ux, qy - uy, 0.055), (qx + ux, qy + uy, 0.055), (qx + ux, qy + uy, 0.061),
                  (qx - ux, qy - uy, 0.061)], (nx, ny, 0))
    pm.obj(flat("hab_team" + team, shade(team, 0.78), 0.5), "panels")
    sm_.obj(neon, "strips")
    sol = solar8()
    for j in range(2):
        bx((0.07, 0.04, 0.005), (wx - 0.006, wy - 0.03 + j * 0.05, 0.108), sol, bev=0, rot=(0.4, 0, 0))
        bx((0.06, 0.006, 0.014), (wx - 0.006, wy - 0.016 + j * 0.05, 0.1), cap, bev=0)
    cy(0.004, 0.05, (wx + 0.035, wy + 0.045, 0.115), seam, 6)
    o = cy(0.022, 0.006, (wx + 0.035, wy + 0.045, 0.142), seam, 10, r2=0.012)
    o.rotation_euler = (0.6, 0, -0.6)
    bx((0.008, 0.008, 0.008), (wx + 0.035, wy + 0.045, 0.172), tip, bev=0)
    # the front yard: lit paths, the landing pad with the drone, the hydroponic planters, light masts
    lr_lit_path([(px_, -0.035), (px_, -0.12), (0.12, -0.155)], 0.04, mats)
    lr_lit_path([(px_ - 0.023, -0.12), (-0.105, -0.12)], 0.034, mats, ext=(-0.003, 0.004))  # (joins the first one)
    d8_pad(0.17, -0.155, 0.072, 0.03, mats)
    lr_drone(0.17, -0.155, 0.045, team, mats, rz=0.35, s=1.15)
    for k in range(3):
        lr_planter(-0.185, -0.075 - k * 0.048, 0.13, mats)
    lr_mast(-0.07, -0.2, 0.1, mats, -0.002)
    lr_mast(0.075, -0.06, 0.1, mats, -0.002)
    # pines behind the compound (frame 2: trees between the buildings)
    for (x, y, s_) in ((-0.1, 0.235, 0.62), (0.085, 0.24, 0.56), (-0.215, 0.165, 0.48)):
        pine(x, y, s_)


def lr_boards(key, period, c1, c2):
    """Vertical boards in two tones (barn siding) on walls facing any way: bands across x + y."""
    def s_of(nt, L, pos):
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(pos, sp.inputs[0])
        ad = nt.nodes.new("ShaderNodeMath")
        ad.operation = "ADD"
        L.new(sp.outputs[0], ad.inputs[0])
        L.new(sp.outputs[1], ad.inputs[1])
        dv = nt.nodes.new("ShaderNodeMath")
        dv.operation = "DIVIDE"
        L.new(ad.outputs[0], dv.inputs[0])
        dv.inputs[1].default_value = period
        return dv.outputs[0]
    return _stripe_mat(("lr_boards", key, period, c1, c2), s_of, c1, c2)


def lr_field(rect, z, mt, clip=None):
    """A field plate: the rectangle (x0, y0, x1, y1) clipped to the convex outline clip (CCW), standing z high."""
    x0, y0, x1, y1 = rect
    poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if clip:
        poly = _clip_convex(poly, clip)
    extrude(poly, -0.004, z, mt)
    return poly


def lr_span(c, lo, hi, R):
    """The part of [lo, hi] along a row at offset c that stays inside a circle of radius R."""
    lim = math.sqrt(max(R * R - c * c, 0.0))
    return max(lo, -lim), min(hi, lim)


def lr_ridges(rows, w, wt, h, z, mt, name="ridges"):
    """Crop ridges: a trapezoid prism from (xa, ya) to (xb, yb) for each row (bottom width w, top width wt, height h)
    standing on z; one mesh for all of them."""
    mb = _MB()
    for (xa, ya, xb, yb) in rows:
        L = math.hypot(xb - xa, yb - ya)
        if L < 0.02:
            continue
        ux, uy = (xb - xa) / L, (yb - ya) / L
        nx, ny = -uy, ux

        def P(px, py, s_, hh):
            return (px + nx * s_, py + ny * s_, z + hh)
        b0l, b0r, b1l, b1r = P(xa, ya, -w / 2, 0), P(xa, ya, w / 2, 0), P(xb, yb, -w / 2, 0), P(xb, yb, w / 2, 0)
        t0l, t0r, t1l, t1r = P(xa, ya, -wt / 2, h), P(xa, ya, wt / 2, h), P(xb, yb, -wt / 2, h), P(xb, yb, wt / 2, h)
        mb.face([t0l, t0r, t1r, t1l], (0, 0, 1))
        mb.face([b0r, b1r, t1r, t0r], (nx, ny, 0.5))
        mb.face([b1l, b0l, t0l, t1l], (-nx, -ny, 0.5))
        mb.face([b0l, b0r, t0r, t0l], (-ux, -uy, 0.3))
        mb.face([b1r, b1l, t1l, t1r], (ux, uy, 0.3))
    return mb.obj(mt, name)


def lr_ears(pts, mts, rnd, r=(0.013, 0.018), top=0.03, lean=0.008):
    """Ears of ripe grain: open three-sided pyramids at the points (x, y, z), each in one of the materials mts — a
    bristly golden mass at map distance (reference frame 3's wheat)."""
    mbs = [_MB() for _ in mts]
    for (x, y, zm) in pts:
        rr = rnd.uniform(*r)
        rot = rnd.uniform(0, math.tau)
        ap = (x + rnd.uniform(-lean, lean), y + rnd.uniform(-lean, lean), zm + top)
        base = [(x + rr * math.cos(rot + k * math.tau / 3), y + rr * math.sin(rot + k * math.tau / 3), zm)
                for k in range(3)]
        mb = mbs[rnd.randrange(len(mbs))]
        for k in range(3):
            p0, p1 = base[k], base[(k + 1) % 3]
            mb.face([p0, p1, ap], ((p0[0] + p1[0]) / 2 - x, (p0[1] + p1[1]) / 2 - y, rr * 0.6))
    for mb, mt in zip(mbs, mts):
        mb.obj(mt, "ears")


def lr_clumps(pts, mts, rnd, r=(0.02, 0.026)):
    """Leafy row crops: a squat five-leaf dome at each point (x, y, z), in one of the greens mts."""
    mbs = [_MB() for _ in mts]
    for (x, y, z) in pts:
        rr = rnd.uniform(*r)
        c = (x + rnd.uniform(-0.003, 0.003), y + rnd.uniform(-0.003, 0.003), z + rr * 0.8)
        rot = rnd.uniform(0, math.tau)
        rim = []
        for k in range(5):
            a = rot + k * math.tau / 5 + rnd.uniform(-0.15, 0.15)
            rk = rr * rnd.uniform(0.88, 1.12)
            rim.append((x + rk * math.cos(a), y + rk * math.sin(a), z - rr * rnd.uniform(0.05, 0.25)))
        mb = mbs[rnd.randrange(len(mbs))]
        for k in range(5):
            p0, p1 = rim[k], rim[(k + 1) % 5]
            mb.face([c, p0, p1], ((p0[0] + p1[0]) / 2 - x, (p0[1] + p1[1]) / 2 - y, rr))
    for mb, mt in zip(mbs, mts):
        mb.obj(mt, "clumps")


def lr_gambrel_barn(team, w=0.22, d=0.3, h=0.11):
    """A gambrel barn, gable ends to the front and back (the barns of frame 3, brought up to date): weathered timber
    board walls (not barn red: red is the enemy colour on the map, so only the roof and the star carry a colour),
    four roof slopes laid in team-slate courses, white fascia and corner trim, a cupola on the ridge, big X-braced
    doors and a hay loft door in the front gable under a team barn star, lit side windows."""
    from mathutils import Vector
    boards = lr_boards("barn", 0.017, "#9c6b45", "#83573a")
    white = flat("trim_w", "#f7f5ef", 0.6)
    roof_c = slate(team)
    k1 = 1.6
    xk = w * 0.3
    zk = h + (w / 2 - xk) * k1
    zr = zk + xk * 0.55
    oh = 0.022
    xe, ze = w / 2 + oh, h - oh * k1
    L = d / 2 + 0.018
    prof = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h), (xk, zk), (0.0, zr), (-xk, zk), (-w / 2, h)]
    extrude(prof, -d / 2, d / 2, boards, rot=(math.pi / 2, 0, 0))
    MBs, BUTT, slab = [_MB(), _MB()], _MB(), _MB()
    tk, ct = 0.007, 0.009
    for sx in (-1, 1):
        for (p, q, n_) in (((xe, ze), (xk, zk), 3), ((xk, zk), (0.0, zr), 2)):
            nv = Vector((sx * (q[1] - p[1]), 0, abs(p[0] - q[0]))).normalized()
            A = Vector((sx * p[0], -L, p[1])) + nv * tk
            B = Vector((sx * p[0], L, p[1])) + nv * tk
            C = Vector((sx * q[0], L, q[1])) + nv * tk
            D = Vector((sx * q[0], -L, q[1])) + nv * tk
            slab.face([A, B, C, D], nv)
            for yy, sg in ((-L, -1), (L, 1)):  # verge edges
                a0 = Vector((sx * p[0], yy, p[1]))
                b0 = Vector((sx * q[0], yy, q[1]))
                slab.face([a0, b0, b0 + nv * tk, a0 + nv * tk], (0, sg, 0))
            course_rows(MBs, tuple(A), tuple(B), tuple(C), tuple(D), n_, ct, butt=BUTT, band=0.8)
        a0 = Vector((sx * xe, -L, ze))
        slab.face([a0, Vector((sx * xe, L, ze)), Vector((sx * xe, L, ze)) + Vector((0, 0, tk + ct)),
                   a0 + Vector((0, 0, tk + ct))], (sx, 0, -0.3))
    slab.obj(tex("roof", shade(roof_c, 0.8), 1.6), "roof_slab")
    for mb, mt in zip(MBs, _roof_mats(roof_c, 0.84, "roof")):
        mb.obj(mt, "roof_courses")
    BUTT.obj(tex("roof", shade(roof_c, 0.68), 1.6), "roof_butts")
    lift = tk + ct + 0.004
    for yy in (-L - 0.004, L + 0.004):  # white fascia along both gables
        for sx in (-1, 1):
            beam((sx * xe, yy, ze + lift), (sx * xk, yy, zk + lift), 0.014, white)
            beam((sx * xk, yy, zk + lift), (0.0, yy, zr + lift), 0.014, white)
    beam((0, -L - 0.006, zr + lift), (0, L + 0.006, zr + lift), 0.016, flat("ridge#2c3036", "#2c3036", 0.8))
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.012, 0.012, h), (sx * w / 2, sy * d / 2, h / 2), white, bev=0)
    # the cupola on the ridge
    bx((0.044, 0.05, 0.036), (0, 0, zr + lift + 0.016), white, bev=0)
    bx((0.046, 0.052, 0.014), (0, 0, zr + lift + 0.02), flat("louvre", "#55595f", 0.7), bev=0)
    _hip_roof(0.044, 0.05, 0.03, (0, 0, zr + lift + 0.034), flat("cupola" + team, slate(team, 1.05), 0.6), 0.008)
    # the front gable: big X-braced doors, the hay loft door, the barn star in the team colour
    yf = -d / 2 - 0.003
    bx((0.11, 0.008, 0.094), (0, yf, 0.047), white, bev=0)
    bx((0.096, 0.01, 0.084), (0, yf - 0.001, 0.042), flat("barn_door", "#5c3f2b", 0.8), bev=0)
    for sx in (-1, 1):
        beam((sx * 0.044, yf - 0.007, 0.006), (0.0, yf - 0.007, 0.078), 0.008, white)
        beam((sx * 0.044, yf - 0.007, 0.078), (0.0, yf - 0.007, 0.006), 0.008, white)
    bx((0.004, 0.012, 0.084), (0, yf - 0.006, 0.042), white, bev=0)
    bx((0.05, 0.008, 0.046), (0, yf, h + 0.016), white, bev=0)
    bx((0.04, 0.01, 0.038), (0, yf - 0.001, h + 0.016), flat("loft", "#2b2420", 0.9), bev=0)
    bx((0.03, 0.008, 0.03), (0, yf - 0.002, zk + 0.004), flat("star" + team, team, 0.5), bev=0, rot=(0, math.pi / 4, 0))
    for sx in (-1, 1):
        for u in (-0.07, 0.07):
            lr_window(sx * (w / 2 + 0.003), u, 0.07, sx * math.pi / 2, w=0.03, h=0.03, lit=(u > 0) == (sx > 0),
                      frame="#f7f5ef")


def lr_silo(x, y, r, h, team, ladder_a=-2.2):
    """A grain silo: a concrete footing, corrugated steel rings, a band in the team colour, a pale domed cap with a
    vent and a dark ladder line down its side."""
    corr = lr_bands("silo", 2, 0.017, "#d6dadf", "#aeb5bd")
    cy(r + 0.012, 0.02, (x, y, 0.01), flat("conc", CONC, 0.8), 14)
    cy(r, h, (x, y, h / 2), corr, 14)
    cy(r + 0.004, 0.034, (x, y, h * 0.84), flat("band" + team, slate(team, 1.2), 0.5), 14)
    cy(r + 0.004, 0.01, (x, y, h * 0.4), flat("silo_ring", "#8d949c", 0.5), 14)
    hemi(r * 1.03, (x, y, h), flat("silo_cap", "#e8ebee", 0.4), 14, 3, (1, 1, 0.55))
    cy(0.014, 0.016, (x, y, h + r * 0.56 + 0.004), flat("silo_ring", "#8d949c", 0.5), 6)
    ca, sa = math.cos(ladder_a), math.sin(ladder_a)
    lad = _MB()
    lad.strip((x + ca * r, y + sa * r, 0.03), (x + ca * r, y + sa * r, h + 0.01), (ca, sa, 0), 0.014, 0.004)
    lad.obj(flat("ladder", "#3a3f46", 0.6), "ladder")


def lr_bin(x, y, r, h):
    """A hopper-bottom feed bin on four legs, with a cone roof."""
    leg = flat("silo_ring", "#8d949c", 0.5)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        beam((x + math.cos(a) * r * 0.8, y + math.sin(a) * r * 0.8, 0.0),
             (x + math.cos(a) * r * 0.7, y + math.sin(a) * r * 0.7, 0.07), 0.008, leg)
    cy(0.012, 0.04, (x, y, 0.05), leg, 10, r2=r)
    cy(r, h, (x, y, 0.07 + h / 2), lr_bands("silo", 2, 0.017, "#d6dadf", "#aeb5bd"), 10)
    cn(r * 1.05, 0.04, (x, y, 0.07 + h + 0.02), flat("silo_cap", "#e8ebee", 0.4), 10)


def lr_tractor(x, y, rz, plough=True, z=0.0, color="#e2782a"):
    """A tractor standing on z (the crop field's, larger; orange, so it never reads as a red-team unit): hood, cab
    with a white roof, big rear and small front wheels with yellow hubs, an exhaust stack, a disc plough on the
    hitch."""
    red = flat("tractor" + color, color, 0.5)
    dk = flat("tyre", "#1f1f21", 0.9)
    hub = flat("hub", "#f2c230", 0.6)

    def b():
        bx((0.07, 0.04, 0.034), (0.034, 0, 0.046), red, bev=0)
        bx((0.05, 0.052, 0.034), (-0.022, 0, 0.046), red, bev=0)
        bx((0.044, 0.046, 0.044), (-0.022, 0, 0.085), flat("cab", "#2c3a48", 0.3), bev=0)
        bx((0.054, 0.056, 0.006), (-0.022, 0, 0.11), flat("trim_w", "#f7f5ef", 0.6), bev=0)
        bx((0.012, 0.042, 0.016), (0.07, 0, 0.04), flat("grille", "#2b2d31", 0.6), bev=0)
        for sy in (-1, 1):
            cy(0.036, 0.018, (-0.026, sy * 0.037, 0.036), dk, 12, rot=(math.pi / 2, 0, 0))
            cy(0.016, 0.02, (-0.026, sy * 0.037, 0.036), hub, 8, rot=(math.pi / 2, 0, 0))
            cy(0.021, 0.014, (0.048, sy * 0.028, 0.021), dk, 10, rot=(math.pi / 2, 0, 0))
            cy(0.009, 0.016, (0.048, sy * 0.028, 0.021), hub, 6, rot=(math.pi / 2, 0, 0))
        cy(0.004, 0.044, (0.05, 0.012, 0.084), dk, 5)
        if plough:
            beam((-0.05, 0, 0.03), (-0.09, 0, 0.03), 0.01, red)
            beam((-0.09, -0.05, 0.03), (-0.13, 0.05, 0.03), 0.012, red)
            for k in range(4):
                f = (k + 0.5) / 4
                cy(0.016, 0.004, (-0.09 - 0.04 * f, -0.05 + 0.1 * f, 0.016), flat("disc", "#9aa1a8", 0.4), 8,
                   rot=(math.pi / 2, 0, 0.5))
    build_at(b, x, y, rz, z=z)


def lr_combine(team, x, y, rz, z=0.0):
    """A combine harvester in the team colour (frame 2's farm machinery): body and grain tank, a cab under a white
    roof, big drive wheels, the wide header with its reel out front, an unloading auger folded along the side."""
    body = flat("combine" + team, shade(team, 0.92), 0.5)
    light = flat("combine_l" + team, shade(team, 1.3), 0.5)
    dk = flat("tyre", "#1f1f21", 0.9)
    steel = flat("header", "#3d4148", 0.6)

    def b():
        bx((0.15, 0.078, 0.064), (-0.01, 0, 0.074), body, bev=0)
        bx((0.074, 0.072, 0.034), (-0.04, 0, 0.122), light, bev=0)
        bx((0.05, 0.058, 0.046), (0.045, 0, 0.128), flat("cab", "#2c3a48", 0.3), bev=0)
        bx((0.058, 0.066, 0.007), (0.045, 0, 0.154), flat("trim_w", "#f7f5ef", 0.6), bev=0)
        bx((0.05, 0.08, 0.006), (-0.03, 0, 0.042), flat("stripe_w", "#f7f5ef", 0.6), bev=0)
        for sy in (-1, 1):
            cy(0.042, 0.02, (0.03, sy * 0.044, 0.042), dk, 12, rot=(math.pi / 2, 0, 0))
            cy(0.018, 0.022, (0.03, sy * 0.044, 0.042), flat("hub", "#f2c230", 0.6), 8, rot=(math.pi / 2, 0, 0))
            cy(0.025, 0.014, (-0.07, sy * 0.036, 0.025), dk, 10, rot=(math.pi / 2, 0, 0))
        beam((0.06, 0, 0.05), (0.1, 0, 0.034), 0.04, body)  # feeder house
        bx((0.04, 0.22, 0.022), (0.118, 0, 0.022), steel, bev=0)  # the header
        bx((0.012, 0.226, 0.03), (0.098, 0, 0.034), body, bev=0)
        cy(0.02, 0.21, (0.124, 0, 0.056), light, 8, rot=(math.pi / 2, 0, 0))  # the reel
        for sy in (-1, 1):
            beam((0.09, sy * 0.106, 0.04), (0.124, sy * 0.106, 0.056), 0.008, body)
        rod((-0.06, 0.04, 0.13), (0.06, 0.05, 0.14), 0.007, light, n=6)  # unloading auger
        cy(0.004, 0.03, (-0.05, -0.02, 0.15), dk, 5)
    build_at(b, x, y, rz, z=z)


def lr_pickup(x, y, rz, color, z=0.0):
    """A farm pickup: body, cab with dark glass, an open bed, two axles."""
    def b():
        bc = flat("car" + color, color, 0.4)
        bx((0.11, 0.05, 0.022), (0, 0, 0.026), bc, bev=0)
        bx((0.044, 0.048, 0.026), (0.016, 0, 0.05), bc, bev=0)
        bx((0.046, 0.05, 0.014), (0.018, 0, 0.05), flat("car_glass", "#1d2a38", 0.2), bev=0)
        bx((0.046, 0.042, 0.004), (-0.03, 0, 0.038), flat("bed_d", "#2b2d31", 0.8), bev=0)
        for sy in (-1, 1):
            bx((0.05, 0.004, 0.01), (-0.03, sy * 0.023, 0.042), bc, bev=0)
        for sx in (-0.034, 0.034):
            cy(0.013, 0.054, (sx, 0, 0.013), flat("tyre", "#1f1f21", 0.9), 6, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz, z=z)


def lr_irrigation(x0, x1, y, z=0.1, towers=3, zg=0.0):
    """A linear irrigation line across a field whose soil stands zg high: a pale pipe on wheeled A-frame towers, a
    truss under each span and drop sprinklers (a long readable line over the crop rows)."""
    pipe = flat("irr_pipe", "#d0d5da", 0.4)
    leg = flat("irr_leg", "#8d949c", 0.5)
    dk = flat("tyre", "#1f1f21", 0.9)
    beam((x0, y, z), (x1, y, z), 0.011, pipe)
    for i in range(towers + 1):
        xt = x0 + (x1 - x0) * i / towers
        for sy in (-1, 1):
            beam((xt, y + sy * 0.032, zg + 0.016), (xt, y, z), 0.008, leg)
            cy(0.016, 0.01, (xt, y + sy * 0.034, zg + 0.016), dk, 8, rot=(math.pi / 2, 0, 0))
        bx((0.02, 0.016, 0.02), (xt, y, z - 0.012), leg, bev=0)
        if i < towers:
            xn = x0 + (x1 - x0) * (i + 1) / towers
            for f0, f1 in ((0.0, 0.5), (0.5, 1.0)):
                beam((xt + (xn - xt) * f0, y, z - (0.0 if f0 == 0.0 else 0.03)),
                     (xt + (xn - xt) * f1, y, z - (0.03 if f1 == 0.5 else 0.0)), 0.005, leg)
            for k in range(1, 4):
                xs = xt + (xn - xt) * k / 4
                beam((xs, y, z), (xs, y, z - 0.04), 0.004, leg)


def farm_modern(team):
    """DL6–7 farm (frame 2's fields with machinery, frame 3's patchwork round the farmyard): four fields round a
    dirt crossroads — ripe wheat half cut by a combine in the team colour with round bales on the stubble, leafy
    rows under a linear irrigation line, a ploughed field with an orange tractor and young rows; a farmyard with a
    gambrel barn under a team-slate roof, two corrugated silos with team bands joined by a grain leg, a feed bin,
    a pickup and shade trees."""
    rnd = random.Random(61)
    pad(0.7, tex("plaster", "#8c7352", 2.0), 0.008, 16, 0.03, 31)
    clip = ngon(0.655, 24, 0.13)
    soil = flat("soil", "#5a3d24", 0.95)
    R = 0.62  # the crops keep inside this circle (the plates run to 0.655)
    # A: wheat, front left — the back part standing, the front cut to stubble with bales, the combine eating into
    # the last two rows
    lr_field((-0.7, -0.7, -0.035, -0.05), 0.018, soil, clip)
    yc, xh = -0.4, -0.27  # the cut line, and the combine's header (the rows behind it are cut)
    stub = lr_bands("stubble", 1, 0.034, "#c99a3f", "#ad8131")
    lr_field((-0.7, -0.7, -0.035, yc), 0.021, stub, clip)
    lr_field((-0.7, yc, xh, -0.26), 0.021, stub, clip)  # (abuts the first stubble plate: no coplanar overlap)
    rows, ears = [], []
    for j in range(5):
        y = -0.095 - j * 0.066
        xa, xb = lr_span(y, -0.655 if j < 3 else xh, -0.07, R)
        rows.append((xa, y, xb, y))
        n = max(2, int((xb - xa) / 0.03))
        for i in range(n):
            for o in (-0.014, 0.014):
                ears.append((xa + (i + 0.5 + (0.5 if o > 0 else 0)) * (xb - xa) / (n + 0.5), y + o + rnd.uniform(-0.004, 0.004),
                             0.06 + rnd.uniform(-0.006, 0.006)))
    lr_ridges(rows, 0.06, 0.044, 0.042, 0.018, flat("wheat_body", "#c08a26", 0.8), "wheat")
    lr_ears(ears, [flat("ear_a", "#e9b83c", 0.8), flat("ear_b", "#f6d462", 0.8), flat("ear_c", "#d9a22e", 0.8)], rnd)
    lr_combine(team, xh - 0.13, -0.33, 0.0, z=0.02)  # (on the stubble)
    for (x, y, a) in ((-0.34, -0.49, 0.3), (-0.19, -0.53, 1.2), (-0.1, -0.44, -0.4)):
        if math.hypot(x, y) < R - 0.02:
            cy(0.034, 0.05, (x, y, 0.055), tex("wood", THATCH, 3.0), 10, rot=(math.pi / 2, 0, a))
    # B: leafy rows, front right, under the irrigation line
    lr_field((0.035, -0.7, 0.7, -0.05), 0.018, soil, clip)
    rows, pts = [], []
    for i in range(8):
        x = 0.085 + i * 0.07
        ya, yb = lr_span(x, -0.655, -0.095, R)
        if yb - ya < 0.06:
            continue
        rows.append((x, ya, x, yb))
        n = max(2, int((yb - ya) / 0.046))
        for k in range(n):
            pts.append((x + rnd.uniform(-0.004, 0.004), ya + (k + 0.5) * (yb - ya) / n, 0.046))
    lr_ridges(rows, 0.05, 0.03, 0.026, 0.018, flat("ridge_g", "#3d5a22", 0.9), "rows")
    lr_clumps(pts, [flat("leaf_a", "#3f7f2c", 0.85), flat("leaf_b", "#5f9e36", 0.85), flat("leaf_c", "#78b442", 0.85)], rnd)
    lr_irrigation(0.07, 0.56, -0.33, 0.105, 3, zg=0.018)
    # C: ploughed, back left, young rows at the back and the tractor at the headland
    lr_field((-0.7, 0.025, -0.035, 0.7), 0.02, lr_bands("furrow", 0, 0.028, "#5b3d22", "#80583a"), clip)
    rows = []
    for j in range(4):
        y = 0.43 + j * 0.05
        xa, xb = lr_span(y, -0.6, -0.08, R)
        rows.append((xa, y, xb, y))
    lr_ridges(rows, 0.03, 0.02, 0.014, 0.02, flat("young", "#5c9634", 0.85), "young")
    lr_tractor(-0.36, 0.3, math.pi, True, z=0.019)  # (on the ploughed field)
    # the farmyard, back right: gravel, the barn, two silos with the grain leg, a feed bin, a pickup, trees
    lr_field((0.035, 0.025, 0.7, 0.7), 0.014, tex("plaster", "#a69c88", 2.5), clip)
    build_at(lambda: lr_gambrel_barn(team), 0.44, 0.2, 0.0, z=0.012)  # (doors clear of the gravel)
    lr_silo(0.15, 0.47, 0.07, 0.44, team, ladder_a=-2.4)
    lr_silo(0.33, 0.47, 0.065, 0.38, team, ladder_a=-1.2)
    leg = flat("silo_ring", "#8d949c", 0.5)
    bx((0.024, 0.024, 0.55), (0.24, 0.56, 0.275), leg, bev=0)
    bx((0.04, 0.04, 0.03), (0.24, 0.56, 0.56), flat("silo_cap", "#e8ebee", 0.4), bev=0)
    rod((0.24, 0.56, 0.55), (0.15, 0.47, 0.49), 0.006, leg, n=5)
    rod((0.24, 0.56, 0.55), (0.33, 0.47, 0.42), 0.006, leg, n=5)
    lr_bin(0.11, 0.25, 0.04, 0.09)
    lr_pickup(0.22, 0.09, 0.3, shade(team, 0.85), z=0.014)  # (on the gravel)
    tree(0.6, 0.05, 0.85)
    tree(0.0, 0.56, 0.8)
    hay = tex("wood", THATCH, 3.0)
    for (x, y, z) in ((0.25, 0.28, 0.048), (0.25, 0.345, 0.048), (0.25, 0.3125, 0.102)):  # a stack of round bales
        cy(0.034, 0.05, (x, y, z), hay, 10, rot=(0, math.pi / 2, 0))


def lr_deck(r, mats, seed=0, n=24, z=0.016):
    """A round deck of dark steel slabs in three tones (the plazas of frame 5) with a pale kerb, and a light line
    in the team colour inset round its edge — the outline of a late-era compound at map distance."""
    st, plate, seam, panel, cap, neon, tip = mats
    outline = ngon(r, n, 0.13)
    tones = [_MB(), _MB(), _MB()]
    rnd = random.Random(90 + seed)
    t = 0.17
    for i in range(-5, 5):
        for j in range(-5, 5):
            cell = _clip_convex([(i * t, j * t), ((i + 1) * t, j * t), ((i + 1) * t, (j + 1) * t), (i * t, (j + 1) * t)],
                                outline)
            if len(cell) >= 3:
                tones[rnd.choice((0, 0, 1, 2))].face([(x, y, z) for x, y in cell], (0, 0, 1))
    for mb, c in zip(tones, ("#4d545e", "#565d68", "#454b54")):
        mb.obj(flat("ground8" + c, c, 0.6), "deck")
    side, ring = _MB(), _MB()
    for k in range(n):
        (x0, y0), (x1, y1) = outline[k], outline[(k + 1) % n]
        side.face([(x0, y0, -0.01), (x1, y1, -0.01), (x1, y1, z), (x0, y0, z)], (y1 - y0, -(x1 - x0), 0))
        f = (r - 0.03) / r
        ring.strip((x0 * f, y0 * f, z), (x1 * f, y1 * f, z), (0, 0, 1), 0.012, 0.0015)
    side.obj(seam, "kerb")
    ring.obj(neon, "edge_light")
    return outline


def lr_plot(x0, y0, x1, y1, mats, z=0.016):
    """A raised crop plot on the deck: a pale steel kerb, dark soil, a team light line along its front edge."""
    st, plate, seam, panel, cap, neon, tip = mats
    bx((x1 - x0 + 0.02, y1 - y0 + 0.02, 0.016), ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.008), seam, bev=0)
    bx((x1 - x0, y1 - y0, 0.004), ((x0 + x1) / 2, (y0 + y1) / 2, z + 0.017), flat("soil8", "#3a2b22", 0.95), bev=0)
    bx((x1 - x0 - 0.02, 0.008, 0.004), ((x0 + x1) / 2, y0 - 0.006, z + 0.017), neon, bev=0)
    return z + 0.019


def lr_ring(x, y, r, z, h, mt, n=12):
    """An open band round a drum (a light ring or a coloured band): n side quads, no caps (they would lie inside the
    drum, unseen)."""
    mb = _MB()
    for k in range(n):
        a0, a1 = math.tau * k / n, math.tau * (k + 1) / n
        am = (a0 + a1) / 2
        p0 = (x + r * math.cos(a0), y + r * math.sin(a0))
        p1 = (x + r * math.cos(a1), y + r * math.sin(a1))
        mb.face([(p0[0], p0[1], z - h / 2), (p1[0], p1[1], z - h / 2), (p1[0], p1[1], z + h / 2),
                 (p0[0], p0[1], z + h / 2)], (math.cos(am), math.sin(am), 0))
    return mb.obj(mt, "ring")


def lr_glass_dome(x, y, r, mats, team, glass, drum=0.035):
    """A greenhouse dome (frame 2's ribbed domes): a steel drum with a team band and a light ring, a door, the
    glass dome (glowing with the beds inside) under pale ribs, a plate oculus with a lit lantern and a needle."""
    st, plate, seam, panel, cap, neon, tip = mats
    n = 12
    cy(r + 0.02, 0.02, (x, y, 0.026), plate, n)
    cy(r, drum, (x, y, 0.016 + drum / 2), flat("hab_steel", "#626a74", 0.5), n)
    lr_ring(x, y, r + 0.004, 0.016 + drum * 0.42, drum * 0.42, flat("hab_team" + team, shade(team, 0.78), 0.5), n)
    lr_ring(x, y, r + 0.006, 0.016 + drum * 0.75, 0.006, neon, n)
    z0 = 0.016 + drum
    cy(r + 0.01, 0.01, (x, y, z0 + 0.005), plate, n)
    C = r * 0.78
    hemi(r, (x, y, z0 + 0.008), glass, 16, 4, (1, 1, 0.78))
    lr_dome_ribs(x, y, z0 + 0.008, r, C, seam, n=8, phis=(0.0, 0.32, 0.64, 0.95, 1.22, 1.42), ring=0.5,
                 t=max(0.009, r * 0.06))
    zt = z0 + 0.008 + C
    cy(r * 0.2, 0.014, (x, y, zt + 0.002), plate, 8)
    cy(r * 0.14, 0.012, (x, y, zt + 0.012), tip, 8)
    rod((x, y, zt + 0.016), (x, y, min(zt + 0.06, 0.25)), 0.005, cap, r2=0.0015, n=4)
    build_at(lambda: d8_portal(0, 0, 0, mats), x, y - r - 0.01, 0.0, s=0.5, z=0.016)


def lr_silo8(x, y, r, h, team, mats):
    """A late-era silo tower: pale steel rings on a plinth, a team band, cold light rings, a dark cone cap with a
    lit tip."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r + 0.018, 0.02, (x, y, 0.026), plate, 10)
    cy(r, h, (x, y, 0.016 + h / 2), lr_bands("silo8", 2, 0.02, "#b9c0c8", "#9aa2ac"), 10)
    lr_ring(x, y, r + 0.003, 0.016 + h * 0.56, 0.04, flat("hab_team" + team, shade(team, 0.78), 0.5), 10)
    for zf in (0.3, 0.82):
        lr_ring(x, y, r + 0.005, 0.016 + h * zf, 0.01, neon, 10)
    cn(r * 1.08, 0.05, (x, y, 0.016 + h + 0.025), cap, 10)
    bx((0.012, 0.012, 0.012), (x, y, 0.016 + h + 0.054), tip, bev=0)


def lr_harvester(x, y, rz, team, mats, z=0.0):
    """A robotic harvester (frame 2's farm machinery, late era) standing on z: a steel body on dark tracks with a
    team top, cold light strips along its flanks and across its back, a sensor dome, a wide header with a cutter
    drum and a cold light bar along its top edge, a grain hopper."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        trk = flat("track8", "#22262c", 0.8)
        for sy in (-1, 1):
            bx((0.13, 0.024, 0.03), (0, sy * 0.042, 0.015), trk, bev=0)
            for u in (-0.045, 0.0, 0.045):  # road wheels showing on the track flanks
                cy(0.011, 0.004, (u, sy * 0.0545, 0.015), seam, 6, rot=(math.pi / 2, 0, 0))
        bx((0.12, 0.07, 0.04), (0, 0, 0.045), seam, bev=0)
        bx((0.1, 0.06, 0.008), (-0.006, 0, 0.068), flat("hullteam" + team, team, 0.5), bev=0)
        bx((0.05, 0.05, 0.03), (-0.035, 0, 0.085), plate, bev=0)
        hemi(0.018, (0.03, 0, 0.068), flat("cab8", "#1b2533", 0.3), 8, 2)
        bx((0.012, 0.004, 0.008), (0.06, 0.0, 0.055), tip, bev=0)
        for sy in (-1, 1):  # cold light strips along the flanks
            bx((0.1, 0.004, 0.006), (0, sy * 0.0355, 0.052), neon, bev=0)
        bx((0.004, 0.05, 0.008), (-0.0615, 0, 0.052), neon, bev=0)  # and across the back
        beam((0.05, 0, 0.035), (0.09, 0, 0.021), 0.03, plate)
        bx((0.03, 0.18, 0.02), (0.1, 0, 0.015), plate, bev=0)
        cy(0.016, 0.17, (0.112, 0, 0.029), seam, 8, rot=(math.pi / 2, 0, 0))
        bx((0.008, 0.18, 0.005), (0.089, 0, 0.0265), neon, bev=0)  # the light bar on the header's near edge
        for sy in (-1, 1):
            bx((0.034, 0.006, 0.03), (0.104, sy * 0.093, 0.02), plate, bev=0)  # header side plates
    build_at(b, x, y, rz, z=z)


def farm_scifi(team):
    """DL8 farm (frame 2: crop plots with machinery, ribbed greenhouse domes, silos): a round steel deck with a team
    light line round its edge; two greenhouse domes glowing with the beds inside, on team-banded drums; three silo
    towers with cold light rings piped to a vaulted processing hangar; in front, three plots — leafy rows between
    cold-lit channels with a crop drone over them, golden grain with a robotic harvester at work, and glowing
    hydroponic troughs — and water tanks."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    rnd = random.Random(71)
    lr_deck(0.7, mats, 3)
    glass = glow("hydro_dome", "#79f2b0", 0.8)
    lr_glass_dome(-0.3, 0.3, 0.19, mats, team, glass)
    lr_glass_dome(0.06, 0.4, 0.13, mats, team, glass)
    for (x, y) in ((0.3, 0.47), (0.42, 0.36), (0.52, 0.23)):
        lr_silo8(x, y, 0.052, 0.17, team, mats)
    d8_hangar(0.3, 0.08, 0.2, 0.12, 0.075, mats, 0.25)
    pipe = flat("pipe8", "#6b737e", 0.4)
    for (x, y) in ((0.3, 0.47), (0.42, 0.36), (0.52, 0.23)):
        rod((x, y, 0.11), (0.36, 0.14, 0.07), 0.009, pipe, n=6)
    d8_tank(-0.02, 0.17, 0.045, 0.1, mats)
    d8_tank(0.07, 0.2, 0.035, 0.08, mats)
    rod((-0.02, 0.17, 0.06), (-0.14, 0.24, 0.06), 0.008, pipe, n=6)
    # the three plots in front (inside the deck's circle)
    zs = lr_plot(-0.5, -0.42, -0.19, -0.06, mats)  # leafy rows between cold-lit channels
    pts = []
    for i in range(5):
        x = -0.47 + i * 0.062
        if i < 4:
            bx((0.006, 0.34, 0.003), (x + 0.031, -0.24, zs + 0.001), tip, bev=0)
        for k in range(7):
            pts.append((x, -0.395 + k * 0.051, zs + 0.012))
    lr_clumps(pts, [flat("leaf_a", "#3f7f2c", 0.85), flat("leaf_b", "#5f9e36", 0.85), flat("leaf8", "#2f6a2a", 0.85)], rnd)
    lr_drone(-0.33, -0.2, 0.19, team, mats, 0.4, 1.2)
    zs = lr_plot(-0.15, -0.6, 0.15, -0.06, mats)  # golden grain with the harvester
    rows, ears = [], []
    for i in range(4):
        x = -0.11 + i * 0.073
        yb = -0.09
        ya = -0.36 if i < 2 else -0.57
        rows.append((x, ya, x, yb))
        n = int((yb - ya) / 0.036)
        for k in range(n):
            for o in (-0.013, 0.013):
                ears.append((x + o, ya + (k + 0.5 + (0.5 if o > 0 else 0)) * (yb - ya) / (n + 0.5), zs + 0.04))
    lr_ridges(rows, 0.056, 0.042, 0.036, zs, flat("wheat_body", "#c08a26", 0.8), "grain")
    lr_ears(ears, [flat("ear_a", "#e9b83c", 0.8), flat("ear_b", "#f6d462", 0.8), flat("ear_c", "#d9a22e", 0.8)], rnd,
            r=(0.013, 0.017), top=0.026)
    lr_harvester(-0.075, -0.44, math.pi / 2, team, mats, z=zs - 0.001)  # (on the soil, not sunk in the plot)
    zs = lr_plot(0.19, -0.42, 0.5, -0.06, mats)  # hydroponic troughs
    hydro = glow("hydro", "#5cff8a", 1.2)
    pts = []
    for j in range(4):
        y = -0.37 + j * 0.09
        bx((0.28, 0.04, 0.03), (0.345, y, zs + 0.015), plate, bev=0)
        bx((0.26, 0.024, 0.004), (0.345, y, zs + 0.031), hydro, bev=0)
        for k in range(8):
            pts.append((0.228 + k * 0.0335, y, zs + 0.036))
    lr_clumps(pts, [flat("leaf_b", "#5f9e36", 0.85), flat("leaf_c", "#78b442", 0.85)], rnd, r=(0.013, 0.016))
    for (x, y) in ((-0.17, -0.02), (0.17, -0.02), (-0.6, 0.05), (0.6, -0.02)):
        lr_mast(x, y, 0.12, mats, 0.012)  # (on the deck, which stands 0.016 high)


def lr_slab(p0, p1, w, t, mt):
    """A sloping slab (a ramp) of width w and thickness t whose top surface runs along the centre line p0 -> p1."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    sx, sy = -dy / L * w / 2, dx / L * w / 2
    top = [(p0[0] - sx, p0[1] - sy, p0[2]), (p1[0] - sx, p1[1] - sy, p1[2]), (p1[0] + sx, p1[1] + sy, p1[2]),
           (p0[0] + sx, p0[1] + sy, p0[2])]
    verts = top + [(x, y, z - t) for (x, y, z) in top]
    faces = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return mesh_obj(verts, faces, mt)


def lr_crystals(items, mts):
    """Raivite crystals: a six-sided prism with a pointed tip for each (x, y, z, r, h, tilt_x, tilt_y), open at the
    foot (it stands in rock or in another crystal), one mesh per glow material (cycled)."""
    from mathutils import Euler, Vector
    mbs = [_MB() for _ in mts]
    for i, (x, y, z, r, h, tx, ty) in enumerate(items):
        M = Euler((tx, ty, 0.0)).to_matrix()
        base = Vector((x, y, z))
        hp = h * 0.72
        ring0 = [M @ Vector((r * math.cos(k * math.tau / 6), r * math.sin(k * math.tau / 6), 0.0)) + base for k in range(6)]
        ring1 = [M @ Vector((r * math.cos(k * math.tau / 6), r * math.sin(k * math.tau / 6), hp)) + base for k in range(6)]
        apex = M @ Vector((0, 0, h)) + base
        mb = mbs[i % len(mbs)]
        for k in range(6):
            k1 = (k + 1) % 6
            n = M @ Vector((math.cos((k + 0.5) * math.tau / 6), math.sin((k + 0.5) * math.tau / 6), 0.0))
            mb.face([ring0[k], ring0[k1], ring1[k1], ring1[k]], tuple(n))
            mb.face([ring1[k], ring1[k1], apex], tuple(n + M @ Vector((0, 0, 0.6))))
    for mb, mt in zip(mbs, mts):
        mb.obj(mt, "crystals")


def lr_terraces(x, y, levels, mt_top, mt_wall, floor_mt, n=20):
    """A pit cut in terraces (reference frame 3's quarry, late era): levels = [(r_outer, z_top), ...] from the rim
    inwards; each terrace is a flat ring with a wall dropping to the next one; the rim also has its outer wall; the
    floor is a disc at the last level's height."""
    top, wall = _MB(), _MB()
    pts = lambda R, z: [(x + R * math.cos(math.tau * k / n), y + R * math.sin(math.tau * k / n), z) for k in range(n)]  # noqa: E731
    for i, (R, z) in enumerate(levels[:-1]):
        r_in, z_in = levels[i + 1]
        o, ii = pts(R, z), pts(r_in, z)
        lo = pts(r_in, z_in)
        for k in range(n):
            k1 = (k + 1) % n
            top.face([o[k], o[k1], ii[k1], ii[k]], (0, 0, 1))
            am = math.tau * (k + 0.5) / n
            wall.face([ii[k], ii[k1], lo[k1], lo[k]], (-math.cos(am), -math.sin(am), 0))
        if i == 0:
            g = pts(R, -0.005)
            for k in range(n):
                k1 = (k + 1) % n
                am = math.tau * (k + 0.5) / n
                wall.face([g[k], g[k1], o[k1], o[k]], (math.cos(am), math.sin(am), 0))
    top.obj(mt_top, "terraces")
    wall.obj(mt_wall, "terrace_walls")
    R, z = levels[-1]
    fl = _MB()
    fl.face(pts(R, z), (0, 0, 1))
    fl.obj(floor_mt, "pit_floor")


def lr_hauler(x, y, rz, team, mats, load):
    """A mining hauler (frame 2's heavy machinery): a steel chassis on six big wheels, a cab in the team colour with a
    dark windscreen and a cold lamp bar, a dump bed heaped with glowing raivite, a hazard-striped bumper."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        dk = flat("tyre", "#1f1f21", 0.9)
        bx((0.17, 0.07, 0.024), (0, 0, 0.044), plate, bev=0)
        for u in (-0.06, -0.02, 0.055):
            for sy in (-1, 1):
                cy(0.026, 0.02, (u, sy * 0.042, 0.026), dk, 10, rot=(math.pi / 2, 0, 0))
                cy(0.011, 0.022, (u, sy * 0.042, 0.026), seam, 6, rot=(math.pi / 2, 0, 0))
        bx((0.05, 0.072, 0.05), (0.06, 0, 0.081), flat("hullteam" + team, shade(team, 0.85), 0.5), bev=0)
        bx((0.006, 0.06, 0.022), (0.086, 0, 0.09), flat("cab8", "#1b2533", 0.3), bev=0)
        bx((0.006, 0.05, 0.006), (0.088, 0, 0.11), tip, bev=0)
        bx((0.01, 0.08, 0.016), (0.09, 0, 0.044), hazard(0.022), bev=0)
        taper_box((0.11, 0.08, 0.05), (-0.03, 0, 0.081), seam, top=(1.08, 1.06))
        bx((0.1, 0.07, 0.004), (-0.03, 0, 0.104), flat("bed_d", "#2b2d31", 0.8), bev=0)
    build_at(b, x, y, rz)
    rnd = random.Random(5)
    c, s_ = math.cos(rz), math.sin(rz)
    items = []
    for k in range(6):
        u, v = -0.065 + (k % 3) * 0.033, -0.017 + (k // 3) * 0.034
        items.append((x + u * c - v * s_, y + u * s_ + v * c, 0.1, 0.012, rnd.uniform(0.03, 0.045),
                      rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5)))
    lr_crystals(items, load)


def lr_conveyor(p0, p1, w, mats, load, legs=2):
    """An inclined ore conveyor from p0 up to p1 (x, y, z): a dark belt between steel side rails on A-frame legs,
    glowing raivite chunks riding on it."""
    st, plate, seam, panel, cap, neon, tip = mats
    from mathutils import Vector
    a, b = Vector(p0), Vector(p1)
    beam(tuple(a), tuple(b), w, flat("belt", "#24272c", 0.8))
    d = (b - a)
    side = Vector((-d.y, d.x, 0)).normalized() * (w / 2 + 0.004)
    for sg in (-1, 1):
        beam(tuple(a + side * sg + Vector((0, 0, 0.01))), tuple(b + side * sg + Vector((0, 0, 0.01))), 0.008, seam)
    for k in range(legs):
        f = (k + 1) / (legs + 1)
        q = a.lerp(b, f)
        for sg in (-1, 1):
            beam(tuple(q + side * sg * 1.6 + Vector((0, 0, -q.z + 0.016))), tuple(q + side * sg), 0.008, plate)
    rnd = random.Random(3)
    items = []
    for k in range(5):
        q = a.lerp(b, 0.12 + k * 0.18)
        items.append((q.x, q.y, q.z + 0.008, 0.012, rnd.uniform(0.024, 0.032), rnd.uniform(-0.6, 0.6),
                      rnd.uniform(-0.6, 0.6)))
    lr_crystals(items, load)


def mine_scifi(team):
    """DL8 mine (frame 2's crystal extraction with glowing parts, frame 3's terraced quarry): on a round steel deck
    with a team light line, a pit cut in three rock terraces with a ramp down to its floor; clusters of cyan raivite
    crystals on the floor and the terraces; over them a steel lattice drill derrick with a glowing core column, a
    drill head with a team band and a crown block with a lit needle; an ore conveyor carrying crystals up to a
    steel processing plant (team panels, light strips, a hopper, vent stacks); a hauler heaped with crystals; crates
    of crystals, tanks and light masts."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    cr = glow("crystal", "#18b4ff", 1.9)
    cr2 = glow("crystal2", "#6fe2ff", 2.3)
    lr_deck(0.7, mats, 5)
    px, py = -0.1, 0.06
    lr_terraces(px, py, [(0.36, 0.08), (0.3, 0.056), (0.23, 0.034), (0.15, 0.018)],
                tex("plaster", "#9a95a0", 2.4), lr_bands("strata", 2, 0.011, "#6a6472", "#544f5c"),
                flat("pit_floor", "#2c2933", 0.9))
    rock = tex("plaster", "#79747f", 3.0)
    rnd = random.Random(17)
    for k in range(9):  # boulders on the rim and the terraces break the clean rings
        a = k * math.tau / 9 + 0.3
        R, z = ((0.33, 0.08), (0.27, 0.056))[k % 2]
        if abs(a - (math.pi * 1.5)) < 0.35:
            continue  # (not on the ramp)
        ico(rnd.uniform(0.016, 0.024), (px + math.cos(a) * R, py + math.sin(a) * R, z + 0.006), rock,
            (1.2, 1.0, 0.7), sub=1)
    # the ramp: up the rim from the deck at the front, then down the terraces to the floor
    ramp = flat("path8", "#2f343b", 0.7)
    ax, ay = px - 0.03, py - 0.5
    rx, ry = px - 0.03, py - 0.33
    fx, fy = px - 0.03, py - 0.12
    for (p, q) in (((ax, ay, 0.016), (rx, ry, 0.088)), ((rx, ry, 0.088), (fx, fy, 0.022))):  # (top surface heights)
        lr_slab(p, q, 0.06, 0.02, ramp)
        for sg in (-1, 1):
            beam((p[0] + sg * 0.026, p[1], p[2] + 0.003), (q[0] + sg * 0.026, q[1], q[2] + 0.003), 0.006, neon)
    # crystals: a big cluster on the floor round the derrick, smaller ones on the terraces
    rnd = random.Random(11)
    items = []
    # (a tilt of (-sin a, cos a) * t leans a crystal at angle a outwards, away from the core)
    for k in range(4):  # the big cluster on the floor: tall prisms splaying out round the core between the legs
        a = k * math.pi / 2 + rnd.uniform(-0.2, 0.2)
        rr = rnd.uniform(0.04, 0.055)
        t_ = rnd.uniform(0.22, 0.32)
        items.append((px + math.cos(a) * rr, py + math.sin(a) * rr, 0.012, rnd.uniform(0.042, 0.048),
                      rnd.uniform(0.26, 0.3), -math.sin(a) * t_, math.cos(a) * t_))
    for k in range(4):  # shorter ones under the legs
        a = math.pi / 4 + k * math.pi / 2 + rnd.uniform(-0.15, 0.15)
        rr = rnd.uniform(0.065, 0.075)
        t_ = rnd.uniform(0.25, 0.35)
        items.append((px + math.cos(a) * rr, py + math.sin(a) * rr, 0.012, rnd.uniform(0.03, 0.036),
                      rnd.uniform(0.13, 0.16), -math.sin(a) * t_, math.cos(a) * t_))
    for k in range(4):  # and small ones splaying out at the foot of the floor wall
        a = k * math.pi / 2 + 0.45 + rnd.uniform(-0.15, 0.15)
        t_ = rnd.uniform(0.5, 0.7)
        items.append((px + math.cos(a) * 0.12, py + math.sin(a) * 0.12, 0.014, rnd.uniform(0.018, 0.022),
                      rnd.uniform(0.07, 0.1), -math.sin(a) * t_, math.cos(a) * t_))
    for (a, R, z) in ((0.5, 0.265, 0.052), (2.3, 0.265, 0.052), (3.4, 0.19, 0.03), (5.6, 0.19, 0.03), (3.9, 0.33, 0.077),
                      (1.4, 0.33, 0.077), (0.0, 0.33, 0.077)):
        for j in range(3):
            b = a + (j - 1) * 0.13
            out = (math.sin(b) * 0.3, -math.cos(b) * 0.3)
            items.append((px + math.cos(b) * R, py + math.sin(b) * R, z, 0.016 + 0.005 * (j == 1),
                          0.07 + 0.05 * (j == 1), out[0] + rnd.uniform(-0.2, 0.2), out[1] + rnd.uniform(-0.2, 0.2)))
    lr_crystals(items, [cr, cr2])
    # the drill derrick over the pit: four lattice legs from the second terrace to a crown block
    legs = []
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        legs.append(((px + math.cos(a) * 0.2, py + math.sin(a) * 0.2, 0.034),
                     (px + math.cos(a) * 0.045, py + math.sin(a) * 0.045, 0.4)))
    for (p, q) in legs:
        beam(p, q, 0.024, plate)
    rim = _MB()  # a light line round the rim of the pit
    for k in range(24):
        a0, a1 = math.tau * k / 24, math.tau * (k + 1) / 24
        rim.strip((px + 0.345 * math.cos(a0), py + 0.345 * math.sin(a0), 0.08),
                  (px + 0.345 * math.cos(a1), py + 0.345 * math.sin(a1), 0.08), (0, 0, 1), 0.01, 0.0015)
    rim.obj(neon, "rim_light")
    for f in (0.42, 0.72):
        pts = [tuple(p[i] + (q[i] - p[i]) * f for i in range(3)) for p, q in legs]
        for k in range(4):
            beam(pts[k], pts[(k + 1) % 4], 0.01, seam)
    core = glow("core", "#7ff0ff", 3.0)
    cy(0.028, 0.34, (px, py, 0.19), core, 8)
    cy(0.042, 0.05, (px, py, 0.3), plate, 10)
    lr_ring(px, py, 0.045, 0.3, 0.026, flat("hab_team" + team, shade(team, 0.78), 0.5), 10)
    lr_ring(px, py, 0.046, 0.33, 0.006, neon, 10)
    bx((0.13, 0.13, 0.056), (px, py, 0.425), st, bev=0)
    bx((0.142, 0.142, 0.012), (px, py, 0.458), plate, bev=0)
    for (nx, ny) in ((0, -1), (1, 0), (-1, 0), (0, 1)):
        bx((0.08 if ny else 0.006, 0.006 if ny else 0.08, 0.036), (px + nx * 0.067, py + ny * 0.067, 0.423),
           flat("hab_team" + team, shade(team, 0.78), 0.5), bev=0)
        bx((0.06 if ny else 0.008, 0.008 if ny else 0.06, 0.007), (px + nx * 0.07, py + ny * 0.07, 0.423), neon, bev=0)
    rod((px, py, 0.46), (px, py, 0.53), 0.006, cap, r2=0.0015, n=4)
    bx((0.016, 0.016, 0.016), (px, py, 0.5), tip, bev=0)
    # the processing plant at the back right, fed by the conveyor
    gx, gy = 0.42, 0.28
    bx((0.2, 0.15, 0.16), (gx, gy, 0.096), steel_facade(), bev=0)
    bx((0.214, 0.164, 0.014), (gx, gy, 0.183), plate, bev=0)
    bx((0.22, 0.17, 0.02), (gx, gy, 0.026), plate, bev=0)
    pm, sm_ = _MB(), _MB()
    for (nx, ny, L, off) in ((0, -1, 0.2, 0.075), (-1, 0, 0.15, 0.1)):
        qx, qy = gx + nx * (off + 0.003), gy + ny * (off + 0.003)
        tx, ty = -ny * L * 0.22, nx * L * 0.22
        pm.face([(qx - tx, qy - ty, 0.05), (qx + tx, qy + ty, 0.05), (qx + tx, qy + ty, 0.165), (qx - tx, qy - ty, 0.165)],
                (nx, ny, 0))
        qx, qy = gx + nx * (off + 0.005), gy + ny * (off + 0.005)
        ux, uy = -ny * 0.008, nx * 0.008
        sm_.face([(qx - ux, qy - uy, 0.06), (qx + ux, qy + uy, 0.06), (qx + ux, qy + uy, 0.155), (qx - ux, qy - uy, 0.155)],
                 (nx, ny, 0))
    pm.obj(flat("hab_team" + team, shade(team, 0.78), 0.5), "panels")
    sm_.obj(neon, "strips")
    cy(0.05, 0.03, (gx - 0.04, gy - 0.01, 0.205), plate, 10, r2=0.02)  # the hopper on the roof
    cy(0.052, 0.012, (gx - 0.04, gy - 0.01, 0.222), seam, 10)
    for (vx, vy) in ((gx + 0.06, gy + 0.04), (gx + 0.06, gy - 0.03)):
        cy(0.016, 0.08, (vx, vy, 0.23), seam, 8)
        lr_ring(vx, vy, 0.018, 0.25, 0.008, tip, 8)
    bx((0.06, 0.006, 0.05), (gx + 0.05, gy - 0.078, 0.045), flat("door8", "#23282f", 0.6), bev=0)
    bx((0.064, 0.008, 0.008), (gx + 0.05, gy - 0.08, 0.074), neon, bev=0)
    lr_conveyor((px + 0.2, py - 0.04, 0.09), (gx - 0.06, gy - 0.02, 0.215), 0.04, mats, [cr, cr2])
    # the hauler on the deck by the ramp, crates of crystals, tanks, light masts
    lr_hauler(-0.36, -0.42, 0.5, team, mats, [cr, cr2])
    for (x, y, rz) in ((0.3, -0.12, 0.2), (0.38, -0.06, 0.2), (0.33, -0.08, 0.2)):
        z0 = 0.016 if (x, y) != (0.33, -0.08) else 0.066
        bx((0.06, 0.06, 0.05), (x, y, z0 + 0.025), plate, rz, bev=0)
        bx((0.05, 0.05, 0.004), (x, y, z0 + 0.051), cr, rz, bev=0)
    d8_tank(-0.47, 0.32, 0.05, 0.13, mats)
    d8_tank(-0.38, 0.43, 0.04, 0.1, mats)
    for (x, y) in ((0.1, -0.4), (-0.56, -0.1), (0.58, 0.02), (0.15, 0.52)):
        lr_mast(x, y, 0.13, mats, 0.012)


# ------------------------------------------------------------------ DL8 DISTRICTS (the built-up land of frame 2)


def d8_mats(team):
    """The citadel's steel kit (residence_dl8 / city_dl8): (steel, plate, seam, panel, cap, neon, cyan). The team
    panels are a step brighter than the citadel's, so a small district tower still shows its colour at map distance."""
    return (steel_facade(), flat("plate8", "#505760", 0.45), flat("seam8", "#8c939c", 0.45),
            flat("panel8d" + team, shade(team, 0.5), 0.4), flat("spire8", "#4c535d", 0.35),
            glow("strip" + team, shade(team, 1.25), 2.0), glow("cyan", CYAN, 2.5))


def d8_plate_pts(r=0.86, lim=0.82):
    """The outline of a district plate: a flat-top hexagon of circumradius r (lined up with the hex: the game turns a
    district by 60° steps, so it always fills its hex like the built-up land of frame 2) with the corners cut at lim."""
    a = r * math.sqrt(3) / 2
    t = math.sqrt(max(lim * lim - a * a, 0.0))
    pts = []
    for k in range(6):
        m = math.pi / 6 + k * math.pi / 3  # edge midpoint
        cx, cy_ = a * math.cos(m), a * math.sin(m)
        ex, ey = -math.sin(m), math.cos(m)
        pts += [(cx - ex * t, cy_ - ey * t), (cx + ex * t, cy_ + ey * t)]
    return pts


def _clip_convex(poly, clip):
    """Sutherland–Hodgman: the 2D polygon poly clipped by the convex counter-clockwise polygon clip."""
    out = list(poly)
    for i in range(len(clip)):
        (ax, ay), (bx_, by_) = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []
        if not inp:
            break

        def inside(p):
            return (bx_ - ax) * (p[1] - ay) - (by_ - ay) * (p[0] - ax) >= 0

        def cut(p, q):
            den = (p[0] - q[0]) * (ay - by_) - (p[1] - q[1]) * (ax - bx_)
            t = ((p[0] - ax) * (ay - by_) - (p[1] - ay) * (ax - bx_)) / den
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            if inside(q):
                if not inside(p):
                    out.append(cut(p, q))
                out.append(q)
            elif inside(p):
                out.append(cut(p, q))
    return out


def d8_plate(mats, seed=0):
    """Dark steel paving in large slabs of three tones (the plaza of frame 5) with a pale kerb round its edge (the
    plate's sides), so the block reads as built-up land. The slabs are the plate's top itself: nothing to z-fight."""
    st, plate, seam, panel, cap, neon, tip = mats
    pts = d8_plate_pts()
    tones = [_MB(), _MB(), _MB()]
    rnd = random.Random(80 + seed)
    t = 0.164
    for i in range(-5, 5):
        for j in range(-5, 5):
            cell = _clip_convex([(i * t, j * t), ((i + 1) * t, j * t), ((i + 1) * t, (j + 1) * t), (i * t, (j + 1) * t)],
                                pts)
            if len(cell) >= 3:
                tones[rnd.choice((0, 0, 1, 2))].face([(x, y, 0.02) for x, y in cell], (0, 0, 1))
    for mb, c in zip(tones, ("#4d545e", "#565d68", "#454b54")):
        mb.obj(flat("ground8" + c, c, 0.6), "plate")
    side = _MB()
    n = len(pts)
    for k in range(n):
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % n]
        nx, ny = (y1 - y0), -(x1 - x0)
        side.face([(x0, y0, -0.01), (x1, y1, -0.01), (x1, y1, 0.02), (x0, y0, 0.02)], (nx, ny, 0))
    side.obj(seam, "kerb")


def d8_road(p0, p1, w, mats, z=0.022):
    """A dark avenue with a cold light line along each edge (the glowing streets between the blocks of frame 2)."""
    st, plate, seam, panel, cap, neon, tip = mats
    (x0, y0), (x1, y1) = p0, p1
    ln = math.hypot(x1 - x0, y1 - y0)
    a = math.atan2(y1 - y0, x1 - x0)
    bx((ln, w, 0.004), ((x0 + x1) / 2, (y0 + y1) / 2, z), flat("road8", "#2a2e34", 0.6), a, bev=0)
    ox, oy = -math.sin(a) * w / 2, math.cos(a) * w / 2
    for s_ in (-1, 1):
        beam((x0 + s_ * ox, y0 + s_ * oy, z + 0.002), (x1 + s_ * ox, y1 + s_ * oy, z + 0.002), 0.012, neon)


def d8_lawn(x, y, w, d, mats, rz=0.0, trees=()):
    """A raised lawn in a pale kerb with a few pines (frame 2: trees between the towers)."""
    st, plate, seam, panel, cap, neon, tip = mats
    bx((w + 0.016, d + 0.016, 0.01), (x, y, 0.024), seam, rz, bev=0)
    bx((w, d, 0.01), (x, y, 0.027), flat("lawn8", "#3b7432", 0.8), rz, bev=0)
    c, s_ = math.cos(rz), math.sin(rz)
    for (u, v, sc_) in trees:
        pine(x + u * c - v * s_, y + u * s_ + v * c, sc_)


def d8_tower(x, y, w, d, h, mats, top="spire", rings=(), buttress=True, needle=0.05, seam_z=0.3, foot=True, sp=1.6):
    """A district tower in the citadel kit (frames 2 and 5): a plinth, a steel shaft with window slits, a pale plate
    seam, corner buttresses, neon rings, an inset team panel with a cold light strip on every face (a district is
    seen from any side), a setback crown with a light line, and a top: a dark four-sided spire, a lit beacon roof, a
    small glass dome or a flat roof with plant — each with a needle and a lit tip. Returns the height of the top."""
    st, plate, seam, panel, cap, neon, tip = mats
    if foot:  # (not on a podium)
        bx((w + 0.03, d + 0.03, 0.03), (x, y, 0.035), plate, bev=0)
    bx((w, d, h), (x, y, h / 2), st, bev=0)
    bx((w + 0.012, d + 0.012, 0.018), (x, y, h * seam_z), seam, bev=0)
    if buttress:
        bh = h * 0.95 - 0.05
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((0.018, 0.018, bh), (x + sx * w / 2, y + sy * d / 2, 0.05 + bh / 2), plate, bev=0)
    for zf in rings:
        bx((w + 0.016, d + 0.016, 0.012), (x, y, h * zf), neon, bev=0)
    pm, sm = _MB(), _MB()
    z0, z1 = h * seam_z + 0.014, h * 0.93
    for (nx, ny) in ((0, -1), (1, 0), (-1, 0), (0, 1)):
        L = w if ny else d
        off = (d if ny else w) / 2
        px, py = x + nx * (off + 0.002), y + ny * (off + 0.002)
        tx, ty = -ny * L * 0.23, nx * L * 0.23
        pm.face([(px - tx, py - ty, z0), (px + tx, py + ty, z0), (px + tx, py + ty, z1), (px - tx, py - ty, z1)],
                (nx, ny, 0))
        qx, qy = x + nx * (off + 0.004), y + ny * (off + 0.004)
        ux, uy = -ny * 0.015, nx * 0.015
        sm.face([(qx - ux, qy - uy, z0 + 0.012), (qx + ux, qy + uy, z0 + 0.012), (qx + ux, qy + uy, z1 - 0.012),
                 (qx - ux, qy - uy, z1 - 0.012)], (nx, ny, 0))
    pm.obj(panel, "panels")
    sm.obj(neon, "strips")
    ch = max(0.035, h * 0.1)
    bx((w * 0.8, d * 0.8, ch), (x, y, h + ch / 2), st, bev=0)
    bx((w * 0.86, d * 0.86, 0.012), (x, y, h + ch), plate, bev=0)
    bx((w * 0.8 + 0.008, d * 0.8 + 0.008, 0.01), (x, y, h + 0.012), neon, bev=0)  # a light line round the crown foot
    zt = h + ch + 0.006
    if top == "spire":
        hc = min(w, d) * sp
        cn(min(w, d) * 0.4, hc, (x, y, zt + hc / 2), cap, 4, rot=(0, 0, math.pi / 4))
        zt += hc
    elif top == "beacon":  # a lit roof light under a dark cap (the glowing tower tips of frame 2)
        bx((w * 0.46, d * 0.46, 0.032), (x, y, zt + 0.016), tip, bev=0)
        bx((w * 0.56, d * 0.56, 0.014), (x, y, zt + 0.039), cap, bev=0)
        zt += 0.046
    elif top == "dome":
        r = min(w, d) * 0.36
        cy(r + 0.006, 0.01, (x, y, zt + 0.003), neon, 8)
        hemi(r, (x, y, zt), flat("dome_glass", "#6fa9cf", 0.3), 8, 2, (1, 1, 0.9))
        zt += r * 0.9
    else:  # flat roof with plant and a dish
        bx((w * 0.34, d * 0.3, 0.03), (x - w * 0.18, y + d * 0.12, zt + 0.015), seam, bev=0)
        cy(0.022, 0.012, (x + w * 0.2, y - d * 0.15, zt + 0.006), cap, 8)
    if needle:
        rod((x, y, zt - 0.01), (x, y, zt + needle), 0.006, cap, r2=0.0015, n=4)
        bx((0.014, 0.014, 0.014), (x, y, zt + needle * 0.6), tip, bev=0)
        zt += needle
    return zt


def d8_podium(x, y, w, d, h, mats, rz=0.0, plant=True, lights=True):
    """A low steel block (the podiums of frames 2 and 5): window slits, a band of warm lit shopfronts, a cold light
    line under the plate roof, a dark roof deck with glowing roof-light bars (seen from the game camera above), roof
    plant."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((w, d, h), (0, 0, h / 2), st, bev=0)
        bx((w + 0.004, d + 0.004, 0.016), (0, 0, 0.022 + 0.012), flat("warm8", "#ffbe62", 0.5), bev=0)
        bx((w + 0.008, d + 0.008, 0.008), (0, 0, h - 0.005), neon, bev=0)
        bx((w + 0.016, d + 0.016, 0.014), (0, 0, h + 0.007), plate, bev=0)
        bx((w - 0.028, d - 0.028, 0.006), (0, 0, h + 0.016), flat("deck8", "#2c3137", 0.6), bev=0)
        if lights:  # two roof-light bars along the long sides
            ln, wd = (w, d) if w >= d else (d, w)
            for s_ in (-1, 1):
                o = wd / 2 - 0.03
                bx((ln * 0.62, 0.012, 0.006) if w >= d else (0.012, ln * 0.62, 0.006),
                   (0, s_ * o, h + 0.02) if w >= d else (s_ * o, 0, h + 0.02), neon, bev=0)
        if plant:
            bx((min(w * 0.3, 0.07), min(d * 0.4, 0.05), 0.026), (w * 0.22, d * 0.08, h + 0.027), seam, bev=0)
            cy(0.016, 0.03, (-w * 0.28, -d * 0.12, h + 0.029), cap, 8)
    build_at(b, x, y, rz)


def d8_mast(x, y, h, mats):
    """A light mast by the avenue: a slim pale pole with a cold lamp."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(0.006, h, (x, y, 0.02 + h / 2), seam, 6)
    bx((0.02, 0.02, 0.02), (x, y, 0.02 + h + 0.01), tip, bev=0)


def d8_dome(x, y, r, h, mats):
    """The civic dome of frame 2: a plinth, a steel drum with window slits under a band of team panels with a light
    ring, a cornice, a blue glass dome with pale ribs and a ring rib, a plate oculus with a lit lantern and a needle."""
    st, plate, seam, panel, cap, neon, tip = mats
    n = 16
    cy(r + 0.03, 0.03, (x, y, 0.035), plate, n)
    cy(r, h, (x, y, h / 2), st, n)
    cy(r + 0.004, h * 0.3, (x, y, h * 0.7), panel, n)
    cy(r + 0.008, 0.012, (x, y, h * 0.7), neon, n)
    cy(r * 1.08, 0.02, (x, y, h + 0.01), plate, n)
    R, C, z0 = r * 0.97, r * 0.97 * 0.74, h + 0.02
    hemi(R, (x, y, z0), flat("dome_glass", "#6fa9cf", 0.3), n, 4, (1, 1, 0.74))

    def pt(phi, a):
        return (x + R * math.cos(phi) * math.cos(a), y + R * math.cos(phi) * math.sin(a), z0 + C * math.sin(phi))

    def nrm(phi, a):
        v = (math.cos(phi) * math.cos(a) / R, math.cos(phi) * math.sin(a) / R, math.sin(phi) / C)
        ln = math.sqrt(sum(c * c for c in v))
        return tuple(c / ln for c in v)

    ribs = _MB()
    phis = [0.0, 0.35, 0.7, 1.05, 1.3]
    for k in range(8):
        a = math.tau * k / 8 + math.pi / 8
        for i in range(len(phis) - 1):
            pm_ = (phis[i] + phis[i + 1]) / 2
            ribs.strip(pt(phis[i], a), pt(phis[i + 1], a), nrm(pm_, a), 0.012, 0.004)
    for k in range(n):  # a ring rib round the dome's shoulder
        a0, a1 = math.tau * k / n, math.tau * (k + 1) / n
        ribs.strip(pt(0.62, a0), pt(0.62, a1), nrm(0.62, (a0 + a1) / 2), 0.01, 0.004)
    ribs.obj(seam, "ribs")
    zt = z0 + C
    cy(r * 0.24, 0.022, (x, y, zt), plate, 8)
    cy(r * 0.17, 0.02, (x, y, zt + 0.02), tip, 8)
    rod((x, y, zt + 0.025), (x, y, zt + 0.11), 0.006, cap, r2=0.0015, n=4)
    return zt + 0.11


def d8_round(x, y, r, h, mats):
    """A slim round steel tower (the drum towers of frame 2): neon rings, light strips, a plate crown, a glass cap."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r + 0.025, 0.03, (x, y, 0.035), plate, 10)
    cy(r, h, (x, y, h / 2), st, 10)
    for zf in (0.42, 0.78):
        cy(r + 0.007, 0.012, (x, y, h * zf), neon, 10)
    sm = _MB()
    for a in (-math.pi / 2, math.pi / 6, math.pi * 5 / 6):  # light strips down three sides
        ca, sa = math.cos(a), math.sin(a)
        px, py = x + ca * (r + 0.003), y + sa * (r + 0.003)
        ux, uy = -sa * 0.011, ca * 0.011
        sm.face([(px - ux, py - uy, h * 0.1), (px + ux, py + uy, h * 0.1), (px + ux, py + uy, h * 0.9),
                 (px - ux, py - uy, h * 0.9)], (ca, sa, 0))
    sm.obj(neon, "strips")
    cy(r * 1.15, 0.024, (x, y, h + 0.012), plate, 10)
    hemi(r * 0.92, (x, y, h + 0.024), flat("dome_glass", "#6fa9cf", 0.3), 10, 2, (1, 1, 0.8))
    zt = h + 0.024 + r * 0.92 * 0.8
    rod((x, y, zt - 0.01), (x, y, zt + 0.07), 0.006, cap, r2=0.0015, n=4)
    bx((0.014, 0.014, 0.014), (x, y, zt + 0.045), tip, bev=0)


def d8_skybridge(p0, p1, mats):
    """A steel skybridge with a light line under it (the lit bridges of frame 2)."""
    st, plate, seam, panel, cap, neon, tip = mats
    beam(p0, p1, 0.04, plate)
    beam((p0[0], p0[1], p0[2] - 0.024), (p1[0], p1[1], p1[2] - 0.024), 0.014, neon)


def solar8():
    """Solar cells: a navy sheet ruled into cells by pale frame lines (world space, baked) — the dark blue panel
    fields of frame 2."""
    key = ("solar8",)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("solar8")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links

    def mth(op, a, b):
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
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])
    lx = mth("GREATER_THAN", mth("FRACT", mth("DIVIDE", sp.outputs[0], 0.027), None), 0.8)
    ly = mth("GREATER_THAN", mth("FRACT", mth("DIVIDE", sp.outputs[1], 0.022), None), 0.78)
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(mth("MAXIMUM", lx, ly), _sock(mx, "Factor_Float"))
    _sock(mx, "A_Color").default_value = (*kit.srgb("#1f3a6b"), 1)
    _sock(mx, "B_Color").default_value = (*kit.srgb("#9fb3cc"), 1)
    bs = nt.nodes["Principled BSDF"]
    L.new(_sock(mx, "Result_Color", True), bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.4
    kit._MATS[key] = m
    return m


def d8_solar(x, y, cols, rows, mats, pw=0.12, pd=0.08):
    """A field of tilted solar panels on low rails, in a pale frame."""
    st, plate, seam, panel, cap, neon, tip = mats
    sm = solar8()
    W, D = cols * (pw + 0.014), rows * (pd + 0.03)
    bx((W + 0.03, D + 0.02, 0.008), (x, y, 0.024), plate, bev=0)
    for j in range(rows):
        yy = y - D / 2 + (j + 0.5) * D / rows
        bx((W, 0.014, 0.022), (x, yy + 0.012, 0.034), cap, bev=0)  # the rail under the high edge
        for i in range(cols):
            xx = x - W / 2 + (i + 0.5) * W / cols
            bx((pw, pd, 0.006), (xx, yy, 0.044), sm, bev=0, rot=(0.38, 0, 0))  # tilted towards −Y (the sun side)


def d8_hangar(x, y, w, d, h, mats, rz=0.0):
    """A steel hangar under a pale barrel vault with dark ribs; lit doors in both gable ends, a light line along it."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((w, d, h), (0, 0, h / 2), st, bev=0)
        R, hv, segs = d / 2 + 0.008, d * 0.36, 6
        roof, ends, rib = _MB(), _MB(), _MB()
        arc = [(R * math.cos(math.pi * i / segs), h + hv * math.sin(math.pi * i / segs)) for i in range(segs + 1)]
        for i in range(segs):
            (y0, z0), (y1, z1) = arc[i], arc[i + 1]
            nyz = (0, (y0 + y1) / 2, (z0 + z1) / 2 - h)  # outward from the vault's axis
            roof.face([(-w / 2 - 0.01, y0, z0), (w / 2 + 0.01, y0, z0), (w / 2 + 0.01, y1, z1), (-w / 2 - 0.01, y1, z1)],
                      nyz)
            for xr in (-w * 0.3, 0.0, w * 0.3):  # ribs across the vault
                rib.strip((xr, y0, z0), (xr, y1, z1), nyz, 0.014, 0.004)
        for sx in (-1, 1):
            ends.face([(sx * w / 2, yy, zz) for yy, zz in arc], (sx, 0, 0))
        roof.obj(seam, "vault")
        ends.obj(st, "gables")
        rib.obj(cap, "ribs")
        for sx in (-1, 1):
            bx((0.006, d * 0.5, h * 0.72), (sx * (w / 2 + 0.002), 0, h * 0.36 + 0.02), flat("door8", "#23282f", 0.6),
               bev=0)
            bx((0.008, d * 0.56, 0.01), (sx * (w / 2 + 0.004), 0, h * 0.78 + 0.02), neon, bev=0)
            bx((0.008, d * 0.5, 0.012), (sx * (w / 2 + 0.004), 0, 0.03), flat("warm8", "#ffbe62", 0.5), bev=0)
        for sy in (-1, 1):
            bx((w + 0.004, 0.008, 0.01), (0, sy * (d / 2 + 0.002), h - 0.012), neon, bev=0)
    build_at(b, x, y, rz)


def d8_pad(x, y, r, z, mats):
    """A landing pad: a dark deck on a raised steel drum with a hazard-striped rim, a cold light circle with a cross
    bar and four lit corner lamps."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r, z - 0.01, (x, y, (z - 0.01) / 2), plate, 12)
    # the hazard rim: an open band and a top ring only (full cylinder caps would be big striped islands in the atlas)
    rim = _MB()
    R0, R1 = r * 0.92, r + 0.004
    for k in range(12):
        a0, a1 = math.tau * k / 12, math.tau * (k + 1) / 12
        am = (a0 + a1) / 2

        def p_(R, a, zz):
            return (x + R * math.cos(a), y + R * math.sin(a), zz)
        rim.face([p_(R1, a0, z - 0.016), p_(R1, a1, z - 0.016), p_(R1, a1, z + 0.002), p_(R1, a0, z + 0.002)],
                 (math.cos(am), math.sin(am), 0))
        rim.face([p_(R0, a0, z + 0.002), p_(R1, a0, z + 0.002), p_(R1, a1, z + 0.002), p_(R0, a1, z + 0.002)],
                 (0, 0, 1))
    rim.obj(hazard_ring(x, y, R1, 12), "rim")
    cy(r * 0.94, 0.008, (x, y, z + 0.002), flat("deck8", "#2c3137", 0.6), 12)
    ring = _MB()
    for k in range(12):
        a0, a1 = math.tau * k / 12, math.tau * (k + 1) / 12
        ring.strip((x + math.cos(a0) * r * 0.66, y + math.sin(a0) * r * 0.66, z + 0.008),
                   (x + math.cos(a1) * r * 0.66, y + math.sin(a1) * r * 0.66, z + 0.008), (0, 0, 1), 0.016, 0.0)
    ring.obj(neon, "padring")
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        bx((0.02, 0.02, 0.014), (x + math.cos(a) * r * 0.84, y + math.sin(a) * r * 0.84, z + 0.012), tip, bev=0)


def d8_shuttle(x, y, z, rz, team, mats):
    """A small shuttle parked on a pad: a pale hull with a team stripe, a dark canopy, swept wings, two engine pods."""
    st, plate, seam, panel, cap, neon, tip = mats
    hull = flat("hull8", "#c3cad3", 0.4)

    def b():
        taper_box((0.2, 0.07, 0.045), (0, 0, 0.03), hull, top=(0.82, 0.62))
        wedge = [(0.1, -0.035), (0.17, 0.0), (0.1, 0.035)]
        extrude(wedge, 0.008, 0.045, hull)
        bx((0.06, 0.05, 0.016), (0.075, 0, 0.056), flat("cab8", "#1b2533", 0.3), bev=0)
        bx((0.09, 0.072, 0.012), (-0.03, 0, 0.054), flat("hullteam" + team, team, 0.5), bev=0)
        wing = [(0.03, 0.03), (-0.07, 0.13), (-0.1, 0.13), (-0.08, 0.03)]
        extrude(wing, 0.018, 0.026, hull)
        extrude([(px, -py) for px, py in wing], 0.018, 0.026, hull)
        for sy in (-1, 1):
            cy(0.018, 0.07, (-0.075, sy * 0.115, 0.028), plate, 8, rot=(0, math.pi / 2, 0))
            cy(0.013, 0.006, (-0.112, sy * 0.115, 0.028), tip, 8, rot=(0, math.pi / 2, 0))
            bx((0.03, 0.012, 0.006), (-0.085, sy * 0.13, 0.024 + 0.0), flat("hullteam" + team, team, 0.5), bev=0)
    build_at(b, x, y, rz, z=z)


def d8_tank(x, y, r, h, mats):
    """A pale storage tank with a light band and a domed cap."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r, h, (x, y, h / 2), seam, 10)
    cy(r + 0.004, 0.012, (x, y, h * 0.62), neon, 10)
    cy(r + 0.004, 0.014, (x, y, 0.03), plate, 10)
    hemi(r, (x, y, h), seam, 10, 2, (1, 1, 0.5))


def d8_containers(x, y, rz, team, mats):
    """A stack of cargo containers (team colour, amber, grey) with dark end doors."""
    def b():
        for (u, v, z, c) in ((0.0, 0.0, 0.0, team), (0.0, 0.05, 0.0, "#b8862e"), (0.0, 0.1, 0.0, "#7b838e"),
                             (0.01, 0.025, 0.04, "#7b838e"), (0.0, 0.075, 0.04, team)):
            bx((0.11, 0.044, 0.04), (u, v, 0.02 + z + 0.02), flat("cont8" + c, shade(c, 0.85), 0.6), bev=0)
            for sx in (-1, 1):
                bx((0.004, 0.036, 0.032), (u + sx * 0.056, v, 0.02 + z + 0.02), flat("door8", "#23282f", 0.6), bev=0)
    build_at(b, x, y, rz)


def d8_car(x, y, rz, color, mats):
    """A small hover car over an avenue: a rounded body, a dark canopy, a cold glow under it."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        taper_box((0.06, 0.03, 0.016), (0, 0, 0.042), flat("car8" + color, color, 0.4), top=(0.8, 0.8))
        bx((0.026, 0.022, 0.01), (-0.004, 0, 0.054), flat("cab8", "#1b2533", 0.3), bev=0)
        bx((0.046, 0.022, 0.004), (0, 0, 0.032), tip, bev=0)
    build_at(b, x, y, rz)


def d8_portal(x, y, rz, mats):
    """A lit entrance porch (the portal of frame 5) facing −Y after the turn rz: steel, plate roof, cold-lit door."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((0.13, 0.07, 0.09), (0, 0, 0.045), st, bev=0)
        bx((0.15, 0.085, 0.014), (0, -0.004, 0.097), plate, bev=0)
        bx((0.06, 0.006, 0.06), (0, -0.036, 0.05), tip, bev=0)
        for sx in (-1, 1):
            bx((0.018, 0.018, 0.1), (sx * 0.056, -0.038, 0.05), plate, bev=0)
            bx((0.006, 0.006, 0.07), (sx * 0.056, -0.048, 0.05), neon, bev=0)
    build_at(b, x, y, rz)


def district_scifi(team):
    """DL8+ built-up land, variant A — the tower cluster of reference frame 2 in the citadel's steel kit: a tall
    central spire rising from a podium megablock with a second spire and a mid-rise, a beacon tower over a skybridge,
    a small domed tower, every face with an inset team panel and a cold light strip; podiums with warm lit
    shopfronts round a glowing avenue and side street, lawns with pines, light masts, crates. On a hex-shaped dark
    steel plate; lower than city_dl8, so the city still stands out."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    d8_plate(mats)
    d8_road((-0.74, -0.1), (0.74, -0.1), 0.09, mats)
    d8_road((0.1, -0.145), (0.1, -0.7), 0.07, mats)
    # the back of the block: a podium megablock with the central spire, a second spire and a mid-rise between them
    d8_podium(-0.2, 0.25, 0.62, 0.3, 0.1, mats)
    d8_tower(-0.06, 0.25, 0.19, 0.17, 0.42, mats, "spire", foot=False, sp=1.3)
    d8_tower(-0.4, 0.22, 0.15, 0.14, 0.3, mats, "spire", foot=False)
    d8_tower(-0.24, 0.36, 0.13, 0.1, 0.18, mats, "roof", buttress=False, needle=0.0, foot=False)
    d8_podium(0.38, 0.3, 0.28, 0.24, 0.08, mats, plant=False)
    d8_tower(0.36, 0.3, 0.16, 0.15, 0.34, mats, "beacon", foot=False)
    d8_skybridge((0.04, 0.28, 0.27), (0.28, 0.3, 0.27), mats)
    d8_tower(0.1, 0.56, 0.13, 0.11, 0.22, mats, "dome", buttress=False)
    d8_tower(0.58, 0.07, 0.14, 0.15, 0.16, mats, "roof", buttress=False, needle=0.05)
    d8_lawn(-0.38, 0.54, 0.24, 0.15, mats, 0.5, ((-0.07, 0.0, 0.85), (0.06, 0.02, 0.7)))
    # the front of the block: a spire on a podium, a flat-roofed tower on another, a low block, a lawn with pines
    d8_podium(0.42, -0.36, 0.32, 0.24, 0.08, mats, plant=False)
    d8_tower(0.36, -0.34, 0.14, 0.14, 0.27, mats, "spire", foot=False)
    d8_tower(0.52, -0.43, 0.08, 0.07, 0.13, mats, "beacon", buttress=False, needle=0.0, foot=False)
    d8_podium(-0.38, -0.36, 0.3, 0.24, 0.07, mats, plant=False)
    d8_tower(-0.42, -0.34, 0.16, 0.14, 0.22, mats, "roof", foot=False, needle=0.06)
    d8_podium(-0.2, -0.58, 0.22, 0.12, 0.1, mats, plant=False, lights=False)
    d8_pad(-0.2, -0.58, 0.05, 0.135, mats)  # a small rooftop landing pad
    d8_lawn(-0.04, -0.36, 0.14, 0.2, mats, 0.0, ((0.0, 0.05, 0.75), (0.01, -0.05, 0.6)))
    for (x, y) in ((-0.6, -0.17), (0.2, -0.03), (0.68, -0.17), (0.18, -0.62)):
        d8_mast(x, y, 0.13, mats)
    for (x, y, s_) in ((0.22, 0.03, 0.04), (0.27, 0.035, 0.03)):
        bx((s_, s_ * 1.4, s_), (x, y, 0.02 + s_ / 2), flat("crate8", "#b8862e", 0.6), bev=0)
    d8_car(-0.3, -0.08, 0.0, "#e6e9ee", mats)
    d8_car(0.42, -0.12, math.pi, team, mats)


def district_scifi_b(team):
    """DL8+ built-up land, variant B — the civic block of frame 2: a great blue glass dome with pale ribs over a steel
    drum banded in team panels and a light ring, on a plaza with a glowing rim, ringed by spired and beacon towers
    on podiums, a drum tower with a glass cap, mid-rise blocks, podiums with warm lit shopfronts and lawns with
    pines."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    d8_plate(mats, 1)
    dx_, dy_ = -0.06, 0.06
    cy(0.33, 0.004, (dx_, dy_, 0.022), flat("road8", "#2a2e34", 0.6), 20)  # the plaza round the dome
    ring = _MB()
    for k in range(20):
        a0, a1 = math.tau * k / 20, math.tau * (k + 1) / 20
        ring.strip((dx_ + math.cos(a0) * 0.32, dy_ + math.sin(a0) * 0.32, 0.025),
                   (dx_ + math.cos(a1) * 0.32, dy_ + math.sin(a1) * 0.32, 0.025), (0, 0, 1), 0.014, 0.0)
    ring.obj(neon, "plazaring")
    d8_road((dx_ + 0.03, dy_ - 0.32), (0.0, -0.72), 0.08, mats)
    d8_dome(dx_, dy_, 0.25, 0.14, mats)
    d8_portal(dx_ + 0.01, dy_ - 0.275, 0.0, mats)
    d8_car(-0.005, -0.5, 1.48, "#e6e9ee", mats)
    d8_podium(0.46, 0.27, 0.24, 0.22, 0.07, mats, plant=False)
    d8_tower(0.44, 0.27, 0.15, 0.14, 0.4, mats, "spire", foot=False)
    d8_podium(0.45, -0.3, 0.24, 0.22, 0.07, mats, plant=False)
    d8_tower(0.42, -0.28, 0.14, 0.13, 0.26, mats, "beacon", foot=False)
    d8_tower(-0.5, -0.24, 0.13, 0.13, 0.3, mats, "spire")
    d8_round(-0.46, 0.4, 0.08, 0.3, mats)
    d8_tower(0.33, 0.48, 0.1, 0.1, 0.14, mats, "roof", buttress=False, needle=0.05)
    d8_podium(0.5, -0.02, 0.16, 0.2, 0.1, mats)
    d8_podium(0.06, 0.6, 0.32, 0.12, 0.08, mats, 0.0)
    d8_podium(-0.62, 0.08, 0.12, 0.22, 0.07, mats, plant=False)
    d8_podium(-0.36, -0.56, 0.2, 0.1, 0.08, mats)
    d8_lawn(-0.2, -0.42, 0.14, 0.12, mats, 0.0, ((0.0, 0.0, 0.8),))
    d8_lawn(0.22, -0.52, 0.18, 0.13, mats, 0.0, ((-0.04, 0.0, 0.75), (0.05, 0.01, 0.6)))
    for (x, y) in ((-0.12, -0.6), (0.11, -0.36), (0.22, 0.34), (-0.42, 0.13)):
        d8_mast(x, y, 0.13, mats)


def district_scifi_c(team):
    """DL8+ built-up land, variant C — the service block: a raised landing pad with a hazard rim, a light circle and
    a parked shuttle in the team colour, a steel hangar under a ribbed vault, stacks of cargo containers, a control
    tower with a glass cab, a field of solar panels (the dark blue grids of frame 2), storage tanks with light bands
    and pipes, a works block with two stacks, a gatehouse, light masts along a glowing service road."""
    mats = d8_mats(team)
    st, plate, seam, panel, cap, neon, tip = mats
    d8_plate(mats, 2)
    d8_road((-0.74, -0.02), (0.74, -0.02), 0.085, mats)
    # front: the landing pad with a shuttle, the hangar, containers, a gatehouse
    d8_pad(0.36, -0.3, 0.21, 0.05, mats)
    d8_shuttle(0.36, -0.3, 0.049, 0.6, team, mats)  # (hull on the deck)
    d8_hangar(-0.33, -0.3, 0.38, 0.24, 0.11, mats)
    d8_containers(0.03, -0.3, math.pi / 2, team, mats)
    d8_podium(-0.08, -0.58, 0.2, 0.12, 0.08, mats)
    d8_car(-0.12, -0.04, 0.0, team, mats)
    d8_car(0.46, 0.0, math.pi, "#e6e9ee", mats)
    # back: the control tower, the solar field, tanks with pipes, the works block with two stacks
    tx, ty = 0.06, 0.24
    bx((0.15, 0.15, 0.03), (tx, ty, 0.035), plate, bev=0)
    bx((0.1, 0.1, 0.36), (tx, ty, 0.18), st, bev=0)
    bx((0.112, 0.112, 0.016), (tx, ty, 0.12), seam, bev=0)
    pm, sm_ = _MB(), _MB()
    for (nx, ny) in ((0, -1), (1, 0), (-1, 0), (0, 1)):
        px, py = tx + nx * 0.052, ty + ny * 0.052
        ux, uy = -ny * 0.024, nx * 0.024
        pm.face([(px - ux, py - uy, 0.135), (px + ux, py + uy, 0.135), (px + ux, py + uy, 0.34),
                 (px - ux, py - uy, 0.34)], (nx, ny, 0))
        px, py = tx + nx * 0.054, ty + ny * 0.054
        ux, uy = -ny * 0.013, nx * 0.013
        sm_.face([(px - ux, py - uy, 0.145), (px + ux, py + uy, 0.145), (px + ux, py + uy, 0.33),
                  (px - ux, py - uy, 0.33)], (nx, ny, 0))
    pm.obj(panel, "panels")
    sm_.obj(neon, "strips")
    cy(0.1, 0.018, (tx, ty, 0.369), plate, 8)
    cy(0.095, 0.05, (tx, ty, 0.403), flat("cab8", "#1b2533", 0.3), 8)
    cy(0.099, 0.01, (tx, ty, 0.405), tip, 8)
    cy(0.105, 0.016, (tx, ty, 0.436), cap, 8)
    rod((tx, ty, 0.44), (tx, ty, 0.56), 0.007, cap, r2=0.002, n=4)
    bx((0.016, 0.016, 0.016), (tx, ty, 0.52), tip, bev=0)
    bx((0.05, 0.004, 0.03), (tx + 0.02, ty, 0.5), seam, bev=0)  # a radar vane on the mast
    d8_solar(-0.36, 0.33, 3, 2, mats)
    d8_tank(0.38, 0.2, 0.065, 0.17, mats)
    d8_tank(0.54, 0.07, 0.055, 0.14, mats)
    pipe = flat("pipe8", "#6b737e", 0.4)
    rod((0.38, 0.2, 0.08), (0.54, 0.07, 0.08), 0.012, pipe, n=6)
    rod((0.38, 0.2, 0.06), (0.11, 0.24, 0.06), 0.012, pipe, n=6)
    d8_podium(0.26, 0.5, 0.26, 0.15, 0.12, mats, 0.0, plant=False)
    for sx in (-1, 1):
        x = 0.26 + sx * 0.065
        cy(0.034, 0.14, (x, 0.5, 0.19), seam, 10)
        cy(0.038, 0.014, (x, 0.5, 0.255), cap, 10)
        cy(0.036, 0.01, (x, 0.5, 0.21), neon, 10)
    d8_podium(-0.62, 0.15, 0.12, 0.16, 0.09, mats, 0.0)
    d8_lawn(-0.18, 0.6, 0.22, 0.11, mats, 0.0, ((-0.06, 0.0, 0.7), (0.06, 0.0, 0.6)))
    for (x, y) in ((-0.5, -0.09), (-0.02, 0.05), (0.62, -0.09), (0.12, -0.52)):
        d8_mast(x, y, 0.13, mats)


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
    ASSETS[f"district_scifi_{_t}"] = (lambda c: (lambda: district_scifi(c)))(_c)
    ASSETS[f"district_scifi_b_{_t}"] = (lambda c: (lambda: district_scifi_b(c)))(_c)
    ASSETS[f"district_scifi_c_{_t}"] = (lambda c: (lambda: district_scifi_c(c)))(_c)
for _n in range(1, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"city_dl{_n}_{_t}"] = (lambda f, c: (lambda: f(c)))(CITY[_n - 1], _c)
        ASSETS[f"residence_dl{_n}_{_t}"] = (lambda f, c: (lambda: f(c)))(RES[_n - 1], _c)
for _n in range(1, 9):
    ASSETS[f"fort_l{_n}"] = (lambda n: (lambda: fort_ring(n)))(_n)
    ASSETS[f"fort_l{_n}_edge"] = (lambda n: (lambda: fort_edge(n)))(_n)
    ASSETS[f"fort_l{_n}_post"] = (lambda n: (lambda: fort_post(n)))(_n)


ROUND_ANGLE = 65  # smooth-by-angle limit of the parts tagged "round" (lowpoly)


def _soft_keep(objs):
    """The soft masses (bx / cy soft=...) that keep their round 3-segment bevel: those whose smallest side is at least
    SOFT_MIN, at most SOFT_MAX of them, the largest by volume (a group of equal ones at the cut is left out whole, so
    twin towers stay alike)."""
    vol = lambda o: round(o.dimensions[0] * o.dimensions[1] * o.dimensions[2], 6)  # noqa: E731
    cand = sorted((o for o in objs if o.get("soft") and min(o.dimensions) >= SOFT_MIN), key=vol, reverse=True)
    if len(cand) > SOFT_MAX:
        cut = vol(cand[SOFT_MAX])
        cand = [o for o in cand[:SOFT_MAX] if vol(o) > cut]
    return {o.name for o in cand}


def lowpoly(objs):
    """Mobile budget: one-segment chamfers, no bevel on tiny parts, smooth-by-angle shading. «Raivon Soft» (§6.2):
    the few largest soft masses (_soft_keep) keep their round 3-segment bevel, followed by a WEIGHTED_NORMAL that
    keeps the sharp edges (_soften), so their big faces stay flat and only the bevels shade round."""
    keep = _soft_keep(objs)
    plain = []
    for o in objs:
        dims = min(o.dimensions) if o.dimensions else 0
        bevels = [md for md in o.modifiers if md.type == "BEVEL"]
        for md in bevels:
            if o.name in keep:
                md.segments = 3
                md.width = min(md.width, dims * 0.2)
                break
            md.segments = 1
            if dims < 0.03 or md.width < 0.004:
                for x in list(o.modifiers):
                    o.modifiers.remove(x)
                break
            md.width = min(md.width, dims * 0.2)
        if not any(md.type == "BEVEL" for md in o.modifiers):
            plain.append(o)
    if keep:
        print(f"soft masses: {len(keep)} keep a round 3-segment bevel", flush=True)
    # «Raivon Soft»: parts tagged "round" (the 6-sided ridge, hip and barge rolls, the izba logs) shade as smooth
    # tubes: their 60° facets fall under ROUND_ANGLE (the end caps stay crisp at 90°), at no triangle cost
    for want, ang in ((False, 50), (True, ROUND_ANGLE)):
        group = [o for o in plain if bool(o.get("round")) == want]
        if group:
            bpy.ops.object.select_all(action="DESELECT")
            for o in group:
                o.select_set(True)
            bpy.context.view_layer.objects.active = group[0]
            bpy.ops.object.shade_smooth_by_angle(angle=math.radians(ang))


SETTLED = {"homestead", "city_dl1", "city_dl2", "city_dl3", "city_dl4", "residence_dl1", "residence_dl2",
           "residence_dl3", "residence_dl4", "residence_dl5", "residence_dl6", "residence_dl7", "residence_dl8",
           "city_dl5", "city_dl6", "city_dl7", "city_dl8"}


def _drop_ground_faces(objs):
    """Delete the faces that lie flat on the ground facing down (the pad's underside, the bottoms of walls, plinths
    and barrels standing on it): the camera and the sun are always above, so they never show or cast a shadow, and
    leaving them out gives their share of the bake to the parts that are seen."""
    for o in objs:
        if o.modifiers:  # a bevelled box: leave its chamfered bottom alone
            continue
        me = o.data
        if me.users > 1:
            o.data = me = me.copy()
        mw = o.matrix_world
        n3 = mw.to_3x3()
        bm = bmesh.new()
        bm.from_mesh(me)
        doomed = []
        for f in bm.faces:
            nz = (n3 @ f.normal).normalized().z if f.normal.length > 0 else 0.0
            if nz < -0.985 and max((mw @ v.co).z for v in f.verts) < 0.016:
                doomed.append(f)
        if doomed and len(doomed) < len(bm.faces):
            bmesh.ops.delete(bm, geom=doomed, context="FACES_ONLY")
            bm.to_mesh(me)
            me.update()
        bm.free()


ATLAS = {"residence_dl4", "residence_dl5", "residence_dl6", "residence_dl7", "residence_dl8",
         "city_dl5", "city_dl6", "city_dl7", "city_dl8"}  # (the late cities: dense tile courses and thin trim too)
# the DL8 districts stand on many hexes at once: the tight atlas at 512 px (as the towers), so their window slits and
# panels keep their texels without a 1024 sheet per variant
DISTRICTS = {"district_scifi", "district_scifi_b", "district_scifi_c"}
# the DL6+ countryside: hundreds of small props (crop heads, pickets, panels) on one hex — the same tight 512 atlas, so
# the flat colours collapse into palette cells and the textured faces (siding, furrows, corrugation) keep the texels
LATE_RURAL = {"homestead_modern", "homestead_scifi", "farm_modern", "farm_scifi", "mine_scifi"}


def _kept(mt):
    """A material that keeps its own shader in the game (a lamp, a lit window, metal): it never samples the bake."""
    b = mt.node_tree.nodes["Principled BSDF"]
    return b.inputs["Emission Strength"].default_value > 0 or b.inputs["Metallic"].default_value > 0.3


def _uniform(mt):
    """A material of one flat colour: nothing feeds its base colour."""
    b = mt.node_tree.nodes.get("Principled BSDF")
    return b is not None and not b.inputs["Base Color"].is_linked


# the gutter fill moved to export_assets (bake_asset fills its gutter too); kept under the old name for the other
# exporters that call it from here
_fill_gutter = ea._fill_gutter


def bake_atlas(objs, size=1024, thin=0.018, cell=12, margin=0.003):
    """export_assets.bake_asset with a tighter atlas, for the hero residences.

    smart_project spends its island margin on every island, and a castle of boxes, slits and tile courses is
    thousands of small islands: the stone and roof textures shrank to a fraction of the sheet and the thinnest parts
    sampled the black gutter. Here only the faces that carry texture detail are unwrapped (then packed by the
    concave packer with one fixed margin); faces of one flat colour, faces whose material keeps its own shader, and
    faces thinner than `thin` (posts, rails, course lips: a texel or two wide, no room for detail) all collapse onto
    one small palette cell per material in a strip along the top of the sheet."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.convert(target="MESH")  # apply modifiers
    bpy.ops.object.join()
    ob = bpy.context.active_object
    me = ob.data
    mw = ob.matrix_world
    plain = [_uniform(s.material) or _kept(s.material) for s in ob.material_slots]
    pal = []
    for p in me.polygons:
        vs = [mw @ me.vertices[i].co for i in p.vertices]
        area = sum(((vs[i] - vs[0]).cross(vs[i + 1] - vs[0])).length for i in range(1, len(vs) - 1)) / 2
        lmax = max((vs[i] - vs[i - 1]).length for i in range(len(vs))) or 1e-9
        width = min(area / lmax * (2 if len(vs) == 3 else 1), math.sqrt(area))
        pal.append(plain[p.material_index] or width < thin)
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.select_set(False)
    for f in bm.faces:
        if pal[f.index]:
            f.hide_set(True)
    bmesh.update_edit_mesh(me)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0)
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="CARDINAL", margin_method="FRACTION", margin=margin,
                            shape_method="CONCAVE")
    bpy.ops.mesh.reveal(select=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    # the palette strip: one cell per material along the top of the sheet; the packed islands shrink to make room
    cells = sorted({p.material_index for p in me.polygons if pal[p.index]})
    per_row = size // cell
    rows = max(1, -(-len(cells) // per_row))
    s = 1.0 - rows * cell / size
    slot_cell = {mi: k for k, mi in enumerate(cells)}
    uvl = me.uv_layers.active.data
    hw = cell * 0.3 / size
    for p in me.polygons:
        lo = list(p.loop_indices)
        if not pal[p.index]:
            for li in lo:
                u, v = uvl[li].uv
                uvl[li].uv = (u * s, v * s)
            continue
        k = slot_cell[p.material_index]
        cu = (k % per_row + 0.5) * cell / size
        cv = s + (k // per_row + 0.5) * cell / size
        if len(lo) == 4:
            ring = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        elif len(lo) == 3:
            ring = [(-1, -1), (1, -1), (1, 1)]
        else:
            ring = [(math.cos(math.tau * i / len(lo)) * 1.2, math.sin(math.tau * i / len(lo)) * 1.2)
                    for i in range(len(lo))]
        for li, (a, b) in zip(lo, ring):
            uvl[li].uv = (cu + a * hw, cv + b * hw)
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
    sc.render.bake.margin_type = "EXTEND"  # a palette cell spreads its own colour, not a neighbour's across a seam
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})
    # soft painted AO on the packed islands only: the palette strip along the top (v >= s) holds many faces collapsed
    # onto one cell, so AO there would be garbage
    ea.paint_ao(ob, img, keep_rows_from=int(round(s * size)))
    _fill_gutter(img)
    # one material: the baked colour; lamps, glass and metal keep their own (as bake_asset does)
    baked = bpy.data.materials.new("baked")
    baked.use_nodes = True
    bnt = baked.node_tree
    tx = bnt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    bnt.links.new(tx.outputs["Color"], bnt.nodes["Principled BSDF"].inputs["Base Color"])
    bnt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
    keep = {i: (s_.material if _kept(s_.material) else baked) for i, s_ in enumerate(ob.material_slots)}
    mats = list(dict.fromkeys(keep.values()))
    old_idx = [p.material_index for p in me.polygons]
    me.materials.clear()
    for mm in mats:
        me.materials.append(mm)
    for p, oi in zip(me.polygons, old_idx):
        p.material_index = mats.index(keep[oi])
    img.pack()
    return ob


def export(name, out):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    lowpoly(objs)
    smokes = [o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.name.startswith(("smoke", "flag"))]
    if name.rsplit("_", 1)[0] in SETTLED | DISTRICTS | LATE_RURAL or name.startswith("fort_"):
        _drop_ground_faces(objs)
    # the hero model is seen up close, and the dense towns carry hundreds of thin beams and tile courses that need
    # the texels (at 512 they shrink below a pixel and sample the black gutter)
    if name.rsplit("_", 1)[0] in ATLAS:
        ob = bake_atlas(objs, 1024)
    elif name.rsplit("_", 1)[0] in DISTRICTS | LATE_RURAL:
        ob = bake_atlas(objs, 512)
    else:
        ob = ea.bake_asset(objs, 1024 if name.startswith(("residence", "city_dl1", "city_dl2", "city_dl3", "city_dl4"))
                           else 512)
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
