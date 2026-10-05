extends RefCounted
## Army march on the strategic map (canon §8.1, §13): 20 s per hex over own land, 40 s over occupied and wild
## land; never through hexes held by another state. A march is a movement, not a timer — nothing speeds it up.
## State lives on the army: a["march"] = {"path": [next hex, …, destination], "t0": leg start, "leg": seconds}.
## a["hex"] is always the last hex reached, so an offensive that starts mid-march fights from there (04 §7.2).

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")

const OWN_SEC := 20
const OTHER_SEC := 40


## Seconds to enter `hex` for `side`, or -1 when the hex can't be marched through.
static func leg_seconds(world: World, side: int, hex: int) -> int:
	var c: Dictionary = world.cells[hex]
	if not Types.is_passable(c):
		return -1
	if c["owner"] == side and c["controller"] == side:
		return OWN_SEC
	if c["controller"] == side or (c["owner"] == Types.NOBODY and c["controller"] == Types.NOBODY):
		return OTHER_SEC
	return -1


## Fastest route (Dijkstra, ties by hex id): {"path": [hexes after `from` … `to`], "seconds": total} or {}.
static func route(world: World, side: int, from: int, to: int) -> Dictionary:
	if from == to or leg_seconds(world, side, to) < 0:
		return {}
	var dist := {from: 0}
	var prev := {}
	var open: Array = [from]
	var done := {}
	while not open.is_empty():
		var best := 0
		for i in range(1, open.size()):
			var a: int = open[i]
			var b: int = open[best]
			if int(dist[a]) < int(dist[b]) or (int(dist[a]) == int(dist[b]) and a < b):
				best = i
		var cur: int = open[best]
		open.remove_at(best)
		if done.has(cur):
			continue
		done[cur] = true
		if cur == to:
			break
		for n in world.neighbors[cur]:
			var nid: int = n
			if nid < 0:
				continue
			var leg := leg_seconds(world, side, nid)
			if leg < 0 or done.has(nid):
				continue
			var nd: int = int(dist[cur]) + leg
			if not dist.has(nid) or nd < int(dist[nid]):
				dist[nid] = nd
				prev[nid] = cur
				open.append(nid)
	if not dist.has(to):
		return {}
	var path: Array = []
	var h := to
	while h != from:
		path.push_front(h)
		h = prev[h]
	return {"path": path, "seconds": int(dist[to])}


## Orders `army` to march to `to`. Returns the route ({} when unreachable; the army then stays put).
static func order(world: World, army: Dictionary, to: int, now: int) -> Dictionary:
	var r := route(world, int(army["side"]), int(army["hex"]), to)
	if r.is_empty():
		return {}
	var path: Array = r["path"]
	army["march"] = {"path": path.duplicate(), "t0": now, "leg": leg_seconds(world, int(army["side"]), int(path[0]))}
	return r


static func is_marching(army: Dictionary) -> bool:
	return army.get("march") != null and typeof(army["march"]) == TYPE_DICTIONARY and not (army["march"]["path"] as Array).is_empty()


static func stop(army: Dictionary) -> void:
	army.erase("march")


## Advances the march to `now`: every finished leg moves a["hex"] on. A hex that became impassable (peace
## treaty, enemy capture) ends the march where the army stands. Returns true when the army arrived or stopped.
static func step(world: World, army: Dictionary, now: int) -> bool:
	if not is_marching(army):
		return false
	var m: Dictionary = army["march"]
	var path: Array = m["path"]
	while not path.is_empty() and now >= int(m["t0"]) + int(m["leg"]):
		army["hex"] = int(path.pop_front())
		m["t0"] = int(m["t0"]) + int(m["leg"])
		if path.is_empty():
			break
		var leg := leg_seconds(world, int(army["side"]), int(path[0]))
		if leg < 0:
			path.clear()
			break
		m["leg"] = leg
	if path.is_empty():
		army.erase("march")
		return true
	return false


## 0..1 along the current leg (for drawing), and the hex the army is heading to; {} when not marching.
static func progress(army: Dictionary, now_f: float) -> Dictionary:
	if not is_marching(army):
		return {}
	var m: Dictionary = army["march"]
	var f := clampf((now_f - float(m["t0"])) / maxf(1.0, float(m["leg"])), 0.0, 1.0)
	return {"to": int((m["path"] as Array)[0]), "f": f}


## Seconds until arrival at the destination.
static func seconds_left(world: World, army: Dictionary, now: int) -> int:
	if not is_marching(army):
		return 0
	var m: Dictionary = army["march"]
	var path: Array = m["path"]
	var left := maxi(0, int(m["t0"]) + int(m["leg"]) - now)
	for i in range(1, path.size()):
		left += maxi(0, leg_seconds(world, int(army["side"]), int(path[i])))
	return left
