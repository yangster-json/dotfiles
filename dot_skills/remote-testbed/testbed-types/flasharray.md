# FlashArray

Use RAS controller endpoints (normally `<testbed>-ct0`/`-ct1`, but trust RAS over the nickname). Check bay visibility read-only first; a bay may show on one controller only:

```bash
ssh -o BatchMode=yes -o ConnectTimeout=15 -J root@<ras_name> <controller> 'wssdtool --bay <bay> ls'
```
