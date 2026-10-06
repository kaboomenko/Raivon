extends SceneTree
## Chapter III ring «Континент» (canon §12.1, 02 §15.3–15.5). Run: godot --headless --path game --script res://tests/test_ring3.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const RingGen := preload("res://scripts/sim/ring_gen.gd")
const RingNext := preload("res://scripts/sim/ring_next.gd")
const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _world(seed_value: int):
	var w = MapGen.generate_chapter_one(seed_value)
	RingGen.extend_chapter_two(w, seed_value ^ 0x2)
	return w


func _initialize() -> void:
	var w = _world(20261004)
	var old_n: int = w.cells.size()
	var old_cells: Array = []
	for c in w.cells:
		old_cells.append(c.duplicate())
	var t := Time.get_ticks_msec()
	_check(RingNext.extend_chapter_three(w, 20261004 ^ 0x3), "ring III generated in %d ms (%s)" % [Time.get_ticks_msec() - t, RingNext.last_fail])
	var land := 0
	for c in w.cells:
		if Types.is_passable(c):
			land += 1
	_check(land == 160, "world land 90 + 70 = %d" % land)
	var same := true
	for i in old_n:
		for k in ["q", "r", "terrain", "kind", "owner"]:
			if w.cells[i][k] != old_cells[i][k]:
				same = false
	_check(same, "old cells unchanged (02 §17.2)")
	var sizes := {}
	var wild := 0
	for i in range(old_n, w.cells.size()):
		var c: Dictionary = w.cells[i]
		if Types.is_passable(c):
			sizes[int(c["owner"])] = int(sizes.get(int(c["owner"]), 0)) + 1
			if int(c["owner"]) == Types.NOBODY:
				wild += 1
	_check(sizes.get(RingNext.ALVARIA, 0) == 22 and sizes.get(RingNext.SAREN, 0) == 15 and sizes.get(RingNext.PACK, 0) == 15, "Alvaria 22, Saren 15, Pack 15 (%s)" % str(sizes))
	_check(wild == 18, "18 wild hexes (%d)" % wild)
	_check(String(w.states[RingNext.PACK]["archetype"]) == "raven" and bool(w.states[RingNext.ALVARIA]["hegemon"]), "Raven and the hegemon")
	var caps: Array[Vector2i] = []
	for st in w.states:
		if int(st["capital_id"]) >= 0:
			caps.append(Vector2i(int(w.cells[int(st["capital_id"])]["q"]), int(w.cells[int(st["capital_id"])]["r"])))
	var spaced := true
	for a in caps.size():
		for b in range(a + 1, caps.size()):
			if HexGrid.distance(caps[a], caps[b]) < 5:
				spaced = false
	_check(spaced and caps.size() == 8, "8 capitals, ≥5 apart")
	for s in [RingNext.ALVARIA, RingNext.SAREN, RingNext.PACK]:
		var cap: int = w.states[s]["capital_id"]
		_check(cap >= old_n and w.cells[cap]["kind"] == "capital" and w.cells[cap]["owner"] == s, "state %d capital on the ring" % s)
		# F2: a farm and a mine of its own within 3 hexes of the capital
		var cv := Vector2i(int(w.cells[cap]["q"]), int(w.cells[cap]["r"]))
		var has := {}
		for c in w.cells:
			if int(c["owner"]) == s and HexGrid.distance(Vector2i(int(c["q"]), int(c["r"])), cv) <= 3:
				has[String(c["kind"])] = true
		_check(has.has("farm") and has.has("mine"), "F2: state %d has a farm and a mine near the capital" % s)
		var core := MapGen.core_of(w, s)
		var clean := true
		for id in core:
			if String(w.cells[id]["kind"]) in ["oil", "raivite_vein"]:
				clean = false
		_check(clean, "F4/F9: no oil or vein in the core of state %d" % s)
	var kinds := {}
	for i in range(old_n, w.cells.size()):
		var k: String = w.cells[i]["kind"]
		kinds[k] = int(kinds.get(k, 0)) + 1
	_check(kinds.get("port", 0) == 3 and kinds.get("oil", 0) == 3 and kinds.get("factory", 0) == 2 and kinds.get("city", 0) == 4 \
		and kinds.get("military_base", 0) == 2 and kinds.get("farm", 0) == 6 and kinds.get("mine", 0) == 6 and kinds.get("raivite_vein", 0) == 1,
		"special hexes by quota 02 §15.4 %s" % str(kinds))
	for i in range(old_n, w.cells.size()):
		var c: Dictionary = w.cells[i]
		if c["kind"] == "port":
			var wet := false
			for n in w.neighbors[i]:
				if n >= 0 and w.cells[n]["terrain"] == "water":
					wet = true
			_check(wet, "port %d by the water" % i)
		if int(c["owner"]) == Types.NOBODY and Types.is_passable(c):
			_check(String(c["kind"]) in ["plain", "farm", "mine"], "F10: wild hex %d is ordinary, a farm or a mine (%s)" % [i, c["kind"]])
		_check(String(c["name"]) != "" or c["kind"] == "plain", "named special %d" % i)
	_check(RingNext.extend_chapter_three(w, 1), "idempotent")
	_check(w.cells.size() == old_n + 86, "nothing added twice (%d new cells)" % (w.cells.size() - old_n))
	# deterministic and valid for other seeds
	var a = _world(77)
	var b = _world(77)
	RingNext.extend_chapter_three(a, 77 ^ 0x3)
	RingNext.extend_chapter_three(b, 77 ^ 0x3)
	var fa := ""
	var fb := ""
	for c in a.cells:
		fa += "%d%s%d," % [c["q"], c["kind"], c["owner"]]
	for c in b.cells:
		fb += "%d%s%d," % [c["q"], c["kind"], c["owner"]]
	_check(fa == fb, "same seed, same ring")
	var ok := 0
	for s in 6:
		var x = _world(1000 + s)
		if RingNext.extend_chapter_three(x, (1000 + s) ^ 0x3):
			ok += 1
		else:
			print("  seed %d: %s" % [1000 + s, RingNext.last_fail])
	_check(ok == 6, "6 of 6 other seeds give a valid ring")
	print("ALL RING III CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
