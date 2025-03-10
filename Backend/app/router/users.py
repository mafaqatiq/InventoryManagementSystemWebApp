from typing import Annotated
from fastapi import Path, APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.database import SessionLocal
from app.models import Users
import starlette.status as status 
from .auth import get_current_user
from passlib.context import CryptContext

router = APIRouter(
    prefix= '/users',
    tags=['users']
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency Injection
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

#######################
# Pydantic Models
#######################

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)

#######################
# User Profile Endpoints
#######################

@router.get('/profile', status_code=status.HTTP_200_OK)
def get_user_profile(user: user_dependency, db: db_dependency):
    """Get the current user's profile information"""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    
    if not user_model:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user_model.id,
        "username": user_model.username,
        "email": user_model.email,
        "first_name": user_model.first_name,
        "last_name": user_model.last_name,
        "phone_number": user_model.phone_number,
        "role": user_model.role,
        "is_active": user_model.is_active
    }

@router.put('/password', status_code=status.HTTP_204_NO_CONTENT)
def change_password(user: user_dependency, db: db_dependency, password_update: PasswordUpdate):
    """Update the current user's password"""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    
    if not bcrypt_context.verify(password_update.current_password, user_model.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    user_model.hashed_password = bcrypt_context.hash(password_update.new_password)
    db.add(user_model)
    db.commit()

@router.put('/phone-number/{phone_number}', status_code=status.HTTP_204_NO_CONTENT)
def update_phone_number(user: user_dependency, db: db_dependency, phone_number: str):
    """Update the current user's phone number"""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    user_model.phone_number = phone_number
    db.commit()
