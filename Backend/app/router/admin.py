from typing import Annotated, List, Optional
from fastapi import Path, APIRouter, Body
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.database import SessionLocal
from app.models import Users
import starlette.status as status 
from .auth import get_current_user, bcrypt_context

router = APIRouter(
    prefix= '/admin',
    tags=['admin']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency Injection
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

# Pydantic models for user management
class UserBase(BaseModel):
    email: str
    username: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None
    is_active: bool = True
    role: str = "user"

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int
    
    class Config:
        orm_mode = True

# Helper function to check admin role
def check_admin(user):
    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

# User management endpoints
@router.get('/users', response_model=List[UserResponse], status_code=status.HTTP_200_OK)
def get_all_users(db: db_dependency, user: user_dependency):
    check_admin(user)
    return db.query(Users).all()

@router.get('/users/{user_id}', response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user(user_id: int, db: db_dependency, user: user_dependency):
    check_admin(user)
    
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    return db_user

@router.put('/users/{user_id}', response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_user(user_id: int, user_update: UserUpdate, db: db_dependency, user: user_dependency):
    check_admin(user)
    
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Update only provided fields
    update_data = user_update.dict(exclude_unset=True)
    
    # Hash password if provided
    if 'password' in update_data:
        update_data['hashed_password'] = bcrypt_context.hash(update_data.pop('password'))
    
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete('/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: db_dependency, user: user_dependency):
    check_admin(user)
    
    db_user = db.query(Users).filter(Users.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Prevent deleting yourself
    if db_user.id == user.get('id'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    db.delete(db_user)
    db.commit()
    return None

@router.post('/users', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_create: UserCreate, db: db_dependency, user: user_dependency):
    check_admin(user)
    
    # Check if email or username already exists
    existing_email = db.query(Users).filter(Users.email == user_create.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = db.query(Users).filter(Users.username == user_create.username).first()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    user_data = user_create.dict()
    hashed_password = bcrypt_context.hash(user_data.pop('password'))
    
    db_user = Users(
        **user_data,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get('/debug/current-user', status_code=status.HTTP_200_OK)
def get_current_user_info(user: user_dependency):
    """Debug endpoint to show the current user's information."""
    return user