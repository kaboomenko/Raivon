extends SceneTree
# temporary probe (s09): L.plural forms
func _initialize() -> void:
	var L = load("res://scripts/l10n.gd")
	for lang in ["ru", "en"]:
		TranslationServer.set_locale(lang)
		var out := PackedStringArray()
		for n in [0, 1, 2, 4, 5, 11, 12, 15, 21, 22, 25, 101, 111]:
			out.append(L.plural(n, "plural.shards"))
		print(lang, ": ", " | ".join(out))
	quit()
