shader_type spatial;
// Squad figures come baked into one mesh (tools/blender/troops_assets.py: 4×3 block, 0.13 spacing, odd rows
// shifted 0.06). Each vertex finds its figure from that grid, so every figure moves as one piece with its
// own phase: a marching bob, and a forward lean / weapon thrust in the upper body while fighting.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform float roughness_v = 0.8;
uniform bool solid = false;  // one unit (rider, vehicle): a single phase, no per-figure split
instance uniform float march = 0.0;
instance uniform float fight = 0.0;

float figure_phase(vec3 v) {
	if (solid) {
		return 0.0;
	}
	float row = floor((-v.z + 0.185) / 0.13);
	float off = mod(row, 2.0) > 0.5 ? 0.06 : 0.0;
	float col = floor((v.x + 0.265 - off) / 0.13);
	return fract(sin(dot(vec2(col, row), vec2(12.9898, 78.233))) * 43758.5453) * 6.2831;
}

void vertex() {
	float ph = figure_phase(VERTEX);
	float h = clamp(VERTEX.y / 0.4, 0.0, 1.0);
	float t = TIME;
	// marching: a little hop per step
	VERTEX.y += abs(sin(t * 9.0 + ph)) * 0.022 * march;
	// fighting: lean in and thrust, stronger toward the head and the weapon tip
	float thrust = max(0.0, sin(t * 13.0 + ph * 1.7));
	VERTEX.z += (thrust * 0.05 * fight + sin(t * 9.0 + ph) * 0.012 * march) * h * h;
	VERTEX.x += sin(t * 7.0 + ph) * 0.008 * fight * h;
}

void fragment() {
	vec4 c = texture(albedo_tex, UV);
	ALBEDO = c.rgb;
	ROUGHNESS = roughness_v;
}
