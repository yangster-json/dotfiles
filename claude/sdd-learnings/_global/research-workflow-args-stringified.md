---
name: research-workflow-args-stringified
description: research.js/review.js crashed when the Workflow `args` object arrived as a JSON string — fixed 2026-07-31 by a tolerant parse at the top of both scripts
metadata:
  type: feedback
  stage: research
  tags: workflow,research,args,fallback
---

The research stage's `run_via: workflow research` failed instantly (12 ms, zero
agents spawned) with:

    Error: undefined is not an object (evaluating 'angles.map')
    at <anonymous> (workflow.js:23:46)

Cause: `workflows/research.js` line 24 does a bare destructure —
`const { feature, slug, workdir, angles, models = {} } = args` — but the
Workflow tool's `args` input has no declared type in its schema, so a JSON
object passed in the tool call can reach the script as a **string** instead of
a parsed object. Destructuring a string yields `undefined` for every key, and
the first `.map` throws.

**How to avoid:** when a workflow script fails on the very first property
access of `args` with ~0 ms runtime and 0 agents, do not re-send the same call
hoping for a different serialization — it is deterministic. Either

1. take the stage's declared `fallback:` immediately (spawn the stage's agents
   yourself via the Agent tool, matching `agentType` and the `models` map), or
2. make the script tolerant at the top:
   `const input = typeof args === 'string' ? JSON.parse(args) : args`
   and destructure from `input`.

**Resolved 2026-07-31 (option 2).** Both `workflows/research.js` and
`workflows/review.js` now start with
`const input = typeof args === 'string' ? JSON.parse(args) : args`, destructure
from `input`, and throw a message naming the bad payload if the required keys
are missing. The edit landed in the plugin *source*
(`~/.claude/sdd-plugin/workflows/`, which is the `jasyang-dotfiles` marketplace
directory) and was mirrored into the installed copy under
`plugins/cache/jasyang-dotfiles/sdd/0.1.1/workflows/`, so `/plugin update` no
longer reverts it.

Still worth knowing: a workflow that dies on its first `args` property access
with ~0 ms runtime and 0 agents is a deterministic serialization problem, not a
flake — re-sending the identical call will fail identically. Any *new* workflow
script must carry the same guard; the tool schema still declares no type for
`args`.
