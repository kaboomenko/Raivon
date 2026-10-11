"""Headgear (§7.5 step 8). P1 builds what Bram, Lira and Vega wear in era 1: Lira's kerchief. Hats seated on the hat
ring, brims and visors come with P2 (§7.5: 24 rim samples 0.01 H into the hair, visors down 14 deg).

kerchief — a soft cloth shell over the hair (a metaball sheet sampled on the head above an edge line that runs high
           over the forehead, over the ears and low at the nape; its thickness clears the hair cap), a folded hem
           along its front edge (one clean, smooth rolled rim — no torn hairline, no ribbing), a knot at the back of
           the head and two flat cloth tails with a soft fold sticking out back (her "top back" signature zone, §7.2).
"""
import math

from mathutils import Matrix, Vector

from . import core


def build_headgear(ctx):
    hg = ctx.ch.get("headgear")
    if not hg:
        return
    {"kerchief": kerchief}[hg["kind"]](ctx, hg)


def kerchief(ctx, hg):
    head = ctx.objs["head"]
    edge_tbl = hg.get("edge", [(0, 40), (40, 34), (75, 16), (100, 4), (140, -8), (180, -16)])

    def edge(h):
        az = abs(math.degrees(math.atan2(h.x, -h.y)))
        return core.lerp_table(edge_tbl, az)

    def elev(h):
        return math.degrees(math.atan2(h.z, math.hypot(h.x, h.y)))

    samples, s = core.surface_samples(head, 3600, lambda h, n, d: elev(h) > edge(h))
    th = hg.get("thick", 0.085)
    el = core.sheet_elems(samples, s, lambda h, n: th * (0.7 + 0.3 * core.smoothstep(0, 10, elev(h) - edge(h))),
                          inset=0.02)
    # the folded hem: a soft rolled edge — balls packed closer than their radius, so they fuse into one smooth roll
    # (48 spaced balls read as a ribbed knit band)
    hem = []
    for k in range(160):
        az = -180 + 360 * k / 160
        e = core.lerp_table(edge_tbl, abs(az)) + 2.0
        d = core.az_el(az, e)
        h, n = core.ray(head, d * 3, -d)
        if h is None:
            continue
        hem.append(dict(co=h + n * (th * 0.72), half=th * 0.50, stiff=2.0))
    el += hem
    # the knot at the back of the head (top back) and its two tails, out toward the back (screen left)
    kd = core.az_el(hg.get("knot_az", 178), hg.get("knot_el", 18))
    kh, kn = core.ray(head, kd * 3, -kd)
    knot = kh + kn * (th * 1.3)
    el.append(dict(co=knot, half=(0.07, 0.06, 0.06), stiff=2.4))
    el.append(dict(co=knot + kn * 0.03 + Vector((0.03, 0, 0.0)), half=(0.05, 0.05, 0.05), stiff=2.4))
    m = core.fabric(ctx, "kerchief", hg["color"], z0=-0.2, z1=0.6, rough=0.85, sheen=0.3)
    o = core.mb_mesh(ctx, "Kerchief", el, 0.011, m, smooth_iter=2, name="kerchief")
    ctx.add(o, "hat", head, kind="embed", head=True)    # headgear next to the face: its own group (§7.4 rule)
    ctx.objs["kerchief"] = o
    # tails: two flattened tapered ribbons from the knot, out and back (V), drooping a little
    back = (Vector((kn.x, kn.y, 0)).normalized() * 0.4 + core.world_dir(ctx, (-1.0, 0.35, 0.0), head=True)).normalized()
    tails = []
    ln = hg.get("tail", 0.36)
    side = Vector((0, 0, 1)).cross(back).normalized()
    for k, (up, sw) in enumerate(((0.30, 0.20), (-0.45, -0.16))):
        el2 = []
        prev = knot
        n_ = 30
        for i in range(1, n_ + 1):
            t = i / n_
            # out from the knot, then drooping: soft flat cloth ends that widen toward the tip (a "V" of two ends),
            # with one fold (the end twists a little); samples overlapping, so the cloth is smooth, not ribbed
            p = knot + back * (ln * t) + side * (sw * 0.3 * t) + Vector((0, 0, up * ln * 0.6 * t - 0.16 * t * t))
            w = 0.065 + 0.065 * t
            fwd_ = (p - prev).normalized()
            nrm = side.cross(fwd_).normalized()
            twist = Matrix.Rotation(math.radians(28 * math.sin(math.pi * t) * (1 if k else -1)), 4, "Z").to_quaternion()
            el2.append(dict(co=p, half=(w, 0.016, ln / n_ * 1.6), stiff=2.2,
                            rot=core.frame_quat(fwd_, nrm) @ twist))
            prev = p
        tl = core.mb_mesh(ctx, "Tail%d" % k, el2, 0.008, m, smooth_iter=2, name="kerchief_tail%d" % k)
        ctx.add(tl, "detail:kerchief_tails", o, kind="surface", head=True)
        tails.append(tl)
        ctx.sig_objs.append(tl)
    ctx.details["kerchief_tails"] = 400
    ctx.L["knot"] = knot
