extends SceneTree
## «Военный пропуск» (canon §15.6, 09 §9.12). Run: godot --headless --path game --script res://tests/test_pass.gd

const BattlePass := preload("res://scripts/sim/battlepass.gd")

var fails := 0


func _check(cond: bool, msg: String) -> void:
	print(("PASS  " if cond else "FAIL  ") + msg)
	if not cond:
		fails += 1


func _initialize() -> void:
	var d: Dictionary = BattlePass.data()
	var levels: Array = d.get("levels", [])
	_check(levels.size() == 40, "40 levels")
	var free_r := 0
	var prem_r := 0
	var rai := 0
	var speed := 0
	for l in levels:
		var f: Array = l["free"]
		var p: Array = l["premium"]
		if f[0] == "raivite":
			free_r += int(f[1])
		if p[0] == "raivite":
			prem_r += int(p[1])
		if p[0] == "shards" and p[1] == "cmd_rai":
			rai += int(p[2])
		if p[0] == "speed":
			speed += int(p[1])
	_check(free_r == 300 and prem_r == 1200 and rai == 30 and speed == 12, "canon totals: 300 / 1 200 Raivites, 30 Rai shards, 12 h speed-ups")
	var t := BattlePass.EPOCH + 3 * 86400
	var bp := BattlePass.new()
	bp.refresh(t)
	_check(bp.season == 0 and bp.level() == 0, "season 1 starts at level 0")
	# offensives: full XP for the first 8 a day, then 10
	var got := 0
	for i in 10:
		got += bp.gain("offensive2", t)
	_check(got == 8 * 55 + 2 * 10, "offensives: 8 full, then 10 (%d)" % got)
	_check(bp.gain("peace", t) == 80 and bp.gain("peace", t) == 80 and bp.gain("peace", t) == 80 and bp.gain("peace", t) == 0, "3 victorious peaces a day")
	_check(bp.gain("peace", t + 86400) == 80, "the cap resets the next day")
	bp.add_xp(2000 - bp.xp, t)
	_check(bp.level() == 2 and bp.can_claim(1, "free") and not bp.can_claim(3, "free"), "level 2 claims levels 1–2 only")
	_check(not bp.can_claim(1, "premium"), "premium needs the pass")
	_check(bp.claim(1, "free") == levels[0]["free"] and bp.claim(1, "free").is_empty(), "a reward is claimed once")
	bp.buy("iap_pass")
	_check(bp.can_claim(1, "premium") and bp.level() == 2, "premium opens its track, no levels")
	var e := BattlePass.new()
	e.refresh(t)
	e.buy("iap_pass_elite")
	_check(e.premium and e.elite and e.level() == 15, "elite: premium + 15 levels")
	var u := BattlePass.new()
	u.refresh(t)
	u.add_xp(2000, t)
	u.buy("iap_pass")
	u.buy("iap_pass_elite_up")
	_check(u.elite and u.level() == 17, "premium → elite upgrade adds the 15 levels")
	bp.add_xp(100000, t)
	_check(bp.level() == 40, "the level caps at 40")
	# a new season resets everything
	bp.refresh(t + 28 * 86400)
	_check(bp.season == 1 and bp.xp == 0 and not bp.premium and bp.claimed_free.is_empty(), "the next season starts fresh")
	var q := BattlePass.new()
	e.claim(3, "premium")
	q.load_dict(e.to_dict())
	_check(q.elite and q.xp == e.xp and q.claimed_prem.has(3), "save and load")
	print("ALL PASS CHECKS PASSED" if fails == 0 else "%d FAILED" % fails)
	quit(1 if fails > 0 else 0)
