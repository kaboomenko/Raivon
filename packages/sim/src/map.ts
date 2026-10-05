// Chapter I «Долина» map generator (canon §12.1): 50 land hexes —
// player 7 (core), Кремнёвые Бароны (Wolf) 14, Вольные Хутора (Fox) 10, wild 19.
// Deterministic from seed; retries seeds until the validator passes.

import { DIRS, disk, hexDistance, hexKey, type Axial } from './hex.js';
import { Rng } from './rng.js';
import {
  KIND_VALUE,
  NOBODY,
  PLAYER,
  isPassable,
  type Cell,
  type HexKind,
  type StateInfo,
  type World,
} from './types.js';

export const BARONS = 2;
export const HAMLETS = 3;

const RADIUS = 4;
const PLAYER_CAP: Axial = { q: 0, r: 3 };
const BARONS_CAP: Axial = { q: 3, r: -1 };
const HAMLETS_CAP: Axial = { q: -3, r: 1 };
const IMPASSABLE = 11;
const BARONS_SIZE = 14;
const HAMLETS_SIZE = 10;

export function makeStates(): StateInfo[] {
  return [
    { id: NOBODY, name: 'Дикие земли', color: 0xb9b2a3, archetype: 'player', capitalId: -1, devLevel: 0 },
    { id: PLAYER, name: 'Ваша держава', color: 0x2e6bff, archetype: 'player', capitalId: -1, devLevel: 1 },
    { id: BARONS, name: 'Кремнёвые Бароны', color: 0xe0393e, archetype: 'wolf', capitalId: -1, devLevel: 1 },
    { id: HAMLETS, name: 'Вольные Хутора', color: 0x3fa34d, archetype: 'fox', capitalId: -1, devLevel: 1 },
  ];
}

function buildTopology(cells: Cell[]): { neighbors: number[][]; byKey: Map<string, number> } {
  const byKey = new Map<string, number>();
  cells.forEach((c) => byKey.set(hexKey(c.q, c.r), c.id));
  const neighbors = cells.map((c) => DIRS.map((d) => byKey.get(hexKey(c.q + d.q, c.r + d.r)) ?? -1));
  return { neighbors, byKey };
}

export function generateChapterOne(seed: number): World {
  for (let attempt = 0; attempt < 200; attempt++) {
    const w = tryGenerate(seed + attempt * 7919);
    if (validateChapterOne(w).length === 0) return w;
  }
  throw new Error('map generator: no valid map found');
}

function tryGenerate(seed: number): World {
  const rng = new Rng(seed);
  const coords = disk(RADIUS);
  const cells: Cell[] = coords.map((a, id) => ({
    id,
    q: a.q,
    r: a.r,
    terrain: 'plain',
    kind: 'plain',
    value: 1,
    owner: NOBODY,
    controller: NOBODY,
    fort: 0,
  }));
  const { neighbors, byKey } = buildTopology(cells);
  const idOf = (a: Axial): number => byKey.get(hexKey(a.q, a.r))!;
  const coreOf = (cap: Axial): number[] => [idOf(cap), ...neighbors[idOf(cap)]!.filter((n) => n >= 0)];

  const states = makeStates();
  const reserved = new Set<number>([...coreOf(PLAYER_CAP), ...coreOf(BARONS_CAP), ...coreOf(HAMLETS_CAP)]);

  // 1. Impassable terrain on the rim, away from capitals' cores.
  const rim = cells.filter((c) => hexDistance(c, { q: 0, r: 0 }) >= RADIUS - 1 && !reserved.has(c.id));
  rng.shuffle(rim);
  for (const c of rim.slice(0, IMPASSABLE)) c.terrain = rng.int(3) === 0 ? 'mountain' : 'water';

  // 2. Player core: capital + 6 neighbours.
  for (const id of coreOf(PLAYER_CAP)) setOwner(cells[id]!, PLAYER);

  // 3. Grow AI states by BFS from their capitals.
  grow(cells, neighbors, idOf(HAMLETS_CAP), HAMLETS, HAMLETS_SIZE, rng, (c) => hexDistance(c, HAMLETS_CAP) * 10);
  // Barons are biased toward the player so the first war has a front.
  grow(cells, neighbors, idOf(BARONS_CAP), BARONS, BARONS_SIZE, rng, (c) => hexDistance(c, BARONS_CAP) * 10 + hexDistance(c, PLAYER_CAP) * 6);

  // 4. Kinds and terrain.
  const setKind = (id: number, kind: HexKind, name?: string): void => {
    const c = cells[id]!;
    c.kind = kind;
    c.value = KIND_VALUE[kind];
    if (name) c.name = name;
  };
  setKind(idOf(PLAYER_CAP), 'capital', 'Столица');
  setKind(idOf(BARONS_CAP), 'capital', 'Кремнёвый замок');
  setKind(idOf(HAMLETS_CAP), 'capital', 'Хуторской двор');
  states[PLAYER]!.capitalId = idOf(PLAYER_CAP);
  states[BARONS]!.capitalId = idOf(BARONS_CAP);
  states[HAMLETS]!.capitalId = idOf(HAMLETS_CAP);

  const free = (owner: number): Cell[] =>
    rng.shuffle(cells.filter((c) => c.owner === owner && c.kind === 'plain' && isPassable(c)));
  const playerFree = free(PLAYER);
  setKind(playerFree[0]!.id, 'farm', 'Мельничный луг');

  // Barons: a frontier mine (war goal bait), a city and a farm, preferring hexes near the player.
  const baronsFree = free(BARONS).sort((a, b) => hexDistance(a, PLAYER_CAP) - hexDistance(b, PLAYER_CAP));
  setKind(baronsFree[0]!.id, 'mine', 'Кремнёвый карьер');
  setKind(baronsFree[2]!.id, 'city', 'Ржавый узел');
  setKind(baronsFree[baronsFree.length - 1]!.id, 'farm', 'Баронские поля');
  const hamletsFree = free(HAMLETS).sort((a, b) => hexDistance(a, PLAYER_CAP) - hexDistance(b, PLAYER_CAP));
  setKind(hamletsFree[0]!.id, 'mine', 'Медная шахта');
  setKind(hamletsFree[1]!.id, 'farm', 'Хуторские нивы');
  const wildFree = free(NOBODY);
  if (wildFree[0]) setKind(wildFree[0].id, 'farm', 'Заброшенная мельница');
  if (wildFree[1]) setKind(wildFree[1].id, 'mine', 'Старая штольня');

  for (const c of cells) {
    if (!isPassable(c) || c.kind !== 'plain' || reserved.has(c.id)) continue;
    const roll = rng.int(100);
    if (roll < 14) c.terrain = 'forest';
    else if (roll < 24) c.terrain = 'hills';
  }

  return { seed, radius: RADIUS, cells, neighbors, byKey, states };
}

function setOwner(c: Cell, s: number): void {
  c.owner = s;
  c.controller = s;
}

function grow(
  cells: Cell[],
  neighbors: number[][],
  start: number,
  state: number,
  size: number,
  rng: Rng,
  score: (c: Cell) => number,
): void {
  const owned = new Set<number>([start]);
  setOwner(cells[start]!, state);
  while (owned.size < size) {
    const frontier: Cell[] = [];
    for (const id of owned) {
      for (const n of neighbors[id]!) {
        if (n < 0 || owned.has(n)) continue;
        const c = cells[n]!;
        if (c.owner !== NOBODY || !isPassable(c)) continue;
        if (!frontier.includes(c)) frontier.push(c);
      }
    }
    if (frontier.length === 0) return;
    let best = Infinity;
    let picks: Cell[] = [];
    for (const c of frontier) {
      const s = score(c);
      if (s < best) {
        best = s;
        picks = [c];
      } else if (s === best) picks.push(c);
    }
    const pick = rng.pick(picks);
    owned.add(pick.id);
    setOwner(pick, state);
  }
}

/** Returns a list of problems; empty = valid. */
export function validateChapterOne(w: World): string[] {
  const problems: string[] = [];
  const land = w.cells.filter(isPassable);
  if (land.length !== 50) problems.push(`land hexes ${land.length} != 50`);
  const count = (s: number): number => land.filter((c) => c.owner === s).length;
  if (count(PLAYER) !== 7) problems.push('player size != 7');
  if (count(BARONS) !== BARONS_SIZE) problems.push('barons size');
  if (count(HAMLETS) !== HAMLETS_SIZE) problems.push('hamlets size');
  // Front with Barons: at least 3 shared edges with the player.
  let shared = 0;
  for (const c of land) {
    if (c.owner !== PLAYER) continue;
    for (const n of w.neighbors[c.id]!) if (n >= 0 && w.cells[n]!.owner === BARONS) shared++;
  }
  if (shared < 3) problems.push(`player-barons border ${shared} < 3`);
  // Every state is connected.
  for (const s of [PLAYER, BARONS, HAMLETS]) {
    if (!connected(w, land.filter((c) => c.owner === s).map((c) => c.id))) problems.push(`state ${s} disconnected`);
  }
  // All land is mutually reachable (no isolated islands).
  if (!connected(w, land.map((c) => c.id))) problems.push('land disconnected');
  return problems;
}

function connected(w: World, ids: number[]): boolean {
  if (ids.length === 0) return true;
  const set = new Set(ids);
  const seen = new Set<number>([ids[0]!]);
  const q = [ids[0]!];
  while (q.length) {
    const id = q.pop()!;
    for (const n of w.neighbors[id]!) {
      if (n >= 0 && set.has(n) && !seen.has(n)) {
        seen.add(n);
        q.push(n);
      }
    }
  }
  return seen.size === set.size;
}

/** Ядро: capital + 6 neighbours that are officially owned by the same state (canon §3.1). */
export function coreOf(w: World, state: number): Set<number> {
  const cap = w.states[state]?.capitalId ?? -1;
  const out = new Set<number>();
  if (cap < 0 || w.cells[cap]!.owner !== state) return out;
  out.add(cap);
  for (const n of w.neighbors[cap]!) if (n >= 0 && w.cells[n]!.owner === state) out.add(n);
  return out;
}

export function officialValue(w: World, state: number): number {
  let v = 0;
  for (const c of w.cells) if (c.owner === state && isPassable(c)) v += c.value;
  return v;
}

export function cloneWorld(w: World): World {
  return {
    ...w,
    cells: w.cells.map((c) => ({ ...c })),
    states: w.states.map((s) => ({ ...s })),
  };
}
