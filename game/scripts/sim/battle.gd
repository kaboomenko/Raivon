extends RefCounted
## Real-time offensive simulation (canon §9.2–9.9, docs/gdd/03_war_combat.md), port of
## packages/sim/src/battle.ts. 10 Hz, integer fixed point: Strength ×1000 (FX), multipliers in
## permille, energy ×300. Fully deterministic (no floats in state; forecast uses sqrt for display/AI).
##
## Army (Dictionary):
##   {id:int, side:int, hex:int, str:int, max_str:int,
##    infantry:int (share of infantry in ‰, ≥500 → «Стойкость» +50% def),
##    hold:bool, move:null|{from:int, to:int, left:int}, start_str:int, attrition:int, routed:bool}
## Clash (Dictionary):
##   {id:int, target:int, side:int, attackers:Array[int], defender:int (-1 = none),
##    start_atk:int, start_def:int, entering:int (ticks until the attacker enters; 0 = fighting),
##    corridor:bool, breakthrough:null|{army:int, dir:int, steps:int}}
## Command (Dictionary):
##   {t:"attack", army, target} | {t:"card", card, target} | {t:"move", army, to} | {t:"hold", army} | {t:"retreat"}
## BattleEvent (Dictionary), "type" is one of:
##   clash {tick, clash, target, side} | capture {tick, hex, side, from} | repelled {tick, hex, side}
##   routed {tick, army} | retreat {tick, army, to} | card {tick, side, card, hex} | end {tick, reason}
## Options (Dictionary): {attacker:int (player side), defender:int, ai_energy_mult:int (‰), cards:Array[String],
##   ticks:int (optional offensive length, default OFFENSIVE_TICKS)}

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const Topology := preload("res://scripts/sim/topology.gd")
const World := preload("res://scripts/sim/world.gd")

const TICKS_PER_SEC := 10
const OFFENSIVE_TICKS := 90 * TICKS_PER_SEC
const FINAL_RUSH_TICKS := 20 * TICKS_PER_SEC
const ENERGY_UNIT := 300 # 1 energy point
const ENERGY_MAX := 10 * ENERGY_UNIT
const LOSS_PERMILLE := 15 # 0.015 × enemy Might per tick
const BREAK_PERMILLE := 300 # break below 30% of clash-start strength
const ENTER_TICKS := 15
const ENTER_TICKS_CORRIDOR := 8
const MOVE_TICKS := 15
const CARD_COOLDOWN := 10 * TICKS_PER_SEC

## card id -> {cost, name, target: "enemy"|"own"}
const CARDS := {
	"attack": {"cost": 2, "name": "Атака", "target": "enemy"},
	"breakthrough": {"cost": 3, "name": "Прорыв", "target": "enemy"},
	"airstrike": {"cost": 4, "name": "Авиаудар", "target": "enemy"},
	"encircle": {"cost": 3, "name": "Окружение", "target": "enemy"},
	"defense": {"cost": 2, "name": "Оборона", "target": "own"},
}

var world: World
var armies: Array
var opts: Dictionary
var tick: int = 0
var over: bool = false
## "time" | "retreat" | "wiped"
var end_reason: String = "time"
## Garrison strength per cell id (×1000).
var garrison: Array[int] = []
var clashes: Array[Dictionary] = []
var events: Array[Dictionary] = []
## Applied commands: {tick, side, cmd}
var command_log: Array[Dictionary] = []
## side -> energy (×300)
var energy: Dictionary = {}
## "side:card" -> ticks left
var cooldown: Dictionary = {}
## Side currently in «последний рубеж», -1 = none.
var last_stand: int = -1

var _effects: Array[Dictionary] = [] # {kind: "defense"|"encircle"|"airFort"|"weak", hex, left}
var _queue: Array[Dictionary] = [] # {side, cmd}
var _supply_cache: Dictionary = {}
var _next_clash_id: int = 1
var _captured: Dictionary = {}
var _lost: Dictionary = {}
var _routed_player: int = 0
var _protected_core: Dictionary = {}


func _init(p_world: World, p_armies: Array, p_opts: Dictionary) -> void:
	world = p_world
	armies = p_armies
	opts = p_opts
	for c in world.cells:
		garrison.append(garrison_for(c["id"], c["controller"]) if Types.is_passable(c) else 0)
	energy[attacker()] = 5 * ENERGY_UNIT
	energy[defender()] = ((5 * int(opts["ai_energy_mult"])) / 1000) * ENERGY_UNIT
	for a in armies:
		a["start_str"] = a["str"]
		a["attrition"] = 0
		a["move"] = null
	# The AI never targets the player's core in any battle (canon §9.11, decision 19).
	_protected_core = MapGen.core_of(world, attacker())


# ---------- helpers ----------

func attacker() -> int:
	return opts["attacker"]


func defender() -> int:
	return opts["defender"]


func enemy_of(side: int) -> int:
	return defender() if side == attacker() else attacker()


func garrison_for(hex: int, controller: int) -> int:
	var c: Dictionary = world.cells[hex]
	if controller != attacker() and controller != defender():
		# neutral/wild hexes are not part of the war
		return 0
	var dl: int = world.states[controller]["dev_level"] if controller >= 0 and controller < world.states.size() else 1
	var base := Types.js_round(10 * int(c["value"]) * Types.strength_mult(dl) * Types.FX)
	return base if c["owner"] == controller else base / 2


## Idle (not moving, not routed, alive) army of `side` standing in `hex`, or null.
func army_at(hex: int, side: int) -> Variant:
	for a in armies:
		if a["hex"] == hex and a["side"] == side and not a["routed"] and a["str"] > 0 and a["move"] == null:
			return a
	return null


func army_by_id(id: int) -> Variant:
	for a in armies:
		if a["id"] == id:
			return a
	return null


func is_supplied(hex: int, side: int) -> bool:
	if has_effect("encircle", hex):
		return false
	if not _supply_cache.has(side):
		_supply_cache[side] = Topology.supplied(world, side)
	return _supply_cache[side].has(hex)


func energy_points(side: int) -> int:
	return int(energy.get(side, 0)) / ENERGY_UNIT


## Offensive length; opts.ticks shortens it (FTUE: 60 s, canon §14.3).
func duration_ticks() -> int:
	return int(opts.get("ticks", OFFENSIVE_TICKS))


func is_rush() -> bool:
	return tick > duration_ticks() - FINAL_RUSH_TICKS


func seconds_left() -> int:
	return maxi(0, ceili(float(duration_ticks() - tick) / TICKS_PER_SEC))


## The clash this army is attacking in, or null.
func attacking(army: Dictionary) -> Variant:
	for cl in clashes:
		if (cl["attackers"] as Array).has(army["id"]):
			return cl
	return null


func _valid_cell(id: int) -> bool:
	return id >= 0 and id < world.cells.size()


## Is `side` allowed to attack `target` right now?
func can_target(side: int, target: int) -> bool:
	if not _valid_cell(target):
		return false
	var c: Dictionary = world.cells[target]
	if not Types.is_passable(c):
		return false
	if c["controller"] != enemy_of(side):
		return false
	if side != attacker() and _protected_core.has(target):
		return false
	return true


func adjacent_idle_armies(side: int, target: int) -> Array:
	var ns: PackedInt32Array = world.neighbors[target]
	var out: Array = []
	for a in armies:
		if a["side"] == side and not a["routed"] and a["str"] > 0 and a["move"] == null and ns.has(a["hex"]) and attacking(a) == null:
			out.append(a)
	out.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return x["id"] < y["id"])
	return out


# ---------- forms and multipliers ----------

func _controlled_neighbors(hex: int, side: int) -> int:
	var n := 0
	for id in world.neighbors[hex]:
		if id >= 0 and world.cells[id]["controller"] == side:
			n += 1
	return n


## {wedge, encircle, corridor, salient}
func forms_for(side: int, target: int, attacker_hexes: Array) -> Dictionary:
	var enemy := enemy_of(side)
	var distinct := {}
	for h in attacker_hexes:
		distinct[h] = true
	return {
		"wedge": distinct.size() >= 2,
		"encircle": _controlled_neighbors(target, side) >= 4 or not is_supplied(target, enemy),
		"corridor": _controlled_neighbors(target, side) == 1,
		"salient": _controlled_neighbors(target, side) >= 4 and world.cells[target]["owner"] == enemy,
	}


func _atk_mult(army: Dictionary, f: Dictionary, breakthrough: bool) -> int:
	var m := 1000
	if f["wedge"]:
		m += 200
	if f["encircle"]:
		m += 300 # «Окружение» +30% damage
	if breakthrough:
		m += 500
	if not is_supplied(army["hex"], army["side"]):
		m -= 200
	return maxi(200, m)


func _def_mult(target: int, def_army: Variant, f: Dictionary) -> int:
	var c: Dictionary = world.cells[target]
	var side: int = c["controller"]
	var m := 1100 # base + defender +10%
	var fort: int = c["fort"]
	if has_effect("airFort", target):
		fort = maxi(0, fort - 1)
	m += 150 * fort
	if c["terrain"] == "forest" or c["terrain"] == "hills":
		m += 250
	if c["kind"] == "city":
		m += 250
	if c["kind"] == "capital":
		m += 500
	if def_army != null and def_army["infantry"] >= 500:
		m += 500 # «Стойкость»
	if def_army != null and def_army["hold"]:
		m += 100
	if has_effect("defense", target):
		m += 500
	if has_effect("weak", target):
		m -= 300
	if f["salient"]:
		m -= 150
	if not is_supplied(target, side):
		m -= 200
	if last_stand == side:
		m += 250
	return maxi(200, m)


## Forecast for `side` attacking `target` with the given armies (canon §9.5, F = √W).
## Returns {f:float, atk_might:int, def_might:int, forms:Array[String]}.
func forecast(side: int, army_ids: Array, target: int, breakthrough: bool = false) -> Dictionary:
	var atk: Array = []
	var hexes: Array = []
	for id in army_ids:
		var a: Variant = army_by_id(id)
		if a != null:
			atk.append(a)
			hexes.append(a["hex"])
	var f := forms_for(side, target, hexes)
	var enemy := enemy_of(side)
	var def_army: Variant = army_at(target, enemy)
	var gar: int = garrison[target]
	if f["corridor"]:
		gar /= 2
	var atk_str := 0
	var atk_might := 0
	for a in atk:
		atk_str += a["str"]
	for a in atk:
		atk_might += (int(a["str"]) * _atk_mult(a, f, breakthrough)) / 1000
	var def_str: int = (int(def_army["str"]) if def_army != null else 0) + gar
	var def_might := (def_str * _def_mult(target, def_army, f)) / 1000
	var forms: Array[String] = []
	if f["wedge"]:
		forms.append("Клин +20%")
	if f["encircle"]:
		forms.append("Окружение +30%")
	if f["corridor"]:
		forms.append("Коридор")
	if f["salient"]:
		forms.append("Выступ −15%")
	var fval := 99.0
	if def_might > 0 and def_str > 0:
		fval = sqrt(float(atk_might * atk_str) / float(def_might * def_str))
	return {"f": fval, "atk_might": atk_might, "def_might": def_might, "forms": forms}


# ---------- commands ----------

## Queues a command for the next tick; false if it is invalid right now.
func issue(side: int, cmd: Dictionary) -> bool:
	if over:
		return false
	if not validate(side, cmd):
		return false
	_queue.append({"side": side, "cmd": cmd})
	return true


func _cost(cmd: Dictionary) -> int:
	if cmd["t"] == "attack":
		return CARDS["attack"]["cost"]
	if cmd["t"] == "card":
		return CARDS[cmd["card"]]["cost"]
	return 0


func card_ready(side: int, card: String) -> bool:
	return int(cooldown.get("%d:%s" % [side, card], 0)) <= 0


func _army_can_act(a: Variant, side: int) -> bool:
	return a != null and a["side"] == side and not a["routed"] and a["move"] == null and attacking(a) == null


func validate(side: int, cmd: Dictionary) -> bool:
	var e: int = energy.get(side, 0)
	if cmd["t"] == "card" and not CARDS.has(cmd["card"]):
		return false
	if e < _cost(cmd) * ENERGY_UNIT:
		return false
	match cmd["t"]:
		"attack":
			var a: Variant = army_by_id(cmd["army"])
			if not _army_can_act(a, side):
				return false
			if not world.neighbors[a["hex"]].has(cmd["target"]):
				return false
			return can_target(side, cmd["target"])
		"move":
			var a: Variant = army_by_id(cmd["army"])
			if not _army_can_act(a, side):
				return false
			var to: int = cmd["to"]
			if not _valid_cell(to) or not world.neighbors[a["hex"]].has(to):
				return false
			var c: Dictionary = world.cells[to]
			return Types.is_passable(c) and c["controller"] == side and army_at(to, side) == null
		"hold":
			var a: Variant = army_by_id(cmd["army"])
			return a != null and a["side"] == side
		"retreat":
			return side == attacker()
		"card":
			var card: String = cmd["card"]
			if not card_ready(side, card):
				return false
			var target: int = cmd["target"]
			if not _valid_cell(target):
				return false
			var c: Dictionary = world.cells[target]
			if not Types.is_passable(c):
				return false
			if CARDS[card]["target"] == "own":
				return c["controller"] == side
			if card == "airstrike":
				return c["controller"] == enemy_of(side) or c["controller"] == side
			if not can_target(side, target):
				return false
			if card == "attack" or card == "breakthrough":
				return adjacent_idle_armies(side, target).size() > 0
			return true
	return false


func _apply(side: int, cmd: Dictionary) -> void:
	if not validate(side, cmd):
		return
	energy[side] = int(energy.get(side, 0)) - _cost(cmd) * ENERGY_UNIT
	command_log.append({"tick": tick, "side": side, "cmd": cmd})
	match cmd["t"]:
		"attack":
			_start_or_join(side, cmd["target"], [army_by_id(cmd["army"])], null)
		"move":
			var a: Dictionary = army_by_id(cmd["army"])
			a["move"] = {"from": a["hex"], "to": cmd["to"], "left": MOVE_TICKS}
			a["hold"] = false
		"hold":
			var a: Dictionary = army_by_id(cmd["army"])
			a["hold"] = not a["hold"]
		"retreat":
			_finish("retreat")
		"card":
			var card: String = cmd["card"]
			cooldown["%d:%s" % [side, card]] = 0 if card == "attack" else CARD_COOLDOWN
			events.append({"type": "card", "tick": tick, "side": side, "card": card, "hex": cmd["target"]})
			_play_card(side, card, cmd["target"])


func _play_card(side: int, card: String, target: int) -> void:
	match card:
		"attack":
			_start_or_join(side, target, adjacent_idle_armies(side, target), null)
		"defense":
			_effects.append({"kind": "defense", "hex": target, "left": 15 * TICKS_PER_SEC})
			var a: Variant = army_at(target, side)
			if a != null:
				a["str"] = mini(a["max_str"], int(a["str"]) + int(a["max_str"]) / 10)
		"encircle":
			_effects.append({"kind": "encircle", "hex": target, "left": 12 * TICKS_PER_SEC})
		"breakthrough":
			var cands := adjacent_idle_armies(side, target)
			cands.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
				return x["str"] > y["str"] or (x["str"] == y["str"] and x["id"] < y["id"]))
			var army: Dictionary = cands[0]
			var dir: int = world.neighbors[army["hex"]].find(target)
			_start_or_join(side, target, [army], {"army": army["id"], "dir": dir, "steps": 1})
		"airstrike":
			var enemy := enemy_of(side)
			var area: Array[int] = [target]
			for n in world.neighbors[target]:
				if n >= 0:
					area.append(n)
			for hex in area:
				for a in armies:
					if a["hex"] == hex and a["side"] == enemy and not a["routed"]:
						a["str"] = maxi(1, int(a["str"]) - int(a["max_str"]) / 5)
				var cell: Dictionary = world.cells[hex]
				if cell["controller"] == enemy:
					garrison[hex] = maxi(0, garrison[hex] - garrison_for(hex, enemy) / 5)
					_effects.append({"kind": "airFort", "hex": hex, "left": 15 * TICKS_PER_SEC})


func _find_clash(target: int, side: int) -> Variant:
	for cl in clashes:
		if cl["target"] == target and cl["side"] == side:
			return cl
	return null


func _start_or_join(side: int, target: int, list: Array, breakthrough: Variant) -> void:
	if list.is_empty():
		return
	var clash: Variant = _find_clash(target, side)
	var enemy := enemy_of(side)
	if clash == null:
		var hexes: Array = []
		for a in list:
			hexes.append(a["hex"])
		var f := forms_for(side, target, hexes)
		if f["corridor"]:
			garrison[target] = garrison[target] / 2
		var def: Variant = army_at(target, enemy)
		clash = {
			"id": _next_clash_id,
			"target": target,
			"side": side,
			"attackers": [] as Array[int],
			"defender": def["id"] if def != null else -1,
			"start_atk": 0,
			"start_def": (int(def["str"]) if def != null else 0) + garrison[target],
			"entering": 0,
			"corridor": f["corridor"],
			"breakthrough": breakthrough,
		}
		_next_clash_id += 1
		clashes.append(clash)
		events.append({"type": "clash", "tick": tick, "clash": clash["id"], "target": target, "side": side})
	elif breakthrough != null and clash["breakthrough"] == null:
		clash["breakthrough"] = breakthrough
	for a in list:
		if (clash["attackers"] as Array).has(a["id"]):
			continue
		clash["attackers"].append(a["id"])
		clash["start_atk"] += a["str"]
		a["hold"] = false


# ---------- simulation ----------

## Advances the battle by one tick (0.1 s).
func step() -> void:
	if over:
		return
	tick += 1

	var rush := is_rush()
	for side in [attacker(), defender()]:
		var regen := 10 # 1 energy per 3 s = 300 / 30 ticks
		if rush:
			regen *= 2
		if last_stand == side:
			regen = (regen * 1250) / 1000
		if side == defender():
			regen = (regen * int(opts["ai_energy_mult"])) / 1000
		energy[side] = mini(ENERGY_MAX, int(energy.get(side, 0)) + regen)
	for k in cooldown.keys():
		if cooldown[k] > 0:
			cooldown[k] = cooldown[k] - 1

	var pending := _queue
	_queue = []
	for p in pending:
		_apply(p["side"], p["cmd"])
		if over:
			return

	_step_moves()
	_step_clashes()
	_step_effects()
	if tick % TICKS_PER_SEC == 0:
		_step_attrition()

	var player_alive := false
	for a in armies:
		if a["side"] == attacker() and not a["routed"] and a["str"] > 0:
			player_alive = true
			break
	if not player_alive:
		_finish("wiped")
	elif tick >= duration_ticks():
		_finish("time")


func _step_moves() -> void:
	for a in armies:
		if a["move"] == null:
			continue
		a["move"]["left"] -= 1
		if a["move"]["left"] > 0:
			continue
		var to: int = a["move"]["to"]
		var c: Dictionary = world.cells[to]
		# Arrive only if the hex is still ours and free; otherwise bounce back.
		if c["controller"] == a["side"] and army_at(to, a["side"]) == null:
			a["hex"] = to
		a["move"] = null
		# Reinforcing a hex under attack (even while the enemy is entering): become its defender.
		for cl in clashes:
			if cl["target"] != a["hex"] or cl["side"] == a["side"] or cl["defender"] != -1:
				continue
			cl["defender"] = a["id"]
			cl["start_def"] = a["str"] if cl["entering"] > 0 else int(cl["start_def"]) + int(a["str"])
			cl["entering"] = 0


func _live_attackers(cl: Dictionary) -> Array:
	var out: Array = []
	for id in cl["attackers"]:
		var a: Variant = army_by_id(id)
		if a != null and not a["routed"] and a["str"] > 0 and a["move"] == null:
			out.append(a)
	return out


func _step_clashes() -> void:
	var done: Array[int] = [] # clash ids
	var order := clashes.duplicate()
	order.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return x["id"] < y["id"])
	for cl in order:
		var atk := _live_attackers(cl)
		if atk.is_empty():
			done.append(cl["id"])
			continue
		if cl["entering"] > 0:
			cl["entering"] -= 1
			if cl["entering"] == 0:
				_capture(cl, atk)
				done.append(cl["id"])
			continue
		var enemy := enemy_of(cl["side"])
		var target: int = cl["target"]
		var cell: Dictionary = world.cells[target]
		if cell["controller"] != enemy:
			done.append(cl["id"])
			continue
		var def: Variant = army_by_id(cl["defender"]) if cl["defender"] != -1 else null
		var def_army: Variant = null
		if def != null and not def["routed"] and def["hex"] == target and def["move"] == null:
			def_army = def
		var hexes: Array = []
		for a in atk:
			hexes.append(a["hex"])
		var f := forms_for(cl["side"], target, hexes)
		var bt: Variant = cl["breakthrough"]
		var atk_might := 0
		var atk_str := 0
		for a in atk:
			var is_bt: bool = bt != null and bt["army"] == a["id"]
			atk_might += (int(a["str"]) * _atk_mult(a, f, is_bt)) / 1000
			atk_str += a["str"]
		var gar: int = garrison[target]
		var def_str: int = (int(def_army["str"]) if def_army != null else 0) + gar
		var def_might := (def_str * _def_mult(target, def_army, f)) / 1000

		var atk_loss := (def_might * LOSS_PERMILLE) / 1000
		var def_loss := (atk_might * LOSS_PERMILLE) / 1000
		for a in atk:
			a["str"] = maxi(0, int(a["str"]) - (atk_loss * int(a["str"])) / maxi(1, atk_str))
		if def_str > 0:
			if def_army != null:
				def_army["str"] = maxi(0, int(def_army["str"]) - (def_loss * int(def_army["str"])) / def_str)
			garrison[target] = maxi(0, gar - (def_loss * gar) / def_str)

		var atk_now := 0
		for a in atk:
			atk_now += a["str"]
		var def_now: int = (int(def_army["str"]) if def_army != null else 0) + garrison[target]
		var atk_broken: bool = atk_now * 1000 < int(cl["start_atk"]) * BREAK_PERMILLE
		var def_broken: bool = def_now * 1000 < int(cl["start_def"]) * BREAK_PERMILLE or def_now <= 0
		if atk_broken:
			# Simultaneous break: the attacker breaks (canon §9.5).
			events.append({"type": "repelled", "tick": tick, "hex": target, "side": cl["side"]})
			done.append(cl["id"])
		elif def_broken:
			garrison[target] = 0
			if def_army != null:
				_retreat_or_rout(def_army, f["encircle"])
			cl["entering"] = ENTER_TICKS_CORRIDOR if cl["corridor"] else ENTER_TICKS
	for id in done:
		for i in clashes.size():
			if clashes[i]["id"] == id:
				clashes.remove_at(i)
				break


func _retreat_or_rout(army: Dictionary, encircled: bool) -> void:
	if not encircled:
		for n in world.neighbors[army["hex"]]:
			if n < 0:
				continue
			var c: Dictionary = world.cells[n]
			if not Types.is_passable(c) or c["controller"] != army["side"] or army_at(n, army["side"]) != null:
				continue
			var contested := false
			for cl in clashes:
				if cl["target"] == n and cl["entering"] == 0:
					contested = true
					break
			if contested:
				continue
			army["hex"] = n
			army["hold"] = false
			events.append({"type": "retreat", "tick": tick, "army": army["id"], "to": n})
			return
	_rout(army)


func _rout(army: Dictionary) -> void:
	# Routed: returns with 10% Strength to the nearest supplied official own hex without an army.
	army["routed"] = true
	events.append({"type": "routed", "tick": tick, "army": army["id"]})
	if army["side"] == attacker():
		_routed_player += 1
	for cl in clashes:
		var kept: Array[int] = []
		for id in cl["attackers"]:
			if id != army["id"]:
				kept.append(id)
		cl["attackers"] = kept
		if cl["defender"] == army["id"]:
			cl["defender"] = -1
	var side: int = army["side"]
	var sup := Topology.supplied(world, side)
	var start: int = army["hex"]
	var dist := {start: 0}
	var queue: Array[int] = [start]
	var head := 0
	while head < queue.size():
		var id: int = queue[head]
		head += 1
		var c: Dictionary = world.cells[id]
		if id != start and c["owner"] == side and c["controller"] == side and sup.has(id) and army_at(id, side) == null:
			army["hex"] = id
			army["str"] = maxi(1, int(army["max_str"]) / 10)
			return
		for n in world.neighbors[id]:
			if n < 0 or dist.has(n) or not Types.is_passable(world.cells[n]):
				continue
			dist[n] = dist[id] + 1
			queue.append(n)
	army["str"] = 0


func _capture(cl: Dictionary, atk: Array) -> void:
	var target: int = cl["target"]
	var side: int = cl["side"]
	var cell: Dictionary = world.cells[target]
	var from: int = cell["controller"]
	# Any enemy army still standing in the hex is pushed out (or routed if it cannot retreat).
	for e in armies:
		if e["side"] != side and e["hex"] == target and not e["routed"] and e["str"] > 0 and e["move"] == null:
			_retreat_or_rout(e, false)
	cell["controller"] = side
	garrison[target] = garrison_for(target, side)
	_supply_cache.clear()
	if side == attacker():
		if cell["owner"] != side:
			_captured[target] = true
		_lost.erase(target)
	else:
		_captured.erase(target)
		if cell["owner"] == attacker():
			_lost[target] = true
	events.append({"type": "capture", "tick": tick, "hex": target, "side": side, "from": from})
	if cl["corridor"]:
		_effects.append({"kind": "weak", "hex": target, "left": 20 * TICKS_PER_SEC})

	# The strongest attacker moves in; the rest hold their hexes.
	var lead: Dictionary = atk[0]
	for a in atk:
		if a["str"] > lead["str"] or (a["str"] == lead["str"] and a["id"] < lead["id"]):
			lead = a
	if army_at(target, side) == null:
		lead["hex"] = target

	var bt: Variant = cl["breakthrough"]
	if bt != null and bt["army"] == lead["id"] and lead["hex"] == target and bt["steps"] < 3:
		_continue_breakthrough(lead, bt)


func _continue_breakthrough(army: Dictionary, bt: Dictionary) -> void:
	var dir: int = bt["dir"]
	var ns: PackedInt32Array = world.neighbors[army["hex"]]
	var next: int = ns[dir] if dir >= 0 and dir < ns.size() else -1
	if next < 0 or not can_target(army["side"], next):
		return
	var enemy := enemy_of(army["side"])
	var cell: Dictionary = world.cells[next]
	if army_at(next, enemy) != null or cell["fort"] >= 3:
		return # stops at an army or fort ≥3
	var stp := {"army": army["id"], "dir": dir, "steps": int(bt["steps"]) + 1}
	if garrison[next] * 2 <= int(army["str"]):
		# takes weak hexes outright
		garrison[next] = 0
		var clash := {
			"id": _next_clash_id,
			"target": next,
			"side": army["side"],
			"attackers": [army["id"]] as Array[int],
			"defender": -1,
			"start_atk": army["str"],
			"start_def": 0,
			"entering": ENTER_TICKS,
			"corridor": false,
			"breakthrough": stp,
		}
		_next_clash_id += 1
		clashes.append(clash)
	else:
		_start_or_join(army["side"], next, [army], stp)


func _step_effects() -> void:
	var before := _effects.size()
	var kept: Array[Dictionary] = []
	for e in _effects:
		e["left"] -= 1
		if e["left"] > 0:
			kept.append(e)
	_effects = kept
	if before != _effects.size():
		_supply_cache.clear()


## kind: "defense" | "encircle" | "airFort" | "weak"
func has_effect(kind: String, hex: int) -> bool:
	for e in _effects:
		if e["kind"] == kind and e["hex"] == hex:
			return true
	return false


## Active effects (read-only copies): {kind, hex, left}.
func effects() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for e in _effects:
		out.append(e.duplicate())
	return out


func _step_attrition() -> void:
	# Out of supply: −0.5% Strength per second, at most −40% per battle (canon §9.7).
	for a in armies:
		if a["routed"] or a["str"] <= 0 or is_supplied(a["hex"], a["side"]):
			continue
		var cap := (int(a["start_str"]) * 400) / 1000
		var loss := mini((int(a["max_str"]) * 5) / 1000, cap - int(a["attrition"]))
		if loss > 0:
			a["str"] = maxi(1, int(a["str"]) - loss)
			a["attrition"] = int(a["attrition"]) + loss


func _finish(reason: String) -> void:
	if over:
		return
	over = true
	end_reason = reason
	clashes.clear()
	for a in armies:
		a["move"] = null
		a["routed"] = false
		a["hold"] = false
	events.append({"type": "end", "tick": tick, "reason": reason})


## {captured:Array[int] (sorted), lost:Array[int] (sorted), routed_player_armies:int, reason:String}
func result() -> Dictionary:
	var cap: Array[int] = []
	for id in _captured:
		cap.append(id)
	cap.sort()
	var lost: Array[int] = []
	for id in _lost:
		lost.append(id)
	lost.sort()
	return {"captured": cap, "lost": lost, "routed_player_armies": _routed_player, "reason": end_reason}
