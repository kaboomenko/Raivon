shader_type spatial;
// A banner's cloth fluttering in the wind: pinned at the pole edge, rippling more toward the free edge; both faces
// of the cloth (side = +1 front, −1 back, a quad turned by 180°) move together in world space.
render_mode cull_back;

uniform sampler2D tex : source_color, filter_linear_mipmap;
instance uniform float side = 1.0;

void vertex() {
	float free_ = side > 0.0 ? UV.x : 1.0 - UV.x;  // 0 at the pole, 1 at the fly end
	float ph = MODEL_MATRIX[3].x * 1.7 + MODEL_MATRIX[3].z * 1.1;  // neighbouring banners out of step
	float w = sin(TIME * 3.4 - free_ * 5.5 + ph) * 0.04 + sin(TIME * 5.3 - free_ * 9.0 + ph * 1.3) * 0.01;
	VERTEX.z += side * w * free_;
	VERTEX.y += sin(TIME * 2.2 - free_ * 4.0 + ph) * 0.006 * free_;
}

void fragment() {
	vec4 c = texture(tex, UV);
	ALBEDO = c.rgb;
	ALPHA = c.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	ROUGHNESS = 0.75;
}
