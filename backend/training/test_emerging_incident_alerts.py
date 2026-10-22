from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_alert_threshold_is_explainable_and_not_too_sensitive():
    source = (ROOT / "app/routes/admin_routes.py").read_text(encoding="utf-8")
    assert "def _should_raise_surge_alert" in source
    assert "reports_last_24h >= 3" in source
    assert "reports_last_24h >= 2 and critical_reports_last_24h >= 1" in source
    assert '@router.get("/analytics/surge-alerts")' in source

def test_admin_ui_explains_signal_and_has_no_translation_review_feature():
    html = (ROOT.parent / "frontend/admin_dashboard.html").read_text(encoding="utf-8")
    js = (ROOT.parent / "frontend/js/admin_dashboard.js").read_text(encoding="utf-8")
    assert "Emerging Incident Alerts" in html
    assert "not proof of a confirmed emergency" in html
    assert "get('/admin/analytics/surge-alerts')" in js
    assert "translation-feedback" not in html
    assert "loadTranslationFeedback" not in js

def test_citizen_translation_report_removed():
    html = (ROOT.parent / "frontend/complaint_details.html").read_text(encoding="utf-8")
    js = (ROOT.parent / "frontend/js/complaint_details.js").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "translationFeedbackPanel" not in html
    assert "translation-feedback/complaints" not in js
    assert "translation_feedback_router" not in main

if __name__ == "__main__":
    for test in (test_alert_threshold_is_explainable_and_not_too_sensitive, test_admin_ui_explains_signal_and_has_no_translation_review_feature, test_citizen_translation_report_removed):
        test()
    print("Emerging incident alert checks passed")
