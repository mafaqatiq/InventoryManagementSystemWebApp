from fastapi import FastAPI, Request
from app.database import engine, Base
from app import models
from app.router import auth, admin, todos, users   

app = FastAPI()



@app.get('/')
def home(request: Request):
    return {"message": "Hello World"}

models.Base.metadata.create_all(bind=engine)   # create a db from models.py and database.py to create todos.db

app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(admin.router)
app.include_router(users.router)
