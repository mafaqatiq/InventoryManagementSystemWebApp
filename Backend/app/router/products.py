from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import enum
from app.database import SessionLocal
from app.models import Product, Category, ProductImage, Stock, Review, Users, Gender, Size, StockChangeType
import starlette.status as status
from app.router.auth import get_current_user
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix='/products',
    tags=['products']
)

admin_router = APIRouter(
    prefix='/admin/products',
    tags=['admin-products']
)

stock_router = APIRouter(
    prefix='/admin/stocks',
    tags=['admin-stocks']
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

# Pydantic models for request/response
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        orm_mode = True

class ProductImageBase(BaseModel):
    image_url: str
    is_primary: bool = False

class ProductImageCreate(ProductImageBase):
    pass

class ProductImageResponse(ProductImageBase):
    id: int
    
    class Config:
        orm_mode = True

class ReviewBase(BaseModel):
    rating: int
    review_text: str
    
    @validator('rating')
    def rating_must_be_valid(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

class ReviewCreate(ReviewBase):
    pass

class ReviewResponse(ReviewBase):
    id: int
    user_id: int
    product_id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

class StockBase(BaseModel):
    change_type: StockChangeType
    quantity: int

class StockCreate(StockBase):
    pass

class StockResponse(StockBase):
    id: int
    product_id: int
    date: datetime
    
    class Config:
        orm_mode = True

class ProductBase(BaseModel):
    name: str
    category_id: int
    brand: str
    weight: Optional[float] = None
    gender: Gender
    size: Size
    description: str
    price: float
    in_stock: bool = True

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    brand: Optional[str] = None
    weight: Optional[float] = None
    gender: Optional[Gender] = None
    size: Optional[Size] = None
    description: Optional[str] = None
    price: Optional[float] = None
    in_stock: Optional[bool] = None

class ProductResponse(ProductBase):
    id: int
    how_much_sold: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class ProductDetailResponse(ProductResponse):
    category: CategoryResponse
    images: List[ProductImageResponse]
    reviews: List[ReviewResponse]
    stock_left: int
    
    class Config:
        orm_mode = True

# Sorting options
class SortOptions(str, enum.Enum):
    NEWEST = "newest"
    PRICE_LOW_TO_HIGH = "price_low_to_high"
    PRICE_HIGH_TO_LOW = "price_high_to_low"
    BEST_SELLING = "best_selling"

# Helper functions
def apply_filters(query, category_id=None, min_price=None, max_price=None, 
                 size=None, gender=None, in_stock=None):
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if size:
        query = query.filter(Product.size == size)
    if gender:
        query = query.filter(Product.gender == gender)
    if in_stock is not None:
        query = query.filter(Product.in_stock == in_stock)
    return query

def apply_sorting(query, sort_by=SortOptions.NEWEST):
    if sort_by == SortOptions.NEWEST:
        return query.order_by(desc(Product.created_at))
    elif sort_by == SortOptions.PRICE_LOW_TO_HIGH:
        return query.order_by(asc(Product.price))
    elif sort_by == SortOptions.PRICE_HIGH_TO_LOW:
        return query.order_by(desc(Product.price))
    elif sort_by == SortOptions.BEST_SELLING:
        return query.order_by(desc(Product.how_much_sold))
    return query

def apply_pagination(query, skip=0, limit=12):
    return query.offset(skip).limit(limit)

def check_admin(user):
    if user is None or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

# Category endpoints
@admin_router.post('/categories/', response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(user: user_dependency, db: db_dependency, category: CategoryCreate):
    check_admin(user)
    db_category = Category(**category.dict())
    db.add(db_category)
    try:
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )

@router.get('/categories/', response_model=List[CategoryResponse])
def get_categories(db: db_dependency, skip: int = 0, limit: int = 100):
    return db.query(Category).offset(skip).limit(limit).all()

# Admin Product endpoints
@admin_router.post('/', response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(user: user_dependency, db: db_dependency, product: ProductCreate):
    check_admin(user)
    
    # Check if category exists
    category = db.query(Category).filter(Category.id == product.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {product.category_id} not found"
        )
    
    db_product = Product(**product.dict())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@admin_router.put('/{product_id}', response_model=ProductResponse)
def update_product(user: user_dependency, db: db_dependency, product_id: int, product: ProductUpdate):
    check_admin(user)
    
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    # Update only provided fields
    update_data = product.dict(exclude_unset=True)
    
    # If category_id is provided, check if it exists
    if 'category_id' in update_data:
        category = db.query(Category).filter(Category.id == update_data['category_id']).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id {update_data['category_id']} not found"
            )
    
    for key, value in update_data.items():
        setattr(db_product, key, value)
    
    db_product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_product)
    return db_product

@admin_router.delete('/{product_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_product(user: user_dependency, db: db_dependency, product_id: int):
    check_admin(user)
    
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    db.delete(db_product)
    db.commit()
    return None

@admin_router.get('/', response_model=List[ProductResponse])
def get_all_products_admin(
    user: user_dependency, 
    db: db_dependency,
    category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[Size] = None,
    gender: Optional[Gender] = None,
    in_stock: Optional[bool] = None,
    sort_by: SortOptions = SortOptions.NEWEST,
    skip: int = 0,
    limit: int = 12
):
    check_admin(user)
    
    query = db.query(Product)
    
    # Apply filters
    query = apply_filters(
        query, category_id, min_price, max_price, size, gender, in_stock
    )
    
    # Apply sorting
    query = apply_sorting(query, sort_by)
    
    # Apply pagination
    total = query.count()
    products = apply_pagination(query, skip, limit).all()
    
    return products

@admin_router.get('/last-week', response_model=List[ProductResponse])
def get_last_week_products(user: user_dependency, db: db_dependency):
    check_admin(user)
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    products = db.query(Product).filter(Product.created_at >= one_week_ago).all()
    
    return products

@admin_router.get('/last-month', response_model=List[ProductResponse])
def get_last_month_products(user: user_dependency, db: db_dependency):
    check_admin(user)
    
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    products = db.query(Product).filter(Product.created_at >= one_month_ago).all()
    
    return products

# Stock management endpoints
@stock_router.get('/', response_model=List[StockResponse])
def get_stock_history(
    user: user_dependency, 
    db: db_dependency,
    product_id: Optional[int] = None,
    change_type: Optional[StockChangeType] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100
):
    check_admin(user)
    
    query = db.query(Stock)
    
    if product_id:
        query = query.filter(Stock.product_id == product_id)
    if change_type:
        query = query.filter(Stock.change_type == change_type)
    if from_date:
        query = query.filter(Stock.date >= from_date)
    if to_date:
        query = query.filter(Stock.date <= to_date)
    
    return query.order_by(desc(Stock.date)).offset(skip).limit(limit).all()

@stock_router.put('/{product_id}', response_model=StockResponse)
def update_stock(
    user: user_dependency, 
    db: db_dependency, 
    product_id: int, 
    stock_update: StockCreate
):
    check_admin(user)
    
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    # Create stock movement
    stock_movement = Stock(
        product_id=product_id,
        change_type=stock_update.change_type,
        quantity=stock_update.quantity
    )
    
    db.add(stock_movement)
    
    # Update product in_stock status based on calculated stock
    current_stock = product.stock_left
    if stock_update.change_type == StockChangeType.RESTOCK or stock_update.change_type == StockChangeType.RETURN:
        current_stock += stock_update.quantity
    elif stock_update.change_type == StockChangeType.SALE:
        current_stock -= stock_update.quantity
        # Update how_much_sold if it's a sale
        product.how_much_sold += stock_update.quantity
    
    # Update in_stock status
    product.in_stock = current_stock > 0
    
    db.commit()
    db.refresh(stock_movement)
    return stock_movement

# Product Image endpoints
@admin_router.post('/{product_id}/images', response_model=ProductImageResponse)
def add_product_image(
    user: user_dependency, 
    db: db_dependency, 
    product_id: int, 
    image: ProductImageCreate
):
    check_admin(user)
    
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    # If this is marked as primary, unset any existing primary images
    if image.is_primary:
        existing_primary = db.query(ProductImage).filter(
            ProductImage.product_id == product_id,
            ProductImage.is_primary == True
        ).all()
        for img in existing_primary:
            img.is_primary = False
    
    db_image = ProductImage(product_id=product_id, **image.dict())
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    return db_image

# Customer Product endpoints
@router.get('/', response_model=List[ProductResponse])
def get_products(
    db: db_dependency,
    user: Optional[user_dependency] = None,  # Optional authentication
    category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[Size] = None,
    gender: Optional[Gender] = None,
    in_stock: Optional[bool] = True,  # Default to showing only in-stock items
    sort_by: SortOptions = SortOptions.NEWEST,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100)
):
    skip = (page - 1) * limit
    
    query = db.query(Product)
    
    # Apply filters
    query = apply_filters(
        query, category_id, min_price, max_price, size, gender, in_stock
    )
    
    # Apply sorting
    query = apply_sorting(query, sort_by)
    
    # Get total count for pagination info
    total = query.count()
    
    # Apply pagination
    products = apply_pagination(query, skip, limit).all()
    
    return products

@router.get('/{product_id}', response_model=ProductDetailResponse)
def get_product(
    db: db_dependency,
    product_id: int = Path(..., ge=1),
    user: Optional[user_dependency] = None  # Optional authentication
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    return product

@router.get('/this-week', response_model=List[ProductResponse])
def get_this_week_products(
    db: db_dependency,
    user: Optional[user_dependency] = None,  # Optional authentication
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100)
):
    skip = (page - 1) * limit
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    query = db.query(Product).filter(
        Product.created_at >= one_week_ago,
        Product.in_stock == True
    )
    
    total = query.count()
    products = query.order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    return products

@router.get('/this-month', response_model=List[ProductResponse])
def get_this_month_products(
    db: db_dependency,
    user: Optional[user_dependency] = None,  # Optional authentication
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100)
):
    skip = (page - 1) * limit
    
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    query = db.query(Product).filter(
        Product.created_at >= one_month_ago,
        Product.in_stock == True
    )
    
    total = query.count()
    products = query.order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    return products

# Review endpoints
@router.post('/{product_id}/reviews/', response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    user: user_dependency,
    db: db_dependency,
    product_id: int,
    review: ReviewCreate
):
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    # Check if user has already reviewed this product
    existing_review = db.query(Review).filter(
        Review.product_id == product_id,
        Review.user_id == user.get('id')
    ).first()
    
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this product"
        )
    
    db_review = Review(
        product_id=product_id,
        user_id=user.get('id'),
        **review.dict()
    )
    
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

@router.get('/{product_id}/reviews/', response_model=List[ReviewResponse])
def get_product_reviews(
    db: db_dependency,
    product_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    user: Optional[user_dependency] = None  # Optional authentication
):
    skip = (page - 1) * limit
    
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    reviews = db.query(Review).filter(
        Review.product_id == product_id
    ).order_by(desc(Review.created_at)).offset(skip).limit(limit).all()
    
    return reviews 