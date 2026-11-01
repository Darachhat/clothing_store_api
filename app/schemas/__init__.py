"""
Central schemas registry.
All schemas are formatted following the enterprise template pattern:
  <ENTITY>_<ACTION>_SCHEMA
"""
from app.schemas.auth_schema import *
from app.schemas.base_schema import *
from app.schemas.customer_schema import *
from app.schemas.expense_schema import *
from app.schemas.inventory_schema import *
from app.schemas.product_schema import *
from app.schemas.promotion_schema import *
from app.schemas.purchase_schema import *
from app.schemas.sale_schema import *
from app.schemas.system_log_schema import *
from app.schemas.telegram_schema import *
