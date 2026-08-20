// drives workflows/spec.js against a stubbed Workflow runtime, so the
// conditional revision round and the digest rules are actually executed.
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'workflows', 'spec.js')
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

const base = { slug: 'feat', feature: 'do the thing', workdir: '/wt/feat',
               models: { 'sdd-spec-writer': 'opus', 'sdd-spec-critic-lite': 'sonnet' } }

const DRAFT = { slug: 'feat', requirements: ['R1', 'R2', 'R3'],
  self_resolved_ambiguities: [{ question: 'q', chose: 'c', because: 'b' }],
  open_issues: [] }
const REVISED = { ...DRAFT, requirements: ['R1', 'R2', 'R3', 'R4'],
  open_issues: ['R2 fallback scope still undecided'] }
const CLEAN = { focus: 'x', verdict: 'approve', findings: [] }
const BLOCKER = { focus: 'x', verdict: 'revise', findings: [
  { target: 'R3', severity: 'blocking', defect: 'walker never fetches at depth 1',
    impact: 'zero rows at the default depth' }] }
const ADVISORY = { focus: 'y', verdict: 'revise', findings: [
  { target: 'R7', severity: 'advisory', defect: 'log2 encoding unstated',
    impact: 'a long tail of decode bugs nobody planned for' }] }

const isWriter = o => o.agentType.includes('spec-writer')
const isLite = o => o.agentType.includes('critic-lite')

const checks = []
const ok = (name, cond, extra = '') =>
  checks.push(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : '  <-- ' + extra}`)

// 1. clean spec: writer + both critics, no revision
{
  const { out, spawns } = await run(base, o => (isWriter(o) ? DRAFT : CLEAN))
  ok('clean: 3 spawns', spawns.length === 3, spawns.map(s => s.label).join(','))
  ok('clean: no revision', out.revised === false)
  ok('clean: requirement count + ids', out.requirements === 3 && out.requirement_ids[2] === 'R3')
  ok('clean: ambiguities kept for gate 1', out.ambiguities.length === 1)
  ok('clean: no blocking', out.blocking.length === 0 && out.advisory.length === 0)
  ok('clean: per-critic verdicts', out.critics.length === 2 && out.critics[0].verdict === 'approve')
  ok('clean: model routed from map', spawns[0].model === 'opus', spawns[0].model)
  ok('clean: critic efforts match frontmatter',
    spawns.filter(s => !isWriter({ agentType: s.agentType })).map(s => s.effort).join(',') === 'high,medium',
    spawns.map(s => `${s.label}:${s.effort}`).join(' '))
  ok('clean: spec text is never returned', !JSON.stringify(out).includes('SHALL'))
}

// 2. a blocking finding triggers exactly one revision round
{
  const { out, spawns } = await run(base,
    o => (isWriter(o) ? DRAFT : (isLite(o) ? ADVISORY : BLOCKER)))
  ok('blocking: revision ran', out.revised === true)
  ok('blocking: 4 spawns', spawns.length === 4, spawns.map(s => s.label).join(','))
  ok('blocking: revision is the writer again',
    spawns[3].label === 'spec-writer:revision' && spawns[3].phase === 'Revise')
  ok('blocking: writer got the findings verbatim',
    spawns[3].prompt.includes('walker never fetches at depth 1'))
  ok('blocking: count reported', out.blocking_addressed === 1)
  ok('blocking: blocking kept in full', out.blocking[0].impact.includes('zero rows'))
  ok('blocking: advisory trimmed to one line',
    out.advisory[0].defect && out.advisory[0].impact === undefined,
    JSON.stringify(out.advisory[0]))
  ok('blocking: finding carries its critic', out.blocking[0].focus === 'feasibility+edge-cases',
    out.blocking[0].focus)
}

// 3. the revised digest supersedes the draft's
{
  const { out } = await run(base, o => (isWriter(o) ? (o.label.includes('revision') ? REVISED : DRAFT)
    : (isLite(o) ? CLEAN : BLOCKER)))
  ok('revised: requirements from the revision', out.requirements === 4)
  ok('revised: open issues from the revision', out.open_issues.length === 1)
}

// 4. revise_inline false hands the findings back untouched
{
  const { out, spawns } = await run({ ...base, revise_inline: false },
    o => (isWriter(o) ? DRAFT : BLOCKER))
  ok('no-inline: 3 spawns', spawns.length === 3)
  ok('no-inline: not revised, blocking returned',
    out.revised === false && out.blocking.length === 2, JSON.stringify(out.blocking))
}

// 5. orchestrator resolutions reach the writer as decisions
{
  const { spawns } = await run(
    { ...base, resolutions: [{ target: 'R3', decision: 'guard is > not >=' }] },
    o => (isWriter(o) ? DRAFT : BLOCKER))
  ok('resolutions: passed verbatim', spawns[3].prompt.includes('guard is > not >='))
  ok('resolutions: marked as decided', spawns[3].prompt.includes('verbatim'))
}

// 6. critics skipped per critics_skip_when
{
  const { out, spawns } = await run({ ...base, critics: false },
    o => (isWriter(o) ? DRAFT : CLEAN))
  ok('skip: writer only', spawns.length === 1 && out.critics_skipped === true)
  ok('skip: still reports the digest', out.requirements === 3 && out.wrote === true)
}

// 7. a dead writer is a gap, not an empty success
{
  const { out, spawns } = await run(base, o => (isWriter(o) ? null : CLEAN))
  ok('writer death: no critics spawned', spawns.length === 1)
  ok('writer death: reported', out.wrote === false && out.failed === 'spec-writer')
}

// 8. one dead critic: named, and the run continues on the other
{
  const { out } = await run(base,
    o => (isWriter(o) ? DRAFT : (isLite(o) ? null : BLOCKER)))
  ok('critic death: named', out.critic_failures.join() === 'testability+consistency',
    JSON.stringify(out.critic_failures))
  ok('critic death: other critic still counted', out.blocking.length === 1)
  ok('critic death: revision still ran', out.revised === true)
}

// 9. a dead revision round keeps the findings for an inline retry
{
  const { out } = await run(base, o => (isWriter(o)
    ? (o.label.includes('revision') ? null : DRAFT) : BLOCKER))
  ok('revision death: reported', out.failed === 'spec-writer:revision')
  ok('revision death: findings preserved', out.blocking.length === 2 && out.revised === false)
}

// 10. args handling
{
  const { out } = await run(JSON.stringify(base), o => (isWriter(o) ? DRAFT : CLEAN))
  ok('args: json string is parsed, not fatal', out.wrote === true)
  let threw = null
  await run({ feature: 'x' }, () => DRAFT).catch(e => { threw = e.message })
  ok('args: missing slug/workdir throws', !!threw, 'did not throw')
}

console.log(checks.join('\n'))
const bad = checks.filter(c => c.startsWith('FAIL')).length
console.log(`\n${checks.length - bad}/${checks.length} passed`)
process.exit(bad ? 1 : 0)
