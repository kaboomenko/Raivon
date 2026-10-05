extends SceneTree
## Army march on the strategic map (canon §8.1). Run: godot --headless --path game --script res://tests/test_march.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const March := preload("res://scripts/sim/march.gd")
const Types := preload("res://scripts/sim/types.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var w := MapGen.generate_chapter_one(20261004)
	var cap: int = w.states[Types.PLAYER]["capital_id"]
	# farthest own hex from the capital by marching time
	var far := -1
	var far_s := 0
	var wild := -1
	var enemy := -1
	for c in w.cells:
		var id: int = c["id"]
		if c["owner"] == Types.PLAYER and id != cap and March.route(w, Types.PLAYER, cap, id).is_empty():
			_check(false, "own hex %d reachable" % id)
		if id != cap and Types.is_passable(c):
			var r := March.route(w, Types.PLAYER, cap, id)
			if not r.is_empty() and int(r["seconds"]) > far_s:
				far = id
				far_s = r["seconds"]
		if c["owner"] == Types.NOBODY and Types.is_passable(c) and wild < 0:
			wild = id
		elif c["owner"] == MapGen.BARONS and enemy < 0:
			enemy = id
	var nb: int = w.neighbors[cap][0]
	_check(March.route(w, Types.PLAYER, cap, nb)["seconds"] == March.OWN_SEC, "own land costs 20 s per hex")
	var r: Dictionary = March.route(w, Types.PLAYER, cap, far)
	var legs := 0
	for h in r["path"]:
		legs += March.leg_seconds(w, Types.PLAYER, h)
	_check((r["path"] as Array).back() == far and legs == far_s and (r["path"] as Array).size() >= 3, "path to the farthest hex %d: %d legs, %d s" % [far, (r["path"] as Array).size(), far_s])
	_check(March.route(w, Types.PLAYER, cap, enemy).is_empty(), "no route into another state's land")
	_check(March.leg_seconds(w, Types.PLAYER, wild) == March.OTHER_SEC, "wild land costs 40 s")
	_check(March.route(w, Types.PLAYER, cap, cap).is_empty(), "no route to the same hex")
	# occupied enemy hex: passable at 40 s
	var occ := enemy
	w.cells[occ]["controller"] = Types.PLAYER
	_check(March.leg_seconds(w, Types.PLAYER, occ) == March.OTHER_SEC, "occupied hex costs 40 s")
	w.cells[occ]["controller"] = MapGen.BARONS
	# march step by step
	var army := {"id": 1, "side": Types.PLAYER, "hex": cap, "str": 75000, "max_str": 75000}
	var t0 := 1_800_000_000
	var o := March.order(w, army, far, t0)
	_check(not o.is_empty() and March.is_marching(army), "march ordered")
	_check(March.seconds_left(w, army, t0) == far_s, "time left = route time")
	_check(not March.step(w, army, t0 + 19) and int(army["hex"]) == cap, "still on the first leg after 19 s")
	var p := March.progress(army, t0 + March.leg_seconds(w, Types.PLAYER, int(o["path"][0])) / 2.0)
	_check(absf(float(p["f"]) - 0.5) < 0.01 and int(p["to"]) == int(o["path"][0]), "halfway along the first leg")
	var first_leg := March.leg_seconds(w, Types.PLAYER, int(o["path"][0]))
	March.step(w, army, t0 + first_leg)
	_check(int(army["hex"]) == int(o["path"][0]), "first hex reached after its leg")
	_check(March.step(w, army, t0 + far_s) and int(army["hex"]) == far and not March.is_marching(army), "arrives exactly on time")
	# a hex lost mid-route ends the march where the army stands
	if (o["path"] as Array).size() >= 3:
		var army2 := {"id": 2, "side": Types.PLAYER, "hex": cap, "str": 1, "max_str": 1}
		March.order(w, army2, far, t0)
		var second: int = o["path"][1]
		w.cells[second]["controller"] = MapGen.BARONS
		_check(March.step(w, army2, t0 + far_s) and int(army2["hex"]) == int(o["path"][0]), "blocked route: stops on the last hex reached")
		w.cells[second]["controller"] = Types.PLAYER
	# deterministic
	_check(March.route(w, Types.PLAYER, cap, far) == March.route(w, Types.PLAYER, cap, far), "routing is deterministic")
	print("ALL MARCH CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
