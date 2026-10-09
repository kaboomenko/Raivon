shader_type spatial;
// «Raivon Soft» occupation hatch (canon §3.1, docs/art_direction.md §6.6): soft anti-aliased diagonal stripes in
// the occupier's colour over a hex held by another state's troops, under a rounded-hex mask (SOFT_R) so the patch
// has no sharp corners. Built by map_view._rebuild_overlay: one fan of radius 1.0 per hex at y 0.04, UV = the
// vertex offset from the hex centre in (x, z).
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform vec4 col : source_color;  // team_look(controller).body

varying vec3 wp;

void vertex() {
	wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float s = (wp.x + wp.z) * 1.6;  // period 0.625: 1.6x wider than the old hatch
	float f = abs(fract(s) - 0.5) * 2.0;
	float aa = fwidth(s) * 2.0;
	float stripe = smoothstep(0.45 - aa, 0.45 + aa, f);
	float mask = smoothstep(0.0, 0.12, -sd_round_hex(UV, HEX_IN * 0.94, SOFT_R));
	ALBEDO = col.rgb;
	ALPHA = 0.45 * stripe * mask;
}
