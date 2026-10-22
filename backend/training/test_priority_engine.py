"""Tests for the dynamic priority engine (pure scoring + DB refresh on SQLite).

Run from the repository root:  python backend/training/test_priority_engine.py
"""
import os, sys, types, warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import priority_engine as pe_version  # noqa: E402
from app.services.priority_engine import compute_dynamic_priority as score  # noqa: E402
print(f"Priority engine loaded: {pe_version.PRIORITY_ENGINE_FIX_VERSION}")

BASE = dict(base_priority="Medium", base_probs={"Low": .1, "Medium": .8, "High": .1}, critical=False,
            text="Garbage not collected near our lane.", department="Sanitation", affected_count=1,
            report_count=1, area_count=1, age_hours=1, since_update_hours=1, status="Assigned",
            reopen_count=0, emergency_alert=False, actively_worked=False)


def run(**kw):
    return score({**BASE, **kw})


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "|", name)
    return cond


ok = True
fresh = run()
ok &= check("fresh single complaint keeps ML base (Medium)", fresh["priority"] == "Medium")
ok &= check("routine garbage complaint is not public-health hazard",
            fresh["score"] < 50 and fresh["factors"] == [])
more = run(affected_count=12, report_count=6)
ok &= check("more affected people raises score", more["score"] > fresh["score"] + 8)
ok &= check("12 affected + 6 reports pushes Medium -> High", more["priority"] == "High")
aging = [run(age_hours=h)["score"] for h in (10, 50, 80, 120, 200)]
ok &= check("score never decreases as time passes", aging == sorted(aging))
ok &= check("long SLA breach raises Medium -> High", run(age_hours=200, since_update_hours=150)["priority"] == "High")
ok &= check("reopen raises score", run(reopen_count=2)["score"] > fresh["score"] + 10)
ok &= check("worsening wording raises score",
            run(text="The pothole is getting worse and wider every day")["score"] > fresh["score"])
ok &= check("missed deadline + failed temporary repair raise score",
            run(text="They promised to fix it but the temporary patch failed")["score"] > fresh["score"] + 6)
low = run(base_priority="Low", base_probs={"Low": .9, "Medium": .08, "High": .02}, text="Bench paint peeling",
          department="Municipal Corporation")
ok &= check("minor issue stays Low", low["priority"] == "Low")
ok &= check("essential service + public health outranks plain issue",
            run(department="Water Supply", text="Sewage is mixing with drinking water, children falling sick")["score"] > fresh["score"] + 12)
ok &= check("verified emergency -> Critical", run(emergency_alert=True)["priority"] == "Critical")
ok &= check("ML critical override stays Critical", run(base_priority="High", critical=True)["priority"] == "Critical")
ok &= check("High-risk floor keeps >= High", run(base_priority="Low", high_floor=True)["priority"] in ("High", "Critical"))
ok &= check("never drops below ML base", run(base_priority="High", base_probs={"High": .5, "Medium": .5},
                                              actively_worked=True)["priority"] in ("High", "Critical"))
ok &= check("Critical needs real emergency (big crowd alone caps at High)",
            run(base_priority="High", base_probs={"High": 1}, affected_count=500, report_count=60, area_count=8,
                age_hours=500, since_update_hours=400)["priority"] == "High")
ok &= check("factor breakdown is explained", all("factor" in f and "detail" in f for f in more["factors"]) and bool(more["reason"]))
ok &= check("raw score band is explicit", more["score_band"] == "High" and more["raw_score"] == more["score"])
ok &= check("label floor is documented when it differs from score band",
            run(base_priority="High", base_probs={"Low": .9, "Medium": .05, "High": .05})["label_adjustments"] == ["ml_base_priority_floor"])

# ---- semantic signal plumbing (fake encoder; real SBERT is checked by calibrate_semantic_signals.py)
import numpy as np  # noqa: E402
from app.services import semantic_signals as ss  # noqa: E402


def fake_encode(sentences):
    # deterministic bag-of-words hashing -> unit vectors (tests the math, not semantics)
    out = np.zeros((len(sentences), 256))
    for i, snt in enumerate(sentences):
        for w in snt.lower().replace(".", "").split():
            out[i, hash(w) % 256] += 1
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


proto_text = ss.PROTOTYPES["worsening"][0]
st = ss.signal_strengths(proto_text, encode=fake_encode)
ok &= check("semantic: text equal to a prototype -> strength 1.0", st["worsening"] > 0.99)
ok &= check("semantic: unrelated text -> low strengths",
            max(ss.signal_strengths("Bench paint peeling", encode=fake_encode).values()) < 0.5)
zero_signals = {k: 0.0 for k in ss.PROTOTYPES}
neutral = run(signals=zero_signals)
sem = run(signals={**zero_signals, "worsening": 1.0, "public_health": 1.0})
half = run(signals={**zero_signals, "worsening": 0.5, "public_health": 0.5})
# Compare injected signal strengths to a zero-signal baseline, not `fresh`,
# whose real SBERT output varies by model/version/cache.
ok &= check("engine: semantic strengths scale the points", sem["score"] > half["score"] > neutral["score"])
ok &= check("engine: injected signals override keyword matching",
            run(text="No problem at all", signals={**{k: 0.0 for k in ss.PROTOTYPES}, "danger": 1.0})["score"] > fresh["score"])

# ---- DB integration -------------------------------------------------------
try:
    import sqlalchemy  # noqa: F401
except ImportError:
    print("SKIP | DB integration tests (sqlalchemy not installed)")
    if not ok:
        raise SystemExit("priority engine tests failed")
    raise SystemExit(0)
for mod in ("langdetect",):
    sys.modules.setdefault(mod, types.ModuleType(mod))
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.complaint import Complaint  # noqa: E402
from app.models.complaint_event import ComplaintEvent  # noqa: E402
from app.models.complaint_support import ComplaintSupport  # noqa: E402
import app.models.user, app.models.department, app.models.complaint_assignment, app.models.complaint_escalation  # noqa: E402,F401
from app.services import priority_engine as pe  # noqa: E402

eng = create_engine("sqlite:///:memory:")
Base.metadata.create_all(eng)
db = sessionmaker(bind=eng)()
now = datetime.now(timezone.utc)
c = Complaint(citizen_id=1, department_id=None, title="Garbage", description="Garbage not collected near our lane.",
              state="X", district="D", area="A", address="a", pincode="1", priority="Medium", status="Assigned",
              predicted_department="Sanitation", created_at=now, incident_cluster_id=None)
db.add(c); db.flush(); c.incident_cluster_id = c.complaint_id
c.base_priority = "Medium"
c.priority_factors = '{"base": {"priority": "Medium", "probs": {"Low": 0.1, "Medium": 0.8, "High": 0.1}, "critical": false, "high_floor": false}}'
db.commit()
pe.refresh_priorities(db, [c]); s0 = c.priority_score
ok &= check("DB: initial refresh keeps Medium", c.priority == "Medium")
for uid in range(2, 16):
    db.add(ComplaintSupport(incident_cluster_id=c.incident_cluster_id, citizen_id=uid))
db.commit()
pe.refresh_cluster(db, c)
ok &= check("DB: 14 'I'm affected' clicks raise score", c.priority_score > s0 + 8)
ok &= check("DB: capped supporter boost does not falsely force High", c.priority == "Medium")
ok &= check("DB: raw score band is exposed separately from adjusted label",
            pe.priority_breakdown(c)["score_band"] == "Medium")
c.created_at = now - timedelta(days=10); db.commit()
before = c.priority_score; pe.refresh_priorities(db, [c])
ok &= check("DB: ageing 10 days raises score further", c.priority_score > before)
ok &= check("DB: actual priority change is logged as an event",
            db.query(ComplaintEvent).filter_by(complaint_id=c.complaint_id, event_type="priority_change").count() >= 1)
db.add(ComplaintEvent(complaint_id=c.complaint_id, event_type="citizen_reopen", title="r", actor="x")); db.commit()
before = c.priority_score; pe.refresh_priorities(db, [c])
ok &= check("DB: citizen reopen raises score", c.priority_score > before)
c.status = "Resolved"; frozen = (c.priority, c.priority_score); db.commit()
pe.refresh_priorities(db, [c])
ok &= check("DB: resolved complaints are frozen", (c.priority, c.priority_score) == frozen)
bd = pe.priority_breakdown(c)
ok &= check("DB: breakdown exposes factors", bool(bd["factors"]) and bd["ml_base_priority"] == "Medium")
ok &= check("DB: explanation score stays synchronized", "raw score" in (c.priority_reason or ""))
if not ok:
    raise SystemExit("priority engine tests failed")
print("Priority engine tests passed.")
