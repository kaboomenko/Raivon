shader_type canvas_item;
// Tilt-shift and vignette over the 3D map (docs/art_direction.md §1: «лёгкий tilt-shift — размытие ближнего низа и
// дальнего верха», edges sinking into shade). Drawn on a canvas layer below the HUD, so the UI stays sharp.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float top_zone = 0.16;     // fraction of the screen height blurred from the top
uniform float bottom_start = 0.66; // blur ramps in from here to the bottom
uniform float max_lod = 2.2;
uniform float vignette = 0.32;

void fragment() {
	vec2 uv = SCREEN_UV;
	float t = max(1.0 - smoothstep(0.0, top_zone, uv.y), smoothstep(bottom_start, 1.0, uv.y));
	vec3 c = textureLod(screen_tex, uv, t * max_lod).rgb;
	vec2 d = (uv - 0.5) * vec2(1.15, 0.85);
	c *= 1.0 - vignette * smoothstep(0.32, 0.78, length(d));
	COLOR = vec4(c, 1.0);
}
