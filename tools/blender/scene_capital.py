"""Visual target: the player's capital on a hex island, Clash-of-Clans-like.

Run: python3 tools/blender/scene_capital.py OUT.png [width height samples]
"""
import math
import random
import sys

import bpy

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import kit  # noqa: E402
from kit import axial_to_xy, box, cone, cyl, flag, hex_prism, house, mat, noisy_mat, palisade, pine, rock, sphere, tree  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/capital.png"
W = int(sys.argv[2]) if len(sys.argv) > 2 else 585
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1266
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 48

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
rnd = random.Random(7)

TILE_H = 0.35
GAP = 0.992

# ---------------------------------------------------------------- terrain

grass_player = noisy_mat("grass_p", "#5cbf2a", "#86d83c", 4.0)
grass_wild = noisy_mat("grass_w", "#6faa3a", "#93c252", 4.0)
grass_enemy = noisy_mat("grass_e", "#7aa63a", "#a5bf4e", 4.0)
dirt = noisy_mat("dirt", "#8a5a34", "#a8743f", 6.0)
sand = noisy_mat("sand", "#e5cf8f", "#f1dfa6", 5.0)
water = mat("water", "#2fa6d9", 0.15)

RADIUS = 6
player = {(q, r) for q in range(-2, 3) for r in range(-2, 3) if abs(q + r) <= 2}
enemy = {(q, r) for q in range(-6, 7) for r in range(-6, 7) if abs(q + r) <= 6 and r <= -3 and q >= 0 and (q, r) not in {(0, -3)}}
lake = {(-3, 3), (-4, 4), (-4, 3)}

cells = {}
for q in range(-RADIUS, RADIUS + 1):
    for r in range(-RADIUS, RADIUS + 1):
        if abs(q + r) > RADIUS:
            continue
        x, y = axial_to_xy(q, r)
        if (q, r) in lake:
            hex_prism("water", (x, y, -0.12), GAP, 0.3, water, sand)
            continue
        top = grass_player if (q, r) in player else grass_enemy if (q, r) in enemy else grass_wild
        h = TILE_H
        hex_prism(f"hex_{q}_{r}", (x, y, 0), GAP, h + 0.6, top, dirt, bevel=0.035)
        cells[(q, r)] = (x, y)

# sea plane far below for depth
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -0.75))
bpy.context.active_object.data.materials.append(mat("sea", "#1b7fb8", 0.2))


def at(q, r, dx=0.0, dy=0.0):
    x, y = cells[(q, r)]
    return (x + dx, y + dy, 0.0)


# ---------------------------------------------------------------- territory border (thick blue contour)

DIRS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
# corner pair facing each neighbour direction in world space (Y flipped vs screen)
def edge_pts(q, r, d, rad):
    """Endpoints of the edge of hex (q,r) facing neighbour direction d (world space)."""
    x, y = cells[(q, r)]
    nx, ny = axial_to_xy(q + DIRS[d][0], r + DIRS[d][1])
    pts = [(x + rad * math.cos(math.pi / 3 * k), y + rad * math.sin(math.pi / 3 * k)) for k in range(6)]
    pts.sort(key=lambda p: math.dist(p, (nx, ny)))
    return pts[0], pts[1]


border_mat = mat("border_blue", "#2e6bff", 0.35, emission="#3b7bff", emit_strength=1.2)
border_glow = mat("border_glow", "#9cc0ff", 0.4, emission="#9cc0ff", emit_strength=0.6)
enemy_border = mat("border_red", "#e0393e", 0.4, emission="#ff4a4a", emit_strength=0.8)


def ribbon(p0, p1, material, z=0.0, w=0.12, h=0.07):
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    ln = math.dist(p0, p1)
    o = box("ribbon", (ln + w * 0.6, w, h), (mx, my, z + h / 2), material, 0.02)
    o.rotation_euler.z = math.atan2(p1[1] - p0[1], p1[0] - p0[0])


for (q, r) in player:
    for d, (dq, dr) in enumerate(DIRS):
        if (q + dq, r + dr) in player:
            continue
        a, b = edge_pts(q, r, d, 0.86)
        ribbon(a, b, border_mat, w=0.16, h=0.08)
        # palisade sits just inside the border on the side facing outside
        a2, b2 = edge_pts(q, r, d, 0.7)
        if (q + dq, r + dr) in enemy or (dq, dr) in [(0, -1), (1, -1)]:
            palisade(a2, b2, 0.0)

for (q, r) in enemy:
    for d, (dq, dr) in enumerate(DIRS):
        n = (q + dq, r + dr)
        if n in enemy or n not in cells:
            continue
        a, b = edge_pts(q, r, d, 0.86)
        ribbon(a, b, enemy_border, w=0.13, h=0.07)

# ---------------------------------------------------------------- capital: town hall castle (0,0)

stone = noisy_mat("castle_stone", "#b8b3a8", "#d6d1c6", 7.0, 0.85)
stone_dark = mat("stone_dark", "#8e877c", 0.85)
roof_blue = mat("roof_blue", "#2f63d6", 0.45)
wood = mat("wood", "#8b5a2b", 0.8)
gold = mat("gold", "#ffc933", 0.3, 0.7)
x0, y0, _ = at(0, 0)
box("keep", (0.62, 0.62, 0.72), (x0, y0, 0.36), stone, 0.05)
for i in range(4):
    a = math.pi / 4 + i * math.pi / 2
    tx, ty = x0 + 0.42 * math.cos(a), y0 + 0.42 * math.sin(a)
    cyl("tower", 0.16, 0.95, (tx, ty, 0.475), stone, 16, 0.03)
    cone("tower_roof", 0.21, 0.42, (tx, ty, 1.16), roof_blue, 16, 0.02)
    sphere("tower_ball", 0.035, (tx, ty, 1.39), gold, (1, 1, 1), 2)
# crenellations
for i in range(8):
    a = i * math.pi / 4
    box("merlon", (0.09, 0.09, 0.09), (x0 + 0.27 * math.cos(a), y0 + 0.27 * math.sin(a), 0.77), stone, 0.015)
box("keep_top", (0.5, 0.5, 0.36), (x0, y0, 0.9), stone, 0.04)
kit.prism_roof("keep_roof", 0.5, 0.5, 0.36, (x0, y0, 1.08), roof_blue)
box("gate", (0.2, 0.03, 0.28), (x0, y0 - 0.315, 0.14), mat("gate", "#5b3a1e", 0.7), 0.03)
box("gate_arch", (0.26, 0.04, 0.05), (x0, y0 - 0.32, 0.3), stone_dark, 0.02)
flag((x0 + 0.05, y0 + 0.05, 1.3), "#2e6bff", 0.55)

# ---------------------------------------------------------------- gold mine (1,0)

mx, my, _ = at(1, 0)
rock_m = noisy_mat("mine_rock", "#8c7a63", "#a99476", 4.0)
sphere("mine_hill", 0.55, (mx, my + 0.1, 0.05), rock_m, (1.1, 0.9, 0.75), 2)
box("mine_frame_l", (0.06, 0.06, 0.4), (mx - 0.14, my - 0.36, 0.2), wood, 0.01)
box("mine_frame_r", (0.06, 0.06, 0.4), (mx + 0.14, my - 0.36, 0.2), wood, 0.01)
box("mine_frame_t", (0.38, 0.07, 0.07), (mx, my - 0.36, 0.42), wood, 0.01)
box("mine_hole", (0.24, 0.05, 0.3), (mx, my - 0.33, 0.15), mat("hole", "#1d150f", 1.0), 0.0)
for i in range(7):
    sphere("gold_nugget", 0.07, (mx + 0.28 + rnd.uniform(-0.1, 0.1), my - 0.3 + rnd.uniform(-0.08, 0.08), 0.06 + rnd.uniform(0, 0.08)), gold, (1, 1, 0.8), 1)
box("cart", (0.22, 0.14, 0.1), (mx - 0.35, my - 0.45, 0.1), wood, 0.02)
for dx in (-0.08, 0.08):
    cyl("wheel", 0.05, 0.03, (mx - 0.35 + dx, my - 0.53, 0.05), mat("iron", "#4a4a4a", 0.5, 0.5), 12, 0.0).rotation_euler.x = math.pi / 2
for i in range(5):
    sphere("cart_gold", 0.05, (mx - 0.35 + rnd.uniform(-0.07, 0.07), my - 0.45 + rnd.uniform(-0.04, 0.04), 0.17), gold, (1, 1, 1), 1)

# ---------------------------------------------------------------- farm + windmill (-1,1) and (-2,1)

fx, fy, _ = at(-1, 1)
field = mat("field", "#e8c34a", 0.8)
for i in range(4):
    box("crop_row", (0.95, 0.12, 0.08), (fx, fy - 0.3 + i * 0.2, 0.04), field, 0.03)
wx, wy, _ = at(-2, 1)
cyl("mill_body", 0.22, 0.7, (wx, wy, 0.35), mat("mill", "#f0e6d2", 0.8), 12, 0.03, r2=0.16)
cone("mill_roof", 0.24, 0.3, (wx, wy, 0.85), mat("mill_roof", "#c0392b", 0.5), 12)
hub = (wx, wy - 0.22, 0.62)
for i in range(4):
    blade = box("blade", (0.06, 0.02, 0.5), (hub[0], hub[1], hub[2]), mat("sail", "#fbf6ea", 0.8), 0.01)
    blade.rotation_euler.y = i * math.pi / 2 + 0.3
    blade.location = (hub[0] + 0.25 * math.sin(i * math.pi / 2 + 0.3), hub[1], hub[2] + 0.25 * math.cos(i * math.pi / 2 + 0.3))

# ---------------------------------------------------------------- houses

for (q, r, dx, dy, rot, roof) in [
    (0, 1, -0.25, 0.2, 0.2, "#d64a3a"),
    (0, 1, 0.3, -0.2, -0.3, "#e0703a"),
    (-1, 0, 0.0, 0.1, 0.5, "#d64a3a"),
    (1, -1, -0.2, 0.15, -0.2, "#c9462f"),
    (1, -1, 0.3, -0.25, 0.4, "#e0703a"),
    (-1, 2, 0.0, 0.0, 0.1, "#d64a3a"),
    (2, -1, 0.0, 0.0, -0.4, "#c9462f"),
]:
    house(at(q, r, dx, dy), rot, roof=roof)

# ---------------------------------------------------------------- barracks + soldiers (0,-1)

bx, by, _ = at(-1, -1)
box("barracks", (0.75, 0.45, 0.32), (bx, by + 0.15, 0.16), mat("barracks_wall", "#a26b3c", 0.8), 0.03)
kit.prism_roof("barracks_roof", 0.75, 0.45, 0.28, (bx, by + 0.15, 0.32), mat("roof_green", "#3c8d2f", 0.5))
flag((bx + 0.33, by + 0.3, 0.3), "#2e6bff", 0.5)
skin = mat("skin", "#f2c29a", 0.7)
tunic = mat("tunic", "#2e6bff", 0.6)
helm = mat("helm", "#c9ced6", 0.3, 0.6)


def soldier(x, y, s=1.0, spear=True):
    cyl("legs", 0.045 * s, 0.12 * s, (x, y, 0.06 * s), mat("pants", "#4a3527", 0.8), 10, 0.01)
    cyl("body", 0.07 * s, 0.16 * s, (x, y, 0.19 * s), tunic, 12, 0.03)
    sphere("head", 0.065 * s, (x, y, 0.33 * s), skin, (1, 1, 1), 2)
    sphere("helmet", 0.07 * s, (x, y, 0.36 * s), helm, (1, 1, 0.6), 2)
    if spear:
        cyl("spear", 0.01 * s, 0.5 * s, (x + 0.08 * s, y, 0.25 * s), wood, 6, 0.0)
        cone("spear_tip", 0.025 * s, 0.07 * s, (x + 0.08 * s, y, 0.53 * s), helm, 6, 0.0)


for i in range(3):
    for j in range(2):
        soldier(bx - 0.25 + i * 0.22, by - 0.25 - j * 0.18)

# builder with hammer near a construction site (1,1)
cx, cy, _ = at(1, 1)
box("site_floor", (0.6, 0.5, 0.06), (cx, cy, 0.03), mat("planks", "#c08a50", 0.8), 0.02)
for dx, dy in [(-0.25, -0.2), (0.25, -0.2), (-0.25, 0.2), (0.25, 0.2)]:
    box("scaffold", (0.05, 0.05, 0.5), (cx + dx, cy + dy, 0.25), wood, 0.01)
box("scaffold_top", (0.6, 0.05, 0.05), (cx, cy - 0.2, 0.48), wood, 0.01)
cyl("b_body", 0.075, 0.17, (cx + 0.05, cy - 0.38, 0.2), mat("overall", "#3a6fd8", 0.6), 12, 0.03)
sphere("b_head", 0.07, (cx + 0.05, cy - 0.38, 0.35), skin, (1, 1, 1), 2)
sphere("b_hat", 0.075, (cx + 0.05, cy - 0.38, 0.39), mat("hardhat", "#ffcc00", 0.4), (1, 1, 0.55), 2)

# watchtower near the enemy front (1,-2)
tx, ty, _ = at(1, -2)
for dx, dy in [(-0.12, -0.12), (0.12, -0.12), (-0.12, 0.12), (0.12, 0.12)]:
    box("tower_leg", (0.05, 0.05, 0.7), (tx + dx, ty + dy, 0.35), wood, 0.01)
box("tower_deck", (0.38, 0.38, 0.06), (tx, ty, 0.72), wood, 0.02)
cone("tower_cap", 0.3, 0.25, (tx, ty, 0.95), mat("roof", "#d64a3a", 0.5), 4)
soldier(tx, ty, 0.8, spear=False)
bpy.data.objects[-1].location.z += 0.0

# ---------------------------------------------------------------- wild lands: trees, rocks, a gold deposit with yellow outline

for (q, r), (x, y) in cells.items():
    if (q, r) in player or (q, r) in enemy:
        continue
    for i in range(rnd.randint(1, 3)):
        p = (x + rnd.uniform(-0.45, 0.45), y + rnd.uniform(-0.45, 0.45), 0.0)
        if rnd.random() < 0.55:
            pine(p, rnd.uniform(0.8, 1.1))
        else:
            tree(p, rnd.uniform(0.8, 1.1), rnd.randint(0, 99))
    if rnd.random() < 0.4:
        rock((x + rnd.uniform(-0.4, 0.4), y + rnd.uniform(-0.4, 0.4), 0.02), rnd.uniform(0.7, 1.2))

# deposit on wild hex (-3, 0): pile of gold ore + glowing yellow hex outline
dq = (-3, 0)
if dq in cells:
    gx, gy = cells[dq]
    for i in range(10):
        sphere("ore", 0.08, (gx + rnd.uniform(-0.18, 0.18), gy + rnd.uniform(-0.18, 0.18), 0.05 + rnd.uniform(0, 0.1)), gold, (1, 1, 0.8), 1)
    yellow = mat("deposit_outline", "#ffd21f", 0.3, emission="#ffd21f", emit_strength=3.0)
    for k in range(6):
        a = (gx + 0.85 * math.cos(-math.pi / 3 * k), gy + 0.85 * math.sin(-math.pi / 3 * k))
        b = (gx + 0.85 * math.cos(-math.pi / 3 * (k + 1)), gy + 0.85 * math.sin(-math.pi / 3 * (k + 1)))
        ribbon(a, b, yellow, z=0.01, w=0.06, h=0.03)

# enemy lands: red banners and a few red-roofed huts, a red army
for (q, r) in sorted(enemy):
    x, y = cells[(q, r)]
    if rnd.random() < 0.5:
        house((x + 0.1, y, 0), rnd.uniform(-0.5, 0.5), wall="#d9c8a8", roof="#8e2f2a")
    else:
        pine((x - 0.2, y + 0.2, 0), 1.0)
    if rnd.random() < 0.6:
        flag((x - 0.3, y - 0.3, 0), "#e0393e", 0.55)

# ---------------------------------------------------------------- lighting, camera, render

world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (*kit.srgb("#9fd3ff"), 1)
bg.inputs["Strength"].default_value = 0.9

bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 4.2
sun.data.angle = math.radians(6)
sun.data.color = (1.0, 0.95, 0.85)
sun.rotation_euler = (math.radians(40), math.radians(-20), math.radians(-35))

cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 13.5
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
# CoC-like view: looking north, ~38° below horizon
el = math.radians(52)
dist = 30
cam.location = (0.0, -dist * math.sin(el) + 1.2, dist * math.cos(el))
cam.rotation_euler = (el, 0, 0)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = W
scene.render.resolution_y = H
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Punchy"
except TypeError:
    pass
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("rendered", OUT)
