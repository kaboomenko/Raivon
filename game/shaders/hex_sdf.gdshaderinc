// «Raivon Soft» hex distance fields (docs/art_direction.md §6.1, §6.6): shared by the territory fill, the scorch,
// the occupation hatch, the terrain seams and the water foam.
// Frame: map (x, z) goes straight to SDF (x, y), in hex radii (R = 1). Corner k is at 60°·k (as map_view._hex_pts),
// so the flat edges of a hex at the origin are at y = ±HEX_IN.
// Sources: Inigo Quilez, 2D distance functions (sdHexagon) and smooth minimum; Red Blob Games, hex rounding.
#ifndef HEX_SDF_INC
#define HEX_SDF_INC

const float SOFT_R = 0.3;  // the one corner radius of every hex contour (soft_palette.gd SOFT_R)
const float HEX_IN = 0.866025;  // the inradius (apothem) of a hex of radius 1

// Signed distance to a flat-topped hexagon of inradius r centred at the origin (negative inside).
float sd_hex(vec2 p, float r) {
	const vec3 k = vec3(-0.866025404, 0.5, 0.577350269);
	p = abs(p);
	p -= 2.0 * min(dot(k.xy, p), 0.0) * k.xy;
	p -= vec2(clamp(p.x, -k.z * r, k.z * r), r);
	return length(p) * sign(p.y);
}

// The same hexagon (same inradius r) with its corners rounded by rho.
float sd_round_hex(vec2 p, float r, float rho) {
	return sd_hex(p, r - rho) - rho;
}

// Polynomial smooth minimum: rounds the corner where two distance fields meet, within k.
float smin(float a, float b, float k) {
	float h = max(k - abs(a - b), 0.0) / k;
	return min(a, b) - h * h * k * 0.25;
}

// The centre of neighbour k relative to the hex centre, in map_view DIRS / sim.neighbors order.
vec2 nb_off(int k) {
	if (k == 0) { return vec2(1.5, 0.866025); }
	if (k == 1) { return vec2(1.5, -0.866025); }
	if (k == 2) { return vec2(0.0, -1.732051); }
	if (k == 3) { return vec2(-1.5, -0.866025); }
	if (k == 4) { return vec2(-1.5, 0.866025); }
	return vec2(0.0, 1.732051);
}

// World (x, z) -> the offset from the centre of the hex it lies in (identical rounding to map_view.id_at_world).
vec2 hex_local(vec2 w) {
	float q = w.x / 1.5;
	float r = w.y / 1.7320508 - q * 0.5;
	float s = -q - r;
	float rq = round(q);
	float rr = round(r);
	float rs = round(s);
	float dq = abs(rq - q);
	float dr = abs(rr - r);
	float ds = abs(rs - s);
	if (dq > dr && dq > ds) { rq = -rr - rs; } else if (dr > ds) { rr = -rq - rs; }
	return w - vec2(1.5 * rq, 1.7320508 * (rr + rq * 0.5));
}

// Distance from p (hex-local) to the union of the neighbours whose bit is set in mask (bit k = neighbour k),
// with their meeting corners rounded by smin(k). 9.0 when the mask is empty. The field only knows the six
// neighbours: the nearest second-ring hex is >= 1.0 away, so anything fading out within 0.9 stays seamless.
float mask_dist(vec2 p, int mask, float k) {
	float d = 9.0;
	for (int i = 0; i < 6; i++) {
		if (((mask >> i) & 1) == 1) {
			d = smin(d, sd_hex(p - nb_off(i), HEX_IN), k);
		}
	}
	return d;
}

#endif
