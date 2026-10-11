"""Beards and moustaches (§7.5 step 4): a few broad, smooth strand groups (core.clump) laid along a guide surface —
the face above the chin, an analytic shape below it — over a hidden backing (a sparse sheet of large balls on the face
plus big soft volumes), so soft grooves run between the groups (no small bumps, no separate "petals", art director
note 3); a negative element keeps the mouth clear; the beard's upper edge depends on the mood (an open laugh needs
its lower lip and a little chin clear, its corners covered). Converted to a mesh, Smooth 4 (§7.5: no Subsurf).

Styles (chars.py "beard": {"style": ...}):
  pear — wider than the jaw by `wider` W on each side, `below` H under the chin, two rounded lower lobes (Bram's
         signature: the lower head wider than the top), with a bushy moustache.
"""
from mathutils import Vector

from . import core
from .core import H


def build_beard(ctx):
    bd = ctx.ch.get("beard")
    if not bd:
        return
    {"pear": _pear}[bd["style"]](ctx, bd)
    if bd.get("moustache"):
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
    zj = chin_z + 0.07                                      # the widest row, at the jaw line
    th = bd.get("clump_th", 0.06)

    def half_w(z):
        """The pear's half width at z: the sideburns' width up on the cheek, widest at the jaw, two lobes at the tip."""
        t = (zj - z) / (zj - tip_z)
        return wide * core.lerp_table([(-1.0, 0.78), (0.0, 1.0), (0.3, 0.90), (0.6, 0.68), (0.85, 0.50), (1.0, 0.42)], t)

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
            el.append(dict(co=(s_ * x * sx, ys + dy, zc), half=r * k, stiff=2.4))
    # the moustache in the hair's rust (darker than the beard top, §7.6 palette slots): it reads as hair over the lip,
    # not as a fleshy upper lip on a beard the skin's own hue
    mat = core.hair_mat(ctx, "moustache", bd.get("moustache_color", bd["color"]), mz - 0.04, mz + 0.1,
                        dark=bd.get("moustache_dark", bd.get("dark")), light=bd.get("moustache_light", bd.get("light")),
                        crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Mous", el, 0.008, mat, smooth_iter=2, name="moustache")
    ctx.add(o, "beard", head, kind="embed", head=True)
    ctx.sig_objs.append(o)
