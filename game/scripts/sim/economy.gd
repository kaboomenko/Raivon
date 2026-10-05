extends RefCounted
## Deterministic economy of one player state (canon 00_canon.md §4, §5, §6.2, §7, §13; numbers from
## 05_economy_buildings.md and 11_balance_numbers.md — canon wins on conflict).
##
## Time is integer unix seconds passed in by the caller; the clock is never read here.
## All rates are integer "milli-units per hour"; accrual is exact integer math in sub-units
## (SUB = 3 600 000 sub-units = 1 resource unit, i.e. milli-unit × second / hour), so splitting the
## same time span into more ticks gives the same result.
##
## Building (Dictionary): {id:int, type:String, hex:int, level:int, upgrade_end:int (0 = idle)}
##   - capital buildings (Резиденция, Казарма, …) stand on the capital hex;
##   - hex-type buildings (Кварталы, Ферма, Шахта, Порт, Военная база) have ONE level for the whole
##     state (canon §7) and are stored once with hex = -1; building_at(hex) maps a hex to them by kind;
##   - fort / tower are per hex (canon §7) and also carry "paid": Dictionary (sum actually paid, for the
##     100% refund when the hex is ceded by treaty, canon §7 / решение 20).
##
## Usage: call tick(world, now) before collect()/collect_all()/start_upgrade(); the collect time is
## last_tick. Methods without a world argument use a cache of the player's hexes refreshed by every
## call that receives a world (_init, tick, income_per_hour, can_build, start_build).
##
## Not modelled yet (chapter I does not need them): oil (HUD from DL5, canon §4), Нефтевышка / Завод
## (DL5), research multipliers and «Бережливость» (§12.3), army food upkeep (armies module, §8.1),
## ruin / war fatigue / repair (§9.14), mothballing (§3.4), subscription autocollect, raivite veins.

const Types := preload("res://scripts/sim/types.gd")
const World := preload("res://scripts/sim/world.gd")
const _Self := preload("res://scripts/sim/economy.gd")

## Stored resources (canon §4). Oil exists only from DL5 (outside chapter I, max DL3) — not tracked yet.
const RES := ["gold", "food", "metal"]
## Hard currency key (canon §4: no cap, never plundered).
const RAIVITE := "raivite"
## Translation keys of resource names in refusal reasons (genitive in Russian: «Не хватает золота»).
const RES_NAMES := {"gold": "res.gen.gold", "food": "res.gen.food", "metal": "res.gen.metal", "oil": "res.gen.oil", "raivite": "res.gen.raivite"}

const HOUR := 3600
const SUB := 3600000                 # sub-units per resource unit (milli × s / h)
const POOL_HOURS := 8                # canon §4, §13: income accumulates in hexes up to 8 h; E7 pause after 8 h
const FREE_FINISH_SEC := 300         # canon §13.1: ≤5 min left — finish for free

## Starting stock: 05 §20.1 (accepted in 11 §6). Raivites: canon is silent — DEFAULT 50 (invented).
const START_RES := {"gold": 1000, "food": 600, "metal": 600, "raivite": 50}
const START_BUILDERS := 2            # canon §7 «Строители: 2 на старте»
## Chapter DL cap: DL ≤ 3/5/7/8/9/10 in chapters I–VI (canon §6.2).
const CHAPTER_DL_CAP: Array[int] = [0, 3, 5, 7, 8, 9, 10]

## М_произв and М_апкип ×100, index = DL (canon §6.2).
const PROD_MULT100: Array[int] = [100, 100, 150, 220, 320, 460, 650, 900, 1250, 1600, 2000]
const UPKEEP_MULT100: Array[int] = [100, 100, 170, 280, 450, 700, 1100, 1700, 2700, 4300, 7000]

## Hex production at DL1, building level 1, units/h (canon §5.1). "lvl" = building type whose level
## multiplies the output by (1 + 0,08 × (ур − 1)); "" = no level multiplier (plain hexes, capital).
const HEX_PRODUCTION := {
	"plain": {"res": {"gold": 4}, "lvl": ""},
	"farm": {"res": {"food": 30}, "lvl": "farm"},
	"mine": {"res": {"metal": 30}, "lvl": "mine"},
	"city": {"res": {"gold": 40}, "lvl": "quarters"},
	"port": {"res": {"gold": 20}, "lvl": "port"},
	"capital": {"res": {"gold": 150, "food": 30, "metal": 30}, "lvl": ""},
	"military_base": {"res": {}, "lvl": "military_base"},   # no income (canon §5.1)
}

## Building catalogue (canon §7; C_B — 05 §8.4 / 11 §7.3, author's proposal adopted by 11).
## class: "capital" (on the capital hex, one per state), "hex_type" (one level per state, on every hex
## of `kind`), "defense" (per hex). upkeep = base gold/h (canon §7). unlock_dl = DL that grants it free.
const BUILDINGS := {
	"residence": {"name": "bld.residence", "class": "capital", "cb": 0, "upkeep": 0, "unlock_dl": 1},
	"barracks": {"name": "bld.barracks", "class": "capital", "cb": 180, "upkeep": 2, "unlock_dl": 1},
	"academy": {"name": "bld.academy", "class": "capital", "cb": 220, "upkeep": 2, "unlock_dl": 1},
	"warehouse": {"name": "bld.warehouse", "class": "capital", "cb": 160, "upkeep": 1, "unlock_dl": 1},
	"infirmary": {"name": "bld.infirmary", "class": "capital", "cb": 160, "upkeep": 2, "unlock_dl": 1},
	"convoy_yard": {"name": "bld.convoy_yard", "class": "capital", "cb": 140, "upkeep": 1, "unlock_dl": 1},
	"market": {"name": "bld.market", "class": "capital", "cb": 140, "upkeep": 1, "unlock_dl": 2},
	"embassy": {"name": "bld.embassy", "class": "capital", "cb": 200, "upkeep": 2, "unlock_dl": 3},
	"quarters": {"name": "bld.quarters", "class": "hex_type", "kind": "city", "cb": 260, "upkeep": 3, "unlock_dl": 1},
	"farm": {"name": "bld.farm", "class": "hex_type", "kind": "farm", "cb": 200, "upkeep": 2, "unlock_dl": 1},
	"mine": {"name": "bld.mine", "class": "hex_type", "kind": "mine", "cb": 200, "upkeep": 2, "unlock_dl": 1},
	"port": {"name": "bld.port", "class": "hex_type", "kind": "port", "cb": 180, "upkeep": 2, "unlock_dl": 1},
	"military_base": {"name": "bld.military_base", "class": "hex_type", "kind": "military_base", "cb": 260, "upkeep": 5, "unlock_dl": 1},
	"fort": {"name": "bld.fort", "class": "defense", "cb": 0, "upkeep": 5, "unlock_dl": 1},
	"tower": {"name": "bld.tower", "class": "defense", "cb": 0, "upkeep": 3, "unlock_dl": 1},
}
## Order in which capital / hex-type buildings appear (05 §8.7: start set; Рынок at DL2, Посольство at DL3).
const BUILDING_ORDER: Array[String] = ["residence", "barracks", "academy", "warehouse", "infirmary",
	"convoy_yard", "market", "embassy", "quarters", "farm", "mine", "port", "military_base"]
## Types the player places on a hex with start_build (canon §7: only fort and tower are built per hex;
## everything else appears automatically).
const BUILDABLE: Array[String] = ["fort", "tower"]
const NO_HEX_REASON := {
	"quarters": "err.no_city", "farm": "err.no_farm", "mine": "err.no_mine",
	"port": "err.no_port", "military_base": "err.no_military_base",
}
## «Казна пуста» forbids starting these (canon §7).
const TREASURY_LOCKED: Array[String] = ["residence", "barracks", "academy", "infirmary", "embassy",
	"military_base", "fort", "tower"]

## 1,22^k × 10⁹ for k = 0..19 — building price growth (05 §8.4, 11 §7.1).
const GROWTH_122_E9: Array[int] = [1000000000, 1220000000, 1488400000, 1815848000, 2215334560,
	2702708163, 3297303959, 4022710830, 4907707213, 5987402800, 7304631415, 8911650327,
	10872213399, 13264100346, 16182202423, 19742286956, 24085590086, 29384419905, 35848992284,
	43735770586]
## Building timer to reach level L (index = L), seconds (05 §8.5 / §22, within canon §13 ranges).
const BUILD_SECONDS: Array[int] = [0, 0, 5, 30, 120, 300, 900, 1200, 2700, 5400, 9000, 10800, 14400,
	18000, 28800, 43200, 57600, 64800, 86400, 108000, 129600]
## Fort / tower timer to reach level L (05 §8.5).
const DEFENSE_SECONDS: Array[int] = [0, 10, 60, 600, 1200, 3600, 7200, 14400, 28800, 43200, 57600]
## Fort / tower price per level: base × М_произв(ур) × 1,5^(ур−1) (05 §9.17–9.18, 11 §8.1).
const DEFENSE_COST_BASE := {
	"fort": {"metal": 100, "gold": 50, "oil": 10},   # oil only from level 8
	"tower": {"metal": 80, "gold": 60},
}

## Residence = DL transition, index = target DL (canon §6.2 hexes and timers; 11 §6.2 prices).
const RESIDENCE_HEXES: Array[int] = [0, 0, 10, 16, 24, 32, 44, 56, 80, 120, 170]
const RESIDENCE_SECONDS: Array[int] = [0, 0, 60, 900, 3600, 10800, 28800, 43200, 86400, 129600, 172800]
const RESIDENCE_COST := [
	{}, {},
	{"gold": 300, "metal": 100}, {"gold": 1500, "metal": 650}, {"gold": 5600, "metal": 3700},
	{"gold": 12000, "metal": 8000}, {"gold": 23000, "metal": 16000, "oil": 7000},
	{"gold": 46000, "metal": 32000, "oil": 14000}, {"gold": 90000, "metal": 63000, "oil": 27000},
	{"gold": 172000, "metal": 134000, "oil": 76000}, {"gold": 324000, "metal": 252000, "oil": 144000},
]

## Склад: 5 000 × 1,35^(ур−1) per resource, rounded (canon §4, §7; table 05 §6.1).
const STORAGE_CAP: Array[int] = [0, 5000, 6750, 9113, 12302, 16608, 22420, 30267, 40861, 55162, 74469,
	100533, 135719, 183221, 247348, 333920, 450792, 608570, 821569, 1109118, 1497310]
## Speed-up price anchors [minutes, raivites], linear in between, rounded up (canon §13.1).
const SPEEDUP_POINTS := [[1, 1], [10, 6], [60, 20], [180, 50], [480, 100], [1440, 240], [2880, 420]]

var res: Dictionary = {}
var buildings: Array = []
var builders: int = START_BUILDERS
var last_tick: int = 0
## hex id -> {res: whole units} of uncollected income (only keys > 0; hexes with nothing are absent).
var stock: Dictionary = {}
## Start of the 8 h economy window (canon §4 E7): income and upkeep stop 8 h after the last collect.
var last_collect: int = 0
var chapter: int = 1
var capital_hex: int = -1
var next_id: int = 1
## Research levels that change the economy (canon §12.3, set by research.gd): gold/food/metal +2% output
## per level, "cellars" +2 pp protected share per level, "thrift" −3% upkeep per level.
var research := {"gold": 0, "food": 0, "metal": 0, "cellars": 0, "thrift": 0}

## hex id -> {res: sub-unit remainder < SUB} — fractional part of stock.
var _stock_rem: Dictionary = {}
var _upkeep_rem: int = 0
## Army food upkeep, thousandths of food per hour (04 §6.1); set by the game from its armies before tick().
var army_food_milli: int = 0
var _food_rem: int = 0
## Разорение after a plundered defeat (canon §9.14): −ruin_pct% production on own hexes until ruin_until.
var ruin_pct: int = 0
var ruin_until: int = 0
## Damaged hex buildings (canon §9.14): hex id -> repair end (0 = waiting for repair); −50% output until repaired.
var damaged: Dictionary = {}
const REPAIR_SEC := 600
const REPAIR_PCT := 5
const DAMAGE_KINDS: Array[String] = ["city", "farm", "mine", "port"]
var _rate_t: int = -1  # time the temporary modifiers are evaluated at (inside _accrue), else last_tick
var _events: Array = []
## Cache of the player's land, refreshed whenever a world is passed in.
var _synced: bool = false
var _own_kinds: Dictionary = {}      # official hex id -> kind
var _own_ctrl: Dictionary = {}       # official hex id -> controlled by the player
var _gold_net_milli: int = 0


func _init(world: World = null, now: int = 0) -> void:
	res = START_RES.duplicate()
	last_tick = now
	last_collect = now
	for t in BUILDING_ORDER:
		if int(BUILDINGS[t]["unlock_dl"]) <= 1:
			_add_building(t, -1, 1)
	if world == null:
		return
	capital_hex = int(world.states[Types.PLAYER]["capital_id"])
	for b in buildings:
		if BUILDINGS[b["type"]]["class"] == "capital":
			b["hex"] = capital_hex
	# Forts already standing on player land become fort buildings (paid unknown -> 0).
	for c in world.cells:
		var f: int = c["fort"]
		if f > 0 and c["owner"] == Types.PLAYER:
			var fb := _add_building("fort", int(c["id"]), f)
			fb["paid"] = {}
	_sync(world)


# ---------------------------------------------------------------- queries

func dev_level() -> int:
	var r := _find_type("residence")
	return 1 if r.is_empty() else int(r["level"])


func storage_cap() -> Dictionary:
	var lvl := _type_level("warehouse")
	var cap: int = STORAGE_CAP[clampi(lvl, 1, STORAGE_CAP.size() - 1)]
	var out := {}
	for r in RES:
		out[r] = cap
	return out


## Protected share of the warehouse, percent (canon §7: ур. 1–4 40%, 5–9 45%, 10–14 50%, 15–19 55%, 20 60%).
func protected_percent() -> int:
	return _warehouse_protected() + 2 * int(research.get("cellars", 0))


func _warehouse_protected() -> int:
	var lvl := _type_level("warehouse")
	if lvl >= 20:
		return 60
	if lvl >= 15:
		return 55
	if lvl >= 10:
		return 50
	if lvl >= 5:
		return 45
	return 40


## Net income per hour (whole units, truncated): hex production (own + 50% of occupied enemy hexes)
## minus gold upkeep of buildings, forts and towers (canon §5.1, §7).
func income_per_hour(world: World) -> Dictionary:
	_sync(world)
	var gross := _rates_total(world)
	var up := _upkeep_milli()
	var out := {}
	for r in RES:
		var v: int = gross[r]
		if r == "gold":
			v -= up
		elif r == "food":
			v -= army_food_milli
		out[r] = v / 1000
	return out


## gross_rate (canon §4): official non-mothballed hexes, no temporary modifiers, whole units/h.
## Used for «часы производства» (deposits, 12 h loss cap, buy-out).
func gross_per_hour(world: World) -> Dictionary:
	var out := {}
	for r in RES:
		out[r] = 0
	for c in world.cells:
		if c["owner"] != Types.PLAYER or not Types.is_passable(c):
			continue
		var hr := _hex_rate_milli(c, false)
		for r in hr:
			out[r] = int(out[r]) + int(hr[r])
	for r in RES:
		out[r] = int(out[r]) / 1000
	return out


## Gold upkeep per hour (whole units, truncated) — buildings, forts, towers (canon §7).
func upkeep_per_hour() -> int:
	return _upkeep_milli() / 1000


## Production of one hex for the player, whole units/h (0 for hexes the player does not control).
func hex_income(world: World, hex: int) -> Dictionary:
	var out := {}
	var c: Dictionary = world.cells[hex]
	if c["controller"] != Types.PLAYER or not Types.is_passable(c):
		return out
	var hr := _hex_rate_milli(c, c["owner"] != Types.PLAYER)
	var m := _temp_mult100(hex, c["owner"] == Types.PLAYER)
	for r in hr:
		out[r] = int(hr[r]) * m / 100 / 1000
	return out


## Exact uncollected amount of a resource over all hexes (sums the fractional remainders too), whole
## units — what «Собрать всё» would bring with unlimited storage (up to the per-hex rounding).
func stock_total(r: String) -> int:
	var total := 0
	for h in stock:
		total += int(stock[h].get(r, 0)) * SUB
	for h in _stock_rem:
		total += int(_stock_rem[h].get(r, 0))
	return total / SUB


func building(id: int) -> Dictionary:
	for b in buildings:
		if b["id"] == id:
			return b
	return {}


## Main building on a hex: the hex-type building for its kind (farm hex -> Ферма), otherwise the first
## building standing on it (capital -> Резиденция, any hex -> its fort). {} when none.
func building_at(hex: int) -> Dictionary:
	var all := buildings_at(hex)
	return {} if all.is_empty() else all[0]


func buildings_at(hex: int) -> Array:
	var out: Array = []
	if _own_kinds.has(hex):
		var t := _hex_type_for_kind(String(_own_kinds[hex]))
		if t != "":
			out.append(_find_type(t))
	for b in buildings:
		if b["hex"] == hex and hex >= 0:
			out.append(b)
	return out


func busy_builders(now: int) -> int:
	var n := 0
	for b in buildings:
		if int(b["upgrade_end"]) > now:
			n += 1
	return n


## Maximum level the building may reach at the current DL (canon §7: 2 × УР; Резиденция = УР up to the
## chapter cap; fort / tower ≤ УР and ≤ 10).
func max_level(b: Dictionary) -> int:
	var t: String = b["type"]
	var dl := dev_level()
	if t == "residence":
		return mini(10, CHAPTER_DL_CAP[clampi(chapter, 1, CHAPTER_DL_CAP.size() - 1)])
	if BUILDINGS[t]["class"] == "defense":
		return mini(10, dl)
	return mini(20, 2 * dl)


## Price of the next level: resources (gold/food/metal, "oil" only when > 0) plus "seconds".
func upgrade_cost(b: Dictionary) -> Dictionary:
	return _level_cost(String(b["type"]), int(b["level"]) + 1)


## Price of building a fort / tower from scratch (level 1). {} for types that are not placed on hexes.
func build_cost(type: String) -> Dictionary:
	if not BUILDABLE.has(type):
		return {}
	return _level_cost(type, 1)


## "" when the upgrade can start, else a reason: a translation key, or "key|arg|…" (UI: l10n.gd `t()`).
func can_upgrade(b: Dictionary, now: int) -> String:
	if b.is_empty() or building(int(b["id"])).is_empty():
		return "err.no_building"
	_complete_due(now)
	if int(b["upgrade_end"]) != 0:
		return "err.upgrading"
	var t: String = b["type"]
	var lvl: int = b["level"]
	if t == "residence":
		if lvl >= 10:
			return "err.max_level"
		if lvl >= max_level(b):
			return "err.chapter_locked|%d" % (chapter + 1)
		if _synced and _own_kinds.size() < RESIDENCE_HEXES[lvl + 1]:
			return "err.need_hexes|%d" % RESIDENCE_HEXES[lvl + 1]
	else:
		var cls: String = BUILDINGS[t]["class"]
		var absolute := 10 if cls == "defense" else 20
		if lvl >= absolute:
			return "err.max_level"
		if lvl >= max_level(b):
			var need := lvl + 1 if cls == "defense" else (lvl + 2) / 2
			return "err.need_residence|%d" % need
		if cls == "hex_type" and _synced and _count_kind(String(BUILDINGS[t]["kind"])) == 0:
			return NO_HEX_REASON[t]
		if cls == "defense" and _synced and not bool(_own_ctrl.get(int(b["hex"]), false)):
			return "err.hex_occupied"
	return _can_pay_and_staff(t, upgrade_cost(b), now)


func can_build(world: World, type: String, hex: int, now: int) -> String:
	_sync(world)
	_complete_due(now)
	if not BUILDABLE.has(type):
		return "err.not_hex_building"
	if hex < 0 or hex >= world.cells.size():
		return "err.no_hex"
	var c: Dictionary = world.cells[hex]
	if not Types.is_passable(c):
		return "err.cant_build_here"
	if c["owner"] != Types.PLAYER:
		return "err.not_your_hex"
	if c["controller"] != Types.PLAYER:
		return "err.hex_occupied"
	for b in buildings:
		if b["hex"] == hex and b["type"] == type:
			return "err.fort_exists" if type == "fort" else "err.tower_exists"
	if type == "tower":
		if c["kind"] != "plain":
			return "err.tower_plain_only"
		var towers := 0
		for b in buildings:
			if b["type"] == "tower":
				towers += 1
		if towers >= 2 * dev_level():
			return "err.tower_limit|%d" % (2 * dev_level())
	return _can_pay_and_staff(type, build_cost(type), now)


## Raivites to finish the running upgrade now (canon §13.1); 0 when idle or within the free 5 min.
func speedup_cost(b: Dictionary, now: int) -> int:
	var end: int = b.get("upgrade_end", 0)
	if end == 0:
		return 0
	return speedup_price(end - now)


static func speedup_price(seconds_left: int) -> int:
	if seconds_left <= FREE_FINISH_SEC:
		return 0
	if seconds_left <= 60:
		return 1
	for i in range(1, SPEEDUP_POINTS.size()):
		var a: int = SPEEDUP_POINTS[i - 1][0]
		var pa: int = SPEEDUP_POINTS[i - 1][1]
		var bm: int = SPEEDUP_POINTS[i][0]
		var pb: int = SPEEDUP_POINTS[i][1]
		if seconds_left <= bm * 60:
			return pa + _ceil_div((pb - pa) * (seconds_left - a * 60), (bm - a) * 60)
	return int(SPEEDUP_POINTS[SPEEDUP_POINTS.size() - 1][1])


## «Казна пуста» (canon §3.4): gold 0 with a negative hourly balance.
func treasury_empty() -> bool:
	return int(res["gold"]) <= 0 and _gold_net_milli < 0


# ---------------------------------------------------------------- actions

func start_upgrade(id: int, now: int) -> bool:
	var b := building(id)
	if b.is_empty() or can_upgrade(b, now) != "":
		return false
	var cost := upgrade_cost(b)
	_pay(b, cost)
	b["upgrade_end"] = now + int(cost["seconds"])
	return true


func start_build(world: World, type: String, hex: int, now: int) -> bool:
	if can_build(world, type, hex, now) != "":
		return false
	var b := _add_building(type, hex, 0)
	b["paid"] = {}
	var cost := build_cost(type)
	_pay(b, cost)
	b["upgrade_end"] = now + int(cost["seconds"])
	return true


## Spends raivites (free inside the last 5 min) and completes the upgrade at once. The completion
## event is reported by the next tick().
func finish_now(id: int, now: int) -> bool:
	var b := building(id)
	if b.is_empty() or int(b["upgrade_end"]) == 0:
		return false
	var price := speedup_cost(b, now)
	if int(res.get(RAIVITE, 0)) < price:
		return false
	res[RAIVITE] = int(res.get(RAIVITE, 0)) - price
	_complete(b)
	return true


## Advances the economy to `now`: accrues hex income into `stock` (each hex capped at 8 h of its
## income), charges gold upkeep (pool first, then storage, never below 0), stops both 8 h after the
## last collect (canon §4 E7), completes finished upgrades in time order, syncs forts and DL into the
## world. Returns events: {type:"upgrade_done", building, building_type, level}, {type:"dev_level", level},
## {type:"building_unlocked", building, building_type}, {type:"fort_refund", building, hex, refund}.
func tick(world: World, now: int) -> Array:
	_sync(world)
	if now > last_tick:
		var t := last_tick
		while true:
			var next := now
			for b in buildings:
				var e: int = b["upgrade_end"]
				if e > t and e < next:
					next = e
			if ruin_until > t and ruin_until < next:
				next = ruin_until
			for h in damaged:
				var re: int = damaged[h]
				if re > t and re < next:
					next = re
			_rate_t = t
			_accrue(world, t, next)
			_rate_t = -1
			t = next
			_complete_due(t)
			_finish_repairs(t)
			if t >= now:
				break
		last_tick = now
	_complete_due(now)
	_finish_repairs(now)
	_sync_world(world)
	_sync(world)
	var out := _events
	_events = []
	return out


## Moves the hex's stock into storage up to the warehouse cap; the rest stays on the hex.
## Returns what was actually gained. Also restarts the 8 h economy window at last_tick.
func collect(hex: int) -> Dictionary:
	var gained := {}
	for r in RES:
		gained[r] = 0
	_collect_hex(hex, gained, storage_cap())
	last_collect = last_tick
	return gained


func collect_all() -> Dictionary:
	var gained := {}
	for r in RES:
		gained[r] = 0
	var cap := storage_cap()
	for h in _sorted_keys(stock):
		_collect_hex(h, gained, cap)
	last_collect = last_tick
	return gained


## Credits one-off income (loot, contribution, deposits): up to the warehouse cap, the excess burns
## (canon §4); over_cap = true for paid / gift sources that ignore the cap. Returns what was credited.
func add_resources(amounts: Dictionary, over_cap: bool = false) -> Dictionary:
	var cap := storage_cap()
	var out := {}
	for r in amounts:
		var v: int = amounts[r]
		if v <= 0:
			continue
		var cur: int = res.get(r, 0)
		var add := v
		if not over_cap and cap.has(r):
			add = mini(v, maxi(0, int(cap[r]) - cur))
		res[r] = cur + add
		out[r] = add
	return out


## Plunder / contribution on defeat (canon §9.14): takes `fraction` (0.3–0.6) of the uncollected stock
## and of the UNPROTECTED part of storage (protected = floor(min(stored, cap) × share), share 40–60% by
## Склад level, canon §7). Raivites are never taken. `loss_cap` (optional, per resource) is the 12 h
## gross_rate ceiling. Stock is taken first, then storage. Returns what was taken.
func plunder(fraction: float, loss_cap: Dictionary = {}) -> Dictionary:
	var pm := clampi(roundi(fraction * 1000.0), 0, 1000)
	var cap := storage_cap()
	var pct := protected_percent()
	var taken := {}
	for r in RES:
		var limit: int = loss_cap.get(r, -1)
		var got := 0
		for h in _sorted_keys(stock):
			var s: Dictionary = stock[h]
			var have: int = s.get(r, 0)
			var take := have * pm / 1000
			if limit >= 0:
				take = mini(take, limit - got)
			if take > 0:
				s[r] = have - take
				got += take
		var stored: int = res.get(r, 0)
		var protected_amt := mini(stored, int(cap[r])) * pct / 100
		var take_s := (stored - protected_amt) * pm / 1000
		if limit >= 0:
			take_s = mini(take_s, limit - got)
		if take_s > 0:
			res[r] = stored - take_s
			got += take_s
		taken[r] = got
	_prune_stock()
	return taken


# ---------------------------------------------------------------- save / load

func to_dict() -> Dictionary:
	return {
		"res": res.duplicate(),
		"buildings": buildings.duplicate(true),
		"builders": builders,
		"last_tick": last_tick,
		"last_collect": last_collect,
		"stock": stock.duplicate(true),
		"stock_rem": _stock_rem.duplicate(true),
		"upkeep_rem": _upkeep_rem,
		"food_rem": _food_rem,
		"ruin_pct": ruin_pct,
		"ruin_until": ruin_until,
		"damaged": damaged.duplicate(),
		"army_food_milli": army_food_milli,
		"chapter": chapter,
		"capital_hex": capital_hex,
		"next_id": next_id,
		"gold_net_milli": _gold_net_milli,
		"research": research.duplicate(),
	}


## Accepts to_dict() output, also after a JSON round trip (float numbers, string keys).
static func from_dict(d: Dictionary) -> RefCounted:
	var e: _Self = _Self.new(null, int(d.get("last_tick", 0)))
	var rs: Dictionary = d.get("research", {})
	for k in rs:
		e.research[String(k)] = int(rs[k])
	e.res = {}
	var r_in: Dictionary = d.get("res", {})
	for k in r_in:
		e.res[String(k)] = int(r_in[k])
	e.buildings = []
	var b_in: Array = d.get("buildings", [])
	for bv in b_in:
		var src: Dictionary = bv
		var b := {
			"id": int(src["id"]), "type": String(src["type"]), "hex": int(src["hex"]),
			"level": int(src["level"]), "upgrade_end": int(src["upgrade_end"]),
		}
		if src.has("paid"):
			b["paid"] = _int_dict(src["paid"])
		e.buildings.append(b)
	e.builders = int(d.get("builders", START_BUILDERS))
	e.last_tick = int(d.get("last_tick", 0))
	e.last_collect = int(d.get("last_collect", e.last_tick))
	e.stock = _int_keyed(d.get("stock", {}))
	e._stock_rem = _int_keyed(d.get("stock_rem", {}))
	e._upkeep_rem = int(d.get("upkeep_rem", 0))
	e._food_rem = int(d.get("food_rem", 0))
	e.ruin_pct = int(d.get("ruin_pct", 0))
	e.ruin_until = int(d.get("ruin_until", 0))
	var dm: Dictionary = d.get("damaged", {})
	for k in dm:
		e.damaged[int(k)] = int(dm[k])
	e.army_food_milli = int(d.get("army_food_milli", 0))
	e.chapter = int(d.get("chapter", 1))
	e.capital_hex = int(d.get("capital_hex", -1))
	e.next_id = int(d.get("next_id", e.buildings.size() + 1))
	e._gold_net_milli = int(d.get("gold_net_milli", 0))
	return e


# ---------------------------------------------------------------- internals

func _add_building(type: String, hex: int, level: int) -> Dictionary:
	var h := hex
	if BUILDINGS[type]["class"] == "capital":
		h = capital_hex
	var b := {"id": next_id, "type": type, "hex": h, "level": level, "upgrade_end": 0}
	next_id += 1
	buildings.append(b)
	return b


func _find_type(type: String) -> Dictionary:
	for b in buildings:
		if b["type"] == type:
			return b
	return {}


func _type_level(type: String) -> int:
	var b := _find_type(type)
	return 0 if b.is_empty() else int(b["level"])


static func _hex_type_for_kind(kind: String) -> String:
	for t in BUILDINGS:
		if BUILDINGS[t]["class"] == "hex_type" and BUILDINGS[t]["kind"] == kind:
			return t
	return ""


func _count_kind(kind: String) -> int:
	var n := 0
	for h in _own_kinds:
		if _own_kinds[h] == kind and bool(_own_ctrl[h]):
			n += 1
	return n


static func _ceil_div(a: int, b: int) -> int:
	return (a + b - 1) / b


static func _level_mult100(level: int) -> int:
	return 100 + 8 * (maxi(level, 1) - 1)


func _prod_mult100() -> int:
	return PROD_MULT100[clampi(dev_level(), 1, 10)]


## Cost of reaching `level` for a building type (resources + "seconds").
func _level_cost(type: String, level: int) -> Dictionary:
	var out := {}
	for r in RES:
		out[r] = 0
	var cls: String = BUILDINGS[type]["class"]
	if type == "residence":
		var i := clampi(level, 2, 10)
		var rc: Dictionary = RESIDENCE_COST[i]
		for r in rc:
			out[r] = int(rc[r])
		out["seconds"] = RESIDENCE_SECONDS[i]
	elif cls == "defense":
		# base × М_произв(ур) × 1,5^(ур−1), М_произв by the fort's own level (canon §7), rounded up.
		var lv := clampi(level, 1, 10)
		var p3 := 1
		var p2 := 1
		for i in lv - 1:
			p3 *= 3
			p2 *= 2
		var base: Dictionary = DEFENSE_COST_BASE[type]
		for r in base:
			if r == "oil" and lv < 8:
				continue
			out[r] = _ceil_div(int(base[r]) * PROD_MULT100[lv] * p3, 100 * p2)
		out["seconds"] = DEFENSE_SECONDS[lv]
	else:
		# C_B × М_произв(текущий УР) × 1,22^(ур−1), ur = current level; to level ≥ 9: 75% gold + 25% metal.
		var lv := clampi(level, 2, 20)
		var num: int = int(BUILDINGS[type]["cb"]) * _prod_mult100() * GROWTH_122_E9[lv - 2]
		var den: int = 100 * 1000000000
		if lv <= 8:
			out["gold"] = _ceil_div(num, den)
		else:
			out["gold"] = _ceil_div(3 * num, 4 * den)
			out["metal"] = _ceil_div(num, 4 * den)
		out["seconds"] = BUILD_SECONDS[lv]
	return out


func _can_pay_and_staff(type: String, cost: Dictionary, now: int) -> String:
	if TREASURY_LOCKED.has(type) and treasury_empty():
		return "err.treasury_empty"
	if busy_builders(now) >= builders:
		return "err.builders_busy"
	for r in ["gold", "food", "metal", "oil"]:
		if int(cost.get(r, 0)) > int(res.get(r, 0)):
			return "err.not_enough|" + String(RES_NAMES[r])
	return ""


func _pay(b: Dictionary, cost: Dictionary) -> void:
	for r in cost:
		if r == "seconds":
			continue
		var v: int = cost[r]
		if v <= 0:
			continue
		res[r] = int(res.get(r, 0)) - v
		if b.has("paid"):
			var paid: Dictionary = b["paid"]
			paid[r] = int(paid.get(r, 0)) + v


func _complete(b: Dictionary) -> void:
	b["level"] = int(b["level"]) + 1
	b["upgrade_end"] = 0
	_events.append({"type": "upgrade_done", "building": b["id"], "building_type": b["type"], "level": b["level"]})
	if b["type"] == "residence":
		var dl: int = b["level"]
		_events.append({"type": "dev_level", "level": dl})
		for t in BUILDING_ORDER:
			if int(BUILDINGS[t]["unlock_dl"]) <= dl and _find_type(t).is_empty():
				var nb := _add_building(t, -1, 1)
				_events.append({"type": "building_unlocked", "building": nb["id"], "building_type": t})


func _complete_due(now: int) -> void:
	# Time order, then id order — deterministic.
	var due: Array = []
	for b in buildings:
		var e: int = b["upgrade_end"]
		if e > 0 and e <= now:
			due.append(b)
	due.sort_custom(func(x: Dictionary, y: Dictionary) -> bool:
		if x["upgrade_end"] != y["upgrade_end"]:
			return int(x["upgrade_end"]) < int(y["upgrade_end"])
		return int(x["id"]) < int(y["id"]))
	for b in due:
		_complete(b)


## Player land cache + gold balance used by methods without a world argument.
func _sync(world: World) -> void:
	if world == null:
		return
	_own_kinds = {}
	_own_ctrl = {}
	for c in world.cells:
		if c["owner"] == Types.PLAYER and Types.is_passable(c):
			_own_kinds[int(c["id"])] = String(c["kind"])
			_own_ctrl[int(c["id"])] = c["controller"] == Types.PLAYER
	_synced = true
	var gross := _rates_total(world)
	_gold_net_milli = int(gross["gold"]) - _upkeep_milli()


## Writes fort levels and DL into the world; removes forts / towers on hexes the player no longer owns
## and refunds 100% of what was paid over the cap (canon §7, решение 20; 05 §6.3).
func _sync_world(world: World) -> void:
	if world == null:
		return
	world.states[Types.PLAYER]["dev_level"] = dev_level()
	var keep: Array = []
	for b in buildings:
		if BUILDINGS[b["type"]]["class"] != "defense":
			keep.append(b)
			continue
		var c: Dictionary = world.cells[int(b["hex"])]
		if c["owner"] != Types.PLAYER:
			if b["type"] == "tower":
				c["tower"] = 0
			var refund := add_resources(b.get("paid", {}), true)
			_events.append({"type": "fort_refund", "building": b["id"], "hex": b["hex"], "refund": refund})
			continue
		if b["type"] == "fort":
			c["fort"] = int(b["level"])
		elif b["type"] == "tower":
			c["tower"] = int(b["level"])
		keep.append(b)
	buildings = keep


## Income of one hex in milli-units/h for the player. occupied = enemy-owned hex under player control
## (50% by the occupant's formula, canon §5.1).
func _hex_rate_milli(c: Dictionary, occupied: bool) -> Dictionary:
	var out := {}
	var spec: Dictionary = HEX_PRODUCTION.get(String(c["kind"]), {})
	if spec.is_empty():
		return out
	var lvl_type: String = spec["lvl"]
	var lm := 100 if lvl_type == "" else _level_mult100(_type_level(lvl_type))
	var mp := _prod_mult100()
	var base: Dictionary = spec["res"]
	for r in base:
		var v: int = int(base[r]) * mp * lm / 10   # base × 1000 × mp/100 × lm/100
		v = v * (100 + 2 * int(research.get(r, 0))) / 100
		if occupied:
			v /= 2
		out[r] = v
	return out


## hex id -> rate dict (milli/h) for every hex currently producing for the player.
func _hex_rates(world: World) -> Dictionary:
	var out := {}
	for c in world.cells:
		if c["controller"] != Types.PLAYER or not Types.is_passable(c):
			continue
		var hr := _hex_rate_milli(c, c["owner"] != Types.PLAYER)
		if hr.is_empty():
			continue
		var m := _temp_mult100(int(c["id"]), c["owner"] == Types.PLAYER)
		if m != 100:
			for r in hr:
				hr[r] = int(hr[r]) * m / 100
		out[int(c["id"])] = hr
	return out


## Temporary production modifiers of an own hex, percent: ruin × damaged building (they multiply, canon §5.1).
func _temp_mult100(hex: int, own: bool) -> int:
	if not own:
		return 100
	var t := _rate_t if _rate_t >= 0 else last_tick
	var m := 100
	if ruin_until > t:
		m = m * (100 - ruin_pct) / 100
	if damaged.has(hex):
		var e: int = damaged[hex]
		if e == 0 or e > t:
			m = m / 2
	return m


## Ruin after a plundered defeat: a repeat doesn't stack — the larger percent and the later end win (canon §5.1).
func apply_ruin(pct: int, seconds: int, now: int) -> void:
	if ruin_until > now:
		ruin_pct = maxi(ruin_pct, pct)
		ruin_until = maxi(ruin_until, now + seconds)
	else:
		ruin_pct = pct
		ruin_until = now + seconds


func ruin_left(now: int) -> int:
	return maxi(0, ruin_until - now)


## Halves the remaining ruin (ad_ruin_halve, canon §15.2).
func halve_ruin(now: int) -> void:
	if ruin_until > now:
		ruin_until = now + (ruin_until - now) / 2


## Damages up to `n` hex buildings of the loser (cities, farms, mines, ports; never capital buildings),
## the most productive first, ties by hex id. Returns the damaged hex ids.
func damage_buildings(world: World, n: int) -> Array:
	var cands: Array = []
	for c in world.cells:
		if c["owner"] != Types.PLAYER or c["controller"] != Types.PLAYER or not DAMAGE_KINDS.has(String(c["kind"])):
			continue
		if damaged.has(int(c["id"])):
			continue
		var tot := 0
		var hr := _hex_rate_milli(c, false)
		for r in hr:
			tot += int(hr[r])
		cands.append([tot, int(c["id"])])
	cands.sort_custom(func(a, b): return a[0] > b[0] if a[0] != b[0] else a[1] < b[1])
	var out: Array = []
	for i in mini(n, cands.size()):
		damaged[int(cands[i][1])] = 0
		out.append(int(cands[i][1]))
	return out


## Repair price: 5% of the current level price of the hex's building type, 10 min (canon §9.14).
func repair_cost(world: World, hex: int) -> Dictionary:
	var spec: Dictionary = HEX_PRODUCTION.get(String(world.cells[hex]["kind"]), {})
	var t: String = spec.get("lvl", "")
	var lvl := maxi(1, _type_level(t)) if t != "" else 1
	var full := _level_cost(t, lvl) if t != "" else {"gold": 100}
	var out := {}
	for r in RES:
		var v: int = int(full.get(r, 0)) * REPAIR_PCT / 100
		if v > 0:
			out[r] = v
	if out.is_empty():
		out["gold"] = 10
	return out


## "" when the repair can start, else a reason key.
func can_repair(world: World, hex: int) -> String:
	if not damaged.has(hex):
		return "err.not_damaged"
	if int(damaged[hex]) > 0:
		return "err.repairing"
	var cost := repair_cost(world, hex)
	for r in cost:
		if int(res.get(r, 0)) < int(cost[r]):
			return "err.not_enough|" + String(RES_NAMES[r])
	return ""


## Starts a repair (free = ad_repair: no cost, done at once). Returns true when started.
func start_repair(world: World, hex: int, now: int, free := false) -> bool:
	if free:
		if not damaged.has(hex):
			return false
		damaged.erase(hex)
		return true
	if can_repair(world, hex) != "":
		return false
	var cost := repair_cost(world, hex)
	for r in cost:
		res[r] = int(res[r]) - int(cost[r])
	damaged[hex] = now + REPAIR_SEC
	return true


func _finish_repairs(now: int) -> void:
	for h in damaged.keys():
		var e: int = damaged[h]
		if e > 0 and e <= now:
			damaged.erase(h)
			_events.append({"type": "repair_done", "hex": h})


func _rates_total(world: World) -> Dictionary:
	var out := {}
	for r in RES:
		out[r] = 0
	var rates := _hex_rates(world)
	for h in rates:
		var hr: Dictionary = rates[h]
		for r in hr:
			out[r] = int(out[r]) + int(hr[r])
	return out


## Gold upkeep, milli/h: base × М_апкип(УР) × (1 + 0,08 × (ур − 1)) × n (canon §7). Capital buildings
## count once; hex types per own controlled hex of their kind; fort / tower by their own level and
## only on controlled hexes (occupied hex: 0, canon §5.1). Residence base 0.
func _upkeep_milli() -> int:
	var mu: int = UPKEEP_MULT100[clampi(dev_level(), 1, 10)]
	var total := 0
	for b in buildings:
		var t: String = b["type"]
		var spec: Dictionary = BUILDINGS[t]
		var base: int = spec["upkeep"]
		var lvl: int = b["level"]
		if base == 0 or lvl <= 0:
			continue
		match String(spec["class"]):
			"capital":
				total += base * mu * _level_mult100(lvl) / 10
			"hex_type":
				total += base * mu * _level_mult100(lvl) * _count_kind(String(spec["kind"])) / 10
			"defense":
				if bool(_own_ctrl.get(int(b["hex"]), not _synced)):
					total += base * UPKEEP_MULT100[clampi(lvl, 1, 10)] * _level_mult100(lvl) / 10
	return total * (100 - 3 * int(research.get("thrift", 0))) / 100


## Accrues the interval [a, b) clipped to the 8 h economy window (canon §4 E7).
func _accrue(world: World, a: int, b: int) -> void:
	var end := mini(b, last_collect + POOL_HOURS * HOUR)
	if end <= a:
		return
	var dt := end - a
	_sync(world)
	var quarters := 3 if treasury_empty() else 4   # «Казна пуста»: production −25% (canon §3.4)
	var rates := _hex_rates(world)
	var keys := _sorted_keys(rates)
	# The pool grows by the NET flow (canon §4, 05 §5.1); coins over hexes are a visual split of the
	# pool proportional to hex income (05 §5.1). So gold upkeep is spread over gold hexes pro rata:
	# every gold hex but the biggest gets floor(rate × net / gross), the biggest takes the rest, so
	# Σ = net exactly and accrual is linear in time (same result for any tick granularity).
	var up := _upkeep_milli()
	var gold_gross := 0
	var top := -1
	var top_rate := 0
	for h in keys:
		var g: int = int(rates[h].get("gold", 0)) * quarters / 4
		gold_gross += g
		if g > top_rate:
			top = h
			top_rate = g
	var gold_net := maxi(0, gold_gross - up)
	var gold_eff := {}
	var given := 0
	for h in keys:
		var g: int = int(rates[h].get("gold", 0)) * quarters / 4
		if g > 0 and h != top:
			gold_eff[h] = g * gold_net / gold_gross
			given += int(gold_eff[h])
	if top >= 0:
		gold_eff[top] = gold_net - given
	for h in keys:
		var hr: Dictionary = rates[h]
		for r in hr:
			var rate: int = hr[r]
			var eff: int = gold_eff.get(h, 0) if r == "gold" else rate * quarters / 4
			_add_stock(h, String(r), eff * dt, rate * POOL_HOURS * HOUR)
	# Upkeep above gold income: whole units from the pool (stock, hex id order), then storage;
	# no debt (canon §4 E2).
	var owed := _upkeep_rem + maxi(0, up - gold_gross) * dt
	var whole := owed / SUB
	_upkeep_rem = owed % SUB
	for h in _sorted_keys(stock):
		if whole <= 0:
			break
		var s: Dictionary = stock[h]
		var have: int = s.get("gold", 0)
		var take := mini(have, whole)
		if take > 0:
			s["gold"] = have - take
			whole -= take
	if whole > 0:
		res["gold"] = maxi(0, int(res["gold"]) - whole)
	_take_pool_first("food", army_food_milli, dt)
	_prune_stock()


## Army upkeep (04 §6.1): `milli_per_h` × dt in whole units, first from the uncollected pool (hex id order),
## then from storage; never below 0 and no debt (canon §4 E2).
func _take_pool_first(r: String, milli_per_h: int, dt: int) -> void:
	if milli_per_h <= 0:
		return
	var owed := _food_rem + milli_per_h * dt
	var whole := owed / SUB
	_food_rem = owed % SUB
	for h in _sorted_keys(stock):
		if whole <= 0:
			break
		var s: Dictionary = stock[h]
		var have: int = s.get(r, 0)
		var take := mini(have, whole)
		if take > 0:
			s[r] = have - take
			whole -= take
	if whole > 0:
		res[r] = maxi(0, int(res.get(r, 0)) - whole)


## Adds `sub` sub-units of r to a hex; the total is capped at `cap_sub` (but never reduced below what
## already lies there — a lost hex keeps its stock, 05 §5.5).
func _add_stock(hex: int, r: String, sub: int, cap_sub: int) -> void:
	if not stock.has(hex):
		stock[hex] = {}
	if not _stock_rem.has(hex):
		_stock_rem[hex] = {}
	var s: Dictionary = stock[hex]
	var rem: Dictionary = _stock_rem[hex]
	var cur: int = int(s.get(r, 0)) * SUB + int(rem.get(r, 0))
	var total := cur + sub
	var cap := maxi(cur, cap_sub)
	if total > cap:
		total = cap
	s[r] = total / SUB
	rem[r] = total % SUB


func _collect_hex(hex: int, gained: Dictionary, cap: Dictionary) -> void:
	if not stock.has(hex):
		return
	var s: Dictionary = stock[hex]
	for r in RES:
		var have: int = s.get(r, 0)
		if have <= 0:
			continue
		var cur: int = res.get(r, 0)
		var move := mini(have, maxi(0, int(cap[r]) - cur))
		if move > 0:
			res[r] = cur + move
			s[r] = have - move
			gained[r] = int(gained.get(r, 0)) + move
	_prune_stock()


func _prune_stock() -> void:
	for h in _sorted_keys(stock):
		var s: Dictionary = stock[h]
		for r in s.keys():
			if int(s[r]) <= 0:
				s.erase(r)
		if s.is_empty():
			stock.erase(h)


static func _sorted_keys(d: Dictionary) -> Array:
	var ks: Array = d.keys()
	ks.sort()
	return ks


static func _int_dict(v: Variant) -> Dictionary:
	var out := {}
	if v is Dictionary:
		var src: Dictionary = v
		for k in src:
			out[String(k)] = int(src[k])
	return out


static func _int_keyed(v: Variant) -> Dictionary:
	var out := {}
	if v is Dictionary:
		var src: Dictionary = v
		for k in src:
			out[int(k)] = _int_dict(src[k])
	return out
