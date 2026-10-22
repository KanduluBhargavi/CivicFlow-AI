# CivicFlow ML Model Manifest — Frozen Review/Resume Version

## Production models

### Department routing
- Task: 8-class civic department routing
- Production model: Logistic Regression
- Representation: word TF-IDF (1–2 grams) + character TF-IDF (3–5 grams)
- Selection: 4-model benchmark, 3-fold stratified CV, Macro-F1 primary
- Held-out accuracy: 93.93%
- Held-out Macro-F1: 93.41%
- Confidence: native `predict_proba`

### Priority / severity
- Task: Low / Medium / High priority classification (+ runtime Critical safety layer)
- Production model: SGDClassifier (log-loss), selected by 5-fold grouped CV macro-F1
- Representation: word TF-IDF (1-3) + char TF-IDF (3-5) + 12 urgency features (`urgency_features.py`, FEATURE_VERSION 1)
- Training data: `dataset/priority_dataset.csv` (CivicFlow in-domain labels)
- Grouped CV accuracy 78.7% / macro-F1 77.9%; grouped hold-out accuracy 80.2% / macro-F1 79.5%
- Retrain: `python backend/training/train_priority_model.py`; inference check: `python backend/training/test_priority_model.py`

## Preprocessing locked
- Drop missing target/text rows
- Normalize repeated whitespace
- Lowercasing and Unicode accent stripping inside TF-IDF
- Word unigrams + bigrams
- Character 3–5 grams for typos/noisy grievance text
- Remove exact duplicate normalized complaint text before splitting
- Remove contradictory identical department-text labels
- Exclude target-leakage columns from priority training
- Stratified splitting to preserve class balance
- No aggressive stemming/lemmatization

## Reproducibility
- Random state: 42
- scikit-learn pinned in `backend/requirements.txt`
- Reports and confusion matrices are under `models/reports/`
- Run `python backend/training/test_ml_stack.py` for a fast inference check.

## Freeze decision
The ML base is considered frozen for Review 2 / resume use. Future work should focus on application features and workflow unless new labelled production data is collected.

## Runtime safety guard
- High-priority safety floor prevents explicit serious hazards (e.g. transformer sparking, exposed electrical cables, open manholes, contaminated drinking water) from remaining Low/Medium due to short or sparse text.
- Critical remains reserved for explicit immediate life-safety emergencies.
