shader_type spatial;
// «Raivon Soft» cartoon water (docs/art_direction.md §6.7, soft_style_plan P5): turquoise shallows at the shore, a
// clear blue middle and a deeper blue further out, soft ripples with glints, a solid white foam lip along the shore
// and one slow foam ring that leaves the shore every ≈ 8 s. All of it is drawn from d, the distance to the land,
// rounded with SOFT_R like the coastline (map_view._coastline), so the foam follows the curves of the coast.
// Per water hex (map_view._build_water): UV = the vertex minus the hex centre (x, z), UV2.x = the land mask (bit k:
// neighbour k, in DIRS order, is land). The field only knows the six neighbours: land further away is >= 1.0 from
// any point of the hex, so the deep ramp ends at 1.0 (not 1.2) and the colours agree across every hex edge.
// The foam lip starts under the beach rim (0.08 wide) and hides small mismatches between the field and the rim.
// UV2.y shifts the shore out where the coast is a beach sloping into the water (the bay: map_view._bay_shore): the
// shallows, the lip and the ring start at the waterline there; the deep ramp keeps the raw distance, so the bay's
// far edges still match the open sea. lip_w widens the lip from the middle zoom out (map_view._water_zoom).
render_mode cull_back;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 shallow : source_color = vec3(0.373, 0.816, 0.855);  // #5FD0DA
uniform vec3 mid : source_color = vec3(0.212, 0.639, 0.847);  // #36A3D8
uniform vec3 deep : source_color = vec3(0.165, 0.482, 0.749);  // #2A7BBF
uniform vec3 foam : source_color = vec3(0.949, 0.980, 1.0);  // #F2FAFF
uniform bool open_sea = false;  // the plane round the world: no land mask, all deep water
// The colours above are what the screen should show (§6.3). Lit by the sun (1.1) and the sky ambient (0.8), an
// albedo comes out ≈ 2× brighter in linear terms (P5: the open sea read #31A5F7, L* 65, for #2A7BBF, the shallows
// clipped at #6DE3FF), so the albedo takes this factor, as the ground's vertex colours take map_view.GROUND_K.
uniform float light_k = 0.5;
uniform float lip_w = 0.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += sin(TIME * 1.3 + wpos.x * 1.7 + wpos.z * 1.1) * 0.012;
}

void fragment() {
	vec2 uv1 = wpos.xz * 0.35 + vec2(TIME * 0.025, TIME * 0.018);
	vec2 uv2 = wpos.xz * 0.8 - vec2(TIME * 0.03, -TIME * 0.022);
	float n = texture(noise_tex, uv1).r * 0.6 + texture(noise_tex, uv2).r * 0.4;
	// the distance to the land: the rounded neighbour hexes, their meeting corners filled by smin
	float d = 9.0;
	if (!open_sea) {
		int mask = int(UV2.x + 0.5);
		for (int k = 0; k < 6; k++) {
			if (((mask >> k) & 1) == 1) {
				d = smin(d, sd_round_hex(UV - nb_off(k), HEX_IN, SOFT_R), 0.28);
			}
		}
	}
	float ds = d - UV2.y;  // from the shore as an in-map coast has it
	vec3 c = mix(shallow, mid, smoothstep(0.08, 0.45, ds));
	c = mix(c, deep, smoothstep(0.45, 1.0, d));
	// soft ripples and glints
	c *= 0.97 + 0.06 * n;
	c += vec3(0.25) * smoothstep(0.74, 0.78, n);
	// the foam lip at the shore, and the slow ring
	float lip = 1.0 - smoothstep(0.10 + lip_w, 0.15 + 1.4 * lip_w, ds);
	float ph = fract(TIME * 0.12);
	float rr = 0.16 + lip_w + ph * 0.5;
	float ring = (1.0 - smoothstep(0.02, 0.045, abs(ds - rr))) * 0.7 * (1.0 - ph);
	c = mix(c, foam, max(lip, ring));
	ALBEDO = c * light_k;
	ROUGHNESS = 0.35;
	SPECULAR = 0.3;
}
