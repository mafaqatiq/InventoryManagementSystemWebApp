from fastapi import FastAPI, Request
from app.database import engine, Base
from app import models
from app.router import auth, admin, todos, users   

# Create database tables before initializing the app
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get('/')
def home(request: Request):
    return {"message": "Hello World"}

# Include routers
app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(admin.router)
app.include_router(users.router)