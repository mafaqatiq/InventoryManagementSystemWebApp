from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from app.database import SessionLocal
from app.models import Order, OrderItem, CartItem, Product, Stock, StockChangeType, OrderStatus, PaymentMethod
import starlette.status as status
from app.router.auth import get_current_user

# Define routers with clear prefixes and tags
router = APIRouter(
    prefix='/orders',
    tags=['orders']
)

admin_router = APIRouter(
    prefix='/admin/orders',
    tags=['admin-orders']
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
# Helper Functions
#######################

def check_admin(user):
    """Verify that the user has admin privileges"""
    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

#######################
# Pydantic Models
#######################

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    price_at_time: float
    subtotal: float
    
    class Config:
        orm_mode = True

class OrderResponse(BaseModel):
    id: int
    status: OrderStatus
    total_amount: float
    shipping_address: str
    payment_method: PaymentMethod
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    
    class Config:
        orm_mode = True

class OrderCreate(BaseModel):
    shipping_address: str
    payment_method: PaymentMethod

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

#######################
# Customer Order Endpoints
#######################

@router.post('/', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    user: user_dependency,
    db: db_dependency,
    order_data: OrderCreate
):
    """Create a new order from the user's cart items"""
    # Get user's cart items
    cart_items = db.query(CartItem).filter(CartItem.user_id == user['id']).all()
    
    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create order with empty cart"
        )
    
    # Calculate total amount and check stock
    total_amount = 0
    order_items_data = []
    
    for cart_item in cart_items:
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
        
        # Check if enough stock is available
        if product.stock_left < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough stock for product '{product.name}'. Available: {product.stock_left}, Requested: {cart_item.quantity}"
            )
        
        # Calculate subtotal for this item
        subtotal = product.price * cart_item.quantity
        total_amount += subtotal
        
        # Prepare order item data
        order_items_data.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": cart_item.quantity,
            "price_at_time": product.price,
            "subtotal": subtotal
        })
    
    # Create order
    new_order = Order(
        user_id=user['id'],
        status=OrderStatus.PENDING,
        total_amount=total_amount,
        shipping_address=order_data.shipping_address,
        payment_method=order_data.payment_method
    )
    
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    
    # Create order items
    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=new_order.id,
            **item_data
        )
        db.add(order_item)
        
        # Update product stock
        product_id = item_data["product_id"]
        quantity = item_data["quantity"]
        
        # Record stock movement
        stock_movement = Stock(
            product_id=product_id,
            change_type=StockChangeType.SALE,
            quantity=quantity
        )
        db.add(stock_movement)
        
        # Update product sales count
        product = db.query(Product).filter(Product.id == product_id).first()
        product.how_much_sold += quantity
        
        # Check if product is now out of stock
        if product.stock_left - quantity <= 0:
            product.in_stock = False
    
    db.commit()
    
    # Clear the user's cart
    for cart_item in cart_items:
        db.delete(cart_item)
    
    db.commit()
    
    # Refresh order to include items
    db.refresh(new_order)
    return new_order

@router.get('/', response_model=List[OrderResponse])
def get_user_orders(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 10
):
    """Get all orders for the current user with pagination"""
    orders = db.query(Order).filter(
        Order.user_id == user['id']
    ).order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@router.get('/{order_id}', response_model=OrderResponse)
def get_order(
    order_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Get a specific order by ID for the current user"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user['id']
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    
    # Ensure order items are loaded
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return order

#######################
# Admin Order Endpoints
#######################

@admin_router.get('/', response_model=List[OrderResponse])
def get_all_orders(
    user: user_dependency,
    db: db_dependency,
    status: Optional[OrderStatus] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 10
):
    """Get all orders with filtering options (admin only)"""
    check_admin(user)
    
    query = db.query(Order)
    
    # Apply filters
    if status:
        query = query.filter(Order.status == status)
    
    if from_date:
        query = query.filter(Order.created_at >= from_date)
    
    if to_date:
        query = query.filter(Order.created_at <= to_date)
    
    # Apply pagination
    orders = query.order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@admin_router.get('/recent', response_model=List[OrderResponse])
def get_recent_orders(
    user: user_dependency,
    db: db_dependency
):
    """Get orders from the last week (admin only)"""
    check_admin(user)
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    orders = db.query(Order).filter(
        Order.created_at >= one_week_ago
    ).order_by(desc(Order.created_at)).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@admin_router.get('/monthly', response_model=List[OrderResponse])
def get_monthly_orders(
    user: user_dependency,
    db: db_dependency
):
    """Get orders from the last month (admin only)"""
    check_admin(user)
    
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    orders = db.query(Order).filter(
        Order.created_at >= one_month_ago
    ).order_by(desc(Order.created_at)).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@admin_router.get('/{order_id}', response_model=OrderResponse)
def admin_get_order(
    order_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Get a specific order by ID (admin only)"""
    check_admin(user)
    
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    
    # Ensure order items are loaded
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return order

@admin_router.put('/{order_id}/status', response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    user: user_dependency,
    db: db_dependency
):
    """Update the status of an order (admin only)"""
    check_admin(user)
    
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    
    # Update status
    order.status = status_update.status
    order.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    # Ensure order items are loaded
    order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return order

#######################
# Admin Dashboard Endpoints
#######################

@admin_router.get('/dashboard/summary', status_code=status.HTTP_200_OK)
def get_orders_summary(
    user: user_dependency,
    db: db_dependency
):
    """Get summary statistics about orders for admin dashboard (admin only)"""
    check_admin(user)
    
    # Total orders
    total_orders = db.query(func.count(Order.id)).scalar()
    
    # Orders by status
    orders_by_status = db.query(
        Order.status, 
        func.count(Order.id)
    ).group_by(
        Order.status
    ).all()
    
    # Format orders by status
    status_data = [
        {"status": status.value, "count": count}
        for status, count in orders_by_status
    ]
    
    # Total revenue
    total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
    
    # Recent orders (last 7 days)
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    recent_orders_count = db.query(func.count(Order.id)).filter(
        Order.created_at >= one_week_ago
    ).scalar()
    
    # Recent revenue (last 7 days)
    recent_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= one_week_ago
    ).scalar() or 0
    
    # Monthly orders (last 30 days)
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    monthly_orders_count = db.query(func.count(Order.id)).filter(
        Order.created_at >= one_month_ago
    ).scalar()
    
    # Monthly revenue (last 30 days)
    monthly_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= one_month_ago
    ).scalar() or 0
    
    # Latest orders (top 5)
    latest_orders = db.query(Order).order_by(
        desc(Order.created_at)
    ).limit(5).all()
    
    latest_orders_data = [
        {
            "id": order.id,
            "status": order.status.value,
            "total_amount": order.total_amount,
            "created_at": order.created_at
        }
        for order in latest_orders
    ]
    
    return {
        "total_orders": total_orders,
        "orders_by_status": status_data,
        "total_revenue": total_revenue,
        "recent_orders_count": recent_orders_count,
        "recent_revenue": recent_revenue,
        "monthly_orders_count": monthly_orders_count,
        "monthly_revenue": monthly_revenue,
        "latest_orders": latest_orders_data
    }

@admin_router.get('/dashboard/all', response_model=List[OrderResponse])
def get_all_orders_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 100
):
    """Get all orders for admin dashboard (admin only)"""
    check_admin(user)
    
    orders = db.query(Order).order_by(
        desc(Order.created_at)
    ).offset(skip).limit(limit).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@admin_router.get('/dashboard/by-status/{status}', response_model=List[OrderResponse])
def get_orders_by_status_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    status: OrderStatus,
    skip: int = 0,
    limit: int = 100
):
    """Get orders filtered by status for admin dashboard (admin only)"""
    check_admin(user)
    
    orders = db.query(Order).filter(
        Order.status == status
    ).order_by(
        desc(Order.created_at)
    ).offset(skip).limit(limit).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders

@admin_router.get('/dashboard/recent', response_model=List[OrderResponse])
def get_recent_orders_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    days: int = 3,
    limit: int = 10
):
    """Get recent orders for admin dashboard (admin only)"""
    check_admin(user)
    
    recent_date = datetime.utcnow() - timedelta(days=days)
    orders = db.query(Order).filter(
        Order.created_at >= recent_date
    ).order_by(
        desc(Order.created_at)
    ).limit(limit).all()
    
    # Ensure order items are loaded
    for order in orders:
        order.items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    
    return orders 