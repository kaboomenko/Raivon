"""The bust (§7.5 step 5): a lofted torso whose top rings are the neck, arms as capsules whose round tops are the
deltoids. Proportions from §7.3: shoulders 2.0 W (character 1.75–2.6 W; women 8 % narrower), the shoulder top flat
over ~60 % of the half width with a slope under 15 deg (epaulettes and pauldrons need a flat seat), the neck
0.50–0.60 W (women 0.36 W), the arms visible down to the bottom edge of the frame.

Body space = head-local units before the pose: the skull centre at the origin, the neck base around z -0.62, the
frame's bottom edge around z -1.3 (the framing solver decides).
"""
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
    sh = b.get("shoulders", S["shoulders"]) * (S["female_shoulders"] if ctx.female else 1.0)
    k = sh * ctx.W / 1.95
    neck = b.get("neck", 0.36 if ctx.female else S["neck_w"]) * ctx.W / 2
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
