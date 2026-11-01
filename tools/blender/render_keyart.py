"""Key art for the splash/loading screen and store: the residence evolving DL1 → DL8 along a diagonal of
hex tiles (huts in front, neon citadel at the back), troops of matching eras beside them.

Run: python3 tools/blender/render_keyart.py OUT.png [width height samples] [--frame=portrait|feature]
  portrait (default, 941×1672 at 64 samples — the B4.6 settings): docs/store/keyart_portrait.png and the splash
  (compose_keyart.py --edge-fade=080F29 for game/assets/splash/splash.png);
  feature: the same scene seen across the path for the Play feature graphic (render 2048×1000 at 48 samples;
  compose_keyart.py --layout=feature scales it to 1024×500 with the title centred over the sky and sea).
Uses the exported models in game/assets/models (run evolution_assets.py / troops_assets.py first).
Then tools/ui/compose_keyart.py adds the title and refuses a render with black holes in the land.

The player's land is outlined the way the map draws a border (docs/art_direction.md §6.1 rule 1, §6.6): one flat
ribbon on the ground along the outline of the eight era hexes, corners rounded, a dark edge, the body and a light
stripe, no emission. It lies on the ground, so the models stand on it (the old floating neon rings crossed the
roofs as light-blue hairlines). The era models are lifted by a few millimetres each: the big DL1–DL3 bases overlap
their neighbours', and two coplanar bases rendered their overlap black in Cycles (the shadow rays of one hit the
other).

The banners carry the realm's flag, as on the map (Q6): a model's banner cloth is a team-blue box with a blank white
emblem box, and an empty "flagt…"/"flagw…" marks it (evolution_assets.flag_at); the game paints the state's flag
(flag_view.gd) on a quad over each face of the marker (map_view._flag_cloth). paint_flags() does the same here with
the player's default flag (FlagView.DEFAULT: a solid #1F4FBF field, the white eagle, the gold edge), so no banner
shows the blank grey square. place() parents a model's roots under one transform, so the markers move, turn and
scale with the mesh. render_icon.py imports these helpers.
"""
import math
import os
import sys
import tempfile

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
from kit import hex_prism, mat, noisy_mat  # noqa: E402

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "models")

# FlagView.DEFAULT (game/scripts/flag_view.gd): the field FIELD[0], the emblem colour FIELD[13], the plain gold edge
FLAG_FIELD, FLAG_EMBLEM, FLAG_EDGE = (0x1F, 0x4F, 0xBF), (0xF2, 0xF2, 0xF0), ((0xD9, 0xB4, 0x5A), (0x8A, 0x6A, 0x2A))
FLAG_PX = {False: (130, 208), True: (208, 136)}  # map_view._flag_material: a tall banner / a wide flag on a pole
FLAG_SS = 4  # the texture is drawn this many times larger (it is seen bigger than on the map)
_FLAG_MATS = {}


def flag_texture(wide, path):
    """The default flag as flag_view.gd draws it (_shape, draw_emblem "eagle", the frame polylines), RGBA."""
    from PIL import Image, ImageDraw
    w, h = (v * FLAG_SS for v in FLAG_PX[wide])
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    shape = [(w * .08, 0), (w * .92, 0), (w * .92, h * .8), (w * .5, h * .98), (w * .08, h * .8)]
    d.polygon(shape, fill=FLAG_FIELD + (255,))
    cx, cy, s = w * .5, h * .42, min(w, h) * .3
    eagle = [(0, -.5), (.15, -.1), (1.0, -.55), (.7, .05), (.25, .2), (.12, .8), (-.12, .8), (-.25, .2), (-.7, .05),
             (-1.0, -.55), (-.15, -.1)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in eagle], fill=FLAG_EMBLEM + (255,))
    ring = shape + [shape[0]]
    d.line(ring, fill=FLAG_EDGE[0] + (255,), width=int(round(max(2.0, w * 0.05))), joint="curve")
    d.line(ring, fill=FLAG_EDGE[1] + (255,), width=int(round(max(1.0, w * 0.015))), joint="curve")
    im.save(path)
    return path


def flag_material(wide):
    """A lit cloth with the flag texture and its alpha (cut out like the game's alpha scissor), roughness 0.75."""
    if wide in _FLAG_MATS:
        return _FLAG_MATS[wide]
    path = flag_texture(wide, os.path.join(tempfile.mkdtemp(prefix="raivon_flag_"), "flag_%s.png" % ("w" if wide else "t")))
    m = bpy.data.materials.new("flag_" + ("w" if wide else "t"))
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.interpolation = "Cubic"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    cut = nt.nodes.new("ShaderNodeMath")  # alpha scissor at 0.5, as the game's material
    cut.operation = "GREATER_THAN"
    cut.inputs[1].default_value = 0.5
    nt.links.new(tex.outputs["Alpha"], cut.inputs[0])
    nt.links.new(cut.outputs[0], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 0.75
    _FLAG_MATS[wide] = m
    return m


def paint_flags(markers):
    """A quad on each face of every flag marker (an empty scaled to the cloth: x width, y thickness, z height),
    textured with the flag — map_view._flag_cloth: the front faces −Y, the back is the front turned 180° about the
    up axis (it reads the right way round from behind too)."""
    for at in markers:
        me = bpy.data.meshes.new("flagcloth")
        verts = [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5),
                 (.5, .5, -.5), (-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5)]
        me.from_pydata(verts, [], [(0, 1, 2, 3), (4, 5, 6, 7)])
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li, (u, v) in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
                uv.data[li].uv = (u, v)
        me.materials.append(flag_material(at.name.startswith("flagw")))
        o = bpy.data.objects.new("flagcloth_" + at.name, me)
        bpy.context.scene.collection.objects.link(o)
        o.parent = at


def place(name, x, y, rz=0.0, s=1.0, z=0.0, flags=True):
    """Import game/assets/models/<name>.glb at (x, y, z), turned rz about the up axis and scaled s: its roots (the
    mesh and the marker empties) under one parent, so the markers keep their places on the mesh; flag markers get
    the flag (paint_flags). Returns the parent, or None when the model is missing."""
    path = os.path.join(MODELS, name + ".glb")
    if not os.path.exists(path):
        return None
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = set(bpy.data.objects) - before
    root = bpy.data.objects.new(name + "_at", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (x, y, z)
    root.rotation_euler = (0.0, 0.0, rz)
    root.scale = (s, s, s)
    for o in new:
        if o.parent is None:
            o.parent = root
    if flags:
        paint_flags(sorted((o for o in new if o.type == "EMPTY" and o.name.startswith("flag")), key=lambda o: o.name))
    return root


def reset_scene():
    """An empty scene; the material caches (kit's and the flags') pointed into the old one."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    _FLAG_MATS.clear()


def hex_xy(q, r):
    return 1.5 * q, -math.sqrt(3) * (r + q / 2)


# the border ribbon's bands, outside → in (§6.6: dark edge 0–17 %, body, light stripe 30–52 %, body), the player's
# colours of game/scripts/soft_palette.gd (rim, body, hi)
RIBBON_BANDS = ((0.0, 0.17, "#1D4DB3"), (0.17, 0.30, "#4FA8FF"), (0.30, 0.52, "#B8E0FF"), (0.52, 1.0, "#4FA8FF"))
RIBBON_W = 0.15     # world units (≈ 0.16 at the strategic zoom, §6.6)
RIBBON_IN = 0.03    # the ribbon's outer edge this far inside the hex outline (the tiles' bevelled rims)
RIBBON_Z = 0.03     # over the tile tops (z 0) and the models' lifted bases (z ≤ 0.024): flat on the ground,
                    # under the walls and the troops that stand on it
SOFT_ROUNDS = 3     # Chaikin rounds: a corner cut to ≈ SOFT_R = 0.3 of the hex radius (§6.1 rule 2)
LIFT = 0.0015       # each era model this much over the previous one (no coplanar bases)
SEAM_Z = -0.06      # the soil floor of the seams between tiles (seam_floor)

# tiles: a diagonal path of 8 era hexes from the front (bottom of frame) to the back, wild hexes around
PATH = [(-2, 3), (-1, 2), (-1, 1), (0, 0), (0, -1), (1, -2), (1, -3), (2, -4)]
# the cameras: (location, target, lens). portrait — the B4.6 frame (huts at the bottom, the citadel at the back);
# feature — across the path, so the eras read left to right (huts on the left, the neon citadel on the right) under
# a band of sky and sea for the title (compose_keyart.py --layout=feature)
FRAMES = {
    "portrait": ((4.5, 12.5, 8.0), (0.5, 0.4, 0.9), 38),
    "feature": ((-6.64, 8.94, 4.0), (0.86, 0.84, 1.7), 27),
}
# the sky's strength per frame, and a cool fill sun from behind the camera (its share of the key's energy): the low
# feature camera looks under the conifers' tiers and into the gaps at their feet, which the B4.6 light (sky 0.9, no
# fill) left near-black (compose_keyart's check: runs of 17 px under rgb 24 by the DL3/DL4 hexes). A fill of 0.25
# clears it; sky 1.1 with fill 0.4 cleared it too but flattened the frame
SKY = {"portrait": 0.9, "feature": 0.9}
FILL = {"portrait": 0.0, "feature": 0.25}
FILL_COLOR = (0.66, 0.76, 0.91)  # the map's sky fill #A9C1E8, linear


def seam_floor(centres, material):
    """A soil floor SEAM_Z under the tiles' tops, one full hexagon (radius 1, the exact tiling, so they meet edge to
    edge without overlapping) under each tile: the 0.03 seams between the 0.985 tiles end on lit soil instead of
    the 0.95-deep slot, which a low camera (the feature frame) saw as near-black runs (compose_keyart's check)."""
    verts, faces = [], []
    for (x, y) in centres:
        base = len(verts)
        verts += [(x + math.cos(math.pi / 3 * k), y + math.sin(math.pi / 3 * k), SEAM_Z) for k in range(6)]
        faces.append(tuple(range(base, base + 6)))
    me = bpy.data.meshes.new("seam_floor")
    me.from_pydata(verts, [], faces)
    o = bpy.data.objects.new("seam_floor", me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    return o


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


def main(argv):
    pos = [a for a in argv if not a.startswith("--")]
    out = os.path.abspath(pos[0] if pos else "/tmp/keyart.png")  # Blender reads a relative path from the .blend
    frame = next((a.split("=", 1)[1] for a in argv if a.startswith("--frame=")), "portrait")
    w = int(pos[1]) if len(pos) > 1 else (941 if frame == "portrait" else 2048)
    h = int(pos[2]) if len(pos) > 2 else (1672 if frame == "portrait" else 1000)
    samples = int(pos[3]) if len(pos) > 3 else 64

    reset_scene()
    scene = bpy.context.scene
    grass = noisy_mat("grass", "#58b82a", "#8ad83f", 4.0)
    grass_red = noisy_mat("grass_red", "#b5a43a", "#d4b24e", 4.0)
    dirt = noisy_mat("dirt", "#8a5a34", "#a8743f", 6.0)

    era = {c: len(PATH) - i for i, c in enumerate(PATH)}  # huts nearest the camera, citadel at the back
    floor = []
    for q in range(-5, 6):
        for r in range(-7, 7):
            x, y = hex_xy(q, r)
            if abs(x) > 6.5 or y < -5.5 or y > 9:
                continue
            enemy = q >= 2 and (q, r) not in era
            hex_prism(f"h{q}_{r}", (x, y, 0), 0.985, 0.95, grass_red if enemy else grass, dirt, bevel=0.035)
            floor.append((x, y))
    seam_floor(floor, dirt)

    border_ribbon(list(era))

    for (q, r), dl in era.items():
        x, y = hex_xy(q, r)
        lift = LIFT * (len(PATH) + 1 - dl)  # the huts in front highest: their base lies over the next one's
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
    bg.inputs["Strength"].default_value = SKY[frame]

    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 4.0
    sun.angle = math.radians(8)
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(48), math.radians(-20), math.radians(35))
    scene.collection.objects.link(so)

    loc, aim, lens = FRAMES[frame]
    if FILL[frame] > 0:  # along the view, from behind the camera: it lights what the camera sees of the undersides
        fill = bpy.data.lights.new("fill", "SUN")
        fill.energy = sun.energy * FILL[frame]
        fill.angle = math.radians(30)
        fill.color = FILL_COLOR
        fo = bpy.data.objects.new("fill", fill)
        view = Vector(aim) - Vector(loc)
        fo.rotation_euler = view.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(fo)
    cam = bpy.data.cameras.new("cam")
    cam.lens = lens
    co = bpy.data.objects.new("cam", cam)
    scene.collection.objects.link(co)
    scene.camera = co
    co.location = loc
    target = bpy.data.objects.new("t", None)
    target.location = aim
    scene.collection.objects.link(target)
    tc = co.constraints.new("TRACK_TO")
    tc.target = target
    tc.track_axis = "TRACK_NEGATIVE_Z"
    tc.up_axis = "UP_Y"

    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.seed = 0
    scene.cycles.use_denoising = True
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.film_transparent = False
    transforms = [i.identifier for i in scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    scene.view_settings.view_transform = "AgX" if "AgX" in transforms else "Filmic"
    scene.view_settings.look = "AgX - Punchy" if scene.view_settings.view_transform == "AgX" else "None"
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("keyart ->", out)


if __name__ == "__main__":
    main(sys.argv[1:])
