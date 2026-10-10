export const meta = {
  name: 'ui-redesign-continue',
  description: 'Continuation (args-driven, restart-safe) — implement the new UI design system (docs/ui_style.md): kit + icons, then HUD, tabs and cards, hex panel and action button, war screens, tab cards, shop/pass/meta, collections, dialogs, FTUE coach, toasts, final sweep — each step implemented, independently reviewed with screenshots, fixed',
  phases: [
    { title: 'Kit', detail: 'UI kit (fonts, tokens, components) and the 3D icon set in parallel' },
    { title: 'Screens', detail: 'screen groups in a strict chain (shared files)' },
    { title: 'Sweep', detail: 'final sweep and lint' },
  ],
}

const SCRATCH = '/tmp/claude-0/-home-user-Raivon/6fa81df3-3b92-5348-855c-cb135734d3b5/scratchpad'

const TITLES = {
  s01_kit: 'UI kit: bundled fonts, ui_kit.gd tokens/components, legacy helpers delegate (global restyle)',
  s02_icons: '3D icon set: new icons, re-rendered food/metal/oil, ink rim, building card art',
  s03_hud_top: 'HUD frame: resource pills on a currency layer, top scrim, ruler portrait, left column, minimap',
  s04_tabs_tray_army: 'Bottom folder tabs, card tray, Kit.card component, Army tab cards',
  s05_hex_action: 'Hex panel and the single big action button',
  s06_war_screens: 'War HUD: control bar, battle hand, drag ghost, result, peace treaty, ultimatum, ceremony',
  s07_tab_cards: 'Buildings, Development, Diplomacy and World tab cards; leader dialog; alarm',
  s08_meta_shop_pass: 'Shop, War Pass, Chronicle, Patent, Settings on the paper modal language',
  s09_meta_collections: 'Commanders, commander card and picker, hand picker, calendar, profile, inbox, flag editor',
  s10_dialogs: 'Generic dialogs, market, territory swap, ally ask, separate peace',
  s11_ftue_coach: 'FTUE coach: spotlight, ring, pointer, advisor bubble',
  s12_toasts: 'Toasts: slate pill with icon, queue and merge',
  s14_final_sweep: 'Final sweep: no pictographs or Color literals left, lint, docs, full screenshot set',
}
const CHAIN = ['s03_hud_top', 's04_tabs_tray_army', 's05_hex_action', 's06_war_screens', 's07_tab_cards', 's08_meta_shop_pass',
  's09_meta_collections', 's10_dialogs', 's11_ftue_coach', 's12_toasts']

const COMMON = `
Project: /home/user/Raivon — «Raivon: Territory Wars», a portrait mobile hex-territory strategy in Godot 4.5.1. The owner's
verdicts (verbatim): «по интерфейсу у тебя выходит жесткий нейрослоп. Сделай нормальный интерфейс.» and «сделай более
мультяшный дизайн (в качестве примера бери Clash of Clans). Находи примеры в интернете, но не копируй.» The team audited 31
screens, researched mobile game UI and wrote the design system: READ docs/ui_style.md in full before you start (tokens, fonts
Rubik + Nunito, components, screen notes). The step plan with the FULL instructions of every step is docs/dev/ui_plan.json —
find your step by id and follow its instructions and verify section exactly (adapt only where the code proves an instruction
wrong, and say so). The world itself is being restyled in parallel (docs/art_direction.md §6) — the UI must sit well on a
brighter, softer, sunnier map.
Rules:
- Other agents work in this repo at the same time: a map/light lane edits game/scripts/map_view.gd, game/scripts/main.gd
  (environment/lighting only), game/shaders/*, and a Blender model lane edits tools/blender/*.py (except icon_assets.py and
  card_art.py until it reaches its last step) and game/assets/models/*. Edit only the files your step owns (listed in the plan);
  for main.gd keep to UI wiring. Do NOT edit game/scripts/map_view.gd (in-world labels are a later step). Re-read a file right
  before editing it; never revert changes you did not make.
- Fonts/textures need a Godot import: before running "/opt/godot/Godot_v4.5.1-stable_linux.x86_64 --headless --path game
  --import", check that no other import runs (pgrep -fa -- '--import' must show nothing but your own grep), else wait and retry.
- Screenshots: tools/godot_shot.sh OUT.png [--demo=..] [--tab=..] [--select=q,r] [--dl=N] --lang=ru --shot-delay=3 (expansion
  demos like dip2/coalition/swap need --shot-delay=12..22). Read every PNG you make (they are images) and judge it honestly as a
  player would: does it look like a polished shipped mobile game, friendly and cartoon, consistent, readable, not AI slop?
  Also check --lang=en for text fitting where your screens have long strings.
- Tests: /opt/godot/Godot_v4.5.1-stable_linux.x86_64 --headless --path game --script res://tests/test_flow.gd must keep 224
  PASS lines and no "SCRIPT ERROR"; run the other suites in game/tests/ when you touch logic.
- NEVER run git commit/add/push/checkout/stash/reset (diff/status are fine). The main session commits.
- Put scratch files under ${SCRATCH}/ui_impl/<step id>/ .
`

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    step: { type: 'string' }, done: { type: 'boolean' },
    changes: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, what: { type: 'string' } }, required: ['file', 'what'] } },
    screenshots: { type: 'array', items: { type: 'string' } },
    tests: { type: 'string' }, deviations: { type: 'string' }, notes: { type: 'string' },
  },
  required: ['step', 'done', 'changes', 'screenshots'],
}
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string', enum: ['high', 'medium', 'low'] }, screen: { type: 'string' }, problem: { type: 'string' }, fix_hint: { type: 'string' } },
      required: ['severity', 'problem'] } },
    screenshots: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['ok', 'issues', 'summary'],
}

function implPrompt(id) {
  return `${COMMON}
YOUR STEP: ${id} — ${TITLES[id]}. Open docs/dev/ui_plan.json, read step "${id}" (instructions, owner_files, functions, verify)
and implement it fully. Screenshot the affected screens before and after, compare, run the tests, return the structured result.`
}
function reviewPrompt(id, impl) {
  return `${COMMON}
You are an independent, demanding senior game UI REVIEWER of step ${id} — ${TITLES[id]}. Do not edit project files.
The implementer reported: ${JSON.stringify(impl, null, 1)}
Check against step ${id} in docs/dev/ui_plan.json and against docs/ui_style.md. Take your own screenshots of every screen the
step touches (ru and en), read them closely and judge like a player and like an art director: consistency with the design
system (tokens, fonts, radii, outlines, buttons, colours by role), readability on a phone, hierarchy and one primary action,
no emoji/glyph icons or text walls left on these screens, nothing overlapping or cut off, no leftover "dark web dashboard"
look, works on the brighter map, tests green (run test_flow). Set ok=true only if no high/medium issue remains. Be concrete.`
}
function fixPrompt(id, impl, review) {
  return `${COMMON}
YOUR STEP: fix the reviewer's issues for step ${id} — ${TITLES[id]} (plan: docs/dev/ui_plan.json).
Implementer report: ${JSON.stringify(impl, null, 1)}
Reviewer issues (fix every high and medium; low when cheap): ${JSON.stringify(review.issues, null, 1)}
Verify with screenshots and tests, then return the same structured result as the implementation.`
}

async function runStep(id, ph) {
  const impl = await agent(implPrompt(id), { label: `${id}:impl`, phase: ph, schema: IMPL_SCHEMA })
  if (!impl) { log(`${id}: no result`); return { id, impl: null } }
  const review = await agent(reviewPrompt(id, impl), { label: `${id}:review`, phase: ph, schema: REVIEW_SCHEMA })
  const blocking = (review && review.issues ? review.issues : []).filter((i) => i.severity !== 'low')
  if (review && review.ok && blocking.length === 0) { log(`${id}: review passed`); return { id, impl, review, fix: null } }
  log(`${id}: ${blocking.length} blocking issue(s) — fixing`)
  const fix = await agent(fixPrompt(id, impl, review || { issues: [] }), { label: `${id}:fix`, phase: ph, schema: IMPL_SCHEMA })
  return { id, impl, review, fix }
}


const RESUME = '/tmp/claude-0/-home-user-Raivon/6fa81df3-3b92-5348-855c-cb135734d3b5/scratchpad/resume_args.json'

function noteImpl(id) { return `The implementation of step ${id} is finished; its full structured report is the JSON value of key "${id}_impl" in ${RESUME} — read it first.` }

async function runFrom(item, ph) {
  const id = item.id
  const start = item.start || 'impl'
  if (start === 'impl') return runStep(id, ph)
  const impl = { step: id, done: true, note: noteImpl(id) }
  let review = null
  if (start === 'review') {
    review = await agent(reviewPrompt(id, impl), { label: `${id}:review`, phase: ph, schema: REVIEW_SCHEMA })
    const blocking = (review && review.issues ? review.issues : []).filter((i) => i.severity !== 'low')
    if (review && review.ok && blocking.length === 0) { log(`${id}: review passed`); return { id, review, fix: null } }
  } else {
    review = { issues: [{ severity: 'high', problem: `The reviewer's verdict for step ${id} is the JSON value of key "${id}_review" in ${RESUME} — read it and fix every high and medium issue (low when cheap). A previous fix agent was interrupted by a container restart; its partial edits are committed (git log -p -3 for the step's files) — inspect them, keep what is right, finish.` }] }
  }
  const fix = await agent(fixPrompt(id, impl, review || { issues: [] }), { label: `${id}:fix`, phase: ph, schema: IMPL_SCHEMA })
  return { id, review, fix }
}

const PLAN = args || { lanes: [] }
const lanes = await parallel(PLAN.lanes.map((lane, li) => async () => {
  const out = []
  for (const item of lane) out.push(await runFrom(item, item.phase || (PLAN.phases ? PLAN.phases[li] : 'Run')))
  return out
}))
let final = null
if (PLAN.final) final = await runFrom({ id: PLAN.final }, 'Final')
return { lanes, final }
