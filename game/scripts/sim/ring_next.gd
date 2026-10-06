extends RefCounted
## Rings III+ (canon §12.1, 02 §15.2–15.5): new land grows around the whole old world (not a disk any more) in
## lobes aimed at its thinnest sides; each lobe holds one new state, the rest is a wild buffer. Distances are
## measured to the old world, so the ring follows its outline. Old cells never change (02 §17.2); new cells get
## ids after them and the topology is rebuilt. Deterministic from the seed; retries until the validator passes.
## Chapter II keeps its own generator (ring_gen.gd) so saved worlds regenerate cell for cell.

const Types := preload("res://scripts/sim/types.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const World := preload("res://scripts/sim/world.gd")
const MapGen := preload("res://scripts/sim/map_gen.gd")
const RingGen := preload("res://scripts/sim/ring_gen.gd")

const ALVARIA := 6
const SAREN := 7
const PACK := 8
const MAX_OLD_EDGES := 3  # F6
const CAP_SPACING := 5    # V06
const CAP_DEPTH := 3      # F6: rings III+ — a new capital ≥3 hexes from the old world

## Chapter III «Континент» (canon §12.1, 02 §15.3–15.4): +70 land, Альвария 22 (Wolf-hegemon), Сарен 15 (Fox),
## Серая Стая 15 (Raven), 18 wild; ~8% mountains and ~10% water; 3 lobes.
const CH3 := {
	"land": 70, "water": 9, "mountains": 7, "reach": 7, "dl": 5,  # dl: chapter II cap 4 + 1
	"states": [
		{"id": ALVARIA, "name": "state.alvaria", "color": 0xe8873a, "archetype": "wolf", "hegemon": true, "size": 22, "capital": "cell.alvaria_capital"},
		{"id": SAREN, "name": "state.saren", "color": 0xd9669b, "archetype": "fox", "size": 15, "capital": "cell.saren_capital"},
		{"id": PACK, "name": "state.pack", "color": 0x8d6e4c, "archetype": "raven", "size": 15, "capital": "cell.pack_capital"},
	],
	# order of placement (02 §15.2 step 9); counts per 02 §15.4
	"quota": [["raivite_vein", 1], ["port", 3], ["oil", 3], ["city", 4], ["factory", 2], ["military_base", 2], ["farm", 6], ["mine", 6]],
	"names": {
		"city": ["cell.ch3_city_steppe", "cell.ch3_city_cedar", "cell.ch3_city_crossroads", "cell.ch3_city_tannery"],
		"farm": ["cell.ch3_farm_feather", "cell.ch3_farm_millet", "cell.ch3_farm_horse", "cell.ch3_farm_honey", "cell.ch3_farm_barley", "cell.ch3_farm_berry"],
		"mine": ["cell.ch3_mine_coal", "cell.ch3_mine_tin", "cell.ch3_mine_red", "cell.ch3_mine_deep", "cell.ch3_mine_salt", "cell.ch3_mine_quartz"],
		"port": ["cell.ch3_port_amber", "cell.ch3_port_seal", "cell.ch3_port_north"],
		"oil": ["cell.ch3_oil_black", "cell.ch3_oil_tar", "cell.ch3_oil_steppe"],
		"factory": ["cell.ch3_factory_brick", "cell.ch3_factory_forge"],
		"military_base": ["cell.ch3_base_steppe", "cell.ch3_base_taiga"],
		"raivite_vein": ["cell.ch3_vein"],
	},
}

## Chapter IV «Индустриальный пояс» (canon §12.1, 02 §15.3–15.4, 07 §3.8): +90 land, Стальной Конклав 26
## (Turtle-hegemon), Вейлмарк 20 (Raven), Республика Озёр 21 (Owl), 23 wild; ~10% mountains (passes), ~10% water.
const CONCLAVE := 9
const VEILMARK := 10
const LAKES := 11
const CH4 := {
	"land": 90, "water": 11, "mountains": 11, "reach": 8, "dl": 7,  # dl: chapter III cap 6 + 1
	"states": [
		{"id": CONCLAVE, "name": "state.conclave", "color": 0x8a6b4f, "archetype": "turtle", "hegemon": true, "size": 26, "capital": "cell.conclave_capital"},
		{"id": VEILMARK, "name": "state.veilmark", "color": 0x5fa65a, "archetype": "raven", "size": 20, "capital": "cell.veilmark_capital"},
		{"id": LAKES, "name": "state.lakes", "color": 0x3aa7b8, "archetype": "owl", "size": 21, "capital": "cell.lakes_capital"},
	],
	"quota": [["raivite_vein", 1], ["port", 4], ["oil", 4], ["city", 5], ["factory", 3], ["military_base", 3], ["farm", 7], ["mine", 7]],
	"names": {
		"city": ["cell.ch4_city_smelter", "cell.ch4_city_rail", "cell.ch4_city_canyon", "cell.ch4_city_dynamo", "cell.ch4_city_mesa"],
		"farm": ["cell.ch4_farm_terrace", "cell.ch4_farm_oasis", "cell.ch4_farm_cactus", "cell.ch4_farm_greenhouse", "cell.ch4_farm_ranch", "cell.ch4_farm_orchard", "cell.ch4_farm_dust"],
		"mine": ["cell.ch4_mine_copper", "cell.ch4_mine_iron", "cell.ch4_mine_bauxite", "cell.ch4_mine_nickel", "cell.ch4_mine_open", "cell.ch4_mine_rust", "cell.ch4_mine_cobalt"],
		"port": ["cell.ch4_port_lake", "cell.ch4_port_ferry", "cell.ch4_port_dock", "cell.ch4_port_canal"],
		"oil": ["cell.ch4_oil_rig", "cell.ch4_oil_flare", "cell.ch4_oil_shale", "cell.ch4_oil_basin"],
		"factory": ["cell.ch4_factory_steel", "cell.ch4_factory_conveyor", "cell.ch4_factory_arms"],
		"military_base": ["cell.ch4_base_canyon", "cell.ch4_base_rail", "cell.ch4_base_lake"],
		"raivite_vein": ["cell.ch4_vein"],
	},
}

static var last_fail := ""


static func has_ring(w: World, cfg: Dictionary) -> bool:
	var last: int = (cfg["states"] as Array)[-1]["id"]
	return w.states.size() > last


static func states(cfg: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for s in cfg["states"]:
		out.append({"id": int(s["id"]), "name": String(s["name"]), "color": int(s["color"]), "archetype": String(s["archetype"]),
			# a new hegemon starts at its chapter's DL cap, the others at the previous cap + 1 (canon §9.16)
			"hegemon": bool(s.get("hegemon", false)), "capital_id": -1, "dev_level": int(cfg["dl"]) + (1 if bool(s.get("hegemon", false)) else 0)})
	return out


static func extend_chapter_three(w: World, seed_value: int) -> bool:
	return extend(w, CH3, seed_value)


static func extend_chapter_four(w: World, seed_value: int) -> bool:
	return extend(w, CH4, seed_value)


## Adds the ring to the world. Returns true on success (the world is unchanged on failure).
static func extend(w: World, cfg: Dictionary, seed_value: int) -> bool:
	if has_ring(w, cfg):
		return true
	for attempt in 100:
		var s := seed_value + attempt * 104729
		var add := _try(w, cfg, s)
		if not add.is_empty():
			var first_new := w.cells.size()
			_apply(w, cfg, add)
			RingGen._rivers(w, first_new, s)
			return true
	push_error("ring generator: no valid ring found (%s)" % last_fail)
	return false


static func _key(q: int, r: int) -> String:
	return HexGrid.hex_key(q, r)


## Lobe directions: the angles where the old world reaches least far from its centre, ≥ 90° apart, jittered.
static func _lobe_angles(w: World, n: int, rng) -> Array[float]:
	var reach: Array[float] = []
	for b in 36:
		var a := deg_to_rad(b * 10.0)
		var m := 0.0
		for c in w.cells:
			var p := RingGen._center(int(c["q"]), int(c["r"]))
			if p.length() < 0.5:
				continue
			if RingGen._ang_diff(atan2(-p.y, p.x), a) <= deg_to_rad(20.0):
				m = maxf(m, p.length())
		reach.append(m)
	var base: Array[float] = []
	var order: Array = range(36)
	order.sort_custom(func(x, y): return reach[x] < reach[y] if reach[x] != reach[y] else x < y)
	var gap := deg_to_rad(360.0 / n - 40.0)
	for b in order:
		var a := deg_to_rad(b * 10.0)
		var ok := true
		for o in base:
			if RingGen._ang_diff(a, o) < gap:
				ok = false
		if ok:
			base.append(a)
		if base.size() == n:
			break
	var out: Array[float] = []
	for a in base:
		out.append(a + deg_to_rad(float(rng.next_int(21) - 10)))  # jitter after spacing
	return out


## Builds the new cells as a separate list; {} when the attempt fails validation.
static func _try(w: World, cfg: Dictionary, seed_value: int) -> Dictionary:
	var rng := Rng.new(seed_value)
	var defs: Array = cfg["states"]
	var n_lobes := defs.size()
	var reach_max: int = cfg["reach"]
	var land_goal: int = cfg["land"]
	var lobes := _lobe_angles(w, n_lobes, rng)
	if lobes.size() < n_lobes:
		last_fail = "lobes"
		return {}
	# the biggest state (the hegemon) takes the thinnest side; the rest in angle order
	# distance of every candidate position to the old world (BFS outward over the hex grid)
	var old := {}
	for c in w.cells:
		old[_key(int(c["q"]), int(c["r"]))] = true
	var dist := {}
	var ring: Array = []
	for c in w.cells:
		for dv in HexGrid.DIRS:
			var k := _key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
			if not old.has(k) and not dist.has(k):
				dist[k] = 1
				ring.append(Vector2i(int(c["q"]) + dv.x, int(c["r"]) + dv.y))
	var head := 0
	while head < ring.size():
		var p: Vector2i = ring[head]
		head += 1
		var d: int = dist[_key(p.x, p.y)]
		if d >= reach_max:
			continue
		for dv in HexGrid.DIRS:
			var k := _key(p.x + dv.x, p.y + dv.y)
			if not old.has(k) and not dist.has(k):
				dist[k] = d + 1
				ring.append(Vector2i(p.x + dv.x, p.y + dv.y))
	var sigma := 0.6
	var cand := {}
	for p in ring:
		var k := _key(p.x, p.y)
		var th := RingGen._angle(p.x, p.y)
		var thick := 0.0
		for i in n_lobes:
			var amp := 6.5 * float(defs[i]["size"]) / 15.0
			thick += amp * exp(-pow(RingGen._ang_diff(th, lobes[i]) / sigma, 2.0))
		var noise := float(rng.next_int(1000)) / 1000.0
		cand[k] = {"q": p.x, "r": p.y, "d": int(dist[k]), "p": float(dist[k]) - thick - 0.8 * noise, "noise": 0.8 * noise}
	# per-lobe budgets: land = state + its share of the wild; the first (biggest) lobe also takes the main bay
	# and the spare mountains, one other lobe the small bay; two rim mountains each
	var water_n: int = cfg["water"]
	var bays := [water_n - water_n / 3, water_n / 3]
	var bay_lobes := [0, 1 + rng.next_int(n_lobes - 1)]
	var sum_sizes := 0
	for d in defs:
		sum_sizes += int(d["size"])
	var wild_total := land_goal - sum_sizes
	var budget: Array[int] = []
	var wild_left := wild_total
	for i in n_lobes:
		var wi := wild_total * int(defs[i]["size"]) / sum_sizes
		wild_left -= wi
		budget.append(int(defs[i]["size"]) + wi + 2)
	budget[0] += wild_left + int(cfg["mountains"]) - 2 * n_lobes
	for bi in 2:
		budget[int(bay_lobes[bi])] += int(bays[bi])
	# grow each lobe from its own stretch of the old rim, nearest to its direction first
	var picked: Array = []
	var owner_of := {}  # key -> lobe
	var old_pass := {}
	for oc in w.cells:
		if Types.is_passable(oc):
			old_pass[_key(int(oc["q"]), int(oc["r"]))] = true
	var by_land := func(k: String) -> bool:  # by later rings the old rim is mostly sea and mountains
		var c: Dictionary = cand[k]
		for dv in HexGrid.DIRS:
			if old_pass.has(_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)):
				return true
		return false
	for i in n_lobes:
		var frontier := {}
		for k in cand:
			if int(cand[k]["d"]) == 1 and not owner_of.has(k) and by_land.call(k):
				frontier[k] = true
		var score := func(k: String) -> float:
			var c: Dictionary = cand[k]
			return float(c["d"]) + 9.0 * RingGen._ang_diff(RingGen._angle(int(c["q"]), int(c["r"])), lobes[i]) + float(c["noise"])
		var grown_n := 0
		var started := false
		while grown_n < budget[i] and not frontier.is_empty():
			var best := ""
			var best_s := 0.0
			for k in frontier:
				var sc: float = score.call(k)
				if best == "" or sc < best_s or (sc == best_s and k < best):
					best = k
					best_s = sc
			frontier.erase(best)
			owner_of[best] = i
			var c: Dictionary = cand[best]
			c["lobe"] = i
			picked.append(c)
			grown_n += 1
			if not started:  # one seed on the rim, then the lobe grows only from what it holds
				started = true
				frontier = {}
			for dv in HexGrid.DIRS:
				var nk := _key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
				if cand.has(nk) and not owner_of.has(nk):
					frontier[nk] = true
		if grown_n < budget[i]:
			last_fail = "grow %d" % i
			return {}
	var by_key := {}
	for c in picked:
		c["terrain"] = "plain"
		c["kind"] = "plain"
		c["owner"] = Types.NOBODY
		c["name"] = ""
		by_key[_key(int(c["q"]), int(c["r"]))] = c
	var nbrs := func(c: Dictionary) -> Array:
		var out: Array = []
		for dv in HexGrid.DIRS:
			var nk := _key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
			if by_key.has(nk):
				out.append(by_key[nk])
		return out
	# all land of the world stays one piece: a bay or a mountain that would cut a lobe off is not placed
	var all_land_connected := func() -> bool:
		var nodes := {}
		for k in old_pass:
			nodes[k] = true
		for c in picked:
			if c["terrain"] == "plain":
				nodes[_key(int(c["q"]), int(c["r"]))] = true
		var first: String = nodes.keys()[0]
		var seen := {first: true}
		var stack: Array = [first]
		while not stack.is_empty():
			var k: String = stack.pop_back()
			var parts := k.split(",")
			for dv in HexGrid.DIRS:
				var nk := _key(int(parts[0]) + dv.x, int(parts[1]) + dv.y)
				if nodes.has(nk) and not seen.has(nk):
					seen[nk] = true
					stack.append(nk)
		return seen.size() == nodes.size()
	# water: a sea bay on the far edge of one lobe and a smaller one on another (ports need two coasts)
	for bi in 2:
		# the bay sits on the lobe's flank, away from its axis, so the deep middle stays land for the capital
		var bl: int = bay_lobes[bi]
		var side := func(c: Dictionary) -> float:
			return RingGen._ang_diff(RingGen._angle(int(c["q"]), int(c["r"])), lobes[bl]) * 10.0 + float(c["d"])
		var seed_c: Dictionary = {}
		for c in picked:
			if int(c["lobe"]) == bl and c["terrain"] == "plain" and int(c["d"]) >= 2 and (seed_c.is_empty() or float(side.call(c)) > float(side.call(seed_c))):
				seed_c = c
		if seed_c.is_empty():
			last_fail = "bay"
			return {}
		seed_c["terrain"] = "water"
		var bay: Array = [seed_c]
		while bay.size() < int(bays[bi]):
			var nxt: Dictionary = {}
			for b in bay:
				for n in nbrs.call(b):
					if n["terrain"] == "plain" and int(n["lobe"]) == bl and (nxt.is_empty() or float(side.call(n)) > float(side.call(nxt))):
						nxt = n
			if nxt.is_empty():
				last_fail = "bay2"
				return {}
			nxt["terrain"] = "water"
			bay.append(nxt)
		if not all_land_connected.call():
			last_fail = "bay cuts land"
			return {}
	# mountains: on the rim next to the old world, two per lobe off-centre (narrow necks), the rest inland
	var m_left: int = cfg["mountains"]
	for li in n_lobes:
		var rim: Array = picked.filter(func(c): return c["terrain"] == "plain" and int(c["d"]) == 1 and int(c["lobe"]) == li)
		rim.sort_custom(func(a, b):
			var ea := RingGen._ang_diff(RingGen._angle(int(a["q"]), int(a["r"])), lobes[li])
			var eb := RingGen._ang_diff(RingGen._angle(int(b["q"]), int(b["r"])), lobes[li])
			return ea > eb if ea != eb else _key(int(a["q"]), int(a["r"])) < _key(int(b["q"]), int(b["r"])))
		var placed_here := 0
		for c in rim:
			if placed_here >= 2 or m_left <= 0:
				break
			c["terrain"] = "mountain"
			if all_land_connected.call():
				placed_here += 1
				m_left -= 1
			else:
				c["terrain"] = "plain"
	var inland: Array = rng.shuffle(picked.filter(func(c): return c["terrain"] == "plain" and int(c["d"]) >= 3 and int(c["lobe"]) == 0))
	for c in inland:
		if m_left <= 0:
			break
		c["terrain"] = "mountain"
		if all_land_connected.call():
			m_left -= 1
		else:
			c["terrain"] = "plain"
	var land: Array = picked.filter(func(c): return c["terrain"] == "plain")
	if land.size() != land_goal:
		last_fail = "land %d" % land.size()
		return {}
	# capitals: deep in each lobe, mostly land around, ≥5 from every capital
	var all_caps: Array[Vector2i] = []
	for st in w.states:
		var cid: int = st["capital_id"]
		if cid >= 0:
			all_caps.append(Vector2i(int(w.cells[cid]["q"]), int(w.cells[cid]["r"])))
	var caps: Array = []
	for li in n_lobes:
		var best_c: Dictionary = {}
		var best_s := -1.0e9
		for c in land:
			if int(c["lobe"]) != li or int(c["d"]) < CAP_DEPTH:
				continue
			var land_n := 0
			for n in nbrs.call(c):
				if n["terrain"] == "plain":
					land_n += 1
			if land_n < 4:
				continue
			var cv := Vector2i(int(c["q"]), int(c["r"]))
			var ok := true
			for oc in all_caps:
				if HexGrid.distance(cv, oc) < CAP_SPACING:
					ok = false
			if not ok:
				continue
			var s := float(land_n) - 2.0 * RingGen._ang_diff(RingGen._angle(cv.x, cv.y), lobes[li]) + 0.1 * float(c["d"])
			if s > best_s:
				best_s = s
				best_c = c
		if best_c.is_empty():
			var deep := land.filter(func(c): return int(c["lobe"]) == li and int(c["d"]) >= CAP_DEPTH)
			var roomy := deep.filter(func(c): return nbrs.call(c).filter(func(n): return n["terrain"] == "plain").size() >= 4)
			last_fail = "capital %d (deep %d, roomy %d)" % [li, deep.size(), roomy.size()]
			return {}
		caps.append(best_c)
		all_caps.append(Vector2i(int(best_c["q"]), int(best_c["r"])))
	# simultaneous growth from the capitals; hexes touching the old world stay wild if possible
	var grown: Array = []
	var active: Array = []
	for i in n_lobes:
		caps[i]["owner"] = int(defs[i]["id"])
		grown.append([caps[i]])
		active.append(true)
	var any_active := true
	while any_active:
		any_active = false
		for i in n_lobes:
			if not active[i]:
				continue
			if (grown[i] as Array).size() >= int(defs[i]["size"]):
				active[i] = false
				continue
			var opts: Array = []
			var seen := {}
			for c in grown[i]:
				for n in nbrs.call(c):
					var nk := _key(int(n["q"]), int(n["r"]))
					if n["terrain"] == "plain" and int(n["owner"]) == Types.NOBODY and not seen.has(nk):
						seen[nk] = true
						opts.append(n)
			if opts.is_empty():
				active[i] = false
				continue
			var cap_v := Vector2i(int(caps[i]["q"]), int(caps[i]["r"]))
			var best_d := 1 << 30
			var picks: Array = []
			for n in opts:
				var dd := HexGrid.distance(Vector2i(int(n["q"]), int(n["r"])), cap_v) * 10 + (100 if int(n["d"]) == 1 else 0)
				if dd < best_d:
					best_d = dd
					picks = [n]
				elif dd == best_d:
					picks.append(n)
			var pk: Dictionary = picks[rng.next_int(picks.size())]
			pk["owner"] = int(defs[i]["id"])
			grown[i].append(pk)
			any_active = true
	# repair the 3-edge contact rule (F6): touching hexes go back to the wild, deeper wild hexes join instead
	var old_edges := func(c: Dictionary) -> int:
		var e := 0
		for dv in HexGrid.DIRS:
			if old_pass.has(_key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)):
				e += 1
		return e
	for i in n_lobes:
		for guard in 30:
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
				for n in nbrs.call(c):
					if n["terrain"] == "plain" and int(n["owner"]) == Types.NOBODY and int(old_edges.call(n)) == 0 and (repl.is_empty() or _key(int(n["q"]), int(n["r"])) < _key(int(repl["q"]), int(repl["r"]))):
						repl = n
			if repl.is_empty():
				break
			worst["owner"] = Types.NOBODY
			grown[i].erase(worst)
			repl["owner"] = int(defs[i]["id"])
			grown[i].append(repl)
	for i in n_lobes:
		if (grown[i] as Array).size() != int(defs[i]["size"]):
			last_fail = "size %d" % i
			return {}
	if not _place_specials(cfg, land, caps, nbrs, rng):
		return {}
	for i in n_lobes:
		caps[i]["kind"] = "capital"
		caps[i]["name"] = String(defs[i]["capital"])
	for c in land:
		if c["kind"] != "plain":
			continue
		var roll := rng.next_int(100)
		if roll < 22:
			c["terrain"] = "forest"
		elif roll < 40:
			c["terrain"] = "hills"
	var add := {"cells": picked, "caps": caps}
	var problems := validate(w, cfg, add)
	if not problems.is_empty():
		last_fail = str(problems)
		return {}
	return add


## Special hexes (02 §15.2 step 9, §15.5): every capital gets a farm and a mine within 3 hexes on its own land
## (F2); oil fields and the vein stay out of the cores (F4, F9); the wild gets at most one farm and one mine (F10).
static func _place_specials(cfg: Dictionary, land: Array, caps: Array, nbrs: Callable, rng) -> bool:
	var names: Dictionary = cfg["names"]
	var used := {}  # kind -> names used
	var put := func(c: Dictionary, kind: String) -> void:
		var k: int = used.get(kind, 0)
		c["kind"] = kind
		c["name"] = names[kind][k % (names[kind] as Array).size()]
		used[kind] = k + 1
	var core := {}
	for cp in caps:
		core[_key(int(cp["q"]), int(cp["r"]))] = true
		for n in nbrs.call(cp):
			core[_key(int(n["q"]), int(n["r"]))] = true
	var is_cap := func(c: Dictionary) -> bool:
		return caps.has(c)
	var left := {}
	for qk in cfg["quota"]:
		left[String(qk[0])] = int(qk[1])
	# F2 first
	for cp in caps:
		var cv := Vector2i(int(cp["q"]), int(cp["r"]))
		for kind in ["farm", "mine"]:
			var pool: Array = land.filter(func(c): return int(c["owner"]) == int(cp["owner"]) and c["kind"] == "plain" and not is_cap.call(c) \
				and HexGrid.distance(Vector2i(int(c["q"]), int(c["r"])), cv) <= 3)
			if pool.is_empty():
				last_fail = "F2"
				return false
			pool = rng.shuffle(pool)
			put.call(pool[0], kind)
			left[kind] = int(left[kind]) - 1
	var wild_used := {}
	for qk in cfg["quota"]:
		var kind: String = qk[0]
		var n_kind: int = left[kind]
		var pool: Array = land.filter(func(c): return c["kind"] == "plain" and not is_cap.call(c))
		if kind in ["oil", "raivite_vein"]:
			pool = pool.filter(func(c): return int(c["owner"]) != Types.NOBODY and not core.has(_key(int(c["q"]), int(c["r"]))))
		elif kind in ["farm", "mine"]:
			pass
		else:
			pool = pool.filter(func(c): return int(c["owner"]) != Types.NOBODY)
		if kind == "port":
			pool = pool.filter(func(c):
				for n in nbrs.call(c):
					if n["terrain"] == "water":
						return true
				return false)
		pool = rng.shuffle(pool)
		# spread between the states: fewest of this kind first
		var per_owner := {}
		for c in land:
			if c["kind"] == kind:
				per_owner[int(c["owner"])] = int(per_owner.get(int(c["owner"]), 0)) + 1
		var placed := 0
		var guard := 0
		while placed < n_kind and guard < 200:
			guard += 1
			var best: Dictionary = {}
			for c in pool:
				if c["kind"] != "plain":
					continue
				var o: int = c["owner"]
				if o == Types.NOBODY and int(wild_used.get(kind, 0)) >= 1:
					continue
				var score: int = int(per_owner.get(o, 0)) * 10 + (5 if o == Types.NOBODY else 0)
				if best.is_empty() or score < int(per_owner.get(int(best["owner"]), 0)) * 10 + (5 if int(best["owner"]) == Types.NOBODY else 0):
					best = c
			if best.is_empty():
				break
			put.call(best, kind)
			var bo: int = best["owner"]
			per_owner[bo] = int(per_owner.get(bo, 0)) + 1
			if bo == Types.NOBODY:
				wild_used[kind] = int(wild_used.get(kind, 0)) + 1
			placed += 1
		if placed < n_kind:
			last_fail = "quota %s" % kind
			return false
	return true


## Problems of a candidate ring (empty = valid): land, state sizes, the 3-edge contact rule, connectivity.
static func validate(w: World, cfg: Dictionary, add: Dictionary) -> Array[String]:
	var problems: Array[String] = []
	var cells: Array = add["cells"]
	var all := {}
	for c in w.cells:
		all[_key(int(c["q"]), int(c["r"]))] = {"owner": int(c["owner"]), "pass": Types.is_passable(c), "old": true}
	var land := 0
	var count := {}
	for c in cells:
		var walk: bool = c["terrain"] != "water" and c["terrain"] != "mountain"
		all[_key(int(c["q"]), int(c["r"]))] = {"owner": int(c["owner"]), "pass": walk, "old": false}
		if walk:
			land += 1
			count[int(c["owner"])] = int(count.get(int(c["owner"]), 0)) + 1
	if land != int(cfg["land"]):
		problems.append("ring land %d" % land)
	var ids: Array = []
	for s in cfg["states"]:
		ids.append(int(s["id"]))
		if int(count.get(int(s["id"]), 0)) != int(s["size"]):
			problems.append("state %d size %d" % [int(s["id"]), int(count.get(int(s["id"]), 0))])
	for s in ids:
		var edges := 0
		for c in cells:
			if int(c["owner"]) != s:
				continue
			for dv in HexGrid.DIRS:
				var nk := _key(int(c["q"]) + dv.x, int(c["r"]) + dv.y)
				if all.has(nk) and all[nk]["old"] and all[nk]["pass"]:
					edges += 1
		if edges > MAX_OLD_EDGES:
			problems.append("state %d touches the old world by %d edges" % [s, edges])
	for s in ids + [-1]:
		var mset := {}
		for k in all:
			if all[k]["pass"] and (s == -1 or int(all[k]["owner"]) == s):
				mset[k] = true
		if mset.is_empty():
			continue
		var first: String = mset.keys()[0]
		var seen := {first: true}
		var q: Array = [first]
		while not q.is_empty():
			var k: String = q.pop_back()
			var parts := k.split(",")
			for dv in HexGrid.DIRS:
				var nk := _key(int(parts[0]) + dv.x, int(parts[1]) + dv.y)
				if mset.has(nk) and not seen.has(nk):
					seen[nk] = true
					q.append(nk)
		if seen.size() != mset.size():
			problems.append("disconnected: %s" % ("all land" if s == -1 else "state %d" % s))
	return problems


static func _apply(w: World, cfg: Dictionary, add: Dictionary) -> void:
	for st in states(cfg):
		w.states.append(st)
	var base := w.cells.size()
	var cells: Array = add["cells"]
	var caps: Array = add["caps"]
	var reach := 0
	for i in cells.size():
		var c: Dictionary = cells[i]
		w.cells.append({
			"id": base + i, "q": int(c["q"]), "r": int(c["r"]), "terrain": String(c["terrain"]), "kind": String(c["kind"]),
			"value": int(Types.KIND_VALUE.get(String(c["kind"]), 1)), "owner": int(c["owner"]), "controller": int(c["owner"]),
			"fort": 0, "name": String(c["name"]),
		})
		var k := caps.find(c)
		if k >= 0:
			w.states[int(cfg["states"][k]["id"])]["capital_id"] = base + i
		reach = maxi(reach, HexGrid.distance(Vector2i(int(c["q"]), int(c["r"])), Vector2i.ZERO))
	w.radius = maxi(w.radius, reach)
	MapGen._build_topology(w)
