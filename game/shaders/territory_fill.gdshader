shader_type spatial;
// «Raivon Soft» territory fill (docs/art_direction.md §6.6): a wash of the state's colour that is strongest at the
// border and fades inward along the exact distance to foreign land, so its contours are round — no star creases
// from the hex centres, no hexagonal bands. Built by map_view._rebuild_overlay as one 6-triangle fan per owned hex:
//   UV  = the vertex offset from the hex centre in (x, z) (hex_sdf.gdshaderinc's local frame);
//   UV2 = (mask: bit k set when neighbour k is foreign, off-map or impassable; born: the ceremony flip time).
// It starts at `start` inside the border line, under the ribbon's dark rim.
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, shadows_disabled;

#include "res://shaders/hex_sdf.gdshaderinc"

uniform vec3 team : source_color;  // team_look(o).fill
uniform float a_rim = 0.42;  // alpha at the border (by zoom, map_view._fill_zoom)
uniform float a_in = 0.10;  // alpha deep inside
uniform float fade = 0.9;  // how far inward the rim alpha fades (<= 0.9: the field only sees the six neighbours)
uniform float start = 0.07;  // the fill begins this far inside the border line
uniform float now = 1000000.0;  // the ceremony clock: a freshly captured hex fades in over 0.35 s

varying vec2 v_p;
varying flat float v_mask;
varying flat float v_born;

void vertex() {
	v_p = UV;
	v_mask = UV2.x;
	v_born = UV2.y;
}

void fragment() {
	float d = mask_dist(v_p, int(v_mask + 0.5), 0.22);
	float t = smoothstep(0.0, fade, d - start);
	float a = (a_in + (a_rim - a_in) * pow(1.0 - t, 1.5)) * smoothstep(start - 0.02, start, d);
	ALBEDO = team;
	ALPHA = a * smoothstep(v_born, v_born + 0.35, now);
}
