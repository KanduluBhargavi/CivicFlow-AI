# CivicFlow AI — ML Model Card

## Production ML tasks

CivicFlow uses two trained classifiers and one transparent safety escalation layer:

1. **Department routing** — predicts the responsible civic department.
2. **Priority/severity classification** — predicts Low, Medium, or High urgency (retrained on CivicFlow in-domain data with urgency features).
3. **Critical safety escalation** — promotes explicit life-safety emergencies to Critical because the available training data has no genuine Critical class.

## Model selection methodology

The project does **not** directly choose one classifier. Four conventional text-classification algorithms are benchmarked:

- Complement Naive Bayes
- Logistic Regression
- Linear SVM
- SGD Classifier (log-loss)

**Macro-F1** is the main selection metric because the class distributions are imbalanced.

### Department routing

The department benchmark uses **3-fold stratified cross-validation** on the training split. Each fold refits the TF-IDF representation and classifier. The winner is then evaluated once on an untouched 20% held-out test set.

Winner: **Logistic Regression**

- Held-out accuracy: **93.93%**
- Held-out macro-F1: **93.41%**
- CV macro-F1: **91.51%**

Production features combine **word TF-IDF (unigrams+bigrams)** and **character TF-IDF (3–5 grams)**. Character features help with spelling variants, typos, and noisy grievance text.

### Priority / severity

Priority is trained on CivicFlow's own human-labelled complaints (`dataset/priority_dataset.csv`, 1,438 rows / ~1,240 distinct complaints). The earlier CivicComp (Bengaluru, keyword-derived labels) model scored ~82% on its own test split but only **~23% accuracy on CivicFlow-style complaints** (domain shift). Mixing CivicComp into training also lowered in-domain accuracy, so it is no longer used for the production priority model.

- Features: word TF-IDF (1-3 grams) + character TF-IDF (3-5 grams) + 13 hand-built urgency features (`backend/app/services/urgency_features.py`: safety, health, vulnerable people, service outage, urgency words, duration/repetition, scale, mitigating/administrative wording, etc.)
- Runtime safety: Critical/High regex overrides reject clear local negation and resolved historical hazards; semantic similarity remains a signal strength, not a calibrated probability.
- Dynamic priority reporting: `score`/`raw_score` is the numeric situational score, `score_band` is its numeric band, and `priority` is the final label after documented safety/ML-floor adjustments.
- Selection: 5-fold **grouped** CV (templated "URGENT:/EMERGENCY:" variants of one complaint never straddle folds), macro-F1 primary. Four families compared; winner: **SGD (log-loss)**.
- CV accuracy: **78.7%**, CV macro-F1: **77.9%**
- Untouched grouped 80/20 hold-out: accuracy **80.2%**, macro-F1 **79.5%** (High 0.84, Medium 0.78, Low 0.76 F1)
- Deployed model is refit on all data; confidence from native `predict_proba`.
- Runtime safety layers (Critical / High-risk floors) sit on top and can only raise priority.

## Data leakage controls

- Exact repeated complaint text is removed before splitting.
- Contradictory identical department texts are excluded from department training.
- `severity_score`, `high_keywords_matched`, and `medium_keywords_matched` are excluded from priority inputs because they directly encode the target.
- Final test sets are not used to select the winning model.

## Confidence and human review

The deployed classifiers expose probability outputs. CivicFlow can surface confidence and route low-confidence cases for officer review rather than silently treating every prediction as certain.

## Why Random Forest is not in the benchmark

CivicFlow's main feature matrices are extremely high-dimensional and sparse TF-IDF vectors. Linear models, Naive Bayes, and SGD are more appropriate baselines for this representation. Random Forest is therefore intentionally replaced by SGD as the fourth scalable baseline rather than included only for appearance.

## Critical priority

The source severity dataset has only Low, Medium, and High labels. CivicFlow therefore does not fabricate Critical examples. Instead, explicit emergency conditions such as live electrical hazards, fire/explosion, structural collapse, trapped persons, and similarly immediate life-safety situations are handled by an auditable safety escalation layer.

## Dynamic priority (live score)

The ML model gives the *starting* priority from the complaint text. `backend/app/services/priority_engine.py` then keeps priority live (score 0-100, bands Low <35, Medium <62, High <88, Critical):

| Group | Signals |
|---|---|
| Reach | distinct citizens affected (reporters + "I'm affected" supporters), linked/duplicate reports, number of localities |
| Impact | essential service (water, power, health, school) incl. critical time, public-health risk, major infrastructure failure, vulnerable people, immediate-danger wording |
| Trend / history | worsening, recurring, missed deadline, failed/temporary repair, citizen reopen |
| Time | age vs. SLA (approaching / overdue), time since last status update |
| Context | active officer work in last 24h (small relief), verified emergency alert (manager sets via `POST /department/complaint/{id}/emergency-alert`) |

Rules: priority never drops below the ML base class; Critical only for ML safety override, verified emergency, or danger wording with a very high score; resolved complaints are frozen. Every change is logged as a `priority_change` event and the factor breakdown is returned as `priority_analysis` in complaint-detail APIs.
Triggers: submission, "I'm affected", status change, citizen reopen, dashboard/escalation loads, and a background refresh every `PRIORITY_REFRESH_MINUTES` (default 15; 0 disables).
Tests: `python backend/training/test_priority_engine.py`.

### How text signals are detected (semantic, not keyword lists)
Worsening, recurring, missed deadline, failed repair, essential service, critical time, public health, infrastructure failure, vulnerable people, danger and wide scale are detected with **Sentence-BERT** (`all-MiniLM-L6-v2`, the same model used for duplicate detection). Each signal is described by example sentences; the complaint is split into sentences and the strength (0-1) is the best cosine similarity to those examples. Points are scaled by strength, so paraphrases ("the crack keeps spreading") are understood without exact words. If the embedding model is unavailable the engine falls back to keyword patterns. Check/tune with `python backend/training/calibrate_semantic_signals.py` (`SEMANTIC_SIGNAL_LOW/HIGH`).
