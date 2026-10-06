extends RefCounted
## Weekly tasks (canon §14.5, 08 §8.7): a fixed set of 7, reset on Monday 04:00, targets by DL (1–3 / 4–6 / 7–8),
## pass XP on completion (3 400 a week), and the week's chest in two steps — 4 of 7 tasks and 6 of 7 (the higher
## step forgives one task and needs no daily login). Progress is the growth of stat counters since the week began.

const WEEK := 7 * 86400
const MONDAY := 1791172800  # 2026-10-05 04:00 UTC, a Monday
## code, stat counters (summed), targets by DL tier, XP
const TASKS := [
	["weekly_peace", ["peace_wins"], [1, 2, 2], 500],
	["weekly_capture", ["captures"], [15, 30, 40], 500],
	["weekly_orders", ["orders_all_days"], [4, 4, 4], 600],
	["weekly_deposits", ["convoys"], [15, 20, 25], 400],
	["weekly_builds", ["upgrades", "research_starts"], [8, 12, 12], 400],
	["weekly_forms", ["pockets"], [2, 2, 2], 500],
	["weekly_camps", ["camps", "colonized"], [5, 5, 5], 500],  # W7 stand-in while there are no events (08 §8.7.1)
]
const STEP_NEED := [4, 6]

var week := -1
var base := {}      # stat -> value at the week's start
var need := []      # per task, fixed for the week at its start
var claimed := {}   # task index -> true
var chest := {}     # step (0 / 1) -> true


static func week_of(now: int) -> int:
	return int(floor(float(now - MONDAY) / WEEK))


static func week_end(now: int) -> int:
	return MONDAY + (week_of(now) + 1) * WEEK


func refresh(now: int, dl: int, stats: Dictionary) -> bool:
	var w := week_of(now)
	if w == week and need.size() == TASKS.size():
		return false
	week = w
	base = {}
	for t in TASKS:
		for k in t[1]:
			base[k] = int(stats.get(k, 0))
	var tier := 0 if dl <= 3 else (1 if dl <= 6 else 2)
	need = []
	for t in TASKS:
		need.append(int((t[2] as Array)[tier]))
	claimed = {}
	chest = {}
	return true


func progress(i: int, stats: Dictionary) -> int:
	var n := 0
	for k in TASKS[i][1]:
		n += int(stats.get(k, 0)) - int(base.get(k, 0))
	return mini(int(need[i]), n)


func claim(i: int, stats: Dictionary) -> int:
	if i < 0 or i >= TASKS.size() or claimed.has(i) or progress(i, stats) < int(need[i]):
		return 0
	claimed[i] = true
	return int(TASKS[i][3])


func done_count() -> int:
	return claimed.size()


## The week's chest step (0: 4 of 7, 1: 6 of 7). True once per step and week.
func claim_chest(step: int) -> bool:
	if chest.has(step) or done_count() < int(STEP_NEED[step]):
		return false
	chest[step] = true
	return true


func to_dict() -> Dictionary:
	return {"week": week, "base": base.duplicate(), "need": need.duplicate(), "claimed": claimed.keys(), "chest": chest.keys()}


func load_dict(d: Dictionary) -> void:
	week = int(d.get("week", -1))
	base = {}
	var b: Dictionary = d.get("base", {})
	for k in b:
		base[String(k)] = int(b[k])
	need = []
	for n in d.get("need", []):
		need.append(int(n))
	claimed = {}
	for i in d.get("claimed", []):
		claimed[int(i)] = true
	chest = {}
	for s in d.get("chest", []):
		chest[int(s)] = true
