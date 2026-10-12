"""Hair (§7.5 step 3): a thin metaball sheet over the scalp (sheet-solved radii) plus flattened "ribbon locks" laid
over the surface frame from the crown or the parting to the fringe and the nape; tips may leave the scalp (a fringe
over the forehead, a bob's ends). Locks whose root would lie inside a headgear are dropped and 6–10 "escape" locks
grow below its rim (hats come with P2; the kerchief keeps a fringe under its edge). Converted to a mesh, Smooth 2,
no Subsurf (§7.5); a character may coarsen its main hair mass (hair "res", Rai: P-A10's triangle budget). Material: object-Z gradient (+8 % L* on top) x AO crevice tint.

Styles (chars.py "hair": {"style": ...}):
  swept    — short hair, a fringe of broad locks swept to the far side, ears free (Bram);
  kerchief — only what shows under a kerchief: three long fringe locks and the temples, the nape gathered to the
             braid's root (a landmark); the braid — flat plaited lobes at +-25 deg with a groove between them, hung
             from that root through the head pose — is built with the body (it lies on the near shoulder) by
             `build_braid` (Lira);
  bob      — an asymmetric bob: a side parting on the far side, the near side longer with a "chisel" point at the
             jaw, the ends turned in; an optional streak (`_streak`): one two-strand lock in its own colour cast onto
             the dark hair, from the top front across the fringe to the near brow (Vega);
  tufts    — a bald dome (glossy, face.skin_mat) with a low horseshoe band and soft fans of clumps at the sides (Olm
             over the ears, Kort behind them);
  fringe   — only what a hood shows: 6-10 tapered wisps from under the hood's rim, swept to the far side and
             overlapping, their pointed tips on the brow line, light at the tips (Vik);
  short    — short hair swept back, culled under a hat, escape locks below its rim (Seir);
  flattop  — a brush cut with a flat top: one shell grown out of the scalp, filling a rounded cut volume (walls
             leaning in, a level top just over the crown, rounded corners) and a thin crop where the skull bulges
             past it; the crop's colour fades to a skin-mixed tone above the ears, the front rises from a visible
             hairline; bristle tips along the top's rim, lighter at the tips; Z-stretched stubble grains in the
             shader (Frey);
  ponytail — hair drawn up to a high gather, a fringe to the far side and a tail of 7 clumps arcing over and behind
             the head (Irma);
  bun      — hair swept up to a tall vertical bun coiled round its axis (Vance);
  long     — long hair swept back from a high forehead down behind the shoulders (Rai);
  quiff    — a quiff curling out from under a cap's front edge (Hawk).
"""
import math

import bpy  # noqa: F401  (bpy before bmesh)
import bmesh
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
                         crevice=hr.get("crevice"), stubble=hr.get("stubble", 0.0))


def build_hair(ctx):
    st = ctx.ch["hair"]["style"]
    fn = {"swept": _swept, "kerchief": _kerchief, "bob": _bob, "tufts": _tufts, "fringe": _fringe, "short": _short,
          "flattop": _flattop, "ponytail": _ponytail, "bun": _bun, "long": _long, "quiff": _quiff}.get(st)
    (fn or _P3_STYLES[st])(ctx)


def _cut(ctx, el):
    """Drop the hair elements a headgear covers (§7.5 step 3: locks rooted inside the hat are culled; what lies below
    the rim stays — the escape locks). headgear.plan sets ctx.hair_cut (a predicate on a point) before the hair."""
    f = getattr(ctx, "hair_cut", None)
    if f is None:
        return el
    return [e for e in el if not f(Vector(e["co"]))]


def _finish_hair(ctx, el, col, name="hair", res=0.011, signature=False, cut=True, smooth_iter=2):
    if cut:
        el = _cut(ctx, el)
    mat = _hair_mat(ctx, "hair_" + name, col)
    if name == "hair":      # a character may coarsen its main hair mass (Rai's long hair: P-A10's 500k triangles)
        res = max(res, ctx.ch["hair"].get("res", res))
    o = core.mb_mesh(ctx, "Hair" + name, el, res, mat, smooth_iter=smooth_iter, name=name)
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
    # a character may thin the cap (Bram: a close crop under the locks, so the crown is visibly narrower than the
    # pear beard at 48 px — P-A2)
    t0, t1 = hr.get("sheet", (0.035, 0.03))
    th_l, lift_l = hr.get("lock_th", 0.05), hr.get("lock_lift", 0.45)
    el = core.sheet_elems(samples, s, lambda h, n: (t0 + t1 * core.smoothstep(0.1, 0.45, h.z))
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
        el += core.ribbon_lock(head, [crown, mid, tip_d, hang], w * sx, w * 0.8 * sx, th_l, n=14, lift=lift_l,
                               free_tail=1)
    # sides and back: locks from the crown down to the hairline; short over the ears (ears stay free)
    for az, el_end, w in [(-76, 18, 0.07), (-98, 10, 0.07), (76, 20, 0.07), (98, 12, 0.07), (-125, 0, 0.08),
                          (125, 2, 0.08), (-152, -8, 0.085), (152, -6, 0.085), (180, -12, 0.085)]:
        el += core.ribbon_lock(head, [crown, core.az_el(az, (72 + el_end) / 2), core.az_el(az, el_end)], w * sx,
                               w * 0.75 * sx, th_l * 0.9, n=12, lift=lift_l * 0.9)
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
    # the fringe: 3 long, broad locks from under the kerchief edge, swept to the far side, tips over the forehead and
    # clear of the brows (short narrow locks read as dark horns on the brow line)
    for az, w, sweep in [(-28, 0.088, 16), (-4, 0.092, 20), (20, 0.08, 18)]:
        root = core.az_el(az, 50)
        mid = core.az_el(az + sweep * 0.5, 42)
        tip_d = core.az_el(az + sweep, 37)
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        hang = hit + nor * 0.03 + Vector((math.sin(math.radians(az + sweep)) * 0.035, -0.02, -fringe * 0.32))
        el += core.ribbon_lock(head, [root, mid, tip_d, hang], w * sx, w * 0.62 * sx, 0.04, n=14, lift=0.45,
                               free_tail=1)
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
        el += core.ribbon_lock(head, path, w * sx, w * 0.7 * sx, 0.05, n=14, lift=0.45, free_tail=1)
    _finish_hair(ctx, el, hr["color"], signature=True)
    if stk and streak_path:
        _streak(ctx, head, part, streak_path, stk, sx)


def _streak(ctx, head, part, streak_path, col, sx):
    """Vega's silver lock (§7.6: one ribbon lock 0.12 H, only hers): cast onto the dark hair's own surface (as a beard's
    locks onto its mass), so it follows every bump of the hair under it instead of poking through. It leaves the hair
    narrow by the parting at the front top, falls nearly straight down across the fringe (a sweep along the head's
    outline read as a white headband at 64-128 px, review r3) to a free tip by the near brow; two strands side by
    side below the root, so a groove runs down it with the hair's AO. Its value sits a step under the #C8CCD4 slot and
    darkest at the root (it grows out of the dark hair), lightest at the tip (#B8BCC4)."""
    hair = ctx.objs["hair"]
    core.update()
    el = []
    wmax = 0.12 * H * 0.5
    # (the root lies on the front of the hair, well inside its outline seen from the level camera: a root up at the
    # crown stood off the top of the head like a horn)
    stk = ctx.ch["hair"]
    route = stk.get("streak_route", [(14, 58), (2, 50), (-13, 40), (-25, 30)])   # (azimuth, elevation) on the hair
    w0, w1 = stk.get("streak_w", (0.55, 1.0))                                    # root / middle width share
    tip_d = core.az_el(route[-1][0] - 5, route[-1][1] - 6)
    th_, tn_ = core.ray(hair, tip_d * 3, -tip_d)
    for k, da in enumerate((-2.5, 2.5)):     # two strands ~0.06 apart: 0.12 H together, a groove between
        free = th_ + tn_ * 0.010 + Vector((-0.010 + da * 0.003, -0.018, -0.07 - abs(da) * 0.002))
        p_ = [core.az_el(az + da * (0.2 + 0.8 * i / (len(route) - 1)), el) for i, (az, el) in enumerate(route)] + [free]
        el += core.ribbon_lock(hair, p_, wmax * 0.55 * w0, wmax * 0.55 * w1, 0.026, n=40, lift=0.08, free_tail=1,
                               taper_at=0.62, wmin=0.022)
    mat = core.hair_mat(ctx, "hair_streak", stk.get("streak_mid", core.hex_scale(col, 0.92)), 0.1, 0.62,
                        dark=stk.get("streak_tip", col), light=stk.get("streak_root", core.hex_scale(col, 0.78)),
                        crevice=stk.get("streak_crevice", "#5E626C"))
    o = core.mb_mesh(ctx, "Streak", el, 0.006, mat, smooth_iter=2, name="streak")
    ctx.add(o, "detail:streak", hair, kind="surface", head=True)
    ctx.details["streak"] = 400


# ------------------------------------------------------------------ helpers for P2 styles
def _tuft(head, d, out_dir, ln, w, th, n, rng, spread=14.0, up=0.35, back=0.25, sx=1.0):
    """A soft tuft: a few broad clumps fanning out of the scalp at direction d (from the head centre), each a short
    flattened ribbon leaving the surface and curling up/back at a rounded tip (fluffy sides of a bald head)."""
    el = []
    hit, nor = core.ray(head, d * 3, -d)
    if hit is None:
        return el
    tang = Vector((0, 0, 1)).cross(nor)
    if tang.length < 1e-6:
        tang = Vector((1, 0, 0))
    tang.normalize()
    for k in range(n):
        f = (k - (n - 1) / 2) / max(1, (n - 1) / 2)
        a = math.radians(spread * f)
        dd = (nor * math.cos(a) + Vector((0, 0, 1)) * math.sin(a) * 1.2).normalized()
        root = hit - nor * 0.01 + Vector((0, 0, f * w * 0.9))
        l_ = ln * (0.75 + 0.25 * (1 - abs(f))) * rng.uniform(0.9, 1.1)
        p1 = root + dd * l_ * 0.45 + out_dir * l_ * 0.15
        tip = root + dd * l_ * 0.85 + out_dir * l_ * 0.45 + Vector((0, 0, up * l_ * (0.4 + 0.6 * (f + 1) / 2)))
        nrm = [tang, tang, tang]
        el += core.clump([root, p1, tip], nrm, w, w * 0.9, th, n=10, lift=0.0, taper_at=0.55, tip=0.45, stiff=2.6,
                         flat=0.85)
    # a soft core under the fan, so the clumps grow from one mass, not from bare skin
    el.append(dict(co=hit + nor * th * 0.3, half=(w * 1.3, th * 1.1, w * 1.5), stiff=2.2,
                   rot=core.frame_quat(Vector((0, 0, 1)), nor)))
    return el


# ------------------------------------------------------------------ tufts: a bald dome (Olm, Kort)
def _tufts(ctx):
    """A bald dome (§7.6 Olm "лысый купол с бликом", Kort "лысый купол") with soft tufts at the sides: a low
    horseshoe band round the back from ear to ear (sheet) and a fan of broad clumps on each side — over the ears and
    sticking out sideways (Olm: 0.10 W, the "fluffy sides") or behind them (Kort). The skin shader makes the dome
    glossy (face.skin_mat: "bald")."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    tf = hr.get("tufts", {})
    sx = ctx.P["hx"] / 0.48
    el = []
    band_az = tf.get("band_az", 95)
    lo, hi = tf.get("band_lo", -24), tf.get("band_hi", 8)

    def keep(h, n, d):
        az = abs(math.degrees(math.atan2(h.x, -h.y)))
        e = math.degrees(math.atan2(h.z, math.hypot(h.x, h.y)))
        top = hi + 8 * core.smoothstep(band_az, 180, az)
        return az > band_az and lo < e < top
    samples, s = core.surface_samples(head, 2400, keep)
    el += core.sheet_elems(samples, s, lambda h, n: tf.get("band_t", 0.035))
    out_w = tf.get("out", 0.10) * ctx.W
    for side in (-1, 1):
        for az, e, ln, w, n in tf.get("fans", [(100, 14, 1.0, 0.055, 5), (122, 6, 0.85, 0.05, 4)]):
            d = core.az_el(side * az, e)
            out_dir = Vector((side, 0.25, 0.0)).normalized()
            el += _tuft(head, d, out_dir, out_w * ln + 0.06, w, 0.04, n, ctx.rng, up=tf.get("up", 0.35), sx=sx)
    _finish_hair(ctx, el, hr["color"], smooth_iter=3)


# ------------------------------------------------------------------ fringe: only what shows under a hood (Vik)
def _fringe(ctx):
    """Shaggy hair seen only at a hood's opening (§7.6 Vik: "5–7 прядей из капюшона на брови", §7.5 step 3: 6–10
    escape locks below the rim): a scalp sheet over the front (the hood hides the rest) and tapered wisps (core.clump)
    from under the hood's front edge, swept diagonally to the far side and overlapping, down over the forehead to
    pointed tips on the brow line; shaded light at the tips, darker at the roots under the hood."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.26), (40, 0.22), (70, 0.12), (90, 0.02), (130, -0.10), (180, -0.20)])
    samples, s = core.surface_samples(head, 2000, lambda h, n, d: h.z > hl(h) + 0.015)
    el = core.sheet_elems(samples, s, lambda h, n: 0.035)
    # the escape locks (§7.5 step 3: 6-10 below the rim): long tapered wisps rooted under the hood, out past its rim
    # and down over the forehead to a pointed tip on (or just over) the brow line, overlapping their neighbours. Only
    # the rounded ends of short locks used to clear the rim — three smooth ovoids on the brows, "pebbles", P2 review.
    # (azimuth, width, sweep to the far side in deg, tip height over the brow line in H, lift off the skin)
    brow_z = ctx.P["eye_z"] + ctx.P["sclera_h"] * 0.5 + 0.05 * H
    rim_el = hr.get("rim_el", 44)
    # (diagonal, swept to the far side and overlapping from the rim down: vertical, evenly spaced spikes read as a
    # row of fangs; their tips rest on the brows' upper edge, the far ones higher: crossing the far brow they cut it
    # under P-A3's 6 px length at 64 px in the laugh)
    for az, w, sweep, tip_dz, lift in hr.get("wisps", [(-46, 0.10, 20, 0.07, 0.018), (-33, 0.11, 24, 0.035, 0.024),
                                                       (-20, 0.115, 28, 0.015, 0.030), (-7, 0.115, 30, 0.04, 0.032),
                                                       (6, 0.11, 30, 0.025, 0.030), (19, 0.10, 28, 0.06, 0.026),
                                                       (31, 0.09, 24, 0.11, 0.022), (42, 0.08, 18, 0.14, 0.018)]):
        root_d = core.az_el(az * 0.8, rim_el + 14)
        rim_d = core.az_el(az + sweep * 0.3, rim_el)
        hr_, nr_ = core.ray(head, root_d * 3, -root_d)
        hm_, nm_ = core.ray(head, rim_d * 3, -rim_d)
        tip_az = az + sweep
        tz = brow_z + tip_dz * H
        ht_, nt_ = core.ray_front(head, math.sin(math.radians(tip_az)) * 0.40 * sx, tz)
        if hr_ is None or hm_ is None or ht_ is None:
            continue
        mid = hm_.lerp(ht_, 0.5)
        hmid, nmid = core.ray(head, mid * 3, -mid.normalized())
        if hmid is None:
            continue
        pts = [hr_ + nr_ * 0.03, hm_ + nm_ * 0.045, hmid + nmid * (0.02 + lift), ht_ + nt_ * (0.012 + lift * 0.6)]
        nrs = [nr_, nm_, nmid, nt_]
        el += core.clump(pts, nrs, w * sx, w * 0.8 * sx, 0.030, n=18, lift=0.0, taper_at=0.38, tip=0.10, stiff=2.6,
                         flat=0.7)
    # (no temple locks: the hood covers the temples, and in its shade they only darkened the hair beside the face)
    # shaded the other way up (light at the tips, which hang lowest; the roots under the hood darker): a straw
    # mid-tone whose clumps part in AO crevices — not a flat near-white (hair vs skin keeps dE76 >= 30 by value)
    mat = core.hair_mat(ctx, "hair_hair", hr["color"], brow_z + 0.22, brow_z + 0.02, dark=hr.get("dark"),
                        light=hr.get("light"), crevice=hr.get("crevice"))
    o = core.mb_mesh(ctx, "Hairhair", el, hr.get("res", 0.0105), mat, smooth_iter=2, name="hair")   # P-A10 tris
    ctx.add(o, "hair", head, kind="embed", head=True)
    ctx.objs["hair"] = o


# ------------------------------------------------------------------ short (Seir; under hats)
def _short(ctx):
    """Short hair (§7.6 Seir "короткие седые, пряди из-под шляпы с ближней стороны"): a scalp sheet and broad locks
    swept back from the hairline; a headgear culls what it covers (ctx.hair_cut) and `escape` locks grow below its
    rim at the near temple and over the ears."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.30), (30, 0.28), (60, 0.2), (80, 0.12), (100, 0.06), (140, -0.12), (180, -0.22)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.015)
    el = core.sheet_elems(samples, s, lambda h, n: 0.035 + 0.02 * core.smoothstep(0.1, 0.45, h.z))
    crown = core.az_el(180, 70)
    for az in range(-150, 181, 30):
        e0 = core.lerp_table([(0, 44), (60, 34), (90, 20), (130, 6), (180, -4)], abs(az))
        el += core.ribbon_lock(head, [core.az_el(az, e0), core.az_el(az * 0.9 + (12 if az >= 0 else -12), (e0 + 70) / 2),
                                      crown], 0.085 * sx, 0.07 * sx, 0.042, n=12, lift=0.4)
    for az, e_root, e_tip, w in hr.get("escape", [(-70, 26, 2, 0.07), (-86, 22, -6, 0.065), (-102, 16, -10, 0.06),
                                                    (78, 24, 4, 0.06), (96, 18, -6, 0.06)]):
        el += core.ribbon_lock(head, [core.az_el(az + 6, e_root + 14), core.az_el(az, e_root), core.az_el(az - 4, e_tip)],
                               w * sx, w * 0.6 * sx, 0.04, n=10, lift=0.45, taper_at=0.55)
    _finish_hair(ctx, el, hr["color"])


# ------------------------------------------------------------------ flat top (Frey)
def _flattop(ctx):
    """A brush cut with a flat top (§7.6 Frey: "площадка" with a flat top, a crisp hairline, stubble in the shader;
    her "T" signature's square top). One shell grown out of the scalp along its normals, thick where it fills a cut
    volume and a thin crop elsewhere, plus a row of bristle tips along the top's rim — all the "hair" group:
      - the cut volume (per azimuth, in the (radius, z) plane): a wall that leans in by `lean` (sides, front) from
        `ridge` H under the crown (the sides) or the hairline (the front), a level top `top` H over the crown, the
        corner between them rounded by `corner` H. Where the scalp lies inside it the shell fills out to its walls
        (the squared top); where the skull bulges past it (the temples, over the ears, the back) the shell is a crop
        `side` H thin;
      - the fade: the crop and the fill meet in a smooth max (fillet `ramp` H), so the hair grows out of the scalp
        instead of standing on it with a ledge (a block on a foot read as a hat, a fez, a pillbox, P2 reviews); the
        crop's colour grades toward a skin-mixed tone (`fade`) where the shell is thin (a point attribute), so the
        sides fade down to skin above the ears; the front rises over `front_ramp` H from the hairline to `front` H,
        a brushed-up front edge on bare forehead skin;
      - the bristle edge: many short tapered tips along the top's rim (a point attribute lightens them toward the
        tip), and a sparse row of fine tips on the front hairline.
    The shell's shader adds Z-stretched grains (brushed-up bristles on the walls, dots on the top), a matte warm
    brown: darker low, a little lighter on top, never cream (a pale block read as foam or cork)."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    crown = ctx.L["crown"]
    side_t = hr.get("side", 0.008) * H
    t_front = hr.get("front", 0.05) * H
    fr = hr.get("front_ramp", 0.05) * H
    z_top = crown.z + hr.get("top", 0.035) * H
    rc = hr.get("corner", 0.05) * H
    z_ridge = crown.z - hr.get("ridge", 0.22) * H
    k_bl = hr.get("ramp", 0.06) * H
    fband = hr.get("fade_band", 0.08) * H
    fw0, fw1 = hr.get("front_w", (25.0, 55.0))
    lean_f, lean_s = (math.tan(math.radians(a)) for a in hr.get("lean", (35.0, 25.0)))
    hl = hairline_fn(hr.get("hairline", [(0, 0.31), (30, 0.30), (55, 0.24), (75, 0.15), (95, 0.07), (130, -0.08),
                                         (180, -0.20)]))
    c0 = Vector((0.0, 0.0, crown.z * 0.25))

    def hit(az, el):
        d = core.az_el(az, el)
        return core.ray(head, c0 + d * 3.0, -d)

    def skull_r(az, z):
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.0))
        h, _ = core.ray(head, Vector((0, 0, z)) + d * 2.0, -d)
        return Vector((h.x, h.y)).length if h is not None else 0.0

    def smax(a, b, k):
        h = max(k - abs(a - b), 0.0) / k
        return max(a, b) + h * h * k * 0.25

    n_az = 96
    azs = [-180 + 360 * i / n_az for i in range(n_az)]
    cols = []
    for az in azs:
        f = 1.0 - core.smoothstep(fw0, fw1, abs(az))
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.0))
        zh = hl(d)
        z_ref = z_ridge + (zh + fr - z_ridge) * f
        r0 = skull_r(az, z_ref) + side_t + (t_front - side_t) * f
        lean = lean_s + (lean_f - lean_s) * f
        nl = math.sqrt(1.0 + lean * lean)

        def sdf(q, r0=r0, lean=lean, nl=nl, z_ref=z_ref):
            # the rounded intersection of the leaning wall and the level top, in this azimuth's (r, z) plane
            a = (Vector((q.x, q.y)).length - r0 + lean * (q.z - z_ref)) / nl + rc
            b = q.z - z_top + rc
            return math.hypot(max(a, 0.0), max(b, 0.0)) + min(max(a, b), 0.0) - rc
        # where the scalp meets the hairline (the shell starts just under it, tucked into the skin)
        el0 = None
        prev = -72.0
        for el in range(-70, 88, 3):
            h, _ = hit(az, el)
            if h is not None and h.z >= hl(h) - 0.02:
                lo, hi = prev, float(el)
                for _ in range(5):
                    mid = (lo + hi) / 2
                    hm, _ = hit(az, mid)
                    if hm is not None and hm.z >= hl(hm) - 0.02:
                        hi = mid
                    else:
                        lo = mid
                el0 = hi
                break
            prev = float(el)
        if el0 is None:
            el0 = 60.0
        col = []
        for s in (0.0, 0.015, 0.035, 0.06, 0.09, 0.13, 0.18, 0.24, 0.31, 0.38, 0.45, 0.52, 0.59, 0.65, 0.71, 0.76,
                  0.81, 0.85, 0.89, 0.925, 0.955, 0.98, 1.0):
            el = el0 + (87.0 - el0) * s
            p, n = hit(az, el)
            if p is None:
                continue
            u = p.z - hl(p)
            crop_s = -0.006 + (side_t + 0.006) * core.smoothstep(-0.012, 0.02, u)
            crop_f = -0.006 + (t_front + 0.006) * core.smoothstep(-0.012, fr, u)
            crop = crop_s + (crop_f - crop_s) * f
            g = core.smoothstep(0.0, fr, u)
            # fill out to the cut volume along the normal (a few sphere-tracing steps from the scalp)
            t = -sdf(p)
            for _ in range(4):
                t = t - sdf(p + n * t)
            t = min(t, 0.35 * H)
            # the fill grows in over `front_ramp` above the hairline (g): at and under the hairline the shell is the
            # crop alone, tucked into the skin
            th = crop + g * (smax(crop, t, k_bl) - crop) if t > crop - k_bl else crop
            q = p + n * th
            # the fade (0 = hair, 1 = the skin-mixed tone): the hair's colour grades to the skin over `fade_band` H
            # above the hairline on the sides and the back (a fade), over a crisp 0.025 H at the front (the hairline)
            fd = 1.0 - core.smoothstep(-0.004, fband + (0.025 * H - fband) * f, u)
            col.append((q, th, fd))
        cols.append(col)
    # equal row counts per column (a miss drops a row): pad from the top
    n_rows = min(len(c) for c in cols)
    cols = [c[:n_rows - 1] + [c[-1]] for c in cols]
    bm = bmesh.new()
    fade_v = []
    grid = []
    for col in cols:
        ring = []
        for q, th, fd in col:
            ring.append(bm.verts.new(q))
            fade_v.append(fd)
        grid.append(ring)
    for i in range(n_az):
        a, b = grid[i], grid[(i + 1) % n_az]
        for k in range(n_rows - 1):
            bm.faces.new((a[k], b[k], b[k + 1], a[k + 1]))
    top_c = bm.verts.new((0.0, 0.0, max(c[-1][0].z for c in cols)))
    fade_v.append(0.0)
    for i in range(n_az):
        bm.faces.new((grid[i][-1], grid[(i + 1) % n_az][-1], top_c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    blk = core.mesh_obj("hair", bm)
    attr = blk.data.color_attributes.new("fade", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(fade_v):
        attr.data[i].color = (v, v, v, 1.0)
    # the faded edge's tone: the skin as the shader paints it, a little toward the hair's dark (stubble on skin)
    from .qa import skin_albedo
    fade_col = hr.get("fade") or core.hex_mix(skin_albedo(ctx), hr.get("dark", hr["color"]), hr.get("fade_mix", 0.25))
    mat = core.hair_mat(ctx, "hair_hair", hr["color"], z_ridge - 0.04, z_top, dark=hr.get("dark"), light=hr.get("light"),
                        crevice=hr.get("crevice"), stubble=hr.get("stubble", 0.0), grain=hr.get("grain"),
                        rough=hr.get("rough", 0.6), spec=hr.get("spec", 0.5), fleck=hr.get("fleck"),
                        edge=("fade", fade_col, 1.0), edge_last=True)
    core.finish(blk, mat, sub=1)
    ctx.add(blk, "hair", head, kind="embed", head=True)
    ctx.sig_objs.append(blk)
    ctx.objs["hair"] = blk
    # the bristle edge: tapered tips (5-sided cones) in one mesh, the tip lighter (a point attribute)
    rng = ctx.rng
    tip_m = core.hair_mat(ctx, "hair_bristle", hr["color"], z_ridge - 0.04, z_top, dark=hr["color"],
                          light=hr.get("light"), crevice=hr.get("crevice"), rough=hr.get("rough", 0.6),
                          spec=hr.get("spec", 0.5), edge=("tip", hr.get("tip", hr.get("light", hr["color"])), 1.0))
    bm = bmesh.new()
    tipv = []

    def cone(base, up, ln, r0):
        side = up.cross(Vector((0, 0, 1)) if abs(up.z) < 0.9 else Vector((1, 0, 0))).normalized()
        side2 = up.cross(side).normalized()
        ring = []
        for j in range(5):
            a = 2 * math.pi * j / 5
            ring.append(bm.verts.new(base - up * ln * 0.35 + (side * math.cos(a) + side2 * math.sin(a)) * r0))
            tipv.append(0.0)
        apex = bm.verts.new(base + up * ln)
        tipv.append(1.0)
        for j in range(5):
            bm.faces.new((ring[j], ring[(j + 1) % 5], apex))
        bm.faces.new(list(reversed(ring)))

    def col_at(az):
        x = (az + 180.0) / 360.0 * n_az
        i0 = int(math.floor(x)) % n_az
        return cols[i0], cols[(i0 + 1) % n_az], x - math.floor(x)
    a0, a1, n_top, ln_top, r_top = hr.get("bristles_top", (-115.0, 115.0, 150, 0.032, 0.0075))
    for i in range(n_top):
        az = a0 + (a1 - a0) * (i + rng.uniform(-0.45, 0.45)) / max(1, n_top - 1)
        ca, cb, w = col_at(az)
        # the rim: the outermost point of the rounded corner (where the shell's profile turns over into the top)
        zr = z_top - rc * rng.uniform(0.25, 0.6)
        ka = min(range(n_rows), key=lambda k: abs(ca[k][0].z - zr) + (0.0 if ca[k][1] > side_t * 3 else 1.0))
        kb = min(range(n_rows), key=lambda k: abs(cb[k][0].z - zr) + (0.0 if cb[k][1] > side_t * 3 else 1.0))
        base = ca[ka][0].lerp(cb[kb][0], w)
        out = Vector((base.x, base.y, 0.0)).normalized()
        up = (Vector((0, 0, 1)) * rng.uniform(0.8, 1.0) + out * rng.uniform(0.25, 0.65)
              + out.cross(Vector((0, 0, 1))) * rng.uniform(-0.2, 0.2)).normalized()
        cone(base, up, ln_top * H * rng.uniform(0.6, 1.35), r_top * H * rng.uniform(0.8, 1.2))
    a0, a1, n_fr, ln_fr, r_fr = hr.get("bristles_front", (-46.0, 46.0, 50, 0.018, 0.0045))
    for i in range(n_fr):
        az = a0 + (a1 - a0) * (i + rng.uniform(-0.4, 0.4)) / max(1, n_fr - 1)
        ca, cb, w = col_at(az)
        # just above the hairline, where the crop has grown to the brushed-up front (the first rows are tucked)
        kk = next((k for k in range(n_rows) if ca[k][1] > t_front * 0.45), 4)
        base = ca[kk][0].lerp(cb[kk][0], w)
        out = Vector((base.x, base.y, 0.0)).normalized()
        up = (Vector((0, 0, 1)) * rng.uniform(0.7, 1.0) + out * rng.uniform(0.3, 0.6)).normalized()
        cone(base, up, ln_fr * H * rng.uniform(0.6, 1.3), r_fr * H * rng.uniform(0.8, 1.2))
    tips = core.mesh_obj("hair_tips", bm)
    attr = tips.data.color_attributes.new("tip", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(tipv):
        attr.data[i].color = (v, v, v, 1.0)
    core.finish(tips, tip_m)
    ctx.add(tips, "hair", blk, kind="embed", head=True)
    ctx.sig_objs.append(tips)
    return blk


# ------------------------------------------------------------------ ponytail (Irma)
def _ponytail(ctx):
    """A high ponytail (§7.6 Irma: platinum, 7 ribbons, gathered 0.15 H above the crown, arcing back and down to the
    shoulder — the "hook" over and behind the head): a scalp sheet; locks from all round the hairline drawn up to the
    gather at the top back; a fringe swept to the far side; the tail — 7 broad clumps around one arcing path, fanning
    out toward their tips; a band at the gather."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.32), (30, 0.30), (60, 0.22), (85, 0.10), (110, 0.0), (150, -0.14), (180, -0.20)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.012)
    el = core.sheet_elems(samples, s, lambda h, n: 0.038 + 0.012 * core.smoothstep(0.2, 0.5, h.z))
    g_az, g_el = hr.get("gather", (180, 52))
    gd = core.az_el(g_az, g_el)
    gh, gn = core.ray(head, gd * 3, -gd)
    gather = gh + gn * 0.07
    for az in range(-150, 181, 25):
        e0 = core.lerp_table([(0, 40), (60, 30), (90, 18), (130, 4), (180, -8)], abs(az))
        if abs(az) < 50:
            continue        # the front goes under the fringe
        el += core.ribbon_lock(head, [core.az_el(az, e0), core.az_el(az * 0.6 + g_az * 0.4 * (1 if az >= 0 else -1),
                                                                     (e0 + g_el) / 2), gd],
                               0.09 * sx, 0.06 * sx, 0.042, n=12, lift=0.4)
    # the fringe: from a parting on the near side, swept over the forehead to the far temple
    for az, w, el_tip in hr.get("fringe", [(-30, 0.095, 40), (-8, 0.10, 36), (14, 0.095, 30), (34, 0.085, 24)]):
        tip_d = core.az_el(az + 30, el_tip)
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        path = [core.az_el(-40, 64), core.az_el(az + 10, 54), tip_d,
                hit + nor * 0.04 + Vector((0.03, -0.015, -0.03))]
        el += core.ribbon_lock(head, path, w * sx, w * 0.6 * sx, 0.048, n=14, lift=0.45, free_tail=1)
    # back over the crown to the gather (no bare scalp between the fringe's roots and the tail)
    for az in (-30, 0, 30):
        el += core.ribbon_lock(head, [core.az_el(az - 40, 62), core.az_el(az * 0.5 + 120, 80), gd], 0.10 * sx,
                               0.08 * sx, 0.045, n=12, lift=0.4)
    o = _finish_hair(ctx, el, hr["color"])
    # the tail: an arc over and behind the head, down to the shoulder (head-local, +Y is the back of the head)
    crown = ctx.L["crown"]
    tl = hr.get("tail", {})
    up = tl.get("up", 0.15) * H
    path = [gather, Vector((gather.x, gather.y + 0.08, crown.z + up)),
            Vector((gather.x, gather.y + 0.32, crown.z + up * 0.8)),
            Vector((gather.x - 0.02, gather.y + 0.52, crown.z - 0.18)),
            Vector((gather.x - 0.05, gather.y + 0.56, crown.z - 0.55)),
            Vector((gather.x - 0.08, gather.y + 0.48, crown.z - 0.92))]
    path = [Vector(p) + Vector(tl.get("shift", (0, 0, 0))) * (i / 5) for i, p in enumerate(path)]
    pts = core.catmull(path, 40)
    tel = []
    n_c = tl.get("n", 7)
    for k in range(n_c):
        a = 2 * math.pi * k / n_c
        cp, nrm = [], []
        for i, p in enumerate(pts):
            t = i / (len(pts) - 1)
            tang = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            side = tang.cross(Vector((1, 0, 0))).normalized()
            if side.length < 1e-6:
                side = Vector((0, 0, 1))
            b2 = tang.cross(side).normalized()
            r = tl.get("r0", 0.04) + tl.get("r1", 0.06) * math.sin(math.pi * min(1.0, t * 1.4)) \
                + tl.get("r2", 0.09) * core.smoothstep(0.6, 1.0, t)
            off = side * math.cos(a + t * 1.2) * r + b2 * math.sin(a + t * 1.2) * r * 0.8
            cp.append(p + off)
            nrm.append((side * math.cos(a + t * 1.2) + b2 * math.sin(a + t * 1.2)).normalized())
        ln_k = 0.88 + 0.12 * math.cos(a * 2)
        cut_n = int(len(cp) * ln_k)
        tel += core.clump(cp[:cut_n:2], nrm[:cut_n:2], 0.062, 0.05, 0.042, n=40, lift=0.0, taper_at=0.65, tip=0.3,
                          stiff=2.8, flat=0.75)
    mat = _hair_mat(ctx, "hair_tail", hr["color"], -0.6, 0.62)
    tail = core.mb_mesh(ctx, "Tail", tel, 0.011, mat, smooth_iter=3, name="ponytail")
    ctx.add(tail, "detail:ponytail", o, kind="embed", head=True)       # P-A8 "хвост 3000": its own ID group
    ctx.sig_objs.append(tail)
    ctx.objs["ponytail"] = tail
    bi = tl.get("band_at", 3)            # the hair tie: a band round the tail just past the gather
    band = core.torus("pony_band", (pts[bi] + pts[bi + 1]) / 2, tl.get("band_r", 0.06), 0.018,
                      core.principled(ctx, "pony_band", tl.get("band", "#3A3C46"), 0.5, sheen=0.2),
                      nrm=(pts[bi + 2] - pts[max(0, bi - 1)]).normalized(), seg=32, rseg=10)
    ctx.add(band, "costume:band", tail, kind="embed", head=True)
    ctx.details["ponytail"] = 3000
    ctx.L["gather"] = gather


# ------------------------------------------------------------------ bun (Vance)
def _bun(ctx):
    """A tall vertical bun (§7.6 Vance: 0.28 H over the crown, "витки лент вокруг вертикали"; her "hat"): a scalp
    sheet; broad locks swept up from all round the hairline to the bun's base; the bun — two ribbon clumps coiling up
    around a vertical axis, narrowing toward the top, over a soft core; a silver pin with a pearl."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.32), (30, 0.30), (60, 0.22), (85, 0.10), (110, 0.0), (150, -0.14), (180, -0.20)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.012)
    el = core.sheet_elems(samples, s, lambda h, n: 0.036 + 0.01 * core.smoothstep(0.2, 0.5, h.z))
    b_az, b_el = hr.get("base", (175, 86))
    bd = core.az_el(b_az, b_el)
    bh, bn = core.ray(head, bd * 3, -bd)
    base = bh + bn * 0.02
    for az in range(-160, 181, 20):
        e0 = core.lerp_table([(0, 42), (50, 36), (90, 20), (130, 4), (180, -8)], abs(az))
        el += core.ribbon_lock(head, [core.az_el(az, e0), core.az_el(az, (e0 + b_el) / 2 + 4), bd],
                               0.09 * sx, 0.07 * sx, 0.042, n=14, lift=0.42)
    o = _finish_hair(ctx, el, hr["color"])
    bun = hr.get("bun", {})
    height = bun.get("h", 0.28) * H
    crown = ctx.L["crown"]
    axis_top = Vector((base.x, base.y + bun.get("lean", 0.03), crown.z + height))
    r0, r1 = bun.get("r", (0.13, 0.05))
    turns = bun.get("turns", 2.6)
    bel = []
    # the core: soft balls up the axis
    for k in range(5):
        t = k / 4
        c = base.lerp(axis_top, t * 0.9)
        r = r0 * (1 - t) + r1 * t
        bel.append(dict(co=c, half=r * 0.7, stiff=2.0))
    for strand in range(bun.get("strands", 1)):
        cp, nrm = [], []
        n_ = 90
        for i in range(n_):
            t = i / (n_ - 1)
            a = 2 * math.pi * turns * t + strand * math.pi
            c = base.lerp(axis_top, t)
            r = r0 * (1 - t ** 1.5) + r1 * t ** 1.5
            off = Vector((math.cos(a), math.sin(a), 0.0)) * r
            cp.append(c + off + Vector((0, 0, 0.0)))
            nrm.append(off.normalized())
        bel += core.clump(cp[::2], nrm[::2], bun.get("w", 0.085), bun.get("w", 0.085) * 0.7, 0.06, n=70, lift=0.0,
                          taper_at=0.85, tip=0.5, stiff=2.8, flat=0.9)
    mat = _hair_mat(ctx, "hair_bun", hr["color"], 0.1, crown.z + height)
    b = core.mb_mesh(ctx, "Bun", bel, 0.010, mat, smooth_iter=2, name="bun")
    ctx.add(b, "detail:bun", o, kind="embed", head=True)               # P-A8 "пучок 3500": its own ID group
    ctx.sig_objs.append(b)
    ctx.objs["bun"] = b
    ctx.details["bun"] = 3500
    ctx.L["bun_axis"] = (base, axis_top)


# ------------------------------------------------------------------ long (Rai)
def _long(ctx):
    """Long hair swept back (§7.6 Rai: "длинные белые назад, за плечи"): a high forehead line; broad locks from the
    hairline straight back over the head and down past the nape, their free tails falling behind the neck and over
    the shoulders' back; side locks behind the ears down to the shoulders."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.36), (30, 0.33), (60, 0.24), (85, 0.12), (110, 0.0), (150, -0.14), (180, -0.20)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.012)
    el = core.sheet_elems(samples, s, lambda h, n: 0.040 + 0.015 * core.smoothstep(0.2, 0.5, h.z))
    drop = hr.get("drop", -0.80)
    for az in range(-150, 151, 20):
        sg = 1 if az > 0 else (-1 if az < 0 else (1 if ctx.rng.random() < 0.5 else -1))
        e0 = core.lerp_table([(0, 52), (40, 44), (70, 32), (100, 16), (150, 2)], abs(az))
        b_az = sg * (180 - 0.6 * min(abs(az), 70)) if abs(az) <= 100 else sg * (abs(az) + 12)
        mid = core.az_el(b_az * 0.85, 72) if abs(az) < 40 else core.az_el((az + b_az) / 2, 46)
        back = core.az_el(b_az, 2)
        hb, nb = core.ray(head, back * 3, -back)
        if hb is None:
            continue
        r_ = math.hypot(hb.x, hb.y) + 0.05
        ang = math.atan2(hb.x, hb.y)
        fall = Vector((math.sin(ang) * r_ * 1.05, math.cos(ang) * r_ * 1.05, (hb.z + drop) / 2))
        tail = Vector((math.sin(ang) * r_ * 1.15, math.cos(ang) * r_ * 1.0 + 0.04, drop))
        el += core.ribbon_lock(head, [core.az_el(az, e0), mid, back, fall, tail], 0.10 * sx, 0.08 * sx, 0.05, n=18,
                               lift=0.42, free_tail=2, taper_at=0.8)
    for s_ in (-1, 1):
        for az, e0 in ((70, 26), (88, 18)):
            d0 = core.az_el(s_ * az, e0)
            h0, n0 = core.ray(head, d0 * 3, -d0)
            if h0 is None:
                continue
            hb = Vector((s_ * (abs(h0.x) + 0.06), h0.y + 0.16, -0.30))
            tail = Vector((s_ * (abs(h0.x) + 0.10), h0.y + 0.24, drop + 0.1))
            el += core.ribbon_lock(head, [d0, core.az_el(s_ * (az + 22), 0), hb, tail], 0.09 * sx, 0.07 * sx, 0.05,
                                   n=16, lift=0.42, free_tail=2, taper_at=0.8)
    _finish_hair(ctx, el, hr["color"])


# ------------------------------------------------------------------ quiff (Hawk, under the cap)
def _quiff(ctx):
    """A quiff from under a cap's front edge (§7.6 Hawk: "тёмно-каштановый кок из-под края шлема"): the scalp sheet
    (culled under the cap) and three broad locks rooted under the cap's front edge, rising and curling forward and to
    the far side over the forehead, their tips free; short locks at the temples below the cap."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.30), (30, 0.28), (60, 0.2), (80, 0.12), (100, 0.06), (140, -0.12), (180, -0.22)])
    samples, s = core.surface_samples(head, 2000, lambda h, n, d: h.z > hl(h) + 0.015)
    el = _cut(ctx, core.sheet_elems(samples, s, lambda h, n: 0.04))
    q = hr.get("quiff", {})
    e_root = q.get("root_el", 40)
    for az, w, sweep, up in q.get("locks", [(-26, 0.12, 30, 1.0), (-4, 0.13, 34, 1.2), (18, 0.11, 30, 0.95)]):
        root = core.az_el(az, e_root + 8)
        hit, nor = core.ray(head, root * 3, -root)
        if hit is None:
            continue
        mid_d = core.az_el(az + sweep * 0.4, e_root - 2)
        hm, nm = core.ray(head, mid_d * 3, -mid_d)
        if hm is None:
            continue
        lift_p = hm + nm * (0.09 * up) + Vector((0, -0.04, 0.03 * up))
        tip_d = core.az_el(az + sweep, e_root - 16)
        ht, nt = core.ray(head, tip_d * 3, -tip_d)
        if ht is None:
            continue
        tip = ht + nt * 0.05 + Vector((math.sin(math.radians(az + sweep)) * 0.03, -0.05, -0.02))
        el += core.ribbon_lock(head, [root, mid_d, lift_p, tip], w * sx, w * 0.5 * sx, 0.05, n=16, lift=0.45,
                               free_tail=2, taper_at=0.55)
    for s_ in (-1, 1):
        el += core.ribbon_lock(head, [core.az_el(s_ * 66, 30), core.az_el(s_ * 76, 14), core.az_el(s_ * 80, 2)],
                               0.065 * sx, 0.04 * sx, 0.035, n=10, lift=0.4, taper_at=0.6)
    _finish_hair(ctx, el, hr["color"], cut=False)


# ================================================================== P3: the leaders' and the ruler's hair (§7.8, §7.10)
def _bald(ctx):
    """A bald head (Torvald; Ormdek under his steel plate): no hair object; face.skin_mat glosses the dome (hair
    "bald": True)."""
    return None


def _second(ctx, el, col, name, dark=None, light=None, crevice=None, res=0.011, smooth_iter=2):
    """A second hair mass in its own colour (grey temples, grey streaks): the "hair" ID group, parented to the head."""
    el = _cut(ctx, el)
    if not el:
        return None
    hr = ctx.ch["hair"]
    mat = core.hair_mat(ctx, "hair_" + name, col, 0.1, 0.62, dark=dark or core.hex_scale(col, 0.8),
                        light=light or core.hex_mix(col, "#ffffff", 0.15), crevice=crevice or hr.get("crevice"))
    o = core.mb_mesh(ctx, "Hair" + name, el, res, mat, smooth_iter=smooth_iter, name=name)
    ctx.add(o, "hair", ctx.objs["head"], kind="embed", head=True)
    ctx.objs[name] = o
    return o


def _mane(ctx):
    """A short mane swept straight back (Grodek, §7.8: "чёрная короткая грива назад, седые виски"): a scalp sheet
    and broad locks from the hairline back over the crown, longer at the nape where their ends flick out; the
    temples grey (`temples`: a second mass of short locks in front of and above the ears)."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn(hr.get("hairline", [(0, 0.31), (30, 0.29), (60, 0.21), (80, 0.13), (100, 0.07), (140, -0.14),
                                         (180, -0.24)]))
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.015 and not (
        hr.get("temples") and 62 < abs(math.degrees(math.atan2(h.x, -h.y))) < 112 and h.z < 0.30))
    el = core.sheet_elems(samples, s, lambda h, n: 0.04 + 0.03 * core.smoothstep(0.1, 0.45, h.z))
    nape = hr.get("nape", -0.30)
    for az in range(-160, 181, 20):
        e0 = core.lerp_table([(0, 47), (40, 42), (60, 36), (100, 22), (140, 6), (180, 0)], abs(az))
        sg = 1 if az >= 0 else -1
        back_az = sg * min(180, abs(az) + 40) if abs(az) < 140 else az
        ctrl = [core.az_el(az, e0), core.az_el(az * 0.6 + sg * 50, 66), core.az_el(back_az, 18)]
        tail = None
        if abs(az) >= 90:
            d = core.az_el(back_az, -8)
            hb, nb = core.ray(head, d * 3, -d)
            if hb is not None:
                tail = Vector((hb.x * 1.12, hb.y + 0.10, nape))
        el += core.ribbon_lock(head, ctrl + ([tail] if tail is not None else []), 0.10 * sx, 0.07 * sx, 0.05, n=14,
                               lift=0.5, free_tail=1 if tail is not None else 0, taper_at=0.65)
    _finish_hair(ctx, el, hr["color"])
    tc = hr.get("temples")
    if tc:
        el2 = []
        for s_ in (-1, 1):
            for az, e0, e1 in ((70, 34, 4), (84, 30, -2), (98, 28, 0)):
                el2 += core.ribbon_lock(head, [core.az_el(s_ * az, e0), core.az_el(s_ * (az + 14), (e0 + e1) / 2),
                                               core.az_el(s_ * (az + 30), e1)], 0.075 * sx, 0.06 * sx, 0.04, n=10,
                                        lift=0.5)
        _second(ctx, el2, tc, "temples", crevice=hr.get("temple_crevice", "#5A5A62"))


def _curls(ctx):
    """A cloud of copper curls (Mirosya, §7.8: "облако медных кудрей шириной 1.4 W"): a scalp sheet and some 90 small
    curls — each a C of soft balls round a sunk centre — over a cloud that leaves the face open, widest at the sides
    by the ears (the cloud's half width `width` x W / 2 there), a few curls over the forehead; `flat` < 1 presses the
    cloud down (the tired mood: "кудри приплюснуты")."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    flat = hr.get("flat", 1.0)
    width = hr.get("width", 1.4)
    hl = hairline_fn([(0, 0.30), (30, 0.29), (55, 0.22), (80, 0.06), (100, -0.10), (140, -0.24), (180, -0.30)])
    samples, s = core.surface_samples(head, 2000, lambda h, n, d: h.z > hl(h) + 0.01)
    el = core.sheet_elems(samples, s, lambda h, n: 0.05)
    half = width * ctx.W / 2
    rng = ctx.rng
    cr = hr.get("curl", 0.052)
    for d in core.fib_dirs(hr.get("n", 150)):
        az = math.degrees(math.atan2(d.x, -d.y))
        el_ = math.degrees(math.asin(max(-1.0, min(1.0, d.z))))
        if abs(az) < 58 and el_ < 34:          # the face stays open
            continue
        if el_ < core.lerp_table([(0, 20), (60, -6), (90, -38), (130, -44), (180, -40)], abs(az)):
            continue
        hit, nor = core.ray(head, d * 3, -d)
        if hit is None:
            continue
        # out from the scalp: thick at the sides (the 1.4 W width at ear level), less on top and at the back
        side = abs(nor.x)
        out = 0.05 + max(0.0, half - abs(hit.x)) * side * 0.95 * core.smoothstep(-0.45, -0.05, hit.z)
        out *= 1.0 - 0.45 * core.smoothstep(0.15, 0.45, hit.z)      # a low crown: the cloud is wide, not tall
        out *= flat if hit.z > 0.1 else 1.0
        c = hit + nor * out
        if flat < 1.0 and c.z > 0.2:
            c.z = 0.2 + (c.z - 0.2) * flat
        t1 = nor.orthogonal().normalized()
        t1 = (Matrix.Rotation(rng.uniform(0, 2 * math.pi), 3, nor) @ t1).normalized()
        t2 = nor.cross(t1).normalized()
        r = cr * rng.uniform(0.85, 1.2)
        el.append(dict(co=c - nor * r * 0.3, half=r * 0.9, stiff=2.2))
        nl = hr.get("lobes", 5)          # fewer, rounder lobes per curl: big smooth clumps, not a cauliflower (AD)
        for k in range(nl):
            a = math.radians(-40 + 280 * k / max(1, nl - 1) * (4 / 5 if nl == 5 else 1.0))
            el.append(dict(co=c + (t1 * math.cos(a) + t2 * math.sin(a)) * r * 0.85 + nor * r * 0.15,
                           half=r * hr.get("lobe_k", 0.55), stiff=2.8))
        # a filler between the scalp and the curl, so the cloud has no holes
        if out > 0.08:
            el.append(dict(co=hit + nor * out * 0.5, half=min(out * 0.55, 0.14), stiff=2.0))
    # fringe curls along the forehead's edge
    for az in (-36, -20, -4, 12, 28, 42):
        d = core.az_el(az, 33)
        hit, nor = core.ray(head, d * 3, -d)
        if hit is None:
            continue
        c = hit + nor * 0.05 + Vector((0, -0.01, -0.01))
        r = cr * 0.95
        el.append(dict(co=c, half=r * 0.9, stiff=2.2))
        for k in range(4):
            a = math.radians(-30 + 80 * k)
            el.append(dict(co=c + Vector((math.cos(a) * r * 0.8, -0.01, math.sin(a) * r * 0.8)), half=r * 0.5,
                           stiff=2.8))
    _finish_hair(ctx, el, hr["color"], res=hr.get("res", 0.012), signature=True)


def _owl(ctx):
    """Smooth hair swept back with two sharp "owl" tufts wide at the back, turned out 30 deg (Iveta, §7.8: "два острых
    «совиных» пучка широко сзади"): a scalp sheet, broad locks from the hairline back to a low knot at the nape, and
    per side a tapering clump from the back of the crown up and out to a sharp point (leaders may be sharp, §7.2)."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.31), (30, 0.29), (60, 0.20), (80, 0.11), (100, 0.04), (140, -0.14), (180, -0.22)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.015)
    el = core.sheet_elems(samples, s, lambda h, n: 0.045 + 0.02 * core.smoothstep(0.1, 0.45, h.z))
    for az in range(-150, 151, 25):
        e0 = core.lerp_table([(0, 46), (50, 38), (90, 22), (130, 6), (180, 0)], abs(az))
        sg = 1 if az >= 0 else -1
        el += core.ribbon_lock(head, [core.az_el(az, e0), core.az_el(az * 0.7 + sg * 40, 58),
                                      core.az_el(sg * 168, 12)], 0.10 * sx, 0.08 * sx, 0.045, n=12, lift=0.45)
    # a side parting and two broad locks swept across the forehead's top (without them the smooth crown read as a cap)
    for az, e in ((-24, 46), (-50, 34)):
        el += core.ribbon_lock(head, [core.az_el(28, 70), core.az_el(az * 0.4, 60), core.az_el(az, e)], 0.12 * sx,
                               0.10 * sx, 0.05, n=14, lift=0.5)
    tf = hr.get("tufts", {})
    ln = tf.get("len", 0.34) * H
    for sd in (-1, 1):
        rd = core.az_el(sd * tf.get("az", 128), tf.get("el", 40))
        hit, nor = core.ray(head, rd * 3, -rd)
        if hit is None:
            continue
        out = math.radians(tf.get("out", 30))
        d = Vector((sd * math.sin(out) * 1.0, 0.35, math.cos(out))).normalized()
        d = (d + nor * 0.35).normalized()
        pts = [hit - nor * 0.02, hit + nor * 0.05 + d * ln * 0.30, hit + nor * 0.06 + d * ln * 0.65, hit + d * ln]
        el += core.clump(pts, [nor, nor, nor, nor], tf.get("w", 0.13), tf.get("w", 0.13) * 0.7, 0.08, n=22, lift=0.0,
                         taper_at=0.25, tip=0.06, stiff=2.6, flat=0.8)
    o = _finish_hair(ctx, el, hr["color"], signature=True)
    return o


def _straight(ctx):
    """Long straight hair from a parting (Sairin, Vedana, §7.8): locks from the parting over the crown and down the
    sides past the ears and the jaw, their tails hanging straight to rest on the shoulders (z `drop`), the near side
    fuller with a side parting; `across` adds one lock from the parting across the face (the tired mood: "прядь через
    лицо" / "волосы падают на лицо")."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    part = hr.get("part", 0.0)                 # the parting's azimuth (0 centre, + toward the far side)
    hl = hairline_fn([(0, 0.32), (30, 0.30), (60, 0.21), (80, 0.12), (100, 0.04), (140, -0.14), (180, -0.22)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.012)
    el = core.sheet_elems(samples, s, lambda h, n: 0.04 + 0.02 * core.smoothstep(0.1, 0.45, h.z))
    drop = hr.get("drop", -0.66)
    w0 = hr.get("lock_w", 0.10)
    for az in list(range(-165, 166, 15)):
        if abs(az - part) < 6:
            continue
        sg = 1 if az > part else -1
        root = core.az_el(part + sg * 4, 72)
        e_side = core.lerp_table([(0, 38), (40, 34), (70, 22), (100, 6), (180, -6)], abs(az))
        mid = core.az_el(az, e_side)
        low = core.az_el(az + sg * 6, -18 if abs(az) < 120 else -10)
        hb, nb = core.ray(head, low * 3, -low)
        if hb is None:
            continue
        r_ = math.hypot(hb.x, hb.y)
        ang = math.atan2(hb.x, -hb.y)
        out = 1.0 + 0.10 * core.smoothstep(40, 100, abs(az))
        tail_z = drop - 0.10 * core.smoothstep(60, 110, abs(az))
        y_t = -math.cos(ang) * r_ * out + (0.08 if abs(az) > 120 else 0.0)
        tail = Vector((math.sin(ang) * (r_ + 0.06) * out, y_t, tail_z))
        if abs(az) < 50:
            continue        # the front: framed by the side locks, the face stays open
        # (dense samples along the long free tail: 18 left a string of beads, the "cauliflower" of note 3)
        el += core.ribbon_lock(head, [root, mid, low, tail], w0 * sx, w0 * 0.85 * sx, 0.045, n=40, lift=0.45,
                               free_tail=1, taper_at=0.85, wmin=0.06)
    # the fringe sweep from the parting toward the near side, over the forehead's top
    for k, (az, e) in enumerate(((-30, 50), (-55, 40))):
        el += core.ribbon_lock(head, [core.az_el(part - 4, 74), core.az_el(az * 0.5, 62), core.az_el(az, e)],
                               0.12 * sx, 0.10 * sx, 0.045, n=12, lift=0.45)
    if hr.get("across"):
        # one lock off the parting, down across the near brow and eye to the cheek (a strand falling over the face)
        d0 = core.az_el(part - 6, 70)
        hit, nor = core.ray(head, d0 * 3, -d0)
        p1 = core.ray_front(head, -0.06 * sx, ctx.P["eye_z"] + 0.20 * H)
        p2 = core.ray_front(head, -0.20 * sx, ctx.P["eye_z"] - 0.02 * H)
        p3 = core.ray_front(head, -0.30 * sx, ctx.P["eye_z"] - 0.24 * H)
        if hit is not None and all(q[0] is not None for q in (p1, p2, p3)):
            pts = [hit + nor * 0.04, p1[0] + p1[1] * 0.05, p2[0] + p2[1] * 0.06, p3[0] + p3[1] * 0.05]
            el += core.clump(pts, [nor, p1[1], p2[1], p3[1]], 0.07, 0.05, 0.035, n=16, lift=0.0, taper_at=0.6,
                             tip=0.3, stiff=2.6, flat=0.8)
    _finish_hair(ctx, el, hr["color"], res=hr.get("res", 0.012))


def _slick(ctx):
    """Slicked-back hair with a widow's peak (Velian, §7.8: "гладкие тёмно-каштановые волосы с мысом"): a hairline with
    a point at the middle of the forehead and receding corners, thin locks combed straight back close to the head,
    glossy (hair "rough")."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    tbl = hr.get("hairline", [(0, 0.25), (12, 0.30), (30, 0.31), (55, 0.22), (80, 0.13), (105, 0.04),
                              (145, -0.14), (180, -0.22)])
    hl = hairline_fn(tbl)
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.01)
    el = core.sheet_elems(samples, s, lambda h, n: 0.035 + 0.012 * core.smoothstep(0.1, 0.45, h.z))
    for az in range(-160, 161, 16):
        e0 = math.degrees(math.atan2(core.lerp_table(tbl, abs(az)) + 0.02, 0.45))
        sg = 1 if az >= 0 else -1
        el += core.ribbon_lock(head, [core.az_el(az, e0 + 2), core.az_el(az * 0.55 + sg * 60, 62),
                                      core.az_el(sg * 172, 4)], 0.085 * sx, 0.07 * sx, 0.032, n=14, lift=0.35)
    _finish_hair(ctx, el, hr["color"])


def _wild(ctx):
    """Wild long hair (Bjorulf, §7.8: "дикие длинные чёрно-седые волосы"): the long hair swept back (_long) with its
    locks jittered and some sticking out, a few grey streak locks in a second colour."""
    hr = ctx.ch["hair"]
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    rng = ctx.rng
    hl = hairline_fn([(0, 0.32), (30, 0.30), (60, 0.22), (85, 0.12), (110, 0.0), (150, -0.14), (180, -0.20)])
    samples, s = core.surface_samples(head, 2400, lambda h, n, d: h.z > hl(h) + 0.012)
    el = core.sheet_elems(samples, s, lambda h, n: 0.05 + 0.02 * core.smoothstep(0.2, 0.5, h.z))
    drop = hr.get("drop", -0.62)
    streaks = []
    for az in range(-160, 161, 14):
        sg = 1 if az > 0 else -1
        e0 = core.lerp_table([(0, 48), (40, 42), (70, 30), (100, 14), (150, 2)], abs(az))
        if abs(az) < 30:
            # a ragged fringe: short locks hanging forward over the forehead
            tip = core.ray_front(head, math.sin(math.radians(az)) * 0.36 * sx, ctx.P["eye_z"] + 0.30 * H)
            if tip[0] is None:
                continue
            lock = core.ribbon_lock(head, [core.az_el(az + 160 * sg, 70), core.az_el(az, 55), core.az_el(az, e0),
                                           tip[0] + tip[1] * 0.07], 0.08 * sx, 0.05 * sx, 0.04, n=12, lift=0.45,
                                    free_tail=1, taper_at=0.5)
        else:
            back = core.az_el(sg * min(178, abs(az) + 35 + rng.uniform(-10, 10)), rng.uniform(-6, 10))
            hb, nb = core.ray(head, back * 3, -back)
            if hb is None:
                continue
            ang = math.atan2(hb.x, hb.y)
            r_ = math.hypot(hb.x, hb.y)
            fly = rng.uniform(0.04, 0.16) * core.smoothstep(50, 110, abs(az))
            tail = Vector((math.sin(ang) * (r_ + 0.06 + fly), math.cos(ang) * (r_ + 0.02) + 0.04,
                           drop + rng.uniform(-0.06, 0.10)))
            lock = core.ribbon_lock(head, [core.az_el(az, e0), core.az_el((az + back_az(back)) / 2, 44), back, tail],
                                    0.095 * sx, 0.06 * sx, 0.05, n=36, lift=0.45, free_tail=1, taper_at=0.6)
        (streaks if hr.get("streak") and (az // 14) % 4 == 1 and abs(az) > 40 else el).extend(lock)
    _finish_hair(ctx, el, hr["color"])
    if streaks:
        _second(ctx, streaks, hr["streak"], "streaks", crevice=hr.get("crevice"))


def back_az(d):
    return math.degrees(math.atan2(d.x, -d.y))


_P3_STYLES = {"bald": _bald, "mane": _mane, "curls": _curls, "owl": _owl, "straight": _straight, "slick": _slick,
              "wild": _wild}
