extends SceneTree
## Commander levels (04 §15.5). Run: godot --headless --path game --script res://tests/test_commanders.gd

const Commanders := preload("res://scripts/sim/commanders.gd")
const Cases := preload("res://scripts/sim/cases.gd")
const Battle := preload("res://scripts/sim/battle.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Armies := preload("res://scripts/sim/armies.gd")
const Types := preload("res://scripts/sim/types.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _gold_to(lvl: int) -> int:
	var g := 0
	for l in range(2, lvl + 1):
		g += int(Commanders.GOLD[l - 2])
	return g


func _initialize() -> void:
	# the totals of 04 §15.5
	_check(Commanders.spent("common", 16) == 112 and Commanders.spent("rare", 16) == 153 and Commanders.spent("epic", 16) == 196 and Commanders.spent("legendary", 16) == 284, "shards with the unlock to level 16: 112 / 153 / 196 / 284")
	_check(Commanders.spent("common", 20) == 199 and Commanders.spent("rare", 20) == 263 and Commanders.spent("epic", 20) == 327 and Commanders.spent("legendary", 20) == 458, "to level 20: 199 / 263 / 327 / 458")
	_check(_gold_to(16) == 59700 and _gold_to(20) == 137500, "gold: 59 700 to level 16, 137 500 to 20")
	_check(Commanders.level_cap(1) == 2 and Commanders.level_cap(8) == 16 and Commanders.level_cap(12) == 20, "level ≤ 2 × DL, at most 20")
	_check(is_equal_approx(Commanders.value(5.0, 15.0, 10), 9.736) and is_equal_approx(Commanders.value(5.0, 15.0, 16), 12.894), "v(L) linear, ×1000 rounded down: 9.736 at 10, 12.894 at 16")
	_check(is_equal_approx(Commanders.value(1.5, 2.0, 20), 2.0) and is_equal_approx(Commanders.value(5.0, 15.0, 1), 5.0), "v(1) = v1, v(20) = v20")
	for id in Commanders.PASSIVES:
		_check(not Cases.commander(String(id)).is_empty(), "%s exists" % id)
	var in_albums := {}
	for a in Commanders.ALBUMS:
		for c in a[1]:
			in_albums[c] = true
	_check(in_albums.size() == 12 and Commanders.PASSIVES.size() == 12, "12 commanders, each in exactly one album")

	var m := Commanders.new()
	_check(m.level("cmd_bram", "common", 9) == 0 and m.block_reason("cmd_bram", "common", 9, 9999, 8) == "locked", "9 of 10 shards: locked")
	_check(m.level("cmd_bram", "common", 10) == 1 and m.free_shards("cmd_bram", "common", 10) == 0, "10 shards open him at level 1, nothing left")
	_check(m.next_cost("cmd_bram", "common", 10) == [1, 250, 1], "level 2: 1 shard + 250 gold, DL1")
	_check(m.block_reason("cmd_bram", "common", 10, 9999, 8) == "shards", "no spare shard")
	_check(m.block_reason("cmd_bram", "common", 11, 100, 8) == "gold", "no gold")
	_check(m.upgrade("cmd_bram", "common", 11, 300, 1) == 250 and m.level("cmd_bram", "common", 11) == 2, "level 2 bought for 250 gold")
	_check(m.block_reason("cmd_bram", "common", 99, 99999, 1) == "dl", "level 3 needs DL2")
	var g := 0
	while m.block_reason("cmd_bram", "common", 999, 999999, 8) == "":
		g += m.upgrade("cmd_bram", "common", 999, 999999, 8)
	_check(m.level("cmd_bram", "common", 999) == 16 and g == _gold_to(16) - 250, "DL8 stops at level 16")
	_check(m.free_shards("cmd_bram", "common", 999) == 999 - 112, "the spare shards stay")
	_check(not Commanders.maxed("rare", 262) and Commanders.maxed("rare", 263), "maxed once the shards reach level 20")
	_check(Commanders.album_of("cmd_rai") == "founder" and Commanders.album_of("cmd_kort") == "staff", "albums")
	var q := Commanders.new()
	q.load_dict(m.to_dict())
	_check(q.level("cmd_bram", "common", 999) == 16, "save and load")
	# assignment (04 §15.6): one army per commander, moving takes it off the old army
	var asg := Commanders.new()
	asg.assign(1, "cmd_bram")
	asg.assign(2, "cmd_bram")
	_check(asg.cmd_of(1) == "" and asg.cmd_of(2) == "cmd_bram" and asg.army_of("cmd_bram") == 2, "a commander leads one army")
	asg.assign(1, "cmd_frey")
	asg.keep_armies([1])
	_check(asg.army_of("cmd_bram") == -1 and asg.cmd_of(1) == "cmd_frey", "a lost army frees its commander")
	var asg2 := Commanders.new()
	asg2.load_dict(asg.to_dict())
	_check(asg2.cmd_of(1) == "cmd_frey", "assignments survive a save")
	_battle_checks()
	print("ALL COMMANDER CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)


## The passives in the battle engine: attack, wedge, home defence, start energy, a cheaper landing.
func _battle_checks() -> void:
	var w := MapGen.generate_chapter_one(20261004)
	var target := -1
	var srcs: Array = []
	for c in w.cells:
		if c["controller"] != MapGen.BARONS or c["kind"] != "plain":
			continue
		srcs = []
		for n in w.neighbors[c["id"]]:
			if n >= 0 and w.cells[n]["controller"] == Types.PLAYER:
				srcs.append(n)
		if srcs.size() >= 2:
			target = c["id"]
			break
	_check(target >= 0, "a hex with a two-hex front")
	var a1 := Armies.infantry_army(1, Types.PLAYER, int(srcs[0]), 3, 1)
	var a2 := Armies.infantry_army(2, Types.PLAYER, int(srcs[1]), 3, 1)
	var d := Armies.infantry_army(101, MapGen.BARONS, target, 3, 1)
	var b := Battle.new(w, [a1, a2, d], {"attacker": Types.PLAYER, "defender": MapGen.BARONS, "ai_energy_mult": 0, "cards": [], "energy_bonus": 1, "landing_discount": 1})
	var m0: int = b.forecast(Types.PLAYER, [1], target)["atk_might"]
	a1["cmd_atk"] = 100
	var m1: int = b.forecast(Types.PLAYER, [1], target)["atk_might"]
	_check(m1 == m0 * 1100 / 1000, "+10%% attack: Might ×1.1 (%d → %d)" % [m0, m1])
	a1.erase("cmd_atk")
	var w0: int = b.forecast(Types.PLAYER, [1, 2], target)["atk_might"]
	a2["cmd_wedge"] = 74
	var w1: int = b.forecast(Types.PLAYER, [1, 2], target)["atk_might"]
	_check(w1 > w0, "Vega's wedge bonus lifts both armies of the wedge (%d → %d)" % [w0, w1])
	_check(b.energy_points(Types.PLAYER) == 6, "Lady Vance: +1 energy at the start")
	_check(b._cost({"t": "card", "card": "landing"}, Types.PLAYER) == 3 and b._cost({"t": "card", "card": "landing"}, MapGen.BARONS) == 4, "Admiral Seir: «Десант» costs 3 for the player only")
	var dm0: int = b._def_mult(target, d, b.forms_for(Types.PLAYER, target, [srcs[0]]))
	d["cmd_home"] = 97
	var dm1: int = b._def_mult(target, d, b.forms_for(Types.PLAYER, target, [srcs[0]]))
	_check(dm1 == dm0 + 97, "Colonel Frey: +9.7% defence on an own official hex")
	d.erase("cmd_home")
	a2.erase("cmd_wedge")
	a2["cmd_forms"] = 74
	_check(b.forecast(Types.PLAYER, [1, 2], target)["atk_might"] == w1, "Emperor Rai adds the same to the Wedge")
	var sf := b.forms_for(Types.PLAYER, target, [srcs[0]])
	sf["salient"] = true
	var sm0: int = b._def_mult(target, d, sf)
	d["cmd_forms"] = 74
	_check(b._def_mult(target, d, sf) == sm0 + 74, "his own hex: the Salient penalty shrinks by v")
