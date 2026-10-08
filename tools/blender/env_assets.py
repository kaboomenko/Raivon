"""Environment props for the medieval map: trees, rocks, mountains, farm, windmill, mine (+ bush, flowers).

Overwrites the simple placeholder props that export_assets.py makes (same file names, same footprints),
so the map picks them up without code changes:
  tree_pine.glb  tree_round.glb  rock.glb  mountain.glb  wheat_field.glb  windmill.glb  mine.glb
  bush.glb  flowers.glb   (new decoration, not used by the game yet)

Run:   python3 tools/blender/env_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/env_assets.py game/assets/models --sheet OUT.png
       (props on grass hex tiles, arranged the way map_view.gd scatters them, ~45° ortho camera)

Conventions as in evolution_assets.py: Z up, base on Z=0, origin = hex centre (1 hex = flat-top hexagon of
circumradius 1.0), front faces −Y (Godot +Z, towards the camera). Procedural colours are painted in model
space (height / facing gradients = cheap fake light, moss, snow) and baked into one 512 px texture per
asset; emissive materials (mine lantern) stay separate so they glow in Godot.

windmill.glb has two nodes: the tower and a separate node named "sails" whose origin is the hub; spin it
about its local Z axis in Godot (the hub axis points to the model's front, Godot +Z).
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils import noise as mnoise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
import evolution_assets as ev  # noqa: E402
from evolution_assets import bx, cy, shade, tex, flat, glow  # noqa: E402

WOOD = "#7d5130"
WOOD_L = "#a8743f"
WOOD_D = "#5a3a22"
BARK = "#6a4327"
ROOF_BLUE = "#2d55b8"
STONE = "#cbc3b4"
STONE_D = "#8f877b"


# ------------------------------------------------------------------ painted materials (baked)


class Paint:
    """Tiny node-graph builder: colour from model-space position / normal, ends in Principled Base Color."""

    def __init__(self, name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        self.m, self.nt = m, m.node_tree
        self.L = self.nt.links
        self.bsdf = self.nt.nodes["Principled BSDF"]
        geo = self.nt.nodes.new("ShaderNodeNewGeometry")
        self.pos = geo.outputs["Position"]
        sp = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.L.new(self.pos, sp.inputs[0])
        sn = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.L.new(geo.outputs["Normal"], sn.inputs[0])
        self.x, self.y, self.z = sp.outputs[0], sp.outputs[1], sp.outputs[2]
        self.nz = sn.outputs[2]

    def _in(self, sock, v):
        if isinstance(v, (int, float)):
            sock.default_value = v
        elif isinstance(v, str):
            sock.default_value = (*kit.srgb(v), 1)
        else:
            self.L.new(v, sock)

    def math(self, op, a, b=None):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        self._in(n.inputs[0], a)
        if b is not None:
            self._in(n.inputs[1], b)
        return n.outputs[0]

    def step(self, v, lo, hi):
        """Smoothstep 0..1 of v between lo and hi (hi < lo inverts)."""
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        self._in(n.inputs["Value"], v)
        if hi < lo:
            lo, hi = hi, lo
            n.inputs["To Min"].default_value, n.inputs["To Max"].default_value = 1.0, 0.0
        n.inputs["From Min"].default_value = lo
        n.inputs["From Max"].default_value = hi
        return n.outputs["Result"]

    def noise(self, scale, detail=3.0, stretch=None):
        n = self.nt.nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        vec = self.pos
        if stretch:
            vm = self.nt.nodes.new("ShaderNodeVectorMath")
            vm.operation = "MULTIPLY"
            self.L.new(self.pos, vm.inputs[0])
            vm.inputs[1].default_value = stretch
            vec = vm.outputs[0]
        self.L.new(vec, n.inputs["Vector"])
        return n.outputs["Fac"]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        self._in(ev._sock(n, "Factor_Float"), fac)
        self._in(ev._sock(n, "A_Color"), a)
        self._in(ev._sock(n, "B_Color"), b)
        return ev._sock(n, "Result_Color", True)

    def done(self, col, rough=0.85):
        self._in(self.bsdf.inputs["Base Color"], col)
        self.bsdf.inputs["Roughness"].default_value = rough
        return self.m


_PAINT = {}


def cached(key, fn):
    if key not in _PAINT:
        _PAINT[key] = fn()
    return _PAINT[key]


def foliage(dark, mid, light, z0=0.0, z1=0.6, hl=0.75, scale=11.0):
    """Leaves: mottled dark/mid, sun-lit light tops, dark undersides, darker towards the ground."""
    def build():
        p = Paint("foliage")
        n = p.noise(scale, 4.0)
        col = p.mix(p.step(n, 0.3, 0.6), dark, mid)
        top = p.math("MULTIPLY", p.step(p.nz, 0.35, 0.9), p.step(p.noise(scale * 0.6, 2.0), 0.3, 0.55))
        col = p.mix(p.math("MULTIPLY", top, hl), col, light)
        col = p.mix(p.step(p.nz, -0.05, -0.6), col, shade(dark, 0.62))
        col = p.mix(p.math("MULTIPLY", p.step(p.z, z1, z0), 0.45), col, shade(dark, 0.7))
        return p.done(col, 0.9)
    return cached(("foliage", dark, mid, light, z0, z1, hl, scale), build)


def rock_paint(c1, c2, moss=("#4f7f2c", "#77a83a"), moss_at=0.62, scale=7.0):
    """Faceted stone: mottled grey, fine speckles, moss on up-facing faces."""
    def build():
        p = Paint("rockpaint")
        col = p.mix(p.step(p.noise(scale, 4.0), 0.3, 0.7), c1, c2)
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(scale * 5, 2.0), 0.55, 0.75), 0.35), col, shade(c1, 0.7))
        col = p.mix(p.step(p.nz, 0.1, -0.5), col, shade(c1, 0.72))
        if moss:
            mf = p.math("ADD", p.nz, p.math("MULTIPLY", p.math("SUBTRACT", p.noise(6.0, 3.0), 0.5), 0.7))
            mcol = p.mix(p.step(p.noise(14.0), 0.35, 0.65), moss[0], moss[1])
            col = p.mix(p.step(mf, moss_at, moss_at + 0.12), col, mcol)
        return p.done(col, 0.9)
    return cached(("rock", c1, c2, moss, moss_at, scale), build)


def mountain_paint(grass_line=0.13, snow_line=0.78):
    """Grassy foot → scree → stratified rock (darker on steep faces) → snow on high / flat faces."""
    def build():
        p = Paint("mountain")
        jit = p.math("MULTIPLY", p.math("SUBTRACT", p.noise(5.0, 3.0), 0.5), 0.16)
        zz = p.math("ADD", p.z, jit)
        strata = p.noise(2.2, 3.0, stretch=(1.0, 1.0, 9.0))
        rock = p.mix(p.step(strata, 0.35, 0.68), "#7b746c", "#a39a8d")
        rock = p.mix(p.math("MULTIPLY", p.step(p.noise(30.0, 2.0), 0.55, 0.75), 0.3), rock, "#5e5852")
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.75, 0.25), 0.55), rock, "#5a544e")
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.55, 0.9), 0.5), rock, "#b8ad9c")
        scree = p.mix(p.step(p.noise(18.0), 0.4, 0.6), "#8f7f62", "#a7966f")
        col = p.mix(p.step(zz, grass_line + 0.16, grass_line + 0.04), rock, scree)
        grass = p.mix(p.step(p.noise(9.0, 3.0), 0.35, 0.65), "#3f5f2a", "#526f33")  # ≈ map plain grass (muted, 2026-10-08)
        col = p.mix(p.step(zz, grass_line + 0.03, grass_line - 0.03), col, grass)
        sf = p.math("ADD", zz, p.math("MULTIPLY", p.math("SUBTRACT", p.nz, 0.55), 0.35))
        snow = p.mix(p.step(p.nz, 0.2, 0.8), "#c9d6e6", "#fbfdff")
        col = p.mix(p.step(sf, snow_line, snow_line + 0.05), col, snow)
        return p.done(col, 0.9)
    return cached(("mountain", grass_line, snow_line), build)


def zgrad(c0, c1, c2, z0, z1, scale=20.0, rough=0.8):
    """Vertical gradient c0 (z0) → c1 → c2 (z1) with a little noise (wheat, grass tufts)."""
    def build():
        p = Paint("zgrad")
        zm = (z0 + z1) / 2
        col = p.mix(p.step(p.z, z0, zm), c0, c1)
        col = p.mix(p.step(p.z, zm, z1), col, c2)
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(scale, 2.0), 0.5, 0.75), 0.3), col, shade(c0, 0.85))
        return p.done(col, rough)
    return cached(("zgrad", c0, c1, c2, z0, z1, scale), build)


def furrows(c_dark, c_light, period=0.13, axis=0):
    """Ploughed soil: stripes along Y (rows) with noise."""
    def build():
        p = Paint("soil")
        u = p.x if axis == 0 else p.y
        s = p.math("SINE", p.math("MULTIPLY", u, math.tau / period))
        col = p.mix(p.step(s, -0.4, 0.6), c_dark, c_light)
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(16.0), 0.45, 0.7), 0.4), col, shade(c_dark, 0.8))
        return p.done(col, 0.95)
    return cached(("furrows", c_dark, c_light, period, axis), build)


# ------------------------------------------------------------------ geometry helpers


def poly(verts, faces, mats, face_mat=None, flat_shade=True, name="poly"):
    """Mesh object from verts/faces (faces wound CCW seen from outside); one material index per face."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    for m_ in mats:
        o.data.materials.append(m_)
    if face_mat:
        for p, i in zip(o.data.polygons, face_mat):
            p.material_index = i
    for p in o.data.polygons:
        p.use_smooth = not flat_shade
    if flat_shade:
        o["flat"] = True
    return o


def hull(points, mt, flat_shade=True):
    """Convex hull of points → faceted rock."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("hull")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("hull", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mt)
    for p in o.data.polygons:
        p.use_smooth = not flat_shade
    if flat_shade:
        o["flat"] = True
    return o


def boulder(cx, cy_, rx, ry, rz, mt, seed, n=16, z0=-0.02, lean=0.0):
    """Chunky faceted stone sitting on the ground (flat-ish bottom just below z0)."""
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        u = rnd.uniform(0, math.tau)
        v = rnd.uniform(0.05, 1.0) ** 0.8  # bias towards the top half
        ring = math.sqrt(max(0.0, 1 - v * v))
        k = rnd.uniform(0.8, 1.08)
        pts.append((cx + rx * ring * math.cos(u) * k + lean * v * rz, cy_ + ry * ring * math.sin(u) * k, z0 + rz * v * k))
    for i in range(6):  # foot ring
        u = i / 6 * math.tau + rnd.uniform(-0.3, 0.3)
        pts.append((cx + rx * 0.95 * math.cos(u), cy_ + ry * 0.95 * math.sin(u), z0 - 0.02))
    return hull(pts, mt)


def blob(r, loc, mt, scale=(1, 1, 1), sub=2, seed=0, jitter=0.12):
    """Lumpy smooth sphere (foliage clump)."""
    o = ev.ico(r, (0, 0, 0), mt, scale, sub)
    rnd = random.Random(seed)
    for v in o.data.vertices:
        d = v.co.normalized()
        k = 1 + jitter * mnoise.noise(d * 2.3 + Vector((seed * 1.7, seed * 0.3, 0))) + rnd.uniform(-0.02, 0.02)
        v.co = v.co * k
    o.location = loc
    return o


def star_tier(cx, cy_, z0, z1, r, n, rot, mt, mt_under, droop=0.035, inner=0.8, seed=0):
    """One pine tier: star-shaped skirt (drooping branch tips), apex at z1, concave dark underside."""
    rnd = random.Random(seed)
    verts = [(cx, cy_, z1)]
    for k in range(2 * n):
        a = rot + math.pi * k / n
        if k % 2 == 0:
            rr = r * rnd.uniform(0.9, 1.08)
            z = z0 - droop * rnd.uniform(0.7, 1.2)
        else:
            rr = r * inner
            z = z0 + (z1 - z0) * 0.12
        verts.append((cx + rr * math.cos(a), cy_ + rr * math.sin(a), z))
    verts.append((cx, cy_, z0 + (z1 - z0) * 0.22))
    c = len(verts) - 1
    faces, fm = [], []
    for k in range(2 * n):
        a, b = 1 + k, 1 + (k + 1) % (2 * n)
        faces.append((0, a, b))
        fm.append(0)
        faces.append((c, b, a))
        fm.append(1)
    return poly(verts, faces, [mt, mt_under], fm, flat_shade=False, name="tier")


def pine_tree(x=0.0, y=0.0, s=1.0, n=9, tiers=4, seed=0, mats=None):
    """Layered stylised pine, ~0.62·s tall."""
    rnd = random.Random(seed)
    if mats is None:
        mats = pine_mats()
    ma, mb, mu, bark = mats
    cy(0.032 * s, 0.17 * s, (x, y, 0.085 * s), bark, 6, 0.0, r2=0.024 * s)
    radii = [0.25, 0.205, 0.16, 0.11, 0.08][:tiers]
    zstep = 0.47 / tiers
    for i, r in enumerate(radii):
        z0 = (0.11 + i * zstep) * s
        z1 = z0 + (0.25 if i < tiers - 1 else 0.24) * s * (1.0 if tiers >= 4 else 1.15)
        ox, oy = rnd.uniform(-0.012, 0.012) * s, rnd.uniform(-0.012, 0.012) * s
        star_tier(x + ox, y + oy, z0, z1, r * s, n, rnd.uniform(0, 1), ma if i % 2 == 0 else mb, mu,
                  droop=0.028 * s, seed=seed * 10 + i)


def pine_mats():
    return (foliage("#1a3f22", "#29592b", "#5a8236", 0.1, 0.62, 0.45, 7.0),
            foliage("#1d4425", "#2d5f2e", "#62893a", 0.1, 0.62, 0.45, 7.0),
            flat("pine_under", "#25502b", 0.9),
            tex("wood", BARK))


def round_tree(x=0.0, y=0.0, s=1.0, seed=0, crowns=None, sub=2):
    leaf = foliage("#2a511b", "#416f27", "#6c8f33", 0.15, 0.55, 0.55, 9.0)
    bark = tex("wood", BARK)
    cy(0.036 * s, 0.24 * s, (x, y, 0.12 * s), bark, 6, 0.0, r2=0.026 * s)
    ev.rod((x, y, 0.17 * s), (x + 0.075 * s, y - 0.03 * s, 0.27 * s), 0.013 * s, bark, n=5)
    ev.rod((x, y, 0.19 * s), (x - 0.07 * s, y + 0.03 * s, 0.28 * s), 0.012 * s, bark, n=5)
    crowns = crowns or [(0.0, 0.0, 0.34, 0.15), (0.09, -0.06, 0.29, 0.11), (-0.09, 0.05, 0.31, 0.115),
                        (0.03, 0.06, 0.44, 0.11), (-0.02, -0.08, 0.40, 0.09)]
    for i, (cx, cy_, cz, r) in enumerate(crowns):
        blob(r * s, (x + cx * s, y + cy_ * s, cz * s), leaf, (1, 1, 0.88), sub if r >= 0.1 else 1, seed * 7 + i)


# ------------------------------------------------------------------ assets


def tree_pine():
    pine_tree(seed=3)


def tree_round():
    round_tree(seed=2)


def bush():
    leaf = foliage("#2a521c", "#427228", "#6a9034", 0.0, 0.16, 0.55, 14.0)
    for i, (x, y, z, r) in enumerate([(0, 0, 0.06, 0.085), (0.07, -0.03, 0.045, 0.06), (-0.065, 0.02, 0.045, 0.065),
                                      (0.01, 0.04, 0.1, 0.055)]):
        blob(r, (x, y, z), leaf, (1, 1, 0.85), 1, 40 + i, 0.15)
    berry = flat("berry", "#d8344a", 0.6)
    for x, y, z in [(0.03, -0.075, 0.08), (-0.05, -0.05, 0.07), (0.09, -0.06, 0.05)]:
        ev.ico(0.012, (x, y, z), berry, (1, 1, 1), 1)


def flowers():
    grass = zgrad("#3f7d24", "#5fa832", "#9ad04e", 0.0, 0.07)
    rnd = random.Random(8)
    for i in range(5):
        a = i / 5 * math.tau + rnd.uniform(-0.4, 0.4)
        r = rnd.uniform(0.03, 0.11)
        x, y = math.cos(a) * r, math.sin(a) * r
        for j in range(3):  # 3 blades per tuft
            b = rnd.uniform(0, math.tau)
            ev.rod((x, y, 0.0), (x + 0.025 * math.cos(b), y + 0.025 * math.sin(b), rnd.uniform(0.05, 0.08)), 0.008, grass,
                   r2=0.0, n=3)
    cols = ["#ffffff", "#ffd23f", "#e8508a", "#ffffff", "#b07cff", "#ffd23f", "#ff7a3d"]
    centre = flat("flower_c", "#f2b51e", 0.6)
    for i, c in enumerate(cols):
        a = i / len(cols) * math.tau + rnd.uniform(-0.3, 0.3)
        r = rnd.uniform(0.02, 0.12)
        x, y, z = math.cos(a) * r, math.sin(a) * r, rnd.uniform(0.04, 0.07)
        ev.rod((x, y, 0), (x, y, z), 0.005, grass, r2=0.0, n=3)
        ev.cn(0.02, 0.014, (x, y, z), flat("petal" + c, c, 0.6), 5, rot=(math.pi, 0, rnd.uniform(0, 1)))
        if c != "#ffd23f":
            ev.cn(0.007, 0.006, (x, y, z + 0.007), centre, 4)


def rock():
    mt = rock_paint("#8a8580", "#aaa59c")
    boulder(0.0, 0.01, 0.15, 0.12, 0.2, mt, 11, 18, lean=0.08)
    boulder(0.14, -0.07, 0.085, 0.075, 0.11, mt, 12, 14)
    boulder(-0.12, 0.08, 0.07, 0.065, 0.085, mt, 13, 12)
    boulder(0.06, -0.15, 0.04, 0.035, 0.04, mt, 14, 10)
    boulder(-0.1, -0.09, 0.032, 0.03, 0.03, mt, 15, 9)


def crag():
    """Hills hex (the rocky outcrops of the reference frames): a grey stone ridge of stacked faceted blocks with
    ledges, a scree apron, moss on the tops and a few pines clinging to it."""
    mt = rock_paint("#7f7a73", "#a29c92", moss_at=0.7)
    dark = rock_paint("#6a655f", "#8a847b", moss=None)
    # the main ridge: three stepped masses rising toward the back
    boulder(-0.12, 0.18, 0.3, 0.2, 0.42, mt, 41, 22, lean=0.06)
    boulder(0.2, 0.12, 0.24, 0.18, 0.32, mt, 42, 20, lean=-0.05)
    boulder(-0.32, -0.02, 0.2, 0.16, 0.24, dark, 43, 18)
    boulder(0.36, -0.12, 0.16, 0.13, 0.17, mt, 44, 16)
    # ledges and broken blocks in front
    boulder(0.02, -0.12, 0.17, 0.12, 0.13, dark, 45, 16)
    boulder(-0.18, -0.3, 0.1, 0.08, 0.08, mt, 46, 12)
    boulder(0.24, -0.34, 0.08, 0.07, 0.06, mt, 47, 10)
    # scree: little stones spilling down the front
    rnd = random.Random(48)
    for k in range(14):
        x, y = rnd.uniform(-0.45, 0.45), rnd.uniform(-0.48, -0.15)
        r = rnd.uniform(0.018, 0.04)
        boulder(x, y, r, r * 0.9, r * 0.8, dark if k % 3 else mt, 60 + k, 8)
    pm = pine_mats()
    for (x, y, sc) in ((0.42, 0.3, 0.75), (-0.45, 0.32, 0.85), (0.05, 0.46, 0.7), (-0.5, -0.25, 0.6)):
        pine_tree(x, y, sc, seed=int(x * 100 + y * 10), mats=pm)


def _mountain_height(x, y, k=0.84):
    x, y = x / k, y / k
    peaks = [(-0.08, 0.12, 1.38, 0.72, 0.0), (0.37, -0.12, 0.98, 0.55, 1.7), (-0.42, -0.24, 0.8, 0.5, 3.1),
             (0.2, 0.46, 0.78, 0.45, 4.4)]
    hs = []
    for px, py, H, R, ph in peaks:
        dx, dy = x - px, y - py
        d = math.hypot(dx, dy)
        th = math.atan2(dy, dx)
        Rm = R * (1 + 0.2 * math.sin(3 * th + ph) + 0.08 * math.sin(7 * th + 2 * ph))
        t = max(0.0, 1 - d / Rm)
        hs.append(H * t ** 1.3)
    hs.sort(reverse=True)
    h = hs[0] + 0.18 * hs[1]
    v = Vector((x * 3.5, y * 3.5, 0.7))
    h += 0.07 * mnoise.noise(v) * (0.35 + h) + 0.045 * abs(mnoise.noise(v * 2.7))
    r = math.hypot(x, y)
    apron = 0.17 * max(0.0, 1 - r / 0.95) ** 1.1
    h = max(h, apron)
    h -= 0.03 * min(1.0, max(0.0, (r - 0.78) / 0.17))
    return h


def mountain():
    mt = mountain_paint()
    rings, segs, R = 17, 34, 0.8
    rnd = random.Random(21)
    verts = [(0.0, 0.0, 0.0)]
    for i in range(1, rings + 1):
        for j in range(segs):
            a = (j + (0.5 if i % 2 else 0.0)) / segs * math.tau
            r = R * i / rings
            if i < rings:
                r += rnd.uniform(-0.25, 0.25) * R / rings
                a += rnd.uniform(-0.2, 0.2) / segs * math.tau
            else:
                r -= rnd.uniform(0.0, 0.03)
            verts.append([r * math.cos(a), r * math.sin(a), 0.0])
    verts = [(x, y, _mountain_height(x, y)) for x, y, _ in verts]

    def vid(i, j):
        return 1 + (i - 1) * segs + (j % segs)

    faces = []
    for j in range(segs):
        faces.append((0, vid(1, j), vid(1, j + 1)))
    for i in range(1, rings):
        for j in range(segs):
            a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
            if i % 2:  # inner ring offset by half a segment → alternate diagonals for even triangles
                faces += [(a, b, c), (a, c, d)]
            else:
                faces += [(a, b, d), (b, c, d)]
    # short skirt below the rim so the foot never floats
    base = len(verts)
    for j in range(segs):
        vx, vy, _ = verts[vid(rings, j)]
        verts.append((vx * 0.98, vy * 0.98, -0.12))
    for j in range(segs):
        a, b = vid(rings, j), vid(rings, j + 1)
        faces.append((a, base + j, base + (j + 1) % segs, b))
    poly(verts, faces, [mt])
    # boulders and pines on the grassy foot
    rk = rock_paint("#857f77", "#a39b8f", moss_at=0.55)
    for k, (a, r, s) in enumerate([(4.4, 0.68, 0.06), (1.2, 0.7, 0.05), (2.6, 0.66, 0.055)]):
        x, y = r * math.cos(a), r * math.sin(a)
        boulder(x, y, s * 1.2, s, s * 1.1, rk, 70 + k, 12, z0=_mountain_height(x, y) - 0.03)
    mats = pine_mats()
    placed = []
    cand = [(a, r) for a in [i * 0.37 for i in range(17)] for r in (0.6, 0.68)]
    random.Random(5).shuffle(cand)
    for a, r in cand:
        x, y = r * math.cos(a), r * math.sin(a)
        h = _mountain_height(x, y)
        if h > 0.16 or any(math.dist((x, y), p) < 0.2 for p in placed):
            continue
        placed.append((x, y))
        build = (lambda s_, sd: (lambda: pine_tree(0, 0, s_, n=6, tiers=3, seed=sd, mats=mats)))(random.Random(len(placed)).uniform(0.38, 0.5), 30 + len(placed))
        ev.build_at(build, x, y, 0.0, 1.0, z=h - 0.02)
        if len(placed) >= 7:
            break


def wheat_paint():
    """Golden crop: darker stalks at the base, bright ears on top, fine vertical streaks."""
    def build():
        p = Paint("wheat")
        col = p.mix(p.step(p.z, 0.04, 0.1), "#7a4a12", "#d08a12")
        col = p.mix(p.step(p.z, 0.1, 0.16), col, "#f2b828")
        streak = p.step(p.noise(5.0, 2.0, stretch=(14.0, 14.0, 1.2)), 0.5, 0.72)
        col = p.mix(p.math("MULTIPLY", streak, 0.5), col, "#a86410")
        return p.done(col, 0.8)
    return cached(("wheat",), build)


def wheat_row(x, y0, y1, mt, rnd, step=0.04):
    """A continuous row of standing wheat along Y: rippled ridge-roof profile, wider at the top."""
    n = max(2, round((y1 - y0) / step))
    prof = []
    for j in range(n + 1):
        y = y0 + (y1 - y0) * j / n
        h = rnd.uniform(0.11, 0.135) * (0.7 if j % 2 else 1.0)
        w = 0.04 if j % 2 else 0.052
        jx = rnd.uniform(-0.01, 0.01)
        zb = 0.035
        prof.append([(x - 0.024, y, zb), (x - w, y, zb + h * 0.72), (x + jx, y, zb + h),
                     (x + w, y, zb + h * 0.72), (x + 0.024, y, zb)])
    verts = [v for ring in prof for v in ring]
    faces = []
    for j in range(n):
        for k in range(4):
            a, b = j * 5 + k, j * 5 + k + 1
            faces.append((a, b, b + 5, a + 5))
    faces.append(tuple(range(4, -1, -1)))
    faces.append(tuple(n * 5 + k for k in range(5)))
    return poly(verts, faces, [mt], flat_shade=False, name="wheat_row")  # open bottom, wound outwards


def wheat_field():
    soil = furrows("#5e3d22", "#80552f", period=0.12)
    box = kit.box
    box("soil", (0.9, 0.7, 0.05), (0, 0, 0.0), soil, 0.012)
    ridge = tex("plaster", "#6b4628")
    wheat = wheat_paint()
    rnd = random.Random(5)
    xs = [-0.36 + i * 0.12 for i in range(7)]
    for i, x in enumerate(xs):
        # ridge (triangular prism along Y)
        ev.extrude([(-0.045, 0.0), (0.045, 0.0), (0.0, 0.03)], -0.31, 0.31, ridge, (x, 0, 0.025), (math.pi / 2, 0, 0))
        y0 = -0.13 if i == 6 else -0.3  # a bare corner for the bale
        wheat_row(x, y0, 0.3, wheat, rnd)
    # hay bale on the bare corner
    hay = zgrad("#b98f3a", "#dcb455", "#ecd07a", 0.03, 0.12, 30.0)
    cy(0.05, 0.08, (0.36, -0.22, 0.075), hay, 10, 0.0, rot=(0, math.pi / 2, 0.3))
    # a low dry-stone wall round the field (reference frame 4: fields in stone enclosures), a gap at the front
    post = tex("wood", WOOD)
    st = ev.stone("#b9b4aa", 1.2)
    cap = ev.stone("#9f998e", 1.2)
    for (x0, y0, x1, y1) in ((-0.47, 0.39, 0.49, 0.39), (0.49, 0.39, 0.49, -0.37), (-0.47, -0.37, -0.47, 0.39),
                             (0.49, -0.37, 0.08, -0.37), (-0.12, -0.37, -0.47, -0.37)):
        ln = math.dist((x0, y0), (x1, y1))
        ang = math.atan2(y1 - y0, x1 - x0)
        bx((ln - 0.06, 0.05, 0.07), ((x0 + x1) / 2, (y0 + y1) / 2, 0.035), st, ang, 0.008)
        bx((ln - 0.06, 0.06, 0.016), ((x0 + x1) / 2, (y0 + y1) / 2, 0.075), cap, ang, 0.004)
    for (x, y) in ((-0.47, 0.39), (0.49, 0.39), (0.49, -0.37), (-0.47, -0.37)):  # corner piers hide the joints
        bx((0.08, 0.08, 0.1), (x, y, 0.05), cap, 0.0, 0.008)
    for x in (-0.12, 0.08):  # gateposts
        bx((0.06, 0.06, 0.11), (x, -0.37, 0.055), cap, 0.0, 0.008)
    # scarecrow
    sx, sy = -0.12, 0.04
    cy(0.012, 0.32, (sx, sy, 0.16), post, 5)
    ev.beam((sx - 0.1, sy, 0.24), (sx + 0.1, sy, 0.24), 0.014, post)
    ev.taper_box((0.1, 0.045, 0.11), (sx, sy, 0.215), flat("shirt", "#b8402f", 0.9), top=(0.75, 1.0))
    for d in (-1, 1):
        ev.beam((sx + d * 0.035, sy, 0.25), (sx + d * 0.1, sy, 0.235), 0.032, flat("shirt", "#b8402f", 0.9))
        ev.ico(0.016, (sx + d * 0.11, sy, 0.234), wheat, (1, 1, 1), 1)
    ev.ico(0.034, (sx, sy, 0.31), flat("sack", "#d8c08c", 0.9), (1, 1, 1.05), 1)
    cy(0.06, 0.008, (sx, sy, 0.335), hay, 10)
    cy(0.03, 0.05, (sx, sy, 0.36), hay, 8, 0.0, r2=0.018)


def crop_field():
    """A modern field (DL6–7 countryside): long rows of green crops and a ripe golden strip on ploughed soil, a wire
    fence on posts, a red tractor at the headland and round bales — the industrial cousin of the walled wheat plot."""
    soil = furrows("#5a3b21", "#7a5230", period=0.1)
    box = kit.box
    box("soil", (0.9, 0.7, 0.05), (0, 0, 0.0), soil, 0.012)
    green = foliage("#3d6a22", "#558a2c", "#7aa83a", 0.02, 0.1, 0.55, 18.0)
    wheat = wheat_paint()
    rnd = random.Random(9)
    for i in range(8):  # crop rows; the two near rows ripe
        x = -0.38 + i * 0.105
        if i >= 6:
            wheat_row(x, -0.3, 0.3, wheat, rnd)
        else:
            bx((0.06, 0.6, 0.05), (x, 0.0, 0.05), green, 0.0, 0.012)
    post = tex("wood", WOOD)
    wire = flat("wire", "#9aa0a6", 0.5)
    for (x0, y0, x1, y1) in ((-0.46, 0.37, 0.46, 0.37), (0.46, 0.37, 0.46, -0.35), (-0.46, -0.35, -0.46, 0.37)):
        ln = math.dist((x0, y0), (x1, y1))
        n = max(2, int(ln / 0.15))
        for k in range(n + 1):
            cy(0.006, 0.08, (x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, 0.04), post, 5)
        for z in (0.05, 0.075):
            ev.beam((x0, y0, z), (x1, y1, z), 0.0025, wire)
    # a red tractor at the near headland
    red = flat("tractor", "#c23a2b", 0.5)
    dk = flat("tyre", "#1f1f21", 0.9)
    tx, ty = 0.18, -0.4
    bx((0.12, 0.06, 0.05), (tx, ty, 0.06), red, 0.0, 0.008)
    bx((0.05, 0.055, 0.06), (tx - 0.03, ty, 0.115), flat("cab", "#2c3a48", 0.3), 0.0, 0.006)
    bx((0.06, 0.06, 0.008), (tx - 0.03, ty, 0.15), red, 0.0, 0.003)
    for sx, r in ((-0.04, 0.032), (0.045, 0.02)):
        for sy in (-1, 1):
            cy(r, 0.016, (tx + sx, ty + sy * 0.038, r), dk, 10, rot=(math.pi / 2, 0, 0))
    cy(0.006, 0.04, (tx + 0.035, ty + 0.012, 0.1), dk, 5)  # exhaust
    hay = zgrad("#b98f3a", "#dcb455", "#ecd07a", 0.03, 0.12, 30.0)
    for (x, y) in ((-0.3, -0.42), (-0.2, -0.43)):
        cy(0.04, 0.055, (x, y, 0.04), hay, 10, 0.0, rot=(math.pi / 2, 0, 0.2))


def windmill():
    st = ev.stone(STONE, 1.1)
    std = ev.stone(STONE_D, 1.1)
    wood = tex("wood", WOOD)
    woodd = tex("wood", WOOD_D)
    roof = tex("roof", ROOF_BLUE)
    cy(0.2, 0.07, (0, 0, 0.035), std, 8, 0.01)
    cy(0.175, 0.5, (0, 0, 0.32), st, 8, 0.008, r2=0.135)
    cy(0.152, 0.045, (0, 0, 0.585), woodd, 8, 0.006)
    # gallery: little plank ring + posts
    cy(0.21, 0.02, (0, 0, 0.36), tex("wood", WOOD_L), 8, 0.004)
    for k in range(8):
        a = (k + 0.5) / 8 * math.tau
        ev.beam((0.2 * math.cos(a), 0.2 * math.sin(a), 0.37), (0.2 * math.cos(a), 0.2 * math.sin(a), 0.43), 0.012, woodd)
    cy(0.205, 0.012, (0, 0, 0.43), woodd, 8, 0.0)
    # cap
    cn = ev.cn(0.19, 0.24, (0, 0, 0.6 + 0.12), roof, 8)
    cn.rotation_euler.z = math.pi / 8
    ev.ico(0.022, (0, 0, 0.85), flat("gold", "#ffc933", 0.4), (1, 1, 1), 1)
    # door + windows (front −Y)
    bx((0.085, 0.03, 0.14), (0, -0.172, 0.14), tex("wood", "#4a2f19"), 0, 0.006)
    bx((0.105, 0.025, 0.02), (0, -0.168, 0.215), std, 0, 0.004)
    win = flat("win_dark", "#2a1d12", 0.9)
    for a, z in ((math.pi * 0.25, 0.48), (math.pi * 0.75, 0.3), (-math.pi * 0.5 + 0.9, 0.5)):
        r = 0.15 if z > 0.4 else 0.163
        bx((0.035, 0.02, 0.05), (r * math.cos(a), r * math.sin(a), z), win, a + math.pi / 2, 0.003)
    # flour sacks + a crate by the door
    sack = tex("plaster", "#e6dcc4")
    ev.ico(0.04, (0.12, -0.2, 0.035), sack, (1, 0.85, 0.9), 1)
    ev.ico(0.035, (0.17, -0.15, 0.03), sack, (1, 0.85, 0.9), 1)
    bx((0.07, 0.07, 0.065), (-0.14, -0.18, 0.0325), tex("wood", WOOD_L), 0.3, 0.006)
    # hub + sails (separate node)
    hub_y, hub_z = -0.2, 0.62
    cy(0.035, 0.1, (0, -0.17, hub_z), wood, 8, 0.0, rot=(math.pi / 2, 0, 0))
    sails = []
    sails.append(cy(0.045, 0.04, (0, hub_y - 0.02, hub_z), woodd, 8, 0.0, rot=(math.pi / 2, 0, 0)))
    cloth = tex("plaster", "#f1e7d0")
    for i in range(4):
        a = i * math.pi / 2 + 0.35

        def P(rad, off=0.0, dy=0.0):  # point along the arm (rad from hub) shifted sideways by off
            return (math.sin(a) * rad + math.cos(a) * off, hub_y - 0.03 + dy, hub_z + math.cos(a) * rad - math.sin(a) * off)

        sails.append(ev.beam(P(0.02), P(0.4), 0.018, wood))
        o = bx((0.1, 0.008, 0.29), P(0.245, 0.058, 0.004), cloth, 0, 0.0)
        o.rotation_euler.y = a
        sails.append(o)
        sails.append(ev.beam(P(0.1, 0.112, -0.004), P(0.395, 0.112, -0.004), 0.01, woodd))
        for rad in (0.12, 0.2, 0.28, 0.37):
            sails.append(ev.beam(P(rad, -0.005, -0.006), P(rad, 0.115, -0.006), 0.008, woodd))
    for o in sails:
        o["sails"] = True
    return (0.0, hub_y, hub_z)


def mine():
    rk = rock_paint("#7f786e", "#a0978a", moss_at=0.82)
    dirt = ev.pad(0.6, ev.stone("#9a8f7f", 1.4), 0.012, 14, 0.12, 4, 1.0, 0.85)  # a flagged yard (reference frame 4)
    dirt.location.y = -0.12
    # the quarried cliff of reference frame 4: three stepped tiers of cut grey blocks, highest at the back, with
    # ledges a man could stand on — not a smooth mossy boulder
    rnd = random.Random(9)
    cut = rock_paint("#7d776e", "#a39b8f", moss=None, scale=9.0)
    cut_d = rock_paint("#6a645c", "#8a8278", moss=None, scale=9.0)
    for t, (y0, y1, zmax, xr) in enumerate(((0.0, 0.2, 0.3, 0.56), (0.17, 0.36, 0.48, 0.5), (0.33, 0.5, 0.66, 0.38))):
        x = -xr
        while x < xr - 0.04:
            w = rnd.uniform(0.11, 0.19)
            w = min(w, xr - x)
            h = zmax * rnd.uniform(0.82, 1.0) * (1.0 - 0.35 * (abs(x + w / 2) / xr) ** 2)
            d = (y1 - y0) * rnd.uniform(0.9, 1.1)
            bx((w * 0.98, d, h), (x + w / 2, (y0 + y1) / 2 + rnd.uniform(-0.015, 0.015), h / 2),
               cut if (t + int(x * 10)) % 3 else cut_d, rnd.uniform(-0.08, 0.08), 0.008)
            x += w
    rk = rock_paint("#7f786e", "#a0978a", moss_at=0.82)
    boulder(-0.48, 0.0, 0.1, 0.09, 0.12, rk, 31, 12)
    boulder(0.5, 0.04, 0.09, 0.08, 0.1, rk, 32, 12)
    boulder(-0.33, -0.2, 0.06, 0.05, 0.06, rk, 34, 10)
    # adit + timber frame
    bx((0.22, 0.12, 0.26), (0, -0.04, 0.13), flat("adit", "#120d09", 1.0), 0, 0.0)
    timber = tex("wood", "#6e4526")
    for dx in (-0.14, 0.14):
        bx((0.045, 0.045, 0.32), (dx, -0.1, 0.16), timber, 0, 0.006)
        ev.beam((dx, -0.1, 0.24), (dx * 0.55, -0.1, 0.3), 0.025, timber)
    bx((0.4, 0.06, 0.05), (0, -0.1, 0.335), timber, 0, 0.006)
    bx((0.44, 0.12, 0.018), (0, -0.09, 0.365), tex("wood", WOOD_L), 0, 0.004)
    # rails + sleepers coming out of the adit
    steel = flat("rail", "#55575e", 0.5)
    for k in range(8):
        y = -0.06 - k * 0.07
        bx((0.15, 0.03, 0.014), (0, y, 0.018), timber, 0, 0.003)
    for dx in (-0.045, 0.045):
        bx((0.012, 0.56, 0.014), (dx, -0.3, 0.031), steel, 0, 0.0)
    # ore cart on the rails
    cart = tex("wood", "#7a4f2c")
    ev.taper_box((0.17, 0.12, 0.085), (0, -0.4, 0.09), cart, top=(1.15, 1.15), bev=0.0)
    band = flat("band", "#3d3f45", 0.5)
    for dx in (-0.06, 0.06):
        bx((0.014, 0.142, 0.086), (dx, -0.4, 0.09), band, 0, 0.0)
    for dx in (-0.045, 0.045):
        for dy in (-0.045, 0.045):
            cy(0.026, 0.016, (dx * 1.25, -0.4 + dy, 0.035), band, 8, 0.0, rot=(0, math.pi / 2, 0))
    ore = rock_paint("#5d5852", "#7a736a", moss=None)
    gold = flat("ore_gold", "#f2b632", 0.45)
    for k in range(7):
        a = k / 7 * math.tau
        r = 0.035 if k else 0.0
        boulder(r * math.cos(a), -0.4 + r * math.sin(a), 0.035, 0.03, 0.04, gold if k in (2, 5) else ore, 50 + k, 9,
                z0=0.125)
    # lantern on a post (glass stays emissive)
    lx, ly = 0.24, -0.16
    bx((0.03, 0.03, 0.42), (lx, ly, 0.21), timber, 0, 0.004)
    ev.beam((lx, ly, 0.4), (lx - 0.09, ly, 0.4), 0.02, timber)
    iron = flat("iron", "#2b2a2e", 0.5)
    cy(0.004, 0.03, (lx - 0.08, ly, 0.38), iron, 4)
    bx((0.04, 0.04, 0.006), (lx - 0.08, ly, 0.362), iron, 0, 0.0)
    bx((0.034, 0.034, 0.048), (lx - 0.08, ly, 0.335), glow("lantern", "#ffc25a", 4.0), 0, 0.0)
    ev.cn(0.03, 0.025, (lx - 0.08, ly, 0.37), iron, 4).rotation_euler.z = math.pi / 4
    bx((0.04, 0.04, 0.006), (lx - 0.08, ly, 0.31), iron, 0, 0.0)
    # crates, barrel and a pickaxe
    bx((0.085, 0.085, 0.08), (-0.26, -0.22, 0.04), tex("wood", WOOD_L), 0.25, 0.006)
    bx((0.065, 0.065, 0.06), (-0.2, -0.3, 0.03), tex("wood", WOOD_L), -0.3, 0.006)
    cy(0.04, 0.09, (-0.33, -0.33, 0.045), tex("wood", WOOD), 8, 0.004)
    cy(0.042, 0.012, (-0.33, -0.33, 0.07), band, 8, 0.0)
    ev.beam((0.18, -0.3, 0.0), (0.2, -0.3, 0.14), 0.012, timber)
    ev.beam((0.17, -0.3, 0.135), (0.24, -0.3, 0.15), 0.016, flat("steel", "#8d9099", 0.4))
    # a heap of ore by the cart
    for k in range(5):
        boulder(0.13 + rnd.uniform(-0.04, 0.04), -0.48 + rnd.uniform(-0.03, 0.03), 0.04, 0.035, 0.035,
                gold if k == 1 else ore, 60 + k, 9)
    # the quarry of reference frames 3–4: a wooden treadwheel crane over a cut ledge, stacked dressed blocks,
    # scaffolding up the rock face
    blk = tex("plaster", "#c8c2b6", 2.0)
    for i, (x, y, z) in enumerate(((0.36, -0.36, 0.03), (0.44, -0.36, 0.03), (0.4, -0.28, 0.03), (0.4, -0.32, 0.085),
                                   (0.32, -0.28, 0.03), (0.48, -0.28, 0.03))):
        bx((0.075, 0.07, 0.055), (x, y, z), blk, 0.1 * (i % 3), 0.005)
    cx, cy0 = 0.46, -0.12  # crane: an A-frame with a jib reaching over the blocks, rope and a hook with a block
    for sy in (-1, 1):
        ev.beam((cx - 0.06, cy0 + sy * 0.05, 0.0), (cx, cy0, 0.42), 0.022, timber)
        ev.beam((cx + 0.06, cy0 + sy * 0.05, 0.0), (cx, cy0, 0.42), 0.022, timber)
    ev.beam((cx - 0.06, cy0 + 0.04, 0.36), (cx - 0.04, cy0 - 0.24, 0.46), 0.02, timber)
    cy(0.06, 0.03, (cx - 0.02, cy0 + 0.09, 0.12), tex("wood", WOOD_L), 12, 0.0, rot=(math.pi / 2, 0, 0))  # treadwheel
    cy(0.065, 0.02, (cx - 0.02, cy0 + 0.09, 0.12), tex("wood", "#6e4526"), 12, 0.0, rot=(math.pi / 2, 0, 0))
    rope = flat("rope", "#d8c8a0", 0.9)
    ev.beam((cx - 0.04, cy0 - 0.24, 0.46), (cx - 0.04, cy0 - 0.24, 0.2), 0.006, rope)
    bx((0.06, 0.055, 0.045), (cx - 0.04, cy0 - 0.24, 0.17), blk, 0.3, 0.004)
    for z in (0.14, 0.28):  # scaffolding planks and poles against the rock face, left of the adit
        bx((0.24, 0.06, 0.012), (-0.34, -0.06, z), tex("wood", WOOD_L), 0.0, 0.002)
    for x in (-0.45, -0.23):
        for y in (-0.09, -0.03):
            cy(0.01, 0.34, (x, y, 0.17), timber, 6)
    # the timber headframe of reference frame 4 over a shaft on the left shoulder of the rock: four raked legs,
    # braces, a platform and the sheave wheel on top, with the rope down into the shaft
    hx, hy, top = -0.3, 0.16, 0.86
    legs = [(-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)]
    for (dx, dy) in legs:
        ev.beam((hx + dx * 1.6, hy + dy * 1.6, 0.0), (hx + dx * 0.55, hy + dy * 0.55, top), 0.026, timber)
    for z, k in ((0.3, 1.25), (0.58, 0.9)):  # horizontal braces at two levels
        for i in range(4):
            a, b = legs[i], legs[(i + 1) % 4]
            ev.beam((hx + a[0] * k, hy + a[1] * k, z), (hx + b[0] * k, hy + b[1] * k, z), 0.016, timber)
    for i in (0, 2):  # diagonal crosses on the front and back
        a, b = legs[i], legs[(i + 1) % 4]
        ev.beam((hx + a[0] * 1.25, hy + a[1] * 1.25, 0.3), (hx + b[0] * 0.9, hy + b[1] * 0.9, 0.58), 0.012, timber)
    bx((0.16, 0.16, 0.018), (hx, hy, top), tex("wood", WOOD_L), 0.0, 0.003)
    for sx in (-1, 1):  # the wheel's bearing posts
        bx((0.02, 0.02, 0.07), (hx + sx * 0.035, hy, top + 0.035), timber, 0.0, 0.002)
    cy(0.075, 0.016, (hx, hy, top + 0.08), tex("wood", "#6e4526"), 14, 0.0, rot=(0, math.pi / 2, 0))
    cy(0.06, 0.02, (hx, hy, top + 0.08), flat("iron", "#2b2a2e", 0.5), 14, 0.0, rot=(0, math.pi / 2, 0))
    ev.beam((hx, hy - 0.07, top + 0.08), (hx, hy - 0.07, 0.25), 0.005, rope)
    ev.beam((hx, hy - 0.07, top + 0.08), (hx + 0.24, hy - 0.2, 0.12), 0.005, rope)  # to the winch
    # a second cart heaped with glowing ore, by the yard's edge (the warm-lit carts of frame 4)
    gx, gy = -0.12, -0.46
    ev.taper_box((0.15, 0.11, 0.075), (gx, gy, 0.085), cart, top=(1.15, 1.15), bev=0.0)
    for dx in (-0.05, 0.05):
        bx((0.012, 0.13, 0.076), (gx + dx, gy, 0.085), band, 0, 0.0)
    for dx in (-0.04, 0.04):
        for dy in (-0.04, 0.04):
            cy(0.024, 0.014, (gx + dx * 1.25, gy + dy, 0.032), band, 8, 0.0, rot=(0, math.pi / 2, 0))
    hot = glow("ore_hot", "#ffb347", 2.2)
    for k in range(6):
        a = k / 6 * math.tau
        r = 0.03 if k else 0.0
        boulder(gx + r * math.cos(a), gy + r * math.sin(a), 0.03, 0.026, 0.034, hot if k % 2 == 0 else gold, 70 + k, 8,
                z0=0.115)


ASSETS = {
    "tree_pine": tree_pine,
    "tree_round": tree_round,
    "rock": rock,
    "crag": crag,
    "mountain": mountain,
    "wheat_field": wheat_field,
    "crop_field": crop_field,
    "windmill": windmill,
    "mine": mine,
    "bush": bush,
    "flowers": flowers,
}


# ------------------------------------------------------------------ export


def reset():
    ea.reset()
    _PAINT.clear()


def export(name, out, pivot=None):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    ev.lowpoly([o for o in objs if not o.get("flat")])
    # sails: apply modifiers now and tag their vertices so they can be split off after the joint bake
    tagged = [o for o in objs if o.get("sails")]
    for o in tagged:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.convert(target="MESH")
        vg = o.vertex_groups.new(name="sails")
        vg.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
    ob = ea.bake_asset(objs, 512)
    ob.name = name
    ob.data.name = name
    parts = [ob]
    if tagged:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        ob.vertex_groups.active_index = ob.vertex_groups["sails"].index
        bpy.ops.object.vertex_group_select()
        bpy.ops.mesh.separate(type="SELECTED")
        bpy.ops.object.mode_set(mode="OBJECT")
        sl = [o for o in bpy.context.selected_objects if o is not ob][0]
        sl.name = "sails"
        sl.data.name = "sails"
        for o in (ob, sl):
            o.vertex_groups.clear()
        bpy.context.scene.cursor.location = pivot
        bpy.ops.object.select_all(action="DESELECT")
        sl.select_set(True)
        bpy.context.view_layer.objects.active = sl
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
        parts.append(sl)
    tris = 0
    for o in parts:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    ws = [o.matrix_world @ v.co for o in parts for v in o.data.vertices]
    rad = max(math.hypot(w.x, w.y) for w in ws)
    ext = [(min(w[i] for w in ws), max(w[i] for w in ws)) for i in range(3)]
    mats = sorted({m_.name for o in parts for m_ in o.data.materials})
    print(f"EXPORTED {name}: tris={tris} nodes={[o.name for o in parts]} radius={rad:.2f} "
          f"x={ext[0][0]:.2f}..{ext[0][1]:.2f} y={ext[1][0]:.2f}..{ext[1][1]:.2f} height={ext[2][1]:.2f} mats={mats}",
          flush=True)
    return tris


# ------------------------------------------------------------------ contact sheet


def _layout():
    """Tiles as map_view.gd fills them. Each entry: (model, godot_x, godot_z, rot_y, scale)."""
    rnd = random.Random(4)
    tiles = []
    forest = []
    for i in range(rnd.randint(8, 12)):
        forest.append(("tree_pine" if rnd.random() < 0.75 else "tree_round", rnd.uniform(-0.62, 0.62),
                       rnd.uniform(-0.62, 0.62), rnd.uniform(0, math.tau), rnd.uniform(0.85, 1.3)))
    tiles.append(forest)
    plain = []
    for i in range(4):
        plain.append(("tree_pine" if rnd.random() < 0.6 else "tree_round", rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
                      rnd.uniform(0, math.tau), rnd.uniform(0.7, 1.0)))
    plain += [("bush", -0.35, 0.4, 0.3, 1.2), ("bush", 0.45, -0.1, 1.3, 1.0), ("flowers", 0.0, 0.3, 0.0, 1.3),
              ("flowers", -0.5, -0.2, 2.0, 1.1)]
    tiles.append(plain)
    hills = [("rock", rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, math.tau), rnd.uniform(1.2, 2.0))
             for _ in range(3)] + [("tree_pine", 0.3, 0.3, 0.0, 1.0)]
    tiles.append(hills)
    tiles.append([("tree_pine", -0.45, 0.25, 0.0, 1.0), ("tree_round", 0.0, 0.25, 0.0, 1.0), ("rock", 0.45, 0.25, 0.0, 1.0),
                  ("bush", -0.3, -0.35, 0.0, 1.0), ("flowers", 0.25, -0.35, 0.0, 1.0)])
    tiles.append([("mountain", 0, 0, 1.1, 1.4)])
    tiles.append([("wheat_field", 0.1, 0.1, 0.0, 0.95), ("windmill", -0.45, -0.3, 0.4, 0.95)])
    tiles.append([("mine", 0, 0, 0.2, 1.1)])
    tiles.append([("mountain", 0, 0, 4.0, 2.4)])
    return tiles


def contact_sheet(model_dir, png, res_x=2400):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#5aa632", "#7cc443", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    tiles = _layout()
    cols, sp = 4, 2.3
    rows_y = [0.0, 2.9]
    # back row: wider gaps so the 2.4x mountain does not hide its neighbours
    back_x = [-4.1, -1.6, 0.8, 3.5]
    for ti, items in enumerate(tiles):
        cx = (ti % cols - (cols - 1) / 2) * sp if ti < cols else back_x[ti - cols]
        cyy = rows_y[ti // cols]
        kit.hex_prism("tile", (cx, cyy, 0), 1.0, 0.18, grass, dirt, 0.03)
        for name, gx, gz, rot, s in items:
            path = os.path.join(model_dir, name + ".glb")
            if not os.path.exists(path):
                continue
            before = {o.name for o in bpy.context.scene.objects}
            bpy.ops.import_scene.gltf(filepath=path)
            M = Matrix.Translation((cx + gx, cyy - gz, 0)) @ Matrix.Rotation(rot, 4, "Z") @ Matrix.Scale(s, 4)
            for o in bpy.context.scene.objects:
                if o.name not in before and o.parent is None:
                    o.matrix_world = M @ o.matrix_world
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
    cam.data.ortho_scale = cols * sp + 1.6
    el = math.radians(45)
    cyc = rows_y[-1] / 2 + 0.9
    cam.location = (0, cyc - 30 * math.cos(el), 30 * math.sin(el))
    cam.rotation_euler = (math.pi / 2 - el, 0, 0)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 20
    sc.cycles.use_denoising = True
    sc.render.resolution_x = res_x
    sc.render.resolution_y = int(res_x * 0.62)
    sc.view_settings.view_transform = "AgX"
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    print("SHEET", png)


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0] if args else "game/assets/models"
    rest = args[1:]
    if "--sheet" in rest:
        contact_sheet(out, rest[rest.index("--sheet") + 1])
        sys.exit(0)
    os.makedirs(out, exist_ok=True)
    only = set(rest)
    report = {}
    for name, build in ASSETS.items():
        if only and name not in only:
            continue
        reset()
        pivot = build()
        report[name] = export(name, out, pivot)
    print("TRIS", report)
