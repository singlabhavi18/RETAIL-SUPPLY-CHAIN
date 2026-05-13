import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from app import models


def predict_mid_month_stockout(db: Session):
    """
    Predict mid-month restock needs by forecasting remaining days and calculating expected stockout date.
    
    Logic:
    1. Use historical daily sales data
    2. Train XGBoost model for demand forecasting
    3. Forecast demand for each remaining day in the month
    4. Calculate cumulative demand to find expected stockout date
    5. Return products that will run out before month end with expected stockout date
    
    Returns:
        List of products with expected stockout dates
    """
    
    at_risk_products = []
    
    products = db.query(models.Product).all()
    
    for product in products:
        
        sales = db.query(models.Sale).filter(
            models.Sale.product_id == product.product_id
        ).all()
        
        if not sales:
            continue
        
        # Convert to DataFrame
        df = pd.DataFrame([{
            "date": s.sale_date,
            "units": s.units_sold,
            "holiday": s.holiday_flag if s.holiday_flag else 0
        } for s in sales])
        
        df["date"] = pd.to_datetime(df["date"])
        
        # Aggregate per day
        df = df.groupby("date").agg({
            "units": "sum",
            "holiday": "max"
        }).reset_index()
        
        # Fill missing dates
        full_range = pd.date_range(df["date"].min(), df["date"].max())
        
        df = (
            df.set_index("date")
            .reindex(full_range)
            .fillna(0)
            .rename_axis("date")
            .reset_index()
        )
        
        # Feature engineering
        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
        
        df["lag_1"] = df["units"].shift(1)
        df["lag_7"] = df["units"].shift(7)
        
        df["rolling_mean_7"] = df["units"].shift(1).rolling(7).mean()
        df["rolling_mean_14"] = df["units"].shift(1).rolling(14).mean()
        
        df = df.dropna()
        
        if len(df) < 30:
            continue
        
        # Train model
        features = [
            "day_of_week",
            "day_of_month",
            "month",
            "is_weekend",
            "holiday",
            "lag_1",
            "lag_7",
            "rolling_mean_7",
            "rolling_mean_14"
        ]
        
        X = df[features]
        y = df["units"]
        
        model = xgb.XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=5,
            random_state=42
        )
        
        model.fit(X, y)
        
        # Calculate remaining days in month
        last_date = df["date"].max()
        days_in_month = pd.Timestamp(last_date).days_in_month
        days_left = days_in_month - last_date.day
        
        if days_left <= 0:
            continue
        
        # Get current stock
        inventory = db.query(models.Inventory).filter(
            models.Inventory.product_id == product.product_id
        ).first()
        
        if not inventory:
            continue
        
        current_stock = inventory.current_stock
        
        # Recursive forecasting for remaining days
        last_row = df.iloc[-1].copy()
        history_units = df["units"].tolist()
        
        daily_forecasts = []
        forecast_dates = []
        cumulative_demand = 0
        expected_stockout_date = None
        will_stockout = False
        
        for i in range(days_left):
            next_date = last_row["date"] + timedelta(days=1)
            
            lag_1 = history_units[-1]
            lag_7 = history_units[-7] if len(history_units) >= 7 else history_units[-1]
            
            rolling_7 = np.mean(history_units[-7:])
            rolling_14 = np.mean(history_units[-14:]) if len(history_units) >= 14 else rolling_7
            
            new_row = {
                "day_of_week": next_date.dayofweek,
                "day_of_month": next_date.day,
                "month": next_date.month,
                "is_weekend": int(next_date.dayofweek in [5, 6]),
                "holiday": 0,
                "lag_1": lag_1,
                "lag_7": lag_7,
                "rolling_mean_7": rolling_7,
                "rolling_mean_14": rolling_14
            }
            
            X_pred = pd.DataFrame([new_row])
            pred = model.predict(X_pred)[0]
            pred = max(0, round(pred))
            
            daily_forecasts.append(pred)
            forecast_dates.append(next_date)
            
            # Calculate cumulative demand
            cumulative_demand += pred
            
            # Check if stock will run out on this day
            if not will_stockout and cumulative_demand >= current_stock:
                will_stockout = True
                expected_stockout_date = next_date
            
            history_units.append(pred)
            last_row["units"] = pred
            last_row["date"] = next_date
        
        # Only include products that will stockout before month end
        if will_stockout:
            days_until_stockout = (expected_stockout_date - last_date).days if expected_stockout_date else None
            
            at_risk_products.append({
                "product_name": product.product_name,
                "current_stock": current_stock,
                "predicted_remaining_month_demand": sum(daily_forecasts),
                "days_left_in_month": days_left,
                "expected_stockout_date": expected_stockout_date.strftime("%Y-%m-%d") if expected_stockout_date else None,
                "days_until_stockout": days_until_stockout,
                "daily_forecast": daily_forecasts[:7],  # First 7 days forecast
                "urgency": "High" if days_until_stockout and days_until_stockout <= 3 else "Medium" if days_until_stockout and days_until_stockout <= 7 else "Low"
            })
    
    # Sort by urgency and days until stockout
    urgency_order = {"High": 0, "Medium": 1, "Low": 2}
    at_risk_products.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), x["days_until_stockout"] if x["days_until_stockout"] else 999))
    
    return at_risk_products
