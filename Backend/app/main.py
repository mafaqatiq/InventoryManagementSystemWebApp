from fastapi import FastAPI
from app.database import engine, Base
import app.models
from app.routes import router  # ✅ Correct import

app = FastAPI()

# Create database tables
Base.metadata.create_all(bind=engine)

# Include API routes
app.include_router(router)  # ✅ Corrected usage

@app.get("/")
def read_root():
    return {"message": "Very Warm Welcome to Inventory Management System!"}
