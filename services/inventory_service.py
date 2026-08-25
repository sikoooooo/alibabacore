from datetime import datetime, timedelta
from core.database import supabase, db_manager
from services.notification_service import NotificationService

class InventoryService:
    @staticmethod
    def convert_to_base_unit(branch: str, item_name: str, quantity: float, unit: str, parsed: dict = None):
        parsed = parsed or {}
        conv_factor = float(parsed.get("conversion_factor") or 1.0)
        major_u = parsed.get("major_unit") or "كرتونة"
        minor_u = parsed.get("minor_unit") or "قطعة"
        brand = parsed.get("brand", "غير محدد")
        supplier = parsed.get("supplier", "غير محدد")
        try:
            if conv_factor <= 1.0:
                units_res = supabase.table("item_units").select("conversion_factor, major_unit, minor_unit")\
                    .eq("branch", branch).ilike("item_name", item_name)\
                    .ilike("brand", brand).ilike("supplier", supplier).execute()
                if not units_res.data:
                    units_res = supabase.table("item_units").select("conversion_factor, major_unit, minor_unit")\
                        .eq("branch", branch).ilike("item_name", item_name).execute()
                if units_res.data:
                    row = units_res.data[0]
                    conv_factor = float(row.get("conversion_factor") or 1.0)
                    major_u = row.get("major_unit") or major_u
                    minor_u = row.get("minor_unit") or minor_u
                else:
                    inv_res = supabase.table("inventory").select("conversion_factor, minor_unit, major_unit")\
                        .eq("branch", branch).ilike("item_name", item_name).execute()
                    if inv_res.data:
                        row = inv_res.data[0]
                        conv_factor = float(row.get("conversion_factor") or 1.0)
                        major_u = row.get("major_unit") or major_u
                        minor_u = row.get("minor_unit") or minor_u

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

    @staticmethod
    def save_item_unit_preference(branch: str, item_name: str, brand: str, supplier: str, major_unit: str, minor_unit: str, conversion_factor: float):
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

    @staticmethod
    def query_inventory(branch: str, item_name: str = None):
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
                avg_cost = float(row.get("average_cost") or 0.0)
                
                cost_info = f" *(متوسط التكلفة: {avg_cost:,.2f} ج.م)*" if avg_cost > 0 else ""

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
                    response_lines.append(f"- **{name}:** {formatted_qty} *(إجمالي: {total_str} {minor_unit})*{cost_info}")
                else:
                    total_str = f"{int(total_qty)}" if total_qty.is_integer() else f"{total_qty:.1f}"
                    unit = row.get("unit") or minor_unit
                    response_lines.append(f"- **{name}:** {total_str} {unit}{cost_info}")
            return True, "\n".join(response_lines)
        except Exception as e:
            return False, f"⚠️ خطأ أثناء الاستعلام: {str(e)}"

    @staticmethod
    def _record_treasury(branch: str, flow_type: str, amount: float, description: str):
        """تسجيل النقدية في حركة الخزينة والدرج آلياً."""
        try:
            supabase.table("treasury_ledger").insert({
                "branch": branch,
                "type": flow_type,
                "amount": amount,
                "description": description
            }).execute()
        except Exception as e:
            print(f"Error recording treasury: {e}")

    @staticmethod
    def execute_transaction(branch: str, parsed: dict, user_text: str):
        try:
            company_id, branch_id = db_manager.ensure_default_enterprise_setup(branch) if hasattr(db_manager, 'ensure_default_enterprise_setup') else (None, None)
            trans_type = parsed.get("type", "PURCHASE")
            item_name = parsed.get("item_name", "غير محدد").strip()
            brand = parsed.get("brand", "غير محدد")
            supplier = parsed.get("supplier", "غير محدد")
            raw_quantity = float(parsed.get("quantity", 1.0))
            unit = parsed.get("unit", "وحدة")
            unit_price = float(parsed.get("unit_price", 0.0))

            base_quantity, conversion_note, conv_factor, major_unit, minor_unit = InventoryService.convert_to_base_unit(
                branch, item_name, raw_quantity, unit, parsed
            )

            if conv_factor > 1.0:
                InventoryService.save_item_unit_preference(
                    branch, item_name, brand, supplier, major_unit, minor_unit, conv_factor
                )

            if unit_price > 0:
                if base_quantity != raw_quantity and (parsed.get("unit") == minor_unit or unit_price < 100):
                    total_amount = base_quantity * unit_price
                else:
                    total_amount = raw_quantity * unit_price
            else:
                total_amount = 0.0

            # 1. تسوية الأسعار المعلقة (UPDATE_PRICE)
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

                    if new_total > 0:
                        flow_type = "OUTFLOW" if pending_trans.get("type") == "PURCHASE" else "INFLOW"
                        InventoryService._record_treasury(branch, flow_type, new_total, f"تسوية سعر {item_name}")

                    return True, f"✅ تم تحديث السعر وتسوية الفاتورة بنجاح! (الإجمالي الجديد: {new_total:,.2f} ج.م)"

            # 2. تسجيل المعاملة في جدول المعاملات
            trans_data = {
                "company_id": company_id,
                "branch_id": branch_id,
                "branch": branch,
                "type": trans_type,
                "item_name": item_name,
                "brand": brand,
                "supplier_customer": supplier,
                "input_quantity": raw_quantity,
                "quantity": base_quantity,
                "unit": unit,
                "unit_price": unit_price,
                "total_amount": total_amount,
                "raw_text": user_text,
                "created_at": datetime.utcnow().isoformat()
            }
            inserted_tx = supabase.table("transactions").insert(trans_data).execute()
            tx_id = inserted_tx.data[0]["id"] if inserted_tx.data else "PENDING"

            # 3. إرسال تنبيه فور تسجيل حركة بدون سعر
            if total_amount == 0.0 and trans_type in ["PURCHASE", "SALE"]:
                NotificationService.notify_missing_price(item_name, str(tx_id), branch_id)

            # 4. تسجيل قيود اليومية وحركة الدرج الخزينة
            if total_amount > 0:
                journal_data = {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch_name": branch,
                    "description": f"{('مبيعات' if trans_type == 'SALE' else 'مشتريات')} {item_name} - {supplier} ({raw_quantity} {unit})",
                    "amount": total_amount,
                    "entry_type": trans_type,
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("journal_entries").insert(journal_data).execute()

                if not parsed.get("is_installment"):
                    flow_type = "OUTFLOW" if trans_type == "PURCHASE" else "INFLOW"
                    InventoryService._record_treasury(branch, flow_type, total_amount, f"{trans_type} - {item_name}")

            # 5. تحديث المخزون والمتوسط السعري المرجح (WAC)
            inv_query = supabase.table("inventory").select("*").eq("branch", branch).ilike("item_name", item_name).execute()
            if inv_query.data:
                current_row = inv_query.data[0]
                current_qty = float(current_row.get("quantity") or current_row.get("total_base_quantity") or 0.0)
                current_cost = float(current_row.get("average_cost") or 0.0)
                min_stock = float(current_row.get("min_stock_level") or 5.0)

                if trans_type == "PURCHASE":
                    new_qty = current_qty + base_quantity
                    new_wac = ((current_qty * current_cost) + total_amount) / new_qty if (new_qty > 0 and unit_price > 0) else current_cost
                elif trans_type == "SALE":
                    new_qty = current_qty - base_quantity
                    new_wac = current_cost
                elif trans_type == "RETURN":
                    new_qty = current_qty + base_quantity
                    new_wac = current_cost
                else:
                    new_qty = current_qty
                    new_wac = current_cost

                update_payload = {
                    "quantity": new_qty,
                    "total_base_quantity": new_qty,
                    "average_cost": new_wac
                }
                if conv_factor > 1:
                    update_payload["conversion_factor"] = conv_factor
                    update_payload["major_unit"] = major_unit
                    update_payload["minor_unit"] = minor_unit

                supabase.table("inventory").update(update_payload).eq("id", current_row["id"]).execute()

                # تنبيه النواقص
                if new_qty <= min_stock:
                    NotificationService.notify_low_stock(item_name, new_qty, branch_id)
            else:
                initial_qty = base_quantity if trans_type in ["PURCHASE", "RETURN"] else -base_quantity
                initial_cost = unit_price if (trans_type == "PURCHASE" and unit_price > 0) else 0.0
                supabase.table("inventory").insert({
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "branch": branch,
                    "item_name": item_name,
                    "brand": brand,
                    "quantity": initial_qty,
                    "total_base_quantity": initial_qty,
                    "average_cost": initial_cost,
                    "unit": minor_unit if conv_factor > 1 else unit,
                    "major_unit": major_unit,
                    "minor_unit": minor_unit,
                    "conversion_factor": conv_factor
                }).execute()

            # 6. صياغة النتيجة التفاعلية
            if total_amount == 0.0:
                msg = f"✅ تم حفظ الكمية بالمخزن بنجاح (+{(int(base_quantity) if base_quantity.is_integer() else base_quantity)} {minor_unit})!\n⚠️ المعاملة معلقة السعر، يمكنك إدخال السعر الآن أو التسعير لاحقاً."
            else:
                msg = f"✅ تم حفظ المعاملة بنجاح! (الإجمالي: {total_amount:,.2f} ج.م)"

            if conversion_note:
                msg += f"\n📦 {conversion_note}"
            return True, msg

        except Exception as e:
            return False, f"خطأ أثناء الحفظ: {str(e)}"

    @staticmethod
    def check_slow_moving_items(branch: str, days_threshold: int = 30) -> list:
        """
        رصد الأصناف الراكدة (التي لم تباع منذ N يوماً) وإرسال تنبيه مع عرض تسويقي مقترح.
        """
        try:
            inv_res = supabase.table("inventory").select("*").eq("branch", branch).gt("quantity", 0).execute()
            if not inv_res.data:
                return []

            slow_items = []
            cutoff_date = (datetime.utcnow() - timedelta(days=days_threshold)).isoformat()

            for item in inv_res.data:
                item_name = item.get("item_name")
                qty = float(item.get("quantity") or 0.0)

                # البحث عن آخر عملية بيع لهذا الصنف
                recent_sales = supabase.table("transactions").select("created_at")\
                    .eq("branch", branch)\
                    .eq("type", "SALE")\
                    .ilike("item_name", item_name)\
                    .gt("created_at", cutoff_date)\
                    .limit(1).execute()

                if not recent_sales.data:
                    # توليد عرض تسويقي ذكي للصنف الراكد
                    suggestion = f"🎯 عرض ترويجي: اشترِ 2 قطعة من '{item_name}' واحصل على قطعة مجاناً / خصم 15% لتسريع حركة المخزون."
                    NotificationService.notify_slow_moving(
                        item_name=item_name,
                        days_inactive=days_threshold,
                        current_qty=qty,
                        marketing_suggestion=suggestion,
                        branch_id=item.get("branch_id")
                    )
                    slow_items.append({
                        "item_name": item_name,
                        "quantity": qty,
                        "suggestion": suggestion
                    })
            return slow_items
        except Exception as e:
            print(f"Error checking slow moving items: {e}")
            return []
