// Flat-top hex geometry in screen space (docs/gdd/02_map_territory.md §2).

export interface Pt {
  x: number;
  y: number;
}

export interface Layout {
  R: number;
  ox: number;
  oy: number;
}

const SQ3 = Math.sqrt(3);

export function hexCenter(L: Layout, q: number, r: number): Pt {
  return { x: L.ox + 1.5 * L.R * q, y: L.oy + SQ3 * L.R * (r + q / 2) };
}

/** Corner k (0..5) at angle 60k° (flat-top). */
export function corner(c: Pt, R: number, k: number): Pt {
  const a = (Math.PI / 3) * k;
  return { x: c.x + R * Math.cos(a), y: c.y + R * Math.sin(a) };
}

export function hexPoly(c: Pt, R: number): number[] {
  const out: number[] = [];
  for (let k = 0; k < 6; k++) {
    const p = corner(c, R, k);
    out.push(p.x, p.y);
  }
  return out;
}

/** Corner pair of the edge facing neighbor DIRS[dir] (see sim/hex.ts). */
export const EDGE_CORNERS: readonly [number, number][] = [
  [0, 1],
  [5, 0],
  [4, 5],
  [3, 4],
  [2, 3],
  [1, 2],
];

export function pixelToAxial(L: Layout, x: number, y: number): { q: number; r: number } {
  const px = (x - L.ox) / L.R;
  const py = (y - L.oy) / L.R;
  const q = (2 / 3) * px;
  const r = (-1 / 3) * px + (SQ3 / 3) * py;
  return cubeRound(q, r);
}

function cubeRound(fq: number, fr: number): { q: number; r: number } {
  const fs = -fq - fr;
  let q = Math.round(fq);
  let r = Math.round(fr);
  const s = Math.round(fs);
  const dq = Math.abs(q - fq);
  const dr = Math.abs(r - fr);
  const ds = Math.abs(s - fs);
  if (dq > dr && dq > ds) q = -r - s;
  else if (dr > ds) r = -q - s;
  return { q, r };
}

/** Clip segment a→b to a convex polygon (Cyrus–Beck). Returns null if outside. */
export function clipToConvex(a: Pt, b: Pt, poly: Pt[]): [Pt, Pt] | null {
  let t0 = 0;
  let t1 = 1;
  const d = { x: b.x - a.x, y: b.y - a.y };
  // polygon is clockwise in screen space (y down) for corners at 0..300°
  for (let i = 0; i < poly.length; i++) {
    const p = poly[i]!;
    const q = poly[(i + 1) % poly.length]!;
    // inward normal for this winding
    const n = { x: -(q.y - p.y), y: q.x - p.x };
    const w = { x: a.x - p.x, y: a.y - p.y };
    const num = n.x * w.x + n.y * w.y;
    const den = n.x * d.x + n.y * d.y;
    if (Math.abs(den) < 1e-9) {
      if (num < 0) return null;
      continue;
    }
    const t = -num / den;
    if (den > 0) t0 = Math.max(t0, t);
    else t1 = Math.min(t1, t);
    if (t0 > t1) return null;
  }
  return [
    { x: a.x + d.x * t0, y: a.y + d.y * t0 },
    { x: a.x + d.x * t1, y: a.y + d.y * t1 },
  ];
}

export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
export const clamp01 = (t: number): number => Math.max(0, Math.min(1, t));
export const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
export const easeInOut = (t: number): number => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

export function shade(color: number, k: number): number {
  const r = Math.min(255, Math.round(((color >> 16) & 0xff) * k));
  const g = Math.min(255, Math.round(((color >> 8) & 0xff) * k));
  const b = Math.min(255, Math.round((color & 0xff) * k));
  return (r << 16) | (g << 8) | b;
}
