import os
from typing import Dict, Any, List
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_client() -> Client:
    """إرجاع كائن الاتصال بقاعدة البيانات."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

class NotificationService:
    
    @classmethod
    def create_notification(cls, title: str, message: str, alert_type: str = "INFO", 
                            user_id: str = None, branch_id: str = None) -> Dict[str, Any]:
        """
        إنشاء إشعار جديد في قاعدة البيانات وترحيله للـ Realtime.
        أنواع التنبيهات: WARNING, CREDIT, PRICE, INVENTORY, PENDING_PRICE
        """
        supabase = get_supabase_client()
        payload = {
            "title": title,
            "message": message,
            "type": alert_type,
            "user_id": user_id,
            "branch_id": branch_id,
            "is_read": False
        }
        res = supabase.table("notifications").insert(payload).execute()
        return res.data[0] if res.data else {}

    @classmethod
    def notify_missing_price(cls, item_name: str, transaction_id: str, branch_id: str = None) -> Dict[str, Any]:
        """تنبيه عند تسجيل حركة لصنف بدون سعر تكلفة/بيع (unit_price = 0.0)."""
        return cls.create_notification(
            title="⚠️ صنف معلق بدون سعر",
            message=f"تم تسجيل المعاملة ({transaction_id[:8]}) للصنف '{item_name}' بدون سعر. يرجى إدخال السعر لتفعيل القيود المالية ومتوسط التكلفة.",
            alert_type="PENDING_PRICE",
            branch_id=branch_id
        )

    @classmethod
    def notify_credit_warning(cls, customer_name: str, current_debt: float, limit: float, branch_id: str = None) -> Dict[str, Any]:
        """تنبيه تجاوز الحد الائتماني للعميل."""
        return cls.create_notification(
            title="🔴 تجاوز الحد الائتماني",
            message=f"العميل {customer_name} تجاوز الحد الائتماني المسموح ({limit:,.2f} ج.م). إجمالي الديون الحالية: {current_debt:,.2f} ج.م.",
            alert_type="CREDIT",
            branch_id=branch_id
        )

    @classmethod
    def notify_low_stock(cls, item_name: str, remaining_qty: float, branch_id: str = None) -> Dict[str, Any]:
        """تنبيه وصول مخزون صنف للحد الأدنى."""
        return cls.create_notification(
            title="📦 تنبيه نواقص المخزون",
            message=f"رصيد الصنف '{item_name}' أوشك على النفاد. المتبقي حالياً: {remaining_qty}.",
            alert_type="INVENTORY",
            branch_id=branch_id
        )

    @classmethod
    def get_unread_notifications(cls, branch_id: str = None) -> List[Dict[str, Any]]:
        """جلب جميع التنبيهات غير المقروءة للواجهة."""
        supabase = get_supabase_client()
        query = supabase.table("notifications").select("*").eq("is_read", False)
        if branch_id:
            query = query.eq("branch_id", branch_id)
        res = query.order("created_at", desc=True).execute()
        return res.data or []

    @classmethod
    def mark_as_read(cls, notification_id: str) -> bool:
        """تحديث حالة الإشعار إلى مقروء."""
        supabase = get_supabase_client()
        res = supabase.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
        return bool(res.data)
