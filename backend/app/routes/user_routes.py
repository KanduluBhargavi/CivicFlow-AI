from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session
from app.utils.security import hash_password
from app.schemas.auth_schema import LoginRequest
from app.utils.security import verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from app.database import SessionLocal
from app.models.user import User
from app.schemas.user_schema import UserCreate


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