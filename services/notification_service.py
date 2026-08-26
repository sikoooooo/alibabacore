import os
from typing import Dict, Any, List, Optional
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_client() -> Optional[Client]:
    """إرجاع كائن الاتصال بقاعدة البيانات بشكل آمن."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None

class NotificationService:
    
    @classmethod
    def create_notification(
        cls, 
        title: str, 
        message: str, 
        alert_type: str = "INFO", 
        user_id: Optional[str] = None, 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """إنشاء إشعار جديد في قاعدة البيانات وترحيله للـ Realtime."""
        target_branch = branch_id or branch
        client = get_supabase_client()
        if not client:
            return {}
        try:
            payload = {
                "title": title,
                "message": message,
                "type": alert_type,
                "user_id": user_id,
                "branch_id": target_branch,
                "branch": target_branch,
                "is_read": False
            }
            res = client.table("notifications").insert(payload).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            print(f"Error creating notification: {e}")
            return {}

    @classmethod
    def notify_slow_moving(
        cls, 
        item_name: str, 
        days_inactive: int, 
        current_qty: float, 
        marketing_suggestion: str = "", 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """تنبيه بالبضائع الراكدة مصحوباً باقتراح تسويقي من الـ AI."""
        target_branch = branch_id or branch
        return cls.create_notification(
            title="💡 تنبيه صنف راكد + اقتراح تسويقي",
            message=f"الصنف '{item_name}' لم يتحرك منذ {days_inactive} يوماً (الرصيد: {current_qty}).\n💡 اقتراح النظام: {marketing_suggestion}",
            alert_type="SLOW_MOVING",
            branch_id=target_branch
        )

    @classmethod
    def notify_missing_price(
        cls, 
        item_name: str, 
        transaction_id: str = "", 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """تنبيه عند تسجيل حركة لصنف بدون سعر تكلفة/بيع."""
        target_branch = branch_id or branch
        tx_ref = f" ({transaction_id[:8]})" if transaction_id else ""
        return cls.create_notification(
            title="⚠️ صنف معلق بدون سعر",
            message=f"تم تسجيل المعاملة{tx_ref} للصنف '{item_name}' بدون سعر. يرجى إدخال السعر لتفعيل القيود المالية ومتوسط التكلفة.",
            alert_type="PENDING_PRICE",
            branch_id=target_branch
        )

    @classmethod
    def notify_credit_warning(
        cls, 
        customer_name: str, 
        current_debt: float, 
        limit: float, 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """تنبيه تجاوز الحد الائتماني للعميل."""
        target_branch = branch_id or branch
        return cls.create_notification(
            title="🔴 تجاوز الحد الائتماني",
            message=f"العميل {customer_name} تجاوز الحد الائتماني المسموح ({limit:,.2f} ج.م). إجمالي الديون الحالية: {current_debt:,.2f} ج.م.",
            alert_type="CREDIT",
            branch_id=target_branch
        )

    @classmethod
    def notify_low_stock(
        cls, 
        item_name: str, 
        remaining_qty: float, 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> Dict[str, Any]:
        """تنبيه وصول مخزون صنف للحد الأدنى."""
        target_branch = branch_id or branch
        return cls.create_notification(
            title="📦 تنبيه نواقص المخزون",
            message=f"رصيد الصنف '{item_name}' أوشك على النفاد. المتبقي حالياً: {remaining_qty}.",
            alert_type="INVENTORY",
            branch_id=target_branch
        )

    @classmethod
    def get_smart_alerts(cls, branch: str) -> Dict[str, Any]:
        """جلب الإشعارات الذكية غير المقروءة والمنسقة للفرع."""
        unread = cls.get_unread_notifications(branch=branch)
        if not unread:
            return {"status": "SUCCESS", "message": "✅ لا توجد تنبيهات جديدة حالياً."}
        
        formatted_msgs = [f"- [{item['title']}] {item['message']}" for item in unread]
        return {
            "status": "SUCCESS",
            "count": len(unread),
            "message": "🔔 **التنبيهات المعلقة:**\n\n" + "\n".join(formatted_msgs)
        }

    @classmethod
    def get_unread_notifications(
        cls, 
        branch_id: Optional[str] = None,
        branch: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """جلب جميع التنبيهات غير المقروءة للواجهة."""
        target_branch = branch_id or branch
        client = get_supabase_client()
        if not client:
            return []
        try:
            query = client.table("notifications").select("*").eq("is_read", False)
            if target_branch:
                query = query.eq("branch_id", target_branch)
            res = query.order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"Error fetching notifications: {e}")
            return []

    @classmethod
    def mark_as_read(cls, notification_id: str) -> bool:
        """|تحديث حالة الإشعار إلى مقروء."""
        client = get_supabase_client()
        if not client:
            return False
        try:
            res = client.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()
            return bool(res.data)
        except Exception as e:
            print(f"Error marking notification as read: {e}")
            return False
