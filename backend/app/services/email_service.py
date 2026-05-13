import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from typing import List, Dict


def send_restock_alert_email(
    products: List[Dict],
    recipient_email: str,
    forecast_days: int = 7
) -> bool:
    """
    Send restock alert email using SMTP.
    
    Args:
        products: List of product dictionaries with restock information
        recipient_email: Email address to send the alert to
        forecast_days: Number of days forecast was calculated for
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    # Get SMTP configuration from environment variables
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL", smtp_username)
    
    # Validate configuration
    if not all([smtp_server, smtp_username, smtp_password, recipient_email]):
        print("SMTP configuration incomplete. Email not sent.")
        return False
    
    try:
        # Create email message
        msg = MIMEMultipart()
        
        if len(products) == 1:
            # Single product alert
            product = products[0]
            msg["Subject"] = f"Restock Alert - {product['product_name']}"
            
            body = f"""RESTOCK ALERT

Product: {product['product_name']}
Current Stock: {product['current_stock']}
Reorder Point: {product['reorder_point']}
Recommended Order Quantity: {product['recommended_order_qty']}
Forecasted Demand (Next {forecast_days} Days): {product.get(f'forecasted_demand_next_{forecast_days}days', 0)}
Safety Stock: {product.get('safety_stock', 0)}

Action Required: Please place an order to restock this product.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:
            # Multiple products alert
            total_qty = sum(p['recommended_order_qty'] for p in products)
            msg["Subject"] = f"Restock Alert - {len(products)} Products Need Attention"
            
            product_list = ""
            for i, product in enumerate(products, 1):
                product_list += f"""
{i}. {product['product_name']}
   Current Stock: {product['current_stock']}
   Reorder Point: {product['reorder_point']}
   Recommended Order Quantity: {product['recommended_order_qty']}
   Forecasted Demand (Next {forecast_days} Days): {product.get(f'forecasted_demand_next_{forecast_days}days', 0)}
"""
            
            body = f"""RESTOCK ALERT - {len(products)} Products Need Attention

The following products require restocking:
{product_list}

Total Recommended Order Quantity: {total_qty}

Action Required: Please place orders to restock these products.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        msg.attach(MIMEText(body, "plain"))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"Restock alert email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


def send_stockout_alert_email(
    products: List[Dict],
    recipient_email: str
) -> bool:
    """
    Send stockout risk alert email using SMTP.
    
    Args:
        products: List of product dictionaries with stockout risk information
        recipient_email: Email address to send the alert to
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    # Get SMTP configuration from environment variables
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender_email = os.getenv("SENDER_EMAIL", smtp_username)
    
    # Validate configuration
    if not all([smtp_server, smtp_username, smtp_password, recipient_email]):
        print("SMTP configuration incomplete. Email not sent.")
        return False
    
    try:
        # Create email message
        msg = MIMEMultipart()
        
        if len(products) == 1:
            # Single product alert
            product = products[0]
            msg["Subject"] = f"Stockout Risk Alert - {product['product_name']}"
            
            body = f"""STOCKOUT RISK ALERT

Product: {product['product_name']}
Current Stock: {product['current_stock']}
Predicted Demand (Next 7 Days): {product['predicted_next_n_days']}
Predicted Demand (Remaining Month): {product['predicted_remaining_month']}
Days Left in Month: {product['days_left_in_month']}
Recommended Restock: {product['recommended_restock']}

WARNING: This product is at high risk of stockout!

Action Required: Please place an order immediately.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:
            # Multiple products alert
            total_restock = sum(p['recommended_restock'] for p in products)
            msg["Subject"] = f"Stockout Risk Alert - {len(products)} Products at Risk"
            
            product_list = ""
            for i, product in enumerate(products, 1):
                product_list += f"""
{i}. {product['product_name']}
   Current Stock: {product['current_stock']}
   Predicted Demand (Next 7 Days): {product['predicted_next_n_days']}
   Recommended Restock: {product['recommended_restock']}
"""
            
            body = f"""STOCKOUT RISK ALERT - {len(products)} Products at Risk

The following products are at high risk of stockout:
{product_list}

Total Recommended Restock: {total_restock}

WARNING: These products may run out of stock soon!

Action Required: Please place orders immediately.

Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        msg["From"] = sender_email
        msg["To"] = recipient_email
        
        msg.attach(MIMEText(body, "plain"))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        
        print(f"Stockout alert email sent successfully to {recipient_email}")
        return True
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False
