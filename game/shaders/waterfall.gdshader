shader_type spatial;
render_mode unshaded, cull_disabled, blend_mix, depth_draw_opaque;
// Waterfalls over the map edge (map_view._build_waterfalls): UV.y runs down the fall; streaks scroll downward,
// foam brightens toward the bottom, the sides fade out.
uniform sampler2D noise_tex : filter_linear_mipmap, repeat_enable;

void fragment() {
	float n = texture(noise_tex, vec2(UV.x * 3.0, UV.y * 0.8 - TIME * 0.9)).r;
	float n2 = texture(noise_tex, vec2(UV.x * 7.0 + 0.3, UV.y * 1.6 - TIME * 1.4)).r;
	vec3 deep = vec3(0.07, 0.36, 0.46);
	vec3 foam = vec3(0.86, 0.94, 0.97);
	float streak = smoothstep(0.45, 0.75, n * 0.6 + n2 * 0.4);
	vec3 c = mix(deep, foam, clamp(streak * 0.8 + UV.y * 0.45, 0.0, 1.0));
	float side = smoothstep(0.0, 0.12, UV.x) * smoothstep(1.0, 0.88, UV.x);
	ALBEDO = c;
	ALPHA = side * (0.82 + 0.18 * streak);
}
