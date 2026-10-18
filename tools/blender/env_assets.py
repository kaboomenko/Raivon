"""Environment props for the medieval map: trees, rocks, mountains, farm, windmill, mine (+ bush, flowers).

Overwrites the simple placeholder props that export_assets.py makes (same file names, same footprints),
so the map picks them up without code changes:
  tree_pine.glb  tree_round.glb  rock.glb  mountain.glb  wheat_field.glb  windmill.glb  mine.glb
  bush.glb  flowers.glb  crop_field.glb (DL6–7 plots)  crag.glb (hills hexes)
  dark_lake.glb (the Dark Lake hex; map_view spawns it once followup_map_view_dark_lake.patch lands — art pass 5)

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
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
import evolution_assets as ev  # noqa: E402
from evolution_assets import bx, cy, shade, tex, flat, glow  # noqa: E402

WOOD = "#7d5130"
WOOD_L = "#a8743f"
WOOD_D = "#5a3a22"
BARK_SOFT = "#7b5536"  # the soft trees' trunks (§6.3: warm, never near-black)
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


# «Raivon Soft» stone (§6.3): warm grey rock, a pale sunlit top, lilac shade (never a darker grey), spring-green moss.
# Under the M1 sun a face turned to the sky shows ×1.25 lighter than its albedo: §6.3's pale top #D8CFBF clipped to
# «white-hot» (V > 0.92, S < 0.18: 8.5 % of a rock pile's pixels in game), and even #BDB3A3 sat at V 0.93 there. So
# the top only turns warm (sunlit sand) at the base's value, the light makes it the brightest face.
# Even #B9AF9F (L* 72) lit to L* 86–89 in game (#EADFCD), and with the lilac flanks the piles read as lilac-white
# porcelain, as light as the straw roofs (L* 77–85 on screen; §6.3 value rule: roofs are the lightest surfaces);
# #AEA391 (L* 67.5) still lit to 82.5. So the base and top sit at L* 63–64 (≈ −10 under §6.3's #BDB3A3: lit faces
# ≈ 78, under the roofs) and a touch warmer (b* 11–13), and the moss is a step less yellow than §6.3's #8DBA4E
# (hue 91° instead of 85°): soft_model's saturation ×1.15 turned it lime on screen.
STONE_C = {"base": "#A39886", "top": "#A69983", "shade": "#8C86A0", "moss": "#84B556"}
MOSS_C = ("#72A44C", STONE_C["moss"])  # moss mottle: a slightly deeper green and the moss
# the massif's stone: the same warm grey, deeper. A mountain is mostly sunlit slope, so its albedo shows ×1.5 lighter
# on screen: #BDB3A3 read L* 85 (a pale ghost whose snow caps vanished), #80786B ≈ 75 — still a pale mound at the
# world zoom; #7E6F5A keeps a mid-value massif under snow caps. Warmer than the rocks' grey (b* 14–19, the shoulders
# a pale sand): under the warm sun the lit side reads warm, and the shade side, where soft_light adds the blue sky
# ambient and its lilac fill, reads lilac — a temperature split that carries the form at the world zoom
MOUNTAIN_C = {"base": "#7E6F5A", "warm": "#8A7A62", "top": "#A38F70"}


def rock_paint(c1=STONE_C["base"], c2="#A89D8B", moss=MOSS_C, moss_at=0.62, scale=7.0, top=STONE_C["top"],
               shade_c=STONE_C["shade"], speck=0.1):
    """Loose stones and boulders. «Raivon Soft» (§6.3, §6.8): warm grey c1 with big soft patches of c2, the warm
    `top` colour on the up-facing faces, the lilac `shade_c` on the faces that turn down (a shade hue, never a darker
    grey), a faint speckle (0.1, was 0.35: nothing finer than the eye holds at map zoom) and moss on the up-facing
    faces. top=None and shade_c=None give the old faceted-stone paint (speckle and underside in shade(c1)), which the
    mine keeps."""
    def build():
        p = Paint("rockpaint")
        under = shade_c or shade(c1, 0.72)
        col = p.mix(p.step(p.noise(scale, 4.0 if top is None else 2.0), 0.3, 0.7), c1, c2)
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(scale * 5, 2.0), 0.55, 0.75), speck), col,
                    shade(c1, 0.7) if shade_c is None else shade_c)
        if top:
            col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.6, 0.95), 0.7), col, top)
        col = p.mix(p.step(p.nz, 0.1, -0.5), col, under)
        if moss:
            mf = p.math("ADD", p.nz, p.math("MULTIPLY", p.math("SUBTRACT", p.noise(6.0, 3.0), 0.5), 0.7))
            mcol = p.mix(p.step(p.noise(14.0), 0.35, 0.65), moss[0], moss[1])
            col = p.mix(p.step(mf, moss_at, moss_at + 0.12), col, mcol)
        return p.done(col, 0.9)
    return cached(("rock", c1, c2, moss, moss_at, scale, top, shade_c, speck), build)


def granite_paint(base=STONE_C["base"], top=STONE_C["top"], shade_c=STONE_C["shade"], moss=MOSS_C, moss_at=0.8,
                  scale=4.0, cracks=0.1, moss_z=0.08, cover=0.3, warm="#A89D8B", lilac=0.5):
    """The big rounded stone blocks of «Raivon Soft» (§6.3, §6.8: «тёплый серый, лиловая тень, мох»), for soft_block:
    - warm grey `base` (STONE_C: §6.3's #BDB3A3, deeper, see there) in a few big soft patches of `warm`, a very
      faint banding;
    - a warm cream `top` on the faces turned to the sky (the broad slanted top of every block; see STONE_C);
    - lilac `shade_c` (#8C86A0) on the steep and down-turned faces (up to `lilac` of it: 0.5, was 0.75, which with
      the blue sky ambient and the lilac shade fill of soft_light read as lilac porcelain rather than warm grey) and
      a little at the foot — the shade side leans to the §6.3 shade hue instead of going grey (§6.1 rule 3), so a
      block reads as a lit top over lilac flanks; the AO bake darkens the creases on top of it;
    - joints between upright blocks only as a hint (cracks 0.1, was 0.4, and in the lilac shade, not near-black);
    - soft patches of spring-green moss on the flattest high tops (about `cover` of them; none below moss_z)."""
    def build():
        p = Paint("granite")
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(scale, 2.0), 0.35, 0.65), 0.7), base, warm)
        band = p.noise(scale * 0.5, 2.0, stretch=(1.0, 1.0, 8.0))
        col = p.mix(p.math("MULTIPLY", p.step(band, 0.5, 0.68), 0.15), col, shade(base, 0.9))
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.6, 0.95), 0.7), col, top)
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.55, -0.05), lilac), col, shade_c)
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, -0.15, -0.7), 0.6), col, shade_c)
        col = p.mix(p.math("MULTIPLY", p.step(p.z, 0.05, 0.0), 0.3), col, shade_c)  # grounded foot
        if cracks:  # a hint of jointing: upright blocks of a slightly different tone, parted by soft lilac lines
            vs = (1.0, 1.0, 0.15)
            _, cell = p.voronoi(scale * 2.0, "F1", vs)
            col = p.mix(p.math("MULTIPLY", p.step(cell, 0.4, 0.1), 0.15), col, shade(base, 0.92))
            edge, _ = p.voronoi(scale * 2.0, "DISTANCE_TO_EDGE", vs)
            steep = p.step(p.nz, 0.7, 0.35)
            fis = p.math("MULTIPLY", p.step(edge, 0.06, 0.02), steep)
            col = p.mix(p.math("MULTIPLY", fis, cracks), col, shade_c)
        if moss:  # soft solid patches, flattest high tops only
            lo = 0.5 + (0.5 - cover) * 0.26  # noise Fac ≈ N(0.5, 0.1): P(Fac > lo) ≈ cover
            patch = p.step(p.noise(scale * 2.4, 2.0), lo - 0.02, lo + 0.05)
            mf = p.math("MULTIPLY", p.math("MULTIPLY", p.step(p.nz, moss_at, moss_at + 0.1), patch),
                        p.step(p.z, moss_z, moss_z + 0.03))
            mcol = p.mix(p.step(p.noise(10.0, 2.0), 0.35, 0.65), moss[0], moss[1])
            col = p.mix(mf, col, mcol)
        return p.done(col, 0.9)
    return cached(("granite", base, top, shade_c, moss, moss_at, scale, cracks, moss_z, cover, warm, lilac), build)


def soft_block(cx, cy_, w, d, h, mt, seed, z0=-0.02, rz=0.0, cuts=(6, 10), sub=2, bevel=0.1, segs=2, top=0.62,
               ground=0.15, sharp=50.0, min_bevel=0.08, taper=0.0, top_el=(1.05, 1.35), lean=(0.0, 0.0)):
    """A big rounded block of stone of «Raivon Soft» (§6.8: «крупные скруглённые глыбы, фаска 10 %, 2 сегмента») —
    it replaces the old sharp convex-hull tors.
    - An icosphere (sub 2) is cut by 6–10 random planes, each hole filled with one flat face: a chunky pebble whose
      flat faces meet in what is left of the sphere, so its corners are round. The first cut is a broad slanted top
      (normal 60–77° up), the face the paint lights with the «top» colour; the others go round the flanks.
    - It is stretched to the block's real footprint w × d (as the tors') with its top at z0 + h and its equator
      ground·h above z0 (the widest part near the grass: the stone sits in the ground, never on a point), turned rz,
      moved to (cx, cy_), and its part under the ground is dropped (never seen, no triangles spent).
    - The edges sharper than `sharp`° get a round bevel of `bevel` × the smallest size in `segs` segments — only on
      blocks whose smallest size is at least min_bevel (§6.2: bevels only where they show, on masses ≥ 0.08).
    - Normals: WEIGHTED_NORMAL (face area), so each big face stays one calm plane and the bevels and the round
      corners shade softly into it — a soft toy stone instead of a faceted gem. Applied by bake_asset's convert.
    Edges between 24° and 50° (a flat face meeting the sphere's rest) already shade soft under the weighted normals,
    so the bevel goes to the face-to-face edges that read as sharp: ≈ 90 triangles a block before the bevel and
    ≈ 60–110 for it (beveling every edge over 24° cost 400–500 a block). sub=1 with bevel=0 is for pebbles (scree,
    loose stones): about 30–45 triangles where nobody sees more.
    taper (0 = a pebble's straight flanks): the footprint shrinks to (1 − taper) of itself at the top, so a tall
    block becomes a rounded rock tooth — the peaks of the mountain massif; top_el: the elevation range (rad) of the
    top cut's normal (lower = a steeper crest); lean (dx, dy): the top shifts by that much, the foot stays."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    # turn the sphere at random first, so no two blocks share the icosphere's vertex pattern
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(rnd.uniform(0, math.tau), 3, "Z")
                     @ Matrix.Rotation(rnd.uniform(-0.4, 0.4), 3, "X"))
    n_cuts = rnd.randint(*cuts)
    az0 = rnd.uniform(0, math.tau)
    for k in range(n_cuts):
        if k == 0:  # the broad top face, slanted a little
            el, off, az = rnd.uniform(*top_el), rnd.uniform(top, top + 0.1), rnd.uniform(0, math.tau)
        else:  # flanks all round (spread evenly with jitter), a few tilted up or down
            az = az0 + k / max(1, n_cuts - 1) * math.tau + rnd.uniform(-0.35, 0.35)
            el, off = rnd.uniform(-0.2, 0.55), rnd.uniform(0.68, 0.86)
        nrm = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=nrm * off,
                                     plane_no=nrm, clear_outer=True)
        rim = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
        if rim:
            bmesh.ops.holes_fill(bm, edges=rim, sides=0)
    xs, ys = [v.co.x for v in bm.verts], [v.co.y for v in bm.verts]
    mx, my = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    sx, sy = w / (max(xs) - min(xs)), d / (max(ys) - min(ys))
    sz = h * (1.0 - ground) / max(v.co.z for v in bm.verts)
    c, s_ = math.cos(rz), math.sin(rz)
    for v in bm.verts:
        x, y, z = (v.co.x - mx) * sx, (v.co.y - my) * sy, z0 + ground * h + v.co.z * sz
        t = min(1.0, max(0.0, (z - z0) / h))
        x, y = x * (1.0 - taper * t), y * (1.0 - taper * t)
        v.co = Vector((cx + x * c - y * s_ + lean[0] * t, cy_ + x * s_ + y * c + lean[1] * t, z))
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z0), plane_no=(0, 0, 1),
                           clear_inner=True)
    if bevel and segs and min(w, d, h) >= min_bevel:
        edges = [e for e in bm.edges if not e.is_boundary and len(e.link_faces) == 2
                 and e.calc_face_angle(0.0) > math.radians(sharp)]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=bevel * min(w, d, h), segments=segs, profile=0.5,
                            affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("block")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("block", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mt)
    for p in o.data.polygons:
        p.use_smooth = True
    wn = o.modifiers.new("soft", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.weight = 50
    wn.keep_sharp = False
    o["flat"] = True  # ev.lowpoly leaves it alone (no smooth-by-angle over the weighted normals)
    o["block"] = True  # convex: cull_hidden may test points against it
    return o


def cull_hidden(objs, margin=0.003):
    """Drop the faces of stacked soft blocks that lie wholly inside another block (built in world coordinates,
    convex: an icosphere cut by planes, beveled; open at the ground). The crag's ridge blocks interpenetrate deeply,
    so a good share of their triangles was never visible — and invisible faces still cost overdraw and texels."""
    planes = {}
    for o in objs:
        me = o.data
        planes[o.name] = [(Vector(p.normal), Vector(p.center)) for p in me.polygons]
    dropped = 0
    for o in objs:
        others = [planes[x.name] for x in objs if x is not o]
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        dead = [f for f in bm.faces if any(all(all(n.dot(v.co - c) < -margin for n, c in pl) for v in f.verts)
                                            for pl in others)]
        if dead:
            dropped += sum(len(f.verts) - 2 for f in dead)
            bmesh.ops.delete(bm, geom=dead, context="FACES")
            bm.to_mesh(me)
        bm.free()
    return dropped


def mountain_paint(grass_line=0.15, snow_edge=0.24):
    """The B6 heightfield massif's paint; since art pass 5 only the grassy foot of mountain() uses it (grass_line
    above the foot's top: all meadow). «Raivon Soft» massif (§6.3, §6.8): a meadow-green foot
    (a step under the §6.3 plain #74A645) whose rim climbs the slopes in broad soft tongues → warm grey stone
    (MOUNTAIN_C, in big soft patches, a pale sandy tone on the shoulders, a faint lilac lean on the steepest flanks
    — the model turns at random on the map, so the paint can only follow the slope, not the sun: a warm albedo lets
    the sun light it warm and the sky ambient shade it lilac, so the form reads at the world zoom; no fine strata,
    speckle or scree band — they read as haze at map size) → a soft snow cap on the two big masses. The caps follow the "cap" point attribute that mountain() writes
    (1 at a mass's summit, 0 at its cap's rim, below 0 lower down), broken by a broad noise and leaning onto the
    flatter slopes; their edge is a smoothstep `snow_edge` wide. Snow is a pale blue-grey albedo, #C6CEDF lit and
    #A9B4CF in the shade, that the light lifts to blue-white: #E8EDF7 and even #D5DCEA clipped to pure #FFFFFF on the
    sunlit summits in game (flat white blobs without form, «white-hot» 3.4 % of a close mountain frame; §6.12 keeps
    white-hot for foam and clouds)."""
    def build():
        p = Paint("mountain")
        jit = p.math("MULTIPLY", p.math("SUBTRACT", p.noise(2.5, 2.0), 0.5), 0.22)  # broad tongues, no speckle
        zz = p.math("ADD", p.z, jit)
        # the massif's stone is the rocks' warm grey a step deeper (MOUNTAIN_C): a whole mountain of #BDB3A3 read as
        # a pale ghost under the soft light and lost its snow caps; mid-value stone keeps the sun's form shading
        rock = p.mix(p.math("MULTIPLY", p.step(p.noise(2.5, 2.0), 0.35, 0.65), 0.7), MOUNTAIN_C["base"],
                     MOUNTAIN_C["warm"])
        band = p.noise(1.6, 2.0, stretch=(1.0, 1.0, 6.0))
        rock = p.mix(p.math("MULTIPLY", p.step(band, 0.5, 0.7), 0.15), rock, shade(MOUNTAIN_C["base"], 0.9))
        # most of a massif faces the sky (nz 0.5–0.8): the pale sandy top colour on its shoulders, only a faint lilac
        # lean on the steepest flanks (0.45 below nz 0.2): the lilac of the shade comes from the light (soft_light's
        # sky ambient and lilac fill); painted lilac also turns the sunlit flanks pink (#C2B7BD, hue 341° at 0.7)
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.72, 0.92), 0.75), rock, MOUNTAIN_C["top"])
        rock = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.62, 0.2), 0.45), rock, STONE_C["shade"])
        # a step under the plain #74A645: the foot is lit by the wrap light and tilts to the sun, and a brighter apron
        # read as a lime disc round the mountains on the slate of the unexplored land
        grass = p.mix(p.step(p.noise(6.0, 2.0), 0.35, 0.65), "#5E9040", "#6C9E44")
        col = p.mix(p.step(zz, grass_line + 0.045, grass_line + 0.015), rock, grass)
        at = p.nt.nodes.new("ShaderNodeAttribute")
        at.attribute_name = "cap"
        sf = p.math("ADD", at.outputs["Fac"], p.math("MULTIPLY", p.math("SUBTRACT", p.noise(3.0, 2.0), 0.5), 0.5))
        sf = p.math("ADD", sf, p.math("MULTIPLY", p.math("SUBTRACT", p.nz, 0.6), 0.4))
        snow = p.mix(p.step(p.nz, 0.2, 0.8), "#A9B4CF", "#C6CEDF")
        col = p.mix(p.step(sf, 0.0, snow_edge), col, snow)
        return p.done(col, 0.9)
    return cached(("mountain", grass_line, snow_edge), build)


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


def pine_paint(dark="#2E6B3E", mid="#3F8A47", light="#8CC152", deep="#24563A", seed=0.0):
    """Conifer tiers of «Raivon Soft» (art direction §6.3, §6.8): on every tier deep green up under the tier above,
    then the dark green with big soft mid-green mottles, a mid-green band and sunlit yellow-green rims — the value
    steps of a cartoon pine. The tip factor (0.15 at the apex ring → 1 on the rim and the rolled lip) is the per-tier
    line tip_a + tip_b·z that soft_tier writes as two point attributes: constant over a tier, so the paint follows
    the height exactly (interpolating the per-vertex "tip" over the long apex-to-rim fan triangles drew a dark
    six-point star on every tier), wherever the tree stands and however it is scaled. Few, large colour patches
    (noise scale 5, detail 2) instead of the old needle speckle: nothing finer than the eye can hold at map zoom
    (§6.1 rule 5)."""
    def build():
        p = Paint("pine")
        ta, tb = (p.nt.nodes.new("ShaderNodeAttribute") for _ in range(2))
        ta.attribute_name, tb.attribute_name = "tip_a", "tip_b"
        tip = p.math("ADD", ta.outputs["Fac"], p.math("MULTIPLY", tb.outputs["Fac"], p.z))
        tip = p.math("MINIMUM", p.math("MAXIMUM", tip, 0.0), 1.0)
        # the visible band of a tier runs from tip ≈ 0.72 (just under the tier above, seen from the map camera) to the
        # rim: deep green up under the overhang → dark → a mid green band → the sunlit rim, so each tier reads as its
        # own layer (the value steps of a cartoon pine) while the base stays as dark as the forest ground needs
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(5.0, 2.0), 0.45, 0.75), 0.5), dark, mid)
        col = p.mix(p.math("MULTIPLY", p.step(tip, 0.84, 0.95), 0.5), col, mid)
        lit = p.math("MULTIPLY", p.step(tip, 0.93, 1.0), p.step(p.nz, -0.6, 0.2))
        lit = p.math("MULTIPLY", lit, p.math("ADD", 0.5, p.math("MULTIPLY", p.step(p.noise(4.0, 2.0), 0.3, 0.6), 0.3)))
        col = p.mix(lit, col, light)
        col = p.mix(p.math("MULTIPLY", p.step(tip, 0.84, 0.64), 0.85), col, deep)
        return p.done(col, 0.9)
    return cached(("pinepaint", dark, mid, light, deep, seed), build)


def soft_normals(o, fn):
    """Custom per-vertex normals (fn(co), or a list of one normal per vertex) on a part built in world coordinates
    (identity transform): the bake and the game shade it as one smooth volume, whatever its facets and scallops
    (§6.8, normals of one volume). The part is marked "flat", so ev.lowpoly's smooth-by-angle leaves them alone."""
    me = o.data
    for p in me.polygons:
        p.use_smooth = True
    ns = fn if isinstance(fn, list) else [fn(Vector(v.co)) for v in me.vertices]
    me.normals_split_custom_set_from_vertices([tuple(Vector(n).normalized()) for n in ns])
    o["flat"] = True
    return o


def _radial(c):
    """Horizontal unit vector from the vertical axis through c to a point (+X on the axis itself)."""
    def f(p):
        d = Vector((p.x - c[0], p.y - c[1], 0.0))
        return d.normalized() if d.length > 1e-6 else Vector((1.0, 0.0, 0.0))
    return f


def soft_tier(cx, cy_, z0, z1, r, mt, seed, n=24, waves=6, wave=0.1, droop=0.02, lip=0.02, apex=0.2, cap=False,
              up=0.6, na=12):
    """One pine tier of «Raivon Soft» (§6.8): a round skirt scalloped r(θ) = r·(1 + wave·cos 6θ) in n segments, its
    crests hanging `droop` lower like heavy branch ends; a rolled lip (one more ring `lip` in from the rim and `lip`
    under it), so the edge reads as a soft rounded rim instead of a blade; and a small apex ring of na vertices
    (apex·r) instead of a point, closed only when `cap` — lower apexes sit inside the tier above, and the ball on the
    top tier covers its hole. Twelve apex vertices, not six: from a six-vertex ring every vertex fanned four rim
    vertices, and at close zoom each tier read as a hexagonal pyramid (six straight ridges apex → rim). Normals come
    from a cone proxy, normalize(radial + up·0.6) (the lip rolls under: radial − up·0.25), so each tier shades as one
    soft volume. Writes the tip attributes for pine_paint (tip_attrs: apex 0.15 → rim 1, linear in height). Open
    underneath: the camera (pitch ≥ 40°) never looks up into it. 12 + 24 + 24 vertices, 84 triangles (94 capped)."""
    rnd = random.Random(seed)
    rot = rnd.uniform(0.0, math.tau)
    verts, tip = [], []
    for k in range(na):
        a = rot + k / na * math.tau
        verts.append((cx + r * apex * math.cos(a), cy_ + r * apex * math.sin(a), z1))
        tip.append(0.15)
    rims = []
    for k in range(n):
        a = rot + k / n * math.tau
        w = math.cos(waves * (a - rot))
        rr = r * (1.0 + wave * w)
        z = z0 - droop * (0.5 + 0.5 * w)
        rims.append((a, rr, z, w))
        verts.append((cx + rr * math.cos(a), cy_ + rr * math.sin(a), z))
        tip.append(0.9 + 0.1 * w)
    for a, rr, z, w in rims:  # the rolled lip
        verts.append((cx + (rr - lip) * math.cos(a), cy_ + (rr - lip) * math.sin(a), z - lip))
        tip.append(1.0)
    S, L = na, na + n
    per = n // na
    faces = []
    for i in range(na):  # apex ring → rim: a fan of `per` triangles per apex vertex and one bridge
        for j in range(per):
            faces.append((i, S + (i * per + j) % n, S + (i * per + j + 1) % n))
        faces.append((i, S + ((i + 1) * per) % n, (i + 1) % na))
    for k in range(n):  # rim → lip
        k1 = (k + 1) % n
        faces.append((S + k, L + k, L + k1))
        faces.append((S + k, L + k1, S + k1))
    if cap:
        faces.append(tuple(range(na)))
    o = poly(verts, faces, [mt], flat_shade=False, name="tier")
    tip_attrs(o, tip, 0.15 + 0.85 * z1 / (z1 - z0), -0.85 / (z1 - z0))
    rad = _radial((cx, cy_))
    soft_normals(o, [rad(Vector(v)) + Vector((0.0, 0.0, up if i < L else -0.25)) for i, v in enumerate(verts)])
    return o


def soft_trunk(x, y, rings, mt, n=6):
    """A smooth tapered trunk: rings [(z, r), ...] from below the ground up into the foliage, no caps (one end is
    under the grass, the other inside the crown), radial normals so its few sides read round. 2·n triangles a band."""
    verts = []
    for z, r in rings:
        for k in range(n):
            a = k / n * math.tau + 0.3
            verts.append((x + r * math.cos(a), y + r * math.sin(a), z))
    faces = []
    for i in range(len(rings) - 1):
        for k in range(n):
            a, b = i * n + k, i * n + (k + 1) % n
            faces.append((a, b, b + n, a + n))
    o = poly(verts, faces, [mt], flat_shade=False, name="trunk")
    return soft_normals(o, _radial((x, y)))


def tall_pine(x=0.0, y=0.0, s=1.0, seed=0, mt=None, bark=None, n=24, na=12, z=0.0):
    """«Raivon Soft» conifer (§6.8): three fat scalloped tiers (radii 0.24 / 0.19 / 0.13) with rolled rims, a ball
    on top and the trunk showing at the foot — stout, height ≈ 2.3× the bottom radius (was 3.2×), ~0.565·s tall.
    The bottom tier starts high (rim 0.25, droop 0.01, lip 0.015) and the tiers are packed tight above it, so a stub
    of brown trunk (r 0.055) shows under the skirt at the close-zoom pitch of 40° (camera_rig.gd) and in the upper
    half of the z03 frame: the front rim has to clear (0.24 − 0.055)·tan 40° ≈ 0.16, and the lowest crest of the
    rolled lip hangs at 0.225 (≈ 0.05 of trunk under a crest, ≈ 0.1 under a trough); below the middle of a close
    frame the perspective looks down at ≈ 45° and only the troughs show it. Droop and lip shrink with the tier
    radius, so every upper rim still hangs clear of the tier below (a deep-green band under each). 284
    triangles (three 84-triangle tiers, the 20-triangle ball that plugs the top apex ring, a 12-triangle trunk), one
    material besides the bark. n / na: the tiers' rim and apex segments; the small pines that cling to the crag and
    the mountain slopes use 18 / 9 (63-triangle tiers, 221 triangles a tree, still three rim points a scallop).
    z: the ground height under the trunk (a slope). Build the tree there rather than move it up afterwards:
    pine_paint reads the tiers' tip lines in model-space height, so a tree lifted after the build paints wrong."""
    rnd = random.Random(seed)
    mt = mt or pine_paint()
    bark = bark or tex("wood", BARK_SOFT)
    soft_trunk(x, y, [(z - 0.02 * s, 0.055 * s), (z + 0.34 * s, 0.036 * s)], bark)
    # (radius, rim z0, apex z1, droop, lip); the apex of a lower tier sits inside the tier above
    tiers = [(0.24, 0.25, 0.40, 0.01, 0.015), (0.19, 0.325, 0.475, 0.016, 0.016), (0.13, 0.41, 0.525, 0.011, 0.011)]
    for i, (r, z0, z1, droop, lip) in enumerate(tiers):
        ox, oy = rnd.uniform(-0.008, 0.008) * s, rnd.uniform(-0.008, 0.008) * s
        top = i == len(tiers) - 1
        # the top tier's apex ring is smaller (0.15·r ≈ 0.02) so the ball below covers it: no cap needed
        soft_tier(x + ox, y + oy, z + z0 * s, z + z1 * s, r * s, mt, seed * 10 + i, droop=droop * s, lip=lip * s,
                  apex=0.15 if top else 0.2, n=n, na=na)
    # the ball on the apex (tip 0.9: it catches the light like the rims); 0.01 above the apex ring, its section there
    # (≥ 0.021 even between the icosahedron's vertices) is wider than the ring (0.0195)
    c = Vector((x + ox, y + oy, z + (tiers[-1][2] + 0.01) * s))
    ball = soft_ball(0.03 * s, c, mt, sub=1)
    tip_attrs(ball, [0.9] * len(ball.data.vertices), 0.9, 0.0)


def tip_attrs(o, tip, a, b):
    """Tip point attributes: the per-vertex "tip" (as before) and the part's tip line tip_a + tip_b·z, which
    pine_paint reads (exact in height, see there)."""
    for name, vals in (("tip", tip), ("tip_a", [a] * len(tip)), ("tip_b", [b] * len(tip))):
        at = o.data.attributes.new(name, "FLOAT", "POINT")
        at.data.foreach_set("value", vals)


def soft_ball(r, c, mt, sub=1, scale=(1.0, 1.0, 1.0)):
    """A smooth icosphere built in world coordinates with sphere normals (ico sub 1: 20 triangles)."""
    us, fs = _ico(sub)
    verts = [c + Vector((u.x * r * scale[0], u.y * r * scale[1], u.z * r * scale[2])) for u in us]
    o = poly(verts, fs, [mt], flat_shade=False, name="ball")
    return soft_normals(o, lambda p: Vector(((p - c).x / scale[0], (p - c).y / scale[1], (p - c).z / scale[2])))


_ICO = {}


def _ico(sub):
    """Unit icosphere (vertex directions, faces): sub 1 = 20 triangles, sub 2 = 80."""
    if sub not in _ICO:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        bm.verts.index_update()
        _ICO[sub] = ([v.co.normalized() for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces])
        bm.free()
    return _ICO[sub]


# ------------------------------------------------------------------ assets


# art pass 6 (AP6): the forest spruce of reference frame 1 — the dark conifer masses of the strategic view. Four
# scalloped tiers instead of three, a little narrower at the foot and taller (0.64 instead of 0.565: 2.8× the bottom
# radius instead of 2.3×), so a wood reads as a stand of spruces whose crowns overlap in depth rather than a field of
# round cartoon pines; the body leans to the deep and shade greens of §6.3 (SPRUCE_C: the dark body at §6.3's deep
# #24563A, the mid-green mottles and band at its shade #2E6B3E, the sunlit tips a step softer; deep #1F4F37 stays
# over the §6.1 floor at L* 30) — in game the first, lighter set (#2A6340 / #38814A / #8CC152) still read as bright
# cartoon pines under the soft shader's lift, not as the dark masses of the reference. Same triangle count as the
# three-tier pine (284: four 63-triangle tiers of 18 / 9 segments, the ball, the trunk). The tiers:
# (radius, rim z0, apex z1, droop, lip); the apex of each sits inside the tier above
SPRUCE_TIERS = ((0.23, 0.2, 0.34, 0.01, 0.014), (0.19, 0.285, 0.425, 0.013, 0.014), (0.15, 0.375, 0.51, 0.011, 0.012),
                (0.105, 0.465, 0.585, 0.009, 0.01))
SPRUCE_C = dict(dark="#255C3C", mid="#2F6E42", light="#7FB84E", deep="#1F4F37")


def spruce(x=0.0, y=0.0, s=1.0, seed=0, mt=None, bark=None, n=18, na=9, z=0.0, tiers=SPRUCE_TIERS):
    """The forest spruce (art pass 6, see SPRUCE_TIERS): tall_pine's soft scalloped tiers with rolled rims, four of
    them, the ball on top and a stub of trunk under the skirt (the bottom rim at 0.2: (0.23 − 0.05)·tan 40° ≈ 0.15
    of trunk clears at the close pitch)."""
    rnd = random.Random(seed)
    mt = mt or pine_paint(**SPRUCE_C)
    bark = bark or tex("wood", BARK_SOFT)
    soft_trunk(x, y, [(z - 0.02 * s, 0.05 * s), (z + 0.3 * s, 0.033 * s)], bark)
    for i, (r, z0, z1, droop, lip) in enumerate(tiers):
        ox, oy = rnd.uniform(-0.007, 0.007) * s, rnd.uniform(-0.007, 0.007) * s
        top = i == len(tiers) - 1
        soft_tier(x + ox, y + oy, z + z0 * s, z + z1 * s, r * s, mt, seed * 10 + i, droop=droop * s, lip=lip * s,
                  apex=0.15 if top else 0.2, n=n, na=na)
    c = Vector((x + ox, y + oy, z + (tiers[-1][2] + 0.01) * s))
    ball = soft_ball(0.026 * s, c, mt, sub=1)
    tip_attrs(ball, [0.9] * len(ball.data.vertices), 0.9, 0.0)


def tree_pine():
    spruce(seed=3)


def crown_paint(dark, mid, light, deep, centre, radius):
    """Broadleaf crown of «Raivon Soft» (§6.3, §6.8): big soft patches of mid and dark green, a sunlit yellow-green
    cap, and a gentle "occlusion" that deepens the colour towards the crown's centre — the creases between the clumps
    go deep green, so the cushion keeps its lumps without a speckle."""
    def build():
        p = Paint("crown")
        vm = p.nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "DISTANCE"
        p.L.new(p.pos, vm.inputs[0])
        vm.inputs[1].default_value = centre
        occ = p.step(p.math("DIVIDE", vm.outputs["Value"], radius), 0.65, 1.0)
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(5.0, 2.0), 0.45, 0.75), 0.45), dark, mid)
        # the cap starts at nz 0.7 (was 0.65): cushion() tilts the normals up by 0.35, which would widen the lit cap
        top = p.math("MULTIPLY", p.step(p.nz, 0.7, 0.97), p.step(p.noise(4.0, 2.0), 0.3, 0.6))
        col = p.mix(p.math("MULTIPLY", top, p.math("MULTIPLY", occ, 0.45)), col, light)
        col = p.mix(p.math("MULTIPLY", p.math("SUBTRACT", 1.0, occ), 0.9), col, deep)
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, -0.2, -0.8), 0.5), col, deep)
        return p.done(col, 0.9)
    return cached(("crown", dark, mid, light, deep, tuple(centre), radius), build)


LEAF_C = ("#3B7A46", "#5DA040", "#A4D05C", "#2F6B3A")  # broadleaf dark / mid / lit / deep (§6.3)


class Lump:
    """One clump of a cushion crown: an icosphere of radius r round c, squashed by `scale`, its surface pushed
    out by up to ±jitter with smooth noise (the same function the cull test reads, so the cull is exact)."""

    def __init__(self, c, r, scale=(1.0, 1.0, 0.88), jitter=0.06, seed=0):
        self.c, self.r, self.s, self.j = Vector(c), r, Vector(scale), jitter
        self.off = Vector((seed * 1.7, seed * 0.3, 0.0))

    def k(self, u):
        return 1.0 + self.j * mnoise.noise(u * 2.3 + self.off)

    def at(self, u):
        return self.c + Vector((u.x * self.s.x, u.y * self.s.y, u.z * self.s.z)) * (self.r * self.k(u))

    def inside(self, p, margin=0.92):
        """True when p is inside this lump's mesh (margin < 1 keeps clear of the flat facets between vertices)."""
        q = p - self.c
        q = Vector((q.x / self.s.x, q.y / self.s.y, q.z / self.s.z)) / self.r
        d = q.length
        return d < 1e-9 or d < margin * self.k(q / d)


def cushion(lumps, mt, proxy, sub=2, ground=-0.004, w_proxy=0.5, w_lump=0.5, w_up=0.35):
    """A crown of «Raivon Soft» (§6.8): the lumps' icospheres joined into one mesh with every face hidden inside
    another lump or under the ground dropped (no overdraw, no wasted triangles). Normals: mostly those of one proxy
    ellipsoid (centre, (a, a, b)) enclosing the crown, so the crown shades as one cushion while its silhouette keeps
    the lumps — blended half and half with each lump's own normal and tilted up: normalize(0.5·proxy + 0.5·lump +
    0.35·up). With the proxy normal alone, a side lump that faces the camera reported a near-horizontal silhouette
    normal (N·V ≈ 0) and took the full fresnel rim of soft_light (0.2 × sun, white) plus wrap light over its whole
    face: it rendered as a pale, milky "ghost" lump (C* 27–30 next to 67–70). Blended, 3 % of the camera-facing
    vertices keep a rim term above 0.06 at pitch 40° (15 % before; 0.4 % at 56°), and each lump still shades softly
    into the next."""
    pc, pa = Vector(proxy[0]), Vector(proxy[1])
    us, fs = _ico(sub)
    verts, faces, normals = [], [], []
    for lump in lumps:
        pts = [lump.at(u) for u in us]
        others = [o for o in lumps if o is not lump]
        keep = [f for f in fs if not all(pts[i].z < ground for i in f)
                and not any(all(o.inside(pts[i]) for i in f) for o in others)]
        used = sorted({i for f in keep for i in f})
        remap = {i: len(verts) + n for n, i in enumerate(used)}
        verts.extend(pts[i] for i in used)
        faces.extend(tuple(remap[i] for i in f) for f in keep)
        for i in used:  # the lump's own (squashed-sphere) normal
            u = us[i]
            normals.append(Vector((u.x / lump.s.x, u.y / lump.s.y, u.z / lump.s.z)).normalized())
    up = Vector((0.0, 0.0, 1.0))
    for k, p in enumerate(verts):
        d = p - pc
        n_p = Vector((d.x / pa.x ** 2, d.y / pa.y ** 2, d.z / pa.z ** 2)).normalized()
        normals[k] = n_p * w_proxy + normals[k] * w_lump + up * w_up
    o = poly(verts, faces, [mt], flat_shade=False, name="crown")
    return soft_normals(o, normals)


def crown_surface(lumps, c, u, step=0.001):
    """Where a ray from c (inside the crown) along u leaves the crown."""
    t = 0.0
    while any(o.inside(c + u * t, 1.0) for o in lumps) and t < 1.0:
        t += step
    return c + u * t


def dome(c, r, n, mt, k=6):
    """A berry: a k-sided dome of radius r on the crown surface at c, facing n, its rim sunk a quarter radius into
    the leaves (the hidden half of a ball is never built) — sphere normals, k triangles."""
    n = Vector(n).normalized()
    e1 = n.orthogonal().normalized()
    e2 = n.cross(e1)
    verts = [c + n * r]
    for i in range(k):
        a = i / k * math.tau
        verts.append(c + (e1 * math.cos(a) + e2 * math.sin(a)) * r - n * (0.25 * r))
    o = poly(verts, [(0, 1 + i, 1 + (i + 1) % k) for i in range(k)], [mt], flat_shade=False, name="berry")
    return soft_normals(o, lambda p: p - c)


def lush_tree(x=0.0, y=0.0, s=1.15, seed=0):
    """«Raivon Soft» broadleaf (§6.8): a cushion crown of four merged clumps — three round the trunk and one on top —
    with the normals of one volume, on a stout trunk (≈ 23 % of the crown width) with a root flare. s = 1.15: the old
    tree ×1.15 — crown ≈ 0.40 wide (old 0.33–0.35) and ≈ 0.59 tall. The side clumps sit closer in and are a little
    smaller than the first soft build (0.46 wide, ×1.35), which merged the trees of a forest hex into one canopy."""
    rnd = random.Random(seed)
    cz = 0.33 * s
    leaf = crown_paint(*LEAF_C, (x, y, cz), 0.18 * s)
    bark = tex("wood", BARK_SOFT)
    soft_trunk(x, y, [(-0.02 * s, 0.058 * s), (0.04 * s, 0.043 * s), (0.27 * s, 0.033 * s)], bark)
    lumps = []
    for k in range(3):
        a = -math.pi / 2 + k * math.tau / 3 + rnd.uniform(-0.2, 0.2)
        d = rnd.uniform(0.07, 0.078) * s
        lumps.append(Lump((x + d * math.cos(a), y + d * math.sin(a), cz - rnd.uniform(0.0, 0.02) * s),
                          rnd.uniform(0.112, 0.121) * s, seed=seed * 7 + k))
    lumps.append(Lump((x + 0.01 * s, y + 0.012 * s, cz + 0.085 * s), 0.115 * s, seed=seed * 7 + 3))  # the top clump
    cushion(lumps, leaf, ((x, y, cz + 0.02 * s), (0.21 * s, 0.21 * s, 0.2 * s)))


def tree_round():
    lush_tree(seed=2)


def bush():
    """«Raivon Soft» bush (§6.8): a low cushion of three tightly merged clumps with the normals of one volume, as big
    as the old bush ×1.15 (0.30 × 0.23 × 0.16), and four round berries (r 0.02, was six) — a red accent that still
    reads at map size. ≤ 200 triangles."""
    s = 1.34  # the clumps overlap more than the old ones (one cushion): ×1.34 on their layout = the old size ×1.15
    leaf = crown_paint(*LEAF_C, (0.0, 0.0, 0.03 * s), 0.12 * s)
    lumps = [Lump((0.0, 0.0, 0.045 * s), 0.085 * s, (1.0, 1.0, 0.85), seed=40),
             Lump((0.045 * s, -0.02 * s, 0.033 * s), 0.065 * s, (1.0, 1.0, 0.85), seed=41),
             Lump((-0.042 * s, 0.016 * s, 0.033 * s), 0.068 * s, (1.0, 1.0, 0.85), seed=42)]
    cushion(lumps, leaf, ((0.0, 0.0, 0.03 * s), (0.15 * s, 0.15 * s, 0.11 * s)))
    berry = flat("berry", "#e0304a", 0.6)
    c = Vector((0.0, 0.0, 0.03 * s))
    for az, el in ((-60, 28), (-140, 40), (40, 30), (150, 58)):  # two on the camera side, one aside, one on top
        u = Vector((math.cos(math.radians(az)) * math.cos(math.radians(el)),
                    math.sin(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
        dome(crown_surface(lumps, c, u), 0.02, u, berry)


def petal_disc(x, y, z, r, mt, centre_mt, rnd, lobes=5):
    """A flower head of «Raivon Soft» (§6.8): a flat five-lobed petal disc (slightly domed, tilted a little towards
    a random side) and a round flat centre just above it; up-facing normals, so it reads as one bright dot."""
    tilt = Vector((rnd.uniform(-0.25, 0.25), rnd.uniform(-0.25, 0.25), 1.0)).normalized()
    rot = Matrix.Rotation(rnd.uniform(0, math.tau), 3, "Z")
    q = Vector((0, 0, 1)).rotation_difference(tilt).to_matrix() @ rot
    o0 = Vector((x, y, z))
    n = lobes * 3
    verts = [o0 + q @ Vector((0, 0, 0.004))]
    for k in range(n):
        a = k / n * math.tau
        rr = r * (0.78 + 0.22 * math.cos(lobes * a))
        verts.append(o0 + q @ Vector((rr * math.cos(a), rr * math.sin(a), 0.0)))
    faces = [(0, 1 + k, 1 + (k + 1) % n) for k in range(n)]
    o = poly(verts, faces, [mt], flat_shade=False, name="petals")
    soft_normals(o, lambda p: tilt * 2.0 + (p - o0) * 4.0)
    cv = [o0 + q @ Vector((0, 0, 0.006))]
    for k in range(6):
        a = k / 6 * math.tau
        cv.append(o0 + q @ Vector((r * 0.32 * math.cos(a), r * 0.32 * math.sin(a), 0.0045)))
    c = poly(cv, [(0, 1 + k, 1 + (k + 1) % 6) for k in range(6)], [centre_mt], flat_shade=False, name="centre")
    soft_normals(c, lambda p: tilt)


def flowers():
    """A patch of wild flowers (§6.8): five bigger heads (×1.4) of flat petal discs on short stems, among four
    chunky grass tufts. ≤ 174 triangles (as before)."""
    grass = zgrad("#4a8a2c", "#6db23a", "#a4d05c", 0.0, 0.07)
    rnd = random.Random(8)
    for i in range(4):
        a = i / 4 * math.tau + rnd.uniform(-0.4, 0.4)
        r = rnd.uniform(0.04, 0.11)
        x, y = math.cos(a) * r, math.sin(a) * r
        for j in range(3):  # 3 blades per tuft
            b = rnd.uniform(0, math.tau)
            ev.rod((x, y, 0.0), (x + 0.025 * math.cos(b), y + 0.025 * math.sin(b), rnd.uniform(0.05, 0.075)), 0.011,
                   grass, r2=0.0, n=3)
    # cream, not white: a white head is a «white-hot» pixel at map zoom (§6.12)
    cols = [("#ffeeb8", "#f2b51e"), ("#ffd23f", "#e07a1f"), ("#f0679a", "#f2b51e"), ("#b58cff", "#f2d04a"),
            ("#ff8a3d", "#ffd23f")]
    for i, (c, cc) in enumerate(cols):
        a = i / len(cols) * math.tau + rnd.uniform(-0.3, 0.3)
        r = rnd.uniform(0.03, 0.12)
        x, y, z = math.cos(a) * r, math.sin(a) * r, rnd.uniform(0.045, 0.075)
        ev.rod((x, y, 0), (x, y, z), 0.006, grass, r2=0.0, n=3)
        petal_disc(x, y, z, 0.028, flat("petal" + c, c, 0.6), flat("flower_c" + cc, cc, 0.6), rnd)


def rock():
    """«Raivon Soft» outcrop (§6.8: «крупные скруглённые глыбы»): three big rounded blocks — a leaning main block, a
    second one and a low slab at its foot — and two loose stones, in warm grey with pale tops, lilac shade and a
    little moss (granite_paint). The faces hidden inside a neighbour are dropped.
    239 triangles, under the tree budget (§6.2: ≤ 300): rocks are scattered by the dozen over the badlands, taiga and
    hills hexes (≈ 140 of them from chapter III on) and drawn as one map-wide MultiMesh, so every triangle here is
    paid ≈ 140 times in every frame (485 cost ≈ +48 k primitives a frame). So only the main block keeps the round
    2-segment bevel, on its sharpest edges (> 70°: the top's rim and the face-to-face corners that catch the light);
    the second block, the slab and the stones are cut icosahedra (sub 1) under the soft weighted normals, which read
    just as round at map size. The second block takes 4–5 cuts, the slab 2–3 and the stones only the ground cut (a
    plain icosahedron: a round pebble) — fewer than soft_block's 6–10, which only add n-gon fans on a small stone."""
    mt = granite_paint(moss_at=0.72, scale=6.0, moss_z=0.1, cover=0.4)
    blocks = [soft_block(0.0, 0.02, 0.25, 0.2, 0.19, mt, 11, rz=0.3, sharp=70.0),
              soft_block(0.15, -0.07, 0.14, 0.12, 0.11, mt, 12, rz=-0.4, sub=1, cuts=(4, 5), bevel=0),
              soft_block(-0.13, 0.07, 0.15, 0.13, 0.07, mt, 13, rz=0.8, sub=1, cuts=(2, 3), bevel=0),  # the slab
              soft_block(0.05, -0.16, 0.09, 0.08, 0.07, mt, 14, sub=1, cuts=(0, 0), bevel=0),  # two loose stones
              soft_block(-0.11, -0.1, 0.075, 0.065, 0.06, mt, 15, sub=1, cuts=(0, 0), bevel=0)]
    cull_hidden(blocks)


def crag():
    """Hills hex (the rocky outcrops of the reference frames), «Raivon Soft» (§6.8): a ridge of five big rounded
    blocks rising toward the back, two broad ledges in front, four round stones at their foot (the scree, 12 → 4)
    and pines clinging to it. Two tones of warm grey stone (the summit and back blocks a step deeper) with pale tops,
    lilac shade and moss on the flattest tops; the faces buried in a neighbouring block are dropped. ≤ 1500
    triangles: the blocks ≈ 1000, two pines of 18-segment tiers (221 each; four 284-triangle B5 pines alone would
    take 1136)."""
    mt = granite_paint(moss_at=0.75, moss_z=0.1, cover=0.4)
    deep = granite_paint(base="#998E7D", top="#9C8E79", moss=None, warm="#9E9383")
    big = dict(cuts=(4, 6), sharp=60.0, ground=0.05)  # 4–6 cuts and the sharpest edges only: ≈ 120 triangles a block
    blocks = [
        # the main ridge: broad rounded blocks rising toward the back, the summit block stacked on them
        soft_block(-0.12, 0.15, 0.42, 0.34, 0.34, mt, 41, rz=0.15, **big),
        soft_block(0.2, 0.13, 0.36, 0.3, 0.28, mt, 42, rz=-0.35, **big),
        soft_block(0.05, 0.3, 0.42, 0.3, 0.32, deep, 50, rz=0.4, **big),
        soft_block(-0.03, 0.22, 0.32, 0.27, 0.27, deep, 49, z0=0.22, rz=-0.2, **big),  # the summit, on top
        soft_block(-0.38, 0.0, 0.26, 0.22, 0.2, deep, 43, rz=0.5, **big),
        # two broad ledges in front
        soft_block(0.03, -0.1, 0.32, 0.18, 0.12, mt, 45, rz=0.05, **big),
        soft_block(0.38, -0.08, 0.2, 0.17, 0.14, mt, 44, rz=-0.6, **big),
    ]
    rnd = random.Random(48)
    for k, (x, y) in enumerate(((-0.3, -0.26), (-0.12, -0.33), (0.2, -0.3), (0.42, -0.3))):  # the scree
        r = rnd.uniform(0.032, 0.045)
        blocks.append(soft_block(x + rnd.uniform(-0.03, 0.03), y + rnd.uniform(-0.03, 0.03), 2.1 * r, 1.8 * r,
                                 1.5 * r, deep if k % 2 else mt, 60 + k, sub=1, cuts=(1, 2), bevel=0))
    cull_hidden(blocks)
    for (x, y, sc) in ((0.47, 0.3, 0.84), (-0.5, 0.3, 0.88)):
        tall_pine(x, y, sc, seed=int(abs(x) * 100 + abs(y) * 10), n=18, na=9)


# art pass 5 (A1): the massif's rock — a cool mid grey after the grey alpine peaks of reference frames 1–3 (the old
# warm #7E6F5A read as a sand pile in game), a pale lit top on the up-facing facets, lilac on the steep and turned-away
# ones; the light lifts a mountain's albedo ≈ ×1.4 on screen, so the base sits at L* ≈ 50 (≈ 68–72 lit)
MASSIF_C = {"base": "#7D7873", "warm": "#87817A", "top": "#A29B8F", "shade": "#7C7892", "deep": "#6E6A6C"}


# the massif's snow (A1 review): a blue-white albedo, lit / shade. The light lifts it ≈ ×1.14 on screen and washes
# out its saturation: #B4C0DA (S 0.17) came out as (206, 217, 239) — V 0.94 S 0.14, inside the §6.12 «white-hot» band
# (V > 0.92 and S < 0.18) — and with caps over the top 33–39 % of each peak and on every facet tilted up past 0.3 it
# frosted the main peak two thirds of the way down. The reviewer's #A3AFCB / #97A3C2 on the crest facets only
# (SNOW_NZ 0.58, caps 22 / 20 / 15 %) left a pale lilac tip that vanished at the strategic zoom (no brighter than the
# rock's pale top #A29B8F); now a bluer snow (S ≈ 0.24: on screen S ≥ 0.18, out of the white-hot band however bright)
# on the up-facing facets past 0.5 — a soft cap that reads at the map zoom
SNOW_LIT, SNOW_SHADE, SNOW_NZ = "#A8B6DC", "#98A6CC", 0.5


def massif_paint(snow_z=0.6, snow_nz=SNOW_NZ):
    """The rock teeth of the massif (art pass 5): MASSIF_C grey in big soft patches and faint horizontal strata (the
    layered cliffs of reference frame 3), a pale top on the up-facing facets, lilac on the steep and turned-away
    ones, a deeper grey low down; soft snow caps (SNOW_LIT / SNOW_SHADE) on the up-facing crest facets of the high
    blocks (above snow_z, normal z over snow_nz, both edges broken by a broad noise; the flanks stay bare rock), so a
    peak reads as a soft snow cap over grey crags (§6.8), not as a frosted slab."""
    def build():
        p = Paint("massif")
        col = p.mix(p.math("MULTIPLY", p.step(p.noise(3.0, 2.0), 0.35, 0.65), 0.7), MASSIF_C["base"], MASSIF_C["warm"])
        band = p.noise(2.2, 2.0, stretch=(0.6, 0.6, 9.0))  # strata: flat bands in height
        col = p.mix(p.math("MULTIPLY", p.step(band, 0.48, 0.62), 0.35), col, MASSIF_C["deep"])
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.55, 0.9), 0.75), col, MASSIF_C["top"])
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.4, -0.1), 0.55), col, MASSIF_C["shade"])
        col = p.mix(p.math("MULTIPLY", p.step(p.z, 0.22, 0.04), 0.4), col, MASSIF_C["deep"])
        jit = p.math("MULTIPLY", p.math("SUBTRACT", p.noise(3.5, 2.0), 0.5), 0.45)  # a ragged snow line
        sf = p.math("MULTIPLY", p.step(p.math("ADD", p.z, jit), snow_z - 0.03, snow_z + 0.05),
                    p.step(p.math("ADD", p.nz, p.math("MULTIPLY", jit, 0.6)), snow_nz - 0.08, snow_nz + 0.08))
        snow = p.mix(p.step(p.nz, 0.6, 0.95), SNOW_SHADE, SNOW_LIT)
        col = p.mix(sf, col, snow)
        return p.done(col, 0.9)
    return cached(("massif", snow_z, snow_nz), build)


def _mound(x, y):
    """Height of the massif's grassy foot at (x, y): one broad low dome (0.26 high) with a lobed rim, so the rock
    teeth rise out of a hill rather than stand on the flat hex; it sinks a little at the rim (skirt below)."""
    r = math.hypot(x, y)
    th = math.atan2(y, x)
    R = 0.8 * (1 + 0.08 * math.sin(3 * th + 0.7) + 0.04 * math.sin(5 * th + 2.0))
    t = min(1.0, max(0.0, 1 - r / R))
    h = 0.26 * t * t * (3 - 2 * t)
    v = Vector((x * 3.0, y * 3.0, 0.4))
    h += 0.025 * mnoise.noise(v) * t
    return h - 0.03 * min(1.0, max(0.0, (r - 0.7) / 0.1))


# the rock masses of the massif: (x, y, w, d, h, z0, taper, seed, rz, lean, snow) — snow caps over the top `snow`
# share of a block's height (0 = bare rock), all leaning together.
# A1 review in game: the first teeth (taper 0.55–0.62, 5–7 cuts, a steep top cut) read on the map as a cluster of grey
# crystals; A1 made them broader, blunter and cut 7–9 times under a flatter top. Art pass 6 (A1 review 2: «the front
# low block and the right slab read as rounded standing stones, not a ridge of peaks as in ref1/ref3»): a long ridge
# body (the first block: 1.42 wide, a crest at 0.6) now joins the three peaks, so they rise out of one mass with
# saddles between them; the peaks are pointier (taper 0.66–0.7) and stand on the ridge's back half, so the ridge's
# front slope covers their feet; one broad back shoulder; two low spurs in front that lean back (their front faces
# slope instead of standing upright). MASSIF_SNOW_NZ: the peaks' snow takes facets tilted up past 0.4 (the pointier
# faces are steeper: at 0.5 the caps shrank to the tips)
MASSIF = [
    (0.0, 0.1, 1.42, 0.76, 0.6, 0.05, 0.64, 310, 0.15, (0.0, 0.02), 0.1),  # the ridge body
    (0.0, 0.18, 0.8, 0.68, 1.0, 0.06, 0.66, 301, 0.3, (0.02, -0.02), 0.32),  # the main peak
    (0.44, 0.14, 0.6, 0.55, 0.74, 0.05, 0.7, 302, -0.5, (-0.05, 0.0), 0.28),
    (-0.46, 0.1, 0.58, 0.52, 0.66, 0.05, 0.7, 303, 0.9, (0.05, 0.0), 0.26),
    (0.0, 0.44, 1.1, 0.4, 0.5, 0.04, 0.55, 304, 0.1, (0.0, -0.03), 0.0),  # the back shoulder
    (0.14, -0.26, 0.55, 0.32, 0.24, 0.04, 0.5, 306, 0.1, (0.0, 0.07), 0.0),  # two spurs in front
    (-0.32, -0.2, 0.36, 0.28, 0.2, 0.04, 0.45, 309, 0.5, (0.03, 0.05), 0.0),
]
MASSIF_SNOW_NZ = 0.4


def mountain():
    """Mountain massif, art pass 5 (A1) after the grey alpine peaks of reference frames 1–3 in «Raivon Soft» (§6.8:
    «горы — 3 мягких массива, снег мягкими шапками»). The B6 massif — one smooth heightfield of three blended masses —
    read in game as a single beige cone (a sand pile or a volcano) on a lime apron. Now three rock teeth rise out of
    a grassy hill: tall soft blocks (soft_block with taper: an icosahedron cut by planes into broad facets with
    round 14 % bevels, narrowing to a rounded crest) in cool grey with pale tops, lilac shade and faint strata, snow caps on
    the up-facing facets of the three peaks, shoulder blocks and a front ledge round them (the faces buried in a
    neighbour dropped), a few pebbles and the soft pines of the forests on the foot. Art pass 6: a ridge body joins
    the peaks (see MASSIF) and the slopes carry the forest spruces. Footprint radius 0.8 (the old one); the map scales
    it ×1.5–1.75 on a mountain hex and ×1.5–2.8 on the horizon."""
    grass = mountain_paint(grass_line=0.6)  # the old massif paint: below its grass line it is the meadow foot
    rings, segs, R = 8, 24, 0.82
    verts = [(0.0, 0.0, _mound(0.0, 0.0))]
    rnd = random.Random(21)
    for i in range(1, rings + 1):
        for j in range(segs):
            a = (j + (0.5 if i % 2 else 0.0)) / segs * math.tau + (rnd.uniform(-0.1, 0.1) / segs * math.tau if i < rings else 0)
            r = R * i / rings
            x, y = r * math.cos(a), r * math.sin(a)
            verts.append((x, y, _mound(x, y)))

    def vid(i, j):
        return 1 + (i - 1) * segs + (j % segs)

    faces = [(0, vid(1, j), vid(1, j + 1)) for j in range(segs)]
    for i in range(1, rings):
        for j in range(segs):
            a, b, c, d = vid(i, j), vid(i + 1, j), vid(i + 1, j + 1), vid(i, j + 1)
            faces += [(a, b, c), (a, c, d)] if i % 2 else [(a, b, d), (b, c, d)]
    base = len(verts)
    for j in range(segs):
        vx, vy, _ = verts[vid(rings, j)]
        verts.append((vx * 0.98, vy * 0.98, -0.12))
    for j in range(segs):
        a, b = vid(rings, j), vid(rings, j + 1)
        faces.append((a, base + j, base + (j + 1) % segs, b))
    foot = poly(verts, faces, [grass], flat_shade=False, name="foot")
    at = foot.data.attributes.new("cap", "FLOAT", "POINT")
    at.data.foreach_set("value", [-1.0] * len(verts))
    bvh = BVHTree.FromPolygons([Vector(v) for v in verts], faces)

    def height(x, y):
        hit = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0.0, 0.0, -1.0)))[0]
        return hit.z if hit is not None else 0.0

    blocks = []
    for (x, y, w, d, h, z0, taper, seed, rz, lean, cap) in MASSIF:
        mt = massif_paint(snow_z=round(z0 + (1.0 - cap) * h, 3) if cap else 9.0, snow_nz=MASSIF_SNOW_NZ)
        if taper > 0.3:  # peaks and shoulders: many cuts under a flat top → a rounded crest
            kw = dict(cuts=(7, 9), top_el=(1.15, 1.4), bevel=0.14)
        else:  # the low front ledge: a plain rounded rock
            kw = dict(cuts=(5, 7), top_el=(0.9, 1.2))
        blocks.append(soft_block(x, y, w, d, h, mt, seed, z0=z0, rz=rz, top=0.74, ground=0.05, sharp=55.0,
                                 taper=taper, lean=lean, **kw))
    cull_hidden(blocks)
    # pebbles and pines on the grassy foot, clear of the rock
    rk = granite_paint(moss_at=0.7, scale=6.0, moss_z=0.0, cover=0.4)
    for k, (a, r, s_) in enumerate([(4.4, 0.66, 0.05), (2.2, 0.7, 0.045), (5.8, 0.62, 0.04)]):
        x, y = r * math.cos(a), r * math.sin(a)
        z0 = height(x, y) - 0.02
        soft_block(x, y, s_ * 2.2, s_ * 1.8, s_ * 1.3, rk, 70 + k, z0=z0, rz=a, sub=1, cuts=(2, 3), bevel=0)
    # the slope pines in the forest spruces' darker greens (art pass 6), three tiers each to keep the triangle count
    pine_mt, bark = pine_paint(**SPRUCE_C), tex("wood", BARK_SOFT)
    for k, (a, r, s_) in enumerate([(4.95, 0.64, 0.5), (3.35, 0.66, 0.46), (1.25, 0.68, 0.44), (0.25, 0.7, 0.42),
                                    (4.0, 0.7, 0.4), (5.6, 0.7, 0.44)]):
        x, y = r * math.cos(a), r * math.sin(a)
        tall_pine(x, y, s_, 30 + k, pine_mt, bark, n=18, na=9, z=height(x, y) - 0.012)


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


def leafy_paint(dark, mid, light, z0, z1):
    """Leafy row crops: mottled greens, a sunlit crown on every clump, and deep shade low down (z0..z1) — between the
    clumps and under their rims — so each clump stands out as its own round plant."""
    def build():
        p = Paint("leafy")
        col = p.mix(p.step(p.noise(22.0, 3.0), 0.3, 0.65), dark, mid)
        col = p.mix(p.math("MULTIPLY", p.step(p.nz, 0.8, 0.98), 0.55), col, light)
        col = p.mix(p.math("MULTIPLY", p.step(p.z, z1, z0), 0.85), col, shade(dark, 0.6))
        return p.done(col, 0.9)
    return cached(("leafy", dark, mid, light, z0, z1), build)


def crop_row(x, y0, y1, body_mt, leaf_mt, rnd, w=0.08, step=0.05, z=0.066, rr=(0.027, 0.034), body_h=0.04):
    """A row of leafy crops (beet, potatoes, cabbage): a low green ridge under two staggered lines of round leafy
    clumps. Each clump is a squat five-leaf dome (height about half its width) with soft normals, so a row reads
    as rounded foliage, not as crystal shards; heads stay inside y0..y1 so the leaves keep to the soil bed."""
    ev.extrude([(-w / 2, 0.0), (w / 2, 0.0), (w * 0.36, body_h), (-w * 0.36, body_h)], -y1, -y0, body_mt,
               (x, 0, 0.025), (math.pi / 2, 0, 0))
    verts, faces = [], []
    n = max(2, round((y1 - y0) / step))
    for li in range(2):
        ox = (li - 0.5) * w * 0.48
        for j in range(n + (0 if li else 1)):
            r = rnd.uniform(*rr)
            t = (j + (0.5 if li else 0.0)) / n
            cx_ = x + ox + rnd.uniform(-0.006, 0.006)
            cy_ = y0 + r * 0.8 + (y1 - y0 - r * 1.6) * t + rnd.uniform(-0.005, 0.005)
            zm = z + rnd.uniform(-0.006, 0.01)
            b = len(verts)
            verts.append((cx_ + rnd.uniform(-0.004, 0.004), cy_ + rnd.uniform(-0.004, 0.004), zm + r * rnd.uniform(0.72, 0.86)))
            rot = rnd.uniform(0, math.tau)
            for k in range(5):
                a = rot + k * math.tau / 5 + rnd.uniform(-0.15, 0.15)
                rk = r * rnd.uniform(0.86, 1.12)
                verts.append((cx_ + rk * math.cos(a), cy_ + rk * math.sin(a), zm - r * rnd.uniform(0.05, 0.3)))
            for k in range(5):
                faces.append((b, b + 1 + k, b + 1 + (k + 1) % 5))
    o = poly(verts, faces, [leaf_mt], flat_shade=False, name="crops")
    o["flat"] = True  # keep the soft normals: lowpoly's 50° auto-smooth would split the squat domes into facets
    return o


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
    # two crops side by side; dark low down (ridge, clump rims), lit clump tops, so each clump stands out
    greens = (leafy_paint("#2f5a1c", "#4c8a2a", "#8cc244", 0.056, 0.08),
              leafy_paint("#3a6420", "#6a9a30", "#a8cf52", 0.056, 0.08))
    ripe = ripe_paint()
    rnd = random.Random(9)
    for i in range(8):  # leafy crop rows (heads on a ridge, not smooth bars); the two near rows ripe wheat
        x = -0.38 + i * 0.105
        if i >= 6:
            wheat_bed(x, -0.3, 0.3, ripe, ripe, rnd, w=0.09, step=0.036)
        else:
            g = greens[(i // 2) % 2]
            crop_row(x, -0.28, 0.28, g, g, rnd)
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


# art pass 6 (AP6): the quarry face of reference frame 4 as stepped terraces of straight cut blocks. A1's rounded
# boulders (soft_block) read as a rock pile, the pre-A1 sharp grey cubes as a crate of dice: now each tier is a row of
# dressed blocks (cut_block: a box with straight flanks and a bevelled rim, so it stays soft at map size)
# standing on the ledge of the tier below, set back 0.16 so every flat ledge shows as a light band over the dark
# riser below it — at the map pitch (≈ 50°) a riser of 0.18 and a ledge of 0.16 project to about the same height, the
# value rhythm of cut steps. The blocks part by MINE_GAP (the AO bake draws the joints), heights jitter by MINE_JIT
# and one block of the middle tier is half cut away (the work face). Rough rock shoulders close both ends.
# MINE_TIERS: (front y, back y, top height, half width), front to back
MINE_TIERS = ((0.0, 0.18, 0.24, 0.5), (0.16, 0.34, 0.42, 0.44), (0.32, 0.5, 0.6, 0.34))
MINE_W, MINE_GAP, MINE_JIT = (0.2, 0.27), 0.008, 0.025


def cut_block(cx, cy_, w, d, h, mt, z0=-0.01, rz=0.0, bev=0.018, segs=1):
    """A dressed stone block (art pass 6, the quarry tiers): a box w × d × h standing on z0, turned rz, with a bevel
    of `bev` on every edge (§6.2: bevels on masses ≥ 0.08) and weighted normals, so its faces stay calm planes and
    its edges catch a soft highlight. One segment: 44 triangles (two: 108 — the 13 blocks of the quarry would add
    ≈ 800 for an edge that reads the same at map size)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w, v.co.y * d, (v.co.z + 0.5) * h))
    bmesh.ops.bevel(bm, geom=bm.edges[:], offset=min(bev, 0.3 * min(w, d, h)), segments=segs, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    c, s_ = math.cos(rz), math.sin(rz)
    for v in bm.verts:
        x, y = v.co.x, v.co.y
        v.co = Vector((cx + x * c - y * s_, cy_ + x * s_ + y * c, z0 + v.co.z))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("cut_block")
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new("cut_block", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mt)
    for p in o.data.polygons:
        p.use_smooth = True
    wn = o.modifiers.new("soft", "WEIGHTED_NORMAL")
    wn.mode = "FACE_AREA"
    wn.weight = 50
    wn.keep_sharp = False
    o["flat"] = True
    o["block"] = True
    return o


def mine():
    dirt = ev.pad(0.6, ev.stone("#9a8f7f", 1.4), 0.012, 14, 0.12, 4, 1.0, 0.85)  # a flagged yard (reference frame 4)
    dirt.location.y = -0.12
    # the quarried cliff of reference frames 3–4: three terraces of cut blocks rising to the back (MINE_TIERS, see
    # there), a lighter and a deeper stone so neighbouring blocks part by tone as well as by the joint
    rnd = random.Random(9)
    cut = granite_paint(moss=None, cracks=0.0, scale=5.0)
    cut_d = granite_paint(base="#998E7D", top="#9C8E79", moss=None, warm="#9E9383", cracks=0.0, scale=5.0)
    blocks = []
    for t, (y0, y1, zmax, xr) in enumerate(MINE_TIERS):
        x = -xr
        k = 0
        while x < xr - 0.05:
            w = min(rnd.uniform(MINE_W[0], MINE_W[1]), xr - x)
            if xr - x - w < 0.1:  # no sliver at the end of a row
                w = xr - x
            h = zmax - rnd.uniform(0.0, MINE_JIT)
            d = y1 - y0
            if t == 1 and k == 2:  # the work face: a block half cut away, a step down in the middle tier
                h = zmax - 0.1
            blocks.append(cut_block(x + w / 2, (y0 + y1) / 2 + rnd.uniform(-0.008, 0.008), w - MINE_GAP, d, h,
                                    cut if (t + k) % 2 else cut_d, rz=rnd.uniform(-0.03, 0.03)))
            x += w
            k += 1
    # rough rock shoulders at both ends of the face and a rough crest over the top tier: the uncut hill the terraces
    # are cut into. They stay inside the pre-AP6 mine's footprint box (x −0.575..0.586, y ≤ 0.51): with the first
    # shoulders (x −0.66..0.61, y to 0.67) the model's AABB grew and pulled one more mine into the frame's frustum
    # at the edge of the close view (+1 draw, AP6 inventory)
    rough = granite_paint(moss_at=0.75, moss_z=0.1, cover=0.4)
    for (x, y, w, d, h, sd, rz) in ((-0.44, 0.33, 0.24, 0.28, 0.5, 41, 0.3), (0.45, 0.33, 0.23, 0.27, 0.46, 42, -0.4),
                                    (0.0, 0.43, 0.6, 0.14, 0.7, 43, 0.05)):
        blocks.append(soft_block(x, y, w, d, h, rough, sd, rz=rz, cuts=(4, 6), sharp=60.0, ground=0.05))
    cull_hidden(blocks)
    rk = granite_paint(moss_at=0.7, scale=6.0, moss_z=0.0, cover=0.4)
    soft_block(-0.48, 0.0, 0.2, 0.18, 0.13, rk, 31, sub=1, cuts=(2, 3), bevel=0)
    soft_block(0.5, 0.04, 0.18, 0.16, 0.11, rk, 32, sub=1, cuts=(2, 3), bevel=0)
    soft_block(-0.33, -0.2, 0.12, 0.1, 0.07, rk, 34, sub=1, cuts=(1, 2), bevel=0)
    # adit + timber frame
    bx((0.22, 0.12, 0.26), (0, -0.04, 0.13), flat("adit", "#2E2A30", 1.0), 0, 0.0)  # §6.1 rule 3: no albedo under ≈ #2A2A30
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
    ore = rock_paint("#5d5852", "#7a736a", moss=None, top=None, shade_c=None, speck=0.35)
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


def _blob(R, n=32, lobes=((3, 0.08, 1.0), (5, 0.05, 2.0)), sx=1.0, sy=1.0):
    """A soft rounded outline: r(θ) = R·(1 + Σ a·sin(kθ + φ)), n points (no corners, §6.1 rule 2)."""
    pts = []
    for i in range(n):
        t = i / n * math.tau
        r = R * (1.0 + sum(a * math.sin(k * t + ph) for k, a, ph in lobes))
        pts.append((sx * r * math.cos(t), sy * r * math.sin(t)))
    return pts


def dark_lake():
    """The Dark Lake (canon §5.1: dormant oil; art pass 5, A1) — replaces map_view's placeholder, a near-black 9-sided
    disc (0.07, 0.06, 0.12) with sharp corners and three loose rocks, the darkest and crudest shape on the map. A
    rounded pond (soft lobed outline, no corners) of still violet-black oil with an oily sheen (its own glossy
    material, kept out of the bake like the oil fields' crude, albedo #45406A: SoftLook clamps its metallic to 0.25, so
    the pond shows at about half its albedo's luminance — #2E2B42 measured L* ≈ 11 on screen in game, a black hole;
    #3E3A5C gave a median ≈ 15–18 but still 3.7 % of a close frame under L* 15 (A1 review); now a step lighter, still
    the darkest water on the map), pale
    lilac sheen streaks and a few oil bubbles on it; a ring of wet dark mud and a sandy shore that fades into the
    hex's grass; clumps of chunky reeds with brown heads, rounded mossy rocks and a dead stump on the shore."""
    shore = tex("plaster", "#B9A27E", 2.0)
    wet = tex("plaster", "#857360", 2.5)
    oil = kit.mat("dark_lake", "#45406A", 0.08, 0.55)
    ev.extrude(_blob(0.66, lobes=((3, 0.07, 1.0), (5, 0.04, 2.0))), -0.01, 0.008, shore)
    ev.extrude(_blob(0.6, lobes=((3, 0.08, 1.1), (5, 0.05, 2.1))), -0.01, 0.013, wet)
    ev.extrude(_blob(0.55, lobes=((3, 0.08, 1.1), (5, 0.05, 2.1))), -0.004, 0.017, oil)
    sheen = flat("lake_sheen", "#605D8A", 0.3)  # a step over the pond (was #57557E over #3E3A5C)
    for (x, y, a, b, rz) in ((-0.12, 0.1, 0.16, 0.035, 0.4), (0.15, -0.12, 0.12, 0.03, -0.3), (0.05, 0.28, 0.09, 0.025,
                                                                                               0.9)):
        o = ev.extrude(_blob(1.0, n=16, lobes=((2, 0.05, 0.3),), sx=a, sy=b), 0.017, 0.0185, sheen)
        o.rotation_euler.z = rz
        o.location = (x, y, 0.0)
    for (x, y, r) in ((0.02, -0.02, 0.028), (-0.24, -0.16, 0.02), (0.26, 0.14, 0.022)):  # slow oil bubbles
        ev.uvs(r, (x, y, 0.017), oil, 10, 5, (1.0, 1.0, 0.7))
    rk = granite_paint(moss_at=0.65, scale=6.0, moss_z=0.0, cover=0.5)
    for k, (a, r, s_) in enumerate(((0.6, 0.66, 0.085), (2.5, 0.64, 0.065), (4.3, 0.67, 0.08), (5.5, 0.62, 0.055))):
        soft_block(r * math.cos(a), r * math.sin(a), s_ * 2.4, s_ * 2.0, s_ * 1.5, rk, 120 + k, rz=a, sub=1,
                   cuts=(2, 3), bevel=0)
    reed = flat("reed", "#6E9A48", 0.85)
    reed_l = flat("reed_l", "#8DB45A", 0.85)
    head = flat("reed_head", "#7A5232", 0.85)
    rnd = random.Random(31)
    for (a, r) in ((1.5, 0.6), (3.4, 0.58), (5.0, 0.6), (0.1, 0.57)):  # reed clumps at the water's edge
        cx_, cy2 = r * math.cos(a), r * math.sin(a)
        for j in range(5):
            b = j / 5 * math.tau + rnd.uniform(-0.3, 0.3)
            d = 0.0 if j == 0 else rnd.uniform(0.025, 0.045)
            x, y = cx_ + d * math.cos(b), cy2 + d * math.sin(b)
            h = rnd.uniform(0.15, 0.22)
            lean = (rnd.uniform(-0.02, 0.02), rnd.uniform(-0.02, 0.02))
            ev.cn(0.024, h, (x, y, h / 2), reed if j % 2 else reed_l, 6).rotation_euler = (lean[1] * 4, -lean[0] * 4, 0)
            if j % 2 == 0:
                cy(0.016, 0.055, (x + lean[0] * 0.6, y + lean[1] * 0.6, h * 0.78), head, 6)
    bark = tex("wood", "#8A6A4A", 2.0)  # a dead stump on the shore, its pale broken top
    cy(0.035, 0.09, (-0.5, 0.36, 0.045), bark, 8)
    cy(0.036, 0.008, (-0.5, 0.36, 0.093), flat("stump_top", "#C9A878", 0.8), 8)


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
    "dark_lake": dark_lake,
}


# ------------------------------------------------------------------ export


def reset():
    ea.reset()
    _PAINT.clear()


# models whose bake atlas gets its empty space filled (fill_atlas); mountain, mine and flowers keep the plain bake
FILL_ATLAS = {"windmill", "wheat_field", "crop_field", "tree_pine", "tree_round", "bush", "rock", "crag"}


def fill_atlas(ob):
    """Fill the atlas pixels that no UV island touches (the bake leaves them black) with the colour of the nearest
    islands, by a push-pull pyramid. Many small islands (wheat ears, crop heads, pine tiers) leave 20–45 % of a
    512 px atlas empty; the mipmaps Godot builds would average that black in and darken the model at map zoom.
    Pixels under an island stay as baked, so a sliver too thin to bake (a fence wire) keeps its old dark colour."""
    import numpy as np
    from PIL import Image, ImageDraw
    img = next(n.image for s in ob.material_slots if s.material and s.material.name.startswith("baked")
               for n in s.material.node_tree.nodes if n.type == "TEX_IMAGE")
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    a = a.reshape(h, w, 4)
    me = ob.data
    me.calc_loop_triangles()
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2) * (w, h) - 0.5
    tl = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("loops", tl)
    mask = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(mask)
    for tri in uv[tl].reshape(-1, 3, 2):  # image rows run bottom-up like v, so no flip
        dr.polygon([tuple(p) for p in tri], fill=1, outline=1)
    island = np.asarray(mask, np.float32) > 0
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
    empty = (cov == 0) & ~island
    a[..., :3] = np.where(empty[..., None], fill, a[..., :3])
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
