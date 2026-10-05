extends RefCounted
## Рынок (05 §13, canon §7): resource exchange at 3:1 (level 1) down to 2:1 (level 20) and the daily trader —
## 3 «resource for resource» lots at better rates, one purchase each per day, refreshed at 04:00 (server time).
## Raivites, medals and items never take part. Works in war and with an empty treasury.
## Deterministic: integer maths, the trader is seeded by the day number.

const Economy := preload("res://scripts/sim/economy.gd")
const World := preload("res://scripts/sim/world.gd")

const DAY := 86400
const REFRESH_SEC := 4 * 3600  # 04:00
## Trader lots (05 §13.3): rate «give : get» in thousandths, volume in hours of gross income of the received resource.
const LOTS := [
	{"key": "trader.needed", "rate": 1500, "hours": 2},
	{"key": "trader.common", "rate": 1500, "hours": 2},
	{"key": "trader.generous", "rate": 1250, "hours": 1},
]
const GENEROUS_EVEN_PCT := 25  # chance that the generous lot is 1:1
const MIN_LOT := 50

var day: int = -1          # trader day the lots were rolled for
var lots: Array = []       # [{give, get, give_amt, get_amt, rate, key, bought}]


## Exchange rate «give : get» in thousandths: 3 − (L − 1) / 19 (05 §13.1).
static func rate_milli(level: int) -> int:
	var l := clampi(level, 1, 20)
	return 3000 - (l - 1) * 1000 / 19


static func market_level(econ: Economy) -> int:
	return econ._type_level("market")


## What `give_amt` of `give` buys right now: received = floor(given / rate), cut to the free warehouse space
## (the input is trimmed so nothing burns). Returns {give, get, cap_hit} or {} when not possible.
static func quote(econ: Economy, give: String, get_res: String, give_amt: int) -> Dictionary:
	if give == get_res or not Economy.RES.has(give) or not Economy.RES.has(get_res):
		return {}
	var lvl := market_level(econ)
	if lvl <= 0:
		return {}
	var rate := rate_milli(lvl)
	var g := clampi(give_amt, 0, int(econ.res.get(give, 0)))
	var out := g * 1000 / rate
	var free := maxi(0, int(econ.storage_cap()[get_res]) - int(econ.res.get(get_res, 0)))
	var cap_hit := false
	if out > free:
		out = free
		g = (out * rate + 999) / 1000  # smallest input that still yields `out`
		cap_hit = true
	return {"give": g, "get": out, "cap_hit": cap_hit, "rate": rate}


## Performs the exchange. Returns the quote applied, or {} (nothing changes) when it would yield nothing.
static func exchange(econ: Economy, give: String, get_res: String, give_amt: int) -> Dictionary:
	var q := quote(econ, give, get_res, give_amt)
	if q.is_empty() or int(q["get"]) <= 0:
		return {}
	econ.res[give] = int(econ.res[give]) - int(q["give"])
	econ.res[get_res] = int(econ.res[get_res]) + int(q["get"])
	return q


static func trader_day(now: int) -> int:
	return int(floor(float(now - REFRESH_SEC) / DAY))


static func refresh_left(now: int) -> int:
	return (trader_day(now) + 1) * DAY + REFRESH_SEC - now


## Rolls the day's lots when the day changed. Lot 1 «Нужное» buys the resource the warehouse is emptiest of,
## paid with the fullest; lots 2–3 are random pairs not repeating any earlier pair of the day.
func refresh(econ: Economy, world: World, now: int) -> void:
	var d := trader_day(now)
	if d == day and lots.size() == LOTS.size():
		return
	day = d
	lots = []
	var rng := RandomNumberGenerator.new()
	rng.seed = hash("trader:%d" % d)
	var cap := econ.storage_cap()
	var gross := econ.gross_per_hour(world)
	var order: Array = Economy.RES.duplicate()
	order.sort_custom(func(a, b):
		var fa := float(econ.res.get(a, 0)) / maxf(1.0, float(cap[a]))
		var fb := float(econ.res.get(b, 0)) / maxf(1.0, float(cap[b]))
		return fa < fb if fa != fb else String(a) < String(b))
	var pairs: Array = [[order[order.size() - 1], order[0]]]  # [give, get]
	var all_pairs: Array = []
	for a in Economy.RES:
		for b in Economy.RES:
			if a != b:
				all_pairs.append([a, b])
	for i in range(1, LOTS.size()):
		var free_pairs: Array = all_pairs.filter(func(p): return not pairs.has(p))
		pairs.append(free_pairs[rng.randi_range(0, free_pairs.size() - 1)])
	for i in LOTS.size():
		var spec: Dictionary = LOTS[i]
		var rate: int = spec["rate"]
		if i == 2 and rng.randi_range(1, 100) <= GENEROUS_EVEN_PCT:
			rate = 1000
		var give: String = pairs[i][0]
		var get_res: String = pairs[i][1]
		var get_amt := maxi(MIN_LOT, int(gross.get(get_res, 0)) * int(spec["hours"]))
		lots.append({"key": spec["key"], "give": give, "get": get_res, "rate": rate,
			"get_amt": get_amt, "give_amt": (get_amt * rate + 999) / 1000, "bought": false})


## "" when lot `i` can be bought now, else a reason key.
func can_buy(econ: Economy, i: int) -> String:
	if i < 0 or i >= lots.size():
		return "market.no_lot"
	var lot: Dictionary = lots[i]
	if lot["bought"]:
		return "market.bought"
	if market_level(econ) <= 0:
		return "market.locked"
	if int(econ.res.get(lot["give"], 0)) < int(lot["give_amt"]):
		return "market.not_enough"
	if int(econ.res.get(lot["get"], 0)) + int(lot["get_amt"]) > int(econ.storage_cap()[lot["get"]]):
		return "market.no_space"
	return ""


func buy(econ: Economy, i: int) -> bool:
	if can_buy(econ, i) != "":
		return false
	var lot: Dictionary = lots[i]
	econ.res[lot["give"]] = int(econ.res[lot["give"]]) - int(lot["give_amt"])
	econ.res[lot["get"]] = int(econ.res[lot["get"]]) + int(lot["get_amt"])
	lot["bought"] = true
	return true


func to_dict() -> Dictionary:
	return {"day": day, "lots": lots.duplicate(true)}


func load_dict(d: Dictionary) -> void:
	day = int(d.get("day", -1))
	lots = []
	for l in d.get("lots", []):
		if typeof(l) == TYPE_DICTIONARY:
			var lot: Dictionary = l
			lots.append({"key": String(lot.get("key", "")), "give": String(lot.get("give", "gold")), "get": String(lot.get("get", "food")),
				"rate": int(lot.get("rate", 1500)), "give_amt": int(lot.get("give_amt", 0)), "get_amt": int(lot.get("get_amt", 0)),
				"bought": bool(lot.get("bought", false))})
