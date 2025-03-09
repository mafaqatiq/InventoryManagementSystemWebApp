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

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
 
 


class RequestUsers(BaseModel):
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

# AUTHENTICATION
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def authenticate_user(username: str, password: str, db):
    user_model = db.query(Users).filter(Users.username == username).first()
    if not user_model:
        return False
    if not bcrypt_context.verify(password, user_model.hashed_password):
        return False
    return user_model


# Authorization
SECRET_KEY = 'e971251b73bfb51ad154684ce30e215fe1d60de5f993c7eff1f5468b3aa99c1e'
ALGORITHM = 'HS256'
Oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

# AUTHORIZATION (Creating jwt token and also encoding it)
def create_access_token(username: str, user_id: int, role:str,  expires_delta: timedelta):
    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: Annotated[str, Depends(Oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        user_role: str = payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate the user' )
        return {'username': username, 'id': user_id, 'user_role': user_role}
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate the user' )

 


@router.post('/', status_code=status.HTTP_201_CREATED)
def create_user(db: db_dependency, request_users: RequestUsers):

    users_model = Users(
        email=request_users.email,
        username=request_users.username,
        first_name=request_users.first_name,
        last_name=request_users.last_name,
        hashed_password= bcrypt_context.hash(request_users.password),
        role=request_users.role,
        is_active = True,
        phone_number = request_users.phone_number
    )

    if not users_model:
        raise HTTPException(status_code=404, detail="Erro occur on db side")
    db.add(users_model)
    db.commit()
    return users_model


@router.post('/token', response_model=Token)
def login_for_access_token(
    response: Response,  # Add this parameter
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], 
    db: db_dependency
):
    user_model = authenticate_user(form_data.username, form_data.password, db)
    if not user_model:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate the user')
    token = create_access_token(user_model.username, user_model.id, user_model.role, timedelta(minutes=20))
    
    # Set the JWT token in a cookie
    response.set_cookie(
        key="access_token",  # Cookie name
        value=f"Bearer {token}",  # Cookie value (JWT token)
        max_age=1200,  # Cookie expiration time in seconds (20 minutes)
        httponly=True,  # Prevent client-side JavaScript from accessing the cookie
        secure=True,  # Ensure the cookie is only sent over HTTPS
        samesite="lax"  # Prevent CSRF attacks
    )
    
    return {"access_token": token, "token_type": "bearer"}



@router.post('/logout')
def logout(response: Response):
    # Delete the JWT token cookie
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}