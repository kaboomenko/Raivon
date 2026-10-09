shader_type spatial;
// Drifting cloud shadows (art direction: a sunny map that breathes): a plane just above the territory fills,
// multiplied onto everything under it — ground, fills, water — while trees, buildings, armies and the
// territory borders (drawn above it, docs/art_direction.md §6.6 layer order) stay lit.
render_mode blend_mul, unshaded, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform sampler2D cloud_noise : filter_linear_mipmap, repeat_enable;
uniform float strength = 0.3;  // a light, soft passing shade (docs/art_direction.md §6.4)
uniform vec3 shade : source_color = vec3(0.75, 0.78, 0.92);  // cool blue-lilac, like every shadow in §6.3
uniform vec2 wind = vec2(0.11, 0.05);
uniform float mul_k = 1.0;  // 2 on the Mobile renderer (map_view.MUL_K)

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec2 uv = wpos.xz * 0.055 - wind * TIME * 0.04;
	float cl = texture(cloud_noise, uv).r * 0.75 + texture(cloud_noise, uv * 2.3 + vec2(0.5, 0.2)).r * 0.25;
	ALBEDO = mix(vec3(1.0), shade, smoothstep(0.5, 0.75, cl) * strength) * mul_k;
}
