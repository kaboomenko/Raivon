shader_type spatial;
// «Raivon Soft» border ribbon (docs/art_direction.md §6.6): one solid, rounded candy ribbon along each state's
// border instead of the neon halo, the white core and the inner hex grid. Built by map_view._emit_ribbon:
//   UV.x  = arc length along the loop (world units), UV.y = signed offset from the border line (+ inward);
//   COLOR = (edge kind / 2: 0 wild or water, 0.5 another state, 1 the war front;
//            wild: 1 on edges facing no-man's land or water, faded across the corner arcs;
//            t along the edge 0..1 for the capture draw-on; 1);
//   UV2.x = the time the hex flipped in the capture ceremony (-1000 = always drawn).
// Profile from the border line inward (v = UV.y / w): dark rim 0–17 %, body, light band 30–52 %, an anti-aliased
// edge at 100 %, a soft inner shadow to 145 % (alpha 0.28). Outward: a soft skirt 0.10 wide, only on wild edges.
// No emission (unshaded ignores it): in DL8 the light band glows by adding to the HDR albedo (glow_k).
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;

uniform vec3 body : source_color;
uniform vec3 rim : source_color;
uniform vec3 hi : source_color;
uniform float w = 0.16;  // visible width, by zoom (map_view.set_zoom): 0.08 close … 0.16 strategic
uniform float skirt = 0.10;  // the outer skirt width (map_view.RIB_SKIRT)
uniform float skirt_a = 0.3;  // skirt alpha, by zoom 0.2 … 0.32
uniform float now = 1000000.0;  // the ceremony clock (map_view.ceremony_t), 1e6 outside a ceremony
uniform float glow_k = 0.0;  // DL8: the light band adds hi * glow_k (keep the result <= 1.6)
uniform float pulse = 0.0;  // 0..1 alpha pulse (P8 markers)
uniform float dash = 0.0;  // > 0: dashed along UV.x with this period (P8 markers)

void fragment() {
	float prog = clamp((now - UV2.x) / 0.3, 0.0, 1.0);
	if (COLOR.b > prog + 0.0001) {
		discard;  // capture: the edge is drawn on along its length in 0.3 s
	}
	float y = UV.y;
	vec3 c;
	float a;
	if (y < 0.0) {  // the soft outer skirt, wild and water edges only
		float s = clamp(1.0 + y / skirt, 0.0, 1.0);
		c = mix(body, hi, 0.35);
		a = skirt_a * COLOR.g * s * s;
	} else {
		float v = y / w;
		if (v > 1.45) {
			discard;
		}
		float aa = fwidth(v) * 0.75;
		c = mix(rim, body, smoothstep(0.17 - aa, 0.17 + aa, v));
		float band = smoothstep(0.30 - aa, 0.30 + aa, v) * (1.0 - smoothstep(0.52 - aa, 0.52 + aa, v));
		float front = step(0.75, COLOR.r);
		float breathe = front * (0.5 + 0.5 * sin(TIME * 3.14159));  // 0.5 Hz
		float tick = front * band * smoothstep(0.45, 0.55, fract(UV.x / 0.6 - TIME * 0.5));
		c = mix(c, hi, band * mix(0.85, 1.0, breathe));
		c = mix(c, vec3(1.0), tick * 0.35);
		c += hi * band * glow_k;
		// The outer edge is anti-aliased only where ground shows beyond it (wild edges): on a shared border the
		// neighbour's ribbon starts exactly at the same line, and fading both rims there let the ground through as a
		// light hairline in the middle of the dark seam.
		float outer = mix(1.0, smoothstep(0.0, 2.0 * aa, v), COLOR.g);
		a = (1.0 - smoothstep(1.0 - aa, 1.0 + aa, v)) * outer;
		if (v > 1.0) {  // the soft inner shadow
			c = rim * 0.35;
			a = 0.28 * pow(1.0 - (v - 1.0) / 0.45, 2.0);
		}
	}
	if (dash > 0.0) {
		a *= step(fract(UV.x / dash), 0.6);
	}
	a *= mix(1.0, 0.75 + 0.25 * (0.5 + 0.5 * sin(TIME * 5.236)), pulse);
	ALBEDO = c;
	ALPHA = a;
}
