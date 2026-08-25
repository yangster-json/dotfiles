# FlashBlade access

RAS labels such as `flashblade` and notes/environment fields define the actual
route. Read `JUMP_HOST`, controller/blade fields, and `notes` rather than
constructing a host name.

Typical Thor topology:

```text
FM / jump host -> blade
ssh -J <jump-host> root@<blade>
```

For example, RAS may resolve an alias to a node with:

```text
JUMP_HOST=fw-zeus00
controller=ir6
notes: ssh -J fw-zeus00 root@ir6
```

Use exactly:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -J fw-zeus00 root@ir6
```

Confirm the blade identity with a shallow read-only command before transferring
files or running a test.

Do not use `HLOB=y`, `ir@<ras-name>`, or a generic `make cp` rule for a
FlashBlade target unless it has been reviewed to implement this exact route.
