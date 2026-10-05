extends RefCounted
## Supply and pockets (canon §9.7), port of packages/sim/src/topology.ts.
## Supply depends only on connectivity, not distance. Sets are Dictionaries {cell_id: true}.

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")


## Hexes controlled by `side` that can trace a path of `side`-controlled hexes to a supply source
## (own capital / military base / port that is both owned and controlled).
static func supplied(w: World, side: int, blocked: Dictionary = {}) -> Dictionary:
	var out := {}
	var queue: Array[int] = []
	for c in w.cells:
		if c["controller"] != side or c["owner"] != side or blocked.has(c["id"]):
			continue
		var kind: String = c["kind"]
		if kind == "capital" or kind == "military_base" or kind == "port":
			out[c["id"]] = true
			queue.append(c["id"])
	while not queue.is_empty():
		var id: int = queue.pop_back()
		for n in w.neighbors[id]:
			if n < 0 or out.has(n) or blocked.has(n):
				continue
			var c: Dictionary = w.cells[n]
			if not Types.is_passable(c) or c["controller"] != side:
				continue
			out[n] = true
			queue.append(n)
	return out


## Pockets of `side` against `enemy`: connected groups of ≤12 `side`-controlled hexes without supply
## that border `enemy` (an isolated exclave not touching the enemy is not a pocket).
## Each group is a sorted Array[int]; groups are ordered by their first-found cell id.
static func pockets(w: World, side: int, enemy: int, blocked: Dictionary = {}) -> Array:
	var sup := supplied(w, side, blocked)
	var seen := {}
	var result: Array = []
	for c in w.cells:
		var cid: int = c["id"]
		if c["controller"] != side or not Types.is_passable(c) or sup.has(cid) or seen.has(cid):
			continue
		var group: Array[int] = []
		var queue: Array[int] = [cid]
		seen[cid] = true
		var touches_enemy := false
		while not queue.is_empty():
			var id: int = queue.pop_back()
			group.append(id)
			for n in w.neighbors[id]:
				if n < 0:
					continue
				var nc: Dictionary = w.cells[n]
				if nc["controller"] == enemy:
					touches_enemy = true
				if nc["controller"] != side or not Types.is_passable(nc) or sup.has(n) or seen.has(n):
					continue
				seen[n] = true
				queue.append(n)
		if touches_enemy and group.size() <= 12:
			group.sort()
			result.append(group)
	return result


## Ring distance (BFS over hexes in `within`) from a seed set; used by the peace ceremony ink wave.
## Returns {cell_id: ring}.
static func rings_from(w: World, seeds: Array, within: Dictionary) -> Dictionary:
	var dist := {}
	var frontier: Array[int] = []
	for s in seeds:
		dist[s] = 0
		frontier.append(s)
	var d := 0
	while not frontier.is_empty():
		d += 1
		var next: Array[int] = []
		for id in frontier:
			for n in w.neighbors[id]:
				if n < 0 or dist.has(n) or not within.has(n):
					continue
				dist[n] = d
				next.append(n)
		frontier = next
	return dist
