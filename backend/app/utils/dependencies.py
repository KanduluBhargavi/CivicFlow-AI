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

    department = db.query(Department).filter(
        Department.department_email == email
    ).first()

    
    if department is None:
        raise credentials_exception

    return department


