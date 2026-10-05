extends SceneTree
## Marauder camps (canon §5.1, 02 §13, 03 §5.7). Run: godot --headless --path game --script res://tests/test_camps.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const Camps := preload("res://scripts/sim/camps.gd")
const Battle := preload("res://scripts/sim/battle.gd")
const Armies := preload("res://scripts/sim/armies.gd")
const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _dist(w, a: int, b: int) -> int:
	return HexGrid.distance(Vector2i(int(w.cells[a]["q"]), int(w.cells[a]["r"])), Vector2i(int(w.cells[b]["q"]), int(w.cells[b]["r"])))


func _initialize() -> void:
	var w := MapGen.generate_chapter_one(20261004)
	var t0 := 1_800_000_000
	var c := Camps.new(42)
	var goal := Camps.target(w)
	_check(goal >= 2 and goal <= 4, "camps target clamp(round(wild/5), 2, 4) = %d" % goal)
	c.tick(w, {}, t0)
	_check(c.active.size() == goal, "initial fill: %d camps" % c.active.size())
	var caps: Array = []
	for st in w.states:
		if int(st["capital_id"]) >= 0:
			caps.append(int(st["capital_id"]))
	for cm in c.active:
		var h: int = cm["hex"]
		_check(w.cells[h]["owner"] == Types.NOBODY and Types.is_passable(w.cells[h]), "camp %d on a wild passable hex" % h)
		for cap in caps:
			if _dist(w, h, cap) < 2:
				_check(false, "≥2 from capital %d" % cap)
		for o in c.active:
			if o != cm and _dist(w, h, int(o["hex"])) < 3:
				_check(false, "≥3 between camps")
	var c2 := Camps.new(42)
	c2.tick(w, {}, t0)
	_check(c2.to_dict() == c.to_dict(), "deterministic placement")
	# garrison grows with camps beaten today
	var g0 := c.garrison(75000, t0)
	_check(g0 == 45000, "garrison 0.6 × average max strength (%d)" % g0)
	var gross := {"gold": 160, "food": 45, "metal": 30}
	var h0: int = c.active[0]["hex"]
	var r0: String = c.active[0]["res"]
	var rw := c.defeat(h0, gross, t0)
	_check(rw["res"] == r0 and int(rw["amount"]) == maxi(Camps.MIN_REWARD, int(gross[r0])), "reward = 1 h gross of the shown resource (%s %d)" % [r0, int(rw["amount"])])
	_check(c.at(h0).is_empty() and c.active.size() == goal - 1, "camp removed")
	_check(c.garrison(75000, t0) == 54000, "next garrison +20% after a beaten camp")
	c.tick(w, {}, t0 + 100)
	_check(c.active.size() == goal - 1, "no respawn before 4 h")
	c.tick(w, {}, t0 + Camps.RESPAWN_SEC)
	_check(c.active.size() == goal, "respawn after 4 h")
	# daily cap
	for i in 2:
		c.defeat(int(c.active[0]["hex"]), gross, t0 + 10)
	var last := c.defeat(int(c.active[0]["hex"]), gross, t0 + 20)
	_check(int(last["amount"]) == 0 and c.rewards_left(t0 + 20) == 0, "4th camp of the day pays nothing")
	_check(c.rewards_left(t0 + 86400) == 3, "rewards reset next day")
	# save round trip
	var c3 := Camps.new(1)
	c3.load_dict(JSON.parse_string(JSON.stringify(c.to_dict())))
	_check(c3.to_dict() == c.to_dict(), "save round trip")
	# camp fight: only the camp hex is a target, the battle ends when the raiders break
	var w2 := MapGen.generate_chapter_one(20261004)
	var cc := Camps.new(5)
	cc.tick(w2, {}, t0)
	var camp := -1
	var src := -1
	for cm in cc.active:
		for n in w2.neighbors[int(cm["hex"])]:
			if n >= 0 and w2.cells[n]["owner"] == Types.PLAYER:
				camp = cm["hex"]
				src = n
	if camp < 0:
		# make one attackable: give the player a neighbour of the first camp
		camp = cc.active[0]["hex"]
		for n in w2.neighbors[camp]:
			if n >= 0 and Types.is_passable(w2.cells[n]):
				src = n
				w2.cells[n]["owner"] = Types.PLAYER
				w2.cells[n]["controller"] = Types.PLAYER
				break
	var army := Armies.infantry_army(1, Types.PLAYER, src, 1, 1)
	var b := Battle.new(w2, [army], {"attacker": Types.PLAYER, "defender": Types.NOBODY, "ai_energy_mult": 0, "cards": ["attack"], "camp": camp, "ticks": Camps.FIGHT_TICKS})
	b.garrison[camp] = cc.garrison(int(army["max_str"]), t0)
	var other := -1
	for x in w2.cells:
		if x["owner"] == Types.NOBODY and Types.is_passable(x) and int(x["id"]) != camp and w2.neighbors[src].has(int(x["id"])):
			other = x["id"]
	_check(b.can_target(Types.PLAYER, camp), "camp hex is a target")
	_check(other < 0 or not b.can_target(Types.PLAYER, other), "other wild hexes are not")
	b.issue(Types.PLAYER, {"t": "attack", "army": 1, "target": camp})
	while not b.over:
		b.step()
	_check(b.end_reason == "camp" and b.tick < Camps.FIGHT_TICKS, "raiders broken at %.1f s (army %d vs garrison %d)" % [b.tick / 10.0, int(army["max_str"]) / 1000, cc.garrison(int(army["max_str"]), t0) / 1000])
	print("ALL CAMP CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
