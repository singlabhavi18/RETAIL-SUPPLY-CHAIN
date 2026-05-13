from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from app.database import engine, SessionLocal
from app import models, schemas
from datetime import datetime, date
import pandas as pd

from app.services.forecast_service import forecast_next_month
from app.services.stockout_service import predict_stockout
from app.services.safety_stock_service import calculate_safety_stock
from app.services.restock_service import get_restock_recommendations, send_restock_alerts
from app.services.mid_month_stockout_service import predict_mid_month_stockout
from app.schemas import InventoryAdd


app = FastAPI()

models.Base.metadata.create_all(bind=engine)


# -------------------------
# DATABASE SESSION
# -------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# HEALTH CHECK
# -------------------------

@app.get("/")
def health_check():
    return {"status": "Backend running successfully"}


# -------------------------
# ADD PRODUCT
# -------------------------

@app.post("/add-product")
def add_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):

    existing = db.query(models.Product).filter(
        models.Product.product_name == product.product_name.lower().strip()
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Product already exists")

    new_product = models.Product(
        product_name=product.product_name.lower().strip(),
        category=product.category,
        holding_cost=product.holding_cost,
        shortage_cost=product.shortage_cost,
        lead_time_days=product.lead_time_days
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    new_inventory = models.Inventory(
        product_id=new_product.product_id,
        current_stock=product.initial_stock
    )

    db.add(new_inventory)
    db.commit()

    return {
        "message": "Product created successfully",
        "product_id": new_product.product_id
    }


# -------------------------
# UPLOAD SALES
# -------------------------

@app.post("/upload-sales")
def upload_sales(file: UploadFile = File(...), db: Session = Depends(get_db)):

    try:
        df = pd.read_csv(file.file)

        df = df.dropna(how="all")

        required_columns = ["Date", "Product Name", "Units Sold"]

        for col in required_columns:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"Missing column: {col}")

    except Exception:
        raise HTTPException(status_code=400, detail="Invalid CSV file")

    try:

        for _, row in df.iterrows():

            if pd.isna(row["Product Name"]) or pd.isna(row["Units Sold"]):
                continue

            product_name = str(row["Product Name"]).lower().strip()
            units_sold = int(row["Units Sold"])

            product = db.query(models.Product).filter(
                models.Product.product_name == product_name
            ).first()

            if not product:
                db.rollback()
                raise HTTPException(
                    status_code=400,
                    detail=f"Product '{product_name}' not found. Please add the product first."
                )

            new_sale = models.Sale(
                product_id=product.product_id,
                sale_date=datetime.strptime(row["Date"], "%Y-%m-%d").date(),
                units_sold=units_sold,
                price=row.get("Price"),
                discount=row.get("Discount"),
                weather=row.get("Weather Condition"),
                holiday_flag=row.get("Holiday/Promotion"),
                competitor_price=row.get("Competitor Pricing"),
                seasonality=row.get("Seasonality")
            )

            db.add(new_sale)

            inventory = db.query(models.Inventory).filter(
                models.Inventory.product_id == product.product_id
            ).first()

            inventory.current_stock -= units_sold

        db.commit()

        # -------------------------
        # AUTOMATIC STOCKOUT CHECK
        # -------------------------

        latest_date = db.query(models.Sale.sale_date)\
            .order_by(models.Sale.sale_date.desc())\
            .first()[0]

        FORECAST_INTERVAL_DAYS = 3

        risky_products = []

        if latest_date.day % FORECAST_INTERVAL_DAYS == 0:
            risky_products = predict_stockout(db, n_days=7)

        return {
            "message": "Sales uploaded successfully",
            "stockout_check_run": latest_date.day % FORECAST_INTERVAL_DAYS == 0,
            "risky_products": risky_products
        }

    except Exception as e:
        db.rollback()
        raise e


# -------------------------
# INVENTORY VIEW
# -------------------------

@app.get("/inventory")
def get_inventory(product_names: str = Query(None), db: Session = Depends(get_db)):

    query = db.query(models.Product, models.Inventory).join(
        models.Inventory,
        models.Product.product_id == models.Inventory.product_id
    )

    if product_names:
        names_list = [name.strip().lower() for name in product_names.split(",")]
        query = query.filter(models.Product.product_name.in_(names_list))

    results = query.all()

    response = []

    for product, inventory in results:
        response.append({
            "product_id": product.product_id,
            "product_name": product.product_name,
            "current_stock": inventory.current_stock
        })

    return response


# -------------------------
# SALES QUERY
# -------------------------

@app.get("/sales")
def get_sales(
    start_date: date,
    end_date: date,
    product_names: str = Query(None),
    db: Session = Depends(get_db)
):

    query = db.query(models.Sale, models.Product).join(
        models.Product,
        models.Sale.product_id == models.Product.product_id
    ).filter(
        models.Sale.sale_date >= start_date,
        models.Sale.sale_date <= end_date
    )

    if product_names:
        names_list = [name.strip().lower() for name in product_names.split(",")]
        query = query.filter(models.Product.product_name.in_(names_list))

    results = query.all()

    response = []

    for sale, product in results:
        response.append({
            "product_name": product.product_name,
            "sale_date": sale.sale_date,
            "units_sold": sale.units_sold,
            "price": sale.price,
            "discount": sale.discount
        })

    return response


# -------------------------
# FORECAST NEXT MONTH
# -------------------------

@app.get("/forecast-next-month")
def forecast(product_names: str = None, db: Session = Depends(get_db)):
    return forecast_next_month(db, product_names)


# -------------------------
# ADD INVENTORY
# -------------------------

@app.post("/add-to-inventory")
def add_to_inventory(data: InventoryAdd, db: Session = Depends(get_db)):

    product_name = data.product_name.lower().strip()

    if data.quantity_added <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    product = db.query(models.Product).filter(
        models.Product.product_name == product_name
    ).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Product '{product_name}' not found"
        )

    inventory = db.query(models.Inventory).filter(
        models.Inventory.product_id == product.product_id
    ).first()

    if not inventory:
        inventory = models.Inventory(
            product_id=product.product_id,
            current_stock=data.quantity_added
        )
        db.add(inventory)
    else:
        inventory.current_stock += data.quantity_added

    db.commit()

    return {
        "product_name": product_name,
        "quantity_added": data.quantity_added,
        "updated_stock": inventory.current_stock
    }


# -------------------------
# MANUAL STOCKOUT CHECK
# -------------------------

@app.get("/stockout-risk")
def stockout_risk(n_days: int = 7, db: Session = Depends(get_db)):
    return predict_stockout(db, n_days)


# -------------------------
# SAFETY STOCK CALCULATION
# -------------------------

@app.get("/safety-stock")
def safety_stock(product_names: str = Query(None), db: Session = Depends(get_db)):
    return calculate_safety_stock(db, product_names)


# -------------------------
# RESTOCK RECOMMENDATIONS
# -------------------------

@app.get("/restock-recommendations")
def restock_recommendations(
    forecast_days: int = Query(7, ge=1, le=30),
    product_names: str = Query(None),
    db: Session = Depends(get_db)
):
    return get_restock_recommendations(db, forecast_days, product_names)


@app.get("/send-restock-alerts")
def send_restock_alerts_endpoint(
    forecast_days: int = Query(7, ge=1, le=30),
    product_names: str = Query(None),
    send_email: bool = Query(True),
    db: Session = Depends(get_db)
):
    return send_restock_alerts(db, forecast_days, product_names, send_email)


# -------------------------
# MID-MONTH STOCKOUT PREDICTION
# -------------------------

@app.get("/mid-month-stockout-prediction")
def mid_month_stockout_prediction(db: Session = Depends(get_db)):
    return predict_mid_month_stockout(db)


# -------------------------
# BULK RESTOCK
# -------------------------

@app.post("/bulk-restock")
def bulk_restock(request: schemas.BulkRestockRequest, db: Session = Depends(get_db)):
    """
    Bulk restock multiple products in a single request.
    Updates inventory for all products in the request.
    """
    
    updated_products = []
    errors = []
    
    try:
        for item in request.items:
            product_name = item.product_name.lower().strip()
            
            if item.quantity_added <= 0:
                errors.append({
                    "product_name": product_name,
                    "error": "Quantity must be greater than 0"
                })
                continue
            
            product = db.query(models.Product).filter(
                models.Product.product_name == product_name
            ).first()
            
            if not product:
                errors.append({
                    "product_name": product_name,
                    "error": "Product not found"
                })
                continue
            
            inventory = db.query(models.Inventory).filter(
                models.Inventory.product_id == product.product_id
            ).first()
            
            if not inventory:
                inventory = models.Inventory(
                    product_id=product.product_id,
                    current_stock=item.quantity_added
                )
                db.add(inventory)
            else:
                inventory.current_stock += item.quantity_added
            
            updated_products.append({
                "product_name": product_name,
                "quantity_added": item.quantity_added,
                "updated_stock": inventory.current_stock
            })
        
        db.commit()
        
        return {
            "message": f"Successfully updated {len(updated_products)} products",
            "updated_products": updated_products,
            "errors": errors
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))