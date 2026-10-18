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
	var CmdPortrait = load("res://scripts/cmd_portrait.gd")
	_check(CmdPortrait.era_of(1) == 1 and CmdPortrait.era_of(3) == 1 and CmdPortrait.era_of(4) == 2 and CmdPortrait.era_of(7) == 3 and CmdPortrait.era_of(8) == 4, "portrait eras: DL1–3, 4–5, 6–7, 8+ (04 §15.4)")
	_portrait_checks(CmdPortrait)
	_battle_checks()
	print("ALL COMMANDER CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)


## The portrait's small-slot path (cmd_portrait.gd, docs/art_direction.md §7.12): the face crop of the very file the
## bust would draw — every commander in every era (calm) and Bram's smiles (the mail's advisor) — and none for a leader
## or another commander's smile (the bust is drawn then); a new era drops the old era's face entries; the FIT table
## covers every face crop, and its fits keep the headgear in (the chip's circle, the square slots' frame, the fan's rows
## above the card's name).
func _portrait_checks(CmdPortrait) -> void:
	var ids := ["cmd_bram", "cmd_lira", "cmd_olm", "cmd_vik", "cmd_vega", "cmd_kort", "cmd_seir", "cmd_frey", "cmd_irma",
		"cmd_hawk", "cmd_vance", "cmd_rai"]
	var keep_era: int = CmdPortrait.era
	var faces := 0
	var wrong: Array = []
	for e in [1, 2, 3, 4]:
		CmdPortrait.era = e
		for id in ids:
			var t: Texture2D = CmdPortrait._render_face(id, "")
			var want := "face_%s%s.png" % [id, "" if e == 1 else "_e%d" % e]
			if t != null and t.resource_path.ends_with(want):
				faces += 1
			else:
				wrong.append("%s E%d" % [id, e])
	_check(faces == 48, "a face crop for the 12 commanders × 4 eras, calm, each its own era's file (%d of 48%s)" % [faces,
		"" if wrong.is_empty() else "; not: " + ", ".join(wrong)])
	var smiles := 0
	for e in [1, 2, 3, 4]:
		CmdPortrait.era = e
		var t: Texture2D = CmdPortrait._render_face("cmd_bram", "smile")
		if t != null and t.resource_path.ends_with("face_cmd_bram%s_smile.png" % ("" if e == 1 else "_e%d" % e)):
			smiles += 1
	_check(smiles == 4, "Bram's smile has its face crop in every era (the mail's advisor): %d of 4" % smiles)
	CmdPortrait.era = 1
	var busts := true
	for id in ["cmd_lira", "cmd_rai", "cmd_vance"]:  # a smile render without a face crop of its own: the bust
		busts = busts and CmdPortrait._render_face(id, "smile") == null and CmdPortrait._render(id, "smile") != null
	_check(busts, "another commander's smile has no face crop: null, the bust is drawn")
	var ldr := true
	for id in ["ldr_alvaria", "ldr_barons", "ldr_lakes"]:
		ldr = ldr and CmdPortrait._render_face(id, "") == null and CmdPortrait._render_face(id, "angry") == null
	_check(ldr, "a leader has no face crop: null, the bust is drawn")
	CmdPortrait._render_face("cmd_bram", "")
	var had: bool = CmdPortrait._renders.keys().any(func(k): return String(k).begins_with("face|"))
	CmdPortrait.era = 2
	CmdPortrait._sync_era()
	var left: bool = CmdPortrait._renders.keys().any(func(k): return String(k).begins_with("face|"))
	_check(had and not left and CmdPortrait._renders.is_empty() and CmdPortrait._cache_era == 2,
		"a new era clears the face entries (and the rest of the old era's renders)")
	CmdPortrait.era = keep_era
	CmdPortrait._sync_era()
	# the FIT table: one entry per face crop shipped, its bust present
	var missing: Array = []
	for f in DirAccess.get_files_at("res://assets/ui/portraits"):
		var name := String(f)
		if name.begins_with("face_cmd_") and name.ends_with(".png"):
			var b := name.trim_prefix("face_").trim_suffix(".png")
			if not CmdPortrait.FIT.has(b) or not ResourceLoader.exists("res://assets/ui/portraits/%s.png" % b):
				missing.append(b)
	_check(missing.is_empty() and CmdPortrait.FIT.size() == 52, "FIT covers the 52 face crops and their busts%s" % (
		"" if missing.is_empty() else " (missing: " + ", ".join(missing) + ")"))
	# the fits: the chip's crop covers its circle's sides and bottom, the head ≥ 28 px (side ≥ 28 / 0.66 / 38 of the diameter); a square
	# slot's headgear 2 px under its 2 px frame; the fan's bust from the skyline (2 px under the frame) to the chin
	# within the rows over the card's name (50 in the middle, 44 on the sides: the cover scale may leave a px more)
	var bad: Array = []
	var cp: Control = CmdPortrait.new("cmd_bram", "common")
	cp.size = Vector2(48, 50)
	cp.circle = Rect2(5, 6, 38, 38)
	var sqs: Array = []
	for side in [72.0, 64.0]:
		var q: Control = CmdPortrait.new("cmd_bram", "common")
		q.size = Vector2(side, side)
		sqs.append(q)
	for b in CmdPortrait.FIT:
		var fit: Array = CmdPortrait.FIT[b]
		var r: Rect2 = cp._chip_fit(fit)
		var c: Rect2 = cp.circle  # (a lowered crop may leave the circle's top to the plate: that is its sky anyway)
		if r.position.x > c.position.x or r.end.x < c.end.x or r.end.y < c.end.y or r.size.x < 28.0 / 0.66 - 0.5:
			bad.append("%s chip %s" % [b, r])
		for q in sqs:
			var d: Rect2 = q._square_fit(fit, Rect2(Vector2.ZERO, q.size), Vector2(256, 256))
			var tip := d.position.y + float(fit[0]) * d.size.y / 256.0
			if tip < 2.0 * q.frame_w() - 0.01 or d.position.y > 4.0 or d.size.x < q.size.x:
				bad.append("%s square %d: tip %.1f" % [b, int(q.size.x), tip])
	for q in sqs:
		q.free()
	var fan: Control = CmdPortrait.new("cmd_bram", "common")
	fan.size = Vector2(58, 70)
	for hb in [20.0, 26.0]:
		fan.hidden_bottom = hb
		for b in CmdPortrait.FIT:
			var fit: Array = CmdPortrait.FIT[b]
			var d: Rect2 = fan._bust_fit(fit, Vector2(512, 588))
			var k := d.size.y / 588.0
			var sky := d.position.y + float(fit[3]) * k
			var chin := d.position.y + float(fit[4]) * k
			if sky < 4.0 - 0.6 or chin > 70.0 - hb + 1.2 or d.end.y < 70.0 - 0.01 or d.position.x > 0.01 or d.end.x < 57.99:
				bad.append("%s fan %d: sky %.1f chin %.1f" % [b, int(hb), sky, chin])
	cp.free()
	fan.free()
	_check(bad.is_empty(), "the fits keep the headgear in: the chip's circle covered (sides, bottom) and the head ≥ 28 px, the squares' 72 / 64 2 px gap, the fan's head over the name%s" % (
		"" if bad.is_empty() else " (" + ", ".join(bad.slice(0, 6)) + ")"))


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
