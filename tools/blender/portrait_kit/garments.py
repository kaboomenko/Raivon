"""Costume layers (§7.5 steps 6–7, §7.3 "Костюм"): shells built from the torso rings (resampled finely, shrinkwrapped
just outside what they cover, a front opening cut, solidified >= 0.02 H, Subsurf for rounded edges), collars with
real thickness, belts, front panels (an apron bib), straps that follow the costume and end under something, and
the cord work (frogging) cast onto the chest. Layers sit 0.012 H apart (STYLE["layer_gap"]).

A character's costume is data (chars.py "costume"): {"base": {...}, "layers": [...]} — this module has no branch per
character. Kinds: vest, collar, belt, bib (also an apron or a stole), strap, frogging, placket; and (P2) fur (a
metaball sheet collar with soft clumps, never a torus), buttons, lapels, quilt (a gambeson's stitched channels),
pauldrons (layered plates cast onto the flat shoulder tops), cloak (a cape shell over the shoulders and arms, open
in front), cape_collar (a tall stand collar framing the head from behind), jabot (tiers of pleated lace),
neckerchief, clasp, pocket, piping (a cord along a front path). Every layer registers the object it lies on (the
contact test) and adds itself to ctx.outer (what later layers and props are cast onto).
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
              "neckerchief": neckerchief, "clasp": clasp, "pocket": pocket, "piping": piping}.get(ly["kind"]) \
            or _P3_KINDS[ly["kind"]]
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
    if ly.get("camo"):
        m = core.camo_mat(ctx, name, ly["color"], ly["camo"], scale=ly.get("camo_scale", 5.0), z0=z0, z1=z1)
    elif ly.get("plate"):
        # §7.7 E4 painted plates (roughness 0.45, metallic 0.25) or polished steel (`metal`)
        m = core.principled(ctx, name, ly["color"], rough=ly.get("rough", 0.45), metal=ly.get("metallic", 0.25),
                            coat=ly.get("coat", 0.3))
    else:
        m = core.grad_mat(ctx, name, core.hex_scale(ly["color"], top_k), core.hex_scale(ly["color"], bot_k), z0, z1,
                          rough=ly.get("rough", 0.85), sheen=ly.get("sheen", 0.35))
    # a smooth plate needs one subdivision level, not two (83k -> 21k triangles: Bram's E4 was 546k, over the 500k
    # budget of §7.11)
    core.finish(o, m, sub=1 if ly.get("plate") else 2)
    ctx.add(o, _group(ly), ctx.objs["torso"], kind="surface")
    ctx.outer.append(o)
    ctx.objs[ly.get("id", name)] = o
    return o



def _nearest_host(ctx, pts):
    """The costume layer (torso or one of ctx.outer) nearest to some points: the contact host of a part that stands
    on whatever is under it."""
    best, bd = ctx.objs["torso"], 1e9
    core.update()
    for ob in [ctx.objs["torso"]] + list(ctx.outer):
        try:
            tree = core.bvh_of(ob)
        except Exception:
            continue
        inv = ob.matrix_world.inverted()
        for p in pts:
            loc, _, _, dist = tree.find_nearest(inv @ p)
            if loc is not None and dist < bd:
                bd, best = dist, ob
    return best

def collar(ctx, ly, name):
    """A stand collar around the neck base: a short tube with real thickness and a rounded top edge (§7.3: no flat
    triangle). Height in H; 'gap' leaves a front gap (a V). By default each ring follows the torso at its height (low
    on the shoulder slope that makes a funnel); 'stand' keeps the top ring's section all the way down — an upright
    band that rises out of the costume (Rai: the funnel lay on the shoulder slope and read as a flat plate at the neck,
    P2 review)."""
    spec = ctx.torso_spec
    zb = ly.get("z", -0.66)
    hgt = ly.get("h", 0.06) * H
    out = ly.get("out", 0.02)
    seg = 64
    bm = bmesh.new()
    rings = []
    for k in range(5):
        z = zb + hgt * k / 4
        hx, hy, n, yo = core.ring_at(spec, min(zb + hgt if ly.get("stand") else z, -0.40))
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
    base_ring = [v.co.copy() for v in rings[0] if v.is_valid]
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["collar"] * H, ly.get("thick", 0.03)), offset=1.0)
    core.finish(o, _mat(ctx, ly, name), sub=2)
    # on the layer it stands on: an E4 collar on the breastplate, not the torso 0.015 H under it (the contact check)
    ctx.add(o, _group(ly), _nearest_host(ctx, base_ring[::4]) if out >= 0.02 else ctx.objs["torso"], kind="surface")
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
    # on the shell it wraps (a vest / a plate) or the torso — not a strap or pocket added just before it
    under = [ob for ob in ctx.outer if ob.name.startswith(("vest", "cloak", "bib"))]
    ctx.add(o, "costume:belt", under[-1] if under else ctx.objs["torso"], kind="surface")
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
    rnd = ly.get("round", 0.0)       # rounded top corners (radius): square ones folded into flat triangles where
    for j in range(nz + 1):          # they ran past the torso's slope (Rai's stole, P2 review)
        z = bottom + (top - bottom) * j / nz
        ww = w * (1.0 + 0.25 * (1 - j / nz))           # a little wider toward the waist
        if rnd and z > top - rnd:
            ww -= rnd * (1.0 - math.sqrt(max(0.0, 1.0 - ((z - (top - rnd)) / rnd) ** 2)))
        row = [bm.verts.new((-ww + 2 * ww * i / nx, -1.2, z)) for i in range(nx + 1)]
        grid.append(row)
    for j in range(nz):
        for i in range(nx):
            bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
    o = core.mesh_obj(name, bm)
    tgt = ctx.outer[-1] if ly.get("over_last") else ctx.objs["torso"]
    core.shrinkwrap(o, tgt, ly.get("gap", S["layer_gap"]) * H, method="PROJECT", project_y=True)
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
    hosts = []
    for i in range(n):
        t = i / (n - 1)
        x = x0 + (x1 - x0) * t
        z = z0 + (z1 - z0) * t
        h, nn, ob = core.ray_any(ctx.outer, (x, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        pts.append(h + nn * (S["strap_off"] * H + 0.004))
        nors.append(nn)
        hosts.append(ob)
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
    # on the surface most of it was cast onto (the layer added last is not always under it: a pocket, another strap)
    host = max(set(hosts), key=hosts.count) if hosts else ctx.outer[-1]
    ctx.add(o, _group(ly), host, kind="surface")
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
        p0 = hit + nor * (t * cl.get("sink", 0.85))
        # curl > 0: a C-shaped ribbon (the middle pushed sideways), lying flat on the sheet — karakul in ribbons, not
        # round lumps (P2 review: "chocolate mousse")
        bend = Vector()
        if cl.get("curl"):
            bend = nor.cross(tang).normalized() * ln * cl["curl"] * (1 if rng.random() < 0.5 else -1)
        el += core.clump([p0 - tang * ln * 0.5, p0 + nor * cl.get("rise", 0.01) + bend, p0 + tang * ln * 0.5],
                         [nor, nor, nor], cl.get("w", 0.035), cl.get("w", 0.035) * 0.8, cl.get("th", 0.03),
                         n=cl.get("balls", 6), lift=0.0, taper_at=0.6, tip=cl.get("tip", 0.6), stiff=2.6, flat=0.9)
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


def piping(ctx, ly, name):
    """A piped edge (Irma's riding jacket: the orange edge of its closure, §7.6 accent): a round cord along a path of
    front points (x in shoulder units, z), cast onto the costume along the view axis and lifted off it by its own
    radius — a costume part with a body, not a painted line."""
    k = ctx.shoulder_k
    r = ly.get("r", 0.012)
    pts, hosts = [], []
    path = core.catmull([Vector((x * k, 0.0, z)) for x, z in ly["path"]], ly.get("n", 28))
    for q in path:
        h, nn, ob = core.ray_any(ctx.outer, (q.x, -2.0, q.z), (0, 1, 0))
        if h is not None:
            pts.append(h + nn * (r * 0.6))
            hosts.append(ob)
    if len(pts) < 3:
        return None
    c = core.curve(name, pts, [1.0] * len(pts), r, core.principled(ctx, name, ly["color"], rough=0.45, coat=0.2))
    ctx.add(c, _group(ly), max(set(hosts), key=hosts.count), kind="surface")     # on what it was cast onto
    return c


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
    steel = _metal(ctx, name, ly.get("color", "#C8D0DA"), ly)
    em = ly.get("stripe_emit", 0.0)
    stripe = core.principled(ctx, name + "_stripe", ly.get("stripe", "#3B7A52"), rough=0.35, coat=0.3,
                             emit=ly.get("stripe", "#3B7A52") if em else None, es=em)
    n = ly.get("n", 3)
    # `grow`: the plates' radius over the arm (H) — heavier armour stands further off the deltoid; `lift`: the dome's
    # centre raised (H), so the top plate rises over the shoulder line; `sides`: (-1,) the near arm only (an arm plate)
    for s in ly.get("sides", (-1, 1)):
        top, bot = (Vector(v) for v in ctx.objs["arm_axis%+d" % s])
        arm = ctx.objs["arm%+d" % s]
        r_arm = 0.205 * k + ly.get("grow", 0.0)
        c = top + Vector((s * 0.02, 0.0, -0.02 + ly.get("lift", 0.0)))
        out = Vector((s, 0, 0))
        fwd = Vector((0, -1, 0))
        up = Vector((0, 0, 1))
        bands = ly.get("bands", [(96, 44), (56, 10), (22, -24)])[:n]
        parent = arm
        grow = ly.get("grow", 0.0) + ly.get("lift", 0.0)
        if grow > 0.004:
            # plates standing off the arm (grow / lift) rest on a padded leather cap filling the gap under them (the
            # contact check: the lowest plate floated 0.05 H off the deltoid)
            r_in = 0.205 * k + 0.004
            r_out = r_arm + 0.026 + 0.014 * (n - 1) - 0.004
            e_lo, e_hi = min(b[1] for b in bands) + 6, max(b[0] for b in bands) - 4
            a_pad = math.radians(ly.get("spread", 95) - 8 * (n - 1) - 6)
            c0 = top + Vector((s * 0.02, 0.0, -0.02))
            bm = bmesh.new()
            nu, ne = 20, 8
            grid = []
            for j in range(ne + 1):
                e = math.radians(e_lo + (e_hi - e_lo) * j / ne)
                row = []
                for ii in range(nu + 1):
                    a = -a_pad + 2 * a_pad * ii / nu
                    d = (out * math.cos(a) + fwd * math.sin(a)) * math.cos(e) + up * math.sin(e)
                    row.append(bm.verts.new(c0.lerp(c, 0.5) + d * (r_in + r_out) * 0.5))
                grid.append(row)
            for j in range(ne):
                for ii in range(nu):
                    bm.faces.new((grid[j][ii], grid[j][ii + 1], grid[j + 1][ii + 1], grid[j + 1][ii]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
            pad = core.mesh_obj("%s%+d_pad" % (name, s), bm)
            core.solidify(pad, (r_out - r_in) + (c - c0).length, offset=0.0)
            core.finish(pad, core.principled(ctx, name + "_pad", ly.get("pad", "#3A4150"), rough=0.6, coat=0.1), sub=1)
            ctx.add(pad, "detail:" + ly.get("detail", "pauldrons"), arm, kind="embed")    # sunk into the deltoid
            parent = pad
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
    rings the hull of the torso and the arms plus a gap, open in front (`open`: the half width per height; each ring
    an arc from one edge of the opening round the back to the other), 0.03 H thick, bevelled, Subsurf 2."""
    spec = ctx.torso_spec
    z0, z1 = ly.get("z0", -1.9), ly.get("z1", -0.64)
    nz, seg = 20, 72
    gap = ly.get("gap", 0.025)
    op = ly.get("open", [(-1.9, 0.30), (-1.2, 0.20), (-0.85, 0.12), (-0.66, 0.10)])
    # the arcs keep the full ring's density (72 round the whole), so a wide opening costs fewer faces (P-A10)
    seg = max(24, int(round(seg * (1.0 - 0.5 * min(1.0, max(w for _, w in op) * ctx.shoulder_k / 0.62)) + 4)))
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
        # the ring as an arc round the back from one edge of the front opening to the other (half width `open` at
        # this height): the opening's edges are smooth lines (deleting the faces whose centres fell inside it left a
        # stair-step on the front edge, P2 review)
        w = core.lerp_table(op, z) * ctx.shoulder_k
        nn_ = ly.get("n", 2.6)
        r = min(1.0, (w / hx2) ** (nn_ / 2.0)) if hx2 > 1e-6 else 1.0
        a1, a2 = 2 * math.pi - math.acos(-r), 2 * math.pi - math.acos(r)
        ring = []
        for k in range(seg):
            a = a2 + (a1 + 2 * math.pi - a2) * k / (seg - 1)
            c, s_ = math.cos(a), math.sin(a)
            ring.append(bm.verts.new((hx2 * math.copysign(abs(c) ** (2 / nn_), c),
                                      hy2 * math.copysign(abs(s_) ** (2 / nn_), s_) + yo + ly.get("dy", 0.02), z)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(seg - 1):
            bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    o = core.mesh_obj(name, bm)
    core.solidify(o, max(S["layer_min"] * H, ly.get("thick", 0.03)), offset=1.0)
    sh_top, sh_bot = ly.get("shade", (1.06, 0.88))     # Rai: a darker top, so the key-lit shoulders stay deep blue
    if ly.get("camo"):
        m = core.camo_mat(ctx, name, ly["color"], ly["camo"], scale=ly.get("camo_scale", 5.0), z0=z0, z1=z1)
    else:
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
    # the host can be narrower than the pocket (Olm's E3/E4 aprons): a corner the projection misses stays at y -1.5
    # and floats as a board toward the camera, so the panel shrinks toward its centre until every corner lands
    for _ in range(8):
        if all(core.ray_any([tgt], (x * k + sx * w * 1.04, -2.0, z + sz * hgt / 2 * 1.04), (0, 1, 0))[0] is not None
               for sx in (-1, 1) for sz in (-1, 1)):
            break
        w *= 0.9
        hgt *= 0.95
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


# ================================================================== P3: the eras' costume parts (§7.6, §7.7)
def _metal(ctx, name, col, ly):
    if ly.get("painted"):
        return core.principled(ctx, name, col, rough=0.45, metal=0.25, coat=0.3)
    return core.principled(ctx, name, col, rough=ly.get("rough", 0.3), metal=ly.get("metallic", 0.55),
                           coat=ly.get("coat", 0.2))


def _frame(nrm, out):
    """A rotation with Z along `nrm` and X along `out` projected into the surface."""
    from mathutils import Matrix as M
    z = Vector(nrm).normalized()
    x = Vector(out) - z * Vector(out).dot(z)
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x).normalized()
    return M((x, y, z)).transposed().to_quaternion()


def epaulettes(ctx, ly, name):
    """Epaulettes on the flat shoulder tops (§7.3: only the flat top seats them; cast from above): per side an oval
    board `len` x `w` (kit units) lying on the shoulder, its outer end a round crescent, a fringe of `fringe` short
    cords hanging from the outer rim (E2: gold, silver, bronze; heavy: longer cords), a button at the inner end;
    `board` = a plain rectangular shoulder board with a stripe (E3)."""
    k = ctx.shoulder_k
    m = _metal(ctx, name, ly.get("color", "#E8B23A"), ly)
    base_m = core.fabric(ctx, name + "_cloth", ly.get("cloth", ly.get("color", "#E8B23A")), rough=0.7, sheen=0.3) \
        if ly.get("cloth") else m
    grp = "detail:" + ly["detail"] if ly.get("detail") else "metal"
    for s in (-1, 1):
        x = s * ly.get("x", 0.44) * k
        h, nn, ob = core.ray_any(ctx.outer, (x, ly.get("y", 0.04), 2.0), (0, 0, -1))
        if h is None:
            continue
        L = ly.get("len", 0.24) * k
        W = ly.get("w", 0.15)
        out = Vector((s, 0, 0))
        q = _frame(nn, out)
        c = h + nn * 0.018
        board = core.box(name + "_board%+d" % s, c, (L, W, 0.03), base_m, bev=min(W, L) * (0.18 if ly.get("board") else 0.45),
                         segs=4)
        board.rotation_mode = "QUATERNION"
        board.rotation_quaternion = q
        ctx.add(board, grp, ob, kind="surface")
        ax = q @ Vector((1, 0, 0))
        ay = q @ Vector((0, 1, 0))
        if ly.get("board"):
            st = core.box(name + "_stripe%+d" % s, c + nn * 0.016, (L * 0.86, W * 0.22, 0.012),
                          core.principled(ctx, name + "_stripe", ly.get("stripe", "#E8B23A"), rough=0.35, metal=0.4),
                          bev=0.004)
            st.rotation_mode = "QUATERNION"
            st.rotation_quaternion = q
            ctx.add(st, grp, board, kind="embed")
            pad = None
        else:
            # the crescent at the outer end: a thicker round pad
            pad = core.cylinder(name + "_pad%+d" % s, c + ax * L * 0.32 + nn * 0.01, W * 0.62, 0.05, m, nrm=nn,
                                verts=32, bev=0.016)
            ctx.add(pad, grp, board, kind="embed")
        nf = ly.get("fringe", 0)
        for i in range(nf):
            a = math.radians(-70 + 140 * i / max(1, nf - 1))
            p = c + ax * (L * 0.32 + W * 0.6 * math.cos(a)) + ay * (W * 0.6 * math.sin(a))
            ln = ly.get("fringe_len", 0.09)
            cord = core.curve(name + "_fringe%+d_%d" % (s, i), [p, p + Vector((0, 0, -ln * 0.5)) + ax * 0.01,
                                                                p + Vector((0, 0, -ln)) + ax * 0.012],
                              [1.0, 0.95, 0.9], ly.get("fringe_r", 0.011), m, order=3)
            ctx.add(cord, grp, pad or board, kind="embed")    # hangs from the crescent pad's rim
        btn = core.uvsphere(name + "_btn%+d" % s, c - ax * L * 0.36 + nn * 0.02, (0.022, 0.022, 0.016), m, 12, 6)
        btn.rotation_mode = "QUATERNION"
        btn.rotation_quaternion = q
        ctx.add(btn, grp, board, kind="embed")
    if ly.get("detail"):
        ctx.details[ly["detail"]] = ly.get("min_px", 400)


def strip(ctx, ly, name):
    """A flat band along a front path (x in shoulder units, z), cast onto the costume: §7.7 E4's accent strip (1.0-1.2,
    <= 1.6 emission, >= 0.04 H wide), a raivite seam, a painted stripe."""
    k = ctx.shoulder_k
    pts, nrs, hosts = [], [], []
    path = core.catmull([Vector((x * k, 0.0, z)) for x, z in ly["path"]], ly.get("n", 30))
    for q in path:
        h, nn, ob = core.ray_any(ctx.outer, (q.x, -2.0, q.z), (0, 1, 0))
        if h is not None:
            pts.append(h + nn * 0.006)
            nrs.append(nn)
            hosts.append(ob)
    if len(pts) < 3:
        return None
    o = core.ribbon_mesh(name, pts, ly.get("w", 0.045), normals=nrs)
    core.solidify(o, 0.012, offset=1.0)
    core.bevel(o, 0.004, 2)
    col = ly.get("color", "#F0A830")
    em = ly.get("emit", 0.0)
    m = core.principled(ctx, name, col, rough=0.3, coat=0.3, emit=col if em else None, es=em)
    core.finish(o, m, sub=1)
    grp = "detail:" + ly.get("detail", "glow" if em else "stripe")
    ctx.add(o, grp, max(set(hosts), key=hosts.count), kind="surface")
    ctx.details[ly.get("detail", "glow" if em else "stripe")] = ly.get("min_px", 100)
    return o


def aiguillette(ctx, ly, name):
    """An aiguillette (§7.6 Vance "аксельбант с Э2 (3 шнура ≥ 0.04 H с дальнего плеча)"): `n` cords from under the far
    epaulette down across the chest in loops of different sag to a point by the front, metal tips (aglets) on the
    longest ones; cast onto the costume."""
    k = ctx.shoulder_k
    m = _metal(ctx, name, ly.get("color", "#C8CCD4"), ly)
    grp = "detail:" + ly.get("detail", "aiguillette")
    a0 = Vector((ly.get("from", (0.42, -0.70))[0] * k, 0.0, ly.get("from", (0.42, -0.70))[1]))
    a1 = Vector((ly.get("to", (0.06, -0.92))[0] * k, 0.0, ly.get("to", (0.06, -0.92))[1]))
    r = ly.get("r", 0.022)
    for i in range(ly.get("n", 3)):
        sag = 0.06 + 0.07 * i
        pts, hosts = [], []
        for j in range(15):
            t = j / 14
            p = a0.lerp(a1, t) + Vector((0.0, 0.0, -sag * 4 * t * (1 - t)))
            h, nn, ob = core.ray_any(ctx.outer, (p.x, -2.0, p.z), (0, 1, 0))
            if h is not None:
                pts.append(h + nn * (r + 0.004 + 0.003 * i))
                hosts.append(ob)
        if len(pts) < 3:
            continue
        c = core.curve("%s_cord%d" % (name, i), pts, [1.0] * len(pts), r, m)
        ctx.add(c, grp, max(set(hosts), key=hosts.count), kind="surface")     # on the plate in E4, not the torso
        if i == ly.get("n", 3) - 1:
            tip = core.cylinder("%s_aglet" % name, pts[-1] + Vector((0, 0, -0.04)), r * 1.6, 0.08, m, nrm=(0, 0, 1),
                                verts=12, bev=0.006)
            ctx.add(tip, grp, c, kind="embed")
    ctx.details[ly.get("detail", "aiguillette")] = ly.get("min_px", 800)


def medal_bar(ctx, ly, name):
    """A ribbon bar (§7.7 E3 "одна планка наград в акцентном цвете"): `n` small coloured blocks in a row at (x, z),
    cast onto the costume; or `medals` (a star / disc on a ribbon) hanging below it."""
    k = ctx.shoulder_k
    x0, z = ly.get("at", (-0.24, -0.86))
    cols = ly.get("colors", ["#E8B23A", "#C0452A", "#3E9BF0"])
    bw, bh = ly.get("w", 0.06), ly.get("h", 0.036)
    grp = "detail:" + ly.get("detail", "medals")
    for i, col in enumerate(cols):
        x = x0 * k + (i - (len(cols) - 1) / 2) * bw * 1.04
        h, nn, ob = core.ray_any(ctx.outer, (x, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        m = core.principled(ctx, "%s_%d" % (name, i), col, rough=0.5, coat=0.2, sheen=0.3)
        b = core.box("%s_%d" % (name, i), h + nn * 0.016, (bw, bh, 0.024), m, bev=0.005)
        b.rotation_mode = "QUATERNION"
        b.rotation_quaternion = _frame(nn, Vector((1, 0, 0)))
        ctx.add(b, grp, ob, kind="surface")
    for j, md in enumerate(ly.get("medals", [])):
        x = x0 * k + md.get("dx", 0.0)
        zz = z - bh - md.get("drop", 0.07)
        h, nn, ob = core.ray_any(ctx.outer, (x, -2.0, zz), (0, 1, 0))
        if h is None:
            continue
        rib = core.principled(ctx, "%s_rib%d" % (name, j), md.get("ribbon", cols[0]), rough=0.5, sheen=0.3)
        # the ribbon lies on the costume where it is (cast at its own height: offset up from the medal's hit it stood
        # off the chest's curve, the contact check)
        hr, nr, obr = core.ray_any(ctx.outer, (x, -2.0, zz + 0.04), (0, 1, 0))
        if hr is None:
            hr, nr, obr = h + Vector((0, 0, 0.04)), nn, ob
        rb = core.box("%s_rib%d" % (name, j), hr + nr * 0.010, (0.045, 0.06, 0.016), rib, bev=0.004)
        rb.rotation_mode = "QUATERNION"
        rb.rotation_quaternion = _frame(nr, Vector((1, 0, 0)))
        ctx.add(rb, grp, obr, kind="surface")
        from . import headgear
        headgear.emblem(ctx, dict(kind=md.get("kind", "star"), size=md.get("size", 0.10), color=md.get("color", "#E8B23A")),
                        h, nn, ob, grp, name="%s_medal%d" % (name, j), head=False)
    ctx.details[ly.get("detail", "medals")] = ly.get("min_px", 80)


def ruff(ctx, ly, name):
    """A pleated ruff round the neck (Iveta, §7.8: "кольцо белого плиссированного брыжа"): a ring from the neck out to
    `r` (kit units) at the neck base, its pleats a zig-zag up and down round the ring, white, 0.02 H thick."""
    neck = ctx.objs["neck"]
    zc = ly.get("z", -0.62)
    r_out = ly.get("r", 0.36)
    np_ = ly.get("pleats", 28)
    amp = ly.get("amp", 0.05)
    bm = bmesh.new()
    rows = []
    nr, na = 5, np_ * 4
    for i in range(nr + 1):
        t = i / nr
        row = []
        for j in range(na):
            a = 2 * math.pi * j / na
            d = Vector((math.sin(a), -math.cos(a), 0.0))
            h, nn = core.ray(neck, Vector((0, 0.07, zc)) + d * 2, -d)
            r0 = (Vector((h.x, h.y - 0.07, 0.0)).length if h is not None else 0.2) - 0.01
            r = r0 + (r_out - r0) * t
            z = zc + amp * t * math.sin(np_ * a) - 0.04 * t * t
            row.append(bm.verts.new((d.x * r, 0.07 + d.y * r * ly.get("depth_k", 1.0), z)))
        rows.append(row)
    for r0, r1 in zip(rows, rows[1:]):
        for j in range(na):
            jj = (j + 1) % na
            bm.faces.new((r0[j], r0[jj], r1[jj], r1[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    o = core.mesh_obj(name, bm)
    core.solidify(o, ly.get("t", 0.022), offset=0.0)
    m = core.principled(ctx, name, ly.get("color", "#F4F2EE"), rough=0.7, sheen=0.4)
    core.finish(o, m, sub=1)
    grp = "detail:" + ly["detail"] if ly.get("detail") else "costume:" + ly.get("id", "ruff")
    ctx.add(o, grp, neck, kind="embed")
    ctx.outer.append(o)
    if ly.get("signature"):
        ctx.sig_objs.append(o)
    if ly.get("detail"):
        ctx.details[ly["detail"]] = ly.get("min_px", 2000)
    return o


def tails(ctx, ly, name):
    """Fur tails hanging from a stole down the chest (Sairin, §7.8: "белый волчий палантин с хвостами"): from the
    points `at` (x in shoulder units, z), each a tapering metaball chain hanging down `len` with a soft swing, in the
    fur's material."""
    k = ctx.shoulder_k
    col = ly.get("color", "#F2F0EC")
    m = core.hair_mat(ctx, name, col, -1.6, -0.6, dark=ly.get("dark"), light=ly.get("light"), crevice=ly.get("crevice"),
                      rough=0.8)
    grp = "detail:" + ly["detail"] if ly.get("detail") else "costume:" + ly.get("id", "tails")
    objs = []
    for i, (x, z) in enumerate(ly.get("at", [(-0.20, -0.86), (0.20, -0.86)])):
        h, nn, ob = core.ray_any(ctx.outer, (x * k, -2.0, z), (0, 1, 0))
        if h is None:
            continue
        el = []
        ln = ly.get("len", 0.55)
        for j in range(14):
            t = j / 13
            p = h + nn * (0.05 + 0.02 * t) + Vector((0.03 * math.sin(math.pi * t) * (1 if x > 0 else -1), 0.0, -ln * t))
            hh, n2, _ = core.ray_any(ctx.outer, (p.x, -2.0, p.z), (0, 1, 0))
            if hh is not None:
                p = Vector((p.x, min(p.y, hh.y - 0.05), p.z))
            r = ly.get("r", 0.075) * (1.0 - 0.55 * t ** 1.5)
            el.append(dict(co=p, half=(r, r * 0.75, r * 1.1), stiff=2.2))
        o = core.mb_mesh(ctx, "Tail" + name + str(i), el, 0.010, m, smooth_iter=2, name="%s_%d" % (name, i))
        ctx.add(o, grp, ob, kind="surface")
        objs.append(o)
        if ly.get("signature"):
            ctx.sig_objs.append(o)
    ctx.outer += objs
    return objs


_P3_KINDS = {"epaulettes": epaulettes, "strip": strip, "aiguillette": aiguillette, "medal_bar": medal_bar,
             "ruff": ruff, "tails": tails}
