from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.models.department import Department
from app.database import SessionLocal
from app.models.user import User
from app.utils.security import decode_access_token
from jose import JWTError, jwt
from app.database import get_db
from app.config import SECRET_KEY, ALGORITHM


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):

    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid Token")

    email = payload.get("sub")

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user



def get_current_department(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials"
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        
        email = payload.get("sub")
        
        if email is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    role = (payload.get("role") or "").lower()

    department = db.query(Department).filter(
        Department.department_email == email
    ).first()

    if department is not None:
        department._actor_role = "manager"
        department._actor_name = department.department_name
        department._actor_user_id = None
        return department

    # Individual officer accounts reuse the existing User table.
    # They are mapped to a department through users.department_id and
    # can access the same department workspace with their own identity.
    if role == "officer":
        officer = db.query(User).filter(User.email == email).first()
        if officer and officer.is_active is False:
            raise HTTPException(status_code=403, detail="This officer account is inactive")
        if officer and officer.department_id:
            department = db.query(Department).filter(
                Department.department_id == officer.department_id
            ).first()
            if department:
                department._actor_role = "officer"
                department._actor_name = officer.full_name
                department._actor_user_id = officer.user_id
                return department

    raise credentials_exception


