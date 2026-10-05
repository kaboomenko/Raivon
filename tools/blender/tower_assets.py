"""Defensive towers by level (canon: the tower's look evolves with the state's era, like the fort ring).

Builds and exports to OUT (default game/assets/models):
  tower_l{1..8}.glb   team-neutral tower, spawned at the back-right of a hex (small footprint)

  1 вышка с пращником          crude lookout on rough poles, slinger on top, stone pile
  2 деревянная вышка лучника   timber watchtower, plank parapet, thatch tent roof, archer with a bow
  3 каменная башня с баллистой  round stone tower, corbelled crenellations, ballista on top
  4 пушечная башня             octagonal brick bastion on a stone plinth, cannons, grey flag
  5 пулемётное гнездо          concrete tower, sandbag ring, machine gun and a helmeted gunner
  6 ДОТ с зениткой (ПВО)        hexagonal concrete pillbox with a twin anti-aircraft gun
  7 ракетная башня             steel column, hazard stripes, tilted missile pod, red sensor glow
  8 лазерная турель            white composite pylon, turret head with a glowing cyan emitter

Run:   python3 tools/blender/tower_assets.py game/assets/models [name ...]
Sheet: python3 tools/blender/tower_assets.py game/assets/models --sheet OUT.png [--cols 1,2,3] [--tile 1.0]

Conventions (same as evolution_assets.py): Z up, base on Z=0, origin = model centre, front faces −Y.
Footprint radius ≤ 0.28, height 0.55–0.95. Procedural colours are baked into one 512 px texture;
emissive materials (sensor, cyan emitter) stay separate so they keep glowing in Godot.
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
                              glow, build_at, shade, WOOD, WOOD_D, WOOD_L, THATCH, STONE, STONE_D, BRICK, DIRT,
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


def cannon(x, y, a, z=0.0, s=1.0):
    """Field cannon on a wooden carriage pointing along angle a (around Z), scaled by s."""
    def b():
        wd = tex("wood", "#6a4327")
        iron = flat("iron", IRON, 0.5)
        bx((0.09, 0.06, 0.035), (0, 0, 0.04), wd, bev=0)
        for sy in (-1, 1):
            cy(0.03, 0.014, (-0.01, sy * 0.037, 0.03), wd, 8, rot=(math.pi / 2, 0, 0))
        cy(0.022, 0.15, (0.04, 0, 0.075), iron, 8, r2=0.016, rot=(0, math.pi / 2 - 0.12, 0))
        cy(0.02, 0.016, (0.112, 0, 0.084), iron, 8, rot=(0, math.pi / 2 - 0.12, 0))
        ico(0.016, (-0.035, 0, 0.068), iron)
    build_at(b, x, y, a, s=s, z=z)


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


# ------------------------------------------------------------------ towers


def tower_l1():
    """Crude lookout: four rough leaning poles, a jagged plank deck, a slinger, piles of stones."""
    wd = tex("wood", WOOD_D, 2.0)
    wr = tex("wood", "#8a6440", 2.5)
    rk = tex("plaster", "#8d8a84", 1.5)
    ev.pad(0.24, tex("plaster", DIRT, 1.2), 0.008, 10, 0.08, 21)
    H = 0.4
    rnd = random.Random(1)
    tops = []
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        b0 = (math.cos(a) * 0.2 + rnd.uniform(-0.01, 0.01), math.sin(a) * 0.2 + rnd.uniform(-0.01, 0.01))
        t = (math.cos(a) * 0.13, math.sin(a) * 0.13)
        rod((b0[0], b0[1], 0.0), (t[0], t[1], H + 0.08 + rnd.uniform(-0.015, 0.02)), 0.018, wd, r2=0.014, n=6)
        tops.append((t, b0))
    # cross bracing on every side and a crude rail at hip height
    for k in range(4):
        (t0, b0), (t1, b1) = tops[k], tops[(k + 1) % 4]
        f0, f1 = 0.12, 0.72
        p0 = [b0[i] + (t0[i] - b0[i]) * f0 for i in (0, 1)]
        p1 = [b1[i] + (t1[i] - b1[i]) * f1 for i in (0, 1)]
        beam((p0[0], p0[1], H * f0), (p1[0], p1[1], H * f1), 0.016, wr)
        beam((t0[0], t0[1], H + 0.065), (t1[0], t1[1], H + 0.06), 0.014, wr)
    plank_deck(0.25, 0.25, H, tex("wood", "#9a7046", 3.0), 5, 0.022, 3, 0.03)
    ladder(-0.045, 0.045, -0.26, -0.15, H, wr, 5)
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
    """Timber watchtower: braced splayed posts, plank parapet, thatch tent roof, an archer drawing a bow."""
    wd = tex("wood", WOOD, 2.0)
    wl = tex("wood", WOOD_L, 2.5)
    H = 0.4
    base, top = 0.165, 0.12
    corners = [(sx, sy) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    for sx, sy in corners:
        beam((sx * base, sy * base, 0.0), (sx * top, sy * top, H), 0.034, wd)
        cy(0.026, 0.03, (sx * base, sy * base, 0.015), stone(STONE_D), 6)
    for k in range(4):
        (ax, ay), (bx_, by) = corners[k], corners[(k + 1) % 4]
        zm = H * 0.5
        mm = base + (top - base) * 0.5
        beam((ax * mm, ay * mm, zm), (bx_ * mm, by * mm, zm), 0.022, wl)
        beam((ax * base * 0.96, ay * base * 0.96, 0.03), (bx_ * mm, by * mm, zm), 0.018, wl)
        beam((ax * mm, ay * mm, zm), (bx_ * top, by * top, H - 0.02), 0.018, wl)
    plank_deck(0.3, 0.3, H, tex("wood", "#9a7046", 3.0), 5, 0.026, 5, 0.0)
    # plank parapet
    pw = tex("wood", "#8c5e34", 4.0)
    ph = 0.06
    for k in range(4):
        a = k * math.pi / 2
        c, s_ = math.cos(a), math.sin(a)
        bx((0.3, 0.02, ph), (-s_ * 0.0 + c * 0.0 + s_ * 0.14, -c * 0.14, H + 0.013 + ph / 2), pw, a, bev=0)
        bx((0.32, 0.03, 0.02), (s_ * 0.14, -c * 0.14, H + 0.013 + ph), wd, a, bev=0)
    # roof posts and thatch tent roof
    zr = H + 0.28
    for sx, sy in corners:
        bx((0.024, 0.024, zr - H), (sx * 0.135, sy * 0.135, H + (zr - H) / 2), wd, bev=0)
    hip_roof(0.3, 0.3, 0.14, (0, 0, zr), tex("wood", "#d2a54e", 4.0), oh=0.03)
    bx((0.31, 0.31, 0.02), (0, 0, zr - 0.005), wd, bev=0)
    cn(0.03, 0.05, (0, 0, zr + 0.15), wd, 6)
    ladder(-0.04, 0.04, -0.25, -0.16, H, wl, 5)
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


def tower_l3():
    """Round stone tower with a corbelled crenellated top and a ballista."""
    st = stone(STONE, 1.0)
    sd = stone(STONE_D, 1.0)
    cy(0.225, 0.06, (0, 0, 0.03), sd, 12)
    cy(0.205, 0.44, (0, 0, 0.28), st, 12, r2=0.185)
    cy(0.185, 0.06, (0, 0, 0.53), sd, 12, r2=0.218)
    cy(0.218, 0.04, (0, 0, 0.58), st, 12)
    for k in range(8):
        a = k * math.tau / 8 + math.tau / 16
        bx((0.07, 0.05, 0.065), (math.cos(a) * 0.195, math.sin(a) * 0.195, 0.632), st, a + math.pi / 2, bev=0.006)
    cy(0.185, 0.012, (0, 0, 0.6), tex("wood", "#9a7046", 3.0), 12)
    # door with an arched top, iron bands, arrow slits
    door = tex("wood", "#4a2f19", 2.0)
    bx((0.075, 0.03, 0.1), (0, -0.196, 0.11), door, bev=0)
    cy(0.0375, 0.03, (0, -0.196, 0.16), door, 8, rot=(math.pi / 2, 0, 0))
    bx((0.1, 0.034, 0.02), (0, -0.2, 0.06), sd, bev=0)
    for z in (0.09, 0.14):
        bx((0.08, 0.036, 0.008), (0, -0.197, z), flat("iron", IRON, 0.6), bev=0)
    slit = flat("slit", "#1e1a17", 0.9)
    for a, z in ((-math.pi / 2, 0.36), (-math.pi / 2 + 1.2, 0.3), (-math.pi / 2 - 1.2, 0.3), (math.pi / 2, 0.33)):
        r = 0.205 + (0.185 - 0.205) * (z - 0.06) / 0.44 - 0.002
        bx((0.018, 0.02, 0.07), (math.cos(a) * r, math.sin(a) * r, z), slit, a + math.pi / 2, bev=0)

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


def tower_l4():
    """Octagonal brick bastion on a sloped stone plinth: two cannons on top, one through a gun port, grey flag."""
    sb = stone("#a39b8d", 1.2)
    br = stone(BRICK, 1.4)
    trim = stone(STONE, 1.0)
    rot = (0, 0, math.pi / 8)
    cy(0.255, 0.2, (0, 0, 0.1), sb, 8, r2=0.215, rot=rot)
    cy(0.222, 0.035, (0, 0, 0.215), trim, 8, rot=rot)
    cy(0.2, 0.3, (0, 0, 0.38), br, 8, r2=0.195, rot=rot)
    cy(0.195, 0.04, (0, 0, 0.545), trim, 8, r2=0.228, rot=rot)
    cy(0.228, 0.035, (0, 0, 0.58), trim, 8, rot=rot)
    cy(0.19, 0.012, (0, 0, 0.6), tex("wood", "#9a7046", 3.0), 8, rot=rot)
    for k in range(8):  # merlons on the octagon corners, embrasures on the faces
        a = math.pi / 8 + k * math.pi / 4
        bx((0.075, 0.06, 0.075), (math.cos(a) * 0.198, math.sin(a) * 0.198, 0.635), br, a + math.pi / 2, bev=0.006)
        bx((0.08, 0.065, 0.014), (math.cos(a) * 0.198, math.sin(a) * 0.198, 0.676), trim, a + math.pi / 2, bev=0)
    for a in (-math.pi * 0.75, -math.pi * 0.25):
        cannon(math.cos(a) * 0.1, math.sin(a) * 0.1, a, 0.606, 1.15)
    # gun port on the front face with a barrel poking out
    ap = 0.2 * math.cos(math.pi / 8) - 0.003
    bx((0.075, 0.02, 0.065), (0, -ap, 0.36), trim, bev=0)
    bx((0.05, 0.024, 0.045), (0, -ap, 0.36), flat("slit", "#1e1a17", 0.9), bev=0)
    iron = flat("iron", IRON, 0.5)
    cy(0.017, 0.07, (0, -ap - 0.03, 0.358), iron, 8, r2=0.014, rot=(math.pi / 2 + 0.06, 0, 0))
    cy(0.019, 0.012, (0, -ap - 0.062, 0.356), iron, 8, rot=(math.pi / 2 + 0.06, 0, 0))
    # door on the back, cannonballs, flag
    bx((0.07, 0.02, 0.11), (0, 0.205, 0.075), tex("wood", "#4a2f19", 2.0), bev=0)
    for (x, y) in ((0.05, 0.06), (0.075, 0.075), (0.06, 0.09)):
        ico(0.016, (x, y, 0.622), iron)
    ico(0.016, (0.063, 0.075, 0.645), iron)
    neutral_flag(-0.06, 0.1, 0.9, 0.15)


def tower_l5():
    """Concrete machine-gun nest: tapered low tower, sandbag ring, MG on a tripod, helmeted gunner."""
    cm = tex("plaster", "#b9b5ad", 2.0)
    cd = tex("plaster", "#8f8b83", 2.0)
    H = 0.4
    taper_box((0.36, 0.36, H), (0, 0, H / 2), cm, (0.86, 0.86), bev=0.01)
    bx((0.37, 0.37, 0.04), (0, 0, 0.02), cd, bev=0.006)
    for z in (0.14, 0.27):  # formwork seams
        w = 0.36 - (0.36 * 0.14) * z / H
        bx((w + 0.006, w + 0.006, 0.008), (0, 0, z), cd, bev=0)
    bx((0.33, 0.33, 0.03), (0, 0, H + 0.015), cd, bev=0.006)
    w_slit = 0.36 - (0.36 * 0.14) * 0.22 / H
    bx((0.12, 0.02, 0.025), (0, -w_slit / 2, 0.22), flat("slit", "#15171a", 0.9), bev=0)
    bx((0.15, 0.04, 0.012), (0, -w_slit / 2 - 0.01, 0.24), cd, bev=0)
    bx((0.07, 0.012, 0.03), (w_slit / 2 * 0.0 + 0.1, -w_slit / 2 - 0.002, 0.08), flat("warn", WARN, 0.6), bev=0)
    bx((0.08, 0.02, 0.13), (0, 0.18 - 0.012, 0.075), flat("steeldoor", "#5b6168", 0.5), bev=0)  # back door
    # steel ladder on the right side
    st = flat("steel", "#4c4f55", 0.5)
    xr = 0.18 - (0.36 * 0.14 / 2) * 0.5 + 0.02
    for y in (-0.04, 0.04):
        beam((0.2, y, 0.0), (0.168, y, H + 0.04), 0.01, st)
    for i in range(1, 7):
        f = i / 7
        beam((0.2 - 0.032 * f, -0.04, (H + 0.04) * f), (0.2 - 0.032 * f, 0.04, (H + 0.04) * f), 0.008, st)
    _ = xr
    # sandbag ring (two staggered rows), open at the front for the gun
    bag = tex("plaster", SAND, 3.0)
    Z = H + 0.03
    for row in range(2):
        for k in range(4):
            a = k * math.pi / 2
            c, s_ = math.cos(a), math.sin(a)
            n = 3
            for i in range(n):
                f = (i + 0.5 + (0.5 if row else 0.0)) / n - 0.5
                if row and i == n - 1:
                    continue
                if k == 0 and abs(f) < 0.2:  # gap in the front row (k=0 side faces −Y)
                    continue
                t = f * 0.27
                px, py = c * t + s_ * 0.135, s_ * t - c * 0.135
                o = uvs(0.05, (px, py, Z + 0.02 + row * 0.036), bag, 6, 4, (1.0, 0.55, 0.42))
                o.rotation_euler.z = a + (0.15 if (i + row) % 2 else -0.1)
    # machine gun on a tripod, aimed forward over the gap
    iron = flat("gun", IRON, 0.5)
    gz = Z + 0.075
    for a in (-math.pi / 2, math.pi / 6, math.pi * 5 / 6):
        rod((0, -0.06, gz), (math.cos(a) * 0.045, -0.06 + math.sin(a) * 0.045, Z), 0.005, iron, n=4)
    bx((0.04, 0.1, 0.04), (0, -0.05, gz + 0.012), flat("gunbody", "#3d4147", 0.5), bev=0.004)
    cy(0.016, 0.08, (0, -0.135, gz + 0.016), flat("gunbody", "#3d4147", 0.5), 8, rot=(math.pi / 2, 0, 0))
    cy(0.007, 0.1, (0, -0.215, gz + 0.016), iron, 6, rot=(math.pi / 2, 0, 0))
    cn(0.012, 0.02, (0, -0.265, gz + 0.016), iron, 6, rot=(math.pi / 2, 0, 0))
    bx((0.045, 0.04, 0.035), (0.045, -0.045, gz + 0.0), flat("ammo", OLIVE, 0.7), bev=0)
    bx((0.06, 0.07, 0.045), (-0.08, 0.06, Z + 0.023), flat("ammo", OLIVE, 0.7), bev=0.004)
    build_at(lambda: man(OLIVE, OLIVE_D, "gun", "helmet", 1.1), 0.0, 0.03, z=Z)


def tower_l6():
    """Hexagonal concrete pillbox (ДОТ) with a twin anti-aircraft gun on a turret ring."""
    cm = tex("plaster", "#a9a59c", 2.0)
    cd = tex("plaster", "#86827a", 2.0)
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
    bx((0.07, 0.012, 0.03), (0.1, -0.21 + 0.004, 0.1), flat("warn", WARN, 0.6), -0.0, bev=0)
    # turret ring + twin AA gun pointing up and forward
    ol = flat("olive", OLIVE, 0.6)
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
    """Steel missile tower: hazard-striped plinth, ribbed column, tilted 2×3 missile pod, red sensor glow."""
    sw = flat("steelwall", STEEL, 0.45)
    sd = flat("steelrib", STEEL_D, 0.45)
    hz = stripes(WARN, "#1f1f22", 14.0)
    cy(0.255, 0.07, (0, 0, 0.035), sd, 6)
    cy(0.235, 0.05, (0, 0, 0.095), hz, 6)
    cy(0.22, 0.02, (0, 0, 0.13), sd, 6)
    cy(0.15, 0.42, (0, 0, 0.35), sw, 8, r2=0.115, rot=(0, 0, math.pi / 8))
    for k in range(4):
        a = k * math.pi / 2
        beam((math.cos(a) * 0.15, math.sin(a) * 0.15, 0.14), (math.cos(a) * 0.117, math.sin(a) * 0.117, 0.54), 0.03, sd)
    cy(0.13, 0.04, (0, 0, 0.52), hz, 8, rot=(0, 0, math.pi / 8))
    cy(0.13, 0.03, (0, 0, 0.555), sd, 10)
    bx((0.06, 0.016, 0.1), (0, -0.145, 0.24), flat("hatch", "#4a515c", 0.5), bev=0, rot=(-0.08, 0, 0))
    bx((0.03, 0.01, 0.012), (0, -0.15, 0.3), glow("sensor", "#ff4a3a", 4.0), bev=0)

    def head():
        cy(0.11, 0.04, (0, 0, 0.02), sw, 10)
        for sx in (-1, 1):
            bx((0.022, 0.1, 0.12), (sx * 0.125, 0.0, 0.08), sd, bev=0.004)
        cy(0.018, 0.27, (0, 0, 0.11), sd, 8, rot=(0, math.pi / 2, 0))

        def pod():
            bx((0.22, 0.2, 0.14), (0, 0, 0), sw, bev=0.008)
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
        build_at(pod, 0, 0.01, tilt=(-0.42, 0), z=0.12)
        cy(0.005, 0.12, (-0.085, 0.07, 0.24), sd, 4)
        ico(0.011, (-0.085, 0.07, 0.305), glow("sensor", "#ff4a3a", 4.0))
    build_at(head, 0, 0, z=0.57)


def tower_l8():
    """Laser turret: white composite pylon with cyan seams, energy ring, turret head with a glowing emitter."""
    comp = flat("composite", COMP, 0.4)
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
    torus(0.15, 0.012, (0, 0, 0.37), cyan, seg=16, mseg=4)
    for k in range(3):
        a = math.pi / 2 + k * math.tau / 3
        beam((math.cos(a) * 0.112, math.sin(a) * 0.112, 0.37), (math.cos(a) * 0.15, math.sin(a) * 0.15, 0.37), 0.016, trim)
    cy(0.11, 0.05, (0, 0, z1 + 0.02), trim, 10)

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
    build_at(head, 0, 0.02, z=z1 + 0.03)


TOWERS = [tower_l1, tower_l2, tower_l3, tower_l4, tower_l5, tower_l6, tower_l7, tower_l8]
ASSETS = {f"tower_l{n + 1}": f for n, f in enumerate(TOWERS)}


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
