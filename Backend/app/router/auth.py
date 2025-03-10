from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Path, APIRouter, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.database import SessionLocal
from app.models import Users
import starlette.status as status 
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer    
from jose import jwt, JWTError 

router = APIRouter(
    prefix= '/auth', 
    tags=['Authentication']
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# Security configuration
SECRET_KEY = 'your-secret-key'
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
Oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

#######################
# Pydantic Models
#######################

class UserRegistration(BaseModel):
    email: str
    username: str
    first_name: str
    last_name: str
    password: str
    role: str
    phone_number: str

class Token(BaseModel):
    access_token: str
    token_type: str

#######################
# Helper Functions
#######################

def authenticate_user(username: str, password: str, db):
    """Verify user credentials"""
    user_model = db.query(Users).filter(Users.username == username).first()
    if not user_model:
        return False
    
    if not bcrypt_context.verify(password, user_model.hashed_password):
        return False
    
    return user_model

def create_access_token(username: str, user_id: int, role: str, expires_delta: timedelta):
    """Generate a JWT token for authenticated users"""
    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: Annotated[str, Depends(Oauth2_bearer)]):
    """Decode and validate JWT token to get current user"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        user_role: str = payload.get('role')
        
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user')
        
        return {'username': username, 'id': user_id, 'user_role': user_role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate user')

#######################
# Authentication Endpoints
#######################

@router.post('/register', status_code=status.HTTP_201_CREATED)
def register_user(db: db_dependency, user: UserRegistration):
    """Register a new user"""
    # Check if username or email already exists
    existing_user = db.query(Users).filter(
        (Users.username == user.username) | (Users.email == user.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    user_model = Users(
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        phone_number=user.phone_number,
        hashed_password=bcrypt_context.hash(user.password),
        is_active=True
    )
    
    db.add(user_model)
    db.commit()
    
    return {"message": "User created successfully"}

@router.post('/token', response_model=Token)
def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: db_dependency
):
    """Authenticate user and provide access token"""
    # Authenticate user
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Generate token
    token = create_access_token(
        username=user.username,
        user_id=user.id,
        role=user.role,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    
    return Token(access_token=token, token_type="bearer")

@router.post('/logout')
def logout(response: Response):
    """Log out user by clearing the token cookie"""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}