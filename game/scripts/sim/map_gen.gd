extends RefCounted
## Chapter I «Долина» map generator (canon §12.1), port of packages/sim/src/map.ts.
## 50 land hexes — player 7 (core), Кремнёвые Бароны (Wolf) 14, Вольные Хутора (Fox) 10, wild 19.
## Deterministic from seed; retries seeds until the validator passes.

const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const World := preload("res://scripts/sim/world.gd")

const BARONS := 2
const HAMLETS := 3

const RADIUS := 4
const PLAYER_CAP := Vector2i(0, 3)
const BARONS_CAP := Vector2i(3, -3)
const HAMLETS_CAP := Vector2i(-3, 0)
const IMPASSABLE := 11
const BARONS_SIZE := 14
const HAMLETS_SIZE := 10


static func make_states() -> Array[Dictionary]:
	var out: Array[Dictionary] = [
		{"id": Types.NOBODY, "name": "Дикие земли", "color": 0xb9b2a3, "archetype": "player", "capital_id": -1, "dev_level": 0},
		{"id": Types.PLAYER, "name": "Ваша держава", "color": 0x2e6bff, "archetype": "player", "capital_id": -1, "dev_level": 1},
		{"id": BARONS, "name": "Кремнёвые Бароны", "color": 0xf08a24, "archetype": "wolf", "capital_id": -1, "dev_level": 1},
		{"id": HAMLETS, "name": "Вольные Хутора", "color": 0x3fa34d, "archetype": "fox", "capital_id": -1, "dev_level": 1},
	]
	return out


static func _build_topology(w: World) -> void:
	w.by_key = {}
	for c in w.cells:
		w.by_key[HexGrid.hex_key(c["q"], c["r"])] = c["id"]
	w.neighbors = []
	for c in w.cells:
		var ns := PackedInt32Array()
		for d in HexGrid.DIRS:
			ns.append(w.by_key.get(HexGrid.hex_key(c["q"] + d.x, c["r"] + d.y), -1))
		w.neighbors.append(ns)


## Returns a valid chapter I world, or null (with push_error) if 200 attempts fail.
static func generate_chapter_one(seed_value: int) -> World:
	for attempt in 200:
		var w := _try_generate(seed_value + attempt * 7919)
		if w != null and validate_chapter_one(w).is_empty():
			return w
	push_error("map generator: no valid map found")
	return null


static func _id_of(w: World, a: Vector2i) -> int:
	return w.by_key[HexGrid.hex_key(a.x, a.y)]


static func _core_ids(w: World, cap: Vector2i) -> Array[int]:
	var cid := _id_of(w, cap)
	var out: Array[int] = [cid]
	for n in w.neighbors[cid]:
		if n >= 0:
			out.append(n)
	return out


static func _set_kind(c: Dictionary, kind: String, cell_name: String = "") -> void:
	c["kind"] = kind
	c["value"] = Types.KIND_VALUE[kind]
	if cell_name != "":
		c["name"] = cell_name


static func _free(cells: Array[Dictionary], owner: int, rng: Rng) -> Array:
	var out: Array = []
	for c in cells:
		if c["owner"] == owner and c["kind"] == "plain" and Types.is_passable(c):
			out.append(c)
	return rng.shuffle(out)


static func _sort_by_player_distance(arr: Array) -> Array:
	return Types.stable_sort(arr, func(a: Dictionary, b: Dictionary) -> int:
		return HexGrid.distance(HexGrid.axial(a), PLAYER_CAP) - HexGrid.distance(HexGrid.axial(b), PLAYER_CAP))


static func _try_generate(seed_value: int) -> World:
	var rng := Rng.new(seed_value)
	var w := World.new()
	w.map_seed = seed_value
	w.radius = RADIUS
	var coords := HexGrid.disk(RADIUS)
	for i in coords.size():
		w.cells.append({
			"id": i, "q": coords[i].x, "r": coords[i].y,
			"terrain": "plain", "kind": "plain", "value": 1,
			"owner": Types.NOBODY, "controller": Types.NOBODY, "fort": 0, "name": "",
		})
	_build_topology(w)
	var cells := w.cells
	w.states = make_states()

	var reserved := {}
	for cap in [PLAYER_CAP, BARONS_CAP, HAMLETS_CAP]:
		for id in _core_ids(w, cap):
			reserved[id] = true

	# 1. Impassable terrain on the rim, away from capitals' cores.
	var rim: Array = []
	for c in cells:
		if HexGrid.distance(HexGrid.axial(c), Vector2i.ZERO) >= RADIUS - 1 and not reserved.has(c["id"]):
			rim.append(c)
	rng.shuffle(rim)
	for c in rim.slice(0, IMPASSABLE):
		c["terrain"] = "mountain" if rng.next_int(3) == 0 else "water"

	# 2. Player core: capital + 6 neighbours.
	for id in _core_ids(w, PLAYER_CAP):
		_set_owner(cells[id], Types.PLAYER)

	# 3. Grow AI states by BFS from their capitals.
	_grow(w, _id_of(w, HAMLETS_CAP), HAMLETS, HAMLETS_SIZE, rng, func(c: Dictionary) -> int:
		return HexGrid.distance(HexGrid.axial(c), HAMLETS_CAP) * 10)
	# Barons are biased toward the player so the first war has a front.
	_grow(w, _id_of(w, BARONS_CAP), BARONS, BARONS_SIZE, rng, func(c: Dictionary) -> int:
		return HexGrid.distance(HexGrid.axial(c), BARONS_CAP) * 10 + HexGrid.distance(HexGrid.axial(c), PLAYER_CAP) * 10)

	# 4. Kinds and terrain.
	_set_kind(cells[_id_of(w, PLAYER_CAP)], "capital", "Столица")
	_set_kind(cells[_id_of(w, BARONS_CAP)], "capital", "Кремнёвый замок")
	_set_kind(cells[_id_of(w, HAMLETS_CAP)], "capital", "Хуторской двор")
	w.states[Types.PLAYER]["capital_id"] = _id_of(w, PLAYER_CAP)
	w.states[BARONS]["capital_id"] = _id_of(w, BARONS_CAP)
	w.states[HAMLETS]["capital_id"] = _id_of(w, HAMLETS_CAP)

	var player_free := _free(cells, Types.PLAYER, rng)
	if player_free.is_empty():
		return null
	_set_kind(player_free[0], "farm", "Мельничный луг")

	# Barons: a frontier mine (war goal bait), a city and a farm, preferring hexes near the player.
	var barons_free := _sort_by_player_distance(_free(cells, BARONS, rng))
	if barons_free.size() < 3:
		return null
	_set_kind(barons_free[0], "mine", "Кремнёвый карьер")
	_set_kind(barons_free[2], "city", "Ржавый узел")
	_set_kind(barons_free[barons_free.size() - 1], "farm", "Баронские поля")
	var hamlets_free := _sort_by_player_distance(_free(cells, HAMLETS, rng))
	if hamlets_free.size() < 2:
		return null
	_set_kind(hamlets_free[0], "mine", "Медная шахта")
	_set_kind(hamlets_free[1], "farm", "Хуторские нивы")
	var wild_free := _free(cells, Types.NOBODY, rng)
	if wild_free.size() > 0:
		_set_kind(wild_free[0], "farm", "Заброшенная мельница")
	if wild_free.size() > 1:
		_set_kind(wild_free[1], "mine", "Старая штольня")

	for c in cells:
		if not Types.is_passable(c) or c["kind"] != "plain" or reserved.has(c["id"]):
			continue
		var roll := rng.next_int(100)
		if roll < 14:
			c["terrain"] = "forest"
		elif roll < 24:
			c["terrain"] = "hills"

	return w


static func _set_owner(c: Dictionary, s: int) -> void:
	c["owner"] = s
	c["controller"] = s


static func _grow(w: World, start: int, state: int, size: int, rng: Rng, score: Callable) -> void:
	var cells := w.cells
	var owned := {start: true} # insertion-ordered set
	_set_owner(cells[start], state)
	while owned.size() < size:
		var frontier: Array = []
		var in_frontier := {}
		for id in owned:
			for n in w.neighbors[id]:
				if n < 0 or owned.has(n):
					continue
				var c: Dictionary = cells[n]
				if c["owner"] != Types.NOBODY or not Types.is_passable(c):
					continue
				if not in_frontier.has(n):
					in_frontier[n] = true
					frontier.append(c)
		if frontier.is_empty():
			return
		var best := 1 << 62
		var picks: Array = []
		for c in frontier:
			var s: int = score.call(c)
			if s < best:
				best = s
				picks = [c]
			elif s == best:
				picks.append(c)
		var p: Dictionary = rng.pick(picks)
		owned[p["id"]] = true
		_set_owner(p, state)


## Returns a list of problems; empty = valid.
static func validate_chapter_one(w: World) -> Array[String]:
	var problems: Array[String] = []
	var land: Array[Dictionary] = []
	for c in w.cells:
		if Types.is_passable(c):
			land.append(c)
	if land.size() != 50:
		problems.append("land hexes %d != 50" % land.size())
	var count := func(s: int) -> int:
		var k := 0
		for c in land:
			if c["owner"] == s:
				k += 1
		return k
	if count.call(Types.PLAYER) != 7:
		problems.append("player size != 7")
	if count.call(BARONS) != BARONS_SIZE:
		problems.append("barons size")
	if count.call(HAMLETS) != HAMLETS_SIZE:
		problems.append("hamlets size")
	# Front with Barons: at least 3 shared edges with the player.
	var shared := 0
	for c in land:
		if c["owner"] != Types.PLAYER:
			continue
		for n in w.neighbors[c["id"]]:
			if n >= 0 and w.cells[n]["owner"] == BARONS:
				shared += 1
	if shared < 3:
		problems.append("player-barons border %d < 3" % shared)
	# The first war must have something to win: non-core Barons hexes touching the player.
	var b_core := core_of(w, BARONS)
	var annexable := 0
	var front_hexes := 0
	for c in land:
		if c["owner"] != BARONS or not _touches_owner(w, c["id"], Types.PLAYER):
			continue
		front_hexes += 1
		if not b_core.has(c["id"]):
			annexable += 1
	if annexable < 2:
		problems.append("annexable front hexes %d < 2" % annexable)
	if front_hexes < 3:
		problems.append("barons front hexes %d < 3" % front_hexes)
	# Every state is connected.
	for s in [Types.PLAYER, BARONS, HAMLETS]:
		var ids: Array[int] = []
		for c in land:
			if c["owner"] == s:
				ids.append(c["id"])
		if not _connected(w, ids):
			problems.append("state %d disconnected" % s)
	# All land is mutually reachable (no isolated islands).
	var all_ids: Array[int] = []
	for c in land:
		all_ids.append(c["id"])
	if not _connected(w, all_ids):
		problems.append("land disconnected")
	return problems


static func _touches_owner(w: World, id: int, owner: int) -> bool:
	for n in w.neighbors[id]:
		if n >= 0 and w.cells[n]["owner"] == owner:
			return true
	return false


static func _connected(w: World, ids: Array[int]) -> bool:
	if ids.is_empty():
		return true
	var members := {}
	for id in ids:
		members[id] = true
	var seen := {ids[0]: true}
	var q: Array[int] = [ids[0]]
	while not q.is_empty():
		var id: int = q.pop_back()
		for n in w.neighbors[id]:
			if n >= 0 and members.has(n) and not seen.has(n):
				seen[n] = true
				q.append(n)
	return seen.size() == members.size()


## Ядро: capital + 6 neighbours that are officially owned by the same state (canon §3.1).
## Returns an insertion-ordered set {cell_id: true}.
static func core_of(w: World, state: int) -> Dictionary:
	var cap: int = w.states[state]["capital_id"] if state >= 0 and state < w.states.size() else -1
	var out := {}
	if cap < 0 or w.cells[cap]["owner"] != state:
		return out
	out[cap] = true
	for n in w.neighbors[cap]:
		if n >= 0 and w.cells[n]["owner"] == state:
			out[n] = true
	return out


static func official_value(w: World, state: int) -> int:
	var v := 0
	for c in w.cells:
		if c["owner"] == state and Types.is_passable(c):
			v += c["value"]
	return v


## Deep-copies cells and states; topology (neighbors, by_key) is shared (immutable).
static func clone_world(w: World) -> World:
	var out := World.new()
	out.map_seed = w.map_seed
	out.radius = w.radius
	out.neighbors = w.neighbors
	out.by_key = w.by_key
	for c in w.cells:
		out.cells.append(c.duplicate())
	for s in w.states:
		out.states.append(s.duplicate())
	return out
