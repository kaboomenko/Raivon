"""Props and personal gear (§7.5 steps 7 and 9), placed on their parents by ray casts: P1 has what Bram, Lira and
Vega need in era 1 — the spoon, the millstone amulet on its cord and the sleeve chevrons (Bram); the leaf badge and
the bandage roll on the satchel strap (Lira); the glasses and the pointer tucked under the far arm (Vega). The
creatures, hands and the rest of §7.6's props column come with P2.

A character's props are data (chars.py "props": [{"kind": ...}, ...]); every prop registers its parent (contacts)
and, when §14 P-A8 lists it, its detail name and minimum visible pixel count.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from . import core
from .core import H
from .style import C


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
def glasses(ctx, pr):
    """Rectangular glasses with rounded corners (§7.5, §7.6): a frame 0.025 H, a bridge over the nose, temples running
    back under the hair, pads on the nose; glass lenses (transmission 0.95, IOR 1.2, a tint by multiplication)."""
    head = ctx.objs["head"]
    t = pr.get("frame", 0.025) * H
    fm = core.principled(ctx, "glasses_frame", pr.get("color", "#2A2A30"), rough=0.3, metal=pr.get("metal", 0.0), coat=0.4)
    glass = core.glass_mat(ctx, "glasses_lens", pr.get("tint", "#F4F8FF"))
    grp = _detail(ctx, pr, "glasses", 500)
    inner = []
    rims = []
    for e in ctx.objs["eyes"]:
        rx, ry, rz = e["radii"]
        c = e["centre"]
        side = e["side"]
        rot = e["obj"].rotation_euler.to_matrix()
        w = rx * pr.get("w", 1.55)
        hh = rz * pr.get("h", 1.05)
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
        ctx.add(rim, grp, head, kind="free", head=True)
        rims.append(rim)
        # the lens: a thin plate filling the rim
        bm = bmesh.new()
        rt = rot.transposed()
        vs = [bm.verts.new(front + rot @ ((rt @ (q - front)) * 0.98)) for q in pts]
        bm.faces.new(vs)
        lens = core.mesh_obj("glasses_lens_" + e["tag"], bm)
        core.solidify(lens, 0.006, offset=0.0)
        core.finish(lens, glass)
        lens["kit_glass"] = 1
        lens.visible_shadow = False   # no caustics: a glass that casts a shadow would put the eyes in the dark
        ctx.add(lens, "glass", rim, kind="embed", head=True)
        inner.append(front + rot @ Vector((-side * w, 0.0, hh * 0.25)))
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
        ctx.add(tm, grp, rim, kind="surface", head=True)
    # the bridge over the nose
    if len(inner) == 2:
        mid = (inner[0] + inner[1]) / 2
        hb, nb = core.ray_front(head, mid.x, mid.z)
        top = (hb + nb * (t * 0.8 + 0.01)) if hb is not None else mid
        br = core.curve("glasses_bridge", [inner[0], top, inner[1]], [1, 1, 1], t / 2, fm, order=3)
        ctx.add(br, grp, rims[0], kind="surface", head=True)
    ctx.glasses = True


def pointer(ctx, pr):
    """The pointer (§7.6, P1 pose without a hand): a wooden rod with an iron tip tucked between the far arm and the
    torso, horizontal and pointing to the right of the frame at chest level."""
    k = ctx.shoulder_k
    d = core.world_dir(ctx, (1.0, pr.get("toward", -0.15), 0.0))
    p0 = Vector((pr.get("x", 0.60) * k, pr.get("y", 0.02), pr.get("z", -1.0)))
    shaft = pr.get("d", 0.045) * H
    tip_l = pr.get("tip", 0.16) * H
    reach = pr.get("reach", 0.42)
    a, b = p0 - d * 0.30, p0 + d * reach
    wood = core.principled(ctx, "pointer_wood", pr.get("color", "#8A5A34"), 0.55, coat=0.1)
    grp = _detail(ctx, pr, "pointer", 1200)
    rod = core.curve("pointer_rod", [a, (a + b) / 2, b], [1, 1, 1], shaft / 2, wood, order=2)
    ctx.add(rod, grp, ctx.objs["arm+1"], kind="free")
    iron = core.principled(ctx, "pointer_tip", pr.get("tip_color", "#8A929C"), 0.32, metal=0.5)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=shaft * 1.05, radius2=0.004, depth=tip_l)
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
