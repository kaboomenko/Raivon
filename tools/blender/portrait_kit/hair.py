"""Hair (§7.5 step 3): a thin metaball sheet over the scalp (sheet-solved radii) plus flattened "ribbon locks" laid
over the surface frame from the crown or the parting to the fringe and the nape; tips may leave the scalp (a fringe
over the forehead, a bob's ends). Locks whose root would lie inside a headgear are dropped and 6–10 "escape" locks
grow below its rim (hats come with P2; the kerchief keeps a fringe under its edge). Converted to a mesh, Smooth 2,
no Subsurf (§7.5). Material: object-Z gradient (+8 % L* on top) x AO crevice tint.

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
  fringe   — only what a hood shows: shaggy locks over the brows and at the temples (Vik);
  short    — short hair swept back, culled under a hat, escape locks below its rim (Seir);
  flattop  — a cropped shell filled up to a flat plane with near-vertical walls, a crisp hairline and stubble in
             the shader (Frey);
  ponytail — hair drawn up to a high gather, a fringe to the far side and a tail of 7 clumps arcing over and behind
             the head (Irma);
  bun      — hair swept up to a tall vertical bun coiled round its axis (Vance);
  long     — long hair swept back from a high forehead down behind the shoulders (Rai);
  quiff    — a quiff curling out from under a cap's front edge (Hawk).
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
                         crevice=hr.get("crevice"), stubble=hr.get("stubble", 0.0))


def build_hair(ctx):
    st = ctx.ch["hair"]["style"]
    {"swept": _swept, "kerchief": _kerchief, "bob": _bob, "tufts": _tufts, "fringe": _fringe, "short": _short,
     "flattop": _flattop, "ponytail": _ponytail, "bun": _bun, "long": _long, "quiff": _quiff}[st](ctx)


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
    """Shaggy hair seen only at a hood's opening (§7.6 Vik: "5–7 прядей из капюшона на брови"): a scalp sheet over
    the front (the hood hides the rest) and 5–7 broad locks of uneven length from under the hood's front edge down
    over the forehead to the brows, their tips free and separated; two locks at the temples."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    sx = ctx.P["hx"] / 0.48
    hl = hairline_fn([(0, 0.26), (40, 0.22), (70, 0.12), (90, 0.02), (130, -0.10), (180, -0.20)])
    samples, s = core.surface_samples(head, 2000, lambda h, n, d: h.z > hl(h) + 0.015)
    el = core.sheet_elems(samples, s, lambda h, n: 0.035)
    tip_el = hr.get("tip_el", 30)
    locks = hr.get("locks", [(-42, 0.088, -4, 0.75), (-26, 0.098, 4, 1.1), (-10, 0.10, 10, 1.25), (6, 0.098, 14, 1.0),
                             (22, 0.092, 18, 1.15), (38, 0.085, 20, 0.85)])
    for az, w, sweep, length in locks:
        root = core.az_el(az * 0.8, 62)
        mid = core.az_el(az + sweep * 0.5, 48)
        tip_d = core.az_el(az + sweep, tip_el + 6 * (1.1 - length))
        hit, nor = core.ray(head, tip_d * 3, -tip_d)
        if hit is None:
            continue
        hang = hit + nor * 0.035 + Vector((math.sin(math.radians(az + sweep)) * 0.03, -0.02, -0.07 * length))
        el += core.ribbon_lock(head, [root, mid, tip_d, hang], w * sx, w * 0.78 * sx, 0.048, n=16, lift=0.45,
                               free_tail=1, taper_at=0.86, wmin=0.05)
    for s_ in (-1, 1):
        el += core.ribbon_lock(head, [core.az_el(s_ * 60, 44), core.az_el(s_ * 74, 22), core.az_el(s_ * 80, 4)],
                               0.07 * sx, 0.045 * sx, 0.04, n=10, lift=0.4, taper_at=0.6)
    _finish_hair(ctx, el, hr["color"], cut=False)


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
    """A flat-top crop (§7.6 Frey: "площадка", a 0.035 H shell with a flat top, a crisp hairline, stubble in the
    shader): a sheet whose thickness fills the head's dome up to a flat plane (the square top of her "T"
    signature) and is 0.035 H on the sides; a crisp hairline where the shell thins to 0.3 of itself (a full-thickness
    edge read as a cap's rim); the crown planed off level after meshing."""
    head = ctx.objs["head"]
    hr = ctx.ch["hair"]
    crown = ctx.L["crown"]
    side_t = hr.get("side", 0.035) * H
    z_top = crown.z + hr.get("top", 0.07) * H
    hl = hairline_fn(hr.get("hairline", [(0, 0.31), (30, 0.30), (55, 0.24), (75, 0.15), (95, 0.07), (130, -0.08),
                                         (180, -0.20)]))
    samples, s = core.surface_samples(head, 3200, lambda h, n, d: h.z > hl(h))

    def thick(h, n):
        t = side_t
        if n.z > 0.2:
            # up to the flat plane, but the walls stay near-vertical: the outward reach is held to 1.5 x the side
            # thickness (filling to a box round the skull overhung the temples like a mushroom cap)
            horiz = math.sqrt(max(1e-4, 1 - n.z * n.z))
            t = max(t, min((z_top - h.z) / max(n.z, 0.3), 1.5 * side_t / horiz, hr.get("max_t", 0.2)))
        # crisp but thin at the hairline (a full-thickness edge read as a knitted cap's rim over the forehead)
        return t * (0.3 + 0.7 * core.smoothstep(0.0, 0.05, h.z - hl(h)))
    el = core.sheet_elems(samples, s, thick)
    o = _finish_hair(ctx, el, hr["color"], res=0.010, signature=True, smooth_iter=3)
    # the flat top itself: the metaball sheet rounds every edge, so the crown is planed off at the flat plane (a
    # level "площадка" with a soft-cornered rim, not a dome that reads as a knitted cap)
    flat = z_top - hr.get("plane", 0.02) * H
    to_head = head.matrix_world.inverted() @ o.matrix_world
    back = to_head.inverted()
    for v in o.data.vertices:
        q = to_head @ v.co
        if q.z > flat:
            q.z = flat + (q.z - flat) * hr.get("plane_k", 0.15)
            v.co = back @ q
    o.data.update()
    return o


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
            r = 0.04 + 0.06 * math.sin(math.pi * min(1.0, t * 1.4)) + 0.09 * core.smoothstep(0.6, 1.0, t)
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
    band = core.torus("pony_band", (pts[3] + pts[4]) / 2, 0.06, 0.018,
                      core.principled(ctx, "pony_band", tl.get("band", "#3A3C46"), 0.5, sheen=0.2),
                      nrm=(pts[5] - pts[2]).normalized(), seg=32, rseg=10)
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
