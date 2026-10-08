shader_type spatial;
// Hand-painted ground: vertex colour (biome + territory tint) broken up by large patches,
// dirt spots and fine grass speckle, world-space so tiles join seamlessly.
render_mode cull_back;

uniform sampler2D noise_big : filter_linear_mipmap, repeat_enable;
uniform sampler2D noise_fine : filter_linear_mipmap, repeat_enable;
uniform vec3 dirt_color : source_color = vec3(0.45, 0.33, 0.2);
uniform float dirt_amount = 0.22;

varying vec3 wpos;
varying vec3 wnormal;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnormal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec3 base = pow(COLOR.rgb, vec3(2.2)); // vertex colours are authored in sRGB
	float big = texture(noise_big, wpos.xz * 0.045).r;
	float mid = texture(noise_big, wpos.xz * 0.21 + vec2(0.37, 0.11)).r;
	float fine = texture(noise_fine, wpos.xz * 1.6).r;
	float top = smoothstep(0.6, 0.9, wnormal.y);
	// large light/dark meadow patches
	vec3 c = base * mix(0.78, 1.18, big);
	// warm sunlit tufts vs cool shade
	c = mix(c, c * vec3(1.12, 1.08, 0.82), smoothstep(0.55, 0.8, mid) * 0.6);
	// dirt patches on flat ground
	float dirt = smoothstep(0.62, 0.78, mid * 0.6 + big * 0.5) * dirt_amount * top;
	c = mix(c, dirt_color * (0.8 + 0.4 * fine), dirt);
	// fine grass speckle
	c *= mix(0.86, 1.1, fine);
	// rocky cliffs on the tile skirts (the reference's plateau edges): layered grey-brown strata with a grassy lip
	float strata = sin(wpos.y * 38.0 + texture(noise_fine, wpos.xz * 0.9 + wpos.y).r * 4.0) * 0.5 + 0.5;
	vec3 rock = mix(vec3(0.2, 0.18, 0.16), vec3(0.42, 0.39, 0.34), strata * 0.6 + fine * 0.4);
	float lip = smoothstep(-0.12, -0.02, wpos.y);  // the turf overhang just under the hex top
	c = mix(mix(rock, c * 0.7, lip), c, top);
	ALBEDO = c;
	ROUGHNESS = 0.92;
	SPECULAR = 0.2;
}
