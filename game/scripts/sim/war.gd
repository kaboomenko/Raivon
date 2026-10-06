extends RefCounted
## War score, offensive stars, peace demands and treaty (canon §9.12–9.14, §10.1),
## port of packages/sim/src/war.ts.
##
## War (Dictionary):
##   {enemy:int, goal:int (player's war-goal hex, +10 while held), ai_goal:int (AI goal: most valuable
##    player border hex outside the core, -1 = none), enemy_value0:int, player_value0:int,
##    battles:int (battle points clamped to ±10), offensives:int}
## WarScore (Dictionary):
##   {score:float, occupation:float, losses:float, battles:int, goal:int, capital:int, control:int (%)}
## Demand (Dictionary):
##   {id:String ("pocket:i" | "annex:<cell>" | "contribution:i" | "reparations"),
##    kind:String ("annex"|"pocket"|"contribution"|"reparations"), hexes:Array[int], cost:float, label:String}
## TreatyResult (Dictionary): {annexed:Array[int], returned:Array[int], gold_packs:int, reparations:bool}

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Topology := preload("res://scripts/sim/topology.gd")
const World := preload("res://scripts/sim/world.gd")


static func _touches_controller(w: World, id: int, controller: int) -> bool:
	for n in w.neighbors[id]:
		if n >= 0 and w.cells[n]["controller"] == controller:
			return true
	return false


static func _touches_owner(w: World, id: int, owner: int) -> bool:
	for n in w.neighbors[id]:
		if n >= 0 and w.cells[n]["owner"] == owner:
			return true
	return false


static func _sort_value_desc(cells: Array) -> void:
	cells.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return a["value"] > b["value"] or (a["value"] == b["value"] and a["id"] < b["id"]))


## Suggested war goals: enemy border hexes outside its core touching the player, best first.
static func recommend_goals(w: World, enemy: int, n: int = 3) -> Array[int]:
	var core := MapGen.core_of(w, enemy)
	var border: Array = []
	for c in w.cells:
		if c["owner"] == enemy and Types.is_passable(c) and not core.has(c["id"]) and _touches_controller(w, c["id"], Types.PLAYER):
			border.append(c)
	_sort_value_desc(border)
	var out: Array[int] = []
	for i in mini(n, border.size()):
		out.append(border[i]["id"])
	return out


static func declare_war(w: World, enemy: int, goal: int) -> Dictionary:
	var player_core := MapGen.core_of(w, Types.PLAYER)
	var cands: Array = []
	for c in w.cells:
		if c["owner"] == Types.PLAYER and not player_core.has(c["id"]) and _touches_owner(w, c["id"], enemy):
			cands.append(c)
	_sort_value_desc(cands)
	return {
		"enemy": enemy,
		"goal": goal,
		"ai_goal": cands[0]["id"] if cands.size() > 0 else -1,
		"enemy_value0": MapGen.official_value(w, enemy),
		"player_value0": MapGen.official_value(w, Types.PLAYER),
		"battles": 0,
		"offensives": 0,
	}


## Enemy hexes inside the player's pockets count as occupation (canon §9.7).
static func enemy_pocket_hexes(w: World, war: Dictionary) -> Array[int]:
	var out: Array[int] = []
	for g in Topology.pockets(w, war["enemy"], Types.PLAYER):
		out.append_array(g)
	return out


static func war_score(w: World, war: Dictionary) -> Dictionary:
	var enemy: int = war["enemy"]
	var occ := 0
	var lost := 0
	var pocket_set := {}
	for id in enemy_pocket_hexes(w, war):
		pocket_set[id] = true
	for c in w.cells:
		if not Types.is_passable(c):
			continue
		if c["owner"] == enemy and (c["controller"] == Types.PLAYER or pocket_set.has(c["id"])):
			occ += c["value"]
		if c["owner"] == Types.PLAYER and c["controller"] == enemy:
			lost += c["value"]
	var occupation := Types.round1(float(occ * 100) / float(maxi(1, war["enemy_value0"])))
	var losses := Types.round1(float(lost * 100) / float(maxi(1, war["player_value0"])))
	var goal := 0
	if war["goal"] >= 0 and w.cells[war["goal"]]["controller"] == Types.PLAYER:
		goal += 10
	if war["ai_goal"] >= 0 and w.cells[war["ai_goal"]]["controller"] == enemy:
		goal -= 10
	var enemy_cap: int = w.states[enemy]["capital_id"]
	var capital := 20 if enemy_cap >= 0 and w.cells[enemy_cap]["controller"] == Types.PLAYER else 0
	var battles: int = war["battles"]
	if war.has("coalition") and battles > 0:
		battles = mini(20, battles * 2)  # «Триумф» (canon §10.8): won battles count double against a coalition
	var raw: float = occupation - losses + battles + goal + capital
	var score := Types.round1(clampf(raw, -100.0, 100.0))
	return {
		"score": score,
		"occupation": occupation,
		"losses": losses,
		"battles": battles,
		"goal": goal,
		"capital": capital,
		"control": Types.js_round(50.0 + score / 2.0),
	}


## ★ for any capture, ★★ with the flag hex, ★★★ with the flag hex and no routed armies.
static func offensive_stars(captured: Array, flag_hex: int, routed: int) -> int:
	if captured.is_empty():
		return 0
	if not captured.has(flag_hex):
		return 1
	return 3 if routed == 0 else 2


static func record_offensive(war: Dictionary, stars: int) -> void:
	var pts := -1 if stars == 0 else stars
	war["battles"] = clampi(int(war["battles"]) + pts, -10, 10)
	war["offensives"] = int(war["offensives"]) + 1


# ---------- peace ----------

static func hex_peace_cost(w: World, war: Dictionary, hex: int) -> float:
	return Types.round1(float(int(w.cells[hex]["value"]) * 100) / float(maxi(1, war["enemy_value0"])))


static func available_demands(w: World, war: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var core := MapGen.core_of(w, war["enemy"]) # decision 19: the enemy core is never demanded
	var groups: Array = []
	for g in Topology.pockets(w, war["enemy"], Types.PLAYER):
		var kept: Array[int] = []
		for id in g:
			if not core.has(id):
				kept.append(id)
		if not kept.is_empty():
			groups.append(kept)
	var in_pocket := {}
	for i in groups.size():
		var g: Array[int] = groups[i]
		var sum := 0.0
		for id in g:
			in_pocket[id] = true
			sum += hex_peace_cost(w, war, id)
		out.append({"id": "pocket:%d" % i, "kind": "pocket", "hexes": g, "cost": Types.round1(0.5 * sum),
			"label": "demand.pocket|%d" % g.size()})
	for c in w.cells:
		if c["owner"] != war["enemy"] or c["controller"] != Types.PLAYER or core.has(c["id"]) or in_pocket.has(c["id"]):
			continue
		var hexes: Array[int] = [c["id"]]
		out.append({"id": "annex:%d" % c["id"], "kind": "annex", "hexes": hexes, "cost": hex_peace_cost(w, war, c["id"]),
			"label": c["name"] if c["name"] != "" else "tile.hex"})
	for i in range(1, 4):
		out.append({"id": "contribution:%d" % i, "kind": "contribution", "hexes": [] as Array[int], "cost": 5.0,
			"label": "demand.contribution"})
	out.append({"id": "reparations", "kind": "reparations", "hexes": [] as Array[int], "cost": 5.0,
		"label": "demand.reparations"})
	return out


## «Самое ценное за доступные очки»: pockets first, then the goal, then hexes by value, then gold.
static func recommend_package(w: World, war: Dictionary, demands: Array, budget: float) -> Array[Dictionary]:
	var value := func(d: Dictionary) -> int:
		var v := 0
		for id in d["hexes"]:
			v += w.cells[id]["value"]
		return v
	var rank := func(d: Dictionary) -> int:
		if d["kind"] == "pocket":
			return 0
		if d["kind"] == "annex":
			return 1 if d["hexes"][0] == war["goal"] else 2
		return 3
	var order := demands.duplicate()
	Types.stable_sort(order, func(a: Dictionary, b: Dictionary) -> int:
		var r: int = rank.call(a) - rank.call(b)
		if r != 0:
			return r
		var v: int = value.call(b) - value.call(a)
		if v != 0:
			return v
		var ia: String = a["id"]
		var ib: String = b["id"]
		return -1 if ia < ib else (1 if ia > ib else 0))
	var chosen: Array[Dictionary] = []
	var left := budget
	for d in order:
		if d["cost"] <= left + 1e-9:
			chosen.append(d)
			left = Types.round1(left - d["cost"])
	return chosen


## Applies a victorious treaty for the player. Unclaimed occupations return to their owners.
static func apply_treaty(w: World, war: Dictionary, chosen: Array) -> Dictionary:
	var annex := {}
	for d in chosen:
		for id in d["hexes"]:
			annex[id] = true
	var returned: Array[int] = []
	for c in w.cells:
		if not Types.is_passable(c):
			continue
		if annex.has(c["id"]):
			c["owner"] = Types.PLAYER
			c["controller"] = Types.PLAYER
			c["fort"] = 0
		elif c["controller"] != c["owner"] and (c["owner"] == war["enemy"] or c["owner"] == Types.PLAYER):
			c["controller"] = c["owner"]
			returned.append(c["id"])
	var annexed: Array[int] = []
	for id in annex:
		annexed.append(id)
	annexed.sort()
	var gold := 0
	var reps := false
	for d in chosen:
		if d["kind"] == "contribution":
			gold += 1
		if d["kind"] == "reparations":
			reps = true
	return {"annexed": annexed, "returned": returned, "gold_packs": gold, "reparations": reps}


## White peace: every occupation returns.
static func white_peace(w: World) -> void:
	for c in w.cells:
		if Types.is_passable(c) and c["controller"] != c["owner"]:
			c["controller"] = c["owner"]
