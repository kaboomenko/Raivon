import { Application } from 'pixi.js';
import {
  BARONS,
  Battle,
  BattleAI,
  CARDS,
  ENERGY_UNIT,
  FINAL_RUSH_TICKS,
  HAMLETS,
  NOBODY,
  OFFENSIVE_TICKS,
  PLAYER,
  TICKS_PER_SEC,
  applyTreaty,
  availableDemands,
  coreOf,
  declareWar,
  enemyPocketHexes,
  generateChapterOne,
  infantryArmy,
  isPassable,
  offensiveStars,
  officialValue,
  recommendGoals,
  recommendPackage,
  recordOffensive,
  ringsFrom,
  startingArmies,
  warScore,
  whitePeace,
  type Army,
  type CardId,
  type Demand,
  type War,
  type World,
} from '@raivon/sim';
import { setMuted, sfx, unlockAudio, vibrate } from './audio.js';
import { COLORS, MapView, type Ceremony, type DrawState, type Highlight } from './view.js';

type Mode = 'intro' | 'map' | 'pickGoal' | 'war' | 'battle' | 'result' | 'peace' | 'ceremony';

const HAND: CardId[] = ['attack', 'breakthrough', 'airstrike', 'encircle', 'defense'];
const CARD_ART: Record<CardId, string> = { attack: '⚔️', breakthrough: '🛡️', airstrike: '✈️', encircle: '🎯', defense: '🧱' };
const CHAPTER_GOAL = 20;
const SEED = Number(new URLSearchParams(location.search).get('seed') ?? 20261004);

const $ = <T extends HTMLElement = HTMLElement>(sel: string): T => document.querySelector(sel) as T;
const top = $('#top');
const bottom = $('#bottom');
const panel = $('#panel');
const toastBox = $('#toast');
const ghost = $('#ghost');

interface Game {
  world: World;
  armies: Army[];
  mode: Mode;
  war: War | null;
  battle: Battle | null;
  ai: BattleAI | null;
  goalChoices: number[];
  flag: number;
  demands: Demand[];
  chosen: Set<string>;
  ceremony: (Ceremony & { annexed: number[]; summary: string[]; startedAt: number }) | null;
  truce: Map<number, number>;
  battleStartControl: Map<number, number>;
  muted: boolean;
}

const G: Game = {
  world: generateChapterOne(SEED),
  armies: [],
  mode: 'intro',
  war: null,
  battle: null,
  ai: null,
  goalChoices: [],
  flag: -1,
  demands: [],
  chosen: new Set(),
  ceremony: null,
  truce: new Map(),
  battleStartControl: new Map(),
  muted: false,
};
G.armies = startingArmies(G.world);

// ---------- toasts ----------
function toast(msg: string): void {
  const d = document.createElement('div');
  d.textContent = msg;
  toastBox.appendChild(d);
  setTimeout(() => d.remove(), 2500);
}

// ---------- pixi ----------
const app = new Application();
await app.init({
  resizeTo: $('#stage'),
  backgroundAlpha: 0,
  antialias: true,
  resolution: Math.min(window.devicePixelRatio || 1, 2),
  autoDensity: true,
});
$('#stage').appendChild(app.canvas);
const view = new MapView(app);
view.setWorld(G.world);

function relayout(): void {
  const topH = top.getBoundingClientRect().height;
  let botH = bottom.getBoundingClientRect().height;
  // A bottom sheet (peace treaty) pushes the map up so the demanded hexes stay visible.
  const sheet = panel.querySelector<HTMLElement>('.sheet');
  if (sheet && !panel.classList.contains('hidden') && !panel.classList.contains('center')) botH = Math.max(botH, sheet.getBoundingClientRect().height);
  view.layout(app.screen.width, app.screen.height, topH + 6, botH + 6);
}
new ResizeObserver(relayout).observe(document.body);

// ---------- helpers ----------
const W = (): World => G.world;
const cellName = (id: number): string => {
  const c = W().cells[id]!;
  if (c.name) return c.name;
  const t: Record<string, string> = { plain: 'Равнина', forest: 'Лес', hills: 'Холмы', water: 'Вода', mountain: 'Горы' };
  return t[c.terrain] ?? 'Гекс';
};
const playerHexCount = (): number => W().cells.filter((c) => c.owner === PLAYER && isPassable(c)).length;
const enemyName = (id: number): string => W().states[id]?.name ?? '';

function neighborStates(): number[] {
  const out = new Set<number>();
  for (const c of W().cells) {
    if (c.owner !== PLAYER) continue;
    for (const n of W().neighbors[c.id]!) {
      if (n < 0) continue;
      const o = W().cells[n]!.owner;
      if (o !== PLAYER && o !== NOBODY) out.add(o);
    }
  }
  return [...out].sort();
}

function ensureArmiesFor(state: number): void {
  if (G.armies.some((a) => a.side === state)) return;
  const front = W()
    .cells.filter((c) => c.owner === state && isPassable(c) && W().neighbors[c.id]!.some((n) => n >= 0 && W().cells[n]!.owner === PLAYER))
    .map((c) => c.id);
  const cap = W().states[state]!.capitalId;
  const dl = W().states[state]!.devLevel;
  let id = 100 + state * 10;
  G.armies.push(infantryArmy(id++, state, front[0] ?? cap, 3, dl));
  const second = front.find((h) => h !== front[0]) ?? cap;
  if (second !== (front[0] ?? cap)) G.armies.push(infantryArmy(id++, state, second, 3, dl));
}

/** Put every army back on a hex its side controls (after treaties, routs, colonization). */
function normalizeArmies(): void {
  const occupied = new Set<string>();
  for (const a of G.armies) {
    const c = W().cells[a.hex]!;
    const key = `${a.side}:${a.hex}`;
    if (c.controller === a.side && !occupied.has(key)) {
      occupied.add(key);
      continue;
    }
    // BFS to nearest own free hex
    const seen = new Set<number>([a.hex]);
    const q = [a.hex];
    while (q.length) {
      const id = q.shift()!;
      const cc = W().cells[id]!;
      if (cc.controller === a.side && cc.owner === a.side && !occupied.has(`${a.side}:${id}`)) {
        a.hex = id;
        occupied.add(`${a.side}:${id}`);
        break;
      }
      for (const n of W().neighbors[id]!) {
        if (n >= 0 && !seen.has(n) && isPassable(W().cells[n]!)) {
          seen.add(n);
          q.push(n);
        }
      }
    }
  }
}

// ---------- HUD rendering ----------
function renderTop(): void {
  if (G.mode === 'intro') {
    top.innerHTML = '';
    return;
  }
  const w = W();
  if ((G.mode === 'battle' || G.mode === 'war' || G.mode === 'result') && G.war) {
    const ws = warScore(w, G.war);
    const b = G.battle;
    const secs = b ? b.secondsLeft() : null;
    const rush = b ? b.tick > OFFENSIVE_TICKS - FINAL_RUSH_TICKS : false;
    top.innerHTML = `
      <div class="control">
        <div class="row">
          <div class="bar"><div class="fill" style="width:${ws.control}%"></div>
            <div class="lbl"><span>${ws.control}%</span><span>${100 - ws.control}%</span></div></div>
          ${secs !== null && G.mode === 'battle' ? `<div class="timer ${rush ? 'rush' : ''}">${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}</div>` : ''}
        </div>
        <div class="row" style="margin-top:6px;font-size:12px;color:var(--muted)">
          <span>Война: ${enemyName(G.war.enemy)}</span><span style="margin-left:auto">Военный счёт: <b style="color:#fff">${ws.score > 0 ? '+' : ''}${ws.score}</b></span>
        </div>
        ${ws.control <= 30 ? '<div class="laststand">ВЫ НА ГРАНИ ПОРАЖЕНИЯ! Последний рубеж: +25% к защите</div>' : ''}
      </div>`;
    return;
  }
  const hexes = playerHexCount();
  top.innerHTML = `
    <div class="statebar">
      <div class="flag"></div>
      <div><div class="name">Ваша держава</div><div style="font-size:11px;color:var(--muted)">Уровень развития 1 · Хутор</div></div>
      <div class="stats">Гексов: <b style="color:#fff">${hexes}</b> · Держава ${officialValue(w, PLAYER)}<br/>Глава I «Долина»: <b style="color:#fff">${hexes}/${CHAPTER_GOAL}</b></div>
      <button class="btn ghost small" id="mute" style="margin-left:6px">${G.muted ? '🔇' : '🔊'}</button>
    </div>`;
  $('#mute').onclick = () => {
    G.muted = !G.muted;
    setMuted(G.muted);
    renderTop();
  };
}

function renderBottom(): void {
  const w = W();
  switch (G.mode) {
    case 'intro':
      bottom.innerHTML = '';
      return;
    case 'map': {
      const ns = neighborStates();
      const btns = ns
        .map((s) => {
          const truce = G.truce.get(s) ?? 0;
          const left = Math.max(0, Math.ceil((truce - Date.now()) / 1000));
          return left > 0
            ? `<button class="btn ghost" disabled>Перемирие с «${enemyName(s)}» ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}</button>`
            : `<button class="btn red" data-war="${s}">⚔️ Объявить войну: ${enemyName(s)}</button>`;
        })
        .join('');
      bottom.innerHTML = `
        <div class="info">Тап по серому гексу у границы — колонизация. Тап по любому гексу — информация.</div>
        ${btns || '<div class="hint">Нет соседей для войны — колонизируйте дикие земли</div>'}
        ${playerHexCount() >= CHAPTER_GOAL ? '<button class="btn green" id="chapter">🌍 Мир расширяется (глава I пройдена)</button>' : ''}`;
      bottom.querySelectorAll<HTMLButtonElement>('[data-war]').forEach((b) => (b.onclick = () => startPickGoal(Number(b.dataset.war))));
      const ch = bottom.querySelector<HTMLButtonElement>('#chapter');
      if (ch) ch.onclick = () => showChapterDone();
      break;
    }
    case 'pickGoal':
      bottom.innerHTML = `
        <div class="info">Выберите <b>цель войны</b> — гекс, ради которого вы воюете (+10 к военному счёту, пока он ваш). Рекомендованные подсвечены.</div>
        <button class="btn ghost" id="cancel">Отмена</button>`;
      $('#cancel').onclick = () => setMode('map');
      break;
    case 'war': {
      const ws = warScore(w, G.war!);
      const ready = G.armies.filter((a) => a.side === PLAYER).every((a) => a.str * 2 >= a.maxStr);
      const peaceLabel = ws.score > 0 ? `🕊️ Мир (${ws.score})` : Math.abs(ws.score) < 10 ? '🕊️ Белый мир' : '🏳️ Просить мира';
      bottom.innerHTML = `
        <div class="info">Армии с готовностью ≥50% идут в наступление. Захваченное — <b>оккупировано</b>: толстая граница не меняется до мира.</div>
        <div class="row-btns">
          <button class="btn ghost" id="refill">♻️ Пополнить армии</button>
          <button class="btn green" id="peace">${peaceLabel}</button>
        </div>
        <button class="btn red" id="offensive" ${ready ? '' : 'disabled'}>▶ Наступление (90 с)</button>
        ${ready ? '' : '<div class="hint">Пополните армии: в игре это 20 мин или реклама</div>'}`;
      $('#refill').onclick = () => {
        for (const a of G.armies) a.str = a.maxStr;
        sfx.tap();
        toast('Армии пополнены (в полной игре — таймер 20 мин или реклама)');
        renderBottom();
      };
      $('#peace').onclick = () => openPeace();
      $('#offensive').onclick = () => startOffensive();
      break;
    }
    case 'battle':
      renderBattleBottom();
      break;
    case 'result':
    case 'peace':
    case 'ceremony':
      bottom.innerHTML = '';
      break;
  }
  relayout();
}

let handEls: HTMLElement[] = [];
function renderBattleBottom(): void {
  bottom.innerHTML = `
    <div class="energy"><div class="num" id="enum">5</div><div class="segs">${'<div class="seg"><i></i></div>'.repeat(10)}</div></div>
    <div class="hand">${HAND.map(
      (c) => `<div class="card" data-card="${c}"><div class="art">${CARD_ART[c]}</div><div class="nm">${CARDS[c].name}</div><div class="cost">${CARDS[c].cost}</div></div>`,
    ).join('')}</div>
    <div class="row-btns"><button class="btn ghost small" id="retreat">Отступить</button></div>`;
  handEls = [...bottom.querySelectorAll<HTMLElement>('.card')];
  handEls.forEach((el) => attachCardDrag(el, el.dataset.card as CardId));
  $('#retreat').onclick = () => G.battle?.issue(PLAYER, { t: 'retreat' });
  relayout();
}

function updateBattleHud(): void {
  const b = G.battle;
  if (!b) return;
  const e = b.energy.get(PLAYER) ?? 0;
  const pts = Math.floor(e / ENERGY_UNIT);
  const frac = (e % ENERGY_UNIT) / ENERGY_UNIT;
  const num = document.getElementById('enum');
  if (num) num.textContent = String(pts);
  bottom.querySelectorAll<HTMLElement>('.seg i').forEach((el, i) => {
    el.style.width = i < pts ? '100%' : i === pts ? `${Math.round(frac * 100)}%` : '0%';
  });
  for (const el of handEls) {
    const card = el.dataset.card as CardId;
    const cd = b.cooldown.get(`${PLAYER}:${card}`) ?? 0;
    el.classList.toggle('off', pts < CARDS[card].cost || cd > 0);
    let cdEl = el.querySelector('.cd');
    if (cd > 0) {
      if (!cdEl) {
        cdEl = document.createElement('div');
        cdEl.className = 'cd';
        el.appendChild(cdEl);
      }
      cdEl.textContent = String(Math.ceil(cd / TICKS_PER_SEC));
    } else cdEl?.remove();
  }
}

// ---------- panels ----------
function showPanel(html: string, center = false, parchment = false): HTMLElement {
  panel.className = center ? 'center' : '';
  panel.innerHTML = `<div class="sheet ${parchment ? 'parchment' : ''}">${html}</div>`;
  requestAnimationFrame(relayout);
  return panel.firstElementChild as HTMLElement;
}
function hidePanel(): void {
  panel.className = 'hidden';
  panel.innerHTML = '';
  requestAnimationFrame(relayout);
}

function showIntro(): void {
  showPanel(
    `<div class="title"><div class="sub">ПРОТОТИП v0.1</div><h1>RAIVON</h1><div style="font-weight:800;color:var(--muted)">Territory Wars</div></div>
     <div class="howto">
       <div><span>🔵</span>Вы — синее государство. Рядом — Кремнёвые Бароны.</div>
       <div><span>👆</span>Свайп от своей армии к вражескому гексу — атака (2 энергии).</div>
       <div><span>🃏</span>Перетащите карту на гекс: Атака всеми, Прорыв, Авиаудар, Окружение, Оборона.</div>
       <div><span>▦</span>Захваченное заштриховано — это оккупация. Граница не меняется.</div>
       <div><span>🕊️</span>Подпишите мир — и граница перетечёт на новые земли.</div>
     </div>
     <button class="btn" id="go" style="width:100%">Начать</button>`,
    true,
  );
  $('#go').onclick = () => {
    unlockAudio();
    sfx.tap();
    hidePanel();
    setMode('map');
  };
}

function showChapterDone(): void {
  sfx.fanfare();
  showPanel(
    `<h2>🌍 Глава I пройдена!</h2>
     <p>В полной игре здесь начинается церемония «Мир расширяется»: туман по краям рассеивается, и карта вырастает до 90 гексов с новыми государствами (глава II «Речной край»).</p>
     <p>В прототипе можно продолжать воевать и колонизировать.</p>
     <div class="row-btns"><button class="btn ghost" id="restart">Начать заново</button><button class="btn" id="ok">Продолжить</button></div>`,
    true,
  );
  $('#ok').onclick = () => hidePanel();
  $('#restart').onclick = () => location.reload();
}

// ---------- mode transitions ----------
function setMode(m: Mode): void {
  G.mode = m;
  renderTop();
  renderBottom();
}

function startPickGoal(enemy: number): void {
  ensureArmiesFor(enemy);
  normalizeArmies();
  G.goalChoices = recommendGoals(W(), enemy, 3);
  G.war = declareWar(W(), enemy, G.goalChoices[0] ?? -1);
  setMode('pickGoal');
  toast(`Выберите цель войны против «${enemyName(enemy)}»`);
}

function confirmWar(goal: number): void {
  const enemy = G.war!.enemy;
  G.war = declareWar(W(), enemy, goal);
  sfx.warn();
  vibrate(60);
  toast(`Война объявлена! Цель — «${cellName(goal)}»`);
  setMode('war');
}

function startOffensive(): void {
  const war = G.war!;
  // AI refills between offensives (its readiness rules, canon 11 §15.1)
  for (const a of G.armies) if (a.side === war.enemy) a.str = a.maxStr;
  const flag = W().cells[war.goal]?.controller === war.enemy ? war.goal : recommendGoals(W(), war.enemy, 1)[0] ?? -1;
  G.flag = flag;
  G.battleStartControl = new Map(W().cells.map((c) => [c.id, c.controller]));
  G.battle = new Battle(W(), G.armies, { attacker: PLAYER, defender: war.enemy, aiEnergyMult: 600, cards: HAND });
  G.ai = new BattleAI(war.enemy);
  acc = 0;
  sfx.warn();
  setMode('battle');
  toast('В бой! Свайп от армии к врагу или перетащите карту');
}

function endOffensive(): void {
  const b = G.battle!;
  const war = G.war!;
  const res = b.result();
  const stars = offensiveStars(res.captured, G.flag, res.routedPlayerArmies);
  recordOffensive(war, stars);
  const ws = warScore(W(), war);
  G.battle = null;
  G.ai = null;
  normalizeArmies();
  G.mode = 'result';
  renderTop();
  renderBottom();
  const reasonText = res.reason === 'retreat' ? 'Вы отступили' : res.reason === 'wiped' ? 'Все армии сломлены' : 'Время вышло';
  showPanel(
    `<h2>Итоги наступления</h2>
     <div class="stars">${[1, 2, 3].map((i) => `<span class="${i <= stars ? '' : 'off'}">★</span>`).join('')}</div>
     <p style="text-align:center">${reasonText}. ★ — взят гекс, ★★ — взят флажок, ★★★ — без разбитых армий.</p>
     <div class="kv"><span>Захвачено гексов</span><b>${res.captured.length}</b></div>
     <div class="kv"><span>Потеряно своих</span><b>${res.lost.length}</b></div>
     <div class="kv"><span>Военный счёт</span><b>${ws.score > 0 ? '+' : ''}${ws.score}</b></div>
     <div class="kv"><span>Контроль фронта</span><b>${ws.control}%</b></div>
     <p>Захваченные земли пока только оккупированы. Чтобы граница их охватила — подпишите мир.</p>
     <div class="row-btns" style="margin-top:10px">
       <button class="btn ghost" id="again">Продолжить войну</button>
       <button class="btn green" id="peace">🕊️ Мир (${ws.score})</button>
     </div>`,
    true,
  );
  $('#again').onclick = () => {
    hidePanel();
    setMode('war');
  };
  $('#peace').onclick = () => {
    hidePanel();
    openPeace();
  };
}

// ---------- peace ----------
function openPeace(): void {
  const war = G.war!;
  const ws = warScore(W(), war);
  if (ws.score <= 0) return openDefeatOrWhite(ws.score);
  G.demands = availableDemands(W(), war);
  G.chosen = new Set(recommendPackage(W(), war, G.demands, ws.score).map((d) => d.id));
  G.mode = 'peace';
  renderTop();
  renderBottom();
  renderPeace();
}

function chosenCost(): number {
  return Math.round(G.demands.filter((d) => G.chosen.has(d.id)).reduce((s, d) => s + d.cost, 0) * 10) / 10;
}

function renderPeace(): void {
  const war = G.war!;
  const ws = warScore(W(), war);
  const used = chosenCost();
  const icon = (d: Demand): string => (d.kind === 'pocket' ? '⭕' : d.kind === 'annex' ? (d.hexes[0] === war.goal ? '🚩' : '⬢') : d.kind === 'contribution' ? '💰' : '📜');
  const rows = G.demands
    .map((d) => {
      const on = G.chosen.has(d.id);
      const fits = on || used + d.cost <= ws.score + 1e-9;
      return `<div class="demand ${on ? 'on' : ''} ${fits ? '' : 'no'}" data-id="${d.id}"><div class="ic">${icon(d)}</div><div class="tx">${d.label}</div><div class="pts">${d.cost}</div></div>`;
    })
    .join('');
  const sheet = showPanel(
    `<h2>📜 Мирный договор с «${enemyName(war.enemy)}»</h2>
     <p class="muted">Чем выше военный счёт, тем больше можно потребовать. ИИ согласится, если сумма не больше счёта. Ядро врага (столицу и 6 соседей) требовать нельзя.</p>
     <div class="budget"><span>Очки: ${used} / ${ws.score}</span><span>Контроль фронта ${ws.control}%</span></div>
     ${rows}
     <button class="btn green seal" id="seal" ${used <= ws.score + 1e-9 ? '' : 'disabled'}><span class="prog"></span>🔏 Удерживайте печать — подписать мир</button>
     <button class="btn ghost" id="back" style="width:100%;margin-top:8px">Назад к войне</button>`,
    false,
    true,
  );
  sheet.querySelectorAll<HTMLElement>('.demand').forEach((el) => {
    el.onclick = () => {
      const id = el.dataset.id!;
      const d = G.demands.find((x) => x.id === id)!;
      if (G.chosen.has(id)) G.chosen.delete(id);
      else if (chosenCost() + d.cost <= ws.score + 1e-9) G.chosen.add(id);
      sfx.tap();
      renderPeace();
    };
  });
  $('#back').onclick = () => {
    hidePanel();
    setMode('war');
  };
  attachHold($('#seal'), 800, () => signPeace());
}

function attachHold(btn: HTMLElement, ms: number, done: () => void): void {
  const prog = btn.querySelector<HTMLElement>('.prog');
  let start = 0;
  let raf = 0;
  const tick = (): void => {
    const k = Math.min(1, (performance.now() - start) / ms);
    if (prog) prog.style.width = `${k * 100}%`;
    if (k >= 1) {
      cancel();
      done();
      return;
    }
    raf = requestAnimationFrame(tick);
  };
  const cancel = (): void => {
    cancelAnimationFrame(raf);
    start = 0;
    if (prog) prog.style.width = '0';
  };
  btn.addEventListener('pointerdown', (e) => {
    if ((btn as HTMLButtonElement).disabled) return;
    e.preventDefault();
    start = performance.now();
    vibrate(20);
    raf = requestAnimationFrame(tick);
  });
  btn.addEventListener('pointerup', cancel);
  btn.addEventListener('pointerleave', cancel);
  btn.addEventListener('pointercancel', cancel);
}

function signPeace(): void {
  const war = G.war!;
  const w = W();
  const before = officialValue(w, PLAYER);
  const hexesBefore = playerHexCount();
  const oldPlayer = new Set(w.cells.filter((c) => c.owner === PLAYER).map((c) => c.id));
  const chosen = G.demands.filter((d) => G.chosen.has(d.id));
  const prevOwner = new Map<number, number>();
  for (const d of chosen) for (const h of d.hexes) prevOwner.set(h, w.cells[h]!.owner);
  const res = applyTreaty(w, war, chosen);
  normalizeArmies();
  hidePanel();
  sfx.seal();
  vibrate([40, 30, 80]);

  // ink wave order: hexes touching the old territory first, ~0.25 s per ring (canon §10.3)
  const annexedSet = new Set(res.annexed);
  const seeds = res.annexed.filter((id) => w.neighbors[id]!.some((n) => oldPlayer.has(n)));
  const rings = ringsFrom(w, seeds.length ? seeds : res.annexed.slice(0, 1), annexedSet);
  const flipAt = new Map<number, number>();
  let maxRing = 0;
  for (const id of res.annexed) {
    const r = rings.get(id) ?? 0;
    maxRing = Math.max(maxRing, r);
    flipAt.set(id, 1.6 + 0.25 * r + ((id * 37) % 7) * 0.02);
  }
  const cities = res.annexed.filter((id) => w.cells[id]!.kind === 'city').length;
  const summary = [
    res.annexed.length ? `+${res.annexed.length} гекс.${cities ? ` · +${cities} город` : ''}` : 'Земли не присоединены',
    `Держава ${before} → ${officialValue(w, PLAYER)}`,
    `Глава I: ${hexesBefore} → ${playerHexCount()} из ${CHAPTER_GOAL}`,
  ];
  if (res.goldPacks) summary.push(`💰 Контрибуция: ${res.goldPacks} × 4 ч золота`);
  if (res.reparations) summary.push('📜 Репарации: 10% производства на 24 ч');
  G.ceremony = { t: 0, flipAt, prevOwner, zoom: 1, annexed: res.annexed, summary, startedAt: performance.now() };
  G.truce.set(war.enemy, Date.now() + 30 * 60 * 1000); // chapter I truce 30 min
  G.war = null;
  G.flag = -1;
  G.mode = 'ceremony';
  renderTop();
  renderBottom();
  popIndex = 0;
  ceremonyDuration = Math.max(5.5, 1.6 + 0.25 * maxRing + 1.9);
}

let popIndex = 0;
let ceremonyDuration = 7;
function stepCeremony(): void {
  const c = G.ceremony!;
  c.t = (performance.now() - c.startedAt) / 1000;
  c.zoom = 1 - 0.08 * Math.min(1, Math.max(0, (c.t - 0.8) / 0.8));
  const flips = [...c.flipAt.entries()].sort((a, b) => a[1] - b[1]);
  while (popIndex < flips.length && c.t >= flips[popIndex]![1]) {
    sfx.pop(popIndex);
    vibrate(10);
    popIndex++;
  }
  const countersAt = ceremonyDuration - 3;
  let box = document.getElementById('counters');
  if (c.t >= countersAt && !box) {
    sfx.fanfare();
    box = document.createElement('div');
    box.id = 'counters';
    box.className = 'counters';
    box.innerHTML = c.summary.map((s) => `<div>${s}</div>`).join('');
    $('#app').appendChild(box);
    [...box.children].forEach((el, i) => setTimeout(() => el.classList.add('show'), i * 250));
  }
  if (c.t >= ceremonyDuration - 1.5 && G.mode === 'ceremony' && !document.getElementById('cer-done')) {
    const btn = document.createElement('button');
    btn.id = 'cer-done';
    btn.className = 'btn';
    btn.textContent = 'Продолжить';
    btn.style.cssText = 'position:absolute;left:16px;right:16px;bottom:calc(var(--safe-bottom) + 18px);z-index:16';
    btn.onclick = () => {
      document.getElementById('counters')?.remove();
      btn.remove();
      G.ceremony = null;
      setMode('map');
    };
    $('#app').appendChild(btn);
  }
}

function openDefeatOrWhite(score: number): void {
  const war = G.war!;
  if (Math.abs(score) < 10) {
    showPanel(
      `<h2>🕊️ Белый мир</h2><p>Счёт почти равный (${score}). Все оккупации вернутся владельцам, грабежа нет.</p>
       <div class="row-btns"><button class="btn ghost" id="back">Назад</button><button class="btn green" id="ok">Подписать</button></div>`,
      true,
    );
    $('#ok').onclick = () => {
      whitePeace(W());
      normalizeArmies();
      G.truce.set(war.enemy, Date.now() + 30 * 60 * 1000);
      G.war = null;
      hidePanel();
      setMode('map');
    };
  } else {
    // Defeat (canon §9.14): the AI annexes what it occupies, ≤20% of value, ≤1 city, never the core; plunder 60% (Wolf).
    const w = W();
    const core = coreOf(w, PLAYER);
    const limit = Math.floor(officialValue(w, PLAYER) * 0.2);
    let taken = 0;
    let cities = 0;
    const lost: number[] = [];
    for (const c of w.cells.filter((x) => x.owner === PLAYER && x.controller === war.enemy).sort((a, b) => b.value - a.value)) {
      if (core.has(c.id) || taken + c.value > limit || (c.kind === 'city' && cities >= 1)) continue;
      taken += c.value;
      if (c.kind === 'city') cities++;
      lost.push(c.id);
    }
    showPanel(
      `<h2>🏳️ Просить мира</h2><p>«${enemyName(war.enemy)}» требует ${lost.length} гекс. и разграбит 60% незащищённых складов (в прототипе экономики нет). Ядро державы потерять нельзя.</p>
       <div class="row-btns"><button class="btn ghost" id="back">Воевать дальше</button><button class="btn red" id="ok">Принять</button></div>`,
      true,
    );
    $('#ok').onclick = () => {
      for (const id of lost) {
        w.cells[id]!.owner = war.enemy;
        w.cells[id]!.controller = war.enemy;
      }
      whitePeace(w);
      normalizeArmies();
      G.truce.set(war.enemy, Date.now() + 30 * 60 * 1000);
      G.war = null;
      hidePanel();
      setMode('map');
      toast('Щит восстановления 24 ч и «Реванш» +15% (в полной игре)');
    };
  }
  $('#back').onclick = () => hidePanel();
}

// ---------- colonization ----------
function tryColonize(id: number): boolean {
  const w = W();
  const c = w.cells[id]!;
  if (c.owner !== NOBODY || !isPassable(c)) return false;
  if (!w.neighbors[id]!.some((n) => n >= 0 && w.cells[n]!.owner === PLAYER)) return false;
  c.owner = PLAYER;
  c.controller = PLAYER;
  sfx.pop(3);
  view.burst(id, COLORS.player);
  view.floatText(id, '+1 гекс', 0xbcd2ff);
  toast(`Колонизирован «${cellName(id)}» (в игре — золото и таймер 1 мин)`);
  renderTop();
  renderBottom();
  return true;
}

// ---------- input on the map ----------
interface Drag {
  army: Army;
  x: number;
  y: number;
  moved: boolean;
}
let drag: Drag | null = null;
let hoverHex = -1;
let lastTap = { army: -1, t: 0 };
let cardDrag: { card: CardId; x: number; y: number } | null = null;
let forecastEl: HTMLElement | null = null;

function canvasPoint(e: PointerEvent): { x: number; y: number } {
  const r = app.canvas.getBoundingClientRect();
  return { x: e.clientX - r.left, y: e.clientY - r.top };
}

app.canvas.addEventListener('pointerdown', (e) => {
  const p = canvasPoint(e);
  const hex = view.hexAt(p.x, p.y);
  if (hex < 0) return;
  if (G.mode === 'battle' && G.battle) {
    const a = G.battle.armies.find((x) => x.side === PLAYER && x.hex === hex && !x.move && x.str > 0);
    if (a) {
      drag = { army: a, x: p.x, y: p.y, moved: false };
      app.canvas.setPointerCapture(e.pointerId);
    }
    return;
  }
  onMapTap(hex);
});

app.canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  const p = canvasPoint(e);
  drag.x = p.x;
  drag.y = p.y;
  if (Math.hypot(p.x - view.centerOf(drag.army.hex).x, p.y - view.centerOf(drag.army.hex).y) > view.L.R * 0.6) drag.moved = true;
  hoverHex = view.hexAt(p.x, p.y);
});

app.canvas.addEventListener('pointerup', (e) => {
  if (!drag || !G.battle) return;
  const b = G.battle;
  const a = drag.army;
  const p = canvasPoint(e);
  const hex = view.hexAt(p.x, p.y);
  if (!drag.moved) {
    const now = performance.now();
    if (lastTap.army === a.id && now - lastTap.t < 350) {
      b.issue(PLAYER, { t: 'hold', army: a.id });
      toast(a.hold ? 'Позиция снята' : 'Держать позицию: +10% к защите');
    } else {
      showArmyInfo(a);
    }
    lastTap = { army: a.id, t: now };
  } else if (hex >= 0 && W().neighbors[a.hex]!.includes(hex)) {
    if (b.canTarget(PLAYER, hex)) {
      if (b.issue(PLAYER, { t: 'attack', army: a.id, target: hex })) {
        sfx.attack();
        vibrate(15);
      } else toast('Не хватает энергии (нужно 2)');
    } else if (W().cells[hex]!.controller === PLAYER) {
      if (!b.issue(PLAYER, { t: 'move', army: a.id, to: hex })) toast('Гекс занят');
    }
  }
  drag = null;
  hoverHex = -1;
});

function showArmyInfo(a: Army): void {
  const b = G.battle;
  const sup = b ? b.isSupplied(a.hex, a.side) : true;
  toast(`Армия: Сила ${Math.round(a.str / 1000)} / ${Math.round(a.maxStr / 1000)} · Пехота «Стойкость» +50% в обороне${sup ? '' : ' · БЕЗ СНАБЖЕНИЯ −20%'}`);
}

function onMapTap(hex: number): void {
  const w = W();
  const c = w.cells[hex]!;
  if (G.mode === 'pickGoal' && G.war) {
    const enemy = G.war.enemy;
    const valid = c.owner === enemy && !coreOf(w, enemy).has(hex);
    if (valid) {
      sfx.tap();
      showPanel(
        `<h2>⚔️ Объявить войну?</h2><p>Противник: <b>${enemyName(enemy)}</b>. Цель войны: <b>${cellName(hex)}</b> (ценность ${c.value}).</p>
         <p>Пока цель ваша — +10 к военному счёту. Оккупированное станет вашим только после мира.</p>
         <button class="btn red seal" id="declare" style="width:100%"><span class="prog"></span>Удерживайте — объявить войну</button>
         <button class="btn ghost" id="no" style="width:100%;margin-top:8px">Отмена</button>`,
        true,
      );
      attachHold($('#declare'), 800, () => {
        hidePanel();
        confirmWar(hex);
      });
      $('#no').onclick = () => hidePanel();
    } else toast(coreOf(w, enemy).has(hex) ? 'Ядро врага (столица и соседи) не может быть целью' : 'Выберите вражеский гекс');
    return;
  }
  if (G.mode === 'map' && tryColonize(hex)) return;
  const owner = w.states[c.owner]?.name ?? '';
  const occ = c.controller !== c.owner ? ` · оккупирован: ${w.states[c.controller]?.name}` : '';
  toast(`${cellName(hex)} · ценность ${c.value}${isPassable(c) ? ` · ${owner}${occ}` : ''}`);
}

// ---------- card drag ----------
function attachCardDrag(el: HTMLElement, card: CardId): void {
  el.addEventListener('pointerdown', (e) => {
    if (!G.battle) return;
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    cardDrag = { card, x: e.clientX, y: e.clientY };
    ghost.textContent = CARD_ART[card];
    ghost.classList.remove('hidden');
    moveGhost(e.clientX, e.clientY);
    sfx.tap();
  });
  el.addEventListener('pointermove', (e) => {
    if (!cardDrag) return;
    cardDrag.x = e.clientX;
    cardDrag.y = e.clientY;
    moveGhost(e.clientX, e.clientY);
  });
  const finish = (e: PointerEvent): void => {
    if (!cardDrag || !G.battle) return;
    const r = app.canvas.getBoundingClientRect();
    const hex = view.hexAt(e.clientX - r.left, e.clientY - r.top);
    const overHand = (e.target as HTMLElement | null)?.closest?.('#bottom') && e.clientY > bottom.getBoundingClientRect().top;
    if (hex >= 0 && !overHand) {
      if (G.battle.issue(PLAYER, { t: 'card', card: cardDrag.card, target: hex })) {
        if (cardDrag.card === 'airstrike') sfx.airstrike();
        else sfx.card();
        vibrate(20);
      } else {
        const b = G.battle;
        const pts = b.energyPoints(PLAYER);
        toast(pts < CARDS[cardDrag.card].cost ? `Нужно ${CARDS[cardDrag.card].cost} энергии` : 'Недопустимая цель');
      }
    }
    cardDrag = null;
    ghost.classList.add('hidden');
  };
  el.addEventListener('pointerup', finish);
  el.addEventListener('pointercancel', () => {
    cardDrag = null;
    ghost.classList.add('hidden');
  });
}

function moveGhost(x: number, y: number): void {
  ghost.style.left = `${x}px`;
  ghost.style.top = `${y}px`;
}

// ---------- frame loop ----------
let acc = 0;
let lastHud = 0;
app.ticker.add((tk) => {
  const dt = Math.min(0.1, tk.deltaMS / 1000);
  const b = G.battle;
  if (G.mode === 'battle' && b) {
    acc += dt;
    while (acc >= 1 / TICKS_PER_SEC && !b.over) {
      acc -= 1 / TICKS_PER_SEC;
      if (b.tick % TICKS_PER_SEC === 0 && G.war) {
        const ws = warScore(W(), G.war);
        b.lastStand = ws.control <= 30 ? PLAYER : null;
      }
      G.ai?.think(b);
      const n = b.events.length;
      b.step();
      for (const ev of b.events.slice(n)) handleEvent(ev);
    }
    if (b.over) endOffensive();
  }
  if (G.mode === 'ceremony' && G.ceremony) stepCeremony();

  const now = performance.now();
  if (now - lastHud > 250) {
    lastHud = now;
    if (G.mode === 'battle') renderTop();
    if (G.mode === 'map') renderBottom();
  }
  updateBattleHud();
  view.draw(drawState(now / 1000));
  updateForecast();
});

function handleEvent(ev: Battle['events'][number]): void {
  const war = G.war;
  switch (ev.type) {
    case 'capture':
      sfx.capture();
      view.burst(ev.hex, ev.side === PLAYER ? COLORS.player : COLORS.war);
      view.floatText(ev.hex, ev.side === PLAYER ? 'Оккупирован!' : 'Потерян', ev.side === PLAYER ? 0xbcd2ff : 0xffb3b3);
      if (war && ev.hex === war.goal && ev.side === PLAYER) toast('🚩 Цель войны взята: +10 к счёту');
      break;
    case 'repelled':
      sfx.repelled();
      view.floatText(ev.hex, ev.side === PLAYER ? 'Атака отбита' : 'Отбились!', 0xffffff);
      break;
    case 'routed':
      view.floatText(G.battle?.armyById(ev.army)?.hex ?? 0, 'Армия разбита', 0xffb347);
      break;
    case 'card':
      if (ev.card === 'airstrike') view.burst(ev.hex, 0xffa630, true);
      else view.burst(ev.hex, ev.side === PLAYER ? 0x9ad1ff : 0xff9a9a);
      if (ev.side !== PLAYER) view.floatText(ev.hex, CARDS[ev.card].name, 0xffb3b3);
      break;
    default:
      break;
  }
}

function drawState(time: number): DrawState {
  const highlights: Highlight[] = [];
  const b = G.battle;
  if (G.mode === 'pickGoal') {
    for (const id of G.goalChoices) highlights.push({ hex: id, color: 0xffffff, pulse: true });
  }
  if (G.mode === 'map') {
    for (const c of W().cells) {
      if (c.owner === NOBODY && isPassable(c) && W().neighbors[c.id]!.some((n) => n >= 0 && W().cells[n]!.owner === PLAYER)) {
        highlights.push({ hex: c.id, color: 0xdfe7ff });
      }
    }
  }
  if (G.mode === 'peace') {
    for (const d of G.demands) if (G.chosen.has(d.id)) for (const h of d.hexes) highlights.push({ hex: h, color: 0x7cff8a, pulse: true });
  }
  let dragLine: DrawState['dragLine'] = null;
  if (drag && drag.moved && b) {
    const from = view.centerOf(drag.army.hex);
    const valid = hoverHex >= 0 && W().neighbors[drag.army.hex]!.includes(hoverHex) && (b.canTarget(PLAYER, hoverHex) || W().cells[hoverHex]!.controller === PLAYER);
    dragLine = { from, to: { x: drag.x, y: drag.y }, color: valid ? 0xffffff : 0x999999 };
    for (const n of W().neighbors[drag.army.hex]!) if (n >= 0 && b.canTarget(PLAYER, n)) highlights.push({ hex: n, color: 0xff8080 });
  }
  if (cardDrag && b) {
    const spec = CARDS[cardDrag.card];
    for (const c of W().cells) {
      const ok = b.validate(PLAYER, { t: 'card', card: cardDrag.card, target: c.id }) || (spec.target === 'enemy' && b.canTarget(PLAYER, c.id) && cardDrag.card !== 'attack' && cardDrag.card !== 'breakthrough');
      if (ok) highlights.push({ hex: c.id, color: spec.target === 'own' ? 0x9ad1ff : 0xff8080 });
    }
  }
  return {
    world: W(),
    armies: b ? b.armies : G.armies,
    battle: b,
    atWarWith: G.war?.enemy ?? null,
    goal: G.war && (G.mode === 'war' || G.mode === 'battle' || G.mode === 'result') ? G.war.goal : -1,
    flag: G.mode === 'battle' ? G.flag : -1,
    highlights,
    pocketHexes: G.war ? enemyPocketHexes(W(), G.war) : [],
    dragLine,
    forecast: null,
    ceremony: G.ceremony,
    time,
  };
}

function updateForecast(): void {
  const b = G.battle;
  let target = -1;
  let armies: number[] = [];
  let bt = false;
  if (b && drag && drag.moved && hoverHex >= 0 && W().neighbors[drag.army.hex]!.includes(hoverHex) && b.canTarget(PLAYER, hoverHex)) {
    target = hoverHex;
    armies = [drag.army.id];
  } else if (b && cardDrag && (cardDrag.card === 'attack' || cardDrag.card === 'breakthrough')) {
    const r = app.canvas.getBoundingClientRect();
    const hex = view.hexAt(cardDrag.x - r.left, cardDrag.y - r.top);
    if (hex >= 0 && b.canTarget(PLAYER, hex)) {
      const adj = b.adjacentIdleArmies(PLAYER, hex);
      if (adj.length) {
        target = hex;
        bt = cardDrag.card === 'breakthrough';
        armies = bt ? [adj.sort((x, y) => y.str - x.str)[0]!.id] : adj.map((a) => a.id);
      }
    }
  }
  if (target < 0 || !b) {
    forecastEl?.remove();
    forecastEl = null;
    return;
  }
  const fc = b.forecast(PLAYER, armies, target, bt);
  if (!forecastEl) {
    forecastEl = document.createElement('div');
    forecastEl.className = 'forecast';
    $('#app').appendChild(forecastEl);
  }
  const color = fc.f >= 1.3 ? '#7cff8a' : fc.f >= 0.9 ? '#ffd166' : '#ff6b6b';
  const p = view.centerOf(target);
  const r = app.canvas.getBoundingClientRect();
  forecastEl.style.borderColor = color;
  forecastEl.style.color = color;
  forecastEl.style.left = `${r.left + p.x}px`;
  forecastEl.style.top = `${r.top + p.y - view.L.R * 2.1}px`;
  forecastEl.textContent = `⚔ ×${fc.f >= 10 ? '10+' : fc.f.toFixed(1)}${fc.forms.length ? ' · ' + fc.forms.join(' · ') : ''}`;
}

// ---------- boot ----------
renderTop();
renderBottom();
relayout();
showIntro();

// Expose for automated screenshots/tests.
(window as unknown as { __raivon: unknown }).__raivon = { G, view, startPickGoal, confirmWar, startOffensive, openPeace, signPeace };
