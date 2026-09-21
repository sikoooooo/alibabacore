from typing import Dict, Any
from core.database import get_supabase_client

class QueryService:
    @classmethod
    def get_comprehensive_report(cls, branch: str, report_type: str) -> Dict[str, Any]:
        """
        استعلامات شاملة ومخصصة ومفصولة هندسياً لبرنامج نافع:
        report_type: (inventory, installments, suppliers, sales_reps, expenses, assets)
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        try:
            if report_type == "inventory":
                # استرجاع البضائع المخزنية الحقيقية فقط (باستبعاد المصروفات والأصول والقروض)
                res = supabase.table("inventory").select("item_name, total_base_quantity, avg_cost_per_base, major_unit, selling_price").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "المخزن فارغ حالياً."}
                
                # تصفية البضائع التي تسجلت كمصروفات أو أصول بالخطأ سابقاً
                filtered_items = [
                    i for i in res.data 
                    if not any(kw in i['item_name'].lower() for kw in ["رواتب", "صيانة", "قرض", "أصل", "جهاز"])
                ]
                
                if not filtered_items:
                    return {"status": "SUCCESS", "message": "لا توجد أصناف مخزنية حقيقية حالياً (المخزن الصافي نظيف)."}

                items = [
                    f"- {i['item_name']} (الرصيد: {i['total_base_quantity']} {i.get('major_unit', 'وحدة')}, التكلفة: {i['avg_cost_per_base']}ج, سعر البيع: {i.get('selling_price', 0)}ج)"
                    for i in filtered_items
                ]
                return {
                    "status": "SUCCESS", 
                    "type": "inventory", 
                    "data": filtered_items, 
                    "message": f"📦 **تقرير المخزن الصافي لبرنامج نافع - فرع ({branch}):**\n" + "\n".join(items)
                } 

            elif report_type == "installments":
                res = supabase.table("installments").select("customer_name, item_name, remaining_amount, due_date, status").eq("branch", branch).execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد أقساط مسجلة حالياً."}
                insts = [f"- العميل: {i['customer_name']} | الصنف: {i.get('item_name', 'غير محدد')} | المتبقي: {i['remaining_amount']}ج | الاستحقاق: {i.get('due_date', 'غير محدد')}" for i in res.data]
                return {
                    "status": "SUCCESS", 
                    "type": "installments", 
                    "data": res.data, 
                    "message": f"💳 **متابعة أقساط العملاء والذمم (فرع {branch}):**\n" + "\n".join(insts)
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
                    "message": f"🏭 **مستحقات الموردين المستقلة (فرع {branch}):**\n" + "\n".join(sups)
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
                    "message": f"📊 **إجمالي مبيعات فرع ({branch}):** {total_sales:,.2f} جنيه عبر ({len(res.data)}) حركة بيع."
                } 

            elif report_type == "expenses":
                res = supabase.table("treasury_ledger").select("*").eq("branch", branch).ilike("description", "%مصروف%").execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد مصروفات مسجلة حالياً."}
                total_exp = sum(float(i.get("amount", 0)) for i in res.data)
                items = [f"- {i.get('description')}: {float(i.get('amount', 0)):,.2f}ج" for i in res.data]
                return {
                    "status": "SUCCESS",
                    "type": "expenses",
                    "data": res.data,
                    "message": f"💸 **تقرير المصروفات التشغيلية لفرع ({branch}):**\nإجمالي المصروفات: {total_exp:,.2f} جنيه\n" + "\n".join(items)
                }

            elif report_type == "assets":
                res = supabase.table("treasury_ledger").select("*").eq("branch", branch).ilike("description", "%أصل ثابت%").execute()
                if not res.data:
                    return {"status": "SUCCESS", "message": "لا توجد أصول ثابتة مسجلة حالياً."}
                total_assets = sum(float(i.get("amount", 0)) for i in res.data)
                items = [f"- {i.get('description')}: {float(i.get('amount', 0)):,.2f}ج" for i in res.data]
                return {
                    "status": "SUCCESS",
                    "type": "assets",
                    "data": res.data,
                    "message": f"🏛️ **تقرير الأصول الثابتة لفرع ({branch}):**\nإجمالي قيمة الأصول: {total_assets:,.2f} جنيه\n" + "\n".join(items)
                }

            else:
                return {"status": "ERROR", "message": "⚠️ نوع التقرير المطلوب غير معروف."}

        except Exception as e:
            print(f"Comprehensive query error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء جلب التقارير: {str(e)}"}

    @classmethod
    def get_customer_installments(cls, branch: str, customer_name: str) -> Dict[str, Any]:
        """
        استعلام مخصص لجلب جدول الأقساط والذمم الخاصة بعميل معين بالاسم من جدول installments بتركيز تجمعي.
        """
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        try:
            response = supabase.table("installments")\
                .select("*")\
                .eq("branch", branch)\
                .ilike("customer_name", f"%{customer_name}%")\
                .execute()
                
            records = response.data if response.data else []
            if not records:
                return {"status": "EMPTY", "message": f"لا توجد أقساط مسجلة حالياً للعميل: {customer_name}"}
                
            report_lines = [f"📊 **جدول أقساط العميل ({customer_name}) - فرع ({branch}):**\n"]
            for r in records:
                report_lines.append(
                    f"- **الصنف:** {r.get('item_name')}\n"
                    f"  * إجمالي الفاتورة: {float(r.get('total_amount', 0)):,.2f} ج.م | المقدم: {float(r.get('down_payment', 0)):,.2f} ج.م\n"
                    f"  * المتبقي: **{float(r.get('remaining_amount', 0)):,.2f} ج.م** | قيمة القسط: {float(r.get('installment_value', 0)):,.2f} ج.م\n"
                    f"  * تاريخ الاستحقاق: {r.get('due_date')} | الحالة: `{r.get('status')}`\n"
                    f"-----------------------------------"
                )
            return {
                "status": "SUCCESS", 
                "type": "customer_installments", 
                "data": records, 
                "message": "\n".join(report_lines)
            }
        except Exception as e:
            return {"status": "ERROR", "message": f"خطأ في جلب أقساط العميل: {str(e)}"}
