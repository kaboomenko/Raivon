"""Beards and moustaches (§7.5 step 4): a few broad, smooth strand groups (core.clump) laid along a guide surface —
the face above the chin, an analytic shape below it — over a hidden backing (a sparse sheet of large balls on the face
plus big soft volumes), so soft grooves run between the groups (no small bumps, no separate "petals", art director
note 3); a negative element keeps the mouth clear; the beard's upper edge depends on the mood (an open laugh needs
its lower lip and a little chin clear, its corners covered). Converted to a mesh, Smooth 4 (§7.5: no Subsurf).

Styles (chars.py "beard": {"style": ...}):
  pear   — wider than the jaw by `wider` W on each side, `below` H under the chin, two rounded lower lobes (Bram's
           signature: the lower head wider than the top), with a bushy moustache; `widest` (H over the chin) and
           `profile` (the half width down the beard) shape the pear;
  walrus — a walrus moustache (Kort): `w` W wide, hanging `drop` H below the mouth, its ends below the chin; the
           mouth hidden in the calm, a window over the open laugh and the ends lifted `smile_lift` H;
  short  — a short beard along the jaw (Seir: 0.06 H) with a moustache; its clumps ride inside the sheet
           (clump_lift), so the union does not swell past the set thickness;
  long   — a long beard (Rai): `below` H under the chin, three big lobes converging to a point, the moustache
           flowing into it;
  thin   — a thin moustache (Hawk: 0.04 H, the ends curled up 0.02 H): two tapered halves parted at the philtrum,
           inside the mouth's width;
  chops  — mutton-chop sideburns (Olm: 0.16 W), the chin bare.
"""
import math

from mathutils import Vector

from . import core
from .core import H


def build_beard(ctx):
    bd = ctx.ch.get("beard")
    if not bd:
        return
    {"pear": _pear, "walrus": _walrus, "short": _short, "long": _long, "thin": _thin, "chops": _chops,
     "forked": _long, "box": _long, "goatee": _long, "round": _long, "braids": _braids, "scruffy": _short,
     "none": lambda c, b: None}[bd["style"]](ctx, bd)
    if bd.get("moustache") == "upturned":
        _upturned(ctx, bd)
    elif bd.get("moustache"):
        _moustache(ctx, bd)


def _beard_line(ctx, bd):
    """Upper edge of the beard on the face (z) as a function of |x|: under the lower lip in the middle, below the
    cheek apples (they stay bare and blushed), up to the sideburns in front of the ears. An open laugh lowers the
    middle under the open mouth."""
    mz = ctx.L["mouth_z"]
    sx = ctx.P["hx"] / 0.48
    if getattr(ctx, "mouth_open", False):
        zs = min(q[1] for q in ctx.mouth_pts) - 0.028
        # (up to the corners' height at the sides: no bare skin between the moustache's tips, the corners and the
        # beard)
        mid = [(0.0, zs), (0.08, zs + 0.006), (0.15, zs + 0.045), (0.20, mz + 0.0), (0.24, mz + 0.012)]
    else:
        # closed: right under the lower lip, so no bare chin shows between the lip and the beard
        mid = [(0.0, mz - 0.046), (0.08, mz - 0.044), (0.16, mz - 0.032), (0.22, mz - 0.012)]
    tbl = mid + [(0.28, mz + 0.035), (0.34, mz + 0.085), (0.40, mz + 0.15), (0.44, mz + 0.23), (0.5, mz + 0.27)]
    return lambda x: core.lerp_table([(a * sx, b) for a, b in tbl], abs(x))


def _pear(ctx, bd):
    """Bram's pear (§7.6, art director note 3): 8 broad, smooth strand groups over a hidden backing mass.

    A guide surface defines the pear: on the face from the beard line down to the jaw (the head itself, ray cast),
    then an analytic shape hanging below the chin — widest at the jaw line (`wider` W past the jaw on each side),
    narrowing to two rounded lower lobes `below` H under the chin, split by a notch. The clumps run down it along
    lines of constant u (their share of the width at each height), so they converge into the lobes; neighbours touch,
    and the AO crevice tone marks a soft groove between them. The backing (a sparse sheet of large balls on the face
    and a chain of big soft volumes inside the pear) fills the inside and never reaches the surface."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    line = _beard_line(ctx, bd)
    chin_z = ctx.L["chin"].z
    jaw_x = abs(ctx.L["jaw_near"].x) if ctx.L.get("jaw_near") else 0.4 * sx
    wide = jaw_x + bd.get("wider", 0.12) * ctx.W          # half width of the beard's widest row
    tip_z = chin_z - bd.get("below", 0.45) * H              # the lowest point (lobe bottoms)
    fy = ctx.L["face_y"]
    zj = chin_z + bd.get("widest", 0.07)                    # the widest row (at the jaw line by default)
    th = bd.get("clump_th", 0.06)
    prof = bd.get("profile", [(-1.0, 0.78), (0.0, 1.0), (0.3, 0.90), (0.6, 0.68), (0.85, 0.50), (1.0, 0.42)])

    def half_w(z):
        """The pear's half width at z: the sideburns' width up on the cheek, widest at the jaw, two lobes at the tip."""
        t = (zj - z) / (zj - tip_z)
        return wide * core.lerp_table(prof, t)

    def guide(x, z):
        """A point of the guide surface and its normal: on the face above the chin (the beard's own thickness in
        front of it), the analytic pear below and past the head's outline (a front that wraps back to the sides)."""
        w = half_w(z)
        u = x / max(w, 1e-6)
        t = max(0.0, (zj - z) / (zj - tip_z))
        if z > chin_z - 0.02:
            hit, nor = core.ray_front(head, x, z)
            if hit is not None:
                return hit + nor * 0.05, nor
        ya = fy - 0.01 + 0.03 * t + 0.40 * w * u * u
        return Vector((x, ya, z)), Vector((0.8 * u / max(w, 0.2), -1.0, -0.15 * t)).normalized()

    # the backing: a sparse face sheet under the beard line and big soft volumes inside the pear
    open_m = getattr(ctx, "mouth_open", False)

    def keep(h, n, d):
        # (an open mouth: the sheet stops a little lower under it — its rounded top edge stood over the lower lip
        # and hid the bottom of the opening)
        if h.z > line(h.x) - 0.01 - (0.035 if open_m and abs(h.x) < 0.26 * sx else 0.0):
            return False
        if abs(h.x) > 0.36 * sx and h.z > -0.25:          # the sideburn stays in front of the ear
            return h.y < -0.06
        return h.y < 0.12

    samples, s = core.surface_samples(head, 1300, keep)
    el = core.sheet_elems(samples, s, lambda h, n: 0.036 + 0.026 * core.smoothstep(0.0, 0.2, line(h.x) - h.z))
    for k in range(7):
        t = k / 6
        z = zj - (zj - tip_z) * (0.05 + 0.80 * t)
        w = half_w(z)
        for sd in (-1, 1):
            g, _ = guide(sd * 0.50 * w, z)
            el.append(dict(co=(sd * 0.50 * w, g.y + 0.13, z), half=(0.42 * w, 0.12, 0.12), stiff=2.0))
    # the clumps: 4 per side at u = 0.13, 0.38, 0.63, 0.88 of the width; roots on the face under the beard line,
    # ends on the lobe outline (rounded: the middle of each lobe hangs lowest)
    lobe_x = 0.24 * wide
    for sd in (-1, 1):
        # (the tips converge: each side's four end close together, overlapping, so the side closes into one rounded
        # lobe, not four little points)
        for u, (w0, w1), xe in [(0.13, (0.095, 0.07), 0.42), (0.38, (0.105, 0.075), 0.72),
                                (0.63, (0.11, 0.075), 1.0), (0.88, (0.10, 0.07), 1.28)]:
            x_root = sd * u * half_w(-0.10)
            # (the outer clump starts at the jaw: higher up, the sideburn's edge turns away and its round root would
            # stand out of the face's outline as a horn)
            z_root = min(line(x_root) - 0.035, -0.16 if u < 0.8 else -0.25)
            if abs(x_root) < 0.30 * sx:                     # under the mouth: just below the beard line there
                # (an open mouth: lower, so the clump's rounded start stays under the lower lip, not over the opening)
                z_root = line(x_root) - (0.08 if open_m else 0.04)
            xe_ = sd * xe * lobe_x
            # the lobe outline: lowest under the lobe's middle, rising to the notch between the two lobes and outward
            d_ = (abs(xe_) - lobe_x) / lobe_x
            ze = tip_z + 0.035 + (0.15 if d_ < 0 else 0.09) * d_ * d_
            # the path only runs down: a root under a big open mouth can sit below the jaw row
            z1 = min(zj, z_root - 0.04)
            ctrl = [(x_root, z_root), (sd * u * half_w(z1), z1)]
            for t in (0.35, 0.68):
                z = z1 - (z1 - tip_z) * t
                x = sd * u * half_w(z)
                ctrl.append((x + (xe_ - x) * t * 0.35, z))
            ctrl.append((xe_, ze))
            pts, nrs = [], []
            for x, z in ctrl:
                g, n_ = guide(x, z)
                pts.append(g)
                nrs.append(n_)
            el += core.clump(pts, nrs, w0, w1, th, n=26, lift=0.0, taper_at=0.6, tip=0.7, stiff=2.8, flat=0.75,
                             root=0.22)
    if getattr(ctx, "mouth_open", False):
        pts = ctx.mouth_pts
        zs = [q[1] for q in pts]
        # (a soft, shallow window: the sheet and the clumps already stop under the lower lip; a deep notch left the
        # beard's inner walls around the opening in black shadow, past the albedo floor, §7.4)
        el.append(dict(co=(0.0, fy - 0.06, (min(zs) + max(zs)) / 2 - 0.01), half=(0.15 * sx, 0.08, 0.08), stiff=3.0,
                       neg=True))
    else:
        # the closed mouth: a flat window over the lower lip only (a taller one bared the chin at its two ends — cream
        # "fangs" under the lip, review r3)
        el.append(dict(co=(0.0, fy - 0.08, ctx.L["mouth_z"] - 0.024), half=(0.10 * sx, 0.12, 0.02), stiff=4.0,
                       neg=True))
    # shaded the other way up from hair (§7.4 "волосы у лица — кожа"): light lobe tips where the beard lies on the
    # costume, a darker root band along the face (the "edge" attribute: 1 at the beard line, 0 from 0.08 below it)
    # (the root colour reaches down to the jaw line: the beard next to the skin is the darker part, the light tips lie
    # on the jerkin)
    mat = core.hair_mat(ctx, "beard", bd["color"], tip_z, ctx.L["mouth_z"] - 0.04, dark=bd.get("tip"),
                        light=bd.get("root"), crevice=bd.get("crevice"),
                        edge=("beard_edge", bd["edge"], 0.85) if bd.get("edge") else None)
    o = core.mb_mesh(ctx, "Beard", el, 0.012, mat, smooth_iter=4, name="beard")
    if bd.get("edge"):
        attr = o.data.color_attributes.new("beard_edge", "FLOAT_COLOR", "POINT")
        for i, v in enumerate(o.data.vertices):
            e = 1.0 - core.smoothstep(0.0, 0.08, line(v.co.x) - v.co.z)
            if open_m:
                # not around an open mouth: there the band sits in the opening's shadow and went black (past the
                # albedo floor, §7.4); the lips and teeth separate the beard from the face there
                e *= core.smoothstep(0.20 * sx, 0.30 * sx, abs(v.co.x))
            attr.data[i].color = (e, e, e, 1.0)
    ctx.add(o, "beard", head, kind="embed", head=True)
    ctx.objs["beard"] = o
    ctx.L["beard_tip"] = Vector((0, fy + 0.1, tip_z))
    ctx.sig_objs.append(o)


def _moustache(ctx, bd):
    """A bushy moustache under the nose: two drooping lobes over the upper lip and the mouth corners (the lower lip
    stays visible under it); a grin lifts it and curls the tips up."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    mz = ctx.L["mouth_z"]
    nz = ctx.L["nose_tip"].z
    top = (nz + mz) / 2 + 0.004
    hit, _ = core.ray_front(head, 0, top)
    ys = hit.y
    el = []
    k = bd.get("moustache_k", 1.0)
    for s_ in (-1, 1):
        #        x      dy     z (from `top`)  r
        chain = [(0.03, -0.045, 0.0, 0.052), (0.085, -0.04, -0.006, 0.058), (0.14, -0.024, -0.016, 0.054),
                 (0.19, 0.0, -0.03, 0.046), (0.232, 0.024, -0.05, 0.034), (0.258, 0.042, -0.072, 0.024)]
        if ctx.smile:
            chain = [(x * 1.06, dy, z + 0.026 + 0.07 * core.smoothstep(0.1, 0.26, x), r) for x, dy, z, r in chain]
        mtop = ctx.L.get("mouth_top") if getattr(ctx, "mouth_open", False) else None
        for x, dy, z, r in chain:
            zc = top + z
            if mtop:
                # an open mouth: the lower edge clears the opening's top by 0.012 (its teeth show, §7.6 "с зубами")
                xs_ = s_ * x * sx
                if mtop[0][0] - 0.01 <= xs_ <= mtop[-1][0] + 0.01:
                    zc = max(zc, core.lerp_table(mtop, xs_) + 0.012 + r * k * 0.8)
            el.append(dict(co=(s_ * x * sx, ys + dy + (0.006 if mtop else 0.0), zc), half=r * k, stiff=2.4))
    # the moustache in the hair's rust (darker than the beard top, §7.6 palette slots): it reads as hair over the lip,
    # not as a fleshy upper lip on a beard the skin's own hue
    mat = core.hair_mat(ctx, "moustache", bd.get("moustache_color", bd["color"]), mz - 0.04, mz + 0.1,
                        dark=bd.get("moustache_dark", bd.get("dark")), light=bd.get("moustache_light", bd.get("light")),
                        crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Mous", el, 0.008, mat, smooth_iter=2, name="moustache")
    ctx.add(o, "beard", head, kind="embed", head=True)
    ctx.sig_objs.append(o)


def _beard_mat(ctx, bd, z0, z1, name="beard"):
    return core.hair_mat(ctx, name, bd["color"], z0, z1, dark=bd.get("tip"), light=bd.get("root"),
                         crevice=bd.get("crevice"))


def _register(ctx, o, sig=True, name="beard"):
    ctx.add(o, "beard", ctx.objs["head"], kind="embed", head=True)
    ctx.objs[name] = o
    if sig:
        ctx.sig_objs.append(o)
    return o


# ------------------------------------------------------------------ walrus (Kort)
def _walrus(ctx, bd):
    """Kort's walrus moustache (§7.6: #EDEDF2, 0.85 W wide, hanging 0.25 H below the mouth, the ends below the
    chin): five broad clumps a side from under the nose, out along the upper lip and down over the mouth corners,
    the outer ones longest; over a soft backing. Calm: it hides the mouth. Smile: the ends rise `smile_lift` H and a
    window over the open mouth shows the lip and teeth."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    mz = ctx.L["mouth_z"]
    nz = ctx.L["nose_tip"].z
    chin_z = ctx.L["chin"].z
    top = nz - bd.get("top", 0.035)
    hw = bd.get("w", 0.85) * ctx.W / 2
    drop = bd.get("drop", 0.25) * H
    th = bd.get("clump_th", 0.055)
    lift = bd.get("smile_lift", 0.04) * H if ctx.smile else 0.0
    open_m = getattr(ctx, "mouth_open", False)
    fy = ctx.L["face_y"]

    def guide(x, z):
        hit, nor = core.ray_front(head, x, z)
        if hit is not None and z > chin_z + 0.05 and nor.y < -0.25:
            return hit + nor * th * 0.8, nor
        mh, _ = core.ray_front(head, x * 0.85, max(z, chin_z + 0.06))
        y = (mh.y if mh is not None else fy) - th * 0.9 - 0.012
        return Vector((x, y, z)), Vector((0.35 * x / hw, -1.0, -0.25)).normalized()

    el = []
    for sd in (-1, 1):
        for j, u in enumerate((0.0, 0.22, 0.45, 0.7, 1.0)):
            x0 = sd * (0.02 + 0.075 * u) * sx
            z0 = top - 0.006 * u
            ex = sd * hw * (0.30 + 0.70 * u)
            ez = mz - drop * (0.50 + 0.50 * u) + lift * (0.4 + 1.2 * u)
            x1 = sd * (0.07 + 0.16 * u) * sx
            z1 = top - 0.035 - 0.02 * u + lift * 0.5
            x2 = sd * min(hw * 0.95, (0.15 + 0.22 * u) * sx)
            z2 = mz - 0.02 - drop * 0.25 * u + lift
            ctrl = [(x0, z0), (x1, z1), (x2, z2), (ex, ez)]
            pts, nrs = [], []
            for x, z in ctrl:
                g, n_ = guide(x, z)
                pts.append(g)
                nrs.append(n_)
            w0 = 0.075 + 0.01 * (1 - u)
            el += core.clump(pts, nrs, w0, 0.06, th, n=22, lift=0.0, taper_at=0.6, tip=0.55, stiff=2.8, flat=0.8,
                             root=0.15)
    # the backing: a soft band under the nose over the upper lip (no skin between the clumps)
    for sd in (-1, 1):
        for x in (0.03, 0.10, 0.17):
            g, n_ = guide(sd * x * sx, top - 0.03 + lift * 0.4)
            el.append(dict(co=g - n_ * th * 0.5, half=(0.06, th * 0.8, 0.045), stiff=2.0,
                           rot=core.frame_quat(Vector((0, 0, 1)), n_)))
    if open_m and ctx.smile:
        zs = [q[1] for q in ctx.mouth_pts]
        xs = [q[0] for q in ctx.mouth_pts]
        el.append(dict(co=((min(xs) + max(xs)) / 2, fy - 0.07, (min(zs) + max(zs)) / 2 - 0.005),
                       half=((max(xs) - min(xs)) * 0.42, 0.12, (max(zs) - min(zs)) * 0.62), stiff=3.0, neg=True))
    mat = _beard_mat(ctx, bd, mz - drop - 0.05, top)
    o = core.mb_mesh(ctx, "Walrus", el, 0.010, mat, smooth_iter=4, name="beard")
    _register(ctx, o)
    ctx.L["beard_tip"] = Vector((0, fy, mz - drop))


# ------------------------------------------------------------------ short beard (Seir)
def _short(ctx, bd):
    """A short beard along the jaw (Seir, §7.6: #CFCFD4, 0.06 H, with a moustache): a sheet on the face under the
    beard line (cheek apples bare) `thick` H deep, softened by broad short clumps on the chin and jaw so it reads as
    hair, not a shell; an open mouth keeps its window (the beard line drops under it)."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    line = _beard_line(ctx, bd)
    t = bd.get("thick", 0.06) * H
    open_m = getattr(ctx, "mouth_open", False)

    def keep(h, n, d):
        if h.z > line(h.x) - 0.005 - (0.03 if open_m and abs(h.x) < 0.24 * sx else 0.0):
            return False
        if abs(h.x) > 0.36 * sx and h.z > -0.25:
            return h.y < -0.06
        return h.y < 0.12 and h.z > ctx.L["chin"].z - bd.get("under", 0.06)
    samples, s = core.surface_samples(head, 1800, keep)
    el = core.sheet_elems(samples, s, lambda h, n: t * (0.55 + 0.45 * core.smoothstep(0.0, 0.05, line(h.x) - h.z)))
    chin_z = ctx.L["chin"].z
    for sd in (-1, 1):
        for u in (0.12, 0.38, 0.64, 0.88):
            x = sd * u * 0.40 * sx
            z0 = line(x) - 0.03
            h0, n0 = core.ray_front(head, x, z0)
            h1, n1 = core.ray_front(head, x * 1.02, max(chin_z + 0.03, z0 - 0.10))
            if h0 is None or h1 is None:
                continue
            tip = h1 + Vector((0, -0.005, -0.025 - 0.015 * (1 - u)))
            # (the clumps ride in the sheet, not on it: lifted onto its surface they doubled the beard to a 0.2 H
            # cotton-wool mass round the jaw, P2 review; §7.6 asks 0.06 H)
            cl = bd.get("clump_lift", 0.4)
            el += core.clump([h0 + n0 * t * cl, h1 + n1 * t * cl * 1.25, tip], [n0, n1, n1], 0.06, 0.055,
                             t * bd.get("clump_th", 0.6), n=12, lift=0.0, taper_at=0.6, tip=0.6, stiff=2.6, flat=0.8)
    if open_m:
        zs = [q[1] for q in ctx.mouth_pts]
        el.append(dict(co=(0.0, ctx.L["face_y"] - 0.05, (min(zs) + max(zs)) / 2), half=(0.14 * sx, 0.08, 0.07),
                       stiff=3.0, neg=True))
    mat = _beard_mat(ctx, bd, chin_z - 0.1, ctx.L["mouth_z"])
    o = core.mb_mesh(ctx, "Short", el, 0.010, mat, smooth_iter=3, name="beard")
    _register(ctx, o, sig=False)


# ------------------------------------------------------------------ long beard (Rai)
LONG_PROFILE = [(-1.0, 0.80), (0.0, 1.0), (0.25, 0.88), (0.55, 0.62), (0.8, 0.36), (1.0, 0.12)]
HANG = {
    # Rai (§7.6): three lobes converging to a point
    "long": dict(wider=0.02, below=0.6, profile=LONG_PROFILE, lobes=[(-0.42, 0.62), (0.0, 1.0), (0.42, 0.66)],
                 mode="converge"),
    # Grodek (§7.8 "раздвоенная чёрная борода"): wide, splitting into two points with a notch between them
    "forked": dict(wider=0.05, below=0.52, profile=[(-1.0, 0.80), (0.0, 1.0), (0.3, 0.96), (0.6, 0.86),
                                                     (0.85, 0.76), (1.0, 0.70)],
                   lobes=[(-0.55, 1.0), (0.55, 1.0)], mode="fork"),
    # Ormdek (§7.8 "борода-короб, срезанная прямоугольником"): straight sides, a flat bottom
    "box": dict(wider=0.08, below=0.44, profile=[(-1.0, 0.86), (0.0, 1.0), (0.5, 1.0), (1.0, 0.97)],
                lobes=[(0.0, 1.0)], mode="straight"),
    # Velian (§7.8 "острая бородка"): a narrow pointed goatee on the chin only
    "goatee": dict(width=0.17, below=0.26, profile=[(-1.0, 0.7), (0.0, 1.0), (0.4, 0.8), (0.8, 0.4), (1.0, 0.12)],
                   lobes=[(0.0, 1.0)], mode="converge", chin_only=True),
    # the ruler (§7.10 "ухоженная круглая борода 0.18–0.25 H ниже подбородка"): a rounded bottom
    "round": dict(wider=0.05, below=0.22, profile=[(-1.0, 0.86), (0.0, 1.0), (0.3, 0.96), (0.6, 0.80), (0.85, 0.55),
                                                    (1.0, 0.28)],
                  lobes=[(0.0, 1.0)], mode="round"),
}


def _long(ctx, bd):
    """The hanging beards (HANG): Rai's long beard (§7.6: #EEF0F5 with a blue AO, 0.6 H under the chin, three big
    lobes converging to a point, the moustache flowing in), and the leaders' and the ruler's — forked (two points),
    box (straight sides, a flat bottom), goatee (the chin only), round (a rounded bottom). The pear's construction (a
    guide surface: the face, then an analytic shape below the chin) with the style's profile and lobes."""
    d = dict(HANG[bd["style"]])
    d.update({k: v for k, v in bd.items() if k in ("wider", "below", "profile", "lobes", "mode", "width")})
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    line = _beard_line(ctx, bd)
    chin_z = ctx.L["chin"].z
    jaw_x = abs(ctx.L["jaw_near"].x) if ctx.L.get("jaw_near") else 0.4 * sx
    wide = d["width"] * ctx.W if d.get("width") else jaw_x + d.get("wider", 0.02) * ctx.W
    tip_z = chin_z - d.get("below", 0.6) * H
    fy = ctx.L["face_y"]
    zj = chin_z + (0.03 if d.get("chin_only") else 0.07)
    th = bd.get("clump_th", 0.06)
    open_m = getattr(ctx, "mouth_open", False)
    prof = d["profile"]
    mode = d.get("mode", "converge")
    chin_only = d.get("chin_only", False)

    def half_w(z):
        tt = (zj - z) / (zj - tip_z)
        return wide * core.lerp_table(prof, tt)

    def guide(x, z):
        w = half_w(z)
        u = x / max(w, 1e-6)
        tt = max(0.0, (zj - z) / (zj - tip_z))
        if z > chin_z - 0.02:
            hit, nor = core.ray_front(head, x, z)
            if hit is not None:
                return hit + nor * 0.05, nor
        ya = fy - 0.01 + 0.04 * tt + 0.35 * w * u * u
        return Vector((x, ya, z)), Vector((0.8 * u / max(w, 0.2), -1.0, -0.1 * tt)).normalized()

    def keep(h, n, d_):
        if chin_only:
            # a goatee: the chin under the lower lip only
            return (abs(h.x) < wide * 0.95 and h.z < ctx.L["mouth_z"] - 0.045 - (0.03 if open_m else 0.0)
                    and h.y < 0.0)
        if h.z > line(h.x) - 0.01 - (0.035 if open_m and abs(h.x) < 0.26 * sx else 0.0):
            return False
        if abs(h.x) > 0.36 * sx and h.z > -0.25:
            return h.y < -0.06
        return h.y < 0.12
    samples, s = core.surface_samples(head, 1300, keep)
    el = core.sheet_elems(samples, s, lambda h, n: 0.036 + 0.026 * core.smoothstep(0.0, 0.2, line(h.x) - h.z))
    for k in range(8):
        t = k / 7
        z = zj - (zj - tip_z) * (0.05 + 0.8 * t)
        w = half_w(z)
        g, _ = guide(0.0, z)
        el.append(dict(co=(0.0, g.y + 0.12, z), half=(0.8 * w, 0.12, 0.12), stiff=2.0))
    # the lobes: the clumps of each lobe converge to its end ("converge"; the middle lobe reaches the tip), split
    # into two points ("fork"), hang straight to a flat bottom ("straight") or end on a rounded bottom ("round")
    lobes = d.get("lobes", [(-0.42, 0.62), (0.0, 1.0), (0.42, 0.66)])     # (x share, depth share)
    us = [(-0.82, (0.09, 0.07)), (-0.55, (0.10, 0.075)), (-0.28, (0.105, 0.08)), (0.0, (0.11, 0.08)),
          (0.28, (0.105, 0.08)), (0.55, (0.10, 0.075)), (0.82, (0.09, 0.07))]
    if chin_only:
        us = [(-0.6, (0.07, 0.05)), (-0.2, (0.08, 0.055)), (0.2, (0.08, 0.055)), (0.6, (0.07, 0.05))]
    for u, (w0, w1) in us:
        lx, ld = min(lobes, key=lambda lb: abs(lb[0] - u * 0.75))
        x_root = u * half_w(-0.10)
        z_root = line(x_root) - (0.08 if (open_m and abs(x_root) < 0.3 * sx) else 0.04)
        z_root = min(z_root, -0.16 if abs(u) < 0.8 else -0.25)
        if chin_only:
            x_root = u * wide * 0.8
            z_root = ctx.L["mouth_z"] - 0.06 - (0.04 if open_m else 0.0)
        ze = zj - (zj - tip_z) * ld
        if mode == "straight":
            ze = tip_z + 0.02 * (1 - abs(u))
            xe = u * half_w(ze) * 1.05
        elif mode == "round":
            ze = zj - (zj - tip_z) * (1.0 - 0.55 * u * u)
            xe = u * half_w(ze) * 0.9
        elif mode == "fork":
            xe = lx * half_w(ze) * 1.15 + (u - lx) * 0.06
            ze = ze + 0.10 * abs(u - lx)
        else:
            xe = lx * half_w(ze) * 1.6 + (u - lx) * 0.05
        z1 = min(zj, z_root - 0.04)
        ctrl = [(x_root, z_root), (u * half_w(z1), z1)]
        for t in (0.35, 0.7):
            z = z1 - (z1 - ze) * t
            x = u * half_w(z) * (1 - t) + xe * t
            ctrl.append((x, z))
        ctrl.append((xe, ze))
        pts, nrs = [], []
        for x, z in ctrl:
            g, n_ = guide(x, z)
            pts.append(g)
            nrs.append(n_)
        el += core.clump(pts, nrs, w0, w1, th, n=26, lift=0.0, taper_at=0.6,
                         tip=0.4 if mode != "straight" else 0.85, stiff=2.8, flat=0.75, root=0.2)
    if bd.get("jut"):
        # anger pushes the beard forward (Ormdek, §7.8 "борода выпячивается")
        for e in el:
            if not e.get("neg") and e["co"][2] < chin_z:
                c = Vector(e["co"])
                e["co"] = c + Vector((0.0, -bd["jut"] * core.smoothstep(chin_z, tip_z, c.z), 0.0))
    if open_m:
        zs = [q[1] for q in ctx.mouth_pts]
        el.append(dict(co=(0.0, fy - 0.06, (min(zs) + max(zs)) / 2 - 0.01), half=(0.15 * sx, 0.08, 0.08), stiff=3.0,
                       neg=True))
    else:
        el.append(dict(co=(0.0, fy - 0.08, ctx.L["mouth_z"] - 0.024), half=(0.10 * sx, 0.12, 0.02), stiff=4.0,
                       neg=True))
    mat = core.hair_mat(ctx, "beard", bd["color"], tip_z, ctx.L["mouth_z"] - 0.04, dark=bd.get("tip"),
                        light=bd.get("root"), crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Long", el, 0.012, mat, smooth_iter=4, name="beard")
    _register(ctx, o, sig=bd.get("signature", False))
    ctx.L["beard_tip"] = Vector((0, fy + 0.1, tip_z))
    ctx.L["beard_wide"] = wide


# ------------------------------------------------------------------ thin moustache (Hawk)
def _thin(ctx, bd):
    """A thin moustache (Hawk, §7.6: 0.04 H, #3A2414, the ends curled up 0.02): two tapered curves from the philtrum
    out along the upper lip past the corners, the tips turning up (higher in the smile, with the corners)."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    mz = ctx.L["mouth_z"]
    nz = ctx.L["nose_tip"].z
    t = bd.get("thick", 0.04) * H
    mp = ctx.ch["mouth"].get(ctx.mood, ctx.ch["mouth"]["calm"])
    mtop = ctx.L.get("mouth_top") if getattr(ctx, "mouth_open", False) else None
    base = mz + bd.get("above", 0.035) * H
    mat = core.hair_mat(ctx, "beard", bd["color"], mz - 0.05, mz + 0.1, dark=bd.get("tip"), light=bd.get("root"),
                        crevice=bd.get("crevice"))
    # two tapered halves parted at the philtrum, kept inside the mouth's width (§7.6 0.04 H, the ends up 0.02):
    # one long bar past the corners read as a stick or a cigarette across the lip at 128 px (P2 review)
    half_w = mp.get("w", 0.27) * H / 2
    x0, x1 = bd.get("part", 0.022), bd.get("reach", 0.92) * half_w / sx
    for sd in (-1, 1):
        lift = (mp.get("near" if sd < 0 else "far", 0.0)) * H
        pts, rad = [], []
        n = 9
        for i in range(n):
            f = i / (n - 1)
            x = sd * (x0 + (x1 - x0) * f) * sx
            z = (base - 0.004 * math.sin(math.pi * f) + lift * f ** 2
                 + bd.get("curl", 0.02) * H * core.smoothstep(0.6, 1.0, f) * 1.4)
            if mtop and mtop[0][0] - 0.01 <= x <= mtop[-1][0] + 0.01:
                z = max(z, core.lerp_table(mtop, x) + t * 0.7)
            z = min(z, nz - t * 0.9)
            h, nn = core.ray_front(head, x, z)
            if h is None:
                continue
            pts.append(h + nn * t * 0.25)
            # rounded at the parting, fullest a third of the way out, tapering to a fine upturned tip
            rad.append((0.55 + 0.45 * math.sin(math.pi * min(1.0, f * 1.6)))
                       * (1 - 0.75 * core.smoothstep(0.45, 1.0, f)))
        o = core.curve("moustache%+d" % sd, pts, rad, t / 2, mat)
        ctx.add(o, "beard", head, kind="surface", head=True)


# ------------------------------------------------------------------ mutton chops (Olm)
def _chops(ctx, bd):
    """Mutton-chop sideburns (Olm, §7.6: "бакенбарды-котлеты 0.16 W, слиты с пучками; подбородок голый"): on each
    cheek in front of the ear, from the tuft above the ear down past the jaw corner — a band of the head between two
    azimuths (its front edge widening downward to `w` W) — a sheet with broad downward clumps over it; the chin and
    the upper lip stay bare."""
    head = ctx.objs["head"]
    w = bd.get("w", 0.16) * ctx.W
    t = bd.get("thick", 0.05)
    z_top = ctx.P["eye_z"] + 0.03
    z_bot = ctx.L["mouth_z"] - bd.get("below", 0.03) * H
    el = []
    for sd in (-1, 1):
        ear = ctx.L["ear_" + ("near" if sd < 0 else "far")][0]
        if ear is None:
            continue
        az_back = abs(math.degrees(math.atan2(ear.x, -ear.y))) - 4      # the ear's front edge
        r_ = math.hypot(ear.x, ear.y)

        def keep(h, n, d, sd=sd, az_back=az_back, r_=r_):
            if h.x * sd <= 0 or not (z_bot < h.z < z_top):
                return False
            az = abs(math.degrees(math.atan2(h.x, -h.y)))
            zz = (h.z - z_bot) / (z_top - z_bot)
            span = math.degrees(w * (0.75 + 0.55 * (1 - zz)) / max(r_, 0.2))
            return az_back - span < az < az_back + 6
        samples, s = core.surface_samples(head, 2600, keep)
        el += core.sheet_elems(samples, s, lambda h, n: t * (0.6 + 0.4 * core.smoothstep(z_bot, z_bot + 0.08, h.z)))
        for k in range(3):
            f = (k + 0.5) / 3
            span_top = math.degrees(w * 0.75 / max(r_, 0.2))
            span_bot = math.degrees(w * 1.3 / max(r_, 0.2))
            a0 = math.radians(sd * (az_back - span_top * f))
            a1 = math.radians(sd * (az_back - span_bot * f))
            d0 = Vector((math.sin(a0), -math.cos(a0), 0.0))
            d1 = Vector((math.sin(a1), -math.cos(a1), 0.0))
            h0, n0 = core.ray(head, Vector((0, 0, z_top - 0.03)) + d0 * 2, -d0)
            h1, n1 = core.ray(head, Vector((0, 0, z_bot + 0.03)) + d1 * 2, -d1)
            if h0 is None or h1 is None:
                continue
            tip = h1 + n1 * t * 0.4 + Vector((0, 0, -0.05))
            el += core.clump([h0 + n0 * t * 0.5, h1 + n1 * t * 0.6, tip], [n0, n1, n1], 0.055, 0.065, t * 0.7, n=12,
                             lift=0.0, taper_at=0.6, tip=0.55, stiff=2.6, flat=0.8)
    mat = _beard_mat(ctx, bd, z_bot - 0.05, z_top)
    o = core.mb_mesh(ctx, "Chops", el, 0.010, mat, smooth_iter=3, name="beard")
    ctx.details["sideburns"] = bd.get("min_px", 2000)
    ctx.add(o, "detail:sideburns", head, kind="embed", head=True)     # its own ID group: P-A8 "бакенбарды 2000"
    ctx.objs["beard"] = o


# ================================================================== P3: braids and an upturned moustache (§7.8)
def _braids(ctx, bd):
    """Torvald's beard (§7.8: "длинная седая борода двумя толстыми косами с каменными бусинами"): a short hanging
    mass under the chin (the "long" construction, 0.22 H, rounded) from which two thick plaits hang to `below` H under
    the chin — flat lobes leaning +-25 deg in turn along a gently curving path, narrowing — each tied off with sandstone
    beads (`bead`)."""
    short = dict(bd, style="round", below=bd.get("mass_below", 0.22), wider=bd.get("wider", 0.02), signature=True)
    _long(ctx, short)
    o_mass = ctx.objs["beard"]
    chin_z = ctx.L["chin"].z
    fy = ctx.L["face_y"]
    wide = ctx.L.get("beard_wide", 0.35)
    ln = bd.get("below", 0.62) * H
    w = bd.get("plait_w", 0.13) * H
    el = []
    beads = []
    for sd in (-1, 1):
        x0 = sd * wide * bd.get("spread", 0.42)
        top = Vector((x0, fy - 0.02, chin_z - 0.08))
        bot = Vector((x0 * 0.85, fy + 0.06, chin_z - ln))
        n = 9
        prev = top
        for i in range(n):
            t = i / (n - 1)
            p = top.lerp(bot, t) + Vector((0.0, -0.04 * math.sin(math.pi * t), 0.0))
            ww = w * (1.0 - 0.35 * t)
            lean = math.radians(25 * (1 if i % 2 else -1))
            along = (bot - top).normalized()
            q = core.frame_quat(along, Vector((0, -1, 0)))
            from mathutils import Quaternion
            q = q @ Quaternion((0, 1, 0), lean)
            el.append(dict(co=p, half=(ww * 0.55, ww * 0.30, ww * 0.62), stiff=2.6, rot=q))
            prev = p
        for t in bd.get("beads", (0.12, 1.02)):
            beads.append((top.lerp(bot, t) + Vector((0, -0.01, 0)), w * (0.42 if t < 0.5 else 0.48)))
    mat = core.hair_mat(ctx, "braids", bd["color"], chin_z - ln, chin_z, dark=bd.get("tip"), light=bd.get("root"),
                        crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Braids", el, 0.010, mat, smooth_iter=2, name="beard_braids")
    ctx.add(o, "beard", o_mass, kind="embed", head=True)
    ctx.sig_objs.append(o)
    stone = core.principled(ctx, "bead_stone", bd.get("bead", "#C8B48A"), rough=0.75)
    for k, (c, r) in enumerate(beads):
        b = core.uvsphere("beard_bead%d" % k, c, (r, r * 0.9, r * 0.8), stone, 20, 10)
        ctx.add(b, "detail:beads", o, kind="embed", head=True)
    ctx.details["beads"] = bd.get("bead_px", 150)


def _upturned(ctx, bd):
    """An upturned moustache (Velian, §7.8 "закрученные вверх усы"): two tapered curves from the philtrum out along
    the upper lip past the corners, then curling up (`curl` H; negative: the tips droop — his anger), thicker than
    Hawk's thin one, the outer half off the face."""
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    mz = ctx.L["mouth_z"]
    nz = ctx.L["nose_tip"].z
    t = bd.get("m_thick", 0.05) * H
    curl = bd.get("curl", 0.09) * H
    reach = bd.get("reach", 0.34)
    mtop = ctx.L.get("mouth_top") if getattr(ctx, "mouth_open", False) else None
    base = mz + bd.get("above", 0.04) * H
    mat = core.hair_mat(ctx, "moustache", bd.get("moustache_color", bd["color"]), mz - 0.05, mz + 0.12,
                        dark=bd.get("tip"), light=bd.get("root"), crevice=bd.get("crevice"))
    for sd in (-1, 1):
        pts, rad = [], []
        n = 12
        for i in range(n):
            f = i / (n - 1)
            x = sd * (0.02 + (reach - 0.02) * min(1.0, f / 0.7)) * sx
            z = base - 0.006 * math.sin(math.pi * min(1.0, f / 0.7))
            if f > 0.6:
                g = (f - 0.6) / 0.4
                x += sd * 0.03 * sx * math.sin(math.pi * g) - sd * 0.02 * sx * g * g
                z += curl * g ** 1.3
            if mtop and mtop[0][0] - 0.01 <= x <= mtop[-1][0] + 0.01:
                z = max(z, core.lerp_table(mtop, x) + t * 0.7)
            z = min(z, nz - t * 0.9) if f < 0.5 else z
            h, nn = core.ray_front(head, x, z)
            if h is None or f > 0.7:
                # off the face's outline: keep going in front of the cheek
                hh, n2 = core.ray_front(head, x * 0.85, z)
                y = (hh.y - 0.02) if hh is not None else ctx.L["face_y"] + 0.05
                pts.append(Vector((x, y - t * 0.3, z)))
            else:
                pts.append(h + nn * t * 0.35)
            rad.append((0.6 + 0.4 * math.sin(math.pi * min(1.0, f * 1.8))) * (1 - 0.7 * core.smoothstep(0.6, 1.0, f)))
        o = core.curve("moustache%+d" % sd, pts, rad, t / 2, mat)
        ctx.add(o, "beard", head, kind="surface", head=True)
