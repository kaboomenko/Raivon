#!/usr/bin/env python3
"""UI lint for the Godot client (docs/ui_style.md §8.1). Stdlib only.

Rules:
  R1  a Color( literal in game_ui.gd, hud.gd, shop_ui.gd; in main.gd only inside the arguments of
      set_primary / set_action / show_choice / hex_label. ui_kit.gd (the tokens) is exempt.
  R2  a font size in _label( / Kit.label( / add_theme_font_size_override that is not on the type scale.
  R3  a radius in _style( / Kit.style( not in {0, 8, 14, 20, 24, 34} and below 40 (circles).
  R4  pictographs in strings.csv and in .gd string literals (emoji, symbols, arrows, geometric shapes,
      and ★☆✓✕‹›✎✦•).
  R5  a font size under 20, or a _fit floor under 20.
  R6  shadow_size above 2 (a soft glow: the «web» look).
  R7  modulate alpha used as the «disabled» look of a button.

Scans game/scripts/{game_ui,hud,shop_ui,main,map_view}.gd and game/locale/strings.csv.
Output: one `file:line RULE message` per finding, then the count per rule.
Usage: python3 tools/ui_lint.py [--strict]   (--strict: exit 1 when anything is found)
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "game"
SCRIPTS = ["game_ui.gd", "hud.gd", "shop_ui.gd", "main.gd", "map_view.gd"]
R1_FILES = {"game_ui.gd", "hud.gd", "shop_ui.gd"}
R1_MAIN_CALLS = ("set_primary", "set_action", "show_choice", "hex_label")
SCALE = {22, 24, 26, 28, 30, 32, 36, 40, 44, 46, 60, 64}
RADII = {0, 8, 14, 20, 24, 34}
PICTO_RANGES = [(0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2190, 0x21FF), (0x2B00, 0x2BFF), (0x25A0, 0x25FF)]
PICTO_CHARS = set("★☆✓✕‹›✎✦•")
RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]


def is_picto(ch: str) -> bool:
    c = ord(ch)
    return ch in PICTO_CHARS or c == 0xFE0F or any(a <= c <= b for a, b in PICTO_RANGES)


def mask(src: str):
    """Returns (code, strings): `code` is the source with comments blanked and string contents replaced by
    spaces (same length, so offsets and lines match); `strings` lists (offset, text) of every literal."""
    out = list(src)
    strings = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == "#":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
        elif c in "\"'":
            triple = src.startswith(c * 3, i)
            q = c * 3 if triple else c
            j = i + len(q)
            buf = []
            while j < n and not src.startswith(q, j):
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if src[j] == "\n" and not triple:
                    break
                buf.append(src[j])
                j += 1
            strings.append((i, "".join(buf)))
            for k in range(i + len(q), min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j + len(q)
        else:
            i += 1
    return "".join(out), strings


def line_of(src: str, off: int) -> int:
    return src.count("\n", 0, off) + 1


def call_args(code: str, open_idx: int):
    """Splits the arguments of the call whose '(' is at open_idx (code is masked, so strings and comments
    cannot confuse the depth). Returns ([(start, end), …], close_idx)."""
    depth = 0
    args = []
    start = open_idx + 1
    i = open_idx
    while i < len(code):
        ch = code[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                args.append((start, i))
                return args, i
        elif ch == "," and depth == 1:
            args.append((start, i))
            start = i + 1
        i += 1
    return args, len(code) - 1


INT_RE = re.compile(r"^\s*(\d+)\s*$")


def int_arg(code: str, span):
    m = INT_RE.match(code[span[0]:span[1]])
    return int(m.group(1)) if m else None


def lint_gd(path: Path, findings):
    src = path.read_text(encoding="utf-8")
    code, strings = mask(src)
    name = path.name
    rel = path.relative_to(ROOT)

    def add(off, rule, msg):
        findings.append((str(rel), line_of(src, off), rule, msg))

    # R1: Color( literals
    if name in R1_FILES:
        for m in re.finditer(r"\bColor\(", code):
            add(m.start(), "R1", "Color literal (use a Kit token)")
    elif name == "main.gd":
        for m in re.finditer(r"\b(%s)\(" % "|".join(R1_MAIN_CALLS), code):
            args, end = call_args(code, m.end() - 1)
            for c in re.finditer(r"\bColor\(", code[m.end():end]):
                add(m.end() + c.start(), "R1", "Color literal in %s() (pass a role)" % m.group(1))

    # R2 / R5: font sizes
    for m in re.finditer(r"(?<![\w.])(_label|Kit\.label|_inline|_title)\(", code):
        args, _ = call_args(code, m.end() - 1)
        if len(args) >= 2:
            v = int_arg(code, args[1])
            if v is not None:
                if v < 20:
                    add(m.start(), "R5", "font size %d under 20" % v)
                elif v not in SCALE:
                    add(m.start(), "R2", "font size %d off the scale" % v)
    for m in re.finditer(r"add_theme_font_size_override\(", code):
        args, _ = call_args(code, m.end() - 1)
        if len(args) >= 2:
            v = int_arg(code, args[1])
            if v is not None:
                if v < 20:
                    add(m.start(), "R5", "font size %d under 20" % v)
                elif v not in SCALE:
                    add(m.start(), "R2", "font size %d off the scale" % v)
    for m in re.finditer(r"(?<![\w.])_fit\(", code):
        args, _ = call_args(code, m.end() - 1)
        # game_ui: _fit(label, base, max_w); hud: _fit(label, text, max_w, base)
        idx = 3 if name == "hud.gd" else 1
        if len(args) > idx:
            v = int_arg(code, args[idx])
            if v is not None and v < 20:
                add(m.start(), "R5", "_fit base %d under 20" % v)
    for fm in re.finditer(r"^func\s+(\w*fit\w*)\(", code, re.M):
        body_end = code.find("\nfunc ", fm.end())
        body = code[fm.end(): body_end if body_end > 0 else len(code)]
        for wm in re.finditer(r"\b\w+\s*>\s*(\d+)\s+and\b", body):
            if int(wm.group(1)) < 20:
                add(fm.end() + wm.start(), "R5", "%s() floor %s under 20" % (fm.group(1), wm.group(1)))

    # R3: radii
    for m in re.finditer(r"(?<![\w.])(_style|Kit\.style)\(", code):
        args, _ = call_args(code, m.end() - 1)
        if len(args) >= 2:
            v = int_arg(code, args[1])
            if v is not None and v not in RADII and v < 40:
                add(m.start(), "R3", "radius %d off the set" % v)

    # R4: pictographs in string literals (ui_kit.gd keeps its table as escapes)
    for off, text in strings:
        bad = sorted({ch for ch in text if is_picto(ch)})
        if bad:
            add(off, "R4", "pictograph %s in a string literal" % " ".join(bad))

    # R6: soft shadows
    for m in re.finditer(r"shadow_size\s*=\s*(\d+)", code):
        if int(m.group(1)) > 2:
            add(m.start(), "R6", "shadow_size %s > 2" % m.group(1))

    # R7: modulate alpha as «disabled» (a partial alpha; 0.0 as a fade-in start is fine)
    def partial(expr: str) -> bool:
        return any(0.05 <= float(v) <= 0.99 for v in re.findall(r"(?<![\w.])(0?\.\d+)", expr))

    for m in re.finditer(r"\b(\w+)\.modulate(\.a)?\s*=\s*([^\n]*)", code):
        rhs = m.group(3)
        hit = False
        if m.group(2):
            hit = partial(rhs)
        else:
            for c in re.finditer(r"\bColor\(", rhs):
                args, _ = call_args(rhs, c.end() - 1)
                if len(args) == 4 and partial(rhs[args[3][0]:args[3][1]]):
                    hit = True
        if hit:
            add(m.start(), "R7", "%s.modulate alpha as a state (use the lock role)" % m.group(1))


def lint_csv(path: Path, findings):
    rel = path.relative_to(ROOT)
    with path.open(encoding="utf-8", newline="") as f:
        for ln, row in enumerate(csv.reader(f), start=1):
            if ln == 1 or not row:
                continue
            for cell in row[1:]:
                bad = sorted({ch for ch in cell if is_picto(ch)})
                if bad:
                    findings.append((str(rel), ln, "R4", "pictograph %s in %s" % (" ".join(bad), row[0])))
                    break


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    findings = []
    for s in SCRIPTS:
        p = GAME / "scripts" / s
        if p.exists():
            lint_gd(p, findings)
    lint_csv(GAME / "locale" / "strings.csv", findings)
    findings.sort(key=lambda f: (f[0], f[1], f[2]))
    for f, ln, rule, msg in findings:
        print("%s:%d %s %s" % (f, ln, rule, msg))
    counts = {r: 0 for r in RULES}
    for _, _, rule, _ in findings:
        counts[rule] += 1
    print("---")
    print("  ".join("%s %d" % (r, counts[r]) for r in RULES) + "  total %d" % len(findings))
    return 1 if strict and findings else 0


if __name__ == "__main__":
    sys.exit(main())
