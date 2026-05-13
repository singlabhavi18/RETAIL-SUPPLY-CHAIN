from sqlalchemy.orm import Session
from app import models
from app.services.safety_stock_service import calculate_safety_stock
from app.services.stockout_service import predict_stockout
from app.services.email_service import send_restock_alert_email
import os


def get_restock_recommendations(db: Session, forecast_days: int = 7, product_names: str = None):
    """
    Generate restock recommendations based on safety stock and forecasted demand.
    
    Logic:
    - If current_stock < reorder_point:
        recommended_qty = (forecasted_demand + safety_stock) - current_stock
    - Otherwise: recommended_qty = 0
    
    Args:
        db: Database session
        forecast_days: Number of days to forecast demand (default: 7)
        product_names: Optional comma-separated list of product names to filter
    
    Returns:
        List of dictionaries with restock recommendations
    """
    
    # Get safety stock data (includes reorder_point and safety_stock)
    safety_stock_data = calculate_safety_stock(db, product_names)
    
    # Build lookup dictionary for safety stock data
    safety_stock_lookup = {
        item["product_name"]: item 
        for item in safety_stock_data
    }
    
    # Get forecasted demand from stockout service
    stockout_predictions = predict_stockout(db, n_days=forecast_days)
    
    # Build lookup dictionary for forecasted demand
    forecast_lookup = {
        item["product_name"]: item 
        for item in stockout_predictions
    }
    
    recommendations = []
    
    # Get all products (filtered if product_names provided)
    query = db.query(models.Product)
    if product_names:
        names_list = [name.strip().lower() for name in product_names.split(",")]
        query = query.filter(models.Product.product_name.in_(names_list))
    
    products = query.all()
    
    for product in products:
        product_name = product.product_name
        
        # Get current stock
        inventory = db.query(models.Inventory).filter(
            models.Inventory.product_id == product.product_id
        ).first()
        
        if not inventory:
            continue
        
        current_stock = inventory.current_stock
        
        # Get safety stock data
        ss_data = safety_stock_lookup.get(product_name)
        if not ss_data:
            continue
        
        reorder_point = ss_data["reorder_point"]
        safety_stock = ss_data["safety_stock"]
        
        # Get forecasted demand (if available, otherwise use 0)
        forecast_data = forecast_lookup.get(product_name)
        forecasted_demand = forecast_data["predicted_next_n_days"] if forecast_data else 0
        
        # Calculate recommended order quantity
        if current_stock < reorder_point:
            recommended_order_qty = (forecasted_demand + safety_stock) - current_stock
            recommended_order_qty = max(0, round(recommended_order_qty))
        else:
            recommended_order_qty = 0
        
        # Only include products that need restocking or have forecast data
        if recommended_order_qty > 0 or forecast_data:
            recommendations.append({
                "product_name": product_name,
                "current_stock": current_stock,
                "reorder_point": reorder_point,
                "recommended_order_qty": recommended_order_qty,
                "forecasted_demand_next_{}days".format(forecast_days): forecasted_demand,
                "safety_stock": safety_stock
            })
    
    return recommendations


def send_restock_alerts(db: Session, forecast_days: int = 7, product_names: str = None, send_email: bool = True):
    """
    Get restock recommendations and send email alerts for products that need restocking.
    
    Args:
        db: Database session
        forecast_days: Number of days to forecast demand (default: 7)
        product_names: Optional comma-separated list of product names to filter
        send_email: Whether to send email alerts (default: True)
    
    Returns:
        Dictionary with recommendations and email status
    """
    
    # Get restock recommendations
    recommendations = get_restock_recommendations(db, forecast_days, product_names)
    
    # Filter products that need restocking (recommended_order_qty > 0)
    products_needing_restock = [
        rec for rec in recommendations 
        if rec["recommended_order_qty"] > 0
    ]
    
    email_sent = False
    email_status = ""
    
    if send_email and products_needing_restock:
        # Get recipient email from environment
        recipient_email = os.getenv("ALERT_RECIPIENT_EMAIL")
        
        if recipient_email:
            email_sent = send_restock_alert_email(
                products=products_needing_restock,
                recipient_email=recipient_email,
                forecast_days=forecast_days
            )
            email_status = "Email sent successfully" if email_sent else "Failed to send email"
        else:
            email_status = "ALERT_RECIPIENT_EMAIL not configured in .env"
    elif send_email and not products_needing_restock:
        email_status = "No products need restocking - no email sent"
    else:
        email_status = "Email sending disabled"
    
    return {
        "recommendations": recommendations,
        "products_needing_restock_count": len(products_needing_restock),
        "email_sent": email_sent,
        "email_status": email_status
    }
