from fastapi import FastAPI, Request
from app.database import engine, Base
from app import models
from app.router import auth, admin, users, products

# Create database tables before initializing the app
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="E-commerce API",
    description="API for E-commerce Dashboard and Customer App",
    version="1.0.0"
)

@app.get('/')
def home(request: Request):
    return {"message": "Welcome to the E-commerce API"}

 

# Include routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(products.admin_router)
app.include_router(products.stock_router)