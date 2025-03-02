from sqlalchemy.orm import Session
from app.models import InventoryItem

def get_items(db: Session):
    return db.query(InventoryItem).all()

def add_item(db: Session, name: str, quantity: int):
    item = InventoryItem(name=name, quantity=quantity)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
