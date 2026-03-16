from pydantic import BaseModel
from datetime import date


class ProductCreate(BaseModel):
    product_name: str
    category: str
    holding_cost: float
    shortage_cost: float
    lead_time_days: int
    initial_stock: int


class InventoryAdd(BaseModel):
    product_name: str
    quantity_added: int