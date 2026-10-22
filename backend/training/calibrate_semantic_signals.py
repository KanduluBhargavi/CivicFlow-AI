"""Check / calibrate the Sentence-BERT signal detector on your machine.

Run from the repository root (needs sentence-transformers and the cached model):
    python backend/training/calibrate_semantic_signals.py

Prints the strength (0..1) of each signal for probe complaints and flags probes
whose expected signal is weak (< 0.4) or whose unrelated signals fire (> 0.6).
If many expected signals are weak, lower SEMANTIC_SIGNAL_LOW/HIGH; if unrelated
ones fire, raise them.
"""
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.semantic_signals import signal_strengths  # noqa: E402

PROBES = [
    ("The crack in the wall is spreading across the building every day.", {"worsening", "infrastructure"}),
    ("They promised to repair the road last month but no one has come.", {"missed_deadline"}),
    ("We got it patched but within a week the pothole opened up again.", {"failed_repair", "recurring"}),
    ("Dirty sewage water is entering our drinking water pipes and kids are ill.", {"public_health", "vulnerable"}),
    ("There is no power at the district hospital during the night.", {"essential", "critical_time"}),
    ("Hundreds of families in the entire ward have no water.", {"wide_scale"}),
    ("A live wire is hanging low and someone could get electrocuted.", {"danger"}),
    ("Please repaint the faded bench in the park.", set()),
    ("I want to update the name on my property tax receipt.", set()),
]


def main():
    bad = 0
    for text, expected in PROBES:
        s = signal_strengths(text)
        if s is None:
            raise SystemExit("Sentence-BERT model unavailable - cannot calibrate.")
        weak = [e for e in expected if s[e] < 0.4]
        noisy = [k for k, v in s.items() if k not in expected and v > 0.6]
        bad += bool(weak or noisy)
        top = ", ".join(f"{k}={v:.2f}" for k, v in sorted(s.items(), key=lambda kv: -kv[1])[:4])
        print(("OK  " if not (weak or noisy) else "CHECK"), "|", text[:70], "\n      ", top,
              (f"\n       weak expected: {weak}" if weak else ""), (f"\n       unexpected: {noisy}" if noisy else ""))
    print(f"\n{len(PROBES) - bad}/{len(PROBES)} probes look right.")


if __name__ == "__main__":
    main()
