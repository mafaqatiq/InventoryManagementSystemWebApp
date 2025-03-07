from typing import Annotated
from fastapi import Path, APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException
from app.database import SessionLocal
from app.models import Todos
import starlette.status as status 
from .auth import get_current_user

router = APIRouter(
    prefix='/todos',
    tags=['todos']
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


# For Post Request, remember we need to use pydantics, so lets create class (Don't add id, its handled by sqlalchemy, )
class TodoRequest(BaseModel):
    title: str= Field(min_lenght=3)
    description: str = Field(min_lenght=3, max_length=100)
    priority: int= Field(gt=0, lt=6)
    complete: bool

@router.get('/', status_code=status.HTTP_200_OK)
def all_todos(user:user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication Failed")
    return db.query(Todos).filter(Todos.owner_id == user.get('id')).all()
    

@router.get('/todos/{todoId}', status_code=status.HTTP_200_OK)
def get_todo_by_todoId(user: user_dependency, db: db_dependency, todoId: int = Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication Failed")
    todo_result = db.query(Todos).filter(Todos.id == todoId).filter(Todos.owner_id == user.get('id')).first()
    if todo_result is not None:
        return todo_result
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No Todo Found with ID: {todoId}")

@router.post('/todos/create-todo', status_code=status.HTTP_201_CREATED)
def create_todo(user: user_dependency, db: db_dependency, todo_request: TodoRequest):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication Failed")
        
    todo_model = Todos(**todo_request.model_dump(), owner_id=user.get('id'))
    db.add(todo_model)
    db.commit()
    return todo_model

@router.put('/todo/update-todo/{todoId}', status_code=status.HTTP_200_OK)
def update_todo_by_id(user: user_dependency, db:db_dependency,  todo_request: TodoRequest , todoId: int= Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication Failed")
    todo_model = db.query(Todos).filter(Todos.id == todoId).filter(Todos.owner_id == user.get('id')).first()
    if todo_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found this todo")
    todo_model.title = todo_request.title
    todo_model.description = todo_request.description
    todo_model.priority = todo_request.priority
    todo_model.complete = todo_request.complete
    db.commit()
    return todo_model


@router.delete('/todos/delete-todo/{todoId}', status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(user: user_dependency, db: db_dependency, todoId: int = Path(gt=0)):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication Failed")
    todo_model = db.query(Todos).filter(Todos.id == todoId).filter(Todos.owner_id == user.get('id')).first()
    if todo_model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="todo Not found")
    db.delete(todo_model)
    db.commit()
    return {"detail": "Todo deleted successfully"}

