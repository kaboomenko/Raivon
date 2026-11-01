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
	var four := 1791172800 + 40 * 86400  # 04:00 of a later day
	c.visit(four - 60)
	c.claim()
	_check(c.visit(four + 60) and c.credited == 5, "03:59 and 04:01 are two calendar days")
	_check(Calendar.entry(26)[0][0][0] == "shards_choice" and Calendar.entry(54)[0][0][0] == "shards_pick", "day 26: shards of the player's choice; cycle 2 gives them automatically")
	c.choice = 15
	var q := Calendar.new()
	q.load_dict(c.to_dict())
	_check(q.choice == 15, "an unpicked choice survives a save")
	_check(q.credited == 5 and q.pending and q.last_day == c.last_day, "save and load")
	_local_day()


## The day starts at 04:00 device-local time (canon 00 §13, 08 §8.8.4; playtest 2 Q3: it was 04:00 UTC — the evening
## before in New York, 07:00 in Kyiv): biases −300 (New York), 0, +180 (Moscow), +540 (Tokyo) around a day boundary.
func _local_day() -> void:
	var monday := 1791172800  # 2026-10-05 04:00 UTC
	for b in [-300, 0, 180, 540]:
		Calendar.bias_min = b
		var four: int = monday + 10 * 86400 - b * 60  # 04:00 local of a day
		_check(Calendar.local_day(four - 60) + 1 == Calendar.local_day(four + 60), "bias %+d: 03:59 and 04:01 local are two game days" % b)
		_check(Calendar.next_reset(four - 60) == four and Calendar.next_reset(four + 60) == four + 86400, "bias %+d: the next reset is 04:00 local" % b)
		var cb := Calendar.new()
		cb.visit(four - 3600)
		cb.claim()
		_check(not cb.visit(four - 60) and cb.visit(four + 60) and cb.credited == 2, "bias %+d: the calendar's next day comes at 04:00 local" % b)
	Calendar.bias_min = 0
	_check(Calendar.local_day(monday + 3600) == Calendar.game_day(monday + 3600), "game_day is the local day")
	# the offset is adopted at once the first time, then changes at most once per 7 days (08 §8.8.4)
	var t := monday
	_check(Calendar.adopt_bias(0, 0, 180, t) == [180, t], "first run (or an old save): the device's offset at once")
	_check(Calendar.adopt_bias(180, t, -300, t + 3 * 86400) == [180, t], "a new zone within 7 days waits")
	_check(Calendar.adopt_bias(180, t, -300, t + 7 * 86400) == [-300, t + 7 * 86400], "after 7 days the new zone is taken")
	_check(Calendar.adopt_bias(180, t, 180, t + 9 * 86400) == [180, t], "the same zone: nothing changes")
	# a step west turns the day number back: never a second credit of the same day
	var w := Calendar.new()
	Calendar.bias_min = 0
	_check(w.visit(t + 2 * 3600) and w.credited == 1, "credited at 06:00 UTC")
	w.claim()
	Calendar.bias_min = -300  # now New York: 07:00 UTC is 02:00 there, the day before
	_check(not w.visit(t + 3 * 3600) and not w.visit(t + 5 * 3600 + 60) and w.credited == 1, "a step west: the same day is not credited again")
	_check(w.visit(t + 86400 + 5 * 3600 + 60) and w.credited == 2, "… the next local day is")
	Calendar.bias_min = 0
	# a save from before the local day keeps its streak
	var old := Calendar.new()
	old.load_dict({"credited": 12, "last_day": Calendar.local_day(t), "pending": false})
	_check(old.visit(t + 86400 + 60) and old.credited == 13, "an old save keeps its streak")
	print("ALL CALENDAR CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
