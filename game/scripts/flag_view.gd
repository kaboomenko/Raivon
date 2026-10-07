extends Control
## The realm's flag (10 §4.23): a banner whose field is split by one of 12 divisions in 2 colours, an emblem in its
## colour, and a frame (`cos_frame`). Drawn from vectors at any size — the HUD crest, the profile, the constructor.
## Pure yellow and gold are emblem-only colours, never the field (canon §2.2 п. 37: a flag must not read as a
## yellow map marker).

const DIVISIONS := ["solid", "fess", "pale", "tierce", "bend", "cross", "saltire", "pile", "bordure", "quarters", "chevron", "roundel"]
## 16 heraldic field colours.
const FIELD := [
	Color("1f4fbf"), Color("2e6bff"), Color("16a3c4"), Color("1c7a4a"), Color("4e9a2a"), Color("8a1c1c"),
	Color("c8332b"), Color("e06a1b"), Color("7a3fb0"), Color("b0407a"), Color("5a3a22"), Color("2a2d36"),
	Color("6b7280"), Color("f2f2f0"), Color("0d1b3a"), Color("3a5a40"),
]
## The emblem may also be gold or pure yellow.
const EMBLEM_EXTRA := [Color("e8b23a"), Color("ffd60a")]
const EMBLEMS := ["eagle", "star", "crown", "tower", "sword", "sun", "moon", "tree", "anchor", "hammer", "wheat", "key",
	"bolt", "mountain", "wave", "flame", "hexagon", "crystal", "arrow", "leaf", "bell", "gear", "axe", "horseshoe"]
## Premium emblems (canon §15.5): the `cos_flag_part` id -> drawing.
const PREMIUM := {"cos_flag_part_recruit_star": "recruit_star", "cos_flag_part_half_world": "half_world", "cos_flag_part_skyscraper": "skyscraper"}
## Frames: `cos_frame` id -> [outer, inner] colours; "" is the plain gold edge.
const FRAMES := {
	"": [Color("d9b45a"), Color("8a6a2a")],
	"cos_frame_recruit": [Color("6fa8dc"), Color("2e5f8a")],
	"cos_frame_season_1": [Color("1fb5ad"), Color("0e6d68")],
	"cos_frame_ice": [Color("dff4ff"), Color("7cc4e8")],
	"cos_frame_veteran": [Color("b0803a"), Color("5a3d18")],
	"cos_frame_empire": [Color("8e5bd0"), Color("e8b23a")],
	"cos_frame_ultra": [Color("3a8dff"), Color("f0f6ff")],
	"cos_frame_arena_legend": [Color("f08a24"), Color("ffe08a")],
	"cos_frame_patent_month": [Color("c8ccd4"), Color("3a8dff")],
}
const DEFAULT := {"div": "solid", "c1": 0, "c2": 13, "em": "eagle", "ec": 13, "frame": ""}

var flag: Dictionary = DEFAULT.duplicate()


func _init(f: Dictionary = {}) -> void:
	if not f.is_empty():
		flag = f
	mouse_filter = Control.MOUSE_FILTER_IGNORE


static func emblem_colors() -> Array:
	return FIELD + EMBLEM_EXTRA


static func field_color(i: int) -> Color:
	return FIELD[clampi(i, 0, FIELD.size() - 1)]


## A random flag from a seed (the FTUE presets and the «Случайно» die): two field colours that differ, an emblem
## colour that stands out from the first.
static func random_flag(seed_v: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_v
	var c1 := rng.randi_range(0, FIELD.size() - 1)
	var c2 := (c1 + rng.randi_range(3, FIELD.size() - 3)) % FIELD.size()
	var ecs := emblem_colors()
	var ec := rng.randi_range(0, ecs.size() - 1)
	while (ecs[ec] as Color).get_luminance() - field_color(c1).get_luminance() < 0.25 and field_color(c1).get_luminance() - (ecs[ec] as Color).get_luminance() < 0.25:
		ec = (ec + 1) % ecs.size()
	return {"div": DIVISIONS[rng.randi_range(0, DIVISIONS.size() - 1)], "c1": c1, "c2": c2,
		"em": EMBLEMS[rng.randi_range(0, EMBLEMS.size() - 1)], "ec": ec, "frame": ""}


## An AI state's flag (10 §4.23: AI states have flags too): its map colour as the field, the rest from a seed.
static func ai_flag(seed_key: String, map_color: Color) -> Dictionary:
	var f := random_flag(hash(seed_key))
	var best := 0
	var best_d := 1e9
	for i in FIELD.size():
		var c: Color = FIELD[i]
		var d := Vector3(c.r - map_color.r, c.g - map_color.g, c.b - map_color.b).length_squared()
		if d < best_d:
			best_d = d
			best = i
	f["c1"] = best
	if int(f["c2"]) == best:
		f["c2"] = 13 if best != 13 else 11
	var ecs := emblem_colors()
	if absf((ecs[int(f["ec"])] as Color).get_luminance() - field_color(best).get_luminance()) < 0.25:
		f["ec"] = 13 if field_color(best).get_luminance() < 0.5 else 11
	return f


func _shape(w: float, h: float) -> PackedVector2Array:
	return PackedVector2Array([Vector2(w * .08, 0), Vector2(w * .92, 0), Vector2(w * .92, h * .8), Vector2(w * .5, h * .98), Vector2(w * .08, h * .8)])


func _p(pts: Array, w: float, h: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for v in pts:
		out.append(Vector2(v[0] * w, v[1] * h))
	return out


func _circle(c: Vector2, r: float, n := 32) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in n:
		var a := TAU * i / n
		out.append(c + Vector2(cos(a), sin(a)) * r)
	return out


## The second colour's parts of a division, in unit coordinates.
func _division(div: String, w: float, h: float) -> Array:
	match div:
		"fess":
			return [_p([[0, .5], [1, .5], [1, 1], [0, 1]], w, h)]
		"pale":
			return [_p([[.5, 0], [1, 0], [1, 1], [.5, 1]], w, h)]
		"tierce":
			return [_p([[0, .33], [1, .33], [1, .62], [0, .62]], w, h)]
		"bend":
			return [_p([[1, 0], [1, 1], [0, 1]], w, h)]
		"cross":
			return [_p([[.42, 0], [.58, 0], [.58, 1], [.42, 1]], w, h), _p([[0, .32], [1, .32], [1, .48], [0, .48]], w, h)]
		"saltire":
			return [_p([[0, 0], [.13, 0], [1, .87], [1, 1], [.87, 1], [0, .13]], w, h), _p([[1, 0], [1, .13], [.13, 1], [0, 1], [0, .87], [.87, 0]], w, h)]
		"pile":
			return [_p([[0, 0], [1, 0], [.5, .78]], w, h)]
		"quarters":
			return [_p([[.5, 0], [1, 0], [1, .45], [.5, .45]], w, h), _p([[0, .45], [.5, .45], [.5, 1], [0, 1]], w, h)]
		"chevron":
			return [_p([[0, .7], [.5, .34], [1, .7], [1, .9], [.5, .54], [0, .9]], w, h)]
		"roundel":
			return [_circle(Vector2(w * .5, h * .42), minf(w, h) * .3)]
	return []


func _draw() -> void:
	var w := size.x
	var h := size.y
	var shape := _shape(w, h)
	var c1 := field_color(int(flag.get("c1", 0)))
	var c2 := field_color(int(flag.get("c2", 13)))
	var div := String(flag.get("div", "solid"))
	if div == "bordure":
		draw_colored_polygon(shape, c2)
		var inner := PackedVector2Array()
		var ctr := Vector2(w * .5, h * .45)
		for v in shape:
			inner.append(ctr + (v - ctr) * 0.8)
		draw_colored_polygon(inner, c1)
	else:
		draw_colored_polygon(shape, c1)
		for part in _division(div, w, h):
			for piece in Geometry2D.intersect_polygons(part, shape):
				draw_colored_polygon(piece, c2)
	var ecs := emblem_colors()
	var ec: Color = ecs[clampi(int(flag.get("ec", 13)), 0, ecs.size() - 1)]
	var em := String(flag.get("em", "eagle"))
	draw_emblem(self, String(PREMIUM.get(em, em)), Vector2(w * .5, h * .42), minf(w, h) * .3, ec)
	var fr: Array = FRAMES.get(String(flag.get("frame", "")), FRAMES[""])
	var ring := shape.duplicate()
	ring.append(shape[0])
	draw_polyline(ring, fr[0], maxf(2.0, w * 0.05), true)
	draw_polyline(ring, fr[1], maxf(1.0, w * 0.015), true)


## An emblem centred at `c`, about `s` in radius, on any canvas item (the constructor's buttons draw them too).
static func draw_emblem(ci: CanvasItem, em: String, c: Vector2, s: float, col: Color) -> void:
	var dark := col.darkened(0.45)
	match em:
		"eagle":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .5), c + Vector2(s * .15, -s * .1), c + Vector2(s * 1.0, -s * .55), c + Vector2(s * .7, s * .05), c + Vector2(s * .25, s * .2), c + Vector2(s * .12, s * .8), c + Vector2(-s * .12, s * .8), c + Vector2(-s * .25, s * .2), c + Vector2(-s * .7, s * .05), c + Vector2(-s * 1.0, -s * .55), c + Vector2(-s * .15, -s * .1)]), col)
		"star", "recruit_star":
			var pts := PackedVector2Array()
			for i in 10:
				var a := -PI / 2 + PI * i / 5
				pts.append(c + Vector2(cos(a), sin(a)) * (s * 0.85 if i % 2 == 0 else s * 0.36))
			ci.draw_colored_polygon(pts, col)
			if em == "recruit_star":
				ci.draw_arc(c, s * 1.0, 0, TAU, 40, col, s * 0.1, true)
		"crown":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(-s * .8, s * .5), c + Vector2(-s * .8, -s * .35), c + Vector2(-s * .4, s * .05), c + Vector2(0, -s * .6), c + Vector2(s * .4, s * .05), c + Vector2(s * .8, -s * .35), c + Vector2(s * .8, s * .5)]), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .8, s * .5), Vector2(s * 1.6, s * .22)), dark)
		"tower":
			ci.draw_rect(Rect2(c + Vector2(-s * .45, -s * .35), Vector2(s * .9, s * 1.15)), col)
			for i in 3:
				ci.draw_rect(Rect2(c + Vector2(-s * .55 + i * s * .4, -s * .65), Vector2(s * .3, s * .32)), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .15, s * .35), Vector2(s * .3, s * .45)), dark)
		"sword":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .95), c + Vector2(s * .13, -s * .7), c + Vector2(s * .13, s * .35), c + Vector2(-s * .13, s * .35), c + Vector2(-s * .13, -s * .7)]), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .5, s * .35), Vector2(s, s * .14)), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .08, s * .49), Vector2(s * .16, s * .4)), dark)
		"sun":
			ci.draw_circle(c, s * .42, col, true, -1.0, true)
			for i in 12:
				var a := TAU * i / 12
				ci.draw_line(c + Vector2(cos(a), sin(a)) * s * .55, c + Vector2(cos(a), sin(a)) * s * .9, col, s * .12, true)
		"moon":
			var outer := PackedVector2Array()
			var inner := PackedVector2Array()
			for i in 32:
				var a := TAU * i / 32
				outer.append(c + Vector2(cos(a), sin(a)) * s * .75)
				inner.append(c + Vector2(s * .35, -s * .12) + Vector2(cos(a), sin(a)) * s * .6)
			for piece in Geometry2D.clip_polygons(outer, inner):
				ci.draw_colored_polygon(piece, col)
		"tree":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .9), c + Vector2(s * .7, s * .35), c + Vector2(-s * .7, s * .35)]), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .12, s * .35), Vector2(s * .24, s * .5)), dark)
		"anchor":
			ci.draw_line(c + Vector2(0, -s * .7), c + Vector2(0, s * .7), col, s * .16, true)
			ci.draw_line(c + Vector2(-s * .4, -s * .4), c + Vector2(s * .4, -s * .4), col, s * .14, true)
			ci.draw_arc(c + Vector2(0, s * .1), s * .62, 0.15, PI - 0.15, 24, col, s * .16, true)
			ci.draw_arc(c + Vector2(0, -s * .82), s * .16, 0, TAU, 16, col, s * .1, true)
		"hammer":
			ci.draw_rect(Rect2(c + Vector2(-s * .1, -s * .3), Vector2(s * .2, s * 1.1)), dark.lerp(col, 0.5))
			ci.draw_rect(Rect2(c + Vector2(-s * .6, -s * .75), Vector2(s * 1.2, s * .45)), col)
		"wheat":
			ci.draw_line(c + Vector2(0, s * .9), c + Vector2(0, -s * .8), col, s * .08, true)
			for i in 5:
				var y := -s * .7 + i * s * .3
				ci.draw_colored_polygon(_leaf(c + Vector2(-s * .18, y), s * .22, -0.6), col)
				ci.draw_colored_polygon(_leaf(c + Vector2(s * .18, y), s * .22, 0.6), col)
		"key":
			ci.draw_arc(c + Vector2(0, -s * .45), s * .3, 0, TAU, 24, col, s * .14, true)
			ci.draw_line(c + Vector2(0, -s * .15), c + Vector2(0, s * .85), col, s * .14, true)
			ci.draw_line(c + Vector2(0, s * .55), c + Vector2(s * .3, s * .55), col, s * .12, true)
			ci.draw_line(c + Vector2(0, s * .8), c + Vector2(s * .3, s * .8), col, s * .12, true)
		"bolt":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(s * .15, -s * .95), c + Vector2(-s * .45, s * .1), c + Vector2(-s * .02, s * .1), c + Vector2(-s * .2, s * .95), c + Vector2(s * .45, -s * .15), c + Vector2(s * .05, -s * .15)]), col)
		"mountain":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(-s * .95, s * .6), c + Vector2(-s * .25, -s * .7), c + Vector2(s * .1, -s * .05), c + Vector2(s * .4, -s * .45), c + Vector2(s * .95, s * .6)]), col)
		"wave":
			for k in 3:
				var pts := PackedVector2Array()
				for i in 25:
					var x := -s * .9 + i * s * 1.8 / 24
					pts.append(c + Vector2(x, -s * .45 + k * s * .45 + sin(i * 0.8) * s * .12))
				ci.draw_polyline(pts, col, s * .14, true)
		"flame":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .95), c + Vector2(s * .3, -s * .35), c + Vector2(s * .55, -s * .5), c + Vector2(s * .6, s * .2), c + Vector2(s * .3, s * .75), c + Vector2(-s * .3, s * .75), c + Vector2(-s * .6, s * .2), c + Vector2(-s * .35, -s * .3), c + Vector2(-s * .15, -s * .1)]), col)
		"hexagon":
			var hx := PackedVector2Array()
			for i in 6:
				var a := PI / 6 + TAU * i / 6
				hx.append(c + Vector2(cos(a), sin(a)) * s * .8)
			ci.draw_colored_polygon(hx, col)
			var hi := PackedVector2Array()
			for i in 6:
				var a := PI / 6 + TAU * i / 6
				hi.append(c + Vector2(cos(a), sin(a)) * s * .45)
			ci.draw_colored_polygon(hi, dark)
		"crystal":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .95), c + Vector2(s * .55, -s * .2), c + Vector2(0, s * .95), c + Vector2(-s * .55, -s * .2)]), col)
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s * .95), c + Vector2(s * .2, -s * .2), c + Vector2(0, s * .95), c + Vector2(-s * .2, -s * .2)]), col.lightened(0.35))
		"arrow":
			ci.draw_line(c + Vector2(-s * .6, s * .6), c + Vector2(s * .4, -s * .4), col, s * .14, true)
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(s * .75, -s * .75), c + Vector2(s * .15, -s * .55), c + Vector2(s * .55, -s * .15)]), col)
		"leaf":
			ci.draw_colored_polygon(_leaf(c, s * .9, 0.0), col)
			ci.draw_line(c + Vector2(0, s * .85), c + Vector2(0, -s * .6), dark, s * .07, true)
		"bell":
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(-s * .2, -s * .7), c + Vector2(s * .2, -s * .7), c + Vector2(s * .45, -s * .1), c + Vector2(s * .7, s * .5), c + Vector2(-s * .7, s * .5), c + Vector2(-s * .45, -s * .1)]), col)
			ci.draw_circle(c + Vector2(0, s * .65), s * .16, col, true, -1.0, true)
		"gear":
			ci.draw_circle(c, s * .58, col, true, -1.0, true)
			for i in 8:
				var a := TAU * i / 8
				ci.draw_line(c + Vector2(cos(a), sin(a)) * s * .5, c + Vector2(cos(a), sin(a)) * s * .85, col, s * .24)
			ci.draw_circle(c, s * .22, dark, true, -1.0, true)
		"axe":
			ci.draw_line(c + Vector2(-s * .45, s * .8), c + Vector2(s * .3, -s * .7), dark.lerp(col, 0.5), s * .12, true)
			ci.draw_colored_polygon(PackedVector2Array([c + Vector2(s * .05, -s * .55), c + Vector2(s * .75, -s * .85), c + Vector2(s * .85, -s * .05), c + Vector2(s * .3, -s * .1)]), col)
		"horseshoe":
			ci.draw_arc(c + Vector2(0, -s * .05), s * .6, PI * 0.85, PI * 2.15, 28, col, s * .24, true)
		"half_world":
			ci.draw_circle(c, s * .8, col, true, -1.0, true)
			var half := PackedVector2Array([c + Vector2(0, -s * .8)])
			for i in 17:
				var a := -PI / 2 + PI * i / 16
				half.append(c + Vector2(cos(a), sin(a)) * s * .8)
			ci.draw_colored_polygon(half, dark)
			ci.draw_arc(c, s * .8, 0, TAU, 40, col.lightened(0.3), s * .06, true)
			ci.draw_line(c + Vector2(-s * .8, 0), c + Vector2(s * .8, 0), col.lightened(0.3), s * .05, true)
		"skyscraper":
			ci.draw_rect(Rect2(c + Vector2(-s * .3, -s * .6), Vector2(s * .6, s * 1.45)), col)
			ci.draw_rect(Rect2(c + Vector2(-s * .15, -s * .85), Vector2(s * .3, s * .3)), col)
			ci.draw_line(c + Vector2(0, -s * .85), c + Vector2(0, -s * 1.05), col, s * .06)
			for r in 5:
				for k in 2:
					ci.draw_rect(Rect2(c + Vector2(-s * .2 + k * s * .24, -s * .45 + r * s * .26), Vector2(s * .14, s * .14)), dark)


static func _leaf(c: Vector2, s: float, tilt: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in 17:
		var t := float(i) / 16.0
		var y := lerpf(-1.0, 1.0, t)
		pts.append(c + Vector2(sin(t * PI) * s * 0.42, y * s).rotated(tilt))
	for i in range(15, 0, -1):
		var t := float(i) / 16.0
		var y := lerpf(-1.0, 1.0, t)
		pts.append(c + Vector2(-sin(t * PI) * s * 0.42, y * s).rotated(tilt))
	return pts
