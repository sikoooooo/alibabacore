from core.database import supabase, db_manager

class InventoryService:
    @staticmethod
    def execute_transaction(branch: str, parsed_data: dict, raw_text: str):
        try:
            trans_type = parsed_data.get("type", "SALE")
            item_name = parsed_data.get("item_name", "غير محدد")
            
            # معالجة آمنة للأرقام
            try:
                input_qty = float(parsed_data.get("quantity", 1))
            except Exception:
                input_qty = 1.0
                
            try:
                unit_price = float(parsed_data.get("unit_price", 0))
            except Exception:
                unit_price = 0.0

            total_amount = input_qty * unit_price

            # جلب معرفات الشركة والفرع
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch)
            if not company_id or not branch_id:
                return False, "فشل في الاتصال بهيكل الشركة والفروع في قاعدة البيانات."

            # جلب اسم الشركة النصي صراحة للمحاسب القانوني
            company_name = "الشركة الافتراضية العامة"
            try:
                comp_res = supabase.table("companies").select("name").eq("id", company_id).execute()
                if comp_res.data:
                    company_name = comp_res.data[0].get("name", "الشركة الافتراضية العامة")
            except Exception:
                pass

            # 1. تسجيل الحركة الأساسية في جدول transactions
            supabase.table("transactions").insert({
                "company_id": company_id, 
                "branch_id": branch_id, 
                "branch": branch,
                "type": trans_type, 
                "item_name": item_name, 
                "input_quantity": input_qty,
                "unit_price": unit_price, 
                "total_amount": total_amount, 
                "raw_text": raw_text
            }).execute()

            # 2. تسجيل القيد المحاسبي المزدوج مع الأسماء النصية الصريحة للمحاسب القانوني
            if trans_type == "PURCHASE":
                description = f"قيد شراء صنف ({item_name}) - مدين: المخزون / دائن: النقدية أو الموردين"
            else:
                description = f"قيد بيع صنف ({item_name}) - مدين: النقدية أو العملاء / دائن: المبيعات"

            supabase.table("journal_entries").insert({
                "company_id": company_id, 
                "branch_id": branch_id,
                "company_name": company_name,
                "branch_name": branch,
                "description": description, 
                "total_amount": total_amount
            }).execute()

            # 3. تحديث المخزن (إضافة أو خصم)
            existing = supabase.table("inventory").select("*").eq("branch", branch).eq("item_name", item_name).execute()
            if existing.data:
                current_total = float(existing.data[0].get("total_base_quantity", 0))
                new_total = current_total - input_qty if trans_type == "SALE" else current_total + input_qty
                supabase.table("inventory").update({"total_base_quantity": new_total}).eq("branch", branch).eq("item_name", item_name).execute()
            else:
                initial_total = input_qty if trans_type == "PURCHASE" else -input_qty
                supabase.table("inventory").insert({
                    "branch": branch, 
                    "item_name": item_name, 
                    "total_base_quantity": initial_total, 
                    "avg_cost_per_base": unit_price
                }).execute()
                
            return True, "تم تسجيل الحركة والقيود المحاسبية بأسماء واضحة للمحاسب بنجاح"
            
        except Exception as e:
            return False, str(e)
