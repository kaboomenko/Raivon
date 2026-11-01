extends RefCounted
## Login calendar (canon §14.5, 08 §8.8): a soft streak — a calendar day is credited on the first visit of a game
## day (the 04:00 local reset, local_day below), a missed day pauses it and never resets it. The credited day's reward waits until taken
## (a new day is not credited while it waits). Cycle 1 «Новобранец» is the 28-day table of 08 §8.8.2; then cycle 2+
## «Державный календарь» (08 §8.8.3) repeats. `ad_daily_double` doubles the day's reward except on key days.
## Deterministic; the caller pays the rewards out.

const DAY := 86400
const REFRESH_SEC := 4 * 3600
const LENGTH := 28

## Each day: [rewards, ×2 allowed]. A reward is [kind, …]: res h · crate n · raivite n · speed h count · builder ·
## cmd id (the unlock shards) · shards id n · shards_pick n (the least advanced common/rare commander) ·
## shards_choice n (the player picks a common/rare commander) · cosmetic id · season_cosmetic (a not yet owned rare
## frame or emote).
const CYCLE_1 := [
	[[["res", 2], ["crate", 1]], true],
	[[["builder"]], false],
	[[["raivite", 30]], true],
	[[["cmd", "cmd_vega"]], false],
	[[["speed", 1, 2]], true],
	[[["crate", 2]], true],
	[[["cmd", "cmd_irma"]], false],
	[[["res", 4]], true],
	[[["raivite", 40]], true],
	[[["speed", 3, 1]], true],
	[[["shards", "cmd_vega", 10]], true],
	[[["cosmetic", "cos_flag_part_recruit_star"]], false],
	[[["res", 6]], true],
	[[["raivite", 300]], false],
	[[["crate", 3]], true],
	[[["speed", 3, 2]], true],
	[[["shards", "cmd_irma", 10]], true],
	[[["res", 8]], true],
	[[["raivite", 50]], true],
	[[["cosmetic", "cos_frame_recruit"]], false],
	[[["cosmetic", "cos_border_ink_flame"]], false],
	[[["speed", 8, 1]], true],
	[[["crate", 3]], true],
	[[["raivite", 60]], true],
	[[["res", 12]], true],
	[[["shards_choice", 15]], true],
	[[["cosmetic", "cos_emote_drumroll"]], false],
	[[["shards", "cmd_rai", 20]], false],
]
## Cycle 2+: the week pattern (days 1–7 repeat; day 28 replaces the 4th week's 7th day).
const WEEK_2 := [
	[[["res", 4]], true],
	[[["crate", 1]], true],
	[[["raivite", 20]], true],
	[[["speed", 1, 1]], true],
	[[["shards_pick", 5]], true],
	[[["speed", 3, 1]], true],
	[[["raivite", 10], ["crate", 1]], true],
]
const DAY_28 := [[["season_cosmetic"]], false]

var credited := 0        # calendar days credited in total (the next reward is day `credited`)
var last_day := -1       # the game day of the last credit
var pending := false     # the credited day's reward waits to be taken
var choice := 0          # shards taken but not yet given: the player still picks the commander


## ---- the game day (one clock for the calendar, the orders, the patent, the weekly tasks and the rewarded caps)
## The daily reset is 04:00 device-local time (canon 00 §13 line 1165, §16 line 1626; 08 §8.8.4): `bias_min` is the
## device's UTC offset in minutes (Time.get_time_zone_from_system().bias, east of Greenwich positive) as main keeps it
## in the save, adopted through adopt_bias — at most once per 7 days, so a trip or a zone trick cannot roll days (the
## server's check stays in the backlog). Playtest 2 (Q3): the reset was 04:00 UTC — the evening before in New York,
## 06:00/07:00 in Kyiv — while the UI said «после 04:00».
static var bias_min := 0
const TZ_HOLD_SEC := 7 * DAY
const WEEK := 7 * DAY
const MONDAY := 1791172800  # 2026-10-05 04:00 UTC, a Monday: a week starts on Monday 04:00 local (the bias applied)


## The local game day of unix time `now` (the day number changes at 04:00 local).
static func local_day(now: int) -> int:
	return int(floor(float(now + bias_min * 60 - REFRESH_SEC) / DAY))


static func game_day(now: int) -> int:
	return local_day(now)


## Unix time of the next 04:00 local after `now`.
static func next_reset(now: int) -> int:
	return (local_day(now) + 1) * DAY + REFRESH_SEC - bias_min * 60


## The local week of `now` (it changes on Monday 04:00 local) and the unix time it ends.
static func local_week(now: int) -> int:
	return int(floor(float(now + bias_min * 60 - MONDAY) / WEEK))


static func week_end(now: int) -> int:
	return MONDAY + (local_week(now) + 1) * WEEK - bias_min * 60


## The offset the game counts days by: [bias, since] from the saved pair and the device's offset now. The first time
## (a fresh install, a save from before it was kept: `since` 0) the device's is taken at once; later a different one
## only once the saved one has held TZ_HOLD_SEC (08 §8.8.4).
static func adopt_bias(saved: int, since: int, device: int, now: int) -> Array:
	if since <= 0:
		return [device, now]
	if device != saved and now - since >= TZ_HOLD_SEC:
		return [device, now]
	return [saved, since]


## A day (or week) number the clock gives now counts as one already seen when it is the last one seen or lies at most
## `slack` behind it: a zone step west turns the number back (at most 26 h: −12…+14), which must not credit, roll or
## pay that day a second time. A clock set further back is the device's own business (server time: backlog).
static func seen(d: int, last: int, slack := 2) -> bool:
	return d <= last and last - d <= slack


## Cycle number (1-based) and day in the cycle (1..28) of calendar day n (1-based).
static func cycle_of(n: int) -> int:
	return (n - 1) / LENGTH + 1


static func day_in_cycle(n: int) -> int:
	return (n - 1) % LENGTH + 1


static func entry(n: int) -> Array:
	var d := day_in_cycle(n)
	if cycle_of(n) == 1:
		return CYCLE_1[d - 1]
	if d == LENGTH:
		return DAY_28
	return WEEK_2[(d - 1) % 7]


## Credits a new calendar day on the first visit of a game day. True when a reward became ready.
func visit(now: int) -> bool:
	var d := local_day(now)
	if seen(d, last_day):
		return false
	last_day = d
	if pending:
		return false  # the day goes to the waiting reward — days don't pile up (08 §8.8.1)
	credited += 1
	pending = true
	return true


## The waiting day's rewards ([] when nothing waits); marks it taken.
func claim() -> Array:
	if not pending:
		return []
	pending = false
	return (entry(credited)[0] as Array).duplicate(true)


func can_double() -> bool:
	return pending and bool(entry(credited)[1])


func to_dict() -> Dictionary:
	return {"credited": credited, "last_day": last_day, "pending": pending, "choice": choice}


func load_dict(d: Dictionary) -> void:
	credited = int(d.get("credited", 0))
	last_day = int(d.get("last_day", -1))
	pending = bool(d.get("pending", false))
	choice = int(d.get("choice", 0))
