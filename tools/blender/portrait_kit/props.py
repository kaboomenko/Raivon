"""Props, personal gear and creatures (§7.5 steps 7 and 9), placed on their parents by ray casts — era 1's props
column of §7.6: the spoon, the millstone amulet on its cord and the sleeve chevrons (Bram); the leaf badge and the
bandage roll on the satchel strap (Lira); the glasses with nose pads and the pointer (Vega: held by the near hand,
hand-free dropped); the wrench in the apron pocket and the pencil behind the ear (Olm); the raven and the bow tip
(Vik); the hourglass on a chain to a button (Kort); the spyglass (Seir: in the near hand, hand-free on a strap) and
the earring ring; Frey's stud and tower badge; Irma's gauntlet (on the near hand at the collar, hand-free tucked
under the strap); Hawk's silk scarf and wings badge; Vance's chess queen (pinched at the chin, hand-free a pendant),
brooch and hairpin; Rai's staff and banner with the game's white eagle. Hands: body.hand.

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
         "glasses": glasses, "pointer": pointer, "hourglass": hourglass, "wrench": wrench, "pencil": pencil,
         "raven": raven, "bow": bow, "spyglass": spyglass, "earring": earring, "badge_relief": badge_relief,
         "scarf": scarf, "queen": queen, "brooch": brooch, "hairpin": hairpin, "banner": banner,
         "gauntlet": gauntlet}[pr["kind"]](ctx, pr)
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
    held = bool(pr.get("hand")) and ctx.hands
    if pr.get("hand") and not ctx.hands and pr.get("free") == "none":
        return      # the hand-free fallback drops the pointer (P1's Vega)
    if held:
        # the near hand holds its back end in front of the chest (§7.6 "ближняя кисть на древке"): the rod crosses
        # the chest to the right of the frame, past the far arm; kept clear of the costume along its whole length
        gx, gz = pr.get("grip", (-0.12, -1.0))
        h, nn, _ = core.ray_any(ctx.outer, (gx * k, -2.0, gz), (0, 1, 0))
        g = (h + nn * 0.09) if h is not None else Vector((gx * k, -0.6, gz))
        a, b = g - d * pr.get("back", 0.08), g + d * pr.get("reach_hand", 0.95)
        clr = shaft / 2 + pr.get("clear", 0.03)
        push = 0.0
        for i in range(21):
            q = a.lerp(b, i / 20)
            hh, _, _ = core.ray_any(ctx.outer, (q.x, -2.0, q.z), (0, 1, 0))
            if hh is not None:
                push = max(push, q.y - (hh.y - clr))
        a.y -= push
        b.y -= push
        g.y -= push
    arm = ctx.objs["arm+1"]
    wood = core.principled(ctx, "pointer_wood", pr.get("color", "#8A5A34"), 0.55, coat=0.1)
    grp = _detail(ctx, pr, "pointer", 1200)
    rod = core.curve("pointer_rod", [a, (a + b) / 2, b], [1, 1, 1], shaft / 2, wood, order=2)
    ctx.add(rod, grp, arm, kind="free" if held else "embed")   # hand-free: clamped in the arm (its back half inside)
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
    if held:
        from . import body
        body.hand(ctx, dict(pr["hand"], target=g, axis=d, radius=shaft / 2))
        return
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


# ------------------------------------------------------------------ P2 props
def _chain(ctx, name, a, b, sag, m, link=0.022, parent=None, grp="metal", wire=0.0045):
    """A chain of small alternating links from a to b, sagging by `sag` in the middle."""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    n = max(4, int(L / link))
    pts = []
    free = max(1, n // 6)
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t) + Vector((0, -0.004, -sag * 4 * t * (1 - t)))
        # the chain lies on the costume: each link cast onto what is under it
        h, nn, _ = core.ray_any(ctx.outer, (p.x, -2.0, p.z), (0, 1, 0))
        if h is not None and 0 < i < n - free:      # (the last links hang free to the end ring)
            p = h + nn * (wire + 0.004)
        pts.append(p)
    k0 = n - free - 1                                # straight from the last link on the costume to the end
    if k0 > 0:
        for i in range(k0 + 1, n):
            f = (i - k0) / (n - k0)
            pts[i] = pts[k0].lerp(pts[n], f)
    for i in range(n):
        p0, p1 = pts[i], pts[i + 1]
        c = (p0 + p1) / 2
        d = (p1 - p0).normalized()
        side = d.cross(Vector((0, -1, 0)))
        if side.length < 1e-6:
            side = Vector((1, 0, 0))
        side.normalize()
        nrm = side if i % 2 else d.cross(side).normalized()
        lk = core.torus("%s_link%d" % (name, i), c, link * 0.45, wire, m, nrm=nrm, seg=12, rseg=6)
        lk.scale = (1.0, 1.0, 1.0)
        # each link hangs in the one before it (the first on the button / the host)
        ctx.add(lk, grp, parent if i == 0 else prev, kind="embed")
        prev = lk
    return pts


def hourglass(ctx, pr):
    """Kort's hourglass on a chain (§7.6: 0.22 H, bronze, amber sand, the top half full; the chain to a button):
    two bronze end plates and three posts round two glass bulbs (tinted, see-through), amber sand — a heap in the
    bottom bulb, the top bulb half full — hanging against the coat from a short chain that runs up to a button."""
    k = ctx.shoulder_k
    hgt = pr.get("h", 0.22) * H
    x, z = pr.get("at", (-0.22, -1.12))
    h, nrm, par = core.ray_any(ctx.outer, (x * k, -2.0, z), (0, 1, 0))
    if h is None:
        return
    up = Vector((0, 0, 1))
    r = hgt * 0.30
    c = h + nrm * (r + 0.012)
    bronze = core.principled(ctx, "bronze", pr.get("color", "#B0803A"), rough=0.32, metal=0.55)
    glass = core.principled(ctx, "hg_glass", "#E8F0F4", rough=0.05, coat=0.5, spec=0.8)
    b = glass.node_tree.nodes["Principled BSDF"]
    b.inputs["Alpha"].default_value = 0.35
    sand = core.principled(ctx, "sand", pr.get("sand", "#E8A33A"), rough=0.7)
    grp = _detail(ctx, pr, "hourglass", 500)
    for s_ in (-1, 1):
        pl = core.cylinder("hg_plate%+d" % s_, c + up * s_ * hgt * 0.46, r * 1.05, hgt * 0.08, bronze, nrm=up, bev=0.006)
        ctx.add(pl, grp, par, kind="free")
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.5
        off = Vector((math.cos(a), math.sin(a), 0)) * r * 0.85
        po = core.cylinder("hg_post%d" % i, c + off, 0.009, hgt * 0.86, bronze, nrm=up, verts=12)
        ctx.add(po, grp, par, kind="free")
    for s_ in (-1, 1):
        bulb = core.uvsphere("hg_bulb%+d" % s_, c + up * s_ * hgt * 0.20, (r * 0.72, r * 0.72, hgt * 0.24), glass, 24, 12)
        ctx.add(bulb, grp, par, kind="free")
    top_sand = core.uvsphere("hg_sand_top", c + up * hgt * 0.13, (r * 0.58, r * 0.58, hgt * 0.10), sand, 20, 10)
    ctx.add(top_sand, grp, par, kind="free")
    heap = core.uvsphere("hg_sand_low", c - up * hgt * 0.30, (r * 0.62, r * 0.62, hgt * 0.10), sand, 20, 10)
    ctx.add(heap, grp, par, kind="free")
    stream = core.cylinder("hg_stream", c - up * hgt * 0.08, 0.004, hgt * 0.36, sand, nrm=up, verts=8)
    ctx.add(stream, grp, par, kind="free")
    # the hourglass rests on the coat (its back touches the surface): one contact part for the whole object
    ctx.parts[-1].kind = "free"
    ring_top = c + up * (hgt * 0.5 + 0.02)
    ring = core.torus("hg_ring", ring_top, 0.018, 0.005, bronze, nrm=Vector((1, 0, 0)), seg=16, rseg=6)
    ctx.add(ring, grp, par, kind="free")
    btn = ctx.L.get(pr.get("button", "button_0"))
    if btn is not None:
        top = btn[0]
        _chain(ctx, "hg_chain", top, ring_top + Vector((0, 0, 0.012)), pr.get("sag", 0.05), bronze,
               parent=par, grp=grp)
    # the contact test: the hourglass touches the coat
    ctx.add(core.uvsphere("hg_touch", h + nrm * 0.006, (r * 0.4, r * 0.4, 0.006), bronze, 8, 4), grp, par,
            kind="surface")


def wrench(ctx, pr):
    """Olm's wrench in his apron pocket (§7.6: handle 0.7 H, jaws 0.22 H by the far side of the neck above the
    shoulder line): a flat bevelled bar from the pocket up past the far shoulder, an open-end head (a C ring) at the
    top; iron (era 1)."""
    k = ctx.shoulder_k
    pocket = ctx.L.get(pr.get("pocket", "pocket"))
    if pocket is not None:
        a = Vector((pocket[0].x, 0.0, pocket[0].z - 0.05))
    else:
        a = Vector((pr.get("x0", 0.14) * k, 0.0, pr.get("z0", -1.10)))
    ln = pr.get("len", 0.70) * H
    ang = math.radians(pr.get("ang", 18))          # leaning out from the vertical, toward the far side
    d = Vector((math.sin(ang), pr.get("dy", -0.05), math.cos(ang))).normalized()
    h, nn, par = core.ray_any(ctx.outer, (a.x, -2.0, a.z), (0, 1, 0))
    a = h + nn * 0.02 if h is not None else a
    b = a + d * ln
    b.y = min(b.y, a.y + pr.get("top_dy", 0.0))
    iron = core.principled(ctx, "wrench", pr.get("color", "#9AA4B0"), rough=0.35, metal=0.55)
    grp = _detail(ctx, pr, "wrench", 1200)
    w, t = pr.get("w", 0.055), pr.get("t", 0.026)
    mid = (a + b) / 2
    bar = core.box("wrench_bar", mid, (w, t, (b - a).length), iron, bev=0.010, segs=3)
    bar.rotation_mode = "QUATERNION"
    bar.rotation_quaternion = core.frame_quat(b - a, nn if h is not None else Vector((0, -1, 0)))
    bar.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(b - a)
    ctx.add(bar, grp, par, kind="surface")
    jaw_r = pr.get("jaw", 0.22) * H / 2
    c = b + d * jaw_r * 0.8
    # the C ring: a torus with its top cut away (the open end), facing the camera
    bm = bmesh.new()
    segs, rseg = 36, 10
    rr = jaw_r * 0.62
    tube = jaw_r * 0.38
    gap = math.radians(pr.get("gap", 70))
    ring = []
    for i in range(segs + 1):
        aa = gap / 2 + (2 * math.pi - gap) * i / segs
        row = []
        for j in range(rseg):
            bb = 2 * math.pi * j / rseg
            row.append(bm.verts.new(((rr + tube * math.cos(bb)) * math.sin(aa), tube * 0.55 * math.sin(bb),
                                     (rr + tube * math.cos(bb)) * math.cos(aa))))
        ring.append(row)
    for i in range(segs):
        for j in range(rseg):
            bm.faces.new((ring[i][j], ring[i + 1][j], ring[i + 1][(j + 1) % rseg], ring[i][(j + 1) % rseg]))
    for row in (ring[0], ring[-1]):
        bm.faces.new(row)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    head = core.mesh_obj("wrench_jaws", bm)
    head.location = c
    head.rotation_mode = "QUATERNION"
    head.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    core.finish(head, iron, sub=1)
    ctx.add(head, grp, bar, kind="embed")
    ctx.sig_objs += [bar, head]
    ctx.L["wrench_top"] = c


def pencil(ctx, pr):
    """A pencil behind the near ear (Olm, §7.6 "карандаш за ухом 0.04 H"): a hexagonal stick 0.04 H thick resting in
    the crease between the ear and the head, a sharpened wooden tip with graphite poking forward over the ear."""
    head = ctx.objs["head"]
    ear = ctx.L["ear_near"][0]
    if ear is None:
        return
    ln = pr.get("len", 0.26) * H
    r = pr.get("d", 0.04) * H / 2
    c = ear + Vector((-0.035, 0.025, 0.06))
    d = Vector(pr.get("dir", (0.25, -0.92, -0.30))).normalized()
    body_m = core.principled(ctx, "pencil", pr.get("color", "#C9A24A"), rough=0.45, coat=0.2)
    wood = core.principled(ctx, "pencil_wood", pr.get("wood", "#E8DCC0"), rough=0.6)
    lead = core.principled(ctx, "pencil_lead", "#3A3A42", rough=0.4)
    grp = _detail(ctx, pr, "pencil", 60)
    st = core.cylinder("pencil", c - d * ln * 0.1, r, ln, body_m, nrm=d, verts=6, bev=0.003)
    ctx.add(st, grp, head, kind="surface", head=True)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=r, radius2=r * 0.25, depth=ln * 0.18)
    tip = core.mesh_obj("pencil_tip", bm)
    tip.location = c - d * ln * 0.1 + d * (ln * 0.5 + ln * 0.09)
    core.align_z(tip, d)
    core.finish(tip, wood)
    ctx.add(tip, grp, st, kind="embed", head=True)
    pt = core.uvsphere("pencil_lead", c - d * ln * 0.1 + d * (ln * 0.5 + ln * 0.18), (r * 0.28, r * 0.28, r * 0.5), lead,
                       8, 6)
    core.align_z(pt, d)
    ctx.add(pt, grp, tip, kind="embed", head=True)


def _on_outer(ctx, x, z, k=True):
    """(hit, normal, object) of a front ray onto the costume at (x in shoulder units, z)."""
    return core.ray_any(ctx.outer, ((x * ctx.shoulder_k) if k else x, -2.0, z), (0, 1, 0))


def _lathe(name, profile, m, seg=32, axis=Vector((0, 0, 1)), base=Vector((0, 0, 0))):
    """A body of revolution: profile [(r, z)] bottom to top, revolved about `axis` through `base`."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
                      for i in range(seg)])
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = core.mesh_obj(name, bm)
    o.location = base
    core.align_z(o, axis)
    return core.finish(o, m)


# ------------------------------------------------------------------ the raven (Vik)
def raven(ctx, pr):
    """Vik's raven on the near shoulder (§7.6: body 0.55 H, head with beak 0.12 H, a fanned tail, #343A52 with a
    #5A6FA0 sheen, a yellow #E8C040 iris with a catchlight, claws cast onto the shoulder, looking at the camera,
    >= 0.06 H clear of the cheek): a metaball body (chest, belly, back, neck, head), two folded wings of broad
    feather clumps, a tail fan of five clumps, a hooked beak, legs and three-toed claws ray-cast onto what it stands
    on. Built in body space, facing the camera."""
    k = ctx.shoulder_k
    size = pr.get("size", 0.55) * H
    cam = core.world_dir(ctx, (0.0, -1.0, 0.0))          # toward the camera, body space
    right = core.world_dir(ctx, (1.0, 0.0, 0.0))
    up = Vector((0, 0, 1))
    x = pr.get("x", -0.60) * k
    y = pr.get("y", 0.10)
    h, nn, perch = core.ray_any(ctx.outer, (x, y, 1.5), (0, 0, -1))
    if h is None:
        return
    feet = h
    face = (cam * math.cos(math.radians(pr.get("turn", 25))) + right * math.sin(math.radians(pr.get("turn", 25)))).normalized()
    side = up.cross(face).normalized()
    s = size / 0.55
    el = []
    lean = math.radians(pr.get("lean", 12))
    axis = (up * math.cos(lean) - face * math.sin(lean) * -1.0).normalized()

    def P(f, u, sd=0.0):
        return feet + face * f * s + up * u * s + side * sd * s
    # body: chest (forward), belly, back, rump
    el += [dict(co=P(0.05, 0.20), half=(0.12 * s, 0.12 * s, 0.16 * s), stiff=2.0, rot=core.frame_quat(axis, face)),
           dict(co=P(0.0, 0.12), half=(0.11 * s, 0.10 * s, 0.12 * s), stiff=2.0, rot=core.frame_quat(axis, face)),
           dict(co=P(-0.06, 0.24), half=(0.11 * s, 0.09 * s, 0.15 * s), stiff=2.0, rot=core.frame_quat(axis, face)),
           dict(co=P(0.03, 0.35), half=0.068 * s, stiff=2.2),                        # neck
           dict(co=P(0.06, 0.45), half=(0.088 * s, 0.092 * s, 0.088 * s), stiff=2.4)]  # head
    # folded wings: three broad feather clumps a side from the shoulder of the wing down and back past the rump
    for sd in (-1, 1):
        for j, (f0, u0, u1, ln) in enumerate(((0.02, 0.33, 0.06, 1.0), (-0.02, 0.30, 0.02, 1.15), (-0.06, 0.27, -0.02, 1.25))):
            a = P(f0, u0, sd * 0.10)
            b = P(f0 - 0.08 * ln, (u0 + u1) / 2, sd * 0.115)
            c = P(f0 - 0.17 * ln, u1 - 0.04 * ln, sd * 0.07)
            nrm = side * sd
            el += core.clump([a, b, c], [nrm, nrm, nrm], 0.075 * s, 0.05 * s, 0.03 * s, n=12, lift=0.0, taper_at=0.55,
                             tip=0.35, stiff=2.6, flat=0.8)
    # the tail fan: five clumps from the rump, down and back, spread
    for j in range(5):
        f_ = (j - 2) / 2
        a = P(-0.10, 0.08, f_ * 0.03)
        c = P(-0.26, -0.20, f_ * 0.11)
        el += core.clump([a, (a + c) / 2, c], [face, face, face], 0.045 * s, 0.05 * s, 0.022 * s, n=10, lift=0.0,
                         taper_at=0.7, tip=0.7, stiff=2.6, flat=0.8)
    mat = core.principled(ctx, "raven", pr.get("color", "#343A52"), rough=0.45, coat=0.25, sheen=0.3)
    nt = mat.node_tree
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.2
    rim = core.node_math(nt, "POWER", lw.outputs["Facing"], 3.0)
    nt.links.new(core.node_mix(nt, rim, pr.get("color", "#343A52"), pr.get("sheen", "#5A6FA0")),
                 nt.nodes["Principled BSDF"].inputs["Base Color"])
    body = core.mb_mesh(ctx, "Raven", el, 0.010, mat, smooth_iter=3, name="raven")
    grp = _detail(ctx, pr, "raven", 4000)
    ctx.add(body, grp, perch, kind="surface")
    ctx.sig_objs.append(body)
    # the beak: a hooked cone from the head toward the camera
    beak_m = core.principled(ctx, "raven_beak", pr.get("beak", "#3A3C46"), rough=0.35, coat=0.3)
    hc = P(0.06, 0.45)
    bdir = (face + up * -0.15).normalized()
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.042 * s, radius2=0.005, depth=0.14 * s)
    bk = core.mesh_obj("raven_beak", bm)
    bk.location = hc + bdir * (0.075 * s + 0.06 * s)
    core.align_z(bk, bdir)
    bk.scale = (1.0, 0.8, 1.0)
    core.bevel(bk, 0.004, 2)
    core.finish(bk, beak_m)
    ctx.add(bk, grp, body, kind="embed")
    # the eyes: yellow iris, dark pupil, a catchlight — on both sides of the head, the near one toward the camera
    iris_m = core.principled(ctx, "raven_eye", pr.get("eye", "#E8C040"), rough=0.2, coat=0.6)
    pup_m = core.principled(ctx, "raven_pupil", "#1E1A24", rough=0.2, coat=0.6)
    catch = core.emit_mat(ctx, "catch", "#ffffff", 6.0)
    for sd in (-1, 1):
        d = (face * 0.55 + side * sd * 0.8 + up * 0.15).normalized()
        hh, nh = core.ray(body, hc + d * 0.5, -d)
        if hh is None:
            continue
        ey = core.uvsphere("raven_eye%+d" % sd, hh + nh * 0.004, (0.027 * s, 0.027 * s, 0.014 * s), iris_m, 16, 8)
        core.align_z(ey, nh)
        ctx.add(ey, grp, body, kind="embed")
        pp = core.uvsphere("raven_pupil%+d" % sd, hh + nh * 0.014 + (cam - nh * cam.dot(nh)) * 0.006,
                           (0.013 * s, 0.013 * s, 0.006 * s), pup_m, 12, 6)
        core.align_z(pp, nh)
        ctx.add(pp, grp, ey, kind="embed")
        ct = core.uvsphere("raven_catch%+d" % sd, hh + nh * 0.020 + up * 0.009 * s - side * sd * 0.004,
                           (0.006 * s, 0.006 * s, 0.002), catch, 8, 4)
        ct.visible_shadow = False
        ctx.add(ct, "catch", ey, kind="embed")
    # legs and claws: two short legs, three toes each cast onto the perch
    leg_m = core.principled(ctx, "raven_leg", pr.get("leg", "#3A3C46"), rough=0.5)
    for sd in (-1, 1):
        top = P(0.02, 0.06, sd * 0.045)
        hf, nf, pobj = core.ray_any(ctx.outer, top + up * 0.02, (0, 0, -1))
        if hf is None:
            continue
        leg = core.curve("raven_leg%+d" % sd, [top, hf + nf * 0.012], [1.0, 0.9], 0.012 * s, leg_m, order=2)
        ctx.add(leg, grp, body, kind="embed")
        for j, a in enumerate((-35, 0, 35, 180)):
            dd = (Matrix.Rotation(math.radians(a), 3, nf) @ face).normalized()
            tip0 = hf + dd * 0.05 * s
            ht, nt_, _ = core.ray_any(ctx.outer, tip0 + nf * 0.1, -nf)
            if ht is None:
                continue
            toe = core.curve("raven_toe%+d_%d" % (sd, j), [hf + nf * 0.01, (hf + ht) / 2 + nf * 0.016, ht + nt_ * 0.006],
                             [1.0, 0.9, 0.5], 0.009 * s, leg_m, order=3)
            ctx.add(toe, grp, pobj, kind="surface")
    ctx.L["raven_head"] = hc


# ------------------------------------------------------------------ bow tip (Vik)
def bow(ctx, pr):
    """The tip of a bow slung on the back (Vik, §7.6: 0.6 H of it behind the far shoulder): a tapering wooden limb
    with a recurved tip rising behind the far shoulder, its string running down behind the shoulder."""
    k = ctx.shoulder_k
    wood = core.principled(ctx, "bow", pr.get("color", "#6B4A2A"), rough=0.5, coat=0.2)
    string = core.principled(ctx, "bow_string", pr.get("string", "#D8CCAA"), rough=0.6)
    b0 = Vector((pr.get("x0", 0.40) * k, pr.get("y", 0.30), pr.get("z0", -0.95)))
    ln = pr.get("len", 0.6) * H
    lean = math.radians(pr.get("lean", 20))
    d = Vector((math.sin(lean), 0.05, math.cos(lean))).normalized()
    side = d.cross(Vector((0, -1, 0))).normalized()
    pts, rad = [], []
    n = 9
    for i in range(n):
        t = i / (n - 1)
        bend = 0.10 * t * t
        p = b0 + d * (ln * 1.25 * t) - side * bend * 0.6
        if t > 0.82:                    # the recurve: the tip flicks back
            p += side * (t - 0.82) * 0.5
        pts.append(p)
        rad.append(1.0 - 0.55 * t)
    limb = core.curve("bow_limb", pts, rad, pr.get("r", 0.024), wood)
    grp = _detail(ctx, pr, "bow", 600)
    ctx.add(limb, grp, ctx.objs["torso"], kind="free")
    tip = pts[-1]
    st = core.curve("bow_string", [tip, b0 + d * 0.05 + side * 0.18], [1.0, 1.0], 0.005, string, order=2)
    ctx.add(st, grp, limb, kind="free")
    nock = core.uvsphere("bow_nock", tip, (0.02, 0.02, 0.02), wood, 12, 6)
    ctx.add(nock, grp, limb, kind="free")


# ------------------------------------------------------------------ spyglass (Seir)
def spyglass(ctx, pr):
    """Seir's brass spyglass (§7.6: 0.8 H long, 0.11 H across): three telescoping brass sections with rims, a
    leather grip band and a dark eyepiece, resting on the near shoulder and rising behind the head at `ang` deg
    (backward-up: on the picture up and to the left behind the head — his near-shoulder diagonal). Held by the near
    hand (pr["hand"]: body.hand) or, hand-free, slung on a strap across the chest (§7.5 fallback)."""
    k = ctx.shoulder_k
    ln = pr.get("len", 0.8) * H
    r = pr.get("d", 0.11) * H / 2
    ang = math.radians(pr.get("ang", 50))
    held = bool(pr.get("hand")) and ctx.hands
    dw = pr.get("dir_world_hand", pr.get("dir_world")) if held else pr.get("dir_world")
    if dw:
        back = core.world_dir(ctx, dw)                          # given in picture terms (x right, y away, z up)
        back = Vector((back.x, back.y, 0.0)).normalized()
    else:
        back = Vector(pr.get("dir_xy", (-0.35, 1.0, 0.0))).normalized()
    d = (back * math.cos(ang) + Vector((0, 0, math.sin(ang)))).normalized()
    sx, sz = pr.get("rest_hand", pr.get("rest", (-0.62, None))) if held else pr.get("rest", (-0.62, None))
    h, nn, par = core.ray_any(ctx.outer, (sx * k, pr.get("rest_y", 0.0), 1.5), (0, 0, -1))
    if h is None:
        return
    rest = h + nn * (r + 0.01)
    below = pr.get("below_hand", pr.get("below", 0.30)) if (pr.get("hand") and ctx.hands) else pr.get("below", 0.30)
    a = rest - d * ln * below
    brass = core.principled(ctx, "spyglass", pr.get("color", "#E0AD45"), rough=0.3, metal=0.55)
    leather = core.principled(ctx, "spy_leather", pr.get("leather", "#6B4A2A"), rough=0.55, coat=0.1)
    dark = core.principled(ctx, "spy_dark", "#3A3C46", rough=0.4)
    grp = _detail(ctx, pr, "spyglass", 2000)
    segs = [(0.0, 0.45, r), (0.43, 0.75, r * 0.86), (0.73, 1.0, r * 0.72)]
    objs = []
    for i, (t0, t1, rr) in enumerate(segs):
        c = a + d * ln * (t0 + t1) / 2
        o = core.cylinder("spy_tube%d" % i, c, rr, ln * (t1 - t0), brass, nrm=d, verts=32, bev=0.004)
        ctx.add(o, grp, par, kind="free")
        objs.append(o)
        rim = core.torus("spy_rim%d" % i, a + d * ln * t1, rr * 1.02, 0.008, brass, nrm=d, seg=32, rseg=8)
        ctx.add(rim, grp, o, kind="free")
    band = core.cylinder("spy_grip", a + d * ln * 0.18, r * 1.04, ln * 0.18, leather, nrm=d, verts=32, bev=0.004)
    ctx.add(band, grp, objs[0], kind="free")
    obj_rim = core.torus("spy_objective", a, r * 1.05, 0.012, brass, nrm=d, seg=32, rseg=8)
    ctx.add(obj_rim, grp, objs[0], kind="free")
    eye = core.cylinder("spy_eyepiece", a + d * (ln + 0.02), r * 0.55, 0.04, dark, nrm=d, verts=24, bev=0.006)
    ctx.add(eye, grp, objs[-1], kind="free")
    ctx.sig_objs += objs
    # the contact: the tube rests on the shoulder
    touch = core.uvsphere("spy_touch", h + nn * 0.004, (r * 0.4, r * 0.4, 0.004), brass, 8, 4)
    ctx.add(touch, grp, par, kind="surface")
    ctx.L["spyglass"] = (a, d, ln, r)
    if pr.get("hand") and ctx.hands:
        from . import body
        grip_at = a + d * ln * pr.get("grip_t", 0.12)
        body.hand(ctx, dict(pr["hand"], target=grip_at, axis=d, radius=r * 1.04))
    elif pr.get("strap", True):
        # hand-free: a strap from the tube's middle over the near shoulder and across the chest to the far hip
        st_col = pr.get("strap_color", "#6B4A2A")
        strap_ly = dict(kind="strap", id="spy_strap", color=st_col, w=0.06, over_shoulder=True,
                        **{"from": (pr.get("strap_from", (-0.42, -0.70))), "to": pr.get("strap_to", (0.55, -1.6))})
        from . import garments
        garments.strap(ctx, strap_ly, "spy_strap")


# ------------------------------------------------------------------ earrings (Seir, Frey)
def earring(ctx, pr):
    """An earring on the near ear's lobe: "ring" (Seir: gold, 0.10 H across, a 0.03 H tube) or "stud" (Frey)."""
    tag = pr.get("ear", "near")
    side = -1 if tag == "near" else 1
    lb = ctx.L.get("lobe_" + tag)
    if lb is None:
        return
    lobe, lr, ear_o = lb
    m = core.principled(ctx, "earring", pr.get("color", "#E8B23A"), rough=0.28, metal=0.55)
    grp = _detail(ctx, pr, "earring", 60)
    if pr.get("style", "ring") == "ring":
        # a ring through the lobe: hanging from its bottom
        R = pr.get("d", 0.10) * H / 2
        t = pr.get("tube", 0.03) * H / 2
        o = core.torus("earring", lobe + Vector((side * lr * 0.3, -0.01, -lr * 0.6 - R * 0.8)), R, t, m,
                       nrm=Vector((1.0, -0.35, 0.0)).normalized(), seg=32, rseg=10)
    else:
        # a stud on the lobe's outer face, toward the camera
        o = core.uvsphere("earring", lobe + Vector((side * lr * 0.95, -lr * 0.35, 0.0)), (0.026, 0.026, 0.026), m, 16, 8)
    ctx.add(o, grp, ear_o, kind="surface", head=True)


# ------------------------------------------------------------------ relief badges (Frey's tower, Hawk's wings)
def badge_relief(ctx, pr):
    """A relief badge on the chest: "tower" (Frey, §7.6: silver, 0.18 H — a crenellated tower with a door on a round
    plate) or "wings" (Hawk: gold wings 0.24 H round a sky hex)."""
    x, z = pr.get("at", (-0.25, -0.95))
    h, nn, par = _on_outer(ctx, x, z)
    if h is None:
        return
    size = pr.get("size", 0.18) * H
    q = Vector((0, 0, 1)).rotation_difference(nn)
    up_ = (Vector((0, 0, 1)) - nn * nn.z).normalized()
    rt = nn.cross(up_).normalized() * -1
    metal = core.principled(ctx, pr.get("kind_mat", "badge_metal"), pr.get("color", "#C8CCD4"), rough=0.3, metal=0.55)
    grp = _detail(ctx, pr, pr.get("detail", "badge"), 500)
    base = h + nn * 0.004

    def at(u, v, w=0.0):
        return base + rt * u * size + up_ * v * size + nn * w

    if pr.get("style", "tower") == "tower":
        plate = core.cylinder("badge_plate", at(0, 0, 0.004), size * 0.52, 0.02, metal, nrm=nn, verts=40, bev=0.006)
        ctx.add(plate, grp, par, kind="surface")
        dark = core.principled(ctx, "badge_dark", pr.get("dark", "#3B5A44"), rough=0.4, coat=0.3)
        inner = core.cylinder("badge_enamel", at(0, 0, 0.014), size * 0.43, 0.012, dark, nrm=nn, verts=40, bev=0.003)
        ctx.add(inner, grp, plate, kind="embed")
        tw = core.box("badge_tower", at(0, -0.04, 0.026), (size * 0.34, size * 0.50, 0.026), metal, bev=0.005)
        tw.rotation_mode = "QUATERNION"
        tw.rotation_quaternion = core.frame_quat(up_, nn)
        tw.rotation_quaternion = (Matrix((rt, up_, nn)).transposed().to_quaternion())
        ctx.add(tw, grp, plate, kind="embed")
        for j in (-1, 0, 1):
            mr = core.box("badge_merlon", at(j * 0.125, 0.26, 0.026), (size * 0.085, size * 0.10, 0.026), metal, bev=0.004)
            mr.rotation_mode = "QUATERNION"
            mr.rotation_quaternion = tw.rotation_quaternion
            ctx.add(mr, grp, plate, kind="embed")
        door = core.box("badge_door", at(0, -0.18, 0.040), (size * 0.11, size * 0.16, 0.016), dark, bev=0.003)
        door.rotation_mode = "QUATERNION"
        door.rotation_quaternion = tw.rotation_quaternion
        ctx.add(door, grp, plate, kind="embed")
    else:   # wings round a sky hex
        sky = core.principled(ctx, "badge_sky", pr.get("hex", "#6FA8DC"), rough=0.3, coat=0.4)
        hx = core.cylinder("badge_hex", at(0, 0, 0.012), size * 0.17, 0.024, sky, nrm=nn, verts=6, bev=0.004)
        ctx.add(hx, grp, par, kind="surface")
        rim = core.torus("badge_hex_rim", at(0, 0, 0.022), size * 0.17, 0.007, metal, nrm=nn, seg=6, rseg=6)
        ctx.add(rim, grp, hx, kind="embed")
        for sd in (-1, 1):
            for j in range(3):
                ln = size * (0.42 - 0.08 * j)
                a = at(sd * 0.14, 0.04 - 0.07 * j, 0.012)
                b = at(sd * (0.14 + ln / size), 0.12 - 0.05 * j, 0.012)
                f = core.curve("badge_feather%+d_%d" % (sd, j), [a, (a + b) / 2 + nn * 0.004, b], [1.0, 0.9, 0.35],
                               size * 0.055, metal, order=3)
                ctx.add(f, grp, par, kind="surface")
    ctx.L["badge"] = base


# ------------------------------------------------------------------ scarf (Hawk)
def scarf(ctx, pr):
    """Hawk's white silk scarf (§7.6: flying to the right in an S, 0.9 x 0.18 H): a soft roll round the neck and one
    long flat tail from the throat out to the right of the frame in an S, widening and thinning toward its end,
    smooth silk."""
    neck = ctx.objs["neck"]
    torso = ctx.objs["torso"]
    el = []
    zc = pr.get("z", -0.62)
    for i in range(30):
        a = 2 * math.pi * i / 30
        d = Vector((math.sin(a), -math.cos(a), 0))
        hh, nn = core.ray(neck, Vector((0, 0.07, zc)) + d * 2, -d)
        if hh is None:
            continue
        el.append(dict(co=hh + nn * 0.03, half=(0.06, 0.045, 0.055), stiff=2.2, rot=core.frame_quat(Vector((0, 0, 1)), nn)))
    h, nn, _ = core.ray_any([neck, torso], (0.03, -2.0, zc - 0.06), (0, 1, 0))
    knot = h + nn * 0.06 if h is not None else Vector((0, -0.32, zc - 0.06))
    el.append(dict(co=knot, half=(0.07, 0.05, 0.06), stiff=2.2))
    silk = core.principled(ctx, "scarf", pr.get("color", "#F6F6F2"), rough=0.45, sheen=0.5, coat=0.1)
    roll = core.mb_mesh(ctx, "ScarfRoll", el, 0.009, silk, smooth_iter=2, name="scarf_roll")
    grp = _detail(ctx, pr, "scarf", 3000)
    ctx.add(roll, grp, neck, kind="embed")
    right = core.world_dir(ctx, (1.0, 0.0, 0.0))
    cam = core.world_dir(ctx, (0.0, -1.0, 0.0))
    ln = pr.get("len", 0.9) * H
    w0, w1 = pr.get("w", (0.10, 0.19))
    n = 26
    pts, nrs, ws = [], [], []
    for i in range(n):
        t = i / (n - 1)
        # an S: out to the right, lifting and dipping once and a quarter, drooping toward its end
        p = knot + right * (ln * t) + Vector((0, 0, pr.get("rise", -0.10) * t - 0.08 * t * t
                                                 + 0.085 * math.sin(2 * math.pi * t * 1.25)))
        p += cam * (0.06 * math.sin(math.pi * t))
        pts.append(p)
        tw = math.radians(pr.get("twist", 50) * math.sin(math.pi * t * 1.5))
        nrs.append((cam * math.cos(tw) + Vector((0, 0, 1)) * math.sin(tw)).normalized())
        ws.append(w0 + (w1 - w0) * t ** 0.8)
    tail = core.ribbon_mesh("scarf_tail", pts, ws, normals=nrs)
    core.solidify(tail, 0.016, offset=0.0)
    core.finish(tail, silk, sub=2)
    ctx.add(tail, grp, roll, kind="free")
    ctx.sig_objs += [tail]


# ------------------------------------------------------------------ chess queen (Vance), brooch, hairpin
QUEEN = [(0.0, 0.0), (0.46, 0.0), (0.48, 0.05), (0.40, 0.09), (0.30, 0.12), (0.22, 0.20), (0.17, 0.42),
         (0.16, 0.60), (0.26, 0.64), (0.26, 0.68), (0.16, 0.71), (0.20, 0.80), (0.28, 0.90), (0.24, 0.94),
         (0.12, 0.95), (0.10, 0.98), (0.0, 1.0)]


def queen(ctx, pr):
    """The chess queen (Vance, §7.6: 0.30 H, dark wood in era 1): a turned piece — base, waist, collar, a crown of
    rounded points, a ball on top — pinched by the near hand at the chin (pr["hand"]) or, hand-free, as a pendant
    on a chain on the jabot (§7.5 fallback, a smaller piece)."""
    hgt = pr.get("h", 0.30) * H
    wood = core.principled(ctx, "queen", pr.get("color", "#5A3A26"), rough=0.35, coat=0.4)
    grp = _detail(ctx, pr, "queen", 1500)
    hold = bool(pr.get("hand")) and ctx.hands
    if hold:
        from . import rig
        m = rig.head_pose_matrix(ctx)
        chin = m @ ctx.L["chin"]
        base = chin + Vector(pr.get("offset", (-0.20, -0.10, -0.10)))
        axis = Vector(pr.get("axis", (0.0, 0.0, 1.0))).normalized()
        par = ctx.objs["torso"]
    else:
        jt = ctx.L.get("jabot_top")
        hgt *= pr.get("pendant_k", 0.6)
        x, z = pr.get("pendant_at", (0.0, -0.90))
        h, nn, par = _on_outer(ctx, x, z)
        if h is None:
            return
        base = h + nn * (hgt * 0.22 + 0.008) - Vector((0, 0, hgt * 0.5))
        axis = Vector((0, 0, 1))
    prof = [(r * hgt * 0.62, z * hgt) for r, z in QUEEN]
    q = _lathe("queen", prof, wood, seg=40, axis=axis, base=base)
    core.bevel(q, 0.003, 2)
    ctx.add(q, grp, par, kind="free")
    for i in range(6):
        a = 2 * math.pi * i / 6
        p = base + axis * hgt * 0.93 + (Vector((math.cos(a), math.sin(a), 0)) * hgt * 0.16)
        b = core.uvsphere("queen_point%d" % i, p, (hgt * 0.045, hgt * 0.045, hgt * 0.045), wood, 12, 6)
        ctx.add(b, grp, q, kind="free")
    top = core.uvsphere("queen_ball", base + axis * hgt * 1.04, (hgt * 0.07,) * 3, wood, 16, 8)
    ctx.add(top, grp, q, kind="free")
    ctx.sig_objs += [q, top]
    if hold:
        from . import body
        body.hand(ctx, dict(pr["hand"], target=base + axis * hgt * 0.06, axis=axis, radius=hgt * 0.14))
    else:
        silver = core.principled(ctx, "silver", "#C8CCD4", rough=0.3, metal=0.55)
        ring = core.torus("queen_loop", base + axis * hgt * 1.12, 0.014, 0.005, silver, nrm=Vector((1, 0, 0)), seg=12,
                          rseg=6)
        ctx.add(ring, grp, q, kind="free")
        for sd in (-1, 1):
            a = base + axis * hgt * 1.14
            b_ = Vector((sd * 0.16 * ctx.shoulder_k, a.y + 0.10, -0.64))
            h2, n2, _ = core.ray_any(ctx.outer, (b_.x, -2.0, b_.z), (0, 1, 0))
            if h2 is not None:
                b_ = h2 + n2 * 0.006
            _chain(ctx, "queen_chain%+d" % sd, a, b_, 0.0, silver, link=0.018, parent=par, grp=grp, wire=0.0035)
    ctx.L["queen"] = base


def brooch(ctx, pr):
    """A pearl brooch in silver (Vance, §7.6: 0.10 H, on the lace jabot): an oval silver frame and a pearl."""
    x, z = pr.get("at", (0.0, -0.70))
    h, nn, par = _on_outer(ctx, x, z)
    if h is None:
        return
    d = pr.get("d", 0.10) * H
    silver = core.principled(ctx, "silver", pr.get("color", "#C8CCD4"), rough=0.3, metal=0.55)
    pearl = core.principled(ctx, "pearl", "#F4F0EA", rough=0.25, coat=0.6, sheen=0.3)
    grp = _detail(ctx, pr, "brooch", 150)
    fr = core.torus("brooch_frame", h + nn * 0.012, d * 0.45, 0.01, silver, nrm=nn, seg=32, rseg=8)
    fr.scale = (1.0, 1.0, 1.0)
    ctx.add(fr, grp, par, kind="surface")
    pl = core.uvsphere("brooch_pearl", h + nn * 0.026, (d * 0.36, d * 0.36, d * 0.32), pearl, 24, 12)
    ctx.add(pl, grp, fr, kind="embed")


def hairpin(ctx, pr):
    """A silver pin with a pearl head through the bun (Vance)."""
    ax = ctx.L.get("bun_axis")
    if ax is None:
        return
    base, top = ax
    c = base.lerp(top, pr.get("t", 0.35))
    d = Vector(pr.get("dir", (-0.85, -0.2, 0.35))).normalized()
    silver = core.principled(ctx, "silver", "#C8CCD4", rough=0.3, metal=0.55)
    pearl = core.principled(ctx, "pearl", "#F4F0EA", rough=0.25, coat=0.6, sheen=0.3)
    grp = _detail(ctx, pr, "hairpin", 40)
    a, b = c - d * 0.10, c + d * 0.17
    pin = core.curve("hairpin", [a, b], [1.0, 1.0], 0.007, silver, order=2)
    ctx.add(pin, grp, ctx.objs.get("bun") or ctx.objs["head"], kind="embed", head=True)
    pl = core.uvsphere("hairpin_pearl", b, (0.026, 0.026, 0.026), pearl, 16, 8)
    ctx.add(pl, grp, pin, kind="embed", head=True)


# ------------------------------------------------------------------ banner (Rai)
EAGLE = [(0.0, 0.5), (0.07, 0.4), (0.12, 0.3), (0.5, 0.5), (0.4, 0.32), (0.49, 0.28), (0.36, 0.14), (0.44, 0.1),
         (0.15, -0.02), (0.22, -0.5), (0.0, -0.34), (-0.22, -0.5), (-0.15, -0.02), (-0.44, 0.1), (-0.36, 0.14),
         (-0.49, 0.28), (-0.4, 0.32), (-0.5, 0.5), (-0.12, 0.3), (-0.07, 0.4)]   # the game's white eagle (prop_assets)


def banner(ctx, pr):
    """Rai's staff and banner (§7.6: a blue cloth with our white eagle seen at the top right, never across the face;
    the finial a raivite crystal): a wooden staff rising behind the far shoulder, a crossbar at its top, the cloth
    hanging from it toward the far side with a soft wave, the white eagle on it (the game's emblem outline), a hex
    raivite crystal on top (emission <= 2.0, §7.4)."""
    k = ctx.shoulder_k
    wood = core.principled(ctx, "staff", pr.get("color", "#8A5A34"), rough=0.5, coat=0.15)
    cloth = core.principled(ctx, "banner", pr.get("cloth", "#2B5FD9"), rough=0.8, sheen=0.4)
    white = core.principled(ctx, "banner_eagle", "#F6F6F2", rough=0.7, sheen=0.3)
    grp = _detail(ctx, pr, "banner", 2500)
    right = core.world_dir(ctx, (1.0, 0.0, 0.0))
    cam = core.world_dir(ctx, (0.0, -1.0, 0.0))
    b0 = Vector((pr.get("x", 0.50) * k, pr.get("y", 0.32), -1.6))
    top = Vector((b0.x + pr.get("lean", 0.06), b0.y, pr.get("top", 0.80)))
    r = pr.get("r", 0.024)
    staff = core.curve("banner_staff", [b0, top], [1.0, 1.0], r, wood, order=2)
    ctx.add(staff, grp, ctx.objs["torso"], kind="free")
    bar_z = pr.get("bar_z", top.z - 0.06)
    bw = pr.get("w", 0.42)
    bh = pr.get("h", 0.62)
    a = Vector((top.x, top.y, bar_z))
    bar = core.curve("banner_bar", [a - right * 0.03, a + right * (bw + 0.03)], [1.0, 1.0], r * 0.7, wood, order=2)
    ctx.add(bar, grp, staff, kind="free")
    nu, nv = 14, 18
    bm = bmesh.new()
    grid = []
    for j in range(nv + 1):
        v = j / nv
        row = []
        for i in range(nu + 1):
            u = i / nu
            wave = 0.035 * math.sin(2 * math.pi * (u * 1.2 + v * 0.6)) * (0.4 + 0.6 * v)
            p = a + right * (bw * u) + cam * wave + Vector((0, 0, -bh * v))
            # a swallow-tail at the bottom: the middle cut up
            if j == nv:
                p += Vector((0, 0, 0.12 * (1 - abs(2 * u - 1))))
            row.append(bm.verts.new(p))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cl = core.mesh_obj("banner_cloth", bm)
    core.solidify(cl, 0.012, offset=0.0)
    core.finish(cl, cloth, sub=1)
    ctx.add(cl, grp, bar, kind="free")
    # the eagle: the emblem outline on the cloth's front, following its wave
    ew, eh = bw * 0.72, bh * 0.52
    cu, cv = 0.5, 0.42
    bm = bmesh.new()
    vs = []
    for u_, v_ in EAGLE:
        u = cu + u_ * ew / bw
        v = cv - v_ * eh / bh
        wave = 0.035 * math.sin(2 * math.pi * (u * 1.2 + v * 0.6)) * (0.4 + 0.6 * v)
        vs.append(bm.verts.new(a + right * (bw * u) + cam * (wave + 0.009) + Vector((0, 0, -bh * v))))
    bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    eg = core.mesh_obj("banner_eagle", bm)
    core.solidify(eg, 0.004, offset=0.0)
    core.finish(eg, white, smooth=False)
    ctx.add(eg, grp, cl, kind="free")
    gem = core.principled(ctx, "raivite", "#3A8DFF", rough=0.15, coat=0.6, emit="#3A8DFF", es=pr.get("emit", 1.5))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.05, radius2=0.0, depth=0.16)
    cr = core.mesh_obj("banner_crystal", bm)
    cr.location = top + Vector((0, 0, 0.08))
    core.bevel(cr, 0.004, 2)
    core.finish(cr, gem)
    ctx.add(cr, grp, staff, kind="free")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.05, radius2=0.0, depth=0.07)
    cr2 = core.mesh_obj("banner_crystal_low", bm)
    cr2.location = top - Vector((0, 0, 0.035))
    cr2.rotation_euler = (math.pi, 0, 0)
    core.finish(cr2, gem)
    ctx.add(cr2, grp, staff, kind="free")
    ctx.sig_objs += [cl, eg, staff]
    ctx.skyline_exempt = [staff, cl, eg, cr, cr2, bar]


# ------------------------------------------------------------------ gauntlet (Irma)
def gauntlet(ctx, pr):
    """Irma's gauntlet (§7.6: the near hand holds up the raised collar, a flared cuff 0.30 H with an orange piping;
    hand-free: the gauntlets tucked behind a strap, §7.5): with pr["hand"] a gloved hand (body.hand, grip "edge") at
    the collar and the flared cuff round its wrist; otherwise two gauntlets (cuff + flat glove) tucked under the chest
    strap, their fingers hanging out."""
    leather = core.principled(ctx, "gauntlet", pr.get("color", "#3A3C46"), rough=0.45, coat=0.25)
    orange = core.principled(ctx, "gauntlet_pipe", pr.get("piping", "#F08A24"), rough=0.45, coat=0.2)
    grp = _detail(ctx, pr, "gauntlet", 1500)
    if pr.get("hand") and ctx.hands:
        from . import body
        info = body.hand(ctx, dict(pr["hand"], glove=pr.get("color", "#3A3C46")))
        if info is None:
            return
        wrist, f = info["wrist"], info["f"]
        cuff_l = pr.get("cuff", 0.30) * H
        prof = [(0.092, 0.0), (0.10, cuff_l * 0.3), (0.13, cuff_l * 0.75), (0.15, cuff_l)]
        cf = _lathe("gauntlet_cuff", prof, leather, seg=32, axis=-f, base=wrist + f * 0.02)
        ctx.add(cf, grp, info["obj"], kind="free")
        pipe = core.torus("gauntlet_pipe", wrist + f * 0.02 - f * cuff_l, 0.15, 0.014, orange, nrm=f, seg=32, rseg=8)
        ctx.add(pipe, grp, cf, kind="free")
        ctx.sig_objs.append(cf)
        return
    strap = ctx.objs.get(pr.get("on", "strap"))
    pts = ctx.L.get(pr.get("on", "strap"))
    if strap is None or not pts:
        return
    for j, zt in enumerate(pr.get("z", (-0.95, -1.06))):
        p = min(pts, key=lambda q: abs(q.z - zt))
        h, nn, _ = core.ray_any([strap], (p.x, -2.0, p.z), (0, 1, 0))
        if h is None:
            continue
        down = Vector((0.12 * (1 if j else -1), 0, -1)).normalized()
        cuff_l = pr.get("cuff", 0.30) * H * 0.75
        prof = [(0.045, 0.0), (0.06, cuff_l * 0.5), (0.085, cuff_l)]
        c0 = h + nn * 0.05 - down * cuff_l * 0.55
        cf = _lathe("gauntlet_cuff%d" % j, prof, leather, seg=28, axis=-down, base=c0 + down * cuff_l)
        cf.scale = (1.0, 0.55, 1.0)
        ctx.add(cf, grp, strap, kind="free")
        pipe = core.torus("gauntlet_pipe%d" % j, c0, 0.085, 0.01, orange, nrm=-down, seg=28, rseg=8)
        pipe.scale = (1.0, 0.55, 1.0)
        ctx.add(pipe, grp, cf, kind="free")
        el = [dict(co=c0 + down * (cuff_l + 0.06), half=(0.07, 0.03, 0.08), stiff=2.4,
                   rot=core.frame_quat(down, nn))]
        for fi in range(3):
            fx = (fi - 1) * 0.04
            el.append(dict(co=c0 + down * (cuff_l + 0.15) + Vector((fx, 0, 0)), half=(0.022, 0.022, 0.05), stiff=2.6,
                           rot=core.frame_quat(down, nn)))
        gl = core.mb_mesh(ctx, "Glove%d" % j, el, 0.008, leather, smooth_iter=2, name="glove%d" % j)
        ctx.add(gl, grp, cf, kind="free")
        ctx.sig_objs.append(cf)
