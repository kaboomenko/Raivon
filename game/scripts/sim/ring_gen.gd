extends RefCounted
## Chapter II «Речной край» ring (canon §12.1, 02 §15): +40 land around the chapter I disk — two lobes (north and
## south, the world grows up and down for the portrait screen) with a bay and a mountain ridge; Речная Лига (Owl, 16)
## in the north lobe, Орден Камня (Turtle, 14) in the south one, 10 wild hexes as a buffer. Grows the World in place:
## new cells get ids after the old ones and the topology is rebuilt (old cells never change, 02 §17.2).
## Deterministic from the seed; retries until the validator passes.

const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const World := preload("res://scripts/sim/world.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")

const LEAGUE := 4
const ORDER := 5
const OLD_RADIUS := 4
const MAX_REACH := 9
static var last_fail := ""
const NEW_LAND := 40
const WATER := 6
const MOUNTAINS := 4
const LEAGUE_SIZE := 16
const ORDER_SIZE := 14
const MAX_OLD_EDGES := 3  # a new state touches the old world by ≤3 edges (02 §17.2, F6)
const CAP_SPACING := 5
const AI_START_DL := 3  # previous chapter cap 2 + 1 (canon §9.16)
## Ring II special hexes (02 §15.4; veins and Dark Lakes are not in the client yet).
const QUOTA := {"city": 2, "farm": 3, "mine": 3, "port": 2, "military_base": 1, "raivite_vein": 1, "dark_lake": 1}
const NAMES := {
	"city": ["cell.ch2_city_ford", "cell.ch2_city_bridge"],
	"farm": ["cell.ch2_farm_reed", "cell.ch2_farm_willow", "cell.ch2_farm_delta"],
	"mine": ["cell.ch2_mine_granite", "cell.ch2_mine_slate", "cell.ch2_mine_iron"],
	"port": ["cell.ch2_port_fish", "cell.ch2_port_salt"],
	"military_base": ["cell.ch2_base"],
	"raivite_vein": ["cell.ch2_vein"],
	"dark_lake": ["cell.ch2_dark_lake"],
}


static func states() -> Array[Dictionary]:
	var out: Array[Dictionary] = [
		{"id": LEAGUE, "name": "state.league", "color": 0x2bb5a8, "archetype": "owl", "capital_id": -1, "dev_level": AI_START_DL},
		{"id": ORDER, "name": "state.order", "color": 0x8e7cc3, "archetype": "turtle", "capital_id": -1, "dev_level": AI_START_DL},
	]
	return out


static func has_ring_two(w: World) -> bool:
	return w.states.size() > ORDER


## Adds ring II to a chapter I world. Returns true on success (the world is unchanged on failure).
static func extend_chapter_two(w: World, seed_value: int) -> bool:
	if has_ring_two(w):
		return true
	for attempt in 50:
		var add := _try(w, seed_value + attempt * 104729)
		if not add.is_empty():
			var first_new := w.cells.size()
			_apply(w, add)
			_rivers(w, first_new, seed_value + attempt * 104729)
			return true
	push_error("ring II generator: no valid ring found")
	return false


static func _angle(q: int, r: int) -> float:
	var x := 1.5 * q
	var z := sqrt(3.0) * (r + q / 2.0)
	return atan2(-z, x)  # 0 = east, PI/2 = north (up on screen)


static func _ang_diff(a: float, b: float) -> float:
	return absf(wrapf(a - b, -PI, PI))


## Builds the new cells as a separate list; {} when the attempt fails validation.
static func _try(w: World, seed_value: int) -> Dictionary:
	var rng := Rng.new(seed_value)
	var lobes: Array[float] = []
	for base in [100.0, 295.0]:  # north, and south-east (clear of the player capital in the south)
		lobes.append(deg_to_rad(base + float(rng.next_int(41) - 20)))
	var sigma := 0.5  # narrow necks: few ring hexes touch the old world
	var amp := 5.0
	# candidate positions around the disk, with a noise value each
	var cand := {}  # key -> {q, r, d, p}
	for q in range(-MAX_REACH, MAX_REACH + 1):
		for r in range(-MAX_REACH, MAX_REACH + 1):
			var d := HexGrid.distance(Vector2i(q, r), Vector2i.ZERO)
			if d <= OLD_RADIUS or d > MAX_REACH:
				continue
			var th := _angle(q, r)
			var thick := 0.0
			for c in lobes:
				thick += amp * (1.0 + 0.35 * absf(sin(c))) * exp(-pow(_ang_diff(th, c) / sigma, 2.0))
			var noise := float(rng.next_int(1000)) / 1000.0
			cand[HexGrid.hex_key(q, r)] = {"q": q, "r": r, "d": d, "p": (d - OLD_RADIUS) - thick - 0.8 * noise}
	# greedy growth from the old rim, lowest score first
	var total := NEW_LAND + WATER + MOUNTAINS
	var picked: Array = []
	var picked_set := {}
	var frontier := {}
	for k in cand:
		if int(cand[k]["d"]) == OLD_RADIUS + 1:
			frontier[k] = true
	while picked.size() < total and not frontier.is_empty():
		var best := ""
		for k in frontier:
			if best == "" or float(cand[k]["p"]) < float(cand[best]["p"]) or (float(cand[k]["p"]) == float(cand[best]["p"]) and k < best):
				best = k
		frontier.erase(best)
		picked.append(cand[best])
		picked_set[best] = true
		var bq: int = cand[best]["q"]
		var br: int = cand[best]["r"]
		for dv in HexGrid.DIRS:
			var nk := HexGrid.hex_key(bq + dv.x, br + dv.y)
			if cand.has(nk) and not picked_set.has(nk):
				frontier[nk] = true
	if picked.size() < total:
		last_fail = "step1"
		return {}
	# which lobe every new cell belongs to
	for c in picked:
		var th := _angle(int(c["q"]), int(c["r"]))
		c["lobe"] = 0 if _ang_diff(th, lobes[0]) <= _ang_diff(th, lobes[1]) else 1
		c["terrain"] = "plain"
		c["kind"] = "plain"
		c["owner"] = Types.NOBODY
		c["name"] = ""
	var by_key := {}
	for c in picked:
		by_key[HexGrid.hex_key(int(c["q"]), int(c["r"]))] = c
	# a bay of 6 water cells on the outer edge of one lobe
	var bay_lobe := rng.next_int(2)
	var seed_c: Dictionary = {}
	for c in picked:
		if int(c["lobe"]) == bay_lobe and (seed_c.is_empty() or int(c["d"]) > int(seed_c["d"]) or (int(c["d"]) == int(seed_c["d"]) and float(c["p"]) > float(seed_c["p"]))):
			seed_c = c
	var bay: Array = [seed_c]
	seed_c["terrain"] = "water"
	while bay.size() < WATER:
		var nxt: Dictionary = {}
		for b in bay:
			for dv in HexGrid.DIRS:
				var nk := HexGrid.hex_key(int(b["q"]) + dv.x, int(b["r"]) + dv.y)
				if by_key.has(nk) and by_key[nk]["terrain"] == "plain":
					var n: Dictionary = by_key[nk]
					if nxt.is_empty() or int(n["d"]) > int(nxt["d"]) or (int(n["d"]) == int(nxt["d"]) and float(n["p"]) > float(nxt["p"])):
						nxt = n
		if nxt.is_empty():
			last_fail = "step2"
			return {}
		nxt["terrain"] = "water"
		bay.append(nxt)
	# mountains on the rim next to the old world (02 §15.2: the rim is often mountains), two per lobe neck,
	# off-centre so each lobe stays connected to the old world
	var rim := picked.filter(func(c): return c["terrain"] == "plain" and int(c["d"]) == OLD_RADIUS + 1)
	var placed := 0
	for lobe in 2:
		var mine: Array = rim.filter(func(c): return int(c["lobe"]) == lobe)
		mine.sort_custom(func(a, b):
			var ea := _ang_diff(_angle(int(a["q"]), int(a["r"])), lobes[lobe])
			var eb := _ang_diff(_angle(int(b["q"]), int(b["r"])), lobes[lobe])
			return ea > eb if ea != eb else HexGrid.hex_key(int(a["q"]), int(a["r"])) < HexGrid.hex_key(int(b["q"]), int(b["r"])))
		for c in mine.slice(0, MOUNTAINS / 2):
			c["terrain"] = "mountain"
			placed += 1
	if placed < MOUNTAINS:
		var rest := picked.filter(func(c): return c["terrain"] == "plain" and int(c["d"]) == OLD_RADIUS + 1)
		for c in rest.slice(0, MOUNTAINS - placed):
			c["terrain"] = "mountain"
	var land := picked.filter(func(c): return c["terrain"] == "plain")
	if land.size() != NEW_LAND:
		last_fail = "step3"
		return {}
	# capitals: deep in each lobe, mostly surrounded by land, far from the old world and every capital
	var old_caps: Array[Vector2i] = []
	for st in w.states:
		var cid: int = st["capital_id"]
		if cid >= 0:
			old_caps.append(Vector2i(int(w.cells[cid]["q"]), int(w.cells[cid]["r"])))
	var caps: Array = []
	for lobe in 2:
		var best_c: Dictionary = {}
		var best_s := -1.0e9
		for c in land:
			if int(c["lobe"]) != lobe or int(c["d"]) < OLD_RADIUS + 2:
				continue
			var land_n := 0
			for dv in HexGrid.DIRS:
				var nk := HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
				if (by_key.has(nk) and by_key[nk]["terrain"] == "plain"):
					land_n += 1
			if land_n < 4:
				continue
			var cv := Vector2i(int(c["q"]), int(c["r"]))
			var ok := true
			for oc in old_caps:
				if HexGrid.distance(cv, oc) < CAP_SPACING:
					ok = false
			for nc in caps:
				if HexGrid.distance(cv, Vector2i(int(nc["q"]), int(nc["r"]))) < CAP_SPACING:
					ok = false
			if not ok:
				continue
			var s := float(land_n) - 2.0 * _ang_diff(_angle(cv.x, cv.y), lobes[lobe]) + 0.1 * float(c["d"])
			if s > best_s:
				best_s = s
				best_c = c
		if best_c.is_empty():
			last_fail = "step4"
			return {}
		caps.append(best_c)
	# the League takes the north lobe (next to the Barons), the Order the south one (next to the player)
	var owners := [LEAGUE, ORDER]
	var sizes := [LEAGUE_SIZE, ORDER_SIZE]
	# simultaneous growth from the capitals over ring land, ties shuffled by this step's stream
	var grown := [[caps[0]], [caps[1]]]
	caps[0]["owner"] = owners[0]
	caps[1]["owner"] = owners[1]
	var active := [true, true]
	while active[0] or active[1]:
		for i in 2:
			if not active[i]:
				continue
			if grown[i].size() >= sizes[i]:
				active[i] = false
				continue
			var opts: Array = []
			var seen := {}
			for c in grown[i]:
				for dv in HexGrid.DIRS:
					var nk := HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
					if by_key.has(nk) and not seen.has(nk):
						var n: Dictionary = by_key[nk]
						if n["terrain"] == "plain" and int(n["owner"]) == Types.NOBODY:
							seen[nk] = true
							opts.append(n)
			if opts.is_empty():
				active[i] = false
				continue
			var cap_v := Vector2i(int(caps[i]["q"]), int(caps[i]["r"]))
			var best_d := 1 << 30
			var picks: Array = []
			for n in opts:
				# hexes touching the old world stay wild if possible: a new state meets the old world by ≤3 edges
				var dd := HexGrid.distance(Vector2i(int(n["q"]), int(n["r"])), cap_v) * 10 + (100 if int(n["d"]) <= OLD_RADIUS + 1 else 0)
				if dd < best_d:
					best_d = dd
					picks = [n]
				elif dd == best_d:
					picks.append(n)
			var p: Dictionary = picks[rng.next_int(picks.size())]
			p["owner"] = owners[i]
			grown[i].append(p)
	# repair: hand hexes that touch the old world back to the wild, take deeper wild hexes instead
	var old_keys := {}
	for oc in w.cells:
		if Types.is_passable(oc):
			old_keys[HexGrid.hex_key(int(oc["q"]), int(oc["r"]))] = true
	var old_edges := func(c: Dictionary) -> int:
		var e := 0
		for dv in HexGrid.DIRS:
			if old_keys.has(HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)):
				e += 1
		return e
	for i in 2:
		for guard in 20:
			var total_e := 0
			var worst: Dictionary = {}
			for c in grown[i]:
				var e: int = old_edges.call(c)
				total_e += e
				if e > 0 and c != caps[i] and (worst.is_empty() or e > int(old_edges.call(worst))):
					worst = c
			if total_e <= MAX_OLD_EDGES or worst.is_empty():
				break
			var repl: Dictionary = {}
			for c in grown[i]:
				for dv in HexGrid.DIRS:
					var nk := HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
					if by_key.has(nk):
						var n: Dictionary = by_key[nk]
						if n["terrain"] == "plain" and int(n["owner"]) == Types.NOBODY and int(old_edges.call(n)) == 0 and (repl.is_empty() or HexGrid.hex_key(int(n["q"]), int(n["r"])) < HexGrid.hex_key(int(repl["q"]), int(repl["r"]))):
							repl = n
			if repl.is_empty():
				break
			worst["owner"] = Types.NOBODY
			grown[i].erase(worst)
			repl["owner"] = owners[i]
			grown[i].append(repl)
	if grown[0].size() != LEAGUE_SIZE or grown[1].size() != ORDER_SIZE:
		last_fail = "step5"
		return {}
	# special hexes: ports on land next to water, then cities, farms, mines, the base — by score, ties by seed
	var specials: Array = []
	for kind in ["raivite_vein", "port", "city", "military_base", "farm", "mine", "dark_lake"]:
		var n_kind: int = QUOTA[kind]
		var pool: Array = land.filter(func(c): return c["kind"] == "plain" and c != caps[0] and c != caps[1])
		if kind == "port":
			pool = pool.filter(func(c):
				for dv in HexGrid.DIRS:
					var nk := HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
					if by_key.has(nk) and by_key[nk]["terrain"] == "water":
						return true
				return false)
		pool = rng.shuffle(pool)
		# spread: one of each kind per state first, then the wild
		pool.sort_custom(func(a, b):
			var ra := 0 if int(a["owner"]) != Types.NOBODY else 1
			var rb := 0 if int(b["owner"]) != Types.NOBODY else 1
			return ra < rb)
		var taken_owner := {}
		var k := 0
		for c in pool:
			if k >= n_kind:
				break
			if taken_owner.get(int(c["owner"]), 0) >= 1 + n_kind / 2 and k < n_kind - 1:
				continue
			c["kind"] = kind
			c["name"] = NAMES[kind][k % NAMES[kind].size()]
			taken_owner[int(c["owner"])] = taken_owner.get(int(c["owner"]), 0) + 1
			k += 1
		if k < n_kind:
			last_fail = "step6"
			return {}
	caps[0]["kind"] = "capital"
	caps[0]["name"] = "cell.league_capital"
	caps[1]["kind"] = "capital"
	caps[1]["name"] = "cell.order_capital"
	for c in land:
		if c["kind"] != "plain":
			continue
		var roll := rng.next_int(100)
		if roll < 16:
			c["terrain"] = "forest"
		elif roll < 26:
			c["terrain"] = "hills"
	var add := {"cells": picked, "caps": [caps[0], caps[1]]}
	if not validate(w, add).is_empty():
		last_fail = str(validate(w, add)) + " step7"
		return {}
	return add


## Problems of a candidate ring (empty = valid): sizes, connectivity, the 3-edge contact rule.
static func validate(w: World, add: Dictionary) -> Array[String]:
	var problems: Array[String] = []
	var cells: Array = add["cells"]
	var all := {}  # key -> {owner, passable}
	for c in w.cells:
		all[HexGrid.hex_key(int(c["q"]), int(c["r"]))] = {"owner": int(c["owner"]), "pass": Types.is_passable(c), "old": true}
	var land := 0
	var count := {LEAGUE: 0, ORDER: 0}
	for c in cells:
		var walk: bool = c["terrain"] != "water" and c["terrain"] != "mountain"
		all[HexGrid.hex_key(int(c["q"]), int(c["r"]))] = {"owner": int(c["owner"]), "pass": walk, "old": false}
		if walk:
			land += 1
			if count.has(int(c["owner"])):
				count[int(c["owner"])] += 1
	if land != NEW_LAND:
		problems.append("ring land %d != %d" % [land, NEW_LAND])
	if count[LEAGUE] != LEAGUE_SIZE or count[ORDER] != ORDER_SIZE:
		problems.append("state sizes %s" % str(count))
	# contact with the old world
	for s in [LEAGUE, ORDER]:
		var edges := 0
		for c in cells:
			if int(c["owner"]) != s:
				continue
			for dv in HexGrid.DIRS:
				var nk := HexGrid.hex_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
				if all.has(nk) and all[nk]["old"] and all[nk]["pass"]:
					edges += 1
		if edges > MAX_OLD_EDGES:
			problems.append("state %d touches the old world by %d edges" % [s, edges])
	# connectivity: every state, and all land of the world
	for s in [LEAGUE, ORDER, -1]:
		var members: Array = []
		for k in all:
			if all[k]["pass"] and (s == -1 or int(all[k]["owner"]) == s):
				members.append(k)
		if members.is_empty():
			continue
		var mset := {}
		for k in members:
			mset[k] = true
		var seen := {members[0]: true}
		var q: Array = [members[0]]
		while not q.is_empty():
			var k: String = q.pop_back()
			var parts := k.split(",")
			var cq := int(parts[0])
			var cr := int(parts[1])
			for dv in HexGrid.DIRS:
				var nk := HexGrid.hex_key(cq + dv.x, cr + dv.y)
				if mset.has(nk) and not seen.has(nk):
					seen[nk] = true
					q.append(nk)
		if seen.size() != mset.size():
			problems.append("disconnected: %s" % ("all land" if s == -1 else "state %d" % s))
	return problems


## Rivers (02 §15.2 step 5): 2–3 chains of hex edges in the ring that start by the mountains and run outward
## to the sea or the edge of the world; only edges between two land hexes count. Never along the player's core.
static func _rivers(w: World, first_new: int, seed_value: int) -> void:
	var rng := Rng.new(seed_value ^ 0x51AE)
	var corners := {}  # corner key -> {pos: Vector2, links: {corner key: [cell a, cell b]}}
	for c in w.cells:
		var ctr := _center(int(c["q"]), int(c["r"]))
		var pts: Array = []
		for k in 6:
			pts.append(ctr + Vector2(cos(PI / 3.0 * k), sin(PI / 3.0 * k)))
		for k in 6:
			var p: Vector2 = pts[k]
			var q: Vector2 = pts[(k + 1) % 6]
			var mid := (p + q) / 2.0
			var other := _cell_at(w, ctr + 2.0 * (mid - ctr))
			var kp := _ckey(p)
			var kq := _ckey(q)
			for pair in [[kp, p, kq], [kq, q, kp]]:
				if not corners.has(pair[0]):
					corners[pair[0]] = {"pos": pair[1], "links": {}}
				corners[pair[0]]["links"][pair[2]] = [int(c["id"]), other]
	var core := MapGen.core_of(w, Types.PLAYER)
	var land := func(id: int) -> bool:
		return id >= 0 and Types.is_passable(w.cells[id])
	var starts: Array = []
	for k in corners:
		var near_mountain := false
		var ring_land := 0
		for ok in corners[k]["links"]:
			for id in corners[k]["links"][ok]:
				if id >= first_new and w.cells[id]["terrain"] == "mountain":
					near_mountain = true
				if id >= first_new and land.call(id):
					ring_land += 1
		if near_mountain and ring_land >= 2:
			starts.append(k)
	starts.sort()
	starts = rng.shuffle(starts)
	var made := 0
	for s0 in starts:
		if made >= 3:
			break
		var path_edges: Array = []
		var seen := {s0: true}
		var cur: String = s0
		for step in 14:
			var best := ""
			var best_d := -1.0
			for nk in corners[cur]["links"]:
				if seen.has(nk):
					continue
				var cells_e: Array = corners[cur]["links"][nk]
				if cells_e[1] < 0 and cells_e[0] < first_new:
					continue
				var d: float = (corners[nk]["pos"] as Vector2).length() + float(rng.next_int(100)) / 250.0
				if d > best_d:
					best_d = d
					best = nk
			if best == "":
				break
			var pair: Array = corners[cur]["links"][best]
			var a: int = pair[0]
			var b: int = pair[1]
			seen[best] = true
			cur = best
			if a < 0 or b < 0 or not land.call(a) or not land.call(b):
				if (a >= 0 and w.cells[a]["terrain"] == "water") or (b >= 0 and w.cells[b]["terrain"] == "water") or a < 0 or b < 0:
					break  # reached the sea or the edge of the world
				continue
			if core.has(a) or core.has(b) or (a < first_new and b < first_new):
				continue
			path_edges.append(World.edge_key(a, b))
		var fresh := path_edges.filter(func(e): return not w.rivers.has(e))
		if fresh.size() >= 4:
			for e in fresh:
				w.rivers[e] = true
			made += 1


static func _center(q: int, r: int) -> Vector2:
	return Vector2(1.5 * q, sqrt(3.0) * (r + q / 2.0))


static func _ckey(p: Vector2) -> String:
	return "%d,%d" % [roundi(p.x * 100.0), roundi(p.y * 100.0)]


static func _cell_at(w: World, p: Vector2) -> int:
	var q := p.x / 1.5
	var r := p.y / sqrt(3.0) - q / 2.0
	var s := -q - r
	var rq := roundf(q)
	var rr := roundf(r)
	var rs := roundf(s)
	if absf(rq - q) > absf(rr - r) and absf(rq - q) > absf(rs - s):
		rq = -rr - rs
	elif absf(rr - r) > absf(rs - s):
		rr = -rq - rs
	return w.id_at(int(rq), int(rr))


static func _apply(w: World, add: Dictionary) -> void:
	for st in states():
		w.states.append(st)
	var base := w.cells.size()
	var cells: Array = add["cells"]
	for i in cells.size():
		var c: Dictionary = cells[i]
		var cell := {
			"id": base + i, "q": int(c["q"]), "r": int(c["r"]), "terrain": String(c["terrain"]), "kind": String(c["kind"]),
			"value": int(Types.KIND_VALUE.get(String(c["kind"]), 1)), "owner": int(c["owner"]), "controller": int(c["owner"]),
			"fort": 0, "name": String(c["name"]),
		}
		w.cells.append(cell)
		if c == add["caps"][0]:
			w.states[LEAGUE]["capital_id"] = base + i
		elif c == add["caps"][1]:
			w.states[ORDER]["capital_id"] = base + i
	w.radius = MAX_REACH
	MapGen._build_topology(w)
