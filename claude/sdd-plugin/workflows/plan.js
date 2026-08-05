export const meta = {
  name: 'sdd-plan',
  description: 'planner run, plus the deterministic set math the orchestrator would otherwise do by hand — coverage gaps and per-task file-set conflicts',
  phases: [
    { title: 'Plan', detail: 'sdd:sdd-planner writes specs/<slug>/tasks.md' },
  ],
}

// invoked by /sdd:run's plan stage (see pipeline.yaml run_via).
//
// WHY a one-agent stage is scripted anyway: the planner's return is the whole
// task list — for a 10-task feature that is every task's file list and verify
// command, several KB that then sit in the orchestrator's window for the rest
// of the run. tasks.md holds all of it on disk, and the orchestrator needs a
// task's files/verify exactly once, when it writes that task's subspec at
// implement setup. So this returns the TABLE (what state.md mirrors) and the
// two derived facts the orchestrator would otherwise compute from the paths:
//   - coverage_gaps — requirements no task claims
//   - conflicts     — per task, the tasks whose file sets overlap it
// conflicts is set math, so it belongs in a script, not in a model: batching
// then needs only ids and depends_on, and the paths never enter the window.
//
// WHAT STAYS WITH THE ORCHESTRATOR: mirroring the table into state.md, gate 1
// (including the gate1_skip_if_simple check), routing a gate reroute, and
// reading each task's files/verify from tasks.md when it writes that subspec.
//
// args: { slug, workdir, revision, requirements, models }
//   slug         — feature slug (specs/<slug>/)
//   workdir      — absolute path of the feature worktree; the planner works there
//   revision     — optional string reason (gate-1/gate-2 feedback, a coverage
//                  gap); present -> the planner is told this is a revision
//   requirements — optional R-ids from the spec stage (spec.js returns them as
//                  requirement_ids); pass them and coverage_gaps is checked
//                  against the spec instead of only the planner's self-report
//   models       — optional config.models map (agent short-name -> tier)

// same args-may-arrive-stringified guard as workflows/research.js
// ref: sdd-learnings/_global/research-workflow-args-stringified.md
const input = typeof args === 'string' ? JSON.parse(args) : args
const { slug, workdir, revision = '', models = {} } = input || {}
if (!slug || !workdir) {
  throw new Error(`sdd-plan: args needs slug and workdir, got ${JSON.stringify(input)}`)
}
const modelOf = name => (models[name] ? { model: models[name] } : {})

const PLAN_SCHEMA = {
  type: 'object',
  required: ['tasks', 'coverage', 'unplannable'],
  properties: {
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'title', 'requirements', 'files', 'depends_on',
                   'parallel_ok', 'complexity', 'verify'],
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          requirements: { type: 'array', items: { type: 'string' } },
          files: { type: 'array', items: { type: 'string' } },
          depends_on: { type: 'array', items: { type: 'string' } },
          parallel_ok: { type: 'boolean' },
          complexity: { enum: ['simple', 'standard'] },
          verify: { type: 'string' },
        },
      },
    },
    // requirement id -> task ids
    coverage: { type: 'object', additionalProperties: { type: 'array', items: { type: 'string' } } },
    unplannable: {
      type: 'array',
      items: {
        type: 'object',
        required: ['requirement', 'why'],
        properties: { requirement: { type: 'string' }, why: { type: 'string' } },
      },
    },
  },
}

phase('Plan')
const plan = await agent(
  [
    `workdir: ${workdir} — run every command from this directory; all paths are relative to it.`,
    `inputs: ${JSON.stringify(revision ? { slug, revision: true, reason: revision } : { slug })}`,
  ].join('\n'),
  {
    agentType: 'sdd:sdd-planner', ...modelOf('sdd-planner'), effort: 'xhigh',
    label: revision ? 'planner:revision' : 'planner', phase: 'Plan',
    schema: PLAN_SCHEMA,
  }
)
if (!plan) return { planned: false, failed: 'planner' }

const tasks = plan.tasks || []
// normalize once: a path list is only comparable after the strings are
const fileset = t => new Set((t.files || []).map(f => f.trim()).filter(Boolean))
const sets = new Map(tasks.map(t => [t.id, fileset(t)]))

const conflictsFor = t => tasks
  .filter(o => o.id !== t.id)
  .filter(o => [...sets.get(t.id)].some(f => sets.get(o.id).has(f)))
  .map(o => o.id)

// a requirement claimed by no task is a planning failure the planner did not
// report as unplannable — the two are different and gate 1 needs both. checked
// against the spec's own requirement ids when the orchestrator passes them
// (spec.js returns requirement_ids); without them only the planner's two
// self-reports can be cross-checked against each other.
const claimed = new Set(tasks.flatMap(t => t.requirements || []))
const covered = new Set(Object.entries(plan.coverage || {})
  .filter(([, ids]) => (ids || []).length).map(([r]) => r))
const coverage_gaps = (input.requirements || [])
  .filter(r => !claimed.has(r) && !covered.has(r))
// the planner's coverage map says covered, no task's requirement list agrees
const coverage_disputed = [...covered].filter(r => !claimed.has(r))

const table = tasks.map(t => ({
  id: t.id,
  title: t.title,
  complexity: t.complexity,
  depends_on: t.depends_on || [],
  parallel_ok: !!t.parallel_ok,
  requirements: t.requirements || [],
  files: (t.files || []).length,
  conflicts: conflictsFor(t),
}))

// parallel_ok is the planner's claim; conflicts is what the paths actually say.
// a disagreement is worth naming — it is exactly the batching mistake that
// serializes a whole stage, or corrupts one
const parallel_ok_disputed = table
  .filter(t => t.parallel_ok && t.conflicts.length)
  .map(t => ({ id: t.id, overlaps: t.conflicts }))
if (parallel_ok_disputed.length) {
  log(`${parallel_ok_disputed.length} task(s) claim parallel_ok but share files`)
}
log(`plan: ${table.length} tasks, ${table.filter(t => t.complexity === 'simple').length} simple`)

return {
  planned: true,
  revised: !!revision,
  tasks: table,
  simple: table.filter(t => t.complexity === 'simple').length,
  standard: table.filter(t => t.complexity === 'standard').length,
  coverage_counts: Object.fromEntries(
    Object.entries(plan.coverage || {}).map(([r, ids]) => [r, (ids || []).length])),
  coverage_gaps,
  coverage_disputed,
  unplannable: plan.unplannable || [],
  parallel_ok_disputed,
}
