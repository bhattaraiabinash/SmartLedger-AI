
from pydantic import BaseModel, Field, field_validator
from typing import List
from decimal import Decimal, InvalidOperation

class ExtractedLineItem(BaseModel):
    item_name: str
    quantity: int = Field(gt=0)
    unit_price: Decimal
    line_total: Decimal
    
    @field_validator("unit_price", "line_total", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Could not parse '{v}' as a decimal amount")
class ExtractedInvoiceData(BaseModel):
    vendor_name: str
    invoice_number: str | None = None
    invoice_date: str | None = None ##kept as string here; parsedtodateLater
    total_amount: Decimal
    line_items: List[ExtractedLineItem]
    
    @field_validator("total_amount", mode="before")
    @classmethod
    def parsse_total(cls, v):
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Could not parse '{v}' as a decimal amount") 
             
            