// drives workflows/implement.js against a stubbed Workflow runtime, so the
// retry ladder / escalation routing / thin-row rules are actually executed.
import { readFileSync } from 'fs'

const SRC = '/home/jasyang/dotfiles/claude/sdd-plugin/workflows/implement.js'
const body = readFileSync(SRC, 'utf8').replace('export const meta', 'const meta')

async function run(args, agentImpl) {
  const spawns = []
  const agent = async (prompt, opts) => {
    spawns.push({ label: opts.label, agentType: opts.agentType,
                  effort: opts.effort, model: opts.model, phase: opts.phase, prompt })
    return agentImpl(opts, prompt, spawns.length)
  }
  const parallel = ths => Promise.all(ths.map(t => t().catch(() => null)))
  const fn = new Function('agent', 'parallel', 'log', 'phase', 'args',
    `return (async () => {\n${body}\n})()`)
  const out = await fn(agent, parallel, () => {}, () => {}, args)
  return { out, spawns }
}

const T = (id, complexity = 'standard') =>
  ({ id, title: `do ${id}`, complexity, subspec: `specs/f/tasks/${id}.md`,
     workdir: `/wt/${id}` })
const base = { slug: 'feat', attempts: 3, models: { 'sdd-implementer': 'sonnet' } }

const IMPL_OK = { task: 'T1', status: 'done',
  files_changed: [{ path: 'a.c', what: 'lots of prose about what changed' }],
  red: { cmd: 'make test', exit: 1, tail: 'X'.repeat(400) },
  verify: { cmd: 'make test', exit: 0, tail: 'Y'.repeat(400) } }
const PASS = { task: 'T1', verdict: 'pass',
  requirements: [{ id: 'R1', status: 'satisfied', evidence: 'a.c:10' }],
  failures: [] }
const FAIL = { task: 'T1', verdict: 'fail', verify: { cmd: 'make test', exit: 1 },
  failures: [{ what: 'hollow', where: 'a.c:10', expected: 'real data' }] }

const checks = []
const ok = (name, cond, extra = '') =>
  checks.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  <-- ' + extra}`)

// 1. happy path
{
  const { out, spawns } = await run({ ...base, tasks: [T('T1')] },
    o => (o.agentType.includes('verifier') ? PASS : IMPL_OK))
  const r = out.results[0]
  ok('happy: verified', r.status === 'verified', r.status)
  ok('happy: 1 impl + 1 verify', spawns.length === 2, JSON.stringify(spawns.map(s => s.label)))
  ok('happy: ready lists it', JSON.stringify(out.ready) === '["T1"]')
  ok('happy: model routed from map', spawns[0].model === 'sonnet', spawns[0].model)
  ok('happy: no retries', r.retries === 0)
  // thin-row rules
  const j = JSON.stringify(r)
  ok('thin: no command tails', !j.includes('XXXX') && !j.includes('YYYY'))
  ok('thin: no per-file prose', !j.includes('lots of prose'))
  ok('thin: keeps red+green exits', r.red.exit === 1 && r.verify.exit === 0)
  ok('thin: requirement count only', r.requirements_checked === 1 && !j.includes('a.c:10'))
  ok('thin: row under 400 bytes', j.length < 400, `${j.length}b: ${j}`)
  // verifier independence
  ok('verifier gets no implementer report',
    !spawns[1].prompt.includes('files_changed') && !spawns[1].prompt.includes('done'))
}

// 2. one failure then a pass -> retry at bumped effort
{
  let n = 0
  const { out, spawns } = await run({ ...base, tasks: [T('T1')] },
    o => o.agentType.includes('verifier') ? (++n === 1 ? FAIL : PASS) : IMPL_OK)
  const r = out.results[0]
  ok('retry: ends verified', r.status === 'verified', r.status)
  ok('retry: counted once', r.retries === 1 && out.retries_total === 1, JSON.stringify(r))
  const impls = spawns.filter(s => s.agentType.includes('implementer'))
  ok('retry: effort medium -> high', impls.map(i => i.effort).join(',') === 'medium,high',
    impls.map(i => i.effort).join(','))
  ok('retry: 2nd impl carries evidence', impls[1].prompt.includes('hollow'))
  ok('retry: phase is Retry', impls[1].phase === 'Retry', impls[1].phase)
}

// 3. always failing -> needs_diagnosis after attempts-1 tries
{
  const { out, spawns } = await run({ ...base, tasks: [T('T1')] },
    o => (o.agentType.includes('verifier') ? FAIL : IMPL_OK))
  const r = out.results[0]
  ok('diag: needs_diagnosis', r.status === 'needs_diagnosis', r.status)
  ok('diag: 2 impl tries (attempts-1)',
    spawns.filter(s => s.agentType.includes('implementer')).length === 2)
  ok('diag: carries evidence for the final rung',
    !!r.evidence && r.evidence.failures[0].what === 'hollow')
  ok('diag: escalated, not ready',
    out.ready.length === 0 && out.escalations[0].status === 'needs_diagnosis')
}

// 4. ladder disabled
{
  const { out, spawns } = await run({ ...base, attempts: 1, tasks: [T('T1')] },
    o => (o.agentType.includes('verifier') ? FAIL : IMPL_OK))
  ok('attempts=1: one try only',
    spawns.filter(s => s.agentType.includes('implementer')).length === 1)
  ok('attempts=1: exhausted not needs_diagnosis',
    out.results[0].status === 'exhausted', out.results[0].status)
}

// 5. escalations short-circuit before any verify
{
  const nf = { ...IMPL_OK, needs_files: [{ path: 'b.h', why: 'decl lives here' }] }
  const { out, spawns } = await run({ ...base, tasks: [T('T1')] }, () => nf)
  ok('needs_files: routed', out.results[0].status === 'needs_files')
  ok('needs_files: no verifier spawned',
    !spawns.some(s => s.agentType.includes('verifier')))
  ok('needs_files: no retry', spawns.length === 1)
  ok('needs_files: passes the ask through',
    out.results[0].needs_files[0].path === 'b.h')

  const amb = { ...IMPL_OK, ambiguities: [{ question: 'retry twice or thrice?' }] }
  const two = await run({ ...base, tasks: [T('T1')] }, () => amb)
  ok('ambiguity: routed', two.out.results[0].status === 'ambiguity')
}

// 6. simple task: lite implementer, no verifier by design
{
  const { out, spawns } = await run({ ...base, tasks: [T('T9', 'simple')] }, () => IMPL_OK)
  ok('simple: implemented', out.results[0].status === 'implemented')
  ok('simple: lite agent', spawns[0].agentType === 'sdd:sdd-implementer-lite',
    spawns[0].agentType)
  ok('simple: effort low', spawns[0].effort === 'low')
  ok('simple: no verifier', spawns.length === 1)
  ok('simple: counts as ready for the orchestrator to check',
    JSON.stringify(out.ready) === '["T9"]')
}

// 7. a dead agent is never a pass; tasks stay independent
{
  const { out } = await run({ ...base, tasks: [T('T1'), T('T2'), T('T3', 'simple')] },
    (o, _p, i) => {
      if (o.label.startsWith('impl:T2')) return null            // implementer dies
      return o.agentType.includes('verifier') ? PASS : IMPL_OK
    })
  const by = Object.fromEntries(out.results.map(r => [r.id, r.status]))
  ok('mixed: dead impl -> agent_failed', by.T2 === 'agent_failed', JSON.stringify(by))
  ok('mixed: siblings unaffected', by.T1 === 'verified' && by.T3 === 'implemented',
    JSON.stringify(by))
  ok('mixed: failure excluded from ready', !out.ready.includes('T2'))
}

// 8. bad args are refused loudly rather than running zero agents
for (const [name, a] of [['no tasks', { ...base, tasks: [] }],
                         ['task missing workdir', { ...base, tasks: [{ id: 'T1', subspec: 's' }] }],
                         ['stringified args', JSON.stringify({ ...base, tasks: [T('T1')] })]]) {
  let threw = null
  const res = await run(a, o => (o.agentType.includes('verifier') ? PASS : IMPL_OK))
    .catch(e => { threw = e.message; return null })
  if (name === 'stringified args') {
    ok('args: json string is parsed, not fatal', !!res && res.out.results.length === 1,
      threw || 'no result')
  } else {
    ok(`args: ${name} throws`, !!threw, 'did not throw')
  }
}

console.log(checks.join('\n'))
const bad = checks.filter(c => c.startsWith('FAIL')).length
console.log(`\n${checks.length - bad}/${checks.length} passed`)
process.exit(bad ? 1 : 0)
