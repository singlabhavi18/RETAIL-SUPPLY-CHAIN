from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from app.database import Base


# PRODUCTS TABLE
class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50))
    holding_cost = Column(Numeric(10, 2), nullable=False)
    shortage_cost = Column(Numeric(10, 2), nullable=False)
    lead_time_days = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())


# INVENTORY TABLE
class Inventory(Base):
    __tablename__ = "inventory"

    product_id = Column(Integer, ForeignKey("products.product_id"), primary_key=True)
    current_stock = Column(Integer, nullable=False)
    last_updated = Column(TIMESTAMP, server_default=func.now())


# SALES TABLE
class Sale(Base):
    __tablename__ = "sales"

    sale_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    sale_date = Column(Date, nullable=False)
    units_sold = Column(Integer, nullable=False)
    price = Column(Numeric(10,2))
    discount = Column(Numeric(10,2))
    weather = Column(String(50))
    holiday_flag = Column(Integer)
    competitor_price = Column(Numeric(10,2))
    seasonality = Column(String(50))