// Axial hex coordinates, flat-top orientation (docs/gdd/02_map_territory.md).
// Screen: x grows with q, y grows with r (+ q/2). Pixel conversion lives in the client.

export interface Axial {
  q: number;
  r: number;
}

// Order matters for edge indexing: edge i of a hex is shared with neighbor DIRS[i].
export const DIRS: readonly Axial[] = [
  { q: 1, r: 0 }, // 0: lower-right
  { q: 1, r: -1 }, // 1: upper-right
  { q: 0, r: -1 }, // 2: up
  { q: -1, r: 0 }, // 3: upper-left
  { q: -1, r: 1 }, // 4: lower-left
  { q: 0, r: 1 }, // 5: down
];

export const hexKey = (q: number, r: number): string => `${q},${r}`;

export function hexDistance(a: Axial, b: Axial): number {
  const dq = a.q - b.q;
  const dr = a.r - b.r;
  return (Math.abs(dq) + Math.abs(dr) + Math.abs(dq + dr)) / 2;
}

export function neighborOf(h: Axial, dir: number): Axial {
  const d = DIRS[dir]!;
  return { q: h.q + d.q, r: h.r + d.r };
}

export function disk(radius: number): Axial[] {
  const out: Axial[] = [];
  for (let q = -radius; q <= radius; q++) {
    const r1 = Math.max(-radius, -q - radius);
    const r2 = Math.min(radius, -q + radius);
    for (let r = r1; r <= r2; r++) out.push({ q, r });
  }
  return out;
}

// Direction index from a to an adjacent b, or -1.
export function dirTo(a: Axial, b: Axial): number {
  for (let i = 0; i < 6; i++) {
    const d = DIRS[i]!;
    if (a.q + d.q === b.q && a.r + d.r === b.r) return i;
  }
  return -1;
}
