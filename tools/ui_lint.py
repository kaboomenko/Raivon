#!/usr/bin/env python3
r"""UI lint for the Godot client (docs/ui_style.md §8.1). Stdlib only.

Rules:
  R1  a Color( literal in game_ui.gd, hud.gd, shop_ui.gd; in main.gd only inside the arguments of
      set_primary / set_action / show_choice / hex_label. ui_kit.gd (the tokens) is exempt.
  R2  a font size in _label( / Kit.label( / add_theme_font_size_override that is not on the type scale.
  R3  a radius in _style( / Kit.style( not in {0, 8, 14, 20, 24, 34} and below 40 (circles).
  R4  pictographs (emoji, symbols, arrows, geometric shapes, technical symbols, icon-font glyphs, and ★☆✓✕‹›✎✦•)
      in strings.csv, in the strings of game/data/*.json and in .gd code, however they are spelt: the character
      itself, an escape in a literal ("\u2694", "\U01F48E", a JSON-style "\\u2694"), a code point turned into
      text (char(0x2694), String.chr(9876), "%c" % 0x2694, literal bytes through get_string_from_utf8()), or a %c
      placeholder in strings.csv. char() / String.chr() / "%c" whose code point the lint cannot work out (a variable)
      count too: write the character, or a literal code point, so it can be checked. The decoders that turn old
      pictographs into icons are the only exceptions (R4_ALLOW). Every script under game/scripts/ is checked.
  R5  a font size under 20, or a _fit floor under 20.
  R6  shadow_size above 2 (a soft glow: the «web» look).
  R7  modulate alpha used as the «disabled» look of a button.

Scans game/scripts/{game_ui,hud,shop_ui,main,map_view}.gd (all rules), the other game/scripts/**/*.gd (R4 only),
game/locale/strings.csv and game/data/*.json (R4).
Output: one `file:line RULE message` per finding, then the count per rule.
Usage: python3 tools/ui_lint.py [--strict]   (--strict: exit 1 when anything is found)
CI (.github/workflows/tests.yml, step «UI lint») runs it with --strict: the tree must stay at total 0.
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
PICTO_RANGES = [(0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2190, 0x21FF), (0x2B00, 0x2BFF), (0x25A0, 0x25FF),
                (0x2300, 0x23FF), (0x27F0, 0x27FF), (0x2900, 0x297F), (0xE000, 0xF8FF), (0x2139, 0x2139),
                (0x20E3, 0x20E3), (0x24C2, 0x24C2), (0x3030, 0x3030), (0x303D, 0x303D), (0x3297, 0x3299)]
# (technical ⏱⏩⌛, more arrows ⟶⤴, icon-font private use, and the stray emoji ℹ Ⓜ 〰 〽 ㊗ ㊙ and the keycap)
PICTO_CHARS = set("★☆✓✕‹›✎✦•")
RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
# R4 exceptions: (script, const) whose value may hold pictographs. Only decoders that turn an old pictograph into an
# icon (never drawn as a glyph) belong here; anything else is a finding.
R4_ALLOW = {
    ("ui_kit.gd", "PICTO"): "Kit.split_icons: legacy pictograph → icon name / vector chrome",
    ("map_view.gd", "MAP_PICTO"): "in-world labels: legacy pictograph → 3D icon (docs/ui_style.md §4.14)",
    # The drag forecast's commander mark: SoftLabel3D draws U+2605 as the gold-star icon, never as a glyph. Debt: an
    # icon argument on MapView.soft_label would retire it (map_view.gd + main._cmd_mark, outside the lint's reach).
    ("main.gd", "CMD_MARK"): "soft_label marker U+2605 → the xp icon (MAP_PICTO)",
}


def is_picto(ch: str) -> bool:
    return is_picto_code(ord(ch))


def is_picto_code(c: int) -> bool:
    if not 0 <= c <= 0x10FFFF:
        return False
    return chr(c) in PICTO_CHARS or c == 0xFE0F or any(a <= c <= b for a, b in PICTO_RANGES)


ESC_RE = re.compile(r"\\(?:u([0-9a-fA-F]{4})|U([0-9a-fA-F]{6})|(.))", re.S)


def unescape(raw: str) -> str:
    """The text a GDScript literal holds: \\uXXXX (UTF-16 surrogate pairs joined), \\UXXXXXX and the one-letter
    escapes; `raw` is the literal's source between the quotes."""
    units = []

    def flush(out):
        i = 0
        while i < len(units):
            u = units[i]
            if 0xD800 <= u <= 0xDBFF and i + 1 < len(units) and 0xDC00 <= units[i + 1] <= 0xDFFF:
                out.append(chr(0x10000 + ((u - 0xD800) << 10) + (units[i + 1] - 0xDC00)))
                i += 2
                continue
            out.append(chr(u) if u < 0x110000 else "\ufffd")
            i += 1
        units.clear()

    out = []
    pos = 0
    simple = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", "\"": "\"",
              "'": "'", "\n": ""}
    for m in ESC_RE.finditer(raw):
        if m.start() > pos:
            flush(out)
            out.append(raw[pos:m.start()])
        if m.group(1):
            units.append(int(m.group(1), 16))
        else:
            flush(out)
            if m.group(2):
                c = int(m.group(2), 16)
                out.append(chr(c) if c < 0x110000 else "\ufffd")
            else:
                out.append(simple.get(m.group(3), m.group(3)))
        pos = m.end()
    flush(out)
    out.append(raw[pos:])
    return "".join(out)


JSON_ESC_RE = re.compile(r"\\u([0-9a-fA-F]{4})")


def picto_in_text(text: str):
    """Pictographs a piece of text holds, also behind a JSON-style \\uXXXX still in it (decoded at run time)."""
    bad = {ch for ch in text if is_picto(ch)}
    bad |= {chr(int(h, 16)) for h in JSON_ESC_RE.findall(text) if is_picto_code(int(h, 16))}
    return sorted(bad)


def int_value(expr: str, consts: dict):
    """The int an expression of int literals, names of this file's int consts and + - * // | << >> works out to;
    None when it is not that simple."""
    import ast
    try:
        node = ast.parse(expr.strip(), mode="eval").body
    except SyntaxError:
        return None

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.Name) and n.id in consts:
            return consts[n.id]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return None if v is None else (-v if isinstance(n.op, ast.USub) else v)
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if a is None or b is None:
                return None
            ops = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
                   ast.FloorDiv: lambda: a // b if b else None, ast.BitOr: lambda: a | b,
                   ast.LShift: lambda: a << b if 0 <= b < 32 else None, ast.RShift: lambda: a >> b if b >= 0 else None}
            f = ops.get(type(n.op))
            return f() if f else None
        return None

    return ev(node)


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

    lint_r4(src, code, strings, name, add)

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


CONST_RE = re.compile(r"^[ \t]*(?:static[ \t]+)?const[ \t]+(\w+)\b[^=\n]*?:?=", re.M)
INT_DECL_RE = re.compile(r"^[ \t]*(?:static[ \t]+)?(?:const|var)[ \t]+(\w+)[ \t]*(?::[ \t]*int[ \t]*)?:?=[ \t]*([^\n]+)$", re.M)
CHR_RE = re.compile(r"(?<![\w.])(?:char|String\.chr)\(")
BYTES_RE = re.compile(r"\bPackedByteArray\(\s*\[")
BYTES_DECODE_RE = re.compile(r"\s*\)\s*\.\s*get_string_from_(utf8|utf16|utf32|wchar|ascii)\s*\(")
FMT_RE = re.compile(r"%[-+0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?([scdoxXfv])")
CODEC = {"utf8": "utf-8", "utf16": "utf-16-le", "utf32": "utf-32-le", "wchar": "utf-32-le", "ascii": "latin-1"}


def fmt_convs(text: str):
    """The conversions of a format string in order ('s', 'd', 'c', …), %% skipped."""
    return [m.group(1) for m in FMT_RE.finditer(text.replace("%%", ""))]


def lint_r4(src: str, code: str, strings, name: str, add):
    """R4 over one script: pictographs in its string literals however they are spelt, and code points turned into
    text (char(), String.chr(), "%c" %, literal bytes decoded). Inside an R4_ALLOW const nothing is reported."""
    allow = []
    for m in CONST_RE.finditer(code):
        if (name, m.group(1)) not in R4_ALLOW:
            continue
        i = m.end()
        while i < len(code) and code[i] in " \t":
            i += 1
        if i < len(code) and code[i] in "[{(":
            _, end = call_args(code, i)
        else:
            end = code.find("\n", i)
            end = len(code) if end < 0 else end
        allow.append((m.start(), end + 1))

    def report(off, msg):
        if not any(a <= off < b for a, b in allow):
            add(off, "R4", msg)

    consts = {}
    for m in INT_DECL_RE.finditer(code):
        v = int_value(src[m.start(2):m.end(2)].split("#", 1)[0], consts)
        if v is not None:
            consts[m.group(1)] = v

    def show(chars):
        return " ".join("%s (U+%04X)" % (c, ord(c)) for c in chars)

    for off, raw in strings:
        q = 3 if src.startswith(src[off] * 3, off) else 1
        is_raw = off > 0 and src[off - 1] == "r" and (off < 2 or not (src[off - 2].isalnum() or src[off - 2] == "_"))
        text = raw if is_raw else unescape(raw)
        bad = picto_in_text(text)
        if bad:
            spelt = [c for c in bad if c in raw]
            how = "" if len(spelt) == len(bad) else " written as an escape"
            report(off, "pictograph %s%s in a string literal" % (show(bad), how))
        convs = fmt_convs(text)
        if "c" not in convs:
            continue
        # "%c" % operand: the code points it formats must be literal and not pictographs
        end = off + 2 * q + len(raw)
        m = re.compile(r"\s*%\s*").match(code, end)
        if not m:
            report(off, "a %c format whose code point the lint cannot see (write the character instead)")
            continue
        j = m.end()
        if j < len(code) and code[j] == "[":
            spans, _ = call_args(code, j)
            items = [src[a:b] for a, b in spans]
        else:
            t = re.compile(r"[\w.]+(?:\([^()\n]*\))?").match(code, j)
            items = [src[j:t.end()]] if t else []
        for k, conv in enumerate(convs):
            if conv != "c":
                continue
            v = int_value(items[k], consts) if k < len(items) else None
            if v is None:
                report(off, "a %c format whose code point the lint cannot work out (use a literal)")
            elif is_picto_code(v):
                report(off, "pictograph U+%04X through a %%c format" % v)

    for m in CHR_RE.finditer(code):
        spans, _ = call_args(code, m.end() - 1)
        arg = src[spans[0][0]:spans[0][1]] if len(spans) == 1 else ""
        v = int_value(arg, consts) if arg.strip() else None
        fn = m.group(0)[:-1]
        if v is None:
            report(m.start(), "%s() with a code point the lint cannot work out (write the character or a literal)" % fn)
        elif is_picto_code(v):
            report(m.start(), "pictograph %s through %s()" % (show([chr(v)]), fn))

    for m in BYTES_RE.finditer(code):
        spans, close = call_args(code, m.end() - 1)
        d = BYTES_DECODE_RE.match(code, close + 1)
        if not d:
            continue
        vals = [int_value(src[a:b], consts) for a, b in spans if src[a:b].strip()]
        if not vals or any(v is None or not 0 <= v <= 255 for v in vals):
            continue
        bad = picto_in_text(bytes(vals).decode(CODEC[d.group(1)], "replace"))
        if bad:
            report(m.start(), "pictograph %s from literal bytes (get_string_from_%s)" % (show(bad), d.group(1)))


def lint_r4_file(path: Path, findings):
    src = path.read_text(encoding="utf-8")
    code, strings = mask(src)
    rel = path.relative_to(ROOT)
    lint_r4(src, code, strings, path.name,
            lambda off, rule, msg: findings.append((str(rel), line_of(src, off), rule, msg)))


def lint_csv(path: Path, findings):
    rel = path.relative_to(ROOT)
    with path.open(encoding="utf-8", newline="") as f:
        for ln, row in enumerate(csv.reader(f), start=1):
            if ln == 1 or not row:
                continue
            for cell in row[1:]:
                bad = picto_in_text(cell)
                if bad:
                    findings.append((str(rel), ln, "R4", "pictograph %s in %s" % (" ".join(bad), row[0])))
                    break
                if "c" in fmt_convs(cell):
                    findings.append((str(rel), ln, "R4", "%%c placeholder in %s (a code point formatted at run time)"
                                     % row[0]))
                    break


def lint_json(path: Path, findings):
    """R4 over a data file: every string (keys too) after JSON decoding, so escapes count."""
    import json
    rel = path.relative_to(ROOT)
    raw = path.read_text(encoding="utf-8")
    lines = raw.split("\n")

    def where(text):
        for probe in (json.dumps(text, ensure_ascii=False)[1:-1][:24], json.dumps(text)[1:-1][:24]):
            for i, ln in enumerate(lines, start=1):
                if probe and probe in ln:
                    return i
        return 1

    def walk(node):
        items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else []
        for k, v in items:
            for t in ([k] if isinstance(k, str) else []) + ([v] if isinstance(v, str) else []):
                bad = picto_in_text(t)
                if bad:
                    findings.append((str(rel), where(t), "R4", "pictograph %s in a data string" % " ".join(bad)))
            walk(v)

    walk(json.loads(raw))


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    findings = []
    for s in SCRIPTS:
        p = GAME / "scripts" / s
        if p.exists():
            lint_gd(p, findings)
    for p in sorted((GAME / "scripts").rglob("*.gd")):
        if p.parent != GAME / "scripts" or p.name not in SCRIPTS:
            lint_r4_file(p, findings)
    lint_csv(GAME / "locale" / "strings.csv", findings)
    for p in sorted((GAME / "data").glob("*.json")):
        lint_json(p, findings)
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
