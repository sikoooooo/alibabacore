import os
import streamlit as st
from typing import Dict, Any, List, Optional
from supabase import create_client, Client

def get_supabase_client() -> Optional[Client]:
    """إرجاع كائن الاتصال بقاعدة البيانات بأمان عالي لدعم Streamlit Cloud"""
    try:
        from core.database import supabase
        if supabase:
            return supabase
    except Exception:
        pass
        
    url = getattr(st, "secrets", {}).get("SUPABASE_URL") or getattr(st, "secrets", {}).get("supabase_url") or os.getenv("SUPABASE_URL", "")
    key = getattr(st, "secrets", {}).get("SUPABASE_KEY") or getattr(st, "secrets", {}).get("supabase_key") or os.getenv("SUPABASE_KEY", "")
    
    if not url or not key:
        return None
    return create_client(url, key)

class InstallmentService:
    
    @classmethod
    def check_customer_credit(cls, customer_name: str, new_debt_amount: float) -> Dict[str, Any]:
        """التحقق مما إذا كان العميل يتجاوز الحد الائتماني المسموح به."""
        supabase = get_supabase_client()
        if not supabase:
            return {"is_exceeded": False, "warning_message": "⚠️ تعذر الاتصال بقاعدة البيانات للتحقق من الائتمان."}
        
        try:
            # 1. جلب الحد الائتماني للعميل (الافتراضي 10,000 ج.م)
            limit_res = supabase.table("customer_credit_limits").select("credit_limit").eq("customer_name", customer_name).execute()
            credit_limit = float(limit_res.data[0]["credit_limit"]) if limit_res.data else 10000.0
            
            # 2. حساب إجمالي الديون الحالية المتبقية على العميل
            debt_res = supabase.table("installments").select("remaining_amount").eq("customer_name", customer_name).neq("status", "PAID").execute()
            current_debt = sum([float(item["remaining_amount"]) for item in debt_res.data]) if debt_res.data else 0.0
            
            total_projected_debt = current_debt + new_debt_amount
            is_exceeded = total_projected_debt > credit_limit
            
            return {
                "customer_name": customer_name,
                "current_debt": current_debt,
                "credit_limit": credit_limit,
                "total_projected_debt": total_projected_debt,
                "is_exceeded": is_exceeded,
                "warning_message": f"⚠️ تنبيه الائتمان: العميل {customer_name} سيتجاوز الحد الائتماني ({credit_limit:,.2f} ج.م). إجمالي الديون الحالية: {current_debt:,.2f} ج.م" if is_exceeded else ""
            }
        except Exception as e:
            print(f"Credit check error: {e}")
            return {"is_exceeded": False, "warning_message": ""}

    @classmethod
    def set_customer_credit_limit(cls, customer_name: str, new_limit: float, branch: str) -> Dict[str, Any]:
        """تحديث أو إدراج الحد الائتماني للعميل مباشرة من واجهة الشات دون الحاجة للوحة تحكم Supabase."""
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        try:
            existing = supabase.table("customer_credit_limits").select("id").eq("customer_name", customer_name).execute()
            
            payload = {
                "customer_name": customer_name,
                "credit_limit": new_limit,
                "branch": branch
            }
            
            if existing.data:
                supabase.table("customer_credit_limits").update({"credit_limit": new_limit}).eq("customer_name", customer_name).execute()
            else:
                supabase.table("customer_credit_limits").insert(payload).execute()
                
            return {
                "status": "SUCCESS",
                "message": f"✅ تم تحديث الحد الائتماني للعميل '{customer_name}' ليصبح {new_limit:,.2f} ج.م بنجاح."
            }
        except Exception as e:
            print(f"Set credit limit error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء تحديث الحد الائتماني: {str(e)}"}

    @classmethod
    def record_installment(cls, transaction_id: str, branch: str, customer_name: str, 
                           total_amount: float, down_payment: float, remaining_amount: float, 
                           due_date: str) -> Dict[str, Any]:
        """تسجيل عملية بيع آجل / تقسيط جديدة في جدول الأقساط."""
        supabase = get_supabase_client()
        if not supabase: return {}
        
        status = "PAID" if remaining_amount <= 0 else "PENDING"
        payload = {
            "transaction_id": transaction_id,
            "branch": branch,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "down_payment": down_payment,
            "remaining_amount": remaining_amount,
            "due_date": due_date,
            "status": status
        }
        try:
            res = supabase.table("installments").insert(payload).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            print(f"Record installment error: {e}")
            return {}

    @classmethod
    def process_payment(cls, customer_name: str, payment_amount: float, branch: str) -> Dict[str, Any]:
        """تحصيل مبلغ نقدي لسداد ديون سابقة لعميل (خصم من أقدم قسط)."""
        supabase = get_supabase_client()
        if not supabase: return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        try:
            pending_res = supabase.table("installments").select("*").eq("customer_name", customer_name).neq("status", "PAID").order("created_at", desc=False).execute()
                
            if not pending_res.data:
                return {"status": "NO_DEBT", "message": f"لا يوجد ديون معلقة على العميل {customer_name}."}
                
            amount_to_apply = payment_amount
            updated_records = []
            
            for record in pending_res.data:
                if amount_to_apply <= 0:
                    break
                    
                rem = float(record["remaining_amount"])
                if amount_to_apply >= rem:
                    amount_to_apply -= rem
                    new_rem = 0.0
                    new_status = "PAID"
                else:
                    new_rem = rem - amount_to_apply
                    amount_to_apply = 0.0
                    new_status = "PARTIAL"
                    
                upd = supabase.table("installments").update({"remaining_amount": new_rem, "status": new_status}).eq("id", record["id"]).execute()
                if upd.data:
                    updated_records.append(upd.data[0])
                    
            return {
                "status": "SUCCESS",
                "applied_amount": payment_amount - amount_to_apply,
                "remaining_unapplied": amount_to_apply,
                "updated_records": updated_records
            }
        except Exception as e:
            print(f"Process payment error: {e}")
            return {"status": "ERROR"}

    @classmethod
    def get_branch_debts_summary(cls, branch: str) -> List[Dict[str, Any]]:
        """استخراج كشف حساب الديون والأقساط المستحقة للفرع."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            res = supabase.table("installments").select("*").eq("branch", branch).neq("status", "PAID").order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            print(f"Get debts summary error: {e}")
            return []

    @classmethod
    def get_monthly_installments_with_arrears(cls, branch: str, customer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """جلب الأقساط المستحقة والمتراكمة (القديمة والجديدة مجمعة تحت اسم العميل مع ترحيل المتأخرات)."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            query = supabase.table("installments").select("*").eq("branch", branch).neq("status", "PAID")
            if customer_name:
                query = query.eq("customer_name", customer_name)
            
            res = query.order("due_date", desc=False).execute()
            return res.data or []
        except Exception as e:
            print(f"Error fetching installments with arrears: {e}")
            return []

    @classmethod
    def get_due_installments_for_alerts(cls, branch: str) -> List[Dict[str, Any]]:
        """جلب الأقساط المستحقة والمتأخرة التي لم تُسدد بعد (من الأيام السابقة وحتى اليوم) لعرضها في الإشعارات."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            from datetime import date
            today_str = date.today().isoformat()
            
            res = supabase.table("installments") \
                .select("*") \
                .eq("branch", branch) \
                .neq("status", "PAID") \
                .lte("due_date", today_str) \
                .order("due_date", desc=False) \
                .execute()
                
            return res.data or []
        except Exception as e:
            print(f"Error fetching due installments for alerts: {e}")
            return []
