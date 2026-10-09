#!/usr/bin/env python3
"""Look metrics of Raivon screenshots — the «Raivon Soft» check (docs/art_direction.md §6.12).

Usage: python3 -I tools/look_metrics.py IMG [IMG ...] [--crop x0,y0,x1,y1] [--check]
           [--sample x0,y0,x1,y1 ...] [--gray OUT.png] [--deutan OUT.png]

One line per image, measured over the map area (x 110-720, y 300-1380 of a 941x1672 shot: below the minimap,
above the bottom panel, right of the left button column; the whole image for any other size; --crop overrides):
  V p10/p50/p90       HSV value percentiles
  S                   mean HSV saturation
  black               near-black pixels, V < 0.25
  white-hot           V > 0.92 and S < 0.18
  grit                mean |gradient| of the luma (Rec.709 weights on the sRGB values)
  hard                pixels with |gradient| > 0.25
  L* p10/p50/p90      CIE L* percentiles;  L*<15  share of very dark pixels
  grass               median colour of grass pixels (hue 60-150 deg, S > 0.2): #hex, L*, S %, hue deg, share of the crop
--check      adds a line per image with the §6.12 targets that are missed (hard edges: 6 % for a file named *dl8*).
--sample R   mean sRGB #hex and CIE L*a*b* (+ chroma, hue angle, L* spread) of rectangle R in full-image pixels;
             repeatable. For the ribbon ΔL* (blue vs red body) and the shadow-side hue.
--gray OUT   greyscale copy (each pixel's luminance Y, re-encoded to sRGB: equal L* reads as equal grey).
--deutan OUT deuteranopia simulation: Machado et al. 2009, severity 1.0, applied on linear RGB.
With several images, --gray/--deutan write OUT with "_<image name>" inserted before the extension; an OUT
without an extension gets ".png". Exits 1 when an image cannot be read, a crop or sample misses it, or a copy
cannot be written (the other images are still measured).
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

MAP_CROP = (110, 300, 720, 1380)  # x0, y0, x1, y1 for a 941x1672 shot
SHOT_SIZE = (941, 1672)
LUMA = np.array([0.2126, 0.7152, 0.0722])
MACHADO_DEUTAN_1 = np.array([[0.367322, 0.860646, -0.227968],
                             [0.280085, 0.672501, 0.047413],
                             [-0.011820, 0.042940, 0.968881]])
# sRGB (D65) linear -> XYZ
RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                    [0.2126729, 0.7151522, 0.0721750],
                    [0.0193339, 0.1191920, 0.9503041]])
WHITE_D65 = np.array([0.95047, 1.0, 1.08883])


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def lab_f(t):
    return np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)


def srgb_to_lab(rgb):
    """rgb: (..., 3) sRGB in 0..1 -> (..., 3) CIE L*a*b* (D65)."""
    xyz = to_linear(rgb) @ RGB2XYZ.T / WHITE_D65
    f = lab_f(xyz)
    L = np.where(xyz[..., 1] > 0.008856, 116 * f[..., 1] - 16, 903.3 * xyz[..., 1])
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def lightness(rgb):
    Y = to_linear(rgb) @ LUMA
    return np.where(Y > 0.008856, 116 * np.cbrt(Y) - 16, 903.3 * Y)


def hsv_parts(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    return h, s, mx


def hexcol(rgb):
    return "#%02X%02X%02X" % tuple(int(round(v)) for v in np.clip(rgb, 0, 1) * 255)


def rect(text, name):
    try:
        x0, y0, x1, y1 = (int(v) for v in text.split(","))
    except ValueError:
        sys.exit(f"{name} wants x0,y0,x1,y1 (got '{text}')")
    if x1 <= x0 or y1 <= y0:
        sys.exit(f"{name}: empty rectangle {text}")
    return x0, y0, x1, y1


def measure(a, path):
    """a: (h, w, 3) sRGB 0..1 crop. Returns a dict of the metrics."""
    h, s, v = hsv_parts(a)
    lum = a @ LUMA
    gx = np.abs(np.diff(lum, axis=1))[:-1, :]
    gy = np.abs(np.diff(lum, axis=0))[:, :-1]
    grad = np.hypot(gx, gy)
    L = lightness(a)
    green = (h > 60) & (h < 150) & (s > 0.2)
    m = {
        "v": np.percentile(v, [10, 50, 90]),
        "s": s.mean(),
        "black": 100 * (v < 0.25).mean(),
        "white": 100 * ((v > 0.92) & (s < 0.18)).mean(),
        "grit": grad.mean(),
        "hard": 100 * (grad > 0.25).mean(),
        "L": np.percentile(L, [10, 50, 90]),
        "L15": 100 * (L < 15).mean(),
        "grass_share": 100 * green.mean(),
        "dl8": "dl8" in os.path.basename(path).lower(),
    }
    if green.any():
        m["grass"] = np.median(a[green], 0)
        m["grass_L"] = np.median(L[green])
        m["grass_S"] = 100 * np.median(s[green])
        m["grass_h"] = np.median(h[green])
    return m


def line(name, m):
    out = (f"{name}: V p10/p50/p90 {m['v'][0]:.2f}/{m['v'][1]:.2f}/{m['v'][2]:.2f} | S {m['s']:.2f}"
           f" | black {m['black']:.1f}% | white-hot {m['white']:.2f}% | grit {m['grit']:.3f} | hard {m['hard']:.2f}%"
           f" | L* p10/p50/p90 {m['L'][0]:.0f}/{m['L'][1]:.0f}/{m['L'][2]:.0f} | L*<15 {m['L15']:.1f}%")
    if "grass" in m:
        out += (f" | grass {hexcol(m['grass'])} L* {m['grass_L']:.0f} S {m['grass_S']:.0f}% hue {m['grass_h']:.0f}°"
                f" ({m['grass_share']:.0f}% of px)")
    else:
        out += " | grass none"
    return out


def check(m):
    """The §6.12 targets that this image misses."""
    miss = []

    def need(ok, text):
        if not ok:
            miss.append(text)
    need(m["v"][0] >= 0.33, f"V p10 {m['v'][0]:.2f} < 0.33")
    need(0.50 <= m["v"][1] <= 0.62, f"V p50 {m['v'][1]:.2f} not in 0.50-0.62")
    need(m["L"][0] >= 28, f"L* p10 {m['L'][0]:.0f} < 28")
    need(52 <= m["L"][1] <= 62, f"L* p50 {m['L'][1]:.0f} not in 52-62")
    need(m["black"] <= 3, f"black {m['black']:.1f}% > 3%")
    need(m["L15"] < 1.5, f"L*<15 {m['L15']:.1f}% >= 1.5%")
    need(m["white"] <= 1.0, f"white-hot {m['white']:.2f}% > 1%")
    need(m["grit"] <= 0.035, f"grit {m['grit']:.3f} > 0.035")
    hard_max = 6.0 if m["dl8"] else 2.5
    need(m["hard"] <= hard_max, f"hard {m['hard']:.2f}% > {hard_max:g}%")
    need(0.48 <= m["s"] <= 0.62, f"S {m['s']:.2f} not in 0.48-0.62")
    if "grass" in m:
        need(59 <= m["grass_L"] <= 75, f"grass L* {m['grass_L']:.0f} not in 59-75")
        need(45 <= m["grass_S"] <= 62, f"grass S {m['grass_S']:.0f}% not in 45-62%")
        need(80 <= m["grass_h"] <= 95, f"grass hue {m['grass_h']:.0f}° not in 80-95°")
    else:
        miss.append("no grass pixels")
    return miss


def sample(full, r):
    """The sample line, or None when the rectangle misses the image."""
    x0, y0, x1, y1 = r
    h, w = full.shape[:2]
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    px = full[y0:y1, x0:x1].reshape(-1, 3)
    mean = px.mean(0)
    L, a, b = srgb_to_lab(mean)
    Ls = lightness(px)
    return (f"sample {x0},{y0},{x1},{y1}: {hexcol(mean)} L*a*b* {L:.1f} {a:+.1f} {b:+.1f}"
            f" | C* {np.hypot(a, b):.1f} h° {np.degrees(np.arctan2(b, a)) % 360:.0f}"
            f" | L* spread p10-p90 {np.percentile(Ls, 10):.0f}-{np.percentile(Ls, 90):.0f}")


def out_name(base, path, many):
    stem, ext = os.path.splitext(base)
    if many:
        stem += "_" + os.path.splitext(os.path.basename(path))[0]
    return stem + (ext or ".png")  # PIL picks the format from the extension


def save(img, dst, name, what):
    """Writes a derived copy; False (and a message) when it cannot be written."""
    try:
        img.save(dst)
    except (OSError, ValueError) as e:
        print(f"  {name} {what}: cannot write {dst} ({e})")
        return False
    print(f"  {name} {what} -> {dst}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="+")
    ap.add_argument("--crop", help="x0,y0,x1,y1 of the measured area (default: the map area of a 941x1672 shot)")
    ap.add_argument("--sample", action="append", default=[], help="x0,y0,x1,y1: mean colour of a rectangle")
    ap.add_argument("--gray", help="write a greyscale copy to this PNG")
    ap.add_argument("--deutan", help="write a deuteranopia simulation to this PNG")
    ap.add_argument("--check", action="store_true", help="list the §6.12 targets each image misses")
    args = ap.parse_args()
    crop = rect(args.crop, "--crop") if args.crop else None
    samples = [rect(t, "--sample") for t in args.sample]
    many = len(args.images) > 1
    failed = 0  # images with a problem: the exit status says so even when the lines scroll by
    for path in args.images:
        name = os.path.basename(path)
        try:
            im = Image.open(path).convert("RGB")
        except OSError as e:
            print(f"{name}: cannot read ({e})")
            failed += 1
            continue
        full = np.asarray(im).astype(np.float64) / 255
        if crop:
            x0, y0, x1, y1 = crop
        elif im.size == SHOT_SIZE:
            x0, y0, x1, y1 = MAP_CROP
        else:
            x0, y0, x1, y1 = 0, 0, im.size[0], im.size[1]
        a = full[y0:y1, x0:x1]
        if a.shape[0] < 2 or a.shape[1] < 2:
            print(f"{name}: crop {x0},{y0},{x1},{y1} is outside the {im.size[0]}x{im.size[1]} image")
            failed += 1
            continue
        ok = True
        m = measure(a, path)
        print(line(name, m))
        if args.check:
            miss = check(m)
            print(f"  {name} §6.12 misses: " + ("; ".join(miss) if miss else "none"))
        for r in samples:
            text = sample(full, r)
            if text is None:
                print(f"  {name} sample {','.join(map(str, r))}: outside the {im.size[0]}x{im.size[1]} image")
                ok = False
            else:
                print(f"  {name} {text}")
        if args.gray:
            Y = to_linear(full) @ LUMA
            g = (to_srgb(Y) * 255 + 0.5).astype(np.uint8)
            ok &= save(Image.fromarray(g, "L"), out_name(args.gray, path, many), name, "gray")
        if args.deutan:
            sim = to_srgb(to_linear(full) @ MACHADO_DEUTAN_1.T)
            ok &= save(Image.fromarray((sim * 255 + 0.5).astype(np.uint8), "RGB"),
                       out_name(args.deutan, path, many), name, "deutan")
        failed += not ok
    if failed:
        sys.stdout.flush()  # the per-image lines first, then the summary
        print(f"look_metrics: {failed} of {len(args.images)} image(s) had a problem (see above)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
