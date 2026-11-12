# CI workflow validated locally (2026-11-11)

Every job in `.github/workflows/ci.yml`, run on commit `72e528e` before
any push. The Python suites ran in virtualenvs installed from each service's
pinned `requirements.txt` (fastapi 0.161.1, starlette 1.10.0, httpx 0.28.1,
cryptography 50.0.2, pyjwt 2.15.1), as CI installs them.

| Job | Command | Result |
|---|---|---|
| Frontend | `npm run lint` | clean |
| Frontend | `npx tsc --noEmit` | clean |
| Frontend | `npm test` | 24 passed (8 files) |
| Frontend | `npm run build` | compiled successfully |
| API | `pytest services/api/tests` | 126 passed |
| Orchestrator | `pytest services/orchestrator/tests` | 50 passed |
| Worker | `pytest services/worker/tests` | 9 passed |
| Stream processor | `pytest services/video-ingest/tests` | 64 passed |
| Detector | `pytest services/detector/tests` | 10 passed |
| Stream publisher | `pytest services/stream-publisher/tests` | 3 passed |
| Compose | `docker compose config --quiet` (base and soak overlay) | valid |

Playwright E2E (Section C) against the compose stack: 5/5 consecutive runs
from reset (`e2e/five-runs-final/`), then a confirmation run on the final
demo history, 9/9 steps.

**CI on GitHub: green** (2026-11-12, run 43214271332 on `63c8ec3`, all 7 jobs passed):
https://github.com/Uday-Teja-nex/smartops/actions/runs/43214271332
The only annotations are GitHub's Node.js 20 and ubuntu-latest deprecation notices.
