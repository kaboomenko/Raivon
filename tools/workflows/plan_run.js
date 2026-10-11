export const meta = {
  name: 'plan-run',
  description: 'Generic args-driven, restart-safe runner for a step plan in docs/dev/*.json: lanes of steps run in parallel, each step implemented, independently reviewed with screenshots, fixed; optional final step',
  phases: [
    { title: 'Lanes', detail: 'parallel lanes, steps in each lane in order (implement → review → fix)' },
    { title: 'Final', detail: 'final step after all lanes' },
  ],
}

// args: {"plan": "docs/dev/hud_perf_plan.json", "lanes": [[{"id": "H1", "start": "impl|review|fix"}, ...], ...], "final": "F1"}
// start: impl (default); review — the implementer finished, its report is key "<id>_impl" of RESUME; fix — the reviewer
// finished, its verdict is key "<id>_review" of RESUME (docs/dev/restart.md).
const RESUME = '/tmp/claude-0/-home-user-Raivon/6fa81df3-3b92-5348-855c-cb135734d3b5/scratchpad/resume_args.json'
const PLAN = args || { lanes: [] }
const PLAN_FILE = PLAN.plan

const HEAD = `Project: /home/user/Raivon. The step plan is ${PLAN_FILE}: READ its "common" section (context and rules — follow
them strictly) and your step (instructions, owner_files, verify) before anything else. Adapt an instruction only where the
code proves it wrong, and say so in your report.`

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    step: { type: 'string' }, done: { type: 'boolean' },
    changes: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, what: { type: 'string' } }, required: ['file', 'what'] } },
    measurements: { type: 'string' },
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
    measurements: { type: 'string' },
    screenshots: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
  },
  required: ['ok', 'issues', 'summary'],
}

function implPrompt(id) {
  return `${HEAD}
YOUR STEP: ${id}. Implement it fully. Measure and screenshot before and after, compare, run the tests, return the structured
result (put the numbers in "measurements").`
}
function reviewPrompt(id, impl) {
  return `${HEAD}
You are an independent, demanding REVIEWER of step ${id} (senior engine programmer and game UI art director in one). Do not
edit project files. The implementer reported: ${JSON.stringify(impl, null, 1)}
Check the work against the step and the common rules: re-measure yourself (do not trust the reported numbers), take your own
screenshots of every screen the step touches and compare them with the "before" state (git stash is forbidden — use the
implementer's baseline shots and diff images, or reason from the diff), read the code diff (git diff) for correctness, input
handling, resize, leaks (textures/viewports created per frame), and anything that could break on a phone. Tests must be green
(run test_flow). Set ok=true only if no high/medium issue remains. Be concrete: file, function, screen, numbers.`
}
function fixPrompt(id, impl, review) {
  return `${HEAD}
YOUR STEP: fix the reviewer's issues for step ${id}.
Implementer report: ${JSON.stringify(impl, null, 1)}
Reviewer issues (fix every high and medium; low when cheap): ${JSON.stringify(review.issues, null, 1)}
Verify with measurements, screenshots and tests, then return the same structured result as the implementation.`
}

function noteImpl(id) { return `The implementation of step ${id} is finished; its full structured report is the JSON value of key "${id}_impl" in ${RESUME} — read it first.` }

async function runFrom(item, ph) {
  const id = item.id
  const start = item.start || 'impl'
  let impl = null
  if (start === 'impl') {
    impl = await agent(implPrompt(id), { label: `${id}:impl`, phase: ph, schema: IMPL_SCHEMA })
    if (!impl) { log(`${id}: no result`); return { id, impl: null } }
  } else {
    impl = { step: id, done: true, note: noteImpl(id) }
  }
  let review = null
  if (start !== 'fix') {
    review = await agent(reviewPrompt(id, impl), { label: `${id}:review`, phase: ph, schema: REVIEW_SCHEMA })
    const blocking = (review && review.issues ? review.issues : []).filter((i) => i.severity !== 'low')
    if (review && review.ok && blocking.length === 0) { log(`${id}: review passed`); return { id, impl, review, fix: null } }
    log(`${id}: ${blocking.length} blocking issue(s) — fixing`)
  } else {
    review = { issues: [{ severity: 'high', problem: `The reviewer's verdict for step ${id} is the JSON value of key "${id}_review" in ${RESUME} — read it and fix every high and medium issue (low when cheap). A previous fix agent may have been interrupted by a container restart; its partial edits are committed (git log -p -3 for the step's files) — inspect them, keep what is right, finish.` }] }
  }
  const fix = await agent(fixPrompt(id, impl, review || { issues: [] }), { label: `${id}:fix`, phase: ph, schema: IMPL_SCHEMA })
  return { id, impl, review, fix }
}

const lanes = await parallel(PLAN.lanes.map((lane) => async () => {
  const out = []
  for (const item of lane) out.push(await runFrom(item, 'Lanes'))
  return out
}))
let final = null
if (PLAN.final) {
  final = await runFrom({ id: PLAN.final }, 'Final')
}
return { lanes, final }
