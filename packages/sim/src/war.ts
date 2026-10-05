// War score, offensive stars, peace demands and treaty (canon §9.12–9.14, §10.1).

import { coreOf, officialValue } from './map.js';
import { pockets } from './topology.js';
import { PLAYER, isPassable, type StateId, type World } from './types.js';

export interface War {
  enemy: StateId;
  /** Player's war goal hex (+10 while held). */
  goal: number;
  /** AI's goal: the most valuable player border hex outside the core. */
  aiGoal: number;
  enemyValue0: number;
  playerValue0: number;
  /** Battle points, clamped to ±10 (★ +1, ★★ +2, ★★★ +3, no capture −1). */
  battles: number;
  offensives: number;
}

export interface WarScore {
  score: number;
  occupation: number;
  losses: number;
  battles: number;
  goal: number;
  capital: number;
  /** Контроль фронта, % */
  control: number;
}

const round1 = (x: number): number => Math.round(x * 10) / 10;

export function recommendGoals(w: World, enemy: StateId, n = 3): number[] {
  const core = coreOf(w, enemy);
  const border = w.cells.filter(
    (c) =>
      c.owner === enemy &&
      isPassable(c) &&
      !core.has(c.id) &&
      w.neighbors[c.id]!.some((id) => id >= 0 && w.cells[id]!.controller === PLAYER),
  );
  return border.sort((a, b) => b.value - a.value || a.id - b.id).slice(0, n).map((c) => c.id);
}

export function declareWar(w: World, enemy: StateId, goal: number): War {
  const playerCore = coreOf(w, PLAYER);
  const aiGoal =
    w.cells
      .filter(
        (c) =>
          c.owner === PLAYER &&
          !playerCore.has(c.id) &&
          w.neighbors[c.id]!.some((id) => id >= 0 && w.cells[id]!.owner === enemy),
      )
      .sort((a, b) => b.value - a.value || a.id - b.id)[0]?.id ?? -1;
  return {
    enemy,
    goal,
    aiGoal,
    enemyValue0: officialValue(w, enemy),
    playerValue0: officialValue(w, PLAYER),
    battles: 0,
    offensives: 0,
  };
}

/** Enemy hexes inside the player's pockets count as occupation (canon §9.7). */
export function enemyPocketHexes(w: World, war: War): number[] {
  return pockets(w, war.enemy, PLAYER).flat();
}

export function warScore(w: World, war: War): WarScore {
  let occ = 0;
  let lost = 0;
  const pocketSet = new Set(enemyPocketHexes(w, war));
  for (const c of w.cells) {
    if (!isPassable(c)) continue;
    if (c.owner === war.enemy && (c.controller === PLAYER || pocketSet.has(c.id))) occ += c.value;
    if (c.owner === PLAYER && c.controller === war.enemy) lost += c.value;
  }
  const occupation = round1((occ * 100) / Math.max(1, war.enemyValue0));
  const losses = round1((lost * 100) / Math.max(1, war.playerValue0));
  let goal = 0;
  if (war.goal >= 0 && w.cells[war.goal]!.controller === PLAYER) goal += 10;
  if (war.aiGoal >= 0 && w.cells[war.aiGoal]!.controller === war.enemy) goal -= 10;
  const enemyCap = w.states[war.enemy]!.capitalId;
  const capital = enemyCap >= 0 && w.cells[enemyCap]!.controller === PLAYER ? 20 : 0;
  const raw = occupation - losses + war.battles + goal + capital;
  const score = round1(Math.max(-100, Math.min(100, raw)));
  return { score, occupation, losses, battles: war.battles, goal, capital, control: Math.round(50 + score / 2) };
}

export function offensiveStars(captured: number[], flagHex: number, routed: number): number {
  if (captured.length === 0) return 0;
  if (!captured.includes(flagHex)) return 1;
  return routed === 0 ? 3 : 2;
}

export function recordOffensive(war: War, stars: number): void {
  const pts = stars === 0 ? -1 : stars;
  war.battles = Math.max(-10, Math.min(10, war.battles + pts));
  war.offensives++;
}

// ---------- peace ----------

export type DemandKind = 'annex' | 'pocket' | 'contribution' | 'reparations';

export interface Demand {
  id: string;
  kind: DemandKind;
  hexes: number[];
  cost: number;
  label: string;
}

export function hexPeaceCost(w: World, war: War, hex: number): number {
  return round1((w.cells[hex]!.value * 100) / Math.max(1, war.enemyValue0));
}

export function availableDemands(w: World, war: War): Demand[] {
  const out: Demand[] = [];
  const core = coreOf(w, war.enemy); // decision 19: the enemy core is never demanded
  const pocketGroups = pockets(w, war.enemy, PLAYER).map((g) => g.filter((id) => !core.has(id))).filter((g) => g.length);
  const inPocket = new Set(pocketGroups.flat());
  pocketGroups.forEach((g, i) => {
    const cost = round1(0.5 * g.reduce((s, id) => s + hexPeaceCost(w, war, id), 0));
    out.push({ id: `pocket:${i}`, kind: 'pocket', hexes: g, cost, label: `Котёл целиком (${g.length} гекс.)` });
  });
  for (const c of w.cells) {
    if (c.owner !== war.enemy || c.controller !== PLAYER || core.has(c.id) || inPocket.has(c.id)) continue;
    out.push({ id: `annex:${c.id}`, kind: 'annex', hexes: [c.id], cost: hexPeaceCost(w, war, c.id), label: c.name ?? 'Гекс' });
  }
  for (let i = 1; i <= 3; i++) out.push({ id: `contribution:${i}`, kind: 'contribution', hexes: [], cost: 5, label: 'Контрибуция (4 ч золота)' });
  out.push({ id: 'reparations', kind: 'reparations', hexes: [], cost: 5, label: 'Репарации (10% производства, 24 ч)' });
  return out;
}

/** «Самое ценное за доступные очки»: pockets first, then the goal, then hexes by value, then gold. */
export function recommendPackage(w: World, war: War, demands: Demand[], budget: number): Demand[] {
  const value = (d: Demand): number => d.hexes.reduce((s, id) => s + w.cells[id]!.value, 0);
  const order = [...demands].sort((a, b) => {
    const rank = (d: Demand): number => (d.kind === 'pocket' ? 0 : d.kind === 'annex' ? (d.hexes[0] === war.goal ? 1 : 2) : 3);
    return rank(a) - rank(b) || value(b) - value(a) || a.id.localeCompare(b.id);
  });
  const chosen: Demand[] = [];
  let left = budget;
  for (const d of order) {
    if (d.cost <= left + 1e-9) {
      chosen.push(d);
      left = round1(left - d.cost);
    }
  }
  return chosen;
}

export interface TreatyResult {
  annexed: number[];
  returned: number[];
  goldPacks: number;
  reparations: boolean;
}

/** Applies a victorious treaty for the player. Unclaimed occupations return to their owners. */
export function applyTreaty(w: World, war: War, chosen: Demand[]): TreatyResult {
  const annex = new Set(chosen.flatMap((d) => d.hexes));
  const returned: number[] = [];
  for (const c of w.cells) {
    if (!isPassable(c)) continue;
    if (annex.has(c.id)) {
      c.owner = PLAYER;
      c.controller = PLAYER;
      c.fort = 0;
    } else if (c.controller !== c.owner && (c.owner === war.enemy || c.owner === PLAYER)) {
      c.controller = c.owner;
      returned.push(c.id);
    }
  }
  return {
    annexed: [...annex].sort((a, b) => a - b),
    returned,
    goldPacks: chosen.filter((d) => d.kind === 'contribution').length,
    reparations: chosen.some((d) => d.kind === 'reparations'),
  };
}

/** White peace: every occupation returns. */
export function whitePeace(w: World): void {
  for (const c of w.cells) if (isPassable(c) && c.controller !== c.owner) c.controller = c.owner;
}
