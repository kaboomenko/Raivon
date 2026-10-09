shader_type spatial;
// «Raivon Soft» scorched ground (docs/art_direction.md §6.6): a soft multiply under an AI state's fill, white at
// the border and easing to `tint` inside along the same distance field as territory_fill (no hard hex edge).
// The player's land has none. Mesh and attributes as territory_fill.gdshader (one fan per hex, 0.024 high).
// mul_k is mandatory: the Mobile renderer keeps colours at half value, an unscaled multiply darkens the land 2x.
render_mode blend_mul, unshaded, cull_disabled, depth_draw_never, shadows_disabled;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform vec3 tint : source_color = vec3(0.96, 0.93, 0.90);  // war enemy / other AI / DL8 (map_view._rebuild_overlay)
uniform float mul_k = 1.0;  // map_view.MUL_K: 2 on the Mobile renderer

varying vec2 v_p;
varying flat float v_mask;
varying flat float v_born;

void vertex() {
	v_p = UV;
	v_mask = UV2.x;
	v_born = UV2.y;
}

void fragment() {
	float d = mask_dist(v_p, int(v_mask + 0.5), 0.22);
	ALBEDO = mix(vec3(1.0), tint, smoothstep(0.07, 0.57, d)) * mul_k;
}
