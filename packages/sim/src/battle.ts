// Real-time offensive simulation (canon §9.2–9.9, docs/gdd/03_war_combat.md).
// 10 Hz, integer fixed point. Strength ×1000 (FX), multipliers in permille, energy ×300.

import { coreOf } from './map.js';
import { supplied } from './topology.js';
import { FX, STRENGTH_MULT, isPassable, type StateId, type World } from './types.js';

export const TICKS_PER_SEC = 10;
export const OFFENSIVE_TICKS = 90 * TICKS_PER_SEC;
export const FINAL_RUSH_TICKS = 20 * TICKS_PER_SEC;
export const ENERGY_UNIT = 300; // 1 energy point
const ENERGY_MAX = 10 * ENERGY_UNIT;
const LOSS_PERMILLE = 15; // 0.015 × enemy Might per tick
const BREAK_PERMILLE = 300; // break below 30% of clash-start strength
const ENTER_TICKS = 15;
const ENTER_TICKS_CORRIDOR = 8;
const MOVE_TICKS = 15;
const CARD_COOLDOWN = 10 * TICKS_PER_SEC;

export type CardId = 'attack' | 'defense' | 'encircle' | 'breakthrough' | 'airstrike';

export const CARDS: Record<CardId, { cost: number; name: string; target: 'enemy' | 'own' }> = {
  attack: { cost: 2, name: 'Атака', target: 'enemy' },
  breakthrough: { cost: 3, name: 'Прорыв', target: 'enemy' },
  airstrike: { cost: 4, name: 'Авиаудар', target: 'enemy' },
  encircle: { cost: 3, name: 'Окружение', target: 'enemy' },
  defense: { cost: 2, name: 'Оборона', target: 'own' },
};

export interface Army {
  id: number;
  side: StateId;
  hex: number;
  str: number;
  maxStr: number;
  /** Share of infantry in ‰ — drives «Стойкость» (+50% def at ≥50% share). */
  infantry: number;
  hold: boolean;
  move: { from: number; to: number; left: number } | null;
  /** Strength at battle start, caps out-of-supply attrition at −40%. */
  startStr: number;
  attrition: number;
  routed: boolean;
}

export interface Clash {
  id: number;
  target: number;
  side: StateId;
  attackers: number[];
  defender: number | null;
  startAtk: number;
  startDef: number;
  /** ticks left until the attacker enters after the defender broke; 0 = fighting */
  entering: number;
  corridor: boolean;
  breakthrough: { army: number; dir: number; steps: number } | null;
}

export type Command =
  | { t: 'attack'; army: number; target: number }
  | { t: 'card'; card: CardId; target: number }
  | { t: 'move'; army: number; to: number }
  | { t: 'hold'; army: number }
  | { t: 'retreat' };

interface Effect {
  kind: 'defense' | 'encircle' | 'airFort' | 'weak';
  hex: number;
  left: number;
}

export type BattleEvent =
  | { type: 'clash'; tick: number; clash: number; target: number; side: StateId }
  | { type: 'capture'; tick: number; hex: number; side: StateId; from: StateId }
  | { type: 'repelled'; tick: number; hex: number; side: StateId }
  | { type: 'routed'; tick: number; army: number }
  | { type: 'retreat'; tick: number; army: number; to: number }
  | { type: 'card'; tick: number; side: StateId; card: CardId; hex: number }
  | { type: 'end'; tick: number; reason: 'time' | 'retreat' | 'wiped' };

export interface Forecast {
  f: number;
  atkMight: number;
  defMight: number;
  forms: string[];
}

export interface BattleResult {
  captured: number[];
  lost: number[];
  routedPlayerArmies: number;
  reason: 'time' | 'retreat' | 'wiped';
}

export interface BattleOptions {
  attacker: StateId; // the player side
  defender: StateId;
  aiEnergyMult: number; // ×1000 (600 = ×0.6 in chapter I)
  cards: CardId[];
}

export class Battle {
  readonly world: World;
  readonly armies: Army[];
  readonly opts: BattleOptions;
  tick = 0;
  over = false;
  endReason: BattleResult['reason'] = 'time';
  readonly garrison: number[];
  readonly clashes: Clash[] = [];
  readonly events: BattleEvent[] = [];
  readonly log: { tick: number; side: StateId; cmd: Command }[] = [];
  readonly energy = new Map<StateId, number>();
  readonly cooldown = new Map<string, number>();
  lastStand: StateId | null = null;
  private effects: Effect[] = [];
  private queue: { side: StateId; cmd: Command }[] = [];
  private supplyCache = new Map<StateId, Set<number>>();
  private nextClashId = 1;
  private captured = new Set<number>();
  private lost = new Set<number>();
  private routedPlayer = 0;
  private protectedCore: Set<number>;

  constructor(world: World, armies: Army[], opts: BattleOptions) {
    this.world = world;
    this.armies = armies;
    this.opts = opts;
    this.garrison = world.cells.map((c) => (isPassable(c) ? this.garrisonFor(c.id, c.controller) : 0));
    this.energy.set(opts.attacker, 5 * ENERGY_UNIT);
    this.energy.set(opts.defender, Math.floor((5 * opts.aiEnergyMult) / 1000) * ENERGY_UNIT);
    for (const a of armies) {
      a.startStr = a.str;
      a.attrition = 0;
      a.move = null;
    }
    // The AI never targets the player's core in any battle (canon §9.11, decision 19).
    this.protectedCore = coreOf(world, opts.attacker);
  }

  // ---------- helpers ----------

  enemyOf(side: StateId): StateId {
    return side === this.opts.attacker ? this.opts.defender : this.opts.attacker;
  }

  garrisonFor(hex: number, controller: StateId): number {
    const c = this.world.cells[hex]!;
    if (controller !== this.opts.attacker && controller !== this.opts.defender) {
      // neutral/wild hexes are not part of the war
      return 0;
    }
    const dl = this.world.states[controller]?.devLevel ?? 1;
    const base = Math.round(10 * c.value * (STRENGTH_MULT[dl] ?? 1) * FX);
    return c.owner === controller ? base : Math.floor(base / 2);
  }

  armyAt(hex: number, side: StateId): Army | undefined {
    return this.armies.find((a) => a.hex === hex && a.side === side && !a.routed && a.str > 0 && !a.move);
  }

  armyById(id: number): Army | undefined {
    return this.armies.find((a) => a.id === id);
  }

  isSupplied(hex: number, side: StateId): boolean {
    if (this.effects.some((e) => e.kind === 'encircle' && e.hex === hex)) return false;
    let s = this.supplyCache.get(side);
    if (!s) {
      s = supplied(this.world, side);
      this.supplyCache.set(side, s);
    }
    return s.has(hex);
  }

  energyPoints(side: StateId): number {
    return Math.floor((this.energy.get(side) ?? 0) / ENERGY_UNIT);
  }

  secondsLeft(): number {
    return Math.max(0, Math.ceil((OFFENSIVE_TICKS - this.tick) / TICKS_PER_SEC));
  }

  attacking(army: Army): Clash | undefined {
    return this.clashes.find((c) => c.attackers.includes(army.id));
  }

  /** Is `side` allowed to attack `target` right now? */
  canTarget(side: StateId, target: number): boolean {
    const c = this.world.cells[target];
    if (!c || !isPassable(c)) return false;
    if (c.controller !== this.enemyOf(side)) return false;
    if (side !== this.opts.attacker && this.protectedCore.has(target)) return false;
    return true;
  }

  adjacentIdleArmies(side: StateId, target: number): Army[] {
    const ns = this.world.neighbors[target]!;
    return this.armies
      .filter((a) => a.side === side && !a.routed && a.str > 0 && !a.move && ns.includes(a.hex) && !this.attacking(a))
      .sort((a, b) => a.id - b.id);
  }

  // ---------- forms and multipliers ----------

  private controlledNeighbors(hex: number, side: StateId): number {
    let n = 0;
    for (const id of this.world.neighbors[hex]!) if (id >= 0 && this.world.cells[id]!.controller === side) n++;
    return n;
  }

  formsFor(side: StateId, target: number, attackerHexes: number[]): { wedge: boolean; encircle: boolean; corridor: boolean; salient: boolean } {
    const enemy = this.enemyOf(side);
    const distinct = new Set(attackerHexes).size;
    return {
      wedge: distinct >= 2,
      encircle: this.controlledNeighbors(target, side) >= 4 || !this.isSupplied(target, enemy),
      corridor: this.controlledNeighbors(target, side) === 1,
      salient: this.controlledNeighbors(target, side) >= 4 && this.world.cells[target]!.owner === enemy,
    };
  }

  private atkMult(army: Army, f: ReturnType<Battle['formsFor']>, breakthrough: boolean): number {
    let m = 1000;
    if (f.wedge) m += 200;
    if (f.encircle) m += 300; // «Окружение» +30% damage
    if (breakthrough) m += 500;
    if (!this.isSupplied(army.hex, army.side)) m -= 200;
    return Math.max(200, m);
  }

  private defMult(target: number, defArmy: Army | undefined, f: ReturnType<Battle['formsFor']>): number {
    const c = this.world.cells[target]!;
    const side = c.controller;
    let m = 1100; // base + defender +10%
    let fort = c.fort;
    if (this.effects.some((e) => e.kind === 'airFort' && e.hex === target)) fort = Math.max(0, fort - 1);
    m += 150 * fort;
    if (c.terrain === 'forest' || c.terrain === 'hills') m += 250;
    if (c.kind === 'city') m += 250;
    if (c.kind === 'capital') m += 500;
    if (defArmy && defArmy.infantry >= 500) m += 500; // «Стойкость»
    if (defArmy?.hold) m += 100;
    if (this.effects.some((e) => e.kind === 'defense' && e.hex === target)) m += 500;
    if (this.effects.some((e) => e.kind === 'weak' && e.hex === target)) m -= 300;
    if (f.salient) m -= 150;
    if (!this.isSupplied(target, side)) m -= 200;
    if (this.lastStand === side) m += 250;
    return Math.max(200, m);
  }

  /** Forecast for `side` attacking `target` with the given armies (canon §9.5, F = √W). */
  forecast(side: StateId, armyIds: number[], target: number, breakthrough = false): Forecast {
    const attackers = armyIds.map((id) => this.armyById(id)).filter((a): a is Army => !!a);
    const f = this.formsFor(side, target, attackers.map((a) => a.hex));
    const enemy = this.enemyOf(side);
    const defArmy = this.armyAt(target, enemy);
    let garrison = this.garrison[target] ?? 0;
    if (f.corridor) garrison = Math.floor(garrison / 2);
    const atkStr = attackers.reduce((s, a) => s + a.str, 0);
    const atkMight = attackers.reduce((s, a) => s + Math.floor((a.str * this.atkMult(a, f, breakthrough)) / 1000), 0);
    const defStr = (defArmy?.str ?? 0) + garrison;
    const defMight = Math.floor((defStr * this.defMult(target, defArmy, f)) / 1000);
    const forms: string[] = [];
    if (f.wedge) forms.push('Клин +20%');
    if (f.encircle) forms.push('Окружение +30%');
    if (f.corridor) forms.push('Коридор');
    if (f.salient) forms.push('Выступ −15%');
    const fval = defMight <= 0 || defStr <= 0 ? 99 : Math.sqrt((atkMight * atkStr) / (defMight * defStr));
    return { f: fval, atkMight, defMight, forms };
  }

  // ---------- commands ----------

  issue(side: StateId, cmd: Command): boolean {
    if (this.over) return false;
    if (!this.validate(side, cmd)) return false;
    this.queue.push({ side, cmd });
    return true;
  }

  private cost(cmd: Command): number {
    if (cmd.t === 'attack') return CARDS.attack.cost;
    if (cmd.t === 'card') return CARDS[cmd.card].cost;
    return 0;
  }

  cardReady(side: StateId, card: CardId): boolean {
    return (this.cooldown.get(`${side}:${card}`) ?? 0) <= 0;
  }

  validate(side: StateId, cmd: Command): boolean {
    const energy = this.energy.get(side) ?? 0;
    if (energy < this.cost(cmd) * ENERGY_UNIT) return false;
    switch (cmd.t) {
      case 'attack': {
        const a = this.armyById(cmd.army);
        if (!a || a.side !== side || a.routed || a.move || this.attacking(a)) return false;
        if (!this.world.neighbors[a.hex]!.includes(cmd.target)) return false;
        return this.canTarget(side, cmd.target);
      }
      case 'move': {
        const a = this.armyById(cmd.army);
        if (!a || a.side !== side || a.routed || a.move || this.attacking(a)) return false;
        if (!this.world.neighbors[a.hex]!.includes(cmd.to)) return false;
        const c = this.world.cells[cmd.to]!;
        return isPassable(c) && c.controller === side && !this.armyAt(cmd.to, side);
      }
      case 'hold': {
        const a = this.armyById(cmd.army);
        return !!a && a.side === side;
      }
      case 'retreat':
        return side === this.opts.attacker;
      case 'card': {
        if (!this.cardReady(side, cmd.card)) return false;
        const c = this.world.cells[cmd.target];
        if (!c || !isPassable(c)) return false;
        const spec = CARDS[cmd.card];
        if (spec.target === 'own') return c.controller === side;
        if (cmd.card === 'airstrike') return c.controller === this.enemyOf(side) || c.controller === side;
        if (!this.canTarget(side, cmd.target)) return false;
        if (cmd.card === 'attack' || cmd.card === 'breakthrough') return this.adjacentIdleArmies(side, cmd.target).length > 0;
        return true;
      }
    }
  }

  private apply(side: StateId, cmd: Command): void {
    if (!this.validate(side, cmd)) return;
    this.energy.set(side, (this.energy.get(side) ?? 0) - this.cost(cmd) * ENERGY_UNIT);
    this.log.push({ tick: this.tick, side, cmd });
    switch (cmd.t) {
      case 'attack':
        this.startOrJoin(side, cmd.target, [this.armyById(cmd.army)!], null);
        break;
      case 'move': {
        const a = this.armyById(cmd.army)!;
        a.move = { from: a.hex, to: cmd.to, left: MOVE_TICKS };
        a.hold = false;
        break;
      }
      case 'hold': {
        const a = this.armyById(cmd.army)!;
        a.hold = !a.hold;
        break;
      }
      case 'retreat':
        this.finish('retreat');
        break;
      case 'card':
        this.cooldown.set(`${side}:${cmd.card}`, cmd.card === 'attack' ? 0 : CARD_COOLDOWN);
        this.events.push({ type: 'card', tick: this.tick, side, card: cmd.card, hex: cmd.target });
        this.playCard(side, cmd.card, cmd.target);
        break;
    }
  }

  private playCard(side: StateId, card: CardId, target: number): void {
    switch (card) {
      case 'attack':
        this.startOrJoin(side, target, this.adjacentIdleArmies(side, target), null);
        break;
      case 'defense': {
        this.effects.push({ kind: 'defense', hex: target, left: 15 * TICKS_PER_SEC });
        const a = this.armyAt(target, side);
        if (a) a.str = Math.min(a.maxStr, a.str + Math.floor(a.maxStr / 10));
        break;
      }
      case 'encircle':
        this.effects.push({ kind: 'encircle', hex: target, left: 12 * TICKS_PER_SEC });
        break;
      case 'breakthrough': {
        const army = this.adjacentIdleArmies(side, target).sort((a, b) => b.str - a.str || a.id - b.id)[0]!;
        const dir = this.world.neighbors[army.hex]!.indexOf(target);
        this.startOrJoin(side, target, [army], { army: army.id, dir, steps: 1 });
        break;
      }
      case 'airstrike': {
        const enemy = this.enemyOf(side);
        const area = [target, ...this.world.neighbors[target]!.filter((n) => n >= 0)];
        for (const hex of area) {
          for (const a of this.armies) {
            if (a.hex === hex && a.side === enemy && !a.routed) a.str = Math.max(1, a.str - Math.floor(a.maxStr / 5));
          }
          const cell = this.world.cells[hex]!;
          if (cell.controller === enemy) {
            this.garrison[hex] = Math.max(0, (this.garrison[hex] ?? 0) - Math.floor(this.garrisonFor(hex, enemy) / 5));
            this.effects.push({ kind: 'airFort', hex, left: 15 * TICKS_PER_SEC });
          }
        }
        break;
      }
    }
  }

  private startOrJoin(side: StateId, target: number, armies: Army[], breakthrough: Clash['breakthrough']): void {
    if (armies.length === 0) return;
    let clash = this.clashes.find((c) => c.target === target && c.side === side);
    const enemy = this.enemyOf(side);
    if (!clash) {
      const f = this.formsFor(side, target, armies.map((a) => a.hex));
      if (f.corridor) this.garrison[target] = Math.floor((this.garrison[target] ?? 0) / 2);
      const def = this.armyAt(target, enemy);
      clash = {
        id: this.nextClashId++,
        target,
        side,
        attackers: [],
        defender: def ? def.id : null,
        startAtk: 0,
        startDef: (def?.str ?? 0) + (this.garrison[target] ?? 0),
        entering: 0,
        corridor: f.corridor,
        breakthrough,
      };
      this.clashes.push(clash);
      this.events.push({ type: 'clash', tick: this.tick, clash: clash.id, target, side });
    } else if (breakthrough && !clash.breakthrough) {
      clash.breakthrough = breakthrough;
    }
    for (const a of armies) {
      if (clash.attackers.includes(a.id)) continue;
      clash.attackers.push(a.id);
      clash.startAtk += a.str;
      a.hold = false;
    }
  }

  // ---------- simulation ----------

  step(): void {
    if (this.over) return;
    this.tick++;

    const rush = this.tick > OFFENSIVE_TICKS - FINAL_RUSH_TICKS;
    for (const side of [this.opts.attacker, this.opts.defender]) {
      let regen = 10; // 1 energy per 3 s = 300 / 30 ticks
      if (rush) regen *= 2;
      if (this.lastStand === side) regen = Math.floor((regen * 1250) / 1000);
      if (side === this.opts.defender) regen = Math.floor((regen * this.opts.aiEnergyMult) / 1000);
      this.energy.set(side, Math.min(ENERGY_MAX, (this.energy.get(side) ?? 0) + regen));
    }
    for (const [k, v] of this.cooldown) if (v > 0) this.cooldown.set(k, v - 1);

    const pending = this.queue;
    this.queue = [];
    for (const p of pending) {
      this.apply(p.side, p.cmd);
      if (this.over) return;
    }

    this.stepMoves();
    this.stepClashes();
    this.stepEffects();
    if (this.tick % TICKS_PER_SEC === 0) this.stepAttrition();

    const playerAlive = this.armies.some((a) => a.side === this.opts.attacker && !a.routed && a.str > 0);
    if (!playerAlive) this.finish('wiped');
    else if (this.tick >= OFFENSIVE_TICKS) this.finish('time');
  }

  private stepMoves(): void {
    for (const a of this.armies) {
      if (!a.move) continue;
      a.move.left--;
      if (a.move.left > 0) continue;
      const to = a.move.to;
      const c = this.world.cells[to]!;
      // Arrive only if the hex is still ours and free; otherwise bounce back.
      if (c.controller === a.side && !this.armyAt(to, a.side)) a.hex = to;
      a.move = null;
      // Reinforcing a hex under attack (even while the enemy is entering): become its defender.
      for (const cl of this.clashes) {
        if (cl.target !== a.hex || cl.side === a.side || cl.defender !== null) continue;
        cl.defender = a.id;
        cl.startDef = cl.entering > 0 ? a.str : cl.startDef + a.str;
        cl.entering = 0;
      }
    }
  }

  private stepClashes(): void {
    const done: Clash[] = [];
    for (const cl of [...this.clashes].sort((x, y) => x.id - y.id)) {
      const attackers = cl.attackers
        .map((id) => this.armyById(id))
        .filter((a): a is Army => !!a && !a.routed && a.str > 0 && !a.move);
      if (attackers.length === 0) {
        done.push(cl);
        continue;
      }
      if (cl.entering > 0) {
        cl.entering--;
        if (cl.entering === 0) {
          this.capture(cl, attackers);
          done.push(cl);
        }
        continue;
      }
      const enemy = this.enemyOf(cl.side);
      const cell = this.world.cells[cl.target]!;
      if (cell.controller !== enemy) {
        done.push(cl);
        continue;
      }
      const def = cl.defender !== null ? this.armyById(cl.defender) : undefined;
      const defArmy = def && !def.routed && def.hex === cl.target && !def.move ? def : undefined;
      const f = this.formsFor(cl.side, cl.target, attackers.map((a) => a.hex));
      const bt = cl.breakthrough;
      const atkMights = attackers.map((a) => Math.floor((a.str * this.atkMult(a, f, !!bt && bt.army === a.id)) / 1000));
      const atkMight = atkMights.reduce((s, m) => s + m, 0);
      const atkStr = attackers.reduce((s, a) => s + a.str, 0);
      const garrison = this.garrison[cl.target] ?? 0;
      const defStr = (defArmy?.str ?? 0) + garrison;
      const defMight = Math.floor((defStr * this.defMult(cl.target, defArmy, f)) / 1000);

      const atkLoss = Math.floor((defMight * LOSS_PERMILLE) / 1000);
      const defLoss = Math.floor((atkMight * LOSS_PERMILLE) / 1000);
      for (const a of attackers) a.str = Math.max(0, a.str - Math.floor((atkLoss * a.str) / Math.max(1, atkStr)));
      if (defStr > 0) {
        if (defArmy) defArmy.str = Math.max(0, defArmy.str - Math.floor((defLoss * defArmy.str) / defStr));
        this.garrison[cl.target] = Math.max(0, garrison - Math.floor((defLoss * garrison) / defStr));
      }

      const atkNow = attackers.reduce((s, a) => s + a.str, 0);
      const defNow = (defArmy?.str ?? 0) + (this.garrison[cl.target] ?? 0);
      const atkBroken = atkNow * 1000 < cl.startAtk * BREAK_PERMILLE;
      const defBroken = defNow * 1000 < cl.startDef * BREAK_PERMILLE || defNow <= 0;
      if (atkBroken) {
        // Simultaneous break: the attacker breaks (canon §9.5).
        this.events.push({ type: 'repelled', tick: this.tick, hex: cl.target, side: cl.side });
        done.push(cl);
      } else if (defBroken) {
        this.garrison[cl.target] = 0;
        if (defArmy) this.retreatOrRout(defArmy, f.encircle);
        cl.entering = cl.corridor ? ENTER_TICKS_CORRIDOR : ENTER_TICKS;
      }
    }
    for (const cl of done) this.clashes.splice(this.clashes.indexOf(cl), 1);
  }

  private retreatOrRout(army: Army, encircled: boolean): void {
    if (!encircled) {
      for (const n of this.world.neighbors[army.hex]!) {
        if (n < 0) continue;
        const c = this.world.cells[n]!;
        if (!isPassable(c) || c.controller !== army.side || this.armyAt(n, army.side)) continue;
        if (this.clashes.some((cl) => cl.target === n && cl.entering === 0)) continue;
        army.hex = n;
        army.hold = false;
        this.events.push({ type: 'retreat', tick: this.tick, army: army.id, to: n });
        return;
      }
    }
    this.rout(army);
  }

  private rout(army: Army): void {
    // Routed: returns with 10% Strength to the nearest supplied official own hex without an army.
    army.routed = true;
    this.events.push({ type: 'routed', tick: this.tick, army: army.id });
    if (army.side === this.opts.attacker) this.routedPlayer++;
    for (const cl of this.clashes) {
      cl.attackers = cl.attackers.filter((id) => id !== army.id);
      if (cl.defender === army.id) cl.defender = null;
    }
    const sup = supplied(this.world, army.side);
    const dist = new Map<number, number>([[army.hex, 0]]);
    const queue = [army.hex];
    while (queue.length) {
      const id = queue.shift()!;
      const c = this.world.cells[id]!;
      if (id !== army.hex && c.owner === army.side && c.controller === army.side && sup.has(id) && !this.armyAt(id, army.side)) {
        army.hex = id;
        army.str = Math.max(1, Math.floor(army.maxStr / 10));
        return;
      }
      for (const n of this.world.neighbors[id]!) {
        if (n < 0 || dist.has(n) || !isPassable(this.world.cells[n]!)) continue;
        dist.set(n, dist.get(id)! + 1);
        queue.push(n);
      }
    }
    army.str = 0;
  }

  private capture(cl: Clash, attackers: Army[]): void {
    const cell = this.world.cells[cl.target]!;
    const from = cell.controller;
    // Any enemy army still standing in the hex is pushed out (or routed if it cannot retreat).
    for (const e of this.armies) {
      if (e.side !== cl.side && e.hex === cl.target && !e.routed && e.str > 0 && !e.move) this.retreatOrRout(e, false);
    }
    cell.controller = cl.side;
    this.garrison[cl.target] = this.garrisonFor(cl.target, cl.side);
    this.supplyCache.clear();
    if (cl.side === this.opts.attacker) {
      if (cell.owner !== cl.side) this.captured.add(cl.target);
      this.lost.delete(cl.target);
    } else {
      this.captured.delete(cl.target);
      if (cell.owner === this.opts.attacker) this.lost.add(cl.target);
    }
    this.events.push({ type: 'capture', tick: this.tick, hex: cl.target, side: cl.side, from });
    if (cl.corridor) this.effects.push({ kind: 'weak', hex: cl.target, left: 20 * TICKS_PER_SEC });

    // The strongest attacker moves in; the rest hold their hexes.
    const lead = [...attackers].sort((a, b) => b.str - a.str || a.id - b.id)[0]!;
    if (!this.armyAt(cl.target, cl.side)) lead.hex = cl.target;

    const bt = cl.breakthrough;
    if (bt && bt.army === lead.id && lead.hex === cl.target && bt.steps < 3) this.continueBreakthrough(lead, bt);
  }

  private continueBreakthrough(army: Army, bt: NonNullable<Clash['breakthrough']>): void {
    const next = this.world.neighbors[army.hex]![bt.dir] ?? -1;
    if (next < 0 || !this.canTarget(army.side, next)) return;
    const enemy = this.enemyOf(army.side);
    const cell = this.world.cells[next]!;
    if (this.armyAt(next, enemy) || cell.fort >= 3) return; // stops at an army or fort ≥3
    const step = { army: army.id, dir: bt.dir, steps: bt.steps + 1 };
    if ((this.garrison[next] ?? 0) * 2 <= army.str) {
      // takes weak hexes outright
      this.garrison[next] = 0;
      const clash: Clash = {
        id: this.nextClashId++,
        target: next,
        side: army.side,
        attackers: [army.id],
        defender: null,
        startAtk: army.str,
        startDef: 0,
        entering: ENTER_TICKS,
        corridor: false,
        breakthrough: step,
      };
      this.clashes.push(clash);
    } else {
      this.startOrJoin(army.side, next, [army], step);
    }
  }

  private stepEffects(): void {
    for (const e of this.effects) e.left--;
    const before = this.effects.length;
    this.effects = this.effects.filter((e) => e.left > 0);
    if (before !== this.effects.length) this.supplyCache.clear();
  }

  hasEffect(kind: Effect['kind'], hex: number): boolean {
    return this.effects.some((e) => e.kind === kind && e.hex === hex);
  }

  private stepAttrition(): void {
    // Out of supply: −0.5% Strength per second, at most −40% per battle (canon §9.7).
    for (const a of this.armies) {
      if (a.routed || a.str <= 0 || this.isSupplied(a.hex, a.side)) continue;
      const cap = Math.floor((a.startStr * 400) / 1000);
      const loss = Math.min(Math.floor((a.maxStr * 5) / 1000), cap - a.attrition);
      if (loss > 0) {
        a.str = Math.max(1, a.str - loss);
        a.attrition += loss;
      }
    }
  }

  private finish(reason: BattleResult['reason']): void {
    if (this.over) return;
    this.over = true;
    this.endReason = reason;
    this.clashes.length = 0;
    for (const a of this.armies) {
      a.move = null;
      a.routed = false;
      a.hold = false;
    }
    this.events.push({ type: 'end', tick: this.tick, reason });
  }

  result(): BattleResult {
    return {
      captured: [...this.captured].sort((a, b) => a - b),
      lost: [...this.lost].sort((a, b) => a - b),
      routedPlayerArmies: this.routedPlayer,
      reason: this.endReason,
    };
  }
}
