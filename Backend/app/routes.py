from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import crud  # ✅ Fixed import

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/items")
def read_items(db: Session = Depends(get_db)):
    return crud.get_items(db)  # ✅ Fixed

@router.post("/items")
def create_item(name: str, quantity: int, db: Session = Depends(get_db)):
    return crud.add_item(db, name, quantity)  # ✅ Fixed
