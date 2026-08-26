from typing import Dict, Any
from core.database import get_supabase_client

class QueryService:

    @classmethod
    def get_comprehensive_report(cls, branch: str, report_type: str) -> Dict[str, Any]:
        """
        استعلامات شاملة ومخصصة حسب رغبة التاجر:
        report_type: (inventory, installments, suppliers, sales_reps)
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
            
        try:
            if report_type == "inventory":
                res = supabase.table("inventory").select("item_name, quantity, price, cost").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "المخزن فارغ حالياً."}
                
                items = [f"- {i['item_name']} (الكمية: {i['quantity']}, السعر: {i['price']}ج)" for i in res.data]
                return {
                    "status": "SUCCESS",
                    "type": "inventory",
                    "data": res.data,
                    "message": f"📦 **تقرير المخزن للفرع ({branch}):**\n" + "\n".join(items)
                }
                
            elif report_type == "installments":
                res = supabase.table("installments").select("customer_name, remaining_amount, due_date").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد أقساط مسجلة حالياً."}
                    
                insts = [f"- العميل: {i['customer_name']} | المتبقي: {i['remaining_amount']}ج | الاستحقاق: {i['due_date']}" for i in res.data]
                return {
                    "status": "SUCCESS",
                    "type": "installments",
                    "data": res.data,
                    "message": f"💳 **متابعة أقساط العملاء:**\n" + "\n".join(insts)
                }
                
            elif report_type == "suppliers":
                res = supabase.table("suppliers_dues").select("supplier_name, total_due, notes").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد مستحقات للموردين مسجلة."}
                    
                sups = [f"- المورد: {i['supplier_name']} | المستحق: {i['total_due']}ج" for i in res.data]
                return {
                    "status": "SUCCESS",
                    "type": "suppliers",
                    "data": res.data,
                    "message": f"🏭 **مستحقات الموردين:**\n" + "\n".join(sups)
                }
                
            elif report_type == "sales_reps":
                res = supabase.table("transactions").select("item_name, quantity, total_price, created_at").eq("branch", branch).eq("type", "sale").execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد مبيعات مسجلة حتى الآن."}
                    
                total_sales = sum(float(i.get("total_price", 0)) for i in res.data)
                return {
                    "status": "SUCCESS",
                    "type": "sales_reps",
                    "data": res.data,
                    "message": f"📊 **إجمالي مبيعات الفرع:** {total_sales} جنيه عبر ({len(res.data)}) حركة بيع."
                }
            else:
                return {"status": "ERROR", "message": "⚠️ نوع التقرير المطلوب غير معروف."}
                
        except Exception as e:
            print(f"Comprehensive query error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء جلب التقارير: {str(e)}"}
