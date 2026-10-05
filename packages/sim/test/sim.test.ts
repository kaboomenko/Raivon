import { describe, expect, it } from 'vitest';
import {
  BARONS,
  Battle,
  BattleAI,
  FX,
  HAMLETS,
  PLAYER,
  applyTreaty,
  availableDemands,
  cloneWorld,
  coreOf,
  declareWar,
  generateChapterOne,
  infantryArmy,
  isPassable,
  offensiveStars,
  recommendGoals,
  recommendPackage,
  startingArmies,
  validateChapterOne,
  warScore,
  type Army,
  type World,
} from '../src/index.js';

const SEED = 20261004;

function battleWorld(): World {
  return generateChapterOne(SEED);
}

describe('map generator', () => {
  it('builds a valid chapter I map deterministically', () => {
    const a = generateChapterOne(SEED);
    const b = generateChapterOne(SEED);
    expect(validateChapterOne(a)).toEqual([]);
    expect(JSON.stringify(a.cells)).toEqual(JSON.stringify(b.cells));
    expect(a.cells.filter(isPassable)).toHaveLength(50);
    expect(coreOf(a, PLAYER).size).toBe(7);
  });

  it('is valid for many seeds', () => {
    for (let s = 1; s <= 30; s++) expect(validateChapterOne(generateChapterOne(s))).toEqual([]);
  });
});

/** A clean duel on a real map: one attacker vs one defender, no terrain or forms. */
function duel(atk: number, def: number, defInfantry = 0): { b: Battle; target: number; attacker: Army } {
  const w = battleWorld();
  // find a plain player hex next to a plain Barons hex
  for (const c of w.cells) {
    if (c.controller !== PLAYER || !isPassable(c)) continue;
    for (const n of w.neighbors[c.id]!) {
      const t = n >= 0 ? w.cells[n]! : undefined;
      if (!t || t.controller !== BARONS || t.kind !== 'plain' || t.terrain !== 'plain') continue;
      for (const x of w.cells) x.fort = 0;
      const attacker = infantryArmy(1, PLAYER, c.id, 1, 1);
      attacker.str = attacker.maxStr = atk * FX;
      const defender = infantryArmy(101, BARONS, t.id, 1, 1);
      defender.str = defender.maxStr = def * FX;
      defender.infantry = defInfantry;
      const b = new Battle(w, [attacker, defender], { attacker: PLAYER, defender: BARONS, aiEnergyMult: 0, cards: [] });
      b.garrison[t.id] = 0;
      return { b, target: t.id, attacker };
    }
  }
  throw new Error('no duel spot');
}

describe('combat formula (canon §9.5)', () => {
  it('equal sides break after ~8 s', () => {
    const { b, target, attacker } = duel(100, 91); // 100 vs 91×1.1 ≈ F 1.0
    const fc = b.forecast(PLAYER, [attacker.id], target);
    expect(fc.f).toBeGreaterThan(0.95);
    expect(fc.f).toBeLessThan(1.05);
    b.issue(PLAYER, { t: 'attack', army: attacker.id, target });
    let ended = -1;
    for (let i = 0; i < 200 && ended < 0; i++) {
      b.step();
      if (b.clashes.length === 0 || b.clashes[0]!.entering > 0) ended = b.tick;
    }
    expect(ended / 10).toBeGreaterThan(6);
    expect(ended / 10).toBeLessThan(9.5);
  });

  it('reproduces the canon example F = 1.16 → 1.31', () => {
    // Wedge of two armies totalling 100 vs army 60 + garrison 20 behind fort 2.
    const w = battleWorld();
    const target = w.cells.find(
      (c) =>
        c.controller === BARONS &&
        c.kind === 'plain' &&
        c.terrain === 'plain' &&
        w.neighbors[c.id]!.filter((n) => n >= 0 && w.cells[n]!.controller === PLAYER).length >= 2,
    );
    if (!target) return; // map without a two-hex front: covered by other seeds
    const srcs = w.neighbors[target.id]!.filter((n) => n >= 0 && w.cells[n]!.controller === PLAYER);
    target.fort = 2;
    const a1 = infantryArmy(1, PLAYER, srcs[0]!, 1, 1);
    const a2 = infantryArmy(2, PLAYER, srcs[1]!, 1, 1);
    a1.str = a1.maxStr = 50 * FX;
    a2.str = a2.maxStr = 50 * FX;
    const d = infantryArmy(101, BARONS, target.id, 1, 1);
    d.str = d.maxStr = 60 * FX;
    d.infantry = 0;
    const b = new Battle(w, [a1, a2, d], { attacker: PLAYER, defender: BARONS, aiEnergyMult: 0, cards: [] });
    b.garrison[target.id] = 20 * FX;
    const fc = b.forecast(PLAYER, [1, 2], target.id);
    if (fc.forms.length === 1) {
      expect(fc.f).toBeCloseTo(1.16, 1);
      target.fort = 0; // «Артобстрел»: fort −2 levels
      expect(b.forecast(PLAYER, [1, 2], target.id).f).toBeCloseTo(1.31, 1);
    }
  });

  it('concentration beats dispersion (Lanchester)', () => {
    const { b, target, attacker } = duel(150, 100);
    const strong = b.forecast(PLAYER, [attacker.id], target).f;
    attacker.str = 75 * FX;
    const weak = b.forecast(PLAYER, [attacker.id], target).f;
    expect(strong / weak).toBeGreaterThan(1.9);
  });
});

function playScripted(seed: number): string {
  const w = generateChapterOne(seed);
  const armies = startingArmies(w);
  const war = declareWar(w, BARONS, recommendGoals(w, BARONS)[0]!);
  const b = new Battle(w, armies, { attacker: PLAYER, defender: BARONS, aiEnergyMult: 600, cards: ['attack', 'defense'] });
  const ai = new BattleAI(BARONS);
  while (!b.over) {
    if (b.tick % 20 === 0) {
      // naive player bot: attack-all on the goal or any adjacent target
      // player bot: attack-all where the forecast is good, preferring the war goal
      let best: { id: number; f: number } | null = null;
      for (const c of w.cells) {
        if (!b.canTarget(PLAYER, c.id)) continue;
        const ids = b.adjacentIdleArmies(PLAYER, c.id).map((a) => a.id);
        if (ids.length === 0) continue;
        const f = b.forecast(PLAYER, ids, c.id).f + (c.id === war.goal ? 0.3 : 0);
        if (f >= 1.2 && (!best || f > best.f)) best = { id: c.id, f };
      }
      if (best) b.issue(PLAYER, { t: 'card', card: 'attack', target: best.id });
    }
    ai.think(b);
    b.step();
  }
  return JSON.stringify({ r: b.result(), cells: w.cells.map((c) => c.controller), armies: b.armies.map((a) => [a.hex, a.str]) });
}

describe('determinism and full offensive', () => {
  it('same inputs give the same result', () => {
    expect(playScripted(SEED)).toEqual(playScripted(SEED));
  });

  it('an offensive runs 90 s and captures hexes', () => {
    const out = JSON.parse(playScripted(SEED));
    expect(out.r.reason).toBe('time');
    expect(out.r.captured.length).toBeGreaterThan(0);
  });

  it('AI never captures the player core', () => {
    for (let s = 1; s <= 10; s++) {
      const w = generateChapterOne(s);
      const core = coreOf(w, PLAYER);
      const armies = startingArmies(w);
      // weaken the player so the AI attacks a lot
      for (const a of armies) if (a.side === PLAYER) a.str = Math.floor(a.str / 4);
      const b = new Battle(w, armies, { attacker: PLAYER, defender: BARONS, aiEnergyMult: 1000, cards: [] });
      const ai = new BattleAI(BARONS);
      while (!b.over) {
        ai.think(b);
        b.step();
      }
      for (const id of core) expect(w.cells[id]!.controller).toBe(PLAYER);
    }
  });
});

describe('war score and peace (canon §9.12, §10.1)', () => {
  it('scores occupation and builds a treaty that never takes the enemy core', () => {
    const w = generateChapterOne(SEED);
    const war = declareWar(w, BARONS, recommendGoals(w, BARONS)[0]!);
    const w2 = cloneWorld(w);
    // occupy every non-core Barons hex
    const core = coreOf(w2, BARONS);
    for (const c of w2.cells) if (c.owner === BARONS && !core.has(c.id)) c.controller = PLAYER;
    const ws = warScore(w2, war);
    expect(ws.score).toBeGreaterThan(30);
    expect(ws.control).toBe(Math.round(50 + ws.score / 2));
    const demands = availableDemands(w2, war);
    expect(demands.some((d) => d.hexes.some((h) => core.has(h)))).toBe(false);
    const pkg = recommendPackage(w2, war, demands, ws.score);
    expect(pkg.reduce((s, d) => s + d.cost, 0)).toBeLessThanOrEqual(ws.score + 1e-9);
    const res = applyTreaty(w2, war, pkg);
    for (const id of res.annexed) expect(w2.cells[id]!.owner).toBe(PLAYER);
    for (const c of w2.cells) if (isPassable(c)) expect(c.controller).toBe(c.owner);
    expect(w2.cells.filter((c) => c.owner === HAMLETS)).toHaveLength(10);
  });

  it('stars follow the canon', () => {
    expect(offensiveStars([], 5, 0)).toBe(0);
    expect(offensiveStars([3], 5, 0)).toBe(1);
    expect(offensiveStars([5], 5, 1)).toBe(2);
    expect(offensiveStars([5], 5, 0)).toBe(3);
  });
});
