from core.database import supabase, db_manager
from core.local_sync import LocalSyncManager

sync_manager = LocalSyncManager()

class InventoryService:
    @staticmethod
    def normalize_item_name(name: str) -> str:
        """
        توحيد صيغ الأرقام والوحدات فقط (مثل لتر ونصف إلى 1.5 لتر) 
        دون المساس بالأسماء التجارية أو دمج أصناف مختلفة.
        """
        if not name:
            return "غير محدد"
        
        normalized = name.strip().lower()
        
        replacements = {
            "لتر ونصف": "1.5 لتر",
            "واحد ونصف لتر": "1.5 لتر",
            "١.٥ لتر": "1.5 لتر",
            "نصف لتر": "0.5 لتر",
            "نص لتر": "0.5 لتر",
            "٧٠٠ مل": "0.7 لتر",
            "٨٠٠ مل": "0.8 لتر"
        }
        
        for key, val in replacements.items():
            if key in normalized:
                normalized = normalized.replace(key, val)
                
        return normalized.title()

    @staticmethod
    def format_stock_display(item_name: str, total_base_qty, units_per_carton: int = 12):
        """
        تنسيق المخزن واستنباط الوحدة الصغرى بدقة (زجاجة، كيس، علبة، قطعة)
        """
        try:
            qty = float(total_base_qty)
        except (TypeError, ValueError):
            return f"{total_base_qty} وحدة"
        
        name_lower = (item_name or "").lower()
        if any(w in name_lower for w in ["زيت", "عصير", "مياه", "خل", "صويا"]):
            unit_name = "زجاجة"
        elif any(w in name_lower for w in ["مكرونة", "سكر", "رز", "أرز", "ملح", "دقيق", "بن"]):
            unit_name = "كيس"
        elif any(w in name_lower for w in ["جبنة", "تونة", "صلصة", "سمنة", "حلاوة", "شاي"]):
            unit_name = "علبة"
        elif any(w in name_lower for w in ["بسكويت", "شيبسي", "شوكولاتة"]):
            unit_name = "باكو"
        else:
            unit_name = "قطعة"
        
        if units_per_carton <= 1:
            return f"{qty:g} {unit_name}"
            
        cartons = int(qty // units_per_carton)
        pieces = int(qty % units_per_carton)
        
        result_parts = []
        if cartons > 0:
            result_parts.append(f"{cartons} كرتونة")
        if pieces > 0 or cartons == 0:
            result_parts.append(f"{pieces} {unit_name}")
            
        return " و ".join(result_parts)

    @classmethod
    def execute_transaction(cls, branch: str, parsed_data: dict, raw_text: str):
        try:
            trans_type = parsed_data.get("type", "SALE")
            raw_item_name = parsed_data.get("item_name", "غير محدد")
            item_name = cls.normalize_item_name(raw_item_name)
            
            # استخراج البيانات الجديدة (الماركة، المورد/العميل، والتقسيط)
            brand = parsed_data.get("brand", "غير محدد")
            supplier = parsed_data.get("supplier", "غير محدد")
            is_installment = bool(parsed_data.get("is_installment", False))
            
            try:
                down_payment = float(parsed_data.get("down_payment", 0))
            except Exception:
                down_payment = 0.0

            try:
                installment_value = float(parsed_data.get("installment_value", 0))
            except Exception:
                installment_value = 0.0

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
                        input_qty = float(unpriced.data[0]["input_quantity"])

                total_amount = input_qty * unit_price

                # تحديد الوصف الشامل مع الماركة والمورد والتقسيط
                party_label = "المورد" if trans_type == "PURCHASE" else "العميل"
                desc_prefix = f"شراء من {supplier}" if trans_type == "PURCHASE" else f"بيع لـ {supplier}"
                full_description = f"{desc_prefix} - صنف ({item_name}) ماركة ({brand})"
                if is_installment:
                    full_description += " [نظام التقسيط]"

                if target_transaction_id:
                    # تحديث حركة سابقة غير مسعرة
                    supabase.table("transactions").update({
                        "unit_price": unit_price,
                        "total_amount": total_amount,
                        "raw_text": raw_text,
                        "supplier": supplier,
                        "brand": brand,
                        "is_installment": is_installment
                    }).eq("id", target_transaction_id).execute()

                    supabase.table("journal_entries").insert({
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "company_name": company_name,
                        "branch_name": branch,
                        "description": f"تسعير وتحديث: {full_description}",
                        "total_amount": total_amount
                    }).execute()

                    supabase.table("inventory").update({
                        "avg_cost_per_base": unit_price,
                        "brand": brand
                    }).eq("branch", branch).eq("item_name", item_name).execute()

                    # تسجيل القسط إن وجد
                    if is_installment:
                        remaining_amount = total_amount - down_payment
                        supabase.table("installments").insert({
                            "branch": branch,
                            "customer_name": supplier,
                            "item_name": item_name,
                            "total_amount": total_amount,
                            "down_payment": down_payment,
                            "remaining_amount": remaining_amount,
                            "installment_value": installment_value,
                            "status": "نشط"
                        }).execute()

                    msg = f"✅ تم تحديث سعر الصنف ({item_name}) - ماركة ({brand}) - {party_label}: ({supplier}) - الإجمالي: {total_amount:,.2f}"
                    if is_installment:
                        msg += f"\n💳 تم تسجيل قسط بجهة ({supplier}) بمبلغ متبقي ({total_amount - down_payment:,.2f})."
                    return True, msg

                else:
                    # إضافة حركة جديدة
                    supabase.table("transactions").insert({
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "branch": branch,
                        "type": trans_type,
                        "item_name": item_name,
                        "input_quantity": input_qty,
                        "unit_price": unit_price,
                        "total_amount": total_amount,
                        "raw_text": raw_text,
                        "supplier": supplier,
                        "brand": brand,
                        "is_installment": is_installment
                    }).execute()

                    supabase.table("journal_entries").insert({
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "company_name": company_name,
                        "branch_name": branch,
                        "description": full_description,
                        "total_amount": total_amount
                    }).execute()

                    # إدراج حركة الأقساط إذا كانت العملية بالتقسيط
                    if is_installment:
                        remaining_amount = total_amount - down_payment
                        supabase.table("installments").insert({
                            "branch": branch,
                            "customer_name": supplier,
                            "item_name": item_name,
                            "total_amount": total_amount,
                            "down_payment": down_payment,
                            "remaining_amount": remaining_amount,
                            "installment_value": installment_value,
                            "status": "نشط"
                        }).execute()

                    # تحديث المخزون
                    existing = supabase.table("inventory").select("*").eq("branch", branch).eq("item_name", item_name).execute()
                    if existing.data:
                        current_total = float(existing.data[0].get("total_base_quantity", 0))
                        current_avg_cost = float(existing.data[0].get("avg_cost_per_base", 0))
                        
                        if trans_type == "SALE":
                            new_total = current_total - input_qty
                            new_avg_cost = current_avg_cost
                        else:
                            new_total = current_total + input_qty
                            new_avg_cost = unit_price if unit_price > 0 else current_avg_cost

                        supabase.table("inventory").update({
                            "total_base_quantity": new_total, 
                            "avg_cost_per_base": new_avg_cost,
                            "brand": brand
                        }).eq("branch", branch).eq("item_name", item_name).execute()
                    else:
                        initial_total = input_qty if trans_type == "PURCHASE" else -input_qty
                        initial_cost = unit_price if trans_type == "PURCHASE" else 0.0
                        supabase.table("inventory").insert({
                            "branch": branch,
                            "item_name": item_name,
                            "total_base_quantity": initial_total,
                            "avg_cost_per_base": initial_cost,
                            "brand": brand
                        }).execute()
                        
                    if unit_price == 0:
                        return True, f"✅ تم إثبات كمية ({input_qty}) للصنف ({item_name}) [ماركة: {brand}] في المخزن. يرجى تزويدي بالسعر لاحقاً."
                    else:
                        msg = f"✅ تم تسجيل العملية بالكامل (الصنف: {item_name} | ماركة: {brand} | {party_label}: {supplier} | الكمية: {input_qty} | إجمالي: {total_amount:,.2f})."
                        if is_installment:
                            msg += f"\n💳 تم إدراج قسط جديد بجهة ({supplier}) بمبلغ متبقي ({total_amount - down_payment:,.2f})."
                        return True, msg

            except Exception as cloud_err:
                sync_manager.save_offline(branch, raw_text, parsed_data)
                return True, f"⚠️ انقطع الاتصال! تم حفظ الحركة محلياً (عدد المعلق: {sync_manager.get_pending_count()})"
                
        except Exception as e:
            return False, str(e)
