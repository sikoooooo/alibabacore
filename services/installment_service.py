import os
from typing import Dict, Any, List
from supabase import create_client, Client

# تهيئة الاتصال بـ Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_client() -> Client:
    """إرجاع كائن الاتصال بقاعدة البيانات."""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

class InstallmentService:
    
    @classmethod
    def check_customer_credit(cls, customer_name: str, new_debt_amount: float) -> Dict[str, Any]:
        """
        التحقق مما إذا كان العميل يتجاوز الحد الائتماني المسموح به.
        """
        supabase = get_supabase_client()
        
        # 1. جلب الحد الائتماني للعميل (الافتراضي 10,000 ج.م إن لم يحدد)
        limit_res = supabase.table("customer_credit_limits")\
            .select("credit_limit")\
            .eq("customer_name", customer_name)\
            .execute()
        
        credit_limit = limit_res.data[0]["credit_limit"] if limit_res.data else 10000.0
        
        # 2. حساب إجمالي الديون الحالية المتبقية على العميل
        debt_res = supabase.table("installments")\
            .select("remaining_amount")\
            .eq("customer_name", customer_name)\
            .neq("status", "PAID")\
            .execute()
            
        current_debt = sum([item["remaining_amount"] for item in debt_res.data]) if debt_res.data else 0.0
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

    @classmethod
    def record_installment(cls, transaction_id: str, branch: str, customer_name: str, 
                           total_amount: float, down_payment: float, remaining_amount: float, 
                           due_date: str) -> Dict[str, Any]:
        """
        تسجيل عملية بيع آجل / تقسيط جديدة في جدول الأقساط.
        """
        supabase = get_supabase_client()
        
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
        
        res = supabase.table("installments").insert(payload).execute()
        return res.data[0] if res.data else {}

    @classmethod
    def process_payment(cls, customer_name: str, payment_amount: float, branch: str) -> Dict[str, Any]:
        """
        تحصيل مبلغ نقدي لسداد ديون سابقة لعميل (خصم من أقدم قسط).
        """
        supabase = get_supabase_client()
        
        # جلب الأقساط المعلقة مرتبة من الأقدم للأحدث
        pending_res = supabase.table("installments")\
            .select("*")\
            .eq("customer_name", customer_name)\
            .neq("status", "PAID")\
            .order("created_at", desc=False)\
            .execute()
            
        if not pending_res.data:
            return {"status": "NO_DEBT", "message": f"لا يوجد ديون معلقة على العميل {customer_name}."}
            
        amount_to_apply = payment_amount
        updated_records = []
        
        for record in pending_res.data:
            if amount_to_apply <= 0:
                break
                
            rem = record["remaining_amount"]
            if amount_to_apply >= rem:
                amount_to_apply -= rem
                new_rem = 0.0
                new_status = "PAID"
            else:
                new_rem = rem - amount_to_apply
                amount_to_apply = 0.0
                new_status = "PARTIAL"
                
            upd = supabase.table("installments")\
                .update({"remaining_amount": new_rem, "status": new_status})\
                .eq("id", record["id"])\
                .execute()
                
            if upd.data:
                updated_records.append(upd.data[0])
                
        return {
            "status": "SUCCESS",
            "applied_amount": payment_amount - amount_to_apply,
            "remaining_unapplied": amount_to_apply,
            "updated_records": updated_records
        }

    @classmethod
    def get_branch_debts_summary(cls, branch: str) -> List[Dict[str, Any]]:
        """
        استخراج كشف حساب الديون والأقساط المستحقة للفرع.
        """
        supabase = get_supabase_client()
        res = supabase.table("installments")\
            .select("*")\
            .eq("branch", branch)\
            .neq("status", "PAID")\
            .order("created_at", desc=True)\
            .execute()
        return res.data or []
