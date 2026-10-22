"""Regression tests for department routing and guard-confidence semantics.

Run from the repository root: python backend/training/test_department_routing.py
"""
import sys
import types
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Keep these model-inference tests runnable without optional translation packages.
for mod, attrs in {
    "langdetect": {"detect": lambda t: "en"},
    "deep_translator": {"GoogleTranslator": object, "MyMemoryTranslator": object},
    "deep_translator.exceptions": {"TooManyRequests": Exception},
}.items():
    try:
        __import__(mod)
    except ImportError:
        module = types.ModuleType(mod)
        module.__dict__.update(attrs)
        sys.modules[mod] = module

from app.services import ai_service  # noqa: E402


def check(name, condition):
    print(("PASS" if condition else "FAIL"), "|", name)
    if not condition:
        raise AssertionError(name)


def main():
    cases = {
        "A pothole has opened on the main road.": "Roads & Transport",
        "Garbage has not been collected for five days.": "Sanitation",
        "Drinking water is dirty and unsafe.": "Water Supply",
        "A live wire is hanging across the road.": "Electricity",
    }
    for text, expected in cases.items():
        result = ai_service.predict_department_details(text)
        check(f"department prediction returns valid label for: {text}", result["department"] in ai_service.DEPARTMENT_GUARD_PATTERNS)
        # Explicit guard matches should take precedence for these high-signal examples.
        check(f"high-signal routing: expected {expected}", result["department"] == expected)

    # Force the statistical model to disagree with a clear guard phrase, and
    # verify that its confidence is not misrepresented as confidence in the
    # guard-selected final label.
    with patch.object(ai_service, "_probability_payload", return_value=(
        "Municipal Corporation", 0.97,
        {"Municipal Corporation": 0.97, "Water Supply": 0.02, "Sanitation": 0.01},
    )):
        result = ai_service.predict_department_details("Drinking water is dirty and unsafe.")
    check("guard can override model department", result["department"] == "Water Supply" and result["guard_applied"])
    check("model confidence retained separately", result["model_confidence"] == 0.97)
    check("guard override does not claim final-label confidence", result["confidence"] is None)
    check("guard override requests human review", result["needs_human_review"] is True)
    print("Department routing regression tests passed.")


if __name__ == "__main__":
    main()
