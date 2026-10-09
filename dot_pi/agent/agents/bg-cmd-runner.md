---
name: bg-cmd-runner
description: Run any potentially long-running command (build, copy, soak, repro, test wait) in the background, locally or over ssh, and notify the session when it exits. Use instead of blocking or polling.
runner:
  type: external-cli
  command: /u/jasyang/.pi/agent/bin/bg-cmd-runner
  promptDelivery: stdin
systemPromptMode: replace
---

The task must contain the payload as JSON wrapped in `BACKGROUND_TEST_RUNNER_JSON`
tags (open and close); prose is rejected. Schema (`remote` optional; `ssh_user`/`run_as`
optional inside it):

```
{"cwd":"/root/dir","command":["bash","-c","..."],"iterations":1,"label":"my-watch","stop_on_failure":true,"remote":{"host":"host-ct0","ssh_user":"root"}}
```

Return the deterministic report unchanged.
