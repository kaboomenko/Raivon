extends SceneTree
## Balance probe: chapter I first war with player bots of different skill (FTUE offensive: 60 s, enemy plays
## no cards). Prints captured hexes, war score and what the recommended treaty annexes.
## Run: godot --headless --path game --script /abs/path/tools/balance/first_war.gd

const MapGen := preload("res://scripts/sim/map_gen.gd")
const Armies := preload("res://scripts/sim/armies.gd")
const War := preload("res://scripts/sim/war.gd")
const Battle := preload("res://scripts/sim/battle.gd")
const BattleAI := preload("res://scripts/sim/battle_ai.gd")
const Types := preload("res://scripts/sim/types.gd")


## skill: seconds between orders (a slow player issues fewer orders), min forecast to attack, use cards?
func play(seed_value: int, interval_ticks: int, min_f: float, cards: bool, ai_mult: int, ticks: int) -> Dictionary:
	var w := MapGen.generate_chapter_one(seed_value)
	var armies := Armies.starting_armies(w)
	var war := War.declare_war(w, MapGen.BARONS, War.recommend_goals(w, MapGen.BARONS, 1)[0])
	var b := Battle.new(w, armies, {"attacker": Types.PLAYER, "defender": MapGen.BARONS, "ai_energy_mult": ai_mult,
		"cards": ["attack", "breakthrough", "airstrike", "encircle", "defense"], "ticks": ticks})
	var ai := BattleAI.new(MapGen.BARONS)
	while not b.over:
		if b.tick % interval_ticks == 0:
			var best := -1
			var best_f := 0.0
			var best_army := -1
			for c in w.cells:
				if not b.can_target(Types.PLAYER, c["id"]):
					continue
				var ids: Array = []
				for a in b.adjacent_idle_armies(Types.PLAYER, c["id"]):
					ids.append(a["id"])
				if ids.is_empty():
					continue
				var f: float = b.forecast(Types.PLAYER, ids, c["id"])["f"]
				if f >= min_f and (best < 0 or f > best_f):
					best = c["id"]
					best_f = f
					best_army = ids[0]
			if best >= 0:
				if cards:
					b.issue(Types.PLAYER, {"t": "card", "card": "attack", "target": best})
				else:
					b.issue(Types.PLAYER, {"t": "attack", "army": best_army, "target": best})
		ai.think(b)
		b.step()
	var res := b.result()
	var stars := War.offensive_stars(res["captured"], war["goal"], res["routed_player_armies"])
	War.record_offensive(war, stars)
	var ws := War.war_score(w, war)
	var demands := War.available_demands(w, war)
	var pkg := War.recommend_package(w, war, demands, ws["score"])
	var annexed := 0
	for d in pkg:
		annexed += (d["hexes"] as Array).size()
	return {"captured": res["captured"].size(), "score": ws["score"], "annexed": annexed}


func _initialize() -> void:
	var profiles := [
		["expert (order every 2 s, cards)", 20, 1.2, true],
		["average (order every 5 s, drag)", 50, 1.0, false],
		["casual (order every 10 s, drag)", 100, 0.9, false],
		["new (order every 15 s, drag)", 150, 0.8, false],
	]
	for p in profiles:
		var caps := []
		var anns := []
		var scores := []
		for seed_value in [20261004]:
			for variant in 1:
				var r := play(seed_value, int(p[1]), float(p[2]), bool(p[3]), 0, 600)
				caps.append(r["captured"])
				anns.append(r["annexed"])
				scores.append(r["score"])
		print("%-36s captured %s  annexed %s  score %s" % [p[0], str(caps), str(anns), str(scores)])
	quit()
