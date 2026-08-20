# FlashArray access

Use the controller endpoints recorded in RAS, normally `<testbed>-ct0` and
`<testbed>-ct1`. Confirm the requested bay's current visibility read-only before
running a test or collecting logs:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 <controller> \
  'wssdtool --bay <bay> ls'
```

A bay may be visible on one controller only. Do not assume controller topology
from the testbed nickname if RAS reports another route.
