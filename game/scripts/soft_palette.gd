extends RefCounted
## «Raivon Soft» shared shape and colour constants (docs/art_direction.md §6.1, §6.3).
## One corner radius for every hex outline of the world, and the states' ribbon colours: body, light band ("hi"),
## dark rim and the territory fill. The player and the enemy at war are fixed pairs checked for greyscale and
## deuteranopia (ΔL* of the bodies 17); every other state goes through soft_team().
## These are the colours as they should read on screen (the HUD uses them as they are). An unshaded map material
## takes them through scene(), which undoes the grade the 3D view puts on them.

## The corner radius of every hex outline (ribbons, coast, selection, hatch, seams), in hex radii (R = 1).
const SOFT_R := 0.3

const PLAYER := {"body": Color("#4FA8FF"), "hi": Color("#B8E0FF"), "rim": Color("#1D4DB3"), "fill": Color("#3D8BFF")}
## The enemy at war and the Barons: coral fill rather than maroon (red over green turns brown).
const ENEMY := {"body": Color("#DD3A30"), "hi": Color("#FFB3A3"), "rim": Color("#8E1D17"), "fill": Color("#FF6A5A")}

## The 3D view's grade (main.gd _environment, §6.4): Filmic at EXPOSURE, then brightness, contrast, saturation.
## Exposure 0.75, below the 0.9 of G1 (soft_style_plan F1): with the sunny ground of P3 and the models of B8 every
## frame measured lighter than §6.12 (V p50 0.75–0.84, L* p50 66–73, lawn L* 71–76, white-hot up to 1.9 %). Measured
## at 0.8 / 0.72: the lawn L* 67–70 / 65–68 (§6.3 ≈ #7FB347, L* 67), L* p50 63–66 / 61–63, white-hot halved; 0.75
## sits between them, nearest the approved style frame (lawn L* 63, L* p50 59) without dulling the sunny look.
const EXPOSURE := 0.75
const GRADE_BCS := Vector3(1.03, 1.04, 1.12)  # brightness, contrast, saturation


## A state's colours from its flag colour: a saturated, bright body; a darker, slightly redder rim; a light band
## 60 % toward white; a fill 15 % toward white.
static func soft_team(c: Color) -> Dictionary:
	var body := Color.from_hsv(c.h, clampf(c.s, 0.62, 0.8), clampf(c.v, 0.82, 1.0))
	var rim := Color.from_hsv(fposmod(c.h - 0.02, 1.0), minf(body.s * 1.1, 1.0), body.v * 0.55)
	return {"body": body, "hi": body.lerp(Color.WHITE, 0.6), "rim": rim, "fill": body.lerp(Color.WHITE, 0.15)}


## The colour to give an unshaded map material (ribbons, fills, hatch, strength pills, the strike arrow, the
## selection) so that it reads as `c` on screen. Unshaded colours still pass through the 3D view's Filmic tonemap and
## grade, which lift and shift them: at exposure 0.9 #4FA8FF came out as #56CDFF (lighter and cyan, the hue of the
## water), #DD3A30 as #FF3C2D and the light band #B8E0FF as near-white #D6F6FF (measured on the Mobile renderer to
## within 2–3 levels). This is the exact inverse of that chain: Godot's tonemap_filmic (exposure bias 2, white 1)
## and apply_bcs. Light fog (0.001) and the vignette are left out (≈ 1–2 %). Alpha is kept.
static func scene(c: Color) -> Color:
	var g := (c.r + c.g + c.b) / 3.0
	var v := Vector3(c.r, c.g, c.b)
	v = Vector3(g, g, g) + (v - Vector3(g, g, g)) / GRADE_BCS.z  # undo the saturation (it keeps the channel mean)
	v = Vector3(0.5, 0.5, 0.5) + (v - Vector3(0.5, 0.5, 0.5)) / GRADE_BCS.y  # the contrast
	v /= GRADE_BCS.x  # the brightness
	var lin := Color(clampf(v.x, 0.0, 1.0), clampf(v.y, 0.0, 1.0), clampf(v.z, 0.0, 1.0)).srgb_to_linear()
	var out := Color(_unfilmic(lin.r), _unfilmic(lin.g), _unfilmic(lin.b)) * (1.0 / EXPOSURE)
	out = Color(clampf(out.r, 0.0, 1.0), clampf(out.g, 0.0, 1.0), clampf(out.b, 0.0, 1.0)).linear_to_srgb()
	out.a = c.a
	return out


## The same look with every colour through scene().
static func scene_look(look: Dictionary) -> Dictionary:
	var out := {}
	for k in look:
		out[k] = scene(look[k])
	return out


# Godot's Filmic curve (tonemap.glsl, tonemap_filmic) with its exposure bias of 2 baked into A and B.
const _FA := 0.88
const _FB := 0.6
const _FC := 0.1
const _FD := 0.2
const _FE := 0.01
const _FF := 0.3


static func _filmic_raw(x: float) -> float:
	return (x * (_FA * x + _FC * _FB) + _FD * _FE) / (x * (_FA * x + _FB) + _FD * _FF) - _FE / _FF


## The linear input that Filmic (white 1) maps to y: the positive root of A(u−1)x² + B(u−C)x + D(uF−E) = 0, with
## u = y · filmic(1) + E/F (for 0 ≤ y < 1 the leading coefficient is negative and the roots have opposite signs).
static func _unfilmic(y: float) -> float:
	y = clampf(y, 0.0, 0.999)
	var u := y * _filmic_raw(1.0) + _FE / _FF
	var a := _FA * (u - 1.0)
	var b := _FB * (u - _FC)
	var c := _FD * (u * _FF - _FE)
	var disc := sqrt(maxf(b * b - 4.0 * a * c, 0.0))
	return maxf((-b - disc) / (2.0 * a), 0.0)
