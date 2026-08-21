from core.database import supabase, db_manager
from core.local_sync import LocalSyncManager

sync_manager = LocalSyncManager()

class InventoryService:
    @staticmethod
    def execute_transaction(branch: str, parsed_data: dict, raw_text: str):
        try:
            trans_type = parsed_data.get("type", "SALE")
            item_name = parsed_data.get("item_name", "غير محدد")
            
            try:
                input_qty = float(parsed_data.get("quantity", 1))
            except Exception:
                input_qty = 1.0
                
            try:
                unit_price = float(parsed_data.get("unit_price", 0))
            except Exception:
                unit_price = 0.0

            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch)
            if not company_id or not branch_id:
                return False, "فشل في جلب هيكل الشركة والفرع"

            company_name = "الشركة الافتراضية العامة"
            try:
                comp_res = supabase.table("companies").select("name").eq("id", company_id).execute()
                if comp_res.data:
                    company_name = comp_res.data[0].get("name", "الشركة الافتراضية العامة")
            except Exception:
                pass

            try:
                # 🧠 الذكاء المحاسبي: البحث عما إذا كان هناك سجل سابق غير مسعر لهذا الصنف في نفس الفرع لتحديثه
                target_transaction_id = None
                if unit_price > 0 and item_name != "غير محدد":
                    unpriced = supabase.table("transactions") \
                        .select("id, input_quantity") \
                        .eq("branch", branch) \
                        .eq("item_name", item_name) \
                        .eq("unit_price", 0) \
                        .order("created_at", desc=True) \
                        .limit(1) \
                        .execute()
                    if unpriced.data:
                        target_transaction_id = unpriced.data[0]["id"]
                        # وراثة الكمية الصحيحة من السجل القديم غير المسعر
                        input_qty = float(unpriced.data[0]["input_quantity"])

                total_amount = input_qty * unit_price

                if target_transaction_id:
                    # 🔄 تحديث السجل القديم بدلاً من إنشاء سطر جديد
                    supabase.table("transactions").update({
                        "unit_price": unit_price,
                        "total_amount": total_amount,
                        "raw_text": raw_text
                    }).eq("id", target_transaction_id).execute()

                    # تسجيل قيد محاسبي بالتحديث
                    description = f"تسعير وتحديث قيد {trans_type} للصنف ({item_name})"
                    supabase.table("journal_entries").insert({
                        "company_id": company_id, "branch_id": branch_id,
                        "company_name": company_name, "branch_name": branch,
                        "description": description, "total_amount": total_amount
                    }).execute()

                    # تحديث متوسط التكلفة في المخزن
                    supabase.table("inventory").update({
                        "avg_cost_per_base": unit_price
                    }).eq("branch", branch).eq("item_name", item_name).execute()

                    return True, f"✅ تم تحديث سعر الصنف ({item_name}) للكمية ({input_qty}) وأصبح الإجمالي: {total_amount:,.2f}"

                else:
                    # ➕ إدراج حركة جديدة كالعادة إذا كانت كاملة أو مسعرة من البداية
                    supabase.table("transactions").insert({
                        "company_id": company_id, "branch_id": branch_id, "branch": branch,
                        "type": trans_type, "item_name": item_name, "input_quantity": input_qty,
                        "unit_price": unit_price, "total_amount": total_amount, "raw_text": raw_text
                    }).execute()

                    description = f"قيد {trans_type} للصنف ({item_name}) بفرع {branch}"
                    supabase.table("journal_entries").insert({
                        "company_id": company_id, "branch_id": branch_id,
                        "company_name": company_name, "branch_name": branch,
                        "description": description, "total_amount": total_amount
                    }).execute()

                    # تحديث المخزن
                    existing = supabase.table("inventory").select("*").eq("branch", branch).eq("item_name", item_name).execute()
                    if existing.data:
                        current_total = float(existing.data[0].get("total_base_quantity", 0))
                        new_total = current_total - input_qty if trans_type == "SALE" else current_total + input_qty
                        supabase.table("inventory").update({
                            "total_base_quantity": new_total, 
                            "avg_cost_pet_base" if "avg_cost_pet_base" in existing.data[0] else "avg_cost_per_base": unit_price if unit_price > 0 else existing.data[0].get("avg_cost_per_base", 0)
                        }).eq("branch", branch).eq("item_name", item_name).execute()
                    else:
                        initial_total = input_qty if trans_type == "PURCHASE" else -input_qty
                        supabase.table("inventory").insert({
                            "branch": branch, "item_name": item_name, "total_base_quantity": initial_total, "avg_cost_per_base": unit_price
                        }).execute()
                        
                    if unit_price == 0:
                        return True, f"✅ تم إثبات كمية ({input_qty}) للصنف ({item_name}) في المخزن. يرجى تزويدي بالسعر لاحقاً."
                    else:
                        return True, f"✅ تم تسجيل العملية بالكامل (كمية: {input_qty}، إجمالي: {total_amount:,.2f})."

            except Exception as cloud_err:
                sync_manager.save_offline(branch, raw_text, parsed_data)
                return True, f"⚠️ انقطع الاتصال! تم حفظ الحركة محلياً (عدد المعلق: {sync_manager.get_pending_count()})"
                
        except Exception as e:
            return False, str(e)
