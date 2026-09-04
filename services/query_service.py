from typing import Dict, Any
from core.database import get_supabase_client

class QueryService:
    @classmethod
    def get_comprehensive_report(cls, branch: str, report_type: str) -> Dict[str, Any]:
        """
        استعلامات شاملة ومخصصة ومفصولة هندسياً حسب رغبة التاجر:
        report_type: (inventory, installments, suppliers, sales_reps, expenses, assets)
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        try:
            if report_type == "inventory":
                # استرجاع البضائع المخزنية الحقيقية فقط (باستبعاد المصروفات والأصول والقروض)
                res = supabase.table("inventory").select("item_name, total_base_quantity, avg_cost_per_base, major_unit").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "المخزن فارغ حالياً."}
                
                # تصفية البضائع التي تسجلت خطأ كمصروفات أو أصول بالخطأ سابقاً
                filtered_items = [
                    i for i in res.data 
                    if not any(kw in i['item_name'].lower() for kw in ["رواتب", "صيانة", "قرض", "أصل", "جهاز"])
                ]
                
                if not filtered_items:
                    return {"status": "SUCCESS", "message": "لا توجد أصناف مخزنية حقيقية حالياً (المخزن الصافي نظيف)."}

                items = [f"- {i['item_name']} (الرصيد: {i['total_base_quantity']} {i.get('major_unit', 'وحدة')}, التكلفة: {i['avg_cost_per_base']}ج)" for i in filtered_items]
                return {
                    "status": "SUCCESS", 
                    "type": "inventory", 
                    "data": filtered_items, 
                    "message": f"📦 **تقرير المخزن الصافي للفرع ({branch}):**\n" + "\n".join(items)
                } 

            elif report_type == "installments":
                res = supabase.table("installments").select("customer_name, remaining_amount, due_date").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد أقساط مسجلة حالياً."}
                insts = [f"- العميل: {i['customer_name']} | المتبقي: {i['remaining_amount']}ج | الاستحقاق: {i.get('due_date', 'غير محدد')}" for i in res.data]
                return {
                    "status": "SUCCESS", 
                    "type": "installments", 
                    "data": res.data, 
                    "message": f"💳 **متابعة أقساط العملاء والذمم:**\n" + "\n".join(insts)
                } 

            elif report_type == "suppliers":
                res = supabase.table("suppliers").select("supplier_name, current_balance, phone").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد مستحقات للموردين مسجلة."}
                sups = [f"- المورد: {i['supplier_name']} | الرصيد الدائن: {i['current_balance']}ج" for i in res.data]
                return {
                    "status": "SUCCESS", 
                    "type": "suppliers", 
                    "data": res.data, 
                    "message": f"🏭 **مستحقات الموردين المستقلة:**\n" + "\n".join(sups)
                } 

            elif report_type == "sales_reps":
                res = supabase.table("transactions").select("item_name, quantity, unit_price, type, created_at").eq("branch", branch).ilike("type", "%sale%").execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد مبيعات مسجلة حتى الآن."}
                total_sales = sum(float(i.get("quantity", 0)) * float(i.get("unit_price", 0)) for i in res.data)
                return {
                    "status": "SUCCESS", 
                    "type": "sales_reps", 
                    "data": res.data, 
                    "message": f"📊 **إجمالي مبيعات وأرباح الفرع:** {total_sales} جنيه عبر ({len(res.data)}) حركة بيع."
                } 
            else:
                return {"status": "ERROR", "message": "⚠️ نوع التقرير المطلوب غير معروف."}

        except Exception as e:
            print(f"Comprehensive query error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء جلب التقارير: {str(e)}"}
