from core.database import supabase, db_manager
from datetime import datetime

class InventoryService:
    @staticmethod
    def execute_transaction(branch: str, parsed: dict, user_text: str):
        try:
            # 1. التأكد من وجود الشركة والفرع والحصول على الـ IDs الخاصة بهم
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch)
            if not company_id or not branch_id:
                return False, "فشل في جلب أو إنشاء بيانات الفرع والشركة في قاعدة البيانات."

            trans_type = parsed.get("type") # PURCHASE أو SALE
            item_name = parsed.get("item_name", "غير محدد")
            brand = parsed.get("brand", "غير محدد")
            supplier = parsed.get("supplier", "غير محدد")
            quantity = float(parsed.get("quantity", 1.0))
            unit = parsed.get("unit", "وحدة")
            unit_price = float(parsed.get("unit_price", 0.0))
            total_amount = quantity * unit_price
            
            is_installment = parsed.get("is_installment", False)
            down_payment = float(parsed.get("down_payment", 0.0))
            installment_value = float(parsed.get("installment_value", 0.0))

            # 2. تسجيل المعاملة في جدول transactions
            trans_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch": branch,
                "type": trans_type,
                "item_name": item_name,
                "brand": brand,
                "supplier_customer": supplier,
                "quantity": quantity,
                "unit": unit,
                "unit_price": unit_price,
                "total_amount": total_amount,
                "raw_text": user_text,
                "created_at": datetime.utcnow().isoformat()
            }
            
            trans_res = supabase.table("transactions").insert(trans_data).execute()
            if not trans_res.data:
                return False, "فشل حفظ المعاملة في جدول transactions."

            # 3. تسجيل قيد اليومية في journal_entries
            journal_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch_name": branch,
                "description": f"{'مبيعات' if trans_type == 'SALE' else 'مشتريات'} صنف {item_name} - {supplier}",
                "amount": total_amount,
                "entry_type": trans_type,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("journal_entries").insert(journal_data).execute()

            # 4. تحديث أو إضافة الصنف في المخزن (inventory)
            inv_query = supabase.table("inventory").select("*").eq("branch", branch).eq("item_name", item_name).execute()
            if inv_query.data:
                current_qty = float(inv_query.data[0].get("quantity", 0.0))
                new_qty = (current_qty + quantity) if trans_type == "PURCHASE" else (current_qty - quantity)
                supabase.table("inventory").update({"quantity": new_qty}).eq("branch", branch).eq("item_name", item_name).execute()
            else:
                initial_qty = quantity if trans_type == "PURCHASE" else -quantity
                supabase.table("inventory").insert({
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch": branch,
                    "item_name": item_name,
                    "brand": brand,
                    "quantity": initial_qty,
                    "unit": unit
                }).execute()

            # 5. إذا كانت المعاملة تقسيط، يتم تسجيلها في جدول installments
            if is_installment:
                remaining_amount = total_amount - down_payment
                inst_data = {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch": branch,
                    "customer_name": supplier,
                    "item_name": item_name,
                    "total_amount": total_amount,
                    "down_payment": down_payment,
                    "remaining_amount": remaining_amount,
                    "installment_value": installment_value,
                    "status": "نشط",
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("installments").insert(inst_data).execute()

            return True, f"تم تنفيذ المعاملة وحفظها بنجاح في قاعدة البيانات! (الإجمالي: {total_amount:,.2f} ج.م)"

        except Exception as e:
            return False, f"خطأ تقني أثناء الحفظ في قاعدة البيانات: {str(e)}"
