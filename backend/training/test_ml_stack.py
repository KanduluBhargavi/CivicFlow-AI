"""Fast smoke test for the frozen CivicFlow ML stack.
Run from repository root:
    python backend/training/test_ml_stack.py
No retraining is performed.
"""
from pathlib import Path
import joblib
import re

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models"

DEPT_MODEL = joblib.load(MODEL_DIR / "department_model.pkl")
DEPT_VEC = joblib.load(MODEL_DIR / "vectorizer.pkl")
PRI_MODEL = joblib.load(MODEL_DIR / "priority_model.pkl")
PRI_VEC = joblib.load(MODEL_DIR / "priority_vectorizer.pkl")

EXPECTED_DEPARTMENTS = {
    "Education", "Electricity", "Healthcare", "Municipal Corporation",
    "Police", "Roads & Transport", "Sanitation", "Water Supply"
}
EXPECTED_PRIORITIES = {"Low", "Medium", "High"}


def priority_features(text):
    import sys
    from scipy import sparse
    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.urgency_features import matrix
    clean = re.sub(r"\s+", " ", str(text)).strip()
    return sparse.hstack([PRI_VEC.transform([clean]), sparse.csr_matrix(matrix([clean]))]).tocsr()


def predict_department(text):
    x = DEPT_VEC.transform([text])
    pred = DEPT_MODEL.predict(x)[0]
    probs = DEPT_MODEL.predict_proba(x)[0] if hasattr(DEPT_MODEL, "predict_proba") else None
    return pred, (float(max(probs)) if probs is not None else None)


def predict_priority(text, department):
    x = priority_features(text)
    pred = PRI_MODEL.predict(x)[0]
    probs = PRI_MODEL.predict_proba(x)[0] if hasattr(PRI_MODEL, "predict_proba") else None
    return pred, (float(max(probs)) if probs is not None else None)


def main():
    samples = [
        "There is a large pothole on the main road near the bus stand.",
        "No drinking water has been supplied to our locality since yesterday.",
        "Garbage has not been collected for several days and is overflowing.",
        "A transformer is sparking and power supply is interrupted.",
    ]
    assert set(DEPT_MODEL.classes_) == EXPECTED_DEPARTMENTS, DEPT_MODEL.classes_
    assert set(PRI_MODEL.classes_) == EXPECTED_PRIORITIES, PRI_MODEL.classes_
    assert hasattr(DEPT_MODEL, "predict_proba"), "Department model must expose probabilities"
    assert hasattr(PRI_MODEL, "predict_proba"), "Priority model must expose probabilities"
    for text in samples:
        dept, dc = predict_department(text)
        pri, pc = predict_priority(text, dept)
        assert dept in EXPECTED_DEPARTMENTS
        assert pri in EXPECTED_PRIORITIES
        assert dc is None or 0.0 <= dc <= 1.0
        assert pc is None or 0.0 <= pc <= 1.0
        print(f"PASS | {dept:24s} | {pri:6s} | dept_conf={dc:.3f} | priority_conf={pc:.3f}")
    print("ML stack smoke test passed.")

if __name__ == "__main__":
    main()
