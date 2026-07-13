export const meta = {
  name: 'sdd-research',
  description: 'parallel research scouts — one angle each; enumeration angles on sdd:sdd-researcher (haiku), cross-file angles on sdd:sdd-researcher-deep (sonnet)',
  phases: [
    { title: 'Scout', detail: 'one agent per angle, all in parallel' },
  ],
}

// invoked by /sdd:run's research stage (see pipeline.yaml run_via).
// args: { feature, slug, workdir, angles: [{ angle, depth, learnings }] }
//   feature   — the feature description from intake
//   workdir   — absolute path of the feature worktree
//   angles    — 2-4 entries picked by the orchestrator (that is judgment and
//               stays there); depth "enum" -> sdd:sdd-researcher,
//               "deep" -> sdd:sdd-researcher-deep
//   learnings — optional array of learning-entry file paths for that angle
// the script only guarantees the fan-out; the orchestrator synthesizes
// research.md from the returned reports. models are pinned in agent
// frontmatter and resolved via agentType — never set model here.

const { feature, slug, workdir, angles } = args

phase('Scout')
const scouts = await parallel(angles.map((a, i) => () =>
  agent(
    [
      `workdir: ${workdir} — investigate this repo; run every command from this directory.`,
      `feature (slug ${slug}): ${feature}`,
      `your one research angle: ${a.angle}`,
      a.learnings && a.learnings.length
        ? `read these past-mistake learning entries first: ${a.learnings.join(', ')}`
        : '',
    ].filter(Boolean).join('\n'),
    {
      agentType: a.depth === 'deep' ? 'sdd:sdd-researcher-deep' : 'sdd:sdd-researcher',
      // effort matches each scout's frontmatter — explicit so the routing
      // holds on the workflow path regardless of how agentType resolves it
      effort: a.depth === 'deep' ? 'medium' : 'low',
      label: `scout${i + 1}:${a.depth}`,
      phase: 'Scout',
    }
  ).then(report => (report ? { angle: a.angle, depth: a.depth, report } : null))
))

const failed = angles.filter((a, i) => !scouts[i]).map(a => a.angle)
if (failed.length) log(`${failed.length} scout(s) failed — orchestrator should re-run those angles inline`)

// reports are the scouts' structured markdown (## Angle / Findings /
// Conventions / Risks / Open questions) — raw material for research.md
return { scouts: scouts.filter(Boolean), failed_angles: failed }
