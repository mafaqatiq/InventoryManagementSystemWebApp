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

#######################
# Pydantic Models
#######################

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

#######################
# Helper Functions
#######################

def check_admin(user):
    """Verify that the user has admin privileges"""
    if not user or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

#######################
# Admin User Management Endpoints
#######################

@router.get('/users', response_model=List[UserResponse], status_code=status.HTTP_200_OK)
def get_all_users(db: db_dependency, user: user_dependency):
    """Get all users (admin only)"""
    check_admin(user)
    return db.query(Users).all()

@router.get('/users/{user_id}', response_model=UserResponse, status_code=status.HTTP_200_OK)
def get_user(user_id: int, db: db_dependency, user: user_dependency):
    """Get a specific user by ID (admin only)"""
    check_admin(user)
    
    user_model = db.query(Users).filter(Users.id == user_id).first()
    if not user_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    
    return user_model

@router.put('/users/{user_id}', response_model=UserResponse, status_code=status.HTTP_200_OK)
def update_user(user_id: int, user_update: UserUpdate, db: db_dependency, user: user_dependency):
    """Update a user's information (admin only)"""
    check_admin(user)
    
    user_model = db.query(Users).filter(Users.id == user_id).first()
    if not user_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    
    # Update only provided fields
    update_data = user_update.dict(exclude_unset=True)
    
    # Hash password if provided
    if 'password' in update_data:
        update_data['hashed_password'] = bcrypt_context.hash(update_data['password'])
        del update_data['password']
    
    for key, value in update_data.items():
        setattr(user_model, key, value)
    
    db.commit()
    db.refresh(user_model)
    return user_model

@router.delete('/users/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: db_dependency, user: user_dependency):
    """Delete a user (admin only)"""
    check_admin(user)
    
    # Prevent admin from deleting themselves
    if user_id == user.get('id'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user_model = db.query(Users).filter(Users.id == user_id).first()
    if not user_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    
    db.delete(user_model)
    db.commit()
    return None

@router.post('/users', response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_create: UserCreate, db: db_dependency, user: user_dependency):
    """Create a new user (admin only)"""
    check_admin(user)
    
    # Check if username or email already exists
    existing_user = db.query(Users).filter(
        (Users.username == user_create.username) | (Users.email == user_create.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    user_model = Users(
        email=user_create.email,
        username=user_create.username,
        first_name=user_create.first_name,
        last_name=user_create.last_name,
        role=user_create.role,
        phone_number=user_create.phone_number,
        hashed_password=bcrypt_context.hash(user_create.password),
        is_active=user_create.is_active
    )
    
    db.add(user_model)
    db.commit()
    db.refresh(user_model)
    return user_model

#######################
# Admin Debug Endpoints
#######################

@router.get('/debug/current-user', status_code=status.HTTP_200_OK)
def get_current_user_info(user: user_dependency):
    """Get information about the currently authenticated user (admin only)"""
    check_admin(user)
    return user