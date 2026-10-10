export const meta = {
  name: 'soft-style-continue',
  description: 'Continuation (args-driven, restart-safe) — implement the soft cartoon style (art_direction §6): map/light lane (tooling, grade, soft model shading, rounded ribbons, fills, ground, coast, water, grass, world edge, markers) and Blender model lane (soft bake, trees, buildings, rocks, troops, districts, re-export), each step implemented, independently reviewed with screenshots, fixed',
  phases: [
    { title: 'Map', detail: 'map and light steps in order, each implement → review → fix' },
    { title: 'Models', detail: 'Blender model steps after the soft shading lands' },
    { title: 'Final', detail: 'calibration against the §6.12 targets' },
  ],
}

const SCRATCH = '/tmp/claude-0/-home-user-Raivon/6fa81df3-3b92-5348-855c-cb135734d3b5/scratchpad'

const STEPS = {
  T0: { title: 'Tooling: visible shader errors, look metrics, standard shot set, baseline', lane: 'map' },
  G1: { title: 'Sunny grade and soft light', lane: 'map' },
  M1: { title: 'Soft toon shading for every model, no re-export', lane: 'map' },
  P1: { title: 'Rounded candy ribbons replace the neon borders, white cores and the inner hex grid', lane: 'map' },
  P2: { title: 'Rounded inward territory fill, soft scorch and soft occupation hatch (distance field)', lane: 'map' },
  P3: { title: 'Continuous sunny ground: blended corners, no inner walls, calm shader, soft rounded hex seams', lane: 'map' },
  P4: { title: 'Rounded coastline geometry', lane: 'map' },
  P5: { title: 'Beach rim, cartoon water with SDF foam, softer rivers and roads', lane: 'map' },
  P6: { title: 'Calm grass: fewer rounded tufts, flowers, clean lawn from afar', lane: 'map' },
  P7: { title: 'Soft world edge: rounded fog cookies over a slate underlay, puffy two-tone clouds', lane: 'map' },
  P8: { title: 'Soft markers, FX and juice: selection, deposits, health pills, burst, strike arrow, capture pop', lane: 'map' },
  B0: { title: 'Blender: painted AO in the bake, softer procedural textures, lighter palette', lane: 'models' },
  B5: { title: 'Blender: rounded trees and bushes', lane: 'models' },
  B1: { title: 'Blender: shared building helpers — fat roofs, round ridges and finials, bigger windows, soft masses', lane: 'models' },
  B2: { title: 'Blender: capital/residence DL1–4 — chunky, friendly silhouettes', lane: 'models' },
  B3: { title: 'Blender: towns DL1–4 and homesteads — fewer, bigger, rounder houses', lane: 'models' },
  B6: { title: 'Blender: soft rocks, crags and friendly mountains', lane: 'models' },
  B7: { title: 'Blender: chunky troops DL1–4 without breaking the troop animation', lane: 'models' },
  B4: { title: 'Blender: DL8 districts and capital/city DL8 without the tile look', lane: 'models' },
  B8: { title: 'Re-export every model with the soft bake, palette and helpers', lane: 'models' },
  B9: { title: 'Re-render UI art (cards, icons, portraits) under the soft light', lane: 'models' },
  F1: { title: 'Calibrate against the §6 targets, unify 3D text, document and publish screenshots', lane: 'final' },
}
const MAP_ORDER = ['T0', 'G1', 'M1', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7', 'P8']
const MODEL_ORDER = ['B0', 'B5', 'B1', 'B2', 'B3', 'B6', 'B7', 'B4', 'B8', 'B9']

const COMMON = `
Project: /home/user/Raivon — «Raivon: Territory Wars», a portrait mobile hex-territory strategy in Godot 4.5.1 (phones run the
Mobile renderer; tools/godot_shot.sh shoots with it). The owner's verdict (verbatim): «У тебя выходит слишком строгий и острый
дизайн. Особенно гексы. Сделай это более приятно для глаза. Находи примеры в интернете, но не копируй. Также сделай более
мультяшный дизайн (в качестве примера бери Clash of Clans).» The team researched and wrote the specification: READ
docs/art_direction.md §6 «Мультяшный стиль "Raivon Soft"» in full before you start (palette, radii SOFT_R, light, materials,
territory, ground, models, metrics §6.12, budgets). The step-by-step plan with the FULL instructions of every step is in
docs/dev/soft_style_plan.json — find your step by its id and follow its instructions and verify section exactly (adapt only
where the code proves an instruction wrong, and say so).
Rules:
- Several agents work in this repo at the same time on DIFFERENT files (a map/light lane, a Blender model lane and a UI lane
  that restyles game/scripts/game_ui.gd, hud.gd, shop_ui.gd). Edit only the files your step owns (listed in the plan; small
  necessary touches elsewhere are allowed if you state them). Re-read a file right before editing it; never revert changes you
  did not make.
- You MAY run the game for screenshots: tools/godot_shot.sh OUT.png [--zoom=..] [--focus=q,r,zoom] [--dl=N] [--ai-dl=N]
  [--demo=..] --lang=ru --shot-delay=3 (~1–2 min each), and the tests: /opt/godot/Godot_v4.5.1-stable_linux.x86_64 --headless
  --path game --script res://tests/test_flow.gd (expect 224 PASS lines and no "SCRIPT ERROR"; also test_sim, test_economy,
  test_ring, test_deposits, test_commanders, test_camps, test_march when you touch gameplay-adjacent code). Read every PNG you
  make (they are images) and judge it honestly against §6 and the owner's words.
- Only the Blender model lane runs "/opt/godot/Godot_v4.5.1-stable_linux.x86_64 --headless --path game --import" (after
  exporting GLBs or adding textures); the map lane must not run --import (it only changes scripts and shaders, which load
  without it). If your step adds a texture or font, say so in your result so the main session imports it.
- NEVER run git commit/add/push/checkout/stash/reset (git diff/status are fine). The main session commits.
- Keep phone performance: draw calls and primitives within §6.2 budgets (godot_shot prints "perf draw_calls=…").
- Put scratch files and screenshots under ${SCRATCH}/soft/<step id>/ .
`

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    step: { type: 'string' },
    done: { type: 'boolean' },
    changes: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, what: { type: 'string' } }, required: ['file', 'what'] } },
    screenshots: { type: 'array', items: { type: 'string' } },
    metrics: { type: 'string' },
    tests: { type: 'string' },
    needs_import: { type: 'boolean' },
    deviations: { type: 'string' },
    notes: { type: 'string' },
  },
  required: ['step', 'done', 'changes', 'screenshots'],
}
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string', enum: ['high', 'medium', 'low'] }, problem: { type: 'string' }, fix_hint: { type: 'string' } },
      required: ['severity', 'problem'] } },
    softer_than_before: { type: 'string' },
    screenshots: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['ok', 'issues', 'summary'],
}

function implPrompt(id) {
  return `${COMMON}
YOUR STEP: ${id} — ${STEPS[id].title}. Open docs/dev/soft_style_plan.json, read step "${id}" (instructions, owner_files, verify)
and implement it fully. Take before screenshots first (or reuse the baseline from step T0 under ${SCRATCH}/soft/T0/ if it exists),
then after screenshots, and compare. Return the structured result (files changed, screenshots, metrics from tools/look_metrics.py
if it exists, test results, deviations from the plan).`
}
function reviewPrompt(id, impl) {
  return `${COMMON}
You are an independent, demanding REVIEWER of step ${id} — ${STEPS[id].title}. Do not edit project files.
The implementer reported: ${JSON.stringify(impl, null, 1)}
Check against the step's instructions and verify section in docs/dev/soft_style_plan.json and against docs/art_direction.md §6:
take your own screenshots (strategic default, --zoom=0.3 --dl=3 --ai-dl=3, a close --focus=0,3,0.06, and whatever the step
needs, e.g. --dl=8 --ai-dl=8 or a demo), read them, and judge: does it look clearly softer, rounder, friendlier and more cartoon
(owner: like Clash of Clans, without copying)? Look for regressions: broken or missing borders/fills, wrong colours, black or
neon leftovers, z-fighting, things disappearing, armies/labels/selection broken, shader errors in the log, performance over
budget, failing tests (run test_flow if scripts changed). Set ok=true only if no high/medium issue remains. Be concrete.`
}
function fixPrompt(id, impl, review) {
  return `${COMMON}
YOUR STEP: fix the reviewer's issues for step ${id} — ${STEPS[id].title} (plan: docs/dev/soft_style_plan.json).
Implementer report: ${JSON.stringify(impl, null, 1)}
Reviewer issues (fix every high and medium; low when cheap): ${JSON.stringify(review.issues, null, 1)}
Verify with screenshots and tests, then return the same structured result as the implementation.`
}

async function runStep(id, phaseName) {
  const impl = await agent(implPrompt(id), { label: `${id}:impl`, phase: phaseName, schema: IMPL_SCHEMA })
  if (!impl) { log(`${id}: no result`); return { id, impl: null } }
  const review = await agent(reviewPrompt(id, impl), { label: `${id}:review`, phase: phaseName, schema: REVIEW_SCHEMA })
  const blocking = (review && review.issues ? review.issues : []).filter((i) => i.severity !== 'low')
  if (review && review.ok && blocking.length === 0) { log(`${id}: review passed`); return { id, impl, review, fix: null } }
  log(`${id}: ${blocking.length} blocking issue(s) — fixing`)
  const fix = await agent(fixPrompt(id, impl, review || { issues: [] }), { label: `${id}:fix`, phase: phaseName, schema: IMPL_SCHEMA })
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
