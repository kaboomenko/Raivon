// Pixi map renderer: terrain, state tint, occupation hatching, official borders,
// front, pockets, armies, clashes and the peace-ceremony ink wave.

import { Application, Container, Graphics, Text } from 'pixi.js';
import {
  DIRS,
  NOBODY,
  PLAYER,
  isPassable,
  type Army,
  type Battle,
  type Cell,
  type World,
} from '@raivon/sim';
import {
  EDGE_CORNERS,
  clamp01,
  clipToConvex,
  corner,
  easeOutBack,
  hexCenter,
  hexPoly,
  lerp,
  pixelToAxial,
  shade,
  type Layout,
  type Pt,
} from './geometry.js';

export const COLORS = {
  player: 0x2e6bff,
  war: 0xe0393e,
  wild: 0xb9b2a3,
  deposit: 0xffd21f,
};

const TERRAIN_BASE: Record<string, number> = {
  plain: 0x86a85a,
  forest: 0x5f8a45,
  hills: 0xa39a63,
  water: 0x2d5f8a,
  mountain: 0x7b7468,
};

const KIND_ICON: Record<string, string> = {
  capital: '🏰',
  city: '🏘️',
  farm: '🌾',
  mine: '⛏️',
  military_base: '⛺',
  port: '⚓',
};

export interface Ceremony {
  /** seconds since the seal */
  t: number;
  /** per annexed hex: time (s) when it flips to official */
  flipAt: Map<number, number>;
  /** owner before the treaty for annexed hexes */
  prevOwner: Map<number, number>;
  zoom: number;
}

export interface Highlight {
  hex: number;
  color: number;
  pulse?: boolean;
}

export interface DrawState {
  world: World;
  armies: Army[];
  battle: Battle | null;
  atWarWith: number | null;
  goal: number;
  flag: number;
  highlights: Highlight[];
  pocketHexes: number[];
  dragLine: { from: Pt; to: Pt; color: number } | null;
  forecast: { hex: number; f: number; forms: string[] } | null;
  ceremony: Ceremony | null;
  time: number;
}

interface Floater {
  text: Text;
  born: number;
  x: number;
  y: number;
}

interface Burst {
  x: number;
  y: number;
  born: number;
  color: number;
  big: boolean;
}

export class MapView {
  readonly app: Application;
  readonly root = new Container();
  private terrain = new Graphics();
  private tint = new Graphics();
  private hatch = new Graphics();
  private borders = new Graphics();
  private overlay = new Graphics();
  private icons = new Container();
  private armyLayer = new Container();
  private fx = new Graphics();
  private floatLayer = new Container();
  private tokens = new Map<number, { c: Container; g: Graphics; t: Text }>();
  private iconTexts = new Map<number, Text>();
  private floaters: Floater[] = [];
  private bursts: Burst[] = [];
  L: Layout = { R: 30, ox: 0, oy: 0 };
  private world: World | null = null;
  private baseLayout: Layout = { R: 30, ox: 0, oy: 0 };

  constructor(app: Application) {
    this.app = app;
    this.root.addChild(this.terrain, this.tint, this.hatch, this.icons, this.borders, this.overlay, this.armyLayer, this.fx, this.floatLayer);
    app.stage.addChild(this.root);
  }

  setWorld(w: World): void {
    this.world = w;
    for (const t of this.iconTexts.values()) t.destroy();
    this.iconTexts.clear();
    for (const tok of this.tokens.values()) tok.c.destroy({ children: true });
    this.tokens.clear();
  }

  /** Fit the radius-N disk between the HUD bars (canon §9.3: R = clamp(min((W−16)/14, H/15.59), 22, 34)). */
  layout(width: number, height: number, top: number, bottom: number): void {
    const radius = this.world?.radius ?? 4;
    const cols = 3 * radius + 2; // 14 for radius 4
    const rows = Math.sqrt(3) * (2 * radius + 1); // 15.59
    const avail = height - top - bottom;
    const R = Math.max(18, Math.min(46, Math.min((width - 16) / cols, avail / rows)));
    this.baseLayout = { R, ox: width / 2, oy: top + avail / 2 };
    this.L = { ...this.baseLayout };
  }

  hexAt(x: number, y: number): number {
    if (!this.world) return -1;
    const a = pixelToAxial(this.L, x, y);
    return this.world.byKey.get(`${a.q},${a.r}`) ?? -1;
  }

  centerOf(id: number): Pt {
    const c = this.world!.cells[id]!;
    return hexCenter(this.L, c.q, c.r);
  }

  stateColor(state: number, atWarWith: number | null): number {
    if (state === PLAYER) return COLORS.player;
    if (state === NOBODY) return COLORS.wild;
    if (state === atWarWith) return COLORS.war;
    return this.world!.states[state]?.color ?? COLORS.wild;
  }

  floatText(hex: number, text: string, color = 0xffffff): void {
    const p = this.centerOf(hex);
    const t = new Text({ text, style: { fontFamily: 'system-ui, sans-serif', fontSize: Math.round(this.L.R * 0.55), fontWeight: '800', fill: color, stroke: { color: 0x000000, width: 4 } } });
    t.anchor.set(0.5);
    this.floatLayer.addChild(t);
    this.floaters.push({ text: t, born: performance.now(), x: p.x, y: p.y });
  }

  burst(hex: number, color: number, big = false): void {
    const p = this.centerOf(hex);
    this.bursts.push({ x: p.x, y: p.y, born: performance.now(), color, big });
  }

  draw(s: DrawState): void {
    const w = s.world;
    if (!w) return;
    // Ceremony camera: pull back slightly (canon §10.3 step 2).
    const z = s.ceremony ? s.ceremony.zoom : 1;
    this.L = { R: this.baseLayout.R * z, ox: this.baseLayout.ox, oy: this.baseLayout.oy };
    const R = this.L.R;

    this.terrain.clear();
    this.tint.clear();
    this.hatch.clear();
    this.borders.clear();
    this.overlay.clear();
    this.fx.clear();

    const ownerOf = (c: Cell): number => {
      const cer = s.ceremony;
      if (cer && cer.flipAt.has(c.id) && s.ceremony!.t < cer.flipAt.get(c.id)!) return cer.prevOwner.get(c.id)!;
      return c.owner;
    };

    // --- terrain + tint ---
    for (const c of w.cells) {
      const p = hexCenter(this.L, c.q, c.r);
      let scale = 0.97;
      const cer = s.ceremony;
      if (cer && cer.flipAt.has(c.id)) {
        const dt = cer.t - cer.flipAt.get(c.id)!;
        if (dt >= 0 && dt < 0.35) scale = 0.97 * (1 + 0.08 * Math.sin((dt / 0.35) * Math.PI)); // «pop» 1.08 → 1.0
      }
      this.terrain.poly(hexPoly(p, R * scale)).fill({ color: TERRAIN_BASE[c.terrain] ?? 0x888888 });
      if (c.terrain === 'mountain') this.drawMountain(p, R);
      if (c.terrain === 'water') this.drawWaves(p, R, s.time);
      if (!isPassable(c)) continue;
      if (c.terrain === 'forest') this.drawTrees(p, R);
      if (c.terrain === 'hills') this.drawHills(p, R);
      const owner = ownerOf(c);
      const alpha = owner === NOBODY ? 0.4 : 0.55;
      this.tint.poly(hexPoly(p, R * scale)).fill({ color: this.stateColor(owner, s.atWarWith), alpha });

      // occupation hatching (canon §3.1): diagonal stripes in the occupier's colour
      const occupiedNow = c.controller !== owner && !(s.ceremony && s.ceremony.flipAt.has(c.id) && s.ceremony.t >= s.ceremony.flipAt.get(c.id)!);
      if (occupiedNow) {
        let a = 0.9;
        if (s.ceremony && s.ceremony.flipAt.has(c.id)) {
          a = 0.9 * clamp01((s.ceremony.flipAt.get(c.id)! - s.ceremony.t) / 0.4 + 0.2);
        }
        this.drawHatch(p, R * scale, this.stateColor(c.controller, s.atWarWith), a);
      }
      this.updateIcon(c, p, R);
    }

    // --- official borders (thick contour), animated by the ceremony ---
    this.drawBorders(s, ownerOf);

    // --- front line between controllers at war ---
    if (s.atWarWith !== null && !s.ceremony) {
      for (const c of w.cells) {
        if (!isPassable(c) || c.controller !== PLAYER) continue;
        const p = hexCenter(this.L, c.q, c.r);
        for (let d = 0; d < 6; d++) {
          const n = w.neighbors[c.id]![d]!;
          if (n < 0 || w.cells[n]!.controller !== s.atWarWith) continue;
          const [k1, k2] = EDGE_CORNERS[d]!;
          const a = corner(p, R, k1);
          const b = corner(p, R, k2);
          const glow = 0.55 + 0.35 * Math.sin(s.time * 4);
          this.overlay.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ width: R * 0.22, color: 0xffffff, alpha: 0.18 * glow, cap: 'round' });
          this.overlay.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ width: R * 0.07, color: 0xfff4e0, alpha: 0.9, cap: 'round' });
        }
      }
    }

    // --- pockets (red pulsing dashed outline) ---
    if (s.pocketHexes.length && !s.ceremony) {
      const set = new Set(s.pocketHexes);
      const pulse = 0.5 + 0.5 * Math.sin(s.time * 5);
      for (const id of set) {
        const c = w.cells[id]!;
        const p = hexCenter(this.L, c.q, c.r);
        for (let d = 0; d < 6; d++) {
          const n = w.neighbors[c.id]![d]!;
          if (n >= 0 && set.has(n)) continue;
          const [k1, k2] = EDGE_CORNERS[d]!;
          this.dashed(corner(p, R * 0.9, k1), corner(p, R * 0.9, k2), 0xff5a5a, 0.5 + 0.5 * pulse, R * 0.09);
        }
      }
    }

    // --- highlights ---
    for (const h of s.highlights) {
      const c = w.cells[h.hex];
      if (!c) continue;
      const p = hexCenter(this.L, c.q, c.r);
      const a = h.pulse ? 0.45 + 0.4 * Math.sin(s.time * 6) : 0.85;
      this.overlay.poly(hexPoly(p, R * 0.86)).stroke({ width: R * 0.1, color: h.color, alpha: a });
    }

    // --- goal flag ---
    for (const [hex, col] of [[s.goal, 0xffffff], [s.flag, 0xffd166]] as const) {
      if (hex < 0 || s.ceremony) continue;
      const c = w.cells[hex]!;
      const p = hexCenter(this.L, c.q, c.r);
      const fx = p.x + R * 0.35;
      const fy = p.y - R * 0.55;
      this.overlay.moveTo(fx, fy).lineTo(fx, fy + R * 0.55).stroke({ width: 2, color: 0x222222 });
      this.overlay.poly([fx, fy, fx + R * 0.32, fy + R * 0.1, fx, fy + R * 0.22]).fill({ color: col });
      if (hex === s.flag && s.flag !== s.goal) break;
    }

    // --- clashes ---
    if (s.battle) {
      for (const cl of s.battle.clashes) {
        const tp = this.centerOf(cl.target);
        for (const id of cl.attackers) {
          const a = s.battle.armyById(id);
          if (!a) continue;
          const ap = this.centerOf(a.hex);
          const mx = lerp(ap.x, tp.x, 0.5);
          const my = lerp(ap.y, tp.y, 0.5);
          const jitter = Math.sin(s.time * 30 + id) * R * 0.04;
          const col = this.stateColor(cl.side, s.atWarWith);
          this.fx.moveTo(ap.x, ap.y).lineTo(mx, my).stroke({ width: R * 0.12, color: col, alpha: 0.7, cap: 'round' });
          this.fx.circle(mx + jitter, my, R * 0.16).fill({ color: 0xfff1c1, alpha: 0.9 });
          this.fx.star(mx + jitter, my, 6, R * 0.26, R * 0.12).fill({ color: 0xffa630, alpha: 0.75 });
        }
        if (cl.entering > 0) this.fx.circle(tp.x, tp.y, R * 0.7).stroke({ width: 3, color: 0xffffff, alpha: 0.8 });
      }
      for (const c of w.cells) {
        if (s.battle.hasEffect('defense', c.id)) {
          const p = this.centerOf(c.id);
          this.fx.poly(hexPoly(p, R * 0.8)).stroke({ width: R * 0.12, color: 0x9ad1ff, alpha: 0.85 });
        }
        if (s.battle.hasEffect('encircle', c.id)) {
          const p = this.centerOf(c.id);
          const rr = R * (0.9 + 0.08 * Math.sin(s.time * 8));
          this.fx.circle(p.x, p.y, rr).stroke({ width: R * 0.08, color: 0xff6b6b, alpha: 0.9 });
        }
      }
    }

    // --- drag line + forecast ---
    if (s.dragLine) {
      const { from, to, color } = s.dragLine;
      this.fx.moveTo(from.x, from.y).lineTo(to.x, to.y).stroke({ width: R * 0.16, color, alpha: 0.85, cap: 'round' });
      this.fx.circle(to.x, to.y, R * 0.18).fill({ color, alpha: 0.9 });
    }

    this.drawArmies(s);
    this.drawBursts();
    this.drawFloaters();
  }

  private drawBorders(s: DrawState, ownerOf: (c: Cell) => number): void {
    const w = s.world;
    const R = this.L.R;
    const width = Math.max(3.5, R * 0.2);
    const inset = width * 0.55;
    const cer = s.ceremony;
    for (const c of w.cells) {
      if (!isPassable(c)) continue;
      const owner = ownerOf(c);
      if (owner === NOBODY) continue;
      const p = hexCenter(this.L, c.q, c.r);
      const color = shade(this.stateColor(owner, s.atWarWith), 0.6);
      for (let d = 0; d < 6; d++) {
        const n = w.neighbors[c.id]![d]!;
        const nc = n >= 0 ? w.cells[n]! : null;
        let alpha = 1;
        if (nc && isPassable(nc) && ownerOf(nc) === owner) {
          // Old contour pieces fade out right after the neighbour flips to the same owner.
          if (!cer) continue;
          const fn = cer.flipAt.get(nc.id);
          const fc = cer.flipAt.get(c.id) ?? -1;
          if (fn === undefined || fc >= fn) continue;
          alpha = clamp01(1 - (cer.t - fn) / 0.3);
          if (alpha <= 0) continue;
        }
        const [k1, k2] = EDGE_CORNERS[d]!;
        const a = corner(p, R - inset, k1);
        let b = corner(p, R - inset, k2);
        // Ceremony: the new contour is drawn like ink along the edge (≈0.25 s per ring).
        if (cer && cer.flipAt.has(c.id)) {
          const prog = clamp01((cer.t - cer.flipAt.get(c.id)!) / 0.3);
          if (prog <= 0) continue;
          b = { x: lerp(a.x, b.x, prog), y: lerp(a.y, b.y, prog) };
        }
        this.borders.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ width: width + 2.5, color: 0xffffff, alpha: 0.7 * alpha, cap: 'round' });
        this.borders.moveTo(a.x, a.y).lineTo(b.x, b.y).stroke({ width, color, alpha, cap: 'round' });
      }
    }
  }

  private dashed(a: Pt, b: Pt, color: number, alpha: number, width: number): void {
    const n = 4;
    for (let i = 0; i < n; i++) {
      const t0 = i / n;
      const t1 = t0 + 0.6 / n;
      this.overlay
        .moveTo(lerp(a.x, b.x, t0), lerp(a.y, b.y, t0))
        .lineTo(lerp(a.x, b.x, t1), lerp(a.y, b.y, t1))
        .stroke({ width, color, alpha, cap: 'round' });
    }
  }

  private drawHatch(p: Pt, R: number, color: number, alpha: number): void {
    const poly: Pt[] = [];
    for (let k = 0; k < 6; k++) poly.push(corner(p, R, k));
    const period = R * 0.4;
    for (let off = -2 * R; off <= 2 * R; off += period) {
      const a = { x: p.x + off - 2 * R, y: p.y + 2 * R };
      const b = { x: p.x + off + 2 * R, y: p.y - 2 * R };
      const seg = clipToConvex(a, b, poly);
      if (seg) this.hatch.moveTo(seg[0].x, seg[0].y).lineTo(seg[1].x, seg[1].y).stroke({ width: R * 0.16, color, alpha });
    }
  }

  private drawTrees(p: Pt, R: number): void {
    for (const [dx, dy] of [[-0.35, 0.15], [0.3, 0.25], [0.05, -0.3]] as const) {
      const x = p.x + dx * R;
      const y = p.y + dy * R;
      this.terrain.poly([x, y - R * 0.28, x - R * 0.17, y + R * 0.08, x + R * 0.17, y + R * 0.08]).fill({ color: 0x2f5a2a });
    }
  }

  private drawHills(p: Pt, R: number): void {
    this.terrain.poly([p.x - R * 0.55, p.y + R * 0.25, p.x - R * 0.15, p.y - R * 0.2, p.x + R * 0.2, p.y + R * 0.25]).fill({ color: 0x8a7f4e });
    this.terrain.poly([p.x - R * 0.05, p.y + R * 0.3, p.x + R * 0.3, p.y - R * 0.05, p.x + R * 0.6, p.y + R * 0.3]).fill({ color: 0x7c7246 });
  }

  private drawMountain(p: Pt, R: number): void {
    this.terrain.poly([p.x - R * 0.6, p.y + R * 0.4, p.x - R * 0.1, p.y - R * 0.5, p.x + R * 0.4, p.y + R * 0.4]).fill({ color: 0x5c564d });
    this.terrain.poly([p.x - R * 0.24, p.y - R * 0.24, p.x - R * 0.1, p.y - R * 0.5, p.x + R * 0.04, p.y - R * 0.24]).fill({ color: 0xf2efe9 });
    this.terrain.poly([p.x + R * 0.05, p.y + R * 0.4, p.x + R * 0.35, p.y - R * 0.15, p.x + R * 0.65, p.y + R * 0.4]).fill({ color: 0x4d4840 });
  }

  private drawWaves(p: Pt, R: number, t: number): void {
    for (let i = -1; i <= 1; i++) {
      const y = p.y + i * R * 0.35;
      const sh = Math.sin(t * 1.5 + p.x * 0.05 + i) * R * 0.08;
      this.terrain.moveTo(p.x - R * 0.35 + sh, y).quadraticCurveTo(p.x + sh, y - R * 0.12, p.x + R * 0.35 + sh, y).stroke({ width: 1.5, color: 0x8fc1e8, alpha: 0.55 });
    }
  }

  private updateIcon(c: Cell, p: Pt, R: number): void {
    const icon = KIND_ICON[c.kind];
    if (!icon) return;
    let t = this.iconTexts.get(c.id);
    if (!t) {
      t = new Text({ text: icon, style: { fontSize: 64 } });
      t.anchor.set(0.5);
      this.icons.addChild(t);
      this.iconTexts.set(c.id, t);
    }
    const size = c.kind === 'capital' ? R * 0.95 : R * 0.7;
    t.scale.set(size / 64);
    t.position.set(p.x, p.y - R * 0.05);
  }

  private drawArmies(s: DrawState): void {
    const alive = new Set<number>();
    const R = this.L.R;
    for (const a of s.armies) {
      if (a.str <= 0) continue;
      alive.add(a.id);
      let tok = this.tokens.get(a.id);
      if (!tok) {
        const c = new Container();
        const g = new Graphics();
        const t = new Text({ text: '', style: { fontFamily: 'system-ui, sans-serif', fontSize: 40, fontWeight: '800', fill: 0xffffff } });
        t.anchor.set(0.5);
        c.addChild(g, t);
        this.armyLayer.addChild(c);
        tok = { c, g, t };
        this.tokens.set(a.id, tok);
      }
      let p = this.centerOf(a.hex);
      if (a.move) {
        const to = this.centerOf(a.move.to);
        const k = 1 - a.move.left / 15;
        p = { x: lerp(p.x, to.x, k), y: lerp(p.y, to.y, k) };
      }
      const color = this.stateColor(a.side, s.atWarWith);
      const g = tok.g;
      g.clear();
      const rr = R * 0.5;
      // pawn-like token: shadow, base disc, flag
      g.ellipse(0, rr * 0.75, rr * 0.95, rr * 0.35).fill({ color: 0x000000, alpha: 0.3 });
      g.circle(0, 0, rr).fill({ color: shade(color, 0.75) }).stroke({ width: Math.max(2, R * 0.08), color: 0xffffff });
      g.circle(0, 0, rr * 0.78).fill({ color });
      // readiness arc
      const ready = a.maxStr > 0 ? a.str / a.maxStr : 0;
      g.arc(0, 0, rr * 1.12, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * ready).stroke({ width: Math.max(2, R * 0.07), color: ready >= 0.5 ? 0x7cff8a : 0xffb347 });
      if (a.hold) g.poly(hexPoly({ x: 0, y: 0 }, rr * 1.35)).stroke({ width: 2, color: 0x9ad1ff });
      tok.t.text = String(Math.round(a.str / 1000));
      tok.t.scale.set((R * 0.48) / 40);
      tok.c.position.set(p.x, p.y + R * 0.18);
      tok.c.alpha = a.routed ? 0.4 : 1;
    }
    for (const [id, tok] of this.tokens) {
      if (!alive.has(id)) {
        tok.c.destroy({ children: true });
        this.tokens.delete(id);
      }
    }
  }

  private drawBursts(): void {
    const now = performance.now();
    this.bursts = this.bursts.filter((b) => now - b.born < (b.big ? 900 : 600));
    for (const b of this.bursts) {
      const k = (now - b.born) / (b.big ? 900 : 600);
      const r = this.L.R * (b.big ? 2.2 : 1) * easeOutBack(Math.min(1, k * 1.4));
      this.fx.circle(b.x, b.y, r).stroke({ width: this.L.R * 0.15 * (1 - k), color: b.color, alpha: 1 - k });
      if (b.big) this.fx.circle(b.x, b.y, r * 0.6).fill({ color: 0xffb347, alpha: 0.5 * (1 - k) });
    }
  }

  private drawFloaters(): void {
    const now = performance.now();
    this.floaters = this.floaters.filter((f) => {
      const k = (now - f.born) / 1300;
      if (k >= 1) {
        f.text.destroy();
        return false;
      }
      f.text.position.set(f.x, f.y - this.L.R * 1.2 * k);
      f.text.alpha = 1 - k * k;
      return true;
    });
  }
}

export function neighborsDirs(): number {
  return DIRS.length;
}
