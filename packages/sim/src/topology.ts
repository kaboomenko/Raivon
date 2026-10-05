// Supply and pockets (canon §9.7). Supply depends only on connectivity, not distance.

import { isPassable, type World } from './types.js';

/** Hexes controlled by `side` that can trace a path of `side`-controlled hexes to a supply source. */
export function supplied(w: World, side: number, blocked: ReadonlySet<number> = new Set()): Set<number> {
  const out = new Set<number>();
  const queue: number[] = [];
  for (const c of w.cells) {
    if (c.controller !== side || c.owner !== side || blocked.has(c.id)) continue;
    if (c.kind === 'capital' || c.kind === 'military_base' || c.kind === 'port') {
      out.add(c.id);
      queue.push(c.id);
    }
  }
  while (queue.length) {
    const id = queue.pop()!;
    for (const n of w.neighbors[id]!) {
      if (n < 0 || out.has(n) || blocked.has(n)) continue;
      const c = w.cells[n]!;
      if (!isPassable(c) || c.controller !== side) continue;
      out.add(n);
      queue.push(n);
    }
  }
  return out;
}

/**
 * Pockets of `side` against `enemy`: connected groups of ≤12 `side`-controlled hexes without supply
 * that border `enemy` (an isolated exclave not touching the enemy is not a pocket).
 */
export function pockets(w: World, side: number, enemy: number, blocked: ReadonlySet<number> = new Set()): number[][] {
  const sup = supplied(w, side, blocked);
  const seen = new Set<number>();
  const result: number[][] = [];
  for (const c of w.cells) {
    if (c.controller !== side || !isPassable(c) || sup.has(c.id) || seen.has(c.id)) continue;
    const group: number[] = [];
    const queue = [c.id];
    seen.add(c.id);
    let touchesEnemy = false;
    while (queue.length) {
      const id = queue.pop()!;
      group.push(id);
      for (const n of w.neighbors[id]!) {
        if (n < 0) continue;
        const nc = w.cells[n]!;
        if (nc.controller === enemy) touchesEnemy = true;
        if (nc.controller !== side || !isPassable(nc) || sup.has(n) || seen.has(n)) continue;
        seen.add(n);
        queue.push(n);
      }
    }
    if (touchesEnemy && group.length <= 12) result.push(group.sort((a, b) => a - b));
  }
  return result;
}

/** Ring distance (BFS over passable hexes) from a seed set; used by the peace ceremony ink wave. */
export function ringsFrom(w: World, seeds: Iterable<number>, within: ReadonlySet<number>): Map<number, number> {
  const dist = new Map<number, number>();
  let frontier: number[] = [];
  for (const s of seeds) {
    dist.set(s, 0);
    frontier.push(s);
  }
  let d = 0;
  while (frontier.length) {
    d++;
    const next: number[] = [];
    for (const id of frontier) {
      for (const n of w.neighbors[id]!) {
        if (n < 0 || dist.has(n) || !within.has(n)) continue;
        dist.set(n, d);
        next.push(n);
      }
    }
    frontier = next;
  }
  return dist;
}
