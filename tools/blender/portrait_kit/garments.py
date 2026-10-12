"""Costume layers (§7.5 steps 6–7, §7.3 "Костюм"): shells built from the torso rings (resampled finely, shrinkwrapped
just outside what they cover, a front opening cut, solidified >= 0.02 H, Subsurf for rounded edges), collars with
real thickness, belts, front panels (an apron bib), straps that follow the costume and end under something, and
the cord work (frogging) cast onto the chest. Layers sit 0.012 H apart (STYLE["layer_gap"]).

A character's costume is data (chars.py "costume"): {"base": {...}, "layers": [...]} — this module has no branch per
character. Kinds: vest, collar, belt, bib (also an apron or a stole), strap, frogging, placket; and (P2) fur (a
metaball sheet collar with soft clumps, never a torus), buttons, lapels, quilt (a gambeson's stitched channels),
pauldrons (layered plates cast onto the flat shoulder tops), cloak (a cape shell over the shoulders and arms, open
in front), cape_collar (a tall stand collar framing the head from behind), jabot (tiers of pleated lace),
neckerchief, clasp, pocket. Every layer registers the object it lies on (the contact test) and adds itself to
ctx.outer (what later layers and props are cast onto).
"""
import math

import bmesh
from mathutils import Matrix, Vector

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
              "placket": placket, "fur": fur, "buttons": buttons, "lapels": lapels, "quilt": quilt,
              "pauldrons": pauldrons, "cloak": cloak, "cape_collar": cape_collar, "jabot": jabot,
              "neckerchief": neckerchief, "clasp": clasp, "pocket": pocket}[ly["kind"]]
        fn(ctx, ly, "%s%d" % (ly["kind"], i))
        core.update()


def _mat(ctx, ly, name):
    if ly.get("metal"):
        return core.principled(ctx, name, ly["color"], rough=ly.get("rough", 0.3), metal=ly.get("metallic", 0.5))
    return core.fabric(ctx, name, ly["color"], rough=ly.get("rough", 0.8), sheen=ly.get("sheen", 0.3))


def _group(ly):
    """The layer's ID group: its P-A8 detail, metal, or costume:<id> (each garment its own colour, so the beard rule
    of §7.4 can test the beard against each piece it lies on)."""
    if ly.get("detail"):
        return "detail:" + ly["detail"]
    if ly.get("metal"):
        return "metal"
    return "costume:" + ly.get("id", ly["kind"])


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
    top_k, bot_k = ly.get("shade", (1.06, 0.9))
    m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], top_k), core.hex_scale(ly["color"], bot_k), z0, z1,
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
    top_ring = [v.co.copy() for v in rings[-1]]          # (before the bmesh is freed: the piping follows it)
    if gap:
        kill = [f for f in bm.faces if f.calc_center_median().y < 0 and abs(f.calc_center_median().x) < gap]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["collar"] * H, ly.get("thick", 0.03)), offset=1.0)
    core.finish(o, _mat(ctx, ly, name), sub=2)
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    if ly.get("piping"):
        # a coloured piping along the collar's top edge (Irma's orange, §7.6 "оранжевый кант"), from end to end of
        # the opening when the collar is open in front
        pts = top_ring
        order = sorted(range(len(pts)), key=lambda i: (math.atan2(pts[i].x, -pts[i].y) + 2 * math.pi) % (2 * math.pi))
        seq = [pts[i] for i in order]
        if gap:
            seq = [q for q in seq if not (q.y < 0 and abs(q.x) < gap)]
        pts2 = []
        for q in seq:
            rad = Vector((q.x, q.y - 0.07, 0.0)).normalized()
            pts2.append(q + rad * (max(S["collar"] * H, ly.get("thick", 0.03)) * 0.5) + Vector((0, 0, 0.004)))
        pc = core.curve(name + "_piping", pts2, [1.0] * len(pts2), ly.get("piping_r", 0.016),
                        core.principled(ctx, name + "_piping", ly["piping"], rough=0.45, coat=0.2), kind="POLY")
        ctx.add(pc, "costume:piping", o, kind="embed")
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
    ctx.add(o, "costume:belt", ctx.outer[-1], kind="surface")
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
    if ly.get("leather"):
        m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], 1.06), core.hex_scale(ly["color"], 0.9), bottom, top,
                          rough=0.5, coat=0.12)
    else:
        m = core.principled(ctx, name, ly["color"], rough=ly.get("rough", 0.85), sheen=ly.get("sheen", 0.25))  # flat: a white bib stays light to the hem
    core.finish(o, m, sub=1)
    core.bevel(o, S["bevel"] * H * 1.5, 2)
    ctx.add(o, _group(ly), tgt, kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", "bib")] = o
    if ly.get("detail"):
        ctx.details[ly["detail"]] = ly.get("min_px", 3000)
    core.update()
    if ly.get("straps"):
        for s in (-1, 1):
            pts = []
            for t in range(9):
                f = t / 8
                x = s * (w * 0.80 + (0.36 * k - w * 0.80) * f)
                zz = top + 0.02 + (-0.655 - top) * min(1.0, f * 1.3)
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
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    return o


# ------------------------------------------------------------------ P2 kinds
def _arm_extent(ctx, z):
    """The arms' outer half width and depth at height z (the capsules seen from the front), for shells that wrap
    over the arms (cloaks)."""
    best_x, best_y = 0.0, 0.0
    for s in (-1, 1):
        top, bot = (Vector(v) for v in ctx.objs["arm_axis%+d" % s])
        r = 0.205 * ctx.shoulder_k
        if z > top.z + r:
            continue
        f = 0.0 if z >= top.z else min(1.0, (top.z - z) / max(top.z - bot.z, 1e-6))
        c = top.lerp(bot, f)
        rr = r if z <= top.z else math.sqrt(max(0.0, r * r - (z - top.z) ** 2))
        best_x = max(best_x, abs(c.x) + rr)
        best_y = max(best_y, abs(c.y) + rr)
    return best_x, best_y


def fur(ctx, ly, name):
    """A fur collar (§7.3: a metaball sheet with clumps and an AO tone, never a torus): a sheet on the shoulders
    round the neck — out to `r` (shoulder units) over the shoulders, down to `front_z` in a soft V in front — rolled
    (thickest in the middle of the band), with broad soft clumps over it (Kort's karakul in ribbons, Hawk's fluffy
    sheepskin)."""
    torso = ctx.objs["torso"]
    k = ctx.shoulder_k
    r_out = ly.get("r", 0.56) * k
    r_in = ly.get("r_in", 0.18) * k
    front = ly.get("front_z", -0.92)
    t0 = ly.get("t", 0.09)

    def geo(h):
        r = math.hypot(h.x, h.y - 0.05)
        az = abs(math.degrees(math.atan2(h.x, -(h.y - 0.05))))
        return r, az

    gap = ly.get("open", 0.0) * k          # the front opening's half width at the bottom of the V

    def keep(h, n, d):
        r, az = geo(h)
        zmin = core.lerp_table([(0, front), (35, front + 0.08), (80, ly.get("side_z", -0.84)), (180, ly.get("back_z", -0.80))], az)
        if gap and h.y < 0.0 and abs(h.x) < gap * core.smoothstep(-0.6, front, h.z):
            return False
        return r_in * 0.85 < r < r_out and h.z > zmin and h.z < -0.45
    samples, s = core.surface_samples(torso, 4200, keep, centre=(0, 0.05, -0.9), radius=0.75)

    def thick(h, n):
        r, az = geo(h)
        rn = max(0.0, min(1.0, (r - r_in) / max(r_out - r_in, 1e-6)))
        zmin = core.lerp_table([(0, front), (35, front + 0.08), (80, ly.get("side_z", -0.84)), (180, ly.get("back_z", -0.80))], az)
        edge = core.smoothstep(0.0, 0.06, h.z - zmin)
        return t0 * (0.45 + 0.55 * math.sin(math.pi * min(1.0, 0.1 + 0.9 * rn))) * (0.5 + 0.5 * edge)
    el = core.sheet_elems(samples, s, thick, inset=0.02)
    cl = ly.get("clumps", {})
    rng = ctx.rng
    picks = [samples[i] for i in sorted(rng.sample(range(len(samples)), min(len(samples), cl.get("n", 46))))]
    for hit, nor, d in picks:
        r, az = geo(hit)
        t = thick(hit, nor)
        if t < 0.03:
            continue
        a = rng.uniform(0, 2 * math.pi)
        tang = nor.orthogonal().normalized()
        tang = (Matrix.Rotation(a, 3, nor) @ tang).normalized()
        ln = cl.get("len", 0.07) * rng.uniform(0.8, 1.2)
        p0 = hit + nor * (t * 0.85)
        el += core.clump([p0 - tang * ln * 0.5, p0 + nor * 0.01, p0 + tang * ln * 0.5], [nor, nor, nor],
                         cl.get("w", 0.035), cl.get("w", 0.035) * 0.8, cl.get("th", 0.03), n=6, lift=0.0, taper_at=0.6,
                         tip=0.6, stiff=2.6, flat=0.9)
    col = ly["color"]
    m = core.hair_mat(ctx, name, col, -1.0, -0.55, dark=ly.get("dark"), light=ly.get("light"),
                      crevice=ly.get("crevice"), rough=0.75)
    o = core.mb_mesh(ctx, "Fur" + name, el, ly.get("res", 0.012), m, smooth_iter=ly.get("smooth", 3), name=name)
    grp = "detail:" + ly["detail"] if ly.get("detail") else "costume:" + ly.get("id", "fur")
    if ly.get("detail"):
        ctx.details[ly["detail"]] = ly.get("min_px", 2500)
    ctx.add(o, grp, torso, kind="embed")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", "fur")] = o
    if ly.get("signature"):
        ctx.sig_objs.append(o)
    return o


def buttons(ctx, ly, name):
    """Buttons (§7.3: ray cast along the normal, 0.012 H off): domed discs with a rim at (x, z) points (x in shoulder
    units), each registered on the surface it was cast onto. ly["at"]: [(x, z), ...]."""
    k = ctx.shoulder_k
    r = ly.get("r", 0.03)
    m = core.principled(ctx, name, ly.get("color", "#E0AD45"), rough=0.3, metal=ly.get("metallic", 0.5))
    for i, (x, z) in enumerate(ly["at"]):
        h, nn, ob = core.ray_any(ctx.outer, (x * k, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        b = core.cylinder("%s_%d" % (name, i), h + nn * (S["attach_off"] * H * 0.5), r, 0.022, m, nrm=nn, bev=0.009)
        ctx.add(b, "metal", ob, kind="surface")
        dome = core.uvsphere("%s_dome%d" % (name, i), h + nn * 0.016, (r * 0.62, r * 0.62, r * 0.35), m, 16, 8)
        core.align_z(dome, nn)
        ctx.add(dome, "metal", b, kind="embed")
        ctx.L["%s_%d" % (ly.get("id", name), i)] = (h + nn * 0.02, nn)


def lapels(ctx, ly, name):
    """Lapels (revers): two flat panels on the coat's front from the neck down to `bottom` — each a long triangle
    with a notch at the outer top corner — projected onto the costume along Y, 0.025 H thick with a bevel; in the
    coat's colour or an accent (Vance's violet)."""
    k = ctx.shoulder_k
    pts_l = ly.get("shape", [(0.10, -0.64), (0.26, -0.70), (0.36, -0.78), (0.30, -0.84), (0.22, -0.98), (0.06, -1.16)])
    tgt = ctx.objs.get(ly.get("on", "torso")) or ctx.objs["torso"]
    m = core.fabric(ctx, name, ly["color"], rough=ly.get("rough", 0.8), sheen=ly.get("sheen", 0.3))
    for s_ in (-1, 1):
        bm = bmesh.new()
        poly = [(s_ * x * k, z) for x, z in pts_l]
        cx = sum(p[0] for p in poly) / len(poly)
        cz = sum(p[1] for p in poly) / len(poly)
        n = len(poly)
        ctr = bm.verts.new((cx, -1.2, cz))
        rings = [[bm.verts.new((cx + (x - cx) * f, -1.2, cz + (z - cz) * f)) for x, z in poly]
                 for f in (0.25, 0.5, 0.75, 1.0)]
        for i in range(n):
            bm.faces.new((ctr, rings[0][i], rings[0][(i + 1) % n]))
        for j in range(3):
            for i in range(n):
                bm.faces.new((rings[j][i], rings[j + 1][i], rings[j + 1][(i + 1) % n], rings[j][(i + 1) % n]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        o = core.mesh_obj("%s%+d" % (name, s_), bm)
        core.shrinkwrap(o, tgt, S["layer_gap"] * H * 0.6, method="PROJECT", project_y=True)
        core.solidify(o, max(S["collar"] * H, 0.026), offset=1.0)
        core.bevel(o, S["bevel"] * H, 2)
        core.finish(o, m, sub=1)
        ctx.add(o, _group(ly), tgt, kind="surface")
        ctx.outer.append(o)


def quilt(ctx, ly, name):
    """A gambeson's quilting (Frey): stitched channels on a shell — horizontal seams every `dz` and short vertical
    seams between them every `dx` (box quilting), sunk curves of a darker tone cast onto the shell."""
    tgt = ctx.objs[ly.get("on", "torso")]
    k = ctx.shoulder_k
    m = core.principled(ctx, name, ly["color"], rough=0.8)
    z0, z1 = ly.get("z", (-1.45, -0.74))
    dz, dx = ly.get("dz", 0.10), ly.get("dx", 0.13) * k
    xw = ly.get("w", 0.62) * k
    if ly.get("style", "channels") == "channels":
        # vertical channels (a gambeson's quilting) and a horizontal seam every `dz` * 3
        x = -xw
        col = 0
        while x <= xw + 1e-6:
            pts = []
            for i in range(20):
                zz = z1 - (z1 - z0) * i / 19
                h, nn = core.ray(tgt, (x, -2.0, zz), (0, 1, 0))
                if h is not None:
                    pts.append(h + nn * 0.002)
            if len(pts) > 3:
                c = core.curve("%s_v%d" % (name, col), pts, [1.0] * len(pts), ly.get("r", 0.008), m)
                ctx.add(c, "costume:" + ly.get("id", "quilt"), tgt, kind="surface")
            x += dx
            col += 1
        for row, zz in enumerate(ly.get("seams", ())):
            pts = []
            for i in range(25):
                x = -xw + 2 * xw * i / 24
                h, nn = core.ray(tgt, (x, -2.0, zz), (0, 1, 0))
                if h is not None:
                    pts.append(h + nn * 0.002)
            if len(pts) > 3:
                c = core.curve("%s_h%d" % (name, row), pts, [1.0] * len(pts), 0.009, m)
                ctx.add(c, "costume:" + ly.get("id", "quilt"), tgt, kind="surface")
        return
    z = z1
    row = 0
    while z > z0:
        pts = []
        for i in range(25):
            x = -xw + 2 * xw * i / 24
            h, nn = core.ray(tgt, (x, -2.0, z), (0, 1, 0))
            if h is not None:
                pts.append(h + nn * 0.002)
        if len(pts) > 3:
            c = core.curve("%s_h%d" % (name, row), pts, [1.0] * len(pts), 0.007, m)
            ctx.add(c, "costume:" + ly.get("id", "quilt"), tgt, kind="surface")
        x = -xw + (dx * 0.5 if row % 2 else 0.0)
        while x < xw:
            a, _ = core.ray(tgt, (x, -2.0, z - 0.01), (0, 1, 0))
            b, nb = core.ray(tgt, (x, -2.0, z - dz + 0.01), (0, 1, 0))
            if a is not None and b is not None:
                c = core.curve("%s_v%d" % (name, row), [a + nb * 0.002, b + nb * 0.002], [1.0, 1.0], 0.006, m, order=2)
                ctx.add(c, "costume:" + ly.get("id", "quilt"), tgt, kind="surface")
            x += dx
        z -= dz
        row += 1


def pauldrons(ctx, ly, name):
    """Pauldrons (§7.3: cast onto the flat shoulder tops): `n` layered plates per shoulder (Frey: 3), each a curved
    band of a shell round the deltoid (the arm capsule's top), the top plate outermost, 0.025 H thick with bevels;
    polished steel, an enamel stripe along each plate's lower edge, a leather strap under them."""
    k = ctx.shoulder_k
    steel = core.principled(ctx, name, ly.get("color", "#C8D0DA"), rough=0.3, metal=0.55, coat=0.2)
    stripe = core.principled(ctx, name + "_stripe", ly.get("stripe", "#3B7A52"), rough=0.35, coat=0.3)
    n = ly.get("n", 3)
    for s in (-1, 1):
        top, bot = (Vector(v) for v in ctx.objs["arm_axis%+d" % s])
        arm = ctx.objs["arm%+d" % s]
        r_arm = 0.205 * k
        c = top + Vector((s * 0.02, 0.0, -0.02))
        out = Vector((s, 0, 0))
        fwd = Vector((0, -1, 0))
        up = Vector((0, 0, 1))
        bands = ly.get("bands", [(96, 44), (56, 10), (22, -24)])[:n]
        parent = arm
        # bottom-up: the lowest lame rests on the arm, each plate above overlaps (and rests on) the one under it
        for i, (e1, e0) in reversed(list(enumerate(bands))):
            R = r_arm + 0.026 + 0.014 * (n - 1 - i)
            a_max = math.radians(ly.get("spread", 95) - 8 * i)
            bm = bmesh.new()
            nu, ne = 28, 10
            grid = []
            for j in range(ne + 1):
                e = math.radians(e0 + (e1 - e0) * j / ne)
                row = []
                for ii in range(nu + 1):
                    a = -a_max + 2 * a_max * ii / nu
                    d = (out * math.cos(a) + fwd * math.sin(a)) * math.cos(e) + up * math.sin(e)
                    row.append(bm.verts.new(c + d * R))
                grid.append(row)
            for j in range(ne):
                for ii in range(nu):
                    bm.faces.new((grid[j][ii], grid[j][ii + 1], grid[j + 1][ii + 1], grid[j + 1][ii]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            o = core.mesh_obj("%s%+d_%d" % (name, s, i), bm)
            core.solidify(o, max(S["layer_min"] * H, 0.028), offset=0.0)
            core.bevel(o, 0.008, 3)
            core.finish(o, steel, sub=1)
            ctx.add(o, "detail:" + ly.get("detail", "pauldrons"), parent, kind="surface")
            ctx.sig_objs.append(o)
            # the enamel stripe along the lower edge
            e = math.radians(e0 + (e1 - e0) * 0.22)
            pts = []
            for ii in range(15):
                a = -a_max * 0.92 + 2 * a_max * 0.92 * ii / 14
                d = (out * math.cos(a) + fwd * math.sin(a)) * math.cos(e) + up * math.sin(e)
                pts.append(c + d * (R + 0.016))
            st = core.curve("%s_stripe%+d_%d" % (name, s, i), pts, [1.0] * len(pts), ly.get("stripe_r", 0.012), stripe)
            st.scale = (1, 1, 1)
            ctx.add(st, "detail:" + ly.get("detail", "pauldrons"), o, kind="embed")
            ctx.sig_objs.append(st)          # part of the plate (and of its colour in P-A9's signature group)
            parent = o
    ctx.details[ly.get("detail", "pauldrons")] = ly.get("min_px", 10000)


def cloak(ctx, ly, name):
    """A cloak (Vik, Rai): a shell round the shoulders, arms and back from the neck base down out of the frame, its
    rings the hull of the torso and the arms plus a gap, open in front (the opening widens downward), 0.03 H thick,
    bevelled, Subsurf 2."""
    spec = ctx.torso_spec
    z0, z1 = ly.get("z0", -1.9), ly.get("z1", -0.64)
    nz, seg = 20, 72
    gap = ly.get("gap", 0.025)
    bm = bmesh.new()
    rings = []
    for i in range(nz):
        z = z0 + (z1 - z0) * i / (nz - 1)
        hx, hy, n, yo = core.ring_at(spec, z)
        ax, ay = _arm_extent(ctx, z)
        top = core.smoothstep(z1 - 0.10, z1, z)
        hx2 = max(hx, ax) + gap + ly.get("flare", 0.08) * core.smoothstep(z1, z0, z)
        hy2 = max(hy, ay + 0.05) + gap
        hx2 = hx2 * (1 - top) + (hx + gap) * top
        hy2 = hy2 * (1 - top) + (hy + gap) * top
        rings.append(core.superellipse_ring(bm, z, hx2, hy2, ly.get("n", 2.6), yo + ly.get("dy", 0.02), seg=seg))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    op = ly.get("open", [(-1.9, 0.30), (-1.2, 0.20), (-0.85, 0.12), (-0.66, 0.10)])
    kill = [f for f in bm.faces if f.calc_center_median().y < 0
            and abs(f.calc_center_median().x) < core.lerp_table(op, f.calc_center_median().z) * ctx.shoulder_k]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["layer_min"] * H, ly.get("thick", 0.03)), offset=1.0)
    sh_top, sh_bot = ly.get("shade", (1.06, 0.88))     # Rai: a darker top, so the key-lit shoulders stay deep blue
    m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], sh_top), core.hex_scale(ly["color"], sh_bot), z0, z1,
                      rough=ly.get("rough", 0.85), sheen=ly.get("sheen", 0.35), spec=ly.get("spec", 0.5))
    core.finish(o, m, sub=2)
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    return o


def cape_collar(ctx, ly, name):
    """A tall stand collar framing the head from behind (Rai's signature, §7.6 "стоячий воротник-пелерина рамкой у
    головы"): a flaring sector of a cone round the neck, open at the front, rising from the shoulders to `top_z`,
    the top edge rolled with a silver piping; its own lining colour inside."""
    k = ctx.shoulder_k
    zb, zt = ly.get("z0", -0.70), ly.get("top_z", -0.05)
    rb, rt = ly.get("r0", 0.30) * k, ly.get("r1", 0.52)
    a_open = math.radians(ly.get("open", 62))
    bm = bmesh.new()
    nu, nv = 48, 12
    grid = []
    for j in range(nv + 1):
        f = j / nv
        z = zb + (zt - zb) * f
        r = rb + (rt - rb) * (f ** 1.4)
        row = []
        for i in range(nu + 1):
            a = a_open + (2 * math.pi - 2 * a_open) * i / nu      # from the near front round the back to the far front
            # the front ends dip down (the collar's corners fall toward the chest)
            dz = -0.10 * (1 - math.sin((a - a_open) / (2 * math.pi - 2 * a_open) * math.pi)) * f
            row.append(bm.verts.new((r * -math.sin(a) * 1.05, 0.08 + r * -math.cos(a) * 0.95, z + dz)))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["collar"] * H, 0.03), offset=0.0)
    core.bevel(o, 0.008, 2)
    m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], 1.1), core.hex_scale(ly["color"], 0.92), zb, zt,
                      rough=0.75, sheen=0.4)
    core.finish(o, m, sub=2)
    ctx.add(o, "detail:" + ly.get("detail", "cape_collar"), ctx.objs["torso"], kind="embed")
    ctx.details[ly.get("detail", "cape_collar")] = ly.get("min_px", 4000)
    ctx.sig_objs.append(o)
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    # the piping along the top edge
    pts = [v.co.copy() for v in o.data.vertices][-(nu + 1):]
    pip = core.curve(name + "_piping", pts, [1.0] * len(pts), ly.get("piping_r", 0.016),
                     core.principled(ctx, name + "_pip", ly.get("piping", "#C8CCD4"), rough=0.3, metal=0.5))
    ctx.add(pip, "metal", o, kind="embed")
    return o


def jabot(ctx, ly, name):
    """A lace jabot (Vance, §7.6 "кружевное жабо"): `tiers` pleated half-fans hanging from the throat down the
    chest, each a little wider and lower, the pleats a wave of the edge toward the camera; white, Subsurf 2."""
    torso = ctx.objs["torso"]
    m = core.principled(ctx, name, ly.get("color", "#F4F2F6"), rough=0.7, sheen=0.4)
    z_top = ly.get("top", -0.66)
    hosts = []
    for t in range(ly.get("tiers", 3)):
        zc = z_top - 0.10 * t
        R = ly.get("r", 0.13) * (1 + 0.18 * t)
        h, nn, ob = core.ray_any(ctx.outer, (0.0, -2.0, zc - R * 0.5), (0, 1, 0))
        if h is None:
            continue
        y0 = h.y - 0.02 - 0.012 * t
        bm = bmesh.new()
        nr, na = 6, 36
        grid = []
        for i in range(nr + 1):
            r = R * (0.12 + 0.88 * i / nr)
            row = []
            for j in range(na + 1):
                a = math.radians(-80 + 160 * j / na)        # a fan hanging down (0 = straight down)
                wave = 0.035 * (i / nr) ** 1.5 * math.sin(j * math.pi * 7 / na * 2)
                row.append(bm.verts.new((r * math.sin(a), y0 - wave - 0.01 * (i / nr), zc - r * math.cos(a) * 0.9)))
            grid.append(row)
        for i in range(nr):
            for j in range(na):
                bm.faces.new((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        o = core.mesh_obj("%s_%d" % (name, t), bm)
        core.solidify(o, 0.012, offset=0.0)
        core.finish(o, m, sub=2)
        ctx.add(o, "costume:" + ly.get("id", "jabot"), ob, kind="embed")
        hosts.append(o)
    ctx.outer += hosts
    ctx.objs[ly.get("id", "jabot")] = hosts[0] if hosts else torso
    ctx.L["jabot_top"] = Vector((0.0, (hosts[0].data.vertices[0].co.y if hosts else -0.4) - 0.03, z_top - 0.04))


def neckerchief(ctx, ly, name):
    """A neckerchief (Seir, §7.6 "белый шейный платок"): a soft roll round the neck base, a knot under the chin and
    two short tails down the chest — metaballs, cloth-white, smoothed."""
    torso = ctx.objs["torso"]
    neck = ctx.objs["neck"]
    el = []
    zc = ly.get("z", -0.60)
    for i in range(28):
        a = 2 * math.pi * i / 28
        d = Vector((math.sin(a), -math.cos(a), 0))
        h, nn = core.ray(neck, Vector((0, 0.07, zc)) + d * 2, -d)
        if h is None:
            continue
        el.append(dict(co=h + nn * 0.02, half=(0.05, 0.035, 0.045), stiff=2.2, rot=core.frame_quat(Vector((0, 0, 1)), nn)))
    h, nn, ob = core.ray_any([neck, torso], (0.0, -2.0, zc - 0.05), (0, 1, 0))
    knot = h + nn * 0.05 if h is not None else Vector((0, -0.3, zc - 0.05))
    el.append(dict(co=knot, half=(0.06, 0.05, 0.05), stiff=2.4))
    for s_ in (-1, 1):
        prev = knot
        for k2 in range(1, 7):
            t = k2 / 6
            p = knot + Vector((s_ * 0.05 * t, -0.03 * t, -0.18 * t))
            hh, nn2 = core.ray(torso, (p.x, -2.0, p.z), (0, 1, 0))
            if hh is not None:
                p = Vector((p.x, min(p.y, hh.y - 0.03), p.z))
            el.append(dict(co=p, half=(0.045 - 0.01 * t, 0.018, 0.035), stiff=2.2,
                           rot=core.frame_quat(p - prev, Vector((0, -1, 0)))))
            prev = p
    m = core.fabric(ctx, name, ly.get("color", "#F2F2F2"), z0=-1.0, z1=-0.5, rough=0.8, sheen=0.3)
    o = core.mb_mesh(ctx, "Neck" + name, el, 0.008, m, smooth_iter=2, name=name)
    ctx.add(o, "costume:" + ly.get("id", "neckerchief"), neck, kind="embed")
    ctx.outer.append(o)
    return o


def clasp(ctx, ly, name):
    """A cloak / coat clasp (Kort's bronze): two oval plates either side of the front opening joined by a short bar,
    cast onto the costume."""
    k = ctx.shoulder_k
    m = core.principled(ctx, name, ly.get("color", "#B0803A"), rough=0.32, metal=0.55)
    z = ly.get("z", -0.72)
    pos, plates = [], []
    for s_ in (-1, 1):
        h, nn, ob = core.ray_any(ctx.outer, (s_ * ly.get("x", 0.07) * k, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        o = core.uvsphere("%s%+d" % (name, s_), h + nn * 0.012, (0.05, 0.05, 0.022), m, 24, 12)
        core.align_z(o, nn)
        ctx.add(o, "metal", ob, kind="surface")
        pos.append(h + nn * 0.026)
        plates.append(o)
    if len(pos) == 2:
        mid = (pos[0] + pos[1]) / 2
        h, nn, ob = core.ray_any(ctx.outer, (mid.x, -2.0, mid.z - 0.01), (0, 1, 0))
        if h is not None:
            mid = Vector((mid.x, min(mid.y, h.y - 0.016), mid.z - 0.01))
        bar = core.curve(name + "_bar", [pos[0], mid, pos[1]], [1, 1, 1], 0.012, m, order=3)
        ctx.add(bar, "metal", plates[0], kind="embed")      # it runs from plate to plate


def pocket(ctx, ly, name):
    """A patch pocket (Olm's apron: the wrench's): a panel projected onto its host (ly["on"]), stitched edge, its top
    a little open."""
    tgt = ctx.objs[ly.get("on", "torso")]
    k = ctx.shoulder_k
    x, z = ly["at"]
    w, hgt = ly.get("w", 0.12) * k, ly.get("h", 0.14)
    bm = bmesh.new()
    vs = []
    for j in range(5):
        zz = z - hgt / 2 + hgt * j / 4
        vs.append([bm.verts.new((x * k - w + 2 * w * i / 6, -1.5, zz)) for i in range(7)])
    for j in range(4):
        for i in range(6):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    o = core.mesh_obj(name, bm)
    core.shrinkwrap(o, tgt, 0.006, method="PROJECT", project_y=True)
    core.solidify(o, 0.022, offset=1.0)
    core.bevel(o, 0.006, 2)
    m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], 1.0), core.hex_scale(ly["color"], 0.86), z - hgt / 2,
                      z + hgt / 2, rough=0.55, coat=0.1)
    core.finish(o, m, sub=1)
    ctx.add(o, "costume:" + ly.get("id", "pocket"), tgt, kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    ctx.L[ly.get("id", name)] = (Vector((x * k, 0, z + hgt / 2)), w)
    return o
