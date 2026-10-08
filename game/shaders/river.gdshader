shader_type spatial;
// Rivers between hexes: flowing ripples with soft glints over a teal bed, lighter shallows and a lace of foam
// along the banks (COLOR.r = 0 mid-stream, 1 at a bank). Unshaded: the ribbon sits flat on the ground and its
// look must not depend on the sun.
render_mode unshaded, cull_disabled;

uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;
uniform vec3 bed : source_color = vec3(0.1, 0.36, 0.48);
uniform vec3 shallow : source_color = vec3(0.18, 0.48, 0.56);

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
	float foam = smoothstep(0.86, 0.99, bank + (n - 0.5) * 0.3 + sin(TIME * 2.0 + wpos.x * 5.0) * 0.03);
	c = mix(c, vec3(0.82, 0.9, 0.92), foam * 0.4);  // a broken lace, not an outline
	ALBEDO = c;
}
