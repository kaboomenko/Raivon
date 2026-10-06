extends SceneTree
## Login calendar (08 §8.8). Run: godot --headless --path game --script res://tests/test_calendar.gd

const Calendar := preload("res://scripts/sim/calendar.gd")
const Cases := preload("res://scripts/sim/cases.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _sum(from: int, to: int, kind: String) -> int:
	var n := 0
	for k in range(from, to + 1):
		for r in Calendar.entry(k)[0]:
			if r[0] == kind:
				n += int(r[1])
	return n


func _initialize() -> void:
	_check(Calendar.CYCLE_1.size() == 28, "cycle 1 has 28 days")
	_check(_sum(1, 28, "raivite") == 480 and _sum(1, 28, "crate") == 9, "cycle 1: 480 Raivites and 9 War crates (08 §8.8.2)")
	_check(_sum(29, 56, "raivite") == 110 and _sum(57, 84, "raivite") == 110, "cycle 2+: 110 Raivites, repeating (08 §8.8.3)")
	var keys := 0
	for e in Calendar.CYCLE_1:
		if not e[1]:
			keys += 1
	_check(keys == 9 and not Calendar.entry(2)[1] and Calendar.entry(1)[1], "9 key days without ×2")
	_check(Calendar.entry(56)[0][0][0] == "season_cosmetic" and Calendar.entry(35)[0].size() == 2, "cycle 2: day 28 cosmetic, day 7 combo")
	for e in Calendar.CYCLE_1:
		for r in e[0]:
			if r[0] == "cosmetic":
				_check(not Cases.cosmetic(String(r[1])).is_empty(), "cosmetic %s exists" % r[1])
			if r[0] in ["cmd", "shards"]:
				_check(not Cases.commander(String(r[1])).is_empty(), "commander %s exists" % r[1])

	var t0 := 1791172800 + 3600  # Monday 05:00
	var c := Calendar.new()
	_check(c.visit(t0) and c.pending and c.credited == 1, "first visit credits day 1")
	_check(not c.visit(t0 + 3600), "same game day: nothing new")
	_check(not c.visit(t0 + 86400), "a waiting reward blocks the next credit")
	_check(c.can_double() and c.claim().size() == 2 and not c.pending, "day 1: resources + crate, ×2 allowed")
	_check(c.claim().is_empty(), "taken once")
	_check(not c.visit(t0 + 86400 + 3600), "the day of the block is spent")
	_check(c.visit(t0 + 2 * 86400) and c.credited == 2 and not c.can_double(), "day 2 (builder): no ×2")
	c.claim()
	_check(c.visit(t0 + 30 * 86400) and c.credited == 3, "a long absence only pauses (soft streak)")
	# 03:59 and 04:01 are two game days (08 §8.8.4)
	c.claim()
	var four := 1791172800 + 10 * 86400  # 04:00 of a later day
	c.visit(four - 60)
	c.claim()
	_check(c.visit(four + 60) and c.credited == 5, "03:59 and 04:01 are two calendar days")
	var q := Calendar.new()
	q.load_dict(c.to_dict())
	_check(q.credited == 5 and q.pending and q.last_day == c.last_day, "save and load")
	print("ALL CALENDAR CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
