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
##   ticks:int (optional offensive length, default OFFENSIVE_TICKS); the attacker's commanders (04 §15.2, all
##   optional): energy_bonus:int (start energy points), regen_pm:int (‰ faster energy), landing_discount:int,
##   air_pm:int (‰ more «Авиаудар» damage)}
## Commander passives on an army (all optional, ‰): cmd_atk (attack), cmd_def (defence), cmd_home (defence on its
##   own official hex), cmd_forts (attack on a hex with a fort ≥ 1), cmd_port (attack and defence on or next to a
##   port its side controls), cmd_wedge (extra «Клин» for every army of an attack it joins), cmd_breach:bool
##   («Прорыв» goes one hex further).

const HexGridLib := preload("res://scripts/sim/hexgrid.gd")
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
const AIR_DEFENSE_LVL := 6  # a tower from this level is also air defence (canon §7)

## card id -> {cost, name, target: "enemy"|"own"}
const CARDS := {
	"attack": {"cost": 2, "name": "card.attack", "target": "enemy"},
	"breakthrough": {"cost": 3, "name": "card.breakthrough", "target": "enemy"},
	"airstrike": {"cost": 4, "name": "card.airstrike", "target": "enemy"},
	"encircle": {"cost": 3, "name": "card.encircle", "target": "enemy"},
	"defense": {"cost": 2, "name": "card.defense", "target": "own"},
	"corps": {"cost": 3, "name": "card.corps", "target": "own"},
	"landing": {"cost": 4, "name": "card.landing", "target": "enemy"},  # «Десант», DL7 (03 §12.2)
	"missile": {"cost": 5, "name": "card.missile", "target": "enemy"},  # «Ракетный удар», DL8  # «Союзный корпус», only with an ally in the war
}
const CORPS_TICKS := 30 * TICKS_PER_SEC
const CORPS_SHARE_PM := 300  # 30% of the average max Strength of the side's armies

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
var _corps_used: Dictionary = {}  # side -> true once «Союзный корпус» was played this offensive
var _landings: Array = []          # [{army, at}] landed copies waiting 1.5 s before they attack
var _landing_hexes: Dictionary = {} # hex -> side: hexes a landing took (the «Высадка» star needs them held)
var wedges: Dictionary = {}         # side -> clashes joined from 2+ hexes («Клин», the Chronicle counts them)
var _missile_hit: Dictionary = {}   # hex -> true: fort −3 and the tower out until the battle ends
const LANDING_SHARE_PM := 400       # the copy has 40% of the strongest army's max Strength
const LANDING_DELAY := 15           # 1.5 s after the drop it attacks


func _init(p_world: World, p_armies: Array, p_opts: Dictionary) -> void:
	world = p_world
	armies = p_armies
	opts = p_opts
	for c in world.cells:
		garrison.append(garrison_for(c["id"], c["controller"]) if Types.is_passable(c) else 0)
	energy[attacker()] = (5 + int(opts.get("energy_bonus", 0))) * ENERGY_UNIT
	energy[defender()] = ((5 * int(opts["ai_energy_mult"])) / 1000) * ENERGY_UNIT
	for a in armies:
		a["start_str"] = a["str"]
		a["attrition"] = 0
		a["move"] = null
	# The AI never targets the player's core in any battle (canon §9.11, decision 19).
	_protected_core = MapGen.core_of(world, Types.PLAYER)  # the player's core, whoever attacks


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
	if opts.has("camp") and target != int(opts["camp"]):
		return false  # marauder fight (03 §5.7): only the camp hex
	if side != Types.PLAYER and _protected_core.has(target):
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
		"target": target,
		"wedge": distinct.size() >= 2,
		"encircle": _controlled_neighbors(target, side) >= 4 or not is_supplied(target, enemy),
		"corridor": _controlled_neighbors(target, side) == 1,
		"salient": _controlled_neighbors(target, side) >= 4 and world.cells[target]["owner"] == enemy,
	}


## True when the hex is a port, or touches one, that `side` controls (Admiral Seir).
func _near_port(hex: int, side: int) -> bool:
	var c: Dictionary = world.cells[hex]
	if c["kind"] == "port" and int(c["controller"]) == side:
		return true
	for id in world.neighbors[hex]:
		if id >= 0 and world.cells[id]["kind"] == "port" and int(world.cells[id]["controller"]) == side:
			return true
	return false


## The commanders' «Клин» bonus of an attack: Vega and Rai add up for every army in it (03 §9.1).
static func wedge_extra(atk: Array) -> int:
	var w := 0
	for a in atk:
		w += int(a.get("cmd_wedge", 0))
	return w


func _atk_mult(army: Dictionary, f: Dictionary, breakthrough: bool) -> int:
	var m := 1000 + int(army.get("cmd_atk", 0))
	if f["wedge"]:
		m += 200 + int(f.get("wedge_extra", 0))
	if army.has("cmd_forts") and f.has("target") and effective_fort(int(f["target"])) >= 1:
		m += int(army["cmd_forts"])
	if army.has("cmd_port") and _near_port(int(army["hex"]), int(army["side"])):
		m += int(army["cmd_port"])
	if f["encircle"]:
		m += 300 # «Окружение» +30% damage
	if breakthrough:
		m += 500
	if not is_supplied(army["hex"], army["side"]):
		m -= 200
	if f.has("target") and world.is_river(int(army["hex"]), int(f["target"])):
		m -= 250  # attacking across a river (canon §5.1)
	return maxi(200, m)


## Fort level after the cards: «Авиаудар» −1 for 15 s, «Ракетный удар» −3 to the end of the battle.
func effective_fort(hex: int) -> int:
	var fort: int = world.cells[hex]["fort"]
	if has_effect("airFort", hex):
		fort -= 1
	if _missile_hit.has(hex):
		fort -= 3
	return maxi(0, fort)


func _def_mult(target: int, def_army: Variant, f: Dictionary) -> int:
	var c: Dictionary = world.cells[target]
	var side: int = c["controller"]
	var m := 1100 # base + defender +10%
	var fort := effective_fort(target)
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
	if def_army != null:
		m += int(def_army.get("cmd_def", 0))
		if c["owner"] == side:
			m += int(def_army.get("cmd_home", 0))
		if def_army.has("cmd_port") and _near_port(target, side):
			m += int(def_army["cmd_port"])
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
	f["wedge_extra"] = wedge_extra(atk)
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
		forms.append("form.wedge")
	if f["encircle"]:
		forms.append("form.encircle")
	if f["corridor"]:
		forms.append("form.corridor")
	if f["salient"]:
		forms.append("form.salient")
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


func _cost(cmd: Dictionary, side: int = -1) -> int:
	if cmd["t"] == "attack":
		return CARDS["attack"]["cost"]
	if cmd["t"] == "card":
		var c: int = CARDS[cmd["card"]]["cost"]
		if cmd["card"] == "landing" and side == attacker():
			c = maxi(1, c - int(opts.get("landing_discount", 0)))  # Admiral Seir
		return c
	return 0


func card_ready(side: int, card: String) -> bool:
	return int(cooldown.get("%d:%s" % [side, card], 0)) <= 0


func _army_can_act(a: Variant, side: int) -> bool:
	return a != null and a["side"] == side and not a["routed"] and a["move"] == null and attacking(a) == null


func validate(side: int, cmd: Dictionary) -> bool:
	var e: int = energy.get(side, 0)
	if cmd["t"] == "card" and not CARDS.has(cmd["card"]):
		return false
	if e < _cost(cmd, side) * ENERGY_UNIT:
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
			if card == "corps":
				if not (opts.get("cards", []) as Array).has("corps") or _corps_used.has(side) or army_at(target, side) != null:
					return false
				var front := false
				for n in world.neighbors[target]:
					if n >= 0 and world.cells[n]["controller"] == enemy_of(side):
						front = true
				return c["controller"] == side and front
			if CARDS[card]["target"] == "own":
				return c["controller"] == side
			if card == "airstrike":
				return c["controller"] == enemy_of(side) or c["controller"] == side
			if card == "missile":
				return can_target(side, target)
			if card == "landing":
				return can_land(side, target)
			if not can_target(side, target):
				return false
			if card == "attack" or card == "breakthrough":
				return adjacent_idle_armies(side, target).size() > 0
			return true
	return false


func _apply(side: int, cmd: Dictionary) -> void:
	if not validate(side, cmd):
		return
	energy[side] = int(energy.get(side, 0)) - _cost(cmd, side) * ENERGY_UNIT
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
		"corps":
			# a temporary allied army without traits on an empty front hex, for 30 s (03 §11)
			var total := 0
			var n := 0
			for a in armies:
				if a["side"] == side and not a.has("temp_until"):
					total += int(a["max_str"])
					n += 1
			var s: int = (total / maxi(1, n)) * CORPS_SHARE_PM / 1000
			armies.append({"id": 900 + tick % 1000, "side": side, "hex": target, "str": s, "max_str": s, "infantry": 0,
				"hold": false, "move": null, "start_str": s, "attrition": 0, "routed": false, "temp_until": tick + CORPS_TICKS, "corps": true})
			_corps_used[side] = true
			events.append({"type": "corps", "tick": tick, "hex": target, "side": side})
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
		"missile":
			# army and garrison −50% of current Strength; the tower is out and the fort −3 to the end (03 §12.2)
			var foe := enemy_of(side)
			for a in armies:
				if a["hex"] == target and a["side"] == foe and not a["routed"]:
					a["str"] = maxi(1, int(a["str"]) / 2)
			garrison[target] = int(garrison[target]) / 2
			_missile_hit[target] = true
			events.append({"type": "missile", "tick": tick, "hex": target, "side": side})
		"landing":
			# a copy of the strongest own army at 40% of its max Strength drops on the hex and attacks in 1.5 s
			var best: Variant = null
			for a in armies:
				if a["side"] == side and not a.has("temp_until") and not a["routed"] and (best == null or int(a["max_str"]) > int(best["max_str"])):
					best = a
			var s: int = int(best["max_str"]) * LANDING_SHARE_PM / 1000
			var copy := {"id": 960 + tick % 1000, "side": side, "hex": target, "str": s, "max_str": s, "infantry": int(best.get("infantry", 0)),
				"hold": false, "move": null, "start_str": s, "attrition": 0, "routed": false, "temp_until": 1 << 30, "landing": true}
			armies.append(copy)
			_landings.append({"army": copy["id"], "at": tick + LANDING_DELAY})
			events.append({"type": "landing", "tick": tick, "hex": target, "side": side})
		"airstrike":
			# target and its 6 neighbours: −20% max Strength of enemy armies and garrisons, forts −1 for 15 s;
			# hexes under the enemy's air defence take half the damage (canon §7, 03 §12.2)
			var enemy := enemy_of(side)
			var air_pm := 1000 + (int(opts.get("air_pm", 0)) if side == attacker() else 0)  # General Hawk
			for hex in airstrike_area(target):
				var div := 10 if air_defended(hex, enemy) else 5
				var hit := false
				for a in armies:
					if a["hex"] == hex and a["side"] == enemy and not a["routed"]:
						a["str"] = maxi(1, int(a["str"]) - int(a["max_str"]) * air_pm / (div * 1000))
						hit = true
				var cell: Dictionary = world.cells[hex]
				if cell["controller"] == enemy:
					garrison[hex] = maxi(0, garrison[hex] - garrison_for(hex, enemy) / div)
					_effects.append({"kind": "airFort", "hex": hex, "left": 15 * TICKS_PER_SEC})
					hit = true
				if div == 10 and hit:
					events.append({"type": "flak", "tick": tick, "hex": hex, "side": enemy})


## «Десант» (03 §12.2): an enemy hex with no army and an effective fort of 0, within 2 hexes of a hex the side
## controls (or 4 of its port); the side needs a regular army to copy.
func can_land(side: int, target: int) -> bool:
	if not can_target(side, target) or army_at(target, enemy_of(side)) != null or effective_fort(target) > 0:
		return false
	var has_army := false
	for a in armies:
		if a["side"] == side and not a.has("temp_until") and not a["routed"]:
			has_army = true
	if not has_army:
		return false
	var t: Dictionary = world.cells[target]
	var tv := Vector2i(int(t["q"]), int(t["r"]))
	for c in world.cells:
		if c["controller"] != side:
			continue
		var d := HexGridLib.distance(tv, Vector2i(int(c["q"]), int(c["r"])))
		if d <= 2 or (d <= 4 and c["kind"] == "port"):
			return true
	return false


## The airstrike's 7 hexes: the target and its neighbours on the map.
func airstrike_area(target: int) -> Array[int]:
	var area: Array[int] = [target]
	for n in world.neighbors[target]:
		if n >= 0:
			area.append(n)
	return area


## Air defence (canon §7): `hex` is within radius 1 of a working tower of level ≥ 6 held by `side`.
func air_defended(hex: int, side: int) -> bool:
	for h in airstrike_area(hex):
		var c: Dictionary = world.cells[h]
		if int(c.get("tower", 0)) >= AIR_DEFENSE_LVL and c["owner"] == side and c["controller"] == side:
			return true
	return false


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
	if not clash.has("wedge") and (clash["attackers"] as Array).size() >= 2:
		var from := {}
		for aid in clash["attackers"]:
			var aa: Variant = army_by_id(aid)
			if aa != null:
				from[aa["hex"]] = true
		if from.size() >= 2:
			clash["wedge"] = true
			wedges[side] = int(wedges.get(side, 0)) + 1


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
		else:
			regen = (regen * (1000 + int(opts.get("regen_pm", 0)))) / 1000  # Emperor Rai
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

	_step_landings()
	_step_moves()
	_step_clashes()
	_step_temp_armies()
	_step_towers()
	_step_effects()
	if tick % TICKS_PER_SEC == 0:
		_step_attrition()

	var player_alive := false
	for a in armies:
		if a["side"] == attacker() and not a["routed"] and a["str"] > 0:
			player_alive = true
			break
	if opts.has("camp") and _captured.has(int(opts["camp"])):
		_finish("camp")  # raiders broken: the camp is destroyed
	elif not player_alive:
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
		f["wedge_extra"] = wedge_extra(atk)
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


## Landed copies attack their hex 1.5 s after the drop; a copy that loses its clash is gone (03 §12.2).
func _step_landings() -> void:
	for l in _landings.duplicate():
		if tick < int(l["at"]):
			continue
		_landings.erase(l)
		var a: Variant = army_by_id(int(l["army"]))
		if a != null:
			_start_or_join(int(a["side"]), int(a["hex"]), [a], null)
	for a in armies.duplicate():
		if a.has("landing") and int(world.cells[int(a["hex"])]["controller"]) == int(a["side"]):
			_landing_hexes[int(a["hex"])] = int(a["side"])
		elif a.has("landing") and _landings.filter(func(x): return int(x["army"]) == int(a["id"])).is_empty() and _find_clash(int(a["hex"]), int(a["side"])) == null:
			_remove_army(a)  # repelled: the copy is gone


## The «Высадка» star: a hex taken by a landing is still held by its side when the battle ends.
func landing_held(side: int) -> bool:
	for h in _landing_hexes:
		if int(_landing_hexes[h]) == side and int(world.cells[int(h)]["controller"]) == side:
			return true
	return false


## Temporary armies («Союзный корпус») vanish when their time is up, even mid-clash (03 §11).
func _step_temp_armies() -> void:
	for a in armies.duplicate():
		if a.has("temp_until") and tick >= int(a["temp_until"]):
			_remove_army(a)


func _remove_army(a: Dictionary) -> void:
	for cl in clashes:
		var kept: Array[int] = []
		for id in cl["attackers"]:
			if id != a["id"]:
				kept.append(id)
		cl["attackers"] = kept
		if cl["defender"] == a["id"]:
			cl["defender"] = -1
	armies.erase(a)


## М_силы by level, permille (canon §6.2) — towers hit by their own level.
const STR_MULT_PM: Array[int] = [1000, 1000, 1250, 1550, 1900, 2350, 2900, 3600, 4400, 5400, 6600]


## Towers (canon §7, 03 §8.6): 1.5 × М_силы(tower level) Strength per second to every enemy army in an adjacent
## hex while it is in any clash. A tower on an occupied hex works for nobody. Direct damage: no multipliers.
func _step_towers() -> void:
	var in_clash := {}
	for cl in clashes:
		for aid in cl["attackers"]:
			in_clash[aid] = true
		if cl["defender"] != -1:
			in_clash[cl["defender"]] = true
	if in_clash.is_empty():
		return
	for c in world.cells:
		var lvl: int = int(c.get("tower", 0))
		if lvl <= 0 or c["controller"] != c["owner"] or _missile_hit.has(int(c["id"])):
			continue
		var side: int = c["owner"]
		var dmg: int = (150 * STR_MULT_PM[clampi(lvl, 1, 10)]) / 1000
		for n in world.neighbors[c["id"]]:
			if n < 0:
				continue
			for a in armies:
				if a["hex"] != n or a["side"] == side or a["routed"] or int(a["str"]) <= 0 or not in_clash.has(a["id"]):
					continue
				a["str"] = maxi(1, int(a["str"]) - dmg)
				if tick % TICKS_PER_SEC == 0:
					events.append({"type": "tower_hit", "tick": tick, "hex": c["id"], "target": n})


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
	var across := false
	for a in atk:
		if world.is_river(int(a["hex"]), target):
			across = true
	events.append({"type": "capture", "tick": tick, "hex": target, "side": side, "from": from, "river": across})
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
	if bt != null and bt["army"] == lead["id"] and lead["hex"] == target and bt["steps"] < (4 if bool(lead.get("cmd_breach", false)) else 3):
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
	for a in armies.duplicate():
		if a.has("temp_until"):
			armies.erase(a)
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
