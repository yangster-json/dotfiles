# Pure MFG navigation (read-only)

Resolve MFG serials → PTS runs → ptjungle `testbook.txt`. Never start tests, remove DUTs, or modify MFG records/drive data unless asked. `*.mfg.purestorage.com` certs aren't locally trusted: use `curl -k` / unverified SSL only for user-supplied MFG URLs.

Chain: Unit Journey serial row → PTS run ID → `https://<site>-ptlb-1.mfg.purestorage.com/test_detail?run_id=<ID>` → `GET /core/api/v1/test/execution/logviewer/<ID>` (JSON containing ptjungle dir `http://<site>-ptjungle-1.mfg.purestorage.com/log/.../`) → `<dir>/testbook.txt`. Test-detail page is dynamic; API + ptjungle are directly readable (no login for archived runs; on auth error use browser flow).

## By input

- **ptjungle URL**: `curl -k -fsSL "$URL" -o /tmp/mfg-testbook.txt`, then `rg` locally (don't pipe big logs to grep).
- **PTS URL / run ID**: `curl -k -fsS "$PTS_HOST/core/api/v1/test/execution/logviewer/$RUN_ID" -o /tmp/mfg-run-$RUN_ID.json`; extract dir with `re.search(r'https?://[^"\\ ]+/log/[^"\\ ]+/', text)`; append `testbook.txt`.
- **Unit Journey URL / serials**: data arrives via NiceGUI websocket — initial HTML is empty, don't conclude "no runs". Use Playwright.

## Serials → runs (Playwright)

Install if missing: `python3 -m pip install -q --target /tmp/mfg-playwright playwright && PYTHONPATH=/tmp/mfg-playwright python3 -m playwright install chromium`. Missing shared lib → install only that package (e.g. `sudo -n apt-get install -y libgbm1`).

```python
import json; from urllib.parse import quote
from playwright.sync_api import sync_playwright
serials = ['PFMKH...']; base = 'https://pe16-oes-mtd-1.mfg.purestorage.com'
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page(ignore_https_errors=True)
    pg.goto(f'{base}/unit-journey?sn={quote(",".join(serials))}', wait_until='networkidle', timeout=120_000)
    pg.get_by_role('button', name='Look up').click(); pg.wait_for_timeout(15_000)
    runs = {}
    for s in serials:
        pg.get_by_text(s, exact=True).first.click(); pg.wait_for_timeout(500)
        runs[s] = [h for h in pg.locator('a').evaluate_all('a => a.map(x => x.href)') if 'test_detail?run_id=' in h]
    json.dump(runs, open('/tmp/mfg-run-ids.json', 'w'), indent=2); b.close()
```

- Keep every run per serial; don't assume latest. Check result, failing step/code, times, testbook before choosing.
- A Unit Journey `FAIL` may be unrelated; confirm signature in `testbook.txt`.
- Same-site serials: one browser session. Timeout after row click = page navigated; reload journey URL.

## Fetch testbooks

Per run: logviewer API → dir → `testbook.txt`, via `ThreadPoolExecutor(8–10)` with `urllib` + `ssl._create_unverified_context()`, UA `Mozilla/5.0`, timeouts 45s/90s. Save locally: `serial → run → PTS URL → testbook URL`, matched lines, errors/missing artifacts. Don't paste full logs.

## Investigate

`rg -n -i -C 5 'FAIL_TEST|\bFAIL\b|Exception|Traceback|Assertion|ERROR|timeout' /tmp/mfg-testbook.txt`. Find failed test/op, exact error, timestamps, serial/bay, preceding warnings, inputs, low-level output. PTS top-level result is a summary, not root cause; read test definition/source for unfamiliar tests. Lot-level request → cover all drives, not one representative; don't call failures identical without matching evidence.

## Report

```text
MFG investigation: <n> serials, <n> runs, <n> matching failures
Serial  Run ID  Bay  Test/step  Signature
<serial> (run <id>, <bay>, <test>)
  <exact line>
  artifact: <URL>
Distribution
  <signature/step/category>: <count>
Conclusion
  Facts: ...   Inference: ...   Unknowns: ...
```

Group by signature, step, error code, location, sw version; include missing artifacts.
