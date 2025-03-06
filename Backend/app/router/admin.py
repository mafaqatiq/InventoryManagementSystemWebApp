from typing import Annotated
from fastapi import Path, APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from database import SessionLocal
from models import Todos, Users
import starlette.status as status 
from .auth import get_current_user

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

# Dependency Injection -(Part which runs behind the scenes before performing requested task [Depends(get_db)], to call db first)-
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency =  Annotated[dict, Depends(get_current_user)]


@router.get('/todo', status_code=status.HTTP_200_OK)
def read_all(user: user_dependency, db: db_dependency):
    if user is None or user.get('user_role')!= 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    return db.query(Todos).all()

@router.delete('/todo/{todoId}', status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(user: user_dependency, db: db_dependency, todoId: int):
    if user is None or user.get('user_role')!= 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    todo_model = db.query(Todos).filter(Todos.id == todoId).first()
    if todo_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No Todo Found with ID: {todoId}")
    db.delete(todo_model)
    db.commit()



@router.get('/users', status_code=status.HTTP_200_OK)
def get_all_users(db: db_dependency, user: user_dependency):
    if user is None or user.get('user_role')!= 'admin':
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Authentication Failed')
    return  db.query(Users).all()