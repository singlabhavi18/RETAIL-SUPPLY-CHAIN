import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app import models


def calculate_safety_stock(db: Session, product_names: str = None):
    """
    Calculate safety stock and reorder point for each product.
    
    Formula:
    - safety_stock = Z * std_dev_demand * sqrt(lead_time)
    - reorder_point = (avg_demand * lead_time) + safety_stock
    
    Where:
    - Z = 1.65 (95% service level)
    - std_dev_demand = standard deviation of daily demand
    - lead_time = lead_time_days from Product model
    - avg_demand = average daily demand
    """
    
    Z_SCORE = 1.65  # 95% service level
    
    results = []
    
    # Fetch products
    query = db.query(models.Product)
    
    if product_names:
        names_list = [name.strip().lower() for name in product_names.split(",")]
        query = query.filter(models.Product.product_name.in_(names_list))
    
    products = query.all()
    
    for product in products:
        
        # Fetch historical sales data
        sales = db.query(models.Sale).filter(
            models.Sale.product_id == product.product_id
        ).all()
        
        if not sales:
            continue
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            "date": s.sale_date,
            "units": s.units_sold
        } for s in sales])
        
        df["date"] = pd.to_datetime(df["date"])
        
        # Aggregate per day
        df = df.groupby("date").agg({"units": "sum"}).reset_index()
        
        # Fill missing dates with 0 demand
        full_range = pd.date_range(df["date"].min(), df["date"].max())
        df = (
            df.set_index("date")
            .reindex(full_range)
            .fillna(0)
            .rename_axis("date")
            .reset_index()
        )
        
        # Calculate demand statistics
        daily_demand = df["units"].values
        avg_demand = np.mean(daily_demand)
        std_dev_demand = np.std(daily_demand, ddof=1)  # Sample standard deviation
        
        # Get lead time from product model
        lead_time = product.lead_time_days
        
        # Calculate safety stock
        safety_stock = Z_SCORE * std_dev_demand * np.sqrt(lead_time)
        
        # Calculate reorder point
        reorder_point = (avg_demand * lead_time) + safety_stock
        
        results.append({
            "product_name": product.product_name,
            "lead_time_days": lead_time,
            "avg_daily_demand": round(avg_demand, 2),
            "std_dev_daily_demand": round(std_dev_demand, 2),
            "safety_stock": round(safety_stock),
            "reorder_point": round(reorder_point)
        })
    
    return results
