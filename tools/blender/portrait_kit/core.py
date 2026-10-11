"""Core helpers of the portrait kit (§7.5): the build context and part registry, materials, rays onto evaluated
meshes, tapered curves, metaballs with sheet-solved radii, ribbon locks, lofts and capsules, shells (shrinkwrap +
solidify + bevel) and the premultiplied Lanczos downscale.

Lessons kept from the spike (docs/art_direction.md §7.5): `import bpy` before `import bmesh`; every metaball object
gets a unique name (objects whose names share a prefix up to the dot merge into one field); every ray is cast
straight at its target (a slanted ray slides over the head); a dense sheet of balls swells past its nominal radius —
`sheet_radius` solves the radius for a wanted thickness; no Subsurf on metaball meshes (Smooth 2–3 instead).
"""
import math
import random

import bpy
import bmesh  # noqa: E402  (bmesh is importable only after bpy)
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from . import style

S = style.STYLE
H = style.HEAD_H


# ------------------------------------------------------------------ colour
def srgb(h):
    if isinstance(h, (tuple, list)):
        return tuple(h[:3])
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def rgba(h):
    return (*srgb(h), 1.0)


def hex_mix(a, b, t):
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(pa, pb))


def hex_scale(a, k):
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(x * k)))) for x in pa)


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp_table(tbl, x):
    if x <= tbl[0][0]:
        return tbl[0][1]
    for (x0, y0), (x1, y1) in zip(tbl, tbl[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tbl[-1][1]


# ------------------------------------------------------------------ the build context
class Part:
    __slots__ = ("obj", "group", "parent", "detail", "kind", "head", "name")

    def __init__(self, obj, group, parent, detail, kind, head):
        self.obj, self.group, self.parent, self.detail, self.kind, self.head = obj, group, parent, detail, kind, head
        self.name = detail or obj.name


class Ctx:
    """One portrait build: the character data, the mood, the era, the landmarks the head hands out, the parts (each
    with its ID group, its parent for the contact test and whether it turns with the head), the materials."""

    def __init__(self, cid, char, mood="calm", era=1):
        self.cid, self.ch, self.mood, self.era = cid, char, mood, era
        self.smile = mood == "smile"
        self.rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(cid)))  # stable across runs
        self.parts = []
        self.mats = {}
        self.L = {}                 # landmarks, head-local kit units (before the pose)
        self.objs = {}              # named key objects: head, torso, arm-1, arm+1, hair, beard ...
        self.mb_count = 0
        self.female = char.get("female", False)
        self.W = H * char["head"]["wh"]
        self.details = {}           # P-A8: detail name -> minimum visible px on the master
        self.sig_objs = []          # the objects that make the signature (§7.2): the sig mask of the QA pass
        self.notes = []

    def add(self, obj, group, parent=None, detail=None, kind="surface", head=False):
        self.parts.append(Part(obj, group, parent, detail, kind, head))
        return obj

    def mb_name(self, base):
        self.mb_count += 1
        return "mb%s%03d" % (base, self.mb_count)


# ------------------------------------------------------------------ materials
def principled(ctx, name, col, rough=0.6, metal=0.0, sss=0.0, coat=0.0, sheen=0.0, emit=None, es=0.0, spec=0.5,
               coat_rough=0.12):
    if name in ctx.mats:
        return ctx.mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba(col)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    if sss:
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
        b.inputs["Subsurface Scale"].default_value = 0.04 * H
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = coat_rough
    if sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    if emit:
        b.inputs["Emission Color"].default_value = rgba(emit)
        b.inputs["Emission Strength"].default_value = es
    m["kit_base"] = col
    ctx.mats[name] = m
    return m


def node_mix(nt, fac, a, b, blend="MIX"):
    """RGBA mix node; a/b are sockets or hex strings; returns the result socket."""
    n = nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = blend
    for idx, v in ((6, a), (7, b)):
        if isinstance(v, str):
            n.inputs[idx].default_value = rgba(v)
        else:
            nt.links.new(v, n.inputs[idx])
    if isinstance(fac, (int, float)):
        n.inputs[0].default_value = fac
    else:
        nt.links.new(fac, n.inputs[0])
    return n.outputs[2]


def node_ramp(nt, fac, stops, interp="LINEAR"):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.interpolation = interp
    els = r.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], rgba(stops[0][1])
    els[1].position, els[1].color = stops[-1][0], rgba(stops[-1][1])
    for p, c in stops[1:-1]:
        e = els.new(p)
        e.color = rgba(c)
    nt.links.new(fac, r.inputs[0])
    return r.outputs[0]


def node_math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def node_obj_axis(nt, axis, v0, v1, space="Object"):
    """0..1 along an object-space (or generated) axis between v0 and v1."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs[space], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs[1].default_value = v0
    mr.inputs[2].default_value = v1
    nt.links.new(sep.outputs["XYZ".index(axis)], mr.inputs[0])
    return mr.outputs[0]


def node_blob(nt, centre, radius, scale=(1.0, 1.0, 1.0)):
    """Soft spherical falloff 0..1 around an object-space point (procedural paint)."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = tuple(s / radius for s in scale)
    mp.inputs["Location"].default_value = tuple(-c * s / radius for c, s in zip(centre, scale))
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    g = nt.nodes.new("ShaderNodeTexGradient")
    g.gradient_type = "QUADRATIC_SPHERE"
    nt.links.new(mp.outputs[0], g.inputs[0])
    return g.outputs["Fac"]


def ao_crevice(nt, base_socket, dark, dist=0.06 * H, at=0.8):
    """Multiply a colour by an AO-driven crevice tint (the grooves of hair, beards and fur)."""
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 8
    ao.inputs["Distance"].default_value = dist
    crev = node_ramp(nt, ao.outputs["AO"], [(0.0, dark), (at, "#ffffff")])
    return node_mix(nt, 1.0, base_socket, crev, "MULTIPLY")


def floor_albedo(nt, sock, floor="#2A2A30"):
    """§7.4's albedo floor: a colour darker than `floor` (by luminance) is scaled up to it, hue kept. Only pupils,
    lash lines, mouth interiors, seams and glasses rubber may sit below it."""
    fy = sum(k * v for k, v in zip((0.2126, 0.7152, 0.0722), srgb(floor)))
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(sock, bw.inputs[0])
    eps = nt.nodes.new("ShaderNodeMath")
    eps.operation = "MAXIMUM"
    eps.inputs[1].default_value = 1e-4
    nt.links.new(bw.outputs[0], eps.inputs[0])
    div = nt.nodes.new("ShaderNodeMath")
    div.operation = "DIVIDE"
    div.inputs[0].default_value = fy
    nt.links.new(eps.outputs[0], div.inputs[1])
    k = nt.nodes.new("ShaderNodeMath")
    k.operation = "MAXIMUM"
    k.inputs[1].default_value = 1.0
    nt.links.new(div.outputs[0], k.inputs[0])
    sc = nt.nodes.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    nt.links.new(sock, sc.inputs[0])
    nt.links.new(k.outputs[0], sc.inputs["Scale"])
    return sc.outputs["Vector"]


def hair_mat(ctx, name, col, z0, z1, dark=None, light=None, rough=0.6, crevice=None, edge=None):
    """Hair, fur, beards: object-Z gradient (`dark` at z0, `light` at z1; hair: +8 % L* on top) x AO crevice tint
    (§7.11), held at the albedo floor (§7.4: the crevice tint multiplies, so dark hair would otherwise drop far below
    it). edge = (point attribute, colour, strength): a tone painted where the attribute is 1 (a beard's root band
    along the face)."""
    if name in ctx.mats:
        return ctx.mats[name]
    m = principled(ctx, name, col, rough=rough)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    dark = dark or hex_scale(col, 0.72)
    light = light or hex_mix(col, "#ffffff", 0.12)
    base = node_ramp(nt, node_obj_axis(nt, "Z", z0, z1), [(0.0, dark), (0.55, col), (1.0, light)])
    if edge:
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = edge[0]
        base = node_mix(nt, node_math(nt, "MULTIPLY", at.outputs["Fac"], edge[2], clamp=True), base, edge[1])
    nt.links.new(floor_albedo(nt, ao_crevice(nt, base, crevice or hex_scale(col, 0.5))), b.inputs["Base Color"])
    return m


def grad_mat(ctx, name, top, bottom, z0, z1, rough=0.8, sheen=0.0, coat=0.0, axis="Z", space="Object"):
    """Fabric / leather: a vertical gradient (1.05 -> 0.92 down the torso, §7.11)."""
    if name in ctx.mats:
        return ctx.mats[name]
    m = principled(ctx, name, top, rough=rough, sheen=sheen, coat=coat)
    nt = m.node_tree
    nt.links.new(node_ramp(nt, node_obj_axis(nt, axis, z0, z1, space), [(0.0, bottom), (1.0, top)]),
                 nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m


def fabric(ctx, name, col, z0=-1.9, z1=-0.6, rough=0.8, sheen=0.3):
    return grad_mat(ctx, name, hex_scale(col, 1.05), hex_scale(col, 0.92), z0, z1, rough=rough, sheen=sheen)


def emit_mat(ctx, name, col="#ffffff", strength=6.0):
    if name in ctx.mats:
        return ctx.mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba(col)
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m["kit_base"] = col
    ctx.mats[name] = m
    return m


def glass_mat(ctx, name, tint="#ffffff"):
    """Lenses (§7.5): see-through glass with a tint by multiplication and one diagonal highlight band over ~15 % of
    the lens. Built as transparent + glossy rather than refractive transmission: without caustics a refractive lens
    darkens the eye behind it (measured: the iris kept 10 % of its contrast), §7.5 asks for >= 70 %. The Fresnel
    sheen is a flat warm-white emission (the glossy rays' world, #F2ECE2), not a glossy BSDF: a real reflection of
    the dark hair behind the far lens left near-black pixels at alpha 0.05 past the face outline (P-A6 dark fringe)."""
    if name in ctx.mats:
        return ctx.mats[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = rgba(tint)
    gl = nt.nodes.new("ShaderNodeEmission")
    gl.inputs["Color"].default_value = rgba("#F2ECE2")
    gl.inputs["Strength"].default_value = 0.6
    fr = nt.nodes.new("ShaderNodeFresnel")
    fr.inputs["IOR"].default_value = 1.1
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(fr.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    # the diagonal highlight: a band across the lens in object space (generated coordinates, x + z)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    add = node_math(nt, "ADD", sep.outputs[0], sep.outputs[2])
    band = node_math(nt, "MULTIPLY", node_math(nt, "GREATER_THAN", add, 1.32),
                     node_math(nt, "LESS_THAN", add, 1.50))
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba("#ffffff")
    em.inputs["Strength"].default_value = 0.3
    add_sh = nt.nodes.new("ShaderNodeAddShader")
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(band, mix2.inputs["Fac"])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(mix.outputs[0], add_sh.inputs[0])
    nt.links.new(em.outputs[0], add_sh.inputs[1])
    nt.links.new(add_sh.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    m["kit_base"] = tint
    ctx.mats[name] = m
    return m


# ------------------------------------------------------------------ objects
def link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def set_mat(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)


def finish(o, m=None, sub=0, smooth_iter=0, smooth_fac=0.5, smooth=True):
    if m is not None:
        set_mat(o, m)
    if o.type == "MESH" and smooth:
        for p in o.data.polygons:
            p.use_smooth = True
    if smooth_iter:
        s = o.modifiers.new("smooth", "SMOOTH")
        s.factor = smooth_fac
        s.iterations = smooth_iter
    if sub:
        s = o.modifiers.new("sub", "SUBSURF")
        s.levels = sub
        s.render_levels = sub
    return o


def bevel(o, width, segments=3, angle=None):
    b = o.modifiers.new("bevel", "BEVEL")
    b.width = width
    b.segments = segments
    if angle is not None:
        b.limit_method = "ANGLE"
        b.angle_limit = math.radians(angle)
    return b


def solidify(o, thickness, offset=1.0, rim=True):
    s = o.modifiers.new("thick", "SOLIDIFY")
    s.thickness = thickness
    s.offset = offset
    s.use_rim = rim
    return s


def shrinkwrap(o, target, offset, method="NEAREST_SURFACEPOINT", mode="OUTSIDE_SURFACE", project_y=False):
    sw = o.modifiers.new("wrap", "SHRINKWRAP")
    sw.target = target
    sw.wrap_method = method
    sw.wrap_mode = mode
    sw.offset = offset
    if method == "PROJECT":
        sw.use_project_y = project_y
        sw.use_negative_direction = True
        sw.use_positive_direction = True
    return sw


def uvsphere(name, loc, scale, m, seg=32, rings=16, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    o = mesh_obj(name, bm)
    o.location = loc
    o.scale = scale
    if rot is not None:
        o.rotation_euler = rot
    return finish(o, m)


def box(name, loc, size, m, bev=0.0, segs=3, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    o = mesh_obj(name, bm)
    o.location = loc
    o.scale = size
    if rot is not None:
        o.rotation_euler = rot
    if bev:
        bv = bevel(o, bev, segs)
        bv.affect = "EDGES"
    return finish(o, m)


def cylinder(name, loc, r, depth, m, nrm=(0, 0, 1), verts=48, bev=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r, depth=depth)
    o = mesh_obj(name, bm)
    o.location = loc
    align_z(o, nrm)
    if bev:
        bevel(o, bev, 3)
    return finish(o, m)


def torus(name, loc, R, r, m, nrm=(0, 0, 1), seg=48, rseg=16):
    bm = bmesh.new()
    vs = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(rseg):
            b = 2 * math.pi * j / rseg
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a),
                                      r * math.sin(b))))
        vs.append(ring)
    for i in range(seg):
        for j in range(rseg):
            bm.faces.new((vs[i][j], vs[(i + 1) % seg][j], vs[(i + 1) % seg][(j + 1) % rseg], vs[i][(j + 1) % rseg]))
    o = mesh_obj(name, bm)
    o.location = loc
    align_z(o, nrm)
    return finish(o, m)


def align_z(o, nor, spin=0.0):
    q = Vector((0, 0, 1)).rotation_difference(Vector(nor).normalized())
    if spin:
        q = q @ Matrix.Rotation(spin, 4, "Z").to_quaternion()
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = q


def update():
    bpy.context.view_layer.update()


def ray(obj, origin, direction, dist=10.0):
    """World-space ray onto the evaluated object (modifiers included): (location, normal) or (None, None)."""
    dg = bpy.context.evaluated_depsgraph_get()
    inv = obj.matrix_world.inverted()
    o = inv @ Vector(origin)
    d = (inv.to_3x3() @ Vector(direction)).normalized()
    ok, loc, nor, _ = obj.ray_cast(o, d, distance=dist, depsgraph=dg)
    if not ok:
        return None, None
    mw = obj.matrix_world
    return mw @ loc, (mw.to_3x3().inverted().transposed() @ nor).normalized()


def ray_front(obj, x, z, y0=-3.0):
    """Cast straight along +Y at (x, z) onto obj (the face, the chest)."""
    return ray(obj, (x, y0, z), (0, 1, 0))


def ray_to(obj, target, centre=(0, 0, 0), dist=3.0):
    """Cast from outside straight at `target` along the line from `centre` (a point on a roundish surface)."""
    d = (Vector(target) - Vector(centre))
    if d.length < 1e-6:
        d = Vector((0, -1, 0))
    d.normalize()
    return ray(obj, Vector(centre) + d * dist, -d)


def curve(name, pts, radii, depth, m, order=4, res=4, cyclic=False, kind="NURBS"):
    """Tapered tube: NURBS (or POLY) through-ish points with per-point radius (bevel_depth x radius)."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_mode = "ROUND"
    cu.bevel_depth = depth
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    cu.resolution_u = 12
    sp = cu.splines.new(kind)
    sp.points.add(len(pts) - 1)
    for p, co, r in zip(sp.points, pts, radii):
        p.co = (co[0], co[1], co[2], 1.0)
        p.radius = r
    if kind == "NURBS":
        sp.order_u = min(order, len(pts))
        sp.use_endpoint_u = True
    sp.use_cyclic_u = cyclic
    o = link(bpy.data.objects.new(name, cu))
    o.data.materials.append(m)
    return o


def curve_to_mesh(o):
    """Bake a curve object to a mesh (so it can be shrinkwrapped, ray-tested, BVH-tested)."""
    return to_mesh(o)


# ------------------------------------------------------------------ metaballs
THRESH = 0.6


def _k(stiff):
    return math.sqrt(1 - (THRESH / stiff) ** (1 / 3))


def metaball(ctx, base, elems, res=0.016):
    """elems: dicts with co and either R (raw radius) or half (surface half-extent, float or 3-tuple, designed for an
    isolated element), stiff=2, neg=False, rot=quaternion. Unique object names (see the module docstring)."""
    name = ctx.mb_name(base)
    mb = bpy.data.metaballs.new(name)
    mb.resolution = res
    mb.render_resolution = res
    mb.threshold = THRESH
    ob = link(bpy.data.objects.new(name, mb))
    for el in elems:
        stiff = el.get("stiff", 2.0)
        half = el.get("half")
        if "R" in el:
            e = mb.elements.new(type="BALL")
            e.radius = el["R"]
        elif isinstance(half, (int, float)):
            e = mb.elements.new(type="BALL")
            e.radius = half / _k(stiff)
        else:
            e = mb.elements.new(type="ELLIPSOID")
            hm = max(half)
            e.radius = hm / _k(stiff)
            e.size_x, e.size_y, e.size_z = (h / hm for h in half)
            if el.get("rot") is not None:
                e.rotation = el["rot"]
        e.co = el["co"]
        e.stiffness = stiff
        e.use_negative = el.get("neg", False)
    return ob


def to_mesh(ob):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.convert(target="MESH")
    return bpy.context.view_layer.objects.active


def mb_mesh(ctx, base, elems, res, mat, smooth_iter=2, name=None):
    """Metaball set -> mesh (+ Smooth, no Subsurf: §7.5)."""
    o = to_mesh(metaball(ctx, base, elems, res))
    if name:
        o.name = name
    return finish(o, mat, smooth_iter=smooth_iter)


def fib_dirs(n):
    """n near-uniform directions on the sphere (Fibonacci lattice)."""
    ga = math.pi * (3 - math.sqrt(5))
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(1 - z * z)
        a = ga * i
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def sheet_radius(h, s, stiff=2.0):
    """Metaball radius that puts the surface of a dense sheet of balls (spacing s) at height h above the sheet.
    Field of a continuous sheet: F(h) = rho*stiff*pi*R^2*(1-h^2/R^2)^4/4 (verified by the spike's calib to <1 %)."""
    rho = 1 / (s * s)
    lo, hi = 1e-4, 0.9999
    for _ in range(50):
        q = (lo + hi) / 2
        R = h / q
        if rho * stiff * math.pi * R * R * (1 - q * q) ** 4 / 4 > THRESH:
            lo = q
        else:
            hi = q
    return h / ((lo + hi) / 2)


def surface_samples(obj, n, keep, centre=(0, 0, 0), radius=0.5):
    """Ray-cast n uniform directions onto obj from around `centre`; keep(hit, normal, d) filters."""
    out = []
    c = Vector(centre)
    for d in fib_dirs(n):
        hit, nor = ray(obj, c + d * 3, -d)
        if hit is not None and keep(hit, nor, d):
            out.append((hit, nor, d))
    return out, math.sqrt(4 * math.pi * radius ** 2 / n)


def sheet_elems(samples, s, thick_fn, inset=0.02):
    el = []
    for hit, nor, d in samples:
        t = thick_fn(hit, nor)
        if t <= 0.004:
            continue
        R = sheet_radius(t + inset, s)
        el.append(dict(co=hit - nor * inset, R=R, stiff=2.0))
    return el


def slerp(a, b, t):
    a, b = Vector(a).normalized(), Vector(b).normalized()
    om = math.acos(max(-1.0, min(1.0, a.dot(b))))
    if om < 1e-5:
        return a
    return (a * math.sin((1 - t) * om) + b * math.sin(t * om)) / math.sin(om)


def az_el(az, el):
    """Direction from the head centre: azimuth 0 = the face (-Y), +90 = the character's left (+X); elevation up."""
    a, e = math.radians(az), math.radians(el)
    return Vector((math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)))


def frame_quat(tangent, normal):
    """Quaternion mapping local X->binormal, Y->normal, Z->tangent (for ribbon-lock ellipsoids)."""
    n = Vector(normal).normalized()
    t = Vector(tangent)
    t = (t - n * t.dot(n))
    if t.length < 1e-6:
        t = n.orthogonal()
    t.normalize()
    b = n.cross(t).normalized()
    m = Matrix((b, n, t)).transposed()
    return m.to_quaternion()


def ribbon_lock(obj, pts3, w0, w1, th, n=12, lift=0.5, free_tail=0, centre=(0, 0, 0), taper_at=0.7, wmin=0.05):
    """A flattened hair lock. pts3: control entries, each a direction from `centre` (resolved onto obj by a ray and
    lifted by lift*th) or, for the last `free_tail` entries, a free 3D point (a fringe tip hanging off the scalp).
    Each sample is an ellipsoid oriented (across, normal, along): w across the flow (w0 -> w1), th thick."""
    c = Vector(centre)
    ctrl = []
    for i, v in enumerate(pts3):
        if free_tail and i >= len(pts3) - free_tail:
            ctrl.append(("free", Vector(v)))
        else:
            ctrl.append(("dir", Vector(v).normalized()))
    pos = []
    last_nor = Vector((0, -1, 0))
    for i in range(n):
        t = i / (n - 1)
        seg = t * (len(ctrl) - 1)
        k = min(int(seg), len(ctrl) - 2)
        f = seg - k
        (ka, a), (kb, b) = ctrl[k], ctrl[k + 1]
        if ka == "dir" and kb == "dir":
            d = slerp(a, b, f)
            hit, nor = ray(obj, c + d * 3, -d)
            if hit is None:
                continue
            last_nor = nor
            pos.append((hit + nor * th * lift, nor, t))
        else:
            pa = a
            if ka == "dir":
                hit, nor = ray(obj, c + a * 3, -a)
                if hit is None:
                    continue
                pa = hit + nor * th * lift
            pb = b
            if kb == "dir":
                hit, nor = ray(obj, c + b * 3, -b)
                if hit is None:
                    continue
                pb = hit + nor * th * lift
            pos.append((pa * (1 - f) + pb * f, last_nor, t))
    el = []
    for i, (p, nor, t) in enumerate(pos):
        q = pos[min(i + 1, len(pos) - 1)][0] - pos[max(i - 1, 0)][0]
        if q.length < 1e-6:
            continue
        w = w0 + (w1 - w0) * t
        taper = 1 - 0.55 * smoothstep(taper_at, 1.0, t)
        el.append(dict(co=p, half=(w * taper, th * (0.6 + 0.4 * taper), max(w, wmin) * 1.1),
                       stiff=2.4, rot=frame_quat(q, nor)))
    return el


# ------------------------------------------------------------------ body geometry
def superellipse_ring(bm, z, hx, hy, n, yoff, seg=40, xoff=0.0):
    ring = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        c, s = math.cos(a), math.sin(a)
        x = hx * math.copysign(abs(c) ** (2 / n), c) + xoff
        y = hy * math.copysign(abs(s) ** (2 / n), s) + yoff
        ring.append(bm.verts.new((x, y, z)))
    return ring


def loft(name, rings_spec, seg=40, cap_top=False, cap_bottom=True):
    """rings_spec: (z, half width, half depth, superellipse exponent, y offset)."""
    bm = bmesh.new()
    rings = [superellipse_ring(bm, *r, seg=seg) for r in rings_spec]
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    if cap_top:
        bm.faces.new(rings[-1][::-1])
    if cap_bottom:
        bm.faces.new(rings[0][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_obj(name, bm)


def ring_at(spec, z):
    """Interpolated ring (half width, half depth, exponent, y offset) of a loft spec at height z."""
    if z <= spec[0][0]:
        return spec[0][1:]
    for a, b in zip(spec, spec[1:]):
        if a[0] <= z <= b[0]:
            f = (z - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * f for i in range(1, 5))
    return spec[-1][1:]


def capsule(name, top, bottom, r_top, r_bot, seg=24, rings=8, cap_rings=6, squash=1.0):
    """A tube with a hemispherical cap at the top (the deltoid of an arm), open at the bottom."""
    top, bottom = Vector(top), Vector(bottom)
    axis = (top - bottom).normalized()
    rot = Vector((0, 0, 1)).rotation_difference(axis).to_matrix()
    bm = bmesh.new()
    rings_v = []
    L = (top - bottom).length
    for i in range(rings + 1):
        t = i / rings
        r = r_bot + (r_top - r_bot) * t
        rings_v.append([bm.verts.new(bottom + rot @ Vector((r * math.cos(2 * math.pi * k / seg),
                                                            r * squash * math.sin(2 * math.pi * k / seg),
                                                            L * t))) for k in range(seg)])
    for j in range(1, cap_rings):
        a = (math.pi / 2) * j / cap_rings
        r = r_top * math.cos(a)
        rings_v.append([bm.verts.new(top + rot @ Vector((r * math.cos(2 * math.pi * k / seg),
                                                         r * squash * math.sin(2 * math.pi * k / seg),
                                                         r_top * math.sin(a)))) for k in range(seg)])
    pole = bm.verts.new(top + rot @ Vector((0, 0, r_top)))
    for r0, r1 in zip(rings_v, rings_v[1:]):
        for k in range(seg):
            m = (k + 1) % seg
            bm.faces.new((r0[k], r0[m], r1[m], r1[k]))
    for k in range(seg):
        bm.faces.new((rings_v[-1][k], rings_v[-1][(k + 1) % seg], pole))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return mesh_obj(name, bm)


def ribbon_mesh(name, pts, width, normals=None, up=(0, -1, 0)):
    """A flat strip along a polyline (width across, in the plane perpendicular to `up` x tangent)."""
    bm = bmesh.new()
    pairs = []
    for i, p in enumerate(pts):
        p = Vector(p)
        t = Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])
        t.normalize()
        n = Vector(normals[i]) if normals else Vector(up)
        side = t.cross(n).normalized() * (width[i] if isinstance(width, (list, tuple)) else width) / 2
        pairs.append((bm.verts.new(p - side), bm.verts.new(p + side)))
    for (a0, b0), (a1, b1) in zip(pairs, pairs[1:]):
        bm.faces.new((a0, b0, b1, a1))
    return mesh_obj(name, bm)


# ------------------------------------------------------------------ BVH helpers (contacts)
def bvh_of(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(obj.evaluated_get(dg), dg)


def eval_verts(obj, world=True, faces=False):
    """Evaluated vertex positions (and, with faces=True, the face centres too: a long cylinder touches a narrow strap
    between its end rings, where it has no vertex)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = obj.matrix_world
    out = [mw @ v.co if world else v.co.copy() for v in me.vertices]
    if faces:
        out += [mw @ f.center if world else f.center.copy() for f in me.polygons]
    ev.to_mesh_clear()
    return out


# ------------------------------------------------------------------ images
def downscale(src, size_w, out):
    """Premultiplied Lanczos downscale of an RGBA PNG to size_w wide (aspect kept); no dark fringes."""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(src).convert("RGBA")).astype(np.float32) / 255.0
    h, w = a.shape[:2]
    size_h = max(1, round(h * size_w / w))
    rgb, al = a[..., :3] * a[..., 3:4], a[..., 3:4]

    def rs(ch):
        return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize((size_w, size_h), Image.LANCZOS))
    r = np.stack([rs(rgb[..., i]) for i in range(3)], -1)
    al2 = np.clip(rs(al[..., 0]), 0, 1)[..., None]
    r = np.where(al2 > 1e-4, r / np.maximum(al2, 1e-4), 0)
    outa = np.concatenate([np.clip(r, 0, 1), al2], -1)
    Image.fromarray((outa * 255 + 0.5).astype(np.uint8), "RGBA").save(out)


def ray_any(objs, origin, direction, dist=10.0):
    """The nearest hit of a ray over several objects: (location, normal, object) or (None, None, None)."""
    best = (None, None, None)
    bd = 1e9
    for o in objs:
        h, n = ray(o, origin, direction, dist)
        if h is not None:
            d = (h - Vector(origin)).length
            if d < bd:
                bd, best = d, (h, n, o)
    return best


def world_dir(ctx, d, head=False):
    """A direction given in world (camera) terms — +X screen right, -Y toward the camera, +Z up — expressed in body
    space (or head space, head=True), so a prop can point 'to the right of the frame' whatever the pose."""
    po = ctx.ch["pose"]
    yaw = po["body"] + (po.get("head", 0.0) if head else 0.0)
    return (Matrix.Rotation(math.radians(-yaw), 3, "Z") @ Vector(d)).normalized()
