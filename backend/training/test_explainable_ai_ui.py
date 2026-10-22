from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
engine = (ROOT / "backend" / "app" / "services" / "priority_engine.py").read_text(encoding="utf-8")
route = (ROOT / "backend" / "app" / "routes" / "department_routes.py").read_text(encoding="utf-8")
html = (ROOT / "frontend" / "department_complaint_details.html").read_text(encoding="utf-8")
js = (ROOT / "frontend" / "js" / "department_details.js").read_text(encoding="utf-8")
css = (ROOT / "frontend" / "css" / "department_details.css").read_text(encoding="utf-8")

checks = {
    "priority breakdown exposes base priority": '"ml_base_priority"' in engine,
    "priority breakdown exposes confidence and review flag": '"ml_confidence"' in engine and '"needs_human_review"' in engine,
    "authorized department complaint endpoint returns priority analysis": '"priority_analysis": priority_breakdown(complaint)' in route,
    "HTML contains decision panel and metric targets": 'id="aiDecisionPanel"' in html and 'id="aiBasePriority"' in html and 'id="aiPriorityFactors"' in html,
    "frontend renders the API explanation": 'renderPriorityExplanation(c.priority_analysis, c)' in js,
    "factor details are rendered with textContent": 'detail.textContent = item.detail' in js,
    "decision panel has responsive styling": '.ai-decision-panel' in css and '@media (max-width: 800px)' in css,
}
failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + " | " + name)
if failed:
    raise SystemExit("Explainable AI static regression checks failed: " + ", ".join(failed))
print("Explainable AI static regression checks passed.")
