extends SceneTree
## «Державный патент» (09 §9.13). Run: godot --headless --path game --script res://tests/test_patent.gd

const Patent := preload("res://scripts/sim/patent.gd")
const Calendar := preload("res://scripts/sim/calendar.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var t0 := Patent.MONDAY + 3600  # Monday 05:00
	var p := Patent.new()
	_check(not p.active(t0) and p.trial_eligible(), "starts inactive, the intro offer available")
	p.buy(t0, true)
	_check(p.active(t0) and p.days_left(t0) == 7 and not p.trial_eligible(), "the intro: 7 days, once")
	p.buy(t0, true)
	_check(p.days_left(t0) == 7, "the intro can't be taken twice")
	p.buy(t0)
	_check(p.days_left(t0) == 37, "a month stacks onto the time left")
	_check(p.claim_daily(t0) and not p.claim_daily(t0 + 3600), "40 Raivites once a game day")
	_check(p.claim_daily(t0 + 86400), "the next day again")
	_check(p.weekly_key(t0) and not p.weekly_key(t0 + 86400), "a Royal key once a week")
	_check(p.weekly_key(t0 + 7 * 86400), "next Monday another key")
	_check(p.month_frame(t0) and not p.month_frame(t0 + 3600), "the frame of the month once")
	var late := t0 + 40 * 86400
	_check(not p.active(late) and not p.claim_daily(late) and not p.weekly_key(late), "expired: no perks")
	var q := Patent.new()
	q.load_dict(p.to_dict())
	_check(q.until == p.until and q.trial_used and q.months.size() == 1, "save and load")
	# the day's Raivites and the Monday key follow 04:00 local (canon §13): biases −300, 0, +180, +540
	for b in [-300, 0, 180, 540]:
		Calendar.bias_min = b
		var four: int = Patent.MONDAY + 14 * 86400 - b * 60  # a Monday, 04:00 local
		var pb := Patent.new()
		pb.buy(four - 2 * 86400)
		_check(pb.claim_daily(four - 3600) and not pb.claim_daily(four - 60) and pb.claim_daily(four + 60), "bias %+d: 40 Raivites again from 04:00 local" % b)
		_check(pb.weekly_key(four - 60) and not pb.weekly_key(four - 30) and pb.weekly_key(four + 60), "bias %+d: the key's week turns on Monday 04:00 local" % b)
	Calendar.bias_min = 0
	var pw := Patent.new()
	pw.buy(t0)
	pw.claim_daily(t0 + 2 * 3600)
	Calendar.bias_min = -300  # a step west: the day number goes back, the day's Raivites are not paid twice
	_check(not pw.claim_daily(t0 + 3 * 3600) and not pw.daily_ready(t0 + 3 * 3600), "a step west: no second daily claim")
	Calendar.bias_min = 0
	print("ALL PATENT CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
