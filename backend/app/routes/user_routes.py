from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session
from app.schemas.auth_schema import LoginRequest
from app.utils.security import verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal, get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate,UserUpdate,PasswordChange
from app.utils.security import hash_password, verify_password
from app.utils.auth import get_current_user
from app.models.department import Department


router = APIRouter()

@router.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    new_user=User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password=hash_password(user.password),
        role="Citizen",
        department_id=user.department_id,
        state=user.state,
        district=user.district,
        address=user.address,
        area=user.area,
        landmark=user.landmark,
        pincode=user.pincode,
        latitude=user.latitude,
        longitude=user.longitude
        
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "message": "User Registered Successfully",
        "user_id": new_user.user_id
    }

ADMIN_EMAIL = "admin@civicflow.com"
ADMIN_PASSWORD = "admin123"
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    
    if (
    form_data.username == ADMIN_EMAIL
    and form_data.password == ADMIN_PASSWORD
):
        token = create_access_token(
        {
            "sub": ADMIN_EMAIL,
            "role": "admin"
        }
        )

        return {
        "access_token": token,
        "role": "admin",
        "name": "Administrator"
        }
    
    department = db.query(Department).filter((Department.department_email == form_data.username) |
    (Department.username == form_data.username)).first()

    db_user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if department:

        if not verify_password(
        form_data.password,
        department.password
        ):
            raise HTTPException(
            status_code=401,
            detail="Invalid Email or Password"
            )

        token = create_access_token(
        {
            "sub": department.department_email,
            "role": "department"
        }
    )

        return {

        "access_token": token,

        "role": "department",

        "department": department.department_name}

    if not db_user:
        raise HTTPException(
        status_code=401,
        detail="Invalid Email or Password"
    )

    if not verify_password(form_data.password, db_user.password):
        raise HTTPException(
        status_code=401,
        detail="Invalid Email or Password"
    )

    access_token = create_access_token(
        data={
            "sub": db_user.email,
            "role": "citizen"
            }
    )

    return {
    "access_token": access_token,
    "token_type": "bearer",
    "role": "citizen",
    "name": db_user.full_name
}

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
    current_user.state = profile.state
    current_user.district = profile.district
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