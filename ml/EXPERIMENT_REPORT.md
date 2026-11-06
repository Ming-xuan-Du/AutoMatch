
# AutoMatch — Inventory Anomaly Detection Experiment

## 1. Objective

Evaluate a deterministic rule-based anomaly detector and a
scikit-learn Isolation Forest model using used-car dealership
inventory.

The system identifies potentially suspicious vehicle records
for manual review. It does not automatically modify prices,
remove vehicles, or determine whether a listing is incorrect.

## 2. Dataset

Source: Existing AutoMatch PostgreSQL inventory.

Reference year: 2026

- Total database vehicle records: 222
- Confirmed-present vehicles: 219
- Vehicles with missing cash prices: 18
- ML-eligible vehicles: 201
- Training vehicles: 161
- Held-out vehicles: 40

The three records with `missing_streak=1` were excluded
because they were not confirmed present in the latest
complete inventory synchronization.

Missing finance prices were not substituted for cash prices.

Dataset SHA-256:

33855e59f9fa67f871bb4a36d42e4d419dd2120d933789d1a727c6365dae7a21

## 3. Rule-Based Baseline

The initial validation baseline checks:

- Invalid vehicle years
- Nonpositive cash prices
- Nonpositive finance prices
- Negative mileage
- Negative missing streaks
- Empty listing identifiers, titles, and listing URLs

Historical change rules additionally flag:

- Cash-price changes of at least 50%
- Mileage decreases between inventory snapshots

The 50% threshold is a provisional review heuristic.

Observed database results:

- Current vehicles checked: 219
- Historical audit records checked: 14
- Invalid-value findings: 0
- Suspicious historical changes: 0
- Missing cash prices: 18 (tracked separately)

Zero findings do not prove that the inventory is error-free.

## 4. ML Feature Engineering

Feature version: v1

Numerical features:

1. Vehicle age = max(0, 2026 - year)
2. log1p(cash price)
3. log1p(mileage in kilometers)

Body style is retained as descriptive metadata but is not
included in the initial numerical model.

A StandardScaler and Isolation Forest are fitted together
inside a scikit-learn Pipeline.

The training split contains 161 vehicles. Neither the
held-out originals nor their synthetic alterations were
used for model fitting.

## 5. Isolation Forest Configuration

Model version: iforest_v1

- n_estimators: 200
- max_samples: auto
- contamination: 0.05
- random_state: 42
- n_jobs: 1

Training-only diagnostics:

- Training outlier predictions: 8
- Training inlier predictions: 153
- Median decision score: 0.133004

These are unsupervised training predictions, not
confirmed vehicle-data errors.

The model was persisted using joblib, accompanied by
a metadata file containing its configuration, source
dataset fingerprint, and software versions.

Model reload verification passed.

## 6. Held-Out Evaluation

The 40 held-out vehicles were used to create:

- 40 original assumed-normal control cases
- 40 deliberately altered synthetic anomaly cases

Synthetic scenarios (10 examples each):

- Cash price multiplied by 4
- Cash price divided by 5
- Mileage multiplied by 4
- Mileage divided by 5

Each synthetic example modifies one numerical attribute.

Training and evaluation vehicle identities do not overlap.

The model's existing threshold was retained. No threshold
tuning was performed on the held-out evaluation cases.

## 7. Evaluation Results

| Metric | Snapshot Rules | Isolation Forest | Paired Change Rules |
|---|---:|---:|---:|
| True positives | 0 | 9 | 30 |
| False negatives | 40 | 31 | 10 |
| False positives | 0 | 3 | 0 |
| True negatives | 40 | 37 | 40 |
| Synthetic recall | 0% | 22.50% | 75.00% |
| Assumed-normal flag rate | 0% | 7.50% | 0% |
| Balanced-set precision | N/A | 75.00% | 100.00% |

The evaluation uses synthetic labels. The original controls
have not been verified to be anomaly-free.

The paired change rules are not directly comparable to
the single-record methods because they receive additional
before/after information.

Original controls in the paired-change experiment are
constructed as unchanged cases, so their zero flag rate
should not be interpreted as a measured production
false-positive rate.

## 8. Isolation Forest Detection by Scenario

| Scenario | Detected | Recall |
|---|---:|---:|
| Cash price multiplied by 4 | 1/10 | 10% |
| Cash price divided by 5 | 1/10 | 10% |
| Mileage multiplied by 4 | 1/10 | 10% |
| Mileage divided by 5 | 6/10 | 60% |

The model was more sensitive to large mileage decreases
than to the other tested modifications.

## 9. Anomaly Score Movement

In 38 of 40 synthetic pairs, the altered vehicle received
a lower, more anomalous Isolation Forest decision score.

- More anomalous: 38
- Less anomalous: 2
- Ties: 0

This demonstrates directional score sensitivity in this
experiment, even though binary detection recall was 22.5%.

## 10. Flagged Original Vehicles

Three original held-out vehicles were flagged by the model:

- 2026 GMC HUMMER EV
- 2023 Mercedes-Benz G-Class AMG G 63
- 2005 Honda S2000

These listings have not been independently verified as
data errors.

Unusual vehicle categories and legitimate luxury vehicles
may generate model flags.

## 11. Interpretation

Isolation Forest detected 9 of 40 deliberately altered
vehicles, compared with 30 detected by the paired
historical change rules.

The historical rules had an advantage because they
received previous and updated values.

The model assigned more anomalous scores to most altered
vehicles but rarely crossed the fixed classification
threshold.

The observed results do not establish that Isolation
Forest is more reliable than deterministic rules.

## 12. Limitations

- Only 201 vehicles were eligible for ML preparation.
- The inventory contains heterogeneous vehicle types.
- Make and model were not included as ML features.
- Original evaluation controls were not manually labeled.
- Synthetic changes may not represent real dealership errors.
- The evaluation has an artificial 50% anomaly prevalence.
- Change-based rules use information unavailable to the
  snapshot-only model.
- Performance may vary across inventory snapshots.
- Production precision and recall remain unknown.
- No independent second holdout was used for model tuning.

## 13. Engineering Decision

Retain deterministic validation and historical change rules
as the primary source of explainable review findings.

Retain Isolation Forest v1 as an experimental supplementary
source of anomaly-review candidates.

All findings require human review.

Neither detector may directly modify inventory prices,
vehicle availability, or matching results.

## 14. Verification

At the end of Milestone 7.5:

- Backend pytest suite: 182 passed
- Model reload verification: passed
- Model/dataset fingerprint verification: passed
- Training/evaluation identity overlap: 0
- PostgreSQL modifications during evaluation: none

Generated model artifacts, metadata, and evaluation JSON
reports are stored locally under `ml/artifacts/` and
excluded from Git.
