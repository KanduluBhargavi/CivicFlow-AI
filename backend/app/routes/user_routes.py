from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.utils.security import create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal, get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate, PasswordChange, OTPVerifyRequest, OTPResendRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.utils.security import hash_password, verify_password
from app.utils.auth import get_current_user
from app.models.department import Department
from app.utils.location_normalization import normalize_location
from app.services.notification_service import send_email
from app.services.auth_guard import assert_login_allowed, record_login_failure, clear_login_failures
from app.services.otp_service import (
    OTP_TTL_SECONDS,
    create_otp_challenge,
    verify_otp_challenge,
    resend_otp_challenge,
)
import os


router = APIRouter()

@router.post("/register")
def register_user(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start citizen registration by verifying the submitted email first.

    The user is not inserted into PostgreSQL until the OTP is verified.
    """
    email = user.email.strip().lower()
    phone = (user.phone or "").strip()

    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long."
        )

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please sign in instead."
        )

    if phone and db.query(User).filter(User.phone == phone).first():
        raise HTTPException(
            status_code=409,
            detail="An account with this phone number already exists."
        )

    state, district = normalize_location(user.state, user.district)

    pending_user = {
        "full_name": user.full_name.strip(),
        "email": email,
        "phone": phone,
        "password_hash": hash_password(user.password),
        "role": "Citizen",
        "department_id": user.department_id,
        "state": state,
        "district": district,
        "address": user.address,
        "area": user.area,
        "landmark": user.landmark,
        "pincode": user.pincode,
        "latitude": user.latitude,
        "longitude": user.longitude,
    }

    challenge = create_otp_challenge(
        email=email,
        purpose="registration",
        context={"pending_user": pending_user},
    )

    background_tasks.add_task(
        _send_security_otp,
        email,
        challenge["otp"],
        "Verify Your CivicFlow AI Registration",
        "registration",
    )

    response = {
        "otp_required": True,
        "challenge_id": challenge["challenge_id"],
        "masked_email": challenge["masked_email"],
        "expires_in": challenge["expires_in"],
        "resend_after": challenge["resend_after"],
        "message": "Verification code sent. Verify your email to create the account.",
    }

    if os.getenv("OTP_DEV_MODE", "false").lower() == "true":
        response["dev_otp"] = challenge["otp"]

    return response


@router.post("/register/verify-otp")
def verify_registration_otp(
    payload: OTPVerifyRequest,
    db: Session = Depends(get_db),
):
    if not payload.otp.isdigit() or len(payload.otp) != 6:
        raise HTTPException(status_code=400, detail="Enter a valid 6-digit OTP.")

    result = verify_otp_challenge(
        payload.challenge_id,
        payload.otp,
        "registration",
    )

    if not result["ok"]:
        raise HTTPException(status_code=result["status"], detail=result["detail"])

    data = result["context"]["pending_user"]

    # Re-check uniqueness at verification time in case another registration
    # completed while this OTP was pending.
    if db.query(User).filter(User.email == data["email"]).first():
        raise HTTPException(status_code=409, detail="This email is already registered.")

    if data["phone"] and db.query(User).filter(User.phone == data["phone"]).first():
        raise HTTPException(status_code=409, detail="This phone number is already registered.")

    new_user = User(
        full_name=data["full_name"],
        email=data["email"],
        phone=data["phone"],
        password=data["password_hash"],
        role=data["role"],
        department_id=data["department_id"],
        state=data["state"],
        district=data["district"],
        address=data["address"],
        area=data["area"],
        landmark=data["landmark"],
        pincode=data["pincode"],
        latitude=data["latitude"],
        longitude=data["longitude"],
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This email or phone number is already registered."
        )

    return {
        "message": "Email verified. Account created successfully.",
        "user_id": new_user.user_id,
    }


@router.post("/register/resend-otp")
def resend_registration_otp(
    payload: OTPResendRequest,
    background_tasks: BackgroundTasks,
):
    result = resend_otp_challenge(payload.challenge_id, "registration")

    if not result["ok"]:
        raise HTTPException(status_code=result["status"], detail=result["detail"])

    background_tasks.add_task(
        _send_security_otp,
        result["email"],
        result["otp"],
        "Verify Your CivicFlow AI Registration",
        "registration",
    )

    response = {
        "message": "A new verification code has been sent.",
        "masked_email": result["masked_email"],
        "expires_in": result["expires_in"],
        "resend_after": result["resend_after"],
    }

    if os.getenv("OTP_DEV_MODE", "false").lower() == "true":
        response["dev_otp"] = result["otp"]

    return response


ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH") or ""


def _send_security_otp(to_email: str, otp: str, subject: str, purpose: str):
    purpose_text = (
        "complete your CivicFlow AI registration"
        if purpose == "registration"
        else "reset your CivicFlow AI password"
    )

    message = f"""
    <p>Use the following verification code to {purpose_text}.</p>

    <div style="
        margin: 22px 0;
        padding: 18px;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 12px;
        text-align: center;
    ">
        <div style="font-size: 13px; color: #64748b; margin-bottom: 8px;">
            One-time verification code
        </div>
        <div style="
            font-size: 34px;
            font-weight: 800;
            letter-spacing: 8px;
            color: #1d4ed8;
        ">
            {otp}
        </div>
    </div>

    <p>This code expires in <b>{OTP_TTL_SECONDS // 60} minutes</b>.</p>
    <p>If you did not request this action, you can ignore this email.</p>
    """

    return send_email(to_email, subject, message)


def _build_login_identity(username: str, password: str, db: Session):
    normalized_username = (username or "").strip().lower()
    try:
        is_admin = bool(ADMIN_EMAIL and ADMIN_PASSWORD_HASH and normalized_username == ADMIN_EMAIL
                        and verify_password(password, ADMIN_PASSWORD_HASH))
    except (ValueError, TypeError):
        is_admin = False
    if is_admin:
        return {
            "token_payload": {"sub": ADMIN_EMAIL, "role": "admin"},
            "response": {
                "role": "admin",
                "actual_role": "admin",
                "name": "Administrator",
            },
        }

    department = db.query(Department).filter(
        (Department.department_email == username)
        | (Department.username == username)
    ).first()

    if department:
        if not verify_password(password, department.password):
            raise HTTPException(status_code=401, detail="Invalid Email or Password")

        return {
            "token_payload": {
                "sub": department.department_email,
                "role": "department",
            },
            "response": {
                "role": "department",
                "actual_role": "manager",
                "name": department.department_name,
                "department": department.department_name,
            },
        }

    db_user = db.query(User).filter(User.email == username).first()

    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid Email or Password")

    user_role = (db_user.role or "Citizen").lower()
    if user_role == "officer" and db_user.is_active is False:
        raise HTTPException(status_code=403, detail="This officer account is inactive. Contact your department manager.")

    if user_role == "officer" and db_user.department_id:
        department_obj = db.query(Department).filter(
            Department.department_id == db_user.department_id
        ).first()

        return {
            "token_payload": {"sub": db_user.email, "role": "officer"},
            "response": {
                "role": "department",
                "actual_role": "officer",
                "name": db_user.full_name,
                "department": (
                    department_obj.department_name
                    if department_obj
                    else "Department"
                ),
            },
        }

    return {
        "token_payload": {"sub": db_user.email, "role": "citizen"},
        "response": {
            "role": "citizen",
            "actual_role": "citizen",
            "name": db_user.full_name,
        },
    }


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Normal email/password login with lightweight brute-force protection.

    OTP remains reserved for first-time email verification and password recovery.
    """
    login_name = form_data.username.strip()
    if "@" in login_name:
        login_name = login_name.lower()

    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = assert_login_allowed(login_name, client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        identity = _build_login_identity(
            login_name,
            form_data.password,
            db,
        )
    except HTTPException as exc:
        locked, retry = record_login_failure(login_name, client_ip)
        if locked:
            raise HTTPException(
                status_code=429,
                detail="Too many failed login attempts. Login is temporarily locked for 15 minutes.",
                headers={"Retry-After": str(retry)},
            )
        raise exc

    clear_login_failures(login_name, client_ip)
    access_token = create_access_token(data=identity["token_payload"])

    return {
        "access_token": access_token,
        "token_type": "bearer",
        **identity["response"],
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="No CivicFlow citizen/officer account was found with this email."
        )

    challenge = create_otp_challenge(
        email=email,
        purpose="password_reset",
        context={"user_id": user.user_id},
    )

    background_tasks.add_task(
        _send_security_otp,
        email,
        challenge["otp"],
        "CivicFlow AI Password Reset Code",
        "password_reset",
    )

    response = {
        "challenge_id": challenge["challenge_id"],
        "masked_email": challenge["masked_email"],
        "expires_in": challenge["expires_in"],
        "resend_after": challenge["resend_after"],
        "message": "Password reset code sent.",
    }

    if os.getenv("OTP_DEV_MODE", "false").lower() == "true":
        response["dev_otp"] = challenge["otp"]

    return response


@router.post("/forgot-password/resend-otp")
def resend_password_reset_otp(
    payload: OTPResendRequest,
    background_tasks: BackgroundTasks,
):
    result = resend_otp_challenge(payload.challenge_id, "password_reset")

    if not result["ok"]:
        raise HTTPException(status_code=result["status"], detail=result["detail"])

    background_tasks.add_task(
        _send_security_otp,
        result["email"],
        result["otp"],
        "CivicFlow AI Password Reset Code",
        "password_reset",
    )

    response = {
        "message": "A new password reset code has been sent.",
        "masked_email": result["masked_email"],
        "expires_in": result["expires_in"],
        "resend_after": result["resend_after"],
    }

    if os.getenv("OTP_DEV_MODE", "false").lower() == "true":
        response["dev_otp"] = result["otp"]

    return response


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    if not payload.otp.isdigit() or len(payload.otp) != 6:
        raise HTTPException(status_code=400, detail="Enter a valid 6-digit OTP.")

    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 8 characters long."
        )

    result = verify_otp_challenge(
        payload.challenge_id,
        payload.otp,
        "password_reset",
    )

    if not result["ok"]:
        raise HTTPException(status_code=result["status"], detail=result["detail"])

    user = db.query(User).filter(
        User.user_id == result["context"]["user_id"]
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")

    user.password = hash_password(payload.new_password)
    db.commit()

    return {"message": "Password reset successfully. You can now sign in."}


@router.get("/profile")
def get_profile(
    current_user: User = Depends(get_current_user)
):

    return {
        "name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "state": current_user.state,
        "district": current_user.district,
        "area": current_user.area,
        "address": current_user.address,
        "pincode": current_user.pincode
    }



@router.put("/profile")
def update_profile(
    profile: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    current_user.full_name = profile.full_name
    current_user.phone = profile.phone
    state, district = normalize_location(profile.state, profile.district)
    current_user.state = state
    current_user.district = district
    current_user.area = profile.area
    current_user.address = profile.address
    current_user.pincode = profile.pincode

    db.commit()

    return {
        "message": "Profile Updated Successfully"
    }


@router.put("/change-password")
def change_password(
    passwords: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(
        User.user_id == current_user.user_id
    ).first()

    if not verify_password(
        passwords.old_password,
        user.password
    ):
        return {
            "message": "Old password is incorrect"
        }

    user.password = hash_password(passwords.new_password)

    db.commit()

    return {
        "message": "Password Changed Successfully"
    }
