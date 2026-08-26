from core.database import get_supabase_client
class InventoryService:
    @classmethod
    def process_transaction(cls, branch: str, item_name: str, quantity: float, price: float, supplier: str, transaction_type: str) -> dict:
        supabase = get_supabase_client()
        if not supabase:
            return {"status": "ERROR", "message": "قاعدة البيانات غير متوفرة."}
        try:
            data = {
                "branch": branch,
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": price,
                "supplier": supplier,
                "type": transaction_type
            }
            supabase.table("transactions").insert(data).execute()
            return {"status": "SUCCESS"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    @classmethod
    def update_inventory_field(cls, branch: str, item_name: str, field_name: str, new_value: Any) -> Dict[str, Any]:
        """دالة شاملة لتحديث أي خانة ناقصة أو تعديلها (المورد، البراند، إلخ) لصنف معين في جدول المخزن والحركات."""
        # ... باقي الكود كما هو بدون تغيير في المسافات الداخلية ...
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
