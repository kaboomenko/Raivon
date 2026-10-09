extends RefCounted
## Raivon UI kit — the design tokens and components of docs/ui_style.md (§3 tokens, §4 components).
## Every screen uses it as `const Kit := preload("res://scripts/ui_kit.gd")` (no class_name, like the rest of
## the project). This is the only UI file where Color literals are allowed (tools/ui_lint.py R1).
## All numbers are in the 941×1672 design space.

const SELF := preload("res://scripts/ui_kit.gd")
const L := preload("res://scripts/l10n.gd")

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
const MAP_ROCK := Color("a9aebb")  ## minimap mountains (the land is in the states' colours, water shows the well)
const WHITE := Color(1, 1, 1)

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
const LOCK_MOD := Color(0.55, 0.57, 0.62)  ## a closed item's icon (§3.5)

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
	var _sb := StyleBoxFlat.new()
	var _gl := StyleBoxFlat.new()

	func _init() -> void:
		name = "KitDecor"
		mouse_filter = Control.MOUSE_FILTER_IGNORE
		set_anchors_preset(Control.PRESET_FULL_RECT)
		_sb.anti_aliasing = true
		_sb.corner_detail = 10
		_gl.anti_aliasing = true
		_gl.corner_detail = 8

	func _enter_tree() -> void:
		var p := get_parent() as CanvasItem
		if p and not p.draw.is_connected(queue_redraw):
			p.draw.connect(queue_redraw)

	func _draw() -> void:
		var p := get_parent() as Control
		if p == null:
			return
		var sb := p.get_theme_stylebox("panel") as StyleBoxFlat
		if sb == null or not sb.has_meta("kit_lip") or sb.bg_color.a < 0.99:
			return
		var out := float(sb.border_width_left)
		var r := float(sb.corner_radius_top_left)
		var face := sb.bg_color
		var lip := float(sb.get_meta("kit_lip", 0))
		if size.y < 52.0:
			lip = minf(lip, 5.0)
		if size.y < 36.0:
			lip = 0.0
		var inner := Rect2(out, out, size.x - 2.0 * out, size.y - 2.0 * out)
		if lip > 0.0:
			_sb.bg_color = face
			# concentric with each of the parent's corners (one may be square: the tray under the first tab)
			_sb.corner_radius_top_left = int(maxf(0.0, sb.corner_radius_top_left - out))
			_sb.corner_radius_top_right = int(maxf(0.0, sb.corner_radius_top_right - out))
			_sb.corner_radius_bottom_left = int(maxf(0.0, sb.corner_radius_bottom_left - out))
			_sb.corner_radius_bottom_right = int(maxf(0.0, sb.corner_radius_bottom_right - out))
			_sb.border_width_bottom = int(lip)
			_sb.border_color = sb.get_meta("kit_lip_color", face.darkened(0.3))
			draw_style_box(_sb, inner)
		var kind: String = sb.get_meta("kit_kind", "")
		var rl := maxf(float(sb.corner_radius_top_left), 12.0)
		var rr := maxf(float(sb.corner_radius_top_right), 12.0)
		if kind == "slate" and size.x > rl + rr + 8.0:
			draw_line(Vector2(rl, out + 1.0), Vector2(size.x - rr, out + 1.0), SLATE_HI, 2.0)
		elif kind == "cream" and size.x > 64.0:
			var inset := 24.0 if size.x > 200.0 else maxf(r, 12.0)
			draw_line(Vector2(inset, out + 2.0), Vector2(size.x - inset, out + 2.0), Color(1, 1, 1, 0.7), 3.0)
		elif kind == "role" and size.y >= 30.0 and not face.is_equal_approx(ROLE["lock"][0]):  # «unavailable»: no gloss
			var fh := inner.size.y - lip
			var side := 12.0 if size.y >= 104.0 else 8.0
			_gl.bg_color = SELF.gloss(face)
			_gl.set_corner_radius_all(int(maxf(4.0, r - out - 6.0)))
			draw_style_box(_gl, Rect2(out + side, out + 5.0, inner.size.x - 2.0 * side, maxf(4.0, fh * 0.34)))


# ------------------------------------------------------------------ vector chrome and shapes

## Draws kit shapes: vector chrome (x, check, chevron_left/right, plus, minus, arrow_up, arrow_right, swap), stars,
## hex badges, the title plate, dots, discs, bars, the blueprint grid and the tooltip tail. Never a font glyph.
class KitShape extends Control:
	var kind := ""
	var face := Color.WHITE
	var lip := Color.BLACK
	var data := {}

	func _init(k := "", f := Color.WHITE) -> void:
		kind = k
		face = f
		mouse_filter = Control.MOUSE_FILTER_IGNORE

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

	func _draw() -> void:
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
			"tail":  # tooltip tail pointing down (data.up = true: up)
				var up: bool = data.get("up", false)
				var p := PackedVector2Array([Vector2(0, 0), Vector2(size.x, 0), Vector2(size.x * 0.5, size.y)]) if not up \
					else PackedVector2Array([Vector2(0, size.y), Vector2(size.x, size.y), Vector2(size.x * 0.5, 0)])
				draw_colored_polygon(p, face)
				draw_line(p[0], p[2], INK, 4.0, true)
				draw_line(p[1], p[2], INK, 4.0, true)

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
		draw_style_box(o, Rect2(0, 0, w, h))
		var ih := h - 6.0
		var t := StyleBoxFlat.new()
		t.anti_aliasing = true
		t.bg_color = CREAM_DEEP if paper else SLATE_WELL
		t.set_corner_radius_all(int(ih * 0.5))
		draw_style_box(t, Rect2(3, 3, w - 6.0, ih))
		if frac <= 0.0:
			return
		var fw := maxf(ih, (w - 6.0) * frac)
		var f := StyleBoxFlat.new()
		f.anti_aliasing = true
		f.bg_color = face
		f.set_corner_radius_all(int(ih * 0.5))
		f.border_width_bottom = int(maxf(1.0, ih * 0.18))
		f.border_color = face.darkened(0.25)
		draw_style_box(f, Rect2(3, 3, fw, ih))
		if fw > ih:
			var gl := StyleBoxFlat.new()
			gl.anti_aliasing = true
			gl.bg_color = Color(1, 1, 1, 0.3)
			gl.set_corner_radius_all(int(ih * 0.15))
			draw_style_box(gl, Rect2(3.0 + ih * 0.35, 3.0 + ih * 0.12, fw - ih * 0.7, maxf(2.0, ih * 0.3)))


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
		add_theme_stylebox_override("panel", _sb)
		for it in items:
			var a: Array = it
			var ic: TextureRect = null
			var tex := SELF.icon_tex(String(a[0])) if a.size() > 0 else null
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

	## The items shown: all of them (at most 2), or the scarcest one when compact / more than two.
	func _shown() -> Array:
		if _rows.size() <= 2 and not compact:
			return _rows
		for r in _rows:
			if r["short"]:
				return [r]
		return _rows.slice(0, 1)

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
				x += 6.0
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
			if apply:
				_more.text = mt
				_more.visible = true
				_num(_more, num, TEXT, x, mw, h)
			x += mw
		elif apply:
			_more.visible = false
		return x + maxf(9.0, roundf(h * 0.24))

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
	var cb := Callable()
	var cap: Label
	var press := 0.0:
		set(v):
			press = v
			_apply_press()
	var _parts: Array = []  # [{node, kind, base, text}]
	var _down := false
	var _fired_frame := -1
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
				tr_.texture = SELF.icon_tex(String(pc["i"]))
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
		var p_steps := SELF.fit_steps(int(pg[1]), int(pg[2]))
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
		for s in SELF.fit_steps(int(g[4]), cap_floor):
			if _row_w(parts, s, icon_side, gap, pw0) <= avail:
				return _plan(parts, s, ph, p_steps[0], pi)
		if pp != null:
			# then the price's number
			for pn in p_steps:
				if _row_w(parts, cap_floor, icon_side, gap, pp.width_for(ph, pn, pi)) <= avail:
					return _plan(parts, cap_floor, ph, pn, pi)
			# L / M: the caption over the price, beside the icon
			if STACK_GEOM.has(c) and not texts.is_empty():
				var sg: Array = STACK_GEOM[c]
				var sph := float(sg[2])
				var spi := float(sg[5])
				var row := parts.filter(func(p): return p["kind"] != "price" and p["kind"] != "main_icon")
				var lead := icon_side + gap if parts.any(func(p): return p["kind"] == "main_icon") else 0.0
				for s in SELF.fit_steps(int(sg[0]), int(sg[1])):
					if s * 1.2 + 2.0 + sph > face_h - 2.0:
						continue
					var cw := _row_w(row, s, icon_side, gap, 0.0)
					for pn in SELF.fit_steps(int(sg[3]), int(sg[4])):
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

	func _draw() -> void:
		var g := geom()
		var r: float = g[0]
		var out: float = g[1]
		var lip: float = g[2]
		var sh: float = g[3]
		var w := size.x
		var h := size.y
		var lip_now := lerpf(lip, 2.0, press)
		var dy := lip - lip_now
		var face := face_color()
		if press < 0.5 and sh > 0.0:
			_sb.bg_color = Color(INK, SHADOW_A)
			_sb.set_corner_radius_all(int(r))
			_sb.border_width_bottom = 0
			draw_style_box(_sb, Rect2(0, sh, w, h))
		_sb.bg_color = INK
		_sb.set_corner_radius_all(int(r))
		_sb.border_width_bottom = 0
		draw_style_box(_sb, Rect2(0, dy, w, h - dy))
		_sb.bg_color = face
		_sb.set_corner_radius_all(int(maxf(0.0, r - out)))
		_sb.border_width_bottom = int(lip_now)
		_sb.border_color = lip_color()
		var inner := Rect2(out, dy + out, w - 2.0 * out, h - dy - 2.0 * out)
		draw_style_box(_sb, inner)
		_sb.border_width_bottom = 0
		var face_h := inner.size.y - lip_now
		if enabled and role != "lock":  # «unavailable» never has a gloss (§4.1), also on a lock button that answers
			var side := 12.0 if cls() == "L" else 8.0
			if round_btn:
				side = maxf(side, r * 0.45)
			_sb.bg_color = SELF.gloss(face)
			_sb.set_corner_radius_all(int(maxf(4.0, r - out - 6.0)))
			draw_style_box(_sb, Rect2(out + side, dy + out + 5.0, inner.size.x - 2.0 * side, maxf(4.0, face_h * 0.34)))
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
		else:
			return
		var frame := Engine.get_process_frames()
		if is_press:
			if _down:
				return  # the emulated mouse twin of a touch
			_down = true
			SELF.press_in(self)
			if hold and enabled:
				_hold_t = 0.0
				set_process(true)
		elif is_release:
			if _fired_frame == frame:
				return
			_fired_frame = frame
			_down = false
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
				elif was:
					pass  # released early: nothing happens
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
## (§3.6 POP_IN); a window replaced in the same frame passes false.
static func title_plate(panel: Control, text: String, role := "info", icon := "", animate := true) -> KitShape:
	var h := 84.0
	var has_icon := icon != "" and icon_tex(icon) != null
	var tw := text_w(text, 46, "d900")
	var w := clampf(tw + 108.0 + (64.0 if has_icon else 0.0), 320.0, maxf(320.0, panel.size.x - 200.0))
	var s := KitShape.new("plate", face_of(role))
	s.lip = lip_of(role)
	s.size = Vector2(w, h)
	s.position = Vector2((panel.size.x - w) * 0.5, -42.0)
	panel.add_child(s)
	var tx := 54.0 + (64.0 if has_icon else 0.0)
	var l := label(text, 46, TEXT, true)
	l.add_theme_font_size_override("font_size", fit_size(text, 46, w - tx - 54.0, "d900", 32))
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	l.position = Vector2(tx, 0)
	l.size = Vector2(w - tx - 54.0, h - 12.0)
	s.add_child(l)
	if has_icon:
		var ic := TextureRect.new()
		ic.texture = icon_tex(icon)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.size = Vector2(92, 92)
		ic.position = Vector2(-22, (h - 92.0) * 0.5 - 6.0)
		s.add_child(ic)
	var d := _dur(0.22)
	if animate and d > 0.0:
		s.position.y = -62.0
		s.modulate.a = 0.0
		var drop := s.create_tween().set_parallel()
		drop.tween_property(s, "position:y", -42.0, d).set_delay(0.06).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
		drop.tween_property(s, "modulate:a", 1.0, d * 0.5).set_delay(0.06)
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
	p.add_theme_stylebox_override("panel", sb)
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

	func _box(r: Rect2, col: Color, rad: float) -> void:
		_sb.draw_center = true
		_sb.bg_color = col
		_sb.set_border_width_all(0)
		_sb.set_corner_radius_all(int(rad))
		draw_style_box(_sb, r)

	func _draw() -> void:
		var w := size.x
		var h := size.y
		var r := h * 0.5
		_box(Rect2(0, 4, w, h), Color(INK, SHADOW_A), r)
		_box(Rect2(0, 0, w, h), INK, r)
		var face := Rect2(4, 4, w - 8.0, h - 8.0)
		_box(face, SLATE_WELL, r - 4.0)
		if frac > 0.0:
			var fw := maxf(face.size.y, face.size.x * frac)
			_box(Rect2(face.position, Vector2(fw, face.size.y)), FULL if full else SLATE_FILL, r - 4.0)
		# sunken: the rim of the body casts a shade along the top of the face
		_sb.draw_center = false
		_sb.set_border_width_all(0)
		_sb.border_width_top = 4
		_sb.border_color = Color(INK, 0.5)
		_sb.set_corner_radius_all(int(r - 4.0))
		draw_style_box(_sb, face)
		_sb.draw_center = true

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
	p.ic.texture = icon_tex(icon)
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
	var title := ""
	var details := ""
	var body: Panel
	var art: Panel
	var pic: Control  ## the backdrop and the picture (dimmed together when locked)
	var name_label: Label
	var cta: KitButton
	var chip: Control
	var chip_cb := Callable()
	var _press_at := Vector2(-1, -1)
	var _tap_frame := -1

	func _init() -> void:
		name = "card"
		add_theme_stylebox_override("panel", StyleBoxEmpty.new())
		mouse_filter = Control.MOUSE_FILTER_PASS
		custom_minimum_size = Vector2(W, H)
		size = custom_minimum_size
		size_flags_vertical = Control.SIZE_SHRINK_BEGIN
		gui_input.connect(_on_input)

	func _on_input(e: InputEvent) -> void:
		var pos := Vector2.ZERO
		var pressed := false
		if e is InputEventMouseButton and (e as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
			pos = (e as InputEventMouseButton).position
			pressed = e.pressed
		elif e is InputEventScreenTouch:
			pos = (e as InputEventScreenTouch).position
			pressed = e.pressed
		else:
			return
		if pressed:
			_press_at = pos
			return
		var from := _press_at
		_press_at = Vector2(-1, -1)
		var f := Engine.get_process_frames()
		if f == _tap_frame or from.x < 0.0 or from.distance_to(pos) > 16.0 or not Rect2(Vector2.ZERO, size).has_point(pos):
			return  # the emulated mouse twin of a touch, or a drag that scrolled the row
		if cta != null and cta.visible and Rect2(body.position + cta.position, cta.size).has_point(pos):
			return  # the button acts on its own
		_tap_frame = f
		if chip != null and chip.visible and Rect2(body.position + chip.position, chip.size).grow(6.0).has_point(pos):
			if not (chip is KitButton) and chip_cb.is_valid():
				chip_cb.call()
			return
		SELF.tooltip(self, title, details)


## A tray card (§4.4) — see KitCard. `art_tex` is cover-cropped into the art window, or, with opts.art_side, drawn
## as an icon of that side centred at opts.art_y (default 42) on the backdrop. opts:
##   backdrop: "sky" (default: the sky gradient over a grass strip) | "blueprint" | "team" (+ team: Color) | "cream"
##   art_node: a Control laid into the art window (172×104 local coordinates) over the picture
##   badge: the text of the top-left hex badge (R 22, centre 16, 16); badge_role (info)
##   tag: a short text on an INK pill at the art's top-left instead of a badge («7/12»)
##   chip: {node: Control} (a portrait, clipped round) | {plus: true} (a go «+» button) | {icon: name}; chip_cb
##   dot: the role of a dot on the card's corner; dot_n: its number (-1: none)
##   art_bar: {frac, role}: an S bar along the art's bottom, under the name
##   cta: {role, caption, icon, price ([[icon, text, short]] ≤ 2), cb, enabled, reason} → an XS button at
##        (6, 114, 168, 46); without a cb it opens the card's tooltip; a disabled one shows `reason` when tapped
##   stat: {icon, text, bar_frac, bar_role, check} → icon 36 + NUM_S 26, an optional S bar at y 146, a go check
##   locked: dark art + a lock 56; the cta becomes lock XS with a lock and opts.lock_caption («УР3»), its tap shows
##           opts.reason
##   selected: a brass outline 5 and a 6 px lift
##   details: the tooltip text of a tap on the body
static func card(art_tex: Texture2D, title: String, opts := {}) -> KitCard:
	var c := KitCard.new()
	c.title = title
	c.details = String(opts.get("details", ""))
	var sel: bool = opts.get("selected", false)
	var locked: bool = opts.get("locked", false)
	var b := Panel.new()
	b.name = "body"
	b.mouse_filter = Control.MOUSE_FILTER_IGNORE
	b.size = Vector2(KitCard.W, KitCard.H)
	var sb := style(SLATE, 20, 5 if sel else 4, face_of("brass") if sel else INK, 5, 6)
	b.add_theme_stylebox_override("panel", sb)
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
	aw.add_theme_stylebox_override("panel", asb)
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
	if art_tex != null:
		var side := float(opts.get("art_side", 0.0))
		if side > 0.0:
			var cy := float(opts.get("art_y", 42.0))
			var ic := _card_rect(art_tex, Rect2((w - side) * 0.5, cy - side * 0.5, side, side))
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
		var side := float(opts.get("art_side", 0.0))
		var lc := Vector2(w * 0.5, 42.0)
		if side > 0.0 and art_tex != null:
			lc = Vector2(w * 0.5, float(opts.get("art_y", 42.0))) + Vector2(side * 0.36, side * 0.18)
		var lk := _card_rect(icon_tex("lock"), Rect2(lc - Vector2(28, 28), Vector2(56, 56)))
		lk.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		aw.add_child(lk)
	# ---- the name on its scrim (an S bar under it with art_bar)
	var bar_d: Dictionary = opts.get("art_bar", {})
	var nw := w - 12.0
	var ns := fit_size(title, 26, nw, "d900", 22)
	var long := text_w(title, ns, "d900") > nw
	var two := long and title.strip_edges().contains(" ")  # two lines at 22; one long word is cut instead
	if long:
		ns = 22
	var name_bottom := h - (28.0 if not bar_d.is_empty() else 3.0)
	var sh := minf(h, (h - name_bottom) + (ns * 1.25) * (2.0 if two else 1.0) + 18.0)
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
		nl.add_theme_constant_override("line_spacing", -4)
	elif long:
		nl.clip_text = true
		nl.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	nl.position = Vector2(6, name_bottom - 64.0)
	nl.size = Vector2(nw, 64.0)
	aw.add_child(nl)
	c.name_label = nl
	if not bar_d.is_empty():
		bar(aw, Rect2(8, h - 24.0, w - 16.0, 16.0), float(bar_d.get("frac", 0.0)), String(bar_d.get("role", "go")))
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
		var why := String(ct.get("reason", ""))
		if why != "":
			btn.denied.connect(func(): SELF.tooltip(btn, title, why))
		c.cta = btn
	else:
		var st: Dictionary = opts.get("stat", {})
		if not st.is_empty():
			_card_stat(b, st)
	# ---- corners: badge or tag top-left, chip top-right, dot
	if opts.has("badge"):
		hex_badge(b, Vector2(16, 16), 22, String(opts.get("badge_role", "info")), String(opts["badge"]))
	elif opts.has("tag"):
		var tg := caption_pill(b, String(opts["tag"]), 32.0, alpha(INK, 0.85), 24)
		tg.name = "tag"
		tg.position = Vector2(o + 4.0, o + 4.0)
	var chd: Dictionary = opts.get("chip", {})
	var chip_r := Rect2(142, -6, 44, 44)  # Ø44 centred on (164, 16)
	if chd.get("plus", false):
		c.chip = button(b, chip_r, "go", "", {"icon": "plus", "round": true, "size": "XS", "filter": Control.MOUSE_FILTER_PASS,
			"cb": opts.get("chip_cb", Callable()), "hit_pad": 8.0})
	elif chd.has("node") or chd.has("icon"):
		var ring := Panel.new()
		ring.name = "chip"
		var rsb := style(SLATE_WELL, 22, 3, INK, 3, 0)
		rsb.set_meta("kit_kind", "")
		ring.add_theme_stylebox_override("panel", rsb)
		ring.position = chip_r.position
		ring.size = chip_r.size
		ring.mouse_filter = Control.MOUSE_FILTER_PASS
		b.add_child(ring)
		var inner := Panel.new()  # the picture inside the ring, clipped round
		var isb := StyleBoxFlat.new()
		isb.bg_color = SKY_LOW
		isb.anti_aliasing = true
		isb.set_corner_radius_all(19)
		inner.add_theme_stylebox_override("panel", isb)
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
		else:
			inner.add_child(_card_rect(icon_tex(String(chd["icon"])), Rect2(3, 3, 32, 32)))
		c.chip = ring
		c.chip_cb = opts.get("chip_cb", Callable())
	if opts.has("dot"):
		var d := dot(b, int(opts.get("dot_n", -1)), String(opts["dot"]))
		d.name = "dot"
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


## The stat line of a tray card's bottom zone: icon 36 + NUM_S 26 (fit to 22), an optional S bar at y 146, an
## optional go check at the right end.
static func _card_stat(b: Control, st: Dictionary) -> void:
	var has_bar := st.has("bar_frac")
	var cy := 128.0 if has_bar else 137.0
	var x := 12.0
	var tex := icon_tex(String(st.get("icon", "")))
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
## timer_war (red). Returns the chip Panel sized to its content.
static func chip(parent: Node, pos: Vector2, icon: String, text: String, kind := "status", fill := Color(0, 0, 0, 0)) -> Panel:
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
	var p := Panel.new()
	var sb := style(face, int(h * 0.5), out, INK, 0, 0)
	sb.set_meta("kit_kind", "")
	p.add_theme_stylebox_override("panel", sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var x := 10.0
	if icon != "" and icon_tex(icon) != null:
		var ic := TextureRect.new()
		ic.texture = icon_tex(icon)
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.mouse_filter = Control.MOUSE_FILTER_IGNORE
		ic.size = Vector2(icon_side, icon_side)
		ic.position = Vector2(6.0, (h - icon_side) * 0.5)
		p.add_child(ic)
		x = 8.0 + icon_side
	var l := label(text, size, TEXT, true)
	l.add_theme_font_override("font", font(font_kind))
	var tw := text_w(text, size, font_kind)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.position = Vector2(x, -1)
	l.size = Vector2(tw, h)
	l.name = "label"
	p.add_child(l)
	p.position = pos
	p.size = Vector2(x + tw + 12.0, h)
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
	node.create_tween().tween_property(node, "modulate:a", 1.0, t)


static func count_up(l: Label, from: int, to: int, ms := 450) -> void:
	var d := _dur(ms / 1000.0)
	if d <= 0.0:
		l.text = fmt_num(to)
		return
	l.create_tween().tween_method(func(v: float): l.text = fmt_num(roundi(v)), float(from), float(to), d)


# ------------------------------------------------------------------ paper shim for screens not rebuilt yet

## Not-yet-migrated modals are cream now: legacy light text becomes ink, dark inner panels become wells.
## Screens rebuilt on the kit set meta `kit_native` on their frame and are skipped.
static func paperize(box) -> void:
	if not is_instance_valid(box) or not (box is Control) or (box as Control).has_meta("kit_native"):
		return
	var panels: Array = []
	var labels: Array = []
	_collect(box, panels, labels, false)
	for p in panels:
		var pc := p as Control
		var sb := pc.get_theme_stylebox("panel") as StyleBoxFlat
		if sb == null or sb.bg_color.a < 0.05:
			continue
		var lum := sb.bg_color.get_luminance()
		if sb.has_meta("kit_track"):
			var t := style(CREAM_DEEP, sb.corner_radius_top_left, 0, INK, 0, 0)
			t.set_meta("kit_kind", "")
			pc.add_theme_stylebox_override("panel", t)
			pc.set_meta("well", true)
		elif lum < 0.3 or (sb.bg_color.a < 0.5 and not sb.has_meta("kit_role")):
			var accent: Color = sb.get_meta("kit_accent", Color(0, 0, 0, 0))
			var face := CREAM_WELL
			if sb.bg_color.a < 0.5 and lum >= 0.3:
				face = CREAM_WELL.lerp(Color(sb.bg_color, 1.0), sb.bg_color.a)
			var r := mini(20, int(minf(pc.size.x, pc.size.y) * 0.5)) if pc.size.y > 0 else 20
			var w := style(face, r, 4 if accent.a > 0.0 else 0, accent if accent.a > 0.0 else INK, 0, 0)
			w.set_meta("kit_kind", "")
			pc.add_theme_stylebox_override("panel", w)
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
			var sb := (ch as Control).get_theme_stylebox("panel") as StyleBoxFlat
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


## A cream bubble above (or under) `source`, never covering it, 16 px from the screen edges.
static func tooltip(source: Control, title: String, text := "") -> Control:
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
	box.add_theme_stylebox_override("panel", style(CREAM, 24, 4, INK, 6, 6))
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
	var above := src.position.y - bh - 28.0 >= 16.0
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
