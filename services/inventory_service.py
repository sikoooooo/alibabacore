from core.database import supabase, db_manager
from datetime import datetime

class InventoryService:
    @staticmethod
    def convert_to_base_unit(branch: str, item_name: str, quantity: float, unit: str):
        try:
            inv_res = supabase.table("inventory").select("conversion_factor, minor_unit, major_unit").eq("branch", branch).eq("item_name", item_name).execute()
            if inv_res.data:from core.database import supabase, db_manager
from datetime import datetime

class InventoryService:
    @staticmethod
    def convert_to_base_unit(branch: str, item_name: str, quantity: float, unit: str):
        """
        تحويل الكمية المدخلة للوحدة الصغرى بناءً على معامل التحويل في قاعدة البيانات.
        """
        try:
            inv_res = supabase.table("inventory").select("conversion_factor, minor_unit, major_unit").eq("branch", branch).ilike("item_name", item_name).execute()
            if inv_res.data:
                row = inv_res.data[0]
                conversion_factor = float(row.get("conversion_factor") or 1.0)
                major_unit = row.get("major_unit")
                
                if major_unit and unit.strip().lower() == major_unit.strip().lower() and conversion_factor > 1:
                    base_qty = quantity * conversion_factor
                    minor_unit = row.get('minor_unit', 'قطعة')
                    return base_qty, f"تم تحويل {quantity} {unit} إلى {base_qty} {minor_unit}"
        except Exception as e:
            print(f"Unit conversion check error: {e}")
        
        return quantity, ""

    @staticmethod
    def query_inventory(branch: str, item_name: str = None):
        """
        الاستعلام عن المخزون وتحليل الرصيد إلى كراتين وقطع تلقائياً.
        """
        try:
            query = supabase.table("inventory").select("*").eq("branch", branch)
            if item_name and item_name != "غير محدد":
                query = query.ilike("item_name", f"%{item_name}%")
                
            res = query.execute()
            if not res.data:
                return True, f"🔍 لم يتم العثور على صنف يطابق '{item_name}' في المخزن." if item_name else "🔍 المخزن فارغ حالياً."

            response_lines = ["📦 **نتائج الاستعلام عن المخزن:**\n"]
            for row in res.data:
                name = row.get("item_name")
                total_qty = float(row.get("quantity") or row.get("total_base_quantity") or 0.0)
                conversion_factor = float(row.get("conversion_factor") or 1.0)
                major_unit = row.get("major_unit") or "كرتونة"
                minor_unit = row.get("minor_unit") or "قطعة"

                if conversion_factor > 1 and total_qty > 0:
                    major_count = int(total_qty // conversion_factor)
                    minor_count = total_qty % conversion_factor
                    
                    details = []
                    if major_count > 0:
                        details.append(f"{major_count} {major_unit}")
                    if minor_count > 0 or major_count == 0:
                        minor_str = f"{int(minor_count)}" if minor_count.is_integer() else f"{minor_count:.1f}"
                        details.append(f"{minor_str} {minor_unit}")
                    
                    formatted_qty = " و ".join(details)
                    total_str = f"{int(total_qty)}" if total_qty.is_integer() else f"{total_qty:.1f}"
                    response_lines.append(f"- **{name}:** {formatted_qty} *(إجمالي: {total_str} {minor_unit})*")
                else:
                    total_str = f"{int(total_qty)}" if total_qty.is_integer() else f"{total_qty:.1f}"
                    unit = row.get("unit") or minor_unit
                    response_lines.append(f"- **{name}:** {total_str} {unit}")

            return True, "\n".join(response_lines)

        except Exception as e:
            return False, f"⚠️ خطأ أثناء الاستعلام: {str(e)}"

    @staticmethod
    def execute_transaction(branch: str, parsed: dict, user_text: str):
        """
        تنفيذ وتسجيل المبيعات والمشتريات وتحديث جدول المخزون ودليل اليومية.
        """
        try:
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch)
            if not company_id or not branch_id:
                return False, "فشل تحديد الفرع والشركة في قاعدة البيانات."

            trans_type = parsed.get("type")
            item_name = parsed.get("item_name", "غير محدد").strip()
            brand = parsed.get("brand", "غير محدد")
            supplier = parsed.get("supplier", "غير محدد")
            quantity = float(parsed.get("quantity", 1.0))
            unit = parsed.get("unit", "وحدة")
            unit_price = float(parsed.get("unit_price", 0.0))
            total_amount = quantity * unit_price

            # تحويل الكميات للوحدة الصغرى
            base_quantity, conversion_note = InventoryService.convert_to_base_unit(branch, item_name, quantity, unit)

            # 1. تسجيل المعاملة
            trans_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch": branch,
                "type": trans_type,
                "item_name": item_name,
                "brand": brand,
                "supplier_customer": supplier,
                "quantity": base_quantity,
                "unit": unit,
                "unit_price": unit_price,
                "total_amount": total_amount,
                "raw_text": user_text,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("transactions").insert(trans_data).execute()

            # 2. قيود اليومية
            journal_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch_name": branch,
                "description": f"{'مبيعات' if trans_type == 'SALE' else 'مشتريات'} {item_name} - {supplier} ({quantity} {unit})",
                "amount": total_amount,
                "entry_type": trans_type,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("journal_entries").insert(journal_data).execute()

            # 3. تحديث جدول المخزون
            inv_query = supabase.table("inventory").select("*").eq("branch", branch).ilike("item_name", item_name).execute()
            if inv_query.data:
                current_row = inv_query.data[0]
                current_qty = float(current_row.get("quantity") or current_row.get("total_base_quantity") or 0.0)
                new_qty = (current_qty + base_quantity) if trans_type == "PURCHASE" else (current_qty - base_quantity)
                supabase.table("inventory").update({"quantity": new_qty, "total_base_quantity": new_qty}).eq("id", current_row["id"]).execute()
            else:
                initial_qty = base_quantity if trans_type == "PURCHASE" else -base_quantity
                supabase.table("inventory").insert({
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch": branch,
                    "item_name": item_name,
                    "brand": brand,
                    "quantity": initial_qty,
                    "total_base_quantity": initial_qty,
                    "unit": unit
                }).execute()

            msg = f"تم حفظ المعاملة بنجاح! (الإجمالي: {total_amount:,.2f} ج.م)"
            if conversion_note:
                msg += f"\n📦 {conversion_note}"
            return True, msg

        except Exception as e:
            return False, f"خطأ أثناء الحفظ: {str(e)}"
                row = inv_res.data[0]
                conversion_factor = float(row.get("conversion_factor") or 1.0)
                major_unit = row.get("major_unit")
                
                if major_unit and unit.strip() == major_unit.strip() and conversion_factor > 1:
                    return quantity * conversion_factor, f"تم التحويل من {major_unit} إلى الوحدة الصغرى بمعامل {conversion_factor}"
        except Exception as e:
            print(f"Unit conversion error: {e}")
        return quantity, ""

    @staticmethod
    def execute_transaction(branch: str, parsed: dict, user_text: str):
        try:
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch)
            if not company_id or not branch_id:
                return False, "فشل إعداد الشركة أو الفرع."

            trans_type = parsed.get("type")
            unit_price = float(parsed.get("unit_price", 0.0))

            # ==============================================================
            # 🛠️ ميزة مرونة المدخلات: تحديث السعر لمعاملة سابقة (بدون تكرار)
            # ==============================================================
            if trans_type == "UPDATE_PRICE":
                recent_trans = supabase.table("transactions").select("*").eq("branch", branch).order("created_at", desc=True).limit(1).execute()
                if not recent_trans.data:
                    return False, "لم يتم العثور على معاملة سابقة لتحديث سعرها."
                
                last_record = recent_trans.data[0]
                record_id = last_record["id"]
                old_qty = float(last_record["quantity"])
                item_name = last_record["item_name"]
                
                new_total = old_qty * unit_price
                
                # تحديث الترانساكشن
                supabase.table("transactions").update({"unit_price": unit_price, "total_amount": new_total}).eq("id", record_id).execute()
                
                # تحديث دفتر اليومية
                recent_journal = supabase.table("journal_entries").select("*").eq("branch_name", branch).ilike("description", f"%{item_name}%").order("created_at", desc=True).limit(1).execute()
                if recent_journal.data:
                    j_id = recent_journal.data[0]["id"]
                    supabase.table("journal_entries").update({"amount": new_total}).eq("id", j_id).execute()
                    
                return True, f"تم تعديل سعر {item_name} بنجاح! الإجمالي الجديد: {new_total:,.2f} ج.م (تم التحديث بدون تكرار المخزون) 🛠️"
            # ==============================================================

            item_name = parsed.get("item_name", "غير محدد")
            brand = parsed.get("brand", "غير محدد")
            supplier = parsed.get("supplier", "غير محدد")
            quantity = float(parsed.get("quantity", 1.0))
            unit = parsed.get("unit", "وحدة")
            total_amount = quantity * unit_price
            
            is_installment = parsed.get("is_installment", False)
            down_payment = float(parsed.get("down_payment", 0.0))
            installment_value = float(parsed.get("installment_value", 0.0))
            due_date = parsed.get("due_date", "غير محدد")

            adjusted_quantity, conversion_msg = InventoryService.convert_to_base_unit(branch, item_name, quantity, unit)

            trans_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch": branch,
                "type": trans_type,
                "item_name": item_name,
                "brand": brand,
                "supplier_customer": supplier,
                "quantity": adjusted_quantity,
                "unit": unit,
                "unit_price": unit_price,
                "total_amount": total_amount,
                "raw_text": user_text,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("transactions").insert(trans_data).execute()

            journal_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch_name": branch,
                "description": f"{'مبيعات' if trans_type == 'SALE' else 'مشتريات'} {item_name} - {supplier} ({quantity} {unit})",
                "amount": total_amount,
                "entry_type": trans_type,
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("journal_entries").insert(journal_data).execute()

            inv_query = supabase.table("inventory").select("*").eq("branch", branch).eq("item_name", item_name).execute()
            if inv_query.data:
                current_qty = float(inv_query.data[0].get("quantity", 0.0))
                new_qty = (current_qty + adjusted_quantity) if trans_type == "PURCHASE" else (current_qty - adjusted_quantity)
                supabase.table("inventory").update({"quantity": new_qty}).eq("branch", branch).eq("item_name", item_name).execute()
            else:
                initial_qty = adjusted_quantity if trans_type == "PURCHASE" else -adjusted_quantity
                supabase.table("inventory").insert({
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch": branch,
                    "item_name": item_name,
                    "brand": brand,
                    "quantity": initial_qty,
                    "unit": unit
                }).execute()

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
                    "due_date": due_date,
                    "status": "نشط",
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("installments").insert(inst_data).execute()

            success_msg = f"تم الحفظ مبدئياً! (الإجمالي: {total_amount:,.2f} ج.م)" if total_amount == 0 else f"تم الحفظ بنجاح! (الإجمالي: {total_amount:,.2f} ج.م)"
            if conversion_msg:
                success_msg += f"\n📦 *{conversion_msg}*"
            return True, success_msg

        except Exception as e:
            return False, f"خطأ في قاعدة البيانات: {str(e)}"
