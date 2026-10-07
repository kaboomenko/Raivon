extends SceneTree
## «Летопись державы» (07 §7). Run: godot --headless --path game --script res://tests/test_chronicle.gd

const Chronicle := preload("res://scripts/sim/chronicle.gd")
const Cases := preload("res://scripts/sim/cases.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var rv := 0
	var cos := 0
	var codes := {}
	for row in Chronicle.LIST:
		rv += int(row[4])
		codes[row[0]] = true
		if String(row[5]) != "":
			cos += 1
			_check(not Cases.cosmetic(String(row[5])).is_empty(), "cosmetic %s exists" % row[5])
	_check(Chronicle.LIST.size() == 40 and codes.size() == 40, "40 distinct goals")
	_check(rv == 665 and cos == 6, "665 Raivites and 6 cosmetics in all (07 §7.3)")
	var c := Chronicle.new()
	_check(c.update({"peaces": 1, "@hexes": 10}) == ["ach_first_peace"], "the first peace is reached, announced once")
	_check(c.update({"peaces": 1, "@hexes": 10}).is_empty(), "nothing new on the next tick")
	_check(c.claimable() == 1 and c.claim("ach_first_peace") == [25, ""] and c.claim("ach_first_peace").is_empty(), "claimed once for 25")
	c.update({"@hexes": 26})
	c.update({"@hexes": 12})
	_check(c.can_claim("ach_hexes_25") and c.progress("ach_hexes_25") == 25, "a live measure that drops keeps the goal reached")
	c.update({"blueprints": 99, "arena_league": 9})
	_check(c.reached.has("ach_blueprints_25") and not c.reached.has("ach_arena_legend"), "«soon» goals don't count yet; blueprints do")
	var q := Chronicle.new()
	q.load_dict(c.to_dict())
	_check(q.claimed.has("ach_first_peace") and q.can_claim("ach_hexes_25") and q.progress("ach_hexes_25") == 25, "save and load")
	var ord := Chronicle.new()
	ord.update({"peaces": 1})
	ord.update({"@hexes": 25})
	_check(ord.recent(3) == ["ach_hexes_25", "ach_first_peace"], "the latest goals, newest first")
	var ord2 := Chronicle.new()
	ord2.load_dict(ord.to_dict())
	_check(ord2.order == ord.order, "the order survives a save")
	print("ALL CHRONICLE CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
