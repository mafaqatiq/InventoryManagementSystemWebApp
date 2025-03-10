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

# Helper function to check admin role
def check_admin(user):
    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

# Pydantic models
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

# Customer order endpoints
@router.post('/', response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    user: user_dependency,
    db: db_dependency,
    order_data: OrderCreate
):
    """Create a new order from the user's cart"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Get all cart items for the user
    cart_items = db.query(CartItem).filter(CartItem.user_id == user.get('id')).all()
    
    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your cart is empty"
        )
    
    # Calculate total amount and validate stock
    total_amount = 0
    order_items_data = []
    
    for cart_item in cart_items:
        product = db.query(Product).filter(Product.id == cart_item.product_id).first()
        
        # Skip if product no longer exists
        if not product:
            continue
        
        # Check if product is in stock
        if not product.in_stock or product.stock_left < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough stock for {product.name}. Available: {product.stock_left}"
            )
        
        # Calculate subtotal
        subtotal = product.price * cart_item.quantity
        total_amount += subtotal
        
        # Prepare order item data
        order_items_data.append({
            "product_id": product.id,
            "quantity": cart_item.quantity,
            "price_at_time": product.price,
            "product": product
        })
    
    # Create order
    db_order = Order(
        user_id=user.get('id'),
        status=OrderStatus.PENDING,
        total_amount=total_amount,
        shipping_address=order_data.shipping_address,
        payment_method=order_data.payment_method
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Create order items and update stock
    for item_data in order_items_data:
        # Create order item
        order_item = OrderItem(
            order_id=db_order.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            price_at_time=item_data["price_at_time"]
        )
        db.add(order_item)
        
        # Update product stock
        product = item_data["product"]
        
        # Create stock movement (sale)
        stock_movement = Stock(
            product_id=product.id,
            change_type=StockChangeType.SALE,
            quantity=item_data["quantity"]
        )
        db.add(stock_movement)
        
        # Update product sales count
        product.how_much_sold += item_data["quantity"]
        
        # Update in_stock status based on remaining stock
        current_stock = product.stock_left - item_data["quantity"]
        product.in_stock = current_stock > 0
    
    # Clear the user's cart
    db.query(CartItem).filter(CartItem.user_id == user.get('id')).delete()
    
    db.commit()
    
    # Fetch the complete order with items for response
    db_order = db.query(Order).filter(Order.id == db_order.id).first()
    
    # Prepare response
    order_items = []
    for item in db_order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown Product"
        
        order_items.append(OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product_name,
            quantity=item.quantity,
            price_at_time=item.price_at_time,
            subtotal=item.price_at_time * item.quantity
        ))
    
    return OrderResponse(
        id=db_order.id,
        status=db_order.status,
        total_amount=db_order.total_amount,
        shipping_address=db_order.shipping_address,
        payment_method=db_order.payment_method,
        created_at=db_order.created_at,
        updated_at=db_order.updated_at,
        items=order_items
    )

@router.get('/', response_model=List[OrderResponse])
def get_user_orders(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 10
):
    """Get all orders for the current user"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Get all orders for the user
    orders = db.query(Order).filter(
        Order.user_id == user.get('id')
    ).order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@router.get('/{order_id}', response_model=OrderResponse)
def get_order(
    order_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Get a specific order by ID"""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Get the order
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == user.get('id')
    ).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    
    # Prepare response
    order_items = []
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown Product"
        
        order_items.append(OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product_name,
            quantity=item.quantity,
            price_at_time=item.price_at_time,
            subtotal=item.price_at_time * item.quantity
        ))
    
    return OrderResponse(
        id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        shipping_address=order.shipping_address,
        payment_method=order.payment_method,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=order_items
    )

# Admin order endpoints
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
    """Get all orders with optional filtering"""
    check_admin(user)
    
    # Build query with filters
    query = db.query(Order)
    
    if status:
        query = query.filter(Order.status == status)
    
    if from_date:
        query = query.filter(Order.created_at >= from_date)
    
    if to_date:
        query = query.filter(Order.created_at <= to_date)
    
    # Get orders with pagination
    orders = query.order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@admin_router.get('/last-week', response_model=List[OrderResponse])
def get_last_week_orders(
    user: user_dependency,
    db: db_dependency
):
    """Get orders from the last 7 days"""
    check_admin(user)
    
    # Calculate date 7 days ago
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    
    # Get orders from the last week
    orders = db.query(Order).filter(
        Order.created_at >= one_week_ago
    ).order_by(desc(Order.created_at)).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@admin_router.get('/last-month', response_model=List[OrderResponse])
def get_last_month_orders(
    user: user_dependency,
    db: db_dependency
):
    """Get orders from the last 30 days"""
    check_admin(user)
    
    # Calculate date 30 days ago
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    
    # Get orders from the last month
    orders = db.query(Order).filter(
        Order.created_at >= one_month_ago
    ).order_by(desc(Order.created_at)).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@admin_router.get('/{order_id}', response_model=OrderResponse)
def admin_get_order(
    order_id: int,
    user: user_dependency,
    db: db_dependency
):
    """Get a specific order by ID (admin access)"""
    check_admin(user)
    
    # Get the order
    order = db.query(Order).filter(Order.id == order_id).first()
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found"
        )
    
    # Prepare response
    order_items = []
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown Product"
        
        order_items.append(OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product_name,
            quantity=item.quantity,
            price_at_time=item.price_at_time,
            subtotal=item.price_at_time * item.quantity
        ))
    
    return OrderResponse(
        id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        shipping_address=order.shipping_address,
        payment_method=order.payment_method,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=order_items
    )

@admin_router.put('/{order_id}/status', response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    user: user_dependency,
    db: db_dependency
):
    """Update the status of an order"""
    check_admin(user)
    
    # Get the order
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
    
    # Prepare response
    order_items = []
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        product_name = product.name if product else "Unknown Product"
        
        order_items.append(OrderItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=product_name,
            quantity=item.quantity,
            price_at_time=item.price_at_time,
            subtotal=item.price_at_time * item.quantity
        ))
    
    return OrderResponse(
        id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        shipping_address=order.shipping_address,
        payment_method=order.payment_method,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=order_items
    )

@admin_router.get('/dashboard/summary', status_code=status.HTTP_200_OK)
def get_orders_summary(
    user: user_dependency,
    db: db_dependency
):
    """Get summary statistics for orders"""
    check_admin(user)
    
    # Calculate dates
    now = datetime.utcnow()
    one_day_ago = now - timedelta(days=1)
    one_week_ago = now - timedelta(days=7)
    one_month_ago = now - timedelta(days=30)
    
    # Get counts
    total_orders = db.query(func.count(Order.id)).scalar()
    
    today_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= one_day_ago
    ).scalar()
    
    week_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= one_week_ago
    ).scalar()
    
    month_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= one_month_ago
    ).scalar()
    
    # Get revenue
    total_revenue = db.query(func.sum(Order.total_amount)).scalar() or 0
    
    today_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= one_day_ago
    ).scalar() or 0
    
    week_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= one_week_ago
    ).scalar() or 0
    
    month_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= one_month_ago
    ).scalar() or 0
    
    # Get status counts
    pending_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.PENDING
    ).scalar()
    
    processing_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.PROCESSING
    ).scalar()
    
    shipped_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.SHIPPED
    ).scalar()
    
    delivered_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.DELIVERED
    ).scalar()
    
    cancelled_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.CANCELLED
    ).scalar()
    
    return {
        "orders": {
            "total": total_orders,
            "today": today_orders,
            "week": week_orders,
            "month": month_orders
        },
        "revenue": {
            "total": float(total_revenue),
            "today": float(today_revenue),
            "week": float(week_revenue),
            "month": float(month_revenue)
        },
        "status": {
            "pending": pending_orders,
            "processing": processing_orders,
            "shipped": shipped_orders,
            "delivered": delivered_orders,
            "cancelled": cancelled_orders
        }
    }

@admin_router.get('/dashboard/all', response_model=List[OrderResponse])
def get_all_orders_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 100
):
    """Get all orders without filtering for admin dashboard"""
    check_admin(user)
    
    # Get all orders with pagination
    orders = db.query(Order).order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@admin_router.get('/dashboard/by-status/{status}', response_model=List[OrderResponse])
def get_orders_by_status_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    status: OrderStatus,
    skip: int = 0,
    limit: int = 100
):
    """Get orders filtered by status for admin dashboard"""
    check_admin(user)
    
    # Get orders with the specified status
    orders = db.query(Order).filter(
        Order.status == status
    ).order_by(desc(Order.created_at)).offset(skip).limit(limit).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response

@admin_router.get('/dashboard/recent', response_model=List[OrderResponse])
def get_recent_orders_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    days: int = 3,
    limit: int = 10
):
    """Get recent orders for admin dashboard"""
    check_admin(user)
    
    # Calculate date for recent orders
    recent_date = datetime.utcnow() - timedelta(days=days)
    
    # Get recent orders
    orders = db.query(Order).filter(
        Order.created_at >= recent_date
    ).order_by(desc(Order.created_at)).limit(limit).all()
    
    # Prepare response
    response = []
    for order in orders:
        order_items = []
        for item in order.items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            product_name = product.name if product else "Unknown Product"
            
            order_items.append(OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=product_name,
                quantity=item.quantity,
                price_at_time=item.price_at_time,
                subtotal=item.price_at_time * item.quantity
            ))
        
        response.append(OrderResponse(
            id=order.id,
            status=order.status,
            total_amount=order.total_amount,
            shipping_address=order.shipping_address,
            payment_method=order.payment_method,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=order_items
        ))
    
    return response 