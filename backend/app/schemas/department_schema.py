import re
from pydantic import BaseModel, Field, field_validator


class ComplaintStatusUpdate(BaseModel):

    status: str
    note: str | None = None


class OfficerActionCreate(BaseModel):
    action_type: str = "Officer Note"
    note: str


class DepartmentProfileUpdate(BaseModel):

    department_name: str
    description: str | None = None


class DepartmentPasswordChange(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

class OfficerCreate(BaseModel):
    # These credentials are required by the API, not just by browser controls.
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=15)
    state: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=80)
    area: str | None = Field(default=None, max_length=120)
    specialization: str | None = Field(default=None, max_length=120)
    max_active_cases: int = Field(default=20, ge=1, le=200)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Officer name is required")
        return value

    @field_validator("email")
    @classmethod
    def normalize_and_validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid officer email address")
        return value

    @field_validator("state", "district")
    @classmethod
    def validate_officer_location(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Officer posting state and district are required")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Temporary password cannot be blank")
        return value


class OfficerStatusUpdate(BaseModel):
    is_active: bool


class OfficerProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=100)
    phone: str | None = Field(default=None, max_length=15)
    state: str = Field(min_length=2, max_length=80)
    district: str = Field(min_length=2, max_length=80)
    area: str | None = Field(default=None, max_length=120)
    specialization: str | None = Field(default=None, max_length=120)
    max_active_cases: int = Field(ge=1, le=200)

    @field_validator("full_name")
    @classmethod
    def validate_profile_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Officer name is required")
        return value

    @field_validator("email")
    @classmethod
    def normalize_profile_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid officer email address")
        return value

    @field_validator("state", "district")
    @classmethod
    def validate_officer_posting(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Officer posting state and district are required")
        return value




class ManualRerouteRequest(BaseModel):
    department_id: int
    reason: str | None = None



class ManualEscalationRequest(BaseModel):
    reason: str
    level: int = 2
