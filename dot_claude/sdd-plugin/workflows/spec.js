export const meta = {
  name: 'sdd-spec',
  description: 'spec writer, then both critics in parallel, then one conditional revision round — the orchestrator gets a digest, not the debate',
  phases: [
    { title: 'Write', detail: 'sdd:sdd-spec-writer writes specs/<slug>/spec.md' },
    { title: 'Critique', detail: 'feasibility (opus) + testability (sonnet) in parallel' },
    { title: 'Revise', detail: 'only when a critic left a blocking finding' },
  ],
}

// invoked by /sdd:run's spec stage (see pipeline.yaml run_via).
//
// WHY this stage is a script: it was the largest fan-out still running inline.
// The writer's return, BOTH critics' full finding lists, and the revision
// round's return all landed in the orchestrator's own window — which only
// grows — so every later stage of the run paid for them again on every
// request. A measured run spent ~100k of its window here. Now the debate
// happens in the script and the orchestrator gets a digest: full text for
// BLOCKING findings only (that is the part it must adjudicate and restate at
// gate 1), one line each for advisory ones, counts for the rest. spec.md
// itself is on disk either way — the writer writes it, nobody returns it.
//
// WHAT STAYS WITH THE ORCHESTRATOR:
//   - research.md (synthesized before this runs) and the intake/user input
//   - adjudicating a blocking finding it has EVIDENCE against: a critic claim
//     that research.md or the code falsifies. Pass `revise_inline: false` to
//     get the findings back before any revision, or `resolutions` to tell the
//     writer how to resolve specific ones (both are used on a gate-1 reroute).
//   - recording ambiguities as amendments, gate 1, state.md, metrics
//
// args: { slug, feature, workdir, user_input, critics, revise_inline,
//         resolutions, models }
//   slug          — feature slug (specs/<slug>/)
//   feature       — the feature description from intake
//   workdir       — absolute path of the feature worktree; every agent works there
//   user_input    — interview answers, a gate decision, or '' (optional)
//   critics       — false skips the critique+revision phases entirely
//                   (config.critics_optional / critics_skip_when); default true
//   revise_inline — false returns the findings WITHOUT revising, for the
//                   orchestrator to arbitrate itself; default true
//   resolutions   — optional [{target, decision}] the writer must apply verbatim
//   models        — optional config.models map (agent short-name -> tier)

// same args-may-arrive-stringified guard as workflows/research.js
// ref: sdd-learnings/_global/research-workflow-args-stringified.md
const input = typeof args === 'string' ? JSON.parse(args) : args
const {
  slug, feature, workdir, user_input = '', critics = true,
  revise_inline = true, resolutions = [], models = {},
} = input || {}
if (!slug || !workdir) {
  throw new Error(`sdd-spec: args needs slug and workdir, got ${JSON.stringify(input)}`)
}
// spread this into an agent()'s opts to route its tier from config.models;
// no entry -> {} -> the key is absent and the agent's frontmatter model stands
const modelOf = name => (models[name] ? { model: models[name] } : {})
const here = `workdir: ${workdir} — run every command from this directory; all paths are relative to it.`

const WRITER_SCHEMA = {
  type: 'object',
  required: ['slug', 'requirements'],
  properties: {
    slug: { type: 'string' },
    requirements: { type: 'array', items: { type: 'string' } },
    self_resolved_ambiguities: {
      type: 'array',
      items: {
        type: 'object',
        required: ['question', 'chose', 'because'],
        properties: {
          question: { type: 'string' },
          chose: { type: 'string' },
          because: { type: 'string' },
        },
      },
    },
    open_issues: { type: 'array', items: { type: 'string' } },
  },
}

const CRITIC_SCHEMA = {
  type: 'object',
  required: ['focus', 'verdict', 'findings'],
  properties: {
    focus: { type: 'string' },
    verdict: { enum: ['approve', 'revise'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['target', 'severity', 'defect', 'impact'],
        properties: {
          target: { type: 'string' },
          severity: { enum: ['blocking', 'advisory'] },
          defect: { type: 'string' },
          impact: { type: 'string' },
        },
      },
    },
  },
}

const CRITIC_AGENTS = [
  { key: 'sdd-spec-critic', focus: 'feasibility+edge-cases', effort: 'high' },
  { key: 'sdd-spec-critic-lite', focus: 'testability+consistency', effort: 'medium' },
]

const writerPrompt = extra => [
  here,
  `inputs: ${JSON.stringify({ slug, feature_description: feature, user_input })}`,
  extra,
].filter(Boolean).join('\n')

phase('Write')
const draft = await agent(
  writerPrompt(),
  {
    agentType: 'sdd:sdd-spec-writer', ...modelOf('sdd-spec-writer'),
    effort: 'high', label: 'spec-writer', phase: 'Write', schema: WRITER_SCHEMA,
  }
)
if (!draft) {
  // no spec.md means nothing for the critics to read — hand back a gap, never
  // an empty success
  return { wrote: false, failed: 'spec-writer' }
}

const digest = d => ({
  requirements: (d.requirements || []).length,
  requirement_ids: d.requirements || [],
  ambiguities: d.self_resolved_ambiguities || [],
  open_issues: d.open_issues || [],
})

if (!critics) {
  log('critics skipped per critics_skip_when — writer only')
  return { wrote: true, ...digest(draft), critics_skipped: true, revised: false }
}

phase('Critique')
// barrier is correct: the revision round needs BOTH critics' findings, and a
// single critic's verdict is not enough to decide whether to revise at all
const reviews = await parallel(CRITIC_AGENTS.map(c => () =>
  agent(
    `${here}\ninputs: ${JSON.stringify({ slug })}`,
    {
      agentType: `sdd:${c.key}`, ...modelOf(c.key), effort: c.effort,
      label: `critic:${c.key === 'sdd-spec-critic' ? 'feasibility' : 'testability'}`,
      phase: 'Critique', schema: CRITIC_SCHEMA,
    }
  // key on the focus we ASKED for, not the one the model echoes, so a drift
  // in wording cannot desync the failure list
  ).then(r => (r ? { ...r, focus: c.focus } : null))
))

const critic_failures = CRITIC_AGENTS.filter((c, i) => !reviews[i]).map(c => c.focus)
if (critic_failures.length) {
  log(`${critic_failures.length} critic(s) failed — orchestrator should re-run inline`)
}
const found = reviews.filter(Boolean).flatMap(r =>
  r.findings.map(f => ({ ...f, focus: r.focus })))
const blocking = found.filter(f => f.severity === 'blocking')
// advisory findings are trimmed on purpose: they are gate-1 colour, not work
const advisory = found.filter(f => f.severity !== 'blocking')
  .map(f => ({ target: f.target, defect: f.defect, focus: f.focus }))
log(`critique: ${blocking.length} blocking, ${advisory.length} advisory`)

const summary = {
  wrote: true,
  ...digest(draft),
  critics: reviews.filter(Boolean).map(r => ({
    focus: r.focus, verdict: r.verdict,
    blocking: r.findings.filter(f => f.severity === 'blocking').length,
    advisory: r.findings.filter(f => f.severity !== 'blocking').length,
  })),
  blocking,
  advisory,
  critic_failures,
  revised: false,
}

if (!blocking.length) return summary
if (!revise_inline) {
  log('revise_inline false — findings handed back unrevised')
  return summary
}

phase('Revise')
const revision = await agent(
  writerPrompt([
    'inputs (revision): ' + JSON.stringify({
      revision: true,
      reason: 'critic blocking findings — resolve every one, or move it to Open issues with the reason it cannot be resolved',
      blocking_findings: blocking,
      orchestrator_resolutions: resolutions,
    }),
    'Apply every orchestrator_resolutions entry verbatim; those are decisions',
    'already made, not suggestions to weigh.',
  ].join('\n')),
  {
    agentType: 'sdd:sdd-spec-writer', ...modelOf('sdd-spec-writer'),
    effort: 'high', label: 'spec-writer:revision', phase: 'Revise',
    schema: WRITER_SCHEMA,
  }
)
if (!revision) {
  // the draft and the findings are still real; the orchestrator dispatches the
  // revision itself rather than shipping an unrevised spec to gate 1
  log('revision round failed — orchestrator should re-run it inline')
  return { ...summary, failed: 'spec-writer:revision' }
}

// after a revision, anything the writer could NOT resolve is in open_issues —
// that plus the original blocking list is what gate 1 has to see
return {
  ...summary,
  ...digest(revision),
  blocking_addressed: blocking.length,
  revised: true,
}
