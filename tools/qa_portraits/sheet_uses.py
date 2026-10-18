"""Every place the game shows a portrait, at its real size (941×1672 canvas px, 1:1), drawn with the game's own crop,
plate, halo, frame and scrims (docs/art_direction.md §7.12; cmd_portrait.gd, game_ui.gd, hud.gd, shop_ui.gd).
numpy + Pillow.

Usage: python3 -I tools/qa_portraits/sheet_uses.py PORTRAIT_DIR OUT_DIR [--plate=B|current] [--palette=ui|gdd]
                                                 [--mipmaps] [--tag=NAME]

Writes OUT_DIR/sheet_uses_<plate>_<palette>[_mip][_TAG].png. Rows (each cell captioned with the use and its size):
 1. album tile 242×312 (CmdPortrait ×, INK scrim over the bottom 150 px) for every commander present, one locked;
 2. commander card 312×352 (calm, and smile after a level-up), FTUE advisor bust 160×184 (cover, sky);
 3. seal 138×146 in its trim frame: leaders on their state colour (calm, angry), the dialog advisor (cmd_bram smile on
    sky), each commander at seal size on its rarity plate; diplomacy card art 172×104 (fit 128×147 at y −14, the name
    scrim covers everything below the eyes);
 4. raw renders without a plate (case reveal 87×100 / 68×78 / 157×180, pass 94×108, chapter legacy 87×100);
 5. small slots: shard pick 120, inbox 72, picker 72, calendar 64, army-tab fan 58×70, army chip Ø38 (48×50 render);
 6. the ruler: HUD 74×72 (brass, steel), profile 104 — when ruler*.png are present.
Sampling emulates Godot's canvas: one bilinear tap per screen pixel with NO mipmaps (today's import); --mipmaps
pre-filters minified textures by area (what P4's mipmaps + TEXTURE_FILTER_LINEAR_WITH_MIPMAPS give).
Plate "B" = §7.4, cmd_portrait.gd since P4 (rc.lightened(0.18) -> rc, a soft halo of concentric circles, no dark
ring; a locked commander a flat INK α 0.3 silhouette); "current" = cmd_portrait.gd before P4 (lightened(0.08) ->
darkened(0.42), a white α0.1 halo with a darker outline, the locked render multiplied by INK α 0.3).
Works on a folder that holds only some of the 150 names: uses whose files are missing are left out (listed).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # works under python3 -I too
import qa_common as Q  # noqa: E402

FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "fonts", "Rubik-VF.ttf")
OPTS = {}
SRC = "."


def hexc(h, a=1.0):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [a], dtype=np.float32)


INK, SKY_TOP, SKY_LOW = hexc("1b2140"), hexc("8fcdf2"), hexc("e3f4fd")
SKY_HI = hexc("a3d6f4")  # SKY_TOP.lightened(0.18): the top of the HUD crest's sky (hud.gd _build_crest since T1)
CREAM_ROW, CREAM_DEEP, PREMIUM_WELL = hexc("fffbf0"), hexc("d9c7a0"), hexc("ffe7a6")
BRASS, STEEL = hexc("e6b13e"), hexc("b9c7d6")


def rarity_col(r):
    return hexc(Q.PALETTES[OPTS.get("palette", "ui")][r])


def lightened(c, a):
    o = c.copy()
    o[:3] = c[:3] + (1 - c[:3]) * a
    return o


def darkened(c, a):
    o = c.copy()
    o[:3] = c[:3] * (1 - a)
    return o


def lerp(a, b, t):
    return a + (b - a) * t


def alpha(c, a):
    o = c.copy()
    o[3] = a
    return o


_cache = {}
MISSING = set()


def tex(name, era=1, mood=""):
    """CmdPortrait._render's lookup: era+mood, era calm, era-1 mood, era-1 calm. Premultiplied float RGBA or None."""
    base = name if era == 1 else "%s_e%d" % (name, era)
    for n in [base + ("_" + mood if mood else ""), base, name + ("_" + mood if mood else ""), name]:
        p = os.path.join(SRC, n + ".png")
        if os.path.exists(p):
            if p not in _cache:
                a = np.asarray(Image.open(p).convert("RGBA"), dtype=np.float32) / 255
                a[..., :3] *= a[..., 3:4]
                _cache[p] = a
            return _cache[p]
    MISSING.add(name + ("_" + mood if mood else ""))
    return None


def _prefilter(t, sw, sh, w, h):
    """--mipmaps: area-average the texture so a minified tap sees what a mip level holds."""
    th, tw = t.shape[:2]
    k = min(w / sw, h / sh)
    if k >= 0.999 or "mipmaps" not in OPTS:
        return t, 1.0
    nw, nh = max(1, int(round(tw * k))), max(1, int(round(th * k)))
    chans = [np.asarray(Image.fromarray(t[..., i], "F").resize((nw, nh), Image.BOX)) for i in range(4)]
    return np.stack(chans, -1), nw / tw


def sample(t, src, w, h):
    """Godot canvas sampling: per screen pixel one bilinear tap at its centre. src = (x, y, sw, sh) in texels."""
    sx, sy, sw, sh = src
    t, k = _prefilter(t, sw, sh, w, h)
    sx, sy, sw, sh = sx * k, sy * k, sw * k, sh * k
    th, tw = t.shape[:2]
    xs = sx + (np.arange(w) + 0.5) / w * sw - 0.5
    ys = sy + (np.arange(h) + 0.5) / h * sh - 0.5
    x0 = np.floor(xs).astype(int)
    y0 = np.floor(ys).astype(int)
    fx = (xs - x0)[None, :, None]
    fy = (ys - y0)[:, None, None]

    def g(yy, xx):
        inside = ((yy >= 0) & (yy < th))[:, None] & ((xx >= 0) & (xx < tw))[None, :]
        v = t[np.clip(yy, 0, th - 1)][:, np.clip(xx, 0, tw - 1)]
        return v * inside[..., None]
    a = g(y0, x0) * (1 - fx) + g(y0, x0 + 1) * fx
    b = g(y0 + 1, x0) * (1 - fx) + g(y0 + 1, x0 + 1) * fx
    return a * (1 - fy) + b * fy


def canvas(w, h, col=None):
    c = np.zeros((h, w, 4), np.float32)
    if col is not None:
        c[...] = col[:3].tolist() + [1.0]
        c[..., :3] *= col[3]
        c[..., 3] = col[3]
    return c


def over(dst, src, x=0, y=0, mask=None):
    h, w = src.shape[:2]
    H, W = dst.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x].copy()
    if mask is not None:
        s *= mask[y0 - y:y1 - y, x0 - x:x1 - x, None]
    d = dst[y0:y1, x0:x1]
    d[...] = s + d * (1 - s[..., 3:4])


def rrect_mask(w, h, r, ss=4, inset=0.0):
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).rounded_rectangle([inset * ss, inset * ss, (w - inset) * ss - 1, (h - inset) * ss - 1],
                                         radius=max(0, r - inset) * ss, fill=255)
    return np.asarray(im.resize((w, h), Image.BOX), np.float32) / 255


def ellipse_mask(w, h, cx, cy, rx, ry, ss=4):
    im = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(im).ellipse([(cx - rx) * ss, (cy - ry) * ss, (cx + rx) * ss, (cy + ry) * ss], fill=255)
    return np.asarray(im.resize((w, h), Image.BOX), np.float32) / 255


def solid(w, h, col):
    c = canvas(w, h)
    c[..., :3] = col[:3] * col[3]
    c[..., 3] = col[3]
    return c


def vgrad(w, h, top, bot):
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    c = top[None, None, :] * (1 - t) + bot[None, None, :] * t
    c = np.broadcast_to(c, (h, w, 4)).copy()
    c[..., :3] *= c[..., 3:4]
    return c


def ring(w, h, r, bw, col):
    m = rrect_mask(w, h, r) - rrect_mask(w, h, r, inset=bw)
    return solid(w, h, col), np.clip(m, 0, 1)


def cmd_portrait(name, w, h, rarity="common", locked=False, mood="", era=1, plate=None, frame=True):
    """cmd_portrait.gd _draw() with a render: plate gradient in the rounded box, a halo, the render cover-cropped from
    the TOP (horizontally centred), the frame R min(20, u/4), width clamp(u*0.025, 2, 4)."""
    u = min(w, h)
    rc = plate if plate is not None else rarity_col(rarity)
    fr = min(20.0, u * 0.25)
    box = rrect_mask(w, h, fr)
    b_mode = OPTS.get("plate", "B") == "B"
    if locked:
        top = lerp(rc, CREAM_DEEP, 0.72)
        bot = darkened(top, 0.32)
    elif b_mode:
        top, bot = lightened(rc, 0.18), rc.copy()
    else:
        top, bot = lightened(rc, 0.08), darkened(rc, 0.42)
    out = canvas(w, h)
    over(out, vgrad(w, h, top, bot), mask=box)
    if b_mode:  # soft concentric halo (cmd_portrait.gd HALO, HALO_LOCKED), +4–6 L* at the centre, no outline
        for k, (rr, a) in enumerate(((0.40, 0.05), (0.33, 0.05), (0.26, 0.05))):
            over(out, solid(w, h, hexc("ffffff", 0.02 if locked else a)),
                 mask=ellipse_mask(w, h, w * .5, h * .42, u * rr, u * rr) * box)
    else:
        hm = ellipse_mask(w, h, w * .5, h * .42, u * .36, u * .36)
        over(out, solid(w, h, hexc("ffffff", 0.1 if not locked else 0.05)), mask=hm * box)
        lw = max(1.2, u * 0.007)
        rm = np.clip(hm - ellipse_mask(w, h, w * .5, h * .42, u * .36 - lw, u * .36 - lw), 0, 1)
        over(out, solid(w, h, hexc("a6a6a6", 0.1)), mask=rm * box)
    t = tex(name, era, mood)
    if t is None:
        return None
    th, tw = t.shape[:2]
    sc = max(w / tw, h / th)
    pic = sample(t, ((tw - w / sc) / 2, 0, w / sc, h / sc), w, h)
    if locked and b_mode:  # P4: a flat INK α 0.3 silhouette from the render's alpha (SILHOUETTE shader), no detail
        mod = alpha(INK, 0.3)
        pic = np.concatenate([np.broadcast_to(np.asarray(mod[:3], np.float32), pic.shape[:2] + (3,)),
                              pic[..., 3:4] * mod[3]], axis=-1)
    elif locked:  # before P4: the render multiplied by INK α 0.3 (goggles and grey hair showed through)
        mod = alpha(INK, 0.3)
        pic = pic * np.array(list(mod[:3]) + [mod[3]], np.float32)
    over(out, pic, mask=box)
    if frame:
        col = rc if not locked else darkened(lerp(rc, CREAM_DEEP, 0.72), 0.45)
        s, m = ring(w, h, int(fr), int(round(min(4.0, max(2.0, u * 0.025)))), col)
        over(out, s, mask=m)
    return out


def tex_rect(name, w, h, mode, era=1, mood=""):
    t = tex(name, era, mood)
    if t is None:
        return None
    th, tw = t.shape[:2]
    if mode == "covered":
        sc = max(w / tw, h / th)
        return sample(t, ((tw - w / sc) / 2, (th - h / sc) / 2, w / sc, h / sc), w, h)
    sc = min(w / tw, h / th)
    dw, dh = int(round(tw * sc)), int(round(th * sc))
    out = canvas(w, h)
    over(out, sample(t, (0, 0, tw, th), dw, dh), (w - dw) // 2, (h - dh) // 2)
    return out


def _need(*parts):
    return all(p is not None for p in parts)


# ------------------------------------------------------------------ the uses (each returns an RGBA canvas or None)
def use_album(name, rarity, locked=False, era=1):
    W, H = 250, 320
    p = cmd_portrait(name, 242, 312, rarity, locked, era=era)
    if p is None:
        return None
    out = canvas(W, H)
    over(out, solid(W, H, INK), mask=rrect_mask(W, H, 24))
    over(out, p, 4, 4)
    clip = rrect_mask(W - 16, H - 16, 14)
    sc = canvas(W - 16, H - 16)
    over(sc, vgrad(W - 16, 150, alpha(INK, 0.0), alpha(INK, 0.92)), 0, H - 16 - 150)
    over(out, sc, 8, 8, mask=clip)
    return out


def use_card(name, rarity, locked=False, mood="", era=1):
    p = cmd_portrait(name, 312, 352, rarity, locked, mood, era)
    if p is None:
        return None
    out = canvas(320, 360)
    over(out, solid(320, 360, INK), mask=rrect_mask(320, 360, 24))
    over(out, p, 4, 4)
    return out


def use_face(name, rarity, side, locked=False, mood="", era=1):
    return cmd_portrait(name, side, side, rarity, locked, mood, era)


def use_chip(name, rarity, era=1):
    p = cmd_portrait(name, 48, 50, rarity, era=era)
    if p is None:
        return None
    out = canvas(44, 44)
    over(out, solid(44, 44, hexc("17203a")), mask=ellipse_mask(44, 44, 22, 22, 22, 22))
    inner = canvas(38, 38, SKY_LOW)
    over(inner, p, -5, -3)
    over(out, inner, 3, 3, mask=ellipse_mask(38, 38, 19, 19, 19, 19))
    s, m = solid(44, 44, INK), np.clip(ellipse_mask(44, 44, 22, 22, 22, 22) - ellipse_mask(44, 44, 22, 22, 19, 19), 0, 1)
    over(out, s, mask=m)
    return out


def use_fan(faces, era=1):
    W, H = 172, 104
    out = vgrad(W, H, SKY_TOP, SKY_LOW)
    out[H - 30:] = 0
    over(out, solid(W, 30, hexc("86c45e")), 0, H - 30)
    for i in (0, 2, 1):
        k = i - 1
        nm, rar, lk = faces[i % len(faces)]
        p = cmd_portrait(nm, 58, 70, rar, lk, era=era)
        if p is None:
            return None
        fr = canvas(64, 76)
        over(fr, solid(64, 76, INK), mask=rrect_mask(64, 76, 8))
        over(fr, p, 3, 3)
        im = Image.fromarray((np.clip(fr, 0, 1) * 255).astype(np.uint8), "RGBA")
        big = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        big.paste(im, (28, 22))
        big = big.rotate(-k * 8, resample=Image.BICUBIC, center=(60, 98))
        over(out, np.asarray(big, np.float32) / 255, int(86 + k * 42 - 32) - 28, int(8 + 12 + abs(k) * 6) - 22)
    return out


def use_seal(name, plate, mood="", trim=BRASS):
    p = cmd_portrait(name, 138, 146, plate=plate, mood=mood)
    if p is None:
        return None
    W, H = 156, 170
    out = canvas(W, H)
    over(out, solid(W, H, trim), mask=rrect_mask(W, H, 20))
    s, m = ring(W, H, 20, 4, INK)
    over(out, s, mask=m)
    over(out, p, 9, 9, mask=rrect_mask(138, 146, 14))
    s, m = ring(138, 146, 14, 3, INK)
    over(out, s, 9, 9, mask=m)
    return out


def use_mini(name, plate, mood="", side=80):
    p = tex_rect(name, side, side, "covered", mood=mood)
    if p is None:
        return None
    out = canvas(side, side)
    m = rrect_mask(side, side, 14)
    over(out, solid(side, side, plate), mask=m)
    over(out, p, mask=m)
    s, mm = ring(side, side, 14, 3, INK)
    over(out, s, mask=mm)
    return out


def use_dipl(name, plate, mood=""):
    p = tex_rect(name, 128, 147, "fit", mood=mood)
    if p is None:
        return None
    W, H = 172, 104
    out = vgrad(W, H, lightened(plate, 0.15), darkened(plate, 0.2))
    over(out, p, 22, -14)
    over(out, vgrad(W, 40, alpha(INK, 0.0), alpha(INK, 0.85)), 0, H - 40)
    return out


def use_coach(name="cmd_bram", mood="smile", era=1):
    p = tex_rect(name, 160, 184, "covered", era, mood)
    if p is None:
        return None
    W, H = 160, 184
    out = canvas(W, H)
    m = rrect_mask(W, H, 20)
    over(out, vgrad(W, H, SKY_TOP, SKY_LOW), mask=m)
    over(out, p, mask=m)
    s, mm = ring(W, H, 20, 4, INK)
    over(out, s, mask=mm)
    return out


def use_hud_ruler(era=1, trim=BRASS):
    p = tex_rect("ruler", 74, 72, "covered", era)
    if p is None:
        return None
    W, H = 90, 96
    out = canvas(W, H)
    over(out, solid(W, H, trim), mask=rrect_mask(W, H, 20))
    s, m = ring(W, H, 20, 4, INK)
    over(out, s, mask=m)
    well = canvas(74, 72)
    wm = rrect_mask(74, 72, 14)
    over(well, vgrad(74, 72, SKY_HI, SKY_TOP), mask=wm)
    over(well, p, mask=wm)
    over(out, well, 8, 8)
    s, m = ring(74, 72, 14, 3, INK)
    over(out, s, 8, 8, mask=m)
    return out


def use_profile_ruler(era=1):
    p = tex_rect("ruler", 104, 104, "covered", era)
    if p is None:
        return None
    W, H = 120, 130
    out = canvas(W, H)
    over(out, solid(W, H, BRASS), mask=rrect_mask(W, H, 20))
    s, m = ring(W, H, 20, 4, INK)
    over(out, s, mask=m)
    sky = canvas(104, 104)
    wm = rrect_mask(104, 104, 14)
    over(sky, solid(104, 104, SKY_TOP), mask=wm)
    over(sky, p, mask=wm)
    over(out, sky, 8, 8)
    return out


def use_tile_raw(name, tile_w, tile_h, side, face=CREAM_ROW, era=1, title_lines=1):
    if title_lines == 2:
        side = max(48, side - 22)
    p = tex_rect(name, side, side, "fit", era)
    if p is None:
        return None
    out = canvas(tile_w, tile_h)
    over(out, solid(tile_w, tile_h, face), mask=rrect_mask(tile_w, tile_h, 20))
    over(out, p, (tile_w - side) // 2, 14)
    return out


# ------------------------------------------------------------------ layout
def to_img(a):
    a = np.clip(a, 0, 1)
    rgb = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-6), 0)
    return Image.fromarray((np.concatenate([rgb, a[..., 3:4]], -1) * 255 + 0.5).astype(np.uint8), "RGBA")


def font(s, w=600):
    try:
        f = ImageFont.truetype(FONT, s)
        try:
            f.set_variation_by_axes([w])
        except Exception:
            pass
        return f
    except Exception:
        return ImageFont.load_default()


class Sheet:
    def __init__(self, w, bg=(236, 228, 210)):
        self.w, self.bg, self.items, self.y = w, bg, [], 0

    def title(self, text, size=26):
        self.items.append(("t", text, size, self.y))
        self.y += size + 12

    def note(self, text, size=17):
        self.items.append(("n", text, size, self.y))
        self.y += size + 8

    def row(self, cells, gap=16, label=16):
        cells = [(c, cap) for c, cap in cells if c is not None]
        if not cells:
            return
        x, h, placed = 16, 0, []
        f = font(label, 600)
        for c, cap in cells:
            im = to_img(c)
            cw = max(im.width, int(f.getlength(cap)) + 4)
            if x + cw > self.w - 16:
                self.y += h + label + 16
                x, h = 16, 0
            placed.append((im, cap, x, self.y))
            x += cw + gap
            h = max(h, im.height)
        for im, cap, px, py in placed:
            self.items.append(("i", im, cap, px, py, label))
        self.y += h + label + 20

    def save(self, path):
        img = Image.new("RGB", (self.w, self.y + 10), self.bg)
        d = ImageDraw.Draw(img)
        for it in self.items:
            if it[0] == "t":
                d.text((16, it[3]), it[1], fill=(27, 33, 64), font=font(it[2], 800))
            elif it[0] == "n":
                d.text((16, it[3]), it[1], fill=(70, 70, 90), font=font(it[2], 500))
            else:
                _, im, cap, px, py, ls = it
                img.paste(im, (px, py), im)
                d.text((px, py + im.height + 3), cap, fill=(40, 40, 60), font=font(ls, 600))
        img.save(path)
        print("saved", path, img.size)


def main():
    global SRC
    pos, opts = Q.parse(sys.argv[1:])
    OPTS.update(opts)
    SRC, out = pos[0], pos[1]
    os.makedirs(out, exist_ok=True)
    Q.report_missing(SRC)
    plate_mode, pal = OPTS.get("plate", "B"), OPTS.get("palette", "ui")
    cmds = ["cmd_" + c for c in Q.COMMANDERS if os.path.exists(os.path.join(SRC, "cmd_%s.png" % c))]
    ldrs = ["ldr_" + x for x in Q.LEADERS if os.path.exists(os.path.join(SRC, "ldr_%s.png" % x))]
    rar = {c: Q.RARITY[c[4:]] for c in cmds}
    s = Sheet(1700)
    s.title("Portraits where the game shows them: 1:1 on the 941×1672 canvas — plate %s, %s palette%s" % (
        plate_mode, pal, ", mipmaps" if "mipmaps" in OPTS else ", no mipmaps (today's import)"))
    s.note("Source: %s. Album / card / seal / small slots use CmdPortrait (cover-cropped from the top)." % SRC)
    if cmds:
        s.row([(use_album(c, rar[c]), "album 242×312 %s" % c[4:]) for c in cmds] +
              [(use_album(cmds[-1], rar[cmds[-1]], locked=True), "locked")])
        s.row([(use_card(c, rar[c]), "card 312×352 %s" % c[4:]) for c in cmds] +
              [(use_card(c, rar[c], mood="smile"), "card smile %s" % c[4:]) for c in cmds[:2]] +
              [(use_coach("cmd_bram" if "cmd_bram" in cmds else cmds[0]), "FTUE advisor 160×184")])
    seal = [(use_seal(l, hexc(Q.LEADER_PLATE[l[4:]])), "seal 138×146 %s" % l[4:]) for l in ldrs]
    seal += [(use_seal(l, hexc(Q.LEADER_PLATE[l[4:]]), "angry"), "angry") for l in ldrs[:3]]
    if cmds:
        adv = "cmd_bram" if "cmd_bram" in cmds else cmds[0]
        seal += [(use_seal(adv, SKY_TOP, "smile"), "dialog advisor (%s smile)" % adv[4:])]
        seal += [(use_seal(c, rarity_col(rar[c])), "seal size %s" % c[4:]) for c in cmds]
    seal += [(use_dipl(l, hexc(Q.LEADER_PLATE[l[4:]])), "diplomacy 172×104 %s" % l[4:]) for l in ldrs[:3]]
    s.row(seal)
    if cmds:
        tint = lambda c: lerp(rarity_col(rar[c]), CREAM_ROW, 0.55)  # noqa: E731
        raw = []
        for c in cmds:
            raw += [(use_tile_raw(c, 206, 176, 100, tint(c)), "reveal 87×100 %s" % c[4:])]
        raw += [(use_tile_raw(cmds[0], 206, 176, 100, tint(cmds[0]), title_lines=2), "two-line 68×78"),
                (use_tile_raw(cmds[-1], 300, 340, 180, tint(cmds[-1])), "single reveal 157×180"),
                (use_tile_raw(cmds[0], 150, 150, 108, PREMIUM_WELL), "pass 94×108"),
                (use_tile_raw(cmds[-1], 206, 176, 100), "legacy 87×100")]
        s.row(raw)
        small = []
        for c in cmds:
            small += [(use_face(c, rar[c], 120), "shard 120 %s" % c[4:]), (use_face(c, rar[c], 72), "picker 72"),
                      (use_face(c, rar[c], 64), "calendar 64"), (use_chip(c, rar[c]), "chip 38")]
        adv = "cmd_bram" if "cmd_bram" in cmds else cmds[0]
        small += [(use_face(adv, rar[adv], 72, mood="smile"), "inbox 72 (smile)")]
        small += [(use_mini(l, hexc(Q.LEADER_PLATE[l[4:]])), "dialog row 80 %s" % l[4:]) for l in ldrs[:3]]
        fan = [(c, rar[c], False) for c in cmds[:3]]
        small += [(use_fan(fan), "army-tab fan 58×70")]
        s.row(small, gap=12)
    if os.path.exists(os.path.join(SRC, "ruler.png")):
        s.row([(use_hud_ruler(1), "HUD ruler 74×72 e1"), (use_hud_ruler(2), "e2"), (use_hud_ruler(3, STEEL), "e3"),
               (use_hud_ruler(4, STEEL), "e4"), (use_profile_ruler(1), "profile 104 e1"),
               (use_profile_ruler(4), "e4")])
    if MISSING:
        s.note("missing (left out or replaced by the lookup chain): " + ", ".join(sorted(MISSING))[:300])
    name = "sheet_uses_%s_%s%s%s.png" % (plate_mode, pal, "_mip" if "mipmaps" in OPTS else "",
                                         ("_" + OPTS["tag"]) if "tag" in OPTS else "")
    s.save(os.path.join(out, name))


if __name__ == "__main__":
    main()
