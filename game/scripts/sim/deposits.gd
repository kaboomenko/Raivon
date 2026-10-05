extends RefCounted
## Yellow-outlined deposits and convoys (canon §5.2, §8.2). Deterministic: all randomness comes from the
## seeded Rng, time is integer unix seconds passed in by the caller.
##
## Deposit: {id, hex, res, size ("S"|"M"|"L"), amount, gather_sec, expires, convoy (-1 = free)}
## Convoy:  {id, deposit, hex, res, amount, depart, arrive, gathered, back}

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

const RES_KINDS: Array[String] = ["gold", "food", "metal"]
## Translation keys of deposit names.
const NAMES := {"gold": "dep.gold", "food": "dep.food", "metal": "dep.metal"}
## Size → hours of the player's gross production of that resource, and the gather time (canon §5.2).
const SIZE_HOURS := {"S": 0.5, "M": 1.5, "L": 4.0}
const SIZE_GATHER := {"S": 15 * 60, "M": 45 * 60, "L": 120 * 60}
const LIFETIME := 12 * 3600  # unclaimed deposits vanish (canon §5.2)
const RESPAWN_MIN := 30 * 60
const RESPAWN_MAX := 90 * 60
const STEP_OWN := 10  # convoy seconds per hex over own land, 20 elsewhere (canon §8.2)
const STEP_OTHER := 20
## Convoys by development level, index = DL (canon §8.2 table).
const CONVOYS: Array[int] = [2, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6]

var rng: Rng
var active: Array = []
var convoys: Array = []
var pending_respawn: Array = []  # unix times when a new deposit appears
var next_id := 1


func _init(seed_value: int = 1) -> void:
	rng = Rng.new(seed_value)


static func quota(world: World) -> int:
	var n := 0
	for c in world.cells:
		if Types.is_passable(c):
			n += 1
	return ceili(n / 8.0)


## Keeps the deposit quota filled, expires stale ones and moves convoys along; returns events:
## {type: "convoy_back", res, amount, hex} | {type: "spawned", hex} | {type: "expired", hex}.
func tick(world: World, gross_per_hour: Dictionary, now: int) -> Array:
	var events: Array = []
	for d in active.duplicate():
		if int(d["convoy"]) < 0 and now >= int(d["expires"]):
			active.erase(d)
			pending_respawn.append(now)
			events.append({"type": "expired", "hex": d["hex"]})
	for cv in convoys.duplicate():
		if now >= int(cv["back"]):
			convoys.erase(cv)
			var dep := _find(int(cv["deposit"]))
			if not dep.is_empty():
				active.erase(dep)
			pending_respawn.append(now + RESPAWN_MIN + rng.next_int(RESPAWN_MAX - RESPAWN_MIN))
			events.append({"type": "convoy_back", "res": cv["res"], "amount": cv["amount"], "hex": cv["hex"]})
	# fill the quota: missing deposits respawn when their timer is due (initially all at once)
	var due := maxi(0, quota(world) - active.size() - pending_respawn.size())
	for t in pending_respawn.duplicate():
		if now >= int(t):
			pending_respawn.erase(t)
			due += 1
	for i in due:
		var d := _spawn(world, gross_per_hour, now)
		if not d.is_empty():
			events.append({"type": "spawned", "hex": d["hex"]})
	return events


func at(hex: int) -> Dictionary:
	for d in active:
		if int(d["hex"]) == hex:
			return d
	return {}


func free_convoys(dev_level: int) -> int:
	return CONVOYS[clampi(dev_level, 0, 10)] - convoys.size()


## A deposit can be gathered when it is free, on passable land the player controls or on wild land,
## and the player has a free convoy (canon §5.2: AI deposits only through occupied hexes in war).
func can_send(world: World, hex: int, dev_level: int) -> String:
	var d := at(hex)
	if d.is_empty():
		return "err.no_deposit"
	if int(d["convoy"]) >= 0:
		return "err.convoy_en_route"
	var c: Dictionary = world.cells[hex]
	if c["controller"] != Types.PLAYER and c["controller"] != Types.NOBODY:
		return "err.foreign_land"
	if free_convoys(dev_level) <= 0:
		return "err.convoys_busy"
	return ""


func send(world: World, hex: int, dev_level: int, now: int, fast := false) -> bool:
	if can_send(world, hex, dev_level) != "":
		return false
	var d := at(hex)
	var travel := travel_seconds(world, hex)
	var gather: int = d["gather_sec"]
	if fast:  # FTUE: the first convoy goes 15 s and gathers 30 s (canon §14.3)
		travel = 15
		gather = 30
	var cv := {"id": next_id, "deposit": d["id"], "hex": hex, "res": d["res"], "amount": d["amount"],
		"depart": now, "arrive": now + travel, "gathered": now + travel + gather, "back": now + 2 * travel + gather}
	next_id += 1
	convoys.append(cv)
	d["convoy"] = cv["id"]
	return true


## Seconds from the capital to the hex: 10 s per step over own land, 20 s otherwise (straight line).
func travel_seconds(world: World, hex: int) -> int:
	var cap: int = world.states[Types.PLAYER]["capital_id"]
	var a := Vector2i(world.cells[cap]["q"], world.cells[cap]["r"])
	var b := Vector2i(world.cells[hex]["q"], world.cells[hex]["r"])
	var dist: int = HexGrid.distance(a, b)
	var own: bool = world.cells[hex]["owner"] == Types.PLAYER
	return maxi(STEP_OWN, dist * (STEP_OWN if own else STEP_OTHER))


func convoy_for(hex: int) -> Dictionary:
	for cv in convoys:
		if int(cv["hex"]) == hex:
			return cv
	return {}


## Convoy state for the view: {phase: "out"|"gather"|"back", progress 0..1 within the phase, left seconds}.
static func convoy_phase(cv: Dictionary, now: int) -> Dictionary:
	if now < int(cv["arrive"]):
		return {"phase": "out", "progress": _frac(now, cv["depart"], cv["arrive"]), "left": int(cv["back"]) - now}
	if now < int(cv["gathered"]):
		return {"phase": "gather", "progress": _frac(now, cv["arrive"], cv["gathered"]), "left": int(cv["back"]) - now}
	return {"phase": "back", "progress": _frac(now, cv["gathered"], cv["back"]), "left": int(cv["back"]) - now}


static func _frac(now: int, a: int, b: int) -> float:
	return clampf(float(now - a) / maxf(1.0, float(b - a)), 0.0, 1.0)


## Places a deposit (FTUE / tests): explicit hex, resource and size.
func spawn_at(world: World, hex: int, res: String, size: String, gross_per_hour: Dictionary, now: int) -> Dictionary:
	var d := {"id": next_id, "hex": hex, "res": res, "size": size, "amount": _amount(res, size, gross_per_hour),
		"gather_sec": SIZE_GATHER[size], "expires": now + LIFETIME, "convoy": -1}
	next_id += 1
	active.append(d)
	return d


func _amount(res: String, size: String, gross_per_hour: Dictionary) -> int:
	var ph: int = maxi(30, int(gross_per_hour.get(res, 0)))
	return maxi(20, int(round(ph * float(SIZE_HOURS[size]))))


## 40% on own land, 40% on wild land, 20% on AI land (canon §5.2). Deposit hexes carry no forts and
## are never capitals; one deposit per hex.
func _spawn(world: World, gross_per_hour: Dictionary, now: int) -> Dictionary:
	var roll := rng.next_int(100)
	var want := "own" if roll < 40 else ("wild" if roll < 80 else "ai")
	var cands: Array = []
	for c in world.cells:
		if not Types.is_passable(c) or c["kind"] == "capital" or int(c["fort"]) > 0 or not at(c["id"]).is_empty():
			continue
		var kind := "own" if c["owner"] == Types.PLAYER else ("wild" if c["owner"] == Types.NOBODY else "ai")
		if kind == want:
			cands.append(c["id"])
	if cands.is_empty() and want == "wild":
		for c in world.cells:  # no wild land left: the neutral share goes to own hexes
			if Types.is_passable(c) and c["owner"] == Types.PLAYER and c["kind"] != "capital" and int(c["fort"]) == 0 and at(c["id"]).is_empty():
				cands.append(c["id"])
	if cands.is_empty():
		return {}
	var hex: int = cands[rng.next_int(cands.size())]
	var res: String = RES_KINDS[rng.next_int(RES_KINDS.size())]
	var sroll := rng.next_int(100)
	var size := "S" if sroll < 50 else ("M" if sroll < 85 else "L")
	return spawn_at(world, hex, res, size, gross_per_hour, now)


func _find(id: int) -> Dictionary:
	for d in active:
		if int(d["id"]) == id:
			return d
	return {}


func to_dict() -> Dictionary:
	return {"rng": [rng.s0, rng.s1, rng.s2, rng.s3], "active": active, "convoys": convoys, "pending": pending_respawn, "next_id": next_id}


static func from_dict(d: Dictionary, seed_value: int = 1):
	var x = load("res://scripts/sim/deposits.gd").new(seed_value)
	var st: Array = d.get("rng", [])
	if st.size() == 4:
		x.rng.s0 = int(st[0])
		x.rng.s1 = int(st[1])
		x.rng.s2 = int(st[2])
		x.rng.s3 = int(st[3])
	for a in d.get("active", []):
		x.active.append({"id": int(a["id"]), "hex": int(a["hex"]), "res": String(a["res"]), "size": String(a["size"]),
			"amount": int(a["amount"]), "gather_sec": int(a["gather_sec"]), "expires": int(a["expires"]), "convoy": int(a["convoy"])})
	for c in d.get("convoys", []):
		var cv := {}
		for k in c:
			cv[k] = String(c[k]) if k == "res" else int(c[k])
		x.convoys.append(cv)
	for t in d.get("pending", []):
		x.pending_respawn.append(int(t))
	x.next_id = int(d.get("next_id", 1))
	return x
