shader_type canvas_item;
// Tilt-shift and vignette over the 3D map (docs/art_direction.md §1: «лёгкий tilt-shift — размытие ближнего низа и
// дальнего верха»). The vignette is light and cool (§6.4): the corners tint towards (0.86, 0.90, 1.0) instead of
// sinking into black. Drawn on a canvas layer below the HUD, so the UI stays sharp.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float top_zone = 0.16;     // fraction of the screen height blurred from the top
uniform float bottom_start = 0.66; // blur ramps in from here to the bottom
uniform float max_lod = 2.2;
uniform float vignette = 0.12;  // 0.12 -> corners reach (0.86, 0.90, 1.0)

void fragment() {
	vec2 uv = SCREEN_UV;
	float t = max(1.0 - smoothstep(0.0, top_zone, uv.y), smoothstep(bottom_start, 1.0, uv.y));
	vec3 c = textureLod(screen_tex, uv, t * max_lod).rgb;
	vec2 d = (uv - 0.5) * vec2(1.15, 0.85);
	float m = smoothstep(0.32, 0.78, length(d));
	c *= mix(vec3(1.0), vec3(1.0 - vignette * 1.15, 1.0 - vignette * 0.8, 1.0), m);
	COLOR = vec4(c, 1.0);
}
