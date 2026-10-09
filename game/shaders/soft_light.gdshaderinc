// «Raivon Soft» model light (docs/art_direction.md §6.5), shared by soft_model.gdshader and troops.gdshader.
// - wrapped diffuse: a soft band smoothstep(-0.3, 0.8, N·L) instead of a hard terminator; the band is warm
//   (peach) where it fades, white where the face is fully lit;
// - a faint fresnel rim (0.2) on the lit side only;
// - no specular highlight: the models are matte toys.
// The shade side gets only the cool sky ambient of main.gd (#A9C1E8), so it reads blue-lilac, never black.
// LIGHT_COLOR carries a × PI in Godot 4 (light_storage.cpp), hence the / PI; ATTENUATION holds the shadow.
void light() {
	float ndl = dot(NORMAL, LIGHT);
	float w = smoothstep(-0.3, 0.8, ndl);
	vec3 warm = mix(vec3(1.0, 0.82, 0.72), vec3(1.0), smoothstep(0.3, 0.9, w));
	DIFFUSE_LIGHT += LIGHT_COLOR / PI * ATTENUATION * w * warm;
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	SPECULAR_LIGHT += LIGHT_COLOR / PI * ATTENUATION * fres * 0.2 * step(0.0, ndl);
}
