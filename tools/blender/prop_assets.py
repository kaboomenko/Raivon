"""Whole-hex props for special hex kinds (raider camp on a wild hex, port, military base).

Builds and exports to OUT (default game/assets/models):
  raider_camp.glb     marauder camp: шатры из шкур с полосами, частокол с воротами, факелы, костёр с котлом
                      (маркер smoke_fire), красное знамя с белой волчьей головой, вышка
  port.glb            fishing / trade port: deep-water cove, pier toward +X, stone and half-timbered warehouse,
                      round harbour tower with a lantern, moored boats, crane, fish stall
  military_base.glb   early-era garrison: stone walls, gatehouse with an arch and banners, slate-roofed towers,
                      stone barracks (маркер smoke_barracks), tents, training yard, smithy, white banner
  warship_<team>.glb  war cog: planked hull, castles with team parapets, lit stern, team sails with the white eagle

Run:   python3 tools/blender/prop_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/prop_assets.py game/assets/models --sheet OUT.png [--cols 1,2,3] [--tile 1.0]
       [--res 3200] [--rot DEG]  (--rot turns every model around Z, to check how it reads from another side)

Conventions (same as evolution_assets.py): Z up, base on Z=0, origin = hex centre, 1 hex = flat-top
hexagon of circumradius 1.0, front faces −Y. Unlike towers these props fill the WHOLE hex: everything stays
within radius ~0.85. Team-neutral. Procedural colours are baked into one 512 px texture; emissive materials
(camp fire, lanterns, lit windows) stay separate so they keep glowing in Godot; empties named smoke* are exported
as plain nodes (map_view hangs chimney smoke on them).
"""
import math
import os
import random
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
import evolution_assets as ev  # noqa: E402  (guarded: importing it builds nothing)
import tower_assets as ta  # noqa: E402  (guarded: importing it builds nothing)
from evolution_assets import (bx, cy, cn, ico, uvs, torus, rod, beam, hip_roof, flat, tex, stone,  # noqa: E402
                              glow, build_at, mesh_obj, extrude, shade, taper_box, WOOD_D, WOOD_L, STONE,
                              STONE_D, GOLD)
from kit import prism_roof  # noqa: E402

CANVAS = "#a29d93"
CANVAS_D = "#858076"
CANVAS_W = "#d3c9b0"
RAG = "#6e1c1a"
RAG_RED = "#a3241b"
SLATE_N = "#56667c"  # neutral slate: the blue-grey roofs of the reference without a team colour
BONE = "#ece3cf"
IRON = "#2e3034"
WATER = "#3f8fc2"
TRIM_BLUE = "#3d6fa8"
SAIL = "#efe7d2"
STRAW = "#d8b25c"
FLAME = "#ff8a1e"
FLAME_Y = "#ffd34a"
HEX_R = 0.84


# ------------------------------------------------------------------ small parts


def tube(p0, p1, r, mt, r2=None, n=6, cap=False):
    """Open-ended n-sided pole (tapered with r2) from p0 to p1 — no hidden end caps (spars, masts, rigging)."""
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(ref).normalized()
    v = d.cross(u)
    r2 = r if r2 is None else r2
    vs = [tuple(c + (u * math.cos(math.tau * k / n) + v * math.sin(math.tau * k / n)) * rr)
          for c, rr in ((a, r), (b, r2)) for k in range(n)]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    if cap:
        faces.append(tuple(range(n, 2 * n)))
    o = mesh_obj(vs, faces, mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


def planks(color, row=0.014, length=0.12, deck=False, across=None):
    """Boards in rows with dark seams and staggered butts (object space): rows follow Z on hull sides and walls,
    run along X on a deck (deck=True). Every board a slightly different tone. across=(oy, ox): deck boards laid
    across X instead, one row per board — the seams fall at x = k * row - ox, the butts shift by oy along Y.
    (The export joins every part into one object, so "object space" is the model's own space.)"""
    key = ("planks", color, row, length, deck, across)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("planks")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sp.inputs[0])
    co = nt.nodes.new("ShaderNodeCombineXYZ")
    if across:
        for src, dst, off in ((1, 0, across[0]), (0, 1, across[1])):
            add = nt.nodes.new("ShaderNodeMath")
            add.operation = "ADD"
            add.inputs[1].default_value = off
            L.new(sp.outputs[src], add.inputs[0])
            L.new(add.outputs[0], co.inputs[dst])
    else:
        L.new(sp.outputs[0], co.inputs[0])
        L.new(sp.outputs[1 if deck else 2], co.inputs[1])
    br = nt.nodes.new("ShaderNodeTexBrick")
    L.new(co.outputs[0], br.inputs["Vector"])
    br.offset = 0.37
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = length
    br.inputs["Row Height"].default_value = row
    br.inputs["Mortar Size"].default_value = row * 0.16
    br.inputs["Mortar Smooth"].default_value = 0.2
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*kit.srgb(color), 1)
    br.inputs["Color2"].default_value = (*kit.srgb(shade(color, 0.8)), 1)
    br.inputs["Mortar"].default_value = (*kit.srgb(shade(color, 0.42)), 1)
    grain = nt.nodes.new("ShaderNodeTexNoise")  # streaky grain along the boards
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (6.0, 60.0, 60.0) if not deck else (6.0, 60.0, 60.0)
    L.new(co.outputs[0], mp.inputs["Vector"])
    L.new(mp.outputs[0], grain.inputs["Vector"])
    grain.inputs["Scale"].default_value = 1.0
    grain.inputs["Detail"].default_value = 3.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.28
    L.new(br.outputs["Color"], mix.inputs["A"])
    L.new(grain.outputs["Color"], mix.inputs["B"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    kit._MATS[key] = m
    return m


def sailcloth(color):
    """Sail canvas: vertical cloths sewn edge to edge (faint seams) with a soft mottle (object space Y/Z)."""
    key = ("sailcloth", color)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("sailcloth")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sp.inputs[0])
    co = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(sp.outputs[1], co.inputs[0])
    L.new(sp.outputs[2], co.inputs[1])
    br = nt.nodes.new("ShaderNodeTexBrick")
    L.new(co.outputs[0], br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Brick Width"].default_value = 0.04
    br.inputs["Row Height"].default_value = 2.0
    br.inputs["Mortar Size"].default_value = 0.0025
    br.inputs["Bias"].default_value = 0.0
    br.inputs["Color1"].default_value = (*kit.srgb(color), 1)
    br.inputs["Color2"].default_value = (*kit.srgb(shade(color, 0.95)), 1)
    br.inputs["Mortar"].default_value = (*kit.srgb(shade(color, 0.84)), 1)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 30.0
    L.new(tc.outputs["Object"], noise.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.18
    L.new(br.outputs["Color"], mix.inputs["A"])
    L.new(noise.outputs["Color"], mix.inputs["B"])
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.85
    kit._MATS[key] = m
    return m


def spike(p0, p1, r, mt, n=5):
    """Open cone (no base) from a ring of radius r at p0 to a point at p1 — a sharpened stake tip, a flame."""
    a, b = Vector(p0), Vector(p1)
    d = (b - a).normalized()
    ref = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
    u = d.cross(ref).normalized()
    v = d.cross(u)
    vs = [tuple(a + (u * math.cos(math.tau * k / n) + v * math.sin(math.tau * k / n)) * r) for k in range(n)]
    o = mesh_obj(vs + [tuple(b)], [(k, (k + 1) % n, n) for k in range(n)], mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


def lathe(prof, mats, n=8, top=None, bottom=None, rot=0.0, loc=(0.0, 0.0, 0.0)):
    """Surface of revolution about Z from prof = [(r, z), ...] bottom → top, one material per band (r = 0 closes a
    band to a point); optional flat caps `top` / `bottom` (materials). No hidden faces."""
    cx, cy_, cz = loc

    def ring(r, z):
        return [(cx + r * math.cos(rot + math.tau * k / n), cy_ + r * math.sin(rot + math.tau * k / n), cz + z)
                for k in range(n)]
    for i in range(len(prof) - 1):
        (r0, z0), (r1, z1) = prof[i], prof[i + 1]
        if r1 == 0:
            vs, fs = ring(r0, z0) + [(cx, cy_, cz + z1)], [(k, (k + 1) % n, n) for k in range(n)]
        elif r0 == 0:
            vs, fs = [(cx, cy_, cz + z0)] + ring(r1, z1), [(0, 1 + (k + 1) % n, 1 + k) for k in range(n)]
        else:
            vs, fs = ring(r0, z0) + ring(r1, z1), [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
        o = mesh_obj(vs, fs, mats[i])
        for p_ in o.data.polygons:
            p_.use_smooth = True
    if top:
        mesh_obj(ring(*prof[-1]), [tuple(range(n))], top)
    if bottom:
        mesh_obj(ring(*prof[0]), [tuple(range(n))], bottom)


def flat_poly(pts, z, mt):
    """One flat polygon lying at height z, facing up (ground decals: trampled paths, lawn, joint caps)."""
    o = mesh_obj([(x, y, z) for x, y in pts], [tuple(range(len(pts)))], mt)
    for p_ in o.data.polygons:
        if p_.normal.z < 0:
            p_.flip()
    return o


def tri_plate(p0, p1, p2, mt, t=0.008):
    """Thin triangular plate (sails, torn cloth, tent doors) with thickness t along its normal."""
    a, b, c = Vector(p0), Vector(p1), Vector(p2)
    n = (b - a).cross(c - a).normalized() * (t / 2)
    vs = [a - n, b - n, c - n, a + n, b + n, c + n]
    faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
    return mesh_obj([tuple(v) for v in vs], faces, mt)


def quad_plate(p0, p1, p2, p3, mt, t=0.008):
    tri_plate(p0, p1, p2, mt, t)
    tri_plate(p0, p2, p3, mt, t)


def stake(x, y, h, r, lean, mt, tip, n=5):
    """Sharpened log: base at (x, y, -0.01), leaning by `lean` (dx, dy) at the top, pointed tip (open shaft and
    tip: no hidden caps)."""
    p0 = Vector((x, y, -0.01))
    p1 = Vector((x + lean[0], y + lean[1], h))
    d = (p1 - p0).normalized()
    tube(tuple(p0), tuple(p1), r, mt, n=n)
    spike(tuple(p1), tuple(p1 + d * r * 2.4), r, tip, n)


def ridge_tent(L, W, h, canvas, patches=(), door=True, sticks=True, seed=0, stripes=()):
    """A-frame canvas tent at the origin: ridge along Y, opening on the −Y gable, patches on the slopes; `stripes`
    = (y fraction of L, width, material) bands painted across both slopes."""
    prism_roof("tent", L, W, h, (0, 0, 0), canvas, overhang=0.0, rot_z=math.pi / 2)
    nl = math.hypot(h, W / 2)
    for (fy, sw, mt) in stripes:
        y0, y1 = fy * L - sw / 2, fy * L + sw / 2
        for sx in (-1, 1):
            ox, oz = sx * h / nl * 0.003, W / 2 / nl * 0.003
            mesh_obj([(ox, y0, h + oz), (sx * W / 2 + ox, y0, oz), (sx * W / 2 + ox, y1, oz), (ox, y1, h + oz)],
                     [(0, 1, 2, 3)], mt)
    dark = flat("tent_in", "#2b2420", 0.9)
    if door:
        tri_plate((-W * 0.22, -L / 2 - 0.004, 0.0), (W * 0.22, -L / 2 - 0.004, 0.0), (0, -L / 2 - 0.004, h * 0.78),
                  dark, 0.006)
        # one flap rolled back to the side
        tri_plate((W * 0.22, -L / 2 - 0.006, 0.0), (W * 0.36, -L / 2 - 0.03, 0.0), (0.0, -L / 2 - 0.006, h * 0.78),
                  canvas, 0.008)
    wd = tex("wood", WOOD_D, 2.0)
    if sticks:
        for sy in (-1, 1):
            y = sy * (L / 2 + 0.006)
            for sx in (-1, 1):
                rod((sx * 0.012, y, h - 0.02), (-sx * 0.025, y, h + 0.035), 0.006, wd, n=4)
    rnd = random.Random(seed)
    ang = math.atan2(h, W / 2)
    for i, pm in enumerate(patches):
        sx = 1 if i % 2 == 0 else -1
        u = rnd.uniform(0.3, 0.65)             # 0 = ridge, 1 = eave
        y = rnd.uniform(-L * 0.3, L * 0.3)
        x = sx * u * W / 2
        z = h * (1 - u)
        s = rnd.uniform(0.045, 0.07)
        bx((s, s * rnd.uniform(0.8, 1.3), 0.006), (x + sx * 0.004 * math.sin(ang), y, z + 0.004 * math.cos(ang)),
           pm, bev=0, rot=(0, sx * ang, 0))


def cone_tent(r, h, canvas, patches=(), seed=0, bands=()):
    """Round marauder tent (yurt-like cone), a dark doorway toward −Y, poles crossing above the apex; `bands` =
    (from, to height fraction, material) rings painted round the hide."""
    cn(r, h, (0, 0, h / 2), canvas, 8, rot=(0, 0, math.pi / 8))
    for (f0, f1, mt) in bands:
        lathe([(r * (1 - f0) + 0.004, h * f0), (r * (1 - f1) + 0.004, h * f1)], (mt,), 8, rot=math.pi / 8)
    ap = r * math.cos(math.pi / 8)
    dark = flat("tent_in", "#2b2420", 0.9)
    f = 0.42
    tri_plate((-0.055, -ap - 0.006, 0.0), (0.055, -ap - 0.006, 0.0), (0, -ap * (1 - f) - 0.006, h * f), dark, 0.006)
    wd = tex("wood", WOOD_D, 2.0)
    for k in range(3):
        a = k * math.tau / 3 + 0.4
        rod((math.cos(a) * r * 0.16, math.sin(a) * r * 0.16, h * 0.82),
            (-math.cos(a) * r * 0.22, -math.sin(a) * r * 0.22, h * 1.16), 0.008, wd, n=4)
    cy(r * 0.08, 0.03, (0, 0, h * 0.86), tex("wood", "#3a2a1e", 2.0), 6)  # smoke hole collar
    rnd = random.Random(seed)
    slope = math.atan2(r, h)
    for i, pm in enumerate(patches):
        a = -math.pi / 2 + (i + 1) * math.tau / (len(patches) + 1) + rnd.uniform(-0.2, 0.2)
        u = rnd.uniform(0.25, 0.55)                       # height fraction
        rr = r * (1 - u) * math.cos(math.pi / 8) + 0.004
        s = rnd.uniform(0.05, 0.075)
        o = bx((s * 0.9, 0.006, s), (math.cos(a) * rr, math.sin(a) * rr, h * u), pm, bev=0)
        o.rotation_euler = (-slope, 0, a + math.pi / 2)  # XYZ euler: tilt about X first, then turn about Z
    # rope band around the skirt
    cy(r * 0.79 + 0.004, 0.012, (0, 0, h * 0.2), tex("plaster", "#6b5a44", 3.0), 8, r2=r * 0.79 + 0.004,
       rot=(0, 0, math.pi / 8))


def crate(x, y, s, rz=0.0, z=0.0, c="#a07a4a"):
    bx((s, s, s), (x, y, z + s / 2), tex("wood", c, 4.0), rz, bev=0)
    bx((s + 0.006, s + 0.006, s * 0.18), (x, y, z + s / 2), tex("wood", shade(c, 0.65), 3.0), rz, bev=0)


def barrel(x, y, r=0.034, h=0.085, z=0.0, c="#8a5e36", lie=None):
    """Barrel: staves swelling between two dark iron-bound ends, a lighter lid (one lean lathe, no hidden faces)."""
    def b():
        wd = tex("wood", c, 3.0)
        hoop = flat("hoop", IRON, 0.6)
        lathe([(r * 0.86, 0.0), (r * 0.98, h * 0.15), (r * 0.98, h * 0.85), (r * 0.86, h)], (hoop, wd, hoop), 8,
              top=tex("wood", shade(c, 1.2), 3.0), bottom=hoop if lie is not None else None)
    if lie is None:
        build_at(b, x, y, z=z)
    else:
        build_at(b, x, y, lie, tilt=(0, math.pi / 2), z=z + r)


def sack(x, y, s=1.0, rz=0.0, z=0.0, c="#b9a27a"):
    m = tex("plaster", c, 3.0)
    o = uvs(0.04 * s, (x, y, z + 0.032 * s), m, 6, 4, (1.0, 0.8, 0.85))
    o.rotation_euler.z = rz
    spike((x, y, z + 0.058 * s), (x, y, z + 0.08 * s), 0.012 * s, m, 5)


def rope_coil(x, y, r=0.035, z=0.0):
    m = tex("plaster", "#cdb88c", 4.0)
    torus(r, 0.008, (x, y, z + 0.008), m, seg=8, mseg=3)
    torus(r * 0.7, 0.008, (x, y, z + 0.018), m, seg=6, mseg=3)


def spear(p0, p1, wood, iron, r=0.006):
    tube(p0, p1, r, wood, n=4)
    d = (Vector(p1) - Vector(p0)).normalized()
    spike(p1, tuple(Vector(p1) + d * 0.04), 0.011, iron, 4)


def weapon_rack(x, y, rz, n_spears=4, shields=0, shield_c=None, axes=0):
    """A-frame weapon rack along local X: spears leaning on a bar, optional round shields and axes."""
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        wl = tex("wood", "#9a7046", 3.0)
        iron = flat("iron", IRON, 0.5)
        for sx in (-1, 1):
            tube((sx * 0.1, -0.035, 0.0), (sx * 0.1, 0.0, 0.11), 0.008, wd, n=4)
            tube((sx * 0.1, 0.035, 0.0), (sx * 0.1, 0.0, 0.11), 0.008, wd, n=4)
        tube((-0.115, 0.0, 0.105), (0.115, 0.0, 0.105), 0.008, wd, n=4)
        tube((-0.1, 0.0, 0.035), (0.1, 0.0, 0.035), 0.006, wd, n=4)
        for i in range(n_spears):
            xx = -0.07 + i * 0.14 / max(1, n_spears - 1)
            spear((xx, -0.05, 0.0), (xx + 0.004, 0.01, 0.2), wl, iron)
        for i in range(axes):
            xx = 0.05 - i * 0.07
            tube((xx, 0.04, 0.0), (xx, 0.012, 0.12), 0.006, wl, n=4)
            bx((0.012, 0.035, 0.03), (xx, 0.022, 0.11), iron, bev=0, rot=(-0.23, 0, 0))
        for i in range(shields):
            xx = -0.06 + i * 0.12
            sm = tex("wood", shield_c or "#8a6440", 2.0)
            nrm = Vector((0.0, -math.cos(0.25), math.sin(0.25)))
            c = Vector((xx, -0.05, 0.045))
            tube(tuple(c + nrm * 0.005), tuple(c - nrm * 0.005), 0.042, sm, n=10, cap=True)
            spike(tuple(c - nrm * 0.004), tuple(c - nrm * 0.016), 0.012, iron, 4)
    build_at(b, x, y, rz)


def ground_poly(pts, mt, h=0.01):
    return extrude(pts, -0.01, h, mt)


def clamp_hex(p, r=HEX_R):
    """Pull a point inside a flat-top hexagon of circumradius r."""
    x, y = p
    a = math.atan2(y, x)
    k = math.floor((a + math.tau) % math.tau / (math.pi / 3))
    a0 = k * math.pi / 3
    c0 = (r * math.cos(a0), r * math.sin(a0))
    c1 = (r * math.cos(a0 + math.pi / 3), r * math.sin(a0 + math.pi / 3))
    # distance from centre to the hex edge along a (edge between c0 and c1)
    ex, ey = c1[0] - c0[0], c1[1] - c0[1]
    dx, dy = math.cos(a), math.sin(a)
    den = dx * ey - dy * ex
    t = (c0[0] * ey - c0[1] * ex) / den if abs(den) > 1e-9 else r
    d = math.hypot(x, y)
    if d > t:
        return (dx * t, dy * t), True
    return (x, y), False


# ------------------------------------------------------------------ raider camp


# the white beast's head of the enemy war banners (reference frame 1, the red side: red banners with a white wolf):
# pricked ears, ruffed cheeks, a long muzzle — an outline in a unit box (u right, v up)
WOLF = [(0.0, 0.1), (0.24, 0.5), (0.33, 0.1), (0.48, 0.0), (0.33, -0.07), (0.4, -0.2), (0.15, -0.17), (0.07, -0.5),
        (-0.07, -0.5), (-0.15, -0.17), (-0.4, -0.2), (-0.33, -0.07), (-0.48, 0.0), (-0.33, 0.1), (-0.24, 0.5)]


def emblem_xz(x, y, z, w, h, mt, pts):
    """Flat one-polygon emblem w × h centred at (x, y, z) in a plane facing ±Y."""
    return mesh_obj([(x + u * w, y, z + v * h) for u, v in pts], [tuple(range(len(pts)))], mt)


def torch(x, y, z, wood):
    """Burning torch: a stick ending at z with a pitch-black head and a two-tone flame (glow, kept out of the bake)."""
    tube((x, y, z - 0.08), (x, y, z), 0.008, wood, n=4)
    tube((x, y, z - 0.004), (x, y, z + 0.018), 0.011, flat("pitch", "#2a211c", 0.9), r2=0.014, n=5, cap=True)
    spike((x, y, z + 0.012), (x + 0.004, y, z + 0.085), 0.017, glow("flame", FLAME, 3.0), 5)
    spike((x, y, z + 0.016), (x + 0.002, y - 0.003, z + 0.06), 0.011, glow("flame_y", FLAME_Y, 3.5), 5)


def war_banner(px, py, H, cloth_c=RAG_RED, em_c=BONE):
    """Marauder war banner: a rough pole with a lashed cross stick, a long red cloth with a ragged foot and the white
    wolf's head on both faces (facing −Y), a horned skull on the pole top, two tattered streamers."""
    pole = tex("wood", "#5a3e27", 2.0)
    tube((px, py, -0.01), (px - 0.008, py + 0.006, H), 0.016, pole, r2=0.011, n=6)
    rk = tex("plaster", "#7f7b75", 1.5)
    for k in range(3):
        a = k * math.tau / 3 + 0.3
        ico(0.028, (px + math.cos(a) * 0.034, py + math.sin(a) * 0.034, 0.01), rk, (1.1, 1.0, 0.7))
    top = H - 0.06
    yc = py - 0.016
    tube((px - 0.135, yc + 0.004, top + 0.01), (px + 0.135, yc + 0.004, top + 0.006), 0.008, pole, n=5)
    cloth = flat("war_cloth", cloth_c, 0.85)
    w, h = 0.11, 0.32
    foot = [(1.0, -0.8), (0.75, -1.0), (0.5, -0.82), (0.22, -1.03), (0.0, -0.85), (-0.25, -1.04), (-0.52, -0.83),
            (-0.76, -1.0), (-1.0, -0.82)]
    pts = [(px - w, 0.0), (px + w, 0.0)] + [(px + u * w, v * h) for u, v in foot]
    mesh_obj([(x, yc, top + z) for x, z in pts], [tuple(range(len(pts)))], cloth)
    trim = flat("war_trim", shade(cloth_c, 0.55), 0.85)  # dark band along the head of the cloth
    mesh_obj([(px - w, yc - 0.002, top), (px + w, yc - 0.002, top), (px + w, yc - 0.002, top - 0.03),
              (px - w, yc - 0.002, top - 0.03)], [(0, 1, 2, 3)], trim)
    mesh_obj([(px - w, yc + 0.002, top), (px + w, yc + 0.002, top), (px + w, yc + 0.002, top - 0.03),
              (px - w, yc + 0.002, top - 0.03)], [(0, 1, 2, 3)], trim)
    em = flat("war_emblem", em_c, 0.7)
    eye = flat("war_eye", "#2a1512", 0.9)
    ez = top - 0.15
    for dy in (-0.003, 0.003):
        emblem_xz(px, yc + dy, ez, 0.19, 0.21, em, WOLF)
        for sx in (-1, 1):  # slanted eyes
            mesh_obj([(px + sx * 0.012, yc + 2 * dy, ez + 0.006), (px + sx * 0.05, yc + 2 * dy, ez + 0.026),
                      (px + sx * 0.03, yc + 2 * dy, ez - 0.006)], [(0, 1, 2)], eye)
        mesh_obj([(px - 0.014, yc + 2 * dy, ez - 0.085), (px + 0.014, yc + 2 * dy, ez - 0.085),
                  (px, yc + 2 * dy, ez - 0.105)], [(0, 1, 2)], eye)  # nose
    rag_d = flat("rag_d", shade(RAG, 0.7), 0.9)
    for sx, ln in ((-1, 0.16), (1, 0.12)):  # streamers off the stick ends
        x = px + sx * 0.128
        mesh_obj([(x - 0.009, yc, top + 0.006), (x + 0.009, yc, top + 0.006), (x + 0.012 * sx, yc, top - ln),
                  (x - 0.006, yc, top - ln * 0.8)], [(0, 1, 2, 3)], rag_d)
    skull(px - 0.008, py + 0.006, H + 0.016, 1.25)


def lookout_l1(wood, plank, hide, torch_wood):
    """Crude raised lookout of lashed poles: splayed legs with X-braces, a plank deck with a stick rail, a hide
    awning, a ladder up the front and a torch."""
    H = 0.34
    tops = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            b0, t0 = (sx * 0.1, sy * 0.1, -0.01), (sx * 0.068, sy * 0.068, H + 0.12)
            tube(b0, t0, 0.012, wood, r2=0.009, n=5)
            tops.append(t0)
    for (a, b) in (((-1, -1), (1, -1)), ((1, -1), (1, 1))):  # X-braces on the front and the right side
        p = [(sx * 0.093, sy * 0.093) for sx, sy in (a, b)]
        tube((p[0][0], p[0][1], 0.03), (p[1][0], p[1][1], H - 0.03), 0.009, wood, n=4)
        tube((p[1][0], p[1][1], 0.03), (p[0][0], p[0][1], H - 0.03), 0.009, wood, n=4)
    bx((0.19, 0.19, 0.018), (0, 0, H), plank, bev=0)
    for k in range(4):  # rail of sticks round the deck
        a, b = tops[(0, 1, 3, 2)[k]], tops[(1, 3, 2, 0)[k]]
        tube((a[0], a[1], H + 0.065), (b[0], b[1], H + 0.065), 0.008, wood, n=4)
    mesh_obj([(-0.1, 0.1, H + 0.14), (0.1, 0.1, H + 0.14), (0.11, -0.11, H + 0.1), (-0.11, -0.11, H + 0.1)],
             [(0, 1, 2, 3)], hide)
    for sx in (-1, 1):  # ladder up the front
        tube((sx * 0.034, -0.2, -0.01), (sx * 0.034, -0.1, H + 0.01), 0.008, wood, n=4)
    for k in range(4):
        f = (k + 0.6) / 4.6
        y, z = -0.2 + 0.1 * f, H * f
        tube((-0.036, y, z), (0.036, y, z), 0.006, wood, n=4)
    # torch on a bracket off the front-right leg, out in front of the awning (its flame clears the hide roof)
    tube((0.07, -0.072, H + 0.03), (0.078, -0.138, H + 0.03), 0.007, wood, n=4)
    torch(0.078, -0.14, H + 0.09, torch_wood)


def raider_camp():
    """Marauder camp (reference frame 1, the enemy side: red war banners with a white beast's head, fires and
    smoke): a sharpened-log palisade with a lashed gate frame, skulls and torches; hide tents painted with dark and
    red bands, the chief's tent under a red awning; a camp fire with a tripod and cauldron (smoke marker for the
    game); the red wolf banner; a raised lookout with a torch; a hide on a stretching frame, a woodpile, a weapon
    rack, a pile of loot, trampled paths and grass at the foot of the stakes."""
    dirt = tex("plaster", "#86684a", 1.4)
    ev.pad(0.79, dirt, 0.006, 16, 0.05, 7)
    ev.pad(0.42, tex("plaster", "#6f553c", 1.6), 0.01, 12, 0.12, 8)  # trampled centre
    mud = flat("mud_path", "#674c36", 0.95)
    flat_poly([(-0.12, -0.755), (-0.02, -0.74), (0.11, -0.755), (0.1, -0.62), (0.07, -0.5), (0.12, -0.36), (0.05, -0.27),
               (-0.04, -0.3), (-0.07, -0.42), (-0.05, -0.56), (-0.1, -0.68)], 0.012, mud)  # worn from the gate in
    flat_poly([(0.1, 0.0), (0.17, 0.06), (0.21, 0.15), (0.15, 0.19), (0.1, 0.12), (0.04, 0.06)], 0.012, mud)
    lawn = flat("camp_lawn", "#5f7432", 0.95)  # tufty grass left where nobody walks, by the stakes
    for (cx_, cy2, r_, n_, sd) in ((-0.56, 0.3, 0.1, 7, 1), (0.08, 0.64, 0.09, 6, 2), (-0.62, -0.32, 0.08, 6, 3),
                                   (0.6, -0.34, 0.08, 6, 4), (-0.2, 0.62, 0.07, 6, 5)):
        flat_poly(ev.ngon(r_, n_, 0.3, 1.3, 0.8, 0.25, sd), 0.0, lawn).location = (cx_, cy2, 0.009)
    # ---- palisade ring with a gap at the front (−Y)
    wd = tex("wood", "#6e4c30", 2.0)
    wd2 = tex("wood", "#5a3e27", 2.0)
    tip = flat("stake_tip", "#c9a471", 0.85)
    rnd = random.Random(11)
    R = 0.74
    n = 60
    gap = math.radians(24)
    for k in range(n):
        a = -math.pi / 2 + (k + 0.5) * math.tau / n
        if abs(math.atan2(math.sin(a + math.pi / 2), math.cos(a + math.pi / 2))) < gap:
            continue
        if rnd.random() < 0.06:  # a missing log here and there
            continue
        rr = R + rnd.uniform(-0.012, 0.012)
        x, y = math.cos(a) * rr, math.sin(a) * rr
        h = rnd.uniform(0.16, 0.24)
        lean = 0.03 + rnd.uniform(-0.01, 0.015)
        stake(x, y, h, 0.024, (math.cos(a) * lean + rnd.uniform(-0.01, 0.01), math.sin(a) * lean), wd if k % 3 else wd2,
              tip)
    # lashed cross rails in sections (inner side)
    rail = tex("wood", "#7d5a38", 3.0)
    sec = math.tau / 9
    a = -math.pi / 2 + gap + 0.03
    while a + sec * 0.6 < math.tau - math.pi / 2 - gap:
        a1 = min(a + sec, math.tau - math.pi / 2 - gap - 0.03)
        rr = R - 0.03
        tube((math.cos(a) * rr, math.sin(a) * rr, 0.1 + rnd.uniform(-0.01, 0.01)),
             (math.cos(a1) * rr, math.sin(a1) * rr, 0.11 + rnd.uniform(-0.01, 0.01)), 0.01, rail, n=4)
        a = a1 + 0.02
    # grass growing at the foot of the stakes, inside and out
    grass = flat("camp_grass", "#5d7a2e", 0.9)
    grass2 = flat("camp_grass2", "#8a9a40", 0.9)
    for k in range(14):
        a = -math.pi / 2 + gap + 0.15 + k * (math.tau - 2 * gap - 0.3) / 13
        rr = R - 0.07 + rnd.uniform(-0.012, 0.012)
        cx_, cy2 = math.cos(a) * rr, math.sin(a) * rr
        for j in range(4):
            b = j * math.tau / 4 + k
            spike((cx_ + math.cos(b) * 0.014, cy2 + math.sin(b) * 0.014, 0.0),
                  (cx_ + math.cos(b) * 0.04, cy2 + math.sin(b) * 0.04, 0.06 + 0.02 * ((j + k) % 3)), 0.011,
                  grass if (j + k) % 2 else grass2, 3)
    # gate: two tall posts, a lashed lintel log with a skull and bones, a torch on each post
    gp = []
    for sx in (-1, 1):
        a = -math.pi / 2 + sx * (gap + 0.04)
        x, y = math.cos(a) * R, math.sin(a) * R
        stake(x, y, 0.36, 0.032, (0.0, -0.01), wd2, tip, n=6)
        gp.append((x, y - 0.01))
        torch(x, y - 0.045, 0.3, wd2)
        tube((x, y - 0.01, 0.24), (x, y - 0.045, 0.24), 0.008, wd2, n=4)  # bracket
    tube((gp[0][0] - 0.03, gp[0][1], 0.31), (gp[1][0] + 0.03, gp[1][1], 0.32), 0.02, wd2, n=6)
    rope = flat("lash_rope", "#b49a6a", 0.8)
    for (x, y) in gp:
        tube((x, y, 0.29), (x, y, 0.34), 0.024, rope, n=6)
    skull(0.0, gp[0][1] - 0.012, 0.255, 1.15)
    tube((0.0, gp[0][1] - 0.004, 0.31), (0.0, gp[0][1] - 0.008, 0.285), 0.003, rope, n=3)
    # ---- tents: hide and canvas with painted bands, patches; the chief's tent with a red awning
    pA = tex("plaster", "#b8a684", 2.5)
    pB = tex("plaster", "#6c6257", 2.5)
    pC = tex("plaster", "#8b7a62", 2.5)
    band_d = flat("tent_band_d", "#3e2f24", 0.9)
    band_r = flat("tent_band_r", "#8a2a20", 0.85)
    build_at(lambda: cone_tent(0.22, 0.4, tex("plaster", "#a38a66", 1.8), (pA, pB, pC, pA), 3,
                               bands=((0.12, 0.2, band_d), (0.46, 0.53, band_r))), -0.3, 0.32, 0.0)

    def chief_tent():
        L_, W_, h_ = 0.32, 0.27, 0.21
        ridge_tent(L_, W_, h_, tex("plaster", "#8f7a5a", 1.8), (pA, pB, pA, pC), seed=5,
                   stripes=((-0.3, 0.035, band_d), (0.3, 0.035, band_d), (0.0, 0.03, band_r)))
        awn = flat("awning", RAG_RED, 0.85)
        y0, y1 = -L_ / 2, -L_ / 2 - 0.13
        for sx in (-1, 1):
            tube((sx * 0.1, y1, -0.01), (sx * 0.1, y1, h_ * 0.7), 0.008, wd2, n=4)
        dag = [(-0.11, y1, h_ * 0.69)] + [(-0.11 + 0.22 * k / 6, y1 - 0.004, h_ * (0.69 if k % 2 == 0 else 0.6))
                                          for k in range(1, 6)] + [(0.11, y1, h_ * 0.69)]
        mesh_obj([(0.0, y0 + 0.005, h_ * 0.86)] + dag, [tuple(range(len(dag) + 1))], awn)
        skull(0.0, y0 - 0.012, h_ * 0.78, 0.9)
    build_at(chief_tent, 0.25, 0.38, -0.45)
    build_at(lambda: ridge_tent(0.22, 0.2, 0.15, tex("plaster", "#9a948a", 1.8), (pB, pA, pC), seed=9,
                                stripes=((-0.25, 0.03, band_d), (0.25, 0.03, band_d))),
             -0.5, -0.12, -math.pi / 2 - 0.35)
    # ---- camp fire: stone ring, crossed logs, flame, a tripod with a cauldron; the game adds the smoke
    fx, fy = 0.04, -0.06
    rk = tex("plaster", "#7f7b75", 1.5)
    for k in range(9):
        a = k * math.tau / 9
        ico(0.022, (fx + math.cos(a) * 0.075, fy + math.sin(a) * 0.075, 0.016), rk, (1.2, 1.0, 0.75))
    ico(0.05, (fx, fy, 0.005), flat("ash", "#3a3330", 0.95), (1.2, 1.2, 0.25))
    logm = tex("wood", "#5e3d24", 2.5)
    for k in range(4):
        a = k * math.pi / 2 + 0.4
        tube((fx + math.cos(a) * 0.065, fy + math.sin(a) * 0.065, 0.01), (fx, fy, 0.075), 0.011, logm, n=5)
    cn(0.045, 0.11, (fx, fy, 0.065), glow("flame", FLAME, 3.0), 6)
    cn(0.026, 0.08, (fx + 0.005, fy - 0.004, 0.06), glow("flame_y", FLAME_Y, 3.5), 6)
    for k in range(3):  # tripod over the fire, a cauldron on a chain
        a = k * math.tau / 3 + 0.5
        tube((fx + math.cos(a) * 0.11, fy + math.sin(a) * 0.11, -0.005), (fx, fy, 0.25), 0.009, wd2, n=4)
    pot = flat("cauldron", "#2b2a2c", 0.5)
    tube((fx, fy, 0.25), (fx, fy, 0.16), 0.004, pot, n=3)
    lathe([(0.018, 0.115), (0.032, 0.13), (0.03, 0.16)], (pot, pot), 8, top=flat("stew", "#6b4a2a", 0.6),
          loc=(fx, fy, 0.0))
    bpy.ops.object.empty_add(location=(fx, fy, 0.2))
    bpy.context.active_object.name = "smoke_fire"
    # log seats
    seat = tex("wood", "#7a5232", 2.5)
    for a, ln in ((math.radians(200), 0.16), (math.radians(-20), 0.14)):
        x, y = fx + math.cos(a) * 0.19, fy + math.sin(a) * 0.19
        cy(0.026, ln, (x, y, 0.026), seat, 6, rot=(math.pi / 2, 0, a))
    # ---- the red war banner with the white wolf, at the back of the camp
    war_banner(0.0, 0.52, 0.86)
    # ---- raised lookout over the palisade on the right
    build_at(lambda: lookout_l1(wd, tex("wood", "#8a6440", 3.0), tex("plaster", "#7d6a50", 2.0), wd2), 0.5, 0.06,
             -0.25)
    # ---- a hide stretched on a frame, a woodpile
    def hide_frame():
        tube((-0.07, 0.0, -0.01), (-0.07, 0.0, 0.2), 0.01, wd2, n=4)
        tube((0.07, 0.0, -0.01), (0.07, 0.0, 0.2), 0.01, wd2, n=4)
        tube((-0.085, 0.0, 0.19), (0.085, 0.0, 0.19), 0.009, wd2, n=4)
        tube((-0.075, 0.0, 0.035), (0.075, 0.0, 0.035), 0.009, wd2, n=4)
        hide_pts = [(-0.05, 0.18), (0.0, 0.17), (0.05, 0.18), (0.058, 0.12), (0.048, 0.05), (0.0, 0.045),
                    (-0.048, 0.05), (-0.058, 0.12)]
        mesh_obj([(x, -0.004, z) for x, z in hide_pts], [tuple(range(len(hide_pts)))], flat("hide", "#9a7650", 0.9))
        mesh_obj([(x * 0.5, -0.006, 0.112 + (z - 0.112) * 0.5) for x, z in hide_pts], [tuple(range(len(hide_pts)))],
                 flat("hide_d", "#6e5034", 0.9))
    build_at(hide_frame, -0.3, -0.03, 0.15)
    def woodpile():
        cap = flat("logcut", "#d9b27a", 0.8)
        for row, ys in enumerate(((-0.028, 0.0, 0.028), (-0.014, 0.014))):
            for yy in ys:
                z = 0.016 + row * 0.026
                tube((-0.07, yy, z), (0.07, yy, z), 0.014, tex("wood", "#7a5232", 3.0), n=5)
                for sx in (-1, 1):
                    mesh_obj([(sx * 0.0705, yy + 0.013 * math.cos(math.tau * k / 5), z + 0.013 * math.sin(
                        math.tau * k / 5)) for k in range(5)], [tuple(range(5))], cap)
    build_at(woodpile, -0.06, 0.24, 0.3)
    # ---- weapon rack (front left) and a pile of loot (front right)
    weapon_rack(-0.4, -0.4, 0.75, 3, 1, RAG_RED, 1)
    crate(0.36, -0.36, 0.085, 0.3)
    crate(0.44, -0.27, 0.07, -0.2)
    crate(0.37, -0.35, 0.06, 0.6, z=0.085)
    sack(0.47, -0.4, 1.0, 0.4)
    sack(0.27, -0.44, 0.9, -0.5)
    barrel(0.52, -0.18, lie=0.3)
    # open chest with gold
    build_at(lambda: (bx((0.08, 0.05, 0.04), (0, 0, 0.02), tex("wood", "#5e3d24", 3.0), bev=0),
                      bx((0.085, 0.055, 0.008), (0, 0, 0.004), flat("iron", IRON, 0.5), bev=0),
                      uvs(0.035, (0, 0, 0.038), flat("gold", GOLD, 0.35), 8, 4, (1.05, 0.65, 0.4)),
                      bx((0.08, 0.012, 0.045), (0, 0.032, 0.058), tex("wood", "#5e3d24", 3.0), bev=0, rot=(-0.35, 0, 0))),
             0.18, -0.4, 0.15)
    # bones on the ground
    bone = flat("bone", BONE, 0.7)
    tube((-0.14, -0.3, 0.008), (-0.08, -0.33, 0.008), 0.006, bone, n=4)
    tube((-0.12, -0.36, 0.008), (-0.09, -0.29, 0.008), 0.006, bone, n=4)


def skull(x, y, z, s=1.0):
    """Horned skull facing −Y: a round cranium, a jaw block, dark eye sockets."""
    def b():
        bone = flat("bone", BONE, 0.7)
        hole = flat("socket", "#1c1714", 0.9)
        ico(0.028, (0, 0, 0.0), bone, (1.0, 1.0, 1.0))
        bx((0.034, 0.03, 0.02), (0, -0.008, -0.02), bone, bev=0)
        for sx in (-1, 1):
            mesh_obj([(sx * 0.004, -0.0265, 0.008), (sx * 0.02, -0.0235, 0.008), (sx * 0.012, -0.0262, -0.006)],
                     [(0, 1, 2)], hole)
            spike((sx * 0.02, 0.0, 0.016), (sx * 0.042, 0.0, 0.045), 0.008, bone, 4)  # little horns
    build_at(b, x, y, z=z, s=s)


# ------------------------------------------------------------------ port


def hull(L, W, H, body, deck, trim=None):
    """Boat hull along X (bow at +X): flared sides, pointed bow, flat transom, planked deck at the top."""
    top = [(-L / 2, -0.38 * W), (-L * 0.3, -0.5 * W), (L * 0.05, -0.5 * W), (L * 0.3, -0.36 * W), (L / 2, 0.0),
           (L * 0.3, 0.36 * W), (L * 0.05, 0.5 * W), (-L * 0.3, 0.5 * W), (-L / 2, 0.38 * W)]
    bot = [(x * 0.82 if x > 0 else x * 0.9, y * 0.45) for x, y in top]
    n = len(top)
    vs = [(x, y, 0.0) for x, y in bot] + [(x, y, H) for x, y in top]
    faces = [tuple(reversed(range(n)))] + [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    mesh_obj(vs, faces + [tuple(range(n, 2 * n))], body)
    inner = [(x * 0.9, y * 0.8) for x, y in top]
    extrude(inner, H - 0.012, H - 0.004, deck)
    if trim:
        band = [(x * 1.01, y * 1.06) for x, y in top]
        extrude(band, H - 0.02, H - 0.006, trim)
    bx((0.012, 0.012, H * 0.6), (L / 2 + 0.002, 0, H * 0.9), body, bev=0)  # stem post


def sailboat():
    """Small fishing sailboat along X with a triangular sail on the mast (visible from either side)."""
    body = tex("wood", "#7a5232", 3.0)
    deck = tex("wood", "#b48a58", 4.0)
    trim = flat("trim_blue", TRIM_BLUE, 0.6)
    hull(0.4, 0.15, 0.075, body, deck, trim)
    wd = tex("wood", "#5a3e27", 2.0)
    mx = 0.04
    cy(0.009, 0.46, (mx, 0, 0.075 + 0.23), wd, 6)
    beam((mx - 0.16, 0, 0.12), (mx + 0.01, 0, 0.12), 0.012, wd)  # boom
    sail = flat("sail", SAIL, 0.8)
    tri_plate((mx - 0.005, 0, 0.52), (mx - 0.005, 0, 0.135), (mx - 0.155, 0, 0.135), sail, 0.006)
    tri_plate((mx + 0.005, 0, 0.47), (mx + 0.005, 0, 0.135), (mx + 0.135, 0, 0.135), sail, 0.006)  # jib
    st = flat("sail_blue", TRIM_BLUE, 0.7)
    quad_plate((mx - 0.006, 0, 0.28), (mx - 0.006, 0, 0.25), (mx - 0.112, 0, 0.18), (mx - 0.083, 0, 0.215), st, 0.009)
    ico(0.012, (mx, 0, 0.535), flat("pennant", TRIM_BLUE, 0.6))
    rig = flat("rigging", "#3a2c20", 0.8)  # thin dark rigging, as on the reference ships
    rod((mx, 0, 0.5), (0.2, 0, 0.08), 0.0045, rig, n=3)  # forestay
    rod((mx, 0, 0.5), (-0.19, 0, 0.08), 0.0045, rig, n=3)  # backstay
    crate(-0.1, 0.02, 0.045, 0.3, z=0.068)
    barrel(-0.1, -0.035, 0.018, 0.04, z=0.068)


def rowboat():
    body = tex("wood", "#8a6440", 3.0)
    deck = tex("wood", "#5e4126", 3.0)
    hull(0.22, 0.1, 0.05, body, deck, flat("trim_blue", TRIM_BLUE, 0.6))
    bx((0.016, 0.085, 0.01), (0.0, 0, 0.05), tex("wood", WOOD_L, 3.0), bev=0)
    oar = tex("wood", "#c9a06a", 3.0)
    for sy in (-1, 1):
        rod((-0.03, sy * 0.03, 0.055), (0.07, sy * 0.13, 0.012), 0.0055, oar, n=4)
        bx((0.035, 0.016, 0.004), (0.075, sy * 0.135, 0.01), oar, math.atan2(0.1, 0.1) * sy, bev=0)


def crane():
    """Wooden quay derrick: braced mast, angled jib reaching to +X over the water, rope with a cargo net."""
    wd = tex("wood", "#6a4327", 2.0)
    wl = tex("wood", "#9a7046", 2.5)
    for a in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        beam((math.cos(a) * 0.08, math.sin(a) * 0.08, 0.012), (0, 0, 0.012), 0.024, wd)
        beam((math.cos(a) * 0.07, math.sin(a) * 0.07, 0.015), (0, 0, 0.14), 0.014, wl)
    cy(0.02, 0.44, (0, 0, 0.22), wd, 6)
    jib0 = (0.0, 0.0, 0.22)
    jib1 = (0.27, 0.0, 0.48)
    beam(jib0, jib1, 0.022, wl)
    beam((0, 0, 0.43), (0.18, 0, 0.395), 0.012, wl)
    rope = flat("rope", "#e8dcc0", 0.8)
    rod((0.0, 0.0, 0.44), (0.27, 0.0, 0.48), 0.0045, rope, n=3)
    rod(jib1, (0.27, 0.0, 0.2), 0.0045, rope, n=3)
    cy(0.03, 0.04, (-0.035, 0.0, 0.13), wl, 8, rot=(math.pi / 2, 0, 0))  # winch drum
    torus(0.03, 0.005, (-0.035, 0.0, 0.13), rope, rot=(math.pi / 2, 0, 0), seg=8, mseg=3)
    # hanging bundle (net of sacks)
    uvs(0.045, (0.27, 0.0, 0.17), tex("plaster", "#b9a27a", 3.0), 8, 5, (1.0, 1.0, 0.9))
    for a in (0.5, 2.6, 4.6):
        rod((0.27, 0.0, 0.21), (0.27 + math.cos(a) * 0.04, math.sin(a) * 0.04, 0.17), 0.0035, rope, n=3)


def _cove(quay, water_c=WATER, shallow_c="#79c1df", joints=False, edge=None):
    """The port's water cove opening at the +X edge with a lighter rim and a quay along the land side. `joints`:
    the quay and the rim are continuous mitred strips (no stone ends overlapping in one plane where two runs meet at
    an angle — the dark notches and flicker of separate beams); otherwise one beam per stretch."""
    # ---- water cove (an inlet so the port reads on any tile, whatever the neighbours are)
    cx = 0.5
    pts = []
    rnd = random.Random(4)
    for k in range(24):
        a = k * math.tau / 24
        r = 1.0 + rnd.uniform(-0.04, 0.04)
        p = (cx + math.cos(a) * 0.42 * r, math.sin(a) * 0.66 * r)
        p, _ = clamp_hex(p, HEX_R)
        pts.append(p)
    water = tex("plaster", water_c, 1.2)
    ground_poly(pts, water, 0.012)
    # shallow lighter rim and the stone quay along the land side of the cove
    shallow = tex("plaster", shallow_c, 1.5)
    n = len(pts)
    built = []
    for k in range(n):
        p0, p1 = pts[k], pts[(k + 1) % n]
        _, c0 = clamp_hex((p0[0] * 1.03, p0[1] * 1.03), HEX_R)
        _, c1 = clamp_hex((p1[0] * 1.03, p1[1] * 1.03), HEX_R)
        built.append(not (c0 and c1))  # a stretch along the hex edge is open sea
    if joints:
        start = built.index(False)
        chains, cur = [], []
        for i in range(1, n + 1):
            k = (start + i) % n
            if built[k]:
                cur = cur or [pts[k]]
                cur.append(pts[(k + 1) % n])
            elif cur:
                chains.append(cur)
                cur = []
        for ch in chains:  # the cove runs counter-clockwise: the water lies to the left of each chain
            _strip(ch, 0.05, -0.005, 0.045, quay)
            _strip(_offset(ch, 0.04), 0.025, 0.0015, 0.0265, shallow)
            if edge:  # a painted / lit line along the quay's water edge (the late-era ports)
                _strip(_offset(ch, 0.018), 0.008, 0.044, 0.0475, edge)
        return cx
    for k in range(n):
        if not built[k]:
            continue
        p0, p1 = pts[k], pts[(k + 1) % n]
        beam((p0[0], p0[1], 0.02), (p1[0], p1[1], 0.02), 0.05, quay)
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        dx, dy = mx - cx, my
        dl = math.hypot(dx, dy)
        q0 = (p0[0] - dx / dl * 0.04, p0[1] - dy / dl * 0.04, 0.014)
        q1 = (p1[0] - dx / dl * 0.04, p1[1] - dy / dl * 0.04, 0.014)
        beam(q0, q1, 0.025, shallow)
    return cx


def _miters(ch):
    """Per point of an open 2D polyline: the left miter direction scaled so that offsetting by it times d keeps both
    neighbouring segments at distance d."""
    segs = []
    for (a, b) in zip(ch, ch[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        segs.append((-dy / ln, dx / ln))
    out = []
    for i in range(len(ch)):
        ns = [segs[j] for j in (i - 1, i) if 0 <= j < len(segs)]
        mx, my = sum(v[0] for v in ns), sum(v[1] for v in ns)
        ml = math.hypot(mx, my)
        mx, my = mx / ml, my / ml
        k = 1.0 / max(0.5, mx * ns[0][0] + my * ns[0][1])
        out.append((mx * k, my * k))
    return out


def _offset(ch, d):
    """The polyline moved d to its left (mitred)."""
    return [(p[0] + m[0] * d, p[1] + m[1] * d) for p, m in zip(ch, _miters(ch))]


def _strip(ch, w, z0, z1, mt):
    """A kerb of width w from z0 to z1 along an open polyline: mitred top and sides, square ends, no bottom."""
    ms = _miters(ch)
    vs = []
    for p, m in zip(ch, ms):
        for sd in (1, -1):
            for z in (z0, z1):
                vs.append((p[0] + m[0] * sd * w / 2, p[1] + m[1] * sd * w / 2, z))
    # per point i: 4i = left bottom, 4i+1 left top, 4i+2 right bottom, 4i+3 right top
    fs = []
    for i in range(len(ch) - 1):
        a, b = 4 * i, 4 * (i + 1)
        fs += [(a + 1, a + 3, b + 3, b + 1), (a, a + 1, b + 1, b), (a + 2, b + 2, b + 3, a + 3)]
    e = 4 * (len(ch) - 1)
    fs += [(0, 2, 3, 1), (e, e + 1, e + 3, e + 2)]
    o = mesh_obj(vs, fs, mt)
    top = o.data.polygons[0]
    if top.normal.z < 0:  # an open shell: make sure the faces point out (the top up)
        for p_ in o.data.polygons:
            p_.flip()
    return o


def harbour_tower():
    """Round stone harbour tower (the sea-wall towers of reference frame 1): a battered foot, a corbelled
    crenellated top, a lantern glowing for the boats under a slate cone with a gold finial, a door and lit slits
    toward the quay."""
    st = stone(ev.STONE, 1.4)
    sd = stone(STONE_D, 1.4)
    lathe([(0.078, 0.0), (0.068, 0.035), (0.06, 0.33)], (sd, st), 10)
    lathe([(0.06, 0.33), (0.076, 0.355), (0.076, 0.38)], (sd, sd), 10, top=sd)
    for k in range(6):  # merlons round the parapet
        a = math.tau * k / 6 + math.pi / 6
        bx((0.022, 0.034, 0.032), (math.cos(a) * 0.064, math.sin(a) * 0.064, 0.396), st, a, bev=0)
    iron = flat("iron", IRON, 0.5)
    for k in range(4):  # lantern room: posts round a glowing lamp
        a = math.tau * k / 4 + math.pi / 4
        tube((math.cos(a) * 0.032, math.sin(a) * 0.032, 0.38), (math.cos(a) * 0.032, math.sin(a) * 0.032, 0.44), 0.004,
             iron, n=3)
    lathe([(0.024, 0.385), (0.024, 0.435)], (glow("beacon", "#ffcf6b", 3.0),), 6)
    lathe([(0.05, 0.438), (0.0, 0.52)], (tex("roof", SLATE_N, 2.0),), 8, bottom=flat("eave", ev.ROOF_TRIM, 0.8))
    spike((0.0, 0.0, 0.515), (0.0, 0.0, 0.55), 0.007, flat("gold", GOLD, 0.35), 4)
    def fy(z, off):
        """y of a point `off` in front of the battered −Y face of the 10-gon shaft at height z (z >= 0.035)."""
        return -((0.068 - 0.008 * (z - 0.035) / 0.295) * math.cos(math.pi / 10) + off)
    # door on the top of the batter: a pale stone surround round a pointed plank door, both on the sloping face
    for (hw, z0, z1, zp, off, m_) in ((0.02, 0.035, 0.108, 0.128, 0.002, flat("door_surround", "#c8c0b0", 0.85)),
                                      (0.016, 0.035, 0.1, 0.116, 0.0035, planks("#4a2d17", 0.014, 0.3))):
        mesh_obj([(-hw, fy(z0, off), z0), (hw, fy(z0, off), z0), (hw, fy(z1, off), z1), (0.0, fy(zp, off), zp),
                  (-hw, fy(z1, off), z1)], [(0, 1, 2, 3, 4)], m_)
    lit = ev.win_lit()
    for z in (0.19, 0.27):
        mesh_obj([(-0.009, fy(z, 0.002), z), (0.009, fy(z, 0.002), z), (0.009, fy(z + 0.035, 0.002), z + 0.035),
                  (-0.009, fy(z + 0.035, 0.002), z + 0.035)], [(0, 1, 2, 3)], lit)


def warehouse():
    """Harbour warehouse of the reference towns: a stone ground floor with a blue double loading door, a jettied
    half-timbered loft with lit windows and blue shutters, a coursed slate roof, a hoist beam out of the gable over
    the water with a pulley and a sack."""
    w, d, h0, h1 = 0.38, 0.26, 0.12, 0.1
    rope = flat("rope", "#e8dcc0", 0.8)
    bx((w + 0.02, d + 0.02, 0.03), (0, 0, 0.015), stone(STONE_D, 1.2), bev=0)
    bx((w, d, h0), (0, 0, h0 / 2), stone(ev.STONE, 1.4), bev=0)
    W1, D1 = w + 0.024, d + 0.024
    bx((W1 + 0.008, D1 + 0.008, 0.016), (0, 0, h0 + 0.008), flat("timber", ev.TIMBER, 0.85), bev=0)  # jetty beam
    pm = tex("plaster", ev.PLASTER, 1.5)
    z0, z1 = h0 + 0.016, h0 + 0.016 + h1
    bx((W1, D1, h1), (0, 0, (z0 + z1) / 2), pm, bev=0)
    wins = {0: [-0.1, 0.1], 2: [0.0], 3: [0.0]}
    zw = ev.timber_walls(W1, D1, z0, z1, wins, None, rail=0.32, posts="strip")
    for f, us in wins.items():
        a = f * math.pi / 2
        dist = (D1 if f % 2 == 0 else W1) / 2 + 0.006
        for u in us:
            ev.shutter_window(math.sin(a) * dist + math.cos(a) * u, -math.cos(a) * dist + math.sin(a) * u, zw, a,
                              TRIM_BLUE, shutters=(f == 0))
    # loading door: two blue plank leaves in a dark frame under a timber lintel
    fr = flat("frame" + ev.TIMBER, ev.TIMBER, 0.85)
    bx((0.13, 0.008, 0.115), (-0.04, -d / 2 - 0.002, 0.0575), fr, bev=0)
    for sx in (-1, 1):
        bx((0.054, 0.012, 0.1), (-0.04 + sx * 0.029, -d / 2 - 0.005, 0.05), planks(TRIM_BLUE, 0.016, 0.3), bev=0)
    bx((0.14, 0.016, 0.016), (-0.04, -d / 2 - 0.006, 0.112), fr, bev=0)
    ev.gable_roof(W1, D1, 0.15, (0, 0, z1), SLATE_N, pm, n=4, eave_z=0.0)
    # hoist beam out of the +X gable with a pulley, a rope and a sack
    beam((W1 / 2 - 0.02, 0, z1 + 0.05), (W1 / 2 + 0.1, 0, z1 + 0.05), 0.022, tex("wood", WOOD_D, 2.0))
    bx((0.06, 0.012, 0.07), (W1 / 2 + 0.003, 0, z0 + 0.045), flat("loft", "#2b2420", 0.9), math.pi / 2, bev=0)
    tube((W1 / 2 + 0.09, 0, z1 + 0.04), (W1 / 2 + 0.09, 0, 0.1), 0.0045, rope, n=3)
    sack(W1 / 2 + 0.09, 0, 0.8, 0, z=0.04)


def fish_stall():
    """Quay stall facing −Y: four posts, a counter with the catch and a basket, a red-and-cream striped awning."""
    wd = tex("wood", "#6a4327", 2.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tube((sx * 0.075, sy * 0.04, -0.005), (sx * 0.075, sy * 0.04, 0.13 + (0.025 if sy > 0 else 0.0)), 0.008, wd,
                 n=4)
    bx((0.16, 0.07, 0.05), (0, 0, 0.025), tex("wood", "#8a6440", 3.0), bev=0)
    mesh_obj([(-0.07, -0.03, 0.051), (0.07, -0.03, 0.051), (0.07, 0.03, 0.051), (-0.07, 0.03, 0.051)], [(0, 1, 2, 3)],
             flat("ice", "#cfd8dc", 0.4))
    fish = flat("fish", "#a9b8c2", 0.4)
    for i in range(4):  # the catch laid on the counter
        x = -0.05 + i * 0.033
        mesh_obj([(x - 0.012, -0.018, 0.053), (x + 0.008, -0.022, 0.053), (x + 0.014, 0.0, 0.053),
                  (x + 0.008, 0.02, 0.053), (x - 0.012, 0.016, 0.053), (x - 0.004, 0.0, 0.053)],
                 [(0, 1, 2, 3, 4, 5)], fish)
    tube((0.11, -0.02, -0.005), (0.11, -0.02, 0.04), 0.022, tex("wood", STRAW, 4.0), r2=0.026, n=6, cap=True)
    stripes = (flat("awn_red", "#b8352c", 0.7), flat("awn_cream", "#efe7d2", 0.7))
    for k in range(5):
        x0, x1 = -0.095 + k * 0.038, -0.095 + (k + 1) * 0.038
        mesh_obj([(x0, 0.05, 0.158), (x1, 0.05, 0.158), (x1, -0.075, 0.122), (x0, -0.075, 0.122)], [(0, 1, 2, 3)],
                 stripes[k % 2])


def port():
    """Fishing/trade port (reference frame 1: the harbour with stone towers, wooden jetties and deep blue water): a
    deep-water cove opening at the +X edge with a stone quay, a cobbled yard, a plank pier with mooring posts and a
    lantern, a sailboat and a rowboat moored, a round harbour tower with a glowing lantern, a stone and
    half-timbered warehouse with a slate roof and a hoist, a derrick, a fish stall with a striped awning, a fish
    drying rack and heaps of nets, crates, barrels, sacks and rope coils."""
    _cove(stone("#a39b8d", 1.4), "#235b8c", "#3f8db4", joints=True)
    # cobbled quay yard on the land side
    ev.pad(0.36, stone("#a89c86", 2.2), 0.008, 12, 0.08, 6, 1.0, 1.25)
    # ---- pier from the quay to the +X edge
    post = tex("wood", "#5a3e27", 2.0)
    py, pw, z = -0.03, 0.15, 0.075
    x0, x1 = 0.02, 0.79
    n = 17
    # boards across the pier: one plank row per board (its own tone and grain along it), the seams in the gaps
    deck = planks("#a8814f", (x1 - x0) / n, 2.0, True, (1.0, -x0))
    for sy in (-1, 1):
        beam((x0, py + sy * 0.05, z - 0.02), (x1, py + sy * 0.05, z - 0.02), 0.02, post)
    for i in range(n):
        x = x0 + (i + 0.5) / n * (x1 - x0)
        bx((((x1 - x0) / n) - 0.006, pw + (0.012 if i % 3 == 0 else 0.0), 0.014), (x, py, z), deck, bev=0)
    rope = flat("rope", "#e8dcc0", 0.8)
    for i in range(5):  # mooring posts with rope lashings
        x = 0.22 + i * 0.14
        for sy in (-1, 1):
            hh = 0.13 + (0.02 if i == 4 else 0.0)
            tube((x, py + sy * 0.085, 0.0), (x, py + sy * 0.085, hh), 0.015, post, n=6, cap=True)
            tube((x, py + sy * 0.085, hh - 0.04), (x, py + sy * 0.085, hh - 0.025), 0.0165, rope, n=6)
    rope_coil(0.5, py + 0.03, 0.026, z + 0.007)
    crate(0.36, py - 0.025, 0.05, 0.25, z=z + 0.007)
    barrel(0.68, py - 0.025, 0.022, 0.05, z=z + 0.007)
    # lantern post at the pier end
    cy(0.007, 0.2, (0.76, py - 0.06, z + 0.1), post, 5)
    bx((0.04, 0.008, 0.008), (0.745, py - 0.06, z + 0.19), post, bev=0)
    bx((0.022, 0.022, 0.03), (0.73, py - 0.06, z + 0.165), glow("lantern", "#ffcf6b", 2.5), bev=0)
    cn(0.018, 0.014, (0.73, py - 0.06, z + 0.187), flat("iron", IRON, 0.5), 4, rot=(0, 0, math.pi / 4))
    # ---- moored boats: sailboat on the +Y side of the pier, rowboat on the −Y side
    build_at(sailboat, 0.44, 0.17, 0.04, z=0.004)
    build_at(rowboat, 0.5, -0.27, -0.1, z=0.004)
    tube((0.36, py + 0.085, 0.11), (0.3, 0.12, 0.07), 0.0045, rope, n=3)
    tube((0.5, py - 0.085, 0.11), (0.42, -0.25, 0.05), 0.0045, rope, n=3)
    # ---- warehouse, harbour tower, derrick
    build_at(warehouse, -0.36, 0.32, -0.1)
    build_at(harbour_tower, 0.27, 0.6)
    build_at(crane, 0.06, 0.42, 0.15)
    # ---- cargo on the quay
    crate(-0.03, -0.2, 0.07, 0.2)
    crate(0.05, -0.25, 0.06, -0.3)
    crate(-0.02, -0.21, 0.05, 0.6, z=0.07)
    for (x, y) in ((-0.12, -0.12), (-0.08, -0.05), (-0.15, -0.04)):
        barrel(x, y)
    barrel(-0.09, -0.1, z=0.085, r=0.03, h=0.075)
    barrel(0.0, 0.1, lie=1.2)
    rope_coil(-0.02, 0.2, 0.032)
    sack(0.06, 0.3, 1.0, 0.3)
    sack(0.0, 0.33, 0.9, -0.2)
    # ---- fish stall on the yard, fish drying rack and heaps of nets (front left)
    build_at(fish_stall, -0.2, -0.36, 0.1)
    def fish_rack():
        wd = tex("wood", "#6a4327", 2.5)
        for sx in (-1, 1):
            tube((sx * 0.12, -0.03, 0.0), (sx * 0.12, 0.0, 0.17), 0.008, wd, n=4)
            tube((sx * 0.12, 0.03, 0.0), (sx * 0.12, 0.0, 0.17), 0.008, wd, n=4)
        tube((-0.13, 0, 0.165), (0.13, 0, 0.165), 0.006, wd, n=4)
        fish = flat("fish", "#a9b8c2", 0.4)
        for i in range(6):
            x = -0.09 + i * 0.036
            ico(0.014, (x, 0, 0.125), fish, (0.6, 0.35, 2.2))
            spike((x, 0, 0.098), (x, 0, 0.08), 0.011, fish, 4)
        net = flat("net", "#5d6b5a", 0.9)
        ico(0.06, (0.02, 0.09, 0.0), net, (1.2, 0.9, 0.35))
        ico(0.045, (-0.09, 0.1, 0.0), flat("net2", "#7a6a4a", 0.9), (1.1, 1.0, 0.4))
        torus(0.03, 0.006, (0.02, 0.09, 0.022), flat("float", "#d9962a", 0.6), seg=6, mseg=3)
    build_at(fish_rack, -0.47, -0.3, 0.35)
    # a boat turned keel-up on trestles for caulking, a tar pot beside it (front left, on the grass)
    def boat_repair():
        wd = tex("wood", "#6a4327", 2.5)
        for x in (-0.06, 0.06):
            for sy in (-1, 1):
                tube((x, sy * 0.045, -0.005), (x, 0.0, 0.05), 0.005, wd, n=4)
        build_at(lambda: hull(0.24, 0.1, 0.045, tex("wood", "#8a6440", 3.0), tex("wood", "#5e4126", 3.0),
                              flat("trim_blue", TRIM_BLUE, 0.6)), 0.0, 0.0, 0.0, tilt=(math.pi, 0.0), z=0.1)
        beam((-0.1, 0.0, 0.104), (0.105, 0.0, 0.104), 0.012, tex("wood", "#4a2f19", 2.0))  # the keel, upward
        lathe([(0.016, 0.0), (0.019, 0.03)], (flat("tarpot", "#2b2a2c", 0.5),), 6, top=flat("tar", "#141210", 0.4),
              loc=(0.0, -0.09, 0.0))
    build_at(boat_repair, -0.4, -0.52, 0.25)
    # mooring bollards on the quay edge
    for (x, y) in ((0.15, -0.34), (0.12, 0.3)):
        lathe([(0.02, 0.0), (0.016, 0.05), (0.024, 0.065), (0.0, 0.075)], (post, post, post), 6, loc=(x, y, 0.0))


# ------------------------------------------------------------------ military base


def dummy(x, y, rz=0.0):
    """Straw training dummy on a post with a cross arm and a sack head."""
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        straw = tex("wood", STRAW, 4.0)
        for a in (0, math.pi / 2):
            tube((math.cos(a) * -0.045, math.sin(a) * -0.045, 0.008), (math.cos(a) * 0.045, math.sin(a) * 0.045, 0.008),
                 0.008, wd, n=4)
        tube((0, 0, 0.0), (0, 0, 0.17), 0.008, wd, n=5)
        uvs(0.035, (0, 0, 0.115), straw, 6, 4, (1.0, 0.8, 1.35))
        tube((-0.06, 0, 0.14), (0.06, 0, 0.14), 0.007, wd, n=4)
        for sx in (-1, 1):
            spike((sx * 0.055, 0, 0.14), (sx * 0.085, 0, 0.14), 0.014, straw, 5)
        ico(0.024, (0, 0, 0.185), tex("plaster", "#c9b48a", 3.0), (1, 1, 1.05))
        mesh_obj([(-0.014, -0.0245, 0.193), (0.014, -0.0245, 0.193), (0.014, -0.0235, 0.186), (-0.014, -0.0235, 0.186)],
                 [(0, 1, 2, 3)], flat("socket", "#2b2420", 0.9))
    build_at(b, x, y, rz)


def archery_target(x, y, rz=0.0):
    """Straw butt on a tripod with a painted face (white, red, white) and two arrows in it."""
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        for p0 in ((-0.05, 0.03, 0.0), (0.05, 0.03, 0.0), (0.0, 0.07, 0.0)):
            tube(p0, (0.0, 0.0, 0.16), 0.007, wd, n=4)
        t = 0.2
        ax = Vector((0.0, -math.cos(t), math.sin(t)))  # the face normal, leaning back by t
        c0 = Vector((0.0, -0.01, 0.1))
        tube(tuple(c0 - ax * 0.013), tuple(c0 + ax * 0.013), 0.06, tex("wood", STRAW, 4.0), n=10, cap=True)
        u = Vector((1, 0, 0))
        v = ax.cross(u)
        for k, (r, c) in enumerate(((0.046, "#efe9da"), (0.03, "#b8352c"), (0.013, "#efe9da"))):
            cc = c0 + ax * (0.0135 + 0.001 * k)
            mesh_obj([tuple(cc + (u * math.cos(math.tau * i / 10) + v * math.sin(math.tau * i / 10)) * r)
                      for i in range(10)], [tuple(range(10))], flat("tgt_" + c, c, 0.7))
        ar = flat("arrow", "#d8c49a", 0.8)
        for dx, dz in ((0.012, 0.01), (-0.02, -0.015)):
            tube((dx, -0.02, 0.1 + dz), (dx + 0.01, -0.08, 0.1 + dz + 0.012), 0.0045, ar, n=3)
    build_at(b, x, y, rz)


def tower_sq(x, y, w, h, st, cap, roof, slit=None, lit=None, front_y=None):
    """Square stone tower: a corbelled parapet, four corner merlons and a pyramid slate roof inside them; a dark
    arrow slit and a lit window on the −Y face."""
    bx((w, w, h), (x, y, h / 2), st, bev=0)
    W2 = w + 0.024
    bx((W2, W2, 0.032), (x, y, h + 0.012), cap, bev=0)
    m = 0.036
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((m, m, 0.036), (x + sx * (W2 - m) / 2, y + sy * (W2 - m) / 2, h + 0.046), st, bev=0)
    ev._hip_roof(w - 0.012, w - 0.012, w * 1.05, (x, y, h + 0.026), roof, 0.0)
    fy = y - w / 2 - 0.002
    if slit:
        mesh_obj([(x - 0.009, fy, h * 0.38), (x + 0.009, fy, h * 0.38), (x + 0.009, fy, h * 0.55), (x - 0.009, fy, h * 0.55)],
                 [(0, 1, 2, 3)], slit)
    if lit:
        mesh_obj([(x - 0.014, fy, h * 0.68), (x + 0.014, fy, h * 0.68), (x + 0.014, fy, h * 0.86), (x - 0.014, fy, h * 0.86)],
                 [(0, 1, 2, 3)], lit)


def hanging_banner(x, y, z_top, w, h, cloth, em, rod_m):
    """A long banner hanging down a wall facing −Y: a rod, a swallow-tailed cloth, a shield emblem."""
    tube((x - w / 2 - 0.012, y - 0.006, z_top + 0.004), (x + w / 2 + 0.012, y - 0.006, z_top + 0.004), 0.0065, rod_m,
         n=4)
    mesh_obj([(x - w / 2, y, z_top), (x + w / 2, y, z_top), (x + w / 2, y, z_top - h), (x, y, z_top - h * 0.82),
              (x - w / 2, y, z_top - h)], [(0, 1, 2, 3, 4)], cloth)
    mesh_obj([(x + u * w * 0.62, y - 0.002, z_top - h * 0.36 + v * w * 0.72) for u, v in HEATER], [tuple(range(5))], em)


def military_base():
    """Early garrison (reference frames 1 and 4: stone gate towers with arched gates, banners on the towers, warm
    windows): a stone-walled square with a gatehouse of two square towers joined by an arch (crenels, slate pyramid
    roofs, open timber doors, banners), slate-roofed corner towers, a stone barracks with lit windows and a smoking
    chimney, a row of soldier tents, a training yard with straw dummies and an archery target, weapon racks, guards
    at the gate, a neutral white banner."""
    S = 0.55
    # ---- ground: packed earth inside, sand yard, gravel path from the gate
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], tex("plaster", "#a58a62", 1.5), 0.006)
    ground_poly([(0.06, -0.5), (0.5, -0.5), (0.5, -0.06), (0.06, -0.06)], tex("plaster", "#cdb482", 2.0), 0.012)
    ground_poly([(-0.07, -0.66), (0.03, -0.66), (0.03, 0.05), (-0.07, 0.05)], stone("#b9ad97", 2.2), 0.01)
    # ---- low stone walls with a coping and merlons between the towers
    st = stone(STONE, 1.3)
    sd = stone(STONE_D, 1.3)
    slate = tex("roof", SLATE_N, 1.6)
    lit = ev.win_lit()
    slit_m = flat("slit", "#2a2420", 0.9)
    H, T = 0.11, 0.05
    gate, gx0 = 0.1, -0.02
    TS = 0.13  # gate tower
    xl, xr = gx0 - gate - TS, gx0 + gate + TS  # outer faces of the gate towers
    segs = [((-S, S), (S, S)), ((S, -S), (S, S)), ((-S, -S), (-S, S)), ((-S, -S), (xl, -S)), ((xr, -S), (S, -S))]
    for (a, b) in segs:
        L = math.dist(a, b)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        bx((L, T, H), (mx, my, H / 2), st, ang, bev=0)
        bx((L + 0.01, T + 0.016, 0.022), (mx, my, H + 0.011), sd, ang, bev=0)
        nb = int((L - 0.1) / 0.14)
        for i in range(nb):  # little merlons, clear of the towers at the ends
            f = (0.05 + (i + 0.5) * (L - 0.1) / nb) / L
            bx((0.05, T + 0.004, 0.03), (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, H + 0.036), st, ang, bev=0)
    for sx in (-1, 1):  # corner towers with slate roofs (set in a little: the model stays within its radius)
        for sy in (-1, 1):
            tower_sq(sx * (S - 0.02), sy * (S - 0.02), 0.11, 0.23, st, sd, slate, slit_m if sy < 0 else None)
    # ---- gatehouse: two towers, an arched bridge with crenels, open plank doors, banners
    for x in (gx0 - gate - TS / 2, gx0 + gate + TS / 2):
        tower_sq(x, -S, TS, 0.3, st, sd, slate)
    bz0, bz1 = 0.19, 0.27
    bx((2 * gate, 0.074, bz1 - bz0), (gx0, -S, (bz0 + bz1) / 2), st, bev=0)
    bx((2 * gate + 0.01, 0.09, 0.02), (gx0, -S, bz1 + 0.01), sd, bev=0)
    for i in range(3):
        bx((0.04, 0.074, 0.032), (gx0 - 0.07 + i * 0.07, -S, bz1 + 0.036), st, bev=0)
    for (m_, hw, z0, z1, dy) in ((flat("win_frame", "#3a2a1e", 0.8), 0.02, 0.205, 0.262, 0.002), (lit, 0.013, 0.211, 0.256,
                                                                                               0.004)):
        mesh_obj([(gx0 - hw, -S - 0.037 - dy, z0), (gx0 + hw, -S - 0.037 - dy, z0), (gx0 + hw, -S - 0.037 - dy, z1),
                  (gx0 - hw, -S - 0.037 - dy, z1)], [(0, 1, 2, 3)], m_)  # a lit window over the arch
    zs = bz0 - gate  # arch springing: a semicircle of radius `gate` closing under the bridge
    arc = [(gx0 + gate * math.cos(math.pi * k / 8), zs + gate * math.sin(math.pi * k / 8)) for k in range(9)]
    for yy in (-S - 0.038, -S + 0.038):  # the spandrels either side of the arch, front and back
        for corner, half in (((gx0 + gate, bz0), arc[0:5]), ((gx0 - gate, bz0), arc[4:9])):
            pts = [corner] + half
            mesh_obj([(x, yy, z) for x, z in pts], [tuple(range(len(pts)))], st)
    intr = [(x, y_, z) for x, z in arc for y_ in (-S - 0.038, -S + 0.038)]
    mesh_obj(intr, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(8)], sd)  # the arch's underside
    door = planks("#7a5232", 0.016, 0.3)
    band = flat("door_band", IRON, 0.5)
    for sx in (-1, 1):  # leaves swung half open into the yard: their planks and iron bands show through the arch
        hx = gx0 + sx * gate
        a = math.radians(45)
        cxl, cyl = hx - sx * math.cos(a) * gate * 0.48, -S + 0.03 + math.sin(a) * gate * 0.48
        bx((gate * 0.96, 0.014, 0.17), (cxl, cyl, 0.085), door, -sx * a, bev=0)
        for zb in (0.035, 0.1):  # two iron bands low enough to show under the arch
            bx((gate * 0.97, 0.018, 0.012), (cxl, cyl, zb), band, -sx * a, bev=0)
    cloth = flat("banner_white", "#ecebe6", 0.7)
    em = flat("banner_grey", "#7d838c", 0.6)
    rod_m = flat("banner_rod", GOLD, 0.4)
    for x in (gx0 - gate - TS / 2, gx0 + gate + TS / 2):
        hanging_banner(x, -S - TS / 2 - 0.006, 0.27, 0.07, 0.14, cloth, em, rod_m)
    iron = flat("iron", IRON, 0.5)
    for sx in (-1, 1):  # lanterns on brackets either side of the arch (the lit gate of reference frame 4)
        x = gx0 + sx * (gate + 0.022)
        tube((x, -S - 0.065, 0.165), (x, -S - 0.092, 0.165), 0.004, iron, n=3)
        bx((0.018, 0.018, 0.024), (x, -S - 0.092, 0.15), ev.glow("gate_lamp", "#ffcf6b", 2.5), bev=0)
        spike((x, -S - 0.092, 0.161), (x, -S - 0.092, 0.178), 0.014, iron, 4)
    # ---- barracks along the back wall: stone walls, slate roof, lit windows, a door with a hood, a chimney
    def barracks():
        w, d, h = 0.5, 0.2, 0.13
        bx((w + 0.02, d + 0.02, 0.025), (0, 0, 0.0125), sd, bev=0)
        bx((w, d, h), (0, 0, h / 2), stone("#b3aa9a", 1.6), bev=0)
        bx((w + 0.008, d + 0.008, 0.016), (0, 0, h - 0.008), tex("wood", WOOD_D, 2.0), bev=0)  # timber wall plate
        prism_roof("roof", w, d, 0.12, (0, 0, h - 0.005), slate, overhang=0.04)
        bx((w + 0.1, 0.03, 0.025), (0, 0, h + 0.115), tex("wood", "#4f3a28", 2.0), bev=0)
        mesh_obj([(-0.032, -d / 2 - 0.002, 0.0), (0.032, -d / 2 - 0.002, 0.0), (0.032, -d / 2 - 0.002, 0.1),
                  (-0.032, -d / 2 - 0.002, 0.1)], [(0, 1, 2, 3)], planks("#4a2f19", 0.014, 0.3))
        bx((0.09, 0.05, 0.012), (0, -d / 2 - 0.03, 0.11), tex("wood", "#6d5640", 2.0), bev=0, rot=(0.3, 0, 0))
        fr = flat("win_frame", "#3a2a1e", 0.8)
        for x in (-0.18, -0.09, 0.09, 0.18):
            for (yy, m_, hw, z0, z1) in ((-d / 2 - 0.002, fr, 0.022, 0.058, 0.108), (-d / 2 - 0.004, lit, 0.015, 0.064,
                                                                                       0.102)):
                mesh_obj([(x - hw, yy, z0), (x + hw, yy, z0), (x + hw, yy, z1), (x - hw, yy, z1)], [(0, 1, 2, 3)], m_)
        for sx in (-1, 1):
            mesh_obj([(sx * (w / 2 + 0.003), y_, z) for y_, z in ((-0.016, 0.064), (0.016, 0.064), (0.016, 0.102),
                                                                   (-0.016, 0.102))], [(0, 1, 2, 3)], lit)
        cy(0.026, 0.11, (0.16, 0.04, h + 0.09), stone(STONE_D), 6)
        cy(0.031, 0.016, (0.16, 0.04, h + 0.15), sd, 6)
        bpy.ops.object.empty_add(location=(0.16, 0.04, h + 0.17))
        bpy.context.active_object.name = "smoke_barracks"
    build_at(barracks, 0.1, 0.34)
    # ---- row of soldier tents on the left, opening toward the parade ground (+X)
    canvas = tex("plaster", CANVAS_W, 2.0)
    stripe = flat("tent_stripe", "#4f6688", 0.8)
    for y in (-0.33, -0.1, 0.13):
        build_at(lambda: (ridge_tent(0.19, 0.15, 0.16, canvas, (), True, True,
                                     stripes=((-0.3, 0.028, stripe), (0.3, 0.028, stripe))),
                          beam((0, -0.1, 0.163), (0, 0.1, 0.163), 0.016, flat("ridge_grey", "#7d8086", 0.7)),
                          bx((0.155, 0.2, 0.012), (0, 0, 0.006), tex("plaster", "#7d6a50", 1.5), bev=0)),
                 -0.37, y, math.pi / 2)
    # ---- flagpole with a neutral white banner on a stone base
    fx, fy = -0.12, 0.06
    cy(0.05, 0.04, (fx, fy, 0.02), sd, 8)
    cy(0.035, 0.03, (fx, fy, 0.055), st, 8)
    ta.neutral_flag(fx, fy, 0.9, 0.2)
    # ---- training yard: dummies, archery target, weapon racks
    dummy(0.2, -0.22, 0.2)
    dummy(0.36, -0.36, -0.3)
    dummy(0.2, -0.4, 0.1)
    archery_target(0.44, -0.14, math.pi / 2 + 0.3)
    weapon_rack(0.44, 0.1, math.pi / 2, 4, 2, "#8a8f96")
    weapon_rack(-0.18, -0.28, math.pi / 2, 3, 1, "#8a8f96", 1)
    # ---- smithy lean-to against the back wall: a slate pent roof on posts, a glowing forge, an anvil, a quench tub
    def smithy():
        wdk = tex("wood", WOOD_D, 2.0)
        for sx in (-1, 1):
            tube((sx * 0.065, 0.0, -0.01), (sx * 0.065, 0.0, 0.14), 0.008, wdk, n=4)
        bx((0.16, 0.13, 0.012), (0.0, 0.06, 0.155), tex("wood", "#7a5a3a", 2.5), bev=0, rot=(-0.25, 0, 0))  # pent roof
        bx((0.08, 0.06, 0.05), (-0.02, -0.04, 0.025), stone(STONE_D, 1.6), bev=0)  # hearth
        mesh_obj([(-0.052, -0.062, 0.051), (0.012, -0.062, 0.051), (0.012, -0.018, 0.051), (-0.052, -0.018, 0.051)],
                 [(0, 1, 2, 3)], ev.glow("forge", "#ff7a1e", 3.0))
        bx((0.034, 0.03, 0.12), (-0.02, -0.01, 0.13), stone(STONE_D, 1.6), bev=0)  # flue up through the roof
        tube((0.05, -0.1, -0.005), (0.05, -0.1, 0.04), 0.014, tex("wood", "#7a5232", 3.0), n=6, cap=True)
        bx((0.034, 0.014, 0.014), (0.05, -0.1, 0.047), iron, bev=0)  # anvil on a stump
        spike((0.067, -0.1, 0.047), (0.082, -0.1, 0.05), 0.007, iron, 4)
    build_at(smithy, 0.42, 0.42)
    barrel(0.49, 0.29, 0.026, 0.05, c="#6e4c30")
    # ---- supplies: crates, barrels, hay by the barracks
    crate(-0.27, 0.4, 0.06, 0.2)
    crate(-0.2, 0.44, 0.05, -0.3)
    barrel(-0.2, 0.25)
    barrel(-0.14, 0.27, r=0.03, h=0.075)
    ev.haystack(0.47, -0.45, 0.45)
    # ---- guards flanking the gate outside
    for sx in (-1, 1):
        gx_, gy_ = gx0 + sx * 0.235, -S - 0.1
        hands = build_at(lambda: ta.man("#8d9096", "#5a4f45", "idle", "helmet", 1.15), gx_, gy_, 0.0)
        hx, hy, hz = hands[0 if sx < 0 else 1]
        spear((gx_ + hx, gy_ + hy, 0.0), (gx_ + hx, gy_ + hy, 0.2), tex("wood", "#9a7046", 3.0), flat("iron", IRON, 0.5))


# the white displayed eagle of the reference sails (frame 1): head up, wings raised with two feather tips each,
# forked tail — an outline in a unit box (u right, v up); glTF draws it double-sided
EAGLE_SAIL = [(0.0, 0.5), (0.07, 0.4), (0.12, 0.3), (0.5, 0.5), (0.4, 0.32), (0.49, 0.28), (0.36, 0.14), (0.44, 0.1),
              (0.15, -0.02), (0.22, -0.5), (0.0, -0.34), (-0.22, -0.5), (-0.15, -0.02), (-0.44, 0.1), (-0.36, 0.14),
              (-0.49, 0.28), (-0.4, 0.32), (-0.5, 0.5), (-0.12, 0.3), (-0.07, 0.4)]
HEATER = [(-0.5, 0.5), (0.5, 0.5), (0.5, 0.05), (0.0, -0.5), (-0.5, 0.05)]


def emblem_yz(x, y, z, w, h, mt, pts=EAGLE_SAIL):
    """Flat one-polygon emblem w × h centred at (x, y, z) in a plane facing ±X."""
    return mesh_obj([(x, y + u * w, z + v * h) for u, v in pts], [tuple(range(len(pts)))], mt)


def square_sail(mx, zt, zb, wt, wb, belly, cloth, em=None, yard=None):
    """Square sail hung from a yard at zt in front (+X) of a mast at x = mx, its belly blown toward the bow: a 3×3
    grid whose middle panel is flat, so the white emblem lies on it — once on each face. wt / wb: head / foot width."""
    us, su = (0.0, 0.16, 0.84, 1.0), (0.0, 1.0, 1.0, 0.0)
    vs, tv = (0.0, 0.16, 0.84, 1.0), (0.6, 1.0, 1.0, 0.1)
    x0 = mx + 0.017
    verts = []
    for j, v in enumerate(vs):
        hw = (wb + (wt - wb) * v) / 2
        for i, u in enumerate(us):
            verts.append((x0 + belly * su[i] * tv[j], -hw + 2 * hw * u, zb + (zt - zb) * v))
    faces = [(j * 4 + i, j * 4 + i + 1, (j + 1) * 4 + i + 1, (j + 1) * 4 + i) for j in range(3) for i in range(3)]
    o = mesh_obj(verts, faces, cloth)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    if em:
        ew, eh = 0.64 * min(wt, wb), 0.62 * (zt - zb)
        for dx in (0.003, -0.003):
            emblem_yz(x0 + belly + dx, 0.0, (zt + zb) / 2, ew, eh, em)
    if yard:
        tube((x0 - 0.003, -wt / 2 - 0.02, zt + 0.004), (x0 - 0.003, wt / 2 + 0.02, zt + 0.004), 0.0075, yard, n=5)
    return o


# stations of the cog's hull from the transom (t = 0) to the stem (t = 1): half-beam factor, gunwale height, keel z
_COG_T = (0.0, 0.14, 0.38, 0.6, 0.78, 0.91, 1.0)
_COG_W = (0.8, 0.96, 1.0, 0.98, 0.84, 0.55, 0.0)
_COG_SH = (0.155, 0.13, 0.114, 0.112, 0.12, 0.142, 0.168)
_COG_K = (0.03, 0.006, 0.0, 0.0, 0.006, 0.03, 0.075)


def _cog_at(L, W, x):
    """Half-beam (at the gunwale) and gunwale height of the cog hull at x (linear between stations)."""
    t = min(max((x + L / 2) / L, 0.0), 1.0)
    for i in range(len(_COG_T) - 1):
        if t <= _COG_T[i + 1]:
            f = (t - _COG_T[i]) / (_COG_T[i + 1] - _COG_T[i])
            w = (_COG_W[i] + (_COG_W[i + 1] - _COG_W[i]) * f) * W / 2
            return w * 0.95, _COG_SH[i] + (_COG_SH[i + 1] - _COG_SH[i]) * f
    return 0.0, _COG_SH[-1]


def cog_hull(L, W, bands, transom, deck, deck_z=0.078):
    """Round-bellied cog hull along X (bow at +X), open-topped shell with a raked stem and transom, a sheer that
    rises fore and aft, and horizontal colour bands (tarred bottom, planking, a dark wale, lighter upper strakes,
    a pale rail cap) — `bands` = 5 materials from the keel up. A planked deck inside at deck_z."""
    n = len(_COG_T)
    rows = []  # rows[i] = [(x, y, z) ...] of one side's profile from the keel to the gunwale (y >= 0)
    for i, t in enumerate(_COG_T):
        w = _COG_W[i] * W / 2
        sh, kz = _COG_SH[i], _COG_K[i]
        prof = [(0.0, kz), (0.9 * w, 0.05), (w, sh - 0.036), (0.995 * w, sh - 0.024), (0.96 * w, sh - 0.009),
                (0.95 * w, sh)]
        out, zp = [], -1.0
        for y, z in prof:
            z = max(z, zp + 0.006)
            zp = z
            f = (z - prof[0][1]) / max(sh - prof[0][1], 1e-6)
            rake = 0.06 * f if i == n - 1 else (-0.025 * f if i == 0 else 0.0)
            out.append((-L / 2 + t * L + rake, y, z))
        rows.append(out)
    verts, idx = [], {}

    def vid(p):
        k = tuple(round(c, 6) for c in p)
        if k not in idx:
            idx[k] = len(verts)
            verts.append(p)
        return idx[k]
    band_faces = [[] for _ in range(5)]
    for sy in (1, -1):
        for i in range(n - 1):
            for k in range(5):
                a, b = rows[i][k], rows[i][k + 1]
                c, d = rows[i + 1][k + 1], rows[i + 1][k]
                q = [vid((p[0], sy * p[1], p[2])) for p in (a, b, c, d)]
                q = list(dict.fromkeys(q))
                if len(q) >= 3:
                    band_faces[k].append(tuple(q))
    for k in range(5):
        used = sorted({v for f in band_faces[k] for v in f})
        remap = {v: i for i, v in enumerate(used)}
        o = mesh_obj([verts[v] for v in used], [tuple(remap[v] for v in f) for f in band_faces[k]], bands[k])
        for p_ in o.data.polygons:
            p_.use_smooth = True
    # transom: the flat stern between the two sides
    st = rows[0]
    ring = [(p[0], p[1], p[2]) for p in reversed(st)] + [(p[0], -p[1], p[2]) for p in st[1:]]
    mesh_obj(ring, [tuple(range(len(ring)))], transom)
    # deck: the hull outline at deck height, a little inside the shell
    pts = []
    for i in range(n - 1):
        w, _ = _cog_at(L, W, -L / 2 + _COG_T[i] * L)
        pts.append((-L / 2 + _COG_T[i] * L + (0.006 if i == 0 else 0.0), 0.93 * w))
    pts.append((L / 2 - 0.01, 0.0))
    ring = pts + [(x, -y) for x, y in reversed(pts[:-1])]
    mesh_obj([(x, y, deck_z) for x, y in ring], [tuple(range(len(ring)))], deck)


def ship_castle(xa, xb, z_out, z_side, z_in, zf, zt, L, W, wall, band, floor):
    """Raised castle on the cog between its outer end xa (stern or bow) and its inner end xb (facing the waist):
    plank walls standing just inside the hull sides (the outer wall from z_out, the sides from z_side, the inner
    wall from the deck at z_in), a floor at zf and a parapet band in the team colour up to zt."""
    (wa, _), (wb, _) = _cog_at(L, W, xa), _cog_at(L, W, xb)
    ring = [(xa, wa * 0.97), (xb, wb * 0.97), (xb, -wb * 0.97), (xa, -wa * 0.97)]
    z0s = (z_side, z_in, z_side, z_out)
    for k in range(4):
        (xa_, ya_), (xb_, yb_) = ring[k], ring[(k + 1) % 4]
        for (za, zb, mt) in ((z0s[k], zf, wall), (zf, zt, band)):
            mesh_obj([(xa_, ya_, za), (xb_, yb_, za), (xb_, yb_, zb), (xa_, ya_, zb)], [(0, 1, 2, 3)], mt)
    mesh_obj([(x, y, zf) for x, y in ring], [(0, 1, 2, 3)], floor)
    return ring


def warship(team):
    """A two-masted war cog along X (bow at +X) for the open water (reference frame 1: ships under the state's
    sails with the white eagle in the bay). A round planked hull with a rising sheer, tarred bottom, dark wale and
    pale rail; raised castles fore and aft with team-coloured parapets; lit stern windows and a stern lantern; big
    bellied square sails in the team colour, each course with the white eagle on both faces; light yards, a crow's
    nest, shrouds and stays, team pennants and a stern ensign; shields hung along the waist; cargo on the deck.
    The game spins it so the bow or the stern faces the camera — the sails and both castles read face-on."""
    L, W = 0.62, 0.2
    wood = planks("#9c6230", 0.0135)
    upper = planks("#bd8446", 0.0115)
    cog_hull(L, W, (flat("tar", "#2b211a", 0.8), wood, flat("wale", "#3e2615", 0.7), upper,
                    flat("rail", "#d9ad6c", 0.7)), planks("#7e4f28", 0.0135), planks("#c09060", 0.018, 0.16, True))
    teamc = flat("parapet" + team, ev.shade(team, 0.8), 0.6)
    castle_w = planks("#9c6838", 0.012)
    floor = planks("#b88a58", 0.016, 0.14, True)
    white = flat("emblem", "#f3efe6", 0.6)
    iron = flat("iron", IRON, 0.5)
    lit = ev.win_lit()
    # ---- stern castle: walls, floor, team parapet, lit windows on the stern and the sides, a door to the waist
    xs0, xs1 = -L / 2 - 0.028, -0.165
    ring = ship_castle(xs0, xs1, 0.145, 0.1, 0.078, 0.2, 0.225, L, W, castle_w, teamc, floor)
    for (x, y) in ring:  # corner merlons crenellate the castle (the war cogs' fighting tops)
        bx((0.026, 0.026, 0.028), (x - 0.013 * math.copysign(1, x - (xs0 + xs1) / 2), y - 0.013 * math.copysign(1, y),
                                   0.239), teamc, bev=0)
    frame = flat("win_frame", "#3a2414", 0.8)
    for y in (-0.042, 0.0, 0.042):  # stern gallery: three lit windows over the rudder, the castle overhanging
        mesh_obj([(xs0 - 0.002, y + sy * 0.0145, z) for sy, z in ((-1, 0.151), (1, 0.151), (1, 0.19), (-1, 0.19))],
                 [(0, 1, 2, 3)], frame)
        mesh_obj([(xs0 - 0.004, y + sy * 0.0095, z) for sy, z in ((-1, 0.156), (1, 0.156), (1, 0.185), (-1, 0.185))],
                 [(0, 1, 2, 3)], lit)
    for sy in (-1, 1):
        w, _ = _cog_at(L, W, -0.235)
        mesh_obj([(x, sy * (w * 0.97 + 0.003), z) for x, z in ((-0.252, 0.152), (-0.218, 0.152), (-0.218, 0.185),
                                                                (-0.252, 0.185))], [(0, 1, 2, 3)], lit)
        mesh_obj([(xs1 + 0.003, sy * 0.05 + d, z) for d, z in ((-0.011, 0.162), (0.011, 0.162), (0.011, 0.19),
                                                                (-0.011, 0.19))], [(0, 1, 2, 3)], lit)
    mesh_obj([(xs1 + 0.003, y, z) for y, z in ((-0.02, 0.08), (0.02, 0.08), (0.02, 0.15), (-0.02, 0.15))],
             [(0, 1, 2, 3)], flat("door", "#4a2d17", 0.8))
    bx((0.012, 0.016, 0.115), (-L / 2 - 0.016, 0.0, 0.088), planks("#6e4426", 0.012), bev=0, rot=(0, -0.2, 0))  # rudder
    # stern lantern on a bracket over the rail, the state's ensign on a staff beside it
    tube((xs0 + 0.01, 0.0, 0.225), (xs0 + 0.01, 0.0, 0.27), 0.005, iron, n=4)
    bx((0.024, 0.024, 0.03), (xs0 + 0.01, 0.0, 0.288), ev.glow("ship_lantern", "#ffcf6b", 2.5), bev=0)
    cn(0.022, 0.022, (xs0 + 0.01, 0.0, 0.314), iron, 4, rot=(0, 0, math.pi / 4))
    fy = -0.036
    tube((xs0 + 0.012, fy, 0.2), (xs0 + 0.012, fy, 0.37), 0.004, tex("wood", "#5a3a20", 3.0), n=4)
    flag = flat("ensign" + team, team, 0.7)
    fz, fw, fh = 0.328, 0.12, 0.075
    mesh_obj([(xs0 + 0.012, fy - fw * k, fz + fh / 2 * s) for k, s in ((0, 1), (1, 1), (1, -1), (0, -1))],
             [(0, 1, 2, 3)], flag)
    for dx in (0.003, -0.003):
        emblem_yz(xs0 + 0.012 + dx, fy - fw / 2, fz, fh * 0.75, fh * 0.75, white)
    # ---- forecastle over the bow
    ship_castle(0.3, 0.2, 0.14, 0.1, 0.078, 0.19, 0.212, L, W, castle_w, teamc, floor)
    # ---- shields hung along the waist rail, team colour and white in turn
    for k, x in enumerate((-0.13, -0.07, -0.01, 0.05, 0.11, 0.165)):
        w, sh = _cog_at(L, W, x)
        for sy in (-1, 1):
            m_ = teamc if (k + (sy > 0)) % 2 == 0 else white
            mesh_obj([(x + u * 0.034, sy * (w / 0.95 + 0.004), sh - 0.016 + v * 0.036) for u, v in HEATER],
                     [tuple(range(5))], m_)
    # ---- masts, sails, yards, crow's nest, pennants
    spar = tex("wood", "#c99a5c", 3.0)
    mastm = tex("wood", "#6e4426", 3.0)
    rope = flat("rigging", "#3a2c20", 0.8)
    cloth = sailcloth(ev.shade(team, 0.82))
    pen = flat("pennant" + team, team, 0.6)
    mm, mf = -0.02, 0.175
    tube((mm, 0.0, 0.07), (mm, 0.0, 0.705), 0.0115, mastm, r2=0.008, n=6)
    tube((mf, 0.0, 0.07), (mf, 0.0, 0.565), 0.0095, mastm, r2=0.007, n=6)
    square_sail(mm, 0.465, 0.225, 0.3, 0.33, 0.034, cloth, white, spar)  # main course with the eagle
    square_sail(mm, 0.655, 0.555, 0.19, 0.24, 0.02, cloth, None, spar)  # main topsail
    square_sail(mf, 0.43, 0.215, 0.24, 0.27, 0.03, cloth, white, spar)  # fore course with the eagle
    tube((mm, 0.0, 0.49), (mm, 0.0, 0.528), 0.03, planks("#7a4b28", 0.01), n=8)  # crow's nest (open tub)
    mesh_obj([(mm + 0.029 * math.cos(math.tau * k / 8), 0.029 * math.sin(math.tau * k / 8), 0.494) for k in range(8)],
             [tuple(range(8))], planks("#5a3a20"))
    for (x, z, ln) in ((mm, 0.705, 0.15), (mf, 0.565, 0.11)):  # swallow-tailed pennants streaming abeam
        mesh_obj([(x, 0.0, z), (x, ln, z - 0.012), (x, ln * 0.78, z - 0.019), (x, ln * 0.98, z - 0.03),
                  (x, 0.0, z - 0.026)], [(0, 1, 2, 3, 4)], pen)
    # ---- bowsprit, jib, rigging
    tube((0.27, 0.0, 0.19), (0.44, 0.0, 0.245), 0.0085, spar, r2=0.005, n=5)
    mesh_obj([(0.212, 0.0, 0.503), (0.415, 0.0, 0.24), (0.28, 0.0, 0.222)], [(0, 1, 2)], flat("jib", SAIL, 0.8))
    for (mx, zt, xs) in ((mm, 0.5, (-0.05, -0.1)), (mf, 0.42, (0.13,))):
        for sy in (-1, 1):
            for x in xs:
                w, sh = _cog_at(L, W, x)
                tube((mx, 0.0, zt), (x, sy * w, sh), 0.0022, rope, n=3)
    tube((mm, 0.0, 0.69), (mf, 0.0, 0.43), 0.0022, rope, n=3)  # stays
    tube((mf, 0.0, 0.55), (0.43, 0.0, 0.243), 0.0022, rope, n=3)
    tube((mm, 0.0, 0.69), (xs0 + 0.04, 0.0, 0.225), 0.0022, rope, n=3)
    # ---- cargo in the waist: crates, a barrel pair, a grated hatch
    bx((0.04, 0.04, 0.036), (0.07, 0.03, 0.096), planks("#a77a46", 0.01), 0.3, bev=0)
    bx((0.034, 0.034, 0.03), (0.105, -0.035, 0.093), planks("#8e6438", 0.01), -0.2, bev=0)
    bx((0.03, 0.03, 0.026), (0.075, 0.032, 0.127), planks("#b98c55", 0.01), 0.7, bev=0)
    for (x, y) in ((-0.13, 0.04), (-0.13, -0.035)):
        tube((x, y, 0.078), (x, y, 0.13), 0.019, tex("wood", "#8a5e36", 3.0), n=7, cap=True)
        tube((x, y, 0.1), (x, y, 0.106), 0.0205, iron, n=7)
    bx((0.07, 0.06, 0.008), (-0.075, 0.0, 0.082), planks("#5a3a20", 0.008, 0.02, True), bev=0)


# ------------------------------------------------------------------ steel ships (DL6+)


def _sta_at(L, stations, x):
    """Half-beam and sheer of a station hull at x (linear between the stations (t along the length, half-beam,
    sheer height))."""
    t = min(max((x + L / 2) / L, 0.0), 1.0)
    for (t0, w0, s0), (t1, w1, s1) in zip(stations, stations[1:]):
        if t <= t1:
            f = (t - t0) / max(t1 - t0, 1e-9)
            return w0 + (w1 - w0) * f, s0 + (s1 - s0) * f
    return stations[-1][1], stations[-1][2]


def _flare_y(w, z, flare):
    """Half-width of a flared hull side at height z (flare = (fraction of the beam at the waterline, z of full beam))."""
    return w * (flare[0] + (1.0 - flare[0]) * min(1.0, z / flare[1]))


def _orient(o, out):
    """Flip the faces of an open shell whose normal points against out(centre) (recalc can't tell in from out)."""
    for p_ in o.data.polygons:
        if p_.normal.dot(Vector(out(p_.center))) < 0:
            p_.flip()
    o.data.update()
    return o


def steel_hull(L, stations, levels, mats, deck_mt, transom_mt, flare=(0.72, 0.035), rake=0.03):
    """A steel hull along X (bow at +X) lofted through `stations` (t, half-beam, sheer): horizontal colour bands with
    their feet at `levels` (mats[k] from levels[k] up to the next level, the last one up to the sheer), sides flaring
    from flare[0] of the beam at the waterline to the full beam at flare[1], a stem raked forward by `rake`, a flat
    transom and a deck following the sheer (a raised forecastle where the sheer steps up)."""
    zs_band = list(levels)
    verts, idx = [], {}

    def vid(p):
        k = tuple(round(c, 6) for c in p)
        if k not in idx:
            idx[k] = len(verts)
            verts.append(p)
        return idx[k]

    rows = []
    n = len(stations)
    for i, (t, w, sh) in enumerate(stations):
        zp = sorted(set([z for z in zs_band if z < sh - 1e-4] + ([flare[1]] if flare[1] < sh else []))) + [sh]
        row = []
        for z in zp:
            x = -L / 2 + t * L + (rake * z / sh if i == n - 1 else 0.0)
            row.append((x, _flare_y(w, z, flare), z))
        rows.append(row)
    band_faces = [[] for _ in mats]

    def band_of(z):
        k = 0
        for j, lv in enumerate(zs_band):
            if z >= lv - 1e-6:
                k = j
        return k
    def pt(j, z, sy):
        t_, w_, sh_ = stations[j]
        z = min(z, sh_)
        return (-L / 2 + t_ * L + (rake * z / sh_ if j == n - 1 else 0.0), sy * _flare_y(w_, z, flare), z)
    for sy in (1, -1):
        for i in range(n - 1):
            # walk both rows together by z (they hold different z sets where the sheer steps: the lower one stops
            # at its sheer, so the step closes with triangles)
            zall = sorted(set(round(p[2], 6) for p in rows[i] + rows[i + 1]))
            for z0, z1 in zip(zall, zall[1:]):
                q = [vid(pt(i, z0, sy)), vid(pt(i, z1, sy)), vid(pt(i + 1, z1, sy)), vid(pt(i + 1, z0, sy))]
                q = list(dict.fromkeys(q))
                if len(q) >= 3:
                    band_faces[band_of(z0)].append(tuple(q))
    for k, mt in enumerate(mats):
        if not band_faces[k]:
            continue
        used = sorted({v for f in band_faces[k] for v in f})
        remap = {v: j for j, v in enumerate(used)}
        o = mesh_obj([verts[v] for v in used], [tuple(remap[v] for v in f) for f in band_faces[k]], mt)
        _orient(o, lambda c: (0.0, 1.0 if c.y > 0 else -1.0, 0.0))
    # transom: the flat stern between the two sides
    st = rows[0]
    ring = [(p[0], p[1], p[2]) for p in reversed(st)] + [(p[0], -p[1], p[2]) for p in st[1:]]
    _orient(mesh_obj(ring, [tuple(range(len(ring)))], transom_mt), lambda c: (-1.0, 0.0, 0.0))
    # deck: a strip between the gunwales just under the sheer
    dverts, didx = [], {}

    def did(p):
        k = tuple(round(c, 6) for c in p)
        if k not in didx:
            didx[k] = len(dverts)
            dverts.append(p)
        return didx[k]
    df = []
    for i in range(n - 1):
        ring = []
        for j, sy in ((i, -1), (i + 1, -1), (i + 1, 1), (i, 1)):
            t_, w_, sh_ = stations[j]
            x = -L / 2 + t_ * L + (0.004 if j == 0 else 0.0) + (rake - 0.012 if j == n - 1 else 0.0)
            ring.append(did((x, sy * _flare_y(w_, sh_, flare) * 0.95, sh_ - 0.004)))
        ring = list(dict.fromkeys(ring))
        if len(ring) >= 3:
            df.append(tuple(ring))
    _orient(mesh_obj(dverts, df, deck_mt), lambda c: (0.0, 0.0, 1.0))
    return rows


def _hull_side(L, stations, flare, x, z, sy, off=0.0016):
    """Point on the hull side at (x, z) on side sy, `off` proud of it, and the side's heading (rz) there."""
    w, _ = _sta_at(L, stations, x)
    w2, _ = _sta_at(L, stations, x + 0.01)
    y = _flare_y(w, z, flare) + off
    dy = _flare_y(w2, z, flare) - _flare_y(w, z, flare)
    return (x, sy * y, z), math.atan2(sy * dy, 0.01)


_SEG7 = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg",
         9: "abcdfg"}


def hull_number(L, stations, flare, digits, x0, z0, h, mt, t=0.0045):
    """The hull number painted on both bows: seven-segment digits of height h lying on the hull side, read from
    the bow aft on starboard and port alike."""
    wd = h * 0.55
    pitch = wd + h * 0.32
    nd = len(digits)
    for sy in (-1, 1):
        for k, d in enumerate(digits):
            # read left to right from either side: starboard (sy < 0) runs aft → bow, port bow → aft
            xc = x0 - sy * (k - (nd - 1) / 2) * pitch
            for s in _SEG7[d]:
                hor = s in "agd"
                zz = {"a": h, "g": h / 2, "d": 0.0, "b": h * 0.75, "c": h * 0.25, "e": h * 0.25, "f": h * 0.75}[s]
                side = {"b": 1, "c": 1, "e": -1, "f": -1}.get(s, 0)
                p, rz = _hull_side(L, stations, flare, xc - sy * side * wd / 2, z0 + zz, sy)
                bx((wd + t if hor else t, 0.002, t if hor else h / 2 + t), p, mt, rz, bev=0)


def _gun_turret(x, y, z, aim, house, dark, barrels=2, r=0.03, length=0.075, sc=1.0):
    """A naval gun turret: a barbette ring, a house with sloped faces and a flat-faced front, a blast bag and
    `barrels` long guns toward aim (±1 along X)."""
    def b():
        cy(r * 1.05, 0.012, (0, 0, 0.006), dark, 10)
        taper_box((r * 2.2, r * 1.8, r * 0.85), (-r * 0.15, 0, 0.012 + r * 0.42), house, (0.78, 0.8))
        bx((0.006, r * 1.2, r * 0.5), (r * 0.98, 0, 0.012 + r * 0.38), dark, bev=0)  # the gun port plate
        for k in range(barrels):
            yy = (k - (barrels - 1) / 2) * r * 0.5
            rod((r * 0.95, yy, 0.012 + r * 0.38), (r * 0.95 + length, yy, 0.012 + r * 0.46), 0.0042, dark, n=5)
            cy(0.0055, 0.008, (r * 0.95 + length, yy, 0.012 + r * 0.46), dark, 5, rot=(0, math.pi / 2 - 0.03, 0))
    build_at(b, x, y, 0.0 if aim > 0 else math.pi, sc, z=z)


def destroyer(team):
    """A steel destroyer of the industrial and modern eras (DL6–7) along X (bow at +X): a lofted hull with a rising
    sheer and a raised forecastle, red bottom, black boot topping and the state's stripe, the hull number on both
    bows; a stepped bridge with a wrap-round window band and wings, a tripod mast with yards, radar and a lamp, two
    raked funnels with the state's band, a superfiring pair of twin turrets forward and one aft, missile cells, lifeboats
    on davits, a helideck with its H at the stern, the ensign and a jack."""
    grey = flat("ship_grey", "#7d848c", 0.55)
    light = ev.facade("#a5acb4", "#1c2a38", 0.026, 0.03, 0.42, 0.42, lit="#ffd27a", lit_p=0.18, z0=0.004)
    plain = flat("ship_light", "#a5acb4", 0.5)
    deck = ev.facade("#5d636a", "#5d636a", wf=0.0, brick=True, brick_scale=22.0, mortar_k=0.9)  # deck plating
    roof = flat("ship_roof", "#686f77", 0.6)
    # the upper strakes with a row of portholes under the deck edge
    upper = ev.facade("#7d848c", "#262d34", 0.024, 0.06, 0.3, 0.22, lit="#ffd27a", lit_p=0.12, z0=0.035)
    dark = flat("ship_dark", "#2c3035", 0.5)
    red = flat("ship_red", "#8a2f26", 0.6)
    boot = flat("ship_boot", "#1e2023", 0.6)
    stripe = flat("hull_stripe" + team, team, 0.55)
    white = flat("hull_no", "#ecebe6", 0.6)
    win = flat("bridge_win", "#16212c", 0.2)
    L = 0.7
    S = [(0.0, 0.064, 0.07), (0.14, 0.076, 0.068), (0.4, 0.08, 0.068), (0.53, 0.08, 0.07), (0.545, 0.08, 0.086),
         (0.72, 0.072, 0.092), (0.86, 0.05, 0.098), (0.95, 0.024, 0.104), (1.0, 0.0, 0.108)]
    FL = (0.72, 0.034)
    steel_hull(L, S, [0.0, 0.01, 0.018, 0.044, 0.054], [red, boot, grey, stripe, upper], deck, grey, FL, 0.03)
    hull_number(L, S, FL, (7, 4), 0.255, 0.06, 0.026, white)
    zq, zf = 0.064, 0.082  # quarterdeck and forecastle deck heights (just under the sheer)
    # ---- forward: superfiring twin turrets, missile cells, the jack and the anchor gear
    _gun_turret(0.21, 0, zf, 1, plain, dark)
    cy(0.034, 0.024, (0.135, 0, zf + 0.012), grey, 10)  # barbette lifting B turret over A
    _gun_turret(0.135, 0, zf + 0.024, 1, plain, dark)
    for i in range(3):
        for j in range(2):
            bx((0.011, 0.011, 0.004), (0.085 + i * 0.014 - 0.0, -0.012 + j * 0.024, zf + 0.001), dark, bev=0)
    rod((0.37, 0, 0.1), (0.37, 0, 0.15), 0.0025, dark, n=4)  # jack staff
    bx((0.03, 0.003, 0.02), (0.355, 0, 0.14), flat("flag" + team, team, 0.7), bev=0)
    for sy in (-1, 1):
        cy(0.007, 0.008, (0.3, sy * 0.022, 0.1), dark, 6)  # windlass
    # ---- the bridge: a stepped house, a wrap-round window band, wings, a radar dome on top
    bx((0.15, 0.104, 0.042), (0.03, 0, zf - 0.002 + 0.021), light, bev=0.004)
    bx((0.1, 0.09, 0.036), (0.045, 0, zf + 0.04 + 0.018), light, bev=0.004)
    bx((0.104, 0.094, 0.014), (0.046, 0, zf + 0.061), win, bev=0)
    bx((0.012, 0.15, 0.008), (0.07, 0, zf + 0.066), plain, bev=0)  # bridge wings
    bx((0.11, 0.1, 0.008), (0.044, 0, zf + 0.08), roof, bev=0)
    uvs(0.016, (0.03, 0, zf + 0.09), flat("radome", "#e4e6e8", 0.4), 8, 4)
    # ---- the tripod mast with yards, a radar bar, a lamp and the state's pennant
    mx, mz = 0.0, zf + 0.084
    top = 0.33
    rod((mx, 0, mz), (mx - 0.004, 0, top), 0.0045, dark, n=5)
    for sy in (-1, 1):
        rod((mx - 0.03, sy * 0.028, mz - 0.01), (mx - 0.003, 0, top - 0.08), 0.0032, dark, n=4)
    for (z, w) in ((top - 0.08, 0.09), (top - 0.045, 0.06)):
        bx((0.006, w, 0.005), (mx - 0.002, 0, z), dark, bev=0)
    bx((0.022, 0.012, 0.012), (mx - 0.002, 0, top - 0.08 + 0.01), plain, bev=0)  # platform
    bx((0.012, 0.075, 0.014), (mx - 0.003, 0, top - 0.02), plain, bev=0)  # radar bar
    ico(0.006, (mx - 0.004, 0, top + 0.004), glow("mast_lamp", "#ffd27a", 2.5))
    tri_plate((mx - 0.004, 0, top - 0.03), (mx - 0.004, 0, top - 0.046), (mx - 0.07, 0, top - 0.04),
              flat("pennant" + team, team, 0.7), 0.003)
    # ---- two raked funnels with black caps and the state's band
    for (fx, h) in ((-0.07, 0.085), (-0.135, 0.075)):
        p0, p1 = (fx, 0, zq), (fx - 0.014, 0, zq + h)
        rod(p0, p1, 0.02, plain, n=10)
        rod((fx - 0.0105, 0, zq + h * 0.62), (fx - 0.0125, 0, zq + h * 0.74), 0.0215, stripe, n=10)
        rod((fx - 0.0128, 0, zq + h * 0.92), (fx - 0.015, 0, zq + h + 0.004), 0.0215, boot, n=10)
    # midships deckhouse between the funnels, lifeboats on davits each side
    bx((0.2, 0.086, 0.034), (-0.1, 0, zq + 0.017), light, bev=0.004)
    bx((0.21, 0.09, 0.006), (-0.1, 0, zq + 0.036), roof, bev=0)
    boat = flat("lifeboat", "#e8752a", 0.6)
    for sy in (-1, 1):
        for bxp in (-0.04, -0.17):
            uvs(0.011, (bxp, sy * 0.056, zq + 0.04), boat, 8, 4, (2.4, 1.0, 0.8))
            for dx in (-0.016, 0.016):
                tube((bxp + dx, sy * 0.042, zq + 0.034), (bxp + dx, sy * 0.058, zq + 0.056), 0.0022, dark, n=3)
    # ---- aft: Y turret facing astern, the helideck with its H, the ensign
    _gun_turret(-0.235, 0, zq, -1, plain, dark)
    hd = -0.31
    bx((0.09, 0.1, 0.004), (hd, 0, zq + 0.002), flat("helideck", "#3a3f45", 0.7), bev=0)
    cy(0.036, 0.002, (hd, 0, zq + 0.005), white, 16)
    cy(0.031, 0.002, (hd, 0, zq + 0.006), flat("helideck", "#3a3f45", 0.7), 16)
    for dx in (-0.011, 0.011):  # the H, its uprights across the ship so it reads from the side camera
        bx((0.005, 0.032, 0.002), (hd + dx, 0, zq + 0.0075), white, bev=0)
    bx((0.024, 0.005, 0.002), (hd, 0, zq + 0.0075), white, bev=0)
    rod((-0.352, 0, zq), (-0.352, 0, zq + 0.1), 0.003, dark, n=4)  # ensign staff
    bx((0.06, 0.004, 0.04), (-0.32, 0, zq + 0.078), flat("flag" + team, team, 0.7), bev=0)
    bx((0.022, 0.006, 0.015), (-0.32, 0, zq + 0.078), flat("emblem", "#f3efe6", 0.6), bev=0)


def cruiser_scifi(team):
    """A hover cruiser of the late era (DL8+) along X (bow at +X), in the grey steel of the late citadel: a faceted
    hull of pale plates over a dark keel riding on a cold glowing cushion, the state's light strips and inset team
    panels along the sides; a stepped steel bridge tower with a lit window band and a dark needle mast with a lit tip;
    twin rail-gun turrets fore and aft with cold coils, a missile block with lit hatches, three engine nozzles
    glowing at the stern."""
    dk = flat("sf_hull", "#2b3240", 0.35)
    plate = ev.facade("#4a515c", "#9aa2ac", 0.09, 0.024, 0.95, 0.8, lit="#9aa2ac", lit_p=0.0)
    plain = flat("sf_plate", "#8c939c", 0.4)
    trim = flat("sf_trim", "#454e5e", 0.4)
    deck = ev.facade("#3a414b", "#3a414b", wf=0.0, brick=True, brick_scale=12.0, mortar_k=1.16)  # armour plates, pale seams
    st = ev.steel_facade()
    cap = flat("spire8", "#4c535d", 0.35)
    panel = flat("panel8" + team, ev.shade(team, 0.42), 0.4)
    neon = ev.glow("team" + team, team, 3.0)
    cyan = ev.glow("engine", "#7fe6ff", 4.0)
    L = 0.7
    S = [(0.0, 0.07, 0.058), (0.1, 0.086, 0.06), (0.45, 0.09, 0.064), (0.68, 0.082, 0.07), (0.86, 0.052, 0.08),
         (1.0, 0.0, 0.092)]
    FL = (0.6, 0.026)
    steel_hull(L, S, [0.0, 0.007, 0.026, 0.034], [cyan, dk, neon, plate], deck, trim, FL, 0.035)
    # a light line along both gunwales (the neon outlines of reference frame 2), broken at the stations
    for sy in (-1, 1):
        for (t0, w0, s0), (t1, w1, s1) in zip(S[:-1], S[1:-1] + [(0.985, 0.012, 0.09)]):
            p0 = (-L / 2 + t0 * L + 0.003, sy * (_flare_y(w0, s0, FL) - 0.0025), s0 + 0.0015)
            p1 = (-L / 2 + t1 * L, sy * (_flare_y(w1, s1, FL) - 0.0025), s1 + 0.0015)
            beam(p0, p1, 0.005, neon)
    # inset team panels along the plated upper sides, cold strips down their middles (the citadel's signature)
    for sy in (-1, 1):
        for (x, w) in ((-0.2, 0.12), (-0.04, 0.12), (0.12, 0.1)):
            p, rz = _hull_side(L, S, FL, x, 0.05, sy, 0.0012)
            bx((w, 0.003, 0.018), p, panel, rz, bev=0)
            p, rz = _hull_side(L, S, FL, x, 0.05, sy, 0.0026)
            bx((w * 0.8, 0.003, 0.004), p, cyan, rz, bev=0)
    # stern: an engine block with three glowing nozzles and light slits
    bx((0.05, 0.12, 0.045), (-0.355, 0, 0.034), trim, bev=0.004)
    for (y, r) in ((-0.038, 0.016), (0.0, 0.019), (0.038, 0.016)):
        cy(r, 0.02, (-0.382, y, 0.034), dk, 10, rot=(0, math.pi / 2, 0))
        cy(r * 0.72, 0.004, (-0.393, y, 0.034), cyan, 10, rot=(0, math.pi / 2, 0))
    for sy in (-1, 1):  # side engine nacelles on swept pylons, glowing aft, a light line along the outboard side
        beam((-0.22, sy * 0.08, 0.042), (-0.27, sy * 0.106, 0.042), 0.012, trim)
        cy(0.014, 0.09, (-0.295, sy * 0.112, 0.042), plain, 8, rot=(0, math.pi / 2, 0))
        cn(0.014, 0.04, (-0.23, sy * 0.112, 0.042), plain, 8, rot=(0, math.pi / 2, 0))
        cy(0.016, 0.016, (-0.335, sy * 0.112, 0.042), dk, 8, rot=(0, math.pi / 2, 0))
        cy(0.011, 0.004, (-0.344, sy * 0.112, 0.042), cyan, 8, rot=(0, math.pi / 2, 0))
        bx((0.07, 0.003, 0.004), (-0.295, sy * 0.1265, 0.042), neon, bev=0)
    z0 = 0.064
    # ---- the bridge tower: stepped steel blocks with plate seams, a lit window band, a needle mast
    bx((0.22, 0.12, 0.04), (-0.04, 0, z0 + 0.02), st, bev=0.006)
    bx((0.23, 0.13, 0.008), (-0.04, 0, z0 + 0.04), plain, bev=0)
    taper_box((0.14, 0.095, 0.04), (-0.05, 0, z0 + 0.044 + 0.02), st, (0.82, 0.8))
    bx((0.012, 0.074, 0.012), (0.018, 0, z0 + 0.066), cyan, bev=0)  # bridge glazing
    for sy in (-1, 1):
        bx((0.1, 0.004, 0.006), (-0.05, sy * 0.044, z0 + 0.066), cyan, bev=0)
    bx((0.07, 0.06, 0.024), (-0.07, 0, z0 + 0.096), plain, bev=0.004)
    for sy in (-1, 1):  # inset team panels on the tower's sides with a cold strip
        bx((0.08, 0.003, 0.022), (-0.04, sy * 0.0615, z0 + 0.02), panel, bev=0)
        bx((0.06, 0.003, 0.004), (-0.04, sy * 0.063, z0 + 0.02), neon, bev=0)
    mz = z0 + 0.108
    cn(0.022, 0.06, (-0.075, 0, mz + 0.03), cap, 4, rot=(0, 0, math.pi / 4))
    rod((-0.075, 0, mz + 0.05), (-0.075, 0, 0.29), 0.004, cap, r2=0.0012, n=4)
    for z in (mz + 0.075, mz + 0.105):
        bx((0.006, 0.05, 0.004), (-0.075, 0, z), cap, bev=0)
    bx((0.01, 0.01, 0.01), (-0.075, 0, 0.27), cyan, bev=0)
    uvs(0.014, (-0.02, 0.036, z0 + 0.12), flat("radome", "#e4e6e8", 0.4), 8, 4)
    # ---- twin rail-gun turrets fore and aft: angular houses, long rails with cold coils
    def railgun(x, z, aim):
        def b():
            cy(0.03, 0.01, (0, 0, 0.005), dk, 8)
            taper_box((0.07, 0.056, 0.024), (0, 0, 0.022), plain, (0.75, 0.7))
            bx((0.03, 0.058, 0.006), (-0.01, 0, 0.022), trim, bev=0)
            for sy in (-0.011, 0.011):
                beam((0.028, sy, 0.024), (0.11, sy, 0.028), 0.007, trim)
                for k in range(3):
                    bx((0.006, 0.01, 0.01), (0.05 + k * 0.02, sy, 0.0255 + k * 0.001), cyan, bev=0)
        build_at(b, x, 0, 0.0 if aim > 0 else math.pi, z=z)
    railgun(0.17, 0.07, 1)
    railgun(-0.24, z0 - 0.002, -1)
    # missile block with lit hatches ahead of the bridge
    bx((0.07, 0.07, 0.022), (0.09, 0, 0.074 + 0.011), trim, bev=0.004)
    for i in range(3):
        for j in range(3):
            bx((0.013, 0.013, 0.003), (0.072 + i * 0.018, -0.018 + j * 0.018, 0.0965), neon, bev=0)
    # the state's ensign aft of the tower
    rod((-0.3, 0, z0), (-0.3, 0, z0 + 0.09), 0.003, cap, n=4)
    bx((0.05, 0.004, 0.032), (-0.274, 0, z0 + 0.07), flat("flag" + team, team, 0.7), bev=0)
    bx((0.018, 0.006, 0.013), (-0.274, 0, z0 + 0.07), flat("emblem", "#f3efe6", 0.6), bev=0)


def _ribbed(color, axis=0, period=0.011, k=0.78):
    """Corrugated steel baked like every procedural colour: ribs that vary along X (axis 0), Y (1), Z (2: the
    horizontal slats of a roller door) or X + Y (3: round every wall of a box)."""
    def s_of(nt, L, pos):
        sp = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(pos, sp.inputs[0])
        if axis == 3:
            ad = nt.nodes.new("ShaderNodeMath")
            ad.operation = "ADD"
            L.new(sp.outputs[0], ad.inputs[0])
            L.new(sp.outputs[1], ad.inputs[1])
            src = ad.outputs[0]
        else:
            src = sp.outputs[axis]
        dv = nt.nodes.new("ShaderNodeMath")
        dv.operation = "DIVIDE"
        L.new(src, dv.inputs[0])
        dv.inputs[1].default_value = period
        return dv.outputs[0]
    return ev._stripe_mat(("ribbed", color, axis, period, k), s_of, color, shade(color, k))


CONT_COLS = ["#b5452f", "#d9822b", "#2f7f8f", "#8a8f96", "#3f7a3a", "#c9b23a"]


def container(x, y, z, rz, c, L=0.13, W=0.05, H=0.048):
    """A corrugated shipping container (ribs across its length, plain door ends)."""
    axis = 0 if abs(math.cos(rz)) > 0.7 else 1
    bx((L, W, H), (x, y, z + H / 2), _ribbed(c, axis, 0.0095), rz, bev=0)


def container_stack(x, y, rz, team, heights, seed=3, pitch=0.054):
    """A block of container stacks side by side (across rz), each heights[k] high; the state's colour on one box
    of every other stack."""
    rnd = random.Random(seed)
    c, s = math.cos(rz), math.sin(rz)
    for k, n in enumerate(heights):
        off = (k - (len(heights) - 1) / 2) * pitch
        px, py = x - s * off, y + c * off
        for j in range(n):
            col = team if (j == n - 1 and k % 2 == 0) else rnd.choice(CONT_COLS)
            container(px, py, 0.008 + j * 0.051, rz, col)


def sts_crane(team, reach=0.34, back=0.15, load=True):
    """A ship-to-shore container crane (local frame: it rides rails along X; the boom runs along +Y over the berth):
    a portal of four legs in the state's colour on hazard-striped bogies with cross bracing, a white lattice boom
    with a back-reach, an A-frame with stays, a machinery house, the operator's cab, a trolley with its spreader
    and a container on the hook."""
    frame = flat("crane" + team, team, 0.45)
    white = flat("crane_w", "#e9ecef", 0.45)
    dk = flat("crane_dk", "#2c3036", 0.5)
    haz = ev.hazard(0.018)
    sx, sy, z0, zp, zb = 0.055, 0.058, 0.0, 0.3, 0.355
    for y in (-sy, sy):
        bx((2 * sx + 0.04, 0.026, 0.022), (0, y, z0 + 0.011), haz, bev=0)  # bogie sill on the rail
        for x in (-sx, sx):
            bx((0.02, 0.02, zp - z0), (x, y, (z0 + zp) / 2), frame, bev=0)
        beam((-sx, y, z0 + 0.03), (sx, y, zp - 0.03), 0.009, frame)  # diagonal brace
        bx((2 * sx + 0.02, 0.022, 0.024), (0, y, zp - 0.012), frame, bev=0)  # portal beam along X
    for x in (-sx, sx):
        bx((0.022, 2 * sy + 0.02, 0.026), (x, 0, zp + 0.013), frame, bev=0)  # cross beams under the boom
        bx((0.016, 2 * sy, 0.014), (x, 0, z0 + 0.12), frame, bev=0)  # lower tie between the legs
    # the boom: two white girders with ties on top, from the back-reach to the tip over the water
    y0, y1 = -back, reach
    for x in (-0.02, 0.02):
        bx((0.012, y1 - y0, 0.022), (x, (y0 + y1) / 2, zb), white, bev=0)
    n = int((y1 - y0) / 0.05)
    for k in range(n + 1):
        y = y0 + (y1 - y0) * k / n
        bx((0.052, 0.008, 0.008), (0, y, zb + 0.012), white, bev=0)
    for k in range(n):  # zigzag web on both girders (the lattice of the boom)
        ya, yb = y0 + (y1 - y0) * k / n, y0 + (y1 - y0) * (k + 1) / n
        for x in (-0.026, 0.026):
            beam((x, ya, zb - 0.009), (x, yb, zb + 0.009) if k % 2 == 0 else (x, yb, zb - 0.009), 0.004, white)
    # A-frame over the portal with forestays to the tip and backstays to the tail
    za = 0.53
    for x in (-0.03, 0.03):
        beam((x * 1.6, -0.03, zb), (x, -0.005, za), 0.014, frame)
        beam((x * 1.6, 0.04, zb), (x, -0.005, za), 0.011, frame)
    bx((0.07, 0.02, 0.018), (0, -0.005, za), frame, bev=0)
    for x in (-0.024, 0.024):
        tube((x, -0.005, za), (x, y1 - 0.02, zb + 0.012), 0.003, dk, n=4)
        tube((x, -0.005, za), (x, y0 + 0.02, zb + 0.012), 0.003, dk, n=4)
    # machinery house on the tail, a band of the state's colour
    bx((0.07, 0.07, 0.045), (0, y0 + 0.04, zb + 0.034), white, bev=0.004)
    bx((0.072, 0.072, 0.01), (0, y0 + 0.04, zb + 0.03), frame, bev=0)
    # the operator's cab hung under the boom, its glass toward the water
    bx((0.035, 0.035, 0.03), (0.0, 0.1, zb - 0.03), white, bev=0)
    bx((0.03, 0.004, 0.016), (0.0, 0.1 + 0.019, zb - 0.028), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    # the trolley, its ropes and the spreader with a container
    yt = reach - 0.1
    bx((0.05, 0.04, 0.016), (0, yt, zb - 0.017), dk, bev=0)
    if load:
        zc = 0.17
        for x in (-0.012, 0.012):
            tube((x, yt, zb - 0.025), (x, yt, zc + 0.058), 0.0022, dk, n=3)
        bx((0.135, 0.045, 0.008), (0, yt, zc + 0.054), flat("spreader", "#d9b23a", 0.5), math.pi / 2, bev=0)
        container(0, yt, zc, math.pi / 2, team)


def cargo_ship(team):
    """A container feeder along X (bow at +X): a dark hull with a red boot band and the state's sheer stripe, rows of
    containers two tiers high, a white bridge house aft with lit windows and wings, a funnel with the state's band,
    a foremast and a lifeboat."""
    hull(0.62, 0.17, 0.08, flat("hull_cargo", "#2f3a46", 0.6), flat("deck_cargo", "#7a3a2c", 0.7),
         flat("boot" + team, team, 0.6))
    rnd = random.Random(11)
    for i in range(4):
        for j in range(3):
            for k in range(2 if (i + j) % 3 else 1):
                c = team if (i == 1 and k == 1) else rnd.choice(CONT_COLS)
                ax = 0
                bx((0.088, 0.046, 0.04), (-0.1 + i * 0.094, -0.05 + j * 0.05, 0.1 + k * 0.042), _ribbed(c, ax, 0.009),
                   bev=0)
    # bridge house: white with window rows (some lit), a dark window band at the top, wings, a radar mast
    house = ev.facade("#e8e6e0", "#1d2a38", 0.022, 0.03, 0.5, 0.45, lit="#ffd27a", lit_p=0.3, z0=0.08)
    bx((0.07, 0.12, 0.09), (-0.24, 0, 0.125), house, bev=0.004)
    bx((0.074, 0.124, 0.014), (-0.24, 0, 0.162), flat("bridge_g", "#1d2a38", 0.2), bev=0)
    bx((0.03, 0.17, 0.008), (-0.215, 0, 0.165), flat("bridge_w", "#e8e6e0", 0.5), bev=0)
    bx((0.08, 0.13, 0.01), (-0.24, 0, 0.175), flat("bridge_r", "#3b4048", 0.5), bev=0)
    rod((-0.24, 0, 0.18), (-0.24, 0, 0.25), 0.004, flat("mast_dk", "#2c3036", 0.5), n=4)
    bx((0.008, 0.05, 0.006), (-0.24, 0, 0.235), flat("mast_dk", "#2c3036", 0.5), bev=0)
    cy(0.022, 0.07, (-0.285, 0, 0.17), flat("funnel_w", "#e8e6e0", 0.5), 10)
    cy(0.0225, 0.02, (-0.285, 0, 0.19), flat("funnel" + team, team, 0.5), 10)
    cy(0.0225, 0.008, (-0.285, 0, 0.207), flat("funnel_cap", "#1e2023", 0.5), 10)
    uvs(0.012, (-0.2, 0.072, 0.1), flat("lifeboat", "#e8752a", 0.6), 8, 4, (2.2, 1.0, 0.8))
    rod((0.25, 0, 0.08), (0.25, 0, 0.17), 0.004, flat("mast_dk", "#2c3036", 0.5), n=4)


def tug(team):
    """A harbour tug along X: a red hull with a black sheer band and tyre fenders, a white wheelhouse with a dark
    window band, a black funnel with the state's band, a towing post aft."""
    hull(0.2, 0.08, 0.05, flat("tug_red", "#b03a2e", 0.6), flat("tug_deck", "#4a4f55", 0.7),
         flat("tug_band", "#1e2023", 0.6))
    bx((0.07, 0.05, 0.035), (0.01, 0, 0.065), flat("tug_house", "#ecebe6", 0.5), bev=0.004)
    bx((0.074, 0.054, 0.012), (0.01, 0, 0.074), flat("bridge_g", "#1d2a38", 0.2), bev=0)
    bx((0.05, 0.04, 0.02), (0.015, 0, 0.092), flat("tug_house", "#ecebe6", 0.5), bev=0)
    bx((0.054, 0.044, 0.008), (0.015, 0, 0.096), flat("bridge_g", "#1d2a38", 0.2), bev=0)
    cy(0.012, 0.05, (-0.03, 0, 0.1), flat("tug_band", "#1e2023", 0.6), 8)
    cy(0.0125, 0.012, (-0.03, 0, 0.1), flat("funnel" + team, team, 0.5), 8)
    cy(0.008, 0.02, (-0.07, 0, 0.06), flat("tug_band", "#1e2023", 0.6), 6)
    tyre = flat("tyre", "#1f1f21", 0.9)
    for (x, y) in ((0.09, 0.0), (0.06, 0.03), (0.06, -0.03), (-0.04, 0.042), (-0.04, -0.042)):
        torus(0.011, 0.005, (x + 0.004 * (1 if x > 0 else 0), y * 1.05, 0.032), tyre,
              (math.pi / 2, 0, math.atan2(y, x) + math.pi / 2), 6, 3)


def warehouse_modern(team, w=0.42, d=0.24, h=0.16):
    """A terminal shed facing −Y: corrugated white walls with a band of the state's colour under the eaves, three
    roller doors in dark frames with yellow bollards, a low gable roof with skylight strips, and a two-storey office
    at the +X end with warm lit windows and roof plant."""
    wall = _ribbed("#c9cdd2", 3, 0.012, 0.82)
    bx((w, d, h), (0, 0, h / 2), wall, bev=0)
    bx((w + 0.006, d + 0.006, 0.024), (0, 0, h - 0.018), flat("band" + team, team, 0.6), bev=0)
    roofm = flat("shed_roof", "#5b636c", 0.6)
    ev.hip_roof(w + 0.02, d + 0.02, 0.05, (0, 0, h), roofm, oh=0.0)
    sky = flat("skylight", "#a9c6d6", 0.25)
    for x in (-0.12, 0.0, 0.12):  # skylight strips down the front slope
        mesh_obj([(x - 0.025, -d / 2 + 0.02, h + 0.009), (x + 0.025, -d / 2 + 0.02, h + 0.009),
                  (x + 0.025, -0.02, h + 0.043), (x - 0.025, -0.02, h + 0.043)], [(0, 1, 2, 3)], sky)
    door = _ribbed("#e1e4e8", 2, 0.008, 0.82)
    fr = flat("door_frame", "#3a3e44", 0.6)
    yel = flat("bollard_y", "#e8c12e", 0.5)
    for x in (-0.13, -0.01):
        bx((0.1, 0.008, 0.11), (x, -d / 2 - 0.002, 0.055), fr, bev=0)
        bx((0.086, 0.01, 0.1), (x, -d / 2 - 0.004, 0.05), door, bev=0)
        for sx in (-1, 1):
            cy(0.007, 0.03, (x + sx * 0.055, -d / 2 - 0.02, 0.015), yel, 6)
    # the office at the +X end: two storeys of lit windows, a flat roof with plant, a sign in the state's colour
    ow = 0.12
    office = ev.facade("#e6e2d8", "#25313d", 0.03, 0.05, 0.55, 0.5, lit="#ffd27a", lit_p=0.4, z0=0.01)
    bx((ow, d + 0.03, h + 0.04), (w / 2 + ow / 2 - 0.005, 0.0, (h + 0.04) / 2), office, bev=0)
    bx((ow + 0.008, d + 0.038, 0.012), (w / 2 + ow / 2 - 0.005, 0.0, h + 0.046), flat("office_cap", "#8a9097", 0.6), bev=0)
    for (x, y) in ((w / 2 + 0.03, 0.04), (w / 2 + 0.08, -0.03)):
        bx((0.03, 0.03, 0.02), (x, y, h + 0.062), flat("ac", "#aeb4bb", 0.5), bev=0)
    bx((0.08, 0.006, 0.026), (w / 2 + ow / 2 - 0.005, -d / 2 - 0.018, h + 0.01), flat("sign" + team, team, 0.5), bev=0)
    bx((0.05, 0.007, 0.008), (w / 2 + ow / 2 - 0.005, -d / 2 - 0.019, h + 0.01), flat("sign_w", "#f3efe6", 0.5), bev=0)


def flood_mast(x, y, h=0.4):
    """A tall floodlight mast of the quay with a head of three warm lamps."""
    post = flat("lamp_post", "#7c838c", 0.5)
    cy(0.009, h, (x, y, h / 2), post, 6)
    bx((0.06, 0.012, 0.03), (x, y, h + 0.012), post, bev=0)
    for dx in (-0.018, 0.0, 0.018):
        bx((0.014, 0.008, 0.014), (x + dx, y - 0.009, h + 0.008), glow("flood", "#ffd99a", 3.0), bev=0)


def box_truck(team, cont_c):
    """A container truck along X: a cab in the state's colour, a dark chassis and a container on the trailer."""
    dk = flat("chassis", "#2b2d31", 0.6)
    bx((0.2, 0.04, 0.012), (-0.02, 0, 0.022), dk, bev=0)
    bx((0.045, 0.05, 0.045), (0.105, 0, 0.042), flat("cab" + team, team, 0.45), bev=0.005)
    bx((0.006, 0.042, 0.018), (0.128, 0, 0.05), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    container(-0.035, 0, 0.028, 0.0, cont_c, 0.14)
    for dx in (-0.09, -0.06, 0.03, 0.1):
        for sy in (-1, 1):
            cy(0.013, 0.01, (dx, sy * 0.024, 0.013), flat("tyre", "#1f1f21", 0.9), 8, rot=(math.pi / 2, 0, 0))


def port_modern(team):
    """The industrial port (DL6–7) after the late-era harbours of reference frame 2: a concrete terminal round the
    cove with a yellow-lined quay edge, two ship-to-shore gantry cranes in the state's colour on the pier (rails,
    bogies, lattice booms, A-frames, a container on the hook), a container feeder at the berth, a red tug, stacked
    corrugated containers, a terminal shed with roller doors and a lit office, fuel tanks with the state's band, a
    container truck, tyre fenders, bollards and warm floodlight masts."""
    conc = ev.facade("#8e9298", "#8e9298", wf=0.0, brick=True, brick_scale=7.0, mortar_k=0.82)  # quay slabs
    yel = flat("paint_y", "#e8c12e", 0.6)
    _cove(conc, "#3a7fae", "#6aaecc", joints=True, edge=yel)
    apron = ev.facade("#868a90", "#868a90", wf=0.0, brick=True, brick_scale=9.0, mortar_k=0.88)
    # the terminal apron covers the land side of the hex (the late-era harbours are built up to the edge)
    ground_poly([clamp_hex(p_, 0.8)[0] for p_ in ((0.22, -0.7), (-0.3, -0.7), (-0.66, -0.36), (-0.74, 0.0),
                                                   (-0.62, 0.42), (-0.3, 0.68), (0.22, 0.68), (0.1, 0.0))], apron, 0.008)
    py = -0.03
    pier = ev.facade("#959a9f", "#959a9f", wf=0.0, brick=True, brick_scale=6.0, mortar_k=0.84)
    bx((0.78, 0.16, 0.05), (0.41, py, 0.05), pier, bev=0)  # concrete pier to the edge
    dk = flat("crane_dk", "#2c3036", 0.5)
    for sy in (-1, 1):
        bx((0.76, 0.006, 0.002), (0.41, py + sy * 0.058, 0.076), dk, bev=0)  # crane rails
        bx((0.76, 0.006, 0.002), (0.41, py + sy * 0.075, 0.076), yel, bev=0)  # yellow edge line
    tyre = flat("tyre", "#1f1f21", 0.9)
    for i in range(7):  # rubber fenders along both faces of the pier
        x = 0.1 + i * 0.11
        for sy in (-1, 1):
            bx((0.016, 0.008, 0.03), (x, py + sy * 0.083, 0.05), tyre, bev=0)
    for i in range(6):
        cy(0.011, 0.022, (0.15 + i * 0.12, py - 0.068, 0.086), flat("bollard", "#2b2d31", 0.5), 8)
    # two gantry cranes on the pier, booms out over the berth (+Y)
    build_at(lambda: sts_crane(team), 0.3, py, 0.0, z=0.075)
    build_at(lambda: sts_crane(team, load=False), 0.6, py, 0.0, z=0.075)
    # the container feeder at the berth and a tug off the pier's other side
    build_at(lambda: cargo_ship(team), 0.47, 0.215, 0.0, z=0.004)
    build_at(lambda: tug(team), 0.58, -0.32, 0.5, z=0.004)
    # the container yard on the apron (front), a truck with a box on the way to the pier
    container_stack(-0.34, -0.36, 0.0, team, (3, 2, 3, 1), seed=5)
    container_stack(-0.12, -0.38, 0.0, team, (2, 3, 1), seed=8)
    container_stack(-0.3, -0.1, 0.0, team, (1, 2, 2), seed=12)
    for (x0, x1, y) in ((-0.56, 0.06, -0.235), (-0.4, 0.06, -0.5)):
        bx((x1 - x0, 0.006, 0.002), ((x0 + x1) / 2, y, 0.0085), yel, bev=0)  # yard lane lines
    build_at(lambda: box_truck(team, CONT_COLS[2]), -0.02, -0.16, 0.15)
    # the terminal shed at the back, fuel tanks on the left
    build_at(lambda: warehouse_modern(team), -0.34, 0.34, -0.1)
    for (x, y, r) in ((-0.62, 0.02, 0.07), (-0.58, -0.17, 0.055)):
        cy(r, 0.12 if r > 0.06 else 0.1, (x, y, 0.06 if r > 0.06 else 0.05), flat("tank_w", "#e3e6e9", 0.4), 14)
        cy(r + 0.002, 0.016, (x, y, 0.085 if r > 0.06 else 0.07), flat("band" + team, team, 0.6), 14)
        cn(r, 0.03, (x, y, (0.12 if r > 0.06 else 0.1) + 0.015), flat("tank_top", "#aeb4bb", 0.5), 14)
    flood_mast(0.06, 0.06, 0.4)
    flood_mast(-0.02, -0.5, 0.36)
    flood_mast(0.12, -0.4, 0.36)


def steel_kit(team):
    """The grey steel kit of the late citadel (residence_dl8, city_dl8; reference frame 5): steel with narrow lit
    slits, dark plate trim, pale plate seams, recessed panels in a deep team tone, dark spire caps, the state's cold
    light strips and cyan lamps."""
    return dict(st=ev.steel_facade(), plate=flat("plate8", "#505760", 0.45), seam=flat("seam8", "#8c939c", 0.45),
                panel=flat("panel8" + team, shade(team, 0.42), 0.4), cap=flat("spire8", "#4c535d", 0.35),
                neon=glow("strip" + team, shade(team, 1.25), 2.0), cyan=glow("cyan", ev.CYAN, 2.5),
                comp=ev.facade("#7d858f", "#a3abb5", 0.1, 0.07, 0.94, 0.86, lit="#a3abb5", lit_p=0.0),
                dark=flat("comptrim", "#3e444d", 0.5), white=flat("pod", "#e3e8ee", 0.35))


def inset_panel(x, y, z, w, h, nx, ny, k):
    """A recessed team panel on a wall facing (nx, ny) with a cold light strip down its middle (the citadel's
    signature), standing just proud of the wall at (x, y)."""
    rz = 0.0 if ny else math.pi / 2
    bx((w, 0.004, h), (x + nx * 0.001, y + ny * 0.001, z), k["panel"], rz, bev=0)
    bx((0.01, 0.006, h * 0.8), (x + nx * 0.003, y + ny * 0.003, z), k["neon"], rz, bev=0)


def control_tower8(k, h=0.42):
    """The harbour control tower in the citadel's steel: a plinth, a shaft with pale plate seams and inset team
    panels with cold strips, a glass cab ringed by a light band, a dark spire with a lit needle."""
    w = 0.1
    bx((0.16, 0.16, 0.05), (0, 0, 0.025), k["plate"], bev=0.004)
    bx((0.165, 0.165, 0.008), (0, 0, 0.052), k["seam"], bev=0)
    bx((w, w, h), (0, 0, h / 2), k["st"], bev=0)
    for zf in (0.4, 0.7):
        bx((w + 0.01, w + 0.01, 0.016), (0, 0, h * zf), k["seam"], bev=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.016, 0.016, h * 0.94), (sx * w / 2, sy * w / 2, h * 0.47), k["plate"], bev=0)
    inset_panel(0, -w / 2, h * 0.55, w * 0.42, h * 0.5, 0, -1, k)
    inset_panel(w / 2, 0, h * 0.55, w * 0.42, h * 0.5, 1, 0, k)
    zc = h + 0.02
    cy(0.085, 0.02, (0, 0, h + 0.01), k["plate"], 8)
    cy(0.1, 0.05, (0, 0, zc + 0.025), flat("cab8", "#1b2533", 0.25), 8)
    cy(0.102, 0.012, (0, 0, zc + 0.03), k["cyan"], 8)
    cy(0.112, 0.016, (0, 0, zc + 0.058), k["plate"], 8)
    cn(0.05, 0.13, (0, 0, zc + 0.066 + 0.065), k["cap"], 4, rot=(0, 0, math.pi / 4))
    rod((0, 0, zc + 0.19), (0, 0, zc + 0.27), 0.005, k["cap"], r2=0.0015, n=4)
    bx((0.014, 0.014, 0.014), (0, 0, zc + 0.24), k["cyan"], bev=0)
    for sx in (-1, 1):  # antenna dishes on the cab roof
        uvs(0.016, (sx * 0.06, 0.03, zc + 0.075), k["white"], 8, 4, (1, 1, 0.5))


def cargo_hall8(k, team, w=0.34, d=0.22, h=0.14):
    """A steel cargo hall facing −Y (the chunky steel blocks of reference frame 5): a chamfered roof, buttresses with
    plate seams, a wide glowing bay door in a dark frame flanked by team panels, a light line under the eaves and
    roof plant with a vent glow."""
    bx((w, d, h), (0, 0, h / 2), k["st"], bev=0)
    taper_box((w + 0.012, d + 0.012, 0.04), (0, 0, h + 0.02), k["plate"], (0.86, 0.8))
    bx((w + 0.014, d + 0.014, 0.012), (0, 0, h * 0.4), k["seam"], bev=0)
    for x in (-w / 2, -w / 6, w / 6, w / 2):  # buttresses on the front and back
        for sy in (-1, 1):
            bx((0.02, 0.016, h * 0.95), (x, sy * d / 2, h * 0.475), k["plate"], bev=0)
    bx((0.13, 0.01, 0.1), (0, -d / 2 - 0.003, 0.05), k["dark"], bev=0)
    bx((0.11, 0.012, 0.085), (0, -d / 2 - 0.005, 0.043), glow("bay8", "#9fdcff", 0.9), bev=0)
    for sx in (-1, 1):
        inset_panel(sx * 0.115, -d / 2 - 0.002, h * 0.55, 0.05, h * 0.62, 0, -1, k)
    bx((w * 0.9, 0.006, 0.008), (0, -d / 2 - 0.004, h - 0.01), k["neon"], bev=0)
    for (x, y) in ((-0.08, 0.04), (0.09, 0.02)):
        bx((0.06, 0.06, 0.03), (x, y, h + 0.055), k["comp"], bev=0)
        cy(0.016, 0.006, (x, y, h + 0.072), k["cyan"], 8)


def energy_crane(k, team, reach=0.3, back=0.12, pod=True):
    """A late-era cargo gantry (local frame like sts_crane: rails along X, the arm along +Y over the berth): steel
    pylons with cold strips on a dark sill, a plated arm with a light line under it, a counterweight block, and an
    emitter ring at the tip holding a cargo pod in a column of cold light (a tractor beam)."""
    sx, sy, zp, zb = 0.05, 0.055, 0.3, 0.33
    for y in (-sy, sy):
        bx((2 * sx + 0.04, 0.03, 0.02), (0, y, 0.01), k["dark"], bev=0)
        for x in (-sx, sx):
            taper_box((0.03, 0.03, zp), (x, y, zp / 2), k["comp"], (0.7, 0.7))
            bx((0.006, 0.032, zp * 0.7), (x, y, zp * 0.5), k["cyan"], bev=0)
    for x in (-sx, sx):
        bx((0.026, 2 * sy + 0.03, 0.03), (x, 0, zp + 0.015), k["plate"], bev=0)
    y0, y1 = -back, reach
    for x in (-0.016, 0.016):  # twin plated girders with light lines along their tops
        bx((0.018, y1 - y0, 0.028), (x, (y0 + y1) / 2, zb + 0.014), k["comp"], bev=0)
        bx((0.006, y1 - y0 - 0.03, 0.004), (x, (y0 + y1) / 2 + 0.01, zb + 0.03), k["neon"], bev=0)
    for f in (0.3, 0.55, 0.8):
        bx((0.05, 0.012, 0.01), (0, y0 + (y1 - y0) * f, zb + 0.022), k["plate"], bev=0)
    bx((0.08, 0.07, 0.05), (0, y0 + 0.035, zb + 0.06), k["st"], bev=0)  # counterweight / machinery block
    inset_panel(0, y0 + 0.035 - 0.036, zb + 0.06, 0.05, 0.035, 0, -1, k)
    yt = reach - 0.05
    cy(0.032, 0.014, (0, yt, zb - 0.005), k["dark"], 10)
    cy(0.026, 0.006, (0, yt, zb - 0.014), k["cyan"], 10)
    if pod:
        zc = 0.13
        bx((0.026, 0.026, zb - 0.02 - (zc + 0.05)), (0, yt, (zb - 0.02 + zc + 0.05) / 2), glow("tractor", "#7fdcff", 0.7), bev=0)
        bx((0.1, 0.06, 0.05), (0, yt, zc + 0.025), k["white"], math.pi / 2, bev=0.012)
        bx((0.102, 0.008, 0.008), (0.031, yt, zc + 0.03), k["neon"], math.pi / 2, bev=0)


def hover_lifter(k, team):
    """A hover cargo lifter parked on its pad: a pale hull with a dark canopy, the state's stripe, four ducted fans
    glowing cold."""
    bx((0.14, 0.07, 0.035), (0, 0, 0.03), k["white"], bev=0.012)
    bx((0.04, 0.05, 0.02), (0.05, 0, 0.055), flat("canopy8", "#1b2533", 0.2), bev=0.008)
    bx((0.142, 0.072, 0.008), (0, 0, 0.03), k["neon"], bev=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.022, 0.014, (sx * 0.06, sy * 0.052, 0.025), k["dark"], 10)
            cy(0.016, 0.004, (sx * 0.06, sy * 0.052, 0.033), k["cyan"], 10)


def pod_rack(k, team, n=3):
    """A two-tier steel rack of rounded cargo pods with the state's and cyan strips."""
    for x in (-n * 0.045, n * 0.045):
        for y in (-0.035, 0.035):
            bx((0.012, 0.012, 0.14), (x, y, 0.07), k["plate"], bev=0)
    for z in (0.004, 0.07):
        bx((n * 0.09 + 0.02, 0.08, 0.008), (0, 0, z + 0.004), k["plate"], bev=0)
    for t in range(2):
        for i in range(n):
            if t == 1 and i == n - 1:
                continue
            x = (i - (n - 1) / 2) * 0.09
            bx((0.08, 0.06, 0.054), (x, 0, 0.012 + t * 0.066 + 0.027), k["white"], bev=0.014)
            bx((0.082, 0.062, 0.008), (x, 0, 0.012 + t * 0.066 + 0.03), k["neon"] if (i + t) % 2 else k["cyan"], bev=0)


def port_scifi(team):
    """The late-era port (DL8+) after the lit harbours of reference frame 2, in the steel kit of the late citadel: a
    dark steel apron laced with the state's light strips, composite quays with a cold lit edge, a plated pier with
    neon edges and light posts, the hover cruiser at berth under an energy gantry that holds a cargo pod in a tractor
    beam, a docking arm to the cruiser, a steel control tower with team panels and a lit spire, a steel cargo hall
    with a glowing bay door, a lit pad with a hover lifter and racks of cargo pods."""
    kk = steel_kit(team)
    _cove(kk["comp"], "#2f6e9c", "#5aa0c4", joints=True, edge=kk["cyan"])
    apron = ev.stone("#454a52", 0.8)  # the dark steel plaza slabs of the late capital
    ground_poly([clamp_hex(p_, 0.8)[0] for p_ in ((0.22, -0.7), (-0.3, -0.7), (-0.66, -0.36), (-0.74, 0.0),
                                                   (-0.62, 0.42), (-0.3, 0.68), (0.22, 0.68), (0.1, 0.0))], apron, 0.008)
    for (p0, p1) in (((-0.62, -0.2), (0.06, -0.2)), ((-0.06, -0.62), (-0.06, 0.6))):  # light strips across the apron
        beam((p0[0], p0[1], 0.009), (p1[0], p1[1], 0.009), 0.01, kk["neon"])
    py = -0.03
    bx((0.78, 0.15, 0.04), (0.41, py, 0.05), kk["comp"], bev=0)
    for sy in (-1, 1):
        bx((0.76, 0.008, 0.008), (0.41, py + sy * 0.077, 0.068), kk["neon"], bev=0)
        bx((0.76, 0.012, 0.03), (0.41, py + sy * 0.077, 0.045), kk["dark"], bev=0)
    for i in range(5):  # light posts along the pier
        x = 0.16 + i * 0.15
        bx((0.012, 0.012, 0.06), (x, py - 0.062, 0.1), kk["plate"], bev=0)
        bx((0.016, 0.016, 0.012), (x, py - 0.062, 0.134), kk["cyan"], bev=0)
    build_at(lambda: cruiser_scifi(team), 0.46, 0.22, 0.0, 0.75, z=0.004)
    build_at(lambda: energy_crane(kk, team), 0.34, py, 0.0, z=0.07)
    # a docking arm from the pier to the cruiser's side, a glowing joint at the elbow
    for (p0, p1) in (((0.6, py + 0.06, 0.075), (0.6, 0.08, 0.13)), ((0.6, 0.08, 0.13), (0.6, 0.145, 0.07))):
        beam(p0, p1, 0.022, kk["plate"])
    ico(0.016, (0.6, 0.08, 0.13), kk["cyan"])
    # the control tower, the cargo hall, the pad with a lifter, racks of pods
    build_at(lambda: control_tower8(kk), -0.5, 0.32)
    build_at(lambda: cargo_hall8(kk, team), -0.16, 0.42, -0.08)
    cy(0.13, 0.014, (-0.3, -0.04, 0.012), kk["dark"], 16)
    cy(0.118, 0.006, (-0.3, -0.04, 0.02), ev.glow("padring" + team, team, 1.6), 16)
    cy(0.104, 0.008, (-0.3, -0.04, 0.021), flat("pad_sf", "#2c323b", 0.5), 16)
    build_at(lambda: hover_lifter(kk, team), -0.3, -0.04, 0.4, z=0.024)
    build_at(lambda: pod_rack(kk, team), -0.32, -0.42, 0.0)
    build_at(lambda: pod_rack(kk, team, 2), 0.0, -0.44, 0.0)
    for (x, y) in ((-0.06, 0.12), (-0.62, -0.14), (0.0, -0.28)):  # light masts
        cy(0.007, 0.18, (x, y, 0.09), flat("mast", "#d0d4da", 0.5), 6)
        bx((0.022, 0.022, 0.022), (x, y, 0.19), glow("lamp8", "#bfe8ff", 3.0), bev=0)


def _walls(S, gate, h, t, body, cap, cap_t=0.012, cap_w=None, base=None):
    """Four straight walls round a square yard (half-size S) with a gate gap of half-width `gate` in the front (−Y)
    wall: the body, a coping on top (and a darker plinth); returns the wall runs as (p0, p1)."""
    runs = [((-S, S), (S, S)), ((S, S), (S, -S)), ((-S, -S), (-S, S)), ((S, -S), (gate, -S)), ((-gate, -S), (-S, -S))]
    for (p0, p1) in runs:
        ln = math.dist(p0, p1)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        m = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        bx((ln + t, t, h), (m[0], m[1], h / 2), body, ang, bev=0)
        bx((ln + t + 0.008, cap_w or t + 0.01, cap_t), (m[0], m[1], h + cap_t / 2), cap, ang, bev=0)
        if base:
            bx((ln + t + 0.006, t + 0.008, 0.02), (m[0], m[1], 0.01), base, ang, bev=0)
    return runs


def razor_wire(p0, p1, z, mt, pitch=0.026, amp=0.02):
    """Razor wire along a wall top seen from afar: a zigzag ribbon (one quad per tooth) standing on the coping."""
    ln = math.dist(p0, p1)
    n = max(2, int(ln / pitch))
    ux, uy = (p1[0] - p0[0]) / ln, (p1[1] - p0[1]) / ln
    vs, fs = [], []
    for i in range(n + 1):
        f = i / n
        x, y = p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f
        zz = z + (amp if i % 2 else 0.0)
        vs += [(x - uy * 0.002, y + ux * 0.002, zz), (x + uy * 0.002, y - ux * 0.002, zz + 0.004)]
    for i in range(n):
        fs.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    mesh_obj(vs, fs, mt)


def guard_tower(team, h=0.26, big=True):
    """A concrete watch post: a square shaft with a ladder line, a cabin with dark windows all round under a roof in
    the state's slate, a warm searchlight toward the front and sandbags on the gallery."""
    conc = ev.facade("#8c9095", "#a9acb0", 0.06, 0.4, 0.9, 0.99, lit="#a9acb0", lit_p=0.0, z0=-0.01)
    w = 0.07 if big else 0.055
    bx((w, w, h), (0, 0, h / 2), conc, bev=0)
    bx((w + 0.03, w + 0.03, 0.012), (0, 0, h + 0.006), flat("tower_deck", "#6f747a", 0.6), bev=0)
    cw = w + 0.02
    bx((cw, cw, 0.05), (0, 0, h + 0.012 + 0.025), flat("tower_cab", "#c8c9c4", 0.6), bev=0)
    bx((cw + 0.002, cw + 0.002, 0.018), (0, 0, h + 0.012 + 0.03), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    ev.hip_roof(cw + 0.024, cw + 0.024, 0.035, (0, 0, h + 0.062), flat("roof" + team, ev.slate(team, 1.05), 0.6),
                oh=0.0)
    bx((0.018, 0.016, 0.014), (0, -cw / 2 - 0.01, h + 0.052), flat("lamp_body", "#2b2d31", 0.5), bev=0)
    bx((0.014, 0.004, 0.01), (0, -cw / 2 - 0.019, h + 0.052), glow("search", "#ffe2a0", 3.0), bev=0)
    bx((0.006, 0.004, h - 0.02), (w / 2 * 0.4, -w / 2 - 0.002, h / 2), flat("ladder", "#3a3e44", 0.6), bev=0)


def quonset(team, L=0.36, R=0.15):
    """An arched steel hangar along X: a ribbed half-barrel standing on the ground, end walls, a big ribbed door with
    a band of the state's colour over it, and a light over the door."""
    n = 12
    rib = _ribbed("#8f969d", 0, 0.03, 0.84)
    vs, fs = [], []
    for k in range(n + 1):
        a = math.pi * k / n
        for x in (-L / 2, L / 2):
            vs.append((x, math.cos(a) * R, math.sin(a) * R * 0.95))
    for k in range(n):
        fs.append((2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2))
    _orient(mesh_obj(vs, fs, rib), lambda c: (0.0, c.y, c.z))
    for sx in (-1, 1):  # end walls
        pts = [(sx * L / 2, math.cos(math.pi * k / n) * R * 0.995, math.sin(math.pi * k / n) * R * 0.945)
               for k in range(n + 1)]
        _orient(mesh_obj(pts, [tuple(range(n + 1))], flat("hangar_end", "#a3a8ae", 0.6)), lambda c: (sx, 0.0, 0.0))
    door = _ribbed("#5d636a", 2, 0.012, 0.8)
    bx((0.006, 0.17, 0.11), (L / 2 + 0.003, 0, 0.055), door, bev=0)
    bx((0.008, 0.19, 0.016), (L / 2 + 0.004, 0, 0.118), flat("band" + team, team, 0.6), bev=0)
    bx((0.012, 0.016, 0.008), (L / 2 + 0.008, 0, 0.135), glow("door_lamp", "#ffe2a0", 3.0), bev=0)


def barracks_block(team, w=0.3, d=0.13, floors=2):
    """A barracks block: two storeys of windows (some lit warm), a pitched roof in the state's slate with a dark
    ridge, an entrance canopy, air conditioners."""
    fh = 0.07
    wall = ev.facade("#cbc6b8", "#25313d", 0.04, fh, 0.45, 0.5, lit="#ffd27a", lit_p=0.35, z0=0.0)
    bx((w, d, fh * floors), (0, 0, fh * floors / 2), wall, bev=0)
    bx((w + 0.006, d + 0.006, 0.01), (0, 0, fh * floors), flat("cornice", "#8a9097", 0.6), bev=0)
    ev.gable_roof(w + 0.01, d + 0.01, 0.07, (0, 0, fh * floors), ev.slate(team, 1.05), wall, n=4, eave_z=0.0)
    bx((0.06, 0.03, 0.008), (0, -d / 2 - 0.015, 0.06), flat("canopy", "#5d636a", 0.6), bev=0)
    bx((0.04, 0.006, 0.05), (0, -d / 2 - 0.002, 0.025), flat("door", "#3a3e44", 0.6), bev=0)
    for x in (-0.1, 0.09):
        bx((0.026, 0.014, 0.02), (x, -d / 2 - 0.007, 0.1), flat("ac", "#aeb4bb", 0.5), bev=0)


def helicopter(team):
    """A utility helicopter along X: an olive body with a dark canopy and the state's roundel, a tail boom with a fin
    and a rotor, skids, two long rotor blades."""
    od = flat("olive", "#56603a", 0.6)
    dk = flat("rotor", "#26282b", 0.5)
    uvs(0.03, (0.0, 0, 0.042), od, 10, 6, (1.9, 1.0, 0.9))
    uvs(0.022, (0.04, 0, 0.05), flat("canopy_h", "#1b2533", 0.2), 8, 5, (1.2, 0.95, 0.8))
    rod((-0.04, 0, 0.05), (-0.15, 0, 0.06), 0.009, od, r2=0.005, n=6)
    bx((0.03, 0.004, 0.04), (-0.15, 0, 0.075), od, bev=0)
    bx((0.004, 0.04, 0.004), (-0.152, 0.004, 0.075), dk, bev=0)
    for sy in (-1, 1):
        bx((0.11, 0.006, 0.005), (0.0, sy * 0.03, 0.006), dk, bev=0)
        for x in (-0.03, 0.03):
            beam((x, sy * 0.03, 0.006), (x, sy * 0.018, 0.026), 0.004, dk)
    cy(0.012, 0.012, (0.0, 0, 0.078), dk, 6)
    for a in (0.4, 0.4 + math.pi / 2):
        bx((0.3, 0.012, 0.003), (0.0, 0, 0.086), dk, a, bev=0)
    for sy in (-1, 1):
        cy(0.012, 0.002, (-0.01, sy * 0.028, 0.044), flat("roundel" + team, team, 0.6), 10, rot=(math.pi / 2, 0, 0))


def tank_parked(team):
    """A parked battle tank along X: an olive hull on dark tracks, a turret with a long gun and the state's mark."""
    od = flat("olive", "#56603a", 0.6)
    dk = flat("track", "#26282b", 0.7)
    for sy in (-1, 1):
        bx((0.15, 0.024, 0.03), (0, sy * 0.034, 0.015), dk, bev=0)
    taper_box((0.15, 0.064, 0.026), (0, 0, 0.041), od, (0.92, 0.9))
    taper_box((0.07, 0.054, 0.024), (-0.01, 0, 0.064), od, (0.8, 0.8))
    rod((0.025, 0, 0.066), (0.13, 0, 0.068), 0.0045, od, n=5)
    bx((0.02, 0.02, 0.002), (-0.015, 0, 0.0765), flat("mark" + team, team, 0.6), bev=0)


def army_truck(team):
    """An army truck along X: an olive cab, a canvas-covered bed, six wheels."""
    olive = flat("truck", "#4f5a3a", 0.6)
    bx((0.11, 0.07, 0.012), (-0.02, 0, 0.022), flat("chassis", "#2b2d31", 0.6), bev=0)
    bx((0.05, 0.068, 0.05), (0.06, 0, 0.045), olive, bev=0.006)
    bx((0.006, 0.054, 0.02), (0.086, 0, 0.055), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    bx((0.1, 0.07, 0.04), (-0.035, 0, 0.048), flat("canvas", "#6b7350", 0.8), bev=0.008)
    for dx in (-0.065, -0.03, 0.06):
        for sy in (-1, 1):
            cy(0.016, 0.01, (dx, sy * 0.036, 0.016), flat("tyre", "#1f1f21", 0.9), 8, rot=(math.pi / 2, 0, 0))


def military_base_modern(team):
    """The industrial base (DL6–7), a compound of the late-era maps (reference frame 2): concrete panel walls with
    razor wire, a gatehouse with a striped barrier, four concrete watch posts with slate roofs in the state's tone
    and warm searchlights, an arched steel hangar with a fighter on its apron, a barracks block with lit windows,
    a helipad with a helicopter, a radar mast with a dish, a parked tank and trucks, sandbags and the flag."""
    S = 0.55
    asph = ev.facade("#5d6166", "#5d6166", wf=0.0, brick=True, brick_scale=5.0, mortar_k=0.86)  # concrete slabs
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], asph, 0.006)
    conc = ev.facade("#8c9095", "#aaadb1", 0.07, 0.14, 0.92, 0.99, lit="#aaadb1", lit_p=0.0, z0=-0.02)
    cap = flat("base_cap", "#7d8186", 0.7)
    runs = _walls(S, 0.1, 0.1, 0.04, conc, cap)
    wire = flat("wire", "#4a4d52", 0.5)
    for (p0, p1) in runs:
        razor_wire(p0, p1, 0.112, wire)
    # the gate: two pillars with hazard bands, a guard booth, a striped barrier arm across the road
    haz = ev.hazard(0.02, "#f2c230", "#26272b")
    for sx in (-1, 1):
        bx((0.05, 0.05, 0.14), (sx * 0.125, -S, 0.07), conc, bev=0)
        bx((0.054, 0.054, 0.03), (sx * 0.125, -S, 0.11), haz, bev=0)
    bx((0.06, 0.05, 0.06), (0.17, -S + 0.06, 0.03), flat("booth", "#c8c9c4", 0.6), bev=0)
    bx((0.062, 0.052, 0.02), (0.17, -S + 0.06, 0.044), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    bx((0.074, 0.064, 0.008), (0.17, -S + 0.06, 0.064), flat("roof" + team, ev.slate(team, 1.05), 0.6), bev=0)
    bx((0.2, 0.01, 0.01), (0.0, -S - 0.03, 0.06), ev.hazard_dir(0.03, 0.0, "#e8e6e0", "#c0392b"), bev=0)
    bx((0.02, 0.02, 0.06), (0.1, -S - 0.03, 0.03), flat("barrier_post", "#3a3e44", 0.6), bev=0)
    # a road in from the gate and the parade ground lines
    white = flat("paint_w", "#e8e6e0", 0.6)
    for x in (-0.09, 0.09):
        bx((0.008, 0.36, 0.002), (x, -S + 0.2, 0.0075), white, bev=0)
    # watch posts on the four corners
    for (x, y, big) in ((-S, -S, False), (S, -S, False), (-S, S, True), (S, S, True)):
        build_at(lambda b=big: guard_tower(team, 0.26 if b else 0.2, b), x, y, 0.0)
    # the arched hangar at the back left, a fighter on its apron
    build_at(lambda: quonset(team), -0.24, 0.3, 0.0)
    bx((0.2, 0.2, 0.002), (-0.0, 0.3, 0.0075), flat("apron_c", "#787c82", 0.8), bev=0)
    build_at(ea.fighter, 0.1, 0.3, 0.0, 0.62, z=0.04)
    for sy in (-1, 1):
        cy(0.008, 0.035, (0.12, 0.3 + sy * 0.03, 0.0175), flat("tyre", "#1f1f21", 0.9), 6)
    # the barracks block along the right wall
    build_at(lambda: barracks_block(team), 0.36, -0.04, -math.pi / 2)
    # helipad with a helicopter
    hx, hy = -0.26, -0.2
    cy(0.15, 0.01, (hx, hy, 0.012), flat("pad_c", "#7d8186", 0.7), 20)
    cy(0.125, 0.004, (hx, hy, 0.018), white, 20)
    cy(0.117, 0.006, (hx, hy, 0.019), flat("pad_c", "#7d8186", 0.7), 20)
    for (dx, w, d) in ((-0.035, 0.016, 0.1), (0.035, 0.016, 0.1), (0.0, 0.07, 0.016)):
        bx((w, d, 0.004), (hx + dx, hy, 0.022), white, bev=0)
    build_at(lambda: helicopter(team), hx, hy, 0.5, z=0.024)
    # radar mast with a dish and a red light, the flag
    rx, ry = 0.36, 0.32
    for sx in (-1, 1):
        for sy in (-1, 1):
            beam((rx + sx * 0.04, ry + sy * 0.04, 0.0), (rx + sx * 0.012, ry + sy * 0.012, 0.3), 0.007, flat("steel_dk", "#3a3e44", 0.5))
    for z in (0.1, 0.2):
        bx((0.08 - z * 0.18, 0.08 - z * 0.18, 0.006), (rx, ry, z), flat("steel_dk", "#3a3e44", 0.5), bev=0)
    bx((0.04, 0.04, 0.012), (rx, ry, 0.306), flat("steel_dk", "#3a3e44", 0.5), bev=0)
    ev.hemi(0.06, (rx, ry - 0.005, 0.36), flat("dish", "#e4e6e8", 0.4), 10, 3, (1, 1, 0.45)).rotation_euler = (math.pi / 2 + 0.5, 0, 0.3)
    rod((rx, ry, 0.312), (rx, ry - 0.02, 0.35), 0.006, flat("steel_dk", "#3a3e44", 0.5), n=4)
    ico(0.008, (rx + 0.02, ry + 0.02, 0.31), glow("beacon_red", "#ff4a3a", 3.0))
    ev.flagpole(0.06, 0.04, 0.42, team, 0.12)
    # vehicles: a tank and two trucks parked in a row, sandbags by the gate
    build_at(lambda: tank_parked(team), 0.24, -0.38, math.pi)
    for k in range(2):
        build_at(lambda: army_truck(team), 0.0, -0.12 - k * 0.09, 0.0)
    ev.sandbag_ring(-0.42, 0.0, 0.06, 2)
    for (x, y) in ((0.0, -0.06), (0.15, 0.12)):
        crate(x + 0.09, y + 0.02, 0.04, 0.2, c="#5b6436")


def mech_walker(team, k):
    """A parked walker of the late armies: two digitigrade legs, a wedge torso in steel with a glowing visor, arm
    guns and a missile pod, the state's panel on the hull."""
    st, dk = k["seam"], k["dark"]
    for sy in (-1, 1):
        beam((0.0, sy * 0.035, 0.0), (0.02, sy * 0.035, 0.05), 0.016, dk)  # shin
        beam((0.02, sy * 0.035, 0.05), (-0.015, sy * 0.032, 0.09), 0.018, st)  # thigh
        bx((0.05, 0.022, 0.008), (0.008, sy * 0.035, 0.004), dk, bev=0)  # foot
    taper_box((0.08, 0.09, 0.05), (0.0, 0, 0.115), st, (0.8, 0.85))
    bx((0.06, 0.06, 0.02), (-0.03, 0, 0.13), k["plate"], bev=0)
    bx((0.006, 0.05, 0.01), (0.041, 0, 0.122), k["cyan"], bev=0)  # visor
    bx((0.03, 0.004, 0.026), (0.0, -0.046, 0.11), k["panel"], bev=0)
    bx((0.03, 0.004, 0.026), (0.0, 0.046, 0.11), k["panel"], bev=0)
    for sy in (-1, 1):
        bx((0.03, 0.024, 0.03), (0.0, sy * 0.06, 0.12), dk, bev=0)  # shoulder
        rod((0.0, sy * 0.064, 0.105), (0.075, sy * 0.064, 0.105), 0.008, dk, n=6)  # arm gun
    bx((0.03, 0.04, 0.022), (-0.03, 0.0, 0.15), k["plate"], bev=0)  # missile pod
    for j in range(2):
        bx((0.004, 0.008, 0.008), (-0.0145, -0.008 + j * 0.016, 0.152), k["neon"], bev=0)


def mech_bay(k, team, w=0.3, d=0.2, h=0.2):
    """An open-fronted steel mech bay facing −Y: steel side walls and a back wall with plate seams, a plated roof with
    a light line along its front edge, gantry beams with cold lamps inside, a bay number panel and a walker parked
    inside on a lit floor plate."""
    for sx in (-1, 1):
        bx((0.03, d, h), (sx * (w / 2 - 0.015), 0, h / 2), k["st"], bev=0)
        inset_panel(sx * (w / 2 - 0.015), -d / 2 - 0.001, h * 0.55, 0.018, h * 0.7, 0, -1, k)
    bx((w, 0.03, h), (0, d / 2 - 0.015, h / 2), k["st"], bev=0)
    taper_box((w + 0.02, d + 0.02, 0.03), (0, 0, h + 0.015), k["plate"], (0.9, 0.86))
    bx((w * 0.92, 0.006, 0.008), (0, -d / 2 - 0.006, h - 0.008), k["neon"], bev=0)
    bx((w - 0.06, 0.02, 0.02), (0, -d / 2 + 0.02, h - 0.03), k["plate"], bev=0)  # gantry beam over the opening
    for x in (-0.07, 0.07):
        bx((0.03, 0.012, 0.006), (x, -d / 2 + 0.02, h - 0.043), glow("bay_lamp", "#cfeeff", 2.5), bev=0)
    bx((w - 0.07, d - 0.04, 0.006), (0, 0.0, 0.003), flat("bay_floor", "#2c323b", 0.5), bev=0)
    bx((w - 0.1, 0.004, h * 0.55), (0, d / 2 - 0.032, h * 0.45), glow("bay8", "#9fdcff", 0.9), bev=0)  # lit back wall
    bx((w - 0.09, 0.008, 0.002), (0, -d / 2 + 0.04, 0.0065), k["cyan"], bev=0)
    build_at(lambda: mech_walker(team, k), 0.0, 0.01, -math.pi / 2, 1.0, z=0.006)


def defence_turret(k, team):
    """A corner defence turret: a steel drum with a cold light band, a domed turret with twin barrels pointing out of
    the corner, a sensor fin."""
    cy(0.075, 0.12, (0, 0, 0.06), k["comp"], 8)
    cy(0.078, 0.012, (0, 0, 0.09), k["cyan"], 8)
    cy(0.082, 0.014, (0, 0, 0.127), k["dark"], 8)
    ev.hemi(0.05, (0, 0, 0.134), k["seam"], 8, 3, (1, 1, 0.75))
    for sy in (-0.012, 0.012):
        rod((0.03, sy, 0.15), (0.09, sy, 0.152), 0.0055, k["dark"], n=5)
    bx((0.016, 0.004, 0.012), (0.044, 0, 0.166), k["neon"], bev=0)
    bx((0.012, 0.004, 0.04), (-0.03, 0, 0.18), k["dark"], bev=0)


def military_base_scifi(team):
    """The late-era base (DL8+) in the steel kit of the late citadel (reference frames 2 and 5): composite walls with
    glowing joints and a cold light line along the coping, corner turrets with light bands, a gate with an energy
    barrier, an open mech bay with a walker inside, two lit landing pads (a gunship on one), shield emitter pylons
    with glowing orbs, a steel command block with inset team panels and a holo banner, a dark steel yard laced with
    light strips."""
    kk = steel_kit(team)
    S = 0.55
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], ev.stone("#454a52", 0.8), 0.006)
    # the coping glows in the state's colour (the lit wall tops of reference frame 2 outline the compound from afar)
    runs = _walls(S, 0.11, 0.1, 0.05, kk["comp"], kk["neon"], 0.01, 0.054, kk["dark"])
    for (p0, p1) in runs:  # the light line along the coping and glowing joints down the plates
        ln = math.dist(p0, p1)
        ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        n = (math.sin(ang), -math.cos(ang))
        for side in (-1, 1):
            m = ((p0[0] + p1[0]) / 2 + n[0] * side * 0.0265, (p0[1] + p1[1]) / 2 + n[1] * side * 0.0265)
            bx((ln - 0.04, 0.004, 0.008), (m[0], m[1], 0.075), kk["neon"], ang, bev=0)
        for f in [i / max(1, int(ln / 0.16)) for i in range(1, int(ln / 0.16))]:
            q = (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f)
            bx((0.008, 0.056, 0.06), (q[0], q[1], 0.05), kk["cyan"], ang, bev=0)
    # the gate: two emitter posts and an energy barrier between them
    for sx in (-1, 1):
        bx((0.04, 0.07, 0.16), (sx * 0.13, -S, 0.08), kk["st"], bev=0)
        bx((0.044, 0.074, 0.012), (sx * 0.13, -S, 0.165), kk["dark"], bev=0)
        bx((0.006, 0.076, 0.1), (sx * 0.13, -S, 0.08), kk["cyan"], bev=0)
    for z in (0.03, 0.07, 0.11):
        bx((0.22, 0.004, 0.012), (0, -S, z), glow("curtain", "#1a8fd0", 0.9), bev=0)
    # corner turrets
    for (x, y) in ((-S, -S), (S, -S), (-S, S), (S, S)):  # (the front ones aim down the approach, the back ones out)
        build_at(lambda: defence_turret(kk, team), x, y, -math.pi / 2 if y < 0 else (0.0 if x > 0 else math.pi))
    # the mech bay on the back left, the command block on the back right
    build_at(lambda: mech_bay(kk, team), -0.24, 0.3, 0.0)
    cx_, cy_ = 0.28, 0.3
    bx((0.24, 0.16, 0.16), (cx_, cy_, 0.08), kk["st"], bev=0)
    bx((0.25, 0.17, 0.014), (cx_, cy_, 0.16), kk["plate"], bev=0)
    bx((0.252, 0.172, 0.012), (cx_, cy_, 0.07), kk["seam"], bev=0)
    taper_box((0.14, 0.1, 0.05), (cx_ + 0.01, cy_ + 0.01, 0.192), kk["st"], (0.8, 0.75))
    bx((0.2, 0.006, 0.008), (cx_, cy_ - 0.083, 0.15), kk["neon"], bev=0)
    for x in (-0.07, 0.07):
        inset_panel(cx_ + x, cy_ - 0.081, 0.11, 0.04, 0.07, 0, -1, k=kk)
    bx((0.05, 0.008, 0.06), (cx_, cy_ - 0.083, 0.03), kk["dark"], bev=0)  # door
    bx((0.04, 0.009, 0.05), (cx_, cy_ - 0.084, 0.026), glow("bay8", "#9fdcff", 0.9), bev=0)
    for (x, y) in ((cx_ + 0.06, cy_ + 0.03),):
        rod((x, y, 0.21), (x, y, 0.34), 0.004, kk["cap"], r2=0.0015, n=4)
        bx((0.012, 0.012, 0.012), (x, y, 0.32), kk["cyan"], bev=0)
    uvs(0.022, (cx_ - 0.05, cy_ + 0.03, 0.225), kk["white"], 8, 4, (1, 1, 0.5))
    # holo banner by the command block
    hx, hy = 0.08, 0.16
    cy(0.03, 0.02, (hx, hy, 0.016), kk["plate"], 6)
    cy(0.006, 0.3, (hx, hy, 0.15), flat("mast", "#d0d4da", 0.5), 6)
    bx((0.1, 0.004, 0.13), (hx + 0.056, hy, 0.23), glow("holo" + team, team, 1.0), bev=0)
    bx((0.11, 0.008, 0.008), (hx + 0.056, hy, 0.3), kk["cyan"], bev=0)
    crest = [(0.0, -0.03), (0.022, -0.013), (0.022, 0.022), (0.0, 0.013), (-0.022, 0.022), (-0.022, -0.013)]
    extrude(crest, -0.004, 0.004, glow("holo_crest", "#eef8ff", 1.6), (hx + 0.056, hy, 0.24), (math.pi / 2, 0, 0))
    # two landing pads with lit rims, a gunship on the right one
    for (px, py, r) in ((0.26, -0.24, 0.15), (-0.26, -0.24, 0.13)):
        cy(r, 0.012, (px, py, 0.012), kk["dark"], 16)
        cy(r - 0.014, 0.006, (px, py, 0.02), ev.glow("padring" + team, team, 1.6), 16)
        cy(r - 0.026, 0.008, (px, py, 0.021), flat("pad_sf", "#2c323b", 0.5), 16)
        for a in (0.0, math.pi / 2):
            bx((r * 1.1, 0.008, 0.002), (px, py, 0.0255), kk["cyan"], a + math.pi / 4, bev=0)
    build_at(ea.gunship, 0.26, -0.24, 0.6, 0.5, z=0.06)
    build_at(lambda: hover_lifter(kk, team), -0.26, -0.24, 2.0, z=0.026)
    # shield emitter pylons with glowing orbs, light strips across the yard
    for (x, y) in ((-0.02, -0.06), (0.0, 0.42)):
        bx((0.04, 0.04, 0.2), (x, y, 0.1), kk["comp"], bev=0)
        bx((0.006, 0.042, 0.16), (x, y, 0.1), kk["cyan"], bev=0)
        bx((0.06, 0.06, 0.016), (x, y, 0.205), kk["dark"], bev=0)
        uvs(0.028, (x, y, 0.245), glow("orb" + team, shade(team, 1.05), 1.6), 10, 6)
        torus(0.042, 0.004, (x, y, 0.245), flat("ring_frame", "#c9d0d8", 0.4), (math.pi / 2.6, 0, 0.4), 14, 3)
    for (p0, p1) in (((0.0, -0.53), (0.0, -0.1)), ((-0.5, 0.08), (0.5, 0.08))):
        beam((p0[0], p0[1], 0.0075), (p1[0], p1[1], 0.0075), 0.012, kk["neon"])
    for (x, y, s_) in ((0.46, -0.02, 0.045), (0.42, 0.04, 0.035), (-0.46, -0.02, 0.04)):
        bx((s_, s_ * 1.4, s_), (x, y, s_ / 2 + 0.006), flat("crate8", "#b8862e", 0.6), bev=0)


PROPS = [raider_camp, port, military_base]
ASSETS = {f.__name__: f for f in PROPS}
for _t, _c in ev.TEAMS.items():
    ASSETS["warship_" + _t] = (lambda c: (lambda: warship(c)))(_c)
    ASSETS["destroyer_" + _t] = (lambda c: (lambda: destroyer(c)))(_c)
    ASSETS["cruiser_scifi_" + _t] = (lambda c: (lambda: cruiser_scifi(c)))(_c)
    ASSETS["port_modern_" + _t] = (lambda c: (lambda: port_modern(c)))(_c)
    ASSETS["port_scifi_" + _t] = (lambda c: (lambda: port_scifi(c)))(_c)
    ASSETS["military_base_modern_" + _t] = (lambda c: (lambda: military_base_modern(c)))(_c)
    ASSETS["military_base_scifi_" + _t] = (lambda c: (lambda: military_base_scifi(c)))(_c)


# ------------------------------------------------------------------ export


# the whole-hex props carry many thin poles (stakes, braces, ladders, posts, flagpoles): in a 512 px atlas their faces
# get UV islands under a texel wide that no texel centre falls into, so they bake black — they get a 1024 px atlas
# (like the residences); one of each per map, so the extra texture memory stays small
BAKE_1024 = {"raider_camp", "port", "military_base"}
# the late-era ports, bases and steel ships: hundreds of thin rails, struts, seams and light strips — the tight atlas of
# the residences (flat colours and thin faces on a palette strip, only textured faces unwrapped) keeps them out of the
# black gutter; the ships stay at 512 (small on the screen, several on the map)
SHIPS = ("destroyer_", "cruiser_scifi_")
ATLAS_PROPS = ("port_modern_", "port_scifi_", "military_base_modern_", "military_base_scifi_") + SHIPS


def export(name, out):
    """evolution_assets.export (lowpoly, 512 px bake — 1024 for BAKE_1024 — glTF) with the mesh origin moved to the
    model origin."""
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    ev.lowpoly(objs)
    if name.startswith(ATLAS_PROPS):
        if not name.startswith(SHIPS):
            ev._drop_ground_faces(objs)
        ob = ev.bake_atlas(objs, 512 if name.startswith(SHIPS) else 1024)
    else:
        ob = ea.bake_asset(objs, 1024 if name in BAKE_1024 else 512)
    ob.name = name
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.calc_loop_triangles()
    tris = len(ob.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    for o in bpy.context.scene.objects:  # smoke markers travel with the model as plain nodes (map_view adds smoke)
        if o.type == "EMPTY" and o.name.startswith("smoke"):
            o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    vs = [v.co for v in ob.data.vertices]
    rad = max(math.hypot(v.x, v.y) for v in vs)
    print(f"EXPORTED {name}: tris={tris} radius={rad:.3f} zmin={min(v.z for v in vs):.3f} "
          f"height={max(v.z for v in vs):.3f} mats={[m_.name for m_ in ob.data.materials]}", flush=True)
    return tris, rad


# ------------------------------------------------------------------ contact sheet


def prop_sheet(model_dir, png, cols=None, tile=1.0, res=3200, rot=0.0):
    """One row of grass hex tiles with a prop on each (raider_camp, port, military_base left → right)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    names = list(ASSETS)
    cols = cols or list(range(1, len(names) + 1))
    sp = max(2.05 * tile, 0.75)
    for ci, n in enumerate(cols):
        x = (ci - (len(cols) - 1) / 2) * sp
        kit.hex_prism("tile", (x, 0, 0), tile, 0.18, grass, dirt, 0.03)
        before = {o.name for o in bpy.context.scene.objects}
        bpy.ops.import_scene.gltf(filepath=os.path.join(model_dir, f"{names[n - 1]}.glb"))
        for o in bpy.context.scene.objects:
            if o.name not in before and o.parent is None:
                o.matrix_world = Matrix.Translation((x, 0, 0)) @ Matrix.Rotation(math.radians(rot), 4, "Z") @ o.matrix_world
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
        rot = float(rest[rest.index("--rot") + 1]) if "--rot" in rest else 0.0
        prop_sheet(out, png, cols, tile, res, rot)
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
