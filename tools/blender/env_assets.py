"""Environment props for the medieval map: trees, rocks, mountains, farm, windmill, mine (+ bush, flowers).

Overwrites the simple placeholder props that export_assets.py makes (same file names, same footprints),
so the map picks them up without code changes:
  tree_pine.glb  tree_round.glb  rock.glb  mountain.glb  wheat_field.glb  windmill.glb  mine.glb
  bush.glb  flowers.glb  crop_field.glb (DL6–7 plots)  crag.glb (hills hexes)

Run:   python3 tools/blender/env_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/env_assets.py game/assets/models --sheet OUT.png
       (props on grass hex tiles, arranged the way map_view.gd scatters them, ~45° ortho camera)

Conventions as in evolution_assets.py: Z up, base on Z=0, origin = hex centre (1 hex = flat-top hexagon of
circumradius 1.0), front faces −Y (Godot +Z, towards the camera). Procedural colours are painted in model
space (height / facing gradients = cheap fake light, moss, snow) and baked into one 512 px texture per
asset; emissive materials (mine lantern, windmill windows) stay separate so they glow in Godot.

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

    def voronoi(self, scale, feature="F1", stretch=None):
        """Voronoi cells of the model-space position: (distance, per-cell random colour) outputs."""
        n = self.nt.nodes.new("ShaderNodeTexVoronoi")
        n.feature = feature
        n.inputs["Scale"].default_value = scale
        vec = self.pos
        if stretch:
            vm = self.nt.nodes.new("ShaderNodeVectorMath")
            vm.operation = "MULTIPLY"
            self.L.new(self.pos, vm.inputs[0])
            vm.inputs[1].default_value = stretch
            vec = vm.outputs[0]
        self.L.new(vec, n.inputs["Vector"])
        return n.outputs["Distance"], n.outputs.get("Color")

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


def granite_paint(c1, c2, moss=("#34481f", "#4a6328"), moss_at=0.86, scale=6.0, cracks=0.4, moss_z=0.08, cover=0.3):
    """Mid-grey granite of reference frames 1 and 3: horizontal strata, dark shadowed fissures down the steep faces
    (joints, not marble veins), lighter sunlit top facets, darker steep faces and foot, and a few solid patches of dark
    moss on the flattest high tops only (about `cover` of them; none on small stones below moss_z)."""
    def build():
        p = Paint("granite")
        col = p.mix(p.step(p.noise(scale, 4.0), 0.3, 0.7), c1, c2)
        strata = p.noise(scale * 0.5, 3.0, stretch=(1.0, 1.0, 10.0))
        col = p.mix(p.math("MULTIPLY", p.step(strata, 0.48, 0.66), 0.45), col, shade(c1, 0.78))
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.55, 0.9), 0.4), col, shade(c2, 1.12))
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.35, -0.2), 0.45), col, shade(c1, 0.68))
        col = p.mix(p.math("MULTIPLY", p.step(p.z, 0.05, 0.0), 0.35), col, shade(c1, 0.6))  # grounded foot
        if cracks:  # granite jointing (reference frames 1, 3): tall blocks of slightly different tone parted by dark,
            # straight-edged joints that read as shadowed crevices — not as the meandering veins of marble
            vs = (1.0, 1.0, 0.45)
            _, cell = p.voronoi(scale * 1.4, "F1", vs)
            col = p.mix(p.math("MULTIPLY", p.step(cell, 0.45, 0.1), 0.45), col, shade(c1, 0.8))
            col = p.mix(p.math("MULTIPLY", p.step(cell, 0.6, 0.95), 0.35), col, shade(c2, 1.08))
            edge, _ = p.voronoi(scale * 1.4, "DISTANCE_TO_EDGE", vs)
            steep = p.math("ADD", 0.45, p.math("MULTIPLY", p.step(p.nz, 0.7, 0.35), 0.55))
            fis = p.math("MULTIPLY", p.step(edge, 0.05, 0.018), steep)
            col = p.mix(p.math("MULTIPLY", fis, cracks), col, shade(c1, 0.3))
        if moss:  # solid patches (so no strata show through), flattest high tops only
            lo = 0.5 + (0.5 - cover) * 0.26  # noise Fac ≈ N(0.5, 0.1): P(Fac > lo) ≈ cover
            patch = p.step(p.noise(scale * 1.6, 2.0), lo, lo + 0.03)
            mf = p.math("MULTIPLY", p.math("MULTIPLY", p.step(p.nz, moss_at, moss_at + 0.04), patch),
                        p.step(p.z, moss_z, moss_z + 0.02))
            mcol = p.mix(p.step(p.noise(14.0), 0.35, 0.65), moss[0], moss[1])
            col = p.mix(mf, col, mcol)
        return p.done(col, 0.9)
    return cached(("granite", c1, c2, moss, moss_at, scale, cracks, moss_z, cover), build)


def tor(cx, cy_, w, d, h, mt, seed, z0=-0.02, slant=0.25, rz=0.0, k=0.2):
    """Angular block of stone (a granite tor): a jittered box hull with a slanted, broken top — sharp facets and
    flat ledges instead of a round boulder."""
    rnd = random.Random(seed)
    pts = []
    c, s_ = math.cos(rz), math.sin(rz)
    for sx in (-1, 1):
        for sy in (-1, 1):
            for zz, kk in ((z0, 1.0), (z0 + h * rnd.uniform(0.35, 0.55), 1.0 - k * 0.3)):
                pts.append((sx * w / 2 * kk * rnd.uniform(0.85, 1.05), sy * d / 2 * kk * rnd.uniform(0.85, 1.05), zz))
            ztop = z0 + h * (1.0 - slant * (0.5 - 0.5 * sy) * rnd.uniform(0.6, 1.0)) * rnd.uniform(0.86, 1.0)
            pts.append((sx * w / 2 * (1 - k) * rnd.uniform(0.7, 1.0), sy * d / 2 * (1 - k) * rnd.uniform(0.7, 1.0), ztop))
    for _ in range(4):  # a broken crest
        pts.append((rnd.uniform(-w, w) * 0.32, rnd.uniform(-d, d) * 0.32, z0 + h * rnd.uniform(0.84, 1.04)))
    for (ux, uy) in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # bulging / pinched flanks: no two faces alike
        b = rnd.uniform(0.95, 1.18)
        pts.append((ux * w / 2 * b + uy * rnd.uniform(-0.2, 0.2) * w, uy * d / 2 * b + ux * rnd.uniform(-0.2, 0.2) * d,
                    z0 + h * rnd.uniform(0.25, 0.6)))
    pts = [(cx + x * c - y * s_, cy_ + x * s_ + y * c, z) for x, y, z in pts]
    return hull(pts, mt)


def mountain_paint(grass_line=0.13, snow_line=0.78):
    """Grassy foot → scree → stratified rock (darker on steep faces) → snow on high / flat faces."""
    def build():
        p = Paint("mountain")
        jit = p.math("MULTIPLY", p.math("SUBTRACT", p.noise(5.0, 3.0), 0.5), 0.16)
        zz = p.math("ADD", p.z, jit)
        strata = p.noise(2.2, 3.0, stretch=(1.0, 1.0, 9.0))
        rock = p.mix(p.step(strata, 0.35, 0.68), "#6c6a67", "#97938d")  # cool grey granite (reference frame 1)
        rock = p.mix(p.math("MULTIPLY", p.step(p.noise(30.0, 2.0), 0.55, 0.75), 0.3), rock, "#4f4d4b")
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.75, 0.25), 0.55), rock, "#4a4846")
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.55, 0.9), 0.5), rock, "#b0aca5")
        scree = p.mix(p.step(p.noise(18.0), 0.4, 0.6), "#7d7870", "#958f84")
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


def shingle_paint(c, z0, hc, row=0.024, scale=1.0):
    """Roof shingles in horizontal rows (staggered tiles, world space) whose colour darkens towards the foot of each
    course of height hc above z0 — the overlap shadow that makes a coursed cap read as layered (reference frame 4)."""
    def build():
        p = Paint("shingles")
        co = p.nt.nodes.new("ShaderNodeCombineXYZ")
        p.L.new(p.math("MULTIPLY", p.math("ADD", p.x, p.y), 1.0 / scale), co.inputs[0])
        p.L.new(p.math("MULTIPLY", p.z, 1.0 / scale), co.inputs[1])
        br = p.nt.nodes.new("ShaderNodeTexBrick")
        p.L.new(co.outputs[0], br.inputs["Vector"])
        br.inputs["Color1"].default_value = (*kit.srgb(c), 1)
        br.inputs["Color2"].default_value = (*kit.srgb(shade(c, 0.82)), 1)
        br.inputs["Mortar"].default_value = (*kit.srgb(shade(c, 0.5)), 1)
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Mortar Size"].default_value = 0.004
        br.inputs["Brick Width"].default_value = row * 1.5
        br.inputs["Row Height"].default_value = row
        col = br.outputs["Color"]
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(18.0, 2.0), 0.5, 0.8), 0.35), col, shade(c, 1.25))
        f = p.math("FRACT", p.math("DIVIDE", p.math("SUBTRACT", p.z, z0), hc))
        col = p.mix(p.math("MULTIPLY", p.step(f, 0.32, 0.0), 0.75), col, shade(c, 0.45))
        return p.done(col, 0.8)
    return cached(("shingle", c, z0, hc, row, scale), build)


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


def pine_paint(dark, mid, light, deep, seed=0.0):
    """Conifer needles lit per tier (reference frames 1 and 3): deep blue-green inside, mottled mid green, sunlit
    yellow-green branch tips. The tip factor comes from a point attribute "tip" written by pine_tier (1 at the
    branch tips, 0 at the trunk), so the layering reads wherever the tree stands and however it is scaled."""
    def build():
        p = Paint("pine")
        at = p.nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = "tip"
        tip = at.outputs["Fac"]
        n = p.noise(9.0, 4.0)
        col = p.mix(p.step(n, 0.3, 0.62), dark, mid)
        lit = p.math("MULTIPLY", p.step(tip, 0.72, 0.98), p.step(p.nz, -0.2, 0.5))
        lit = p.math("MULTIPLY", lit, p.math("ADD", 0.55, p.math("MULTIPLY", p.step(p.noise(5.0, 2.0), 0.3, 0.6), 0.45)))
        col = p.mix(lit, col, light)
        col = p.mix(p.step(tip, 0.45, 0.1), col, deep)
        col = p.mix(p.step(p.nz, -0.1, -0.6), col, shade(deep, 0.8))
        return p.done(col, 0.9)
    return cached(("pinepaint", dark, mid, light, deep, seed), build)


def pine_tier(cx, cy_, z0, z1, r, n, rot, mt, droop=0.045, inner=0.66, seed=0):
    """One pine tier: a star skirt of n drooping branch tips around an apex, with a dark concave underside; writes
    the "tip" attribute (apex 0.15, notches 0.5, tips 1, underside 0) for pine_paint."""
    rnd = random.Random(seed)
    verts, tip = [(cx, cy_, z1)], [0.12]
    for k in range(2 * n):
        a = rot + math.pi * k / n + rnd.uniform(-0.08, 0.08)
        if k % 2 == 0:
            rr = r * rnd.uniform(0.9, 1.08)
            z = z0 - droop * rnd.uniform(0.75, 1.2)
            tip.append(1.0)
        else:
            rr = r * inner
            z = z0 + (z1 - z0) * 0.16
            tip.append(0.5)
        verts.append((cx + rr * math.cos(a), cy_ + rr * math.sin(a), z))
    verts.append((cx, cy_, z0 + (z1 - z0) * 0.3))
    tip.append(0.0)
    c = len(verts) - 1
    faces = []
    for k in range(2 * n):
        a, b = 1 + k, 1 + (k + 1) % (2 * n)
        faces.append((0, a, b))
        faces.append((c, b, a))
    o = poly(verts, faces, [mt], flat_shade=False, name="tier")
    at = o.data.attributes.new("tip", "FLOAT", "POINT")
    for i, v in enumerate(tip):
        at.data[i].value = v
    return o


def tall_pine(x=0.0, y=0.0, s=1.0, seed=0, mt=None, bark=None, n=8, tiers=5):
    """Tall layered conifer of reference frames 1 and 3: narrow (height ≈ 3.2× width), five drooping tiers with
    sunlit tips over a dark interior, and the trunk showing at the foot. ~0.75·s tall, ~0.25·s radius."""
    rnd = random.Random(seed)
    mt = mt or pine_paint("#173c24", "#245a2f", "#79a443", "#0e2817")
    bark = bark or tex("wood", BARK)
    cy(0.042 * s, 0.2 * s, (x, y, 0.1 * s), bark, 6, 0.0, r2=0.02 * s)
    radii = [0.228, 0.19, 0.155, 0.12, 0.085][-tiers:]
    for i, r in enumerate(radii):
        z0 = (0.16 + i * 0.1) * s
        z1 = z0 + (0.22 if i < len(radii) - 1 else 0.185) * s
        ox, oy = rnd.uniform(-0.01, 0.01) * s, rnd.uniform(-0.01, 0.01) * s
        pine_tier(x + ox, y + oy, z0, z1, r * s, n if i < 3 else n - 1, rnd.uniform(0, 1), mt,
                  droop=0.045 * s, seed=seed * 10 + i)


def pine_mats():
    return (foliage("#1a3f22", "#29592b", "#5a8236", 0.1, 0.62, 0.45, 7.0),
            foliage("#1d4425", "#2d5f2e", "#62893a", 0.1, 0.62, 0.45, 7.0),
            flat("pine_under", "#25502b", 0.9),
            tex("wood", BARK))


# ------------------------------------------------------------------ assets


def tree_pine():
    tall_pine(seed=3)


def crown_paint(dark, mid, light, deep, centre, radius):
    """Broadleaf crown: mottled greens, a sunlit top, and a baked "occlusion" that darkens everything near the crown's
    centre — the gaps between clumps go deep green, so the crown reads as lumpy and layered, not as one pale ball."""
    def build():
        p = Paint("crown")
        vm = p.nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "DISTANCE"
        p.L.new(p.pos, vm.inputs[0])
        vm.inputs[1].default_value = centre
        occ = p.step(p.math("DIVIDE", vm.outputs["Value"], radius), 0.55, 0.95)
        col = p.mix(p.step(p.noise(8.0, 4.0), 0.3, 0.62), dark, mid)
        top = p.math("MULTIPLY", p.step(p.nz, 0.55, 0.95), p.step(p.noise(5.0, 2.0), 0.32, 0.6))
        col = p.mix(p.math("MULTIPLY", top, p.math("MULTIPLY", occ, 0.7)), col, light)
        col = p.mix(p.math("SUBTRACT", 1.0, occ), col, deep)
        col = p.mix(p.step(p.nz, -0.05, -0.6), col, shade(deep, 0.85))
        return p.done(col, 0.9)
    return cached(("crown", dark, mid, light, deep, tuple(centre), radius), build)


def lush_tree(x=0.0, y=0.0, s=1.0, seed=0):
    """Broadleaf of the reference frames: a full crown built in two layers — a ring of four clumps round a central
    mass, two smaller clumps on top — sunlit on top, deep green inside, on a flared trunk with forked limbs."""
    rnd = random.Random(seed)
    leaf = crown_paint("#1f4518", "#346224", "#86ae40", "#112c0d", (x, y, 0.26 * s), 0.22 * s)
    bark = tex("wood", BARK)
    cy(0.045 * s, 0.26 * s, (x, y, 0.13 * s), bark, 6, 0.0, r2=0.024 * s)
    for a in (0.4, 2.5, 4.4):  # forked limbs reaching into the crown
        ev.rod((x, y, 0.17 * s), (x + 0.09 * s * math.cos(a), y + 0.09 * s * math.sin(a), 0.29 * s), 0.014 * s, bark, n=5,
               r2=0.008 * s)
    crowns = [(0.0, 0.0, 0.35, 0.13, 2)]
    for k in range(4):
        a = k * math.pi / 2 + 0.6 + rnd.uniform(-0.25, 0.25)
        d = rnd.uniform(0.085, 0.1)
        crowns.append((d * math.cos(a), d * math.sin(a), rnd.uniform(0.29, 0.32), rnd.uniform(0.095, 0.11), 2))
    crowns += [(0.03, -0.04, 0.45, 0.085, 1), (-0.05, 0.05, 0.43, 0.08, 1)]
    for i, (cx, cy_, cz, r, sub) in enumerate(crowns):
        blob(r * s, (x + cx * s, y + cy_ * s, cz * s), leaf, (1, 1, 0.86), sub, seed * 7 + i, 0.14)


def tree_round():
    lush_tree(seed=2)


def bush():
    leaf = crown_paint("#1f4518", "#346224", "#86ae40", "#112c0d", (0.0, 0.0, 0.03), 0.12)  # as the broadleaf crown
    for i, (x, y, z, r) in enumerate([(0, 0, 0.06, 0.085), (0.07, -0.03, 0.045, 0.06), (-0.065, 0.02, 0.045, 0.065),
                                      (0.01, 0.04, 0.1, 0.055)]):
        blob(r, (x, y, z), leaf, (1, 1, 0.85), 1, 40 + i, 0.15)
    berry = flat("berry", "#e0304a", 0.6)  # a red accent that still reads at map size
    for x, y, z in [(0.03, -0.078, 0.085), (-0.05, -0.055, 0.075), (0.09, -0.06, 0.055), (-0.1, -0.02, 0.06),
                    (0.0, -0.035, 0.135), (0.065, 0.02, 0.1)]:
        ev.ico(0.0135, (x, y, z), berry, (1, 1, 1), 1)


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
    """A granite outcrop (reference frames 1 and 3): a leaning angular block, a second block and a flat slab at its
    foot, two loose stones — sharp facets, strata and cracks, pale tops."""
    mt = granite_paint("#69645c", "#8a8479", moss_at=0.74, scale=9.0, cracks=0.45, moss_z=0.1)
    tor(0.0, 0.02, 0.24, 0.19, 0.2, mt, 11, slant=0.3, rz=0.3)
    tor(0.15, -0.07, 0.13, 0.11, 0.115, mt, 12, slant=0.2, rz=-0.4)
    tor(-0.13, 0.07, 0.13, 0.12, 0.06, mt, 13, slant=0.1, rz=0.8, k=0.1)
    boulder(0.05, -0.16, 0.045, 0.04, 0.04, mt, 14, 9)
    boulder(-0.11, -0.1, 0.036, 0.032, 0.032, mt, 15, 8)


def crag():
    """Hills hex (the rocky outcrops of the reference frames): a grey stone ridge of stacked faceted blocks with
    ledges, a scree apron, moss on the tops and a few pines clinging to it."""
    mt = granite_paint("#625d56", "#837d73", moss_at=0.72, cracks=0.5, moss_z=0.1, cover=0.4)
    dark = granite_paint("#544f49", "#716b63", moss=None, cracks=0.55)
    # the main ridge (reference frame 3's grey crags): stacked angular tors with ledges, rising toward the back
    tor(-0.1, 0.18, 0.36, 0.28, 0.42, mt, 41, slant=0.15, rz=0.15)
    tor(-0.05, 0.25, 0.26, 0.2, 0.6, dark, 49, slant=0.3, rz=-0.2, k=0.5)  # the summit
    tor(0.2, 0.12, 0.3, 0.24, 0.3, mt, 42, slant=0.25, rz=-0.35)
    tor(0.24, 0.2, 0.2, 0.16, 0.44, dark, 50, slant=0.3, rz=0.4, k=0.45)
    tor(-0.33, 0.0, 0.22, 0.2, 0.24, dark, 43, slant=0.3, rz=0.5)
    tor(0.38, -0.1, 0.18, 0.15, 0.16, mt, 44, slant=0.3, rz=-0.6)
    # ledges and broken blocks in front
    tor(0.02, -0.08, 0.3, 0.14, 0.13, mt, 45, slant=0.15, rz=0.05, k=0.12)
    tor(-0.18, -0.27, 0.12, 0.1, 0.08, dark, 46, slant=0.2, rz=0.9)
    tor(0.24, -0.32, 0.1, 0.09, 0.06, mt, 47, slant=0.2, rz=-0.3)
    # scree: little stones spilling down the front
    rnd = random.Random(48)
    for k in range(12):
        x, y = rnd.uniform(-0.45, 0.45), rnd.uniform(-0.48, -0.17)
        r = rnd.uniform(0.02, 0.04)
        boulder(x, y, r, r * 0.9, r * 0.75, dark if k % 3 else mt, 60 + k, 8)
    for (x, y, sc) in ((0.44, 0.3, 0.78), (-0.45, 0.33, 0.82), (0.08, 0.47, 0.72), (-0.52, -0.22, 0.62)):
        tall_pine(x, y, sc, seed=int(abs(x) * 100 + abs(y) * 10))


def _mountain_height(x, y, k=0.84):
    x, y = x / k, y / k
    # a massif of comparable sharp peaks (reference frame 1), not one cone
    peaks = [(-0.1, 0.14, 1.2, 0.62, 0.0), (0.36, -0.08, 1.02, 0.5, 1.7), (-0.4, -0.22, 0.88, 0.46, 3.1),
             (0.22, 0.44, 0.84, 0.42, 4.4)]
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
    h += 0.1 * h * (1.0 - abs(mnoise.noise(v * 1.6 + Vector((3.1, 0.0, 0.0)))))  # ridged crests and gullies
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
    cand = [(a, r) for a in [i * 0.37 for i in range(17)] for r in (0.48, 0.56, 0.62, 0.7)]
    random.Random(5).shuffle(cand)
    for a, r in cand:  # pines climb the lower slopes (reference frame 1), not only the grassy foot
        x, y = r * math.cos(a), r * math.sin(a)
        h = _mountain_height(x, y)
        if h > 0.34 or any(math.dist((x, y), p) < 0.16 for p in placed):
            continue
        placed.append((x, y))
        build = (lambda s_, sd: (lambda: pine_tree(0, 0, s_, n=6, tiers=3, seed=sd, mats=mats)))(random.Random(len(placed)).uniform(0.38, 0.5), 30 + len(placed))
        ev.build_at(build, x, y, 0.0, 1.0, z=h - 0.02)
        if len(placed) >= 12:
            break


def ripe_paint():
    """Ripe wheat of reference frames 3–4: ochre stalks in the shade, warm gold ears, pale sunlit tips, fine
    vertical streaks — brighter and yellower than the old crop so a field reads as gold at map size."""
    def build():
        p = Paint("ripe")
        col = p.mix(p.step(p.z, 0.04, 0.085), "#8a5a12", "#dc9e1c")
        col = p.mix(p.step(p.z, 0.085, 0.12), col, "#f6c425")
        col = p.mix(p.step(p.z, 0.12, 0.15), col, "#ffe35c")
        streak = p.step(p.noise(6.0, 2.0, stretch=(22.0, 22.0, 1.5)), 0.58, 0.78)
        col = p.mix(p.math("MULTIPLY", streak, 0.22), col, "#c0801a")
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(40.0, 1.0), 0.6, 0.8), 0.45), col, "#fff4b0")
        return p.done(col, 0.75)
    return cached(("ripe",), build)


def wheat_bed(x, y0, y1, body_mt, ear_mt, rnd, w=0.104, lines=2, step=0.034, ear_z=0.118, rr=(0.016, 0.021), top=0.034,
              bottom=0.058, body_h=0.07, lean=0.012):
    """A bed of standing wheat along Y (reference frame 4: a dense bristly mass of ears, not a smooth ridge):
    a stalk body, and over it rows of upright ears — each a plump three-sided grain head with a blunt top and a
    random lean, wide enough that neighbouring beds close into one golden mass. With bottom=None the heads are
    open-bottomed pyramids sitting on the body (low leafy crops: three triangles each)."""
    ev.extrude([(-w / 2, 0.0), (w / 2, 0.0), (w * 0.4, body_h), (-w * 0.4, body_h)], -y1, -y0, body_mt,
               (x, 0, 0.025), (math.pi / 2, 0, 0))
    verts, faces = [], []
    n = max(2, round((y1 - y0) / step))
    for li in range(lines):
        ox = (li - (lines - 1) / 2) * (w * 0.56)
        for j in range(n + (0 if li % 2 else 1)):
            y = y0 + (j + (0.5 if li % 2 else 0.0)) * (y1 - y0) / n
            cx_ = x + ox + rnd.uniform(-0.008, 0.008)
            cy_ = y + rnd.uniform(-0.006, 0.006)
            zm = ear_z + rnd.uniform(-0.012, 0.016)
            r = rnd.uniform(*rr)
            lx, ly = rnd.uniform(-lean, lean) + ox * 0.3, rnd.uniform(-lean, lean)
            rot = rnd.uniform(0, math.tau)
            b = len(verts)
            verts.append((cx_ - lx * 0.6, cy_ - ly * 0.6, zm - (bottom or 0.0)))
            for k in range(3):
                a = rot + k * math.tau / 3
                verts.append((cx_ + r * math.cos(a), cy_ + r * math.sin(a), zm))
            verts.append((cx_ + lx, cy_ + ly, zm + top))
            for k in range(3):
                p0, p1 = b + 1 + k, b + 1 + (k + 1) % 3
                faces.append((b + 4, p0, p1))
                if bottom:
                    faces.append((b, p1, p0))
    return poly(verts, faces, [ear_mt], flat_shade=True, name="ears")


def stook(x, y, mt, band, s=1.0, rz=0.0):
    """A medieval stook: a bundle of cut sheaves standing on end, tied round the waist, ears splayed on top."""
    def b():
        cy(0.036, 0.075, (0, 0, 0.0375), mt, 6, 0.0, r2=0.026)
        ev.cn(0.04, 0.05, (0, 0, 0.095), mt, 6)
        cy(0.029, 0.012, (0, 0, 0.058), band, 6, 0.0)
    ev.build_at(b, x, y, rz, s)


def wheat_field():
    soil = furrows("#5e3d22", "#80552f", period=0.12)
    box = kit.box
    box("soil", (0.9, 0.7, 0.05), (0, 0, 0.0), soil, 0.012)
    body = ripe_paint()
    rnd = random.Random(5)
    xs = [-0.36 + i * 0.12 for i in range(7)]
    for i, x in enumerate(xs):
        y0 = -0.08 if i == 6 else -0.3  # a reaped corner for the stooks
        wheat_bed(x, y0, 0.3, body, body, rnd)
    # the reaped corner: stubble, three stooks of sheaves and a sickle-cut swath (reference frames: lived-in fields)
    stub = zgrad("#a8792c", "#c99a40", "#ddb456", 0.025, 0.05, 30.0)
    bx((0.1, 0.2, 0.012), (0.36, -0.2, 0.03), stub, 0.0, 0.0)
    sheaf = zgrad("#b07a22", "#dcae3e", "#f4d468", 0.0, 0.13, 26.0)
    tie = flat("tie", "#7a5a34", 0.9)
    for (sx, sy, s, rz) in ((0.36, -0.13, 1.0, 0.2), (0.33, -0.25, 0.9, 1.1), (0.41, -0.3, 0.85, 2.0)):
        stook(sx, sy, sheaf, tie, s, rz)
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
    hay = zgrad("#b98f3a", "#dcb455", "#ecd07a", 0.03, 0.12, 30.0)
    sx, sy = -0.12, 0.04
    cy(0.012, 0.32, (sx, sy, 0.16), post, 5)
    ev.beam((sx - 0.1, sy, 0.24), (sx + 0.1, sy, 0.24), 0.014, post)
    ev.taper_box((0.1, 0.045, 0.11), (sx, sy, 0.215), flat("shirt", "#b8402f", 0.9), top=(0.75, 1.0))
    for d in (-1, 1):
        ev.beam((sx + d * 0.035, sy, 0.25), (sx + d * 0.1, sy, 0.235), 0.032, flat("shirt", "#b8402f", 0.9))
        ev.ico(0.016, (sx + d * 0.11, sy, 0.234), sheaf, (1, 1, 1), 1)
    ev.ico(0.034, (sx, sy, 0.31), flat("sack", "#d8c08c", 0.9), (1, 1, 1.05), 1)
    cy(0.06, 0.008, (sx, sy, 0.335), hay, 10)
    cy(0.03, 0.05, (sx, sy, 0.36), hay, 8, 0.0, r2=0.018)


def crop_field():
    """A modern field (DL6–7 countryside): long rows of green crops and a ripe golden strip on ploughed soil, a wire
    fence on posts, a red tractor at the headland and round bales — the industrial cousin of the walled wheat plot."""
    soil = furrows("#5a3b21", "#7a5230", period=0.1)
    box = kit.box
    box("soil", (0.9, 0.7, 0.05), (0, 0, 0.0), soil, 0.012)
    greens = (foliage("#2f5a1c", "#4c8a2a", "#8cc244", 0.03, 0.1, 0.8, 22.0),  # two crops side by side
              foliage("#3a6420", "#6a9a30", "#a8cf52", 0.03, 0.1, 0.8, 22.0))
    ripe = ripe_paint()
    rnd = random.Random(9)
    for i in range(8):  # leafy crop rows (heads on a ridge, not smooth bars); the two near rows ripe wheat
        x = -0.38 + i * 0.105
        if i >= 6:
            wheat_bed(x, -0.3, 0.3, ripe, ripe, rnd, w=0.09, step=0.036)
        else:
            g = greens[(i // 2) % 2]
            wheat_bed(x, -0.3, 0.3, g, g, rnd, w=0.08, step=0.036, ear_z=0.075, rr=(0.024, 0.03), top=0.03,
                      bottom=None, body_h=0.05, lean=0.008)
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


def coursed_cone(z0, r0, h, mt, n=8, courses=4, lip=0.013, rot=math.pi / 8, x=0.0, y=0.0):
    """Steep conical cap laid in overlapping shingle courses (reference frames 3–4: the windmill's dark-blue cap):
    each course is a frustum a little wider at its foot than the top of the one below, so every course casts a
    dark line — readable layering at game size, where a plain cone reads as one flat colour."""
    for k in range(courses):
        t0, t1 = k / courses, (k + 1) / courses
        zb = z0 + h * t0 - (lip * 0.5 if k else 0.0)
        zt = z0 + h * t1
        rb = r0 * (1 - t0) + lip * (1.0 - 0.4 * t0)
        if k == courses - 1:
            o = ev.cn(rb, zt - zb, (x, y, (zb + zt) / 2), mt, n)
        else:
            o = cy(rb, zt - zb, (x, y, (zb + zt) / 2), mt, n, 0.0, r2=r0 * (1 - t1) + lip * 0.25)
        o.rotation_euler.z = rot


def grain_sack(x, y, z, mt, tie, s=1.0, lie=0.0, rz=0.0):
    """A plump burlap sack with a tied neck (standing, or lying when lie≈π/2)."""
    def b():
        ev.ico(0.034 * s, (0, 0, 0.036 * s), mt, (1.0, 0.82, 1.12), 1)
        ev.cn(0.014 * s, 0.026 * s, (0, 0, 0.082 * s), tie, 4)
    ev.build_at(b, x, y, rz, 1.0, (0.0, lie), z)


def hand_cart(load, tie, wood_mt, wheel_mt, iron_mt):
    """Two-wheeled hand cart (reference frame 4: carts at the foot of every work site), shafts resting on the
    ground towards −X, loaded with sacks."""
    bx((0.13, 0.085, 0.016), (0, 0, 0.056), wood_mt, 0, 0.0)
    for sy in (-1, 1):
        bx((0.13, 0.008, 0.034), (0, sy * 0.043, 0.077), wood_mt, 0, 0.0)
        cy(0.042, 0.012, (0.012, sy * 0.054, 0.042), wheel_mt, 8, 0.0, rot=(math.pi / 2, 0, 0))
        ev.beam((-0.06, sy * 0.034, 0.05), (-0.17, sy * 0.03, 0.006), 0.012, wood_mt)
    grain_sack(-0.05, -0.018, 0.094, load, tie, 0.95, math.pi / 2 - 0.2, 0.1)
    grain_sack(-0.035, 0.022, 0.09, load, tie, 0.9, math.pi / 2 - 0.1, -0.15)


def windmill():
    """Tower mill of reference frames 3–4: a tall tapered stone tower in bold courses, a reefing gallery, a steep
    dark-blue cap in shingle courses with the windshaft housing on its front, four big lattice sails with canvas,
    an arched door, warm-lit windows, and sacks and a loaded cart at its foot."""
    st = ev.stone("#bab09f", 0.72)  # big warm-grey blocks: the courses must still read at game size
    std = ev.stone(STONE_D, 0.72)
    wood = tex("wood", WOOD)
    woodd = tex("wood", WOOD_D)
    woodl = tex("wood", WOOD_L)
    roof = tex("roof", "#30509a", 0.9)  # deep slate-blue like the reference roofs, not the bright team blue
    cap_h, cap_z0 = 0.3, 0.652
    cap = shingle_paint("#3a5aa6", cap_z0, cap_h / 4)
    iron = flat("iron", "#2b2a2e", 0.5)
    rot8 = math.pi / 8  # a flat octagon face looks at the camera (−Y), not a corner

    zb, zt, rb, rt = 0.05, 0.63, 0.172, 0.118  # the tower: a tapered octagon

    def r_at(z):
        return rb + (rt - rb) * (z - zb) / (zt - zb)

    def apo(z):  # distance from the axis to a flat face at height z
        return r_at(z) * math.cos(rot8)

    cy(0.205, 0.06, (0, 0, 0.03), std, 8, 0.0).rotation_euler.z = rot8  # plinth
    cy(rb, zt - zb, (0, 0, (zb + zt) / 2), st, 8, 0.006, r2=rt).rotation_euler.z = rot8
    cy(r_at(0.28) + 0.01, 0.024, (0, 0, 0.28), std, 8, 0.0).rotation_euler.z = rot8  # string course
    # reefing gallery: plank ring on struts, posts and a hand rail
    zg = 0.4
    cy(0.205, 0.018, (0, 0, zg), woodl, 8, 0.004).rotation_euler.z = rot8
    for k in range(8):
        a = k / 8 * math.tau + rot8
        c, s_ = math.cos(a), math.sin(a)
        ev.beam((0.19 * c, 0.19 * s_, zg + 0.005), (0.19 * c, 0.19 * s_, zg + 0.07), 0.011, woodd)
    ev.torus(0.19, 0.0065, (0, 0, zg + 0.07), woodd, (0, 0, rot8), 8, 3)
    # cap: curb, shingle courses, finial
    cy(rt + 0.014, 0.03, (0, 0, zt + 0.01), woodd, 8, 0.0).rotation_euler.z = rot8
    coursed_cone(cap_z0, 0.15, cap_h, cap, 8, 4, lip=0.02)
    cy(0.006, 0.05, (0, 0, cap_z0 + cap_h + 0.015), iron, 4)
    ev.ico(0.017, (0, 0, cap_z0 + cap_h + 0.045), flat("gold", "#ffc933", 0.4), (1, 1, 1), 1)
    # windshaft housing on the cap's front: a little gabled box the axle comes out of
    hub_y, hub_z = -0.25, 0.67
    bx((0.085, 0.1, 0.07), (0, -0.115, hub_z), woodd, 0, 0.0)
    ev.extrude([(-0.055, 0.0), (0.055, 0.0), (0.0, 0.042)], 0.06, 0.172, roof, (0, 0, hub_z + 0.035), (math.pi / 2, 0, 0))
    cy(0.024, 0.09, (0, -0.205, hub_z), wood, 8, 0.0, rot=(math.pi / 2, 0, 0))  # windshaft
    # arched door in a stone surround, iron straps, a step
    door_mt = tex("wood", "#5c3a1f", 2.2)
    for (w, d, y, mt) in ((0.104, 0.03, -apo(0.12) + 0.001, std), (0.07, 0.02, -apo(0.12) - 0.007, door_mt)):
        bx((w, d, 0.11), (0, y, 0.06 + 0.055), mt, 0, 0.0)
        cy(w / 2, d, (0, y, 0.17), mt, 8, 0.0, rot=(math.pi / 2, 0, 0))
    for z in (0.095, 0.155):
        bx((0.06, 0.006, 0.008), (0, -apo(0.12) - 0.019, z), iron, 0, 0.0)
    bx((0.13, 0.055, 0.03), (0, -0.21, 0.015), std, 0, 0.004)
    # small windows: dark frame, warm lit glass, stone lintel (reference frames: lamplight in every building)
    frame_mt = flat("frame", "#3a2616", 0.8)
    for th, z in ((-math.pi / 4, 0.2), (-3 * math.pi / 4, 0.3), (-math.pi / 2, 0.52), (math.pi, 0.46)):  # normals at k·45°
        d = apo(z)
        c, s_ = math.cos(th), math.sin(th)
        rz = th + math.pi / 2
        bx((0.046, 0.012, 0.062), (c * (d + 0.002), s_ * (d + 0.002), z), frame_mt, rz, 0.0)
        bx((0.03, 0.014, 0.046), (c * (d + 0.004), s_ * (d + 0.004), z - 0.002), ev.win_lit(), rz, 0.0)
        bx((0.058, 0.018, 0.012), (c * (d + 0.004), s_ * (d + 0.004), z + 0.037), std, rz, 0.0)
    # life at the foot: a sack pile, a loaded hand cart, a barrel
    sack = tex("plaster", "#c9a46a", 1.6)  # burlap: tan, so the pile does not read as white balls
    tie = flat("tie", "#7a5a34", 0.9)
    for (x, y, z, s, rz) in ((0.13, -0.245, 0.0, 1.0, 0.3), (0.2, -0.19, 0.0, 1.05, -0.5), (0.235, -0.11, 0.0, 0.9, 1.2),
                             (0.165, -0.215, 0.07, 0.9, 0.9)):
        grain_sack(x, y, z, sack, tie, s, 0.0, rz)
    ev.build_at(lambda: hand_cart(sack, tie, woodl, wood, iron), -0.25, -0.13, -0.6)
    cy(0.03, 0.068, (-0.1, -0.245, 0.034), wood, 8, 0.0)
    cy(0.032, 0.008, (-0.1, -0.245, 0.05), iron, 8, 0.0)
    # sails (separate node, spun about the hub): stout boss, four stocks, lattice of bars and rails, canvas
    sails = []
    sails.append(cy(0.05, 0.045, (0, hub_y - 0.0225, hub_z), woodd, 8, 0.0, rot=(math.pi / 2, 0, 0)))
    sails.append(cy(0.028, 0.016, (0, hub_y - 0.05, hub_z), iron, 8, 0.0, rot=(math.pi / 2, 0, 0)))
    cloth = tex("plaster", "#ecdcb8", 1.4)
    L = 0.4
    for i in range(4):
        a = i * math.pi / 2 + 0.35

        def P(rad, off=0.0, dy=0.0):  # point along the arm (rad from hub) shifted sideways by off
            return (math.sin(a) * rad + math.cos(a) * off, hub_y - 0.03 + dy, hub_z + math.cos(a) * rad - math.sin(a) * off)

        sails.append(ev.beam(P(0.02, 0.0, -0.002), P(L + 0.01, 0.0, -0.002), 0.024, woodd))  # the stock
        o = bx((0.118, 0.005, L - 0.09), P(0.09 + (L - 0.09) / 2, 0.072, 0.008), cloth, 0, 0.0)
        o.rotation_euler.y = a
        sails.append(o)
        sails.append(ev.beam(P(0.085, 0.135, -0.004), P(L, 0.135, -0.004), 0.012, wood))  # outer rail
        for k in range(5):
            rad = 0.09 + (L - 0.09) * k / 4
            sails.append(ev.beam(P(rad, -0.03, 0.0), P(rad, 0.141, 0.0), 0.01, wood))  # bars
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


# models whose bake atlas gets its empty space filled (fill_atlas); mountain, mine and flowers keep the plain bake
FILL_ATLAS = {"windmill", "wheat_field", "crop_field", "tree_pine", "tree_round", "bush", "rock", "crag"}


def fill_atlas(ob):
    """Fill the atlas pixels that no UV island covers (the bake leaves them black) with the colour of the nearest
    islands, by a push-pull pyramid. Many small islands (wheat ears, crop heads, pine tiers) leave 20–45 % of a
    512 px atlas empty; the mipmaps Godot builds would average that black in and darken the model at map zoom."""
    import numpy as np
    img = next(n.image for s in ob.material_slots if s.material and s.material.name.startswith("baked")
               for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE")
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    cov = (a[..., :3].max(-1) > 0).astype(np.float32)  # nothing in these models bakes to pure black
    cols, wts = [a[..., :3] * cov[..., None]], [cov]
    while cols[-1].shape[0] > 1 and cols[-1].shape[1] > 1:  # pull: sums of colour and coverage per level
        c, wt = cols[-1], wts[-1]
        hh, ww = c.shape[0] // 2, c.shape[1] // 2
        cols.append(c.reshape(hh, 2, ww, 2, 3).sum((1, 3)))
        wts.append(wt.reshape(hh, 2, ww, 2).sum((1, 3)))
    fill = cols[-1] / np.maximum(wts[-1], 1e-8)[..., None]
    for c, wt in zip(reversed(cols[:-1]), reversed(wts[:-1])):  # push: holes take the coarser level's average
        up = fill.repeat(2, 0).repeat(2, 1)
        fill = np.where(wt[..., None] > 0, c / np.maximum(wt, 1e-8)[..., None], up)
    a[..., :3] = np.where(cov[..., None] > 0, a[..., :3], fill)
    img.pixels.foreach_set(a.ravel())
    img.update()
    img.pack()


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
    if name in FILL_ATLAS:
        fill_atlas(ob)
    ob.name = name
    ob.data.name = name
    parts = [ob]
    if tagged:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        # the join keeps the first object's transform (the windmill's plinth is turned π/8): bake the rotation into
        # the mesh so the split-off sails get an identity rotation and spin about their true axle in Godot
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
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
