"""Beards and moustaches (§7.5 step 4): a mass from a sheet of balls sampled under the beard line plus rounded lobes,
then ribbon locks cast onto a temporary mesh of that mass so they sit ~0.02 above it (soft grooves, not separate
"petals"); a negative element keeps the mouth clear; the beard's upper edge depends on the mood (an open laugh
needs its lower lip and a little chin clear). Converted to a mesh, Smooth 2 (§7.5).

Styles (chars.py "beard": {"style": ...}):
  pear — wider than the jaw by `wider` W on each side, `below` H under the chin, two lower lobes (Bram's
         signature: the lower head wider than the top), with a bushy moustache.
"""
import math

import bpy
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
        mid = [(0.0, zs), (0.08, zs + 0.004), (0.16, zs + 0.03), (0.22, mz - 0.01)]
    else:
        mid = [(0.0, mz - 0.07), (0.08, mz - 0.064), (0.16, mz - 0.04), (0.22, mz - 0.012)]
    tbl = mid + [(0.28, mz + 0.035), (0.34, mz + 0.085), (0.40, mz + 0.15), (0.44, mz + 0.23), (0.5, mz + 0.27)]
    return lambda x: core.lerp_table([(a * sx, b) for a, b in tbl], abs(x))


def _pear(ctx, bd):
    head = ctx.objs["head"]
    sx = ctx.P["hx"] / 0.48
    line = _beard_line(ctx, bd)
    chin_z = ctx.L["chin"].z
    jaw_x = abs(ctx.L["jaw_near"].x) if ctx.L.get("jaw_near") else 0.4 * sx
    wide = jaw_x + bd.get("wider", 0.12) * ctx.W          # half width of the beard's widest row
    tip_z = chin_z - bd.get("below", 0.45) * H              # the lowest point (lobe bottoms)

    def keep(h, n, d):
        if h.z > line(h.x):
            return False
        if abs(h.x) > 0.36 * sx and h.z > -0.25:          # the sideburn stays in front of the ear
            return h.y < -0.06
        return h.y < 0.12

    samples, s = core.surface_samples(head, 2400, keep)

    def thick(h, n):
        depth = line(h.x) - h.z
        side = core.smoothstep(0.25 * sx, 0.46 * sx, abs(h.x))
        full = core.smoothstep(0.0, 0.25, depth)
        return (0.022 + 0.085 * full) * (1 - 0.55 * side) * (0.45 + 0.55 * core.smoothstep(0.0, 0.05, depth))

    el = core.sheet_elems(samples, s, thick)
    # the pear: lobes swelling out to `wide` at the jaw line and down to two rounded lower lobes
    fy = ctx.L["face_y"]
    lobes = []
    for x, dz, r, yo in [(-0.78, 0.18, 0.12, 0.25), (0.78, 0.18, 0.12, 0.25),          # widest row (in units of wide)
                         (-0.55, 0.0, 0.14, 0.12), (0.55, 0.0, 0.14, 0.12),
                         (-0.22, -0.02, 0.15, 0.06), (0.22, -0.02, 0.15, 0.06),
                         (-0.40, -0.22, 0.13, 0.08), (0.40, -0.22, 0.13, 0.08),
                         (0.0, -0.18, 0.13, 0.05)]:
        lobes.append((x * wide, fy + 0.10 + yo, chin_z + dz * (chin_z - tip_z) - 0.06, r))
    # the two lower lobes (the pear's bottom), split by a shallow notch
    lo = tip_z + 0.10
    lobes += [(-0.20 * wide, fy + 0.13, lo, 0.115), (0.20 * wide, fy + 0.13, lo, 0.115),
              (-0.12 * wide, fy + 0.12, lo + 0.08, 0.10), (0.12 * wide, fy + 0.12, lo + 0.08, 0.10)]
    for x, y, z, r in lobes:
        el.append(dict(co=(x, y, z), half=r, stiff=2.3))
    tmp = core.to_mesh(core.metaball(ctx, "BeardMass", el, 0.012))
    core.update()
    lock_el = []
    strands = [(-0.3, -0.27, -0.24, -0.62), (-0.15, -0.40, -0.12, -0.92), (0.0, -0.42, -0.01, -0.88),
               (0.15, -0.40, 0.12, -0.92), (0.3, -0.27, 0.24, -0.62), (-0.40, -0.12, -0.42, -0.52),
               (0.40, -0.12, 0.42, -0.52), (-0.52, -0.32, -0.36, -0.70), (0.52, -0.32, 0.36, -0.70)]
    for x0, z0, x1, z1 in strands:
        x0, x1 = x0 * wide / 0.52, x1 * wide / 0.52
        z0 = chin_z + (z0 + 0.53) * 1.0
        z1 = chin_z + (z1 + 0.53) * (chin_z - tip_z) / 0.45
        prev = None
        for k in range(9):
            t = k / 8
            x = x0 + (x1 - x0) * t
            z = z0 + (z1 - z0) * t
            hit, nor = core.ray_front(tmp, x, z)
            if hit is None:
                continue
            w = 0.05 + 0.03 * math.sin(math.pi * min(1.0, t * 1.15))
            if prev is not None:
                seg = (hit - prev).length
                lock_el.append(dict(co=(hit + prev) / 2 - nor * 0.016, half=(w, 0.026, seg * 0.85 + 0.02), stiff=2.2,
                                    rot=core.frame_quat(hit - prev, nor)))
            prev = hit
    bpy.data.objects.remove(tmp)
    el += lock_el
    if getattr(ctx, "mouth_open", False):
        pts = ctx.mouth_pts
        zs = [q[1] for q in pts]
        el.append(dict(co=(0.0, fy - 0.08, (min(zs) + max(zs)) / 2 - 0.01), half=(0.16 * sx, 0.12, 0.09), stiff=4.0,
                       neg=True))
    else:
        el.append(dict(co=(0.0, fy - 0.08, ctx.L["mouth_z"] - 0.006), half=(0.07 * sx, 0.12, 0.026), stiff=4.0,
                       neg=True))
    mat = core.hair_mat(ctx, "beard", bd["color"], tip_z, ctx.L["mouth_z"] + 0.1, dark=bd.get("dark"),
                        light=bd.get("light"), crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Beard", el, 0.011, mat, smooth_iter=3, name="beard")
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
        for x, dy, z, r in chain:
            el.append(dict(co=(s_ * x * sx, ys + dy, top + z), half=r * k, stiff=2.4))
    mat = core.hair_mat(ctx, "moustache", bd["color"], mz - 0.04, mz + 0.1, dark=bd.get("dark"), light=bd.get("light"),
                        crevice=bd.get("crevice"))
    o = core.mb_mesh(ctx, "Mous", el, 0.008, mat, smooth_iter=2, name="moustache")
    ctx.add(o, "beard", head, kind="embed", head=True)
    ctx.sig_objs.append(o)
