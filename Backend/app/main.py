from fastapi import FastAPI, Request
from app.database import engine, Base
from app import models
from app.router import auth, admin, users, products, cart, orders

# Create database tables before initializing the app
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Inventory Management System API",
    description="API for Inventory Management System Dashboard and Customer App",
    version="1.0.0"
)

@app.get('/')
def home(request: Request):
    return {
        "message": "Welcome to the Inventory Management System API",
        "documentation": "/docs",
        "redoc": "/redoc"
    }

# Include authentication routers
app.include_router(auth.router)

# Include user routers
app.include_router(users.router)
app.include_router(admin.router)

# Include product routers
app.include_router(products.router)
app.include_router(products.admin_router)
app.include_router(products.stock_router)

# Include cart and order routers
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(orders.admin_router)