extends RefCounted
## Battle AI — a small utility scorer (canon §9.16), port of packages/sim/src/ai.ts.
## Decides once per 0.5 s. Never targets the player's core (enforced by Battle.can_target).
## Usage: var ai := BattleAI.new(side); each tick: ai.think(battle); battle.step()

const Types := preload("res://scripts/sim/types.gd")
const Battle := preload("res://scripts/sim/battle.gd")

var side: int
var _last_move: Dictionary = {} # army id -> tick of the last move order


func _init(p_side: int) -> void:
	side = p_side


func think(b: Battle) -> void:
	if b.over or b.tick % 5 != 0:
		return
	var energy: int = b.energy.get(side, 0)
	var enemy := b.enemy_of(side)

	# 1. Shore up a defended hex that is losing.
	if energy >= int(Battle.CARDS["defense"]["cost"]) * Battle.ENERGY_UNIT and b.card_ready(side, "defense"):
		for cl in b.clashes:
			if cl["side"] != enemy or cl["entering"] > 0 or b.has_effect("defense", cl["target"]):
				continue
			var fc := b.forecast(enemy, cl["attackers"], cl["target"])
			var cell: Dictionary = b.world.cells[cl["target"]]
			if fc["f"] >= 0.95 and (cl["defender"] != -1 or cell["value"] >= 2):
				b.issue(side, {"t": "card", "card": "defense", "target": cl["target"]})
				return

	# 2. Attack the best target.
	if energy >= int(Battle.CARDS["attack"]["cost"]) * Battle.ENERGY_UNIT:
		var best: Dictionary = {}
		var seen := {}
		for a in b.armies:
			if a["side"] != side or a["routed"] or a["move"] != null or b.attacking(a) != null:
				continue
			for t in b.world.neighbors[a["hex"]]:
				if t < 0 or seen.has(t) or not b.can_target(side, t):
					continue
				seen[t] = true
				var list := b.adjacent_idle_armies(side, t)
				var ids: Array = []
				for x in list:
					ids.append(x["id"])
				var fc := b.forecast(side, ids, t)
				var cell: Dictionary = b.world.cells[t]
				var recapture := 0.6 if cell["owner"] == side else 0.0
				var score: float = fc["f"] + cell["value"] * 0.08 + recapture
				if fc["f"] >= 1.25 and (best.is_empty() or score > best["score"]):
					best = {"target": t, "armies": list, "score": score}
		if not best.is_empty():
			var list: Array = best["armies"]
			if list.size() >= 2 and b.card_ready(side, "attack"):
				b.issue(side, {"t": "card", "card": "attack", "target": best["target"]})
			else:
				b.issue(side, {"t": "attack", "army": list[0]["id"], "target": best["target"]})
			return

	# 3. Reposition idle armies toward threatened frontier hexes.
	_reposition(b, enemy)


func _reposition(b: Battle, enemy: int) -> void:
	var threatened := {}
	for a in b.armies:
		if a["side"] != enemy or a["routed"]:
			continue
		for n in b.world.neighbors[a["hex"]]:
			if n >= 0 and b.world.cells[n]["controller"] == side and b.army_at(n, side) == null:
				threatened[n] = true
	if threatened.is_empty():
		return
	for a in b.armies:
		if a["side"] != side or a["routed"] or a["move"] != null or b.attacking(a) != null:
			continue
		if int(_last_move.get(a["id"], -999)) > b.tick - 30:
			continue
		# Already on the front line? stay.
		var on_front := false
		for n in b.world.neighbors[a["hex"]]:
			if n >= 0 and b.world.cells[n]["controller"] == enemy:
				on_front = true
				break
		if on_front:
			continue
		var stp := _step_toward(b, a, threatened)
		if stp >= 0 and b.issue(side, {"t": "move", "army": a["id"], "to": stp}):
			_last_move[a["id"]] = b.tick
			return


## First hex of the shortest own-controlled path from the army to any goal, or -1.
func _step_toward(b: Battle, a: Dictionary, goals: Dictionary) -> int:
	var start: int = a["hex"]
	var prev := {start: -1}
	var queue: Array[int] = [start]
	var head := 0
	while head < queue.size():
		var id: int = queue[head]
		head += 1
		if id != start and goals.has(id):
			var cur := id
			while prev[cur] != start:
				cur = prev[cur]
			return cur
		for n in b.world.neighbors[id]:
			if n < 0 or prev.has(n):
				continue
			var c: Dictionary = b.world.cells[n]
			if not Types.is_passable(c) or c["controller"] != side:
				continue
			prev[n] = id
			queue.append(n)
	return -1
