
# AutoMatch — Natural-Language Extraction Evaluation

## Model
- Provider: Local Ollama
- Model: qwen3:4b-instruct
- Task: Extract seven structured vehicle search requirements
- Output validation: Pydantic
- Dataset: 50 manually labeled synthetic customer statements

## Evaluation Results

| Metric | Result |
|---|---:|
| Field decision accuracy | 93.43% (327/350) |
| Explicit requirement recall | 100% (90/90) |
| Explicit value precision | 90% (90/100) |
| Hallucinated constraint rate | 3.85% (10/260) |
| Ambiguity/preference accuracy | 75% (15/20) |
| Perfect statement accuracy | 58% (29/50) |
| Failed API calls | 0/50 |

## Key Findings

The model successfully extracted all 90 explicitly labeled
requirements in this synthetic evaluation.

However, it incorrectly activated 10 nonmandatory constraints.
The most common issue was inferring body style from a
vehicle's model name.

AutoMatch requires salesperson review and manual correction
of extracted fields before deterministic inventory matching.

## Reproduction

Set AI_PROVIDER=ollama and ensure the local model is running.

Run:

python -m evaluation.run_extraction_eval

## Limitations

- The evaluation uses synthetic statements, not real customers.
- The dataset is relatively small.
- The reported results are an initial benchmark, not a
  held-out final evaluation after model tuning.
- Performance may vary on unseen customer language.
- Human review reduces risk but does not guarantee correctness.
