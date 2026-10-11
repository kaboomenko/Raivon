"""Pose, gaze, light, camera, framing and render (§7.11).

- pose: the head parts turn on a pivot at the neck (turn, roll, nod per character, plus the mood's head delta), then
  the whole figure turns by the character's body angle (face toward the right of the frame);
- camera: 85 mm, sensor 36 mm fitted VERTICAL (23.9 deg), level (no tilt) at the eye height; the framing solver
  sets shift_x, shift_y and the distance from projected landmarks so that on the 512×588 master the eye line is at
  y 250 +- 2, the head centre at x 256 +- 12 and the head height H_px at the character's value +- 3; it then checks the
  skyline (>= 30 px; 50 for crowns and leader headgear) and the side band (above y 412 nothing within 28 px of a
  side); a frame that does not fit steps H_px down by 4 to 256, below that the build fails with a message;
- gaze: once the pose and the camera are known, each iris is aimed at the camera (a shader offset) and its two
  catchlights are placed where the key light would glint (big one) and opposite (small one), emission 6, no shadow;
- light: key / rim / kicker area lights and the sky world whose glossy rays see a warm neutral (§7.11);
- render: Cycles, AgX Punchy, 64 samples (96 for review), adaptive 0.01, OIDN, filter 1.2, 6 bounces, 8 transparent,
  no caustics, clamp indirect 3, seed 0, persistent data, transparent film, RGBA 8 bit.
"""
import math
import time

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

from . import core, style

R = style.RENDER


# ------------------------------------------------------------------ pose
def pose(ctx):
    po = ctx.ch["pose"]
    md = ctx.ch.get("pose_" + ctx.mood, {})
    pivot = core.link(bpy.data.objects.new("head_pivot", None))
    pivot.location = PIVOT
    core.update()
    for p in ctx.parts:
        if p.head and p.obj.parent is None:
            p.obj.parent = pivot
            p.obj.matrix_parent_inverse = pivot.matrix_world.inverted()
    for k in ("mouth_cutter",):
        o = ctx.objs.get(k)
        if o is not None and o.parent is None:
            o.parent = pivot
            o.matrix_parent_inverse = pivot.matrix_world.inverted()
    nod = po.get("nod", 0.0) + md.get("nod", 0.0)
    roll = po.get("roll", 0.0) + md.get("roll", 0.0)
    turn = po.get("head", 0.0) + md.get("head", 0.0)
    pivot.rotation_euler = (math.radians(-nod), math.radians(roll), math.radians(turn))
    root = core.link(bpy.data.objects.new("root", None))
    for o in bpy.context.scene.objects:
        if o.parent is None and o is not root and o.type not in ("LIGHT", "CAMERA"):
            o.parent = root
    root.rotation_euler.z = math.radians(po["body"])
    ctx.objs["pivot"], ctx.objs["root"] = pivot, root
    core.update()


PIVOT = (0.0, 0.05, -0.45)


def head_pose_matrix(ctx, with_body=False):
    """The pose of `pose` as a matrix, known before the pose is applied: head-local -> body space (the head turns,
    rolls and nods on the neck pivot), and with with_body the body's turn too (-> world). Used to anchor body-side
    parts to head landmarks (the braid's root at the nape) and to foresee the camera's perspective."""
    po = ctx.ch["pose"]
    md = ctx.ch.get("pose_" + ctx.mood, {})
    nod = po.get("nod", 0.0) + md.get("nod", 0.0)
    roll = po.get("roll", 0.0) + md.get("roll", 0.0)
    turn = po.get("head", 0.0) + md.get("head", 0.0)
    rot = Euler((math.radians(-nod), math.radians(roll), math.radians(turn)), "XYZ").to_matrix().to_4x4()
    m = Matrix.Translation(Vector(PIVOT)) @ rot @ Matrix.Translation(-Vector(PIVOT))
    if with_body:
        m = Matrix.Rotation(math.radians(po["body"]), 4, "Z") @ m
    return m


def head_to_world(ctx, p):
    """A head-local landmark (before the pose) -> world, through the posed pivot."""
    pivot = ctx.objs["pivot"]
    rest = Matrix.Translation(Vector(PIVOT))
    return pivot.matrix_world @ (rest.inverted() @ Vector(p))


# ------------------------------------------------------------------ light and world
def light_rig():
    sc = bpy.context.scene
    L = style.LIGHT
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    bg.inputs["Color"].default_value = core.rgba(L["world"])
    bg.inputs["Strength"].default_value = L["world_strength"]
    ref = nt.nodes.new("ShaderNodeBackground")
    ref.inputs["Color"].default_value = core.rgba(L["reflect"])
    ref.inputs["Strength"].default_value = L["world_strength"] * L["reflect_share"]
    lp = nt.nodes.new("ShaderNodeLightPath")
    mx = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Glossy Ray"], mx.inputs["Fac"])
    nt.links.new(bg.outputs[0], mx.inputs[1])
    nt.links.new(ref.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], nt.nodes["World Output"].inputs["Surface"])
    for name in ("key", "rim", "kick"):
        d = L[name]
        lt = bpy.data.lights.new(name, "AREA")
        lt.energy = d["energy"]
        lt.color = core.srgb(d["color"])
        lt.size = d["size"]
        o = core.link(bpy.data.objects.new(name, lt))
        o.location = d["loc"]
        o.rotation_euler = (Vector(d["target"]) - Vector(d["loc"])).to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------------ projection
def _frame(cam):
    sc = bpy.context.scene
    fr = [v for v in cam.data.view_frame(scene=sc)]
    xs = [v.x for v in fr]
    ys = [v.y for v in fr]
    return min(xs), max(xs), min(ys), max(ys), fr[0].z


def project(cam, pts, size):
    """World points (N, 3) -> PNG pixel coords (N, 2) (x right, y down), as world_to_camera_view does."""
    W, Hh = size
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    mi = np.array(cam.matrix_world.inverted())
    hom = np.c_[pts, np.ones(len(pts))] @ mi.T
    x0, x1, y0, y1, fz = _frame(cam)
    z = hom[:, 2]
    k = fz / np.where(np.abs(z) < 1e-9, -1e-9, z)
    qx, qy = hom[:, 0] * k, hom[:, 1] * k
    u = (qx - x0) / (x1 - x0)
    v = (qy - y0) / (y1 - y0)
    return np.c_[u * W, (1 - v) * Hh]


def visible_points(ctx):
    """World positions of every render-visible vertex (meshes, curves, metaball meshes)."""
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in bpy.context.scene.objects:
        if o.type not in ("MESH", "CURVE") or o.hide_render:
            continue
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        n = len(me.vertices)
        if n:
            co = np.empty(n * 3)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            mw = np.array(o.matrix_world)
            out.append(np.c_[co, np.ones(n)] @ mw.T)
        ev.to_mesh_clear()
    return np.concatenate(out)[:, :3] if out else np.zeros((0, 3))


def head_points(ctx):
    dg = bpy.context.evaluated_depsgraph_get()
    head = ctx.objs["head"]
    ev = head.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    mw = np.array(head.matrix_world)
    return (np.c_[co, np.ones(n)] @ mw.T)[:, :3]


# ------------------------------------------------------------------ camera and framing
def camera(ctx):
    sc = bpy.context.scene
    cam = core.link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam")))
    cam.data.lens = R["lens"]
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_height = R["sensor"]
    cam.data.sensor_width = R["sensor"]
    cam.rotation_euler = (math.radians(90), 0, 0)   # level, looking along +Y
    sc.camera = cam
    ctx.objs["cam"] = cam
    return cam


def frame_targets(ctx, size, frame="bust"):
    """The framing numbers for a frame mode, in PNG px of `size`. bust = §7.11 on the 512×588 master (scaled for other
    sizes); face = a square face crop (not shipped: §7.12 — +31 % head for slots <= 72 px), hair may leave the top."""
    if frame == "face":
        w = size[0]
        return dict(eye_y=0.50 * w, head_x=0.5 * w, h_px=0.62 * w, sky=None, side_band=None, side_rows=None,
                    step=R["h_step"] * w / 512, h_min=0.5 * w)
    k = size[1] / 588.0
    sky = R["skyline_headgear"] if ctx.ch.get("tall_headgear") else R["skyline"]
    return dict(eye_y=R["eye_y"] * k, head_x=R["head_x"] * k, h_px=float(ctx.ch["head"]["h_px"]) * k, sky=sky * k,
                side_band=R["side_band"] * k, side_rows=R["side_rows"] * k, step=R["h_step"] * k, h_min=R["h_min"] * k)


def solve_frame(ctx, size, frame="bust", log=print):
    """Shift and distance so the eye line, head centre and head height land on §7.11's numbers; then the skyline and
    side-band checks, stepping H_px down by 4 when the frame does not fit (an error below 256)."""
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = size
    t = frame_targets(ctx, size, frame)
    k = size[1] / 588.0
    cam = ctx.objs["cam"]
    eyes = [e["obj"].matrix_world.translation.copy() for e in ctx.objs["eyes"]]
    eye_z = sum(e.z for e in eyes) / 2
    chin = head_to_world(ctx, ctx.L["chin"])
    crown = head_to_world(ctx, ctx.L["crown"])
    target_h = t["h_px"]
    allpts = visible_points(ctx)
    hpts = head_points(ctx)
    while True:
        cam.location = (0.0, -6.0, eye_z)
        cam.data.shift_x = cam.data.shift_y = 0.0
        for it in range(10):
            core.update()
            pe = project(cam, eyes, size)
            ph = project(cam, [chin, crown], size)
            hp = project(cam, hpts, size)
            h_px = abs(ph[0, 1] - ph[1, 1])
            eye_y = pe[:, 1].mean()
            head_x = (hp[:, 0].min() + hp[:, 0].max()) / 2
            err_h = h_px / target_h
            dy = eye_y - t["eye_y"]
            dx = head_x - t["head_x"]
            if abs(err_h - 1) < 0.002 and abs(dy) < 0.4 and abs(dx) < 0.8:
                break
            cam.location.y = -((-cam.location.y) * err_h)      # the size goes ~1/distance
            # shift is in units of the frame's fitted (vertical) size: one unit = size[1] pixels
            cam.data.shift_y -= dy / size[1]       # + shift_y moves the content down
            cam.data.shift_x += dx / size[1]
        core.update()
        pa = project(cam, allpts, size)
        sky = float(pa[:, 1].min())
        ok = True
        side_l = side_r = float(size[0])
        if t["side_rows"] is not None:
            upper = pa[pa[:, 1] < t["side_rows"]]
            side_l = float(upper[:, 0].min()) if len(upper) else float(size[0])
            side_r = float(size[0] - upper[:, 0].max()) if len(upper) else float(size[0])
            ok = sky >= t["sky"] and side_l >= t["side_band"] and side_r >= t["side_band"]
        ctx.frame = dict(mode=frame, h_px=round(h_px / k, 2), eye_y=round(eye_y / k, 2), head_x=round(head_x / k, 2),
                         skyline=round(sky / k, 1), side=(round(side_l / k, 1), round(side_r / k, 1)),
                         dist=round(-cam.location.y, 4), shift=(round(cam.data.shift_x, 5), round(cam.data.shift_y, 5)),
                         target_h=round(target_h / k, 1))
        if ok:
            return ctx.frame
        log("frame: H_px %.0f does not fit (skyline %.1f, sides %.1f / %.1f) -> H_px %.0f" % (
            target_h / k, sky / k, side_l / k, side_r / k, (target_h - t["step"]) / k))
        target_h -= t["step"]
        if target_h < t["h_min"] - 1e-6:
            raise RuntimeError("%s: the portrait does not fit the frame even at H_px %.0f (skyline %.1f px, sides "
                               "%.1f / %.1f px; need >= %.0f and >= %.0f on the 512x588 master)" % (
                                   ctx.cid, t["h_min"] / k, sky / k, side_l / k, side_r / k, t["sky"] / k,
                                   t["side_band"] / k))


# ------------------------------------------------------------------ gaze and catchlights
def solve_gaze(ctx):
    cam = ctx.objs["cam"]
    key = Vector(style.LIGHT["key"]["loc"])
    ey = ctx.ch["eyes"]
    off = ey.get("gaze", (0.0, 0.0))
    catch = core.emit_mat(ctx, "catch", "#ffffff", style.STYLE["catch_emit"])
    ctx.L["iris_world"] = []
    for e in ctx.objs["eyes"]:
        eye = e["obj"]
        mw = eye.matrix_world
        c = mw.translation
        local = (mw.inverted().to_3x3() @ (cam.location - c)).normalized()
        gx, gz = local.x + off[0], local.z + off[1]
        mat = eye.data.materials[0]
        sx = mat["eye_sx"]
        ri = mat["eye_ri"]
        if "al_x0" in eye:
            # the cartoon cheat: the iris turns toward the camera from where a forward-looking eye has it (the almond's
            # centre), 80 % of the way and never past the almond's side (the far eye of a 3/4 face looks ~55 deg off
            # its lens axis; a true aim would put half its iris under the corner)
            x0, room = eye["al_x0"], max(0.0, eye["al_xc0"] - ri / sx) * 0.8
            gx = x0 + max(-room, min(room, (gx - x0) * 0.8))
            gz = max(-0.45 * eye["al_kh"], min(0.25 * eye["al_kh"], gz))
        mat.node_tree.nodes["gaze"].inputs["Location"].default_value = (-gx * sx, 0.0, -gz)
        e["gaze"] = (gx, gz)
        gy = -math.sqrt(max(0.0, 1 - gx * gx - gz * gz))
        ctx.L["iris_world"].append(mw @ Vector((gx, gy, gz)))
        # the big catchlight: where the key glints (the half vector), kept inside the iris
        nrm_m = mw.to_3x3().inverted().transposed()
        to_cam = (cam.location - c).normalized()
        to_key = (key - c).normalized()
        half = (to_cam + to_key).normalized()
        best, bd = None, -2.0
        for i in range(-12, 13):
            for j in range(-12, 13):
                ux, uz = i / 12.5, j / 12.5
                if ux * ux + uz * uz >= 0.98:
                    continue
                uy = -math.sqrt(1 - ux * ux - uz * uz)
                n = (nrm_m @ Vector((ux, uy, uz))).normalized()
                dd = n.dot(half)
                if dd > bd:
                    bd, best = dd, (ux, uz)
        bx, bz = best
        # inside 0.62 of the iris radius (in the round, rz-unit metric of the shader)
        dxr, dzr = (bx - gx) * sx, bz - gz
        rr = math.hypot(dxr, dzr)
        lim = 0.55 * ri
        if rr > lim or rr < 0.25 * ri:
            ang = math.atan2(dzr, dxr) if rr > 1e-6 else math.radians(140)
            rr2 = min(max(rr, 0.35 * ri), lim)
            dxr, dzr = math.cos(ang) * rr2, math.sin(ang) * rr2
        dzr = min(dzr, 0.30 * ri)   # not too high: a squinting lid must not hide it
        spots = [((gx + dxr / sx, gz + dzr), style.STYLE["catch_big"]),
                 ((gx - 0.85 * dxr / sx, gz - 0.85 * dzr), style.STYLE["catch_small"])]
        if ey.get("one_catch") and e["side"] < 0:
            spots = spots[:1]
        rz = e["radii"][2]
        for k, ((ux, uz), frac) in enumerate(spots):
            uy = -math.sqrt(max(0.0, 1 - ux * ux - uz * uz))
            pos = mw @ Vector((ux, uy, uz))
            n = (nrm_m @ Vector((ux, uy, uz))).normalized()
            r = frac * ri * rz          # the diameter is frac x the iris diameter (2 ri rz)
            o = core.uvsphere("catch_%s_%d" % (e["tag"], k), pos + n * 0.003, (r, r, r * 0.3), catch, 16, 8)
            core.align_z(o, n)
            o.visible_shadow = False
            ctx.add(o, "catch", eye, kind="embed")


# ------------------------------------------------------------------ render
def setup_render(size, samples, look=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = R["adaptive"]
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.cycles.filter_width = R["filter"]
    sc.cycles.pixel_filter_type = "BLACKMAN_HARRIS"
    sc.cycles.max_bounces = R["bounces"]
    sc.cycles.transparent_max_bounces = R["transparent_bounces"]
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.cycles.sample_clamp_indirect = R["clamp_indirect"]
    sc.cycles.seed = 0
    sc.cycles.use_animated_seed = False
    sc.render.use_persistent_data = True
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = size
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look or R["look"]
    sc.view_settings.exposure = 0.0


def render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0
