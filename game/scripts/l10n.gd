extends RefCounted
## Localization helpers on top of Godot's TranslationServer. Strings live in res://locale/strings.csv
## (columns keys,ru,en; imported into strings.ru/en.translation and registered in project.godot).
##
## The sim never translates: names and refusal reasons come out of it as translation keys, optionally
## with arguments packed as "key|arg|arg" (e.g. "err.need_hexes|10"). `t()` turns such a string into
## player text at the UI edge; arguments that are keys themselves (state / cell / resource names) are
## translated too, numeric ones become numbers for %d / %.1f.

## Supported languages, in the order of the Settings switch.
const LANGS: Array[String] = ["ru", "en"]
## Device languages that get the Russian UI by default; every other device starts in English.
const RU_DEVICE_LANGS: Array[String] = ["ru", "uk", "be", "kk"]
const LANG_NAMES := {"ru": "Русский", "en": "English"}


## Default language for this device (OS.get_locale_language()).
static func device_lang() -> String:
	return "ru" if RU_DEVICE_LANGS.has(OS.get_locale_language()) else "en"


## Switches the UI language ("" or an unknown code → the device default).
static func apply(lang: String) -> void:
	TranslationServer.set_locale(lang if LANGS.has(lang) else device_lang())


## Current UI language: "ru" or "en".
static func lang() -> String:
	return "ru" if TranslationServer.get_locale().begins_with("ru") else "en"


## Translates a key, or a packed "key|arg|…" string, into the current language. Plain text without a
## matching key (old saves, already translated text) comes back unchanged.
static func t(s: String) -> String:
	if s == "":
		return ""
	if not s.contains("|"):
		return String(TranslationServer.translate(s))
	var parts := s.split("|")
	var fmt := String(TranslationServer.translate(parts[0]))
	var args: Array = []
	for i in range(1, parts.size()):
		var a: String = parts[i]
		if a.is_valid_int():
			args.append(int(a))
		elif a.is_valid_float():
			args.append(float(a))
		else:
			args.append(String(TranslationServer.translate(a)))
	return fmt % args


## A count with its noun in the right form (docs/ui_style.md §3.7): «1 осколок», «4 осколка», «5 осколков» /
## «1 shard», «4 shards». Reads `<key>.one` / `.few` / `.many` in Russian and `<key>.one` / `.other` in English; each
## form may hold %d for the number. A missing form falls back to `<key>` itself (the plural form, %d too).
static func plural(n: int, key: String) -> String:
	var form := "other"
	var a := absi(n)
	if lang() == "ru":
		var m10 := a % 10
		var m100 := a % 100
		if m10 == 1 and m100 != 11:
			form = "one"
		elif m10 >= 2 and m10 <= 4 and (m100 < 12 or m100 > 14):
			form = "few"
		else:
			form = "many"
	elif a == 1:
		form = "one"
	var k := key + "." + form
	var f := String(TranslationServer.translate(k))
	if f == k:  # no such form: the base key
		f = String(TranslationServer.translate(key))
	return f % n if f.contains("%d") else f


## Packs a key with arguments for `t()` (used for texts stored and translated later, e.g. the inbox).
static func pack(key: String, args: Array = []) -> String:
	var parts := PackedStringArray([key])
	for a in args:
		parts.append(str(a))
	return "|".join(parts)
