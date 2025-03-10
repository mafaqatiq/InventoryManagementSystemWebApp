from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime
from pydantic import BaseModel, Field
from app.database import SessionLocal
from app.models import CartItem, Product, Users
import starlette.status as status
from app.router.auth import get_current_user

router = APIRouter(
    prefix='/cart',
    tags=['cart']
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

#######################
# Pydantic Models
#######################

class CartItemCreate(BaseModel):
    product_id: int
    quantity: int = 1

class CartItemUpdate(BaseModel):
    quantity: int

class CartItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    product_name: str
    product_price: float
    product_image: Optional[str] = None
    subtotal: float
    
    class Config:
        orm_mode = True

class CartSummaryResponse(BaseModel):
    items: List[CartItemResponse]
    total_items: int
    total_amount: float

#######################
# Cart Endpoints
#######################

@router.post('/', response_model=CartItemResponse, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    user: user_dependency,
    db: db_dependency,
    cart_item: CartItemCreate
):
    """Add a product to the user's cart"""
    # Check if product exists
    product = db.query(Product).filter(Product.id == cart_item.product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {cart_item.product_id} not found"
        )
    
    # Check if product is in stock
    if not product.in_stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.name}' is out of stock"
        )
    
    # Check if there's enough stock
    if product.stock_left < cart_item.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough stock for product '{product.name}'. Available: {product.stock_left}, Requested: {cart_item.quantity}"
        )
    
    # Check if product is already in cart
    existing_item = db.query(CartItem).filter(
        CartItem.user_id == user['id'],
        CartItem.product_id == cart_item.product_id
    ).first()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item.quantity + cart_item.quantity
        
        # Check if new quantity exceeds available stock
        if new_quantity > product.stock_left:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add {cart_item.quantity} more units of '{product.name}'. Total would exceed available stock of {product.stock_left}"
            )
        
        existing_item.quantity = new_quantity
        db.commit()
        db.refresh(existing_item)
        
        # Get primary image if available
        primary_image = None
        if product.images:
            for image in product.images:
                if image.is_primary:
                    primary_image = image.image_url
                    break
            if primary_image is None and product.images:
                primary_image = product.images[0].image_url
        
        return CartItemResponse(
            id=existing_item.id,
            product_id=product.id,
            quantity=existing_item.quantity,
            product_name=product.name,
            product_price=product.price,
            product_image=primary_image,
            subtotal=product.price * existing_item.quantity
        )
    else:
        # Create new cart item
        db_cart_item = CartItem(
            user_id=user['id'],
            product_id=cart_item.product_id,
            quantity=cart_item.quantity
        )
        
        db.add(db_cart_item)
        db.commit()
        db.refresh(db_cart_item)
        
        # Get primary image if available
        primary_image = None
        if product.images:
            for image in product.images:
                if image.is_primary:
                    primary_image = image.image_url
                    break
            if primary_image is None and product.images:
                primary_image = product.images[0].image_url
        
        return CartItemResponse(
            id=db_cart_item.id,
            product_id=product.id,
            quantity=db_cart_item.quantity,
            product_name=product.name,
            product_price=product.price,
            product_image=primary_image,
            subtotal=product.price * db_cart_item.quantity
        )

@router.get('/', response_model=CartSummaryResponse)
def get_cart(
    user: user_dependency,
    db: db_dependency
):
    """Get the current user's cart with all items"""
    # Get all cart items for the user
    cart_items = db.query(CartItem).filter(CartItem.user_id == user['id']).all()
    
    # Prepare response
    response_items = []
    total_amount = 0
    total_items = 0
    
    for cart_item in cart_items:
        # Get product
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        
        if not product:
            # Skip if product no longer exists
            continue
        
        # Get primary image if available
        primary_image = None
        if product.images:
            for image in product.images:
                if image.is_primary:
                    primary_image = image.image_url
                    break
            if primary_image is None and product.images:
                primary_image = product.images[0].image_url
        
        # Calculate subtotal
        subtotal = product.price * cart_item.quantity
        total_amount += subtotal
        total_items += cart_item.quantity
        
        response_items.append(CartItemResponse(
            id=cart_item.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            product_name=product.name,
            product_price=product.price,
            product_image=primary_image,
            subtotal=subtotal
        ))
    
    return CartSummaryResponse(
        items=response_items,
        total_items=total_items,
        total_amount=total_amount
    )

@router.put('/{item_id}', response_model=CartItemResponse)
def update_cart_item(
    item_id: int,
    update: CartItemUpdate,
    user: user_dependency,
    db: db_dependency
):
    """Update the quantity of an item in the cart"""
    # Get cart item
    cart_item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.user_id == user['id']
    ).first()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item with id {item_id} not found"
        )
    
    # Get product
    product = db.query(Product).filter(Product.id == cart_item.product_id).first()
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {cart_item.product_id} not found"
        )
    
    # Check if product is in stock
    if not product.in_stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.name}' is out of stock"
        )
    
    # Check if there's enough stock
    if product.stock_left < update.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not enough stock for product '{product.name}'. Available: {product.stock_left}, Requested: {update.quantity}"
        )
    
    # Update quantity
    cart_item.quantity = update.quantity
    db.commit()
    db.refresh(cart_item)
    
    # Get primary image if available
    primary_image = None
    if product.images:
        for image in product.images:
            if image.is_primary:
                primary_image = image.image_url
                break
        if primary_image is None and product.images:
            primary_image = product.images[0].image_url
    
    return CartItemResponse(
        id=cart_item.id,
        product_id=product.id,
        quantity=cart_item.quantity,
        product_name=product.name,
        product_price=product.price,
        product_image=primary_image,
        subtotal=product.price * cart_item.quantity
    )

@router.delete('/{item_id}', status_code=status.HTTP_204_NO_CONTENT)
def remove_from_cart(
    item_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Remove an item from the cart"""
    # Get cart item
    cart_item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.user_id == user['id']
    ).first()
    
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item with id {item_id} not found"
        )
    
    # Delete cart item
    db.delete(cart_item)
    db.commit()
    
    return None

@router.delete('/', status_code=status.HTTP_204_NO_CONTENT)
def clear_cart(
    user: user_dependency,
    db: db_dependency
):
    """Remove all items from the cart"""
    # Delete all cart items for the user
    db.query(CartItem).filter(CartItem.user_id == user['id']).delete()
    db.commit()
    
    return None 