"""Adds the title to the rendered key art → splash / loading screen and store art.
Run: python3 tools/ui/compose_keyart.py RENDER.png OUT.png [--subtitle "Territory Wars"] [--allow-black]
                                        [--layout=portrait|feature]
     python3 tools/ui/compose_keyart.py --check IMAGE.png   (the black-hole check alone; exit 1 on a hole)
--layout=portrait (default): the title over the top of a portrait render, at its size (the splash and
docs/store/keyart_portrait.png, 941×1672). --layout=feature: the Play feature graphic — the render (render_keyart.py
--frame=feature, 2048×1000) scaled to FEATURE_SIZE 1024×500, the title centred over the sky band, nothing within
FEATURE_EDGE of the left and right edges (Play crops and overlays the graphic's edges in some placements).

Before composing it checks the render for black holes in the land (black_runs): Cycles renders the overlap of two
coplanar faces black, and nothing in the soft style is darker than ≈ #2A2A30 (docs/art_direction.md §6.1 rule 3), so a
run of near-black pixels under the title band is a defect. A render with one is refused (exit 1) unless
--allow-black is passed."""
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BLACK_LEVEL = 24    # every channel under this (0–255) is "black"; the darkest soft albedo #2A2A30 is ~42
BLACK_RUN = 10      # a horizontal run at least this long (px) counts
LAND_FROM = 0.3     # the scan starts under the title band (a share of the height)


def black_runs(img, level=BLACK_LEVEL, min_run=BLACK_RUN, top=LAND_FROM):
    """Rows of `img` (under `top` × height) holding a run of ≥ min_run near-black pixels: [(y, x0, length)]."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    out = []
    for y in range(int(h * top), h):
        run = 0
        for x in range(w):
            r, g, b = px[x, y]
            run = run + 1 if max(r, g, b) < level else 0
            if run == min_run:
                out.append((y, x - min_run + 1, min_run))
            elif run > min_run:
                out[-1] = (y, out[-1][1], run)
    return out


def report_black(path, img):
    runs = black_runs(img)
    if not runs:
        print("black-hole check: %s clean (no run of ≥%d px under rgb %d)" % (path, BLACK_RUN, BLACK_LEVEL))
        return True
    ys = [r[0] for r in runs]
    xs = [r[1] for r in runs] + [r[1] + r[2] for r in runs]
    print("black-hole check: %s FAILS: %d rows with near-black runs, longest %d px, box x %d–%d y %d–%d"
          % (path, len(runs), max(r[2] for r in runs), min(xs), max(xs), min(ys), max(ys)))
    return False


if "-h" in sys.argv or "--help" in sys.argv:
    print(__doc__)
    sys.exit(0)


def value_of(flag):
    """The value after `flag`, or None when the flag is absent; a flag with no value (the last word, or followed by
    another --flag) prints the docstring and exits 2."""
    if flag not in sys.argv:
        return None
    i = sys.argv.index(flag)
    if i + 1 >= len(sys.argv) or sys.argv[i + 1].startswith("--"):
        print(__doc__)
        sys.exit(2)
    return sys.argv[i + 1]


if "--check" in sys.argv:
    path = value_of("--check")
    sys.exit(0 if report_black(path, Image.open(path)) else 1)

FEATURE_SIZE = (1024, 500)
FEATURE_EDGE = 0.1  # the title keeps this share of the width clear at each side
subtitle = value_of("--subtitle") or "TERRITORY WARS"
layout = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--layout=")), "portrait")
if layout not in ("portrait", "feature"):
    print(__doc__)
    sys.exit(2)
pos = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--subtitle"]
if len(pos) < 2:
    print(__doc__)
    sys.exit(2)
src, out = pos[0], pos[1]
im = Image.open(src).convert("RGBA")
if not report_black(src, im) and "--allow-black" not in sys.argv:
    sys.exit(1)
if layout == "feature" and im.size != FEATURE_SIZE:
    im = im.resize(FEATURE_SIZE, Image.LANCZOS)
W, H = im.size
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if layout == "portrait":  # the B4.6 numbers
    GRAD_H, GRAD_A = H * 0.36, 150
    T_SIZE, T_Y, T_SPACE = int(W * 0.2), int(H * 0.06), int(W * 0.012)
    S_SIZE, S_Y, S_SPACE = int(W * 0.062), int(H * 0.06 + W * 0.25), int(W * 0.01)
    SHADOW = (6, 10, 8)
else:
    GRAD_H, GRAD_A = H * 0.5, 140
    T_SIZE, T_Y, T_SPACE = int(H * 0.25), int(H * 0.04), int(H * 0.022)
    S_SIZE, S_Y, S_SPACE = int(H * 0.074), int(H * 0.04 + H * 0.29), int(H * 0.019)
    SHADOW = (3, 6, 5)

# soft dark gradient at the top so the title reads over the sky
grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(int(GRAD_H)):
    a = int(GRAD_A * (1 - y / GRAD_H) ** 1.6)
    gd.line([(0, y), (W, y)], fill=(8, 16, 40, a))
im = Image.alpha_composite(im, grad)


def text_layer(txt, size, fill, outline, y, spacing=0):
    font = ImageFont.truetype(BOLD, size)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # letter-spaced width
    widths = [d.textlength(ch, font=font) for ch in txt]
    total = sum(widths) + spacing * (len(txt) - 1)
    x = (W - total) / 2
    if layout == "feature" and total > W * (1 - 2 * FEATURE_EDGE):
        print("compose_keyart: WARNING: '%s' is %d px wide, over the feature graphic's safe width %d"
              % (txt, total, W * (1 - 2 * FEATURE_EDGE)))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    cx = x
    for ch, w in zip(txt, widths):
        sd.text((cx + SHADOW[0], y + SHADOW[1]), ch, font=font, fill=(0, 0, 0, 170))
        d.text((cx, y), ch, font=font, fill=fill, stroke_width=max(3, size // 14), stroke_fill=outline)
        cx += w + spacing
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW[2]))
    return Image.alpha_composite(shadow, layer)


title = text_layer("RAIVON", T_SIZE, (255, 214, 92, 255), (92, 44, 6, 255), T_Y, spacing=T_SPACE)
# vertical gold gradient on the title letters
mask = title.split()[3]
grad2 = Image.new("RGBA", (W, H))
g2 = ImageDraw.Draw(grad2)
y0, y1 = int(H * 0.06), int(H * 0.06 + W * 0.24)
for y in range(H):
    t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
    g2.line([(0, y), (W, y)], fill=(int(255 - 20 * t), int(236 - 80 * t), int(140 - 110 * t), 255))
im = Image.alpha_composite(im, title)
sub = text_layer(subtitle.upper(), S_SIZE, (235, 242, 255, 255), (20, 40, 90, 255), S_Y, spacing=S_SPACE)
im = Image.alpha_composite(im, sub)
im.convert("RGB").save(out)
print(out)
