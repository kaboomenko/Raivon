extends SceneTree
## «Приказы дня» (canon §14.5, 08 §8.6). Run: godot --headless --path game --script res://tests/test_orders.gd

const Orders := preload("res://scripts/sim/orders.gd")
const Calendar := preload("res://scripts/sim/calendar.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var day0 := 1791000000
	var stats := {"collects": 5, "offensives": 1}
	var ctx := {"dl": 2, "stats": stats, "tags": {"war": true, "camp": true, "wild": true, "market": true, "ch2": true}}
	var o := Orders.new()
	_check(o.refresh(day0, ctx) and o.list.size() == 3, "3 orders a day")
	_check(not o.refresh(day0 + 3600, ctx), "the same set within the day")
	var codes := {}
	for x in o.list:
		codes[x["code"]] = true
	_check(codes.size() == 3, "no duplicates in a day's set")
	var slot_b := false
	for t in Orders.POOL:
		if t[0] == o.list[1]["code"]:
			slot_b = t[3] == "B"
	_check(slot_b, "the 2nd order is a map / war one (slot B)")
	# progress counts from the roll; claim pays XP once
	var first: Dictionary = o.list[0]
	_check(o.progress(0, stats) == 0, "progress starts at 0 (counters before the roll don't count)")
	stats[first["stat"]] = int(stats.get(first["stat"], 0)) + int(first["need"])
	_check(o.done(0, stats) and o.claim(0, stats) == int(first["xp"]) and o.claim(0, stats) == 0, "claim pays XP once")
	_check(not o.claim_all(), "the bonus needs all three")
	for i in [1, 2]:
		stats[o.list[i]["stat"]] = int(stats.get(o.list[i]["stat"], 0)) + int(o.list[i]["need"])
		o.claim(i, stats)
	_check(o.claim_all() and not o.claim_all(), "all three: the bonus once")
	# without a war the war orders are not rolled
	var peace_ctx := {"dl": 2, "stats": {}, "tags": {}}
	var p := Orders.new()
	p.refresh(day0, peace_ctx)
	var war_order := false
	for x in p.list:
		for t in Orders.POOL:
			if t[0] == x["code"] and t[5] != "":
				war_order = true
	_check(not war_order and p.list.size() == 3, "only always-available orders when nothing else is possible")
	# the next day rolls a new set; a template doesn't repeat for 3 days
	o.refresh(day0 + 86400, ctx)
	var again := false
	for x in o.list:
		if codes.has(x["code"]):
			again = true
	_check(not again, "yesterday's orders don't come back the next day")
	# one free swap
	var before: String = o.list[2]["code"]
	_check(o.swap(2, ctx) and String(o.list[2]["code"]) != before and not o.swap(1, ctx), "one free swap a day")
	# save / load
	var q := Orders.new()
	q.load_dict(o.to_dict())
	_check(q.day == o.day and q.list.size() == 3 and q.swapped, "save and load")
	# a new set at 04:00 local (canon §13, 08 §8.6): biases −300, 0, +180, +540
	for b in [-300, 0, 180, 540]:
		Calendar.bias_min = b
		var four: int = 1791172800 + 20 * 86400 - b * 60  # 04:00 local
		var ob := Orders.new()
		ob.refresh(four - 3600, ctx)
		_check(not ob.refresh(four - 60, ctx) and ob.refresh(four + 60, ctx), "bias %+d: a new set at 04:00 local" % b)
	# a step west keeps the day's set (its progress and claims)
	Calendar.bias_min = 0
	var ow := Orders.new()
	var t1 := 1791172800 + 30 * 86400 + 2 * 3600  # 06:00 UTC
	ow.refresh(t1, ctx)
	var keep: String = ow.list[0]["code"]
	Calendar.bias_min = -300
	_check(not ow.refresh(t1 + 3600, ctx) and String(ow.list[0]["code"]) == keep, "a step west keeps the day's orders")
	Calendar.bias_min = 0
	print("ALL ORDERS CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
