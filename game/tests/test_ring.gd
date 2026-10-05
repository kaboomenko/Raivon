extends SceneTree
## Chapter II ring (canon §12.1, 02 §15). Run: godot --headless --path game --script res://tests/test_ring.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const RingGen := preload("res://scripts/sim/ring_gen.gd")
const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var t := Time.get_ticks_msec()
	var w := MapGen.generate_chapter_one(20261004)
	var old_n := w.cells.size()
	var old_cells: Array = []
	for c in w.cells:
		old_cells.append(c.duplicate())
	_check(RingGen.extend_chapter_two(w, 20261004 ^ 0x2), "ring II generated in %d ms" % (Time.get_ticks_msec() - t))
	var land := 0
	for c in w.cells:
		if Types.is_passable(c):
			land += 1
	_check(land == 90, "world land 50 + 40 = %d" % land)
	var same := true
	for i in old_n:
		for k in ["q", "r", "terrain", "kind", "owner"]:
			if w.cells[i][k] != old_cells[i][k]:
				same = false
	_check(same, "old cells unchanged (02 §17.2)")
	var sizes := {}
	for c in w.cells:
		if Types.is_passable(c):
			sizes[int(c["owner"])] = int(sizes.get(int(c["owner"]), 0)) + 1
	_check(sizes.get(RingGen.LEAGUE, 0) == 16 and sizes.get(RingGen.ORDER, 0) == 14, "League 16, Order 14 (%s)" % str(sizes))
	for s in [RingGen.LEAGUE, RingGen.ORDER]:
		var cap: int = w.states[s]["capital_id"]
		_check(cap >= old_n and w.cells[cap]["kind"] == "capital" and w.cells[cap]["owner"] == s, "state %d capital on the ring" % s)
		_check(MapGen.core_of(w, s).size() >= 5, "state %d has a core" % s)
	var kinds := {}
	for i in range(old_n, w.cells.size()):
		var k: String = w.cells[i]["kind"]
		kinds[k] = int(kinds.get(k, 0)) + 1
	_check(kinds.get("port", 0) == 2 and kinds.get("city", 0) == 2 and kinds.get("farm", 0) == 3 and kinds.get("mine", 0) == 3 and kinds.get("military_base", 0) == 1, "special hexes by quota %s" % str(kinds))
	for i in range(old_n, w.cells.size()):
		if w.cells[i]["kind"] == "port":
			var wet := false
			for n in w.neighbors[i]:
				if n >= 0 and w.cells[n]["terrain"] == "water":
					wet = true
			_check(wet, "port %d by the water" % i)
	# topology: old rim cells now see ring neighbours
	var linked := false
	for i in old_n:
		for n in w.neighbors[i]:
			if n >= old_n:
				linked = true
	_check(linked, "topology rebuilt across the old rim")
	# player core never borders a new state
	for id in MapGen.core_of(w, Types.PLAYER):
		for n in w.neighbors[id]:
			if n >= 0 and int(w.cells[n]["owner"]) in [RingGen.LEAGUE, RingGen.ORDER]:
				_check(false, "player core touches a new state at %d" % n)
	# deterministic
	var w2 := MapGen.generate_chapter_one(20261004)
	RingGen.extend_chapter_two(w2, 20261004 ^ 0x2)
	var eq := w2.cells.size() == w.cells.size()
	for i in mini(w.cells.size(), w2.cells.size()):
		if w.cells[i] != w2.cells[i]:
			eq = false
	_check(eq, "deterministic")
	_check(RingGen.extend_chapter_two(w, 1) and w.cells.size() == w2.cells.size(), "idempotent")
	# several seeds succeed
	var ok := 0
	for sd in range(1, 11):
		var w3 := MapGen.generate_chapter_one(20261004)
		if RingGen.extend_chapter_two(w3, sd * 7777):
			ok += 1
	_check(ok == 10, "ring found for 10/10 seeds (%d)" % ok)
	print("ALL RING CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
