// Core world types. Strength is fixed-point: 1 unit of Strength = 1000 (canon §16.1, ×1000).

export const FX = 1000;

export type StateId = number; // 0 = nobody (wild land / impassable)
export const NOBODY: StateId = 0;
export const PLAYER: StateId = 1;

export type Terrain = 'plain' | 'forest' | 'hills' | 'water' | 'mountain';
export type HexKind = 'plain' | 'farm' | 'mine' | 'city' | 'capital' | 'military_base' | 'port';

export interface Cell {
  id: number;
  q: number;
  r: number;
  terrain: Terrain;
  kind: HexKind;
  /** hex_value 1..10 (canon §5.1) */
  value: number;
  /** Official owner — changes only by treaty, colonization or swap. */
  owner: StateId;
  /** Actual controller — changes during war (occupation). */
  controller: StateId;
  /** bld_fort level 0..10 */
  fort: number;
  /** Display name for notable hexes */
  name?: string;
}

export type Archetype = 'wolf' | 'fox' | 'turtle' | 'raven' | 'owl';

export interface StateInfo {
  id: StateId;
  name: string;
  /** Heraldic fill color (0xRRGGBB) */
  color: number;
  archetype: Archetype | 'player';
  capitalId: number;
  devLevel: number;
}

export interface World {
  seed: number;
  radius: number;
  cells: Cell[];
  /** neighbors[id][dir] = neighbor cell id or -1 (off-map) */
  neighbors: number[][];
  byKey: Map<string, number>;
  states: StateInfo[];
}

export const isPassable = (c: Cell): boolean => c.terrain !== 'water' && c.terrain !== 'mountain';

/** M_силы by dev level (canon §6.2) */
export const STRENGTH_MULT: readonly number[] = [0, 1.0, 1.25, 1.55, 1.9, 2.35, 2.9, 3.6, 4.4, 5.4, 6.6];

export const KIND_VALUE: Record<HexKind, number> = {
  plain: 1,
  farm: 2,
  mine: 2,
  port: 3,
  military_base: 3,
  city: 4,
  capital: 10,
};
