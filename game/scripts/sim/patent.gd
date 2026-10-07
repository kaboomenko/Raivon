extends RefCounted
## «Державный патент» (canon §15.7, 09 §9.13): a monthly subscription `iap_sub_patent` ($7.99) with the intro offer
## «7 days for $1.99» (`iap_sub_trial`, once per account). While active: rewarded rewards without the video (same
## caps), +1 temporary builder, +1 convoy, income collected automatically, timers ≤10 min finish for free, 40
## Raivites a day (claimed in the first session, an unclaimed day burns), a Royal case key every Monday 04:00 and
## the animated frame of the month. Deterministic; the caller applies the perks. No store SDK yet: a purchase sets
## the paid-until time (debug builds grant it).

const DAY := 86400
const MONTH_SEC := 30 * DAY
const TRIAL_SEC := 7 * DAY
const REFRESH_SEC := 4 * 3600
const MONDAY := 1791172800  # 2026-10-05 04:00 UTC
const DAILY_RAIVITE := 40
const FREE_FINISH_SEC := 600

var until := 0            # paid (or trial) until, unix seconds
var trial_used := false
var daily_day := -1       # the game day whose 40 Raivites were taken
var key_week := -1        # the last week a Royal key was given
var months := {}          # "YYYY-MM" -> true: the frames earned


static func game_day(now: int) -> int:
	return int(floor(float(now - REFRESH_SEC) / DAY))


static func week_of(now: int) -> int:
	return int(floor(float(now - MONDAY) / (7.0 * DAY)))


func active(now: int) -> bool:
	return now < until


func trial_eligible() -> bool:
	return not trial_used


## A purchase or renewal: a month, or the 7-day intro once. Stacks onto the time left.
func buy(now: int, trial := false) -> void:
	if trial:
		if trial_used:
			return
		trial_used = true
	until = maxi(until, now) + (TRIAL_SEC if trial else MONTH_SEC)


func days_left(now: int) -> int:
	return maxi(0, int(ceil(float(until - now) / DAY)))


## The day's 40 Raivites: true once per game day while active.
func claim_daily(now: int) -> bool:
	var d := game_day(now)
	if not active(now) or daily_day == d:
		return false
	daily_day = d
	return true


func daily_ready(now: int) -> bool:
	return active(now) and daily_day != game_day(now)


## A Royal case key on Monday 04:00 if active then: true once per week (the caller adds the key).
func weekly_key(now: int) -> bool:
	var w := week_of(now)
	if not active(now) or key_week == w:
		return false
	key_week = w
	return true


## The frame of this calendar month: true the first time it is seen while active.
func month_frame(now: int) -> bool:
	if not active(now):
		return false
	var dt := Time.get_datetime_dict_from_unix_time(now)
	var key := "%04d-%02d" % [int(dt["year"]), int(dt["month"])]
	if months.has(key):
		return false
	months[key] = true
	return true


func to_dict() -> Dictionary:
	return {"until": until, "trial_used": trial_used, "daily_day": daily_day, "key_week": key_week, "months": months.keys()}


func load_dict(d: Dictionary) -> void:
	until = int(d.get("until", 0))
	trial_used = bool(d.get("trial_used", false))
	daily_day = int(d.get("daily_day", -1))
	key_week = int(d.get("key_week", -1))
	months = {}
	for m in d.get("months", []):
		months[String(m)] = true
