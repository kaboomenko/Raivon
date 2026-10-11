"""C-1 of docs/art_direction.md §7.14: the on-screen lean of every icon's vertical axis, through the icon's own camera.

Run (bpy as a Python module): python3 tools/qa_icons/measure_lean.py [names ...] [--strict]

Imports tools/blender/icon_assets.py read-only, builds every icon in ICONS (or the names given), adds the icon's
render camera (icon_assets.setup_camera; the old ortho emblem camera for an icon_assets without camera modes) and
projects the model's up axis (the _tilt pivot's +Z, world +Z without one) at the model's centre:
- lean: the projected up axis against the frame's vertical, degrees, + = the top leans right;
- edges: the model's own front-left and front-right vertical bbox edges; asym = their mean (what falls one way),
  conv = half their difference (the symmetric keystone of a camera above, + = wider at the top);
- elev: the view elevation over the model's horizontal plane at its centre;
- body: for an object-camera model with a part named "body" (the chests), the keystone of its real front corner edges, flare
  included: half the angle between the projected front-left and front-right body edges (§7.14 C-1: <= 12° per side;
  the research measured −10.2° for flare 0.93 at 85 mm);
- mode: the camera mode (object / emblem).
FLAG marks |lean| > 0.5°, |asym| > 0.5° or body > 12° except the deliberately rolled tools (hammer, key, hourglass,
shard).
Exit 1 with --strict on any FLAG.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "blender"))
import bpy  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import icon_assets as ia  # noqa: E402

ROLL = {"hammer", "key", "hourglass", "shard"}  # a dynamic tool pose (ry), not a perspective error
LIMIT, KEYSTONE = 0.5, 12.0


def build(name):
    if hasattr(ia, "build"):
        ia.build(name)
    else:
        ia.reset()
        ia.ICONS[name]()


def camera(name):
    fill = ia.FILL_BY.get(name, ia.FILL)
    if hasattr(ia, "setup_camera"):
        return ia.setup_camera(name, fill), ia.camera_mode(name)
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = ia.RAW
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.location = (0, -6, 0.6)
    cam.rotation_euler = (math.radians(84), 0, 0)
    ia._fit_camera(cam, fill)
    sc.camera = cam
    return cam, "emblem"


def model_points():
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        pts += [eo.matrix_world @ v.co for v in me.vertices]
        eo.to_mesh_clear()
    return pts


def angle(sc, cam, a, b):
    """Screen angle of the segment a → b (world points) against the vertical, degrees, + = b leans right of a."""
    pa, pb = world_to_camera_view(sc, cam, a), world_to_camera_view(sc, cam, b)
    return math.degrees(math.atan2(pb.x - pa.x, pb.y - pa.y))


def measure(name):
    build(name)
    cam, mode = camera(name)
    sc = bpy.context.scene
    bpy.context.view_layer.update()
    tilt = bpy.data.objects.get("tilt")
    M = tilt.matrix_world.copy() if tilt else Matrix.Identity(4)
    R = M.to_3x3()
    up = (R @ Vector((0, 0, 1))).normalized()
    pts = model_points()
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ctr = (lo + hi) / 2
    lean = angle(sc, cam, ctr, ctr + up * 0.25)
    # the model's own bbox, in the pivot's frame
    inv = M.inverted()
    loc_pts = [inv @ p for p in pts]
    l0 = Vector((min(p.x for p in loc_pts), min(p.y for p in loc_pts), min(p.z for p in loc_pts)))
    l1 = Vector((max(p.x for p in loc_pts), max(p.y for p in loc_pts), max(p.z for p in loc_pts)))
    eL = angle(sc, cam, M @ Vector((l0.x, l0.y, l0.z)), M @ Vector((l0.x, l0.y, l1.z)))
    eR = angle(sc, cam, M @ Vector((l1.x, l0.y, l0.z)), M @ Vector((l1.x, l0.y, l1.z)))
    asym, conv = (eL + eR) / 2, (eR - eL) / 2
    if cam.data.type == "ORTHO":
        view = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    else:
        view = (ctr - cam.matrix_world.translation).normalized()
    elev = math.degrees(math.asin(max(-1.0, min(1.0, -view.dot(up)))))
    body = body_keystone(sc, cam) if mode == "object" else None
    return lean, asym, conv, elev, body, mode


def body_keystone(sc, cam):
    """Half the angle between the projected front-left and front-right edges of the part named "body", or None."""
    o = bpy.data.objects.get("body")
    if o is None:
        return None
    dg = bpy.context.evaluated_depsgraph_get()
    eo = o.evaluated_get(dg)
    me = eo.to_mesh()
    vs = [eo.matrix_world @ v.co for v in me.vertices]
    eo.to_mesh_clear()
    zt, zb = max(v.z for v in vs), min(v.z for v in vs)
    front = [v for v in vs if v.y < min(w.y for w in vs) + 0.05]
    top = [v for v in front if v.z > zt - 0.05]
    bot = [v for v in front if v.z < zb + 0.05]
    if not top or not bot:
        return None
    eL = angle(sc, cam, min(bot, key=lambda v: v.x), min(top, key=lambda v: v.x))
    eR = angle(sc, cam, max(bot, key=lambda v: v.x), max(top, key=lambda v: v.x))
    return (eR - eL) / 2


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(ia.ICONS)
    flags = 0
    print("%-14s %7s %7s %7s %7s %7s  %-6s %s" % ("icon", "lean", "asym", "conv", "elev", "body", "mode", ""))
    for n in names:
        lean, asym, conv, elev, body, mode = measure(n)
        bad = n not in ROLL and (abs(lean) > LIMIT or abs(asym) > LIMIT or (body is not None and abs(body) > KEYSTONE))
        flags += bad
        note = "FLAG" if bad else ("roll (deliberate)" if n in ROLL else "")
        print("%-14s %+7.2f %+7.2f %+7.2f %7.1f %7s  %-6s %s" % (n, lean, asym, conv, elev,
              "%+.2f" % body if body is not None else "-", mode, note), flush=True)
    print("RESULT", "FAIL" if flags else "PASS", flags)
    sys.exit(1 if flags and "--strict" in sys.argv else 0)


if __name__ == "__main__":
    main()
