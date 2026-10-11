"""The face (§7.5 step 2): eyes, lids, lash lines, brows, nose, ears, mouths, marks and the skin paint (blush,
freckles), all placed from the head's landmarks and ray casts. Sizes come from STYLE (§7.3) and the character's
face table (§7.6); the mood (§7.9) changes shapes, angles and lids, never where a feature sits.

Eyes (build_eyes): a shallow convex lens set in a shallow socket (its lower half deeper), leaning a little up with
the face under the eye and standing STYLE["sclera_protrude"] out of it — but only the lens's ALMOND is built (an
ellipse sclera_h tall and 0.85 of that wide, centred where a forward-looking eye shows its iris), its edges tucked
under the upper lid shell and the lower rim, so the white can never drip below the lid line or run past the corners
whatever the face's curvature. Iris, limbal ring and pupil are a radial gradient in its shader (the gaze is a shader
offset set by rig.solve_gaze, kept inside the almond); the upper lid is a skin shell over the lens that bulges only
inside the almond and sinks back into it outside (opening and tilt = character and mood); the lower rim is a thin
skin tube along the visible bottom (the designed lower lid, or the cheek where it covers more; a smile pushes it up
into an arch); the lid cut is calibrated from that bottom and the camera's perspective so the opening on the picture
is (open - low) x sclera_h (§7.6); a tapered lash line runs along the lid's edge (a flick for women). The brows sit
brow_gap above the calm lash line (+ the mood's lift). The two catchlights are added by rig.solve_gaze.
"""
import math

import bmesh
import bpy  # noqa: F401  (bpy before bmesh, everywhere in the kit)
from mathutils import Matrix, Vector

from . import core, style, head as head_mod
from .core import H, S
from .style import C
from .style import SKIN_SAT as S_SAT


# ------------------------------------------------------------------ skin
def skin_mat(ctx):
    """Skin (§7.11): SSS 0.25, roughness 0.5, a warm AO tone in the hollows, painted blush on the cheek apples and,
    when the character has them, freckles (level D: shader paint only) and the scar's pinker band."""
    m = core.principled(ctx, "skin", ctx.ch["skin"], rough=0.5, sss=0.25, spec=0.35)
    nt = m.node_tree
    nt.links.new(skin_color(ctx, nt), nt.nodes["Principled BSDF"].inputs["Base Color"])
    return m


def skin_color(ctx, nt):
    """The skin's base colour network (blush, warm hollows, nose tip, painted marks, per-tone saturation) -> socket."""
    ch = ctx.ch
    col = ch["skin"]
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
    sat = ch.get("skin_sat", S_SAT.get(tone, 1.0) if tone else 1.0)
    if sat != 1.0:
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = sat
        hs.inputs["Value"].default_value = 1.04
        nt.links.new(base, hs.inputs["Color"])
        base = hs.outputs[0]
    return base


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


def eye_geometry(ctx):
    """The eye's lens (§7.3): a shallow convex ellipsoid set in a shallow seat of the face, standing
    STYLE["sclera_protrude"] out of it; eye_fit x the visible sclera, so the almond cut out of it lies on its front
    dome. -> (rx, ry, rz, k), k = the dome's half height on a flat face in unit-sphere z."""
    hv = ctx.P["sclera_h"] / 2 * S["eye_fit"]
    ry = 0.42 * hv
    prot = S["sclera_protrude"] * H
    k = math.sqrt(1 - (1 - prot / ry) ** 2)
    rz = hv / k
    rx = S["sclera_w"] * hv / k
    return rx, ry, rz, k


class Almond:
    """The visible eye in lens units (§7.3), in the eye's local frame around x0 (the lens point a forward-looking eye
    shows its iris at): an ellipse sclera_h tall and 0.85 of that wide (u = (x - x0) / xc0 spans it), cut by the upper
    lid U(u) = U0 + kh (tilt (-side u) - arch u^2) and the designed lower lid D(u) = kh (2 low - 1 - bow u^2) (a smile
    pushes it up into a soft arch) or the face, where the face covers more of the lens than D (the cheek). U0 is set so
    the visible opening — below the lash line, above the lower rim — is (open - low) x sclera_h."""

    def __init__(self, ctx, side, rz, x0, mood=None):
        ey = ctx.ch["eyes"]
        mood = ey.get(ctx.mood if mood is None else mood, {})
        self.kh = ctx.P["sclera_h"] / 2 / rz
        self.xc0 = self.kh * ey.get("almond_w", 1.0)
        self.x0 = x0
        op = mood.get("open", ey.get("open", S["lid_open"]))
        self.open = op[0 if side < 0 else 1] if isinstance(op, (list, tuple)) else op
        self.low = mood.get("low", ey.get("low", 0.0))
        tilt = mood.get("tilt", ey.get("tilt", 0.08))
        arch = mood.get("arch", ey.get("arch", 0.24))
        bow = mood.get("bow", ey.get("bow", 0.0))
        self.a1, self.a2 = -self.kh * tilt * side, -self.kh * arch
        self.b0, self.b2 = self.kh * (2 * self.low - 1), -self.kh * bow
        self.U0 = self.kh * (2 * self.open - 1)
        self.clip = None          # face clip: [(u, z)] where the face covers the lens above D

    def ell(self, u):
        return self.kh * math.sqrt(max(0.0, 1 - u * u))

    def top(self, u):
        return min(self.U0 + self.a1 * u + self.a2 * u * u, self.ell(u))

    def design_bot(self, u):
        return max(self.b0 + self.b2 * u * u, -self.ell(u))

    def bot(self, u):
        b = self.design_bot(u)
        if self.clip:
            b = max(b, core.lerp_table(self.clip, u))
        return b

    def span(self, lc=0.0, rc=0.0):
        vis = [i / 200 for i in range(-200, 201) if self.top(i / 200) - lc - self.bot(i / 200) - rc > 0.03 * self.kh]
        return (vis[0], vis[-1]) if vis else (-0.5, 0.5)

    def x(self, u):
        return self.x0 + u * self.xc0


def build_eyes(ctx):
    """Per eye: the lens (only its almond is built: its edges tuck under the upper lid shell and the lower rim, so the
    white can never drip below the lid line or run past the corners, whatever the face's curvature), the upper lid
    shell, the lower rim tube along the visible bottom (the designed lid, or the cheek where it covers more), the
    lash line. The lid cut is calibrated from the measured bottom so the opening is exact (§7.6 lids x sclera)."""
    ch, p = ctx.ch, ctx.P
    ey = ch["eyes"]
    rx, ry, rz, kv = eye_geometry(ctx)
    prot = S["sclera_protrude"] * H
    head = ctx.objs["head"]
    ctx.objs["eyes"] = []
    lash_t = (S["lash_f"] if ctx.female else S["lash_m"]) * H
    rim_t = (S["rim_smile"] if ctx.smile else S["rim"]) * H
    shell = S["lid_shell"]
    lc, rc = lash_t * 0.5 / rz, rim_t / rz            # what the lash line and the rim tube cover, in lens z
    # §7.6 numbers are measured in H on the picture (chin to crown): the eyes stand ~0.4 nearer the camera than that
    # reference, so the perspective shows them larger; foresee it from the pose and the framing's distance
    from . import rig
    pw = rig.head_pose_matrix(ctx, with_body=True)
    chin, crown = ctx.L["chin"], ctx.L["crown"]
    d_ref = (crown.z - chin.z) * 588.0 * style.RENDER["lens"] / style.RENDER["sensor"] / ch["head"]["h_px"]
    y_ref = ((pw @ chin).y + (pw @ crown).y) / 2
    for side in (-1, 1):
        tag = "near" if side < 0 else "far"
        x = side * p["eye_x"]
        h0, n0 = core.ray_front(head, x, p["eye_z"])
        n_flat = Vector((n0.x, n0.y, 0.0)).normalized()
        yaw = math.atan2(n_flat.x, -n_flat.y) * 0.8
        # the lens faces a little up with the face under the eye (the cheek comes forward below it): its lower half
        # comes forward over the cheek, the upper half goes back under the lid and the brow ridge
        rot = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(math.radians(S["eye_pitch"]), 4, "X")
        r3 = rot.to_3x3()
        fwd = r3 @ Vector((0, -1, 0))
        centre = h0 - fwd * (ry - prot)
        # the almond is centred where a forward-looking eye shows its iris (the head's -Y on the lens), not on the
        # lens axis (which follows the face's curvature outward)
        dl = r3.inverted() @ Vector((0, -1, 0))
        x0 = Vector((dl.x / rx, dl.y / ry, dl.z / rz)).normalized().x
        al = Almond(ctx, side, rz, x0)
        kh = al.kh
        persp = d_ref / (d_ref + (pw @ centre).y - y_ref)

        def lens_pt(u, z, out=0.0):
            xl = al.x(u)
            yy = max(0.0, 1 - xl * xl - z * z)
            return centre + r3 @ Vector((xl * rx, -(math.sqrt(yy) * ry + out), z * rz))

        def covered(u, z):
            """Is the lens point inside the head (the face covers it)? A short ray out along the eye's forward axis
            that leaves the head's surface (the hit normal along the ray) says so."""
            q = lens_pt(u, z, 0.0005)
            hit, nor = core.ray(head, q, fwd, dist=0.08)
            return hit is not None and nor.dot(fwd) > 0.0

        # the face clip: where the cheek covers the lens above the designed lower lid, the visible bottom follows it
        clip = []
        for i in range(21):
            u = -1 + 2 * i / 20
            b = al.design_bot(u)
            t = al.ell(u)
            z = b
            if covered(u, z):
                lo_, hi_ = b, t
                for _ in range(10):
                    mid = (lo_ + hi_) / 2
                    if covered(u, mid):
                        lo_ = mid
                    else:
                        hi_ = mid
                z = hi_
            clip.append((u, z))
        al.clip = clip
        # the lid calibrated from the measured bottom: the widest column between the lash line and the rim (what
        # P-A3 measures) is (open - low) x sclera_h — tilt, arch and the smile's bow move it off the middle
        target = 2 * kh * (al.open - al.low) / persp
        us = [i / 40 for i in range(-40, 41)]

        def calibrate(a_, tgt):
            lo_, hi_ = -kh, 3 * kh
            for _ in range(30):
                mid = (lo_ + hi_) / 2
                a_.U0 = mid
                if max(a_.top(u) - lc - a_.bot(u) - rc for u in us) < tgt:
                    lo_ = mid
                else:
                    hi_ = mid
            a_.U0 = (lo_ + hi_) / 2

        calibrate(al, target)
        # the calm lid, for the brows: they sit on the character's calm lid line plus the mood's own lift — a squint
        # must not pull them down with the lid
        al_c = Almond(ctx, side, rz, x0, mood="calm")
        al_c.clip = clip
        calibrate(al_c, 2 * kh * (al_c.open - al_c.low) / persp)
        ri = S["iris"] * ey.get("iris_k", 1.0) * kh     # iris radius in units of rz (diameter = 0.65 x sclera height)
        # the lens: a grid over the almond (corner to corner, the full ellipse height above its bottom: the shell hides
        # what is above the lid), in unit-lens coordinates (the object is scaled to rx, ry, rz)
        u0, u1 = al.span()
        bm = bmesh.new()
        nu, nv = 40, 18
        grid = []
        for i in range(nu + 1):
            u = u0 - 0.03 + (u1 - u0 + 0.06) * i / nu
            zb = al.bot(u) - rc * 0.7
            zt = max(al.ell(u), al.top(u)) + 0.04 * kh
            row = []
            for j in range(nv + 1):
                z = zb + (zt - zb) * j / nv
                xl = al.x(u)
                yy = max(0.0, 1 - xl * xl - z * z)
                row.append(bm.verts.new((xl, -math.sqrt(yy), z)))
            grid.append(row)
        for i in range(nu):
            for j in range(nv):
                bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        eye = core.mesh_obj("eye_" + tag, bm)
        eye.location = centre
        eye.rotation_euler = rot.to_euler()
        eye.scale = (rx, ry, rz)
        core.finish(eye, eye_mat(ctx, "eye_" + tag, core.hex_scale(ey["iris"], ey.get("iris_shade", 1.0)), ri,
                                 rx / rz))
        if eye.data.polygons and eye.data.polygons[len(eye.data.polygons) // 2].normal.y > 0:
            for f in eye.data.polygons:
                f.flip()
        eye["al_x0"], eye["al_xc0"], eye["al_kh"] = al.x0, al.xc0, kh
        ctx.add(eye, "eye", head, kind="embed", head=True)

        # the upper lid: a skin shell over the lens, `lid_shell` x its depth inside the almond's ellipse and sinking
        # back into it just outside (so the lid is a soft bulge over the eye, its crease following the eye's outline,
        # never a plate standing off the face past the corners); its cut, seen along the eye's axis, is the almond's
        # top
        def shell_k(xl, z):
            # (the fade reaches a little sooner toward the corners: the lid is back in the face where its edge starts
            # to rise, so the rise draws no fold up from the corner — review r3)
            rho = math.hypot((xl - al.x0) / al.xc0 * 1.08, z / kh)
            return shell - (shell - 0.72) * core.smoothstep(1.0, 1.26, rho)

        def shell_cut(xl):
            """The shell's lower edge: the almond's top, then rising past the corners (no flap below the corner) —
            easing in (quadratic over the first 0.3, then straight), so the lash line's curve runs on into the rise
            instead of turning up at a sharp angle."""
            u = (xl - al.x0) / al.xc0
            if abs(u) <= 1.0:
                return al.top(u)
            d = abs(u) - 1.0
            return al.top(math.copysign(1.0, u)) + 2.5 * kh * (d * d / 0.6 if d < 0.3 else d - 0.15)

        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=56, radius=1.0)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < shell_cut(v.co.x) or v.co.y > 0.3], context="VERTS")
        for v in bm.verts:
            v.co.y *= shell_k(v.co.x, v.co.z)
        lid = core.mesh_obj("lid_" + tag, bm)
        lid.location = centre
        lid.rotation_euler = rot.to_euler()
        lid.scale = (rx, ry, rz)
        core.solidify(lid, 0.10, offset=-1)
        core.finish(lid, ctx.mats["skin"], sub=1)
        lid.visible_shadow = False   # the lid does not darken the eye white under it (readable whites, §7.4 iris rule)
        ctx.add(lid, "skin", eye, kind="embed", head=True)
        u0, u1 = al.span(lc, rc)
        # the lower rim: a thin skin tube along the visible bottom on the lens (every mood: the eye sits in a lid, never
        # on the cheek; where the cheek covers the lens it follows the cheek); a smile's pushed-up lid is fuller
        rp_, rr_ = [], []
        n = 15
        for i in range(n):
            t = i / (n - 1)
            u = u0 + (u1 - u0) * t
            rp_.append(lens_pt(u, al.bot(u), rim_t * 0.15))
            rr_.append(0.35 + 0.65 * min(1.0, 1.7 * math.sin(math.pi * t)))   # full over the middle 2/3
        rim = core.curve("lowrim_" + tag, rp_, rr_, rim_t, ctx.mats["skin"])
        ctx.add(rim, "skin", eye, kind="surface", head=True)
        # lash line along the upper lid's cut edge (the shell's edge), corner to corner, thick in the middle; women get
        # an outer flick
        pts, rad = [], []
        n = 17
        ext = 0.06
        for i in range(n):
            t = i / (n - 1)
            u = (u0 - ext) + (u1 - u0 + 2 * ext) * t
            xl = al.x(u)
            zl = al.top(u)
            yy = 1 - xl * xl - zl * zl
            if yy <= 0.02:
                continue
            loc = Vector((xl * rx, -math.sqrt(yy) * ry * shell_k(xl, zl), zl * rz))
            pts.append(centre + r3 @ loc + fwd * 0.003 + Vector((0, 0, 0.002)))
            rad.append(0.45 + 0.65 * math.sin(math.pi * t))
        if ctx.female and len(pts) > 2:
            fl, ang = S["lash_flick"]
            ln = ey.get("flick", fl) * H
            o_end = pts[-1] if side > 0 else pts[0]
            d = r3 @ (Vector((side * math.cos(math.radians(ang)), 0.0, math.sin(math.radians(ang)))) * ln)
            if side > 0:
                pts.append(o_end + d)
                rad.append(0.25)
            else:
                pts.insert(0, o_end + d)
                rad.insert(0, 0.25)
        lash = core.curve("lash_" + tag, pts, rad, lash_t / 2, core.principled(ctx, "lash", C["lash"], 0.5))
        ctx.add(lash, "lash", lid, kind="surface", head=True)
        calm_pts = []
        for i in range(n):
            u = (u0 - ext) + (u1 - u0 + 2 * ext) * i / (n - 1)
            xl, zl = al_c.x(u), al_c.top(u)
            yy = 1 - xl * xl - zl * zl
            if yy > 0.02:
                calm_pts.append(centre + r3 @ Vector((xl * rx, -math.sqrt(yy) * ry * shell_k(xl, zl), zl * rz)))
        # the almond outline for the QA (head-local, before the pose): under the lash line, over the rim
        us = [u0 + (u1 - u0) * i / 16 for i in range(17)]
        outline = [lens_pt(u, al.top(u) - lc) for u in us] + [lens_pt(u, al.bot(u) + rc) for u in us[::-1]]
        ctx.objs["eyes"].append(dict(obj=eye, side=side, centre=centre, radii=(rx, ry, rz), ri=ri, tag=tag,
                                     open=al.open, low=al.low, kv=kv, kh=kh, x0=al.x0, xc0=al.xc0, almond=outline))
        ctx.L["lash_" + tag] = (calm_pts or pts, lash_t / 2)        # the calm lash line (the brows' base)
    ctx.L["sclera_top"] = p["eye_z"] + p["sclera_h"] / 2


# ------------------------------------------------------------------ brows
def _lash_top(lash, x):
    """The top of a lash line (head-local z) at x: its points interpolated, flat beyond its ends."""
    pts, r = lash
    ps = sorted(pts, key=lambda q: q.x)
    if x <= ps[0].x:
        return ps[0].z + r
    for a, b in zip(ps, ps[1:]):
        if a.x <= x <= b.x:
            f = (x - a.x) / max(b.x - a.x, 1e-9)
            return a.z + (b.z - a.z) * f + r
    return ps[-1].z + r


def build_brows(ctx):
    """Brows (§7.3): thick at the inner third, tapering x0.45, 1.15-1.3 eye widths long, 0.05 H above the eye: placed
    from the eye's measured lash line (the visible top of the eye), not the nominal sclera top, so the gap holds for
    every lid opening — the brow's lowest edge clears the lash line by exactly brow_gap (+ the character's lift)."""
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
        inner_dz = (br.get("inner", 0.0) + mood.get("inner", 0.0)) * H
        outer_dz = (br.get("outer", 0.0) + mood.get("outer", 0.0)) * H
        arch = (br.get("arch", 0.025) + mood.get("arch", 0.0)
                + (br.get("arch_far", 0.0) if side > 0 else 0.0)) * H
        # the far brow starts nearer the nose: its outer end turns away with the face, the inner part carries it
        x_in = side * (p["eye_x"] - eye_w * (br.get("in_far", 0.66) if side > 0 else 0.5) - 0.02 * H)
        shape = br.get("shape", "arc")

        def sample(base_z):
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
            return pts, rad

        base_z = ctx.L["sclera_top"] + S["brow_gap"] * H + thick * 0.5 + lift
        lash = ctx.L.get("lash_" + tag)
        if lash:
            for _ in range(3):
                pts, rad = sample(base_z)
                gap = min(q.z - thick * 0.5 * r - _lash_top(lash, q.x) for q, r in zip(pts, rad))
                base_z += S["brow_gap"] * H + lift - gap
        pts, rad = sample(base_z)
        if lash:
            ctx.L["brow_gap_" + tag] = min(q.z - thick * 0.5 * r - _lash_top(lash, q.x) for q, r in zip(pts, rad)) / H
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
    ctx.objs["nose"] = obj
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
    """Open mouths: an EXACT boolean on the head (a D prism, after Subsurf). The prism's faces carry the mouth's dark
    interior material into the head (material transfer): the pocket the cut leaves IS the dark cavity, exactly the
    opening's shape on every face — a separate cavity shape poked through a narrow cheek in the 3/4 view. Its back
    stands STYLE["mouth_depth"] behind the face at the mouth line (the same pocket on every head; a fixed y made it
    shallow on narrow faces). A copy of the uncut face is kept for build_mouth: the real rim is where it meets the
    prism's slanted walls."""
    mp = ctx.ch["mouth"].get(ctx.mood, {})
    if mp.get("type") != "open":
        return
    w, hgt = mp.get("w", S["mouth_open"][0]) * H / 2, mp.get("h", S["mouth_open"][1]) * H
    top = ctx.L["mouth_z"] + mp.get("dz", 0.0) * H + 0.006
    pts = mouth_outline(w, top, hgt, mp.get("near", 0.02) * H, mp.get("far", 0.02) * H)
    xoff = mp.get("x", 0.0) * H
    pts = [(x + xoff, z) for x, z in pts]
    head = ctx.objs["head"]
    fy = ctx.L["face_y"]
    core.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ref = core.link(bpy.data.objects.new("mouth_ref", bpy.data.meshes.new_from_object(head.evaluated_get(dg))))
    ref.matrix_world = head.matrix_world.copy()
    ref.hide_render = True
    ref.hide_viewport = False
    y0, y1, k = -0.95, fy + mp.get("depth", S["mouth_depth"]) * H, 0.8
    cx = sum(q[0] for q in pts) / len(pts)
    cz = sum(q[1] for q in pts) / len(pts)
    bm = bmesh.new()
    front = [bm.verts.new((x, y0, z)) for x, z in pts]
    back = [bm.verts.new((cx + (x - cx) * k, y1, cz + (z - cz) * k)) for x, z in pts]
    bm.faces.new(front[::-1])
    bm.faces.new(back)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[i], front[j], back[j], back[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    cutter = core.mesh_obj("mouth_cutter", bm)
    dark = core.principled(ctx, "mouth_in", C["mouth_in"], 0.6)
    cutter.data.materials.append(dark)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    head.data.materials.append(dark)          # slot 1: the pocket's walls (qa.id_pass maps it to the "mouth" group)
    mod = head.modifiers.new("mouth", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.material_mode = "TRANSFER"
    mod.object = cutter
    ctx.objs["mouth_cutter"] = cutter
    ctx.objs["mouth_ref"] = ref
    ctx.mouth_pts = pts
    ctx.mouth_cut = dict(cx=cx, cz=cz, y0=y0, y1=y1, k=k)
    ctx.mouth_open = True


def _in_poly(x, z, poly):
    inside = False
    for (x1, z1), (x2, z2) in zip(poly, poly[1:] + poly[:1]):
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            inside = not inside
    return inside


class _Opening:
    """The open mouth's real rim (§7.3 "губа-трубка по краю"): the uncut face (carve_mouth's copy) crosses the
    cutter's slanted walls there. A face point is cut when it lies inside the prism's cross-section at its depth
    (the outline scaled toward its centroid from 1 at the front to k at the back); the rim along a vertical line is
    the height where that turns false — found by bisection, with no thresholds, so a pointed chin, a receding lip or a
    narrow face cannot fool it."""

    def __init__(self, ctx):
        self.ref = ctx.objs["mouth_ref"]
        self.pts = ctx.mouth_pts
        c = ctx.mouth_cut
        self.cx, self.cz, self.y0, self.y1, self.k = c["cx"], c["cz"], c["y0"], c["y1"], c["k"]

    def face(self, x, z):
        h, n = core.ray_front(self.ref, x, z)
        return (h, n) if h is not None else (None, None)

    def cut(self, x, z):
        h, _ = self.face(x, z)
        if h is None or not (self.y0 <= h.y <= self.y1):
            return False
        sc = 1.0 - (1.0 - self.k) * (h.y - self.y0) / (self.y1 - self.y0)
        return _in_poly(self.cx + (x - self.cx) / sc, self.cz + (z - self.cz) / sc, self.pts)

    def rim(self, x, z_in, z_out):
        """The rim's height at x between z_in (inside the opening) and z_out (on the face), or None when the opening
        does not reach this x."""
        if not self.cut(x, z_in) or self.cut(x, z_out):
            return None
        lo, hi = z_in, z_out
        for _ in range(24):
            mid = (lo + hi) / 2
            if self.cut(x, mid):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2


def build_mouth(ctx):
    ch = ctx.ch
    head = ctx.objs["head"]
    mp = ch["mouth"].get(ctx.mood, ch["mouth"]["calm"])
    lip_col = ch["mouth"].get("lip", core.hex_mix(ch["skin"], "#c0504a", 0.45))
    lip_m = core.principled(ctx, "lip", lip_col, rough=0.4, sss=0.2)
    dark = core.principled(ctx, "mouth_in", C["mouth_in"], 0.6)
    low_t = (S["lower_lip_f"] if ctx.female else S["lower_lip_m"]) * H
    if getattr(ctx, "mouth_open", False):
        _open_mouth(ctx, head, lip_m, low_t)
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
            # thinner toward the far corner: it turns away with the face and would stand off the far cheek's outline
            lr.append((0.35 + 0.8 * math.sin(math.pi * t) ** 0.7) * (1 - 0.45 * t * t))
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
        ctx.add(core.curve("lip_up", upp, [(0.4 + 0.5 * math.sin(math.pi * (k + 1) / (len(upp) + 1)))
                                           * (1 - 0.45 * ((k + 1) / (len(upp) + 1)) ** 2) for k in range(len(upp))],
                           low_t * 0.32, lip_m), "lip", head, kind="surface", head=True)
    ctx.L["mouth_corners"] = [cp[0], cp[-1]]


def _open_mouth(ctx, head, lip_m, low_t):
    """The open mouth's parts on the real rim (_Opening): upper teeth (§7.3 #FBF6EA over the top 30 % of the
    opening) bent to the face's curve just behind the top rim, off the corners (0.72 of the width); the tongue in
    the lower third, set back behind the lower rim; the lower lip tube on the lower rim (and a thin upper lip for
    women). When the rim cannot be found at enough samples (an unusual face), each part falls back to the outline
    drawn on the face (the old placement) and says so in ctx.notes — never a silent empty curve."""
    pts = ctx.mouth_pts
    op = _Opening(ctx)
    xs = [q[0] for q in pts]
    zs = [q[1] for q in pts]
    cx = (min(xs) + max(xs)) / 2
    w = (max(xs) - min(xs)) / 2
    hh = max(zs) - min(zs)
    fy = ctx.L["face_y"]
    bottom_tbl = sorted((q[0], q[1]) for q in pts[:21])               # the outline's lower arc, by x
    top_tbl = sorted([(q[0], q[1]) for q in pts[21:]] + [(pts[0][0], pts[0][1]), (pts[20][0], pts[20][1])])

    def face_y(x, z):
        h_, _ = op.face(x, z)
        return h_.y if h_ is not None else fy

    # upper teeth: a slab bent to the face's curve behind the top rim
    tw = w * 0.72
    th = hh * S["teeth_share"]
    tx = [cx - tw * 1.05 + 2.1 * tw * i / 8 for i in range(9)]
    samples = []
    for x in tx:
        zt = core.lerp_table(top_tbl, x)
        ze = op.rim(x, zt - hh * 0.4, zt + 0.05)
        if ze is not None:
            samples.append((x, ze, face_y(x, ze + 0.012)))
    if len(samples) < 3:
        ctx.notes.append("%s %s: open-mouth top rim found at %d of 9 teeth samples; teeth on the outline instead"
                         % (ctx.cid, ctx.mood, len(samples)))
        samples = [(x, core.lerp_table(top_tbl, x) - 0.004, face_y(x, core.lerp_table(top_tbl, x) + 0.012)) for x in tx]
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=1.0)
    ze_t = [(q[0], q[1]) for q in samples]
    yf_t = [(q[0], q[2]) for q in samples]
    for v in bm.verts:
        x = cx + v.co.x * tw
        ze = core.lerp_table(ze_t, x)
        yf = core.lerp_table(yf_t, x)
        v.co = Vector((x, yf + 0.016 + (v.co.y + 1.0) * 0.018, ze + 0.004 - th * 0.5 + v.co.z * th * 0.62))
    teeth = core.mesh_obj("teeth", bm)
    core.finish(teeth, core.principled(ctx, "teeth", C["teeth"], 0.3, coat=0.3))
    ctx.add(teeth, "teeth", head, kind="embed", head=True)
    # the tongue: its bottom just under the lower rim's middle, its front behind the face there (on a receding chin a
    # tongue placed from the mouth line's depth stuck out under the lip)
    zb = core.lerp_table(bottom_tbl, cx)
    zr = op.rim(cx, (zb + core.lerp_table(top_tbl, cx)) / 2, zb - 0.06)
    if zr is None:
        zr = zb
    ty, tz = (0.055, hh * 0.20)
    tongue = core.uvsphere("tongue", (cx + 0.008, face_y(cx, zr - 0.004) + 0.02 + ty, zr + tz * 0.6),
                           (w * 0.55, ty, tz), core.principled(ctx, "tongue", C["tongue"], 0.45, sss=0.2), 32, 16)
    ctx.add(tongue, "tongue", head, kind="embed", head=True)
    # the lower lip: a tube on the lower rim, not up the corners
    lower = pts[:21][3:-3]
    lr_t = low_t * 0.42
    lp, lr = [], []

    def lip_pt(x, z):
        h_, n_ = op.face(x, z)
        return None if h_ is None else h_ + n_ * lr_t * 0.35

    for i, (x, z) in enumerate(lower):
        ze = op.rim(x, (z + core.lerp_table(top_tbl, x)) / 2, z - 0.06)
        q = lip_pt(x, ze - lr_t * 0.55) if ze is not None else None
        if q is not None:
            lp.append(q)
            lr.append(0.45 + 0.8 * math.sin(math.pi * i / (len(lower) - 1)))
    if len(lp) < 5:
        ctx.notes.append("%s %s: open-mouth lower rim found at %d of %d samples; lower lip on the outline instead"
                         % (ctx.cid, ctx.mood, len(lp), len(lower)))
        lp, lr = [], []
        for i, (x, z) in enumerate(lower):
            q = lip_pt(x, z - 0.016)
            if q is not None:
                lp.append(q)
                lr.append(0.45 + 0.8 * math.sin(math.pi * i / (len(lower) - 1)))
    if len(lp) < 3:
        raise ValueError("%s %s: the open mouth's lower lip has %d points (the outline misses the face)"
                         % (ctx.cid, ctx.mood, len(lp)))
    ctx.add(core.curve("lip_low", lp, lr, lr_t, lip_m), "lip", head, kind="surface", head=True)
    if ctx.female:  # a thin upper lip along the real top rim
        up = pts[21:]
        ut = low_t * 0.4
        upp, upr = [], []
        for i, (x, z) in enumerate(up):
            ze = op.rim(x, (z + core.lerp_table(bottom_tbl, x)) / 2, z + 0.05)
            h_, n_ = op.face(x, ze + ut * 0.55) if ze is not None else (None, None)
            if h_ is not None:
                upp.append(h_ + n_ * ut * 0.35)
                upr.append(0.5 + 0.5 * math.sin(math.pi * (i + 1) / (len(up) + 1)))
        if len(upp) < 3:
            ctx.notes.append("%s %s: open-mouth top rim found at %d of %d samples; upper lip on the outline instead"
                             % (ctx.cid, ctx.mood, len(upp), len(up)))
            upp, upr = [], []
            for i, (x, z) in enumerate(up):
                h_, n_ = op.face(x, z + 0.012)
                if h_ is not None:
                    upp.append(h_ + n_ * ut * 0.35)
                    upr.append(0.5 + 0.5 * math.sin(math.pi * (i + 1) / (len(up) + 1)))
        if len(upp) > 2:
            ctx.add(core.curve("lip_up", upp, upr, ut, lip_m), "lip", head, kind="surface", head=True)
    # the corners: the outline's two ends (pts[20] the near one, x = -w; pts[0] the far one), on the face
    corners = []
    for q in (pts[20], pts[0]):
        hc, _ = op.face(q[0], q[1] + 0.004)
        corners.append(hc if hc is not None else Vector((q[0], fy, q[1])))
    ctx.L["mouth_corners"] = corners
    ctx.L["mouth_top"] = top_tbl
    bpy.data.objects.remove(ctx.objs.pop("mouth_ref"))


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
