// Starting armies for the chapter I prototype (canon §8.1, 11_balance_numbers.md §15).

import type { Army } from './battle.js';
import { BARONS } from './map.js';
import { FX, PLAYER, STRENGTH_MULT, isPassable, type World } from './types.js';

const INFANTRY_BASE = 25; // per squad at DL1 (canon §8.1, C36)

export function infantryArmy(id: number, side: number, hex: number, slots: number, devLevel: number): Army {
  const max = Math.round(INFANTRY_BASE * slots * (STRENGTH_MULT[devLevel] ?? 1) * FX);
  return { id, side, hex, str: max, maxStr: max, infantry: 1000, hold: false, move: null, startStr: max, attrition: 0, routed: false };
}

/** Player: 2 armies × 3 slots at the front. Barons (Wolf, +1 army): 3 × 3. */
export function startingArmies(w: World): Army[] {
  const front = (side: number, enemy: number): number[] =>
    w.cells
      .filter((c) => c.owner === side && isPassable(c) && w.neighbors[c.id]!.some((n) => n >= 0 && w.cells[n]!.owner === enemy))
      .sort((a, b) => b.value - a.value || a.id - b.id)
      .map((c) => c.id);
  const pf = front(PLAYER, BARONS);
  const bf = front(BARONS, PLAYER);
  const armies: Army[] = [];
  armies.push(infantryArmy(1, PLAYER, pf[0]!, 3, 1));
  armies.push(infantryArmy(2, PLAYER, pf[1] ?? w.states[PLAYER]!.capitalId, 3, 1));
  const baronsDl = w.states[BARONS]!.devLevel;
  // One Barons army holds the front; the others start in the rear and the AI pulls them toward threats.
  const cap = w.states[BARONS]!.capitalId;
  const rear = w.cells
    .filter((c) => c.owner === BARONS && isPassable(c) && c.id !== cap && !bf.includes(c.id))
    .sort((a, b) => b.value - a.value || a.id - b.id)
    .map((c) => c.id);
  armies.push(infantryArmy(101, BARONS, bf[0]!, 3, baronsDl));
  armies.push(infantryArmy(102, BARONS, rear[0] ?? cap, 3, baronsDl));
  armies.push(infantryArmy(103, BARONS, cap, 3, baronsDl));
  return armies;
}
