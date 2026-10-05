// Battle AI — a small utility scorer (canon §9.16). Decides once per 0.5 s.
// Never targets the player's core (enforced by Battle.canTarget).

import { CARDS, ENERGY_UNIT, type Army, type Battle } from './battle.js';
import { isPassable, type StateId } from './types.js';

export class BattleAI {
  private lastMove = new Map<number, number>();

  constructor(private readonly side: StateId) {}

  think(b: Battle): void {
    if (b.over || b.tick % 5 !== 0) return;
    const energy = b.energy.get(this.side) ?? 0;
    const enemy = b.enemyOf(this.side);

    // 1. Shore up a defended hex that is losing.
    if (energy >= CARDS.defense.cost * ENERGY_UNIT && b.cardReady(this.side, 'defense')) {
      for (const cl of b.clashes) {
        if (cl.side !== enemy || cl.entering > 0 || b.hasEffect('defense', cl.target)) continue;
        const fc = b.forecast(enemy, cl.attackers, cl.target);
        const cell = b.world.cells[cl.target]!;
        if (fc.f >= 0.95 && (cl.defender !== null || cell.value >= 2)) {
          b.issue(this.side, { t: 'card', card: 'defense', target: cl.target });
          return;
        }
      }
    }

    // 2. Attack the best target.
    if (energy >= CARDS.attack.cost * ENERGY_UNIT) {
      let best: { target: number; armies: Army[]; score: number } | null = null;
      const seen = new Set<number>();
      for (const a of b.armies) {
        if (a.side !== this.side || a.routed || a.move || b.attacking(a)) continue;
        for (const t of b.world.neighbors[a.hex]!) {
          if (t < 0 || seen.has(t) || !b.canTarget(this.side, t)) continue;
          seen.add(t);
          const armies = b.adjacentIdleArmies(this.side, t);
          const fc = b.forecast(this.side, armies.map((x) => x.id), t);
          const cell = b.world.cells[t]!;
          const recapture = cell.owner === this.side ? 0.6 : 0;
          const score = fc.f + cell.value * 0.08 + recapture;
          if (fc.f >= 1.25 && (!best || score > best.score)) best = { target: t, armies, score };
        }
      }
      if (best) {
        if (best.armies.length >= 2 && b.cardReady(this.side, 'attack')) {
          b.issue(this.side, { t: 'card', card: 'attack', target: best.target });
        } else {
          b.issue(this.side, { t: 'attack', army: best.armies[0]!.id, target: best.target });
        }
        return;
      }
    }

    // 3. Reposition idle armies toward threatened frontier hexes.
    this.reposition(b, enemy);
  }

  private reposition(b: Battle, enemy: StateId): void {
    const threatened = new Set<number>();
    for (const a of b.armies) {
      if (a.side !== enemy || a.routed) continue;
      for (const n of b.world.neighbors[a.hex]!) {
        if (n >= 0 && b.world.cells[n]!.controller === this.side && !b.armyAt(n, this.side)) threatened.add(n);
      }
    }
    if (threatened.size === 0) return;
    for (const a of b.armies) {
      if (a.side !== this.side || a.routed || a.move || b.attacking(a)) continue;
      if ((this.lastMove.get(a.id) ?? -999) > b.tick - 30) continue;
      // Already on the front line? stay.
      if (b.world.neighbors[a.hex]!.some((n) => n >= 0 && b.world.cells[n]!.controller === enemy)) continue;
      const step = this.stepToward(b, a, threatened);
      if (step !== null && b.issue(this.side, { t: 'move', army: a.id, to: step })) {
        this.lastMove.set(a.id, b.tick);
        return;
      }
    }
  }

  private stepToward(b: Battle, a: Army, goals: Set<number>): number | null {
    const prev = new Map<number, number>([[a.hex, -1]]);
    const queue = [a.hex];
    while (queue.length) {
      const id = queue.shift()!;
      if (id !== a.hex && goals.has(id)) {
        let cur = id;
        while (prev.get(cur) !== a.hex) cur = prev.get(cur)!;
        return cur;
      }
      for (const n of b.world.neighbors[id]!) {
        if (n < 0 || prev.has(n)) continue;
        const c = b.world.cells[n]!;
        if (!isPassable(c) || c.controller !== this.side) continue;
        prev.set(n, id);
        queue.push(n);
      }
    }
    return null;
  }
}
