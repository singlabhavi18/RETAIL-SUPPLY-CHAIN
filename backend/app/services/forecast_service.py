import pandas as pd
import numpy as np
import lightgbm as lgb
from sqlalchemy.orm import Session
from datetime import datetime
from app import models


def forecast_next_month(db: Session, product_names=None):

    # 1️⃣ Fetch sales joined with product info
    query = db.query(models.Sale, models.Product).join(
        models.Product,
        models.Sale.product_id == models.Product.product_id
    )

    if product_names:
        names_list = [n.strip().lower() for n in product_names.split(",")]
        query = query.filter(models.Product.product_name.in_(names_list))

    results = query.all()

    if not results:
        return {"message": "No sales data available"}

    # Convert to DataFrame
    rows = []
    for sale, product in results:
        rows.append({
            "Date": sale.sale_date,
            "product_id": product.product_id,
            "product_name": product.product_name,
            "Units Sold": sale.units_sold
        })

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")

    # Monthly aggregation
    df["year"] = df["Date"].dt.year
    df["month"] = df["Date"].dt.month

    monthly = (
        df.groupby(["product_id", "product_name", "year", "month"], as_index=False)
        .agg({"Units Sold": "sum"})
    )

    monthly["Date"] = pd.to_datetime(
        monthly["year"].astype(str) + "-" +
        monthly["month"].astype(str) + "-01"
    )

    monthly = monthly.sort_values(["product_id", "Date"])

    # Cyclic month features
    monthly["month_sin"] = np.sin(2 * np.pi * monthly["month"] / 12)
    monthly["month_cos"] = np.cos(2 * np.pi * monthly["month"] / 12)

    # Lags
    monthly["lag_1"] = monthly.groupby("product_id")["Units Sold"].shift(1)
    monthly["lag_2"] = monthly.groupby("product_id")["Units Sold"].shift(2)
    monthly["lag_3"] = monthly.groupby("product_id")["Units Sold"].shift(3)

    monthly["rolling_mean_3"] = (
        monthly.groupby("product_id")["Units Sold"]
        .transform(lambda x: x.shift(1).rolling(3).mean())
    )

    monthly = monthly.dropna().reset_index(drop=True)

    last_date = monthly["Date"].max()
    next_month = last_date + pd.offsets.MonthBegin(1)

    forecasts = []

    grouped = monthly.groupby("product_id")

    for product_id, group in grouped:

        if len(group) < 4:
            continue

        train = group.copy()
        train["Units Sold_log"] = np.log1p(train["Units Sold"])

        X_train = train.drop(columns=["Units Sold", "Units Sold_log", "Date", "product_name"])
        y_train = train["Units Sold_log"]

        model = lgb.LGBMRegressor(
            n_estimators=500,
            learning_rate=0.05,
            num_leaves=32,
            random_state=42
        )

        model.fit(X_train, y_train)

        last3 = group.tail(3)
        units = last3["Units Sold"].values

        feature = {
            "product_id": product_id,
            "year": next_month.year,
            "month": next_month.month,
            "month_sin": np.sin(2 * np.pi * next_month.month / 12),
            "month_cos": np.cos(2 * np.pi * next_month.month / 12),
            "lag_1": units[-1],
            "lag_2": units[-2],
            "lag_3": units[-3],
            "rolling_mean_3": units.mean()
        }

        X_pred = pd.DataFrame([feature])
        X_pred = X_pred.reindex(columns=X_train.columns, fill_value=0)

        y_pred_log = model.predict(X_pred)[0]
        y_pred = np.expm1(y_pred_log)

        product_name = group["product_name"].iloc[0]

        forecasts.append({
            "product_name": product_name,
            "forecast_month": next_month.strftime("%Y-%m"),
            "forecast_units": round(y_pred)
        })

    return forecasts