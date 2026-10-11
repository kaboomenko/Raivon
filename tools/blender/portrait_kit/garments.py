"""Costume layers (§7.5 steps 6–7, §7.3 "Костюм"): shells built from the torso rings (resampled finely, shrinkwrapped
just outside what they cover, a front opening cut, solidified >= 0.02 H, Subsurf for rounded edges), collars with
real thickness, belts, front panels (an apron bib), straps that follow the costume and end under something, and
the cord work (frogging) cast onto the chest. Layers sit 0.012 H apart (STYLE["layer_gap"]).

A character's costume is data (chars.py "costume"): {"base": {...}, "layers": [...]} — this module has no branch per
character. Kinds: vest, collar, belt, bib, strap, frogging, placket. Every layer registers the object it lies on
(the contact test) and adds itself to ctx.outer (what later layers and props are cast onto).
"""
import math

import bmesh
from mathutils import Vector

from . import core
from .core import H, S


def base_materials(ctx):
    cs = ctx.ch["costume"]
    b = cs["base"]
    ctx.mats["base"] = core.fabric(ctx, "base", b["color"], rough=b.get("rough", 0.8), sheen=b.get("sheen", 0.3))
    sl = cs.get("sleeve")
    if sl:
        ctx.mats["sleeve"] = core.fabric(ctx, "sleeve", sl["color"], rough=sl.get("rough", 0.8), sheen=sl.get("sheen", 0.3))
    return ctx.mats["base"]


def build_layers(ctx):
    ctx.outer = [ctx.objs["torso"], ctx.objs["arm-1"], ctx.objs["arm+1"]]
    for i, ly in enumerate(ctx.ch["costume"].get("layers", [])):
        fn = {"vest": vest, "collar": collar, "belt": belt, "bib": bib, "strap": strap, "frogging": frogging,
              "placket": placket}[ly["kind"]]
        fn(ctx, ly, "%s%d" % (ly["kind"], i))
        core.update()


def _mat(ctx, ly, name):
    if ly.get("metal"):
        return core.principled(ctx, name, ly["color"], rough=ly.get("rough", 0.3), metal=ly.get("metallic", 0.5))
    return core.fabric(ctx, name, ly["color"], rough=ly.get("rough", 0.8), sheen=ly.get("sheen", 0.3))


def _group(ly):
    return ("detail:" + ly["detail"]) if ly.get("detail") else ("metal" if ly.get("metal") else "costume")


# ------------------------------------------------------------------ shells
def vest(ctx, ly, name):
    """A sleeveless jerkin / jacket body: torso rings z0..z1, shrinkwrapped outside the torso, a front opening."""
    spec = ctx.torso_spec
    z0, z1 = ly.get("z0", -1.4), ly.get("z1", -0.64)
    nz, seg = 18, 72
    zs = [z0 + (z1 - z0) * i / (nz - 1) for i in range(nz)]
    bm = bmesh.new()
    rings = [core.superellipse_ring(bm, z, *core.ring_at(spec, z), seg=seg) for z in zs]
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    op = ly.get("open")
    if op:
        def opening(z):
            return core.lerp_table(op, z) * ctx.shoulder_k
        kill = [f for f in bm.faces if f.calc_center_median().y < 0 and abs(f.calc_center_median().x)
                < opening(f.calc_center_median().z)]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    o = core.mesh_obj(name, bm)
    core.shrinkwrap(o, ctx.objs["torso"], S["layer_gap"] * H)
    core.solidify(o, max(S["layer_min"] * H, ly.get("thick", 0.03)), offset=1.0)
    m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], 1.06), core.hex_scale(ly["color"], 0.9), z0, z1,
                      rough=ly.get("rough", 0.85), sheen=ly.get("sheen", 0.35))
    core.finish(o, m, sub=2)
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    return o


def collar(ctx, ly, name):
    """A stand collar around the neck base: a short tube with real thickness and a rounded top edge (§7.3: no flat
    triangle). Height in H; 'open' leaves a front gap (a V)."""
    spec = ctx.torso_spec
    zb = ly.get("z", -0.66)
    hgt = ly.get("h", 0.06) * H
    out = ly.get("out", 0.02)
    seg = 64
    bm = bmesh.new()
    rings = []
    for k in range(5):
        z = zb + hgt * k / 4
        hx, hy, n, yo = core.ring_at(spec, min(z, -0.40))
        grow = out + ly.get("flare", 0.02) * k / 4
        rings.append(core.superellipse_ring(bm, z, hx + grow, hy + grow, n, yo, seg=seg))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    gap = ly.get("gap", 0.0)
    if gap:
        kill = [f for f in bm.faces if f.calc_center_median().y < 0 and abs(f.calc_center_median().x) < gap]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["collar"] * H, ly.get("thick", 0.03)), offset=1.0)
    core.finish(o, _mat(ctx, ly, name), sub=2)
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    return o


def belt(ctx, ly, name):
    spec = ctx.torso_spec
    z = ly.get("z", -1.15)
    w = ly.get("w", 0.13)
    over = ly.get("over", 0.045)          # how far out of the torso: clears the layer under it (vest: gap + thickness)
    seg = 64
    bm = bmesh.new()
    rings = []
    for dz in (-w / 2, -w / 4, 0, w / 4, w / 2):
        hx, hy, n, yo = core.ring_at(spec, z + dz)
        rings.append(core.superellipse_ring(bm, z + dz, hx + over, hy + over, n, yo, seg=seg))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    o = core.mesh_obj(name, bm)
    core.solidify(o, ly.get("thick", 0.035), offset=1.0)
    m = core.principled(ctx, name, ly["color"], rough=0.5, sheen=0.15, coat=0.1)
    core.finish(o, m, sub=2)
    ctx.add(o, "costume", ctx.outer[-1], kind="surface")
    ctx.outer.append(o)
    ctx.objs["belt"] = o
    core.update()
    bk = ly.get("buckle")
    if bk:
        h, nrm = core.ray_front(o, ly.get("buckle_x", 0.0), z)
        brass = core.principled(ctx, "brass", bk, 0.3, metal=0.5)
        fr = core.box("buckle", h + nrm * 0.022, (0.17, 0.035, 0.15), brass, bev=0.035, segs=4)
        core.align_z(fr, nrm)
        fr.rotation_quaternion = fr.rotation_quaternion @ _x90()
        ctx.add(fr, "metal", o, kind="surface")
        hole = core.box("buckle_in", h + nrm * 0.03, (0.10, 0.03, 0.085), m, bev=0.025, segs=3)
        core.align_z(hole, nrm)
        hole.rotation_quaternion = hole.rotation_quaternion @ _x90()
        ctx.add(hole, "costume", fr, kind="embed")
        pin = core.uvsphere("buckle_pin", h + nrm * 0.05, (0.014, 0.014, 0.05), brass, 12, 8)
        pin.rotation_euler = (0, math.radians(90), 0)
        ctx.add(pin, "metal", fr, kind="embed")
        ctx.L["buckle"] = (h, nrm)
    return o


def _x90():
    from mathutils import Quaternion
    return Quaternion((1, 0, 0), math.radians(90))


def bib(ctx, ly, name):
    """An apron bib: a front panel projected onto the costume (shrinkwrap along Y), with straps over the shoulders."""
    k = ctx.shoulder_k
    w = ly.get("w", 0.30) * k
    top, bottom = ly.get("top", -0.80), ly.get("bottom", -2.0)
    bm = bmesh.new()
    nx, nz = 10, 24
    grid = []
    for j in range(nz + 1):
        z = bottom + (top - bottom) * j / nz
        ww = w * (1.0 + 0.25 * (1 - j / nz))           # a little wider toward the waist
        row = [bm.verts.new((-ww + 2 * ww * i / nx, -1.2, z)) for i in range(nx + 1)]
        grid.append(row)
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    o = core.mesh_obj(name, bm)
    tgt = ctx.outer[-1] if ly.get("over_last") else ctx.objs["torso"]
    core.shrinkwrap(o, tgt, S["layer_gap"] * H, method="PROJECT", project_y=True)
    core.solidify(o, max(S["layer_min"] * H, 0.026), offset=1.0)
    m = core.fabric(ctx, name, ly["color"], rough=0.85, sheen=0.25)
    core.finish(o, m, sub=1)
    core.bevel(o, S["bevel"] * H * 1.5, 2)
    ctx.add(o, _group(ly), tgt, kind="surface")
    ctx.outer.append(o)
    ctx.objs["bib"] = o
    core.update()
    if ly.get("straps"):
        for s in (-1, 1):
            pts = []
            for t in range(9):
                f = t / 8
                x = s * (w * 0.80 + (0.36 * k - w * 0.80) * f)
                zz = top + 0.02 + (-0.655 - top) * min(1.0, f * 1.3)
                y_dir = -1 if f < 0.75 else 0.0
                if f < 0.8:
                    h, n, _ = core.ray_any([ctx.objs["torso"]], (x, -2.0, zz), (0, 1, 0))
                else:
                    h, n, _ = core.ray_any([ctx.objs["torso"]], (x, 0.05 - 0.3 * (1 - f), 2.0), (0, 0, -1))
                if h is not None:
                    pts.append(h + n * (S["layer_gap"] * H + 0.012))
            if len(pts) > 2:
                st = core.curve(name + "_strap%+d" % s, pts, [1.0] * len(pts), 0.03, m)
                st.data.bevel_mode = "ROUND"
                st.scale = (1, 1, 1)
                ctx.add(st, "costume", ctx.objs["torso"], kind="surface")
                del y_dir
    return o


def strap(ctx, ly, name):
    """A strap over the costume from (x0, z0) to (x1, z1) (front view), cast onto ctx.outer every step, a flat band
    >= 0.02 H thick with rounded edges; both ends run off under the shoulder line or the frame."""
    k = ctx.shoulder_k
    (x0, z0), (x1, z1) = ly["from"], ly["to"]
    x0, x1 = x0 * k, x1 * k
    w = ly.get("w", 0.075)
    n = 28
    pts, nors = [], []
    over_shoulder = ly.get("over_shoulder", True)
    for i in range(n):
        t = i / (n - 1)
        x = x0 + (x1 - x0) * t
        z = z0 + (z1 - z0) * t
        h, nn, _ = core.ray_any(ctx.outer, (x, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        pts.append(h + nn * (S["strap_off"] * H + 0.004))
        nors.append(nn)
    if over_shoulder:  # continue over the shoulder top to the back (the end goes out of sight)
        top = pts[0]
        for k2, dy in enumerate((0.12, 0.26, 0.40)):
            h, nn, _ = core.ray_any(ctx.outer, (top.x, top.y + dy, 2.0), (0, 0, -1))
            if h is not None:
                pts.insert(0, h + nn * (S["strap_off"] * H + 0.004))
                nors.insert(0, nn)
    o = core.ribbon_mesh(name, pts, w, normals=nors)
    core.solidify(o, max(S["strap_min"] * H, 0.024), offset=1.0)
    core.bevel(o, 0.006, 2)
    m = core.principled(ctx, name, ly["color"], rough=0.5, sheen=0.15, coat=0.1)
    core.finish(o, m, sub=1)
    ctx.add(o, _group(ly), ctx.outer[-1], kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    ctx.L[ly.get("id", name)] = pts
    if ly.get("detail"):
        ctx.details[ly["detail"]] = ly.get("min_px", 3000)
    return o


def frogging(ctx, ly, name):
    """Cord frogging (brandenburgs): `n` horizontal cords across the chest, each ending in a small loop (a torus) and a
    knob; every point cast onto the costume along the normal; each piece registers the surface it was cast onto."""
    k = ctx.shoulder_k
    m = core.principled(ctx, name, ly["color"], rough=0.3, metal=0.5)
    w = ly.get("w", 0.22) * k
    t = ly.get("t", 0.025) * H
    for i, z in enumerate(ly.get("z", (-0.86, -0.98, -1.10))):
        ww = w * (1.0 - 0.06 * i)
        pts, hosts = [], []
        for j in range(9):
            x = -ww + 2 * ww * j / 8
            h, nn, ob = core.ray_any(ctx.outer, (x, -2.0, z + 0.008 * math.cos(math.pi * j / 8)), (0, 1, 0))
            if h is not None:
                pts.append(h + nn * (t * 0.5 + 0.002))
                hosts.append(ob)
        if len(pts) < 3:
            continue
        c = core.curve("%s_cord%d" % (name, i), pts, [1.0] * len(pts), t / 2, m)
        ctx.add(c, "metal", ctx.objs["torso"], kind="surface")
        for end in (pts[0], pts[-1]):
            h, nn, ob = core.ray_any(ctx.outer, (end.x, -2.0, end.z), (0, 1, 0))
            if h is None:
                continue
            lp = core.torus("%s_loop%d" % (name, i), h + nn * (t * 0.42), 0.03, t * 0.42, m, nrm=nn, seg=24, rseg=8)
            ctx.add(lp, "metal", ob, kind="surface")
            bt = core.uvsphere("%s_knot%d" % (name, i), h + nn * t * 0.5, (t * 0.9, t * 0.9, t * 0.6), m, 16, 8)
            core.align_z(bt, nn)
            ctx.add(bt, "metal", ob, kind="surface")


def placket(ctx, ly, name):
    """A closure band down the front (shrinkwrapped, solidified, bevelled)."""
    w = ly.get("w", 0.06)
    top, bottom = ly.get("top", -0.70), ly.get("bottom", -2.0)
    bm = bmesh.new()
    vs = []
    n = 16
    for i in range(n + 1):
        z = top + (bottom - top) * i / n
        vs.append((bm.verts.new((-w + ly.get("x", 0.0), -1.2, z)), bm.verts.new((w + ly.get("x", 0.0), -1.2, z))))
    for i in range(n):
        bm.faces.new((vs[i][0], vs[i][1], vs[i + 1][1], vs[i + 1][0]))
    o = core.mesh_obj(name, bm)
    core.shrinkwrap(o, ctx.objs["torso"], S["layer_gap"] * H * 0.5, method="PROJECT", project_y=True)
    core.solidify(o, 0.02, offset=1.0)
    core.bevel(o, 0.006, 2)
    core.finish(o, _mat(ctx, ly, name))
    ctx.add(o, "costume", ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    return o
