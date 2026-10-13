"""Key art for the splash/loading screen and store: the residence evolving DL1 → DL8 along a diagonal of
hex tiles (huts in front, neon citadel at the back), troops of matching eras beside them.

Run: python3 tools/blender/render_keyart.py OUT.png [width height samples]
Uses the exported models in game/assets/models (run evolution_assets.py / troops_assets.py first).
Then tools/ui/compose_keyart.py adds the title and refuses a render with black holes in the land.

The player's land is outlined the way the map draws a border (docs/art_direction.md §6.1 rule 1, §6.6): one flat
ribbon on the ground along the outline of the eight era hexes, corners rounded, a dark edge, the body and a light
stripe, no emission. It lies on the ground, so the models stand on it (the old floating neon rings crossed the
roofs as light-blue hairlines). The era models are lifted by a few millimetres each: the big DL1–DL3 bases overlap
their neighbours', and two coplanar bases rendered their overlap black in Cycles (the shadow rays of one hit the
other).
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kit import hex_prism, mat, noisy_mat  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/keyart.png"
W = int(sys.argv[2]) if len(sys.argv) > 2 else 941
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1672
SAMPLES = int(sys.argv[4]) if len(sys.argv) > 4 else 64
MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "models")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

grass = noisy_mat("grass", "#58b82a", "#8ad83f", 4.0)
grass_red = noisy_mat("grass_red", "#b5a43a", "#d4b24e", 4.0)
dirt = noisy_mat("dirt", "#8a5a34", "#a8743f", 6.0)
# the border ribbon's bands, outside → in (§6.6: dark edge 0–17 %, body, light stripe 30–52 %, body), the player's
# colours of game/scripts/soft_palette.gd (rim, body, hi)
RIBBON_BANDS = ((0.0, 0.17, "#1D4DB3"), (0.17, 0.30, "#4FA8FF"), (0.30, 0.52, "#B8E0FF"), (0.52, 1.0, "#4FA8FF"))
RIBBON_W = 0.15     # world units (≈ 0.16 at the strategic zoom, §6.6)
RIBBON_IN = 0.03    # the ribbon's outer edge this far inside the hex outline (the tiles' bevelled rims)
RIBBON_Z = 0.03     # over the tile tops (z 0) and the models' lifted bases (z ≤ 0.024): flat on the ground,
                    # under the walls and the troops that stand on it
SOFT_ROUNDS = 3     # Chaikin rounds: a corner cut to ≈ SOFT_R = 0.3 of the hex radius (§6.1 rule 2)
LIFT = 0.0015       # each era model this much over the previous one (no coplanar bases)


def hex_xy(q, r):
    return 1.5 * q, -math.sqrt(3) * (r + q / 2)


def place(name, x, y, rz=0.0, s=1.0, z=0.0):
    path = os.path.join(MODELS, name + ".glb")
    if not os.path.exists(path):
        return
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    for o in set(bpy.data.objects) - before:
        if o.parent is None:
            o.location = (x + o.location.x, y + o.location.y, z + o.location.z)
            o.rotation_euler = (o.rotation_euler.x, o.rotation_euler.y, o.rotation_euler.z + rz)
            o.scale = (s, s, s)


# tiles: a diagonal path of 8 era hexes from the front (bottom of frame) to the back, wild hexes around
path = [(-2, 3), (-1, 2), (-1, 1), (0, 0), (0, -1), (1, -2), (1, -3), (2, -4)]
era = {c: len(path) - i for i, c in enumerate(path)}  # huts nearest the camera, citadel at the back
for q in range(-5, 6):
    for r in range(-7, 7):
        x, y = hex_xy(q, r)
        if abs(x) > 6.5 or y < -5.5 or y > 9:
            continue
        enemy = q >= 2 and (q, r) not in era
        hex_prism(f"h{q}_{r}", (x, y, 0), 0.985, 0.95, grass_red if enemy else grass, dirt, bevel=0.035)


def outline(cells):
    """The outline of a set of hexes (axial coords) as one CCW loop of points: the edges with no neighbour in the
    set, chained end to start (flat-top hexes of radius 1; edge k runs from corner k to corner k + 1)."""
    centres = {(round(hex_xy(q, r)[0], 3), round(hex_xy(q, r)[1], 3)) for (q, r) in cells}
    nxt = {}
    for (q, r) in cells:
        cx, cy = hex_xy(q, r)
        for k in range(6):
            a = math.pi / 3 * k
            m = a + math.pi / 6
            nb = (round(cx + math.sqrt(3) * math.cos(m), 3), round(cy + math.sqrt(3) * math.sin(m), 3))
            if nb in centres:
                continue
            p0 = (round(cx + math.cos(a), 4), round(cy + math.sin(a), 4))
            p1 = (round(cx + math.cos(a + math.pi / 3), 4), round(cy + math.sin(a + math.pi / 3), 4))
            nxt[p0] = p1
    start = min(nxt)
    loop = [start]
    while nxt[loop[-1]] != start:
        loop.append(nxt[loop[-1]])
    return loop


def chaikin(pts, rounds):
    for _ in range(rounds):
        out = []
        for i, p in enumerate(pts):
            q = pts[(i + 1) % len(pts)]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        pts = out
    return pts


def inset(pts, d):
    """The CCW loop moved d inwards (to the left of its direction), mitred at the vertices."""
    out = []
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        normals = []
        for (p, q) in ((a, b), (b, c)):
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln = math.hypot(dx, dy) or 1.0
            normals.append((-dy / ln, dx / ln))
        nx, ny = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        ln = math.hypot(nx, ny) or 1.0
        nx, ny = nx / ln, ny / ln
        k = 1.0 / max(0.5, nx * normals[0][0] + ny * normals[0][1])  # the miter, clamped at sharp corners
        out.append((b[0] + nx * d * k, b[1] + ny * d * k))
    return out


def border_ribbon(cells):
    """The flat border ribbon along the outline of `cells`: one mesh, a material per band (RIBBON_BANDS)."""
    loop = chaikin(outline(cells), SOFT_ROUNDS)
    rings = sorted({b[0] for b in RIBBON_BANDS} | {b[1] for b in RIBBON_BANDS})
    lines = {t: inset(loop, RIBBON_IN + t * RIBBON_W) for t in rings}
    n = len(loop)
    verts, faces, mat_ix = [], [], []
    base = {}
    for t in rings:
        base[t] = len(verts)
        verts += [(x, y, RIBBON_Z) for (x, y) in lines[t]]
    for bi, (t0, t1, _col) in enumerate(RIBBON_BANDS):
        for i in range(n):
            j = (i + 1) % n
            faces.append((base[t0] + i, base[t0] + j, base[t1] + j, base[t1] + i))
            mat_ix.append(bi)
    me = bpy.data.meshes.new("border")
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new("border", me)
    bpy.context.collection.objects.link(o)
    for bi, (_t0, _t1, col) in enumerate(RIBBON_BANDS):
        o.data.materials.append(mat("ribbon_%d" % bi, col, 0.6))
    for f, mi in zip(o.data.polygons, mat_ix):
        f.material_index = mi
        f.use_smooth = False
    return o


border_ribbon(list(era))

for (q, r), dl in era.items():
    x, y = hex_xy(q, r)
    lift = LIFT * (len(path) + 1 - dl)  # the huts in front highest: their base lies over the next one's
    place(f"residence_dl{dl}_blue", x, y + 0.08, rz=0.25, s=1.45 if dl <= 3 else 1.15, z=lift)
    side = -1 if dl % 2 else 1
    if dl >= 2:
        place(f"assault_dl{dl}_blue", x + 0.95 * side, y - 0.55, rz=0.4 * side, s=1.3, z=lift)
    place(f"squad_dl{dl}_blue", x - 0.9 * side, y - 0.75, rz=-0.2 * side, s=1.2, z=lift)

# a red rival city at the back right for contrast
place("city_dl5_red", 4.2, -3.2, rz=0.3, s=1.2)
place("residence_dl6_red", 4.6, -5.0, rz=0.2)

# sea far below, sky
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.6))
bpy.context.active_object.data.materials.append(mat("sea", "#1b7fb8", 0.2))
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.55, 0.75, 1.0, 1)
bg.inputs["Strength"].default_value = 0.9

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 4.0
sun.angle = math.radians(8)
so = bpy.data.objects.new("sun", sun)
so.rotation_euler = (math.radians(48), math.radians(-20), math.radians(35))
scene.collection.objects.link(so)

cam = bpy.data.cameras.new("cam")
cam.lens = 38
co = bpy.data.objects.new("cam", cam)
scene.collection.objects.link(co)
scene.camera = co
co.location = (4.5, 12.5, 8.0)
target = bpy.data.objects.new("t", None)
target.location = (0.5, 0.4, 0.9)
scene.collection.objects.link(target)
tc = co.constraints.new("TRACK_TO")
tc.target = target
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"

scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.render.resolution_x = W
scene.render.resolution_y = H
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
scene.view_settings.look = "AgX - Punchy" if scene.view_settings.view_transform == "AgX" else "None"
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("keyart ->", OUT)
