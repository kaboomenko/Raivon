"""Factories and oil fields by era (canon, buildings table: «кирпичный цех → конвейерный завод → роботизированный
комбинат», «деревянная вышка-качалка → стальная вышка → нефтекомплекс → плазменный экстрактор»).

Builds and exports to OUT (default game/assets/models), team-neutral, one hex each:
  factory_l1  brick works (DL ≤ 5)       brick halls under a slate sawtooth roof with warm-lit north lights, a bottle
                                         kiln with a glowing mouth, tall brick stacks, a flagged yard with rails, a
                                         brick wagon, a coal heap, pallets of bricks, a timber jib crane, crates
  factory_l2  conveyor plant (DL 6–7)    concrete halls with ribbon windows, a corrugated roof with a lit monitor, a
                                         conveyor gallery from a row of silos, banded steel stacks, a yellow gantry
                                         crane over a loading track, trucks, pipe racks, an asphalt yard
  factory_l3  robotic combine (DL ≥ 8)   the citadel's steel kit (residence_dl8 / city_dl8 / district_scifi): a core
                                         block with two great funnels, cold light slots and bronze buttresses, a glass
                                         dome over a glowing reactor core, conveyor tubes with light rings, a robot
                                         assembly bay, a landing pad with a cargo drone
  oil_l1      wooden derrick (DL ≤ 5)    a timber lattice derrick with a sheave on top, a nodding pumpjack, a black
                                         pond in a plank kerb, a plank engine shed with a smoking flue, barrels
  oil_l2      steel derrick (DL 6)       a steel lattice derrick, two pumpjacks, pipe runs to a storage tank, a pump
                                         house, a slush pit of black oil, a tanker truck
  oil_l3      oil complex (DL 7)         tanks with spiral stairs, a distillation column with platforms, a flare stack
                                         with a flame, pipe racks, a separator basin of black oil
  oil_l4      plasma extractor (DL ≥ 8)  a steel drill spire with a glowing ring over a lit well-head, tanks with light
                                         bands, cyan pipes, a black reservoir in a lit steel frame

Run:   python3 tools/blender/industry_assets.py game/assets/models [name ...]

Conventions (same as evolution_assets.py / tower_assets.py): Z up, base on Z=0, origin = hex centre, front faces −Y
(Godot +Z, towards the camera); everything within radius 0.8 of the hex centre. Procedural colours are baked into
one texture through evolution_assets' tight atlas; emissive materials (lit windows, fire, light strips) and the
glossy black oil stay separate so they keep glowing / shining in Godot. Chimney mouths carry "smoke" empties
(evolution_assets.smoke_at) that are exported with the model: the game hangs a smoke plume on each.
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
from evolution_assets import (bx, cy, cn, ico, uvs, rod, beam, taper_box, extrude, pad, flat, tex, stone, glow,  # noqa: E402
                              win_lit, build_at, shade, smoke_at, hemi, gable_roof, steel_facade, facade, hazard,
                              hazard_ring, lr_ring, _MB, WOOD, WOOD_D, WOOD_L, STONE, STONE_D, BRICK, CONC, CONC_D,
                              GOLD, CYAN, TIMBER, ROOF_TRIM)

IRON = "#2e3034"
SOOT = "#2b2726"
CREAM = "#d8cfc0"  # dressed stone trim (cornices, sills, the band on the stacks)
SLATE_N = "#56657a"  # neutral blue-grey slate (the forts' and towers' roofs: no team colour)
COAL = "#26252a"
OIL = "#0b0a0e"
RUST = "#8a4a2c"
SAFETY = "#f2b31d"  # crane yellow
STEEL = "#7f8995"
STEEL_D = "#5c6570"


# ------------------------------------------------------------------ materials


def oil_mat():
    """Black crude: glossy and a little metallic, so it keeps its own shader (never baked) and shines in the game."""
    return kit.mat("oil", OIL, 0.06, 0.55)


def coal_mat():
    return tex("plaster", COAL, 6.0)


def corrugated(c, pitch=0.012, k=0.78):
    """Corrugated sheet: thin dark grooves running down the slope / up the wall (world-space, baked)."""
    key = ("corr", c, pitch, k)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("corrugated")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sp = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sp.inputs[0])

    def mth(op, a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L.new(v, n.inputs[i])
        return n.outputs[0]
    u = mth("ADD", sp.outputs[0], sp.outputs[1])
    g = mth("LESS_THAN", mth("FRACT", mth("DIVIDE", u, pitch), None), 0.3)
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    L.new(g, ev._sock(mx, "Factor_Float"))
    ev._sock(mx, "A_Color").default_value = (*kit.srgb(c), 1)
    ev._sock(mx, "B_Color").default_value = (*kit.srgb(shade(c, k)), 1)
    b = nt.nodes["Principled BSDF"]
    L.new(ev._sock(mx, "Result_Color", True), b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    kit._MATS[key] = m
    return m


# ------------------------------------------------------------------ small parts


def window(x, y, z, rz=0.0, w=0.04, h=0.07, lit=False, frame=CREAM, arch=True):
    """A tall factory window on a wall facing −Y (turned rz): a pale dressed surround, a sill and a lintel standing
    proud, the pane dark or warm-lit (emissive)."""
    def b():
        bx((w + 0.016, 0.008, h + 0.014), (0, 0.0, 0), flat("frame" + frame, frame, 0.7), bev=0)
        bx((w, 0.012, h), (0, -0.002, 0), win_lit() if lit else flat("pane", "#2a3340", 0.4), bev=0)
        bx((w + 0.024, 0.016, 0.01), (0, -0.004, -h / 2 - 0.008), flat("frame" + frame, frame, 0.7), bev=0)
        if arch:
            bx((w + 0.02, 0.014, 0.014), (0, -0.003, h / 2 + 0.01), flat("frame" + frame, frame, 0.7), bev=0)
        bx((0.005, 0.014, h), (0, -0.004, 0), flat("glazing_bar", "#3a3330", 0.7), bev=0)
    build_at(b, x, y, rz, z=z)


def barrel(x, y, z=0.0, r=0.022, h=0.05, c="#8d5f35", hoop=IRON, lie=None):
    """A cask with two dark hoops; lie=angle lays it on its side (axis along that angle)."""
    def b():
        cy(r, h, (0, 0, 0), tex("wood", c, 4.0), 8)
        for dz in (-h * 0.3, h * 0.3):
            cy(r + 0.0015, 0.006, (0, 0, dz), flat("hoop" + hoop, hoop, 0.5), 8)
    if lie is None:
        build_at(b, x, y, z=z + h / 2)
    else:
        build_at(b, x, y, lie, tilt=(0, math.pi / 2), z=z + r)


def crate(x, y, s, z=0.0, rz=0.0, c="#a77b48"):
    bx((s, s, s), (x, y, z + s / 2), tex("wood", c, 5.0), rz, 0)
    bx((s + 0.003, s * 0.2, s + 0.003), (x, y, z + s / 2), tex("wood", WOOD_D, 3.0), rz, 0)


def lantern_post(x, y, h=0.22, wood=None):
    """A timber post with an arm and a warm lantern hanging from it (the lit lanterns of frames 3–4)."""
    wood = wood or tex("wood", "#6e4526")
    bx((0.022, 0.022, h), (x, y, h / 2), wood, bev=0)
    beam((x, y, h - 0.012), (x - 0.06, y, h - 0.012), 0.016, wood)
    iron = flat("iron", IRON, 0.5)
    bx((0.03, 0.03, 0.006), (x - 0.055, y, h - 0.03), iron, bev=0)
    bx((0.024, 0.024, 0.034), (x - 0.055, y, h - 0.05), glow("lantern", "#ffc25a", 4.0), bev=0)
    bx((0.03, 0.03, 0.006), (x - 0.055, y, h - 0.07), iron, bev=0)


def rails(p0, p1, gauge=0.05, z=0.012, sleeper=0.055, wood=None, steel=None):
    """A narrow-gauge track from p0 to p1 (x, y): timber sleepers under two steel rails."""
    wood = wood or tex("wood", "#5e3d24", 3.0)
    steel = steel or flat("rail", "#6d7178", 0.4)
    (x0, y0), (x1, y1) = p0, p1
    L = math.hypot(x1 - x0, y1 - y0)
    a = math.atan2(y1 - y0, x1 - x0)
    n = max(2, int(L / sleeper))
    for k in range(n):
        f = (k + 0.5) / n
        bx((0.022, gauge + 0.036, 0.01), (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, z + 0.005), wood, a, 0)
    ox, oy = -math.sin(a) * gauge / 2, math.cos(a) * gauge / 2
    for s_ in (-1, 1):
        beam((x0 + s_ * ox, y0 + s_ * oy, z + 0.013), (x1 + s_ * ox, y1 + s_ * oy, z + 0.013), 0.008, steel)


def wagon(x, y, rz, load="bricks", gauge=0.05, z=0.0):
    """A small four-wheeled rail wagon (timber box, iron corners and wheels) loaded with bricks or coal."""
    def b():
        wd = tex("wood", "#7a4f2c", 3.0)
        iron = flat("iron", IRON, 0.5)
        bx((0.14, 0.075, 0.012), (0, 0, 0.036), iron, bev=0)  # the chassis
        taper_box((0.13, 0.072, 0.05), (0, 0, 0.067), wd, top=(1.08, 1.1))
        for sx in (-1, 1):
            bx((0.008, 0.08, 0.052), (sx * 0.066, 0, 0.067), iron, bev=0)
        for sx in (-0.042, 0.042):
            for sy in (-1, 1):
                cy(0.019, 0.01, (sx, sy * gauge / 2, 0.026), iron, 8, rot=(math.pi / 2, 0, 0))
        if load == "bricks":
            br = stone(BRICK, 3.0)
            for i in range(3):
                bx((0.036, 0.062, 0.03), (-0.042 + i * 0.042, 0, 0.1), br, bev=0)
            bx((0.034, 0.06, 0.026), (-0.02, 0, 0.126), br, bev=0)
        else:
            hemi(0.066, (0, 0, 0.088), coal_mat(), 8, 2, (1.0, 0.52, 0.5))
    build_at(b, x, y, rz, z=z)


def brick_pallet(x, y, rz=0.0, h=2):
    """A pallet of stacked bricks: a timber pallet with h courses of brick blocks (a brick works' signature props)."""
    def b():
        bx((0.09, 0.07, 0.012), (0, 0, 0.006), tex("wood", WOOD_L, 4.0), bev=0)
        br = stone(BRICK, 3.4)
        for k in range(h):
            bx((0.084, 0.064, 0.03), (0, 0, 0.012 + 0.015 + k * 0.031), br, bev=0)
        bx((0.086, 0.008, 0.026 * h), (0, -0.0, 0.012 + 0.013 * h), flat("strap", "#3d3f45", 0.5), bev=0)
    build_at(b, x, y, rz)


def coal_heap(x, y, r=0.1, h=0.06, seed=0):
    """A heap of coal: a dark mound with lumps on its flanks and crown, a shade lighter (the glint of anthracite)."""
    rnd = random.Random(seed)
    cm = coal_mat()
    lump = tex("plaster", "#4a4952", 5.0)
    hemi(r, (x, y, 0.0), cm, 10, 3, (1.0, 0.85, h / r))
    for k in range(10):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(0.2, 0.9) * r
        zz = h * (1 - (d / r) ** 2) ** 0.5 * 0.92
        ico(rnd.uniform(0.012, 0.02), (x + math.cos(a) * d, y + math.sin(a) * d * 0.85, zz), lump if k % 2 else cm,
            (1.2, 1.0, 0.8))


def drying_shed(x, y, L, w, rz=0.0, roof_c=SLATE_N, rows=3):
    """An open-sided hack shed of a brick works: a slate gable roof on timber posts over rows of pale green (unfired)
    bricks stacked to dry, along local X (turned rz)."""
    def b():
        timber = tex("wood", "#6e4526")
        n = 4
        for i in range(n):
            u = -L / 2 + 0.015 + i * (L - 0.03) / (n - 1)
            for sv in (-1, 1):
                bx((0.016, 0.016, 0.1), (u, sv * (w / 2 - 0.008), 0.05), timber, bev=0)
        for sv in (-1, 1):
            bx((L, 0.018, 0.016), (0, sv * (w / 2 - 0.008), 0.1), timber, bev=0)
        gable_roof(L, w, 0.06, (0, 0, 0.108), roof_c, tex("wood", "#7a5232", 2.0), n=3, ohx=0.02, oh=0.02,
                   **ev.SOFT_ROOF)
        green = stone("#c9a07a", 3.4)
        for j in range(rows):
            v = (j - (rows - 1) / 2) * (w - 0.05) / max(1, rows - 1) * 0.8
            bx((L - 0.06, 0.026, 0.05), (0, v, 0.025 + 0.004), green, bev=0)
    build_at(b, x, y, rz)


def coal_bunker(x, y, rz=0.0, w=0.24, d=0.16, h=0.05, seed=3):
    """A coal heap in a timber bunker: plank walls on posts on three sides, the open side facing −Y (turned rz)."""
    def b():
        pl = tex("wood", "#6a4a30", 3.0)
        post = tex("wood", "#4e3420", 2.0)
        bx((w, 0.014, h), (0, d / 2, h / 2), pl, bev=0)
        for sx in (-1, 1):
            bx((0.014, d, h), (sx * w / 2, 0, h / 2), pl, bev=0)
            for sy in (-1, 1):
                bx((0.02, 0.02, h + 0.02), (sx * w / 2, sy * d / 2, (h + 0.02) / 2), post, bev=0)
        coal_heap(0, 0.01, w * 0.46, h * 1.5, seed)
    build_at(b, x, y, rz)


def ground_strip(pts, mt, z0=0.008, z1=0.016):
    """A thin patch of ground (a cinder track bed, a stained apron) lying on the yard pad."""
    return extrude(pts, z0, z1, mt)


def brick_stack(x, y, h, r0=0.052, r1=0.036, base=0.12, band=CREAM, iron=True):
    """A tall round brick stack on a square base: a pale stone band, iron hoops and a sooty corbelled crown
    (city_dl5's works stacks). Returns the mouth height (a smoke marker goes there)."""
    bm = stone("#9a3d30", 2.0)
    bx((base, base, 0.1), (x, y, 0.05), stone("#7d3329", 2.0), bev=0)
    bx((base + 0.016, base + 0.016, 0.016), (x, y, 0.106), flat("cap" + CREAM, CREAM, 0.7), bev=0)
    cy(r0, h - 0.11, (x, y, 0.11 + (h - 0.11) / 2), bm, 10, r2=r1)
    rr = lambda z: r0 + (r1 - r0) * (z - 0.11) / (h - 0.11)  # noqa: E731
    cy(rr(h * 0.72) + 0.006, 0.03, (x, y, h * 0.72), flat("band" + band, band, 0.7), 10)
    if iron:
        for z in (h * 0.35, h * 0.52):
            cy(rr(z) + 0.003, 0.008, (x, y, z), flat("iron", IRON, 0.5), 10)
    cy(r1 + 0.012, 0.05, (x, y, h - 0.02), flat("soot", SOOT, 0.9), 10, r2=r1 + 0.006)
    cy(r1 - 0.006, 0.004, (x, y, h + 0.006), flat("flue", "#141211", 0.9), 10)
    smoke_at(x, y, h + 0.01)
    return h + 0.01


# ------------------------------------------------------------------ factory_l1


def factory_l1():
    """Brick works (DL ≤ 5; reference frames 3–4 for the lived-in yard, city_dl5's works for the hall): a brick hall
    on a pale plinth under a slate sawtooth roof whose north lights face the camera (three warm-lit glazed bands),
    tall arched windows with dressed surrounds (some lit), a gate with a signboard; a bottle kiln with iron hoops and
    a glowing mouth; two tall brick stacks with stone bands and sooty crowns; a boiler house; a flagged yard with a
    narrow-gauge track, a wagon of bricks, a coal heap, pallets of bricks, a timber jib crane lifting a pallet,
    crates, barrels and a lantern."""
    pad(0.72, stone("#958b7d", 2.2), 0.012, 16, 0.05, 7, 1.0, 0.94)
    roof_c = SLATE_N
    brick = stone(BRICK, 1.4)
    trim = flat("trim" + CREAM, CREAM, 0.7)
    # the hall: brick walls on a pale plinth, a cornice; the sawtooth teeth run front to back, so their jagged
    # profile stands on the front gable (city_dl5's works), the north lights face −X (towards the camera's left)
    hx, hy, W, D, H = -0.03, 0.1, 0.62, 0.38, 0.2
    bx((W, D, H), (hx, hy, H / 2), brick, bev=0)
    bx((W + 0.012, D + 0.012, 0.032), (hx, hy, 0.016), stone(STONE, 1.0), bev=0)
    bx((W + 0.016, D + 0.016, 0.016), (hx, hy, H + 0.004), trim, bev=0)
    for sx in (-1, 1):  # brick pilasters at the corners
        for sy in (-1, 1):
            bx((0.03, 0.03, H), (hx + sx * W / 2, hy + sy * D / 2, H / 2), stone("#8f3a2e", 1.4), bev=0)
    glass = facade("#44546a", "#7fa7c4", 0.034, 0.03, 0.7, 0.66, lit="#ffd27a", lit_p=0.4)
    build_at(lambda: ev.sawtooth_roof(W, D, 4, 0.12, (0, 0, 0), roof_c, brick, glass), hx, hy, math.pi,
             z=H + 0.012)
    # tall windows on the front and the left side, the gate in the front
    yf = hy - D / 2
    for i, x in enumerate((-0.25, -0.17, -0.09, 0.2, 0.27)):
        window(hx + x, yf - 0.002, 0.105, 0.0, 0.042, 0.09, lit=i in (1, 3))
    for i, y in enumerate((-0.12, -0.04, 0.04, 0.12)):
        window(hx - W / 2 - 0.002, hy + y, 0.105, -math.pi / 2, 0.042, 0.09, lit=i in (1, 2))
    gx = hx + 0.06
    bx((0.12, 0.02, 0.16), (gx, yf - 0.002, 0.08), trim, bev=0)  # the gate's dressed surround
    bx((0.09, 0.02, 0.14), (gx, yf - 0.006, 0.07), tex("wood", WOOD_D, 3.0), bev=0)
    bx((0.004, 0.022, 0.14), (gx, yf - 0.008, 0.07), flat("iron", IRON, 0.5), bev=0)
    bx((0.16, 0.012, 0.036), (gx, yf - 0.008, 0.182), flat("sign", "#3f4958", 0.7), bev=0)  # the signboard
    bx((0.12, 0.014, 0.008), (gx, yf - 0.009, 0.182), trim, bev=0)
    # the boiler house on the right, gable roof of slate courses, a lit window
    bhx, bhy = 0.38, 0.18
    bx((0.16, 0.22, 0.15), (bhx, bhy, 0.075), brick, bev=0)
    bx((0.172, 0.232, 0.024), (bhx, bhy, 0.012), stone(STONE, 1.0), bev=0)
    gable_roof(0.22, 0.16, 0.08, (bhx, bhy, 0.15), roof_c, brick, rz=math.pi / 2, n=4, **ev.SOFT_ROOF)
    window(bhx, bhy - 0.111, 0.08, 0.0, 0.04, 0.07, lit=True)
    # the bottle kiln at the front left: a stone plinth, a brick bottle with iron hoops, a sooty neck, a glowing mouth
    kx, ky = -0.47, -0.2
    cy(0.135, 0.05, (kx, ky, 0.025), stone(STONE, 1.0), 14)
    for (z0, z1, r0, r1) in ((0.05, 0.2, 0.125, 0.108), (0.2, 0.3, 0.108, 0.056), (0.3, 0.37, 0.05, 0.046)):
        cy(r0, z1 - z0, (kx, ky, (z0 + z1) / 2), brick, 14, r2=r1)
    for (z, r) in ((0.09, 0.122), (0.15, 0.115), (0.24, 0.088)):
        cy(r + 0.004, 0.01, (kx, ky, z), flat("iron", IRON, 0.5), 14)
    cy(0.058, 0.03, (kx, ky, 0.375), flat("soot", SOOT, 0.9), 12, r2=0.054)
    cy(0.04, 0.004, (kx, ky, 0.392), flat("flue", "#141211", 0.9), 10)
    smoke_at(kx, ky, 0.395)
    # the firing mouth facing the camera: a dressed arch round a glowing opening
    bx((0.07, 0.03, 0.08), (kx, ky - 0.118, 0.09), trim, bev=0)
    bx((0.05, 0.03, 0.06), (kx, ky - 0.124, 0.08), glow("fire", "#ff8a2a", 3.0), bev=0)
    # two tall brick stacks behind the hall
    brick_stack(-0.2, 0.4, 0.9)
    brick_stack(0.16, 0.42, 0.76, r0=0.046, r1=0.034, base=0.11)
    # the yard: a track from the front-right edge into the gate, a wagon of bricks on it
    ground_strip([(gx - 0.065, -0.67), (gx + 0.065, -0.67), (gx + 0.06, yf - 0.01), (gx - 0.06, yf - 0.01)],
                 tex("plaster", "#5d5550", 4.0))
    rails((gx, -0.66), (gx, yf - 0.02), z=0.016)
    wagon(gx, -0.3, math.pi / 2, "bricks", z=0.012)
    # coal heap by the kiln, a shovel in it
    ground_strip([(-0.42, -0.52), (-0.06, -0.56), (-0.04, -0.3), (-0.36, -0.36)], tex("plaster", "#4a4440", 5.0))
    coal_bunker(-0.22, -0.42, 0.12)
    beam((-0.15, -0.44, 0.04), (-0.13, -0.43, 0.15), 0.008, tex("wood", WOOD_L))
    drying_shed(-0.5, 0.17, 0.36, 0.15, math.pi / 2)
    # pallets of bricks and a timber jib crane over them, lifting a pallet towards the wagon
    brick_pallet(0.36, -0.2, 0.1, 2)
    brick_pallet(0.47, -0.27, 0.1, 3)
    brick_pallet(0.38, -0.33, -0.2, 1)
    timber = tex("wood", "#6e4526")
    cxp, cyp = 0.5, -0.08
    bx((0.03, 0.03, 0.42), (cxp, cyp, 0.21), timber, bev=0)
    bx((0.07, 0.07, 0.03), (cxp, cyp, 0.015), stone(STONE, 1.0), bev=0)
    jt = (cxp - 0.28, cyp - 0.2, 0.42)
    beam((cxp + 0.03, cyp + 0.02, 0.4), jt, 0.026, timber)  # the jib
    beam((cxp, cyp, 0.2), (cxp - 0.16, cyp - 0.115, 0.4), 0.018, timber)  # its brace
    rope = flat("rope", "#d8c8a0", 0.9)
    beam(jt, (jt[0], jt[1], 0.24), 0.005, rope)
    bx((0.012, 0.012, 0.012), (jt[0], jt[1], 0.234), flat("iron", IRON, 0.5), bev=0)

    def hung():
        brick_pallet(0, 0, 0.0, 1)
    build_at(hung, jt[0], jt[1], 0.3, z=0.17)
    for sg in (-1, 1):  # the sling from the hook to the pallet's corners
        beam((jt[0], jt[1], 0.232), (jt[0] + sg * 0.04, jt[1] + sg * 0.012, 0.212), 0.004, rope)
    cy(0.04, 0.03, (cxp + 0.01, cyp + 0.05, 0.1), tex("wood", WOOD_L), 10, rot=(math.pi / 2, 0, 0))  # the winch drum
    # crates and barrels by the gate, a lantern on a post
    crate(gx + 0.12, yf - 0.06, 0.05, rz=0.2)
    crate(gx + 0.15, yf - 0.11, 0.04, rz=-0.3)
    crate(gx + 0.13, yf - 0.08, 0.034, z=0.05, rz=0.5)
    barrel(gx - 0.1, yf - 0.06)
    barrel(gx - 0.14, yf - 0.1)
    barrel(-0.06, -0.5, lie=0.4)
    lantern_post(gx - 0.075, yf - 0.12, 0.22, timber)
    # a pile of brick rubble and spoil at the kiln's foot
    for (x, y, s) in ((-0.3, -0.27, 0.03), (-0.27, -0.3, 0.024), (-0.53, -0.3, 0.026)):
        bx((s, s * 0.7, s * 0.5), (x, y, s * 0.25 + 0.012), stone(BRICK, 3.0), 0.4, 0)


# ------------------------------------------------------------------ factory_l2


def steel_stack(x, y, h, r=0.034, r_top=None, bands=3, base_c=CONC, smoke=True):
    """A slim steel stack on a concrete footing: grey shaft, red-and-white warning bands at the top, a walkway ring
    with a rail, a dark mouth (the banded stacks of the modern works). Returns the mouth height."""
    r_top = r_top or r * 0.85
    bx((r * 3.2, r * 3.2, 0.05), (x, y, 0.025), flat("footing", base_c, 0.85), bev=0)
    cy(r, h - 0.05, (x, y, 0.05 + (h - 0.05) / 2), flat("stack_grey", "#9aa0a6", 0.5), 10, r2=r_top)
    rr = lambda z: r + (r_top - r) * (z - 0.05) / (h - 0.05)  # noqa: E731
    bh = 0.03
    for k in range(bands * 2):
        z = h - 0.01 - (k + 0.5) * bh
        c = "#d8342a" if k % 2 == 0 else "#f1eee8"
        lr_ring(x, y, rr(z) + 0.0025, z, bh, flat("band" + c, c, 0.55), 10)
    zr = h - 0.01 - bands * 2 * bh - 0.02
    cy(rr(zr) + 0.018, 0.008, (x, y, zr), flat("walk", "#3d4148", 0.5), 10)
    lr_ring(x, y, rr(zr) + 0.017, zr + 0.016, 0.006, flat("rail_y", SAFETY, 0.5), 10)
    cy(r_top - 0.006, 0.004, (x, y, h - 0.008), flat("flue", "#141211", 0.9), 10)
    if smoke:
        smoke_at(x, y, h)
    return h


def silo(x, y, r, h, c="#dedbd3", ladder=True, rz=0.0):
    """A concrete silo: a pale drum with a darker plinth band, ribs, a shallow cone cap and a caged ladder."""
    sm = tex("plaster", c, 3.0)
    cy(r, h, (x, y, h / 2), sm, 12)
    cy(r + 0.004, 0.03, (x, y, 0.015), flat("plinth", shade(c, 0.72), 0.8), 12)
    for z in (h * 0.4, h * 0.75):
        lr_ring(x, y, r + 0.0025, z, 0.01, flat("rib", shade(c, 0.8), 0.8), 12)
    cn(r + 0.006, r * 0.6, (x, y, h + r * 0.3), flat("silo_cap", "#9aa0a6", 0.5), 12)
    if ladder:
        ca, sa = math.cos(rz), math.sin(rz)
        px, py = x + ca * (r + 0.006), y + sa * (r + 0.006)
        bx((0.012, 0.012, h * 0.9), (px, py, h * 0.45), flat("ladder", "#3d4148", 0.5), rz, 0)


def truck(x, y, rz, cab="#e2782a", box="#d9d6cf", tanker=False):
    """A lorry facing +X (turned rz): a coloured cab with a dark windscreen and a box (or tank) body, six wheels."""
    def b():
        dk = flat("tyre", "#1f1f21", 0.9)
        bx((0.2, 0.05, 0.014), (0, 0, 0.022), flat("chassis", "#33363b", 0.5), bev=0)
        bx((0.05, 0.056, 0.05), (0.075, 0, 0.052), flat("cab" + cab, cab, 0.45), bev=0.004)
        bx((0.006, 0.048, 0.02), (0.1, 0, 0.062), flat("cab_glass", "#1d2a38", 0.2), bev=0)
        bx((0.004, 0.05, 0.008), (0.101, 0, 0.034), flat("bumper", "#c9ccd0", 0.4), bev=0)
        if tanker:
            cy(0.03, 0.13, (-0.03, 0, 0.06), flat("tank" + box, box, 0.35), 10, rot=(0, math.pi / 2, 0))
            bx((0.05, 0.016, 0.008), (-0.03, 0, 0.092), flat("walk", "#3d4148", 0.5), bev=0)
        else:
            bx((0.13, 0.058, 0.06), (-0.03, 0, 0.06), flat("box" + box, box, 0.6), bev=0.003)
            bx((0.132, 0.06, 0.008), (-0.03, 0, 0.034), flat("stripe_o", "#e2782a", 0.5), bev=0)
        for u in (-0.07, -0.04, 0.075):
            for sy in (-1, 1):
                cy(0.016, 0.012, (u, sy * 0.026, 0.016), dk, 8, rot=(math.pi / 2, 0, 0))
    build_at(b, x, y, rz)


def ribbon(x0, x1, y, z, h, rz=0.0, n=8, lit=(), frame="#4a4f57"):
    """A ribbon of windows on a wall facing −Y (turned rz about (x0, y)): a dark frame band, n panes (the ones in
    `lit` warm-lit), a pale sill. Runs along local +X from x0 to x1."""
    L = x1 - x0

    def b():
        bx((L, 0.008, h + 0.012), (L / 2, 0, 0), flat("rframe", frame, 0.6), bev=0)
        pw = L / n
        for i in range(n):
            bx((pw - 0.008, 0.012, h), ((i + 0.5) * pw, -0.002, 0),
               win_lit() if i in lit else flat("pane", "#2a3340", 0.35), bev=0)
        bx((L + 0.01, 0.016, 0.008), (L / 2, -0.004, -h / 2 - 0.008), flat("sill" + CONC, "#e4e0d8", 0.7), bev=0)
    build_at(b, x0, y, rz, z=z)


def low_roof(w, d, h, loc, mt, rz=0.0, oh=0.012):
    """A low-pitched gable roof (ridge along local X) as a closed prism: two slopes, gable ends in the same sheet."""
    W, D = w / 2 + oh, d / 2 + oh
    verts = [(-W, -D, 0), (W, -D, 0), (W, 0, h), (-W, 0, h), (-W, D, 0), (W, D, 0)]
    faces = [(0, 1, 2, 3), (3, 2, 5, 4), (0, 3, 4), (1, 5, 2)]
    return ev.mesh_obj(verts, faces, mt, loc, (0, 0, rz))


def conveyor_gallery(p0, p1, w, h, legs=2, clad="#c9c3b6", win=True):
    """An enclosed conveyor gallery (a long box on a slope) from p0 to p1 (centre line of its floor), corrugated
    cladding, a strip of small windows along it, a roof plate, on steel trestles down to the ground."""
    a, b = Vector(p0), Vector(p1)
    d = b - a
    L = d.length
    yaw = math.atan2(d.y, d.x)
    pitch = math.atan2(d.z, math.hypot(d.x, d.y))
    mid = (a + b) / 2

    def body():
        bx((L, w, h), (0, 0, h / 2), corrugated(clad, 0.01, 0.84), bev=0)
        bx((L + 0.01, w + 0.012, 0.01), (0, 0, h + 0.004), flat("groof", "#5b6168", 0.6), bev=0)
        if win:
            for sy in (-1, 1):
                bx((L * 0.86, 0.004, h * 0.26), (0, sy * (w / 2 + 0.001), h * 0.62), flat("gwin", "#2a3340", 0.35),
                   bev=0)
    build_at(lambda: build_at(body, 0, 0, 0, tilt=(0, -pitch)), mid.x, mid.y, yaw, z=mid.z)
    st = flat("trestle", "#59606a", 0.5)
    for k in range(legs):
        f = (k + 1) / (legs + 1)
        q = a.lerp(b, f)
        ox, oy = -math.sin(yaw) * w * 0.55, math.cos(yaw) * w * 0.55
        for sg in (-1, 1):
            beam((q.x + sg * ox * 1.3, q.y + sg * oy * 1.3, 0.0), (q.x + sg * ox, q.y + sg * oy, q.z), 0.012, st)
        beam((q.x - ox, q.y - oy, q.z * 0.55), (q.x + ox, q.y + oy, q.z * 0.55), 0.01, st)


def gantry_crane(x, y, span, h, rz=0.0, c=SAFETY):
    """A yellow overhead gantry crane on rails (turned rz; spans local X): two A-frame legs, a box girder, a trolley
    with a cab, the hook block, a container hanging from it."""
    def b():
        yel = flat("crane" + c, c, 0.45)
        dk = flat("crane_d", "#3d4148", 0.5)
        for sx in (-1, 1):
            for sy in (-1, 1):
                beam((sx * span / 2, sy * 0.06, 0.0), (sx * span / 2, sy * 0.02, h), 0.018, yel)
            bx((0.03, 0.15, 0.014), (sx * span / 2, 0, 0.012), dk, bev=0)  # the bogie
            beam((sx * span / 2, -0.045, h * 0.3), (sx * span / 2, 0.045, h * 0.3), 0.012, yel)
        bx((span + 0.06, 0.05, 0.034), (0, 0, h + 0.017), yel, bev=0)
        bx((span + 0.06, 0.054, 0.006), (0, 0, h + 0.036), hazard(0.03), bev=0)
        bx((0.05, 0.07, 0.03), (span * 0.12, 0, h - 0.008), dk, bev=0)  # trolley
        bx((0.034, 0.03, 0.03), (span * 0.12 + 0.02, -0.045, h - 0.03), yel, bev=0)  # operator's cab
        bx((0.026, 0.004, 0.016), (span * 0.12 + 0.02, -0.061, h - 0.028), flat("cab_glass", "#1d2a38", 0.2), bev=0)
        for sy in (-1, 1):
            beam((span * 0.12, sy * 0.012, h - 0.02), (span * 0.12, sy * 0.012, h * 0.52), 0.004, dk)
        bx((0.02, 0.03, 0.016), (span * 0.12, 0, h * 0.5), yel, bev=0)
        bx((0.12, 0.05, 0.05), (span * 0.12, 0, h * 0.5 - 0.04), flat("cont_r", "#a8452e", 0.6), bev=0)
        for sx in (-1, 1):
            bx((0.004, 0.044, 0.044), (span * 0.12 + sx * 0.061, 0, h * 0.5 - 0.04), flat("door8", "#23282f", 0.6), bev=0)
    build_at(b, x, y, rz)


def pipe_rack(p0, p1, z, pipes=(("#d8b23a", 0.009), ("#b5413a", 0.009), ("#9aa0a6", 0.012)), posts=3):
    """A pipe rack: steel T-posts carrying a bundle of coloured pipes along p0 -> p1 at height z."""
    (x0, y0), (x1, y1) = p0, p1
    a = math.atan2(y1 - y0, x1 - x0)
    ox, oy = -math.sin(a), math.cos(a)
    st = flat("trestle", "#59606a", 0.5)
    for k in range(posts):
        f = k / max(1, posts - 1)
        px, py = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        bx((0.012, 0.012, z), (px, py, z / 2), st, bev=0)
        beam((px - ox * 0.035, py - oy * 0.035, z), (px + ox * 0.035, py + oy * 0.035, z), 0.01, st)
    n = len(pipes)
    for i, (c, r) in enumerate(pipes):
        o = (i - (n - 1) / 2) * 0.024
        rod((x0 + ox * o, y0 + oy * o, z + 0.012), (x1 + ox * o, y1 + oy * o, z + 0.012), r,
            flat("pipe" + c, c, 0.45), n=6)


def belt_conveyor(p0, p1, w=0.04, legs=3, load=6, crate_c=("#b98a52", "#8f6a3e")):
    """An open belt conveyor on trestles from p0 to p1 (x, y, z of the belt): a dark belt between yellow side rails,
    A-frame legs, crates riding on it (the conveyor that names the plant)."""
    a, b = Vector(p0), Vector(p1)
    d = b - a
    yaw = math.atan2(d.y, d.x)
    beam(tuple(a), tuple(b), w, flat("belt", "#26292e", 0.8))
    side = Vector((-math.sin(yaw), math.cos(yaw), 0)) * (w / 2 + 0.004)
    rail = flat("rail_y", SAFETY, 0.5)
    for sg in (-1, 1):
        beam(tuple(a + side * sg + Vector((0, 0, 0.008))), tuple(b + side * sg + Vector((0, 0, 0.008))), 0.008, rail)
    st = flat("trestle", "#59606a", 0.5)
    for k in range(legs):
        q = a.lerp(b, (k + 0.5) / legs)
        for sg in (-1, 1):
            beam(tuple(q + side * sg * 1.5 + Vector((0, 0, 0.012 - q.z))), tuple(q + side * sg - Vector((0, 0, 0.01))),
                 0.008, st)
    for k in range(load):
        q = a.lerp(b, (k + 0.5) / load)
        s_ = 0.026 if k % 2 else 0.03
        bx((s_, s_, s_), (q.x, q.y, q.z + 0.006 + s_ / 2), tex("wood", crate_c[k % 2], 5.0), yaw, 0)


def factory_l2():
    """Conveyor plant (DL 6–7; the modern works beside city_dl6 / port_modern): on a concrete yard, a long concrete
    hall with pilasters and warm-lit ribbon windows under a blue-grey corrugated roof with a glazed monitor along its
    ridge; an open belt conveyor carrying crates across the yard from the silos to a corrugated assembly shed with a
    hazard-framed roller door; three silos under a head house with a bucket elevator and a truck hopper, an enclosed
    gallery to the hall; two banded steel stacks; a yellow gantry crane over a loading track lifting a container;
    trucks, a pipe rack, stacked containers, lamps."""
    pad(0.74, stone("#a3a19b", 1.1), 0.012, 16, 0.03, 11, 1.0, 0.95)
    asph = flat("asphalt", "#5d6066", 0.85)
    line = flat("line_y", "#e8c547", 0.6)
    conc = tex("plaster", "#cdc8bd", 2.5)
    roof_c = "#5f6f84"
    # the long hall at the back: concrete over a darker plinth, pilasters, ribbon windows, corrugated roof, monitor
    hx, hy, W, D, H = -0.15, 0.2, 0.6, 0.26, 0.2
    bx((W, D, H), (hx, hy, H / 2), conc, bev=0)
    bx((W + 0.01, D + 0.01, 0.04), (hx, hy, 0.02), flat("plinth_c", "#8b877f", 0.8), bev=0)
    for i in range(7):
        x = hx - W / 2 + i * W / 6
        bx((0.02, D + 0.016, H), (x, hy, H / 2), flat("pilaster", "#e1ddd4", 0.8), bev=0)
    yf = hy - D / 2
    for i in range(6):
        x0 = hx - W / 2 + i * W / 6 + 0.016
        ribbon(x0, x0 + W / 6 - 0.032, yf - 0.002, 0.13, 0.065, 0.0, 3, lit=(0, 2) if i % 2 else (1,))
    xl = hx - W / 2 - 0.002  # the left end wall (it turns towards the camera in the game): one ribbon of four
    ribbon(xl, xl + D - 0.06, hy + D / 2 - 0.03, 0.13, 0.065, -math.pi / 2, 4, lit=(1, 2))
    low_roof(W, D, 0.06, (hx, hy, H), corrugated(roof_c, 0.012, 0.8), oh=0.014)
    bx((W * 0.8, 0.07, 0.05), (hx, hy, H + 0.06 + 0.012), flat("monitor", "#4d5868", 0.6), bev=0)
    bx((W * 0.76, 0.004, 0.026), (hx, hy - 0.036, H + 0.072), win_lit(), bev=0)
    bx((W * 0.82, 0.084, 0.008), (hx, hy, H + 0.1), flat("monitor_cap", "#3d4148", 0.6), bev=0)
    for x in (hx - 0.2, hx + 0.2):  # roof ventilators
        cy(0.016, 0.03, (x, hy + 0.08, H + 0.04), flat("vent", "#9aa0a6", 0.5), 8)
        cy(0.022, 0.008, (x, hy + 0.08, H + 0.058), flat("vent", "#9aa0a6", 0.5), 8)
    # the stacks behind the hall
    steel_stack(-0.36, 0.42, 0.95)
    steel_stack(-0.16, 0.44, 0.82, r=0.03)
    # the assembly shed at the front left: corrugated walls, a vault, a hazard-framed roller door facing −Y
    sx_, sy_ = -0.5, -0.12
    clad = corrugated("#b9bfc6", 0.01, 0.82)
    bx((0.2, 0.3, 0.14), (sx_, sy_, 0.07), clad, bev=0)
    R, segs = 0.1 + 0.006, 5
    arc = [(R * math.cos(math.pi * i / segs), 0.14 + 0.06 * math.sin(math.pi * i / segs)) for i in range(segs + 1)]
    vault, ends = _MB(), _MB()
    for i in range(segs):
        (u0, z0), (u1, z1) = arc[i], arc[i + 1]
        n = ((u0 + u1) / 2, 0, (z0 + z1) / 2 - 0.14)
        vault.face([(sx_ + u0, sy_ - 0.16, z0), (sx_ + u0, sy_ + 0.16, z0), (sx_ + u1, sy_ + 0.16, z1),
                    (sx_ + u1, sy_ - 0.16, z1)], n)
    for sg in (-1, 1):
        ends.face([(sx_ + u, sy_ + sg * 0.15, z) for u, z in arc], (0, sg, 0))
    vault.obj(corrugated(roof_c, 0.012, 0.8), "vault")
    ends.obj(clad, "vault_ends")
    bx((0.12, 0.012, 0.11), (sx_, sy_ - 0.152, 0.055), corrugated("#7d858f", 0.008, 0.8), bev=0)
    for sg in (-1, 1):
        bx((0.012, 0.014, 0.12), (sx_ + sg * 0.066, sy_ - 0.153, 0.06), hazard(0.02), bev=0)
    bx((0.144, 0.014, 0.012), (sx_, sy_ - 0.153, 0.122), hazard(0.02), bev=0)
    bx((0.07, 0.012, 0.02), (sx_, sy_ - 0.153, 0.175), win_lit(), bev=0)
    for k in range(3):  # windows down its side facing the camera's left
        y = sy_ - 0.09 + k * 0.09
        bx((0.004, 0.05, 0.03), (sx_ - 0.102, y, 0.1), win_lit() if k == 1 else flat("pane", "#2a3340", 0.35), bev=0)
    # three silos in a row at the back right under a head house, a bucket elevator with a truck hopper at its foot
    for x in (0.27, 0.42, 0.57):
        silo(x, 0.34, 0.07, 0.4, ladder=False)
    bx((0.44, 0.07, 0.05), (0.42, 0.34, 0.445), corrugated("#c9c3b6", 0.01, 0.84), bev=0)
    bx((0.45, 0.08, 0.01), (0.42, 0.34, 0.475), flat("groof", "#5b6168", 0.6), bev=0)
    bx((0.3, 0.004, 0.014), (0.42, 0.304, 0.448), win_lit(), bev=0)
    ex, ey = 0.66, 0.16
    bx((0.045, 0.045, 0.52), (ex, ey, 0.26), corrugated("#d6a13a", 0.01, 0.8), bev=0)
    bx((0.07, 0.06, 0.04), (ex, ey, 0.53), flat("hood", "#5b6168", 0.6), bev=0)
    beam((ex - 0.01, ey + 0.02, 0.52), (0.62, 0.32, 0.46), 0.018, flat("chute", "#59606a", 0.5))
    taper_box((0.09, 0.09, 0.06), (ex - 0.02, ey - 0.11, 0.045), flat("hopper", "#59606a", 0.5), top=(1.3, 1.3))
    bx((0.118, 0.118, 0.006), (ex - 0.02, ey - 0.11, 0.078), hazard(0.025), bev=0)
    beam((ex - 0.01, ey - 0.08, 0.06), (ex, ey - 0.02, 0.06), 0.02, flat("chute", "#59606a", 0.5))
    # the open belt conveyor: from the silos' foot down the yard, then across it to the assembly shed, crates on it
    belt_conveyor((0.42, 0.29, 0.075), (0.42, -0.04, 0.075), 0.04, legs=2, load=3)
    belt_conveyor((0.42, -0.06, 0.075), (sx_ + 0.1, -0.06, 0.1), 0.04, legs=4, load=7)
    bx((0.06, 0.06, 0.1), (0.42, -0.06, 0.05), flat("transfer", "#7d858f", 0.6), bev=0)
    # the gantry crane over a loading track in the front yard, a truck under it
    ev.extrude([(-0.3, -0.45), (0.32, -0.45), (0.32, -0.23), (-0.3, -0.23)], 0.008, 0.016, asph)
    for k in range(4):
        bx((0.06, 0.008, 0.002), (-0.22 + k * 0.16, -0.24, 0.017), line, bev=0)
    rails((-0.26, -0.34), (0.28, -0.34), gauge=0.16, z=0.016, sleeper=0.05)
    gantry_crane(-0.02, -0.34, 0.3, 0.24)
    truck(0.08, -0.34, math.pi, cab="#2f6db3")
    truck(0.3, -0.58, 0.6, cab="#e2782a", box="#d9d6cf")
    truck(ex - 0.03, ey - 0.3, math.pi / 2, cab="#c9ccd0", box="#7b838e", tanker=False)
    # a pipe rack from the hall to the bucket elevator, stacked containers, lamps
    pipe_rack((hx + W / 2 + 0.01, 0.13), (0.62, 0.13), 0.15, posts=3)
    for (x, y, z, c) in ((-0.28, -0.58, 0.0, "#a8452e"), (-0.28, -0.525, 0.0, "#7b838e"),
                         (-0.28, -0.55, 0.05, "#c99a2e")):
        bx((0.12, 0.05, 0.05), (x, y, 0.012 + z + 0.025), flat("cont" + c, c, 0.6), 0.1, bev=0)
    for (x, y) in ((-0.56, -0.38), (0.3, -0.17), (-0.26, 0.03)):
        ev.street_lamp(x, y, 0.2, modern=True)


# ------------------------------------------------------------------ factory_l3 (the DL8 steel kit, team-neutral)


BRONZE8 = "#a77c45"  # the warm bronze columns and pipes of reference frame 5's works


def kit8():
    """evolution_assets.d8_mats without a team (steel, plate, seam, panel, cap, neon, tip): dark steel inset panels
    instead of team panels, cold-blue light strips (the lit seams of frames 2 and 5) and the cyan tips."""
    return (steel_facade(), flat("plate8", "#505760", 0.45), flat("seam8", "#8c939c", 0.45),
            flat("panel8n", "#343c48", 0.4), flat("spire8", "#4c535d", 0.35),
            glow("strip_cold", "#86c8ff", 2.0), glow("cyan", CYAN, 2.5))


def light_slots(x, y, w, z0, z1, n, mats, rz=0.0, inset=0.6):
    """Tall cold light slots in dark inset panels on a wall facing −Y (turned rz about (x, y)): frame 5's glowing
    slots between the buttresses."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        pm, sm = _MB(), _MB()
        step = w / n
        for i in range(n):
            u = -w / 2 + (i + 0.5) * step
            hw = step * inset / 2
            pm.face([(u - hw, -0.002, z0), (u + hw, -0.002, z0), (u + hw, -0.002, z1), (u - hw, -0.002, z1)], (0, -1, 0))
            sm.face([(u - 0.007, -0.004, z0 + 0.01), (u + 0.007, -0.004, z0 + 0.01), (u + 0.007, -0.004, z1 - 0.01),
                     (u - 0.007, -0.004, z1 - 0.01)], (0, -1, 0))
        pm.obj(panel, "slot_panels")
        sm.obj(neon, "slots")
    build_at(b, x, y, rz)


def funnel(x, y, z0, z1, r, mats, smoke=True):
    """A great steel funnel (frame 5's two stacks): a bronze collar, steel shaft with a plate band, a cold light ring
    under a flared lip, a dark mouth."""
    st, plate, seam, panel, cap, neon, tip = mats
    cy(r + 0.012, 0.03, (x, y, z0 + 0.015), flat("bronze8", BRONZE8, 0.4), 12)
    cy(r, z1 - z0, (x, y, (z0 + z1) / 2), flat("funnel8", "#8a929c", 0.4), 12)
    lr_ring(x, y, r + 0.003, z0 + (z1 - z0) * 0.45, 0.02, plate, 12)
    lr_ring(x, y, r + 0.003, z1 - 0.06, 0.012, neon, 12)
    cy(r + 0.01, 0.026, (x, y, z1 - 0.008), plate, 12, r2=r + 0.016)
    cy(r - 0.004, 0.004, (x, y, z1 + 0.004), flat("flue", "#141211", 0.9), 12)
    if smoke:
        smoke_at(x, y, z1 + 0.01)


def robot_arm(x, y, rz, s=1.0, c="#e8a23a"):
    """An industrial robot arm (turned rz, reaching along local +X): a dark base, an orange turret, two arm links
    and a wrist with a cold-lit gripper."""
    def b():
        org = flat("robot" + c, c, 0.45)
        dk = flat("robot_d", "#2c3138", 0.5)
        cy(0.018, 0.01, (0, 0, 0.005), dk, 8)
        cy(0.013, 0.02, (0, 0, 0.02), org, 8)
        p0, p1, p2 = (0.0, 0.0, 0.03), (0.018, 0.0, 0.075), (0.055, 0.0, 0.06)
        beam(p0, p1, 0.012, org)
        beam(p1, p2, 0.009, org)
        ico(0.008, p1, dk)
        beam(p2, (0.06, 0.0, 0.04), 0.006, dk)
        bx((0.006, 0.014, 0.006), (0.06, 0.0, 0.036), glow("cyan", CYAN, 2.5), bev=0)
    build_at(b, x, y, rz, s=s)


def cargo_drone(x, y, z, rz, mats, crate_c="#b8862e"):
    """A heavy cargo drone (turned rz): a steel body with a cold eye, four rotor arms with dark discs and lit hubs,
    a container slung under it."""
    st, plate, seam, panel, cap, neon, tip = mats

    def b():
        bx((0.06, 0.05, 0.02), (0, 0, 0.05), seam, bev=0)
        bx((0.03, 0.004, 0.008), (0.0, -0.027, 0.05), tip, bev=0)
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            ex, ey = math.cos(a) * 0.055, math.sin(a) * 0.055
            beam((0, 0, 0.052), (ex, ey, 0.056), 0.008, plate)
            cy(0.026, 0.003, (ex, ey, 0.06), flat("rotor", "#1d2026", 0.4), 8)
            cy(0.005, 0.008, (ex, ey, 0.06), tip, 4)
        bx((0.07, 0.04, 0.036), (0, 0, 0.018), flat("cont8" + crate_c, crate_c, 0.6), bev=0)
        for sx in (-1, 1):
            bx((0.004, 0.034, 0.03), (sx * 0.036, 0, 0.018), flat("door8", "#23282f", 0.6), bev=0)
    build_at(b, x, y, rz, z=z)


def tube_bridge(p0, p1, r, mats, rings=3):
    """An enclosed conveyor tube from p0 to p1 (pale steel) with cold light rings round it."""
    st, plate, seam, panel, cap, neon, tip = mats
    rod(p0, p1, r, seam, n=8)
    a, b = Vector(p0), Vector(p1)
    for k in range(rings):
        q = a.lerp(b, (k + 1) / (rings + 1))
        rod(tuple(q - (b - a).normalized() * 0.006), tuple(q + (b - a).normalized() * 0.006), r + 0.004, neon, n=8)


def factory_l3():
    """Robotic combine (DL ≥ 8; reference frame 5's works in the steel kit of residence_dl8 / district_scifi): on a
    round steel deck with a cold light ring, a core block with bronze buttresses between tall cold light slots in dark
    inset panels, a setback crown and two great funnels with light rings (smoke markers); a reactor drum with a cage of
    pale ribs round a glowing cyan core; conveyor tubes with light rings to a transfer tower and an open robot bay
    where orange robot arms work along a lit production line; a landing pad with a cargo drone; tanks with light
    bands, light masts, a lit avenue to the portal."""
    mats = kit8()
    st, plate, seam, panel, cap, neon, tip = mats
    bronze = flat("bronze8", BRONZE8, 0.4)
    ev.lr_deck(0.72, mats, 7)
    ev.d8_road((0.02, -0.7), (0.02, -0.0), 0.08, mats, z=0.02)
    # the core block
    cx_, cy_, W, D, H = -0.06, 0.2, 0.38, 0.28, 0.34
    bx((W + 0.03, D + 0.03, 0.03), (cx_, cy_, 0.031), plate, bev=0)
    bx((W, D, H), (cx_, cy_, H / 2), st, bev=0)
    bx((W + 0.012, D + 0.012, 0.018), (cx_, cy_, 0.11), seam, bev=0)
    light_slots(cx_, cy_ - D / 2, W - 0.04, 0.125, H - 0.03, 4, mats)
    light_slots(cx_ - W / 2, cy_, D - 0.04, 0.125, H - 0.03, 3, mats, rz=-math.pi / 2)
    for i in range(5):  # bronze buttresses between the slots on the front, and at the corners
        u = cx_ - W / 2 + i * W / 4
        bx((0.026, 0.03, H + 0.01), (u, cy_ - D / 2 - 0.004, (H + 0.01) / 2), bronze, bev=0)
    for sy in (-1, 1):
        bx((0.03, 0.026, H + 0.01), (cx_ - W / 2 - 0.004, cy_ + sy * (D / 2 - 0.02), (H + 0.01) / 2), bronze, bev=0)
    bx((W * 0.8, D * 0.78, 0.06), (cx_, cy_, H + 0.03), st, bev=0)
    bx((W * 0.84, D * 0.82, 0.012), (cx_, cy_, H + 0.064), plate, bev=0)
    bx((W * 0.8 + 0.008, D * 0.78 + 0.008, 0.01), (cx_, cy_, H + 0.01), neon, bev=0)
    funnel(cx_ - 0.09, cy_ + 0.04, H + 0.07, 0.88, 0.06, mats)
    funnel(cx_ + 0.07, cy_ + 0.05, H + 0.07, 0.8, 0.052, mats)
    ev.d8_portal(cx_ + 0.08, cy_ - D / 2 - 0.035, 0.0, mats)
    # the reactor: a steel drum, a cage of pale ribs round a glowing core
    rx, ry = 0.38, 0.26
    cy(0.15, 0.03, (rx, ry, 0.03), plate, 14)
    cy(0.13, 0.1, (rx, ry, 0.08), st, 14)
    lr_ring(rx, ry, 0.134, 0.1, 0.03, panel, 14)
    lr_ring(rx, ry, 0.136, 0.1, 0.008, neon, 14)
    cy(0.14, 0.014, (rx, ry, 0.137), plate, 14)
    ico(0.085, (rx, ry, 0.2), glow("core8", "#7ff0ff", 3.0), (1, 1, 0.95), sub=2)
    ev.lr_dome_ribs(rx, ry, 0.144, 0.12, 0.13, seam, 8, (0.0, 0.45, 0.9, 1.25, 1.45), 0.55, 0.014)
    cy(0.03, 0.02, (rx, ry, 0.28), plate, 8)
    rod((rx, ry, 0.29), (rx, ry, 0.36), 0.006, cap, r2=0.0015, n=4)
    bx((0.014, 0.014, 0.014), (rx, ry, 0.34), tip, bev=0)
    # a transfer tower at the right and tubes to it from the core block and the reactor
    tx, ty = 0.52, -0.04
    bx((0.08, 0.08, 0.26), (tx, ty, 0.13), st, bev=0)
    bx((0.09, 0.09, 0.012), (tx, ty, 0.266), plate, bev=0)
    bx((0.084, 0.004, 0.012), (tx, ty - 0.042, 0.2), neon, bev=0)
    tube_bridge((cx_ + W / 2, 0.1, 0.22), (tx - 0.04, ty + 0.02, 0.22), 0.022, mats, 4)
    tube_bridge((rx + 0.02, ry - 0.13, 0.08), (tx, ty + 0.04, 0.12), 0.018, mats, 2)
    # the robot bay at the front left: an open floor with a lit production line and robot arms
    bx_, by_ = -0.38, -0.27
    bx((0.36, 0.24, 0.02), (bx_, by_, 0.026), plate, bev=0)
    bx((0.36, 0.022, 0.13), (bx_, by_ + 0.12, 0.08), st, bev=0)
    bx((0.022, 0.24, 0.1), (bx_ - 0.18, by_, 0.066), st, bev=0)
    bx((0.364, 0.026, 0.01), (bx_, by_ + 0.12, 0.148), neon, bev=0)
    bx((0.3, 0.05, 0.016), (bx_ + 0.01, by_, 0.044), flat("belt", "#26292e", 0.8), bev=0)
    for sg in (-1, 1):
        bx((0.3, 0.006, 0.006), (bx_ + 0.01, by_ + sg * 0.028, 0.054), neon, bev=0)
    for k in range(5):
        bx((0.026, 0.026, 0.018), (bx_ - 0.11 + k * 0.06, by_, 0.061), flat("part8", "#d9dde2", 0.45), bev=0)
    for k, (u, sg) in enumerate(((-0.08, 1), (0.0, -1), (0.08, 1))):
        robot_arm(bx_ + u, by_ + sg * 0.062, -sg * math.pi / 2, 1.35)
    rim = _MB()
    for (p0, p1) in (((bx_ - 0.17, by_ - 0.115), (bx_ + 0.17, by_ - 0.115)), ((bx_ + 0.17, by_ - 0.115),
                                                                              (bx_ + 0.17, by_ + 0.1))):
        rim.strip((p0[0], p0[1], 0.0365), (p1[0], p1[1], 0.0365), (0, 0, 1), 0.014, 0.0)
    rim.obj(hazard(0.025), "bay_rim")
    tube_bridge((cx_ - W / 2, 0.1, 0.2), (bx_ - 0.05, by_ + 0.13, 0.13), 0.02, mats, 2)
    # the landing pad with a cargo drone, tanks, masts
    ev.d8_pad(0.32, -0.36, 0.16, 0.05, mats)
    cargo_drone(0.32, -0.36, 0.052, 0.3, mats)
    for (x, y, r, h) in ((0.6, 0.12, 0.05, 0.16), (0.56, 0.26, 0.042, 0.13)):
        cy(r, h, (x, y, h / 2), seam, 10)
        lr_ring(x, y, r + 0.004, h * 0.62, 0.012, neon, 10)
        lr_ring(x, y, r + 0.004, 0.03, 0.014, plate, 10)
        hemi(r, (x, y, h), seam, 10, 2, (1, 1, 0.5))
    # a vaulted processing hall at the back left, its lit doors facing the camera
    ev.d8_hangar(-0.47, 0.22, 0.26, 0.2, 0.1, mats, math.pi / 2)
    # containers by the pad, bronze pipes from the reactor to the core block on low supports
    ev.d8_containers(0.13, -0.5, 0.0, "#c26a2c", mats)
    for k, z in enumerate((0.045, 0.075)):
        rod((rx - 0.13, ry - 0.06 + k * 0.03, z), (cx_ + W / 2, ry - 0.06 + k * 0.03, z), 0.012, bronze, n=6)
    for x in (0.18, 0.24):
        bx((0.012, 0.05, 0.06), (x, ry - 0.045, 0.03), plate, bev=0)
    for (x, y) in ((-0.14, -0.5), (0.16, -0.14), (-0.62, -0.06), (0.1, 0.52)):
        ev.lr_mast(x, y, 0.13, mats, 0.016)


# ------------------------------------------------------------------ oil fields: shared parts


def oil_pool(pts, z=0.014):
    """A pool of black crude (glossy, its own material) lying just above the ground pad."""
    return extrude(pts, -0.004, z, oil_mat())


def plank_kerb(pts, wood, t=0.026, h=0.022, posts=None):
    """A timber kerb round a polygon (closed): a squared log along each edge, posts at the corners."""
    n = len(pts)
    for k in range(n):
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % n]
        beam((x0, y0, h / 2), (x1, y1, h / 2), t, wood)
        if posts:
            bx((t * 1.15, t * 1.15, h + 0.016), (x0, y0, (h + 0.016) / 2), posts, bev=0)


def lattice_tower(x, y, b0, b1, z0, z1, levels, leg, girt, brace, mt_leg, mt_girt=None, faces=(0, 1, 2, 3),
                  zigzag=False):
    """A four-legged tapered lattice tower (a derrick): legs from the half-width b0 at z0 to b1 at z1, horizontal
    girts at the given level fractions, diagonal braces on the chosen faces (0 front −Y, 1 right, 2 back, 3 left):
    crossed in each bay, or one zigzag diagonal per bay."""
    mt_girt = mt_girt or mt_leg
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]

    def P(c, f):
        bb = b0 + (b1 - b0) * f
        return (x + corners[c][0] * bb, y + corners[c][1] * bb, z0 + (z1 - z0) * f)
    for c in range(4):
        beam(P(c, 0.0), P(c, 1.0), leg, mt_leg)
    lv = [0.0] + list(levels) + [1.0]
    for f in levels:
        for c in range(4):
            beam(P(c, f), P((c + 1) % 4, f), girt, mt_girt)
    for fc in faces:
        a, b = fc, (fc + 1) % 4
        for i in range(len(lv) - 1):
            f0, f1 = lv[i], lv[i + 1]
            if zigzag:
                if i % 2:
                    beam(P(a, f0), P(b, f1), brace, mt_girt)
                else:
                    beam(P(b, f0), P(a, f1), brace, mt_girt)
            else:
                beam(P(a, f0), P(b, f1), brace, mt_girt)
                beam(P(b, f0), P(a, f1), brace, mt_girt)
    return P


def pumpjack(x, y, rz, s=1.0, frame="#6e4526", beam_c="#7a4f2c", head="#2e3034", weight="#3d3f45", base=None,
             wellhead="#55575e", nod=0.12, wood=True):
    """A nodding-donkey pumpjack (turned rz; the horsehead at local +X over the well): a skid, an A-frame Samson post,
    the walking beam (nodded down by `nod`) with a curved horsehead, the crank discs with their counterweights at
    the back, the pitman arms, a gearbox, the polished rod down into a wellhead."""
    def b():
        fm = tex("wood", frame, 3.0) if wood else flat("pj_frame" + frame, frame, 0.5)
        bm = tex("wood", beam_c, 3.0) if wood else flat("pj_beam" + beam_c, beam_c, 0.45)
        hm = flat("pj_head" + head, head, 0.5)
        wm = flat("pj_weight" + weight, weight, 0.5)
        bx((0.26, 0.05, 0.016), (0.0, 0, 0.008), base or fm, bev=0)  # the skid
        pz = 0.16
        for sy in (-1, 1):  # the Samson post
            beam((-0.03, sy * 0.03, 0.012), (0.0, sy * 0.008, pz), 0.012, fm)
            beam((0.05, sy * 0.03, 0.012), (0.0, sy * 0.008, pz), 0.012, fm)
        L0, L1 = 0.1, 0.11
        ca, sa = math.cos(nod), math.sin(nod)
        p_back = (-L0 * ca, 0, pz + L0 * sa)
        p_front = (L1 * ca, 0, pz - L1 * sa)
        beam(p_back, p_front, 0.018, bm)
        ico(0.01, (0, 0, pz), hm)
        # the horsehead: a curved plate at the front end, built as a thick fan
        hx, _, hz = p_front
        pts = []
        for k in range(5):
            a = -0.9 + k * 0.45 - nod
            pts.append((hx + 0.008 + 0.05 * math.cos(a) * 0.55, hz + 0.055 * math.sin(a)))
        prof = [(hx - 0.004, hz - 0.036)] + pts + [(hx - 0.004, hz + 0.036)]  # bottom-left, the arc up, top-left
        extrude(prof, -0.012, 0.012, hm, rot=(math.pi / 2, 0, 0))
        rx = hx + 0.035
        beam((rx, 0, hz - 0.045), (rx, 0, 0.05), 0.004, flat("rod_pol", "#c9ccd0", 0.3))
        cy(0.012, 0.04, (rx, 0, 0.02), flat("wh" + wellhead, wellhead, 0.5), 8)
        bx((0.034, 0.01, 0.01), (rx, 0, 0.034), flat("wh" + wellhead, wellhead, 0.5), bev=0)
        # the crank at the back: gearbox, two crank discs with counterweights, pitman arms up to the beam's tail
        bx((0.04, 0.034, 0.036), (-0.09, 0, 0.034), flat("gearbox", "#4a4d52", 0.5), bev=0)
        for sy in (-1, 1):
            cy(0.03, 0.008, (-0.09, sy * 0.024, 0.05), wm, 10, rot=(math.pi / 2, 0, 0))
            bx((0.03, 0.01, 0.024), (-0.108, sy * 0.026, 0.038), wm, bev=0, rot=(0, 0.5, 0))
            beam((-0.07, sy * 0.026, 0.06), (p_back[0], sy * 0.012, p_back[2]), 0.006, hm)
    build_at(b, x, y, rz, s=s)


def derrick_l1(x, y, top=0.94):
    """The timber derrick of a cable-tool well (frames 3–4's timber headframes): a plank rig floor, four raked
    legs, girts and crossed braces, a crown platform with a sheave wheel, a monkey board, a ladder, the drill line."""
    timber = tex("wood", "#6e4526")
    light = tex("wood", "#8a5a33", 1.5)
    plank = tex("wood", WOOD_L, 2.0)
    bx((0.38, 0.38, 0.03), (x, y, 0.015), plank, bev=0)
    for sx in (-1, 1):
        bx((0.04, 0.4, 0.034), (x + sx * 0.17, y, 0.017), timber, bev=0)  # sills
    P = lattice_tower(x, y, 0.15, 0.04, 0.03, top, (0.22, 0.43, 0.63, 0.82), 0.024, 0.014, 0.01, timber, light,
                      faces=(0, 1, 2, 3))
    bx((0.12, 0.12, 0.016), (x, y, top + 0.008), plank, bev=0)
    for sx in (-1, 1):
        bx((0.014, 0.014, 0.05), (x + sx * 0.026, y, top + 0.04), timber, bev=0)
    cy(0.036, 0.014, (x, y, top + 0.052), tex("wood", "#5e3d24", 2.0), 12, rot=(0, math.pi / 2, 0))
    cy(0.026, 0.016, (x, y, top + 0.052), flat("iron", IRON, 0.5), 10, rot=(0, math.pi / 2, 0))
    rope = flat("rope", "#d8c8a0", 0.9)
    beam((x, y - 0.03, top + 0.05), (x, y - 0.03, 0.06), 0.004, rope)
    bx((0.012, 0.012, 0.08), (x, y - 0.03, 0.1), flat("iron", IRON, 0.5), bev=0)  # the drill bit on the line
    # the monkey board on the front at two thirds, its rail
    f = 0.63
    zb = 0.03 + (top - 0.03) * f
    hb = 0.15 + (0.04 - 0.15) * f
    bx((0.12, 0.06, 0.01), (x, y - hb - 0.03, zb), plank, bev=0)
    beam((x - 0.06, y - hb - 0.06, zb + 0.035), (x + 0.06, y - hb - 0.06, zb + 0.035), 0.008, timber)
    # a ladder up the front-left leg
    for k in range(7):
        ff = 0.06 + k * 0.08
        a, b = P(0, ff), P(1, ff)
        u = 0.18
        beam((a[0] + (b[0] - a[0]) * u, a[1] - 0.01, a[2]), (a[0] + (b[0] - a[0]) * (u + 0.12), a[1] - 0.01, a[2]),
             0.006, light)
    a0, a1 = P(0, 0.0), P(0, 0.62)
    b0, b1 = P(1, 0.0), P(1, 0.62)
    for u in (0.18, 0.3):
        beam((a0[0] + (b0[0] - a0[0]) * u, a0[1] - 0.012, a0[2]), (a1[0] + (b1[0] - a1[0]) * u, a1[1] - 0.012, a1[2]),
             0.008, timber)
    return top + 0.09


def oil_l1():
    """Wooden derrick and pumpjack (DL ≤ 5; the timber headframes and lived-in yards of frames 3–4): on trampled
    earth with dark oil stains, a tall timber lattice derrick with a sheave on its crown, a monkey board, a ladder,
    the drill line and a band wheel; a timber pumpjack nodding over its well; a black pond of crude in a squared-log
    kerb with a plank jetty and a trough from the derrick; a plank engine shed with a shingle roof, a lit window and
    a smoking iron flue; a staved storage vat with iron hoops; barrels stacked and standing, a barrel cart, a
    lantern on a post."""
    pad(0.7, tex("plaster", "#8d7354", 3.0), 0.012, 16, 0.07, 21, 1.0, 0.95)
    stain = tex("plaster", "#4a3a2c", 4.0)
    ground_strip([(-0.3, -0.04), (0.08, -0.08), (0.14, 0.12), (0.06, 0.34), (-0.26, 0.32), (-0.32, 0.1)], stain,
                 0.006, 0.0135)
    timber = tex("wood", "#6e4526")
    wood_l = tex("wood", WOOD_L, 2.0)
    dx, dy = -0.08, 0.14
    derrick_l1(dx, dy, 0.93)
    # the band wheel and its belt to the engine shed
    cy(0.065, 0.016, (dx + 0.22, dy - 0.05, 0.08), tex("wood", "#5e3d24", 2.0), 14, rot=(math.pi / 2, 0, 0))
    cy(0.012, 0.03, (dx + 0.22, dy - 0.05, 0.08), flat("iron", IRON, 0.5), 8, rot=(math.pi / 2, 0, 0))
    for sy in (-1, 1):
        bx((0.016, 0.016, 0.08), (dx + 0.22, dy - 0.05 + sy * 0.02, 0.04), timber, bev=0)
    beam((dx + 0.22, dy - 0.056, 0.14), (0.3, 0.27, 0.07), 0.006, flat("belt_l", "#3a2a20", 0.8))
    # the engine shed with a smoking flue
    sx_, sy_ = 0.32, 0.34
    bx((0.2, 0.14, 0.11), (sx_, sy_, 0.055), tex("wood", "#a07a52", 2.0), bev=0)
    for u in (-0.1, 0.1):
        for v in (-0.07, 0.07):
            bx((0.016, 0.016, 0.11), (sx_ + u, sy_ + v, 0.055), timber, bev=0)
    gable_roof(0.2, 0.14, 0.07, (sx_, sy_, 0.11), SLATE_N, tex("wood", "#a07a52", 2.0), n=4, **ev.SOFT_ROOF)
    window(sx_ - 0.04, sy_ - 0.072, 0.065, 0.0, 0.03, 0.04, lit=True, frame="#5a3a22", arch=False)
    bx((0.04, 0.008, 0.08), (sx_ + 0.05, sy_ - 0.072, 0.04), tex("wood", WOOD_D, 3.0), bev=0)
    fx, fy = sx_ + 0.06, sy_ + 0.02
    cy(0.013, 0.24, (fx, fy, 0.2), flat("iron", IRON, 0.5), 8)
    cy(0.02, 0.012, (fx, fy, 0.32), flat("iron", IRON, 0.5), 8)
    smoke_at(fx, fy, 0.33)
    # the pumpjack over its well at the front right
    pumpjack(0.28, -0.14, 0.0, 1.5)
    # the storage vat: staves and iron hoops under a shallow cone
    vx, vy = 0.5, 0.12
    cy(0.085, 0.13, (vx, vy, 0.065), tex("wood", "#7a5a3c", 3.0), 14)
    for z in (0.03, 0.075, 0.115):
        lr_ring(vx, vy, 0.088, z, 0.008, flat("iron", IRON, 0.5), 14)
    cn(0.095, 0.05, (vx, vy, 0.155), tex("roof", "#6f5a48", 1.6), 14)
    rod((vx - 0.03, vy - 0.08, 0.03), (0.44, -0.12, 0.03), 0.01, flat("iron", IRON, 0.5), n=6)  # its pipe from the jack
    # the pond of crude in a squared-log kerb, a plank jetty, a trough down from the derrick
    pond = [(-0.6, -0.22), (-0.55, -0.4), (-0.4, -0.54), (-0.2, -0.56), (-0.06, -0.46), (-0.04, -0.3),
            (-0.12, -0.16), (-0.3, -0.1), (-0.5, -0.1)]
    ground_strip([(x * 1.1 + 0.03, y * 1.1 + 0.03) for x, y in pond], stain, 0.006, 0.0135)
    oil_pool(pond)
    plank_kerb(pond, timber, posts=tex("wood", "#4e3420", 2.0))
    bx((0.2, 0.05, 0.012), (-0.22, -0.34, 0.026), wood_l, 0.5, bev=0)  # the jetty
    for (u, v) in ((-0.3, -0.38), (-0.15, -0.3)):
        bx((0.014, 0.014, 0.04), (u, v, 0.012), timber, bev=0)
    barrel(-0.17, -0.31, 0.032, c="#4a3020")
    # the trough on trestles from the rig floor to the pond
    beam((dx - 0.05, dy - 0.2, 0.05), (-0.2, -0.13, 0.035), 0.03, tex("wood", "#5e3d24", 2.0))
    beam((dx - 0.05, dy - 0.2, 0.06), (-0.2, -0.13, 0.045), 0.016, oil_mat())
    for f in (0.3, 0.7):
        px, py = dx - 0.05 + (-0.2 - dx + 0.05) * f, dy - 0.2 + (-0.13 - dy + 0.2) * f
        bx((0.012, 0.04, 0.04), (px, py, 0.02), timber, bev=0)
    # a stack of casing pipe on timber sleepers
    for u in (-0.08, 0.08):
        bx((0.02, 0.1, 0.014), (0.16 + u, -0.4, 0.007), timber, bev=0)
    for k, (v, z) in enumerate(((-0.03, 0.0), (0.0, 0.0), (0.03, 0.0), (-0.015, 0.026), (0.015, 0.026))):
        rod((0.04, -0.4 + v, 0.027 + z), (0.28, -0.4 + v, 0.027 + z), 0.013, flat("casing", "#4a4d52", 0.45), n=6)
    # barrels: a stack lying by the shed, some standing (oil-stained), a barrel cart, a lantern
    for (u, v, z) in ((0.12, 0.42, 0.0), (0.17, 0.42, 0.0), (0.22, 0.42, 0.0), (0.145, 0.42, 0.04),
                      (0.195, 0.42, 0.04)):
        barrel(u, v, z, lie=0.0, c="#6a4a2c")
    for (u, v, c) in ((0.5, -0.3, "#4a3020"), (0.54, -0.35, "#6a4a2c"), (0.48, -0.37, "#4a3020")):
        barrel(u, v, c=c)

    def cart():
        wd = tex("wood", "#8a5e36", 2.5)
        bx((0.13, 0.085, 0.014), (0.0, 0, 0.055), wd, bev=0)
        for sy in (-1, 1):
            bx((0.13, 0.008, 0.03), (0.0, sy * 0.043, 0.075), wd, bev=0)
            cy(0.034, 0.01, (0.0, sy * 0.052, 0.034), tex("wood", WOOD_D, 2.0), 8, rot=(math.pi / 2, 0, 0))
            beam((-0.06, sy * 0.03, 0.05), (-0.17, sy * 0.034, 0.008), 0.01, tex("wood", WOOD_D, 2.0))
        for u in (-0.03, 0.03):
            barrel(u, 0.0, 0.062, r=0.02, h=0.046, c="#4a3020")
    build_at(cart, 0.32, -0.52, 0.5)
    lantern_post(0.16, -0.02, 0.22, timber)


def steel_tank(x, y, r, h, c="#e6e3dc", band=None, stair=True, roof="cone", n=16, rail=True):
    """A welded steel storage tank: a pale shell with weld rings, a dark foot, a shallow cone (or dome) roof with a
    handrail, a stair climbing round it (frame of steps in steel), a coloured band."""
    sh = flat("tank" + c, c, 0.45)
    cy(r + 0.012, 0.014, (x, y, 0.007), flat("tank_foot", "#77736b", 0.8), n)
    cy(r, h, (x, y, h / 2), sh, n)
    for z in (h * 0.34, h * 0.67):
        lr_ring(x, y, r + 0.002, z, 0.006, flat("weld" + c, shade(c, 0.86), 0.5), n)
    if band:
        lr_ring(x, y, r + 0.003, h * 0.82, 0.03, flat("tband" + band, band, 0.5), n)
    if roof == "cone":
        cn(r + 0.006, r * 0.22, (x, y, h + r * 0.11), sh, n)
    else:
        hemi(r + 0.004, (x, y, h), sh, n, 3, (1, 1, 0.35))
    if rail:
        lr_ring(x, y, r - 0.004, h + 0.022, 0.006, flat("rail_y", SAFETY, 0.5), n)
    if stair:
        st = flat("stair", "#4a4f57", 0.5)
        k = 7
        for i in range(k):
            a = -math.pi / 2 - 0.3 + i * 0.16
            z = (i + 0.5) / k * h
            bx((0.03, 0.016, 0.006), (x + math.cos(a) * (r + 0.01), y + math.sin(a) * (r + 0.01), z), st, a + math.pi / 2,
               bev=0)
        a0, a1 = -math.pi / 2 - 0.3, -math.pi / 2 - 0.3 + (k - 1) * 0.16
        pts = [(x + math.cos(a0 + (a1 - a0) * t) * (r + 0.024), y + math.sin(a0 + (a1 - a0) * t) * (r + 0.024),
                0.03 + t * h) for t in (0.0, 0.33, 0.66, 1.0)]
        for i in range(3):
            beam(pts[i], pts[i + 1], 0.005, flat("rail_y", SAFETY, 0.5))


def pump_house(x, y, rz=0.0, w=0.16, d=0.12, h=0.1, wall="#c9b9a0", roof="#5b6168", sign="#2f6db3"):
    """A small brick-and-render pump house: a flat roof with a parapet, a lit window, a steel door, a vent."""
    def b():
        bx((w, d, h), (0, 0, h / 2), tex("plaster", wall, 2.5), bev=0)
        bx((w + 0.01, d + 0.01, 0.03), (0, 0, 0.015), stone(BRICK, 1.6), bev=0)
        bx((w + 0.012, d + 0.012, 0.012), (0, 0, h + 0.006), flat("parapet", roof, 0.6), bev=0)
        bx((w - 0.01, d - 0.01, 0.004), (0, 0, h + 0.012), flat("roof_d", "#3d4148", 0.7), bev=0)
        bx((0.036, 0.006, 0.03), (-w * 0.22, -d / 2 - 0.002, h * 0.6), win_lit(), bev=0)
        bx((0.044, 0.008, 0.008), (-w * 0.22, -d / 2 - 0.004, h * 0.6 - 0.02), flat("sill" + CONC, "#e4e0d8", 0.7),
           bev=0)
        bx((0.036, 0.006, 0.07), (w * 0.22, -d / 2 - 0.002, 0.035), flat("door_s", "#4a5560", 0.5), bev=0)
        bx((0.05, 0.006, 0.014), (w * 0.22, -d / 2 - 0.003, 0.084), flat("sign" + sign, sign, 0.6), bev=0)
        cy(0.012, 0.04, (-w * 0.25, d * 0.2, h + 0.03), flat("vent", "#9aa0a6", 0.5), 8)
    build_at(b, x, y, rz)


def oil_l2():
    """Steel derrick (DL 6; the modern era beside port_modern / farm_modern): on a gravel pad with oil stains, a
    steel lattice derrick on a braced substructure with a red crown block, a racking board, the driller's doghouse,
    a catwalk down to a rack of drill pipe; two steel pumpjacks with amber horseheads and red counterweights; pipe
    runs on low supports with valve wheels to a white storage tank with a stair and a blue band; a pump house with a
    lit window; a concrete-lined slush pit of black oil; a tanker truck, drums on a pallet, lamps."""
    pad(0.72, tex("plaster", "#a8a296", 2.5), 0.012, 16, 0.04, 31, 1.0, 0.95)
    stain = tex("plaster", "#3f3a36", 4.0)
    steel = flat("derrick8", "#9aa1a9", 0.45)
    steel_d = flat("derrick_d", "#6b737d", 0.45)
    dx, dy = -0.2, 0.18
    ground_strip([(dx - 0.26, dy - 0.24), (dx + 0.2, dy - 0.28), (dx + 0.26, dy + 0.18), (dx - 0.2, dy + 0.24)], stain,
                 0.006, 0.0135)
    # the substructure and rig floor, the derrick, its crown
    bx((0.36, 0.36, 0.07), (dx, dy, 0.035), corrugated("#5c6570", 0.014, 0.8), bev=0)
    bx((0.4, 0.4, 0.014), (dx, dy, 0.077), flat("rigfloor", "#4a4f57", 0.6), bev=0)
    bx((0.404, 0.404, 0.008), (dx, dy, 0.07), hazard(0.03), bev=0)
    top = 0.95
    lattice_tower(dx, dy, 0.15, 0.035, 0.084, top, (0.17, 0.34, 0.5, 0.66, 0.82), 0.018, 0.01, 0.007, steel, steel_d)
    bx((0.11, 0.11, 0.036), (dx, dy, top + 0.018), flat("crown_r", "#d8342a", 0.5), bev=0)
    bx((0.13, 0.13, 0.008), (dx, dy, top + 0.002), flat("crown_w", "#f1eee8", 0.6), bev=0)
    rod((dx, dy, top + 0.036), (dx, dy, top + 0.08), 0.004, steel_d, n=4)
    bx((0.01, 0.01, 0.01), (dx, dy, top + 0.08), glow("beacon_r", "#ff4a3a", 4.0), bev=0)
    f = 0.66
    zb = 0.084 + (top - 0.084) * f
    hb = 0.15 + (0.035 - 0.15) * f
    bx((0.1, 0.05, 0.008), (dx, dy - hb - 0.025, zb), flat("rack_y", SAFETY, 0.5), bev=0)  # the racking board
    beam((dx, dy, top), (dx, dy, 0.12), 0.006, flat("cable", "#2b2d31", 0.6))
    bx((0.03, 0.03, 0.04), (dx, dy, 0.32), flat("block_y", SAFETY, 0.5), bev=0)  # the travelling block
    # the doghouse on the rig floor's side, the drawworks
    bx((0.12, 0.08, 0.08), (dx + 0.25, dy + 0.06, 0.12), flat("doghouse", "#e2782a", 0.5), bev=0)
    bx((0.05, 0.004, 0.026), (dx + 0.23, dy + 0.018, 0.13), win_lit(), bev=0)
    bx((0.13, 0.09, 0.008), (dx + 0.25, dy + 0.06, 0.164), flat("roof_d", "#3d4148", 0.7), bev=0)
    bx((0.07, 0.06, 0.04), (dx + 0.06, dy + 0.12, 0.104), flat("drawworks", "#2f6db3", 0.5), bev=0)
    # the diesel power unit behind the rig floor, its exhaust smoking
    bx((0.1, 0.07, 0.06), (dx + 0.27, dy + 0.19, 0.03), flat("engine", "#5c6570", 0.5), bev=0)
    bx((0.104, 0.074, 0.01), (dx + 0.27, dy + 0.19, 0.062), flat("engine_top", "#e2782a", 0.5), bev=0)
    cy(0.009, 0.1, (dx + 0.3, dy + 0.2, 0.11), flat("iron", IRON, 0.5), 6)
    smoke_at(dx + 0.3, dy + 0.2, 0.165)
    # the catwalk from the V-door down to the pipe rack in front
    ev.lr_slab((dx, dy - 0.2, 0.084), (dx + 0.02, dy - 0.48, 0.03), 0.07, 0.016, flat("catwalk", "#59606a", 0.6))
    for v in (-0.6, -0.44):
        bx((0.2, 0.016, 0.02), (dx + 0.02, dy + v + 0.0, 0.01), flat("pr_post", "#59606a", 0.6), bev=0)
    for k, (u, z) in enumerate(((-0.05, 0.0), (-0.025, 0.0), (0.0, 0.0), (0.025, 0.0), (0.05, 0.0), (-0.0375, 0.024),
                                (-0.0125, 0.024), (0.0125, 0.024), (0.0375, 0.024))):
        rod((dx + 0.02 + u, dy - 0.64, 0.032 + z), (dx + 0.02 + u, dy - 0.4, 0.032 + z), 0.012,
            flat("dpipe", "#6d7178" if k % 2 else "#4a4d52", 0.45), n=6)
    # two steel pumpjacks
    pj = dict(frame="#5c6570", beam_c="#3d4148", head="#e2a12a", weight="#c8382c", base=flat("skid", "#4a4f57", 0.6),
              wood=False)
    pumpjack(0.26, -0.3, 0.3, 1.45, **pj)
    pumpjack(0.48, 0.0, -0.3, 1.25, nod=-0.08, **pj)
    # the storage tank, pipe runs on low supports from the wellheads, valve wheels
    tx, ty = 0.32, 0.36
    steel_tank(tx, ty, 0.14, 0.2, band="#2f6db3")
    pipe = flat("pipe_g", "#7d858f", 0.4)
    wh1 = (0.26 + math.cos(0.3) * 0.2, -0.3 + math.sin(0.3) * 0.2)
    wh2 = (0.48 + math.cos(-0.3) * 0.17, math.sin(-0.3) * 0.17)
    run = [(wh1[0], wh1[1]), (0.58, -0.12), (0.6, 0.14), (tx + 0.1, ty - 0.1)]
    for i in range(len(run) - 1):
        rod((run[i][0], run[i][1], 0.03), (run[i + 1][0], run[i + 1][1], 0.03), 0.009, pipe, n=6)
        mx, my = (run[i][0] + run[i + 1][0]) / 2, (run[i][1] + run[i + 1][1]) / 2
        bx((0.014, 0.03, 0.026), (mx, my, 0.013), flat("pr_post", "#59606a", 0.6), bev=0)
    rod((wh2[0], wh2[1], 0.03), (0.6, wh2[1], 0.03), 0.009, pipe, n=6)
    for (vx, vy) in ((0.58, -0.12), (0.6, 0.14)):
        cy(0.016, 0.004, (vx, vy, 0.06), flat("valve_r", "#c8382c", 0.5), 8)
        rod((vx, vy, 0.03), (vx, vy, 0.058), 0.004, pipe, n=4)
    # the pump house and the slush pit of black oil in a concrete lining
    pump_house(0.06, 0.38, 0.0)
    pit = [(-0.58, -0.3), (-0.22, -0.3), (-0.22, -0.56), (-0.52, -0.56)]
    oil_pool([(-0.565, -0.315), (-0.235, -0.315), (-0.235, -0.545), (-0.505, -0.545)])
    plank_kerb(pit, flat("conc_lip", "#c9c3b6", 0.8), t=0.03, h=0.03)
    for (u, v) in ((-0.4, -0.3), (-0.3, -0.56)):
        bx((0.02, 0.02, 0.06), (u, v, 0.03), flat("rail_y", SAFETY, 0.5), bev=0)
    # a tanker truck, drums on a pallet, lamps
    truck(0.0, -0.16, 0.25, cab="#c9ccd0", box="#e6e3dc", tanker=True)
    bx((0.09, 0.07, 0.01), (0.46, -0.44, 0.017), tex("wood", WOOD_L, 4.0), bev=0)
    for k, (u, v) in enumerate(((-0.022, -0.016), (0.022, -0.016), (-0.022, 0.018), (0.022, 0.018))):
        cy(0.018, 0.05, (0.46 + u, -0.44 + v, 0.047), flat("drum" + ("#2f6db3" if k % 3 else "#c8382c"),
                                                            "#2f6db3" if k % 3 else "#c8382c", 0.45), 8)
    for (x, y) in ((-0.08, -0.4), (0.62, 0.22), (-0.56, 0.06)):
        ev.street_lamp(x, y, 0.2, modern=True)


FACTORIES = [factory_l1, factory_l2, factory_l3]
OILS = [oil_l1, oil_l2]
ASSETS = {f"factory_l{n + 1}": f for n, f in enumerate(FACTORIES)}
ASSETS.update({f"oil_l{n + 1}": f for n, f in enumerate(OILS)})
SIZE = {}  # bake size per model (the tight atlas at 512 by default, as the towers and the districts)


# ------------------------------------------------------------------ export


def export(name, out):
    """tower_assets.export (lowpoly, tight atlas, glTF, mesh origin at the model origin) that keeps the chimney
    markers: the "smoke"/"flag" empties are exported with the model as plain nodes (as evolution_assets.export)."""
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    marks = [o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.name.startswith(("smoke", "flag"))]
    bpy.context.view_layer.update()
    ev.lowpoly(objs)
    ev._drop_ground_faces(objs)
    ob = ev.bake_atlas(objs, SIZE.get(name, 512))
    ob.name = name
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.calc_loop_triangles()
    tris = len(ob.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    for o in marks:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    vs = [v.co for v in ob.data.vertices]
    rad = max(math.hypot(v.x, v.y) for v in vs)
    print(f"EXPORTED {name}: tris={tris} radius={rad:.3f} zmin={min(v.z for v in vs):.3f} "
          f"height={max(v.z for v in vs):.3f} smoke={len([m for m in marks if m.name.startswith('smoke')])} "
          f"mats={[m_.name for m_ in ob.data.materials]}", flush=True)
    return tris, rad


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0] if args else "game/assets/models"
    os.makedirs(out, exist_ok=True)
    only = set(args[1:])
    report = {}
    for name, build in ASSETS.items():
        if only and name not in only:
            continue
        ea.reset()
        build()
        report[name] = export(name, out)
    print("TRIS", {k: v[0] for k, v in report.items()})
