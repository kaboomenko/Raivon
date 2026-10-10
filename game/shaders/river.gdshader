shader_type spatial;
// Rivers between hexes («Raivon Soft», docs/art_direction.md §6.7): flowing ripples with soft glints over a clear
// blue bed, turquoise shallows and a solid foam bank along both banks (COLOR.r = 0 mid-stream, 1 at a bank).
// Unshaded: the ribbon sits flat on the ground and its look must not depend on the sun.
render_mode unshaded, cull_disabled;

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 bed : source_color = vec3(0.212, 0.639, 0.847);  // #36A3D8, the water's middle blue
uniform vec3 shallow : source_color = vec3(0.373, 0.816, 0.855);  // #5FD0DA
uniform vec3 foam_color : source_color = vec3(0.949, 0.980, 1.0);  // #F2FAFF, the water's foam
// The colours above are what the screen should show, as in water.gdshader: unshaded, an albedo still comes out ≈ 2×
// brighter in linear terms through the exposure and the tonemap (P5: the bed read #4BD7F9 for #36A3D8, brighter
// than the lake beside it), so the albedo takes the water's factor.
uniform float light_k = 0.5;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float bank = COLOR.r;
	vec2 uv1 = wpos.xz * 1.6 + vec2(TIME * 0.12, TIME * 0.07);
	vec2 uv2 = wpos.xz * 2.7 - vec2(TIME * 0.09, -TIME * 0.11);
	float n = texture(noise_tex, uv1).r * 0.6 + texture(noise_tex, uv2).r * 0.4;
	vec3 c = mix(bed, shallow, clamp(bank * 0.7 + (n - 0.5) * 0.35, 0.0, 1.0));
	c += vec3(0.2, 0.26, 0.26) * smoothstep(0.66, 0.78, n) * (1.0 - bank);  // glints mid-stream
	float foam = smoothstep(0.82, 0.95, bank + (n - 0.5) * 0.15) * 0.65;  // a solid bank, gently wavy
	c = mix(c, foam_color, foam);
	ALBEDO = c * light_k;
}
