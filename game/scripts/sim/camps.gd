extends RefCounted
## Marauder camps (canon §5.1, 02 §13, 03 §5.7, 05 §16): objects on wild hexes. A 60 s fight against the
## raiders destroys the camp and pays 1 h of gross income of the resource shown over the tents (≤3 rewards a
## day, reset at 04:00). A camp blocks colonization of its hex. Respawn 4 h after a defeat; at most
## clamp(round(wild hexes / 5), 2, 4) camps in a chapter ring and ≤6 on the map. Deterministic.

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")
const Rng := preload("res://scripts/sim/rng.gd")
const HexGrid := preload("res://scripts/sim/hexgrid.gd")

const RESPAWN_SEC := 4 * 3600
const MAX_ACTIVE := 6
const REWARDS_PER_DAY := 3
const DAY := 86400
const REFRESH_SEC := 4 * 3600  # 04:00
const MIN_CAMP_DIST := 3
const MIN_CAPITAL_DIST := 2
const TERRAINS: Array[String] = ["plain", "forest", "hills"]
const RES: Array[String] = ["gold", "food", "metal"]
const MIN_REWARD := 50
const FIGHT_TICKS := 600  # 60 s

var active: Array = []    # [{hex, res}]
var respawn: Array = []   # [due unix time] one per defeated camp
var reward_day := -1
var rewards := 0          # rewards paid on reward_day
var beaten_today := 0     # camps beaten on reward_day (raises the next garrison, 03 §5.7)
var rng


func _init(seed: int = 1) -> void:
	rng = Rng.new(seed)


static func target(world: World) -> int:
	var wild := 0
	for c in world.cells:
		if c["owner"] == Types.NOBODY and Types.is_passable(c):
			wild += 1
	if wild == 0:
		return 0
	return clampi(roundi(wild / 5.0), 2, 4)


func at(hex: int) -> Dictionary:
	for c in active:
		if int(c["hex"]) == hex:
			return c
	return {}


func blocked_hexes() -> Dictionary:
	var out := {}
	for c in active:
		out[int(c["hex"])] = true
	return out


static func _dist(world: World, a: int, b: int) -> int:
	var ca: Dictionary = world.cells[a]
	var cb: Dictionary = world.cells[b]
	return HexGrid.distance(Vector2i(int(ca["q"]), int(ca["r"])), Vector2i(int(cb["q"]), int(cb["r"])))


## Wild hexes a camp may stand on now (`taken`: hexes with deposits or a colonization in progress).
func _candidates(world: World, taken: Dictionary) -> Array:
	var caps: Array = []
	for st in world.states:
		if int(st["capital_id"]) >= 0:
			caps.append(int(st["capital_id"]))
	var out: Array = []
	for c in world.cells:
		var id: int = c["id"]
		if c["owner"] != Types.NOBODY or c["controller"] != Types.NOBODY or not Types.is_passable(c):
			continue
		if not TERRAINS.has(String(c["terrain"])) or String(c["kind"]) != "plain" or taken.has(id):
			continue
		var ok := true
		for cap in caps:
			if _dist(world, id, cap) < MIN_CAPITAL_DIST:
				ok = false
				break
		for cm in active:
			if ok and _dist(world, id, int(cm["hex"])) < MIN_CAMP_DIST:
				ok = false
		if ok:
			out.append(id)
	return out


## Fills free camp slots (first call at the start of a chapter) and spawns respawns that are due.
## Returns the hexes of new camps.
func tick(world: World, taken: Dictionary, now: int) -> Array:
	var spawned: Array = []
	# a camp whose hex stopped being wild (colonized, annexed) disappears
	var keep: Array = []
	for cm in active:
		var c: Dictionary = world.cells[int(cm["hex"])]
		if c["owner"] == Types.NOBODY and c["controller"] == Types.NOBODY:
			keep.append(cm)
	active = keep
	var goal := mini(target(world), MAX_ACTIVE)
	var due := 0
	var later: Array = []
	for t in respawn:
		if int(t) <= now:
			due += 1
		else:
			later.append(t)
	# initial fill: nothing active, nothing pending -> the ring gets its camps at once
	var free := goal - active.size() - later.size()
	var want := mini(free, due) if not respawn.is_empty() else free
	respawn = later
	for i in maxi(0, want):
		var cands := _candidates(world, taken)
		if cands.is_empty():
			respawn.append(now + RESPAWN_SEC)  # no room: try again later
			continue
		var weights: Array = []
		var total := 0
		for id in cands:
			var w := 1
			for n in world.neighbors[id]:
				if n >= 0 and world.cells[n]["owner"] == Types.PLAYER:
					w = 3  # next to the player: can be attacked right away
					break
			weights.append(w)
			total += w
		var roll: int = rng.next_int(total)
		var pick: int = cands[0]
		for k in cands.size():
			roll -= int(weights[k])
			if roll < 0:
				pick = cands[k]
				break
		var res: String = RES[rng.next_int(RES.size())]
		active.append({"hex": pick, "res": res})
		spawned.append(pick)
	return spawned


## Can the player attack this camp now (it borders a hex the player controls)?
static func attackable(world: World, hex: int) -> bool:
	for n in world.neighbors[hex]:
		if n >= 0 and world.cells[n]["controller"] == Types.PLAYER:
			return true
	return false


## Raider strength (03 §5.7): 0.6 × average max Strength of the player's armies × (1 + 0.2 × camps beaten today).
func garrison(avg_max_str: int, now: int) -> int:
	_roll_day(now)
	return avg_max_str * 6 * (10 + 2 * mini(beaten_today, 2)) / 100


## Fort level of the camp in the fight: min(DL, 2).
static func fort_level(dl: int) -> int:
	return mini(dl, 2)


## The camp is destroyed (the hex is wild again and can be colonized). Returns {res, amount} — amount 0 once
## the daily reward cap is spent. `gross` = gross income per hour of the player.
func defeat(hex: int, gross: Dictionary, now: int) -> Dictionary:
	var cm := at(hex)
	if cm.is_empty():
		return {}
	active.erase(cm)
	respawn.append(now + RESPAWN_SEC)
	_roll_day(now)
	beaten_today += 1
	var r: String = cm["res"]
	if rewards >= REWARDS_PER_DAY:
		return {"res": r, "amount": 0}
	rewards += 1
	return {"res": r, "amount": maxi(MIN_REWARD, int(gross.get(r, 0)))}


func rewards_left(now: int) -> int:
	_roll_day(now)
	return REWARDS_PER_DAY - rewards


func _roll_day(now: int) -> void:
	var d := int(floor(float(now - REFRESH_SEC) / DAY))
	if d != reward_day:
		reward_day = d
		rewards = 0
		beaten_today = 0


func to_dict() -> Dictionary:
	return {"active": active.duplicate(true), "respawn": respawn.duplicate(), "reward_day": reward_day,
		"rewards": rewards, "beaten": beaten_today, "rng": [rng.s0, rng.s1, rng.s2, rng.s3]}


func load_dict(d: Dictionary) -> void:
	active = []
	for c in d.get("active", []):
		if typeof(c) == TYPE_DICTIONARY:
			active.append({"hex": int(c.get("hex", -1)), "res": String(c.get("res", "gold"))})
	respawn = []
	for t in d.get("respawn", []):
		respawn.append(int(t))
	reward_day = int(d.get("reward_day", -1))
	rewards = int(d.get("rewards", 0))
	beaten_today = int(d.get("beaten", 0))
	var st: Array = d.get("rng", [])
	if st.size() == 4:
		rng.s0 = int(st[0])
		rng.s1 = int(st[1])
		rng.s2 = int(st[2])
		rng.s3 = int(st[3])
