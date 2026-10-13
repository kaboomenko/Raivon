"""Headgear (§7.5 step 8): era 1's kerchief (Lira), hood (Vik), tricorn (Seir), aviator cap with flaps (Hawk),
goggles (Olm's brass pair on the dome, Irma's rubber driving goggles on the hairline, Hawk's on the cap) and circlet
(Rai). Hats are seated on the hair: 24 rim samples cast onto the built hair, the rim 0.01 H into it (§7.5); the hair
under a hat is culled before it is meshed (`plan` -> ctx.hair_cut) so only the escape locks below the rim remain.

hood     — Vik's hood with its soft peak (the peak measured as its own ID region, `_region_slot`);
kerchief — a soft cloth shell over the hair (a metaball sheet sampled on the head above an edge line that runs high
           over the forehead, over the ears and low at the nape; its thickness clears the hair cap), a folded hem
           along its front edge (one clean, smooth rolled rim — no torn hairline, no ribbing), a knot at the back of
           the head and two flat cloth tails with a soft fold sticking out back (her "top back" signature zone, §7.2).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import core
from .core import H


def plan(ctx):
    """Before the hair: what the headgear covers (ctx.hair_cut, a predicate on a head-local point) — the hair builder
    drops the elements inside it (§7.5 step 3) and keeps what lies below the rim (the escape locks)."""
    hg = ctx.ch.get("headgear")
    if not hg:
        return
    kind = hg["kind"]
    if kind in ("tricorn", "bicorne"):
        rz = _rim_fn(ctx, hg)
        ctx.hair_cut = lambda p: p.z > rz(p) + 0.012
    elif kind == "aviator":
        edge = _edge_fn(hg.get("edge", AVIATOR_EDGE))
        ctx.hair_cut = lambda p: _elev(p) > edge(p) + 2.0
    elif kind == "hat" and hg.get("cut_hair", True):
        plan_hat(ctx, hg)
    elif kind == "shell" and hg.get("cut_hair", False):
        edge = _edge_fn(hg.get("edge", [(0, 46), (40, 40), (70, 24), (95, 8), (130, -8), (180, -14)]))
        ctx.hair_cut = lambda p: _elev(p) > edge(p) + hg.get("cut_margin", 4.0)


def build_headgear(ctx):
    hg = ctx.ch.get("headgear")
    if not hg:
        return
    builders = {"kerchief": kerchief, "hood": hood, "tricorn": tricorn, "aviator": aviator, "goggles": goggles_hg,
                "circlet": circlet, "hat": hat, "shell": shell, "visor": visor, "headset": headset,
                "diadem": diadem, "crown": crown, "bicorne": bicorne, "frame": frame_helmet, "earpiece": earpiece}
    builders[hg["kind"]](ctx, hg)
    for extra in hg.get("extra", []):          # a second piece worn with it (Hawk's goggles on the cap, a visor ...)
        builders[extra["kind"]](ctx, extra)


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


def _elev(p):
    return math.degrees(math.atan2(p.z, math.hypot(p.x, p.y)))


def _az(p):
    return math.degrees(math.atan2(p.x, -p.y))


def _edge_fn(tbl):
    def f(p):
        return core.lerp_table(tbl, abs(_az(p)))
    return f


def _surf(ctx):
    """What a headgear sits on: the hair (and its parts) over the head."""
    out = [ctx.objs[k] for k in ("hair", "bun", "ponytail") if ctx.objs.get(k) is not None]
    return out + [ctx.objs["head"]]


# ------------------------------------------------------------------ hood (Vik)
def hood(ctx, hg):
    """A hood (§7.6 Vik: #4E6B3A, shell 0.04 H, edge 0.05 H, a soft peak 0.25 H back): a cloth sheet over the head
    and hair outside the face opening (an edge line high on the forehead, down the cheeks behind the jaw), clearing
    the hair; a rolled edge round the opening; the soft peak — a tapering chain of balls from the crown's back that
    stands `peak` H clear of the hood's own surface, up and back at `peak_dir`, its tip drooping; the lower part
    drapes round the neck to the shoulders (it meets the cloak). The peak is one smooth surface with the hood but
    its own ID region (detail:hood_peak: the faces outside the hood built without it) and the only part of the hood
    in the signature mask."""
    head = ctx.objs["head"]
    hair = ctx.objs.get("hair")
    edge_tbl = hg.get("edge", [(0, 46), (40, 40), (62, 22), (76, -10), (88, -60), (180, -90)])

    def edge(h):
        return core.lerp_table(edge_tbl, abs(_az(h)))
    th = hg.get("thick", 0.075)
    samples, s = core.surface_samples(head, 3600, lambda h, n, d: _elev(h) > edge(h) and h.z > -0.45)

    def thick(h, n):
        t = th
        if hair is not None:
            hh, _ = core.ray(hair, h + n * 0.4, -n, dist=0.6)
            if hh is not None:
                t = max(t, (hh - h).dot(n) + 0.04 * H)
        return t
    el = core.sheet_elems(samples, s, thick, inset=0.02)
    # the rolled edge round the opening
    for k in range(120):
        az = -100 + 200 * k / 119
        e = core.lerp_table(edge_tbl, abs(az)) + 1.5
        d = core.az_el(az, e)
        h, n = core.ray(head, d * 3, -d)
        if h is None or h.z < -0.5:
            continue
        el.append(dict(co=h + n * (thick(h, n) * 0.85), half=hg.get("edge_r", 0.05) * H * 0.6 + 0.02, stiff=2.0))
    # the drape round the neck: rings of balls from the jaw down to the shoulders, open at the front
    for j in range(6):
        f = j / 5
        z = -0.42 - 0.26 * f
        r = 0.36 + 0.14 * f
        for i in range(26):
            a = math.radians(-118 + 236 * i / 25 + 180)
            co = Vector((r * math.sin(a), 0.10 + r * -math.cos(a) * 0.9, z))
            el.append(dict(co=co, half=0.075, stiff=2.0))
    # the peak: a soft tapering cone that leaves the hood's crown at the back and stands `peak` H clear of the hood's
    # own surface (§7.6 "мягкий пик 0.25 H назад"; measured from the base of the cone it stood only 15-20 px past the
    # dome, P2 review), up and back at `peak_dir` (azimuth, elevation in head space: a little toward the near side, so
    # the level 3/4 camera sees it side-on instead of foreshortened behind the head), its tip drooping a little
    pk = hg.get("peak", 0.25) * H
    pd = core.az_el(*hg.get("peak_at", (180, 48)))
    ph, pn = core.ray(head, pd * 3, -pd)
    t_here = thick(ph, pn)
    base = ph + pn * t_here * 0.45
    d = core.az_el(*hg.get("peak_dir", (180, 37)))
    inside = t_here * 0.55 / max(d.dot(pn), 0.35)          # from the base to the hood's outer surface along d
    r0 = hg.get("peak_r", 0.13)
    peak_el = []
    n_pk = 22
    for k in range(n_pk):
        t = k / (n_pk - 1)
        ln = (inside + pk) * t
        # a soft cone: wide where it leaves the hood, its last third bending down toward a rounded tip
        c = base + d * ln + Vector((0, 0, -hg.get("droop", 0.06) * core.smoothstep(0.45, 1.0, t) * t))
        peak_el.append(dict(co=c, half=r0 * (1 - 0.80 * t ** 0.85) + 0.010, stiff=2.0))
    # the fabric gradient (§7.11: 1.05 at the crown down to `shade_low` at the drape round the neck — a lighter low
    # end keeps the drape's shadow under the chin over the albedo floor, §7.4 dark budget)
    if hg.get("camo"):
        m = core.camo_mat(ctx, "hood", hg["color"], hg["camo"], scale=hg.get("camo_scale", 5.0), z0=-0.7, z1=0.6)
    else:
        m = core.grad_mat(ctx, "hood", core.hex_scale(hg["color"], 1.05),
                          core.hex_scale(hg["color"], hg.get("shade_low", 0.92)), -0.7, 0.6, rough=0.85, sheen=0.35)
    o = core.mb_mesh(ctx, "Hood", el + peak_el, 0.013, m, smooth_iter=3, name="hood")
    ctx.add(o, "hat", head, kind="embed", head=True)
    ctx.objs["hood"] = o
    # the peak is one surface with the hood (a smooth metaball union) but its own ID region: the hood's faces outside
    # the same hood built without the peak (a hidden proxy) go to material slot 1 — the ID pass colours them
    # detail:hood_peak and the signature mask takes only them (P-A8 "пик капюшона 1500" and the 48 px signature share
    # measured the whole hood before: every gate passed a peak that hardly showed, P2 review)
    dome = core.mb_mesh(ctx, "HoodDome", el, 0.013, m, smooth_iter=3, name="hood_dome")
    _region_slot(ctx, o, dome, m, "detail:hood_peak", margin=hg.get("peak_margin", 0.012))
    bpy.data.objects.remove(dome, do_unlink=True)
    ctx.details["hood_peak"] = hg.get("min_px", 1500)


def _region_slot(ctx, obj, without, mat, group, margin=0.01, signature=True):
    """Faces of `obj` lying more than `margin` outside the mesh `without` (the same part built without one feature)
    go to material slot 1 (the same material in the beauty render); the ID pass colours that slot `group` and, with
    `signature`, the signature mask takes only that slot (ctx.slot_groups / ctx.sig_slots)."""
    from mathutils.bvhtree import BVHTree
    core.update()
    wm = without.data        # both raw (before their identical Smooth modifiers): like is compared with like
    tree = BVHTree.FromPolygons([v.co.copy() for v in wm.vertices], [tuple(p.vertices) for p in wm.polygons])
    inv = without.matrix_world.inverted() @ obj.matrix_world
    me = obj.data
    if len(me.materials) < 2:
        me.materials.append(mat)
    n_in = 0
    for f in me.polygons:
        c = inv @ f.center
        loc, nor, _, dist = tree.find_nearest(c)
        out = loc is not None and (c - loc).dot(nor) > 0 and dist > margin
        f.material_index = 1 if out else 0
        n_in += out
    me.update()
    ctx.slot_groups = dict(getattr(ctx, "slot_groups", {}), **{obj.name: {1: group}})
    if signature:
        ctx.sig_slots = dict(getattr(ctx, "sig_slots", {}), **{obj.name: {1}})
    return n_in


# ------------------------------------------------------------------ tricorn (Seir)
def _rim_fn(ctx, hg):
    """The hat's rim height round the head (head-local z as a function of the point's azimuth): the hat ring of the
    head's landmarks raised / lowered by rim_dz, tilted back by `tilt` degrees."""
    ring = ctx.L["hat_ring"]
    dz = hg.get("rim_dz", 0.0)
    tilt = math.radians(hg.get("tilt", 0.0))
    tbl = sorted((_az(p), p.z + dz + math.sin(tilt) * p.y) for p in ring)
    tbl = [(a - 360, z) for a, z in tbl[-3:]] + tbl + [(a + 360, z) for a, z in tbl[:3]]

    def f(p):
        return core.lerp_table(tbl, _az(p))
    return f


def tricorn(ctx, hg):
    """A tricorn (§7.6 Seir era 1: a plain felt tricorn with a white edge): a crown dome seated on the hair (24 rim
    samples cast onto the built hair, the rim 0.01 H into it) and the brim turned up into three walls whose top edge
    is a rounded triangle in plan — a corner at the front, two at the back sides — 0.035 H felt, bevelled, a white
    tape along the edge."""
    surf = _surf(ctx)
    rz = _rim_fn(ctx, hg)
    n = 96
    base, dirs = [], []
    seat_hits = 0
    for i in range(n):
        az = -180 + 360 * i / n
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.0))
        z = rz(Vector((d.x, d.y, 0.0)) * 0.4)
        h, nn, ob = core.ray_any(surf, Vector((0, 0.03, z)) + d * 2.0, -d)
        if h is None:
            h = Vector((0, 0.03, z)) + d * 0.45
        else:
            seat_hits += 1
        base.append(h - d * 0.01 * H)
        dirs.append(d)
    c = sum(base, Vector()) / n
    crown_top = max(p.z for p in base) + hg.get("crown", 0.20) * H
    a0 = math.radians(hg.get("corner_az", 0.0))
    e_mid, e_cor = hg.get("mid", 0.02), hg.get("corner", 0.24)
    hw = hg.get("wall", 0.19) * H
    felt = core.fabric(ctx, "tricorn", hg["color"], z0=c.z - 0.05, z1=crown_top, rough=0.85, sheen=0.3)
    bm = bmesh.new()
    rows = []
    nv = 8
    tops = []
    nc = hg.get("corners", 3)                 # 3: a tricorn; 2 at the sides: a bicorne worn crosswise
    wc = hg.get("wall_corner", 1.10)          # the wall's height at a corner (x `wall`): a bicorne's points are low
    for i in range(n):
        az = math.radians(-180 + 360 * i / n)
        w = ((math.cos(nc * (az - a0)) + 1) / 2) ** 2.2
        ext = e_mid + (e_cor - e_mid) * w
        r = (base[i] - c).to_2d().length
        top = Vector((c.x + dirs[i].x * (r + ext), c.y + dirs[i].y * (r + ext), base[i].z + hw * (1.0 + (wc - 1.0) * w)))
        tops.append(top)
    for j in range(nv + 1):
        f = j / nv
        row = []
        for i in range(n):
            b, t = base[i], tops[i]
            # the wall curves out of the rim and stands up (a concave flare)
            p = b.lerp(t, f)
            p.z = b.z + (t.z - b.z) * (f ** 0.85)
            out = (t - b).to_2d()
            p.x = b.x + out.x * (f ** 1.6)
            p.y = b.y + out.y * (f ** 1.6)
            row.append(bm.verts.new(p))
        rows.append(row)
    for j in range(nv):
        for i in range(n):
            ii = (i + 1) % n
            bm.faces.new((rows[j][i], rows[j][ii], rows[j + 1][ii], rows[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    brim = core.mesh_obj("tricorn_brim", bm)
    core.solidify(brim, max(0.035 * H, 0.036), offset=0.0)
    core.bevel(brim, 0.008, 2)
    core.finish(brim, felt, sub=2)
    ctx.add(brim, "hat", ctx.objs.get("hair") or ctx.objs["head"], kind="surface", head=True)
    # the crown: a dome from the rim to crown_top
    bm = bmesh.new()
    rows = []
    for j in range(10):
        f = j / 9
        row = []
        for i in range(n):
            b = base[i]
            r = (b - c).to_2d()
            k = math.cos(f * math.pi / 2) ** 0.55
            row.append(bm.verts.new((c.x + r.x * k, c.y + r.y * k, b.z + (crown_top - b.z) * math.sin(f * math.pi / 2))))
        rows.append(row)
    for j in range(9):
        for i in range(n):
            ii = (i + 1) % n
            bm.faces.new((rows[j][i], rows[j][ii], rows[j + 1][ii], rows[j + 1][i]))
    bm.faces.new(rows[-1][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    crown = core.mesh_obj("tricorn_crown", bm)
    core.solidify(crown, 0.03, offset=-1.0)
    core.finish(crown, felt, sub=hg.get("crown_sub", 2))      # Seir: 1 (P-A10's 500k triangles with his hand)
    ctx.add(crown, "hat", brim, kind="embed", head=True)
    # the white tape along the walls' top edge
    tape = core.curve("tricorn_tape", tops + tops[:1], [1.0] * (n + 1), hg.get("tape", 0.022),
                      core.fabric(ctx, "tricorn_tape", hg.get("trim", "#F2F2F2"), rough=0.7, sheen=0.3), order=3,
                      kind="POLY")
    ctx.add(tape, "hat", brim, kind="embed", head=True)
    if hg.get("tape2"):
        # a second, inner galloon line (Seir E2 "треуголка с золотым галуном")
        t2 = [b.lerp(t, 0.82) for b, t in zip(base, tops)]
        tp2 = core.curve("tricorn_tape2", t2 + t2[:1], [1.0] * (n + 1), hg.get("tape", 0.022) * 0.7,
                         core.fabric(ctx, "tricorn_tape", hg.get("trim", "#F2F2F2"), rough=0.7, sheen=0.3), order=3,
                         kind="POLY")
        ctx.add(tp2, "hat", brim, kind="embed", head=True)
    for bg in ([hg["badge"]] if hg.get("badge") else []):
        a = math.radians(bg.get("az", 0.0))
        dd = Vector((math.sin(a), -math.cos(a), 0.0))
        zc = base[0].z + hw * bg.get("g", 0.55)
        zc = sum(b.z for b in base) / n + hw * bg.get("g", 0.55)
        hit, nrm = core.ray(brim, Vector((c.x, c.y, zc)) + dd * 2.0, -dd)
        if hit is not None:
            emblem(ctx, bg, hit, nrm, brim, "hat")
    ctx.sig_objs += [brim, crown, tape]
    ctx.L["hat_seat_hits"] = seat_hits
    ctx.hat = dict(base=base, top=tops)


# ------------------------------------------------------------------ aviator cap (Hawk)
AVIATOR_EDGE = [(0, 47), (35, 42), (60, 28), (78, 6), (92, -16), (120, -24), (180, -26)]


def aviator(ctx, hg):
    """A leather aviator cap (§7.6 Hawk era 1: "кожаная шапка с клапанами", #7A5133, fur #EDE3D0 at the face): a
    leather sheet hugging the cranium and the hair above an edge line (high on the forehead, down in front of the
    ears, low at the nape), the ear flaps of his signature — turned up and out like small wings, or with
    flaps["down"] hanging over the ears, lining inside (Hawk era 1: up they read as horns, P2) — a fluffy cream fur
    roll along the face edge; goggles go on it (hg["extra"])."""
    head = ctx.objs["head"]
    hair = ctx.objs.get("hair")
    edge = _edge_fn(hg.get("edge", AVIATOR_EDGE))
    samples, s = core.surface_samples(head, 3600, lambda h, n, d: _elev(h) > edge(h))
    th = hg.get("thick", 0.06)

    def thick(h, n):
        t = th
        if hair is not None:
            hh, _ = core.ray(hair, h + n * 0.4, -n, dist=0.6)
            if hh is not None:
                t = max(t, (hh - h).dot(n) + 0.03 * H)
        return t * (0.75 + 0.25 * core.smoothstep(0, 8, _elev(h) - edge(h)))
    el = core.sheet_elems(samples, s, thick, inset=0.02)
    leather = core.grad_mat(ctx, "cap", core.hex_scale(hg["color"], 1.08), core.hex_scale(hg["color"], 0.9), -0.3, 0.6,
                            rough=0.5, coat=0.15)
    cap = core.mb_mesh(ctx, "Cap", el, 0.011, leather, smooth_iter=3, name="cap")
    ctx.add(cap, "hat", head, kind="embed", head=True)
    ctx.objs["cap"] = cap
    ctx.sig_objs.append(cap)
    # the flaps: a rounded leather plate each side, hinged at the ear's top, folded up and out
    fl = hg.get("flaps", {})
    for side in (-1, 1):
        ear = ctx.L["ear_" + ("near" if side < 0 else "far")][0]
        if ear is None:
            continue
        hh_, nh_ = core.ray(cap, Vector((side * 2.0, ear.y + 0.02, ear.z + 0.05)), (-side, 0, 0))
        hinge = (hh_ - nh_ * 0.02) if hh_ is not None else Vector((ear.x + side * 0.08, ear.y, ear.z + 0.05))
        ang = math.radians(fl.get("out", 48))
        outv = Vector((side * math.cos(ang), 0.10, math.sin(ang))).normalized()
        L_, W_ = fl.get("len", 0.25), fl.get("w", 0.19)
        el2 = []
        face_n = Vector((0.0, -1.0, 0.0))            # the flap's flat side toward the front: a wing, not a stick
        if fl.get("down"):
            # hanging down over the ear against the side of the head, a little out at the bottom (a flying cap's
            # ear flap; turned up and out like wings they read as horns or ears, P2 review)
            outv = Vector((side * fl.get("splay", 0.22), 0.06, -1.0)).normalized()
            face_n = Vector((side, 0.0, 0.0))
            hinge = hinge + Vector((side * 0.012, 0.0, 0.04))
        for k in range(7):
            t = k / 6
            c = hinge + outv * (L_ * t)
            w_ = W_ * (0.75 + 0.25 * math.sin(math.pi * min(1.0, t * 1.2)))
            el2.append(dict(co=c, half=(w_ * 0.5, 0.024, 0.05), stiff=2.4, rot=core.frame_quat(outv, face_n)))
        flap = core.mb_mesh(ctx, "Flap%+d" % side, el2, 0.008, leather, smooth_iter=2, name="flap%+d" % side)
        ctx.add(flap, "hat", cap, kind="surface", head=True)
        ctx.sig_objs.append(flap)
        # its fur lining shows on the turned-up face
        el3 = []
        for k in range(6):
            t = (k + 0.5) / 6
            # turned up: the lining on the face toward the camera; hanging down: inside, peeking at the edges
            c = hinge + outv * (L_ * t) + face_n * (-0.016 if fl.get("down") else 0.024)
            el3.append(dict(co=c, half=(W_ * 0.36, 0.02, 0.04), stiff=2.4, rot=core.frame_quat(outv, face_n)))
        fm = core.hair_mat(ctx, "cap_fur", hg.get("fur", "#EDE3D0"), -0.3, 0.5, crevice=hg.get("fur_crevice", "#B8A890"))
        lin = core.mb_mesh(ctx, "Lin%+d" % side, el3, 0.008, fm, smooth_iter=2, name="flapfur%+d" % side)
        ctx.add(lin, "detail:" + hg.get("fur_detail", "fur"), flap, kind="embed", head=True)
    if not hg.get("fur_roll", True):
        # (a leather flying helmet without the fur at the face: Hawk E2)
        ctx.details["helmet"] = hg.get("min_px", 4000)
        ctx.detail_groups = dict(getattr(ctx, "detail_groups", {}), helmet="hat")
        return
    # the fur roll along the face edge (fluffy: balls packed along the edge plus soft clumps)
    elf = []
    edge_tbl = hg.get("edge", AVIATOR_EDGE)
    for k in range(90):
        az = -95 + 190 * k / 89
        e = core.lerp_table(edge_tbl, abs(az)) + 1.0
        d = core.az_el(az, e)
        h, n = core.ray(head, d * 3, -d)
        if h is None:
            continue
        t = thick(h, n)
        r = hg.get("fur_r", 0.045) * (1.0 + 0.12 * math.sin(k * 1.7))
        elf.append(dict(co=h + n * (t * 0.8), half=r, stiff=2.0))
    fm = core.hair_mat(ctx, "cap_fur", hg.get("fur", "#EDE3D0"), -0.3, 0.5, crevice=hg.get("fur_crevice", "#B8A890"))
    fur = core.mb_mesh(ctx, "CapFur", elf, 0.009, fm, smooth_iter=2, name="cap_fur")
    ctx.add(fur, "detail:" + hg.get("fur_detail", "fur"), cap, kind="embed", head=True)
    ctx.details[hg.get("fur_detail", "fur")] = hg.get("fur_px", 2500)
    ctx.details["helmet"] = hg.get("min_px", 4000)
    ctx.detail_groups = dict(getattr(ctx, "detail_groups", {}), helmet="hat")   # the cap is the "hat" ID group


# ------------------------------------------------------------------ goggles (Olm, Irma, Hawk)
def goggles_hg(ctx, hg):
    """Goggles worn up on the head (§7.6): two cups at (az, el) +- spread on the head (or the hair / the cap), each a
    short cylinder along the surface normal tipped up by `tilt`, a rim and a lens (glass, tinted), a bridge; a strap
    round the head over the hair. style "brass" (Olm: round lenses 0.22 H, rims 0.03 H, a flip-up loupe 0.10 H),
    "rubber" (Irma: oval #2E2E34 rubber cups, orange lenses at 60 %), "aviator" (Hawk: sky lenses, brass rims)."""
    head = ctx.objs["head"]
    surf = [ctx.objs[k] for k in ("cap", "hair") if ctx.objs.get(k) is not None] + [head]
    style = hg.get("style", "brass")
    d_lens = hg.get("lens", 0.22) * H
    rim_t = hg.get("rim", 0.03) * H
    el0 = hg.get("el", 42)
    spread = hg.get("spread", 17)
    rim_col = hg.get("rim_color", "#C9A24A" if style != "rubber" else "#2E2E34")
    rim_m = (core.principled(ctx, "goggle_rim", rim_col, rough=0.32, metal=hg.get("metallic", 0.55)) if style != "rubber"
             else core.principled(ctx, "goggle_rim", rim_col, rough=0.55, coat=0.2))
    lens_col = hg.get("lens_color", "#BFE0EE")
    # E4's HUD lenses glow softly (<= 0.6, §7.4 "HUD-линзы ≤ 0.6")
    lens_m = core.principled(ctx, "goggle_lens", lens_col, rough=0.08, coat=0.6, spec=0.8,
                             emit=lens_col if hg.get("lens_glow") else None, es=hg.get("lens_glow", 0.0))
    grp = "detail:" + hg.get("detail", "goggles")
    centres = []
    cups = []
    oval = hg.get("oval", 1.0)
    for s_ in (-1, 1):
        az = hg.get("az", 0.0) + s_ * spread
        d = core.az_el(az, el0)
        h, n, ob = core.ray_any(surf, d * 3, -d)
        if h is None:
            continue
        nrm = (n + Vector((0, 0, hg.get("tilt", 0.35)))).normalized()
        depth = hg.get("depth", 0.07)
        c = h + nrm * (depth * 0.5 - 0.01)
        cup = core.cylinder("goggle_cup%+d" % s_, c, d_lens / 2 + rim_t * 0.4, depth, rim_m, nrm=nrm, verts=40,
                            bev=0.012)
        cup.scale = (1.0, oval, 1.0) if oval != 1.0 else (1, 1, 1)
        ctx.add(cup, grp, ob, kind="surface", head=True)
        cups.append(cup)
        front = c + nrm * (depth * 0.5)
        ring = core.torus("goggle_rim%+d" % s_, front, d_lens / 2, rim_t / 2, rim_m, nrm=nrm, seg=40, rseg=12)
        if oval != 1.0:
            ring.scale = (1.0, oval, 1.0)
        ctx.add(ring, grp, cup, kind="surface", head=True)
        lens = core.uvsphere("goggle_lens%+d" % s_, front - nrm * 0.004, (d_lens / 2 * 0.95, d_lens / 2 * 0.95 * oval,
                                                                           0.02), lens_m, 32, 12)
        core.align_z(lens, nrm)
        ctx.add(lens, grp, cup, kind="embed", head=True)
        # a highlight streak on the lens
        centres.append((front, nrm, c))
    if len(centres) == 2:
        a, b = centres[0][0], centres[1][0]
        mid = (a + b) / 2
        hm, nm_, _ = core.ray_any(surf, mid + (centres[0][1] + centres[1][1]).normalized() * 2,
                                  -(centres[0][1] + centres[1][1]).normalized())
        top = hm + nm_ * 0.025 if hm is not None else mid
        br = core.curve("goggle_bridge", [a, top, b], [1, 1, 1], rim_t * 0.45, rim_m, order=3)
        ctx.add(br, grp, cups[0], kind="embed", head=True)
        # the strap round the head through the cups' outer sides, over the hair
        pts, nrs, hosts = [], [], []
        zc = (centres[0][2].z + centres[1][2].z) / 2 - 0.02
        for k in range(40):
            az = hg.get("az", 0.0) + spread + 22 + (360 - 2 * spread - 44) * k / 39
            dd = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.0))
            el_ = el0 - 6 - 18 * math.sin(math.pi * k / 39) * hg.get("strap_drop", 1.0)
            d3 = core.az_el(az, el_)
            h, n, ob_ = core.ray_any(surf, d3 * 3, -d3)
            if h is not None:
                pts.append(h + n * 0.012)
                nrs.append(n)
                hosts.append(ob_)
        if len(pts) > 4:
            st = core.ribbon_mesh("goggle_strap", pts, hg.get("strap_w", 0.055), normals=[Vector((0, 0, 1))] * len(pts))
            core.solidify(st, 0.016, offset=0.0)
            core.finish(st, core.principled(ctx, "goggle_strap", hg.get("strap", "#5A3A22"), rough=0.5, coat=0.1),
                        sub=1)
            host = max(set(hosts), key=hosts.count) if hosts else head
            ctx.add(st, grp, host, kind="embed", head=True)
    if hg.get("loupe") and centres:
        # the flip-up loupe: a small lens on a hinge at the near cup's top, folded up over it
        f, nrm, c = centres[0]
        upv = (Vector((0, 0, 1)) - nrm * nrm.z).normalized()
        lr = hg["loupe"] * H / 2
        hinge = f + upv * (d_lens / 2 + rim_t * 0.4)
        ln_n = (nrm * 0.35 + upv * 0.94).normalized()
        lc = hinge + (upv * 0.6 - nrm * 0.25).normalized() * (lr + 0.01)
        hg_ = core.cylinder("goggle_hinge", hinge, rim_t * 0.35, 0.05, rim_m, nrm=nrm.cross(upv).normalized(), verts=12)
        ctx.add(hg_, grp, cups[0], kind="embed", head=True)
        lp = core.torus("goggle_loupe", lc, lr, rim_t * 0.38, rim_m, nrm=ln_n, seg=32, rseg=10)
        ln = core.uvsphere("goggle_loupe_lens", lc, (lr * 0.9, lr * 0.9, 0.012), lens_m, 24, 8)
        core.align_z(ln, ln_n)
        ctx.add(ln, grp, lp, kind="embed", head=True)
        v_ = hinge - lc
        v_ = (v_ - ln_n * v_.dot(ln_n)).normalized() * lr        # the point of the ring nearest the hinge
        arm = core.curve("goggle_loupe_arm", [hinge, lc + v_], [1, 1], rim_t * 0.3, rim_m, order=2)
        ctx.add(arm, grp, hg_, kind="embed", head=True)
        ctx.add(lp, grp, arm, kind="embed", head=True)
    ctx.details[hg.get("detail", "goggles")] = hg.get("min_px", 1200)
    if hg.get("signature"):
        # the whole pair (cups, rims, lenses, bridge, strap, loupe): rims alone left holes in the 48 px signature
        # mask (Olm: 7.5 % of the head zone, P-A3 needs 8 %)
        ctx.sig_objs += [o for o in bpy.context.scene.objects if o.name.startswith("goggle_")]


# ------------------------------------------------------------------ circlet (Rai)
def circlet(ctx, hg):
    """A silver circlet (§7.6 Rai: a band 0.06 H with a hex raivite 0.12 H on the brow): a band round the head over
    the hair on a plane tilted down to the back, cast onto the hair; a hexagonal stone in a silver bezel at the front,
    its core emitting <= 2.0 and staying blue (§7.4)."""
    surf = _surf(ctx)
    head = ctx.objs["head"]
    w = hg.get("w", 0.06) * H
    e_front, e_back = hg.get("el", (34, 14))
    pts, nrs = [], []
    for k in range(73):
        az = -180 + 360 * k / 72
        e = e_back + (e_front - e_back) * (math.cos(math.radians(az)) + 1) / 2
        d = core.az_el(az, e)
        h, n, _ = core.ray_any(surf, d * 3, -d)
        if h is not None:
            pts.append(h + n * 0.008)
            nrs.append(n)
    silver = core.principled(ctx, "circlet", hg.get("color", "#C8CCD4"), rough=0.3, metal=0.55, coat=0.2)
    band = core.ribbon_mesh("circlet", pts, w, normals=[Vector((0, 0, 1))] * len(pts))
    core.solidify(band, 0.014, offset=0.0)
    core.bevel(band, 0.004, 2)
    core.finish(band, silver, sub=1)
    ctx.add(band, "metal", ctx.objs.get("hair") or head, kind="embed", head=True)
    d = core.az_el(0, e_front)
    h, n, ob = core.ray_any(surf, d * 3, -d)
    if h is not None:
        r = hg.get("stone", 0.12) * H / 2
        bez = core.cylinder("circlet_bezel", h + n * 0.02, r * 1.22, 0.03, silver, nrm=n, verts=6, bev=0.006)
        ctx.add(bez, "metal", band, kind="surface", head=True)
        gem = core.principled(ctx, "raivite", "#3A8DFF", rough=0.15, coat=0.6, emit="#3A8DFF",
                              es=hg.get("emit", 1.6))
        st = core.cylinder("circlet_raivite", h + n * 0.04, r, 0.03, gem, nrm=n, verts=6, bev=0.008)
        ctx.add(st, "detail:" + hg.get("detail", "raivite"), bez, kind="surface", head=True)
        ctx.details[hg.get("detail", "raivite")] = hg.get("min_px", 150)


# ================================================================== P3: era and leader headgear (§7.6 Э2–Э4, §7.8, §7.10)
def _seat_ring(ctx, hg, n=72):
    """The seat of a rigid hat (§7.5 step 8): at n azimuths a ray from the hat's axis out to the hair (or the head) on
    the hat ring's plane (hat_ring + rim_dz, tilted by `tilt`), smoothed to 3 harmonics (an ovoid that hugs the hair,
    not every lock's bump) and taken 0.01 H into the hair. -> (centre, [(az deg, r, z)])."""
    surf = _surf(ctx)
    rz = _rim_fn(ctx, hg)
    cy = hg.get("cy", 0.03)
    raw = []
    for i in range(n):
        az = -180 + 360 * i / n
        d = Vector((math.sin(math.radians(az)), -math.cos(math.radians(az)), 0.0))
        z = rz(d * 0.4)
        h, nn, ob = core.ray_any(surf, Vector((0, cy, z)) + d * 2.0, -d)
        r = (Vector((h.x, h.y - cy, 0.0)).length if h is not None else 0.42)
        raw.append((az, r, z))
    # 3-harmonic fit of r(az) and z(az)
    def fit(vals):
        a0 = sum(vals) / n
        cs = []
        for k in (1, 2, 3):
            ak = 2 / n * sum(v * math.cos(math.radians(k * az)) for (az, _, _), v in zip(raw, vals))
            bk = 2 / n * sum(v * math.sin(math.radians(k * az)) for (az, _, _), v in zip(raw, vals))
            cs.append((k, ak, bk))
        return lambda az: a0 + sum(ak * math.cos(math.radians(k * az)) + bk * math.sin(math.radians(k * az))
                                   for k, ak, bk in cs)
    fr = fit([r for _, r, _ in raw])
    fz = fit([z for _, _, z in raw])
    into = hg.get("into", 0.01) * H
    ring = [(az, fr(az) - into + hg.get("r_add", 0.0), fz(az)) for az, _, _ in raw]
    return Vector((hg.get("cx", 0.0), cy, 0.0)), ring


def _hat_mat(ctx, hg, name, col=None, kind=None):
    col = col or hg["color"]
    kind = kind or hg.get("mat", "fabric")
    if kind == "metal":
        return core.principled(ctx, name, col, rough=hg.get("rough", 0.32), metal=hg.get("metallic", 0.55),
                               coat=hg.get("coat", 0.2))
    if kind == "painted":          # §7.7 E4 painted plates: roughness 0.45, metallic 0.25
        return core.principled(ctx, name, col, rough=0.45, metal=0.25, coat=0.25)
    if kind == "leather":
        return core.grad_mat(ctx, name, core.hex_scale(col, 1.08), core.hex_scale(col, 0.9), -0.3, 0.8, rough=0.5,
                             coat=0.15)
    if kind == "fur":
        return core.hair_mat(ctx, name, col, 0.1, 0.9, dark=hg.get("fur_dark"), light=hg.get("fur_light"),
                             crevice=hg.get("fur_crevice"), rough=0.8)
    if kind == "velvet":
        return core.grad_mat(ctx, name, core.hex_scale(col, 1.08), core.hex_scale(col, 0.88), 0.1, 0.9, rough=0.85,
                             sheen=0.6)
    return core.grad_mat(ctx, name, core.hex_scale(col, 1.06), core.hex_scale(col, 0.9), 0.1, 0.9, rough=0.85,
                         sheen=0.3)


def plan_hat(ctx, hg):
    rz = _rim_fn(ctx, hg)
    cut = hg.get("cut", 0.012)
    ctx.hair_cut = lambda p: p.z > rz(p) + cut


def hat(ctx, hg):
    """A rigid hat seated on the hair (§7.5 step 8): its crown lofted from the seat ring (_seat_ring) up to a top
    plane `h` H over the ring's highest point (tilted `top_tilt` deg, + back), the rows given by `profile` [(g, r_k)]
    (g: 0 seat .. 1 top, r_k: x the seat's radius; a dome closes at r_k 0); a flat top cap unless the profile closes;
    a band (`band`: height H, colour); a brim (`brim`: {"w": H, "ang": deg + up, "front": half-angle of a visor or
    None for all round, "up_sides": deg the sides curl up}) — visors 14 deg down (§7.5); an emblem on the front
    (`badge`). Shako, top hat, toque, peaked cap, fur colpack, helmets (dome + brim), beret, side cap."""
    c, ring = _seat_ring(ctx, hg)
    n = len(ring)
    prof = hg.get("profile", [(0.0, 1.0), (1.0, 1.0)])
    zmax = max(z for _, _, z in ring)
    top_z = zmax + hg.get("h", 0.20) * H
    tt = math.radians(hg.get("top_tilt", 0.0))
    side_tilt = math.radians(hg.get("side_tilt", 0.0))
    sq = hg.get("squash", (1.0, 1.0))       # (x, y) scale of the crown above the seat (a side cap: narrow, long)

    def top_at(x, y):
        return top_z + math.tan(tt) * y + math.tan(side_tilt) * x

    mat = _hat_mat(ctx, hg, "hat_" + hg.get("id", hg["kind"]))
    bm = bmesh.new()
    rows = []
    for g, rk in prof:
        row = []
        for az, r, z in ring:
            a = math.radians(az)
            dx, dy = math.sin(a), -math.cos(a)
            k = 1.0 + (rk - 1.0) * 1.0
            sx_ = 1.0 + (sq[0] - 1.0) * g
            sy_ = 1.0 + (sq[1] - 1.0) * g
            x, y = c.x + dx * r * k * sx_, c.y + dy * r * k * sy_
            zz = z + (top_at(x, y) - z) * (g ** hg.get("rise", 1.0))
            row.append(bm.verts.new((x, y, zz)))
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    closed = prof[-1][1] < 0.05
    if not closed:
        ctr = bm.verts.new((c.x, c.y, top_at(c.x, c.y) + hg.get("top_dome", 0.0)))
        for i in range(n):
            bm.faces.new((rows[-1][i], rows[-1][(i + 1) % n], ctr))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    crown = core.mesh_obj("hat_crown", bm)
    core.solidify(crown, hg.get("wall", 0.03), offset=-1.0)
    core.finish(crown, mat, sub=hg.get("sub", 2))
    parent = ctx.objs.get("hair") or ctx.objs["head"]
    grp = "detail:" + hg["detail"] if hg.get("detail") else "hat"
    ctx.add(crown, grp, parent, kind="surface", head=True)
    ctx.objs["hat"] = crown
    ctx.sig_objs += [crown] if hg.get("signature") else []
    if hg.get("detail"):
        ctx.details[hg["detail"]] = hg.get("min_px", 1500)
    objs = [crown]
    # the band round the base
    bd = hg.get("band")
    if bd:
        bh = bd.get("h", 0.06) * H
        bmat = _hat_mat(ctx, dict(hg, **bd), "hatband_" + hg.get("id", hg["kind"]), bd["color"], bd.get("mat", "fabric"))
        bm = bmesh.new()
        brs = []
        for f in (0.0, 0.5, 1.0):
            row = []
            for az, r, z in ring:
                a = math.radians(az)
                dx, dy = math.sin(a), -math.cos(a)
                # on the crown's wall at this height (the crown widens / tilts: follow its first rows)
                g = 0.0
                hh = z + bh * f
                kk = 1.0 + (prof[1][1] - 1.0) * min(1.0, (bh * f) / max(1e-6, (top_z - z) * prof[1][0])) if len(prof) > 1 else 1.0
                row.append(bm.verts.new((c.x + dx * (r * kk + bd.get("out", 0.008)), c.y + dy * (r * kk + bd.get("out", 0.008)),
                                         hh)))
            brs.append(row)
        for r0, r1 in zip(brs, brs[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        band = core.mesh_obj("hat_band", bm)
        core.solidify(band, 0.014, offset=1.0)
        core.finish(band, bmat, sub=1)
        ctx.add(band, grp, crown, kind="embed", head=True)
        objs.append(band)
    # the brim
        # (a visor: the front only, `front` half-angle; all round otherwise)
    br = hg.get("brim")
    if br:
        w = br.get("w", 0.06) * H
        bmat = _hat_mat(ctx, dict(hg, **br), "hatbrim_" + hg.get("id", hg["kind"]), br.get("color", hg["color"]),
                        br.get("mat", hg.get("mat", "fabric")))
        bm = bmesh.new()
        brs = []
        front = br.get("front")
        for f in (0.0, 0.33, 0.66, 1.0):
            row = []
            for az, r, z in ring:
                a = math.radians(az)
                dx, dy = math.sin(a), -math.cos(a)
                if front is not None:
                    ww = w * core.smoothstep(front + 18, front - 4, abs(az))
                else:
                    ww = w * (1.0 + br.get("front_k", 0.0) * max(0.0, math.cos(a)))
                ang = math.radians(br.get("ang", 0.0) + br.get("up_sides", 0.0) * abs(math.sin(a)) ** 2)
                rr = r + br.get("out", -0.012) + ww * f * math.cos(ang)      # its root inside the crown's wall
                zz = z + br.get("dz", 0.0) * H + ww * f * math.sin(ang) - (0.0 if front is None else 0.0)
                row.append(bm.verts.new((c.x + dx * rr, c.y + dy * rr, zz)))
            brs.append(row)
        for r0, r1 in zip(brs, brs[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        brim = core.mesh_obj("hat_brim", bm)
        core.solidify(brim, br.get("t", 0.026), offset=0.0)
        core.finish(brim, bmat, sub=1)
        core.bevel(brim, 0.006, 2)
        ctx.add(brim, grp, crown, kind="embed", head=True)
        objs.append(brim)
    # the emblem on the front of the crown
    for bg in ([hg["badge"]] if hg.get("badge") else []) + hg.get("badges", []):
        g = bg.get("g", 0.45)
        az = bg.get("az", 0.0)
        a = math.radians(az)
        dd = Vector((math.sin(a), -math.cos(a), 0.0))
        zz = core.lerp_table([(q[0], q[2]) for q in ring], az)
        zz = zz + (top_at(0, -0.4) - zz) * g
        hit, nrm = core.ray(crown, Vector((c.x, c.y, zz)) + dd * 2.0, -dd)
        if hit is not None:
            emblem(ctx, bg, hit, nrm, crown, grp if not bg.get("detail") else "detail:" + bg["detail"])
    if hg.get("tassel"):
        _tassel(ctx, hg["tassel"], crown, c, top_at)
    cs = hg.get("chinstrap")
    if cs:
        # a chin strap from the brim's sides down to the jaw (Bram E3: "ремешок уходит в бороду")
        sm = core.principled(ctx, "chinstrap", cs.get("color", "#5A3A22"), rough=0.5, coat=0.1)
        head = ctx.objs["head"]
        for sd in (-1, 1):
            az = sd * cs.get("az", 80)
            a = math.radians(az)
            zr = core.lerp_table([(q[0], q[2]) for q in ring], az)
            rr = core.lerp_table([(q[0], q[1]) for q in ring], az)
            p0 = Vector((c.x + math.sin(a) * (rr + 0.01), c.y - math.cos(a) * (rr + 0.01), zr))
            pts = [p0]
            for t in (0.3, 0.6, 1.0):
                z = zr + (cs.get("to_z", -0.40) - zr) * t
                x = sd * (abs(p0.x) - 0.10 * t)
                h_, n_ = core.ray(head, Vector((sd * 3.0, p0.y - 0.10 * t, z)), (-sd, 0, 0))
                if h_ is not None:
                    pts.append(h_ + n_ * 0.012)
            if len(pts) > 2:
                cu = core.curve("chinstrap%+d" % sd, pts, [1.0] * len(pts), 0.016, sm, order=3)
                ctx.add(cu, grp, crown, kind="free", head=True)
    ctx.hat = dict(base=[Vector((c.x + math.sin(math.radians(az)) * r, c.y - math.cos(math.radians(az)) * r, z))
                         for az, r, z in ring], top_z=top_z)
    ctx.L["hat_top"] = top_z
    if hg.get("signature"):
        ctx.sig_objs += objs
    if hg.get("tails"):
        # kerchief tails knotted at the back under the hat (Lira E3 / E4, her signature in every era)
        tl = hg["tails"]
        rm = core.fabric(ctx, "hat_tails", tl["color"], rough=0.6, sheen=0.4)
        surfs = [ob for ob in (crown, ctx.objs.get("hair"), ctx.objs["head"]) if ob is not None]
        _knot_tails(ctx, tl, surfs, grp, rm)
    return crown


def _tassel(ctx, ts, crown, c, top_at):
    """A cord and tassel from the top of a colpack down its side (Kort E2: "меховой колпак с бронзовой кистью")."""
    m = core.principled(ctx, "tassel", ts.get("color", "#B0803A"), rough=0.35, metal=0.45)
    a = math.radians(ts.get("az", 70))
    top = Vector((c.x, c.y, top_at(c.x, c.y)))
    side = Vector((math.sin(a), -math.cos(a), 0.0))
    hit, nrm = core.ray(crown, top + side * 0.15 + Vector((0, 0, 0.5)), (0, 0, -1))
    p0 = hit + nrm * 0.01 if hit is not None else top
    h2, n2 = core.ray(crown, Vector((c.x, c.y, top.z - 0.12)) + side * 2.0, -side)
    p1 = (h2 + n2 * 0.03) if h2 is not None else p0 + side * 0.2
    cord = core.curve("tassel_cord", [p0, (p0 + p1) / 2 + side * 0.04 + Vector((0, 0, 0.02)), p1], [1, 1, 1], 0.012, m,
                      order=3)
    ctx.add(cord, "hat", crown, kind="surface", head=True)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.045, radius2=0.015, depth=0.10)
    t = core.mesh_obj("tassel", bm)
    t.location = p1 + Vector((0, 0, -0.05))
    core.bevel(t, 0.006, 2)
    core.finish(t, m)
    ctx.add(t, "hat", cord, kind="embed", head=True)


def emblem(ctx, bg, hit, nrm, parent, grp, name="emblem", head=True):
    """A small emblem cast on a surface (§7.3: sewn on along the normal, 0.012 H off): "disc", "hex", "star" (5
    points), "leaf" (two halves, a rib), "millstone" (a disc with a hole and 4 furrows), "arrow", "wave_hex" (our
    wave-and-hex sea badge), "coin". Emission `emit` (<= 1.6 E4) optional."""
    kind = bg.get("kind", "disc")
    size = bg.get("size", 0.12) * H
    col = bg.get("color", "#E0AD45")
    m = core.principled(ctx, name + "_" + kind + col, col, rough=bg.get("rough", 0.3), metal=bg.get("metal", 0.5),
                        coat=0.2, emit=col if bg.get("emit") else None, es=bg.get("emit", 0.0))
    base = hit + nrm * (0.010 + 0.004)
    up = (Vector((0, 0, 1)) - nrm * nrm.z).normalized()
    rt = nrm.cross(up).normalized() * -1
    q = Matrix((rt, up, nrm)).transposed().to_quaternion()
    out = []

    def place(o):
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = q
        ctx.add(o, grp, parent, kind="surface", head=head)
        out.append(o)
        return o
    if kind in ("disc", "coin", "millstone"):
        o = core.cylinder(name, base, size / 2, 0.022, m, nrm=nrm, verts=32, bev=0.006)
        ctx.add(o, grp, parent, kind="surface", head=head)
        out.append(o)
        if kind == "millstone":
            dk = core.principled(ctx, name + "_dk", bg.get("dark", "#7A5A2A"), rough=0.5)
            ho = core.torus(name + "_hole", base + nrm * 0.012, size * 0.15, 0.008, dk, nrm=nrm, seg=20, rseg=6)
            ctx.add(ho, grp, o, kind="embed", head=head)
            for k in range(4):
                aa = math.pi / 4 + k * math.pi / 2
                f = core.uvsphere(name + "_furrow", base + nrm * 0.012 + (rt * math.cos(aa) + up * math.sin(aa)) * size * 0.32,
                                  (size * 0.13, 0.006, 0.005), dk, 10, 5)
                f.rotation_mode = "QUATERNION"
                f.rotation_quaternion = q @ Matrix.Rotation(aa, 4, "Z").to_quaternion()
                ctx.add(f, grp, o, kind="embed", head=head)
        if kind == "coin":
            rim = core.torus(name + "_rim", base + nrm * 0.011, size * 0.44, 0.006, m, nrm=nrm, seg=24, rseg=6)
            ctx.add(rim, grp, o, kind="embed", head=head)
    elif kind == "hex":
        o = core.cylinder(name, base, size / 2, 0.024, m, nrm=nrm, verts=6, bev=0.005)
        ctx.add(o, grp, parent, kind="surface", head=head)
        out.append(o)
        if bg.get("inner"):
            mi = core.principled(ctx, name + "_in", bg["inner"], rough=0.25, coat=0.4,
                                 emit=bg["inner"] if bg.get("inner_emit") else None, es=bg.get("inner_emit", 0.0))
            o2 = core.cylinder(name + "_in", base + nrm * 0.012, size * 0.36, 0.012, mi, nrm=nrm, verts=6, bev=0.003)
            ctx.add(o2, grp, o, kind="embed", head=head)
    elif kind == "star":
        bm = bmesh.new()
        vs = []
        for k in range(10):
            aa = math.pi / 2 + k * math.pi / 5
            rr = size / 2 * (1.0 if k % 2 == 0 else 0.45)
            vs.append(bm.verts.new((math.cos(aa) * rr, math.sin(aa) * rr, 0.0)))
        bm.faces.new(vs)
        o = core.mesh_obj(name, bm)
        o.location = base
        core.solidify(o, 0.02, offset=0.0)
        core.finish(o, m, smooth=False)
        core.bevel(o, 0.004, 2)
        place(o)
    elif kind == "leaf":
        for s_ in (-1, 1):
            lf = core.uvsphere(name + "_leaf", base + rt * s_ * size * 0.09, (size * 0.16, size * 0.30, 0.012), m, 20, 10)
            lf.rotation_mode = "QUATERNION"
            lf.rotation_quaternion = q @ Matrix.Rotation(math.radians(35 - s_ * 14), 4, "Z").to_quaternion()
            ctx.add(lf, grp, parent, kind="surface", head=head)
            out.append(lf)
    elif kind == "arrow":
        bm = bmesh.new()
        pts = [(0.0, 0.5), (0.22, 0.16), (0.08, 0.16), (0.08, -0.5), (-0.08, -0.5), (-0.08, 0.16), (-0.22, 0.16)]
        vs = [bm.verts.new((x * size, y * size, 0.0)) for x, y in pts]
        bm.faces.new(vs)
        o = core.mesh_obj(name, bm)
        o.location = base
        core.solidify(o, 0.02, offset=0.0)
        core.finish(o, m, smooth=False)
        place(o)
    elif kind == "wave_hex":
        o = core.cylinder(name, base, size / 2, 0.022, m, nrm=nrm, verts=6, bev=0.005)
        ctx.add(o, grp, parent, kind="surface", head=head)
        out.append(o)
        blue = core.principled(ctx, name + "_wave", bg.get("wave", "#2F8FB0"), rough=0.3, coat=0.3)
        pts = [base + nrm * 0.016 + rt * (size * (-0.3 + 0.6 * i / 8)) + up * (size * 0.07 * math.sin(i * 1.6) - size * 0.05)
               for i in range(9)]
        wv = core.curve(name + "_wv", pts, [1.0] * 9, size * 0.06, blue)
        ctx.add(wv, grp, o, kind="embed", head=head)
    return out


def shell(ctx, hg):
    """A soft or hard shell over the head and hair above an edge line (azimuth -> elevation): a metaball sheet that
    clears the hair, a rolled rim, an optional dome lift (a colpack's or a bonnet's crown), a ridge (`crest`), ribs
    (`ribs`: a tank helmet's padded rolls), ear cups (`cups`), ear flaps (`flaps`: down, or tied up over the crown —
    the ushanka) and an emblem. Materials: fabric, leather, fur, painted, metal. Bonnet, ushanka, tank headset, hard
    flight helmet, rescue helmet, steel skullcap."""
    head = ctx.objs["head"]
    hair = ctx.objs.get("hair")
    edge = _edge_fn(hg.get("edge", [(0, 46), (40, 40), (70, 24), (95, 8), (130, -8), (180, -14)]))
    samples, s = core.surface_samples(head, 3600, lambda h, n, d: _elev(h) > edge(h))
    th = hg.get("thick", 0.06)
    lift = hg.get("lift", 0.0)

    def thick(h, n):
        t = th
        if hair is not None:
            hh, _ = core.ray(hair, h + n * 0.5, -n, dist=0.7)
            if hh is not None:
                t = max(t, (hh - h).dot(n) + hg.get("clear", 0.03) * H)
        t += lift * core.smoothstep(hg.get("lift_from", 0.15), 0.53, h.z)
        return t * (0.75 + 0.25 * core.smoothstep(0, 8, _elev(h) - edge(h)))
    el = core.sheet_elems(samples, s, thick, inset=0.02)
    tbl = hg.get("edge", [(0, 46), (40, 40), (70, 24), (95, 8), (130, -8), (180, -14)])
    if hg.get("roll", 0.0):
        for k in range(120):
            az = -180 + 360 * k / 120
            e = core.lerp_table(tbl, abs(az)) + 1.5
            d = core.az_el(az, e)
            h, n = core.ray(head, d * 3, -d)
            if h is None:
                continue
            el.append(dict(co=h + n * thick(h, n) * 0.85, half=hg["roll"] * H, stiff=2.0))
    for rb in hg.get("ribs", []):
        # a padded roll over the crown along one azimuth (a tank helmet's ribs)
        for k in range(16):
            e = core.lerp_table(tbl, abs(rb)) + 4 + (90 - core.lerp_table(tbl, abs(rb)) - 4) * k / 15
            d = core.az_el(rb if k < 15 else 0, e)
            h, n = core.ray(head, d * 3, -d)
            if h is None:
                continue
            el.append(dict(co=h + n * (thick(h, n) + 0.01), half=0.045, stiff=2.2))
    mat = _hat_mat(ctx, hg, "shell_" + hg.get("id", hg["kind"]))
    o = core.mb_mesh(ctx, "Shell", el, hg.get("res", 0.012), mat, smooth_iter=hg.get("smooth", 3), name="shell")
    grp = "detail:" + hg["detail"] if hg.get("detail") else "hat"
    ctx.add(o, grp, head, kind="embed", head=True)
    ctx.objs["cap"] = o
    ctx.objs["hat"] = o
    if hg.get("detail"):
        ctx.details[hg["detail"]] = hg.get("min_px", 1500)
    if hg.get("signature"):
        ctx.sig_objs.append(o)
    # ear cups (a headset's, a hard helmet's)
    for cp in [hg["cups"]] if hg.get("cups") else []:
        cm = _hat_mat(ctx, dict(hg, **cp), "cup_" + hg.get("id", hg["kind"]), cp.get("color", hg["color"]),
                      cp.get("mat", hg.get("mat", "fabric")))
        for side in cp.get("sides", (-1, 1)):
            ear = ctx.L["ear_" + ("near" if side < 0 else "far")][0]
            if ear is None:
                continue
            hh_, nh_ = core.ray(o, Vector((side * 2.0, ear.y, ear.z)), (-side, 0, 0))
            if hh_ is None:
                hh_, nh_ = Vector((ear.x + side * 0.06, ear.y, ear.z)), Vector((side, 0, 0))
            r = cp.get("r", 0.10) * H
            cup = core.cylinder("cup%+d" % side, hh_ + nh_ * 0.02, r, cp.get("d", 0.06), cm, nrm=nh_, verts=32, bev=0.014)
            ctx.add(cup, grp, o, kind="surface", head=True)
            if hg.get("signature"):
                ctx.sig_objs.append(cup)
    fl = hg.get("flaps")
    if fl:
        fm = _hat_mat(ctx, dict(hg, **fl), "flap_" + hg.get("id", hg["kind"]), fl.get("color", hg["color"]),
                      fl.get("mat", hg.get("mat", "fabric")))
        for side in (-1, 1):
            ear = ctx.L["ear_" + ("near" if side < 0 else "far")][0]
            if ear is None:
                continue
            hh_, nh_ = None, None
            for k in range(10):    # the shell's side may end above the ear (Kort's E3 ushanka): climb to its rim
                hh_, nh_ = core.ray(o, Vector((side * 2.0, ear.y + 0.02, ear.z + 0.06 + 0.03 * k)), (-side, 0, 0))
                if hh_ is not None:
                    break
            hinge = (hh_ - nh_ * 0.02) if hh_ is not None else Vector((ear.x + side * 0.08, ear.y, ear.z + 0.05))
            if fl.get("up"):
                # tied up over the crown (the ushanka's ears): from the hinge up the side and over toward the top
                outv = Vector((side * 0.25, 0.05, 1.0)).normalized()
            else:
                outv = Vector((side * fl.get("splay", 0.2), 0.05, -1.0)).normalized()
            L_, W_ = fl.get("len", 0.26), fl.get("w", 0.20)
            el2 = []
            for k in range(7):
                t = k / 6
                c = hinge + outv * (L_ * t) + Vector((side * 0.03 * math.sin(math.pi * t), 0, 0))
                w_ = W_ * (0.75 + 0.25 * math.sin(math.pi * min(1.0, t * 1.2)))
                el2.append(dict(co=c, half=(w_ * 0.5, 0.03, 0.05), stiff=2.4,
                                rot=core.frame_quat(outv, Vector((side, 0.0, 0.0)))))
            flap = core.mb_mesh(ctx, "SFlap%+d" % side, el2, 0.009, fm, smooth_iter=2, name="sflap%+d" % side)
            ctx.add(flap, grp, o, kind="surface", head=True)
            if hg.get("signature"):
                ctx.sig_objs.append(flap)
    for bg in ([hg["badge"]] if hg.get("badge") else []):
        d = core.az_el(bg.get("az", 0.0), bg.get("el", 34))
        hit, nrm = core.ray(o, d * 3, -d)
        if hit is not None:
            emblem(ctx, bg, hit, nrm, o, grp if not bg.get("detail") else "detail:" + bg["detail"])
    rb = hg.get("ribbon")
    if rb:
        # a ribbon band round the shell (Lira E2's white bonnet: a green ribbon) and its two tails at the back (her
        # "top back" signature, as the kerchief's knot tails)
        rm = core.fabric(ctx, "shell_ribbon", rb["color"], rough=0.6, sheen=0.4)
        pts = []
        for k in range(73):
            az = -180 + 360 * k / 72
            e = core.lerp_table(tbl, abs(az)) + rb.get("above", 7)
            d = core.az_el(az, e)
            h, n = core.ray(o, d * 3, -d)
            if h is not None:
                pts.append(h + n * 0.004)
        if len(pts) > 4:
            st = core.ribbon_mesh("shell_ribbon", pts, rb.get("w", 0.05), normals=[Vector((0, 0, 1))] * len(pts))
            core.solidify(st, 0.014, offset=0.0)
            core.finish(st, rm, sub=1)
            ctx.add(st, grp, o, kind="embed", head=True)
        _knot_tails(ctx, rb, [o], grp, rm)
    return o


def _knot_tails(ctx, rb, surfs, grp, rm):
    """A knot at (`knot_az`, `knot_el`) on the first of `surfs` it hits and two flat cloth tails flying back from it
    (Lira's kerchief tails, §7.2 "Верх сзади": her signature in every era — on the E2 bonnet's ribbon, and since the P3
    review on the E3 side cap and the E4 helmet, where the 48 px signature share fell under 8 % without them)."""
    kd = core.az_el(rb.get("knot_az", -150), rb.get("knot_el", 10))
    kh, kn, ob = core.ray_any(surfs, kd * 3, -kd)
    if kh is None:
        return None
    knot = kh + kn * rb.get("knot_off", 0.03)
    ko = core.uvsphere("shell_knot", knot, (0.05, 0.04, 0.045), rm, 16, 8)
    ctx.add(ko, grp, ob, kind="surface", head=True)
    back = (Vector((kn.x, kn.y, 0)).normalized() * 0.4 + core.world_dir(ctx, (-1.0, 0.35, 0.0), head=True)).normalized()
    side_ = Vector((0, 0, 1)).cross(back).normalized()
    ln = rb.get("tail", 0.30)
    tw = rb.get("tail_w", 0.045)
    for k_, (up, sw) in enumerate(((0.20, 0.16), (-0.5, -0.14))):
        el2 = []
        prev = knot
        for i in range(1, 25):
            t = i / 24
            p = knot + back * (ln * t) + side_ * (sw * 0.3 * t) + Vector((0, 0, up * ln * 0.6 * t - 0.14 * t * t))
            fwd_ = (p - prev).normalized()
            el2.append(dict(co=p, half=(tw + tw * 0.67 * t, 0.012, ln / 24 * 1.6), stiff=2.2,
                            rot=core.frame_quat(fwd_, side_.cross(fwd_).normalized())))
            prev = p
        tl = core.mb_mesh(ctx, "STail%d" % k_, el2, 0.008, rm, smooth_iter=2, name="shell_tail%d" % k_)
        ctx.add(tl, "detail:kerchief_tails", ko, kind="surface", head=True)
        ctx.sig_objs.append(tl)
    ctx.details["kerchief_tails"] = rb.get("min_px", 300)
    return ko


def visor(ctx, hg):
    """A visor band round the front of the head (§7.6 E4: Olm's goggle-visor on the brow with an orange HUD, Vik's
    raised green visor strip on the hood, Irma's raised visor strip, Seir's raised clear HUD visor, Lira's raised clear
    visor, Hawk's raised visor; Vega's HUD strip across the eyes — clear, a thin white line): a curved strip over
    azimuths +-`span` at elevation `el` (on the hat when there is one, else on the hair or the head), `h` H tall, a
    frame (`frame` colour) top and bottom, the glass tinted (`tint`, `alpha`) or glowing (`glow` <= 1.6 at `emit`)."""
    surf = [ctx.objs[k] for k in ("hat", "cap", "hood", "hair") if ctx.objs.get(k) is not None] + [ctx.objs["head"]]
    if hg.get("on") == "head":
        surf = [ctx.objs["head"]]
    span = hg.get("span", 70)
    el0 = hg.get("el", 30)
    hh = hg.get("h", 0.09) * H
    off = hg.get("off", 0.03)
    n = 40
    rows_top, rows_bot = [], []
    ends = {}                     # per end: (the surface point under it, its object) — the side arms' anchors
    hit_objs = []
    for i in range(n + 1):
        az = -span + 2 * span * i / n
        for e, rows in ((el0 + hg.get("dh", 9), rows_top), (el0 - hg.get("dh", 9), rows_bot)):
            d = core.az_el(az + hg.get("az", 0.0), e)
            h, nn, ob = core.ray_any(surf, d * 3, -d)
            if h is None:
                h, nn, ob = d * 0.5, d, ctx.objs["head"]
            rows.append(h + nn * off)
            hit_objs.append(ob)
            if i in (0, n):
                ends.setdefault(-1 if i == 0 else 1, []).append((h, ob))
    # the strip: rebuild as a ribbon between the top and the bottom rows, its middle a little proud
    bm = bmesh.new()
    vs = []
    for k in range(3):
        f = k / 2
        vs.append([bm.verts.new(a.lerp(b, f) + (a - b).cross(Vector((0, 0, 1))).normalized() * 0.0) for a, b in
                   zip(rows_top, rows_bot)])
    for r0, r1 in zip(vs, vs[1:]):
        for i in range(n):
            bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    strip = core.mesh_obj("visor", bm)
    core.solidify(strip, 0.012, offset=0.0)
    grp = "detail:" + hg["detail"] if hg.get("detail") else "glass"
    fr = hg.get("frame")
    # a visor held off the surface (off > 0.04: Vega's strip across the eyes, Seir's over the cap brim) hangs on two
    # side arms from its pivots back to the hat / hair / head under its ends; it is registered on a pivot, the pivot
    # on its arm, the arm on that surface (the contact check: a strip 0.05-0.09 H in front of the face read as floating)
    arms = fr and off > 0.04
    if hg.get("glow"):
        m = core.principled(ctx, "visor_glow", hg.get("tint", "#F08A24"), rough=0.2, coat=0.5, emit=hg.get("tint", "#F08A24"),
                            es=hg["glow"])
        core.finish(strip, m, sub=1)
        if not arms:
            ctx.add(strip, grp, max(set(hit_objs), key=hit_objs.count), kind="surface", head=True)
    else:
        m = core.glass_mat(ctx, "visor_glass", hg.get("tint", "#E8F4FF"))
        core.finish(strip, m, smooth=True, sub=1)
        strip["kit_glass"] = 1
        strip.visible_shadow = False
        if not arms:
            ctx.add(strip, "glass", max(set(hit_objs), key=hit_objs.count), kind="surface", head=True)
    if fr:
        fm = core.principled(ctx, "visor_frame", fr, rough=0.35, metal=hg.get("frame_metal", 0.3), coat=0.3)
        pivots = []
        for sd in (-1, 1):
            a, b = (rows_top[0], rows_bot[0]) if sd < 0 else (rows_top[-1], rows_bot[-1])
            pv = core.cylinder("visor_pivot%+d" % sd, (a + b) / 2, hh * 0.45, 0.03, fm,
                               nrm=((a + b) / 2 - Vector((0, 0.02, (a.z + b.z) / 2))).normalized(), verts=20, bev=0.006)
            if arms:
                (h0, ob0), (h1, ob1) = ends[sd][0], ends[sd][1]
                # into the surface under the upper end (the midpoint of two hits on hat and hair floated, the check)
                anchor = h0 + (a - h0).normalized() * -0.006 if (a - h0).length > 1e-6 else h0
                arm = core.curve("visor_arm%+d" % sd, [(a + b) / 2, ((a + b) / 2).lerp(anchor, 0.5), anchor],
                                 [1.0, 1.0, 1.0], max(0.012, hh * 0.16), fm, order=3)
                ctx.add(arm, "hat", ob0, kind="surface", head=True)
                ctx.add(pv, "hat", arm, kind="embed", head=True)
            else:
                ctx.add(pv, "hat", strip, kind="embed", head=True)
            pivots.append(pv)
        if arms:
            ctx.add(strip, grp if hg.get("glow") else "glass", pivots[0], kind="embed", head=True)
        # the frame wires carry the P-A8 detail of a clear visor (Vega's HUD: its glass reads as "glass" in the ID pass,
        # so the detail measured 0 px, P3 review)
        fgrp = grp if (hg.get("glow") or hg.get("detail")) else "hat"
        for rows, nm in ((rows_top, "visor_top"), (rows_bot, "visor_bot")):
            cu = core.curve(nm, rows, [1.0] * len(rows), hg.get("frame_r", 0.012), fm, order=3)
            ctx.add(cu, fgrp, strip, kind="embed", head=True)
    if hg.get("line"):
        # a thin white HUD line along the strip (Vega E4), glowing softly (<= 0.6, §7.4 HUD lenses)
        lm = core.emit_mat(ctx, "hud_line", hg["line"], hg.get("line_emit", 0.6))
        pts = [a.lerp(b, 0.62) + (a.lerp(b, 0.62) - Vector((0, 0.05, a.z))).normalized() * 0.008
               for a, b in zip(rows_top, rows_bot)]
        cu = core.curve("hud_line", pts[4:-4], [1.0] * len(pts[4:-4]), 0.0045, lm, order=3)
        ctx.add(cu, grp if hg.get("detail") else "glass", strip, kind="embed", head=True)
    if hg.get("detail"):
        ctx.details[hg["detail"]] = hg.get("min_px", 400)
    return strip


def headset(ctx, hg):
    """A headset (§7.6 Kort E4 "гарнитура на одно ухо", Vance E4 "наушник", Vega E4): a thin band over the head and
    hair from one ear (`sides`) up over the crown, an ear cup on the listening side, a short mic boom toward the
    mouth (`mic`)."""
    surf = [ctx.objs[k] for k in ("hat", "hair") if ctx.objs.get(k) is not None] + [ctx.objs["head"]]
    m = core.principled(ctx, "headset", hg.get("color", "#3A4150"), rough=0.35, metal=0.3, coat=0.3)
    acc = core.principled(ctx, "headset_acc", hg.get("accent", "#B0803A"), rough=0.3, metal=0.5)
    grp = "detail:" + hg.get("detail", "headset")
    sides = hg.get("sides", (-1,))
    side = sides[0]
    pts, hosts = [], []
    for k in range(17):
        t = k / 16
        e = -2 + 90 * t if len(sides) == 1 else -2 + 184 * t
        az = side * 92 if (len(sides) == 1 or t < 0.5) else -side * 92
        el_ = e if e <= 90 else 180 - e
        d = core.az_el(az, el_)
        h, nn, ob = core.ray_any(surf, d * 3, -d)
        if h is not None:
            pts.append(h + nn * 0.016)
            hosts.append(ob)
    if len(pts) > 3:
        st = core.ribbon_mesh("headset_band", pts, hg.get("w", 0.045), normals=[Vector((0, 1, 0))] * len(pts))
        core.solidify(st, 0.016, offset=0.0)
        core.finish(st, m, sub=1)
        # on the surface most of it lies on (over the hair, not 0.07 H off the scalp, the contact check)
        ctx.add(st, grp, max(set(hosts), key=hosts.count), kind="embed", head=True)
    ear = ctx.L["ear_" + ("near" if side < 0 else "far")][0]
    if ear is not None:
        r = hg.get("r", 0.10) * H
        c = ear + Vector((side * 0.05, 0.0, 0.0))
        cup = core.cylinder("headset_cup", c, r, 0.06, m, nrm=Vector((side, 0, 0)), verts=32, bev=0.014)
        ctx.add(cup, grp, ctx.objs["head"], kind="surface", head=True)
        ring = core.torus("headset_ring", c + Vector((side * 0.032, 0, 0)), r * 0.72, 0.010, acc, nrm=Vector((side, 0, 0)),
                          seg=28, rseg=8)
        ctx.add(ring, grp, cup, kind="embed", head=True)
        if hg.get("mic"):
            mz = ctx.L["mouth_z"]
            a = c + Vector((side * 0.03, -0.04, -0.03))
            b = Vector((side * 0.20, ctx.L["face_y"] - 0.06, mz + 0.01))
            # (`mic_r`: a thicker boom — at 0.012 Vega's far-side boom broke into a separate 6 px alpha island at 512)
            boom = core.curve("headset_mic", [a, (a + b) / 2 + Vector((side * 0.05, -0.04, -0.02)), b], [1, 1, 1],
                              hg.get("mic_r", 0.012), m, order=3)
            ctx.add(boom, grp, cup, kind="embed", head=True)
            tip = core.uvsphere("headset_mic_tip", b, (0.022, 0.022, 0.022), acc, 12, 6)
            ctx.add(tip, grp, boom, kind="embed", head=True)
    ctx.details[hg.get("detail", "headset")] = hg.get("min_px", 300)


def diadem(ctx, hg):
    """An iron diadem with two wolf-ear spikes (Sairin, §7.8: "два высоких откинутых назад железных острия диадемы, без
    кольца шипов и камней"): a band round the head over the hair (on a plane higher at the front), and two tall
    blades rising from its top sides and swept back — sharp (leaders may be sharp, §7.2)."""
    surf = _surf(ctx)
    m = core.principled(ctx, "diadem", hg.get("color", "#5A6270"), rough=0.32, metal=0.55, coat=0.25)
    w = hg.get("w", 0.07) * H
    e_front, e_back = hg.get("el", (40, 22))
    pts = []
    for k in range(73):
        az = -180 + 360 * k / 72
        e = e_back + (e_front - e_back) * (math.cos(math.radians(az)) + 1) / 2
        d = core.az_el(az, e)
        h, n, _ = core.ray_any(surf, d * 3, -d)
        if h is not None:
            pts.append(h + n * 0.010)
    band = core.ribbon_mesh("diadem", pts, w, normals=[Vector((0, 0, 1))] * len(pts))
    core.solidify(band, 0.02, offset=0.0)
    core.bevel(band, 0.005, 2)
    core.finish(band, m, sub=1)
    grp = "detail:" + hg.get("detail", "diadem")
    ctx.add(band, grp, ctx.objs.get("hair") or ctx.objs["head"], kind="embed", head=True)
    ctx.sig_objs.append(band)
    ln = hg.get("spike", 0.42) * H
    for sd in (-1, 1):
        az = sd * hg.get("spike_az", 34)
        e = e_back + (e_front - e_back) * (math.cos(math.radians(az)) + 1) / 2
        d = core.az_el(az, e + 3)
        h, n, _ = core.ray_any(surf, d * 3, -d)
        if h is None:
            continue
        back = math.radians(hg.get("back", 32))
        out = math.radians(hg.get("out", 14))
        dirv = Vector((sd * math.sin(out), math.sin(back), math.cos(back))).normalized()
        el = []
        # a flat blade: wide at the root, a sharp tip, curving back a little toward the tip
        for k in range(14):
            t = k / 13
            p = h + n * 0.01 + dirv * ln * t + Vector((0, 0.06 * t * t, 0))
            wd = 0.075 * (1 - t) ** 0.9 + 0.004
            el.append(dict(co=p, half=(wd, 0.022 * (1 - 0.6 * t) + 0.004, ln / 13 * 0.9), stiff=2.6,
                           rot=core.frame_quat(dirv, Vector((0, -1, 0)))))
        sp = core.mb_mesh(ctx, "Spike%+d" % sd, el, 0.007, m, smooth_iter=1, name="diadem_spike%+d" % sd)
        ctx.add(sp, grp, band, kind="surface", head=True)
        ctx.sig_objs.append(sp)
    ctx.details[hg.get("detail", "diadem")] = hg.get("min_px", 1500)


def crown(ctx, hg):
    """The ruler's crown (§7.10): a gold band 0.07 H (#E8B23A) seated over the hair, 5 rounded merlons of a fortress
    wall round its front (not spikes, not lilies), a blue hex raivite in each (emission <= 1.0 E1–E3, <= 1.6 E4), a
    small white eagle on the middle one, a blue velvet cap inside rising between the merlons; its top >= 0.20 H over
    the hair."""
    c, ring = _seat_ring(ctx, dict(hg, rim_dz=hg.get("rim_dz", 0.10), tilt=hg.get("tilt", -6), into=0.008))
    n = len(ring)
    gold = core.principled(ctx, "crown_gold", hg.get("color", "#E8B23A"), rough=0.30, metal=0.55, coat=0.3)
    bw = hg.get("band", 0.07) * H
    bm = bmesh.new()
    rows = []
    for f in (0.0, 0.5, 1.0):
        rows.append([bm.verts.new((c.x + math.sin(math.radians(az)) * (r + 0.012), c.y - math.cos(math.radians(az)) * (r + 0.012),
                                   z + bw * f)) for az, r, z in ring])
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    band = core.mesh_obj("crown_band", bm)
    core.solidify(band, 0.03, offset=1.0)
    core.bevel(band, 0.006, 2)
    core.finish(band, gold, sub=1)
    grp = "detail:crown"
    ctx.add(band, grp, ctx.objs.get("hair") or ctx.objs["head"], kind="surface", head=True)
    objs = [band]
    # the velvet cap: a dome from inside the band up to `cap` H over the band's top
    vel = core.grad_mat(ctx, "crown_velvet", core.hex_scale(hg.get("velvet", "#2E5BD8"), 1.05),
                        core.hex_scale(hg.get("velvet", "#2E5BD8"), 0.8), 0.2, 0.9, rough=0.8, sheen=0.6)
    top = max(z for _, _, z in ring) + bw + hg.get("cap", 0.20) * H
    bm = bmesh.new()
    rows = []
    for g in (0.0, 0.3, 0.55, 0.75, 0.9, 1.0):
        rk = math.cos(g * math.pi / 2) ** 0.6
        rows.append([bm.verts.new((c.x + math.sin(math.radians(az)) * (r + 0.006) * rk, c.y - math.cos(math.radians(az)) * (r + 0.006) * rk,
                                   z + bw * 0.5 + (top - z - bw * 0.5) * math.sin(g * math.pi / 2)))
                     for az, r, z in ring])
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cap = core.mesh_obj("crown_cap", bm)
    core.finish(cap, vel, sub=2)
    ctx.add(cap, grp, band, kind="embed", head=True)
    objs.append(cap)
    # the merlons: 5 rounded blocks round the front, each with a hex raivite; the middle one carries the eagle
    mh = hg.get("merlon", 0.14) * H
    mw = hg.get("merlon_w", 0.15) * H
    gem = core.principled(ctx, "crown_gem", "#3A8DFF", rough=0.15, coat=0.6, emit="#3A8DFF", es=hg.get("emit", 1.0))
    white = core.principled(ctx, "crown_eagle", "#F6F6F2", rough=0.5, coat=0.3)
    for k, az in enumerate(hg.get("merlons", (-96, -48, 0, 48, 96))):
        a = math.radians(az)
        r = core.lerp_table([(q[0], q[1]) for q in ring], az) + 0.012 + 0.015
        z = core.lerp_table([(q[0], q[2]) for q in ring], az) + bw
        out = Vector((math.sin(a), -math.cos(a), 0.0))
        base = Vector((c.x, c.y, 0.0)) + out * r
        base.z = z
        # a block with a rounded top (a box with a big bevel), its face toward `out`
        mb = core.box("crown_merlon%d" % k, base + Vector((0, 0, mh * 0.45)), (mw, 0.032, mh), gold, bev=mw * 0.42, segs=6)
        mb.rotation_mode = "QUATERNION"
        mb.rotation_quaternion = Vector((0, -1, 0)).rotation_difference(out)
        ctx.add(mb, grp, band, kind="embed", head=True)
        objs.append(mb)
        st = core.cylinder("crown_raivite%d" % k, base + Vector((0, 0, mh * 0.40)) + out * 0.026, mw * 0.27, 0.02, gem,
                           nrm=out, verts=6, bev=0.004)
        ctx.add(st, "detail:crown_gems", mb, kind="embed", head=True)
        if az == 0:
            # the white eagle (the game's emblem outline) on the middle merlon, over the stone
            from .props import EAGLE
            bm = bmesh.new()
            s_ = mw * 0.55
            rt = out.cross(Vector((0, 0, 1))).normalized() * -1
            ctr = base + Vector((0, 0, mh * 0.80)) + out * 0.022
            vs = [bm.verts.new(ctr + rt * (x * s_) + Vector((0, 0, y * s_ * 0.8))) for x, y in EAGLE]
            bm.faces.new(vs)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            eg = core.mesh_obj("crown_eagle", bm)
            core.solidify(eg, 0.01, offset=0.0)
            core.finish(eg, white, smooth=False)
            ctx.add(eg, "detail:crown_eagle", mb, kind="embed", head=True)
            ctx.details["crown_eagle"] = hg.get("eagle_px", 30)
    ctx.details["crown"] = hg.get("min_px", 3000)
    ctx.details["crown_gems"] = hg.get("gem_px", 60)
    ctx.sig_objs += objs
    ctx.L["hat_top"] = top


def bicorne(ctx, hg):
    """A bicorne worn crosswise (§7.6 Vega E2 "двууголка поперёк, наклонена, каре видно"): the tricorn's felt walls with
    two corners at the sides — a half-moon tallest in the middle front and back, its points out over the ears; a gold
    tape along the edge and a cockade at the front."""
    hg2 = dict(hg, corners=2, corner_az=90.0)
    return tricorn(ctx, hg2)


def frame_helmet(ctx, hg):
    """An open helmet frame (§7.6 Irma E4 "открытый каркас шлема ... хвост через кольцо сзади"): a brow band round the
    head over the hair, a crest band from the brow over the crown to the nape and two side bands from the temples up
    to the crest, all flat painted metal; a ring at the back the ponytail runs through."""
    surf = _surf(ctx)
    m = _hat_mat(ctx, hg, "frame_" + hg.get("id", "frame"), kind=hg.get("mat", "painted"))
    w = hg.get("w", 0.075) * H
    grp = "hat"
    objs = []

    def band(name, dirs):
        pts, nrs, hosts = [], [], []
        for d in dirs:
            h, n, ob = core.ray_any(surf, d * 3, -d)
            if h is not None:
                pts.append(h + n * 0.014)     # its inner face on the hair (0.03 left a 0.015 H gap, the contact check)
                nrs.append(n)
                hosts.append(ob)
        if len(pts) < 3:
            return None
        # the band's flat side on the head: its width across the run, in the surface
        o = core.ribbon_mesh(name, pts, w, normals=[(nrs[i].cross((pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]))
                                                     .cross(nrs[i])).normalized() * -1 if False else nrs[i]
                                                    for i in range(len(pts))])
        core.solidify(o, 0.024, offset=0.0)
        core.bevel(o, 0.006, 2)
        core.finish(o, m, sub=1)
        ctx.add(o, grp, max(set(hosts), key=hosts.count), kind="embed", head=True)
        objs.append(o)
        return o
    el_b = hg.get("el", 30)
    band("frame_brow", [core.az_el(-180 + 360 * k / 72, el_b + 6 * math.cos(math.radians(-180 + 360 * k / 72)))
                        for k in range(73)])
    band("frame_crest", [core.az_el(0 if e <= 90 else 180, e if e <= 90 else 180 - e) for e in range(el_b + 4, 176, 4)])
    for sd in (-1, 1):
        band("frame_side%+d" % sd, [core.az_el(sd * 90, e) for e in range(el_b - 4, 88, 4)])
    if hg.get("ring"):
        g = ctx.L.get("ponytail_root")
        if g is not None:
            r = core.torus("frame_ring", g, 0.06, 0.016, m, nrm=Vector((0, 0.6, 0.8)).normalized(), seg=24, rseg=8)
            ctx.add(r, grp, objs[0] if objs else ctx.objs["head"], kind="free", head=True)
    ctx.objs["hat"] = objs[0] if objs else None
    if hg.get("signature"):
        ctx.sig_objs += objs


def earpiece(ctx, hg):
    """An earpiece on the near ear (§7.6 Vance E4 "наушник"): a small domed cup over the ear with a short mic stem."""
    m = core.principled(ctx, "earpiece", hg.get("color", "#C8CCD4"), rough=0.3, metal=0.5, coat=0.3)
    side = -1 if hg.get("ear", "near") == "near" else 1
    ear = ctx.L["ear_" + ("near" if side < 0 else "far")][0]
    if ear is None:
        return
    c = ear + Vector((side * 0.045, 0.0, 0.0))
    cup = core.uvsphere("earpiece", c, (0.035, 0.05, 0.06), m, 20, 10)
    ctx.add(cup, "detail:" + hg.get("detail", "earpiece"), ctx.objs["head"], kind="surface", head=True)
    if hg.get("mic", True):
        a = c + Vector((side * 0.01, -0.03, -0.04))
        b = a + Vector((side * 0.01, -0.12, -0.06))
        st = core.curve("earpiece_mic", [a, b], [1.0, 0.8], 0.008, m, order=2)
        ctx.add(st, "detail:" + hg.get("detail", "earpiece"), cup, kind="embed", head=True)
    ctx.details[hg.get("detail", "earpiece")] = hg.get("min_px", 60)
