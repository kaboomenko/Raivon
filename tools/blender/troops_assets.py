"""Troops by development level (canon §6.1, column «Пехота / Штурм»): «ополченцы с вилами → штурмовики в броне».

Builds and exports to OUT (default game/assets/models):
  squad_dl{1..8}_{blue,red,green}.glb    infantry block of 12 figures, drop-in for squad_<team>.glb
  assault_dl{2..8}_{blue,red,green}.glb  the «Штурм» unit beside it, drop-in for knight_<team>.glb
      dl2 mounted rider · dl3 knight · dl4 dragoon · dl5 armoured car · dl6 WW2 tank ·
      dl7 main battle tank · dl8 hover tank

Run:   python3 tools/blender/troops_assets.py game/assets/models [name or glob, e.g. 'squad_dl3_*' ...]
Sheet: python3 tools/blender/troops_assets.py game/assets/models --sheet OUT.png [--team blue] [--ref]
       [--cols 4] [--dl 1,2,3]
       (one grass hex per DL with squad + assault + banner placed exactly like map_view.gd::_make_army;
        --ref adds the legacy squad_<team> + knight_<team> as a first tile for comparison)

Conventions (same as export_assets.py / evolution_assets.py): Z up, base on Z=0, origin = centre of the
unit's footprint, every figure and vehicle faces −Y in Blender = +Z in Godot (towards the default camera).
Figures are ~0.42 tall (1:6), the squad block spans ≈0.58 × 0.4 like squad_blue; vehicles are ≤0.34 wide.
Everything is joined and baked into one 512 px texture; emissive parts (torches, visors, hover pads) stay
a separate glowing material.
"""
import fnmatch
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
import evolution_assets as ev  # noqa: E402  (guarded as well)
from evolution_assets import (TEAMS, WHITE, GOLD, beam, build_at, bx, cn, cy, extrude, flat, glow,  # noqa: E402
                              mesh_obj, rod, shade, taper_box, tex, uvs)

SKIN = "#e8b48e"
STEEL = "#c3c9d1"
IRON = "#8d9399"
DARK = "#2b2d31"
RUBBER = "#26272a"
LEATHER = "#6b4a2f"
WOODC = "#7a5232"
OLIVE = "#5d6b3c"
KHAKI = "#b3a477"
DL3_MAIL = "#59606a"   # DL3 men-at-arms: dark mail and steel (the far view of reference frames 1 and 3)
DL3_STEEL = "#5a626e"  # the game sun lifts steel a lot: helmets and pauldrons are what the far camera sees


def mixc(a, b, t):
    """Blend two sRGB hex colours (t = 0 → a, 1 → b)."""
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(pa, pb))


def F(c, rough=0.75):
    return flat("t" + c, c, rough)


def M(c, rough=0.75):
    """F for a colour string; a ready material (camouflage) passes through."""
    return F(c, rough) if isinstance(c, str) else c


def team_glow(team, k=1.15, strength=5.0):
    return glow("team" + team, shade(team, k), strength)


def camo(base, dark, light, scale=9.0):
    """Three-tone world-space blotch camouflage (baked like any procedural colour)."""
    key = ("camo", base, dark, light, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("camo")
    m.use_nodes = True
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 1.5
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*kit.srgb(dark), 1)
    els[1].position = 0.43
    els[1].color = (*kit.srgb(base), 1)
    e = els.new(0.6)
    e.color = (*kit.srgb(light), 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    kit._MATS[key] = m
    return m


def fy(x, r):
    """Y of the front surface of an 8-sided torso / belt of radius r (a vertex at −Y) at lateral offset x: where a
    strap or pouch must sit to lie on the cloth instead of floating before it."""
    return -(r - abs(x) * 0.41421)


def netted(base, line, scale=46.0):
    """Helmet net: two crossing families of thin world-space bands over the base colour (baked like any colour)."""
    key = ("net", base, line, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("net")
    m.use_nodes = True
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    facs = []
    for rz in (0.0, math.pi / 2):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0, 0, rz)
        nt.links.new(geo.outputs["Position"], mp.inputs["Vector"])
        wv = nt.nodes.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = "DIAGONAL"
        wv.wave_profile = "SIN"
        wv.inputs["Scale"].default_value = scale
        wv.inputs["Distortion"].default_value = 0.0
        nt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
        facs.append(wv.outputs["Fac"])
    mx = nt.nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    nt.links.new(facs[0], mx.inputs[0])
    nt.links.new(facs[1], mx.inputs[1])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*kit.srgb(base), 1)
    els[1].position = 0.86
    els[1].color = (*kit.srgb(line), 1)
    nt.links.new(mx.outputs["Value"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.75
    kit._MATS[key] = m
    return m


def links(base, dark, scale=15.0):
    """Track links: dark bands across the track every link pitch along Y (world space, baked like any colour)."""
    key = ("links", base, dark, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("links")
    m.use_nodes = True
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = "Y"
    wv.wave_profile = "SIN"
    wv.inputs["Scale"].default_value = scale
    wv.inputs["Distortion"].default_value = 0.0
    nt.links.new(geo.outputs["Position"], wv.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*kit.srgb(base), 1)
    els[1].position = 0.62
    els[1].color = (*kit.srgb(dark), 1)
    nt.links.new(wv.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
    kit._MATS[key] = m
    return m


def side_prism(profile, w, mt, x=0.0):
    """Prism along X of width w from a (y, z) side profile — hulls seen from the side."""
    n = len(profile)
    verts = [(x - w / 2, y, z) for y, z in profile] + [(x + w / 2, y, z) for y, z in profile]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    return mesh_obj(verts, faces, mt)


def taper_extrude(pts, z0, z1, mt, k=0.8, loc=(0, 0, 0)):
    """Prism from a 2D polygon whose top is scaled by k (sloped turret sides)."""
    n = len(pts)
    verts = [(x, y, z0) for x, y in pts] + [(x * k, y * k, z1) for x, y in pts]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return mesh_obj(verts, faces, mt, loc)


def disc(r, loc, mt, axis="x", n=10, h=0.01):
    """Thin round plate facing ±X (axis 'x') or ±Y (axis 'y')."""
    rot = (0, math.pi / 2, 0) if axis == "x" else (math.pi / 2, 0, 0)
    return cy(r, h, loc, mt, n, rot=rot)


# the white displayed eagle of the reference banners and shields (frames 3–5): wings raised high with feathered
# tips, a small head, legs with talons spread, a fanned tail — a 30-point outline in a unit box (u right, v up),
# mirror-symmetric with exactly two centre-line points (badge_on cuts it there)
_EAGLE_R = [(0.0, 0.36), (0.07, 0.28), (0.055, 0.18), (0.18, 0.3), (0.3, 0.5), (0.34, 0.36), (0.5, 0.4), (0.4, 0.2),
            (0.5, 0.14), (0.3, 0.02), (0.11, -0.02), (0.1, -0.16), (0.24, -0.26), (0.08, -0.28), (0.14, -0.5),
            (0.0, -0.42)]
EAGLE = _EAGLE_R + [(-u, v) for u, v in _EAGLE_R[1:-1]][::-1]
# a 12-point eagle (raised wings, head, fanned tail) for emblems too small to show the full outline
_EAGLE_S_R = [(0.0, 0.42), (0.1, 0.2), (0.5, 0.48), (0.38, 0.06), (0.14, -0.04), (0.22, -0.48), (0.0, -0.32)]
EAGLE_S = _EAGLE_S_R + [(-u, v) for u, v in _EAGLE_S_R[1:-1]][::-1]


def face_obj(polys, n, mt, two=0.0):
    """One-sided flat polygon(s) wound explicitly towards normal n — never `mesh_obj`, whose normal recalculation
    picks an arbitrary side for a lone face, and the in-game troops shader culls back faces. `two` > 0 adds the
    mirror face(s) `two` behind, wound the other way, for flags seen from both sides."""
    verts, faces = [], []

    def add(pts, nn):
        # Newell normal: the true winding of any (also concave) outline, unlike the first-corner cross product
        s = [0.0, 0.0, 0.0]
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            s[0] += (p[1] - q[1]) * (p[2] + q[2])
            s[1] += (p[2] - q[2]) * (p[0] + q[0])
            s[2] += (p[0] - q[0]) * (p[1] + q[1])
        if s[0] * nn[0] + s[1] * nn[1] + s[2] * nn[2] < 0:
            pts = pts[::-1]
        faces.append(tuple(range(len(verts), len(verts) + len(pts))))
        verts.extend(tuple(p) for p in pts)
    nx, ny, nz = n
    for pts in polys:
        if two:
            h = two / 2
            add([(p[0] + nx * h, p[1] + ny * h, p[2] + nz * h) for p in pts], n)
            add([(p[0] - nx * h, p[1] - ny * h, p[2] - nz * h) for p in pts], (-nx, -ny, -nz))
        else:
            add(list(pts), n)
    me = bpy.data.meshes.new("badge")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new("badge", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mt)
    return o


def badge(w, h, loc, mt, face="-y", pts=EAGLE, tilt=0.0, side=-1, two=0.0):
    """Flat one-polygon emblem w × h centred at loc. face '-y': upright, facing −Y (side=+1 faces +Y), `tilt` leans
    its top back (radians) to lie on a sloped plate; 'x': on a flank, facing side·X; 'z': lying on a roof, facing up
    with its top towards +Y so it reads upright from the game camera in front. Wound explicitly (see face_obj)."""
    x, y, z = loc
    ct, st = math.cos(tilt), math.sin(tilt)
    if face == "x":
        verts = [(x, y + u * w, z + v * h) for u, v in pts]
        n = (side, 0, 0)
    elif face == "z":
        verts = [(x + u * w, y + v * h, z) for u, v in pts]
        n = (0, 0, 1)
    else:
        verts = [(x + u * w, y + v * h * st, z + v * h * ct) for u, v in pts]
        n = (0, side * ct, -side * st)
    return face_obj([verts], n, mt, two)


def badge_on(target, w, h, loc, mt, axis="y", side=-1, pts=EAGLE, off=0.0025):
    """Emblem laid onto a curved, faceted surface (a caparison): every outline point is cast onto `target` along the
    view axis and lifted `off` back towards the viewer, and the outline is cut in two along its vertical centre
    line so each half follows its own facet instead of bridging under the cloth. axis 'y' + side −1 = seen from the
    front, axis 'x' + side ±1 = seen from that flank, axis 'z' = seen from above (its top towards +Y, like badge
    'z'; loc z is ignored)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    me = target.data
    tree = BVHTree.FromPolygons([target.matrix_world @ v.co for v in me.vertices], [p.vertices for p in me.polygons])
    x, y, z = loc
    d = {"y": Vector((0, -side, 0)), "x": Vector((-side, 0, 0)), "z": Vector((0, 0, -1))}[axis]  # into the surface

    def place(u, v):
        if axis == "z":
            p = Vector((x + u * w, y + v * h, 2.0))
        else:
            p = Vector((x + u * w, y + side, z + v * h)) if axis == "y" else Vector((x + side, y + u * w, z + v * h))
        hit = tree.ray_cast(p, d, 2.0)[0]
        assert hit is not None, "badge_on: outline point off the target surface"
        return tuple(hit - d * off)
    k0 = [i for i, (u, _) in enumerate(pts) if abs(u) < 1e-9]
    if len(k0) == 2:  # symmetric outline: split at its two centre-line points
        a, b = k0
        halves = [pts[a:b + 1], pts[b:] + pts[:a + 1]]
    else:
        halves = [pts]
    polys = [[place(u, v) for u, v in hp] for hp in halves]
    return face_obj(polys, tuple(-d), mt)


def surface_band(targets, c, tilt, phis, h, mt, off=0.0025):
    """Strap lying on a faceted body (the horse's chest): a band of height h in the plane through c tilted `tilt`
    about X (front dipping), its edge points cast onto `targets` from outside towards c and lifted `off` — so it
    follows the facets instead of cutting through them. phis = angles round the body, 0 = the front (−Y)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    vs, fs = [], []
    for t in targets:
        b = len(vs)
        vs += [t.matrix_world @ v.co for v in t.data.vertices]
        fs += [[b + i for i in p_.vertices] for p_ in t.data.polygons]
    tree = BVHTree.FromPolygons(vs, fs)
    c = Vector(c)
    fwd = Vector((0, -math.cos(tilt), -math.sin(tilt)))
    nrm = Vector((0, -math.sin(tilt), math.cos(tilt)))
    rows = []
    for e in (-h / 2, h / 2):
        row = []
        for ph in phis:
            d = (fwd * math.cos(ph) + Vector((math.sin(ph), 0, 0))).normalized()
            o = c + nrm * e + d * 0.4
            hit = tree.ray_cast(o, -d, 0.8)[0]
            row.append(tuple((hit if hit is not None else c + nrm * e) + d * off))
        rows.append(row)
    quads = []
    for k in range(len(phis) - 1):
        q = [rows[0][k], rows[0][k + 1], rows[1][k + 1], rows[1][k]]
        mid = sum((Vector(p_) for p_ in q), Vector()) / 4
        quads.append((q, tuple(mid - c - nrm * (nrm.dot(mid - c)))))
    o = None
    for q, n_ in quads:
        o = face_obj([q], n_, mt)
    return o


STAR = [((0.5 if k % 2 == 0 else 0.2) * math.sin(k * math.pi / 5), (0.5 if k % 2 == 0 else 0.2) * math.cos(k * math.pi / 5))
        for k in range(10)]
CIRCLE = [(0.5 * math.cos(math.tau * k / 12), 0.5 * math.sin(math.tau * k / 12)) for k in range(12)]
CHEVRON = [(0.0, 0.5), (0.5, -0.2), (0.5, -0.5), (0.0, 0.1), (-0.5, -0.5), (-0.5, -0.2)]


def ell(ax, ay, z, n, cx=0.0, cy_=0.0, a0=0.0, zf=None):
    """n points of a horizontal ellipse (z may vary per point through zf(k))."""
    return [(cx + ax * math.cos(a0 + math.tau * k / n), cy_ + ay * math.sin(a0 + math.tau * k / n),
             zf(k) if zf else z) for k in range(n)]


def loft(rings, mt, cap0=False, cap1=False):
    """Skin consecutive rings of equal length (open tube), optionally capping the first / last ring."""
    n = len(rings[0])
    verts = [p for r in rings for p in r]
    faces = []
    for i in range(len(rings) - 1):
        a, b = i * n, (i + 1) * n
        faces += [(a + k, a + (k + 1) % n, b + (k + 1) % n, b + k) for k in range(n)]
    if cap0:
        faces.append(tuple(range(n)))
    if cap1:
        faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    o = mesh_obj(verts, faces, mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


def pennant(top, bot, length, mt, band=None, fork=0.35):
    """Swallow-tailed pennant in the YZ plane hanging from a pole between `top` and `bot`, flying towards +Y;
    `band` = a second colour along the hoist."""
    (x, y0, z0), (_, y1, z1) = top, bot
    zm = (z0 + z1) / 2
    pts = [(y0, z0), (y0 + length, z0 - 0.006), (y0 + length * (1 - fork), zm), (y1 + length, z1 + 0.006), (y1, z1)]
    o = face_obj([[(x, a, b) for a, b in pts]], (1, 0, 0), mt, two=0.0012)  # both faces: seen from either side
    if band:
        k = 0.28
        bp = [(y0, z0), (y0 + length * k, z0 - 0.006 * k), (y1 + length * k, z1 + 0.006 * k), (y1, z1)]
        for sx in (-1, 1):  # the hoist band on each face, wound outwards
            face_obj([[(x + sx * 0.0018, a, b) for a, b in bp]], (sx, 0, 0), band)
    return o


# ====================================================================== FIGURES
# One soldier at the origin facing −Y. Body: legs to 0.17, torso 0.16–0.31, head centre 0.355.
# `seated` lifts the body by SEAT and bends the legs astride a horse (horse back at ≈0.33).

SEAT = 0.2
SH = 0.056  # shoulder half-width


def ring(r, h, loc, mt, n=8, r2=None, a0=0.0):
    """Open tube (no caps): belts, skirts, bands — half the triangles of a capped cylinder. a0 turns the polygon
    (π/n puts a flat face, not an edge, to the front)."""
    r2 = r if r2 is None else r2
    x, y, z = loc
    verts = [(x + r * math.cos(a0 + math.tau * k / n), y + r * math.sin(a0 + math.tau * k / n), z - h / 2) for k in range(n)]
    verts += [(x + r2 * math.cos(a0 + math.tau * k / n), y + r2 * math.sin(a0 + math.tau * k / n), z + h / 2) for k in range(n)]
    faces = [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    o = mesh_obj(verts, faces, mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


SPREAD = 0.024  # riders sit astride a saddle cloth / caparison: knees and boots outside the hanging cloth


def _legs(Z, seated, trouser, boot, r=0.017, boot_h=0.03, gaiter=None):
    """Legs (one 5-sided tube each) and boots; `gaiter` = gaiters / puttees / greaves up to the knee."""
    t, b = M(trouser, 0.85), F(boot, 0.8)
    for sx in (-1, 1):
        if seated:
            kx, bxx = sx * (0.068 + SPREAD), sx * (0.072 + SPREAD)
            knee = (kx, -0.06, Z + 0.15)
            rod((sx * 0.03, 0, Z + 0.17), knee, r, t, n=5)
            rod(knee, (bxx, -0.045, Z + 0.035), r * 0.95, F(gaiter, 0.8) if gaiter else t, n=5)
            bx((0.03, 0.05, boot_h), (bxx, -0.052, Z + 0.015), b, bev=0)
        else:
            rod((sx * 0.022, 0, 0.175), (sx * 0.025, 0, 0.02), r, t, r2=r * 0.9, n=5)
            if gaiter:
                bx((0.03, 0.032, 0.06), (sx * 0.025, -0.001, 0.055), M(gaiter, 0.8), bev=0)
            bx((0.032, 0.05, boot_h), (sx * 0.025, -0.008, boot_h / 2), b, bev=0)


def _torso(Z, c, r0=0.043, r1=0.05, skirt=None, skirt_len=0.07):
    cy(r0, 0.15, (0, 0, Z + 0.235), M(c), 8, r2=r1)
    if skirt:
        ring(0.058, skirt_len, (0, 0, Z + 0.165 - skirt_len / 2 + 0.02), F(skirt), 8, r2=0.046)


def _arm(Z, sx, hand, c, r=0.014):
    rod((sx * SH, 0, Z + 0.295), (hand[0], hand[1], Z + hand[2]), r, M(c), r2=r * 0.85, n=5)


def _head(Z, skin=SKIN):
    uvs(0.033, (0, -0.002, Z + 0.355), F(skin, 0.7), 8, 4)


def _belt(Z, c, z=0.175, r=0.047):
    ring(r, 0.016, (0, 0, Z + z), F(c), 8)


def _vertical(Z, x, y, z0, z1, mt, r=0.0062, n=4):
    rod((x, y, Z + z0), (x, y, Z + z1), r, mt, n=n)


def _round_shield(Z, face, rim, x=-0.066, y=-0.05, z=0.215, r=0.058):
    """Round shield: a bright iron rim, the team face and the white eagle (reference frames 3–4)."""
    disc(r, (x, y + 0.004, Z + z), F(rim, 0.4), "y", 10, 0.01)
    disc(r * 0.84, (x, y - 0.002, Z + z), F(face, 0.7), "y", 10, 0.01)
    badge(r * 1.1, r * 1.1, (x, y - 0.0095, Z + z), F(WHITE, 0.6))


HEATER = [(-0.038, 0.05), (0.038, 0.05), (0.038, 0.0), (0.03, -0.035), (0.016, -0.06), (0.0, -0.075), (-0.016, -0.06),
          (-0.03, -0.035), (-0.038, 0.0)]


def plate_xz(pts, loc, t, mt, k=1.0):
    """Prism of thickness t (along Y) from an (x, z) outline scaled by k, centred at loc."""
    x, y, z = loc
    n = len(pts)
    verts = [(x + u * k, y - t / 2, z + v * k) for u, v in pts] + [(x + u * k, y + t / 2, z + v * k) for u, v in pts]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return mesh_obj(verts, faces, mt)


def _heater_shield(Z, team, x=-0.066, y=-0.052, z=0.215, rim=STEEL, field=None):
    """Heater shield of the reference knights (frame 3): steel border, team field, white eagle."""
    plate_xz(HEATER, (x, y + 0.004, Z + z), 0.008, F(rim, 0.35), 1.16)
    plate_xz(HEATER, (x, y - 0.002, Z + z), 0.008, F(field or team, 0.7))
    badge(0.05, 0.056, (x, y - 0.0085, Z + z - 0.004), F(WHITE, 0.6))


def _surcoat(Z, team, hem=0.085, top=0.302, waist=0.18, r=0.058, flare=0.066, k=0.86):
    """Team surcoat over the mail, flat-fronted (an octagon turned a half step) so the white eagle lies on it,
    flaring into a skirt to the knees."""
    a0 = math.pi / 8
    loft([ell(r, r, Z + top, 8, a0=a0), ell(r, r, Z + waist, 8, a0=a0), ell(flare, flare, Z + hem, 8, a0=a0)],
         F(shade(team, k), 0.7))  # a deeper blue than the banners, as on the reference soldiers
    badge(0.04, 0.044, (0, -r * math.cos(a0) - 0.003, Z + 0.252), F(WHITE, 0.6))
    ring(r + 0.004, 0.016, (0, 0, Z + waist), F(LEATHER, 0.7), 8, a0=a0)  # sword belt


def _pauldrons(Z, mt, r=0.03):
    """Layered steel shoulder plates — the brightest spot of a reference soldier at map distance: a domed plate
    over a broader flat lame (both closed, so they hold up from every side)."""
    for sx in (-1, 1):
        uvs(r, (sx * 0.057, 0, Z + 0.3), mt, 6, 3, (1.1, 1.15, 0.72))
        uvs(r, (sx * 0.061, 0, Z + 0.277), mt, 6, 3, (1.15, 1.2, 0.35))


def _sash(Z, mt, r=0.057, h=0.012, tilt=0.6, z=0.245):
    """Strap from the right shoulder to the left hip: a band tilted about the body axis, elliptical so it keeps
    the same distance from the torso all the way round (a tilted circle would sink into the sides)."""
    o = loft([ell(r / math.cos(tilt), r, -h / 2, 10), ell(r / math.cos(tilt), r, h / 2, 10)], mt)
    o.location = (0, 0, Z + z)
    o.rotation_euler.y = -tilt
    return o


def _cape(Z, c, top=0.3, hem=0.11, m=5):
    """Short cloth cape wrapped round the back from under the pauldrons to above the surcoat hem: a curved shell
    6 mm thick hugging the surcoat, widening and falling into folds at the hem (reference frame 4)."""
    rings = []
    for z, R, half, fold in ((top, 0.059, 0.95, 0.0), (0.2, 0.0625, 1.05, 0.0), (hem, 0.069, 1.15, 0.005)):
        arc = [math.pi / 2 - half + 2 * half * k / (m - 1) for k in range(m)]
        rr = [R + fold * (k % 2) for k in range(m)]
        outer = [((r_ + 0.006) * math.cos(a), (r_ + 0.006) * math.sin(a), Z + z) for a, r_ in zip(arc, rr)]
        inner = [(r_ * math.cos(a), r_ * math.sin(a), Z + z) for a, r_ in zip(arc, rr)]
        rings.append(outer + inner[::-1])
    o = loft(rings, F(c, 0.8), cap0=True, cap1=True)
    for p_ in o.data.polygons:
        p_.use_smooth = False
    return o


def _roll(Z, mt, r=0.061, rt=0.011, tilt=0.72, z=0.248, n=12, m=4, side=1):
    """Blanket roll worn horseshoe-fashion from one shoulder (side +1: the +X one) over the chest to the opposite
    hip: a closed tube (m-sided) round a tilted ellipse that is a circle of radius r seen from above, so it keeps
    clear of the torso all the way round (like _sash)."""
    a, b = r / math.cos(tilt), r
    verts = []
    for k in range(n):
        t = math.tau * k / n
        px, py = a * math.cos(t), b * math.sin(t)
        gx, gy = math.cos(t) / a, math.sin(t) / b  # in-plane outward normal of the ellipse
        gl = math.hypot(gx, gy)
        gx, gy = gx / gl, gy / gl
        for j in range(m):
            ph = math.tau * j / m + math.pi / 4
            verts.append((px + rt * math.cos(ph) * gx, py + rt * math.cos(ph) * gy, rt * math.sin(ph)))
    faces = [(k * m + j, k * m + (j + 1) % m, ((k + 1) % n) * m + (j + 1) % m, ((k + 1) % n) * m + j)
             for k in range(n) for j in range(m)]
    o = mesh_obj(verts, faces, mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    o.location = (0, 0, Z + z)
    o.rotation_euler.y = -tilt * side
    return o


def figure(dl, team, v=0, seated=False):
    """Infantryman of development level dl (v = variant: weapons, headgear) facing −Y."""
    Z = SEAT if seated else 0.0
    rnd = random.Random(v * 31 + dl)
    if dl == 1:  # militia: tunic, rope belt, straw hat / hood / bare head; pitchfork, torch or axe
        tunic = (team, shade(team, 0.78), mixc(team, "#8a6a44", 0.35))[v % 3]
        _legs(Z, seated, ("#7a5a3a", "#5e4630", "#6d5d48")[v % 3], "#4a3526", gaiter="#9c8662")
        _torso(Z, tunic, skirt=tunic, skirt_len=0.08)
        _belt(Z, "#c9a86a", 0.18, 0.046)
        _head(Z)
        hat = v % 4
        if hat == 0:  # straw hat
            cy(0.062, 0.008, (0, 0, Z + 0.375), F("#e0bf6a", 0.85), 10)
            cy(0.03, 0.04, (0, 0, Z + 0.395), F("#d8b25c", 0.85), 8, r2=0.022)
        elif hat == 1:  # hood
            cy(0.042, 0.075, (0, 0.006, Z + 0.37), F("#7d6a52", 0.9), 8, r2=0.012)
        elif hat == 2:  # cap
            uvs(0.035, (0, 0.002, Z + 0.37), F("#8a3a2a", 0.9), 8, 4, (1, 1, 0.65))
        else:  # hair
            uvs(0.034, (0, 0.004, Z + 0.364), F("#4a3020", 0.9), 8, 4, (1, 1, 0.7))
        wood = F("#8a6038", 0.8)
        kind = ("fork", "fork", "torch", "fork", "axe", "fork")[v % 6]
        hx, hy = 0.066, -0.04
        _arm(Z, 1, (hx, hy, 0.22), tunic)
        if v % 3 == 1:
            _arm(Z, -1, (-0.07, -0.03, 0.43), tunic)  # shaking a fist
            bx((0.022, 0.022, 0.024), (-0.071, -0.03, Z + 0.445), F(SKIN), bev=0)
        else:
            _arm(Z, -1, (-0.06, -0.02, 0.17), tunic)
        if kind == "fork":
            _vertical(Z, hx, hy, 0.05, 0.58, wood)
            iron = F("#7f858c", 0.5)
            bx((0.05, 0.008, 0.009), (hx, hy, Z + 0.585), iron, bev=0)
            for dx in (-0.021, 0.0, 0.021):
                bx((0.007, 0.007, 0.065), (hx + dx, hy, Z + 0.62), iron, bev=0)
        elif kind == "torch":
            _vertical(Z, hx, hy, 0.12, 0.5, wood)
            cy(0.016, 0.03, (hx, hy, Z + 0.5), F("#3a2a1c"), 6)
            cn(0.024, 0.075, (hx, hy, Z + 0.55), glow("fire", "#ff6a10", 4.0), 6)
        else:
            _vertical(Z, hx, hy, 0.12, 0.48, wood)
            bx((0.05, 0.008, 0.045), (hx + 0.02, hy, Z + 0.46), F("#9aa0a6", 0.45), bev=0)
    elif dl == 2:  # spearmen: quilted gambeson, leather baldric, iron spaulders, kettle hat, eagle shield, long spear
        _legs(Z, seated, "#4a3f35", LEATHER, gaiter="#8a7356")
        gam = shade(team, 0.9)
        _torso(Z, gam, 0.046, 0.052, skirt=shade(team, 0.75), skirt_len=0.09)
        _belt(Z, LEATHER, 0.18, 0.05)
        _sash(Z, F(LEATHER, 0.75))
        _head(Z)
        iron = F("#aab1b9", 0.4)  # kettle hat: a dome over a downturned brim, the face shows beneath it
        uvs(0.034, (0, 0, Z + 0.377), iron, 8, 4, (1, 1, 0.8))
        cy(0.051, 0.017, (0, 0, Z + 0.368), iron, 10, r2=0.031)
        for sx in (-1, 1):  # iron spaulders
            uvs(0.027, (sx * 0.056, 0, Z + 0.298), F("#9ba2aa", 0.4), 6, 3, (1.05, 1.1, 0.72))
        hx, hy = 0.068, -0.045
        _arm(Z, 1, (hx, hy, 0.24), gam)
        _arm(Z, -1, (-0.06, -0.04, 0.22), gam)
        _vertical(Z, hx, hy, 0.03 if not seated else 0.17, 0.7, F("#8a6038", 0.8))  # a rider rests it on his thigh
        cn(0.015, 0.06, (hx, hy, Z + 0.73), F(STEEL, 0.35), 5)
        _round_shield(Z, team, "#c3c9d1")
    elif dl == 3:  # men-at-arms: mail, team surcoat with the white eagle, steel pauldrons, nasal helm, heater shield,
        # short cape (reference frames 3–4: blue surcoats over steel, bright shoulder plates, capes)
        # the far view of reference frames 1 and 3 reads these men as deep team blue over dark steel: blued, darker
        # mail and helmets, a deeper surcoat and cape, a darker shield rim — only the eagles stay white
        mail = DL3_MAIL
        # blued steel like the reference helmets (a cold steel tint for the other teams: a red tint reads pink)
        helm = F(mixc(DL3_STEEL, team if team == TEAMS["blue"] else "#4a5872", 0.18), 0.35)
        _legs(Z, seated, "#2e2826", "#3b291c")
        _torso(Z, mail, 0.045, 0.052)
        _surcoat(Z, team, hem=0.085 if not seated else 0.14, k=0.64)
        if not seated:
            _cape(Z, shade(team, 0.48))
        _pauldrons(Z, F(DL3_STEEL, 0.35))
        _head(Z)
        cn(0.038, 0.06, (0, 0.002, Z + 0.39), helm, 8)
        ring(0.039, 0.012, (0, 0.002, Z + 0.364), helm, 8)
        bx((0.008, 0.01, 0.03), (0, -0.035, Z + 0.355), helm, bev=0)
        _arm(Z, 1, (0.08, -0.05, 0.37), mail)
        _arm(Z, -1, (-0.062, -0.04, 0.22), mail)
        beam((0.082, -0.055, Z + 0.39), (0.092, -0.06, Z + 0.56), 0.011, F("#8c939c", 0.3))
        bx((0.045, 0.012, 0.01), (0.081, -0.055, Z + 0.385), F(GOLD, 0.4), bev=0)
        _heater_shield(Z, team, rim="#6b7480", field=shade(team, 0.82))
    elif dl == 4:  # musketeers: long coat, white cross belts, tricorn; shouldered musket with bayonet
        coat = team
        _legs(Z, seated, "#ece6d6", "#262222", gaiter="#2e2a2a")
        _torso(Z, coat, 0.045, 0.051, skirt=shade(team, 0.82), skirt_len=0.12)
        w = F(WHITE, 0.6)
        for s in (-1, 1):
            b = bx((0.012, 0.012, 0.15), (0, -0.046, Z + 0.24), w, bev=0)
            b.rotation_euler.y = s * 0.55
        _belt(Z, WHITE, 0.175, 0.049)
        bx((0.018, 0.005, 0.018), (0, -0.0525, Z + 0.24), F(GOLD, 0.4), bev=0, rot=(0, math.pi / 4, 0))  # belt plate
        for sx in (-1, 1):  # gold shoulder knots
            uvs(0.021, (sx * 0.052, 0, Z + 0.303), F(GOLD, 0.45), 6, 3, (1.15, 1.2, 0.55))
        if not seated:  # hide knapsack with a rolled grey blanket on top
            bx((0.072, 0.03, 0.075), (0, 0.062, Z + 0.245), F("#6e4a2c", 0.8), bev=0)
            cy(0.017, 0.084, (0, 0.062, Z + 0.297), F("#b9b4a8", 0.85), 6, rot=(0, math.pi / 2, 0))
        _head(Z)
        o = extrude(ev.ngon(0.064, 3, -math.pi / 2), 0, 0.024, F("#1f1c1c", 0.8))
        o.location = (0, 0.008, Z + 0.375)
        o = extrude(ev.ngon(0.067, 3, -math.pi / 2), 0, 0.006, F(GOLD, 0.5))
        o.location = (0, 0.008, Z + 0.372)
        cy(0.031, 0.03, (0, 0.006, Z + 0.4), F("#1f1c1c", 0.8), 8, r2=0.027)
        if v % 12 == 9 and not seated:  # standard-bearer
            _arm(Z, 1, (0.06, -0.04, 0.3), coat)
            _arm(Z, -1, (-0.04, -0.05, 0.25), coat)
            _vertical(Z, 0.06, -0.04, 0.05, 0.8, F("#d9d2c3", 0.5))
            bx((0.15, 0.008, 0.1), (0.135, -0.04, Z + 0.74), F(team, 0.7), bev=0)
            for sy in (-1, 1):  # the white eagle on both faces of the colour
                badge(0.07, 0.074, (0.138, -0.04 + sy * 0.0065, Z + 0.74), F(WHITE, 0.6), side=sy)
            uvs(0.012, (0.06, -0.04, Z + 0.81), F(GOLD, 0.4), 6, 4)
        else:
            _arm(Z, 1, (0.066, -0.035, 0.2), coat)
            _arm(Z, -1, (-0.06, -0.02, 0.17), coat)
            rod((0.068, -0.036, Z + 0.1), (0.074, -0.01, Z + 0.4), 0.008, F("#6b4226", 0.8), n=4)
            rod((0.074, -0.01, Z + 0.4), (0.077, 0.002, Z + 0.56), 0.005, F(IRON, 0.4), n=4)
            rod((0.077, 0.002, Z + 0.56), (0.079, 0.008, Z + 0.63), 0.004, F(STEEL, 0.3), r2=0.0005, n=4)
    elif dl == 5:  # riflemen c. 1900: deep team tunic, shako with a white pompom and a brass plate, a grey blanket
        # roll worn across the chest, leather belt with cartridge pouches, puttees; knapsack with a mess tin; shouldered
        # rifle with bayonet (far view of reference frames 1 and 3: deep team colour, a light accent on every man)
        tun = shade(team, 0.64)
        blk = F("#1d1b1a", 0.45)
        _legs(Z, seated, shade(team, 0.42), "#33251a", gaiter="#9d9070")
        _torso(Z, tun, 0.044, 0.05, skirt=tun, skirt_len=0.05)
        _belt(Z, "#4a3322", 0.18, 0.048)
        bx((0.013, 0.005, 0.013), (0, -0.0495, Z + 0.18), F(GOLD, 0.4), bev=0)  # buckle
        for s in (-1, 1):  # cartridge pouches either side of the buckle
            bx((0.02, 0.012, 0.022), (s * 0.026, fy(0.026, 0.048) - 0.005, Z + 0.186), F("#2c2119", 0.7), bev=0,
               rz=s * math.pi / 8)
        _roll(Z, F("#9a958a", 0.9), side=-1)
        if not seated:  # hide knapsack hanging on its shoulder straps behind the roll, its flap, a mess tin on top
            bx((0.07, 0.034, 0.074), (0, 0.09, Z + 0.255), F("#5b3f27", 0.8), bev=0)
            bx((0.072, 0.036, 0.026), (0, 0.09, Z + 0.282), F("#6e4e32", 0.8), bev=0)
            cy(0.014, 0.046, (0.006, 0.092, Z + 0.303), F("#9aa0a6", 0.45), 6, rot=(0, math.pi / 2, 0))
            for s in (-1, 1):
                beam((s * 0.025, 0.074, Z + 0.293), (s * 0.027, 0.012, Z + 0.318), 0.008, F("#3a2819", 0.7))
        _head(Z)
        cap = F(shade(team, 0.5), 0.7)  # shako: a flaring team body, black top, band and peak
        cy(0.032, 0.046, (0, 0.004, Z + 0.394), cap, 8, r2=0.036)
        cy(0.0365, 0.006, (0, 0.004, Z + 0.42), blk, 8)
        ring(0.0335, 0.01, (0, 0.004, Z + 0.375), blk, 8)
        bx((0.05, 0.03, 0.006), (0, -0.034, Z + 0.373), blk, bev=0, rot=(0.25, 0, 0))
        bx((0.017, 0.006, 0.019), (0, -0.031, Z + 0.398), F(GOLD, 0.4), bev=0, rot=(0, math.pi / 4, 0))  # plate
        uvs(0.0095, (0, -0.018, Z + 0.432), F(WHITE, 0.7), 6, 4)  # pompom
        _arm(Z, 1, (0.066, -0.035, 0.2), tun)
        _arm(Z, -1, (-0.06, -0.02, 0.17), tun)
        rod((0.068, -0.036, Z + 0.1), (0.074, -0.012, Z + 0.37), 0.008, F("#5a3a22", 0.8), n=4)
        rod((0.074, -0.012, Z + 0.37), (0.076, -0.004, Z + 0.47), 0.0045, F(DARK, 0.4), n=4)
        rod((0.076, -0.004, Z + 0.47), (0.078, 0.002, Z + 0.55), 0.004, F(STEEL, 0.3), r2=0.0005, n=4)
    elif dl == 6:  # WW2 infantry: netted steel helmet with foliage, pale webbing (Y-straps down the chest, a row of
        # ammo pouches), a big pack with a blanket roll and an entrenching tool; rifle with a leather sling at port arms
        jac = mixc(shade(team, 0.6), OLIVE, 0.2)
        _legs(Z, seated, "#4b4e40", "#2a2522", gaiter="#8f8566")
        _torso(Z, jac, 0.045, 0.05, skirt=jac, skirt_len=0.05)
        wc = "#c4b588"  # pale webbing: light lines on the dark tunic that read from far
        web = F(wc, 0.8)
        _belt(Z, wc, 0.18, 0.049)
        for s in (-1, 1):
            bx((0.012, 0.1, 0.008), (s * 0.03, 0, Z + 0.313), web, bev=0)  # over the shoulder
            beam((s * 0.031, fy(0.031, 0.05) - 0.003, Z + 0.31), (s * 0.022, fy(0.022, 0.0455) - 0.003, Z + 0.19),
                 0.009, web)  # down the chest to the belt
            for k, x in enumerate((0.016, 0.034)):  # two ammo pouches either side of the buckle
                bx((0.016, 0.012, 0.024), (s * x, fy(x, 0.049) - 0.0045, Z + 0.19), web, bev=0, rz=s * math.pi / 8)
        if not seated:
            if v % 6 != 4:  # pack with a blanket roll on top and an entrenching tool strapped on its back
                bx((0.074, 0.038, 0.08), (0, 0.064, Z + 0.25), F("#5b6040"), bev=0)
                cy(0.016, 0.088, (0, 0.064, Z + 0.304), F("#8a7f62", 0.9), 6, rot=(0, math.pi / 2, 0))
                bx((0.03, 0.006, 0.036), (0, 0.086, Z + 0.226), F("#3f4433", 0.6), bev=0)
                rod((0, 0.086, Z + 0.244), (0, 0.086, Z + 0.3), 0.0045, F("#7a5232", 0.8), n=4)
            else:  # radio operator
                bx((0.065, 0.04, 0.09), (0, 0.065, Z + 0.26), F("#4a4e38"), bev=0)
                _vertical(Z, 0.02, 0.07, 0.3, 0.62, F(DARK), 0.003, 4)
        _head(Z)
        hel = netted(OLIVE, "#3a4226")
        uvs(0.041, (0, 0.002, Z + 0.37), hel, 8, 4, (1, 1.05, 0.62))
        cy(0.047, 0.006, (0, 0.002, Z + 0.37), hel, 8)
        for k, (ax, ay) in enumerate(((-0.022, -0.012), (0.02, 0.016), (0.002, 0.026))):  # foliage in the net:
            # flat clumps lying on the dome (seated on its surface, tilted with its slope)
            zs = 0.37 + 0.0254 * math.sqrt(max(0.0, 1 - (ax / 0.041) ** 2 - ((ay - 0.002) / 0.043) ** 2))
            o = uvs(0.0115 - 0.0015 * (k == 2), (ax, ay, Z + zs + 0.001), F(("#587a2c", "#6d8238", "#4d6a2a")[k], 0.9),
                    5, 3, (1.35, 1.1, 0.6))
            o.rotation_euler = (-(ay - 0.002) * 12, ax * 12, k * 1.1)
        _arm(Z, 1, (0.045, -0.07, 0.2), jac)
        _arm(Z, -1, (-0.035, -0.075, 0.3), jac)
        beam((0.06, -0.075, Z + 0.15), (-0.03, -0.08, Z + 0.33), 0.013, F("#6b4226", 0.8))
        beam((-0.03, -0.08, Z + 0.33), (-0.075, -0.082, Z + 0.43), 0.008, F(DARK, 0.4))
        sl = F("#4a3322", 0.7)  # the sling, sagging between the butt and the fore-end
        beam((0.052, -0.084, Z + 0.158), (0.018, -0.092, Z + 0.196), 0.005, sl)
        beam((0.018, -0.092, Z + 0.196), (-0.022, -0.088, Z + 0.312), 0.005, sl)
    elif dl == 7:  # modern infantry: team multicam fatigues, coyote plate carrier with magazine pouches and an
        # assault pack with a radio, coyote helmet with goggles, NVG mount and ear defenders, team shoulder marks with
        # a white dot (seen from above at the game camera), tan boots and knee pads; carbine with optic at low ready
        fat = camo(shade(team, 0.6), shade(team, 0.36), mixc(shade(team, 0.72), "#8f8e7a", 0.4), 38.0)
        coy, coy_d = "#7a6b4c", "#56493a"
        _legs(Z, seated, fat, "#6e5c40", gaiter=fat)
        for sx in (-1, 1):  # knee pads
            if not seated:
                bx((0.028, 0.012, 0.03), (sx * 0.024, -0.016, 0.095), F("#2a2b2c"), bev=0)
        _torso(Z, fat, 0.044, 0.049)
        bx((0.1, 0.104, 0.1), (0, 0, Z + 0.25), F(coy, 0.85), bev=0.008)  # plate carrier
        for dx in (-0.028, 0.0, 0.028):  # magazine pouches
            bx((0.022, 0.016, 0.032), (dx, -0.059, Z + 0.226), F(coy_d, 0.85), bev=0)
        bx((0.04, 0.01, 0.022), (0.012, -0.056, Z + 0.278), F(coy_d, 0.85), bev=0)  # admin pouch
        for sx in (-1, 1):  # team marks on the shoulder straps, a white dot in each — read from above
            bx((0.026, 0.034, 0.008), (sx * 0.05, -0.004, Z + 0.302), F(team, 0.7), bev=0)
            badge(0.013, 0.013, (sx * 0.05, -0.006, Z + 0.3065), F(WHITE, 0.6), "z", CIRCLE)
        if not seated:  # assault pack with a radio and a stubby antenna (below the helmet top)
            bx((0.066, 0.032, 0.072), (0, 0.067, Z + 0.24), F(coy_d, 0.85), bev=0)
            bx((0.03, 0.02, 0.034), (-0.018, 0.091, Z + 0.25), F("#2a2c2e", 0.6), bev=0)
            _vertical(Z, -0.026, 0.094, 0.26, 0.4, F("#1c1d20", 0.5), 0.0028, 4)
        _head(Z, "#d9a07a")
        hel = F(coy, 0.7)
        uvs(0.041, (0, 0.003, Z + 0.37), hel, 8, 4, (1, 1.05, 0.78))
        ring(0.0415, 0.008, (0, 0.003, Z + 0.376), F("#1c1d20", 0.6), 8)  # goggle strap
        bx((0.05, 0.012, 0.015), (0, -0.0385, Z + 0.381), F("#1c1d20", 0.5), bev=0)  # goggles pushed up
        for sx in (-1, 1):
            bx((0.019, 0.004, 0.01), (sx * 0.012, -0.0448, Z + 0.381), F("#e0a43c", 0.2), bev=0)  # amber lenses
            uvs(0.0125, (sx * 0.036, 0.0, Z + 0.352), F("#2e3033", 0.6), 6, 3, (0.7, 1, 1))  # ear defenders
        bx((0.02, 0.014, 0.012), (0, -0.032, Z + 0.4), F("#1c1d20", 0.4), bev=0)  # NVG mount
        _arm(Z, 1, (0.05, -0.07, 0.2), fat)
        _arm(Z, -1, (-0.02, -0.08, 0.26), fat)
        gun = F("#232529", 0.5)
        beam((0.07, -0.07, Z + 0.21), (-0.04, -0.085, Z + 0.3), 0.016, gun)
        beam((-0.04, -0.085, Z + 0.3), (-0.07, -0.088, Z + 0.33), 0.007, gun)
        bx((0.012, 0.014, 0.035), (0.0, -0.08, Z + 0.235), gun, bev=0, rot=(0, -0.65, 0))
        bx((0.03, 0.012, 0.012), (0.02, -0.08, Z + 0.287), F("#141516"), bev=0, rot=(0, -0.7, 0))
    else:  # dl 8 power armour (reference frames 2 and 5): a navy shell tapering from broad shoulders, a team chest
        # plate framed in bronze with a glowing core, segmented abdomen plates with the dark undersuit showing in the
        # seams, a bronze belt, greaves and forearm guards; rounded team pauldrons over navy lames with the
        # white eagle; a round navy helmet set in a high collar, a gunmetal face plate and a glowing T-visor; heavy
        # energy rifle
        plate = F("#5b636e", 0.4)
        joint = F("#23272d", 0.6)
        navy = F(shade(team, 0.5), 0.45)
        tm = F(shade(team, 0.85), 0.45)
        bronze = F("#a8743e", 0.35)
        gl = team_glow(team)
        if seated:
            _legs(Z, True, "#23272d", "#5b636e", 0.022, 0.04)
        else:
            for sx in (-1, 1):  # bronze greaves down to the boots, under navy knee guards (reference frame 5)
                rod((sx * 0.026, 0, 0.18), (sx * 0.03, 0, 0.1), 0.023, joint, n=5)
                bx((0.04, 0.045, 0.075), (sx * 0.03, -0.005, 0.0675), bronze, bev=0)
                bx((0.034, 0.014, 0.028), (sx * 0.03, -0.031, 0.118), navy, bev=0)  # knee guard
                bx((0.042, 0.06, 0.03), (sx * 0.03, -0.01, 0.015), joint, bev=0)
        bx((0.1, 0.075, 0.07), (0, 0, Z + 0.17), joint, bev=0)
        bx((0.104, 0.079, 0.016), (0, 0, Z + 0.156), bronze, bev=0)  # belt
        for k, z in enumerate((0.18, 0.199)):  # abdomen plates, the undersuit dark in the seams between them
            bx((0.074 - 0.008 * k, 0.012, 0.015), (0, -0.039, Z + z), navy, bev=0)
        # the shell runs up to the shoulders and a sloped gorget carries the helmet: no neck gap under it
        taper_box((0.104, 0.084, 0.15), (0, 0, Z + 0.23), navy, top=(1.2, 1.1))  # shell
        cy(0.046, 0.04, (0, 0.004, Z + 0.322), navy, 8, r2=0.036)  # high collar the helmet sits in
        taper_box((0.072, 0.012, 0.074), (0, -0.0425, Z + 0.256), bronze, top=(1.3, 1.0))  # chest frame
        taper_box((0.06, 0.012, 0.064), (0, -0.0475, Z + 0.261), tm, top=(1.32, 1.0))  # chest plate
        bx((0.02, 0.012, 0.02), (0, -0.0545, Z + 0.282), gl, bev=0, rot=(0, math.pi / 4, 0))  # core
        bx((0.07, 0.03, 0.08), (0, 0.06, Z + 0.27), joint, bev=0)  # power pack
        for sx in (-1, 1):
            bx((0.018, 0.006, 0.018), (sx * 0.02, 0.077, Z + 0.25), gl, bev=0)
            # rounded team pauldron over a navy lame, oval and kept within the figure's own width so neighbours in
            # the squad stand apart: the team colour stays the brightest note from above
            pd = uvs(0.029, (sx * 0.066, 0, Z + 0.314), F(team, 0.5), 8, 4, (0.92, 1.1, 0.62))
            ring(0.027, 0.016, (sx * 0.067, 0, Z + 0.296), navy, 8, r2=0.025, a0=math.pi / 8)  # lame
            badge_on(pd, 0.025, 0.025, (sx * 0.066, -0.003, 0), F(WHITE, 0.6), "z", pts=EAGLE_S, off=0.0015)
        uvs(0.036, (0, 0.003, Z + 0.366), navy, 8, 4, (1, 1.08, 1.02))  # helmet, set down in the collar
        bx((0.052, 0.016, 0.034), (0, -0.031, Z + 0.356), plate, bev=0)  # face plate
        bx((0.046, 0.006, 0.01), (0, -0.0405, Z + 0.366), gl, bev=0)  # T-visor
        bx((0.01, 0.006, 0.018), (0, -0.0405, Z + 0.354), gl, bev=0)
        bx((0.01, 0.05, 0.016), (0, 0.004, Z + 0.4), bronze, bev=0)  # crest
        for sx in (-1, 1):  # arms in the undersuit, bronze forearm guards
            hand = (0.06, -0.07, Z + 0.21) if sx > 0 else (-0.03, -0.085, Z + 0.25)
            sh = (sx * (SH + 0.012), 0, Z + 0.3)
            rod(sh, hand, 0.019, joint, n=6)
            p0 = tuple(sh[i] + (hand[i] - sh[i]) * 0.5 for i in range(3))
            p1 = tuple(sh[i] + (hand[i] - sh[i]) * 0.92 for i in range(3))
            rod(p0, p1, 0.024, bronze, r2=0.022, n=5)
        g = F("#3a3f47", 0.5)
        beam((0.075, -0.08, Z + 0.2), (-0.06, -0.095, Z + 0.3), 0.03, g)
        beam((-0.06, -0.095, Z + 0.3), (-0.1, -0.1, Z + 0.33), 0.012, g)
        beam((0.05, -0.097, Z + 0.22), (-0.04, -0.11, Z + 0.287), 0.008, gl)


# ---------------------------------------------------------------------- formations

# eight figures in three loose staggered rows, a figure's width apart (reference frames 3–4: soldiers stand as
# separate readable men, not a packed block); the footprint of the old 4×3 block is kept (x ≈ −0.26…0.32)
LOOSE = [(-0.22, -0.15), (-0.02, -0.15), (0.18, -0.15), (-0.12, 0.0), (0.08, 0.0), (0.28, 0.0), (-0.2, 0.15), (0.0, 0.15)]


def squad(dl, team):
    """8 figures in a loose group of squad_<team> size (x ≈ −0.26…0.32, y ≈ −0.17…0.17); DL4's standard-bearer walks
    in the back row."""
    rnd = random.Random(dl * 7)
    for k, (x, y) in enumerate(LOOSE):
        jit = {1: 0.04, 7: 0.03, 8: 0.01}.get(dl, 0.02)  # DL8: broad armour, kept a pauldron's width apart
        yaw = {1: 0.5, 6: 0.25, 7: 0.35}.get(dl, 0.15)
        dx, dy = rnd.uniform(-jit, jit), rnd.uniform(-jit, jit)
        rz = rnd.uniform(-yaw, yaw)
        s = 0.95 * (rnd.uniform(0.92, 1.04) if dl == 1 else 1.0) * (1.06 if dl == 8 else 1.0)
        v = 9 if (dl == 4 and k == 7) else k
        build_at(lambda d=dl, vv=v: figure(d, team, vv), x + dx, y + dy, rz, s)


def sentry(dl, team):
    """Two sentries of the era standing a pace apart, turned a little toward each other (reference frames 3–4:
    single soldiers guard the farms, the quarry and the gates)."""
    pair = ((-0.09, 0.0, 0.3), (0.095, 0.03, -0.22)) if dl == 8 else ((-0.06, 0.0, 0.35), (0.07, 0.03, -0.25))
    for k, (x, y, rz) in enumerate(pair):  # DL8: the broad power armour stands a little further apart
        build_at(lambda d=dl, vv=k + 3: figure(d, team, vv), x, y, rz, 0.95 * (1.06 if dl == 8 else 1.0))


# ====================================================================== ASSAULT UNITS


def horse(coat, mane, sock=None, saddle=None, covered=False, reins=False, breast=None):
    """Horse facing −Y: back at z≈0.335, body y −0.17…0.17, head to y≈−0.33, height ≈0.5. A rounded barrel with
    chest and rump, an arched neck, a wedge head with a darker muzzle, eyes and a bridle, tapered legs with
    hooves, a mane crest and a full tail — so it reads as a horse at map zoom, not a box. Lean enough (≈720 tris)
    to leave the budget for the cloth: `covered` skips the barrel, chest and rump a caparison hides anyway;
    `breast` = colour of a breast collar lying on the chest, with a brass boss at the front."""
    c, mn = F(coat, 0.75), F(mane, 0.85)
    dark = F(mixc(coat, "#1a1410", 0.45), 0.8)
    leather = F("#3a2516", 0.7)
    if not covered:  # barrel, chest and rump
        bx((0.11, 0.26, 0.12), (0, 0, 0.27), c, bev=0.05)
        chest = uvs(0.075, (0, -0.12, 0.285), c, 8, 6, (0.85, 1.0, 1.0))
        uvs(0.078, (0, 0.12, 0.29), c, 8, 6, (0.9, 1.0, 0.95))
        if breast:  # breast collar round the point of the shoulder, dipping at the front, back under the cloth
            surface_band([chest], (0, -0.12, 0.29), 0.32, [math.radians(a) for a in range(-105, 106, 21)], 0.016,
                         F(breast, 0.7))
            uvs(0.011, (0, -0.193, 0.265), F(GOLD, 0.4), 6, 3, (1, 0.45, 1))
    # arched neck and head
    beam((0, -0.13, 0.31), (0, -0.2, 0.44), 0.082, c, 0.025)
    uvs(0.045, (0, -0.205, 0.45), c, 8, 5)
    beam((0, -0.2, 0.455), (0, -0.305, 0.39), 0.058, c, 0.022)
    beam((0, -0.29, 0.4), (0, -0.335, 0.37), 0.048, dark, 0.016)  # muzzle
    for sx in (-1, 1):
        bx((0.012, 0.016, 0.012), (sx * 0.029, -0.235, 0.452), F("#141010", 0.3), bev=0)  # eyes
        cn(0.012, 0.042, (sx * 0.018, -0.19, 0.495), c, 4)  # ears
        rod((sx * 0.031, -0.2, 0.448), (sx * 0.027, -0.318, 0.385), 0.0045, leather, n=4)  # cheek strap
    rod((-0.032, -0.322, 0.382), (0.032, -0.322, 0.382), 0.005, leather, n=4)  # noseband
    if saddle or reins:
        for sx in (-1, 1):  # reins back to the rider
            rod((sx * 0.03, -0.32, 0.38), (sx * 0.04, -0.05, 0.4), 0.0035, leather, n=4)
    # mane: a crest of tufts along the neck
    for k in range(5):
        t = k / 4.0
        cn(0.02, 0.05, (0, -0.11 - 0.08 * t, 0.37 + 0.11 * t), mn, 4, rot=(math.radians(-35), 0, 0))
    cn(0.018, 0.045, (0, -0.215, 0.49), mn, 4, rot=(math.radians(-70), 0, 0))  # forelock
    # legs: forearm/gaskin tapering to the knee, cannon to the hoof
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 0.036, sy * 0.115
            rod((x, y, 0.25), (x, y - 0.006, 0.122), 0.022 if sy > 0 else 0.02, c, r2=0.0135, n=5)
            rod((x, y - 0.006, 0.128), (x, y - 0.012, 0.03), 0.012, c, n=5)
            cy(0.018, 0.024, (x, y - 0.012, 0.012), F(sock or mane), 6)
    # tail: three strands fanned
    for k, ox in enumerate((-0.012, 0.0, 0.012)):
        rod((ox * 0.5, 0.17, 0.32), (ox * 2.2, 0.24 + 0.01 * (k == 1), 0.12), 0.024 if k == 1 else 0.017, mn, r2=0.008, n=5)
    if saddle and not covered:
        bx((0.125, 0.12, 0.02), (0, 0.005, 0.338), F(saddle, 0.7), bev=0)


def saddle_cloth(team, trim, y0=0.005, length=0.16, drop=0.125, rear=0.0):
    """Team saddle cloth hanging down both flanks to the belly (reference frame 3: the blue cloth under the rider),
    with a contrasting trim along the hem and the white eagle on each side; `rear` > 0 pulls the back corner into
    a point (the dragoon's shabraque)."""
    tc = F(team, 0.7)
    tr = F(trim, 0.45)
    bx((0.128, length, 0.014), (0, y0, 0.344), tc, bev=0)
    y_a, y_b = y0 - length / 2, y0 + length / 2
    zt, zb = 0.348, 0.348 - drop
    prof = [(y_a, zt), (y_b, zt), (y_b + rear, zb + 0.02 if rear else zb), (y_a, zb)]
    prof_t = [(y_a - 0.006, zt), (y_b + 0.006, zt), (y_b + rear + 0.008, zb - 0.008 if rear else zb - 0.014),
              (y_a - 0.006, zb - 0.014)]
    for sx in (-1, 1):
        side_prism(prof_t, 0.006, tr, sx * 0.0675)  # trim: a border showing round the cloth
        side_prism(prof, 0.007, tc, sx * 0.0715)
        badge(0.064, 0.064, (sx * 0.0785, y0 + 0.006, zt - drop * 0.46), F(WHITE, 0.6), face="x", side=sx)
    return tc


def assault_dl2(team):
    """Mounted spearman: bay horse with breast strap, team saddle cloth with a pale trim and the white eagle,
    rider in gambeson with the eagle shield; a team pennant below the spear head."""
    horse("#7a5235", "#2a1d14", "#e8e0d0", reins=True, breast="#3a2516")
    saddle_cloth(team, "#e9e2cf")
    figure(2, team, 0, seated=True)
    hx, hy, Z = 0.068, -0.045, SEAT
    pennant((hx, hy + 0.008, Z + 0.69), (hx, hy + 0.008, Z + 0.635), 0.085, F(team, 0.7), F(WHITE, 0.6))


def assault_dl3(team):
    """Knight: iron-grey destrier in a dagged team caparison to the knees with the white eagle on both flanks and the
    chest, steel chanfron and team plume; the rider in a surcoat with steel pauldrons, great helm and crest,
    heater shield, lance with a swallow-tailed pennant."""
    # toned like the DL3 men-at-arms beside him (reference frame 3: the rider reads as dark steel and deep team blue
    # like the infantry): an iron-grey destrier, the deeper surcoat and caparison, dark mail, blued steel
    horse("#77736c", "#46423e", "#2e2a28", reins=True, covered=True)
    tc = F(shade(team, 0.64), 0.7)
    helm = F(mixc(DL3_STEEL, team if team == TEAMS["blue"] else "#4a5872", 0.18), 0.35)  # the squad's helmets
    n = 20
    hem = lambda k: 0.155 if k % 2 == 0 else 0.192  # noqa: E731  dagged hem
    arch = lambda z, a: (lambda k: z + a * abs(math.sin(math.tau * k / n)))  # noqa: E731  withers and croup up
    # the flank ring at 0.215 keeps the panel above the dags flat, so the emblems lie on it
    cap = loft([ell(0.035, 0.15, 0.0, n, zf=arch(0.352, 0.016)), ell(0.062, 0.2, 0.0, n, zf=arch(0.34, 0.012)),
                ell(0.075, 0.222, 0.29, n), ell(0.0801, 0.2284, 0.215, n), ell(0.083, 0.232, 0.0, n, zf=hem)],
               tc, cap0=True)
    # gold border along the foot of that panel, above the dags, 3 mm proud of the cloth all the way round
    loft([ell(0.0831, 0.2314, 0.215, n), ell(0.0823, 0.2304, 0.227, n)], F(GOLD, 0.45))
    wh = F(WHITE, 0.6)
    for sx in (-1, 1):  # the eagle on each flank, on the panel between the border and the back (clear of the boot)
        badge_on(cap, 0.054, 0.056, (0, 0.03, 0.259), wh, "x", sx)
    badge_on(cap, 0.046, 0.054, (0, 0, 0.259), wh, "y", -1)  # and on the chest
    beam((0, -0.19, 0.452), (0, -0.305, 0.392), 0.068, helm)  # chanfron
    cn(0.014, 0.06, (0, -0.205, 0.5), tc, 5, rot=(-0.4, 0, 0))  # plume on the chanfron
    Z = SEAT
    _legs(Z, True, DL3_MAIL, "#4a4f57", gaiter=DL3_MAIL)
    _torso(Z, DL3_MAIL, 0.046, 0.054)
    _surcoat(Z, team, hem=0.13, k=0.64)
    _pauldrons(Z, F(DL3_STEEL, 0.35), 0.032)
    cy(0.037, 0.07, (0, 0, Z + 0.36), helm, 8)  # great helm
    bx((0.05, 0.008, 0.008), (0, -0.037, Z + 0.365), F("#1d1b1a"), bev=0)
    cn(0.03, 0.06, (0, 0.0, Z + 0.425), tc, 6)  # crest
    uvs(0.012, (0, 0, Z + 0.458), F(WHITE, 0.6), 6, 4)
    _arm(Z, 1, (0.07, -0.06, 0.22), DL3_MAIL)
    _arm(Z, -1, (-0.06, -0.04, 0.24), DL3_MAIL)
    _heater_shield(Z, team, -0.08, -0.05, 0.225, rim="#6b7480", field=shade(team, 0.82))
    lance = F("#d9d2c3", 0.6)
    rod((0.072, 0.06, Z + 0.06), (0.072, -0.08, Z + 0.62), 0.008, lance, n=5)
    cn(0.014, 0.06, (0.072, -0.085, Z + 0.66), F(STEEL, 0.3), 5).rotation_euler.x = 0.24
    cy(0.016, 0.03, (0.072, 0.04, Z + 0.14), F(STEEL, 0.35), 6, rot=(0.24, 0, 0))  # vamplate
    pennant((0.072, -0.0705, Z + 0.582), (0.072, -0.053, Z + 0.51), 0.11, F(team, 0.7), F(WHITE, 0.6))


def assault_dl4(team):
    """Dragoon: dark horse with a pointed team shabraque in gold lace and a rolled cloak behind the saddle, rider in
    coat with brass crested helmet and raised sabre."""
    horse("#4a3326", "#1d1612", "#d9d2c3", reins=True)
    saddle_cloth(team, "#e0b040", y0=0.02, length=0.17, drop=0.12, rear=0.05)
    cy(0.022, 0.13, (0, 0.105, 0.37), F("#3b4a63", 0.85), 6, rot=(0, math.pi / 2, 0))  # rolled cloak
    for sx in (-1, 1):
        bx((0.012, 0.012, 0.04), (sx * 0.05, 0.105, 0.37), F(LEATHER, 0.7), bev=0)  # straps
    Z = SEAT
    _legs(Z, True, "#ece6d6", "#1f1c1c", gaiter="#262222")
    _torso(Z, team, 0.045, 0.051)
    w = F(WHITE, 0.6)
    for s in (-1, 1):
        b = bx((0.012, 0.012, 0.15), (0, -0.046, Z + 0.24), w, bev=0)
        b.rotation_euler.y = s * 0.55
    _belt(Z, WHITE, 0.175, 0.049)
    for sx in (-1, 1):  # gold epaulettes
        uvs(0.024, (sx * 0.055, 0, Z + 0.302), F(GOLD, 0.4), 6, 3, (1.1, 1.15, 0.6))
    _head(Z)
    brass = F("#d6a640", 0.4)
    uvs(0.037, (0, 0.002, Z + 0.375), brass, 8, 4, (1, 1.05, 0.9))
    cy(0.042, 0.008, (0, 0.002, Z + 0.36), brass, 10)
    beam((0, -0.03, Z + 0.4), (0, 0.06, Z + 0.37), 0.022, F("#1a1414", 0.9))  # horsehair crest
    rod((0, 0.04, Z + 0.38), (0, 0.07, Z + 0.28), 0.012, F("#1a1414", 0.9), r2=0.004, n=4)
    _arm(Z, 1, (0.075, -0.05, 0.4), team)
    _arm(Z, -1, (-0.06, -0.06, 0.2), team)
    beam((0.078, -0.055, Z + 0.41), (0.1, -0.1, Z + 0.58), 0.01, F(STEEL, 0.3))  # sabre
    bx((0.03, 0.012, 0.012), (0.078, -0.055, Z + 0.405), F(GOLD, 0.4), bev=0)
    rod((-0.07 - SPREAD, 0.04, Z + 0.07), (-0.08 - SPREAD * 0.5, -0.02, Z + 0.36), 0.008, F("#6b4226", 0.8), n=5)  # carbine
    cy(0.02, 0.07, (0.08 + SPREAD * 0.6, 0.11, Z + 0.1), F("#d6a640", 0.4), 6, rot=(0.3, 0, 0))  # holster


def assault_dl5(team):
    """Armoured car (c. 1914): bonnet with armoured radiator louvres in front, riveted steel-blue body with the team
    band, round MG turret with the air-recognition roundel, wooden-spoked wheels, a pick and a shovel strapped to the
    flank, petrol tins on the rear fender, spare wheel on the tail."""
    body = F(mixc(shade(team, 0.75), "#4f5844", 0.5), 0.7)
    dk = F("#2b2d2f")
    rv = F("#6d737a", 0.4)
    wood = F("#a07448", 0.75)
    bx((0.17, 0.42, 0.035), (0, 0, 0.085), dk, bev=0)
    bx((0.21, 0.24, 0.13), (0, 0.07, 0.17), body, bev=0.012)
    o = taper_box((0.17, 0.17, 0.095), (0, -0.13, 0.145), body, (0.82, 0.86), bev=0.01)
    o.location.z = 0.1475
    bx((0.12, 0.012, 0.07), (0, -0.218, 0.14), F("#4a4c4e", 0.5), bev=0)
    for z in (0.117, 0.131, 0.145, 0.159):  # armoured radiator louvres
        bx((0.108, 0.006, 0.007), (0, -0.2255, z), dk, bev=0)
    for sx in (-1, 1):
        cy(0.015, 0.02, (sx * 0.06, -0.22, 0.2), glow("lamp", "#ffe2a0", 3.0), 6, rot=(math.pi / 2, 0, 0))
        bx((0.006, 0.006, 0.006), (sx * 0.052, -0.2255, 0.172), rv, bev=0)  # louvre frame rivets
        for sy in (-0.15, 0.15):
            bx((0.04, 0.12, 0.012), (sx * 0.1, sy, 0.125), dk, bev=0)  # mudguards
        for sy in (-0.14, 0.15):  # wheels: black tyre, six wooden spokes, iron hub
            disc(0.058, (sx * 0.1, sy, 0.058), F(RUBBER, 0.9), "x", 10, 0.038)
            for k in range(3):
                b = bx((0.005, 0.082, 0.007), (sx * 0.1215, sy, 0.058), wood, bev=0)
                b.rotation_euler.x = k * math.pi / 3
            disc(0.014, (sx * 0.124, sy, 0.058), F("#8a8c86", 0.5), "x", 6, 0.006)
        bx((0.006, 0.08, 0.04), (sx * 0.107, 0.06, 0.18), F("#22252a"), bev=0)  # vision slit plate
        for k in range(4):  # rivets along the foot of the side plate
            bx((0.007, 0.008, 0.008), (sx * 0.1065, -0.03 + k * 0.064, 0.12), rv, bev=0)
    bx((0.214, 0.244, 0.025), (0, 0.07, 0.205), F(team, 0.7), bev=0)  # team band
    # a pick and a shovel strapped to the left flank, petrol tins on the right rear fender
    rod((-0.11, -0.04, 0.142), (-0.11, 0.12, 0.142), 0.0045, wood, n=4)
    bx((0.006, 0.008, 0.05), (-0.111, -0.034, 0.142), F(IRON, 0.45), bev=0)
    rod((-0.11, 0.0, 0.126), (-0.11, 0.13, 0.126), 0.0045, wood, n=4)
    bx((0.006, 0.03, 0.024), (-0.111, 0.142, 0.126), F(IRON, 0.45), bev=0)
    for k in range(2):
        bx((0.026, 0.034, 0.042), (0.1, 0.112 + k * 0.04, 0.152), F(mixc(OLIVE, "#3a3d33", 0.3), 0.7), bev=0)
    cy(0.072, 0.075, (0, 0.06, 0.27), body, 10, r2=0.064)
    cy(0.066, 0.012, (0, 0.06, 0.312), dk, 10)
    badge(0.074, 0.074, (0, 0.06, 0.3195), F(WHITE, 0.6), "z", CIRCLE)  # air-recognition roundel on the turret roof
    badge(0.04, 0.04, (0, 0.06, 0.322), F(team, 0.7), "z", CIRCLE)
    disc(0.042, (-0.035, 0.201, 0.165), F(RUBBER, 0.9), "y", 10, 0.022)  # spare wheel on the tail
    disc(0.022, (-0.035, 0.2135, 0.165), F("#8a8c86", 0.6), "y", 8, 0.004)
    for sx in (-1, 1):
        disc(0.026, (sx * 0.069, 0.06, 0.27), F(WHITE, 0.6), "x", 10, 0.006)
        disc(0.015, (sx * 0.072, 0.06, 0.27), F(team, 0.7), "x", 8, 0.006)
    rod((0, 0.0, 0.27), (0, -0.09, 0.27), 0.016, F("#41443f", 0.5), n=6)  # water jacket
    rod((0, -0.09, 0.27), (0, -0.14, 0.27), 0.006, dk, n=5)
    rod((0.07, 0.17, 0.2), (0.07, 0.19, 0.48), 0.004, dk, n=4)
    bx((0.07, 0.006, 0.045), (0.105, 0.19, 0.455), F(team, 0.7), bev=0)


def crewman(x, y, z, helmet, coat, s=0.62):
    """Commander standing in an open hatch at height z, chest up, forearms on the rim — a sign of life on the
    vehicle (scaled infantry proportions)."""
    cy(0.04 * s, 0.075 * s, (x, y, z + 0.03 * s), F(coat, 0.8), 6, r2=0.047 * s)
    uvs(0.033 * s, (x, y - 0.002, z + 0.1 * s), F(SKIN, 0.7), 6, 4)
    uvs(0.039 * s, (x, y + 0.003, z + 0.115 * s), F(helmet, 0.6), 6, 3, (1, 1.05, 0.62))
    for sx in (-1, 1):
        rod((sx * 0.045 * s + x, y, z + 0.06 * s), (sx * 0.05 * s + x, y - 0.045 * s, z + 0.004), 0.013 * s, F(coat, 0.8), n=5)


def tracks(L, x, w=0.07, h=0.09, wheels=5, r=0.03, mt_track=None, mt_wheel=None, skirt=None):
    tr = mt_track or F("#3a3631", 0.85)
    for sx in (-1, 1):
        bx((w, L, h), (sx * x, 0, h / 2 + 0.005), tr, bev=0.025)
        if skirt:  # four skirt panels with dark seams between them
            n, gap = 4, 0.006
            pl = (L * 0.86 - gap * (n - 1)) / n
            for k in range(n):
                y = -0.01 - L * 0.43 + pl / 2 + k * (pl + gap)
                bx((0.012, pl, h * 0.62), (sx * (x + w / 2 + 0.004), y, h * 0.72), skirt, bev=0)
            continue
        for i in range(wheels):
            y = -L / 2 + 0.06 + i * (L - 0.12) / (wheels - 1)
            disc(r, (sx * (x + w / 2 + 0.002), y, r + 0.012), mt_wheel or F("#5a5c55", 0.7), "x", 8, 0.012)


def running_gear(L, x, w, sprocket_y, idler_y, z_hub=0.05, r_sp=0.036, r_id=0.03, inset=0.003, hub=True):
    """Drive sprocket and idler at the track ends (outer faces at x ± w/2 + inset): the running gear that makes a
    tank read as tracked at the game camera."""
    wheel = F("#55574f", 0.65)
    for sx in (-1, 1):
        xo = sx * (x + w / 2 + inset)
        disc(r_sp, (xo, sprocket_y, z_hub), wheel, "x", 10, 0.014)
        if hub:
            disc(r_sp * 0.45, (xo + sx * 0.007, sprocket_y, z_hub), F("#8d9399", 0.45), "x", 6, 0.004)
        disc(r_id, (xo, idler_y, z_hub - 0.004), wheel, "x", 8, 0.012)


def assault_dl6(team):
    """WW2 medium tank: sloped glacis with driver's hatches, periscopes, a bow MG and spare track links, cast round
    turret with the team band and white stars, link-textured tracks with sprocket, idler and return rollers, a
    shovel and an axe on the flank, petrol cans and a rolled tarp on the deck, headlamps with brush guards."""
    body = camo(mixc(team, "#5d6b3c", 0.55), mixc(team, "#2f3622", 0.6), mixc(team, "#7d7b56", 0.55), 7.0)
    lk = links("#57534b", "#1c1a18", 15.0)
    dk = F("#2b2d2f")
    wood = F("#8a6038", 0.8)
    tracks(0.46, 0.105, 0.07, 0.09, 5, 0.032, mt_track=lk)
    running_gear(0.46, 0.105, 0.07, -0.205, 0.205, 0.052)
    side_prism([(-0.235, 0.075), (-0.24, 0.1), (-0.13, 0.18), (0.2, 0.18), (0.235, 0.14), (0.235, 0.075)], 0.28, body)
    gla = math.atan2(0.08, 0.11)  # glacis slope
    gn = (0, -math.sin(gla), math.cos(gla))

    def on_glacis(y, up=0.0):
        return (y, 0.1 + (y + 0.24) * 0.08 / 0.11 + gn[2] * up, gn[1] * up)
    for sx in (-1, 1):  # driver's and co-driver's hatches with periscopes
        yy, zz, dy = on_glacis(-0.152, 0.004)
        bx((0.046, 0.044, 0.01), (sx * 0.055, yy + dy, zz), F(mixc(team, "#2f3622", 0.6), 0.7), bev=0, rot=(gla, 0, 0))
        yy, zz, dy = on_glacis(-0.142, 0.014)
        bx((0.014, 0.01, 0.012), (sx * 0.055, yy + dy, zz), dk, bev=0, rot=(gla, 0, 0))
    yy, zz, dy = on_glacis(-0.214, 0.004)  # spare track links across the lower glacis
    bx((0.2, 0.034, 0.008), (0, yy + dy, zz), lk, bev=0, rot=(gla, 0, 0))
    yy, zz, dy = on_glacis(-0.19, 0.0)  # bow MG in its ball mount
    uvs(0.014, (0.06, yy, zz), body, 6, 4)
    rod((0.06, yy - 0.01, zz), (0.06, yy - 0.05, zz - 0.004), 0.004, dk, n=4)
    for sx in (-1, 1):  # headlamps with brush guards on the front corners
        cy(0.011, 0.014, (sx * 0.1, -0.243, 0.112), F("#d8d2b8", 0.3), 6, rot=(math.pi / 2, 0, 0))
        bx((0.028, 0.004, 0.004), (sx * 0.1, -0.256, 0.124), dk, bev=0)
        bx((0.004, 0.016, 0.026), (sx * 0.1135, -0.248, 0.112), dk, bev=0)
    # a shovel (front) and an axe (rear) strapped to each flank, clear of the white stars
    for sx in (-1, 1):
        xs = sx * 0.1435
        rod((xs, -0.19, 0.15), (xs, -0.05, 0.15), 0.0045, wood, n=4)
        bx((0.006, 0.03, 0.026), (xs, -0.2, 0.15), F("#3f4433", 0.6), bev=0)
        rod((xs, 0.09, 0.145), (xs, 0.21, 0.145), 0.0045, wood, n=4)
        bx((0.006, 0.012, 0.03), (xs, 0.2, 0.152), F(IRON, 0.45), bev=0)
    for k in range(2):  # petrol cans beside the turret
        bx((0.026, 0.034, 0.042), (0.114, 0.104 + k * 0.04, 0.201), F(mixc(OLIVE, "#3a3d33", 0.3), 0.7), bev=0)
    cy(0.012, 0.03, (-0.11, 0.21, 0.195), dk, 6)  # exhaust
    cy(0.1, 0.085, (0, 0.03, 0.222), body, 12, r2=0.084)
    cy(0.035, 0.03, (0.04, 0.06, 0.278), body, 8)  # cupola
    crewman(0.04, 0.06, 0.293, OLIVE, shade(team, 0.78))
    badge(0.05, 0.05, (-0.02, -0.015, 0.2665), F(WHITE, 0.6), "z", STAR)  # white star on the turret roof
    cy(0.016, 0.16, (-0.02, 0.17, 0.196), F(KHAKI, 0.85), 6, rot=(0, math.pi / 2, 0))  # rolled tarp on the deck
    for sx in (-1, 1):
        bx((0.006, 0.012, 0.036), (-0.02 + sx * 0.05, 0.17, 0.196), F(LEATHER, 0.7), bev=0)  # straps
    bx((0.09, 0.03, 0.06), (0, -0.075, 0.22), body, bev=0.008)  # mantlet
    rod((0, -0.09, 0.22), (0, -0.34, 0.22), 0.012, F("#3b3e36", 0.6), n=8)
    cy(0.017, 0.035, (0, -0.33, 0.22), F("#2f322c"), 8, rot=(math.pi / 2, 0, 0))
    ring(0.098, 0.02, (0, 0.03, 0.205), F(team, 0.7), 12, r2=0.0955)  # team band round the turret
    for sx in (-1, 1):
        a0 = math.pi if sx > 0 else 0.0
        o = extrude([((0.032 if k % 2 == 0 else 0.013) * math.cos(a0 + k * math.pi / 5),
                      (0.032 if k % 2 == 0 else 0.013) * math.sin(a0 + k * math.pi / 5)) for k in range(10)],
                    0, 0.004, F(WHITE, 0.6))
        o.rotation_euler = (0, math.pi / 2 * sx, 0)
        o.location = (sx * 0.142, 0.04, 0.135)
    rod((-0.06, 0.08, 0.26), (-0.06, 0.08, 0.6), 0.003, F(DARK), n=4)
    bx((0.075, 0.005, 0.045), (-0.0225, 0.08, 0.575), F(team, 0.7), bev=0)


def assault_dl7(team):
    """Main battle tank: long flat hull, angular wedge turret with spaced add-on armour on the cheeks, long
    smoothbore with thermal sleeve, segmented side skirts over link-textured tracks with sprocket and idler, driver's
    hatch with periscopes, stowage bins and an engine grille on the deck, headlamps, a team panel on the bustle bags
    beside the white chevron."""
    body = camo(mixc(team, "#6b6f5a", 0.5), mixc(team, "#2c3026", 0.6), mixc(team, "#a09a7a", 0.5), 6.0)
    sk = body
    lk = links("#57534b", "#1c1a18", 15.0)
    dk = F("#24262a")
    tracks(0.48, 0.11, 0.065, 0.08, 6, 0.03, mt_track=lk, skirt=sk)
    running_gear(0.48, 0.11, 0.065, 0.214, -0.228, 0.044, 0.032, 0.027, inset=-0.0015, hub=False)
    side_prism([(-0.25, 0.07), (-0.25, 0.095), (-0.17, 0.15), (0.24, 0.155), (0.255, 0.12), (0.255, 0.07)], 0.29, body)
    tpts = [(-0.055, -0.16), (0.055, -0.16), (0.12, -0.06), (0.118, 0.12), (0.075, 0.17), (-0.075, 0.17), (-0.118, 0.12), (-0.12, -0.06)]
    tur = camo(mixc(team, "#55594a", 0.5), mixc(team, "#262a20", 0.6), mixc(team, "#8c8668", 0.5), 6.0)
    cy(0.1, 0.02, (0, 0.03, 0.16), dk, 10)  # turret ring
    taper_extrude(tpts, 0, 0.085, tur, 0.84, (0, 0.03, 0.165))
    era = F(mixc(team, "#3a3d36", 0.75), 0.7)
    for sx in (-1, 1):  # spaced add-on armour standing off the turret cheeks
        rz = math.atan2(0.1, 0.065 * sx)
        nx, ny = 0.838 * sx, -0.545
        bx((0.108, 0.012, 0.06), (sx * 0.0875 + nx * 0.011, -0.08 + ny * 0.011, 0.2), era, bev=0, rz=rz)
    badge(0.06, 0.055, (0.035, 0.07, 0.2515), F(WHITE, 0.6), "z", CHEVRON)  # white recognition chevron
    cy(0.028, 0.01, (-0.05, 0.075, 0.253), dk, 8)  # commander's hatch ring
    crewman(-0.05, 0.075, 0.258, "#3c4046", shade(team, 0.72))
    for k, dx in enumerate((-0.062, 0.0, 0.062)):  # stowage bags in the bustle rack
        bx((0.056, 0.036, 0.042), (dx, 0.192, 0.212), F(("#7d7656", "#5f6447", "#8a8160")[k], 0.9), bev=0)
    bx((0.05, 0.03, 0.004), (0, 0.192, 0.235), F(team, 0.7), bev=0)  # team panel on the middle bag
    bx((0.19, 0.006, 0.006), (0, 0.212, 0.236), dk, bev=0)  # rack rail
    # driver's hatch with periscopes on the front deck, stowage bins along the deck edges, engine grille, headlamps
    cy(0.021, 0.006, (0, -0.152, 0.155), dk, 8)
    for dx in (-0.016, 0.016):
        bx((0.014, 0.01, 0.01), (dx, -0.176, 0.158), F("#30332c"), bev=0)
    for sx in (-1, 1):
        bx((0.024, 0.15, 0.022), (sx * 0.131, 0.06, 0.163), F("#4a4d42", 0.8), bev=0)
        cy(0.01, 0.012, (sx * 0.112, -0.252, 0.088), F("#d8d2b8", 0.3), 6, rot=(math.pi / 2, 0, 0))
    bx((0.14, 0.026, 0.006), (0, 0.222, 0.157), links("#3a3c38", "#151617", 40.0), bev=0)  # engine grille, on the deck
    rod((0, -0.12, 0.21), (0, -0.44, 0.21), 0.0115, F("#3c3f37", 0.6), n=8)
    cy(0.017, 0.07, (0, -0.21, 0.21), F("#3c3f37", 0.6), 8, rot=(math.pi / 2, 0, 0))  # sleeve
    cy(0.018, 0.04, (0, -0.33, 0.21), F("#30332c"), 8, rot=(math.pi / 2, 0, 0))  # fume extractor
    bx((0.04, 0.05, 0.04), (0.075, -0.02, 0.262), F("#30332c"), bev=0.006)  # commander's sight
    disc(0.012, (0.075, -0.046, 0.265), glow("optic", "#7cf0ff", 2.5), "y", 6, 0.004)
    rod((-0.07, 0.0, 0.27), (-0.07, -0.08, 0.27), 0.005, F(DARK), n=4)  # roof MG
    bx((0.02, 0.04, 0.025), (-0.07, 0.01, 0.26), F(DARK), bev=0)
    for sx in (-1, 1):
        for k in range(3):
            rod((sx * 0.11, -0.04 + k * 0.025, 0.215), (sx * 0.135, -0.06 + k * 0.025, 0.23), 0.008, F("#30332c"), n=5)
        bx((0.006, 0.12, 0.03), (sx * 0.121, 0.06, 0.205), F(team, 0.7), bev=0)  # team band
        bx((0.006, 0.18, 0.02), (sx * 0.152, 0.0, 0.11), F(team, 0.7), bev=0)
    rod((0.07, 0.15, 0.24), (0.07, 0.15, 0.58), 0.003, F(DARK), n=4)
    bx((0.07, 0.005, 0.04), (0.105, 0.15, 0.56), F(team, 0.7), bev=0)


def assault_dl8(team):
    """Heavy hover tank: a gunmetal wedge on team nacelles floating over glowing pads, twin rail cannon, light strips,
    a team nose plate, glowing intake grilles, team turret cheeks, missile pods, bronze trim (reference frames 2, 5)."""
    plate = F("#68707b", 0.4)
    dk = F("#2c3139", 0.55)
    gl = team_glow(team)
    H = 0.09  # hover gap
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.042, 0.03, (sx * 0.12, sy * 0.15, H - 0.005), dk, 8)
            cy(0.034, 0.012, (sx * 0.12, sy * 0.15, H - 0.026), gl, 8)
    side_prism([(-0.25, H + 0.035), (-0.19, H), (0.21, H), (0.25, H + 0.03), (0.24, H + 0.085), (-0.08, H + 0.11),
                (-0.2, H + 0.075)], 0.2, plate)
    for sx in (-1, 1):  # side nacelles
        side_prism([(-0.22, H + 0.005), (0.23, H), (0.245, H + 0.065), (-0.15, H + 0.07)], 0.06, F(team, 0.5), sx * 0.125)
        bx((0.006, 0.34, 0.014), (sx * 0.157, 0.0, H + 0.035), gl, bev=0)
        bx((0.04, 0.012, 0.03), (sx * 0.125, 0.244, H + 0.035), gl, bev=0)  # thrusters
    tpts = [(-0.045, -0.15), (0.045, -0.15), (0.1, -0.05), (0.1, 0.09), (0.055, 0.13), (-0.055, 0.13), (-0.1, 0.09), (-0.1, -0.05)]
    taper_extrude(tpts, 0, 0.065, dk, 0.72, (0, 0.03, H + 0.1))
    taper_extrude([(x * 0.6, y * 0.6) for x, y in tpts], 0, 0.012, plate, 0.85, (0, 0.04, H + 0.165))
    badge(0.074, 0.074, (0, 0.036, H + 0.1785), F(WHITE, 0.6), "z")  # the white eagle on the turret roof
    o = cy(0.17, 0.004, (0, 0, 0.004), glow("underglow" + team, team, 1.2), 12)
    o.scale = (0.9, 1.45, 1)
    bx((0.1, 0.01, 0.012), (0, -0.115, H + 0.135), gl, bev=0)  # sensor strip
    for sx in (-1, 1):
        bx((0.02, 0.28, 0.024), (sx * 0.028, -0.24, H + 0.13), plate, bev=0)
        bx((0.006, 0.26, 0.008), (sx * 0.028, -0.24, H + 0.145), gl, bev=0)
        for k in range(3):
            bx((0.03, 0.012, 0.032), (sx * 0.028, -0.2 - k * 0.06, H + 0.13), F(team, 0.5), bev=0)
    bx((0.034, 0.03, 0.05), (-0.06, 0.1, H + 0.19), dk, bev=0)  # sensor mast
    cy(0.012, 0.012, (-0.06, 0.1, H + 0.222), gl, 6)
    # armour detail after reference frames 2 and 5: a raised team plate on the nose with the gunmetal seams showing
    # round it, glowing intake grilles on the rear deck, team cheek plates with light strips on the turret, missile
    # pods with glowing tubes on the nacelles, bronze trim along the nacelles and bronze muzzles on the rails
    bronze = F("#a8743e", 0.35)
    ns = math.atan2(0.035, 0.12)
    bx((0.15, 0.105, 0.008), (0, -0.14 - 0.003 * math.sin(ns), 0.1825 + 0.003 * math.cos(ns)), F(shade(team, 0.7), 0.45),
       bev=0, rot=(ns, 0, 0))
    rs = -math.atan2(0.025, 0.32)
    for sx in (-1, 1):
        bx((0.044, 0.064, 0.006), (sx * 0.046, 0.185, 0.1813), dk, bev=0, rot=(rs, 0, 0))  # intake grille
        for y in (0.168, 0.2):
            bx((0.032, 0.007, 0.004), (sx * 0.046, y, 0.1813 + 0.004 - (y - 0.185) * 0.078), gl, bev=0, rot=(rs, 0, 0))
        th = -0.407 * sx  # turret side lean
        nx, nz = 0.918 * sx, 0.395
        bx((0.006, 0.1, 0.05), (sx * 0.086 + nx * 0.0035, 0.047, 0.2225 + nz * 0.0035), F(team, 0.5), bev=0,
           rot=(0, th, 0))  # cheek plate
        bx((0.004, 0.08, 0.008), (sx * 0.086 + nx * 0.0075, 0.047, 0.214 + nz * 0.0075), gl, bev=0, rot=(0, th, 0))
        bx((0.044, 0.07, 0.03), (sx * 0.125, 0.16, 0.172), dk, bev=0)  # missile pod
        for dx in (-0.01, 0.01):
            bx((0.012, 0.004, 0.012), (sx * 0.125 + dx, 0.1235, 0.174), gl, bev=0)
        bx((0.004, 0.36, 0.008), (sx * 0.1565, 0.045, 0.15), bronze, bev=0)  # nacelle trim
        bx((0.026, 0.02, 0.03), (sx * 0.028, -0.373, H + 0.13), bronze, bev=0)  # rail muzzle


def _seg(p0, p1, w, t, mt, out=0.0, bev=0.0):
    """Box from p0 to p1 (its length), w wide across X and t thick along the normal that faces the front (−Y),
    pushed `out` along that normal: armour plates laid on the front of a leg or arm segment."""
    from mathutils import Vector
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    xa = Vector((1, 0, 0))
    xa = (xa - d * xa.dot(d)).normalized()
    n = d.cross(xa)
    if n.y > 0:
        n = -n
    if xa.cross(n).dot(d) < 0:
        xa = -xa
    o = bx((w, t, (b - a).length), tuple((a + b) / 2 + n * out), mt, bev=bev)
    o.rotation_euler = Matrix((xa, n, d)).transposed().to_euler()
    return o


def _vprism(profile, hw0, hw1, z0, z1, mt):
    """side_prism whose half-width grows from hw0 at z0 to hw1 at z1: a chest broadening to the shoulders."""
    n = len(profile)

    def hw(z):
        return hw0 + (hw1 - hw0) * (z - z0) / (z1 - z0)
    verts = [(-hw(z), y, z) for y, z in profile] + [(hw(z), y, z) for y, z in profile]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    return mesh_obj(verts, faces, mt)


def mech(team):
    """DL8 heavy walker (reference frames 2 and 5: the hunched gunmetal mechs among the late-era infantry) facing
    −Y: a broad chest under huge rounded team pauldrons with the white eagle, a low armoured head with a glowing
    visor slit, a rotary-cannon right arm and an armoured fist on the left, twin shoulder missile pods with glowing
    tube ends, armoured legs with knee guards, glowing joints and hydraulic pistons, broad three-toed feet with a
    heel spur; a navy chest plate framed in bronze with a glowing core and bronze trim like the DL8 power armour."""
    plate = F("#636b77", 0.4)    # gunmetal armour
    dk = F("#262a31", 0.55)      # frame and joints
    steel = F("#b9c0c9", 0.3)    # piston rods
    navy = F(shade(team, 0.5), 0.45)
    tm = F(team, 0.5)
    bronze = F("#a8743e", 0.35)
    gl = team_glow(team)
    visor = glow("visor" + team, team, 4.5)
    # ---- legs: hip → knee forward → ankle back, a broad three-toed foot
    for sx in (-1, 1):
        hip = (sx * 0.066, 0.01, 0.262)
        knee = (sx * 0.076, -0.05, 0.155)
        ankle = (sx * 0.082, 0.022, 0.056)
        cy(0.03, 0.05, hip, dk, 8, rot=(0, math.pi / 2, 0))  # hip joint
        disc(0.016, (sx * 0.092, 0.01, 0.262), gl, "x", 6, 0.004)
        beam(hip, knee, 0.04, dk)  # thigh frame
        _seg((sx * 0.066, 0.004, 0.272), (sx * 0.076, -0.05, 0.165), 0.056, 0.018, plate, 0.018, 0.004)  # thigh plate
        _seg((sx * 0.066, -0.002, 0.255), (sx * 0.075, -0.042, 0.19), 0.03, 0.006, tm, 0.03)  # team stripe
        cy(0.024, 0.056, knee, dk, 8, rot=(0, math.pi / 2, 0))  # knee joint
        disc(0.013, (sx * 0.105, -0.05, 0.155), gl, "x", 6, 0.004)
        beam(knee, ankle, 0.034, dk)  # shin frame
        _seg((sx * 0.077, -0.046, 0.15), (sx * 0.082, 0.016, 0.068), 0.05, 0.016, plate, 0.016, 0.004)  # greave
        _seg((sx * 0.077, -0.042, 0.14), (sx * 0.081, 0.004, 0.08), 0.054, 0.006, bronze, 0.026)  # bronze shin trim
        # knee guard: a heavy cap over the joint with two bronze rivets
        _seg((sx * 0.076, -0.058, 0.2), (sx * 0.077, -0.082, 0.14), 0.05, 0.016, plate, 0.0, 0.004)
        for dx in (-0.014, 0.014):
            _seg((sx * 0.076 + dx, -0.062, 0.19), (sx * 0.076 + dx, -0.072, 0.165), 0.008, 0.006, bronze, 0.0095)
        # hydraulic piston on the outer flank: dark cylinder from the hip, steel rod into the calf
        top, mid, bot = (sx * 0.104, 0.024, 0.245), (sx * 0.108, 0.026, 0.165), (sx * 0.11, 0.02, 0.09)
        rod(top, mid, 0.0095, dk, n=6)
        rod(mid, bot, 0.0065, steel, n=5)
        bx((0.022, 0.02, 0.02), (sx * 0.097, 0.022, 0.248), dk, bev=0)  # mounts on the hip and the calf
        bx((0.026, 0.02, 0.018), (sx * 0.098, 0.016, 0.09), dk, bev=0)
        cy(0.02, 0.05, ankle, dk, 8, rot=(0, math.pi / 2, 0))  # ankle joint
        x = sx * 0.084
        bx((0.054, 0.05, 0.034), (x, 0.004, 0.035), plate, bev=0.006)  # ankle block
        bx((0.074, 0.07, 0.016), (x, -0.008, 0.008), dk, bev=0)  # sole
        for dx in (-0.025, 0.0, 0.025):  # toes splayed forward, bronze toe caps
            tx = x + dx * 1.15
            _seg((x + dx * 0.6, -0.03, 0.016), (tx, -0.078, 0.01), 0.02, 0.018, plate, 0.0)
            bx((0.022, 0.012, 0.014), (tx, -0.084, 0.008), bronze, bev=0)
        _seg((x, 0.03, 0.016), (x, 0.066, 0.008), 0.022, 0.014, dk, 0.0)  # heel spur
    # ---- hips: a dark block, a navy fauld framed in bronze
    bx((0.15, 0.085, 0.056), (0, 0.01, 0.272), dk, bev=0.008)
    taper_box((0.08, 0.014, 0.05), (0, -0.04, 0.244), bronze, top=(1.15, 1.0))
    taper_box((0.066, 0.014, 0.044), (0, -0.045, 0.247), navy, top=(1.18, 1.0))
    # ---- torso: a hunched chest broadening to the shoulders
    prof = [(-0.055, 0.29), (0.065, 0.29), (0.088, 0.35), (0.065, 0.425), (-0.035, 0.438), (-0.084, 0.398),
            (-0.09, 0.335)]
    _vprism(prof, 0.068, 0.092, 0.29, 0.438, plate)
    tilt = -math.atan2(0.006, 0.063)  # the chest front leans back a little
    yf = -0.0905
    bx((0.11, 0.008, 0.066), (0, yf - 0.002, 0.366), bronze, bev=0, rot=(tilt, 0, 0))  # chest frame
    bx((0.094, 0.008, 0.052), (0, yf - 0.0045, 0.367), navy, bev=0, rot=(tilt, 0, 0))  # chest plate
    bx((0.024, 0.008, 0.024), (0, yf - 0.0075, 0.368), gl, bev=0, rot=(tilt, math.pi / 4, 0))  # core
    for dx in (-0.048, 0.048):  # rivets at the frame corners
        for z in (0.338, 0.394):
            bx((0.007, 0.006, 0.007), (dx, yf - 0.006 - (z - 0.366) * 0.095, z), steel, bev=0)
    # upper chest: a dark vent either side of the head with two glowing slats, laid on the upper front slope
    y0, z0, y1, z1 = -0.084, 0.398, -0.035, 0.438
    ln = math.hypot(y1 - y0, z1 - z0)
    dy, dz = (y1 - y0) / ln, (z1 - z0) / ln
    th = -math.atan2(dy, dz)  # local Z along the slope

    def on_slope(x, s_, out):
        return (x, y0 + dy * s_ - dz * out, z0 + dz * s_ + dy * out)
    for sx in (-1, 1):
        bx((0.028, 0.004, 0.026), on_slope(sx * 0.06, 0.032, 0.002), dk, bev=0, rot=(th, 0, 0))
        for s_ in (0.025, 0.039):
            bx((0.022, 0.003, 0.005), on_slope(sx * 0.06, s_, 0.0045), gl, bev=0, rot=(th, 0, 0))
    for sx in (-1, 1):  # side armour under the pauldrons: team plates with bronze edge strips
        bx((0.01, 0.11, 0.07), (sx * 0.088, 0.008, 0.352), tm, bev=0.003)
        bx((0.012, 0.115, 0.008), (sx * 0.089, 0.008, 0.315), bronze, bev=0)
    # ---- head: low between the shoulders, a gunmetal helm with a glowing visor slit and a bronze crest
    bx((0.07, 0.062, 0.05), (0, -0.052, 0.44), plate, bev=0.007)
    bx((0.064, 0.006, 0.016), (0, -0.0835, 0.447), visor, bev=0)
    bx((0.046, 0.008, 0.016), (0, -0.0825, 0.425), dk, bev=0)  # jaw grille
    bx((0.012, 0.05, 0.012), (0, -0.05, 0.469), bronze, bev=0)  # crest
    # ---- shoulders: huge rounded team pauldrons with the white eagle over a bronze rim and a navy lame
    for sx in (-1, 1):
        cy(0.026, 0.05, (sx * 0.105, 0.005, 0.395), dk, 8, rot=(0, math.pi / 2, 0))  # shoulder joint
        pd = uvs(0.052, (sx * 0.122, 0.004, 0.428), tm, 10, 5, (0.9, 1.12, 0.68))
        ring(0.047, 0.012, (sx * 0.122, 0.004, 0.41), bronze, 10, r2=0.046)
        ring(0.042, 0.018, (sx * 0.124, 0.004, 0.392), navy, 8, r2=0.044, a0=math.pi / 8)
        badge_on(pd, 0.05, 0.05, (sx * 0.122, -0.004, 0), F(WHITE, 0.6), "z", pts=EAGLE_S, off=0.0015)
    # ---- arms: upper arm down to the elbow, forearm forward
    for sx in (-1, 1):
        sh, el = (sx * 0.128, 0.004, 0.39), (sx * 0.136, 0.006, 0.305)
        beam(sh, el, 0.034, dk)
        _seg((sx * 0.128, 0.0, 0.385), (sx * 0.136, 0.0, 0.322), 0.04, 0.012, plate, 0.018)  # upper-arm plate
        cy(0.022, 0.048, el, dk, 8, rot=(0, math.pi / 2, 0))  # elbow
        disc(0.012, (el[0] + sx * 0.025, el[1], el[2]), gl, "x", 6, 0.004)
    x = 0.138  # right: a rotary cannon in a gunmetal housing with a team ammo box and a bronze clamp
    cy(0.03, 0.085, (x, -0.04, 0.292), plate, 8, rot=(math.pi / 2, 0, 0))
    cy(0.032, 0.008, (x, -0.07, 0.292), gl, 8, rot=(math.pi / 2, 0, 0))  # glowing coil
    bx((0.036, 0.05, 0.02), (x, -0.036, 0.326), tm, bev=0)  # ammo box
    bx((0.038, 0.006, 0.022), (x, -0.012, 0.326), bronze, bev=0)
    for k in range(3):
        a = math.pi / 2 + k * math.tau / 3
        bx_, bz = x + 0.012 * math.cos(a), 0.292 + 0.012 * math.sin(a)
        rod((bx_, -0.08, bz), (bx_, -0.172, bz), 0.0065, dk, n=5)
    cy(0.023, 0.012, (x, -0.128, 0.292), bronze, 8, rot=(math.pi / 2, 0, 0))  # barrel clamp
    cy(0.022, 0.01, (x, -0.168, 0.292), dk, 8, rot=(math.pi / 2, 0, 0))  # muzzle plate
    x = -0.138  # left: an armoured forearm with a team guard and a heavy three-fingered fist
    bx((0.05, 0.085, 0.048), (x, -0.045, 0.292), plate, bev=0.006)
    bx((0.04, 0.07, 0.008), (x, -0.045, 0.319), tm, bev=0)  # forearm guard
    bx((0.042, 0.008, 0.01), (x, -0.083, 0.319), bronze, bev=0)
    bx((0.048, 0.036, 0.044), (x, -0.104, 0.288), dk, bev=0.005)  # fist
    for dx in (-0.015, 0.0, 0.015):
        bx((0.013, 0.016, 0.03), (x + dx, -0.126, 0.279), plate, bev=0)  # knuckles
    bx((0.012, 0.03, 0.014), (x + 0.03, -0.1, 0.28), plate, bev=0)  # thumb
    # ---- twin shoulder missile pods behind the head, tipped up so the glowing tube ends face the camera
    a = -0.3
    ca, sa = math.cos(a), math.sin(a)
    for sx in (-1, 1):
        px, py, pz = sx * 0.064, 0.04, 0.452

        def P(u, v, w):
            return (px + u, py + v * ca - w * sa, pz + v * sa + w * ca)
        bx((0.054, 0.07, 0.044), P(0, 0, 0), dk, bev=0.005, rot=(a, 0, 0))
        bx((0.05, 0.004, 0.04), P(0, -0.0365, 0), navy, bev=0, rot=(a, 0, 0))  # tube face
        bx((0.058, 0.012, 0.048), P(0, -0.024, 0), bronze, bev=0, rot=(a, 0, 0))  # bronze band
        for i in (-1, 1):
            for j in (-1, 1):
                cy(0.0085, 0.006, P(i * 0.013, -0.038, j * 0.0105), gl, 6, rot=(math.pi / 2 + a, 0, 0))
        bx((0.044, 0.04, 0.006), P(0, 0.008, 0.024), plate, bev=0, rot=(a, 0, 0))  # lid
    rod((0.08, 0.06, 0.46), (0.08, 0.06, 0.51), 0.0035, dk, n=4)  # antenna, rooted in the right pod
    cy(0.007, 0.008, (0.08, 0.06, 0.514), gl, 6)
    # ---- back: a power pack with glowing vents and two exhaust stacks
    bx((0.11, 0.03, 0.08), (0, 0.092, 0.365), dk, bev=0.006)
    for sx in (-1, 1):
        cy(0.011, 0.04, (sx * 0.042, 0.095, 0.42), dk, 6)
    for k in range(3):  # vent slats
        bx((0.074, 0.004, 0.007), (0, 0.1085, 0.343 + k * 0.018), gl, bev=0)


ASSAULT = {2: assault_dl2, 3: assault_dl3, 4: assault_dl4, 5: assault_dl5, 6: assault_dl6, 7: assault_dl7, 8: assault_dl8}

ASSETS = {}
for _n in range(1, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"squad_dl{_n}_{_t}"] = (lambda n, c: (lambda: squad(n, c)))(_n, _c)
        ASSETS[f"sentry_dl{_n}_{_t}"] = (lambda n, c: (lambda: sentry(n, c)))(_n, _c)
for _n in range(2, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"assault_dl{_n}_{_t}"] = (lambda n, c: (lambda: ASSAULT[n](c)))(_n, _c)
for _t, _c in TEAMS.items():
    ASSETS[f"mech_{_t}"] = (lambda c: (lambda: mech(c)))(_c)


def export(name, out):
    """evolution_assets.export (lowpoly, 512 px bake, glTF) with the mesh origin moved to the model origin."""
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    ev.lowpoly(objs)
    ob = ea.bake_asset(objs, 512)
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
    print(f"EXPORTED {name}: tris={tris} x={min(v.x for v in vs):.2f}..{max(v.x for v in vs):.2f} "
          f"y={min(v.y for v in vs):.2f}..{max(v.y for v in vs):.2f} height={max(v.z for v in vs):.2f} "
          f"mats={[m_.name for m_ in ob.data.materials]}", flush=True)
    return tris


# ====================================================================== contact sheet


def troops_sheet(model_dir, png, team="blue", ref=False, res=2400, cols=4, only=None):
    """One grass hex per DL: squad + assault + banner exactly as map_view.gd::_make_army places them."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    tiles = []
    if ref:
        tiles.append([("squad_" + team, (-0.15, 0.05), 1.15), ("knight_" + team, (0.32, 0.25), 1.25)])
    for n in (only or range(1, 9)):
        t = [(f"squad_dl{n}_{team}", (-0.15, 0.05), 1.15)]
        if n >= 2:
            t.append((f"assault_dl{n}_{team}", (0.32, 0.25), 1.25))
        tiles.append(t)
    sp = 1.75
    nrows = (len(tiles) + cols - 1) // cols
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        x = (c - (cols - 1) / 2) * sp
        y = -r * sp * 1.12
        kit.hex_prism("tile", (x, y, 0), 0.85, 0.18, grass, dirt, 0.03)
        for name, (gx, gz), s in t + [("banner_" + team, (0.05, -0.35), 0.9)]:
            before = {o.name for o in bpy.context.scene.objects}
            bpy.ops.import_scene.gltf(filepath=os.path.join(model_dir, name + ".glb"))
            for o in bpy.context.scene.objects:
                if o.name not in before and o.parent is None:
                    # Godot (x, z) → Blender (x, −y); scale about the model origin like the Node3D parent does
                    o.matrix_world = Matrix.Translation((x + gx, y - gz, 0)) @ Matrix.Scale(s, 4) @ o.matrix_world
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
    cam.data.ortho_scale = cols * sp + 0.1
    el = math.radians(46)  # the game camera pitch is 40–52°
    se, ce = math.sin(el), math.cos(el)
    v_top = 0.4 * se + 1.0 * ce  # banner tops of the back row
    v_bot = (-(nrows - 1) * sp * 1.12 - 0.76) * se - 0.2 * ce  # front edge of the front row's tiles
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
    span = v_top - v_bot + 0.1
    sc.render.resolution_y = int(res * span / cam.data.ortho_scale)
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
        team = rest[rest.index("--team") + 1] if "--team" in rest else "blue"
        cols = int(rest[rest.index("--cols") + 1]) if "--cols" in rest else 4
        dls = [int(c) for c in rest[rest.index("--dl") + 1].split(",")] if "--dl" in rest else None
        troops_sheet(out, png, team, "--ref" in rest, 2400, cols, dls)
        sys.exit(0)
    os.makedirs(out, exist_ok=True)
    only = set(rest)
    report = {}
    for name, build in ASSETS.items():
        if only and not any(fnmatch.fnmatch(name, p) for p in only):
            continue
        ea.reset()
        build()
        report[name] = export(name, out)
    print("TRIS", report)
