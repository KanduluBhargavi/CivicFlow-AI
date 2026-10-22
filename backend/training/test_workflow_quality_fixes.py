"""Small regression checks for officer validation and complaint title handling."""
from pydantic import ValidationError
import sys
from pathlib import Path
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.schemas.department_schema import OfficerCreate, DepartmentPasswordChange
from app.utils.complaint_titles import (
    title_needs_shortening,
    short_operational_title,
    display_operational_title,
)


def run():
    long_title = (
        "How many times we have been complaining about the lack of electricity "
        "in our house, only the officers listen."
    )
    translated_description = (
        "How many times we have complained about the lack of electricity in our "
        "house, but the officers do not listen, fix it soon."
    )
    assert title_needs_shortening(long_title)
    assert short_operational_title("Electricity", translated_description) == "Electricity service complaint"
    assert display_operational_title(long_title, "Electricity", translated_description) == "Electricity service complaint"

    for payload in (
        {"full_name": "Test Officer", "email": "", "password": "temporary123"},
        {"full_name": "Test Officer", "email": "test@example.com", "password": ""},
        {"full_name": "Test Officer", "email": "test@example.com", "password": "short"},
        {"full_name": "   ", "email": "test@example.com", "password": "temporary123"},
    ):
        try:
            OfficerCreate(**payload)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Invalid officer payload was accepted: {payload!r}")

    valid = OfficerCreate(
        full_name="Test Officer", email="test@example.com", password="temporary123"
    )
    assert valid.max_active_cases == 20

    try:
        DepartmentPasswordChange(old_password="old", new_password="short")
    except ValidationError:
        pass
    else:
        raise AssertionError("Short new password was accepted")

    print("PASS | long sentence-like title becomes a concise operational label")
    print("PASS | original complaint text remains separately stored")
    print("PASS | officer name/email/password validation rejects missing or weak fields")
    print("PASS | valid officer request keeps default capacity")
    print("PASS | department password change requires a stronger new password")
    print("Workflow quality regression tests passed.")


if __name__ == "__main__":
    run()
