shader_type spatial;
// «Raivon Soft» ground (docs/art_direction.md §6.7): one continuous sunny lawn. The vertex colour is the biome
// colour, already blended across hex corners and edges by map_view._build_terrain, so there is no colour step on any
// hex edge. On top of it, all in world space so the tiles join seamlessly:
//   - big patches ±7 %, sunlit ones warmer and hollows cooler;
//   - a little dirt, and a fine speckle only up close (fine_k);
//   - a soft rounded seam per hex (SOFT_R): a shallow groove at the edge plus a slight cushion, scaled by seam_k
//     (1.0 close … 0.45 far). Never emissive, never a line.
// The tile sides (soil walls down to the water and the world's edge) only take their vertex colour and a faint
// speckle: no rock strata.
// Plain Lambert, not diffuse_lambert_wrap: on flat ground (N·L ≈ 0.82 everywhere) the wrap shapes nothing and only
// cuts the sun's share against the ambient, 0.77× in linear terms at ROUGHNESS 0.95, which flattens the received
// shadows below the §6.4 ≈ 2.3 : 1 (P3 review: deep core 2.13 → 1.74 close). The lawn's brightness is set by the
// vertex colours instead (map_view.GROUND_K).
render_mode cull_back;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform sampler2D noise_big : filter_linear_mipmap, repeat_enable;
uniform sampler2D noise_fine : filter_linear_mipmap, repeat_enable;
uniform vec3 dirt_color : source_color = vec3(0.725, 0.541, 0.333);  // #B98A55
uniform float dirt_amount = 0.08;
uniform float fine_k = 1.0;  // the fine speckle: 1 close … 0 from afar (map_view.set_zoom)
uniform float seam_k = 1.0;  // the hex seams: 1 close … 0.45 from afar (map_view.set_zoom)

varying vec3 wpos;
varying vec3 wnormal;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnormal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 base = pow(COLOR.rgb, vec3(2.2));  // vertex colours are authored in sRGB
	float big = texture(noise_big, wpos.xz * 0.045).r;
	float mid = texture(noise_big, wpos.xz * 0.21 + vec2(0.37, 0.11)).r;
	float fine = texture(noise_fine, wpos.xz * 1.6).r;
	float top = smoothstep(0.3, 0.9, wnormal.y);
	// big patches ±7 %, with a hue shift: the light ones warmer, the hollows cooler
	vec3 c = base * mix(0.93, 1.07, big);
	c = mix(c, c * vec3(1.06, 1.05, 0.90), smoothstep(0.55, 0.8, mid) * 0.5);
	c = mix(c, c * vec3(0.92, 0.98, 1.06), (1.0 - smoothstep(0.2, 0.45, mid)) * 0.4);
	// a few soft dirt spots on the flat ground
	float dirt = smoothstep(0.66, 0.82, mid * 0.6 + big * 0.5) * dirt_amount * top;
	c = mix(c, dirt_color, dirt);
	// fine speckle, only up close
	c *= mix(1.0, mix(0.96, 1.04, fine), fine_k);
	// soft rounded hex seams on the land tops (the water bed at y −0.2 is left out): a groove at the edge plus a
	// slight cushion towards it. The groove is 0.10 wide and 11 % deep, so a neutral hex still reads as a soft cell
	// up close (at 0.07 / 9 % it was lost among the patches); at strat seam_k 0.45 keeps it faint.
	vec2 l = hex_local(wpos.xz);
	float dh = sd_round_hex(l, HEX_IN, SOFT_R);
	float land = top * step(-0.05, wpos.y);
	c *= 1.0 - land * seam_k * (0.11 * smoothstep(-0.10, -0.01, dh) + 0.035 * smoothstep(-0.45, -0.10, dh));
	// the tile sides: their vertex colour (soil -> deep slate) with a faint speckle
	c = mix(base * (0.95 + 0.1 * fine), c, top);
	ALBEDO = c;
	ROUGHNESS = 0.95;
	SPECULAR = 0.15;
}
