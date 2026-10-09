"""Defensive towers by level (canon: the tower's look evolves with the state's era, like the fort ring).

Builds and exports to OUT (default game/assets/models):
  tower_l{1..8}.glb   team-neutral tower, spawned at the back-right of a hex (small footprint)

  1 вышка с пращником          crude lookout on rope-lashed poles, slinger, signal brazier, rag pennant, stone piles
  2 деревянная вышка лучника   timber watchtower, battened parapet hung with shields, coursed thatch tent roof with a
                               pennant, a lantern under the eave, archer with a bow, barrel and crates
  3 каменная башня с баллистой  round tower of big grey courses, string course, machicolation corbels, crenels, stair
                               turret under a slate cone, lit arched window, banner, lantern, ballista and its crew
  4 пушечная башня             octagonal brick bastion with stone quoins on a stone plinth, two bartizans under slate
                               cones, bronze cannons on spoked carriages and in gun ports, shot, powder kegs, grey flag
  5 пулемётное гнездо          cast-concrete tower (formwork lines, tie holes), three courses of sandbags, camouflage
                               net, machine gun with gunner and an observer, ammo crates, searchlight, radio whip
  6 ДОТ с зениткой (ПВО)        hexagonal concrete pillbox with sandbags on its ledge and a camouflage-painted twin AA gun
  7 ракетная башня             riveted steel plating, cold-blue light strips, hazard stripes, tilted missile pod, red
                               sensor glow, radar dish, vent grilles and a console on the plinth
  8 лазерная турель            white composite plates, dark inset panels with cold light slits, cyan edge seams, energy
                               ring, capacitor pods, turret head with heat-sink fins and a glowing cyan emitter

Run:   python3 tools/blender/tower_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/tower_assets.py game/assets/models --sheet OUT.png [--cols 1,2,3] [--tile 1.0]

Conventions (same as evolution_assets.py): Z up, base on Z=0, origin = model centre, front faces −Y.
Footprint radius ≤ 0.28, height 0.55–0.95. Procedural colours are baked into one 512 px texture (the masonry towers
through evolution_assets' tight atlas); emissive materials (fire, lanterns, lit window, sensor, cyan light) stay separate
so they keep glowing in Godot. The towers carry no team colour: neutral off-white/grey cloth, slate-blue cones.
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
import evolution_assets as ev  # noqa: E402  (guarded: importing it builds nothing)
from evolution_assets import (bx, cy, cn, ico, uvs, torus, rod, beam, taper_box, hip_roof, flat, tex, stone,  # noqa: E402
                              glow, win_lit, build_at, shade, WOOD, WOOD_D, WOOD_L, THATCH, STONE, STONE_D, BRICK, DIRT,
                              WHITE, CYAN, GOLD)

SKIN = "#e2a877"
IRON = "#2e3034"
OLIVE = "#5b6347"
OLIVE_D = "#434a35"
SAND = "#c9b27a"
STEEL = "#7f8995"
STEEL_D = "#5c6570"
WARN = "#f2c230"
COMP = "#e3e8ee"
COMP_T = "#4a515c"


# ------------------------------------------------------------------ materials


def stripes(c1=WARN, c2="#1f1f22", scale=14.0):
    """Diagonal hazard stripes (world-space wave bands, baked like every procedural material)."""
    key = ("stripes", c1, c2, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("stripes")
    m.use_nodes = True
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 0.0
    nt.links.new(geo.outputs["Position"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*kit.srgb(c2), 1)
    ramp.color_ramp.elements[1].position = 0.5
    ramp.color_ramp.elements[1].color = (*kit.srgb(c1), 1)
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    kit._MATS[key] = m
    return m


class _NT:
    """Tiny node-graph helper for the procedural materials below."""

    def __init__(self, m):
        self.nt = m.node_tree
        self.L = self.nt.links

    def math(self, op, a, b=None):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                self.L.new(v, n.inputs[i])
        return n.outputs[0]

    def mix(self, fac, a, b):
        n = self.nt.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        sock = lambda ident, out=False: next(x for x in (n.outputs if out else n.inputs) if x.identifier == ident)  # noqa: E731
        if isinstance(fac, (int, float)):
            sock("Factor_Float").default_value = fac
        else:
            self.L.new(fac, sock("Factor_Float"))
        for ident, v in (("A_Color", a), ("B_Color", b)):
            if isinstance(v, str):
                sock(ident).default_value = (*kit.srgb(v), 1)
            else:
                self.L.new(v, sock(ident))
        return sock("Result_Color", True)

    def frame(self):
        """World position x, y, z and face coordinates U, V: along the face and up on walls, x and y on roofs."""
        geo = self.nt.nodes.new("ShaderNodeNewGeometry")
        sp = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.L.new(geo.outputs["Position"], sp.inputs[0])
        sn = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.L.new(geo.outputs["True Normal"], sn.inputs[0])
        x, y, z = sp.outputs[0], sp.outputs[1], sp.outputs[2]
        vm = self.math("LESS_THAN", self.math("ABSOLUTE", sn.outputs[2]), 0.6)
        hm = self.math("SUBTRACT", 1.0, vm)
        u_wall = self.math("ADD", self.math("MULTIPLY", x, self.math("MULTIPLY", sn.outputs[1], -1.0)),
                           self.math("MULTIPLY", y, sn.outputs[0]))
        U = self.math("ADD", self.math("MULTIPLY", u_wall, vm), self.math("MULTIPLY", x, hm))
        V = self.math("ADD", self.math("MULTIPLY", z, vm), self.math("MULTIPLY", y, hm))
        return x, y, z, U, V, vm, geo


def panels(c, seam=None, col=0.07, row=0.09, sw=0.07, rivet="#c9d0d8", rr=0.0045, rough=0.45):
    """Steel or composite plating baked into the texture: panels col × row (along each face and up it, x × y on
    tops) with dark seams and a light rivet at each panel corner (the panelled steel of reference frames 2 and 5)."""
    seam = seam or shade(c, 0.55)
    key = ("panels", c, seam, col, row, sw, rivet, rr)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("panels")
    m.use_nodes = True
    g = _NT(m)
    x, y, z, U, V, vm, geo = g.frame()
    fu, fv = g.math("FRACT", g.math("DIVIDE", U, col)), g.math("FRACT", g.math("DIVIDE", V, row))
    sm = g.math("MAXIMUM", g.math("LESS_THAN", fu, sw), g.math("LESS_THAN", fv, sw * col / row))
    nz = g.nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 14.0
    g.L.new(geo.outputs["Position"], nz.inputs["Vector"])
    base = g.mix(g.math("MULTIPLY", nz.outputs["Fac"], 0.5), shade(c, 0.9), c)
    out = g.mix(sm, base, seam)
    if rivet:
        k = 0.2  # rivets this far into the panel from its corner seams
        du = g.math("MULTIPLY", g.math("MINIMUM", g.math("ABSOLUTE", g.math("SUBTRACT", fu, sw + k * (1 - sw) * 0.5)),
                                       g.math("ABSOLUTE", g.math("SUBTRACT", fu, 1 - k * (1 - sw) * 0.5))), col)
        a2 = sw * col / row
        dv = g.math("MULTIPLY", g.math("MINIMUM", g.math("ABSOLUTE", g.math("SUBTRACT", fv, a2 + 0.1 * (1 - a2))),
                                       g.math("ABSOLUTE", g.math("SUBTRACT", fv, 1 - 0.1 * (1 - a2)))), row)
        d2 = g.math("ADD", g.math("MULTIPLY", du, du), g.math("MULTIPLY", dv, dv))
        out = g.mix(g.math("LESS_THAN", d2, rr * rr), out, rivet)
    b = g.nt.nodes["Principled BSDF"]
    g.L.new(out, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    kit._MATS[key] = m
    return m


def concrete(c, board=0.034, ties=True):
    """Cast concrete baked into the texture: formwork board lines up the walls, a grid of dark tie-rod holes, soft
    mottling and rain streaks running down (the bunkers and pillboxes of the trench era)."""
    key = ("concrete", c, board, ties)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("concrete")
    m.use_nodes = True
    g = _NT(m)
    x, y, z, U, V, vm, geo = g.frame()
    nz = g.nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 10.0
    g.L.new(geo.outputs["Position"], nz.inputs["Vector"])
    out = g.mix(g.math("MULTIPLY", nz.outputs["Fac"], 0.7), shade(c, 0.88), c)
    # rain streaks: noise squashed along Z, only on walls
    sv = g.nt.nodes.new("ShaderNodeCombineXYZ")
    g.L.new(g.math("MULTIPLY", U, 30.0), sv.inputs[0])
    g.L.new(g.math("MULTIPLY", z, 2.0), sv.inputs[1])
    st = g.nt.nodes.new("ShaderNodeTexNoise")
    st.inputs["Scale"].default_value = 1.0
    st.inputs["Detail"].default_value = 1.0
    g.L.new(sv.outputs[0], st.inputs["Vector"])
    streak = g.math("MULTIPLY", g.math("MULTIPLY", g.math("GREATER_THAN", st.outputs["Fac"], 0.56), vm), 0.45)
    out = g.mix(streak, out, shade(c, 0.74))
    fv = g.math("FRACT", g.math("DIVIDE", V, board))
    line = g.math("MULTIPLY", g.math("LESS_THAN", fv, 0.11), vm)
    out = g.mix(g.math("MULTIPLY", line, 0.8), out, shade(c, 0.7))
    if ties:
        fu = g.math("FRACT", g.math("DIVIDE", U, 0.075))
        fz = g.math("FRACT", g.math("DIVIDE", V, board * 2))
        du = g.math("MULTIPLY", g.math("SUBTRACT", fu, 0.5), 0.075)
        dz = g.math("MULTIPLY", g.math("SUBTRACT", fz, 0.5), board * 2)
        hole = g.math("MULTIPLY", g.math("LESS_THAN", g.math("ADD", g.math("MULTIPLY", du, du), g.math("MULTIPLY", dz, dz)),
                                         0.0042 ** 2), vm)
        out = g.mix(hole, out, shade(c, 0.45))
    b = g.nt.nodes["Principled BSDF"]
    g.L.new(out, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.85
    kit._MATS[key] = m
    return m


# ------------------------------------------------------------------ small parts


def man(shirt, pants="#5a4632", pose="idle", hat=None, s=1.0):
    """Chunky low-poly figure (~0.14 tall at s=1) standing at the origin facing −Y.

    pose: "sling" (right arm whirling a sling overhead), "bow" (drawing a bow forward), "gun" (both hands
    forward at chest height), "idle".
    """
    def b():
        sk = flat("skin", SKIN, 0.7)
        pm = tex("plaster", pants, 3.0)
        sm = tex("plaster", shirt, 3.0)
        for sx in (-1, 1):
            bx((0.02, 0.024, 0.05), (sx * 0.013, 0, 0.025), pm, bev=0)
        cy(0.024, 0.052, (0, 0, 0.076), sm, 6, r2=0.029)
        ico(0.02, (0, -0.002, 0.121), sk, (1, 1, 1.08))
        sh = 0.031
        if pose == "sling":
            hands = [(-0.034, -0.06, 0.098), (0.036, 0.008, 0.168)]
        elif pose == "bow":
            hands = [(-0.012, -0.082, 0.1), (0.012, -0.004, 0.102)]
        elif pose == "gun":
            hands = [(-0.022, -0.06, 0.088), (0.022, -0.05, 0.09)]
        else:
            hands = [(-0.034, -0.008, 0.055), (0.034, -0.008, 0.055)]
        for sx, hnd in zip((-1, 1), hands):
            rod((sx * sh, 0, 0.098), hnd, 0.009, sm, n=4)
            ico(0.009, hnd, sk)
        if hat == "hair":
            ico(0.0205, (0, 0.004, 0.128), flat("hair", "#4a2e1a", 0.9), (1, 1, 0.8))
        elif hat == "hood":
            ico(0.022, (0, 0.003, 0.127), sm, (1, 1, 0.95))
        elif hat == "helmet":
            uvs(0.025, (0, -0.002, 0.128), flat("helmet", OLIVE, 0.6), 8, 4, (1, 1, 0.62))
            cy(0.03, 0.005, (0, -0.002, 0.127), flat("helmet", OLIVE, 0.6), 8)
        return hands
    hands = []

    def wrap():
        hands.extend(b())
    build_at(wrap, s=s)
    return [tuple(c * s for c in h) for h in hands]


def rocks(pts, mt, seed=0):
    rnd = random.Random(seed)
    for (x, y, z, r) in pts:
        ico(r, (x, y, z + r * 0.6), mt, (1.0 + rnd.uniform(0, 0.3), 1.0, 0.75))


BRONZE = "#94692f"  # the field guns' barrels (export_assets.cannon's bronze, a shade darker for the small scale)


def bore(p, d, r, n=6, mt=None):
    """The dark bore of a gun: a flat n-gon of radius r at the muzzle p, facing along the barrel direction d
    (one face, so a muzzle reads as a gun at the cost of a few triangles)."""
    from mathutils import Vector
    d = Vector(d).normalized()
    u = d.cross(Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))).normalized()
    v = d.cross(u)
    mb = ev._MB()
    mb.face([tuple(Vector(p) + (u * math.cos(math.tau * k / n) + v * math.sin(math.tau * k / n)) * r) for k in range(n)],
            tuple(d))
    return mb.obj(mt or flat("bore", "#141414", 0.9), "bore")


def cannon(x, y, a, z=0.0, s=1.0):
    """Field cannon pointing along angle a (around Z), scaled by s: a bronze barrel with a muzzle ring and cascabel
    on a wooden carriage with spoked wheels (dark felloe, a pale spoke cross, iron hub)."""
    def b():
        wd = tex("wood", "#6a4327")
        iron = flat("iron", IRON, 0.5)
        brz = flat("bronze", BRONZE, 0.4)
        spoke = flat("spoke", "#b88a56", 0.8)
        bx((0.1, 0.05, 0.03), (-0.01, 0, 0.036), wd, bev=0)
        beam((-0.05, 0, 0.03), (-0.1, 0, 0.006), 0.022, wd)  # trail on the ground
        for sy in (-1, 1):
            y0 = sy * 0.036
            cy(0.032, 0.012, (0.0, y0, 0.032), tex("wood", "#3e2a1a", 2.0), 8, rot=(math.pi / 2, 0, 0))
            for k in range(2):
                bx((0.05, 0.004, 0.006), (0.0, y0 + sy * 0.0065, 0.032), spoke, bev=0, rot=(0, k * math.pi / 2 + math.pi / 4, 0))
        cy(0.021, 0.15, (0.045, 0, 0.072), brz, 8, r2=0.016, rot=(0, math.pi / 2 - 0.1, 0))
        cy(0.02, 0.014, (0.115, 0, 0.079), brz, 8, rot=(0, math.pi / 2 - 0.1, 0))
        cy(0.024, 0.014, (-0.02, 0, 0.066), brz, 8, rot=(0, math.pi / 2 - 0.1, 0))
        ico(0.011, (-0.04, 0, 0.064), brz)
        bore((0.1228, 0, 0.0798), (math.cos(0.1), 0, math.sin(0.1)), 0.0115)
    build_at(b, x, y, a, s=s, z=z)


def shot_pile(x, y, z, r=0.016, mt=None):
    """A pyramid of round shot: a triangle of three with one crowning it."""
    mt = mt or flat("iron", IRON, 0.5)
    d = r * 2.0
    for layer, rows in enumerate(((0, 1), (0,))):
        n = len(rows)
        for i in rows:
            for j in range(n - i):
                px = x + (j - (n - 1 - i) / 2) * d
                py = y + (i - (n - 1) / 3) * d * 0.866 + layer * d * 0.29
                ico(r, (px, py, z + r + layer * d * 0.8), mt)


def keg(x, y, z, s=1.0):
    """A powder keg with two dark hoops."""
    cy(0.022 * s, 0.048 * s, (x, y, z + 0.024 * s), tex("wood", "#8d5f35", 4.0), 8)
    cy(0.0232 * s, 0.006 * s, (x, y, z + 0.04 * s), flat("iron", IRON, 0.5), 8)


def quoins(corners, z0, z1, r_at, n=5, d=0.005, arm=(0.034, 0.022), mt=None, poly=8):
    """Dressed stone quoins on the corners of a polygonal tower (corner angles `corners`, radius r_at(z) of the
    polygon's vertices): alternating long and short blocks standing d proud of both faces, laid as flat quads (the
    buried faces and the paper-thin ends are left out). poly: sides of the polygon."""
    mb = ev._MB()
    half = math.pi / poly
    for ac in corners:
        for i in range(n):
            za, zb = z0 + (z1 - z0) * i / n + 0.003, z0 + (z1 - z0) * (i + 1) / n - 0.003
            for side in (-1, 1):
                L = arm[(i + (side > 0)) % 2]
                ea_ = ac + side * (half + math.pi / 2)  # along this face, away from the corner
                ex, ey = math.cos(ea_), math.sin(ea_)
                pts = []
                for z, ln in ((za, 0.0), (za, L), (zb, L), (zb, 0.0)):
                    rr = r_at(z) + d / math.cos(half)
                    pts.append((math.cos(ac) * rr + ex * ln, math.sin(ac) * rr + ey * ln, z))
                nrm = ac + side * half
                mb.face(pts, (math.cos(nrm), math.sin(nrm), 0.0))
    mb.obj(mt or stone(STONE, 0.8), "quoins")


def port_frame(fa, wall, z, outer, inner, proud, mt, dark):
    """A gun port on a wall facing bearing fa (its face at distance `wall` from the axis): a dressed stone frame
    outer = (w, h) standing `proud` off the wall round an opening inner = (w, h), and the dark port set back in it
    just off the wall face, its reveals in shadow, so the opening reads as a recess from any side (front ring, outer
    sides, dark reveals and back: open shells, the buried faces left out)."""
    c, s_ = math.cos(fa), math.sin(fa)
    n, t = (c, s_, 0.0), (-s_, c, 0.0)

    def P(d, u, v):
        return (c * d + t[0] * u, s_ * d + t[1] * u, z + v)
    fr, dk = ev._MB(), ev._MB()
    (W, H), (w, h) = (outer[0] / 2, outer[1] / 2), (inner[0] / 2, inner[1] / 2)
    d1, d0, db = wall + proud, wall + 0.0015, wall - 0.003
    o4 = [(-W, -H), (W, -H), (W, H), (-W, H)]
    i4 = [(-w, -h), (w, -h), (w, h), (-w, h)]
    for k in range(4):
        (ua, va), (ub, vb) = o4[k], o4[(k + 1) % 4]
        (ia, ja), (ib, jb) = i4[k], i4[(k + 1) % 4]
        fr.face([P(d1, ua, va), P(d1, ub, vb), P(d1, ib, jb), P(d1, ia, ja)], n)  # front ring
        en = [(0, 0, -1), t, (0, 0, 1), (-t[0], -t[1], 0)][k]  # this edge's outward normal (bottom, right, top, left)
        if k != 0:  # the outer bottom faces down: never seen from above
            fr.face([P(db, ua, va), P(db, ub, vb), P(d1, ub, vb), P(d1, ua, va)], en)
        dk.face([P(d0, ia, ja), P(d0, ib, jb), P(d1, ib, jb), P(d1, ia, ja)], tuple(-x for x in en))  # dark reveal
    dk.face([P(d0, u, v) for u, v in i4], n)
    fr.obj(mt, "port_frame")
    dk.obj(dark, "port")


def ladder(x0, x1, y0, y1, z1, mt, rungs=5):
    for x in (x0, x1):
        beam((x, y0, 0.0), (x, y1, z1), 0.016, mt)
    for i in range(1, rungs + 1):
        f = i / (rungs + 1)
        beam((x0, y0 + (y1 - y0) * f, z1 * f), (x1, y0 + (y1 - y0) * f, z1 * f), 0.011, mt)


def plank_deck(w, d, z, mt, n=5, t=0.022, seed=0, jag=0.02):
    rnd = random.Random(seed)
    for i in range(n):
        y = (i + 0.5) / n * d - d / 2
        bx((w + rnd.uniform(-jag, jag), d / n - 0.004, t), (rnd.uniform(-jag, jag) * 0.4, y, z), mt, bev=0)


def neutral_flag(x, y, h, w=0.15):
    pm = flat("pole", "#d9d2c3", 0.5)
    cy(0.009, h, (x, y, h / 2), pm, 6)
    bx((w, 0.008, w * 0.64), (x + w / 2 + 0.006, y, h - w * 0.34), flat("flag_white", "#ecebe6", 0.7), bev=0)
    bx((w, 0.011, w * 0.13), (x + w / 2 + 0.006, y, h - w * 0.34), flat("flag_grey", "#8d9096", 0.7), bev=0)
    ico(0.016, (x, y, h + 0.01), flat("gold", GOLD, 0.35))


CLOTH = "#ecebe6"  # the neutral pennants: off-white cloth with a slate-grey band (towers belong to no one's colours)
CLOTH_BAND = "#6f747c"


def pennant(x, y, z, L, h, rz=0.0, band=True, t=0.006):
    """A swallow-tailed pennant hanging from a pole at (x, y), its top edge at z, flying along +X (rotated rz):
    off-white cloth with a grey band near the hoist, a little sag towards the tail. Thick enough to bake."""
    pts = [(0.0, 0.0), (L, -h * 0.12), (L * 0.74, -h * 0.55), (L, -h * 1.0), (0.0, -h)]
    o = ev.extrude(pts, -t / 2, t / 2, flat("pennant_cloth", CLOTH, 0.75))
    o.rotation_euler = (math.pi / 2, 0, rz)
    o.location = (x, y, z)
    if band:
        b = ev.extrude([(L * 0.16, -h * 0.02), (L * 0.3, -h * 0.04), (L * 0.3, -h * 0.98), (L * 0.16, -h * 0.98)],
                       -t / 2 - 0.0025, t / 2 + 0.0025, flat("pennant_band", CLOTH_BAND, 0.75))
        b.rotation_euler = (math.pi / 2, 0, rz)
        b.location = (x, y, z)
    return o


BANNER_F = "#3f4958"  # the tower banners' field: a dark slate that stands out on the light grey courses


def wall_banner(x, y, z, w, h, rz=0.0, t=0.006, lean=0.0, field=BANNER_F, charge=CLOTH):
    """A neutral banner hung flat on a wall facing −Y (rotated rz), its top edge at z: a dark slate field with a
    swallow-tailed foot, an off-white band across it, a lozenge and a hem at the foot, on a dark hanging rod (the
    facade banners of frames 3-4; dark cloth with a light band reads as a flag on pale stone, at any size).
    lean: the foot stands out by this angle (to follow a battered wall)."""
    tail = 0.74
    pts = [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, -h), (0.0, -h * tail), (-w / 2, -h)]
    hem = 0.06 * h  # the light hem follows the foot's two tails
    for pp, th, mt in ((pts, t, flat("banner_field", field, 0.75)),
                       ([(-w / 2 - 0.002, -h * 0.13), (w / 2 + 0.002, -h * 0.13), (w / 2 + 0.002, -h * 0.27),
                         (-w / 2 - 0.002, -h * 0.27)], t + 0.005, flat("pennant_cloth", charge, 0.75)),
                       ([(w / 2 + 0.002, -h + hem), (w / 2 + 0.002, -h - 0.002), (0.0, -h * tail - 0.002),
                         (0.0, -h * tail + hem)], t + 0.005, flat("pennant_cloth", charge, 0.75)),
                       ([(-w / 2 - 0.002, -h + hem), (0.0, -h * tail + hem), (0.0, -h * tail - 0.002),
                         (-w / 2 - 0.002, -h - 0.002)], t + 0.005, flat("pennant_cloth", charge, 0.75)),
                       ([(0.0, -h * 0.35), (w * 0.2, -h * 0.47), (0.0, -h * 0.59), (-w * 0.2, -h * 0.47)], t + 0.005,
                        flat("pennant_cloth", charge, 0.75))):  # a lozenge for the emblem
        o = ev.extrude(pp, -th / 2, th / 2, mt)
        o.rotation_euler = (math.pi / 2 - lean, 0, rz)
        o.location = (x, y, z)
    c, s_ = math.cos(rz), math.sin(rz)
    rod((x - c * (w / 2 + 0.01), y - s_ * (w / 2 + 0.01), z + 0.004), (x + c * (w / 2 + 0.01), y + s_ * (w / 2 + 0.01), z + 0.004),
        0.0045, flat("iron", IRON, 0.6), n=4)
    for sg in (-1, 1):  # finials on the rod ends
        ico(0.006, (x + sg * c * (w / 2 + 0.012), y + sg * s_ * (w / 2 + 0.012), z + 0.004), flat("finial", GOLD, 0.35))


def lash(p, r, mt, h=0.02):
    """A rope lashing wound round a pole at p (light rope on dark timber: the joints read at a glance)."""
    cy(r, h, p, mt, 6)


def brazier(x, y, z, s=1.0):
    """An iron fire basket on three legs with glowing coals and a flame tongue (warm light of the lookouts)."""
    def b():
        iron = flat("iron", IRON, 0.6)
        for k in range(3):
            a = k * math.tau / 3 + 0.3
            beam((math.cos(a) * 0.04, math.sin(a) * 0.04, 0.0), (math.cos(a) * 0.026, math.sin(a) * 0.026, 0.075), 0.009, iron)
        cy(0.036, 0.032, (0, 0, 0.082), iron, 8, r2=0.044)
        cy(0.036, 0.006, (0, 0, 0.099), glow("fire2", "#ffd34a", 5.0), 8)
        cn(0.028, 0.06, (0, 0, 0.13), glow("fire", "#ff7a1a", 4.0), 6)
    build_at(b, x, y, s=s, z=z)


def lantern(x, y, z, s=1.0, hang=0.0):
    """A small iron-capped lantern with a warm glowing body (hang > 0: on a short chain from above)."""
    def b():
        iron = flat("iron", IRON, 0.6)
        cy(0.017, 0.03, (0, 0, 0.0), glow("lantern", "#ffcf6b", 2.5), 6)
        cn(0.022, 0.018, (0, 0, 0.024), iron, 6)
        cy(0.019, 0.006, (0, 0, -0.017), iron, 6)
        if hang:
            cy(0.0035, hang, (0, 0, 0.033 + hang / 2), iron, 4)
    build_at(b, x, y, s=s, z=z)


def shield(x, y, z, rz, r=0.032, face="#8a5c36", rim=IRON):
    """A round wooden shield hung flat on a parapet facing −Y (rotated rz): plank face on an iron rim, iron boss."""
    def b():
        iron = flat("iron", rim, 0.6)
        cy(r + 0.005, 0.006, (0, 0.002, 0), iron, 8, rot=(math.pi / 2, 0, 0))
        cy(r, 0.006, (0, -0.002, 0), tex("wood", face, 4.0), 8, rot=(math.pi / 2, 0, 0))
        cy(r * 0.3, 0.008, (0, -0.006, 0), iron, 6, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz, z=z)


def camo(c1=OLIVE, c2="#3b4229", c3="#7a6a44", scale=22.0):
    """Camouflage netting: olive, dark green and earth blotches (two thresholded noises), baked like the rest."""
    key = ("camo", c1, c2, c3, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("camo")
    m.use_nodes = True
    g = _NT(m)
    geo = g.nt.nodes.new("ShaderNodeNewGeometry")
    out = c1
    for i, (c, th) in enumerate(((c2, 0.53), (c3, 0.58))):
        nz = g.nt.nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = scale * (1.0 + 0.4 * i)
        nz.inputs["Detail"].default_value = 2.0
        nz.noise_dimensions = "4D"
        nz.inputs["W"].default_value = 3.1 * i
        g.L.new(geo.outputs["Position"], nz.inputs["Vector"])
        out = g.mix(g.math("GREATER_THAN", nz.outputs["Fac"], th), out, c)
    b = g.nt.nodes["Principled BSDF"]
    g.L.new(out, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    kit._MATS[key] = m
    return m


def sandbag_ring(half, z0, courses, bag=(0.075, 0.046, 0.028), gap_front=(), seed=0):
    """Courses of sandbags round a square parapet (centre line at ±half): the bags are tapered boxes in two sand
    tones, each course bonded the other way round at the corners (full rows on two sides, short rows between), and
    gap_front lists the courses left open in the middle of the front (−Y) row for a gun."""
    rnd = random.Random(seed)
    L, D, Hc = bag
    tones = [tex("plaster", SAND, 3.0), tex("plaster", shade(SAND, 0.84), 3.0)]
    for c in range(courses):
        z = z0 + c * Hc + Hc / 2
        for k in range(4):
            a = k * math.pi / 2
            cs, sn = math.cos(a), math.sin(a)
            full = (k + c) % 2 == 0
            n = 4 if full else 3
            for i in range(n):
                t = (i - (n - 1) / 2) * L
                if k == 0 and c in gap_front and abs(t) < L * 0.6:
                    continue
                px, py = cs * t + sn * half, sn * t - cs * half
                o = taper_box((L - 0.004, D, Hc - 0.002), (px, py, z), tones[(i + c + k) % 2], (0.84, 0.7), bev=0)
                o.rotation_euler.z = a + rnd.uniform(-0.04, 0.04)


def crate(x, y, z, w, d, h, rz=0.0, c=OLIVE, band="#c9c08a"):
    """An ammunition crate: olive box with a pale stencil band and a darker lid."""
    bx((w, d, h), (x, y, z + h / 2), flat("crate" + c, c, 0.75), rz, bev=0)
    bx((w + 0.003, d * 0.3, h * 0.5), (x, y, z + h * 0.45), flat("stencil", band, 0.7), rz, bev=0)
    bx((w + 0.004, d + 0.004, 0.008), (x, y, z + h), flat("crate_lid" + c, shade(c, 0.78), 0.75), rz, bev=0)


def searchlight(x, y, z, rz=0.0, tilt=0.25, s=1.0):
    """A searchlight on a yoke: dark drum, warm glowing lens, looking along −Y (rotated rz) and down by tilt."""
    def b():
        dk = flat("gunbody", "#3d4147", 0.5)
        cy(0.012, 0.02, (0, 0, 0.01), dk, 6)
        for sx in (-1, 1):
            bx((0.006, 0.012, 0.04), (sx * 0.028, 0.0, 0.035), dk, bev=0)

        def drum():
            cy(0.024, 0.045, (0, 0, 0), dk, 8, rot=(math.pi / 2, 0, 0))
            cy(0.02, 0.006, (0, -0.0225, 0), glow("searchlight", "#fff1c8", 4.0), 8, rot=(math.pi / 2, 0, 0))
        build_at(drum, 0, 0, tilt=(-tilt, 0), z=0.045)
    build_at(b, x, y, rz, s=s, z=z)


# ------------------------------------------------------------------ towers


def tower_l1():
    """Crude lookout: four rough leaning poles lashed with rope, a jagged plank deck with a hide screen, a slinger,
    a signal brazier, a rag pennant on the tallest pole, piles of stones."""
    wd = tex("wood", WOOD_D, 2.0)
    wr = tex("wood", "#8a6440", 2.5)
    rk = tex("plaster", "#8d8a84", 1.5)
    rope = flat("rope", "#e8dcc0")
    ev.pad(0.24, tex("plaster", DIRT, 1.2), 0.008, 10, 0.08, 21)
    H = 0.4
    rnd = random.Random(1)
    tops = []
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        b0 = (math.cos(a) * 0.2 + rnd.uniform(-0.01, 0.01), math.sin(a) * 0.2 + rnd.uniform(-0.01, 0.01))
        t = (math.cos(a) * 0.13, math.sin(a) * 0.13)
        zt = H + 0.08 + rnd.uniform(-0.015, 0.02)
        if k == 1:  # the back-left pole runs on up as the pennant staff
            zt = H + 0.3
            t = (math.cos(a) * 0.118, math.sin(a) * 0.118)
        rod((b0[0], b0[1], 0.0), (t[0], t[1], zt), 0.018, wd, r2=0.012 if k == 1 else 0.014, n=6)
        tops.append((t, b0, zt))
        # rope lashings where the deck and the rail meet the pole
        for z in (H - 0.012, H + 0.062):
            f = z / zt
            lash((b0[0] + (t[0] - b0[0]) * f, b0[1] + (t[1] - b0[1]) * f, z), 0.0215, rope, 0.022)
    # cross bracing on every side and a crude rail at hip height
    for k in range(4):
        (t0, b0, _), (t1, b1, _) = tops[k], tops[(k + 1) % 4]
        f0, f1 = 0.12, 0.72
        p0 = [b0[i] + (t0[i] - b0[i]) * f0 for i in (0, 1)]
        p1 = [b1[i] + (t1[i] - b1[i]) * f1 for i in (0, 1)]
        beam((p0[0], p0[1], H * f0), (p1[0], p1[1], H * f1), 0.016, wr)
        beam((t0[0], t0[1], H + 0.065), (t1[0], t1[1], H + 0.06), 0.014, wr)
    plank_deck(0.25, 0.25, H, tex("wood", "#9a7046", 3.0), 5, 0.022, 3, 0.03)
    ladder(-0.045, 0.045, -0.26, -0.15, H, wr, 5)
    # a hide screen lashed along the left rail (cloth catching the light), the rag pennant on the tall pole
    hide = tex("plaster", "#b88a5a", 2.0)
    bx((0.012, 0.21, 0.07), (-0.128, 0.0, H + 0.03), hide, bev=0, rot=(0, 0.1, 0))
    bx((0.016, 0.22, 0.012), (-0.123, 0.0, H + 0.066), rope, bev=0)
    t1 = tops[1][0]
    pennant(t1[0] + 0.006, t1[1], H + 0.285, 0.13, 0.055, rz=0.35)
    # signal brazier on the front-left corner of the deck
    brazier(-0.085, -0.085, H + 0.011, 0.95)
    # the slinger and his ammo
    hands = build_at(lambda: man("#a77b4c", "#6b4f35", "sling", "hair", 1.25), 0.01, 0.0, 0.0, z=H + 0.011)
    hx, hy, hz = hands[1]
    hz += H + 0.011
    hx += 0.01
    rod((hx, hy, hz), (hx + 0.03, hy + 0.035, hz + 0.045), 0.0035, flat("rope", "#e8dcc0"), n=4)
    ico(0.014, (hx + 0.032, hy + 0.038, hz + 0.05), rk)
    rocks([(0.08, 0.07, H + 0.011, 0.02), (0.1, 0.035, H + 0.011, 0.017), (0.065, 0.1, H + 0.011, 0.015),
           (0.085, 0.07, H + 0.03, 0.014)], rk, 2)
    cy(0.034, 0.05, (-0.075, 0.07, H + 0.036), tex("wood", THATCH, 3.0), 7, r2=0.04)  # basket of stones
    rocks([(-0.075, 0.07, H + 0.05, 0.016), (-0.065, 0.085, H + 0.05, 0.013)], rk, 3)
    rocks([(0.13, -0.13, 0.0, 0.03), (0.17, -0.1, 0.0, 0.024), (0.15, -0.165, 0.0, 0.02),
           (-0.17, -0.06, 0.0, 0.022)], rk, 4)


def tower_l2():
    """Timber watchtower: braced splayed posts, a battened plank parapet hung with shields, a tent roof of coursed
    thatch with a pennant on the finial, a lantern under the eaves, an archer drawing a bow, a barrel and crates."""
    wd = tex("wood", WOOD, 2.0)
    wl = tex("wood", WOOD_L, 2.5)
    H = 0.4
    base, top = 0.165, 0.12
    corners = [(sx, sy) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for sx, sy in corners:
        beam((sx * base, sy * base, 0.0), (sx * top, sy * top, H), 0.034, wd)
        cy(0.026, 0.03, (sx * base, sy * base, 0.015), stone(STONE_D), 5)
    for k in range(4):
        (ax, ay), (bx_, by) = corners[k], corners[(k + 1) % 4]
        zm = H * 0.5
        mm = base + (top - base) * 0.5
        beam((ax * mm, ay * mm, zm), (bx_ * mm, by * mm, zm), 0.022, wl)
        beam((ax * base * 0.96, ay * base * 0.96, 0.03), (bx_ * mm, by * mm, zm), 0.018, wl)
        beam((ax * mm, ay * mm, zm), (bx_ * top, by * top, H - 0.02), 0.018, wl)
    plank_deck(0.3, 0.3, H, tex("wood", "#9a7046", 3.0), 5, 0.026, 5, 0.0)
    # plank parapet with dark battens on the outer face
    pw = tex("wood", "#8c5e34", 4.0)
    ph = 0.06
    mb = ev._MB()
    for k in range(4):
        a = k * math.pi / 2
        c, s_ = math.cos(a), math.sin(a)
        ln = 0.3 if k % 2 == 0 else 0.27  # alternate long and short boards: no coplanar faces at the corners
        bx((ln + 0.016, 0.02, ph), (s_ * 0.14, -c * 0.14, H + 0.013 + ph / 2), pw, a, bev=0)
        bx((ln + 0.024, 0.03, 0.02), (s_ * 0.14, -c * 0.14, H + 0.013 + ph + 0.002 * (k % 2)), wd, a, bev=0)
        n = (s_, -c, 0.0)
        for f in (-0.33, 0.0, 0.33):
            px, py = s_ * 0.15 + c * f * 0.3, -c * 0.15 + s_ * f * 0.3
            mb.strip((px, py, H + 0.012), (px, py, H + 0.013 + ph - 0.008), n, 0.016, off=0.0025)
    mb.obj(flat("batten", "#4a3020", 0.85), "battens")
    for x in (-0.075, 0.075):  # round shields hung on the front parapet
        shield(x, -0.157, H + 0.05, 0.0, 0.034, "#9a6a3a" if x < 0 else "#7d8a96")
    # roof posts and a tent roof of thatch courses, a pennant on the finial, a lantern under the front eave
    zr = H + 0.28
    for sx, sy in corners:
        bx((0.024, 0.024, zr - H), (sx * 0.135, sy * 0.135, H + (zr - H) / 2), wd, bev=0)
    bx((0.31, 0.31, 0.02), (0, 0, zr - 0.005), wd, bev=0)
    rh = 0.15
    ev.coursed_hip(0.3, 0.3, rh, (0, 0, zr + 0.004), THATCH, oh=0.035, n=4, ct=0.013, tone=0.86,
                   kind="wood")
    cn(0.026, 0.045, (0, 0, zr + rh + 0.02), wd, 6)
    rod((0, 0, zr + rh), (0, 0, zr + rh + 0.09), 0.0055, flat("pole", "#d9d2c3", 0.5), n=4)
    pennant(0.004, 0, zr + rh + 0.088, 0.11, 0.045, rz=-0.3)
    lantern(-0.152, -0.152, zr - 0.052, 0.95, hang=0.03)  # hung from the front-left eave corner
    # a barrel and crates of arrows at the foot of the ladder
    ev.barrel(0.16, -0.2, 1.1)
    bx((0.05, 0.05, 0.045), (-0.19, -0.13, 0.0225), tex("wood", "#a77b48", 5.0), 0.3, bev=0)
    bx((0.04, 0.04, 0.035), (-0.18, -0.13, 0.0625), tex("wood", "#8d6a3e", 5.0), 0.1, bev=0)
    ladder(-0.04, 0.04, -0.25, -0.16, H, wl, 4)
    # archer drawing a bow to the front
    Z = H + 0.013
    hands = build_at(lambda: man("#3f8a3a", "#5a4632", "bow", "hood", 1.2), 0.0, -0.085, z=Z)
    gx, gy, gz = hands[0]
    dx, dy, dz = hands[1]
    gy -= 0.085
    gz += Z
    dy -= 0.085
    dz += Z
    bowm = tex("wood", "#6a4327", 2.0)
    tip_t = (gx, gy + 0.035, gz + 0.075)
    mid_t = (gx, gy - 0.004, gz + 0.045)
    tip_b = (gx, gy + 0.035, gz - 0.07)
    mid_b = (gx, gy - 0.004, gz - 0.04)
    for p0, p1 in (((gx, gy, gz), mid_t), (mid_t, tip_t), ((gx, gy, gz), mid_b), (mid_b, tip_b)):
        beam(p0, p1, 0.009, bowm)
    st = flat("string", "#efe6d0", 0.8)
    rod(tip_t, (dx, dy, dz), 0.0025, st, n=3)
    rod(tip_b, (dx, dy, dz), 0.0025, st, n=3)
    rod((dx, dy, dz), (gx, gy - 0.03, gz), 0.003, flat("arrow", "#d8c49a", 0.8), n=3)
    cy(0.012, 0.07, (0.022, 0.006, Z + 0.1), tex("plaster", "#7a4a2a", 2.0), 6, rot=(0.3, -0.2, 0))  # quiver


def slate_cone(x, y, z0, r, h, roof_c, rings=3, sides=8, lip=0.008, band=0.74):
    """A turret's cone roof in rings of slates (the steep tower roofs of reference frame 4): each ring's lower edge
    stands a lip proud of the ring below, the rings alternate two tones and darken just under the next ring's edge
    (the shadow line the high game camera reads). Open at the bottom: the turret top closes it."""
    mbs, butt = [ev._MB(), ev._MB()], ev._MB()

    def P(rr, z, a):
        return (x + rr * math.cos(a), y + rr * math.sin(a), z)
    for k in range(rings):
        last = k == rings - 1
        fa, fb = k / rings, (1.0 if last else (k + 1.18) / rings)
        za, zb = z0 + h * fa, z0 + h * fb
        ra, rb = r * (1 - fa) + lip, r * (1 - fb)
        lam = ((k + band) / rings - fa) / (fb - fa)
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
    for mb, mt in zip(mbs, (tex("roof", roof_c, 1.6), tex("roof", shade(roof_c, 0.86), 1.6))):
        mb.obj(mt, "cone_courses")
    butt.obj(tex("roof", shade(roof_c, 0.62), 1.6), "cone_butts")
    return z0 + h


def arch_window(x, y, z, w, h, rz=0.0, lit=True):
    """An arched window on a wall facing −Y (rotated rz): a dark stone surround, a warm lit pane with a round head."""
    def b():
        sur = flat("arch_sur", "#6e6152", 0.85)
        bx((w + 0.014, 0.008, h + 0.006), (0, 0.002, -0.003), sur, bev=0)
        cy(w / 2 + 0.007, 0.008, (0, 0.002, h / 2), sur, 8, rot=(math.pi / 2, 0, 0))
        pane = win_lit() if lit else flat("slit", "#1e1a17", 0.9)
        bx((w, 0.012, h), (0, -0.002, 0), pane, bev=0)
        cy(w / 2, 0.012, (0, -0.002, h / 2), pane, 8, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz, z=z)


SLATE_T = "#56657a"  # tower slates: a cool blue-grey (the reference roofs are slate-blue; towers carry no team colour)


def tower_l3():
    """Round stone tower of big grey courses: a string course, machicolation corbels under a crenellated parapet,
    a stair turret with a slate cone, a lit arched window, arrow slits, an arched door with a lantern, and a ballista
    with its crew on the roof."""
    st = stone(STONE, 0.5)
    sd = stone(STONE_D, 0.5)
    rq = (0, 0, math.pi / 12)  # a face (not an edge) of the 12-gon looks to the front
    ap = math.cos(math.pi / 12)
    cy(0.225, 0.06, (0, 0, 0.03), sd, 12, rot=rq)
    cy(0.205, 0.44, (0, 0, 0.28), st, 12, r2=0.185, rot=rq)
    cy(0.2, 0.014, (0, 0, 0.3), sd, 12, rot=rq)  # string course
    cy(0.18, 0.06, (0, 0, 0.53), stone(shade(STONE_D, 0.72), 0.5), 12, r2=0.196, rot=rq)
    corb = ev._MB()  # machicolation corbels carrying the parapet: front, sides and soffit only (the rest is buried)
    for k in range(12):
        a = k * math.tau / 12
        c, s_ = math.cos(a), math.sin(a)
        t = (-s_, c, 0.0)

        def P(rr, u, z):
            return (c * rr + t[0] * u, s_ * rr + t[1] * u, z)
        r0, r1, hw, z0, z1 = 0.176, 0.222, 0.0135, 0.506, 0.562
        corb.face([P(r1, -hw, z0 + 0.012), P(r1, hw, z0 + 0.012), P(r1, hw, z1), P(r1, -hw, z1)], (c, s_, 0))
        corb.face([P(r0, -hw, z0), P(r0, hw, z0), P(r1, hw, z0 + 0.012), P(r1, -hw, z0 + 0.012)], (0, 0, -1))
        for sg in (-1, 1):
            corb.face([P(r0, sg * hw, z0), P(r1, sg * hw, z0 + 0.012), P(r1, sg * hw, z1), P(r0, sg * hw, z1)],
                      (t[0] * sg, t[1] * sg, 0))
    corb.obj(sd, "corbels")
    cy(0.23, 0.044, (0, 0, 0.582), st, 12, rot=rq)
    ta = math.radians(150)  # the stair turret's bearing
    for k in range(8):
        a = k * math.tau / 8 + math.tau / 16
        if abs((a - ta + math.pi) % math.tau - math.pi) < math.radians(15):  # this merlon is inside the turret
            continue
        bx((0.07, 0.05, 0.065), (math.cos(a) * 0.198, math.sin(a) * 0.198, 0.634), st, a + math.pi / 2, bev=0)
    cy(0.185, 0.012, (0, 0, 0.6), tex("wood", "#9a7046", 3.0), 12)
    # stair turret on the back-left, rising above the parapet under a slate cone
    tx, ty = math.cos(ta) * 0.188, math.sin(ta) * 0.188
    cy(0.058, 0.66, (tx, ty, 0.33), st, 8)
    cy(0.066, 0.03, (tx, ty, 0.655), sd, 8)
    slate_cone(tx, ty, 0.668, 0.074, 0.128, SLATE_T, 3, 8)
    uvs(0.011, (tx, ty, 0.8), flat("finial", GOLD, 0.35), 6, 4)
    # door with an arched top and a stone surround, iron bands, a lantern, a lit window, arrow slits
    door = tex("wood", "#4a2f19", 2.0)
    yd = -0.205 * ap
    bx((0.096, 0.02, 0.118), (0, yd + 0.002, 0.118), sd, bev=0)
    cy(0.048, 0.02, (0, yd + 0.002, 0.177), sd, 8, rot=(math.pi / 2, 0, 0))
    bx((0.072, 0.03, 0.1), (0, yd, 0.11), door, bev=0)
    cy(0.036, 0.03, (0, yd, 0.16), door, 8, rot=(math.pi / 2, 0, 0))
    bx((0.11, 0.05, 0.02), (0, yd - 0.012, 0.06), sd, bev=0)
    for z in (0.09, 0.14):
        bx((0.076, 0.036, 0.008), (0, yd - 0.001, z), flat("iron", IRON, 0.6), bev=0)
    lantern(0.06, -0.207, 0.17, 0.9)  # on an iron bracket from the wall beside the door
    beam((0.06, -0.188, 0.2), (0.06, -0.21, 0.2), 0.006, flat("iron", IRON, 0.6))
    aw = -math.pi / 6  # the lit window on the front-right face, a neutral banner on the front
    rw = 0.1925 * ap + 0.002
    arch_window(math.cos(aw) * rw, math.sin(aw) * rw, 0.4, 0.03, 0.05, aw + math.pi / 2)
    wall_banner(0.0, -0.1845, 0.49, 0.08, 0.158, 0.0, lean=0.045)
    slit = flat("slit", "#1e1a17", 0.9)
    for a, z in ((-math.pi / 2 - math.pi / 3, 0.38), (-math.pi / 2 + math.pi / 3, 0.2), (-math.pi / 2 - math.pi / 6, 0.22),
                 (math.pi / 2, 0.33), (math.pi / 6, 0.36)):
        r = (0.205 + (0.185 - 0.205) * (z - 0.06) / 0.44) * ap - 0.002
        bx((0.018, 0.02, 0.07), (math.cos(a) * r, math.sin(a) * r, z), slit, a + math.pi / 2, bev=0)
    for k in range(2):  # slits up the stair turret
        a = ta - 0.5 + k * 1.0
        bx((0.014, 0.02, 0.05), (tx + math.cos(a) * 0.055, ty + math.sin(a) * 0.055, 0.25 + k * 0.17), slit,
           a + math.pi / 2, bev=0)

    def ballista():
        wd = tex("wood", "#7a4c2a", 2.5)
        iron = flat("iron", IRON, 0.5)
        cy(0.03, 0.05, (0, 0, 0.025), wd, 8)
        bx((0.05, 0.05, 0.02), (0, 0, 0.055), iron, bev=0)
        # stock tilted a little up to the front
        t = 0.12
        bx((0.04, 0.26, 0.035), (0, -0.02, 0.08), wd, bev=0, rot=(t, 0, 0))
        fy, fz = -0.12, 0.08 + math.sin(t) * 0.1
        bx((0.07, 0.03, 0.05), (0, fy, fz), iron, bev=0, rot=(t, 0, 0))
        arms = []
        for sx in (-1, 1):
            tip = (sx * 0.15, fy + 0.07, fz + 0.012)
            beam((sx * 0.03, fy, fz), (sx * 0.085, fy - 0.012, fz + 0.01), 0.022, wd)
            beam((sx * 0.085, fy - 0.012, fz + 0.01), tip, 0.018, wd)
            arms.append(tip)
        st_ = flat("string", "#efe6d0", 0.8)
        nock = (0, 0.07, 0.08 - math.sin(t) * 0.09 + 0.022)
        for tip in arms:
            rod(tip, nock, 0.0035, st_, n=3)
        rod((0, 0.06, nock[2]), (0, -0.2, 0.08 + math.sin(t) * 0.18 + 0.022), 0.008, flat("bolt", "#d8c49a", 0.8), n=5)
        cn(0.014, 0.04, (0, -0.215, 0.08 + math.sin(t) * 0.195 + 0.022), iron, 5, rot=(-math.pi / 2 + t, 0, 0))
        cy(0.022, 0.04, (0, 0.11, 0.075 - 0.01), iron, 8, rot=(0, math.pi / 2, 0))  # winch
    build_at(ballista, 0.0, 0.01, z=0.606, s=1.05)
    build_at(lambda: man("#8a6a44", "#4a3a2a", "gun", "hood", 1.05), 0.07, 0.115, -0.35, z=0.606)


def tower_l4():
    """Octagonal brick bastion on a sloped stone plinth: dressed stone quoins, two bartizans with slate cones on the
    back corners, bronze cannons on spoked carriages on top and in gun ports, shot piles and powder kegs, grey flag."""
    sb = stone("#a39b8d", 0.8)
    br = stone(BRICK, 1.4)
    trim = stone(STONE, 0.8)
    rot = (0, 0, math.pi / 8)
    cy(0.255, 0.2, (0, 0, 0.1), sb, 8, r2=0.215, rot=rot)
    cy(0.222, 0.035, (0, 0, 0.215), trim, 8, rot=rot)
    cy(0.2, 0.3, (0, 0, 0.38), br, 8, r2=0.195, rot=rot)
    cy(0.195, 0.04, (0, 0, 0.545), trim, 8, r2=0.228, rot=rot)
    cy(0.228, 0.035, (0, 0, 0.58), trim, 8, rot=rot)
    cy(0.19, 0.012, (0, 0, 0.6), tex("wood", "#9a7046", 3.0), 8, rot=rot)
    # dressed stone quoins up the brick corners that face the camera
    corners = [math.pi / 8 + k * math.pi / 4 for k in range(8)]
    quoins([c for c in corners if math.sin(c) < 0.5], 0.232, 0.525, lambda z: 0.2 - 0.005 * (z - 0.23) / 0.3, 5,
           mt=trim)
    for k in range(8):  # merlons on the octagon corners, embrasures on the faces
        a = math.pi / 8 + k * math.pi / 4
        if math.sin(a) > 0.3:  # the two back corners carry the bartizans
            continue
        bx((0.075, 0.06, 0.075), (math.cos(a) * 0.198, math.sin(a) * 0.198, 0.635), br, a + math.pi / 2, bev=0)
        bx((0.082, 0.066, 0.014), (math.cos(a) * 0.198, math.sin(a) * 0.198, 0.676), trim, a + math.pi / 2, bev=0)
    for a in (math.pi * 3 / 8, math.pi * 5 / 8):  # bartizans: corbelled out, brick drum, slate cone, finial
        x, y = math.cos(a) * 0.19, math.sin(a) * 0.19
        cn(0.06, 0.07, (x, y, 0.565), trim, 8, rot=(math.pi, 0, 0))
        cy(0.056, 0.11, (x, y, 0.655), br, 8)
        cy(0.062, 0.018, (x, y, 0.712), trim, 8)
        for j in range(2):  # slits looking out to the sides
            sa = a + (-1.1 if j == 0 else 1.1)
            bx((0.012, 0.012, 0.04), (x + math.cos(sa) * 0.055, y + math.sin(sa) * 0.055, 0.66), flat("slit", "#1e1a17", 0.9),
               sa + math.pi / 2, bev=0)
        slate_cone(x, y, 0.72, 0.07, 0.15, SLATE_T, 3, 8)
        cn(0.008, 0.03, (x, y, 0.882), flat("finial", GOLD, 0.35), 4)
    for a in (-math.pi * 0.75, -math.pi * 0.25):
        cannon(math.cos(a) * 0.1, math.sin(a) * 0.1, a, 0.606, 1.15)
    # gun ports on the front and the two front-side faces, a bronze muzzle poking out of each
    iron = flat("iron", IRON, 0.5)
    brz = flat("bronze", BRONZE, 0.4)
    for fa in (-math.pi / 2, -math.pi / 2 - math.pi / 4, -math.pi / 2 + math.pi / 4):
        apz = (0.2 - 0.005 * 0.43) * math.cos(math.pi / 8) - 0.003
        c, s_ = math.cos(fa), math.sin(fa)
        # a stone frame round a dark port set back in it: a recess, not a block
        port_frame(fa, (0.2 - 0.005 * 0.43) * math.cos(math.pi / 8), 0.36, (0.074, 0.066), (0.054, 0.048), 0.008, trim,
                   flat("slit", "#1e1a17", 0.9))
        rr = (math.pi / 2 + 0.06, 0, fa + math.pi / 2)  # the barrel looks out of the face and a little down
        cy(0.017, 0.07, (c * (apz + 0.03), s_ * (apz + 0.03), 0.358), brz, 8, r2=0.014, rot=rr)
        cy(0.019, 0.012, (c * (apz + 0.062), s_ * (apz + 0.062), 0.356), brz, 8, rot=rr)  # muzzle ring
        dn = math.sin(0.06)
        bore((c * (apz + 0.069), s_ * (apz + 0.069), 0.356 - 0.007 * dn), (c, s_, -dn), 0.011)
    # a door porch in the front of the plinth with a lantern, round shot and powder kegs on the deck, flag
    bx((0.1, 0.05, 0.13), (0, -0.222, 0.065), sb, bev=0)
    bx((0.112, 0.056, 0.022), (0, -0.223, 0.136), trim, bev=0)
    bx((0.064, 0.012, 0.1), (0, -0.246, 0.05), tex("wood", "#4a2f19", 2.0), bev=0)
    bx((0.07, 0.014, 0.008), (0, -0.247, 0.07), iron, bev=0)
    lantern(0.04, -0.255, 0.1, 0.85)
    shot_pile(0.065, 0.075, 0.606, 0.017, iron)
    keg(-0.1, 0.03, 0.606, 1.0)
    keg(-0.065, 0.06, 0.606, 0.9)
    neutral_flag(-0.02, 0.11, 0.9, 0.15)


def tower_l5():
    """Concrete machine-gun nest: tapered cast tower with formwork lines and tie holes, three courses of sandbags,
    a camouflage net over the back, MG on a tripod with a helmeted gunner, ammo crates, a searchlight, a radio whip."""
    cm = concrete("#b9b5ad")
    cd = concrete("#8f8b83", ties=False)
    H = 0.4
    taper_box((0.36, 0.36, H), (0, 0, H / 2), cm, (0.86, 0.86), bev=0.01)
    bx((0.37, 0.37, 0.04), (0, 0, 0.02), cd, bev=0.006)
    for z in (0.14, 0.27):  # pour joints
        w = 0.36 - (0.36 * 0.14) * z / H
        bx((w + 0.006, w + 0.006, 0.008), (0, 0, z), cd, bev=0)
    bx((0.33, 0.33, 0.03), (0, 0, H + 0.015), cd, bev=0.006)
    w_slit = 0.36 - (0.36 * 0.14) * 0.22 / H
    bx((0.12, 0.02, 0.025), (0, -w_slit / 2, 0.22), flat("slit", "#15171a", 0.9), bev=0)
    bx((0.15, 0.04, 0.012), (0, -w_slit / 2 - 0.01, 0.24), cd, bev=0)
    w_sign = 0.36 - (0.36 * 0.14) * 0.09 / H
    bx((0.08, 0.008, 0.04), (0.095, -w_sign / 2 - 0.002, 0.09), stripes(WARN, "#1f1f22", 34.0), bev=0, rot=(-0.06, 0, 0))
    bx((0.08, 0.02, 0.13), (0, 0.18 - 0.012, 0.075), flat("steeldoor", "#5b6168", 0.5), bev=0)  # back door
    # steel ladder on the right side
    st = flat("steel", "#4c4f55", 0.5)
    for y in (-0.04, 0.04):
        beam((0.2, y, 0.0), (0.168, y, H + 0.04), 0.01, st)
    for i in range(1, 7):
        f = i / 7
        beam((0.2 - 0.032 * f, -0.04, (H + 0.04) * f), (0.2 - 0.032 * f, 0.04, (H + 0.04) * f), 0.008, st)
    # sandbag courses round the roof, the top course open at the front for the gun
    Z = H + 0.03
    sandbag_ring(0.135, Z, 3, gap_front=(2,), seed=5)
    # machine gun on a tripod, aimed forward over the gap
    iron = flat("gun", IRON, 0.5)
    gz = Z + 0.075
    for a in (-math.pi / 2, math.pi / 6, math.pi * 5 / 6):
        rod((0, -0.06, gz), (math.cos(a) * 0.045, -0.06 + math.sin(a) * 0.045, Z), 0.005, iron, n=4)
    bx((0.04, 0.1, 0.04), (0, -0.05, gz + 0.012), flat("gunbody", "#3d4147", 0.5), bev=0)
    cy(0.016, 0.08, (0, -0.135, gz + 0.016), flat("gunbody", "#3d4147", 0.5), 8, rot=(math.pi / 2, 0, 0))
    cy(0.007, 0.1, (0, -0.215, gz + 0.016), iron, 6, rot=(math.pi / 2, 0, 0))
    cn(0.012, 0.02, (0, -0.265, gz + 0.016), iron, 6, rot=(math.pi / 2, 0, 0))
    bx((0.045, 0.04, 0.035), (0.045, -0.045, gz + 0.0), flat("ammo", OLIVE, 0.7), bev=0)
    build_at(lambda: man(OLIVE, OLIVE_D, "gun", "helmet", 1.1), 0.0, 0.03, z=Z)
    # ammo crates stacked by the gunner, a searchlight on the front-right corner, a radio whip clear of the net
    crate(-0.075, -0.04, Z, 0.06, 0.045, 0.036, 0.15, OLIVE_D)
    crate(-0.07, -0.035, Z + 0.036, 0.05, 0.04, 0.03, -0.1, OLIVE_D)
    # an observer leaning on the sandbags under the net
    build_at(lambda: man(OLIVE, OLIVE_D, "gun", "helmet", 1.05), -0.075, 0.075, -0.5, z=Z)
    searchlight(0.118, -0.118, Z + 0.084, -0.5, 0.3)
    bx((0.04, 0.03, 0.035), (0.088, -0.004, Z + 0.0175), flat("radio", OLIVE_D, 0.7), 0.2, bev=0)
    rod((0.098, -0.004, Z + 0.035), (0.104, -0.01, 0.64), 0.0035, flat("steel", "#4c4f55", 0.5), n=4)
    # camouflage net slung over the back half on two poles, draped over the back sandbags (high enough to clear
    # the crew's helmets)
    for x in (-0.13, 0.13):
        rod((x, 0.06, Z + 0.084), (x, 0.06, 0.63), 0.005, tex("wood", WOOD_D, 2.0), n=4)
    rnd = random.Random(7)
    xs = [-0.175, -0.09, 0.0, 0.09, 0.175]
    rows = [(0.035, 0.635), (0.095, 0.605), (0.15, 0.562), (0.185, 0.495), (0.198, 0.41)]
    verts = []
    for (y, z) in rows:
        for x in xs:
            sag = 0.022 * (1 - (abs(x) / 0.175) ** 2) if y < 0.15 else 0.0
            verts.append((x + rnd.uniform(-0.006, 0.006), y + rnd.uniform(-0.006, 0.006), z - sag + rnd.uniform(-0.006, 0.006)))
    nx = len(xs)
    faces = [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(len(rows) - 1) for i in range(nx - 1)]
    ev.mesh_obj(verts, faces, camo())


def tower_l6():
    """Hexagonal cast-concrete pillbox (ДОТ, formwork lines and rain streaks) with a ring of sandbags on its ledge,
    a hazard plate and a camouflage-painted twin anti-aircraft gun on a turret ring."""
    cm = concrete("#a9a59c")
    cd = concrete("#86827a", ties=False)
    cy(0.268, 0.05, (0, 0, 0.025), tex("plaster", "#7d6a50", 1.5), 6)  # earth skirt
    cy(0.255, 0.28, (0, 0, 0.19), cm, 6, r2=0.215)
    cy(0.235, 0.05, (0, 0, 0.355), cd, 6, r2=0.225)
    cy(0.17, 0.05, (0, 0, 0.405), cm, 6, r2=0.15)
    slit = flat("slit", "#15171a", 0.9)
    zf = 0.21
    rv = 0.255 + (0.215 - 0.255) * (zf - 0.05) / 0.28
    ap = rv * math.cos(math.pi / 6)
    for a in (-math.pi / 2, -math.pi / 2 - math.pi / 3, -math.pi / 2 + math.pi / 3, math.pi / 2):
        c, s_ = math.cos(a), math.sin(a)
        bx((0.11, 0.02, 0.026), (c * (ap - 0.002), s_ * (ap - 0.002), zf), slit, a + math.pi / 2, bev=0)
        bx((0.14, 0.035, 0.014), (c * (ap + 0.004), s_ * (ap + 0.004), zf + 0.026), cd, a + math.pi / 2, bev=0)
    zs = 0.1
    aps = (0.255 + (0.215 - 0.255) * (zs - 0.05) / 0.28) * math.cos(math.pi / 6)
    bx((0.08, 0.008, 0.04), (0.1, -aps - 0.003, zs), stripes(WARN, "#1f1f22", 34.0), bev=0, rot=(-0.14, 0, 0))
    # sandbags round the ledge: one course all round, a second on the three faces towards the front
    tones = [tex("plaster", SAND, 3.0), tex("plaster", shade(SAND, 0.84), 3.0)]
    rnd = random.Random(3)
    for k in range(6):
        a = math.pi / 6 + k * math.pi / 3
        c, s_ = math.cos(a), math.sin(a)
        courses = [(0.397, (-0.047, 0.047))] + ([(0.43, (-0.024, 0.06))] if s_ < -0.4 else [])
        for zc, ts in courses:
            for i, t in enumerate(ts):
                px, py = c * 0.171 - s_ * t, s_ * 0.171 + c * t
                o = taper_box((0.088 if zc < 0.42 else 0.07, 0.04, 0.034), (px, py, zc), tones[(i + k + (zc > 0.42)) % 2],
                              (0.84, 0.7), bev=0)
                o.rotation_euler.z = a + math.pi / 2 + rnd.uniform(-0.05, 0.05)
    # turret ring + twin AA gun pointing up and forward, painted in camouflage blotches
    ol = camo(OLIVE, "#3b4229", "#8a7a50", 11.0)
    od = flat("olive_d", OLIVE_D, 0.6)
    iron = flat("gun", IRON, 0.5)
    cy(0.135, 0.03, (0, 0, 0.445), od, 10)
    Z = 0.46

    def aa():
        cy(0.085, 0.03, (0, 0, 0.015), ol, 10)
        for sx in (-1, 1):
            bx((0.02, 0.1, 0.1), (sx * 0.06, 0.0, 0.075), ol, bev=0.004)
        el = math.radians(55)
        piv = (0, 0.0, 0.1)
        bx((0.09, 0.08, 0.06), piv, od, bev=0.006, rot=(el - math.pi / 2, 0, 0))
        d = (0, -math.cos(el), math.sin(el))
        for sx in (-1, 1):
            p0 = (sx * 0.026, piv[1] + d[1] * 0.02, piv[2] + d[2] * 0.02)
            p1 = (sx * 0.026, piv[1] + d[1] * 0.23, piv[2] + d[2] * 0.23)
            rod(p0, p1, 0.009, iron, n=6)
            rod((sx * 0.026, piv[1] + d[1] * 0.21, piv[2] + d[2] * 0.21), (sx * 0.026, piv[1] + d[1] * 0.25, piv[2] + d[2] * 0.25),
                0.014, iron, n=6)
            bx((0.03, 0.05, 0.05), (sx * 0.026, piv[1] - d[1] * 0.02, piv[2] + 0.06), ol, bev=0)  # magazines
        # curved gun shield in front
        for j, a in enumerate((-0.5, 0.0, 0.5)):
            bx((0.075, 0.012, 0.08), (math.sin(a) * 0.09, -math.cos(a) * 0.09, 0.07), ol, a, bev=0, rot=(0.15, 0, a))
        bx((0.03, 0.03, 0.03), (0.0, 0.07, 0.06), od, bev=0)  # seat
    build_at(aa, 0.0, 0.0, z=Z, s=1.35)
    # whip antenna at the back
    cy(0.005, 0.22, (-0.12, 0.12, 0.38 + 0.11), flat("steel", "#4c4f55", 0.5), 4)
    ico(0.01, (-0.12, 0.12, 0.6), glow("lamp_red", "#ff4a3a", 3.0))


def tower_l7():
    """Steel missile tower: hazard-striped plinth with vent grilles and a console; a ribbed column of
    riveted plates with cold-blue light strips; a tilted 2×3 missile pod in riveted plating with a cold strip across
    its top, red sensor glow and a small radar dish."""
    sw = panels(STEEL, shade(STEEL, 0.6), 0.075, 0.1)
    sd = flat("steelrib", STEEL_D, 0.45)
    pl = panels(STEEL_D, shade(STEEL_D, 0.6), 0.09, 0.06)
    hz = stripes(WARN, "#1f1f22", 14.0)
    cold = glow("cyan", CYAN, 2.5)
    cy(0.255, 0.07, (0, 0, 0.035), pl, 6)
    cy(0.235, 0.05, (0, 0, 0.095), hz, 6)
    cy(0.22, 0.02, (0, 0, 0.13), sd, 6)
    cy(0.15, 0.42, (0, 0, 0.35), sw, 8, r2=0.115, rot=(0, 0, math.pi / 8))
    for k in range(4):
        a = k * math.pi / 2
        beam((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.14), (math.cos(a) * 0.117, math.sin(a) * 0.117, 0.54), 0.03, sd)
    # cold-blue light strips up the faces between the ribs (the lit seams of reference frames 2 and 5)
    k8 = math.cos(math.pi / 8)
    for a in (-math.pi / 4, -3 * math.pi / 4, math.pi / 4, 3 * math.pi / 4):
        r0, r1 = (0.15 - 0.035 * 0.04 / 0.42) * k8 + 0.002, (0.15 - 0.035 * 0.34 / 0.42) * k8 + 0.002
        beam((math.cos(a) * r0, math.sin(a) * r0, 0.18), (math.cos(a) * r1, math.sin(a) * r1, 0.48), 0.012, cold)
    cy(0.13, 0.04, (0, 0, 0.52), hz, 8, rot=(0, 0, math.pi / 8))
    cy(0.13, 0.03, (0, 0, 0.555), sd, 10)
    bx((0.06, 0.016, 0.1), (0, -0.145, 0.24), flat("hatch", "#4a515c", 0.5), bev=0, rot=(-0.08, 0, 0))
    bx((0.03, 0.01, 0.012), (0, -0.15, 0.3), glow("sensor", "#ff4a3a", 4.0), bev=0)
    # plinth: vent grilles on the front faces, a console with a cold screen
    ap6 = 0.255 * math.cos(math.pi / 6)
    grille = flat("grille", "#25282d", 0.6)
    for fa in (-math.pi / 2 - math.pi / 3, -math.pi / 2 + math.pi / 3):
        c, s_ = math.cos(fa), math.sin(fa)
        bx((0.09, 0.008, 0.036), (c * ap6, s_ * ap6, 0.036), grille, fa + math.pi / 2, bev=0)
        for j in range(3):
            bx((0.094, 0.01, 0.004), (c * (ap6 + 0.001), s_ * (ap6 + 0.001), 0.024 + j * 0.012), sd, fa + math.pi / 2, bev=0)
    bx((0.07, 0.05, 0.05), (0.13, -0.14, 0.165), sd, 0.0, bev=0)
    bx((0.056, 0.008, 0.03), (0.13, -0.166, 0.172), cold, bev=0, rot=(-0.3, 0, 0))

    def head():
        cy(0.11, 0.04, (0, 0, 0.02), sw, 10)
        for sx in (-1, 1):
            bx((0.022, 0.1, 0.12), (sx * 0.125, 0.0, 0.08), sd, bev=0.004)
        cy(0.018, 0.27, (0, 0, 0.11), sd, 8, rot=(0, math.pi / 2, 0))

        def pod():
            bx((0.22, 0.2, 0.14), (0, 0, 0), panels(STEEL, shade(STEEL, 0.6), 0.055, 0.07), bev=0.008)
            bx((0.226, 0.05, 0.146), (0, 0.03, 0.0), hz, bev=0)
            bx((0.23, 0.022, 0.15), (0, -0.1, 0), sd, bev=0)
            body = flat("missile", "#f0f0ea", 0.5)
            nose = flat("nose_red", "#d9342b", 0.5)
            for ix in (-1, 0, 1):
                for iz in (-1, 1):
                    x, z = ix * 0.068, iz * 0.037
                    cy(0.028, 0.012, (x, -0.112, z), flat("tube", "#22252a", 0.6), 8, rot=(math.pi / 2, 0, 0))
                    cy(0.02, 0.05, (x, -0.13, z), body, 8, rot=(math.pi / 2, 0, 0))
                    cn(0.02, 0.05, (x, -0.18, z), nose, 8, rot=(math.pi / 2, 0, 0))
            bx((0.06, 0.03, 0.03), (0.06, 0.02, 0.085), sd, bev=0)
            bx((0.05, 0.012, 0.02), (0.06, 0.0, 0.088), glow("sensor", "#ff4a3a", 4.0), bev=0)
            # a cold strip across the pod's top, in front of the hazard band (the tilted pod's back faces away from
            # the camera, its top faces up to it)
            bx((0.2, 0.012, 0.006), (0, -0.062, 0.0715), cold, bev=0)
        build_at(pod, 0, 0.01, tilt=(-0.42, 0), z=0.12)
        cy(0.005, 0.12, (-0.085, 0.07, 0.24), sd, 4)
        ico(0.011, (-0.085, 0.07, 0.305), glow("sensor", "#ff4a3a", 4.0))

        def dish():  # a small radar dish looking up and forward, its feed horn on a spike
            cn(0.04, 0.016, (0, 0, 0.0), flat("dish", "#d9dde2", 0.45), 10, rot=(math.pi, 0, 0))
            cy(0.003, 0.034, (0, 0, 0.012), sd, 4)
        # on a bracket off the right cheek of the head
        beam((0.136, 0.03, 0.1), (0.168, 0.03, 0.1), 0.012, sd)
        cy(0.006, 0.05, (0.168, 0.03, 0.12), sd, 4)
        build_at(dish, 0.168, 0.03, tilt=(0.45, 0.0), z=0.15)
    build_at(head, 0, 0, z=0.57)


def tower_l8():
    """Laser turret: a pylon of white composite plates with cyan seams on its edges, dark inset panels with cold light
    slits on the faces, an energy ring, capacitor pods round a stepped base, and a turret head with heat-sink fins
    and a glowing emitter."""
    comp = panels(COMP, "#a9b1bc", 0.06, 0.08, rivet=None, rough=0.4)
    trim = flat("comptrim", COMP_T, 0.5)
    cyan = glow("cyan", CYAN, 2.5)
    cy(0.25, 0.05, (0, 0, 0.025), trim, 6)
    cy(0.225, 0.07, (0, 0, 0.085), comp, 6, r2=0.185)
    cy(0.192, 0.012, (0, 0, 0.12), cyan, 6)
    z0, z1, r0, r1 = 0.12, 0.68, 0.13, 0.085
    cy(r0, z1 - z0, (0, 0, (z0 + z1) / 2), comp, 6, r2=r1)
    for k in (4, 3, 5, 0, 1, 2):  # glowing seams on the hexagonal pylon edges
        a = k * math.pi / 3
        beam((math.cos(a) * (r0 + 0.002), math.sin(a) * (r0 + 0.002), z0 + 0.02),
             (math.cos(a) * (r1 + 0.002), math.sin(a) * (r1 + 0.002), z1 - 0.03), 0.011, cyan if k in (4, 5, 3) else trim)
    # dark inset panels on the three front faces, each split by a cold light slit (the panelled towers of frame 5)
    pan, slit = ev._MB(), ev._MB()
    k6 = math.cos(math.pi / 6)
    for fa in (-math.pi / 2, -math.pi / 2 - math.pi / 3, -math.pi / 2 + math.pi / 3):
        c, s_ = math.cos(fa), math.sin(fa)
        tx, ty = -s_, c
        nrm = (c * 0.99, s_ * 0.99, (r0 - r1) / (z1 - z0) * k6)

        def P(z, u, off):
            rr = (r0 + (r1 - r0) * (z - z0) / (z1 - z0)) * k6 + off
            return (c * rr + tx * u, s_ * rr + ty * u, z)
        for (za, zb) in ((0.16, 0.33), (0.4, 0.6)):
            wa, wb = (r0 + (r1 - r0) * (za - z0) / (z1 - z0)) * 0.36, (r0 + (r1 - r0) * (zb - z0) / (z1 - z0)) * 0.36
            pan.face([P(za, -wa, 0.003), P(za, wa, 0.003), P(zb, wb, 0.003), P(zb, -wb, 0.003)], nrm)
            slit.face([P(za + 0.012, -0.005, 0.0045), P(za + 0.012, 0.005, 0.0045), P(zb - 0.012, 0.005, 0.0045),
                       P(zb - 0.012, -0.005, 0.0045)], nrm)
    pan.obj(flat("comp_dark", "#283241", 0.45), "inset_panels")
    slit.obj(cyan, "light_slits")
    torus(0.15, 0.012, (0, 0, 0.37), cyan, seg=16, mseg=4)
    for k in range(3):
        a = math.pi / 2 + k * math.tau / 3
        beam((math.cos(a) * 0.112, math.sin(a) * 0.112, 0.37), (math.cos(a) * 0.15, math.sin(a) * 0.15, 0.37), 0.016, trim)
    cy(0.11, 0.05, (0, 0, z1 + 0.02), trim, 10)
    # capacitor pods round the base: dark drums with glowing caps
    for k in range(3):
        a = -math.pi / 2 + math.pi / 3 + k * math.tau / 3
        px, py = math.cos(a) * 0.19, math.sin(a) * 0.19
        cy(0.032, 0.07, (px, py, 0.085), trim, 8)
        cy(0.026, 0.01, (px, py, 0.125), cyan, 8)
        cy(0.034, 0.008, (px, py, 0.06), comp, 8)

    def head():
        uvs(0.12, (0, 0.0, 0.07), comp, 12, 6, (1.0, 1.2, 0.72))
        cy(0.122, 0.022, (0, 0.0, 0.06), trim, 12, rot=(0, 0, 0)).scale = (1.0, 1.2, 1.0)
        torus(0.122, 0.006, (0, 0.0, 0.075), cyan, seg=12, mseg=3).scale = (1.0, 1.2, 1.0)
        bx((0.11, 0.02, 0.025), (0, -0.135, 0.1), flat("visor", "#1f2630", 0.3), bev=0, rot=(0.35, 0, 0))
        for sx in (-1, 1):  # side fins
            bx((0.02, 0.12, 0.05), (sx * 0.125, 0.03, 0.075), comp, bev=0.006, rot=(0.2, 0, 0))
            bx((0.022, 0.1, 0.008), (sx * 0.126, 0.03, 0.09), cyan, bev=0, rot=(0.2, 0, 0))
        # emitter barrel
        cy(0.034, 0.1, (0, -0.15, 0.06), trim, 10, r2=0.026, rot=(math.pi / 2, 0, 0))
        cy(0.038, 0.012, (0, -0.135, 0.06), cyan, 10, rot=(math.pi / 2, 0, 0))
        cy(0.031, 0.012, (0, -0.175, 0.06), cyan, 10, rot=(math.pi / 2, 0, 0))
        cy(0.024, 0.014, (0, -0.205, 0.06), glow("lens", "#9ff2ff", 5.0), 10, rot=(math.pi / 2, 0, 0))
        ico(0.016, (0, -0.21, 0.06), glow("lens", "#9ff2ff", 5.0))
        cy(0.004, 0.08, (0.05, 0.06, 0.18), trim, 4)
        ico(0.009, (0.05, 0.06, 0.22), cyan)
        for sx in (-1, 1):  # heat-sink ribs stacked on the outside of each side fin (in the fin's tilted frame)
            for zl in (-0.016, -0.005, 0.006):
                bx((0.016, 0.09, 0.006), (sx * 0.143, 0.03 - zl * math.sin(0.2), 0.075 + zl * math.cos(0.2)), trim,
                   bev=0, rot=(0.2, 0, 0))
    build_at(head, 0, 0.02, z=z1 + 0.03)


TOWERS = [tower_l1, tower_l2, tower_l3, tower_l4, tower_l5, tower_l6, tower_l7, tower_l8]
ASSETS = {f"tower_l{n + 1}": f for n, f in enumerate(TOWERS)}


# ------------------------------------------------------------------ export


# the stone courses, rivets, formwork lines and panel seams need the texels (and the glowing parts give theirs back);
# the timber towers keep the plain unwrap, whose thin beams carry their wood grain
ATLAS = set(os.environ.get("TOWER_ATLAS", ",".join(f"tower_l{n}" for n in range(3, 9))).split(","))


def export(name, out):
    """evolution_assets.export (lowpoly, 512 px bake, glTF) with the mesh origin moved to the model origin."""
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    ev.lowpoly(objs)
    ev._drop_ground_faces(objs)
    # the tight atlas of the residences: textured faces packed with one fixed margin, thin parts (rails, lashings,
    # battens, course lips) and flat colours on palette cells, so nothing small samples the black gutter
    ob = ev.bake_atlas(objs, 512) if name in ATLAS else ea.bake_asset(objs, 512)
    ob.name = name
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.calc_loop_triangles()
    tris = len(ob.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    vs = [v.co for v in ob.data.vertices]
    rad = max(math.hypot(v.x, v.y) for v in vs)
    print(f"EXPORTED {name}: tris={tris} radius={rad:.3f} zmin={min(v.z for v in vs):.3f} "
          f"height={max(v.z for v in vs):.3f} mats={[m_.name for m_ in ob.data.materials]}", flush=True)
    return tris, rad


# ------------------------------------------------------------------ contact sheet


def tower_sheet(model_dir, png, cols=None, tile=1.0, res=3200):
    """One row of grass hex tiles, a tower in the middle of each (levels left → right)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    cols = cols or list(range(1, 9))
    sp = max(2.05 * tile, 0.75)
    for ci, n in enumerate(cols):
        x = (ci - (len(cols) - 1) / 2) * sp
        kit.hex_prism("tile", (x, 0, 0), tile, 0.18, grass, dirt, 0.03)
        before = {o.name for o in bpy.context.scene.objects}
        bpy.ops.import_scene.gltf(filepath=os.path.join(model_dir, f"tower_l{n}.glb"))
        for o in bpy.context.scene.objects:
            if o.name not in before and o.parent is None:
                o.location.x += x
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
    cam.data.ortho_scale = len(cols) * sp + 0.2
    el = math.radians(46)
    se, ce = math.sin(el), math.cos(el)
    v_top = tile * 0.87 * se + 1.0 * ce
    v_bot = -tile * 0.87 * se - 0.2 * ce
    vc = (v_top + v_bot) / 2
    cam.location = (0.0, vc / se - 30 * ce, 30 * se)
    cam.rotation_euler = (math.pi / 2 - el, 0, 0)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x = res
    sc.render.resolution_y = int(res * (v_top - v_bot + 0.15) / cam.data.ortho_scale)
    sc.view_settings.view_transform = "AgX"
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    print("SHEET", png)


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0] if args else "game/assets/models"
    rest = args[1:]
    if "--sheet" in rest:
        png = rest[rest.index("--sheet") + 1]
        cols = [int(c) for c in rest[rest.index("--cols") + 1].split(",")] if "--cols" in rest else None
        tile = float(rest[rest.index("--tile") + 1]) if "--tile" in rest else 1.0
        res = int(rest[rest.index("--res") + 1]) if "--res" in rest else 3200
        tower_sheet(out, png, cols, tile, res)
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
    print("TRIS", {k: v[0] for k, v in report.items()})
