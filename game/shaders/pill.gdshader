shader_type spatial;
// «Raivon Soft» pill (docs/art_direction.md §6.7: the strength bars are "pills"; soft_style_plan P8): a rounded
// rectangle on a quad, corner radius half the quad's height, its edge anti-aliased over one pixel. Two uses, both
// built by map_view._make_army on the bar's two quads:
//   the track (fill = false): `col` with a 1 px navy outline;
//   the fill (fill = true): `col` with a 1 px lighter highlight along its top, cut at the instance's k (0..1). The
//   quad keeps its full size, so the left end stays round at any strength (both ends at full strength) and the cut
//   is a clean, anti-aliased vertical edge; no more squashing the quad by scale.x.
render_mode unshaded, blend_mix, depth_test_disabled, depth_draw_never, cull_disabled, shadows_disabled;

uniform vec4 col : source_color = vec4(1.0);
uniform vec2 size = vec2(0.7, 0.1);  // the quad's size in world units: the SDF works in them, so the ends stay round
uniform bool fill = false;
uniform vec3 outline : source_color = vec3(0.05, 0.1, 0.2);  // the track's outline (UI navy, docs/ui_style.md)
instance uniform float k = 1.0;  // the fill's share 0..1 (map_view.sync_armies: strength / max strength)

void fragment() {
	vec2 hs = size * 0.5;
	vec2 p = (UV - 0.5) * size;  // UV.y = 0 at the top, so p.y < 0 is the upper half
	float r = hs.y;
	vec2 q = abs(p) - hs + r;
	float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;  // the rounded box's distance, < 0 inside
	float px = max(fwidth(d), 1e-5);  // one pixel in world units
	float a = col.a * (1.0 - smoothstep(-0.5 * px, 0.5 * px, d));
	vec3 c = col.rgb;
	if (fill) {
		// the top highlight: the outer pixel of the upper half, fading out toward the middle of the ends
		float band = smoothstep(-2.0 * px, -1.0 * px, d);
		float top = smoothstep(-0.1 * r, -0.5 * r, p.y);
		c = mix(c, mix(c, vec3(1.0), 0.55), band * top);
		float pu = max(fwidth(UV.x), 1e-5);
		if (UV.x > k + pu) {
			discard;
		}
		a *= 1.0 - smoothstep(k - pu, k + pu, UV.x);
	} else {
		c = mix(c, outline, smoothstep(-1.6 * px, -0.6 * px, d));
	}
	ALBEDO = c;
	ALPHA = a;
}
