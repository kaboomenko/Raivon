"""Head cages (§7.5 step 1): a spherified cube (10×10 quads per face) shaped by a superball blend from the cranium to
the jaw, about 18 Gaussian "brushes" whose positions are face parameters, Subdivision Surface 2. The head then hands
out its landmarks (ray casts on the evaluated mesh): eye centres, brow line, nose base, mouth corners, ears,
hairline, crown, jaw corners, chin, the hat ring and the collar ring. Everything else is placed from them.

Shapes (chars.py "head"):
  square — round cranium -> square jaw (superball 2.1 -> 3.5), jaw +6 % (Bram, Frey, Kort);
  oval   — 2.0 -> 2.4, rounded chin (Lira, Vance);
  heart  — wide cheekbones (+0.03 H), the jaw tapers to a narrow pointed chin (Vega);
  long   — a taller cranium, narrower jaw (Olm, Vik, Rai);
  round  — a ball from crown to chin, full cheeks (Hawk).
Character extras (chars.py "head"): jowls (Kort's heavy jaw folds), jaw (+ wider), chin, cheekbones, muzzle,
brow_ridge, cheeks.
Head-local kit units: the skull centre at the origin, chin z = -H/2, crown z = +H/2, the face looks along -Y; +X is
the character's left (the far side in the portrait), -X its right (the near side, toward the camera).
"""
import math

import bmesh
import bpy
from mathutils import Vector

from . import core
from .core import H, S

SHAPES = {
    #          n_top n_jaw jaw_scale taper chin_flat depth
    "square": (2.1, 3.5, 0.06, 0.0, 0.75, 0.47),
    "oval": (2.0, 2.4, -0.02, 0.10, 0.88, 0.45),
    "heart": (2.25, 2.15, -0.02, 0.34, 0.95, 0.45),
    "long": (2.1, 2.6, -0.04, 0.12, 0.85, 0.45),
    "round": (2.0, 2.15, 0.03, 0.02, 0.92, 0.46),
}


def params(ctx):
    hd = ctx.ch["head"]
    n0, n1, jaw, taper, flat, depth = SHAPES[hd.get("shape", "oval")]
    n0 = hd.get("n_top", n0)        # a squarer skull top (Ormdek's head-block, §7.8)
    jaw += hd.get("jaw", 0.0)
    if ctx.female:
        jaw -= (1 - S["female_jaw"])
    p = dict(hx=ctx.W / 2, hy=depth * (0.62 + 0.38 * hd["wh"] / 0.92), hz=H / 2, n0=n0, n1=n1, jaw=jaw, taper=taper,
             flat=flat, shape=hd.get("shape", "oval"))
    p["eye_z"] = -H / 2 + hd.get("eye_line", S["eye_line"]) * H
    p["eye_x"] = hd.get("eye_spacing", S["eye_spacing"]) * H / 2
    p["sclera_h"] = ctx.ch["eyes"].get("sclera", S["sclera_h"]) * H
    return p


def cheek_dz(ctx, side):
    """The mood's lift of a cheek apple (side -1 near, +1 far), kit units (§7.9: a smile 0.04-0.07 H — the character's
    cheek_smile scales it —, a snarl 0.02, the cunning near cheek 0.03, the tired cheeks -0.03)."""
    v = ctx.fx.get("cheek", (0.0, 0.0))[0 if side < 0 else 1]
    return v * H * (ctx.ch["head"].get("cheek_smile", 1.0) if v > 0 else 1.0)


def brushes(ctx, p):
    """Gaussian sculpt brushes (centre, radius, displacement), in head-local units, scaled to this head."""
    sx = p["hx"] / 0.48
    sy = p["hy"] / 0.47
    ez = p["eye_z"]
    ex = p["eye_x"]
    hd = ctx.ch["head"]
    cheek_amt = (0.05 + ctx.fx.get("cheek_amt", 0.0)) * hd.get("cheeks", 1.0)
    sock_r = p["sclera_h"] * 0.85
    sock_d = S["socket_depth"] * H
    face_y = -0.42 * sy
    b = []
    for s in (-1, 1):
        cheek_z = ez - S["cheek_below"] * H + cheek_dz(ctx, s)
        b += [
            ((s * (ex - 0.005), face_y, ez + 0.17), 0.11, (0, -0.022 * hd.get("brow_ridge", 1.0), 0.012)),  # brow ridge
            ((s * ex, face_y - 0.02, ez + 0.005), sock_r, (0, sock_d, 0.0)),                     # eye socket
            # the socket's lower half deeper: the cheek apple must not cover the bottom of the almond (the eye shows
            # its full lower curve over the cheek, its rim follows the cheek)
            ((s * (ex + 0.1 * p["sclera_h"]), face_y - 0.02, ez - S["socket_low_z"] * p["sclera_h"]),
             S["socket_low_r"] * p["sclera_h"], (0, S["socket_low"] * H, 0.0)),
            ((s * 0.27 * sx, -0.33 * sy, ez - 0.04), 0.11,
             (s * (0.025 + hd.get("cheekbones", 0.0)), -0.015 - hd.get("cheekbones", 0.0) * 0.5, 0.0)),  # cheekbone
            ((s * S["cheek_x"] * H * sx / 0.98, -0.36 * sy, cheek_z), S["cheek_r"] * H,
             (s * 0.012, -cheek_amt, 0.008)),                                                     # apple of the cheek
            ((s * 0.43 * sx, -0.12 * sy, 0.14), 0.12, (-s * 0.015, 0.0, 0.0)),                    # temple
        ]
        if p["shape"] == "square":
            b.append(((s * 0.36 * sx, -0.12 * sy, -0.33), 0.2, (s * 0.05, -0.02, -0.01)))   # square jaw corner
        else:
            b.append(((s * 0.33 * sx, -0.14 * sy, -0.30), 0.16, (s * 0.012, -0.012, 0.0)))  # soft jaw
        jw = hd.get("jowls", 0.0)
        if jw:   # heavy jowls: the jaw's lower corners hang out and down (Kort)
            b.append(((s * 0.36 * sx, -0.22 * sy, -0.40), 0.15, (s * 0.06 * jw, -0.03 * jw, -0.035 * jw)))
    chin = hd.get("chin", 0.0)
    b += [
        ((0, -0.46 * sy, ez + 0.13), 0.09, (0, -0.02, 0.0)),            # glabella
        ((0, -0.45 * sy, -0.26), 0.15, (0, -0.035 * hd.get("muzzle", 1.0), 0.0)),  # muzzle
        ((0, -0.38 * sy, -0.44), 0.16, (0, -0.07 - chin * 0.5, -0.02 - chin)),     # chin: forward, not receding
        ((0, -0.30 * sy, -0.40), 0.18, (0, -0.03, 0.0)),                           # the front of the jaw
        ((0, 0.25 * sy, 0.2), 0.3, (0, 0.03, 0.02)),                      # occiput
    ]
    return b


def head_point(u, p, br):
    x, y, z = u
    low = core.smoothstep(0.05, -0.8, z)                       # 0 on the cranium -> 1 at the jaw
    n = p["n0"] + (p["n1"] - p["n0"]) * low
    r = (abs(x) ** n + abs(y) ** n + abs(z) ** n) ** (-1.0 / n)
    xs = 1 + p["jaw"] * low - p["taper"] * (low ** 1.6)
    q = Vector((x * r * p["hx"] * xs, y * r * p["hy"], z * r * p["hz"]))
    if q.y < 0:                                                  # flatter face plane
        q.y *= 1 - 0.07 * core.smoothstep(-0.25, -0.47, q.y)
    cut = -0.38 * p["hz"] / 0.53
    if q.z < cut:                                                # flat (square) or round chin bottom
        q.z = cut + (q.z - cut) * p["flat"]
    d = Vector()
    for c, rad, disp in br:
        w = math.exp(-((q - Vector(c)).length_squared) / (rad * rad))
        d += Vector(disp) * w
    return q + d


def _cage_dirs():
    """The spherified cube's vertex directions (12x12 quads per face)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=11, use_grid_fill=True)
    for v in bm.verts:  # spherified cube: even quads, no pole pinch for the subsurf
        x, y, z = v.co
        v.co = Vector((x * math.sqrt(1 - y * y / 2 - z * z / 2 + y * y * z * z / 3),
                       y * math.sqrt(1 - z * z / 2 - x * x / 2 + z * z * x * x / 3),
                       z * math.sqrt(1 - x * x / 2 - y * y / 2 + x * x * y * y / 3))).normalized()
    return bm


def chin_tip(head, z_from=None):
    """The chin as the level camera sees it: the lowest point of the head's front half (a fan of vertical rays under
    the jaw) — the bottom of the silhouette, which is what H_px (chin to crown) is measured to."""
    chin = None
    for k in range(10):
        y = -0.06 - 0.04 * k
        h, _ = core.ray(head, (0, y, -3), (0, 0, 1))
        if h is not None and (chin is None or h.z < chin.z):
            chin = h
    return chin


def build_head(ctx, skin):
    """The cage + Subsurf 2. §7.3 measures the eye line from the REAL chin (a pointed heart chin or a flat square one
    moves it off the nominal -H/2): the evaluated chin tip and crown are measured and the eye line (with every brush
    placed from it) is moved until eye-to-chin / chin-to-crown is the character's value (two passes at most)."""
    p = params(ctx)
    el = ctx.ch["head"].get("eye_line", S["eye_line"])
    head = None
    for it in range(3):
        br = brushes(ctx, p)
        bm = _cage_dirs()
        for v in bm.verts:
            v.co = head_point(v.co, p, br)
        if head is not None:
            bpy.data.objects.remove(head)
        head = core.mesh_obj("head", bm)
        core.finish(head, skin, sub=2)
        core.update()
        chin = chin_tip(head, p["eye_z"] - 0.30)
        top, _ = core.ray(head, (0, 0, 3), (0, 0, -1))
        if chin is None or top is None:
            break
        real = (p["eye_z"] - chin.z) / (top.z - chin.z)
        err = el - real
        if abs(err) < 0.002 or it == 2:
            break
        p["eye_z"] += err * (top.z - chin.z)
    ctx.objs["head"] = head
    ctx.P = p
    ctx.add(head, "skin", None, kind="root", head=True)
    return head


def landmarks(ctx):
    """Ray-cast the evaluated head for the landmarks every other module places from (head-local units)."""
    head = ctx.objs["head"]
    core.update()
    p = ctx.P
    L = ctx.L
    L["eye_z"], L["eye_x"] = p["eye_z"], p["eye_x"]
    top, _ = core.ray(head, (0, 0, 3), (0, 0, -1))
    bot, _ = core.ray(head, (0, -0.15, -3), (0, 0, 1))
    L["crown"] = top
    # the chin: the visible chin tip; H (chin to crown) and the eye line are measured from it (§7.3)
    L["chin"] = chin_tip(head, p["eye_z"] - 0.30) or bot
    for s, tag in ((-1, "near"), (1, "far")):
        h, n = core.ray_front(head, s * p["eye_x"], p["eye_z"])
        L["eye_surf_" + tag] = (h, n)
        hj, _ = core.ray(head, (s * 3, -0.12, -0.33), (-s, 0, 0))
        L["jaw_" + tag] = hj
        he, ne = core.ray(head, (s * 3, 0.03, p["eye_z"] - 0.06), (-s, 0, 0))
        L["ear_" + tag] = (he, ne)
    nose, nn = core.ray_front(head, 0, p["eye_z"] - 0.20 * H)
    L["nose_base"] = (nose, nn)
    L["mouth_z"] = -H / 2 + ctx.ch["mouth"].get("line", 0.235) * H
    mh, mn = core.ray_front(head, 0, L["mouth_z"])
    L["mouth"] = (mh, mn)
    L["face_y"] = mh.y if mh else -0.45
    # the hat ring: 24 points around the head at the hairline height (a plane tilted 12 deg forward-down)
    ring = []
    for k in range(24):
        a = 2 * math.pi * k / 24
        d = Vector((math.sin(a), -math.cos(a), 0.0))
        z = 0.20 + 0.06 * math.cos(a)  # lower at the back... higher at the forehead
        h, _ = core.ray(head, Vector((0, 0, z)) + d * 3, -d)
        if h is not None:
            ring.append(h)
    L["hat_ring"] = ring
    nz = p["eye_z"] - ctx.ch.get("nose", {}).get("drop", 0.20) * H
    nh, _ = core.ray_front(head, 0, nz)
    L["nose_tip_guess"] = nh
    # the cheek apples (the lit-cheek check of §7.4 samples a disc around the near one)
    for s_, tag in ((-1, "near"), (1, "far")):
        cz = p["eye_z"] - S["cheek_below"] * H + cheek_dz(ctx, s_)
        ch_, _ = core.ray_front(head, s_ * S["cheek_x"] * H * (p["hx"] / 0.48) / 0.98, cz)
        L["cheek_" + tag] = ch_
    L["neck_z"] = L["chin"].z - 0.05 if L["chin"] else -0.6
    return L
