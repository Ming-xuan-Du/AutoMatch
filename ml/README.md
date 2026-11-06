
# AutoMatch — Inventory Anomaly Detection

Milestone 7 implements exploratory data analysis,
deterministic data-quality rules, an experimental
Isolation Forest model, and reproducible evaluation.

## Environment

- Python 3.13
- PostgreSQL
- SQLAlchemy
- NumPy
- scikit-learn
- joblib
- pytest

Run all commands from the AutoMatch repository root.

Use the existing `.venv` and PostgreSQL configuration.

## 1. Explore the inventory

```powershell
python -m ml.explore_inventory
python -m ml.analyze_inventory
python -m ml.inspect_audit_changes
```

These scripts inspect PostgreSQL without modifying records.

## 2. Run deterministic rules

```powershell
python -m ml.run_rule_baseline
```

The baseline validates individual vehicle values and
historical inventory changes.

Findings indicate invalid values or suspicious changes
that may require manual review.

## 3. Prepare the ML dataset

```powershell
python -m ml.prepare_features
python -m ml.prepare_evaluation
```

Feature version v1 uses:

- Vehicle age
- Log-transformed cash price
- Log-transformed mileage

The evaluation preparation uses a deterministic,
identity-disjoint train/holdout split.

## 4. Train Isolation Forest

```powershell
python -m ml.train_isolation_forest
```

The model is trained only on the training partition.

Locally generated artifacts:

- `ml/artifacts/isolation_forest_v1.joblib`
- `ml/artifacts/isolation_forest_v1_metadata.json`

## 5. Evaluate the model

```powershell
python -m ml.evaluate_anomalies
```

The evaluation runner verifies the dataset fingerprint,
training identities, model-file checksum, and compatible
scikit-learn version before loading the saved pipeline.

The model is not retrained or tuned during evaluation.

The evaluation report is written to:

`ml/artifacts/isolation_forest_v1_evaluation.json`

If the inventory fingerprint changes, do not bypass
the mismatch check. Treat the new inventory as a new
experiment and retain the earlier evaluation record.

## 6. Run tests

```powershell
python -m pytest -q
```

## 7. Reproducibility

- Fixed split seed: 42
- Fixed model seed: 42
- Reference year: 2026
- Feature version: v1
- Model version: iforest_v1

The generated metadata contains the data fingerprint,
training configuration, and installed software versions.

Use the recorded compatible dependency versions when
loading an existing model.

Model artifacts use joblib serialization. Never load
untrusted model files.

## 8. Safety and limitations

- No model output automatically changes inventory.
- Missing cash prices are not replaced by finance prices.
- Anomaly scores are not probabilities of incorrect data.
- Model predictions are only potential review candidates.
- Synthetic evaluation metrics are not production metrics.
- Original evaluation vehicles are not verified normal.
- Customer personal information is not part of this pipeline.

See `ml/EXPERIMENT_REPORT.md` for results and limitations.
