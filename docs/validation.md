# Publication verification

Verified on macOS on 2026-11-13. This records checks for the standalone extraction, not a claim that all historical trajectories pass CAD evaluation.

- Python standard-library tests: 7 passed, covering catalog paths, missing rebuild behavior, both labels and updates, historical label preservation, append history, restart persistence, raw JSON bytes, tool images, empty reasoning text, Qwen posthoc provenance, and the original Host/Origin/token/static-file guards. Every test uses its own temporary state and random port.
- `node --check app.js` and Python compilation of viewer, renderer, adapters and import scripts passed.
- SimpleCADAPI 2.2.7 rendered the bundled synthetic box pair through `render_pairs.py`: first run `ok`, second run `cached`. Both source STEP hashes and shared-camera metadata were preserved. Viewing the PNGs requires no CAD SDK.
- Local links in the current README and current usage/catalog documentation were checked. `legacy-history.md` is explicitly historical and contains original experiment-specific paths and counts.
- The original `sites/v63-trajectory-labeler/annotations/` was not used as a test output. The standalone server can point at those files explicitly, but this publication did not restart the live service or change its active catalog.
- No model/API calls were required. The example trajectory is synthetic and labeled accordingly; it is not training data or a recorded model run.

CI repeats the HTTP/adapter tests on Python 3.10, 3.12 and 3.13 and checks frontend JavaScript syntax with Node 22. SDK render verification is optional and performed separately in the pinned CAD environment.
