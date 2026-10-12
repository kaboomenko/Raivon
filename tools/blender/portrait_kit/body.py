"""The bust (§7.5 step 5): a lofted torso whose top rings are the neck, arms as capsules whose round tops are the
deltoids. Proportions from §7.3: shoulders 2.0 W (character 1.75–2.6 W; women 8 % narrower), the shoulder top flat
over ~60 % of the half width with a slope under 15 deg (epaulettes and pauldrons need a flat seat), the neck
0.50–0.60 W (women 0.40 W: §7.3 says 0.36), the arms visible down to the bottom edge of the frame.

Hands (§7.5, `hand`): a metaball palm and fingers gripping a prop ("wrap" round a rod, "pinch" of a small piece),
the forearm entering from the bottom of the frame in its sleeve, a cuff; used by the props of Vega, Seir, Vance and
Irma when the character's hands are on (their hand-free fallbacks otherwise).

Body space = head-local units before the pose: the skull centre at the origin, the neck base around z -0.62, the
frame's bottom edge around z -1.3 (the framing solver decides).
"""
import math

from . import core
from .core import S

# (z, half width, half depth, superellipse exponent, y offset) for shoulders 2.0 W at W = 0.975; x scales with the
# character's shoulder width, the neck rings with its neck width
TORSO = [(-2.0, 0.62, 0.44, 2.6, 0.0), (-1.5, 0.66, 0.47, 2.6, -0.03), (-1.2, 0.68, 0.47, 2.7, -0.03),
         (-0.95, 0.68, 0.44, 2.9, 0.0), (-0.80, 0.66, 0.40, 3.2, 0.02), (-0.72, 0.60, 0.35, 3.4, 0.04),
         (-0.68, 0.48, 0.30, 3.0, 0.05), (-0.655, 0.34, 0.25, 2.4, 0.06)]
NECK = [(-0.70, 1.25, 0.95, 2.0, 0.07), (-0.62, 1.08, 0.90, 2.0, 0.07), (-0.52, 1.0, 0.86, 2.0, 0.075),
        (-0.30, 0.96, 0.84, 2.0, 0.08)]


def spec(ctx):
    b = ctx.ch.get("body", {})
    # women's shoulders 8 % narrower (§7.3) unless the character's width is absolute (Frey's 2.6 W, §7.6)
    sh = b.get("shoulders", S["shoulders"]) * (S["female_shoulders"] if ctx.female and not b.get("absolute") else 1.0)
    k = sh * ctx.W / 1.95
    # women 0.40 W (§7.3's 0.36 W read as a head pasted on a stalk at the album size, P2 review)
    neck = b.get("neck", 0.40 if ctx.female else S["neck_w"]) * ctx.W / 2
    rings = [(z, hx * k, hy * (0.85 + 0.15 * k), n, yo) for z, hx, hy, n, yo in TORSO]
    top = TORSO[-1]
    rings.append((-0.625, max(neck * 1.12, top[1] * k * 0.62), neck * 0.98, 2.0, 0.07))   # the neck base, under collars
    neck_rings = [(z, neck * fx, neck * fy * 0.95, n, yo) for z, fx, fy, n, yo in NECK]
    return rings, k, neck_rings


def build_body(ctx, base_mat):
    rings, k, neck_rings = spec(ctx)
    ctx.torso_spec = rings + neck_rings[2:]     # collars read the neck from here
    ctx.shoulder_k = k
    torso = core.loft("torso", rings, seg=48, cap_top=True)
    core.finish(torso, base_mat, sub=2)
    ctx.objs["torso"] = torso
    ctx.add(torso, "costume", None, kind="root")
    # the neck: skin, from inside the torso up into the head (visible >= 0.06 H unless a collar or beard covers it)
    neck = core.loft("neck", neck_rings, seg=40, cap_top=False, cap_bottom=False)
    core.finish(neck, ctx.mats["skin"], sub=2)
    ctx.objs["neck"] = neck
    ctx.add(neck, "skin", torso, kind="embed")
    arm_mat = ctx.mats.get("sleeve", base_mat)
    for s in (-1, 1):
        top = (s * 0.56 * k, 0.05, -0.86)
        bot = (s * 0.76 * k, 0.09, -2.0)
        arm = core.capsule("arm%+d" % s, top, bot, 0.205 * k, 0.18 * k)
        core.finish(arm, arm_mat, sub=2)
        ctx.objs["arm%+d" % s] = arm
        ctx.objs["arm_axis%+d" % s] = (top, bot)
        ctx.add(arm, "costume", torso, kind="embed")
    core.update()
    ctx.L["shoulder_z"] = -0.66
    return torso


# ------------------------------------------------------------------ hands (§7.5: Vance, Seir, Irma, Vega)
def hand(ctx, h):
    """A cartoon hand (§7.3: x1.4 real, the palm 0.42 H wide, 4 fingers; §7.5: a metaball palm 0.42 x 0.16 x 0.40 H
    + index, middle, fused ring-and-little finger + thumb, stiffness 3, resolution 0.012, Smooth 2, Subsurf 1; fingers
    >= 0.07 H thick; the wrist in a cuff, the forearm entering from the bottom of the frame).

    h: target (the point the grip holds, body space), axis (the held object's axis), radius (the object's radius
    there), grip "wrap" (round a rod: spyglass, pointer shaft; curl 1.0, "lay" = curl 0.6) or "pinch" (a small
    piece between thumb and index: the queen), elbow (where the forearm comes from, below the frame), glove (a
    colour: a gloved hand) else the skin, sleeve (a colour; default the costume's sleeve), cuff (a colour), size
    (x the norm), roll (deg, turns the palm round the forearm). Returns {obj, wrist, f, n} or None."""
    from mathutils import Matrix, Vector
    k = h.get("size", 0.85)
    T = Vector(h["target"])
    a = Vector(h.get("axis", (0, 0, 1))).normalized()
    r = h.get("radius", 0.05)
    E = Vector(h.get("elbow", (T.x, T.y - 0.1, -1.7)))
    cam = core.world_dir(ctx, (0.0, -1.0, 0.0))
    H_ = core.H
    palm_w, palm_t, palm_l = 0.42 * H_ * 0.5 * k, 0.16 * H_ * 0.5 * k, 0.40 * H_ * 0.5 * k
    fr = max(0.07 * H_ / 2, 0.036) * k                      # finger radius (>= 0.07 H thick)
    grip = h.get("grip", "wrap")
    curl = h.get("curl", 1.0 if grip == "wrap" else 0.6)
    # the palm frame: f (wrist -> knuckles) across the object's axis and along the forearm; n (palm -> object)
    fdir = (T - E)
    if grip == "pinch":
        # a piece held up on the fingertips: the hand points along the forearm, its palm toward the camera's side
        fdir = fdir.normalized()
        n = cam.cross(fdir).cross(fdir).normalized()
        if n.dot(cam) > 0:
            n = -n
    else:
        fdir = (fdir - a * fdir.dot(a)).normalized()
        n = a.cross(fdir).normalized()
        # "back": the back of the hand toward the camera, the object behind it (Seir's spyglass on the shoulder);
        # "fingers": the object in front of the palm, the curled fingers seen wrapping it (Vega's pointer)
        if (n.dot(cam) > 0) != (h.get("face", "back") == "fingers"):
            n = -n
    if h.get("roll"):
        q = Matrix.Rotation(math.radians(h["roll"]), 3, fdir)
        n = (q @ n).normalized()
    if grip == "pinch":
        # the piece stands on the fingertips: the palm below the pinch point, a little behind it
        P = T - fdir * palm_l * 1.55 - n * palm_t * 0.3
    else:
        P = T - n * (r + palm_t)
    W = P - fdir * palm_l
    s = n.cross(fdir).normalized()              # across the palm (thumb side sign chosen below)
    thumb_side = 1.0 if s.dot(cam) < 0 else -1.0
    el = [dict(co=P, half=(palm_w, palm_t, palm_l), stiff=3.0, rot=core.frame_quat(fdir, n)),
          dict(co=W + fdir * palm_l * 0.25, half=(palm_w * 0.8, palm_t * 0.9, palm_l * 0.5), stiff=3.0,
               rot=core.frame_quat(fdir, n))]
    knuck = P + fdir * palm_l * 0.85
    fingers = [(-0.70, 1.0, 1.0), (0.0, 1.08, 1.0), (0.70, 0.92, 1.22)]     # (offset across, length, width)
    for off, ln, wk in fingers:
        K = knuck + s * off * palm_w * 0.95 * -thumb_side
        rad = fr * wk
        if grip == "pinch" and off < -0.3:
            # the index reaches up to the pinch point
            pts = [K, K + fdir * 0.05 * ln + n * 0.02, T + s * -thumb_side * rad * 0.6 - n * rad * 0.3]
            for p0, p1 in zip(pts, pts[1:]):
                for t in (0.0, 0.2, 0.4, 0.6, 0.8):
                    el.append(dict(co=p0.lerp(p1, t), half=rad, stiff=4.0))
            el.append(dict(co=pts[-1], half=rad * 0.92, stiff=4.0))
            continue
        C = T + a * (K - T).dot(a)
        u = (K - C)
        rho = max(u.length, r + rad)
        u.normalize()
        v = a.cross(u).normalized()
        if v.dot(fdir) < 0:
            v = -v
        total = (math.radians(200) if grip == "wrap" else math.radians(120)) * curl * ln
        if grip == "pinch":
            rho = rad * 1.6
            C = K + n * rad * 1.6
            u = (K - C).normalized()
        steps = 14
        for i in range(steps + 1):
            th = total * i / steps
            p = C + (u * math.cos(th) + v * math.sin(th)) * (rho if grip != "pinch" else rad * 1.6)
            if grip != "pinch":
                p = C + (u * math.cos(th) + v * math.sin(th)) * (r + rad * 1.05) + u * (rho - r - rad) * (1 - i / steps)
            # capsule-like fingers: dense, stiff balls (less field spill, so neighbours keep a crease between them)
            el.append(dict(co=p, half=rad * (1.0 - 0.10 * i / steps), stiff=4.0))
    # the thumb: from the palm's side near the wrist, round the object the other way, ending by the index tip
    tb = W + fdir * palm_l * 0.55 + s * thumb_side * palm_w * 0.85
    if grip == "pinch":
        tt = T - s * -thumb_side * fr * 0.6 + n * fr * 0.2
        pts = [tb, (tb + tt) / 2 + n * 0.03 + s * thumb_side * 0.03, tt]
    else:
        C = T + a * (tb - T).dot(a)
        u = (tb - C).normalized()
        v = a.cross(u).normalized()
        if v.dot(fdir) > 0:
            v = -v
        pts = [tb]
        for i in range(1, 5):
            th = math.radians(115) * curl * i / 4
            pts.append(C + (u * math.cos(th) + v * math.sin(th)) * (r + fr * 1.05) + a * 0.03 * i * -thumb_side * 0.0)
    for p0, p1 in zip(pts, pts[1:]):
        for t in (0.0, 0.2, 0.4, 0.6, 0.8):
            el.append(dict(co=p0.lerp(p1, t), half=fr * 1.05, stiff=4.0))
    el.append(dict(co=pts[-1], half=fr * 0.95, stiff=4.0))
    glove = h.get("glove")
    mat = (core.principled(ctx, "glove", glove, rough=0.45, coat=0.25) if glove else ctx.mats["skin"])
    o = core.mb_mesh(ctx, "Hand", el, h.get("res", 0.008), mat, smooth_iter=2, name="hand")
    s_mod = o.modifiers.new("sub", "SUBSURF")
    s_mod.levels = s_mod.render_levels = 1
    # the forearm from below the frame up to the wrist, in the sleeve, with a cuff
    sleeve_col = h.get("sleeve")
    sl = (core.fabric(ctx, "forearm", sleeve_col, rough=0.8, sheen=0.3) if sleeve_col
          else ctx.mats.get("sleeve", ctx.mats["base"]))
    fa = core.capsule("forearm", W - fdir * 0.02, E, 0.085 * k, 0.12 * k)
    core.finish(fa, sl, sub=2)
    ctx.add(fa, "costume", ctx.objs["torso"], kind="free")
    ctx.add(o, "skin" if not glove else "detail:" + h.get("detail", "glove"), fa, kind="free")
    if h.get("cuff"):
        cf = core.torus("cuff", W - fdir * 0.035, 0.085 * k, 0.024 * k,
                        core.principled(ctx, "cuff", h["cuff"], rough=0.7, sheen=0.3), nrm=fdir, seg=32, rseg=10)
        ctx.add(cf, "costume", fa, kind="free")
    ctx.objs["hand"] = o
    ctx.L["hand_box"] = (P, palm_w * 2.5)
    return dict(obj=o, wrist=W, f=fdir, n=n)
