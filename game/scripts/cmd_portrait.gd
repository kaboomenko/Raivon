extends Control
## A commander's bust (04 §15.3–15.4, docs/art_direction.md §7.12): the bpy render (tools/blender/portrait_assets.py)
## on plate B — a vertical gradient of the rarity colour, rc.lightened(0.18) at the top to rc at the bottom, with a soft
## halo of concentric white circles behind the head (§7.4) — or the 2D stand-in drawn from the §7.6 palettes (uniform,
## head shape, hair, facial hair, headgear and the one detail each has). The whole picture is a rounded box with a
## rarity-coloured frame (docs/ui_style.md §6 «Командиры»: R 20, OUT 4 at full size, scaled down in small slots); a
## locked commander is a flat INK silhouette (α 0.3) cut from the render's alpha, no detail inside, on a muted plate
## (the screen adds the lock). The renders are filtered with mipmaps (the commanders' 512×588 imports have them), so
## the small slots — the army chip, the fan, the calendar, baked through Kit.KitStill or not — do not shimmer. A bust
## drawn at FACE_MAX px or less (the picker 72, the mail 72, the calendar 64, the army chip 48×50) shows the square
## face crop of the same file instead (`face_<name>.png`, 256×256, mipmapped: the head +26–31 % over the bust's;
## tools/blender/portrait_assets.py --frame=face) when there is one, laid by FIT: in a square slot moved down until its
## headgear clears the rarity frame by FACE_CLEAR, in the chip's circle (`circle`) sized and placed so the hat stays
## inside it. A picture whose bottom another layer covers (`hidden_bottom`: the «Армия» tab's «Командиры» fan 58×70
## under the card's name) shows the bust instead, zoomed so the head and its headgear fit the rows left above it.

const Kit := preload("res://scripts/ui_kit.gd")
## The rarity colours are the kit's (§3.2: the gem and the tinted backdrop; purple is only EPIC).
const RARITY := Kit.RARITY
## The 2D stand-in (drawn only when a render is missing): skin, head [w, h], hair color, hair style, facial hair,
## headgear, uniform, accent — the albedos of docs/art_direction.md §7.6 (skin: the §7.4 tone of each face row, Bram's
## T2 moved to peach-pink as decided after P1; hair; the palette's main cloth and its accent).
const LOOK := {
	"cmd_bram": [Color("f2a88e"), [0.36, 0.40], Color("b5562b"), "short", "beard", "", Color("3f4d5e"), Color("e0ad45")],
	"cmd_lira": [Color("f4b48e"), [0.31, 0.40], Color("5a3420"), "braid", "", "kerchief", Color("2e7a44"), Color("f2f0ea")],
	"cmd_olm": [Color("f0a274"), [0.28, 0.43], Color("d0d0d4"), "sides", "", "goggles", Color("7a4e2d"), Color("c9a24a")],
	"cmd_vik": [Color("f0a274"), [0.29, 0.42], Color("ebd27a"), "messy", "", "hood", Color("4e6b3a"), Color("6b4a2a")],
	"cmd_vega": [Color("de9a6c"), [0.30, 0.41], Color("2e2a2a"), "bob", "", "glasses", Color("44484f"), Color("c8ccd4")],
	"cmd_kort": [Color("f0a274"), [0.38, 0.41], Color("f0eef2"), "bald", "mustache_long", "", Color("5d6236"), Color("b0803a")],
	"cmd_seir": [Color("c47a4e"), [0.33, 0.40], Color("cfcfd4"), "short", "beard_short", "tricorn", Color("175a72"), Color("f2f2f2")],
	"cmd_frey": [Color("9a5a38"), [0.35, 0.39], Color("2a2420"), "buzz", "", "", Color("3b5a44"), Color("c8d0da")],
	"cmd_irma": [Color("f4b48e"), [0.30, 0.41], Color("efe9dc"), "ponytail", "", "goggles", Color("3a3c46"), Color("f08a24")],
	"cmd_hawk": [Color("de9a6c"), [0.31, 0.41], Color("4a3424"), "short", "mustache", "flight", Color("5a3a24"), Color("6fa8dc")],
	"cmd_vance": [Color("f4b48e"), [0.30, 0.41], Color("d9d6e2"), "updo", "", "brooch", Color("4b2c78"), Color("8e5bd0")],
	"cmd_rai": [Color("c47a4e"), [0.33, 0.42], Color("eef0f5"), "long", "beard_long", "circlet", Color("eef1f6"), Color("3a8dff")],
}
## The halo behind the head (§7.4 plate B): concentric white discs [radius × the short side, α] round (0.5 w, 0.42 h),
## antialiased, no outline — at the centre +3.2 (legendary orange) to +5.6 (epic purple) L* over plate B of Kit.RARITY,
## +2.6 to +7.2 over the leaders' state plates. §7.4 asks «≈ +12 L*»: tools/qa_portraits gates the art against these
## three discs, and on Kit.RARITY a +12 L* halo (α ≈ 0.25–0.45) takes the silhouette rim of Olm E1 and Rai E1 (calm
## and smile) and Rai's E4 smile past P-A5's 35 % (to 37–39 %; no leader; P4 measure) — +4–6 or +12 is the art
## director's call. (The ruler is not drawn here: hud.gd and game_ui.gd show it on the sky with no halo.) A locked
## plate: HALO_LOCKED each.
const HALO := [[0.40, 0.05], [0.33, 0.05], [0.26, 0.05]]
const HALO_LOCKED := 0.02
## A locked commander: the render's alpha as a flat silhouette in the vertex colour (INK α 0.3) — the texture's
## colours are dropped, so no goggles or grey hair show through; what is drawn without a texture (the plate, the halo,
## the frame) keeps its colours (the default white texture's alpha is 1).
const SILHOUETTE := "shader_type canvas_item;\nvarying vec4 v_col;\nvoid vertex() {\n\tv_col = COLOR;\n}\n" \
	+ "void fragment() {\n\tCOLOR = vec4(v_col.rgb, v_col.a * texture(TEXTURE, UV).a);\n}\n"
static var _sil_mat: ShaderMaterial
## The largest side (px) drawn with the face crop (docs/art_direction.md §7.12: the slots ≤ 72 px showed the whole
## bust, a 27–40 px head); its eye line is at half its height (the bust's at 0.425: the halo follows it).
const FACE_MAX := 72.0
const FACE_EYE := 0.5
const BUST_EYE := 0.42
## The bust's eye line in its own file (512×588: 0.425 h, §7.14 P-A6) — where the halo goes in a fitted slot.
const BUST_EYE_FILE := 0.425
## The gap between the headgear's tip and the inside of the rarity frame in a fitted small slot, in frame widths
## (docs/art_direction.md §7.12: 2 px under the 2 px frame of the 58–72 px slots; it scales with a baked bust).
const FACE_CLEAR := 1.0
## The small slots' fit per commander render (tools/qa_portraits/face_fit.py --gd writes it, --check compares it with
## the shipped files): [face top, chip side, chip top, bust skyline, bust chin] —
## face top: the face crop's highest figure row (of 256; Rai's banner, which leaves the top by design, left out): a
##   square slot moves the crop down until that row is FACE_CLEAR under its frame;
## chip side, chip top: the face crop's side and top over the chip circle's diameter (T2 drew every crop 50 px tall at
##   −6 over the Ø38 circle, 1.3158 / −0.1579): smaller and lower for tall headgear (a colpack, a bicorne, a bun) so it
##   stays whole inside the circle, the head never under 28 px;
## bust skyline, bust chin: the 512×588 bust's highest figure row and its chin row (the fan's zoom, _bust_fit).
const FIT := {
	"cmd_bram": [25, 1.3158, -0.1247, 81, 377.9],
	"cmd_bram_e2": [5, 1.1316, 0.0176, 43, 377.9],
	"cmd_bram_e3": [10, 1.2961, -0.0425, 54, 377.9],
	"cmd_bram_e4": [14, 1.3092, -0.0491, 65, 377.9],
	"cmd_lira": [24, 1.3158, -0.1200, 85, 371.1],
	"cmd_lira_e2": [15, 1.3158, -0.0739, 71, 371.1],
	"cmd_lira_e3": [28, 1.3158, -0.1397, 93, 371.1],
	"cmd_lira_e4": [16, 1.3158, -0.0739, 76, 371.1],
	"cmd_olm": [30, 1.3158, -0.1579, 98, 380.4],
	"cmd_olm_e2": [30, 1.3158, -0.1579, 98, 380.4],
	"cmd_olm_e3": [30, 1.3158, -0.1579, 98, 380.4],
	"cmd_olm_e4": [30, 1.3158, -0.1579, 98, 380.4],
	"cmd_vik": [13, 1.1382, 0.0386, 70, 370.9],
	"cmd_vik_e2": [13, 1.1382, 0.0386, 70, 370.9],
	"cmd_vik_e3": [13, 1.1382, 0.0386, 70, 370.9],
	"cmd_vik_e4": [13, 1.1382, 0.0386, 70, 370.9],
	"cmd_vega": [25, 1.3158, -0.1255, 86, 377.4],
	"cmd_vega_e2": [5, 1.1711, -0.0182, 46, 377.4],
	"cmd_vega_e3": [25, 1.2961, -0.0433, 90, 377.4],
	"cmd_vega_e4": [25, 1.3158, -0.1255, 83, 377.4],
	"cmd_kort": [37, 1.3158, -0.1579, 104, 379.5],
	"cmd_kort_e2": [6, 1.1250, 0.0428, 56, 379.5],
	"cmd_kort_e3": [15, 1.2961, -0.0428, 73, 377.5],
	"cmd_kort_e4": [32, 1.3158, -0.1447, 96, 379.5],
	"cmd_seir": [29, 1.2829, -0.0413, 99, 381.0],
	"cmd_seir_e2": [29, 1.2829, -0.0347, 99, 381.0],
	"cmd_seir_e3": [22, 1.2237, -0.0051, 87, 381.0],
	"cmd_seir_e4": [22, 1.2237, -0.0051, 87, 381.0],
	"cmd_frey": [25, 1.3158, -0.0987, 85, 380.5],
	"cmd_frey_e2": [25, 1.3158, -0.0987, 85, 380.5],
	"cmd_frey_e3": [25, 1.3158, -0.0987, 85, 380.5],
	"cmd_frey_e4": [25, 1.3158, -0.0987, 85, 380.5],
	"cmd_irma": [28, 1.3158, -0.1414, 87, 379.4],
	"cmd_irma_e2": [28, 1.3158, -0.1414, 87, 379.4],
	"cmd_irma_e3": [16, 1.3158, -0.0822, 73, 379.4],
	"cmd_irma_e4": [23, 1.3092, -0.0460, 82, 379.4],
	"cmd_hawk": [29, 1.3158, -0.0947, 95, 380.9],
	"cmd_hawk_e2": [29, 1.3158, -0.0947, 95, 380.9],
	"cmd_hawk_e3": [29, 1.3158, -0.0947, 95, 380.9],
	"cmd_hawk_e4": [27, 1.3158, -0.1144, 90, 380.9],
	"cmd_vance": [5, 1.1447, -0.0270, 33, 378.6],
	"cmd_vance_e2": [5, 1.1447, -0.0270, 33, 378.6],
	"cmd_vance_e3": [5, 1.1447, -0.0270, 33, 378.6],
	"cmd_vance_e4": [5, 1.1447, -0.0270, 33, 378.6],
	"cmd_rai": [11, 1.3158, -0.1247, 51, 377.1],
	"cmd_rai_e2": [23, 1.3158, -0.1492, 51, 377.1],
	"cmd_rai_e3": [11, 1.3158, -0.1247, 51, 377.1],
	"cmd_rai_e4": [11, 1.3158, -0.1247, 51, 377.1],
	"cmd_bram_smile": [25, 1.3158, -0.1240, 80, 377.6],
	"cmd_bram_e2_smile": [5, 1.1250, 0.0225, 44, 377.6],
	"cmd_bram_e3_smile": [9, 1.2829, -0.0352, 53, 377.6],
	"cmd_bram_e4_smile": [14, 1.3158, -0.0516, 65, 377.6],
}

static var _renders := {}  # "cmd_eN_mood" (and "face|…") -> Texture2D or null — the current era's only (_render drops the rest)
static var _mipped := {}  # a commander's file path -> its texture with mipmaps (one per file, see _load_mipmapped)
static var _cache_era := 0  # the era _renders and _mipped hold
## The uniform era of the portraits (04 §15.4): 1 DL1–3, 2 DL4–5, 3 DL6–7, 4 DL8–10 — set from the player's DL.
static var era := 1


static func era_of(dl: int) -> int:
	return 1 if dl <= 3 else (2 if dl <= 5 else (3 if dl <= 7 else 4))

var cmd := ""
var rarity := "common"
var locked := false:
	set(v):
		locked = v
		material = _silhouette() if v else null
		queue_redraw()
var mood := ""  # "" calm, "angry", "smile", "cunning", "tired" — a render of that mood if there is one, else calm
var plate := Color(0, 0, 0, 0)  # a plate colour instead of the rarity's (AI leaders: their state's colour)
var frame := true  # the rarity-coloured frame round the picture (off where the slot draws its own rim)
## The round window the picture is seen through, in its own coordinates (the army chip: Kit._card_ring clips it to a
## circle of 38): the face crop is laid by FIT's chip columns, its headgear inside the circle. Empty: none.
var circle := Rect2()
## px at the picture's bottom that another layer covers (the «Командиры» card's name over its fan): the bust is drawn,
## zoomed so the head (crown to chin) and its headgear fit the rows above, the headgear FACE_CLEAR under the frame.
var hidden_bottom := 0.0:
	set(v):
		hidden_bottom = v
		queue_redraw()
## The render this bust last drew. Its canvas item keeps only the texture's RID, so this reference keeps the texture
## alive until the bust redraws: when the era changes, _render lets the old era's renders go, and a bust not redrawn
## yet (one outside the "kit_era" group) still shows its old face, not a white box.
var _drawn: Texture2D


func _init(id: String = "", r: String = "common", is_locked := false) -> void:
	cmd = id
	rarity = r
	locked = is_locked
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	# the 512×588 renders shrink to 48–160 px slots: sample their mipmaps (also inside a KitStill bake)
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS


static func _silhouette() -> ShaderMaterial:
	if _sil_mat == null:
		var sh := Shader.new()
		sh.code = SILHOUETTE
		_sil_mat = ShaderMaterial.new()
		_sil_mat.shader = sh
	return _sil_mat


## The halo behind the head: the HALO discs round `c` (`u`: the short side), antialiased, no outline.
func _halo(c: Vector2, u: float) -> void:
	for d in HALO:
		draw_circle(c, u * float(d[0]), Color(1, 1, 1, HALO_LOCKED if locked else float(d[1])), true, -1.0, true)


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


## The frame's radius and width: R 20 / OUT 4 at full size (§6), smaller in a small slot (a chip Ø44, the fan's 58 px).
func frame_r() -> float:
	return minf(20.0, minf(size.x, size.y) * 0.25)


func frame_w() -> float:
	return clampf(minf(size.x, size.y) * 0.025, 2.0, 4.0)


## The picture's outline: a rounded box (what the plate, the render and the frame share).
func _box() -> PackedVector2Array:
	var w := size.x
	var h := size.y
	return Kit.round_poly(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)]), frame_r(), 6)


## The face crop in the chip's circle (`circle`), by FIT's chip columns [_, side, top]: its side and its top over the
## circle's diameter, centred on the circle.
func _chip_fit(fit: Array) -> Rect2:
	var d := circle.size.x
	var side := float(fit[1]) * d
	return Rect2(circle.position.x + (d - side) * 0.5, circle.position.y + float(fit[2]) * d, side, side)


## The face crop in a square slot (`dst`: the crop covering it): moved down until FIT's face top row is FACE_CLEAR under
## the frame — the head keeps its size, the chest gives those px at the bottom (the tall headgear of Vance, Bram E2 and
## Vega E2 touched the 2 px frame of the picker 72 and the calendar 64).
func _square_fit(fit: Array, dst: Rect2, ts: Vector2) -> Rect2:
	dst.position.y = maxf(0.0, frame_w() * (1.0 + FACE_CLEAR) - float(fit[0]) * dst.size.y / ts.y)
	return dst


## The bust zoomed for a picture whose bottom `hidden_bottom` px are covered (the «Командиры» fan): skyline to chin
## (FIT [3], [4], rows of the file) fills the rows above that, the headgear FACE_CLEAR under the frame — never under
## the cover scale (a head that does not fit then shows as it did: its chin may reach a px into the covered rows) and
## always to the picture's bottom (no edge of the render shows).
func _bust_fit(fit: Array, ts: Vector2) -> Rect2:
	var w := size.x
	var h := size.y
	var sky := float(fit[3])
	var top := frame_w() * (1.0 + FACE_CLEAR)
	var k := maxf(maxf(w / ts.x, h / ts.y), (h - hidden_bottom - top) / maxf(1.0, float(fit[4]) - sky))
	var off := clampf(sky - top / k, 0.0, ts.y - h / k)  # the file's row at the picture's top
	return Rect2((w - ts.x * k) * 0.5, -off * k, ts.x * k, ts.y * k)


func _draw() -> void:
	var w := size.x
	var h := size.y
	var u := minf(w, h)
	if w < 2.0 or h < 2.0:
		return
	var rc: Color = RARITY.get(rarity, RARITY["common"]) if plate.a == 0.0 else plate
	# a small slot shows the face crop of the file the bust would draw (if there is one), else the bust — but a
	# picture whose bottom is covered shows the bust, zoomed (_bust_fit)
	var tex: Texture2D = _render_face(cmd, mood) if maxf(w, h) <= FACE_MAX and hidden_bottom <= 0.0 else null
	var face := tex != null
	if not face:
		tex = _render(cmd, mood)
	var box := _box()
	# where the render goes (the box's coordinates) and its eye line (halo_y): cover the box, keep the head, crop the torso —
	# or the small slots' fits (FIT)
	var dst := Rect2()
	var halo_y := h * (FACE_EYE if face else BUST_EYE)  # the eye line: the halo's centre
	if tex != null:
		var ts := tex.get_size()
		var sc := maxf(w / ts.x, h / ts.y)
		dst = Rect2((w - ts.x * sc) / 2.0, 0.0, ts.x * sc, ts.y * sc)
		var fit: Array = FIT.get(_chain(cmd, mood), [])
		if not fit.is_empty():
			if face and circle.has_area():
				dst = _chip_fit(fit)
				halo_y = dst.position.y + dst.size.y * FACE_EYE
			elif face:
				dst = _square_fit(fit, dst, ts)
				halo_y = dst.position.y + dst.size.y * FACE_EYE
			elif hidden_bottom > 0.0 and int(fit[3]) >= 0:
				dst = _bust_fit(fit, ts)
				halo_y = dst.position.y + dst.size.y * BUST_EYE_FILE
	# plate B (§7.4): a vertical gradient of the rarity colour, lightened(0.18) at the top to the colour itself at the
	# bottom — the dark costumes of §7.6 stand off it (a locked one: the colour washed into a muted grey)
	var top := rc.lightened(0.18) if not locked else rc.lerp(Kit.CREAM_DEEP, 0.72)
	var bot := rc if not locked else top.darkened(0.32)
	var cols := PackedColorArray()
	for v in box:
		cols.append(top.lerp(bot, clampf(v.y / h, 0.0, 1.0)))
	draw_polygon(box, cols)
	# a soft halo behind the head: concentric white discs, no dark outline (the «fishbowl» ring is gone)
	_halo(Vector2(w * 0.5, halo_y), u)
	_drawn = tex
	if tex != null:
		# the bpy render at `dst`, drawn through the rounded box (UVs), so its corners never poke out of the frame; a
		# render that does not cover the whole box (a fitted face crop: the plate shows over its top or round it in the
		# chip's circle) through the part of the box it covers. A locked commander is its flat silhouette at α 0.3
		# (SILHOUETTE)
		var poly := box
		if not dst.encloses(Rect2(Vector2.ZERO, size)):
			var cut := Geometry2D.intersect_polygons(box, PackedVector2Array([dst.position, Vector2(dst.end.x,
				dst.position.y), dst.end, Vector2(dst.position.x, dst.end.y)]))
			poly = cut[0] if not cut.is_empty() else PackedVector2Array()
		if poly.size() >= 3:
			var uvs := PackedVector2Array()
			for v in poly:
				uvs.append((v - dst.position) / dst.size)
			draw_colored_polygon(poly, Kit.alpha(Kit.INK, 0.3) if locked else Color.WHITE, uvs, tex)
		_frame(rc)
		return
	var look: Array = LOOK.get(cmd, LOOK["cmd_bram"])
	var shade := Kit.alpha(Kit.INK, 0.3)
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
		_fill(_ellipse(Vector2(w * 0.5, sy - u * 0.04), u * 0.24, u * 0.06), Color("6b5040"))  # fur collar
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
		_fill(_ellipse(hc + Vector2(hw * 1.0, hh * 0.25), u * 0.012, u * 0.012, true), Color("e8b23a"))  # earring
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
	var eye_col := Color("5aa8ff") if cmd == "cmd_rai" and not locked else Color(0.12, 0.1, 0.1)
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
			_fill(_ellipse(hc + Vector2(0, -hh * 0.3), hw * 1.12, hh * 0.86, PI, TAU), Color("7a5133") if not locked else shade)
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
		_fill(_ellipse(Vector2(w * 0.5, sy - u * 0.01), u * 0.17, u * 0.05), Color("f6f6f2"))  # white scarf
	_frame(rc)


## The rarity-coloured frame along the rounded box (a locked one in the muted plate's darker tone).
func _frame(rc: Color) -> void:
	if not frame:
		return
	var sb := StyleBoxFlat.new()
	sb.draw_center = false
	sb.anti_aliasing = true
	sb.corner_detail = 8
	sb.set_corner_radius_all(int(frame_r()))
	sb.set_border_width_all(int(roundf(frame_w())))
	sb.border_color = rc if not locked else rc.lerp(Kit.CREAM_DEEP, 0.72).darkened(0.45)
	draw_style_box(sb, Rect2(Vector2.ZERO, size))


static func _render(id: String, m := "") -> Texture2D:
	_sync_era()
	var key := "%s_e%d_%s" % [id, era, m]
	if not _renders.has(key):
		var file := _chain(id, m)
		var path := "res://assets/ui/portraits/%s.png" % file
		_renders[key] = null if file == "" else (_load_mipmapped(path) if id.begins_with("cmd_") else load(path))
	return _renders[key]


## The face crop (`face_<name>.png`, §7.12) of the very file _render(id, m) draws — the same era and mood, found by
## the same chain — or null when that file has none (the bust is drawn then). Cached with the era's renders.
static func _render_face(id: String, m := "") -> Texture2D:
	_sync_era()
	var key := "face|%s_e%d_%s" % [id, era, m]
	if not _renders.has(key):
		var file := _chain(id, m)
		var path := "res://assets/ui/portraits/face_%s.png" % file
		_renders[key] = _load_mipmapped(path) if file != "" and ResourceLoader.exists(path) else null
	return _renders[key]


## A new era: set_portrait_era redraws the busts on show with its renders (the KitStill bakes are keyed by era), and
## the old era's are never read again — let their textures (a 512×588 bust ≈ 1.5 MB with mipmaps, a 256 face crop
## ≈ 0.35 MB) go; a bust not redrawn yet keeps the one it draws (_drawn) until it is.
static func _sync_era() -> void:
	if _cache_era != era:
		_renders.clear()
		_mipped.clear()
		_cache_era = era


## The file a portrait of `id` in mood `m` is drawn from in the current era (no extension), "" when none exists: the
## era's render in this mood, the era's calm one, then the first era's (mood, calm).
static func _chain(id: String, m: String) -> String:
	var base := id if era == 1 else "%s_e%d" % [id, era]
	for file in [base + ("_" + m if m != "" else ""), base, id + ("_" + m if m != "" else ""), id]:
		if ResourceLoader.exists("res://assets/ui/portraits/%s.png" % file):
			return file
	return ""


## A commander's render with mipmaps, one texture per file however many keys fall back to it (a mood without its own
## render shows the calm one).
static func _load_mipmapped(path: String) -> Texture2D:
	if not _mipped.has(path):
		_mipped[path] = _with_mipmaps(load(path), path)
	return _mipped[path]


## The commanders' 512×588 renders are shown at 38–312 px (§7.12) and need mipmaps. Their .import files ask for them
## (mipmaps/generate=true; tracked in git through assets/ui/portraits/.gitignore). A texture imported without them (an
## .import lost or reset) gets them here, once per file (_load_mipmapped). With a RenderingDevice (Mobile, Forward+)
## the texture's own mip count is read without a readback, so an imported set with mipmaps costs nothing. The new
## texture carries the file's `path` as its resource_path (set_path_cache: outside the ResourceCache), so what keys a
## texture by resource_path (game_ui._mini_face, Kit's caches) stays unique per file, and the import keeps its own
## path and cache entry — a holder that load()ed the file (a shop reveal tile) is left alone; load() still gives the
## import, so the direct users should take _render's texture (P4 follow-up a).
static func _with_mipmaps(tex: Texture2D, path := "") -> Texture2D:
	if tex == null:
		return tex
	var rd := RenderingServer.get_rendering_device()
	if rd != null:
		var rid := RenderingServer.texture_get_rd_texture(tex.get_rid())
		if rid.is_valid() and rd.texture_get_format(rid).mipmaps > 1:
			return tex
	var img := tex.get_image()
	if img == null or img.is_empty() or img.has_mipmaps() or img.is_compressed():
		return tex
	img.generate_mipmaps()
	var mt := ImageTexture.create_from_image(img)
	if path != "":
		mt.set_path_cache(path)
	return mt
