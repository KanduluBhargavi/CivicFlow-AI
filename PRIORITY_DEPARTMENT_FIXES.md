# CivicFlow AI — priority and department fixes

This update preserves the existing trained model artifacts and dataset. No model was retrained and no score weights or priority thresholds were tuned.

## Changes

- Priority Critical/High safety overrides now reject clear local negation (for example, “the transformer is not sparking”) and clearly resolved/historical hazards (for example, “a fire happened last month and was extinguished”). Positive active hazards still trigger the relevant safety rule.
- Department routing output now separates `model_confidence` from confidence in the final department. If a domain guard overrides the model, `confidence` is `null`, `model_confidence` retains the classifier's confidence, the guard is identified, and human review is requested.
- Dynamic priority API breakdowns now expose `raw_score`, `score_band`, and `label_adjustments` separately from the final `priority`. This avoids implying the final label always equals the numeric score's band when a safety or ML-base floor adjusts the label.
- Priority explanations are refreshed when the score changes even if the priority label remains unchanged.
- Model-card docs now correctly say 13 hand-built urgency features.
- Added/expanded regression tests for safety negation/history, department guard confidence semantics, score-band/label semantics, and database refresh behavior.

## Tests run

From the repository root:

```bash
python backend/training/test_priority_model.py
python backend/training/test_priority_engine.py
python backend/training/test_department_routing.py
python -m compileall -q backend/app backend/training
```

All three regression test scripts passed in the editing environment.

## Important environment note

The existing model artifacts were serialized with scikit-learn 1.9.1, while the editing environment has scikit-learn 1.8.0. Inference tests passed, but scikit-learn emitted `InconsistentVersionWarning`. Use the version pinned/used when training the models (or retrain in the target environment) before treating the serialized models as production-ready. This update intentionally does not retrain or replace the models.

## Remaining validation

These code fixes do not prove real-world end-to-end accuracy. Before deployment, evaluate the complete priority pipeline on independently labeled, held-out complaints, including multilingual translation cases, ambiguous department routing, false emergency triggers, and missed emergencies. Sentence-BERT similarity strengths are not calibrated probabilities.
