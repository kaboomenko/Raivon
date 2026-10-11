"""Hair (§7.5 step 3): a thin metaball sheet over the scalp (sheet-solved radii) plus flattened "ribbon locks" laid
over the surface frame from the crown or the parting to the fringe and the nape; tips may leave the scalp (a fringe
over the forehead, a bob's ends). Locks whose root would lie inside a headgear are dropped and 6–10 "escape" locks
grow below its rim (hats come with P2; the kerchief keeps a fringe under its edge). Converted to a mesh, Smooth 2,
no Subsurf (§7.5). Material: object-Z gradient (+8 % L* on top) x AO crevice tint.

Styles (chars.py "hair": {"style": ...}):
  swept    — short hair, a fringe of broad locks swept to the far side, ears free (Bram);
  kerchief — only what shows under a kerchief: a fringe and the temples; the braid is built with the body
             (it lies on the near shoulder) by `build_braid` (Lira);
  bob      — an asymmetric bob: a side parting on the far side, the near side longer with a "chisel" point at the
             jaw, the ends turned in; an optional streak lock in its own colour (Vega).
"""
import math

from mathutils import Matrix, Vector

from . import core
from .core import H


def hairline_fn(table):
    def f(hit):
        az = abs(math.degrees(math.atan2(hit.x, -hit.y)))
        return core.lerp_table(table, az)
    return f


def _hair_mat(ctx, name, col, z0=0.1, z1=0.62):
    hr = ctx.ch["hair"]
    return core.hair_mat(ctx, name, col, z0, z1, dark=hr.get("dark"), light=hr.get("light"),
                         crevice=hr.get("crevice"))


def build_hair(ctx):
    st = ctx.ch["hair"]["style"]
    {"swept": _swept, "kerchief": _kerchief, "bob": _bob}[st](ctx)


def _finish_hair(ctx, el, col, name="hair", res=0.011, signature=False):
    mat = _hair_mat(ctx, "hair_" + name, col)
    o = core.mb_mesh(ctx, "Hair" + name, el, res, mat, smooth_iter=2, name=name)
    ctx.add(o, "hair", ctx.objs["head"], kind="embed", head=True)
    if signature:
        ctx.sig_objs.append(o)
    ctx.objs[name] = o
    return o


# ------------------------------------------------------------------ swept (Bram)
def _swept(ctx):
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.30), (30, 0.28), (60, 0.2), (80, 0.12), (100, 0.08), (140, -0.10), (180, -0.20)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.02)
    el = core.sheet_elems(samples, s, lambda h, n: (0.035 + 0.03 * core.smoothstep(0.1, 0.45, h.z))
                          * (0.5 + 0.5 * core.smoothstep(0.0, 0.08, h.z - hl(h))))
    crown = core.az_el(175, 72)
    # front: broad flattened locks sweeping toward the far side (+X), tips hanging over the forehead
    for az, w, sweep in [(-46, 0.075, 16), (-26, 0.085, 18), (-6, 0.09, 20), (14, 0.085, 18), (34, 0.078, 14),
                         (54, 0.07, 10)]:
        mid = core.az_el(az * 0.7 + 4, 60)
        tip_d = core.az_el(az + sweep, hr.get("fringe_el", 39))
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        hang = hit + nor * 0.045 + Vector((math.sin(math.radians(az + sweep)) * 0.05, -0.03, -0.03))
        el += core.ribbon_lock(head, [crown, mid, tip_d, hang], w * sx, w * 0.8 * sx, 0.05, n=14, lift=0.45,
                               free_tail=1)
    # sides and back: locks from the crown down to the hairline; short over the ears (ears stay free)
    for az, el_end, w in [(-76, 18, 0.07), (-98, 10, 0.07), (76, 20, 0.07), (98, 12, 0.07), (-125, 0, 0.08),
                          (125, 2, 0.08), (-152, -8, 0.085), (152, -6, 0.085), (180, -12, 0.085)]:
        el += core.ribbon_lock(head, [crown, core.az_el(az, (72 + el_end) / 2), core.az_el(az, el_end)], w * sx,
                               w * 0.75 * sx, 0.045, n=12, lift=0.4)
    # sideburns: short flat locks in front of the ears down to the beard line (no skin gap between hair and beard)
    if hr.get("sideburns"):
        for s_ in (-1, 1):
            az = s_ * 80
            el += core.ribbon_lock(head, [core.az_el(az, 22), core.az_el(s_ * 82, 0), core.az_el(s_ * 78, -14)],
                                   0.06 * sx, 0.055 * sx, 0.035, n=8, lift=0.3)
    _finish_hair(ctx, el, hr["color"])


# ------------------------------------------------------------------ under a kerchief (Lira)
def _kerchief(ctx):
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.28), (30, 0.26), (60, 0.18), (85, 0.06), (105, -0.02), (140, -0.14), (180, -0.22)])
    samples, s = core.surface_samples(head, 2000, lambda h, n, d: h.z > hl(h) + 0.015)
    el = core.sheet_elems(samples, s, lambda h, n: 0.028 * (0.5 + 0.5 * core.smoothstep(0.0, 0.06, h.z - hl(h))))
    fringe = hr.get("fringe", 0.08) * H
    # the fringe: 4 locks from under the kerchief edge, parted to the far side, tips over the forehead
    for az, w, sweep in [(-34, 0.07, -10), (-14, 0.075, 6), (6, 0.072, 12), (26, 0.065, 14)]:
        root = core.az_el(az, 48)
        tip_d = core.az_el(az + sweep, 35)
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        hang = hit + nor * 0.03 + Vector((math.sin(math.radians(az + sweep)) * 0.02, -0.02, -fringe * 0.5))
        el += core.ribbon_lock(head, [root, tip_d, hang], w * sx, w * 0.7 * sx, 0.042, n=11, lift=0.45, free_tail=1)
    # temples: locks down in front of the ears, tucked behind them
    for s_ in (-1, 1):
        el += core.ribbon_lock(head, [core.az_el(s_ * 66, 40), core.az_el(s_ * 80, 14), core.az_el(s_ * 92, -4)],
                               0.07 * sx, 0.05 * sx, 0.04, n=10, lift=0.4)
    # nape: hair gathered toward the near side where the braid starts (the braid's root landmark)
    gather = core.az_el(-130, -18)
    for az in (-150, -175, 160):
        el += core.ribbon_lock(head, [core.az_el(az, 40), core.az_el(az * 0.9 - 20, 0), gather],
                               0.08 * sx, 0.07 * sx, 0.045, n=10, lift=0.4)
    gh, gn = core.ray(head, gather * 3, -gather)
    if gh is not None:
        ctx.L["braid_root"] = (gh + gn * 0.03, gn)
    _finish_hair(ctx, el, hr["color"])


def build_braid(ctx):
    """Lira's braid (§7.6): plaited lobes 0.14 H wide — flat leaf-shaped ribbons leaning +-25 deg in turn, a groove
    notched between each lobe and the next on its side (a three-strand plait, not a chain of beads) — from the nape
    gather behind the near ear (the hair's landmark, carried through the head pose: the braid hangs on the body) over
    the near shoulder and out of the frame, a green ribbon tied around it. Built after the body: its lower part lies on
    the costume (ray casts onto the torso)."""
    br = ctx.ch["hair"].get("braid")
    if not br:
        return
    from . import rig
    torso = ctx.objs.get("outer") or ctx.objs["torso"]
    w = br.get("w", 0.14) * H
    col = ctx.ch["hair"]["color"]
    kx = ctx.W / 0.85
    # the root: the nape gather (head landmark) in body space, after the head's turn, roll and nod
    root_h, root_n = ctx.L.get("braid_root", (Vector((-0.33 * kx, 0.12, -0.28)), Vector((-1, 0, 0))))
    m = rig.head_pose_matrix(ctx)
    p0 = m @ root_h
    n0 = (m.to_3x3() @ root_n).normalized()
    p1 = p0 + n0 * 0.05 + Vector((0.0, -0.06, -0.16))
    ctrl = [p0, p1, Vector((-0.45 * kx, -0.20, -0.78)), Vector((-0.42, -0.44, -1.10)),
            Vector((-0.40, -0.50, -1.45)), Vector((-0.39, -0.52, -1.75))]
    # rest the lower part on the costume: cast each low point along the front normal
    path = []
    for i, c in enumerate(ctrl):
        if i >= 2:
            hit, nor = core.ray(torso, Vector((c.x, -2.0, c.z)), (0, 1, 0))
            if hit is not None:
                c = hit + nor * (w * 0.32)
        path.append(c)
    pts = []
    for k in range(80):
        t = k / 79 * (len(path) - 1)
        i = min(int(t), len(path) - 2)
        f = t - i
        a, b = path[i], path[i + 1]
        pa = path[max(i - 1, 0)]
        pb = path[min(i + 2, len(path) - 1)]
        # Catmull-Rom
        pts.append(0.5 * ((2 * a) + (-pa + b) * f + (2 * pa - 5 * a + 4 * b - pb) * f * f + (-pa + 3 * a - 3 * b + pb) * f ** 3))
    seglen = sum((pts[i + 1] - pts[i]).length for i in range(len(pts) - 1))
    step = br.get("lobe", 0.115) * H            # along the braid from one lobe to the next (the other side)
    n_lobes = int(seglen / step)
    targets = [step * (k + 0.6) for k in range(n_lobes)]
    lobes = []
    acc, j = 0.0, 0
    for i in range(len(pts) - 1):
        d = (pts[i + 1] - pts[i]).length
        while j < len(targets) and acc + d >= targets[j]:
            f = (targets[j] - acc) / max(d, 1e-6)
            lobes.append((pts[i].lerp(pts[i + 1], f), (pts[i + 1] - pts[i]).normalized()))
            j += 1
        acc += d
    el = []
    for k, (c, tang) in enumerate(lobes):
        nor = Vector((0, -1, 0.15)).normalized()
        if k < 2:   # the first lobes hang behind the jaw: they face out sideways
            nor = (nor + n0).normalized()
        side = 1 if k % 2 else -1
        across = tang.cross(nor).normalized()
        taper = (0.72 + 0.28 * core.smoothstep(0.0, 2.0, k)) * (1.0 - 0.22 * core.smoothstep(0.7, 1.0, k / max(1, len(lobes) - 1)))
        q = core.frame_quat(tang, nor)
        spin = Matrix.Rotation(math.radians(25 * side), 4, "Y").to_quaternion()
        # a flat leaf: long along its own (leaning) axis, a third of the braid wide, thin; centred off the middle
        el.append(dict(co=c + across * side * w * 0.17, half=(w * 0.27 * taper, w * 0.16, step * 1.02), stiff=3.0,
                       rot=q @ spin))
        # the groove: a notch on the lobe's outer edge where the next lobe of this side begins
        el.append(dict(co=c + tang * step * 1.0 + across * side * w * 0.47 + nor * w * 0.05, half=w * 0.13,
                       stiff=3.0, neg=True))
    mat = _hair_mat(ctx, "hair_braid", col, -1.6, -0.3)
    o = core.mb_mesh(ctx, "Braid", el, 0.008, mat, smooth_iter=2, name="braid")
    ctx.add(o, "hair", torso, kind="surface", head=False)
    ctx.sig_objs.append(o)
    ctx.objs["braid"] = o
    # the ribbon: a flat band around the braid at the 5th lobe
    rib = br.get("ribbon")
    if rib and len(lobes) > 5:
        c, tang = lobes[min(5, len(lobes) - 1)]
        rm = core.principled(ctx, "braid_ribbon", rib, 0.6, sheen=0.3)
        ring = core.torus("braid_ribbon", c, w * 0.40, w * 0.07, rm, nrm=tang, seg=32, rseg=10)
        ring.scale = (1.0, 0.75, 1.6)
        ctx.add(ring, "detail:braid_ribbon", o, kind="surface", head=False)
        bow = []
        for s_ in (-1, 1):
            tip = c + Vector((s_ * w * 0.55, -w * 0.25, -w * 0.15))
            bow.append(core.curve("braid_bow", [c + Vector((0, -w * 0.32, 0)), tip], [1.0, 0.6], w * 0.09, rm, order=2))
        for b in bow:
            ctx.add(b, "detail:braid_ribbon", o, kind="surface", head=False)


# ------------------------------------------------------------------ bob (Vega)
def _bob_lock(head, az, part, end_z, w, th, out, curl, sx):
    """One bob lock: from the parting over the scalp to ear level, then straight down (just outside the head) to the
    bob line, the end turned in toward the neck."""
    low_d = core.az_el(az, -4)
    hit, nor = core.ray(head, low_d * 3, -low_d)
    if hit is None:
        return []
    radial = Vector((hit.x, hit.y, 0.0))
    r0 = radial.length
    radial.normalize()
    top = hit + nor * th * 0.5
    fall = radial * (r0 + out)
    hang = Vector((fall.x, fall.y, (top.z + end_z) / 2))
    tip = Vector((fall.x, fall.y, end_z + 0.02)) - radial * 0.01
    turn = Vector((fall.x, fall.y, end_z + 0.05)) - radial * curl
    mid_d = core.az_el(az, 30)
    return core.ribbon_lock(head, [part, mid_d, low_d, hang, tip, turn], w * sx, w * 0.95 * sx, th, n=18,
                            lift=0.45, free_tail=3, taper_at=0.9)


def _bob(ctx):
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    chin_z = ctx.L["chin"].z
    near_end = chin_z + hr.get("near_len", 0.10) * H      # the near side reaches the jaw ("chisel" point)
    far_end = chin_z + hr.get("far_len", 0.26) * H        # the far side is shorter
    back_end = chin_z + 0.20 * H
    # a high forehead on the far side: her raised far brow (+0.09 H, always) must stay clear of the hair
    def hl(h):
        az = math.degrees(math.atan2(h.x, -h.y))
        if az >= 0:
            tbl = [(0, 0.36), (25, 0.43), (50, 0.42), (70, 0.27), (90, 0.10), (110, -0.08), (180, -0.22)]
        else:
            tbl = [(0, 0.34), (-30, 0.28), (-60, 0.16), (-90, 0.02), (-120, -0.12), (-180, -0.22)]
            tbl = [(-a, b) for a, b in tbl]
            az = -az
        return core.lerp_table(tbl, az)
    samples, s = core.surface_samples(head, 2200, lambda h, n, d: h.z > hl(h) + 0.01)
    el = core.sheet_elems(samples, s, lambda h, n: 0.045 + 0.025 * core.smoothstep(0.0, 0.45, h.z))
    part = core.az_el(40, 66)       # the side parting, far side
    th = 0.055
    # the ring of locks, near front (-70) round the back to the far front (+72); the bob line rises from the near
    # side's jaw to the far side's cheek
    # (the far side starts behind the temple: the raised far brow, her trait, stays clear)
    for az in [-74, -88, -102, -116, -130, -144, -158, -172, 174, 160, 146, 132, 118, 106, 96]:
        if az < 0:
            f = core.smoothstep(-74, -172, az)
            end_z = near_end + (back_end - near_end) * f
        else:
            f = core.smoothstep(174, 96, az)
            end_z = back_end + (far_end - back_end) * f
        el += _bob_lock(head, az, part, end_z, 0.105, th, 0.035 + 0.02 * (1 - abs(abs(az) - 120) / 60), 0.06, sx)
    # the "chisel": the near front lock comes forward and down to a point at the jaw line
    jaw_d = core.az_el(-58, -30)
    jh, jn = core.ray(head, jaw_d * 3, -jaw_d)
    jaw = Vector((jh.x - 0.03, jh.y - 0.05, near_end - 0.02))
    el += core.ribbon_lock(head, [part, core.az_el(-26, 54), core.az_el(-56, 22), core.az_el(-64, -2),
                                  jaw + Vector((0.0, 0.03, 0.12)), jaw], 0.13 * sx, 0.05 * sx, th, n=18, lift=0.45,
                           free_tail=2, taper_at=0.7)
    # a fringe swept from the parting across the forehead to the near temple (it leaves the far brow free); with a
    # streak, its second lock is the silver one (built below, not part of the dark mass)
    stk = hr.get("streak")
    streak_path = None
    for i, (az, w, el_tip) in enumerate([(6, 0.085, 46), (-12, 0.095, 40), (-28, 0.095, 32), (-44, 0.09, 24)]):
        tip_d = core.az_el(az - 24, el_tip)
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        path = [part, core.az_el(az + 8, 56), tip_d, hit + nor * 0.05 + Vector((-0.035, -0.015, -0.035))]
        if stk and i == 1:
            streak_path = (az, el_tip, path)
            continue
        el += core.ribbon_lock(head, path, w * sx, w * 0.7 * sx, 0.05, n=14, lift=0.45, free_tail=1)
    _finish_hair(ctx, el, hr["color"], signature=True)
    if stk and streak_path:
        _streak(ctx, head, part, streak_path, stk, sx)


def _streak(ctx, head, part, streak_path, col, sx):
    """Vega's silver lock (§7.6: one ribbon lock 0.12 H, only hers): it leaves the parting narrow (its root stays
    under the dark hair at the crown: no white patch there), widens over the forehead and tapers toward the near brow
    and cheek; two strands side by side so a groove runs down it, the hair's AO in the groove and a crevice tone well
    under #C8CCD4 — a lock in the fringe, not a sheet laid over the hair."""
    az, el_tip, path = streak_path
    el = []
    wmax = 0.12 * H * 0.5
    for k, da in enumerate((-3.5, 3.5)):     # two strands, ~0.06 apart: 0.12 H together, a groove between
        tip = path[-1] + Vector((da * 0.004, 0.0, -abs(da) * 0.002))
        p_ = [part, core.az_el(az + 8 + da * 0.6, 56), core.az_el(az - 24 + da, el_tip - 2), tip + Vector((0, 0, -0.03))]
        el += core.ribbon_lock(head, p_, 0.016, wmax * 0.5, 0.042, n=16, lift=1.15, free_tail=1, taper_at=0.62,
                               wmin=0.02)
    mat = core.hair_mat(ctx, "hair_streak", col, 0.1, 0.62, dark=core.hex_scale(col, 0.78),
                        light=core.hex_mix(col, "#ffffff", 0.25), crevice="#5E626C")
    o = core.mb_mesh(ctx, "Streak", el, 0.007, mat, smooth_iter=2, name="streak")
    ctx.add(o, "detail:streak", ctx.objs["hair"], kind="surface", head=True)
    ctx.details["streak"] = 400
