import os
import logging
import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
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
                           installment_value: float, due_date: str, installments_count: int = 1, 
                           interval_days: int = 30, custom_schedules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        تسجيل عملية التقسيط بمرونة تامة:
        - installments_count: عدد الأقساط المتكررة.
        - interval_days: الفاصل الزمني بالأيام (7 للأسبوع، 10، 15، 30 للشهر، إلخ).
        - custom_schedules: قائمة مخصصة للدفعات المؤجلة المختلفة (مثل دفع 200 ألف بعد 3 أشهر و200 ألف بعد 6 أشهر).
        """
        supabase = get_supabase_client()
        if not supabase: return {}
        
        clean_cust = customer_name.strip()
        clean_item = item_name.strip()
        
        try:
            base_date = datetime.strptime(due_date.strip().split("T")[0], "%Y-%m-%d")
            inserted_records = []
            
            # 1. إذا وُجد جدول زمني مخصص (دفعات مؤجلة متباينة مثل 3 شهور و6 شهور)
            if custom_schedules and isinstance(custom_schedules, list):
                for sch in custom_schedules:
                    sch_date = base_date + relativedelta(months=int(sch.get("months_offset", 0)))
                    sch_amount = float(sch.get("amount", 0.0))
                    
                    if sch_amount <= 0:
                        continue
                        
                    payload = {
                        "branch": branch.strip(),
                        "customer_name": clean_cust,
                        "item_name": clean_item,
                        "total_amount": total_amount,
                        "down_payment": down_payment,
                        "remaining_amount": round(sch_amount, 2),
                        "installment_value": round(sch_amount, 2),
                        "due_date": sch_date.strftime("%Y-%m-%d"),
                        "status": "نشط"
                    }
                    res = supabase.table("installments").insert(payload).execute()
                    if res.data:
                        inserted_records.append(res.data[0])
            
            # 2. الأقساط الدورية المنتظمة (سواء باليوم أو الشهر)
            if installments_count > 0 and remaining_amount > 0:
                for i in range(max(1, installments_count)):
                    if interval_days >= 30:
                        # الاعتماد على الشهر بدقة إذا كان الفاصل شهرياً أو أكثر
                        months_to_add = i * (interval_days // 30)
                        current_due_date = base_date + relativedelta(months=months_to_add)
                    else:
                        # الاعتماد على الأيام (أسبوع، 10 أيام، 15 يوم)
                        current_due_date = base_date + timedelta(days=i * interval_days)
                    
                    current_rem = installment_value if i < installments_count - 1 else (remaining_amount - (installment_value * (installments_count - 1)))
                    current_rem = max(0.0, current_rem)
                    
                    if current_rem <= 0:
                        continue
                        
                    status = "نشط"
                    
                    payload = {
                        "branch": branch.strip(),
                        "customer_name": clean_cust,
                        "item_name": clean_item,
                        "total_amount": total_amount,
                        "down_payment": down_payment,
                        "remaining_amount": round(current_rem, 2),
                        "installment_value": round(installment_value, 2),
                        "due_date": current_due_date.strftime("%Y-%m-%d"),
                        "status": status
                    }
                    
                    res = supabase.table("installments").insert(payload).execute()
                    if res.data:
                        inserted_records.append(res.data[0])
                    
            return {
                "status": "SUCCESS",
                "records_count": len(inserted_records),
                "records": inserted_records
            }
        except Exception as e:
            logger.error(f"Record installment error: {e}")
            raise Exception(f"خطأ Supabase الفعلي في الأقساط: {str(e)}")

    @classmethod
    def process_payment(cls, customer_name: str, payment_amount: float, branch: str) -> Dict[str, Any]:
        """تحصيل مبلغ نقدي وترحيل الأقساط المسددة بالكامل إلى جدول الأرشيف تلقائياً."""
        supabase = get_supabase_client()
        if not supabase: return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        try:
            clean_cust = customer_name.strip()
            pending_res = supabase.table("installments").select("*").eq("customer_name", clean_cust).neq("status", "مدفوع").order("due_date", desc=False).execute()
                
            if not pending_res.data:
                return {"status": "NO_DEBT", "message": f"لا يوجد ديون معلقة على العميل {clean_cust}."}
                
            amount_to_apply = payment_amount
            updated_records = []
            
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
                
                # إذا أصبح القسط مسدداً بالكامل، نقوم بنقله للأرشيف وحذفه من النشط
                if new_status == "مدفوع":
                    archive_payload = {**record, "remaining_amount": 0.0, "status": "مدفوع"}
                    archive_payload.pop("id", None) # السماح بإنشاء معرف جديد أو الاحتفاظ بالقديم حسب رغبتك
                    supabase.table("installments_archive").insert(archive_payload).execute()
                    
                    supabase.table("installments").delete().eq("id", record["id"]).execute()
                    updated_records.append({**record, "status": "مدفوع (مؤرشف)"})
                else:
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
            logger.error(f"Process payment & archive error: {e}")
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
