extends RefCounted
## Starting armies for the chapter I prototype (canon §8.1, 11_balance_numbers.md §15),
## port of packages/sim/src/armies.ts. Army layout is documented in battle.gd.

const Types := preload("res://scripts/sim/types.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const World := preload("res://scripts/sim/world.gd")

const INFANTRY_BASE := 25 # per squad at DL1 (canon §8.1, C36)


static func infantry_army(id: int, side: int, hex: int, slots: int, dev_level: int) -> Dictionary:
	var mx := Types.js_round(INFANTRY_BASE * slots * Types.strength_mult(dev_level) * Types.FX)
	return {
		"id": id, "side": side, "hex": hex, "str": mx, "max_str": mx, "infantry": 1000,
		"hold": false, "move": null, "start_str": mx, "attrition": 0, "routed": false,
	}


static func _by_value_desc(cells: Array) -> Array[int]:
	cells.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return a["value"] > b["value"] or (a["value"] == b["value"] and a["id"] < b["id"]))
	var out: Array[int] = []
	for c in cells:
		out.append(c["id"])
	return out


## Front hexes of `side` bordering `enemy` (official owners), best value first.
static func _front(w: World, side: int, enemy: int) -> Array[int]:
	var cells: Array = []
	for c in w.cells:
		if c["owner"] != side or not Types.is_passable(c):
			continue
		for n in w.neighbors[c["id"]]:
			if n >= 0 and w.cells[n]["owner"] == enemy:
				cells.append(c)
				break
	return _by_value_desc(cells)


## Player: 2 armies × 3 slots at the front. Barons (Wolf, +1 army): 3 × 3.
static func starting_armies(w: World) -> Array[Dictionary]:
	var barons := MapGen.BARONS
	var pf := _front(w, Types.PLAYER, barons)
	var bf := _front(w, barons, Types.PLAYER)
	var out: Array[Dictionary] = []
	out.append(infantry_army(1, Types.PLAYER, pf[0], 3, 1))
	out.append(infantry_army(2, Types.PLAYER, pf[1] if pf.size() > 1 else int(w.states[Types.PLAYER]["capital_id"]), 3, 1))
	var barons_dl: int = w.states[barons]["dev_level"]
	# One Barons army holds the front; the others start in the rear and the AI pulls them toward threats.
	var cap: int = w.states[barons]["capital_id"]
	var rear_cells: Array = []
	for c in w.cells:
		if c["owner"] == barons and Types.is_passable(c) and c["id"] != cap and not bf.has(c["id"]):
			rear_cells.append(c)
	var rear := _by_value_desc(rear_cells)
	out.append(infantry_army(101, barons, bf[0], 3, barons_dl))
	out.append(infantry_army(102, barons, rear[0] if rear.size() > 0 else cap, 3, barons_dl))
	out.append(infantry_army(103, barons, cap, 3, barons_dl))
	return out
