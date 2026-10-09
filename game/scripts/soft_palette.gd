extends RefCounted
## «Raivon Soft» shared shape and colour constants (docs/art_direction.md §6.1, §6.3).
## One corner radius for every hex outline of the world, and the states' ribbon colours: body, light band ("hi"),
## dark rim and the territory fill. The player and the enemy at war are fixed pairs checked for greyscale and
## deuteranopia (ΔL* of the bodies 17); every other state goes through soft_team().

## The corner radius of every hex outline (ribbons, coast, selection, hatch, seams), in hex radii (R = 1).
const SOFT_R := 0.3

const PLAYER := {"body": Color("#4FA8FF"), "hi": Color("#B8E0FF"), "rim": Color("#1D4DB3"), "fill": Color("#3D8BFF")}
## The enemy at war and the Barons: coral fill rather than maroon (red over green turns brown).
const ENEMY := {"body": Color("#DD3A30"), "hi": Color("#FFB3A3"), "rim": Color("#8E1D17"), "fill": Color("#FF6A5A")}


## A state's colours from its flag colour: a saturated, bright body; a darker, slightly redder rim; a light band
## 60 % toward white; a fill 15 % toward white.
static func soft_team(c: Color) -> Dictionary:
	var body := Color.from_hsv(c.h, clampf(c.s, 0.62, 0.8), clampf(c.v, 0.82, 1.0))
	var rim := Color.from_hsv(fposmod(c.h - 0.02, 1.0), minf(body.s * 1.1, 1.0), body.v * 0.55)
	return {"body": body, "hi": body.lerp(Color.WHITE, 0.6), "rim": rim, "fill": body.lerp(Color.WHITE, 0.15)}
