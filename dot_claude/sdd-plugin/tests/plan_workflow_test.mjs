// drives workflows/plan.js against a stubbed Workflow runtime — the point of
// the script is the derived set math, so that is what gets exercised.
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'workflows', 'plan.js')
const body = readFileSync(SRC, 'utf8').replace('export const meta', 'const meta')

async function run(args, agentImpl) {
  const spawns = []
  const agent = async (prompt, opts) => {
    spawns.push({ label: opts.label, agentType: opts.agentType, effort: opts.effort,
                  model: opts.model, phase: opts.phase, prompt })
    return agentImpl(opts, prompt, spawns.length)
  }
  const parallel = ths => Promise.all(ths.map(t => t().catch(() => null)))
  const fn = new Function('agent', 'parallel', 'log', 'phase', 'args',
    `return (async () => {\n${body}\n})()`)
  const out = await fn(agent, parallel, () => {}, () => {}, args)
  return { out, spawns }
}

const base = { slug: 'feat', workdir: '/wt/feat', models: { 'sdd-planner': 'opus' } }

const T = (id, files, kw = {}) => ({
  id, title: `do ${id}`, requirements: kw.requirements || [`R${id.slice(1)}`],
  files, depends_on: kw.depends_on || [], parallel_ok: kw.parallel_ok !== false,
  complexity: kw.complexity || 'standard', verify: `make test-${id}`,
})

// T1/T3 share decoder.py; T2 is disjoint
const PLAN = {
  tasks: [T('T1', ['decoder.py', 'test_decoder.py']),
          T('T2', ['parser.py'], { complexity: 'simple' }),
          T('T3', ['decoder.py'], { depends_on: ['T1'] })],
  coverage: { R1: ['T1'], R2: ['T2'], R3: ['T3'] },
  unplannable: [],
}

const checks = []
const ok = (name, cond, extra = '') =>
  checks.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  <-- ' + extra}`)

// 1. the table, and the paths that must NOT come back with it
{
  const { out, spawns } = await run(base, () => PLAN)
  ok('table: one row per task', out.tasks.length === 3)
  ok('table: files reduced to a count', out.tasks[0].files === 2, JSON.stringify(out.tasks[0]))
  ok('table: no path strings anywhere', !JSON.stringify(out).includes('decoder.py'))
  ok('table: no verify commands', !JSON.stringify(out).includes('make test-'))
  ok('table: keeps what state.md mirrors',
    out.tasks[2].depends_on.join() === 'T1' && out.tasks[1].complexity === 'simple')
  ok('counts: simple vs standard', out.simple === 1 && out.standard === 2)
  ok('spawn: planner at xhigh, routed from the map',
    spawns.length === 1 && spawns[0].effort === 'xhigh' && spawns[0].model === 'opus',
    JSON.stringify(spawns[0]))
  ok('spawn: label is plain planner', spawns[0].label === 'planner')
}

// 2. conflicts are computed from the file sets, both directions
{
  const { out } = await run(base, () => PLAN)
  const byId = Object.fromEntries(out.tasks.map(t => [t.id, t]))
  ok('conflicts: T1 <-> T3', byId.T1.conflicts.join() === 'T3' && byId.T3.conflicts.join() === 'T1',
    JSON.stringify(out.tasks.map(t => [t.id, t.conflicts])))
  ok('conflicts: disjoint task has none', byId.T2.conflicts.length === 0)
}

// 3. a parallel_ok claim the paths contradict is surfaced, not silently trusted
{
  const { out } = await run(base, () => PLAN)
  ok('disputed: both overlapping tasks named', out.parallel_ok_disputed.length === 2,
    JSON.stringify(out.parallel_ok_disputed))
  const clean = await run(base, () => ({
    ...PLAN, tasks: PLAN.tasks.map(t => (t.id === 'T3' ? { ...t, parallel_ok: false } : t)) }))
  ok('disputed: an honest parallel_ok:false is not disputed',
    clean.out.parallel_ok_disputed.length === 1,
    JSON.stringify(clean.out.parallel_ok_disputed))
}

// 4. coverage checked against the SPEC's requirement ids when given
{
  const { out } = await run({ ...base, requirements: ['R1', 'R2', 'R3', 'R9'] }, () => PLAN)
  ok('coverage: gap found', out.coverage_gaps.join() === 'R9', JSON.stringify(out.coverage_gaps))
  ok('coverage: counts per requirement', out.coverage_counts.R1 === 1)
  const bare = await run(base, () => PLAN)
  ok('coverage: no spec ids -> no invented gaps', bare.out.coverage_gaps.length === 0)
}

// 5. the planner's two self-reports disagreeing is itself a finding
{
  const { out } = await run(base, () => ({
    ...PLAN, coverage: { ...PLAN.coverage, R4: ['T2'] } }))
  ok('disputed coverage: named', out.coverage_disputed.join() === 'R4',
    JSON.stringify(out.coverage_disputed))
}

// 6. unplannable passes straight through — gate 1 needs it
{
  const { out } = await run(base, () => ({
    ...PLAN, unplannable: [{ requirement: 'R5', why: 'needs hardware' }] }))
  ok('unplannable: passed through', out.unplannable[0].why === 'needs hardware')
}

// 7. a revision run says so, in the label and the prompt
{
  const { out, spawns } = await run({ ...base, revision: 'gate 1: split T2' }, () => PLAN)
  ok('revision: labelled', spawns[0].label === 'planner:revision')
  ok('revision: reason reaches the planner', spawns[0].prompt.includes('split T2'))
  ok('revision: flagged in the result', out.revised === true)
}

// 8. a dead planner is a gap, not an empty plan
{
  const { out } = await run(base, () => null)
  ok('planner death: reported', out.planned === false && out.failed === 'planner')
}

// 9. args handling
{
  const { out } = await run(JSON.stringify(base), () => PLAN)
  ok('args: json string is parsed, not fatal', out.planned === true)
  let threw = null
  await run({ slug: 'feat' }, () => PLAN).catch(e => { threw = e.message })
  ok('args: missing workdir throws', !!threw, 'did not throw')
  // a task with no files must not crash the set math
  const { out: sparse } = await run(base, () => ({
    ...PLAN, tasks: [...PLAN.tasks, { ...T('T4', []), files: undefined }] }))
  ok('args: a task without files degrades to zero conflicts',
    sparse.tasks[3].files === 0 && sparse.tasks[3].conflicts.length === 0)
}

console.log(checks.join('\n'))
const bad = checks.filter(c => c.startsWith('FAIL')).length
console.log(`\n${checks.length - bad}/${checks.length} passed`)
process.exit(bad ? 1 : 0)
