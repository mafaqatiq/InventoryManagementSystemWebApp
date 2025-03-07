from typing import Annotated
from fastapi import Path, APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.database import SessionLocal
from app.models import Todos, Users
import starlette.status as status 
from .auth import get_current_user
from passlib.context import CryptContext

router = APIRouter(
    prefix= '/users',
    tags=['users']
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency Injection -(Part which runs behind the scenes before performing requested task [Depends(get_db)], to call db first)-
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency =  Annotated[dict, Depends(get_current_user)]
bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


class UserVerificaiton(BaseModel):
    password: str
    new_password: str = Field(min_length=6)


@router.get('/', status_code=status.HTTP_200_OK)
def get_user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    return db.query(Users).filter(Users.id == user.get('id')).first()

@router.put('/password', status_code=status.HTTP_204_NO_CONTENT)
def change_password(user: user_dependency, db: db_dependency, user_verification: UserVerificaiton):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if not bcrypt_context.verify(user_verification.password, user_model.hashed_password):
        raise HTTPException(status_code=401, detail="Error on Password Change")
    user_model.hashed_password = bcrypt_context.hash(user_verification.new_password)
    db.add(user_model)
    db.commit()

@router.put('/phone-number/{phone_number}', status_code=status.HTTP_204_NO_CONTENT)
def change_phone_number(db: db_dependency, user: user_dependency, phone_number: str ):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication Failed")
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    user_model.phone_number = phone_number
    db.commit()
