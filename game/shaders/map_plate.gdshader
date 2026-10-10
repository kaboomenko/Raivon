shader_type spatial;
// Map plates (docs/ui_style.md §4.14, plan step s13): the HUD's badges and chips drawn in the 3D view, built by
// map_view.gd (_plate_mat). A unit quad becomes a billboard of a fixed size on screen, exactly as Label3D / Sprite3D do
// with billboard + fixed_size, so the plate, its number (Label3D) and its icon (Sprite3D) stay together at any zoom.
// Everything is in design pixels (941×1672 canvas): `box` is the quad's size, `shift` its centre off the node's origin
// (+y up), and `px_k` turns a design pixel into world units at depth 1 (2·tan(fov/2) / canvas height).
//   kind 0, the army plate: a pointy-top rounded hex (R hex_r, corners 0.22R) — an INK contour 4, the team face raised
//     over its lip by 0.14R, a gloss on the top 42 % — with the strength bar under it (bar_size, INK contour 3, a dark
//     track, the team colour filled to k with round ends; k < 0 hides the bar). As Kit's hex badge and Kit.bar.
//   kind 1, the chip: a pill of the quad's size less 2 px a side, `face` (INK α 0.85 for a status chip) inside an
//     optional contour `edge` edge_w wide.
// Colours come in already through SoftPalette.scene(), so the tonemapped view shows the UI's own colours.
render_mode unshaded, blend_mix, depth_test_disabled, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform int kind = 0;
uniform float px_k = 0.000343;
uniform vec4 face : source_color = vec4(0.31, 0.66, 1.0, 1.0);
uniform vec4 lip : source_color = vec4(0.11, 0.3, 0.7, 1.0);
uniform vec4 gloss : source_color = vec4(0.6, 0.8, 1.0, 1.0);
uniform vec4 ink : source_color = vec4(0.106, 0.129, 0.251, 1.0);
uniform vec4 track : source_color = vec4(0.09, 0.125, 0.227, 1.0);
uniform vec4 edge : source_color = vec4(0.0);
uniform float edge_w = 0.0;
uniform float hex_r = 26.0;
uniform vec2 hex_c = vec2(0.0, 34.0);
uniform vec2 bar_c = vec2(0.0, 6.0);
uniform vec2 bar_size = vec2(64.0, 12.0);

instance uniform vec2 box = vec2(72.0, 68.0);
instance uniform vec2 shift = vec2(0.0, 31.0);
instance uniform float k = 1.0;
instance uniform float fade = 1.0;

varying vec2 pa;  // the fragment in design pixels from the node's origin, +y up

void vertex() {
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	float sc = -MODELVIEW_MATRIX[3].z;  // scale by depth (Godot's fixed_size)
	if (PROJECTION_MATRIX[3][3] != 0.0) {
		sc = abs(1.0 / PROJECTION_MATRIX[1][1]);  // orthogonal: as fixed_size does
	}
	pa = VERTEX.xy * box + shift;
	VERTEX = vec3(pa * px_k * sc, 0.0);
}

float sd_box(vec2 p, vec2 hs, float r) {
	vec2 q = abs(p) - hs + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

// The pointy-top rounded hex of circumradius rr (corner radius 0.22R of the full badge), p from its centre.
float sd_badge(vec2 p, float rr, float rho) {
	return sd_round_hex(p.yx, rr * HEX_IN, rho);
}

float cover(float d, float px) {
	return clamp(0.5 - d / px, 0.0, 1.0);
}

// Premultiplied "over": the layer c with coverage a on top of dst (rgb premultiplied, a).
vec4 over(vec4 dst, vec3 c, float a) {
	return vec4(c * a + dst.rgb * (1.0 - a), a + dst.a * (1.0 - a));
}

void fragment() {
	float px = max(length(fwidth(pa)) * 0.7071, 1e-4);  // one screen pixel in design pixels
	vec4 o = vec4(0.0);
	if (kind == 0) {
		vec2 p = pa - hex_c;
		float rho = 0.22 * hex_r;
		float out_w = hex_r > 24.0 ? 4.0 : 3.0;
		float lip_h = 0.14 * hex_r;
		float d0 = sd_badge(p, hex_r, rho);
		float d1 = d0 + out_w;  // inside the contour
		float df = max(d1, sd_badge(p - vec2(0.0, lip_h), hex_r, rho) + out_w);  // the face: raised by the lip
		o = over(o, ink.rgb, cover(d0, px));
		o = over(o, lip.rgb, cover(d1, px));
		o = over(o, face.rgb, cover(df, px));
		// the gloss: a deeper inset, clipped to the top 42 % of the face
		float top = hex_r - out_w;
		float bottom = -hex_r + out_w + lip_h;
		float gy = top - (top - bottom) * 0.42;
		float dg = max(d0 + out_w + 0.12 * hex_r, gy - p.y);
		o = over(o, gloss.rgb, cover(dg, px));
		if (k >= 0.0) {
			vec2 b = pa - bar_c;
			vec2 hs = bar_size * 0.5;
			float db = sd_box(b, hs, hs.y);
			o = over(o, ink.rgb, cover(db, px));
			vec2 ih = hs - 3.0;
			o = over(o, track.rgb, cover(sd_box(b, ih, ih.y), px));
			if (k > 0.0) {
				float fw = max(ih.y * 2.0, ih.x * 2.0 * clamp(k, 0.0, 1.0));
				vec2 fc = vec2(-ih.x + fw * 0.5, 0.0);
				float dfill = sd_box(b - fc, vec2(fw * 0.5, ih.y), ih.y);
				o = over(o, face.rgb, cover(dfill, px));
				// a light line along the fill's top
				o = over(o, gloss.rgb, cover(max(dfill + 1.0, ih.y - 1.5 - b.y), px) * 0.9);
			}
		}
	} else {
		vec2 hs = box * 0.5 - 2.0;
		float d = sd_box(pa - shift, hs, hs.y);
		if (edge_w > 0.0) {
			o = over(o, edge.rgb, cover(d, px) * edge.a);
			o = over(o, face.rgb, cover(d + edge_w, px) * face.a);
		} else {
			o = over(o, face.rgb, cover(d, px) * face.a);
		}
	}
	float a = o.a * fade;
	if (a < 0.003) {
		discard;
	}
	ALBEDO = o.rgb / max(o.a, 1e-4);
	ALPHA = a;
}
