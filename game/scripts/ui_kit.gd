extends RefCounted
## Raivon UI kit — the design tokens and components of docs/ui_style.md (§3 tokens, §4 components).
## Every screen uses it as `const Kit := preload("res://scripts/ui_kit.gd")` (no class_name, like the rest of
## the project). This is the only UI file where Color literals are allowed (tools/ui_lint.py R1).
## All numbers are in the 941×1672 design space.

const SELF := preload("res://scripts/ui_kit.gd")
const L := preload("res://scripts/l10n.gd")
const FlagView := preload("res://scripts/flag_view.gd")

# ------------------------------------------------------------------ tokens: surfaces and ink (§3.2)

const INK := Color("1b2140")
const SLATE := Color("2e3f66")
const SLATE_LIP := Color("1d2843")
const SLATE_WELL := Color("17203a")
const SLATE_FILL := Color("3a5285")
const SLATE_HI := Color("4a5f94")
const CREAM := Color("fff4de")
const CREAM_LIP := Color("dcc290")
const CREAM_WELL := Color("f1e3c3")
const CREAM_ROW := Color("fffbf0")
const ROW_LIP := Color("e2cf9f")
const CREAM_DEEP := Color("d9c7a0")
const SKY_TOP := Color("8fcdf2")
const SKY_LOW := Color("e3f4fd")
const GRASS := Color("86c45e")
const BLUEPRINT := Color("3e7fc1")
const SEA_WELL := Color("2a6596")
const FULL := Color("8c5a1f")
const PREMIUM_WELL := Color("ffe7a6")  ## the War Pass's premium column: a gold-tinted well (§6 Военный пропуск)
const MAP_ROCK := Color("a9aebb")  ## minimap mountains (the land is in the states' colours, water shows the well)
const WILD := Color("977a4b")  ## the «Ничья» owner chip: a darker sand than the map's wild land, so its white text reads; warm, never the lock grey
const WHITE := Color(1, 1, 1)
const CLEAR := Color(0, 0, 0, 0)  ## "no colour" for an optional colour argument (a chip's fill, a badge's face)

# ------------------------------------------------------------------ tokens: text

const TEXT := Color(1, 1, 1)  ## light text on dark / colour, always with the INK outline
const SOFT := Color("c4cce4")  ## Nunito descriptions on slate, no outline
const POS := Color("8be04e")
const NEG := Color("ff7a6e")
const WARN := Color("ffc531")
const INK_TEXT := Color("1b2140")  ## text on paper
const SOFT_CREAM := Color("3a3f5c")
const MUTED_CREAM := Color("6e614b")
const POS_CREAM := Color("267a17")
const NEG_CREAM := Color("c23a2e")
const WARN_CREAM := Color("936204")
const LINK := Color("2266b8")

const RARITY := {"common": Color("a7afbc"), "rare": Color("3e9bf0"), "epic": Color("a65bf2"), "legendary": Color("ff9a1f")}

## Action roles: [face, lip]. Gloss = face.lerp(WHITE, 0.38). Meanings are fixed (§3.2): gold only for spending,
## lock only for «unavailable».
const ROLE := {
	"go": [Color("5cc93b"), Color("3a8f22")],
	"info": [Color("3e9bf0"), Color("2266b8")],
	"war": [Color("ef4b3f"), Color("a92a23")],
	"gold": [Color("ffc531"), Color("c98a0c")],
	"lock": [Color("a7afbc"), Color("6c7482")],
	"slate": [Color("3a5089"), Color("1d2843")],
	"energy": [Color("23c4d8"), Color("13839a")],
	"brass": [Color("e6b13e"), Color("9c6b1c")],
	"steel": [Color("b9c7d6"), Color("6a7c93")],
}

## The only font sizes (§3.3).
const SCALE: Array[int] = [22, 24, 26, 28, 30, 32, 36, 40, 44, 46, 60, 64]
## The only corner radii (circles: ≥ 40 or h/2).
const RADII: Array[int] = [0, 8, 14, 20, 24, 34]
const FIT_FLOOR := 20  ## legacy _fit floor; new screens stop at 22 (24 for regular text)
const SHADOW_A := 0.35
const DIM_A := 0.6
## The advisor's speech bubble (§3.4 table «Подсказка / пузырь»: R 24 / 30, OUT 4 / 5) — the one radius off RADII.
const R_BUBBLE := 30
const LOCK_MOD := Color(0.55, 0.57, 0.62)  ## a closed item's icon (§3.5)
## A control on the currency layer (above every dim) while the coach's spotlight shuts the screen (§4.12): about
## what INK α 0.6 makes of it.
const SHUT_MOD := Color(0.42, 0.45, 0.55)
## How far a finger may travel on the screen and still tap (≈ 7 dp): past it a press inside a scrolling row is a
## swipe, and a swipe never spends (§2: «иначе при прокрутке возможны случайные траты»).
const TAP_SLOP := 16.0


## Where a pointer event (in `c`'s local coordinates) is on the screen. A control inside a scroll moves under the
## finger, so only screen positions tell a swipe from a tap.
static func screen_pos(c: Control, e: InputEvent) -> Vector2:
	var p := Vector2.ZERO
	if e is InputEventMouse:
		p = (e as InputEventMouse).position
	elif e is InputEventScreenTouch:
		p = (e as InputEventScreenTouch).position
	elif e is InputEventScreenDrag:
		p = (e as InputEventScreenDrag).position
	return c.get_global_transform_with_canvas() * p


static func gloss(face: Color) -> Color:
	return face.lerp(WHITE, 0.38)


## A token at another alpha (INK α 0.55 for the top scrim, a transparent frame).
static func alpha(c: Color, a: float) -> Color:
	c.a = a
	return c


static func face_of(role: String) -> Color:
	return (ROLE.get(role, ROLE["info"]) as Array)[0]


static func lip_of(role: String) -> Color:
	return (ROLE.get(role, ROLE["info"]) as Array)[1]


# ------------------------------------------------------------------ fonts (§3.3)

const FONT_PATHS := {"d900": "res://assets/fonts/display_900.tres", "d800": "res://assets/fonts/display_800.tres",
	"b800": "res://assets/fonts/body_800.tres"}
static var _fonts := {}


## kind: d900 (Rubik 900: titles, buttons, numbers), d800 (Rubik 800: labels, chips), b800 (Nunito 800: body).
static func font(kind: String) -> Font:
	if not _fonts.has(kind):
		var p: String = FONT_PATHS.get(kind, FONT_PATHS["d900"])
		_fonts[kind] = load(p) if ResourceLoader.exists(p) else ThemeDB.fallback_font
	return _fonts[kind]


# ------------------------------------------------------------------ snapping

## The smallest scale size >= s (22..64).
static func snap_size(s: float) -> int:
	for v in SCALE:
		if v >= s - 0.01:
			return v
	return SCALE[-1]


static func snap_radius(r: float) -> int:
	if r < 4:
		return 0
	if r <= 16:
		return 14
	if r <= 22:
		return 20
	if r <= 28:
		return 24
	if r <= 40:
		return 34
	return int(r)


static func outline_for(size: int) -> int:
	return clampi(roundi(size / 7.0), 3, 8)


static func shadow_dy(size: int) -> int:
	return clampi(roundi(size / 14.0), 2, 5)


static func is_light(c: Color) -> bool:
	return c.get_luminance() >= 0.5


# ------------------------------------------------------------------ labels (§3.3 text recipe)

## A label styled by theme overrides (so call sites can recolour it and _fit can read its font).
static func label(text: String, size: int, color := TEXT, bold := true) -> Label:
	var l := Label.new()
	l.text = text
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	style_label(l, size, color, bold)
	l.add_child(KitText.new())  # its glyphs from the bake atlas once the text holds still
	return l


## Sizes from 22 up snap to the scale. A request under 22 comes from a legacy layout whose rows are spaced for
## small text (20 px card rows): it keeps its size until that screen is rebuilt on the kit (ui_lint R5 lists
## those call sites).
static func style_label(l: Label, size: int, color: Color, bold := true) -> void:
	var sz := snap_size(size) if size >= SCALE[0] - 1 else size
	l.add_theme_font_override("font", font(("d900" if sz >= 26 else "d800") if bold else "b800"))
	l.add_theme_font_size_override("font_size", sz)
	l.add_theme_color_override("font_color", color)
	ink_text(l, color, sz, bold)


## Outline + hard shadow for light text on dark / colour; none for dark text on paper.
static func ink_text(l: Control, color: Color, sz: int, bold := true) -> void:
	if is_light(color) and color.a > 0.3:
		if bold:
			var o := outline_for(sz)
			l.add_theme_color_override("font_outline_color", INK)
			l.add_theme_constant_override("outline_size", o)
			l.add_theme_color_override("font_shadow_color", INK)
			l.add_theme_constant_override("shadow_offset_x", 0)
			l.add_theme_constant_override("shadow_offset_y", shadow_dy(sz))
			l.add_theme_constant_override("shadow_outline_size", o)
		else:
			l.add_theme_constant_override("outline_size", 0)
			l.add_theme_color_override("font_shadow_color", Color(INK, 0.8))
			l.add_theme_constant_override("shadow_offset_x", 0)
			l.add_theme_constant_override("shadow_offset_y", 2)
			l.add_theme_constant_override("shadow_outline_size", 0)
	else:
		l.add_theme_constant_override("outline_size", 0)
		l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0))
		l.add_theme_constant_override("shadow_outline_size", 0)


## Width of a one-line text at a size, outline included.
static func text_w(text: String, size: int, kind := "d900", outlined := true) -> float:
	var w := font(kind).get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	return w + (2.0 * outline_for(size) if outlined else 0.0)


## The largest scale size <= base (then FIT_FLOOR) at which `text` fits `max_w`.
static func fit_size(text: String, base: int, max_w: float, kind := "d900", floor_ := FIT_FLOOR, outlined := true) -> int:
	for s in fit_steps(base, floor_):
		if text_w(text, s, kind, outlined) <= max_w:
			return s
	return floor_


## Steps a label's font down from `base` through the scale (to 20, or to `base` when a legacy call asks for less)
## until its one-line text fits `max_w`. When even the floor does not fit, the line is cut with an ellipsis inside
## `max_w` instead of running out of its panel (backs game_ui._fit / hud._fit).
static func fit_label(l: Label, base: int, max_w: float) -> void:
	var f := l.get_theme_font("font")
	var steps := fit_steps(base, mini(FIT_FLOOR, base))
	var s: int = steps[-1]
	var fits := false
	for v in steps:
		if f.get_string_size(l.text, HORIZONTAL_ALIGNMENT_LEFT, -1, v).x <= max_w:
			s = v
			fits = true
			break
	l.add_theme_font_size_override("font_size", s)
	if l.has_meta("kit_fit_cut"):  # an earlier, longer text was cut
		l.remove_meta("kit_fit_cut")
		l.clip_text = false
		l.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	if not fits and max_w > 0.0 and l.autowrap_mode == TextServer.AUTOWRAP_OFF:
		l.set_meta("kit_fit_cut", true)
		l.clip_text = true
		l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		l.size.x = max_w


## Scale sizes from snap_size(base) down to 22, then 20 and on down to `floor_` when it is lower (legacy
## call sites never go below the size they asked for).
static func fit_steps(base: int, floor_ := FIT_FLOOR) -> Array[int]:
	var out: Array[int] = []
	if base < SCALE[0] - 1:  # a legacy small size: from itself down to the floor
		for s in range(base, mini(base, floor_) - 1, -1):
			out.append(s)
		return out
	var top := snap_size(base)
	for i in range(SCALE.size() - 1, -1, -1):
		if SCALE[i] <= top and SCALE[i] >= floor_:
			out.append(SCALE[i])
	var below := mini(out[-1] if not out.is_empty() else top, SCALE[0]) - 1
	for s in range(mini(below, FIT_FLOOR), floor_ - 1, -1):
		out.append(s)
	if out.is_empty():
		out.append(floor_)
	return out


# ------------------------------------------------------------------ styles (§3.4)

## Opaque face, INK contour, hard shadow (shadow_size 1 + offset; never > 2), lip drawn by KitDecor.
static func style(face: Color, r := 20, out := 4, outline := INK, shadow := 6, lip := 0) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = face
	s.set_corner_radius_all(r)
	s.border_color = outline
	s.set_border_width_all(out)
	s.corner_detail = 10
	s.anti_aliasing = true
	if shadow > 0:
		s.shadow_color = Color(INK, SHADOW_A)
		s.shadow_size = 1
		s.shadow_offset = Vector2(0, shadow)
	s.set_meta("kit_lip", lip)
	s.set_meta("kit_face", face)
	s.set_meta("kit_lip_color", lip_color_of(face))
	s.set_meta("kit_kind", kind_of_face(face))
	return s


## The lip colour that belongs to a face.
static func lip_color_of(face: Color) -> Color:
	if face.is_equal_approx(SLATE):
		return SLATE_LIP
	if face.is_equal_approx(CREAM):
		return CREAM_LIP
	if face.is_equal_approx(CREAM_ROW):
		return ROW_LIP
	for k in ROLE:
		if face.is_equal_approx(ROLE[k][0]):
			return ROLE[k][1]
	return face.darkened(0.3)


## "slate" / "cream" surfaces get a top highlight line, "role" faces (buttons) a gloss band.
static func kind_of_face(face: Color) -> String:
	if face.is_equal_approx(SLATE):
		return "slate"
	if face.is_equal_approx(CREAM) or face.is_equal_approx(CREAM_ROW):
		return "cream"
	for k in ROLE:
		if face.is_equal_approx(ROLE[k][0]):
			return "role"
	return ""


## Backs the old `_style(bg, radius, border, bw)` of game_ui / hud: maps the legacy palette onto the kit.
static func legacy_style(bg: Color, radius := 14, border := INK, bw := 2) -> StyleBoxFlat:
	var r := snap_radius(radius)
	var out := 0 if bw <= 0 else (3 if bw <= 2 else 4)
	var near_white := bg.s < 0.15 and bg.v > 0.85
	if bg.a < 0.05:  # a frame only (the coach ring): transparent face, the given border
		var ring := style(Color(bg, 0.0), r, bw, border, 0, 0)
		ring.set_meta("kit_kind", "")
		return ring
	if near_white and bg.a < 0.5:
		if bg.a < 0.2:  # a bar track or an empty slot
			var t := style(SLATE_WELL, r, out, INK, 0, 0)
			t.set_meta("kit_track", true)
			t.set_meta("kit_kind", "")
			return t
		var strip := style(Color(1, 1, 1, maxf(bg.a, 0.35)), r, 0, INK, 0, 0)  # a progress strip / marker over a button
		strip.set_meta("kit_kind", "")
		return strip
	if bg.a < 0.5:  # a tinted row (selected / not) stays a tint
		var tl := _accent(border, bw, INK)
		var tint := style(bg, r, out, tl, 0, 0)
		tint.set_meta("kit_kind", "")
		if tl != INK:
			tint.set_meta("kit_accent", tl)
		return tint
	var face: Color
	var lip := 0
	var accent := false
	var lit := _literal_role(bg)
	if is_legacy_disabled(bg):
		face = face_of("lock")
		lip = 6
	elif near_white:
		face = WHITE
	elif lit != "":
		face = face_of(lit)
		lip = 6
	elif bg.get_luminance() < 0.2 or (bg.get_luminance() < 0.26 and (bg.s < 0.35 or (bg.h >= 0.5 and bg.h <= 0.75))):
		# every dark navy panel / card / status plate (a dark red or green stays a role colour)
		face = SLATE
		lip = 6
		accent = true
	elif bg.get_luminance() > 0.75 and bg.r >= bg.b and bg.s < 0.35:  # parchment, not a bright gold
		face = CREAM
	else:
		var role := role_of(bg)
		face = face_of(role)
		lip = 6
	var line := _accent(border, bw, INK) if accent else INK
	var s := style(face, r, (5 if bw >= 5 else 4) if line != INK else out, line, 4 if bw > 0 else 0, lip)
	if line != INK:
		s.set_meta("kit_accent", line)
	return s


## A legacy border that carries meaning (a selection, «today», a realm's colour) keeps its colour; any other
## border becomes INK.
static func _accent(border: Color, bw: int, fallback: Color) -> Color:
	var web_blue := border.h >= 0.55 and border.h <= 0.7 and border.s < 0.65  # the old light-blue panel frame
	if bw >= 3 and border.a >= 0.6 and border.s >= 0.35 and border.v >= 0.5 and not web_blue:
		return Color(border, 1.0)
	return fallback


## The legacy «can't» greys (diplomacy buttons, an upgrade that is not possible): the lock role.
static func is_legacy_disabled(c: Color) -> bool:
	for d in [Color(0.3, 0.33, 0.4), Color(0.25, 0.28, 0.36), Color(0.22, 0.26, 0.36)]:
		if _near(c, d, 0.012):
			return true
	return false


static func _near(a: Color, b: Color, tol: float) -> bool:
	return absf(a.r - b.r) <= tol and absf(a.g - b.g) <= tol and absf(a.b - b.b) <= tol


const _ROLE_LITERALS := [
	["info", [Color(0.13, 0.4, 0.9), Color(0.16, 0.42, 0.95), Color(0.16, 0.35, 0.75)]],
	["go", [Color(0.2, 0.55, 0.3), Color(0.2, 0.6, 0.3), Color(0.12, 0.36, 0.2), Color(0.2, 0.4, 0.25)]],
	["war", [Color(0.8, 0.22, 0.16), Color(0.75, 0.16, 0.12), Color(0.85, 0.15, 0.13), Color(0.9, 0.2, 0.15)]],
	["gold", [Color(0.75, 0.55, 0.12), Color(0.85, 0.55, 0.1), Color(0.8, 0.6, 0.1)]],
	["info", [Color(0.45, 0.3, 0.75), Color(0.55, 0.25, 0.8), Color(0.35, 0.2, 0.55), Color(0.55, 0.3, 0.95)]],
	["info", [Color(0.3, 0.33, 0.42), Color(0.3, 0.35, 0.45), Color(0.32, 0.36, 0.46)]],
	["slate", [Color(0.14, 0.18, 0.27)]],  # an unselected toggle: must differ from the selected (info) one
	["info", [Color(0.45, 0.35, 0.2), Color(0.35, 0.22, 0.12)]],
]


## The role of a known legacy literal, or "".
static func _literal_role(c: Color) -> String:
	for d in [Color(0.25, 0.28, 0.36), Color(0.22, 0.26, 0.36)]:
		if _near(c, d, 0.012):
			return "lock"
	for group in _ROLE_LITERALS:
		for lit in group[1]:
			if _near(c, lit, 0.03):
				return group[0]
	return ""


## The role of a legacy button colour: the known literals first, then by hue.
static func role_of(c: Color) -> String:
	var lit := _literal_role(c)
	if lit != "":
		return lit
	if c.s < 0.2:
		return "info"
	if c.v < 0.35:
		return "slate"
	var h := c.h
	if h >= 0.22 and h <= 0.45:
		return "go"
	if h >= 0.47 and h <= 0.70:
		return "info"
	if h >= 0.94 or h <= 0.03:
		return "war"
	if h >= 0.04 and h <= 0.17:
		return "gold"
	return "info"


# ------------------------------------------------------------------ surface decor (lip, highlight line, gloss)

## Child 0 of a Panel whose StyleBoxFlat carries kit meta: draws the bottom lip inside the contour, the top
## highlight line on slate / paper, the gloss band on role faces. Reads the parent's current style each draw,
## so a later restyle of the parent (set_action) is followed.
class KitDecor extends Control:
	func _init() -> void:
		name = "KitDecor"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func _enter_tree() -> void:
		var p := get_parent() as CanvasItem
		if p and not p.draw.is_connected(queue_redraw):
			p.draw.connect(queue_redraw)

	## What to draw for the parent's style at `sz` (empty: nothing): the lip box, the line or the gloss.
	static func spec(sb: StyleBoxFlat, sz: Vector2) -> Dictionary:
		if sb == null or not sb.has_meta("kit_lip") or sb.bg_color.a < 0.99:
			return {}
		var out := float(sb.border_width_left)
		var r := float(sb.corner_radius_top_left)
		var face := sb.bg_color
		var lip := float(sb.get_meta("kit_lip", 0))
		if sz.y < 52.0:
			lip = minf(lip, 5.0)
		if sz.y < 36.0:
			lip = 0.0
		var kind: String = sb.get_meta("kit_kind", "")
		var rl := maxf(float(sb.corner_radius_top_left), 12.0)
		var rr := maxf(float(sb.corner_radius_top_right), 12.0)
		var d := {"out": out, "r": r, "face": face, "lip": lip, "lip_color": sb.get_meta("kit_lip_color", face.darkened(0.3)),
			"radii": [sb.corner_radius_top_left, sb.corner_radius_top_right, sb.corner_radius_bottom_left, sb.corner_radius_bottom_right],
			"line": "", "rl": rl, "rr": rr, "inset": 0.0, "gloss": false, "side": 0.0}
		if kind == "slate" and sz.x > rl + rr + 8.0:
			d["line"] = "slate"
		elif kind == "cream" and sz.x > 64.0:
			d["line"] = "cream"
			d["inset"] = 24.0 if sz.x > 200.0 else maxf(r, 12.0)
		elif kind == "role" and sz.y >= 30.0 and not face.is_equal_approx(ROLE["lock"][0]):  # «unavailable»: no gloss
			d["gloss"] = true
			d["side"] = 12.0 if sz.y >= 104.0 else 8.0
		if lip <= 0.0 and d["line"] == "" and not d["gloss"]:
			return {}
		return d

	## Draws `d` (spec) on `ci` at the size `sz`.
	static func paint(ci: CanvasItem, d: Dictionary, sz: Vector2) -> void:
		var out: float = d["out"]
		var r: float = d["r"]
		var face: Color = d["face"]
		var lip: float = d["lip"]
		var inner := Rect2(out, out, sz.x - 2.0 * out, sz.y - 2.0 * out)
		if lip > 0.0:
			var sb := StyleBoxFlat.new()
			sb.anti_aliasing = true
			sb.corner_detail = 10
			sb.bg_color = face
			# concentric with each of the parent's corners (one may be square: the tray under the first tab)
			var rad: Array = d["radii"]
			sb.corner_radius_top_left = int(maxf(0.0, rad[0] - out))
			sb.corner_radius_top_right = int(maxf(0.0, rad[1] - out))
			sb.corner_radius_bottom_left = int(maxf(0.0, rad[2] - out))
			sb.corner_radius_bottom_right = int(maxf(0.0, rad[3] - out))
			sb.border_width_bottom = int(lip)
			sb.border_color = d["lip_color"]
			ci.draw_style_box(sb, inner)
		if d["line"] == "slate":
			ci.draw_line(Vector2(d["rl"], out + 1.0), Vector2(sz.x - float(d["rr"]), out + 1.0), SLATE_HI, 2.0)
		elif d["line"] == "cream":
			ci.draw_line(Vector2(d["inset"], out + 2.0), Vector2(sz.x - float(d["inset"]), out + 2.0), Color(1, 1, 1, 0.7), 3.0)
		elif d["gloss"]:
			var fh := inner.size.y - lip
			var side: float = d["side"]
			var gl := StyleBoxFlat.new()
			gl.anti_aliasing = true
			gl.corner_detail = 8
			gl.bg_color = SELF.gloss(face)
			gl.set_corner_radius_all(int(maxf(4.0, r - out - 6.0)))
			ci.draw_style_box(gl, Rect2(out + side, out + 5.0, inner.size.x - 2.0 * side, maxf(4.0, fh * 0.34)))

	## Drawn from the bake atlas (KitBake), sliced: the lip and the line stretch both ways, the gloss (its height
	## follows the face's) only sideways.
	func _draw() -> void:
		var p := get_parent() as Control
		if p == null:
			return
		var d := spec(SELF.flat_of(p), size)
		if d.is_empty():
			return
		var out: float = d["out"]
		var rad: Array = d["radii"]
		var r_top := float(maxi(rad[0], rad[1]))
		var r_bot := float(maxi(rad[2], rad[3]))
		var sp := KitBake.SLICE
		var ml := maxf(float(maxi(rad[0], rad[2])), float(d["rl"]) if d["line"] == "slate" else 0.0) + sp
		var mr := maxf(float(maxi(rad[1], rad[3])), float(d["rr"]) if d["line"] == "slate" else 0.0) + sp
		if d["line"] == "cream":
			ml = maxf(ml, float(d["inset"]) + sp)
			mr = maxf(mr, float(d["inset"]) + sp)
		if d["gloss"]:
			var g := out + float(d["side"]) + maxf(4.0, float(d["r"]) - out - 6.0) + sp
			ml = maxf(ml, g)
			mr = maxf(mr, g)
		var mt := maxf(r_top, out + 4.0) + sp
		# the lip's inner contour keeps the full inner radius above its band: its corner reaches lip + (r − out) up from
		# the bottom edge (a cap any shorter stretched a lip-coloured texel up the frame's inner column, ~300 px on a sheet)
		var mb := maxf(r_bot, out + float(d["lip"]) + (maxf(0.0, r_bot - out) if float(d["lip"]) > 0.0 else 0.0)) + sp
		var key := "decor|%s|%s|%.1f,%.1f,%.1f,%.1f|%s|%s|%s|%.1f,%.1f,%.1f,%.1f" % [(d["face"] as Color).to_html(),
			(d["lip_color"] as Color).to_html(), out, d["r"], d["lip"], d["side"], str(rad), d["line"], str(d["gloss"]),
			d["rl"], d["rr"], d["inset"], 0.0]
		var m := Vector4.ZERO
		var bs := size
		if size.x >= ml + mr + 6.0:
			m.x = ml
			m.z = mr
			bs.x = ml + mr + 4.0
		else:
			key += "|w%.2f" % size.x
		if not d["gloss"] and size.y >= mt + mb + 6.0:
			m.y = mt
			m.w = mb
			bs.y = mt + mb + 4.0
		else:
			key += "|h%.2f" % size.y
		var make := func(z: Vector2) -> Control: return KitPainter.new(func(c: CanvasItem): KitDecor.paint(c, d, z), z)
		if not SELF.draw_baked(self, key, Rect2(Vector2.ZERO, size), bs, make, m):
			paint(self, d, size)


# ------------------------------------------------------------------ baked layers (draw calls, docs/dev/hud_perf_plan.json H1)

## The canvas renderer batches consecutive textured rects that share a texture into one draw call, but sends every
## polygon on its own: each StyleBoxFlat, rounded line, disc and chrome stroke is one draw call (a button cost 4–5,
## a «+» 28, a tray card ~87). KitBake renders each distinct set of a component's static vector layers once,
## offscreen, into one shared atlas; the component then draws texture rects from it — sliced where it stretches — so
## neighbouring kit surfaces share one draw call. Pixel parity: a stage SubViewport renders the layers with the very
## draw calls the component would make, at the device's canvas scale and at the component's sub-pixel offset; a
## second pass copies them un-premultiplied into the atlas SubViewport (which is never cleared), so they blend like
## the vectors did; and until its bake is ready (two frames) a component draws its vectors itself. Something that
## moves without being redrawn (a scrolled card, a container relayout) keeps its old image until it has held still
## for SETTLE_MS; it is then drawn again, at its new sub-pixel offset (the image made for another offset stands in,
## resampled, until that one lands). The atlas keeps the images that some canvas item's commands still show: when
## it is full, the others are dropped and their room is used again; only if that is not enough does it start over.
## Something seen through a modulate α < 1 (a claimed row, a taken calendar day) is made at that α, each layer faded
## on its own on the stage as the vectors are on the screen, and drawn with the α it inherits made up for; while its
## α changes (a fade) its opaque image stands in, faded as one piece. Off when headless (the tests): everything is
## drawn as vectors there.
class KitBake extends Node:
	const ATLAS := Vector2i(2048, 2048)  ## at the canvas scale 1; its side grows with the scale (to 4096)
	const STAGE := Vector2i(2048, 1024)  ## the most one round renders (the stage is sized to each round, freed when idle)
	const RESET_GAP_MS := 5000  ## a full atlas starts again at most this often (else what does not fit stays vectors)
	const PAD := 16.0  ## logical px of room round a bake (text outlines and their shadows, AA fringes); a box: its shadow
	const MAX_SIDE := 900  ## px: anything larger is drawn as vectors
	const SETTLE_MS := 200  ## a moved owner is drawn again once it has held still this long
	const POLL_N := 48  ## owners whose place is looked at per frame (in turn)
	const OPAQUE := 0.999  ## a modulate α below this: seen through, its image made at that α (draw, _fade_alpha)
	const FADE_MIN := 0.05  ## below this α (all but gone: a fade's first frames) no image is made at it
	## A full atlas with less than this share in use is in pieces, not full: what fits none waits (_defer). At k ≠ 1 a
	## long list fills more of it (its rows' images at several sub-pixel offsets): at 1080 × 1918 the Chronicle's fast
	## scroll found no piece for a 558 px title at 66 % in use, and the atlas started over mid-scroll (an ~800 draw burst).
	const FRAGMENTED := 0.8
	const DEFER_MAX := 24  ## images waiting so for a piece large enough before the atlas starts over all the same
	const DEFER_RETRY_MS := 300  ## the waiting images are tried again after this long
	const DEFER_TRIES := 3  ## an image that found no piece this many times takes the full atlas's way (compaction)
	const CELL_Y := 8  ## px: an image's room in the atlas is a multiple of this tall (_cell)
	const PHASES := 8.0  ## sub-pixel offset steps per px and axis: owners that close share a bake (made at the first's)
	## Logical px of straight edge a sliced bake keeps past each corner: what is stretched must be uniform, and the
	## antialiased edge of a StyleBoxFlat is not, for a few px past where its corner arc ends (the half-pixel offsets
	## of a scaled canvas show it).
	const SLICE := 6.0
	const STAGE_IDLE_MS := 2000  ## the stage's render target is freed after this long without a round
	const UNPREMUL := "shader_type canvas_item;\nrender_mode blend_disabled;\n" \
		+ "void fragment() {\n\tvec2 sz = vec2(textureSize(TEXTURE, 0));\n\tivec2 p = ivec2(floor(UV * sz));\n" \
		+ "\tvec4 c = texelFetch(TEXTURE, p, 0);\n\tif (c.a > 0.0) {\n\t\tCOLOR = vec4(c.rgb / c.a, c.a);\n\t} else {\n" \
		+ "\t\t// a transparent texel takes the colour of its most opaque neighbour (alpha 0): filtered at a fractional\n" \
		+ "\t\t// offset the edge then fades out instead of darkening\n\t\tvec4 b = vec4(0.0);\n" \
		+ "\t\tfor (int i = 0; i < 4; i++) {\n\t\t\tivec2 o = ivec2(i == 0 ? 1 : (i == 1 ? -1 : 0), i == 2 ? 1 : (i == 3 ? -1 : 0));\n" \
		+ "\t\t\tvec4 n = texelFetch(TEXTURE, clamp(p + o, ivec2(0), ivec2(sz) - 1), 0);\n\t\t\tif (n.a > b.a) {\n\t\t\t\tb = n;\n\t\t\t}\n\t\t}\n" \
		+ "\t\tCOLOR = vec4(b.a > 0.0 ? b.rgb / b.a : vec3(0.0), 0.0);\n\t}\n}\n"
	## An icon into its atlas cell: an exact copy with two rows of its edge texels repeated round it (what the
	## texture's clamp gives a filter at its edge).
	const ICON_COPY := "shader_type canvas_item;\nrender_mode blend_disabled;\nuniform sampler2D src : filter_nearest;\n" \
		+ "void fragment() {\n\tivec2 sz = textureSize(src, 0);\n\tivec2 p = ivec2(floor(UV * vec2(sz + ivec2(4)))) - ivec2(2);\n" \
		+ "\tCOLOR = texelFetch(src, clamp(p, ivec2(0), sz - ivec2(1)), 0);\n}\n"
	static var inst: KitBake
	static var off := false
	var stage: SubViewport
	var atlas: SubViewport
	var tex_rid: RID
	## Physical px per logical px of the main canvas, per axis: the canvas_items stretch scales x by window width /
	## visible width and y by window height / visible height, and the visible size is whole pixels — so the two
	## differ a little (1080 × 1918: 1080 / 941 and 1918 / 1672), which is half a pixel across the screen. The
	## bakes are made at it.
	var kv := Vector2.ONE
	var k := 1.0  ## the larger of the two (the atlas's size, the fonts' oversampling — Viewport takes the larger too)
	var slots := {}  ## full key -> Rect2i: the baked image in the atlas
	var made := {}  ## full key -> [sub-pixel offset (Vector2), pad (image px)]: how its image was made
	var alts := {}  ## key without the offset -> the full key last baked: stands in while another offset bakes
	var jobs := {}  ## full key -> {size, px, off, pp, base, make}: waiting for a round
	var never := {}  ## keys that are not baked (too large)
	var owners := {}  ## instance id -> WeakRef: everything that drew from the atlas (redrawn when it is reset)
	var waiting := {}  ## key -> {instance id: WeakRef}: redrawn when that bake lands
	var seen := {}  ## volatile key -> [first asked for, last asked for] (ms; held())
	var refs := {}  ## canvas item RID id -> [frame, {full key: true}, WeakRef owner]: the images its commands show now
	var placed := {}  ## host instance id -> [WeakRef, origin on the canvas, moved at (ms)]: what drew from the atlas there
	var parked := {}  ## host instance id -> [WeakRef, rect, pad]: what was out of sight when it asked (not baked yet)
	## host instance id -> [its chain_alpha when last looked at, since when (ms; -1: so since it was first seen), the
	## chain α its commands are made for (1: none — its opaque image, faded as one piece)]: the hosts seen through a
	## modulate α < 1 (_fade_alpha, _poll_moves)
	var fades := {}
	var resets := 0
	var evicted := 0  ## images dropped to make room (they were no longer shown)
	var _moving := {}  # host ids that moved, until they hold still (then they are drawn again)
	var _poll: Array = []  # host ids still to look at in this pass
	var _poll_p: Array = []  # parked host ids still to look at in this pass
	var _defer := {}  # full key -> job: no piece of the (fragmented) atlas fits it yet; queued again after DEFER_RETRY_MS
	var _defer_n := {}  # full key -> how many times it was deferred (DEFER_TRIES)
	var _defer_at := 0
	var _later: Array = []  # [WeakRef, due ms]: owners to redraw then (later())
	var _round: Array = []  # the jobs in flight: {key, base, off, pp, at (stage px), slot, gen}
	var _state := 0  # 0 idle, 1 the stage renders, 2 the atlas copies
	var _gen := 0  # the atlas generation (a reset starts a new one: what is in flight from before is dropped)
	var _sky: Array = []  # the packer's skyline: Vector3i(x, y, width), left to right
	var _free: Array = []  # Rect2i: room left by dropped images (used before the skyline)
	var _used := 0  # px² of the atlas in use
	var _top := 0  # the skyline's highest point
	var _asize := ATLAS  # the atlas's size now
	var _reset_at := -100000
	var _round_at := -100000
	var _landed := -100  # the process frame the last round landed in (its owners draw again in the next ones)
	var _squeeze := false  # the atlas ran out of room: what cannot be seen gives its images up (draw, _release_unseen)
	var _asked := {}  # canvas item RID id -> the frame _release_unseen asked it to draw again
	var why := ""  ## why the atlas last started over (perf_probe)
	var _nodes: Array = []  # the stage / copy nodes of the round
	var _mat: ShaderMaterial
	var _icon_shader: Shader
	## The rendered icons (128 × 128, assets/ui/icons) share the atlas too: each is an AtlasTexture that shows its own
	## texture until the icon is copied into an atlas cell (with its edge texels repeated round it), then that cell —
	## an icon and the kit surfaces round it then batch.
	const ICON := 128
	const ICON_CELL := 132  # 2 px of repeated edge texels round each icon
	var icons := {}  # source texture path -> [AtlasTexture, source Texture2D, atlas cell (Rect2i; size 0: not there)]
	var _icons_new: Array = []  # icon paths to copy into the atlas
	var _icon_round: Array = []  # [path, cell, gen]: the icons being copied

	## The shared instance (made on first use; it joins the scene root a frame later). null when headless.
	static func get_inst() -> KitBake:
		if off:
			return null
		if inst == null or not is_instance_valid(inst):
			if DisplayServer.get_name() == "headless":
				off = true
				return null
			var tree := Engine.get_main_loop() as SceneTree
			if tree == null or tree.root == null:
				return null
			inst = KitBake.new()
			inst.name = "KitBake"
			inst._set_scale(inst._scale(tree.root))  # the bakes asked for before it joins the tree are made at it too
			inst._fit_atlas()
			tree.root.add_child.call_deferred(inst)
		return inst

	func _init() -> void:
		process_mode = Node.PROCESS_MODE_ALWAYS
		stage = SubViewport.new()
		stage.name = "stage"
		stage.size = Vector2i(4, 4)  # (sized to each round)
		stage.transparent_bg = true
		stage.disable_3d = true
		stage.render_target_update_mode = SubViewport.UPDATE_DISABLED
		add_child(stage)
		atlas = SubViewport.new()
		atlas.name = "atlas"
		atlas.size = ATLAS
		atlas.transparent_bg = true
		atlas.disable_3d = true
		atlas.render_target_clear_mode = SubViewport.CLEAR_MODE_NEVER
		atlas.render_target_update_mode = SubViewport.UPDATE_DISABLED
		add_child(atlas)
		tex_rid = atlas.get_texture().get_rid()
		var sh := Shader.new()
		sh.code = UNPREMUL
		_mat = ShaderMaterial.new()
		_mat.shader = sh
		_icon_shader = Shader.new()
		_icon_shader.code = ICON_COPY
		_pack_reset()

	func _ready() -> void:
		_on_resize()
		get_tree().root.size_changed.connect(_on_resize)
		RenderingServer.frame_post_draw.connect(_on_post_draw)

	func _exit_tree() -> void:
		if RenderingServer.frame_post_draw.is_connected(_on_post_draw):
			RenderingServer.frame_post_draw.disconnect(_on_post_draw)

	## Physical px per logical px of the main canvas, per axis (canvas_items stretch).
	static func _scale(root: Window) -> Vector2:
		var win := Vector2(DisplayServer.window_get_size())
		var vis := root.get_visible_rect().size
		if win.x <= 0.0 or win.y <= 0.0 or vis.x <= 0.0 or vis.y <= 0.0:
			return Vector2.ONE
		return win / vis

	func _set_scale(v: Vector2) -> void:
		kv = v
		k = maxf(v.x, v.y)

	func _on_resize() -> void:
		var nk := _scale(get_tree().root)
		if not nk.is_equal_approx(kv):
			_set_scale(nk)
			_fit_atlas()
			reset()

	## The atlas holds the same bakes at any canvas scale: its side grows with the scale. The stage rasterises text at
	## the scale too (the main canvas oversamples its fonts by it), so a baked label is as sharp as a live one.
	func _fit_atlas() -> void:
		var side := clampi(int(ceil(ATLAS.x * maxf(1.0, k) / 256.0)) * 256, ATLAS.x, 4096)
		_asize = Vector2i(side, side)
		atlas.size = _asize
		stage.oversampling_override = k
		_pack_reset()

	## Forgets every bake (the canvas scale changed, or the atlas is full even without what is no longer shown):
	## whatever drew from the atlas draws again (its vectors, then its new bake).
	func reset() -> void:
		resets += 1
		_gen += 1
		_squeeze = false
		_reset_at = Time.get_ticks_msec()
		slots.clear()
		made.clear()
		alts.clear()
		never.clear()
		refs.clear()
		_pack_reset()
		for key in _defer:  # (the new atlas has room for what waited)
			if not jobs.has(key):
				jobs[key] = _defer[key]
		_defer.clear()
		_defer_n.clear()
		_icons_new.clear()
		for path in icons:  # the icons show their own textures until they are in the new atlas
			var e: Array = icons[path]
			var at := e[0] as AtlasTexture
			at.atlas = e[1]
			at.region = Rect2(0, 0, ICON, ICON)
			e[2] = Rect2i()
			_icons_new.append(path)
		var all := owners
		owners = {}
		for id in all:
			_poke(all[id])

	func _poke(w: WeakRef) -> void:
		var o: Object = w.get_ref()
		if o is CanvasItem:
			(o as CanvasItem).queue_redraw()
		elif o is Resource:
			(o as Resource).emit_changed()

	## The sub-pixel offset (in physical px) of a canvas item's local point `p` on a canvas scaled by `k_` (per axis).
	## Controls sit on whole logical pixels (Viewport.gui_snap_controls_to_pixels rounds each one's position), so this
	## is the fraction of `p` itself at the canvas scale 1; a rotated or scaled item is resampled anyway (0).
	static func offset_of(ci: CanvasItem, p: Vector2, k_: Vector2) -> Vector2:
		if ci == null or not ci.is_inside_tree():
			return Vector2.ZERO
		var o := p
		var n: Node = ci
		var snap := ci.get_viewport().gui_snap_controls_to_pixels
		while n is CanvasItem:
			if n is Control:
				var c := n as Control
				if c.rotation != 0.0 or c.scale != Vector2.ONE:
					return Vector2.ZERO
				o += (c.position + Vector2(0.5, 0.5)).floor() if snap else c.position
			elif n is Node2D:
				var n2 := n as Node2D
				if n2.rotation != 0.0 or n2.scale != Vector2.ONE:
					return Vector2.ZERO
				o += n2.position
			if (n as CanvasItem).top_level:
				break
			n = n.get_parent()
		if n is CanvasLayer:
			o += (n as CanvasLayer).offset
		var g := o * k_
		return Vector2(fposmod(g.x, 1.0), fposmod(g.y, 1.0))

	## offset_of at this canvas scale: a bake is made at it, so its texels land on the screen's pixels as the vectors
	## would. Exact, not quantised: the bake's key takes it to 1/8 px (draw: owners that close share one image), but the
	## image is made at its first asker's very offset — a hard edge inside a shape (a title plate's highlight band, its
	## lip) that falls near a pixel centre at k ≠ 1 is then on the same row as the vectors', not one row off.
	func frac_of(ci: CanvasItem, p: Vector2) -> Vector2:
		return offset_of(ci, p, kv)

	## Draws the baked layers `key` into `rect` on the canvas item `ci` (a RID). `size`: the logical size the layers
	## are made at (`make` returns a Control that draws them, its origin at (0, 0)); `m`: slice margins (left, top,
	## right, bottom; logical) on an axis where the layers stretch from `size` to `rect`, 0 0 on an axis where
	## rect.size == size. `f`: the sub-pixel offset (frac_of). `host`: the canvas item `ci` belongs to (`owner` when
	## that is one); `pad`: logical px the layers reach past their rect. Returns false while the bake is not ready —
	## it is then queued, `owner` is redrawn when it lands, and the caller draws its vectors (unless the same layers
	## made at another sub-pixel offset can stand in: they are drawn, resampled, until then).
	func draw(ci: RID, key: String, rect: Rect2, size: Vector2, make: Callable, owner: Object, m := Vector4.ZERO,
			f := Vector2.ZERO, mod := Color.WHITE, queue := true, host: CanvasItem = null, pad := PAD) -> bool:
		# on a sliced axis the stretch must be a whole number of pixels, or the far caps (right, bottom) would land
		# between pixels: the size the layers are made at grows by the fraction (to 1/8 px)
		if m.x > 0.0:
			size.x = _base(rect.size.x, size.x, kv.x)
		if m.y > 0.0:
			size.y = _base(rect.size.y, size.y, kv.y)
		var hh: CanvasItem = host if host != null else owner as CanvasItem
		var base := "%s@%.4f,%.4f|%.3f,%.3f|p%.1f" % [key, kv.x, kv.y, size.x, size.y, pad]
		# seen through a modulate α < 1 (a claimed row, a taken calendar day; `mod`: a label's own): the image is made at
		# that α, each layer faded on its own on the stage as the vectors are here — an opaque image faded as one piece
		# would be lighter (the layers under its face no longer show through) — and drawn with the α it inherits made up
		# for (`mod` α / fa: the product is 1)
		var fa := _fade_alpha(hh, mod.a) if hh != null else 1.0
		if fa < 1.0:
			base += "|a%.3f" % fa
			mod = Color(mod.r, mod.g, mod.b, mod.a / fa)
		var ph := int(PHASES)
		var full := "%s/%d,%d" % [base, posmod(roundi(f.x * PHASES), ph), posmod(roundi(f.y * PHASES), ph)]
		var e := _ref(ci, owner if owner != null else host, hh)  # (its commands are being recorded anew)
		var slot: Variant = slots.get(full)
		if slot != null and _squeeze and not in_sight(hh, rect, pad):
			# the atlas is short of room: what is off the screen gives its image up (draws its vectors, culled) so that
			# the next eviction frees its place; it asks again once it comes onto the screen
			_park(hh, rect, pad)
			return false
		if slot == null:
			if not queue:
				return false
			if not never.has(full):
				var pp := (Vector2(pad, pad) * kv).ceil()
				var pxs := Vector2i((size * kv + 2.0 * pp + Vector2.ONE).ceil())
				if pxs.x > MAX_SIDE or pxs.y > MAX_SIDE or size.x <= 0.0 or size.y <= 0.0:
					never[full] = true
					return false
				if not in_sight(hh, rect, pad):
					# off the screen (the rows of a long list scrolled away below it): not baked, or such a list would fill
					# the atlas and start it over and over; it draws its vectors (the renderer culls them) and is drawn
					# again once it comes onto the screen (_poll_parked)
					_park(hh, rect, pad)
				else:
					if hh != null and not parked.is_empty():
						parked.erase(hh.get_instance_id())
					if not jobs.has(full) or not (jobs[full]["make"] as Callable).is_valid():  # (its first asker is gone)
						jobs[full] = {"size": size, "px": pxs, "off": f, "pp": pp, "base": base, "make": make, "alpha": fa}
					if owner != null:
						if not waiting.has(full):
							waiting[full] = {}
						waiting[full][owner.get_instance_id()] = weakref(owner)
			var alt: Variant = alts.get(base)  # the same layers made at another offset: resampled until then
			if alt == null or not slots.has(alt):
				return false
			full = alt
			slot = slots[alt]
		if owner != null:
			var id := owner.get_instance_id()
			if not owners.has(id):
				owners[id] = weakref(owner)
		var h: CanvasItem = host if host != null else owner as CanvasItem
		if h != null:
			_place(h)
		e[1][full] = true
		var how: Array = made[full]
		_blit(ci, slot, rect, size, m, how[0], how[1], mod)
		return true

	## Whether `rect` (local to `h`, grown by `pad`) is on the screen now (an item of a SubViewport's canvas counts as
	## on it). Only the screen: what a scroll's clip hides but the screen would show (a row under a window's title, a
	## card's badge past the tray's edge) is baked as before — drawn as vectors it would cost its draw calls clipped,
	## while off the screen the renderer culls the vectors for nothing.
	static func in_sight(h: CanvasItem, rect: Rect2, pad: float) -> bool:
		if h == null or not h.is_inside_tree():
			return true
		var vp := h.get_viewport()
		if vp == null or vp != h.get_tree().root:
			return true
		return (h.get_global_transform_with_canvas() * rect.grow(pad)).intersects(vp.get_visible_rect())

	## The α `h`'s own commands are drawn at: its self_modulate times the modulate of it and of every canvas item above
	## it (a top-level item does not inherit its parents') — but for a passing fade's (Kit.passing_fade: a window
	## closing, a tab's content fading in), which what is under it takes as one piece.
	static func chain_alpha(h: CanvasItem) -> float:
		var a := h.self_modulate.a
		var n: Node = h
		while n is CanvasItem:
			var c := n as CanvasItem
			if not c.has_meta(&"kit_fade"):
				a *= c.modulate.a
			if a < FADE_MIN or c.top_level:
				break
			n = n.get_parent()
		return a

	## The α to make `h`'s image at: its α on the screen (chain_alpha × `ma`, a label's own) when that is below 1 and
	## holds — as it was first seen, or for SETTLE_MS since it changed — else 1 (opaque; while its α changes, a fade,
	## the opaque image stands in, faded as one piece by the modulate it inherits).
	func _fade_alpha(h: CanvasItem, ma: float) -> float:
		var id := h.get_instance_id()
		var c := chain_alpha(h)
		var at := snappedf(c * ma, 0.001)
		if at >= OPAQUE:
			if not fades.is_empty():
				fades.erase(id)
			return 1.0
		var now := Time.get_ticks_msec()
		var r: Variant = fades.get(id)
		var steady := true
		if r == null:
			r = [c, -1, 1.0]  # (first seen so: a claimed row is made faded, not faded in)
			fades[id] = r
		elif absf(float(r[0]) - c) > 0.0005:
			r[0] = c
			r[1] = now
			steady = false
		else:
			steady = int(r[1]) < 0 or now - int(r[1]) >= SETTLE_MS
		steady = steady and at >= FADE_MIN
		r[2] = c if steady else 1.0
		return at if steady else 1.0

	## The record of what the canvas item `ci` shows from the atlas: started anew on the first draw in a frame (a
	## canvas item's commands are all recorded again when it is drawn).
	func _ref(ci: RID, owner: Object, host: CanvasItem = null) -> Array:
		var id := ci.get_id()
		var fr := Engine.get_process_frames()
		var e: Variant = refs.get(id)
		if e == null or int(e[0]) != fr:
			e = [fr, {}, weakref(owner) if owner != null else null, weakref(host) if host != null else null]
			refs[id] = e
		return e

	## Asks every canvas item that shows atlas images but is off the screen now (a long list's rows scrolled away) to
	## draw again — its vectors, while _squeeze is on — so its images are no longer shown and the next eviction frees
	## their room. Returns how many were asked.
	func _release_unseen() -> int:
		var n := 0
		var fr := Engine.get_process_frames()
		for id in refs.keys():
			var e: Array = refs[id]
			if (e[1] as Dictionary).is_empty() or int(e[0]) <= int(_asked.get(id, -1)):  # (asked, not drawn since: not again)
				continue
			var h: CanvasItem = (e[3] as WeakRef).get_ref() as CanvasItem if e.size() > 3 and e[3] != null else null
			if h == null and e[2] != null:
				h = (e[2] as WeakRef).get_ref() as CanvasItem
			if h == null or not h.is_inside_tree() or not h.is_visible_in_tree():
				continue
			if not in_sight(h, Rect2(Vector2.ZERO, (h as Control).size if h is Control else Vector2.ZERO), PAD):
				h.queue_redraw()
				_asked[id] = fr
				n += 1
		if _asked.size() > 4096:
			_asked.clear()
		return n

	## Remembers where `h` drew from the atlas (its place on the canvas), to draw it again once it has moved.
	func _place(h: CanvasItem) -> void:
		var id := h.get_instance_id()
		var o := h.get_global_transform_with_canvas().origin
		var e: Variant = placed.get(id)
		if e == null:
			placed[id] = [weakref(h), o, 0]
		else:
			e[1] = o

	## Looks at POLL_N owners' places a frame: one that has moved (a scroll, a relayout, a slide) is drawn again once
	## it has held still for SETTLE_MS, so its images land on whole pixels again (at k ≠ 1 a whole logical pixel is
	## not a whole physical one). Its α too (_poll_alpha).
	func _poll_moves() -> void:
		if placed.is_empty():
			return
		var now := Time.get_ticks_msec()
		if _poll.is_empty():
			_poll = placed.keys()
		for i in mini(POLL_N, _poll.size()):
			var id: int = _poll.pop_back()
			var e: Variant = placed.get(id)
			if e == null:
				continue
			var h := (e[0] as WeakRef).get_ref() as CanvasItem
			if h == null or not h.is_inside_tree():
				placed.erase(id)
				fades.erase(id)
				continue
			var o := h.get_global_transform_with_canvas().origin
			if o != e[1]:
				e[1] = o
				e[2] = now
				_moving[id] = true
			_poll_alpha(h, id, now)
		if _moving.is_empty():
			return
		for id in _moving.keys():
			var e: Variant = placed.get(id)
			var h: CanvasItem = (e[0] as WeakRef).get_ref() as CanvasItem if e != null else null
			if h == null or not h.is_inside_tree():
				_moving.erase(id)
				placed.erase(id)
				continue
			var o := h.get_global_transform_with_canvas().origin
			if o != e[1]:
				e[1] = o
				e[2] = now
			elif now - int(e[2]) >= SETTLE_MS:
				_moving.erase(id)
				h.queue_redraw()

	## Remembers `h`, off the screen when it asked for a bake: it is drawn again once `rect` (local, grown by `pad`) is on
	## the screen (a scroll brought it in), or once it has moved and held still.
	func _park(h: CanvasItem, rect: Rect2, pad: float) -> void:
		_place(h)
		parked[h.get_instance_id()] = [weakref(h), rect, pad]

	## The α of `h` (placed: it drew from the atlas) against the α its commands are made for (fades): brighter — no
	## longer faded, or less — it draws again at once (its image, made up for a lower α, would show too opaque);
	## another α that has held for SETTLE_MS (a parent faded it since, a fade ended) draws again then, at that α. A
	## changing α (a fade going on) leaves it as it is: its image fades as one piece meanwhile. Asked once per change
	## (what it is made for is set here: a host whose drawing does not come back through draw() is not asked again).
	func _poll_alpha(h: CanvasItem, id: int, now: int) -> void:
		var c := chain_alpha(h)
		var r: Variant = fades.get(id)
		if r == null:
			if c >= OPAQUE:
				return
			r = [c, now, 1.0]  # (faded since it drew: opaque)
			fades[id] = r
		elif absf(float(r[0]) - c) > 0.0005:
			r[0] = c
			r[1] = now
		var made_for := float(r[2])
		if c > made_for + 0.002 and made_for < OPAQUE:
			r[2] = minf(c, 1.0)
			h.queue_redraw()
		elif absf(made_for - c) > 0.0005 and c >= FADE_MIN and (c >= OPAQUE or int(r[1]) < 0 or now - int(r[1]) >= SETTLE_MS):
			r[2] = c
			h.queue_redraw()
		if c >= OPAQUE and float(r[2]) >= OPAQUE:
			fades.erase(id)

	## Looks at POLL_N parked hosts a frame: one that has come into sight draws again (and asks for its bakes).
	func _poll_parked() -> void:
		if parked.is_empty():
			return
		if _poll_p.is_empty():
			_poll_p = parked.keys()
		for i in mini(POLL_N, _poll_p.size()):
			var id: int = _poll_p.pop_back()
			var e: Variant = parked.get(id)
			if e == null:
				continue
			var h := (e[0] as WeakRef).get_ref() as CanvasItem
			if h == null or not h.is_inside_tree():
				parked.erase(id)
			elif in_sight(h, e[1], e[2]):
				parked.erase(id)
				h.queue_redraw()

	## True once `key` has been asked for (by any owner) for STILL_MS: a volatile look (a label's text, a bar's fill)
	## is baked only then, so a timer or a growing number does not fill the atlas with every step — while a row of
	## cards rebuilt every second keeps its unchanging texts baked.
	func held(key: String) -> bool:
		var now := Time.get_ticks_msec()
		if seen.size() > 2048:  # forget what was asked for only a while ago
			var keep := {}
			for k_ in seen:
				if now - int(seen[k_][1]) < 20000:
					keep[k_] = seen[k_]
			seen = keep
		var e: Variant = seen.get(key)
		if e == null or now - int(e[1]) > 10000:  # first asked for, or not for a long while: (re)start its clock
			seen[key] = [now, now]
			return false
		e[1] = now
		return now - int(e[0]) >= KitText.STILL_MS

	## The size a sliced axis is made at: at least `base`, and `len` minus it a whole number of physical pixels (`kk`
	## per logical px).
	func _base(len_: float, base: float, kk: float) -> float:
		var b := len_ - floorf((len_ - base) * kk + 0.001) / kk
		return base + roundf((b - base) * 8.0) / 8.0

	## The image's texels map onto the screen 1:1 from the physical pixel where the layers' origin minus the pad
	## (`pp`, image px, plus the sub-pixel offset `f` it was made at) falls.
	func _blit(ci: RID, slot: Rect2i, rect: Rect2, size: Vector2, m: Vector4, f: Vector2, pp: Vector2, mod := Color.WHITE) -> void:
		var img := Vector2(slot.size)
		# x spans: [image x0, x1] -> [logical x0, x1]
		var xs := _spans(rect.position.x, rect.size.x, size.x, m.x, m.z, pp.x + f.x, img.x, kv.x)
		var ys := _spans(rect.position.y, rect.size.y, size.y, m.y, m.w, pp.y + f.y, img.y, kv.y)
		var sp := Vector2(slot.position)
		for y in ys:
			for x in xs:
				var dst := Rect2(x[2], y[2], x[3] - x[2], y[3] - y[2])
				var src := Rect2(sp.x + x[0], sp.y + y[0], x[1] - x[0], y[1] - y[0])
				if dst.size.x > 0.0 and dst.size.y > 0.0 and src.size.x > 0.0 and src.size.y > 0.0:
					RenderingServer.canvas_item_add_texture_rect_region(ci, dst, tex_rid, src, mod)

	## One axis: the image's spans and where they go. `o`: image px of the layers' origin; `w`: image px wide; `kk`:
	## image px per logical px.
	func _spans(pos: float, len_: float, base: float, m0: float, m1: float, o: float, w: float, kk: float) -> Array:
		var x0 := pos - o / kk  # logical position of image px 0
		if m0 <= 0.0 and m1 <= 0.0:
			return [[0.0, w, x0, x0 + w / kk]]
		var shift := len_ - base  # the right part moves with the stretch
		var a := roundf(o + m0 * kk)
		var b := roundf(o + (base - m1) * kk)
		return [[0.0, a, x0, x0 + a / kk], [a, b, x0 + a / kk, x0 + shift + b / kk], [b, w, x0 + shift + b / kk, x0 + shift + w / kk]]

	## The icon `t` (a 128 × 128 render of assets/ui/icons) as an AtlasTexture that moves into the bake atlas; `t`
	## itself when it cannot (another size).
	func icon(t: Texture2D) -> Texture2D:
		var path := t.resource_path
		if icons.has(path):
			return icons[path][0]
		if t.get_width() != ICON or t.get_height() != ICON:
			return t
		var at := AtlasTexture.new()
		at.atlas = t
		at.region = Rect2(0, 0, ICON, ICON)
		at.set_meta("kit_src", t)
		icons[path] = [at, t, Rect2i()]
		_icons_new.append(path)
		return at

	## Redraws `owner` (a CanvasItem) in `ms` milliseconds: a volatile look asks again whether it has held still.
	func later(owner: CanvasItem, ms: int) -> void:
		_later.append([weakref(owner), Time.get_ticks_msec() + ms])

	func _process(_d: float) -> void:
		var now := Time.get_ticks_msec()
		if not _later.is_empty():
			var keep: Array = []
			for e in _later:
				if now < int(e[1]):
					keep.append(e)
					continue
				var o: Object = (e[0] as WeakRef).get_ref()
				if o != null and o.has_method("_rearm"):
					o.call("_rearm")  # (it redraws and may ask for another look later)
				else:
					_poke(e[0])
			_later = keep
		_poll_moves()
		_poll_parked()
		if not _defer.is_empty() and now - _defer_at >= DEFER_RETRY_MS:
			for key in _defer:
				if not jobs.has(key):
					jobs[key] = _defer[key]
			_defer.clear()
		if _state != 0 or not is_inside_tree():
			return
		if not jobs.is_empty():
			_stage_round()
		elif not _icons_new.is_empty():
			_copy_icons()
			if not _icon_round.is_empty():
				atlas.render_target_update_mode = SubViewport.UPDATE_ONCE
				_state = 2
		elif stage.size != Vector2i(4, 4) and now - _round_at > STAGE_IDLE_MS:
			stage.size = Vector2i(4, 4)  # its render target is freed until the next round

	## Copies the icons waiting for a place into their atlas cells (this frame's atlas render); one that finds no
	## room shows its own texture.
	func _copy_icons() -> void:
		var tried := false
		for path in _icons_new:
			var e: Array = icons[path]
			var cell := _alloc(Vector2i(ICON_CELL, ICON_CELL))
			if cell.size.x == 0 and not tried:
				tried = true
				_evict()
				cell = _alloc(Vector2i(ICON_CELL, ICON_CELL))
			if cell.size.x == 0:
				continue
			e[2] = cell
			var c := ColorRect.new()
			var mat := ShaderMaterial.new()
			mat.shader = _icon_shader
			mat.set_shader_parameter("src", e[1])
			c.material = mat
			c.position = Vector2(cell.position)
			c.size = Vector2(cell.size)
			atlas.add_child(c)
			_nodes.append(c)
			_icon_round.append([path, cell, _gen])
		_icons_new.clear()

	## Packs waiting jobs into the stage and the atlas and renders them on the stage this frame.
	func _stage_round() -> void:
		if owners.size() > 4096:  # forget the freed ones
			var live := {}
			for id in owners:
				if (owners[id] as WeakRef).get_ref() != null:
					live[id] = owners[id]
			owners = live
		if refs.size() > 4096:
			for id in refs.keys():
				var w: Variant = refs[id][2]
				if w != null and (w as WeakRef).get_ref() == null:
					refs.erase(id)
		if fades.size() > 4096:  # (the hosts that drew vectors and were freed: never placed, never polled)
			for id in fades.keys():
				if not is_instance_id_valid(id):
					fades.erase(id)
		var x := 0
		var y := 0
		var row := 0
		var ext := Vector2i.ZERO
		var tried := false
		var done: Array = []
		for key in jobs:
			var j: Dictionary = jobs[key]
			var px: Vector2i = j["px"]
			var cell := _cell(px)
			if x + cell.x > STAGE.x:
				x = 0
				y += row
				row = 0
			if y + cell.y > STAGE.y:
				break
			var slot := _alloc(cell)
			if slot.size.x == 0 and not tried:  # the atlas is full: drop what is no longer shown
				tried = true
				_evict()
				slot = _alloc(cell)
			if slot.size.x == 0:
				# full of what is shown — some of it perhaps out of sight (a long list scrolled by): that draws its vectors from
				# the next frame and gives its room up then, instead of the atlas starting over
				_squeeze = true
				if _release_unseen() > 0:
					break
			if slot.size.x == 0 and (not _round.is_empty() or Engine.get_process_frames() - _landed <= 2):
				# full of what is shown now: this round takes what fits, the rest waits — what lands replaces images
				# (a moved owner's old offset, a changed look) that can be dropped once their owners have drawn again
				break
			if slot.size.x == 0:
				var tries := int(_defer_n.get(key, 0))
				if used() < FRAGMENTED and _defer.size() < DEFER_MAX and tries < DEFER_TRIES:
					# a fifth or more free, but in pieces too small for it (a long list's rows dropped here and there): it
					# waits — its owners draw its vectors — instead of the atlas starting over (every image drawn as vectors at
					# once until the round lands: a burst of draw calls in the middle of a scroll); tried again shortly, when
					# what went out of sight has given its room up — DEFER_TRIES times, then the atlas is compacted after all
					if _defer.is_empty():
						_defer_at = Time.get_ticks_msec()
					_defer[key] = j
					_defer_n[key] = tries + 1
					done.append(key)
					continue
				_defer_n.erase(key)
				if Time.get_ticks_msec() - _reset_at < RESET_GAP_MS:
					# full again right after a reset: what does not fit now stays vectors (until the next reset)
					never[key] = true
					done.append(key)
					var ws: Dictionary = waiting.get(key, {})
					waiting.erase(key)
					for id in ws:
						_poke.call_deferred(ws[id])
					continue
				# full of what is shown: start it again with what is drawn now (the jobs stay queued)
				why = "full for %s: %.0f%% in use, %d free rects (largest %s), %d refs, %d parked; %s" % [cell, used() * 100.0, _free.size(), _largest_free(), refs.size(), parked.size(), _refs_census()]
				for n in _nodes:
					(n as Node).queue_free()
				_nodes.clear()
				_round.clear()
				reset()
				return
			done.append(key)
			if not _defer_n.is_empty():
				_defer_n.erase(key)
			var n: Control = (j["make"] as Callable).call(j["size"]) if (j["make"] as Callable).is_valid() else null
			if n == null:  # its asker is gone, or what it asked for has changed: the others waiting ask again
				_release(slot)
				var ws: Dictionary = waiting.get(key, {})
				waiting.erase(key)
				for id in ws:
					_poke.call_deferred(ws[id])
				continue
			# a Node2D holds it: Controls are snapped to whole pixels, the holder keeps the sub-pixel offset
			var pp: Vector2 = j["pp"]
			var holder := Node2D.new()
			holder.position = Vector2(x + 1, y + 1) + pp + (j["off"] as Vector2)
			holder.scale = kv
			# a faded look (draw): each of its layers drawn at that α onto the clear stage, as the vectors are over the screen
			holder.modulate.a = float(j.get("alpha", 1.0))
			n.position = Vector2.ZERO
			holder.add_child(n)
			stage.add_child(holder)
			_nodes.append(holder)
			_round.append({"key": key, "base": j["base"], "off": j["off"], "pp": pp, "at": Vector2i(x, y),
				"slot": slot, "cell": cell, "px": px, "gen": _gen})
			x += cell.x
			row = maxi(row, cell.y)
			ext = ext.max(Vector2i(x, y + row))
		for key in done:
			jobs.erase(key)
		if _round.is_empty():
			return
		# the stage's render target: as large as this round needs (it only grows until it is freed when idle)
		var need := Vector2i(mini(STAGE.x, (ext.x + 127) / 128 * 128), mini(STAGE.y, (ext.y + 127) / 128 * 128))
		if stage.size.x < need.x or stage.size.y < need.y:
			stage.size = stage.size.max(need)
		_round_at = Time.get_ticks_msec()
		stage.render_target_update_mode = SubViewport.UPDATE_ONCE
		_state = 1

	## The atlas room an image of `px` takes: a 1 px clear gutter round it, its height rounded up to CELL_Y — the rows of
	## a long list (titles, subtitles: a few px apart in height) then leave room their successors fit in when they are
	## dropped (at 1080 × 1918 a 389 × 87 title found only 84 px tall pieces at 71 % in use, and the atlas started over).
	static func _cell(px: Vector2i) -> Vector2i:
		return Vector2i(px.x + 2, (px.y + 2 + CELL_Y - 1) / CELL_Y * CELL_Y)

	## The packer: an empty skyline over the whole atlas.
	func _pack_reset() -> void:
		_sky = [Vector3i(0, 0, _asize.x)]
		_free.clear()
		_used = 0
		_top = 0

	## A place for a `cell`-sized image: in the room dropped images left (the best fit, split in two), else on the
	## skyline (the lowest spot, then the leftmost). Size 0 when there is none.
	func _alloc(cell: Vector2i) -> Rect2i:
		var bi := -1
		var ba := 1 << 40
		for i in _free.size():
			var r: Rect2i = _free[i]
			if r.size.x >= cell.x and r.size.y >= cell.y and r.get_area() < ba:
				bi = i
				ba = r.get_area()
		if bi >= 0:
			var r: Rect2i = _free[bi]
			_free.remove_at(bi)
			var rw := r.size.x - cell.x
			var rh := r.size.y - cell.y
			var parts: Array = []
			if rw > rh:  # the larger leftover keeps the full side
				parts = [Rect2i(r.position.x + cell.x, r.position.y, rw, r.size.y), Rect2i(r.position.x, r.position.y + cell.y, cell.x, rh)]
			else:
				parts = [Rect2i(r.position.x, r.position.y + cell.y, r.size.x, rh), Rect2i(r.position.x + cell.x, r.position.y, rw, cell.y)]
			for q in parts:
				if (q as Rect2i).size.x >= 8 and (q as Rect2i).size.y >= 8:
					_free.append(q)
			_used += cell.x * cell.y
			return Rect2i(r.position, cell)
		var best := -1
		var by := 1 << 30
		for i in _sky.size():
			var s: Vector3i = _sky[i]
			if s.x + cell.x > _asize.x:
				break
			var top := 0
			var left := cell.x
			var j := i
			while left > 0:
				var t: Vector3i = _sky[j]
				top = maxi(top, t.y)
				left -= t.z
				j += 1
			if top + cell.y <= _asize.y and top < by:
				by = top
				best = i
		if best < 0:
			return Rect2i()
		var bx: int = (_sky[best] as Vector3i).x
		var nx := bx + cell.x
		var out: Array = []
		var put := false
		for s in _sky:
			var a: Vector3i = s
			var a_end := a.x + a.z
			if a_end <= bx:
				out.append(a)
				continue
			if a.x >= nx:
				if not put:
					out.append(Vector3i(bx, by + cell.y, cell.x))
					put = true
				out.append(a)
				continue
			if a.x < bx:
				out.append(Vector3i(a.x, a.y, bx - a.x))
			if not put:
				out.append(Vector3i(bx, by + cell.y, cell.x))
				put = true
			if a_end > nx:
				out.append(Vector3i(nx, a.y, a_end - nx))
		if not put:
			out.append(Vector3i(bx, by + cell.y, cell.x))
		_sky.clear()
		for a in out:  # neighbours at one height merge
			if not _sky.is_empty() and (_sky[-1] as Vector3i).y == (a as Vector3i).y:
				var l: Vector3i = _sky[-1]
				_sky[-1] = Vector3i(l.x, l.y, l.z + (a as Vector3i).z)
			else:
				_sky.append(a)
		_top = maxi(_top, by + cell.y)
		_used += cell.x * cell.y
		return Rect2i(bx, by, cell.x, cell.y)

	## What holds the atlas (perf_probe): canvas items showing images, how many of them out of sight, asked already.
	func _refs_census() -> String:
		var holding := 0
		var unseen := 0
		var asked := 0
		var nohost := 0
		var px := 0
		for id in refs:
			var e: Array = refs[id]
			if (e[1] as Dictionary).is_empty():
				continue
			holding += 1
			for key in e[1]:
				if slots.has(key):
					px += (slots[key] as Rect2i).get_area()
			var h: CanvasItem = (e[3] as WeakRef).get_ref() as CanvasItem if e.size() > 3 and e[3] != null else null
			if h == null and e[2] != null:
				h = (e[2] as WeakRef).get_ref() as CanvasItem
			if h == null or not h.is_inside_tree():
				nohost += 1
				continue
			if not in_sight(h, Rect2(Vector2.ZERO, (h as Control).size if h is Control else Vector2.ZERO), PAD):
				unseen += 1
				if int(e[0]) <= int(_asked.get(id, -1)):
					asked += 1
		return "%d items hold images (%.0f%% of the atlas), %d out of sight (%d asked, not drawn since), %d without a host" % [
			holding, px * 100.0 / float(_asize.x * _asize.y), unseen, asked, nohost]

	func _largest_free() -> Vector2i:
		var best := Vector2i.ZERO
		for r in _free:
			if (r as Rect2i).get_area() > best.x * best.y:
				best = (r as Rect2i).size
		return best

	func _release(cell: Rect2i) -> void:
		_free.append(cell)
		_used -= cell.get_area()

	## Drops the images no canvas item shows any more (by what each one's commands last drew), so their room is used
	## again. Returns how many.
	func _evict() -> int:
		var live := {}
		for id in refs.keys():
			var e: Array = refs[id]
			var w: Variant = e[2]
			if w != null and (w as WeakRef).get_ref() == null:  # (freed: its commands are gone)
				refs.erase(id)
				continue
			for key in e[1]:
				live[key] = true
		var n := 0
		for key in slots.keys():
			if live.has(key):
				continue
			var s: Rect2i = slots[key]
			_release(Rect2i(s.position - Vector2i(1, 1), _cell(s.size)))
			slots.erase(key)
			made.erase(key)
			n += 1
		for b in alts.keys():
			if not slots.has(alts[b]):
				alts.erase(b)
		evicted += n
		if n > 0:
			_coalesce()
			_lower_sky()
		if _squeeze and used() < 0.5:  # room again: what scrolls out of sight keeps its images
			_squeeze = false
		return n

	## Joins free rects that share a whole edge (neighbours dropped together: a row of labels of one height), so an image
	## a little larger than each of them finds room before the atlas would have to start over.
	func _coalesce() -> void:
		for _pass in 4:
			var joined := false
			for axis in [0, 1]:
				_free.sort_custom(func(a: Rect2i, b: Rect2i) -> bool:
					var a0 := a.position.y if axis == 0 else a.position.x
					var b0 := b.position.y if axis == 0 else b.position.x
					if a0 != b0:
						return a0 < b0
					var a1 := a.size.y if axis == 0 else a.size.x
					var b1 := b.size.y if axis == 0 else b.size.x
					if a1 != b1:
						return a1 < b1
					return (a.position.x if axis == 0 else a.position.y) < (b.position.x if axis == 0 else b.position.y))
				var out: Array = []
				for r in _free:
					var c: Rect2i = r
					if not out.is_empty():
						var q: Rect2i = out[-1]
						if axis == 0 and q.position.y == c.position.y and q.size.y == c.size.y and q.end.x == c.position.x:
							out[-1] = Rect2i(q.position, Vector2i(q.size.x + c.size.x, q.size.y))
							joined = true
							continue
						if axis == 1 and q.position.x == c.position.x and q.size.x == c.size.x and q.end.y == c.position.y:
							out[-1] = Rect2i(q.position, Vector2i(q.size.x, q.size.y + c.size.y))
							joined = true
							continue
					out.append(c)
				_free = out
			if not joined:
				break

	## Gives the free rects that lie right under the skyline back to it (a column whose top images were dropped is
	## lower again), so the room at the top of the atlas is one piece again.
	func _lower_sky() -> void:
		var changed := true
		while changed:
			changed = false
			for i in range(_free.size() - 1, -1, -1):
				var r: Rect2i = _free[i]
				if _sky_flat(r.position.x, r.end.x, r.end.y):
					_sky_set(r.position.x, r.end.x, r.position.y)
					_free.remove_at(i)
					changed = true
		_top = 0
		for sg in _sky:
			_top = maxi(_top, (sg as Vector3i).y)

	## Whether the skyline stands at `y` all along x0 … x1.
	func _sky_flat(x0: int, x1: int, y: int) -> bool:
		for sg in _sky:
			var sk: Vector3i = sg
			if sk.x + sk.z > x0 and sk.x < x1 and sk.y != y:
				return false
		return true

	## The skyline at `y` along x0 … x1 (neighbours at one height merged).
	func _sky_set(x0: int, x1: int, y: int) -> void:
		var out: Array = []
		for sg in _sky:
			var sk: Vector3i = sg
			var e := sk.x + sk.z
			if e <= x0 or sk.x >= x1:
				out.append(sk)
				continue
			if sk.x < x0:
				out.append(Vector3i(sk.x, sk.y, x0 - sk.x))
			out.append(Vector3i(maxi(sk.x, x0), y, mini(e, x1) - maxi(sk.x, x0)))
			if e > x1:
				out.append(Vector3i(x1, sk.y, e - x1))
		_sky.clear()
		for o in out:
			if not _sky.is_empty() and (_sky[-1] as Vector3i).y == (o as Vector3i).y:
				var l: Vector3i = _sky[-1]
				_sky[-1] = Vector3i(l.x, l.y, l.z + (o as Vector3i).z)
			else:
				_sky.append(o)

	## The share of the atlas in use (0..1).
	func used() -> float:
		return float(_used) / float(_asize.x * _asize.y)

	func _on_post_draw() -> void:
		if _state == 1:  # the stage has rendered: copy into the atlas (un-premultiplied) next frame
			for n in _nodes:
				(n as Node).queue_free()
			_nodes.clear()
			var st := stage.get_texture()
			for r in _round:
				var c := TextureRect.new()
				var at := AtlasTexture.new()
				at.atlas = st
				at.region = Rect2(Vector2(r["at"]), Vector2(r["cell"] as Vector2i))
				c.texture = at
				c.material = _mat
				c.position = Vector2((r["slot"] as Rect2i).position)
				atlas.add_child(c)
				_nodes.append(c)
			if not _icons_new.is_empty():
				_copy_icons()
			atlas.render_target_update_mode = SubViewport.UPDATE_ONCE
			_state = 2
		elif _state == 2:  # the atlas has them: draw from it
			for n in _nodes:
				(n as Node).queue_free()
			_nodes.clear()
			for r in _round:
				var ws: Dictionary = waiting.get(r["key"], {})
				waiting.erase(r["key"])
				if int(r["gen"]) == _gen:  # (a reset in between: its place is gone)
					var s: Rect2i = r["slot"]
					slots[r["key"]] = Rect2i(s.position + Vector2i(1, 1), r["px"] as Vector2i)
					made[r["key"]] = [r["off"], r["pp"]]
					alts[r["base"]] = r["key"]
				for id in ws:
					_poke(ws[id])
			_round.clear()
			_landed = Engine.get_process_frames()
			for ic in _icon_round:  # those icons draw from the atlas now
				var e: Array = icons[ic[0]]
				if int(ic[2]) == _gen and e[2] == ic[1]:
					var at := e[0] as AtlasTexture
					at.atlas = atlas.get_texture()
					at.region = Rect2(Vector2((ic[1] as Rect2i).position) + Vector2(2, 2), Vector2(ICON, ICON))
			_icon_round.clear()
			_state = 0


## A Control that runs `paint` (a Callable(ci: CanvasItem)) as its drawing: what KitBake puts on its stage.
class KitPainter extends Control:
	var paint: Callable

	func _init(p: Callable = Callable(), s := Vector2.ZERO) -> void:
		paint = p
		size = s
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _draw() -> void:
		if paint.is_valid():
			paint.call(self)


## A StyleBoxFlat drawn from the bake atlas, nine-sliced (a whole panel costs no draw call of its own beside its kit
## neighbours). The StyleBoxFlat it wraps (`flat`) stays the description: code reads and edits it (Kit.flat_of), an
## edit redraws and re-bakes. `host`: the panel it is drawn on (its sub-pixel offset).
class KitBox extends StyleBox:
	var flat: StyleBoxFlat
	var host: WeakRef

	func _init(f: StyleBoxFlat = null) -> void:
		flat = f
		if f != null:
			_margins()
			f.changed.connect(_on_flat_changed)

	## The wrapped style's margins (content margins, else its border widths), so a container lays out as with it.
	func _margins() -> void:
		for side in [SIDE_LEFT, SIDE_TOP, SIDE_RIGHT, SIDE_BOTTOM]:
			var v := flat.get_margin(side)
			if get_content_margin(side) != v:
				set_content_margin(side, v)

	## An edit of the wrapped style (a border, a content margin, a colour): its margins follow, the panel redraws.
	func _on_flat_changed() -> void:
		_margins()
		emit_changed()

	func _draw(ci: RID, rect: Rect2) -> void:
		var h: Object = host.get_ref() if host != null else null
		if not SELF.draw_flat(ci, rect, flat, h as CanvasItem, self):
			flat.draw(ci, rect)


## A realm's flag (FlagView: a field, a division, an emblem, a frame) drawn from the bake atlas — its polygons cost 6–8
## draw calls a frame (the HUD's crest, the war bar's chips). Until its bake is ready the FlagView child draws it.
## `flag`: the flag dictionary (FlagView); setting it redraws.
class KitFlag extends Control:
	var flag: Dictionary = FlagView.DEFAULT.duplicate():
		set(v):
			flag = v
			if _vec != null:
				_vec.set("flag", v)
				_vec.queue_redraw()
			queue_redraw()
	var _vec: Control

	func _init(f: Dictionary = {}) -> void:
		if not f.is_empty():
			flag = f
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _ready() -> void:
		_vec = FlagView.new(flag)
		_vec.size = size
		_vec.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_vec)
		resized.connect(func(): _vec.size = size)

	func _draw() -> void:
		var f := flag.duplicate(true)
		var sz := size
		var make := func(_z: Vector2) -> Control:
			var v: Control = FlagView.new(f)
			v.size = sz
			return v
		var ok := SELF.draw_baked(self, "flag|%s|%.2f,%.2f" % [var_to_str(f), sz.x, sz.y], Rect2(Vector2.ZERO, sz), sz, make)
		if _vec != null and _vec.visible == ok:
			_vec.visible = not ok


## A still picture that another Control draws as vectors (a commander's bust: a gradient plate, a halo, the render
## through a rounded box and the frame — ~7 draw calls) drawn from the bake atlas instead, one textured rect among its
## kit neighbours. `vec`, the drawing Control, becomes its child (it takes over vec's name, place and size) and draws
## only until the bake has landed, or when it cannot be baked. `key`: everything that changes the picture's pixels
## (its size is added); `make`: (size) -> a fresh Control that draws the same picture at that size (null: the look
## has changed since, do not bake it). `keyer`: () -> what else the picture depends on that may change while it is
## shown (the portraits' era): read at each draw, part of the key, and a bake asked for under another value is dropped.
## Anything else must not change while shown: make a new KitStill for another look.
class KitStill extends Control:
	var key := ""
	var make := Callable()
	var keyer := Callable()
	var vec: Control

	func _init(v: Control = null, k := "", mk := Callable(), kr := Callable()) -> void:
		key = k
		make = mk
		keyer = kr
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		vec = v
		if v != null:
			if v.name != &"":  # (an unnamed Control keeps the engine's own name; an empty one is an error)
				name = v.name
			position = v.position
			size = v.size
			v.position = Vector2.ZERO
			add_child(v)
		resized.connect(func(): if vec != null: vec.size = size)

	func _draw() -> void:
		var k := key
		var mk := make
		if keyer.is_valid():
			var now := str(keyer.call())
			k += "|" + now
			var kr := keyer
			var m0 := make
			mk = func(z: Vector2) -> Control: return m0.call(z) if str(kr.call()) == now else null
		var ok := key != "" and make.is_valid() and size.x > 0.0 and size.y > 0.0 \
			and SELF.draw_baked(self, "still|%s|%.2f,%.2f" % [k, size.x, size.y], Rect2(Vector2.ZERO, size), size, mk)
		if vec != null and vec.visible == ok:
			vec.visible = not ok


## The StyleBoxFlat a panel wears, through a KitBox too (null when it has none).
static func flat_of(c: Control) -> StyleBoxFlat:
	var sb := c.get_theme_stylebox("panel")
	if sb is KitBox:
		return (sb as KitBox).flat
	return sb as StyleBoxFlat


## Puts `sb` on `c` as its panel style, drawn from the bake atlas (KitBox).
static func set_panel(c: Control, sb: StyleBoxFlat) -> void:
	var b := KitBox.new(sb)
	b.host = weakref(c)
	c.add_theme_stylebox_override("panel", b)


## A StyleBoxFlat's look as a bake key (everything that changes its pixels).
static func flat_key(sb: StyleBoxFlat) -> String:
	return "flat|%s|%s|%d,%d,%d,%d|%d,%d,%d,%d|%d%d%d%d|%.2f|%s|%d|%.1f,%.1f" % [sb.bg_color.to_html(), sb.border_color.to_html(),
		sb.border_width_left, sb.border_width_top, sb.border_width_right, sb.border_width_bottom,
		sb.corner_radius_top_left, sb.corner_radius_top_right, sb.corner_radius_bottom_right, sb.corner_radius_bottom_left,
		int(sb.draw_center), int(sb.anti_aliasing), int(sb.border_blend), sb.corner_detail, sb.anti_aliasing_size, sb.shadow_color.to_html(),
		sb.shadow_size, sb.shadow_offset.x, sb.shadow_offset.y]


## Draws a StyleBoxFlat from the bake atlas, nine-sliced (the parts between its corners are uniform); false when it
## cannot be (not baked yet, skewed, expanded; with `exact` false, too small to slice — a box whose size keeps
## changing would bake again and again): draw it as it is then.
static func draw_flat(ci: RID, rect: Rect2, sb: StyleBoxFlat, host: CanvasItem, owner: Object, exact := true) -> bool:
	var kb := KitBake.get_inst()
	if kb == null or sb == null or sb.skew != Vector2.ZERO or sb.expand_margin_left != 0.0 or sb.expand_margin_top != 0.0 \
			or sb.expand_margin_right != 0.0 or sb.expand_margin_bottom != 0.0:
		return false
	var sh := float(sb.shadow_size) if sb.shadow_color.a > 0.0 else 0.0
	var ox := absf(sb.shadow_offset.x) if sh > 0.0 else 0.0
	var oy := absf(sb.shadow_offset.y) if sh > 0.0 else 0.0
	var sp := KitBake.SLICE
	# a side whose border is wider than its neighbours' (a lip as a bottom border) bends its inner contour round the full
	# inner radius above the band: the corner then reaches that border + the radius − the narrower neighbour
	var bl := sb.border_width_left
	var br := sb.border_width_right
	var bt := sb.border_width_top
	var bb := sb.border_width_bottom
	var rl := maxi(sb.corner_radius_top_left, sb.corner_radius_bottom_left)
	var rr := maxi(sb.corner_radius_top_right, sb.corner_radius_bottom_right)
	var rt := maxi(sb.corner_radius_top_left, sb.corner_radius_top_right)
	var rb := maxi(sb.corner_radius_bottom_left, sb.corner_radius_bottom_right)
	var ml := float(maxi(maxi(rl, bl), bl + maxi(0, rl - mini(bt, bb)) if bl > mini(bt, bb) else 0)) + ox + sh + sp
	var mr := float(maxi(maxi(rr, br), br + maxi(0, rr - mini(bt, bb)) if br > mini(bt, bb) else 0)) + ox + sh + sp
	var mt := float(maxi(maxi(rt, bt), bt + maxi(0, rt - mini(bl, br)) if bt > mini(bl, br) else 0)) + oy + sh + sp
	var mb := float(maxi(maxi(rb, bb), bb + maxi(0, rb - mini(bl, br)) if bb > mini(bl, br) else 0)) + oy + sh + sp
	var m := Vector4.ZERO
	var size := rect.size
	var key := flat_key(sb)
	var look := key
	if rect.size.x >= ml + mr + 6.0:
		m.x = ml
		m.z = mr
		size.x = ml + mr + 4.0
	elif exact:
		key += "|w%.2f" % rect.size.x
	else:
		return false
	if rect.size.y >= mt + mb + 6.0:
		m.y = mt
		m.w = mb
		size.y = mt + mb + 4.0
	elif exact:
		key += "|h%.2f" % rect.size.y
	else:
		return false
	# made only when its bake is staged: a copy of the style as it is then (unless it has changed since)
	var make := func(z: Vector2) -> Control:
		if flat_key(sb) != look:
			return null
		var snap := sb.duplicate() as StyleBoxFlat
		return KitPainter.new(func(c: CanvasItem): snap.draw(c.get_canvas_item(), Rect2(Vector2.ZERO, z)), z)
	# the room round it: the box reaches past its rect only by its shadow and its antialiased edge
	var pad := sh + maxf(ox, oy) + sb.anti_aliasing_size + 2.0
	return kb.draw(ci, key, rect, size, make, owner, m, kb.frac_of(host, rect.position), Color.WHITE, true, host, pad)


## The glyphs of a Kit label from the bake atlas (Kit.label gives every label one): a label with the kit's outline and
## shadow costs four draw calls (shadow, outline and fill passes over two glyph textures) and splits its neighbours'
## batches; baked, it is one textured rect among them. A text that keeps changing (a timer, a growing stock) stays
## live: a text bakes once it has held for STILL_MS. The label keeps everything (text, size, theme, layout); while
## its bake shows it draws no glyph (visible_characters 0, counted after shaping so its size does not change) and
## this child draws the image in its place, in the same draw order. A one-line label's image covers only the part
## its glyphs reach (span_of).
class KitText extends Control:
	const STILL_MS := 1200
	var _armed := false

	func _init() -> void:
		name = "KitText"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		# the label's own rect: the renderer culls a canvas item by its rect against the clip (a 0×0 child vanished
		# with the whole text as soon as the label's top-left corner was scrolled out of a ScrollContainer)
		set_anchors_preset(Control.PRESET_FULL_RECT)

	func _enter_tree() -> void:
		var l := get_parent() as Label
		if l != null and not l.draw.is_connected(queue_redraw):
			l.draw.connect(queue_redraw)

	func _draw() -> void:
		var l := get_parent() as Label
		if l == null:
			return
		var kb := KitBake.get_inst()
		if kb == null or l.text.strip_edges() == "" or l.size.x <= 0.0 or get_viewport() != get_tree().root:
			_live(l)
			return
		var key := SELF.label_key(l)
		# a one-line label is made only as wide as its glyphs reach (a list row's title over half its width empty, a
		# bar's centred figure, took that much of the atlas too)
		var sp := span_of(l)
		var sz := Vector2(sp.y, l.size.y) if sp.y > 0.0 else l.size
		var make := func(_z: Vector2) -> Control:
			if not is_instance_valid(l) or SELF.label_key(l) != key:
				return null
			return KitText.clone(l, sp.y)
		var r := Rect2(Vector2(maxf(sp.x, 0.0), 0.0), sz)
		var f := kb.frac_of(self, r.position)
		# baked already (by this label or another one with the same look): at once; else once the text has held
		var ok := kb.draw(get_canvas_item(), "text|" + key, r, sz, make, self, Vector4.ZERO, f, l.self_modulate, false)
		if not ok and kb.held("text|" + key):
			ok = kb.draw(get_canvas_item(), "text|" + key, r, sz, make, self, Vector4.ZERO, f, l.self_modulate)
		elif not ok and not _armed:  # look again once it may have held still
			_armed = true
			kb.later(self, STILL_MS + 100)
		if ok:
			if l.visible_characters != 0:
				l.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
				l.visible_characters = 0
		else:
			_live(l)

	func _rearm() -> void:
		_armed = false
		queue_redraw()

	func _live(l: Label) -> void:
		if l.visible_characters != -1:
			l.visible_characters = -1

	## The part of `l` its glyphs reach, as (x, width): a single line's advance (as a Label shapes it: its font, size
	## and features), its outline and shadow, and a margin, at its alignment — left from x 0; centred, x a whole number
	## and the width the label's less twice x; right, x a whole number to the label's end — so that the line, laid
	## out in a label that wide, falls on the very pixels it does in `l` (Label places a line at int(width − line) / 2
	## centred, int(width − margin − line) right: shifted by whole pixels together with x). (-1, -1) when the whole
	## label is needed (wrapped or several lines, cut, right-to-left, or nearly as wide).
	static func span_of(l: Label) -> Vector2:
		var none := Vector2(-1.0, -1.0)
		var al := l.horizontal_alignment
		if al == HORIZONTAL_ALIGNMENT_FILL or l.autowrap_mode != TextServer.AUTOWRAP_OFF or l.text.contains("\n") \
				or l.lines_skipped != 0 or l.is_layout_rtl() or l.text_direction == Control.TEXT_DIRECTION_RTL:
			return none
		var font := l.get_theme_font("font")
		if font == null:
			return none
		var t := l.text.to_upper() if l.uppercase else l.text
		var adv := font.get_string_size(t, HORIZONTAL_ALIGNMENT_LEFT, -1.0, l.get_theme_font_size("font_size")).x * 1.02
		var sb := l.get_theme_stylebox("normal")
		var reach := float(l.get_theme_constant("outline_size")) + absf(float(l.get_theme_constant("shadow_offset_x"))) \
			+ float(l.get_theme_constant("shadow_outline_size")) + 8.0
		var big := l.size.x
		var x := 0.0
		var w := big
		match al:
			HORIZONTAL_ALIGNMENT_LEFT:
				w = ceilf((sb.get_margin(SIDE_LEFT) if sb != null else 0.0) + adv + reach)
			HORIZONTAL_ALIGNMENT_CENTER:
				x = floorf((big - ceilf(adv + 2.0 * reach)) * 0.5)
				w = big - 2.0 * x
			HORIZONTAL_ALIGNMENT_RIGHT:
				x = floorf(big - ceilf((sb.get_margin(SIDE_RIGHT) if sb != null else 0.0) + adv + reach))
				w = big - x
		if x < 0.0 or w > big - 24.0:
			return none
		return Vector2(x, w)

	## The label as it draws itself, for the stage (`span` > 0: only that wide — span_of's width).
	static func clone(l: Label, span := -1.0) -> Label:
		var c := l.duplicate(0) as Label
		for ch in c.get_children():
			c.remove_child(ch)
			ch.free()
		c.visible_characters = -1
		c.set_anchors_preset(Control.PRESET_TOP_LEFT)
		c.position = Vector2.ZERO
		c.size = Vector2(span, l.size.y) if span > 0.0 else l.size
		c.modulate = Color.WHITE
		c.self_modulate = Color.WHITE
		c.visible = true
		return c


## Everything that changes a label's pixels, as a bake key.
static func label_key(l: Label) -> String:
	var f := l.get_theme_font("font")
	var fid := f.resource_path if f != null and f.resource_path != "" else str(f.get_instance_id() if f != null else 0)
	return "%s|%s|%s|%d|%s|%s|%s|%d|%d,%d,%d|%d|%d%d|%d%d|%d|%d,%d|%d|%d" % [var_to_str(l.text), l.size, fid,
		l.get_theme_font_size("font_size"), l.get_theme_color("font_color").to_html(),
		l.get_theme_color("font_outline_color").to_html(), l.get_theme_color("font_shadow_color").to_html(),
		l.get_theme_constant("outline_size"), l.get_theme_constant("shadow_offset_x"), l.get_theme_constant("shadow_offset_y"),
		l.get_theme_constant("shadow_outline_size"), l.get_theme_constant("line_spacing"), l.horizontal_alignment,
		l.vertical_alignment, int(l.clip_text), l.text_overrun_behavior, l.autowrap_mode, l.max_lines_visible,
		l.lines_skipped, int(l.uppercase), l.justification_flags]


## `t` drawn from the shared icon sheet (KitBake.icon) when it is a rendered icon, else `t`.
static func atlas_of(t: Texture2D) -> Texture2D:
	if t == null or not t.resource_path.begins_with("res://assets/ui/icons/"):
		return t
	var kb := KitBake.get_inst()
	return kb.icon(t) if kb != null else t


## The icon `name` (icon_tex) from the shared icon sheet: what the kit's TextureRects show.
static func icon_atlas(name: String) -> Texture2D:
	return atlas_of(icon_tex(name))


## Draws layers made by `make` (a Callable returning a Control that draws them at `size`) from the bake atlas into
## `rect` on `ci` (a CanvasItem); see KitBake.draw. False while not baked (draw the vectors).
static func draw_baked(ci: CanvasItem, key: String, rect: Rect2, size: Vector2, make: Callable, m := Vector4.ZERO,
		queue := true) -> bool:
	var kb := KitBake.get_inst()
	if kb == null:
		return false
	return kb.draw(ci.get_canvas_item(), key, rect, size, make, ci, m, kb.frac_of(ci, rect.position), Color.WHITE, queue)


# ------------------------------------------------------------------ vector chrome and shapes

## Draws kit shapes: vector chrome (x, check, chevron_left/right, plus, minus, arrow_up, arrow_right, swap), stars,
## hex badges, the title plate, dots, discs, bars, the blueprint grid, the tooltip tail and the coach's ring, pointer
## and ghost finger (§4.12). Never a font glyph.
class KitShape extends Control:
	## Kinds drawn as vectors every frame (they animate by redrawing); every other kind comes from the bake atlas —
	## the rays too while small (a case card's still glow); the opening's big turning sunburst stays vectors (it would
	## take a sixth of the atlas, and its wedges' hard edges would be resampled as it turns).
	const LIVE := ["ring", "finger", "pointer"]
	const RAYS_BAKED := 256.0
	var kind := ""
	var face := Color.WHITE
	var lip := Color.BLACK
	var data := {}
	var vector := false  ## always the vectors (KitBake's stage copy)
	var _armed := false

	func _init(k := "", f := Color.WHITE) -> void:
		kind = k
		face = f
		mouse_filter = Control.MOUSE_FILTER_IGNORE

	func _rearm() -> void:
		_armed = false
		queue_redraw()

	## From the bake atlas.
	func _draw() -> void:
		# a bar: its boxes one by one from the atlas, sliced (_box) — a bar of any fill shares them; baked whole, each
		# bar's look (its fill) took an image of its full size
		if not vector and not LIVE.has(kind) and kind != "bar" and not (kind == "rays" and maxf(size.x, size.y) > RAYS_BAKED):
			var key := "shape|%s|%s|%s|%.2f,%.2f|%s" % [kind, face.to_html(), lip.to_html(), size.x, size.y, var_to_str(data)]
			var k_ := kind
			var f_ := face
			var l_ := lip
			var d_ := data.duplicate(true)
			var s_ := size
			var make := func(_z: Vector2) -> Control:
				var c := KitShape.new(k_, f_)
				c.lip = l_
				c.data = d_
				c.size = s_
				c.vector = true
				return c
			# a look that keeps changing (a bar filling up) is baked only once it holds still (KitBake.held)
			var kb := KitBake.get_inst()
			var settled := kind != "bar" or kb == null or kb.held(key)
			if SELF.draw_baked(self, key, Rect2(Vector2.ZERO, size), size, make, Vector4.ZERO, settled):
				return
			if not settled and not _armed and is_inside_tree():
				_armed = true
				kb.later(self, KitText.STILL_MS + 100)
		_paint()

	func _stroke(pts: PackedVector2Array, w: float, col: Color) -> void:
		draw_polyline(pts, col, w, true)
		for v in pts:
			draw_circle(v, w * 0.5, col, true, -1.0, true)

	## Unit-box polylines of each chrome glyph.
	func _chrome_lines() -> Array:
		match kind:
			"x":
				return [[Vector2(0.27, 0.27), Vector2(0.73, 0.73)], [Vector2(0.73, 0.27), Vector2(0.27, 0.73)]]
			"check":
				return [[Vector2(0.22, 0.52), Vector2(0.42, 0.72), Vector2(0.78, 0.3)]]
			"chevron_left":
				return [[Vector2(0.6, 0.22), Vector2(0.36, 0.5), Vector2(0.6, 0.78)]]
			"chevron_right":
				return [[Vector2(0.4, 0.22), Vector2(0.64, 0.5), Vector2(0.4, 0.78)]]
			"plus":
				return [[Vector2(0.5, 0.22), Vector2(0.5, 0.78)], [Vector2(0.22, 0.5), Vector2(0.78, 0.5)]]
			"minus":
				return [[Vector2(0.22, 0.5), Vector2(0.78, 0.5)]]
			"arrow_up":
				return [[Vector2(0.5, 0.8), Vector2(0.5, 0.24)], [Vector2(0.27, 0.46), Vector2(0.5, 0.23), Vector2(0.73, 0.46)]]
			"arrow_right":
				return [[Vector2(0.2, 0.5), Vector2(0.76, 0.5)], [Vector2(0.54, 0.27), Vector2(0.77, 0.5), Vector2(0.54, 0.73)]]
			"swap":
				return [[Vector2(0.2, 0.35), Vector2(0.76, 0.35)], [Vector2(0.62, 0.21), Vector2(0.78, 0.35), Vector2(0.62, 0.49)],
					[Vector2(0.8, 0.65), Vector2(0.24, 0.65)], [Vector2(0.38, 0.51), Vector2(0.22, 0.65), Vector2(0.38, 0.79)]]
		return []

	func _paint() -> void:
		var s := minf(size.x, size.y)
		var o := (size - Vector2(s, s)) * 0.5
		match kind:
			"x", "check", "chevron_left", "chevron_right", "plus", "minus", "arrow_up", "arrow_right", "swap":
				var k := s / 64.0
				var lines := _chrome_lines()
				var ink_w := maxf(4.0, 18.0 * k)
				var white_w := maxf(2.0, 9.0 * k)
				for ln in lines:
					var pts := PackedVector2Array()
					for v in ln:
						pts.append(o + (v as Vector2) * s)
					_stroke(pts, ink_w, INK)
				for ln in lines:
					var pts := PackedVector2Array()
					for v in ln:
						pts.append(o + (v as Vector2) * s)
					_stroke(pts, white_w, data.get("color", Color.WHITE))
			"star", "star_empty":
				_star(size * 0.5, s * 0.5 - 4.0, kind == "star")
			"hex":
				_hex_badge()
			"plate":
				_plate()
			"dot":  # INK ring 3 → white ring 4 → face; wider than tall («99+») it is a pill
				var rr := size.y * 0.5
				var ring := 7.0 if rr >= 16.0 else 6.0
				if size.x > size.y + 1.0:
					var sb := StyleBoxFlat.new()
					sb.anti_aliasing = true
					for layer in [[0.0, INK], [3.0, Color.WHITE], [ring, face]]:
						var d: float = layer[0]
						sb.bg_color = layer[1]
						sb.set_corner_radius_all(int(rr - d))
						draw_style_box(sb, Rect2(Vector2(d, d), size - Vector2(d, d) * 2.0))
				else:
					var c := size * 0.5
					draw_circle(c, rr, INK, true, -1.0, true)
					draw_circle(c, rr - 3.0, Color.WHITE, true, -1.0, true)
					draw_circle(c, rr - ring, face, true, -1.0, true)
			"bar":
				_bar()
			"disc":  # a round badge: INK ring → lip → face raised by the lip (the tray card's «ready» check)
				var c := size * 0.5
				var rr := minf(size.x, size.y) * 0.5
				draw_circle(c, rr, INK, true, -1.0, true)
				draw_circle(c, rr - 3.0, lip, true, -1.0, true)
				draw_circle(c - Vector2(0, rr * 0.1), rr - 3.0 - rr * 0.08, face, true, -1.0, true)
			"rays":  # the opening's sunburst behind a reward (§6 Лавка): wedges of `face` fading out from the centre
				var c := size * 0.5
				var rr := minf(size.x, size.y) * 0.5
				var n: int = data.get("n", 14)
				for i in n:
					var a0 := TAU * i / n
					var a1 := a0 + TAU / n * 0.5
					var pts := PackedVector2Array([c, c + Vector2.from_angle(a0) * rr, c + Vector2.from_angle(a1) * rr])
					var cols := PackedColorArray([Color(face, 0.55), Color(face, 0.0), Color(face, 0.0)])
					draw_polygon(pts, cols)
				draw_circle(c, rr * 0.42, Color(face, 0.22), true, -1.0, true)
			"ink_hex":  # a border ink's swatch (the Atelier): a map hex of land ringed by the ink, INK contour both sides
				_ink_hex()
			"grid":  # the blueprint backdrop: white 10 % lines every data.step px
				var step: float = data.get("step", 16.0)
				var col := Color(1, 1, 1, 0.1)
				var x := step
				while x < size.x:
					draw_line(Vector2(x, 0), Vector2(x, size.y), col, 1.0)
					x += step
				var y := step
				while y < size.y:
					draw_line(Vector2(0, y), Vector2(size.x, y), col, 1.0)
					y += step
			"tail":  # a tooltip / bubble tail pointing down (data.up = true: up; data.dir: "left" / "right" too)
				var dir: String = data.get("dir", "up" if data.get("up", false) else "down")
				var p: PackedVector2Array
				match dir:
					"up":
						p = PackedVector2Array([Vector2(0, size.y), Vector2(size.x, size.y), Vector2(size.x * 0.5, 0)])
					"left":
						p = PackedVector2Array([Vector2(size.x, 0), Vector2(size.x, size.y), Vector2(0, size.y * 0.5)])
					"right":
						p = PackedVector2Array([Vector2(0, 0), Vector2(0, size.y), Vector2(size.x, size.y * 0.5)])
					_:
						p = PackedVector2Array([Vector2(0, 0), Vector2(size.x, 0), Vector2(size.x * 0.5, size.y)])
				draw_colored_polygon(p, face)
				draw_line(p[0], p[2], INK, 4.0, true)
				draw_line(p[1], p[2], INK, 4.0, true)
				draw_circle(p[2], 2.0, INK, true, -1.0, true)
			"ring":  # the coach's ring: gold 6 between INK 3 strokes, its outer edge on the box (data.r its radius);
				# data.w: its band on each side (left, top, right, bottom; 12 at rest) — swollen out, the gold widens by
				# as much and the inner edge stays put
				var rr := minf(float(data.get("r", 36.0)), minf(size.x, size.y) * 0.5)
				var w: Array = data.get("w", [12.0, 12.0, 12.0, 12.0])
				var sb := StyleBoxFlat.new()
				sb.draw_center = false
				sb.anti_aliasing = true
				sb.corner_detail = 16
				for layer in [[0.0, INK], [3.0, ROLE["gold"][0]]]:
					var d: float = layer[0]
					sb.border_color = layer[1]
					sb.border_width_left = int(roundf(float(w[0]) - 2.0 * d))
					sb.border_width_top = int(roundf(float(w[1]) - 2.0 * d))
					sb.border_width_right = int(roundf(float(w[2]) - 2.0 * d))
					sb.border_width_bottom = int(roundf(float(w[3]) - 2.0 * d))
					sb.set_corner_radius_all(int(maxf(0.0, rr - d)))
					draw_style_box(sb, Rect2(Vector2(d, d), size - Vector2(d, d) * 2.0))
			"pointer":
				_pointer()
			"finger":  # the ghost finger: a white disc Ø64 in an INK 4 contour inside a gold ring (data.a: its alpha)
				var c := size * 0.5
				var a := float(data.get("a", 1.0))
				draw_arc(c, 38.0, 0.0, TAU, 64, Color(INK, a), 10.0, true)
				draw_arc(c, 38.0, 0.0, TAU, 64, Color(ROLE["gold"][0], a), 5.0, true)
				draw_circle(c, 32.0, Color(INK, a), true, -1.0, true)
				draw_circle(c, 28.0, Color(1, 1, 1, a), true, -1.0, true)

	## The coach's pointer: a chunky arrow toward data.dir — a gold face in an INK 4 contour over a 6 px lip of the
	## gold's lip colour (the lip stays below whatever way it points, as on every raised kit shape). No gloss: it is no
	## button. A head and a shaft, each a rounded convex polygon (round_poly takes no concave corners).
	func _pointer() -> void:
		var dir: Vector2 = data.get("dir", Vector2.DOWN)
		var k := minf(size.x, size.y) - 14.0  # the shape inside its contour (4 a side) and the lip (6)
		var c := size * 0.5 - Vector2(0, 3)
		var a := dir.angle()
		var parts: Array = []
		for unit in [[Vector2(-0.02, -0.44), Vector2(0.46, 0.0), Vector2(-0.02, 0.44)],
				[Vector2(-0.46, -0.16), Vector2(0.06, -0.16), Vector2(0.06, 0.16), Vector2(-0.46, 0.16)]]:
			var pts := PackedVector2Array()
			for v in unit:
				pts.append(c + (v as Vector2).rotated(a) * k)
			parts.append(SELF.round_poly(pts, 5.0))
		var lips: Array = []
		for p in parts:
			var q := PackedVector2Array()
			for v in p:
				q.append(v + Vector2(0, 6))
			lips.append(q)
		for p in lips + parts:
			for o in Geometry2D.offset_polygon(p, 4.0, Geometry2D.JOIN_ROUND):
				draw_colored_polygon(o, INK)
		for p in lips:
			draw_colored_polygon(p, ROLE["gold"][1])
		for p in parts:
			draw_colored_polygon(p, ROLE["gold"][0])

	func _star(c: Vector2, rr: float, full: bool) -> void:
		var body := SELF.star_points(c, rr)
		draw_colored_polygon(SELF.star_points(c + Vector2(0, 4), rr), Color(INK, SHADOW_A))
		_stroke(body + PackedVector2Array([body[0]]), 8.0, INK)
		draw_colored_polygon(body, INK)
		if full:
			var f: Color = ROLE["gold"][0]
			draw_colored_polygon(body, ROLE["gold"][1])
			draw_colored_polygon(SELF.star_points(c - Vector2(0, rr * 0.06), rr * 0.9), f)
			draw_colored_polygon(SELF.star_points(c - Vector2(0, rr * 0.2), rr * 0.45), SELF.gloss(f))
		else:
			draw_colored_polygon(body, CREAM_DEEP)
			draw_colored_polygon(SELF.star_points(c + Vector2(0, rr * 0.06), rr * 0.72), CREAM_DEEP.darkened(0.12))

	func _ink_hex() -> void:
		var rr := minf(size.x, size.y) * 0.5 - 3.0
		var c := size * 0.5
		var band := maxf(8.0, rr * 0.3)  # the ink's width: the ink is the point, the land only frames it
		var mid := rr - band * 0.5 - 3.0  # the band's centre line, inside the outer contour
		var raw := SELF.hex_points(c, rr)
		var shadow := PackedVector2Array()
		for v in SELF.round_poly(raw, 0.22 * rr):
			shadow.append(v + Vector2(0, 4))
		draw_colored_polygon(shadow, Color(INK, SHADOW_A))
		draw_colored_polygon(SELF.round_poly(raw, 0.22 * rr), INK)
		draw_colored_polygon(SELF.round_poly(SELF.hex_points(c, rr - band - 3.0), 0.22 * (rr - band)), data.get("land", GRASS.lerp(CREAM_ROW, 0.3)))
		var cols: Array = data.get("colors", [INK_TEXT])
		var ring := SELF.round_poly(SELF.hex_points(c, mid), 0.22 * mid)
		var pts := PackedVector2Array(ring)
		pts.append(ring[0])
		var pc := PackedColorArray()
		for i in pts.size():  # the colours run round the ring: c0 → c1 → … → c0
			var t := float(i) / float(pts.size() - 1) * cols.size()
			var a: Color = cols[int(t) % cols.size()]
			var b: Color = cols[(int(t) + 1) % cols.size()]
			pc.append(a.lerp(b, t - floorf(t)))
		draw_polyline_colors(pts, pc, band, true)
		for i in pts.size():
			draw_circle(pts[i], band * 0.5, pc[i], true, -1.0, true)
		# a white glint on the ink's upper left edge: it reads as a glossy line of ink, not a flat stripe
		var g := PackedVector2Array([ring[int(ring.size() * 0.55)], ring[int(ring.size() * 0.66)]])
		draw_line(g[0] + Vector2(0, -band * 0.2), g[1] + Vector2(0, -band * 0.2), Color(1, 1, 1, 0.55), maxf(2.0, band * 0.25), true)

	func _hex_badge() -> void:
		var rr := minf(size.x, size.y) * 0.5
		var c := size * 0.5
		var out := 3.0 if rr <= 24.0 else 4.0
		var raw := SELF.hex_points(c, rr)
		var body := SELF.round_poly(raw, 0.22 * rr)
		var inner := SELF.round_poly(SELF.inset_poly(raw, out), maxf(1.0, 0.22 * rr - out * 0.6))
		draw_colored_polygon(body, INK)
		draw_colored_polygon(inner, lip)
		var bottom := c.y + rr - out
		var face_poly := SELF.clip_below(inner, bottom - 0.14 * rr)
		draw_colored_polygon(face_poly, face)
		if data.get("gloss", true):
			var top := c.y - rr + out
			var g := SELF.clip_below(SELF.round_poly(SELF.inset_poly(raw, out + rr * 0.12), 0.18 * rr), top + (bottom - 0.14 * rr - top) * 0.42)
			if g.size() >= 3:
				draw_colored_polygon(g, SELF.gloss(face))

	func _plate() -> void:
		var w := size.x
		var h := size.y
		var p := 0.36 * h
		var raw := PackedVector2Array([Vector2(p, 0), Vector2(w - p, 0), Vector2(w, h * 0.5), Vector2(w - p, h), Vector2(p, h), Vector2(0, h * 0.5)])
		var body := SELF.round_poly(raw, 9.0)
		var shadow := PackedVector2Array()
		for v in body:
			shadow.append(v + Vector2(0, 8))
		draw_colored_polygon(shadow, Color(INK, SHADOW_A))
		draw_colored_polygon(body, INK)
		var inner := SELF.round_poly(SELF.inset_poly(raw, 5.0), 6.0)
		draw_colored_polygon(inner, lip)
		var face_poly := SELF.clip_below(inner, h - 5.0 - 9.0)
		draw_colored_polygon(face_poly, face)
		var g := SELF.clip_below(SELF.round_poly(SELF.inset_poly(raw, 11.0), 5.0), 11.0 + (h - 25.0) * 0.34)
		if g.size() >= 3:
			draw_colored_polygon(g, SELF.gloss(face))

	func _bar() -> void:
		var h := size.y
		var w := size.x
		var frac: float = clampf(float(data.get("frac", 0.0)), 0.0, 1.0)
		var paper: bool = data.get("paper", false)
		var o := StyleBoxFlat.new()
		o.anti_aliasing = true
		o.bg_color = INK
		o.set_corner_radius_all(int(h * 0.5))
		_box(o, Rect2(0, 0, w, h))
		var ih := h - 6.0
		var t := StyleBoxFlat.new()
		t.anti_aliasing = true
		t.bg_color = data.get("track", CREAM_DEEP if paper else SLATE_WELL)  # a bar on a dark scrim takes a lighter one
		t.set_corner_radius_all(int(ih * 0.5))
		_box(t, Rect2(3, 3, w - 6.0, ih))
		if frac <= 0.0:
			return
		var fw := maxf(ih, (w - 6.0) * frac)
		var f := StyleBoxFlat.new()
		f.anti_aliasing = true
		f.bg_color = face
		f.set_corner_radius_all(int(ih * 0.5))
		f.border_width_bottom = int(maxf(1.0, ih * 0.18))
		f.border_color = face.darkened(0.25)
		_box(f, Rect2(3, 3, fw, ih))
		if fw > ih:
			var gl := StyleBoxFlat.new()
			gl.anti_aliasing = true
			gl.bg_color = Color(1, 1, 1, 0.3)
			gl.set_corner_radius_all(int(ih * 0.15))
			_box(gl, Rect2(3.0 + ih * 0.35, 3.0 + ih * 0.12, fw - ih * 0.7, maxf(2.0, ih * 0.3)))

	## One of a bar's boxes: from the bake atlas (Kit.draw_flat) when drawn on the screen — sliced across when long
	## enough, so a fill of any such length uses the same image (a short one is made at its length); else (on the
	## stage, not baked yet) as it is.
	func _box(sb: StyleBoxFlat, r: Rect2) -> void:
		if not vector and SELF.draw_flat(get_canvas_item(), r, sb, self, self):
			return
		draw_style_box(sb, r)


static func hex_points(c: Vector2, r: float) -> PackedVector2Array:
	var p := PackedVector2Array()
	for i in 6:
		p.append(c + Vector2.from_angle(deg_to_rad(60.0 * i - 90.0)) * r)
	return p


static func star_points(c: Vector2, r: float) -> PackedVector2Array:
	var p := PackedVector2Array()
	for i in 10:
		p.append(c + Vector2.from_angle(deg_to_rad(36.0 * i - 90.0)) * (r if i % 2 == 0 else r * 0.48))
	return p


## A convex polygon with its corners replaced by arcs of radius `rad`.
static func round_poly(pts: PackedVector2Array, rad: float, seg := 6) -> PackedVector2Array:
	if rad <= 0.5 or pts.size() < 3:
		return pts
	var out := PackedVector2Array()
	var n := pts.size()
	for i in n:
		var p := pts[i]
		var a := pts[(i - 1 + n) % n]
		var b := pts[(i + 1) % n]
		var da := (a - p).normalized()
		var db := (b - p).normalized()
		var half := absf(da.angle_to(db)) * 0.5
		if half < 0.01 or half > PI * 0.5 - 0.001:
			out.append(p)
			continue
		var t := minf(rad / tan(half), minf(p.distance_to(a), p.distance_to(b)) * 0.5)
		var r := t * tan(half)
		var c := p + (da + db).normalized() * (r / sin(half))
		var p1 := p + da * t
		var p2 := p + db * t
		var a1 := (p1 - c).angle()
		var d := wrapf((p2 - c).angle() - a1, -PI, PI)
		for k in seg + 1:
			out.append(c + Vector2.from_angle(a1 + d * k / seg) * r)
	return out


## A convex polygon moved inwards by `d` (mitred: exact for straight edges).
static func inset_poly(pts: PackedVector2Array, d: float) -> PackedVector2Array:
	var r := Geometry2D.offset_polygon(pts, -d, Geometry2D.JOIN_MITER)
	return r[0] if not r.is_empty() else pts


## The part of a polygon above the line y = `y`.
static func clip_below(pts: PackedVector2Array, y: float) -> PackedVector2Array:
	var lo := Vector2(1e9, 1e9)
	var hi := Vector2(-1e9, -1e9)
	for v in pts:
		lo = lo.min(v)
		hi = hi.max(v)
	var box := PackedVector2Array([Vector2(lo.x - 4, lo.y - 4), Vector2(hi.x + 4, lo.y - 4), Vector2(hi.x + 4, y), Vector2(lo.x - 4, y)])
	var r := Geometry2D.intersect_polygons(pts, box)
	return r[0] if not r.is_empty() else PackedVector2Array()


# ------------------------------------------------------------------ the price plate (§4.1)

## An INK pill with [icon][number] per item. It lays its children out for any height and number size, so a button
## sizes it by its class. items: [[icon, text, short], …]; `short` (not enough) paints the number NEG. More than
## two items, or `compact`, show the scarcest one and a «+N» (§4.1: the full list goes to the tooltip).
class KitPrice extends Panel:
	var items: Array = []
	var compact := false
	var _rows: Array = []  # [{ic: TextureRect or null, l: Label, text, short}]
	var _more: Label
	var _sb: StyleBoxFlat

	func _init(its: Array = []) -> void:
		items = its
		name = "price"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		_sb = SELF.style(Color(INK, 0.85), 17, 0, INK, 0, 0)
		_sb.set_meta("kit_kind", "")
		SELF.set_panel(self, _sb)
		for it in items:
			var a: Array = it
			var ic: TextureRect = null
			var tex := SELF.icon_atlas(String(a[0])) if a.size() > 0 else null
			if tex != null:
				ic = TextureRect.new()
				ic.texture = tex
				ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
				add_child(ic)
			var short := a.size() > 2 and bool(a[2])
			var l := SELF.label(String(a[1]) if a.size() > 1 else "", 26, NEG if short else TEXT, true)
			l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			add_child(l)
			_rows.append({"ic": ic, "l": l, "text": l.text, "short": short})
		_more = SELF.label("", 24, TEXT, true)
		_more.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_more.visible = false
		add_child(_more)

	## The items shown: all of them (at most 2); of more, the first two with what is short first (callers order the
	## items scarcest first) and «+N»; when compact, the scarcest one alone.
	func _shown() -> Array:
		if _rows.size() <= 2 and not compact:
			return _rows
		var ranked: Array = _rows.filter(func(r): return r["short"]) + _rows.filter(func(r): return not r["short"])
		return ranked.slice(0, 1 if compact else 2)

	## The plate's width at a height, number size and icon side (nothing moves).
	func width_for(h: float, num: int, icon: float) -> float:
		return _walk(h, num, icon, false)

	## Lays the children out from the final height: icons centred, numbers at `num` (Rubik 900).
	func lay(h: float, num: int, icon: float) -> void:
		var w := _walk(h, num, icon, true)
		_sb.set_corner_radius_all(int(h * 0.5))
		custom_minimum_size = Vector2(w, h)
		size = Vector2(w, h)
		queue_redraw()

	func _walk(h: float, num: int, icon: float, apply: bool) -> float:
		var shown := _shown()
		var x := 3.0 if not shown.is_empty() and shown[0]["ic"] != null else roundf(h * 0.32)
		if apply:
			for r in _rows:
				var on: bool = shown.has(r)
				(r["l"] as Label).visible = on
				if r["ic"] != null:
					(r["ic"] as Control).visible = on
		for i in shown.size():
			var r: Dictionary = shown[i]
			if i > 0:
				x += 6.0 if icon > 24.5 else 4.0  # the small icons (an XS button's two prices) sit a little closer
			if r["ic"] != null:
				if apply:
					var ic: TextureRect = r["ic"]
					ic.size = Vector2(icon, icon)
					ic.position = Vector2(x, (h - icon) * 0.5)
				x += icon - 1.0  # the rendered icons have a transparent margin
			var tw := SELF.text_w(String(r["text"]), num, "d900", false)
			if apply:
				_num(r["l"], num, NEG if r["short"] else TEXT, x, tw, h)
			x += tw
		var more := _rows.size() - shown.size()
		if more > 0:
			var mt := "+%d" % more
			x += 6.0
			var mw := SELF.text_w(mt, num, "d900", false)
			if apply:  # «+1»: the other prices, softer than the numbers so it does not read as part of them
				_more.text = mt
				_more.visible = true
				_num(_more, num, SOFT, x, mw, h)
			x += mw
		elif apply:
			_more.visible = false
		return x + (maxf(9.0, roundf(h * 0.24)) if icon > 24.5 else 7.0)

	func _num(l: Label, num: int, col: Color, x: float, tw: float, h: float) -> void:
		SELF.style_label(l, num, col, true)
		l.add_theme_font_override("font", SELF.font("d900"))
		l.add_theme_font_size_override("font_size", num)
		l.position = Vector2(x, -1.0)
		l.size = Vector2(tw + SELF.outline_for(num), h)


# ------------------------------------------------------------------ the button (§4.1)

## Vector chrome a button can take as its main icon (`{icon: "arrow_up"}`), drawn by KitShape.
const CHROME_KINDS := ["x", "check", "chevron_left", "chevron_right", "plus", "minus", "arrow_up", "arrow_right", "swap",
	"star", "star_empty"]


## A volumetric button: hard shadow → INK body → face with lip → gloss; a centred row [icon][caption][price].
## The handler runs on release inside (like the old _is_tap); a disabled button shakes and emits `denied`.
## A picture another script puts at the left of the face (the hand picker's card art) moves the row right of it.
class KitButton extends Panel:
	signal denied
	signal released_early  ## a hold button let go before its time (the caller may say «hold it»)

	## class: [R, OUT, lip, shadow y, caption size, fit floor, icon size]
	const GEOM := {"L": [24, 5, 10, 8, 40, 30, 72], "M": [20, 4, 8, 6, 32, 26, 56], "S": [20, 4, 6, 6, 26, 22, 44], "XS": [14, 3, 5, 4, 24, 22, 32]}
	## the price plate in the row, by class: [h, NUM, NUM floor, icon] (§3.3: NUM_M 32 on L, NUM_S 26 on S; §3.5:
	## a 44–48 icon on L, 28 in a small price)
	const PRICE_GEOM := {"L": [52, 32, 26, 46], "M": [42, 28, 24, 36], "S": [36, 26, 22, 32], "XS": [32, 24, 22, 28]}
	## L / M with a price that does not fit beside the caption: the caption over the price, next to the icon.
	## [caption, caption floor, plate h, NUM, NUM floor, icon]
	const STACK_GEOM := {"L": [32, 26, 42, 28, 24, 38], "M": [26, 22, 34, 24, 22, 30]}

	var role := "info"
	var size_class := ""
	var caption := ""
	var icon := ""
	var price: Array = []
	var enabled := true
	var hold := false
	var hold_sec := 1.2
	var hit_pad := 0.0
	var round_btn := false
	var icon_scale := 0.0  ## icon-only buttons: icon side as a share of the height
	var content_left := 0.0  ## the content row starts right of this x (0: centred in the face)
	var cap_max := 0  ## the caption's largest size (0: the class's own); set by `unify` for sibling offers
	var price_max := 0  ## the price number's largest size (0: the class's own)
	var force_stack := false  ## L / M: the caption over the price even when one row would fit
	var last_plan := {}  ## the layout `_solve` picked last time (read by `unify`)
	var cb := Callable()
	var cap: Label
	var press := 0.0:
		set(v):
			press = v
			_apply_press()
	var _parts: Array = []  # [{node, kind, base, text}]
	var _down := false
	var _fired_frame := -1
	var _press_g := Vector2.ZERO  # where the finger went down, on the screen
	var _travel := 0.0  # how far it has moved since, at most
	var _scrolled := false  # a scroll around the button began to move during this press
	var _void := false  # the press turned into a swipe: its release does nothing
	var _hold_t := -1.0
	var _built := false
	var _in_rebuild := false
	var _scan_queued := false
	var _auto_left := 0.0  # right edge of a foreign picture at the left of the face
	var _sb := StyleBoxFlat.new()

	func _init() -> void:
		add_theme_stylebox_override("panel", StyleBoxEmpty.new())
		mouse_filter = Control.MOUSE_FILTER_STOP
		_sb.anti_aliasing = true
		_sb.corner_detail = 10
		gui_input.connect(_on_input)
		resized.connect(_layout)
		child_entered_tree.connect(_on_child_entered)
		set_process(false)

	func cls() -> String:
		if size_class != "":
			return size_class
		if size.y >= 104.0:
			return "L"
		if size.y >= 80.0:
			return "M"
		if size.y >= 52.0:
			return "S"
		return "XS"

	func geom() -> Array:
		var g: Array = (GEOM[cls()] as Array).duplicate()
		if round_btn:
			g[0] = int(size.y * 0.5)
		return g

	func face_color() -> Color:
		return SELF.face_of(role if enabled else "lock")

	func lip_color() -> Color:
		return SELF.lip_of(role if enabled else "lock")

	func _has_point(p: Vector2) -> bool:
		return Rect2(Vector2.ZERO, size).grow(hit_pad).has_point(p)

	## (Re)builds the content row; call after changing caption / icon / price / role / enabled.
	func rebuild() -> void:
		_in_rebuild = true
		for part in _parts:
			var old := part["node"] as Node
			if is_instance_valid(old):
				remove_child(old)
				old.queue_free()
		_parts.clear()
		cap = null
		var pieces: Array = []
		if icon != "":
			# a rendered icon, or vector chrome («Улучшить» with an arrow up, «Отмена» with ✕)
			if SELF.icon_tex(icon) == null and SELF.CHROME_KINDS.has(icon):
				pieces.append({"v": icon, "main": true})
			else:
				pieces.append({"i": icon, "main": true})
		pieces.append_array(SELF.split_icons(caption))
		for pc in pieces:
			var node: Control
			var kind := ""
			var main: bool = pc.get("main", false)
			if pc.has("t"):
				var l := SELF.label(String(pc["t"]), 24, TEXT, true)
				l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
				l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
				if cap == null:
					l.name = "cap"
					cap = l
				node = l
				kind = "text"
			elif pc.has("i"):
				var tr_ := TextureRect.new()
				tr_.texture = SELF.icon_atlas(String(pc["i"]))
				tr_.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
				tr_.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
				tr_.mouse_filter = Control.MOUSE_FILTER_IGNORE
				if not enabled:
					tr_.modulate = LOCK_MOD
				node = tr_
				kind = "main_icon" if main else "icon"
			else:
				node = SELF.KitShape.new(String(pc["v"]))
				kind = "main_icon" if main else "chrome"
			if main:
				node.name = "ic"
			add_child(node)
			_parts.append({"node": node, "kind": kind, "base": 0.0, "text": String(pc.get("t", ""))})
		if not price.is_empty():
			var pp := KitPrice.new(price)
			add_child(pp)
			_parts.append({"node": pp, "kind": "price", "base": 0.0})
		if cap == null:  # keep a 'cap' Label for callers that look for it
			cap = SELF.label("", 24)
			cap.name = "cap"
			cap.visible = false
			add_child(cap)
			_parts.append({"node": cap, "kind": "hidden", "base": 0.0})
		_built = true
		_in_rebuild = false
		_layout()
		queue_redraw()

	func _on_child_entered(n: Node) -> void:
		if _in_rebuild or _scan_queued or not (n is Control) or n is KitDecor:
			return
		_scan_queued = true
		_scan_foreign.call_deferred()

	## A picture another script added at the left of the face: the row moves right of it, and the content is laid
	## out again (that script may also have moved the caption).
	func _scan_foreign() -> void:
		_scan_queued = false
		var own := {}
		for part in _parts:
			own[part["node"]] = true
		var left := 0.0
		for ch in get_children():
			var c := ch as Control
			if c == null or own.has(c) or not c.visible or c is Label or c is KitDecor:
				continue
			var r := Rect2(c.position, c.size)
			if r.position.x >= -2.0 and r.position.x < size.x * 0.4 and r.end.x < size.x * 0.6 \
					and r.position.y < size.y * 0.7 and r.end.y > size.y * 0.3:
				left = maxf(left, r.end.x)
		_auto_left = left
		_layout()

	func _layout() -> void:
		if not _built or size.x <= 0.0:
			return
		var g := geom()
		var out: float = g[1]
		var lip: float = g[2]
		var face_h := size.y - 2.0 * out - lip
		var cy := out + face_h * 0.5
		var c := cls()
		var pad := 18.0 if c == "L" else (16.0 if c != "XS" else 10.0)
		var gap := 10.0 if c != "XS" else 6.0
		var inset := maxf(content_left, _auto_left)
		var left := maxf(pad, inset + gap) if inset > 0.0 else pad
		var right := size.x - pad
		var avail := maxf(0.0, right - left)
		var icon_side := minf(float(g[6]), face_h - 6.0)
		if icon_scale > 0.0:
			icon_side = size.y * icon_scale
		var all: Array = []
		for part in _parts:
			if part["kind"] != "hidden" and part["kind"] != "deco":
				all.append(part)
		for part in all:
			if part["kind"] == "text":
				var l0 := part["node"] as Label
				l0.text = String(part.get("text", ""))
				l0.clip_text = false
				l0.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
				l0.remove_theme_constant_override("line_spacing")
		var plan := _solve(all, avail, icon_side, gap, face_h)
		last_plan = plan
		var parts: Array = plan["parts"]
		var keep := {}
		for part in parts:
			keep[part["node"]] = true
		for part in all:
			(part["node"] as Control).visible = keep.has(part["node"])
		var s: int = plan["s"]
		var two: String = plan["two"]
		var stack: bool = plan["stack"]
		var clip_w: float = plan["clip_w"]
		var pw := 0.0
		for part in parts:
			if part["kind"] == "price":
				var kp := part["node"] as KitPrice
				kp.lay(float(plan["ph"]), int(plan["pn"]), float(plan["pi"]))
				pw = kp.size.x
		var total: float = plan["w"] if float(plan["w"]) >= 0.0 else _row_w(parts, s, icon_side, gap, pw)
		total = minf(total, avail)
		var x := left + (avail - total) * 0.5
		var only_text: bool = parts.size() == 1 and parts[0]["kind"] == "text"
		var lcy := cy  # the centre line of the caption row
		var price_pos := Vector2.ZERO
		var cap_x := -1.0  # stacked: where the caption row starts
		if stack:
			var lead := 0.0
			for part in parts:
				if part["kind"] == "main_icon":
					lead = icon_side + gap
			var cw: float = plan["cw"]
			var colw := maxf(cw, pw)
			var top := cy - (s * 1.2 + 2.0 + float(plan["ph"])) * 0.5
			lcy = top + s * 0.6
			price_pos = Vector2(x + lead + (colw - pw) * 0.5, top + s * 1.2 + 2.0)
			cap_x = x + lead + (colw - cw) * 0.5
		var started := false
		for part in parts:
			var n: Control = part["node"]
			var k := String(part["kind"])
			if stack and not started and k != "main_icon" and k != "price":
				x = cap_x
				started = true
			match k:
				"text":
					var l := n as Label
					SELF.style_label(l, s, TEXT, true)
					l.add_theme_font_size_override("font_size", s)
					if s < 22:
						l.add_theme_font_override("font", SELF.font("d800"))
					if two != "":
						l.text = two
						l.add_theme_constant_override("line_spacing", -int(s * 0.12))
					if clip_w >= 0.0:
						l.clip_text = true
						l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
					if only_text and not stack:
						# one caption: the label spans the face, centred (inside [left, right] with an inset or a cut)
						var span := inset > 0.0 or clip_w >= 0.0
						l.position = Vector2(left if span else 0.0, out)
						l.size = Vector2(avail if span else size.x, face_h)
					else:
						var tw: float = plan["two_w"] if two != "" else SELF.text_w(l.text, s, "d900" if s >= 26 else "d800")
						if clip_w >= 0.0:
							tw = minf(tw, clip_w)
						var lh := face_h if two != "" else s * 1.5
						l.position = Vector2(x, lcy - lh * 0.5)
						l.size = Vector2(tw, lh)
						x += tw + gap
				"main_icon":
					if parts.size() == 1 and inset <= 0.0:
						x = (size.x - icon_side) * 0.5  # an icon alone sits in the middle (a round chip is narrower than its pads)
					n.size = Vector2(icon_side, icon_side)
					n.position = Vector2(x, cy - icon_side * 0.5)
					x += icon_side + gap
				"icon", "chrome":
					var side := roundf(s * 1.25) if k == "icon" else roundf(s * 1.1)
					if parts.size() == 1:
						side = icon_side if icon_scale > 0.0 else minf(face_h * 0.62, float(g[6]))
						x = left + (avail - side) * 0.5 if inset > 0.0 else (size.x - side) * 0.5
					n.size = Vector2(side, side)
					n.position = Vector2(x, lcy - side * 0.5)
					x += side + gap
				"price":
					if stack:
						n.position = price_pos
					else:
						n.position = Vector2(x, cy - n.size.y * 0.5)
						x += n.size.x + gap
			part["base"] = n.position.y
		_apply_press()

	## A size step's top under a `unify` cap (never under the floor).
	func _top(base: int, cap_: int, floor_: int) -> int:
		return clampi(cap_, floor_, base) if cap_ > 0 else base

	func _plan(parts: Array, s: int, ph: float, pn: int, pi: float) -> Dictionary:
		return {"parts": parts, "s": s, "ph": ph, "pn": pn, "pi": pi, "two": "", "two_w": 0.0, "stack": false, "cw": 0.0,
			"clip_w": -1.0, "w": -1.0}

	## The largest layout that fits `avail` (docs/ui_style.md §4.1): the caption steps down to its class floor,
	## then the price's number; L / M put the price under the caption; XS keeps the prices and drops the caption
	## (§4.4: «prices or a short caption»); L / M wrap a long caption to two lines; legacy captions go on down to
	## 20; inline pictographs go, then the main icon; two prices become the scarcest one + «+1»; at the very end
	## the caption is cut with an ellipsis. The row never gets wider than `avail`.
	func _solve(all: Array, avail: float, icon_side: float, gap: float, face_h: float) -> Dictionary:
		var c := cls()
		var pp: KitPrice = null
		for part in all:
			if part["kind"] == "price":
				pp = part["node"]
				pp.compact = false
		var pg: Array = PRICE_GEOM[c]
		var ph := minf(float(pg[0]), face_h - 2.0)
		var pi := minf(float(pg[3]), ph)
		var p_steps := SELF.fit_steps(_top(int(pg[1]), price_max, int(pg[2])), int(pg[2]))
		var sets: Array = [all]
		var no_picto := all.filter(func(p): return p["kind"] != "icon" and p["kind"] != "chrome")
		if no_picto.size() < all.size():
			sets.append(no_picto)
		var bare := no_picto.filter(func(p): return p["kind"] != "main_icon")
		if not all.any(func(p): return p["kind"] == "text" or p["kind"] == "price"):
			return _plan(all, int(geom()[4]), ph, p_steps[0], pi)  # an icon-only button keeps its icon
		if bare.size() < no_picto.size():
			sets.append(bare)
		for parts in sets:
			var r := _solve_set(parts, avail, icon_side, gap, face_h, pp, ph, pi, p_steps)
			if not r.is_empty():
				return r
		if pp != null and pp._rows.size() > 1 and c == "XS":
			# XS (a card's button, §4.4: prices or a short caption): both prices with 24 icons before the scarcest alone
			for parts in [all.filter(func(p): return p["kind"] == "price" or p["kind"] == "main_icon"),
					all.filter(func(p): return p["kind"] == "price")]:
				for pn in p_steps:
					if _row_w(parts, FIT_FLOOR, icon_side, gap, pp.width_for(ph, pn, pi - 4.0)) <= avail:
						return _plan(parts, FIT_FLOOR, ph, pn, pi - 4.0)
		if pp != null and pp._rows.size() > 1:
			pp.compact = true
			for parts in sets:
				var r := _solve_set(parts, avail, icon_side, gap, face_h, pp, ph, pi, p_steps)
				if not r.is_empty():
					return r
		if pp != null:
			# no room for the caption at all: the price alone (both prices, then the scarcest + «+1»), rather than a
			# caption cut to a few letters
			var with_icon := all.filter(func(p): return p["kind"] == "price" or p["kind"] == "main_icon")
			var alone := all.filter(func(p): return p["kind"] == "price")
			for compact in ([false, true] if pp._rows.size() > 1 else [false]):
				pp.compact = compact
				for parts in [with_icon, alone]:
					for pn in p_steps:
						if _row_w(parts, FIT_FLOOR, icon_side, gap, pp.width_for(ph, pn, pi)) <= avail:
							return _plan(parts, FIT_FLOOR, ph, pn, pi)
		# nothing fits: the smallest sizes and a cut caption
		var last: Array = sets[-1]
		if pp != null:
			last = last.filter(func(p): return p["kind"] == "price")
		var pl := _plan(last, FIT_FLOOR, ph, p_steps[-1], pi)
		var has_price := last.any(func(p): return p["kind"] == "price")
		var pw := pp.width_for(ph, p_steps[-1], pi) if has_price else 0.0
		var texts := last.filter(func(p): return p["kind"] == "text")
		if not texts.is_empty():
			var rest := last.filter(func(p): return p["kind"] != "text")
			var rest_w := _row_w(rest, FIT_FLOOR, icon_side, gap, pw) - gap * maxf(0.0, rest.size() - 1)
			var room := avail - rest_w - gap * (last.size() - 1)
			pl["clip_w"] = maxf(0.0, room / texts.size())
			pl["w"] = avail
		return pl

	func _solve_set(parts: Array, avail: float, icon_side: float, gap: float, face_h: float, pp: KitPrice, ph: float,
			pi: float, p_steps: Array[int]) -> Dictionary:
		var c := cls()
		var g := geom()
		var cap_floor := int(g[5])
		var texts := parts.filter(func(p): return p["kind"] == "text")
		var pw0 := pp.width_for(ph, p_steps[0], pi) if pp != null else 0.0
		# the caption down its class steps
		var stack_only := force_stack and pp != null and STACK_GEOM.has(c) and not texts.is_empty()
		if not stack_only:
			for s in SELF.fit_steps(_top(int(g[4]), cap_max, cap_floor), cap_floor):
				if _row_w(parts, s, icon_side, gap, pw0) <= avail:
					return _plan(parts, s, ph, p_steps[0], pi)
		if pp != null:
			# then the price's number
			for pn in (p_steps if not stack_only else []):
				if _row_w(parts, cap_floor, icon_side, gap, pp.width_for(ph, pn, pi)) <= avail:
					return _plan(parts, cap_floor, ph, pn, pi)
			# L / M: the caption over the price, beside the icon
			if STACK_GEOM.has(c) and not texts.is_empty():
				var sg: Array = STACK_GEOM[c]
				var sph := float(sg[2])
				var spi := float(sg[5])
				var row := parts.filter(func(p): return p["kind"] != "price" and p["kind"] != "main_icon")
				var lead := icon_side + gap if parts.any(func(p): return p["kind"] == "main_icon") else 0.0
				for s in SELF.fit_steps(_top(int(sg[0]), cap_max, int(sg[1])), int(sg[1])):
					if s * 1.2 + 2.0 + sph > face_h - 2.0:
						continue
					var cw := _row_w(row, s, icon_side, gap, 0.0)
					for pn in SELF.fit_steps(_top(int(sg[3]), price_max, int(sg[4])), int(sg[4])):
						var w := lead + maxf(cw, pp.width_for(sph, pn, spi))
						if w <= avail:
							var pl := _plan(parts, s, sph, pn, spi)
							pl["stack"] = true
							pl["cw"] = cw
							pl["w"] = w
							return pl
			# XS: the prices alone
			if c == "XS" and not texts.is_empty():
				var only := parts.filter(func(p): return p["kind"] == "price" or p["kind"] == "main_icon")
				for pn in p_steps:
					if _row_w(only, cap_floor, icon_side, gap, pp.width_for(ph, pn, pi)) <= avail:
						return _plan(only, cap_floor, ph, pn, pi)
		elif (c == "L" or c == "M") and texts.size() == 1:
			# L / M: a long caption on two lines (L at 32, §4.1)
			var two := SELF.two_lines(String(texts[0]["text"]))
			if two.contains("\n"):
				var others := parts.filter(func(p): return p["kind"] != "text")
				for s in SELF.fit_steps(32 if c == "L" else 26, 22):
					if s * 1.2 * 2.0 > face_h + 6.0:
						continue
					var tw := 0.0
					for ln in two.split("\n"):
						tw = maxf(tw, SELF.text_w(ln, s, "d900" if s >= 26 else "d800"))
					var w := tw + (_row_w(others, s, icon_side, gap, 0.0) + gap if not others.is_empty() else 0.0)
					if w <= avail:
						var pl := _plan(parts, s, ph, p_steps[0], pi)
						pl["two"] = two
						pl["two_w"] = tw
						pl["w"] = w
						return pl
		# legacy captions go on below the class floor (to 20)
		var pwl := pp.width_for(ph, p_steps[-1], pi) if pp != null else 0.0
		for s in SELF.fit_steps(cap_floor, FIT_FLOOR):
			if s < cap_floor and _row_w(parts, s, icon_side, gap, pwl) <= avail:
				return _plan(parts, s, ph, p_steps[-1], pi)
		return {}

	func _row_w(parts: Array, s: int, icon_side: float, gap: float, price_w: float) -> float:
		var w := 0.0
		for part in parts:
			match String(part["kind"]):
				"text":
					w += SELF.text_w((part["node"] as Label).text.replace("\n", " "), s, "d900" if s >= 26 else "d800")
				"main_icon":
					w += icon_side
				"icon":
					w += roundf(s * 1.25)
				"chrome":
					w += roundf(s * 1.1)
				"price":
					w += price_w
		return w + gap * maxf(0.0, parts.size() - 1)

	func _apply_press() -> void:
		var lip: float = geom()[2]
		var dy := (lip - 2.0) * press
		for part in _parts:
			var n: Control = part["node"]
			if is_instance_valid(n):
				n.position.y = float(part["base"]) + dy
		queue_redraw()

	## The body's layers (hard shadow → INK body → face with its lip → gloss) at `sz`, `press` 0..1, on `ci`.
	static func paint_body(ci: CanvasItem, d: Dictionary, sz: Vector2, press_: float) -> void:
		var r: float = d["r"]
		var out: float = d["out"]
		var lip: float = d["lip"]
		var sh: float = d["sh"]
		var w := sz.x
		var h := sz.y
		var lip_now := lerpf(lip, 2.0, press_)
		var dy := lip - lip_now
		var face: Color = d["face"]
		var sb := StyleBoxFlat.new()
		sb.anti_aliasing = true
		sb.corner_detail = 10
		if press_ < 0.5 and sh > 0.0:
			sb.bg_color = Color(INK, SHADOW_A)
			sb.set_corner_radius_all(int(r))
			sb.border_width_bottom = 0
			ci.draw_style_box(sb, Rect2(0, sh, w, h))
		sb.bg_color = INK
		sb.set_corner_radius_all(int(r))
		sb.border_width_bottom = 0
		ci.draw_style_box(sb, Rect2(0, dy, w, h - dy))
		sb.bg_color = face
		sb.set_corner_radius_all(int(maxf(0.0, r - out)))
		sb.border_width_bottom = int(lip_now)
		sb.border_color = d["lipc"]
		var inner := Rect2(out, dy + out, w - 2.0 * out, h - dy - 2.0 * out)
		ci.draw_style_box(sb, inner)
		sb.border_width_bottom = 0
		var face_h := inner.size.y - lip_now
		if d["gloss"]:  # «unavailable» never has a gloss (§4.1), also on a lock button that answers
			var side: float = d["side"]
			sb.bg_color = SELF.gloss(face)
			sb.set_corner_radius_all(int(maxf(4.0, r - out - 6.0)))
			ci.draw_style_box(sb, Rect2(out + side, dy + out + 5.0, inner.size.x - 2.0 * side, maxf(4.0, face_h * 0.34)))

	## At rest the body comes from the bake atlas (KitBake), sliced sideways; pressed (a moment) it is drawn as vectors.
	func _draw() -> void:
		var g := geom()
		var r: float = g[0]
		var out: float = g[1]
		var lip: float = g[2]
		var w := size.x
		var h := size.y
		var lip_now := lerpf(lip, 2.0, press)
		var dy := lip - lip_now
		var face := face_color()
		var side := 12.0 if cls() == "L" else 8.0
		if round_btn:
			side = maxf(side, r * 0.45)
		var d := {"r": r, "out": out, "lip": lip, "sh": float(g[3]), "face": face, "lipc": lip_color(),
			"gloss": enabled and role != "lock", "side": side}
		var baked := false
		if press == 0.0:
			var mx := maxf(r, out + side + maxf(4.0, r - out - 6.0) if d["gloss"] else 0.0) + KitBake.SLICE
			var key := "btn|%s|%s|%.1f,%.1f,%.1f,%.1f,%.2f|%s|h%.2f" % [face.to_html(), (d["lipc"] as Color).to_html(), r, out, lip,
				d["sh"], side, str(d["gloss"]), h]
			var m := Vector4.ZERO
			var bs := size
			if w >= 2.0 * mx + 6.0:
				m = Vector4(mx, 0.0, mx, 0.0)
				bs.x = 2.0 * mx + 4.0
			else:
				key += "|w%.2f" % w
			var make := func(z: Vector2) -> Control: return KitPainter.new(func(c: CanvasItem): KitButton.paint_body(c, d, z, 0.0), z)
			baked = SELF.draw_baked(self, key, Rect2(Vector2.ZERO, size), bs, make, m)
		if not baked:
			paint_body(self, d, size, press)
		var inner := Rect2(out, dy + out, w - 2.0 * out, h - dy - 2.0 * out)
		var face_h := inner.size.y - lip_now
		if _hold_t > 0.0:
			var k := clampf(_hold_t / maxf(0.05, hold_sec), 0.0, 1.0)
			_sb.bg_color = Color(1, 1, 1, 0.75)
			_sb.set_corner_radius_all(int(minf(maxf(0.0, r - out), inner.size.x * k * 0.5)))
			draw_style_box(_sb, Rect2(inner.position, Vector2(inner.size.x * k, face_h)))

	func _process(delta: float) -> void:
		if _hold_t < 0.0:
			set_process(false)
			return
		_hold_t += delta
		queue_redraw()
		if _hold_t >= hold_sec:
			_hold_t = -1.0
			set_process(false)
			queue_redraw()
			if cb.is_valid():
				cb.call()

	## A scroll container around the button began to scroll (it tells every descendant, like BaseButton hears it):
	## once the finger has also left the tap slop, the press is a swipe and its release must not act — a CTA in the
	## card row would otherwise spend while the player only scrolls (§2). Jitter inside the slop still taps.
	func _notification(what: int) -> void:
		if what == NOTIFICATION_SCROLL_BEGIN and _down:
			_scrolled = true
			_check_swipe()

	func _check_swipe() -> void:
		if _void or not _scrolled or _travel <= SELF.TAP_SLOP:
			return
		_void = true
		_hold_t = -1.0
		set_process(false)
		queue_redraw()
		SELF.press_out(self)

	## At the release of a press: true when the press turned into a swipe (it ends without acting; the button has
	## already sprung back). The release position counts too: the last step of a fast swipe may have no motion event.
	func _ends_swipe(e: InputEvent) -> bool:
		_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
		_check_swipe()
		var swiped := _void
		_void = false
		_scrolled = false
		return swiped

	func _on_input(e: InputEvent) -> void:
		var is_press := false
		var is_release := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			is_press = e.pressed
			is_release = not e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			is_press = e.pressed
			is_release = not e.pressed
			pos = (e as InputEventScreenTouch).position
		elif e is InputEventMouseMotion or e is InputEventScreenDrag:
			if _down:
				_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
				_check_swipe()
			return
		else:
			return
		var frame := Engine.get_process_frames()
		if is_press:
			if _down:
				return  # the emulated mouse twin of a touch
			_down = true
			_press_g = SELF.screen_pos(self, e)
			_travel = 0.0
			_scrolled = false
			_void = false
			SELF.press_in(self)
			if hold and enabled:
				_hold_t = 0.0
				set_process(true)
		elif is_release:
			if _fired_frame == frame:
				return
			_fired_frame = frame
			var was_down := _down
			_down = false
			if was_down and _ends_swipe(e):
				return
			SELF.press_out(self)
			var inside := _has_point(pos)
			if hold:
				var was := _hold_t >= 0.0
				_hold_t = -1.0
				set_process(false)
				queue_redraw()
				if not enabled and inside:
					SELF.shake(self)
					denied.emit()
				elif was and inside:
					released_early.emit()  # released early: nothing happens (the caller may explain the hold)
				return
			if not inside:
				return
			if enabled:
				if cb.is_valid():
					cb.call()
			else:
				SELF.shake(self)
				denied.emit()


# ------------------------------------------------------------------ factories (§4)

## opts: icon, price ([[icon, text, short], …]), size ("L"/"M"/"S"/"XS"), cb, enabled, hold, hold_sec, filter, round,
## hit_pad, icon_scale.
static func button(parent: Node, rect: Rect2, role: String, caption: String, opts := {}) -> KitButton:
	var b := KitButton.new()
	b.role = role if ROLE.has(role) else "info"
	b.caption = caption
	b.icon = String(opts.get("icon", ""))
	b.price = opts.get("price", [])
	b.size_class = String(opts.get("size", ""))
	b.cb = opts.get("cb", Callable())
	b.enabled = bool(opts.get("enabled", true))
	b.hold = bool(opts.get("hold", false))
	b.hold_sec = float(opts.get("hold_sec", 1.2))
	b.round_btn = bool(opts.get("round", false))
	b.hit_pad = float(opts.get("hit_pad", 0.0))
	b.icon_scale = float(opts.get("icon_scale", 0.0))
	b.mouse_filter = int(opts.get("filter", Control.MOUSE_FILTER_STOP))
	b.position = rect.position
	b.size = rect.size
	if parent:
		parent.add_child(b)
	b.rebuild()
	return b


## Sibling offers (two passes, ×1 / ×10, two packs side by side) read as one set: after each button fits itself,
## all of them take the smallest caption and price sizes any of them needed, and the stacked layout if any needed it.
static func unify(buttons: Array) -> void:
	var bs: Array = buttons.filter(func(b): return b is KitButton and is_instance_valid(b))
	for _pass in 3:
		var s := 999
		var pn := 999
		var stack := false
		for b in bs:
			var pl: Dictionary = (b as KitButton).last_plan
			if pl.is_empty():
				continue
			s = mini(s, int(pl["s"]))
			pn = mini(pn, int(pl["pn"]))
			stack = stack or bool(pl["stack"])
		var same := true
		for b in bs:
			var pl: Dictionary = (b as KitButton).last_plan
			if pl.is_empty() or int(pl["s"]) != s or int(pl["pn"]) != pn or bool(pl["stack"]) != stack:
				same = false
		if same or s == 999:
			return
		for b in bs:
			var kb := b as KitButton
			kb.cap_max = s
			kb.price_max = pn
			kb.force_stack = stack
			kb._layout()


## A square (opens a screen) or round (acts on the map) icon button; optional caption plate under it.
static func icon_button(parent: Node, rect: Rect2, icon: String, role := "slate", round := false, caption := "", cb := Callable()) -> KitButton:
	var b := button(parent, rect, role, "", {"icon": icon, "round": round, "cb": cb, "icon_scale": 0.70 if round else 0.74,
		"size": "M" if rect.size.y >= 80.0 else "S", "hit_pad": maxf(0.0, (96.0 - rect.size.y) * 0.5)})
	if caption != "":
		icon_caption(b, caption)
	return b


## (Re)sets the caption plate of an icon button (a language switch calls it again; the old plate goes).
## Square: INK pill h 30, MICRO 22, 14 px over the bottom; round: SLATE_WELL pill h 32 with an INK 3 contour,
## LABEL 24, 10 px over the bottom. Both are kept 12 px from the screen edges (§4.2).
static func icon_caption(b: KitButton, caption: String) -> Panel:
	if b.has_meta("kit_caption"):
		var old: Variant = b.get_meta("kit_caption")
		if is_instance_valid(old):
			(old as Node).queue_free()
	var round := b.round_btn
	var plate := caption_pill(b, caption, 32.0 if round else 30.0, SLATE_WELL if round else Color(INK, 0.92), 24 if round else 22, 3 if round else 0)
	plate.name = "caption"
	b.set_meta("kit_caption", plate)
	place_caption(b)
	return plate


## Centres an icon button's caption plate under it, clamped 12 px inside the visible screen; call again when the
## viewport changes size.
static func place_caption(b: KitButton) -> void:
	if not b.has_meta("kit_caption"):
		return
	var plate: Variant = b.get_meta("kit_caption")
	if not is_instance_valid(plate):
		return
	var p := plate as Control
	var px := (b.size.x - p.size.x) * 0.5
	if b.is_inside_tree():
		var gx := b.get_global_rect().position.x
		var vis := b.get_viewport_rect()
		px = clampf(px, vis.position.x + 12.0 - gx, vis.end.x - 12.0 - gx - p.size.x)
	p.position = Vector2(px, b.size.y - (10.0 if b.round_btn else 14.0))


## Ø76 war button with a vector ✕ at the window's top-right corner.
static func close_button(panel: Control, cb: Callable) -> KitButton:
	var c := Vector2(panel.size.x - 40.0, 4.0)
	var b := button(panel, Rect2(c - Vector2(38, 38), Vector2(76, 76)), "war", "", {"round": true, "cb": cb, "size": "S", "hit_pad": 14.0})
	var x := KitShape.new("x")
	x.size = Vector2(42, 42)
	x.position = Vector2(17, 13)
	b.add_child(x)
	b._parts.append({"node": x, "kind": "deco", "base": 13.0})
	return b


## Ø76 info button with a chevron at the window's top-left corner.
static func back_button(panel: Control, cb: Callable) -> KitButton:
	var b := button(panel, Rect2(Vector2(2, -34), Vector2(76, 76)), "info", "", {"round": true, "cb": cb, "size": "S", "hit_pad": 14.0})
	var x := KitShape.new("chevron_left")
	x.size = Vector2(44, 44)
	x.position = Vector2(16, 12)
	b.add_child(x)
	b._parts.append({"node": x, "kind": "deco", "base": 12.0})
	return b


## A pointy-top hex badge (level, cost, energy, rarity) with a numeral.
static func hex_badge(parent: Node, center: Vector2, r: float, role: String, text := "", face := Color(0, 0, 0, 0)) -> KitShape:
	var f: Color = face if face.a > 0.0 else face_of(role)
	var s := KitShape.new("hex", f)
	s.lip = f.darkened(0.32) if face.a > 0.0 else lip_of(role)
	s.size = Vector2(r, r) * 2.0
	s.position = center - Vector2(r, r)
	if parent:
		parent.add_child(s)
	if text != "":
		var l := label(text, roundi(r * 1.05), TEXT, true)
		l.add_theme_font_size_override("font_size", fit_size(text, snap_size(r * 1.05), r * 1.6, "d900", FIT_FLOOR))
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.size = Vector2(r * 2.0, r * 2.0 - r * 0.14)
		l.position = Vector2(0, -r * 0.06)
		s.add_child(l)
	return s


## The hex title plate centred on the window's top edge (y = −42). `animate`: it drops in from −20 px after 60 ms
## (§3.6 POP_IN); a window replaced in the same frame passes false. `size`: TITLE 46, or HERO 64 for «Победа!» (the
## plate grows to h 104, still centred on the edge).
static func title_plate(panel: Control, text: String, role := "info", icon := "", animate := true, size := 46) -> KitShape:
	var h := 84.0 if size <= 46 else 104.0
	var has_icon := icon != "" and icon_tex(icon) != null
	var tw := text_w(text, size, "d900")
	var w := clampf(tw + 108.0 + (64.0 if has_icon else 0.0), 320.0, maxf(320.0, panel.size.x - 200.0))
	var s := KitShape.new("plate", face_of(role))
	s.lip = lip_of(role)
	s.size = Vector2(w, h)
	var y0 := -h * 0.5
	s.position = Vector2((panel.size.x - w) * 0.5, y0)
	panel.add_child(s)
	var tx := 54.0 + (64.0 if has_icon else 0.0)
	var l := label(text, size, TEXT, true)
	l.add_theme_font_size_override("font_size", fit_size(text, size, w - tx - 54.0, "d900", 32))
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.position = Vector2(tx, 0)
	l.size = Vector2(w - tx - 54.0, h - 12.0)
	s.add_child(l)
	if has_icon:
		var ic := TextureRect.new()
		ic.texture = icon_atlas(icon)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.size = Vector2(92, 92)
		ic.position = Vector2(-22, (h - 92.0) * 0.5 - 6.0)
		s.add_child(ic)
	var d := _dur(0.22)
	if animate and d > 0.0:
		s.position.y = y0 - 20.0
		s.modulate.a = 0.0
		var drop := s.create_tween().set_parallel()
		drop.tween_property(s, "position:y", y0, d).set_delay(0.06).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		drop.tween_property(s, "modulate:a", 1.0, d * 0.5).set_delay(0.06)
		passing_fade(s, drop)
	return s


## A notification dot on the parent's top-right corner: Ø40 with a number (MICRO 22; «99+» widens it to a pill),
## Ø26 without.
static func dot(parent: Control, n := -1, role := "war") -> KitShape:
	var s := KitShape.new("dot", face_of(role))
	parent.add_child(s)
	if n >= 0:
		var l := label("", 22, TEXT, true)
		l.name = "n"
		l.add_theme_font_override("font", font("d900"))  # MICRO is Rubik 900
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.position = Vector2(0, -1)
		s.add_child(l)
	set_dot(s, n)
	badge_pop(s)
	return s


## Sets the number of a dot made with one («99+» above 99, widened to a pill) and keeps the dot on its parent's
## top-right corner.
static func set_dot(s: KitShape, n: int) -> void:
	var l := s.get_node_or_null("n") as Label
	var d := 40.0 if l != null else 26.0
	var t := ("99+" if n > 99 else str(maxi(n, 0))) if l != null else ""
	var w := maxf(d, text_w(t, 22, "d900") + 14.0) if t.length() > 2 else d
	s.size = Vector2(w, d)
	s.pivot_offset = s.size * 0.5
	var parent := s.get_parent() as Control
	if parent != null:
		s.position = Vector2(parent.size.x - 4.0, 6.0) - s.size * 0.5
	if l != null:
		l.text = t
		l.size = s.size
	s.queue_redraw()


## A progress bar (§4.7): INK contour, track, fill with a darker bottom and a gloss strip, label inside.
static func bar(parent: Node, rect: Rect2, frac: float, role: String, text := "", on_paper := false) -> KitShape:
	var s := KitShape.new("bar", face_of(role) if ROLE.has(role) else face_of("info"))
	s.data = {"frac": frac, "paper": on_paper}
	s.position = rect.position
	s.size = rect.size
	if parent:
		parent.add_child(s)
	if text != "":
		var l := label(text, roundi(rect.size.y * 0.7), TEXT, true)
		l.add_theme_font_size_override("font_size", fit_size(text, snap_size(rect.size.y * 0.7), rect.size.x - 16.0, "d900", FIT_FLOOR))
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.size = rect.size
		l.name = "label"
		s.add_child(l)
	return s


static func set_bar(b: KitShape, frac: float, text := "") -> void:
	b.data["frac"] = frac
	b.queue_redraw()
	if text != "" and b.has_node("label"):
		(b.get_node("label") as Label).text = text


## A caption pill with a short white text: the plate of a square button (INK, h 30, MICRO 22) or the label under
## a round one (SLATE_WELL, INK 3 contour, h 32, LABEL 24), §4.2. (`Kit.pill` is the resource plate, §4.6.)
static func caption_pill(parent: Node, text: String, h := 30.0, face := Color(0, 0, 0, 0), size := 22, contour := 0) -> Panel:
	var p := Panel.new()
	var f: Color = face if face.a > 0.0 else Color(INK, 0.9)
	var sb := style(f, int(h * 0.5), contour, INK, 0, 0)
	sb.set_meta("kit_kind", "")
	set_panel(p, sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var l := label(text, size, TEXT, true)
	var fs := snap_size(size) if size >= 22 else size
	l.add_theme_font_size_override("font_size", fs)
	var kind := "d800" if fs < 22 or fs == 24 else "d900"  # LABEL 24 is Rubik 800, MICRO 22 and 26+ are Rubik 900
	l.add_theme_font_override("font", font(kind))
	var tw := text_w(text, fs, kind)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	p.size = Vector2(tw + 24.0 + 2.0 * contour, h)
	l.size = p.size
	l.position = Vector2(0, -1)
	p.add_child(l)
	if parent:
		parent.add_child(p)
	return p


# ------------------------------------------------------------------ the resource plate (§4.6)

## A sunken pill: hard shadow +4 → INK body (radius h/2) → SLATE_WELL face inset 4 → the storage fill from the left
## (SLATE_FILL, FULL when the warehouse is full) → a shade along the top of the face. Children: the icon `ic` (68,
## overhanging the left end by 10), the value `value` (NUM 32, Rubik 900) over the rate `rate` (LABEL 24), and for
## raivite the go XS «+» `plus` instead of the rate. A tap opens a tooltip with `tip_title` / `tip_text`.
class KitPill extends Control:
	var icon_name := ""
	var frac := 0.0
	var full := false
	var has_rate := true
	var value_size := 32  ## NUM_M 32; 28 when five plates share the bar
	var value_cap := 0  ## set_caps: the bar's common value size (0: none)
	var rate_cap := 0
	var tip_title := ""
	var tip_text := ""
	var ic: TextureRect
	var value: Label
	var rate: Label
	var plus: KitButton
	var _sb := StyleBoxFlat.new()
	var _tip_frame := -1

	func _init() -> void:
		name = "pill"
		mouse_filter = Control.MOUSE_FILTER_STOP
		_sb.anti_aliasing = true
		_sb.corner_detail = 12
		resized.connect(lay)

	## Stored amount (already formatted), the warehouse share 0..1 and whether it is full (FULL fill, WARN value).
	func set_value(text: String, f: float, is_full: bool) -> void:
		var changed := text != value.text or is_full != full
		frac = clampf(f, 0.0, 1.0)
		full = is_full
		if changed:
			value.text = text
			lay()
		queue_redraw()

	## The «+160/ч» line; `col` POS or NEG.
	func set_rate(text: String, col: Color) -> void:
		if not has_rate:
			return
		if text != rate.text:
			rate.text = text
			lay()
		rate.add_theme_color_override("font_color", col)

	## True when `text` fits the rate line at its floor (22): the bar drops «/ч» from every rate when one does not.
	func rate_fits(text: String) -> bool:
		return _w(text, 22, "d800") <= _geom()["avail"]

	## The sizes the current value / rate would fit at; the bar caps every plate to the smallest, so the numbers
	## of one bar share one size.
	func value_fit() -> int:
		return _fit(value.text, value_size, _geom()["avail"], "d900")

	func rate_fit() -> int:
		return _fit(rate.text, 24, _geom()["avail"], "d800") if has_rate else 24

	## Caps the value / rate sizes (0: no cap); lays out again only when they change.
	func set_caps(v: int, r: int) -> void:
		if v != value_cap or r != rate_cap:
			value_cap = v
			rate_cap = r
			lay()

	## Five plates share the bar from DL5 (value_size 28): a smaller icon and «+». The icon overhangs the left end by
	## 10; the text starts 6 px (compact: 4) right of the icon's visible edge, so a narrow crystal or sack leaves the
	## numbers more room than the round coin (which lands on §4.6's x+60). The go «+» sits on the right rim.
	func _geom() -> Dictionary:
		var compact := value_size < 32
		var side := 56.0 if compact else 68.0
		var ox := -10.0
		var pb := (42.0 if compact else 48.0) if plus != null else 0.0
		var tx := ox + side * SELF.icon_vis_right(ic.texture if ic != null else null) + (4.0 if compact else 6.0)
		var right := size.x - pb - 4.0 if plus != null else size.x - (7.0 if compact else 10.0)
		return {"side": side, "ox": ox, "tx": tx, "avail": maxf(10.0, right - tx), "pb": pb}

	## Glyph width plus one outline (the outline overlaps the margins a little; text_w counts two).
	func _w(text: String, s: int, kind: String) -> float:
		return SELF.text_w(text, s, kind, false) + SELF.outline_for(s)

	func _fit(text: String, base: int, avail: float, kind: String) -> int:
		for s in SELF.fit_steps(base, 22):
			if _w(text, s, kind) <= avail:
				return s
		return 22

	## Lays the children out from the size: value and rate between the icon and the right end (or the «+»).
	func lay() -> void:
		if value == null:
			return
		var g := _geom()
		var h := size.y
		var side: float = g["side"]
		var tx: float = g["tx"]
		var avail: float = g["avail"]
		ic.size = Vector2(side, side)
		ic.position = Vector2(float(g["ox"]), (h - side) * 0.5)
		var vs := _fit(value.text, value_size, avail, "d900")
		if value_cap > 0:
			vs = mini(vs, value_cap)
		SELF.style_label(value, vs, WARN if full else TEXT, true)
		value.add_theme_font_override("font", SELF.font("d900"))
		value.add_theme_font_size_override("font_size", vs)
		value.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		value.clip_text = _w(value.text, vs, "d900") > avail  # never past the plate (an ellipsis at worst)
		value.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		value.position = Vector2(tx, 3.0) if has_rate else Vector2(tx, 0.0)
		value.size = Vector2(avail, 38.0) if has_rate else Vector2(avail, h - 2.0)
		rate.visible = has_rate
		if has_rate:
			var col := rate.get_theme_color("font_color")
			var rs := _fit(rate.text, 24, avail, "d800")
			if rate_cap > 0:
				rs = mini(rs, rate_cap)
			SELF.style_label(rate, rs, col, true)
			rate.add_theme_font_override("font", SELF.font("d800"))
			rate.add_theme_font_size_override("font_size", rs)
			rate.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			rate.clip_text = _w(rate.text, rs, "d800") > avail
			rate.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
			rate.position = Vector2(tx, 38.0)
			rate.size = Vector2(avail, 26.0)
		if plus != null:
			var pb: float = g["pb"]
			plus.size = Vector2(pb, pb)
			plus.position = Vector2(size.x - pb - 2.0, (h - pb) * 0.5)  # its contour on the plate's INK rim
		queue_redraw()

	static func _box(ci: CanvasItem, r: Rect2, col: Color, rad: float) -> void:
		var sb := StyleBoxFlat.new()
		sb.anti_aliasing = true
		sb.corner_detail = 12
		sb.bg_color = col
		sb.set_corner_radius_all(int(rad))
		ci.draw_style_box(sb, r)

	## The body: hard shadow +4 → INK (radius h/2) → the SLATE_WELL face inset 4.
	static func paint_base(ci: CanvasItem, sz: Vector2) -> void:
		var r := sz.y * 0.5
		_box(ci, Rect2(0, 4, sz.x, sz.y), Color(INK, SHADOW_A), r)
		_box(ci, Rect2(0, 0, sz.x, sz.y), INK, r)
		_box(ci, Rect2(4, 4, sz.x - 8.0, sz.y - 8.0), SLATE_WELL, r - 4.0)

	## Sunken: the rim of the body casts a shade along the top of the face (`face`, radius `rad`).
	static func paint_shade(ci: CanvasItem, face: Rect2, rad: float) -> void:
		var sb := StyleBoxFlat.new()
		sb.anti_aliasing = true
		sb.corner_detail = 12
		sb.draw_center = false
		sb.border_width_top = 4
		sb.border_color = Color(INK, 0.5)
		sb.set_corner_radius_all(int(rad))
		ci.draw_style_box(sb, face)

	## The three layers (body, storage fill, shade) come from the bake atlas (KitBake), sliced sideways; the fill's
	## width is kept to a quarter pixel.
	func _draw() -> void:
		var w := size.x
		var h := size.y
		var r := h * 0.5
		var face := Rect2(4, 4, w - 8.0, h - 8.0)
		var m := float(int(r)) + KitBake.SLICE
		var sz := size
		var bs := Vector2(2.0 * m + 4.0, h) if w >= 2.0 * m + 6.0 else size
		var sl := Vector4(m, 0, m, 0) if bs.x < w else Vector4.ZERO
		var key := "pill|h%.2f" % h + ("" if sl.x > 0.0 else "|w%.2f" % w)
		var mk := func(z: Vector2) -> Control: return KitPainter.new(func(c: CanvasItem): KitPill.paint_base(c, z), z)
		if not SELF.draw_baked(self, key, Rect2(Vector2.ZERO, sz), bs, mk, sl):
			paint_base(self, sz)
		if frac > 0.0:
			var fw := roundf(maxf(face.size.y, face.size.x * frac) * 4.0) / 4.0
			var col := FULL if full else SLATE_FILL
			var rad := r - 4.0
			var fm := float(int(rad)) + KitBake.SLICE
			var fs := Vector2(fw, face.size.y)
			var fbs := Vector2(2.0 * fm + 4.0, fs.y) if fw >= 2.0 * fm + 6.0 else fs
			var fsl := Vector4(fm, 0, fm, 0) if fbs.x < fw else Vector4.ZERO
			var fkey := "pillfill|%s|h%.2f" % [col.to_html(), fs.y] + ("" if fsl.x > 0.0 else "|w%.2f" % fw)
			var fmk := func(z: Vector2) -> Control: return KitPainter.new(func(c: CanvasItem): KitPill._box(c, Rect2(Vector2.ZERO, z), col, rad), z)
			if not SELF.draw_baked(self, fkey, Rect2(face.position, fs), fbs, fmk, fsl):
				_box(self, Rect2(face.position, fs), col, rad)
		var sm := float(int(r - 4.0)) + KitBake.SLICE
		var sbs := Vector2(2.0 * sm + 4.0, face.size.y) if face.size.x >= 2.0 * sm + 6.0 else face.size
		var ssl := Vector4(sm, 0, sm, 0) if sbs.x < face.size.x else Vector4.ZERO
		var skey := "pillshade|h%.2f" % face.size.y + ("" if ssl.x > 0.0 else "|w%.2f" % face.size.x)
		var smk := func(z: Vector2) -> Control: return KitPainter.new(func(c: CanvasItem): KitPill.paint_shade(c, Rect2(Vector2.ZERO, z), r - 4.0), z)
		if not SELF.draw_baked(self, skey, face, sbs, smk, ssl):
			paint_shade(self, face, r - 4.0)

	func _gui_input(e: InputEvent) -> void:
		var up: bool = (e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT \
			and not e.is_pressed()) or (e is InputEventScreenTouch and not e.is_pressed())
		if not up or tip_title == "":
			return
		var f := Engine.get_process_frames()
		if f == _tip_frame or not Rect2(Vector2.ZERO, size).grow(6.0).has_point(e.position):
			return  # the emulated mouse twin of a touch, or a drag that ended elsewhere
		_tip_frame = f
		SELF.tooltip(self, tip_title, tip_text)


## A resource plate at `rect` (h 70). opts: rate (false: no rate line, the value centred), value_size (32 / 28),
## plus (a Callable: the go XS «+» at the right end, raivite only).
static func pill(parent: Node, rect: Rect2, icon: String, opts := {}) -> KitPill:
	var p := KitPill.new()
	p.icon_name = icon
	p.has_rate = bool(opts.get("rate", true))
	p.value_size = int(opts.get("value_size", 32))
	p.position = rect.position
	p.size = rect.size
	p.ic = TextureRect.new()
	p.ic.name = "icon"
	p.ic.texture = icon_atlas(icon)
	p.ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	p.ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	p.ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.add_child(p.ic)
	p.value = label("—", 32, TEXT, true)
	p.value.name = "value"
	p.add_child(p.value)
	p.rate = label("", 24, POS, true)
	p.rate.name = "rate"
	p.add_child(p.rate)
	var cb: Callable = opts.get("plus", Callable())
	if cb.is_valid():
		p.plus = button(p, Rect2(rect.size.x - 56.0, 11, 48, 48), "go", "", {"icon": "plus", "size": "XS", "cb": cb, "hit_pad": 12.0})
		p.plus.name = "plus"
	if parent:
		parent.add_child(p)
	p.lay()
	return p


## A vertical two-stop gradient texture (the HUD's top scrim, sky backdrops).
static func vgradient(top: Color, bottom: Color) -> GradientTexture2D:
	var g := Gradient.new()
	g.set_color(0, top)
	g.set_color(1, bottom)
	var t := GradientTexture2D.new()
	t.gradient = g
	t.width = 4
	t.height = 64
	t.fill_from = Vector2(0, 0)
	t.fill_to = Vector2(0, 1)
	return t


## A horizontal two-stop gradient texture (the card row's right-edge fade).
static func hgradient(left: Color, right: Color) -> GradientTexture2D:
	var t := vgradient(left, right)
	t.width = 64
	t.height = 4
	t.fill_to = Vector2(1, 0)
	return t


# ------------------------------------------------------------------ the tray card (§4.4)

const LOCK_ART := Color(0.45, 0.47, 0.52)  ## a closed card's art (§4.4)

## A tray card (§4.4, 180×172). Everything is drawn by `body` (hard shadow +5 → INK R 20 → SLATE face with a lip 6),
## which lifts by 6 px when the card is selected: the art in the top 172×104 window (`art`, clipped to its rounded
## top) on its backdrop, an INK divider, the name on a scrim at the art's bottom; a hex badge top-left, a round chip
## top-right, a dot; the bottom zone (y 112–162) holds one XS button (`cta`) or one stat line. The card passes input
## on (a drag still scrolls the row): a tap on the chip runs `chip_cb`, a tap anywhere else on the body (not on the
## button) opens a tooltip with the title and `details`.
class KitCard extends Panel:
	const W := 180.0
	const H := 172.0
	const CORNER_IN := 2.0  ## the corner badge / chips keep this far inside the card's sides (they stand out upwards)
	var title := ""
	var details := ""
	var body: Panel
	var art: Panel
	var pic: Control  ## the backdrop and the picture (dimmed together when locked)
	var name_label: Label
	var cta: KitButton
	var chip: Control
	var chip_cb := Callable()
	var tap_cb := Callable()  ## a tap on the body runs this instead of the tooltip (a card that opens its own screen)
	var _press_at := Vector2(-1, -1)
	var _press_g := Vector2.ZERO  # where the finger went down, on the screen
	var _travel := 0.0  # how far it has moved on the screen since, at most
	var _press_frame := -1
	var _tap_frame := -1

	func _init() -> void:
		name = "card"
		add_theme_stylebox_override("panel", StyleBoxEmpty.new())
		mouse_filter = Control.MOUSE_FILTER_PASS
		custom_minimum_size = Vector2(W, H)
		size = custom_minimum_size
		size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		gui_input.connect(_on_input)

	## A tap, not a swipe: the travel is measured on the screen, because the card scrolls along with the finger and
	## its local positions barely change during a swipe of the row.
	func _on_input(e: InputEvent) -> void:
		var pos := Vector2.ZERO
		var pressed := false
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pos = (e as InputEventMouseButton).position
			pressed = e.pressed
		elif e is InputEventScreenTouch:
			pos = (e as InputEventScreenTouch).position
			pressed = e.pressed
		elif e is InputEventMouseMotion or e is InputEventScreenDrag:
			if _press_at.x >= 0.0:
				_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
			return
		else:
			return
		if pressed:
			var pf := Engine.get_process_frames()
			if pf != _press_frame:  # not the emulated mouse twin of the same touch (it comes in the same frame)
				_press_frame = pf
				_press_g = SELF.screen_pos(self, e)
				_travel = 0.0
			_press_at = pos
			return
		var from := _press_at
		_press_at = Vector2(-1, -1)
		_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
		var f := Engine.get_process_frames()
		if f == _tap_frame or from.x < 0.0 or _travel > SELF.TAP_SLOP or not Rect2(Vector2.ZERO, size).has_point(pos):
			return  # the emulated mouse twin of a touch, or a swipe of the row
		if cta != null and cta.visible and Rect2(body.position + cta.position, cta.size).has_point(pos):
			return  # the button acts on its own
		_tap_frame = f
		if chip != null and chip.visible and Rect2(body.position + chip.position, chip.size).grow(6.0).has_point(pos):
			if not (chip is KitButton) and chip_cb.is_valid():
				chip_cb.call()
			return
		if tap_cb.is_valid():
			tap_cb.call()
			return
		SELF.tooltip(self, title, details)


## A tray card (§4.4) — see KitCard. `art_tex` is cover-cropped into the art window, or, with opts.art_side, drawn
## as an icon of that side centred at opts.art_y (default 42) on the backdrop. opts:
##   backdrop: "sky" (default: the sky gradient over a grass strip) | "blueprint" | "team" (+ team: Color) | "cream"
##   art_node: a Control laid into the art window (172×104 local coordinates) over the picture
##   badge: the text of the top-left hex badge (R 22, centre 16, 16); badge_role (info)
##   tag: a short text on an INK pill standing out of the top-left corner instead of a badge («7/12»)
##   corner: {icon, fill}: a round status chip Ø44 on the top-left corner instead of a badge (peace, war, pact)
##   chip: {node: Control} (a portrait, clipped round) | {plus: true} (a go «+» button) | {icon: name, fill} |
##         {btn: {icon, role, caption}, count} (a round XS button: «i», a swap; `count`, a stock like «×3», on an INK
##         plate over its bottom); chip_cb. The corners stand out of the top edge, never out of the sides.
##   tag_r: {text, role}: a short text on a pill of the role's face (or SLATE_WELL) standing out of the top-right
##          corner instead of a chip (an opinion «−10»)
##   dot: the role of a dot on the card's corner; dot_n: its number (-1: none)
##   timer: a time left («1ч 59м», WARN with the hourglass) on a line over the name (a busy card whose button pays)
##   art_bar: {frac, role}: an S bar along the art's bottom, under the name
##   cta: {role, caption, icon, price ([[icon, text, short]] ≤ 2), cb, enabled, reason, short_reason} → an XS
##        button at (6, 114, 168, 46); without a cb it opens the card's tooltip; a disabled one shows `reason` when
##        tapped; with `short_reason` (not enough of something, §4.1) it keeps its role but its tap shakes and shows
##        that instead of acting
##   stat: {icon, text, bar_frac, bar_role, check} → icon 36 + NUM_S 26, an optional S bar at y 146, a go check
##   locked: dark art + a lock 56; the cta becomes lock XS with a lock and opts.lock_caption («УР3»), its tap shows
##           opts.reason
##   selected: a brass outline 5 and a 6 px lift
##   details: the tooltip text of a tap on the body; tap_cb: runs instead of that tooltip
static func card(art_tex: Texture2D, title: String, opts := {}) -> KitCard:
	var c := KitCard.new()
	c.title = title
	c.details = String(opts.get("details", ""))
	c.tap_cb = opts.get("tap_cb", Callable())
	var sel: bool = opts.get("selected", false)
	var locked: bool = opts.get("locked", false)
	var b := Panel.new()
	b.name = "body"
	b.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.size = Vector2(KitCard.W, KitCard.H)
	var sb := style(SLATE, 20, 5 if sel else 4, face_of("brass") if sel else INK, 5, 6)
	set_panel(b, sb)
	b.position.y = -6.0 if sel else 0.0
	c.add_child(b)
	c.body = b
	b.add_child(KitDecor.new())  # the lip (child 0)
	var o := float(sb.border_width_left)
	# ---- the art window
	var aw := Panel.new()
	aw.name = "art"
	aw.position = Vector2(o, o)
	aw.size = Vector2(KitCard.W - 2.0 * o, 108.0 - o)
	aw.mouse_filter = Control.MOUSE_FILTER_IGNORE
	aw.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	var kind := String(opts.get("backdrop", "sky"))
	var team: Color = opts.get("team", face_of("info"))
	var asb := StyleBoxFlat.new()
	asb.bg_color = {"blueprint": BLUEPRINT, "team": team, "cream": CREAM}.get(kind, SKY_LOW)
	asb.anti_aliasing = true
	asb.corner_detail = 8
	asb.corner_radius_top_left = int(20.0 - o)
	asb.corner_radius_top_right = int(20.0 - o)
	set_panel(aw, asb)
	b.add_child(aw)
	c.art = aw
	var w := aw.size.x
	var h := aw.size.y
	var pic := Control.new()
	pic.name = "pic"
	pic.size = aw.size
	pic.mouse_filter = Control.MOUSE_FILTER_IGNORE
	aw.add_child(pic)
	c.pic = pic
	match kind:
		"sky":
			pic.add_child(_card_rect(vgradient(SKY_TOP, SKY_LOW), Rect2(0, 0, w, h)))
			var grass := ColorRect.new()
			grass.color = GRASS
			grass.position = Vector2(0, h - 30.0)
			grass.size = Vector2(w, 30.0)
			grass.mouse_filter = Control.MOUSE_FILTER_IGNORE
			pic.add_child(grass)
		"blueprint":
			var grid := KitShape.new("grid")
			grid.size = aw.size
			pic.add_child(grid)
		"team":
			pic.add_child(_card_rect(vgradient(team.lightened(0.15), team.darkened(0.2)), Rect2(0, 0, w, h)))
	# the name's size first: a two-line name (22) takes the art's lower half, so an icon art moves up and shrinks to
	# end above its glyphs (side 56 at y 30), never under them
	var bar_d: Dictionary = opts.get("art_bar", {})
	# the glyphs get the window less 4 px a side; their outline may spill into that margin («Металлургия» fits at 22)
	var nw := w - 8.0
	var ns := fit_size(title, 26, nw, "d900", 22, false)
	var long := text_w(title, ns, "d900", false) > nw
	# a timer line («1ч 59м», opts.timer) stands over the name, which then keeps to one line
	var timer_t := String(opts.get("timer", ""))
	var two := long and timer_t == "" and title.strip_edges().contains(" ")  # two lines at 22; one long word is cut
	if long:
		ns = 22
	var stacked := two or timer_t != ""  # two lines of text over the art's bottom
	var art_side := float(opts.get("art_side", 0.0))
	var art_y := float(opts.get("art_y", 42.0))
	if stacked and art_side > 0.0:
		art_side = minf(art_side, 56.0 if timer_t == "" else 52.0)
		art_y = minf(art_y, 30.0 if timer_t == "" else 28.0)
	if art_tex != null:
		var side := art_side
		if side > 0.0:
			var cy := art_y
			var ic := _card_rect(atlas_of(art_tex), Rect2((w - side) * 0.5, cy - side * 0.5, side, side))
			ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			pic.add_child(ic)
		else:
			var cover := _card_rect(art_tex, Rect2(0, 0, w, h))
			cover.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
			pic.add_child(cover)
	var node: Control = opts.get("art_node")
	if node != null:
		pic.add_child(node)
	if locked:
		pic.modulate = LOCK_ART
		# the lock 56 in the middle of a cover art; beside an icon art it sits on the icon's lower right, so the
		# dimmed icon still reads (a lock over a helmet hid all but its crest)
		var side := art_side
		var lc := Vector2(w * 0.5, 42.0)
		if side > 0.0 and art_tex != null:
			lc = Vector2(w * 0.5, art_y) + Vector2(side * 0.36, side * 0.18)
		var lk := _card_rect(icon_atlas("lock"), Rect2(lc - Vector2(28, 28), Vector2(56, 56)))
		lk.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		aw.add_child(lk)
	# ---- the name on its scrim (an S bar under it with art_bar)
	var name_bottom := h - (28.0 if not bar_d.is_empty() else 3.0)
	if kind == "cream":
		# on paper a long INK ramp turns into a muddy grey band: a short ramp, then a solid strip under the glyphs
		var fh := font("d900").get_height(ns)
		var strip_top := name_bottom - (fh * 2.0 - 4.0 if stacked else fh) - 2.0
		aw.add_child(_card_rect(vgradient(alpha(INK, 0.0), alpha(INK, 0.9)), Rect2(0, strip_top - 10.0, w, 10.0)))
		var strip := ColorRect.new()
		strip.name = "strip"
		strip.color = alpha(INK, 0.9)
		strip.position = Vector2(0, strip_top)
		strip.size = Vector2(w, h - strip_top)
		strip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		aw.add_child(strip)
	else:
		var sh := minf(h, (h - name_bottom) + (ns * 1.25) * (2.0 if stacked else 1.0) + 18.0)
		aw.add_child(_card_rect(vgradient(alpha(INK, 0.0), alpha(INK, 0.9)), Rect2(0, h - sh, w, sh)))
	var nl := label(title, ns, TEXT, true)
	nl.name = "name"
	nl.add_theme_font_override("font", font("d900"))  # CARD: Rubik 900 down to 22
	nl.add_theme_font_size_override("font_size", ns)
	nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nl.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	if two:
		nl.autowrap_mode = TextServer.AUTOWRAP_WORD
		nl.max_lines_visible = 2
		nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS  # a third line is cut with «…», never dropped
		nl.add_theme_constant_override("line_spacing", -4)
	elif long:
		nl.clip_text = true
		nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	nl.position = Vector2(4, name_bottom - 64.0)
	nl.size = Vector2(nw, 64.0)
	aw.add_child(nl)
	c.name_label = nl
	if timer_t != "":
		# the time left (§3.2 WARN: time) with the hourglass, centred on the line over the name
		var fh := font("d900").get_height(ns)
		var tw := text_w(timer_t, 22, "d900")
		var row := Control.new()
		row.name = "timer"
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.size = Vector2(26.0 + 4.0 + tw, 28.0)
		row.position = Vector2(roundf((w - row.size.x) * 0.5), roundf(name_bottom - fh - 28.0 + 6.0))
		var hg := _card_rect(icon_atlas("hourglass"), Rect2(0, 1, 26, 26))
		hg.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		row.add_child(hg)
		var tl := label(timer_t, 22, WARN, true)
		tl.name = "time"
		tl.add_theme_font_override("font", font("d900"))
		tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		tl.position = Vector2(30, -1)
		tl.size = Vector2(tw, 28)
		row.add_child(tl)
		aw.add_child(row)
	if not bar_d.is_empty():
		# on the INK scrim a SLATE_WELL track (and the INK contour) vanish, so an empty bar would not read: SLATE_HI
		var ab := bar(aw, Rect2(8, h - 24.0, w - 16.0, 16.0), float(bar_d.get("frac", 0.0)), String(bar_d.get("role", "go")))
		ab.name = "art_bar"
		ab.data["track"] = SLATE_HI
	var div := ColorRect.new()  # INK 3 px under the art
	div.color = INK
	div.position = Vector2(o, 108.0)
	div.size = Vector2(KitCard.W - 2.0 * o, 3.0)
	div.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.add_child(div)
	# ---- the bottom zone: one XS button or one stat line
	var ct: Dictionary = opts.get("cta", {})
	if locked and opts.has("lock_caption"):
		ct = {"role": "lock", "caption": String(opts["lock_caption"]), "icon": "lock", "enabled": false,
			"reason": String(opts.get("reason", ""))}
	if not ct.is_empty():
		var en: bool = ct.get("enabled", true)
		var cb: Callable = ct.get("cb", Callable())
		var btn := button(b, Rect2(6, 114, 168, 46), String(ct.get("role", "go")), String(ct.get("caption", "")),
			{"icon": String(ct.get("icon", "")), "price": ct.get("price", []), "enabled": en, "size": "XS",
			"filter": Control.MOUSE_FILTER_PASS})
		btn.cb = cb if cb.is_valid() else func(): SELF.tooltip(btn, title, c.details)
		var short_why := String(ct.get("short_reason", ""))
		if short_why != "":  # «Не хватает»: the role stays, the tap shakes and says what is missing (§4.1)
			btn.cb = func():
				SELF.shake(btn)
				SELF.tooltip(btn, title, short_why)
		var why := String(ct.get("reason", ""))
		if why != "":
			btn.denied.connect(func(): SELF.tooltip(btn, title, why))
		c.cta = btn
	else:
		var st: Dictionary = opts.get("stat", {})
		if not st.is_empty():
			_card_stat(b, st)
	# ---- corners: badge or tag top-left, chip top-right, dot. They stand out of the top edge only: sideways they
	# keep CORNER_IN inside the card, so the corners of two neighbours (12 px apart) never read as one pair
	var ci := KitCard.CORNER_IN
	if opts.has("badge"):
		hex_badge(b, Vector2(ci + 19.0, 16), 22, String(opts.get("badge_role", "info")), String(opts["badge"]))
	elif opts.has("tag"):
		# a counter pill standing out of the corner like the badge, so it covers little of the art
		var tg := caption_pill(b, String(opts["tag"]), 32.0, INK, 24)
		tg.name = "tag"
		tg.position = Vector2(ci, -6)
	elif opts.has("corner"):
		_card_ring(b, Rect2(ci, -6, 44, 44), opts["corner"]).name = "corner"
	var chd: Dictionary = opts.get("chip", {})
	var chip_r := Rect2(KitCard.W - ci - 44.0, -6, 44, 44)  # Ø44 centred on (156, 16)
	if chd.get("plus", false):
		c.chip = button(b, chip_r, "go", "", {"icon": "plus", "round": true, "size": "XS", "filter": Control.MOUSE_FILTER_PASS,
			"cb": opts.get("chip_cb", Callable()), "hit_pad": 8.0})
	elif chd.has("btn"):
		var bd: Dictionary = chd["btn"]
		var cbtn := button(b, chip_r, String(bd.get("role", "info")), String(bd.get("caption", "")),
			{"icon": String(bd.get("icon", "")), "round": true, "size": "XS", "filter": Control.MOUSE_FILTER_PASS,
			"cb": opts.get("chip_cb", Callable()), "hit_pad": 8.0, "icon_scale": 0.62 if bd.has("icon") else 0.0})
		cbtn.name = "chip"
		c.chip = cbtn
		if chd.has("count"):
			# how many the button has left («×3»): an INK plate (h 28, MICRO 22) 10 px over its bottom, like a square
			# button's caption plate (§4.2), kept inside the card's side
			var cp := caption_pill(b, String(chd["count"]), 28.0, Color(INK, 0.92), 22)
			cp.name = "chip_count"
			cp.position = Vector2(minf(chip_r.get_center().x - cp.size.x * 0.5, KitCard.W - ci - cp.size.x), chip_r.end.y - 10.0)
	elif chd.has("node") or chd.has("icon"):
		c.chip = _card_ring(b, chip_r, chd)
		c.chip_cb = opts.get("chip_cb", Callable())
	elif opts.has("tag_r"):
		# a short value pill standing out of the top-right corner (an opinion): the role's face, or the slate well
		var td: Dictionary = opts["tag_r"]
		var role := String(td.get("role", ""))
		var tr_ := caption_pill(b, String(td.get("text", "")), 36.0, face_of(role) if ROLE.has(role) else SLATE_WELL, 26, 3)
		tr_.name = "tag_r"
		tr_.position = Vector2(KitCard.W - ci - tr_.size.x, -6)
	if opts.has("dot"):
		var d := dot(b, int(opts.get("dot_n", -1)), String(opts["dot"]))
		d.name = "dot"
		d.position = Vector2(KitCard.W - ci - d.size.x, 6.0 - d.size.y * 0.5)  # inside the card's side too
	return c


## A TextureRect stretched over `r` (backdrops, scrims, pictures) that ignores the mouse.
static func _card_rect(tex: Texture2D, r: Rect2) -> TextureRect:
	var t := TextureRect.new()
	t.texture = tex
	t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	t.stretch_mode = TextureRect.STRETCH_SCALE
	t.mouse_filter = Control.MOUSE_FILTER_IGNORE
	t.position = r.position
	t.size = r.size
	return t


## A round chip Ø44 on a card's corner (§4.4): an INK 3 ring on SLATE_WELL, inside it — clipped round — a portrait
## ({node}) or an icon 32 ({icon}) on SKY_LOW or on `fill` (a status colour). PASS: a drag still scrolls the row.
static func _card_ring(b: Control, r: Rect2, chd: Dictionary) -> Panel:
	var ring := Panel.new()
	ring.name = "chip"
	var rsb := style(SLATE_WELL, 22, 3, INK, 3, 0)
	rsb.set_meta("kit_kind", "")
	set_panel(ring, rsb)
	ring.position = r.position
	ring.size = r.size
	ring.mouse_filter = Control.MOUSE_FILTER_PASS
	b.add_child(ring)
	var inner := Panel.new()  # the picture inside the ring, clipped round
	var isb := StyleBoxFlat.new()
	var fill: Color = chd.get("fill", CLEAR)
	isb.bg_color = fill if fill.a > 0.0 else SKY_LOW
	isb.anti_aliasing = true
	isb.set_corner_radius_all(19)
	set_panel(inner, isb)
	inner.position = Vector2(3, 3)
	inner.size = Vector2(38, 38)
	inner.clip_children = CanvasItem.CLIP_CHILDREN_AND_DRAW
	inner.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ring.add_child(inner)
	if chd.has("node"):
		var pn: Control = chd["node"]
		pn.position = Vector2(-5, -3)  # a little larger than the circle: the portrait's own frame stays outside
		pn.size = Vector2(48, 50)
		inner.add_child(pn)
	elif chd.has("icon"):
		var ic := _card_rect(icon_atlas(String(chd["icon"])), Rect2(3, 3, 32, 32))
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		inner.add_child(ic)
	return ring


## The stat line of a tray card's bottom zone: icon 36 + NUM_S 26 (fit to 22), an optional S bar at y 146, an
## optional go check at the right end.
static func _card_stat(b: Control, st: Dictionary) -> void:
	var has_bar := st.has("bar_frac")
	var cy := 128.0 if has_bar else 137.0
	var x := 12.0
	var tex := icon_atlas(String(st.get("icon", "")))
	if tex != null:
		var ic := _card_rect(tex, Rect2(x, cy - 18.0, 36.0, 36.0))
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		b.add_child(ic)
		x += 40.0
	var right := 168.0
	if st.get("check", false):
		var ck := KitShape.new("disc", face_of("go"))
		ck.lip = lip_of("go")
		ck.position = Vector2(134, cy - 17.0)
		ck.size = Vector2(34, 34)
		b.add_child(ck)
		chrome(ck, "check", Rect2(4, 2, 26, 26))
		right = 128.0
	var text := String(st.get("text", ""))
	var s := fit_size(text, 26, right - x, "d900", 22)
	var l := label(text, s, TEXT, true)
	l.add_theme_font_override("font", font("d900"))
	l.add_theme_font_size_override("font_size", s)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.clip_text = true
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.position = Vector2(x, cy - 20.0)
	l.size = Vector2(right - x, 40.0)
	l.name = "stat"
	b.add_child(l)
	if has_bar:
		bar(b, Rect2(12, 146, 156, 16), float(st["bar_frac"]), String(st.get("bar_role", "go")))


## Chips (§4.8). kind: status (INK pill), owner (fill = the state's colour), stat (SLATE_WELL), timer (M size),
## timer_war (red). Returns the chip Panel sized to its content. opts:
## - size: a smaller text than the kind's (e.g. 22 when a row is short);
## - max_w: the chip never gets wider — the text steps down to 22, then is cut with an ellipsis;
## - color: the text's colour (POS for a plus, NEG for a shortfall; white by default);
## - lock: a closed item (§3.5) — the icon dimmed, a lock icon before the text.
## An icon-only chip (text "") is the icon with an even margin round it.
static func chip(parent: Node, pos: Vector2, icon: String, text: String, kind := "status", fill := Color(0, 0, 0, 0), opts := {}) -> Panel:
	var h := 34.0
	var icon_side := 28.0
	var size := 24
	var face := Color(INK, 0.85)
	var out := 0
	var font_kind := "d800"
	match kind:
		"owner":
			face = fill if fill.a > 0.0 else face_of("info")
			out = 3
		"stat":
			h = 38.0
			icon_side = 32.0
			size = 26
			face = SLATE_WELL
			out = 3
			font_kind = "d900"
		"timer":
			h = 52.0
			icon_side = 44.0
			size = 30
			font_kind = "d900"
		"timer_war":
			face = face_of("war")
			out = 3
	size = int(opts.get("size", size))
	var col: Color = opts.get("color", TEXT)
	var locked := bool(opts.get("lock", false))
	var max_w := float(opts.get("max_w", 0.0))
	var p := Panel.new()
	var sb := style(face, int(h * 0.5), out, INK, 0, 0)
	sb.set_meta("kit_kind", "")
	set_panel(p, sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var x := 10.0
	var has_icon := icon != "" and icon_tex(icon) != null
	if has_icon:
		var ic := TextureRect.new()
		ic.name = "icon"
		ic.texture = icon_atlas(icon)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.size = Vector2(icon_side, icon_side)
		ic.position = Vector2(6.0, (h - icon_side) * 0.5)
		if locked:
			ic.modulate = LOCK_MOD
		p.add_child(ic)
		x = 8.0 + icon_side
	if locked:  # the lock sits before the text, a little smaller than the item's icon
		var ls := roundf(icon_side * 0.8)
		var lk := TextureRect.new()
		lk.name = "lock"
		lk.texture = icon_atlas("lock")
		lk.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		lk.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		lk.mouse_filter = Control.MOUSE_FILTER_IGNORE
		lk.size = Vector2(ls, ls)
		lk.position = Vector2(x - (2.0 if has_icon else 4.0), (h - ls) * 0.5)
		p.add_child(lk)
		x += ls + (0.0 if has_icon else -2.0)
		has_icon = true
	var l := label(text, size, col, true)
	l.add_theme_font_override("font", font(font_kind))
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.name = "label"
	var tw := 0.0
	var w := 0.0
	if text == "":
		l.visible = false
		w = x - 2.0 + 6.0 if has_icon else h  # the icon with the same 6 px on both sides
	else:
		var room := max_w - x - 12.0 if max_w > 0.0 else -1.0
		if room > 0.0 and text_w(text, size, font_kind) > room:
			var s := fit_size(text, size, room, font_kind, mini(22, size))
			style_label(l, s, col, true)
			l.add_theme_font_override("font", font(font_kind))
			size = s
		tw = text_w(text, size, font_kind)
		if room > 0.0 and tw > room:  # still too long at 22: the line gets shorter, not the type
			tw = room
			l.clip_text = true
			l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		w = x + tw + 12.0
	l.position = Vector2(x, -1)
	l.size = Vector2(tw, h)
	p.add_child(l)
	p.position = pos
	p.size = Vector2(w, h)
	if parent:
		parent.add_child(p)
	return p


## A price plate (KitPrice): INK pill with [icon][number] per item. items: [[icon, text, short], …]; `short` (not
## enough) paints the number NEG. `num` / `icon` default by height: NUM 32 / 28 / 26 / 24 for h ≥ 50 / 40 / 34 / less.
static func price_plate(items: Array, h := 34.0, on := "dark", num := 0, icon := 0.0) -> Panel:
	var p := KitPrice.new(items)
	var n := num if num > 0 else (32 if h >= 50.0 else (28 if h >= 40.0 else (26 if h >= 34.0 else 24)))
	p.lay(h, n, icon if icon > 0.0 else roundf(minf(h - 2.0, h * 0.9)))
	return p


static func price(parent: Node, pos: Vector2, items: Array, h := 34.0, on := "dark") -> Panel:
	var p := price_plate(items, h, on)
	p.position = pos
	if parent:
		parent.add_child(p)
	return p


## A vector star: full = gold face + gloss; empty = CREAM_DEEP relief.
static func star(parent: Node, center: Vector2, r: float, full: bool) -> KitShape:
	var s := KitShape.new("star" if full else "star_empty")
	s.size = Vector2(r, r) * 2.0 + Vector2(8, 8)
	s.position = center - s.size * 0.5
	if parent:
		parent.add_child(s)
	return s


## Vector chrome (x, check, chevrons, plus, minus, arrows, swap) in a square box.
static func chrome(parent: Node, kind: String, rect: Rect2, color := Color.WHITE) -> KitShape:
	var s := KitShape.new(kind)
	s.data = {"color": color}
	s.position = rect.position
	s.size = rect.size
	if parent:
		parent.add_child(s)
	return s


## A round go badge with a vector check (Ø40: a selected / claimed tile, §4.9), centred at `center`.
static func check_badge(parent: Node, center: Vector2, d := 40.0) -> KitShape:
	var ck := KitShape.new("disc", face_of("go"))
	ck.name = "check"
	ck.lip = lip_of("go")
	ck.size = Vector2(d, d)
	ck.position = center - ck.size * 0.5
	if parent:
		parent.add_child(ck)
	chrome(ck, "check", Rect2(d * 0.12, d * 0.06, d * 0.76, d * 0.76))
	return ck


# ------------------------------------------------------------------ paper: wells, sections, bubbles (§4.3, §4.9)

## A well on paper: CREAM_WELL, R 20, no contour, no lip (§3.4) — lists and tiles sit in it.
static func well(parent: Node, rect: Rect2, face := CREAM_WELL) -> Panel:
	var p := Panel.new()
	p.name = "well"
	var sb := style(face, 20, 0, INK, 0, 0)
	sb.set_meta("kit_kind", "")
	set_panel(p, sb)
	p.position = rect.position
	p.size = rect.size
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if parent:
		parent.add_child(p)
	return p


## A section header on paper (§4.9): an optional icon 48, Rubik 900 32 INK_TEXT (fit to 24), then a 4 px CREAM_DEEP
## line to the right end. 48 px tall.
static func section(parent: Node, pos: Vector2, w: float, text: String, icon := "") -> Control:
	var c := Control.new()
	c.name = "section"
	c.mouse_filter = Control.MOUSE_FILTER_IGNORE
	c.position = pos
	c.size = Vector2(w, 48)
	var x := 0.0
	var tex := icon_atlas(icon)
	if tex != null:
		var ic := _card_rect(tex, Rect2(0, 0, 48, 48))
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		c.add_child(ic)
		x = 56.0
	var s := fit_size(text, 32, w - x - 40.0, "d900", 24, false)
	var l := label(text, s, INK_TEXT, true)
	l.add_theme_font_size_override("font_size", s)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	var tw := minf(text_w(text, s, "d900", false), w - x - 40.0)
	l.position = Vector2(x, -2)
	l.size = Vector2(tw + 4.0, 48)
	l.clip_text = true
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	c.add_child(l)
	var line := Panel.new()
	var lsb := style(CREAM_DEEP, 2, 0, INK, 0, 0)
	lsb.set_meta("kit_kind", "")
	set_panel(line, lsb)
	line.mouse_filter = Control.MOUSE_FILTER_IGNORE
	line.position = Vector2(x + tw + 16.0, 22)
	line.size = Vector2(maxf(0.0, w - x - tw - 16.0), 4)
	c.add_child(line)
	if parent:
		parent.add_child(c)
	return c


## A speech bubble on paper (a leader's line): a white face, INK 4, R 24, a hard shadow 4, a tail toward the speaker
## ("left" / "right" / "up" / "down"); BODY 28 INK_TEXT (26 when long), word-wrapped, at most 3 lines, centred
## vertically. Returns the bubble Panel; its Label is "text".
static func bubble(parent: Node, rect: Rect2, text: String, tail := "left") -> Panel:
	var p := Panel.new()
	p.name = "bubble"
	var sb := style(WHITE, 24, 4, INK, 4, 0)
	sb.set_meta("kit_kind", "")
	set_panel(p, sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.position = rect.position
	p.size = rect.size
	var tl := KitShape.new("tail", WHITE)
	tl.data = {"dir": tail}
	match tail:
		"left":
			tl.size = Vector2(22, 30)
			tl.position = Vector2(-18, rect.size.y * 0.5 - 15.0)
		"right":
			tl.size = Vector2(22, 30)
			tl.position = Vector2(rect.size.x - 4.0, rect.size.y * 0.5 - 15.0)
		"up":
			tl.size = Vector2(30, 22)
			tl.position = Vector2(rect.size.x * 0.5 - 15.0, -18)
		_:
			tl.size = Vector2(30, 22)
			tl.position = Vector2(rect.size.x * 0.5 - 15.0, rect.size.y - 4.0)
	p.add_child(tl)
	var inner := rect.size.x - 40.0
	var f := font("b800")
	var fs := 28
	for s: int in [28, 26]:
		fs = s
		var lines: float = f.get_multiline_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, inner, s).y / (s * 1.36)
		if lines <= 2.2:
			break
	var l := label(text, fs, INK_TEXT, false)
	l.name = "text"
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.max_lines_visible = 3
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.position = Vector2(20, 4)
	l.size = Vector2(inner, rect.size.y - 8.0)
	p.add_child(l)
	if parent:
		parent.add_child(p)
	return p


# ------------------------------------------------------------------ segments (§4.5)

## A segment that is not selected: text only; a tap calls `cb`.
class KitSegment extends Control:
	var cb := Callable()
	var _down := false
	var _frame := -1

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP
		gui_input.connect(_on_input)

	func _on_input(e: InputEvent) -> void:
		var pressed := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pressed = e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			pressed = e.pressed
			pos = (e as InputEventScreenTouch).position
		else:
			return
		if pressed:
			_down = true
			return
		var f := Engine.get_process_frames()
		if not _down or f == _frame:
			return  # the emulated mouse twin of a touch
		_down = false
		_frame = f
		if Rect2(Vector2.ZERO, size).has_point(pos) and cb.is_valid():
			cb.call()


## Segments (§4.5): an INK 4 track (CREAM_DEEP on paper, SLATE_WELL on slate), the selected segment a raised info
## button S, the others Rubik 900 28 text (SOFT_CREAM on paper, white on slate) fit to 22. A tap on a segment calls
## cb.call(i) (the selected one too: the caller may ignore it). Returns the track Panel; segment i is "seg_i".
static func segmented(parent: Node, rect: Rect2, items: Array, selected: int, cb: Callable, on_paper := true) -> Panel:
	var p := Panel.new()
	p.name = "segmented"
	var sb := style(CREAM_DEEP if on_paper else SLATE_WELL, 24, 4, INK, 0, 0)
	sb.set_meta("kit_kind", "")
	set_panel(p, sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	p.position = rect.position
	p.size = rect.size
	if parent:
		parent.add_child(p)
	var n := maxi(1, items.size())
	var pad := 6.0
	var sw := (rect.size.x - 2.0 * pad) / n
	var col := SOFT_CREAM if on_paper else alpha(WHITE, 0.85)
	for i in items.size():
		var r := Rect2(pad + i * sw, pad, sw, rect.size.y - 2.0 * pad)
		var txt := String(items[i])
		var idx := i
		if i == selected:
			var b := button(p, r.grow_individual(-2, 0, -2, 0), "info", txt, {"size": "S", "cb": func(): cb.call(idx)})
			b.name = "seg_%d" % i
		else:
			var s := KitSegment.new()
			s.name = "seg_%d" % i
			s.position = r.position
			s.size = r.size
			s.cb = func(): cb.call(idx)
			p.add_child(s)
			var fs := fit_size(txt, 28, r.size.x - 16.0, "d900", 22, not on_paper)
			var l := label(txt, fs, col, true)
			l.add_theme_font_size_override("font_size", fs)
			l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			l.size = r.size
			l.clip_text = true
			l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
			s.add_child(l)
	return p


# ------------------------------------------------------------------ tiles (§4.9)

## A tile on paper — see `tile`. A tap (a release inside after a press, not a swipe) calls `cb`; it sinks a little
## while pressed.
class KitTile extends Panel:
	var cb := Callable()
	var _press_g := Vector2.ZERO
	var _travel := 0.0
	var _down := false
	var _frame := -1

	func _init() -> void:
		name = "tile"
		mouse_filter = Control.MOUSE_FILTER_PASS
		gui_input.connect(_on_input)

	func _on_input(e: InputEvent) -> void:
		if not cb.is_valid():
			return
		var pressed := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pressed = e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			pressed = e.pressed
			pos = (e as InputEventScreenTouch).position
		elif e is InputEventMouseMotion or e is InputEventScreenDrag:
			if _down:
				_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
			return
		else:
			return
		var f := Engine.get_process_frames()
		if pressed:
			if _down:
				return
			_down = true
			_press_g = SELF.screen_pos(self, e)
			_travel = 0.0
			pivot_offset = size * 0.5
			scale = Vector2(0.97, 0.97)
			return
		if not _down or f == _frame:
			return
		_down = false
		_frame = f
		scale = Vector2.ONE
		_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
		if _travel <= SELF.TAP_SLOP and Rect2(Vector2.ZERO, size).has_point(pos):
			cb.call()


## A tile on paper (§4.9: a reward, a demand, a statistic): face CREAM_ROW (or opts.face), R 20, lip 5, no contour.
## Top to bottom, centred: the picture, then a title, then a big value and its caption; the amount pill sits on the
## bottom edge. opts:
##   icon: a kit icon name | tex: a Texture2D (a hex render); icon_side (default: by what else the tile holds);
##   pic_overlap: how far the lines under it may rise into the picture's box (a render's transparent margin)
##   title: the name (Rubik 900 26 INK_TEXT, fit to 22, cut at the floor; wrap_title: two lines of 22 instead of the cut)
##   value: a big number (NUM_L 44; value_color, INK_TEXT by default) and caption: a muted line under it (Rubik 800 24)
##   pill: [[icon, text, short], …] — the INK amount pill on the bottom edge (NUM_S 26); pill_inside: above the lip
##   count: a «×N» info hex on the top-left corner when > 1
##   pic_node: a Control drawn in the picture's box instead of an icon (an ink swatch)
##   selected: a go outline 5 + a check badge; claimable: a gold outline 4 (+ breathe unless still); locked: a lock, the picture
##   dimmed; dim: the picture dimmed (it cannot be taken now); taken: a reward already claimed — a check badge on the
##   corner, the tile at 60 %
##   cb: a tap on the tile
static func tile(parent: Node, rect: Rect2, opts := {}) -> KitTile:
	var t := KitTile.new()
	var w := rect.size.x
	var h := rect.size.y
	var face: Color = opts.get("face", CREAM_ROW)
	var sel := bool(opts.get("selected", false))
	var claim := bool(opts.get("claimable", false))
	var locked := bool(opts.get("locked", false))
	var line := face_of("go") if sel else (face_of("gold") if claim else INK)
	var out := 5 if sel else (4 if claim else 0)
	var sb := style(face, 20, out, line, 0, 5)
	sb.set_meta("kit_kind", "")
	sb.set_meta("kit_lip_color", ROW_LIP if face.is_equal_approx(CREAM_ROW) else face.darkened(0.25))
	set_panel(t, sb)
	t.add_child(KitDecor.new())  # the lip (child 0)
	t.position = rect.position
	t.size = rect.size
	t.cb = opts.get("cb", Callable())
	var title := String(opts.get("title", ""))
	var value := String(opts.get("value", ""))
	var caption := String(opts.get("caption", ""))
	var pill: Array = opts.get("pill", [])
	var tex: Texture2D = atlas_of(opts.get("tex", null))
	if tex == null:
		tex = icon_atlas(String(opts.get("icon", "")))
	var pic_node: Control = opts.get("pic_node")  # a drawn picture (an ink swatch) laid in the picture's box
	if pic_node != null:
		tex = null
	var ph := 36.0
	var inside := bool(opts.get("pill_inside", false))  # a demand's cost sits inside, a reward's amount on the edge
	var bottom := h - 5.0 - (4.0 if pill.is_empty() else (ph + 10.0 if inside else ph * 0.5 + 2.0))
	var side := float(opts.get("icon_side", 0.0))
	if side <= 0.0:
		side = minf(w * 0.5, h * 0.44) if (title != "" or value != "") else minf(w, h) * 0.6
	var overlap := float(opts.get("pic_overlap", 0.0)) if tex != null else 0.0  # a render's empty margin under the art
	# wrap_title: a name too long for one line at 22 takes two (the picture gives up the room) instead of «…»
	var two_lines := title != "" and bool(opts.get("wrap_title", false)) and text_w(title, 22, "d900", false) > w - 20.0
	var title_h := 56.0 if two_lines else 34.0
	if two_lines:
		side = maxf(48.0, side - 22.0)
	var parts_h := (side - overlap if tex != null or pic_node != null else 0.0) + (title_h if title != "" else 0.0) \
		+ (50.0 if value != "" else 0.0) + (30.0 if caption != "" else 0.0)
	var y := maxf(6.0, (bottom - parts_h) * 0.5 + 2.0)
	if pic_node != null:
		pic_node.position = Vector2(roundf((w - side) * 0.5), roundf(y))
		pic_node.size = Vector2(side, side)
		t.add_child(pic_node)
		y += side
	elif tex != null:
		var pic := _card_rect(tex, Rect2((w - side) * 0.5, y, side, side))
		pic.name = "pic"
		pic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		if locked or bool(opts.get("dim", false)):
			pic.modulate = LOCK_MOD
		t.add_child(pic)
		if locked:
			var lk := _card_rect(icon_atlas("lock"), Rect2(w * 0.5 + side * 0.18, y + side * 0.42, side * 0.5, side * 0.5))
			lk.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			t.add_child(lk)
		y += side - overlap
	if title != "":
		var s := 22 if two_lines else fit_size(title, 26, w - 20.0, "d900", 22, false)
		var tl := label(title, s, INK_TEXT, true)
		tl.name = "title"
		tl.add_theme_font_size_override("font_size", s)
		tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		tl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		if two_lines:
			tl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
			tl.max_lines_visible = 2
			tl.add_theme_constant_override("line_spacing", -4)
		else:
			tl.clip_text = true
		tl.position = Vector2(10, y)
		tl.size = Vector2(w - 20.0, title_h)
		t.add_child(tl)
		y += title_h
	if value != "":
		var vs := fit_size(value, 44, w - 16.0, "d900", 30, false)
		var vl := label(value, vs, opts.get("value_color", INK_TEXT), true)
		vl.name = "value"
		vl.add_theme_font_size_override("font_size", vs)
		vl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		vl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		vl.position = Vector2(8, y)
		vl.size = Vector2(w - 16.0, 50)
		t.add_child(vl)
		y += 50.0
	if caption != "":
		var cs := fit_size(caption, 24, w - 14.0, "d800", 22, false)
		var cl := label(caption, cs, MUTED_CREAM, true)
		cl.name = "caption"
		cl.add_theme_font_override("font", font("d800"))
		cl.add_theme_font_size_override("font_size", cs)
		cl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		cl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		cl.clip_text = text_w(caption, cs, "d800", false) > w - 14.0  # cut only when even 22 does not fit
		cl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		cl.position = Vector2(4, y - 2.0)
		cl.size = Vector2(w - 8.0, 30)
		t.add_child(cl)
	if not pill.is_empty():
		var pp := price_plate(pill, ph)
		pp.name = "pill"
		pp.position = Vector2(roundf((w - pp.size.x) * 0.5), h - 5.0 - 10.0 - ph if inside else h - ph * 0.5 - 2.0)
		t.add_child(pp)
	var n := int(opts.get("count", 0))
	if n > 1:  # inside the corner: on the edge it would crowd the neighbour's check badge
		var hb := hex_badge(t, Vector2(30, 32), 24, "info", "×%d" % n)
		hb.name = "count"
	if sel:
		check_badge(t, Vector2(w - 6.0, 6.0))
	elif bool(opts.get("taken", false)):
		check_badge(t, Vector2(w - 10.0, 10.0))
		t.modulate.a = 0.6
	if claim and not bool(opts.get("still", false)):  # still: the gold outline alone (one thing breathes per screen)
		breathe(t)
	if parent:
		parent.add_child(t)
	return t


# ------------------------------------------------------------------ rows, toggles, ribbons, links, scrolling

## A list row on paper — see `row`. A tap (a release inside after a press, not a swipe, not on the right element when
## that is a button or a toggle: those act on their own) calls `cb`; the row sinks a little while pressed.
class KitRow extends Panel:
	var cb := Callable()
	var right: Control  ## the one element at the right end
	var title_label: Label
	var icon_node: Control
	var _press_g := Vector2.ZERO
	var _travel := 0.0
	var _down := false
	var _frame := -1

	func _init() -> void:
		name = "row"
		mouse_filter = Control.MOUSE_FILTER_PASS  # a drag still scrolls the list around it
		gui_input.connect(_on_input)

	func _on_input(e: InputEvent) -> void:
		if not cb.is_valid():
			return
		var pressed := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pressed = e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			pressed = e.pressed
			pos = (e as InputEventScreenTouch).position
		elif e is InputEventMouseMotion or e is InputEventScreenDrag:
			if _down:
				_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
			return
		else:
			return
		var on_right := right != null and right.visible and (right is KitButton or right is KitToggle) \
			and Rect2(right.position, right.size).grow(8.0).has_point(pos)
		var f := Engine.get_process_frames()
		if pressed:
			if _down or on_right:
				return
			_down = true
			_press_g = SELF.screen_pos(self, e)
			_travel = 0.0
			pivot_offset = size * 0.5
			scale = Vector2(0.98, 0.98)
			return
		if not _down or f == _frame:
			return
		_down = false
		_frame = f
		scale = Vector2.ONE
		_travel = maxf(_travel, SELF.screen_pos(self, e).distance_to(_press_g))
		if _travel <= SELF.TAP_SLOP and Rect2(Vector2.ZERO, size).has_point(pos) and not on_right:
			cb.call()


## A list row on paper (§4.9): CREAM_ROW (opts.face), R 20, lip 5 ROW_LIP, no contour, h ≥ 96. At the left an icon 72
## (or opts.icon_node, a Control laid in that place: a portrait, a tile 80); the title (Rubik 900 30 INK_TEXT, one line,
## fit to 26, then cut) over a muted line (Nunito 26 MUTED_CREAM) or an M bar; exactly one element at the right end,
## centred on the face, the title stopping 16 px before it. opts:
##   icon (a kit name) | tex (Texture2D) | icon_node (Control); icon_side (72)
##   title; sub (a line) | bar: {frac, role, text}
##   right: "chevron" | "check" | "lock" | a Control already sized (a button, a toggle, a tile)
##   state: "claim" (a gold outline 4) | "done" (a check at the right unless `right` is given, the row at α 0.7) |
##          "locked" (a lock at the right unless given, the icon at α 0.5) | "selected" (a go outline 5 + a check)
##   new: true — a red dot on the icon's corner
##   face (CREAM_ROW); cb: a tap on the row
static func row(parent: Node, rect: Rect2, opts := {}) -> KitRow:
	var r := KitRow.new()
	var w := rect.size.x
	var h := rect.size.y
	var state := String(opts.get("state", ""))
	var face: Color = opts.get("face", CREAM_ROW)
	var line := face_of("go") if state == "selected" else (face_of("gold") if state == "claim" else INK)
	var out := 5 if state == "selected" else (4 if state == "claim" else 0)
	var sb := style(face, 20, out, line, 0, 5)
	sb.set_meta("kit_kind", "")
	sb.set_meta("kit_lip_color", ROW_LIP if face.is_equal_approx(CREAM_ROW) else face.darkened(0.2))
	set_panel(r, sb)
	r.add_child(KitDecor.new())  # the lip (child 0)
	r.position = rect.position
	r.size = rect.size
	r.cb = opts.get("cb", Callable())
	var cy := (h - 5.0) * 0.5  # the face's middle, over the lip
	var pad := 16.0
	var x := pad
	# ---- the picture at the left
	var side := float(opts.get("icon_side", 72.0))
	var node: Control = opts.get("icon_node")
	var tex: Texture2D = atlas_of(opts.get("tex", null))
	if tex == null:
		tex = icon_atlas(String(opts.get("icon", "")))
	if node != null:
		node.position = Vector2(x, roundf(cy - node.size.y * 0.5))
		r.add_child(node)
		x += node.size.x + 16.0
		r.icon_node = node
	elif tex != null:
		var ic := _card_rect(tex, Rect2(x, roundf(cy - side * 0.5), side, side))
		ic.name = "icon"
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		r.add_child(ic)
		x += side + 16.0
		r.icon_node = ic
	if r.icon_node != null:
		if state == "locked":
			r.icon_node.modulate.a = 0.5
		if bool(opts.get("new", false)):
			dot(r.icon_node, -1, "war").name = "new"
	# ---- the one element at the right
	var rt: Variant = opts.get("right", "")
	var rn: Control = null
	if rt is Control:
		rn = rt
	else:
		var kind := String(rt)
		if kind == "":
			kind = "check" if state in ["done", "selected"] else ("lock" if state == "locked" else "")
		match kind:
			"chevron":
				rn = chrome(null, "chevron_right", Rect2(0, 0, 40, 40))
			"check":
				rn = check_badge(null, Vector2(20, 20), 40.0)
			"lock":
				rn = _card_rect(icon_atlas("lock"), Rect2(0, 0, 44, 44))
				(rn as TextureRect).stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var text_r := w - pad
	if rn != null:
		rn.position = Vector2(roundf(w - pad - rn.size.x), roundf(cy - rn.size.y * 0.5))
		r.add_child(rn)
		r.right = rn
		text_r = rn.position.x - 16.0
	# ---- the title over a muted line or a bar
	var tw := maxf(40.0, text_r - x)
	var title := String(opts.get("title", ""))
	var sub := String(opts.get("sub", ""))
	var bd: Dictionary = opts.get("bar", {})
	var two := sub != "" or not bd.is_empty()
	var ts := fit_size(title, 30, tw, "d900", 26, false)
	var tl := label(title, ts, INK_TEXT, true)
	tl.name = "title"
	tl.add_theme_font_size_override("font_size", ts)
	tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tl.clip_text = text_w(title, ts, "d900", false) > tw
	tl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	tl.position = Vector2(x, roundf(cy - (38.0 if two else 20.0)))
	tl.size = Vector2(tw, 40)
	r.add_child(tl)
	r.title_label = tl
	if not bd.is_empty():
		var b := bar(r, Rect2(x, roundf(cy + 6.0), tw, 28), float(bd.get("frac", 0.0)), String(bd.get("role", "info")),
			String(bd.get("text", "")), true)
		b.name = "bar"
	elif sub != "":
		var sl := label(sub, 26, MUTED_CREAM, false)
		sl.name = "sub"
		sl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		sl.clip_text = true
		sl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		sl.position = Vector2(x, roundf(cy + 2.0))
		sl.size = Vector2(tw, 36)
		r.add_child(sl)
	if state == "done":
		r.modulate.a = 0.7
	if parent:
		parent.add_child(r)
	return r


## A switch (§4.13) — see `toggle`.
class KitToggle extends Control:
	signal toggled(on: bool)
	var on := false
	var cb := Callable()  ## cb.call(on) after a tap has flipped it
	var _k := 0.0  # the knob: 0 left (off) … 1 right (on)
	var _down := false
	var _frame := -1
	var _tw: Tween

	func _init() -> void:
		name = "toggle"
		mouse_filter = Control.MOUSE_FILTER_STOP
		custom_minimum_size = Vector2(96, 52)
		size = custom_minimum_size
		gui_input.connect(_on_input)

	func _has_point(p: Vector2) -> bool:
		return Rect2(Vector2.ZERO, size).grow(22.0).has_point(p)  # a 96+ px touch zone (§1.4)

	func set_on(v: bool, animate := true) -> void:
		on = v
		var to := 1.0 if on else 0.0
		if _tw != null and _tw.is_valid():
			_tw.kill()
		var d := SELF._dur(0.14) if animate else 0.0
		if d <= 0.0:
			_k = to
			queue_redraw()
			return
		_tw = create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
		_tw.tween_method(func(k: float):
			_k = k
			queue_redraw(), _k, to, d)

	func _on_input(e: InputEvent) -> void:
		var pressed := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pressed = e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			pressed = e.pressed
			pos = (e as InputEventScreenTouch).position
		else:
			return
		if pressed:
			_down = true
			return
		var f := Engine.get_process_frames()
		if not _down or f == _frame:
			return  # the emulated mouse twin of a touch
		_down = false
		_frame = f
		if not _has_point(pos):
			return
		set_on(not on)
		toggled.emit(on)
		if cb.is_valid():
			cb.call(on)

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var sb := StyleBoxFlat.new()
		sb.anti_aliasing = true
		sb.corner_detail = 10
		sb.bg_color = INK
		sb.set_corner_radius_all(int(h * 0.5))
		draw_style_box(sb, Rect2(0, 0, w, h))
		var face: Color = (ROLE["lock"][0] as Color).lerp(ROLE["go"][0], _k)
		var lipc: Color = (ROLE["lock"][1] as Color).lerp(ROLE["go"][1], _k)
		sb.bg_color = face
		sb.set_corner_radius_all(int(h * 0.5 - 4.0))
		sb.border_width_bottom = 4  # the face's own lip: a toy's thickness, like the buttons
		sb.border_color = lipc
		draw_style_box(sb, Rect2(4, 4, w - 8.0, h - 8.0))
		var r := 20.0
		var c := Vector2(lerpf(h * 0.5, w - h * 0.5, _k), h * 0.5)
		draw_circle(c + Vector2(0, 3), r, Color(INK, SHADOW_A), true, -1.0, true)
		draw_circle(c, r, INK, true, -1.0, true)
		draw_circle(c, r - 3.0, Color.WHITE, true, -1.0, true)


## A switch (§4.13): an INK 4 track 96×52, R 26; on — the go face, the white knob Ø40 at the right; off — the lock face,
## the knob at the left; 140 ms. A tap flips it and calls cb.call(on).
static func toggle(parent: Node, pos: Vector2, on: bool, cb := Callable()) -> KitToggle:
	var t := KitToggle.new()
	t.position = pos
	t.cb = cb
	t.set_on(on, false)
	if parent:
		parent.add_child(t)
	return t


## A ribbon (§4.8: «Выгодно», «Пробный», «Эпик гарантирован»): a pill h 34 of the role's face (war or gold), INK 3,
## MICRO 22, centred at `center` — on the top edge of a button or a card. No tails, no tilt.
static func ribbon(parent: Node, center: Vector2, text: String, role := "war") -> Panel:
	var p := caption_pill(null, text, 34.0, face_of(role), 22, 3)
	p.name = "ribbon"
	p.position = (center - p.size * 0.5).round()
	if parent:
		parent.add_child(p)
	return p


## A round info «i» Ø52 (§6 Лавка): a secondary button that opens a tooltip or a window; a 96 px touch zone.
static func info_button(parent: Node, center: Vector2, cb: Callable, d := 52.0) -> KitButton:
	var b := button(parent, Rect2(center - Vector2(d, d) * 0.5, Vector2(d, d)), "info", "i",
		{"round": true, "size": "XS", "cb": cb, "hit_pad": maxf(0.0, (96.0 - d) * 0.5)})
	b.name = "info"
	return b


## A text link — see `links`.
class KitLink extends Label:
	var cb := Callable()
	var _down := false
	var _frame := -1

	func _init() -> void:
		mouse_filter = Control.MOUSE_FILTER_STOP
		gui_input.connect(_on_input)

	func _on_input(e: InputEvent) -> void:
		var pressed := false
		var pos := Vector2.ZERO
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pressed = e.pressed
			pos = (e as InputEventMouseButton).position
		elif e is InputEventScreenTouch:
			pressed = e.pressed
			pos = (e as InputEventScreenTouch).position
		else:
			return
		if pressed:
			_down = true
			return
		var f := Engine.get_process_frames()
		if not _down or f == _frame:
			return
		_down = false
		_frame = f
		if Rect2(Vector2.ZERO, size).grow(10.0).has_point(pos) and cb.is_valid():
			cb.call()

	func _draw() -> void:  # the underline, under the glyphs only
		var f := get_theme_font("font")
		var fs := get_theme_font_size("font_size")
		var tw := minf(f.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x, size.x)
		var x0 := (size.x - tw) * 0.5
		var y := size.y * 0.5 + fs * 0.62
		draw_line(Vector2(x0, y), Vector2(x0 + tw, y), get_theme_color("font_color"), 2.0, true)


## Text links in one row (the legal links of a store screen): LINK #2266B8 Rubik 800, underlined, separated by small
## INK dots; all at one size — the largest scale size ≤ `size` (≥ 22) at which the whole row fits — each in a slot as
## wide as its text plus an even share of the room left. items: [[text, cb], …]. Returns the KitLink labels.
static func links(parent: Node, rect: Rect2, items: Array, size := 26) -> Array:
	var n := maxi(1, items.size())
	var gap := 32.0
	var s := 22
	for v in fit_steps(size, 22):
		var total := gap * (n - 1)
		for it in items:
			total += text_w(String(it[0]), v, "d800", false)
		if total <= rect.size.x:
			s = v
			break
	var widths: Array = []
	var used := gap * (n - 1)
	for it in items:
		var tw := text_w(String(it[0]), s, "d800", false) + 2.0
		widths.append(tw)
		used += tw
	var extra := maxf(0.0, rect.size.x - used) / n
	var k := 1.0  # even 22 does not fit: every slot shrinks alike and its text is cut
	if used > rect.size.x:
		k = (rect.size.x - gap * (n - 1)) / maxf(1.0, used - gap * (n - 1))
	var out: Array = []
	var x := rect.position.x
	for i in items.size():
		var sw: float = float(widths[i]) * k + extra
		var l := KitLink.new()
		l.text = String(items[i][0])
		l.cb = items[i][1]
		style_label(l, s, LINK, true)
		l.add_theme_font_override("font", font("d800"))
		l.add_theme_font_size_override("font_size", s)
		l.mouse_filter = Control.MOUSE_FILTER_STOP
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		l.clip_text = float(widths[i]) > sw + 0.5
		l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		l.position = Vector2(x, rect.position.y)
		l.size = Vector2(sw, rect.size.y)
		x += sw + gap
		l.name = "link_%d" % i
		if parent:
			parent.add_child(l)
		out.append(l)
		if i > 0 and parent:
			var d := Panel.new()  # the separator: a small INK dot, not a «·» glyph
			var dsb := style(alpha(INK, 0.45), 4, 0, INK, 0, 0)
			dsb.set_meta("kit_kind", "")
			set_panel(d, dsb)
			d.mouse_filter = Control.MOUSE_FILTER_IGNORE
			d.size = Vector2(8, 8)
			d.position = Vector2(l.position.x - gap * 0.5 - 4.0, rect.position.y + rect.size.y * 0.5 - 4.0)
			parent.add_child(d)
	return out


const FADE_H := 24.0  ## the fades of a scrolling well (§4.3)


## Scrolling inside a well (§4.3): a ScrollContainer over the whole well holding a Control `content_h` tall (returned
## as "inner": the content goes in it), 24 px fades of `fade` (the well's colour) at the bottom and, once scrolled, at
## the top, and an 8 px INK α 0.4 pill bar on the right (keep 12 px free there). Returns {inner, scroll}.
static func scroller(well: Control, content_h: float, fade := CREAM_WELL) -> Dictionary:
	var sc := ScrollContainer.new()
	sc.name = "scroll"
	sc.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sc.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	sc.size = well.size
	well.add_child(sc)
	var inner := Control.new()
	inner.name = "content"
	inner.custom_minimum_size = Vector2(well.size.x, content_h)
	inner.mouse_filter = Control.MOUSE_FILTER_PASS
	sc.add_child(inner)
	var fades: Array = []
	for top in [true, false]:
		var f := TextureRect.new()
		f.name = "fade_top" if top else "fade_bottom"
		f.texture = vgradient(fade, alpha(fade, 0.0)) if top else vgradient(alpha(fade, 0.0), fade)
		f.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		f.stretch_mode = TextureRect.STRETCH_SCALE
		f.mouse_filter = Control.MOUSE_FILTER_IGNORE
		f.position = Vector2(10, 0.0 if top else well.size.y - FADE_H)  # 10 in: clear of the well's round corners
		f.size = Vector2(well.size.x - 20.0, FADE_H)
		well.add_child(f)
		fades.append(f)
	var track := Rect2(well.size.x - 12.0, 12.0, 8.0, well.size.y - 24.0)
	var bar_p := Panel.new()
	bar_p.name = "scroll_bar"
	var bsb := style(alpha(INK, 0.4), 8, 0, INK, 0, 0)
	bsb.set_meta("kit_kind", "")
	set_panel(bar_p, bsb)
	bar_p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar_p.size = Vector2(track.size.x, maxf(48.0, track.size.y * minf(1.0, well.size.y / maxf(1.0, content_h))))
	bar_p.position = track.position
	bar_p.visible = content_h > well.size.y + 1.0
	well.add_child(bar_p)
	var span := maxf(1.0, content_h - well.size.y)
	var show_at := func(v: float) -> void:
		var k := clampf(v / span, 0.0, 1.0)
		bar_p.position.y = track.position.y + k * (track.size.y - bar_p.size.y)
		(fades[0] as Control).visible = v > 1.0
		(fades[1] as Control).visible = v < span - 1.0
	sc.get_v_scroll_bar().value_changed.connect(show_at)
	show_at.call(0.0)
	return {"inner": inner, "scroll": sc}


## Scrolls a scroller (Kit.scroller's ScrollContainer) to `y` once it has laid out its content (the range is known
## then); `y` is clamped by the container.
static func scroll_to(sc: ScrollContainer, y: float) -> void:
	if y <= 0.0:
		return
	var go := func() -> void:
		if is_instance_valid(sc):
			sc.scroll_vertical = int(y)
	go.call_deferred()


# ------------------------------------------------------------------ icons (§3.5)

## Until the rendered icon exists (s02), a new name shows its stand-in.
const ICON_FALLBACK := {"swords": "target", "shield": "fort", "dove": "hands", "treaty": "orders", "seal": "lock",
	"handshake": "hands", "globe": "scales", "horn": "target", "gift": "crate", "coins": "coin", "lightning": "hourglass",
	"barrel": "oil", "calendar": "hourglass", "charter": "book", "chest_wood": "crate", "chest_royal": "crown",
	"chest_cards": "cards", "medal_bronze": "medal", "medal_silver": "medal", "medal_gold": "medal", "shard": "frame",
	"blueprint": "flask", "xp": "medal", "mason": "builder", "white_flag": "orders", "pencil": "gear", "sound_on": "gear",
	"sound_off": "gear", "dice": "cards", "eye_off": "lock"}
static var _tex_cache := {}
static var _vis_right := {}
## A cosmetic's picture by its category (the Atelier, an opening's tile, a pass or Chronicle reward).
const COSMETIC_ICON := {"cos_border_ink": "pencil", "cos_peace_seal": "seal", "cos_peace_fireworks": "xp",
	"cos_fill_pattern": "hex_tile", "cos_capital_skin": "castle_icon", "cos_frame": "frame", "cos_flag_part": "pin",
	"cos_unit_skin": "helmet", "cos_emote": "hands"}
## The border inks' own colours (cases.json has the names only), by the id's tail; several run round the ring.
const INK_SWATCH := {"copper": [Color("c8763a"), Color("eaa063")], "gold_thread": [Color("e6b13e"), Color("fff0a8")],
	"flame": [Color("ff4b1f"), Color("ffc531")], "ice": [Color("7fd0f0"), Color("e3f7ff")],
	"neon": [Color("2ff0c8"), Color("ff4fd8")], "aurora": [Color("46e89a"), Color("2fc6d0"), Color("5b7cf2")],
	"river": [Color("2f86e0"), Color("8fd6f2")], "battle_banner": [Color("ef4b3f"), Color("ffc531")],
	"season1_anim": [Color("ffc531"), Color("ef4b3f"), Color("3e9bf0")]}


## A border ink's swatch (§6 Лавка › Ателье): a hex of land ringed by the ink's colours — the ink itself, not a pencil.
static func ink_swatch(id: String, side: float) -> KitShape:
	var cols: Array = [INK_TEXT]
	for k in INK_SWATCH:
		if id.ends_with("_" + String(k)):
			cols = INK_SWATCH[k]
			break
	var s := KitShape.new("ink_hex", WHITE)
	s.name = "swatch"
	s.data = {"colors": cols}
	s.size = Vector2(side, side)
	return s


## res://assets/ui/icons/<name>.png, then res://assets/ui/<name>.png, then the stand-in; null if none exists.
static func icon_tex(name: String) -> Texture2D:
	if name == "":
		return null
	if _tex_cache.has(name):
		return _tex_cache[name]
	var t: Texture2D = null
	for p in ["res://assets/ui/icons/%s.png" % name, "res://assets/ui/%s.png" % name]:
		if ResourceLoader.exists(p):
			t = load(p)
			break
	if t == null and ICON_FALLBACK.has(name):
		t = icon_tex(String(ICON_FALLBACK[name]))
	_tex_cache[name] = t
	return t


## The right edge of an icon's visible pixels as a share of its width (the round coin ≈ 0.97, the raivite crystal
## ≈ 0.83); 0.97 when the image cannot be read.
static func icon_vis_right(t: Texture2D) -> float:
	if t == null:
		return 0.97
	if t.has_meta("kit_src"):  # a sheet icon: read its source
		t = t.get_meta("kit_src")
	var key := t.resource_path if t.resource_path != "" else str(t.get_instance_id())
	if not _vis_right.has(key):
		var f := 0.97
		var img := t.get_image()
		if img != null and not img.is_compressed() and img.get_width() > 0:
			f = float(img.get_used_rect().end.x) / float(img.get_width())
		_vis_right[key] = clampf(f, 0.5, 1.0)
	return float(_vis_right[key])


## Pictographs still in strings / literals → icon names {i} or vector chrome {v}; others are dropped (s14 removes
## them from the strings). Escapes keep this table free of pictographs for the lint.
const PICTO := {
	"\U01F48E": {"i": "raivite"}, "\U01F512": {"i": "lock"}, "\U01F3AC": {"i": "ad"}, "⚔": {"i": "swords"},
	"\U01F54A": {"i": "dove"}, "\U01F4B0": {"i": "coins"}, "⚒": {"i": "hammer"}, "\U01F381": {"i": "gift"},
	"\U01F4DC": {"i": "treaty"}, "\U01F52C": {"i": "flask"}, "⏱": {"i": "hourglass"}, "⛳": {"i": "orders"},
	"⇢": {"i": "orders"}, "⚡": {"i": "lightning"}, "⏩": {"i": "lightning"}, "\U01F30D": {"i": "globe"},
	"\U01F310": {"i": "globe"}, "\U01F50A": {"i": "sound_on"}, "\U01F507": {"i": "sound_off"}, "\U01F434": {"i": "cart"},
	"\U01F3B2": {"i": "dice"}, "\U01F3F0": {"i": "castle_icon"}, "\U01F396": {"i": "medal"}, "\U01F4C5": {"i": "calendar"},
	"\U01F50F": {"i": "seal"}, "✎": {"i": "pencil"},
	"⬆": {"v": "arrow_up"}, "⇄": {"v": "swap"}, "➕": {"v": "plus"}, "★": {"v": "star"},
	"⭐": {"v": "star"}, "☆": {"v": "star_empty"}, "✓": {"v": "check"}, "✕": {"v": "x"},
	"↩": {"v": "chevron_left"}, "‹": {"v": "chevron_left"}, "›": {"v": "chevron_right"},
	"→": {"v": "arrow_right"}, "⟶": {"v": "arrow_right"},
}


static func _is_picto(code: int) -> bool:
	return (code >= 0x1F000 and code <= 0x1FAFF) or (code >= 0x2600 and code <= 0x27BF) or (code >= 0x2190 and code <= 0x21FF) \
		or (code >= 0x2B00 and code <= 0x2BFF) or (code >= 0x25A0 and code <= 0x25FF) or code == 0xFE0F or code == 0x23F1 \
		or code == 0x23E9


## "Открыть · 160 💎" → [{t: "Открыть · 160"}, {i: "raivite"}]. Pieces: {t: text} | {i: icon} | {v: chrome}.
static func split_icons(text: String) -> Array:
	var out: Array = []
	var buf := ""
	for i in text.length():
		var ch := text[i]
		if PICTO.has(ch):
			if buf.strip_edges() != "":
				out.append({"t": buf.strip_edges()})
			buf = ""
			out.append(PICTO[ch])
		elif _is_picto(ch.unicode_at(0)):
			continue
		else:
			buf += ch
	if buf.strip_edges() != "":
		out.append({"t": buf.strip_edges()})
	return out


## True when the text has any pictograph (mapped or not).
static func has_picto(text: String) -> bool:
	for i in text.length():
		if PICTO.has(text[i]) or _is_picto(text.unicode_at(i)):
			return true
	return false


# ------------------------------------------------------------------ numbers, time, plurals (§3.7)

const NBSP := " "
const MINUS := "−"


## RU: exact below 10 000 with NBSP groups, then 12,4K / 124K / 1,2M; EN: 8,620 / 12.4K. Minus is U+2212.
static func fmt_num(n: int) -> String:
	var a := absi(n)
	var s := ""
	if a < 10000:
		s = fmt_exact(a)
	elif a < 100000:
		s = _trim0(fmt_dec(floorf(a / 100.0) / 10.0, 1)) + "K"
	elif a < 1000000:
		s = str(a / 1000) + "K"
	else:
		s = _trim0(fmt_dec(floorf(a / 100000.0) / 10.0, 1)) + "M"
	return (MINUS if n < 0 else "") + s


## A shorter fmt_num for a tight slot: 1,8K from 1 000 (floored like fmt_num), 12K / 124K, 1,2M; exact below 1 000.
static func fmt_short(n: int) -> String:
	var a := absi(n)
	var s := ""
	if a < 1000:
		s = str(a)
	elif a < 10000:
		s = _trim0(fmt_dec(floorf(a / 100.0) / 10.0, 1)) + "K"
	elif a < 1000000:
		s = str(a / 1000) + "K"
	else:
		s = _trim0(fmt_dec(floorf(a / 100000.0) / 10.0, 1)) + "M"
	return (MINUS if n < 0 else "") + s


static func _trim0(s: String) -> String:
	return s.substr(0, s.length() - 2) if s.ends_with(",0") or s.ends_with(".0") else s


## Reads back a number fmt_num wrote (a resource plate's value): [the lowest, the highest] it can stand for, since
## fmt_num floors («12 437» → «12,4K» → [12 400, 12 499]); [-1, -1] when the text is not a number.
static func parse_num(s: String) -> Array:
	var t := s.strip_edges().replace(NBSP, "").replace(" ", "")
	if t.ends_with("K") or t.ends_with("M"):
		var mult := 1000 if t.ends_with("K") else 1000000
		var num := t.left(-1).replace(",", ".")
		if not num.is_valid_float():
			return [-1, -1]
		var low := roundi(num.to_float() * mult)
		# fmt_num keeps one decimal below 100K (and drops a «,0»), whole thousands up to 1M, one decimal of a million
		var step := (100 if low < 100000 else 1000) if mult == 1000 else 100000
		return [low, low + step - 1]
	t = t.replace(",", "").replace(".", "")
	if not t.is_valid_int():
		return [-1, -1]
	return [int(t), int(t)]


## Always exact, grouped (1 000 / 1,000).
static func fmt_exact(n: int) -> String:
	var sep := NBSP if L.lang() == "ru" else ","
	var t := str(absi(n))
	var out := ""
	while t.length() > 3:
		out = sep + t.substr(t.length() - 3) + out
		t = t.substr(0, t.length() - 3)
	return (MINUS if n < 0 else "") + t + out


## A decimal with the locale separator: 54,6 / 54.6.
static func fmt_dec(x: float, d := 1) -> String:
	var s := ("%." + str(d) + "f") % absf(x)
	if L.lang() == "ru":
		s = s.replace(".", ",")
	return (MINUS if x < 0.0 and s.trim_prefix("0").replace("0", "").replace(",", "").replace(".", "") != "" else "") + s


## A store price placeholder («$7.99», until the store SDK gives localized prices) as the player reads it (§3.7):
## RU «7,99 $», EN «$7.99». Anything that is not «$<number>» passes through as it is.
static func store_price(s: String) -> String:
	var t := s.strip_edges()
	if not t.begins_with("$"):
		return t
	var num := t.substr(1).replace(",", ".")
	if not num.is_valid_float():
		return t
	return (num.replace(".", ",") + NBSP + "$") if L.lang() == "ru" else "$" + num


## 42 с · 1:06 · 2ч 57м · 3д 4ч
static func fmt_time(sec: int) -> String:
	sec = maxi(0, sec)
	if sec < 60:
		return L.t("time.s") % sec
	if sec < 3600:
		return "%d:%02d" % [sec / 60, sec % 60]
	if sec < 86400:
		return L.t("time.hm") % [sec / 3600, (sec % 3600) / 60]
	return L.t("time.dh") % [sec / 86400, (sec % 86400) / 3600]


## RU: 3 forms (1 осколок, 2 осколка, 5 осколков); EN: 2. A form with %d gets the number.
static func plural(n: int, forms: Array) -> String:
	var i := 0
	if L.lang() == "ru" and forms.size() >= 3:
		var m10 := absi(n) % 10
		var m100 := absi(n) % 100
		if m10 == 1 and m100 != 11:
			i = 0
		elif m10 >= 2 and m10 <= 4 and (m100 < 12 or m100 > 14):
			i = 1
		else:
			i = 2
	else:
		i = 0 if absi(n) == 1 else mini(1, forms.size() - 1)
	var f := String(forms[i])
	return f % n if f.contains("%d") else f


## Splits a caption into two lines at '\n' or at the space nearest the middle.
static func two_lines(text: String) -> String:
	if text.contains("\n"):
		return text
	var mid := text.length() / 2
	var best := -1
	for i in text.length():
		if text[i] == " " and (best < 0 or absi(i - mid) < absi(best - mid)):
			best = i
	if best < 0:
		return text
	return text.substr(0, best) + "\n" + text.substr(best + 1)


# ------------------------------------------------------------------ motion (§3.6)

static var reduce_motion := false


static func _dur(t: float) -> float:
	return 0.0 if reduce_motion or DisplayServer.get_name() == "headless" else t


static func press_in(b: Control) -> void:
	b.pivot_offset = b.size * 0.5
	var d := _dur(0.07)
	if d <= 0.0:
		b.set("press", 1.0)
		b.scale = Vector2(0.96, 0.96)
		return
	var tw := b.create_tween().set_parallel().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(b, "press", 1.0, d)
	tw.tween_property(b, "scale", Vector2(0.96, 0.96), d)


static func press_out(b: Control) -> void:
	var d := _dur(0.14)
	if d <= 0.0:
		b.set("press", 0.0)
		b.scale = Vector2.ONE
		return
	var tw := b.create_tween().set_parallel().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(b, "press", 0.0, d)
	tw.tween_property(b, "scale", Vector2.ONE, d)


## A window appears: 0.86 → 1.0 over 240 ms, BACK/OUT, from its centre.
static func pop_in(node: Control) -> void:
	node.pivot_offset = node.size * 0.5
	var d := _dur(0.24)
	if d <= 0.0:
		node.scale = Vector2.ONE
		return
	node.scale = Vector2(0.86, 0.86)
	node.create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT).tween_property(node, "scale", Vector2.ONE, d)


## A window closes: 120 ms to 0.94 and transparent, then freed (at once when headless or with reduced motion).
static func close_fx(node: Node) -> void:
	if not is_instance_valid(node):
		return
	if node is Control:
		(node as Control).mouse_filter = Control.MOUSE_FILTER_IGNORE
		node.propagate_call("set_mouse_filter", [Control.MOUSE_FILTER_IGNORE])
	var d := _dur(0.12)
	if d <= 0.0 or not (node is CanvasItem) or not node.is_inside_tree():
		node.queue_free()
		return
	var ci := node as CanvasItem
	var tw := ci.create_tween().set_parallel()
	if ci is Control:
		(ci as Control).pivot_offset = (ci as Control).size * 0.5
		tw.tween_property(ci, "scale", Vector2(0.94, 0.94), d)
	tw.tween_property(ci, "modulate:a", 0.0, d)
	passing_fade(ci)  # (freed at its end)
	tw.chain().tween_callback(ci.queue_free)


## «Unavailable» answers: x ±8, 3 cycles, 240 ms.
static func shake(node: Control) -> void:
	if not node.has_meta("kit_shake_x"):
		node.set_meta("kit_shake_x", node.position.x)
	var x0: float = node.get_meta("kit_shake_x")
	var d := _dur(0.04)
	if d <= 0.0:
		node.position.x = x0
		return
	var tw := node.create_tween()
	for i in 3:
		tw.tween_property(node, "position:x", x0 + 8.0, d)
		tw.tween_property(node, "position:x", x0 - 8.0, d)
	tw.tween_property(node, "position:x", x0, d * 0.5)
	tw.tween_callback(func(): node.remove_meta("kit_shake_x"))


static func badge_pop(node: Control) -> void:
	node.pivot_offset = node.size * 0.5
	var d := _dur(0.24)
	if d <= 0.0:
		node.scale = Vector2.ONE
		return
	node.scale = Vector2.ZERO
	var tw := node.create_tween().set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(node, "scale", Vector2(1.15, 1.15), d * 0.6)
	tw.tween_property(node, "scale", Vector2.ONE, d * 0.4)


## The one breathing element on a screen (a tutorial target, a fresh free reward).
static func breathe(node: Control) -> void:
	if reduce_motion or DisplayServer.get_name() == "headless":
		return
	node.pivot_offset = node.size * 0.5
	var tw := node.create_tween().set_loops().set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(node, "scale", Vector2(1.03, 1.03), 0.45)
	tw.tween_property(node, "scale", Vector2.ONE, 0.45)


## TAB: the new content of a switched tab fades in (120 ms).
static func fade_in(node: CanvasItem, d := 0.12) -> void:
	var t := _dur(d)
	if t <= 0.0:
		node.modulate.a = 1.0
		return
	node.modulate.a = 0.0
	var tw := node.create_tween()
	tw.tween_property(node, "modulate:a", 1.0, t)
	passing_fade(node, tw)


## Marks `node`'s modulate α as a passing fade (a window closing, a tab's content or a toast fading in or out): what
## is under it is drawn from its images as it stands, the whole faded as one piece for those few frames — not made
## again at each α of the tween (KitBake.chain_alpha leaves it out). `tw`: the tween; the mark goes when it ends (a
## node freed at its end needs none).
static func passing_fade(node: CanvasItem, tw: Tween = null) -> void:
	node.set_meta(&"kit_fade", true)
	if tw != null:
		tw.finished.connect(_fade_passed.bind(weakref(node)))


static func _fade_passed(w: WeakRef) -> void:
	var n := w.get_ref() as CanvasItem
	if n != null:
		n.remove_meta(&"kit_fade")


static func count_up(l: Label, from: int, to: int, ms := 450) -> void:
	var d := _dur(ms / 1000.0)
	if d <= 0.0:
		l.text = fmt_num(to)
		return
	l.create_tween().tween_method(func(v: float): l.text = fmt_num(roundi(v)), float(from), float(to), d)


# ------------------------------------------------------------------ paper shim (legacy windows; a no-op since s14)

## Since s14 every modal is rebuilt on the kit and sets meta `kit_native` on its frame, so this is a no-op; it stays
## as the safety net for a future legacy window: its light text becomes ink, its dark inner panels become wells, and
## the first such window is logged once (paper_count counts them all, 0 in a healthy build).
static var paper_count := 0


static func paperize(box) -> void:
	if not is_instance_valid(box) or not (box is Control) or (box as Control).has_meta("kit_native"):
		return
	paper_count += 1
	if paper_count == 1:
		push_warning("Kit.paperize: a modal without meta kit_native was recoloured by the legacy shim (%s); rebuild it on the kit" % (box as Control).name)
	var panels: Array = []
	var labels: Array = []
	_collect(box, panels, labels, false)
	for p in panels:
		var pc := p as Control
		var sb := flat_of(pc)
		if sb == null or sb.bg_color.a < 0.05:
			continue
		var lum := sb.bg_color.get_luminance()
		if sb.has_meta("kit_track"):
			var t := style(CREAM_DEEP, sb.corner_radius_top_left, 0, INK, 0, 0)
			t.set_meta("kit_kind", "")
			set_panel(pc, t)
			pc.set_meta("well", true)
		elif lum < 0.3 or (sb.bg_color.a < 0.5 and not sb.has_meta("kit_role")):
			var accent: Color = sb.get_meta("kit_accent", Color(0, 0, 0, 0))
			var face := CREAM_WELL
			if sb.bg_color.a < 0.5 and lum >= 0.3:
				face = CREAM_WELL.lerp(Color(sb.bg_color, 1.0), sb.bg_color.a)
			var r := mini(20, int(minf(pc.size.x, pc.size.y) * 0.5)) if pc.size.y > 0 else 20
			var w := style(face, r, 4 if accent.a > 0.0 else 0, accent if accent.a > 0.0 else INK, 0, 0)
			w.set_meta("kit_kind", "")
			set_panel(pc, w)
			pc.set_meta("well", true)
	for l in labels:
		var lb := l as Label
		var c := lb.get_theme_color("font_color")
		var nc := c
		var lum := c.get_luminance()
		if lum > 0.85:
			nc = INK_TEXT
		elif c.r > 0.85 and c.g > 0.6 and c.b < 0.6:
			nc = WARN_CREAM
		elif c.s < 0.25 and lum >= 0.55 and lum <= 0.85:
			nc = MUTED_CREAM
		elif c.g > 0.7 and c.g > c.r + 0.15 and c.g > c.b + 0.1:
			nc = POS_CREAM
		elif c.r > 0.75 and c.r > c.g + 0.25 and c.r > c.b + 0.25:
			nc = NEG_CREAM
		elif lum >= 0.5:
			nc = SOFT_CREAM
		if nc != c or lum >= 0.5:
			lb.add_theme_color_override("font_color", nc)
			lb.add_theme_constant_override("outline_size", 0)
			lb.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0))
			lb.add_theme_constant_override("shadow_outline_size", 0)


## Panels inside `box` (not buttons) and labels whose nearest panel is the box or a dark panel (a future well).
static func _collect(node: Node, panels: Array, labels: Array, in_button: bool) -> void:
	for ch in node.get_children():
		if ch is KitButton or ch is KitShape:
			continue
		var is_panel := (ch is Panel or ch is PanelContainer) and not (ch is KitDecor)
		var sub_in_button := in_button
		if is_panel:
			var sb := flat_of(ch as Control)
			var dark := sb != null and sb.bg_color.a >= 0.05 and (sb.bg_color.get_luminance() < 0.3 or sb.bg_color.a < 0.5 or sb.has_meta("kit_track"))
			if not dark:
				sub_in_button = true  # a coloured legacy button: its labels stay white
			panels.append(ch)
		elif ch is Label and not in_button:
			labels.append(ch)
		_collect(ch, panels, labels, sub_in_button)


# ------------------------------------------------------------------ safe area (§3.1)

static func _canvas_scale(node: Node) -> float:
	var vp := node.get_viewport()
	var win := DisplayServer.window_get_size()
	if vp == null or win.y <= 0:
		return 1.0
	return vp.get_visible_rect().size.y / float(win.y)


## The canvas y of the visible bottom minus the system's bottom inset (VB of §3.1).
static func vb(node: Node) -> float:
	var vp := node.get_viewport()
	if vp == null:
		return 1672.0
	var vis := vp.get_visible_rect()
	var bottom := vis.end.y
	if DisplayServer.get_name() == "headless":
		return bottom
	var safe := DisplayServer.get_display_safe_area()
	var win := DisplayServer.window_get_size()
	var wpos := DisplayServer.window_get_position()
	if safe.size.y > 0 and win.y > 0:
		var inset := float(wpos.y + win.y - safe.end.y)
		bottom -= clampf(inset, 0.0, win.y * 0.1) * _canvas_scale(node)
	return bottom


## The system's top inset in canvas units (status bar, notch).
static func top_inset(node: Node) -> float:
	if DisplayServer.get_name() == "headless":
		return 0.0
	var safe := DisplayServer.get_display_safe_area()
	var win := DisplayServer.window_get_size()
	var wpos := DisplayServer.window_get_position()
	if safe.size.y <= 0 or win.y <= 0:
		return 0.0
	return clampf(float(safe.position.y - wpos.y), 0.0, win.y * 0.1) * _canvas_scale(node)


# ------------------------------------------------------------------ tooltip (§4.11)

## Closes on the next tap anywhere (the tap still reaches the game).
class KitTip extends Control:
	var _born := 0

	func _ready() -> void:
		_born = Engine.get_process_frames()

	func _input(e: InputEvent) -> void:
		if Engine.get_process_frames() <= _born:
			return
		if (e is InputEventMouseButton and e.pressed) or (e is InputEventScreenTouch and e.pressed):
			queue_free()


static var _tip: Node


## A cream bubble above (or under) `source`, never covering it, 16 px from the screen edges. `below`: under it when
## there is room (a source at a window's top: above, the tip would cover the title plate and ✕).
static func tooltip(source: Control, title: String, text := "", below := false) -> Control:
	if is_instance_valid(_tip):
		_tip.queue_free()
	var tree := source.get_tree()
	if tree == null:
		return null
	var layer := CanvasLayer.new()
	layer.layer = 90
	tree.root.add_child(layer)
	_tip = layer
	var tip := KitTip.new()
	tip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tip.z_index = 90
	layer.add_child(tip)
	tip.tree_exited.connect(func(): if is_instance_valid(layer): layer.queue_free())
	var max_w := 560.0
	var pad := Vector2(20, 16)
	var tl: Label = null
	var bl: Label = null
	var w := 0.0
	var y := pad.y
	if title != "":
		tl = label(title, 28, INK_TEXT, true)
		w = maxf(w, minf(text_w(title, 28, "d900", false), max_w - 2.0 * pad.x))
	if text != "":
		bl = label(text, 26, SOFT_CREAM, false)
		bl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		bl.max_lines_visible = 4
		for ln in text.split("\n"):  # the longest line, not the whole text as one
			w = maxf(w, minf(text_w(ln, 26, "b800", false) + 2.0, max_w - 2.0 * pad.x))
	w = maxf(w, 160.0)
	var box := Panel.new()
	set_panel(box, style(CREAM, 24, 4, INK, 6, 6))
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tip.add_child(box)
	if tl:
		tl.position = Vector2(pad.x, y)
		tl.size = Vector2(w, 36)
		box.add_child(tl)
		y += 38.0
	if bl:
		bl.position = Vector2(pad.x, y)
		bl.custom_minimum_size = Vector2(w, 0)
		bl.size = Vector2(w, 0)
		box.add_child(bl)
		var lines := mini(4, bl.get_line_count())
		y += maxf(1, lines) * 36.0
	var bw := w + 2.0 * pad.x
	var bh := y + pad.y + 6.0
	box.size = Vector2(bw, bh)
	var dec := KitDecor.new()
	box.add_child(dec)
	box.move_child(dec, 0)
	var vp := source.get_viewport_rect()
	var src := source.get_global_rect()
	var above := src.position.y - bh - 28.0 >= 16.0 and not (below and src.end.y + 26.0 + bh <= vp.size.y - 16.0)
	var by := src.position.y - bh - 26.0 if above else src.end.y + 26.0
	var bx := clampf(src.get_center().x - bw * 0.5, 16.0, vp.size.x - 16.0 - bw)
	box.position = Vector2(bx, by)
	var tail := KitShape.new("tail", CREAM)
	tail.data = {"up": not above}
	tail.size = Vector2(28, 20)
	tail.position = Vector2(clampf(src.get_center().x - bx - 14.0, 20.0, bw - 48.0), bh - 4.0 if above else -16.0)
	box.add_child(tail)
	pop_in(box)
	return tip
