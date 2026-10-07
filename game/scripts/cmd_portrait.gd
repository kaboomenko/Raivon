extends Control
## A commander's bust drawn in 2D from the portrait kit's parameters (04 §15.3–15.4): rarity plate, uniform, head
## shape, hair, facial hair, headgear and the one detail each has. Stands in for the bpy portrait renders; a locked
## commander is a silhouette.

const RARITY := {
	"common": Color("9aa3ad"), "rare": Color("1fb5ad"), "epic": Color("8e5bd0"), "legendary": Color("f08a24"),
}
## skin, head [w, h], hair color, hair style, facial hair, headgear, uniform, accent
const LOOK := {
	"cmd_bram": [Color("e8b48e"), [0.36, 0.40], Color("b5562b"), "short", "beard", "", Color("d9c9a3"), Color("7a4e2d")],
	"cmd_lira": [Color("f0c4a0"), [0.31, 0.40], Color("5a3420"), "braid", "", "kerchief", Color("3e9b5a"), Color("f2f2f2")],
	"cmd_olm": [Color("e2b08c"), [0.28, 0.43], Color("c8c8c8"), "sides", "", "goggles", Color("7a4e2d"), Color("c9a24a")],
	"cmd_vik": [Color("f2c8a4"), [0.29, 0.42], Color("e3c46a"), "messy", "", "hood", Color("4e6b3a"), Color("6b4a2a")],
	"cmd_vega": [Color("e9bd99"), [0.30, 0.41], Color("2e2a2a"), "bob", "", "glasses", Color("44484f"), Color("c8ccd4")],
	"cmd_kort": [Color("dca582"), [0.38, 0.41], Color("d8d8d8"), "bald", "mustache_long", "", Color("5d6236"), Color("b0803a")],
	"cmd_seir": [Color("c98d68"), [0.33, 0.40], Color("cfcfcf"), "short", "beard_short", "tricorn", Color("1f6f8b"), Color("f2f2f2")],
	"cmd_frey": [Color("e4b592"), [0.35, 0.39], Color("6b5a48"), "buzz", "", "", Color("3b5a44"), Color("9aa3ad")],
	"cmd_irma": [Color("f1c9aa"), [0.30, 0.41], Color("efe9dc"), "ponytail", "", "goggles", Color("26272b"), Color("f08a24")],
	"cmd_hawk": [Color("e6b996"), [0.31, 0.41], Color("4a3424"), "short", "mustache", "flight", Color("7a5133"), Color("6fa8dc")],
	"cmd_vance": [Color("f0cdb2"), [0.30, 0.41], Color("d9d9de"), "updo", "", "brooch", Color("8e5bd0"), Color("e8e8f0")],
	"cmd_rai": [Color("e7c0a0"), [0.33, 0.42], Color("f0f0f0"), "long", "beard_long", "circlet", Color("eef1f6"), Color("3a8dff")],
}

var cmd := ""
var rarity := "common"
var locked := false


func _init(id: String = "", r: String = "common", is_locked := false) -> void:
	cmd = id
	rarity = r
	locked = is_locked
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _ellipse(c: Vector2, rx: float, ry: float, from := 0.0, to := TAU, n := 28) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n + 1:
		var a := lerpf(from, to, float(i) / n)
		pts.append(c + Vector2(cos(a) * rx, sin(a) * ry))
	return pts


## A filled shape with a thin antialiased outline a shade darker (the polygon fill itself has hard edges).
func _fill(pts: PackedVector2Array, col: Color) -> void:
	if pts.size() < 3:
		return
	draw_colored_polygon(pts, col)
	var ring := pts.duplicate()
	ring.append(pts[0])
	draw_polyline(ring, col.darkened(0.35), maxf(1.2, minf(size.x, size.y) * 0.007), true)


func _draw() -> void:
	var w := size.x
	var h := size.y
	var u := minf(w, h)
	var rc: Color = RARITY.get(rarity, RARITY["common"])
	# the plate: a vertical gradient of the rarity color
	var top := rc.darkened(0.15) if not locked else Color(0.16, 0.18, 0.24)
	var bot := rc.darkened(0.6) if not locked else Color(0.08, 0.09, 0.13)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)]),
		PackedColorArray([top, top, bot, bot]))
	# a soft halo behind the head
	_fill(_ellipse(Vector2(w * 0.5, h * 0.42), u * 0.36, u * 0.36), Color(1, 1, 1, 0.08 if not locked else 0.03))
	var look: Array = LOOK.get(cmd, LOOK["cmd_bram"])
	var shade := Color(0.05, 0.06, 0.09, 0.95)
	var skin: Color = shade if locked else look[0]
	var hair: Color = shade if locked else look[2]
	var uni: Color = shade if locked else look[6]
	var acc: Color = shade if locked else look[7]
	var hw: float = float(look[1][0]) * u * 0.5
	var hh: float = float(look[1][1]) * u * 0.5
	var hc := Vector2(w * 0.5, h * 0.44)
	var style: String = look[3]
	var gear: String = look[5]
	# hair behind the head (long styles)
	if style in ["braid", "long", "ponytail"]:
		_fill(_ellipse(hc + Vector2(0, hh * 0.35), hw * 1.12, hh * 1.15), hair.darkened(0.12))
	if gear == "hood":
		_fill(_ellipse(hc + Vector2(0, -hh * 0.05), hw * 1.38, hh * 1.3), uni.darkened(0.15))
	# shoulders and the uniform
	var sy := h * 0.78
	var body := PackedVector2Array([Vector2(w * 0.08, h), Vector2(w * 0.14, sy + u * 0.03), Vector2(w * 0.32, sy - u * 0.06),
		Vector2(w * 0.68, sy - u * 0.06), Vector2(w * 0.86, sy + u * 0.03), Vector2(w * 0.92, h)])
	_fill(body, uni)
	# the collar: a V of the accent (scarf, shirt, cloak lining)
	_fill(PackedVector2Array([Vector2(w * 0.4, sy - u * 0.06), Vector2(w * 0.5, sy + u * 0.1), Vector2(w * 0.6, sy - u * 0.06)]),
		acc if cmd in ["cmd_hawk", "cmd_lira", "cmd_seir", "cmd_rai", "cmd_vance"] else uni.lightened(0.18))
	if not locked and cmd in ["cmd_vega", "cmd_frey", "cmd_kort", "cmd_vance"]:
		# epaulettes / pauldrons
		for sx in [-1.0, 1.0]:
			_fill(_ellipse(Vector2(w * 0.5 + sx * w * 0.27, sy - u * 0.02), u * 0.085, u * 0.035), acc)
	if not locked and cmd == "cmd_kort":
		_fill(_ellipse(Vector2(w * 0.5, sy - u * 0.04), u * 0.24, u * 0.06), Color("8a6a48"))  # fur collar
	if not locked and cmd == "cmd_olm":
		draw_line(Vector2(w * 0.38, sy - u * 0.04), Vector2(w * 0.4, h), Color("5a3820"), u * 0.02, true)  # apron straps
		draw_line(Vector2(w * 0.62, sy - u * 0.04), Vector2(w * 0.6, h), Color("5a3820"), u * 0.02, true)
	# neck
	draw_rect(Rect2(hc.x - hw * 0.42, hc.y + hh * 0.6, hw * 0.84, hh * 0.75), skin.darkened(0.12))
	# the head
	_fill(_ellipse(hc, hw, hh), skin)
	# ears
	for sx in [-1.0, 1.0]:
		_fill(_ellipse(hc + Vector2(sx * hw * 0.98, hh * 0.05), hw * 0.14, hh * 0.18), skin.darkened(0.08))
	if not locked and cmd == "cmd_seir":
		_fill(_ellipse(hc + Vector2(hw * 1.0, hh * 0.25), u * 0.012, u * 0.012, true), Color("e8c45a"))  # earring
	# hair on top
	match style:
		"short", "messy":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.35), hw * 1.04, hh * 0.72, PI, TAU), hair)
			if style == "messy":
				for i in 5:
					var x := hc.x - hw * 0.8 + i * hw * 0.4
					_fill(PackedVector2Array([Vector2(x - hw * 0.18, hc.y - hh * 0.55), Vector2(x, hc.y - hh * 0.25), Vector2(x + hw * 0.2, hc.y - hh * 0.6)]), hair)
		"braid", "long", "ponytail", "updo", "bob":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.3), hw * 1.08, hh * 0.78, PI, TAU), hair)
			if style == "bob":
				for sx in [-1.0, 1.0]:
					_fill(_ellipse(hc + Vector2(sx * hw * 0.88, 0), hw * 0.26, hh * 0.55), hair)
				if not locked:
					draw_line(hc + Vector2(-hw * 0.3, -hh * 0.98), hc + Vector2(-hw * 0.1, -hh * 0.55), Color("bfbfbf"), u * 0.018, true)
			if style == "updo":
				_fill(_ellipse(hc + Vector2(0, -hh * 1.12), hw * 0.55, hh * 0.38), hair)
			if style == "ponytail":
				_fill(PackedVector2Array([hc + Vector2(hw * 0.6, -hh * 0.8), hc + Vector2(hw * 1.5, -hh * 0.2), hc + Vector2(hw * 1.25, hh * 0.9), hc + Vector2(hw * 0.85, -hh * 0.3)]), hair)
		"sides":
			for sx in [-1.0, 1.0]:
				_fill(_ellipse(hc + Vector2(sx * hw * 0.86, hh * 0.05), hw * 0.2, hh * 0.42), hair)
		"buzz":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.38), hw * 1.0, hh * 0.66, PI, TAU), hair.lightened(0.1))
	if style == "braid":
		for i in 4:
			_fill(_ellipse(hc + Vector2(hw * 0.95, hh * (0.45 + i * 0.32)), hw * 0.17, hh * 0.17), hair.darkened(0.05))
	# eyes, brows, mouth
	var eye_y := hc.y - hh * 0.02
	var eye_col := Color("3a8dff") if cmd == "cmd_rai" and not locked else Color(0.12, 0.1, 0.1)
	for sx in [-1.0, 1.0]:
		var ec := Vector2(hc.x + sx * hw * 0.38, eye_y)
		if not locked:
			_fill(_ellipse(ec, hw * 0.13, hh * 0.07), Color(0.97, 0.97, 0.97))
			_fill(_ellipse(ec, hw * 0.07, hh * 0.065), eye_col)
			if cmd == "cmd_rai":
				_fill(_ellipse(ec, hw * 0.2, hh * 0.13), Color(0.35, 0.6, 1.0, 0.25))
			draw_line(ec + Vector2(-hw * 0.17, -hh * 0.16), ec + Vector2(hw * 0.17, -hh * (0.2 if sx > 0 and cmd == "cmd_vega" else 0.14)), hair.darkened(0.25), u * 0.016, true)
	if not locked:
		draw_line(Vector2(hc.x, eye_y + hh * 0.05), Vector2(hc.x - hw * 0.06, eye_y + hh * 0.3), skin.darkened(0.25), u * 0.012, true)
		var smile := 0.06 if cmd in ["cmd_hawk", "cmd_vik", "cmd_vance"] else 0.0
		draw_line(Vector2(hc.x - hw * 0.25, hc.y + hh * 0.5), Vector2(hc.x + hw * 0.25, hc.y + hh * (0.5 - smile)), Color(0.55, 0.25, 0.22), u * 0.014, true)
		if cmd == "cmd_lira":
			for sx in [-1.0, 1.0]:
				for i in 3:
					draw_circle(hc + Vector2(sx * hw * (0.28 + i * 0.13), hh * (0.2 + (i % 2) * 0.07)), u * 0.004, Color(0.78, 0.5, 0.36, 0.8), true, -1.0, true)  # freckles
		if cmd in ["cmd_bram", "cmd_frey"]:
			draw_line(hc + Vector2(hw * 0.45, hh * 0.15), hc + Vector2(hw * 0.65, hh * 0.45), Color(0.75, 0.45, 0.4), u * 0.012, true)  # scar
	# facial hair
	match String(look[4]):
		"beard", "beard_long", "beard_short":
			var ln := 1.0 if look[4] == "beard" else (1.5 if look[4] == "beard_long" else 0.65)
			_fill(_ellipse(hc + Vector2(0, hh * 0.38), hw * 0.95, hh * 0.62 * ln, 0.0, PI), hair)
			_fill(_ellipse(hc + Vector2(0, hh * 0.5), hw * 0.22, hh * 0.08), Color(0.45, 0.2, 0.18) if not locked else shade)
		"mustache", "mustache_long":
			var lw := 0.55 if look[4] == "mustache" else 0.85
			var mh := u * (0.014 if look[4] == "mustache" else 0.028)
			draw_line(Vector2(hc.x - hw * lw, hc.y + hh * (0.42 if lw < 0.6 else 0.6)), Vector2(hc.x, hc.y + hh * 0.36), hair, mh, true)
			draw_line(Vector2(hc.x + hw * lw, hc.y + hh * (0.42 if lw < 0.6 else 0.6)), Vector2(hc.x, hc.y + hh * 0.36), hair, mh, true)
	# headgear and details
	match gear:
		"kerchief":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.42), hw * 1.08, hh * 0.66, PI, TAU), acc)
		"goggles":
			for sx in [-1.0, 1.0]:
				_fill(_ellipse(hc + Vector2(sx * hw * 0.36, -hh * 0.62), hw * 0.24, hh * 0.15), Color("3a3a3a") if not locked else shade)
				_fill(_ellipse(hc + Vector2(sx * hw * 0.36, -hh * 0.62), hw * 0.16, hh * 0.1), Color("8fc4d8") if not locked else shade)
			draw_line(hc + Vector2(-hw, -hh * 0.62), hc + Vector2(hw, -hh * 0.62), Color("3a3a3a"), u * 0.012, true)
		"hood":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.42), hw * 1.25, hh * 0.78, PI, TAU), uni.darkened(0.08))
		"glasses":
			for sx in [-1.0, 1.0]:
				draw_arc(Vector2(hc.x + sx * hw * 0.38, eye_y), hw * 0.2, 0, TAU, 20, Color("c8ccd4"), u * 0.01, true)
			draw_line(Vector2(hc.x - hw * 0.18, eye_y), Vector2(hc.x + hw * 0.18, eye_y), Color("c8ccd4"), u * 0.01, true)
		"tricorn":
			_fill(PackedVector2Array([hc + Vector2(-hw * 1.45, -hh * 0.55), hc + Vector2(0, -hh * 1.45), hc + Vector2(hw * 1.45, -hh * 0.55), hc + Vector2(0, -hh * 0.75)]), Color("1d2533") if not locked else shade)
			draw_line(hc + Vector2(-hw * 1.4, -hh * 0.57), hc + Vector2(hw * 1.4, -hh * 0.57), acc, u * 0.012, true)
		"flight":
			_fill(_ellipse(hc + Vector2(0, -hh * 0.3), hw * 1.12, hh * 0.86, PI, TAU), Color("6b4428") if not locked else shade)
			for sx in [-1.0, 1.0]:
				_fill(_ellipse(hc + Vector2(sx * hw * 0.38, -hh * 0.72), hw * 0.26, hh * 0.17), Color("2a2a2a") if not locked else shade)
				_fill(_ellipse(hc + Vector2(sx * hw * 0.38, -hh * 0.72), hw * 0.17, hh * 0.11), acc)
		"brooch":
			_fill(_ellipse(Vector2(w * 0.5, sy + u * 0.07), u * 0.025, u * 0.025), Color("f4f1ea") if not locked else shade)
		"circlet":
			draw_arc(hc + Vector2(0, -hh * 0.1), hw * 1.02, PI * 1.08, PI * 1.92, 24, Color("d0d6de") if not locked else shade, u * 0.022, true)
			_fill(_ellipse(hc + Vector2(0, -hh * 0.98), u * 0.03, u * 0.036), acc)
			if not locked:
				_fill(_ellipse(hc + Vector2(0, -hh * 0.98), u * 0.06, u * 0.06), Color(0.35, 0.6, 1.0, 0.3))
	if not locked and cmd == "cmd_hawk":
		_fill(_ellipse(Vector2(w * 0.5, sy - u * 0.01), u * 0.17, u * 0.05), Color("f4f4f4"))  # white scarf
	if locked:
		var f := get_theme_default_font()
		draw_string(f, Vector2(0, h * 0.5 + u * 0.08), "?", HORIZONTAL_ALIGNMENT_CENTER, w, int(u * 0.28), Color(0.62, 0.68, 0.78, 0.9))
	# the rarity frame
	draw_rect(Rect2(Vector2.ZERO, size), rc if not locked else rc.darkened(0.5), false, maxf(3.0, u * 0.025))
