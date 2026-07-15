from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session
from app.utils.security import hash_password
from app.schemas.auth_schema import LoginRequest
from app.utils.security import verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal, get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate,UserUpdate,PasswordChange
from app.utils.security import hash_password, verify_password
from app.utils.auth import get_current_user


router = APIRouter()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):

    db_user = db.query(User).filter(
        User.email == form_data.username
    ).first()

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
        data={"sub": db_user.email}
    )

    return {
    "access_token": access_token,
    "token_type": "bearer",
    "role": db_user.role,
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