---
name: bg-cmd-runner
description: Run any potentially long-running command (build, copy, soak, repro, test wait) in the background, locally or over ssh, and notify the session when it exits. Use instead of blocking or polling.
runner:
  type: external-cli
  command: /u/jasyang/.pi/agent/bin/bg-cmd-runner
  promptDelivery: stdin
systemPromptMode: replace
---

Run only a payload formatted exactly as:

<BACKGROUND_TEST_RUNNER_JSON>
{"cwd":"/absolute/path","command":["command","arg"],"iterations":1,"label":"safe-name","stop_on_failure":true,"remote":{"host":"optional-ssh-host","ssh_user":"optional-ssh-user","run_as":"optional-remote-user"}}
</BACKGROUND_TEST_RUNNER_JSON>

Return the deterministic report unchanged.
