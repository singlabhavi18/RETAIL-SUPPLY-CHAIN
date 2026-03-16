import pandas as pd
import numpy as np
import xgboost as xgb
from datetime import timedelta
from sqlalchemy.orm import Session
from app import models


def predict_stockout(db: Session, n_days: int = 7, run_every_n_days: int = 7):

    risky_products = []

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

        # =========================
        # RUN MODEL EVERY N DAYS
        # =========================

        last_date = df["date"].max()

        if last_date.day % run_every_n_days != 0:
            continue

        # =========================
        # TRAIN MODEL
        # =========================

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

        # =========================
        # REMAINING DAYS OF MONTH
        # =========================

        days_in_month = pd.Timestamp(last_date).days_in_month
        days_left = days_in_month - last_date.day

        if days_left <= 0:
            continue

        forecast_horizon = days_left

        # =========================
        # RECURSIVE FORECAST
        # =========================

        last_row = df.iloc[-1].copy()

        history_units = df["units"].tolist()

        predictions = []

        for i in range(forecast_horizon):

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

            predictions.append(pred)

            history_units.append(pred)

            last_row["units"] = pred
            last_row["date"] = next_date

        # =========================
        # DEMAND CALCULATIONS
        # =========================

        predicted_next_n_days = sum(predictions[:n_days])

        predicted_remaining_month = sum(predictions)

        # =========================
        # INVENTORY CHECK
        # =========================

        inventory = db.query(models.Inventory).filter(
            models.Inventory.product_id == product.product_id
        ).first()

        if not inventory:
            continue

        current_stock = inventory.current_stock

        if predicted_next_n_days > current_stock:

            recommended_restock = predicted_remaining_month - current_stock

            risky_products.append({
                "product_name": product.product_name,
                "current_stock": current_stock,
                "predicted_next_n_days": predicted_next_n_days,
                "predicted_remaining_month": predicted_remaining_month,
                "days_left_in_month": days_left,
                "recommended_restock": max(0, round(recommended_restock))
            })

    return risky_products