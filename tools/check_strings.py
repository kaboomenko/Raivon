#!/usr/bin/env python3
"""Localization lint for the Godot client (game/).

Fails (exit 1) when:
  * a string literal in game/scripts/**/*.gd contains Cyrillic outside comments (player text must go
    through tr("key") and game/locale/strings.csv), unless it is on the ALLOW list below;
  * a key used in tr("…") / L.t("…") / TranslationServer.translate("…"), or a key-like literal such as
    "err.need_hexes|%d" or "bld.farm" (sim modules return keys), is missing from strings.csv;
  * strings.csv is malformed: header other than keys,ru,en, a non-ASCII or duplicate key, an empty ru or
    en cell, or ru / en with different printf placeholders (%d, %s, %+.1f, …);
  * an entry of game/data/cases.json with a Russian name has no name_en (and categories /
    res_names have no _en twin).

Usage: python3 tools/check_strings.py   (from anywhere; paths are relative to the repo root)
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAME = ROOT / "game"
CSV_PATH = GAME / "locale" / "strings.csv"
CASES_PATH = GAME / "data" / "cases.json"

# Cyrillic literals that are deliberately not translated: (file relative to game/, literal).
ALLOW = {
    ("scripts/l10n.gd", "Русский"),  # language endonym on the Settings switch, same in every UI language
}

CYR = re.compile(r"[Ѐ-ӿ]")
KEY_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")
CALL_RE = re.compile(r"(?:\btr|\bL\.t|TranslationServer\.translate)\(\s*$")
# GDScript format specifiers (flags -, +, 0; conversions s c d o x X f v)
PLACEHOLDER = re.compile(r"%(?:%|[-+0]*\d*(?:\.\d+)?[scdoxXfv])")


def literals(src: str):
    """Yields (line, text, prefix) for every string literal outside comments; prefix is the source
    text before the literal on its line (to recognise tr( calls)."""
    i, n, line = 0, len(src), 1
    line_start = 0
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            line_start = i
        elif c == "#":
            while i < n and src[i] != "\n":
                i += 1
        elif c in "\"'":
            prefix = src[line_start:i]
            if i > 0 and src[i - 1] in "&^":  # StringName / NodePath literals
                prefix = prefix[:-1]
            triple = src.startswith(c * 3, i)
            q = c * 3 if triple else c
            j = i + len(q)
            buf = []
            start_line = line
            while j < n and not src.startswith(q, j):
                if src[j] == "\\" and j + 1 < n:
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if src[j] == "\n":
                    line += 1
                buf.append(src[j])
                j += 1
            yield start_line, "".join(buf), prefix
            i = j + len(q)
        else:
            i += 1


def placeholders(s: str):
    return [p for p in PLACEHOLDER.findall(s) if p != "%%"]


def main() -> int:
    errors = []
    warnings = []

    # ---- strings.csv
    keys = {}
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != ["keys", "ru", "en"]:
        errors.append("strings.csv: header must be keys,ru,en (got %r)" % (rows[0] if rows else None))
    for num, row in enumerate(rows[1:], start=2):
        if len(row) != 3:
            errors.append("strings.csv:%d: expected 3 columns, got %d" % (num, len(row)))
            continue
        k, ru, en = row
        if not KEY_RE.match(k):
            errors.append("strings.csv:%d: key %r is not a lowercase ASCII dotted id" % (num, k))
        if k in keys:
            errors.append("strings.csv:%d: duplicate key %r" % (num, k))
        if not ru.strip() or not en.strip():
            errors.append("strings.csv:%d: %s has an empty ru or en cell" % (num, k))
        for lang, cell in (("ru", ru), ("en", en)):
            # a formatted string (it has placeholders) must escape every other % as %%
            if placeholders(cell) and "%" in PLACEHOLDER.sub("", cell):
                errors.append("strings.csv:%d: %s (%s) has a bare %% next to placeholders: write %%%%" % (num, k, lang))
        if placeholders(ru) != placeholders(en):
            errors.append("strings.csv:%d: %s placeholders differ: ru %s vs en %s"
                          % (num, k, placeholders(ru), placeholders(en)))
        keys[k] = (ru, en)
    prefixes = {k.split(".")[0] for k in keys}

    # ---- scripts
    used = set()
    for path in sorted((GAME / "scripts").rglob("*.gd")):
        rel = path.relative_to(GAME).as_posix()
        for line, text, prefix in literals(path.read_text(encoding="utf-8")):
            if CYR.search(text) and (rel, text) not in ALLOW:
                errors.append("%s:%d: Cyrillic string literal %r (use tr(\"key\"))" % (rel, line, text))
            key = text.split("|", 1)[0]
            if text.endswith("."):
                continue  # a key prefix completed at run time: tr("res.gen." + res)
            if CALL_RE.search(prefix):
                used.add(key)
                if key not in keys:
                    errors.append("%s:%d: tr key %r is missing from strings.csv" % (rel, line, key))
            elif KEY_RE.match(key) and key.split(".")[0] in prefixes:
                used.add(key)
                if key not in keys:
                    errors.append("%s:%d: key-like literal %r is missing from strings.csv" % (rel, line, key))

    # keys built at run time from a literal prefix ("res.gen." + res) count as used
    dynamic = ("res.gen.", "res.short.")
    unused = sorted(k for k in keys if k not in used and not k.startswith(dynamic))
    if unused:
        warnings.append("strings.csv keys not referenced by a literal: " + ", ".join(unused))

    # ---- cases.json
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def walk(node, where):
        if isinstance(node, dict):
            for field in ("name_ru", "name"):
                v = node.get(field)
                if isinstance(v, str) and CYR.search(v) and not node.get("name_en"):
                    errors.append("cases.json %s: %r has no name_en" % (where, v))
            for k, v in node.items():
                walk(v, where + "." + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (where, i))

    walk(data, "")
    for ru_key, en_key in (("categories", "categories_en"), ("res_names", "res_names_en")):
        missing = set(data.get(ru_key, {})) - set(data.get(en_key, {}))
        if missing:
            errors.append("cases.json: %s lacks %s" % (en_key, sorted(missing)))
    if "set_name_ru" in data.get("cases", {}).get("case_collection", {}) and \
            "set_name_en" not in data["cases"]["case_collection"]:
        errors.append("cases.json: case_collection has no set_name_en")

    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("error:", e)
    print("%d keys in strings.csv, %d referenced from scripts; %d error(s)" % (len(keys), len(used), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
