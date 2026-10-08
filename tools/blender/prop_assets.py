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
    """Sharpened log: base at (x, y, -0.01), leaning by `lean` (dx, dy) at the top, pointed tip."""
    p0 = Vector((x, y, -0.01))
    p1 = Vector((x + lean[0], y + lean[1], h))
    d = (p1 - p0).normalized()
    rod(tuple(p0), tuple(p1), r, mt, n=n)
    rod(tuple(p1), tuple(p1 + d * r * 2.4), r, tip, r2=0.001, n=n)


def ridge_tent(L, W, h, canvas, patches=(), door=True, sticks=True, seed=0):
    """A-frame canvas tent at the origin: ridge along Y, opening on the −Y gable, patches on the slopes."""
    prism_roof("tent", L, W, h, (0, 0, 0), canvas, overhang=0.0, rot_z=math.pi / 2)
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


def cone_tent(r, h, canvas, patches=(), seed=0):
    """Round marauder tent (yurt-like cone), a dark doorway toward −Y, poles crossing above the apex."""
    cn(r, h, (0, 0, h / 2), canvas, 8, rot=(0, 0, math.pi / 8))
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
    def b():
        cy(r, h, (0, 0, h / 2), tex("wood", c, 3.0), 8, r2=r)
        cy(r * 1.08, h * 0.14, (0, 0, h / 2), tex("wood", c, 3.0), 8)
        for zz in (h * 0.14, h * 0.86):
            cy(r * 1.03, h * 0.08, (0, 0, zz), flat("hoop", IRON, 0.6), 8)
        cy(r * 0.85, 0.004, (0, 0, h + 0.001), tex("wood", shade(c, 1.2), 3.0), 8)
    if lie is None:
        build_at(b, x, y, z=z)
    else:
        build_at(b, x, y, lie, tilt=(0, math.pi / 2), z=z + r)


def sack(x, y, s=1.0, rz=0.0, z=0.0, c="#b9a27a"):
    m = tex("plaster", c, 3.0)
    o = uvs(0.04 * s, (x, y, z + 0.032 * s), m, 8, 5, (1.0, 0.8, 0.85))
    o.rotation_euler.z = rz
    cy(0.014 * s, 0.018 * s, (x, y, z + 0.068 * s), m, 6, r2=0.008 * s)


def rope_coil(x, y, r=0.035, z=0.0):
    m = tex("plaster", "#cdb88c", 4.0)
    torus(r, 0.008, (x, y, z + 0.008), m, seg=10, mseg=4)
    torus(r * 0.7, 0.008, (x, y, z + 0.018), m, seg=8, mseg=4)


def spear(p0, p1, wood, iron, r=0.006):
    rod(p0, p1, r, wood, n=4)
    d = (Vector(p1) - Vector(p0)).normalized()
    rod(p1, tuple(Vector(p1) + d * 0.04), 0.011, iron, r2=0.001, n=4)


def weapon_rack(x, y, rz, n_spears=4, shields=0, shield_c=None, axes=0):
    """A-frame weapon rack along local X: spears leaning on a bar, optional round shields and axes."""
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        wl = tex("wood", "#9a7046", 3.0)
        iron = flat("iron", IRON, 0.5)
        for sx in (-1, 1):
            beam((sx * 0.1, -0.035, 0.0), (sx * 0.1, 0.0, 0.11), 0.016, wd)
            beam((sx * 0.1, 0.035, 0.0), (sx * 0.1, 0.0, 0.11), 0.016, wd)
        beam((-0.115, 0.0, 0.105), (0.115, 0.0, 0.105), 0.016, wd)
        beam((-0.1, 0.0, 0.035), (0.1, 0.0, 0.035), 0.012, wd)
        for i in range(n_spears):
            xx = -0.07 + i * 0.14 / max(1, n_spears - 1)
            spear((xx, -0.05, 0.0), (xx + 0.004, 0.01, 0.2), wl, iron)
        for i in range(axes):
            xx = 0.05 - i * 0.07
            rod((xx, 0.04, 0.0), (xx, 0.012, 0.12), 0.006, wl, n=4)
            bx((0.012, 0.035, 0.03), (xx, 0.022, 0.11), iron, bev=0, rot=(-0.23, 0, 0))
        for i in range(shields):
            xx = -0.06 + i * 0.12
            sm = tex("wood", shield_c or "#8a6440", 2.0)
            cy(0.042, 0.01, (xx, -0.05, 0.045), sm, 10, rot=(math.pi / 2 - 0.25, 0, 0))
            ico(0.011, (xx, -0.057, 0.047), flat("iron", IRON, 0.5), (1, 0.6, 1))
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


def raider_camp():
    """Marauder camp: grey patched tents, crude sharpened-log palisade (gap at the front), camp fire with
    smoke, a pole with a torn dark-red rag and a skull, a weapon rack and a pile of loot."""
    dirt = tex("plaster", "#86684a", 1.4)
    ev.pad(0.79, dirt, 0.006, 16, 0.05, 7)
    ev.pad(0.42, tex("plaster", "#6f553c", 1.6), 0.01, 12, 0.12, 8)  # trampled centre
    # ---- palisade ring with a gap at the front (−Y)
    wd = tex("wood", "#6e4c30", 2.0)
    wd2 = tex("wood", "#5a3e27", 2.0)
    tip = flat("stake_tip", "#c9a471", 0.85)
    rnd = random.Random(11)
    R = 0.74
    n = 60
    gap = math.radians(24)
    ring_pts = []
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
        ring_pts.append(a)
    # lashed cross rails in sections (inner side)
    rail = tex("wood", "#7d5a38", 3.0)
    sec = math.tau / 9
    a = -math.pi / 2 + gap + 0.03
    while a + sec * 0.6 < math.tau - math.pi / 2 - gap:
        a1 = min(a + sec, math.tau - math.pi / 2 - gap - 0.03)
        rr = R - 0.03
        beam((math.cos(a) * rr, math.sin(a) * rr, 0.1 + rnd.uniform(-0.01, 0.01)),
             (math.cos(a1) * rr, math.sin(a1) * rr, 0.11 + rnd.uniform(-0.01, 0.01)), 0.018, rail)
        a = a1 + 0.02
    # taller gate posts with a skull on one of them
    for sx in (-1, 1):
        a = -math.pi / 2 + sx * (gap + 0.04)
        x, y = math.cos(a) * R, math.sin(a) * R
        stake(x, y, 0.32, 0.032, (0.0, -0.01), wd2, tip, n=6)
    gx, gy = math.cos(-math.pi / 2 + gap + 0.04) * R, math.sin(-math.pi / 2 + gap + 0.04) * R - 0.01
    skull(gx, gy - 0.004, 0.3, 1.0)
    # ---- tents
    pA = tex("plaster", "#b8a684", 2.5)
    pB = tex("plaster", "#6c6257", 2.5)
    pC = tex("plaster", "#8b7a62", 2.5)
    build_at(lambda: cone_tent(0.22, 0.4, tex("plaster", CANVAS, 1.8), (pA, pB, pC, pA), 3), -0.3, 0.32, 0.0)
    build_at(lambda: ridge_tent(0.32, 0.27, 0.21, tex("plaster", CANVAS_D, 1.8), (pA, pB, pA, pC), seed=5),
             0.25, 0.38, -0.45)
    build_at(lambda: ridge_tent(0.22, 0.2, 0.15, tex("plaster", "#9a948a", 1.8), (pB, pA, pC), seed=9),
             -0.5, -0.12, -math.pi / 2 - 0.35)
    # ---- camp fire: stone ring, crossed logs, flame, smoke column
    fx, fy = 0.04, -0.06
    rk = tex("plaster", "#7f7b75", 1.5)
    for k in range(9):
        a = k * math.tau / 9
        ico(0.022, (fx + math.cos(a) * 0.075, fy + math.sin(a) * 0.075, 0.016), rk, (1.2, 1.0, 0.75))
    ico(0.05, (fx, fy, 0.005), flat("ash", "#3a3330", 0.95), (1.2, 1.2, 0.25))
    logm = tex("wood", "#5e3d24", 2.5)
    for k in range(4):
        a = k * math.pi / 2 + 0.4
        rod((fx + math.cos(a) * 0.065, fy + math.sin(a) * 0.065, 0.01), (fx, fy, 0.085), 0.011, logm, n=5)
    cn(0.045, 0.11, (fx, fy, 0.065), glow("flame", FLAME, 3.0), 6)
    cn(0.026, 0.08, (fx + 0.005, fy - 0.004, 0.06), glow("flame_y", FLAME_Y, 3.5), 6)
    for i, (dx, dy, z, r) in enumerate(((0.0, 0.0, 0.155, 0.026), (0.02, 0.012, 0.215, 0.038), (0.06, 0.03, 0.29, 0.05),
                                        (0.12, 0.05, 0.36, 0.042))):  # drifting smoke, darker at the bottom
        c = ("#5e5955", "#7d7873", "#9a958f", "#b2ada7")[i]
        ico(r, (fx + dx, fy + dy, z), flat("smoke%d" % i, c, 0.95), (1.25, 1.0, 0.8), sub=1)
    # log seats
    seat = tex("wood", "#7a5232", 2.5)
    for a, ln in ((math.radians(200), 0.16), (math.radians(-20), 0.14)):
        x, y = fx + math.cos(a) * 0.19, fy + math.sin(a) * 0.19
        cy(0.026, ln, (x, y, 0.026), seat, 6, rot=(math.pi / 2, 0, a))
    # ---- flag pole with a torn dark-red rag and a skull on top
    px, py = 0.0, 0.5
    pole = tex("wood", "#5a3e27", 2.0)
    H = 0.82
    rod((px, py, 0.0), (px - 0.012, py + 0.008, H), 0.017, pole, r2=0.012, n=6)
    for k in range(3):
        a = k * math.tau / 3
        ico(0.03, (px + math.cos(a) * 0.035, py + math.sin(a) * 0.035, 0.012), rk, (1.1, 1.0, 0.7))
    rag = flat("rag", RAG, 0.9)
    rag_d = flat("rag_d", shade(RAG, 0.7), 0.9)
    top = H - 0.07
    x0 = px - 0.004
    # ragged strips of different length hanging off a cross stick toward +X, jagged ends, two tatters
    strips = ((0.22, 0.0), (0.17, 0.045), (0.2, 0.09), (0.11, 0.135))
    for i, (ln, dz) in enumerate(strips):
        z = top - dz
        m_ = rag if i % 2 == 0 else rag_d
        bx((ln, 0.007, 0.046), (x0 + ln / 2, py, z), m_, bev=0, rot=(0.0, 0.05 * i, 0.0))
        tri_plate((x0 + ln, py, z + 0.023), (x0 + ln, py, z - 0.023), (x0 + ln + 0.04, py, z - 0.03 - 0.01 * i), m_, 0.007)
    for xx, ln in ((x0 + 0.05, 0.075), (x0 + 0.12, 0.05)):  # tatters
        bx((0.016, 0.006, ln), (xx, py, top - 0.155 - ln / 2), rag_d, bev=0)
    bx((0.25, 0.013, 0.013), (x0 + 0.11, py, top + 0.028), pole, bev=0)  # cross stick
    skull(px - 0.012, py + 0.008, H + 0.015, 1.25)
    # ---- weapon rack (front left) and a pile of loot (front right)
    weapon_rack(-0.4, -0.4, 0.75, 3, 1, "#5a4636", 1)
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
    rod((-0.14, -0.3, 0.008), (-0.08, -0.33, 0.008), 0.006, bone, n=4)
    rod((-0.12, -0.36, 0.008), (-0.09, -0.29, 0.008), 0.006, bone, n=4)


def skull(x, y, z, s=1.0):
    def b():
        bone = flat("bone", BONE, 0.7)
        hole = flat("socket", "#1c1714", 0.9)
        ico(0.028, (0, 0, 0.0), bone, (1.0, 1.0, 1.0))
        bx((0.034, 0.03, 0.02), (0, -0.008, -0.02), bone, bev=0)
        for sx in (-1, 1):
            ico(0.0085, (sx * 0.011, -0.024, 0.0), hole, (1, 0.6, 1))
            cn(0.008, 0.03, (sx * 0.024, 0.0, 0.022), bone, 5, rot=(0, sx * 0.6, 0))  # little horns
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


def port():
    """Fishing/trade port: a water cove opening at the +X edge, a plank pier into it, a sailboat and a rowboat
    moored, a plank boathouse/warehouse with a blue door, crates, barrels, rope coils, a derrick, a fish rack."""
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
    water = tex("plaster", WATER, 1.2)
    ground_poly(pts, water, 0.012)
    # shallow lighter rim and the stone quay along the land side of the cove
    shallow = tex("plaster", "#79c1df", 1.5)
    quay = stone("#a39b8d", 1.4)
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
    # cobbled quay yard on the land side
    ev.pad(0.36, tex("plaster", "#a89c86", 1.6), 0.008, 12, 0.08, 6, 1.0, 1.25)
    # ---- pier from the quay to the +X edge
    deck = tex("wood", "#a8814f", 4.0)
    post = tex("wood", "#5a3e27", 2.0)
    py, pw, z = -0.03, 0.15, 0.075
    x0, x1 = 0.02, 0.79
    for sy in (-1, 1):
        beam((x0, py + sy * 0.05, z - 0.02), (x1, py + sy * 0.05, z - 0.02), 0.02, post)
    n = 17
    for i in range(n):
        x = x0 + (i + 0.5) / n * (x1 - x0)
        bx((((x1 - x0) / n) - 0.006, pw + (0.012 if i % 3 == 0 else 0.0), 0.014), (x, py, z), deck, bev=0)
    for i in range(5):
        x = 0.22 + i * 0.14
        for sy in (-1, 1):
            cy(0.015, 0.13 + (0.02 if i == 4 else 0.0), (x, py + sy * 0.085, 0.065 + (0.01 if i == 4 else 0.0)), post, 6)
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
    rope = flat("rope", "#e8dcc0", 0.8)
    rod((0.36, py + 0.085, 0.13), (0.3, 0.12, 0.07), 0.003, rope, n=3)
    rod((0.5, py - 0.085, 0.13), (0.42, -0.25, 0.05), 0.003, rope, n=3)
    # ---- warehouse / boathouse (plank walls, thatch roof, blue door and shutters)
    def warehouse():
        w, d, h = 0.38, 0.26, 0.2
        bx((w, d, h), (0, 0, h / 2), tex("wood", "#8a6a48", 3.0), bev=0.008)
        bx((w + 0.02, d + 0.02, 0.03), (0, 0, 0.015), stone(STONE_D, 1.2), bev=0)
        for sx in (-1, 1):
            for sy in (-1, 1):
                bx((0.026, 0.026, h + 0.01), (sx * w / 2, sy * d / 2, h / 2), tex("wood", WOOD_D, 2.0), bev=0)
        prism_roof("roof", w, d, 0.17, (0, 0, h - 0.005), tex("wood", "#c9a55a", 3.0), overhang=0.045)
        bx((w + 0.12, 0.035, 0.03), (0, 0, h + 0.165), tex("wood", "#8a6a3c", 2.0), bev=0)  # ridge cap
        door = flat("door_blue", TRIM_BLUE, 0.7)
        bx((0.11, 0.012, 0.14), (-0.06, -d / 2 - 0.004, 0.07), door, bev=0)
        bx((0.12, 0.016, 0.016), (-0.06, -d / 2 - 0.006, 0.145), tex("wood", WOOD_D, 2.0), bev=0)
        for sxd in (-1, 1):
            beam((-0.06 + sxd * 0.05, -d / 2 - 0.012, 0.01), (-0.06 - sxd * 0.05, -d / 2 - 0.012, 0.13), 0.01,
                 tex("wood", "#2f4f78", 2.0))
        ev.window(0.11, -d / 2 - 0.004, 0.12, 0, 0.045, 0.045, TRIM_BLUE)
        ev.window(0.0, d / 2 + 0.004, 0.12, 0, 0.045, 0.045, TRIM_BLUE)
        ev.window(-w / 2 - 0.004, 0.0, 0.12, math.pi / 2, 0.045, 0.045, TRIM_BLUE)
        # hoist beam out of the gable toward the water with a pulley and a sack
        beam((w / 2 - 0.02, 0, h + 0.07), (w / 2 + 0.1, 0, h + 0.07), 0.024, tex("wood", WOOD_D, 2.0))
        bx((0.06, 0.012, 0.07), (w / 2 + 0.006, 0, h + 0.0), flat("loft", "#2b2420", 0.9), math.pi / 2, bev=0)
        rod((w / 2 + 0.09, 0, h + 0.06), (w / 2 + 0.09, 0, 0.1), 0.003, rope, n=3)
        sack(w / 2 + 0.09, 0, 0.8, 0, z=0.04)
    build_at(warehouse, -0.36, 0.32, -0.1)
    # ---- derrick on the quay at the back, jib over the water
    build_at(crane, 0.13, 0.48, 0.25)
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
    # ---- fish drying rack (front left)
    def fish_rack():
        wd = tex("wood", "#6a4327", 2.5)
        for sx in (-1, 1):
            beam((sx * 0.12, -0.03, 0.0), (sx * 0.12, 0.0, 0.17), 0.016, wd)
            beam((sx * 0.12, 0.03, 0.0), (sx * 0.12, 0.0, 0.17), 0.016, wd)
        beam((-0.13, 0, 0.165), (0.13, 0, 0.165), 0.012, wd)
        fish = flat("fish", "#a9b8c2", 0.4)
        for i in range(6):
            x = -0.09 + i * 0.036
            ico(0.014, (x, 0, 0.125), fish, (0.6, 0.35, 2.2))
            cn(0.011, 0.016, (x, 0, 0.087), fish, 4, rot=(math.pi, 0, 0))
        torus(0.07, 0.006, (0.0, 0.07, 0.006), flat("net", "#6d6a58", 0.9), seg=10, mseg=3)
    build_at(fish_rack, -0.45, -0.3, 0.35)
    # a few posts and a mooring bollard on the quay edge
    for (x, y) in ((0.15, -0.34), (0.12, 0.3)):
        cy(0.02, 0.06, (x, y, 0.04), post, 6)


# ------------------------------------------------------------------ military base


def dummy(x, y, rz=0.0):
    """Straw training dummy on a post with a cross arm and a sack head."""
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        straw = tex("wood", STRAW, 4.0)
        for a in (0, math.pi / 2):
            beam((math.cos(a) * -0.045, math.sin(a) * -0.045, 0.008), (math.cos(a) * 0.045, math.sin(a) * 0.045, 0.008),
                 0.016, wd)
        cy(0.008, 0.2, (0, 0, 0.1), wd, 5)
        uvs(0.035, (0, 0, 0.115), straw, 8, 5, (1.0, 0.8, 1.35))
        beam((-0.06, 0, 0.14), (0.06, 0, 0.14), 0.014, wd)
        for sx in (-1, 1):
            cn(0.014, 0.025, (sx * 0.065, 0, 0.14), straw, 5, rot=(0, sx * math.pi / 2, 0))
        ico(0.024, (0, 0, 0.185), tex("plaster", "#c9b48a", 3.0), (1, 1, 1.05))
        torus(0.012, 0.005, (0, 0, 0.165), flat("rope", "#8a6a40", 0.8), seg=6, mseg=3)
        bx((0.028, 0.006, 0.006), (0, -0.024, 0.19), flat("socket", "#2b2420", 0.9), bev=0)
    build_at(b, x, y, rz)


def archery_target(x, y, rz=0.0):
    def b():
        wd = tex("wood", "#6a4327", 2.5)
        beam((-0.05, 0.03, 0.0), (0.0, 0.0, 0.16), 0.014, wd)
        beam((0.05, 0.03, 0.0), (0.0, 0.0, 0.16), 0.014, wd)
        beam((0.0, 0.07, 0.0), (0.0, 0.0, 0.15), 0.014, wd)
        t = 0.2
        cy(0.06, 0.026, (0, -0.01, 0.1), tex("wood", STRAW, 4.0), 10, rot=(math.pi / 2 - t, 0, 0))
        cy(0.045, 0.026, (0, -0.013, 0.1), flat("tgt_w", "#efe9da", 0.7), 10, rot=(math.pi / 2 - t, 0, 0))
        cy(0.028, 0.026, (0, -0.016, 0.1), flat("tgt_r", "#b8352c", 0.7), 10, rot=(math.pi / 2 - t, 0, 0))
        cy(0.012, 0.026, (0, -0.019, 0.1), flat("tgt_w", "#efe9da", 0.7), 8, rot=(math.pi / 2 - t, 0, 0))
        ar = flat("arrow", "#d8c49a", 0.8)
        for dx, dz in ((0.012, 0.01), (-0.02, -0.015)):
            rod((dx, -0.02, 0.1 + dz), (dx + 0.01, -0.08, 0.1 + dz + 0.012), 0.003, ar, n=3)
    build_at(b, x, y, rz)


def military_base():
    """Early garrison: low stone-wall square with a timber gate (front), barracks hall at the back, a row of soldier
    tents, a training yard with straw dummies and an archery target, weapon racks, a corner lookout, white banner."""
    S = 0.55
    # ---- ground: packed earth inside, sand yard, gravel path from the gate
    ground_poly([(-S, -S), (S, -S), (S, S), (-S, S)], tex("plaster", "#a58a62", 1.5), 0.006)
    ground_poly([(0.06, -0.5), (0.5, -0.5), (0.5, -0.06), (0.06, -0.06)], tex("plaster", "#cdb482", 2.0), 0.012)
    ground_poly([(-0.07, -0.6), (0.03, -0.6), (0.03, 0.05), (-0.07, 0.05)], tex("plaster", "#b9ad97", 2.5), 0.01)
    # ---- low stone walls with a coping, corner pillars, gate gap at the front
    st = stone(STONE, 1.3)
    sd = stone(STONE_D, 1.3)
    H, T = 0.11, 0.05
    gate = 0.1
    segs = [((-S, S), (S, S)), ((S, -S), (S, S)), ((-S, -S), (-S, S)),
            ((-S, -S), (-0.02 - gate, -S)), ((-0.02 + gate, -S), (S, -S))]
    for (a, b) in segs:
        L = math.dist(a, b)
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        bx((L, T, H), (mx, my, H / 2), st, ang, bev=0)
        bx((L + 0.01, T + 0.016, 0.022), (mx, my, H + 0.011), sd, ang, bev=0)
        nb = int(L / 0.14)
        for i in range(nb):  # little merlons
            f = (i + 0.5) / nb
            bx((0.05, T + 0.004, 0.03), (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, H + 0.036), st, ang, bev=0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx((0.085, 0.085, 0.17), (sx * S, sy * S, 0.085), sd, bev=0.008)
            cn(0.07, 0.05, (sx * S, sy * S, 0.195), tex("wood", "#6d5640", 2.0), 4, rot=(0, 0, math.pi / 4))
    # ---- timber gate: two posts, lintel beam with a white plaque, open leaves swung inside
    wd = tex("wood", "#6a4327", 2.0)
    wl = tex("wood", "#8c6a44", 3.0)
    gx0 = -0.02
    for sx in (-1, 1):
        x = gx0 + sx * (gate + 0.02)
        bx((0.05, 0.07, 0.28), (x, -S, 0.14), wd, bev=0.006)
        cn(0.04, 0.05, (x, -S, 0.305), wd, 4, rot=(0, 0, math.pi / 4))
    bx((2 * gate + 0.13, 0.05, 0.04), (gx0, -S, 0.25), wd, bev=0.006)
    bx((0.08, 0.012, 0.05), (gx0, -S - 0.03, 0.25), flat("flag_white", "#ecebe6", 0.7), bev=0)
    bx((0.025, 0.014, 0.025), (gx0, -S - 0.032, 0.25), flat("flag_grey", "#8d9096", 0.7), math.pi / 4, bev=0)
    for sx in (-1, 1):
        hx = gx0 + sx * gate
        a = math.radians(70)
        bx((gate * 0.95, 0.018, 0.17), (hx - sx * math.cos(a) * gate * 0.475, -S + math.sin(a) * gate * 0.475, 0.095),
           wl, -sx * a, bev=0)
    # ---- barracks hall along the back wall
    def barracks():
        w, d, h = 0.5, 0.2, 0.13
        bx((w + 0.02, d + 0.02, 0.025), (0, 0, 0.0125), sd, bev=0)
        bx((w, d, h), (0, 0, h / 2), tex("wood", "#8a6440", 3.0), bev=0.008)
        for sx in (-1, 0, 1):
            for sy in (-1, 1):
                bx((0.024, 0.024, h + 0.005), (sx * w / 2, sy * d / 2, h / 2), tex("wood", WOOD_D, 2.0), bev=0)
        prism_roof("roof", w, d, 0.12, (0, 0, h - 0.005), tex("roof", "#7a6450", 1.6), overhang=0.04)
        bx((w + 0.1, 0.03, 0.025), (0, 0, h + 0.115), tex("wood", "#4f3a28", 2.0), bev=0)
        bx((0.06, 0.012, 0.1), (0, -d / 2 - 0.004, 0.05), tex("wood", "#4a2f19", 2.0), bev=0)
        bx((0.09, 0.05, 0.012), (0, -d / 2 - 0.03, 0.075), tex("wood", "#6d5640", 2.0), bev=0, rot=(0.3, 0, 0))
        for x in (-0.17, -0.09, 0.09, 0.17):
            bx((0.035, 0.012, 0.03), (x, -d / 2 - 0.004, 0.085), flat("slit", "#2a2420", 0.9), bev=0)
        cy(0.024, 0.09, (0.16, 0.04, h + 0.085), stone(STONE_D), 6)
        for sx in (-1, 1):
            bx((0.03, 0.012, 0.03), (sx * w / 2 + sx * 0.004, 0, 0.085), flat("slit", "#2a2420", 0.9), math.pi / 2, bev=0)
    build_at(barracks, 0.1, 0.34)
    # ---- row of soldier tents on the left, opening toward the parade ground (+X)
    canvas = tex("plaster", CANVAS_W, 2.0)
    for y in (-0.33, -0.1, 0.13):
        build_at(lambda: (ridge_tent(0.19, 0.15, 0.16, canvas, (), True, True),
                          beam((0, -0.1, 0.163), (0, 0.1, 0.163), 0.016, flat("ridge_grey", "#7d8086", 0.7)),
                          bx((0.155, 0.2, 0.012), (0, 0, 0.006), tex("plaster", "#7d6a50", 1.5), bev=0)),
                 -0.37, y, math.pi / 2)
    # ---- corner lookout platform (back left)
    def lookout():
        H2 = 0.3
        for sx in (-1, 1):
            for sy in (-1, 1):
                beam((sx * 0.07, sy * 0.07, 0.0), (sx * 0.055, sy * 0.055, H2 + 0.12), 0.02, wd)
        for k in range(4):
            a = k * math.pi / 2
            c, s_ = math.cos(a), math.sin(a)
            beam((c * 0.065 - s_ * 0.065, s_ * 0.065 + c * 0.065, 0.04), (c * 0.06 + s_ * 0.06, s_ * 0.06 - c * 0.06, H2 - 0.04),
                 0.012, wl)
        bx((0.16, 0.16, 0.02), (0, 0, H2), wl, bev=0)
        for k in range(4):
            a = k * math.pi / 2
            bx((0.16, 0.014, 0.05), (math.sin(a) * 0.075, -math.cos(a) * 0.075, H2 + 0.035), wl, a, bev=0)
        hip_roof(0.13, 0.13, 0.09, (0, 0, H2 + 0.12), tex("wood", "#6d5640", 2.0), oh=0.025)
    build_at(lookout, -0.43, 0.43)
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
    # ---- supplies: crates, barrels, hay by the barracks
    crate(0.42, 0.24, 0.06, 0.2)
    crate(0.46, 0.31, 0.05, -0.3)
    barrel(-0.2, 0.25)
    barrel(-0.14, 0.27, r=0.03, h=0.075)
    ev.haystack(0.47, -0.45, 0.45)
    # ---- guards at the gate
    for sx in (-1, 1):
        hands = build_at(lambda: ta.man("#8d9096", "#5a4f45", "idle", "helmet", 1.15), gx0 + sx * 0.2, -S + 0.075, 0.0)
        hx, hy, hz = hands[0 if sx < 0 else 1]
        spear((gx0 + sx * 0.2 + hx, -S + 0.075 + hy, 0.0), (gx0 + sx * 0.2 + hx, -S + 0.075 + hy, 0.2),
              tex("wood", "#9a7046", 3.0), flat("iron", IRON, 0.5))


def warship(team):
    """A two-masted warship along X (bow at +X) for the open water (reference frame 1): a dark hull with a team
    stripe and gun ports, square sails in the team colour with a white emblem, a raised stern castle, pennants."""
    body = tex("wood", "#4e3420", 3.0)
    deck = tex("wood", "#a07a4c", 4.0)
    stripe = flat("hull_stripe" + team, ev.slate(team, 1.15), 0.6)
    hull(0.62, 0.2, 0.1, body, deck, stripe)
    for k in range(5):  # gun ports along both sides
        for sy in (-1, 1):
            bx((0.022, 0.006, 0.018), (-0.18 + k * 0.085, sy * 0.098, 0.06), flat("port_d", "#1a1410", 0.9), bev=0)
    bx((0.16, 0.19, 0.07), (-0.24, 0, 0.135), body, bev=0.006)  # stern castle
    bx((0.17, 0.2, 0.012), (-0.24, 0, 0.172), deck, bev=0)
    wd = tex("wood", "#3e2a1a", 2.0)
    sail_c = flat("sail" + team, ev.slate(team, 1.12), 0.8)
    em = flat("emblem", "#f3efe6", 0.6)
    for (mx, h, w) in ((0.08, 0.56, 0.24), (-0.1, 0.48, 0.2)):
        cy(0.011, h, (mx, 0, 0.1 + h / 2), wd, 6)
        for (z, sw) in ((0.28, w), (0.45, w * 0.8)):
            bx((0.012, sw, 0.16), (mx + 0.012, 0, 0.1 + z), sail_c, bev=0.004)
            beam((mx, -sw / 2 - 0.01, 0.1 + z + 0.07), (mx, sw / 2 + 0.01, 0.1 + z + 0.07), 0.008, wd)
        bx((0.016, w * 0.32, 0.06), (mx + 0.02, 0, 0.1 + 0.28), em, bev=0)
        bx((0.06, 0.004, 0.025), (mx + 0.03, 0, 0.1 + h + 0.01), flat("pennant" + team, team, 0.6), bev=0)
    beam((0.31, 0, 0.1), (0.46, 0, 0.16), 0.01, wd)  # bowsprit
    tri_plate((0.09, 0, 0.5), (0.09, 0, 0.2), (0.4, 0, 0.18), flat("jib", SAIL, 0.8), 0.005)


PROPS = [raider_camp, port, military_base]
ASSETS = {f.__name__: f for f in PROPS}
for _t, _c in ev.TEAMS.items():
    ASSETS["warship_" + _t] = (lambda c: (lambda: warship(c)))(_c)


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
