extends SceneTree
## Weekly tasks (08 §8.7). Run: godot --headless --path game --script res://tests/test_weekly.gd

const Weekly := preload("res://scripts/sim/weekly.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var xp := 0
	for t in Weekly.TASKS:
		xp += int(t[3])
	_check(Weekly.TASKS.size() == 7 and xp == 3400, "7 tasks worth 3 400 XP a week")
	var t0 := Weekly.MONDAY + 86400
	var stats := {"captures": 10, "upgrades": 3}
	var w := Weekly.new()
	_check(w.refresh(t0, 2, stats) and not w.refresh(t0 + 3600, 2, stats), "one set per week")
	_check(w.progress(1, stats) == 0, "progress counts from the week's start")
	stats["captures"] = 25
	_check(w.progress(1, stats) == 15 and w.claim(1, stats) == 500 and w.claim(1, stats) == 0, "a task pays once")
	stats["upgrades"] = 7
	stats["research_starts"] = 4
	_check(w.claim(4, stats) == 400, "builds count upgrades and research together")
	_check(not w.claim_chest(0), "step 1 needs 4 tasks")
	stats["peace_wins"] = 1
	stats["convoys"] = 15
	w.claim(0, stats)
	w.claim(3, stats)
	_check(w.claim_chest(0) and not w.claim_chest(0) and not w.claim_chest(1), "4 of 7: step 1 once, step 2 not yet")
	w.refresh(t0 + 7 * 86400, 5, stats)
	_check(w.done_count() == 0 and int(w.need[1]) == 30, "next week: fresh, DL4–6 targets")
	var q := Weekly.new()
	q.load_dict(w.to_dict())
	_check(q.week == w.week and q.need.size() == 7, "save and load")
	print("ALL WEEKLY CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
