---
name: pure-mfg-navigation
description: Navigate Pure Storage Manufacturing (MFG) Unit Journey, PTS test-detail pages, and ptjungle artifacts to resolve serial numbers to test runs, retrieve testbooks, and investigate any MFG failure. Use when the user provides a `*.mfg.purestorage.com` Unit Journey URL, manufacturing serial numbers, a PTS run ID, a `test_detail?run_id=` URL, a ptjungle artifact URL, or asks to collect or compare MFG logs.
---

# Pure MFG Navigation

Use this skill to resolve MFG inputs into concrete PTS runs and directly readable artifacts. It supports single-drive and lot-level failure investigations without manually opening every UI popup.

## Scope

This skill is read-only. Do not start tests, remove DUTs, change testbed state, or modify MFG records unless the user explicitly asks.

Internal MFG hosts commonly use certificates unavailable to the local trust store. For a supplied, trusted `*.mfg.purestorage.com` URL, use `curl -k` or Python's unverified SSL context only for that request.

## Navigation model

```text
Unit Journey
  → overview serial row
  → serial detail / Every run
  → PTS Test Detail
  → Test Logs
  → ptjungle artifacts
```

```text
Unit Journey serial row
  → PTS run ID
  → https://<site>-ptlb-1.mfg.purestorage.com/test_detail?run_id=<RUN_ID>
  → GET /core/api/v1/test/execution/logviewer/<RUN_ID>
  → ptjungle log directory
  → testbook.txt and related artifacts
```

The PTS test-detail page is dynamic, but its run API and ptjungle artifacts are normally directly readable.

## Step 1 — Start from the supplied source

### Direct ptjungle artifact URL

Download large artifacts first, then search locally.

```bash
LOG_URL='https://<host>.mfg.purestorage.com/log/.../testbook.txt'
OUT=/tmp/mfg-testbook.txt
curl -k --fail --silent --show-error --location "$LOG_URL" -o "$OUT"
rg -n -i -C 5 'fail|error|exception|traceback|assert|timeout' "$OUT"
```

Do not pipe large logs directly into search commands.

### PTS test-detail URL or run ID

Derive the PTS host and run ID, then query the logviewer endpoint.

```bash
PTS_HOST='https://khc-npi-ptlb-1.mfg.purestorage.com'
RUN_ID=25025
META=/tmp/mfg-run-${RUN_ID}-logviewer.json
curl -k --fail --silent --show-error \
  "$PTS_HOST/core/api/v1/test/execution/logviewer/$RUN_ID" \
  -o "$META"
```

Extract a ptjungle directory and fetch its testbook:

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

Append `testbook.txt` to the returned directory URL. If the API returns an authorization error, use the browser flow.

### Unit Journey URL or serial-number list

Unit Journey serves an empty initial overview and populates it via NiceGUI websocket events. Do not scrape the initial HTML and infer that no runs exist.

Use a headless browser to click **Look up**, select each serial, and extract every `test_detail?run_id=` link.

## Step 2 — Resolve serials with Playwright

Install Playwright only when unavailable:

```bash
python3 -m pip install --quiet --target /tmp/mfg-playwright playwright
PYTHONPATH=/tmp/mfg-playwright python3 -m playwright install chromium
```

If Chromium reports a missing shared library, install only the named runtime package. For example:

```bash
sudo -n apt-get install -y libgbm1
```

Reference implementation:

```python
import json
from urllib.parse import quote
from playwright.sync_api import sync_playwright

serials = ['<serial>']
base_url = 'https://<site>.mfg.purestorage.com'
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

Rules:

- Preserve every run and artifact link for each serial.
- Do not assume the newest run is relevant; compare test name, result, timestamps, and failing signature.
- A Unit Journey `FAIL` is only a summary. Confirm the actual failure in artifacts.
- Process serials from one site in one browser session.
- If a row click navigates away or times out, reload the Unit Journey page before processing the next serial.

## Step 3 — Fetch artifacts in parallel

For each PTS detail URL, derive its host and numeric run ID, query logviewer, then fetch `testbook.txt`. Use a bounded worker pool for lots and preserve a serial-to-artifact manifest.

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

Save:

- serial → run ID → PTS detail URL → artifact URL
- test name, result, start/end time, and failure signature
- relevant excerpts with line numbers
- inaccessible or missing artifacts

Do not paste complete large logs in chat unless asked.

## Step 4 — Investigate a failure

Start broad, then narrow to the named test, first failure marker, and relevant surrounding context.

```bash
rg -n -i -C 5 'FAIL_TEST|\bFAIL\b|Exception|Traceback|Assertion|ERROR|timeout' /tmp/mfg-testbook.txt
```

Use testbook structure to identify:

1. test or operation that failed
2. exact failure message and error code
3. affected serial, bay, controller, and run
4. timestamps and preceding warnings
5. test inputs, configuration, and external command output
6. whether the failure is primary, consequential, or a generic wrapper

Search the testbook for its test name, error code, command invocation, and timestamps. When an outer harness reports a generic failure, locate the lower-level command or component output that explains it. Do not assume a wrapper name is the root cause.

For unfamiliar tests, inspect the corresponding test definition, testbook metadata, and source/tool documentation before interpreting an error code. Keep conclusions specific to evidence in the collected artifacts.

## Step 5 — Compare a lot or repeated failures

Create a compact table before drawing conclusions:

```text
Serial       Run ID  Bay        Test / step        Signature                 Artifact
<serial>     <id>    <bay>      <name>             <exact error>             <testbook URL>
```

Then group by exact signature, test step, error code, hardware location, software version, or other evidence-backed discriminator. Report exceptions and missing artifacts rather than forcing a common root cause.

Clearly distinguish:

- **Fact:** quoted artifact evidence and counts.
- **Inference:** a plausible relationship supported by the pattern.
- **Unknown:** data not present in the testbook or supporting artifacts.

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

- Do not manually open many runs if Unit Journey and PTS APIs can enumerate them.
- Do not treat a top-level PTS result or wrapper as the root cause without inspecting artifacts.
- Do not stop after one representative drive for a lot-level request.
- Do not claim failures are identical unless their collected evidence matches.
- Do not mutate MFG equipment, drive data, or MFG records during navigation or investigation.
