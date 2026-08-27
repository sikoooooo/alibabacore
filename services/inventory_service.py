from typing import Dict, Any
from core.database import get_supabase_client

class InventoryService:
    @classmethod
    def process_transaction(cls, branch: str, item_name: str, quantity: float, price: float, supplier: str, transaction_type: str, unit: str = "وحدة", minor_unit: str = None, conversion_factor: float = 1.0) -> dict:
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        try:
            actual_unit = unit if unit and unit != "غير محدد" else "وحدة"
            conv = float(conversion_factor) if conversion_factor and conversion_factor > 0 else 1.0
            
            # الكمية الفعالة بالوحدة الصغرى أو الأساسية
            effective_qty = quantity * conv
            recorded_unit = minor_unit if minor_unit and minor_unit != "غير محدد" else actual_unit

            # 1. تسجيل الحركة في جدول transactions
            tx_data = {
                "branch": branch,
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": price / conv if conv > 1 else price,
                "supplier": supplier,
                "type": transaction_type,
                "unit": recorded_unit
            }
            supabase.table("transactions").insert(tx_data).execute()

            # 2. إنشاء قيد يومي تلقائي في journal_entries
            total_val = quantity * price
            desc_text = f"مشتريات {item_name} ({quantity} {actual_unit})" if transaction_type == "PURCHASE" else f"مبيعات {item_name} ({quantity} {actual_unit})"
            
            journal_data = {
                "branch": branch,
                "description": desc_text,
                "total_amount": total_val if total_val > 0 else 0.0
            }
            try:
                supabase.table("journal_entries").insert(journal_data).execute()
            except Exception as je:
                print(f"Journal entry log error: {je}")

            # 3. تحديث أو إدراج المخزن
            multiplier = 1 if transaction_type == "PURCHASE" else -1
            net_change = effective_qty * multiplier

            existing = supabase.table("inventory").select("*").eq("branch", branch).ilike("item_name", f"%{item_name}%").execute()
            
            if existing.data:
                row = existing.data[0]
                current_qty = float(row.get("total_base_quantity", 0) or 0)
                new_qty = current_qty + net_change
                
                supabase.table("inventory").update({
                    "total_base_quantity": new_qty,
                    "major_unit": recorded_unit
                }).eq("id", row["id"]).execute()
            else:
                new_row = {
                    "branch": branch,
                    "item_name": item_name,
                    "total_base_quantity": net_change,
                    "major_unit": recorded_unit,
                    "avg_cost_per_base": price / conv if conv > 0 else price
                }
                supabase.table("inventory").insert(new_row).execute()

            return {"status": "SUCCESS"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    @classmethod
    def update_inventory_field(cls, branch: str, item_name: str, field_name: str, new_value: Any) -> Dict[str, Any]:
        """دالة شاملة لتحديث أي خانة ناقصة أو تعديلها (المورد، البراند، إلخ) لصنف معين في جدول المخزن والحركات."""
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        
        # خريطة أسماء الحقول المسموح بتعديلها لضمان الأمان المحاسبي
        allowed_fields = {
            "supplier": "المورد",
            "brand": "البراند/الماركة",
            "supplier_customer": "المورد",
            "major_unit": "الوحدة الكبرى",
            "minor_unit": "الوحدة الصغرى"
        }
        
        if field_name not in allowed_fields:
            return {"status": "ERROR", "message": f"⚠️ الحقل '{field_name}' غير مسموح بتعديله مباشره."}
        
        try:
            # البحث عن الصنف في جدول المخزن للفرع المذكور
            res = supabase.table("inventory").select("id, item_name").eq("branch", branch).ilike("item_name", f"%{item_name}%").limit(1).execute()
            
            if not res.data:
                return {"status": "NOT_FOUND", "message": f"⚠️ لم يتم العثور على الصنف '{item_name}' في المخزن لتحديث {allowed_fields[field_name]}."}
                
            record_id = res.data[0]["id"]
            actual_name = res.data[0]["item_name"]
            
            # تنفيذ التحديث في جدول المخزن
            supabase.table("inventory").update({field_name: new_value}).eq("id", record_id).execute()
            
            # تحديث جدول الحركات المرتبط أيضاً لتتطابق البيانات تماماً
            try:
                supabase.table("transactions").update({field_name: new_value}).eq("branch", branch).ilike("item_name", f"%{item_name}%").execute()
            except Exception:
                pass
            
            return {
                "status": "SUCCESS",
                "message": f"✅ تم تحديث {allowed_fields[field_name]} للصنف '{actual_name}' إلى ('{new_value}') بنجاح."
            }
        except Exception as e:
            print(f"Update inventory field error: {e}")
            return {"status": "ERROR", "message": f"حدث خطأ أثناء التحديث: {str(e)}"}
