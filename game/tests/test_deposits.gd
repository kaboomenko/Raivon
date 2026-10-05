extends SceneTree
## Deposits and convoys (canon §5.2, §8.2). Run: godot --headless --path game --script res://tests/test_deposits.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const Deposits := preload("res://scripts/sim/deposits.gd")
const Types := preload("res://scripts/sim/types.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var w := MapGen.generate_chapter_one(20261004)
	var gross := {"gold": 170, "food": 60, "metal": 30}
	var d := Deposits.new(7)
	var t0 := 1_800_000_000
	d.tick(w, gross, t0)
	_check(d.active.size() == Deposits.quota(w), "quota filled: %d deposits (⌈hexes/8⌉ = %d)" % [d.active.size(), Deposits.quota(w)])
	var kinds := {}
	for dep in d.active:
		var c: Dictionary = w.cells[dep["hex"]]
		_check(Types.is_passable(c) and c["kind"] != "capital", "deposit on passable non-capital hex %d" % dep["hex"])
		kinds[dep["hex"]] = true
	_check(kinds.size() == d.active.size(), "one deposit per hex")
	# send a convoy to a deposit the player can reach
	var target := -1
	for dep in d.active:
		if d.can_send(w, dep["hex"], 1) == "":
			target = dep["hex"]
			break
	if target < 0:
		var own := -1
		for c in w.cells:
			if c["owner"] == Types.PLAYER and c["kind"] == "plain" and d.at(c["id"]).is_empty():
				own = c["id"]
				break
		d.spawn_at(w, own, "gold", "S", gross, t0)
		target = own
	var dep: Dictionary = d.at(target)
	var amount: int = dep["amount"]
	_check(d.send(w, target, 1, t0), "convoy sent")
	_check(d.can_send(w, target, 1) == "err.convoy_en_route", "one convoy per deposit")
	var cv: Dictionary = d.convoy_for(target)
	var mid := d.tick(w, gross, int(cv["back"]) - 1)
	var got := false
	for e in mid:
		if e["type"] == "convoy_back":
			got = true
	_check(not got, "no cargo before the convoy returns")
	var evs := d.tick(w, gross, int(cv["back"]))
	var cargo := 0
	for e in evs:
		if e["type"] == "convoy_back":
			cargo = e["amount"]
	_check(cargo == amount and d.at(target).is_empty(), "cargo delivered on return, deposit exhausted (%d)" % cargo)
	_check(d.active.size() == Deposits.quota(w) - 1 and d.pending_respawn.size() == 1, "exhausted deposit respawns later")
	d.tick(w, gross, int(cv["back"]) + Deposits.RESPAWN_MAX + 1)
	_check(d.active.size() == Deposits.quota(w), "respawned within 30–90 min (%d active, %d pending)" % [d.active.size(), d.pending_respawn.size()])
	# convoy limit
	var sent := 0
	for x in d.active:
		if d.send(w, x["hex"], 1, t0 + 10):
			sent += 1
	_check(sent <= Deposits.CONVOYS[1], "convoy limit by DL (%d sent)" % sent)
	# expiry: free deposits vanish after 12 h
	var free_before := 0
	for x in d.active:
		if int(x["convoy"]) < 0:
			free_before += 1
	var later := int(cv["back"]) + Deposits.RESPAWN_MAX + Deposits.LIFETIME + 5
	var ev2 := d.tick(w, gross, later)
	var expired := 0
	for e in ev2:
		if e["type"] == "expired":
			expired += 1
	_check(expired >= 1, "unclaimed deposits expire after 12 h (%d)" % expired)
	# FTUE fast convoy
	var d2 := Deposits.new(3)
	var own2 := -1
	for c in w.cells:
		if c["owner"] == Types.PLAYER and c["kind"] != "capital":
			own2 = c["id"]
			break
	d2.spawn_at(w, own2, "gold", "S", gross, t0)
	d2.send(w, own2, 1, t0, true)
	_check(int(d2.convoy_for(own2)["back"]) - t0 == 60, "FTUE convoy: 15 s + 30 s + 15 s")
	# save round trip
	var copy = Deposits.from_dict(JSON.parse_string(JSON.stringify(d.to_dict())), 7)
	_check(copy.active.size() == d.active.size() and copy.convoys.size() == d.convoys.size() and copy.rng.s0 == d.rng.s0, "save round trip")
	print("\n%s" % ("ALL DEPOSIT CHECKS PASSED" if fails == 0 else "%d FAILED" % fails))
	quit(1 if fails > 0 else 0)
