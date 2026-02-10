"""
Inventory Agent - Manages user pantry and ingredient tracking.
"""
from typing import Optional
from datetime import date, timedelta
from pydantic import BaseModel


class InventoryItem(BaseModel):
    """An item in the user's inventory."""
    ingredient_id: str
    ingredient_name: str
    quantity: float
    unit: str
    expiry_date: Optional[date] = None
    days_until_expiry: Optional[int] = None


class InventoryStatus(BaseModel):
    """Summary of user's inventory status."""
    total_items: int
    expiring_soon: list[InventoryItem]  # Items expiring within 3 days
    expired: list[InventoryItem]


def check_expiry_status(items: list[InventoryItem]) -> InventoryStatus:
    """
    Analyze inventory for expiring items.
    
    Args:
        items: List of inventory items
        
    Returns:
        InventoryStatus with categorized items
    """
    today = date.today()
    expiring_soon = []
    expired = []
    
    for item in items:
        if item.expiry_date:
            days_left = (item.expiry_date - today).days
            item.days_until_expiry = days_left
            
            if days_left < 0:
                expired.append(item)
            elif days_left <= 3:
                expiring_soon.append(item)
    
    return InventoryStatus(
        total_items=len(items),
        expiring_soon=sorted(expiring_soon, key=lambda x: x.days_until_expiry or 0),
        expired=expired,
    )


def format_inventory_alert(status: InventoryStatus) -> str:
    """
    Generate human-readable inventory alert.
    
    Args:
        status: Inventory status
        
    Returns:
        Formatted alert message
    """
    messages = []
    
    if status.expired:
        messages.append("🚨 **Nguyên liệu đã hết hạn:**")
        for item in status.expired:
            messages.append(f"  - {item.ingredient_name}: {item.quantity} {item.unit}")
    
    if status.expiring_soon:
        messages.append("\n⚠️ **Sắp hết hạn (trong 3 ngày):**")
        for item in status.expiring_soon:
            messages.append(
                f"  - {item.ingredient_name}: còn {item.days_until_expiry} ngày"
            )
    
    if not messages:
        messages.append("✅ Tất cả nguyên liệu đều còn hạn sử dụng!")
    
    return "\n".join(messages)
