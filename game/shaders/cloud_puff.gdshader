// Puffy two-tone clouds (docs/art_direction.md §6.7, soft_style_plan P7; map_view._cloud_material): an unshaded
// billboard of one cell of the puff atlas (map_view._cloud_puff_tex: `cells` lobe layouts side by side, white tops,
// lilac-blue undersides). The horizon's MultiMesh picks the cell and a mirror per instance (INSTANCE_CUSTOM.x = cell,
// .y > 0.5 = mirrored), so its one draw call shows 2 × cells different silhouettes; a veil cloud (its own material)
// sets `cell` >= 0 and `mirror` instead. The billboard (keeping the instance's scale) and the distance fade are
// StandardMaterial3D's BILLBOARD_ENABLED + billboard_keep_scale and DISTANCE_FADE_PIXEL_ALPHA.
shader_type spatial;
render_mode unshaded, blend_mix;

uniform sampler2D puff : source_color, filter_linear_mipmap, repeat_disable;
uniform float cells = 3.0;
uniform float cell = -1.0;  // >= 0: this atlas cell (a veil cloud); < 0: INSTANCE_CUSTOM.x (the horizon's MultiMesh)
uniform bool mirror = false;  // with cell >= 0
uniform float alpha = 0.95;  // map_view.part_clouds tweens it to 0
uniform float fade_min = 0.0;  // distance fade by camera distance: gone nearer than fade_min, whole beyond fade_max
uniform float fade_max = 0.0;  // 0: no fade

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
			vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0), vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
			vec4(0.0, 0.0, 0.0, 1.0));
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	float c = cell >= 0.0 ? cell : INSTANCE_CUSTOM.x;
	bool m = cell >= 0.0 ? mirror : INSTANCE_CUSTOM.y > 0.5;
	UV.x = (floor(c + 0.5) + (m ? 1.0 - UV.x : UV.x)) / cells;
}

void fragment() {
	vec4 t = texture(puff, UV);
	ALBEDO = t.rgb;
	float a = t.a * alpha;
	if (fade_max > 0.0) {
		a *= clamp(smoothstep(fade_min, fade_max, length(VERTEX)), 0.0, 1.0);
	}
	ALPHA = a;
}
