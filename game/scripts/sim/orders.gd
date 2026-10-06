extends RefCounted
## «Приказы дня» (canon §14.5, 08 §8.6): 3 daily tasks from a template pool — slot A economy (easy), slot B map
## and war (medium), slot C any — reset at 04:00, rolled lazily on the first look after the reset. Progress is a
## stat counter's growth since the roll (the caller keeps the counters). Each done order pays pass XP (150 / 200
## / 250), all three a War crate + 10 Raivites. One free swap a day. A template doesn't repeat in its slot for 3
## days. Deterministic: the roll is seeded by the day number.

const Rng := preload("res://scripts/sim/rng.gd")

const DAY := 86400
const REFRESH_SEC := 4 * 3600  # 04:00
const XP := {"easy": 150, "mid": 200, "hard": 250}
const ALL_RAIVITE := 10

## code, stat counter, targets for DL 1–3 / 4–6 / 7–8, slot, difficulty, availability tag.
const POOL := [
	["order_collect_3", "collects", [3, 3, 3], "A", "easy", ""],
	["order_deposits", "convoys", [3, 4, 5], "A", "easy", ""],
	["order_raider_camp", "camps", [1, 1, 1], "A", "easy", "camp"],
	["order_colonize", "colonized", [1, 1, 1], "A", "easy", "wild"],
	["order_upgrades_2", "upgrades", [2, 2, 2], "A", "easy", ""],
	["order_fort", "forts", [1, 1, 1], "A", "easy", ""],
	["order_research", "research_starts", [1, 1, 1], "A", "easy", ""],
	["order_train", "trainings", [1, 1, 2], "A", "easy", ""],
	["order_market", "trades", [1, 1, 1], "A", "easy", "market"],
	["order_gift", "gifts", [1, 1, 1], "A", "easy", "ch2"],
	["order_crates_2", "crates", [2, 2, 2], "A", "easy", ""],
	["order_offensives_2", "offensives", [2, 2, 2], "B", "mid", "war"],
	["order_stars_2", "stars2", [1, 1, 1], "B", "mid", "war"],
	["order_capture", "captures", [4, 6, 8], "B", "mid", "war"],
	["order_cards", "cards", [5, 6, 8], "B", "mid", "war"],
	["order_stars_3", "stars3", [1, 1, 1], "C", "hard", "war"],
	["order_pocket", "pockets", [1, 1, 1], "C", "hard", "war"],
	["order_peace_win", "peaces", [1, 1, 1], "C", "hard", "war"],
]

var day := -1
var list: Array = []            # [{code, stat, need, xp, base, claimed}]
var all_claimed := false
var swapped := false            # the free swap of the day is spent
var history := {}               # code -> last day used (no repeats within 3 days)


static func game_day(now: int) -> int:
	return int(floor(float(now - REFRESH_SEC) / DAY))


static func _tier(dl: int) -> int:
	return 0 if dl <= 3 else (1 if dl <= 6 else 2)


## ctx: {dl, stats: Dictionary, tags: {camp, wild, market, ch2, war: bool}}. Rolls a new set when the day changed.
func refresh(now: int, ctx: Dictionary) -> bool:
	var d := game_day(now)
	if d == day and list.size() == 3:
		return false
	day = d
	list = []
	all_claimed = false
	swapped = false
	var rng := Rng.new(d * 7919 + 17)
	var taken := {}
	for slot in ["A", "B", "C"]:
		var pick := _pick(rng, slot, ctx, taken, d)
		if pick.is_empty():
			pick = _pick(rng, "A", ctx, taken, d)  # nothing fits (no war yet): an economy order instead
		if pick.is_empty():
			continue
		taken[pick[0]] = true
		list.append(_instance(pick, ctx))
		history[pick[0]] = d
	return true


func _available(t: Array, ctx: Dictionary) -> bool:
	var tag: String = t[5]
	return tag == "" or bool((ctx.get("tags", {}) as Dictionary).get(tag, false))


func _pick(rng, slot: String, ctx: Dictionary, taken: Dictionary, d: int) -> Array:
	var cands: Array = []
	for t in POOL:
		if taken.has(t[0]) or not _available(t, ctx):
			continue
		if slot != "C" and t[3] != slot:
			continue
		if d - int(history.get(t[0], -100)) < 3:
			continue
		cands.append(t)
	if cands.is_empty():
		return []
	return cands[rng.next_int(cands.size())]


func _instance(t: Array, ctx: Dictionary) -> Dictionary:
	var stats: Dictionary = ctx.get("stats", {})
	var key: String = t[1]
	return {"code": t[0], "stat": key, "need": int((t[2] as Array)[_tier(int(ctx.get("dl", 1)))]), "xp": int(XP[t[4]]),
		"base": int(stats.get(key, 0)), "claimed": false}


func progress(i: int, stats: Dictionary) -> int:
	var o: Dictionary = list[i]
	return mini(int(o["need"]), int(stats.get(o["stat"], 0)) - int(o["base"]))


func done(i: int, stats: Dictionary) -> bool:
	return progress(i, stats) >= int(list[i]["need"])


## Claims order i: returns its XP, or 0 when not done / already claimed.
func claim(i: int, stats: Dictionary) -> int:
	if i < 0 or i >= list.size() or list[i]["claimed"] or not done(i, stats):
		return 0
	list[i]["claimed"] = true
	return int(list[i]["xp"])


func all_done() -> bool:
	for o in list:
		if not o["claimed"]:
			return false
	return list.size() == 3


## Claims the bonus for all three (a War crate + 10 Raivites — the caller pays it). True once a day.
func claim_all() -> bool:
	if all_claimed or not all_done():
		return false
	all_claimed = true
	return true


## The day's one free swap of an unfinished order for another one of the same slot rules.
func swap(i: int, ctx: Dictionary) -> bool:
	if swapped or i < 0 or i >= list.size() or list[i]["claimed"]:
		return false
	var taken := {}
	for o in list:
		taken[o["code"]] = true
	var rng := Rng.new(day * 104729 + i)
	var slot: String = ["A", "B", "C"][i]
	var pick := _pick(rng, slot, ctx, taken, day)
	if pick.is_empty():
		pick = _pick(rng, "A", ctx, taken, day)
	if pick.is_empty():
		return false
	list[i] = _instance(pick, ctx)
	history[pick[0]] = day
	swapped = true
	return true


func to_dict() -> Dictionary:
	return {"day": day, "list": list.duplicate(true), "all": all_claimed, "swapped": swapped, "history": history.duplicate()}


func load_dict(d: Dictionary) -> void:
	day = int(d.get("day", -1))
	list = []
	for o in d.get("list", []):
		if typeof(o) == TYPE_DICTIONARY:
			list.append({"code": String(o.get("code", "")), "stat": String(o.get("stat", "")), "need": int(o.get("need", 1)),
				"xp": int(o.get("xp", 150)), "base": int(o.get("base", 0)), "claimed": bool(o.get("claimed", false))})
	all_claimed = bool(d.get("all", false))
	swapped = bool(d.get("swapped", false))
	history = {}
	var h: Dictionary = d.get("history", {})
	for k in h:
		history[String(k)] = int(h[k])
