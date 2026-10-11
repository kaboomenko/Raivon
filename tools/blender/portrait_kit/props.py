"""Props and personal gear (§7.5 steps 7 and 9), placed on their parents by ray casts: P1 has what Bram, Lira and
Vega need in era 1 — the spoon, the millstone amulet on its cord and the sleeve chevrons (Bram); the leaf badge and
the bandage roll on the satchel strap (Lira); the glasses with nose pads (Vega). The pointer is here for P2 (Vega's
hand holds it; hand-free it read as stuck through her side). The creatures, hands and the rest of §7.6's props
column come with P2.

A character's props are data (chars.py "props": [{"kind": ...}, ...]); every prop registers its parent (contacts)
and, when §14 P-A8 lists it, its detail name and minimum visible pixel count.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from . import core
from .core import H


def build_props(ctx):
    for pr in ctx.ch.get("props", []):
        {"spoon": spoon, "amulet": amulet, "chevrons": chevrons, "badge": badge, "bandage": bandage,
         "glasses": glasses, "pointer": pointer}[pr["kind"]](ctx, pr)
        core.update()


def _detail(ctx, pr, default_name, default_px):
    name = pr.get("detail", default_name)
    ctx.details[name] = pr.get("min_px", default_px)
    return "detail:" + name


# ------------------------------------------------------------------ Bram
def spoon(ctx, pr):
    """A wooden spoon tucked behind the belt next to the buckle, bowl up, leaning out (§7.6: bowl 0.16 H, handle up
    20 deg at the beard tip)."""
    belt = ctx.objs["belt"]
    z = ctx.ch["costume"]["layers"][[l["kind"] for l in ctx.ch["costume"]["layers"]].index("belt")]["z"]
    x = pr.get("x", -0.16) * ctx.shoulder_k
    h, nrm = core.ray_front(belt, x, z)
    lean = math.radians(pr.get("lean", 20))
    up = Vector((-math.sin(lean), 0, math.cos(lean)))
    base = h - nrm * 0.012                     # the handle starts behind the belt
    wood = core.principled(ctx, "wood", pr.get("color", "#C98C50"), 0.55)
    bowl_l = pr.get("bowl", 0.16) * H
    grp = _detail(ctx, pr, "spoon", 1500)
    hl = core.uvsphere("spoon_handle", base + up * 0.07, (0.026, 0.02, 0.19), wood, 16, 8, rot=(0, -lean, 0))
    ctx.add(hl, grp, belt, kind="surface")
    bowl = core.uvsphere("spoon_bowl", base + up * (0.24 + bowl_l * 0.5) + nrm * 0.012, (bowl_l * 0.38, 0.034, bowl_l * 0.5),
                         core.principled(ctx, "wood_lt", pr.get("bowl_color", "#D9A066"), 0.5), 32, 16, rot=(0, -lean, 0))
    ctx.add(bowl, grp, hl, kind="surface")
    # the scoop: a darker inset on the bowl's front
    sc = core.uvsphere("spoon_scoop", base + up * (0.24 + bowl_l * 0.5) + nrm * 0.03, (bowl_l * 0.27, 0.012, bowl_l * 0.37),
                       core.principled(ctx, "wood_dk", "#A86F3A", 0.6), 24, 12, rot=(0, -lean, 0))
    ctx.add(sc, grp, bowl, kind="embed")


def amulet(ctx, pr):
    """A millstone amulet (§7.6: disc 0.16 H, a hole, 4 furrows) on a leather cord from the neck."""
    d = pr.get("d", 0.16) * H
    x, z = pr.get("x", -0.33) * ctx.shoulder_k, pr.get("z", -0.93)
    h, nrm, par = core.ray_any(ctx.outer, (x, -2.0, z), (0, 1, 0))
    grp = _detail(ctx, pr, "amulet", 600)
    stone = core.principled(ctx, "stone", pr.get("color", "#A8A196"), 0.85)
    stone_dk = core.principled(ctx, "stone_dk", "#6F6A63", 0.9)
    disc = core.cylinder("amulet", h + nrm * 0.022, d / 2, 0.04, stone, nrm=nrm, bev=0.014)
    ctx.add(disc, grp, par, kind="surface")
    hole = core.torus("amulet_hole", h + nrm * 0.043, d * 0.16, 0.012, stone_dk, nrm=nrm, seg=24, rseg=8)
    ctx.add(hole, grp, disc, kind="embed")
    q = Vector((0, 0, 1)).rotation_difference(nrm)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        p = h + nrm * 0.043 + q @ Vector((math.cos(a) * d * 0.36, math.sin(a) * d * 0.36, 0))
        f = core.uvsphere("amulet_furrow", p, (d * 0.15, 0.007, 0.006), stone_dk, 12, 6)
        f.rotation_mode = "QUATERNION"
        f.rotation_quaternion = q @ Matrix.Rotation(a, 4, "Z").to_quaternion()
        ctx.add(f, grp, disc, kind="embed")
    cord = core.principled(ctx, "cord", pr.get("cord", "#4F321E"), 0.7)
    for s in (-1, 1):
        c0 = h + nrm * 0.03 + Vector((s * 0.03, 0, d * 0.5))
        # the cord runs up over the costume to the neck: cast a few points
        pts = [c0]
        for t in (0.35, 0.7, 1.0):
            px = c0.x + (s * 0.16 * ctx.shoulder_k - c0.x) * t
            pz = c0.z + (-0.66 - c0.z) * t
            hh, nn, _ = core.ray_any(ctx.outer, (px, -2.0, pz), (0, 1, 0))
            if hh is not None:
                pts.append(hh + nn * 0.01)
        cu = core.curve("amulet_cord%+d" % s, pts, [1.0] * len(pts), 0.009, cord, order=3)
        ctx.add(cu, grp, par, kind="surface")


def chevrons(ctx, pr):
    """Rank chevrons on the near sleeve, cast around the arm."""
    arm = ctx.objs["arm-1"]
    top, bot = (Vector(v) for v in ctx.objs["arm_axis-1"])
    m = core.principled(ctx, "chevron", pr.get("color", "#C0452A"), rough=0.6, sheen=0.2)
    axis = (bot - top).normalized()
    look = Vector((-0.55, -0.83, 0.0)).normalized()
    side = axis.cross(look).normalized()
    grp = _detail(ctx, pr, "chevrons", 300)
    for zc in pr.get("at", (0.13, 0.21))[:pr.get("n", 2)]:
        pts = []
        for i in range(7):
            u = -1 + 2 * i / 6
            c = top + (bot - top) * zc + axis * (0.07 * (1 - abs(u)))
            d = (look + side * u * 0.55).normalized()
            hit, nor = core.ray(arm, c + d * 1.0, -d)
            if hit is not None:
                pts.append(hit + nor * 0.013)
        if len(pts) >= 4:
            ctx.add(core.curve("chevron", pts, [1.0] * len(pts), 0.019, m, order=2), grp, arm, kind="surface")


# ------------------------------------------------------------------ Lira
def badge(ctx, pr):
    """A round badge on a strap: a white disc (bevelled) with a raised green leaf and its midrib (not a cross)."""
    st = ctx.objs[pr.get("on", "strap")]
    pts = ctx.L[pr.get("on", "strap")]
    zt = pr.get("z", -0.95)
    p = min(pts, key=lambda q: abs(q.z - zt))
    h, nrm, _ = core.ray_any([st], (p.x, -2.0, p.z), (0, 1, 0))
    if h is None:
        return
    d = pr.get("d", 0.20) * H
    grp = _detail(ctx, pr, "leaf", 500)
    disc = core.cylinder("badge", h + nrm * 0.018, d / 2, 0.03, core.principled(ctx, "badge_white", "#F6F4EE", 0.45),
                         nrm=nrm, bev=0.01)
    ctx.add(disc, grp, st, kind="surface")
    leaf_m = core.principled(ctx, "leaf", pr.get("leaf", "#3E9B5A"), 0.5)
    q = Vector((0, 0, 1)).rotation_difference(nrm)
    tilt = Matrix.Rotation(math.radians(35), 4, "Z").to_quaternion()
    for s in (-1, 1):
        lf = core.uvsphere("leaf_half", h + nrm * 0.036 + q @ (tilt @ Vector((s * d * 0.09, 0, 0))),
                           (d * 0.16, d * 0.30, 0.012), leaf_m, 24, 12)
        lf.rotation_mode = "QUATERNION"
        lf.rotation_quaternion = q @ tilt @ Matrix.Rotation(math.radians(-s * 14), 4, "Z").to_quaternion()
        ctx.add(lf, grp, disc, kind="embed")
    a = h + nrm * 0.045 + q @ (tilt @ Vector((0, -d * 0.28, 0)))
    b = h + nrm * 0.045 + q @ (tilt @ Vector((0, d * 0.28, 0)))
    ctx.add(core.curve("leaf_rib", [a, b], [1.0, 0.6], 0.006, core.principled(ctx, "leaf_rib", "#2A6A3C", 0.5), order=2),
            grp, disc, kind="embed")


def bandage(ctx, pr):
    """A bandage roll (§7.6: 0.12 H) strapped to the satchel strap: a white cylinder with a spiral lip."""
    st = ctx.objs[pr.get("on", "strap")]
    pts = ctx.L[pr.get("on", "strap")]
    zt = pr.get("z", -1.25)
    p = min(pts, key=lambda q: abs(q.z - zt))
    h, nrm, _ = core.ray_any([st], (p.x, -2.0, p.z), (0, 1, 0))
    if h is None:
        return
    d = pr.get("d", 0.12) * H
    ln = d * 1.25
    i = pts.index(p)
    tang = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
    across = tang.cross(nrm).normalized()
    grp = _detail(ctx, pr, "bandage", 400)
    roll = core.cylinder("bandage", h + nrm * (d * 0.5 + 0.004), d / 2, ln, core.principled(ctx, "bandage", "#F4F2EC", 0.8,
                                                                                         sheen=0.3), nrm=across, bev=0.008)
    ctx.add(roll, grp, st, kind="surface")
    lip = core.torus("bandage_lip", h + nrm * (d * 0.5 + 0.004) + across * ln * 0.18, d * 0.5, 0.006,
                     core.principled(ctx, "bandage_lip", "#D8D2C4", 0.8), nrm=across, seg=32, rseg=8)
    ctx.add(lip, grp, roll, kind="embed")


# ------------------------------------------------------------------ Vega
def _closest_parent(ctx, obj, cands):
    """The candidate an attached part really touches (smallest gap): the contact test (qa.contacts) checks it there."""
    core.update()
    best, bd = cands[0], 1e9
    verts = core.eval_verts(obj)[::4]
    for c in cands:
        if c is None:
            continue
        tree = core.bvh_of(c)
        inv = c.matrix_world.inverted()
        dmin = min((tree.find_nearest(inv @ v)[3] or 1e9) for v in verts)
        if dmin < bd:
            best, bd = c, dmin
    return best


def glasses(ctx, pr):
    """Rectangular glasses with rounded corners (§7.5, §7.6): a frame 0.025 H, a bridge over the nose, temples running
    back under the hair, two pads resting on the nose. The lenses are not refractive glass (a refractive lens without
    caustics kept 10 % of the iris contrast behind it, §7.5 asks >= 70 %): core.glass_mat — transparent with a tint by
    multiplication, a flat warm Fresnel sheen and one diagonal highlight band; flat-shaded, casting no shadow. For the
    contact test (P-A7) the rims and the bridge are registered on what they rest on (the nose or the face), the pads on
    the nose, the temples embedded in the hair."""
    head = ctx.objs["head"]
    nose = ctx.objs.get("nose")
    hair = ctx.objs.get("hair") or head
    t = pr.get("frame", 0.025) * H
    fm = core.principled(ctx, "glasses_frame", pr.get("color", "#2A2A30"), rough=0.3, metal=pr.get("metal", 0.0), coat=0.4)
    glass = core.glass_mat(ctx, "glasses_lens", pr.get("tint", "#F4F8FF"))
    grp = _detail(ctx, pr, "glasses", 500)
    inner = []
    rims = []
    for e in ctx.objs["eyes"]:
        rx, ry, rz = e["radii"]
        side = e["side"]
        # the frame is sized and centred on the visible eye (the almond: half width xc0 rx, half height kh rz =
        # sclera_h / 2), not on the lens behind it, and stands level with the face (the eye's yaw, not its pitch)
        lens_rot = e["obj"].rotation_euler.to_matrix()
        rot = Matrix.Rotation(e["obj"].rotation_euler.z, 3, "Z")
        c = e["centre"] + lens_rot @ Vector((e["x0"] * rx, 0.0, 0.0))
        w = e["xc0"] * rx * pr.get("w", 2.0)
        hh = e["kh"] * rz * pr.get("h", 1.26)
        drop = pr.get("drop", 0.02) * H
        front = c + rot @ Vector((0, -(ry + pr.get("off", 0.04)), -drop))
        ex = pr.get("square", 5.0)        # superellipse exponent: a rectangle with rounded corners
        pts = []
        for k in range(40):
            a = 2 * math.pi * k / 40
            cx, cz = math.cos(a), math.sin(a)
            x = w * math.copysign(abs(cx) ** (2 / ex), cx)
            z = hh * math.copysign(abs(cz) ** (2 / ex), cz)
            pts.append(front + rot @ Vector((x, 0.0, z)))
        rim = core.curve("glasses_rim_" + e["tag"], pts, [1.0] * len(pts), t / 2, fm, order=2, kind="POLY", cyclic=True)
        ctx.add(rim, grp, _closest_parent(ctx, rim, [nose, head]), kind="surface", head=True)
        rims.append(rim)
        # the lens: a thin plate filling the rim
        bm = bmesh.new()
        rt = rot.transposed()
        vs = [bm.verts.new(front + rot @ ((rt @ (q - front)) * 0.98)) for q in pts]
        bm.faces.new(vs)
        lens = core.mesh_obj("glasses_lens_" + e["tag"], bm)
        core.solidify(lens, 0.006, offset=0.0)
        # flat: a smooth-shaded n-gon has only rim vertices, so its normals tilt across the whole lens and the Fresnel
        # sheen turned the near lens grey (iris contrast 0.57)
        core.finish(lens, glass, smooth=False)
        lens["kit_glass"] = 1
        lens.visible_shadow = False   # no caustics: a glass that casts a shadow would put the eyes in the dark
        ctx.add(lens, "glass", rim, kind="embed", head=True)
        inner.append(front + rot @ Vector((-side * w, 0.0, hh * 0.25)))
        # the pad: a small clear bead behind the rim's inner lower corner, resting on the side of the nose (dark
        # frame-coloured pads read as two dots on the nose, review r3: half the size, the lens's clear material,
        # set back from the rim)
        if nose is not None:
            corner = front + rot @ Vector((-side * w * 0.92, 0.0, -hh * 0.35))
            hp, np_ = core.ray(nose, corner + rot @ Vector((0.0, 0.03, 0.0)), Vector((-side, 0.0, 0.0)), dist=0.6)
            if hp is not None and (hp - corner).length < 0.25:
                pr_ = t * 0.38
                pad = core.uvsphere("glasses_pad_" + e["tag"], hp + np_ * pr_ * 0.6, (pr_, pr_ * 0.55, pr_ * 1.3),
                                    glass, 16, 8)
                core.align_z(pad, np_)
                ctx.add(pad, grp, nose, kind="surface", head=True)
                arm_ = core.curve("glasses_padarm_" + e["tag"], [corner, hp + np_ * pr_], [1.0, 0.8], t * 0.16, fm,
                                  order=2)
                ctx.add(arm_, grp, rim, kind="surface", head=True)
        # the temple: from the outer edge back along the head side into the hair
        outer = front + rot @ Vector((side * w, 0.0, hh * 0.25))
        back = []
        for f in (0.0, 0.35, 0.7, 1.0):
            p = outer + Vector((side * 0.05 * f, 0.42 * f, -0.02 * f))
            hh2, nn = core.ray(head, Vector((side * 3, p.y, p.z)), (-side, 0, 0))
            if hh2 is not None and f > 0:
                p = hh2 + nn * (t * 0.8 + 0.035)
            back.append(p)
        tm = core.curve("glasses_temple_" + e["tag"], back, [1.0] * len(back), t * 0.42, fm, order=3)
        ctx.add(tm, grp, hair, kind="embed", head=True)       # runs back under the hair by design
    # the bridge over the nose
    if len(inner) == 2:
        mid = (inner[0] + inner[1]) / 2
        hb, nb = core.ray_front(head, mid.x, mid.z)
        top = (hb + nb * (t * 0.8 + 0.01)) if hb is not None else mid
        br = core.curve("glasses_bridge", [inner[0], top, inner[1]], [1, 1, 1], t / 2, fm, order=3)
        ctx.add(br, grp, _closest_parent(ctx, br, [nose, head]), kind="surface", head=True)
    ctx.glasses = True


def pointer(ctx, pr):
    """The pointer (§7.6, §7.5 "указка — под рукой"): a wooden rod with an iron tip under the far arm, horizontal and
    pointing to the right of the frame at chest level, a fold of the sleeve over it where it leaves the arm; the tip
    is slim: 0.16 H long (§7.6), its base tip_w x the shaft's radius (1.8: a leaf a little wider than the shaft, not an
    arrowhead). NOT USED in P1 (chars.py, Vega): hand-free, the rod could only leave the body at the far side's
    contour and read as stuck through her side (art director note 2); P2's hand module holds it."""
    k = ctx.shoulder_k
    d = core.world_dir(ctx, (1.0, pr.get("toward", -0.15), 0.0))
    p0 = Vector((pr.get("x", 0.60) * k, pr.get("y", 0.02), pr.get("z", -1.0)))
    shaft = pr.get("d", 0.045) * H
    tip_l = pr.get("tip", 0.16) * H
    reach = pr.get("reach", 0.42)
    a, b = p0 - d * 0.40, p0 + d * reach
    arm = ctx.objs["arm+1"]
    wood = core.principled(ctx, "pointer_wood", pr.get("color", "#8A5A34"), 0.55, coat=0.1)
    grp = _detail(ctx, pr, "pointer", 1200)
    rod = core.curve("pointer_rod", [a, (a + b) / 2, b], [1, 1, 1], shaft / 2, wood, order=2)
    ctx.add(rod, grp, arm, kind="embed")      # clamped in the arm: its back half is inside the sleeve by design
    iron = core.principled(ctx, "pointer_tip", pr.get("tip_color", "#8A929C"), 0.32, metal=0.5)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=shaft / 2 * pr.get("tip_w", 1.8), radius2=0.004,
                          depth=tip_l)
    tip = core.mesh_obj("pointer_tip", bm)
    tip.location = b + d * (tip_l / 2)
    core.align_z(tip, d)
    core.bevel(tip, 0.004, 2)
    core.finish(tip, iron)
    ctx.add(tip, grp, rod, kind="surface")
    ferrule = core.cylinder("pointer_ferrule", b - d * 0.01, shaft * 0.62, 0.035, iron, nrm=d, bev=0.004)
    ctx.add(ferrule, grp, rod, kind="surface")
    ctx.sig_objs += [rod, tip, ferrule]
    ctx.L["pointer_tip"] = b + d * tip_l
    # the sleeve fold over the rod where it leaves the arm: a soft roll of the sleeve's own cloth along the arm,
    # standing just outside its surface across the shaft (the rod comes out from under it; its shadow lies on the rod)
    hit, nor = core.ray(arm, b + d * 0.05, -d, dist=1.0)
    if hit is not None and pr.get("fold", True):
        cloth = arm.data.materials[0]
        top_, bot_ = (Vector(v) for v in ctx.objs["arm_axis+1"])
        axis = (top_ - bot_).normalized()
        q = core.frame_quat(axis, d)
        cam = core.world_dir(ctx, (0.0, -1.0, 0.0))          # toward the camera, in body space
        el = [dict(co=hit + d * shaft * 0.45 + axis * shaft * 0.6 + cam * shaft * 0.9,
                   half=(shaft * 1.7, shaft * 1.05, shaft * 2.8), stiff=2.4, rot=q),
              dict(co=hit + d * shaft * 0.25 - axis * shaft * 1.9 + cam * shaft * 0.6,
                   half=(shaft * 1.3, shaft * 0.75, shaft * 1.5), stiff=2.4, rot=q)]
        fold = core.mb_mesh(ctx, "Fold", el, 0.006, cloth, smooth_iter=2, name="pointer_fold")
        ctx.add(fold, "costume", arm, kind="embed")
