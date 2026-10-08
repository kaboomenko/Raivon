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


def mixc(a, b, t):
    """Blend two sRGB hex colours (t = 0 → a, 1 → b)."""
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(pa, pb))


def F(c, rough=0.75):
    return flat("t" + c, c, rough)


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


# the white displayed eagle of the reference banners and shields (frames 3–5): wings raised, head up, forked tail —
# a 12-point outline in a unit box (u right, v up), cheap enough for every soldier's chest and shield
EAGLE = [(0.0, 0.5), (0.1, 0.3), (0.5, 0.46), (0.33, 0.02), (0.12, 0.04), (0.2, -0.5), (0.0, -0.32), (-0.2, -0.5),
         (-0.12, 0.04), (-0.33, 0.02), (-0.5, 0.46), (-0.1, 0.3)]


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
    front, axis 'x' + side ±1 = seen from that flank."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    me = target.data
    tree = BVHTree.FromPolygons([target.matrix_world @ v.co for v in me.vertices], [p.vertices for p in me.polygons])
    x, y, z = loc
    d = Vector((0, -side, 0)) if axis == "y" else Vector((-side, 0, 0))  # ray direction: into the surface

    def place(u, v):
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
    t, b = F(trouser, 0.85), F(boot, 0.8)
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
                bx((0.03, 0.032, 0.06), (sx * 0.025, -0.001, 0.055), F(gaiter, 0.8), bev=0)
            bx((0.032, 0.05, boot_h), (sx * 0.025, -0.008, boot_h / 2), b, bev=0)


def _torso(Z, c, r0=0.043, r1=0.05, skirt=None, skirt_len=0.07):
    cy(r0, 0.15, (0, 0, Z + 0.235), F(c), 8, r2=r1)
    if skirt:
        ring(0.058, skirt_len, (0, 0, Z + 0.165 - skirt_len / 2 + 0.02), F(skirt), 8, r2=0.046)


def _arm(Z, sx, hand, c, r=0.014):
    rod((sx * SH, 0, Z + 0.295), (hand[0], hand[1], Z + hand[2]), r, F(c), r2=r * 0.85, n=5)


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


def _heater_shield(Z, team, x=-0.066, y=-0.052, z=0.215):
    """Heater shield of the reference knights (frame 3): steel border, team field, white eagle."""
    plate_xz(HEATER, (x, y + 0.004, Z + z), 0.008, F(STEEL, 0.35), 1.16)
    plate_xz(HEATER, (x, y - 0.002, Z + z), 0.008, F(team, 0.7))
    badge(0.05, 0.056, (x, y - 0.0085, Z + z - 0.004), F(WHITE, 0.6))


def _surcoat(Z, team, hem=0.085, top=0.302, waist=0.18, r=0.058, flare=0.066):
    """Team surcoat over the mail, flat-fronted (an octagon turned a half step) so the white eagle lies on it,
    flaring into a skirt to the knees."""
    a0 = math.pi / 8
    loft([ell(r, r, Z + top, 8, a0=a0), ell(r, r, Z + waist, 8, a0=a0), ell(flare, flare, Z + hem, 8, a0=a0)],
         F(shade(team, 0.86), 0.7))  # a deeper blue than the banners, as on the reference soldiers
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
        _legs(Z, seated, "#3a3330", "#4a3322")
        _torso(Z, "#a2a8b0", 0.045, 0.052)
        _surcoat(Z, team, hem=0.085 if not seated else 0.14)
        if not seated:
            _cape(Z, shade(team, 0.72))
        _pauldrons(Z, F(STEEL, 0.35))
        _head(Z)
        cn(0.038, 0.06, (0, 0.002, Z + 0.39), F(STEEL, 0.35), 8)
        ring(0.039, 0.012, (0, 0.002, Z + 0.364), F(STEEL, 0.35), 8)
        bx((0.008, 0.01, 0.03), (0, -0.035, Z + 0.355), F(STEEL, 0.35), bev=0)
        _arm(Z, 1, (0.08, -0.05, 0.37), "#a2a8b0")
        _arm(Z, -1, (-0.062, -0.04, 0.22), "#a2a8b0")
        beam((0.082, -0.055, Z + 0.39), (0.092, -0.06, Z + 0.56), 0.011, F(STEEL, 0.3))
        bx((0.045, 0.012, 0.01), (0.081, -0.055, Z + 0.385), F(GOLD, 0.4), bev=0)
        _heater_shield(Z, team)
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
    elif dl == 5:  # riflemen: tunic, peaked cap, puttees, leather webbing, pack; shouldered rifle
        tun = shade(team, 0.82)
        _legs(Z, seated, shade(team, 0.5), "#3d2b1e", gaiter=KHAKI)
        _torso(Z, tun, 0.044, 0.05, skirt=tun, skirt_len=0.05)
        _belt(Z, LEATHER, 0.18, 0.048)
        for s in (-1, 1):
            b = bx((0.01, 0.012, 0.13), (s * 0.022, -0.046, Z + 0.25), F(LEATHER), bev=0)
            b.rotation_euler.y = s * 0.12
        if not seated:
            bx((0.075, 0.035, 0.08), (0, 0.06, Z + 0.25), F("#6d6450", 0.85), bev=0)
            cy(0.016, 0.085, (0, 0.06, Z + 0.3), F("#8b7f63"), 6, rot=(0, math.pi / 2, 0))
        _head(Z)
        cap = F(shade(team, 0.7), 0.7)
        cy(0.034, 0.03, (0, 0.004, Z + 0.385), cap, 8, r2=0.041)
        ring(0.035, 0.01, (0, 0.004, Z + 0.374), F("#1d1b1a"), 8)
        bx((0.05, 0.03, 0.006), (0, -0.034, Z + 0.374), F("#1d1b1a", 0.4), bev=0, rot=(0.25, 0, 0))
        bx((0.012, 0.004, 0.012), (0, -0.04, Z + 0.39), F(GOLD, 0.4), bev=0)
        _arm(Z, 1, (0.066, -0.035, 0.2), tun)
        _arm(Z, -1, (-0.06, -0.02, 0.17), tun)
        rod((0.068, -0.036, Z + 0.1), (0.074, -0.012, Z + 0.37), 0.008, F("#5a3a22", 0.8), n=4)
        rod((0.074, -0.012, Z + 0.37), (0.076, -0.004, Z + 0.47), 0.0045, F(DARK, 0.4), n=4)
        rod((0.076, -0.004, Z + 0.47), (0.078, 0.002, Z + 0.55), 0.004, F(STEEL, 0.3), r2=0.0005, n=4)
    elif dl == 6:  # WW2 infantry: steel helmet, webbing, pack; rifle at port arms (diagonal)
        jac = shade(team, 0.78)
        _legs(Z, seated, "#55584a", "#2a2522", gaiter="#8f8566")
        _torso(Z, jac, 0.045, 0.05, skirt=jac, skirt_len=0.05)
        web = F(KHAKI, 0.8)
        _belt(Z, KHAKI, 0.18, 0.049)
        for s in (-1, 1):
            bx((0.009, 0.1, 0.012), (s * 0.03, 0, Z + 0.3), web, bev=0)
            bx((0.02, 0.012, 0.022), (s * 0.03, -0.048, Z + 0.185), web, bev=0)
        if not seated:
            bx((0.07, 0.035, 0.075), (0, 0.06, Z + 0.25), F("#5b6040"), bev=0)
            cy(0.015, 0.08, (0, 0.06, Z + 0.3), F("#6f6a4e"), 6, rot=(0, math.pi / 2, 0))
        _head(Z)
        hel = F(OLIVE, 0.6)
        uvs(0.041, (0, 0.002, Z + 0.37), hel, 8, 4, (1, 1.05, 0.62))
        cy(0.047, 0.006, (0, 0.002, Z + 0.37), hel, 8)
        if v % 6 == 4:  # radio operator
            bx((0.065, 0.04, 0.09), (0, 0.065, Z + 0.26), F("#4a4e38"), bev=0)
            _vertical(Z, 0.02, 0.07, 0.3, 0.62, F(DARK), 0.003, 4)
        _arm(Z, 1, (0.045, -0.07, 0.2), jac)
        _arm(Z, -1, (-0.035, -0.075, 0.3), jac)
        beam((0.06, -0.075, Z + 0.15), (-0.03, -0.08, Z + 0.33), 0.013, F("#6b4226", 0.8))
        beam((-0.03, -0.08, Z + 0.33), (-0.075, -0.082, Z + 0.43), 0.008, F(DARK, 0.4))
    elif dl == 7:  # modern motorised infantry: fatigues, plate carrier, helmet + NVG, carbine at low ready
        fat = shade(team, 0.72)
        _legs(Z, seated, shade(team, 0.55), "#2b2622", gaiter=shade(team, 0.55))
        for sx in (-1, 1):  # knee pads
            if not seated:
                bx((0.028, 0.012, 0.03), (sx * 0.024, -0.016, 0.095), F("#24272b"), bev=0)
        _torso(Z, fat, 0.044, 0.049)
        vest = F("#34383d", 0.8)
        bx((0.1, 0.104, 0.1), (0, 0, Z + 0.25), vest, bev=0)
        for dx in (-0.028, 0.0, 0.028):
            bx((0.022, 0.016, 0.03), (dx, -0.056, Z + 0.225), F("#2a2d31"), bev=0)
        bx((0.02, 0.012, 0.02), (0.05, -0.012, Z + 0.285), F(team, 0.7), bev=0)  # shoulder patch
        bx((0.02, 0.012, 0.02), (-0.05, -0.012, Z + 0.285), F(team, 0.7), bev=0)
        if not seated:
            bx((0.065, 0.03, 0.07), (0, 0.065, Z + 0.24), F("#3b3f36"), bev=0)
        _head(Z, "#d9a07a")
        hel = F("#3c4046", 0.6)
        uvs(0.04, (0, 0.003, Z + 0.37), hel, 8, 4, (1, 1.05, 0.78))
        bx((0.03, 0.02, 0.018), (0, -0.036, Z + 0.395), F("#1c1d20", 0.4), bev=0)  # NVG mount
        bx((0.05, 0.012, 0.012), (0, -0.032, Z + 0.355), F("#1c1d20", 0.3), bev=0)  # glasses
        _arm(Z, 1, (0.05, -0.07, 0.2), fat)
        _arm(Z, -1, (-0.02, -0.08, 0.26), fat)
        gun = F("#232529", 0.5)
        beam((0.07, -0.07, Z + 0.21), (-0.04, -0.085, Z + 0.3), 0.016, gun)
        beam((-0.04, -0.085, Z + 0.3), (-0.07, -0.088, Z + 0.33), 0.007, gun)
        bx((0.012, 0.014, 0.035), (0.0, -0.08, Z + 0.235), gun, bev=0, rot=(0, -0.65, 0))
        bx((0.03, 0.012, 0.012), (0.02, -0.08, Z + 0.287), F("#141516"), bev=0, rot=(0, -0.7, 0))
    else:  # dl 8 power armour (reference frame 5): deep team-blue shell with bronze chest, shoulder and knee plates
        # over a dark undersuit, a blue helmet with a glowing visor, heavy energy rifle
        plate = F("#5b636e", 0.4)
        joint = F("#23272d", 0.6)
        tm = F(shade(team, 0.72), 0.5)
        hel = F(shade(team, 0.62), 0.45)
        bronze = F("#a8743e", 0.35)
        if seated:
            _legs(Z, True, "#23272d", "#5b636e", 0.022, 0.04)
        else:
            for sx in (-1, 1):
                rod((sx * 0.026, 0, 0.18), (sx * 0.03, 0, 0.1), 0.023, joint, n=6)
                bx((0.04, 0.045, 0.06), (sx * 0.03, -0.005, 0.075), hel, bev=0)
                bx((0.034, 0.014, 0.028), (sx * 0.03, -0.031, 0.118), bronze, bev=0)  # knee guard
                bx((0.042, 0.06, 0.03), (sx * 0.03, -0.01, 0.015), joint, bev=0)
        bx((0.1, 0.075, 0.07), (0, 0, Z + 0.17), joint, bev=0)
        bx((0.044, 0.01, 0.024), (0, -0.04, Z + 0.18), bronze, bev=0)  # belt plate
        bx((0.12, 0.09, 0.13), (0, 0, Z + 0.265), tm, bev=0.018)
        bx((0.074, 0.012, 0.074), (0, -0.046, Z + 0.272), bronze, bev=0)  # chest plate
        bx((0.022, 0.014, 0.022), (0, -0.052, Z + 0.28), team_glow(team), bev=0, rot=(0, math.pi / 4, 0))  # core
        bx((0.07, 0.03, 0.08), (0, 0.06, Z + 0.27), joint, bev=0)  # power pack
        for sx in (-1, 1):
            cy(0.012, 0.012, (sx * 0.02, 0.078, Z + 0.25), team_glow(team), 6, rot=(math.pi / 2, 0, 0))
            # team shoulder plates over a bronze under-plate: the team colour stays the brightest note from above
            bx((0.05, 0.06, 0.04), (sx * 0.075, 0, Z + 0.33), F(team, 0.5), bev=0, rot=(0, sx * 0.3, 0))
            bx((0.054, 0.064, 0.018), (sx * 0.079, 0, Z + 0.304), bronze, bev=0, rot=(0, sx * 0.3, 0))
        bx((0.066, 0.07, 0.065), (0, 0, Z + 0.375), hel, bev=0.016)
        bx((0.06, 0.016, 0.022), (0, -0.035, Z + 0.382), team_glow(team), bev=0)
        bx((0.012, 0.04, 0.02), (0, 0.006, Z + 0.415), bronze, bev=0)  # crest
        rod((SH + 0.02, 0, Z + 0.3), (0.06, -0.07, Z + 0.21), 0.02, joint, n=6)
        rod((-SH - 0.02, 0, Z + 0.3), (-0.03, -0.085, Z + 0.25), 0.02, joint, n=6)
        g = F("#3a3f47", 0.5)
        beam((0.075, -0.08, Z + 0.2), (-0.06, -0.095, Z + 0.3), 0.03, g)
        beam((-0.06, -0.095, Z + 0.3), (-0.1, -0.1, Z + 0.33), 0.012, g)
        beam((0.05, -0.097, Z + 0.22), (-0.04, -0.11, Z + 0.287), 0.008, team_glow(team))


# ---------------------------------------------------------------------- formations

# eight figures in three loose staggered rows, a figure's width apart (reference frames 3–4: soldiers stand as
# separate readable men, not a packed block); the footprint of the old 4×3 block is kept (x ≈ −0.26…0.32)
LOOSE = [(-0.22, -0.15), (-0.02, -0.15), (0.18, -0.15), (-0.12, 0.0), (0.08, 0.0), (0.28, 0.0), (-0.2, 0.15), (0.0, 0.15)]


def squad(dl, team):
    """8 figures in a loose group of squad_<team> size (x ≈ −0.26…0.32, y ≈ −0.17…0.17); DL4's standard-bearer walks
    in the back row."""
    rnd = random.Random(dl * 7)
    for k, (x, y) in enumerate(LOOSE):
        jit = {1: 0.04, 7: 0.03}.get(dl, 0.02)
        yaw = {1: 0.5, 6: 0.25, 7: 0.35}.get(dl, 0.15)
        dx, dy = rnd.uniform(-jit, jit), rnd.uniform(-jit, jit)
        rz = rnd.uniform(-yaw, yaw)
        s = 0.95 * (rnd.uniform(0.92, 1.04) if dl == 1 else 1.0) * (1.06 if dl == 8 else 1.0)
        v = 9 if (dl == 4 and k == 7) else k
        build_at(lambda d=dl, vv=v: figure(d, team, vv), x + dx, y + dy, rz, s)


def sentry(dl, team):
    """Two sentries of the era standing a pace apart, turned a little toward each other (reference frames 3–4:
    single soldiers guard the farms, the quarry and the gates)."""
    for k, (x, y, rz) in enumerate(((-0.06, 0.0, 0.35), (0.07, 0.03, -0.25))):
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
    """Knight: grey destrier in a dagged team caparison to the knees with the white eagle on both flanks and the
    chest, steel chanfron and team plume; the rider in a surcoat with steel pauldrons, great helm and crest,
    heater shield, lance with a swallow-tailed pennant."""
    horse("#d4d0c8", "#6d6a66", "#3a3634", reins=True, covered=True)
    tc = F(shade(team, 0.86), 0.7)
    n = 24
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
    badge_on(cap, 0.04, 0.052, (0, 0, 0.259), wh, "y", -1)  # and on the chest
    beam((0, -0.19, 0.452), (0, -0.305, 0.392), 0.068, F(STEEL, 0.35))  # chanfron
    cn(0.014, 0.06, (0, -0.205, 0.5), tc, 5, rot=(-0.4, 0, 0))  # plume on the chanfron
    Z = SEAT
    _legs(Z, True, "#a2a8b0", "#8d939a", gaiter="#a2a8b0")
    _torso(Z, "#b3b9c1", 0.046, 0.054)
    _surcoat(Z, team, hem=0.13)
    _pauldrons(Z, F(STEEL, 0.35), 0.032)
    cy(0.037, 0.07, (0, 0, Z + 0.36), F(STEEL, 0.35), 8)  # great helm
    bx((0.05, 0.008, 0.008), (0, -0.037, Z + 0.365), F("#1d1b1a"), bev=0)
    cn(0.03, 0.06, (0, 0.0, Z + 0.425), tc, 6)  # crest
    uvs(0.012, (0, 0, Z + 0.458), F(WHITE, 0.6), 6, 4)
    _arm(Z, 1, (0.07, -0.06, 0.22), "#b3b9c1")
    _arm(Z, -1, (-0.06, -0.04, 0.24), "#b3b9c1")
    _heater_shield(Z, team, -0.08, -0.05, 0.225)
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
    """Armoured car (c. 1914): bonnet in front, riveted body, round MG turret, spoked wheels."""
    body = F(mixc(team, "#5f6650", 0.5), 0.7)
    dk = F("#2b2d2f")
    bx((0.17, 0.42, 0.035), (0, 0, 0.085), dk, bev=0)
    bx((0.21, 0.24, 0.13), (0, 0.07, 0.17), body, bev=0.012)
    o = taper_box((0.17, 0.17, 0.095), (0, -0.13, 0.145), body, (0.82, 0.86), bev=0.01)
    o.location.z = 0.1475
    bx((0.12, 0.012, 0.07), (0, -0.218, 0.14), F("#4a4c4e", 0.5), bev=0)
    for sx in (-1, 1):
        cy(0.015, 0.02, (sx * 0.06, -0.22, 0.2), glow("lamp", "#ffe2a0", 3.0), 6, rot=(math.pi / 2, 0, 0))
        bx((0.04, 0.12, 0.012), (sx * 0.1, -0.15, 0.125), dk, bev=0)  # mudguard
        for sy in (-0.14, 0.15):
            disc(0.058, (sx * 0.1, sy, 0.058), F(RUBBER, 0.9), "x", 10, 0.038)
            disc(0.034, (sx * 0.122, sy, 0.058), F("#8a8c86", 0.6), "x", 8, 0.006)
        bx((0.006, 0.08, 0.04), (sx * 0.107, 0.06, 0.18), F("#22252a"), bev=0)  # vision slit plate
    bx((0.214, 0.244, 0.025), (0, 0.07, 0.205), F(team, 0.7), bev=0)  # team band
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
        if skirt:
            bx((0.012, L * 0.86, h * 0.62), (sx * (x + w / 2 + 0.004), -0.01, h * 0.72), skirt, bev=0)
            continue
        for i in range(wheels):
            y = -L / 2 + 0.06 + i * (L - 0.12) / (wheels - 1)
            disc(r, (sx * (x + w / 2 + 0.002), y, r + 0.012), mt_wheel or F("#5a5c55", 0.7), "x", 8, 0.012)


def assault_dl6(team):
    """WW2 medium tank: sloped glacis, cast round turret, short-ish gun, team stars and pennant."""
    body = camo(mixc(team, "#5d6b3c", 0.55), mixc(team, "#2f3622", 0.6), mixc(team, "#7d7b56", 0.55), 7.0)
    tracks(0.46, 0.105, 0.07, 0.09, 5, 0.032)
    side_prism([(-0.235, 0.075), (-0.24, 0.1), (-0.13, 0.18), (0.2, 0.18), (0.235, 0.14), (0.235, 0.075)], 0.28, body)
    for sx in (-1, 1):
        bx((0.012, 0.12, 0.012), (sx * 0.04, -0.17, 0.155), F("#3a3631"), bev=0, rot=(-0.6, 0, 0))  # spare tracks
    cy(0.012, 0.03, (0.08, 0.17, 0.2), F("#2b2d2f"), 6)  # exhaust
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
    """Main battle tank: long flat hull, angular wedge turret, long smoothbore with thermal sleeve, skirts."""
    body = camo(mixc(team, "#6b6f5a", 0.5), mixc(team, "#2c3026", 0.6), mixc(team, "#a09a7a", 0.5), 6.0)
    sk = body
    tracks(0.48, 0.11, 0.065, 0.08, 6, 0.03, skirt=sk)
    side_prism([(-0.25, 0.07), (-0.25, 0.095), (-0.17, 0.15), (0.24, 0.155), (0.255, 0.12), (0.255, 0.07)], 0.29, body)
    tpts = [(-0.055, -0.16), (0.055, -0.16), (0.12, -0.06), (0.118, 0.12), (0.075, 0.17), (-0.075, 0.17), (-0.118, 0.12), (-0.12, -0.06)]
    tur = camo(mixc(team, "#55594a", 0.5), mixc(team, "#262a20", 0.6), mixc(team, "#8c8668", 0.5), 6.0)
    cy(0.1, 0.02, (0, 0.03, 0.16), F("#24262a"), 10)  # turret ring
    taper_extrude(tpts, 0, 0.085, tur, 0.84, (0, 0.03, 0.165))
    badge(0.06, 0.055, (0.035, 0.07, 0.2515), F(WHITE, 0.6), "z", CHEVRON)  # white recognition chevron
    cy(0.028, 0.01, (-0.05, 0.075, 0.253), F("#24262a"), 8)  # commander's hatch ring
    crewman(-0.05, 0.075, 0.258, "#3c4046", shade(team, 0.72))
    for k, dx in enumerate((-0.062, 0.0, 0.062)):  # stowage bags in the bustle rack
        bx((0.056, 0.036, 0.042), (dx, 0.192, 0.212), F(("#7d7656", "#5f6447", "#8a8160")[k], 0.9), bev=0)
    bx((0.19, 0.006, 0.006), (0, 0.212, 0.236), F("#24262a"), bev=0)  # rack rail
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
    """Heavy hover tank: a gunmetal wedge on team nacelles floating over glowing pads, twin rail cannon, light strips."""
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


def mech(team):
    """DL8 walker (reference frames 2 and 5: mechs among the infantry) facing −Y: reverse-jointed legs with broad
    feet, a hip block, an armoured cockpit with a glowing visor, a shoulder rail cannon and a missile pod, team plates
    and light strips. Gunmetal like the walkers of reference frames 2 and 5."""
    plate = F("#626a75", 0.4)
    dk = F("#2c3139", 0.55)
    tm = F(team, 0.5)
    gl = team_glow(team)
    for sx in (-1, 1):
        x = sx * 0.075
        hip = (x, 0.0, 0.26)
        knee = (x, -0.06, 0.16)
        ankle = (x, 0.03, 0.05)
        beam(hip, knee, 0.045, plate)  # thigh forward
        beam(knee, ankle, 0.034, dk)   # shin back (digitigrade)
        cy(0.026, 0.05, knee, dk, 8, rot=(0, math.pi / 2, 0))
        bx((0.007, 0.036, 0.05), (x + sx * 0.026, -0.02, 0.2), gl, bev=0)
        bx((0.07, 0.1, 0.022), (x, -0.005, 0.012), dk, bev=0.006)  # foot
        bx((0.05, 0.035, 0.018), (x, -0.06, 0.016), plate, bev=0.004)  # toe
    bx((0.2, 0.09, 0.06), (0, 0.0, 0.27), dk, bev=0.01)  # hips
    # cockpit torso, tilted forward
    side_prism([(-0.07, 0.29), (0.06, 0.29), (0.09, 0.34), (0.05, 0.42), (-0.06, 0.43), (-0.09, 0.36)], 0.16, plate)
    bx((0.11, 0.012, 0.03), (0, -0.081, 0.385), glow("visor" + team, team, 3.0), bev=0)
    for sx in (-1, 1):
        bx((0.012, 0.13, 0.1), (sx * 0.083, 0.0, 0.36), tm, bev=0.003)  # team side plates
    # shoulder weapons: a rail cannon on the right, a missile pod on the left
    bx((0.04, 0.06, 0.05), (0.11, 0.0, 0.42), dk, bev=0.006)
    bx((0.022, 0.2, 0.022), (0.11, -0.12, 0.43), plate, bev=0.003)
    bx((0.006, 0.18, 0.008), (0.11, -0.12, 0.444), gl, bev=0)
    bx((0.07, 0.07, 0.06), (-0.12, 0.0, 0.42), dk, bev=0.008)
    for i in range(2):
        for j in range(2):
            cy(0.01, 0.012, (-0.135 + i * 0.03, -0.036, 0.405 + j * 0.03), gl, 6, rot=(math.pi / 2, 0, 0))
    cy(0.006, 0.08, (0.04, 0.05, 0.47), dk, 5)  # antenna
    cy(0.009, 0.01, (0.04, 0.05, 0.512), gl, 6)


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
