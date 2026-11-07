
# AutoMatch — Milestone 8: Inventory Anomaly Review

## 1. Overview

Milestone 8 integrates the existing inventory anomaly detectors
into the AutoMatch FastAPI and React application.

The system identifies potentially suspicious vehicle records,
stores review findings, and allows human reviewers to record
decisions and notes.

An anomaly finding is a review suggestion, not a confirmed
vehicle data error.

The existing inventory synchronization, historical tracking,
customer requirement extraction, and deterministic matching
systems remain separate.

## 2. Architecture

The anomaly review workflow consists of:

1. PostgreSQL vehicle inventory and historical audit records.
2. Deterministic vehicle data-quality rules.
3. Historical price and mileage change rules.
4. Experimental Isolation Forest detection.
5. Anomaly scan orchestration and fingerprint deduplication.
6. PostgreSQL anomaly finding persistence.
7. FastAPI review endpoints.
8. React review dashboard and human decisions.

Original inventory values are never automatically corrected
or deactivated by anomaly detection.

## 3. Detection Methods

### 3.1 Deterministic Rules

Existing rule detectors:

- `ml/rule_baseline.py`
- `ml/change_rules.py`

They detect conditions including:

- Invalid vehicle years.
- Nonpositive cash or finance prices.
- Negative mileage.
- Invalid listing identity fields.
- Invalid missing-streak values.
- Large historical cash-price changes.
- Historical mileage decreases.

Missing cash prices are tracked as data-completeness issues,
not automatically classified as anomalies.

### 3.2 Isolation Forest

Model version: `iforest_v1`

Feature version: `v1`

Features:

1. Vehicle age.
2. Log-transformed cash price.
3. Log-transformed mileage.

The model uses a StandardScaler and IsolationForest Pipeline.

The deployed v1 artifact uses reference year 2026.

Inference requires compatible metadata, feature ordering,
software versions, and verified local model artifacts.

The model is optional. Deterministic rules can operate when
the ML artifact is unavailable.

### 3.3 Model Limitations

The original Milestone 7 synthetic evaluation produced:

- Isolation Forest recall: 22.5%.
- Isolation Forest assumed-normal flag rate: 7.5%.
- Historical paired-change rule recall: 75%.

The comparison is not equal-information because historical
change rules receive previous and current values, whereas
Isolation Forest receives only current numerical features.

The evaluation used synthetic anomalies and assumed-normal
controls, so these metrics are not production accuracy claims.

ML anomaly scores are not probabilities or evidence that
a listing is incorrect.

Specialty, luxury, and uncommon vehicles may be flagged
because their numerical features are unusual.

## 4. PostgreSQL Persistence

Alembic migration:

`b492ba2cacee_add_anomaly_review_tables.py`

The migration creates two tables.

### anomaly_flags

Stores:

- Vehicle reference.
- Optional historical inventory-change reference.
- Detector and issue type.
- Explanation and evidence.
- Unique finding fingerprint.
- Optional model score and version.
- First and last detected timestamps.
- Current review status.
- Reviewer note and review timestamp.

### anomaly_review_events

Stores review history, including:

- Finding reference.
- Previous and new review status.
- Previous and new reviewer notes.
- Change timestamp.

Review events are created by the review service when an
actual review change occurs.

The current implementation does not provide a separate
reviewer identity or authentication-account audit trail.

### Finding Idempotency

Finding fingerprints identify equivalent detection evidence.

Repeated scans reuse existing findings instead of inserting
duplicates.

An existing human review decision and reviewer note are
preserved during repeated scans.

Materially changed evidence can produce a new finding.

PostgreSQL enforces fingerprint uniqueness.

## 5. Controlled Anomaly Scanning

Run commands from the repository root.

Preview deterministic rules only:

```powershell
python -m backend.anomalies.scan_cli --no-model
```

Preview rules and Isolation Forest:

```powershell
python -m backend.anomalies.scan_cli
```

Persist findings explicitly:

```powershell
python -m backend.anomalies.scan_cli --apply
```

The default preview uses a PostgreSQL read-only transaction.

The apply mode writes anomaly findings within a controlled
database transaction.

The CLI uses a PostgreSQL advisory transaction lock to
coordinate concurrent scan executions using the same CLI.

The current FastAPI API does not expose a scan-trigger endpoint.

## 6. FastAPI Endpoints

The anomaly review API provides:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/anomalies` | List and filter findings |
| GET | `/api/anomalies/{id}` | View a finding and review history |
| PATCH | `/api/anomalies/{id}/review` | Update review status or note |

Supported review statuses:

- `pending`
- `valid_issue`
- `false_alarm`

List filters include review status and detector type.

The API also supports pagination.

Review updates use a database transaction and row-level
locking on PostgreSQL.

Identical review updates do not create redundant history events.

The API does not modify vehicle inventory data.

## 7. React Review Dashboard

The dashboard is integrated into the existing AutoMatch
React application.

Features include:

- Optional anomaly review panel.
- Review status and detector filters.
- Paginated finding list.
- Vehicle information and original listing links.
- Detection explanations.
- ML scores and model version.
- Read-only detection evidence.
- Human review status and notes.
- Review history.
- Loading, empty, and API error states.

The dashboard preserves the existing customer search,
AI requirement extraction, and inventory status interfaces.

## 8. Local Development Security

Review endpoints require:

`X-AutoMatch-Review-Key`

The local API key is configured through:

`AUTOMATCH_REVIEW_API_KEY`

The key must contain at least 32 characters.

Example configuration:

```dotenv
AUTOMATCH_REVIEW_API_KEY=REPLACE_WITH_A_RANDOM_SECRET
```

Do not commit actual keys or `.env` files.

The React dashboard accepts the key at runtime and keeps
it in component memory rather than localStorage or
Vite environment variables.

This shared API key is a local demonstration control,
not production-grade authentication or authorization.

The review API should not be exposed directly to the public
internet without a proper authentication, authorization,
and transport-security design.

## 9. Local Startup

Start FastAPI from the project root:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start React:

```powershell
cd frontend
npm run dev
```

The Vite development server proxies `/api` requests
to the local FastAPI server.

## 10. Testing

Backend:

```powershell
python -m pytest tests/ -q
```

Frontend:

```powershell
cd frontend
npm run test -- --run
npm run build
```

Latest verified regression results during Milestone 8:

- 248 backend tests passed.
- 21 frontend tests passed.
- 269 combined tests passed.
- Vite production build passed.

Test coverage includes anomaly persistence, duplicate
fingerprints, model validation, detector integration,
review state transitions, review history, API behavior,
and React dashboard interactions.

## 11. Real PostgreSQL Verification

The integration experiment scanned:

- 219 confirmed-present vehicles.
- 14 historical inventory audit records.

Initial results:

- 0 deterministic rule findings.
- 11 Isolation Forest findings.
- 11 new records persisted in anomaly_flags.

A repeated scan created zero duplicate findings.

The review dashboard successfully loaded the findings.

A note-only review of Finding #11 verified that:

- The finding remained pending.
- The reviewer note persisted.
- One review history event was created.
- The saved review was visible in React.

This was an integration test, not a confirmation that
the flagged vehicle contained an actual error.

## 12. Known Limitations

- Isolation Forest is experimental.
- No model-driven vehicle ranking is performed.
- Historical findings are retained even when the latest
  inventory may no longer exhibit the same condition.
- There is no automatic resolved/unresolved finding lifecycle.
- Review status represents a human decision, not current
  anomaly presence.
- The shared local review API key is not user authentication.
- Reviewer identity is not recorded.
- Concurrent writes through interfaces outside the controlled
  CLI locking protocol require additional coordination.
- Full deployment, production security, monitoring, and CI/CD
  are deferred to Milestone 9.

## 13. Next Milestone

Milestone 9 focuses on:

- CI/CD.
- Reproducible environment setup.
- Dependency and secret management.
- Deployment.
- Architecture documentation.
- End-to-end demonstration.
- Final portfolio and resume presentation.
