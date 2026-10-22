"""Dependency-free regression checks for the translation correction workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_model_and_router_are_registered():
    model = (ROOT / "app/models/translation_feedback.py").read_text(encoding="utf-8")
    routes = (ROOT / "app/routes/translation_feedback_routes.py").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    for field in ("complaint_id", "citizen_id", "issue_type", "suggested_correction", "status", "reviewer_note"):
        assert field in model, f"Missing persisted feedback field: {field}"
    assert "Complaint.citizen_id == current_user.user_id" in routes
    assert 'detail="Admin access required"' in routes
    assert '@router.patch("/admin/{feedback_id}")' in routes
    assert "TranslationFeedback" in main and "translation_feedback_router" in main


def test_citizen_and_admin_interfaces_are_connected():
    citizen_html = (ROOT.parent / "frontend/complaint_details.html").read_text(encoding="utf-8")
    citizen_js = (ROOT.parent / "frontend/js/complaint_details.js").read_text(encoding="utf-8")
    admin_html = (ROOT.parent / "frontend/admin_dashboard.html").read_text(encoding="utf-8")
    admin_js = (ROOT.parent / "frontend/js/admin_dashboard.js").read_text(encoding="utf-8")
    assert "translationFeedbackPanel" in citizen_html
    assert "/translation-feedback/complaints/" in citizen_js
    assert 'data-tab="translation-feedback"' in admin_html
    assert "get('/translation-feedback/admin')" in admin_js
    assert "reviewTranslationFeedback" in admin_js


if __name__ == "__main__":
    test_model_and_router_are_registered()
    test_citizen_and_admin_interfaces_are_connected()
    print("Translation feedback workflow checks passed.")
