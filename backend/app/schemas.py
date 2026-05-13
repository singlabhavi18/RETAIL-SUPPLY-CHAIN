from pydantic import BaseModel
from datetime import date
from typing import List


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


class BulkRestockItem(BaseModel):
    product_name: str
    quantity_added: int


class BulkRestockRequest(BaseModel):
    items: List[BulkRestockItem]