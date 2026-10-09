// «Raivon Soft» model light and albedo (docs/art_direction.md §6.5), shared by soft_model.gdshader and troops.gdshader.
// Light:
// - half wrap: Lambert on the lit side, plus a soft band smoothstep(-0.3, 0.8, N·L) at WRAP_K of the sun that
//   carries the light past the terminator, so there is no hard edge (N·L = 0 gets 0.11, -0.3 gets 0). The band at
//   full strength (the first M1 build, as §6.5 writes it) lifted faces at N·L 0.5–0.7 to 0.8–0.95 of the sun:
//   light albedo clipped to white under Filmic (white-hot +0.7 pp) and lit volumes lost their form shading;
// - a warm (peach) terminator that turns white by N·L 0.5, so it stays off the shade faces;
// - a faint fresnel rim (0.2) on the lit side only;
// - no specular highlight: the models are matte toys;
// - the shade side gets the cool sky ambient of main.gd (#A9C1E8) plus a faint lilac fill (sun only, fading out
//   on lit faces), so a neutral wall in shade leans to the §6.3 shade hue #5B5A8C instead of grey (§6.1 rule 3).
// LIGHT_COLOR carries a × PI in Godot 4 (light_storage.cpp), hence the / PI; ATTENUATION holds the shadow.

const float WRAP_K = 0.6;
const vec3 SHADE_FILL = vec3(0.08, 0.0, 0.12);  // linear, added to the diffuse light where the sun does not reach
const vec3 SOFT_LUMA = vec3(0.2126, 0.7152, 0.0722);

// No albedo darker than #2A2A30 (§6.1; linear luminance 0.023): baked doorways, gutters and ink lines become
// charcoal instead of black holes. The floor is on luminance, not per channel: a per-channel max lifted the red
// and blue of the deep bake greens and turned the pines grey-teal.
vec3 soft_floor(vec3 c) {
	return c + max(0.023 - dot(c, SOFT_LUMA), 0.0) * vec3(1.0, 1.0, 1.3);
}

// Saturation ×k on the square root of the linear colour (close to the sRGB the eye judges): in linear space
// ×1.15 inflated the on-screen chroma of the dark bake greens by 30–36 % (pines toward lime).
vec3 soft_saturate(vec3 c, float k) {
	vec3 g = sqrt(max(c, vec3(0.0)));
	g = max(mix(vec3(dot(g, SOFT_LUMA)), g, k), vec3(0.0));
	return g * g;
}

// The baked albedo, softened: saturation ×1.15, the ground-to-top gradient 0.86 -> 1.06 (h: 0 at the feet,
// 1 at the top) and the floor. The top lift goes to the darker colours only: cream walls, sails, flagpoles and
// pale stone are already the lightest surfaces and clipped to white with it.
vec3 soft_albedo(vec3 c, float h) {
	c = soft_saturate(c, 1.15);
	float g = mix(0.86, 1.06, h);
	g = min(g, mix(1.06, 1.0, smoothstep(0.3, 0.6, dot(c, SOFT_LUMA))));
	return soft_floor(c * g);
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float w = max(clamp(ndl, 0.0, 1.0), WRAP_K * smoothstep(-0.3, 0.8, ndl));
	vec3 warm = mix(vec3(1.0, 0.82, 0.72), vec3(1.0), smoothstep(0.05, 0.5, ndl));
	float lit = w * ATTENUATION;
	DIFFUSE_LIGHT += LIGHT_COLOR / PI * lit * warm;
	if (LIGHT_IS_DIRECTIONAL) {
		DIFFUSE_LIGHT += (1.0 - smoothstep(0.0, 0.35, lit)) * SHADE_FILL;
	}
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	SPECULAR_LIGHT += LIGHT_COLOR / PI * ATTENUATION * fres * 0.2 * step(0.0, ndl);
}
