export const meta = {
  name: 'sdd-review',
  description: 'combative review — 3 stances in parallel, conditional combat round, conditional judge, test recommendations',
  phases: [
    { title: 'Round 1', detail: 'breaker / guardian / attacker + test-recommender in parallel' },
    { title: 'Combat', detail: 'only reviewers with opponent findings to contest' },
    { title: 'Judge', detail: 'only when findings survive combat' },
  ],
}

// invoked by /sdd:run's review stage (see pipeline.yaml run_via).
// args: { slug, base_ref, workdir }
//   slug     — feature slug (specs/<slug>/)
//   base_ref — ref the feature diff is taken against
//   workdir  — absolute path of the feature worktree; every agent operates there
// round 0 (mechanical stub grep) and gate 2 stay with the orchestrator — the
// script owns rounds 1-2, withdrawal filtering, the judge, and the
// test-recommender. models are pinned in the plugin's agents/*.md
// frontmatter and resolved via agentType (sdd:sdd-*) — never set model here.

const { slug, base_ref, workdir } = args
const here = `workdir: ${workdir} — run every command from this directory; all paths are relative to it.`

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['stance', 'findings'],
  properties: {
    stance: { type: 'string' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'file', 'line', 'severity', 'summary', 'scenario'],
        properties: {
          id: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          severity: { enum: ['high', 'medium', 'low'] },
          summary: { type: 'string' },
          scenario: { type: 'string' },
        },
      },
    },
  },
}

const COMBAT_SCHEMA = {
  type: 'object',
  required: ['stance', 'rebuttals', 'withdrawn', 'defenses'],
  properties: {
    stance: { type: 'string' },
    rebuttals: {
      type: 'array',
      items: {
        type: 'object',
        required: ['target', 'verdict', 'argument'],
        properties: {
          target: { type: 'string' },
          verdict: { enum: ['refute', 'concede', 'escalate'] },
          argument: { type: 'string' },
          evidence: { type: 'string' },
        },
      },
    },
    withdrawn: { type: 'array', items: { type: 'string' } },
    defenses: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'note'],
        properties: { id: { type: 'string' }, note: { type: 'string' } },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['confirmed', 'rejected'],
  properties: {
    confirmed: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'severity', 'file', 'line', 'summary', 'scenario'],
        properties: {
          id: { type: 'string' },
          merged_with: { type: 'array', items: { type: 'string' } },
          severity: { enum: ['high', 'medium', 'low'] },
          file: { type: 'string' },
          line: { type: 'integer' },
          summary: { type: 'string' },
          scenario: { type: 'string' },
          debate: { type: 'string' },
        },
      },
    },
    rejected: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'reason'],
        properties: {
          id: { type: 'string' },
          reason: { type: 'string' },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

const TEST_ITEM = {
  type: 'object',
  required: ['name', 'why', 'run', 'must_run'],
  properties: {
    name: { type: 'string' },
    why: { type: 'string' },
    run: { type: 'string' },
    must_run: { type: 'boolean' },
  },
}
const TESTS_SCHEMA = {
  type: 'object',
  required: ['unit_tests', 'pytests', 'hw_pytests', 'hw_required'],
  properties: {
    unit_tests: { type: 'array', items: TEST_ITEM },
    pytests: { type: 'array', items: TEST_ITEM },
    hw_pytests: { type: 'array', items: TEST_ITEM },
    hw_required: { type: 'boolean' },
    hw_required_because: { type: 'string' },
  },
}

phase('Round 1')

// started now, awaited only in the return — its result is needed at gate 2,
// not by any round, so it never blocks the review chain. .catch(->null)
// because it is not routed through parallel(): a bare agent() REJECTION here
// would surface as an unhandled rejection and, at the awaits below, abort the
// whole review — the orchestrator degrades a null `tests` gracefully, a throw
// it cannot.
const testRecP = agent(
  `${here}\ninputs: ${JSON.stringify({ slug, base_ref })}`,
  { agentType: 'sdd:sdd-test-recommender', effort: 'low', label: 'test-recommender', phase: 'Round 1', schema: TESTS_SCHEMA }
).catch(() => null)

const STANCES = ['breaker', 'guardian', 'attacker']
// barrier is correct: every round-2 reviewer needs ALL opponent findings
const round1 = (await parallel(STANCES.map(s => () =>
  agent(
    `${here}\nround 1 — find.\ninputs: ${JSON.stringify({ stance: s, slug, base_ref })}`,
    { agentType: 'sdd:sdd-reviewer', effort: 'high', label: `round1:${s}`, phase: 'Round 1', schema: FINDINGS_SCHEMA }
  // key on the stance we REQUESTED, not the one the model echoes — a
  // capitalization/typo drift would otherwise desync byStance/failures/combat
  ).then(r => (r ? { ...r, stance: s } : null))
))).filter(Boolean)

const byStance = {}
for (const r of round1) byStance[r.stance] = r.findings
const allFindings = round1.flatMap(r => r.findings)
const reviewerFailures = STANCES.filter(s => !byStance[s])
log(`round 1: ${allFindings.length} findings from ${round1.length}/3 reviewers`)

if (allFindings.length === 0) {
  return {
    clean: true, confirmed: [], rejected: [], withdrawn: [], unjudged: [],
    reviewer_failures: reviewerFailures, tests: await testRecP,
  }
}

phase('Combat')

// spawn ONLY reviewers that have opponent findings to contest — a reviewer
// whose opponents found nothing has nothing to rebut
const combatants = STANCES.filter(s =>
  byStance[s] && allFindings.length > byStance[s].length)
const combat = (await parallel(combatants.map(s => () =>
  agent(
    `${here}\nround 2 — combat.\ninputs: ${JSON.stringify({
      stance: s, slug, base_ref,
      own_findings: byStance[s],
      opponent_findings: round1.filter(r => r.stance !== s).flatMap(r => r.findings),
    })}`,
    { agentType: 'sdd:sdd-reviewer', effort: 'high', label: `combat:${s}`, phase: 'Combat', schema: COMBAT_SCHEMA }
  )
))).filter(Boolean)

// withdrawals applied here, deterministically — the judge never sees them
const withdrawn = new Set(combat.flatMap(c => c.withdrawn))
const surviving = allFindings.filter(f => !withdrawn.has(f.id))
const debate = combat.map(c => ({
  stance: c.stance,
  rebuttals: c.rebuttals.filter(r => !withdrawn.has(r.target)),
  defenses: c.defenses.filter(d => !withdrawn.has(d.id)),
}))
log(`combat: ${withdrawn.size} withdrawn, ${surviving.length} findings survive`)

if (surviving.length === 0) {
  return {
    clean: true, confirmed: [], rejected: [], withdrawn: [...withdrawn], unjudged: [],
    reviewer_failures: reviewerFailures, tests: await testRecP,
  }
}

phase('Judge')

// .catch(->null) so a judge REJECTION (not just a null-resolved death) still
// falls into the judge-died path below (unjudged + debate handed back) instead
// of aborting the review and discarding all completed round-1/combat work.
const verdict = await agent(
  `${here}\ninputs: ${JSON.stringify({ slug, base_ref, findings: surviving, rebuttals: debate })}`,
  { agentType: 'sdd:sdd-review-judge', effort: 'xhigh', label: 'judge', phase: 'Judge', schema: VERDICT_SCHEMA }
).catch(() => null)

// judge died -> hand the surviving findings + debate back so the
// orchestrator can spawn sdd:sdd-review-judge inline before gate 2
return {
  clean: false,
  confirmed: verdict ? verdict.confirmed : [],
  rejected: verdict ? verdict.rejected : [],
  withdrawn: [...withdrawn],
  unjudged: verdict ? [] : surviving,
  debate: verdict ? undefined : debate,
  reviewer_failures: reviewerFailures,
  tests: await testRecP,
}
