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

# Define routers with clear prefixes and tags
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

# Type annotations for dependencies
db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]

#######################
# Pydantic Models
#######################

# Category Models
class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    
    class Config:
        orm_mode = True

# Product Image Models
class ProductImageBase(BaseModel):
    image_url: str
    is_primary: bool = False

class ProductImageCreate(ProductImageBase):
    pass

class ProductImageResponse(ProductImageBase):
    id: int
    
    class Config:
        orm_mode = True

# Review Models
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

# Stock Models
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

# Product Models
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
    initial_stock: int = 0

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
    reviews: List[ReviewResponse] = []
    average_rating: Optional[float] = None
    
    class Config:
        orm_mode = True

class ProductDetailResponse(ProductResponse):
    category: CategoryResponse
    images: List[ProductImageResponse]
    stock_left: int
    
    class Config:
        orm_mode = True

# Sorting Options
class SortOptions(str, enum.Enum):
    NEWEST = "newest"
    PRICE_LOW_TO_HIGH = "price_low_to_high"
    PRICE_HIGH_TO_LOW = "price_high_to_low"
    BEST_SELLING = "best_selling"

#######################
# Helper Functions
#######################

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
    """Verify that the user has admin privileges"""
    if not user or user.get('user_role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform this action"
        )

def enhance_products_with_reviews(products, db):
    """Add review information to product responses"""
    enhanced_products = []
    
    for product in products:
        # Convert to dict for easier manipulation
        product_dict = {
            **product.__dict__,
            'reviews': [],
            'average_rating': None
        }
        
        # Get reviews for this product
        reviews = db.query(Review).filter(Review.product_id == product.id).all()
        
        if reviews:
            # Calculate average rating
            total_rating = sum(review.rating for review in reviews)
            avg_rating = total_rating / len(reviews)
            product_dict['average_rating'] = round(avg_rating, 1)
            
            # Add reviews to product
            product_dict['reviews'] = reviews
        
        enhanced_products.append(product_dict)
    
    return enhanced_products

#######################
# Category Endpoints
#######################

@router.get('/categories/', response_model=List[CategoryResponse])
def get_categories(db: db_dependency, skip: int = 0, limit: int = 100):
    """Get all categories with pagination"""
    categories = db.query(Category).offset(skip).limit(limit).all()
    return categories

@admin_router.post('/categories/', response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(user: user_dependency, db: db_dependency, category: CategoryCreate):
    """Create a new category (admin only)"""
    check_admin(user)
    
    db_category = Category(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@admin_router.get('/categories/', response_model=List[CategoryResponse])
def get_categories_for_dashboard(user: user_dependency, db: db_dependency):
    """Get all categories for admin dashboard"""
    check_admin(user)
    categories = db.query(Category).all()
    return categories

#######################
# Customer Product Endpoints
#######################

@router.get('/', response_model=List[ProductResponse])
def get_filtered_products(
    db: db_dependency,
    category_id: Optional[int] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[Size] = None,
    gender: Optional[Gender] = None,
    in_stock: Optional[bool] = True,  # Default to showing only in-stock items
    sort_by: SortOptions = SortOptions.NEWEST,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get products with filtering, sorting, and pagination"""
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
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@router.get('/all', response_model=List[ProductResponse])
def get_all_products(
    db: db_dependency,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get all in-stock products with pagination"""
    skip = (page - 1) * limit
    
    query = db.query(Product).filter(Product.in_stock == True)
    products = query.order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@router.get('/detail/{product_id}', response_model=ProductDetailResponse)
def get_product_detail(
    db: db_dependency,
    product_id: int = Path(..., ge=1),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get detailed information about a specific product"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    return product

@router.get('/new-arrivals', response_model=List[ProductResponse])
def get_new_arrivals(
    db: db_dependency,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get products added in the last week"""
    skip = (page - 1) * limit
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    query = db.query(Product).filter(
        Product.created_at >= one_week_ago,
        Product.in_stock == True
    )
    
    products = query.order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@router.get('/monthly-featured', response_model=List[ProductResponse])
def get_monthly_featured(
    db: db_dependency,
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get products added in the last month"""
    skip = (page - 1) * limit
    
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    query = db.query(Product).filter(
        Product.created_at >= one_month_ago,
        Product.in_stock == True
    )
    
    products = query.order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

#######################
# Review Endpoints
#######################

@router.post('/reviews/{product_id}', response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    user: user_dependency,
    db: db_dependency,
    product_id: int,
    review: ReviewCreate
):
    """Create a new review for a product"""
    # Check if product exists
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found"
        )
    
    # Check if user has already reviewed this product
    existing_review = db.query(Review).filter(
        Review.user_id == user['id'],
        Review.product_id == product_id
    ).first()
    
    if existing_review:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already reviewed this product"
        )
    
    # Create review
    db_review = Review(
        **review.dict(),
        user_id=user['id'],
        product_id=product_id
    )
    
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return db_review

@router.get('/reviews/{product_id}', response_model=List[ReviewResponse])
def get_product_reviews(
    db: db_dependency,
    product_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_user: Optional[user_dependency] = Depends(get_current_user)
):
    """Get reviews for a specific product with pagination"""
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

#######################
# Admin Product Endpoints
#######################

@admin_router.post('/', response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(user: user_dependency, db: db_dependency, product: ProductCreate):
    """Create a new product (admin only)"""
    check_admin(user)
    
    # Check if category exists
    category = db.query(Category).filter(Category.id == product.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {product.category_id} not found"
        )
    
    # Extract initial_stock and remove it from the product data
    initial_stock = product.initial_stock
    product_data = product.dict()
    del product_data['initial_stock']
    
    # Create the product
    db_product = Product(**product_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    # Add initial stock if provided
    if initial_stock > 0:
        stock_movement = Stock(
            product_id=db_product.id,
            change_type=StockChangeType.RESTOCK,
            quantity=initial_stock
        )
        db.add(stock_movement)
        db.commit()
        
        # Update product in_stock status
        db_product.in_stock = True
        db.commit()
        db.refresh(db_product)
    
    return db_product

@admin_router.put('/{product_id}', response_model=ProductResponse)
def update_product(user: user_dependency, db: db_dependency, product_id: int, product: ProductUpdate):
    """Update an existing product (admin only)"""
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
    """Delete a product (admin only)"""
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
    """Get all products with filtering for admin (admin only)"""
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
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

#######################
# Admin Dashboard Endpoints
#######################

@admin_router.get('/dashboard/all', response_model=List[ProductResponse])
def get_all_products_for_dashboard(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 100
):
    """Get all products without filtering for admin dashboard (admin only)"""
    check_admin(user)
    
    products = db.query(Product).order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/dashboard/by-category/{category_id}', response_model=List[ProductResponse])
def get_products_by_category(
    user: user_dependency,
    db: db_dependency,
    category_id: int,
    skip: int = 0,
    limit: int = 100
):
    """Get products filtered by category for admin dashboard (admin only)"""
    check_admin(user)
    
    # Check if category exists
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found"
        )
    
    products = db.query(Product).filter(
        Product.category_id == category_id
    ).order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/dashboard/in-stock', response_model=List[ProductResponse])
def get_in_stock_products(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 100
):
    """Get all in-stock products for admin dashboard (admin only)"""
    check_admin(user)
    
    products = db.query(Product).filter(
        Product.in_stock == True
    ).order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/dashboard/out-of-stock', response_model=List[ProductResponse])
def get_out_of_stock_products(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 100
):
    """Get all out-of-stock products for admin dashboard (admin only)"""
    check_admin(user)
    
    products = db.query(Product).filter(
        Product.in_stock == False
    ).order_by(desc(Product.created_at)).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/dashboard/best-selling', response_model=List[ProductResponse])
def get_best_selling_products(
    user: user_dependency,
    db: db_dependency,
    skip: int = 0,
    limit: int = 10
):
    """Get best-selling products for admin dashboard (admin only)"""
    check_admin(user)
    
    products = db.query(Product).order_by(
        desc(Product.how_much_sold)
    ).offset(skip).limit(limit).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/dashboard/low-stock', response_model=List[ProductResponse])
def get_low_stock_products(
    user: user_dependency,
    db: db_dependency,
    threshold: int = 10,
    skip: int = 0,
    limit: int = 100
):
    """Get products with low stock for admin dashboard (admin only)"""
    check_admin(user)
    
    # This is a more complex query that requires joining with Stock
    # First, get all products
    products = db.query(Product).filter(Product.in_stock == True).all()
    
    # Filter products with stock below threshold
    low_stock_products = []
    for product in products:
        if product.stock_left <= threshold:
            low_stock_products.append(product)
    
    # Apply pagination manually
    paginated_products = low_stock_products[skip:skip+limit]
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(paginated_products, db)

@admin_router.get('/dashboard/summary', status_code=status.HTTP_200_OK)
def get_products_summary(
    user: user_dependency,
    db: db_dependency
):
    """Get summary statistics about products for admin dashboard (admin only)"""
    check_admin(user)
    
    # Total products
    total_products = db.query(func.count(Product.id)).scalar()
    
    # In-stock products
    in_stock_products = db.query(func.count(Product.id)).filter(Product.in_stock == True).scalar()
    
    # Out-of-stock products
    out_of_stock_products = db.query(func.count(Product.id)).filter(Product.in_stock == False).scalar()
    
    # Products by category
    products_by_category = db.query(
        Category.name, 
        func.count(Product.id)
    ).join(
        Product, 
        Product.category_id == Category.id
    ).group_by(
        Category.name
    ).all()
    
    # Format products by category
    category_data = [
        {"category": name, "count": count}
        for name, count in products_by_category
    ]
    
    # Best-selling products (top 5)
    best_selling = db.query(Product).order_by(
        desc(Product.how_much_sold)
    ).limit(5).all()
    
    best_selling_data = [
        {
            "id": product.id,
            "name": product.name,
            "sold": product.how_much_sold,
            "price": product.price
        }
        for product in best_selling
    ]
    
    # Recently added products (last 5)
    recent_products = db.query(Product).order_by(
        desc(Product.created_at)
    ).limit(5).all()
    
    recent_products_data = [
        {
            "id": product.id,
            "name": product.name,
            "added": product.created_at,
            "price": product.price
        }
        for product in recent_products
    ]
    
    return {
        "total_products": total_products,
        "in_stock_products": in_stock_products,
        "out_of_stock_products": out_of_stock_products,
        "products_by_category": category_data,
        "best_selling": best_selling_data,
        "recent_products": recent_products_data
    }

@admin_router.get('/recent', response_model=List[ProductResponse])
def get_recent_products(user: user_dependency, db: db_dependency):
    """Get products added in the last week (admin only)"""
    check_admin(user)
    
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    products = db.query(Product).filter(Product.created_at >= one_week_ago).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db)

@admin_router.get('/monthly', response_model=List[ProductResponse])
def get_monthly_products(user: user_dependency, db: db_dependency):
    """Get products added in the last month (admin only)"""
    check_admin(user)
    
    one_month_ago = datetime.utcnow() - timedelta(days=30)
    products = db.query(Product).filter(Product.created_at >= one_month_ago).all()
    
    # Enhance products with reviews and average rating
    return enhance_products_with_reviews(products, db) 