from core.database import supabase, db_manager
from datetime import datetime

class InventoryService:

    # 🟢 بداية الدالة: convert_to_base_unit (تحويل الكميات وقراءة تفضيلات جدول item_units)
    @staticmethod
    def convert_to_base_unit(branch: str, item_name: str, quantity: float, unit: str, parsed: dict = None):
        """
        تحويل الكمية المدخلة للوحدة الصغرى بالاعتماد على الهرمية:
        الرسالة اللحظية -> جدول item_units (مطابقة رباعية ثم ثنائية) -> جدول المخزون.
        """
        parsed = parsed or {}
        conv_factor = float(parsed.get("conversion_factor") or 1.0)
        major_u = parsed.get("major_unit") or "كرتونة"
        minor_u = parsed.get("minor_unit") or "قطعة"
        brand = parsed.get("brand", "غير محدد")
        supplier = parsed.get("supplier", "غير محدد")

        try:
            # 1. إذا لم يُذكر معامل تحويل صريح (> 1) في الرسالة، ابحث في جدول item_units
            if conv_factor <= 1.0:
                # مطابقة رباعية: (الفرع + الصنف + الماركة + المورد)
                units_res = supabase.table("item_units").select("conversion_factor, major_unit, minor_unit")\
                    .eq("branch", branch).ilike("item_name", item_name)\
                    .ilike("brand", brand).ilike("supplier", supplier).execute()
                
                if not units_res.data:
                    # مطابقة ثنائية: (الفرع + الصنف)
                    units_res = supabase.table("item_units").select("conversion_factor, major_unit, minor_unit")\
                        .eq("branch", branch).ilike("item_name", item_name).execute()

                if units_res.data:
                    row = units_res.data[0]
                    conv_factor = float(row.get("conversion_factor") or 1.0)
                    major_u = row.get("major_unit") or major_u
                    minor_u = row.get("minor_unit") or minor_u
                else:
                    # البحث في جدول المخزون كبديل
                    inv_res = supabase.table("inventory").select("conversion_factor, minor_unit, major_unit")\
                        .eq("branch", branch).ilike("item_name", item_name).execute()
                    if inv_res.data:
                        row = inv_res.data[0]
                        conv_factor = float(row.get("conversion_factor") or 1.0)
                        major_u = row.get("major_unit") or major_u
                        minor_u = row.get("minor_unit") or minor_u

            # 2. إجراء التحويل للوحدة الصغرى إذا كانت الوحدة كبرى
            if conv_factor > 1.0:
                unit_clean = unit.strip().lower()
                major_clean = major_u.strip().lower()
                minor_clean = minor_u.strip().lower()

                if unit_clean == major_clean or (unit_clean != minor_clean and conv_factor > 1):
                    base_qty = quantity * conv_factor
                    return base_qty, f"تم تحويل {quantity} {unit} إلى {base_qty} {minor_u}", conv_factor, major_u, minor_u
        except Exception as e:
            print(f"Unit conversion error: {e}")
        
        return quantity, "", conv_factor, major_u, minor_u
    # 🔴 نهاية الدالة: convert_to_base_unit


    # 🟢 بداية الدالة: save_item_unit_preference (حفظ وتحديث التفضيل الذكي في item_units)
    @staticmethod
    def save_item_unit_preference(branch: str, item_name: str, brand: str, supplier: str, major_unit: str, minor_unit: str, conversion_factor: float):
        """
        حفظ أو تحديث قاعدة التعبئة والتحويل الخاصة بالصنف والمورد في جدول item_units.
        """
        if conversion_factor <= 1.0:
            return
            
        try:
            check_q = supabase.table("item_units").select("id").eq("branch", branch)\
                .ilike("item_name", item_name).ilike("brand", brand).ilike("supplier", supplier).execute()
            
            payload = {
                "branch": branch,
                "item_name": item_name,
                "brand": brand,
                "supplier": supplier,
                "major_unit": major_unit,
                "minor_unit": minor_unit,
                "conversion_factor": conversion_factor
            }

            if check_q.data:
                supabase.table("item_units").update(payload).eq("id", check_q.data[0]["id"]).execute()
            else:
                supabase.table("item_units").insert(payload).execute()
        except Exception as e:
            print(f"Error saving item unit preference: {e}")
    # 🔴 نهاية الدالة: save_item_unit_preference


    # 🟢 بداية الدالة: query_inventory (عرض المخزون بالرصيد المزدوج)
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
    # 🔴 نهاية الدالة: query_inventory


    # 🟢 بداية الدالة: execute_transaction (تنفيذ المعاملات وتسوية الأسعار وتحديث تفضيلات الوحدات)
    @staticmethod
    def execute_transaction(branch: str, parsed: dict, user_text: str):
        """
        تنفيذ المبيعات والمشتريات وتحديث المخزون وتفضيلات الوحدات وتسوية الأسعار.
        """
        try:
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch) if hasattr(db_manager, 'ensure_default_enterprise_setup') else (None, None)
            
            trans_type = parsed.get("type", "PURCHASE")
            item_name = parsed.get("item_name", "غير محدد").strip()
            brand = parsed.get("brand", "غير محدد")
            supplier = parsed.get("supplier", "غير محدد")
            raw_quantity = float(parsed.get("quantity", 1.0))
            unit = parsed.get("unit", "وحدة")
            unit_price = float(parsed.get("unit_price", 0.0))

            # 1. تحويل الكمية إلى الوحدة الصغرى بالاعتماد على الهرمية وتفضيلات item_units
            base_quantity, conversion_note, conv_factor, major_unit, minor_unit = InventoryService.convert_to_base_unit(
                branch, item_name, raw_quantity, unit, parsed
            )

            # 2. حفظ تفضيل الوحدة في جدول item_units تلقائياً للتعاملات القادمة
            if conv_factor > 1.0:
                InventoryService.save_item_unit_preference(
                    branch, item_name, brand, supplier, major_unit, minor_unit, conv_factor
                )

            # 3. حساب الإجمالي المالي الصحيح
            if unit_price > 0:
                if base_quantity != raw_quantity and (parsed.get("unit") == minor_unit or unit_price < 100):
                    total_amount = base_quantity * unit_price
                else:
                    total_amount = raw_quantity * unit_price
            else:
                total_amount = 0.0

            # 4. معالجة حالة تحديث سعر معاملة معلقة سابقة (UPDATE_PRICE)
            if trans_type == "UPDATE_PRICE":
                pending_query = supabase.table("transactions").select("*").eq("branch", branch)\
                    .ilike("item_name", f"%{item_name}%").eq("total_amount", 0.0).order("created_at", desc=True).limit(1).execute()
                
                if pending_query.data:
                    pending_trans = pending_query.data[0]
                    target_qty = float(pending_trans.get("quantity") or base_quantity)
                    new_total = target_qty * unit_price if unit_price > 0 else total_amount

                    supabase.table("transactions").update({
                        "unit_price": unit_price,
                        "total_amount": new_total
                    }).eq("id", pending_trans["id"]).execute()

                    journal_data = {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "branch_name": branch,
                        "description": f"تسوية سعر {item_name} - {supplier} بسعر {unit_price} ج.م",
                        "amount": new_total,
                        "entry_type": pending_trans.get("type", "PURCHASE"),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    supabase.table("journal_entries").insert(journal_data).execute()

                    return True, f"✅ تم تحديث السعر وتسوية الفاتورة بنجاح! (الإجمالي الجديد: {new_total:,.2f} ج.م)"

            # 5. تسجيل حركة جديدة في جدول المعاملات
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

            # 6. تسجيل القيود المالية
            if total_amount > 0:
                journal_data = {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch_name": branch,
                    "description": f"{'مبيعات' if trans_type == 'SALE' else 'مشتريات'} {item_name} - {supplier} ({raw_quantity} {unit})",
                    "amount": total_amount,
                    "entry_type": trans_type,
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("journal_entries").insert(journal_data).execute()

            # 7. تحديث جدول المخزون
            inv_query = supabase.table("inventory").select("*").eq("branch", branch).ilike("item_name", item_name).execute()
            
            if inv_query.data:
                current_row = inv_query.data[0]
                current_qty = float(current_row.get("quantity") or current_row.get("total_base_quantity") or 0.0)
                new_qty = (current_qty + base_quantity) if trans_type == "PURCHASE" else (current_qty - base_quantity)
                
                update_payload = {
                    "quantity": new_qty,
                    "total_base_quantity": new_qty
                }
                if conv_factor > 1:
                    update_payload["conversion_factor"] = conv_factor
                    update_payload["major_unit"] = major_unit
                    update_payload["minor_unit"] = minor_unit

                supabase.table("inventory").update(update_payload).eq("id", current_row["id"]).execute()
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
                    "unit": minor_unit if conv_factor > 1 else unit,
                    "major_unit": major_unit,
                    "minor_unit": minor_unit,
                    "conversion_factor": conv_factor
                }).execute()

            # 8. صياغة الرد للتاجر
            if total_amount == 0.0:
                msg = f"✅ تم حفظ الكمية بالمخزن بنجاح (+{int(base_quantity) if base_quantity.is_integer() else base_quantity} {minor_unit})!\n⚠️ المعاملة معلقة السعر، يمكنك إدخال السعر الآن أو التسعير لاحقاً."
            else:
                msg = f"✅ تم حفظ المعاملة بنجاح! (الإجمالي: {total_amount:,.2f} ج.م)"
            
            if conversion_note:
                msg += f"\n📦 {conversion_note}"
            return True, msg

        except Exception as e:
            return False, f"خطأ أثناء الحفظ: {str(e)}"
    # 🔴 نهاية الدالة: execute_transaction
