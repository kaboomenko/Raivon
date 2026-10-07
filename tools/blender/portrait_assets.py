"""Commander portrait kit (04 §15.4): 3/4 busts built from the kit parameters — head shape, hair, facial hair,
headgear, uniform, accessory, palette from 04 §15.3 — rendered on a transparent background (the game draws the
rarity plate and frame). Run: python3 tools/blender/portrait_assets.py OUTDIR [ids...] [--size=256]
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402

# skin, head (w, h), hair colour, hair style, facial hair, headgear, uniform, accent
LOOK = {
    "cmd_bram": ("#e8b48e", (0.40, 0.41), "#b5562b", "short", "beard", "", "#d9c9a3", "#7a4e2d"),
    "cmd_lira": ("#f0c4a0", (0.33, 0.42), "#5a3420", "braid", "", "kerchief", "#3e9b5a", "#f2f2f2"),
    "cmd_olm": ("#e2b08c", (0.31, 0.45), "#c8c8c8", "sides", "", "goggles", "#7a4e2d", "#c9a24a"),
    "cmd_vik": ("#f2c8a4", (0.32, 0.43), "#e3c46a", "messy", "", "hood", "#4e6b3a", "#6b4a2a"),
    "cmd_vega": ("#e9bd99", (0.32, 0.42), "#2e2a2a", "bob", "", "glasses", "#44484f", "#c8ccd4"),
    "cmd_kort": ("#dca582", (0.41, 0.42), "#d8d8d8", "bald", "mustache_long", "", "#5d6236", "#b0803a"),
    "cmd_seir": ("#c98d68", (0.36, 0.41), "#cfcfcf", "short", "beard_short", "tricorn", "#1f6f8b", "#f2f2f2"),
    "cmd_frey": ("#e4b592", (0.38, 0.40), "#6b5a48", "buzz", "", "", "#3b5a44", "#9aa3ad"),
    "cmd_irma": ("#f1c9aa", (0.32, 0.42), "#efe9dc", "ponytail", "", "goggles", "#26272b", "#f08a24"),
    "cmd_hawk": ("#e6b996", (0.34, 0.42), "#4a3424", "short", "mustache", "flight", "#7a5133", "#6fa8dc"),
    "cmd_vance": ("#f0cdb2", (0.32, 0.42), "#d9d9de", "updo", "", "brooch", "#8e5bd0", "#e8e8f0"),
    "cmd_rai": ("#e7c0a0", (0.36, 0.43), "#f0f0f0", "long", "beard_long", "circlet", "#eef1f6", "#3a8dff"),
}
# AI leaders (canon §10.4: the same kit, combinations kept apart from the commanders), in their states' colours
LOOK.update({
    "ldr_barons": ("#d9a07a", (0.42, 0.42), "#2a1d14", "bald", "beard", "", "#c0392b", "#f08a24"),       # Baron Grodek the Fang
    "ldr_hamlets": ("#f0c9a8", (0.34, 0.42), "#c8873a", "braid", "", "kerchief", "#3fa34d", "#e8b23a"),  # Headwoman Mirosya
    "ldr_league": ("#e6bf9c", (0.31, 0.43), "#3a2a1e", "updo", "", "glasses", "#1fb5ad", "#e8e8f0"),    # Chancellor Iveta
    "ldr_order": ("#d8b292", (0.38, 0.43), "#9a9a9a", "short", "beard_long", "", "#7a7f88", "#c8ccd4"),  # Magister Torvald
    "ldr_alvaria": ("#ecc6a8", (0.31, 0.43), "#1a1416", "long", "", "crown", "#8e5bd0", "#c8ccd4"),     # Sovereign Sairin
    "ldr_saren": ("#d9a585", (0.33, 0.42), "#4a2e1c", "short", "mustache", "", "#e08a2a", "#1f6f8b"),    # Doge Velian
    "ldr_pack": ("#e2b896", (0.39, 0.41), "#1c1c22", "messy", "beard_short", "", "#2a2d36", "#9aa3ad"),  # Chieftain Bjorulf
    "ldr_conclave": ("#cfa585", (0.41, 0.42), "#6b6f78", "buzz", "beard", "goggles", "#5a6472", "#b0803a"),  # Archmaster Ormdek
    "ldr_veilmark": ("#efcfb8", (0.31, 0.43), "#2a1830", "bob", "", "brooch", "#4a2a5e", "#c8ccd4"),    # Margravine Vedana
    "ldr_lakes": ("#e0b896", (0.33, 0.43), "#1d2533", "short", "", "glasses", "#2e6bff", "#e8e8f0"),     # Consul Arman
})
HEAD_Z = 1.3


def darker(hex_color, k=0.6):
    h = hex_color.lstrip("#")
    c = [int(int(h[i:i + 2], 16) * k) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(c)


def mix(a, b, t):
    pa = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    pb = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(pa, pb))


# Eras of the uniform (04 §15.4): the face stays, the uniform and the headgear follow the player's DL —
# 1 cloth and leather (DL1–3), 2 coats and bicornes (DL4–5), 3 field uniform (DL6–7), 4 armour and visors (DL8–10).
# Personal gear (goggles, glasses, the flight helmet, the cap, the circlet) is kept in every era.
KEEP_GEAR = ("goggles", "glasses", "flight", "tricorn", "circlet")


def _mouth(name, z, y, mood, lips, w=0.13):
    """The mouth: a line, a frown (corners down, the angry leader of an ultimatum) or a smile (corners up)."""
    if mood == "":
        kit.box(name, (w, 0.03, 0.025), (0, y, z), lips, 0.01)
        return
    up = 1 if mood == "smile" else -1
    w *= 1.2
    kit.box(name, (w * 0.5, 0.035, 0.034), (0, y - 0.004, z + (0.0 if mood == "smile" else 0.016)), lips, 0.012)
    for sx in (-1, 1):
        c = kit.box(name + "_corner", (w * 0.36, 0.035, 0.032), (sx * w * 0.38, y, z + up * 0.022), lips, 0.012)
        c.rotation_euler.y = math.radians(-38 * sx * up)


# Moods (04 §15.4: 5 expression presets; the game uses these): "" calm, "angry" (ultimatum), "smile" (peace).
def build(cid, era=1, mood=""):
    skin_c, (hw, hh), hair_c, style, facial, gear, uni_c, acc_c = LOOK[cid]
    if era == 2:
        uni_c = darker(uni_c, 0.72)
    elif era == 3:
        uni_c = mix(uni_c, "#6b7a4a", 0.65)
    elif era == 4:
        uni_c = mix(uni_c, "#2f3642", 0.8)
    era_hat = era > 1 and gear not in KEEP_GEAR
    if era_hat and gear != "brooch":
        gear = ""
    skin = kit.mat("skin_" + cid, skin_c, 0.55)
    hair = kit.mat("hair_" + cid, hair_c, 0.7)
    uni = kit.mat("uni_" + cid, uni_c, 0.65)
    acc = kit.mat("acc_" + cid, acc_c, 0.45, 0.3 if cid in ("cmd_vega", "cmd_frey", "cmd_rai") else 0.0)
    white = kit.mat("eye_white", "#f6f6f2", 0.3)
    dark = kit.mat("eye_dark", "#1d1714", 0.3)
    lips = kit.mat("lips", "#9b4a3c", 0.5)
    brow = kit.mat("brow_" + cid, darker(hair_c, 0.55), 0.8)
    # bust: shoulders, chest, neck
    kit.sphere("shoulders", 1.0, (0, 0.05, 0.62), uni, (0.72, 0.42, 0.3))
    kit.cyl("chest", 0.6, 0.8, (0, 0.05, 0.22), uni, 32, 0.05, r2=0.66)
    kit.cyl("neck", 0.13, 0.32, (0, 0.02, 0.95), skin, 16, 0.02)
    # the collar: a V of the shirt (or the accent) on the chest
    collar_m = acc if cid in ("cmd_lira", "cmd_seir", "cmd_vance") else kit.mat("shirt", "#e9e2d0", 0.6)
    me = bpy.data.meshes.new("collar")
    me.from_pydata([(-0.17, -0.47, 0.9), (0.17, -0.47, 0.9), (0.0, -0.53, 0.64)], [], [(0, 2, 1)])
    v = bpy.data.objects.new("collar", me)
    bpy.context.scene.collection.objects.link(v)
    me.materials.append(collar_m)
    # head
    kit.sphere("head", 1.0, (0, -0.02, HEAD_Z), skin, (hw, 0.37, hh))
    if cid in ("cmd_bram", "cmd_kort", "cmd_frey"):
        kit.sphere("jaw", 1.0, (0, -0.06, HEAD_Z - 0.2), skin, (hw * 0.92, 0.32, 0.22))
    for sx in (-1, 1):
        kit.sphere("ear", 1.0, (sx * hw * 0.98, 0.02, HEAD_Z - 0.02), skin, (0.06, 0.08, 0.1))
    # eyes, pupils, brows
    for sx in (-1, 1):
        kit.sphere("eye", 0.078, (sx * 0.135, -0.31, HEAD_Z + 0.03), white, (1.0, 0.6, 0.85), 2)
        pc = kit.mat("rai_eye", "#3a8dff", 0.2, emission="#5aa0ff", emit_strength=4.0) if cid == "cmd_rai" else dark
        kit.sphere("pupil", 0.045, (sx * 0.135 + 0.012, -0.355, HEAD_Z + 0.025), pc, (1, 0.6, 1.05), 2)
        bz = HEAD_Z + 0.13 + (-0.02 if mood == "angry" else (0.025 if mood == "smile" else 0.0))
        b = kit.box("brow", (0.15, 0.04, 0.035), (sx * 0.14, -0.34, bz), brow, 0.01)
        tilt = -12 * sx if cid != "cmd_vega" or sx < 0 else 18
        if mood == "angry":
            tilt = -28 * sx  # inner ends down — a scowl
        elif mood == "smile":
            tilt = -6 * sx
        b.rotation_euler.y = math.radians(tilt)
    # nose and mouth
    if cid in ("cmd_bram", "cmd_kort"):
        kit.sphere("nose", 0.075, (0, -0.39, HEAD_Z - 0.06), skin, (1.0, 0.9, 0.9))
    else:
        n = kit.cone("nose", 0.05, 0.16, (0, -0.37, HEAD_Z - 0.04), skin, 8, 0.01)
        n.rotation_euler = (math.radians(-70), 0, 0)
    _mouth("mouth", HEAD_Z - 0.18, -0.335, mood, lips)
    # hair
    if style in ("short", "messy", "braid", "long", "ponytail", "updo", "bob", "buzz") and not (era == 4 and era_hat):
        top = 0.3 if style != "buzz" else 0.24
        kit.sphere("hair_cap", 1.0, (0, 0.03, HEAD_Z + 0.16), hair, (hw + 0.03, 0.4, top + 0.06))
    if style == "messy" and not (era == 4 and era_hat):
        for k in range(6):
            a = -0.5 + k * 0.2
            c = kit.cone("tuft", 0.07, 0.18, (a * hw * 1.6, -0.2, HEAD_Z + 0.36), hair, 6, 0.0)
            c.rotation_euler = (math.radians(-40), math.radians(a * 50), 0)
    if style == "sides" or style == "bald":
        for sx in (-1, 1):
            kit.sphere("side_hair", 1.0, (sx * hw * 0.92, 0.05, HEAD_Z + 0.02), hair, (0.07, 0.2, 0.15))
    if style == "bob":
        for sx in (-1, 1):
            kit.sphere("bob", 1.0, (sx * hw * 0.92, 0.02, HEAD_Z - 0.02), hair, (0.1, 0.3, 0.28))
        kit.box("streak", (0.05, 0.05, 0.22), (-0.1, -0.33, HEAD_Z + 0.27), kit.mat("grey_streak", "#c4c4c4", 0.6), 0.02)
    if style == "braid":
        for k in range(5):
            kit.sphere("braid", 0.075 - k * 0.005, (hw * 0.75, -0.05 - k * 0.04, HEAD_Z - 0.2 - k * 0.12), hair)
    if style == "long":
        kit.sphere("long_hair", 1.0, (0, 0.12, HEAD_Z - 0.1), hair, (hw + 0.1, 0.32, 0.55))
    if style == "ponytail":
        c = kit.cone("ponytail", 0.11, 0.6, (hw * 0.4, 0.3, HEAD_Z + 0.05), hair, 10, 0.02)
        c.rotation_euler = (math.radians(150), math.radians(20), 0)
    if style == "updo":
        kit.sphere("bun", 0.17, (0, 0.06, HEAD_Z + 0.48), hair)
    # facial hair
    if facial.startswith("beard"):
        h = {"beard": 0.28, "beard_short": 0.18, "beard_long": 0.45}[facial]
        kit.sphere("beard", 1.0, (0, -0.16, HEAD_Z - 0.2 - h * 0.35), hair, (hw * 0.95, 0.27, h))
        _mouth("mouth_gap", HEAD_Z - 0.18, -0.39 if facial != "beard_short" else -0.37, mood, lips, 0.12)
    if facial in ("mustache", "mustache_long", "beard", "beard_long"):
        ln = 0.26 if facial == "mustache_long" else 0.13
        for sx in (-1, 1):
            m = kit.sphere("mustache", 1.0, (sx * ln * 0.55, -0.36, HEAD_Z - 0.13 - (0.06 if facial == "mustache_long" else 0)), hair, (ln * 0.55, 0.05, 0.045))
            m.rotation_euler.y = math.radians(25 * sx if facial == "mustache_long" else 10 * sx)
    # headgear
    if gear == "kerchief":
        kit.sphere("kerchief", 1.0, (0, 0.02, HEAD_Z + 0.2), acc, (hw + 0.05, 0.41, 0.3))
    if gear in ("goggles", "flight"):
        if gear == "flight":
            kit.sphere("helmet", 1.0, (0, 0.03, HEAD_Z + 0.12), kit.mat("leather", "#6b4428", 0.55), (hw + 0.05, 0.42, 0.36))
        strap = kit.mat("strap", "#2a2a2a", 0.5)
        for sx in (-1, 1):
            g = kit.cyl("goggle", 0.075, 0.06, (sx * 0.13, -0.33, HEAD_Z + 0.27), strap, 16, 0.01)
            g.rotation_euler.x = math.radians(80)
            lens = kit.cyl("lens", 0.055, 0.02, (sx * 0.13, -0.365, HEAD_Z + 0.272), kit.mat("lens", "#8fc4d8" if gear == "goggles" else "#6fa8dc", 0.1, 0.3), 16, 0.0)
            lens.rotation_euler.x = math.radians(80)
    if gear == "hood":
        kit.sphere("hood", 1.0, (0, 0.08, HEAD_Z + 0.06), uni, (hw + 0.1, 0.42, 0.5))
        kit.sphere("hood_face", 1.0, (0, -0.02, HEAD_Z - 0.02), skin, (hw * 0.96, 0.36, hh * 0.9))
        kit.sphere("hood_hair", 1.0, (0, -0.06, HEAD_Z + 0.2), hair, (hw * 0.85, 0.33, 0.14))
    if gear == "glasses":
        frame = kit.mat("frame", "#c8ccd4", 0.3, 0.8)
        for sx in (-1, 1):
            bpy.ops.mesh.primitive_torus_add(major_radius=0.085, minor_radius=0.012, location=(sx * 0.13, -0.36, HEAD_Z + 0.03), rotation=(math.radians(90), 0, 0))
            bpy.context.active_object.data.materials.append(frame)
    if gear == "tricorn":  # the admiral's peaked cap (04 §15.3: tricorn → cap by era)
        hat = kit.mat("hat", "#1d2533", 0.55)
        kit.cyl("cap_top", hw + 0.06, 0.1, (0, 0.04, HEAD_Z + 0.34), hat, 32, 0.03, r2=hw + 0.12)
        kit.cyl("cap_band", hw + 0.03, 0.07, (0, 0.03, HEAD_Z + 0.27), acc, 32, 0.01)
        visor = kit.sphere("visor", 1.0, (0, -0.3, HEAD_Z + 0.24), kit.mat("visor", "#0d0f14", 0.25), (hw * 0.75, 0.16, 0.03))
        visor.rotation_euler.x = math.radians(-12)
        kit.sphere("badge", 0.04, (0, -0.37, HEAD_Z + 0.3), kit.mat("gold_badge", "#e8b23a", 0.25, 0.8), (1, 0.5, 1))
    if gear == "circlet":
        silver = kit.mat("silver", "#d0d6de", 0.25, 0.9)
        bpy.ops.mesh.primitive_torus_add(major_radius=hw + 0.005, minor_radius=0.018, location=(0, -0.01, HEAD_Z + 0.22), rotation=(math.radians(-8), 0, 0))
        bpy.context.active_object.data.materials.append(silver)
        kit.sphere("raivite", 0.055, (0, -0.375, HEAD_Z + 0.2), kit.mat("raivite_gem", "#3a8dff", 0.1, emission="#5aa0ff", emit_strength=6.0), (1, 0.6, 1.25))
    if gear == "crown":
        gold = kit.mat("crown_gold", "#e8b23a", 0.25, 0.85)
        kit.cyl("crown_band", hw + 0.02, 0.08, (0, 0.0, HEAD_Z + 0.3), gold, 32, 0.01)
        for k in range(7):
            a = math.pi * (0.15 + 0.7 * k / 6)
            kit.cone("crown_spike", 0.035, 0.12, ((hw + 0.02) * math.cos(a), -(hw + 0.0) * math.sin(a) * 0.9, HEAD_Z + 0.39), gold, 4, 0.0)
        kit.sphere("crown_gem", 0.035, (0, -hw - 0.01, HEAD_Z + 0.31), kit.mat("crown_gem", "#8e5bd0", 0.1, emission="#b07aff", emit_strength=3.0), (1, 0.6, 1))
    if gear == "brooch":
        kit.sphere("brooch", 0.06, (0, -0.4, 0.66), kit.mat("pearl", "#f4f1ea", 0.15), (1, 0.6, 1))
    # uniform details
    if cid in ("cmd_vega", "cmd_frey", "cmd_kort", "cmd_vance", "cmd_rai", "ldr_barons", "ldr_alvaria", "ldr_order", "ldr_conclave"):
        for sx in (-1, 1):
            kit.sphere("epaulette", 1.0, (sx * 0.5, -0.02, 0.86), acc, (0.17, 0.2, 0.06))
    if cid in ("ldr_pack", "ldr_barons"):  # fur mantles
        bpy.ops.mesh.primitive_torus_add(major_radius=0.32, minor_radius=0.1, location=(0, 0.02, 0.86))
        bpy.context.active_object.data.materials.append(kit.mat("fur_dark", "#3a2e26" if cid == "ldr_pack" else "#7a5a3a", 0.95))
    if cid == "ldr_pack":  # a raven feather on the shoulder
        f = kit.sphere("feather", 1.0, (0.42, -0.1, 0.98), kit.mat("feather", "#121216", 0.4), (0.04, 0.03, 0.16))
        f.rotation_euler.y = math.radians(-25)
    if cid == "cmd_kort":
        bpy.ops.mesh.primitive_torus_add(major_radius=0.3, minor_radius=0.09, location=(0, 0.02, 0.86))
        bpy.context.active_object.data.materials.append(kit.mat("fur", "#8a6a48", 0.9))
    if cid == "cmd_hawk":
        bpy.ops.mesh.primitive_torus_add(major_radius=0.2, minor_radius=0.075, location=(0, 0.0, 0.9))
        bpy.context.active_object.data.materials.append(kit.mat("scarf", "#f4f4f4", 0.7))
    gold = kit.mat("gold_trim", "#e8b23a", 0.3, 0.8)
    if era == 2:  # a coat: a column of brass buttons, gold epaulettes, a bicorne
        for k in range(4):
            kit.sphere("button", 0.022, (0.0, -0.5, 0.62 - k * 0.11), gold)
        if cid not in ("cmd_vega", "cmd_frey", "cmd_kort", "cmd_vance", "cmd_rai"):
            for sx in (-1, 1):
                kit.sphere("epaulette", 1.0, (sx * 0.5, -0.02, 0.86), gold, (0.17, 0.2, 0.06))
        if era_hat:
            hat = kit.mat("bicorne", "#1d2533", 0.55)
            bc = kit.sphere("bicorne", 1.0, (0, -0.02, HEAD_Z + 0.46), hat, (hw + 0.2, 0.16, 0.17))
            bc.rotation_euler.x = math.radians(-12)
            kit.sphere("bicorne_trim", 1.0, (0, -0.02, HEAD_Z + 0.4), gold, (hw + 0.21, 0.165, 0.03))
            kit.sphere("cockade", 0.055, (0, -0.18, HEAD_Z + 0.48), acc, (1, 0.5, 1))
    if era == 3:  # field uniform: chest pockets, a shoulder belt, a peaked field cap
        for sx in (-1, 1):
            kit.box("pocket", (0.16, 0.04, 0.14), (sx * 0.22, -0.52, 0.5), kit.mat("pocket", darker(uni_c, 0.85), 0.7), 0.02)
        b = kit.box("sam_browne", (0.07, 0.04, 1.1), (0.08, -0.49, 0.42), kit.mat("belt", "#5a3a22", 0.6), 0.01)
        b.rotation_euler.y = math.radians(-32)
        if era_hat:
            cap = kit.mat("field_cap", mix(uni_c, "#3d4a2a", 0.4), 0.6)
            kit.cyl("fcap_top", hw + 0.05, 0.1, (0, 0.04, HEAD_Z + 0.34), cap, 32, 0.03, r2=hw + 0.1)
            kit.cyl("fcap_band", hw + 0.03, 0.07, (0, 0.03, HEAD_Z + 0.27), kit.mat("fcap_band", darker(uni_c, 0.6), 0.6), 32, 0.01)
            v = kit.sphere("fcap_visor", 1.0, (0, -0.3, HEAD_Z + 0.24), kit.mat("visor", "#1b1a16", 0.3), (hw * 0.75, 0.16, 0.03))
            v.rotation_euler.x = math.radians(-12)
            kit.sphere("fcap_badge", 0.035, (0, -0.37, HEAD_Z + 0.3), acc, (1, 0.5, 1))
    if era == 4:  # armour: plates, pauldrons, a glowing strip in the accent colour, a helmet with a visor band
        steel = kit.mat("armour", "#5a6472", 0.3, 0.85)
        glowm = kit.mat("glow_" + cid, acc_c, 0.2, emission=acc_c, emit_strength=5.0)
        for sx in (-1, 1):
            kit.sphere("pauldron", 1.0, (sx * 0.5, 0.0, 0.84), steel, (0.22, 0.26, 0.12))
        kit.box("chest_plate", (0.5, 0.06, 0.42), (0, -0.5, 0.52), steel, 0.05)
        kit.box("chest_glow", (0.36, 0.02, 0.03), (0, -0.54, 0.62), glowm, 0.0)
        if era_hat:
            kit.sphere("helmet", 1.0, (0, 0.03, HEAD_Z + 0.13), steel, (hw + 0.06, 0.43, 0.36))
            bpy.ops.mesh.primitive_torus_add(major_radius=hw + 0.035, minor_radius=0.02, location=(0, -0.01, HEAD_Z + 0.24))
            bpy.context.active_object.data.materials.append(glowm)
    if cid == "cmd_olm" and era == 1:
        kit.box("apron", (0.62, 0.05, 0.7), (0, -0.42, 0.3), kit.mat("apron", "#5a3820", 0.7), 0.03)
        kit.box("wrench", (0.05, 0.03, 0.3), (0.18, -0.46, 0.38), kit.mat("brass", "#c9a24a", 0.3, 0.8), 0.01)
    if cid == "cmd_lira" and era == 1:
        s = kit.box("bag_strap", (0.08, 0.04, 1.0), (0.05, -0.38, 0.45), kit.mat("strap_lira", "#7a5a3a", 0.7), 0.01)
        s.rotation_euler.y = math.radians(35)
    if cid == "cmd_rai":
        kit.sphere("cloak", 1.0, (0, 0.18, 0.55), kit.mat("cloak", "#3a8dff", 0.6), (0.72, 0.4, 0.5))


def setup(size):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 40
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = size
    sc.render.resolution_y = int(size * 1.15)
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.6, 0.7, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    key = bpy.data.objects.new("key", bpy.data.lights.new("key", "AREA"))
    key.data.energy = 260
    key.data.size = 2.5
    key.location = (-2.2, -2.6, 2.8)
    key.rotation_euler = (math.radians(50), 0, math.radians(-40))
    sc.collection.objects.link(key)
    rim = bpy.data.objects.new("rim", bpy.data.lights.new("rim", "AREA"))
    rim.data.energy = 160
    rim.data.size = 1.5
    rim.location = (2.2, 1.8, 2.4)
    rim.rotation_euler = (math.radians(-50), 0, math.radians(140))
    sc.collection.objects.link(rim)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    cam.data.lens = 85
    cam.location = (-1.4, -3.85, 1.7)
    target = (0.0, 0.0, 1.17)
    d = [target[i] - cam.location[i] for i in range(3)]
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    sc.camera = cam


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    size = 256
    for a in sys.argv[1:]:
        if a.startswith("--size="):
            size = int(a[7:])
    eras = [1]
    moods = [""]
    for a in sys.argv[1:]:
        if a.startswith("--eras="):
            eras = [int(x) for x in a[7:].split(",")]
        if a.startswith("--moods="):
            moods = ["" if m == "calm" else m for m in a[8:].split(",")]
    out = args[0]
    ids = args[1:] or list(LOOK)
    os.makedirs(out, exist_ok=True)
    for cid in ids:
        for era in eras:
            for mood in moods:
                bpy.ops.wm.read_factory_settings(use_empty=True)
                kit._MATS.clear()
                build(cid, era, mood)
                setup(size)
                name = cid if era == 1 else "%s_e%d" % (cid, era)  # era 1 keeps the plain name
                if mood:
                    name += "_" + mood
                bpy.context.scene.render.filepath = os.path.join(out, name + ".png")
                bpy.ops.render.render(write_still=True)
                print("rendered", name)


main()
