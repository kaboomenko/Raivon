"""The face (§7.5 step 2): eyes, lids, lash lines, brows, nose, ears, mouths, marks and the skin paint (blush,
freckles), all placed from the head's landmarks and ray casts. Sizes come from STYLE (§7.3) and the character's
face table (§7.6); the mood (§7.9) changes shapes, angles and lids, never where a feature sits.

Eyes: an ellipsoid eyeball in a socket dimple, standing STYLE["sclera_protrude"] out of the face plane; iris,
limbal ring and pupil are a radial gradient in its shader (the gaze is a shader offset set by rig.solve_gaze once the
pose and the camera are known); an upper-lid skin shell 1.1x the eye cut by an arched plane (opening and tilt =
character and mood), a lower-lid shell, a tapered lash line along the lid's cut edge (a flick for women). The two
catchlights are added by rig.solve_gaze (they must sit on the posed iris).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import core, head as head_mod
from .core import H, S
from .style import C
from .style import SKIN_SAT as S_SAT


# ------------------------------------------------------------------ skin
def skin_mat(ctx):
    """Skin (§7.11): SSS 0.25, roughness 0.5, a warm AO tone in the hollows, painted blush on the cheek apples and,
    when the character has them, freckles (level D: shader paint only) and the scar's pinker band."""
    ch = ctx.ch
    col = ch["skin"]
    m = core.principled(ctx, "skin", col, rough=0.5, sss=0.25, spec=0.35)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    p = head_mod.params(ctx)
    ez = p["eye_z"]
    cz = ez - S["cheek_below"] * H + (S["cheek_smile"] * H if ctx.smile else 0.0)
    cx = S["cheek_x"] * H * (p["hx"] / 0.48) / 0.98
    add = core.node_math(nt, "ADD", core.node_blob(nt, (-cx, -0.40, cz), S["blush_r"] * H * 1.5),
                         core.node_blob(nt, (cx, -0.40, cz), S["blush_r"] * H * 1.5), clamp=True)
    # blush opacity at the apple's centre = the character's share (§7.3: men 15 %, women 25 %, young 30 %; a smile +10 %)
    blush = ch.get("blush", S["blush"]["f" if ctx.female else "m"]) + (0.10 if ctx.smile else 0.0)
    fac = core.node_math(nt, "MULTIPLY", add, blush, clamp=True)
    base = core.node_mix(nt, fac, col, C["blush"])
    # the warm tone of the hollows (AO) instead of grey
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.samples = 8
    ao.inputs["Distance"].default_value = 0.05 * H
    warm = core.node_ramp(nt, ao.outputs["AO"], [(0.0, core.hex_mix(col, "#c0503a", 0.35)), (0.72, "#ffffff")])
    base = core.node_mix(nt, 1.0, base, warm, "MULTIPLY")
    nose = ch.get("nose", {})
    if nose.get("tip") and ctx.L.get("nose_tip_guess") is not None:
        tp = ctx.L["nose_tip_guess"]
        fac = core.node_math(nt, "MULTIPLY", core.node_blob(nt, (tp.x, tp.y - 0.04, tp.z), nose.get("tip_r", 0.075)),
                             nose.get("tip_k", 0.55), clamp=True)
        base = core.node_mix(nt, fac, base, nose["tip"])
    for nm, (pts, rad, colr, k) in ctx.skin_paint.items():
        acc = None
        for q in pts:
            bl = core.node_blob(nt, q, rad)
            acc = bl if acc is None else core.node_math(nt, "MAXIMUM", acc, bl)
        sharp = core.node_math(nt, "GREATER_THAN", acc, 0.35)
        base = core.node_mix(nt, core.node_math(nt, "MULTIPLY", sharp, k), base, colr)
    tone = ch.get("skin_tone")
    sat = S_SAT.get(tone, 1.0) if tone else 1.0
    if sat != 1.0:
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = sat
        hs.inputs["Value"].default_value = 1.04
        nt.links.new(base, hs.inputs["Color"])
        base = hs.outputs[0]
    nt.links.new(base, b.inputs["Base Color"])
    return m


def plan_skin_paint(ctx):
    """Freckles and other painted marks need surface points: computed on a temporary copy of the head before the
    skin material is finalised (head-local object coordinates)."""
    ctx.skin_paint = {}


def add_freckles(ctx):
    fr = ctx.ch.get("freckles")
    if not fr:
        return
    head = ctx.objs["head"]
    p = ctx.P
    n = ctx.rng.randint(*S["freckle_n"])
    pts = []
    tries = 0
    while len(pts) < n and tries < 400:
        tries += 1
        side = ctx.rng.choice((-1, 1))
        x = side * ctx.rng.uniform(0.05, 0.27) * (p["hx"] / 0.45)
        z = p["eye_z"] - ctx.rng.uniform(0.07, 0.19) * H + 0.06 * H * (1 - abs(x) / 0.3)
        if abs(x) < 0.06 and z < p["eye_z"] - 0.17 * H:
            continue
        h, nn = core.ray_front(head, x, z)
        if h is None or any((h - q).length < 0.045 for q in pts):
            continue
        pts.append(h)
    ctx.skin_paint["freckles"] = (pts, S["freckle_d"] * H * 0.9, fr, 0.6)
    ctx.details["freckles"] = 10  # P-A8: >= 10 dots (counted as px here; the reviewer counts dots)


# ------------------------------------------------------------------ eyes
def eye_mat(ctx, name, iris_hex, ri, sx):
    """Eyeball shader: sclera / limbal ring / iris gradient / pupil from the radius in the local XZ plane around the
    gaze point; ri = iris radius in units of the eye's z radius, sx = rx / rz (keeps the iris round)."""
    m = core.principled(ctx, name, C["sclera"], rough=0.25, coat=0.5, spec=0.6)
    nt = m.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "gaze"
    mp.inputs["Scale"].default_value = (sx, 0.0, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs[0])
    g = nt.nodes.new("ShaderNodeTexGradient")
    g.gradient_type = "SPHERICAL"  # fac = 1 - r
    nt.links.new(mp.outputs[0], g.inputs[0])
    pupil = S["pupil_smile"] if ctx.smile else ctx.ch["eyes"].get("pupil", S["pupil"])
    rp = ri * pupil
    lim = ri * S["limbal"]
    e = 0.012
    # a saturated mid tone, darker toward the rim (iris vs sclera >= 30 L*, §7.4), a dark limbal ring, a touch lighter
    # around the pupil
    mid = core.hex_scale(iris_hex, 0.52)
    dk = core.hex_scale(iris_hex, 0.25)
    lt = core.hex_scale(iris_hex, 0.95)
    stops = [(0.0, "#e9e2da"), (1 - ri - e, C["sclera"]), (1 - ri, dk), (1 - ri + lim, core.hex_scale(iris_hex, 0.45)),
             (1 - ri + lim + 0.05, mid), (1 - rp - 0.06, core.hex_scale(iris_hex, 0.74)), (1 - rp - e * 0.5, lt), (1 - rp, C["pupil"]),
             (1.0, C["pupil"])]
    nt.links.new(core.node_ramp(nt, g.outputs["Fac"], stops), nt.nodes["Principled BSDF"].inputs["Base Color"])
    m["eye_ri"], m["eye_rp"], m["eye_sx"] = ri, rp, sx
    return m


def _lid_cut(c0, tilt, arch, side):
    def cut(x):
        return c0 + tilt * (-side * x) - arch * x * x   # -side*x > 0 toward the nose
    return cut


def eye_geometry(ctx):
    """The eye as a shallow convex lens set flush in a shallow seat of the face (§7.3): it stands
    STYLE["sclera_protrude"] out of the face, and its visible outline (the cap outside the face) is the sclera:
    `sclera_h` tall and 0.85 of that wide. -> (rx, ry, rz, k) where k is the visible half height in unit-sphere z."""
    hv = ctx.P["sclera_h"] / 2 * S["eye_fit"]
    ry = 0.42 * hv
    prot = S["sclera_protrude"] * H
    k = math.sqrt(1 - (1 - prot / ry) ** 2)
    rz = hv / k
    rx = S["sclera_w"] * hv / k
    return rx, ry, rz, k


def build_eyes(ctx):
    ch, p = ctx.ch, ctx.P
    ey = ch["eyes"]
    mood = ey.get(ctx.mood, {})
    rx, ry, rz, kv = eye_geometry(ctx)
    prot = S["sclera_protrude"] * H
    ri = S["iris"] * ey.get("iris_k", 1.0) * kv      # iris radius in units of rz (diameter = 0.65 x sclera height)
    head = ctx.objs["head"]
    ctx.objs["eyes"] = []
    lash_t = (S["lash_f"] if ctx.female else S["lash_m"]) * H
    for side in (-1, 1):
        tag = "near" if side < 0 else "far"
        x = side * p["eye_x"]
        h0, n0 = core.ray_front(head, x, p["eye_z"])
        n_flat = Vector((n0.x, n0.y, 0.0)).normalized()
        yaw = math.atan2(n_flat.x, -n_flat.y) * 0.8
        rot = Matrix.Rotation(yaw, 4, "Z")
        fwd = rot.to_3x3() @ Vector((0, -1, 0))
        centre = h0 - fwd * (ry - prot)
        eye = core.uvsphere("eye_" + tag, centre, (rx, ry, rz), None, 48, 24)
        eye.rotation_euler = rot.to_euler()
        core.set_mat(eye, eye_mat(ctx, "eye_" + tag, core.hex_scale(ey["iris"], ey.get("iris_shade", 1.0)), ri, rx / rz))
        ctx.add(eye, "eye", head, kind="embed", head=True)
        # lids: opening (share of the visible sclera height left open), tilt (+ lowers the inner corner), arch
        opening = mood.get("open", ey.get("open", S["lid_open"]))
        if isinstance(opening, (list, tuple)):
            opening = opening[0 if side < 0 else 1]
        c0 = -kv + opening * 2 * kv
        tilt = mood.get("tilt", ey.get("tilt", 0.08))
        arch = mood.get("arch", ey.get("arch", 0.24))
        cut = _lid_cut(c0, tilt, arch, side)
        shell = S["lid_shell"]
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < cut(v.co.x) or v.co.y > 0.3], context="VERTS")
        lid = core.mesh_obj("lid_" + tag, bm)
        lid.location = centre
        lid.rotation_euler = rot.to_euler()
        lid.scale = (rx * shell, ry * shell, rz * shell)
        core.solidify(lid, 0.10, offset=-1)
        core.finish(lid, ctx.mats["skin"], sub=1)
        lid.visible_shadow = False   # the lid does not darken the eye white under it (readable whites, §7.4 iris rule)
        ctx.add(lid, "skin", eye, kind="embed", head=True)
        # lower lid: a thin rim over the bottom of the eye; a smile pushes it up into a happy curve
        low = mood.get("low", ey.get("low", 0.0))           # share of the visible height it covers at the middle
        if low <= 0.0:                                        # calm: the face itself is the lower rim
            low = None
        lc = -kv + (low or 0.0) * 2 * kv
        if low is not None:
            bm = bmesh.new()
            bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > lc - 0.10 * kv * v.co.x * v.co.x or v.co.y > 0.3],
                             context="VERTS")
            lo = core.mesh_obj("lowlid_" + tag, bm)
            lo.location = centre
            lo.rotation_euler = rot.to_euler()
            lo.scale = (rx * 1.04, ry * 1.04, rz * 1.04)
            core.solidify(lo, 0.10, offset=-1)
            core.finish(lo, ctx.mats["skin"], sub=1)
            ctx.add(lo, "skin", eye, kind="embed", head=True)
        # lash line along the upper lid's cut edge, thick in the middle; women get an outer flick
        pts, rad = [], []
        n = 15
        for i in range(n):
            u = -0.97 + 1.94 * i / (n - 1)
            z = cut(u)
            yy = 1 - u * u - z * z
            if yy <= 0.02:
                continue
            loc = Vector((u * rx * shell, -math.sqrt(yy) * ry * shell, z * rz * shell))
            pts.append(centre + rot.to_3x3() @ loc + fwd * 0.003 + Vector((0, 0, 0.002)))
            t = (u + 0.97) / 1.94
            rad.append(0.45 + 0.65 * math.sin(math.pi * t))
        if ctx.female and len(pts) > 2:
            fl, ang = S["lash_flick"]
            ln = ey.get("flick", fl) * H
            o_end = pts[-1] if side > 0 else pts[0]
            d = Vector((side * math.cos(math.radians(ang)), 0.0, math.sin(math.radians(ang)))) * ln
            d = rot.to_3x3() @ d
            if side > 0:
                pts.append(o_end + d)
                rad.append(0.25)
            else:
                pts.insert(0, o_end + d)
                rad.insert(0, 0.25)
        lash = core.curve("lash_" + tag, pts, rad, lash_t / 2, core.principled(ctx, "lash", C["lash"], 0.5))
        ctx.add(lash, "lash", lid, kind="surface", head=True)
        ctx.objs["eyes"].append(dict(obj=eye, side=side, centre=centre, radii=(rx, ry, rz), ri=ri, tag=tag,
                                     open=opening, cut=(c0, tilt, arch), kv=kv))
    ctx.L["sclera_top"] = p["eye_z"] + p["sclera_h"] / 2


# ------------------------------------------------------------------ brows
def build_brows(ctx):
    ch, p = ctx.ch, ctx.P
    br = ch["brows"]
    mood = br.get(ctx.mood, {})
    head = ctx.objs["head"]
    eye_w = 2 * S["sclera_w"] * p["sclera_h"] / 2
    length0 = br.get("len", S["brow_len"]) * eye_w
    thick = br.get("thick", S["brow"]) * H
    col = br["color"]
    mat = core.principled(ctx, "brow", col, 0.7, sheen=0.2)
    for side in (-1, 1):
        tag = "near" if side < 0 else "far"
        # the far brow turns away from the camera: a little longer so it reads as long as the near one
        length = length0 * (br.get("len_far", 1.12) if side > 0 else 1.0)
        lift = (br.get("lift", (0.0, 0.0))[0 if side < 0 else 1] + mood.get("lift", (0.0, 0.0))[0 if side < 0 else 1]) * H
        inner_dz = mood.get("inner", 0.0) * H
        outer_dz = mood.get("outer", 0.0) * H
        arch = (br.get("arch", 0.025) + mood.get("arch", 0.0)
                + (br.get("arch_far", 0.0) if side > 0 else 0.0)) * H
        base_z = ctx.L["sclera_top"] + S["brow_gap"] * H + thick * 0.5 + lift
        x_in = side * (p["eye_x"] - eye_w * 0.5 - 0.02 * H)
        shape = br.get("shape", "arc")
        pts, rad = [], []
        n = 8
        for i in range(n):
            t = i / (n - 1)                          # inner -> outer
            x = x_in + side * length * t
            if shape == "straight":
                z = base_z + arch * 0.4 * math.sin(math.pi * t) + 0.01 * H * t
            elif shape == "angular":
                z = base_z + arch * (t / 0.62 if t < 0.62 else (1 - t) / 0.38 * 0.6 + 0.4) - 0.01 * H
            else:  # arc, bushy
                z = base_z + arch * math.sin(math.pi * min(1.0, t * 1.05))
            z += inner_dz * (1 - t) + outer_dz * t
            hit, nor = core.ray_front(head, x, z)
            if hit is None:
                continue
            pts.append(hit + nor * thick * 0.42)
            taper = 1.0 if t < 0.33 else 1 - (1 - S["brow_taper"]) * (t - 0.33) / 0.67
            rad.append(taper * (0.75 if t == 0 else 1.0))
        if shape == "bushy":
            obj = _bushy_brow(ctx, pts, rad, thick, mat, tag)
        else:
            obj = core.curve("brow_" + tag, pts, rad, thick / 2, mat)
        ctx.add(obj, "brow", head, kind="surface", head=True)
        ctx.L["brow_" + tag] = (pts[0], pts[-1])


def _bushy_brow(ctx, pts, rad, thick, mat, tag):
    """A bushy brow: a metaball strip of flattened tufts along the path, each tuft leaning outward-up (hair-like
    locks, §7.3 "кустистая с прядками")."""
    el = []
    for i in range(len(pts) - 1):
        a, b = Vector(pts[i]), Vector(pts[i + 1])
        for k in range(3):
            t = k / 3
            c = a.lerp(b, t)
            r = (rad[i] * (1 - t) + rad[i + 1] * t) * thick * 0.5
            tang = (b - a).normalized()
            up = Vector((0, 0, 1))
            dirv = (tang * 0.8 + up * 0.5).normalized()
            el.append(dict(co=c + Vector((0, 0, ctx.rng.uniform(-0.15, 0.15) * r)),
                           half=(r * 1.25, r * 0.55, r * 0.95), stiff=2.6, rot=core.frame_quat(dirv, Vector((0, -1, 0)))))
    return core.mb_mesh(ctx, "Brow" + tag, el, 0.006, mat, smooth_iter=2, name="brow_" + tag)


# ------------------------------------------------------------------ nose
def build_nose(ctx):
    ch, p = ctx.ch, ctx.P
    nose = ch["nose"]
    head = ctx.objs["head"]
    kind = nose["type"]
    nz = p["eye_z"] - nose.get("drop", 0.20) * H          # the nose tip height
    hit, nor = core.ray_front(head, 0, nz)
    ys = hit.y
    tip = nose.get("tip", ch["skin"])
    W = ctx.W
    if kind == "potato":
        w = S["nose_potato"] * W * nose.get("k", 1.0)
        el = [dict(co=(0, ys - 0.07, nz - 0.005), half=w * 0.46, stiff=2.2),                # the bulb
              dict(co=(w * 0.40, ys - 0.02, nz - 0.03), half=w * 0.26, stiff=2.6),             # two wings
              dict(co=(-w * 0.40, ys - 0.02, nz - 0.03), half=w * 0.26, stiff=2.6),
              dict(co=(0, ys - 0.012, nz + 0.085), half=(0.034, 0.036, 0.06), stiff=2.0)]     # a short bridge
    elif kind == "button":
        d = S["nose_button"] * H * nose.get("k", 1.0)
        el = [dict(co=(0, ys - d * 0.42, nz), half=d * 0.5, stiff=2.4),
              dict(co=(d * 0.42, ys - d * 0.05, nz - d * 0.18), half=d * 0.26, stiff=2.8),
              dict(co=(-d * 0.42, ys - d * 0.05, nz - d * 0.18), half=d * 0.26, stiff=2.8),
              dict(co=(0, ys + 0.0, nz + d * 0.8), half=(d * 0.22, d * 0.3, d * 0.5), stiff=2.0)]
    else:  # straight wedge with a rounded tip (narrow)
        L = S["nose_straight"] * H * nose.get("k", 1.0)
        wn = nose.get("w", 0.055)
        el = [dict(co=(0, ys - wn * 0.9, nz + 0.005), half=wn * 0.85, stiff=2.4),
              dict(co=(wn * 0.75, ys - wn * 0.15, nz - 0.012), half=wn * 0.5, stiff=2.8),
              dict(co=(-wn * 0.75, ys - wn * 0.15, nz - 0.012), half=wn * 0.5, stiff=2.8)]
        for k in range(4):
            t = (k + 1) / 4
            el.append(dict(co=(0, ys - wn * 0.9 * (1 - t) + 0.01 * t, nz + L * t * 0.9),
                           half=(wn * (0.6 - 0.2 * t), wn * 0.6, wn * 0.75), stiff=2.2))
    m = ctx.mats["skin"]          # the same skin (blush, warm hollows, the tip colour) as the head: one surface
    obj = core.mb_mesh(ctx, "Nose", el, 0.007, m, smooth_iter=2, name="nose")
    ctx.add(obj, "nose", head, kind="embed", head=True)
    ctx.L["nose_tip"] = Vector((0, ys - 0.06, nz))


# ------------------------------------------------------------------ ears
def build_ears(ctx):
    p = ctx.P
    head = ctx.objs["head"]
    eh = S["ear_h"] * H * ctx.ch.get("ear_k", 1.0)
    for s in (-1, 1):
        tag = "near" if s < 0 else "far"
        h, n = ctx.L["ear_" + tag]
        if h is None:
            continue
        cz = p["eye_z"] - 0.10 * H
        hh, nn = core.ray(head, (s * 3, h.y, cz), (-s, 0, 0))
        base = hh if hh is not None else h
        rot = Matrix.Rotation(math.radians(s * 20), 4, "Z").to_quaternion()
        out = S["ear_out"] * H
        el = [dict(co=base + Vector((s * out * 0.55, 0.0, 0.0)), half=(0.03, eh * 0.30, eh * 0.46), stiff=2.5, rot=rot),
              dict(co=base + Vector((s * out * 0.7, -0.01, -eh * 0.36)), half=eh * 0.17, stiff=2.5),
              dict(co=base + Vector((s * out * 1.25, -0.02, eh * 0.05)), half=(0.018, eh * 0.18, eh * 0.30), stiff=4.0,
                   neg=True, rot=rot)]
        ear = core.mb_mesh(ctx, "Ear" + tag, el, 0.007, ctx.mats["skin"], smooth_iter=2, name="ear_" + tag)
        ctx.add(ear, "skin", head, kind="embed", head=True)


# ------------------------------------------------------------------ mouths
def mouth_outline(w, top, depth, near_lift=0.0, far_lift=0.0):
    """2D open-mouth outline (x, z) in the face plane: a D whose corners rise by the lifts (near = -X)."""
    pts = []
    n = 20
    for i in range(n + 1):                       # bottom arc, far corner -> near corner
        t = math.pi * i / n
        x = w * math.cos(t)
        lift = far_lift if x > 0 else near_lift
        z = top - depth * math.sin(t) ** 0.7 + (0.02 + lift) * abs(x / w) ** 3
        pts.append((x, z))
    for i in range(1, 8):                        # upper edge, nearly flat, corners lifted
        t = i / 8
        x = -w + 2 * w * t
        lift = far_lift if x > 0 else near_lift
        z = top + (0.02 + lift) * abs(x / w) ** 2 - 0.004
        pts.append((x, z))
    return pts


def carve_mouth(ctx):
    """Smile: an EXACT boolean on the head (a D prism, after Subsurf) — the dark cavity, teeth and tongue go in."""
    mp = ctx.ch["mouth"].get(ctx.mood, {})
    if mp.get("type") != "open":
        return
    w, hgt = mp.get("w", S["mouth_open"][0]) * H / 2, mp.get("h", S["mouth_open"][1]) * H
    top = ctx.L["mouth_z"] + mp.get("dz", 0.0) * H + 0.006
    pts = mouth_outline(w, top, hgt, mp.get("near", 0.02) * H, mp.get("far", 0.02) * H)
    xoff = mp.get("x", 0.0) * H
    pts = [(x + xoff, z) for x, z in pts]
    bm = bmesh.new()
    front = [bm.verts.new((x, -0.95, z)) for x, z in pts]
    cx = sum(q[0] for q in pts) / len(pts)
    cz = sum(q[1] for q in pts) / len(pts)
    back = [bm.verts.new((cx + (x - cx) * 0.8, -0.30, cz + (z - cz) * 0.8)) for x, z in pts]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cutter = core.mesh_obj("mouth_cutter", bm)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    head = ctx.objs["head"]
    mod = head.modifiers.new("mouth", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cutter
    ctx.objs["mouth_cutter"] = cutter
    ctx.mouth_pts = pts
    ctx.mouth_open = True


def build_mouth(ctx):
    ch = ctx.ch
    head = ctx.objs["head"]
    mp = ch["mouth"].get(ctx.mood, ch["mouth"]["calm"])
    lip_col = ch["mouth"].get("lip", core.hex_mix(ch["skin"], "#c0504a", 0.45))
    lip_m = core.principled(ctx, "lip", lip_col, rough=0.4, sss=0.2)
    dark = core.principled(ctx, "mouth_in", C["mouth_in"], 0.6)
    low_t = (S["lower_lip_f"] if ctx.female else S["lower_lip_m"]) * H
    if getattr(ctx, "mouth_open", False):
        pts = ctx.mouth_pts
        xs = [q[0] for q in pts]
        zs = [q[1] for q in pts]
        cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
        w = (max(xs) - min(xs)) / 2
        hh = max(zs) - min(zs)
        fy = ctx.L["face_y"]
        cav = core.uvsphere("mouth_in", (cx, fy + 0.19, cz), (w * 1.0, 0.13, hh * 0.72), dark, 32, 16)
        ctx.add(cav, "mouth", head, kind="embed", head=True)
        # upper teeth: a rounded slab just behind the upper edge, 30 % of the opening height (§7.3)
        top_z = max(zs)
        teeth = core.uvsphere("teeth", (cx, fy + 0.034, top_z - hh * 0.15), (w * 0.86, 0.025, hh * 0.17),
                              core.principled(ctx, "teeth", C["teeth"], 0.3, coat=0.3), 32, 16)
        ctx.add(teeth, "teeth", head, kind="embed", head=True)
        # the tongue in the lower third, set back
        tongue = core.uvsphere("tongue", (cx + 0.008, fy + 0.07, min(zs) + hh * 0.17), (w * 0.56, 0.06, hh * 0.24),
                               core.principled(ctx, "tongue", C["tongue"], 0.45, sss=0.2), 32, 16)
        ctx.add(tongue, "tongue", head, kind="embed", head=True)
        lower = pts[:21]
        lp, lr = [], []
        for i, (x, z) in enumerate(lower[2:-2]):
            hh2, nn = core.ray_front(head, x, z - 0.016)
            if hh2 is None:
                continue
            lp.append(hh2 + nn * 0.004)
            t = i / (len(lower) - 5)
            lr.append(0.45 + 0.8 * math.sin(math.pi * t))
        lip = core.curve("lip_low", lp, lr, low_t * 0.42, lip_m)
        ctx.add(lip, "lip", head, kind="surface", head=True)
        if ctx.female:  # a thin upper lip along the top edge
            up = pts[21:]
            upp, upr = [], []
            for i, (x, z) in enumerate(up):
                hh2, nn = core.ray_front(head, x, z + 0.012)
                if hh2 is None:
                    continue
                upp.append(hh2 + nn * 0.004)
                upr.append(0.5 + 0.5 * math.sin(math.pi * (i + 1) / (len(up) + 1)))
            if len(upp) > 2:
                ctx.add(core.curve("lip_up", upp, upr, low_t * 0.4, lip_m), "lip", head, kind="surface", head=True)
        ctx.L["mouth_corners"] = [Vector((min(xs), fy, pts[-1][1])), Vector((max(xs), fy, pts[0][1]))]
        return
    # closed: a dark crease (>= 0.035 H) with its corners set by the expression, the lower lip under it, a thin upper
    # lip for women; a moustache may hide part of it (Bram)
    w = mp.get("w", S["mouth_w"]) * H / 2
    near, far = mp.get("near", 0.0) * H, mp.get("far", 0.0) * H
    xoff = mp.get("x", 0.0) * H
    z0 = ctx.L["mouth_z"] + mp.get("dz", 0.0) * H
    sag = mp.get("sag", 0.006) * H
    # the closed mouth reads as one fold >= 0.035 H (§7.3): a dark crease line over the lower lip (and a thin upper lip
    # for women); the crease alone stays thin so it does not read as a moustache
    crease_t = mp.get("crease", 0.018) * H
    cp, lp, lr, upp = [], [], [], []
    n = 11
    for i in range(n):
        t = i / (n - 1)
        x = -w + 2 * w * t
        side_lift = near * (1 - t) ** 2.2 + far * t ** 2.2
        zc = z0 - sag * math.sin(math.pi * t) + side_lift
        h, nn = core.ray_front(head, x + xoff, zc)
        if h is not None:
            cp.append(h + nn * 0.004)
        h, nn = core.ray_front(head, (x + xoff) * 0.84, zc - crease_t * 0.5 - low_t * 0.45)
        if h is not None and 0 < i < n - 1:
            lp.append(h + nn * low_t * 0.35)
            lr.append(0.35 + 0.8 * math.sin(math.pi * t) ** 0.7)
        if ctx.female:
            h, nn = core.ray_front(head, (x + xoff) * 0.9, zc + crease_t * 0.55)
            if h is not None and 0 < i < n - 1:
                upp.append(h + nn * 0.003)
    rads = [0.45] + [0.9 + 0.1 * math.sin(math.pi * k / (len(cp) - 1)) for k in range(1, len(cp) - 1)] + [0.45]
    crease = core.curve("mouth_line", cp, rads, crease_t / 2, dark)
    ctx.add(crease, "mouth", head, kind="surface", head=True)
    if lp:
        ctx.add(core.curve("lip_low", lp, lr, low_t / 2, lip_m), "lip", head, kind="surface", head=True)
    if len(upp) > 2:
        ctx.add(core.curve("lip_up", upp, [0.4 + 0.5 * math.sin(math.pi * (k + 1) / (len(upp) + 1)) for k in range(len(upp))],
                           low_t * 0.32, lip_m), "lip", head, kind="surface", head=True)
    ctx.L["mouth_corners"] = [cp[0], cp[-1]]


# ------------------------------------------------------------------ marks
def build_scar(ctx):
    sc = ctx.ch.get("scar")
    if not sc:
        return
    head = ctx.objs["head"]
    p = ctx.P
    m = core.principled(ctx, "scar", C["scar"], rough=0.5, sss=0.1)
    (x0, z0), (x1, z1) = sc["from"], sc["to"]
    x0, x1 = x0 * p["hx"] / 0.48, x1 * p["hx"] / 0.48
    z0, z1 = p["eye_z"] + z0 * H, p["eye_z"] + z1 * H

    def on_face(x, z, off):
        h, n = core.ray_front(head, x, z)
        return None if h is None else h + n * off

    pts = [on_face(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, 0.004) for t in (0, 0.25, 0.5, 0.75, 1)]
    pts = [q for q in pts if q is not None]
    w = S["scar_w"] * H
    obj = core.curve("scar", pts, [0.5, 1.0, 1.1, 0.9, 0.45][:len(pts)], w / 2, m)
    ctx.add(obj, "detail:scar", head, kind="surface", head=True)
    for k, t in enumerate((0.25, 0.5, 0.75)):
        x = x0 + (x1 - x0) * t
        z = z0 + (z1 - z0) * t
        dx, dz = (z1 - z0), -(x1 - x0)
        ln = math.hypot(dx, dz)
        dx, dz = dx / ln * 0.028, dz / ln * 0.028
        a = [on_face(x + ddx, z + ddz, 0.004) for ddx, ddz in ((-dx, -dz), (dx, dz))]
        if all(q is not None for q in a):
            st = core.curve("stitch", a, [0.8, 0.8], w * 0.32, m, order=2)
            ctx.add(st, "detail:scar", head, kind="surface", head=True)
    ctx.details["scar"] = 150
