shader_type spatial;
// Squad figures come baked into one mesh (tools/blender/troops_assets.py: 4×3 block, 0.13 spacing, odd rows
// shifted 0.06; figures face +Z, hips at y ≈ 0.16). Each vertex finds its figure from that grid, so every
// figure moves as one piece with its own phase:
// - march: a body bob, legs scissoring around the hip with the foot lifted, arms swinging against the legs;
// - fight: a three-beat strike — slow wind-up, quick lunge, recovery — strongest at the head and weapon tip,
//   with a half step forward on the lunge;
// - idle: a faint breath so a standing army is never frozen.
// Lit like every other model (docs/art_direction.md §6.5): the soft wrapped light of soft_light.gdshaderinc,
// saturation ×1.15, a feet-to-head gradient and a slight mip bias, as in soft_model.gdshader.
#include "res://shaders/soft_light.gdshaderinc"

uniform sampler2D albedo_tex : source_color, filter_linear_mipmap;
uniform float roughness_v = 0.9;
uniform bool solid = false;  // one unit (rider, vehicle): a single phase, no per-figure split, no legs
instance uniform float march = 0.0;
instance uniform float fight = 0.0;

const float HIP = 0.16;

varying float v_h;  // the undeformed object-space height (troops stand about 0.4 tall)

// the figure a vertex belongs to; parts poking out of the block (front tabards, weapon tips) stay with the
// outer figures instead of falling into a phantom row or column with another phase
vec2 figure_cell(vec3 v) {
	float row = clamp(floor((-v.z + 0.185) / 0.13), 0.0, 2.0);
	float off = mod(row, 2.0) > 0.5 ? 0.06 : 0.0;
	float col = clamp(floor((v.x + 0.265 - off) / 0.13), 0.0, 3.0);
	return vec2(col, row);
}

float figure_phase(vec2 cell) {
	if (solid) {
		return 0.0;
	}
	return fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453) * 6.2831;
}

// the strike curve over one cycle: wind-up to −0.4, lunge to 1, back to 0
float strike(float c) {
	if (c < 0.58) {
		return -0.4 * smoothstep(0.0, 0.58, c);
	}
	if (c < 0.7) {
		return mix(-0.4, 1.0, (c - 0.58) / 0.12);
	}
	return mix(1.0, 0.0, smoothstep(0.7, 1.0, c));
}

void vertex() {
	vec3 v = VERTEX;
	v_h = v.y;
	vec2 cell = figure_cell(v);
	float ph = figure_phase(cell);
	float h = clamp(v.y / 0.4, 0.0, 1.0);
	float t = TIME;
	float gait = sin(t * 9.0 + ph);
	if (!solid) {
		float row_off = mod(cell.y, 2.0) > 0.5 ? 0.06 : 0.0;
		float cx = -0.2 + cell.x * 0.13 + row_off;
		float side = v.x < cx ? -1.0 : 1.0;
		// legs: swing around the hip, the forward foot lifted
		float leg = clamp((HIP - v.y) / HIP, 0.0, 1.0);
		float swing = gait * side;
		VERTEX.z += swing * 0.032 * leg * march;
		VERTEX.y += max(0.0, swing) * 0.014 * leg * march;
		// arms (out from the torso, between waist and shoulder) swing against the legs
		float arm_zone = smoothstep(0.18, 0.22, v.y) * (1.0 - smoothstep(0.32, 0.36, v.y)) * step(0.06, abs(v.x - cx));
		VERTEX.z -= swing * 0.022 * arm_zone * march;
	}
	// the body bobs twice per stride
	VERTEX.y += abs(gait) * 0.018 * march;
	// leans are linear in height — a shear keeps every flat part flat, so a tabard never cuts through the
	// emblem plate in front of it (a curved lean bends thin plates and long boxes differently)
	VERTEX.z += gait * 0.006 * march * h;
	// fighting: the strike, the weapon tip and head leading; a half step forward on the lunge
	float s = strike(fract(t * 1.5 + ph / 6.2831));
	VERTEX.z += s * 0.045 * fight * h + max(s, 0.0) * 0.012 * fight;
	VERTEX.x += sin(t * 7.0 + ph) * 0.007 * fight * h;
	VERTEX.y -= max(-s, 0.0) * 0.012 * fight * h;  // crouch into the wind-up
	// idle: a slow breath
	float idle = 1.0 - max(march, fight);
	VERTEX.y += v.y * 0.025 * (0.5 + 0.5 * sin(t * 2.1 + ph)) * idle;
}

void fragment() {
	vec3 c = texture(albedo_tex, UV, 0.5).rgb;
	float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
	c = max(mix(vec3(l), c, 1.15), vec3(0.0));
	c *= mix(0.86, 1.06, smoothstep(0.0, 0.35, v_h));
	ALBEDO = c;
	ROUGHNESS = roughness_v;
	SPECULAR = 0.2;
}
