"""Regression test for priority prediction (model + safety layers).

Run from the repository root:  python backend/training/test_priority_model.py
Only inference is performed. Missing optional translation libraries are stubbed
so the test works in a minimal environment.
"""
import sys
import types
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

for mod, attrs in {
    "langdetect": {"detect": lambda t: "en"},
    "deep_translator": {"GoogleTranslator": object, "MyMemoryTranslator": object},
    "deep_translator.exceptions": {"TooManyRequests": Exception},
}.items():
    try:
        __import__(mod)
    except ImportError:
        m = types.ModuleType(mod)
        m.__dict__.update(attrs)
        sys.modules[mod] = m

from app.services.ai_service import (  # noqa: E402
    assess_critical_risk, assess_high_risk, predict_priority_details,
)

# (text, department, set of acceptable priorities)
CASES = [
    ("Bridge collapsed and people are trapped under it.", "Roads & Transport", {"Critical"}),
    ("Live wire fallen on the road after the storm.", "Electricity", {"Critical"}),
    ("Transformer is sparking and smoking near the school.", "Electricity", {"Critical", "High"}),
    ("Open manhole on the main road, someone may fall in.", "Roads & Transport", {"High", "Critical"}),
    ("No drinking water for three days, children and elderly are falling sick.", "Water Supply", {"High", "Critical"}),
    ("Sewage is overflowing into homes and causing disease risk.", "Sanitation", {"High", "Critical"}),
    ("Ambulance took over an hour to reach a patient with chest pain.", "Healthcare", {"High", "Critical"}),
    ("Garbage not collected for a week, bins overflowing and smelling.", "Sanitation", {"Medium", "High"}),
    ("Streetlight on our lane has not worked for several weeks.", "Municipal Corporation", {"Medium", "High"}),
    ("Please update the owner name on my property tax receipt.", "Municipal Corporation", {"Low", "Medium"}),
    ("Request to repaint the faded bench in the park.", "Municipal Corporation", {"Low"}),
    ("Slight noise from a nearby shop in the evenings.", "Police", {"Low", "Medium"}),
]


def main():
    failures = 0
    for text, dept, ok in CASES:
        r = predict_priority_details(text, dept)
        passed = r["priority"] in ok
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} | {r['priority']:8s} (expected {'/'.join(sorted(ok)):14s}) "
              f"conf={r['confidence']} | {text}")
    # Negation and resolved-history regressions: these must not trigger the
    # active-hazard overrides merely because a hazard word is present.
    safety_cases = [
        ("There is no fire near the school.", False, False),
        ("The transformer is not sparking.", False, False),
        ("A fire happened last month and was extinguished.", False, False),
        ("There is no live wire; the cable was repaired yesterday.", False, False),
        ("A live wire is hanging over the road.", True, False),
        ("The transformer is sparking and smoking near the school.", False, True),
    ]
    for text, expected_critical, expected_high in safety_cases:
        critical = assess_critical_risk(text)["is_critical"]
        high = assess_high_risk(text)["is_high_risk"]
        passed = critical == expected_critical and high == expected_high
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} | safety negation/history | Critical={critical}, High={high} | {text}")
    if failures:
        raise SystemExit(f"{failures} priority scenario(s) failed")
    print("Priority regression test passed.")


if __name__ == "__main__":
    main()
