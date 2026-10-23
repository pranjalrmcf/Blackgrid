# Live dashboard and offline benchmark

Run from `C:\Blackgrid`. No virtual-environment activation is necessary.

Open the live dashboard:

```powershell
.\.venv\Scripts\python.exe scripts\open_dashboard.py
```

This opens a separate Edge profile after verifying the local server certificate. It pins that certificate's public key for this profile; it does not change the Windows trust store. Sign in by pasting the operator token from `.secrets/alice.token` into the password field. Keep that file private. The token is cleared after login; the session uses a Secure, HttpOnly, SameSite=Strict cookie and expires after 15 minutes. Sign out revokes it. Browser sessions do not authorize job API calls. Ordinary client tokens cannot open global operator data.

The page is also at `https://localhost:8765/api/v1/dashboard` when the local certificate is trusted by the browser. It updates every five seconds, pauses when hidden and shows stale/disconnected state. Operational charts contain observations since this API process started; they are bounded to 720 points. Restart clears sessions/history, while durable jobs, artifacts and billing remain on the original volume.

The benchmark section reads the latest sanitized stage report from the read-only `results/production_phase6` mount. It labels virtual users, counts, API timing and target resource measurements. It is the latest stage, not a combined capacity curve. Every stage's complete raw samples and report remain in the attempt folder. Operational rolling percentiles and benchmark percentiles have different measurement windows.

Run the bounded, free, synthetic benchmark:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase6.py
```

The helper uses the registered v2 protocol, 15 fixed inputs, a separate service, fresh credentials and a fresh retained volume. It stops that service after the pilot and retains output under `results/production_phase6/<attempt>`. It never sends work to the normal API or a hosted model. Do not start overlapping pilots. The production image must contain the current code; rebuild the `production` and `benchmark` targets when source changes. Existing tags are reused, not silently rebuilt.

To independently reconcile a retained successful attempt:

```powershell
.\.venv\Scripts\python.exe scripts\report_phase6.py results\production_phase6\<attempt>
```

This checks raw request counts and percentiles, timestamps, result verification, admission responses, actual users and every job against the separately exported durable ledger, then writes `reconciliation.json` and `stages.csv`. Preserve incomplete/failed attempts too; do not overwrite frozen protocols after inspection.

The API-only stages query capabilities for 15 seconds. Mixed stages offer the registered four-question workload for 30 seconds, then drain accepted work. Locust users wait 2–4 seconds between actions (including status polls); the observer samples resources every two seconds. There is no excluded warmup interval. These short, closed-loop mock runs are engineering observations, not steady-state service-level validation or evidence of real LLM performance. Generator CPU/RSS is separate from target resources; monitoring observer overhead is included in target use. The dashboard's polling overhead has not been isolated in an A/B load test.

The normal service retains its real-data configuration, tools and explicit live-call option. Synthetic configurations have smaller explicit numerical budgets for benchmarking only. No vLLM, GPU, new inference backend or paid call is needed.

Implementation references: [Locust headless execution](https://docs.locust.io/en/stable/running-without-web-ui.html), [request event hooks](https://docs.locust.io/en/stable/extending-locust.html), and [Chromium's public-key-scoped certificate verifier](https://chromium.googlesource.com/chromium/src/+/HEAD/services/network/ignore_errors_cert_verifier.h).
