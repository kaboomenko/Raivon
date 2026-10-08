"""Whole-hex props for special hex kinds (raider camp on a wild hex, port, military base).

Builds and exports to OUT (default game/assets/models):
  raider_camp.glb     marauder camp: серые шатры, частокол, дым костра, флажок с рваным полотнищем
  port.glb            fishing / trade port: water cove, pier toward +X, boathouse, moored boats, crane
  military_base.glb   early-era garrison: low stone-wall compound, barracks, tents, training yard, white banner

Run:   python3 tools/blender/prop_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/prop_assets.py game/assets/models --sheet OUT.png [--cols 1,2,3] [--tile 1.0]
       [--res 3200] [--rot DEG]  (--rot turns every model around Z, to check how it reads from another side)

Conventions (same as evolution_assets.py): Z up, base on Z=0, origin = hex centre, 1 hex = flat-top
hexagon of circumradius 1.0, front faces −Y. Unlike towers these props fill the WHOLE hex: everything stays
within radius ~0.85. Team-neutral. Procedural colours are baked into one 512 px texture; emissive materials
(camp fire, lanterns) stay separate so they keep glowing in Godot.
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
                              glow, build_at, mesh_obj, extrude, shade, WOOD_D, WOOD_L, STONE,
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


def planks(color, row=0.014, length=0.12, deck=False):
    """Boards in rows with dark seams and staggered butts (object space): rows follow Z on hull sides and walls,
    run along X on a deck (deck=True). Every board a slightly different tone."""
    key = ("planks", color, row, length, deck)
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
    tube((x, y, z - 0.08), (x, y, z), 0.006, wood, n=4)
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
        tube((p[0][0], p[0][1], 0.03), (p[1][0], p[1][1], H - 0.03), 0.006, wood, n=4)
        tube((p[1][0], p[1][1], 0.03), (p[0][0], p[0][1], H - 0.03), 0.006, wood, n=4)
    bx((0.19, 0.19, 0.018), (0, 0, H), plank, bev=0)
    for k in range(4):  # rail of sticks round the deck
        a, b = tops[(0, 1, 3, 2)[k]], tops[(1, 3, 2, 0)[k]]
        tube((a[0], a[1], H + 0.065), (b[0], b[1], H + 0.065), 0.006, wood, n=4)
    mesh_obj([(-0.1, 0.1, H + 0.14), (0.1, 0.1, H + 0.14), (0.11, -0.11, H + 0.1), (-0.11, -0.11, H + 0.1)],
             [(0, 1, 2, 3)], hide)
    for sx in (-1, 1):  # ladder up the front
        tube((sx * 0.032, -0.2, -0.01), (sx * 0.032, -0.1, H + 0.01), 0.006, wood, n=4)
    for k in range(4):
        f = (k + 0.6) / 4.6
        y, z = -0.2 + 0.1 * f, H * f
        tube((-0.034, y, z), (0.034, y, z), 0.004, wood, n=3)
    torch(0.075, -0.075, H + 0.13, torch_wood)


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
        tube((x, y - 0.01, 0.24), (x, y - 0.045, 0.24), 0.005, wd2, n=3)  # bracket
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
            tube((sx * 0.1, y1, -0.01), (sx * 0.1, y1, h_ * 0.7), 0.006, wd2, n=4)
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
        tube((fx + math.cos(a) * 0.11, fy + math.sin(a) * 0.11, -0.005), (fx, fy, 0.25), 0.007, wd2, n=4)
    pot = flat("cauldron", "#2b2a2c", 0.5)
    tube((fx, fy, 0.25), (fx, fy, 0.16), 0.003, pot, n=3)
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
        tube((-0.07, 0.0, -0.01), (-0.07, 0.0, 0.2), 0.008, wd2, n=4)
        tube((0.07, 0.0, -0.01), (0.07, 0.0, 0.2), 0.008, wd2, n=4)
        tube((-0.085, 0.0, 0.19), (0.085, 0.0, 0.19), 0.007, wd2, n=4)
        tube((-0.075, 0.0, 0.035), (0.075, 0.0, 0.035), 0.006, wd2, n=4)
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
    rope = flat("rope", "#e8dcc0", 0.8)
    rod((mx, 0, 0.5), (0.2, 0, 0.08), 0.003, rope, n=3)  # forestay
    rod((mx, 0, 0.5), (-0.19, 0, 0.08), 0.003, rope, n=3)  # backstay
    crate(-0.1, 0.02, 0.045, 0.3, z=0.068)
    barrel(-0.1, -0.035, 0.018, 0.04, z=0.068)


def rowboat():
    body = tex("wood", "#8a6440", 3.0)
    deck = tex("wood", "#5e4126", 3.0)
    hull(0.22, 0.1, 0.05, body, deck, flat("trim_blue", TRIM_BLUE, 0.6))
    bx((0.016, 0.085, 0.01), (0.0, 0, 0.05), tex("wood", WOOD_L, 3.0), bev=0)
    oar = tex("wood", "#c9a06a", 3.0)
    for sy in (-1, 1):
        rod((-0.03, sy * 0.03, 0.055), (0.07, sy * 0.13, 0.012), 0.004, oar, n=4)
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
    rod((0.0, 0.0, 0.44), (0.27, 0.0, 0.48), 0.003, rope, n=3)
    rod(jib1, (0.27, 0.0, 0.2), 0.003, rope, n=3)
    cy(0.03, 0.04, (-0.035, 0.0, 0.13), wl, 8, rot=(math.pi / 2, 0, 0))  # winch drum
    torus(0.03, 0.005, (-0.035, 0.0, 0.13), rope, rot=(math.pi / 2, 0, 0), seg=8, mseg=3)
    # hanging bundle (net of sacks)
    uvs(0.045, (0.27, 0.0, 0.17), tex("plaster", "#b9a27a", 3.0), 8, 5, (1.0, 1.0, 0.9))
    for a in (0.5, 2.6, 4.6):
        rod((0.27, 0.0, 0.21), (0.27 + math.cos(a) * 0.04, math.sin(a) * 0.04, 0.17), 0.0035, rope, n=3)


def _cove(quay, water_c=WATER, shallow_c="#79c1df", joints=False):
    """The port's water cove opening at the +X edge with a lighter rim and a quay along the land side; `joints`
    caps the joints between the quay stones (no dark notches where two runs meet at an angle)."""
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
    capped = set()
    for k in range(len(pts)):
        p0, p1 = pts[k], pts[(k + 1) % len(pts)]
        _, c0 = clamp_hex((p0[0] * 1.03, p0[1] * 1.03), HEX_R)
        _, c1 = clamp_hex((p1[0] * 1.03, p1[1] * 1.03), HEX_R)
        if c0 and c1:
            continue  # this stretch runs along the hex edge: open sea
        beam((p0[0], p0[1], 0.02), (p1[0], p1[1], 0.02), 0.05, quay)
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        dx, dy = mx - cx, my
        dl = math.hypot(dx, dy)
        q0 = (p0[0] - dx / dl * 0.04, p0[1] - dy / dl * 0.04, 0.014)
        q1 = (p1[0] - dx / dl * 0.04, p1[1] - dy / dl * 0.04, 0.014)
        beam(q0, q1, 0.025, shallow)
        if joints:  # one cap per joint, just above the overlapping stone tops (no coplanar faces left in view)
            for (x, y) in (p0, p1):
                if (round(x, 4), round(y, 4)) in capped:
                    continue
                capped.add((round(x, 4), round(y, 4)))
                d_ = math.hypot(x - cx, y)
                flat_poly(ev.ngon(0.028, 6, 0.0), 0.047, quay).location = (x, y, 0.0)
                flat_poly(ev.ngon(0.02, 6, 0.0), 0.028, shallow).location = (x - (x - cx) / d_ * 0.04,
                                                                             y - y / d_ * 0.04, 0.0)
    return cx


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
    fy = -0.0625
    mesh_obj([(-0.022, fy, 0.03), (0.022, fy, 0.03), (0.022, fy, 0.1), (0.0, fy - 0.001, 0.115), (-0.022, fy, 0.1)],
             [(0, 1, 2, 3, 4)], planks("#4a2d17", 0.014, 0.3))
    lit = ev.win_lit()
    for z in (0.19, 0.27):
        mesh_obj([(-0.009, -0.0605, z), (0.009, -0.0605, z), (0.009, -0.0605, z + 0.035), (-0.009, -0.0605, z + 0.035)],
                 [(0, 1, 2, 3)], lit)


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
    tube((W1 / 2 + 0.09, 0, z1 + 0.04), (W1 / 2 + 0.09, 0, 0.1), 0.003, rope, n=3)
    sack(W1 / 2 + 0.09, 0, 0.8, 0, z=0.04)


def fish_stall():
    """Quay stall facing −Y: four posts, a counter with the catch and a basket, a red-and-cream striped awning."""
    wd = tex("wood", "#6a4327", 2.5)
    for sx in (-1, 1):
        for sy in (-1, 1):
            tube((sx * 0.075, sy * 0.04, -0.005), (sx * 0.075, sy * 0.04, 0.13 + (0.025 if sy > 0 else 0.0)), 0.006, wd,
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
    deck = planks("#a8814f", 0.02, 0.15, True)
    post = tex("wood", "#5a3e27", 2.0)
    py, pw, z = -0.03, 0.15, 0.075
    x0, x1 = 0.02, 0.79
    for sy in (-1, 1):
        beam((x0, py + sy * 0.05, z - 0.02), (x1, py + sy * 0.05, z - 0.02), 0.02, post)
    n = 17
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
    tube((0.36, py + 0.085, 0.11), (0.3, 0.12, 0.07), 0.003, rope, n=3)
    tube((0.5, py - 0.085, 0.11), (0.42, -0.25, 0.05), 0.003, rope, n=3)
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
            tube((dx, -0.02, 0.1 + dz), (dx + 0.01, -0.08, 0.1 + dz + 0.012), 0.003, ar, n=3)
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
    tube((x - w / 2 - 0.012, y - 0.006, z_top + 0.004), (x + w / 2 + 0.012, y - 0.006, z_top + 0.004), 0.005, rod_m, n=4)
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
    for sx in (-1, 1):  # leaves swung open into the yard
        hx = gx0 + sx * gate
        a = math.radians(72)
        cxl, cyl = hx - sx * math.cos(a) * gate * 0.48, -S + 0.03 + math.sin(a) * gate * 0.48
        bx((gate * 0.96, 0.014, 0.17), (cxl, cyl, 0.085), door, -sx * a, bev=0)
        bx((gate * 0.97, 0.018, 0.012), (cxl, cyl, 0.13), band, -sx * a, bev=0)
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
    ship_castle(xs0, xs1, 0.145, 0.1, 0.078, 0.2, 0.225, L, W, castle_w, teamc, floor)
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
    fy = -0.06
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


def _turret(x, z, steel, dark, aim=1):
    """A gun turret on the deck centreline: a squat round mount, an angled shield and a twin barrel toward ±X."""
    cy(0.032, 0.026, (x, 0, z + 0.013), steel, 10)
    bx((0.05, 0.05, 0.022), (x + aim * 0.006, 0, z + 0.035), steel, bev=0.004)
    for sy in (-0.008, 0.008):
        beam((x + aim * 0.02, sy, z + 0.036), (x + aim * 0.085, sy, z + 0.04), 0.0045, dark)


def destroyer(team):
    """A steel destroyer of the industrial and modern eras (DL6–7) along X (bow at +X): a grey hull with a team
    boot stripe and hull number, a stepped bridge with windows, a raked funnel, a lattice mast with a radar bar,
    turrets fore and aft and the state ensign at the stern."""
    grey = flat("ship_grey", "#7b828a", 0.55)
    deck = flat("ship_deck", "#5a6067", 0.7)
    dark = flat("ship_dark", "#2c3035", 0.5)
    stripe = flat("hull_stripe" + team, ev.slate(team, 1.1), 0.6)
    hull(0.72, 0.16, 0.085, grey, deck, stripe)
    win = flat("bridge_win", "#1c2a38", 0.2)
    z0 = 0.085
    bx((0.2, 0.1, 0.05), (-0.02, 0, z0 + 0.025), grey, bev=0.006)  # main deckhouse
    bx((0.11, 0.085, 0.045), (0.04, 0, z0 + 0.072), grey, bev=0.006)  # bridge
    bx((0.012, 0.075, 0.014), (0.096, 0, z0 + 0.08), win, bev=0)
    for sy in (-1, 1):
        bx((0.08, 0.004, 0.012), (0.04, sy * 0.043, z0 + 0.08), win, bev=0)
    bx((0.07, 0.07, 0.012), (0.03, 0, z0 + 0.1), deck, bev=0.003)
    rod((-0.07, 0, z0 + 0.05), (-0.09, 0, z0 + 0.13), 0.022, grey, n=10)  # raked funnel
    cy(0.023, 0.012, (-0.091, 0, z0 + 0.13), dark, 10)
    rod((0.02, 0, z0 + 0.1), (0.015, 0, z0 + 0.24), 0.006, dark, n=5)  # mast
    for z, w in ((0.17, 0.07), (0.215, 0.045)):
        bx((0.008, w, 0.006), (0.017, 0, z0 + z), dark, bev=0)
    bx((0.02, 0.07, 0.012), (0.015, 0, z0 + 0.245), grey, bev=0.002)  # radar bar
    _turret(0.2, z0, grey, dark, 1)
    _turret(-0.2, z0, grey, dark, -1)
    for k in range(3):  # hull number
        bx((0.018, 0.004, 0.028), (0.24 + k * 0.024, -0.081, 0.055), flat("hull_no", "#e8e6e0", 0.6), bev=0)
        bx((0.018, 0.004, 0.028), (0.24 + k * 0.024, 0.081, 0.055), flat("hull_no", "#e8e6e0", 0.6), bev=0)
    rod((-0.33, 0, z0), (-0.33, 0, z0 + 0.1), 0.004, dark, n=4)  # ensign staff
    bx((0.06, 0.004, 0.04), (-0.3, 0, z0 + 0.08), flat("flag" + team, team, 0.7), bev=0)
    bx((0.022, 0.006, 0.015), (-0.3, 0, z0 + 0.08), flat("emblem", "#f3efe6", 0.6), bev=0)


def cruiser_scifi(team):
    """A hover cruiser of the late era (DL8+) along X (bow at +X): a dark faceted hull riding on a glowing skirt,
    team-coloured neon strips, a wedge bridge, a missile block and a rail gun, an energy glow at the stern."""
    hullc = flat("sf_hull", "#2b3240", 0.35)
    plate = flat("sf_plate", "#454e5e", 0.4)
    neon = ev.glow("team" + team, team, 3.0)
    cyan = ev.glow("engine", "#7fe6ff", 4.0)
    hull(0.74, 0.18, 0.075, hullc, plate)
    for sy in (-1, 1):  # neon strips along both sides
        bx((0.46, 0.006, 0.008), (0.0, sy * 0.088, 0.05), neon, bev=0)
        bx((0.26, 0.006, 0.006), (-0.04, sy * 0.084, 0.025), cyan, bev=0)
    z0 = 0.075
    for k, (x, w, h, d) in enumerate(((0.0, 0.24, 0.05, 0.12), (-0.03, 0.15, 0.04, 0.09))):  # stepped wedge citadel
        bx((w, d, h), (x, 0, z0 + h / 2 + k * 0.05), hullc if k == 0 else plate, bev=0.008)
    bx((0.01, 0.07, 0.012), (0.042, 0, z0 + 0.075), cyan, bev=0)  # bridge glazing
    rod((-0.05, 0, z0 + 0.09), (-0.05, 0, z0 + 0.2), 0.005, plate, n=5)  # sensor spire
    uvs(0.012, (-0.05, 0, z0 + 0.205), neon, 6, 4)
    bx((0.07, 0.07, 0.03), (0.2, 0, z0 + 0.015), plate, bev=0.005)  # missile block
    for i in range(3):
        for j in range(3):
            bx((0.012, 0.012, 0.004), (0.18 + i * 0.02, -0.02 + j * 0.02, z0 + 0.031), neon, bev=0)
    beam((-0.2, 0, z0 + 0.02), (-0.08, 0, z0 + 0.03), 0.009, plate)  # rail gun, aft-facing
    cy(0.026, 0.02, (-0.2, 0, z0 + 0.01), hullc, 10)
    bx((0.012, 0.11, 0.03), (-0.37, 0, 0.04), cyan, bev=0)  # engine glow at the stern
    bx((0.05, 0.004, 0.03), (-0.31, 0, z0 + 0.055), flat("flag" + team, team, 0.7), bev=0)
    rod((-0.34, 0, z0), (-0.34, 0, z0 + 0.07), 0.003, plate, n=4)


def _containers(spots, team, seed=3):
    """Stacks of shipping containers (one in the state's colour per stack), 1–3 high."""
    rnd = random.Random(seed)
    cols = [team, "#c23a2b", "#2f6f8f", "#d9962a", "#3f7a3a", "#8a8f96"]
    for (x, y, rz) in spots:
        for k in range(rnd.randint(1, 3)):
            c = cols[0] if k == 0 else rnd.choice(cols[1:])
            bx((0.13, 0.055, 0.052), (x, y, 0.03 + k * 0.053), flat("cont" + c, c, 0.55), rz, bev=0.004)


def port_modern(team):
    """The industrial port (DL6–7): a concrete quay and pier, a gantry container crane in the state's colour over the
    water, container stacks, a cargo ship with containers on deck, a big shed with roller doors, lamps."""
    conc = flat("conc_quay", "#8e9298", 0.85)
    _cove(conc, "#3a7fae", "#6aaecc")
    ev.pad(0.36, flat("conc_yard", "#83878d", 0.85), 0.008, 12, 0.08, 6, 1.0, 1.25)
    py = -0.03
    bx((0.78, 0.16, 0.05), (0.41, py, 0.05), conc, bev=0.004)  # concrete pier to the edge
    for i in range(6):
        cy(0.012, 0.03, (0.12 + i * 0.13, py - 0.07, 0.09), flat("bollard", "#2b2d31", 0.5), 8)
    steel = flat("crane" + team, ev.shade(team, 0.9), 0.45)
    dk = flat("crane_dk", "#2c3036", 0.5)
    gx = 0.36
    for sx in (-1, 1):  # the gantry's four legs and their sills
        for sy in (-1, 1):
            beam((gx + sx * 0.07, py + sy * 0.07, 0.07), (gx + sx * 0.06, py + sy * 0.06, 0.42), 0.014, steel)
        beam((gx + sx * 0.07, py - 0.07, 0.42), (gx + sx * 0.07, py + 0.07, 0.42), 0.012, steel)
    bx((0.72, 0.05, 0.035), (gx + 0.1, py, 0.45), steel, bev=0.003)  # boom out over the water, back-reach inland
    bx((0.06, 0.06, 0.05), (gx + 0.05, py, 0.5), dk, bev=0.004)  # operator cab
    beam((gx - 0.1, py, 0.45), (gx + 0.02, py, 0.62), 0.008, dk)
    beam((gx + 0.02, py, 0.62), (gx + 0.42, py, 0.46), 0.005, dk)  # stay
    bx((0.12, 0.05, 0.05), (gx + 0.36, py, 0.3), flat("cont" + team, team, 0.55), bev=0.004)  # a box on the hook
    beam((gx + 0.36, py, 0.33), (gx + 0.36, py, 0.44), 0.003, dk)
    # cargo ship moored on the +Y side
    def ship():
        hull(0.6, 0.15, 0.08, flat("hull_cargo", "#3b4048", 0.6), flat("deck_cargo", "#7a3a2c", 0.7),
             flat("boot" + team, team, 0.6))
        for i in range(3):
            for j in range(2):
                c = [team, "#c23a2b", "#d9962a"][(i + j) % 3]
                bx((0.11, 0.05, 0.045), (-0.08 + i * 0.12, -0.028 + j * 0.056, 0.105), flat("cont" + c, c, 0.55), bev=0.003)
        bx((0.08, 0.12, 0.09), (-0.22, 0, 0.125), flat("bridge_w", "#e8e6e0", 0.5), bev=0.006)
        bx((0.09, 0.13, 0.012), (-0.22, 0, 0.175), flat("bridge_r", "#3b4048", 0.5), bev=0)
        bx((0.006, 0.1, 0.014), (-0.18, 0, 0.15), flat("bridge_g", "#1d2a38", 0.2), bev=0)
        cy(0.02, 0.07, (-0.26, 0, 0.2), flat("funnel" + team, team, 0.5), 10)
    build_at(ship, 0.46, 0.2, 0.0, z=0.004)
    _containers([(-0.24, -0.28, 0.0), (-0.24, -0.2, 0.0), (-0.08, -0.3, 0.1), (-0.08, -0.22, 0.1), (0.06, -0.3, 0.0),
                 (-0.04, 0.16, 1.57), (0.04, 0.2, 1.57)], team)
    # the shed: corrugated walls, a team band, roller doors
    def shed():
        w, d, h = 0.4, 0.26, 0.2
        bx((w, d, h), (0, 0, h / 2), ev.facade("#9aa1a8", "#5b636c", 0.05, 0.05, 0.3, 0.2, lit_p=0.1), bev=0.006)
        bx((w + 0.01, d + 0.01, 0.03), (0, 0, h - 0.02), flat("band" + team, team, 0.6), bev=0)
        hip_roof(w, d, 0.05, (0, 0, h), flat("shed_roof", "#5b636c", 0.6), oh=0.01)
        for x in (-0.1, 0.1):
            bx((0.12, 0.012, 0.13), (x, -d / 2 - 0.004, 0.065), flat("roller", "#c8ccd1", 0.5), bev=0)
    build_at(shed, -0.36, 0.32, -0.1)
    for (x, y) in ((0.0, -0.12), (0.2, 0.08), (-0.36, -0.06)):
        ev.street_lamp(x, y, 0.22, True)


def port_scifi(team):
    """The late-era port (DL8+): a dark plated quay with neon edges, a glowing pier, a hover cruiser at berth, a
    control tower with a light ring, white cargo pods and a landing pad in the state's colour."""
    plate = flat("sf_quay", "#3e434b", 0.5)
    _cove(plate, "#2f6e9c", "#5aa0c4")
    ev.pad(0.36, flat("sf_yard", "#4a4f58", 0.6), 0.008, 12, 0.08, 6, 1.0, 1.25)
    neon = ev.glow("neon" + team, team, 3.0)
    cyan = ev.glow("cyan", "#14d2ff", 2.5)
    py = -0.03
    bx((0.78, 0.15, 0.04), (0.41, py, 0.05), plate, bev=0.004)
    for sy in (-1, 1):
        bx((0.76, 0.008, 0.008), (0.41, py + sy * 0.077, 0.066), neon, bev=0)
    build_at(lambda: cruiser_scifi(team), 0.46, 0.22, 0.0, 0.75, z=0.004)
    def tower():
        cy(0.07, 0.5, (0, 0, 0.25), flat("sf_tower", "#59606a", 0.4), 10)
        cy(0.074, 0.014, (0, 0, 0.3), neon, 10)
        cy(0.12, 0.05, (0, 0, 0.52), flat("sf_cab", "#2b3240", 0.3), 12)
        cy(0.122, 0.012, (0, 0, 0.53), cyan, 12)
        rod((0, 0, 0.55), (0, 0, 0.68), 0.006, flat("mast", "#d0d4da", 0.5), n=5)
        ico(0.014, (0, 0, 0.69), neon)
    build_at(tower, -0.42, 0.3)
    pod = flat("pod", "#e8ecf0", 0.35)
    for i, (x, y) in enumerate(((-0.22, -0.26), (-0.1, -0.3), (0.02, -0.26), (-0.16, -0.16), (-0.04, -0.18))):
        bx((0.08, 0.06, 0.06), (x, y, 0.04), pod, 0.1 * i, bev=0.016)
        bx((0.082, 0.008, 0.008), (x, y - 0.031, 0.05), neon if i % 2 else cyan, 0.1 * i, bev=0)
    cy(0.11, 0.012, (-0.1, 0.18, 0.012), flat("pad_sf", "#2c323b", 0.5), 16)
    cy(0.1, 0.006, (-0.1, 0.18, 0.02), ev.glow("padring" + team, team, 1.6), 16)
    cy(0.085, 0.008, (-0.1, 0.18, 0.021), flat("pad_sf", "#2c323b", 0.5), 16)


def _compound_walls(S, wall, cap, h=0.1, gate=0.12):
    """Four straight walls round a square yard with a gate gap in the front (−Y) wall."""
    for (x0, y0, x1, y1) in ((-S, S, S, S), (S, S, S, -S), (-S, -S, -S, S), (S, -S, gate, -S), (-gate, -S, -S, -S)):
        ln = math.dist((x0, y0), (x1, y1))
        ang = math.atan2(y1 - y0, x1 - x0)
        bx((ln, 0.045, h), ((x0 + x1) / 2, (y0 + y1) / 2, h / 2), wall, ang, bev=0.004)
        bx((ln, 0.055, 0.014), ((x0 + x1) / 2, (y0 + y1) / 2, h + 0.007), cap, ang, bev=0)


def military_base_modern(team):
    """The industrial base (DL6–7): a concrete-walled compound, two steel watchtowers, a quonset hangar with the
    state's band, a helipad with an H, parked trucks, a sandbag nest, a flag."""
    S = 0.55
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], flat("base_asph", "#5d6166", 0.85), 0.006)
    conc = flat("base_conc", "#a3a6aa", 0.8)
    _compound_walls(S, conc, flat("base_cap", "#7d8186", 0.7))
    steel = flat("steel_dk", "#3a3e44", 0.5)
    for (x, y) in ((-S, -S), (S, S)):  # watchtowers on two corners
        for sx in (-1, 1):
            for sy in (-1, 1):
                beam((x + sx * 0.05, y + sy * 0.05, 0.0), (x + sx * 0.035, y + sy * 0.035, 0.3), 0.008, steel)
        bx((0.11, 0.11, 0.07), (x, y, 0.335), flat("tower_cab", "#6f747a", 0.6), bev=0.004)
        bx((0.13, 0.13, 0.012), (x, y, 0.376), steel, bev=0)
        bx((0.112, 0.006, 0.02), (x, y - 0.056, 0.34), flat("cab_glass", "#1d2a38", 0.2), bev=0)
    def hangar():  # a half-cylinder of ribbed steel with end walls and a door
        cy(0.17, 0.42, (0, 0, 0.0), flat("hangar", "#8a9097", 0.55), 16, rot=(0, math.pi / 2, 0))  # half sunk: an arch
        for x in (-0.21, 0.21):
            cy(0.172, 0.012, (x, 0, 0.0), flat("band" + team, team, 0.6), 16, rot=(0, math.pi / 2, 0))
        bx((0.012, 0.16, 0.12), (-0.215, 0, 0.06), flat("hangar_door", "#3a3e44", 0.6), bev=0)
    build_at(hangar, -0.12, 0.3)
    # helipad
    cy(0.16, 0.01, (0.28, -0.22, 0.012), flat("pad_c", "#7d8186", 0.7), 20)
    cy(0.13, 0.004, (0.28, -0.22, 0.018), flat("pad_w", "#e8e6e0", 0.6), 20)
    cy(0.122, 0.006, (0.28, -0.22, 0.019), flat("pad_c", "#7d8186", 0.7), 20)
    for (dx, w, d) in ((-0.035, 0.016, 0.1), (0.035, 0.016, 0.1), (0.0, 0.07, 0.016)):
        bx((w, d, 0.004), (0.28 + dx, -0.22, 0.022), flat("pad_w", "#e8e6e0", 0.6), bev=0)
    # parked trucks
    olive = flat("truck", "#4f5a3a", 0.6)
    for (x, y) in ((-0.3, -0.2), (-0.3, -0.06)):
        bx((0.16, 0.07, 0.06), (x, y, 0.045), olive, bev=0.006)
        bx((0.05, 0.068, 0.05), (x + 0.1, y, 0.04), olive, bev=0.006)
        bx((0.006, 0.05, 0.02), (x + 0.125, y, 0.05), flat("cab_glass", "#1d2a38", 0.2), bev=0)
        for dx in (-0.05, 0.03, 0.1):
            for sy in (-1, 1):
                cy(0.016, 0.01, (x + dx, y + sy * 0.036, 0.016), flat("tyre", "#1f1f21", 0.9), 8, rot=(math.pi / 2, 0, 0))
    ev.sandbag_ring(0.0, -0.42, 0.07, 2)
    ev.flagpole(0.3, 0.3, 0.42, team, 0.12)


def military_base_scifi(team):
    """The late-era base (DL8+): a dark plated compound with neon wall strips, a wedge hangar with a glowing door, a
    parked walker, a pad with a hover gunship, sensor masts."""
    S = 0.55
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], flat("sf_ground", "#3e434b", 0.6), 0.006)
    neon = ev.glow("neon" + team, team, 3.0)
    cyan = ev.glow("cyan", "#14d2ff", 2.5)
    _compound_walls(S, flat("sf_wall", "#59606a", 0.45), neon, 0.09)
    def hangar():
        side_w = 0.42
        extrude([(-0.2, 0.0), (0.2, 0.0), (0.14, 0.2), (-0.14, 0.2)], -side_w / 2, side_w / 2,
                flat("sf_hangar", "#4a515c", 0.4), (0, 0, 0), (math.pi / 2, 0, 0))
        bx((0.2, 0.012, 0.12), (0, -0.215, 0.07), cyan, bev=0)
        bx((0.3, 0.44, 0.012), (0, 0, 0.205), flat("sf_roof", "#2b3240", 0.4), bev=0.004)
        bx((0.006, 0.42, 0.008), (0.15, 0, 0.2), neon, bev=0)
        bx((0.006, 0.42, 0.008), (-0.15, 0, 0.2), neon, bev=0)
    build_at(hangar, -0.22, 0.26, math.pi / 2)
    cy(0.17, 0.012, (0.26, -0.2, 0.012), flat("pad_sf", "#2c323b", 0.5), 20)
    cy(0.15, 0.006, (0.26, -0.2, 0.02), ev.glow("padring" + team, team, 1.6), 20)
    cy(0.135, 0.008, (0.26, -0.2, 0.021), flat("pad_sf", "#2c323b", 0.5), 20)
    build_at(ea.gunship, 0.26, -0.2, 0.6, 0.5, z=0.03)
    for (x, y) in ((0.36, 0.34), (-0.4, -0.38)):
        rod((x, y, 0.0), (x, y, 0.32), 0.008, flat("mast", "#d0d4da", 0.5), n=5)
        uvs(0.02, (x, y, 0.33), cyan, 8, 5)


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
    for o in bpy.context.scene.objects:  # smoke markers travel with the model as plain nodes (map_view adds smoke)
        if o.type == "EMPTY" and o.name.startswith(("smoke", "flag")):
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
