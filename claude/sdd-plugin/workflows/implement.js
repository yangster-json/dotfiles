export const meta = {
  name: 'sdd-implement',
  description: 'per-task implement -> verify -> escalating-retry chains, run independently per task; git, subspecs and adjudication stay with the orchestrator',
  phases: [
    { title: 'Implement', detail: 'one implementer per task (lite for simple)' },
    { title: 'Verify', detail: 'sdd:sdd-verifier for standard tasks only' },
    { title: 'Retry', detail: 'only tasks whose verdict came back fail' },
  ],
}

// invoked by /sdd:run's implement stage (see pipeline.yaml run_via).
//
// WHY this stage is a script: the implementer/verifier fan-out was the last
// one still running inline, and it is the biggest. Every implementer return,
// every verifier verdict, and every retry landed in the orchestrator's own
// window — which only grows — so a 10-task feature paid for those returns on
// every subsequent request of the run. Here they land in the script and the
// orchestrator gets back one compact row per task.
//
// WHAT STAYS WITH THE ORCHESTRATOR (workflow scripts have no shell, and the
// rest is judgment the pipeline file deliberately keeps human-adjacent):
//   - subspec writing + the standards digest (implement `setup`)
//   - worktree creation (`sdd-git task-start`) BEFORE invoking this, and every
//     merge (`sdd-git wip` / `task-merge` / `task-abort`) AFTER it returns
//   - simple-task verification: no spawn by design, so the orchestrator re-runs
//     the verify command and checks scope itself (`git status`/`diff`)
//   - needs_files adjudication (scope_stop) and behavioral ambiguities
//   - the LAST retry rung, which is diagnosis-first: root-cause, then amend the
//     subspec / fix the verify command / decompose the task before a final try
//
// args: { slug, tasks, attempts, models }
//   tasks    — [{ id, title, complexity, subspec, workdir }]; workdir is the
//              ABSOLUTE path of the worktree that task owns (the feature
//              worktree for a solo task, its own for a concurrent one) and
//              subspec is relative to it. The orchestrator picks the batch, so
//              pairwise-disjoint file sets and the max-3 concurrency rule are
//              already enforced when it gets here.
//   attempts — config.recovery.task_attempts (default 3). This script uses at
//              most attempts-1 implementer tries, leaving the final
//              diagnosis-first rung to the orchestrator.
//   models   — config.models map (agent short-name -> tier); frontmatter is
//              the fallback when it has no entry.
//
// tested by tests/implement_workflow_test.mjs — `node tests/…mjs` drives this
// file against a stubbed runtime (ladder, escalation routing, thin rows).

// same args-may-arrive-stringified guard as workflows/research.js
// ref: sdd-learnings/_global/research-workflow-args-stringified.md
const input = typeof args === 'string' ? JSON.parse(args) : args
const { slug, tasks, attempts = 3, models = {} } = input || {}
if (!Array.isArray(tasks) || tasks.length === 0) {
  throw new Error(`sdd-implement: args.tasks must be a non-empty array, got ${JSON.stringify(input)}`)
}
for (const t of tasks) {
  if (!t || !t.id || !t.workdir || !t.subspec) {
    throw new Error(`sdd-implement: every task needs id, workdir and subspec, got ${JSON.stringify(t)}`)
  }
}
const modelOf = name => (models[name] ? { model: models[name] } : {})

// effort ladder for the retry rung — "the implementer's effort bumped one
// tier" (pipeline.yaml recovery.task_attempts). Starting points match each
// implementer's frontmatter.
const LADDER = ['low', 'medium', 'high', 'xhigh']
const bump = e => LADDER[Math.min(LADDER.indexOf(e) + 1, LADDER.length - 1)]

const IMPL_SCHEMA = {
  type: 'object',
  required: ['task', 'status'],
  properties: {
    task: { type: 'string' },
    status: { enum: ['done', 'blocked'] },
    files_changed: {
      type: 'array',
      items: {
        type: 'object',
        required: ['path'],
        properties: { path: { type: 'string' }, what: { type: 'string' } },
      },
    },
    red: {
      type: 'object',
      properties: {
        cmd: { type: 'string' }, exit: { type: 'integer' }, tail: { type: 'string' },
      },
    },
    verify: {
      type: 'object',
      properties: {
        cmd: { type: 'string' }, exit: { type: 'integer' }, tail: { type: 'string' },
      },
    },
    needs_files: {
      type: 'array',
      items: {
        type: 'object',
        required: ['path', 'why'],
        properties: { path: { type: 'string' }, why: { type: 'string' } },
      },
    },
    ambiguities: {
      type: 'array',
      items: {
        type: 'object',
        required: ['question'],
        properties: {
          question: { type: 'string' },
          options: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['task', 'verdict'],
  properties: {
    task: { type: 'string' },
    verdict: { enum: ['pass', 'fail'] },
    verify: {
      type: 'object',
      properties: { cmd: { type: 'string' }, exit: { type: 'integer' } },
    },
    requirements: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'status'],
        properties: {
          id: { type: 'string' },
          status: { enum: ['satisfied', 'violated'] },
          evidence: { type: 'string' },
        },
      },
    },
    failures: {
      type: 'array',
      items: {
        type: 'object',
        required: ['what'],
        properties: {
          what: { type: 'string' },
          where: { type: 'string' },
          expected: { type: 'string' },
        },
      },
    },
  },
}

const lite = t => String(t.complexity || 'standard').toLowerCase() === 'simple'

function implementerFor(t) {
  return lite(t)
    ? { agentType: 'sdd:sdd-implementer-lite', key: 'sdd-implementer-lite', effort: 'low' }
    : { agentType: 'sdd:sdd-implementer', key: 'sdd-implementer', effort: 'medium' }
}

// the implementer's contract is {workdir, subspec} and nothing else — the
// subspec already carries the requirements, file list and verify command, so
// re-stating any of it here would be the same tokens paid twice
function implement(t, attempt, effort, evidence) {
  const im = implementerFor(t)
  return agent(
    [
      `inputs: ${JSON.stringify({ workdir: t.workdir, subspec: t.subspec })}`,
      `run every command from workdir; it is the only worktree you may touch.`,
      evidence
        ? `this is retry ${attempt - 1} — the previous attempt FAILED verification. ` +
          `failure evidence json: ${JSON.stringify(evidence)}. ` +
          `fix the cause, do not re-litigate the verdict, and stay inside your file list.`
        : '',
    ].filter(Boolean).join('\n'),
    {
      agentType: im.agentType,
      ...modelOf(im.key),
      effort,
      label: attempt === 1 ? `impl:${t.id}` : `impl:${t.id}#${attempt}`,
      phase: attempt === 1 ? 'Implement' : 'Retry',
      schema: IMPL_SCHEMA,
    }
  )
}

// verifier independence is the whole point of the spawn: it must NOT receive
// the implementer's return (see agents/sdd-verifier.md), so the prompt carries
// only the paths it needs to re-derive everything itself
function verify(t, attempt) {
  return agent(
    `inputs: ${JSON.stringify({ workdir: t.workdir, subspec: t.subspec })}\n` +
    `run every command from workdir. Re-derive everything; you get no implementer report.`,
    {
      agentType: 'sdd:sdd-verifier',
      ...modelOf('sdd-verifier'),
      effort: 'medium',
      label: attempt === 1 ? `verify:${t.id}` : `verify:${t.id}#${attempt}`,
      phase: attempt === 1 ? 'Verify' : 'Retry',
      schema: VERDICT_SCHEMA,
    }
  )
}

// the rows we hand back are deliberately THIN. the reason this stage became a
// script is that agent returns which reach the orchestrator get re-read on
// every later request — so echoing a full verdict (every requirement, every
// failure, command tails) for a task that PASSED would hand the cost straight
// back. pass rows carry counts; only an escalation carries its evidence,
// because there the orchestrator actually has to act on it.
const cmdOnly = r => (r && r.cmd ? { cmd: r.cmd, exit: r.exit } : null)

// one task's whole chain. `parallel` over these (rather than staged pipeline())
// because the stages here are a LOOP, not a fixed sequence: a task that passes
// first try never enters Retry, and no task should wait on another's retries.
async function runTask(t) {
  const row = { id: t.id, title: t.title || '', complexity: lite(t) ? 'simple' : 'standard',
                workdir: t.workdir, attempts_used: 0, retries: 0 }
  // attempts-1 leaves the final diagnosis-first rung to the orchestrator;
  // attempts:1 disables the ladder entirely, so the script's one try is ALL
  // of it and exhausting it means blocked, not needs_diagnosis
  const total = Math.max(1, Number(attempts) || 1)
  const budget = total > 1 ? total - 1 : 1
  let effort = implementerFor(t).effort
  let evidence = null

  for (let attempt = 1; attempt <= budget; attempt++) {
    row.attempts_used = attempt
    row.retries = attempt - 1

    const impl = await implement(t, attempt, effort, evidence).catch(() => null)
    if (!impl) return { ...row, status: 'agent_failed', why: 'implementer returned nothing' }

    // scope + semantics escalations are the orchestrator's to adjudicate, and
    // retrying them would just reproduce the same stop
    if (impl.needs_files && impl.needs_files.length) {
      return { ...row, status: 'needs_files', needs_files: impl.needs_files }
    }
    if (impl.ambiguities && impl.ambiguities.length) {
      return { ...row, status: 'ambiguity', ambiguities: impl.ambiguities }
    }
    if (impl.status === 'blocked') {
      return { ...row, status: 'blocked', verify: cmdOnly(impl.verify) }
    }
    // paths only: enough to log what moved, without the per-file prose
    row.files = (impl.files_changed || []).map(f => f.path).filter(Boolean)
    row.red = cmdOnly(impl.red)         // that the new test was seen red...
    row.verify = cmdOnly(impl.verify)   // ...and green; tails stay in the script

    // simple tasks get no verifier by design — the orchestrator re-runs the
    // verify command and checks scope itself (pipeline.yaml `verification`)
    if (lite(t)) return { ...row, status: 'implemented' }

    const verdict = await verify(t, attempt).catch(() => null)
    if (!verdict) return { ...row, status: 'unverified', why: 'verifier returned nothing' }

    if (verdict.verdict === 'pass') {
      const reqs = verdict.requirements || []
      return { ...row, status: 'verified',
               requirements_checked: reqs.length,
               // a "pass" that still lists violated requirements is a
               // contradiction the orchestrator should see, not swallow
               requirements_violated: reqs.filter(r => r.status === 'violated')
                 .map(r => r.id) }
    }

    evidence = { verify: verdict.verify || null, failures: verdict.failures || [] }
    effort = bump(effort)
    log(`${t.id}: verify FAIL on attempt ${attempt}/${budget}` +
        (attempt < budget ? ` — retrying at effort ${effort}` : ' — handing back for diagnosis'))
  }

  // out of script-side rungs. with a ladder configured the orchestrator still
  // owns the final diagnosis-first try; with the ladder disabled
  // (task_attempts: 1) there is no rung left and the task is simply blocked.
  return { ...row, status: total > 1 ? 'needs_diagnosis' : 'exhausted', evidence }
}

phase('Implement')
log(`${slug}: ${tasks.length} task(s) — ${tasks.map(t => t.id).join(', ')} · ` +
    `${Math.max(1, (Number(attempts) || 1) - 1) || 1} script-side attempt(s) each`)

const results = (await parallel(tasks.map(t => () => runTask(t)))).map(
  // a thunk that threw at all resolves null; never let that read as success
  (r, i) => r || { id: tasks[i].id, status: 'agent_failed', why: 'chain threw' })

for (const r of results) log(`${r.id}: ${r.status}` + (r.retries ? ` after ${r.retries} retry(s)` : ''))

// statuses the orchestrator must act on, split out so nothing needs re-deriving:
//   verified        -> commit + merge it (sdd-git wip / task-merge)
//   implemented     -> simple task: run its verify command + scope check, then merge
//   needs_files     -> adjudicate scope_stop, amend the subspec, re-run the task
//   ambiguity       -> resolve, record an (assumption) amendment, re-run the task
//   needs_diagnosis -> the final diagnosis-first attempt
//   exhausted       -> ladder disabled (task_attempts: 1) and it failed: block it
//   blocked / unverified / agent_failed -> re-run inline; never treat as passed
return {
  results,
  ready: results.filter(r => r.status === 'verified' || r.status === 'implemented').map(r => r.id),
  escalations: results.filter(r =>
    !['verified', 'implemented'].includes(r.status)).map(r => ({ id: r.id, status: r.status })),
  retries_total: results.reduce((n, r) => n + (r.retries || 0), 0),
}
