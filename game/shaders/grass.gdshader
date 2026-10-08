shader_type spatial;
render_mode cull_disabled, diffuse_lambert, specular_disabled;

// Grass tufts (map_view._build_grass): vertex colour × instance tint, the blades sway in a slow wind gust
// whose phase runs across the map, so the meadow ripples instead of nodding in unison.
uniform float sway = 0.018;
uniform float speed = 1.3;

void vertex() {
	vec3 world = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float k = VERTEX.y / 0.1;
	float w = sin(TIME * speed + world.x * 0.9 + world.z * 0.6) * 0.7 + sin(TIME * speed * 2.3 + world.x * 2.1) * 0.3;
	VERTEX.x += w * sway * k * k / max(length(MODEL_MATRIX[0].xyz), 0.01);
	VERTEX.z += w * sway * 0.4 * k * k / max(length(MODEL_MATRIX[2].xyz), 0.01);
}

void fragment() {
	ALBEDO = COLOR.rgb * 0.52;
	NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);  // both faces lit like the ground
	ROUGHNESS = 1.0;
}
