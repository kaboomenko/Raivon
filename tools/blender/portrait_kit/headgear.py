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
    if kind == "tricorn":
        rz = _rim_fn(ctx, hg)
        ctx.hair_cut = lambda p: p.z > rz(p) + 0.012
    elif kind == "aviator":
        edge = _edge_fn(hg.get("edge", AVIATOR_EDGE))
        ctx.hair_cut = lambda p: _elev(p) > edge(p) + 2.0


def build_headgear(ctx):
    hg = ctx.ch.get("headgear")
    if not hg:
        return
    {"kerchief": kerchief, "hood": hood, "tricorn": tricorn, "aviator": aviator, "goggles": goggles_hg,
     "circlet": circlet}[hg["kind"]](ctx, hg)
    for extra in hg.get("extra", []):          # a second piece worn with it (Hawk's goggles on the cap)
        {"goggles": goggles_hg}[extra["kind"]](ctx, extra)


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
    m = core.fabric(ctx, "hood", hg["color"], z0=-0.7, z1=0.6, rough=0.85, sheen=0.35)
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
    for i in range(n):
        az = math.radians(-180 + 360 * i / n)
        w = ((math.cos(3 * (az - a0)) + 1) / 2) ** 2.2
        ext = e_mid + (e_cor - e_mid) * w
        r = (base[i] - c).to_2d().length
        top = Vector((c.x + dirs[i].x * (r + ext), c.y + dirs[i].y * (r + ext), base[i].z + hw * (1.0 + 0.10 * w)))
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
    lens_m = core.principled(ctx, "goggle_lens", lens_col, rough=0.08, coat=0.6, spec=0.8)
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
