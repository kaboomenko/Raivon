shader_type spatial;
// The baked GLB materials are double-sided (StandardMaterial3D cull_mode = disabled): leaves, cloth and single
// planes must stay visible from behind, and DO_SIDE_CHECK flips the normal of a back face for the light.
render_mode cull_disabled;
// «Raivon Soft» look of every imported model (docs/art_direction.md §6.5), swapped in at load by
// scripts/soft_look.gd for the one albedo-baked StandardMaterial3D each GLB ships: the soft wrapped light,
// saturation ×1.15, a ground-to-top gradient and a slight mip bias that melts 1–2 px mortar lines.
#include "res://shaders/soft_light.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform vec4 albedo_color : source_color = vec4(1.0);
uniform float roughness_v = 0.9;

varying float v_y;  // world height; MODEL_MATRIX includes a MultiMesh instance transform, and all land is at y = 0

void vertex() {
	v_y = (MODEL_MATRIX * vec4(VERTEX, 1.0)).y;
}

void fragment() {
	// bias 0.5: one-pixel mortar seams soften; 1 and more bleeds the black gutters between the bake's islands
	vec3 c = texture(albedo_tex, UV, 0.5).rgb * albedo_color.rgb;
	float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c = max(mix(vec3(l), c, 1.15), vec3(0.0));
	c *= mix(0.86, 1.06, smoothstep(0.0, 0.6, v_y));  // feet in the grass a touch darker, tops a touch lighter
	ALBEDO = soft_floor(c);  // the 0.86 at the ground had pushed the mine and tent entrances under L* 15
	ROUGHNESS = roughness_v;
	SPECULAR = 0.2;
}
