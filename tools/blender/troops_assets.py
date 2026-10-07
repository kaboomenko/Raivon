"""Troops by development level (canon §6.1, column «Пехота / Штурм»): «ополченцы с вилами → штурмовики в броне».

Builds and exports to OUT (default game/assets/models):
  squad_dl{1..8}_{blue,red,green}.glb    infantry block of 12 figures, drop-in for squad_<team>.glb
  assault_dl{2..8}_{blue,red,green}.glb  the «Штурм» unit beside it, drop-in for knight_<team>.glb
      dl2 mounted rider · dl3 knight · dl4 dragoon · dl5 armoured car · dl6 WW2 tank ·
      dl7 main battle tank · dl8 hover tank

Run:   python3 tools/blender/troops_assets.py game/assets/models [name or glob, e.g. 'squad_dl3_*' ...]
Sheet: python3 tools/blender/troops_assets.py game/assets/models --sheet OUT.png [--team blue] [--ref]
       [--cols 4] [--dl 1,2,3]
       (one grass hex per DL with squad + assault + banner placed exactly like map_view.gd::_make_army;
        --ref adds the legacy squad_<team> + knight_<team> as a first tile for comparison)

Conventions (same as export_assets.py / evolution_assets.py): Z up, base on Z=0, origin = centre of the
unit's footprint, every figure and vehicle faces −Y in Blender = +Z in Godot (towards the default camera).
Figures are ~0.42 tall (1:6), the squad block spans ≈0.58 × 0.4 like squad_blue; vehicles are ≤0.34 wide.
Everything is joined and baked into one 512 px texture; emissive parts (torches, visors, hover pads) stay
a separate glowing material.
"""
import fnmatch
import math
import os
import random
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kit  # noqa: E402
import export_assets as ea  # noqa: E402  (guarded: importing it builds nothing)
import evolution_assets as ev  # noqa: E402  (guarded as well)
from evolution_assets import (TEAMS, WHITE, GOLD, beam, build_at, bx, cn, cy, extrude, flat, glow,  # noqa: E402
                              mesh_obj, rod, shade, taper_box, tex, uvs)

SKIN = "#e8b48e"
STEEL = "#c3c9d1"
IRON = "#8d9399"
DARK = "#2b2d31"
RUBBER = "#26272a"
LEATHER = "#6b4a2f"
WOODC = "#7a5232"
OLIVE = "#5d6b3c"
KHAKI = "#b3a477"


def mixc(a, b, t):
    """Blend two sRGB hex colours (t = 0 → a, 1 → b)."""
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(pa, pb))


def F(c, rough=0.75):
    return flat("t" + c, c, rough)


def team_glow(team, k=1.15, strength=5.0):
    return glow("team" + team, shade(team, k), strength)


def camo(base, dark, light, scale=9.0):
    """Three-tone world-space blotch camouflage (baked like any procedural colour)."""
    key = ("camo", base, dark, light, scale)
    if key in kit._MATS:
        return kit._MATS[key]
    m = bpy.data.materials.new("camo")
    m.use_nodes = True
    nt = m.node_tree
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 1.5
    nt.links.new(geo.outputs["Position"], nz.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = (*kit.srgb(dark), 1)
    els[1].position = 0.43
    els[1].color = (*kit.srgb(base), 1)
    e = els.new(0.6)
    e.color = (*kit.srgb(light), 1)
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    kit._MATS[key] = m
    return m


def side_prism(profile, w, mt, x=0.0):
    """Prism along X of width w from a (y, z) side profile — hulls seen from the side."""
    n = len(profile)
    verts = [(x - w / 2, y, z) for y, z in profile] + [(x + w / 2, y, z) for y, z in profile]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    return mesh_obj(verts, faces, mt)


def taper_extrude(pts, z0, z1, mt, k=0.8, loc=(0, 0, 0)):
    """Prism from a 2D polygon whose top is scaled by k (sloped turret sides)."""
    n = len(pts)
    verts = [(x, y, z0) for x, y in pts] + [(x * k, y * k, z1) for x, y in pts]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))] + [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    return mesh_obj(verts, faces, mt, loc)


def disc(r, loc, mt, axis="x", n=10, h=0.01):
    """Thin round plate facing ±X (axis 'x') or ±Y (axis 'y')."""
    rot = (0, math.pi / 2, 0) if axis == "x" else (math.pi / 2, 0, 0)
    return cy(r, h, loc, mt, n, rot=rot)


# ====================================================================== FIGURES
# One soldier at the origin facing −Y. Body: legs to 0.17, torso 0.16–0.31, head centre 0.355.
# `seated` lifts the body by SEAT and bends the legs astride a horse (horse back at ≈0.33).

SEAT = 0.2
SH = 0.056  # shoulder half-width


def ring(r, h, loc, mt, n=8, r2=None):
    """Open tube (no caps): belts, skirts, bands — half the triangles of a capped cylinder."""
    r2 = r if r2 is None else r2
    x, y, z = loc
    verts = [(x + r * math.cos(math.tau * k / n), y + r * math.sin(math.tau * k / n), z - h / 2) for k in range(n)]
    verts += [(x + r2 * math.cos(math.tau * k / n), y + r2 * math.sin(math.tau * k / n), z + h / 2) for k in range(n)]
    faces = [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
    o = mesh_obj(verts, faces, mt)
    for p_ in o.data.polygons:
        p_.use_smooth = True
    return o


def _legs(Z, seated, trouser, boot, r=0.017, boot_h=0.03, gaiter=None):
    """Legs (one 5-sided tube each) and boots; `gaiter` = gaiters / puttees / greaves up to the knee."""
    t, b = F(trouser, 0.85), F(boot, 0.8)
    for sx in (-1, 1):
        if seated:
            knee = (sx * 0.068, -0.06, Z + 0.15)
            rod((sx * 0.03, 0, Z + 0.17), knee, r, t, n=5)
            rod(knee, (sx * 0.072, -0.045, Z + 0.035), r * 0.95, F(gaiter, 0.8) if gaiter else t, n=5)
            bx((0.03, 0.05, boot_h), (sx * 0.072, -0.052, Z + 0.015), b, bev=0)
        else:
            rod((sx * 0.022, 0, 0.175), (sx * 0.025, 0, 0.02), r, t, r2=r * 0.9, n=5)
            if gaiter:
                bx((0.03, 0.032, 0.06), (sx * 0.025, -0.001, 0.055), F(gaiter, 0.8), bev=0)
            bx((0.032, 0.05, boot_h), (sx * 0.025, -0.008, boot_h / 2), b, bev=0)


def _torso(Z, c, r0=0.043, r1=0.05, skirt=None, skirt_len=0.07):
    cy(r0, 0.15, (0, 0, Z + 0.235), F(c), 8, r2=r1)
    if skirt:
        ring(0.058, skirt_len, (0, 0, Z + 0.165 - skirt_len / 2 + 0.02), F(skirt), 8, r2=0.046)


def _arm(Z, sx, hand, c, r=0.014):
    rod((sx * SH, 0, Z + 0.295), (hand[0], hand[1], Z + hand[2]), r, F(c), r2=r * 0.85, n=5)


def _head(Z, skin=SKIN):
    uvs(0.033, (0, -0.002, Z + 0.355), F(skin, 0.7), 8, 4)


def _belt(Z, c, z=0.175, r=0.047):
    ring(r, 0.016, (0, 0, Z + z), F(c), 8)


def _vertical(Z, x, y, z0, z1, mt, r=0.0062, n=4):
    rod((x, y, Z + z0), (x, y, Z + z1), r, mt, n=n)


def _round_shield(Z, face, rim, boss=IRON, x=-0.066, y=-0.05, z=0.215, r=0.058):
    disc(r, (x, y + 0.004, Z + z), F(rim), "y", 8, 0.01)
    disc(r * 0.82, (x, y - 0.002, Z + z), F(face), "y", 8, 0.01)
    bx((0.024, 0.012, 0.024), (x, y - 0.008, Z + z), F(boss, 0.4), bev=0, rot=(0, math.pi / 4, 0))


def _kite_shield(Z, team, x=-0.066, y=-0.052, z=0.215):
    c = F(team, 0.7)
    bx((0.072, 0.012, 0.07), (x, y, Z + z + 0.02), c, bev=0)
    t = cn(0.051, 0.07, (x, y, Z + z - 0.05), c, 3)
    t.rotation_euler = (math.pi, 0, math.pi / 2)
    t.scale = (0.7, 0.24, 1)
    w = F(WHITE, 0.6)
    bx((0.012, 0.015, 0.09), (x, y - 0.003, Z + z + 0.0), w, bev=0)
    bx((0.05, 0.015, 0.012), (x, y - 0.003, Z + z + 0.025), w, bev=0)


def figure(dl, team, v=0, seated=False):
    """Infantryman of development level dl (v = variant: weapons, headgear) facing −Y."""
    Z = SEAT if seated else 0.0
    rnd = random.Random(v * 31 + dl)
    if dl == 1:  # militia: tunic, rope belt, straw hat / hood / bare head; pitchfork, torch or axe
        tunic = (team, shade(team, 0.78), mixc(team, "#8a6a44", 0.35))[v % 3]
        _legs(Z, seated, ("#7a5a3a", "#5e4630", "#6d5d48")[v % 3], "#4a3526", gaiter="#9c8662")
        _torso(Z, tunic, skirt=tunic, skirt_len=0.08)
        _belt(Z, "#c9a86a", 0.18, 0.046)
        _head(Z)
        hat = v % 4
        if hat == 0:  # straw hat
            cy(0.062, 0.008, (0, 0, Z + 0.375), F("#e0bf6a", 0.85), 10)
            cy(0.03, 0.04, (0, 0, Z + 0.395), F("#d8b25c", 0.85), 8, r2=0.022)
        elif hat == 1:  # hood
            cy(0.042, 0.075, (0, 0.006, Z + 0.37), F("#7d6a52", 0.9), 8, r2=0.012)
        elif hat == 2:  # cap
            uvs(0.035, (0, 0.002, Z + 0.37), F("#8a3a2a", 0.9), 8, 4, (1, 1, 0.65))
        else:  # hair
            uvs(0.034, (0, 0.004, Z + 0.364), F("#4a3020", 0.9), 8, 4, (1, 1, 0.7))
        wood = F("#8a6038", 0.8)
        kind = ("fork", "fork", "torch", "fork", "axe", "fork")[v % 6]
        hx, hy = 0.066, -0.04
        _arm(Z, 1, (hx, hy, 0.22), tunic)
        if v % 3 == 1:
            _arm(Z, -1, (-0.07, -0.03, 0.43), tunic)  # shaking a fist
            bx((0.022, 0.022, 0.024), (-0.071, -0.03, Z + 0.445), F(SKIN), bev=0)
        else:
            _arm(Z, -1, (-0.06, -0.02, 0.17), tunic)
        if kind == "fork":
            _vertical(Z, hx, hy, 0.05, 0.58, wood)
            iron = F("#7f858c", 0.5)
            bx((0.05, 0.008, 0.009), (hx, hy, Z + 0.585), iron, bev=0)
            for dx in (-0.021, 0.0, 0.021):
                bx((0.007, 0.007, 0.065), (hx + dx, hy, Z + 0.62), iron, bev=0)
        elif kind == "torch":
            _vertical(Z, hx, hy, 0.12, 0.5, wood)
            cy(0.016, 0.03, (hx, hy, Z + 0.5), F("#3a2a1c"), 6)
            cn(0.024, 0.075, (hx, hy, Z + 0.55), glow("fire", "#ff6a10", 4.0), 6)
        else:
            _vertical(Z, hx, hy, 0.12, 0.48, wood)
            bx((0.05, 0.008, 0.045), (hx + 0.02, hy, Z + 0.46), F("#9aa0a6", 0.45), bev=0)
    elif dl == 2:  # spearmen: quilted gambeson, kettle hat, round shield, long spear
        _legs(Z, seated, "#4a3f35", LEATHER, gaiter="#8a7356")
        gam = shade(team, 0.9)
        _torso(Z, gam, 0.046, 0.052, skirt=shade(team, 0.75), skirt_len=0.09)
        _belt(Z, LEATHER, 0.18, 0.05)
        _head(Z)
        iron = F(IRON, 0.45)
        cy(0.056, 0.008, (0, 0, Z + 0.372), iron, 10)
        uvs(0.035, (0, 0, Z + 0.37), iron, 8, 4, (1, 1, 0.75))
        hx, hy = 0.068, -0.045
        _arm(Z, 1, (hx, hy, 0.24), gam)
        _arm(Z, -1, (-0.06, -0.04, 0.22), gam)
        _vertical(Z, hx, hy, 0.03 if not seated else -0.05, 0.7, F("#8a6038", 0.8))
        cn(0.015, 0.06, (hx, hy, Z + 0.73), F(STEEL, 0.35), 5)
        _round_shield(Z, team, "#8a6038")
    elif dl == 3:  # swordsmen: mail, tabard with emblem, nasal helm, kite shield, raised sword
        _legs(Z, seated, "#3a3330", "#4a3322")
        _torso(Z, "#a2a8b0", 0.045, 0.052)
        tab = F(team, 0.7)
        bx((0.074, 0.012, 0.18), (0, -0.047, Z + 0.21), tab, bev=0)
        bx((0.074, 0.012, 0.16), (0, 0.047, Z + 0.22), tab, bev=0)
        bx((0.032, 0.014, 0.032), (0, -0.05, Z + 0.255), F(WHITE, 0.6), bev=0)
        _belt(Z, LEATHER, 0.185, 0.053)
        for sx in (-1, 1):
            uvs(0.026, (sx * 0.054, 0, Z + 0.3), F(STEEL, 0.35), 6, 3, (1, 1, 0.75))
        _head(Z)
        cn(0.038, 0.06, (0, 0.002, Z + 0.39), F(STEEL, 0.35), 8)
        ring(0.039, 0.012, (0, 0.002, Z + 0.364), F(STEEL, 0.35), 8)
        bx((0.008, 0.01, 0.03), (0, -0.035, Z + 0.355), F(STEEL, 0.35), bev=0)
        _arm(Z, 1, (0.08, -0.05, 0.37), "#a2a8b0")
        _arm(Z, -1, (-0.062, -0.04, 0.22), "#a2a8b0")
        beam((0.082, -0.055, Z + 0.39), (0.092, -0.06, Z + 0.56), 0.011, F(STEEL, 0.3))
        bx((0.045, 0.012, 0.01), (0.081, -0.055, Z + 0.385), F(GOLD, 0.4), bev=0)
        _kite_shield(Z, team)
    elif dl == 4:  # musketeers: long coat, white cross belts, tricorn; shouldered musket with bayonet
        coat = team
        _legs(Z, seated, "#ece6d6", "#262222", gaiter="#2e2a2a")
        _torso(Z, coat, 0.045, 0.051, skirt=shade(team, 0.82), skirt_len=0.12)
        w = F(WHITE, 0.6)
        for s in (-1, 1):
            b = bx((0.012, 0.012, 0.15), (0, -0.046, Z + 0.24), w, bev=0)
            b.rotation_euler.y = s * 0.55
        _belt(Z, WHITE, 0.175, 0.049)
        _head(Z)
        o = extrude(ev.ngon(0.064, 3, -math.pi / 2), 0, 0.024, F("#1f1c1c", 0.8))
        o.location = (0, 0.008, Z + 0.375)
        o = extrude(ev.ngon(0.067, 3, -math.pi / 2), 0, 0.006, F(GOLD, 0.5))
        o.location = (0, 0.008, Z + 0.372)
        cy(0.031, 0.03, (0, 0.006, Z + 0.4), F("#1f1c1c", 0.8), 8, r2=0.027)
        if v % 12 == 9 and not seated:  # standard-bearer
            _arm(Z, 1, (0.06, -0.04, 0.3), coat)
            _arm(Z, -1, (-0.04, -0.05, 0.25), coat)
            _vertical(Z, 0.06, -0.04, 0.05, 0.8, F("#d9d2c3", 0.5))
            bx((0.15, 0.008, 0.1), (0.135, -0.04, Z + 0.74), F(team, 0.7), bev=0)
            bx((0.05, 0.011, 0.05), (0.135, -0.04, Z + 0.74), F(WHITE, 0.6), bev=0)
            uvs(0.012, (0.06, -0.04, Z + 0.81), F(GOLD, 0.4), 6, 4)
        else:
            _arm(Z, 1, (0.066, -0.035, 0.2), coat)
            _arm(Z, -1, (-0.06, -0.02, 0.17), coat)
            rod((0.068, -0.036, Z + 0.1), (0.074, -0.01, Z + 0.4), 0.008, F("#6b4226", 0.8), n=4)
            rod((0.074, -0.01, Z + 0.4), (0.077, 0.002, Z + 0.56), 0.005, F(IRON, 0.4), n=4)
            rod((0.077, 0.002, Z + 0.56), (0.079, 0.008, Z + 0.63), 0.004, F(STEEL, 0.3), r2=0.0005, n=4)
    elif dl == 5:  # riflemen: tunic, peaked cap, puttees, leather webbing, pack; shouldered rifle
        tun = shade(team, 0.82)
        _legs(Z, seated, shade(team, 0.5), "#3d2b1e", gaiter=KHAKI)
        _torso(Z, tun, 0.044, 0.05, skirt=tun, skirt_len=0.05)
        _belt(Z, LEATHER, 0.18, 0.048)
        for s in (-1, 1):
            b = bx((0.01, 0.012, 0.13), (s * 0.022, -0.046, Z + 0.25), F(LEATHER), bev=0)
            b.rotation_euler.y = s * 0.12
        if not seated:
            bx((0.075, 0.035, 0.08), (0, 0.06, Z + 0.25), F("#6d6450", 0.85), bev=0)
            cy(0.016, 0.085, (0, 0.06, Z + 0.3), F("#8b7f63"), 6, rot=(0, math.pi / 2, 0))
        _head(Z)
        cap = F(shade(team, 0.7), 0.7)
        cy(0.034, 0.03, (0, 0.004, Z + 0.385), cap, 8, r2=0.041)
        ring(0.035, 0.01, (0, 0.004, Z + 0.374), F("#1d1b1a"), 8)
        bx((0.05, 0.03, 0.006), (0, -0.034, Z + 0.374), F("#1d1b1a", 0.4), bev=0, rot=(0.25, 0, 0))
        bx((0.012, 0.004, 0.012), (0, -0.04, Z + 0.39), F(GOLD, 0.4), bev=0)
        _arm(Z, 1, (0.066, -0.035, 0.2), tun)
        _arm(Z, -1, (-0.06, -0.02, 0.17), tun)
        rod((0.068, -0.036, Z + 0.1), (0.074, -0.012, Z + 0.37), 0.008, F("#5a3a22", 0.8), n=4)
        rod((0.074, -0.012, Z + 0.37), (0.076, -0.004, Z + 0.47), 0.0045, F(DARK, 0.4), n=4)
        rod((0.076, -0.004, Z + 0.47), (0.078, 0.002, Z + 0.55), 0.004, F(STEEL, 0.3), r2=0.0005, n=4)
    elif dl == 6:  # WW2 infantry: steel helmet, webbing, pack; rifle at port arms (diagonal)
        jac = shade(team, 0.78)
        _legs(Z, seated, "#55584a", "#2a2522", gaiter="#8f8566")
        _torso(Z, jac, 0.045, 0.05, skirt=jac, skirt_len=0.05)
        web = F(KHAKI, 0.8)
        _belt(Z, KHAKI, 0.18, 0.049)
        for s in (-1, 1):
            bx((0.009, 0.1, 0.012), (s * 0.03, 0, Z + 0.3), web, bev=0)
            bx((0.02, 0.012, 0.022), (s * 0.03, -0.048, Z + 0.185), web, bev=0)
        if not seated:
            bx((0.07, 0.035, 0.075), (0, 0.06, Z + 0.25), F("#5b6040"), bev=0)
            cy(0.015, 0.08, (0, 0.06, Z + 0.3), F("#6f6a4e"), 6, rot=(0, math.pi / 2, 0))
        _head(Z)
        hel = F(OLIVE, 0.6)
        uvs(0.041, (0, 0.002, Z + 0.37), hel, 8, 4, (1, 1.05, 0.62))
        cy(0.047, 0.006, (0, 0.002, Z + 0.37), hel, 8)
        if v % 6 == 4:  # radio operator
            bx((0.065, 0.04, 0.09), (0, 0.065, Z + 0.26), F("#4a4e38"), bev=0)
            _vertical(Z, 0.02, 0.07, 0.3, 0.62, F(DARK), 0.003, 4)
        _arm(Z, 1, (0.045, -0.07, 0.2), jac)
        _arm(Z, -1, (-0.035, -0.075, 0.3), jac)
        beam((0.06, -0.075, Z + 0.15), (-0.03, -0.08, Z + 0.33), 0.013, F("#6b4226", 0.8))
        beam((-0.03, -0.08, Z + 0.33), (-0.075, -0.082, Z + 0.43), 0.008, F(DARK, 0.4))
    elif dl == 7:  # modern motorised infantry: fatigues, plate carrier, helmet + NVG, carbine at low ready
        fat = shade(team, 0.72)
        _legs(Z, seated, shade(team, 0.55), "#2b2622", gaiter=shade(team, 0.55))
        for sx in (-1, 1):  # knee pads
            if not seated:
                bx((0.028, 0.012, 0.03), (sx * 0.024, -0.016, 0.095), F("#24272b"), bev=0)
        _torso(Z, fat, 0.044, 0.049)
        vest = F("#34383d", 0.8)
        bx((0.1, 0.104, 0.1), (0, 0, Z + 0.25), vest, bev=0)
        for dx in (-0.028, 0.0, 0.028):
            bx((0.022, 0.016, 0.03), (dx, -0.056, Z + 0.225), F("#2a2d31"), bev=0)
        bx((0.02, 0.012, 0.02), (0.05, -0.012, Z + 0.285), F(team, 0.7), bev=0)  # shoulder patch
        bx((0.02, 0.012, 0.02), (-0.05, -0.012, Z + 0.285), F(team, 0.7), bev=0)
        if not seated:
            bx((0.065, 0.03, 0.07), (0, 0.065, Z + 0.24), F("#3b3f36"), bev=0)
        _head(Z, "#d9a07a")
        hel = F("#3c4046", 0.6)
        uvs(0.04, (0, 0.003, Z + 0.37), hel, 8, 4, (1, 1.05, 0.78))
        bx((0.03, 0.02, 0.018), (0, -0.036, Z + 0.395), F("#1c1d20", 0.4), bev=0)  # NVG mount
        bx((0.05, 0.012, 0.012), (0, -0.032, Z + 0.355), F("#1c1d20", 0.3), bev=0)  # glasses
        _arm(Z, 1, (0.05, -0.07, 0.2), fat)
        _arm(Z, -1, (-0.02, -0.08, 0.26), fat)
        gun = F("#232529", 0.5)
        beam((0.07, -0.07, Z + 0.21), (-0.04, -0.085, Z + 0.3), 0.016, gun)
        beam((-0.04, -0.085, Z + 0.3), (-0.07, -0.088, Z + 0.33), 0.007, gun)
        bx((0.012, 0.014, 0.035), (0.0, -0.08, Z + 0.235), gun, bev=0, rot=(0, -0.65, 0))
        bx((0.03, 0.012, 0.012), (0.02, -0.08, Z + 0.287), F("#141516"), bev=0, rot=(0, -0.7, 0))
    else:  # dl 8 power armour: white plates, team plates, glowing visor, heavy energy rifle
        plate = F("#dfe3e8", 0.45)
        joint = F("#2e333a", 0.6)
        tm = F(team, 0.5)
        if seated:
            _legs(Z, True, "#2e333a", "#dfe3e8", 0.022, 0.04)
        else:
            for sx in (-1, 1):
                rod((sx * 0.026, 0, 0.18), (sx * 0.03, 0, 0.1), 0.023, joint, n=6)
                bx((0.04, 0.045, 0.06), (sx * 0.03, -0.005, 0.075), plate, bev=0)
                bx((0.042, 0.06, 0.03), (sx * 0.03, -0.01, 0.015), joint, bev=0)
        bx((0.1, 0.075, 0.07), (0, 0, Z + 0.17), joint, bev=0)
        bx((0.12, 0.09, 0.13), (0, 0, Z + 0.265), tm, bev=0.018)
        bx((0.07, 0.012, 0.07), (0, -0.046, Z + 0.27), plate, bev=0)
        bx((0.022, 0.014, 0.022), (0, -0.052, Z + 0.28), team_glow(team), bev=0, rot=(0, math.pi / 4, 0))  # core
        bx((0.07, 0.03, 0.08), (0, 0.06, Z + 0.27), joint, bev=0)  # power pack
        for sx in (-1, 1):
            cy(0.012, 0.012, (sx * 0.02, 0.078, Z + 0.25), team_glow(team), 6, rot=(math.pi / 2, 0, 0))
            bx((0.05, 0.06, 0.04), (sx * 0.075, 0, Z + 0.33), tm, bev=0, rot=(0, sx * 0.3, 0))
        bx((0.066, 0.07, 0.065), (0, 0, Z + 0.375), plate, bev=0.016)
        bx((0.06, 0.016, 0.022), (0, -0.035, Z + 0.382), team_glow(team), bev=0)
        bx((0.012, 0.04, 0.02), (0, 0.006, Z + 0.415), tm, bev=0)  # crest
        rod((SH + 0.02, 0, Z + 0.3), (0.06, -0.07, Z + 0.21), 0.02, joint, n=6)
        rod((-SH - 0.02, 0, Z + 0.3), (-0.03, -0.085, Z + 0.25), 0.02, joint, n=6)
        g = F("#3a3f47", 0.5)
        beam((0.075, -0.08, Z + 0.2), (-0.06, -0.095, Z + 0.3), 0.03, g)
        beam((-0.06, -0.095, Z + 0.3), (-0.1, -0.1, Z + 0.33), 0.012, g)
        beam((0.05, -0.097, Z + 0.22), (-0.04, -0.11, Z + 0.287), 0.008, team_glow(team))


# ---------------------------------------------------------------------- formations

ROWS = [(-0.2 + i * 0.13 + (0.06 if j % 2 else 0), -0.12 + j * 0.13) for j in range(3) for i in range(4)]


def squad(dl, team):
    """12 figures in the 4×3 block of squad_<team> (x ≈ −0.26…0.32, y ≈ −0.17…0.17)."""
    rnd = random.Random(dl * 7)
    for k, (x, y) in enumerate(ROWS):
        jit = {1: 0.025, 2: 0.008, 3: 0.008, 6: 0.012, 7: 0.02}.get(dl, 0.0)
        yaw = {1: 0.45, 6: 0.15, 7: 0.3}.get(dl, 0.06)
        dx, dy = rnd.uniform(-jit, jit), rnd.uniform(-jit, jit)
        rz = rnd.uniform(-yaw, yaw)
        s = 0.95 * (rnd.uniform(0.92, 1.04) if dl == 1 else 1.0) * (1.06 if dl == 8 else 1.0)
        v = k if dl != 4 else (9 if k == 9 else k % 9)
        build_at(lambda d=dl, vv=v: figure(d, team, vv), x + dx, y + dy, rz, s)


# ====================================================================== ASSAULT UNITS


def horse(coat, mane, sock=None, saddle=None):
    """Horse facing −Y: back at z≈0.335, body y −0.17…0.17, head to y≈−0.33, height ≈0.5. A rounded barrel with
    chest and rump, an arched neck, a wedge head with a darker muzzle, eyes and a bridle, tapered legs with
    knees and hooves, a mane crest and a full tail — so it reads as a horse at map zoom, not a box."""
    c, mn = F(coat, 0.75), F(mane, 0.85)
    dark = F(mixc(coat, "#1a1410", 0.45), 0.8)
    leather = F("#3a2516", 0.7)
    # barrel, chest and rump
    bx((0.11, 0.26, 0.12), (0, 0, 0.27), c, bev=0.05)
    uvs(0.075, (0, -0.12, 0.285), c, 12, 8, (0.85, 1.0, 1.0))
    uvs(0.078, (0, 0.12, 0.29), c, 12, 8, (0.9, 1.0, 0.95))
    # arched neck and head
    beam((0, -0.13, 0.31), (0, -0.2, 0.44), 0.082, c, 0.025)
    uvs(0.045, (0, -0.205, 0.45), c, 10, 6)
    beam((0, -0.2, 0.455), (0, -0.305, 0.39), 0.058, c, 0.022)
    beam((0, -0.29, 0.4), (0, -0.335, 0.37), 0.048, dark, 0.016)  # muzzle
    for sx in (-1, 1):
        uvs(0.009, (sx * 0.03, -0.235, 0.452), F("#141010", 0.3), 6, 4)  # eyes
        cn(0.012, 0.042, (sx * 0.018, -0.19, 0.495), c, 4)  # ears
        rod((sx * 0.031, -0.2, 0.448), (sx * 0.027, -0.318, 0.385), 0.0045, leather, n=4)  # cheek strap
    rod((-0.032, -0.322, 0.382), (0.032, -0.322, 0.382), 0.005, leather, n=4)  # noseband
    if saddle:
        for sx in (-1, 1):  # reins back to the rider
            rod((sx * 0.03, -0.32, 0.38), (sx * 0.04, -0.05, 0.4), 0.0035, leather, n=4)
    # mane: a crest of tufts along the neck
    for k in range(5):
        t = k / 4.0
        cn(0.02, 0.05, (0, -0.11 - 0.08 * t, 0.37 + 0.11 * t), mn, 4, rot=(math.radians(-35), 0, 0))
    cn(0.018, 0.045, (0, -0.215, 0.49), mn, 4, rot=(math.radians(-70), 0, 0))  # forelock
    # legs: forearm/gaskin tapering to the knee, cannon to the hoof
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 0.036, sy * 0.115
            rod((x, y, 0.25), (x, y - 0.006, 0.13), 0.022 if sy > 0 else 0.02, c, r2=0.014, n=6)
            uvs(0.0155, (x, y - 0.006, 0.125), c, 6, 4)
            rod((x, y - 0.006, 0.125), (x, y - 0.012, 0.03), 0.012, c, n=6)
            cy(0.018, 0.024, (x, y - 0.012, 0.012), F(sock or mane), 6)
    # tail: three strands fanned
    for k, ox in enumerate((-0.012, 0.0, 0.012)):
        rod((ox * 0.5, 0.17, 0.32), (ox * 2.2, 0.24 + 0.01 * (k == 1), 0.12), 0.024 if k == 1 else 0.017, mn, r2=0.008, n=5)
    if saddle:
        bx((0.125, 0.12, 0.02), (0, 0.005, 0.338), F(saddle, 0.7), bev=0)


def assault_dl2(team):
    """Mounted rider: bay horse, team saddle cloth, spearman in gambeson with round shield."""
    horse("#7a5235", "#2a1d14", "#e8e0d0")
    tc = F(team, 0.7)
    bx((0.13, 0.15, 0.09), (0, 0.01, 0.3), tc, bev=0.01)
    bx((0.132, 0.05, 0.05), (0, 0.01, 0.3), F(WHITE, 0.6), bev=0)
    figure(2, team, 0, seated=True)


def assault_dl3(team):
    """Knight: grey destrier in a team caparison with emblem, chanfron, great helm, lance with pennant."""
    horse("#d4d0c8", "#6d6a66", "#3a3634")
    tc = F(team, 0.7)
    taper_box((0.155, 0.37, 0.19), (0, 0.0, 0.235), tc, (0.82, 0.92))
    for sx in (-1, 1):
        bx((0.006, 0.07, 0.07), (sx * 0.072, 0.01, 0.25), F(WHITE, 0.6), bev=0)
        bx((0.006, 0.02, 0.07), (sx * 0.072, 0.01, 0.25), F(GOLD, 0.4), bev=0)
    beam((0, -0.19, 0.452), (0, -0.305, 0.392), 0.068, F(STEEL, 0.35))  # chanfron
    Z = SEAT
    _legs(Z, True, "#a2a8b0", "#8d939a", gaiter="#a2a8b0")
    _torso(Z, "#b3b9c1", 0.046, 0.054)
    bx((0.08, 0.012, 0.15), (0, -0.05, Z + 0.23), tc, bev=0)
    bx((0.034, 0.014, 0.034), (0, -0.053, Z + 0.26), F(WHITE, 0.6), bev=0)
    for sx in (-1, 1):
        uvs(0.028, (sx * 0.056, 0, Z + 0.3), F(STEEL, 0.35), 6, 4, (1, 1, 0.75))
    cy(0.037, 0.07, (0, 0, Z + 0.36), F(STEEL, 0.35), 8)  # great helm
    bx((0.05, 0.008, 0.008), (0, -0.037, Z + 0.365), F("#1d1b1a"), bev=0)
    cn(0.022, 0.05, (0, 0.0, Z + 0.42), tc, 6)  # plume
    _arm(Z, 1, (0.07, -0.06, 0.22), "#b3b9c1")
    _arm(Z, -1, (-0.06, -0.04, 0.24), "#b3b9c1")
    _kite_shield(Z, team, -0.075, -0.05, 0.22)
    rod((0.072, 0.06, Z + 0.06), (0.072, -0.08, Z + 0.62), 0.008, F("#d9d2c3", 0.6), n=5)
    cn(0.014, 0.06, (0.072, -0.085, Z + 0.66), F(STEEL, 0.3), 5).rotation_euler.x = 0.24
    bx((0.006, 0.09, 0.05), (0.072, -0.03, Z + 0.58), tc, bev=0, rot=(0.24, 0, 0))  # pennant


def assault_dl4(team):
    """Dragoon: dark horse with team shabraque, rider in coat with brass crested helmet and raised sabre."""
    horse("#4a3326", "#1d1612", "#d9d2c3")
    tc = F(team, 0.7)
    bx((0.132, 0.18, 0.1), (0, 0.02, 0.3), tc, bev=0.01)
    bx((0.135, 0.17, 0.012), (0, 0.02, 0.255), F(GOLD, 0.5), bev=0)
    Z = SEAT
    _legs(Z, True, "#ece6d6", "#1f1c1c", gaiter="#262222")
    _torso(Z, team, 0.045, 0.051)
    w = F(WHITE, 0.6)
    for s in (-1, 1):
        b = bx((0.012, 0.012, 0.15), (0, -0.046, Z + 0.24), w, bev=0)
        b.rotation_euler.y = s * 0.55
    _belt(Z, WHITE, 0.175, 0.049)
    _head(Z)
    brass = F("#d6a640", 0.4)
    uvs(0.037, (0, 0.002, Z + 0.375), brass, 8, 4, (1, 1.05, 0.9))
    cy(0.042, 0.008, (0, 0.002, Z + 0.36), brass, 10)
    beam((0, -0.03, Z + 0.4), (0, 0.06, Z + 0.37), 0.022, F("#1a1414", 0.9))  # horsehair crest
    rod((0, 0.04, Z + 0.38), (0, 0.07, Z + 0.28), 0.012, F("#1a1414", 0.9), r2=0.004, n=4)
    _arm(Z, 1, (0.075, -0.05, 0.4), team)
    _arm(Z, -1, (-0.06, -0.06, 0.2), team)
    beam((0.078, -0.055, Z + 0.41), (0.1, -0.1, Z + 0.58), 0.01, F(STEEL, 0.3))  # sabre
    bx((0.03, 0.012, 0.012), (0.078, -0.055, Z + 0.405), F(GOLD, 0.4), bev=0)
    rod((-0.07, 0.04, Z + 0.07), (-0.08, -0.02, Z + 0.36), 0.008, F("#6b4226", 0.8), n=5)  # carbine
    cy(0.02, 0.07, (0.08, 0.11, Z + 0.1), F("#d6a640", 0.4), 6, rot=(0.3, 0, 0))  # holster


def assault_dl5(team):
    """Armoured car (c. 1914): bonnet in front, riveted body, round MG turret, spoked wheels."""
    body = F(mixc(team, "#5f6650", 0.5), 0.7)
    dk = F("#2b2d2f")
    bx((0.17, 0.42, 0.035), (0, 0, 0.085), dk, bev=0)
    bx((0.21, 0.24, 0.13), (0, 0.07, 0.17), body, bev=0.012)
    o = taper_box((0.17, 0.17, 0.095), (0, -0.13, 0.145), body, (0.82, 0.86), bev=0.01)
    o.location.z = 0.1475
    bx((0.12, 0.012, 0.07), (0, -0.218, 0.14), F("#4a4c4e", 0.5), bev=0)
    for sx in (-1, 1):
        cy(0.015, 0.02, (sx * 0.06, -0.22, 0.2), glow("lamp", "#ffe2a0", 3.0), 6, rot=(math.pi / 2, 0, 0))
        bx((0.04, 0.12, 0.012), (sx * 0.1, -0.15, 0.125), dk, bev=0)  # mudguard
        for sy in (-0.14, 0.15):
            disc(0.058, (sx * 0.1, sy, 0.058), F(RUBBER, 0.9), "x", 10, 0.038)
            disc(0.034, (sx * 0.122, sy, 0.058), F("#8a8c86", 0.6), "x", 8, 0.006)
        bx((0.006, 0.08, 0.04), (sx * 0.107, 0.06, 0.18), F("#22252a"), bev=0)  # vision slit plate
    bx((0.214, 0.244, 0.025), (0, 0.07, 0.205), F(team, 0.7), bev=0)  # team band
    cy(0.072, 0.075, (0, 0.06, 0.27), body, 10, r2=0.064)
    cy(0.066, 0.012, (0, 0.06, 0.312), dk, 10)
    for sx in (-1, 1):
        disc(0.026, (sx * 0.069, 0.06, 0.27), F(WHITE, 0.6), "x", 10, 0.006)
        disc(0.015, (sx * 0.072, 0.06, 0.27), F(team, 0.7), "x", 8, 0.006)
    rod((0, 0.0, 0.27), (0, -0.09, 0.27), 0.016, F("#41443f", 0.5), n=6)  # water jacket
    rod((0, -0.09, 0.27), (0, -0.14, 0.27), 0.006, dk, n=5)
    rod((0.07, 0.17, 0.2), (0.07, 0.19, 0.48), 0.004, dk, n=4)
    bx((0.07, 0.006, 0.045), (0.105, 0.19, 0.455), F(team, 0.7), bev=0)


def tracks(L, x, w=0.07, h=0.09, wheels=5, r=0.03, mt_track=None, mt_wheel=None, skirt=None):
    tr = mt_track or F("#3a3631", 0.85)
    for sx in (-1, 1):
        bx((w, L, h), (sx * x, 0, h / 2 + 0.005), tr, bev=0.025)
        if skirt:
            bx((0.012, L * 0.86, h * 0.62), (sx * (x + w / 2 + 0.004), -0.01, h * 0.72), skirt, bev=0)
            continue
        for i in range(wheels):
            y = -L / 2 + 0.06 + i * (L - 0.12) / (wheels - 1)
            disc(r, (sx * (x + w / 2 + 0.002), y, r + 0.012), mt_wheel or F("#5a5c55", 0.7), "x", 8, 0.012)


def assault_dl6(team):
    """WW2 medium tank: sloped glacis, cast round turret, short-ish gun, team stars and pennant."""
    body = camo(mixc(team, "#5d6b3c", 0.55), mixc(team, "#2f3622", 0.6), mixc(team, "#7d7b56", 0.55), 7.0)
    tracks(0.46, 0.105, 0.07, 0.09, 5, 0.032)
    side_prism([(-0.235, 0.075), (-0.24, 0.1), (-0.13, 0.18), (0.2, 0.18), (0.235, 0.14), (0.235, 0.075)], 0.28, body)
    for sx in (-1, 1):
        bx((0.012, 0.12, 0.012), (sx * 0.04, -0.17, 0.155), F("#3a3631"), bev=0, rot=(-0.6, 0, 0))  # spare tracks
    cy(0.012, 0.03, (0.08, 0.17, 0.2), F("#2b2d2f"), 6)  # exhaust
    cy(0.1, 0.085, (0, 0.03, 0.222), body, 12, r2=0.084)
    cy(0.035, 0.03, (0.04, 0.06, 0.278), body, 8)  # cupola
    bx((0.09, 0.03, 0.06), (0, -0.075, 0.22), body, bev=0.008)  # mantlet
    rod((0, -0.09, 0.22), (0, -0.34, 0.22), 0.012, F("#3b3e36", 0.6), n=8)
    cy(0.017, 0.035, (0, -0.33, 0.22), F("#2f322c"), 8, rot=(math.pi / 2, 0, 0))
    ring(0.098, 0.02, (0, 0.03, 0.205), F(team, 0.7), 12, r2=0.0955)  # team band round the turret
    for sx in (-1, 1):
        a0 = math.pi if sx > 0 else 0.0
        o = extrude([((0.032 if k % 2 == 0 else 0.013) * math.cos(a0 + k * math.pi / 5),
                      (0.032 if k % 2 == 0 else 0.013) * math.sin(a0 + k * math.pi / 5)) for k in range(10)],
                    0, 0.004, F(WHITE, 0.6))
        o.rotation_euler = (0, math.pi / 2 * sx, 0)
        o.location = (sx * 0.142, 0.04, 0.135)
    rod((-0.06, 0.08, 0.26), (-0.06, 0.08, 0.6), 0.003, F(DARK), n=4)
    bx((0.075, 0.005, 0.045), (-0.0225, 0.08, 0.575), F(team, 0.7), bev=0)


def assault_dl7(team):
    """Main battle tank: long flat hull, angular wedge turret, long smoothbore with thermal sleeve, skirts."""
    body = camo(mixc(team, "#6b6f5a", 0.5), mixc(team, "#2c3026", 0.6), mixc(team, "#a09a7a", 0.5), 6.0)
    sk = body
    tracks(0.48, 0.11, 0.065, 0.08, 6, 0.03, skirt=sk)
    side_prism([(-0.25, 0.07), (-0.25, 0.095), (-0.17, 0.15), (0.24, 0.155), (0.255, 0.12), (0.255, 0.07)], 0.29, body)
    tpts = [(-0.055, -0.16), (0.055, -0.16), (0.12, -0.06), (0.118, 0.12), (0.075, 0.17), (-0.075, 0.17), (-0.118, 0.12), (-0.12, -0.06)]
    tur = camo(mixc(team, "#55594a", 0.5), mixc(team, "#262a20", 0.6), mixc(team, "#8c8668", 0.5), 6.0)
    cy(0.1, 0.02, (0, 0.03, 0.16), F("#24262a"), 10)  # turret ring
    taper_extrude(tpts, 0, 0.085, tur, 0.84, (0, 0.03, 0.165))
    rod((0, -0.12, 0.21), (0, -0.44, 0.21), 0.0115, F("#3c3f37", 0.6), n=8)
    cy(0.017, 0.07, (0, -0.21, 0.21), F("#3c3f37", 0.6), 8, rot=(math.pi / 2, 0, 0))  # sleeve
    cy(0.018, 0.04, (0, -0.33, 0.21), F("#30332c"), 8, rot=(math.pi / 2, 0, 0))  # fume extractor
    bx((0.04, 0.05, 0.04), (0.075, -0.02, 0.262), F("#30332c"), bev=0.006)  # commander's sight
    disc(0.012, (0.075, -0.046, 0.265), glow("optic", "#7cf0ff", 2.5), "y", 6, 0.004)
    rod((-0.07, 0.0, 0.27), (-0.07, -0.08, 0.27), 0.005, F(DARK), n=4)  # roof MG
    bx((0.02, 0.04, 0.025), (-0.07, 0.01, 0.26), F(DARK), bev=0)
    for sx in (-1, 1):
        for k in range(3):
            rod((sx * 0.11, -0.04 + k * 0.025, 0.215), (sx * 0.135, -0.06 + k * 0.025, 0.23), 0.008, F("#30332c"), n=5)
        bx((0.006, 0.12, 0.03), (sx * 0.121, 0.06, 0.205), F(team, 0.7), bev=0)  # team band
        bx((0.006, 0.18, 0.02), (sx * 0.152, 0.0, 0.11), F(team, 0.7), bev=0)
    rod((0.07, 0.15, 0.24), (0.07, 0.15, 0.58), 0.003, F(DARK), n=4)
    bx((0.07, 0.005, 0.04), (0.105, 0.15, 0.56), F(team, 0.7), bev=0)


def assault_dl8(team):
    """Heavy hover tank: white wedge on team nacelles floating over glowing pads, twin rail cannon, light strips."""
    plate = F("#d6dbe2", 0.45)
    dk = F("#2c3139", 0.55)
    gl = team_glow(team)
    H = 0.09  # hover gap
    for sx in (-1, 1):
        for sy in (-1, 1):
            cy(0.042, 0.03, (sx * 0.12, sy * 0.15, H - 0.005), dk, 8)
            cy(0.034, 0.012, (sx * 0.12, sy * 0.15, H - 0.026), gl, 8)
    side_prism([(-0.25, H + 0.035), (-0.19, H), (0.21, H), (0.25, H + 0.03), (0.24, H + 0.085), (-0.08, H + 0.11),
                (-0.2, H + 0.075)], 0.2, plate)
    for sx in (-1, 1):  # side nacelles
        side_prism([(-0.22, H + 0.005), (0.23, H), (0.245, H + 0.065), (-0.15, H + 0.07)], 0.06, F(team, 0.5), sx * 0.125)
        bx((0.006, 0.34, 0.014), (sx * 0.157, 0.0, H + 0.035), gl, bev=0)
        bx((0.04, 0.012, 0.03), (sx * 0.125, 0.244, H + 0.035), gl, bev=0)  # thrusters
    tpts = [(-0.045, -0.15), (0.045, -0.15), (0.1, -0.05), (0.1, 0.09), (0.055, 0.13), (-0.055, 0.13), (-0.1, 0.09), (-0.1, -0.05)]
    taper_extrude(tpts, 0, 0.065, dk, 0.72, (0, 0.03, H + 0.1))
    taper_extrude([(x * 0.6, y * 0.6) for x, y in tpts], 0, 0.012, plate, 0.85, (0, 0.04, H + 0.165))
    o = cy(0.17, 0.004, (0, 0, 0.004), glow("underglow" + team, team, 1.2), 12)
    o.scale = (0.9, 1.45, 1)
    bx((0.1, 0.01, 0.012), (0, -0.115, H + 0.135), gl, bev=0)  # sensor strip
    for sx in (-1, 1):
        bx((0.02, 0.28, 0.024), (sx * 0.028, -0.24, H + 0.13), plate, bev=0)
        bx((0.006, 0.26, 0.008), (sx * 0.028, -0.24, H + 0.145), gl, bev=0)
        for k in range(3):
            bx((0.03, 0.012, 0.032), (sx * 0.028, -0.2 - k * 0.06, H + 0.13), F(team, 0.5), bev=0)
    bx((0.034, 0.03, 0.05), (-0.06, 0.1, H + 0.19), dk, bev=0)  # sensor mast
    cy(0.012, 0.012, (-0.06, 0.1, H + 0.222), gl, 6)


ASSAULT = {2: assault_dl2, 3: assault_dl3, 4: assault_dl4, 5: assault_dl5, 6: assault_dl6, 7: assault_dl7, 8: assault_dl8}

ASSETS = {}
for _n in range(1, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"squad_dl{_n}_{_t}"] = (lambda n, c: (lambda: squad(n, c)))(_n, _c)
for _n in range(2, 9):
    for _t, _c in TEAMS.items():
        ASSETS[f"assault_dl{_n}_{_t}"] = (lambda n, c: (lambda: ASSAULT[n](c)))(_n, _c)


def export(name, out):
    """evolution_assets.export (lowpoly, 512 px bake, glTF) with the mesh origin moved to the model origin."""
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    ev.lowpoly(objs)
    ob = ea.bake_asset(objs, 512)
    ob.name = name
    ob.data.transform(ob.matrix_world)
    ob.matrix_world = Matrix.Identity(4)
    ob.data.calc_loop_triangles()
    tris = len(ob.data.loop_triangles)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    path = os.path.join(out, f"{name}.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True, export_yup=True)
    vs = [v.co for v in ob.data.vertices]
    print(f"EXPORTED {name}: tris={tris} x={min(v.x for v in vs):.2f}..{max(v.x for v in vs):.2f} "
          f"y={min(v.y for v in vs):.2f}..{max(v.y for v in vs):.2f} height={max(v.z for v in vs):.2f} "
          f"mats={[m_.name for m_ in ob.data.materials]}", flush=True)
    return tris


# ====================================================================== contact sheet


def troops_sheet(model_dir, png, team="blue", ref=False, res=2400, cols=4, only=None):
    """One grass hex per DL: squad + assault + banner exactly as map_view.gd::_make_army places them."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit._MATS.clear()
    grass = kit.noisy_mat("grass", "#4f9a2c", "#72bf3d", 4.0)
    dirt = kit.noisy_mat("dirt", "#6d4a2c", "#8a5e36", 6.0)
    tiles = []
    if ref:
        tiles.append([("squad_" + team, (-0.15, 0.05), 1.15), ("knight_" + team, (0.32, 0.25), 1.25)])
    for n in (only or range(1, 9)):
        t = [(f"squad_dl{n}_{team}", (-0.15, 0.05), 1.15)]
        if n >= 2:
            t.append((f"assault_dl{n}_{team}", (0.32, 0.25), 1.25))
        tiles.append(t)
    sp = 1.75
    nrows = (len(tiles) + cols - 1) // cols
    for k, t in enumerate(tiles):
        r, c = divmod(k, cols)
        x = (c - (cols - 1) / 2) * sp
        y = -r * sp * 1.12
        kit.hex_prism("tile", (x, y, 0), 0.85, 0.18, grass, dirt, 0.03)
        for name, (gx, gz), s in t + [("banner_" + team, (0.05, -0.35), 0.9)]:
            before = {o.name for o in bpy.context.scene.objects}
            bpy.ops.import_scene.gltf(filepath=os.path.join(model_dir, name + ".glb"))
            for o in bpy.context.scene.objects:
                if o.name not in before and o.parent is None:
                    # Godot (x, z) → Blender (x, −y); scale about the model origin like the Node3D parent does
                    o.matrix_world = Matrix.Translation((x + gx, y - gz, 0)) @ Matrix.Scale(s, 4) @ o.matrix_world
    world = bpy.data.worlds.new("w")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*kit.srgb("#8fa3b5"), 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.active_object
    sun.data.energy = 3.5
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(42), math.radians(-12), math.radians(-35))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    bpy.context.scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = cols * sp + 0.1
    el = math.radians(46)  # the game camera pitch is 40–52°
    se, ce = math.sin(el), math.cos(el)
    v_top = 0.4 * se + 1.0 * ce  # banner tops of the back row
    v_bot = (-(nrows - 1) * sp * 1.12 - 0.76) * se - 0.2 * ce  # front edge of the front row's tiles
    vc = (v_top + v_bot) / 2
    cam.location = (0.0, vc / se - 30 * ce, 30 * se)
    cam.rotation_euler = (math.pi / 2 - el, 0, 0)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x = res
    span = v_top - v_bot + 0.1
    sc.render.resolution_y = int(res * span / cam.data.ortho_scale)
    sc.view_settings.view_transform = "AgX"
    sc.render.filepath = png
    bpy.ops.render.render(write_still=True)
    print("SHEET", png)


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[0] if args else "game/assets/models"
    rest = args[1:]
    if "--sheet" in rest:
        png = rest[rest.index("--sheet") + 1]
        team = rest[rest.index("--team") + 1] if "--team" in rest else "blue"
        cols = int(rest[rest.index("--cols") + 1]) if "--cols" in rest else 4
        dls = [int(c) for c in rest[rest.index("--dl") + 1].split(",")] if "--dl" in rest else None
        troops_sheet(out, png, team, "--ref" in rest, 2400, cols, dls)
        sys.exit(0)
    os.makedirs(out, exist_ok=True)
    only = set(rest)
    report = {}
    for name, build in ASSETS.items():
        if only and not any(fnmatch.fnmatch(name, p) for p in only):
            continue
        ea.reset()
        build()
        report[name] = export(name, out)
    print("TRIS", report)
