import os
import logging
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime
from supabase import create_client, Client

# إعداد نظام التسجيل (Logging) بدلاً من الطباعة العشوائية
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            clean_cust_name = customer_name.strip()
            limit_res = supabase.table("customer_credit_limits").select("credit_limit").eq("customer_name", clean_cust_name).execute()
            credit_limit = float(limit_res.data[0]["credit_limit"]) if limit_res.data else 10000.0
            
            debt_res = supabase.table("installments").select("remaining_amount").eq("customer_name", clean_cust_name).neq("status", "مدفوع").execute()
            current_debt = sum([float(item["remaining_amount"]) for item in debt_res.data]) if debt_res.data else 0.0
            
            total_projected_debt = current_debt + new_debt_amount
            is_exceeded = total_projected_debt > credit_limit
            
            return {
                "customer_name": clean_cust_name,
                "current_debt": current_debt,
                "credit_limit": credit_limit,
                "total_projected_debt": total_projected_debt,
                "is_exceeded": is_exceeded,
                "warning_message": f"⚠️ تنبيه الائتمان: العميل {clean_cust_name} سيتجاوز الحد الائتماني ({credit_limit:,.2f} ج.م). إجمالي الديون الحالية: {current_debt:,.2f} ج.م" if is_exceeded else ""
            }
        except Exception as e:
            logger.error(f"Credit check error: {e}")
            return {"is_exceeded": False, "warning_message": ""}

    @classmethod
    def set_customer_credit_limit(cls, customer_name: str, new_limit: float, branch: str) -> Dict[str, Any]:
        """تحديث أو إدراج الحد الائتماني للعميل مباشرة من واجهة الشات."""
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        try:
            clean_cust_name = customer_name.strip()
            existing = supabase.table("customer_credit_limits").select("id").eq("customer_name", clean_cust_name).execute()
            
            payload = {
                "customer_name": clean_cust_name,
                "credit_limit": new_limit
            }
            
            if existing.data:
                supabase.table("customer_credit_limits").update({"credit_limit": new_limit}).eq("customer_name", clean_cust_name).execute()
            else:
                supabase.table("customer_credit_limits").insert(payload).execute()
                
            return {
                "status": "SUCCESS",
                "message": f"✅ تم تحديث الحد الائتماني للعميل '{clean_cust_name}' ليصبح {new_limit:,.2f} ج.م بنجاح."
            }
        except Exception as e:
            logger.error(f"Set credit limit error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء تحديث الحد الائتماني: {str(e)}"}

    @classmethod
    def record_installment(cls, branch: str, customer_name: str, item_name: str,
                           total_amount: float, down_payment: float, remaining_amount: float, 
                           installment_value: float, due_date: str) -> Dict[str, Any]:
        """تسجيل عملية التقسيط مع تنظيف المدخلات من المسافات الزائدة."""
        supabase = get_supabase_client()
        if not supabase: return {}
        
        clean_cust = customer_name.strip()
        clean_item = item_name.strip()
        status = "مدفوع" if remaining_amount <= 0 else "نشط"
        
        payload = {
            "branch": branch.strip(),
            "customer_name": clean_cust,
            "item_name": clean_item,
            "total_amount": total_amount,
            "down_payment": down_payment,
            "remaining_amount": remaining_amount,
            "installment_value": installment_value,
            "due_date": due_date.strip(),
            "status": status
        }
        try:
            res = supabase.table("installments").insert(payload).execute()
            return res.data[0] if res.data else {}
        except Exception as e:
            logger.error(f"Record installment error: {e}")
            raise Exception(f"خطأ Supabase الفعلي في الأقساط: {str(e)}")

    @classmethod
    def process_payment(cls, customer_name: str, payment_amount: float, branch: str) -> Dict[str, Any]:
        """تحصيل مبلغ نقدي لسداد ديون سابقة مع حفظ التناسق الآمن (Simulation for Transaction Integrity)."""
        supabase = get_supabase_client()
        if not supabase: return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        try:
            clean_cust = customer_name.strip()
            pending_res = supabase.table("installments").select("*").eq("customer_name", clean_cust).neq("status", "مدفوع").order("created_at", desc=False).execute()
                
            if not pending_res.data:
                return {"status": "NO_DEBT", "message": f"لا يوجد ديون معلقة على العميل {clean_cust}."}
                
            amount_to_apply = payment_amount
            updated_records = []
            backup_states = [] # الاحتفاظ بنسخة للرجوع إليها في حال حدوث خطأ طارئ
            
            for record in pending_res.data:
                backup_states.append({"id": record["id"], "remaining_amount": record["remaining_amount"], "status": record["status"]})
                
            try:
                for record in pending_res.data:
                    if amount_to_apply <= 0:
                        break
                        
                    rem = float(record["remaining_amount"])
                    if amount_to_apply >= rem:
                        amount_to_apply -= rem
                        new_rem = 0.0
                        new_status = "مدفوع"
                    else:
                        new_rem = rem - amount_to_apply
                        amount_to_apply = 0.0
                        new_status = "جزئي"
                        
                    upd = supabase.table("installments").update({"remaining_amount": new_rem, "status": new_status}).eq("id", record["id"]).execute()
                    if upd.data:
                        updated_records.append(upd.data[0])
            except Exception as inner_err:
                # عملية الاسترجاع الاحترازي (Rollback Manual Simulation) في حال فشل التحديث وسط الحلقة
                logger.error(f"Payment loop failed, rolling back states: {inner_err}")
                for b in backup_states:
                    supabase.table("installments").update({"remaining_amount": b["remaining_amount"], "status": b["status"]}).eq("id", b["id"]).execute()
                raise inner_err
                    
            return {
                "status": "SUCCESS",
                "applied_amount": payment_amount - amount_to_apply,
                "remaining_unapplied": amount_to_apply,
                "updated_records": updated_records
            }
        except Exception as e:
            logger.error(f"Process payment error: {e}")
            return {"status": "ERROR", "message": f"فشل المعاملة المالية: {str(e)}"}

    @classmethod
    def get_branch_debts_summary(cls, branch: str) -> List[Dict[str, Any]]:
        """استخراج كشف حساب الديون والأقساط المستحقة للفرع."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            res = supabase.table("installments").select("*").eq("branch", branch.strip()).neq("status", "مدفوع").order("created_at", desc=True).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Get debts summary error: {e}")
            return []

    @classmethod
    def get_installments_by_month_or_customer(cls, branch: str, target_month: Optional[int] = None, customer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """فلترة وجلب الأقساط بدقة عالية وسريعة مع معالجة المسافات."""
        supabase = get_supabase_client()
        if not supabase: return []
        
        try:
            clean_branch = branch.strip()
            query = supabase.table("installments").select("*").eq("branch", clean_branch).neq("status", "مدفوع")
            
            if customer_name:
                clean_cust = customer_name.strip()
                query = query.ilike("customer_name", f"%{clean_cust}%")
                
            res = query.execute()
            rows = res.data or []
            
            if not target_month:
                return rows
                
            filtered = []
            for r in rows:
                due_date_str = str(r.get("due_date", "")).strip()
                try:
                    if "-" in due_date_str:
                        dt_obj = datetime.strptime(due_date_str.split("T")[0], "%Y-%m-%d")
                        if dt_obj.month == int(target_month):
                            filtered.append(r)
                    elif f"-{str(target_month).zfill(2)}-" in due_date_str or due_date_str.startswith(f"{target_month}-"):
                        filtered.append(r)
                except Exception:
                    if f"-{target_month}-" in due_date_str or f"/{target_month}/" in due_date_str:
                        filtered.append(r)
            return filtered
            
        except Exception as e:
            logger.error(f"Error filtering installments: {e}")
            return []

    @classmethod
    def get_monthly_installments_with_arrears(cls, branch: str, customer_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """جلب الأقساط المستحقة والمتراكمة للفرع والعميل."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            clean_branch = branch.strip()
            query = supabase.table("installments").select("*").eq("branch", clean_branch).neq("status", "مدفوع")
            if customer_name:
                query = query.eq("customer_name", customer_name.strip())
            
            res = query.order("due_date", desc=False).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error fetching installments with arrears: {e}")
            return []

    @classmethod
    def get_due_installments_for_alerts(cls, branch: str) -> List[Dict[str, Any]]:
        """جلب الأقساط المستحقة والمتأخرة لعرضها في الإشعارات."""
        supabase = get_supabase_client()
        if not supabase: return []
        try:
            today_str = datetime.today().date().isoformat()
            
            res = supabase.table("installments") \
                .select("*") \
                .eq("branch", branch.strip()) \
                .neq("status", "مدفوع") \
                .lte("due_date", today_str) \
                .order("due_date", desc=False) \
                .execute()
                
            return res.data or []
        except Exception as e:
            logger.error(f"Error fetching due installments for alerts: {e}")
            return []
