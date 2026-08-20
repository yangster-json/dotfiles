---
name: pure-mfg-navigation
description: Navigate Pure Storage Manufacturing (MFG) Unit Journey, PTS test-detail pages, and ptjungle artifacts to resolve serials to runs, retrieve testbooks, and investigate any MFG failure. Use when the user provides a `*.mfg.purestorage.com` Unit Journey URL, manufacturing serials, a PTS run ID, a `test_detail?run_id=` URL, a ptjungle artifact URL, or asks to collect or compare MFG logs.
---

# Pure MFG Navigation

Use this skill to turn MFG serial numbers into concrete test runs and directly accessible test artifacts. It supports large multi-drive investigations without manually clicking every UI popup.

## Scope

This skill is read-only. Do not start tests, remove DUTs, change testbed state, or modify MFG records unless the user explicitly asks.

Internal MFG hosts commonly use certificates unavailable to the local trust store. For read-only `curl`/Python requests, use `-k` / an unverified SSL context only for the specific trusted `*.mfg.purestorage.com` URL supplied by the user.

## MFG navigation model

The normal UI path is:

```text
Unit Journey
  → overview serial row
  → serial detail / Every run
  → open_in_new detail link
  → PTS Test Detail
  → Test Logs
  → testbook.txt
```

The underlying identifiers and URLs are:

```text
Unit Journey serial row
  → PTS run ID
  → https://<site>-ptlb-1.mfg.purestorage.com/test_detail?run_id=<RUN_ID>
  → GET /core/api/v1/test/execution/logviewer/<RUN_ID>
  → ptjungle log directory
  → <directory>/testbook.txt
```

Example:

```text
run 25025
https://khc-npi-ptlb-1.mfg.purestorage.com/test_detail?run_id=25025
https://khc-npi-ptlb-1.mfg.purestorage.com/core/api/v1/test/execution/logviewer/25025
http://khc-npi-ptjungle-1.mfg.purestorage.com/log/.../testbook.txt
```

The PTS test-detail page is dynamic, but the run API and ptjungle artifacts are directly readable.

## Step 1 — Start from the user's source

### A direct ptjungle artifact URL

Download it directly to a temporary file, then search locally. Do not pipe a large log directly into `grep`.

```bash
LOG_URL='https://<host>.mfg.purestorage.com/log/.../testbook.txt'
curl -k --fail --silent --show-error --location "$LOG_URL" -o /tmp/mfg-testbook.txt
rg -n -i -C 4 'fail|error|exception' /tmp/mfg-testbook.txt
```

### A PTS test-detail URL or run ID

Derive the PTS host and run ID, then query:

```bash
PTS_HOST='https://khc-npi-ptlb-1.mfg.purestorage.com'
RUN_ID=25025
curl -k --fail --silent --show-error \
  "$PTS_HOST/core/api/v1/test/execution/logviewer/$RUN_ID" \
  -o "/tmp/mfg-run-$RUN_ID-logviewer.json"
```

Extract the ptjungle directory URL from the response, then append `testbook.txt`.

```bash
python3 - <<'PY'
import re
from pathlib import Path

metadata = Path('/tmp/mfg-run-25025-logviewer.json').read_text()
match = re.search(r'https?://[^"\\ ]+/log/[^"\\ ]+/', metadata)
if not match:
    raise SystemExit('No ptjungle log directory found')
print(match.group(0))
PY
```

The API can be used without logging in for archived runs in the environments tested here. If it returns an authorization error, use the browser flow below.

### A Unit Journey URL or serial-number list

The Unit Journey HTML contains an initial empty overview; its actual data arrives through NiceGUI websocket events. Do **not** scrape only the initial HTML and conclude there are no runs.

Use a headless browser to click **Look up**, then click each serial row and extract the PTS detail anchor(s).

## Step 2 — Resolve serials to run IDs with Playwright

Use Python 3 and Playwright. Install only if unavailable:

```bash
python3 -m pip install --quiet --target /tmp/mfg-playwright playwright
PYTHONPATH=/tmp/mfg-playwright python3 -m playwright install chromium
```

Some minimal hosts need Chromium runtime libraries. If startup reports a missing shared library, install only that named package, for example:

```bash
sudo -n apt-get install -y libgbm1
```

Create a temporary script that:

1. Loads `https://<host>/unit-journey?sn=<comma-separated serials>`.
2. Clicks **Look up** and waits for the overview table.
3. For each serial, clicks its table row.
4. Extracts all anchors matching `test_detail?run_id=` from the serial detail.
5. Saves `serial → [run detail URLs]` JSON locally.

Reference implementation:

```python
import json
from urllib.parse import quote
from playwright.sync_api import sync_playwright

serials = ['PFMKH...']
base_url = 'https://pe16-oes-mtd-1.mfg.purestorage.com'
journey_url = f'{base_url}/unit-journey?sn={quote(",".join(serials))}'

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(ignore_https_errors=True)
    page.goto(journey_url, wait_until='networkidle', timeout=120_000)
    page.get_by_role('button', name='Look up').click()
    page.wait_for_timeout(15_000)

    runs = {}
    for serial in serials:
        page.get_by_text(serial, exact=True).first.click()
        page.wait_for_timeout(500)
        runs[serial] = page.locator('a').evaluate_all(
            '(anchors) => anchors.map((anchor) => anchor.href)'
        )

    with open('/tmp/mfg-run-ids.json', 'w') as output:
        json.dump(runs, output, indent=2)
    browser.close()
```

### Important handling rules

- A serial may have multiple runs and multiple testbooks. Preserve every run; do not assume the latest run is the relevant one.
- Check result, failing step/code, start/end time, and testbook before choosing a run.
- A Unit Journey `FAIL` can be an unrelated failure. Confirm the target signature in `testbook.txt`.
- When all serials are in the same site, process them in a single browser session. This is much faster than navigating separately.
- If browser navigation timing out after a row click, the page may have navigated away. Resolve the serials in one page/session or reload the Unit Journey URL before proceeding.

## Step 3 — Query PTS API and fetch logs in parallel

For each PTS detail URL, derive the host and numeric run ID. Query its logviewer endpoint, find the `.../log/.../` directory, and fetch `testbook.txt`.

Use a bounded Python thread pool (8–10 workers) for large lots. Save all output locally before searching. Example structure:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import ssl
from urllib.request import Request, urlopen

ssl_context = ssl._create_unverified_context()

def fetch_testbook(serial, pts_host, run_id):
    metadata_url = f'{pts_host}/core/api/v1/test/execution/logviewer/{run_id}'
    request = Request(metadata_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, context=ssl_context, timeout=45) as response:
        metadata = response.read().decode()

    match = re.search(r'https?://[^"\\ ]+/log/[^"\\ ]+/', metadata)
    if not match:
        raise RuntimeError(f'No log directory for run {run_id}')

    testbook_url = f'{match.group(0)}testbook.txt'
    request = Request(testbook_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, context=ssl_context, timeout=90) as response:
        return serial, run_id, testbook_url, response.read().decode('utf-8', 'replace')

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch_testbook, serial, pts_host, run_id) for serial, pts_host, run_id in targets]
    for future in as_completed(futures):
        serial, run_id, url, text = future.result()
```

For a reproducible multi-run investigation, save:

- `serial → run ID → PTS detail URL → ptjungle testbook URL`
- extracted matching lines
- errors such as missing artifacts or inaccessible runs

Do not emit complete large logs in chat unless the user asks. Report exact relevant lines and retain the artifact URLs for traceability.

## Step 4 — Investigate a MFG testbook

Start broad, then narrow to the named test, first failure marker, and surrounding context:

```bash
rg -n -i -C 5 'FAIL_TEST|\bFAIL\b|Exception|Traceback|Assertion|ERROR|timeout' /tmp/mfg-testbook.txt
```

Identify the failed test or operation, exact error, timestamps, affected serial/bay, preceding warnings, test inputs, and lower-level command output. Treat a top-level PTS result as a summary: inspect the underlying artifacts before describing a root cause.

For unfamiliar tests, inspect the test definition, metadata, and relevant source or tool documentation before interpreting errors. Keep conclusions grounded in the collected artifacts.

## Step 5 — Aggregate and report

For batch requests, make a compact table first:

```text
Serial             Run ID  Bay        Test / step            Signature
<serial>           <id>    <bay>      <name>                 <exact error>
```

Then group by exact signature, test step, error code, hardware location, software version, or another evidence-backed discriminator. Include exceptions and missing artifacts.

Distinguish:

- **Fact:** exact log line and frequency.
- **Inference:** a plausible relationship supported by the pattern.
- **Unknown:** information absent from the collected artifacts.

## Output format

```text
MFG investigation: <count> serials, <count> runs, <count> matching failures

<serial> (run <id>, <bay>, <test>)
  <exact relevant log line>
  artifact: <URL>

Distribution
  <signature / step / category>: <count>

Conclusion
  Facts: <evidence-backed summary>
  Inference: <if justified>
  Unknowns: <missing evidence or required follow-up>
```

## Do not do

- Do not manually click dozens of runs if the Unit Journey and PTS APIs can enumerate them.
- Do not treat a top-level PTS result or wrapper as the root cause without inspecting artifacts.
- Do not stop after one representative drive when the request is a lot-level comparison.
- Do not claim failures are identical unless the collected evidence matches.
- Do not mutate MFG equipment or drive data during log navigation.
