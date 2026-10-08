shader_type spatial;
// Water hexes: deep-to-shallow colour, scrolling ripples with a soft glint, and foam along the edges that
// meet land (COLOR.r = 1 at a shore corner, 0 in open water), breathing slowly.
render_mode cull_back;

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 deep : source_color = vec3(0.13, 0.33, 0.5);  // measured: the reference seas are (27, 80, 126) on screen
uniform vec3 shallow : source_color = vec3(0.17, 0.48, 0.56);
uniform float shore_k = 1.0;  // 0 for the open sea around the world (a plane without vertex colours)

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	VERTEX.y += sin(TIME * 1.3 + wpos.x * 1.7 + wpos.z * 1.1) * 0.012;
}

void fragment() {
	vec2 uv1 = wpos.xz * 0.35 + vec2(TIME * 0.025, TIME * 0.018);
	vec2 uv2 = wpos.xz * 0.8 - vec2(TIME * 0.03, -TIME * 0.022);
	float n = texture(noise_tex, uv1).r * 0.6 + texture(noise_tex, uv2).r * 0.4;
	float shore = COLOR.r * shore_k;
	vec3 c = mix(deep, shallow, clamp(pow(shore, 2.0) * 0.8 + n * 0.25, 0.0, 1.0));
	// glints on the ripples
	float glint = smoothstep(0.68, 0.78, n);
	c += vec3(0.14, 0.2, 0.22) * glint * mix(0.15, 1.0, shore_k);  // the open sea glints softly: far away, it read as snow
	// foam band on the shore, wobbling with the noise and the time
	float band = shore - 0.93 + (n - 0.5) * 0.16 + sin(TIME * 1.6 + wpos.x * 3.0) * 0.025;
	float foam = smoothstep(0.0, 0.06, band);
	c = mix(c, vec3(0.86, 0.92, 0.95), foam * 0.6);  // a thin lace of surf, not a white rim
	ALBEDO = c;
	ROUGHNESS = mix(0.08, 0.6, foam);
	SPECULAR = 0.6;
}
